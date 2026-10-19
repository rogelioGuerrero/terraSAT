/**
 * editorial-review.mjs — Compuerta editorial mecánica del pipeline TerraSAT.
 *
 * Antes de publicar un boletín (web o redes) un humano revisa el artículo y
 * lo atesta con este script, que escribe un manifiesto en
 * scripts/reviews/<producto>-<fin-de-ventana YYYYMMDD>.json con los SHA-256
 * exactos de los bytes del artículo, las zonas y la variante social.
 *
 * assertEditorialReview() verifica ese manifiesto contra los archivos
 * actuales: si cualquier byte cambió desde la revisión, la publicación se
 * bloquea. También exige que las zonas sean datos reales (source "real"),
 * del producto correcto, con ventana current válida y zonas no vacías.
 *
 * Qué garantiza (y qué NO):
 *   - Los hashes fijan los archivos FUENTE: el artículo, las zonas y la
 *     variante social que entran al pipeline son byte a byte lo que el
 *     revisor vio. La presentación final (cuerpo normalizado, título y
 *     excerpt derivados) y los assets generados después (figuras, mapa,
 *     foto/video de stock) quedan FUERA del manifiesto.
 *   - NO autentican la colecta satelital (el pipeline pudo haber fallado o
 *     medido mal) ni certifican la exactitud semántica del texto. Eso sigue
 *     siendo responsabilidad del revisor humano.
 *   - El contenido ya publicado en el sitio NO se revisa retroactivamente.
 *
 * Uso CLI:
 *   node scripts/editorial-review.mjs --product agro|forest|urban \
 *       --reviewer "Nombre" --confirm-reviewed
 *   Sin --confirm-reviewed solo imprime el checklist y sale con error.
 */

import { createHash } from "crypto";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname, basename } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const REVIEWS_DIR = resolve(ROOT, "scripts", "reviews");

export const REVIEW_PRODUCTS = ["agro", "forest", "urban"];

export class EditorialReviewError extends Error {
  constructor(msg) {
    super(msg);
    this.name = "EditorialReviewError";
  }
}

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$/;

function isIsoDate(s) {
  return typeof s === "string" && ISO_DATE_RE.test(s.trim()) && !Number.isNaN(Date.parse(s));
}

