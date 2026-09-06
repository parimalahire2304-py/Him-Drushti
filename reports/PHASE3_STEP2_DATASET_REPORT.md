# Phase 3 Step 2 — Supervised ML Dataset Report

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-04

**Status:** ✅ DATASET VALIDATION PASSED — ready for model training.

---

## 1. Summary

| Item | Value |
|---|---|
| **Total valid supervised pairs** | 101 |
| **Train / Val / Test** | 71 / 16 / 14 |
| **Iceberg trajectories** | 4 (B39, D23, D27, D28) |
| **Prediction horizon** | 7 days (1 week) |
| **Input features** | 25 columns |
| **Target variables** | `target_lat`, `target_lon` |
| **Validation result** | 14/14 checks PASS |

---

## 2. Input Data Sources

| Source | Path | Role |
|---|---|---|
| Iceberg tracks | `data/processed/icebergs/east_prydz_bay_icebergs.csv` | 796 observations, 11 icebergs, 2016–2026 |
| Feature stack | `data/processed/integration/east_prydz_bay_2020_feature_stack.nc` | 9 gridded variables, 8784 hourly steps, 0.25° grid |
| Problem definition | `reports/PHASE3_STEP1_PROBLEM_DEFINITION.md` | Approved ML formulation |

---

## 3. Available Iceberg Trajectories (2020 Window)

| Iceberg | 2020 Records | Valid 7-day Pairs | Mean Displacement | Mean Speed | Drift Type |
|---|---|---|---|---|---|
| **B39** | 22 | 21 | 33.3 km | 4.75 km/day | **Active drift** |
| **D23** | 50 | 48 | 0.08 km | 0.01 km/day | **Grounded** |
| **D27** | 25 | 23 | 2.7 km | 0.38 km/day | **Moderate drift** |
| **D28** | 10 | 9 | 22.6 km | 3.23 km/day | **Active drift** |
| **Total** | 107 | **101** | — | — | — |

**Pairs lost (not 7-day intervals):**
- D23: 1 gap of 21 days (2020-08-21 → 2020-09-11) — 1 pair lost
- D27: 1 gap of 21 days (2020-07-31 → 2020-09-11) — 1 pair lost
- B39: 0 pairs lost (all 7-day intervals)
- D28: 0 pairs lost (all 7-day intervals)
- **Total pairs constructed: 101** (99.0% of consecutive observations were valid 7-day steps)

---

## 4. Chronological Train / Validation / Test Split

| Split | Date Range | Samples | Icebergs | Rationale |
|---|---|---|---|---|
| **Train** | 2020-01-03 → 2020-08-14 | 71 | B39, D23, D27, D28 | Early-season data; all icebergs present |
| **Validation** | 2020-09-11 → 2020-10-30 | 16 | D23, D27 | Mid-season; B39 & D28 already exited |
| **Test** | 2020-11-06 → 2020-12-18 | 14 | D23, D27 | Late-season; only grounded (D23) and moderate (D27) remain |

**Split properties:**
- ✅ Strictly chronological — no temporal overlap
- ✅ No iceberg appears in both train and test at overlapping times
- ✅ Forward-in-time generalization: model trained on Jan–Aug predicts Sep–Dec
- ✅ Leave-one-iceberg-out CV also possible (B39, D23, D27, D28 as held-out)

---

## 5. Input Features (25 columns)

### 5.1 Static Features (2)
| Feature | Source | Description |
|---|---|---|
| `iceberg_length_nm` | NIC CSV | Iceberg length in nautical miles |
| `iceberg_width_nm` | NIC CSV | Iceberg width in nautical miles |

### 5.2 Dynamic Gridded Features (9) — extracted at observation (lat, lon, date)
| Feature | Source | Interpolation | Temporal Agg. | Units |
|---|---|---|---|---|
| `sea_ice_concentration` | NSIDC | Nearest-neighbour | Daily mean | fraction [0,1] |
| `wind_u_10m` | ERA5 | Bilinear | Daily mean | m/s |
| `wind_v_10m` | ERA5 | Bilinear | Daily mean | m/s |
| `temperature_2m` | ERA5 | Bilinear | Daily mean | K |
| `mean_sea_level_pressure` | ERA5 | Bilinear | Daily mean | Pa |
| `total_precipitation` | ERA5 | Bilinear | Daily **sum** | m |
| `bathymetry_elevation` | GEBCO | Nearest-neighbour + fallback | Daily mean (static) | m |
| `ocean_current_u` | GLORYS | Bilinear | Daily mean | m/s |
| `ocean_current_v` | GLORYS | Bilinear | Daily mean | m/s |

