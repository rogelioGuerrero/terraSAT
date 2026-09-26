"""
TerraSAT / AgroSAT — Generador de mapa HTML para el boletín

Genera un mapa HTML standalone con Leaflet mostrando:
- Polígonos de países coloreados según el peor estado de sus zonas
- Rectángulos (footprint satelital) por zona, tamaño proporcional al área

El usuario abre el HTML en el navegador, captura la pantalla, y pega en FB.

Salida: scripts/agrosat-map.html

Ejecutar: uv run python nooa-agent/generate_map.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from demo_alerta_temprana_regional import generate_zones, simulate_zones


STATUS_COLOR = {
    "critico": "#dc2626",
    "alerta": "#ea580c",
    "vigilancia": "#ca8a04",
    "normal": "#16a34a",
    "sin_datos": "#9ca3af",
}

STATUS_LABEL = {
    "critico": "Crítico",
    "alerta": "Alerta",
    "vigilancia": "Vigilancia",
    "normal": "Normal",
    "sin_datos": "Sin datos",
}

STATUS_PRIORITY = {"critico": 0, "alerta": 1, "vigilancia": 2, "normal": 3, "sin_datos": 4}

# Mapeo nombre país (en zones) → nombre en Natural Earth GeoJSON
COUNTRY_GEOJSON = {
    "Honduras": "Honduras",
    "Guatemala": "Guatemala",
    "Nicaragua": "Nicaragua",
    "Colombia": "Colombia",
    "Brasil": "Brazil",
    "Argentina": "Argentina",
    "Chile": "Chile",
}


def _zone_bounds(lat: float, lng: float, area_ha: float) -> tuple[float, float, float, float]:
    """Calcula bounds de un rectángulo aproximado para el área de la zona."""
    area_km2 = area_ha / 100.0
    side_km = math.sqrt(area_km2)
    # 1 grado lat ≈ 111 km; lng depende de latitud
    lat_delta = side_km / 111.0 / 2
    lng_delta = side_km / (111.0 * math.cos(math.radians(lat))) / 2
    # Mínimo visible
    lat_delta = max(lat_delta, 0.15)
    lng_delta = max(lng_delta, 0.15)
    return (lat - lat_delta, lng - lng_delta, lat + lat_delta, lng + lng_delta)


def generate_map_html(zones, today_str: str) -> str:
    # Determinar el peor estado por país
    country_status = {}
    for z in zones:
        geo_name = COUNTRY_GEOJSON.get(z.country, z.country)
        current = country_status.get(geo_name)
        if current is None or STATUS_PRIORITY[z.status] < STATUS_PRIORITY[current]:
            country_status[geo_name] = z.status

    # Rectángulos por zona (footprint satelital)
    zones_js = []
    for z in zones:
        color = STATUS_COLOR.get(z.status, "#666")
        south, west, north, east = _zone_bounds(z.lat, z.lng, z.area_ha)
        if z.status == "sin_datos":
            fill_opacity, stroke_weight, dash = 0.10, 1.5, 'dashArray: "5", '
        elif z.status == "normal":
            fill_opacity, stroke_weight, dash = 0.25, 1.5, ""
        else:
            fill_opacity, stroke_weight, dash = 0.40, 2.5, ""

        popup = (
            f"<b>{z.name}, {z.country}</b><br>"
            f"Cultivo: {z.crop}<br>"
            f"Estado: {STATUS_LABEL.get(z.status, z.status)}<br>"
            f"Área: {z.area_ha:,} ha<br>"
        )
        if z.affected_area_ha > 0:
            popup += f"Afectada: {z.affected_area_ha:,} ha<br>"
        if z.alert_cause:
            popup += f"Causa: {z.alert_cause}<br>"
        if z.days_early_warning > 0:
            popup += f"Anticipación: {z.days_early_warning} días"

        popup_escaped = popup.replace("\n", " ").replace('"', '\\"')
        zones_js.append(
            f'    L.rectangle([[{south:.4f}, {west:.4f}], [{north:.4f}, {east:.4f}]], {{'
            f'fillColor: "{color}", '
            f'color: "{color}", '
            f'{dash}'
            f'weight: {stroke_weight}, '
            f'fillOpacity: {fill_opacity}, '
            f'opacity: 0.8'
            f'}}).addTo(map).bindPopup("{popup_escaped}");'
        )

    # Leyenda
    legend_items = []
    for status, color in STATUS_COLOR.items():
        count = sum(1 for z in zones if z.status == status)
        if count > 0:
            legend_items.append(
                f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0;">'
                f'<div style="width:16px;height:12px;border-radius:2px;background:{color};border:1px solid {color};"></div>'
                f'<span>{STATUS_LABEL[status]} ({count})</span>'
                f'</div>'
            )

    total_ha = sum(z.area_ha for z in zones)
    affected_ha = sum(z.affected_area_ha for z in zones if z.status in ("critico", "alerta"))
    countries = sorted(set(z.country for z in zones))

    # JS para colorear países
    country_status_js = ", ".join(
        f'"{name}": "{STATUS_COLOR[status]}"' for name, status in country_status.items()
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TerraSAT / AgroSAT — Mapa de Alerta — {today_str}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #f8fafc; }}
        #map {{ width: 100%; height: 100vh; }}
        .leaflet-popup-content {{ font-size: 13px; line-height: 1.5; }}
        #legend {{
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            color: #1e293b;
            padding: 16px 20px;
            border-radius: 10px;
            font-size: 14px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            border: 1px solid rgba(0,0,0,0.1);
        }}
        #legend h3 {{
            font-size: 16px;
            margin-bottom: 8px;
            color: #0ea5e9;
        }}
        #legend .subtitle {{
            font-size: 12px;
            color: #64748b;
            margin-bottom: 10px;
        }}
        #legend .stats {{
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid rgba(0,0,0,0.1);
            font-size: 12px;
            color: #475569;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="legend">
        <h3>TerraSAT / AgroSAT</h3>
        <div class="subtitle">Alerta Temprana Agroclimática — {today_str}</div>
        {''.join(legend_items)}
        <div class="stats">
            <b>{len(zones)}</b> zonas · <b>{len(countries)}</b> países<br>
            <b>{total_ha:,}</b> ha monitoreadas<br>
            <b>{affected_ha:,}</b> ha en alerta
        </div>
    </div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var map = L.map('map', {{
            zoomControl: true,
            attributionControl: false
        }}).setView([-10, -62], 4);

        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            maxZoom: 18
        }}).addTo(map);

        // Color por país según peor estado de sus zonas
        var countryColors = {{ {country_status_js} }};

        fetch('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson')
            .then(r => r.json())
            .then(data => {{
                L.geoJSON(data, {{
                    filter: function(f) {{
                        return countryColors.hasOwnProperty(f.properties.NAME);
                    }},
                    style: function(f) {{
                        var color = countryColors[f.properties.NAME];
                        return {{
                            color: color,
                            weight: 1.5,
                            opacity: 0.5,
                            fillOpacity: 0.05,
                            fillColor: color
                        }};
                    }}
                }}).addTo(map);
            }});

        // Rectángulos por zona (footprint de observación)
{chr(10).join(zones_js)}
    </script>
</body>
</html>"""


