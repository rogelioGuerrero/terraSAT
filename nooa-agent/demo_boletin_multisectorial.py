"""
TerraSAT — Boletín Multisectorial de Alerta Temprana

Rotación editorial semanal con 5 productos:
  Semana 1: AgroSAT      — sequía, estrés de cultivos, alerta agroclimática
  Semana 2: SismoSAT     — deformación InSAR post-terremoto, riesgo estructural
  Semana 3: UrbanSAT     — expansión urbana, islas de calor, pérdida de verde
  Semana 4: ForestSAT    — incendios forestales, deforestación, degradación
  Semana 5: HidroSAT     — inundaciones, déficit hídrico, cuerpos de agua

Cada producto usa las funciones detect_*() existentes en change_detection.py
y genera: artículo + prompt de imagen + output en scripts/.

Uso:
  python nooa-agent/demo_boletin_multisectorial.py              # rota automáticamente
  python nooa-agent/demo_boletin_multisectorial.py --product agro    # producto específico
  python nooa-agent/demo_boletin_multisectorial.py --product sismo
  python nooa-agent/demo_boletin_multisectorial.py --product urban
  python nooa-agent/demo_boletin_multisectorial.py --product forest
  python nooa-agent/demo_boletin_multisectorial.py --product hidro
"""

from __future__ import annotations

import logging
import random
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.WARNING)

from change_detection import ChangeDetector
from deformation_map import DeformationMap


# ═════════════════════════════════════════════════════════════════════
# Configuración de productos
# ═════════════════════════════════════════════════════════════════════

PRODUCTS = ["agro", "sismo", "urban", "forest", "hidro"]

PRODUCT_INFO = {
    "agro": {
        "name": "AgroSAT",
        "tagline": "Alerta temprana para la agricultura",
        "hashtags": "#AgroSAT #AgriculturaSostenible #AlertaAgrícola",
        "icon": "🌱",
        "cta": "¿Su plantación, propiedad o empresa agroindustrial opera en alguna de estas zonas? AgroSAT detecta situaciones atípicas que pueden afectar sus cultivos 15 días antes de que aparezcan síntomas visibles. Reportes personalizados disponibles. También trabajamos con aseguradoras y agroservicios. Contacto: info@agtisa.com 📡",
    },
    "sismo": {
        "name": "SismoSAT",
        "tagline": "Análisis de deformación terrestre post-evento",
        "hashtags": "#SismoSAT #MonitoreoSatelital #ReducciónDeRiesgos",
        "icon": "📡",
        "cta": "¿Su municipio, empresa o infraestructura está en zona sísmica? SismoSAT mide deformación del terreno con precisión milimétrica usando radar satelital, incluso en zonas de difícil acceso. Evaluación post-evento en horas, no días. Trabajamos con gestión de riesgos, aseguradoras y entidades de emergencia. Contacto: info@agtisa.com 📡",
    },
    "urban": {
        "name": "UrbanSAT",
        "tagline": "Monitoreo del cambio urbano y territorial",
        "hashtags": "#UrbanSAT #CiudadesInteligentes #MonitoreoUrbano",
        "icon": "🏙️",
        "cta": "¿Su municipio necesita monitoreo satelital del territorio? UrbanSAT detecta cambios urbanos antes del recorrido en terreno. Reportes personalizados por sector: expansión, islas de calor, pérdida de áreas verdes. Vea mapa interactivo en terraSAT.agtisa.com. Contacto: info@agtisa.com 🛰️",
    },
    "forest": {
        "name": "ForestSAT",
        "tagline": "Monitoreo de cobertura forestal y áreas quemadas",
        "hashtags": "#ForestSAT #Bosques #Conservación",
        "icon": "🌲",
        "cta": "¿Su organización trabaja en conservación, silvicultura o carbono? ForestSAT detecta pérdida de cobertura, áreas quemadas y degradación forestal con validación multi-sensor. Reportes para REDD+, certificación y cumplimiento normativo. Contacto: info@agtisa.com 🛰️",
    },
    "hidro": {
        "name": "HidroSAT",
        "tagline": "Monitoreo de cuerpos de agua e inundaciones",
        "hashtags": "#HidroSAT #GestiónDelAgua #AlertaTemprana",
        "icon": "💧",
        "cta": "¿Su territorio enfrenta riesgo de inundaciones o estrés hídrico? HidroSAT mapea cuerpos de agua, detecta inundaciones a través de nubes con radar satelital y monitorea déficit hídrico. Trabajamos con defensas civiles, empresas hidroeléctricas y autoridades de cuencas. Contacto: info@agtisa.com 📡",
    },
}


# ═════════════════════════════════════════════════════════════════════
# Zonas por producto (datos reales de Latinoamérica)
# ═════════════════════════════════════════════════════════════════════

AGRO_ZONES = [
    {"name": "Intibucá", "country": "Honduras", "crop": "Café", "lat": 14.35, "lng": -88.20, "area_ha": 45_000},
    {"name": "El Paraíso", "country": "Honduras", "crop": "Café", "lat": 14.15, "lng": -86.55, "area_ha": 38_000},
    {"name": "Jinotega", "country": "Nicaragua", "crop": "Café", "lat": 13.10, "lng": -86.00, "area_ha": 42_000},
    {"name": "Caldas", "country": "Colombia", "crop": "Café", "lat": 5.07, "lng": -75.50, "area_ha": 65_000},
    {"name": "Mato Grosso", "country": "Brasil", "crop": "Soja", "lat": -12.50, "lng": -55.70, "area_ha": 320_000},
    {"name": "Espírito Santo", "country": "Brasil", "crop": "Café", "lat": -19.19, "lng": -40.34, "area_ha": 85_000},
    {"name": "Córdoba", "country": "Argentina", "crop": "Soja", "lat": -31.42, "lng": -64.18, "area_ha": 180_000},
    {"name": "Valle Central", "country": "Chile", "crop": "Viñas", "lat": -35.00, "lng": -71.00, "area_ha": 55_000},
    {"name": "Mendoza", "country": "Argentina", "crop": "Viñas", "lat": -32.89, "lng": -68.83, "area_ha": 95_000},
    {"name": "São Paulo", "country": "Brasil", "crop": "Caña", "lat": -22.00, "lng": -48.00, "area_ha": 210_000},
]

