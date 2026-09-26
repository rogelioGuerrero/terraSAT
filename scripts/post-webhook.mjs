/**
 * post-webhook.mjs — Publica imagen + artículo vía webhook (Make.com / Zapier / IFTTT).
 *
 * Alternativa a fb-post.mjs cuando la app de Meta no puede obtener los
 * permisos pages_*. El escenario en Make/Zapier ya tiene autorización FB
 * aprobada: nuestro POST dispara su "Create a Post" en la página.
 *
 * Payload: multipart — campo "image" (archivo) + campo "caption" (texto).
 *
 * Requiere (vía .env o entorno): PUBLISH_WEBHOOK_URL
 *
 * Uso:
 *   node scripts/post-webhook.mjs "<imagen.jpg>" "@articulo.txt" [--dry-run]
 */

import { readFileSync, existsSync } from "fs";
import { resolve, basename } from "path";

const args = process.argv.slice(2);
if (!args[0] || args[0] === "--help" || args[0] === "-h") {
  console.log('Uso: node scripts/post-webhook.mjs "<imagen.jpg>" "@articulo.txt" [--dry-run]');
  process.exit(0);
}

const dryRun = args.includes("--dry-run");
const positional = args.filter(a => a !== "--dry-run");
const imagePath = resolve(positional[0]);
const articleArg = positional[1] || "";

try { process.loadEnvFile(resolve(".env")); } catch {}

const WEBHOOK_URL = process.env.PUBLISH_WEBHOOK_URL;
if (!WEBHOOK_URL) {
  console.error("Error: falta PUBLISH_WEBHOOK_URL en .env o entorno");
  console.error("  Crear un Custom Webhook en Make.com → módulo Facebook 'Create a Post'");
  console.error("  y pegar la URL como PUBLISH_WEBHOOK_URL=https://hook.make.com/...");
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
  console.log(`Webhook: ${WEBHOOK_URL.slice(0, 45)}...`);
  console.log(`Imagen:  ${imagePath}`);
  console.log(`Caption (${caption.length} chars):\n${caption}`);
  process.exit(0);
}

const form = new FormData();
form.append("image", new Blob([readFileSync(imagePath)]), basename(imagePath));
form.append("caption", caption);

console.log("Enviando al webhook...");
const resp = await fetch(WEBHOOK_URL, { method: "POST", body: form });
const text = await resp.text();

if (!resp.ok) {
  console.error(`Error ${resp.status}: ${text.slice(0, 400)}`);
  process.exit(1);
}

console.log(`Webhook aceptó la publicación (${resp.status}): ${text.slice(0, 200)}`);
