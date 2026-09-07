#!/usr/bin/env python3
"""
HIM-DRUSHTI  —  PHASE 7B  ONBOARD DASHBOARD BACKEND
Flask app + MQTT (via existing PahoTransport + OnboardReceiver).
Serves the dashboard and pushes real-time updates via SSE.

Run locally:  python dashboard/backend.py
For LAN mode:  python dashboard/backend.py --broker 10.20.231.143
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Paths / imports ──────────────────────────────────────────────────────────
DASHBOARD_DIR = Path(__file__).resolve().parent


def _find_comm_dir() -> Path:
    """Locate the directory holding the Phase-6 communication modules.

    backend.py may be deployed in two layouts:
      repo   :  <project>/dashboard/backend.py
                (modules live in ../scripts/communication)
      laptop2:  <project>/scripts/communication/dashboard/backend.py
                (modules live in the dashboard's own parent)
    Walk upward from the dashboard looking for onboard_receiver.py — the module
    this file imports — so the copied Laptop-2 layout resolves without a
    hard-coded path. Never duplicates the module; it points at the existing one.
    """
    cur = DASHBOARD_DIR
    for _ in range(4):
        if (cur / "onboard_receiver.py").is_file():
            return cur
        sub = cur / "scripts" / "communication"
        if (sub / "onboard_receiver.py").is_file():
            return sub
        cur = cur.parent
    return DASHBOARD_DIR.parent


COMM_DIR = _find_comm_dir()

sys.path.insert(0, str(COMM_DIR))

from flask import Flask, Response, jsonify, render_template, request
from onboard_receiver import OnboardReceiver, LatestState
from state_manager import CommunicationStateMachine, CommState
from transport import PahoTransport

# ── CLI args ─────────────────────────────────────────────────────────────────
def _arg(name: str, default: str) -> str:
    for i, a in enumerate(sys.argv):
        if a == f"--{name}" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return os.getenv(f"HIM_{name.upper()}", default)

CONFIG_PATH = _arg("config", str(COMM_DIR / "communication_config.laptop2.yaml"))


def _broker_from_config(cfg_path: str) -> tuple[str, int] | None:
    """Read (host, port) from the existing Laptop-2 MQTT YAML config.

    backend.py previously hard-coded 127.0.0.1:1883 and never used the YAML's
    broker section for the connection. This is a DEFAULT only: an explicit
    --broker/--port CLI arg (e.g. from start_himdrushti_onboard.bat) or the
    HIM_BROKER / HIM_PORT env vars still win, and a missing or unreadable
    config file falls back to localhost. The YAML file itself is not modified.
    """
    try:
        import yaml
        p = Path(cfg_path)
        if not p.is_file():
            return None
        cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
        broker = cfg.get("communication_state_machine", {}).get("broker", {})
        host = str(broker.get("host", "")).strip()
        if not host:
            return None
        port = int(broker.get("port", 0))
        return host, port
    except Exception:
        return None


_CFG_BROKER = _broker_from_config(CONFIG_PATH) or ("127.0.0.1", 1883)

BROKER_HOST = _arg("broker", _CFG_BROKER[0])
BROKER_PORT = int(_arg("port", str(_CFG_BROKER[1])))
CLIENT_ID   = _arg("client-id", "himdrushti-dashboard")
LISTEN_PORT = int(_arg("listen-port", "5000"))

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
log = logging.getLogger("dashboard")

# ── Flask ────────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=str(DASHBOARD_DIR / "templates"),
    static_folder=str(DASHBOARD_DIR / "static"),
)

# ── Shared state ─────────────────────────────────────────────────────────────
_lock       = threading.Lock()
_latest: dict[str, dict | None] = {
    "observation": None,
    "forecast":    None,
    "risk":        None,
    "route":       None,
    "status":      None,
}
_comm_state: str      = "FRESH"
_conn_ok: bool        = False
_last_update_ts: str  = ""
_update_seq: int      = 0          # monotonic counter for SSE change detection

# ── Receiver wiring ──────────────────────────────────────────────────────────
receiver: OnboardReceiver | None = None


def _on_msg(topic_key: str, payload: dict) -> None:
    global _last_update_ts, _update_seq
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock:
        _latest[topic_key] = payload
        _last_update_ts = now_iso
        _update_seq += 1


def _on_state_change(old: CommState, new: CommState) -> None:
    global _comm_state
    log.info("comm state %s -> %s", old.value, new.value)
    with _lock:
        _comm_state = new.value


def _start_mqtt() -> None:
    global receiver, _conn_ok
    cfg = Path(CONFIG_PATH)
    log.info("connecting  %s:%s  client=%s  config=%s", BROKER_HOST, BROKER_PORT, CLIENT_ID, cfg.name)
    try:
        t = PahoTransport(host=BROKER_HOST, port=BROKER_PORT, client_id=CLIENT_ID)
        t.connect()
        _conn_ok = True
    except Exception as exc:
        log.error("MQTT connect failed: %s", exc)
        _conn_ok = False
        return

    receiver = OnboardReceiver(t, config_path=cfg)
    receiver.register_message_callback(_on_msg)
    receiver.register_state_change_callback(_on_state_change)
    log.info("subscribed to all himdrushti/* topics — waiting for messages")


# ── API helpers ──────────────────────────────────────────────────────────────
def _live_comm_state() -> str:
    """Query the receiver's state machine for the CURRENT communication state.

    The receiver fires state-change callbacks only when a message arrives, so
    during a silent gap the cached _comm_state would go stale. Reading the state
    machine live here reflects real time-since-last-message (STALE / LAST-KNOWN-
    STATE) without touching any Phase 6 logic — pure display-layer aggregation.
    """
    if receiver is None:
        return _comm_state
    try:
        return receiver.get_communication_state().value
    except Exception:
        return _comm_state


def _live_age_hours() -> float | None:
    """Receiver's live message age (time since last valid message)."""
    if receiver is None:
        return _compute_age()
    try:
        return receiver.get_last_observation_age_hours()
    except Exception:
        return _compute_age()


def _snapshot() -> dict:
    with _lock:
        return {
            "observation":   _latest["observation"],
            "forecast":      _latest["forecast"],
            "risk":          _latest["risk"],
            "route":         _latest["route"],
            "status":        _latest["status"],
            "comm_state":    _live_comm_state(),
            "connected":     _conn_ok,
            "last_update":   _last_update_ts,
            "update_seq":    _update_seq,
            "message_age_hours": _live_age_hours(),
        }


def _compute_age() -> float | None:
    """Age of the most recent observation, in hours."""
    obs = _latest["observation"]
    if not obs:
        return None
    try:
        ts_str = obs.get("timestamp") or obs.get("observation_time")
        if not ts_str:
            return None
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0
        return round(age, 2)
    except Exception:
        return None


# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    return jsonify(_snapshot())


@app.route("/api/stream")
def api_stream():
    """Server-Sent Events — pushes on message change, comm-state change, or
    a slow heartbeat (so a silent STALE / LAST-KNOWN-STATE transition is
    reflected on the dashboard even when no new MQTT message arrives)."""
    def generate():
        last_seq = -1
        last_state = None
        last_full_emit = 0.0
        while True:
            snap = _snapshot()
            now = time.time()
            # Emit a full snapshot on: (1) any message change, (2) any comm-state
            # transition (incl. silent STALE / LAST-KNOWN-STATE drift), (3) a
            # ~15 s heartbeat that keeps the clock-driven fields (message age)
            # fresh on screen even when no new MQTT message arrives.
            if (snap["update_seq"] != last_seq
                    or snap["comm_state"] != last_state
                    or now - last_full_emit >= 15.0):
                last_seq = snap["update_seq"]
                last_state = snap["comm_state"]
                last_full_emit = now
                yield f"data: {json.dumps(snap, default=str)}\n\n"
            else:
                yield ": keepalive\n\n"
            time.sleep(1.0)
    return Response(generate(),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    # Start MQTT receiver in background thread (daemon=True so it dies with Flask)
    mqtt_thread = threading.Thread(target=_start_mqtt, daemon=True, name="mqtt")
    mqtt_thread.start()

    log.info("dashboard starting on http://0.0.0.0:%s", LISTEN_PORT)
    app.run(host="0.0.0.0", port=LISTEN_PORT, threaded=True, use_reloader=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