AGRO_DROUGHT_STATUS = {
    "Intibucá": "severa",
    "El Paraíso": "moderada",
    "Jinotega": "leve",
    "Caldas": "moderada",
    "Mato Grosso": "severa",
    "Espírito Santo": "moderada",
    "Córdoba": "normal",
    "Valle Central": "leve",
    "Mendoza": "normal",
    "São Paulo": "normal",
}

AGRO_STRESS_STATUS = {
    "Intibucá": "severo",
    "El Paraíso": "moderado",
    "Jinotega": "leve",
    "Caldas": "moderado",
    "Mato Grosso": "severo",
    "Espírito Santo": "moderado",
    "Córdoba": "sano",
    "Valle Central": "leve",
    "Mendoza": "sano",
    "São Paulo": "sano",
}


# ─── SismoSAT: Terremoto Colombia 10-ago-2026 M7.4 (San José del Palmar, Chocó) ───
# Datos reales: USGS/SGC — epicentro Chocó, profundidad 103km, subducción placa Nazca
# 181+ muertos, 2,500+ heridos, afectó Pereira, Cali, Manizales, Quibdó, Armenia
# También: Venezuela 24-jun-2026 — sismos gemelos M7.2+M7.5, superficiales <15km, 6,300+ muertos

SISMO_ZONES = [
    {"name": "San José del Palmar (epicentro)", "lat": 4.80, "lng": -76.50},
    {"name": "Pereira", "lat": 4.81, "lng": -75.70},
    {"name": "Cali", "lat": 3.45, "lng": -76.53},
    {"name": "Manizales", "lat": 5.07, "lng": -75.52},
    {"name": "Quibdó", "lat": 5.69, "lng": -76.66},
    {"name": "Armenia", "lat": 4.54, "lng": -75.71},
    {"name": "Bogotá", "lat": 4.71, "lng": -74.07},
]

SISMO_PARAMS = {
    "epicenter": (4.80, -76.50),
    "magnitude": 7.4,
    "depth_km": 103.0,
    "fault_type": "thrust",
    "seed": 2026,
}

# Venezuela — 24 junio 2026, sismos gemelos M7.2 + M7.5
SISMO_VENEZUELA_ZONES = [
    {"name": "La Guaira (epicentro)", "lat": 10.60, "lng": -66.93},
    {"name": "Caracas", "lat": 10.49, "lng": -66.88},
    {"name": "Maracay", "lat": 10.25, "lng": -67.59},
    {"name": "Valencia", "lat": 10.16, "lng": -67.99},
]

SISMO_VENEZUELA_PARAMS = {
    "epicenter": (10.60, -66.93),
    "magnitude": 7.5,
    "depth_km": 14.0,
    "fault_type": "strike_slip",
    "seed": 2026,
}


# ─── UrbanSAT: ciudades de Latinoamérica ───

URBAN_ZONES = [
    {"name": "Centro Salto", "lat": -31.38, "lng": -57.97},
    {"name": "Periurbano este Salto", "lat": -31.35, "lng": -57.85},
    {"name": "Periurbano norte Rivera", "lat": -30.90, "lng": -55.55},
    {"name": "Periurbano norte Asunción", "lat": -25.15, "lng": -57.55},
    {"name": "Zona franca Colonia", "lat": -34.45, "lng": -57.84},
    {"name": "Bañado sur Asunción", "lat": -25.35, "lng": -57.60},
    {"name": "Residencial sur Florida", "lat": -34.10, "lng": -56.22},
    {"name": "Centro histórico Cuenca", "lat": -2.90, "lng": -79.00},
]

URBAN_CONSTRUCTION_STATUS = {
    "Centro Salto": "construido",
    "Periurbano este Salto": "construido",
    "Periurbano norte Rivera": "construido",
    "Periurbano norte Asunción": "construido",
    "Zona franca Colonia": "construido",
    "Bañado sur Asunción": "en_construccion",
    "Residencial sur Florida": "en_construccion",
    "Centro histórico Cuenca": "sin_cambio",
}


# ─── ForestSAT: incendios + deforestación ───

FOREST_FIRE_ZONES = [
    {"name": "Maule Centro", "lat": -35.5, "lng": -71.5},
    {"name": "Maule Costa", "lat": -35.3, "lng": -72.2},
    {"name": "Biobío Interior", "lat": -37.2, "lng": -71.8},
    {"name": "Biobío Costa", "lat": -37.0, "lng": -73.0},
    {"name": "Araucanía", "lat": -38.5, "lng": -72.5},
    {"name": "Concepción", "lat": -36.8, "lng": -73.0},
]

FOREST_BURN_STATUS = {
    "Maule Centro": "alta",
    "Maule Costa": "alta",
    "Biobío Interior": "alta",
    "Biobío Costa": "moderada",
    "Araucanía": "moderada",
    "Concepción": "no_quemada",
}

FOREST_DEFORESTATION_ZONES = [
    {"name": "Alto Paraguay", "lat": -19.5, "lng": -58.5},
    {"name": "Boquerón", "lat": -21.5, "lng": -61.5},
    {"name": "Presidente Hayes", "lat": -23.0, "lng": -59.5},
    {"name": "Chaco Central", "lat": -22.0, "lng": -60.0},
    {"name": "Defensores del Chaco", "lat": -20.5, "lng": -59.5},
    {"name": "Medanos del Chaco", "lat": -21.0, "lng": -62.0},
]

FOREST_CLEARING_STATUS = {
    "Alto Paraguay": "deforestado",
    "Boquerón": "deforestado",
    "Presidente Hayes": "deforestado",
    "Chaco Central": "degradado",
    "Defensores del Chaco": "intacto",
    "Medanos del Chaco": "intacto",
}


# ─── HidroSAT: inundaciones + cuerpos de agua ───

HIDRO_ZONES = [
    {"name": "Porto Alegre centro", "lat": -30.03, "lng": -51.23},
    {"name": "Vale do Taquari", "lat": -29.2, "lng": -51.8},
    {"name": "Lajeado", "lat": -29.5, "lng": -51.9},
    {"name": "Canoas", "lat": -29.9, "lng": -51.2},
    {"name": "Serra Gaúcha", "lat": -28.7, "lng": -51.5},
    {"name": "Litoral norte", "lat": -29.3, "lng": -50.0},
]

HIDRO_FLOOD_STATUS = {
    "Porto Alegre centro": "inundado",
    "Vale do Taquari": "inundado",
    "Lajeado": "inundado",
    "Canoas": "parcial",
    "Serra Gaúcha": "no_inundado",
    "Litoral norte": "parcial",
}


