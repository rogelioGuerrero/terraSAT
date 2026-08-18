/**
 * gen-overlay-terrasat.mjs — Genera PNG de branding (logo + texto) para overlay sobre video.
 * Adaptado de add-branding-video-terrasat.mjs
 *
 * Uso: node scripts/gen-overlay-terrasat.mjs --width 1280 --height 720 --output path.png
 */
import sharp from "sharp";
import { writeFileSync } from "fs";

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

const args = process.argv.slice(2);
let width = 1280, height = 720, output = "overlay.png";
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--width" && args[i + 1]) { width = parseInt(args[i + 1], 10); i++; }
  else if (args[i] === "--height" && args[i + 1]) { height = parseInt(args[i + 1], 10); i++; }
  else if (args[i] === "--output" && args[i + 1]) { output = args[i + 1]; i++; }
}

createOverlayPng(width, height, output).then(() => {
  console.log(`Overlay generado: ${output} (${width}x${height})`);
});
