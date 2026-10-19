# TerraSAT

**Mapas interactivos e informes de inteligencia satelital para agricultura y ciudades.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)

---

## Verticales

### AgroSAT — Alerta temprana agrícola

Informe semanal con mapa interactivo que reporta **señales de anomalía espectral** en zonas agrícolas monitoreadas (posible deterioro vegetativo o déficit hídrico; causa por verificar en campo — el pipeline no mide anticipación ni confirma enfermedad).

- **Entregables**: Mapa interactivo HTML + Informe narrativo + GeoJSON/KML drone-ready + Mapa de prescripción (VRA)
- **Clientes**: Productores, cooperativas, aseguradoras, agroservicios, ONGs, fondos verdes en LAC

### UrbanSAT — Monitoreo urbano satelital

Informe mensual con mapa interactivo de nuevas construcciones, islas de calor urbano y pérdida de áreas verdes en ciudades de Latinoamérica y el Caribe.

- **Entregables**: Mapa interactivo HTML + Informe narrativo
- **Clientes**: Gobiernos, catastro, urbanistas, ONGs ambientales, fondos verdes, academia en LAC

---

## Pipeline de publicación

**Manual** (desde el repo, con `.env` local): el pipeline semanal corre a mano —
antes hubo una GH Action (`agrosat-weekly.yml`) pero se retiró: demasiados
secrets que mantener en CI para el valor que daba. Variables en `.env`:
`CDSE_USERNAME`, `CDSE_PASSWORD`, `GROQ_API_KEY`, `PEXELS_API_KEY`;
opcionales: `PUBLISH_WEBHOOK_URL` (publicación FB vía webhook),
`NETLIFY_AUTH_TOKEN` + `NETLIFY_SITE_ID` (deploy del sitio),
`APPWRITE_ENDPOINT` + `APPWRITE_PROJECT_ID` + `APPWRITE_API_KEY`
(+`APPWRITE_DATABASE_ID`, default `pricewatch`) para serie histórica y
estado de fases. El pipeline completo es:

1. Generar análisis: `python nooa-agent/demo_alerta_temprana_regional.py` (AgroSAT) o `python nooa-agent/demo_urban_sat.py` (UrbanSAT)
   - AgroSAT usa **datos reales** por defecto: Sentinel-2 L2A (NDVI/NDRE via CDSE Statistical API, máscara de nubes SCL) + precipitación Open-Meteo/ERA5 vs climatología de 5 años. Ventana actual (21 días) vs mismo período del año anterior. Zonas sin imagen limpia salen como "sin datos". Usar `--simulate` para la simulación histórica.
   - **ForestSAT y UrbanSAT también son reales** — el mismo colector multi-producto (`agro_real_data.py --product forest|urban`) mide índices específicos por dominio: NBR (quema) para bosques, NDBI (área construida) para ciudades. Zonas en `nooa-agent/forest_zones_config.json` y `urban_zones_config.json` (10 cada una, solo `lat`/`lng` obligatorios). El artículo y el informe de la SPA salen con `article_pipeline.py --product <p>` y `publish-informe.mjs --product <p>`. El demo `demo_urban_sat.py` viejo sigue siendo simulado — el camino real es el colector.
   - Las zonas monitoreadas viven en `nooa-agent/*_zones_config.json` — editables sin tocar código. El pipeline es agnóstico a la escala: `area_ha` define el bbox consultado; sirve igual para una región de 300k ha o una finca de 50 ha.
   - **Área afectada = estimación proxy, no medición verificada**: exceso de fracción de píxeles espectrales degradados (ventana actual vs baseline) multiplicado por las hectáreas nominales del bbox de la zona. El pixel medido no certifica que la cubierta afectada sea cultivo/bosque/área construida — no hay verificación en campo. Auditable en `agro-zones.json` → `meta` por zona.
   - La "anticipación" no se mide: en modo real `days_early_warning` es 0 y el boletín reporta la fecha de la última imagen limpia. El claim "semanas antes" del CTA es copy de marketing, no un dato medido.
   - Salidas: `scripts/generated-article.txt`, `scripts/gemini-prompt.txt`, `scripts/agro-zones.json`
   - **Artículo por fases** (`article_pipeline.py`, domain-agnostic): briefing analítico → redacción por bloques → edición → QA determinista (`article_qa.py` compara cada cifra del artículo con los valores permitidos de los datos — no verifica atribución a la zona citada ni claims causales). Estado en Appwrite → cada fase es resumible (`--phase briefing|blocks|edit|qa`) y puede correr en días distintos; si falta el hash de estado local la fase puede reiniciarse.
   - **Serie histórica en Appwrite** (`appwrite_store.py`): cada corrida guarda `terrasat_zone_observations` (1 fila/zona) + `terrasat_bulletin_runs` (estado del pipeline). Base compartida `pricewatch`, colecciones `terrasat_*`. Setup: `python nooa-agent/setup_appwrite_terrasat.py`.
