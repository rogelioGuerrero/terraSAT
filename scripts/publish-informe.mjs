/**
 * publish-informe.mjs — Publica el boletín AgroSAT de la semana en la SPA.
 *
 * Lee scripts/generated-article.txt + scripts/agro-zones.json, genera
 * título/excerpt con Groq (fallback determinista si falla), descarga
 * foto+video de Pexels optimizados, y prepende la entrada a
 * web/src/data/informes.json. Idempotente por período.
 *
 * Requiere: PEXELS_API_KEY en .env o entorno; GROQ_API_KEY opcional.
 * Uso: node scripts/publish-informe.mjs [--dry-run] [--no-video] [--force]
 */

import { readFileSync, writeFileSync, existsSync, unlinkSync, statSync } from "fs";
import { resolve, dirname, join } from "path";
import { fileURLToPath } from "url";
import sharp from "sharp";
import ffmpegPath from "ffmpeg-static";
import ffmpeg from "fluent-ffmpeg";
import { fetchPexels, searchPexelsVideos, toClipMetadata } from "./pexels-utils.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const ASSETS = resolve(ROOT, "web", "src", "assets");
const INFORMES_JSON = resolve(ROOT, "web", "src", "data", "informes.json");

const PRODUCT_SPECS = {
  agro: {
    name: "AgroSAT",
    category: "agrosat",
    zonesPath: resolve(ROOT, "scripts", "agro-zones.json"),
    articlePath: resolve(ROOT, "scripts", "generated-article.txt"),
    photoQuery: "agriculture crop field aerial drone",
    videoQuery: "drought agriculture field dry aerial",
  },
  forest: {
    name: "ForestSAT",
    category: "forestsat",
    zonesPath: resolve(ROOT, "scripts", "forest-zones.json"),
    articlePath: resolve(ROOT, "scripts", "generated-article-forest.txt"),
    photoQuery: "tropical forest canopy aerial amazon",
    videoQuery: "forest canopy aerial jungle",
  },
  urban: {
    name: "UrbanSAT",
    category: "urbansat",
    zonesPath: resolve(ROOT, "scripts", "urban-zones.json"),
    articlePath: resolve(ROOT, "scripts", "generated-article-urban.txt"),
    photoQuery: "city aerial buildings skyline latin america",
    videoQuery: "city aerial drone buildings construction",
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
const ARTICLE_PATH = SPEC.articlePath;
const ZONES_PATH = SPEC.zonesPath;

ffmpeg.setFfmpegPath(ffmpegPath);

const MESES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];

// Estándar editorial: títulos y excerpts publicables — sin markdown ni
// emojis (el LLM a veces devuelve "🛰️ **Crisis...**").
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

function formatPeriod(isoRange) {
  const [a, b] = isoRange.map((s) => new Date(s));
  const sameMonth = a.getUTCMonth() === b.getUTCMonth();
  if (sameMonth)
    return `${a.getUTCDate()}–${b.getUTCDate()} ${MESES[a.getUTCMonth()]} ${a.getUTCFullYear()}`;
  return `${a.getUTCDate()} ${MESES[a.getUTCMonth()]}–${b.getUTCDate()} ${MESES[b.getUTCMonth()]} ${b.getUTCFullYear()}`;
}

// Tokens numéricos del artículo normalizados a dígitos puros ("55.000" → "55000").
// Sirve para verificar que cada cifra de un keyStat exista literalmente en el
// texto ya validado — si el LLM inventa una cifra, el stat se descarta.
function articleDigitTokens(article) {
  const tokens = new Set();
  for (const m of article.matchAll(/\d[\d.,\s\u00A0\u202F]*/g)) {
    const d = m[0].replace(/\D/g, "");
    if (d) tokens.add(d);
  }
  return tokens;
}

function statDigits(stat) {
  const out = [];
  for (const m of `${stat.value} ${stat.label}`.matchAll(/\d[\d.,\s\u00A0\u202F]*/g)) {
    const d = m[0].replace(/\D/g, "");
    if (d) out.push(d);
  }
  return out;
}

function sanitizeStats(raw, article) {
  if (!Array.isArray(raw)) return undefined;
  const tokens = articleDigitTokens(article);
  const stats = raw
    .filter((s) => s && s.value && s.label)
    .map((s) => ({
      value: sanitizeText(String(s.value)).slice(0, 24),
      label: sanitizeText(String(s.label)).slice(0, 60),
    }))
    .filter((s) => statDigits(s).every((d) => tokens.has(d)))
    .slice(0, 4);
  return stats.length ? stats : undefined;
}

async function generateTitleExcerpt(article) {
  const key = process.env.GROQ_API_KEY;
  if (!key) return null;
  try {
    const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      body: JSON.stringify({
        model: process.env.GROQ_MODEL || "openai/gpt-oss-120b",
        max_completion_tokens: 2000,
        response_format: { type: "json_object" },
        messages: [
          {
            role: "user",
            content:
              "Del siguiente boletín agro-satelital genera JSON con tres campos: " +
              '"title" (título periodístico en español, máx 90 caracteres, sin comillas), ' +
              '"excerpt" (resumen de 1-2 oraciones con zonas y hectáreas concretas, máx 220 caracteres) y ' +
              '"keyStats" (array de 3-4 objetos {"value","label"} con las cifras clave del informe: ' +
              'value = la cifra tal como aparece en el texto, ej. "55.000 ha"; label = qué mide en 3-6 palabras). ' +
              "Solo JSON, nada más.\n\nBOLETÍN:\n" + article.slice(0, 6000),
          },
        ],
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const content = data.choices?.[0]?.message?.content || "";
    const parsed = JSON.parse(content.replace(/```json|```/g, "").trim());
    if (!parsed.title || !parsed.excerpt) return null;
    const cut = (s, n) => {
      const t = String(s).slice(0, n);
      return t.length < String(s).length ? t.slice(0, t.lastIndexOf(" ")) : t;
    };
    return {
      title: cut(sanitizeText(parsed.title), 90),
      excerpt: cut(sanitizeText(parsed.excerpt), 220),
      keyStats: sanitizeStats(parsed.keyStats, article),
    };
  } catch {
    return null;
  }
}

function fallbackTitleExcerpt(article, zones) {
  const title =
    sanitizeText(article.split("\n")[0]).slice(0, 90) || `Boletín ${SPEC.name}`;
  const total = zones.reduce((s, z) => s + (z.area_ha || 0), 0);
  const alert = zones
    .filter((z) => z.status === "critico" || z.status === "alerta")
    .reduce((s, z) => s + (z.affected_area_ha || 0), 0);
  const excerpt =
    `Sentinel-2: ${alert.toLocaleString("es-ES")} ha en alerta de ` +
    `${total.toLocaleString("es-ES")} ha monitoreadas en ${zones.length} zonas.`;
  return { title, excerpt: excerpt.slice(0, 220) };
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

async function main() {
  if (!existsSync(ARTICLE_PATH) || !existsSync(ZONES_PATH)) {
    console.error(`Faltan ${ARTICLE_PATH} o ${ZONES_PATH} — corre el boletín ${PRODUCT} primero`);
    process.exit(1);
  }
  const article = readFileSync(ARTICLE_PATH, "utf8").trim();
  const zonesData = JSON.parse(readFileSync(ZONES_PATH, "utf8"));
  const zones = zonesData.zones || [];
  const period = formatPeriod(zonesData.window.current);
  const endDate = zonesData.window.current[1].slice(0, 10).replace(/-/g, "");
  const slug = `informe-${SPEC.category}-${endDate}`;
  const imageFile = `${slug}-opt.jpg`;
  const videoFile = `${slug}-video-opt.mp4`;

  const informes = JSON.parse(readFileSync(INFORMES_JSON, "utf8"));
  if (!FORCE && informes.some((i) => i.date === period && i.category === SPEC.category)) {
    console.log(`Ya existe un informe ${SPEC.category} para "${period}" — nada que hacer (o usa --force)`);
    return;
  }

  const countries = new Set(zones.map((z) => z.country)).size;
  const location = `${zones.length} zonas de ${countries} ${countries === 1 ? "país" : "países"} de LAC`;

  console.log("Generando título, excerpt y cifras clave con Groq...");
  const meta = (await generateTitleExcerpt(article)) || fallbackTitleExcerpt(article, zones);
  const { title, excerpt } = meta;

  const entry = {
    id: String(Math.max(...informes.map((i) => parseInt(i.id, 10) || 0)) + 1),
    title,
    category: SPEC.category,
    date: period,
    location,
    image: imageFile,
    ...(NO_VIDEO ? {} : { video: videoFile }),
    excerpt,
    article,
    ...(meta.keyStats ? { keyStats: meta.keyStats } : {}),
  };

  if (DRY_RUN) {
    console.log("\nDRY-RUN — entrada que se crearía:");
    console.log(JSON.stringify({ ...entry, article: article.slice(0, 120) + "…" }, null, 2));
    console.log(`Assets: ${imageFile}, ${NO_VIDEO ? "(sin video)" : videoFile}`);
    return;
  }

  console.log(`Descargando assets para ${slug}...`);
  const okPhoto = await fetchPhoto(SPEC.photoQuery, join(ASSETS, imageFile));
  if (!okPhoto) {
    console.error("No se pudo descargar foto de Pexels — abortando (el informe requiere imagen)");
    process.exit(1);
  }
  if (!NO_VIDEO) await fetchVideo(SPEC.videoQuery, slug);

  informes.unshift(entry);
  writeFileSync(INFORMES_JSON, JSON.stringify(informes, null, 2) + "\n");
  console.log(`\nInforme #${entry.id} "${title}" añadido a informes.json`);
  console.log("Siguiente: npm --prefix web run build  (o el deploy automático del workflow)");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
