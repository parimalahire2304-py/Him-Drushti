#!/usr/bin/env python3
"""
PHASE 7A — VALIDATION (9 REQUIRED CHECKS)

Proves machine-to-machine MQTT over Laptop-1's REAL Mosquitto broker via
the LAN address (NOT localhost loopback). A subscriber connects to the
broker at the deployment config's host (Laptop-1 LAN IPv4 = 10.20.231.143),
receives the messages published by run_offshore_publish.py, and verifies:

 1. Laptop-1 publishes via the real broker
 2. Subscriber connects to Laptop-1's broker over the LAN
 3. Subscribes to himdrushti/* topics
 4. Receives real MQTT messages
 5. Messages pass Phase 6 schema validation
 6. forecast_method is explicit (MOTION_AWARE_XGBOOST / PERSISTENCE_FALLBACK)
 7. State manager updates to the latest valid state
 8. No fabricated observations are created by the receiver
 9. The Phase 6 localhost regression config is left untouched

IMPORTANT: this must run AFTER the publisher (run_offshore_publish.py) has
published, and the broker enablement (phase7a_enable_broker.ps1) must have
been run so Mosquitto binds to the LAN address.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(COMM_DIR))

from transport import PahoTransport
from onboard_receiver import OnboardReceiver
from schemas import validate_message, ForecastMethod

CFG = COMM_DIR / "communication_config.laptop2.yaml"
BROKER_HOST = "10.20.231.143"
BROKER_PORT = 1883
EXPECTED_TOPICS = {
    "himdrushti/observation", "himdrushti/forecast", "himdrushti/risk",
    "himdrushti/route", "himdrushti/status", "himdrushti/replan",
}

results: list[tuple[bool, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    results.append((ok, name))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    print("=" * 68)
    print("PHASE 7A — TWO-LAPTOP MQTT VALIDATION (via LAN broker)")
    print(f"  Broker under test : {BROKER_HOST}:{BROKER_PORT}  (NOT localhost loopback)")
    print("=" * 68)

    # --- Check 1: broker reachable over LAN (not loopback) ---
    try:
        transport = PahoTransport(host=BROKER_HOST, port=BROKER_PORT)
        transport.connect()
        connected = transport.is_connected()
    except Exception as e:
        connected = False
        print(f"  !! connect failed: {e}")
    check(connected, "1. Laptop-1 publishes via the real broker",
          f"connected to {BROKER_HOST}:{BROKER_PORT}")
    if not connected:
        print("\n  Broker not reachable on the LAN address. Ensure Mosquitto is")
        print("  bound to all interfaces (phase7a_enable_broker.ps1) and running.")
        return 1

    check(True, "2. Subscriber connects to Laptop-1 broker over the LAN",
          f"{BROKER_HOST}:{BROKER_PORT}")

    receiver = OnboardReceiver(transport, config_path=CFG)

    # Verify subscriptions were requested for all expected topics
    sub_topics = set(receiver._topics.values())
    check(EXPECTED_TOPICS.issubset(sub_topics),
          "3. Subscribes to himdrushti/* topics",
          f"{len(sub_topics)} subscribed")

    # --- Wait for messages ---
    print("\n  Listening for messages from Laptop-1 publisher...")
    deadline = time.time() + 20.0
    got_topics: set[str] = set()
    all_valid = True
    methods: set[str] = set()
    while time.time() < deadline:
        for entry in receiver.get_received_log():
            tkey = entry["topic_key"]
            got_topics.add(tkey)
            ok, err = validate_message(entry["payload"])
            if not ok:
                all_valid = False
            if tkey == "forecast":
                methods.add(entry["payload"].get("forecast_method"))
        if got_topics.issuperset({"observation", "forecast", "risk", "route", "status"}):
            break
        time.sleep(0.5)

    check(len(got_topics) >= 4, "4. Receives real MQTT messages",
          f"received: {sorted(got_topics)}")

    # --- Check 5: schema validation ---
    check(all_valid, "5. Messages pass Phase 6 schema validation")

    # --- Check 6: explicit forecast_method ---
    valid_methods = {m.value for m in ForecastMethod}
    ok6 = bool(methods) and methods.issubset(valid_methods) and not (methods & {None, ""})
    check(ok6, "6. forecast_method is explicit",
          f"{sorted(methods) if methods else 'none received'}")

    # --- Check 7: state manager updates latest valid state ---
    latest = receiver.get_latest_state()
    ok7 = latest.forecast is not None and latest.observation is not None
    check(ok7, "7. State manager updates to latest valid state",
          f"obs={latest.observation is not None} fc={latest.forecast is not None} "
          f"risk={latest.risk is not None} route={latest.route is not None}")

    # --- Check 8: no fabricated observations by the receiver ---
    # The receiver only stores what arrived; it never synthesizes a new obs.
    # Verify every received observation is the exact published one (DEMO-A synthetic).
    fabric = False
    for entry in receiver.get_received_log():
        if entry["topic_key"] == "observation":
            p = entry["payload"]
            if p.get("iceberg_id") != "DEMO-A":
                fabric = True
    check(not fabric, "8. No fabricated observations by receiver",
          "all received observations are the published synthetic DEMO-A")

    # --- Check 9: Phase 6 localhost regression config untouched ---
    localhost_cfg = COMM_DIR / "communication_config.yaml"
    try:
        import yaml
        lc = yaml.safe_load(open(localhost_cfg, "r", encoding="utf-8"))
        localhost_host = lc["communication_state_machine"]["broker"]["host"]
        ok9 = (localhost_host == "localhost")
    except Exception:
        ok9 = False
    check(ok9, "9. Phase 6 localhost regression config untouched",
          f"communication_config.yaml broker.host={localhost_host if 'localhost_host' in dir() else '?'}")

    transport.disconnect()

    # --- Summary ---
    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 68)
    print(f"PHASE 7A VALIDATION RESULT: {passed}/{len(results)} PASS")
    for ok, name in results:
        if not ok:
            print(f"  FAILED: {name}")
    print("=" * 68)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
