"""
article_pipeline.py — Generación de artículos por fases, domain-agnostic.

Fases (cada una guarda su estado en Appwrite bulletin_runs → resumible
entre corridas, días o runners efímeros de CI):

  briefing → el LLM actúa de ANALISTA: JSON con hallazgos, patrones,
             ranking, cifras clave (no redacta todavía)
  blocks   → redacción por bloques: lede / alertas / panorama / contexto
             (cada bloque recibe solo su slice — nunca se queda sin tokens)
  edit     → el LLM actúa de EDITOR: cohesión, tono, título, excerpt
  qa       → verificación DETERMINISTA (article_qa): todo número del
             artículo debe existir en los datos; si falla → repair pass
             con la lista de errores; si persiste → el caller usa fallback.

Uso como módulo:
    from article_pipeline import generate
    article = generate("agro", zones_doc, run_id)

Uso CLI (fase individual — multi-día por cron):
    python nooa-agent/article_pipeline.py --product agro --phase briefing

Para agregar un producto (urban, forest...): entrada en PRODUCTS + su
zones JSON. Los prompts son genéricos — el dominio entra por config.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from article_qa import validate_article, validate_format  # noqa: E402

log = logging.getLogger("article_pipeline")

ROOT = Path(__file__).parent.parent

PRODUCTS = {
    "agro": {
        "name": "AgroSAT",
        "subject": "alerta temprana agroclimática para agricultura productiva",
        "zones_json": "scripts/agro-zones.json",
        "sources": "imágenes satelitales Sentinel-2 de la Agencia Espacial Europea (Copernicus) y precipitación ERA5",
        "field_glossary": (
            "area_ha=hectáreas monitoreadas; status=critico/alerta/vigilancia/normal/sin_datos; "
            "alert_cause; affected_area_ha=ha con degradación medida por pixel (exceso vs baseline); "
            "ndvi_delta/ndre_delta=cambio vs mismo período año anterior; "
            "rainfall_pct=lluvia vs climatología 5 años; meta.latest_image=fecha última imagen limpia; "
            "meta.excess_stressed_frac=fracción de pixels degradados nuevos (área afectada)"
        ),
        "cta": (
            "¿Su plantación, propiedad o empresa agroindustrial opera en alguna de estas zonas? "
            "AgroSAT detecta situaciones atípicas que pueden afectar sus cultivos semanas antes "
            "de que aparezcan síntomas visibles, dándole tiempo para actuar. Reportes "
            "personalizados disponibles. También trabajamos con aseguradoras y agroservicios. "
            "Vea mapa interactivo en terraSAT.agtisa.com. Contacto: info@agtisa.com"
        ),
        "with_rain": True,
        "alert_what": "estrés vegetativo medido en los cultivos",
        "unit_name": "el cultivo",
    },
    "forest": {
        "name": "ForestSAT",
        "subject": "monitoreo satelital de bosques, deforestación y quemas",
        "zones_json": "scripts/forest-zones.json",
        "sources": "imágenes satelitales Sentinel-2 de la Agencia Espacial Europea (Copernicus)",
        "field_glossary": (
            "area_ha=hectáreas monitoreadas; status=critico/alerta/vigilancia/normal/sin_datos; "
            "alert_cause; affected_area_ha=ha con pérdida de cobertura medida por pixel (exceso vs baseline); "
            "ndvi_delta/ndre_delta=cambio vs mismo período año anterior; "
            "meta.nbr_delta=cambio del índice de quema (NBR) vs año anterior; "
            "meta.latest_image=fecha última imagen limpia; "
            "meta.excess_stressed_frac=fracción de pixels degradados nuevos (área afectada)"
        ),
        "cta": (
            "¿Su organización gestiona bosques, áreas protegidas o monitorea cambio de uso de suelo? "
            "ForestSAT detecta pérdida de cobertura y señales de quema en escala regional con datos "
            "satelitales verificables. Reportes personalizados para gobiernos, ONGs y aseguradoras. "
            "Vea mapa interactivo en terraSAT.agtisa.com. Contacto: info@agtisa.com"
        ),
        "with_rain": False,
        "alert_what": "pérdida de cobertura forestal, deforestación y cicatrices de quema",
        "unit_name": "la cobertura forestal",
    },
    "urban": {
        "name": "UrbanSAT",
        "subject": "monitoreo satelital de crecimiento urbano y cambio de uso de suelo",
        "zones_json": "scripts/urban-zones.json",
        "sources": "imágenes satelitales Sentinel-2 de la Agencia Espacial Europea (Copernicus)",
        "field_glossary": (
            "area_ha=hectáreas del área metropolitana monitoreada; "
            "status=critico/alerta/vigilancia/normal/sin_datos; alert_cause; "
            "affected_area_ha=ha con ganancia de área construida medida por pixel (exceso vs baseline); "
            "ndvi_delta=cambio de vegetación vs mismo período año anterior; "
            "meta.ndbi_delta=cambio del índice de área construida (NDBI) vs año anterior; "
            "meta.latest_image=fecha última imagen limpia; "
            "meta.excess_stressed_frac=fracción de pixels con ganancia construida nueva"
        ),
        "cta": (
            "¿Su municipio, desarrolladora o aseguradora opera en alguna de estas ciudades? "
            "UrbanSAT mide la expansión de área construida y la pérdida de vegetación con "
            "observación satelital objetiva — catastro, planificación y evaluación de riesgo "
            "en escala metropolitana. Reportes personalizados disponibles. "
            "Vea mapa interactivo en terraSAT.agtisa.com. Contacto: info@agtisa.com"
        ),
        "with_rain": False,
        "alert_what": "expansión de área construida y pérdida de vegetación urbana y periurbana",
        "unit_name": "la ciudad",
    },
}

PHASES = ["briefing", "blocks", "edit", "qa"]


# ─────────────────────────────────────────────────────────────────────
# LLM helper
# ─────────────────────────────────────────────────────────────────────

def _llm(system: str, user: str, max_tokens: int = 4000) -> str:
    from llm_utils import llm_call
    resp = llm_call(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.6, max_tokens=max_tokens,
    )
    content = (resp.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("LLM devolvió contenido vacío")
    return content


def _llm_json(system: str, user: str, max_tokens: int = 4000) -> dict:
    raw = _llm(system, user, max_tokens)
    raw = raw.replace("```json", "").replace("```", "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError(f"LLM no devolvió JSON: {raw[:200]}")
    return json.loads(raw[start:end + 1])


# ─────────────────────────────────────────────────────────────────────
# Estado de fases — Appwrite (compartido entre corridas/CI) +
# archivo local como respaldo
# ─────────────────────────────────────────────────────────────────────

def _state_path(product: str, period: str) -> Path:
    return ROOT / "scripts" / f"article-state-{product}-{period}.json"


def _load_state(product: str, period: str, run_id: str | None) -> dict:
    if run_id:
        from appwrite_store import get_run
        doc = get_run(run_id)
        if doc:
            return {
                "phase": doc.get("phase", "data"),
                "briefing": _maybe_json(doc.get("briefing_json")),
                "blocks": _maybe_json(doc.get("blocks_json")),
                "title": doc.get("title"),
                "article": doc.get("final_article"),
                "qa_errors": doc.get("qa_errors"),
            }
    p = _state_path(product, period)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"phase": "data"}


def _save_state(product: str, period: str, run_id: str | None, state: dict):
    p = _state_path(product, period)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    if run_id:
        from appwrite_store import update_run
        fields = {"phase": state["phase"]}
        if state.get("briefing") is not None:
            fields["briefing_json"] = json.dumps(state["briefing"], ensure_ascii=False)
        if state.get("blocks") is not None:
            fields["blocks_json"] = json.dumps(state["blocks"], ensure_ascii=False)
        if state.get("title"):
            fields["title"] = state["title"]
        if state.get("article"):
            fields["final_article"] = state["article"]
        if state.get("qa_errors") is not None:
            fields["qa_errors"] = state["qa_errors"] if isinstance(state["qa_errors"], str) else "\n".join(state["qa_errors"])
        update_run(run_id, **fields)


def _maybe_json(s):
    if not s:
        return None
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────
# Datos compactos para prompts
# ─────────────────────────────────────────────────────────────────────

def _zone_rows(cfg: dict, zones_doc: dict, statuses: tuple[str, ...] | None = None) -> str:
    rows = []
    for z in zones_doc.get("zones", []):
        if statuses and z.get("status") not in statuses:
            continue
        meta = z.get("meta", {})
        row = (
            f"{z.get('name')} ({z.get('country')}, {z.get('crop')}): "
            f"status={z.get('status')} | causa={z.get('alert_cause') or 'normal'} | "
            f"area={z.get('area_ha')} ha | afectada={z.get('affected_area_ha')} ha | "
            f"dNDVI={z.get('ndvi_delta')}"
        )
        # Índices extra por producto, solo si están medidos
        if cfg.get("with_rain", True):
            row += f" | dNDRE={z.get('ndre_delta')} | lluvia={z.get('rainfall_pct')}%"
        for extra in ("nbr_delta", "ndbi_delta", "ndwi_delta"):
            if meta.get(extra) is not None:
                row += f" | {extra}={meta[extra]}"
        row += (
            f" | pix_degradados={meta.get('excess_stressed_frac')} | "
            f"ultima_imagen={meta.get('latest_image')}"
        )
        rows.append(row)
    return "\n".join(rows) or "(ninguna)"


# ─────────────────────────────────────────────────────────────────────
# Fases
# ─────────────────────────────────────────────────────────────────────

def phase_briefing(cfg: dict, zones_doc: dict) -> dict:
    system = (
        f"Eres el analista de datos de {cfg['name']} ({cfg['subject']}). "
        "No redactas el artículo — produces el briefing analítico que usará el redactor. "
        "Respondes SOLO con JSON válido. No inventes cifras: usa solo las de los datos."
    )
    user = f"""Datos de la corrida ({cfg['sources']}):
{cfg['field_glossary']}

