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
análisis → mapa → screenshot → branding → publicación → informe en la SPA → deploy Netlify.
Secrets requeridos en el repo: `CDSE_USERNAME`, `CDSE_PASSWORD`, `GROQ_API_KEY`,
`PEXELS_API_KEY`; opcionales: `PUBLISH_WEBHOOK_URL` (publicación FB vía webhook),
`NETLIFY_AUTH_TOKEN` + `NETLIFY_SITE_ID` (deploy automático del sitio).
`workflow_dispatch` con `dry_run=true` genera todo sin publicar. Si el job falla, el
mismo pipeline se corre manual:

1. Generar análisis: `python nooa-agent/demo_alerta_temprana_regional.py` (AgroSAT) o `python nooa-agent/demo_urban_sat.py` (UrbanSAT)
   - AgroSAT usa **datos reales** por defecto: Sentinel-2 L2A (NDVI/NDRE via CDSE Statistical API, máscara de nubes SCL) + precipitación Open-Meteo/ERA5 vs climatología de 5 años. Ventana actual (21 días) vs mismo período del año anterior. Zonas sin imagen limpia salen como "sin datos". Usar `--simulate` para la simulación histórica.
   - Las zonas monitoreadas viven en `nooa-agent/agro_zones_config.json` — editables sin tocar código. El pipeline es agnóstico a la escala: `area_ha` define el bbox consultado; sirve igual para una región de 300k ha o una finca de 50 ha.
   - **Área afectada medida, no estimada**: fracción de pixels con NDVI < (media baseline − 0.05) en la ventana actual menos la misma fracción medida en el baseline (exceso de pixels degradados). Todo queda auditable en `agro-zones.json` → `meta` por zona.
   - La "anticipación" no se mide: en modo real `days_early_warning` es 0 y el boletín reporta la fecha de la última imagen limpia. El claim "15 días antes" del CTA es copy de marketing, no un dato medido.
   - Salidas: `scripts/generated-article.txt`, `scripts/gemini-prompt.txt`, `scripts/agro-zones.json`
2. Generar mapa: `python nooa-agent/generate_map.py` (lee `agro-zones.json`; `--simulate` para ignorarlo) o `python nooa-agent/generate_urban_map.py` (UrbanSAT)
3. Foto de cultivo: `node scripts/fetch-pexels-photo.mjs "<query>"` (o imagen Gemini opcional con `gemini-prompt.txt`)
4. `node scripts/combine-images.mjs "<foto>" "<mapa>"` — o `split-analysis.mjs` para efecto mitad natural / mitad análisis
5. `node scripts/add-branding-terrasat.mjs` — branding + período de observación
6. Publicar en Facebook:
   - **Webhook (recomendado)**: `PUBLISH_WEBHOOK_URL` de un escenario Make.com/Zapier (Custom webhook → Facebook "Create a Post") — `node scripts/post-webhook.mjs "<imagen>" "@articulo.txt"`. Necesario porque la app Meta actual no puede obtener `pages_read_engagement` sin App Review.
   - **Graph API**: `node scripts/fb-post.mjs "<imagen>" "@scripts/generated-article.txt"` (solo si la app tiene permisos pages_*; `--dry-run` para previsualizar)
   - **Manual**: subir imagen + pegar artículo en el compositor de la página (o copiar el texto del informe publicado en https://terrasat.agtisa.com)
7. Actualizar SPA: `node scripts/publish-informe.mjs` (genera entrada en `informes.json` + foto/video de Pexels en `web/src/assets/`; `--dry-run` para previsualizar, `--force` para recrear)

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

**Automático**: `node scripts/publish-informe.mjs` (requiere los artefactos del boletín).

**Manual**: copiar imagen a `web/src/assets/informe-<nombre>-opt.jpg` (+ opcional `-video-opt.mp4`), agregar entrada a `web/src/data/informes.json`, `npm run build` y desplegar. Los assets se mapean por convención de nombre vía `import.meta.glob` — no hace falta tocar `terrasat-portfolio.tsx`.

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
