# Phase 3 Step 3 — Baseline Iceberg Trajectory Models Report

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-04

**Status:** ✅ BASELINE EVALUATION COMPLETE

---

## 1. Objective

Establish transparent, deterministic baselines for 7-day iceberg trajectory prediction.  
These baselines are the reference against which all subsequent ML models are compared.  
No model training or fitting occurs — both baselines are analytical rules.

---

## 2. Dataset Used

| Property | Value |
|---|---|
| Source | `data/processed/ml/test.parquet` (Phase 3 Step 2) |
| Samples | 14 (held-out test set) |
| Icebergs | D23 (grounded), D27 (drifting) |
| Date range | 2020-11-06 → 2020-12-25 |
| Prediction horizon | 7 days |
| Split boundary | test obs_date ≥ 2020-10-31 |

---

## 3. Methodology

### 3.1 Model A — Persistence Baseline

**Rule:** Predict the iceberg's position at *t + 7 days* as its current position at time *t*.

```
pred_lat(t+7) = lat(t)
pred_lon(t+7) = lon(t)
```

**Assumption:** The iceberg does not move over the 7-day horizon.  
**Physical basis:** Approximation for grounded or very slow-drifting icebergs.  
**No training required.**

### 3.2 Model B — Linear Motion Extrapolation Baseline

**Rule:** Extrapolate the previous 7-day displacement vector forward by 7 days.

```
prev_delta_lat = lat(t) − lat(t−7)     # observed displacement in the prior 7 days
prev_delta_lon = lon(t) − lon(t−7)

pred_lat(t+7) = lat(t) + prev_delta_lat
pred_lon(t+7) = lon(t) + prev_delta_lon
```

**Assumption:** The iceberg continues at the same velocity it had in the previous 7-day step.  
**Physical basis:** Constant-velocity (inertial) extrapolation; captures drift momentum.  
**No training required.** Uses only `prev_delta_lat`, `prev_delta_lon`, `lat`, `lon` — all available at time *t*.

---

## 4. Metric Definitions

| Metric | Formula | Unit |
|---|---|---|
| **Latitude MAE** | mean(|pred_lat − actual_lat|) | degrees |
| **Latitude RMSE** | sqrt(mean((pred_lat − actual_lat)²)) | degrees |
| **Longitude MAE** | mean(|pred_lon − actual_lon|) | degrees |
| **Longitude RMSE** | sqrt(mean((pred_lon − actual_lon)²)) | degrees |
| **Position MAE** | mean(haversine(pred, actual)) | km |
| **Position RMSE** | sqrt(mean(haversine(pred, actual)²)) | km |
| **Position Median** | median(haversine(pred, actual)) | km |
| **Position Max** | max(haversine(pred, actual)) | km |

Haversine distance uses the WGS-84 mean Earth radius (6371.0088 km).

---

## 5. Per-Sample Results

### 5.1 All 14 Test Samples — Model A (Persistence)

