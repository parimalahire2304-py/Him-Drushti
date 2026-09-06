#!/usr/bin/env python3
"""
PHASE 3G — EXPERIMENT A: Displacement XGBoost (environmental features only)

Trains XGBoost to predict delta_lat and delta_lon (t→t+7 displacement in
degrees) from the APPROVED environmental-feature stack EXCLUDING the
prev_* motion columns (the 19-feature environmental/geometric core).

Trained ONLY on the drifting (non-D23) training population.

Target representation:
  predicted_lat = current_lat + predicted_delta_lat
  predicted_lon = current_lon + predicted_delta_lon

Output (data/processed/ml/models/drifting_xgboost/):
  displacement_xgb_latitude.json
  displacement_xgb_longitude.json
  displacement_xgb_metadata.json
  displacement_xgb_predictions.csv

Output (outputs/ml/drifting_xgboost/):
  displacement_xgb_evaluation.json

Deterministic seed: 42
Does NOT modify existing Phase 3C models or datasets.
"""
from __future__ import annotations

import itertools
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXP = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded"
MOD_DIR = PROJECT_ROOT / "data" / "processed" / "ml" / "models" / "drifting_xgboost"
OUT_DIR = PROJECT_ROOT / "outputs" / "ml" / "drifting_xgboost"
GROUNDED_ICEBERGS = {"D23"}

