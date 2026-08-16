/**
 * add-branding-video-terrasat.mjs — Ensambla video TerraSAT: Intro + Clips + CTA
 *
 * Adaptado de add-branding-video.mjs (BienCuidar / LocalNurse)
 *
 * Lee intro.mp4 y cta.mp4 pre-renderizados (gen-cards-terrasat.mjs).
 * Aplica branding overlay (logo satélite + "TerraSAT" + "agtisa.com") a los clips.
 * Concatena todo con transiciones fade-to-black.
 * Borra los videos originales pesados después de ensamblar (--cleanup).
 *
 * Estructura final:
 *   intro.mp4 (2s) → [clip1 + overlay] → [clip2 + overlay] → ... → cta.mp4 (5s)
 *
 * Uso:
 *   node scripts/add-branding-video-terrasat.mjs clip1.mp4 [clip2.mp4 ...] [--output path] [--crf 23] [--cleanup]
 *
 * Requiere: ffmpeg-static, sharp, y ejecutar gen-cards-terrasat.mjs primero.
 */

import ffmpegStatic from "ffmpeg-static";
import sharp from "sharp";
import { existsSync, readFileSync, writeFileSync, mkdirSync, unlinkSync, statSync } from "fs";
import { resolve, dirname, join, basename, extname } from "path";
import { execFileSync } from "child_process";
import { tmpdir } from "os";

const FFMPEG = ffmpegStatic;
const CARDS_DIR = resolve("scripts", ".cards");
const FADE_DUR = 0.4;

// ── Args ──
const args = process.argv.slice(2);
if (!args[0] || args[0] === "--help" || args[0] === "-h") {
  console.log("Uso: node scripts/add-branding-video-terrasat.mjs clip1.mp4 [clip2.mp4] [--output path] [--crf 23] [--cleanup]");
  console.log("");
  console.log("Requiere intro.mp4 y cta.mp4 en scripts/.cards/ (gen-cards-terrasat.mjs)");
  console.log("--cleanup: borra los videos originales después de ensamblar");
  process.exit(0);
}

const inputPaths = [];
let outputPath = null;
let crf = "23";
let preset = "veryfast";
let cleanup = false;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--output" && args[i + 1]) { outputPath = resolve(args[i + 1]); i++; }
  else if (args[i] === "--crf" && args[i + 1]) { crf = args[i + 1]; i++; }
  else if (args[i] === "--preset" && args[i + 1]) { preset = args[i + 1]; i++; }
  else if (args[i] === "--cleanup") { cleanup = true; }
  else if (!args[i].startsWith("-")) { inputPaths.push(resolve(args[i])); }
}

if (inputPaths.length === 0) { console.error("Error: falta video de entrada"); process.exit(1); }
for (const p of inputPaths) {
  if (!existsSync(p)) { console.error(`Error: no existe ${p}`); process.exit(1); }
}

const introPath = join(CARDS_DIR, "intro.mp4");
const ctaPath = join(CARDS_DIR, "cta.mp4");

if (!existsSync(introPath) || !existsSync(ctaPath)) {
  console.error("Error: falta intro.mp4 o cta.mp4 en scripts/.cards/");
  console.error("Ejecuta primero: node scripts/gen-cards-terrasat.mjs --ref <video.mp4>");
  process.exit(1);
}

if (!outputPath) {
  const dir = dirname(inputPaths[0]);
  const name = basename(inputPaths[0], extname(inputPaths[0]));
  outputPath = join(dir, `${name}_branded.mp4`);
}

