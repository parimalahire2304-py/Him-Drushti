#!/usr/bin/env python3
"""
PHASE 5 — DYNAMIC MULTI-OBJECTIVE ROUTE OPTIMIZER: SYNTHETIC DEMONSTRATION
==========================================================================

Runs the route optimizer on ONE deterministic multi-scenario demonstration of
the East Prydz Bay decision-support workflow, consuming the Phase 4 risk layer
for each scenario and producing a safer vessel route.

    ************************************************************
    *  DEMO / SYNTHETIC SCENARIO  —  NOT real observations.     *
    *  All iceberg / vessel positions below are FABRICATED for  *
    *  this demonstration only. Never mixed into scientific     *
    *  evaluation (Phase 3 / 3A / 3B / 3C untouched).           *
    ************************************************************

Scenarios:
  A  SAFE DIRECT           -> no significant risk on the direct path -> ~direct route
  B  BLOCKED DIRECT        -> synthetic high-risk corridor on the direct path -> detour
  C  MULTI-ICEBERG         -> multiple simultaneous risk regions -> combined field
                              threaded between impassable regions
  D  DYNAMIC REPLAN        -> Route A, then a NEW (synthetic) observation updates the
                              risk layer -> Route B rerouted, reasons reported
  E  COMMUNICATION LOSS    -> FRESH -> COMMUNICATION LOST -> LAST-KNOWN-STATE ROUTE
                              -> NEW OBSERVATION -> FRESH (recompute, compare)

Determinism: every timestamp is fixed (UTC); engine + optimizer deterministic;
figures deterministic (no randomness).

Outputs (machine-readable, existing formats preserved):
  outputs/routing/demo/routing_demo_manifest.json
  outputs/routing/demo/scenario_{A..E}.json
  outputs/routing/demo/scenario_{A..E}_routes.csv
  outputs/routing/figures/scenario_{A..E}.png
  outputs/routing/figures/routing_demo_summary.png

Usage:
    python scripts/routing/run_routing_demo.py
"""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Project modules (Phase 4 risk engine is consumed READ-ONLY from Phase 5).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))          # routing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "risk"))  # risk

from risk_engine import RiskEngine, IcebergState, Forecast, VesselState  # noqa: E402
from route_optimizer import RouteOptimizer  # noqa: E402
from visualize_route import plot_scenario, plot_summary  # noqa: E402

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

# Demo vessel geometry (synthetic). Region bbox: lat -70..-66, lon 72..80.
ROUTE_START_A = (-68.0, 76.0)      # (lat, lon)
ROUTE_DEST_A = (-67.2, 78.6)
ROUTE_START_B = (-69.2, 73.0)
ROUTE_DEST_B = (-67.2, 78.8)


def pt_at(lat: float, lon: float, d_km: float, bearing_deg: float) -> tuple[float, float]:
    """Deterministic synthetic position d_km from (lat, lon) on bearing (°)."""
    R = 6371.0088
    delta = d_km / R
    rlat = math.radians(lat); rlon = math.radians(lon)
    brng = math.radians(bearing_deg)
    tlat = math.asin(max(-1.0, min(1.0, math.sin(rlat) * math.cos(delta)
                                   + math.cos(rlat) * math.sin(delta) * math.cos(brng))))
    tlon = rlon + math.atan2(math.sin(brng) * math.sin(delta) * math.cos(rlat),
                             math.cos(delta) - math.sin(rlat) * math.sin(tlat))
    return math.degrees(tlat), math.degrees(tlon)


def forecast_for(iceberg: IcebergState, d_km: float, bearing_deg: float,
                 horizon_h: float) -> Forecast:
    flat, flon = pt_at(iceberg.lat, iceberg.lon, d_km, bearing_deg)
    return Forecast(iceberg_id=iceberg.iceberg_id, pred_lat=flat, pred_lon=flon,
                    valid_at=ASOF + timedelta(hours=horizon_h), horizon_hours=horizon_h,
                    source="persistence", source_note="synthetic demo forecast (Phase 3C reference source)")


def make_state(iid: str, lat: float, lon: float, age_h: float,
               length_nm: float = 10.0, width_nm: float = 6.0,
               source_note: str = "synthetic demo iceberg") -> IcebergState:
    return IcebergState(iid, lat, lon, observed_at=ASOF - timedelta(hours=age_h),
                        length_nm=length_nm, width_nm=width_nm, drifting=True,
                        synthetic=True, source_note=source_note)