# ── Feature design: approved env stack MINUS prev_* motion ────────────────
FEATURE_COLS = [
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
TARGET_LAT = "delta_lat"
TARGET_LON = "delta_lon"
RANDOM_STATE = 42

# ── Small controlled hyperparameter grid (spec §8) ──────────────────────
PARAM_GRID = {
    "n_estimators":     [100, 200, 300],
    "max_depth":        [2, 3, 4],
    "learning_rate":    [0.05, 0.1],
    "min_child_weight": [5, 10],
    "subsample":        [0.8],
    "colsample_bytree": [0.8],
    "reg_alpha":        [0.1, 1.0],
    "reg_lambda":       [1.0, 5.0],
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    import math as _m
    lat1, lon1, lat2, lon2 = map(np.asarray, [lat1, lon1, lat2, lon2])
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1; dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _pos_error_km(obs_lat, obs_lon, pred_lat, pred_lon):
    return _haversine_km(obs_lat, obs_lon, pred_lat, pred_lon)


def _build_combos():
    keys = list(PARAM_GRID.keys())
    return [dict(zip(keys, v)) for v in itertools.product(*PARAM_GRID.values())]


def _tune(X_tr, y_tr, X_val, y_val, target_name, n_combos):
    combos = _build_combos()
    log.info("    [%s] Tuning %d combos ...", target_name, len(combos))
    t0 = time.perf_counter()
    best_mae = float("inf")
    best_params = combos[0]
    for params in combos:
        m = xgb.XGBRegressor(**params, random_state=RANDOM_STATE, verbosity=0,
                              objective="reg:squarederror", n_jobs=-1)
        m.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
        ma = mean_absolute_error(y_val, m.predict(X_val))
        if ma < best_mae:
            best_mae = ma
            best_params = params
    t = time.perf_counter() - t0
    log.info("    [%s] Best val_mae=%.6f params=%s  (%.1fs)", target_name, best_mae, best_params, t)
    return best_params


def _evaluate(name, df, pred_lat, pred_lon) -> dict:
    ice = df["iceberg_id"].values
    drifting = ~np.isin(ice, list(GROUNDED_ICEBERGS))
    c39 = ice == "C39"
    pos_err_all = _pos_error_km(df["target_lat"].values, df["target_lon"].values,
                                pred_lat, pred_lon)
    pos_err_drift = _pos_error_km(df["target_lat"].values[drifting], df["target_lon"].values[drifting],
                                  pred_lat[drifting], pred_lon[drifting])
    lat_err_all = np.abs(pred_lat - df["target_lat"].values)
    lon_err_all = np.abs(pred_lon - df["target_lon"].values)
    lat_err_drift = np.abs(pred_lat[drifting] - df["target_lat"].values[drifting])
    lon_err_drift = np.abs(pred_lon[drifting] - df["target_lon"].values[drifting])
    pos_err_c39 = _pos_error_km(df["target_lat"].values[c39], df["target_lon"].values[c39],
                                pred_lat[c39], pred_lon[c39])

    def _m(pos_e, lat_e, lon_e, n):
        disp = _pos_error_km(df["lat"].values[:n], df["lon"].values[:n],
                              pred_lat[:n], pred_lon[:n])
        true_disp = df["displacement_km"].values[:n]
        return {
            "n": int(n),
            "pos_mae":    float(np.mean(pos_e)),
            "pos_rmse":   float(np.sqrt(np.mean(pos_e**2))),
            "pos_median": float(np.median(pos_e)),
            "pos_p90":    float(np.quantile(pos_e, 0.90)),
            "pos_max":    float(np.max(pos_e)),
            "lat_mae":    float(np.mean(lat_e)),
            "lon_mae":    float(np.mean(lon_e)),
            "lat_rmse":   float(np.sqrt(np.mean(lat_e**2))),
            "lon_rmse":   float(np.sqrt(np.mean(lon_e**2))),
            "mean_disp_error": float(np.mean(np.abs(disp - true_disp))),
        }

    return {
        "overall":   _m(pos_err_all,  lat_err_all,  lon_err_all,  len(df)),
        "drifting":  _m(pos_err_drift, lat_err_drift, lon_err_drift, int(drifting.sum())),
        "grounded":  {"n": int((~drifting).sum())},
        "C39":       _m(pos_err_c39, np.abs(pred_lat[c39] - df["target_lat"].values[c39]),
                        np.abs(pred_lon[c39] - df["target_lon"].values[c39]), int(c39.sum())),
    }


def main() -> int:
    print("=" * 70)
    print("PHASE 3G — EXPERIMENT A: Displacement XGBoost (env-only features)")
    print("=" * 70)

    train_df = pd.read_parquet(EXP / "train.parquet")
    val_df   = pd.read_parquet(EXP / "val.parquet")
    test_df  = pd.read_parquet(EXP / "test.parquet")

    # Drifting filter (non-D23)
    is_drift_train = ~train_df["iceberg_id"].isin(list(GROUNDED_ICEBERGS))
    is_drift_val   = ~val_df["iceberg_id"].isin(list(GROUNDED_ICEBERGS))
    is_drift_test  = ~test_df["iceberg_id"].isin(list(GROUNDED_ICEBERGS))
    tr = train_df[is_drift_train].reset_index(drop=True)
    va = val_df[is_drift_val].reset_index(drop=True)
    te = test_df[is_drift_test].reset_index(drop=True)

    n_tr, n_va, n_te = len(tr), len(va), len(te)
    print(f"  Drifting population: train={n_tr}  val={n_va}  test={n_te}")
    print(f"  Test icebergs: {sorted(te.iceberg_id.unique())}")
    print(f"  C39 in test: {int((te.iceberg_id=='C39').sum())}")
    print(f"  Using {len(FEATURE_COLS)} env-only features (no prev_*)")

    X_tr = tr[FEATURE_COLS].values;  y_tr_lat = tr[TARGET_LAT].values;  y_tr_lon = tr[TARGET_LON].values
    X_va = va[FEATURE_COLS].values;  y_va_lat = va[TARGET_LAT].values;  y_va_lon = va[TARGET_LON].values
    X_te = te[FEATURE_COLS].values

    for split, X in [("train", X_tr), ("val", X_va), ("test", X_te)]:
        print(f"    NaN in {split}: {int(np.isnan(X).sum())}")

    # Tune lat then lon
    params_lat = _tune(X_tr, y_tr_lat, X_va, y_va_lat, "delta_lat", len(PARAM_GRID))
    params_lon = _tune(X_tr, y_tr_lon, X_va, y_va_lon, "delta_lon", len(PARAM_GRID))

    # Retrain on train+val (spec §11 parity with Phase 3C)
    X_tv = np.vstack([X_tr, X_va])
    y_tv_lat = np.concatenate([y_tr_lat, y_va_lat])
    y_tv_lon = np.concatenate([y_tr_lon, y_va_lon])
    print(f"  Retraining on train+val ({len(X_tv)} samples) ...")
    t0 = time.perf_counter()
    lat_m = xgb.XGBRegressor(**params_lat, random_state=RANDOM_STATE, verbosity=0,
                               objective="reg:squarederror", n_jobs=-1)
    lon_m = xgb.XGBRegressor(**params_lon, random_state=RANDOM_STATE, verbosity=0,
                               objective="reg:squarederror", n_jobs=-1)
    lat_m.fit(X_tv, y_tv_lat, verbose=False)
    lon_m.fit(X_tv, y_tv_lon, verbose=False)
    train_s = time.perf_counter() - t0

    # Predict displacement then reconstruct position
    pred_dlat = lat_m.predict(X_te)
    pred_dlon = lon_m.predict(X_te)
    pred_lat  = te["lat"].values + pred_dlat
    pred_lon  = te["lon"].values + pred_dlon

    print(f"\n  Training time: {train_s:.2f}s")
    metrics = _evaluate("DisplacementXGB", te, pred_lat, pred_lon)
    print(f"\n  EVALUATION (drifting test n={metrics['drifting']['n']}):")
    for group in ["overall", "drifting", "C39"]:
        m = metrics[group]
        print(f"    [{group:9s}] n={m['n']:3d}  pos_mae={m['pos_mae']:.4f}  "
              f"pos_rmse={m['pos_rmse']:.4f}  median={m['pos_median']:.4f}  "
              f"p90={m['pos_p90']:.4f}  max={m['pos_max']:.4f}")

    # Save model files
    MOD_DIR.mkdir(parents=True, exist_ok=True)
    lat_m.save_model(MOD_DIR / "displacement_xgb_latitude.json")
    lon_m.save_model(MOD_DIR / "displacement_xgb_longitude.json")

    meta = {
        "experiment": "A",
        "model_name": "displacement_xgb",
        "description": "Displacement XGBoost (env-only features, drifting-only training)",
        "feature_columns": FEATURE_COLS,
        "n_features": len(FEATURE_COLS),
        "target_columns": [TARGET_LAT, TARGET_LON],
        "drifting_train_n": n_tr,
        "drifting_val_n": n_va,
        "drifting_test_n": n_te,
        "test_icebergs": sorted(te["iceberg_id"].unique().tolist()),
        "hyperparameters": {"latitude": params_lat, "longitude": params_lon},
        "training_samples": len(X_tv),
        "training_time_s": train_s,
        "random_state": RANDOM_STATE,
        "metrics": metrics,
    }
    (MOD_DIR / "displacement_xgb_metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8")

    pred_df = te[["iceberg_id", "obs_date", "target_date", "lat", "lon",
                   "target_lat", "target_lon"]].copy()
    pred_df["pred_lat"] = pred_lat; pred_df["pred_lon"] = pred_lon
    pred_df.to_csv(MOD_DIR / "displacement_xgb_predictions.csv", index=False)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "displacement_xgb_evaluation.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\n  Saved: {MOD_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
