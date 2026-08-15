"""
Análisis real de imágenes Sentinel-2 pre/post terremoto Colombia M7.4 (10-ago-2026).
Usa CDSE Statistical API para obtener NDVI y NBR promedio sin descargar imágenes completos.
También descarga imágenes true color PNG del epicentro.

Zonas: epicentro San José del Palmar (Chocó), Pereira, Cali, Manizales, Quibdó, Armenia.
"""

from __future__ import annotations

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STATS_API_URL = "https://sh.dataspace.copernicus.eu/statistics/v1"
PROCESS_API_URL = "https://sh.dataspace.copernicus.eu/process/v1"

ZONES = [
    {"name": "San José del Palmar (epicentro)", "lat": 4.80, "lng": -76.50},
    {"name": "Pereira", "lat": 4.81, "lng": -75.70},
    {"name": "Cali", "lat": 3.45, "lng": -76.53},
    {"name": "Manizales", "lat": 5.07, "lng": -75.52},
    {"name": "Quibdó", "lat": 5.69, "lng": -76.66},
    {"name": "Armenia", "lat": 4.54, "lng": -75.71},
]

PRE_DATE_RANGE = ("2026-07-28T00:00:00Z", "2026-08-08T23:59:59Z")
POST_DATE_RANGE = ("2026-08-10T00:00:00Z", "2026-08-14T23:59:59Z")


def get_token() -> str:
    data = {
        "client_id": "cdse-public",
        "grant_type": "password",
        "username": os.getenv("CDSE_USERNAME", ""),
        "password": os.getenv("CDSE_PASSWORD", ""),
    }
    resp = requests.post(CDSE_TOKEN_URL, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def request_stats(token: str, bbox: list, time_range: tuple, index: str = "ndvi") -> dict:
    """
    Usa Statistical API para obtener promedio de NDVI o NBR.
    Retorna {mean, min, max, std, date} del índice.
    """
    bands = ["B04", "B08"] if index == "ndvi" else ["B08", "B12"]
    b0, b1 = bands[0], bands[1]

    evalscript = f"""
//VERSION=3
function setup() {{
  return {{
    input: [{{
      bands: ["{b0}", "{b1}", "dataMask"],
      units: "REFLECTANCE"
    }}],
    output: [{{
      id: "index",
      bands: 1,
      sampleType: "FLOAT32"
    }}, {{
      id: "dataMask",
      bands: 1
    }}]
  }};
}}
function evaluatePixel(sample) {{
  let val = (sample.{b0} - sample.{b1}) / (sample.{b0} + sample.{b1});
  return {{ index: [val], dataMask: [sample.dataMask] }};
}}
"""

    request_body = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}
            },
            "data": [{
                "dataFilter": {
                    "timeRange": {
                        "from": time_range[0],
                        "to": time_range[1]
                    }
                },
                "type": "sentinel-2-l1c"
            }]
        },
        "aggregation": {
            "timeRange": {
                "from": time_range[0],
                "to": time_range[1]
            },
            "aggregationInterval": {
                "of": "P1D"
            },
            "evalscript": evalscript,
            "width": 100,
            "height": 100
        }
    }

    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(STATS_API_URL, json=request_body, headers=headers, timeout=120)

    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}

    data = resp.json()

    try:
        intervals = data.get("data", [])
        if not intervals:
            return {"error": "Sin intervalos con datos", "raw": str(data)[:300]}

        # Filtrar intervalos con datos válidos
        valid_intervals = []
        for interval in intervals:
            idx_output = interval.get("outputs", {}).get("index", {})
            bands = idx_output.get("bands", {})
            b0_stats = bands.get("B0", {}).get("stats", {})
            if "mean" in b0_stats and b0_stats["mean"] is not None:
                valid_intervals.append((interval, b0_stats))

        if not valid_intervals:
            return {"error": "Sin datos válidos en ningún día", "raw": str(data)[:300]}

        best, idx_stats = valid_intervals[0]
        date = best.get("interval", {}).get("from", "")[:10]

        return {
            "mean": float(idx_stats["mean"]),
            "min": float(idx_stats.get("min", 0)),
            "max": float(idx_stats.get("max", 0)),
            "std": float(idx_stats.get("stDev", 0)),
            "date": date,
        }
    except (KeyError, TypeError) as e:
        return {"error": f"Error parseando: {e}", "raw": str(data)[:500]}


