/**
 * fetch-pexels-photo.mjs — Busca y descarga una foto de Pexels para el post.
 *
 * Reemplaza el paso manual de generar imagen en Gemini.
 *
 * Requiere: PEXELS_API_KEY en .env o entorno
 * Uso: node scripts/fetch-pexels-photo.mjs "<query>" [--output "<ruta>"] [--index N]
 */

import { writeFileSync } from "fs";
import { resolve } from "path";
import { fetchPexels } from "./pexels-utils.mjs";

const args = process.argv.slice(2);
if (!args[0] || args[0] === "--help" || args[0] === "-h") {
  console.log('Uso: node scripts/fetch-pexels-photo.mjs "<query>" [--output "<ruta>"] [--index N]');
  console.log('  --index N  elige el N-ésimo resultado (default 0)');
  process.exit(0);
}

const query = args[0];
let outputPath = "scripts/pexels-photo.jpg";
let index = 0;

for (let i = 1; i < args.length; i++) {
  if (args[i] === "--output" && args[i + 1]) outputPath = resolve(args[i + 1]), i++;
  else if (args[i] === "--index" && args[i + 1]) index = parseInt(args[i + 1], 10), i++;
}

const url = `https://api.pexels.com/v1/search?query=${encodeURIComponent(query)}&per_page=10&orientation=landscape`;
console.log(`Buscando en Pexels: "${query}"...`);
const data = await fetchPexels(url);
const photos = Array.isArray(data.photos) ? data.photos : [];

if (photos.length === 0) {
  console.error("Sin resultados en Pexels");
  process.exit(1);
}

const photo = photos[Math.min(index, photos.length - 1)];
// large2x (~1880px) tiene buena resolución para posts sin ser gigante
const src = photo.src.large2x || photo.src.large || photo.src.original;
console.log(`Foto ${photo.id} por ${photo.photographer} (${photo.width}x${photo.height})`);

const res = await fetch(src);
if (!res.ok) {
  console.error(`Error descargando: HTTP ${res.status}`);
  process.exit(1);
}
writeFileSync(outputPath, Buffer.from(await res.arrayBuffer()));
console.log(`Guardada: ${outputPath}`);
