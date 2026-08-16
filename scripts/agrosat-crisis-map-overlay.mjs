/**
 * agrosat-crisis-map-overlay.mjs — Combina mapa de AgroSAT + panel de datos semáforo
 *
 * Toma la captura del mapa interactivo y le superpone un panel SVG con
 * las cifras clave del análisis 2024 vs 2026.
 *
 * Uso: node scripts/agrosat-crisis-map-overlay.mjs "<mapa.png>" [--output "<ruta>"]
 */

import sharp from "sharp";
import { existsSync, writeFileSync } from "fs";
import { resolve, dirname, join, basename, extname } from "path";

const args = process.argv.slice(2);
if (!args[0] || args[0] === "--help" || args[0] === "-h") {
  console.log('Uso: node scripts/agrosat-crisis-map-overlay.mjs "<mapa.png>" [--output "<ruta>"]');
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

// ── Datos del análisis ──
const DATA = {
  totalHa: "514,000",
  pctDeterioro: "31%",
  maxImpact: "-26%",
  zonasDeclinando: 12,
  zonasTransicion: 1,
  paises: 10,
  cultivos: "Café · Soja · Maíz · Arroz · Caña",
  critico: 2,
  alerta: 6,
  vigilancia: 4,
  normal: 1,
  hallazgos: [
    { zona: "Loja, Ecuador", cultivo: "Café", detalle: "En transición: migración altitudinal" },
    { zona: "Intibucá, Honduras", cultivo: "Café", detalle: "-26% rendimiento · 20,000 ha" },
    { zona: "Mato Grosso, Brasil", cultivo: "Soja", detalle: "-22% rendimiento · 135,000 ha" },
    { zona: "Chiapas, México", cultivo: "Maíz", detalle: "-25% rendimiento · 30,000 ha" },
  ],
};

function createDataPanel(panelWidth, panelHeight) {
  const padding = Math.round(panelWidth * 0.07);

  const titleSize = Math.round(panelWidth * 0.055);
  const labelSize = Math.round(panelWidth * 0.032);
  const valueSize = Math.round(panelWidth * 0.07);
  const smallSize = Math.round(panelWidth * 0.026);
  const sectionSize = Math.round(panelWidth * 0.036);

  let y = padding + titleSize;

  let svg = `<svg width="${panelWidth}" height="${panelHeight}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="panelGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0a0f0d" stop-opacity="0.97"/>
      <stop offset="100%" stop-color="#0d1311" stop-opacity="0.97"/>
    </linearGradient>
  </defs>

  <rect x="0" y="0" width="${panelWidth}" height="${panelHeight}" fill="url(#panelGrad)"/>

  <!-- Línea superior verde -->
  <rect x="${padding}" y="${padding}" width="${panelWidth - padding * 2}" height="3" fill="#10b981" rx="1.5"/>

  <!-- Título -->
  <text x="${padding}" y="${y + 8}" font-family="Arial, Helvetica, sans-serif" font-size="${titleSize}" font-weight="700" fill="#ffffff">AgroSAT</text>
  <text x="${padding}" y="${y + 8 + titleSize * 1.15}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize * 1.4}" font-weight="400" fill="#10b981" opacity="0.9">Análisis satelital 2024 → 2026</text>
`;

  y += titleSize * 2.6 + padding * 0.5;

  // ─── Cifras principales ───
  svg += `
  <text x="${padding}" y="${y}" font-family="Arial, Helvetica, sans-serif" font-size="${labelSize}" font-weight="400" fill="#9ca3af">Hectáreas con deterioro</text>
  <text x="${padding}" y="${y + valueSize * 0.95}" font-family="Arial, Helvetica, sans-serif" font-size="${valueSize}" font-weight="700" fill="#ef4444">${DATA.totalHa}</text>
  <text x="${padding + valueSize * 2.3}" y="${y + valueSize * 0.95}" font-family="Arial, Helvetica, sans-serif" font-size="${labelSize * 1.3}" font-weight="600" fill="#f59e0b">${DATA.pctDeterioro}</text>
`;
  y += valueSize * 1.5 + padding * 0.5;

  // ─── Impacto máximo ───
  svg += `
  <text x="${padding}" y="${y}" font-family="Arial, Helvetica, sans-serif" font-size="${labelSize}" font-weight="400" fill="#9ca3af">Impacto máximo en rendimiento</text>
  <text x="${padding}" y="${y + valueSize * 0.9}" font-family="Arial, Helvetica, sans-serif" font-size="${valueSize * 0.9}" font-weight="700" fill="#f59e0b">${DATA.maxImpact}</text>
  <text x="${padding + valueSize * 1.6}" y="${y + valueSize * 0.9}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize}" font-weight="400" fill="#9ca3af">Intibucá, Honduras</text>
`;
  y += valueSize * 1.3 + padding * 0.7;

  // ─── Separador ───
  svg += `
  <line x1="${padding}" y1="${y}" x2="${panelWidth - padding}" y2="${y}" stroke="#374151" stroke-width="1"/>
`;
  y += padding * 0.7;

  // ─── Semáforo regional ───
  svg += `
  <text x="${padding}" y="${y + sectionSize}" font-family="Arial, Helvetica, sans-serif" font-size="${sectionSize}" font-weight="600" fill="#e5e7eb">Semáforo regional</text>
`;
  y += sectionSize * 1.9;

  const semaforoItems = [
    { label: "Crítico", count: DATA.critico, color: "#ef4444" },
    { label: "Alerta", count: DATA.alerta, color: "#f59e0b" },
    { label: "Vigilancia", count: DATA.vigilancia, color: "#eab308" },
    { label: "Normal", count: DATA.normal, color: "#22c55e" },
  ];

  const dotSize = Math.round(panelWidth * 0.02);
  const itemHeight = Math.round(sectionSize * 1.7);
  for (const item of semaforoItems) {
    svg += `
  <circle cx="${padding + dotSize}" cy="${y + itemHeight / 2}" r="${dotSize}" fill="${item.color}"/>
  <text x="${padding + dotSize * 3.2}" y="${y + itemHeight / 2 + labelSize * 0.35}" font-family="Arial, Helvetica, sans-serif" font-size="${labelSize}" font-weight="500" fill="#d1d5db">${item.label}</text>
  <text x="${panelWidth - padding}" y="${y + itemHeight / 2 + labelSize * 0.35}" font-family="Arial, Helvetica, sans-serif" font-size="${labelSize * 1.4}" font-weight="700" fill="#ffffff" text-anchor="end">${item.count}</text>
`;
    y += itemHeight;
  }

  y += padding * 0.3;
  svg += `
  <line x1="${padding}" y1="${y}" x2="${panelWidth - padding}" y2="${y}" stroke="#374151" stroke-width="1"/>
`;
  y += padding * 0.7;

  // ─── Hallazgos clave ───
  svg += `
  <text x="${padding}" y="${y + sectionSize}" font-family="Arial, Helvetica, sans-serif" font-size="${sectionSize}" font-weight="600" fill="#e5e7eb">Hallazgos clave</text>
`;
  y += sectionSize * 1.7;

  for (const h of DATA.hallazgos) {
    svg += `
  <text x="${padding}" y="${y + smallSize * 1.3}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize * 1.2}" font-weight="600" fill="#10b981">${h.zona}</text>
  <text x="${padding}" y="${y + smallSize * 2.6}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize}" font-weight="400" fill="#9ca3af">${h.cultivo} · ${h.detalle}</text>
`;
    y += smallSize * 3.4;
  }

  // ─── Cobertura ───
  y += padding * 0.3;
  svg += `
  <line x1="${padding}" y1="${y}" x2="${panelWidth - padding}" y2="${y}" stroke="#374151" stroke-width="1"/>
`;
  y += padding * 0.7;

  svg += `
  <text x="${padding}" y="${y + smallSize * 1.2}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize}" font-weight="400" fill="#6b7280">Cobertura: ${DATA.paises} países · 18 zonas</text>
  <text x="${padding}" y="${y + smallSize * 2.4}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize}" font-weight="400" fill="#6b7280">Cultivos: ${DATA.cultivos}</text>
  <text x="${padding}" y="${y + smallSize * 3.6}" font-family="Arial, Helvetica, sans-serif" font-size="${smallSize}" font-weight="400" fill="#6b7280">Fuentes: NASA · Agencia Espacial Europea</text>
`;

  svg += `\n</svg>`;
  return svg;
}

async function createMapOverlay() {
  console.log(`Procesando mapa: ${inputPath}`);

  const image = sharp(inputPath);
  const metadata = await image.metadata();
  const mapWidth = metadata.width;
  const mapHeight = metadata.height;

  console.log(`Mapa original: ${mapWidth}x${mapHeight}`);

  // Layout: mapa izquierda (62%) + panel derecha (38%)
  // Altura objetivo: 900px (16:9 a 1600px)
  const targetHeight = 900;
  const totalWidth = 1600;
  const panelWidth = Math.round(totalWidth * 0.36);
  const mapTargetWidth = totalWidth - panelWidth;

  // Redimensionar mapa manteniendo proporción, crop centrado
  const mapResized = await sharp(inputPath)
    .resize(mapTargetWidth, targetHeight, { fit: "cover", position: "centre" })
    .jpeg({ quality: 92 })
    .toBuffer();

  console.log(`Mapa redimensionado: ${mapTargetWidth}x${targetHeight}`);
  console.log(`Panel: ${panelWidth}x${targetHeight}`);

  // Crear panel de datos
  const panelSvg = createDataPanel(panelWidth, targetHeight);
  const panelBuffer = Buffer.from(panelSvg);

  // Componer: fondo + mapa + panel
  const result = await sharp({
    create: {
      width: totalWidth,
      height: targetHeight,
      channels: 3,
      background: { r: 10, g: 15, b: 13 },
    },
  })
    .composite([
      { input: mapResized, top: 0, left: 0 },
      { input: panelBuffer, top: 0, left: mapTargetWidth },
    ])
    .jpeg({ quality: 90, progressive: true })
    .toBuffer();

  writeFileSync(outputPath, result);
  console.log(`Imagen combinada: ${outputPath}`);
  console.log(`Tamaño: ${(result.length / 1024).toFixed(0)}KB`);
}

createMapOverlay().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
