#!/usr/bin/env python3
"""
PHASE 5 — ROUTE OPTIMIZATION VISUALISATION

Matplotlib figures for a Phase 5 routing scenario in East Prydz Bay. Every
figure MUST clearly distinguish (Phase 5 spec §14):

  OBSERVED POSITION  /  FORECAST POSITION  /  UNCERTAINTY ENVELOPE  /
  RISK REGION (LOW/MODERATE/HIGH)  /  VESSEL  /  ROUTE

For multi-stage scenarios (DYNAMIC REPLAN, COMMUNICATION LOSS) the original and
rerouted paths are both drawn and labelled (e.g., ROUTE A and ROUTE B). The
figures are decision-support illustrations, NOT navigational charts.

Imported lazily (only by run_routing_demo.py) so that the optimizer core stays
usable in headless, non-matplotlib contexts.
"""

from __future__ import annotations

import math
from pathlib import Path

from risk_engine import EARTH_RADIUS_KM as R_EARTH
from visualize_risk import CLASS_COLORS, _circle_pts

# Deterministic per-stage colours for route lines (stage order):
STAGE_COLORS = {"INITIAL": "#1565c0", "FRESH": "#1565c0",
                "RISK_UPDATE": "#e65100", "COMMUNICATION_LOST": "#6a1b9a",
                "RECOVERY_FRESH": "#1b5e20"}


def _route_legend_label(stage_label_upper: str,
                        multi_stage: bool) -> str:
    if multi_stage:
        order = ["INITIAL", "FRESH", "RISK_UPDATE", "COMMUNICATION_LOST", "RECOVERY_FRESH"]
        letter = {0: "ROUTE A", 1: "ROUTE C", 2: "ROUTE B",
                  3: "LAST-KNOWN-STATE ROUTE", 4: "ROUTE B"}.get(order.index(stage_label_upper), "ROUTE")
        if stage_label_upper == "COMMUNICATION_LOST":
            return "LAST-KNOWN-STATE ROUTE"
        if stage_label_upper == "INITIAL":
            return "ROUTE A"
        if stage_label_upper == "RISK_UPDATE":
            return "ROUTE B"
        if stage_label_upper == "RECOVERY_FRESH":
            return "ROUTE B (after recovery)"
        return f"{letter} ({stage_label_upper})"
    return "ROUTE"


