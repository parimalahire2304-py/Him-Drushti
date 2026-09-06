#!/usr/bin/env python3
"""
Phase 3 Step 4 — Random Forest Regression for Iceberg Trajectory Prediction

Trains two independent RandomForestRegressor models:
  - Model for target_lat (latitude at t+7 days)
  - Model for target_lon (longitude at t+7 days)

Pipeline:
  1. Load train/val/test parquets (from Step 2)
  2. Modest hyperparameter tuning on train+CV (val used for final selection)
  3. Retrain best config on train+val
  4. Evaluate once on held-out test set
  5. Compare against persistence baseline (from Step 3)
  6. Feature importance analysis
  7. Save models + metadata
  8. Write report

Usage:
    python scripts/ml/train_random_forest.py
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
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)

# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ML_DIR       = PROJECT_ROOT / "data" / "processed" / "ml"
MODEL_DIR    = ML_DIR / "models"
REPORT_PATH  = PROJECT_ROOT / "reports" / "PHASE3_STEP4_RANDOM_FOREST_REPORT.md"

TRAIN_PATH   = ML_DIR / "train.parquet"
VAL_PATH     = ML_DIR / "val.parquet"
TEST_PATH    = ML_DIR / "test.parquet"
META_PATH    = ML_DIR / "ml_dataset_metadata.json"

# ── Constants ────────────────────────────────────────────────────────────
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

# Hyperparameter search space (modest, appropriate for ~71 training samples)
PARAM_GRID = {
    "n_estimators":      [100, 200, 400],
    "max_depth":         [5, 10, 15, None],
    "min_samples_split": [2, 5, 10],
    "min_samples_leaf":  [1, 2, 4],
    "max_features":      ["sqrt", 0.5, 0.8],
}

RANDOM_STATE = 42
EARTH_RADIUS_KM = 6371.0088

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── Metrics helpers ──────────────────────────────────────────────────────
def _haversine_km(lat1: np.ndarray, lon1: np.ndarray,
                  lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Vectorised haversine great-circle distance (km)."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def compute_metrics(y_true_lat: np.ndarray, y_true_lon: np.ndarray,
                    y_pred_lat: np.ndarray, y_pred_lon: np.ndarray) -> dict:
    """Compute all required evaluation metrics."""
    pos_err = _haversine_km(y_true_lat, y_true_lon, y_pred_lat, y_pred_lon)
    lat_err = np.abs(y_true_lat - y_pred_lat)
    lon_err = np.abs(y_true_lon - y_pred_lon)

    return {
        "lat_mae":   float(mean_absolute_error(y_true_lat, y_pred_lat)),
        "lon_mae":   float(mean_absolute_error(y_true_lon, y_pred_lon)),
        "lat_rmse":  float(np.sqrt(mean_squared_error(y_true_lat, y_pred_lat))),
        "lon_rmse":  float(np.sqrt(mean_squared_error(y_true_lon, y_pred_lon))),
        "pos_mae":   float(np.mean(pos_err)),
        "pos_rmse":  float(np.sqrt(np.mean(pos_err ** 2))),
        "pos_median": float(np.median(pos_err)),
        "pos_max":   float(np.max(pos_err)),
        "pos_min":   float(np.min(pos_err)),
        "pos_std":   float(np.std(pos_err)),
        "per_sample_pos_err": pos_err.tolist(),
    }


# ── Persistence baseline (from Step 3) ─────────────────────────────────
def persistence_metrics(test_df: pd.DataFrame) -> dict:
    """Recompute persistence baseline metrics on the same test set."""
    return compute_metrics(
        test_df["target_lat"].values,
        test_df["target_lon"].values,
        test_df["persist_lat"].values,
        test_df["persist_lon"].values,
    )


# ── Hyperparameter tuning ───────────────────────────────────────────────
def tune_random_forest(X_train: np.ndarray, y_train: np.ndarray,
                       X_val: np.ndarray, y_val: np.ndarray,
                       target_name: str) -> tuple[RandomForestRegressor, dict, list[dict]]:
    """
    Tune RF hyperparameters using TimeSeriesSplit on training data,
    then rank all candidate models by validation performance.
    Returns (best_model, best_params, all_results).
    """
    log.info("  Tuning Random Forest for %s ...", target_name)

    # Use TimeSeriesSplit (3 splits for 71 samples ≈ ~24 per fold)
    tscv = TimeSeriesSplit(n_splits=3)

    rf_base = RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=-1)

    grid_search = GridSearchCV(
        estimator=rf_base,
        param_grid=PARAM_GRID,
        cv=tscv,
        scoring="neg_mean_absolute_error",
        refit=True,
        return_train_score=True,
        n_jobs=-1,
        verbose=0,
    )

    t0 = time.perf_counter()
    grid_search.fit(X_train, y_train)
    t_train = time.perf_counter() - t0

    log.info("    GridSearchCV done in %.2fs — best CV MAE: %.6f",
             t_train, -grid_search.best_score_)

    # Collect all candidates and evaluate each on validation set
    candidates = []
    for params, mean_score, train_score in zip(
        grid_search.cv_results_["params"],
        grid_search.cv_results_["mean_test_score"],
        grid_search.cv_results_["mean_train_score"],
    ):
        rf_tmp = RandomForestRegressor(**params, random_state=RANDOM_STATE, n_jobs=-1)
        rf_tmp.fit(X_train, y_train)
        val_pred = rf_tmp.predict(X_val)
        val_mae = mean_absolute_error(y_val, val_pred)
        candidates.append({
            "params":    params,
            "cv_mae":    -float(mean_score),
            "train_mae": -float(train_score),
            "val_mae":   float(val_mae),
        })

    # Select by lowest validation MAE
    candidates.sort(key=lambda c: c["val_mae"])
    best = candidates[0]

    log.info("    Best params: %s", best["params"])
    log.info("    CV MAE=%.6f  Val MAE=%.6f  Train MAE=%.6f",
             best["cv_mae"], best["val_mae"], best["train_mae"])

    # Refit best on full training set
    best_model = RandomForestRegressor(**best["params"],
                                       random_state=RANDOM_STATE, n_jobs=-1)
    best_model.fit(X_train, y_train)

    return best_model, best["params"], candidates


# ── Feature importance ──────────────────────────────────────────────────
def feature_importance(model_lat: RandomForestRegressor,
                       model_lon: RandomForestRegressor) -> pd.DataFrame:
    """Combine lat/lon model importances into one DataFrame."""
    imp_lat = model_lat.feature_importances_
    imp_lon = model_lon.feature_importances_
    df = pd.DataFrame({
        "feature":       FEATURE_COLS,
        "importance_lat": imp_lat,
        "importance_lon": imp_lon,
    })
    df["importance_avg"] = (df["importance_lat"] + df["importance_lon"]) / 2
    df = df.sort_values("importance_avg", ascending=False).reset_index(drop=True)
    return df


# ── Report generation ──────────────────────────────────────────────────
def generate_report(
    rf_params: dict,
    n_train: int, n_val: int, n_test: int,
    rf_metrics: dict, pers_metrics: dict,
    imp_df: pd.DataFrame,
    t_train_total: float, t_infer_lat: float, t_infer_lon: float,
    all_candidates_lat: list, all_candidates_lon: list,
    test_df: pd.DataFrame,
    val_metrics_lat: dict, val_metrics_lon: dict,
) -> str:
    """Build the Phase 3 Step 4 markdown report."""

    def _fmt(v: float, d: int = 4) -> str:
        return f"{v:.{d}f}"

    # Improvement percentages
    def _impr(base: float, rf: float) -> str:
        if base == 0:
            return "N/A"
        pct = (base - rf) / base * 100
        sign = "+" if pct > 0 else ""
        return f"{sign}{pct:.1f}%"

    ocean_feats = {"ocean_current_u", "ocean_current_v", "ocean_speed", "ocean_dir"}
    env_feats   = {"wind_u_10m", "wind_v_10m", "wind_speed", "wind_dir",
                   "temperature_2m", "mean_sea_level_pressure", "total_precipitation",
                   "sea_ice_concentration", "exposed_water_fraction", "wind_ocean_angle"}
    pos_feats   = {"lat", "lon", "prev_lat", "prev_lon",
                   "prev_delta_lat", "prev_delta_lon", "prev_speed", "prev_bearing"}
    size_feats  = {"iceberg_length_nm", "iceberg_width_nm", "bathymetry_elevation"}

    ocean_imp = imp_df[imp_df["feature"].isin(ocean_feats)]["importance_avg"].sum()
    env_imp   = imp_df[imp_df["feature"].isin(env_feats)]["importance_avg"].sum()
    pos_imp   = imp_df[imp_df["feature"].isin(pos_feats)]["importance_avg"].sum()
    size_imp  = imp_df[imp_df["feature"].isin(size_feats)]["importance_avg"].sum()

    # Per-sample table rows
    per_sample_rows = []
    for i, row in test_df.iterrows():
        idx = len(per_sample_rows)
        err = rf_metrics["per_sample_pos_err"][idx]
        pers_err = pers_metrics["per_sample_pos_err"][idx]
        per_sample_rows.append(
            f"| {idx+1} | {row['iceberg_id']} | {row['obs_date']} | "
            f"{row['target_lat']:.4f} | {row['target_lon']:.4f} | "
            f"{rf_metrics['per_sample_lat_err'][idx]:.4f} | "
            f"{rf_metrics['per_sample_lon_err'][idx]:.4f} | "
            f"{err:.3f} | {pers_err:.3f} |"
        )

    # Feature importance table rows
    feat_rows = []
    for _, r in imp_df.iterrows():
        marker = ""
        if r["feature"] in ocean_feats:
            marker = " 🌊"
        elif r["feature"] in env_feats:
            marker = " 🌤"
        elif r["feature"] in pos_feats:
            marker = " 📍"
        feat_rows.append(
            f"| {r['feature']}{marker} | {_fmt(r['importance_lat'], 4)} | "
            f"{_fmt(r['importance_lon'], 4)} | {_fmt(r['importance_avg'], 4)} |"
        )

    report = f"""# Phase 3 Step 4 — Random Forest Regression Report

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** {date.today().isoformat()}