def request_true_color(token: str, bbox: list, time_range: tuple, output_path: str) -> bool:
    """Descarga imagen true color (RGB) de Sentinel-2 en PNG."""
    evalscript = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B02", "B03", "B04"] }],
    output: { bands: 3, sampleType: "AUTO" }
  };
}
function evaluatePixel(sample) {
  return [sample.B04 * 2.5, sample.B03 * 2.5, sample.B02 * 2.5];
}
"""
    request_body = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}
            },
            "data": [{
                "dataFilter": {"timeRange": {"from": time_range[0], "to": time_range[1]}},
                "type": "sentinel-2-l1c"
            }]
        },
        "output": {"responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
        "evalscript": evalscript
    }

    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(PROCESS_API_URL, json=request_body, headers=headers, timeout=120)

    if resp.status_code != 200:
        print(f"  Error true color: {resp.status_code} {resp.text[:200]}")
        return False

    with open(output_path, "wb") as f:
        f.write(resp.content)
    return True


def main():
    print("=" * 70)
    print("SismoSAT — Análisis Real de Imágenes Sentinel-2")
    print("Terremoto Colombia M7.4 — 10 agosto 2026 — San José del Palmar, Chocó")
    print("=" * 70)

    print("\nAutenticando con CDSE...")
    token = get_token()
    print("OK")

    results = []

    for zone in ZONES:
        name = zone["name"]
        lat, lng = zone["lat"], zone["lng"]
        bbox = [lng - 0.05, lat - 0.05, lng + 0.05, lat + 0.05]

        print(f"\n--- {name} ({lat}, {lng}) ---")

        # NDVI pre-sismo
        print(f"  NDVI pre-sismo (28-jul a 08-ago)...")
        pre_ndvi = request_stats(token, bbox, PRE_DATE_RANGE, "ndvi")
        if "error" in pre_ndvi:
            print(f"  Error: {pre_ndvi['error']}")
            results.append({"zone": name, "error": pre_ndvi["error"]})
            continue
        print(f"  NDVI pre: mean={pre_ndvi['mean']:.3f} ({pre_ndvi['date']})")

        # NDVI post-sismo
        print(f"  NDVI post-sismo (10-14 ago)...")
        post_ndvi = request_stats(token, bbox, POST_DATE_RANGE, "ndvi")
        if "error" in post_ndvi:
            print(f"  Error: {post_ndvi['error']}")
            results.append({"zone": name, "error": post_ndvi["error"]})
            continue
        print(f"  NDVI post: mean={post_ndvi['mean']:.3f} ({post_ndvi['date']})")

        # NBR pre/post
        print(f"  NBR pre-sismo...")
        pre_nbr = request_stats(token, bbox, PRE_DATE_RANGE, "nbr")
        print(f"  NBR post-sismo...")
        post_nbr = request_stats(token, bbox, POST_DATE_RANGE, "nbr")

        delta_ndvi = post_ndvi["mean"] - pre_ndvi["mean"]
        delta_nbr = None
        if "error" not in post_nbr and "error" not in pre_nbr:
            delta_nbr = post_nbr["mean"] - pre_nbr["mean"]

        # Clasificar cambio
        if delta_ndvi < -0.10:
            cambio = "Pérdida severa de vegetación / posible daño estructural"
        elif delta_ndvi < -0.05:
            cambio = "Pérdida moderada de vegetación"
        elif delta_ndvi < -0.02:
            cambio = "Pérdida leve de vegetación"
        elif delta_ndvi > 0.02:
            cambio = "Sin cambio significativo"
        else:
            cambio = "Sin cambio significativo"

        result = {
            "zone": name,
            "lat": lat,
            "lng": lng,
            "ndvi_pre": round(pre_ndvi["mean"], 3),
            "ndvi_pre_date": pre_ndvi["date"],
            "ndvi_post": round(post_ndvi["mean"], 3),
            "ndvi_post_date": post_ndvi["date"],
            "delta_ndvi": round(delta_ndvi, 3),
            "nbr_pre": round(pre_nbr["mean"], 3) if "error" not in pre_nbr else None,
            "nbr_post": round(post_nbr["mean"], 3) if "error" not in post_nbr else None,
            "delta_nbr": round(delta_nbr, 3) if delta_nbr is not None else None,
            "interpretation": cambio,
        }
        results.append(result)
        print(f"  ΔNDVI: {delta_ndvi:+.3f} → {cambio}")

    # Descargar true color del epicentro pre y post
    print("\n\nDescargando imágenes true color del epicentro...")
    scripts_dir = os.path.join(os.path.dirname(__file__), "..", "scripts")
    epicentro_bbox = [-76.55, 4.75, -76.45, 4.85]
    pre_img = os.path.join(scripts_dir, "sismo-epicentro-pre.png")
    post_img = os.path.join(scripts_dir, "sismo-epicentro-post.png")

    if request_true_color(token, epicentro_bbox, PRE_DATE_RANGE, pre_img):
        print(f"  Pre-sismo: {pre_img}")
    if request_true_color(token, epicentro_bbox, POST_DATE_RANGE, post_img):
        print(f"  Post-sismo: {post_img}")

    # Resumen
    print("\n" + "=" * 70)
    print("RESUMEN DE ANÁLISIS ESPECTRAL REAL — Sentinel-2")
    print("=" * 70)
    for r in results:
        if "error" in r:
            print(f"  {r['zone']}: ERROR — {r['error']}")
        else:
            print(f"  {r['zone']}:")
            print(f"    NDVI: {r['ndvi_pre']} ({r['ndvi_pre_date']}) → {r['ndvi_post']} ({r['ndvi_post_date']}) | Δ={r['delta_ndvi']:+.3f}")
            if r.get("delta_nbr") is not None:
                print(f"    NBR:  {r['nbr_pre']} → {r['nbr_post']} | Δ={r['delta_nbr']:+.3f}")
            print(f"    → {r['interpretation']}")

    # Guardar resultados
    output_path = os.path.join(scripts_dir, "sismo-analysis-real.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados: {output_path}")


if __name__ == "__main__":
    main()
