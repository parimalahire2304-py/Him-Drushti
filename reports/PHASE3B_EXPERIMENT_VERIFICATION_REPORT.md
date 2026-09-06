# PHASE 3B — EXPANDED ML EXPERIMENT VERIFICATION REPORT

**Date:** 2026-09-05  
**Dataset:** `data/processed/ml/expanded/`  
**Status:** ✅ **ALL 11 VERIFICATION CHECKS PASS** — ready for model training (awaiting approval)

---

## 1. VERIFICATION RESULTS (11 CHECKS)

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | 451 valid pairs preserved | ✅ PASS | `full.parquet` = 451 rows |
| 2 | 8 iceberg IDs represented | ✅ PASS | B39, C18B, C39, D21B, D22, D23, D27, D28 |
| 3 | 7 years represented | ✅ PASS | 2016, 2017, 2019, 2020, 2021, 2024, 2025 |
| 4 | 142 drifting / 309 grounded pairs | ✅ PASS | Grounded (D23) = 309; drifting (others) = 142 |
| 5 | Chronological split leakage-safe | ✅ PASS | train end 2021-12-31 < val start 2024-01-04; val end 2024-12-26 < test start 2025-01-16 |
| 6 | No future iceberg positions in predictors | ✅ PASS | 0 target columns in 25-feature set |
| 7 | No future environmental info in predictors | ✅ PASS | 9 env cols extracted at t only; no date columns |
| 8 | C39 zero-shot isolated to test | ✅ PASS | C39 in train=0, val=0, test=9 |
| 9 | No duplicate observations/pairs | ✅ PASS | 0 duplicates |
| 10 | Feature schema matches approved Phase 3 | ✅ PASS | 39 columns, identical names & order to original; 25 features |
| 11 | Original Phase 3 Step 2 dataset unchanged | ✅ PASS | original files predate expanded build |

**RESULT: 11/11 PASS**

---

## 2. PRE-TRAINING REPORT

### 2.1 Total Pairs
**451**

### 2.2 Pairs per Year (input obs_date)

| Year | Pairs |
|---|---|
| 2016 | 49 |
| 2017 | 57 |
| 2019 | 66 |
| 2020 | 103 |
| 2021 | 67 |
| 2024 | 55 |
| 2025 | 54 |
| **Total** | **451** |

### 2.3 Pairs per Iceberg

| Iceberg | Pairs | Type |
|---|---|---|
| D23 | 309 | Grounded |
| C18B | 40 | Drifting |
| D27 | 38 | Moderate drift |
| B39 | 28 | Active drift |
| D22 | 11 | Active drift |
| C39 | 9 | Drifting |
| D28 | 9 | Active drift |
| D21B | 7 | Active drift |
| **Total** | **451** | — |

### 2.4 Drifting / Grounded Counts
- **Grounded:** 309 (D23)
- **Drifting:** 142 (7 icebergs: B39, C18B, D21B, D22, D27, D28, C39)

### 2.5 Train / Val / Test Counts
- **Train:** 342
- **Val:** 55
- **Test:** 54
- **Sum:** 451 ✓

### 2.6 Date Ranges per Split
| Split | obs_date range | target_date end |
|---|---|---|
| Train | 2016-01-01 → 2021-12-31 | through 2022-01-07 |
| Val | 2024-01-04 → 2024-12-26 | through 2025-01-02 |
| Test | 2025-01-16 → 2025-12-26 | through 2026-01-02 |

### 2.7 Iceberg IDs per Split
| Split | # | Icebergs |
|---|---|---|
| Train | 6 | B39, D21B, D22, D23, D27, D28 |
| Val | 2 | C18B, D23 |
| Test | 3 | C18B, C39, D23 |

### 2.8 Feature Count
**25** (2 static + 9 gridded + 6 derived + 2 position + 6 previous-step)

| Group | Features |
|---|---|
| Static (2) | iceberg_length_nm, iceberg_width_nm |
| Position (2) | lat, lon |
| Gridded (9) | sea_ice_concentration, wind_u_10m, wind_v_10m, temperature_2m, mean_sea_level_pressure, total_precipitation, bathymetry_elevation, ocean_current_u, ocean_current_v |
| Derived (6) | wind_speed, wind_dir, ocean_speed, ocean_dir, wind_ocean_angle, exposed_water_fraction |
| Previous-step (6) | prev_lat, prev_lon, prev_delta_lat, prev_delta_lon, prev_speed, prev_bearing |

### 2.9 Target Variables
- **Primary:** `target_lat`, `target_lon`
- **Derived (evaluation only):** delta_lat, delta_lon, displacement_km, speed_km_day, bearing_deg

### 2.10 Missing Values
- **Core features (25): 0 NaN**
- `prev_*` (first observation per trajectory): **60 NaN each** — expected, no t−7 reference exists

### 2.11 Leakage Checks
- Chronological split: ✅ PASS
- No future positions in features: ✅ PASS
- No future environment in features: ✅ PASS
- C39 test-only: ✅ PASS
- No duplicates: ✅ PASS

---

## 3. COMPARISON — ORIGINAL vs EXPANDED

| Metric | Original (Phase 3) | Expanded (Phase 3B) |
|---|---|---|
| Total pairs | 101 | **451** (4.5×) |
| Iceberg IDs | 4 | **8** (+4) |
| Years | 1 (2020) | **7** (+6) |
| Train / Val / Test | 71 / 16 / 14 | **342 / 55 / 54** |
| Features | 25 | **25** (identical) |
| Icebergs | B39, D23, D27, D28 | +C18B, C39, D21B, D22 |
| Drifting pairs | 30 | **142** (4.7×) |
| Grounded pairs | 48 | **309** |
| Zero-shot iceberg | none | **C39 (test-only)** |

**Improvement:** 4.5× pairs | +4 icebergs | +6 years

---

## 4. FILES (Experiment Directory)

| File | Size | Content |
|---|---|---|
| `data/processed/ml/expanded/full.parquet` | 85 KB | 451 rows × 39 cols |
| `data/processed/ml/expanded/train.parquet` | 70 KB | 342 rows |
| `data/processed/ml/expanded/val.parquet` | 31 KB | 55 rows |
| `data/processed/ml/expanded/test.parquet` | 32 KB | 54 rows |
| `data/processed/ml/expanded/ml_dataset_metadata.json` | 4.8 KB | Build metadata (n_features=25, total=451) |

*Model outputs will be written to `data/processed/ml/expanded/models/` once training is approved — kept separate from the original Phase 3 model outputs.*

---

## 5. FILES CONFIRMED UNTOUCHED

- `data/processed/ml/full.parquet`, `train.parquet`, `val.parquet`, `test.parquet`, `ml_dataset_metadata.json` — **original Phase 3 dataset, mtimes predate expanded build**
- `data/processed/ml/models/` — original Phase 3 models, untouched
- All 7 yearly feature stacks — read-only, unmodified
- Phase 1 (iceberg CSV, bathymetry) and Phase 2 data — unmodified

---

## 6. NOT DONE (per instruction)

- ❌ No model trained (RF / XGBoost / LSTM)
- ❌ No additional data downloaded (2022/2023/2026)
- ❌ No existing data or model modified

---

> **STOPPING HERE.**  
> All 11 verification checks PASS. Pre-training report complete.  
> Awaiting approval to train Random Forest, XGBoost, and LSTM on the expanded dataset.
