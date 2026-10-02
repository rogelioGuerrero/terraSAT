# TerraSAT — notas operativas para agentes

## Deploy del sitio (obligatorio tras cambios en web/)

El sitio https://terrasat.agtisa.com (Netlify, site id
`4a7c0880-c95c-414f-b5c0-d6a7385d67eb`) NO tiene auto-deploy desde git.
Después de cualquier cambio en `web/` (o en `informes.json`, figuras en
`web/public/`, assets), hay que hacer build + deploy manual:

```bash
cd web
npm run build
# deploy dist → Netlify (MCP netlify deploy-site, siteId de arriba)
```

Alternativa CLI: `npx netlify-cli deploy --dir=dist --prod`
(requiere `NETLIFY_AUTH_TOKEN`; hoy no está en `.env` — usar el MCP).

Regla del usuario: **no olvidar el deploy** — un cambio commiteado/pusheado
que no se deploya NO es visible en el sitio público.

## Pipeline editorial (estilo JRC)

- `nooa-agent/article_pipeline.py` — genera artículo + `generated-article*-social.txt`
  (variante sin figuras, con CTA+hashtags, para FB).
- `scripts/gen-choropleth-echarts.mjs` — coropleta admin-1 (Natural Earth 10m
  filtrado en `scripts/data/ne_10m_admin_1_lac.geojson`, point-in-polygon).
- `nooa-agent/gen_fig_editorial.py` — barras NDVI/ha afectadas (matplotlib).
- `nooa-agent/generate_map_editorial.py` — mapa Leaflet; `--interactive` genera
  el HTML embebible que publish copia a `web/public/maps/`.
- `scripts/publish-informe.mjs` — orquesta: entrada en `web/src/data/informes.json`,
  figuras en `web/public/figs/`, mapa en `web/public/maps/`. Idempotente por
  período+producto (`--dry-run`, `--force`).

## Convenciones

- Español: `55.000` (miles) y `-0,065` (decimales).
- En el artículo web no van nombres de sensores/misiones (QA los rechaza):
  usar "satélites de la Agencia Espacial Europea (Copernicus)".
- CTA y hashtags NO van en el artículo web — van separados (social/CTA).
- Secrets en `.env` — nunca copiarlos a código ni a la conversación.
