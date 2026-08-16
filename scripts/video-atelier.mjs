/**
 * video-atelier.mjs — Orquestador del pipeline de video TerraSAT
 *
 * Dos fases con human-in-the-loop:
 * Fase 1 — EXPLORAR: El humano busca en Pexels desde el sandbox (barra de búsqueda),
 *           ve previews del CDN, marca los clips que le gustan (se guardan por ID)
 * Fase 2 — ORDENAR: De los clips marcados, asigna orden de aparición y genera
 *           Solo se descargan los clips elegidos → comprimir → cards → branding → ensamblar
 *
 * Uso:
 *   node scripts/video-atelier.mjs [--cta "texto"] [--output path]
 *   node scripts/video-atelier.mjs --query "agriculture aerial" [--count 5] [--cta "texto"]
 */

import { existsSync, mkdirSync, writeFileSync, unlinkSync, statSync } from "fs";
import { resolve, join, dirname, basename } from "path";
import { execFileSync } from "child_process";
import ffmpegStatic from "ffmpeg-static";
import ffmpeg from "fluent-ffmpeg";
import { fileURLToPath } from "url";
import http from "http";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const FFMPEG = ffmpegStatic;
ffmpeg.setFfmpegPath(FFMPEG);

const PEXELS_KEY = "cn1L5H2haPcdyVqVVQHSiHv7cESwnxIbnFW5cTFes6BHwXjqcwqi0t4E";
const ATELIER_DIR = resolve(ROOT, "scripts", ".atelier");

// ── Args ──
const args = process.argv.slice(2);
if (args[0] === "--help" || args[0] === "-h") {
  console.log('Uso: node scripts/video-atelier.mjs [--cta "texto"] [--output path]');
  console.log('      node scripts/video-atelier.mjs --query "agriculture aerial" [--count 5] [--cta "texto"]');
  console.log("");
  console.log("Fase 1: Explorar — buscas en Pexels desde el sandbox, marcas los que te gustan");
  console.log("Fase 2: Ordenar — asignas orden a los marcados y generas el video final");
  process.exit(0);
}

let initialQuery = "";
let maxCount = 10;
let ctaText = "";
let outputPath = null;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--query" && args[i + 1]) { initialQuery = args[i + 1]; i++; }
  else if (args[i] === "--count" && args[i + 1]) { maxCount = parseInt(args[i + 1]); i++; }
  else if (args[i] === "--cta" && args[i + 1]) { ctaText = args[i + 1]; i++; }
  else if (args[i] === "--output" && args[i + 1]) { outputPath = resolve(args[i + 1]); i++; }
}

if (!outputPath) {
  outputPath = join(ATELIER_DIR, "terrasat-video-final.mp4");
}

// ── Helpers ──

async function searchVideos(query, perPage = 15) {
  const url = `https://api.pexels.com/videos/search?query=${encodeURIComponent(query)}&per_page=${perPage}&orientation=landscape`;
  const res = await fetch(url, { headers: { Authorization: PEXELS_KEY } });
  const data = await res.json();

  const suitable = data.videos.filter(
    v => v.duration <= 15 && v.video_files.some(f => f.quality === "hd" && f.width === 1920)
  );
  const pool = suitable.length > 0 ? suitable : data.videos;

  return pool.slice(0, maxCount).map(v => {
    const hdFile = v.video_files.find(f => f.quality === "hd" && f.width === 1920)
      || v.video_files.find(f => f.quality === "hd")
      || v.video_files[0];
    const previewFile = v.video_files.find(f => f.quality === "sd" && f.width <= 640)
      || v.video_files.find(f => f.quality === "sd")
      || hdFile;
    return {
      id: v.id,
      duration: v.duration,
      downloadUrl: hdFile.link,
      previewUrl: previewFile.link,
      posterUrl: v.image,
      width: hdFile.width,
      height: hdFile.height,
    };
  });
}

async function downloadFile(url, path) {
  const res = await fetch(url);
  const buffer = Buffer.from(await res.arrayBuffer());
  writeFileSync(path, buffer);
  return buffer.length;
}

