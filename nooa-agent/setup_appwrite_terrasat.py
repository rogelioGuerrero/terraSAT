"""
setup_appwrite_terrasat.py — Crea la base `terrasat` en el proyecto Appwrite
compartido con pricewatch (project 6ab1922d00020f5a2e99) y sus dos
colecciones: bulletin_runs (1 fila por boletín) y zone_observations
(1 fila por zona por corrida — la serie histórica).

Requiere en .env o entorno:
  APPWRITE_ENDPOINT, APPWRITE_PROJECT_ID, APPWRITE_API_KEY

Uso: python nooa-agent/setup_appwrite_terrasat.py
"""

import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.environ["APPWRITE_ENDPOINT"].rstrip("/")
PROJECT = os.environ["APPWRITE_PROJECT_ID"]
KEY = os.environ["APPWRITE_API_KEY"]
HEADERS = {
    "X-Appwrite-Project": PROJECT,
    "X-Appwrite-Key": KEY,
    "Content-Type": "application/json",
}
# El plan gratis permite 1 base por proyecto — TerraSAT vive dentro de la
# base "pricewatch" con colecciones namespaced "terrasat_*".
DB_ID = os.environ.get("APPWRITE_DATABASE_ID", "pricewatch")


def api(method: str, path: str, **kwargs):
    url = f"{ENDPOINT}{path}"
    res = requests.request(method, url, headers=HEADERS, timeout=30, **kwargs)
    if res.status_code == 409:
        return {"_exists": True}, 409
    if not res.ok:
        print(f"  !! {method} {path}: {res.status_code} {res.text[:300]}")
    return (res.json() if res.text else {}), res.status_code


def ensure_collection(coll_id: str, name: str, attrs: list[dict]):
    _, code = api("POST", f"/databases/{DB_ID}/collections", json={
        "collectionId": coll_id, "name": name, "documentSecurity": False,
    })
    print(f"  colección {coll_id}: {'existente' if code == 409 else 'creada' if code in (200, 201) else 'error'}")

    for attr in attrs:
        kind = attr.pop("type")
        payload = {"key": attr.pop("key"), "required": attr.pop("required", False), **attr}
        _, code = api(
            "POST",
            f"/databases/{DB_ID}/collections/{coll_id}/attributes/{kind}",
            json=payload,
        )
        if code not in (200, 201, 202, 409):
            print(f"    attr {payload['key']}: HTTP {code}")

    # Los atributos se procesan async — esperar a que estén disponibles
    for _ in range(30):
        data, _ = api("GET", f"/databases/{DB_ID}/collections/{coll_id}/attributes")
        statuses = [a.get("status") for a in data.get("attributes", [])]
        if statuses and all(s == "available" for s in statuses):
            print(f"    {len(statuses)} atributos disponibles")
            return
        if any(s in ("failed", "stuck") for s in statuses):
            print(f"    atributos con estado problemático: {statuses}")
            return
        time.sleep(2)


def main():
    print(f"Proyecto: {PROJECT} @ {ENDPOINT}")
    _, code = api("GET", f"/databases/{DB_ID}")
    print(f"database {DB_ID}: {'OK' if code == 200 else f'HTTP {code}'}")

    ensure_collection("terrasat_bulletin_runs", "TerraSAT — Boletines por corrida", [
        {"type": "string", "key": "product", "size": 32, "required": True},
        {"type": "string", "key": "period_start", "size": 16, "required": True},
        {"type": "string", "key": "period_end", "size": 16, "required": True},
        {"type": "datetime", "key": "run_at", "required": True},
        {"type": "string", "key": "phase", "size": 16, "required": True, "default": "data"},
        {"type": "integer", "key": "n_zones", "required": True},
        {"type": "string", "key": "counts_json", "size": 512, "required": True},
        {"type": "string", "key": "title", "size": 256},
        {"type": "string", "key": "briefing_json", "size": 32768},
        {"type": "string", "key": "blocks_json", "size": 65536},
        {"type": "string", "key": "final_article", "size": 32768},
        {"type": "string", "key": "qa_errors", "size": 8192},
    ])

    ensure_collection("terrasat_zone_observations", "TerraSAT — Serie histórica por zona", [
        {"type": "string", "key": "run_id", "size": 64, "required": True},
        {"type": "datetime", "key": "observed_at", "required": True},
        {"type": "string", "key": "zone", "size": 128, "required": True},
        {"type": "string", "key": "country", "size": 64},
        {"type": "string", "key": "crop", "size": 64},
        {"type": "string", "key": "status", "size": 16, "required": True},
        {"type": "string", "key": "alert_cause", "size": 128},
        {"type": "float", "key": "ndvi_base"}, {"type": "float", "key": "ndvi_cur"},
        {"type": "float", "key": "ndre_base"}, {"type": "float", "key": "ndre_cur"},
        {"type": "float", "key": "ndvi_delta"}, {"type": "float", "key": "ndre_delta"},
        {"type": "float", "key": "stressed_frac_base"}, {"type": "float", "key": "stressed_frac_cur"},
        {"type": "float", "key": "excess_stressed_frac"},
        {"type": "integer", "key": "affected_area_ha"},
        {"type": "float", "key": "rainfall_mm"}, {"type": "float", "key": "rainfall_pct"},
        {"type": "integer", "key": "days_cur"},
        {"type": "string", "key": "latest_image", "size": 16},
    ])

    print("\nListo. El pipeline escribirá en estas colecciones en cada corrida.")


if __name__ == "__main__":
    sys.exit(main())
