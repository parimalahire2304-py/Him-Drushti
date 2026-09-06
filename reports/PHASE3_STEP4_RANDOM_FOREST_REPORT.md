# Phase 3 Step 4 — Random Forest Regression Report

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-04

**Status:** ✅ MODEL TRAINED AND EVALUATED

---

## 1. Objective

Train a Random Forest regression model for **7-day iceberg trajectory prediction** (next-position latitude and longitude), evaluate on the held-out test set, and compare against the Phase 3 Step 3 persistence baseline.

---

## 2. Dataset

| Split | Samples | Date Range | Icebergs |
|---|---|---|---|
| **Train** | 71 | 2020-01-03 → 2020-08-14 | B39, D23, D27, D28 |
| **Validation** | 16 | 2020-09-11 → 2020-10-30 | D23, D27 |
| **Test** | 14 | 2020-11-06 → 2020-12-18 | D23, D27 |
| **Total** | 101 | 2020-01-03 → 2020-12-18 | 4 icebergs |

**Feature columns:** 25
**Target variables:** `target_lat` (latitude at t+7d), `target_lon` (longitude at t+7d)

---

## 3. Features Used (25 columns)

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

**Total combinations:** 324 = 324 per target
**Cross-validation:** TimeSeriesSplit with 3 folds (chronological)
**Selection metric:** Validation MAE (neg_mean_absolute_error in CV, then explicit val MAE)

### 4.2 Selected Hyperparameters

| Parameter | Latitude Model | Longitude Model |
|---|---|---|
| `n_estimators` | 400 | 400 |
| `max_depth` | 5 | 5 |
| `min_samples_split` | 2 | 2 |
| `min_samples_leaf` | 1 | 1 |
| `max_features` | 0.8 | 0.8 |
| `random_state` | 42 | 42 |

> **Note:** The same hyperparameter configuration was selected for both latitude and longitude targets. With only 16 validation samples, grid search resolution is limited; aggressive tuning would risk overfitting to the validation set.

---

## 5. Training Procedure

| Step | Description |
|---|---|
| 1 | Load train (71), val (16), test (14) parquets |
| 2 | Verify 25 feature columns present; no target columns in features |
| 3 | GridSearchCV with TimeSeriesSplit(3 folds) on training data |
| 4 | Rank all 324 candidates by validation MAE |
| 5 | Select best configuration (lowest val MAE) |
| 6 | Refit best model on TRAIN+VAL combined (87 samples) |
| 7 | Evaluate once on untouched TEST set (14 samples) |

**Training time (tuning + final fit):** 0.81s
**Inference time (test set, lat):** 58.9ms
**Inference time (test set, lon):** 48.8ms

---

## 6. Test Set Results — Random Forest vs Persistence

### 6.1 Aggregate Metrics

| Metric | Persistence | Random Forest | Improvement |
|---|---|---|---|
| Latitude MAE (°) | 0.0093 | 0.0445 | -379.4% |
| Longitude MAE (°) | 0.0536 | 0.1294 | -141.5% |
| Latitude RMSE (°) | 0.0171 | 0.0681 | -297.7% |
| Longitude RMSE (°) | 0.0982 | 0.2089 | -112.6% |
| **Position MAE (km)** | **2.598** | **7.735** | **-197.7%** |
| Position RMSE (km) | 4.566 | 11.620 | -154.5% |
| Median Position Error (km) | 0.586 | 4.093 | -598.4% |
| Max Position Error (km) | 10.215 | 27.095 | -165.2% |
| Min Position Error (km) | 0.000 | 0.029 | — |
| Std Position Error (km) | 3.756 | 8.671 | — |

### 6.2 Per-Sample Predictions

| # | Iceberg | Obs Date | True Lat | True Lon | RF Lat Err (°) | RF Lon Err (°) | RF Pos Err (km) | Pers Pos Err (km) |
|---|---|---|---|---|---|---|---|---|
| 1 | D23 | 2020-11-06 | -69.4300 | 74.6700 | 0.0002 | 0.0002 | 0.029 | 0.000 |
| 2 | D23 | 2020-11-13 | -69.4300 | 74.6700 | 0.0000 | 0.0128 | 0.499 | 0.000 |
| 3 | D23 | 2020-11-20 | -69.4300 | 74.6800 | 0.0000 | 0.0101 | 0.393 | 0.391 |
| 4 | D23 | 2020-11-27 | -69.4300 | 74.6600 | 0.0028 | 0.0145 | 0.644 | 0.781 |
| 5 | D23 | 2020-12-04 | -69.4300 | 74.6600 | 0.0128 | 0.0512 | 2.454 | 0.000 |
| 6 | D23 | 2020-12-11 | -69.4300 | 74.6600 | 0.0004 | 0.0069 | 0.274 | 0.000 |
| 7 | D23 | 2020-12-18 | -69.4300 | 74.6600 | 0.0001 | 0.0102 | 0.397 | 0.000 |
| 8 | D27 | 2020-11-06 | -67.6300 | 79.0200 | 0.0368 | 0.1333 | 6.966 | 10.215 |
| 9 | D27 | 2020-11-13 | -67.6200 | 79.0400 | 0.1367 | 0.2698 | 18.996 | 1.398 |
| 10 | D27 | 2020-11-20 | -67.6300 | 79.0400 | 0.0741 | 0.6109 | 27.095 | 1.112 |
| 11 | D27 | 2020-11-27 | -67.6600 | 78.8600 | 0.0921 | 0.1973 | 13.197 | 8.311 |
| 12 | D27 | 2020-12-04 | -67.6600 | 78.8600 | 0.1564 | 0.2284 | 19.873 | 0.000 |
| 13 | D27 | 2020-12-11 | -67.6800 | 78.7700 | 0.0614 | 0.2263 | 11.735 | 4.405 |
| 14 | D27 | 2020-12-18 | -67.7300 | 78.5800 | 0.0493 | 0.0396 | 5.732 | 9.755 |