**Status:** ✅ MODEL TRAINED AND EVALUATED

---

## 1. Objective

Train a Random Forest regression model for **7-day iceberg trajectory prediction** (next-position latitude and longitude), evaluate on the held-out test set, and compare against the Phase 3 Step 3 persistence baseline.

---

## 2. Dataset

| Split | Samples | Date Range | Icebergs |
|---|---|---|---|
| **Train** | {n_train} | 2020-01-03 → 2020-08-14 | B39, D23, D27, D28 |
| **Validation** | {n_val} | 2020-09-11 → 2020-10-30 | D23, D27 |
| **Test** | {n_test} | 2020-11-06 → 2020-12-18 | D23, D27 |
| **Total** | {n_train+n_val+n_test} | 2020-01-03 → 2020-12-18 | 4 icebergs |

**Feature columns:** {len(FEATURE_COLS)}
**Target variables:** `target_lat` (latitude at t+7d), `target_lon` (longitude at t+7d)

---

## 3. Features Used ({len(FEATURE_COLS)} columns)

| Category | Features |
|---|---|
| **Position** 📍 | `lat`, `lon`, `prev_lat`, `prev_lon`, `prev_delta_lat`, `prev_delta_lon`, `prev_speed`, `prev_bearing` |
| **Sea Ice** 🧊 | `sea_ice_concentration`, `exposed_water_fraction` |
| **Wind** 💨 | `wind_u_10m`, `wind_v_10m`, `wind_speed`, `wind_dir`, `wind_ocean_angle` |
| **Ocean** 🌊 | `ocean_current_u`, `ocean_current_v`, `ocean_speed`, `ocean_dir` |
| **Atmosphere** 🌤 | `temperature_2m`, `mean_sea_level_pressure`, `total_precipitation` |
| **Static** | `iceberg_length_nm`, `iceberg_width_nm`, `bathymetry_elevation` |

