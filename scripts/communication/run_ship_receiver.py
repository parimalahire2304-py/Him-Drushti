#!/usr/bin/env python3
"""
PHASE 7A — LAPTOP-2 (SHIP / ONBOARD DSS) MQTT SUBSCRIBER ENTRY POINT

Runs the Phase 6 OnboardReceiver against Laptop-1's real Mosquitto broker
over the LAN. This script is designed to run ON LAPTOP-2.

It connects to the broker at the address in the deployment config
(communication_config.laptop2.yaml, host = Laptop-1 LAN/Wi-Fi IPv4),
subscribes to all himdrushti/* topics, and reports each validated message
plus the communication state. It does NOT fabricate observations and does
NOT run any AI forecasting/risk/routing — MQTT is transport only.

Run (on Laptop-2, after pip install paho-mqtt pyyaml):
    python scripts\\communication\\run_ship_receiver.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

COMM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(COMM_DIR))

from transport import PahoTransport           # real Mosquitto over LAN
from onboard_receiver import OnboardReceiver


def _load_broker(cfg_path: Path) -> tuple[str, int, str]:
    import yaml
    cfg = yaml.safe_load(open(cfg_path, "r", encoding="utf-8"))
    broker = cfg["communication_state_machine"]["broker"]
    cids = cfg["communication_state_machine"]["client_ids"]
    return broker["host"], int(broker["port"]), cids["subscriber"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Laptop-2 onboard MQTT subscriber")
    ap.add_argument("--config", default=str(COMM_DIR / "communication_config.laptop2.yaml"),
                    help="Laptop-2 deployment config (default: communication_config.laptop2.yaml)")
    ap.add_argument("--timeout", type=float, default=60.0,
                    help="seconds to listen before exiting (0 = listen forever)")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    host, port, client_id = _load_broker(cfg_path)

    print("=" * 68)
    print("LAPTOP-2  SHIP/ONBOARD DSS  —  MQTT Subscriber")
    print("=" * 68)
    print(f"  Config   : {cfg_path.name}")
    print(f"  Broker   : {host}:{port}   (Laptop-1 OFFSHORE AI SERVER)")
    print(f"  Client ID: {client_id}")
    print(f"  Listening: {args.timeout:.0f}s" + (" (until Ctrl+C)" if args.timeout == 0 else ""))
    print("=" * 68)

    transport = PahoTransport(host=host, port=port, client_id=client_id)
    print(f"  Connecting to {host}:{port} ...")
    transport.connect()
    print(f"  Connected: {transport.is_connected()}")

    receiver = OnboardReceiver(transport, config_path=cfg_path)
    print("  Subscribed to: himdrushti/observation, forecast, risk, route, status, replan")
    print("  Waiting for messages from Laptop-1 ...\n")

    deadline = time.time() + args.timeout if args.timeout > 0 else float("inf")
    try:
        while time.time() < deadline:
            log = receiver.get_received_log()
            # Only print newly arrived messages (track by count)
            if log:
                entry = log[-1]
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
                      f"<{entry['topic_key']}> state {entry['prev_state']}->{entry['new_state']} "
                      f"ts={entry['timestamp']}")
                print("   " + json.dumps(entry["payload"], default=str))
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n  Stopped by user.")
    finally:
        latest = receiver.get_latest_state()
        print("\n" + "=" * 68)
        print("FINAL ONBOARD STATE (Laptop-2):")
        print("  Communication state:", receiver.get_communication_state().value)
        print("  Received messages  :", len(receiver.get_received_log()))
        print("  Latest observation :", latest.observation is not None)
        print("  Latest forecast    :", latest.forecast is not None)
        print("  Latest risk        :", latest.risk is not None)
        print("  Latest route       :", latest.route is not None)
        if latest.forecast:
            print("  Forecast method    :", latest.forecast.get("forecast_method"))
        transport.disconnect()
        print("  Transport disconnected.")
        print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
