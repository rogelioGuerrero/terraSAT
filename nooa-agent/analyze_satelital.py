"""
TerraSAT — Análisis espectral real de imágenes Sentinel-2 vía CDSE.

Un solo script para todos los productos:
  - sismo:  NDVI + NBR pre/post evento sísmico
  - agro:   NDVI + NDRE estrés agrícola
  - urban:  NDVI + NDBI expansión urbana / islas de calor
  - forest: NDVI + NBR deforestación / quema
  - hidro:  NDWI cuerpos de agua

Uso:
  python analyze_satelital.py --product sismo
  python analyze_satelital.py --product urban
  python analyze_satelital.py --product agro
  python analyze_satelital.py --product forest
  python analyze_satelital.py --product hidro
  python analyze_satelital.py --product sismo --zones "Bogotá:4.6,-74.1;Medellín:6.2,-75.6"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STATS_API_URL = "https://sh.dataspace.copernicus.eu/statistics/v1"
PROCESS_API_URL = "https://sh.dataspace.copernicus.eu/process/v1"

# ═══════════════════════════════════════════════════════════════
# Configuraciones por producto
# ═══════════════════════════════════════════════════════════════

PRODUCT_CONFIGS = {
    "sismo": {
        "title": "SismoSAT — Análisis espectral post-evento sísmico",
        "indices": ["ndvi", "nbr"],
        "zones": [
            {"name": "San José del Palmar (epicentro)", "lat": 4.80, "lng": -76.50},
            {"name": "Pereira", "lat": 4.81, "lng": -75.70},
            {"name": "Cali", "lat": 3.45, "lng": -76.53},
            {"name": "Manizales", "lat": 5.07, "lng": -75.52},
            {"name": "Quibdó", "lat": 5.69, "lng": -76.66},
            {"name": "Armenia", "lat": 4.54, "lng": -75.71},
        ],
        "pre_range": ("2026-07-28T00:00:00Z", "2026-08-08T23:59:59Z"),
        "post_range": ("2026-08-10T00:00:00Z", "2026-08-14T23:59:59Z"),
        "pre_label": "pre-sismo",
        "post_label": "post-sismo",
        "output_json": "sismo-analysis-real.json",
        "image_prefix": "sismo",
        "image_bbox": [-76.55, 4.75, -76.45, 4.85],
    },
    "agro": {
        "title": "AgroSAT — Análisis espectral agrícola",
        "indices": ["ndvi", "ndre"],
        "zones": [
            {"name": "Eje Cafetero (Calarcá)", "lat": 4.52, "lng": -75.64},
            {"name": "Valle del Cauca (caña)", "lat": 3.45, "lng": -76.53},
            {"name": "Llanos (Villavicencio)", "lat": 4.14, "lng": -73.62},
            {"name": "Tolima (arroz)", "lat": 4.44, "lng": -75.24},
            {"name": "Cundinamarca (hortalizas)", "lat": 4.86, "lng": -74.06},
        ],
        "pre_range": ("2026-06-01T00:00:00Z", "2026-06-30T23:59:59Z"),
        "post_range": ("2026-07-15T00:00:00Z", "2026-08-14T23:59:59Z"),
        "pre_label": "junio",
        "post_label": "julio-agosto",
        "output_json": "agro-analysis-real.json",
        "image_prefix": "agro",
        "image_bbox": [-75.69, 4.47, -75.59, 4.57],
    },
    "urban": {
        "title": "UrbanSAT — Análisis de cambio urbano",
        "indices": ["ndvi", "ndbi"],
        "zones": [
            {"name": "Bogotá (centro)", "lat": 4.60, "lng": -74.07},
            {"name": "Bogotá (Soacha sur)", "lat": 4.59, "lng": -74.22},
            {"name": "Medellín", "lat": 6.25, "lng": -75.57},
            {"name": "Cali", "lat": 3.45, "lng": -76.53},
            {"name": "Barranquilla", "lat": 10.96, "lng": -74.80},
            {"name": "Caracas", "lat": 10.49, "lng": -66.88},
            {"name": "Buenos Aires", "lat": -34.61, "lng": -58.39},
            {"name": "Asunción", "lat": -25.26, "lng": -57.59},
            {"name": "Santiago de Chile", "lat": -33.45, "lng": -70.67},
            {"name": "Ciudad de Panamá", "lat": 8.98, "lng": -79.53},
            {"name": "Quito", "lat": -0.18, "lng": -78.47},
            {"name": "Montevideo", "lat": -34.90, "lng": -56.16},
        ],
        "pre_range": ("2024-01-01T00:00:00Z", "2024-03-31T23:59:59Z"),
        "post_range": ("2026-06-01T00:00:00Z", "2026-08-14T23:59:59Z"),
        "pre_label": "2024",
        "post_label": "2026",
        "output_json": "urban-analysis-real.json",
        "image_prefix": "urban",
        "image_bbox": [-74.12, 4.55, -74.02, 4.65],
    },
    "forest": {
        "title": "ForestSAT — Análisis de cobertura forestal",
        "indices": ["ndvi", "nbr"],
        "zones": [
            {"name": "Amazonas (Leticia)", "lat": -4.21, "lng": -69.93},
            {"name": "Chocó (Quibdó)", "lat": 5.69, "lng": -76.66},
            {"name": "Orinoquía (Villavicencio)", "lat": 4.14, "lng": -73.62},
            {"name": "Sierra Nevada (Santa Marta)", "lat": 10.90, "lng": -73.75},
            {"name": "Darién", "lat": 8.40, "lng": -77.40},
        ],
        "pre_range": ("2025-08-01T00:00:00Z", "2025-10-31T23:59:59Z"),
        "post_range": ("2026-06-01T00:00:00Z", "2026-08-14T23:59:59Z"),
        "pre_label": "ago-oct 2025",
        "post_label": "jun-ago 2026",
        "output_json": "forest-analysis-real.json",
        "image_prefix": "forest",
        "image_bbox": [-69.98, -4.26, -69.88, -4.16],
    },
    "hidro": {
        "title": "HidroSAT — Análisis de cuerpos de agua",
        "indices": ["ndwi", "ndvi"],
        "zones": [
            {"name": "Embalse del Guavio", "lat": 4.28, "lng": -73.30},
            {"name": "Laguna de Tota", "lat": 5.55, "lng": -72.90},
            {"name": "Río Magdalena (Honda)", "lat": 5.20, "lng": -74.74},
            {"name": "Ciénaga Grande (Santa Marta)", "lat": 10.85, "lng": -74.35},
            {"name": "Embalse de Betania", "lat": 2.95, "lng": -75.55},
        ],
        "pre_range": ("2026-03-01T00:00:00Z", "2026-04-30T23:59:59Z"),
        "post_range": ("2026-07-01T00:00:00Z", "2026-08-14T23:59:59Z"),
        "pre_label": "marzo-abril",
        "post_label": "julio-agosto",
        "output_json": "hidro-analysis-real.json",
        "image_prefix": "hidro",
        "image_bbox": [-73.35, 4.23, -73.25, 4.33],
    },
}

# ═══════════════════════════════════════════════════════════════
# Definición de índices espectrales
# ═══════════════════════════════════════════════════════════════

INDEX_DEFS = {
    "ndvi": {"bands": ["B04", "B08"], "formula": "(B04 - B08) / (B04 + B08)"},
    "nbr":  {"bands": ["B08", "B12"], "formula": "(B08 - B12) / (B08 + B12)"},
    "ndre": {"bands": ["B05", "B08"], "formula": "(B05 - B08) / (B05 + B08)"},
    "ndbi": {"bands": ["B08", "B12"], "formula": "(B12 - B08) / (B12 + B08)"},
    "ndwi": {"bands": ["B03", "B08"], "formula": "(B03 - B08) / (B03 + B08)"},
}

INDEX_LABELS = {
    "ndvi": "NDVI (vegetación)",
    "nbr":  "NBR (quema/estrés)",
    "ndre": "NDRE (estrés temprano)",
    "ndbi": "NDBI (construcción)",
    "ndwi": "NDWI (agua)",
}


# ═══════════════════════════════════════════════════════════════
# Funciones de la API
# ═══════════════════════════════════════════════════════════════

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


def request_stats(token: str, bbox: list, time_range: tuple, index: str) -> dict:
    """Statistical API: devuelve {mean, min, max, std, date} del índice."""
    b0, b1 = INDEX_DEFS[index]["bands"]

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
                    "timeRange": {"from": time_range[0], "to": time_range[1]}
                },
                "type": "sentinel-2-l1c"
            }]
        },
        "aggregation": {
            "timeRange": {"from": time_range[0], "to": time_range[1]},
            "aggregationInterval": {"of": "P1D"},
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


# ═══════════════════════════════════════════════════════════════
# Interpretación de cambios por producto
# ═══════════════════════════════════════════════════════════════

def interpret_change(product: str, index: str, delta: float) -> str:
    if index == "ndvi":
        if product in ("sismo", "forest"):
            if delta < -0.10:
                return "Pérdida severa de vegetación / posible daño estructural"
            elif delta < -0.05:
                return "Pérdida moderada de vegetación"
            elif delta < -0.02:
                return "Pérdida leve de vegetación"
            else:
                return "Sin cambio significativo"
        elif product == "agro":
            if delta < -0.10:
                return "Estrés severo — posible pérdida de cosecha"
            elif delta < -0.05:
                return "Estrés moderado — requiere atención"
            elif delta < -0.02:
                return "Estrés leve detectado"
            else:
                return "Cultivos saludables"
        elif product == "urban":
            if delta < -0.05:
                return "Pérdida significativa de áreas verdes"
            elif delta < -0.02:
                return "Pérdida leve de vegetación urbana"
            elif delta > 0.02:
                return "Recuperación de vegetación urbana"
            else:
                return "Cobertura vegetal estable"
    elif index == "nbr":
        if delta < -0.10:
            return "Quema severa o daño forestal"
        elif delta < -0.05:
            return "Daño forestal moderado"
        elif delta < -0.02:
            return "Estrés forestal leve"
        else:
            return "Sin daño significativo"
    elif index == "ndre":
        if delta < -0.05:
            return "Estrés nutricional detectado"
        elif delta < -0.02:
            return "Estrés temprano leve"
        else:
            return "Condiciones nutricionales normales"
    elif index == "ndbi":
        if delta > 0.02:
            return "Expansión de superficie construida"
        elif delta > 0.01:
            return "Crecimiento urbano leve"
        else:
            return "Superficie construida estable"
    elif index == "ndwi":
        if delta < -0.05:
            return "Reducción significativa del cuerpo de agua"
        elif delta < -0.02:
            return "Reducción leve del agua"
        elif delta > 0.02:
            return "Aumento del cuerpo de agua"
        else:
            return "Cuerpo de agua estable"
    return "Sin cambio significativo"


# ═══════════════════════════════════════════════════════════════
# Función principal
# ═══════════════════════════════════════════════════════════════

def parse_zones(zones_str: str) -> list:
    """Parsea zonas custom: 'Nombre:lat,lng;Nombre2:lat2,lng2'"""
    zones = []
    for item in zones_str.split(";"):
        parts = item.strip().split(":")
        if len(parts) == 2:
            name = parts[0].strip()
            coords = parts[1].strip().split(",")
            if len(coords) == 2:
                zones.append({"name": name, "lat": float(coords[0]), "lng": float(coords[1])})
    return zones


def main():
    parser = argparse.ArgumentParser(description="TerraSAT — Análisis espectral Sentinel-2")
    parser.add_argument("--product", required=True, choices=PRODUCT_CONFIGS.keys(),
                        help="Producto TerraSAT a analizar")
    parser.add_argument("--zones", type=str, default=None,
                        help="Zonas custom: 'Nombre:lat,lng;Nombre2:lat2,lng2'")
    args = parser.parse_args()

    cfg = PRODUCT_CONFIGS[args.product]

    # Override zones si se pasan custom
    zones = parse_zones(args.zones) if args.zones else cfg["zones"]

    print("=" * 70)
    print(f"{cfg['title']}")
    print(f"Índices: {', '.join(cfg['indices'])}")
    print(f"Período 1 ({cfg['pre_label']}): {cfg['pre_range'][0][:10]} a {cfg['pre_range'][1][:10]}")
    print(f"Período 2 ({cfg['post_label']}): {cfg['post_range'][0][:10]} a {cfg['post_range'][1][:10]}")
    print("=" * 70)

    print("\nAutenticando con CDSE...")
    token = get_token()
    print("OK")

    results = []
    indices = cfg["indices"]

    for zone in zones:
        name = zone["name"]
        lat, lng = zone["lat"], zone["lng"]
        bbox = [lng - 0.05, lat - 0.05, lng + 0.05, lat + 0.05]

        print(f"\n--- {name} ({lat}, {lng}) ---")

        result = {"zone": name, "lat": lat, "lng": lng}

        for idx in indices:
            label = INDEX_LABELS.get(idx, idx)

            # Período 1
            print(f"  {idx.upper()} {cfg['pre_label']}...")
            pre = request_stats(token, bbox, cfg["pre_range"], idx)
            if "error" in pre:
                print(f"  Error: {pre['error'][:100]}")
                result[f"{idx}_pre"] = None
                result[f"{idx}_pre_date"] = None
                continue
            print(f"  {idx.upper()} {cfg['pre_label']}: mean={pre['mean']:.3f} ({pre['date']})")
            result[f"{idx}_pre"] = round(pre["mean"], 3)
            result[f"{idx}_pre_date"] = pre["date"]

            # Período 2
            print(f"  {idx.upper()} {cfg['post_label']}...")
            post = request_stats(token, bbox, cfg["post_range"], idx)
            if "error" in post:
                print(f"  Error: {post['error'][:100]}")
                result[f"{idx}_post"] = None
                result[f"{idx}_post_date"] = None
                continue
            print(f"  {idx.upper()} {cfg['post_label']}: mean={post['mean']:.3f} ({post['date']})")
            result[f"{idx}_post"] = round(post["mean"], 3)
            result[f"{idx}_post_date"] = post["date"]

            # Delta e interpretación
            delta = post["mean"] - pre["mean"]
            result[f"delta_{idx}"] = round(delta, 3)
            interpretation = interpret_change(args.product, idx, delta)
            result[f"interp_{idx}"] = interpretation
            print(f"  Δ{idx.upper()}: {delta:+.3f} → {interpretation}")

        results.append(result)

    # Descargar true color del área principal
    print(f"\n\nDescargando imágenes true color del área principal...")
    scripts_dir = os.path.join(os.path.dirname(__file__), "..", "scripts")
    img_bbox = cfg["image_bbox"]
    pre_img = os.path.join(scripts_dir, f"{cfg['image_prefix']}-area-pre.png")
    post_img = os.path.join(scripts_dir, f"{cfg['image_prefix']}-area-post.png")

    if request_true_color(token, img_bbox, cfg["pre_range"], pre_img):
        print(f"  {cfg['pre_label']}: {pre_img}")
    if request_true_color(token, img_bbox, cfg["post_range"], post_img):
        print(f"  {cfg['post_label']}: {post_img}")

    # Resumen
    print("\n" + "=" * 70)
    print(f"RESUMEN DE ANÁLISIS ESPECTRAL REAL — Sentinel-2")
    print("=" * 70)
    for r in results:
        print(f"\n  {r['zone']}:")
        for idx in indices:
            pre_val = r.get(f"{idx}_pre")
            post_val = r.get(f"{idx}_post")
            delta_val = r.get(f"delta_{idx}")
            interp = r.get(f"interp_{idx}", "")
            if pre_val is not None and post_val is not None:
                pre_date = r.get(f"{idx}_pre_date", "")
                post_date = r.get(f"{idx}_post_date", "")
                print(f"    {idx.upper()}: {pre_val} ({pre_date}) → {post_val} ({post_date}) | Δ={delta_val:+.3f}")
                print(f"    → {interp}")
            else:
                print(f"    {idx.upper()}: Sin datos")

    # Guardar resultados
    output_path = os.path.join(scripts_dir, cfg["output_json"])
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados: {output_path}")


if __name__ == "__main__":
    main()
