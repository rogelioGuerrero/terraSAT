/**
 * pexels-utils.mjs — Helpers compartidos para la API de Pexels
 *
 * Centraliza:
 * - Carga de PEXELS_API_KEY desde .env
 * - Peticiones con control de errores
 * - Selección del mejor archivo HD (evita 4K innecesarios)
 * - Metadatos normalizados para TerraSAT
 */

import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

// Cargar .env desde la raíz del repo (Node.js 22+).
// Si no existe o ya está cargado, se ignora el error.
try {
  process.loadEnvFile(join(ROOT, ".env"));
} catch (err) {
  // .env no encontrado o ya procesado; confiamos en process.env.
}

export const PEXELS_API_KEY = process.env.PEXELS_API_KEY;

/**
 * Lanza una petición a la API de Pexels con autorización y control de errores.
 */
export async function fetchPexels(url) {
  if (!PEXELS_API_KEY) {
    throw new Error("PEXELS_API_KEY no configurada. Añádela al archivo .env");
  }
  const res = await fetch(url, {
    headers: { Authorization: PEXELS_API_KEY },
  });
  if (!res.ok) {
    throw new Error(`Pexels API error ${res.status}: ${res.statusText}`);
  }
  const data = await res.json();
  if (!data || typeof data !== "object") {
    throw new Error("Respuesta JSON inválida de Pexels");
  }
  return data;
}

function isDownloadable(f) {
  return (
    f &&
    f.file_type === "video/mp4" &&
    typeof f.width === "number" &&
    f.width > 0 &&
    typeof f.height === "number" &&
    f.height > 0 &&
    typeof f.link === "string" &&
    f.link.startsWith("http")
  );
}

/**
 * Selecciona el mejor archivo HD para descargar.
 * Prioridad: el más pequeño con ancho >= targetWidth, evitando descargar 4K innecesarios.
 */
export function pickBestVideoFile(video, { targetWidth = 1920, minWidth = 1280, maxWidth = 3840 } = {}) {
  if (!video || !Array.isArray(video.video_files) || video.video_files.length === 0) {
    throw new Error(`Video ${video?.id} no tiene archivos disponibles`);
  }

  const hd = video.video_files
    .filter(f => f.quality === "hd" && isDownloadable(f) && f.width >= minWidth && f.width <= maxWidth)
    .sort((a, b) => a.width - b.width);

  let selected = null;
  for (const f of hd) {
    if (f.width >= targetWidth) {
      selected = f;
      break;
    }
  }
  if (!selected && hd.length > 0) {
    selected = hd[hd.length - 1];
  }

  if (!selected) {
    const anyHd = video.video_files.find(f => f.quality === "hd" && isDownloadable(f));
    if (anyHd) selected = anyHd;
  }

  if (!selected) {
    selected = video.video_files.find(f => isDownloadable(f));
  }

  if (!selected) {
    throw new Error(`No hay archivo descargable para el video ${video.id}`);
  }
  return selected;
}

/**
 * Selecciona un archivo pequeño para previsualizar en el sandbox.
 */
export function pickPreviewFile(video) {
  const files = (video.video_files || []).filter(isDownloadable);
  if (files.length === 0) throw new Error(`No hay preview disponible para el video ${video.id}`);

  const sd = files.filter(f => f.quality === "sd");
  if (sd.length) {
    const small = sd.find(f => f.width <= 640) || sd.sort((a, b) => a.width - b.width)[0];
    return small;
  }

  const hd = files
    .filter(f => f.quality === "hd" && f.width <= 1280)
    .sort((a, b) => a.width - b.width);
  if (hd.length) return hd[0];

  return files.sort((a, b) => a.width - b.width)[0];
}

/**
 * Devuelve metadatos normalizados de un video de Pexels.
 */
export function toClipMetadata(video) {
  const best = pickBestVideoFile(video);
  const preview = pickPreviewFile(video);
  return {
    id: video.id,
    duration: video.duration,
    downloadUrl: best.link,
    previewUrl: preview.link,
    posterUrl: video.image,
    width: best.width,
    height: best.height,
  };
}

/**
 * Busca videos en Pexels y devuelve los videos brutos (sin mapear a metadatos).
 */
export async function searchPexelsVideos(query, { perPage = 15, maxDuration = 15, orientation = "landscape" } = {}) {
  const url = `https://api.pexels.com/videos/search?query=${encodeURIComponent(query)}&per_page=${perPage}&orientation=${orientation}`;
  const data = await fetchPexels(url);
  const videos = Array.isArray(data.videos) ? data.videos : [];
  const pool = videos.filter(v => typeof v.duration === "number" && v.duration <= maxDuration && Array.isArray(v.video_files) && v.video_files.length > 0);
  return pool.length > 0 ? pool : videos;
}
