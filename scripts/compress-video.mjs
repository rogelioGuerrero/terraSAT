/**
 * compress-video.mjs — Comprime videos usando ffmpeg-static + fluent-ffmpeg
 *
 * Reduce peso de videos MP4 para web:
 * - Re-encode con H.264, CRF 28 (balance calidad/peso)
 * - Resize manteniendo aspect ratio
 * - FPS limitado a 24
 * - Audio removido (videos de fondo mudos)
 * - +faststart para streaming progresivo
 *
 * Uso: node scripts/compress-video.mjs "<input.mp4>" [--output "<output.mp4>"] [--width 1280] [--crf 28]
 */

import { existsSync, statSync } from "fs";
import { resolve, dirname, join, basename, extname } from "path";
import ffmpegPath from "ffmpeg-static";
import ffmpeg from "fluent-ffmpeg";

ffmpeg.setFfmpegPath(ffmpegPath);

const args = process.argv.slice(2);
if (!args[0] || args[0] === "--help" || args[0] === "-h") {
  console.log('Uso: node scripts/compress-video.mjs "<input.mp4>" [--output "<ruta>"] [--width 1280] [--crf 28]');
  process.exit(0);
}

const inputPath = resolve(args[0]);
let outputPath = null;
let targetWidth = 1280;
let crf = 28;

for (let i = 1; i < args.length; i++) {
  if (args[i] === "--output" && args[i + 1]) {
    outputPath = resolve(args[i + 1]);
    i++;
  } else if (args[i] === "--width" && args[i + 1]) {
    targetWidth = parseInt(args[i + 1]);
    i++;
  } else if (args[i] === "--crf" && args[i + 1]) {
    crf = parseInt(args[i + 1]);
    i++;
  }
}

if (!existsSync(inputPath)) {
  console.error(`Error: no existe ${inputPath}`);
  process.exit(1);
}

if (!outputPath) {
  const dir = dirname(inputPath);
  const name = basename(inputPath, extname(inputPath));
  outputPath = join(dir, `${name}-compressed.mp4`);
}

const inputSize = statSync(inputPath).size;
console.log(`Comprimiendo: ${inputPath}`);
console.log(`Tamaño original: ${(inputSize / 1024 / 1024).toFixed(1)} MB`);
console.log(`Config: ${targetWidth}px, CRF ${crf}, 24fps, sin audio`);

ffmpeg(inputPath)
  .outputOptions([
    `-vf scale=${targetWidth}:-2`,
    "-r 24",
    "-c:v libx264",
    "-preset medium",
    `-crf ${crf}`,
    "-an",
    "-movflags +faststart",
    "-y",
  ])
  .output(outputPath)
  .on("end", () => {
    const outputSize = statSync(outputPath).size;
    const reduction = Math.round((1 - outputSize / inputSize) * 100);
    console.log(`\nVideo comprimido: ${outputPath}`);
    console.log(`${(inputSize / 1024 / 1024).toFixed(1)} MB → ${(outputSize / 1024 / 1024).toFixed(1)} MB (${reduction}% reducción)`);
  })
  .on("error", (err) => {
    console.error("Error:", err.message);
    process.exit(1);
  })
  .run();
