#!/usr/bin/env python3
"""
PHASE 6 — COMMUNICATION STATE MACHINE (shared)

Implements the deterministic FRESH → STALE → LAST_KNOWN_STATE → FRESH
state machine with explicit transitions based on message age.

Consumption pattern:
  - Offshore publisher: tracks when it last published (for status messages).
  - Onboard receiver: tracks when it last received (for state inference).

This module is purely in-memory; it does NOT modify Phase 4 risk config.
It mirrors the Phase 4 freshness thresholds but owns the MQTT-layer
communication_state separately.

Uses communication_config.yaml for thresholds.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "communication_config.yaml"


class CommState(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    LAST_KNOWN_STATE = "LAST_KNOWN_STATE"


def _load_config(path: Path | str | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    with open(cfg_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class CommunicationStateMachine:
    """
    Deterministic communication state machine.

    Transitions:
        FRESH -> STALE: age >= stale_threshold_hours
        STALE -> LAST_KNOWN_STATE: age >= comm_loss_threshold_hours
        Any -> FRESH: a new valid message is received (explicit recover())
    """

    def __init__(
        self,
        config_path: Path | str | None = None,
        last_message_time: datetime | None = None,
    ) -> None:
        cfg_all = _load_config(config_path)
        cfg = cfg_all["communication_state_machine"]
        self.stale_threshold_h = float(cfg["stale_threshold_hours"])
        self.comm_loss_threshold_h = float(cfg["comm_loss_threshold_hours"])
        self._last_message_time: datetime | None = last_message_time
        self._config = cfg_all

    # --- State inference (pure function) ---
    def infer_state(self, asof: datetime) -> CommState:
        """
        Infer communication state from elapsed time since last valid message.
        Returns FRESH if no messages have been received yet (initial state).
        """
        if self._last_message_time is None:
            return CommState.FRESH

        age_h = max((asof - self._last_message_time).total_seconds() / 3600.0, 0.0)
        if age_h < self.stale_threshold_h:
            return CommState.FRESH
        if age_h < self.comm_loss_threshold_h:
            return CommState.STALE
        return CommState.LAST_KNOWN_STATE

    def age_hours(self, asof: datetime) -> float:
        """Return age in hours since last valid message (None => 0)."""
        if self._last_message_time is None:
            return 0.0
        return max((asof - self._last_message_time).total_seconds() / 3600.0, 0.0)

    # --- State updates ---
    def mark_received(self, timestamp: datetime) -> None:
        """
        Record that a valid message was received at `timestamp`.
        This transitions the state back to FRESH.
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        self._last_message_time = timestamp

    def recover(self, timestamp: datetime) -> None:
        """Explicit recovery — equivalent to mark_received but logged as RECOVERY."""
        self.mark_received(timestamp)

    @property
    def last_message_time(self) -> datetime | None:
        return self._last_message_time

    def status_dict(self, asof: datetime) -> dict[str, Any]:
        """Full status snapshot for status messages / debugging."""
        age_h = self.age_hours(asof)
        state = self.infer_state(asof)
        return {
            "communication_state": state.value,
            "last_message_timestamp": self._last_message_time.isoformat(timespec="seconds") if self._last_message_time else None,
            "age_hours": round(age_h, 3),
            "reason": (
                "within freshness window" if state == CommState.FRESH else
                "message age exceeds stale threshold" if state == CommState.STALE else
                "extended communication loss — using last known state"
            ),
        }

    def __repr__(self) -> str:
        return (
            f"CommunicationStateMachine("
            f"stale={self.stale_threshold_h}h, "
            f"comm_loss={self.comm_loss_threshold_h}h, "
            f"last={self._last_message_time}, "
            f"state_now={self.infer_state(datetime.now(timezone.utc)).value})"
        )