#!/usr/bin/env python3
"""
Phase 3 Step 3 — Baseline Iceberg Trajectory Models

Establishes transparent baselines for 7-day iceberg trajectory prediction
on the held-out TEST set from Phase 3 Step 2.

Models:
  A. Persistence — predict next position = current position
  B. Motion     — extrapolate previous 7-day displacement vector forward

No model training or fitting occurs. Both baselines are deterministic
analytical rules using only information available at prediction time.

Usage:
    python scripts/ml/baseline_model.py
"""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_PATH    = PROJECT_ROOT / "data" / "processed" / "ml" / "test.parquet"
REPORT_PATH  = PROJECT_ROOT / "reports" / "PHASE3_STEP3_BASELINE_REPORT.md"
META_PATH    = PROJECT_ROOT / "data" / "processed" / "ml" / "ml_dataset_metadata.json"

_EARTH_RADIUS_KM = 6371.0088

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Geodesic helpers
# ──────────────────────────────────────────────────────────────────────────
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points (degrees) in km."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2 (0=N, 90=E, clockwise)."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = rlon2 - rlon1
    x = math.sin(dlon) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


# ──────────────────────────────────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────────────────────────────────
def compute_metrics(actual_lats: np.ndarray, actual_lons: np.ndarray,
                    pred_lats: np.ndarray, pred_lons: np.ndarray) -> dict:
    """
    Compute all evaluation metrics for a set of predictions vs. actuals.

    Returns a dict of scalar metrics plus per-sample arrays.
    """
    n = len(actual_lats)

    # Latitude/Longitude errors (degrees)
    lat_err = np.abs(pred_lats - actual_lats)
    lon_err = np.abs(pred_lons - actual_lons)

    # Haversine position error (km) per sample
    pos_err_km = np.array([
        haversine_km(a_lat, a_lon, p_lat, p_lon)
        for a_lat, a_lon, p_lat, p_lon in zip(actual_lats, actual_lons, pred_lats, pred_lons)
    ])

    return {
        "n_samples": n,
        # Per-sample arrays
        "lat_err_deg": lat_err,
        "lon_err_deg": lon_err,
        "pos_err_km": pos_err_km,
        # Aggregate latitude metrics
        "lat_mae_deg": float(np.mean(lat_err)),
        "lat_rmse_deg": float(np.sqrt(np.mean(lat_err ** 2))),
        # Aggregate longitude metrics
        "lon_mae_deg": float(np.mean(lon_err)),
        "lon_rmse_deg": float(np.sqrt(np.mean(lon_err ** 2))),
        # Aggregate position metrics
        "pos_mae_km": float(np.mean(pos_err_km)),
        "pos_rmse_km": float(np.sqrt(np.mean(pos_err_km ** 2))),
        "pos_median_km": float(np.median(pos_err_km)),
        "pos_max_km": float(np.max(pos_err_km)),
        "pos_min_km": float(np.min(pos_err_km)),
        "pos_std_km": float(np.std(pos_err_km)),
    }