def run_all(engine: RiskEngine, opt: RouteOptimizer) -> dict:
    demos: dict[str, dict] = {}

    # ---------------- A : SAFE DIRECT ROUTE ----------------
    # Two synthetic icebergs far from the direct path (~90+ km) -> LOW on route.
    vessel_a = VesselState(vessel_id="RV-DEMO", lat=ROUTE_START_A[0], lon=ROUTE_START_A[1],
                           at=ASOF, synthetic=True)
    a1 = make_state("DEMO-A1", *pt_at(ROUTE_START_A[0], ROUTE_START_A[1], 95.0, 190.0),
                    24.0, 6.0, 4.0, "synthetic far drifting iceberg (south of route)")
    a2 = make_state("DEMO-A2", *pt_at(ROUTE_START_A[0], ROUTE_START_A[1], 120.0, 0.0),
                    22.0, 8.0, 5.0, "synthetic far drifting iceberg (north of route)")
    fa1 = forecast_for(a1, 15.0, 200.0, 72.0)
    fa2 = forecast_for(a2, 12.0, 355.0, 72.0)
    ra = engine.evaluate([a1, a2], [fa1, fa2], vessel_a, ASOF)
    layer_a = engine.navigation_layer(ra)
    res_a = opt.solve(ROUTE_START_A, ROUTE_DEST_A, layer_a)
    demos["A"] = _scenario("A", "SAFE DIRECT ROUTE — no significant risk on direct path",
                           ROUTE_START_A, ROUTE_DEST_A, [("INITIAL", ra, layer_a, res_a)],
                           highest=ra[0])

    # ---------------- B : BLOCKED DIRECT ROUTE ----------------
    # Synthetic high-risk corridor centred on the direct path -> must detour.
    vessel_b = VesselState(vessel_id="RV-DEMO", lat=ROUTE_START_B[0], lon=ROUTE_START_B[1],
                           at=ASOF, synthetic=True)
    b = make_state("DEMO-B", -68.9, 75.9, 10.0, 14.0, 9.0,
                   "synthetic large drifting iceberg ON the direct path")
    fb = forecast_for(b, 8.0, 120.0, 72.0)
    rb = engine.evaluate([b], [fb], vessel_b, ASOF)
    layer_b = engine.navigation_layer(rb)
    res_b = opt.solve(ROUTE_START_B, ROUTE_DEST_B, layer_b)
    demos["B"] = _scenario("B", "BLOCKED DIRECT ROUTE — high-risk corridor on direct path",
                           ROUTE_START_B, ROUTE_DEST_B, [("INITIAL", rb, layer_b, res_b)],
                           highest=rb[0])

    # ---------------- C : MULTI-ICEBERG ----------------
    # Three synthetic icebergs create three simultaneous risk regions; the combined
    # field must be threaded between the impassable (HIGH) ones.
    vessel_c = VesselState(vessel_id="RV-DEMO", lat=ROUTE_START_B[0], lon=ROUTE_START_B[1],
                           at=ASOF, synthetic=True)
    c1 = make_state("DEMO-C1", -69.0, 75.7, 10.0, 14.0, 9.0, "synthetic barrier iceberg (middle)")
    c2 = make_state("DEMO-C2", -67.6, 77.2, 12.0, 13.0, 8.0, "synthetic north constraint iceberg")
    c3 = make_state("DEMO-C3", -69.4, 76.9, 14.0, 13.0, 8.0, "synthetic south constraint iceberg")
    fc1 = forecast_for(c1, 7.0, 115.0, 72.0)
    fc2 = forecast_for(c2, 6.0, 355.0, 96.0)
    fc3 = forecast_for(c3, 6.0, 150.0, 96.0)
    rc = engine.evaluate([c1, c2, c3], [fc1, fc2, fc3], vessel_c, ASOF)
    layer_c = engine.navigation_layer(rc)
    res_c = opt.solve(ROUTE_START_B, ROUTE_DEST_B, layer_c)
    demos["C"] = _scenario("C", "MULTI-ICEBERG — combined HIGH regions threaded",
                           ROUTE_START_B, ROUTE_DEST_B, [("INITIAL", rc, layer_c, res_c)],
                           highest=rc[0])

    # ---------------- D : DYNAMIC REPLAN ----------------
    # Stage 1: iceberg forecast far south -> Route A near-direct.
    # Stage 2: NEW (synthetic) observation moves forecast onto Route A -> reroute.
    vessel_d = VesselState(vessel_id="RV-DEMO", lat=ROUTE_START_B[0], lon=ROUTE_START_B[1],
                           at=ASOF, synthetic=True)
    d1 = make_state("DEMO-D", -69.6, 75.2, 14.0, 10.0, 6.0,
                    "synthetic drifting iceberg, initial forecast south of route")
    fd1 = forecast_for(d1, 5.0, 90.0, 72.0)
    rd1 = engine.evaluate([d1], [fd1], vessel_d, ASOF)
    layer_d1 = engine.navigation_layer(rd1)
    res_d1 = opt.solve(ROUTE_START_B, ROUTE_DEST_B, layer_d1)

    d2 = make_state("DEMO-D", -68.7, 76.0, 6.0, 10.0, 6.0,
                    "synthetic NEW observation: iceberg advanced onto Route A")
    fd2 = forecast_for(d2, 7.0, 110.0, 72.0)
    rd2 = engine.evaluate([d2], [fd2], vessel_d, ASOF)
    layer_d2 = engine.navigation_layer(rd2)
    res_d2 = opt.solve(ROUTE_START_B, ROUTE_DEST_B, layer_d2)
    demos["D"] = _scenario(
        "D", "DYNAMIC REPLAN — risk update reroutes A -> B",
        ROUTE_START_B, ROUTE_DEST_B,
        [("INITIAL", rd1, layer_d1, res_d1), ("RISK_UPDATE", rd2, layer_d2, res_d2)],
        highest=rd2[0],
        replan_stage="RISK_UPDATE",
        replanning_reason="New/updated iceberg risk intersects original route A "
                          "(updated forecast corridor covers Route A segments).")

    # ---------------- E : COMMUNICATION LOSS ----------------
    # Stage 1 FRESH -> Stage 2 COMMUNICATION LOST (LAST-KNOWN-STATE, corridor expands)
    # -> stage 3 NEW OBSERVATION (FRESH, recompute). Route stays operational throughout.
    vessel_e = VesselState(vessel_id="RV-DEMO", lat=ROUTE_START_B[0], lon=ROUTE_START_B[1],
                           at=ASOF, synthetic=True)
    e1 = make_state("DEMO-E", -69.2, 75.0, 8.0, 12.0, 8.0,
                    "synthetic iceberg, FRESH observation (stage 1)")
    fe1 = forecast_for(e1, 6.0, 100.0, 72.0)
    re1 = engine.evaluate([e1], [fe1], vessel_e, ASOF)
    layer_e1 = engine.navigation_layer(re1)
    res_e1 = opt.solve(ROUTE_START_B, ROUTE_DEST_B, layer_e1,
                       communication_status="NOMINAL", data_freshness="FRESH")

    # COMMUNICATION LOST: same last-known state, observed_at now 400 h old -> Phase 4
    # engine enters LAST-KNOWN-STATE MODE and grows the corridor (no invented obs).
    e2 = make_state("DEMO-E", -69.2, 75.0, 400.0, 12.0, 8.0,
                    "LAST known state (no new observations during comm loss)")
    fe2 = forecast_for(e2, 6.0, 100.0, 72.0)
    re2 = engine.evaluate([e2], [fe2], vessel_e, ASOF)
    layer_e2 = engine.navigation_layer(re2)
    res_e2 = opt.solve(ROUTE_START_B, ROUTE_DEST_B, layer_e2,
                       communication_status="COMMUNICATION LOST",
                       data_freshness="LAST-KNOWN-STATE MODE")

    # RECOVERY: a NEW synthetic observation arrives -> FRESH -> recompute + reroute.
    e3 = make_state("DEMO-E", -69.1, 75.3, 7.0, 12.0, 8.0,
                    "synthetic NEW observation after recovery (FRESH)")
    fe3 = forecast_for(e3, 6.0, 100.0, 72.0)
    re3 = engine.evaluate([e3], [fe3], vessel_e, ASOF)
    layer_e3 = engine.navigation_layer(re3)
    res_e3 = opt.solve(ROUTE_START_B, ROUTE_DEST_B, layer_e3,
                       communication_status="NOMINAL", data_freshness="FRESH")
    demos["E"] = _scenario(
        "E", "COMMUNICATION LOSS — LAST-KNOWN-STATE ROUTE, then recovery recompute",
        ROUTE_START_B, ROUTE_DEST_B,
        [("FRESH", re1, layer_e1, res_e1),
         ("COMMUNICATION_LOST", re2, layer_e2, res_e2),
         ("RECOVERY_FRESH", re3, layer_e3, res_e3)],
        highest=re2[0],
        replan_stage="RECOVERY_FRESH",
        replanning_reason="New observation received: risk layer recomputed (FRESH); routing re-run and compared with LAST-KNOWN-STATE ROUTE.")

    return demos


