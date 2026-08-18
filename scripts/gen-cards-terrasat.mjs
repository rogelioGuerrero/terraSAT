/**
 * gen-cards-terrasat.mjs — Genera cards de video TerraSAT (intro + CTA)
 *
 * Adaptado de gen-cards.mjs (BienCuidar / LocalNurse)
 *
 * Produce 2 archivos MP4 standalone, pre-renderizados:
 *   scripts/.cards/intro.mp4  — 2s, reutilizable para todos los videos
 *   scripts/.cards/cta.mp4    — 5s, cambia según el CTA
 *
 * Cada card tiene fade in desde negro y fade out a negro integrados.
 * Resolución y FPS se detectan del video de referencia (--ref),
 * o se especifican con --width, --height, --fps.
 *
 * Uso:
 *   node scripts/gen-cards-terrasat.mjs [--ref video.mp4] [--cta "texto"] [--width 1280 --height 720 --fps 24]
 *
 * Si no se pasa --ref, usa 1280x720@24fps por defecto.
 * Si no se pasa --cta, usa CTA por defecto de TerraSAT.
 */

import ffmpegStatic from "ffmpeg-static";
import sharp from "sharp";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import { resolve, dirname, join } from "path";
import { execFileSync } from "child_process";
import { tmpdir } from "os";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FFMPEG = ffmpegStatic;
const CARDS_DIR = resolve(__dirname, ".cards");

// ── Args ──
const args = process.argv.slice(2);
let refVideo = null;
let ctaText = null;
let width = 1280;
let height = 720;
let fps = 24;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--ref" && args[i + 1]) { refVideo = resolve(args[i + 1]); i++; }
  else if (args[i] === "--cta" && args[i + 1]) { ctaText = args[i + 1]; i++; }
  else if (args[i] === "--width" && args[i + 1]) { width = parseInt(args[i + 1]); i++; }
  else if (args[i] === "--height" && args[i + 1]) { height = parseInt(args[i + 1]); i++; }
  else if (args[i] === "--fps" && args[i + 1]) { fps = parseInt(args[i + 1]); i++; }
}

// ── Probe video referencia ──
function probeVideo(videoPath) {
  try {
    execFileSync(FFMPEG, ["-i", videoPath], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  } catch (err) {
    const stderr = err.stderr || "";
    const vidMatch = stderr.match(/Video:.*?(\d{2,5})x(\d{2,5})/);
    const fpsMatch = stderr.match(/(\d+(?:\.\d+)?)\s+(?:fps|tbr)/);
    if (vidMatch) {
      width = parseInt(vidMatch[1], 10);
      height = parseInt(vidMatch[2], 10);
    }
    if (fpsMatch) {
      const v = parseFloat(fpsMatch[1]);
      if (v === 24 || v === 25 || v === 30 || v === 60) fps = Math.round(v);
    }
  }
}

if (refVideo && existsSync(refVideo)) {
  probeVideo(refVideo);
  console.log(`Referencia: ${width}x${height}@${fps}fps`);
} else {
  console.log(`Default: ${width}x${height}@${fps}fps`);
}

// ── CTA por defecto de TerraSAT ──
function extractCTA() {
  if (ctaText) return ctaText;
  return "¿Necesitas inteligencia satelital de tu territorio? Solicita un mapa interactivo piloto de tu región o ciudad.";
}

// ── Icono SVG inline (satélite estilizado de TerraSAT) ──
const SATELLITE_ICON = `
  <path d="M13 7 9 3 5 7l4 4"/>
  <path d="m5 11-1 .5a1 1 0 0 0-.5.5L3 13l.5-.5a1 1 0 0 0 .5-.5L5 11"/>
  <path d="m19 13 .5.5a1 1 0 0 0 .5.5l.5.5-.5-.5a1 1 0 0 0-.5-.5L19 13"/>
  <path d="M14 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"/>
  <path d="m9 7 5 5"/>
  <path d="m17 21 4-4-4-4-4 4 4 4Z"/>
  <path d="m14 14-5-5"/>`;

function escapeXml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function wrapText(text, maxChars) {
  const words = text.split(" ");
  const lines = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > maxChars) {
      if (cur) lines.push(cur.trim());
      cur = w;
    } else cur = (cur + " " + w).trim();
  }
  if (cur) lines.push(cur.trim());
  return lines;
}