def load_zones_from_json(path: Path):
    """Carga zonas desde scripts/agro-zones.json (generado por el boletín)."""
    import json
    from types import SimpleNamespace

    payload = json.loads(path.read_text(encoding="utf-8"))
    zones = [SimpleNamespace(**z) for z in payload["zones"]]
    return zones, payload


def main():
    import argparse
    from datetime import date

    parser = argparse.ArgumentParser(description="AgroSAT — mapa HTML del boletín")
    parser.add_argument("--simulate", action="store_true",
                        help="Ignorar agro-zones.json y simular datos")
    args = parser.parse_args()

    json_path = Path("scripts/agro-zones.json")

    if not args.simulate and json_path.exists():
        zones, payload = load_zones_from_json(json_path)
        gen_at = payload.get("generated_at", "")
        try:
            today_str = date.fromisoformat(gen_at).strftime("%d/%m/%Y")
        except ValueError:
            today_str = date.today().strftime("%d/%m/%Y")
        source = payload.get("source", "?")
        print(f"Zonas cargadas desde {json_path} (fuente: {source}, generado: {gen_at})")
    else:
        if not json_path.exists():
            print(f"No existe {json_path}; usando simulación. "
                  f"Correr demo_alerta_temprana_regional.py primero para datos reales.")
        today_str = date.today().strftime("%d/%m/%Y")
        zones = generate_zones()
        simulate_zones(zones, seed=2026)

    html = generate_map_html(zones, today_str)

    output_dir = Path("scripts")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "agrosat-map.html"
    output_path.write_text(html, encoding="utf-8")

    print(f"Mapa generado: {output_path}")
    print(f"  Abrir en navegador, capturar pantalla, y pegar en FB.")
    print(f"  Después agregar branding con: node scripts/add-branding-terrasat.mjs \"captura.png\" --period \"05-11 ago 2026\"")


if __name__ == "__main__":
    main()