TODAS LAS ZONAS:
{_zone_rows(cfg, zones_doc)}

Genera JSON con:
- "headline": hallazgo principal en 1 oración (con la cifra clave)
- "severity_ranking": zonas de mayor a menor preocupación (nombres)
- "regional_patterns": lista de 2-4 patrones (p.ej. "café centroamericano con déficit hídrico generalizado")
- "contrasts": contrastes interesantes (zonas que se recuperan, etc.)
- "sin_datos": zonas sin datos y por qué
- "key_numbers": las 5-8 cifras que el artículo DEBE citar (label: valor exacto de los datos)
- "cautions": qué NO afirmar (p.ej. causa no verificada vs señal consistente con)
- "angle": el ángulo periodístico recomendado"""
    return _llm_json(system, user, 3000)


def phase_blocks(cfg: dict, zones_doc: dict, briefing: dict) -> dict:
    system = (
        f"Eres el redactor de {cfg['name']} ({cfg['subject']}), producto de TerraSAT. "
        "Español periodístico profesional, tono de alerta temprana creíble — ni alarmista ni frío. "
        "Citas fuentes como los datos satelitales de la ESA/NASA. NUNCA inventes cifras: "
        "solo las del briefing y los datos de zonas."
    )
    briefing_str = json.dumps(briefing, ensure_ascii=False, indent=1)
    blocks = {}

    specs = {
        "lede": (
            "Escribe el lede del boletín: el título periodístico en una línea propia "
            "(sin markdown, sin emojis) seguido de 2-3 oraciones que enganchen con "
            "el hallazgo principal y la cifra clave. Máx 90 palabras. "
            f"TODAS las zonas:\n{_zone_rows(cfg, zones_doc)}"
        ),
        "alertas": (
            f"Escribe la sección de ZONAS EN ALERTA: para cada zona crítica/alerta explica qué "
            f"detectó el satélite (deltas de índices, % pixels afectados"
            + (", lluvia vs normal" if cfg.get("with_rain") else "") +
            f") y qué significa para {cfg['unit_name']}. Agrupa por tipo si hay patrón. "
            "Cifras exactas de los datos.\n"
            "REGLA EDITORIAL: la primera vez que menciones un índice (NDVI, NBR, NDBI) "
            "glosalo en lenguaje llano entre paréntesis — ej. 'NDVI (vigor de la vegetación)'. "
            "Expresa las fracciones de píxeles como porcentajes ('18 % del área monitoreada'), "
            "nunca como decimal crudo (0.18).\n"
            f"ZONAS:\n{_zone_rows(cfg, zones_doc, ('critico', 'alerta'))}"
        ),
        "panorama": (
            "Escribe la sección de PANORAMA: zonas en vigilancia (breve, agrupadas), zonas "
            "normales en contexto (qué significa que no haya señal), y zonas sin datos con "
            "explicación honesta de nubosidad.\n"
            f"ZONAS:\n{_zone_rows(cfg, zones_doc, ('vigilancia', 'normal', 'sin_datos'))}"
        ),
        "contexto": (
            "Escribe el CIERRE: patrón regional del briefing, contrastes (recuperaciones), "
            "y por qué importa monitorear antes de síntomas visibles. Sin CTA comercial — "
            "va aparte. Máx 100 palabras."
        ),
    }

    for name, task in specs.items():
        log.info(f"  bloque: {name}")
        blocks[name] = _llm(
            system,
            f"BRIEFING DEL ANALISTA:\n{briefing_str}\n\nTAREA: {task}",
            2500,
        )
    return blocks


def phase_edit(cfg: dict, briefing: dict, blocks: dict) -> dict:
    system = (
        f"Eres el editor jefe de {cfg['name']} ({cfg['subject']}). Pulís el borrador: "
        "cohesión entre secciones, tono uniforme, transiciones, eliminación de redundancias. "
        "NO cambies ninguna cifra ni nombre de zona — son datos verificados. "
        "FORMATO EDITORIAL PARA WEB: markdown limpio — encabezados de sección en línea propia, "
        "tablas markdown para datos por zona, listas con -, negritas solo para cifras y nombres "
        "de zona. SIN emojis, SIN hashtags, SIN CTA comercial (se agregan aparte). "
        "Números en convención española: punto para miles (55.000 ha) y coma para decimales "
        "(‑0,065). Título periodístico sin markdown ni emojis. "
        "FUENTES: nunca nombres sensores ni misiones (Sentinel-2, Landsat, MODIS, ERA5…); "
        "cita solo la agencia — 'satélites de la Agencia Espacial Europea (Copernicus)', 'NASA'. "
        "LEGIBILIDAD (vendemos servicios a público no técnico): oraciones de máx ~30 palabras; "
        "cada párrafo con una idea; para cada cifra decir qué significa para el lector "
        "(riesgo, dinero, acción); sin jerga sin glosa; respuesta a '¿y a mí qué?' al cierre. "
        "NARRATIVA: el lede ancla siempre el periodo CON AÑO ('entre julio y septiembre de 2026') "
        "y abre con gancho — el dato más llamativo verificado o un contraste, planteando una "
        "pregunta que el artículo responde. Sin hipérbole ni adjetivos alarmistas: la intriga "
        "sale del dato, no de exagerarlo. "
        "Respondes SOLO con JSON válido."
    )
    user = f"""BRIEFING: {json.dumps(briefing, ensure_ascii=False)}

