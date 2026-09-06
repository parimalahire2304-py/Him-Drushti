#!/usr/bin/env python3
"""
PHASE 6 — OFFSHORE MQTT PUBLISHER (Laptop 1)

Publishes system outputs — observations, forecasts, risk assessments,
routes, and communication status — over MQTT.

Architecture:
    Existing AI/Risk/Route pipeline
               |
               v
        Phase 6 OffshorePublisher  (this module)
               |
               v
          MQTT publish

The publisher does NOT rewrite the forecasting, risk, or routing algorithms.
It consumes their outputs and wraps them in Phase 6 MQTT schemas.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMM_CONFIG = Path(__file__).resolve().parent / "communication_config.yaml"

log = logging.getLogger(__name__)


def _load_config(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class OffshorePublisher:
    """
    Offshore (Laptop 1) MQTT publisher adapter.

    Wraps Phase 4/5 outputs into Phase 6 MQTT messages and publishes
    to the configured topic hierarchy via the provided Transport.
    """

    def __init__(self, transport, config_path: Path | str | None = None):
        from transport import Transport
        if not isinstance(transport, Transport):
            raise TypeError(f"transport must be a Transport instance; got {type(transport)}")
        self.transport = transport
        cfg_path = Path(config_path) if config_path else COMM_CONFIG
        self._cfg: dict[str, Any] = _load_config(cfg_path)
        self._topics: dict[str, str] = self._cfg["communication_state_machine"]["topics"]
        self._qos: dict[str, int] = self._cfg["communication_state_machine"]["qos"]

    def publish(self, topic_key: str, msg: dict[str, Any]) -> None:
        """Publish a message to the topic named `topic_key`."""
        if topic_key not in self._topics:
            raise KeyError(f"Unknown topic key: {topic_key}; available: {list(self._topics)}")
        topic = self._topics[topic_key]
        qos = self._qos.get(topic_key, 1)
        self.transport.publish(topic, msg, qos=qos)

    # --- Convenience publishers -----------------------------------------------

    def publish_observation(self, obs_msg: dict[str, Any]) -> None:
        self.publish("observation", obs_msg)

    def publish_forecast(self, fc_msg: dict[str, Any]) -> None:
        self.publish("forecast", fc_msg)

    def publish_risk(self, risk_msg: dict[str, Any]) -> None:
        self.publish("risk", risk_msg)

    def publish_route(self, route_msg: dict[str, Any]) -> None:
        self.publish("route", route_msg)

    def publish_status(self, status_msg: dict[str, Any]) -> None:
        self.publish("status", status_msg)

    def publish_replan(self, replan_msg: dict[str, Any]) -> None:
        self.publish("replan", replan_msg)

    # --- Batch publisher (observation → forecast → risk → route) --------------

    def publish_decision_cycle(
        self,
        obs_msg: dict[str, Any],
        fc_msg: dict[str, Any],
        risk_msg: dict[str, Any],
        route_msg: dict[str, Any],
    ) -> None:
        """Publish a full observation → decision cycle in one call."""
        self.publish_observation(obs_msg)
        self.publish_forecast(fc_msg)
        self.publish_risk(risk_msg)
        self.publish_route(route_msg)

    def __repr__(self) -> str:
        connected = self.transport.is_connected() if hasattr(self.transport, 'is_connected') else None
        return (
            f"OffshorePublisher(connected={connected}, "
            f"topics={list(self._topics.keys())})"
        )