def plot_scenario(engine, opt, scenario: dict, asof, out_path: Path,
                  show: bool = False) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    region = engine.cfg["region"]
    lat0, lat1 = region["lat_min"], region["lat_max"]
    lon0, lon1 = region["lon_min"], region["lon_max"]
    mid_lat = (lat0 + lat1) / 2.0
    stages = scenario["stages"]
    multi_stage = len(stages) > 1

    fig, ax = plt.subplots(figsize=(11.0, 8.75))
    fig.suptitle(f"Scenario {scenario['key']}: {scenario['intent']}",
                 fontsize=13, fontweight="bold")
    ax.set_title(f"East Prydz Bay  ·  as-of {asof} (UTC)  ·  CRS {region['crs']}  ·  "
                 f"PROTOTYPE — NOT a navigational chart",
                 fontsize=8.5, color="0.35")

    # --- risk region mesh (from LAST stage's Phase 4 layer) ---
    _use = stages[-1]
    layer_last = _use[2]
    if layer_last and layer_last.get("cells"):
        lg = np.array([c["lon"] for c in layer_last["cells"]])
        lt = np.array([c["lat"] for c in layer_last["cells"]])
        sc = np.array([0 if c["class"] == "LOW" else (1 if c["class"] == "MODERATE" else 2)
                       for c in layer_last["cells"]])
        ax.scatter(lg, lt, c=sc, cmap="YlOrRd", s=16, alpha=0.32, linewidths=0, zorder=1)

    # --- risk corridors + positions for EVERY stage ---
    for idx, (_label, assessments, _layer, _res) in enumerate(stages):
        for a in assessments:
            color = CLASS_COLORS[a.risk_class]
            clat, clon = _circle_pts(a.forecast.pred_lat, a.forecast.pred_lon,
                                     a.corridor_radius_km)
            ax.fill(clon, clat, color=color, alpha=0.13, linewidth=0, zorder=2)
            elat, elon = _circle_pts(a.forecast.pred_lat, a.forecast.pred_lon,
                                     a.envelope_radius_km)
            ax.plot(elon, elat, color=color, linestyle="--", linewidth=1.0,
                    alpha=0.7, zorder=3)
            ax.scatter([a.forecast.pred_lon], [a.forecast.pred_lat], marker="*",
                       s=150, color=color, edgecolor="black", linewidth=0.5, zorder=5)
            ax.scatter([a.iceberg.lon], [a.iceberg.lat], marker="^", s=85,
                       color="#555b66", edgecolor="black", linewidth=0.5, zorder=4)

    # --- routes (one colour per stage) ---
    for idx, (_label, _ass, _layer, res) in enumerate(stages):
        if not res.route:
            continue
        rlons = [p[1] for p in res.route]
        rlats = [p[0] for p in res.route]
        color = STAGE_COLORS.get(_label, "#37474f")
        lw = 3.4 if len(stages) == 1 else 2.8
        ax.plot(rlons, rlats, color=color, linewidth=lw, solid_capstyle="round",
                zorder=6, alpha=0.95)
        ax.scatter([rlons[0]], [rlats[0]], marker="o", s=46, color=color,
                   edgecolor="white", linewidth=1.0, zorder=7)
        # destination arrow
        ax.scatter([rlons[-1]], [rlats[-1]], marker="o", s=46, color=color,
                   edgecolor="white", linewidth=1.0, zorder=7)

    # --- vessel start and destination ---
    s_lat, s_lon = scenario["start"]
    d_lat, d_lon = scenario["destination"]
    ax.scatter([s_lon], [s_lat], marker="s", s=120, color="#0d47a1",
               edgecolor="white", linewidth=0.9, zorder=8)
    ax.annotate("VESSEL (START)", (s_lon, s_lat), textcoords="offset points",
                xytext=(8, -18), fontsize=9, color="#0d47a1", fontweight="bold", zorder=9)
    ax.scatter([d_lon], [d_lat], marker="P", s=120, color="#1a237e",
               edgecolor="white", linewidth=0.9, zorder=8)
    ax.annotate("DESTINATION", (d_lon, d_lat), textcoords="offset points",
                xytext=(8, 9), fontsize=9, color="#1a237e", fontweight="bold", zorder=9)

    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.set_aspect(1.0 / math.cos(math.radians(mid_lat)))
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°S)")
    ax.grid(True, alpha=0.3, ls=":")

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = [Patch(fc="#2e7d32", alpha=0.45, label="RISK REGION (LOW)"),
               Patch(fc="#f9a825", alpha=0.45, label="RISK REGION (MODERATE)"),
               Patch(fc="#c62828", alpha=0.45, label="RISK REGION (HIGH / impassable)"),
               Line2D([0], [0], color="0.4", linestyle="--", lw=1.2,
                      label="UNCERTAINTY ENVELOPE (prototype — NOT exact boundary)"),
               Line2D([0], [0], marker="*", ls="none", markerfacecolor="0.35",
                      markersize=11, label="FORECAST POSITION"),
               Line2D([0], [0], marker="^", ls="none", markerfacecolor="#555b66",
                      markersize=10, label="OBSERVED POSITION"),
               Line2D([0], [0], marker="s", ls="none", markerfacecolor="#0d47a1",
                      markersize=9, label="VESSEL (START)"),
               Line2D([0], [0], marker="P", ls="none", markerfacecolor="#1a237e",
                      markersize=9, label="DESTINATION")]
    for idx, (_label, _ass, _layer, res) in enumerate(stages):
        if not res.route:
            continue
        color = STAGE_COLORS.get(_label, "#37474f")
        handles.append(Line2D([0], [0], color=color, linewidth=3,
                              label=_route_legend_label(_label, multi_stage)))
    ax.legend(handles=handles, loc="lower left", fontsize=7.5, framealpha=0.95)

    fig.text(0.99, 0.01,
             "DEMO / SYNTHETIC SCENARIO — NOT real observations.  "
             "PROTOTYPE DECISION-SUPPORT ILLUSTRATION, NOT a navigational chart.",
             ha="right", va="bottom", fontsize=8.5, color="#b71c1c",
             fontweight="bold", style="italic")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    return out_path


