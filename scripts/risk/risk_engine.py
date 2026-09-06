#!/usr/bin/env python3
"""
PHASE 4 — UNCERTAINTY-AWARE ICEBERG RISK ENGINE  (core, deterministic)

The first operational decision-support layer of Him-Drushti. It computes, for a
vessel and a set of icebergs in East Prydz Bay:

  Iceberg Forecast -> Forecast Uncertainty -> Spatiotemporal Risk Corridor ->
  Vessel-Specific Risk Score -> Navigation Risk Layer

DESIGN PRINCIPLES (Phase 4 spec):
  * The engine does NOT claim any trajectory model is accurate. The reference
    forecast source is the persistence baseline (Phase 3C "best model" finding).
  * Uncertainty is expressed explicitly, from EMPIRICAL Phase 3C validation
    residuals where the forecast source is covered, or from a labelled
    conservative HEURISTIC fallback otherwise. It is never presented as a
    validated statistical confidence interval.
  * The risk formula is deterministic and explainable; every weight lives in
    scripts/risk/risk_config.yaml and is documented.
  * "Low / Moderate / High" are prototype decision-support categories, NOT
    certified maritime safety standards.
  * Communication resilience is a deterministic state machine:
    FRESH -> STALE -> LAST-KNOWN-STATE MODE (COMMUNICATION LOST) -> RECOVERY.

DATASET / MODEL INTEGRITY
  * The engine only READS existing datasets; it writes only to outputs/risk/.
  * No trajectory model is trained or retrained. No dataset is modified.
  * No observations are fabricated: synthetic positions are only accepted when
    a caller sets synthetic=True explicitly (the demo does this, and labels
    everything "DEMO / SYNTHETIC SCENARIO").

Usage (as a library):
    from risk_engine import RiskEngine, IcebergState, Forecast, VesselState
    engine = RiskEngine()                     # loads scripts/risk/risk_config.yaml
    res = engine.evaluate(inputs, asof)       # list[RiskAssessment]
    layer = engine.navigation_layer(assessments, include=cfg['output']['include_nav_layer'])
    payload = engine.build_outputs(assessments, layer, asof)   # (dict, csv_rows)

The CLI (run_risk_demo.py) drives the labelled synthetic demonstration A-E.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ── Paths / defaults ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "risk_config.yaml"
EARTH_RADIUS_KM = 6371.0088  # consistent with scripts/ml/baseline_model.py

log = logging.getLogger(__name__)

# Lower / upper class ranks for the navigation layer (LOW < MODERATE < HIGH)
CLASS_ORDER = ["LOW", "MODERATE", "HIGH"]
CLASS_RANK = {k: i for i, k in enumerate(CLASS_ORDER)}


# ── Geodesy (mirrors scripts/ml/eval_metrics_expanded.py) ────────────────────
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km. R = 6371.0088 km (project convention)."""
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlat, dlon = rlat2 - rlat1, rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _add_km_bearing(lat: float, lon: float, d_km: float, bearing_deg: float) -> tuple[float, float]:
    """Destination point after d_km along a great-circle bearing (km-based stub)."""
    delta_deg = d_km / (math.pi * EARTH_RADIUS_KM / 180.0)  # ~1 deg per 111.2 km
    rlat = math.radians(lat)
    brng = math.radians(bearing_deg)
    d_rad = math.asin(max(-1.0, min(1.0, delta_deg * math.pi / 180.0)))
    # approximate local (equirectangular) step used only for envelope/demo geometry
    new_lat = lat + d_rad * 180.0 / math.pi * math.cos(brng)
    new_lon = lon + (d_rad * 180.0 / math.pi) * math.sin(brng) / max(math.cos(rlat), 1e-6)
    return new_lat, new_lon


# ── Input records ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class IcebergState:
    """Last-known observed state of an iceberg."""
    iceberg_id: str
    lat: float
    lon: float
    observed_at: datetime
    length_nm: float
    width_nm: float
    drifting: bool = True                   # False => treated as grounded (D23-like)
    uncertainty_mode: str | None = None     # None|'drifting'|'grounded'|'zero_shot'
    synthetic: bool = False                 # must be True for non-project data
    source_note: str = ""


@dataclass(frozen=True)
class Forecast:
    """Predicted iceberg position at a future valid time."""
    iceberg_id: str
    pred_lat: float
    pred_lon: float
    valid_at: datetime
    horizon_hours: float
    source: str = "persistence"             # persistence | rf | xgboost | lstm | custom
    source_note: str = ""


