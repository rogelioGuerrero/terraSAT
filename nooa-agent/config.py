"""
Configuración centralizada para TerraSAT.

Filosofía NOOA: un solo lugar para constantes compartidas.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# ─── LLM ──────────────────────────────────────────────────────────────

MODEL = os.getenv("NOOA_MODEL", "groq/openai/gpt-oss-120b")

# ─── CDSE / Sentinel ──────────────────────────────────────────────────

AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOGUE_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
