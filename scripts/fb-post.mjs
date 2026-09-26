/**
 * fb-post.mjs — Publica imagen + artículo en la página de Facebook de TerraSAT.
 *
 * Uso:
 *   node scripts/fb-post.mjs "<imagen.jpg>" "@scripts/generated-article.txt" [--dry-run]
 *
 * Requiere (vía .env o variables de entorno):
 *   FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN
 *
 * Endpoint: POST /{page_id}/photos (Graph API v21.0) — crea un post con foto
 * en el timeline de la página. --dry-run muestra qué se publicaría sin postear.
 */

import { readFileSync, existsSync } from "fs";
import { resolve } from "path";

const args = process.argv.slice(2);
if (!args[0] || args[0] === "--help" || args[0] === "-h") {
  console.log('Uso: node scripts/fb-post.mjs "<imagen.jpg>" "@articulo.txt" [--dry-run]');
  process.exit(0);
}

const dryRun = args.includes("--dry-run");
const positional = args.filter(a => a !== "--dry-run");
const imagePath = resolve(positional[0]);
const articleArg = positional[1] || "";

// ── .env / env vars ──
function loadEnv() {
  const envPath = resolve(".env");
  if (!existsSync(envPath)) return;
  for (const line of readFileSync(envPath, "utf-8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !line.trim().startsWith("#") && !process.env[m[1]]) {
      process.env[m[1]] = m[2].trim();
    }
  }
}
loadEnv();

const PAGE_ID = process.env.FB_PAGE_ID;
const TOKEN = process.env.FB_PAGE_ACCESS_TOKEN;
if (!PAGE_ID || !TOKEN) {
  console.error("Error: faltan FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN en .env o entorno");
  process.exit(1);
}

if (!existsSync(imagePath)) {
  console.error(`Error: no existe la imagen ${imagePath}`);
  process.exit(1);
}

const caption = articleArg.startsWith("@")
  ? readFileSync(resolve(articleArg.slice(1)), "utf-8").trim()
  : articleArg;

if (!caption) {
  console.error("Error: caption vacío (pasar @archivo.txt o texto)");
  process.exit(1);
}

if (dryRun) {
  console.log("── DRY RUN — no se publica nada ──");
  console.log(`Página:  ${PAGE_ID}`);
  console.log(`Imagen:  ${imagePath}`);
  console.log(`Caption (${caption.length} chars):\n${caption}`);
  process.exit(0);
}

const GRAPH = "https://graph.facebook.com/v21.0";
const form = new FormData();
form.append("source", new Blob([readFileSync(imagePath)]), "post.jpg");
form.append("caption", caption);
form.append("access_token", TOKEN);

console.log(`Publicando en página ${PAGE_ID}...`);
const resp = await fetch(`${GRAPH}/${PAGE_ID}/photos`, { method: "POST", body: form });
const data = await resp.json();

if (!resp.ok) {
  console.error(`Error ${resp.status}:`, JSON.stringify(data, null, 2));
  process.exit(1);
}

console.log(`Publicado. post_id=${data.post_id ?? data.id}`);