function compressVideo(inputPath, outPath, width = 1280, crf = 30) {
  return new Promise((resolveP, reject) => {
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
      .output(outPath)
      .on("end", resolveP)
      .on("error", reject)
      .run();
  });
}

// ── Generar HTML sandbox (dos fases: explorar + ordenar) ──
function generateSandboxHTML(cta, initialQuery) {
  return `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TerraSAT — Video Atelier</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0a1a14;
    color: #e0e0e0;
    min-height: 100vh;
    padding: 20px;
  }
  header {
    text-align: center;
    margin-bottom: 20px;
    padding: 20px;
    background: linear-gradient(135deg, #0d4f3c, #064e3b);
    border-radius: 12px;
  }
  header h1 { color: #6ee7b7; font-size: 1.8rem; letter-spacing: 2px; }
  header p { color: #a7f3d0; margin-top: 8px; font-size: 0.9rem; }
  .search-bar {
    max-width: 1400px;
    margin: 0 auto 20px;
    display: flex;
    gap: 10px;
  }
  .search-bar input {
    flex: 1;
    background: #1f2937;
    border: 1px solid #374151;
    color: #e0e0e0;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 1rem;
  }
  .search-bar button {
    background: #059669;
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 1rem;
    cursor: pointer;
  }
  .search-bar button:hover { background: #047857; }
  .search-bar button:disabled { background: #374151; cursor: not-allowed; }
  .phase-label {
    max-width: 1400px;
    margin: 0 auto 10px;
    font-size: 0.9rem;
    color: #6ee7b7;
    font-weight: 600;
    letter-spacing: 1px;
  }
  .clips-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
    max-width: 1400px;
    margin: 0 auto;
  }
  .clip-card {
    background: #111827;
    border: 2px solid #1f2937;
    border-radius: 10px;
    overflow: hidden;
    transition: border-color 0.2s, transform 0.2s;
  }
  .clip-card:hover { border-color: #059669; transform: translateY(-2px); }
  .clip-card.marked { border-color: #10b981; box-shadow: 0 0 12px rgba(16,185,129,0.3); }
  .clip-video {
    width: 100%;
    aspect-ratio: 16/9;
    object-fit: cover;
    display: block;
    background: #000;
  }
  .clip-info {
    padding: 10px 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .clip-info .meta { font-size: 0.8rem; color: #6b7280; }
  .clip-info .mark-btn {
    background: #1f2937;
    border: 1px solid #374151;
    color: #9ca3af;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.2s;
  }
  .clip-info .mark-btn:hover { border-color: #059669; color: #6ee7b7; }
  .clip-info .mark-btn.marked { background: #059669; color: white; border-color: #059669; }
  .clip-info .order-input {
    width: 50px;
    background: #1f2937;
    border: 1px solid #374151;
    color: #e0e0e0;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.9rem;
    text-align: center;
  }
  .clip-info label { font-size: 0.85rem; color: #9ca3af; display: flex; align-items: center; gap: 6px; }
  .marked-section {
    max-width: 1400px;
    margin: 30px auto 0;
    padding: 20px;
    background: #111827;
    border-radius: 10px;
    display: none;
  }
  .marked-section.visible { display: block; }
  .marked-section h2 { color: #6ee7b7; font-size: 1.2rem; margin-bottom: 15px; }
  .controls {
    max-width: 1400px;
    margin: 20px auto;
    padding: 20px;
    background: #111827;
    border-radius: 10px;
  }
  .controls .row { display: flex; gap: 15px; align-items: center; flex-wrap: wrap; margin-bottom: 15px; }
  .controls label { font-size: 0.9rem; color: #9ca3af; }
  .controls input[type="text"] {
    flex: 1;
    min-width: 300px;
    background: #1f2937;
    border: 1px solid #374151;
    color: #e0e0e0;
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 0.9rem;
  }
  .controls button {
    background: #059669;
    color: white;
    border: none;
    padding: 12px 28px;
    border-radius: 6px;
    font-size: 1rem;
    cursor: pointer;
    transition: background 0.2s;
  }
  .controls button:hover { background: #047857; }
  .controls button:disabled { background: #374151; cursor: not-allowed; }
  .status {
    text-align: center;
    padding: 12px;
    margin-top: 10px;
    border-radius: 6px;
    font-size: 0.9rem;
    display: none;
  }
  .status.success { display: block; background: #064e3b; color: #6ee7b7; }
  .status.error { display: block; background: #7f1d1d; color: #fca5a5; }
  .status.progress { display: block; background: #1e3a5f; color: #93c5fd; }
  .video-preview {
    margin-top: 15px;
    text-align: center;
    display: none;
  }
  .video-preview video {
    max-width: 800px;
    width: 100%;
    border-radius: 8px;
  }
  .hint {
    max-width: 1400px;
    margin: 0 auto 15px;
    padding: 12px 16px;
    background: #0d4f3c;
    border-radius: 8px;
    font-size: 0.85rem;
    color: #a7f3d0;
  }
  .badge {
    display: inline-block;
    background: #059669;
    color: white;
    border-radius: 50%;
    width: 22px;
    height: 22px;
    text-align: center;
    line-height: 22px;
    font-size: 0.75rem;
    font-weight: bold;
    margin-left: 6px;
  }
  .loading { text-align: center; padding: 40px; color: #6b7280; font-size: 1.1rem; }
  .empty { text-align: center; padding: 40px; color: #4b5563; font-size: 0.9rem; }
</style>
</head>
<body>

<header>
  <h1>TerraSAT Video Atelier</h1>
  <p>Fase 1: Explora y marca · Fase 2: Ordena y genera</p>
</header>

<div class="search-bar">
  <input type="text" id="searchInput" placeholder="Buscar videos en Pexels... (ej: aerial drone agriculture, city timelapse, forest satellite)" value="${initialQuery.replace(/"/g, '&quot;')}" onkeydown="if(event.key==='Enter')doSearch()">
  <button id="searchBtn" onclick="doSearch()">🔍 Buscar</button>
</div>

<div class="phase-label">FASE 1 — Explorar (marca los que te gusten)</div>
<div class="hint" id="browseHint">
  <strong>Instrucciones:</strong> Busca con diferentes términos. Dale play a los clips para previsualizar (streaming de Pexels).
  Clic en "Marcar" para guardar los que te gusten. Puedes buscar varias veces con diferentes queries.
</div>
<div class="clips-grid" id="resultsGrid">
  <div class="empty">Escribe un término de búsqueda y haz clic en Buscar</div>
</div>

<div class="marked-section" id="markedSection">
  <h2>⭐ Clips marcados (<span id="markedCount">0</span>)</h2>
  <div class="clips-grid" id="markedGrid"></div>
</div>

<div class="controls">
  <div class="phase-label">FASE 2 — Ordenar y generar</div>
  <div class="hint">
    Asigna número de orden (1, 2, 3...) a los clips marcados. Solo los que tengan orden se descargan y ensamblan.
  </div>
  <div class="row">
    <label>CTA:</label>
    <input type="text" id="ctaInput" value="${cta.replace(/"/g, '&quot;')}" placeholder="Ej: Observación satelital para Latinoamérica">
  </div>
  <div class="row">
    <button onclick="generate()">🎬 Generar Video Final</button>
  </div>
  <div class="status" id="status"></div>
  <div class="video-preview" id="preview">
    <video controls></video>
  </div>
</div>

<script>
  const marked = new Map(); // id -> clip data

  const allClips = new Map(); // id -> clip data (de todas las búsquedas)

  async function doSearch() {
    const input = document.getElementById('searchInput');
    const btn = document.getElementById('searchBtn');
    const grid = document.getElementById('resultsGrid');
    const q = input.value.trim();
    if (!q) return;

    btn.disabled = true;
    btn.textContent = 'Buscando...';
    grid.innerHTML = '<div class="loading">Buscando en Pexels...</div>';

    try {
      const res = await fetch('/search?q=' + encodeURIComponent(q));
      const data = await res.json();
      if (data.clips.length === 0) {
        grid.innerHTML = '<div class="empty">No se encontraron videos para "' + q + '"</div>';
      } else {
        data.clips.forEach(c => allClips.set(c.id, c));
        renderResults(data.clips);
      }
    } catch (e) {
      grid.innerHTML = '<div class="empty">Error: ' + e.message + '</div>';
    }
    btn.disabled = false;
    btn.textContent = '🔍 Buscar';
  }

  function renderResults(clips) {
    const grid = document.getElementById('resultsGrid');
    grid.innerHTML = clips.map(c => {
      const isMarked = marked.has(c.id);
      return \`<div class="clip-card \${isMarked ? 'marked' : ''}" id="result-\${c.id}">
      <video class="clip-video" preload="none" poster="\${c.posterUrl}" controls muted loop>
        <source src="\${c.previewUrl}" type="video/mp4">
      </video>
      <div class="clip-info">
        <div class="meta">ID \${c.id} · \${c.duration}s · \${c.width}x\${c.height}</div>
        <button class="mark-btn \${isMarked ? 'marked' : ''}" onclick="toggleMark(\${c.id})">\${isMarked ? '✓ Marcado' : '☆ Marcar'}</button>
      </div>
    </div>\`;
    }).join('');
  }

  function toggleMark(id) {
    const card = document.getElementById('result-' + id);
    if (!card) return;

    if (marked.has(id)) {
      marked.delete(id);
      card.classList.remove('marked');
      card.querySelector('.mark-btn').classList.remove('marked');
      card.querySelector('.mark-btn').textContent = '☆ Marcar';
    } else {
      const clipData = allClips.get(id);
      if (!clipData) return;
      marked.set(id, clipData);
      card.classList.add('marked');
      card.querySelector('.mark-btn').classList.add('marked');
      card.querySelector('.mark-btn').textContent = '✓ Marcado';
    }
    renderMarked();
  }

  function renderMarked() {
    const section = document.getElementById('markedSection');
    const grid = document.getElementById('markedGrid');
    const count = document.getElementById('markedCount');
    count.textContent = marked.size;

    if (marked.size === 0) {
      section.classList.remove('visible');
      return;
    }
    section.classList.add('visible');

    const clips = Array.from(marked.values());
    grid.innerHTML = clips.map((c, i) => \`<div class="clip-card marked" id="marked-\${c.id}">
      <video class="clip-video" preload="none" poster="\${c.posterUrl}" controls muted loop>
        <source src="\${c.previewUrl}" type="video/mp4">
      </video>
      <div class="clip-info">
        <div class="meta">ID \${c.id} · \${c.duration}s<span class="badge" id="badge-\${c.id}" style="display:none"></span></div>
        <label>Orden: <input type="number" class="order-input" id="order-\${c.id}" min="1" max="\${clips.length}" oninput="updateBadge(\${c.id})"></label>
      </div>
    </div>\`).join('');
  }

  function updateBadge(id) {
    const input = document.getElementById('order-' + id);
    const badge = document.getElementById('badge-' + id);
    const order = parseInt(input.value);
    if (order > 0) {
      badge.textContent = order;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  }

  async function generate() {
    const status = document.getElementById('status');
    const btn = document.querySelector('.controls button');

    const ordered = [];
    for (const [id, clip] of marked) {
      const orderVal = parseInt(document.getElementById('order-' + id)?.value || '0');
      if (orderVal > 0) {
        ordered.push({ clip: { id: clip.id, duration: clip.duration, downloadUrl: clip.downloadUrl, width: clip.width, height: clip.height }, order: orderVal });
      }
    }

    if (ordered.length === 0) {
      status.className = 'status error';
      status.textContent = 'Error: asigna un número de orden a al menos un clip marcado';
      return;
    }

    ordered.sort((a, b) => a.order - b.order);
    const cta = document.getElementById('ctaInput').value.trim();

    const selection = {
      clips: ordered.map(o => o.clip),
      cta: cta,
      timestamp: new Date().toISOString(),
    };

    btn.disabled = true;
    status.className = 'status progress';
    status.textContent = '⏳ Descargando ' + ordered.length + ' clips y ensamblando... (esto toma unos minutos)';
    status.style.display = 'block';

    try {
      const res = await fetch('/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(selection),
      });
      const result = await res.json();

      if (result.ok) {
        status.className = 'status success';
        status.textContent = '✓ Video generado: ' + result.output + ' (' + result.sizeMB + ' MB)';
        const preview = document.getElementById('preview');
        preview.style.display = 'block';
        preview.querySelector('video').src = '/video/' + encodeURIComponent(result.output.split(/[\\/]/).pop());
      } else {
        status.className = 'status error';
        status.textContent = '✗ Error: ' + result.error;
      }
    } catch (e) {
      status.className = 'status error';
      status.textContent = '✗ Error de conexión: ' + e.message;
    }
    btn.disabled = false;
    btn.textContent = '🎬 Generar Video Final';
  }

  // Auto-búsqueda inicial si hay query
  if (document.getElementById('searchInput').value) {
    doSearch();
  }
</script>

</body>
</html>`;
}

