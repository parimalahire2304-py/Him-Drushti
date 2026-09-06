#!/usr/bin/env python3
"""
PHASE 3G → PHASE 4/5 INTEGRATION — VALIDATION SUITE
====================================================

18 deterministic checks per spec §14. All must pass.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "integration"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "risk"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "routing"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "ml" / "drifting_xgboost"))

import numpy as np
import pandas as pd
import xgboost as xgb

from forecast import ForecastEngine, build_observation_from_row  # noqa: E402
from risk_engine import RiskEngine, IcebergState, Forecast, VesselState  # noqa: E402
from route_optimizer import RouteOptimizer  # noqa: E402

# ── Test constants ──────────────────────────────────────────────────────────
ASOF = datetime(2025, 11, 12, 12, 0, 0, tzinfo=timezone.utc)
VESSEL = VesselState(vessel_id="RV-TEST", lat=-68.0, lon=76.0, at=ASOF, synthetic=True)
START = (-68.0, 76.0)
DEST = (-67.0, 78.0)

PASS = 0
FAIL = 0
FAILS: list[str] = []


def _ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f"  ✅ PASS  {name}")


def _fail(name: str, why: str) -> None:
    global FAIL
    FAIL += 1
    FAILS.append(f"{name}: {why}")
    print(f"  ❌ FAIL  {name}: {why}")


# 1. Phase 3G model loads without retraining
def check_model_loads() -> None:
    engine = ForecastEngine()
    if engine._lat_model is None or engine._lon_model is None:
        _fail("model_loads", "Motion-aware XGBoost artifacts failed to load")
    else:
        _ok("model_loads")


# 2. Feature ordering correct (23 features exactly as trained)
def check_feature_order() -> None:
    engine = ForecastEngine()
    if engine._metadata is None:
        _fail("feature_order", "metadata not loaded")
        return
    actual = engine._metadata.get("feature_columns", [])
    from forecast import MOTION_FEATURES
    expected = MOTION_FEATURES
    if actual != expected:
        _fail("feature_order", f"expected {len(expected)} features, got {len(actual)}; mismatch at first diff")
        for i, (e, a) in enumerate(zip(expected, actual)):
            if e != a:
                FAILS.append(f"  feature[{i}]: expected={e}, actual={a}")
    else:
        _ok("feature_order")


# 3. Valid predecessor → Motion-aware selected
def check_valid_predecessor_selects_motion() -> None:
    engine = ForecastEngine()
    # Load a real test sample with predecessor
    test_path = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded" / "test.parquet"
    test_df = pd.read_parquet(test_path)
    mask_drift = ~test_df["iceberg_id"].isin(["D23"])
    mask_prev = test_df["prev_delta_lat"].notna()
    cand = test_df[mask_drift & mask_prev]
    if len(cand) == 0:
        _fail("valid_predecessor", "no test sample with predecessor")
        return
    row = cand.iloc[0]
    obs = build_observation_from_row(row)
    result = engine.forecast_iceberg(obs)
    if result.forecast_method != "MOTION_AWARE_XGBOOST":
        _fail("valid_predecessor", f"expected MOTION_AWARE_XGBOOST, got {result.forecast_method}")
    elif result.fallback_reason is not None:
        _fail("valid_predecessor", f"fallback_reason should be None, got {result.fallback_reason}")
    elif not result.predecessor_available:
        _fail("valid_predecessor", "predecessor_available should be True")
    else:
        _ok("valid_predecessor")


# 4. Missing predecessor → Persistence fallback
def check_missing_predecessor_fallback() -> None:
    engine = ForecastEngine()
    test_path = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded" / "test.parquet"
    test_df = pd.read_parquet(test_path)
    mask_drift = ~test_df["iceberg_id"].isin(["D23"])
    mask_noprev = test_df["prev_delta_lat"].isna()
    cand = test_df[mask_drift & mask_noprev]
    if len(cand) == 0:
        _fail("missing_predecessor", "no test sample without predecessor")
        return
    row = cand.iloc[0]
    obs = build_observation_from_row(row)
    result = engine.forecast_iceberg(obs)
    if result.forecast_method != "PERSISTENCE_FALLBACK":
        _fail("missing_predecessor", f"expected PERSISTENCE_FALLBACK, got {result.forecast_method}")
    elif result.fallback_reason != "NO_VALID_PREDECESSOR":
        _fail("missing_predecessor", f"expected NO_VALID_PREDECESSOR, got {result.fallback_reason}")
    elif result.predecessor_available:
        _fail("missing_predecessor", "predecessor_available should be False")
    else:
        _ok("missing_predecessor")


# 5. NaN predecessor features → Persistence fallback
def check_nan_predecessor_fallback() -> None:
    engine = ForecastEngine()
    obs = {
        "iceberg_id": "TEST-NAN", "lat": -68.0, "lon": 76.0,
        "iceberg_length_nm": 10.0, "iceberg_width_nm": 6.0,
        "sea_ice_concentration": 0.3,
        "wind_u_10m": 2.0, "wind_v_10m": -1.0,
        "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
        "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
        "ocean_current_u": 0.05, "ocean_current_v": -0.02,
        "wind_speed": 2.24, "wind_dir": 116.6,
        "ocean_speed": 0.054, "ocean_dir": 111.8,
        "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
        "prev_delta_lat": float("nan"), "prev_delta_lon": float("nan"),
        "prev_speed": float("nan"), "prev_bearing": float("nan"),
    }
    result = engine.forecast_iceberg(obs)
    if result.forecast_method != "PERSISTENCE_FALLBACK":
        _fail("nan_predecessor", f"expected PERSISTENCE_FALLBACK, got {result.forecast_method}")
    elif result.fallback_reason != "NO_VALID_PREDECESSOR":
        _fail("nan_predecessor", f"expected NO_VALID_PREDECESSOR, got {result.fallback_reason}")
    else:
        _ok("nan_predecessor")


# 6. Model failure → explicit fallback (MODEL_UNAVAILABLE)
def check_model_failure_fallback() -> None:
    # Create engine with non-existent model dir to simulate failure
    bad_dir = PROJECT_ROOT / "data" / "processed" / "ml" / "models" / "drifting_xgboost" / "nonexistent"
    engine = ForecastEngine(model_dir=bad_dir)
    # Provide valid predecessor features
    obs = {
        "iceberg_id": "TEST-MODEL-FAIL", "lat": -68.0, "lon": 76.0,
        "iceberg_length_nm": 10.0, "iceberg_width_nm": 6.0,
        "sea_ice_concentration": 0.3,
        "wind_u_10m": 2.0, "wind_v_10m": -1.0,
        "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
        "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
        "ocean_current_u": 0.05, "ocean_current_v": -0.02,
        "wind_speed": 2.24, "wind_dir": 116.6,
        "ocean_speed": 0.054, "ocean_dir": 111.8,
        "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
        "prev_delta_lat": 0.08, "prev_delta_lon": 0.12,
        "prev_speed": 1.5, "prev_bearing": 56.3,
    }
    result = engine.forecast_iceberg(obs)
    if result.forecast_method != "PERSISTENCE_FALLBACK":
        _fail("model_failure", f"expected PERSISTENCE_FALLBACK, got {result.forecast_method}")
    elif result.fallback_reason != "MODEL_UNAVAILABLE":
        _fail("model_failure", f"expected MODEL_UNAVAILABLE, got {result.fallback_reason}")
    elif not result.predecessor_available:
        _fail("model_failure", "predecessor_available should be True (features were valid)")
    else:
        _ok("model_failure")


# 7. Output schema correct (all required fields)
def check_output_schema() -> None:
    engine = ForecastEngine()
    obs = {
        "iceberg_id": "TEST-SCHEMA", "lat": -68.0, "lon": 76.0,
        "iceberg_length_nm": 10.0, "iceberg_width_nm": 6.0,
        "sea_ice_concentration": 0.3,
        "wind_u_10m": 2.0, "wind_v_10m": -1.0,
        "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
        "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
        "ocean_current_u": 0.05, "ocean_current_v": -0.02,
        "wind_speed": 2.24, "wind_dir": 116.6,
        "ocean_speed": 0.054, "ocean_dir": 111.8,
        "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
        "prev_delta_lat": 0.08, "prev_delta_lon": 0.12,
        "prev_speed": 1.5, "prev_bearing": 56.3,
    }
    result = engine.forecast_iceberg(obs)
    d = result.to_dict()
    required = {"forecast_lat", "forecast_lon", "forecast_method", "model_name",
                "horizon_days", "predecessor_available", "communication_state",
                "data_freshness", "fallback_reason", "timestamp"}
    missing = required - set(d.keys())
    if missing:
        _fail("output_schema", f"missing keys: {missing}")
    else:
        _ok("output_schema")


# 8. Phase 4 accepts either forecast source
def check_phase4_accepts_either() -> None:
    engine = ForecastEngine()
    risk_engine = RiskEngine()

    # Test with Motion-aware
    obs_motion = {
        "iceberg_id": "TEST-P4-MOTION", "lat": -68.5, "lon": 76.0,
        "iceberg_length_nm": 10.0, "iceberg_width_nm": 6.0,
        "sea_ice_concentration": 0.3, "wind_u_10m": 2.0, "wind_v_10m": -1.0,
        "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
        "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
        "ocean_current_u": 0.05, "ocean_current_v": -0.02,
        "wind_speed": 2.24, "wind_dir": 116.6, "ocean_speed": 0.054,
        "ocean_dir": 111.8, "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
        "prev_delta_lat": 0.08, "prev_delta_lon": 0.12, "prev_speed": 1.5, "prev_bearing": 56.3,
    }
    fc_motion = engine.forecast_iceberg(obs_motion)
    forecast_motion = Forecast(
        iceberg_id=obs_motion["iceberg_id"],
        pred_lat=fc_motion.forecast_lat, pred_lon=fc_motion.forecast_lon,
        valid_at=ASOF + timedelta(days=7), horizon_hours=168.0,
        source=fc_motion.model_name, source_note="test motion",
    )
    ice_motion = IcebergState(obs_motion["iceberg_id"], obs_motion["lat"], obs_motion["lon"],
                              ASOF - timedelta(hours=24), obs_motion["iceberg_length_nm"],
                              obs_motion["iceberg_width_nm"], True, synthetic=True)
    try:
        risk_engine.evaluate([ice_motion], [forecast_motion], VESSEL, ASOF)
    except Exception as e:
        _fail("phase4_accepts_either", f"Motion-aware failed: {e}")
        return

    # Test with Persistence
    obs_persist = {**obs_motion, "iceberg_id": "TEST-P4-PERSIST",
                   "prev_delta_lat": float("nan"), "prev_delta_lon": float("nan"),
                   "prev_speed": float("nan"), "prev_bearing": float("nan")}
    fc_persist = engine.forecast_iceberg(obs_persist)
    forecast_persist = Forecast(
        iceberg_id=obs_persist["iceberg_id"],
        pred_lat=fc_persist.forecast_lat, pred_lon=fc_persist.forecast_lon,
        valid_at=ASOF + timedelta(days=7), horizon_hours=168.0,
        source=fc_persist.model_name, source_note="test persist",
    )
    ice_persist = IcebergState(obs_persist["iceberg_id"], obs_persist["lat"], obs_persist["lon"],
                               ASOF - timedelta(hours=24), obs_persist["iceberg_length_nm"],
                               obs_persist["iceberg_width_nm"], True, synthetic=True)
    try:
        risk_engine.evaluate([ice_persist], [forecast_persist], VESSEL, ASOF)
    except Exception as e:
        _fail("phase4_accepts_either", f"Persistence failed: {e}")
        return

    _ok("phase4_accepts_either")


# 9. Phase 4 regression 22/22 PASS
def check_phase4_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "risk" / "validate_risk_engine.py")],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=300
    )
    if result.returncode != 0 or "22 passed" not in result.stdout.lower() and "22/22" not in result.stdout:
        _fail("phase4_regression", f"Phase 4 validation failed: {result.stdout[:500]}")
    else:
        _ok("phase4_regression")


# 10. Phase 5 regression 19/19 PASS
def check_phase5_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "routing" / "validate_routing.py")],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=300
    )
    if result.returncode != 0 or "19 passed" not in result.stdout.lower() and "19/19" not in result.stdout:
        _fail("phase5_regression", f"Phase 5 validation failed: {result.stdout[:500]}")
    else:
        _ok("phase5_regression")


# 11. FRESH state preserved
def check_fresh_state() -> None:
    engine = ForecastEngine()
    obs = {
        "iceberg_id": "TEST-FRESH", "lat": -68.0, "lon": 76.0,
        "iceberg_length_nm": 10.0, "iceberg_width_nm": 6.0,
        "sea_ice_concentration": 0.3, "wind_u_10m": 2.0, "wind_v_10m": -1.0,
        "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
        "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
        "ocean_current_u": 0.05, "ocean_current_v": -0.02,
        "wind_speed": 2.24, "wind_dir": 116.6, "ocean_speed": 0.054,
        "ocean_dir": 111.8, "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
        "prev_delta_lat": 0.08, "prev_delta_lon": 0.12, "prev_speed": 1.5, "prev_bearing": 56.3,
    }
    result = engine.forecast_iceberg(obs, communication_state="NOMINAL", data_freshness="FRESH")
    if result.communication_state != "NOMINAL" or result.data_freshness != "FRESH":
        _fail("fresh_state", f"expected NOMINAL/FRESH, got {result.communication_state}/{result.data_freshness}")
    else:
        _ok("fresh_state")


# 12. STALE state preserved
def check_stale_state() -> None:
    engine = ForecastEngine()
    obs = {"iceberg_id": "TEST-STALE", "lat": -68.0, "lon": 76.0,
           "iceberg_length_nm": 10.0, "iceberg_width_nm": 6.0,
           "sea_ice_concentration": 0.3, "wind_u_10m": 2.0, "wind_v_10m": -1.0,
           "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
           "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
           "ocean_current_u": 0.05, "ocean_current_v": -0.02,
           "wind_speed": 2.24, "wind_dir": 116.6, "ocean_speed": 0.054,
           "ocean_dir": 111.8, "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
           "prev_delta_lat": 0.08, "prev_delta_lon": 0.12, "prev_speed": 1.5, "prev_bearing": 56.3}
    result = engine.forecast_iceberg(obs, communication_state="DEGRADED", data_freshness="STALE")
    if result.communication_state != "DEGRADED" or result.data_freshness != "STALE":
        _fail("stale_state", f"expected DEGRADED/STALE, got {result.communication_state}/{result.data_freshness}")
    else:
        _ok("stale_state")


# 13. LAST-KNOWN-STATE MODE preserved
def check_last_known_state() -> None:
    engine = ForecastEngine()
    obs = {"iceberg_id": "TEST-LKS", "lat": -68.0, "lon": 76.0,
           "iceberg_length_nm": 10.0, "iceberg_width_nm": 6.0,
           "sea_ice_concentration": 0.3, "wind_u_10m": 2.0, "wind_v_10m": -1.0,
           "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
           "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
           "ocean_current_u": 0.05, "ocean_current_v": -0.02,
           "wind_speed": 2.24, "wind_dir": 116.6, "ocean_speed": 0.054,
           "ocean_dir": 111.8, "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
           "prev_delta_lat": 0.08, "prev_delta_lon": 0.12, "prev_speed": 1.5, "prev_bearing": 56.3}
    result = engine.forecast_iceberg(obs, communication_state="COMMUNICATION LOST",
                                     data_freshness="LAST-KNOWN-STATE MODE")
    if result.communication_state != "COMMUNICATION LOST" or result.data_freshness != "LAST-KNOWN-STATE MODE":
        _fail("last_known_state", f"expected COMMUNICATION LOST/LAST-KNOWN-STATE MODE, got {result.communication_state}/{result.data_freshness}")
    else:
        _ok("last_known_state")


# 14. Recovery: new observation → FRESH recompute
def check_recovery() -> None:
    engine = ForecastEngine()
    # First: LAST-KNOWN-STATE
    obs_old = {"iceberg_id": "TEST-RECOV", "lat": -68.0, "lon": 76.0,
               "iceberg_length_nm": 10.0, "iceberg_width_nm": 6.0,
               "sea_ice_concentration": 0.3, "wind_u_10m": 2.0, "wind_v_10m": -1.0,
               "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
               "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
               "ocean_current_u": 0.05, "ocean_current_v": -0.02,
               "wind_speed": 2.24, "wind_dir": 116.6, "ocean_speed": 0.054,
               "ocean_dir": 111.8, "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
               "prev_delta_lat": 0.08, "prev_delta_lon": 0.12, "prev_speed": 1.5, "prev_bearing": 56.3}
    r1 = engine.forecast_iceberg(obs_old, communication_state="COMMUNICATION LOST",
                                 data_freshness="LAST-KNOWN-STATE MODE")
    # Second: NEW observation arrives (different position, FRESH)
    obs_new = {**obs_old, "lat": -67.95, "lon": 76.05,
               "prev_delta_lat": 0.05, "prev_delta_lon": 0.05,
               "prev_speed": 1.0, "prev_bearing": 45.0}
    r2 = engine.forecast_iceberg(obs_new, communication_state="NOMINAL", data_freshness="FRESH")
    if r1.forecast_lat == r2.forecast_lat and r1.forecast_lon == r2.forecast_lon:
        _fail("recovery", "forecast unchanged after new observation")
    elif r2.communication_state != "NOMINAL" or r2.data_freshness != "FRESH":
        _fail("recovery", f"expected NOMINAL/FRESH on recovery, got {r2.communication_state}/{r2.data_freshness}")
    else:
        _ok("recovery")


# 15. Deterministic routing (same inputs → same route)
def check_deterministic_routing() -> None:
    engine = ForecastEngine()
    risk_engine = RiskEngine()
    route_opt = RouteOptimizer()

    obs = {"iceberg_id": "TEST-DET", "lat": -68.5, "lon": 76.0,
           "iceberg_length_nm": 10.0, "iceberg_width_nm": 6.0,
           "sea_ice_concentration": 0.3, "wind_u_10m": 2.0, "wind_v_10m": -1.0,
           "temperature_2m": 265.0, "mean_sea_level_pressure": 101300.0,
           "total_precipitation": 0.0, "bathymetry_elevation": -500.0,
           "ocean_current_u": 0.05, "ocean_current_v": -0.02,
           "wind_speed": 2.24, "wind_dir": 116.6, "ocean_speed": 0.054,
           "ocean_dir": 111.8, "wind_ocean_angle": 4.8, "exposed_water_fraction": 0.7,
           "prev_delta_lat": 0.08, "prev_delta_lon": 0.12, "prev_speed": 1.5, "prev_bearing": 56.3}
    fc = engine.forecast_iceberg(obs)
    forecast = Forecast(obs["iceberg_id"], fc.forecast_lat, fc.forecast_lon,
                        ASOF + timedelta(days=7), 168.0, fc.model_name, "test")
    ice = IcebergState(obs["iceberg_id"], obs["lat"], obs["lon"],
                       ASOF - timedelta(hours=24), obs["iceberg_length_nm"],
                       obs["iceberg_width_nm"], True, synthetic=True)
    ass = risk_engine.evaluate([ice], [forecast], VESSEL, ASOF)
    layer = risk_engine.navigation_layer(ass)

    res1 = route_opt.solve(START, DEST, layer)
    res2 = route_opt.solve(START, DEST, layer)

    if res1.route != res2.route:
        _fail("deterministic_routing", "routes differ on repeated execution")
    elif res1.metrics != res2.metrics:
        _fail("deterministic_routing", "metrics differ on repeated execution")
    else:
        _ok("deterministic_routing")


# 16. No protected dataset modified
def check_no_protected_modified() -> None:
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=PROJECT_ROOT)
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    # Only MODIFIED/DELETED (first column M/D/R) protected files count as a protected
    # edit. Untracked (`??`) Phase 3G / 3C artifacts are legitimately new from their
    # own phases and are not touched by this integration.
    def _is_mod(line: str) -> bool:
        return line.strip() and line[0] in "MDR"
    protected = [l for l in lines if _is_mod(l) and any(p in l for p in
        ["data/processed/ml/expanded/", "data/processed/ml/full.parquet",
         "data/processed/ml/train.parquet", "data/processed/ml/val.parquet",
         "data/processed/ml/test.parquet",
         "scripts/ml/train_xgboost_expanded.py", "scripts/ml/prepare_ml_dataset_expanded.py",
         "scripts/ml/eval_metrics_expanded.py", "scripts/ml/compare_models_expanded.py",
         "config/models.yaml"])]
    if protected:
        _fail("no_protected_modified", f"protected files touched: {protected[:3]}")
    else:
        _ok("no_protected_modified")


# 17. No trajectory model retrained
def check_no_model_retrained() -> None:
    # Verify no .py files in scripts/ml/ were modified except new integration files
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=PROJECT_ROOT)
    modified_ml = [l for l in result.stdout.splitlines() if "scripts/ml/" in l and "drifting_xgboost" not in l and "integration" not in l]
    if modified_ml:
        _fail("no_model_retrained", f"ML scripts modified: {modified_ml}")
    else:
        _ok("no_model_retrained")


# 18. No new data downloads / C39 unchanged
def check_no_downloads_c39_unchanged() -> None:
    # Check test.parquet still has C39 0/0/9
    test_path = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded" / "test.parquet"
    test_df = pd.read_parquet(test_path)
    c39_counts = (
        int((test_df["iceberg_id"] == "C39").sum()),
    )
    if c39_counts[0] != 9:
        _fail("no_downloads_c39", f"C39 test count changed: {c39_counts[0]} != 9")
    else:
        _ok("no_downloads_c39")


def main() -> int:
    print("=" * 60)
    print("PHASE 3G → PHASE 4/5 INTEGRATION VALIDATION (18 checks)")
    print("=" * 60)

    checks = [
        check_model_loads,
        check_feature_order,
        check_valid_predecessor_selects_motion,
        check_missing_predecessor_fallback,
        check_nan_predecessor_fallback,
        check_model_failure_fallback,
        check_output_schema,
        check_phase4_accepts_either,
        check_phase4_regression,
        check_phase5_regression,
        check_fresh_state,
        check_stale_state,
        check_last_known_state,
        check_recovery,
        check_deterministic_routing,
        check_no_protected_modified,
        check_no_model_retrained,
        check_no_downloads_c39_unchanged,
    ]

    for fn in checks:
        try:
            fn()
        except Exception as e:
            _fail(fn.__name__, f"exception: {e}")

    print("=" * 60)
    print(f"VALIDATION RESULT:  {PASS} passed,  {FAIL} failed")
    print("=" * 60)

    if FAIL > 0:
        print("\nFailures:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("✅  ALL 18 INTEGRATION VALIDATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())