@dataclass(frozen=True)
class VesselState:
    vessel_id: str = "RV-DEMO"
    lat: float = -68.0
    lon: float = 76.0
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    draft_m: float = 8.0
    speed_knots: float = 12.0
    heading_deg: float = 180.0
    synthetic: bool = False


# ── Assessment results ───────────────────────────────────────────────────────
@dataclass
class UncertaintyBreakdown:
    sigma_total_km: float
    sigma_forecast_km: float
    sigma_obs_km: float
    sigma_env_km: float
    sigma_stale_km: float
    anchor_tag: str              # 'empirical_drifting' | 'empirical_grounded' |
                                 # 'empirical_zero_shot' | 'heuristic_fallback'
    anchor_footnote: str


@dataclass
class RiskAssessment:
    asof: datetime
    vessel: VesselState
    iceberg: IcebergState
    forecast: Forecast
    separation_km: float
    separation_effective_km: float
    uncertainty: UncertaintyBreakdown
    envelope_radius_km: float
    corridor_radius_km: float
    risk_score: float            # 0..100
    risk_class: str              # LOW | MODERATE | HIGH
    data_freshness: str          # FRESH | STALE | LAST-KNOWN-STATE MODE
    communication_status: str    # NOMINAL | DEGRADED | COMMUNICATION LOST
    age_hours: float
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "timestamp": self.asof.isoformat(timespec="seconds"),
            "vessel_position": {"lat": self.vessel.lat, "lon": self.vessel.lon},
            "iceberg_id": self.iceberg.iceberg_id,
            "iceberg_observed_position": {"lat": self.iceberg.lat, "lon": self.iceberg.lon},
            "iceberg_size_nm": {"length": self.iceberg.length_nm, "width": self.iceberg.width_nm},
            "forecast_position": {"lat": self.forecast.pred_lat, "lon": self.forecast.pred_lon},
            "forecast_horizon_hours": self.forecast.horizon_hours,
            "forecast_source": self.forecast.source,
            "uncertainty_sigma_km": self.uncertainty.sigma_total_km,
            "uncertainty_components_km": {
                "forecast": self.uncertainty.sigma_forecast_km,
                "obs": self.uncertainty.sigma_obs_km,
                "env": self.uncertainty.sigma_env_km,
                "stale": self.uncertainty.sigma_stale_km,
            },
            "uncertainty_anchor": self.uncertainty.anchor_tag,
            "envelope_radius_km": self.envelope_radius_km,
            "corridor_radius_km": self.corridor_radius_km,
            "distance_to_vessel_km": self.separation_km,
            "safety_margin_km": self.separation_km - self.iceberg_sep_for_notes(),
            "risk_score": round(self.risk_score, 4),
            "risk_class": self.risk_class,
            "data_freshness": self.data_freshness,
            "communication_status": self.communication_status,
            "age_hours": self.age_hours,
            "synthetic": self.iceberg.synthetic or self.vessel.synthetic or True,
            "notes": self.notes,
        }
        return d

    def iceberg_sep_for_notes(self) -> float:
        # separation already equals vessel->forecast; safety margin is documented
        return self.separation_km

    def to_csv_row(self) -> dict[str, Any]:
        return {
            "timestamp": self.asof.isoformat(timespec="seconds"),
            "vessel_id": self.vessel.vessel_id,
            "vessel_lat": self.vessel.lat,
            "vessel_lon": self.vessel.lon,
            "iceberg_id": self.iceberg.iceberg_id,
            "iceberg_lat": self.iceberg.lat,
            "iceberg_lon": self.iceberg.lon,
            "forecast_lat": self.forecast.pred_lat,
            "forecast_lon": self.forecast.pred_lon,
            "forecast_horizon_hours": self.forecast.horizon_hours,
            "forecast_source": self.forecast.source,
            "uncertainty_sigma_km": self.uncertainty.sigma_total_km,
            "envelope_radius_km": self.envelope_radius_km,
            "corridor_radius_km": self.corridor_radius_km,
            "distance_to_vessel_km": self.separation_km,
            "separation_effective_km": self.separation_effective_km,
            "iceberg_length_nm": self.iceberg.length_nm,
            "iceberg_width_nm": self.iceberg.width_nm,
            "risk_score": round(self.risk_score, 4),
            "risk_class": self.risk_class,
            "data_freshness": self.data_freshness,
            "communication_status": self.communication_status,
            "age_hours": self.age_hours,
            "synthetic": self.iceberg.synthetic or self.vessel.synthetic,
            "forecast_source_note": self.forecast.source_note,
        }