def _scenario(key: str, intent: str, start: tuple[float, float],
              dest: tuple[float, float], stages: list[tuple[str, list, dict, object]],
              highest, replan_stage: str | None = None,
              replanning_reason: str = "") -> dict:
    """Package a scenario: stages carry (label, assessments, layer, route result)."""
    return {
        "key": key, "intent": intent,
        "start": start, "destination": dest,
        "stages": stages, "highest": highest,
        "replan_stage": replan_stage, "replanning_reason": replanning_reason,
    }


def payload_for(engine: RiskEngine, opt: RouteOptimizer, scenario: dict) -> dict:
    """Build the machine-readable scenario JSON (spec §16)."""
    stages = scenario["stages"]
    risk_scores = [a.risk_score for _, ass, _, _ in stages for a in ass]
    comms = sorted({a.communication_status for _, ass, _, _ in stages for a in ass})
    freshs = sorted({a.data_freshness for _, ass, _, _ in stages for a in ass})
    stage_records = []
    for label, ass, layer, res in stages:
        # risk summary of the Phase 4 layer consumed by the router
        risk = [{"iceberg_id": a.iceberg.iceberg_id, "risk_score": round(a.risk_score, 4),
                 "risk_class": a.risk_class,
                 "corridor_radius_km": round(a.corridor_radius_km, 2),
                 "data_freshness": a.data_freshness,
                 "communication_status": a.communication_status}
                for a in ass]
        stage_records.append({
            "stage": label,
            "risk_consumed": {"n_cells_above_threshold": layer["n_cells_above_threshold"],
                              "covered_cells": layer["covered_cells"],
                              "grid_resolution_degrees": layer["grid_resolution_degrees"],
                              "crs": layer["crs"],
                              "iceberg_risk_summary": risk},
            "route_result": res.to_dict(),
        })
    speed = opt.cfg["vessel"]["speed_knots_default"]
    speed_kmh = speed * float(opt.cfg["vessel"]["knots_to_kmh"])
    return {
        "schema": "him_drushti.route_optimizer.demo.v1",
        "demo_or_synthetic": True,
        "demo_label": "DEMO / SYNTHETIC SCENARIO — NOT real observations",
        "asof": ASOF.isoformat(timespec="seconds"),
        "scenario": scenario["key"],
        "intent": scenario["intent"],
        "vessel": {"vessel_id": "RV-DEMO", "speed_knots": speed, "speed_kmh": speed_kmh,
                   "start": {"lat": scenario["start"][0], "lon": scenario["start"][1]},
                   "destination": {"lat": scenario["destination"][0], "lon": scenario["destination"][1]}},
        "risk_source": "scripts/risk/risk_engine.py navigation_layer (consumed as-is)",
        "route_optimizer": "scripts/routing/route_optimizer.py",
        "config": "scripts/routing/routing_config.yaml",
        "communication_status": comms,
        "data_freshness": freshs,
        "highest_risk_score": round(max(risk_scores), 4) if risk_scores else None,
        "stages": stage_records,
        "replan_stage": scenario["replan_stage"],
        "replanning_reason": scenario["replanning_reason"],
        "labels": opt.cfg["output"]["labels"],
        "used_inputs": {
            "risk_layer (Phase 4 navigation_layer)": True,
            "vessel speed (config/vessel.yaml, RV-DEMO 12 kn)": True,
            "environmental layer": False,
            "note": "No new datasets downloaded; environment cost = 0 in every demo.",
        },
    }