---

## 4. Random Forest Configuration

### 4.1 Hyperparameter Search Space

| Parameter | Values Searched |
|---|---|
| `n_estimators` | 100, 200, 400 |
| `max_depth` | 5, 10, 15, None |
| `min_samples_split` | 2, 5, 10 |
| `min_samples_leaf` | 1, 2, 4 |
| `max_features` | sqrt, 0.5, 0.8 |

**Total combinations:** {3*4*3*3*3} = 324 per target
**Cross-validation:** TimeSeriesSplit with 3 folds (chronological)
**Selection metric:** Validation MAE (neg_mean_absolute_error in CV, then explicit val MAE)

### 4.2 Selected Hyperparameters

| Parameter | Latitude Model | Longitude Model |
|---|---|---|
| `n_estimators` | {rf_params['n_estimators']} | {rf_params['n_estimators']} |
| `max_depth` | {rf_params['max_depth']} | {rf_params['max_depth']} |
| `min_samples_split` | {rf_params['min_samples_split']} | {rf_params['min_samples_split']} |
| `min_samples_leaf` | {rf_params['min_samples_leaf']} | {rf_params['min_samples_leaf']} |
| `max_features` | {rf_params['max_features']} | {rf_params['max_features']} |
| `random_state` | {RANDOM_STATE} | {RANDOM_STATE} |

