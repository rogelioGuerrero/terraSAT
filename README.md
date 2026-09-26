# TerraSAT

**Mapas interactivos e informes de inteligencia satelital para agricultura y ciudades.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)

---

## Verticales

### AgroSAT — Alerta temprana agrícola

Informe semanal con mapa interactivo que detecta deterioro de cultivos, déficit hídrico y enfermedad del cultivo **15 días antes** de que aparezcan síntomas visibles.

- **Entregables**: Mapa interactivo HTML + Informe narrativo + GeoJSON/KML drone-ready + Mapa de prescripción (VRA)
- **Clientes**: Productores, cooperativas, aseguradoras, agroservicios, ONGs, fondos verdes en LAC

### UrbanSAT — Monitoreo urbano satelital

Informe mensual con mapa interactivo de nuevas construcciones, islas de calor urbano y pérdida de áreas verdes en ciudades de Latinoamérica y el Caribe.

- **Entregables**: Mapa interactivo HTML + Informe narrativo
- **Clientes**: Gobiernos, catastro, urbanistas, ONGs ambientales, fondos verdes, academia en LAC

---

## Pipeline de publicación

**Automatizado** (`.github/workflows/agrosat-weekly.yml`): cada lunes 12:00 UTC corre
análisis → mapa → screenshot → branding → publicación en Facebook.
Secrets requeridos en el repo: `CDSE_USERNAME`, `CDSE_PASSWORD`, `GROQ_API_KEY`,
`PEXELS_API_KEY`, `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`. `workflow_dispatch` con `dry_run=true`
genera todo sin publicar. Si el job falla (p.ej. token de FB expirado), el
mismo pipeline se corre manual:

1. Generar análisis: `python nooa-agent/demo_alerta_temprana_regional.py` (AgroSAT) o `python nooa-agent/demo_urban_sat.py` (UrbanSAT)
   - AgroSAT usa **datos reales** por defecto: Sentinel-2 L2A (NDVI/NDRE via CDSE Statistical API, máscara de nubes SCL) + precipitación Open-Meteo/ERA5 vs climatología de 5 años. Ventana actual (21 días) vs mismo período del año anterior. Zonas sin imagen limpia salen como "sin datos". Usar `--simulate` para la simulación histórica.
   - Salidas: `scripts/generated-article.txt`, `scripts/gemini-prompt.txt`, `scripts/agro-zones.json`
2. Generar mapa: `python nooa-agent/generate_map.py` (lee `agro-zones.json`; `--simulate` para ignorarlo) o `python nooa-agent/generate_urban_map.py` (UrbanSAT)
3. Foto de cultivo: `node scripts/fetch-pexels-photo.mjs "<query>"` (o imagen Gemini opcional con `gemini-prompt.txt`)
4. `node scripts/combine-images.mjs "<foto>" "<mapa>"` — o `split-analysis.mjs` para efecto mitad natural / mitad análisis
5. `node scripts/add-branding-terrasat.mjs` — branding + período de observación
6. Publicar en Facebook:
   - **Webhook (recomendado)**: `PUBLISH_WEBHOOK_URL` de un escenario Make.com/Zapier (Custom webhook → Facebook "Create a Post") — `node scripts/post-webhook.mjs "<imagen>" "@articulo.txt"`. Necesario porque la app Meta actual no puede obtener `pages_read_engagement` sin App Review.
   - **Graph API**: `node scripts/fb-post.mjs "<imagen>" "@scripts/generated-article.txt"` (solo si la app tiene permisos pages_*; `--dry-run` para previsualizar)
   - **Manual**: subir imagen + pegar artículo en el compositor de la página
7. Actualizar SPA: agregar entrada a `web/src/data/informes.json` + imagen optimizada en `web/src/assets/`

---

## SPA (Sitio web)

React + Vite + TypeScript + TailwindCSS + shadcn/ui + react-leaflet.

```bash
cd web
npm install
npm run dev    # desarrollo en localhost:5180
npm run build  # build de producción a dist/
```

### Agregar un nuevo informe a la SPA

1. Optimizar imagen con sharp: `node -e "require('sharp')('orig.jpg').resize(800,600,{fit:'cover'}).jpeg({quality:80}).toFile('opt.jpg')"`
2. Copiar a `web/src/assets/informe-<nombre>-opt.jpg`
3. Agregar entrada a `web/src/data/informes.json`
4. Agregar import + mapeo en `web/src/components/terrasat-portfolio.tsx`
5. `npm run build` y desplegar

---

## Requisitos

- Python 3.12+
- Node.js (para scripts de imagen y SPA)
- `uv` para gestión de dependencias Python

```bash
uv sync --no-install-project   # el pyproject declara build que no aplica a este repo
npm install
```

Correr scripts Python con `.venv/Scripts/python` (Windows) o `uv run --no-sync python`.

## Contacto

info@agtisa.com · WhatsApp: 0971 561333 · Latinoamérica y el Caribe (LAC)
