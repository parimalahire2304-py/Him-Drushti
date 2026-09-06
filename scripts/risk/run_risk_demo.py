#!/usr/bin/env python3
"""
PHASE 4 — UNCERTAINTY-AWARE RISK ENGINE: SYNTHETIC DEMONSTRATION

Runs the risk engine on ONE deterministic multi-scenario demonstration of the
East Prydz Bay decision-support workflow.

    ************************************************************
    *  DEMO / SYNTHETIC SCENARIO  —  NOT real observations.     *
    *  All iceberg / vessel positions below are fabricated,     *
    *  labelled SYNTHETIC, and used ONLY to exercise the         *
    *  engine. They are NOT mixed into any scientific           *
    *  evaluation (Phase 3 / 3A / 3B / 3C remain untouched).    *
    ************************************************************

Scenarios:
  A  SAFE SEPARATION            -> LOW / MODERATE classes
  B  ICEBERG APPROACHES         -> HIGH
  C  UNCERTAINTY EXPANDS        -> corridor expands with forecast horizon
  D  COMMUNICATION LOST         -> LAST-KNOWN-STATE MODE, COMMUNICATION LOST
  E  COMMUNICATION RETURNS      -> new observation -> FRESH -> recompute

Determinism: every timestamp is fixed (UTC); the engine is deterministic;
figures are deterministic (fixed seed not needed — no randomness).

Outputs (machine-readable, existing formats preserved):
  outputs/risk/demo/demo_manifest.json        (index + scenario intents)
  outputs/risk/demo/scenario_{A..E}.json      (full payload incl. nav layer)
  outputs/risk/demo/scenario_{A..E}_risk_output.csv
  outputs/risk/figures/scenario_{A..E}.png
  outputs/risk/figures/risk_demo_summary.png

Usage:
    python scripts/risk/run_risk_demo.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Project modules
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from risk_engine import (  # noqa: E402
    PROJECT_ROOT as _ROOT, RiskEngine, Forecast, IcebergState, VesselState,
)
from visualize_risk import plot_assessments  # noqa: E402

BANNER = """
    ************************************************************
    *  DEMO / SYNTHETIC SCENARIO  —  NOT real observations.     *
    *  All iceberg & vessel positions are FABRICATED for this   *
    *  demonstration only. Never mixed into scientific          *
    *  evaluation (Phase 3 / 3A / 3B / 3C untouched).           *
    ************************************************************