// ── Probe ──
function probeVideo(videoPath) {
  try {
    execFileSync(FFMPEG, ["-i", videoPath], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  } catch (err) {
    const stderr = err.stderr || "";
    const info = { width: null, height: null, duration: null, fps: 24 };
    const durMatch = stderr.match(/Duration:\s+(\d+):(\d+):(\d+(?:\.\d+)?)/);
    if (durMatch) {
      info.duration = parseInt(durMatch[1]) * 3600 + parseInt(durMatch[2]) * 60 + parseFloat(durMatch[3]);
    }
    const vidMatch = stderr.match(/Video:.*?(\d{2,5})x(\d{2,5})/);
    if (vidMatch) {
      info.width = parseInt(vidMatch[1]);
      info.height = parseInt(vidMatch[2]);
    }
    const fpsMatch = stderr.match(/(\d+(?:\.\d+)?)\s+(?:fps|tbr)/);
    if (fpsMatch) {
      const v = parseFloat(fpsMatch[1]);
      if ([24, 25, 30, 60].includes(Math.round(v))) info.fps = Math.round(v);
    }
    if (info.width && info.height) return info;
  }
  return null;
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

async function createOverlayPng(w, h, outPath) {
  const gradientHeight = Math.round(h * 0.22);
  const gradientStart = h - gradientHeight;
  const padding = Math.round(w * 0.035);
  const brandSize = Math.round(w * 0.038);
  const urlSize = Math.round(w * 0.024);
  const urlY = h - padding;
  const brandY = urlY - urlSize + Math.round(w * 0.008);
  const iconSize = Math.round(brandSize * 2.4);
  const iconX = padding;
  const iconY = brandY - Math.round(iconSize * 0.75);
  const textX = padding + iconSize + Math.round(w * 0.02);

  const svg = `<svg width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#000" stop-opacity="0"/>
      <stop offset="35%" stop-color="#000" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#000" stop-opacity="0.75"/>
    </linearGradient>
    <linearGradient id="icon" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#059669"/><stop offset="100%" stop-color="#0d9488"/>
    </linearGradient>
  </defs>
  <rect x="0" y="${gradientStart}" width="${w}" height="${gradientHeight}" fill="url(#g)"/>
  <g transform="translate(${iconX}, ${iconY}) scale(${iconSize / 512})">
    <rect width="512" height="512" rx="128" fill="url(#icon)"/>
    <g transform="translate(128, 128) scale(10.67)" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${SATELLITE_ICON}</g>
  </g>
  <text x="${textX}" y="${brandY}" font-family="Arial, Helvetica, sans-serif" font-size="${brandSize}" font-weight="600" fill="#ffffff" letter-spacing="0.5">TerraSAT</text>
  <text x="${textX}" y="${urlY + urlSize}" font-family="Arial, Helvetica, sans-serif" font-size="${urlSize}" font-weight="400" fill="#ffffff" opacity="0.85">agtisa.com</text>
</svg>`;
  writeFileSync(outPath, await sharp(Buffer.from(svg)).png().toBuffer());
}

// ── Procesar un clip: overlay + fade in/out + normalizar ──
function processClip(inputPath, outputPath, overlayPath, w, h, fps) {
  const probe = probeVideo(inputPath);
  const dur = probe?.duration || 10;

  let fadeFilter = `,fade=t=in:st=0:d=${FADE_DUR}`;
  fadeFilter += `,fade=t=out:st=${(dur - FADE_DUR).toFixed(2)}:d=${FADE_DUR}`;

  const processArgs = [
    "-y",
    "-i", inputPath,
    "-i", overlayPath,
    "-filter_complex",
    `[0:v]scale=${w}:${h}:force_original_aspect_ratio=decrease,pad=${w}:${h}:(ow-iw)/2:(oh-ih)/2:color=black[base];` +
    `[base][1:v]overlay=0:0:format=auto,format=yuv420p,fps=${fps}${fadeFilter}[v]`,
    "-map", "[v]",
    "-an",
    "-c:v", "libx264", "-preset", preset, "-crf", crf,
    "-pix_fmt", "yuv420p",
    "-r", String(fps),
    "-movflags", "+faststart",
    outputPath,
  ];

  execFileSync(FFMPEG, processArgs, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

// ── Concat con concat demuxer ──
function concatVideos(fileList, outPath) {
  const listFile = join(tmpdir(), `concat_${Date.now()}.txt`);
  const list = fileList.map(f => `file '${f.replace(/'/g, "'\\''")}'`).join("\n");
  writeFileSync(listFile, list);

  const concatArgs = [
    "-y", "-f", "concat", "-safe", "0",
    "-i", listFile,
    "-c:v", "libx264", "-preset", preset, "-crf", crf,
    "-pix_fmt", "yuv420p",
    "-an",
    "-movflags", "+faststart",
    outPath,
  ];

  try {
    execFileSync(FFMPEG, concatArgs, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  } finally {
    if (existsSync(listFile)) unlinkSync(listFile);
  }
}

// ── Main ──
async function main() {
  const probe = probeVideo(inputPaths[0]);
  if (!probe) { console.error("Error: no se pudo leer el video"); process.exit(1); }
  const { width, height, fps } = probe;

  console.log("═══════════════════════════════════════════");
  console.log("  Ensamblaje Video TerraSAT");
  console.log("═══════════════════════════════════════════\n");
  console.log(`Target: ${width}x${height}@${fps}fps`);
  console.log(`Clips: ${inputPaths.length} | Intro: 2s | CTA: 5s`);
  if (cleanup) console.log(`Cleanup: SÍ (borrar originales)\n`);

  // 1. Generar overlay PNG
  const tmpDir = join(tmpdir(), "terrasat-branding");
  if (!existsSync(tmpDir)) mkdirSync(tmpDir, { recursive: true });
  const overlayPng = join(tmpDir, `overlay_${width}x${height}.png`);
  await createOverlayPng(width, height, overlayPng);
  console.log("✓ Overlay generado");

  // 2. Procesar clips (overlay + fade + normalizar)
  const processedClips = [];
  for (let i = 0; i < inputPaths.length; i++) {
    const out = join(tmpDir, `clip_${i}.mp4`);
    console.log(`Procesando clip ${i + 1}/${inputPaths.length}...`);
    processClip(inputPaths[i], out, overlayPng, width, height, fps);
    processedClips.push(out);
    console.log(`  ✓ ${basename(inputPaths[i])}`);
  }

  // 3. Concat: intro + clips + cta
  const allFiles = [introPath, ...processedClips, ctaPath];
  console.log(`\nConcatenando ${allFiles.length} segmentos...`);

  concatVideos(allFiles, outputPath);

  const outputSize = readFileSync(outputPath).length;
  console.log(`\n✓ Video final: ${outputPath}`);
  console.log(`  Tamaño: ${(outputSize / 1024 / 1024).toFixed(1)} MB`);
  console.log(`  Estructura: Intro 2s → ${inputPaths.length} clip(s) → CTA 5s`);

  // 4. Cleanup: borrar videos originales pesados
  if (cleanup) {
    console.log("\nLimpiando videos originales...");
    let totalFreed = 0;
    for (const p of inputPaths) {
      try {
        const size = statSync(p).size;
        unlinkSync(p);
        totalFreed += size;
        console.log(`  ✓ Borrado: ${basename(p)} (${(size / 1024 / 1024).toFixed(1)} MB)`);
      } catch (e) {
        console.log(`  ✗ No se pudo borrar: ${basename(p)} (${e.message})`);
      }
    }
    console.log(`  Total liberado: ${(totalFreed / 1024 / 1024).toFixed(1)} MB`);
  }
}

main().catch((err) => {
  console.error("Error:", err.message);
  if (err.stderr) console.error(err.stderr.slice(0, 1000));
  process.exit(1);
});