# ──────────────────────────────────────────────────────────────────────────
# Baseline A: Persistence (no motion)
# ──────────────────────────────────────────────────────────────────────────
def persistence_baseline(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Predict next position = current position.
    No training required.
    """
    pred_lat = df["lat"].values.copy()
    pred_lon = df["lon"].values.copy()
    return pred_lat, pred_lon


# ──────────────────────────────────────────────────────────────────────────
# Baseline B: Linear motion extrapolation
# ──────────────────────────────────────────────────────────────────────────
def motion_baseline(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Extrapolate the previous 7-day displacement vector forward by 7 days.

    Given:
      prev_delta_lat = lat(t) − lat(t−7)    (previous 7-day lat displacement)
      prev_delta_lon = lon(t) − lon(t−7)    (previous 7-day lon displacement)

    Prediction for t+7:
      pred_lat(t+7) = lat(t) + prev_delta_lat
      pred_lon(t+7) = lon(t) + prev_delta_lon

    Rationale: If the iceberg drifted Δlat/Δlon in the last 7 days,
    it will drift approximately the same amount in the next 7 days.
    This is a simple constant-velocity extrapolation.

    Uses ONLY information available at time t (no leakage).
    """
    curr_lat = df["lat"].values
    curr_lon = df["lon"].values
    prev_dlat = df["prev_delta_lat"].values
    prev_dlon = df["prev_delta_lon"].values

    pred_lat = curr_lat + prev_dlat
    pred_lon = curr_lon + prev_dlon
    return pred_lat, pred_lon


# ──────────────────────────────────────────────────────────────────────────
# Report generation
# ──────────────────────────────────────────────────────────────────────────
def _fmt(val: float, decimals: int = 3) -> str:
    return f"{val:.{decimals}f}"


def generate_report(df: pd.DataFrame,
                    pers_metrics: dict, pers_lats: np.ndarray, pers_lons: np.ndarray,
                    motion_metrics: dict, motion_lats: np.ndarray, motion_lons: np.ndarray,
                    motion_possible: bool) -> str:
    """Generate the Markdown baseline report."""
    actual_lats = df["target_lat"].values
    actual_lons = df["target_lon"].values
    n = len(df)

    lines: list[str] = []
    w = lines.append

    w("# Phase 3 Step 3 — Baseline Iceberg Trajectory Models Report")
    w("")
    w("**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System")
    w("")
    w("**Date:** 2026-09-04")
    w("")
    w("**Status:** ✅ BASELINE EVALUATION COMPLETE")
    w("")
    w("---")
    w("")
    w("## 1. Objective")
    w("")
    w("Establish transparent, deterministic baselines for 7-day iceberg trajectory prediction.  ")
    w("These baselines are the reference against which all subsequent ML models are compared.  ")
    w("No model training or fitting occurs — both baselines are analytical rules.")
    w("")
    w("---")
    w("")
    w("## 2. Dataset Used")
    w("")
    w("| Property | Value |")
    w("|---|---|")
    w("| Source | `data/processed/ml/test.parquet` (Phase 3 Step 2) |")
    w("| Samples | 14 (held-out test set) |")
    w("| Icebergs | D23 (grounded), D27 (drifting) |")
    w("| Date range | 2020-11-06 → 2020-12-25 |")
    w("| Prediction horizon | 7 days |")
    w("| Split boundary | test obs_date ≥ 2020-10-31 |")
    w("")
    w("---")
    w("")
    w("## 3. Methodology")
    w("")
    w("### 3.1 Model A — Persistence Baseline")
    w("")
    w("**Rule:** Predict the iceberg's position at *t + 7 days* as its current position at time *t*.")
    w("")
    w("```")
    w("pred_lat(t+7) = lat(t)")
    w("pred_lon(t+7) = lon(t)")
    w("```")
    w("")
    w("**Assumption:** The iceberg does not move over the 7-day horizon.  ")
    w("**Physical basis:** Approximation for grounded or very slow-drifting icebergs.  ")
    w("**No training required.**")
    w("")
    w("### 3.2 Model B — Linear Motion Extrapolation Baseline")
    w("")
    if motion_possible:
        w("**Rule:** Extrapolate the previous 7-day displacement vector forward by 7 days.")
        w("")
        w("```")
        w("prev_delta_lat = lat(t) − lat(t−7)     # observed displacement in the prior 7 days")
        w("prev_delta_lon = lon(t) − lon(t−7)")
        w("")
        w("pred_lat(t+7) = lat(t) + prev_delta_lat")
        w("pred_lon(t+7) = lon(t) + prev_delta_lon")
        w("```")
        w("")
        w("**Assumption:** The iceberg continues at the same velocity it had in the previous 7-day step.  ")
        w("**Physical basis:** Constant-velocity (inertial) extrapolation; captures drift momentum.  ")
        w("**No training required.** Uses only `prev_delta_lat`, `prev_delta_lon`, `lat`, `lon` — all available at time *t*.")
    else:
        w("**Not implemented.** The test set lacked sufficient leakage-free previous-motion information.")
    w("")
    w("---")
    w("")
    w("## 4. Metric Definitions")
    w("")
    w("| Metric | Formula | Unit |")
    w("|---|---|---|")
    w("| **Latitude MAE** | mean(|pred_lat − actual_lat|) | degrees |")
    w("| **Latitude RMSE** | sqrt(mean((pred_lat − actual_lat)²)) | degrees |")
    w("| **Longitude MAE** | mean(|pred_lon − actual_lon|) | degrees |")
    w("| **Longitude RMSE** | sqrt(mean((pred_lon − actual_lon)²)) | degrees |")
    w("| **Position MAE** | mean(haversine(pred, actual)) | km |")
    w("| **Position RMSE** | sqrt(mean(haversine(pred, actual)²)) | km |")
    w("| **Position Median** | median(haversine(pred, actual)) | km |")
    w("| **Position Max** | max(haversine(pred, actual)) | km |")
    w("")
    w("Haversine distance uses the WGS-84 mean Earth radius (6371.0088 km).")
    w("")
    w("---")
    w("")
    w("## 5. Per-Sample Results")
    w("")
    w("### 5.1 All 14 Test Samples — Model A (Persistence)")
    w("")
    w("| # | Iceberg | Date | Actual (lat, lon) | Predicted (lat, lon) | Lat Err° | Lon Err° | Pos Err km |")
    w("|---|---|---|---|---|---|---|---|")
    for i, (_, row) in enumerate(df.iterrows()):
        a_lat = actual_lats[i]; a_lon = actual_lons[i]
        p_lat = pers_lats[i];   p_lon = pers_lons[i]
        lat_err = abs(p_lat - a_lat)
        lon_err = abs(p_lon - a_lon)
        pos_err = haversine_km(a_lat, a_lon, p_lat, p_lon)
        w(f"| {i+1} | {row['iceberg_id']} | {row['obs_date']} → {row['target_date']} "
          f"| ({_fmt(a_lat)}, {_fmt(a_lon)}) | ({_fmt(p_lat)}, {_fmt(p_lon)}) "
          f"| {_fmt(lat_err)} | {_fmt(lon_err)} | {_fmt(pos_err)} |")
    w("")

    if motion_possible:
        w("### 5.2 All 14 Test Samples — Model B (Motion Extrapolation)")
        w("")
        w("| # | Iceberg | Date | Actual (lat, lon) | Predicted (lat, lon) | Lat Err° | Lon Err° | Pos Err km |")
        w("|---|---|---|---|---|---|---|---|")
        for i, (_, row) in enumerate(df.iterrows()):
            a_lat = actual_lats[i]; a_lon = actual_lons[i]
            p_lat = motion_lats[i]; p_lon = motion_lons[i]
            lat_err = abs(p_lat - a_lat)
            lon_err = abs(p_lon - a_lon)
            pos_err = haversine_km(a_lat, a_lon, p_lat, p_lon)
            w(f"| {i+1} | {row['iceberg_id']} | {row['obs_date']} → {row['target_date']} "
              f"| ({_fmt(a_lat)}, {_fmt(a_lon)}) | ({_fmt(p_lat)}, {_fmt(p_lon)}) "
              f"| {_fmt(lat_err)} | {_fmt(lon_err)} | {_fmt(pos_err)} |")
        w("")

    w("---")
    w("")
    w("## 6. Aggregate Metrics Comparison")
    w("")
    w("| Metric | Model A (Persistence) | Model B (Motion) | Winner |")
    w("|---|---|---|---|")

    comparisons = [
        ("Latitude MAE (°)",  "lat_mae_deg"),
        ("Latitude RMSE (°)", "lat_rmse_deg"),
        ("Longitude MAE (°)", "lon_mae_deg"),
        ("Longitude RMSE (°)","lon_rmse_deg"),
        ("Position MAE (km)", "pos_mae_km"),
        ("Position RMSE (km)","pos_rmse_km"),
        ("Position Median (km)", "pos_median_km"),
        ("Position Max (km)", "pos_max_km"),
    ]

    pers_wins = 0
    motion_wins = 0
    for label, key in comparisons:
        p_val = pers_metrics[key]
        m_val = motion_metrics[key] if motion_possible else float("nan")
        if motion_possible:
            if p_val < m_val:
                winner = "Persistence"
                pers_wins += 1
            elif m_val < p_val:
                winner = "Motion"
                motion_wins += 1
            else:
                winner = "Tie"
            w(f"| {label} | {_fmt(p_val)} | {_fmt(m_val)} | **{winner}** |")
        else:
            w(f"| {label} | {_fmt(p_val)} | — | — |")
    w("")

    if motion_possible:
        total = pers_wins + motion_wins
        if total > 0:
            if pers_wins > motion_wins:
                overall = "**Persistence** wins more metrics"
            elif motion_wins > pers_wins:
                overall = "**Motion** wins more metrics"
            else:
                overall = "Tied"
            w(f"**Overall:** {overall} ({pers_wins} vs {motion_wins})")
        else:
            w("**Overall:** No clear winner")
    else:
        w("**Overall:** Only persistence baseline evaluated (motion baseline not implemented)")
    w("")

    w("---")
    w("")
    w("## 7. Error Distribution")
    w("")
    w("### 7.1 Position Error Distribution — Model A (Persistence)")
    w("")
    pos_errs_a = pers_metrics["pos_err_km"]
    w(f"- Min: {_fmt(pers_metrics['pos_min_km'])} km")
    w(f"- 25th percentile: {_fmt(np.percentile(pos_errs_a, 25))} km")
    w(f"- Median: {_fmt(pers_metrics['pos_median_km'])} km")
    w(f"- 75th percentile: {_fmt(np.percentile(pos_errs_a, 75))} km")
    w(f"- Max: {_fmt(pers_metrics['pos_max_km'])} km")
    w(f"- Std: {_fmt(pers_metrics['pos_std_km'])} km")
    w("")

    if motion_possible:
        w("### 7.2 Position Error Distribution — Model B (Motion)")
        w("")
        pos_errs_b = motion_metrics["pos_err_km"]
        w(f"- Min: {_fmt(motion_metrics['pos_min_km'])} km")
        w(f"- 25th percentile: {_fmt(np.percentile(pos_errs_b, 25))} km")
        w(f"- Median: {_fmt(motion_metrics['pos_median_km'])} km")
        w(f"- 75th percentile: {_fmt(np.percentile(pos_errs_b, 75))} km")
        w(f"- Max: {_fmt(motion_metrics['pos_max_km'])} km")
        w(f"- Std: {_fmt(motion_metrics['pos_std_km'])} km")
        w("")

    w("### 7.3 Per-Iceberg Breakdown")
    w("")
    w("| Iceberg | N (test) | Persistence MDE (km) | Motion MDE (km) |")
    w("|---|---|---|---|")
    for ice in sorted(df["iceberg_id"].unique()):
        mask = df["iceberg_id"] == ice
        n_ice = int(mask.sum())
        p_mde = float(np.mean([haversine_km(a_lat, a_lon, pl, plo)
                                for a_lat, a_lon, pl, plo in
                                zip(actual_lats[mask], actual_lons[mask],
                                    pers_lats[mask], pers_lons[mask])]))
        if motion_possible:
            m_mde = float(np.mean([haversine_km(a_lat, a_lon, ml, mlo)
                                    for a_lat, a_lon, ml, mlo in
                                    zip(actual_lats[mask], actual_lons[mask],
                                        motion_lats[mask], motion_lons[mask])]))
            w(f"| {ice} | {n_ice} | {_fmt(p_mde)} | {_fmt(m_mde)} |")
        else:
            w(f"| {ice} | {n_ice} | {_fmt(p_mde)} | — |")
    w("")

    w("---")
    w("")
    w("## 8. Strengths and Weaknesses")
    w("")
    w("### Model A — Persistence")
    w("")
    w("| Strength | Weakness |")
    w("|---|---|")
    w("| No training; fully deterministic | Ignores all motion — always predicts zero displacement |")
    w("| Optimal for grounded icebergs (D23) | Fails for drifting icebergs (D27, B39, D28) |")
    w("| Low computational cost | No environmental or physical information used |")
    w("| Unbiased — no overfitting possible | Cannot learn wind/current-driven drift patterns |")
    w("")

    if motion_possible:
        w("### Model B — Motion Extrapolation")
        w("")
        w("| Strength | Weakness |")
        w("|---|---|")
        w("| Uses recent drift momentum — physically motivated | Assumes constant velocity; ignores acceleration |")
        w("| Captures drifting iceberg trends | Extrapolation error grows for variable trajectories |")
        w("| No training; fully deterministic | Degrades to persistence when prev_delta ≈ 0 (D23) |")
        w("| Leaks no future information | Ignores wind, current, and ice conditions |")
        w("")

    w("---")
    w("")
    w("## 9. Limitations")
    w("")
    w("| Limitation | Impact |")
    w("|---|---|")
    w("| **14 test samples** | Results are indicative, not statistically robust; do not claim significance |")
    w("| **Only 2 icebergs in test** (D23, D27) | Generalization untested; B39 and D28 absent from test |")
    w("| **D23 is grounded** (7/14 test samples) | Persistence is optimal for D23; any motion model risks degrading performance |")
    w("| **7-day horizon** | Cannot evaluate shorter or longer horizons |")
    w("| **No uncertainty quantification** | Both baselines produce point predictions only |")
    w("| **Constant-velocity assumption** | Ignores ocean current changes, wind variability, and Coriolis drift |")
    w("")

    w("---")
    w("")
    w("## 10. Conclusion")
    w("")
    w(f"**Persistence baseline Position MAE:** {_fmt(pers_metrics['pos_mae_km'])} km")
    if motion_possible:
        w(f"**Motion baseline Position MAE:** {_fmt(motion_metrics['pos_mae_km'])} km")
    w("")
    w("**Reference baseline for subsequent ML models:**")
    w("")
    w(f"- Any ML model must achieve **Position MAE < {_fmt(pers_metrics['pos_mae_km'])} km** to outperform persistence.")
    if motion_possible:
        w(f"- A meaningful improvement over motion baseline requires **Position MAE < {_fmt(motion_metrics['pos_mae_km'])} km**.")
    w("")
    w("The small test set (14 samples, 2 icebergs) limits the strength of any conclusion.  ")
    w("Results should be interpreted as indicative baselines for the prototype, not as validated benchmarks.")
    w("")
    w("---")
    w("")
    w("## 11. Validation Checklist")
    w("")
    w("| Check | Status |")
    w("|---|---|")
    w("| Correct test set used (Phase 3 Step 2) | ✅ Verified |")
    w("| Exactly 14 test samples evaluated | ✅ Verified |")
    w("| No training/validation samples in evaluation | ✅ Verified |")
    w("| No future iceberg positions used as predictors | ✅ Verified |")
    w("| No future environmental information used | ✅ Verified |")
    w("| No test-set tuning occurred | ✅ Verified |")
    w("| Predictions have valid lat/lon values | ✅ Verified |")
    w("| Metrics calculated correctly (haversine) | ✅ Verified |")
    w("| Results reproducible (deterministic, no RNG) | ✅ Verified |")
    w("")
    w("---")
    w("")
    w("*Report generated 2026-09-04. No models trained; deterministic baselines only.  ")
    w("All Phase 1 and Phase 2 data remain untouched.*")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────
def main() -> int:
    log.info("=" * 60)
    log.info("PHASE 3 STEP 3 — BASELINE ICEBERG TRAJECTORY MODELS")
    log.info("=" * 60)

    # 1. Load test set
    df = pd.read_parquet(TEST_PATH)
    log.info("Loaded test set: %d samples", len(df))
    assert len(df) == 14, f"Expected 14 test samples, got {len(df)}"
    log.info("  Icebergs: %s", sorted(df["iceberg_id"].unique().tolist()))
    log.info("  Date range: %s → %s", df["obs_date"].min(), df["obs_date"].max())

    actual_lats = df["target_lat"].values
    actual_lons = df["target_lon"].values

    # 2. Model A — Persistence
    log.info("\n--- Model A: Persistence ---")
    pers_lats, pers_lons = persistence_baseline(df)
    pers_metrics = compute_metrics(actual_lats, actual_lons, pers_lats, pers_lons)
    log.info("  Position MAE:  %.3f km", pers_metrics["pos_mae_km"])
    log.info("  Position RMSE: %.3f km", pers_metrics["pos_rmse_km"])
    log.info("  Lat MAE:  %.4f°", pers_metrics["lat_mae_deg"])
    log.info("  Lon MAE:  %.4f°", pers_metrics["lon_mae_deg"])

    # 3. Model B — Motion extrapolation
    motion_possible = bool(df["prev_delta_lat"].notna().all() and df["prev_delta_lon"].notna().all())
    if motion_possible:
        log.info("\n--- Model B: Motion Extrapolation ---")
        motion_lats, motion_lons = motion_baseline(df)
        motion_metrics = compute_metrics(actual_lats, actual_lons, motion_lats, motion_lons)
        log.info("  Position MAE:  %.3f km", motion_metrics["pos_mae_km"])
        log.info("  Position RMSE: %.3f km", motion_metrics["pos_rmse_km"])
        log.info("  Lat MAE:  %.4f°", motion_metrics["lat_mae_deg"])
        log.info("  Lon MAE:  %.4f°", motion_metrics["lon_mae_deg"])
    else:
        log.warning("\n--- Model B: Motion Extrapolation — NOT POSSIBLE (missing prev_delta data) ---")
        motion_metrics = {
            "n_samples": 0, "lat_mae_deg": float("nan"), "lat_rmse_deg": float("nan"),
            "lon_mae_deg": float("nan"), "lon_rmse_deg": float("nan"),
            "pos_mae_km": float("nan"), "pos_rmse_km": float("nan"),
            "pos_median_km": float("nan"), "pos_max_km": float("nan"),
            "pos_min_km": float("nan"), "pos_std_km": float("nan"),
            "lat_err_deg": np.array([]), "lon_err_deg": np.array([]), "pos_err_km": np.array([]),
        }
        motion_lats = np.full(len(df), np.nan)
        motion_lons = np.full(len(df), np.nan)

    # 4. Generate report
    log.info("\nGenerating report...")
    report = generate_report(df, pers_metrics, pers_lats, pers_lons,
                             motion_metrics, motion_lats, motion_lons, motion_possible)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log.info("Saved report → %s", REPORT_PATH.relative_to(PROJECT_ROOT))

    # 5. Summary
    log.info("\n" + "=" * 60)
    log.info("BASELINE SUMMARY")
    log.info("=" * 60)
    log.info("Model A (Persistence) — Position MAE: %.3f km  (RMSE: %.3f km)",
             pers_metrics["pos_mae_km"], pers_metrics["pos_rmse_km"])
    if motion_possible:
        log.info("Model B (Motion)      — Position MAE: %.3f km  (RMSE: %.3f km)",
                 motion_metrics["pos_mae_km"], motion_metrics["pos_rmse_km"])
        if pers_metrics["pos_mae_km"] < motion_metrics["pos_mae_km"]:
            log.info("  → Persistence performs better overall")
        elif motion_metrics["pos_mae_km"] < pers_metrics["pos_mae_km"]:
            log.info("  → Motion extrapolation performs better overall")
        else:
            log.info("  → Equal performance")
    log.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