### 5.3 Engineered Features (14)
| Feature | Definition |
|---|---|
| `lat`, `lon` | Current iceberg position (input features) |
| `wind_speed` | √(wind_u² + wind_v²) |
| `wind_dir` | atan2(wind_u, wind_v) ∈ [0, 360°) |
| `ocean_speed` | √(ocean_u² + ocean_v²) |
| `ocean_dir` | atan2(ocean_u, ocean_v) ∈ [0, 360°) |
| `wind_ocean_angle` | Angle between wind and current vectors [0, 180°] |
| `exposed_water_fraction` | 1 − sea_ice_concentration |
| `prev_lat`, `prev_lon` | Previous observation position (NaN if no valid t−7 obs) |
| `prev_delta_lat`, `prev_delta_lon` | Displacement from previous step |
| `prev_speed` | Previous step speed (km/day) |
| `prev_bearing` | Previous step bearing [0, 360°] |

**All features use ONLY information available at or before time *t*.** Targets at *t+7* are never used as inputs.

---

## 6. Target Variables

| Target | Definition | Unit |
|---|---|---|
| `target_lat` | Latitude at next observation (t + 7 days) | decimal degrees |
| `target_lon` | Longitude at next observation (t + 7 days) | decimal degrees |

### Derived Evaluation Targets (not used as model inputs)
| Derived | Definition | Unit |
|---|---|---|
| `delta_lat` | target_lat − lat | degrees |
| `delta_lon` | target_lon − lon | degrees |
| `displacement_km` | Haversine distance between positions | km |
| `speed_km_day` | displacement_km / 7 | km/day |
| `bearing_deg` | Initial bearing from current to next position | degrees |

---

## 7. Dataset Statistics

### 7.1 Target Distributions

| Statistic | `target_lat` | `target_lon` | `displacement_km` | `speed_km_day` | `bearing_deg` |
|---|---|---|---|---|---|
| Mean | −68.46° | 75.75° | 9.58 km | 1.37 km/day | 94.1° |
| Std | 0.99° | 2.15° | 20.2 km | 2.89 km/day | 123.2° |
| Median | −69.21° | 74.67° | 0.00 km | 0.00 km/day | 66.7° |
| Max | −66.37° | 79.52° | 108.2 km | 15.5 km/day | 359.9° |

**Key observation:** D23 (grounded) contributes 48/101 pairs with ~0 km displacement, pulling the median to zero. This reflects real-world conditions — grounded icebergs are common and operationally important to detect.

### 7.2 Per-Iceberg Target Statistics

| Iceberg | Pairs | Mean Disp. (km) | Mean Speed (km/day) | Mean Bearing |
|---|---|---|---|---|
| B39 | 21 | 33.3 | 4.75 | 215° (SW) |
| D23 | 48 | 0.08 | 0.01 | 12° (N) |
| D27 | 23 | 2.7 | 0.38 | 127° (SE) |
| D28 | 9 | 22.6 | 3.23 | 150° (SE) |

### 7.3 Feature Distributions (all within expected physical ranges)

All 25 features pass range sanity checks:
- `sea_ice_concentration`: [0.0, 1.0] ✅
- `wind_u_10m`: [−15.8, +6.6] m/s ✅
- `wind_v_10m`: [−4.9, +11.2] m/s ✅
- `temperature_2m`: [249.7, 274.3] K ✅
- `bathymetry_elevation`: [−1629.6, −381.3] m ✅
- `ocean_current_u/v`: [−0.31, +0.11] m/s ✅
- Engineered features: all within expected bounds ✅

---

## 8. Missing Values

| Column | NaN Count | Percentage | Reason |
|---|---|---|---|
| `prev_lat` | 6 | 5.9% | First observation of each iceberg trajectory has no t−7 predecessor |
| `prev_lon` | 6 | 5.9% | Same as above |
| `prev_delta_lat` | 6 | 5.9% | Same |
| `prev_delta_lon` | 6 | 5.9% | Same |
| `prev_speed` | 6 | 5.9% | Same |
| `prev_bearing` | 6 | 5.9% | Same |

**All other features: 0 NaN** ✅

