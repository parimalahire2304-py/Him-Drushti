#!/usr/bin/env python3
"""
PHASE 3G → PHASE 4/5 INTEGRATION — CONTROLLED DEMONSTRATIONS
==============================================================

Two controlled demos showing the forecasting → risk → routing pipeline
with the Motion-aware XGBoost candidate model and its mandatory
Persistence fallback.

ABSOLUTE CONSTRAINTS:
- All positions are SYNTHETIC / DEMO — NOT real observations
- Motion-aware XGBoost labeled "CANDIDATE IMPROVED FORECAST"
- Persistence fallback labeled "PERSISTENCE FALLBACK"
- Never "proven best", "operationally validated", "guaranteed accurate"
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "integration"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "risk"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "routing"))

from forecast import ForecastEngine, build_observation_from_row  # noqa: E402
from risk_engine import RiskEngine, IcebergState, Forecast, VesselState  # noqa: E402
from route_optimizer import RouteOptimizer  # noqa: E402

# ─── Fixed demo parameters ──────────────────────────────────────────────────
ASOF = datetime(2025, 11, 12, 12, 0, 0, tzinfo=timezone.utc)
DEMO_REGION = {"lat_min": -70.0, "lat_max": -66.0, "lon_min": 72.0, "lon_max": 80.0}

BANNER = """
    ************************************************************
    *  DEMO / SYNTHETIC SCENARIO  —  NOT real observations.     *
    *  All iceberg & vessel positions are FABRICATED for this   *
    *  demonstration only. Never mixed into scientific          *
    *  evaluation (Phase 3 / 3A / 3B / 3C / 3G untouched).     *
    *  Motion-aware XGBoost: CANDIDATE IMPROVED FORECAST MODEL  *
    *  Persistence: MANDATORY FALLBACK                          *
    ************************************************************