def main() -> int:
    print(BANNER)
    engine = RiskEngine()
    opt = RouteOptimizer()
    demos = run_all(engine, opt)

    demo_dir = PROJECT_ROOT / "outputs" / "routing" / "demo"
    fig_dir = PROJECT_ROOT / "outputs" / "routing" / "figures"
    demo_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "demo_label": "DEMO / SYNTHETIC SCENARIO — NOT real observations",
        "asof": ASOF.isoformat(timespec="seconds"),
        "engine": "scripts/routing/route_optimizer.py",
        "config": "scripts/routing/routing_config.yaml",
        "phase4_risk_engine": "scripts/risk/risk_engine.py",
        "scenarios": {},
    }

    for key in ["A", "B", "C", "D", "E"]:
        s = demos[key]
        payload = payload_for(engine, opt, s)
        js_path = demo_dir / f"scenario_{key}.json"
        csv_path = demo_dir / f"scenario_{key}_routes.csv"
        js_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        _write_csv(scenario=s, csv_path=csv_path, opt=opt)
        fig_path = fig_dir / f"scenario_{key}.png"
        plot_scenario(engine, opt, s, ASOF, fig_path)

        stage_summary = []
        for label, _ass, layer, res in s["stages"]:
            m = res.metrics
            stage_summary.append({
                "stage": label,
                "status": res.status, "route_label": res.route_label,
                "route_km": round(m["route_distance_km"], 2),
                "direct_km": round(m["direct_distance_km"], 2),
                "overhead_pct": (round(m["distance_overhead_pct"], 2)
                                 if m["distance_overhead_pct"] is not None else None),
                "time_h": round(m["estimated_travel_time_hours"], 2),
                "max_risk": round(m["max_risk_score_encountered"], 2),
                "n_high": m["n_high_risk_cells_encountered"],
                "n_mod": m["n_moderate_risk_cells_encountered"],
                "cum_risk": round(m["cumulative_risk_cost"], 2),
                "comm": res.communication_status,
                "fresh": res.data_freshness,
            })
        manifest["scenarios"][key] = {
            "intent": s["intent"],
            "json": f"outputs/routing/demo/scenario_{key}.json",
            "csv": f"outputs/routing/demo/scenario_{key}_routes.csv",
            "figure": f"outputs/routing/figures/scenario_{key}.png",
            "stages": stage_summary,
            "replanning_reason": s["replanning_reason"],
        }
        print(f"\nScenario {key}: {s['intent']}")
        for row in stage_summary:
            overtxt = f"{row['overhead_pct']}%" if row["overhead_pct"] is not None else "n/a"
            print(f"  [{row['stage']}] {row['status']:9s} {row['route_label']:22s} "
                  f"route={row['route_km']:7.2f}km direct={row['direct_km']:7.2f}km "
                  f"overhead={overtxt:7s} time~{row['time_h']:5.2f}h maxrisk={row['max_risk']:5.2f} "
                  f"high={row['n_high']} mod={row['n_mod']} comm={row['comm']} ({row['fresh']})")
        if s["replanning_reason"]:
            print(f"    replan reason: {s['replanning_reason']}")

    (demo_dir / "routing_demo_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    summary_fig = fig_dir / "routing_demo_summary.png"
    plot_summary(engine, opt, demos, ASOF, summary_fig)

    print(f"\nManifest: {demo_dir / 'routing_demo_manifest.json'}")
    print(f"Figures : {fig_dir}  (summary -> {summary_fig.name})")
    return 0


def _write_csv(scenario: dict, csv_path: Path, opt: RouteOptimizer) -> None:
    """One row per route stage (machine-readable, spec §16)."""
    base = {
        "scenario": scenario["key"],
        "intent": scenario["intent"],
        "asof": ASOF.isoformat(timespec="seconds"),
        "start_lat": scenario["start"][0], "start_lon": scenario["start"][1],
        "destination_lat": scenario["destination"][0],
        "destination_lon": scenario["destination"][1],
    }
    rows = []
    for label, _ass, _layer, res in scenario["stages"]:
        row = {**base, "stage": label}
        row.update(res.to_csv_row())
        row.pop("schema", None)
        row.pop("timestamp", None)
        rows.append(row)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())