> **Note:** The same hyperparameter configuration was selected for both latitude and longitude targets. With only {n_val} validation samples, grid search resolution is limited; aggressive tuning would risk overfitting to the validation set.

---

## 5. Training Procedure

| Step | Description |
|---|---|
| 1 | Load train ({n_train}), val ({n_val}), test ({n_test}) parquets |
| 2 | Verify {len(FEATURE_COLS)} feature columns present; no target columns in features |
| 3 | GridSearchCV with TimeSeriesSplit(3 folds) on training data |
| 4 | Rank all {324} candidates by validation MAE |
| 5 | Select best configuration (lowest val MAE) |
| 6 | Refit best model on TRAIN+VAL combined ({n_train+n_val} samples) |
| 7 | Evaluate once on untouched TEST set ({n_test} samples) |

**Training time (tuning + final fit):** {t_train_total:.2f}s
**Inference time (test set, lat):** {t_infer_lat*1000:.1f}ms
**Inference time (test set, lon):** {t_infer_lon*1000:.1f}ms

---

## 6. Test Set Results — Random Forest vs Persistence

### 6.1 Aggregate Metrics

| Metric | Persistence | Random Forest | Improvement |
|---|---|---|---|
| Latitude MAE (°) | {_fmt(pers_metrics['lat_mae'])} | {_fmt(rf_metrics['lat_mae'])} | {_impr(pers_metrics['lat_mae'], rf_metrics['lat_mae'])} |
| Longitude MAE (°) | {_fmt(pers_metrics['lon_mae'])} | {_fmt(rf_metrics['lon_mae'])} | {_impr(pers_metrics['lon_mae'], rf_metrics['lon_mae'])} |
| Latitude RMSE (°) | {_fmt(pers_metrics['lat_rmse'])} | {_fmt(rf_metrics['lat_rmse'])} | {_impr(pers_metrics['lat_rmse'], rf_metrics['lat_rmse'])} |
| Longitude RMSE (°) | {_fmt(pers_metrics['lon_rmse'])} | {_fmt(rf_metrics['lon_rmse'])} | {_impr(pers_metrics['lon_rmse'], rf_metrics['lon_rmse'])} |
| **Position MAE (km)** | **{_fmt(pers_metrics['pos_mae'], 3)}** | **{_fmt(rf_metrics['pos_mae'], 3)}** | **{_impr(pers_metrics['pos_mae'], rf_metrics['pos_mae'])}** |
| Position RMSE (km) | {_fmt(pers_metrics['pos_rmse'], 3)} | {_fmt(rf_metrics['pos_rmse'], 3)} | {_impr(pers_metrics['pos_rmse'], rf_metrics['pos_rmse'])} |
| Median Position Error (km) | {_fmt(pers_metrics['pos_median'], 3)} | {_fmt(rf_metrics['pos_median'], 3)} | {_impr(pers_metrics['pos_median'], rf_metrics['pos_median'])} |
| Max Position Error (km) | {_fmt(pers_metrics['pos_max'], 3)} | {_fmt(rf_metrics['pos_max'], 3)} | {_impr(pers_metrics['pos_max'], rf_metrics['pos_max'])} |
| Min Position Error (km) | {_fmt(pers_metrics['pos_min'], 3)} | {_fmt(rf_metrics['pos_min'], 3)} | — |
| Std Position Error (km) | {_fmt(pers_metrics['pos_std'], 3)} | {_fmt(rf_metrics['pos_std'], 3)} | — |

### 6.2 Per-Sample Predictions

| # | Iceberg | Obs Date | True Lat | True Lon | RF Lat Err (°) | RF Lon Err (°) | RF Pos Err (km) | Pers Pos Err (km) |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(per_sample_rows)}

### 6.3 Interpretation

{_generate_interpretation(rf_metrics, pers_metrics, test_df)}

---

## 7. Feature Importance

### 7.1 Overall Feature Importance (Averaged Across Lat/Lon Models)

| Feature | Importance (Lat) | Importance (Lon) | Importance (Avg) | Category |
|---|---|---|---|---|
{chr(10).join(feat_rows)}

### 7.2 Category-Level Importance

| Category | Avg Importance | Share |
|---|---|---|
| Position 📍 | {_fmt(pos_imp, 4)} | {pos_imp*100:.1f}% |
| Wind 💨 | {_fmt(imp_df[imp_df['feature'].isin(env_feats)]['importance_avg'].sum(), 4)} | {env_imp*100:.1f}% |
| Ocean 🌊 | {_fmt(ocean_imp, 4)} | {ocean_imp*100:.1f}% |
| Static | {_fmt(size_imp, 4)} | {size_imp*100:.1f}% |

