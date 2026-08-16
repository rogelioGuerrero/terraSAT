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

1. Generar análisis: `python nooa-agent/demo_alerta_temprana_regional.py` (AgroSAT) o `python nooa-agent/demo_urban_sat.py` (UrbanSAT)
2. Generar mapa: `python nooa-agent/generate_map.py` (AgroSAT) o `python nooa-agent/generate_urban_map.py` (UrbanSAT)
3. Generar imagen artística en Gemini con prompt
4. `node scripts/split-analysis.mjs` — efecto mitad natural / mitad análisis B/N
5. `node scripts/add-branding-terrasat.mjs` — branding + período de observación
6. Publicar imagen + artículo en Facebook
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
uv sync
npm install
```

## Contacto

info@agtisa.com · WhatsApp: 0971 561333 · Latinoamérica y el Caribe (LAC)
