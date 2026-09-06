#!/usr/bin/env python3
"""
PHASE 3C — Random Forest on the EXPANDED dataset.

Adapts the approved Phase 3 Step 4 Random Forest methodology to the
expanded 342-train / 55-val / 54-test dataset while preserving every
integrity rule:
  - tune on train+val only (TimeSeriesSplit on train, select by val MAE)
  - retrain selected config on TRAIN+VAL
  - evaluate exactly once on the untouched 54-sample test set
  - no test data used for tuning / selection / scaling
  - C39 zero-shot isolation preserved (test-only iceberg)

Predictions & metrics use the shared eval_metrics_expanded module so all
models (and persistence) are measured identically.

Outputs (data/processed/ml/expanded/models/):
  random_forest_latitude.joblib / random_forest_longitude.joblib
  rf_expanded_metadata.json
  rf_predictions.csv
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error

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
    "n_estimators":      [100, 200, 400],
    "max_depth":         [5, 10, 15, None],
    "min_samples_split": [2, 5, 10],
    "min_samples_leaf":  [1, 2, 4],
    "max_features":      ["sqrt", 0.5, 0.8],
}
RANDOM_STATE = 42

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def tune_random_forest(X_train, y_train, X_val, y_val, target_name):
    """TimeSeriesSplit CV on train, then select by explicit validation MAE."""
    log.info("  Tuning Random Forest for %s ...", target_name)
    tscv = TimeSeriesSplit(n_splits=3)
    rf_base = RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=-1)
    grid = GridSearchCV(rf_base, PARAM_GRID, cv=tscv,
                        scoring="neg_mean_absolute_error", refit=True,
                        return_train_score=True, n_jobs=-1, verbose=0)
    t0 = time.perf_counter()
    grid.fit(X_train, y_train)
    t_train = time.perf_counter() - t0
    log.info("    GridSearchCV done in %.2fs — best CV MAE: %.6f",
             t_train, -grid.best_score_)

    candidates = []
    for params, mean_score, train_score in zip(
            grid.cv_results_["params"], grid.cv_results_["mean_test_score"],
            grid.cv_results_["mean_train_score"]):
        m = RandomForestRegressor(**params, random_state=RANDOM_STATE, n_jobs=-1)
        m.fit(X_train, y_train)
        val_mae = mean_absolute_error(y_val, m.predict(X_val))
        candidates.append({"params": params, "cv_mae": -float(mean_score),
                           "train_mae": -float(train_score), "val_mae": float(val_mae)})

    candidates.sort(key=lambda c: c["val_mae"])
    best = candidates[0]
    log.info("    Best params: %s  Val MAE=%.6f  CV MAE=%.6f",
             best["params"], best["val_mae"], best["cv_mae"])
    best_model = RandomForestRegressor(**best["params"],
                                       random_state=RANDOM_STATE, n_jobs=-1)
    best_model.fit(X_train, y_train)
    return best_model, best["params"], candidates


def feature_importance(model_lat, model_lon):
    imp_lat = model_lat.feature_importances_
    imp_lon = model_lon.feature_importances_
    df = pd.DataFrame({"feature": FEATURE_COLS,
                       "importance_lat": imp_lat, "importance_lon": imp_lon})
    df["importance_avg"] = (df["importance_lat"] + df["importance_lon"]) / 2
    return df.sort_values("importance_avg", ascending=False).reset_index(drop=True)


def main() -> int:
    print("=" * 70)
    print("PHASE 3C — RANDOM FOREST (expanded dataset)")
    print("=" * 70)

    train_df = pd.read_parquet(TRAIN_PATH)
    val_df = pd.read_parquet(VAL_PATH)
    test_df = pd.read_parquet(TEST_PATH)
    assert len(train_df) == 342 and len(val_df) == 55 and len(test_df) == 54, \
        f"Split mismatch: {len(train_df)}/{len(val_df)}/{len(test_df)}"
    print(f"  Train {len(train_df)} | Val {len(val_df)} | Test {len(test_df)}")

    for col in FEATURE_COLS + TARGET_COLS:
        assert col in train_df.columns, f"Missing column: {col}"

    # Chronological split verification
    train_max = pd.to_datetime(train_df["obs_date"]).max()
    val_min = pd.to_datetime(val_df["obs_date"]).min()
    val_max = pd.to_datetime(val_df["obs_date"]).max()
    test_min = pd.to_datetime(test_df["obs_date"]).min()
    assert train_max < val_min and val_max < test_min, "Chronological split violated"
    print(f"  Chronological split verified: train<={train_max.date()} val<={val_max.date()} test>={test_min.date()}")

    # C39 zero-shot isolation check
    assert (train_df["iceberg_id"] == "C39").sum() == 0
    assert (val_df["iceberg_id"] == "C39").sum() == 0
    assert (test_df["iceberg_id"] == "C39").sum() == 9
    print("  C39 zero-shot isolation verified (train=0, val=0, test=9)")

    X_train = train_df[FEATURE_COLS].values
    X_val = val_df[FEATURE_COLS].values
    X_test = test_df[FEATURE_COLS].values
    y_train_lat = train_df["target_lat"].values
    y_train_lon = train_df["target_lon"].values
    y_val_lat = val_df["target_lat"].values
    y_val_lon = val_df["target_lon"].values
    y_test_lat = test_df["target_lat"].values
    y_test_lon = test_df["target_lon"].values

    # RF natively handles NaN (prev_* first-observation rows) — verified in original.
    for nm, X in [("train", X_train), ("val", X_val), ("test", X_test)]:
        nan = int(np.isnan(X).sum())
        print(f"  NaN in {nm} features: {nan} (prev_* first-obs expected)")

    # ── Tune lat / lon ──
    rf_lat, params_lat, cands_lat = tune_random_forest(X_train, y_train_lat, X_val, y_val_lat, "latitude")
    rf_lon, params_lon, cands_lon = tune_random_forest(X_train, y_train_lon, X_val, y_val_lon, "longitude")
    print(f"  Lat params: {params_lat}")
    print(f"  Lon params: {params_lon}")

    # ── Retrain on TRAIN+VAL ──
    print("\n--- Retraining on TRAIN+VAL ---")
    X_tv = np.vstack([X_train, X_val])
    y_tv_lat = np.concatenate([y_train_lat, y_val_lat])
    y_tv_lon = np.concatenate([y_train_lon, y_val_lon])
    rf_lat_final = RandomForestRegressor(**params_lat, random_state=RANDOM_STATE, n_jobs=-1)
    rf_lon_final = RandomForestRegressor(**params_lon, random_state=RANDOM_STATE, n_jobs=-1)
    t0 = time.perf_counter()
    rf_lat_final.fit(X_tv, y_tv_lat)
    rf_lon_final.fit(X_tv, y_tv_lon)
    train_s = time.perf_counter() - t0
    print(f"  Final training on {len(X_tv)} samples: {train_s:.2f}s")

    # ── Evaluate once on test ──
    print("\n--- Evaluating on TEST ---")
    t0 = time.perf_counter()
    pred_lat = rf_lat_final.predict(X_test)
    t_infer_lat = time.perf_counter() - t0
    t0 = time.perf_counter()
    pred_lon = rf_lon_final.predict(X_test)
    t_infer_lon = time.perf_counter() - t0

    assert np.all(np.isfinite(pred_lat)) and np.all(np.isfinite(pred_lon)), "Non-finite predictions"
    results = evaluate_groups(test_df, pred_lat, pred_lon)
    print("  RF metrics by group:")
    for group, m in results.items():
        print(f"    {group:10s} n={m['n']:3d}  pos_mae={m['pos_mae']:.4f}  "
              f"pos_rmse={m['pos_rmse']:.4f}  med={m['pos_median']:.4f}  max={m['pos_max']:.4f}  "
              f"final={m['final_position_error']:.4f}  traj={m['trajectory_error']:.4f}  "
              f"disp={m['mean_displacement_error']:.4f}")

    # ── Feature importance ──
    imp_df = feature_importance(rf_lat_final, rf_lon_final)
    print("\n  Top 5 features:")
    for _, r in imp_df.head(5).iterrows():
        print(f"    {r.feature}: {r.importance_avg:.4f}")

    # ── Save ──
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(rf_lat_final, OUT_DIR / "random_forest_latitude.joblib")
    joblib.dump(rf_lon_final, OUT_DIR / "random_forest_longitude.joblib")

    ocean_feats = {"ocean_current_u", "ocean_current_v", "ocean_speed", "ocean_dir"}
    env_feats = {"wind_u_10m", "wind_v_10m", "wind_speed", "wind_dir", "temperature_2m",
                 "mean_sea_level_pressure", "total_precipitation", "sea_ice_concentration",
                 "exposed_water_fraction", "wind_ocean_angle"}
    ocean_imp = float(imp_df[imp_df["feature"].isin(ocean_feats)]["importance_avg"].sum())
    env_imp = float(imp_df[imp_df["feature"].isin(env_feats)]["importance_avg"].sum())

    meta = {
        "model_type": "RandomForestRegressor",
        "dataset": "expanded",
        "targets": TARGET_COLS,
        "n_features": len(FEATURE_COLS),
        "feature_columns": FEATURE_COLS,
        "hyperparameters": {"latitude": params_lat, "longitude": params_lon},
        "training_samples": len(X_tv),
        "split_counts": {"train": 342, "val": 55, "test": 54},
        "training_date": date.today().isoformat(),
        "random_state": RANDOM_STATE,
        "timing": {"train_s": train_s, "infer_lat_s": t_infer_lat, "infer_lon_s": t_infer_lon},
        "test_metrics": results,
        "feature_importance_avg": {r.feature: round(r.importance_avg, 4) for _, r in imp_df.iterrows()},
        "ocean_importance_share": round(ocean_imp, 4),
        "env_importance_share": round(env_imp, 4),
    }
    (OUT_DIR / "rf_expanded_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    pred_df = test_df[["iceberg_id", "obs_date", "target_date", "lat", "lon",
                       "target_lat", "target_lon", "persist_lat", "persist_lon"]].copy()
    pred_df["pred_lat"] = pred_lat
    pred_df["pred_lon"] = pred_lon
    pred_df.to_csv(OUT_DIR / "rf_predictions.csv", index=False)

    print(f"\n  Saved models + metadata → {OUT_DIR}")

    # Persistence comparison
    pers = evaluate_groups(test_df, test_df["persist_lat"].values, test_df["persist_lon"].values)
    impr = (pers["overall"]["pos_mae"] - results["overall"]["pos_mae"]) / pers["overall"]["pos_mae"] * 100
    print(f"\n  Overall RF pos_mae={results['overall']['pos_mae']:.3f} km vs persistence "
          f"{pers['overall']['pos_mae']:.3f} km → {impr:+.1f}%")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
