"""
TerraSAT / AgroSAT — Colector de datos reales para el boletín pan-regional.

Reemplaza la simulación de demo_alerta_temprana_regional con:

  - Sentinel-2 L2A via CDSE Statistical API: NDVI + NDRE reales por zona,
    ventana actual (21 días) vs mismo período del año anterior.
    Máscara de nubes por pixel usando banda SCL.
  - Open-Meteo ERA5 archive: precipitación real del período vs
    climatología de los últimos 5 años (mismo rango calendario).

Zonas sin imagen limpia en la ventana quedan con status "sin_datos".

Salidas:
  - Mutación in-place de las AgroZone (mismos campos que simulate_zones)
  - scripts/agro-zones.json — insumo para generate_map.py

Ejecutar standalone:  uv run python nooa-agent/agro_real_data.py [--limit N]
"""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))

from analyze_satelital import get_token  # noqa: E402
from demo_alerta_temprana_regional import classify_zone  # noqa: E402

logger = logging.getLogger(__name__)

STATS_API_URL = "https://sh.dataspace.copernicus.eu/statistics/v1"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

CURRENT_WINDOW_DAYS = 21
CLIMATOLOGY_YEARS = 5
OPEN_METEO_ARCHIVE_DELAY_DAYS = 6  # ERA5 llega con ~5 días de retraso
MAX_BBOX_DELTA = 0.40  # cap del footprint (~44 km de lado por eje)

EVALSCRIPT_NDVI_NDRE = """
//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B04", "B05", "B08", "SCL", "dataMask"],
      units: ["REFLECTANCE", "REFLECTANCE", "REFLECTANCE", "DN", "DN"]
    }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "ndre", bands: 1, sampleType: "FLOAT32" },
      { id: "stressed", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(s) {
  // SCL: 3=sombra de nube, 8/9/10=nubes, 11=nieve -> excluir
  let clear = (s.dataMask == 1 && s.SCL != 3 && s.SCL != 8 &&
               s.SCL != 9 && s.SCL != 10 && s.SCL != 11) ? 1 : 0;
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04);
  let ndre = (s.B08 - s.B05) / (s.B08 + s.B05);
  // Umbral inyectado por llamada (baseline -> -999, nunca estresado)
  let stressed = (clear && ndvi < STRESS_NDVI_THRESHOLD) ? 1.0 : 0.0;
  return { ndvi: [ndvi], ndre: [ndre], stressed: [stressed], dataMask: [clear] };
}
"""


def _evalscript(stress_threshold: float) -> str:
    return EVALSCRIPT_NDVI_NDRE.replace("STRESS_NDVI_THRESHOLD", f"{stress_threshold:.4f}")


# ═════════════════════════════════════════════════════════════════════
# Sentinel-2 — Statistical API (NDVI + NDRE en una sola llamada)
# ═════════════════════════════════════════════════════════════════════

def zone_bbox(lat: float, lng: float, area_ha: float) -> list[float]:
    """Bbox [minLng, minLat, maxLng, maxLat] centrado en la zona."""
    area_km2 = area_ha / 100.0
    side_km = math.sqrt(area_km2)
    lat_delta = side_km / 111.0 / 2
    lng_delta = side_km / (111.0 * math.cos(math.radians(lat))) / 2
    lat_delta = min(max(lat_delta, 0.05), MAX_BBOX_DELTA)
    lng_delta = min(max(lng_delta, 0.05), MAX_BBOX_DELTA)
    return [lng - lng_delta, lat - lat_delta, lng + lng_delta, lat + lat_delta]