# ═════════════════════════════════════════════════════════════════════
# Prompts de imagen por producto
# ═════════════════════════════════════════════════════════════════════

IMAGE_PROMPTS = {
    "agro": """You are a cinematic photographer creating a hero image for an agricultural early warning social media post about Latin American farming.

SUBJECT: Vast agricultural landscape in Latin America showing a mosaic of healthy and stressed crops. Aerial or elevated view showing large fields with visible patches of yellowing or thinning vegetation contrasted with healthy green sections. Could be coffee highlands, soybean plains, or vineyard valleys — diverse Latin American agriculture. Photorealistic, NOT illustration or cartoon.

CAMERA: Elevated angle, drone-style perspective showing the scale of the agricultural landscape. 16:9 widescreen composition. Shallow depth of field with the landscape in focus and distant features softly blurred.

LIGHTING: Early morning golden light, mist rising from valleys. Warm amber tones in highlights, cool blue-greens in shadows. Natural, cinematic color grading. Sense of dawn — the idea of early warning, catching problems before they're obvious.

ENVIRONMENT: Diverse Latin American agricultural landscape. Rolling hills with coffee, flat plains with row crops, or valley vineyards. Dense green vegetation with visible patches of lighter yellow-green where stress is beginning. Farm buildings, roads, or paths visible. Mountains or horizons in the background.

STYLE: Cinematic documentary photography, premium commercial quality, photorealistic. Like a still from a high-end agricultural documentary. NO text, NO watermark, NO logo, NO words in the image — clean visual only.""",

    "sismo": """You are a cinematic 3D visualization artist creating a hero image for a seismic terrain analysis social media post.

SUBJECT: A dramatic cross-section of the Earth's crust after an earthquake, shown like a layered cake or hamburger cut in half — revealing distinct geological layers. The top layer shows lush green vegetation with patches of brown where vegetation was lost. Below it, a cracked soil layer. Then a displaced rock stratum showing clear horizontal shift between left and right sides. Deeper layers show angled fault planes with visible displacement. The cross-section face is illuminated to reveal texture, color, and deformation in each layer. On the surface above, a small Latin American mountain town with subtle structural cracks visible. Photorealistic 3D render, NOT flat illustration.

CAMERA: Slight angle showing both the surface landscape (top) and the underground cross-section (front face) simultaneously. The terrain is visually "sliced open" like a geological textbook diagram but rendered photorealistically. 16:9 widescreen.

LIGHTING: Warm dramatic light from the left illuminating the cross-section face, making each geological layer glow with its distinct color — greens for vegetation, browns for soil, grays and ochres for rock, dark lines for fault planes. Cool ambient light on the surface town. Cinematic depth.

ENVIRONMENT: Andean mountain landscape, tropical vegetation on surface. The cross-section reveals ~500 meters of depth: topsoil with roots, weathered rock, sedimentary layers tilted by tectonic force, a clear fault line where layers don't align left-to-right. Water table visible as a thin blue line between layers. The deformation is visible as layers that shift horizontally — left side higher than right side, showing the tectonic displacement.

STYLE: Photorealistic 3D geological visualization, premium quality. Like a high-end National Geographic cross-section render. Scientifically plausible but visually stunning. The layered composition should immediately communicate "we can see inside the Earth and measure how it moved." NO text, NO watermark, NO logo, NO words in the image — clean visual only.""",

    "urban": """You are a cinematic photographer creating a hero image for an urban monitoring social media post about Latin American city growth.

SUBJECT: Aerial view of a Latin American city showing the boundary between urban sprawl and natural landscape. Visible expansion of new construction into previously green or agricultural areas. Heat island effect suggested by color variation between dense urban core and vegetated periphery. Photorealistic, NOT illustration or cartoon.

CAMERA: High altitude drone perspective, near-vertical view showing the urban grid pattern and its edges. 16:9 widescreen composition. Sharp focus across the entire frame for maximum detail.

LIGHTING: Midday sun with slight haze, emphasizing the texture and color differences between surfaces — concrete, rooftops, vegetation, bare soil. Subtle heat shimmer over dense urban areas.

ENVIRONMENT: Mid-size Latin American city (200K-500K population). Grid pattern streets, mixed residential and commercial zones, industrial areas near the edge. Rivers or coastlines visible. Clear contrast between planned and informal development.

STYLE: Cinematic documentary photography, premium commercial quality, photorealistic. Like a still from a high-end urban planning documentary. NO text, NO watermark, NO logo, NO words in the image — clean visual only.""",

    "forest": """You are a cinematic photographer creating a hero image for a forest monitoring social media post about Latin American deforestation and wildfires.

SUBJECT: Vast Amazon or Chaco forest landscape showing the dramatic boundary between intact primary forest and recently cleared or burned areas. Aerial view revealing the patchwork of healthy dark green canopy, degraded lighter green zones, and bare orange-brown earth where clearing has occurred. Smoke haze visible in the distance from active fires. Photorealistic, NOT illustration or cartoon.

CAMERA: Elevated angle, drone-style perspective at moderate altitude showing both the scale of the forest and the detail of the destruction boundary. 16:9 widescreen composition. Deep depth of field.

LIGHTING: Late afternoon golden hour with atmospheric haze from distant smoke. Warm amber light catching the edges of the forest canopy, reddish tones in the cleared areas, deep green shadows in the intact forest. Dramatic, emotional lighting.

ENVIRONMENT: Tropical or subtropical Latin American forest. Dense canopy with emergent trees, logging roads cutting through, rectangular clearings for agriculture or cattle. Rivers winding through the forest. Mountains on the distant horizon.

STYLE: Cinematic documentary photography, premium commercial quality, photorealistic. Like a still from a high-end environmental documentary. NO text, NO watermark, NO logo, NO words in the image — clean visual only.""",

    "hidro": """You are a cinematic photographer creating a hero image for a water monitoring and flood alert social media post about Latin American rivers and cities.

SUBJECT: A Latin American river city partially submerged by floodwaters. Aerial view showing the normal river channel contrasted with the expanded floodplain. Streets and neighborhoods under murky water, emergency vehicles on higher ground, bridges barely above water level. Photorealistic, NOT illustration or cartoon.

CAMERA: Elevated angle, drone-style perspective showing the extent of the flooding and the relationship between the river and the city. 16:9 widescreen composition. Deep depth of field to show the full scope of the event.

LIGHTING: Overcast grey sky with soft diffused light, suggesting ongoing weather emergency. Muted blue-grey tones in the water, warm earth tones in the non-flooded areas. Somber, documentary atmosphere.

ENVIRONMENT: Mid-size South American city (Rio Grande do Sul style) on a river floodplain. Low-lying neighborhoods submerged, higher areas dry. Parklands and sports fields under water. Industrial areas with warehouses partially flooded. Roads becoming inaccessible.

STYLE: Cinematic documentary photography, premium commercial quality, photorealistic. Like a still from a high-end disaster response documentary. NO text, NO watermark, NO logo, NO words in the image — clean visual only.""",
}


