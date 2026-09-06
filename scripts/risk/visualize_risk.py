#!/usr/bin/env python3
"""
PHASE 4 — RISK ENGINE VISUALISATION

Matplotlib figure for a risk assessment cycle in East Prydz Bay. The map MUST
clearly distinguish the five layers (Phase 4 spec §8):

  OBSERVED POSITION  /  FORECAST POSITION  /  UNCERTAINTY ENVELOPE  /
  RISK CORRIDOR  /  VESSEL

The uncertainty envelope is drawn with a dashed boundary and is labelled in the
legend as a prototype decision-support region — it must NOT be read as an exact
physical boundary or a validated confidence interval.

Imported lazily (only by run_risk_demo.py / validation) so that
`risk_engine.py` stays usable in headless, non-matplotlib contexts.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

EARTH_RADIUS_KM = 6371.0088
CLASS_COLORS = {"LOW": "#2e7d32", "MODERATE": "#f9a825", "HIGH": "#c62828"}


def _circle_pts(lat: float, lon: float, r_km: float, n: int = 72) -> tuple[list[float], list[float]]:
    """Approximate a circle of radius r_km centred at (lat, lon)."""
    lats, lons = [], []
    rlat = math.radians(lat)
    for k in range(n + 1):
        theta = 2 * math.pi * k / n
        # local equirectangular step
        dlat = (r_km / EARTH_RADIUS_KM) * 180.0 / math.pi
        dlon = dlat / max(math.cos(rlat), 1e-6)
        lats.append(lat + dlat * math.cos(theta))
        lons.append(lon + dlon * math.sin(theta))
    return lats, lons


def plot_assessments(assessments: list[Any], layer: dict[str, Any] | None,
                     cfg: dict[str, Any], asof: str,
                     title: str, out_path: Path,
                     show: bool = False) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    region = cfg["region"]
    lat0, lat1, lon0, lon1 = region["lat_min"], region["lat_max"], region["lon_min"], region["lon_max"]
    mid_lat = (lat0 + lat1) / 2.0

    fig, ax = plt.subplots(figsize=(10.5, 8.5))
    fig.suptitle(title, fontsize=13, fontweight="bold")
    ax.set_title(f"East Prydz Bay  ·  as-of {asof} (UTC)  ·  CRS {region['crs']}",
                 fontsize=9, color="0.35")

    # navigation layer as a light mesh
    if layer and layer.get("cells"):
        import numpy as np
        lg = np.array([c["lon"] for c in layer["cells"]])
        lt = np.array([c["lat"] for c in layer["cells"]])
        sc = np.array([0 if c["class"] == "LOW" else (1 if c["class"] == "MODERATE" else 2)
                       for c in layer["cells"]])
        ax.scatter(lg, lt, c=sc, cmap="YlOrRd", s=14, alpha=0.35, linewidths=0, zorder=1)

    for a in assessments:
        cls = a.risk_class
        color = CLASS_COLORS[cls]
        # RISK CORRIDOR (filled, semi-transparent)
        clat, clon = _circle_pts(a.forecast.pred_lat, a.forecast.pred_lon, a.corridor_radius_km)
        ax.fill(clon, clat, color=color, alpha=0.16, linewidth=0, zorder=2)
        # UNCERTAINTY ENVELOPE (dashed — not an exact boundary)
        elat, elon = _circle_pts(a.forecast.pred_lat, a.forecast.pred_lon, a.envelope_radius_km)
        ax.plot(elon, elat, color=color, linestyle="--", linewidth=1.2, alpha=0.85, zorder=3)
        # FORECAST POSITION
        ax.scatter([a.forecast.pred_lon], [a.forecast.pred_lat], marker="*", s=180,
                   color=color, edgecolor="black", linewidth=0.6, zorder=5)
        # OBSERVED POSITION
        ax.scatter([a.iceberg.lon], [a.iceberg.lat], marker="^", s=100,
                   color="#555b66", edgecolor="black", linewidth=0.6, zorder=4)
        # label
        lbl = f"{a.iceberg.iceberg_id}  [{cls}]  {a.risk_score:.1f}"
        ax.annotate(lbl, (a.forecast.pred_lon, a.forecast.pred_lat),
                    textcoords="offset points", xytext=(11, 9), fontsize=8,
                    color=color, fontweight="bold")

    # VESSEL
    if assessments:
        v = assessments[0].vessel
        ax.scatter([v.lon], [v.lat], marker="s", s=120, color="#1565c0",
                   edgecolor="black", linewidth=0.8, zorder=6)
        ax.annotate(f"VESSEL {v.vessel_id}", (v.lon, v.lat),
                    textcoords="offset points", xytext=(8, -16), fontsize=9,
                    color="#1565c0", fontweight="bold")

    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°S)")
    ax.set_aspect(1.0 / math.cos(math.radians(mid_lat)))
    ax.grid(True, alpha=0.3, ls=":")

    # Legend (single source of category meaning)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    legend_handles = [
        Patch(fc="#2e7d32", alpha=0.5, label="RISK CORRIDOR (LOW)"),
        Patch(fc="#f9a825", alpha=0.5, label="RISK CORRIDOR (MODERATE)"),
        Patch(fc="#c62828", alpha=0.5, label="RISK CORRIDOR (HIGH)"),
        Line2D([0], [0], color="0.4", linestyle="--", lw=1.2,
               label="UNCERTAINTY ENVELOPE (prototype region — NOT an exact boundary)"),
        Line2D([0], [0], marker="*", ls="none", color="0.8", markerfacecolor="0.35",
               markersize=11, label="FORECAST POSITION"),
        Line2D([0], [0], marker="^", ls="none", color="0.8", markerfacecolor="#555b66",
               markersize=10, label="OBSERVED POSITION"),
        Line2D([0], [0], marker="s", ls="none", color="0.8", markerfacecolor="#1565c0",
               markersize=9, label="VESSEL"),
    ]
    ax.legend(handles=legend_handles, loc="lower left", fontsize=7.5, framealpha=0.95)

    for a in assessments:
        if a.iceberg.synthetic or a.vessel.synthetic:
            fig.text(0.99, 0.01, "DEMO / SYNTHETIC SCENARIO — NOT real observations.",
                     ha="right", va="bottom", fontsize=9,
                     color="#b71c1c", fontweight="bold", style="italic")
            break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    return out_path