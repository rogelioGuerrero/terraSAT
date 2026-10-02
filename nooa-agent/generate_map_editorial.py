"""
TerraSAT / AgroSAT — Mapa editorial (estático, estilo JRC)

Variante de generate_map.py pensada para captura de pantalla e inserción
como figura en artículos: basemap gris claro (Esri, sin API key), capa de
referencia con topónimos, sin controles de zoom, encabezado con título +
período, leyenda compacta.

Salida: scripts/agrosat-map-editorial.html → screenshot con Playwright MCP.

Ejecutar: .venv/Scripts/python nooa-agent/generate_map_editorial.py
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

STATUS_COLOR = {
    "critico": "#b91c1c",
    "alerta": "#d95f0e",
    "vigilancia": "#eab308",
    "normal": "#15803d",
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

MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]


def _fmt_range(iso_a: str, iso_b: str) -> str:
    a = datetime.fromisoformat(iso_a.replace("Z", "+00:00"))
    b = datetime.fromisoformat(iso_b.replace("Z", "+00:00"))
    if a.month == b.month:
        return f"{a.day}–{b.day} {MESES[a.month - 1]} {a.year}"
    return f"{a.day} {MESES[a.month - 1]}–{b.day} {MESES[b.month - 1]} {b.year}"


# Desplazamientos de etiqueta (px) para zonas cuyo nombre choca con
# topónimos del basemap o con etiquetas vecinas.
LABEL_OFFSET = {
    "Alta Verapaz": (34, -14),
    "El Paraíso": (10, 20),
    "Jinotega": (0, 22),
    "Caldas": (-18, -20),
    "Quindío": (-6, 24),
    "Mendoza": (26, 0),
    "Espírito Santo": (40, 4),
    "Valle Central": (-14, 22),
}


def _circle_js(z, interactive: bool = False) -> str:
    """Círculo proporcional al área (amplificado para legibilidad continental)."""
    color = STATUS_COLOR.get(z.status, "#666")
    radius_m = math.sqrt(z.area_ha * 10_000 / math.pi)
    # A zoom continental el radio real queda invisible; se amplifica con mínimo.
    radius_m = max(radius_m * 3.0, 36_000)
    if z.status == "sin_datos":
        fill_opacity, weight, dash = 0.15, 1.5, 'dashArray: "4",'
    elif z.status == "normal":
        fill_opacity, weight, dash = 0.32, 1.6, ""
    else:
        fill_opacity, weight, dash = 0.50, 2.2, ""

    crop = getattr(z, "crop", None)
    popup = f"<b>{z.name}, {z.country}</b><br>"
    if crop:
        popup += f"Cultivo: {crop} · "
    popup += (
        f"Estado: {STATUS_LABEL.get(z.status, z.status)}<br>"
        f"Área monitoreada: {z.area_ha:,} ha"
    )
    if z.affected_area_ha > 0:
        popup += f"<br>Área afectada: {z.affected_area_ha:,} ha"
    popup = popup.replace('"', '\\"')

    out = (
        f'    L.circle([{z.lat}, {z.lng}], {{'
        f'radius: {radius_m:.0f}, fillColor: "{color}", color: "{color}", '
        f'{dash} weight: {weight}, fillOpacity: {fill_opacity}, opacity: 0.85'
        f'}}).addTo(map).bindPopup("{popup}")'
        f'.bindTooltip("{z.name}", {{direction: "top", offset: [0, -8]}});'
    )
    # Etiquetas permanentes solo en la figura estática, donde no hay hover,
    # y solo en zonas con señal — evita saturar el cluster centroamericano.
    if not interactive and z.status not in ("normal", "sin_datos"):
        dx, dy = LABEL_OFFSET.get(z.name, (0, 0))
        out += (
            f'\n    L.marker([{z.lat}, {z.lng}], {{interactive: false, icon: L.divIcon({{'
            f'className: "zone-label", html: "{z.name}", iconSize: [0, 0], '
            f'iconAnchor: [{-dx}, {-dy}]'
            f'}})}}).addTo(map);'
        )
    return out


def generate_html(zones, period_str: str, title: str, subtitle: str,
                  interactive: bool = False) -> str:
    zones_js = "\n".join(_circle_js(z, interactive) for z in zones)

    legend_items = []
    for status, color in STATUS_COLOR.items():
        count = sum(1 for z in zones if z.status == status)
        if count:
            legend_items.append(
                f'<div class="lg-item"><span class="lg-swatch" style="background:{color}"></span>'
                f'{STATUS_LABEL[status]} <span class="lg-n">({count})</span></div>'
            )

    total_ha = sum(z.area_ha for z in zones)
    affected_ha = sum(z.affected_area_ha for z in zones)
    lats = [z.lat for z in zones]
    lngs = [z.lng for z in zones]
    pad = 1.5 if interactive else 4
    bounds = (
        f"[[{min(lats) - pad}, {min(lngs) - pad * 1.75}], "
        f"[{max(lats) + pad}, {max(lngs) + pad * 1.75}]]"
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{title} — {period_str}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #fff; }}
  #map {{ width: 100%; height: 100vh; }}
  .zone-label {{
    font-size: 12px; font-weight: 700; color: #0f172a;
    text-shadow: 0 0 4px #fff, 0 0 4px #fff, 0 0 5px #fff;
    white-space: nowrap; transform: translate(-50%, -50%); text-align: center;
  }}
  .leaflet-popup-content {{ font-size: 13px; line-height: 1.5; }}
  #titlebox {{
    position: absolute; top: 14px; left: 14px; z-index: 1000;
    background: rgba(255,255,255,0.95); padding: 10px 14px;
    border: 1px solid #e2e8f0; border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08); max-width: 460px;
  }}
  #titlebox h1 {{ font-size: 15px; font-weight: 700; color: #0f172a; }}
  #titlebox p {{ font-size: 11.5px; color: #64748b; margin-top: 2px; }}
  #legend {{
    position: absolute; bottom: 18px; right: 14px; z-index: 1000;
    background: rgba(255,255,255,0.95); padding: 10px 14px;
    border: 1px solid #e2e8f0; border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08); font-size: 12px; color: #334155;
  }}
  #legend .lg-title {{ font-size: 11px; font-weight: 700; color: #64748b;
    text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }}
  .lg-item {{ display: flex; align-items: center; gap: 7px; margin: 3px 0; }}
  .lg-swatch {{ width: 14px; height: 10px; border-radius: 2px; opacity: 0.8;
    border: 1px solid rgba(0,0,0,0.15); }}
  .lg-n {{ color: #94a3b8; }}
  #legend .lg-stats {{ margin-top: 7px; padding-top: 7px;
    border-top: 1px solid #e2e8f0; font-size: 11px; color: #64748b; }}
  #attrib {{
    position: absolute; bottom: 4px; left: 8px; z-index: 1000;
    font-size: 10px; color: #94a3b8;
  }}
</style>
</head>
<body>
<div id="map"></div>
{"" if interactive else f'''<div id="titlebox">
  <h1>{title}</h1>
  <p>{subtitle} · {period_str}</p>
</div>'''}
<div id="legend">
  <div class="lg-title">Estado del cultivo</div>
  {''.join(legend_items)}
  <div class="lg-stats">{len(zones)} zonas · {total_ha:,} ha · {affected_ha:,} ha afectadas</div>
</div>
<div id="attrib">Esri, OpenStreetMap contributors · Datos: Copernicus Sentinel-2, ERA5</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  var interactive = {"true" if interactive else "false"};
  var map = L.map('map', {{
    zoomControl: interactive, attributionControl: false,
    scrollWheelZoom: interactive, dragging: interactive,
    doubleClickZoom: interactive, boxZoom: interactive,
    keyboard: interactive, touchZoom: interactive,
    minZoom: interactive ? 2 : 0
  }});

  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
    maxZoom: 16
  }}).addTo(map);

  // Capa de referencia: topónimos y límites por encima de las zonas
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
    maxZoom: 16, opacity: 0.85
  }}).addTo(map);

{zones_js}

  if (interactive) {{
    // Deja libre la esquina inferior derecha (leyenda) al encuadrar.
    map.fitBounds({bounds}, {{padding: [16, 16], paddingBottomRight: [30, 130]}});
  }} else {{
    map.fitBounds({bounds}, {{padding: [0, 0]}});
  }}
</script>
</body>
</html>"""


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AgroSAT — mapa editorial (captura)")
    parser.add_argument("--zones", default="scripts/agro-zones.json")
    parser.add_argument("--out", default="scripts/agrosat-map-editorial.html")
    parser.add_argument("--title", default="Estrés vegetativo en cultivos de Latinoamérica")
    parser.add_argument("--subtitle", default="Cambio en vigor de la vegetación y área degradada por zona")
    parser.add_argument("--interactive", action="store_true",
                        help="Habilitar zoom/drag/popups — para iframe embebido")
    args = parser.parse_args()

    payload = json.loads(Path(args.zones).read_text(encoding="utf-8"))
    zones = [SimpleNamespace(**z) for z in payload["zones"]]

    win = payload.get("window", {}).get("current", [])
    if len(win) == 2:
        base_year = win[1][:4]
        period_str = f"{_fmt_range(win[0], win[1])} vs mismo período {int(base_year) - 1}"
    else:
        period_str = date.today().strftime("%d/%m/%Y")

    html = generate_html(zones, period_str, args.title, args.subtitle,
                         interactive=args.interactive)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"Mapa editorial: {args.out}")


if __name__ == "__main__":
    main()
