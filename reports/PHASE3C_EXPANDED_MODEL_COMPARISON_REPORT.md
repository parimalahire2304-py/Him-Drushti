# Phase 3C — Expanded Model Comparison Report

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-05

**Status:** ✅ ALL MODELS TRAINED, EVALUATED, VALIDATED

---

## 1. Executive Summary

This report compares the performance of four models on the **expanded 54-sample test set** (East Prydz Bay, 2025) derived from the Phase 3B verified dataset (451 supervised pairs, 8 icebergs, 7 years, chronological train/val/test split):

| Model | Overall Position MAE (km) | Drifting MAE (km) | Grounded MAE (km) | C39 Zero-Shot MAE (km) |
|---|---|---|---|---|
| **Persistence** | **9.05** | **20.30** | **0.05** | **15.72** |
| Random Forest | 16.66 | 36.06 | 1.14 | 43.86 |
| XGBoost | 13.82 | 27.62 | 2.78 | 29.20 |
| LSTM (17 seq) | 34.97 | 81.55 | 2.36 | 54.49 |

**Key finding:** **No ML model beats the persistence baseline** on any subgroup (overall, drifting, grounded, or C39 zero-shot).

---

## 2. Dataset & Experimental Design

### 2.1 Expanded Dataset (Phase 3B Verified)
- **Total supervised pairs:** 451 (vs. 101 original)
- **Icebergs:** 8 (B39, C18B, C39, D21B, D22, D23, D27, D28) (vs. 4 original)
- **Years:** 7 (2016, 2017, 2019, 2020, 2021, 2024, 2025) (vs. 1 original)
- **Drifting / Grounded:** 142 / 309 (D23 grounded, mean 7d disp 0.08 km)
- **Split:** Train 342 (2016–2021) / Val 55 (2024) / Test 54 (2025)
- **Chronological integrity:** train end 2021-12-31 < val start 2024-01-04 < test start 2025-01-16
- **C39 zero-shot:** 9 test samples, 0 train/val

### 2.2 Test Set Composition
| Iceberg | Type | n (flat) | n (LSTM seq) |
|---|---|---|---|
| D23 | Grounded | 30 | 10 |
| C18B | Drifting | 15 | 7 |
| C39 | Drifting (zero-shot) | 9 | 4 |

### 2.3 Evaluation Metrics (shared module)
All models evaluated with identical metric definitions via `eval_metrics_expanded.py`:
- Latitude MAE / RMSE (°)
- Longitude MAE / RMSE (°)
- **Position MAE / RMSE (km)** — primary
- Median / Max / Min / Std position error (km)
- Final-position error (km) — mean error at each trajectory's last step
- Trajectory error (km) — mean of per-trajectory mean position error
- Mean displacement error (km) — mean \|predicted disp − true disp\|

---

## 3. Model Configurations

### 3.1 Persistence Baseline
- **Rule:** predict(t+7) = position(t)
- No training, deterministic
- Inference: <1 ms

### 3.2 Random Forest (adapted from Phase 3 Step 4)
- Two independent `RandomForestRegressor` (lat/lon)
- **Hyperparameter search:** 324 combos, TimeSeriesSplit(3), select by val MAE
- **Selected (lat):** `n_estimators=100, max_depth=5, min_samples_split=2, min_samples_leaf=1, max_features=0.5`
- **Selected (lon):** `n_estimators=100, max_depth=10, min_samples_split=10, min_samples_leaf=2, max_features=0.5`
- **Retrained on:** TRAIN+VAL (397 samples)
- **Training time:** 0.37 s; **Inference:** ~3 ms/test

### 3.3 XGBoost (adapted from Phase 3 Step 5)
- Two independent `XGBRegressor` (lat/lon)
- **Hyperparameter search:** 1,944 combos × explicit train→val + TimeSeriesSplit(3)
- **Selected (lat):** `n_estimators=200, max_depth=3, learning_rate=0.05, min_child_weight=3, subsample=0.8, colsample_bytree=0.7, reg_alpha=0.0, reg_lambda=5.0`
- **Selected (lon):** `n_estimators=50, max_depth=4, learning_rate=0.1, min_child_weight=10, subsample=0.8, colsample_bytree=0.8, reg_alpha=1.0, reg_lambda=5.0`
- **Retrained on:** TRAIN+VAL (397 samples)
- **Training time:** ~0.15 s; **Tuning time:** ~29 min total; **Inference:** ~2 ms/test

### 3.4 LSTM (adapted from Phase 3 Step 6)
- Two independent `IcebergLSTM` (lat/lon): input=25, hidden=32, layers=1, dropout=0.2, fc 32→16→1
- **Sequence length:** 2 (14-day context), validated from Phase 3 Step 6
- **Sequences:** Train 311 / Val 17 / Test 17 (C39: 4 test sequences)
- **Scaling:** StandardScaler fit on TRAIN sequences only; NaN imputed with train mean
- **Early stopping:** val loss, patience 10, ReduceLROnPlateau factor 0.5
- **Parameters per model:** ~8,097
- **Training time:** ~38 s total; **Inference:** ~40 ms/test (17 sequences)