// ── Servidor HTTP del sandbox ──
function startSandboxServer(cta, initialQuery) {
  return new Promise((resolveServer) => {
    const html = generateSandboxHTML(cta, initialQuery);

    const server = http.createServer(async (req, res) => {
      if (req.method === "GET" && (req.url === "/" || req.url === "/index.html")) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(html);
        return;
      }

      // API: buscar en Pexels
      if (req.method === "GET" && req.url.startsWith("/search?")) {
        const urlObj = new URL(req.url, "http://localhost");
        const q = urlObj.searchParams.get("q") || "";
        if (!q) {
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ clips: [] }));
          return;
        }
        try {
          const clips = await searchVideos(q, maxCount);
          console.log(`  Búsqueda "${q}": ${clips.length} resultados`);
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ clips }));
        } catch (e) {
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ clips: [], error: e.message }));
        }
        return;
      }

      if (req.method === "POST" && req.url === "/submit") {
        let body = "";
        req.on("data", chunk => body += chunk);
        req.on("end", async () => {
          try {
            const selection = JSON.parse(body);
            console.log("\n✓ Selección recibida del humano");
            console.log(`  Clips: ${selection.clips.length}`);
            console.log(`  CTA: "${selection.cta}"`);

            res.writeHead(200, { "Content-Type": "application/json" });

            try {
              const result = await downloadAndAssemble(selection);
              res.end(JSON.stringify({ ok: true, output: result.path, sizeMB: result.sizeMB }));
            } catch (e) {
              console.error("Error ensamblando:", e.message);
              res.end(JSON.stringify({ ok: false, error: e.message }));
            }
          } catch (e) {
            res.writeHead(200, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ ok: false, error: e.message }));
          }
        });
        return;
      }

      // Servir video final
      if (req.method === "GET" && req.url.startsWith("/video/")) {
        const fileName = decodeURIComponent(req.url.slice(7));
        const filePath = join(ATELIER_DIR, fileName);
        if (existsSync(filePath)) {
          const stat = statSync(filePath);
          const fileSize = stat.size;
          const range = req.headers.range;

          if (range) {
            const parts = range.replace(/bytes=/, "").split("-");
            const start = parseInt(parts[0], 10);
            const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
            const chunksize = (end - start) + 1;
            const { createReadStream } = await import("fs");
            const stream = createReadStream(filePath, { start, end });
            res.writeHead(206, {
              "Content-Range": `bytes ${start}-${end}/${fileSize}`,
              "Accept-Ranges": "bytes",
              "Content-Length": chunksize,
              "Content-Type": "video/mp4",
            });
            stream.pipe(res);
          } else {
            res.writeHead(200, { "Content-Length": fileSize, "Content-Type": "video/mp4" });
            const { createReadStream } = await import("fs");
            createReadStream(filePath).pipe(res);
          }
          return;
        }
      }

      res.writeHead(404);
      res.end("Not found");
    });

    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      resolveServer({ server, port });
    });
  });
}