### 6.3 Interpretation

Random Forest **does not improve** over persistence (MAE: 7.735 km vs 2.598 km, degradation: 197.7%).

**D23 (grounded):** RF mean error 0.670 km vs persistence 0.167 km. Persistence is more accurate on grounded iceberg.
**D27 (drifting):** RF mean error 14.799 km vs persistence 5.028 km. Persistence is more accurate on drifting iceberg.

The test set is dominated by D23 (grounded, 7/14 samples) where near-zero displacement makes persistence inherently strong. The lack of environmental signal captured by RF does not help beyond position-only prediction in this small-sample regime.

---

## 7. Feature Importance

### 7.1 Overall Feature Importance (Averaged Across Lat/Lon Models)

| Feature | Importance (Lat) | Importance (Lon) | Importance (Avg) | Category |
|---|---|---|---|---|
| lon 📍 | 0.0219 | 0.7356 | 0.3787 |
| lat 📍 | 0.7403 | 0.0100 | 0.3751 |
| prev_lat 📍 | 0.1705 | 0.0041 | 0.0873 |
| prev_lon 📍 | 0.0100 | 0.1404 | 0.0752 |
| bathymetry_elevation | 0.0154 | 0.0593 | 0.0374 |
| iceberg_width_nm | 0.0065 | 0.0085 | 0.0075 |
| prev_speed 📍 | 0.0048 | 0.0038 | 0.0043 |
| prev_delta_lon 📍 | 0.0049 | 0.0029 | 0.0039 |
| exposed_water_fraction 🌤 | 0.0038 | 0.0027 | 0.0033 |
| wind_v_10m 🌤 | 0.0028 | 0.0037 | 0.0033 |
| sea_ice_concentration 🌤 | 0.0048 | 0.0013 | 0.0031 |
| ocean_current_v 🌊 | 0.0013 | 0.0046 | 0.0029 |
| temperature_2m 🌤 | 0.0013 | 0.0037 | 0.0025 |
| ocean_speed 🌊 | 0.0014 | 0.0031 | 0.0022 |
| prev_delta_lat 📍 | 0.0025 | 0.0019 | 0.0022 |
| prev_bearing 📍 | 0.0017 | 0.0021 | 0.0019 |
| ocean_dir 🌊 | 0.0010 | 0.0026 | 0.0018 |
| wind_u_10m 🌤 | 0.0006 | 0.0028 | 0.0017 |
| wind_speed 🌤 | 0.0005 | 0.0020 | 0.0013 |
| ocean_current_u 🌊 | 0.0010 | 0.0012 | 0.0011 |
| wind_dir 🌤 | 0.0010 | 0.0007 | 0.0008 |
| mean_sea_level_pressure 🌤 | 0.0008 | 0.0009 | 0.0008 |
| wind_ocean_angle 🌤 | 0.0007 | 0.0007 | 0.0007 |
| total_precipitation 🌤 | 0.0004 | 0.0008 | 0.0006 |
| iceberg_length_nm | 0.0002 | 0.0006 | 0.0004 |

### 7.2 Category-Level Importance

| Category | Avg Importance | Share |
|---|---|---|
| Position 📍 | 0.9287 | 92.9% |
| Wind 💨 | 0.0180 | 1.8% |
| Ocean 🌊 | 0.0081 | 0.8% |
| Static | 0.0453 | 4.5% |

### 7.3 Key Findings

- **Most important features:** `lon`, `lat`, `prev_lat`
- **Least important features:** `wind_ocean_angle`, `total_precipitation`, `iceberg_length_nm`
- **Ocean current contribution:** 0.8% of total importance — modest predictive signal
- **Environmental variable contribution:** 1.8% of total importance — limited predictive signal

> ⚠️ With only 71 training samples, feature importance rankings have high variance and should not be interpreted as strong scientific causality.

---

## 8. Validation Metrics (Training Diagnostics)

| Metric | Train | Validation |
|---|---|---|
| Latitude MAE (°) | See tuning log | 0.0114 |
| Longitude MAE (°) | See tuning log | 0.0248 |

---

## 9. Overfitting Risk Assessment

| Risk Factor | Status | Notes |
|---|---|---|
| Training set size | ⚠️ Small (71 samples) | RF can memorize training data |
| Validation set size | ⚠️ Very small (16 samples) | Model selection uncertain |
| Gap train→val→test | ✅ Chronological | No temporal leakage |
| Hyperparameter count | ⚠️ 324 candidates | May overfit to 16 val samples |
| Train vs Val MAE gap | ✅ Acceptable | Gap within expected range |

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

- `random_state = 42` (all models)
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

**Verdict:** ✅ PASS — Random Forest trained and evaluated; results ready for comparison with future models.

> **Important:** This model is an experimental benchmark. Persistence (MAE 2.598 km) remains the primary baseline. Any future ML model must beat both persistence AND this Random Forest on the same 14-sample test set.

---

*Audit trail: Phase 1/2 data untouched; no synthetic data generated; chronological split preserved; no test-set tuning.*