The 6 NaN rows per `prev_*` column correspond to the first observation of each trajectory (B39, D23, D27, D28 — plus the first observation after D23/D27's 21-day gaps). This is expected and handled correctly.

---

## 9. Validation Results

All **14/14** validation checks PASS:

| # | Check | Result |
|---|---|---|
| 1 | File existence & structure | ✅ PASS |
| 2 | Sample counts (train/val/test) | ✅ PASS |
| 3 | Trajectory count (4 icebergs) | ✅ PASS |
| 4 | Timestamp ordering within trajectories | ✅ PASS |
| 5 | 7-day target alignment (target_date = obs_date + 7) | ✅ PASS |
| 6 | Feature/target separation (no leakage) | ✅ PASS |
| 7 | Missing values (only expected prev_* NaN) | ✅ PASS |
| 8 | Duplicate samples | ✅ PASS |
| 9 | Invalid coordinates (all in bbox) | ✅ PASS |
| 10 | Feature value ranges (physical sanity) | ✅ PASS |
| 11 | Target value ranges | ✅ PASS |
| 12 | Temporal leakage (chronological split) | ✅ PASS |
| 13 | Future-information leakage | ✅ PASS |
| 14 | Metadata consistency | ✅ PASS |

---

## 10. Leakage Prevention Summary

| Risk | Mitigation Implemented |
|---|---|
| **Temporal leakage** | Strict chronological split: train (Jan–Aug) < val (Sep–Oct) < test (Nov–Dec) |
| **Identity leakage** | Same iceberg appears in train/val/test but at non-overlapping times; leave-one-iceberg-out CV also available |
| **Spatial leakage** | Features interpolated at exact observation (lat, lon) on obs_date only; no future grid cells accessed |
| **Feature leakage** | Target columns (`target_lat`, `target_lon`, `delta_*`, `displacement_*`, `speed_*`, `bearing_*`, `persist_*`) explicitly excluded from feature list |
| **Future environmental conditions** | Daily mean/sum computed ONLY from 24-hourly values on obs_date; no t+7 environmental data used |
| **Missing value filling** | No forward/backward fill; `prev_*` features remain NaN where unavailable (first step per trajectory) |

---

## 11. Baseline Performance (Persistence)

| Metric | Value |
|---|---|
| **Mean Displacement Error (MDE)** | 9.58 km |
| **RMSE of displacement** | 20.66 km |

Any ML model must achieve **MDE < 9.58 km** to outperform the persistence baseline (assume iceberg stays at current position).

---

## 12. Files Created

| File | Description |
|---|---|
| `data/processed/ml/train.parquet` | 71 training samples |
| `data/processed/ml/val.parquet` | 16 validation samples |
| `data/processed/ml/test.parquet` | 14 test samples |
| `data/processed/ml/full.parquet` | All 101 samples combined |
| `data/processed/ml/ml_dataset_metadata.json` | Full provenance & statistics |
| `scripts/ml/prepare_ml_dataset.py` | Reproducible preprocessing pipeline |
| `scripts/ml/validate_ml_dataset.py` | Comprehensive validation (14 checks) |
| `reports/PHASE3_STEP2_DATASET_REPORT.md` | This report |

---

## 13. Limitations & Notes

| Limitation | Impact | Mitigation |
|---|---|---|
| **Small dataset (101 samples)** | Overfitting risk for complex models | Use regularized/linear models, XGBoost with early stopping; physics-informed approach recommended |
| **D23 grounded (48/101 pairs)** | Class imbalance toward zero displacement | Include D23 (grounding detection is valuable); consider weighted loss or two-stage classification |
| **Only 4 icebergs in 2020** | Limited diversity of drift patterns | Use leave-one-iceberg-out CV; accept as prototype constraint |
| **Weekly observation frequency** | Cannot resolve sub-weekly dynamics; 7-day horizon fixed | Document as operational constraint |
| **Coastal bathymetry NaN fallback** | 2 coastal points used nearest-ocean-cell depth | Nearest-neighbour + expanding-radius fallback up to 5 grid cells; documented |
| **No iceberg mass/draft evolution** | Length/width static in NIC data | Accept; future work could add melt/breakup models |

---

## 14. Recommended Next Steps (Phase 3 Step 3+)

1. **Baseline models** (Step 3a): Persistence, linear extrapolation, Ridge regression
2. **Tree-based models** (Step 3b): Random Forest, XGBoost with 25 features → 2 targets
3. **Sequence model** (Step 3c): LSTM with lookback window (3–5 steps)
4. **Physics-informed enhancement** (Step 4): Embed drift dynamics as regularization
5. **Evaluation** (Step 5): Compare against persistence baseline (MDE < 9.58 km)

---

## 15. Reproducibility

- Random state: deterministic (no random operations; purely chronological)
- Split boundaries: `2020-08-15` (train→val) and `2020-10-31` (val→test)
- Feature extraction: bilinear for smooth fields, nearest-neighbour for sea ice & bathymetry
- Temporal aggregation: daily mean (sum for precipitation) from 24 hourly feature-stack values
- All code: `scripts/ml/prepare_ml_dataset.py` and `scripts/ml/validate_ml_dataset.py`

---

*Audit trail: Phase 2 feature stack read-only; no Phase 1 data modified; no external API calls; no synthetic data generated.*