// ── Generar PNGs ──

// Intro: fondo oscuro verde-azulado, icono satélite, "TerraSAT" + título + tagline
async function makeIntroPng(w, h, outPath) {
  const iconSize = Math.round(w * 0.12);
  const brandSize = Math.round(w * 0.065);
  const titleSize = Math.round(w * 0.045);
  const tagSize = Math.round(w * 0.028);
  const cy = Math.round(h * 0.38);

  const svg = `<svg width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0a1a14"/><stop offset="50%" stop-color="#0d4f3c"/><stop offset="100%" stop-color="#064e3b"/>
    </linearGradient>
    <linearGradient id="icon" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#059669"/><stop offset="100%" stop-color="#0d9488"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.38" r="0.5">
      <stop offset="0%" stop-color="#10b981" stop-opacity="0.15"/><stop offset="100%" stop-color="#10b981" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="${w}" height="${h}" fill="url(#bg)"/>
  <rect width="${w}" height="${h}" fill="url(#glow)"/>
  <g transform="translate(${(w - iconSize) / 2}, ${cy - iconSize}) scale(${iconSize / 512})">
    <rect width="512" height="512" rx="128" fill="url(#icon)"/>
    <g transform="translate(128, 128) scale(10.67)" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${SATELLITE_ICON}</g>
  </g>
  <text x="${w / 2}" y="${cy + brandSize * 0.8}" font-family="Arial, Helvetica, sans-serif" font-size="${brandSize}" font-weight="800" fill="#ffffff" text-anchor="middle" letter-spacing="2">TerraSAT</text>
  <text x="${w / 2}" y="${cy + brandSize * 0.8 + titleSize * 1.4}" font-family="Arial, Helvetica, sans-serif" font-size="${titleSize}" font-weight="600" fill="#6ee7b7" text-anchor="middle" letter-spacing="1">Imágenes satelitales para anticipar eventos</text>
  <text x="${w / 2}" y="${cy + brandSize * 0.8 + titleSize * 1.4 + tagSize * 1.8}" font-family="Arial, Helvetica, sans-serif" font-size="${tagSize}" font-weight="400" fill="#a7f3d0" text-anchor="middle" letter-spacing="3" opacity="0.8">Observación satelital LAC</text>
</svg>`;
  writeFileSync(outPath, await sharp(Buffer.from(svg)).png().toBuffer());
}

// CTA: fondo oscuro, icono, "TerraSAT" + texto CTA + URL + WhatsApp
async function makeCTAPng(w, h, ctaText, outPath) {
  const iconSize = Math.round(w * 0.1);
  const brandSize = Math.round(w * 0.05);
  const ctaSize = Math.round(w * 0.036);
  const urlSize = Math.round(w * 0.026);
  const waSize = Math.round(w * 0.022);
  const lines = wrapText(ctaText, 30).slice(0, 4);
  const lh = Math.round(ctaSize * 1.4);
  const totalH = lines.length * lh;
  const cy = Math.round(h * 0.38);
  const iconY = cy - Math.round(h * 0.14);
  const brandY = iconY + iconSize + Math.round(w * 0.02);
  const ctaY = brandY + Math.round(w * 0.05);
  const urlY = ctaY + totalH + Math.round(w * 0.035);
  const waY = urlY + Math.round(w * 0.04);

  const svg = `<svg width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0a1a14"/><stop offset="50%" stop-color="#0d4f3c"/><stop offset="100%" stop-color="#0a1a14"/>
    </linearGradient>
    <linearGradient id="icon" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#059669"/><stop offset="100%" stop-color="#0d9488"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.5" r="0.6">
      <stop offset="0%" stop-color="#10b981" stop-opacity="0.12"/><stop offset="100%" stop-color="#10b981" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="${w}" height="${h}" fill="url(#bg)"/>
  <rect width="${w}" height="${h}" fill="url(#glow)"/>
  <g transform="translate(${(w - iconSize) / 2}, ${iconY}) scale(${iconSize / 512})">
    <rect width="512" height="512" rx="128" fill="url(#icon)"/>
    <g transform="translate(128, 128) scale(10.67)" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${SATELLITE_ICON}</g>
  </g>
  <text x="${w / 2}" y="${brandY}" font-family="Arial, Helvetica, sans-serif" font-size="${brandSize}" font-weight="800" fill="#ffffff" text-anchor="middle" letter-spacing="2">TerraSAT</text>
  ${lines.map((l, i) => `<text x="${w / 2}" y="${ctaY + i * lh}" font-family="Arial, Helvetica, sans-serif" font-size="${ctaSize}" font-weight="500" fill="#d1fae5" text-anchor="middle">${escapeXml(l)}</text>`).join("\n  ")}
  <text x="${w / 2}" y="${urlY}" font-family="Arial, Helvetica, sans-serif" font-size="${urlSize}" font-weight="600" fill="#6ee7b7" text-anchor="middle" letter-spacing="1">agtisa.com</text>
  <text x="${w / 2}" y="${waY}" font-family="Arial, Helvetica, sans-serif" font-size="${waSize}" font-weight="400" fill="#a7f3d0" text-anchor="middle" opacity="0.8">WhatsApp +595 971 561333</text>
</svg>`;
  writeFileSync(outPath, await sharp(Buffer.from(svg)).png().toBuffer());
}

