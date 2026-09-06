#!/usr/bin/env python3
"""
PHASE 3C — Shared evaluation metrics for the expanded-dataset models.

Single source of truth for the metric definitions used by every model
(Random Forest, XGBoost, LSTM) AND the persistence baseline, so that all
reported numbers are computed identically and exactly reproducible.

All metrics are computed on the SAME expanded test set (54 samples) passed
in as `df`, with model predictions (`pred_lat`, `pred_lon`).

Metrics produced (per group):
  - Latitude MAE / RMSE (°)
  - Longitude MAE / RMSE (°)
  - Position MAE / RMSE (km)          <- position/displacement MAE & RMSE
  - Median position error (km)
  - Maximum position error (km)
  - Minimum / Std position error (km)
  - Final-position error (km)          <- mean over trajectories of the
                                           position error at the last step
  - Trajectory error (km)              <- mean over trajectories of the
                                           within-trajectory mean position err
  - Mean displacement error (km)       <- mean |pred_disp - true_disp|

Groups evaluated:
  - overall (all 54)
  - drifting-only (non-D23, non-C39-in-train semantics: C18B + C39 = 24)
  - grounded-only (D23 = 30)
  - C39 zero-shot (9, test-only iceberg)

Fit/scaling must never touch the test set; this module only evaluates.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0088

# Grounded iceberg identifier (from Phase 3A/3B analysis: D23 mean 7d disp ~0.08 km)
GROUNDED_ICEBERGS = {"D23"}


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Vectorised great-circle distance (km). Handles scalars or arrays."""
    lat1, lon1, lat2, lon2 = map(np.asarray, [lat1, lon1, lat2, lon2])
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def compute_group_metrics(df: pd.DataFrame,
                          pred_lat: np.ndarray,
                          pred_lon: np.ndarray,
                          group_mask: np.ndarray | None = None) -> dict:
    """
    Compute the full metric set for a (possibly subset) of the test set.

    `df` is the full test DataFrame; `group_mask` selects the subset
    (boolean array aligned to df rows). When None, uses all rows.
    """
    mask = np.ones(len(df), dtype=bool) if group_mask is None else np.asarray(group_mask, dtype=bool)
    if mask.sum() == 0:
        return {"n": 0}

    y_lat = df["target_lat"].values[mask]
    y_lon = df["target_lon"].values[mask]
    p_lat = np.asarray(pred_lat)[mask]
    p_lon = np.asarray(pred_lon)[mask]
    obs_lat = df["lat"].values[mask]
    obs_lon = df["lon"].values[mask]

    lat_err = np.abs(p_lat - y_lat)
    lon_err = np.abs(p_lon - y_lon)
    pos_err = haversine_km(y_lat, y_lon, p_lat, p_lon)
    pred_disp = haversine_km(obs_lat, obs_lon, p_lat, p_lon)
    true_disp = df["displacement_km"].values[mask]
    disp_err = np.abs(pred_disp - true_disp)

    metrics = {
        "n": int(mask.sum()),
        "lat_mae": float(np.mean(lat_err)),
        "lon_mae": float(np.mean(lon_err)),
        "lat_rmse": float(np.sqrt(np.mean(lat_err ** 2))),
        "lon_rmse": float(np.sqrt(np.mean(lon_err ** 2))),
        "pos_mae": float(np.mean(pos_err)),
        "pos_rmse": float(np.sqrt(np.mean(pos_err ** 2))),
        "pos_median": float(np.median(pos_err)),
        "pos_max": float(np.max(pos_err)),
        "pos_min": float(np.min(pos_err)),
        "pos_std": float(np.std(pos_err)),
        "mean_displacement_error": float(np.mean(disp_err)),
    }

    # --- Trajectory-level metrics ---
    # Group rows by (iceberg_id, obs_date-chain). A trajectory here is the
    # contiguous sequence of 7-day steps per iceberg within the test window.
    traj_keys = pd.Series(np.arange(len(df)), index=df.index)[mask].index
    sub = df.loc[traj_keys].copy()
    sub = sub.assign(_pos_err=pos_err, _pred_lat=p_lat, _pred_lon=p_lon,
                     _true_lat=y_lat, _true_lon=y_lon)
    sub = sub.sort_values("obs_date")

    # Final-position error: mean over trajectories of the error at each
    # trajectory's last (most recent) observation.
    last_rows = sub.groupby("iceberg_id").tail(1)
    metrics["final_position_error"] = float(
        np.mean(haversine_km(last_rows["_true_lat"].values, last_rows["_true_lon"].values,
                             last_rows["_pred_lat"].values, last_rows["_pred_lon"].values))
    )

    # Trajectory error: mean over trajectories of the within-trajectory mean err.
    traj_mean = sub.groupby("iceberg_id")["_pos_err"].mean()
    metrics["trajectory_error"] = float(np.mean(traj_mean))

    # --- Per-sample arrays (for debugging / recomputation checks) ---
    metrics["per_sample_pos_err"] = pos_err.tolist()
    metrics["per_sample_lat_err"] = lat_err.tolist()
    metrics["per_sample_lon_err"] = lon_err.tolist()
    metrics["per_sample_disp_err"] = disp_err.tolist()

    return metrics


def evaluate_groups(df: pd.DataFrame, pred_lat: np.ndarray, pred_lon: np.ndarray) -> dict:
    """
    Evaluate the same predictions across all required subgroups.
    Returns {"overall": {...}, "drifting": {...}, "grounded": {...}, "C39": {...}}.
    """
    ice = df["iceberg_id"].values
    drifting_mask = ~np.isin(ice, list(GROUNDED_ICEBERGS))
    grounded_mask = np.isin(ice, list(GROUNDED_ICEBERGS))
    c39_mask = ice == "C39"

    return {
        "overall": compute_group_metrics(df, pred_lat, pred_lon, None),
        "drifting": compute_group_metrics(df, pred_lat, pred_lon, drifting_mask),
        "grounded": compute_group_metrics(df, pred_lat, pred_lon, grounded_mask),
        "C39": compute_group_metrics(df, pred_lat, pred_lon, c39_mask),
    }


if __name__ == "__main__":
    # Quick self-check against the persistence baseline on the test set.
    from pathlib import Path
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    PROJ = Path(__file__).resolve().parents[2]
    te = pd.read_parquet(PROJ / "data/processed/ml/expanded/test.parquet")
    res = evaluate_groups(te, te["persist_lat"].values, te["persist_lon"].values)
    for group, m in res.items():
        print(f"{group:10s} n={m['n']:3d}  pos_mae={m['pos_mae']:.3f}  "
              f"final={m['final_position_error']:.3f}  traj={m['trajectory_error']:.3f}  "
              f"disp={m['mean_displacement_error']:.3f}")