2. Generar mapa: `python nooa-agent/generate_map.py` (lee `agro-zones.json`; `--simulate` para ignorarlo) o `python nooa-agent/generate_urban_map.py` (UrbanSAT)
3. Foto de cultivo: `node scripts/fetch-pexels-photo.mjs "<query>"` (o imagen Gemini opcional con `gemini-prompt.txt`)
4. `node scripts/combine-images.mjs "<foto>" "<mapa>"` — o `split-analysis.mjs` para efecto mitad natural / mitad análisis
5. `node scripts/add-branding-terrasat.mjs` — branding + período de observación
6. **Revisión editorial (obligatoria antes de publicar)**: un humano revisa
   el artículo contra `*-zones.json` y lo atesta:
   `node scripts/editorial-review.mjs --product agro|forest|urban --reviewer "Nombre" --confirm-reviewed`
   (sin `--confirm-reviewed` solo imprime el checklist). Escribe
   `scripts/reviews/<producto>-<fin-de-ventana>.json` con los SHA-256 de los
   bytes exactos revisados (artículo + zonas + variante social si existe).
   Ver "Compuerta editorial" más abajo para el alcance real de la atestación.
7. Publicar en Facebook:
   - **Webhook (recomendado)**: `PUBLISH_WEBHOOK_URL` de un escenario Make.com/Zapier (Custom webhook → Facebook "Create a Post") — `node scripts/post-webhook.mjs "<imagen>" "@articulo.txt"`. Necesario porque la app Meta actual no puede obtener `pages_read_engagement` sin App Review.
   - **Graph API**: `node scripts/fb-post.mjs "<imagen>" "@scripts/generated-article.txt"` (solo si la app tiene permisos pages_*; `--dry-run` para previsualizar)
   - Ambos scripts **bloquean** el envío de `generated-article*.txt` sin manifiesto de revisión vigente (hashes del artículo web + zonas + archivo social exacto). Captions arbitrarios (texto literal u otros archivos) quedan fuera de la compuerta.
   - **Manual**: subir imagen + pegar artículo en el compositor de la página (o copiar el texto del informe publicado en https://terrasat.agtisa.com)
8. Actualizar SPA: `node scripts/publish-informe.mjs [--product agro|forest|urban]` (genera entrada en `informes.json` + foto/video de Pexels en `web/src/assets/`; `--dry-run` para previsualizar, `--force` para recrear). Idempotente por período+producto. **Requiere la atestación del paso 6** — la compuerta corre antes de generar figuras, assets o llamar a la red, también con `--dry-run`/`--force`. Después de la atestación corre `nooa-agent/article_qa.py` (QA numérico/formato determinista): una cifra que no exista en los datos aborta antes de cualquier side effect. Título y excerpt se derivan determinísticamente del artículo revisado (primera línea y primer párrafo de prosa); no hay metadata por LLM.
   - **Figuras editoriales (estilo JRC)**: si el artículo contiene referencias `/figs/` — inyectadas por `article_pipeline.inject_figures()` a partir de los slots `{{FIG_*}}` que ubica el editor — publish las genera antes de publicar: coropleta admin-1 (`scripts/gen-choropleth-echarts.mjs`, ECharts SSR → PNG, región detectada por point-in-polygon sobre Natural Earth 10m en `scripts/data/`) + barras NDVI y hectáreas afectadas (`nooa-agent/gen_fig_editorial.py`, matplotlib). Si una figura referenciada falla, la publicación **aborta** — el artículo atestado nunca se muta ni se renumera (rompería el manifiesto).
   - **Mapa interactivo embebido**: publish también genera `web/public/maps/<categoria>-<yyyymmdd>.html` con `nooa-agent/generate_map_editorial.py --interactive` (Leaflet, zoom/popups/tooltips habilitados, sin caja de título) y lo embebe como `<iframe>` al final del informe (`campo map` en `informes.json`), con link "Abrir en pantalla completa".
9. Deploy del sitio: `cd web && npm run build` y luego
   `npx netlify-cli deploy --dir=dist --prod` — el sitio Netlify
   (`terrasat`, site id `4a7c0880-c95c-414f-b5c0-d6a7385d67eb`,
   https://terrasat.agtisa.com) NO está conectado al repo: no hay
   auto-deploy por push. Requiere `NETLIFY_AUTH_TOKEN` en `.env`,
   o deploy manual desde el dashboard (drag & drop de `web/dist`).

### Compuerta editorial — alcance y limitaciones

`scripts/editorial-review.mjs` es una compuerta **mecánica**: exige que un
humano revise cada boletín antes de publicarlo (web o redes) y deje
constancia con un manifiesto `scripts/reviews/<producto>-<yyyymmdd>.json`.

Qué verifica al publicar (`assertEditorialReview`, usado por
`publish-informe.mjs`, `fb-post.mjs` y `post-webhook.mjs`):

- El `*-zones.json` es de datos **reales** (`source: "real"` — la salida de
  `--simulate` nunca es publicable), del producto correcto, con
  `window.current` válido y zonas no vacías.
- Existe un manifiesto con `reviewer` no vacío, `reviewed_at` ISO válido y
  producto coincidente.
- Los SHA-256 del manifiesto coinciden **byte a byte** con el artículo, las
  zonas y la variante social actuales — si cualquier archivo cambió tras la
  revisión, la publicación se bloquea hasta re-atestar.

Qué **no** garantiza (limitaciones honestas):

- Los hashes fijan los **archivos fuente** (artículo/zonas/social): son byte
  a byte lo que el revisor vio. **No autentican la colecta satelital** ni
  certifican que el contenido sea semánticamente correcto — eso es
  responsabilidad del revisor humano siguiendo el checklist.
- Solo cubre los artefactos reconocidos del pipeline
  (`generated-article[-forest|-urban][-social].txt` + `*-zones.json`).
  Captions o textos arbitrarios para redes quedan **fuera** de la compuerta.
- El manifiesto cubre **solo los bytes del artículo/zonas/social** — NO cubre
  la metadata derivada (título/excerpt) ni los assets generados después:
  figuras `/figs/`, el mapa interactivo HTML y la foto/video de stock
  (Pexels). Si una figura requerida por el artículo no se genera, la
  publicación aborta (nunca se muta el artículo atestado); el resto de los
  assets deben revisarse visualmente antes del deploy.
- El contenido **ya publicado** en el sitio no se revisa retroactivamente;
  la compuerta aplica a informes nuevos desde su introducción.
- `demo_alerta_temprana_regional.py` (ruta real) sale con error si el
  pipeline por fases falla: no guarda artículo de respaldo ni salidas
  stale. El modo `--simulate` sigue siendo demo interna.

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
