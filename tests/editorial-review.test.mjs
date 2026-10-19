/**
 * Tests de la compuerta editorial (scripts/editorial-review.mjs).
 * Herméticos: todos los fixtures viven en un directorio temporal.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "crypto";
import { spawnSync } from "child_process";
import {
  mkdtempSync, writeFileSync, readFileSync, existsSync, rmSync,
} from "fs";
import { tmpdir } from "os";
import { join, dirname, resolve } from "path";
import { fileURLToPath } from "url";
import {
  assertEditorialReview,
  reviewManifestPath,
} from "../scripts/editorial-review.mjs";
import { runPublish, runArticleQa } from "../scripts/publish-informe.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

const sha = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");

const ARTICLE = "Lead del boletín de prueba.\n\n**Subhead**\n\nPárrafo dos.\n";
const SOCIAL = ARTICLE + "\nCTA info@agtisa.com\n\n#tag\n";
const zonesPayload = (over = {}) => ({
  product: "agro",
  generated_at: "2026-09-28",
  source: "real",
  window: {
    current: ["2026-09-07T00:00:00Z", "2026-09-28T23:59:59Z"],
    baseline: ["2025-09-07T00:00:00Z", "2025-09-28T23:59:59Z"],
  },
  zones: [{ name: "Zona", country: "X", crop: "Y", lat: 0, lng: 0, area_ha: 100 }],
  ...over,
});

function makeFixture(t, { zones = zonesPayload(), withSocial = true } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "editorial-review-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const articlePath = join(dir, "generated-article.txt");
  const zonesPath = join(dir, "agro-zones.json");
  const socialPath = join(dir, "generated-article-social.txt");
  const reviewPath = join(dir, "agro-20260928.json");
  writeFileSync(articlePath, ARTICLE);
  writeFileSync(zonesPath, JSON.stringify(zones, null, 2));
  if (withSocial) writeFileSync(socialPath, SOCIAL);
  return { dir, articlePath, zonesPath, socialPath, reviewPath };
}

function writeManifest(fx, over = {}) {
  const manifest = {
    product: "agro",
    reviewer: "Revisor de Prueba",
    reviewed_at: "2026-10-01T12:00:00Z",
    article_sha256: sha(fx.articlePath),
    zones_sha256: sha(fx.zonesPath),
    ...(existsSync(fx.socialPath) ? { social_sha256: sha(fx.socialPath) } : {}),
    ...over,
  };
  writeFileSync(fx.reviewPath, JSON.stringify(manifest, null, 2));
  return manifest;
}

const call = (fx, over = {}) =>
  assertEditorialReview({
    product: "agro",
    articlePath: fx.articlePath,
    zonesPath: fx.zonesPath,
    reviewPath: fx.reviewPath,
    socialPath: existsSync(fx.socialPath) ? fx.socialPath : null,
    ...over,
  });

test("pasa con zonas reales y hashes coincidentes (artículo+zonas+social)", (t) => {
  const fx = makeFixture(t);
  writeManifest(fx);
  const manifest = call(fx);
  assert.equal(manifest.product, "agro");
  assert.equal(manifest.reviewer, "Revisor de Prueba");
});

test("pasa sin variante social si el manifiesto tampoco la cubre", (t) => {
  const fx = makeFixture(t, { withSocial: false });
  writeManifest(fx);
  const manifest = call(fx, { socialPath: null });
  assert.equal(manifest.social_sha256, undefined);
});

test("rechaza zonas simuladas aunque los hashes coincidan", (t) => {
  const fx = makeFixture(t, { zones: zonesPayload({ source: "simulated" }) });
  writeManifest(fx);
  assert.throws(() => call(fx), /source.*simulated/i);
});

test("rechaza cuando falta el manifiesto de revisión", (t) => {
  const fx = makeFixture(t);
  assert.throws(() => call(fx), /atestación|manifest|falta/i);
});

test("rechaza artículo modificado tras la revisión (hash stale)", (t) => {
  const fx = makeFixture(t);
  writeManifest(fx);
  writeFileSync(fx.articlePath, ARTICLE + "cambio\n");
  assert.throws(() => call(fx), /article_sha256 no coincide/i);
});

test("rechaza zonas modificadas tras la revisión (hash stale)", (t) => {
  const fx = makeFixture(t);
  writeManifest(fx);
  const z = zonesPayload();
  z.zones[0].area_ha = 999;
  writeFileSync(fx.zonesPath, JSON.stringify(z));
  assert.throws(() => call(fx), /zones_sha256 no coincide/i);
});

test("rechaza variante social modificada tras la revisión (hash stale)", (t) => {
  const fx = makeFixture(t);
  writeManifest(fx);
  writeFileSync(fx.socialPath, SOCIAL + "cambio\n");
  assert.throws(() => call(fx), /social_sha256 no coincide/i);
});

test("rechaza manifiesto de otro producto", (t) => {
  const fx = makeFixture(t);
  writeManifest(fx, { product: "forest" });
  assert.throws(() => call(fx), /product.*forest/i);
});

test("rechaza zonas de otro producto aunque el manifiesto diga agro", (t) => {
  const fx = makeFixture(t, { zones: zonesPayload({ product: "forest" }) });
  writeManifest(fx);
  assert.throws(() => call(fx), /product.*forest.*agro|agro.*forest/i);
});

test("rechaza social presentado sin social_sha256 en el manifiesto", (t) => {
  const fx = makeFixture(t);
  const m = writeManifest(fx);
  delete m.social_sha256;
  writeFileSync(fx.reviewPath, JSON.stringify(m));
  assert.throws(() => call(fx), /social_sha256 no coincide/i);
});

test("rechaza manifiesto con social_sha256 cuando no se presenta social", (t) => {
  const fx = makeFixture(t);
  writeManifest(fx);
  assert.throws(() => call(fx, { socialPath: null }), /social_sha256/i);
});

test("rechaza window.current inválida y zones vacío", (t) => {
  const fx = makeFixture(t, {
    zones: zonesPayload({ window: { current: ["no-es-fecha"] }, zones: [] }),
  });
  writeManifest(fx);
  assert.throws(() => call(fx), /window\.current|zones vacío/i);
});

test("rechaza reviewer vacío y reviewed_at inválido", (t) => {
  const fx = makeFixture(t);
  writeManifest(fx, { reviewer: " ", reviewed_at: "ayer" });
  assert.throws(() => call(fx), /reviewer|reviewed_at/i);
});

test("QA numérico acepta artículo fiel a los datos de zonas", (t) => {
  const fx = makeFixture(t);
  writeFileSync(
    fx.articlePath,
    "Boletín de prueba\n\nLa zona Zona registra 100 ha monitoreadas.\n"
  );
  // No lanza: article_qa.py sale 0 (stdout "OK") sobre fixtures temp.
  assert.doesNotThrow(() => runArticleQa(fx.articlePath, fx.zonesPath));
});

test("QA numérico rechaza artículo con cifra fabricada", (t) => {
  const fx = makeFixture(t);
  writeFileSync(
    fx.articlePath,
    "Boletín de prueba\n\nLa zona Zona reporta 99.999 ha afectadas.\n"
  );
  assert.throws(
    () => runArticleQa(fx.articlePath, fx.zonesPath),
    /QA|verificable|99\.999/i
  );
});

// Stubs aislados: la revisión se simula como aprobada (fixture firmado) y se
// inyecta el QA real de Python — sin crear manifiestos en el repo ni red.
const stubReview = () => ({ reviewer: "Test", reviewed_at: "2026-10-01T00:00:00Z" });

test("runPublish: artículo firmado pero con cifra fabricada aborta antes de side effects", async (t) => {
  const fx = makeFixture(t);
  writeFileSync(
    fx.articlePath,
    "Boletín de prueba\n\nLa zona Zona reporta 99.999 ha afectadas.\n"
  );
  const informesPath = join(fx.dir, "informes.json");
  writeFileSync(informesPath, "[]\n");
  let photoCalled = false;
  let figsCalled = false;
  await assert.rejects(
    runPublish(
      { product: "agro" },
      {
        paths: {
          article: fx.articlePath,
          zones: fx.zonesPath,
          social: fx.socialPath,
          informesJson: informesPath,
        },
        fns: {
          review: stubReview,
          qa: (a, z) => runArticleQa(a, z),
          genFigs: () => { figsCalled = true; return []; },
          getPhoto: async () => { photoCalled = true; return true; },
        },
      }
    ),
    /QA|verificable|99\.999/i
  );
  assert.equal(figsCalled, false, "no debió intentar generar figuras");
  assert.equal(photoCalled, false, "no debió tocar la red");
  assert.equal(readFileSync(informesPath, "utf8"), "[]\n", "informes.json intacto");
});

test("runPublish: falla de figura requerida aborta sin mutar artículo ni publicar", async (t) => {
  const fx = makeFixture(t);
  const articleWithFigs =
    "Boletín de prueba\n\nTexto con figura referenciada.\n\n" +
    "![Mapa](/figs/agrosat-20260928-mapa.png)\n\n*Figura 1 — Caption de prueba.*\n";
  writeFileSync(fx.articlePath, articleWithFigs);
  const informesPath = join(fx.dir, "informes.json");
  writeFileSync(informesPath, "[]\n");
  let photoCalled = false;
  await assert.rejects(
    runPublish(
      { product: "agro" },
      {
        paths: {
          article: fx.articlePath,
          zones: fx.zonesPath,
          social: fx.socialPath,
          informesJson: informesPath,
        },
        fns: {
          review: stubReview,
          qa: () => {},
          genFigs: () => ["mapa"],
          genMap: () => { throw new Error("no debió llamarse"); },
          getPhoto: async () => { photoCalled = true; return true; },
        },
      }
    ),
    /figuras requeridas no generadas|no se modifica/i
  );
  assert.equal(readFileSync(fx.articlePath, "utf8"), articleWithFigs, "artículo sin mutar");
  assert.equal(readFileSync(informesPath, "utf8"), "[]\n", "informes.json intacto");
  assert.equal(photoCalled, false, "no debió tocar la red");
});

test("runPublish: si el video falla, el informe sale sin campo video (sin URL rota)", async (t) => {
  const fx = makeFixture(t);
  const informesPath = join(fx.dir, "informes.json");
  writeFileSync(informesPath, "[]\n");
  let videoCalled = false;
  await runPublish(
    { product: "agro" },
    {
      paths: {
        article: fx.articlePath,
        zones: fx.zonesPath,
        social: fx.socialPath,
        informesJson: informesPath,
      },
      fns: {
        review: stubReview,
        qa: () => {},
        genFigs: () => [],
        genMap: () => null,
        getPhoto: async () => true,
        getVideo: async () => { videoCalled = true; return false; },
      },
    }
  );
  assert.equal(videoCalled, true, "se intentó el video");
  const [entry] = JSON.parse(readFileSync(informesPath, "utf8"));
  assert.equal("video" in entry, false, "sin video: el campo no debe aparecer");
  assert.equal(entry.image, "informe-agrosat-20260928-opt.jpg");
});

test("runPublish: dry-run post-gates no escribe informes ni toca la red", async (t) => {
  const fx = makeFixture(t);
  const informesPath = join(fx.dir, "informes.json");
  writeFileSync(informesPath, "[]\n");
  let photoCalled = false;
  await runPublish(
    { product: "agro", dryRun: true, noVideo: true },
    {
      paths: {
        article: fx.articlePath,
        zones: fx.zonesPath,
        social: fx.socialPath,
        informesJson: informesPath,
      },
      fns: {
        review: stubReview,
        qa: () => {},
        getPhoto: async () => { photoCalled = true; return true; },
      },
    }
  );
  assert.equal(photoCalled, false);
  assert.equal(readFileSync(informesPath, "utf8"), "[]\n");
});

test("publish-informe --dry-run sin revisión falla antes de red o cambios web", (t) => {
  // El gate deriva el manifiesto esperado del fin de ventana de agro-zones.json.
  // Si un revisor ya atestó este boletín, el dry-run legítimamente pasa y
  // este test no aplica.
  const zonesPath = join(ROOT, "scripts", "agro-zones.json");
  const zones = JSON.parse(readFileSync(zonesPath, "utf8"));
  const end = new Date(zones.window.current[1]).toISOString().slice(0, 10).replace(/-/g, "");
  if (existsSync(reviewManifestPath("agro", end))) {
    t.skip("ya existe atestación humana para esta ventana — dry-run permitido");
    return;
  }
  const informesPath = join(ROOT, "web", "src", "data", "informes.json");
  const before = readFileSync(informesPath);
  const res = spawnSync(
    process.execPath,
    [join(ROOT, "scripts", "publish-informe.mjs"), "--product", "agro", "--dry-run"],
    { cwd: ROOT, encoding: "utf8" }
  );
  assert.notEqual(res.status, 0, `dry-run debió fallar:\n${res.stdout}\n${res.stderr}`);
  assert.match(res.stdout + res.stderr, /compuerta editorial|atestación|review/i);
  assert.deepEqual(readFileSync(informesPath), before, "informes.json no debió cambiar");
});
