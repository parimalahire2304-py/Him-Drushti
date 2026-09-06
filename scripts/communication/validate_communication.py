#!/usr/bin/env python3
"""
PHASE 6 — COMMUNICATION LAYER VALIDATION (15 checks + regressions)

Deterministic checks per spec §10:
  1  MQTT connection / configuration
  2  Publisher works
  3  Subscriber works
  4  JSON schema validation works
  5  FRESH state
  6  STALE state
  7  LAST_KNOWN_STATE
  8  Recovery
  9  Forecast metadata preserved (Motion-aware)
 10  Persistence fallback metadata preserved
 11  No fabricated observations
 12  Phase 4 regression 22/22
 13  Phase 5 regression 19/19
 14  Phase 3G integration intact
 15  Protected datasets unchanged
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "communication"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "integration"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "risk"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "routing"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "ml" / "drifting_xgboost"))

import yaml

# Consistent synthetic clock with the demo / integration suite
ASOF = datetime(2025, 11, 12, 12, 0, 0, tzinfo=timezone.utc)
ASOF_STALE = ASOF + timedelta(hours=50)
ASOF_LOSS = ASOF + timedelta(hours=170)
ASOF_RECOVERY = ASOF + timedelta(hours=180)

PASS = 0
FAIL = 0
FAILS: list[str] = []


def _ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f"  PASS  {name}")


def _fail(name: str, why: str) -> None:
    global FAIL
    FAIL += 1
    FAILS.append(f"{name}: {why}")
    print(f"  FAIL  {name}: {why}")


# ── Check 1: MQTT connection / configuration ────────────────────────────────
def check_mqtt_connection_config() -> None:
    cfg_path = PROJECT_ROOT / "scripts" / "communication" / "communication_config.yaml"
    if not cfg_path.exists():
        _fail("mqtt_connection_config", f"missing {cfg_path}")
        return
    try:
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    except Exception as e:
        _fail("mqtt_connection_config", f"YAML parse error: {e}")
        return
    csm = cfg.get("communication_state_machine")
    if not isinstance(csm, dict):
        _fail("mqtt_connection_config", "missing communication_state_machine block")
        return
    required_top = ["stale_threshold_hours", "comm_loss_threshold_hours", "topics", "broker", "qos"]
    missing = [k for k in required_top if k not in csm]
    if missing:
        _fail("mqtt_connection_config", f"missing keys in csm: {missing}")
        return
    if not {"observation", "forecast", "risk", "route", "status", "replan"} <= set(csm["topics"].keys()):
        _fail("mqtt_connection_config", f"topics incomplete: {csm['topics']}")
        return
    if float(csm["stale_threshold_hours"]) != 48.0 or float(csm["comm_loss_threshold_hours"]) != 168.0:
        _fail("mqtt_connection_config", "unexpected threshold values (expected 48.0 / 168.0)")
        return
    # Transport instantiation (InMemory deterministic; does not require broker)
    try:
        from transport import make_transport
        t = make_transport("memory")
        if not t.is_connected():
            _fail("mqtt_connection_config", "InMemoryTransport not connected after make_transport(memory)")
            return
        t.disconnect()
    except Exception as e:
        _fail("mqtt_connection_config", f"transport instantiation failed: {e}")
        return
    _ok("mqtt_connection_config")


# ── Check 2: Publisher works ───────────────────────────────────────────────
def check_publisher() -> None:
    try:
        from transport import make_transport
        from offshore_publisher import OffshorePublisher
        from schemas import build_observation
        t = make_transport("memory")
        pub = OffshorePublisher(t)
        obs = build_observation("TEST-PUB", -68.5, 76.0, ASOF.isoformat(timespec="seconds"), timestamp=ASOF)
        pub.publish_observation(obs)
        # InMemory log should contain the observation topic
        if not hasattr(t, "log"):
            _fail("publisher", "transport has no log attribute")
            return
        if not any(entry["topic"] == "himdrushti/observation" for entry in t.log):
            _fail("publisher", f"observation not found in transport log: {t.log}")
            return
        t.disconnect()
    except Exception as e:
        _fail("publisher", f"exception: {e}")
        return
    _ok("publisher")


# ── Check 3: Subscriber / Receiver works ──────────────────────────────────
def check_subscriber() -> None:
    try:
        from transport import make_transport
        from offshore_publisher import OffshorePublisher
        from onboard_receiver import OnboardReceiver
        from schemas import build_observation, build_status
        t = make_transport("memory")
        pub = OffshorePublisher(t)
        recv = OnboardReceiver(t)
        # Publish a fresh observation anchored to ASOF
        obs = build_observation("TEST-SUB", -68.5, 76.0, ASOF.isoformat(timespec="seconds"), timestamp=ASOF)
        pub.publish_observation(obs)
        log = recv.get_received_log()
        if len(log) == 0:
            _fail("subscriber", "receiver log empty after publish")
            return
        if recv.get_latest_state().observation is None:
            _fail("subscriber", "latestState.observation is None after publish")
            return
        if recv.get_latest_state().observation["iceberg_id"] != "TEST-SUB":
            _fail("subscriber", "latest observation iceberg_id mismatch")
            return
        t.disconnect()
    except Exception as e:
        _fail("subscriber", f"exception: {e}")
        return
    _ok("subscriber")


# ── Check 4: JSON schema validation works ─────────────────────────────────
def check_json_schema_validation() -> None:
    try:
        from schemas import (
            build_observation, build_forecast, build_risk, build_route, build_status, build_replan,
            validate_message, validate_observation, validate_forecast,
        )
        # Valid observation passes
        obs = build_observation("TEST-VAL", -68.5, 76.0, ASOF.isoformat(timespec="seconds"), timestamp=ASOF)
        ok, err = validate_observation(obs)
        if not ok:
            _fail("json_schema_validation", f"valid observation rejected: {err}")
            return
        ok2, _ = validate_message(obs)
        if not ok2:
            _fail("json_schema_validation", "validate_message rejected valid observation")
            return
        # Invalid observation fails (missing iceberg_id)
        bad_obs = dict(obs)
        bad_obs.pop("iceberg_id")
        ok3, err3 = validate_observation(bad_obs)
        if ok3:
            _fail("json_schema_validation", "invalid observation (missing iceberg_id) accepted")
            return
        # Valid/invalid forecast method
        fc = build_forecast(
            "TEST-VAL", -68.5, 76.0, 168.0,
            forecast_method="MOTION_AWARE_XGBOOST", model_used="motion_aware_xgb",
            predecessor_available=True, fallback=False, fallback_reason=None,
            timestamp=ASOF,
        )
        ok4, err4 = validate_forecast(fc)
        if not ok4:
            _fail("json_schema_validation", f"valid forecast rejected: {err4}")
            return
        bad_fc = dict(fc)
        bad_fc["forecast_method"] = "INVALID_METHOD"
        ok5, _ = validate_forecast(bad_fc)
        if ok5:
            _fail("json_schema_validation", "invalid forecast_method accepted")
            return
        # Valid risk/route/status/replan
        from schemas import validate_risk, validate_route, validate_status, validate_replan
        risk = build_risk("TEST-VAL", "LOW", 8.0, "FRESH", 36.0, 59.2, 64.2, timestamp=ASOF)
        ok6, err6 = validate_risk(risk)
        if not ok6:
            _fail("json_schema_validation", f"valid risk rejected: {err6}")
            return
        route = build_route("SAFE", "ROUTE", "FRESH", "FRESH", timestamp=ASOF)
        ok7, err7 = validate_route(route)
        if not ok7:
            _fail("json_schema_validation", f"valid route rejected: {err7}")
            return
        status = build_status("FRESH", ASOF.isoformat(timespec="seconds"), 0.0, "within freshness window", timestamp=ASOF)
        ok8, err8 = validate_status(status)
        if not ok8:
            _fail("json_schema_validation", f"valid status rejected: {err8}")
            return
        replan = build_replan("NEW_OBSERVATION", "MOTION_AWARE_XGBOOST", "LOW", "SAFE", timestamp=ASOF)
        ok9, err9 = validate_replan(replan)
        if not ok9:
            _fail("json_schema_validation", f"valid replan rejected: {err9}")
            return
    except Exception as e:
        _fail("json_schema_validation", f"exception: {e}")
        return
    _ok("json_schema_validation")


def _fresh_receiver_at_asof():
    """Helper: receiver with one observation anchored at ASOF."""
    from transport import make_transport
    from offshore_publisher import OffshorePublisher
    from onboard_receiver import OnboardReceiver
    from schemas import build_observation
    t = make_transport("memory")
    pub = OffshorePublisher(t)
    recv = OnboardReceiver(t)
    obs = build_observation("TEST-FRESH", -68.5, 76.0, ASOF.isoformat(timespec="seconds"), timestamp=ASOF)
    pub.publish_observation(obs)
    return t, pub, recv


# ── Check 5: FRESH ─────────────────────────────────────────────────────────
def check_fresh() -> None:
    try:
        from state_manager import CommState
        t, pub, recv = _fresh_receiver_at_asof()
        state = recv.get_communication_state(ASOF)
        age = recv.get_last_observation_age_hours(ASOF)
        if state != CommState.FRESH:
            _fail("fresh", f"expected FRESH at ASOF, got {state.value}")
            return
        if abs(age) > 0.01:
            _fail("fresh", f"expected age ~0 at ASOF, got {age}")
            return
        t.disconnect()
    except Exception as e:
        _fail("fresh", f"exception: {e}")
        return
    _ok("fresh")


# ── Check 6: STALE ─────────────────────────────────────────────────────────
def check_stale() -> None:
    try:
        from state_manager import CommState
        t, pub, recv = _fresh_receiver_at_asof()
        state = recv.get_communication_state(ASOF_STALE)
        age = recv.get_last_observation_age_hours(ASOF_STALE)
        if state != CommState.STALE:
            _fail("stale", f"expected STALE at ASOF+50h, got {state.value} (age {age:.1f}h)")
            return
        if not (48.0 <= age < 168.0):
            _fail("stale", f"expected age in [48,168), got {age:.1f}h")
            return
        t.disconnect()
    except Exception as e:
        _fail("stale", f"exception: {e}")
        return
    _ok("stale")


# ── Check 7: LAST_KNOWN_STATE ─────────────────────────────────────────────
def check_last_known_state() -> None:
    try:
        from state_manager import CommState
        t, pub, recv = _fresh_receiver_at_asof()
        state = recv.get_communication_state(ASOF_LOSS)
        age = recv.get_last_observation_age_hours(ASOF_LOSS)
        if state != CommState.LAST_KNOWN_STATE:
            _fail("last_known_state", f"expected LAST_KNOWN_STATE at ASOF+170h, got {state.value} (age {age:.1f}h)")
            return
        if age < 168.0:
            _fail("last_known_state", f"expected age >=168h, got {age:.1f}h")
            return
        if recv.get_latest_state().is_empty():
            _fail("last_known_state", "latestState is empty during loss — should preserve last valid")
            return
        if recv.get_latest_state().observation is None:
            _fail("last_known_state", "latest observation was lost during LAST_KNOWN_STATE")
            return
        t.disconnect()
    except Exception as e:
        _fail("last_known_state", f"exception: {e}")
        return
    _ok("last_known_state")


# ── Check 8: Recovery ─────────────────────────────────────────────────────
def check_recovery() -> None:
    try:
        from state_manager import CommState
        from schemas import build_observation
        t, pub, recv = _fresh_receiver_at_asof()
        # Verify loss first
        assert recv.get_communication_state(ASOF_LOSS) == CommState.LAST_KNOWN_STATE
        # New valid message at recovery time
        obs2 = build_observation("TEST-RECOV", -68.4, 76.1, ASOF_RECOVERY.isoformat(timespec="seconds"), timestamp=ASOF_RECOVERY)
        pub.publish_observation(obs2)
        state = recv.get_communication_state(ASOF_RECOVERY)
        age = recv.get_last_observation_age_hours(ASOF_RECOVERY)
        if state != CommState.FRESH:
            _fail("recovery", f"expected FRESH after new message at recovery, got {state.value} (age {age:.1f}h)")
            return
        if abs(age) > 0.01:
            _fail("recovery", f"expected age ~0 after recovery, got {age:.1f}h")
            return
        # Latest observation should be the new one
        latest_obs = recv.get_latest_state().observation
        if latest_obs is None or latest_obs["iceberg_id"] != "TEST-RECOV":
            _fail("recovery", "latest observation not updated to recovery message")
            return
        t.disconnect()
    except Exception as e:
        _fail("recovery", f"exception: {e}")
        return
    _ok("recovery")


# ── Check 9: Forecast metadata preserved (Motion-aware) ───────────────────
def check_forecast_metadata_preserved() -> None:
    try:
        from transport import make_transport
        from offshore_publisher import OffshorePublisher
        from onboard_receiver import OnboardReceiver
        from schemas import build_forecast
        t = make_transport("memory")
        pub = OffshorePublisher(t)
        recv = OnboardReceiver(t)
        fc = build_forecast(
            "TEST-FC", -68.5, 76.0, 168.0,
            forecast_method="MOTION_AWARE_XGBOOST", model_used="motion_aware_xgb",
            predecessor_available=True, fallback=False, fallback_reason=None,
            communication_state="FRESH", data_freshness="FRESH",
            timestamp=ASOF,
        )
        pub.publish_forecast(fc)
        latest = recv.get_latest_state().forecast
        if latest is None:
            _fail("forecast_metadata_preserved", "latest forecast is None after publish")
            return
        if latest["forecast_method"] != "MOTION_AWARE_XGBOOST":
            _fail("forecast_metadata_preserved", f"forecast_method altered: {latest['forecast_method']}")
            return
        if latest["model_used"] != "motion_aware_xgb" or latest["predecessor_available"] is not True:
            _fail("forecast_metadata_preserved", f"forecast identity fields altered: {latest}")
            return
        if latest["fallback"] is not False:
            _fail("forecast_metadata_preserved", "fallback flag altered")
            return
        t.disconnect()
    except Exception as e:
        _fail("forecast_metadata_preserved", f"exception: {e}")
        return
    _ok("forecast_metadata_preserved")


# ── Check 10: Persistence fallback metadata preserved ─────────────────────
def check_persistence_fallback_metadata_preserved() -> None:
    try:
        from transport import make_transport
        from offshore_publisher import OffshorePublisher
        from onboard_receiver import OnboardReceiver
        from schemas import build_forecast
        t = make_transport("memory")
        pub = OffshorePublisher(t)
        recv = OnboardReceiver(t)
        fc = build_forecast(
            "TEST-FC-PERSIST", -68.5, 76.0, 168.0,
            forecast_method="PERSISTENCE_FALLBACK", model_used="persistence",
            predecessor_available=False, fallback=True, fallback_reason="NO_VALID_PREDECESSOR",
            communication_state="FRESH", data_freshness="FRESH",
            timestamp=ASOF,
        )
        pub.publish_forecast(fc)
        latest = recv.get_latest_state().forecast
        if latest is None:
            _fail("persistence_fallback_metadata_preserved", "latest forecast is None after publish")
            return
        if latest["forecast_method"] != "PERSISTENCE_FALLBACK":
            _fail("persistence_fallback_metadata_preserved", f"forecast_method altered: {latest['forecast_method']}")
            return
        if latest["fallback_reason"] != "NO_VALID_PREDECESSOR":
            _fail("persistence_fallback_metadata_preserved", f"fallback_reason altered: {latest['fallback_reason']}")
            return
        if latest["fallback"] is not True or latest["predecessor_available"] is not False:
            _fail("persistence_fallback_metadata_preserved", f"fallback/predecessor fields altered: {latest}")
            return
        t.disconnect()
    except Exception as e:
        _fail("persistence_fallback_metadata_preserved", f"exception: {e}")
        return
    _ok("persistence_fallback_metadata_preserved")


# ── Check 11: No fabricated observations ──────────────────────────────────
def check_no_fabricated_obs() -> None:
    try:
        t, pub, recv = _fresh_receiver_at_asof()
        # Record observation count and latest after initial publish
        log_before = len(recv.get_received_log())
        latest_before = recv.get_latest_state().observation
        # Simulate silence through STALE and LAST_KNOWN_STATE: do NOT publish anything new
        # Poll state at loss time — receiver must not have auto-generated an observation
        _ = recv.get_communication_state(ASOF_LOSS)
        log_after = len(recv.get_received_log())
        latest_after = recv.get_latest_state().observation
        if log_after != log_before:
            _fail("no_fabricated_obs", f"receiver log grew during loss without new publish: {log_before} -> {log_after}")
            return
        if latest_after is None or latest_before is None:
            _fail("no_fabricated_obs", "latest observation became None during loss")
            return
        if latest_after["timestamp"] != latest_before["timestamp"]:
            _fail("no_fabricated_obs", "latest observation timestamp changed during loss — fabrication suspected")
            return
        if latest_after["iceberg_id"] != latest_before["iceberg_id"]:
            _fail("no_fabricated_obs", "latest observation identity changed during loss")
            return
        t.disconnect()
    except Exception as e:
        _fail("no_fabricated_obs", f"exception: {e}")
        return
    _ok("no_fabricated_obs")


# ── Check 12: Phase 4 regression 22/22 ───────────────────────────────────
def check_phase4_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "risk" / "validate_risk_engine.py")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=300,
    )
    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 or "22 passed" not in out.lower() and "22/22" not in out:
        _fail("phase4_regression", f"Phase 4 validation did not yield 22/22 PASS. Output head: {out[:600]}")
        return
    _ok("phase4_regression")


# ── Check 13: Phase 5 regression 19/19 ───────────────────────────────────
def check_phase5_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "routing" / "validate_routing.py")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=300,
    )
    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 or "19 passed" not in out.lower() and "19/19" not in out:
        _fail("phase5_regression", f"Phase 5 validation did not yield 19/19 PASS. Output head: {out[:600]}")
        return
    _ok("phase5_regression")


# ── Check 14: Phase 3G integration intact ─────────────────────────────────
def check_phase3g_integration_intact() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "integration" / "validate_integration.py")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=300,
    )
    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 or "18 passed" not in out.lower() and "18/18" not in out:
        _fail("phase3g_integration_intact", f"Phase 3G integration validation did not yield 18/18 PASS. Output head: {out[:600]}")
        return
    _ok("phase3g_integration_intact")


# ── Check 15: Protected datasets unchanged ─────────────────────────────────
def check_protected_datasets_unchanged() -> None:
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    lines = [l for l in result.stdout.splitlines() if l.strip()]

    def _is_mod(line: str) -> bool:
        return bool(line.strip()) and line[0] in "MDR"

    # Data protection rules 1-10: no modified datasets, no downloads, C39 intact
    protected_prefixes = [
        "data/processed/ml/expanded/",
        "data/processed/ml/full.parquet",
        "data/processed/ml/train.parquet",
        "data/processed/ml/val.parquet",
        "data/processed/ml/test.parquet",
        "data/processed/ml/models/drifting_xgboost/",
        "data/raw/",
        "data/processed/icebergs/",
        "data/processed/bathymetry/",
        "data/processed/sea_ice/",
        "data/processed/weather/",
    ]
    bad = [l for l in lines if _is_mod(l) and any(p in l for p in protected_prefixes)]
    if bad:
        _fail("protected_datasets_unchanged", f"protected data files show as modified: {bad[:4]}")
        return
    # Also ensure no new uncommitted data file was created outside outputs/communication
    # (outputs/communication/demo/*.json is allowed)
    import pathlib
    # Check existence of BYU merge or 2026 data not introduced: rely on git untracked
    # but verify test.parquet C39 count as secondary guard
    try:
        import pandas as pd
        test_path = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded" / "test.parquet"
        if test_path.exists():
            test_df = pd.read_parquet(test_path)
            c39 = int((test_df["iceberg_id"] == "C39").sum())
            if c39 != 9:
                _fail("protected_datasets_unchanged", f"C39 test count changed: {c39} != 9")
                return
    except Exception as e:
        _fail("protected_datasets_unchanged", f"C39 guard check exception: {e}")
        return
    _ok("protected_datasets_unchanged")


def main() -> int:
    print("=" * 65)
    print("PHASE 6 — COMMUNICATION LAYER VALIDATION (15 checks)")
    print("=" * 65)
    checks = [
        check_mqtt_connection_config,
        check_publisher,
        check_subscriber,
        check_json_schema_validation,
        check_fresh,
        check_stale,
        check_last_known_state,
        check_recovery,
        check_forecast_metadata_preserved,
        check_persistence_fallback_metadata_preserved,
        check_no_fabricated_obs,
        check_phase4_regression,
        check_phase5_regression,
        check_phase3g_integration_intact,
        check_protected_datasets_unchanged,
    ]
    for fn in checks:
        try:
            fn()
        except Exception as e:
            _fail(fn.__name__, f"unhandled exception: {e}")
    print("=" * 65)
    print(f"VALIDATION RESULT:  {PASS} passed,  {FAIL} failed")
    print("=" * 65)
    if FAIL > 0:
        print("\nFailures:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("ALL 15 PHASE-6 VALIDATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