// ── Descargar, comprimir y ensamblar (solo clips seleccionados) ──
async function downloadAndAssemble(selection) {
  const { clips: selectedClips, cta } = selection;

  // 1. Descargar y comprimir solo los seleccionados
  console.log("\n── Descargando y comprimiendo clips seleccionados ──");
  const compressedPaths = [];

  for (let i = 0; i < selectedClips.length; i++) {
    const c = selectedClips[i];
    console.log(`\n[${i + 1}/${selectedClips.length}] Video ${c.id} (${c.duration}s)`);

    const rawPath = join(ATELIER_DIR, `clip-${i}-raw.mp4`);
    const rawSize = await downloadFile(c.downloadUrl, rawPath);
    console.log(`  Descargado: ${(rawSize / 1024 / 1024).toFixed(1)} MB`);

    const compressedPath = join(ATELIER_DIR, `clip-${i}.mp4`);
    await compressVideo(rawPath, compressedPath, 1280, 30);
    const compressedSize = statSync(compressedPath).size;
    console.log(`  Comprimido: ${(rawSize / 1024 / 1024).toFixed(1)} MB → ${(compressedSize / 1024 / 1024).toFixed(1)} MB`);

    unlinkSync(rawPath);
    console.log(`  Raw eliminado`);

    compressedPaths.push(compressedPath);
  }

  // 2. Generar cards con el CTA
  console.log("\n── Generando cards (intro + CTA) ──");
  const cardsArgs = ["scripts/gen-cards-terrasat.mjs", "--ref", compressedPaths[0]];
  if (cta) cardsArgs.push("--cta", cta);

  execFileSync("node", cardsArgs, { encoding: "utf8", stdio: "inherit", cwd: ROOT });
  console.log("✓ Cards generados");

  // 3. Ensamblar con branding
  console.log("\n── Ensamblando video final ──");
  const brandingArgs = [
    "scripts/add-branding-video-terrasat.mjs",
    ...compressedPaths,
    "--output", outputPath,
    "--cleanup",
  ];

  execFileSync("node", brandingArgs, { encoding: "utf8", stdio: "inherit", cwd: ROOT });

  const finalSize = statSync(outputPath).size;
  const sizeMB = (finalSize / 1024 / 1024).toFixed(1);
  console.log(`\n✓ Video final: ${outputPath}`);
  console.log(`  Tamaño: ${sizeMB} MB`);

  return { path: outputPath, sizeMB };
}