---

## 4. Detailed Metrics

### 4.1 Overall (54 flat-test samples; LSTM: 17 sequences)

| Metric | Persistence | Random Forest | XGBoost | LSTM |
|---|---:|---:|---:|---:|
| **Position MAE (km)** | **9.05** | 16.66 | 13.82 | 34.97 |
| Position RMSE (km) | 24.00 | 33.34 | 26.83 | 61.31 |
| Position Median (km) | 0.00 | 1.95 | 3.95 | 3.40 |
| Position Max (km) | 121.85 | 133.51 | 131.11 | 182.07 |
| Final-position error (km) | 15.63 | 30.93 | 23.24 | 71.37 |
| Trajectory error (km) | 12.94 | 25.46 | 19.55 | 58.16 |
| Mean displacement error (km) | 9.05 | 11.64 | 9.63 | 19.93 |
| Latitude MAE (°) | 0.059 | 0.103 | 0.085 | 0.264 |
| Longitude MAE (°) | 0.110 | 0.181 | 0.147 | 0.354 |

### 4.2 Drifting Only (24 samples; LSTM: 7 sequences)
*Icebergs: C18B (15), C39 (9)*

| Metric | Persistence | Random Forest | XGBoost | LSTM |
|---|---:|---:|---:|---:|
| **Position MAE (km)** | **20.30** | 36.06 | 27.62 | 81.55 |
| Position RMSE (km) | 36.00 | 49.98 | 40.10 | 95.50 |
| Median (km) | 3.67 | 36.36 | 20.20 | 62.22 |
| Max (km) | 121.85 | 133.51 | 131.11 | 182.07 |
| Final-position error (km) | 23.44 | 45.67 | 33.75 | 106.00 |
| Trajectory error (km) | 19.39 | 37.62 | 27.94 | 86.06 |

### 4.3 Grounded Only (30 samples; LSTM: 10 sequences)
*Iceberg: D23*

| Metric | Persistence | Random Forest | XGBoost | LSTM |
|---|---:|---:|---:|---:|
| **Position MAE (km)** | **0.05** | 1.14 | 2.78 | 2.36 |
| Position RMSE (km) | 0.17 | 1.27 | 3.05 | 2.55 |
| Median (km) | 0.00 | 1.11 | 2.28 | 2.34 |
| Max (km) | 0.78 | 2.69 | 5.79 | 4.21 |

### 4.4 C39 Zero-Shot (9 samples; LSTM: 4 sequences)

| Metric | Persistence | Random Forest | XGBoost | LSTM |
|---|---:|---:|---:|---:|
| **Position MAE (km)** | **15.72** | 43.86 | 29.20 | 54.49 |
| Position RMSE (km) | 23.87 | 44.99 | 31.77 | 56.31 |
| Median (km) | 5.83 | 39.39 | 26.77 | 61.84 |
| Max (km) | 57.37 | 65.50 | 59.33 | 64.35 |

---

## 5. Feature Importance Comparison

| Feature | RF Importance | XGB Importance | Category |
|---|---:|---:|---|
| iceberg_width_nm | 0.204 | **0.462** | Static |
| lon | 0.308 | 0.104 | Position |
| lat | 0.257 | 0.203 | Position |
| prev_lon | 0.099 | 0.065 | Position |
| bathymetry_elevation | 0.053 | 0.035 | Static |
| prev_lat | 0.046 | 0.074 | Position |
| ... | ... | ... | ... |

**Category importance shares:**

| Category | RF | XGBoost |
|---|---:|---:|
| Position 📍 | 66.7% | 44.8% |
| Static | 26.1% | 49.7% |
| Wind/Atmosphere 🌤 | 5.2% | 3.2% |
| Ocean 🌊 | 2.0% | 2.3% |

> ⚠️ With only 342 training samples, importance rankings have high variance and **must not** be interpreted as causal evidence.

---

## 6. Computational Cost

| Model | Training Time | Inference Time (test set) |
|---|---:|---:|
| Persistence | 0 s | <1 ms |
| Random Forest | 0.37 s | ~3 ms |
| XGBoost | 0.15 s (+ 29 min tuning) | ~2 ms |
| LSTM | 38 s | ~40 ms (17 sequences) |

---

## 7. Model Comparison Verdicts

