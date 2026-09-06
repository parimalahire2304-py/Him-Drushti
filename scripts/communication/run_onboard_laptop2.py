#!/usr/bin/env python3
"""
PHASE 7A — LAPTOP-2 (SHIP / ONBOARD DSS) LAN MQTT LAUNCHER

Connects Laptop-2 to Laptop-1's real Mosquitto broker over the LAN using
the Phase 7A deployment config (communication_config.laptop2.yaml).

- Loads broker.host / broker.port from communication_config.laptop2.yaml
- Reads the unique Laptop-2 subscriber client ID from the same config
- Instantiates PahoTransport(host, port, client_id=...) explicitly
  (never relies on the 127.0.0.1 default)
- Instantiates OnboardReceiver with the same Laptop-2 config path
- Connects over the LAN, subscribes to all himdrushti/* topics via
  OnboardReceiver, and keeps the process alive for observation
- Prints startup info, received messages, and state transitions
- Handles Ctrl+C cleanly

No AI, no model, no risk/routing logic. No fabrication.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

COMM_DIR = Path(__file__).resolve().parent
# Ensure communication package imports resolve (state_manager, schemas, transport, onboard_receiver)
sys.path.insert(0, str(COMM_DIR))

import yaml  # type: ignore

from transport import PahoTransport
from onboard_receiver import OnboardReceiver


# Deployment config for Laptop-2 — MUST be the Phase 7A file, not the Phase 6 localhost one
CFG = COMM_DIR / "communication_config.laptop2.yaml"


def _load_laptop2_config(cfg_path: Path) -> tuple[str, int, str, dict[str, str], dict[str, int]]:
    """Read broker host/port, subscriber client ID, topics, and QoS from the Laptop-2 config."""
    if not cfg_path.exists():
        raise FileNotFoundError(f"Laptop-2 deployment config not found: {cfg_path}")
    cfg = yaml.safe_load(open(cfg_path, "r", encoding="utf-8"))
    csm = cfg.get("communication_state_machine")
    if csm is None:
        raise ValueError(f"{cfg_path}: missing 'communication_state_machine' section")
    broker = csm.get("broker") or {}
    host = broker.get("host")
    port = broker.get("port")
    if host is None or port is None:
        raise ValueError(f"{cfg_path}: broker.host/port missing (got host={host!r} port={port!r})")
    cids = csm.get("client_ids") or {}
    client_id = cids.get("subscriber")
    if not client_id:
        raise ValueError(f"{cfg_path}: client_ids.subscriber missing")
    topics: dict[str, str] = dict(csm.get("topics") or {})
    qos: dict[str, int] = dict(csm.get("qos") or {})
    return str(host), int(port), str(client_id), topics, qos


def main() -> int:
    host, port, client_id, topics, qos = _load_laptop2_config(CFG)

    print("=" * 68)
    print("PHASE 7A — LAPTOP-2  SHIP/ONBOARD DSS  LAN MQTT LAUNCHER")
    print("=" * 68)
    print(f"  Config    : {CFG.name}")
    print(f"  Broker    : {host}:{port}  (Laptop-1 OFFSHORE AI SERVER, LAN)")
    print(f"  Client ID : {client_id}")
    print(f"  Topics    : {', '.join(topics.values()) if topics else '(none)'}")
    if qos:
        print(f"  QoS       : {', '.join(f'{k}={v}' for k, v in qos.items())}")
    print("=" * 68)

    # Explicitly pass host/port/client_id from the deployment config —
    # never fall back to PahoTransport's 127.0.0.1 default.
    print(f"[laptop2] creating PahoTransport(host={host!r}, port={port}, client_id={client_id!r}) ...")
    transport = PahoTransport(host=host, port=port, client_id=client_id)

    # OnboardReceiver subscribes to all himdrushti/* topics via _subscribe_all()
    # using the same Laptop-2 config path so thresholds/topics stay consistent.
    print(f"[laptop2] creating OnboardReceiver(config_path={CFG.name}) ...")
    receiver = OnboardReceiver(transport, config_path=CFG)

    print(f"[laptop2] connecting to {host}:{port} ...")
    transport.connect()
    connected = transport.is_connected()
    print(f"[laptop2] connected: {connected}")
    if not connected:
        print("[laptop2] ERROR: transport reported not connected after connect().", file=sys.stderr)
        return 1

    print(f"[laptop2] subscribed topics ({len(topics)}):")
    for k, t in topics.items():
        print(f"           - {k}: {t}  (QoS {qos.get(k, 1)})")

    # Initial communication state (before any messages)
    try:
        init_state = receiver.get_communication_state()
        print(f"[laptop2] initial communication state: {init_state.value}")
    except Exception as e:
        print(f"[laptop2] (could not read initial state: {e})")

    print("[laptop2] listening — waiting for MQTT messages from Laptop-1.")
    print("[laptop2] press Ctrl+C to stop cleanly.")
    print("-" * 68)

    # Track already-printed log entries so we only print new arrivals
    printed = 0
    try:
        while True:
            log = receiver.get_received_log()
            # Print any new entries since last iteration
            while printed < len(log):
                entry = log[printed]
                ts = entry.get("timestamp", "")
                topic_key = entry.get("topic_key", "?")
                topic = entry.get("topic", "?")
                prev_state = entry.get("prev_state", "?")
                new_state = entry.get("new_state", "?")
                payload = entry.get("payload", {})
                now_s = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"[{now_s}] <{topic_key}> {topic}  state {prev_state} -> {new_state}  ts={ts}")
                # Print payload compactly (truncate very long payloads)
                import json as _json
                try:
                    pretty = _json.dumps(payload, default=str, ensure_ascii=False)
                    if len(pretty) > 1200:
                        pretty = pretty[:1200] + " ... (truncated)"
                    print(f"  payload: {pretty}")
                except Exception:
                    print(f"  payload: {payload!r}")
                printed += 1
            # Periodic heartbeat / state snapshot every ~10 s when idle
            # (helps observe STALE/LAST_KNOWN_STATE transitions)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[laptop2] interrupted (Ctrl+C) — disconnecting ...")
    finally:
        try:
            latest = receiver.get_latest_state()
            final_state = receiver.get_communication_state()
            total = len(receiver.get_received_log())
            print("-" * 68)
            print("[laptop2] final onboard state:")
            print(f"  communication state : {final_state.value}")
            print(f"  received messages   : {total}")
            print(f"  latest observation  : {latest.observation is not None}")
            print(f"  latest forecast     : {latest.forecast is not None}")
            if latest.forecast:
                print(f"    forecast_method   : {latest.forecast.get('forecast_method')}")
            print(f"  latest risk         : {latest.risk is not None}")
            print(f"  latest route        : {latest.route is not None}")
            print(f"  latest status       : {latest.status is not None}")
        except Exception as e:
            print(f"[laptop2] (final state read failed: {e})")
        try:
            transport.disconnect()
            print("[laptop2] transport disconnected.")
        except Exception:
            pass
        print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