// ── Main ──
async function main() {
  if (!existsSync(ATELIER_DIR)) mkdirSync(ATELIER_DIR, { recursive: true });

  console.log("═══════════════════════════════════════════");
  console.log("  TerraSAT Video Atelier");
  console.log("═══════════════════════════════════════════\n");
  console.log(`Query inicial: ${initialQuery || "(ninguna — buscar desde el sandbox)"}`);
  console.log(`Máximo por búsqueda: ${maxCount}`);
  console.log(`CTA: ${ctaText || "(editable en sandbox)"}\n`);

  // Sandbox HTML con barra de búsqueda integrada
  console.log("── Iniciando sandbox ──");
  const { server, port } = await startSandboxServer(ctaText || "Observación satelital para Latinoamérica", initialQuery);

  const sandboxUrl = `http://127.0.0.1:${port}`;
  console.log(`\n╔═══════════════════════════════════════════════╗`);
  console.log(`║  SANDBOX LISTO                                 ║`);
  console.log(`╚═══════════════════════════════════════════════╝`);
  console.log(`\n  Abre en tu navegador:`);
  console.log(`  ${sandboxUrl}`);
  console.log(`\n  FASE 1: Busca con diferentes términos, dale play, marca los que te gusten.`);
  console.log(`  FASE 2: Asigna orden a los marcados, escribe el CTA, y genera.`);
  console.log(`\n  Solo se descargan los clips que marques y ordenes.`);
  console.log(`\n  Esperando selección del humano...`);

  // Abrir navegador automáticamente
  try {
    if (process.platform === "win32") {
      execFileSync("cmd", ["/c", "start", sandboxUrl], { stdio: "ignore" });
    }
  } catch {}

  // Esperar a que el humano termine (el servidor maneja todo)
  // Mantener el proceso vivo
  process.on("SIGINT", () => {
    console.log("\nCerrando atelier...");
    server.close();
    process.exit(0);
  });

  // El servidor corre indefinidamente hasta que el usuario cierre
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
