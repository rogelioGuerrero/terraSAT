/**
 * fetch-pexels-videos.mjs — Busca y descarga videos de Pexels para cada informe
 *
 * Usa la API de Pexels para buscar videos relevantes por tema,
 * descarga el mejor resultado en 1080p, lo comprime con ffmpeg,
 * y extrae un frame como poster.
 *
 * Requiere: PEXELS_API_KEY en variables de entorno
 * Uso: node scripts/fetch-pexels-videos.mjs
 */

import { existsSync, statSync, writeFileSync, mkdirSync } from "fs";
import { resolve, join } from "path";
import ffmpegPath from "ffmpeg-static";
import ffmpeg from "fluent-ffmpeg";
import { fileURLToPath } from "url";
import { dirname } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

ffmpeg.setFfmpegPath(ffmpegPath);

const PEXELS_KEY = "cn1L5H2haPcdyVqVVQHSiHv7cESwnxIbnFW5cTFes6BHwXjqcwqi0t4E";

// Informes que necesitan video
const informes = [
  { id: "7", query: "agriculture coffee farm aerial drone", file: "informe-agrosat-crisis" },
  { id: "1", query: "coffee plantation green farm aerial", file: "informe-coffee" },
  { id: "2", query: "city urban aerial traffic timelapse", file: "informe-urban-heat" },
  { id: "3", query: "soybean agriculture field aerial drone", file: "informe-soybean" },
  { id: "4", query: "city urban expansion construction aerial", file: "informe-urban-sprawl" },
  { id: "5", query: "coffee plantation mountain hill aerial", file: "informe-coffee-hill" },
  { id: "6", query: "city trees park green aerial drone", file: "informe-urban-trees" },
];

const ASSETS_DIR = resolve(ROOT, "web", "src", "assets");

async function searchVideo(query) {
  const url = `https://api.pexels.com/videos/search?query=${encodeURIComponent(query)}&per_page=10&orientation=landscape`;
  const res = await fetch(url, {
    headers: { Authorization: PEXELS_KEY },
  });
  const data = await res.json();

  // Preferir videos cortos (<=15s) con 1080p
  const suitable = data.videos.filter(
    (v) => v.duration <= 15 && v.video_files.some((f) => f.quality === "hd" && f.width === 1920)
  );

  const pool = suitable.length > 0 ? suitable : data.videos;
  if (pool.length === 0) return null;

  const video = pool[0];
  const hdFile = video.video_files.find((f) => f.quality === "hd" && f.width === 1920)
    || video.video_files.find((f) => f.quality === "hd")
    || video.video_files[0];

  return {
    id: video.id,
    duration: video.duration,
    downloadUrl: hdFile.link,
    posterUrl: video.image,
  };
}

async function downloadFile(url, path) {
  const res = await fetch(url);
  const buffer = Buffer.from(await res.arrayBuffer());
  writeFileSync(path, buffer);
  return buffer.length;
}

function compressVideo(inputPath, outputPath, width = 1280, crf = 30) {
  return new Promise((resolve, reject) => {
    ffmpeg(inputPath)
      .outputOptions([
        `-vf scale=${width}:-2`,
        "-r 24",
        "-c:v libx264",
        "-preset medium",
        `-crf ${crf}`,
        "-an",
        "-movflags +faststart",
        "-y",
      ])
      .output(outputPath)
      .on("end", resolve)
      .on("error", reject)
      .run();
  });
}

function extractPoster(inputPath, outputPath, width = 1280) {
  return new Promise((resolve, reject) => {
    ffmpeg(inputPath)
      .outputOptions([
        `-vf scale=${width}:-2`,
        "-frames:v 1",
        "-q:v 5",
        "-y",
      ])
      .output(outputPath)
      .on("end", resolve)
      .on("error", reject)
      .run();
  });
}

async function processInforme(inf) {
  console.log(`\n--- Informe ${inf.id}: ${inf.file} ---`);
  console.log(`Buscando: "${inf.query}"...`);

  const result = await searchVideo(inf.query);
  if (!result) {
    console.log(`  No se encontraron videos para "${inf.query}"`);
    return;
  }

  console.log(`  Encontrado: video ${result.id} (${result.duration}s)`);

  // Descargar video original
  const rawPath = join(ASSETS_DIR, `${inf.file}-raw.mp4`);
  const rawSize = await downloadFile(result.downloadUrl, rawPath);
  console.log(`  Descargado: ${(rawSize / 1024 / 1024).toFixed(1)} MB`);

  // Comprimir
  const optPath = join(ASSETS_DIR, `${inf.file}-video-opt.mp4`);
  await compressVideo(rawPath, optPath, 1280, 30);
  const optSize = statSync(optPath).size;
  console.log(`  Comprimido: ${(rawSize / 1024 / 1024).toFixed(1)} MB → ${(optSize / 1024 / 1024).toFixed(1)} MB`);

  // Extraer poster
  const posterPath = join(ASSETS_DIR, `${inf.file}-video-poster.jpg`);
  await extractPoster(optPath, posterPath, 1280);
  console.log(`  Poster extraído`);

  // Limpiar raw
  const { unlinkSync } = await import("fs");
  unlinkSync(rawPath);
  console.log(`  Raw eliminado`);
}

async function main() {
  if (!existsSync(ASSETS_DIR)) {
    mkdirSync(ASSETS_DIR, { recursive: true });
  }

  console.log("Buscando y descargando videos de Pexels...");
  console.log(`Total: ${informes.length} informes`);

  for (const inf of informes) {
    try {
      await processInforme(inf);
    } catch (err) {
      console.error(`  Error en informe ${inf.id}: ${err.message}`);
    }
  }

  console.log("\nDone!");
}

main();