| # | Iceberg | Date | Actual (lat, lon) | Predicted (lat, lon) | Lat Err° | Lon Err° | Pos Err km |
|---|---|---|---|---|---|---|---|
| 1 | D23 | 2020-11-06 → 2020-11-13 | (-69.430, 74.670) | (-69.430, 74.670) | 0.000 | 0.000 | 0.000 |
| 2 | D23 | 2020-11-13 → 2020-11-20 | (-69.430, 74.670) | (-69.430, 74.670) | 0.000 | 0.000 | 0.000 |
| 3 | D23 | 2020-11-20 → 2020-11-27 | (-69.430, 74.680) | (-69.430, 74.670) | 0.000 | 0.010 | 0.391 |
| 4 | D23 | 2020-11-27 → 2020-12-04 | (-69.430, 74.660) | (-69.430, 74.680) | 0.000 | 0.020 | 0.781 |
| 5 | D23 | 2020-12-04 → 2020-12-11 | (-69.430, 74.660) | (-69.430, 74.660) | 0.000 | 0.000 | 0.000 |
| 6 | D23 | 2020-12-11 → 2020-12-18 | (-69.430, 74.660) | (-69.430, 74.660) | 0.000 | 0.000 | 0.000 |
| 7 | D23 | 2020-12-18 → 2020-12-25 | (-69.430, 74.660) | (-69.430, 74.660) | 0.000 | 0.000 | 0.000 |
| 8 | D27 | 2020-11-06 → 2020-11-13 | (-67.630, 79.020) | (-67.640, 79.260) | 0.010 | 0.240 | 10.215 |
| 9 | D27 | 2020-11-13 → 2020-11-20 | (-67.620, 79.040) | (-67.630, 79.020) | 0.010 | 0.020 | 1.398 |
| 10 | D27 | 2020-11-20 → 2020-11-27 | (-67.630, 79.040) | (-67.620, 79.040) | 0.010 | 0.000 | 1.112 |
| 11 | D27 | 2020-11-27 → 2020-12-04 | (-67.660, 78.860) | (-67.630, 79.040) | 0.030 | 0.180 | 8.311 |
| 12 | D27 | 2020-12-04 → 2020-12-11 | (-67.660, 78.860) | (-67.660, 78.860) | 0.000 | 0.000 | 0.000 |
| 13 | D27 | 2020-12-11 → 2020-12-18 | (-67.680, 78.770) | (-67.660, 78.860) | 0.020 | 0.090 | 4.405 |
| 14 | D27 | 2020-12-18 → 2020-12-25 | (-67.730, 78.580) | (-67.680, 78.770) | 0.050 | 0.190 | 9.755 |

### 5.2 All 14 Test Samples — Model B (Motion Extrapolation)

| # | Iceberg | Date | Actual (lat, lon) | Predicted (lat, lon) | Lat Err° | Lon Err° | Pos Err km |
|---|---|---|---|---|---|---|---|
| 1 | D23 | 2020-11-06 → 2020-11-13 | (-69.430, 74.670) | (-69.430, 74.670) | 0.000 | 0.000 | 0.000 |
| 2 | D23 | 2020-11-13 → 2020-11-20 | (-69.430, 74.670) | (-69.430, 74.670) | 0.000 | 0.000 | 0.000 |
| 3 | D23 | 2020-11-20 → 2020-11-27 | (-69.430, 74.680) | (-69.430, 74.670) | 0.000 | 0.010 | 0.391 |
| 4 | D23 | 2020-11-27 → 2020-12-04 | (-69.430, 74.660) | (-69.430, 74.690) | 0.000 | 0.030 | 1.172 |
| 5 | D23 | 2020-12-04 → 2020-12-11 | (-69.430, 74.660) | (-69.430, 74.640) | 0.000 | 0.020 | 0.781 |
| 6 | D23 | 2020-12-11 → 2020-12-18 | (-69.430, 74.660) | (-69.430, 74.660) | 0.000 | 0.000 | 0.000 |
| 7 | D23 | 2020-12-18 → 2020-12-25 | (-69.430, 74.660) | (-69.430, 74.660) | 0.000 | 0.000 | 0.000 |
| 8 | D27 | 2020-11-06 → 2020-11-13 | (-67.630, 79.020) | (-67.700, 79.050) | 0.070 | 0.030 | 7.886 |
| 9 | D27 | 2020-11-13 → 2020-11-20 | (-67.620, 79.040) | (-67.620, 78.780) | 0.000 | 0.260 | 11.008 |
| 10 | D27 | 2020-11-20 → 2020-11-27 | (-67.630, 79.040) | (-67.610, 79.060) | 0.020 | 0.020 | 2.380 |
| 11 | D27 | 2020-11-27 → 2020-12-04 | (-67.660, 78.860) | (-67.640, 79.040) | 0.020 | 0.180 | 7.929 |
| 12 | D27 | 2020-12-04 → 2020-12-11 | (-67.660, 78.860) | (-67.690, 78.680) | 0.030 | 0.180 | 8.303 |
| 13 | D27 | 2020-12-11 → 2020-12-18 | (-67.680, 78.770) | (-67.660, 78.860) | 0.020 | 0.090 | 4.405 |
| 14 | D27 | 2020-12-18 → 2020-12-25 | (-67.730, 78.580) | (-67.700, 78.680) | 0.030 | 0.100 | 5.377 |

---

## 6. Aggregate Metrics Comparison

