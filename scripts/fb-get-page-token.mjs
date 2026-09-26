/**
 * fb-get-page-token.mjs — Deriva el Page Access Token desde un User Token.
 *
 * El User Token (Graph API Explorer, con permisos pages_* habilitados)
 * expira; la page token derivada de un user token long-lived NO expira.
 * Este script resuelve /me/accounts, encuentra la página TerraSAT y
 * actualiza FB_PAGE_ID + FB_PAGE_ACCESS_TOKEN en .env.
 *
 * Uso: node scripts/fb-get-page-token.mjs "<user_token>" [--page "Terrasat"]
 */

import { readFileSync, writeFileSync, existsSync } from "fs";
import { resolve } from "path";

const args = process.argv.slice(2);
if (!args[0] || args[0] === "--help") {
  console.log('Uso: node scripts/fb-get-page-token.mjs "<user_token>" [--page "Terrasat"]');
  process.exit(0);
}

const userToken = args[0];
let pageName = "Terrasat";
for (let i = 1; i < args.length; i++) {
  if (args[i] === "--page" && args[i + 1]) { pageName = args[i + 1]; i++; }
}

const resp = await fetch(
  `https://graph.facebook.com/v21.0/me/accounts?access_token=${userToken}`
);
const data = await resp.json();
if (data.error) {
  console.error("Error:", data.error.message);
  process.exit(1);
}

const pages = data.data || [];
console.log(`Páginas administradas por este usuario:`);
for (const p of pages) console.log(`  - ${p.name} (id ${p.id})`);

const target = pages.find(
  p => p.name.toLowerCase() === pageName.toLowerCase()
);
if (!target) {
  console.error(`\nNo se encontró la página "${pageName}". Usar --page "<nombre>"`);
  process.exit(1);
}

const envPath = resolve(".env");
let env = existsSync(envPath) ? readFileSync(envPath, "utf-8") : "";
const set = (k, v) => {
  env = env.match(new RegExp(`^${k}=.*$`, "m"))
    ? env.replace(new RegExp(`^${k}=.*$`, "m"), `${k}=${v}`)
    : env + `\n${k}=${v}`;
};
set("FB_PAGE_ID", target.id);
set("FB_PAGE_ACCESS_TOKEN", target.access_token);
writeFileSync(envPath, env);

console.log(`\n.env actualizado:`);
console.log(`  FB_PAGE_ID=${target.id}`);
console.log(`  FB_PAGE_ACCESS_TOKEN=<page token, ${target.access_token.length} chars>`);
console.log(`  (mismos valores para los secrets de GitHub)`);