function sha256File(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

// Verifica el JSON de zonas contra el producto esperado. Devuelve el
// sufijo YYYYMMDD del fin de la ventana current (nombre del manifiesto).
function checkZonesData(zonesData, product, zonesPath) {
  const where = basename(zonesPath);
  if (!zonesData || typeof zonesData !== "object") {
    throw new EditorialReviewError(`${where}: JSON inválido`);
  }
  if (zonesData.product !== product) {
    throw new EditorialReviewError(
      `${where}: product "${zonesData.product}" no coincide con "${product}"`
    );
  }
  if (zonesData.source !== "real") {
    throw new EditorialReviewError(
      `${where}: source="${zonesData.source}" — solo se publican boletines con datos reales ` +
      `(la simulación --simulate es demo interna, nunca publicable)`
    );
  }
  const current = zonesData.window?.current;
  if (!Array.isArray(current) || current.length !== 2 || !current.every(isIsoDate)) {
    throw new EditorialReviewError(
      `${where}: window.current debe tener dos fechas ISO (inicio, fin)`
    );
  }
  if (!Array.isArray(zonesData.zones) || zonesData.zones.length === 0) {
    throw new EditorialReviewError(`${where}: zones vacío — nada que publicar`);
  }
  return new Date(current[1]).toISOString().slice(0, 10).replace(/-/g, "");
}

// Ruta del manifiesto de revisión para un producto + fin de ventana.
export function reviewManifestPath(product, windowEndYyyymmdd) {
  return resolve(REVIEWS_DIR, `${product}-${windowEndYyyymmdd}.json`);
}

/**
 * Compuerta editorial. Lanza EditorialReviewError si el boletín no tiene
 * atestación humana válida y vigente; devuelve el manifiesto si pasa.
 *
 * { product, articlePath, zonesPath, reviewPath?, socialPath? }
 *   - reviewPath: si se omite, se deriva de window.current[1] de zonesPath
 *     → scripts/reviews/<product>-<yyyymmdd>.json
 *   - socialPath: si se pasa, el manifiesto debe tener social_sha256 igual
 *     al hash del archivo; si el manifiesto trae social_sha256 y no se pasa
 *     socialPath, también falla (faltaría un artefacto del set revisado).
 */
export function assertEditorialReview({ product, articlePath, zonesPath, reviewPath = null, socialPath = null }) {
  if (!REVIEW_PRODUCTS.includes(product)) {
    throw new EditorialReviewError(`product debe ser ${REVIEW_PRODUCTS.join("|")} (recibido: ${product})`);
  }
  for (const [label, p] of [["artículo", articlePath], ["zonas", zonesPath]]) {
    if (!p || !existsSync(p)) {
      throw new EditorialReviewError(`no existe el archivo de ${label}: ${p}`);
    }
  }

  const zonesBuf = readFileSync(zonesPath);
  let zonesData;
  try {
    zonesData = JSON.parse(zonesBuf.toString("utf8"));
  } catch {
    throw new EditorialReviewError(`${basename(zonesPath)}: JSON ilegible`);
  }
  const windowEnd = checkZonesData(zonesData, product, zonesPath);
  const manifestPath = reviewPath || reviewManifestPath(product, windowEnd);

  if (!existsSync(manifestPath)) {
    throw new EditorialReviewError(
      `sin atestación de revisión humana: falta ${manifestPath}\n` +
      `  Revisá el artículo y atestalo con:\n` +
      `  node scripts/editorial-review.mjs --product ${product} --reviewer "Nombre" --confirm-reviewed`
    );
  }
  let manifest;
  try {
    manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  } catch {
    throw new EditorialReviewError(`${basename(manifestPath)}: manifiesto ilegible`);
  }

  const mfile = basename(manifestPath);
  if (manifest.product !== product) {
    throw new EditorialReviewError(`${mfile}: product "${manifest.product}" ≠ "${product}"`);
  }
  if (typeof manifest.reviewer !== "string" || !manifest.reviewer.trim()) {
    throw new EditorialReviewError(`${mfile}: falta reviewer (atestación humana requerida)`);
  }
  if (!isIsoDate(manifest.reviewed_at)) {
    throw new EditorialReviewError(`${mfile}: reviewed_at inválido (debe ser fecha ISO)`);
  }
  const expect = {
    article_sha256: articlePath,
    zones_sha256: zonesPath,
    ...(socialPath ? { social_sha256: socialPath } : {}),
  };
  for (const [field, p] of Object.entries(expect)) {
    const actual = sha256File(p);
    if (manifest[field] !== actual) {
      throw new EditorialReviewError(
        `${mfile}: ${field} no coincide — ${basename(p)} cambió desde la revisión ` +
        `(o el manifiesto es de otro archivo). Re-revisar y re-atestar.`
      );
    }
  }
  if (!socialPath && manifest.social_sha256) {
    throw new EditorialReviewError(
      `${mfile}: el manifiesto incluye social_sha256 pero no se presentó la variante social`
    );
  }
  return manifest;
}

/**
 * Si un path es un artefacto generado del pipeline
 * (generated-article[-forest|-urban][-social].txt), devuelve los paths que
 * debe verificar la compuerta: artículo web subyacente + zonas del producto
 * + la variante social cuando exista. Devuelve null para cualquier otro
 * archivo o texto arbitrario — captions genéricos quedan fuera del gate.
 */
export function generatedArticlePaths(filePath) {
  const name = basename(filePath);
  const m = name.match(/^generated-article(?:-(forest|urban))?(-social)?\.txt$/);
  if (!m) return null;
  const product = m[1] || "agro";
  const dir = dirname(resolve(filePath));
  const suffix = product === "agro" ? "" : `-${product}`;
  const articlePath = resolve(dir, `generated-article${suffix}.txt`);
  const socialFile = resolve(dir, `generated-article${suffix}-social.txt`);
  const isSocial = Boolean(m[2]);
  return {
    product,
    articlePath: isSocial ? articlePath : resolve(filePath),
    zonesPath: resolve(dir, `${product}-zones.json`),
    socialPath: isSocial ? resolve(filePath) : (existsSync(socialFile) ? socialFile : null),
  };
}

// ── CLI de atestación ────────────────────────────────────────────────

const CHECKLIST = (product, articleName, zonesName, socialName) => `
CHECKLIST DE REVISIÓN EDITORIAL — ${product}
El revisor abre los archivos y verifica, a mano:

  [ ] 1. Fuente: ${zonesName} tiene source "real" (no "simulated") y la
         ventana current corresponde al período del boletín.
  [ ] 2. Figuras: cada métrica de las figuras y del mapa coincide con los
         números de ${zonesName} (estados, hectáreas, áreas afectadas).
  [ ] 3. Causalidad: el artículo NO afirma causas (plaga, sequía, fuego,
         deforestación, enfermedad) salvo que exista ground truth externo
         que lo respalde. Las etiquetas alert_cause de las zonas son
         heurísticas internas NO verificadas — no bastan para sostener un
         claim causal publicado.
  [ ] 4. Nada no derivable de los índices: no hay cifras, zonas, eventos ni
         "anticipación en días" que no estén en los datos medidos.
  [ ] 5. Título/excerpt/social: el titular y el lead reflejan lo mismo que
         los datos; ${socialName} es el mismo contenido + CTA/hashtags
         (CTA y hashtags solo en la variante social, nunca en la web).

QUÉ GARANTIZA (y qué NO) la atestación:
  - El SHA-256 del manifiesto fija los archivos FUENTE (artículo, zonas,
    social): son byte a byte lo que el revisor vio. La presentación final
    (cuerpo normalizado, título/excerpt derivados) y los assets generados
    después (figuras, mapa, foto/video) quedan FUERA del manifiesto.
  - NO autentica la colecta satelital ni certifica que el contenido sea
    semánticamente correcto: eso es responsabilidad del revisor.
  - No revisa retroactivamente el contenido ya publicado en el sitio.

Para atestar tras completar el checklist:
  node scripts/editorial-review.mjs --product ${product} \\
      --reviewer "Nombre Apellido" --confirm-reviewed
`;

function cliMain() {
  const args = process.argv.slice(2);
  const get = (flag) => {
    const i = args.indexOf(flag);
    return i >= 0 ? args[i + 1] : null;
  };
  const product = get("--product");
  const reviewer = get("--reviewer");
  const confirm = args.includes("--confirm-reviewed");

  if (!product || !REVIEW_PRODUCTS.includes(product)) {
    console.error(`Uso: node scripts/editorial-review.mjs --product ${REVIEW_PRODUCTS.join("|")} --reviewer "Nombre" --confirm-reviewed`);
    process.exit(1);
  }

  const suffix = product === "agro" ? "" : `-${product}`;
  const articlePath = resolve(ROOT, "scripts", `generated-article${suffix}.txt`);
  const zonesPath = resolve(ROOT, "scripts", `${product}-zones.json`);
  const socialPath = resolve(ROOT, "scripts", `generated-article${suffix}-social.txt`);
  const socialArg = existsSync(socialPath) ? socialPath : null;

  // Las mismas validaciones de zonas que exige el gate: no se atesta un
  // boletín simulado, de otro producto o sin ventana válida.
  let windowEnd;
  try {
    if (!existsSync(articlePath)) throw new EditorialReviewError(`no existe ${articlePath}`);
    if (!existsSync(zonesPath)) throw new EditorialReviewError(`no existe ${zonesPath}`);
    windowEnd = checkZonesData(JSON.parse(readFileSync(zonesPath, "utf8")), product, zonesPath);
  } catch (err) {
    console.error(`⛔ No se puede atestar: ${err.message}`);
    process.exit(1);
  }

  if (!confirm || !reviewer || !reviewer.trim()) {
    console.log(CHECKLIST(product, basename(articlePath), basename(zonesPath), basename(socialPath)));
    if (confirm) console.error("⛔ --confirm-reviewed requiere --reviewer \"Nombre\"");
    else console.log("(salida sin escribir manifiesto — falta --confirm-reviewed y/o --reviewer)");
    process.exit(1);
  }

  const manifest = {
    product,
    reviewer: reviewer.trim(),
    reviewed_at: new Date().toISOString(),
    window_end: `${windowEnd.slice(0, 4)}-${windowEnd.slice(4, 6)}-${windowEnd.slice(6, 8)}`,
    article_sha256: sha256File(articlePath),
    zones_sha256: sha256File(zonesPath),
    ...(socialArg ? { social_sha256: sha256File(socialArg) } : {}),
  };
  mkdirSync(REVIEWS_DIR, { recursive: true });
  const out = reviewManifestPath(product, windowEnd);
  writeFileSync(out, JSON.stringify(manifest, null, 2) + "\n");
  console.log(`Atestación registrada: ${out}`);
  console.log(`  Revisor: ${manifest.reviewer} · ${manifest.reviewed_at}`);
  console.log(`  Cubre: ${basename(articlePath)}, ${basename(zonesPath)}${socialArg ? `, ${basename(socialPath)}` : ""}`);
  console.log("  Recordatorio: los hashes prueban identidad de archivos, no la exactitud del contenido.");
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  cliMain();
}
