/**
 * publish-informe.mjs — Publica el boletín AgroSAT de la semana en la SPA.
 *
 * Lee scripts/generated-article.txt + scripts/agro-zones.json, deriva
 * título/excerpt deterministas del artículo revisado, descarga
 * foto+video de Pexels optimizados, y prepende la entrada a
 * web/src/data/informes.json. Idempotente por período.
 *
 * Compuerta editorial: exige atestación humana vigente
 * (scripts/reviews/<producto>-<yyyymmdd>.json, ver
 * scripts/editorial-review.mjs) ANTES de cualquier generación de assets,
 * figuras o llamada de red — también con --dry-run y --force. Después de la
 * atestación corre el QA numérico/formato determinista
 * (nooa-agent/article_qa.py): una cifra que no existe en los datos aborta.
 * Si una figura referenciada (/figs/) no se genera, se aborta sin publicar:
 * el artículo atestado nunca se muta ni se renumera.
 *
 * Requiere: PEXELS_API_KEY en .env o entorno.
 * Uso: node scripts/publish-informe.mjs [--dry-run] [--no-video] [--force]
 */

import { readFileSync, writeFileSync, existsSync, unlinkSync, statSync, mkdirSync } from "fs";
import { execFileSync } from "child_process";
import { resolve, dirname, join, basename } from "path";
import { fileURLToPath } from "url";
import sharp from "sharp";
import ffmpegPath from "ffmpeg-static";
import ffmpeg from "fluent-ffmpeg";
import { fetchPexels, searchPexelsVideos, toClipMetadata } from "./pexels-utils.mjs";
import { assertEditorialReview } from "./editorial-review.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const ASSETS = resolve(ROOT, "web", "src", "assets");
const FIGS_DIR = resolve(ROOT, "web", "public", "figs");
const MAPS_DIR = resolve(ROOT, "web", "public", "maps");
const INFORMES_JSON = resolve(ROOT, "web", "src", "data", "informes.json");
const PYTHON = existsSync(resolve(ROOT, ".venv", "Scripts", "python.exe"))
  ? resolve(ROOT, ".venv", "Scripts", "python.exe")
  : "python";

const PRODUCT_SPECS = {
  agro: {
    name: "AgroSAT",
    category: "agrosat",
    zonesPath: resolve(ROOT, "scripts", "agro-zones.json"),
    articlePath: resolve(ROOT, "scripts", "generated-article.txt"),
    socialPath: resolve(ROOT, "scripts", "generated-article-social.txt"),
    photoQuery: "agriculture crop field aerial drone",
    videoQuery: "drought agriculture field dry aerial",
    mapTitle: "Estrés vegetativo en cultivos de Latinoamérica",
  },
  forest: {
    name: "ForestSAT",
    category: "forestsat",
    zonesPath: resolve(ROOT, "scripts", "forest-zones.json"),
    articlePath: resolve(ROOT, "scripts", "generated-article-forest.txt"),
    socialPath: resolve(ROOT, "scripts", "generated-article-forest-social.txt"),
    photoQuery: "tropical forest canopy aerial amazon",
    videoQuery: "forest canopy aerial jungle",
    mapTitle: "Estado de la cobertura forestal en Latinoamérica",
  },
  urban: {
    name: "UrbanSAT",
    category: "urbansat",
    zonesPath: resolve(ROOT, "scripts", "urban-zones.json"),
    articlePath: resolve(ROOT, "scripts", "generated-article-urban.txt"),
    socialPath: resolve(ROOT, "scripts", "generated-article-urban-social.txt"),
    photoQuery: "city aerial buildings skyline latin america",
    videoQuery: "city aerial drone buildings construction",
    mapTitle: "Cambio urbano detectado en ciudades de Latinoamérica",
  },
};

const args = process.argv.slice(2);
const DRY_RUN = args.includes("--dry-run");
const NO_VIDEO = args.includes("--no-video");
const FORCE = args.includes("--force");
const prodIdx = args.indexOf("--product");
const PRODUCT = prodIdx >= 0 ? args[prodIdx + 1] : "agro";
const SPEC = PRODUCT_SPECS[PRODUCT];
if (!SPEC) {
  console.error(`--product debe ser ${Object.keys(PRODUCT_SPECS).join("|")}`);
  process.exit(1);
}

ffmpeg.setFfmpegPath(ffmpegPath);

const MESES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];

// Estándar editorial: títulos, excerpts y CTA publicables — sin markdown
// ni emojis (el pipeline a veces produce "🛰️ **Crisis...**").
const EMOJI_RE = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}]/gu;