| Metric | Model A (Persistence) | Model B (Motion) | Winner |
|---|---|---|---|
| Latitude MAE (°) | 0.009 | 0.014 | **Persistence** |
| Latitude RMSE (°) | 0.017 | 0.024 | **Persistence** |
| Longitude MAE (°) | 0.054 | 0.066 | **Persistence** |
| Longitude RMSE (°) | 0.098 | 0.105 | **Persistence** |
| Position MAE (km) | 2.598 | 3.545 | **Persistence** |
| Position RMSE (km) | 4.566 | 5.150 | **Persistence** |
| Position Median (km) | 0.586 | 1.776 | **Persistence** |
| Position Max (km) | 10.215 | 11.008 | **Persistence** |

**Overall:** **Persistence** wins more metrics (8 vs 0)

---

## 7. Error Distribution

### 7.1 Position Error Distribution — Model A (Persistence)

- Min: 0.000 km
- 25th percentile: 0.000 km
- Median: 0.586 km
- 75th percentile: 3.653 km
- Max: 10.215 km
- Std: 3.756 km

### 7.2 Position Error Distribution — Model B (Motion)

- Min: 0.000 km
- 25th percentile: 0.098 km
- Median: 1.776 km
- 75th percentile: 7.259 km
- Max: 11.008 km
- Std: 3.735 km

### 7.3 Per-Iceberg Breakdown

| Iceberg | N (test) | Persistence MDE (km) | Motion MDE (km) |
|---|---|---|---|
| D23 | 7 | 0.167 | 0.335 |
| D27 | 7 | 5.028 | 6.755 |

---

## 8. Strengths and Weaknesses

### Model A — Persistence

| Strength | Weakness |
|---|---|
| No training; fully deterministic | Ignores all motion — always predicts zero displacement |
| Optimal for grounded icebergs (D23) | Fails for drifting icebergs (D27, B39, D28) |
| Low computational cost | No environmental or physical information used |
| Unbiased — no overfitting possible | Cannot learn wind/current-driven drift patterns |

### Model B — Motion Extrapolation

| Strength | Weakness |
|---|---|
| Uses recent drift momentum — physically motivated | Assumes constant velocity; ignores acceleration |
| Captures drifting iceberg trends | Extrapolation error grows for variable trajectories |
| No training; fully deterministic | Degrades to persistence when prev_delta ≈ 0 (D23) |
| Leaks no future information | Ignores wind, current, and ice conditions |

---

## 9. Limitations

| Limitation | Impact |
|---|---|
| **14 test samples** | Results are indicative, not statistically robust; do not claim significance |
| **Only 2 icebergs in test** (D23, D27) | Generalization untested; B39 and D28 absent from test |
| **D23 is grounded** (7/14 test samples) | Persistence is optimal for D23; any motion model risks degrading performance |
| **7-day horizon** | Cannot evaluate shorter or longer horizons |
| **No uncertainty quantification** | Both baselines produce point predictions only |
| **Constant-velocity assumption** | Ignores ocean current changes, wind variability, and Coriolis drift |

---

## 10. Conclusion

**Persistence baseline Position MAE:** 2.598 km
**Motion baseline Position MAE:** 3.545 km

**Reference baseline for subsequent ML models:**

- Any ML model must achieve **Position MAE < 2.598 km** to outperform persistence.
- A meaningful improvement over motion baseline requires **Position MAE < 3.545 km**.

The small test set (14 samples, 2 icebergs) limits the strength of any conclusion.  
Results should be interpreted as indicative baselines for the prototype, not as validated benchmarks.

---

## 11. Validation Checklist

| Check | Status |
|---|---|
| Correct test set used (Phase 3 Step 2) | ✅ Verified |
| Exactly 14 test samples evaluated | ✅ Verified |
| No training/validation samples in evaluation | ✅ Verified |
| No future iceberg positions used as predictors | ✅ Verified |
| No future environmental information used | ✅ Verified |
| No test-set tuning occurred | ✅ Verified |
| Predictions have valid lat/lon values | ✅ Verified |
| Metrics calculated correctly (haversine) | ✅ Verified |
| Results reproducible (deterministic, no RNG) | ✅ Verified |

---

*Report generated 2026-09-04. No models trained; deterministic baselines only.  
All Phase 1 and Phase 2 data remain untouched.*