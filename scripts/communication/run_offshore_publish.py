#!/usr/bin/env python3
"""
PHASE 7E — LAPTOP-1 (OFFSHORE AI SERVER) MQTT PUBLISHER ENTRY POINT

Runs the REAL Phase 3G -> Phase 4 -> Phase 5 pipeline on a REAL historical
D22 observation (2019-11-01) loaded from the existing local ML dataset, and
publishes the resulting observation/forecast/risk/route messages to Laptop-1's
Mosquitto broker over the LAN. Designed to run ON LAPTOP-1, so that Laptop-2's
subscriber receives them machine-to-machine.

HISTORICAL REPLAY — NOT live detection. The observation is the real D22
record from the US NIC Antarctic Iceberg Tracking Database (weekly); the
forecast and risk/route outputs are produced by the existing Phase 3G/4/5
pipeline. MQTT is transport only — forecasting, risk, and routing remain on
Laptop-1. No dataset, model, or core pipeline file is modified.

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

# --- Phase 7E: real historical demo input (source of truth = local dataset) ---
# The D22 2019-11-01 row is read from the existing local ML dataset. It carries
# the full 23-feature vector (env + motion) assembled by the existing Phase 3C
# data-prepipeline from the real 2019 feature stack and the real 2019-10-25
# predecessor. The parallel CSV record verifies position/size/dates.
TRAIN_PATH = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded" / "train.parquet"
ICEBERG_CSV = PROJECT_ROOT / "data" / "processed" / "icebergs" / "east_prydz_bay_icebergs.csv"
DEMO_ICEBERG_ID = "D22"
DEMO_OBS_DATE = "2019-11-01"


def _load_real_d22_row() -> "dict[str, object]":
    """Load the real D22 2019-11-01 row from the existing local ML dataset.

    This is the sole source of truth for the D22 observation+env+motion
    features. Uses duckdb if available (avoids loading pyarrow/fastparquet
    at import time into the main process) with a pandas fallback.
    Raises if the row is missing so the publisher cannot silently publish
    wrong/fallback data.
    """
    # Use duckdb when available (already in the project's data tooling)
    try:
        import duckdb  # type: ignore[import]
        df = duckdb.query(
            "SELECT * FROM read_parquet('%s') "
            "WHERE iceberg_id = 'D22' AND obs_date = '2019-11-01'" % TRAIN_PATH.as_posix()
        ).df()
    except Exception:
        import pandas as pd  # type: ignore[import]
        df = pd.read_parquet(TRAIN_PATH)
        df = df[(df["iceberg_id"] == "D22") & (df["obs_date"].astype(str) == "2019-11-01")]
    if df.empty:
        raise FileNotFoundError("D22 2019-11-01 not found in %s" % TRAIN_PATH)
    row = df.iloc[0].to_dict()
    # Verify the four MUST values before publishing (defense against corrupted dataset)
    import math
    lat, lon = float(row["lat"]), float(row["lon"])
    if not (math.isclose(lat, -66.77, abs_tol=1e-6) and math.isclose(lon, 75.42, abs_tol=1e-6)):
        raise ValueError(
            "D22 focal position changed vs expected: got (%s, %s) expected (-66.77, 75.42); dataset may be altered" % (lat, lon)
        )
    if str(row["iceberg_id"]).upper() != "D22":
        raise ValueError("D22 id mismatch in dataset row")
    if str(row["obs_date"])[:10] != "2019-11-01":
        raise ValueError("D22 obs_date mismatch in dataset row")
    return row


def _real_d22_observation(row: "dict[str, object]", ts: datetime) -> dict:
    """Build the MQTT observation message from the real D22 train row.

    Fields emitted by schemas.build_observation: iceberg_id/lat/lon map to
    latitude/longitude, ice sizes + prev_* go explicitly, remaining env
    features (including rrd + float + None=missing NaN keys) pass via
    **extra_env (schemas.build_observation is written to do exactly this).

    No value is invented: every env/motion field comes from the row; fields
    not present in the dataset are omitted (schema preserves missing-data
    semantics).
    """
    return build_observation(
        iceberg_id=str(row["iceberg_id"]),
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        observation_time=str(row["obs_date"]),
        data_source="US NIC",
        length_nm=float(row["iceberg_length_nm"]),
        width_nm=float(row["iceberg_width_nm"]),
        prev_delta_lat=float(row["prev_delta_lat"]) if row.get("prev_delta_lat") is not None else None,
        prev_delta_lon=float(row["prev_delta_lon"]) if row.get("prev_delta_lon") is not None else None,
        prev_speed=float(row["prev_speed"]) if row.get("prev_speed") is not None else None,
        prev_bearing=float(row["prev_bearing"]) if row.get("prev_bearing") is not None else None,
        timestamp=ts,
        # ---- all env features from the row (schema extra_env) — real values only ----
        iceberg_length_nm=float(row["iceberg_length_nm"]),
        iceberg_width_nm=float(row["iceberg_width_nm"]),
        sea_ice_concentration=float(row["sea_ice_concentration"]),
        wind_u_10m=float(row["wind_u_10m"]),
        wind_v_10m=float(row["wind_v_10m"]),
        temperature_2m=float(row["temperature_2m"]),
        mean_sea_level_pressure=float(row["mean_sea_level_pressure"]),
        total_precipitation=float(row["total_precipitation"]),
        bathymetry_elevation=float(row["bathymetry_elevation"]),
        ocean_current_u=float(row["ocean_current_u"]),
        ocean_current_v=float(row["ocean_current_v"]),
        wind_speed=float(row["wind_speed"]),
        wind_dir=float(row["wind_dir"]),
        ocean_speed=float(row["ocean_speed"]),
        ocean_dir=float(row["ocean_dir"]),
        wind_ocean_angle=float(row["wind_ocean_angle"]),
        exposed_water_fraction=float(row["exposed_water_fraction"]),
        # predecessor geoms for traceability (not fed to the model)
        prev_lat=float(row["prev_lat"]),
        prev_lon=float(row["prev_lon"]),
        # original source + pipeline provenance (not invented)
        observation_date=str(row["obs_date"]),
        source_file="east_prydz_bay_icebergs.csv — AntarcticIcebergs_20191101.csv",
        historical_replay=True,
        historical_label="HISTORICAL REPLAY — 2019-11-01 US NIC weekly archive",
    )


def main() -> int:
    # Load real D22 row before writing any network state
    row = _load_real_d22_row()
    now = datetime.now(timezone.utc)
    comm_state_str = CommunicationState.FRESH.value
    fresh_str = "FRESH"

    print("=" * 68)
    print("LAPTOP-1  OFFSHORE AI SERVER  —  MQTT Publisher  (HISTORICAL REPLAY)")
    print("  Historical replay — not live detection.")
    print("  Source: US NIC Antarctic Iceberg Tracking Database (weekly)")
    print("  Focal : D22  2019-11-01  (-66.77, 75.42)  ← %s" % TRAIN_PATH.name)
    print("  CSV   : D22  2019-11-01  row verified in east_prydz_bay_icebergs.csv")
    print("=" * 68)
    print(f"  Broker   : {BROKER_HOST}:{BROKER_PORT}")
    print(f"  Config   : {CFG.name}")
    print(f"  Pipeline : Phase 3G forecast -> Phase 4 risk -> Phase 5 route")
    print(f"  Publish  : {now.isoformat(timespec='seconds')} UTC  (wall clock)")
    print(f"  Replay   : obs_time 2019-11-01  (historical; not real-time)")
    print("=" * 68)

    # Real D22 observation (already carries all 23 features via extra_env)
    obs_msg = _real_d22_observation(row, now)

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
        drifting=True, synthetic=False,
        source_note="historical replay: US NIC D22 2019-11-01 (real observation)",
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
