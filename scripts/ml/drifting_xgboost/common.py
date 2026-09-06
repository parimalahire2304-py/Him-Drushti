#!/usr/bin/env python3
"""
PHASE 3G — Shared geodesic metrics for the drifting-focused experiments.

Mirrors eval_metrics_expanded (Phase 3C) so Phase 3G numbers are directly
comparable. Earth radius and haversine definition identical.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0088
GROUNDED_ICEBERGS = {"D23"}


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.asarray, [lat1, lon1, lat2, lon2])
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def compute_group_metrics(df: pd.DataFrame, pred_lat: np.ndarray,
                          pred_lon: np.ndarray,
                          group_mask: np.ndarray | None = None) -> dict:
    mask = np.ones(len(df), dtype=bool) if group_mask is None else np.asarray(group_mask, dtype=bool)
    if int(mask.sum()) == 0:
        return {"n": 0, "pos_mae": None, "pos_rmse": None, "pos_median": None,
                "pos_p90": None, "pos_max": None, "pos_min": None, "pos_std": None,
                "lat_mae": None, "lon_mae": None, "lat_rmse": None, "lon_rmse": None,
                "mean_displacement_error": None, "final_position_error": None,
                "trajectory_error": None}
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
        "pos_p90": float(np.quantile(pos_err, 0.90)),
        "pos_max": float(np.max(pos_err)),
        "pos_min": float(np.min(pos_err)),
        "pos_std": float(np.std(pos_err)),
        "mean_displacement_error": float(np.mean(disp_err)),
        "per_sample_pos_err": pos_err.tolist(),
        "per_sample_lat_err": lat_err.tolist(),
        "per_sample_lon_err": lon_err.tolist(),
        "per_sample_disp_err": disp_err.tolist(),
    }
    traj_keys = pd.Series(np.arange(len(df)), index=df.index)[mask].index
    sub = df.loc[traj_keys].copy()
    sub = sub.assign(_pos_err=pos_err, _pred_lat=p_lat, _pred_lon=p_lon,
                     _true_lat=y_lat, _true_lon=y_lon)
    sub = sub.sort_values("obs_date")
    last_rows = sub.groupby("iceberg_id").tail(1)
    metrics["final_position_error"] = float(
        np.mean(haversine_km(last_rows["_true_lat"].values, last_rows["_true_lon"].values,
                             last_rows["_pred_lat"].values, last_rows["_pred_lon"].values))
    )
    traj_mean = sub.groupby("iceberg_id")["_pos_err"].mean()
    metrics["trajectory_error"] = float(np.mean(traj_mean))
    return metrics


def evaluate_groups(df: pd.DataFrame, pred_lat: np.ndarray, pred_lon: np.ndarray) -> dict:
    ice = df["iceberg_id"].values
    return {
        "overall":  compute_group_metrics(df, pred_lat, pred_lon, None),
        "drifting": compute_group_metrics(df, pred_lat, pred_lon,
                                          ~np.isin(ice, list(GROUNDED_ICEBERGS))),
        "grounded": compute_group_metrics(df, pred_lat, pred_lon,
                                          np.isin(ice, list(GROUNDED_ICEBERGS))),
        "C39":      compute_group_metrics(df, pred_lat, pred_lon, ice == "C39"),
    }