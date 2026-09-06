#!/usr/bin/env python3
"""
PHASE 6 — MESSAGE SCHEMAS (shared)

Machine-readable JSON schemas for all MQTT message types in Phase 6.

Schema design principles:
- Every message has `message_type` and `timestamp` (ISO 8601 UTC).
- Forecast message explicitly carries `forecast_method` ("MOTION_AWARE_XGBOOST"
  or "PERSISTENCE_FALLBACK") and `fallback_reason` — never inferred from coordinates.
- Risk/Route messages carry `communication_state` and relevant uncertainty info.
- All messages are self-describing; no out-of-band schema needed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# ── Message Type Enum ─────────────────────────────────────────────────────────
class MessageType(str, Enum):
    OBSERVATION = "observation"
    FORECAST = "forecast"
    RISK = "risk"
    ROUTE = "route"
    STATUS = "status"
    REPLAN = "replan"


# ── Forecast Method Enum ──────────────────────────────────────────────────────
class ForecastMethod(str, Enum):
    MOTION_AWARE_XGBOOST = "MOTION_AWARE_XGBOOST"
    PERSISTENCE_FALLBACK = "PERSISTENCE_FALLBACK"


# ── Communication State Enum (matches Phase 4 state machine) ──────────────────
class CommunicationState(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    LAST_KNOWN_STATE = "LAST-KNOWN-STATE MODE"  # matches Phase 4 naming


# ── Validation Helpers ────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ts(timestamp: str | datetime | None) -> str:
    """Return an ISO timestamp. `timestamp` is an optional override so that
    deterministic synthetic demos can anchor message times to a scenario clock;
    when None, uses the real wall-clock time."""
    if timestamp is None:
        return _now_iso()
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.isoformat(timespec="seconds")
    return str(timestamp)


def _validate_required(obj: dict, required: list[str], msg_type: str) -> tuple[bool, str]:
    missing = [f for f in required if f not in obj]
    if missing:
        return False, f"{msg_type}: missing required fields: {missing}"
    return True, ""


# ── Observation Message ───────────────────────────────────────────────────────
# Fields per spec Step 4:
#   message_type, timestamp, iceberg_id, latitude, longitude, data_source,
#   observation_time, (optional: length_nm, width_nm, prev_delta_* for eligibility)

OBSERVATION_REQUIRED = [
    "message_type", "timestamp", "iceberg_id",
    "latitude", "longitude", "data_source", "observation_time",
]


def build_observation(
    iceberg_id: str,
    lat: float,
    lon: float,
    observation_time: str | datetime,
    data_source: str = "SATELLITE",
    *,
    length_nm: float | None = None,
    width_nm: float | None = None,
    prev_delta_lat: float | None = None,
    prev_delta_lon: float | None = None,
    prev_speed: float | None = None,
    prev_bearing: float | None = None,
    timestamp: str | datetime | None = None,
    **extra_env,
) -> dict[str, Any]:
    """Build a valid observation message dict."""
    if isinstance(observation_time, datetime):
        obs_time = observation_time.isoformat(timespec="seconds")
    else:
        obs_time = str(observation_time)

    msg = {
        "message_type": MessageType.OBSERVATION.value,
        "timestamp": _ts(timestamp),
        "iceberg_id": iceberg_id,
        "latitude": float(lat),
        "longitude": float(lon),
        "data_source": data_source,
        "observation_time": obs_time,
    }
    if length_nm is not None:
        msg["length_nm"] = float(length_nm)
    if width_nm is not None:
        msg["width_nm"] = float(width_nm)
    if prev_delta_lat is not None:
        msg["prev_delta_lat"] = float(prev_delta_lat)
    if prev_delta_lon is not None:
        msg["prev_delta_lon"] = float(prev_delta_lon)
    if prev_speed is not None:
        msg["prev_speed"] = float(prev_speed)
    if prev_bearing is not None:
        msg["prev_bearing"] = float(prev_bearing)
    # Allow pass-through of environmental features
    msg.update({k: v for k, v in extra_env.items() if v is not None})
    return msg


def validate_observation(msg: dict[str, Any]) -> tuple[bool, str]:
    ok, err = _validate_required(msg, OBSERVATION_REQUIRED, "observation")
    if not ok:
        return False, err
    if msg.get("message_type") != MessageType.OBSERVATION.value:
        return False, "observation: message_type must be 'observation'"
    return True, ""


# ── Forecast Message ──────────────────────────────────────────────────────────
# Spec Step 4 requires explicit forecast_method + fallback_reason
FORECAST_REQUIRED = [
    "message_type", "timestamp", "iceberg_id",
    "forecast_method", "model_used", "predecessor_available",
    "fallback", "fallback_reason",
    "forecast_latitude", "forecast_longitude", "forecast_horizon",
]


def build_forecast(
    iceberg_id: str,
    forecast_lat: float,
    forecast_lon: float,
    forecast_horizon_hours: float,
    forecast_method: str,  # "MOTION_AWARE_XGBOOST" or "PERSISTENCE_FALLBACK"
    model_used: str,       # "motion_aware_xgb" or "persistence"
    predecessor_available: bool,
    fallback: bool,
    fallback_reason: str | None,
    *,
    communication_state: str = "FRESH",
    data_freshness: str = "FRESH",
    timestamp: str | datetime | None = None,
) -> dict[str, Any]:
    """Build a valid forecast message dict (spec §7 contract)."""
    return {
        "message_type": MessageType.FORECAST.value,
        "timestamp": _ts(timestamp),
        "iceberg_id": iceberg_id,
        "forecast_method": forecast_method,
        "model_used": model_used,
        "predecessor_available": bool(predecessor_available),
        "fallback": bool(fallback),
        "fallback_reason": fallback_reason,
        "forecast_latitude": float(forecast_lat),
        "forecast_longitude": float(forecast_lon),
        "forecast_horizon": float(forecast_horizon_hours),
        "communication_state": communication_state,
        "data_freshness": data_freshness,
    }


def validate_forecast(msg: dict[str, Any]) -> tuple[bool, str]:
    ok, err = _validate_required(msg, FORECAST_REQUIRED, "forecast")
    if not ok:
        return False, err
    if msg.get("message_type") != MessageType.FORECAST.value:
        return False, "forecast: message_type must be 'forecast'"
    if msg.get("forecast_method") not in [m.value for m in ForecastMethod]:
        return False, f"forecast: invalid forecast_method '{msg.get('forecast_method')}'"
    return True, ""


# ── Risk Message ──────────────────────────────────────────────────────────────
RISK_REQUIRED = [
    "message_type", "timestamp", "iceberg_id",
    "risk_level", "risk_score", "communication_state",
    "uncertainty_sigma_km", "envelope_radius_km", "corridor_radius_km",
]


def build_risk(
    iceberg_id: str,
    risk_level: str,         # "LOW" | "MODERATE" | "HIGH"
    risk_score: float,
    communication_state: str,
    uncertainty_sigma_km: float,
    envelope_radius_km: float,
    corridor_radius_km: float,
    *,
    separation_km: float | None = None,
    separation_effective_km: float | None = None,
    anchor_tag: str | None = None,
    data_freshness: str | None = None,
    timestamp: str | datetime | None = None,
    **extra,
) -> dict[str, Any]:
    """Build a valid risk message dict."""
    msg = {
        "message_type": MessageType.RISK.value,
        "timestamp": _ts(timestamp),
        "iceberg_id": iceberg_id,
        "risk_level": risk_level,
        "risk_score": float(risk_score),
        "communication_state": communication_state,
        "uncertainty_sigma_km": float(uncertainty_sigma_km),
        "envelope_radius_km": float(envelope_radius_km),
        "corridor_radius_km": float(corridor_radius_km),
    }
    if separation_km is not None:
        msg["separation_km"] = float(separation_km)
    if separation_effective_km is not None:
        msg["separation_effective_km"] = float(separation_effective_km)
    if anchor_tag is not None:
        msg["anchor_tag"] = anchor_tag
    if data_freshness is not None:
        msg["data_freshness"] = data_freshness
    msg.update({k: v for k, v in extra.items() if v is not None})
    return msg


def validate_risk(msg: dict[str, Any]) -> tuple[bool, str]:
    ok, err = _validate_required(msg, RISK_REQUIRED, "risk")
    if not ok:
        return False, err
    if msg.get("message_type") != MessageType.RISK.value:
        return False, "risk: message_type must be 'risk'"
    if msg.get("risk_level") not in ["LOW", "MODERATE", "HIGH"]:
        return False, f"risk: invalid risk_level '{msg.get('risk_level')}'"
    return True, ""


# ── Route Message ─────────────────────────────────────────────────────────────
ROUTE_REQUIRED = [
    "message_type", "timestamp",
    "route_status", "route_label", "communication_state", "data_freshness",
]


def build_route(
    route_status: str,           # "SAFE" | "CAUTION" | "NO_SAFE_ROUTE_FOUND"
    route_label: str,            # "ROUTE" | "LAST-KNOWN-STATE ROUTE"
    communication_state: str,
    data_freshness: str,
    *,
    route_distance_km: float | None = None,
    direct_distance_km: float | None = None,
    distance_overhead_pct: float | None = None,
    estimated_travel_time_hours: float | None = None,
    max_risk_score_encountered: float | None = None,
    waypoints: list[dict[str, float]] | None = None,
    replan_reason: str | None = None,
    timestamp: str | datetime | None = None,
    **extra,
) -> dict[str, Any]:
    """Build a valid route message dict."""
    msg = {
        "message_type": MessageType.ROUTE.value,
        "timestamp": _ts(timestamp),
        "route_status": route_status,
        "route_label": route_label,
        "communication_state": communication_state,
        "data_freshness": data_freshness,
    }
    if route_distance_km is not None:
        msg["route_distance_km"] = float(route_distance_km)
    if direct_distance_km is not None:
        msg["direct_distance_km"] = float(direct_distance_km)
    if distance_overhead_pct is not None:
        msg["distance_overhead_pct"] = float(distance_overhead_pct)
    if estimated_travel_time_hours is not None:
        msg["estimated_travel_time_hours"] = float(estimated_travel_time_hours)
    if max_risk_score_encountered is not None:
        msg["max_risk_score_encountered"] = float(max_risk_score_encountered)
    if waypoints is not None:
        msg["waypoints"] = [{"lat": float(w["lat"]), "lon": float(w["lon"])} for w in waypoints]
    if replan_reason is not None:
        msg["replan_reason"] = replan_reason
    msg.update({k: v for k, v in extra.items() if v is not None})
    return msg


def validate_route(msg: dict[str, Any]) -> tuple[bool, str]:
    ok, err = _validate_required(msg, ROUTE_REQUIRED, "route")
    if not ok:
        return False, err
    if msg.get("message_type") != MessageType.ROUTE.value:
        return False, "route: message_type must be 'route'"
    if msg.get("route_status") not in ["SAFE", "CAUTION", "NO_SAFE_ROUTE_FOUND"]:
        return False, f"route: invalid route_status '{msg.get('route_status')}'"
    return True, ""


# ── Communication Status Message ──────────────────────────────────────────────
STATUS_REQUIRED = [
    "message_type", "timestamp",
    "communication_state", "last_message_timestamp", "message_age_hours", "reason",
]


def build_status(
    communication_state: str,
    last_message_timestamp: str | None,
    message_age_hours: float,
    reason: str,
    timestamp: str | datetime | None = None,
) -> dict[str, Any]:
    """Build a valid communication status message dict."""
    return {
        "message_type": MessageType.STATUS.value,
        "timestamp": _ts(timestamp),
        "communication_state": communication_state,
        "last_message_timestamp": last_message_timestamp,
        "message_age_hours": float(message_age_hours),
        "reason": reason,
    }


def validate_status(msg: dict[str, Any]) -> tuple[bool, str]:
    ok, err = _validate_required(msg, STATUS_REQUIRED, "status")
    if not ok:
        return False, err
    if msg.get("message_type") != MessageType.STATUS.value:
        return False, "status: message_type must be 'status'"
    if msg.get("communication_state") not in [s.value for s in CommunicationState]:
        return False, f"status: invalid communication_state '{msg.get('communication_state')}'"
    return True, ""


# ── Replan Message ────────────────────────────────────────────────────────────
REPLAN_REQUIRED = [
    "message_type", "timestamp",
    "replan_trigger", "forecast_method", "risk_level", "route_status",
]


def build_replan(
    replan_trigger: str,         # e.g., "NEW_OBSERVATION", "COMMUNICATION_RECOVERY"
    forecast_method: str,        # "MOTION_AWARE_XGBOOST" or "PERSISTENCE_FALLBACK"
    risk_level: str,             # "LOW" | "MODERATE" | "HIGH"
    route_status: str,           # "SAFE" | "CAUTION" | "NO_SAFE_ROUTE_FOUND"
    *,
    iceberg_id: str | None = None,
    communication_state: str | None = None,
    data_freshness: str | None = None,
    timestamp: str | datetime | None = None,
    **extra,
) -> dict[str, Any]:
    """Build a valid replan message dict."""
    msg = {
        "message_type": MessageType.REPLAN.value,
        "timestamp": _ts(timestamp),
        "replan_trigger": replan_trigger,
        "forecast_method": forecast_method,
        "risk_level": risk_level,
        "route_status": route_status,
    }
    if iceberg_id is not None:
        msg["iceberg_id"] = iceberg_id
    if communication_state is not None:
        msg["communication_state"] = communication_state
    if data_freshness is not None:
        msg["data_freshness"] = data_freshness
    msg.update({k: v for k, v in extra.items() if v is not None})
    return msg


def validate_replan(msg: dict[str, Any]) -> tuple[bool, str]:
    ok, err = _validate_required(msg, REPLAN_REQUIRED, "replan")
    if not ok:
        return False, err
    if msg.get("message_type") != MessageType.REPLAN.value:
        return False, "replan: message_type must be 'replan'"
    return True, ""


# ── Generic validator ─────────────────────────────────────────────────────────
VALIDATORS = {
    MessageType.OBSERVATION.value: validate_observation,
    MessageType.FORECAST.value: validate_forecast,
    MessageType.RISK.value: validate_risk,
    MessageType.ROUTE.value: validate_route,
    MessageType.STATUS.value: validate_status,
    MessageType.REPLAN.value: validate_replan,
}


def validate_message(msg: dict[str, Any]) -> tuple[bool, str]:
    """Dispatch to the appropriate validator by message_type."""
    mtype = msg.get("message_type")
    if mtype not in VALIDATORS:
        return False, f"unknown message_type: {mtype}"
    return VALIDATORS[mtype](msg)


# ── CLI for quick schema demo ─────────────────────────────────────────────────
def main() -> int:
    print("Phase 6 — Message Schema Examples")
    print("=" * 60)

    # Observation
    obs = build_observation(
        "DEMO-A", -68.5, 76.0, "2025-11-12T12:00:00+00:00",
        data_source="SATELLITE", length_nm=12.0, width_nm=8.0,
        prev_delta_lat=0.08, prev_delta_lon=0.12, prev_speed=1.5, prev_bearing=56.3,
    )
    ok, err = validate_observation(obs)
    print(f"Observation: {'OK' if ok else 'FAIL:' + err}")
    print(json.dumps(obs, indent=2))

    # Forecast (motion-aware)
    fc = build_forecast(
        "DEMO-A", -68.503, 75.899, 168.0,
        forecast_method="MOTION_AWARE_XGBOOST", model_used="motion_aware_xgb",
        predecessor_available=True, fallback=False, fallback_reason=None,
    )
    ok, err = validate_forecast(fc)
    print(f"\nForecast (motion): {'OK' if ok else 'FAIL:' + err}")
    print(json.dumps(fc, indent=2))

    # Forecast (persistence fallback)
    fc2 = build_forecast(
        "DEMO-B", -68.5, 76.0, 168.0,
        forecast_method="PERSISTENCE_FALLBACK", model_used="persistence",
        predecessor_available=False, fallback=True, fallback_reason="NO_VALID_PREDECESSOR",
    )
    ok, err = validate_forecast(fc2)
    print(f"\nForecast (persistence): {'OK' if ok else 'FAIL:' + err}")
    print(json.dumps(fc2, indent=2))

    # Risk
    risk = build_risk("DEMO-A", "MODERATE", 37.4, "FRESH", 50.0, 82.3, 87.3,
                      separation_km=96.1, separation_effective_km=91.1,
                      anchor_tag="heuristic_fallback")
    ok, err = validate_risk(risk)
    print(f"\nRisk: {'OK' if ok else 'FAIL:' + err}")
    print(json.dumps(risk, indent=2))

    # Route
    route = build_route(
        "SAFE", "ROUTE", "FRESH", "FRESH",
        route_distance_km=164.3, direct_distance_km=141.6,
        distance_overhead_pct=16.1, estimated_travel_time_hours=7.4,
        max_risk_score_encountered=0.0,
        waypoints=[{"lat": -68.0, "lon": 76.0}, {"lat": -67.2, "lon": 78.6}],
    )
    ok, err = validate_route(route)
    print(f"\nRoute: {'OK' if ok else 'FAIL:' + err}")
    print(json.dumps(route, indent=2))

    # Status
    status = build_status("FRESH", "2025-11-12T12:00:00+00:00", 0.0, "within freshness window")
    ok, err = validate_status(status)
    print(f"\nStatus: {'OK' if ok else 'FAIL:' + err}")
    print(json.dumps(status, indent=2))

    # Replan
    replan = build_replan(
        "COMMUNICATION_RECOVERY", "MOTION_AWARE_XGBOOST", "MODERATE", "SAFE",
        iceberg_id="DEMO-A", communication_state="FRESH", data_freshness="FRESH",
    )
    ok, err = validate_replan(replan)
    print(f"\nReplan: {'OK' if ok else 'FAIL:' + err}")
    print(json.dumps(replan, indent=2))

    print("\n" + "=" * 60)
    print("All schemas demonstrated — validation functions available.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())