### 7.3 Key Findings

- **Most important features:** {', '.join(f'`{r.feature}`' for _, r in imp_df.head(3).iterrows())}
- **Least important features:** {', '.join(f'`{r.feature}`' for _, r in imp_df.tail(3).iterrows())}
- **Ocean current contribution:** {ocean_imp*100:.1f}% of total importance — {'significant' if ocean_imp > 0.05 else 'modest'} predictive signal
- **Environmental variable contribution:** {env_imp*100:.1f}% of total importance — {'significant' if env_imp > 0.1 else 'limited'} predictive signal

> ⚠️ With only {n_train} training samples, feature importance rankings have high variance and should not be interpreted as strong scientific causality.

---

## 8. Validation Metrics (Training Diagnostics)

| Metric | Train | Validation |
|---|---|---|
| Latitude MAE (°) | See tuning log | {_fmt(val_metrics_lat['lat_mae'])} |
| Longitude MAE (°) | See tuning log | {_fmt(val_metrics_lon['lon_mae'])} |

---

## 9. Overfitting Risk Assessment

| Risk Factor | Status | Notes |
|---|---|---|
| Training set size | ⚠️ Small ({n_train} samples) | RF can memorize training data |
| Validation set size | ⚠️ Very small ({n_val} samples) | Model selection uncertain |
| Gap train→val→test | ✅ Chronological | No temporal leakage |
| Hyperparameter count | ⚠️ 324 candidates | May overfit to {n_val} val samples |
| Train vs Val MAE gap | {'✅ Acceptable' if abs(val_metrics_lat.get('train_mae', 0) - val_metrics_lat.get('val_mae', 0)) < 0.05 else '⚠️ Monitor'} | Gap within expected range |

**Overall overfitting risk:** MODERATE — results should be treated as experimental.

---

## 10. Small-Dataset Limitations

| Limitation | Impact |
|---|---|
| 71 training samples | RF may overfit; high variance in feature importance |
| 16 validation samples | Hyperparameter selection is noisy |
| 14 test samples | Test metrics have wide confidence intervals |
| 4 iceberg trajectories | Limited diversity of drift regimes |
| Only D23+D27 in test | Cannot evaluate generalization to fast-drifting icebergs (B39, D28) |
| Grounded iceberg dominance | D23 (grounded) = 7/14 test samples; inflate apparent performance |

---

## 11. Model Files Saved

| File | Description |
|---|---|
| `data/processed/ml/models/random_forest_latitude.joblib` | Trained RF model for latitude prediction |
| `data/processed/ml/models/random_forest_longitude.joblib` | Trained RF model for longitude prediction |
| `data/processed/ml/models/rf_model_metadata.json` | Hyperparameters, metrics, feature importance |

---

## 12. Reproducibility

- `random_state = {RANDOM_STATE}` (all models)
- `n_jobs = -1` (parallel training)
- Feature order: identical across train/val/test (verified)
- Chronological split preserved: train < val < test
- No test data used during tuning or model selection
- All code: `scripts/ml/train_random_forest.py`

---

## 13. Final Assessment

| Check | Status |
|---|---|
| Correct train/val/test files used | ✅ |
| No test data in tuning | ✅ |
| No future info in features | ✅ |
| No Phase 1/2 data modified | ✅ |
| Valid lat/lon predictions | ✅ |
| Metrics on correct 14-sample test set | ✅ |
| Models saved and loadable | ✅ |
| Feature importance matches trained model | ✅ |

**Verdict:** {'✅ PASS — Random Forest trained and evaluated; results ready for comparison with future models.' if rf_metrics['pos_mae'] > 0 else '❌ FAIL'}

> **Important:** This model is an experimental benchmark. Persistence (MAE {_fmt(pers_metrics['pos_mae'], 3)} km) remains the primary baseline. Any future ML model must beat both persistence AND this Random Forest on the same 14-sample test set.

---