# ═════════════════════════════════════════════════════════════════════
# Prompts de artículo por producto
# ═════════════════════════════════════════════════════════════════════

ARTICLE_PROMPTS = {
    "agro": """Eres el editor jefe de AgroSAT, un boletín de alerta temprana agrícola en Latinoamérica.
AgroSAT es un producto de TerraSAT, empresa de procesamiento de imágenes satelitales.
Usas imágenes satelitales de agencias reconocidas (NASA, ESA) para detectar estrés en cultivos antes de que sea visible a simple vista.

Escribes para agricultores, agrónomos, cooperativas y aseguradoras agrícolas. Tono profesional pero con narrativa de intriga: empiezas con el hallazgo más impactante del análisis, creas tensión sobre qué encontraron las imágenes, y revelas los resultados como evidencia científica.

DATOS DE ALERTA AGROCLIMÁTICA:

{zones_data}

REGLAS CRÍTICAS:
- NO menciones nombres de satélites específicos (Sentinel-2, Landsat)
- NO menciones índices técnicos (NDVI, NDRE)
- SI puedes decir: "imágenes satelitales de agencias reconocidas (NASA, ESA)"
- SI puedes decir: "comparamos imágenes antes y después"
- SI puedes decir: "nuestro análisis espectral detectó estrés en los cultivos"
- RESALTA los valores del análisis espectral real como hallazgos
- SIEMPRE incluye fechas y regiones específicas

ESTRUCTURA (con narrativa de intriga):
1. Título impactante (máximo 12 palabras) que genere curiosidad
2. Lead con gancho: empieza con el hallazgo más impactante
3. Revela el análisis: "Comparamos imágenes satelitales y esto es lo que encontramos:" — luego datos por zona
4. Zonas con estrés leve: mención breve agrupada
5. Una línea sobre implicación para cosecha
6. CTA: {cta}
7. Hashtags: {hashtags}

FORMATO: Sin markdown, 250-400 palabras, 2-3 emojis (🛰️ 🌱 ☕ ⚠️ 📡)
Devuelve SOLO el texto del boletín.""",

    "sismo": """Eres el editor jefe de SismoSAT, un boletín de análisis de deformación terrestre post-evento sísmico en Latinoamérica.
SismoSAT es un producto de TerraSAT, empresa de procesamiento de imágenes satelitales.
Usas imágenes de radar satelital de agencias reconocidas (NASA, ESA) para medir deformación del terreno con precisión milimétrica.
También analizas imágenes ópticas para detectar cambios en la cobertura del terreno.

Escribes para gestores de riesgo, ingenieros estructurales, aseguradoras y autoridades de emergencia. Tono profesional pero con narrativa de suspenso: empieza con el dato que más impacta, crea tensión sobre qué encontraron las imágenes, y revela los resultados del análisis como evidencia científica.

DATOS DEL EVENTO SÍSMICO:

{zones_data}

REGLAS CRÍTICAS:
- NO menciones nombres de satélites específicos (Sentinel-1, ALOS, Sentinel-2)
- NO menciones técnicas específicas (InSAR, interferometría, bandas L/C, NDVI, NBR)
- SI puedes decir: "imágenes satelitales de agencias reconocidas (NASA, ESA)"
- SI puedes decir: "medimos deformación del terreno con precisión milimétrica"
- SI puedes decir: "comparamos imágenes antes y después del evento"
- SI puedes decir: "nuestro análisis espectral detectó cambios en la cobertura del terreno"
- SIEMPRE incluye la fecha exacta del evento y la magnitud
- SIEMPRE menciona el país y la región específica
- RESALTA los valores del análisis espectral real como hallazgos (ej: "Lo que encontramos nos sorprendió: Quibdó perdió 22% de su cobertura vegetal")
- Usa el término "deformación del terreno" (no "desplazamiento de capas terrestres")

ESTRUCTURA (con narrativa de intriga):
1. Título impactante (máximo 12 palabras) que genere curiosidad, no solo noticia
2. Lead con gancho: empieza con el hallazgo más impactante del análisis, no con la noticia del sismo
3. Revela el análisis: "Comparamos imágenes satelitales antes y después del evento y esto es lo que encontramos:" — luego los datos por zona, empezando por la más impactante
4. Zonas con cambios moderados: mención breve agrupada
5. Una línea sobre implicación para infraestructura
6. CTA: {cta}
7. Hashtags: {hashtags}

FORMATO: Sin markdown, 250-400 palabras, 2-3 emojis (📡 🏗️ ⚠️ 🌍)
Devuelve SOLO el texto del boletín.""",

    "urban": """Eres el editor jefe de UrbanSAT, un boletín de monitoreo del cambio urbano en Latinoamérica.
UrbanSAT es un producto de TerraSAT, empresa de procesamiento de imágenes satelitales.
Usas imágenes satelitales de agencias reconocidas (NASA, ESA) para detectar expansión urbana, islas de calor y pérdida de áreas verdes.

Escribes para municipios, urbanistas y consultoras de planificación territorial. Tono profesional pero con narrativa de intriga: empiezas con el hallazgo más impactante, creas tensión sobre qué encontraron las imágenes, y revelas los resultados como evidencia.

DATOS DE CAMBIO URBANO:

{zones_data}

REGLAS CRÍTICAS:
- USA SOLO los datos del "ANÁLISIS ESPECTRAL REAL" — ignora los datos simulados
- NO menciones nombres de satélites específicos (Sentinel-2, Landsat)
- NO menciones índices técnicos (NDVI, NDBI)
- SI puedes decir: "imágenes satelitales de agencias reconocidas (NASA, ESA)"
- SI puedes decir: "comparamos imágenes de diferentes años"
- SI puedes decir: "nuestro análisis detectó expansión urbana" o "pérdida de áreas verdes"
- RESALTA los valores numéricos como hallazgos (porcentajes de cambio, comparaciones antes/después)
- Menciona el hallazgo más impactante primero (mayor cambio)
- Habla de DOS hallazgos: vegetación (recuperación o pérdida) Y construcción (expansión o estabilidad)
- SIEMPRE usa las fechas reales que aparecen en los datos (ej: "entre enero 2024 y junio 2026")
- NO inventes ciudades que no estén en los datos

ESTRUCTURA (con narrativa de intriga):
1. Título impactante (máximo 12 palabras) que genere curiosidad
2. Lead con gancho: "Lo que encontramos nos sorprendió:" — empieza con el hallazgo más impactante
3. Revela el análisis: "Comparamos imágenes satelitales de NASA y ESA antes y después, y esto es lo que encontramos:" — luego datos por ciudad
4. Menciona tanto vegetación como construcción para cada ciudad
5. Una línea sobre implicación para planificación urbana
6. CTA: {cta}
7. Hashtags: {hashtags}

FORMATO: Sin markdown, 250-400 palabras, 2-3 emojis (🛰️ 🏙️ 🌳 ⚠️ 📡)
Devuelve SOLO el texto del boletín.""",

    "forest": """Eres el editor jefe de ForestSAT, un boletín de monitoreo forestal en Latinoamérica.
ForestSAT es un producto de TerraSAT, empresa de procesamiento de imágenes satelitales.
Usas imágenes satelitales de agencias reconocidas (NASA, ESA) para detectar incendios forestales, deforestación y degradación de bosques.

Escribes para ministerios de ambiente, ONGs conservacionistas y certificadores. Tono profesional pero con narrativa de intriga: empiezas con el hallazgo más impactante, creas tensión sobre qué encontraron las imágenes, y revelas los resultados como evidencia.

DATOS FORESTALES:

{zones_data}

REGLAS CRÍTICAS:
- NO menciones nombres de satélites específicos (Sentinel-2, Landsat)
- NO menciones índices técnicos (NBR, NDVI, dNBR)
- SI puedes decir: "imágenes satelitales de agencias reconocidas (NASA, ESA)"
- SI puedes decir: "comparamos imágenes antes y después"
- SI puedes decir: "nuestro análisis detectó pérdida de cobertura forestal"
- RESALTA los valores del análisis espectral real como hallazgos
- SIEMPRE incluye fechas y regiones específicas

ESTRUCTURA (con narrativa de intriga):
1. Título impactante (máximo 12 palabras) que genere curiosidad
2. Lead con gancho: empieza con el hallazgo más impactante
3. Revela el análisis: "Comparamos imágenes satelitales y esto es lo que encontramos:" — luego datos por zona
4. Áreas intactas: una línea
5. Una línea sobre implicación para biodiversidad
6. CTA: {cta}
7. Hashtags: {hashtags}

FORMATO: Sin markdown, 250-400 palabras, 2-3 emojis (🛰️ 🌲 🔥 🌳 📡)
Devuelve SOLO el texto del boletín.""",

    "hidro": """Eres el editor jefe de HidroSAT, un boletín de monitoreo de cuerpos de agua e inundaciones en Latinoamérica.
HidroSAT es un producto de TerraSAT, empresa de procesamiento de imágenes satelitales.
Usas imágenes satelitales de agencias reconocidas (NASA, ESA), incluyendo radar que penetra nubosidad, para mapear inundaciones y monitorear déficit hídrico.

Escribes para defensas civiles, autoridades de cuencas, empresas hidroeléctricas y seguros. Tono profesional pero con narrativa de intriga: empiezas con el hallazgo más impactante, creas tensión sobre qué encontraron las imágenes, y revelas los resultados como evidencia.

DATOS HIDROLÓGICOS:

{zones_data}

REGLAS CRÍTICAS:
- NO menciones nombres de satélites específicos (Sentinel-1, Sentinel-2)
- NO menciones índices técnicos (NDWI, SAR backscatter)
- SI puedes decir: "imágenes satelitales de agencias reconocidas (NASA, ESA)"
- SI puedes decir: "radar satelital que penetra nubosidad"
- SI puedes decir: "comparamos imágenes antes y después"
- SI puedes decir: "nuestro análisis detectó cambios en los cuerpos de agua"
- RESALTA los valores del análisis espectral real como hallazgos
- SIEMPRE incluye fechas y regiones específicas

ESTRUCTURA (con narrativa de intriga):
1. Título impactante (máximo 12 palabras) que genere curiosidad
2. Lead con gancho: empieza con el hallazgo más impactante
3. Revela el análisis: "Comparamos imágenes satelitales y esto es lo que encontramos:" — luego datos por zona
4. Zonas sin afectación: una línea
5. Una línea sobre implicación para comunidades
6. CTA: {cta}
7. Hashtags: {hashtags}

FORMATO: Sin markdown, 250-400 palabras, 2-3 emojis (🛰️ 💧 ⚠️ 🌊 📡)
Devuelve SOLO el texto del boletín.""",
}


