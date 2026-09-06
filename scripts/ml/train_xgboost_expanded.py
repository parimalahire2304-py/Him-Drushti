#!/usr/bin/env python3
"""
PHASE 3C — XGBoost on the EXPANDED dataset.

Faithful adaptation of the approved Phase 3 Step 5 XGBoost methodology
to the expanded 342-train / 55-val / 54-test dataset:
  - explicit train→val evaluation + TimeSeriesSplit(3) CV
  - no test data in tuning
  - natively handles prev_* NaN (no imputation, XGB's native NaN support)
  - gain-based feature importance
  - retrains best config on TRAIN+VAL, evaluates once on test
  - shared eval_metrics_expanded for subgroup metrics

Outputs (data/processed/ml/expanded/models/):
  xgboost_latitude.json  /  xgboost_longitude.json
  xgb_expanded_metadata.json
  xgb_predictions.csv
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
from sklearn.model_selection import TimeSeriesSplit

from eval_metrics_expanded import evaluate_groups

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXP = PROJECT_ROOT / "data" / "processed" / "ml" / "expanded"
OUT_DIR = EXP / "models"
TRAIN_PATH = EXP / "train.parquet"
VAL_PATH = EXP / "val.parquet"
TEST_PATH = EXP / "test.parquet"

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
    "prev_lat", "prev_lon",
    "prev_delta_lat", "prev_delta_lon",
    "prev_speed", "prev_bearing",
]
TARGET_COLS = ["target_lat", "target_lon"]

PARAM_GRID = {
    "n_estimators":     [50, 100, 200],
    "max_depth":        [3, 4, 5],
    "learning_rate":    [0.01, 0.05, 0.1],
    "min_child_weight": [3, 5, 10],
    "subsample":        [0.7, 0.8],
    "colsample_bytree": [0.7, 0.8],
    "reg_alpha":        [0.0, 0.1, 1.0],
    "reg_lambda":       [1.0, 5.0],
}
RANDOM_STATE = 42

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def _build_param_combos():
    keys = list(PARAM_GRID.keys())
    return [dict(zip(keys, vals)) for vals in itertools.product(*PARAM_GRID.values())]


def tune_xgboost(X_train, y_train, X_val, y_val, target_name):
    log.info("  Tuning XGBoost for %s ...", target_name)
    combos = _build_param_combos()
    log.info("    Total combinations: %d", len(combos))
    tscv = TimeSeriesSplit(n_splits=3)
    candidates = []
    t0 = time.perf_counter()

    for params in combos:
        xgb_params = dict(params, random_state=RANDOM_STATE, verbosity=0,
                          objective="reg:squarederror", n_jobs=-1)

        # TimeSeriesSplit CV on train
        cv_scores = []
        for tr_idx, vl_idx in tscv.split(X_train):
            Xtr, Xvl = X_train[tr_idx], X_train[vl_idx]
            ytr, yvl = y_train[tr_idx], y_train[vl_idx]
            m = xgb.XGBRegressor(**xgb_params)
            m.fit(Xtr, ytr, eval_set=[(Xvl, yvl)], verbose=False)
            cv_scores.append(mean_absolute_error(yvl, m.predict(Xvl)))
        cv_mae = float(np.mean(cv_scores))

        # Explicit val evaluation
        mf = xgb.XGBRegressor(**xgb_params)
        mf.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        val_mae = float(mean_absolute_error(y_val, mf.predict(X_val)))
        train_mae = float(mean_absolute_error(y_train, mf.predict(X_train)))

        candidates.append({"params": params, "cv_mae": cv_mae,
                           "val_mae": val_mae, "train_mae": train_mae, "model": mf})

    t_tune = time.perf_counter() - t0
    log.info("    Tuning done in %.2fs", t_tune)
    candidates.sort(key=lambda c: c["val_mae"])
    best = candidates[0]
    log.info("    Best params: %s  Val MAE=%.6f  CV MAE=%.6f  Train MAE=%.6f",
             best["params"], best["val_mae"], best["cv_mae"], best["train_mae"])
    return best["model"], best["params"], candidates, t_tune


def feature_importance(model_lat, model_lon):
    imp_lat = model_lat.feature_importances_
    imp_lon = model_lon.feature_importances_
    df = pd.DataFrame({"feature": FEATURE_COLS,
                       "importance_lat": imp_lat, "importance_lon": imp_lon})
    df["importance_avg"] = (df["importance_lat"] + df["importance_lon"]) / 2
    return df.sort_values("importance_avg", ascending=False).reset_index(drop=True)


def main() -> int:
    print("=" * 70)
    print("PHASE 3C — XGBOOST (expanded dataset)")
    print("=" * 70)

    train_df = pd.read_parquet(TRAIN_PATH)
    val_df = pd.read_parquet(VAL_PATH)
    test_df = pd.read_parquet(TEST_PATH)
    assert len(train_df) == 342 and len(val_df) == 55 and len(test_df) == 54, \
        f"Split mismatch: {len(train_df)}/{len(val_df)}/{len(test_df)}"
    print(f"  Train {len(train_df)} | Val {len(val_df)} | Test {len(test_df)}")

    for col in FEATURE_COLS + TARGET_COLS:
        assert col in train_df.columns, f"Missing column: {col}"

    train_max = pd.to_datetime(train_df["obs_date"]).max()
    val_min = pd.to_datetime(val_df["obs_date"]).min()
    val_max = pd.to_datetime(val_df["obs_date"]).max()
    test_min = pd.to_datetime(test_df["obs_date"]).min()
    assert train_max < val_min and val_max < test_min, "Chronological split violated"
    print(f"  Chronological split verified")
    assert (train_df["iceberg_id"] == "C39").sum() == 0
    assert (val_df["iceberg_id"] == "C39").sum() == 0
    assert (test_df["iceberg_id"] == "C39").sum() == 9
    print("  C39 zero-shot isolation verified")

    # XGB natively handles NaN (prev_*) — no imputation
    X_train = train_df[FEATURE_COLS].values
    X_val = val_df[FEATURE_COLS].values
    X_test = test_df[FEATURE_COLS].values
    y_train_lat = train_df["target_lat"].values
    y_train_lon = train_df["target_lon"].values
    y_val_lat = val_df["target_lat"].values
    y_val_lon = val_df["target_lon"].values

    for nm, X in [("train", X_train), ("val", X_val), ("test", X_test)]:
        print(f"  NaN in {nm}: {int(np.isnan(X).sum())}")

    # ── Tune lat / lon ──
    model_lat, params_lat, cands_lat, t_tune_lat = \
        tune_xgboost(X_train, y_train_lat, X_val, y_val_lat, "latitude")
    model_lon, params_lon, cands_lon, t_tune_lon = \
        tune_xgboost(X_train, y_train_lon, X_val, y_val_lon, "longitude")
    print(f"  Lat params: {params_lat}")
    print(f"  Lon params: {params_lon}")

    # ── Retrain on TRAIN+VAL ──
    print("\n--- Retraining on TRAIN+VAL ---")
    X_tv = np.vstack([X_train, X_val])
    y_tv_lat = np.concatenate([y_train_lat, y_val_lat])
    y_tv_lon = np.concatenate([y_train_lon, y_val_lon])
    xgb_lat_final = xgb.XGBRegressor(**params_lat, random_state=RANDOM_STATE,
                                      verbosity=0, objective="reg:squarederror", n_jobs=-1)
    xgb_lon_final = xgb.XGBRegressor(**params_lon, random_state=RANDOM_STATE,
                                      verbosity=0, objective="reg:squarederror", n_jobs=-1)
    t0 = time.perf_counter()
    xgb_lat_final.fit(X_tv, y_tv_lat, verbose=False)
    xgb_lon_final.fit(X_tv, y_tv_lon, verbose=False)
    train_s = time.perf_counter() - t0
    print(f"  Final training on {len(X_tv)} samples: {train_s:.2f}s")

    # ── Evaluate once on test ──
    print("\n--- Evaluating on TEST ---")
    t0 = time.perf_counter()
    pred_lat = xgb_lat_final.predict(X_test)
    t_infer_lat = time.perf_counter() - t0
    t0 = time.perf_counter()
    pred_lon = xgb_lon_final.predict(X_test)
    t_infer_lon = time.perf_counter() - t0
    assert np.all(np.isfinite(pred_lat)) and np.all(np.isfinite(pred_lon))
    results = evaluate_groups(test_df, pred_lat, pred_lon)
    print("  XGB metrics by group:")
    for group, m in results.items():
        print(f"    {group:10s} n={m['n']:3d}  pos_mae={m['pos_mae']:.4f}  "
              f"pos_rmse={m['pos_rmse']:.4f}  med={m['pos_median']:.4f}  max={m['pos_max']:.4f}  "
              f"final={m['final_position_error']:.4f}  traj={m['trajectory_error']:.4f}  "
              f"disp={m['mean_displacement_error']:.4f}")

    # ── Feature importance (gain-based) ──
    imp_df = feature_importance(xgb_lat_final, xgb_lon_final)
    print("\n  Top 5 features:")
    for _, r in imp_df.head(5).iterrows():
        print(f"    {r.feature}: {r.importance_avg:.4f}")

    # ── Save ──
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    xgb_lat_final.save_model(OUT_DIR / "xgboost_latitude.json")
    xgb_lon_final.save_model(OUT_DIR / "xgboost_longitude.json")

    ocean_feats = {"ocean_current_u", "ocean_current_v", "ocean_speed", "ocean_dir"}
    env_feats = {"wind_u_10m", "wind_v_10m", "wind_speed", "wind_dir", "temperature_2m",
                 "mean_sea_level_pressure", "total_precipitation", "sea_ice_concentration",
                 "exposed_water_fraction", "wind_ocean_angle"}
    ocean_imp = float(imp_df[imp_df["feature"].isin(ocean_feats)]["importance_avg"].sum())
    env_imp = float(imp_df[imp_df["feature"].isin(env_feats)]["importance_avg"].sum())

    meta = {
        "model_type": "XGBRegressor",
        "dataset": "expanded",
        "targets": TARGET_COLS,
        "n_features": len(FEATURE_COLS),
        "feature_columns": FEATURE_COLS,
        "hyperparameters": {"latitude": params_lat, "longitude": params_lon},
        "training_samples": len(X_tv),
        "split_counts": {"train": 342, "val": 55, "test": 54},
        "training_date": date.today().isoformat(),
        "random_state": RANDOM_STATE,
        "timing": {"train_s": train_s, "tune_lat_s": t_tune_lat, "tune_lon_s": t_tune_lon,
                    "infer_lat_s": t_infer_lat, "infer_lon_s": t_infer_lon},
        "test_metrics": results,
        "feature_importance_avg": {r.feature: round(r.importance_avg, 4) for _, r in imp_df.iterrows()},
        "ocean_importance_share": round(ocean_imp, 4),
        "env_importance_share": round(env_imp, 4),
    }
    (OUT_DIR / "xgb_expanded_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    pred_df = test_df[["iceberg_id", "obs_date", "target_date", "lat", "lon",
                       "target_lat", "target_lon", "persist_lat", "persist_lon"]].copy()
    pred_df["pred_lat"] = pred_lat
    pred_df["pred_lon"] = pred_lon
    pred_df.to_csv(OUT_DIR / "xgb_predictions.csv", index=False)

    print(f"\n  Saved models + metadata → {OUT_DIR}")
    pers = evaluate_groups(test_df, test_df["persist_lat"].values, test_df["persist_lon"].values)
    impr = (pers["overall"]["pos_mae"] - results["overall"]["pos_mae"]) / pers["overall"]["pos_mae"] * 100
    print(f"\n  Overall XGB pos_mae={results['overall']['pos_mae']:.3f} km vs persistence "
          f"{pers['overall']['pos_mae']:.3f} km → {impr:+.1f}%")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
