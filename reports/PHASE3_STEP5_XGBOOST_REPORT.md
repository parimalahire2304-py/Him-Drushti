# Phase 3 Step 5 — XGBoost Regression Report

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-04

**Status:** ✅ MODEL TRAINED AND EVALUATED

---

## 1. Objective

Train an XGBoost regression model for **7-day iceberg trajectory prediction** (next-position latitude and longitude), evaluate on the held-out test set, and compare against the persistence baseline and Random Forest.

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

## 3. XGBoost Methodology

| Step | Description |
|---|---|
| 1 | Load train (71), val (16), test (14) parquets |
| 2 | Verify 25 feature columns; no target leakage |
| 3 | Grid search over 1944 hyperparameter combos on training data |
| 4 | TimeSeriesSplit(3) CV on training set; evaluate on validation set |
| 5 | Select best configuration (lowest validation MAE) |
| 6 | Refit on TRAIN+VAL (87 samples) |
| 7 | Evaluate once on untouched TEST set (14 samples) |

> **NaN handling:** XGBoost natively handles missing values (prev_* NaN for first trajectory step); no imputation applied.

---

## 4. Hyperparameter Configuration

### 4.1 Search Space

| Parameter | Values Searched |
|---|---|
| `n_estimators` | 50, 100, 200 |
| `max_depth` | 3, 4, 5 |
| `learning_rate` | 0.01, 0.05, 0.1 |
| `min_child_weight` | 3, 5, 10 |
| `subsample` | 0.7, 0.8 |
| `colsample_bytree` | 0.7, 0.8 |
| `reg_alpha` | 0.0, 0.1, 1.0 |
| `reg_lambda` | 1.0, 5.0 |

**Total combinations:** 1944
**CV strategy:** TimeSeriesSplit(3 folds) on training data
**Selection:** Validation MAE (16 samples)

### 4.2 Selected Hyperparameters

| Parameter | Value |
|---|---|
| `n_estimators` | 200 |
| `max_depth` | 4 |
| `learning_rate` | 0.1 |
| `min_child_weight` | 3 |
| `subsample` | 0.8 |
| `colsample_bytree` | 0.7 |
| `reg_alpha` | 0.0 |
| `reg_lambda` | 1.0 |
| `objective` | reg:squarederror |
| `random_state` | 42 |

> The same hyperparameter configuration is used for both latitude and longitude targets.

### 4.3 Training Diagnostics

| Metric | Train | Validation |
|---|---|---|
| Latitude MAE (°) | 0.0010 | 0.0010 |
| Longitude MAE (°) | 0.0116 | 0.0127 |
| Position MAE (km) | 0.528 | 0.546 |

---

## 5. Test Set Results — All Models Comparison

### 5.1 Aggregate Metrics

| Metric | Persistence | Random Forest | XGBoost | XGB vs Pers | XGB vs RF |
|---|---|---|---|---|---|
| Latitude MAE (°) | 0.0093 | 0.0445 | **0.0406** | -337.6% | +8.7% |
| Longitude MAE (°) | 0.0536 | 0.1294 | **0.5676** | -959.5% | -338.7% |
| Latitude RMSE (°) | 0.0171 | 0.0681 | **0.0619** | -261.6% | +9.1% |
| Longitude RMSE (°) | 0.0982 | 0.2089 | **0.7448** | -658.2% | -256.5% |
| **Position MAE (km)** | **2.598** | **7.735** | **25.080** | **-865.5%** | **-224.3%** |
| Position RMSE (km) | 4.566 | 11.620 | 32.155 | -604.2% | -176.7% |
| Median Pos Err (km) | 0.586 | 4.093 | 23.820 | -3964.6% | -482.0% |
| Max Pos Err (km) | 10.215 | 27.095 | 57.918 | -467.0% | -113.8% |
| Min Pos Err (km) | 0.000 | 0.029 | 0.171 | — | — |
| Std Pos Err (km) | 3.756 | 8.671 | 20.124 | — | — |

### 5.2 Per-Sample Predictions

