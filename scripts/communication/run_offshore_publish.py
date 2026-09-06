#!/usr/bin/env python3
"""
PHASE 7A — LAPTOP-1 (OFFSHORE AI SERVER) MQTT PUBLISHER ENTRY POINT

Runs the REAL Phase 3G -> Phase 4 -> Phase 5 pipeline for a synthetic
observation and publishes the resulting observation/forecast/risk/route
messages to Laptop-1's Mosquitto broker over the LAN. Designed to run
ON LAPTOP-1, so that Laptop-2's subscriber receives them machine-to-machine.

NO data is fabricated as real: the observation is explicitly synthetic
(Phase 6 synthetic_label / demo_note). MQTT is transport only — forecasting,
risk, and routing remain on Laptop-1.

Run (on Laptop-1):
    python scripts\\communication\\run_offshore_publish.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMM_DIR = Path(__file__).resolve().parent

# --- import paths (mirror run_communication_demo.py) ---
sys.path.insert(0, str(COMM_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "integration"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "risk"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "routing"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "ml" / "drifting_xgboost"))

import yaml  # type: ignore

from schemas import build_observation, build_forecast, build_risk, build_route, build_status
from state_manager import CommState
from schemas import CommunicationState
from transport import PahoTransport
from offshore_publisher import OffshorePublisher
from forecast import ForecastEngine
from risk_engine import RiskEngine, IcebergState, Forecast, VesselState
from route_optimizer import RouteOptimizer

# Route start/destination (identical to Phase 6 demo)
ROUTE_START = (-68.0, 76.0)
ROUTE_DEST = (-67.2, 78.6)

# Broker = Laptop-1 itself (real Mosquitto, now bound to all interfaces)
BROKER_HOST = "10.20.231.143"
BROKER_PORT = 1883
CFG = COMM_DIR / "communication_config.laptop2.yaml"


def _synthetic_observation(iceberg_id: str, lat: float, lon: float, ts) -> dict:
    """Full synthetic observation (message + env features for the pipeline)."""
    obs = build_observation(
        iceberg_id, lat, lon, ts.isoformat(timespec="seconds"),
        data_source="SATELLITE",
        length_nm=12.0, width_nm=8.0,
        prev_delta_lat=0.08, prev_delta_lon=0.12,
        prev_speed=1.5, prev_bearing=56.3,
        timestamp=ts,
    )
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


def main() -> int:
    now = datetime.now(timezone.utc)
    comm_state_str = CommunicationState.FRESH.value
    fresh_str = "FRESH"

    print("=" * 68)
    print("LAPTOP-1  OFFSHORE AI SERVER  —  MQTT Publisher")
    print("=" * 68)
    print(f"  Broker   : {BROKER_HOST}:{BROKER_PORT}  (real Mosquitto, LAN)")
    print(f"  Config   : {CFG.name}")
    print(f"  Pipeline : Phase 3G forecast -> Phase 4 risk -> Phase 5 route")
    print(f"  Timestamp: {now.isoformat(timespec='seconds')}  (SYNTHETIC demo data)")
    print("=" * 68)

    # Synthetic observation (has a valid predecessor -> motion-aware path)
    obs_msg = _synthetic_observation("DEMO-A", -68.5, 76.0, now)

    # --- Adapter: MQTT latitude/longitude -> pipeline lat/lon (no data invented) ---
    pipeline_obs = dict(obs_msg)
    pipeline_obs["lat"] = obs_msg["latitude"]
    pipeline_obs["lon"] = obs_msg["longitude"]

    # --- Phase 3G forecast ---
    engine = ForecastEngine()
    fc = engine.forecast_iceberg(
        pipeline_obs,
        communication_state=comm_state_str,
        data_freshness=fresh_str,
    )
    fc_msg = build_forecast(
        iceberg_id=obs_msg["iceberg_id"],
        forecast_lat=fc.forecast_lat, forecast_lon=fc.forecast_lon,
        forecast_horizon_hours=fc.horizon_days * 24,
        forecast_method=fc.forecast_method, model_used=fc.model_name,
        predecessor_available=fc.predecessor_available,
        fallback=(fc.forecast_method == "PERSISTENCE_FALLBACK"),
        fallback_reason=fc.fallback_reason,
        communication_state=comm_state_str, data_freshness=fresh_str,
        timestamp=now,
    )
    print(f"  Forecast: {fc.forecast_method}  model={fc.model_name}  "
          f"predecessor={fc.predecessor_available}  fallback={fc.fallback_reason}")

    # --- Phase 4 risk ---
    risk_engine = RiskEngine()
    ice_state = IcebergState(
        iceberg_id=obs_msg["iceberg_id"],
        lat=obs_msg["latitude"], lon=obs_msg["longitude"],
        observed_at=now - timedelta(hours=24),
        length_nm=obs_msg["length_nm"], width_nm=obs_msg["width_nm"],
        drifting=True, synthetic=True, source_note="synthetic two-laptop demo",
    )
    forecast_ice = Forecast(
        iceberg_id=obs_msg["iceberg_id"],
        pred_lat=fc.forecast_lat, pred_lon=fc.forecast_lon,
        valid_at=now + timedelta(hours=fc.horizon_days * 24),
        horizon_hours=float(fc.horizon_days * 24),
        source=fc.model_name, source_note=f"forecast_method={fc.forecast_method}",
    )
    vessel = VesselState(
        vessel_id="RV-DEMO", lat=ROUTE_START[0], lon=ROUTE_START[1],
        at=now, synthetic=True, speed_knots=12.0,
    )
    assessments = risk_engine.evaluate([ice_state], [forecast_ice], vessel, now)
    risk = assessments[0]
    risk_msg = build_risk(
        iceberg_id=obs_msg["iceberg_id"],
        risk_level=risk.risk_class, risk_score=risk.risk_score,
        communication_state=comm_state_str,
        uncertainty_sigma_km=risk.uncertainty.sigma_total_km,
        envelope_radius_km=risk.envelope_radius_km,
        corridor_radius_km=risk.corridor_radius_km,
        separation_km=risk.separation_km,
        separation_effective_km=risk.separation_effective_km,
        anchor_tag=risk.uncertainty.anchor_tag,
        data_freshness=fresh_str, timestamp=now,
    )
    print(f"  Risk    : {risk.risk_class}  score={risk.risk_score:.2f}")

    # --- Phase 5 routing ---
    route_opt = RouteOptimizer()
    risk_layer = risk_engine.navigation_layer(assessments)
    route_res = route_opt.solve(
        ROUTE_START, ROUTE_DEST, risk_layer,
        communication_status=risk.communication_status,
        data_freshness=fresh_str,
    )
    route_msg = build_route(
        route_status=route_res.status, route_label=route_res.route_label,
        communication_state=comm_state_str, data_freshness=fresh_str,
        route_distance_km=route_res.metrics.get("route_distance_km"),
        direct_distance_km=route_res.metrics.get("direct_distance_km"),
        distance_overhead_pct=route_res.metrics.get("distance_overhead_pct"),
        estimated_travel_time_hours=route_res.metrics.get("estimated_travel_time_hours"),
        max_risk_score_encountered=route_res.metrics.get("max_risk_score_encountered"),
        waypoints=[{"lat": la, "lon": lo} for la, lo in route_res.route[:5]]
                   + ([{"lat": route_res.route[-1][0], "lon": route_res.route[-1][1]}]
                      if route_res.route else []),
        timestamp=now,
    )
    print(f"  Route   : {route_res.status}  label={route_res.route_label}")

    # --- Connect and publish over the real broker ---
    # Use the config's distinct publisher client ID so the validator (which
    # also connects to the LAN broker in the orchestrated test harness)
    # is not kicked by MQTT client-ID collision (same default ID).
    _cfg = yaml.safe_load(open(CFG, "r", encoding="utf-8"))
    _pub_cid = _cfg["communication_state_machine"]["client_ids"]["publisher"]
    transport = PahoTransport(host=BROKER_HOST, port=BROKER_PORT, client_id=_pub_cid)
    transport.connect()
    print(f"  Connected to {BROKER_HOST}:{BROKER_PORT}: {transport.is_connected()}")

    publisher = OffshorePublisher(transport, config_path=CFG)
    publisher.publish_observation(obs_msg)
    publisher.publish_forecast(fc_msg)
    publisher.publish_risk(risk_msg)
    publisher.publish_route(route_msg)
    # Build a valid Phase 6 status dict via build_status(), then publish it.
    # (Previously called publish_status(comm_state=..., reason=...) with keyword
    #  args — a TypeError, since publish_status expects a single dict.)
    status_msg = build_status(
        communication_state=comm_state_str,
        last_message_timestamp=now.isoformat(timespec="seconds"),
        message_age_hours=0.0,
        reason="fresh, normal operations",
        timestamp=now,
    )
    publisher.publish_status(status_msg)

    # allow async paho to flush
    import time
    time.sleep(1.5)
    transport.disconnect()
    print("=" * 68)
    print("Published 5 messages (observation, forecast, risk, route, status).")
    print("Verify receipt on Laptop-2 with run_ship_receiver.py")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
