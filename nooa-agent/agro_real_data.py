"""
TerraSAT — Colector de datos reales multi-producto (agro / forest / urban).

Sentinel-2 L2A via CDSE Statistical API — una llamada por zona/ventana
devuelve NDVI, NDRE, NBR, NDBI, NDWI + fracción de pixels "estresados"
(definición por producto). Máscara de nubes por pixel vía banda SCL.

- agro:   ventana 21d vs mismo período año-1 + lluvia ERA5 (Open-Meteo).
          Estrés pixel = NDVI < baseline_mean - 0.05.
- forest: ventana 60d vs año-1. Estrés pixel = NDVI < baseline - 0.05
          (deforestación/degradación). NBR reportado para quema.
- urban:  ventana 60d vs año-1. Estrés pixel = NDBI > baseline + 0.05
          (ganancia de área construida) + NDVI reportado.

Zonas sin imagen limpia -> status "sin_datos" (nunca inventa valores).

Salidas: mutación in-place de zonas + scripts/<product>-zones.json

Ejecutar standalone:
  uv run python nooa-agent/agro_real_data.py [--product agro|forest|urban] [--limit N]
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

logger = logging.getLogger(__name__)

STATS_API_URL = "https://sh.dataspace.copernicus.eu/statistics/v1"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

CLIMATOLOGY_YEARS = 5
OPEN_METEO_ARCHIVE_DELAY_DAYS = 6  # ERA5 llega con ~5 días de retraso
MAX_BBOX_DELTA = 0.40  # cap del footprint (~44 km de lado por eje)


# ═════════════════════════════════════════════════════════════════════
# Productos
# ═════════════════════════════════════════════════════════════════════

PRODUCTS = {
    "agro": {
        "zones_config": "agro_zones_config.json",
        "out_json": "agro-zones.json",
        "window_days": 21,
        # Pixel estresado: NDVI bajo media baseline - margen
        "stress_index": "ndvi", "stress_op": "<", "stress_margin": 0.05,
        "with_rain": True,
        "classify": "agro",
    },
    "forest": {
        "zones_config": "forest_zones_config.json",
        "out_json": "forest-zones.json",
        "window_days": 60,
        "stress_index": "ndvi", "stress_op": "<", "stress_margin": 0.05,
        "with_rain": False,
        "classify": "forest",
    },
    "urban": {
        "zones_config": "urban_zones_config.json",
        "out_json": "urban-zones.json",
        "window_days": 60,
        # Pixel "expandido": NDBI sobre media baseline + margen
        "stress_index": "ndbi", "stress_op": ">", "stress_margin": 0.05,
        "with_rain": False,
        "classify": "urban",
    },
}


# ═════════════════════════════════════════════════════════════════════
# Evalscript unificado — todos los índices en una sola llamada
# ═════════════════════════════════════════════════════════════════════

EVALSCRIPT_ALL = """
//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B03", "B04", "B05", "B08", "B11", "B12", "SCL", "dataMask"],
      units: ["REFLECTANCE","REFLECTANCE","REFLECTANCE","REFLECTANCE","REFLECTANCE","REFLECTANCE","DN","DN"]
    }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "ndre", bands: 1, sampleType: "FLOAT32" },
      { id: "nbr", bands: 1, sampleType: "FLOAT32" },
      { id: "ndbi", bands: 1, sampleType: "FLOAT32" },
      { id: "ndwi", bands: 1, sampleType: "FLOAT32" },
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
  let nbr  = (s.B08 - s.B12) / (s.B08 + s.B12);
  let ndbi = (s.B11 - s.B08) / (s.B11 + s.B08);
  let ndwi = (s.B03 - s.B08) / (s.B03 + s.B08);
  // STRESS_EXPR se inyecta por llamada (baseline -> expr falsa)
  let stressed = (clear && (STRESS_EXPR)) ? 1.0 : 0.0;
  return { ndvi: [ndvi], ndre: [ndre], nbr: [nbr], ndbi: [ndbi],
           ndwi: [ndwi], stressed: [stressed], dataMask: [clear] };
}
"""


def _evalscript(stress_expr: str | None) -> str:
    expr = stress_expr or "false"
    return EVALSCRIPT_ALL.replace("STRESS_EXPR", expr)


# ═════════════════════════════════════════════════════════════════════
# Sentinel-2 — Statistical API
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


INDEX_IDS = ("ndvi", "ndre", "nbr", "ndbi", "ndwi")


def request_index_stats(
    token: str,
    bbox: list[float],
    time_range: tuple[str, str],
    width: int = 64,
    height: int = 64,
    stress_expr: str | None = None,
) -> dict:
    """
    Stats de todos los índices de una ventana temporal. Devuelve:
      {"ndvi","ndre","nbr","ndbi","ndwi","stressed_frac","n_days","latest_date"}
    o {"error": "..."}.

    stressed_frac = fracción de pixels limpios que cumplen stress_expr
    (p.ej. "ndvi < 0.54" o "ndbi > 0.23"). Medido por pixel — no estimado.
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
            "evalscript": _evalscript(stress_expr),
            "width": width,
            "height": height,
        },
    }

    import time
    resp = None
    for attempt in range(3):
        try:
            resp = requests.post(
                STATS_API_URL,
                json=request_body,
                headers={"Authorization": f"Bearer {token}"},
                timeout=120,
            )
        except requests.RequestException as e:
            return {"error": f"HTTP request falló: {e}"}
        if resp.status_code != 429:
            break
        time.sleep(15 * (attempt + 1))  # throttling transitorio — reintento

    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}

    means: dict[str, list] = {k: [] for k in INDEX_IDS}
    stressed_means, latest_date = [], ""
    for interval in resp.json().get("data", []):
        outputs = interval.get("outputs", {})
        ndvi_stats = outputs.get("ndvi", {}).get("bands", {}).get("B0", {}).get("stats", {})
        ndvi_mean = ndvi_stats.get("mean")
        # NaN = todos los pixels enmascarados (nubes densas) -> día inválido
        if ndvi_mean is None or math.isnan(float(ndvi_mean)):
            continue
        for k in INDEX_IDS:
            v = outputs.get(k, {}).get("bands", {}).get("B0", {}).get("stats", {}).get("mean")
            if v is not None and not math.isnan(float(v)):
                means[k].append(float(v))
        s = outputs.get("stressed", {}).get("bands", {}).get("B0", {}).get("stats", {}).get("mean")
        if s is not None and not math.isnan(float(s)):
            stressed_means.append(float(s))
        latest_date = interval.get("interval", {}).get("from", "")[:10]

    if not means["ndvi"]:
        return {"error": "Sin días válidos en la ventana"}

    out = {
        "stressed_frac": (sum(stressed_means) / len(stressed_means)) if stressed_means else 0.0,
        "n_days": len(means["ndvi"]),
        "latest_date": latest_date,
    }
    for k in INDEX_IDS:
        out[k] = (sum(means[k]) / len(means[k])) if means[k] else None
    return out


