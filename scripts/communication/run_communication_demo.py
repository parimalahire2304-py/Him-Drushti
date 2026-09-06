#!/usr/bin/env python3
"""
PHASE 6 — DETERMINISTIC COMMUNICATION RESILIENCE DEMO
=======================================================

Runs 6 labelled synthetic scenarios showing the full offshore MQTT
publisher → broker → onboard receiver state machine with Phase 3G→4→5
integration.

SCENARIOS:
  A  FRESH                  Normal communication, motion-aware forecast
  B  STALE                  Message age exceeds stale threshold
  C  LAST_KNOWN_STATE       Extended loss, preserve last valid state
  D  RECOVERY               Communication resumes, recompute/replan
  E  FORECAST FALLBACK      No valid predecessor → PERSISTENCE_FALLBACK
  F  AI FORECAST            Valid predecessor → MOTION_AWARE_XGBOOST

All values are SYNTHETIC / DEMO — never described as real observations.

Uses InMemoryTransport by default (deterministic, no Mosquitto needed).
Can use real Mosquitto via: python run_communication_demo.py --broker
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "integration"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "risk"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "routing"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "ml" / "drifting_xgboost"))

import yaml
from state_manager import CommunicationStateMachine, CommState
from schemas import (
    build_observation, build_forecast, build_risk, build_route, build_status, build_replan,
    MessageType, ForecastMethod, CommunicationState,
    validate_observation, validate_forecast, validate_risk, validate_route, validate_status,
)
from transport import InMemoryTransport, make_transport, Transport
from offshore_publisher import OffshorePublisher
from onboard_receiver import OnboardReceiver

from forecast import ForecastEngine
from risk_engine import RiskEngine, IcebergState, Forecast, VesselState
from route_optimizer import RouteOptimizer

BANNER = """
    ************************************************************
    *  PHASE 6 — COMMUNICATION RESILIENCE DEMO                  *
    *  All scenarios use SYNTHETIC values.                       *
    *  NOT real Antarctic observations.                          *
    *  Motion-aware XGBoost: CANDIDATE IMPROVED FORECAST         *
    *  Persistence: MANDATORY FALLBACK                           *
    ************************************************************