def request_ndvi_ndre_stats(
    token: str,
    bbox: list[float],
    time_range: tuple[str, str],
    width: int = 64,
    height: int = 64,
    stress_threshold: float = -999.0,
) -> dict:
    """
    Stats NDVI+NDRE de una ventana temporal. Devuelve:
      {"ndvi", "ndre", "stressed_frac", "n_days", "latest_date"}
    o {"error": "..."} si falla o no hay días válidos.

    stressed_frac = fracción de pixels limpios con NDVI < stress_threshold.
    Medido por pixel — no estimado. Con threshold=-999 siempre es 0.
    """
    request_body = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
            },
            "data": [{
                "dataFilter": {
                    "timeRange": {"from": time_range[0], "to": time_range[1]},
                    "maxCloudCoverage": 80,
                },
                "type": "sentinel-2-l2a",
            }],
        },
        "aggregation": {
            "timeRange": {"from": time_range[0], "to": time_range[1]},
            "aggregationInterval": {"of": "P1D"},
            "evalscript": _evalscript(stress_threshold),
            "width": width,
            "height": height,
        },
    }

    try:
        resp = requests.post(
            STATS_API_URL,
            json=request_body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
    except requests.RequestException as e:
        return {"error": f"HTTP request falló: {e}"}

    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}

    ndvi_means, ndre_means, stressed_means, latest_date = [], [], [], ""
    for interval in resp.json().get("data", []):
        outputs = interval.get("outputs", {})
        ndvi_stats = outputs.get("ndvi", {}).get("bands", {}).get("B0", {}).get("stats", {})
        ndre_stats = outputs.get("ndre", {}).get("bands", {}).get("B0", {}).get("stats", {})
        stressed_stats = outputs.get("stressed", {}).get("bands", {}).get("B0", {}).get("stats", {})
        if ndvi_stats.get("mean") is not None and ndre_stats.get("mean") is not None:
            ndvi_means.append(float(ndvi_stats["mean"]))
            ndre_means.append(float(ndre_stats["mean"]))
            if stressed_stats.get("mean") is not None:
                stressed_means.append(float(stressed_stats["mean"]))
            latest_date = interval.get("interval", {}).get("from", "")[:10]

    if not ndvi_means:
        return {"error": "Sin días válidos en la ventana"}

    return {
        "ndvi": sum(ndvi_means) / len(ndvi_means),
        "ndre": sum(ndre_means) / len(ndre_means),
        "stressed_frac": (sum(stressed_means) / len(stressed_means)) if stressed_means else 0.0,
        "n_days": len(ndvi_means),
        "latest_date": latest_date,
    }


# ═════════════════════════════════════════════════════════════════════
# Open-Meteo ERA5 — precipitación vs climatología
# ═════════════════════════════════════════════════════════════════════