| Question | Answer | Evidence |
|---|---|---|
| **Best overall model?** | **Persistence** | 9.05 km MAE |
| **Best drifting model?** | **Persistence** | 20.30 km MAE |
| **Does RF beat persistence?** | **NO** | RF 16.66 vs Pers 9.05 (−84%) |
| **Does XGBoost beat RF?** | **YES** | XGB 13.82 vs RF 16.66 (+17% improvement) |
| **Does LSTM beat XGBoost?** | **NO** | LSTM 34.97 vs XGB 13.82 (−153%) |
| **Does any model improve drifting over persistence?** | **NO** | Best drifting: XGB 27.62 > Pers 20.30 |
| **Does C39 zero-shot indicate useful generalization?** | **NO** | All models >> persistence on C39 |

---

## 8. Statistical Caution

- **Test set small:** 54 flat samples (24 drifting, 30 grounded); LSTM evaluated on only 17 sequences.
- **No significance testing performed** — confidence intervals not computed; do **not** claim statistical significance.
- **Grounded iceberg dominance** in test (30/54 = 56%) biases overall metrics toward persistence.
- **Drifting icebergs underrepresented** in training for the expanded 2025 test conditions.
- Feature importance rankings are unstable at this sample size.

---

## 9. Validation Summary (19/19 PASS)

All integrity checks passed:

| Check | Status |
|---|---|
| 451 pairs preserved | ✅ |
| 8 iceberg IDs, 7 years | ✅ |
| 142 drifting / 309 grounded | ✅ |
| Chronological split train<val<test | ✅ |
| No future positions in features | ✅ |
| No future environment in features | ✅ |
| C39 zero-shot isolated (0/0/9) | ✅ |
| No duplicates | ✅ |
| Feature schema = Phase 3 (39 cols, 25 features) | ✅ |
| Original Phase 3 dataset unchanged | ✅ |
| Predictions finite | ✅ |
| Models reload & reproduce predictions | ✅ |
| Reported metrics = recomputed metrics | ✅ |

---

## 10. Files Produced

```
data/processed/ml/expanded/
├── models/
│   ├── persistence_metrics.json
│   ├── persistence_predictions.csv
│   ├── random_forest_latitude.joblib
│   ├── random_forest_longitude.joblib
│   ├── rf_expanded_metadata.json
│   ├── rf_predictions.csv
│   ├── xgboost_latitude.json
│   ├── xgboost_longitude.json
│   ├── xgb_expanded_metadata.json
│   ├── xgb_predictions.csv
│   ├── lstm_latitude.pt
│   ├── lstm_longitude.pt
│   ├── lstm_feature_scaler.joblib
│   ├── lstm_scaler_lat.joblib
│   ├── lstm_scaler_lon.joblib
│   ├── lstm_expanded_metadata.json
│   ├── lstm_predictions.csv
│   ├── lstm_training_history.json
│   └── comparison_summary.json
```

Scripts created:
- `scripts/ml/baseline_expanded.py`
- `scripts/ml/train_random_forest_expanded.py`
- `scripts/ml/train_xgboost_expanded.py`
- `scripts/ml/train_lstm_expanded.py`
- `scripts/ml/eval_metrics_expanded.py`
- `scripts/ml/compare_models_expanded.py`
- `scripts/ml/validate_phase3c.py`

---

## 11. Conclusion & Recommendation

**STATUS: COMPLETE**

| Field | Value |
|---|---|
| **BEST OVERALL MODEL** | Persistence |
| **BEST DRIFTING MODEL** | Persistence |
| **PERSISTENCE PERFORMANCE** | 9.05 km pos_mae (overall) / 20.30 km (drifting) |
| **RF PERFORMANCE** | 16.66 km pos_mae (overall) / 36.06 km (drifting) |
| **XGBOOST PERFORMANCE** | 13.82 km pos_mae (overall) / 27.62 km (drifting) |
| **LSTM PERFORMANCE** | 34.97 km pos_mae (overall, 17 seq) / 81.55 km (drifting) |
| **C39 ZERO-SHOT RESULT** | Persistence 15.72 km; all ML models worse |
| **DOES ML BEAT PERSISTENCE?** | **NO** |

**Recommendation:**  
At the current sample scale (342 training pairs), with grounded-iceberg dominance and limited drifting trajectory diversity, **the persistence baseline remains the most reliable operational predictor**. Further ML investment should focus on:

1. Acquiring more drifting-iceberg trajectories (especially fast-drifting regimes like B39/D28)
2. Extending the training window to capture more seasonal variability
3. Exploring whether ocean current data (GLORYS) materially improves drift prediction once available
4. Re-evaluating when training samples exceed ~1,000 drifting pairs

**No CNN/Transformer/additional data collection initiated per instruction.**

---

*Audit trail: Phase 1/2 data untouched; original Phase 3 dataset immutable; expanded dataset isolated in `data/processed/ml/expanded/`; no test leakage; all models evaluated once on untouched test set; validation suite 19/19 PASS.*