function sanitizeText(s) {
  return String(s)
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/^#+\s*/gm, "")
    .replace(EMOJI_RE, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

// El artículo web va limpio (sin CTA ni hashtags), pero la SPA renderiza
// ambos aparte — los extrae de la variante social generada por
// article_pipeline.social_version(): "<artículo>\n\n<cta> 🌱☕\n\n#tags".
function extractSocialExtras(socialPath) {
  if (!existsSync(socialPath)) return {};
  const lines = readFileSync(socialPath, "utf8")
    .replace(/\r\n?/g, "\n")
    .split("\n");
  const hashtags = [];
  while (lines.length) {
    const last = lines[lines.length - 1].trim();
    if (!last) { lines.pop(); continue; }
    if (/^#[\p{L}\d_]+(\s+#[\p{L}\d_]+)*$/u.test(last)) {
      hashtags.unshift(...last.split(/\s+/).map((t) => t.replace(/^#/, "")));
      lines.pop();
    } else break;
  }
  const idx = lines.findIndex(
    (l) => l.includes("info@agtisa.com") || l.trim().startsWith("¿Su ")
  );
  const cta = idx >= 0 ? sanitizeText(lines[idx]) : "";
  return { ...(cta ? { cta } : {}), ...(hashtags.length ? { hashtags } : {}) };
}

function formatPeriod(isoRange) {
  const [a, b] = isoRange.map((s) => new Date(s));
  const sameMonth = a.getUTCMonth() === b.getUTCMonth();
  if (sameMonth)
    return `${a.getUTCDate()}–${b.getUTCDate()} ${MESES[a.getUTCMonth()]} ${a.getUTCFullYear()}`;
  return `${a.getUTCDate()} ${MESES[a.getUTCMonth()]}–${b.getUTCDate()} ${MESES[b.getUTCMonth()]} ${b.getUTCFullYear()}`;
}

// Corte en límite de palabra: nunca parte una palabra a la mitad.
function wordTrim(s, n) {
  const t = s.trim();
  if (t.length <= n) return t;
  const cut = t.slice(0, n);
  const i = cut.lastIndexOf(" ");
  return (i > 0 ? cut.slice(0, i) : cut).trim();
}

// Un bloque de prosa sustantiva: no encabezado, imagen, cita, subhead en
// negrita, nota/caption en cursiva ni lista.
function isProseBlock(block) {
  const t = block.trim();
  if (!t) return false;
  if (/^#{1,6}\s/.test(t)) return false;
  if (/^[!>]/.test(t)) return false;
  if (/^\*\*[^*]+\*\*$/.test(t)) return false;
  if (/^\*[^*]+\*$/.test(t)) return false;
  if (/^([-*+] |\d+\. )/.test(t)) return false;
  return true;
}

// Título y excerpt deterministas, derivados del artículo ya revisado (el
// manifiesto fija sus bytes): título = primera línea, excerpt = primer
// párrafo de prosa sustantiva. No se genera metadata con LLM ni hay
// fallback que introduzca cifras o nombres de sensores no revisados.
function deriveTitleExcerpt(article, productName) {
  const title =
    wordTrim(sanitizeText(article.split(/\r?\n/, 1)[0]), 90) || `Boletín ${productName}`;
  const firstPara = article.split(/\r?\n\s*\r?\n/).find(isProseBlock);
  const excerpt = wordTrim(sanitizeText(firstPara || title), 220);
  return { title, excerpt };
}

// QA determinista anti-alucinación numérica (nooa-agent/article_qa.py):
// compara cada cifra del artículo con los valores permitidos del zones JSON
// y chequea formato editorial. Lanza Error con el detalle si no pasa.
export function runArticleQa(articlePath, zonesPath, python = PYTHON) {
  try {
    execFileSync(
      python,
      [
        resolve(ROOT, "nooa-agent", "article_qa.py"),
        "--article", articlePath,
        "--zones", zonesPath,
      ],
      { stdio: ["ignore", "pipe", "inherit"], cwd: ROOT, encoding: "utf8" }
    );
  } catch (err) {
    const detail = String(err.stdout || "").trim();
    throw new Error(
      `QA numérico/formato rechazó ${basename(articlePath)}: ${detail || err.message}`
    );
  }
}

// Figuras editoriales (estilo JRC): coropleta admin-1 (ECharts SSR) +
// barras matplotlib. Los nombres coinciden con los que article_pipeline
// inyecta en el markdown: /figs/<category>-<yyyymmdd>-<key>.png
function genFigures(figPrefix, zonesPath, spec) {
  mkdirSync(FIGS_DIR, { recursive: true });
  const failed = [];
  try {
    execFileSync("node", [
      resolve(ROOT, "scripts", "gen-choropleth-echarts.mjs"),
      "--zones", zonesPath,
      "--out", join(FIGS_DIR, `${figPrefix}-mapa.png`),
      "--title", spec.mapTitle,
      "--subtitle", "Unidad admin-1 coloreada por estado de la zona monitoreada",
    ], { stdio: "inherit", cwd: ROOT });
  } catch {
    failed.push("mapa");
  }
  try {
    execFileSync(PYTHON, [
      resolve(ROOT, "nooa-agent", "gen_fig_editorial.py"),
      "--zones", zonesPath,
      "--out-dir", FIGS_DIR,
      "--prefix", figPrefix,
    ], { stdio: "inherit", cwd: ROOT });
  } catch {
    failed.push("ndvi", "ha");
  }
  return failed;
}

// Mapa interactivo Leaflet embebido en el informe (iframe /maps/*.html).
// Devuelve la ruta web relativa o null si no se pudo generar — el mapa es
// un asset complementario, no está referenciado en los bytes del artículo.
function genInteractiveMap(figPrefix, zonesPath, spec) {
  try {
    mkdirSync(MAPS_DIR, { recursive: true });
    const out = join(MAPS_DIR, `${figPrefix}.html`);
    execFileSync(PYTHON, [
      resolve(ROOT, "nooa-agent", "generate_map_editorial.py"),
      "--zones", zonesPath,
      "--out", out,
      "--interactive",
      "--title", spec.mapTitle,
      "--subtitle", "Explorá cada zona: clic para ver cultivo, estado y hectáreas",
    ], { stdio: "inherit", cwd: ROOT });
    return `/maps/${figPrefix}.html`;
  } catch (err) {
    console.warn(`  Mapa interactivo no generado: ${err.message}`);
    return null;
  }
}

async function fetchPhoto(query, outPath) {
  const url = `https://api.pexels.com/v1/search?query=${encodeURIComponent(query)}&per_page=8&orientation=landscape`;
  const data = await fetchPexels(url);
  const photos = Array.isArray(data.photos) ? data.photos : [];
  if (!photos.length) return false;
  const src = photos[0].src.large2x || photos[0].src.large || photos[0].src.original;
  const res = await fetch(src);
  if (!res.ok) return false;
  await sharp(Buffer.from(await res.arrayBuffer()))
    .resize(800, 600, { fit: "cover" })
    .jpeg({ quality: 82 })
    .toFile(outPath);
  console.log(`  Foto: ${outPath}`);
  return true;
}

function ffmpegRun(input, opts, out) {
  return new Promise((res, rej) =>
    ffmpeg(input).outputOptions(opts).output(out).on("end", res).on("error", rej).run()
  );
}

async function fetchVideo(query, slug) {
  const videos = await searchPexelsVideos(query);
  if (!videos.length) return false;
  const meta = toClipMetadata(videos[0]);
  const raw = join(ASSETS, `${slug}-raw.mp4`);
  const opt = join(ASSETS, `${slug}-video-opt.mp4`);
  const poster = join(ASSETS, `${slug}-video-poster.jpg`);
  try {
    const res = await fetch(meta.downloadUrl);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    writeFileSync(raw, Buffer.from(await res.arrayBuffer()));
    await ffmpegRun(raw, [
      "-vf scale=1280:-2", "-r 24", "-c:v libx264", "-preset medium",
      "-crf 30", "-an", "-movflags +faststart", "-y",
    ], opt);
    await ffmpegRun(opt, ["-vf scale=1280:-2", "-frames:v 1", "-q:v 5", "-y"], poster);
    console.log(`  Video: ${(statSync(opt).size / 1024 / 1024).toFixed(1)} MB + poster`);
    return true;
  } catch (err) {
    console.error(`  Video falló: ${err.message}`);
    for (const f of [opt, poster]) try { if (existsSync(f)) unlinkSync(f); } catch {}
    return false;
  } finally {
    try { if (existsSync(raw)) unlinkSync(raw); } catch {}
  }
}

// Núcleo publicador. Toda operación con side effects (red, escritura de
// informes.json, generación de assets) va detrás de la compuerta editorial
// + QA. `deps` permite inyectar stubs en tests (paths y funciones falsas)
// sin tocar el repo ni la red.
export async function runPublish(opts = {}, deps = {}) {
  const product = opts.product || PRODUCT;
  const spec = PRODUCT_SPECS[product];
  if (!spec) throw new Error(`--product debe ser ${Object.keys(PRODUCT_SPECS).join("|")}`);
  const paths = {
    article: spec.articlePath,
    zones: spec.zonesPath,
    social: spec.socialPath,
    informesJson: INFORMES_JSON,
    ...(deps.paths || {}),
  };
  const fns = {
    review: assertEditorialReview,
    qa: runArticleQa,
    genFigs: (figPrefix) => genFigures(figPrefix, paths.zones, spec),
    genMap: (figPrefix) => genInteractiveMap(figPrefix, paths.zones, spec),
    getPhoto: fetchPhoto,
    getVideo: fetchVideo,
    ...(deps.fns || {}),
  };
  const dryRun = Boolean(opts.dryRun);
  const noVideo = Boolean(opts.noVideo);
  const force = Boolean(opts.force);

  if (!existsSync(paths.article) || !existsSync(paths.zones)) {
    throw new Error(`Faltan ${paths.article} o ${paths.zones} — corre el boletín ${product} primero`);
  }

  // 1) Compuerta editorial: atestación humana vigente sobre los bytes
  //    exactos de artículo+zonas(+social) — antes de cualquier otra cosa,
  //    incluidos --dry-run y --force.
  let review;
  try {
    review = fns.review({
      product,
      articlePath: paths.article,
      zonesPath: paths.zones,
      socialPath: existsSync(paths.social) ? paths.social : null,
    });
  } catch (err) {
    throw new Error(`Compuerta editorial: ${err.message}`);
  }
  console.log(`Revisión editorial verificada — ${review.reviewer} (${review.reviewed_at})`);

  // 2) QA determinista: cada cifra del artículo revisado debe existir en
  //    los datos de zonas (article_qa.py). Falla → abort antes de assets.
  fns.qa(paths.article, paths.zones);
  console.log("QA numérico/formato: OK");

  const article = readFileSync(paths.article, "utf8").trim();
  const zonesData = JSON.parse(readFileSync(paths.zones, "utf8"));
  const zones = zonesData.zones || [];
  const period = formatPeriod(zonesData.window.current);
  const endDate = zonesData.window.current[1].slice(0, 10).replace(/-/g, "");
  const slug = `informe-${spec.category}-${endDate}`;
  const imageFile = `${slug}-opt.jpg`;
  const videoFile = `${slug}-video-opt.mp4`;

  const informes = JSON.parse(readFileSync(paths.informesJson, "utf8"));
  if (!force && informes.some((i) => i.date === period && i.category === spec.category)) {
    console.log(`Ya existe un informe ${spec.category} para "${period}" — nada que hacer (o usa --force)`);
    return;
  }

  const countries = new Set(zones.map((z) => z.country)).size;
  const location = `${zones.length} zonas de ${countries} ${countries === 1 ? "país" : "países"} de LAC`;

  const { title, excerpt } = deriveTitleExcerpt(article, spec.name);

  const entry = {
    id: String(Math.max(...informes.map((i) => parseInt(i.id, 10) || 0)) + 1),
    title,
    category: spec.category,
    date: period,
    location,
    image: imageFile,
    excerpt,
    article,
    ...extractSocialExtras(paths.social),
  };

  if (dryRun) {
    console.log("\nDRY-RUN — entrada que se crearía:");
    console.log(JSON.stringify({ ...entry, article: article.slice(0, 120) + "…" }, null, 2));
    console.log(
      `Assets: ${imageFile}, ` +
      (noVideo ? "(sin video)" : `${videoFile} (planificado — se incluye solo si la descarga tiene éxito)`)
    );
    return;
  }

  // Figuras editoriales: solo si el artículo referencia /figs/ (las inyecta
  // article_pipeline.inject_figures). Son requeridas: si alguna falla se
  // aborta SIN publicar — mutar o renumerar el artículo atestado rompería
  // el manifiesto de revisión (los bytes deben ser idénticos a lo revisado).
  if (article.includes("/figs/")) {
    console.log("Generando figuras editoriales (coropleta + barras)...");
    const failed = fns.genFigs(`${spec.category}-${endDate}`);
    if (failed.length) {
      throw new Error(
        `Figuras requeridas no generadas: ${failed.join(", ")} — ` +
        "publicación abortada; el artículo revisado no se modifica"
      );
    }
  }

  // Mapa interactivo embebido en el informe (iframe en la SPA)
  const mapPath = fns.genMap(`${spec.category}-${endDate}`);
  if (mapPath) entry.map = mapPath;

  console.log(`Descargando assets para ${slug}...`);
  const okPhoto = await fns.getPhoto(spec.photoQuery, join(ASSETS, imageFile));
  if (!okPhoto) {
    throw new Error("No se pudo descargar foto de Pexels — abortando (el informe requiere imagen)");
  }
  // Video opcional: entra al informe solo si la descarga+optimización tuvo
  // éxito — nunca una URL rota. Falla → el informe sale sin video.
  if (!noVideo && (await fns.getVideo(spec.videoQuery, slug))) entry.video = videoFile;

  informes.unshift(entry);
  writeFileSync(paths.informesJson, JSON.stringify(informes, null, 2) + "\n");
  console.log(`\nInforme #${entry.id} "${title}" añadido a informes.json`);
  console.log("Siguiente: npm --prefix web run build  (o el deploy automático del workflow)");
}

const IS_CLI = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (IS_CLI) {
  runPublish({ product: PRODUCT, dryRun: DRY_RUN, noVideo: NO_VIDEO, force: FORCE }).catch((err) => {
    console.error(err instanceof Error ? err.message : err);
    process.exit(1);
  });
}