# Compat: nombre anterior usado en imports viejos
request_ndvi_ndre_stats = request_index_stats


# ═════════════════════════════════════════════════════════════════════
# Open-Meteo ERA5 — precipitación vs climatología (solo agro)
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
# Clasificadores por producto
# ═════════════════════════════════════════════════════════════════════

def _classify_forest(z, d_nbr: float | None):
    """Deforestación/quema: caída de NDVI y NBR vs año anterior."""
    nbr = d_nbr if d_nbr is not None else 0.0
    if z.ndvi_delta < -0.08 and nbr < -0.05:
        z.status, z.alert_cause = "critico", "Deforestación o quema severa"
    elif z.ndvi_delta < -0.04 or nbr < -0.03:
        z.status, z.alert_cause = "alerta", "Pérdida de cobertura forestal"
    elif z.ndvi_delta < -0.02 or nbr < -0.015:
        z.status, z.alert_cause = "vigilancia", "Degradación incipiente"
    else:
        z.status, z.alert_cause = "normal", ""


def _classify_urban(z, d_ndbi: float | None):
    """Expansión urbana: NDBI sube (más construido) + NDVI baja."""
    ndbi = d_ndbi if d_ndbi is not None else 0.0
    if ndbi > 0.08 and z.ndvi_delta < -0.04:
        z.status, z.alert_cause = "critico", "Expansión urbana masiva"
    elif ndbi > 0.05 and z.ndvi_delta < -0.02:
        z.status, z.alert_cause = "alerta", "Expansión urbana acelerada"
    elif ndbi > 0.02 or (ndbi > 0.015 and z.ndvi_delta < -0.02):
        z.status, z.alert_cause = "vigilancia", "Crecimiento urbano detectado"
    else:
        z.status, z.alert_cause = "normal", ""