# ═════════════════════════════════════════════════════════════════════
# Carga de análisis espectral real de Sentinel-2
# ═════════════════════════════════════════════════════════════════════

def load_sentinel2_analysis(product: str) -> list | None:
    """Carga JSON de análisis espectral real si existe."""
    import json as _json
    import os as _os
    json_map = {
        "sismo": "sismo-analysis-real.json",
        "agro": "agro-analysis-real.json",
        "urban": "urban-analysis-real.json",
        "forest": "forest-analysis-real.json",
        "hidro": "hidro-analysis-real.json",
    }
    fname = json_map.get(product)
    if not fname:
        return None
    path = _os.path.join(_os.path.dirname(__file__), "..", "scripts", fname)
    if not _os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return _json.load(f)


def format_sentinel2_data(product: str, s2_data: list, indices: list) -> list:
    """Formatea datos reales de Sentinel-2 en líneas para zones_data."""
    lines = ["ANÁLISIS ESPECTRAL REAL — comparación de imágenes satelitales (USA SOLO ESTOS DATOS, ignora cualquier otro dato debajo):"]
    for r in s2_data:
        parts = [f"- {r['zone']}:"]
        for idx in indices:
            pre_val = r.get(f"{idx}_pre")
            post_val = r.get(f"{idx}_post")
            pre_date = r.get(f"{idx}_pre_date", "")
            post_date = r.get(f"{idx}_post_date", "")
            delta = r.get(f"delta_{idx}")
            if pre_val is not None and post_val is not None:
                pct_change = abs(delta) * 100
                parts.append(
                    f"{idx.upper()} {pre_val} ({pre_date}) → {post_val} ({post_date}), cambio de {pct_change:.1f}%"
                )
        # Interpretación del primer índice
        interp = r.get(f"interp_{indices[0]}", "")
        # También interpretación del segundo índice si existe
        if len(indices) > 1:
            interp2 = r.get(f"interp_{indices[1]}", "")
            parts.append(f"→ {interp}; {interp2}")
        else:
            parts.append(f"→ {interp}")
        lines.append(" ".join(parts))
    lines.append("FIN DEL ANÁLISIS ESPECTRAL REAL — NO uses datos de otras secciones.")
    return lines


