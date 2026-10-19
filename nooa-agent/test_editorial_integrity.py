"""Regression checks for quantitative editorial safeguards (no external APIs)."""

import sys
import json
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import agro_real_data
import article_pipeline
import article_qa
from demo_alerta_temprana_regional import AgroZone


def sample_doc():
    return {
        "window": {"current": ["2026-09-07", "2026-09-28"]},
        "zones": [{
            "name": "Caldas", "status": "alerta", "area_ha": 45000,
            "affected_area_ha": 13800, "rainfall_pct": -51.6,
            "ndvi_delta": -0.0651, "ndre_delta": -0.03,
            "meta": {"latest_image": "2026-09-27"},
        }],
    }


def test_spanish_thousands_and_decimals_stay_together():
    assert article_qa.extract_numbers("1.536,4 % y -0,065") == [1536.4, -0.065]
    assert article_qa.extract_numbers("NDVI −0,065") == [-0.065]
    assert article_qa.extract_numbers("NDVI ‑0,065") == [-0.065]


def test_large_and_small_inventions_are_not_exempt():
    doc = sample_doc()
    assert article_qa.validate_article("Caldas: 13.000 ha", doc)
    assert article_qa.validate_article("Se midieron 5 zonas", doc)
    assert article_qa.validate_article("En 2040", doc)
    assert article_qa.validate_article("NDVI -0,061", doc)


def test_known_values_dates_and_figure_number_pass():
    doc = sample_doc()
    text = (
        "7-28 sep 2026: Caldas tiene 13.800 ha y NDVI -0,065. "
        "Figura 1. ![Mapa](/figs/agrosat-20260928-mapa.png)"
    )
    assert article_qa.validate_article(text, doc) == []


def test_small_bbox_is_not_inflated_and_oversized_bbox_fails():
    bbox = agro_real_data.zone_bbox(0, 0, 50)
    assert bbox[2] - bbox[0] < 0.03
    with pytest.raises(ValueError, match="dividirla"):
        agro_real_data.zone_bbox(0, 0, 2_000_000)


def test_missing_baseline_stress_does_not_become_area_affected(monkeypatch):
    zone = AgroZone("Caldas", "Colombia", "Cafe", 5.0, -75.0, 45000)
    valid = {
        "ndvi": 0.5, "ndre": 0.3, "nbr": 0.2, "ndbi": 0.1, "ndwi": 0.1,
        "stressed_frac": 0.5, "n_days": 4, "latest_date": "2026-09-27",
    }
    results = iter([valid, {"error": "baseline unavailable"}, valid])
    monkeypatch.setattr(agro_real_data, "get_token", lambda: "test-token")
    monkeypatch.setattr(agro_real_data, "request_index_stats", lambda *a, **kw: next(results))
    monkeypatch.setattr(agro_real_data, "dump_zones_json", lambda *a, **kw: None)
    agro_real_data.collect_real_zones([zone], today=date(2026, 9, 28), verbose=False)
    assert zone.status == "sin_datos"
    assert zone.affected_area_ha == 0
    assert zone.data_meta["error_base_stress"] == "baseline unavailable"


def test_missing_rain_is_not_published_as_zero_or_causal(monkeypatch, tmp_path):
    zone = AgroZone("Caldas", "Colombia", "Cafe", 5.0, -75.0, 45000)
    base = {
        "ndvi": 0.6, "ndre": 0.4, "nbr": 0.2, "ndbi": 0.1, "ndwi": 0.1,
        "stressed_frac": 0.1, "n_days": 4, "latest_date": "2025-09-27",
    }
    cur = {**base, "ndvi": 0.4, "ndre": 0.2, "stressed_frac": 0.4,
           "latest_date": "2026-09-27"}
    results = iter([base, base, cur])
    monkeypatch.setattr(agro_real_data, "get_token", lambda: "test-token")
    monkeypatch.setattr(agro_real_data, "request_index_stats", lambda *a, **kw: next(results))
    monkeypatch.setattr(
        agro_real_data, "fetch_precipitation", lambda *a, **kw: {"error": "sin ERA5"},
    )
    monkeypatch.chdir(tmp_path)
    agro_real_data.collect_real_zones([zone], today=date(2026, 9, 28), verbose=False)
    saved = json.loads((tmp_path / "scripts" / "agro-zones.json").read_text(encoding="utf-8"))
    assert saved["zones"][0]["rainfall_pct"] is None
    assert saved["zones"][0]["meta"]["precip"]["error"] == "sin ERA5"
    assert "lluvia" not in article_pipeline._zone_rows(
        article_pipeline.PRODUCTS["agro"], saved,
    )
    assert "enfermedad" not in zone.alert_cause.lower()


def test_stale_completed_article_is_not_reused(monkeypatch):
    stages = []
    monkeypatch.setattr(
        article_pipeline, "_load_state",
        lambda *args: {"phase": "done", "zones_sha256": "old-data", "article": "stale"},
    )
    monkeypatch.setattr(article_pipeline, "_save_state", lambda *args: None)
    monkeypatch.setattr(
        article_pipeline, "phase_briefing",
        lambda *args: stages.append("briefing") or {},
    )
    monkeypatch.setattr(
        article_pipeline, "phase_blocks",
        lambda *args: stages.append("blocks") or {},
    )
    monkeypatch.setattr(
        article_pipeline, "phase_edit",
        lambda *args: stages.append("edit") or {"article": "Texto nuevo", "title": "Nuevo"},
    )
    monkeypatch.setattr(article_pipeline, "inject_figures", lambda *args: "Texto nuevo")
    monkeypatch.setattr(
        article_pipeline, "phase_qa",
        lambda *args: (args[2], []),
    )
    assert article_pipeline.generate("agro", sample_doc()) == "Texto nuevo"
    assert stages == ["briefing", "blocks", "edit"]


def test_publication_qa_cli_rejects_new_invented_number(tmp_path):
    doc_path = tmp_path / "zones.json"
    article_path = tmp_path / "article.txt"
    doc_path.write_text(json.dumps(sample_doc()), encoding="utf-8")
    article_path.write_text(
        "Caldas: 13.800 ha y NDVI (vigor de la vegetación) -0,065.",
        encoding="utf-8",
    )
    args = ["--article", str(article_path), "--zones", str(doc_path)]
    assert article_qa.main(args) == 0
    article_path.write_text("Caldas: 13.000 ha inventadas.", encoding="utf-8")
    assert article_qa.main(args) == 1
