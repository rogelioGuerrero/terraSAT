"""
appwrite_store.py — Persistencia del pipeline TerraSAT en Appwrite.

Tablas (API nueva TablesDB, dentro de la DB compartida "pricewatch",
namespaced terrasat_*):
  - terrasat_bulletin_runs     1 fila por corrida; guarda fase del pipeline
                               (data → briefing → blocks → edit → qa → done)
                               así cada fase es resumible — incluso en runners
                               efímeros de CI.
  - terrasat_zone_observations 1 fila por zona por corrida — serie histórica.

Toda escritura es best-effort: si Appwrite no responde, el pipeline sigue
(nunca bloquea el boletín por un problema de persistencia).

Env: APPWRITE_ENDPOINT, APPWRITE_PROJECT_ID, APPWRITE_API_KEY,
     APPWRITE_DATABASE_ID (default "pricewatch")
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.environ.get("APPWRITE_ENDPOINT", "").rstrip("/")
PROJECT = os.environ.get("APPWRITE_PROJECT_ID", "")
KEY = os.environ.get("APPWRITE_API_KEY", "")
DB = os.environ.get("APPWRITE_DATABASE_ID", "pricewatch")
COLL_RUNS = "terrasat_bulletin_runs"
COLL_OBS = "terrasat_zone_observations"

log = logging.getLogger("appwrite_store")


def available() -> bool:
    return bool(ENDPOINT and PROJECT and KEY)


def _req(method: str, path: str, **kwargs):
    res = requests.request(
        method, f"{ENDPOINT}{path}",
        headers={
            "X-Appwrite-Project": PROJECT,
            "X-Appwrite-Key": KEY,
            "Content-Type": "application/json",
        },
        timeout=30, **kwargs,
    )
    body = res.json() if res.text else {}
    return body, res.status_code


def run_id_for(product: str, period_start: str, period_end: str) -> str:
    """rowId determinista: agro-2026-09-05_2026-09-26 (≤36 chars)."""
    rid = f"{product}-{period_start[:10]}_{period_end[:10]}"
    return re.sub(r"[^a-zA-Z0-9._-]", "", rid)[:36]


def get_run(run_id: str) -> dict | None:
    if not available():
        return None
    try:
        body, code = _req("GET", f"/tablesdb/{DB}/tables/{COLL_RUNS}/rows/{run_id}")
        return body if code == 200 else None
    except Exception as e:
        log.warning(f"Appwrite get_run fallo: {e}")
        return None


def update_run(run_id: str, **fields) -> bool:
    """PATCH sobre el documento del run; crea si no existe."""
    if not available():
        return False
    try:
        base = f"/tablesdb/{DB}/tables/{COLL_RUNS}/rows"
        _, code = _req("PATCH", f"{base}/{run_id}", json={"data": fields})
        if code == 404:
            _, code = _req("POST", base, json={"rowId": run_id, "data": fields})
        return code in (200, 201)
    except Exception as e:
        log.warning(f"Appwrite update_run fallo: {e}")
        return False


def save_observations(run_id: str, zones_doc: dict) -> int:
    """Escribe una fila por zona — la serie histórica."""
    if not available():
        return 0
    now = datetime.now(timezone.utc).isoformat()
    written = 0
    base = f"/tablesdb/{DB}/tables/{COLL_OBS}/rows"
    for i, z in enumerate(zones_doc.get("zones", [])):
        meta = z.get("meta", {})
        doc_id = re.sub(r"[^a-zA-Z0-9._-]", "", f"{run_id}-{i:02d}")[:36]
        row = {
            "run_id": run_id,
            "observed_at": now,
            "zone": z.get("name", ""),
            "country": z.get("country", ""),
            "crop": z.get("crop", ""),
            "status": z.get("status", "sin_datos"),
            "alert_cause": z.get("alert_cause", "") or "",
            "ndvi_base": meta.get("ndvi_base"), "ndvi_cur": meta.get("ndvi_cur"),
            "ndre_base": meta.get("ndre_base"), "ndre_cur": meta.get("ndre_cur"),
            "ndvi_delta": z.get("ndvi_delta"), "ndre_delta": z.get("ndre_delta"),
            "stressed_frac_base": meta.get("stressed_frac_base"),
            "stressed_frac_cur": meta.get("stressed_frac_cur"),
            "excess_stressed_frac": meta.get("excess_stressed_frac"),
            "affected_area_ha": z.get("affected_area_ha"),
            "rainfall_mm": z.get("rainfall_mm"), "rainfall_pct": z.get("rainfall_pct"),
            "days_cur": meta.get("days_cur"),
            "latest_image": meta.get("latest_image", ""),
        }
        try:
            _, code = _req("POST", base, json={"rowId": doc_id, "data": {k: v for k, v in row.items() if v is not None}})
            if code == 409:
                _, code = _req("PATCH", f"{base}/{doc_id}", json={"data": {k: v for k, v in row.items() if v is not None}})
            if code in (200, 201):
                written += 1
        except Exception as e:
            log.warning(f"Appwrite obs {z.get('name')}: {e}")
    return written


def counts_by_status(zones: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for z in zones:
        counts[z.get("status", "sin_datos")] = counts.get(z.get("status", "sin_datos"), 0) + 1
    return counts


def save_bulletin_data(product: str, zones_doc: dict) -> str | None:
    """Punto de entrada tras la colección de datos. Devuelve el run_id."""
    if not available():
        log.info("Appwrite no configurado — continuo sin persistencia")
        return None
    window = zones_doc.get("window", {})
    period_start = window.get("current", ["", ""])[0][:10]
    period_end = window.get("current", ["", ""])[1][:10]
    rid = run_id_for(product, period_start, period_end)

    ok = update_run(
        rid,
        product=product,
        period_start=period_start,
        period_end=period_end,
        run_at=datetime.now(timezone.utc).isoformat(),
        phase="data",
        n_zones=len(zones_doc.get("zones", [])),
        counts_json=json.dumps(counts_by_status(zones_doc.get("zones", [])), ensure_ascii=False),
    )
    n_obs = save_observations(rid, zones_doc)
    log.info(f"Appwrite: run {rid} {'guardado' if ok else 'error'}; {n_obs} observaciones")
    return rid