# ═════════════════════════════════════════════════════════════════════
# Ejecución de detección por producto
# ═════════════════════════════════════════════════════════════════════

def run_agro() -> dict[str, Any]:
    """Ejecuta AgroSAT: sequía + estrés de cultivos."""
    detector = ChangeDetector()

    zones_for_detection = [{"name": z["name"], "lat": z["lat"], "lng": z["lng"]} for z in AGRO_ZONES]

    drought_result = detector.detect_drought(
        event_name="Alerta agroclimática Latinoamérica",
        zones=zones_for_detection,
        drought_status=AGRO_DROUGHT_STATUS,
        seed=2026,
    )

    stress_result = detector.detect_crop_stress(
        event_name="Estrés de cultivos Latinoamérica",
        zones=zones_for_detection,
        stress_status=AGRO_STRESS_STATUS,
        seed=2026,
    )

    # Cargar análisis espectral real de Sentinel-2 si existe
    s2_data = load_sentinel2_analysis("agro")
    zones_data = []
    if s2_data:
        zones_data.extend(format_sentinel2_data("agro", s2_data, ["ndvi", "ndre"]))
        zones_data.append("")
        zones_data.append("Modelo de estrés agrícola (simulación calibrada):")

    for z in AGRO_ZONES:
        name = z["name"]
        status = AGRO_DROUGHT_STATUS.get(name, "normal")
        stress = AGRO_STRESS_STATUS.get(name, "sano")
        affected_pct = 0
        if status == "severa":
            affected_pct = random.Random(hash(name) % 1000).uniform(35, 50)
        elif status == "moderada":
            affected_pct = random.Random(hash(name) % 1000).uniform(20, 35)
        elif status == "leve":
            affected_pct = random.Random(hash(name) % 1000).uniform(10, 20)

        affected_ha = int(z["area_ha"] * affected_pct / 100)

        zones_data.append(
            f"- {name}, {z['country']} ({z['crop']}): {z['area_ha']:,} ha | "
            f"Estado sequía: {status} | Estrés cultivo: {stress} | "
            f"Área afectada: {affected_ha:,} ha | "
            f"Anticipación: 15 días"
        )

    drought_summary = f"Análisis de Sequía — {drought_result.event_name}\nZonas: {len(drought_result.zones)} | Área: {drought_result.total_affected_area_km2:.1f} km² | Severidad: {drought_result.max_severity}"
    stress_summary = f"Análisis de Estrés — {stress_result.event_name}\nZonas: {len(stress_result.zones)} | Área: {stress_result.total_affected_area_km2:.1f} km² | Severidad: {stress_result.max_severity}"

    return {
        "zones_data": "\n".join(zones_data),
        "detection_results": {"drought": drought_result, "stress": stress_result},
        "summary": drought_summary + "\n" + stress_summary,
    }


def run_sismo() -> dict[str, Any]:
    """Ejecuta SismoSAT: deformación InSAR + análisis espectral real Sentinel-2 post-terremoto."""
    import json as _json
    import os as _os

    # Colombia — M7.4, 10 ago 2026, Chocó, 103km profundidad
    def_map_col = DeformationMap()
    def_map_col.generate(
        epicenter=SISMO_PARAMS["epicenter"],
        magnitude=SISMO_PARAMS["magnitude"],
        zone_centers=SISMO_ZONES,
        depth_km=SISMO_PARAMS["depth_km"],
        fault_type=SISMO_PARAMS["fault_type"],
        seed=SISMO_PARAMS["seed"],
    )

    # Venezuela — M7.5, 24 jun 2026, La Guaira, 14km profundidad (superficial)
    def_map_ven = DeformationMap()
    def_map_ven.generate(
        epicenter=SISMO_VENEZUELA_PARAMS["epicenter"],
        magnitude=SISMO_VENEZUELA_PARAMS["magnitude"],
        zone_centers=SISMO_VENEZUELA_ZONES,
        depth_km=SISMO_VENEZUELA_PARAMS["depth_km"],
        fault_type=SISMO_VENEZUELA_PARAMS["fault_type"],
        seed=SISMO_VENEZUELA_PARAMS["seed"],
    )

    # Cargar análisis espectral REAL de Sentinel-2 (si existe)
    s2_analysis = None
    s2_path = _os.path.join(_os.path.dirname(__file__), "..", "scripts", "sismo-analysis-real.json")
    if _os.path.exists(s2_path):
        with open(s2_path, "r", encoding="utf-8") as f:
            s2_analysis = _json.load(f)

    zones_data = [
        "EVENTO 1: Colombia — 10 agosto 2026, M7.4, San José del Palmar (Chocó), profundidad 103km",
        "181+ muertos, 2,500+ heridos, 200 desaparecidos. Subducción placa Nazca.",
        "",
        "ANÁLISIS ESPECTRAL REAL — Sentinel-2 (NDVI pre/post sismo):",
    ]

    # Añadir datos reales de Sentinel-2 si disponibles
    if s2_analysis:
        for r in s2_analysis:
            if "error" in r:
                zones_data.append(f"- {r['zone']}: Error en análisis")
            else:
                zones_data.append(
                    f"- {r['zone']}: NDVI {r['ndvi_pre']} ({r['ndvi_pre_date']}) → "
                    f"{r['ndvi_post']} ({r['ndvi_post_date']}) | "
                    f"ΔNDVI={r['delta_ndvi']:+.3f} | "
                    f"NBR {r['nbr_pre']} → {r['nbr_post']} | "
                    f"ΔNBR={r['delta_nbr']:+.3f}" if r.get("delta_nbr") is not None else
                    f"- {r['zone']}: NDVI {r['ndvi_pre']} → {r['ndvi_post']} | "
                    f"ΔNDVI={r['delta_ndvi']:+.3f} | {r['interpretation']}"
                )
        zones_data.append("")
        zones_data.append("Modelo de deformación InSAR (simulación calibrada por magnitud/profundidad):")
    else:
        zones_data.append("(Ejecutar analyze_sismo_real.py para análisis espectral real)")
        zones_data.append("")

    for z in def_map_col.prioritize_zones():
        zones_data.append(
            f"- {z.name}: deformación max {z.max_deformation_mm:.0f}mm, "
            f"promedio {z.avg_deformation_mm:.0f}mm | "
            f"Severidad: {z.severity} | "
            f"Riesgo estructural: {z.building_risk}/100 | "
            f"Área: {z.area_km2:.1f} km²"
        )

    zones_data.extend([
        "",
        "EVENTO 2: Venezuela — 24 junio 2026, sismos gemelos M7.2 + M7.5, La Guaira, profundidad <15km",
        "6,300+ muertos. Fallas Boconó y San Sebastián (strike-slip, placa Caribe).",
        "",
    ])
    for z in def_map_ven.prioritize_zones():
        zones_data.append(
            f"- {z.name}: deformación max {z.max_deformation_mm:.0f}mm, "
            f"promedio {z.avg_deformation_mm:.0f}mm | "
            f"Severidad: {z.severity} | "
            f"Riesgo estructural: {z.building_risk}/100 | "
            f"Área: {z.area_km2:.1f} km²"
        )

    summary = (
        f"COLOMBIA M7.4 (10-ago-2026):\n{def_map_col.summary()}\n\n"
        f"VENEZUELA M7.5 (24-jun-2026):\n{def_map_ven.summary()}"
    )

    return {
        "zones_data": "\n".join(zones_data),
        "detection_results": {"colombia": def_map_col, "venezuela": def_map_ven},
        "summary": summary,
    }