"""

ASOF = datetime(2025, 11, 12, 12, 0, 0, tzinfo=timezone.utc)
ASOF_STALE = ASOF + timedelta(hours=50)   # >48h stale threshold
ASOF_LOSS  = ASOF + timedelta(hours=170)  # >168h communication loss
ASOF_RECOVERY = ASOF + timedelta(hours=180)

# Synthetic iceberg geometry (same as Phase 3G/Phase 6 demos)
ROUTE_START = (-68.0, 76.0)
ROUTE_DEST  = (-67.2, 78.6)


def pt_at(lat: float, lon: float, d_km: float, bearing_deg: float):
    import math
    R = 6371.0088
    delta = d_km / R
    rlat, rlon = math.radians(lat), math.radians(lon)
    brng = math.radians(bearing_deg)
    tlat = math.asin(max(-1, min(1, math.sin(rlat)*math.cos(delta)
                                 + math.cos(rlat)*math.sin(delta)*math.cos(brng))))
    tlon = rlon + math.atan2(math.sin(brng)*math.sin(delta)*math.cos(rlat),
                             math.cos(delta) - math.sin(rlat)*math.sin(tlat))
    return math.degrees(tlat), math.degrees(tlon)


def _synthetic_observation(
    iceberg_id: str,
    lat: float, lon: float,
    *,
    has_predecessor: bool = True,
    obs_time: str | None = None,
    timestamp: str | datetime | None = None,
) -> dict:
    """Create a full synthetic observation dict (message + features for forecast pipeline)."""
    obs = build_observation(
        iceberg_id, lat, lon,
        obs_time or ASOF.isoformat(timespec="seconds"),
        data_source="SATELLITE",
        length_nm=12.0, width_nm=8.0,
        prev_delta_lat=0.08 if has_predecessor else float("nan"),
        prev_delta_lon=0.12 if has_predecessor else float("nan"),
        prev_speed=1.5 if has_predecessor else float("nan"),
        prev_bearing=56.3 if has_predecessor else float("nan"),
        timestamp=timestamp,
    )
    # Add environmental features for the forecast pipeline
    obs.update({
        "iceberg_length_nm": 12.0, "iceberg_width_nm": 8.0,
        "sea_ice_concentration": 0.3,
        "wind_u_10m": 2.0, "wind_v_10m": -1.0,
        "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
        "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
        "ocean_current_u": 0.05, "ocean_current_v": -0.02,
        "wind_speed": 2.24, "wind_dir": 116.6,
        "ocean_speed": 0.054, "ocean_dir": 111.8,
        "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
    })
    return obs


def _run_forecast_risk_route(
    obs_msg: dict,
    *,
    has_predecessor: bool,
    comm_state: CommState,
    asof: datetime,
) -> tuple[dict, dict, dict]:
    """Run the full Phase 3G → Phase 4 → Phase 5 pipeline and return MQTT messages."""
    from schemas import MessageType as MT
    comm_state_str = CommunicationState.FRESH.value if comm_state == CommState.FRESH else (
        CommunicationState.STALE.value if comm_state == CommState.STALE else
        CommunicationState.LAST_KNOWN_STATE.value
    )
    fresh_str = "FRESH" if comm_state == CommState.FRESH else (
        "STALE" if comm_state == CommState.STALE else "LAST-KNOWN-STATE MODE"
    )

    # --- Adapter: MQTT observation schema -> Phase 3G forecast interface ---
    # MQTT message uses latitude/longitude (Phase 6 spec Step 4); the Phase 3G
    # forecast interface expects lat/lon. No data is invented: this only maps
    # existing message fields onto the pipeline's expected keys.
    pipeline_obs = dict(obs_msg)
    pipeline_obs["lat"] = obs_msg["latitude"]
    pipeline_obs["lon"] = obs_msg["longitude"]

    # --- Forecast pipeline ---
    engine = ForecastEngine()
    fc_result = engine.forecast_iceberg(
        pipeline_obs,
        communication_state=comm_state_str,
        data_freshness=fresh_str,
    )

    fc_msg = build_forecast(
        iceberg_id=obs_msg["iceberg_id"],
        forecast_lat=fc_result.forecast_lat,
        forecast_lon=fc_result.forecast_lon,
        forecast_horizon_hours=fc_result.horizon_days * 24,
        forecast_method=fc_result.forecast_method,
        model_used=fc_result.model_name,
        predecessor_available=fc_result.predecessor_available,
        fallback=(fc_result.forecast_method == "PERSISTENCE_FALLBACK"),
        fallback_reason=fc_result.fallback_reason,
        communication_state=comm_state_str,
        data_freshness=fresh_str,
        timestamp=asof,
    )

    # --- Phase 4 Risk ---
    risk_engine = RiskEngine()
    ice_state = IcebergState(
        iceberg_id=obs_msg["iceberg_id"],
        lat=obs_msg["latitude"], lon=obs_msg["longitude"],
        observed_at=asof - timedelta(hours=24),
        length_nm=obs_msg["length_nm"], width_nm=obs_msg["width_nm"],
        drifting=True, synthetic=True, source_note="synthetic demo",
    )
    forecast_ice = Forecast(
        iceberg_id=obs_msg["iceberg_id"],
        pred_lat=fc_result.forecast_lat, pred_lon=fc_result.forecast_lon,
        valid_at=asof + timedelta(hours=fc_result.horizon_days * 24),
        horizon_hours=float(fc_result.horizon_days * 24),
        source=fc_result.model_name, source_note=f"forecast_method={fc_result.forecast_method}",
    )
    vessel = VesselState(
        vessel_id="RV-DEMO", lat=ROUTE_START[0], lon=ROUTE_START[1],
        at=asof, synthetic=True, speed_knots=12.0,
    )
    assessments = risk_engine.evaluate([ice_state], [forecast_ice], vessel, asof)
    risk = assessments[0]

    risk_msg = build_risk(
        iceberg_id=obs_msg["iceberg_id"],
        risk_level=risk.risk_class,
        risk_score=risk.risk_score,
        communication_state=comm_state_str,
        uncertainty_sigma_km=risk.uncertainty.sigma_total_km,
        envelope_radius_km=risk.envelope_radius_km,
        corridor_radius_km=risk.corridor_radius_km,
        separation_km=risk.separation_km,
        separation_effective_km=risk.separation_effective_km,
        anchor_tag=risk.uncertainty.anchor_tag,
        data_freshness=fresh_str,
        timestamp=asof,
    )

    # --- Phase 5 Routing ---
    route_opt = RouteOptimizer()
    risk_layer = risk_engine.navigation_layer(assessments)
    route_res = route_opt.solve(
        ROUTE_START, ROUTE_DEST, risk_layer,
        communication_status=risk.communication_status,
        data_freshness=fresh_str,
    )

    route_msg = build_route(
        route_status=route_res.status,
        route_label=route_res.route_label,
        communication_state=comm_state_str,
        data_freshness=fresh_str,
        route_distance_km=route_res.metrics.get("route_distance_km"),
        direct_distance_km=route_res.metrics.get("direct_distance_km"),
        distance_overhead_pct=route_res.metrics.get("distance_overhead_pct"),
        estimated_travel_time_hours=route_res.metrics.get("estimated_travel_time_hours"),
        max_risk_score_encountered=route_res.metrics.get("max_risk_score_encountered"),
        waypoints=[{"lat": lat, "lon": lon} for lat, lon in route_res.route[:5]]
                   + ([{"lat": route_res.route[-1][0], "lon": route_res.route[-1][1]}]
                      if route_res.route else []),
        timestamp=asof,
    )

    return fc_msg, risk_msg, route_msg


def _print_header(title: str) -> None:
    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)


def _drain(receiver, expected: int, timeout: float = 5.0) -> None:
    """Wait until the receiver has processed `expected` messages.

    PahoTransport delivers asynchronously on a network thread, so after
    publishing we poll the receiver's processed-message log until the batch
    has been fully reflected. This keeps the demo deterministic under both
    InMemory (synchronous) and real-broker (asynchronous) transports.
    """
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if len(receiver.get_received_log()) >= expected:
            return
        time.sleep(0.05)
    raise RuntimeError(
        f"_drain timed out: receiver processed {len(receiver.get_received_log())} "
        f"messages, expected {expected}"
    )


def _print_forecast(fc_msg: dict) -> None:
    print(f"    Forecast:     ({fc_msg['forecast_latitude']:.5f}, {fc_msg['forecast_longitude']:.5f})")
    print(f"    Method:       {fc_msg['forecast_method']}")
    print(f"    Model used:   {fc_msg['model_used']}")
    print(f"    Predecessor:  {'available' if fc_msg['predecessor_available'] else 'not available'}")
    if fc_msg["fallback"]:
        print(f"    Fallback:     {fc_msg['fallback_reason']}")
    print(f"    Horizon:      {fc_msg['forecast_horizon']:.0f} h ({fc_msg['forecast_horizon']/24:.0f} d)")


def _print_risk(risk_msg: dict) -> None:
    print(f"    Risk:         {risk_msg['risk_level']} (score {risk_msg['risk_score']:.1f})")
    print(f"    σ total:      {risk_msg['uncertainty_sigma_km']:.1f} km ({risk_msg.get('anchor_tag','')})")
    print(f"    Envelope:     {risk_msg['envelope_radius_km']:.1f} km | Corridor: {risk_msg['corridor_radius_km']:.1f} km")
    print(f"    Separation:   {risk_msg.get('separation_km', 'n/a')} km (effective: {risk_msg.get('separation_effective_km', 'n/a')} km)")


def _print_route(route_msg: dict) -> None:
    print(f"    Route:        {route_msg['route_status']} ({route_msg['route_label']})")
    print(f"    Route dist:   {route_msg.get('route_distance_km', 'n/a')} km | Direct: {route_msg.get('direct_distance_km', 'n/a')} km")
    print(f"    Overhead:     {route_msg.get('distance_overhead_pct', 'n/a')}% | Travel time: {route_msg.get('estimated_travel_time_hours', 'n/a'):.1f} h"
          if route_msg.get('estimated_travel_time_hours') else
          f"    Overhead:     {route_msg.get('distance_overhead_pct', 'n/a')}%")


def run_demo(use_real_broker: bool = False) -> dict[str, Any]:
    """Run all 6 scenarios and return results dict."""
    # Create transport
    if use_real_broker:
        transport = make_transport("paho")
        print(f"  [Transport: REAL Mosquitto broker on 127.0.0.1:1883]")
    else:
        transport = make_transport("memory")
        print(f"  [Transport: InMemoryTransport (deterministic, no broker needed)]")

    # Create publisher and receiver
    publisher = OffshorePublisher(transport)
    receiver = OnboardReceiver(transport)
    print(f"  Publisher: {publisher}")
    print(f"  Receiver:  {receiver}")
    print(f"  State machine: {receiver._comm_state}")

    scenarios = {}

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO A: FRESH (normal communication)
    # ─────────────────────────────────────────────────────────────────────────
    _print_header("SCENARIO A: FRESH — NORMAL COMMUNICATION")
    ice_lat, ice_lon = pt_at(*ROUTE_START, 95.0, 190.0)
    obs_a = _synthetic_observation("DEMO-A", ice_lat, ice_lon, has_predecessor=True,
                                   timestamp=ASOF)
    fc_a, risk_a, route_a = _run_forecast_risk_route(
        obs_a, has_predecessor=True, comm_state=CommState.FRESH, asof=ASOF
    )
    publisher.publish_decision_cycle(obs_a, fc_a, risk_a, route_a)
    _drain(receiver, 4)
    print("  State:", receiver.get_communication_state(ASOF).value)
    print(f"  Age: {receiver.get_last_observation_age_hours(ASOF):.1f} h")
    _print_forecast(fc_a)
    _print_risk(risk_a)
    _print_route(route_a)
    scenarios["A"] = {"state": receiver.get_communication_state(ASOF).value,
                      "forecast_method": fc_a["forecast_method"],
                      "risk_level": risk_a["risk_level"],
                      "route_status": route_a["route_status"]}

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO B: STALE (>48 h since last message, <168 h)
    # ─────────────────────────────────────────────────────────────────────────
    _print_header("SCENARIO B: STALE — MESSAGE AGE EXCEEDS STALE THRESHOLD")
    print("  No new messages published since Scenario A...")
    print(f"  State: {receiver.get_communication_state(ASOF_STALE).value}")
    print(f"  Age: {receiver.get_last_observation_age_hours(ASOF_STALE):.1f} h")
    state_b = receiver.get_communication_state(ASOF_STALE)
    print(f"  Using last valid state (no new observations)")
    status_b = receiver.get_status_dict(ASOF_STALE)
    print(f"  Status message: {json.dumps(status_b, indent=4)}")
    scenarios["B"] = {"state": state_b.value, "age_hours": status_b["age_hours"],
                      "reason": status_b["reason"]}

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO C: LAST_KNOWN_STATE (>168 h loss)
    # ─────────────────────────────────────────────────────────────────────────
    _print_header("SCENARIO C: LAST_KNOWN_STATE — EXTENDED COMMUNICATION LOSS")
    print("  Still no new messages...")
    print(f"  State: {receiver.get_communication_state(ASOF_LOSS).value}")
    print(f"  Age: {receiver.get_last_observation_age_hours(ASOF_LOSS):.1f} h")
    state_c = receiver.get_communication_state(ASOF_LOSS)
    print(f"  Last valid observation preserved (NOT fabricated)")
    print(f"  forecast_message_type: {receiver.get_latest_state().forecast['message_type'] if receiver.get_latest_state().forecast else 'none'}")
    scenarios["C"] = {"state": state_c.value, "age_hours": receiver.get_last_observation_age_hours(ASOF_LOSS),
                      "last_state_preserved": not receiver.get_latest_state().is_empty()}

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO D: RECOVERY (new valid observation)
    # ─────────────────────────────────────────────────────────────────────────
    _print_header("SCENARIO D: RECOVERY — NEW OBSERVATION, RECOMPUTE/REPLAN")
    print("  New observation arrives on SATCOM...")
    obs_d = _synthetic_observation("DEMO-A", ice_lat + 0.01, ice_lon - 0.01,
                                   has_predecessor=True,
                                   obs_time=ASOF_RECOVERY.isoformat(timespec="seconds"),
                                   timestamp=ASOF_RECOVERY)
    fc_d, risk_d, route_d = _run_forecast_risk_route(
        obs_d, has_predecessor=True, comm_state=CommState.FRESH, asof=ASOF_RECOVERY
    )
    publisher.publish_decision_cycle(obs_d, fc_d, risk_d, route_d)
    replan_d = build_replan(
        replan_trigger="COMMUNICATION_RECOVERY",
        forecast_method=fc_d["forecast_method"],
        risk_level=risk_d["risk_level"],
        route_status=route_d["route_status"],
        iceberg_id="DEMO-A",
        communication_state="FRESH",
        data_freshness="FRESH",
        timestamp=ASOF_RECOVERY,
    )
    publisher.publish_replan(replan_d)
    _drain(receiver, 9)
    state_d = receiver.get_communication_state(ASOF_RECOVERY)
    print(f"  State: {state_d.value}")
    print(f"  Age: {receiver.get_last_observation_age_hours(ASOF_RECOVERY):.1f} h")
    _print_forecast(fc_d)
    _print_risk(risk_d)
    _print_route(route_d)
    scenarios["D"] = {"state": state_d.value,
                      "forecast_method": fc_d["forecast_method"],
                      "risk_level": risk_d["risk_level"],
                      "route_status": route_d["route_status"]}

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO E: FORECAST FALLBACK (no valid predecessor)
    # ─────────────────────────────────────────────────────────────────────────
    _print_header("SCENARIO E: FORECAST FALLBACK — PERSISTENCE (NO PREDECESSOR)")
    obs_e = _synthetic_observation("DEMO-E", ice_lat, ice_lon, has_predecessor=False,
                               timestamp=ASOF)
    fc_e, risk_e, route_e = _run_forecast_risk_route(
        obs_e, has_predecessor=False, comm_state=CommState.FRESH, asof=ASOF
    )
    publisher.publish_decision_cycle(obs_e, fc_e, risk_e, route_e)
    _drain(receiver, 13)
    print(f"  State: {receiver.get_communication_state(ASOF).value}")
    _print_forecast(fc_e)
    _print_risk(risk_e)
    _print_route(route_e)
    scenarios["E"] = {"state": receiver.get_communication_state(ASOF).value,
                      "forecast_method": fc_e["forecast_method"],
                      "fallback_reason": fc_e["fallback_reason"],
                      "risk_level": risk_e["risk_level"],
                      "route_status": route_e["route_status"]}

    # ─────────────────────────────────────────────────────────────────────────
    # SCENARIO F: AI FORECAST (valid predecessor → motion-aware)
    # ─────────────────────────────────────────────────────────────────────────
    _print_header("SCENARIO F: AI FORECAST — MOTION-AWARE XGBOOST (VALID PREDECESSOR)")
    obs_f = _synthetic_observation("DEMO-F", ice_lat, ice_lon, has_predecessor=True,
                               timestamp=ASOF)
    fc_f, risk_f, route_f = _run_forecast_risk_route(
        obs_f, has_predecessor=True, comm_state=CommState.FRESH, asof=ASOF
    )
    publisher.publish_decision_cycle(obs_f, fc_f, risk_f, route_f)
    _drain(receiver, 17)
    print(f"  State: {receiver.get_communication_state(ASOF).value}")
    _print_forecast(fc_f)
    _print_risk(risk_f)
    _print_route(route_f)
    scenarios["F"] = {"state": receiver.get_communication_state(ASOF).value,
                      "forecast_method": fc_f["forecast_method"],
                      "risk_level": risk_f["risk_level"],
                      "route_status": route_f["route_status"]}

    # ─────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────────
    _print_header("SCENARIO SUMMARY")
    print(f"  {'Scenario':<12} {'State':<20} {'Forecast':<30} {'Risk':<10} {'Route'}")
    print("  " + "-" * 80)
    for tag in ["A", "B", "C", "D", "E", "F"]:
        s = scenarios[tag]
        print(f"  {tag:<12} {s['state']:<20} {s.get('forecast_method','n/a'):<30} {s.get('risk_level','n/a'):<10} {s.get('route_status','n/a')}")
    print("  " + "-" * 80)

    _print_header("PHASE 6 DEMO COMPLETE — ALL SYNTHETIC / DEMO")

    # Save outputs
    out_dir = PROJECT_ROOT / "outputs" / "communication" / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "him_drushti.phase6_communication_demo.v1",
        "transport": "memory" if not use_real_broker else "paho",
        "scenarios": scenarios,
        "message_log_count": len(receiver.get_received_log()),
        "note": "SYNTHETIC DEMO — NOT real Antarctic observations.",
    }
    out_file = out_dir / "communication_demo.json"
    out_file.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\n  Saved: {out_file}")
    print(f"  Total MQTT messages received: {len(receiver.get_received_log())}")

    return result


def main() -> int:
    print(BANNER)
    import argparse
    parser = argparse.ArgumentParser(description="Phase 6 Communication Demo")
    parser.add_argument("--broker", action="store_true",
                        help="Use real Mosquitto broker (127.0.0.1:1883) instead of InMemory")
    args = parser.parse_args()
    run_demo(use_real_broker=args.broker)
    return 0


if __name__ == "__main__":
    sys.exit(main())