# ── Engine ───────────────────────────────────────────────────────────────────
class RiskEngine:
    """Deterministic, config-driven risk engine. No I/O beyond config read."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        path = Path(config_path) if config_path else DEFAULT_CONFIG
        with open(path, "r", encoding="utf-8") as fh:
            self.cfg: dict[str, Any] = yaml.safe_load(fh)
        self._cfg_path = path
        self._empirical_anchors = self.cfg["uncertainty"]["anchors"]

    # ---- Uncertainty ------------------------------------------------------
    def _anchor_for(self, iceberg: IcebergState) -> tuple[float, str, str]:
        mode = iceberg.uncertainty_mode or ("grounded" if not iceberg.drifting else "drifting")
        if mode == "grounded":
            return self._empirical_anchors["grounded_sigma_km"], "empirical_grounded", \
                "EMPIRICAL: Phase 3C persistence pos-RMSE @168h, grounded icebergs (D23, n=30)"
        if mode == "zero_shot":
            return self._empirical_anchors["zero_shot_sigma_km"], "empirical_zero_shot", \
                "EMPIRICAL: Phase 3C persistence pos-RMSE @168h, C39 zero-shot (n=9)"
        return self._empirical_anchors["drifting_sigma_km"], "empirical_drifting", \
            "EMPIRICAL: Phase 3C persistence pos-RMSE @168h, drifting icebergs (n=24)"

    def sigma_forecast(self, iceberg: IcebergState, forecast: Forecast) -> tuple[float, str, str, float]:
        """
        EMPIRICAL validation-derived sigma at the requested horizon.
        sigma(h) = sigma_ref * (h / reference_horizon_hours) ** horizon_scaling_gamma.
        The power law is a HEURISTIC (random-walk analogue); the anchor is empirical.
        For a source with no empirical record, returns the labelled conservative
        HEURISTIC fallback and flags it.
        """
        cfg_u = self.cfg["uncertainty"]
        gamma = float(cfg_u["horizon_scaling_gamma"])
        h_ref = float(cfg_u["reference_horizon_hours"])
        h = max(float(forecast.horizon_hours), 0.0)
        if forecast.source.lower() in [s.lower() for s in cfg_u["empirical_sources"]]:
            ref, tag, footnote = self._anchor_for(iceberg)
            sigma = ref * (h / h_ref) ** gamma if h > 0 else 0.0
            return sigma, tag, footnote, ref
        fallback = float(cfg_u["fallback_sigma_km"])
        note = str(cfg_u["fallback_sigma_note"])
        sigma = fallback * (h / h_ref) ** gamma if h > 0 else 0.0
        return sigma, "heuristic_fallback", note, fallback

    def sigma_stale(self, age_hours: float, communication_status: str) -> float:
        cfg_f = self.cfg["freshness"]
        if age_hours <= 0:
            return 0.0
        growth = float(cfg_f["stale_growth_rate_km_per_h"])
        cap = float(cfg_f["stale_growth_cap_km"])
        if communication_status == "COMMUNICATION LOST":
            growth *= float(cfg_f["comm_loss_growth_factor"])
        return min(growth * age_hours, cap)

    # ---- State machine ------------------------------------------------------
    def freshness_state(self, observed_at: datetime, asof: datetime) -> tuple[str, str, float]:
        age_h = max((asof - observed_at).total_seconds() / 3600.0, 0.0)
        cfg_f = self.cfg["freshness"]
        if age_h < float(cfg_f["freshness_hours"]):
            return "FRESH", "NOMINAL", age_h
        if age_h < float(cfg_f["comm_loss_hours"]):
            return "STALE", "DEGRADED", age_h
        return "LAST-KNOWN-STATE MODE", "COMMUNICATION LOST", age_h

    # ---- Risk score ---------------------------------------------------------
    def _risk_score(self, sep_eff_km: float, sigma_total_km: float,
                    iceberg: IcebergState) -> float:
        cfg_r = self.cfg["risk"]
        sigma = max(sigma_total_km, 1e-9)
        n_units = sep_eff_km / sigma
        size_norm = math.sqrt(iceberg.length_nm * iceberg.width_nm) \
            / float(cfg_r["reference_size_nm"])
        size_scaling = min(1.0 + math.log2(max(size_norm, 1e-9)), float(cfg_r["size_scaling_cap"]))
        raw = size_scaling * math.exp(-0.5 * n_units * n_units)
        return 100.0 * min(raw, 1.0)

    def _risk_class(self, score: float) -> str:
        for cls, spec in self.cfg["risk"]["classes"].items():
            if score >= float(spec["min_score"]):
                best = cls
        return best  # noqa: F821  (last iteration is the highest band)

    # ---- One iceberg --------------------------------------------------------
    def assess(self, iceberg: IcebergState, forecast: Forecast,
               vessel: VesselState, asof: datetime,
               sigma_env_km: float | None = None) -> RiskAssessment:
        notes: list[str] = []
        data_freshness, comm_status, age_h = self.freshness_state(iceberg.observed_at, asof)

        sigma_f, anchor, footnote, _ref = self.sigma_forecast(iceberg, forecast)
        if anchor == "heuristic_fallback":
            notes.append(str(self.cfg["uncertainty"]["fallback_sigma_note"]))
        sigma_obs = float(self.cfg["uncertainty"]["sigma_obs_km"])
        sigma_env = float(self.cfg["uncertainty"]["sigma_env_km_default"]) \
            if sigma_env_km is None else float(sigma_env_km)
        sigma_stale = self.sigma_stale(age_h, comm_status)
        sigma_total = math.sqrt(sigma_f**2 + sigma_obs**2 + sigma_env**2 + sigma_stale**2)

        sep_km = haversine_km(vessel.lat, vessel.lon, forecast.pred_lat, forecast.pred_lon)
        margin = float(self.cfg["risk"]["safety_buffer_km"])
        sep_eff = max(sep_km - margin, 0.0)
        score = self._risk_score(sep_eff, sigma_total, iceberg)
        cls = self._risk_class(score)

        k_sigma = float(self.cfg["uncertainty"]["k_sigma_envelope"])
        envelope_radius = k_sigma * sigma_total
        corridor_radius = envelope_radius + margin

        if data_freshness == "LAST-KNOWN-STATE MODE":
            notes.append("COMMUNICATION LOST: no invented observations; "
                         "continuing with last known state (LAST-KNOWN-STATE MODE).")
        if iceberg.synthetic or vessel.synthetic:
            notes.append("SYNTHETIC DEMO DATA — NOT a real observation.")

        return RiskAssessment(
            asof=asof, vessel=vessel, iceberg=iceberg, forecast=forecast,
            separation_km=sep_km, separation_effective_km=sep_eff,
            uncertainty=UncertaintyBreakdown(
                sigma_total_km=round(sigma_total, 4),
                sigma_forecast_km=round(sigma_f, 4),
                sigma_obs_km=round(sigma_obs, 4),
                sigma_env_km=round(sigma_env, 4),
                sigma_stale_km=round(sigma_stale, 4),
                anchor_tag=anchor, anchor_footnote=footnote,
            ),
            envelope_radius_km=round(envelope_radius, 4),
            corridor_radius_km=round(corridor_radius, 4),
            risk_score=round(score, 4), risk_class=cls,
            data_freshness=data_freshness, communication_status=comm_status,
            age_hours=round(age_h, 3), notes=notes,
        )

    # ---- Multiple icebergs / navigation layer -------------------------------
    def evaluate(self, icebergs: list[IcebergState], forecasts: list[Forecast],
                 vessel: VesselState, asof: datetime,
                 sigma_env_km: float | None = None) -> list[RiskAssessment]:
        by_id = {f.iceberg_id: f for f in forecasts}
        out: list[RiskAssessment] = []
        for ice in icebergs:
            fc = by_id.get(ice.iceberg_id)
            if fc is None:
                log.warning("no forecast for iceberg %s (skipped in this cycle)", ice.iceberg_id)
                continue
            out.append(self.assess(ice, fc, vessel, asof, sigma_env_km))
        out.sort(key=lambda r: (-r.risk_score, r.iceberg.iceberg_id))
        return out

    def highest_risk(self, assessments: list[RiskAssessment]) -> RiskAssessment | None:
        return assessments[0] if assessments else None

    def navigation_layer(self, assessments: list[RiskAssessment],
                         grid_res_deg: float | None = None) -> dict[str, Any]:
        """Max-class per grid cell across all corridors (LPF for a routing engine)."""
        region = self.cfg["region"]
        res = float(grid_res_deg or self.cfg["navigation"]["grid_resolution_degrees"])
        lat0, lat1 = region["lat_min"], region["lat_max"]
        lon0, lon1 = region["lon_min"], region["lon_max"]
        n_lat = int(round((lat1 - lat0) / res)) + 1
        n_lon = int(round((lon1 - lon0) / res)) + 1

        cells: dict[tuple[int, int], float] = {}
        for a in assessments:
            r_km = a.corridor_radius_km
            if r_km <= 0:
                continue
            # scan the grid cells roughly within the corridor bounding square
            dlat_deg = r_km / 111.2
            dlon_deg = r_km / (111.2 * max(math.cos(math.radians(a.forecast.pred_lat)), 1e-6))
            i0 = max(0, int(math.floor((a.forecast.pred_lat - dlat_deg - lat0) / res)))
            i1 = min(n_lat - 1, int(math.ceil((a.forecast.pred_lat + dlat_deg - lat0) / res)))
            j0 = max(0, int(math.floor((a.forecast.pred_lon - dlon_deg - lon0) / res)))
            j1 = min(n_lon - 1, int(math.ceil((a.forecast.pred_lon + dlon_deg - lon0) / res)))
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    c_lat = lat0 + i * res + res / 2
                    c_lon = lon0 + j * res + res / 2
                    d = haversine_km(c_lat, c_lon, a.forecast.pred_lat, a.forecast.pred_lon)
                    if d <= r_km:
                        cells[(i, j)] = max(cells.get((i, j), 0.0), a.risk_score)
        return {
            "grid_resolution_degrees": res,
            "crs": region["crs"],
            "lat_min": lat0, "lat_max": lat1,
            "lon_min": lon0, "lon_max": lon1,
            "n_cells_above_threshold": sum(1 for v in cells.values() if v >= 5.0),
            "covered_cells": len(cells),
            "cells": [{"lat": round(lat0 + i * res + res / 2, 5),
                       "lon": round(lon0 + j * res + res / 2, 5),
                       "max_score": round(v, 4),
                       "class": self._risk_class(v)}
                      for (i, j), v in sorted(cells.items())],
        }

    # ---- Outputs -------------------------------------------------------------
    def build_outputs(self, assessments: list[RiskAssessment],
                      layer: dict[str, Any] | None, asof: datetime) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        best = self.highest_risk(assessments)
        payload: dict[str, Any] = {
            "schema": "him_drushti.risk_engine.v1",
            "timestamp": asof.isoformat(timespec="seconds"),
            "demo_or_synthetic": any(a.iceberg.synthetic for a in assessments) or
                                 any(a.vessel.synthetic for a in assessments),
            "n_icebergs_assessed": len(assessments),
            "highest_risk_iceberg": best.iceberg.iceberg_id if best else None,
            "highest_risk_score": best.risk_score if best else None,
            "highest_risk_class": best.risk_class if best else None,
            "communication_status": sorted({a.communication_status for a in assessments}),
            "data_freshness": sorted({a.data_freshness for a in assessments}),
            "risk_classes_note": self.cfg["risk"]["class_boundary_note"],
            "uncertainty_note": self.cfg["uncertainty"]["envelope_note"],
            "icebergs": [a.to_dict() for a in assessments],
            "navigation_layer": layer,
        }
        rows = [a.to_csv_row() for a in assessments]
        return payload, rows


# ── Helpers for demo / callers ───────────────────────────────────────────────
def default_vessel(cfg: dict[str, Any]) -> VesselState:
    v = cfg["vessel_defaults"]
    return VesselState(vessel_id=v["vessel_id"], draft_m=v["draft_m"],
                       speed_knots=v["speed_knots"], heading_deg=v["heading_deg"])


def write_outputs(payload: dict[str, Any], rows: list[dict[str, Any]],
                  cfg: dict[str, Any], prefix: str = "") -> tuple[Path, Path]:
    import csv as _csv
    out = cfg["output"]
    out_dir = Path(PROJECT_ROOT) / "outputs" / "risk"
    out_dir.mkdir(parents=True, exist_ok=True)
    js = Path(PROJECT_ROOT) / out["json"]
    cs = Path(PROJECT_ROOT) / out["csv"]
    if prefix:
        js = out_dir / f"{prefix}_risk_output.json"
        cs = out_dir / f"{prefix}_risk_output.csv"
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    with open(cs, "w", newline="", encoding="utf-8") as fh:
        if rows:
            writer = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    return js, cs


if __name__ == "__main__":
    # quick self-test: engine loads and evaluates a synthetic point
    print(RiskEngine().cfg["risk"]["classes"]["HIGH"])