def run_urban() -> dict[str, Any]:
    """Ejecuta UrbanSAT: expansión urbana e islas de calor + análisis espectral real."""
    detector = ChangeDetector()

    zones_for_detection = [{"name": z["name"], "lat": z["lat"], "lng": z["lng"]} for z in URBAN_ZONES]

    construction_result = detector.detect_construction(
        event_name="Cambio urbano Latinoamérica",
        zones=zones_for_detection,
        construction_status=URBAN_CONSTRUCTION_STATUS,
        seed=2026,
    )

    # Cargar análisis espectral real de Sentinel-2
    s2_data = load_sentinel2_analysis("urban")
    zones_data = []
    if s2_data:
        zones_data.extend(format_sentinel2_data("urban", s2_data, ["ndvi", "ndbi"]))
        zones_data.append("")
        zones_data.append("Modelo de cambio urbano (simulación calibrada):")

    for z in URBAN_ZONES:
        name = z["name"]
        status = URBAN_CONSTRUCTION_STATUS.get(name, "sin_cambio")
        if status == "construido":
            change = "Construcción nueva confirmada"
            area = random.Random(hash(name) % 1000).uniform(0.5, 3.0)
        elif status == "en_construccion":
            change = "Construcción en progreso"
            area = random.Random(hash(name) % 1000).uniform(0.2, 1.0)
        else:
            change = "Sin cambios significativos"
            area = 0.0

        zones_data.append(
            f"- {name}: {change} | Área: {area:.1f} km²"
        )

    return {
        "zones_data": "\n".join(zones_data),
        "detection_results": {"construction": construction_result},
        "summary": detector.summary(),
    }


def run_forest() -> dict[str, Any]:
    """Ejecuta ForestSAT: incendios + deforestación + análisis espectral real."""
    detector = ChangeDetector()

    fire_zones = [{"name": z["name"], "lat": z["lat"], "lng": z["lng"]} for z in FOREST_FIRE_ZONES]
    deforest_zones = [{"name": z["name"], "lat": z["lat"], "lng": z["lng"]} for z in FOREST_DEFORESTATION_ZONES]

    fire_result = detector.detect_burned_area(
        event_name="Incendios forestales Chile",
        zones=fire_zones,
        burn_severity_map=FOREST_BURN_STATUS,
        seed=2026,
    )

    deforest_result = detector.detect_deforestation(
        event_name="Deforestación Chaco Paraguayo",
        zones=deforest_zones,
        clearing_status=FOREST_CLEARING_STATUS,
        seed=2026,
    )

    # Cargar análisis espectral real de Sentinel-2
    s2_data = load_sentinel2_analysis("forest")
    zones_data = []
    if s2_data:
        zones_data.extend(format_sentinel2_data("forest", s2_data, ["ndvi", "nbr"]))
        zones_data.append("")
        zones_data.append("Modelo de incendios y deforestación (simulación calibrada):")
    for z in FOREST_FIRE_ZONES:
        name = z["name"]
        severity = FOREST_BURN_STATUS.get(name, "no_quemada")
        if severity == "alta":
            area = random.Random(hash(name) % 1000).uniform(800, 1600)
        elif severity == "moderada":
            area = random.Random(hash(name) % 1000).uniform(200, 600)
        else:
            area = 0
        zones_data.append(
            f"- {name} (Chile): severidad quemada {severity} | Área: {area:.0f} km²"
        )

    for z in FOREST_DEFORESTATION_ZONES:
        name = z["name"]
        status = FOREST_CLEARING_STATUS.get(name, "intacto")
        if status == "deforestado":
            area = random.Random(hash(name) % 1000).uniform(300, 1000)
        elif status == "degradado":
            area = random.Random(hash(name) % 1000).uniform(50, 300)
        else:
            area = 0
        zones_data.append(
            f"- {name} (Paraguay): {status} | Área: {area:.0f} km²"
        )

    fire_summary = f"Análisis de Incendios — {fire_result.event_name}\nZonas: {len(fire_result.zones)} | Área: {fire_result.total_affected_area_km2:.1f} km² | Severidad: {fire_result.max_severity}"
    deforest_summary = f"Análisis de Deforestación — {deforest_result.event_name}\nZonas: {len(deforest_result.zones)} | Área: {deforest_result.total_affected_area_km2:.1f} km² | Severidad: {deforest_result.max_severity}"

    return {
        "zones_data": "\n".join(zones_data),
        "detection_results": {"fire": fire_result, "deforestation": deforest_result},
        "summary": fire_summary + "\n" + deforest_summary,
    }


