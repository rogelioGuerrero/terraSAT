/**
 * agrosat-crisis-overlay.mjs — Compone foto Unsplash + panel de datos semáforo regional
 *
 * Toma una foto real de paisaje agrícola y le superpone un panel SVG con
 * las cifras clave del análisis 2024 vs 2026 de AgroSAT.
 *
 * Uso: node scripts/agrosat-crisis-overlay.mjs "<foto>" [--output "<ruta>"]
 */

import sharp from "sharp";
import { existsSync, writeFileSync } from "fs";
import { resolve, dirname, join, basename, extname } from "path";

const args = process.argv.slice(2);
if (!args[0] || args[0] === "--help" || args[0] === "-h") {
  console.log('Uso: node scripts/agrosat-crisis-overlay.mjs "<foto>" [--output "<ruta>"]');
  process.exit(0);
}

const inputPath = resolve(args[0]);
let outputPath = null;

for (let i = 1; i < args.length; i++) {
  if (args[i] === "--output" && args[i + 1]) {
    outputPath = resolve(args[i + 1]);
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
  outputPath = join(dir, `${name}-overlay.jpg`);
}

// ── Datos del análisis (hardcoded del script Python) ──
const DATA = {
  totalHa: "514,000",
  pctDeterioro: "31%",
  maxImpact: "-26%",
  zonasDeclinando: 12,
  zonasTransicion: 1,
  paises: 10,
  cultivos: "Café · Soja · Maíz · Arroz · Caña",
  // Semáforo
  critico: 2,   // >-20% rendimiento
  alerta: 6,    // -8% a -20%
  vigilancia: 4, // -2% a -8%
  normal: 1,     // estable
  // Hallazgos clave
  hallazgos: [
    { zona: "Loja, Ecuador", cultivo: "Café", detalle: "En transición: migración altitudinal" },
    { zona: "Intibucá, Honduras", cultivo: "Café", detalle: "-26% rendimiento · 20,000 ha" },
    { zona: "Mato Grosso, Brasil", cultivo: "Soja", detalle: "-22% rendimiento · 135,000 ha" },
    { zona: "Chiapas, México", cultivo: "Maíz", detalle: "-25% rendimiento · 30,000 ha" },
  ],
};

function createDataPanel(width, height) {
  // Panel lateral derecho: 38% del ancho
  const panelWidth = Math.round(width * 0.38);
  const panelX = width - panelWidth;
  const padding = Math.round(panelWidth * 0.08);

  // Escala de fuentes relativa al panel
  const titleSize = Math.round(panelWidth * 0.052);
  const labelSize = Math.round(panelWidth * 0.035);
  const valueSize = Math.round(panelWidth * 0.065);
  const smallSize = Math.round(panelWidth * 0.028);
  const sectionSize = Math.round(panelWidth * 0.038);

  // Posiciones Y
  let y = padding + titleSize;

  // ─── Construir SVG del panel ───
  let svg = `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="panelGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0a0f0d" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="#0a0f0d" stop-opacity="0.95"/>
    </linearGradient>
    <linearGradient id="leftFade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0a0f0d" stop-opacity="0"/>
      <stop offset="100%" stop-color="#0a0f0d" stop-opacity="0.6"/>
    </linearGradient>
  </defs>

  <!-- Fade izquierdo del panel para suavizar transición -->
  <rect x="${panelX - 40}" y="0" width="40" height="${height}" fill="url(#leftFade)"/>

  <!-- Panel principal -->
  <rect x="${panelX}" y="0" width="${panelWidth}" height="${height}" fill="url(#panelGrad)"/>

  <!-- Línea superior verde -->
  <rect x="${panelX + padding}" y="${padding}" width="${panelWidth - padding * 2}" height="3" fill="#10b981" rx="1.5"/>

  <!-- Título -->
  <text x="${panelX + padding}" y="${y + 10}" font-family="Arial, Helvetica, sans-serif" font-size="${titleSize}" font-weight="700" fill="#ffffff">AgroSAT</text>
  <text x="${panelX + padding}" y="${y + 10 + titleSize * 1.1}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize * 1.3}" font-weight="400" fill="#10b981" opacity="0.9">Análisis satelital 2024 → 2026</text>
`;

  y += titleSize * 2.5 + padding;

  // ─── Cifras principales ───
  svg += `
  <text x="${panelX + padding}" y="${y}" font-family="Arial, Helvetica, sans-serif" font-size="${labelSize}" font-weight="400" fill="#9ca3af">Hectáreas con deterioro</text>
  <text x="${panelX + padding}" y="${y + valueSize * 0.9}" font-family="Arial, Helvetica, sans-serif" font-size="${valueSize}" font-weight="700" fill="#ef4444">${DATA.totalHa}</text>
  <text x="${panelX + padding + valueSize * 2.2}" y="${y + valueSize * 0.9}" font-family="Arial, Helvetica, sans-serif" font-size="${labelSize * 1.2}" font-weight="600" fill="#f59e0b">${DATA.pctDeterioro}</text>
`;
  y += valueSize * 1.4 + padding * 0.6;

  // ─── Impacto máximo ───
  svg += `
  <text x="${panelX + padding}" y="${y}" font-family="Arial, Helvetica, sans-serif" font-size="${labelSize}" font-weight="400" fill="#9ca3af">Impacto máximo en rendimiento</text>
  <text x="${panelX + padding}" y="${y + valueSize * 0.85}" font-family="Arial, Helvetica, sans-serif" font-size="${valueSize * 0.85}" font-weight="700" fill="#f59e0b">${DATA.maxImpact}</text>
  <text x="${panelX + padding + valueSize * 1.5}" y="${y + valueSize * 0.85}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize}" font-weight="400" fill="#9ca3af">Intibucá, Honduras</text>
`;
  y += valueSize * 1.2 + padding * 0.8;

  // ─── Línea separadora ───
  svg += `
  <line x1="${panelX + padding}" y1="${y}" x2="${panelX + panelWidth - padding}" y2="${y}" stroke="#374151" stroke-width="1"/>
`;
  y += padding * 0.8;

  // ─── Semáforo regional ───
  svg += `
  <text x="${panelX + padding}" y="${y + sectionSize}" font-family="Arial, Helvetica, sans-serif" font-size="${sectionSize}" font-weight="600" fill="#e5e7eb">Semáforo regional</text>
`;
  y += sectionSize * 1.8;

  const semaforoItems = [
    { label: "Crítico", count: DATA.critico, color: "#ef4444", icon: "🔴" },
    { label: "Alerta", count: DATA.alerta, color: "#f59e0b", icon: "🟠" },
    { label: "Vigilancia", count: DATA.vigilancia, color: "#eab308", icon: "🟡" },
    { label: "Normal", count: DATA.normal, color: "#22c55e", icon: "🟢" },
  ];

  const dotSize = Math.round(panelWidth * 0.022);
  const itemHeight = Math.round(sectionSize * 1.6);
  for (const item of semaforoItems) {
    svg += `
  <circle cx="${panelX + padding + dotSize}" cy="${y + itemHeight / 2}" r="${dotSize}" fill="${item.color}"/>
  <text x="${panelX + padding + dotSize * 3}" y="${y + itemHeight / 2 + labelSize * 0.35}" font-family="Arial, Helvetica, sans-serif" font-size="${labelSize}" font-weight="500" fill="#d1d5db">${item.label}</text>
  <text x="${panelX + panelWidth - padding}" y="${y + itemHeight / 2 + labelSize * 0.35}" font-family="Arial, Helvetica, sans-serif" font-size="${labelSize * 1.3}" font-weight="700" fill="#ffffff" text-anchor="end">${item.count}</text>
`;
    y += itemHeight;
  }

  y += padding * 0.4;
  svg += `
  <line x1="${panelX + padding}" y1="${y}" x2="${panelX + panelWidth - padding}" y2="${y}" stroke="#374151" stroke-width="1"/>
`;
  y += padding * 0.8;

  // ─── Hallazgos clave ───
  svg += `
  <text x="${panelX + padding}" y="${y + sectionSize}" font-family="Arial, Helvetica, sans-serif" font-size="${sectionSize}" font-weight="600" fill="#e5e7eb">Hallazgos clave</text>
`;
  y += sectionSize * 1.6;

  for (const h of DATA.hallazgos) {
    svg += `
  <text x="${panelX + padding}" y="${y + smallSize * 1.2}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize * 1.15}" font-weight="600" fill="#10b981">${h.zona}</text>
  <text x="${panelX + padding}" y="${y + smallSize * 2.4}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize}" font-weight="400" fill="#9ca3af">${h.cultivo} · ${h.detalle}</text>
`;
    y += smallSize * 3.2;
  }

  // ─── Cobertura ───
  y += padding * 0.4;
  svg += `
  <line x1="${panelX + padding}" y1="${y}" x2="${panelX + panelWidth - padding}" y2="${y}" stroke="#374151" stroke-width="1"/>
`;
  y += padding * 0.8;

  svg += `
  <text x="${panelX + padding}" y="${y + smallSize * 1.2}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize}" font-weight="400" fill="#6b7280">Cobertura: ${DATA.paises} países · 18 zonas</text>
  <text x="${panelX + padding}" y="${y + smallSize * 2.4}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize}" font-weight="400" fill="#6b7280">Cultivos: ${DATA.cultivos}</text>
  <text x="${panelX + padding}" y="${y + smallSize * 3.6}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize}" font-weight="400" fill="#6b7280">Fuentes: NASA · Agencia Espacial Europea</text>
`;

  svg += `\n</svg>`;
  return svg;
}

async function createOverlay() {
  console.log(`Procesando: ${inputPath}`);

  const image = sharp(inputPath);
  const metadata = await image.metadata();
  const width = metadata.width;
  const height = metadata.height;

  console.log(`Dimensiones originales: ${width}x${height}`);

  // Redimensionar a 1600x900 (16:9) con crop centrado
  const targetWidth = 1600;
  const targetHeight = 900;

  console.log(`Redimensionando a: ${targetWidth}x${targetHeight} (16:9 crop)`);

  const resized = await sharp(inputPath)
    .resize(targetWidth, targetHeight, { fit: "cover", position: "centre" })
    .jpeg({ quality: 90 })
    .toBuffer();

  const overlaySvg = createDataPanel(targetWidth, targetHeight);
  const overlayBuffer = Buffer.from(overlaySvg);

  const result = await sharp(resized)
    .composite([{ input: overlayBuffer, top: 0, left: 0 }])
    .jpeg({ quality: 88, progressive: true })
    .toBuffer();

  writeFileSync(outputPath, result);
  console.log(`Overlay aplicado: ${outputPath}`);
  console.log(`Tamaño: ${(result.length / 1024).toFixed(0)}KB`);
}

createOverlay().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
