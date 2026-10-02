"""
gen_fig_editorial.py — Figuras PNG estilo editorial (JRC) para el artículo.

Genera, a partir de scripts/agro-zones.json:
  fig-ndvi.png     — ΔNDVI por zona vs mismo período del año anterior
                     (barras divergentes, ordenadas)
  fig-afectada.png — hectáreas degradadas medidas por pixel, zonas con
                     señal (alerta / vigilancia / critico)

Estilo: fondo blanco, grilla suave, sin bordes, fuentes del sistema —
la misma sobriedad de las figuras del JRC MARS Bulletin.

Ejecutar: .venv/Scripts/python nooa-agent/gen_fig_editorial.py
          [--zones scripts/agro-zones.json] [--out-dir scripts] [--prefix fig]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

ROOT = Path(__file__).parent.parent

NEG = "#d95f0e"      # deterioro
POS = "#15803d"      # mejora / vigor
GRID = "#e2e8f0"
TEXT = "#334155"

plt.rcParams.update({
    "font.family": "Segoe UI",
    "font.size": 10.5,
    "text.color": TEXT,
    "axes.edgecolor": "#cbd5e1",
    "axes.labelcolor": TEXT,
    "xtick.color": TEXT,
    "ytick.color": TEXT,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def _style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def fig_ndvi(zones, out_dir: Path, prefix: str, base_year: str = "2025") -> Path:
    rows = sorted(zones, key=lambda z: z["ndvi_delta"])
    names = [f"{z['name']} ({z['country'][:3].upper()})" for z in rows]
    vals = [z["ndvi_delta"] for z in rows]
    colors = [NEG if v < 0 else POS for v in vals]

    fig, ax = plt.subplots(figsize=(7.6, 5.2), dpi=170)
    bars = ax.barh(names, vals, color=colors, height=0.62)
    ax.axvline(0, color="#94a3b8", lw=1)
    _style(ax)
    ax.set_xlabel(f"Cambio en NDVI (vigor de la vegetación) vs mismo período de {base_year}")
    ax.xaxis.set_major_formatter(mtick.FormatStrFormatter("%.2f"))
    for b, v in zip(bars, vals):
        ax.text(
            v + (0.004 if v >= 0 else -0.004), b.get_y() + b.get_height() / 2,
            f"{v:+.3f}".replace(".", ","),
            va="center", ha="left" if v >= 0 else "right", fontsize=9, color=TEXT,
        )
    ax.set_xlim(min(vals) - 0.045, max(vals) + 0.055)
    fig.tight_layout()
    out = out_dir / f"{prefix}-ndvi.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def fig_afectada(zones, out_dir: Path, prefix: str, base_year: str = "2025") -> Path:
    rows = sorted(
        [z for z in zones if z.get("affected_area_ha", 0) > 0],
        key=lambda z: z["affected_area_ha"],
    )
    names = [f"{z['name']} ({z['country'][:3].upper()})" for z in rows]
    vals = [z["affected_area_ha"] for z in rows]
    colors = {
        "critico": "#b91c1c", "alerta": "#d95f0e", "vigilancia": "#eab308",
    }

    fig, ax = plt.subplots(figsize=(7.6, 4.4), dpi=170)
    bars = ax.barh(
        names, vals, height=0.6,
        color=[colors.get(z["status"], NEG) for z in rows],
    )
    _style(ax)
    ax.set_xlabel(f"Hectáreas con degradación medida por píxel (exceso vs {base_year})")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    for b, v in zip(bars, vals):
        ax.text(
            v + max(vals) * 0.012, b.get_y() + b.get_height() / 2,
            f"{v:,.0f}".replace(",", ".") + " ha",
            va="center", fontsize=9, color=TEXT,
        )
    ax.set_xlim(0, max(vals) * 1.16)
    fig.tight_layout()
    out = out_dir / f"{prefix}-ha.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def main():
    parser = argparse.ArgumentParser(description="Figuras editoriales del boletín")
    parser.add_argument("--zones", default=str(ROOT / "scripts" / "agro-zones.json"))
    parser.add_argument("--out-dir", default=str(ROOT / "scripts"))
    parser.add_argument("--prefix", default="fig")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(Path(args.zones).read_text(encoding="utf-8"))
    zones = payload["zones"]
    base_year = (payload.get("window", {}).get("baseline", [""])[0] or "")[:4] or "2025"
    for f in (fig_ndvi, fig_afectada):
        print(f"  -> {f(zones, out_dir, args.prefix, base_year)}")


if __name__ == "__main__":
    main()