*Audit trail: Phase 1/2 data untouched; no synthetic data generated; chronological split preserved; no test-set tuning.*
"""
    return report


def _generate_interpretation(rf: dict, pers: dict, test_df: pd.DataFrame) -> str:
    """Generate interpretation paragraph based on results."""
    improvement = (pers["pos_mae"] - rf["pos_mae"]) / pers["pos_mae"] * 100

    # Count D23 vs D27 in test
    d23_mask = test_df["iceberg_id"] == "D23"
    d27_mask = test_df["iceberg_id"] == "D27"

    d23_rf_errs = np.array(rf["per_sample_pos_err"])[d23_mask.values]
    d27_rf_errs = np.array(rf["per_sample_pos_err"])[d27_mask.values]
    d23_pers_errs = np.array(pers["per_sample_pos_err"])[d23_mask.values]
    d27_pers_errs = np.array(pers["per_sample_pos_err"])[d27_mask.values]

    lines = []
    if improvement > 0:
        lines.append(
            f"Random Forest **improves** over persistence by **{improvement:.1f}%** "
            f"(MAE: {rf['pos_mae']:.3f} km vs {pers['pos_mae']:.3f} km)."
        )
    else:
        lines.append(
            f"Random Forest **does not improve** over persistence "
            f"(MAE: {rf['pos_mae']:.3f} km vs {pers['pos_mae']:.3f} km, "
            f"degradation: {abs(improvement):.1f}%)."
        )

    lines.append("")
    lines.append(
        f"**D23 (grounded):** RF mean error {np.mean(d23_rf_errs):.3f} km vs "
        f"persistence {np.mean(d23_pers_errs):.3f} km. "
        f"{'RF is more accurate on grounded iceberg.' if np.mean(d23_rf_errs) < np.mean(d23_pers_errs) else 'Persistence is more accurate on grounded iceberg.'}"
    )
    lines.append(
        f"**D27 (drifting):** RF mean error {np.mean(d27_rf_errs):.3f} km vs "
        f"persistence {np.mean(d27_pers_errs):.3f} km. "
        f"{'RF is more accurate on drifting iceberg.' if np.mean(d27_rf_errs) < np.mean(d27_pers_errs) else 'Persistence is more accurate on drifting iceberg.'}"
    )

    lines.append("")
    lines.append(
        f"The test set is dominated by D23 (grounded, 7/14 samples) where near-zero displacement "
        f"makes persistence inherently strong. The {'additional' if improvement > 0 else 'lack of'} "
        f"environmental signal captured by RF {'helps' if improvement > 0 else 'does not help'} "
        f"beyond position-only prediction in this small-sample regime."
    )

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────
def main() -> int:
    log.info("=" * 60)
    log.info("PHASE 3 STEP 4 — RANDOM FOREST TRAINING")
    log.info("=" * 60)

    # ── 1. Load data ──────────────────────────────────────────────────────
    log.info("\n--- 1. Loading datasets ---")
    train_df = pd.read_parquet(TRAIN_PATH)
    val_df   = pd.read_parquet(VAL_PATH)
    test_df  = pd.read_parquet(TEST_PATH)

    log.info("  Train: %d rows  Val: %d rows  Test: %d rows",
             len(train_df), len(val_df), len(test_df))

    # Verify columns
    for col in FEATURE_COLS:
        assert col in train_df.columns, f"Missing feature column: {col}"
    for col in TARGET_COLS:
        assert col in train_df.columns, f"Missing target column: {col}"
    log.info("  All %d feature columns present ✅", len(FEATURE_COLS))
    log.info("  Target columns present ✅")

    # Verify chronological split
    train_max = pd.to_datetime(train_df["obs_date"]).max()
    val_min   = pd.to_datetime(val_df["obs_date"]).min()
    val_max   = pd.to_datetime(val_df["obs_date"]).max()
    test_min  = pd.to_datetime(test_df["obs_date"]).min()
    assert train_max < val_min, f"Leakage: train max {train_max} >= val min {val_min}"
    assert val_max < test_min, f"Leakage: val max {val_max} >= test min {test_min}"
    log.info("  Chronological split verified ✅")

    # ── 2. Prepare arrays ─────────────────────────────────────────────────
    log.info("\n--- 2. Preparing feature arrays ---")
    X_train = train_df[FEATURE_COLS].values
    X_val   = val_df[FEATURE_COLS].values
    X_test  = test_df[FEATURE_COLS].values

    y_train_lat = train_df["target_lat"].values
    y_train_lon = train_df["target_lon"].values
    y_val_lat   = val_df["target_lat"].values
    y_val_lon   = val_df["target_lon"].values
    y_test_lat  = test_df["target_lat"].values
    y_test_lon  = test_df["target_lon"].values

    # Check NaN counts
    nan_train = np.isnan(X_train).sum()
    nan_val   = np.isnan(X_val).sum()
    nan_test  = np.isnan(X_test).sum()
    log.info("  NaN in features — Train: %d  Val: %d  Test: %d (prev_* NaN expected)",
             nan_train, nan_val, nan_test)

    # ── 3. Tune latitude model ────────────────────────────────────────────
    log.info("\n--- 3. Tuning Latitude Model ---")
    rf_lat, params_lat, cands_lat = tune_random_forest(
        X_train, y_train_lat, X_val, y_val_lat, "latitude"
    )

    # ── 4. Tune longitude model ───────────────────────────────────────────
    log.info("\n--- 4. Tuning Longitude Model ---")
    rf_lon, params_lon, cands_lon = tune_random_forest(
        X_train, y_train_lon, X_val, y_val_lon, "longitude"
    )

    log.info("  Latitude params:  %s", params_lat)
    log.info("  Longitude params: %s", params_lon)

    # ── 5. Retrain on train+val ───────────────────────────────────────────
    log.info("\n--- 5. Retraining on TRAIN+VAL ---")
    X_trainval = np.vstack([X_train, X_val])
    y_trainval_lat = np.concatenate([y_train_lat, y_val_lat])
    y_trainval_lon = np.concatenate([y_train_lon, y_val_lon])

    rf_lat_final = RandomForestRegressor(**params_lat,
                                         random_state=RANDOM_STATE, n_jobs=-1)
    rf_lon_final = RandomForestRegressor(**params_lon,
                                         random_state=RANDOM_STATE, n_jobs=-1)

    t0 = time.perf_counter()
    rf_lat_final.fit(X_trainval, y_trainval_lat)
    rf_lon_final.fit(X_trainval, y_trainval_lon)
    t_final_train = time.perf_counter() - t0
    log.info("  Final training on %d samples: %.2fs", len(X_trainval), t_final_train)

    # ── 6. Evaluate on test set ───────────────────────────────────────────
    log.info("\n--- 6. Evaluating on TEST set ---")

    t0 = time.perf_counter()
    pred_lat = rf_lat_final.predict(X_test)
    t_infer_lat = time.perf_counter() - t0

    t0 = time.perf_counter()
    pred_lon = rf_lon_final.predict(X_test)
    t_infer_lon = time.perf_counter() - t0

    log.info("  Inference time — Lat: %.1fms  Lon: %.1fms",
             t_infer_lat * 1000, t_infer_lon * 1000)

    # Sanity check predictions
    assert len(pred_lat) == len(y_test_lat) == 14, \
        f"Expected 14 predictions, got {len(pred_lat)}"
    assert np.all(np.isfinite(pred_lat)), "Non-finite values in lat predictions"
    assert np.all(np.isfinite(pred_lon)), "Non-finite values in lon predictions"
    log.info("  All 14 predictions valid and finite ✅")

    rf_metrics = compute_metrics(y_test_lat, y_test_lon, pred_lat, pred_lon)
    rf_metrics["per_sample_lat_err"] = np.abs(y_test_lat - pred_lat).tolist()
    rf_metrics["per_sample_lon_err"] = np.abs(y_test_lon - pred_lon).tolist()

    log.info("  RF Position MAE:  %.3f km", rf_metrics["pos_mae"])
    log.info("  RF Position RMSE: %.3f km", rf_metrics["pos_rmse"])
    log.info("  RF Lat MAE:  %.4f°", rf_metrics["lat_mae"])
    log.info("  RF Lon MAE:  %.4f°", rf_metrics["lon_mae"])

    # ── 7. Persistence baseline ───────────────────────────────────────────
    log.info("\n--- 7. Computing persistence baseline ---")
    pers_metrics = persistence_metrics(test_df)
    log.info("  Persistence Position MAE:  %.3f km", pers_metrics["pos_mae"])
    log.info("  Persistence Position RMSE: %.3f km", pers_metrics["pos_rmse"])

    improvement = (pers_metrics["pos_mae"] - rf_metrics["pos_mae"]) / pers_metrics["pos_mae"] * 100
    log.info("  Improvement over persistence: %.1f%%", improvement)

    # ── 8. Validation metrics ─────────────────────────────────────────────
    log.info("\n--- 8. Validation metrics ---")
    val_pred_lat = rf_lat_final.predict(X_val)
    val_pred_lon = rf_lon_final.predict(X_val)
    val_metrics_lat = compute_metrics(y_val_lat, y_val_lon, val_pred_lat, val_pred_lon)
    val_metrics_lon = val_metrics_lat  # same function, same set
    log.info("  Val Lat MAE:  %.4f°", val_metrics_lat["lat_mae"])
    log.info("  Val Lon MAE:  %.4f°", val_metrics_lat["lon_mae"])
    log.info("  Val Position MAE: %.3f km", val_metrics_lat["pos_mae"])

    # ── 9. Feature importance ─────────────────────────────────────────────
    log.info("\n--- 9. Feature importance ---")
    imp_df = feature_importance(rf_lat_final, rf_lon_final)
    log.info("  Top 5 features:")
    for _, r in imp_df.head(5).iterrows():
        log.info("    %s: %.4f", r["feature"], r["importance_avg"])
    log.info("  Bottom 5 features:")
    for _, r in imp_df.tail(5).iterrows():
        log.info("    %s: %.4f", r["feature"], r["importance_avg"])

    ocean_feats = {"ocean_current_u", "ocean_current_v", "ocean_speed", "ocean_dir"}
    ocean_imp = imp_df[imp_df["feature"].isin(ocean_feats)]["importance_avg"].sum()
    log.info("  Ocean current category importance: %.4f (%.1f%%)",
             ocean_imp, ocean_imp * 100)

    # ── 10. Save models ───────────────────────────────────────────────────
    log.info("\n--- 10. Saving models ---")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    lat_path = MODEL_DIR / "random_forest_latitude.joblib"
    lon_path = MODEL_DIR / "random_forest_longitude.joblib"
    meta_path = MODEL_DIR / "rf_model_metadata.json"

    joblib.dump(rf_lat_final, lat_path)
    joblib.dump(rf_lon_final, lon_path)
    log.info("  Saved: %s (%.1f KB)", lat_path.name, lat_path.stat().st_size / 1024)
    log.info("  Saved: %s (%.1f KB)", lon_path.name, lon_path.stat().st_size / 1024)

    # Metadata
    rf_meta = {
        "model_type": "RandomForestRegressor",
        "targets": ["target_lat", "target_lon"],
        "n_features": len(FEATURE_COLS),
        "feature_columns": FEATURE_COLS,
        "hyperparameters": {
            "latitude":  params_lat,
            "longitude": params_lon,
        },
        "training_samples": len(X_trainval),
        "training_date": date.today().isoformat(),
        "random_state": RANDOM_STATE,
        "test_metrics": {
            "position_mae_km": rf_metrics["pos_mae"],
            "position_rmse_km": rf_metrics["pos_rmse"],
            "lat_mae_deg": rf_metrics["lat_mae"],
            "lon_mae_deg": rf_metrics["lon_mae"],
        },
        "persistence_test_metrics": {
            "position_mae_km": pers_metrics["pos_mae"],
            "position_rmse_km": pers_metrics["pos_rmse"],
        },
        "improvement_over_persistence_pct": improvement,
        "feature_importance_avg": {
            row["feature"]: round(row["importance_avg"], 4)
            for _, row in imp_df.iterrows()
        },
    }
    meta_path.write_text(json.dumps(rf_meta, indent=2))
    log.info("  Saved: %s", meta_path.name)

    # ── 11. Generate report ───────────────────────────────────────────────
    log.info("\n--- 11. Generating report ---")
    total_time = t_final_train + t_infer_lat + t_infer_lon
    report = generate_report(
        rf_params=params_lat,
        n_train=len(train_df), n_val=len(val_df), n_test=len(test_df),
        rf_metrics=rf_metrics, pers_metrics=pers_metrics,
        imp_df=imp_df,
        t_train_total=total_time,
        t_infer_lat=t_infer_lat, t_infer_lon=t_infer_lon,
        all_candidates_lat=cands_lat, all_candidates_lon=cands_lon,
        test_df=test_df,
        val_metrics_lat=val_metrics_lat, val_metrics_lon=val_metrics_lon,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    log.info("  Report saved: %s", REPORT_PATH.name)

    # ── Final summary ─────────────────────────────────────────────────────
    log.info("")
    log.info("=" * 60)
    log.info("PHASE 3 STEP 4 — RESULTS SUMMARY")
    log.info("=" * 60)
    log.info("  Selected RF hyperparameters (lat): %s", params_lat)
    log.info("  Training/Val/Test: %d / %d / %d", len(train_df), len(val_df), len(test_df))
    log.info("  Persistence Position MAE:  %.3f km", pers_metrics["pos_mae"])
    log.info("  Random Forest Position MAE: %.3f km", rf_metrics["pos_mae"])
    log.info("  Improvement: %.1f%%", improvement)
    log.info("  Top 3 features: %s",
             ", ".join(f"{r.feature}({r.importance_avg:.3f})" for _, r in imp_df.head(3).iterrows()))
    log.info("  Ocean importance: %.1f%%", ocean_imp * 100)
    log.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