"""

# Fixed, deterministic "operation time" (UTC). A 2025 date inside the Phase 3C
# supported/test window; deliberately NOT 2026 (see Phase 3C constraints).
ASOF = datetime(2025, 11, 12, 12, 0, 0, tzinfo=timezone.utc)


def vessel_of(engine: RiskEngine) -> VesselState:
    v = engine.cfg["vessel_defaults"]
    return VesselState(vessel_id=v["vessel_id"], draft_m=v["draft_m"],
                       speed_knots=v["speed_knots"], heading_deg=v["heading_deg"],
                       synthetic=True)


def pt_at(lat: float, lon: float, d_km: float, bearing_deg: float) -> tuple[float, float]:
    """Deterministic synthetic position d_km from (lat, lon) on bearing (°)."""
    import math
    # Spherical law of cosines destination (accurate enough for < 200 km)
    R = 6371.0088
    delta = d_km / R
    rlat = math.radians(lat)
    rlon = math.radians(lon)
    brng = math.radians(bearing_deg)
    tlat = math.asin(max(-1.0, min(1.0,
           math.sin(rlat) * math.cos(delta) +
           math.cos(rlat) * math.sin(delta) * math.cos(brng))))
    tlon = rlon + math.atan2(
        math.sin(brng) * math.sin(delta) * math.cos(rlat),
        math.cos(delta) - math.sin(rlat) * math.sin(tlat))
    return math.degrees(tlat), math.degrees(tlon)


def forecast_for(engine: RiskEngine, iceberg_id: str, from_state: IcebergState,
                 d_km: float, bearing_deg: float, horizon_h: float,
                 source: str = "persistence") -> Forecast:
    """Deterministic forecast: persistence of the state + d_km (synthetic)."""
    flat, flon = pt_at(from_state.lat, from_state.lon, d_km, bearing_deg)
    return Forecast(iceberg_id=iceberg_id, pred_lat=flat, pred_lon=flon,
                    valid_at=ASOF + timedelta(hours=horizon_h), horizon_hours=horizon_h,
                    source=source, source_note="synthetic demo forecast")


def run_all() -> dict[str, dict]:
    engine = RiskEngine()
    vessel = vessel_of(engine)
    demos: dict[str, dict] = {}

    # ---------- Scenario A : safe separation -> LOW / MODERATE ----------
    # Vessel fixed; forecasts placed at exact distances (synthetic).
    vessel_a = VesselState(vessel_id=vessel.vessel_id, lat=-67.8, lon=74.05, at=ASOF,
                           synthetic=True)
    f_a1_lat, f_a1_lon = pt_at(vessel_a.lat, vessel_a.lon, 100.0, 210.0)   # 100 km -> LOW
    f_a2_lat, f_a2_lon = pt_at(vessel_a.lat, vessel_a.lon, 44.0, 215.0)    #  44 km -> MODERATE
    a1_lat, a1_lon = pt_at(f_a1_lat, f_a1_lon, 25.0, 30.0)
    a2_lat, a2_lon = pt_at(f_a2_lat, f_a2_lon, 20.0, 35.0)
    a1 = IcebergState("DEMO-A1", lat=a1_lat, lon=a1_lon, observed_at=ASOF - timedelta(hours=24),
                      length_nm=6.0, width_nm=4.0, drifting=True, synthetic=True,
                      source_note="synthetic far drifting iceberg")
    a2 = IcebergState("DEMO-A2", lat=a2_lat, lon=a2_lon, observed_at=ASOF - timedelta(hours=22),
                      length_nm=10.0, width_nm=6.0, drifting=True, synthetic=True,
                      source_note="synthetic closer drifting iceberg")
    fa1 = Forecast("DEMO-A1", f_a1_lat, f_a1_lon, ASOF + timedelta(hours=72), 72.0,
                   "persistence", "synthetic demo forecast")
    fa2 = Forecast("DEMO-A2", f_a2_lat, f_a2_lon, ASOF + timedelta(hours=72), 72.0,
                   "persistence", "synthetic demo forecast")
    ra = engine.evaluate([a1, a2], [fa1, fa2], vessel_a, ASOF)
    layer_a = engine.navigation_layer([r for r in ra])
    demos["A"] = {"intent": "SAFE SEPARATION -> LOW / MODERATE",
                  "assessments": ra, "layer": layer_a, "vessel": vessel_a,
                  "forecasts": [fa1, fa2], "states": [a1, a2]}

    # ---------- Scenario B : iceberg approaches -> HIGH ----------
    b = IcebergState("DEMO-B", lat=-68.0, lon=76.2, observed_at=ASOF - timedelta(hours=24),
                     length_nm=12.0, width_nm=8.0, drifting=True, synthetic=True)
    fb = forecast_for(engine, "DEMO-B", b, d_km=5.0, bearing_deg=135.0, horizon_h=72.0)
    vessel_b = VesselState(vessel_id=vessel.vessel_id, lat=-68.05, lon=76.28, at=ASOF,
                           synthetic=True)   # ~5-6 km from forecast
    rb = engine.evaluate([b], [fb], vessel_b, ASOF)
    demos["B"] = {"intent": "ICEBERG APPROACHES -> HIGH",
                  "assessments": rb, "layer": engine.navigation_layer(rb),
                  "vessel": vessel_b, "forecasts": [fb], "states": [b]}

    # ---------- Scenario C : uncertainty expands -> corridor expands ----------
    vessel_c = VesselState(vessel_id=vessel.vessel_id, lat=-68.05, lon=76.28, at=ASOF,
                           synthetic=True)
    c1 = IcebergState("DEMO-C1", lat=-68.1, lon=76.15, observed_at=ASOF - timedelta(hours=24),
                      length_nm=12.0, width_nm=8.0, drifting=True, synthetic=True)
    c2 = IcebergState("DEMO-C2", lat=-68.1, lon=76.15, observed_at=ASOF - timedelta(hours=24),
                      length_nm=12.0, width_nm=8.0, drifting=True, synthetic=True)
    f_c_lat, f_c_lon = pt_at(vessel_c.lat, vessel_c.lon, 8.0, 210.0)
    fc1 = Forecast("DEMO-C1", f_c_lat, f_c_lon, ASOF + timedelta(hours=72), 72.0,
                   "persistence", "synthetic demo forecast")
    fc2 = Forecast("DEMO-C2", f_c_lat, f_c_lon, ASOF + timedelta(hours=168), 168.0,
                   "persistence", "synthetic demo forecast")
    rc1 = engine.assess(c1, fc1, vessel_c, ASOF)
    rc2 = engine.assess(c2, fc2, vessel_c, ASOF)
    rc = sorted([rc1, rc2], key=lambda r: -r.risk_score)
    demos["C"] = {"intent": "UNCERTAINTY EXPANDS -> corridor expands (72h vs 168h)",
                  "assessments": rc, "layer": engine.navigation_layer(rc),
                  "vessel": vessel_c, "forecasts": [fc1, fc2], "states": [c1, c2]}

    # ---------- Scenario D : communication lost -> LAST-KNOWN-STATE MODE ----------
    d = IcebergState("DEMO-D", lat=-68.0, lon=76.2, observed_at=ASOF - timedelta(hours=400),
                     length_nm=12.0, width_nm=8.0, drifting=True, synthetic=True,
                     source_note="last valid state BEFORE comm loss")
    fd = forecast_for(engine, "DEMO-D", d, d_km=5.0, bearing_deg=135.0, horizon_h=72.0)
    vessel_d = VesselState(vessel_id=vessel.vessel_id, lat=-68.05, lon=76.28, at=ASOF,
                           synthetic=True)
    rd = engine.evaluate([d], [fd], vessel_d, ASOF)
    demos["D"] = {"intent": "COMMUNICATION LOST -> LAST-KNOWN-STATE MODE",
                  "assessments": rd, "layer": engine.navigation_layer(rd),
                  "vessel": vessel_d, "forecasts": [fd], "states": [d]}

    # ---------- Scenario E : communication returns -> recovery recompute ----------
    e = IcebergState("DEMO-E", lat=-67.95, lon=76.18, observed_at=ASOF - timedelta(hours=6),
                     length_nm=12.0, width_nm=8.0, drifting=True, synthetic=True,
                     source_note="NEW observation received after comm loss")
    fe = forecast_for(engine, "DEMO-E", e, d_km=4.0, bearing_deg=140.0, horizon_h=72.0)
    vessel_e = VesselState(vessel_id=vessel.vessel_id, lat=-68.05, lon=76.28, at=ASOF,
                           synthetic=True)
    re_ = engine.evaluate([e], [fe], vessel_e, ASOF)
    demos["E"] = {"intent": "COMMUNICATION RETURNS -> FRESH -> risk recomputed",
                  "assessments": re_, "layer": engine.navigation_layer(re_),
                  "vessel": vessel_e, "forecasts": [fe], "states": [e]}

    return demos


def main() -> int:
    print(BANNER)
    engine = RiskEngine()
    demos = run_all()

    demo_dir = PROJECT_ROOT / "outputs" / "risk" / "demo"
    fig_dir = PROJECT_ROOT / "outputs" / "risk" / "figures"
    demo_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "demo_label": "DEMO / SYNTHETIC SCENARIO — NOT real observations",
        "asof": ASOF.isoformat(timespec="seconds"),
        "engine": "scripts/risk/risk_engine.py",
        "config": "scripts/risk/risk_config.yaml",
        "scenarios": {},
        "uncertainty_note": engine.cfg["uncertainty"]["envelope_note"],
    }

    for key in ["A", "B", "C", "D", "E"]:
        s = demos[key]
        payload, rows = engine.build_outputs(s["assessments"], s["layer"], ASOF)
        js_path = demo_dir / f"scenario_{key}.json"
        csv_path = demo_dir / f"scenario_{key}_risk_output.csv"
        js_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        import csv as _csv
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            if rows:
                w = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
        fig_path = fig_dir / f"scenario_{key}.png"
        plot_assessments(s["assessments"], s["layer"], engine.cfg,
                         ASOF.isoformat(timespec="seconds"),
                         f"Demo scenario {key}: {s['intent']}", fig_path)

        summary = [(f"{a.iceberg.iceberg_id}", a.risk_class,
                    round(a.risk_score, 2), round(a.corridor_radius_km, 1),
                    a.data_freshness, a.communication_status)
                   for a in s["assessments"]]
        manifest["scenarios"][key] = {
            "intent": s["intent"],
            "json": f"outputs/risk/demo/scenario_{key}.json",
            "csv": f"outputs/risk/demo/scenario_{key}_risk_output.csv",
            "figure": f"outputs/risk/figures/scenario_{key}.png",
            "summary": summary,
        }
        print(f"  Scenario {key}: {s['intent']}")
        for row in summary:
            print(f"    {row[0]:9s} {row[1]:9s} score={row[2]:6.2f} "
                  f"corridor={row[3]:6.1f} km  {row[4]:22s} {row[5]}")

    (demo_dir / "demo_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    _summary_figure(demos, engine)
    print(f"\nManifest: {demo_dir / 'demo_manifest.json'}")
    print(f"Figures : {fig_dir}")
    return 0


def _summary_figure(demos: dict[str, dict], engine: RiskEngine) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    from visualize_risk import CLASS_COLORS, _circle_pts

    region = engine.cfg["region"]
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for ax, (key, s) in zip(axes.ravel(), demos.items()):
        v = s["vessel"]
        for a in s["assessments"]:
            c = CLASS_COLORS[a.risk_class]
            clat, clon = _circle_pts(a.forecast.pred_lat, a.forecast.pred_lon, a.corridor_radius_km)
            ax.fill(clon, clat, color=c, alpha=0.15, zorder=2)
            elat, elon = _circle_pts(a.forecast.pred_lat, a.forecast.pred_lon, a.envelope_radius_km)
            ax.plot(elon, elat, "--", color=c, lw=1.1, zorder=3)
            ax.scatter([a.forecast.pred_lon], [a.forecast.pred_lat], marker="*", c=c,
                       s=90, edgecolor="k", linewidth=0.5, zorder=5)
            ax.scatter([a.iceberg.lon], [a.iceberg.lat], marker="^", c="#555b66",
                       s=60, edgecolor="k", linewidth=0.5, zorder=4)
        ax.scatter([v.lon], [v.lat], marker="s", c="#1565c0", s=70,
                   edgecolor="k", linewidth=0.6, zorder=6)
        ax.set_xlim(region["lon_min"], region["lon_max"])
        ax.set_ylim(region["lat_min"], region["lat_max"])
        ax.set_aspect(1.0 / __import__("math").cos(__import__("math").radians((region["lat_min"] + region["lat_max"]) / 2)))
        ax.set_title(f"Scenario {key}: {s['intent']}", fontsize=9)
        ax.grid(True, alpha=0.3, ls=":")
        ax.tick_params(labelsize=7)
    axes[1, 2].axis("off")
    axes[1, 2].legend(handles=[
        Patch(fc=CLASS_COLORS[k], alpha=0.5, label=f"RISK CORRIDOR ({k})") for k in CLASS_COLORS
    ] + [
        Line2D([0], [0], marker="*", ls="none", markerfacecolor="0.35", label="FORECAST POSITION"),
        Line2D([0], [0], marker="^", ls="none", markerfacecolor="#555b66", label="OBSERVED POSITION"),
        Line2D([0], [0], marker="s", ls="none", markerfacecolor="#1565c0", label="VESSEL"),
        Line2D([0], [0], color="0.4", ls="--", label="UNCERTAINTY ENVELOPE (NOT an exact boundary)"),
    ], loc="center", fontsize=8)
    axes[1, 2].text(0.5, 0.12, "DEMO / SYNTHETIC SCENARIO\nNOT real observations",
                    ha="center", va="center", fontsize=9, color="#b71c1c",
                    fontweight="bold", transform=axes[1, 2].transAxes)
    fig.suptitle("Him-Drushti Phase 4 — Uncertainty-Aware Risk Engine (synthetic demo)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = PROJECT_ROOT / "outputs" / "risk" / "figures" / "risk_demo_summary.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())