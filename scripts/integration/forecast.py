#!/usr/bin/env python3
"""
PHASE 3G → PHASE 4/5 INTEGRATION — FORECASTING INTERFACE
==========================================================

Provides the clean `forecast_iceberg(observation)` interface that selects
between Motion-aware XGBoost (when a valid predecessor exists) and
Persistence (mandatory fallback) with full eligibility checks, deterministic
fallback reasons, and the exact output contract required by Phase 4/5.

ABSOLUTE CONSTRAINTS (from spec):
- Motion-aware XGBoost is a CANDIDATE IMPROVED FORECAST MODEL, NOT approved
  to replace persistence globally.
- Eligibility: ALL of prev_delta_lat, prev_delta_lon, prev_speed, prev_bearing
  must be legitimately available from a REAL predecessor observation (t-7 → t).
  NO interpolation, NO fabrication, NO estimation, NO future information.
- Fallback is deterministic: IF valid predecessor AND artifact loads AND finite
  predictions → Motion-aware; ELSE → Persistence.
- Fallback reason is NEVER silent: NO_VALID_PREDECESSOR or MODEL_UNAVAILABLE.
- Model artifact: load ONLY existing Phase 3G Motion-aware artifacts; DO NOT
  retrain/alter; use exact feature order (19 env + 4 motion = 23 total).
- Output contract JSON must include all required fields.
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths / constants ───────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = PROJECT_ROOT / "data" / "processed" / "ml" / "models" / "drifting_xgboost"
DEFAULT_HORIZON_DAYS = 7  # 7-day forecast horizon (Phase 3C/3G convention)

# Canonical feature columns — must match training exactly (23 features)
ENV_FEATURES = [
    "lat", "lon",
    "iceberg_length_nm", "iceberg_width_nm",
    "sea_ice_concentration",
    "wind_u_10m", "wind_v_10m",
    "temperature_2m", "mean_sea_level_pressure",
    "total_precipitation", "bathymetry_elevation",
    "ocean_current_u", "ocean_current_v",
    "wind_speed", "wind_dir",
    "ocean_speed", "ocean_dir",
    "wind_ocean_angle", "exposed_water_fraction",
]
MOTION_FEATURES = ENV_FEATURES + [
    "prev_delta_lat", "prev_delta_lon", "prev_speed", "prev_bearing",
]

# Grounded iceberg label (Phase 3C/3G)
GROUNDED_ICEBERGS = {"D23"}

EARTH_RADIUS_KM = 6371.0088

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── Output contract ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ForecastResult:
    """Machine-readable forecast output contract (spec §7)."""
    forecast_lat: float
    forecast_lon: float
    forecast_method: str          # "MOTION_AWARE_XGBOOST" | "PERSISTENCE_FALLBACK"
    model_name: str               # "motion_aware_xgb" | "persistence"
    horizon_days: int             # 7
    predecessor_available: bool   # True iff all 4 prev_* are finite
    communication_state: str      # FRESH | STALE | LAST-KNOWN-STATE MODE (passed through)
    data_freshness: str           # FRESH | STALE | LAST-KNOWN-STATE MODE (passed through)
    fallback_reason: str | None   # None, "NO_VALID_PREDECESSOR", "MODEL_UNAVAILABLE"
    timestamp: str                # ISO UTC when forecast was generated

    def to_dict(self) -> dict[str, Any]:
        return {
            "forecast_lat": round(self.forecast_lat, 6),
            "forecast_lon": round(self.forecast_lon, 6),
            "forecast_method": self.forecast_method,
            "model_name": self.model_name,
            "horizon_days": self.horizon_days,
            "predecessor_available": self.predecessor_available,
            "communication_state": self.communication_state,
            "data_freshness": self.data_freshness,
            "fallback_reason": self.fallback_reason,
            "timestamp": self.timestamp,
        }


# ── Core logic ──────────────────────────────────────────────────────────────
class ForecastEngine:
    """Deterministic forecast engine with strict eligibility + mandatory fallback."""

    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = Path(model_dir) if model_dir else MOD_DIR
        self._lat_model: xgb.XGBRegressor | None = None
        self._lon_model: xgb.XGBRegressor | None = None
        self._metadata: dict | None = None
        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Load ONLY the existing Phase 3G Motion-aware XGBoost artifacts."""
        lat_path = self.model_dir / "motion_aware_xgb_latitude.json"
        lon_path = self.model_dir / "motion_aware_xgb_longitude.json"
        meta_path = self.model_dir / "motion_aware_xgb_metadata.json"

        if not lat_path.exists() or not lon_path.exists():
            log.warning("Motion-aware XGBoost artifacts not found at %s", self.model_dir)
            self._lat_model = None
            self._lon_model = None
            self._metadata = None
            return

        try:
            self._lat_model = xgb.XGBRegressor()
            self._lat_model.load_model(lat_path)
            self._lon_model = xgb.XGBRegressor()
            self._lon_model.load_model(lon_path)
            self._metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            # Verify feature ordering matches expected 23 features
            expected = MOTION_FEATURES
            actual = self._metadata.get("feature_columns", [])
            if actual != expected:
                log.warning("Feature column mismatch: expected %d, got %d",
                            len(expected), len(actual))
                log.warning("Expected: %s", expected)
                log.warning("Actual:   %s", actual)
            log.info("Loaded Motion-aware XGBoost (n_features=%d, n_train=%d)",
                     self._metadata.get("n_features", -1),
                     self._metadata.get("training_samples", -1))
        except Exception as e:
            log.error("Failed to load Motion-aware XGBoost: %s", e)
            self._lat_model = None
            self._lon_model = None
            self._metadata = None

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math
        rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
        rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
        dlat, dlon = rlat2 - rlat1, rlon2 - rlon1
        a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
        return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

    @staticmethod
    def _has_valid_predecessor(obs: dict[str, Any]) -> bool:
        """Check if ALL four prev_* features are finite (legitimate predecessor)."""
        required = ["prev_delta_lat", "prev_delta_lon", "prev_speed", "prev_bearing"]
        for key in required:
            val = obs.get(key)
            if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                return False
        return True

    @staticmethod
    def _persistence_forecast(obs: dict[str, Any]) -> tuple[float, float]:
        """Persistence baseline: forecast = current position."""
        return float(obs["lat"]), float(obs["lon"])

    def _motion_aware_forecast(self, obs: dict[str, Any]) -> tuple[float, float] | None:
        """Run Motion-aware XGBoost if model loaded and features available."""
        if self._lat_model is None or self._lon_model is None:
            return None
        # Build feature vector in exact training order (23 features)
        try:
            X = np.array([[obs[f] for f in MOTION_FEATURES]], dtype=float)
        except KeyError as e:
            log.warning("Missing feature for motion model: %s", e)
            return None
        if not np.all(np.isfinite(X)):
            log.warning("Non-finite feature values in motion model input")
            return None
        dlat = float(self._lat_model.predict(X)[0])
        dlon = float(self._lon_model.predict(X)[0])
        if not (np.isfinite(dlat) and np.isfinite(dlon)):
            log.warning("Non-finite motion model predictions")
            return None
        # Reconstruct position = current + predicted delta
        forecast_lat = float(obs["lat"]) + dlat
        forecast_lon = float(obs["lon"]) + dlon
        return forecast_lat, forecast_lon

    def forecast_iceberg(
        self,
        observation: dict[str, Any],
        *,
        horizon_days: int = DEFAULT_HORIZON_DAYS,
        communication_state: str = "FRESH",
        data_freshness: str = "FRESH",
    ) -> ForecastResult:
        """
        Main forecast interface (spec §3).

        Args:
            observation: dict with at least keys:
                - iceberg_id (str)
                - lat, lon (float) — current observed position
                - prev_delta_lat, prev_delta_lon, prev_speed, prev_bearing (float or NaN)
                - plus all 19 environmental features (see ENV_FEATURES)
            horizon_days: forecast horizon in days (default 7)
            communication_state: from Phase 4 state machine (FRESH/STALE/LAST-KNOWN-STATE MODE)
            data_freshness: from Phase 4 state machine (FRESH/STALE/LAST-KNOWN-STATE MODE)

        Returns:
            ForecastResult with the full output contract.
        """
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

        # Eligibility: must have all 4 prev_* finite from real predecessor
        has_pred = self._has_valid_predecessor(observation)

        # Try Motion-aware XGBoost
        motion_result = None
        if has_pred:
            motion_result = self._motion_aware_forecast(observation)

        if motion_result is not None:
            # Motion-aware selected
            return ForecastResult(
                forecast_lat=motion_result[0],
                forecast_lon=motion_result[1],
                forecast_method="MOTION_AWARE_XGBOOST",
                model_name="motion_aware_xgb",
                horizon_days=horizon_days,
                predecessor_available=True,
                communication_state=communication_state,
                data_freshness=data_freshness,
                fallback_reason=None,
                timestamp=timestamp,
            )
        else:
            # Fallback to Persistence (mandatory)
            pers_lat, pers_lon = self._persistence_forecast(observation)
            if has_pred:
                reason = "MODEL_UNAVAILABLE"
            else:
                reason = "NO_VALID_PREDECESSOR"
            return ForecastResult(
                forecast_lat=pers_lat,
                forecast_lon=pers_lon,
                forecast_method="PERSISTENCE_FALLBACK",
                model_name="persistence",
                horizon_days=horizon_days,
                predecessor_available=has_pred,
                communication_state=communication_state,
                data_freshness=data_freshness,
                fallback_reason=reason,
                timestamp=timestamp,
            )