"""


def pt_at(lat: float, lon: float, d_km: float, bearing_deg: float) -> tuple[float, float]:
    """Deterministic synthetic position d_km from (lat, lon) on bearing (°).

    Mirrors scripts/routing/run_routing_demo.py so demo geometry is placed well
    clear of the navigable route (safe-route configuration, sigma≈50 km).
    """
    R = 6371.0088
    delta = d_km / R
    rlat = math.radians(lat)
    rlon = math.radians(lon)
    brng = math.radians(bearing_deg)
    tlat = math.asin(max(-1.0, min(1.0, math.sin(rlat) * math.cos(delta)
                                   + math.cos(rlat) * math.sin(delta) * math.cos(brng))))
    tlon = rlon + math.atan2(math.sin(brng) * math.sin(delta) * math.cos(rlat),
                             math.cos(delta) - math.sin(rlat) * math.sin(tlat))
    return math.degrees(tlat), math.degrees(tlon)


def _print_route(route_res, indent: str = "    ") -> None:
    """Print route result, tolerating NO_SAFE_ROUTE_FOUND (None metrics)."""
    for key, label in (
        ("route_distance_km", "Route distance"),
        ("direct_distance_km", "Direct distance"),
        ("distance_overhead_pct", "Overhead"),
        ("max_risk_score_encountered", "Max risk on route"),
    ):
        val = route_res.metrics.get(key)
        if isinstance(val, (int, float)):
            print(f"{indent}{label}: {val:.1f}"
                  + ("%" if key == "distance_overhead_pct" else " km" if "distance" in key else ""))
        else:
            print(f"{indent}{label}: n/a")
    print(f"{indent}Route waypoints: {len(route_res.route)}")
    if route_res.no_route_reason:
        print(f"{indent}No-route reason: {route_res.no_route_reason}")


def _synthetic_observation(
    iceberg_id: str,
    lat: float, lon: float,
    *,
    age_hours: float = 24.0,
    has_predecessor: bool = True,
    length_nm: float = 10.0,
    width_nm: float = 6.0,
) -> dict:
    """Create a synthetic observation dict with or without predecessor features."""
    # Base environmental features (simplified — real values come from feature stacks)
    base_env = {
        "lat": lat, "lon": lon,
        "iceberg_length_nm": length_nm, "iceberg_width_nm": width_nm,
        "sea_ice_concentration": 0.3,
        "wind_u_10m": 2.0, "wind_v_10m": -1.0,
        "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
        "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
        "ocean_current_u": 0.05, "ocean_current_v": -0.02,
        "wind_speed": 2.24, "wind_dir": 116.6,
        "ocean_speed": 0.054, "ocean_dir": 111.8,
        "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
    }
    if has_predecessor:
        # Legitimate predecessor: 7-day displacement ~10 km NE
        base_env.update({
            "prev_delta_lat": 0.08,   # ~9 km north
            "prev_delta_lon": 0.12,   # ~10 km east
            "prev_speed": 1.5,        # km/day
            "prev_bearing": 56.3,     # degrees
        })
    else:
        base_env.update({
            "prev_delta_lat": float("nan"),
            "prev_delta_lon": float("nan"),
            "prev_speed": float("nan"),
            "prev_bearing": float("nan"),
        })
    base_env["iceberg_id"] = iceberg_id
    return base_env


def _forecast_to_phase4(engine: ForecastEngine, obs: dict, source_note: str) -> Forecast:
    """Convert ForecastResult to Phase 4 Forecast dataclass."""
    res = engine.forecast_iceberg(obs)
    # forecast_method already tells us the source
    return Forecast(
        iceberg_id=obs["iceberg_id"],
        pred_lat=res.forecast_lat,
        pred_lon=res.forecast_lon,
        valid_at=ASOF + timedelta(days=res.horizon_days),
        horizon_hours=float(res.horizon_days * 24),
        source=res.model_name,  # "motion_aware_xgb" or "persistence"
        source_note=source_note,
    )


def _print_forecast_summary(label: str, res, obs: dict) -> None:
    print(f"\n  {label}")
    print(f"    Iceberg: {obs['iceberg_id']}")
    print(f"    Current position: ({obs['lat']:.5f}, {obs['lon']:.5f})")
    if res.predecessor_available:
        print(f"    Predecessor Δ: ({obs['prev_delta_lat']:.5f}, {obs['prev_delta_lon']:.5f})")
        print(f"    Predecessor speed: {obs['prev_speed']:.2f} km/day, bearing: {obs['prev_bearing']:.1f}°")
    else:
        print(f"    Predecessor: NOT AVAILABLE")
    print(f"    → Forecast position: ({res.forecast_lat:.5f}, {res.forecast_lon:.5f})")
    print(f"    → Method: {res.forecast_method}")
    print(f"    → Model: {res.model_name}")
    if res.fallback_reason:
        print(f"    → Fallback reason: {res.fallback_reason}")
    print(f"    → Candidate status: {'CANDIDATE IMPROVED FORECAST' if res.forecast_method == 'MOTION_AWARE_XGBOOST' else 'PERSISTENCE FALLBACK (mandatory)'}")


def run_demo_a() -> dict:
    """Demo A: Predecessor available → Motion-aware XGBoost selected."""
    print("=" * 70)
    print("DEMO A — PREDECESSOR AVAILABLE → MOTION-AWARE XGBOOST SELECTED")
    print("=" * 70)

    engine = ForecastEngine()
    risk_engine = RiskEngine()
    route_opt = RouteOptimizer()

    # Synthetic observation WITH valid predecessor. Iceberg placed ~95 km south
    # of the route (mirrors routing demo scenario A) so the risk envelope
    # (sigma ≈ 50 km) never blocks a safe route.
    route_start = (-68.0, 76.0)
    route_dest = (-67.2, 78.6)
    ice_lat, ice_lon = pt_at(route_start[0], route_start[1], 95.0, 190.0)
    obs = _synthetic_observation(
        "DEMO-A",
        lat=ice_lat, lon=ice_lon,
        age_hours=24.0,
        has_predecessor=True,
        length_nm=12.0, width_nm=8.0,
    )

    # Forecast
    fc_result = engine.forecast_iceberg(obs, communication_state="NOMINAL", data_freshness="FRESH")
    _print_forecast_summary("FORECAST RESULT", fc_result, obs)

    # Phase 4 Risk
    fc = _forecast_to_phase4(engine, obs, "CANDIDATE IMPROVED FORECAST — Motion-aware XGBoost")
    ice_state = IcebergState(
        iceberg_id=obs["iceberg_id"],
        lat=obs["lat"], lon=obs["lon"],
        observed_at=ASOF - timedelta(hours=obs.get("age_hours", 24.0)),
        length_nm=obs["iceberg_length_nm"], width_nm=obs["iceberg_width_nm"],
        drifting=True, synthetic=True,
        source_note="synthetic demo iceberg with predecessor",
    )
    vessel = VesselState(
        vessel_id="RV-DEMO", lat=route_start[0], lon=route_start[1], at=ASOF,
        synthetic=True, speed_knots=12.0,
    )
    risk_assessments = risk_engine.evaluate([ice_state], [fc], vessel, ASOF)
    risk_layer = risk_engine.navigation_layer(risk_assessments)
    risk = risk_assessments[0]
    print(f"\n  RISK ASSESSMENT")
    print(f"    Separation: {risk.separation_km:.1f} km, Effective: {risk.separation_effective_km:.1f} km")
    print(f"    Uncertainty σ: {risk.uncertainty.sigma_total_km:.1f} km (anchor: {risk.uncertainty.anchor_tag})")
    print(f"    Envelope radius: {risk.envelope_radius_km:.1f} km, Corridor: {risk.corridor_radius_km:.1f} km")
    print(f"    Risk score: {risk.risk_score:.2f} ({risk.risk_class})")
    print(f"    Freshness: {risk.data_freshness}, Comm: {risk.communication_status}")

    # Phase 5 Routing
    route_res = route_opt.solve(route_start, route_dest, risk_layer)
    print(f"\n  ROUTING RESULT")
    print(f"    Status: {route_res.status} ({route_res.route_label})")
    _print_route(route_res)

    return {
        "demo": "A",
        "forecast": fc_result.to_dict(),
        "risk": risk.to_dict(),
        "route": route_res.to_dict(),
    }


def run_demo_b() -> dict:
    """Demo B: Predecessor unavailable → Persistence fallback."""
    print("\n" + "=" * 70)
    print("DEMO B — PREDECESSOR UNAVAILABLE → PERSISTENCE FALLBACK")
    print("=" * 70)

    engine = ForecastEngine()
    risk_engine = RiskEngine()
    route_opt = RouteOptimizer()

    # Synthetic observation WITHOUT valid predecessor. Same geometry as Demo A
    # (iceberg ~95 km south of route) so the two demos compare cleanly.
    route_start = (-68.0, 76.0)
    route_dest = (-67.2, 78.6)
    ice_lat, ice_lon = pt_at(route_start[0], route_start[1], 95.0, 190.0)
    obs = _synthetic_observation(
        "DEMO-B",
        lat=ice_lat, lon=ice_lon,
        age_hours=24.0,
        has_predecessor=False,
        length_nm=12.0, width_nm=8.0,
    )

    # Forecast
    fc_result = engine.forecast_iceberg(obs, communication_state="NOMINAL", data_freshness="FRESH")
    _print_forecast_summary("FORECAST RESULT", fc_result, obs)

    # Phase 4 Risk
    fc = _forecast_to_phase4(engine, obs, "PERSISTENCE FALLBACK — mandatory (no valid predecessor)")
    ice_state = IcebergState(
        iceberg_id=obs["iceberg_id"],
        lat=obs["lat"], lon=obs["lon"],
        observed_at=ASOF - timedelta(hours=obs.get("age_hours", 24.0)),
        length_nm=obs["iceberg_length_nm"], width_nm=obs["iceberg_width_nm"],
        drifting=True, synthetic=True,
        source_note="synthetic demo iceberg WITHOUT predecessor",
    )
    vessel = VesselState(
        vessel_id="RV-DEMO", lat=route_start[0], lon=route_start[1], at=ASOF,
        synthetic=True, speed_knots=12.0,
    )
    risk_assessments = risk_engine.evaluate([ice_state], [fc], vessel, ASOF)
    risk_layer = risk_engine.navigation_layer(risk_assessments)
    risk = risk_assessments[0]
    print(f"\n  RISK ASSESSMENT")
    print(f"    Separation: {risk.separation_km:.1f} km, Effective: {risk.separation_effective_km:.1f} km")
    print(f"    Uncertainty σ: {risk.uncertainty.sigma_total_km:.1f} km (anchor: {risk.uncertainty.anchor_tag})")
    print(f"    Envelope radius: {risk.envelope_radius_km:.1f} km, Corridor: {risk.corridor_radius_km:.1f} km")
    print(f"    Risk score: {risk.risk_score:.2f} ({risk.risk_class})")
    print(f"    Freshness: {risk.data_freshness}, Comm: {risk.communication_status}")

    # Phase 5 Routing
    route_res = route_opt.solve(route_start, route_dest, risk_layer)
    print(f"\n  ROUTING RESULT")
    print(f"    Status: {route_res.status} ({route_res.route_label})")
    _print_route(route_res)

    return {
        "demo": "B",
        "forecast": fc_result.to_dict(),
        "risk": risk.to_dict(),
        "route": route_res.to_dict(),
    }


def main() -> int:
    print(BANNER)

    demo_a = run_demo_a()
    demo_b = run_demo_b()

    # Save machine-readable outputs
    out_dir = PROJECT_ROOT / "outputs" / "integration" / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)

    for demo in [demo_a, demo_b]:
        path = out_dir / f"integration_demo_{demo['demo']}.json"
        path.write_text(json.dumps(demo, indent=2, default=str), encoding="utf-8")
        print(f"\n  Saved: {path}")

    print("\n" + "=" * 70)
    print("INTEGRATION DEMOS COMPLETE — ALL SYNTHETIC / DEMO DATA")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())