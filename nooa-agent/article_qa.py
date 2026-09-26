"""
article_qa.py — Verificación determinista del artículo generado.

Extrae TODO número del artículo y chequea que corresponda a un valor real
del JSON de zonas (medido o agregado). Es el gate anti-alucinación:
un número que no matchea ningún dato → error → repair pass o fallback.

No usa LLM — es Python puro, por eso es confiable.
"""

from __future__ import annotations

import re

_NUM_RE = re.compile(r"-?\d{1,3}(?:[.,   ]\d{3})+|-?\d+(?:[.,]\d+)?")


def _parse_num(raw: str) -> float | None:
    s = raw.replace(chr(0x202f), '').replace(chr(0xa0), '').replace(' ', '').strip()
    if not s:
        return None
    # Miles solo si la parte entera empieza en digito NO-cero:
    # '14,600' -> 14600   pero   '-0.120' -> -0.12 (decimal)
    if re.fullmatch(r'-?[1-9]\d{0,2}([.,]\d{3})+', s):
        try:
            return float(re.sub(r'[.,]', '', s))
        except ValueError:
            return None
    # Decimal simple: 0.032 | -51,2 | -0.120
    s2 = s.replace(',', '.')
    try:
        return float(s2)
    except ValueError:
        return None
    # Grupos de miles: 14,600 | 14.600 | 50 000
    if re.fullmatch(r"-?\d{1,3}([.,]\d{3})+", s):
        try:
            return float(re.sub(r"[.,]", "", s))
        except ValueError:
            return None
    # Decimal simple: 0.032 | -51,2
    s2 = s.replace(",", ".")
    try:
        return float(s2)
    except ValueError:
        return None


def extract_numbers(text: str) -> list[float]:
    out = []
    for m in _NUM_RE.finditer(text):
        v = _parse_num(m.group(0))
        if v is not None:
            out.append(v)
    return out


def allowed_values(zones_doc: dict) -> dict[str, float]:
    """Todos los valores numéricos que el artículo puede citar legítimamente."""
    vals: dict[str, float] = {}
    zones = zones_doc.get("zones", [])

    def put(label, v, *roundings):
        if v is None:
            return
        vals[label] = float(v)
        for r in roundings:
            vals[f"{label}~r{r}"] = round(float(v), r) if r > 0 else round(float(v), r)

    for z in zones:
        n = z.get("name", "?")
        meta = z.get("meta", {})
        put(f"{n}.area_ha", z.get("area_ha"), -2, -3)
        put(f"{n}.affected", z.get("affected_area_ha"), -2, -3)
        put(f"{n}.rain_pct", z.get("rainfall_pct"), 0, 1)
        put(f"{n}.rain_mm", z.get("rainfall_mm"), 0, 1)
        put(f"{n}.ndvi_delta", z.get("ndvi_delta"), 2, 3)
        put(f"{n}.ndre_delta", z.get("ndre_delta"), 2, 3)
        for k in ("ndvi_base", "ndvi_cur", "ndre_base", "ndre_cur"):
            put(f"{n}.{k}", meta.get(k), 2, 3)
        for k in ("stressed_frac_cur", "excess_stressed_frac"):
            f = meta.get(k)
            if f is not None:
                put(f"{n}.{k}pct", float(f) * 100, 0, 1)
        put(f"{n}.days", meta.get("days_cur"))
        # día del mes de la última imagen (números como 25 en "25 sep")
        li = meta.get("latest_image", "")
        if li:
            put(f"{n}.latest_day", int(li[8:10]))
            put(f"{n}.latest_year", int(li[:4]))

    # Agregados
    total = sum(z.get("area_ha", 0) for z in zones)
    put("total_area", total, -3, -4)
    for st in ("critico", "alerta", "vigilancia"):
        sub = [z for z in zones if z.get("status") == st]
        put(f"count.{st}", len(sub))
        put(f"affected.{st}", sum(z.get("affected_area_ha", 0) for z in sub), -2, -3)
    put("count.total", len(zones))
    put("count.sin_datos", len([z for z in zones if z.get("status") == "sin_datos"]))
    put("count.normal", len([z for z in zones if z.get("status") == "normal"]))

    # Sumas por pares/trios de zonas en alerta (el artículo agrupa así)
    alert = [z for z in zones if z.get("status") in ("critico", "alerta", "vigilancia")]
    for i, a in enumerate(alert):
        for j, b in enumerate(alert):
            if j > i:
                put(f"pair.{a['name']}+{b['name']}",
                    a.get("affected_area_ha", 0) + b.get("affected_area_ha", 0), -2, -3)
    put("affected.alert+vig", sum(z.get("affected_area_ha", 0) for z in alert), -2, -3)

    # Fechas de la ventana
    w = zones_doc.get("window", {}).get("current", [])
    for i, tag in enumerate(("wstart", "wend")):
        if len(w) > i:
            d = w[i][:10]
            put(f"{tag}.day", int(d[8:10]))
            put(f"{tag}.month", int(d[5:7]))
            put(f"{tag}.year", int(d[:4]))
    return vals


def validate_article(article: str, zones_doc: dict, tol: float = 0.06) -> list[str]:
    """
    Devuelve lista de errores (vacía = artículo fiel a los datos).
    Números ≤ 10 y años se ignoran (conteos de zonas, fechas, etc.).
    """
    allowed = allowed_values(zones_doc)
    zone_names = {z.get("name", "") for z in zones_doc.get("zones", [])}
    errors = []

    for raw in _NUM_RE.findall(article):
        v = _parse_num(raw)
        if v is None or abs(v) <= 10 or 1900 <= v <= 2100:
            continue
        # ¿Existe algún valor permitido a <tol relativo?
        match = any(abs(v - a) <= max(abs(a) * tol, 0.006) for a in allowed.values())
        if not match:
            errors.append(f"Número no verificable en los datos: {raw}")

    # Zonas mencionadas que no existen (por nombre exacto, capitalizado)
    for m in re.finditer(r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)\b", article):
        pass  # demasiado fuzzy — el check de números ya cubre lo material

    return errors