// ── Renderizar PNG → MP4 con fade in/out ──
function renderCardPngToMp4(pngPath, mp4Path, duration, fadeDur, useKenBurns = false) {
  const totalFrames = Math.round(duration * fps);

  let vf;
  if (useKenBurns) {
    const zoomExpr = "1+0.03*on/" + totalFrames;
    vf =
      `scale=${width * 2}:${height * 2}:flags=lanczos,` +
      `zoompan=z='${zoomExpr}':d=${totalFrames}:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s=${width}x${height}:fps=${fps},` +
      `format=yuv420p,` +
      `fade=t=in:st=0:d=${fadeDur},fade=t=out:st=${(duration - fadeDur).toFixed(2)}:d=${fadeDur}`;
  } else {
    vf =
      `scale=${width}:${height},format=yuv420p,fps=${fps},` +
      `fade=t=in:st=0:d=${fadeDur},fade=t=out:st=${(duration - fadeDur).toFixed(2)}:d=${fadeDur}`;
  }

  const renderArgs = [
    "-y",
    "-loop", "1", "-i", pngPath,
    "-t", String(duration),
    "-vf", vf,
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
    "-pix_fmt", "yuv420p",
    "-f", "mp4",
    mp4Path,
  ];

  execFileSync(FFMPEG, renderArgs, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

// ── Main ──
async function main() {
  if (!existsSync(CARDS_DIR)) mkdirSync(CARDS_DIR, { recursive: true });

  const tmpDir = join(tmpdir(), "terrasat-cards");
  if (!existsSync(tmpDir)) mkdirSync(tmpDir, { recursive: true });

  const cta = extractCTA();
  console.log(`CTA: "${cta}"\n`);

  // CTA de la SPA: "¿Necesitas inteligencia satelital de tu territorio?"

  // 1. Generar PNGs
  const introPng = join(tmpDir, `intro_${width}x${height}.png`);
  const ctaPng = join(tmpDir, `cta_${width}x${height}.png`);

  console.log("Generando PNGs...");
  await makeIntroPng(width, height, introPng);
  await makeCTAPng(width, height, cta, ctaPng);
  console.log("  ✓ Intro PNG");
  console.log("  ✓ CTA PNG\n");

  // 2. Renderizar a MP4
  const introMp4 = join(CARDS_DIR, "intro.mp4");
  const ctaMp4 = join(CARDS_DIR, "cta.mp4");

  console.log(`Renderizando intro.mp4 (${width}x${height}@${fps}, 3s, fade 0.5s, Ken Burns)...`);
  renderCardPngToMp4(introPng, introMp4, 3, 0.5, true);
  console.log("  ✓");

  console.log(`Renderizando cta.mp4 (${width}x${height}@${fps}, 5s, fade 0.5s)...`);
  renderCardPngToMp4(ctaPng, ctaMp4, 5, 0.5, false);
  console.log("  ✓\n");

  console.log(`Cards generados en: ${CARDS_DIR}`);
  console.log(`  intro.mp4 — 3s (reutilizable)`);
  console.log(`  cta.mp4   — 5s (CTA actual)`);
}

main().catch((err) => {
  console.error("Error:", err.message);
  if (err.stderr) console.error(err.stderr.slice(0, 800));
  process.exit(1);
});