# ── Convenience: build observation from Phase 3C/3G test row ────────────────
def build_observation_from_row(row: pd.Series) -> dict[str, Any]:
    """Convert a Phase 3C/3G test DataFrame row to the observation dict."""
    obs = row.to_dict()
    # Ensure all required keys exist (some may be missing for grounded icebergs)
    for f in MOTION_FEATURES:
        if f not in obs:
            obs[f] = np.nan
    return obs


# ── CLI for quick demo / smoke test ─────────────────────────────────────────
def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Phase 3G forecast engine demo")
    parser.add_argument("--iceberg", default="C18B", help="Iceberg ID from test set")
    parser.add_argument("--demo-a", action="store_true", help="Run Demo A (predecessor available)")
    parser.add_argument("--demo-b", action="store_true", help="Run Demo B (predecessor unavailable)")
    args = parser.parse_args()

    engine = ForecastEngine()
    test_path = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded" / "test.parquet"
    test_df = pd.read_parquet(test_path)

    if args.demo_a:
        # Demo A: pick a drifting test sample WITH predecessor
        mask_drift = ~test_df["iceberg_id"].isin(list(GROUNDED_ICEBERGS))
        mask_prev = test_df["prev_delta_lat"].notna()
        cand = test_df[mask_drift & mask_prev]
        if len(cand) == 0:
            print("No drifting test sample with predecessor found")
            return 1
        row = cand.iloc[0]
        obs = build_observation_from_row(row)
        result = engine.forecast_iceberg(obs)
        print("=" * 60)
        print("DEMO A — PREDECESSOR AVAILABLE → MOTION-AWARE XGBOOST")
        print("=" * 60)
        print(f"  Iceberg: {obs['iceberg_id']}")
        print(f"  Current position: ({obs['lat']:.5f}, {obs['lon']:.5f})")
        print(f"  Predecessor delta: ({obs['prev_delta_lat']:.5f}, {obs['prev_delta_lon']:.5f})")
        print(f"  Predecessor speed: {obs['prev_speed']:.2f} km/day")
        print(f"  Predecessor bearing: {obs['prev_bearing']:.1f}°")
        print(f"  → Forecast: ({result.forecast_lat:.5f}, {result.forecast_lon:.5f})")
        print(f"  → Method: {result.forecast_method}")
        print(f"  → Fallback reason: {result.fallback_reason}")
        print(f"  → Predecessor available: {result.predecessor_available}")
        print()
        return 0

    if args.demo_b:
        # Demo B: pick a drifting test sample WITHOUT predecessor
        mask_drift = ~test_df["iceberg_id"].isin(list(GROUNDED_ICEBERGS))
        mask_noprev = test_df["prev_delta_lat"].isna()
        cand = test_df[mask_drift & mask_noprev]
        if len(cand) == 0:
            print("No drifting test sample without predecessor found")
            return 1
        row = cand.iloc[0]
        obs = build_observation_from_row(row)
        result = engine.forecast_iceberg(obs)
        print("=" * 60)
        print("DEMO B — PREDECESSOR UNAVAILABLE → PERSISTENCE FALLBACK")
        print("=" * 60)
        print(f"  Iceberg: {obs['iceberg_id']}")
        print(f"  Current position: ({obs['lat']:.5f}, {obs['lon']:.5f})")
        print(f"  Predecessor delta: NaN (no valid predecessor)")
        print(f"  → Forecast (persistence): ({result.forecast_lat:.5f}, {result.forecast_lon:.5f})")
        print(f"  → Method: {result.forecast_method}")
        print(f"  → Fallback reason: {result.fallback_reason}")
        print(f"  → Predecessor available: {result.predecessor_available}")
        print()
        return 0

    # Default: single iceberg demo
    row = test_df[test_df["iceberg_id"] == args.iceberg].iloc[0]
    obs = build_observation_from_row(row)
    result = engine.forecast_iceberg(obs)
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())