| # | Iceberg | Obs Date | True Lat | True Lon | XGB Pos (km) | RF Pos (km) | Pers Pos (km) |
|---|---|---|---|---|---|---|---|
| 1 | D23 | 2020-11-06 | -69.4300 | 74.6700 | 0.772 | 0.029 | 0.000 |
| 2 | D23 | 2020-11-13 | -69.4300 | 74.6700 | 0.171 | 0.499 | 0.000 |
| 3 | D23 | 2020-11-20 | -69.4300 | 74.6800 | 0.351 | 0.393 | 0.391 |
| 4 | D23 | 2020-11-27 | -69.4300 | 74.6600 | 1.205 | 0.644 | 0.781 |
| 5 | D23 | 2020-12-04 | -69.4300 | 74.6600 | 14.674 | 2.454 | 0.000 |
| 6 | D23 | 2020-12-11 | -69.4300 | 74.6600 | 13.684 | 0.274 | 0.000 |
| 7 | D23 | 2020-12-18 | -69.4300 | 74.6600 | 12.505 | 0.397 | 0.000 |
| 8 | D27 | 2020-11-06 | -67.6300 | 79.0200 | 43.717 | 6.966 | 10.215 |
| 9 | D27 | 2020-11-13 | -67.6200 | 79.0400 | 45.766 | 18.996 | 1.398 |
| 10 | D27 | 2020-11-20 | -67.6300 | 79.0400 | 57.918 | 27.095 | 1.112 |
| 11 | D27 | 2020-11-27 | -67.6600 | 78.8600 | 40.964 | 13.197 | 8.311 |
| 12 | D27 | 2020-12-04 | -67.6600 | 78.8600 | 48.434 | 19.873 | 0.000 |
| 13 | D27 | 2020-12-11 | -67.6800 | 78.7700 | 37.995 | 11.735 | 4.405 |
| 14 | D27 | 2020-12-18 | -67.7300 | 78.5800 | 32.965 | 5.732 | 9.755 |

### 5.3 Per-Iceberg Breakdown

| Iceberg | Samples | XGB MAE (km) | RF MAE (km) | Pers MAE (km) |
|---|---|---|---|---|
| D23 | 7 | 6.195 | 0.670 | 0.167 |
| D27 | 7 | 43.966 | 14.799 | 5.028 |

### 5.4 Interpretation

XGBoost **does not improve** over persistence (MAE: 25.080 km vs 2.598 km, degradation: 865.5%).
XGBoost **does not improve** over Random Forest (MAE: 25.080 km vs 7.735 km).
**D23:** XGB 6.195 km, RF 0.670 km, Pers 0.167 km → best: Persistence
**D27:** XGB 43.966 km, RF 14.799 km, Pers 5.028 km → best: Persistence

---

## 6. Feature Importance

### 6.1 Overall Feature Importance (Averaged Across Lat/Lon Models)

| Feature | XGB Imp (Lat) | XGB Imp (Lon) | XGB Avg | RF Avg |
|---|---|---|---|---|
| lat 📍 | 0.6506 | 0.0206 | 0.3356 |
| prev_lon 📍 | 0.0093 | 0.4585 | 0.2339 |
| lon 📍 | 0.0549 | 0.3846 | 0.2198 |
| prev_lat 📍 | 0.1627 | 0.0149 | 0.0888 |
| bathymetry_elevation  | 0.0216 | 0.0236 | 0.0226 |
| prev_bearing 📍 | 0.0316 | 0.0041 | 0.0179 |
| temperature_2m 🌤 | 0.0009 | 0.0232 | 0.0120 |
| wind_dir 🌤 | 0.0005 | 0.0228 | 0.0116 |
| sea_ice_concentration 🌤 | 0.0171 | 0.0056 | 0.0114 |
| wind_v_10m 🌤 | 0.0005 | 0.0197 | 0.0101 |
| prev_delta_lat 📍 | 0.0159 | 0.0031 | 0.0095 |
| ocean_current_v 🌊 | 0.0106 | 0.0028 | 0.0067 |
| ocean_speed 🌊 | 0.0104 | 0.0010 | 0.0057 |
| prev_delta_lon 📍 | 0.0029 | 0.0034 | 0.0031 |
| ocean_current_u 🌊 | 0.0046 | 0.0004 | 0.0025 |
| wind_u_10m 🌤 | 0.0015 | 0.0026 | 0.0020 |
| prev_speed 📍 | 0.0006 | 0.0034 | 0.0020 |
| iceberg_length_nm  | 0.0018 | 0.0013 | 0.0016 |
| ocean_dir 🌊 | 0.0002 | 0.0016 | 0.0009 |
| total_precipitation 🌤 | 0.0007 | 0.0011 | 0.0009 |
| wind_speed 🌤 | 0.0003 | 0.0008 | 0.0006 |
| wind_ocean_angle 🌤 | 0.0003 | 0.0003 | 0.0003 |
| mean_sea_level_pressure 🌤 | 0.0002 | 0.0003 | 0.0003 |
| iceberg_width_nm  | 0.0003 | 0.0000 | 0.0002 |
| exposed_water_fraction 🌤 | 0.0001 | 0.0002 | 0.0001 |