CLASSIFIERS = {
    "forest": _classify_forest,
    "urban": _classify_urban,
}


# ═════════════════════════════════════════════════════════════════════
# Colector principal
# ═════════════════════════════════════════════════════════════════════

def load_zones(product: str) -> list:
    """Carga nooa-agent/<product>_zones_config.json → lista de zonas.
    Para agro delega en generate_zones (mantiene el fallback interno)."""
    from demo_alerta_temprana_regional import AgroZone, generate_zones

    if product == "agro":
        return generate_zones()

    cfg_path = Path(__file__).parent / PRODUCTS[product]["zones_config"]
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    zones = []
    for z in data["zones"]:
        lat, lng = float(z["lat"]), float(z["lng"])
        zones.append(AgroZone(
            z.get("name") or f"Zona {lat:.2f},{lng:.2f}",
            z.get("country", ""),
            z.get("crop", "Zona"),
            lat, lng,
            int(z.get("area_ha", 50000)),
        ))
    return zones


def collect_real_zones(
    zones: list,
    today: date | None = None,
    verbose: bool = True,
    product: str = "agro",
) -> list:
    """
    Llena cada zona con datos reales (deltas de índices, lluvia si aplica)
    y clasifica su estado según el producto. Mutación in-place.
    """
    spec = PRODUCTS[product]
    today = today or date.today()
    win = spec["window_days"]

    cur_end = today
    cur_start = today - timedelta(days=win)
    base_end = cur_end - timedelta(days=365)
    base_start = cur_start - timedelta(days=365)

    meteo_end = today - timedelta(days=OPEN_METEO_ARCHIVE_DELAY_DAYS)
    meteo_start = meteo_end - timedelta(days=win)

    cur_range = (f"{cur_start.isoformat()}T00:00:00Z", f"{cur_end.isoformat()}T23:59:59Z")
    base_range = (f"{base_start.isoformat()}T00:00:00Z", f"{base_end.isoformat()}T23:59:59Z")

    if verbose:
        print(f"  Producto: {product} | ventana {win}d")
        print(f"  Ventana actual:   {cur_start} -> {cur_end}")
        print(f"  Baseline (ano-1): {base_start} -> {base_end}")
        print(f"  Autenticando con CDSE...")

    token = get_token()
    if verbose:
        print("  OK\n")

    idx = spec["stress_index"]
    op = spec["stress_op"]
    margin = spec["stress_margin"]

    for z in zones:
        bbox = zone_bbox(z.lat, z.lng, z.area_ha)
        if verbose:
            print(f"  {z.name}, {z.country} ({z.crop})")

        base = request_index_stats(token, bbox, base_range)

        # Pixel estresado: índice cruza (media baseline ± margen).
        # Mismo umbral en ambas ventanas; el exceso cur-base cancela la
        # dispersión natural de la zona. Medido por pixel — no estimado.
        if "error" not in base and base.get(idx) is not None:
            thr = base[idx] - margin if op == "<" else base[idx] + margin
            stress_expr = f"{idx} {op} {thr:.4f}"
            base_stress = request_index_stats(token, bbox, base_range, stress_expr=stress_expr)
        else:
            stress_expr, base_stress = None, {"error": base.get("error", "?")}

        cur = request_index_stats(token, bbox, cur_range, stress_expr=stress_expr)

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
            d_nbr = (cur["nbr"] - base["nbr"]) if (cur["nbr"] and base["nbr"]) else None
            d_ndbi = (cur["ndbi"] - base["ndbi"]) if (cur["ndbi"] and base["ndbi"]) else None
            d_ndwi = (cur["ndwi"] - base["ndwi"]) if (cur["ndwi"] and base["ndwi"]) else None

            if spec["with_rain"]:
                precip = fetch_precipitation(z.lat, z.lng, meteo_start, meteo_end)
                z.rainfall_mm = 0.0 if "error" in precip else precip["mm"]
                z.rainfall_pct = 0.0 if "error" in precip else precip["pct"]
            else:
                precip = {"skipped": f"no aplica a {product}"}
                z.rainfall_mm, z.rainfall_pct = 0.0, 0.0

            if spec["classify"] == "agro":
                from demo_alerta_temprana_regional import classify_zone
                classify_zone(z)
            else:
                CLASSIFIERS[spec["classify"]](z, d_nbr if spec["classify"] == "forest" else d_ndbi)

            # Área afectada medida: exceso de pixels estresados vs baseline
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
            # Índices extra por producto (meta = auditoría completa)
            if d_nbr is not None:
                z.data_meta["nbr_base"], z.data_meta["nbr_cur"], z.data_meta["nbr_delta"] = (
                    round(base["nbr"], 4), round(cur["nbr"], 4), round(d_nbr, 4))
            if d_ndbi is not None:
                z.data_meta["ndbi_base"], z.data_meta["ndbi_cur"], z.data_meta["ndbi_delta"] = (
                    round(base["ndbi"], 4), round(cur["ndbi"], 4), round(d_ndbi, 4))
            if d_ndwi is not None:
                z.data_meta["ndwi_base"], z.data_meta["ndwi_cur"], z.data_meta["ndwi_delta"] = (
                    round(base["ndwi"], 4), round(cur["ndwi"], 4), round(d_ndwi, 4))

            if verbose:
                extra = ""
                if spec["classify"] == "forest":
                    extra = f" | NBR d{d_nbr:+.3f}"
                elif spec["classify"] == "urban":
                    extra = f" | NDBI d{d_ndbi:+.3f}"
                rain = f" | lluvia {z.rainfall_pct:+.0f}%" if spec["with_rain"] else ""
                print(
                    f"    NDVI d{z.ndvi_delta:+.3f}{extra}{rain} | "
                    f"pix afectados {excess_frac*100:.0f}% | {cur['n_days']}d -> {z.status}"
                )

    dump_zones_json(zones, source="real", today=today,
                    window={"current": cur_range, "baseline": base_range},
                    product=product)
    return zones


# ═════════════════════════════════════════════════════════════════════
# Export a JSON
# ═════════════════════════════════════════════════════════════════════

def dump_zones_json(zones: list, source: str, today: date,
                    window: dict | None = None, product: str = "agro") -> Path:
    output_dir = Path("scripts")
    output_dir.mkdir(exist_ok=True)
    path = output_dir / PRODUCTS[product]["out_json"]

    payload = {
        "product": product,
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

    parser = argparse.ArgumentParser(
        description="TerraSAT — colector de datos reales Sentinel-2 (multi-producto)")
    parser.add_argument("--product", default="agro", choices=list(PRODUCTS))
    parser.add_argument("--limit", type=int, default=None, help="Procesar solo las primeras N zonas (test)")
    args = parser.parse_args()

    zones = load_zones(args.product)
    if args.limit:
        zones = zones[: args.limit]

    collect_real_zones(zones, product=args.product)
    print(f"\n  JSON: scripts/{PRODUCTS[args.product]['out_json']}")


if __name__ == "__main__":
    main()
