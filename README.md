# TerraSAT

**Procesamiento de imágenes satelitales para agricultura y ciudades.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)

---

## Verticales

### AgroSAT — Alerta temprana agrícola

Boletín semanal que detecta deterioro de cultivos, déficit hídrico y enfermedad del cafetal **15 días antes** de que aparezcan síntomas visibles.

- **Cliente**: Agricultores, cooperativas, aseguradoras, agroservicios
- **Salidas**: Artículo + mapa HTML + imagen con branding

### UrbanSAT — Monitoreo urbano satelital

Boletín mensual con 3 servicios:
1. Detección de nuevas construcciones (cambio de uso de suelo)
2. Islas de calor urbano
3. Pérdida de áreas verdes

- **Cliente**: Municipios, catastro, direcciones de obras, ambiente
- **Ciudades**: Salto, Colonia, Rivera, Florida (Uruguay), Asunción (Paraguay), Santa Cruz (Bolivia), Cuenca (Ecuador)

---

## Pipeline de publicación

1. Generar boletín: `python nooa-agent/demo_alerta_temprana_regional.py` (AgroSAT) o `python nooa-agent/demo_urban_sat.py` (UrbanSAT)
2. Generar mapa: `python nooa-agent/generate_map.py` (AgroSAT) o `python nooa-agent/generate_urban_map.py` (UrbanSAT)
3. Generar imagen artística en Gemini con prompt
4. `node scripts/split-analysis.mjs` — efecto mitad natural / mitad análisis B/N
5. `node scripts/add-branding-terrasat.mjs` — branding + período de observación
6. Publicar imagen + artículo

---

## Requisitos

- Python 3.12+
- Node.js (para scripts de imagen)
- `uv` para gestión de dependencias

```bash
uv sync
npm install
```

## Contacto

info@agtisa.com · terraSAT.agtisa.com
