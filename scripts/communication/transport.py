#!/usr/bin/env python3
"""
PHASE 6 — TRANSPORT LAYER

Abstracts the MQTT transport behind a simple Interface so:
- Real Mosquitto-backed transport works over 127.0.0.1:1883 (paho-mqtt).
- In-memory transport works for deterministic testing (no broker needed).

The interface is intentionally minimal (connect/publish/subscribe/disconnect)
so the demo/validation logic never calls paho directly.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]

log = logging.getLogger(__name__)

# ── Abstract interface ────────────────────────────────────────────────────────
class Transport:
    """Minimal pub/sub transport interface."""

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def publish(self, topic: str, payload: dict[str, Any], *, qos: int = 1) -> None: ...
    def subscribe(self, topic: str, callback: Callable[[str, dict], None], *, qos: int = 1) -> None: ...
    def is_connected(self) -> bool: ...


# ── In-memory transport (deterministic, no broker) ───────────────────────────
class InMemoryTransport(Transport):
    """
    Synchronous in-memory transport. Messages are delivered to subscribers
    in the same call (or queued if a buffer is desired). Fully deterministic.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable]] = {}
        self._connected = False
        # retained messages per topic (for 'latest' semantics)
        self._retained: dict[str, dict] = {}
        # ordered log of all published messages (for demo/validation)
        self.log: list[dict[str, Any]] = []

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def publish(self, topic: str, payload: dict[str, Any], *, qos: int = 1) -> None:
        self._retained[topic] = payload
        self.log.append({"topic": topic, "qos": qos, "payload": payload})
        # Deliver to matching subscribers (exact-topic match; MQTT wildcards not needed here)
        for sub_topic, cbs in list(self._subs.items()):
            if sub_topic == topic:
                for cb in list(cbs):
                    cb(topic, payload)

    def subscribe(self, topic: str, callback: Callable, *, qos: int = 1) -> None:
        self._subs.setdefault(topic, []).append(callback)

    def unsubscribe(self, topic: str, callback: Callable | None = None) -> None:
        if callback is None:
            self._subs.pop(topic, None)
        else:
            lst = self._subs.get(topic)
            if lst:
                try:
                    lst.remove(callback)
                except ValueError:
                    pass

    def retained(self, topic: str) -> dict | None:
        return self._retained.get(topic)

    def clear_log(self) -> None:
        self.log.clear()


# ── paho-mqtt transport (real broker) ─────────────────────────────────────────
class PahoTransport(Transport):
    """
    Real MQTT transport over a running Mosquitto broker (localhost:1883).
    Uses paho-mqtt 2.x with synchronous connect + threaded network loop.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 1883,
        keepalive: int = 60,
        client_id: str = "himdrushti-phase6",
    ) -> None:
        self.host = host
        self.port = port
        self.keepalive = keepalive
        self.client_id = client_id
        self._client = None
        self._connected = False
        self._callbacks: dict[str, list[Callable]] = {}

    def connect(self) -> None:
        import paho.mqtt.client as mqtt

        if self._client is not None and self._connected:
            return

        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                             client_id=self.client_id)

        def on_connect(c, u, f, rc, props=None):
            if rc == 0:
                self._connected = True
                log.info(f"PahoTransport connected ({self.client_id}@{self.host}:{self.port})")
                for topic, cbs in list(self._callbacks.items()):
                    c.subscribe(topic, qos=1)
            else:
                log.warning(f"PahoTransport connect failed rc={rc}")

        def on_message(c, u, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
            except Exception as e:
                log.warning(f"PahoTransport JSON decode error on {msg.topic}: {e}")
                return
            for cb in list(self._callbacks.get(msg.topic, [])):
                cb(msg.topic, payload)
            # Wildcards: also check +/# style — not needed for exact-topic tests,
            # but support prefix-wildcard subscriptions if ever added.

        def on_disconnect(c, u, *args):
            self._connected = False

        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        client.connect(self.host, self.port, keepalive=self.keepalive)
        client.loop_start()

        # wait briefly for the CONNACK
        deadline = time.time() + 2.0
        while not self._connected and time.time() < deadline:
            time.sleep(0.02)

        if not self._connected:
            client.loop_stop()
            raise RuntimeError(
                f"PahoTransport failed to connect to {self.host}:{self.port} — "
                "ensure Mosquitto is running."
            )

        self._client = client

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    def publish(self, topic: str, payload: dict[str, Any], *, qos: int = 1) -> None:
        if not self.is_connected():
            raise RuntimeError(f"PahoTransport not connected — cannot publish to {topic}")
        self._client.publish(topic, json.dumps(payload, default=str), qos=qos)

    def subscribe(self, topic: str, callback: Callable, *, qos: int = 1) -> None:
        if topic not in self._callbacks:
            self._callbacks[topic] = []
        self._callbacks[topic].append(callback)
        if self.is_connected():
            self._client.subscribe(topic, qos=qos)


# ── Factory ───────────────────────────────────────────────────────────────────
def make_transport(prefer: str = "auto") -> Transport:
    """
    Create a Transport.

    prefer:
      "auto"   -> try Paho (real Mosquitto) on 127.0.0.1:1883; fall back to InMemory if broker unreachable.
      "paho"   -> require real Mosquitto (error if not available).
      "memory" -> always in-memory (deterministic, no broker needed).
    """
    if prefer == "memory":
        t = InMemoryTransport()
        t.connect()
        return t

    # Try real broker first
    try:
        import paho.mqtt.client as _m
        t = PahoTransport()
        t.connect()
        return t
    except Exception as e:
        log.warning(f"make_transport: real broker unavailable ({e})")
        if prefer == "paho":
            raise
        t = InMemoryTransport()
        t.connect()
        log.info("make_transport: using InMemoryTransport (deterministic fallback)")
        return t