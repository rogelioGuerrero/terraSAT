/**
 * gen-choropleth-echarts.mjs — Mapa coroplético admin-1 (estilo JRC) + overlay
 * de círculos por zona monitoreada.
 *
 * ECharts en modo SSR: renderiza SVG sin navegador → sharp → PNG.
 * Fuente geográfica: Natural Earth admin-1 10m filtrado a LAC
 * (scripts/data/ne_10m_admin_1_lac.geojson).
 * La región de cada zona se detecta por point-in-polygon — sirve para
 * cualquier producto (agro/forest/urban) sin mantener mapeo de nombres.
 *
 * Uso: node scripts/gen-choropleth-echarts.mjs [--zones <json>] [--out <png>]
 *      [--svg <svg>] [--title "..."] [--subtitle "..."]
 * Default: scripts/agro-zones.json → scripts/agrosat-choropleth.{svg,png}
 */

import { readFileSync, writeFileSync } from "fs";
import { resolve } from "path";
import * as echarts from "echarts";
import sharp from "sharp";

const argv = process.argv.slice(2);
const arg = (name, dflt) => {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : dflt;
};

const ZONES_PATH = arg("--zones", "scripts/agro-zones.json");
const GEO_PATH = "scripts/data/ne_10m_admin_1_lac.geojson";
const OUT_PNG = arg("--out", "scripts/agrosat-choropleth.png");
const OUT_SVG = arg("--svg", OUT_PNG.replace(/\.png$/i, "") + ".svg");
const TITLE = arg("--title", "Estado de las zonas monitoreadas");
const SUBTITLE_EXTRA = arg("--subtitle", "");

const W = 1040;
const H = 820;

const STATUS = {
  critico: { color: "#b91c1c", label: "Crítico", v: 0 },
  alerta: { color: "#d95f0e", label: "Alerta", v: 1 },
  vigilancia: { color: "#eab308", label: "Vigilancia", v: 2 },
  normal: { color: "#15803d", label: "Normal", v: 3 },
  sin_datos: { color: "#9ca3af", label: "Sin datos", v: 4 },
};

// Posición de la etiqueta del círculo por zona (evita colisiones en los
// clusters de Centroamérica y el Eje Cafetero).
const LABEL_POS = {
  "Alta Verapaz": "left",
  "El Paraíso": "top",
  Jinotega: "bottom",
  Caldas: "left",
  "Quindío": "bottom",
  "Espírito Santo": "right",
  "Valle Central": "left",
  Mendoza: "bottom",
};

const hexA = (hex, a) => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
};

// Países que se dibujan como contexto (gris neutro)
const CONTEXT_ADMINS = new Set([
  "Mexico", "Guatemala", "Belize", "Honduras", "El Salvador", "Nicaragua",
  "Costa Rica", "Panama", "Colombia", "Venezuela", "Ecuador", "Peru",
  "Brazil", "Bolivia", "Paraguay", "Uruguay", "Argentina", "Chile",
  "Guyana", "Suriname", "Cuba", "Haiti", "Dominican Republic", "Jamaica",
  "Puerto Rico", "Trinidad and Tobago", "Bahamas",
]);

const norm = (s) =>
  (s ?? "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z]/g, "");

// ─── Point-in-polygon (ray casting) ──────────────────────────────────

function ringContains(ring, x, y) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)
      inside = !inside;
  }
  return inside;
}

function featureContains(f, lng, lat) {
  const g = f.geometry;
  const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  return polys.some(
    (poly) =>
      ringContains(poly[0], lng, lat) &&
      !poly.slice(1).some((hole) => ringContains(hole, lng, lat))
  );
}

// ─── Datos ───────────────────────────────────────────────────────────

const zonesPayload = JSON.parse(readFileSync(ZONES_PATH, "utf8"));
const zones = zonesPayload.zones;
const geoAll = JSON.parse(readFileSync(GEO_PATH, "utf8"));

const lacFeatures = geoAll.features.filter((f) =>
  CONTEXT_ADMINS.has(f.properties.admin)
);

// Región admin-1 por zona: el feature que contiene el punto (lng, lat).
// Si el punto cae fuera (costa/borde), la región más cercana por
// centroide etiquetado en Natural Earth.
const regionKey = (f) => f.properties.iso_3166_2 || f.properties.adm1_code;
const unmatched = [];
const regionOf = {};
for (const z of zones) {
  let feat = lacFeatures.find((f) => featureContains(f, z.lng, z.lat));
  if (!feat) {
    feat = lacFeatures
      .filter((f) => f.properties.latitude != null)
      .sort(
        (a, b) =>
          Math.hypot(a.properties.latitude - z.lat, a.properties.longitude - z.lng) -
          Math.hypot(b.properties.latitude - z.lat, b.properties.longitude - z.lng)
      )[0];
  }
  if (feat) {
    regionOf[z.name] = regionKey(feat);
    console.log(
      `  ${z.name} → ${feat.properties.name} (${feat.properties.iso_3166_2})`
    );
  } else {
    unmatched.push(z.name);
  }
}
if (unmatched.length) {
  console.warn("Sin match admin-1:", unmatched.join(", "));
}

echarts.registerMap("LAC1", { type: "FeatureCollection", features: lacFeatures });