BORRADOR POR BLOQUES:
### LEDE
{blocks.get('lede', '')}

### ALERTAS
{blocks.get('alertas', '')}

### PANORAMA
{blocks.get('panorama', '')}

### CONTEXTO
{blocks.get('contexto', '')}

Devuelve JSON con:
- "title": título periodístico (máx 90 caracteres)
- "excerpt": resumen 1-2 oraciones con zonas y hectáreas concretas (máx 220 caracteres)
- "article": el artículo final pulido, completo, listo para publicar (sin CTA ni hashtags — se agregan aparte)"""
    return _llm_json(system, user, 4500)


def phase_qa(cfg: dict, zones_doc: dict, edited: dict) -> tuple[dict, list[str]]:
    """QA determinista (cifras + formato editorial) + un repair pass."""
    errors = validate_article(edited.get("article", ""), zones_doc)
    errors += validate_format(edited.get("article", ""), edited.get("title", ""))
    if not errors:
        return edited, []

    log.warning(f"QA: {len(errors)} problemas — repair pass")
    allowed_hint = json.dumps(
        {k: v for k, v in _allowed_summary(zones_doc).items()}, ensure_ascii=False
    )
    try:
        fixed = _llm(
            f"Editor de {cfg['name']}. Corrige el artículo según los ERRORES listados "
            "(cifras no verificables → usa los valores reales; formato → aplica el estándar "
            "editorial web: sin emojis, sin hashtags, números con punto para miles y coma "
            "para decimales). No cambies nada más. "
            "Devuelve el artículo completo corregido, solo texto.",
            f"ERRORES:\n" + "\n".join(errors) +
            f"\n\nVALORES REALES PERMITIDOS:\n{allowed_hint}\n\nARTÍCULO:\n{edited['article']}",
            4500,
        )
        edited["article"] = fixed
        errors = validate_article(fixed, zones_doc)
        errors += validate_format(fixed, edited.get("title", ""))
    except Exception as e:
        log.warning(f"Repair pass fallo: {e}")
    return edited, errors


def _allowed_summary(zones_doc: dict) -> dict:
    """Resumen legible de valores reales para el repair pass."""
    out = {}
    for z in zones_doc.get("zones", []):
        out[z["name"]] = {
            "status": z["status"], "area_ha": z["area_ha"],
            "affected_area_ha": z["affected_area_ha"],
            "ndvi_delta": z["ndvi_delta"], "ndre_delta": z["ndre_delta"],
            "rainfall_pct": z["rainfall_pct"],
        }
    return out


# ─────────────────────────────────────────────────────────────────────
# Orquestador
# ─────────────────────────────────────────────────────────────────────

def generate(product: str, zones_doc: dict | None = None,
             run_id: str | None = None, only_phase: str | None = None) -> str:
    cfg = PRODUCTS[product]

    if zones_doc is None:
        zones_doc = json.loads((ROOT / cfg["zones_json"]).read_text(encoding="utf-8"))

    period = zones_doc.get("window", {}).get("current", ["", ""])[0][:10] or str(date.today())
    state = _load_state(product, period, run_id)
    done = {"data": -1, "briefing": 0, "blocks": 1, "edit": 2, "qa": 3, "done": 4}
    cur = done.get(state.get("phase", "data"), -1)

    def want(idx: int, name: str) -> bool:
        return (only_phase == name) if only_phase else (idx > cur)

    if want(0, "briefing"):
        print("  Fase briefing (analista)...")
        state["briefing"] = phase_briefing(cfg, zones_doc)
        state["phase"] = "briefing"
        _save_state(product, period, run_id, state)

    if want(1, "blocks"):
        print("  Fase blocks (redacción por bloques)...")
        state["blocks"] = phase_blocks(cfg, zones_doc, state["briefing"])
        state["phase"] = "blocks"
        _save_state(product, period, run_id, state)

    if want(2, "edit"):
        print("  Fase edit (edición)...")
        edited = phase_edit(cfg, state["briefing"], state["blocks"])
        state["title"] = edited.get("title", "")
        state["article"] = edited.get("article", "")
        state["_excerpt"] = edited.get("excerpt", "")
        state["phase"] = "edit"
        _save_state(product, period, run_id, state)

    if want(3, "qa"):
        print("  Fase qa (verificación determinista)...")
        edited = {"title": state["title"], "article": state["article"],
                  "excerpt": state.get("_excerpt", "")}
        edited, errors = phase_qa(cfg, zones_doc, edited)
        state["article"] = edited["article"]
        state["qa_errors"] = errors
        state["phase"] = "done" if not errors else "qa_failed"
        _save_state(product, period, run_id, state)
        if errors:
            raise RuntimeError(f"QA falló tras repair: {errors[:3]}")

    # Artículo final para la WEB (limpio: sin CTA ni hashtags).
    # La variante social se compone aparte — ver social_version().
    return state["article"].strip()


def social_version(product: str, article: str) -> str:
    """Variante para redes sociales: artículo + CTA + hashtags (deterministas).

    El CTA y los hashtags NO van en el artículo web — se inyectan solo aquí,
    en el archivo *-social.txt que consume el pipeline de Facebook.
    """
    cfg = PRODUCTS[product]
    return (
        f"{article.strip()}\n\n{cfg['cta']} 🌱☕\n\n"
        f"#TerraSAT #{cfg['name']} #AlertaTemprana #Satélite"
    )


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", default="agro", choices=list(PRODUCTS))
    parser.add_argument("--phase", default=None, choices=PHASES,
                        help="correr solo una fase (multi-día); default = todas las pendientes")
    args = parser.parse_args()

    cfg = PRODUCTS[args.product]
    zones_doc = json.loads((ROOT / cfg["zones_json"]).read_text(encoding="utf-8"))
    try:
        from appwrite_store import save_bulletin_data
        run_id = save_bulletin_data(args.product, zones_doc)
    except Exception:
        run_id = None
    article = generate(args.product, zones_doc, run_id=run_id, only_phase=args.phase)
    if not args.phase or args.phase == "qa":
        fname = "generated-article.txt" if args.product == "agro" else f"generated-article-{args.product}.txt"
        out = ROOT / "scripts" / fname
        out.write_text(article, encoding="utf-8")
        social_out = ROOT / "scripts" / fname.replace(".txt", "-social.txt")
        social_out.write_text(social_version(args.product, article), encoding="utf-8")
        print(f"\nArtículo (web): {out}")
        print(f"Artículo (social): {social_out}")


if __name__ == "__main__":
    main()