def fetch_precipitation(
    lat: float,
    lng: float,
    start: date,
    end: date,
    years_back: int = CLIMATOLOGY_YEARS,
) -> dict:
    """
    Precipitación de la ventana [start, end] vs climatología de los
    años anteriores (mismo rango calendario). Devuelve:
      {"mm": float, "pct": float, "n_days": int, "normal_mm": float}
    o {"error": "..."}.
    """
    first_year = start.year - years_back
    try:
        range_start = date(first_year, start.month, start.day)
    except ValueError:  # 29 de febrero
        range_start = date(first_year, 2, 28)

    try:
        resp = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lng,
                "start_date": range_start.isoformat(),
                "end_date": end.isoformat(),
                "daily": "precipitation_sum",
                "timezone": "UTC",
            },
            timeout=60,
        )
    except requests.RequestException as e:
        return {"error": f"Open-Meteo falló: {e}"}

    if resp.status_code != 200:
        return {"error": f"Open-Meteo HTTP {resp.status_code}: {resp.text[:200]}"}

    daily = resp.json().get("daily", {})
    dates, values = daily.get("time", []), daily.get("precipitation_sum", [])
    precip_by_day = {d: v for d, v in zip(dates, values) if v is not None}

    def window_sum(y: int) -> tuple[float, int]:
        try:
            s = date(y, start.month, start.day)
            e = date(y, end.month, end.day)
        except ValueError:
            s = date(y, 2, 28)
            e = date(y, 2, 28)
        days = [(s + timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]
        vals = [precip_by_day[d] for d in days if d in precip_by_day]
        return sum(vals), len(vals)

    cur_mm, cur_days = window_sum(end.year)
    if cur_days < (end - start).days // 2:
        return {"error": "Precipitación insuficiente en la ventana actual"}

    year_sums = []
    for y in range(first_year, end.year):
        s, n = window_sum(y)
        if n >= (end - start).days // 2:
            year_sums.append(s)

    if not year_sums:
        return {"error": "Sin climatología disponible"}

    normal = sum(year_sums) / len(year_sums)
    pct = ((cur_mm - normal) / normal * 100) if normal > 0 else 0.0
    return {"mm": cur_mm, "pct": pct, "n_days": cur_days, "normal_mm": normal}


# ═════════════════════════════════════════════════════════════════════
# Colector principal
# ═════════════════════════════════════════════════════════════════════

def collect_real_zones(zones: list, today: date | None = None, verbose: bool = True) -> list:
    """
    Llena cada AgroZone con datos reales (ndvi_delta, ndre_delta,
    rainfall_mm, rainfall_pct) y clasifica su estado. Mutación in-place.
    """
    today = today or date.today()
    cur_end = today
    cur_start = today - timedelta(days=CURRENT_WINDOW_DAYS)
    base_end = cur_end - timedelta(days=365)
    base_start = cur_start - timedelta(days=365)

    meteo_end = today - timedelta(days=OPEN_METEO_ARCHIVE_DELAY_DAYS)
    meteo_start = meteo_end - timedelta(days=CURRENT_WINDOW_DAYS)

    cur_range = (f"{cur_start.isoformat()}T00:00:00Z", f"{cur_end.isoformat()}T23:59:59Z")
    base_range = (f"{base_start.isoformat()}T00:00:00Z", f"{base_end.isoformat()}T23:59:59Z")

    if verbose:
        print(f"  Ventana actual:   {cur_start} -> {cur_end}")
        print(f"  Baseline (ano-1): {base_start} -> {base_end}")
        print(f"  Autenticando con CDSE...")

    token = get_token()
    if verbose:
        print("  OK\n")

    for z in zones:
        bbox = zone_bbox(z.lat, z.lng, z.area_ha)
        if verbose:
            print(f"  {z.name}, {z.country} ({z.crop})")

        base = request_ndvi_ndre_stats(token, bbox, base_range)

        # Umbral de pixel estresado: media baseline - 0.05. Se aplica el
        # MISMO umbral a la ventana baseline y a la actual; el área afectada
        # es el EXCESO de pixels degradados (cur - base), así se cancela la
        # dispersión natural de la zona (una zona sana siempre tiene pixels
        # por debajo de su propia media).
        if "error" not in base:
            stress_threshold = base["ndvi"] - 0.05
            base_stress = request_ndvi_ndre_stats(token, bbox, base_range, stress_threshold=stress_threshold)
        else:
            stress_threshold, base_stress = -999.0, {"error": base["error"]}

        cur = request_ndvi_ndre_stats(token, bbox, cur_range, stress_threshold=stress_threshold)

        if "error" in cur or "error" in base:
            z.status = "sin_datos"
            z.alert_cause = "Sin imagen limpia (nubosidad)"
            z.affected_area_ha = 0
            z.days_early_warning = 0
            z.data_meta = {"error_cur": cur.get("error"), "error_base": base.get("error")}
            if verbose:
                print(f"    sin datos — cur: {cur.get('error', 'ok')[:60]} | base: {base.get('error', 'ok')[:60]}")
        else:
            z.ndvi_delta = cur["ndvi"] - base["ndvi"]
            z.ndre_delta = cur["ndre"] - base["ndre"]

            precip = fetch_precipitation(z.lat, z.lng, meteo_start, meteo_end)
            if "error" in precip:
                z.rainfall_mm = 0.0
                z.rainfall_pct = 0.0
            else:
                z.rainfall_mm = precip["mm"]
                z.rainfall_pct = precip["pct"]

            classify_zone(z)

            # ── Área afectada medida: exceso de pixels degradados ──
            # Fracción de pixels con NDVI < umbral en ventana actual MENOS
            # la misma fracción medida en el baseline. Medido, no estimado.
            excess_frac = max(0.0, cur["stressed_frac"] - base_stress.get("stressed_frac", 0.0))
            if z.status in ("critico", "alerta", "vigilancia"):
                z.affected_area_ha = int(round(z.area_ha * excess_frac, -2))
                affected_method = "pixel_excess_fraction"
            else:
                z.affected_area_ha = 0
                affected_method = "none"

            # Anticipación no se mide — se reporta la fecha de la última imagen
            z.days_early_warning = 0

            z.data_meta = {
                "ndvi_base": round(base["ndvi"], 4), "ndvi_cur": round(cur["ndvi"], 4),
                "ndre_base": round(base["ndre"], 4), "ndre_cur": round(cur["ndre"], 4),
                "days_base": base["n_days"], "days_cur": cur["n_days"],
                "latest_image": cur["latest_date"],
                "stressed_frac_cur": round(cur["stressed_frac"], 4),
                "stressed_frac_base": round(base_stress.get("stressed_frac", 0.0), 4),
                "excess_stressed_frac": round(excess_frac, 4),
                "affected_method": affected_method,
                "precip": precip,
            }
            if verbose:
                print(
                    f"    NDVI {base['ndvi']:.3f}->{cur['ndvi']:.3f} (d{z.ndvi_delta:+.3f}) | "
                    f"NDRE d{z.ndre_delta:+.3f} | lluvia {z.rainfall_pct:+.0f}% | "
                    f"pix afectados {excess_frac*100:.0f}% ({cur['stressed_frac']*100:.0f}%"
                    f"-{base_stress.get('stressed_frac', 0)*100:.0f}%) | "
                    f"{cur['n_days']}d -> {z.status}"
                )

    dump_zones_json(zones, source="real", today=today,
                    window={"current": cur_range, "baseline": base_range})
    return zones


# ═════════════════════════════════════════════════════════════════════
# Export a JSON (insumo de generate_map.py)
# ═════════════════════════════════════════════════════════════════════

def dump_zones_json(zones: list, source: str, today: date, window: dict | None = None) -> Path:
    output_dir = Path("scripts")
    output_dir.mkdir(exist_ok=True)
    path = output_dir / "agro-zones.json"

    payload = {
        "generated_at": today.isoformat(),
        "source": source,
        "window": window or {},
        "zones": [
            {
                "name": z.name, "country": z.country, "crop": z.crop,
                "lat": z.lat, "lng": z.lng, "area_ha": z.area_ha,
                "status": z.status, "alert_cause": z.alert_cause,
                "affected_area_ha": z.affected_area_ha,
                "days_early_warning": z.days_early_warning,
                "ndvi_delta": round(z.ndvi_delta, 4),
                "ndre_delta": round(z.ndre_delta, 4),
                "rainfall_mm": round(z.rainfall_mm, 1),
                "rainfall_pct": round(z.rainfall_pct, 1),
                "meta": getattr(z, "data_meta", {}),
            }
            for z in zones
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ═════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════

def main():
    import argparse

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="AgroSAT — colector de datos reales Sentinel-2 + Open-Meteo")
    parser.add_argument("--limit", type=int, default=None, help="Procesar solo las primeras N zonas (test)")
    args = parser.parse_args()

    from demo_alerta_temprana_regional import generate_zones

    zones = generate_zones()
    if args.limit:
        zones = zones[: args.limit]

    collect_real_zones(zones)
    print(f"\n  JSON: scripts/agro-zones.json")


if __name__ == "__main__":
    main()