def run_hidro() -> dict[str, Any]:
    """Ejecuta HidroSAT: inundaciones + análisis espectral real."""
    detector = ChangeDetector()

    zones_for_detection = [{"name": z["name"], "lat": z["lat"], "lng": z["lng"]} for z in HIDRO_ZONES]

    flood_result = detector.detect_flood(
        event_name="Inundaciones Rio Grande do Sul",
        zones=zones_for_detection,
        flood_status=HIDRO_FLOOD_STATUS,
        seed=2026,
    )

    # Cargar análisis espectral real de Sentinel-2
    s2_data = load_sentinel2_analysis("hidro")
    zones_data = []
    if s2_data:
        zones_data.extend(format_sentinel2_data("hidro", s2_data, ["ndwi", "ndvi"]))
        zones_data.append("")
        zones_data.append("Modelo de inundación (simulación calibrada):")
    for z in HIDRO_ZONES:
        name = z["name"]
        status = HIDRO_FLOOD_STATUS.get(name, "no_inundado")
        if status == "inundado":
            area = random.Random(hash(name) % 1000).uniform(50, 200)
        elif status == "parcial":
            area = random.Random(hash(name) % 1000).uniform(10, 50)
        else:
            area = 0
        zones_data.append(
            f"- {name} (Brasil): {status} | Área inundada: {area:.0f} km²"
        )

    return {
        "zones_data": "\n".join(zones_data),
        "detection_results": {"flood": flood_result},
        "summary": detector.summary(),
    }


PRODUCT_RUNNERS = {
    "agro": run_agro,
    "sismo": run_sismo,
    "urban": run_urban,
    "forest": run_forest,
    "hidro": run_hidro,
}


# ═════════════════════════════════════════════════════════════════════
# Generación de artículo con LLM
# ═════════════════════════════════════════════════════════════════════

def generate_article(product: str, data: dict[str, Any]) -> str:
    """Genera el artículo del boletín via LLM."""
    info = PRODUCT_INFO[product]
    prompt_template = ARTICLE_PROMPTS[product]

    prompt = prompt_template.format(
        zones_data=data["zones_data"],
        cta=info["cta"],
        hashtags=info["hashtags"],
    )

    try:
        from llm_utils import llm_call

        response = llm_call(
            messages=[
                {"role": "system", "content": f"Eres el editor de {info['name']}, boletín de TerraSAT. Respondes en español, formato profesional para redes sociales."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.warning(f"LLM article failed: {e}")
        return _fallback_article(product, data)


def _fallback_article(product: str, data: dict[str, Any]) -> str:
    """Artículo de respaldo sin LLM."""
    info = PRODUCT_INFO[product]
    lines = data["zones_data"].split("\n")

    article = f"{info['icon']} {info['name'].upper()} — ALERTA\n\n"
    article += f"Análisis de imágenes satelitales de NASA y ESA detecta eventos en Latinoamérica.\n\n"
    article += "Zonas detectadas:\n"
    for line in lines:
        article += f"• {line}\n"
    article += f"\n{info['cta']}\n\n{info['hashtags']}"
    return article


# ═════════════════════════════════════════════════════════════════════
# Guardar outputs
# ═════════════════════════════════════════════════════════════════════

def save_outputs(product: str, article: str, today: date):
    """Guarda artículo y prompt de imagen."""
    output_dir = Path("scripts")
    output_dir.mkdir(exist_ok=True)

    article_path = output_dir / f"{product}-article.txt"
    article_path.write_text(article, encoding="utf-8")
    print(f"  📄 Artículo guardado: {article_path}")

    prompt_path = output_dir / f"{product}-image-prompt.txt"
    prompt_path.write_text(IMAGE_PROMPTS[product], encoding="utf-8")
    print(f"  🎨 Prompt de imagen guardado: {prompt_path}")


# ═════════════════════════════════════════════════════════════════════
# Rotación automática
# ═════════════════════════════════════════════════════════════════════

def get_current_product(today: date) -> str:
    """Calcula qué producto toca según la semana del año."""
    week_num = today.isocalendar()[1]
    return PRODUCTS[week_num % len(PRODUCTS)]


# ═════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="TerraSAT — Boletín Multisectorial")
    parser.add_argument("--product", choices=PRODUCTS, help="Producto específico (default: rotación automática)")
    args = parser.parse_args()

    today = date(2026, 8, 14)
    product = args.product or get_current_product(today)
    info = PRODUCT_INFO[product]

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║  TerraSAT / {info['name']:<10} — BOLETÍN MULTISECTORIAL              ║
║  {info['tagline']:<52}  ║
║  Fecha: {today.strftime('%d/%m/%Y')}                                              ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    # ─── Ejecutar detección ─────────────────────────────────────
    print(f"  Ejecutando detección {info['name']}...\n")
    data = PRODUCT_RUNNERS[product]()

    print(f"  {'─' * 66}")
    print(f"  📊 RESULTADOS DE DETECCIÓN")
    print(f"  {'─' * 66}")
    for line in data["summary"].split("\n"):
        print(f"  {line}")

    # ─── Generar artículo ───────────────────────────────────────
    print(f"\n  Generando artículo con LLM...\n")
    article = generate_article(product, data)

    print(f"\n  {'═' * 66}")
    print(f"  📝 ARTÍCULO PARA REDES SOCIALES")
    print(f"  {'═' * 66}")
    print()
    for line in article.split("\n"):
        print(f"  {line}")

    # ─── Guardar outputs ────────────────────────────────────────
    print(f"\n  {'─' * 66}")
    save_outputs(product, article, today)

    # ─── Pipeline de publicación ────────────────────────────────
    print(f"\n  {'─' * 66}")
    print(f"  Pipeline de publicación:")
    print(f"  1. Generar imagen en Gemini con scripts/{product}-image-prompt.txt")
    print(f"  2. node scripts/add-branding-terrasat.mjs \"imagen_gemini.png\" --output \"scripts/{product}-post.jpg\" --period \"{today.strftime('%d')}–{(today + timedelta(days=6)).strftime('%d %b %Y')}\"")
    print(f"  3. Publicar en Facebook con scripts/{product}-article.txt")
    print(f"  {'─' * 66}")

    # ─── Próximo producto ───────────────────────────────────────
    idx = PRODUCTS.index(product)
    next_product = PRODUCTS[(idx + 1) % len(PRODUCTS)]
    next_info = PRODUCT_INFO[next_product]
    next_week = today + timedelta(days=7)
    print(f"\n  Próximo boletín: {next_info['name']} — {next_info['tagline']}")
    print(f"  Fecha: {next_week.strftime('%d/%m/%Y')}")
    print(f"  Ejecutar: python nooa-agent/demo_boletin_multisectorial.py --product {next_product}")


if __name__ == "__main__":
    main()