def plot_summary(engine, opt, demos: dict, asof, out_path: Path) -> Path:
    """2x3 summary figure for the whole demo (mirrors Phase 4 convention)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    region = engine.cfg["region"]
    mid_lat = (region["lat_min"] + region["lat_max"]) / 2.0
    fig, axes = plt.subplots(2, 3, figsize=(16, 9.5))
    for ax, (key, s) in zip(axes.ravel(), demos.items()):
        stages = s["stages"]
        for _label, _ass, layer, res in stages:
            if layer and layer.get("cells"):
                lg = np.array([c["lon"] for c in layer["cells"]])
                lt = np.array([c["lat"] for c in layer["cells"]])
                sc = np.array([0 if c["class"] == "LOW" else
                               (1 if c["class"] == "MODERATE" else 2)
                               for c in layer["cells"]])
                ax.scatter(lg, lt, c=sc, cmap="YlOrRd", s=10, alpha=0.25,
                           linewidths=0, zorder=1)
            if not res.route:
                continue
            ax.plot([p[1] for p in res.route], [p[0] for p in res.route],
                    color=STAGE_COLORS.get(_label, "#37474f"), linewidth=2.6,
                    solid_capstyle="round", zorder=6)
        ax.scatter([s["start"][1]], [s["start"][0]], marker="s", s=60,
                   color="#0d47a1", edgecolor="white", linewidth=0.7, zorder=8)
        ax.scatter([s["destination"][1]], [s["destination"][0]], marker="P", s=60,
                   color="#1a237e", edgecolor="white", linewidth=0.7, zorder=8)
        ax.set_xlim(region["lon_min"], region["lon_max"])
        ax.set_ylim(region["lat_min"], region["lat_max"])
        ax.set_aspect(1.0 / math.cos(math.radians(mid_lat)))
        ax.set_title(f"Scenario {key}: {s['intent']}", fontsize=8.5)
        ax.grid(True, alpha=0.3, ls=":")
        ax.tick_params(labelsize=7)
    axes[1, 2].axis("off")
    axes[1, 2].legend(handles=[
        Patch(fc="#2e7d32", alpha=0.45, label="RISK REGION (LOW)"),
        Patch(fc="#f9a825", alpha=0.45, label="RISK REGION (MODERATE)"),
        Patch(fc="#c62828", alpha=0.45, label="RISK REGION (HIGH / impassable)"),
        Line2D([0], [0], color="#1565c0", linewidth=3, label="ROUTE A (initial / fresh)"),
        Line2D([0], [0], color="#e65100", linewidth=3, label="ROUTE B (risk update)"),
        Line2D([0], [0], color="#6a1b9a", linewidth=3, label="LAST-KNOWN-STATE ROUTE"),
        Line2D([0], [0], color="#1b5e20", linewidth=3, label="ROUTE (after recovery)"),
        Line2D([0], [0], marker="s", ls="none", markerfacecolor="#0d47a1",
               markersize=9, label="VESSEL (START)"),
        Line2D([0], [0], marker="P", ls="none", markerfacecolor="#1a237e",
               markersize=9, label="DESTINATION"),
    ], loc="center", fontsize=8)
    axes[1, 2].text(0.5, 0.10,
                    "DEMO / SYNTHETIC SCENARIO — NOT real observations.\n"
                    "PROTOTYPE DECISION-SUPPORT ILLUSTRATION, NOT a navigational chart.",
                    ha="center", va="center", fontsize=8, color="#b71c1c",
                    fontweight="bold")
    fig.suptitle("Him-Drushti Phase 5 — Dynamic Multi-Objective Route Optimizer (synthetic demo)",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out_path