// Peor estado por región admin-1 (una región puede tener >1 zona)
const regionStatus = {};
for (const z of zones) {
  const r = regionOf[z.name];
  if (!r) continue;
  const cur = regionStatus[r];
  if (!cur || STATUS[z.status].v < STATUS[cur].v) regionStatus[r] = z.status;
}

const usedStatuses = [...new Set(zones.map((z) => z.status))].sort(
  (a, b) => STATUS[a].v - STATUS[b].v
);

const totalHa = zones.reduce((s, z) => s + z.area_ha, 0);
const affHa = zones.reduce((s, z) => s + (z.affected_area_ha || 0), 0);

const MESES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
const win = zonesPayload?.window?.current ?? [];
let periodStr = "";
if (win.length === 2) {
  const a = new Date(win[0]);
  const b = new Date(win[1]);
  periodStr =
    a.getUTCMonth() === b.getUTCMonth()
      ? `${a.getUTCDate()}–${b.getUTCDate()} ${MESES[a.getUTCMonth()]} ${a.getUTCFullYear()}`
      : `${a.getUTCDate()} ${MESES[a.getUTCMonth()]}–${b.getUTCDate()} ${MESES[b.getUTCMonth()]} ${b.getUTCFullYear()}`;
}
const subtext = [SUBTITLE_EXTRA, periodStr].filter(Boolean).join(" · ");

// ─── Opción ECharts ──────────────────────────────────────────────────

const option = {
  animation: false,
  backgroundColor: "#e8eff5",
  title: {
    text: TITLE,
    subtext,
    left: 16,
    top: 12,
    textStyle: { fontSize: 17, fontWeight: 700, color: "#0f172a" },
    subtextStyle: { fontSize: 11.5, color: "#64748b" },
  },
  geo: {
    map: "LAC1",
    nameProperty: "iso_3166_2",
    roam: false,
    boundingCoords: [
      [-96, 20],
      [-30, -57],
    ],
    itemStyle: {
      areaColor: "#f5f6f8",
      borderColor: "#c3ccd6",
      borderWidth: 0.6,
    },
    emphasis: { disabled: true },
    select: { disabled: true },
    regions:
      process.env.NO_REGIONS === "1"
        ? []
        : Object.entries(regionStatus).map(([name, st]) => ({
            name,
            itemStyle: {
              areaColor: hexA(STATUS[st].color, 0.30),
              borderColor: STATUS[st].color,
              borderWidth: 0.8,
            },
          })),
  },
  visualMap: {
    type: "piecewise",
    seriesIndex: 0,
    inverse: true,
    right: 14,
    bottom: 40,
    orient: "vertical",
    itemWidth: 14,
    itemHeight: 10,
    itemGap: 6,
    textStyle: { fontSize: 11.5, color: "#334155" },
    pieces: usedStatuses.map((s) => ({
      value: STATUS[s].v,
      label: `${STATUS[s].label} (${zones.filter((z) => z.status === s).length})`,
      color: STATUS[s].color,
    })),
    outOfRange: { color: "#eef2f6" },
  },
  graphic: [
    {
      type: "text",
      left: 14,
      bottom: 8,
      style: {
        text: `${zones.length} zonas · ${totalHa.toLocaleString("es-ES")} ha · ${affHa.toLocaleString("es-ES")} ha afectadas   |   Natural Earth · Datos: Copernicus Sentinel-2, ERA5`,
        fontSize: 10.5,
        fill: "#94a3b8",
      },
    },
  ],
  series: [
    {
      type: "scatter",
      coordinateSystem: "geo",
      data: (process.env.NO_SCATTER === "1" ? [] : zones).map((z) => ({
        name: z.name,
        value: [z.lng, z.lat, STATUS[z.status].v],
        symbolSize: Math.max(11, Math.sqrt(z.area_ha) * 0.048 + 6),
        itemStyle: {
          color: STATUS[z.status].color,
          opacity: z.status === "normal" ? 0.55 : 0.85,
          borderColor: "#ffffff",
          borderWidth: 1.2,
          shadowBlur: 3,
          shadowColor: "rgba(0,0,0,0.25)",
        },
        label:
          z.status === "normal" || z.status === "sin_datos"
            ? { show: false }
            : {
                show: true,
                formatter: z.name,
                position: LABEL_POS[z.name] ?? "top",
                distance: 7,
                fontSize: 10.5,
                fontWeight: 600,
                color: "#0f172a",
                textBorderColor: "#ffffff",
                textBorderWidth: 2.5,
              },
      })),
      labelLayout: { hideOverlap: false },
      z: 10,
    },
  ],
};

// ─── Render SSR → SVG → PNG ──────────────────────────────────────────

const chart = echarts.init(null, null, {
  renderer: "svg",
  ssr: true,
  width: W,
  height: H,
});
chart.setOption(option);
const svg = chart.renderToSVGString();
chart.dispose();

writeFileSync(resolve(OUT_SVG), svg);
await sharp(Buffer.from(svg), { density: 160 })
  .flatten({ background: "#e8eff5" })
  .png()
  .toFile(OUT_PNG);
console.log(`SVG: ${OUT_SVG}`);
console.log(`PNG: ${OUT_PNG}`);
