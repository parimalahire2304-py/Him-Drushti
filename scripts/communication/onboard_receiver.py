#!/usr/bin/env python3
"""
PHASE 6 — ONBOARD MQTT RECEIVER / STATE MANAGER (Laptop 2)

Subscribes to required topics, validates message structure,
tracks message age, maintains communication state, preserves
the most recent valid state, detects stale/loss, and recovers
when valid messages arrive again.

Critical: does NOT fabricate new iceberg observations during
communication loss — preserves LAST_KNOWN_STATE explicitly.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMM_CONFIG = Path(__file__).resolve().parent / "communication_config.yaml"

log = logging.getLogger(__name__)

# Import our shared components
sys_path_comm = str(Path(__file__).resolve().parent)
import sys
sys.path.insert(0, sys_path_comm)
from state_manager import CommunicationStateMachine, CommState
from schemas import (
    validate_message,
    MessageType,
    ForecastMethod,
    CommunicationState,
    build_status,
)
from transport import Transport


@dataclass
class LatestState:
    """Container for the most recent valid state across all message types."""
    observation: dict[str, Any] | None = None
    forecast: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    route: dict[str, Any] | None = None
    status: dict[str, Any] | None = None

    def is_empty(self) -> bool:
        return all(v is None for v in [
            self.observation, self.forecast, self.risk, self.route, self.status
        ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation": self.observation,
            "forecast": self.forecast,
            "risk": self.risk,
            "route": self.route,
            "status": self.status,
        }


class OnboardReceiver:
    """
    Onboard (Laptop 2) MQTT receiver and state manager.

    Responsibilities:
    1. Subscribe to all required Phase 6 topics.
    2. Receive and validate messages against Phase 6 schemas.
    3. Record message timestamps and update internal CommunicationStateMachine.
    4. Preserve the most recent valid state per message type.
    5. Detect stale communication and extended loss.
    6. Recover automatically when valid messages arrive again.
    7. Never fabricate new observations during loss.
    """

    def __init__(
        self,
        transport: Transport,
        config_path: Path | str | None = None,
    ) -> None:
        if not isinstance(transport, Transport):
            raise TypeError(f"transport must be a Transport instance; got {type(transport)}")
        self.transport = transport
        cfg_path = Path(config_path) if config_path else COMM_CONFIG
        self._cfg: dict[str, Any] = yaml.safe_load(open(cfg_path, "r", encoding="utf-8"))
        self._topics: dict[str, str] = self._cfg["communication_state_machine"]["topics"]
        self._qos: dict[str, int] = self._cfg["communication_state_machine"]["qos"]

        # Communication state machine (tracks message age)
        self._comm_state = CommunicationStateMachine(config_path=cfg_path)

        # Latest valid state (never overwritten with None)
        self._latest = LatestState()

        # Thread-safe received message log
        self._received_log: list[dict[str, Any]] = []
        self._log_lock = threading.Lock()

        # Callbacks for external integration
        self._on_state_change: list[Callable[[CommState, CommState], None]] = []
        self._on_message: list[Callable[[str, dict], None]] = []

        # Setup subscriptions
        self._subscribe_all()

    def _subscribe_all(self) -> None:
        """Subscribe to all Phase 6 topics."""
        for topic_key, topic in self._topics.items():
            self.transport.subscribe(topic, self._make_callback(topic_key), qos=self._qos.get(topic_key, 1))

    def _make_callback(self, topic_key: str) -> Callable[[str, dict], None]:
        """Create a topic-specific callback that updates state and validates."""
        def callback(topic: str, payload: dict[str, Any]) -> None:
            # Validate message structure
            ok, err = validate_message(payload)
            if not ok:
                log.warning(f"OnboardReceiver: invalid {topic_key} message: {err}")
                return

            # Update communication state machine (recovery on valid message)
            ts_str = payload.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    ts = datetime.now(timezone.utc)
            else:
                ts = datetime.now(timezone.utc)

            old_state = self._comm_state.infer_state(ts)
            self._comm_state.recover(ts)
            new_state = self._comm_state.infer_state(ts)

            # Record in log
            with self._log_lock:
                self._received_log.append({
                    "topic_key": topic_key,
                    "topic": topic,
                    "timestamp": ts.isoformat(timespec="seconds"),
                    "payload": payload,
                    "prev_state": old_state.value,
                    "new_state": new_state.value,
                })

            # Store latest valid state for this message type
            if topic_key == "observation":
                self._latest.observation = payload
            elif topic_key == "forecast":
                self._latest.forecast = payload
            elif topic_key == "risk":
                self._latest.risk = payload
            elif topic_key == "route":
                self._latest.route = payload
            elif topic_key == "status":
                self._latest.status = payload

            # Notify external callbacks
            if old_state != new_state:
                for cb in list(self._on_state_change):
                    cb(old_state, new_state)
            for cb in list(self._on_message):
                cb(topic_key, payload)

            log.debug(f"OnboardReceiver: {topic_key} received, state {old_state.value}->{new_state.value}")
        return callback

    # --- Public API -----------------------------------------------------------

    def register_state_change_callback(self, cb: Callable[[CommState, CommState], None]) -> None:
        """Register a callback fired on communication state transitions."""
        self._on_state_change.append(cb)

    def register_message_callback(self, cb: Callable[[str, dict], None]) -> None:
        """Register a callback fired on every validated message."""
        self._on_message.append(cb)

    def get_communication_state(self, asof: datetime | None = None) -> CommState:
        """Get current communication state."""
        if asof is None:
            asof = datetime.now(timezone.utc)
        return self._comm_state.infer_state(asof)

    def get_status_dict(self, asof: datetime | None = None) -> dict[str, Any]:
        """Get full communication status (for status messages / monitoring)."""
        if asof is None:
            asof = datetime.now(timezone.utc)
        return self._comm_state.status_dict(asof)

    def get_latest_state(self) -> LatestState:
        """Get the most recent valid state across all message types."""
        return self._latest

    def get_received_log(self) -> list[dict[str, Any]]:
        """Get the ordered log of all received messages."""
        with self._log_lock:
            return list(self._received_log)

    def clear_log(self) -> None:
        with self._log_lock:
            self._received_log.clear()

    def has_valid_state(self) -> bool:
        """Return True if we have at least one valid observation."""
        return self._latest.observation is not None

    def is_in_communication_loss(self, asof: datetime | None = None) -> bool:
        """Convenience: are we in LAST_KNOWN_STATE?"""
        return self.get_communication_state(asof) == CommState.LAST_KNOWN_STATE

    def get_last_observation_age_hours(self, asof: datetime | None = None) -> float:
        """Age of the last valid observation message."""
        if asof is None:
            asof = datetime.now(timezone.utc)
        return self._comm_state.age_hours(asof)

    def __repr__(self) -> str:
        return f"OnboardReceiver(connected={self.transport.is_connected()}, state={self.get_communication_state().value})"