### 6.2 Category-Level Importance

| Category | XGB Importance | Share |
|---|---|---|
| Position 📍 | 0.9106 | 91.1% |
| Environment 🌤 | 0.0494 | 4.9% |
| Ocean 🌊 | 0.0157 | 1.6% |
| Static | 0.0243 | 2.4% |

### 6.3 Key Findings

- **Most important features:** `lat`, `prev_lon`, `lon`
- **Least important features:** `mean_sea_level_pressure`, `iceberg_width_nm`, `exposed_water_fraction`
- **Ocean current contribution:** 1.6% — modest predictive signal
- **Environmental variable contribution:** 4.9% — limited predictive signal

---

## 7. Performance Metrics

| Metric | XGBoost |
|---|---|
| Training time (tuning + final fit) | 554.25s |
| Inference time (test, lat) | 1.2ms |
| Inference time (test, lon) | 1.0ms |
| Model file size (lat) | ~204 KB |
| Model file size (lon) | ~157 KB |

---

## 8. Overfitting Risk Assessment

| Risk Factor | Status | Notes |
|---|---|---|
| Training set size (71 samples) | ⚠️ Small | XGBoost may memorize training patterns |
| Validation set size (16 samples) | ⚠️ Very small | Model selection is noisy |
| Chronological split | ✅ No leakage | Train < Val < Test |
| Regularization applied | ✅ | reg_alpha, reg_lambda, min_child_weight constrain complexity |
| Max depth constrained | ✅ | Depth ≤ 4 limits tree complexity |
| Boosting rounds | ✅ Conservative | n_estimators = 200, lr = 0.1 |

**Overfitting risk:** MODERATE — treated as experimental benchmark.

---

## 9. Small-Dataset Limitations

| Limitation | Impact |
|---|---|
| 71 training samples | Limited generalization |
| 16 validation samples | Noisy hyperparameter selection |
| 14 test samples | Wide confidence intervals on metrics |
| Only D23+D27 in test | Cannot evaluate on fast-drifting icebergs |
| D23 grounded dominance | 7/14 test samples near-zero displacement |

---

## 10. Reproducibility

- `random_state = 42`
- XGBoost `verbosity = 0`, `objective = reg:squarederror`
- Feature order identical across all splits
- Chronological split preserved
- No test data used during tuning
- All code: `scripts/ml/train_xgboost.py`

---

## 11. Files Saved

| File | Description |
|---|---|
| `data/processed/ml/models/xgboost_latitude.json` | XGBoost model for latitude |
| `data/processed/ml/models/xgboost_longitude.json` | XGBoost model for longitude |
| `data/processed/ml/models/xgb_model_metadata.json` | Hyperparameters, metrics, importance |

---

## 12. Validation Checks

| Check | Status |
|---|---|
| Correct train/val/test files used | ✅ |
| Test set = exactly 14 samples | ✅ |
| No test data in tuning | ✅ |
| No future info in features | ✅ |
| No target leakage | ✅ |
| Phase 1/2 data unchanged | ✅ |
| Feature stack unchanged | ✅ |
| Valid lat/lon predictions | ✅ |
| Metrics on same 14-sample test set | ✅ |
| Models loadable | ✅ |
| Feature importance matches model | ✅ |
| Report numbers match computed results | ✅ |

---

## 13. Final Assessment

| Check | Status |
|---|---|
| Correct files | ✅ |
| No test leakage | ✅ |
| No future info | ✅ |
| Valid predictions | ✅ |
| Metrics match | ✅ |

**Verdict:** ✅ PASS — XGBoost trained, evaluated, and compared. Results ready for next model or final analysis.

> **Important:** Persistence remains the strongest baseline on this test set (2.598 km). Any future model must beat persistence on the same 14-sample test set.

---

*Audit trail: Phase 1/2 data untouched; no synthetic data; chronological split preserved; no test-set tuning.*
