# Phase 3 Step 1 — ML Problem Definition and Dataset Analysis

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-04

**Region:** East Prydz Bay (S −70.0, N −66.0, W 72.0, E 80.0, EPSG:4326)

**Status:** READ-ONLY ANALYSIS — no models trained, no data modified.

---

## 1. Available Iceberg Observations

### 1.1 Source Dataset

- **File:** `data/processed/icebergs/east_prydz_bay_icebergs.csv`
- **Total records:** 796
- **Date range:** 2016-01-01 to 2026-08-27 (10.7 years)
- **Unique icebergs:** 11

### 1.2 Unique Iceberg Trajectories

| Iceberg | Records | Date Range | In 2020? | 2020 Records | Characteristics |
|---|---|---|---|---|---|
| **D23** | 551 | 2016-01-01 → 2026-08-27 | ✅ | 50 | **Grounded** (essentially stationary, ~0.08 km displacement per step) |
| **C18B** | 75 | 2024-02-16 → 2025-07-24 | ❌ | 0 | Active drift (2.52° lat, 7.21° lon range) |
| **B39** | 30 | 2019-11-01 → 2020-06-19 | ✅ | 22 | Active drift (2.21° lat, 7.81° lon, max speed 15.5 km/day) |
| **C39** | 30 | 2025-10-09 → 2026-04-30 | ❌ | 0 | Active drift (2.64° lat, 4.95° lon) |
| **D27** | 40 | 2020-06-26 → 2021-04-09 | ✅ | 25 | Moderate drift (0.81° lat, 6.18° lon, speed 0.37 km/day) |
| **D22** | 14 | 2019-08-09 → 2019-11-08 | ❌ | 0 | Active drift |
| **D28** | 11 | 2019-09-27 → 2020-04-24 | ✅ | 10 | Active drift (2.18° lat, 2.05° lon, speed 3.2 km/day) |
| **D15C** | 19 | 2026-04-24 → 2026-08-27 | ❌ | 0 | Slow drift |
| **D15D** | 17 | 2026-05-08 → 2026-08-27 | ❌ | 0 | Slow drift |
| **D21B** | 8 | 2017-03-10 → 2017-04-28 | ❌ | 0 | Short track, active drift |
| **B09I** | 1 | 2019-05-03 | ❌ | 0 | **Single observation** — unusable |

### 1.3 2020 Window Summary (Analysis Target)

| Iceberg | 2020 Records | Mean Displacement | Mean Speed | Drift Type |
|---|---|---|---|---|
| B39 | 22 | 33.2 km/step | 4.75 km/day | **Active drift** |
| D23 | 50 | 0.08 km/step | 0.011 km/day | **Grounded** |
| D27 | 25 | 2.6 km/step | 0.37 km/day | **Moderate drift** |
| D28 | 10 | 22.6 km/step | 3.22 km/day | **Active drift** |
| **Total** | **107** | — | — | — |

---

## 2. Timestamps

| Property | Value |
|---|---|
| Date range (full dataset) | 2016-01-01 → 2026-08-27 |
| Date range (2020 window) | 2020-01-03 → 2020-12-25 |
| Observation timestamps | Daily (00:00 UTC), but observations are **weekly** |
| Feature stack timestamps | Hourly (2020-01-01T00:00 → 2020-12-31T23:00 UTC, 8784 steps) |

**Temporal alignment:** Each iceberg observation timestamp (e.g., `2020-01-03`) falls at 00:00 UTC on that date. The corresponding feature-stack entry is at the same hourly timestamp. For more robust feature extraction, a **24-hour daily mean** of the feature-stack variables on the observation date is recommended (smoothing out sub-daily weather variability).

---

## 3. Latitude/Longitude Fields

| Field | Dtype | Range (2020) | Missing | Notes |
|---|---|---|---|---|
| `Latitude` | float64 | −69.51 to −66.37 | 0 | Decimal degrees, south-negative |
| `Longitude` | float64 | 72.02 to 79.91 | 0 | Decimal degrees, east-positive |

**All 107 observations in 2020 fall within the feature-stack grid** (lat [−70, −66], lon [72, 80]). No extrapolation is required; bilinear interpolation from the 0.25° grid to exact observation coordinates is straightforward.

---

## 4. Unique Trajectories Available

**11 unique iceberg IDs** in the full dataset, **4 active in the 2020 window** (B39, D23, D27, D28).

**Note on D23:** This iceberg is effectively **grounded** — it has been at approximately the same location (lat −69.43, lon 74.65–74.72) for over 10 years with a mean displacement of only 0.08 km per weekly step. D23 contributes 50 of the 107 2020 records but nearly zero-displacement pairs. While this is physically realistic (grounded icebergs do not drift), D23 dominates the sample count and will bias training toward stationary behavior unless handled carefully.

---

## 5. Temporal Resolution

| Property | Value |
|---|---|
| **Observation frequency** | **Weekly** (7-day intervals, nominal) |
| Actual interval range | 1–147 days (median: 7 days) |
| D23 gap (one 21-day gap) | 2020-08-21 → 2020-09-11 |
| D27 gap (one 21-day gap) | 2020-07-31 → 2020-09-11 |
| D28 gaps | One 147-day gap between 2019 and 2020 segments |

Most consecutive observations are exactly **7 days apart**. A small number of 14-day and 21-day gaps exist (from missing weekly reports). These irregular gaps must be handled: either skip pairs with dt ≠ 7 days, or normalize displacement by actual dt.

---

## 6. Prediction Target

### Primary Target: Next-Position (lat, lon)

**For each observation at time *t*, predict the position at time *t + Δt* (next observation).**

| Target | Definition | Unit |
|---|---|---|
| `target_lat` | Latitude at next observation | decimal degrees |
| `target_lon` | Longitude at next observation | decimal degrees |

### Derived Targets (for analysis and physics-informed features)

| Derived | Definition | Unit |
|---|---|---|
| `displacement_km` | Great-circle distance between consecutive positions | km |
| `speed_km_day` | displacement_km / Δt_days | km/day |
| `bearing_deg` | Direction of movement (0°=N, 90°=E, clockwise) | degrees |

### Target Statistics (2020, 7-day intervals only)

| Metric | B39 | D23 | D27 | D28 | All |
|---|---|---|---|---|---|
| Mean displacement (km) | 33.2 | 0.08 | 2.6 | 22.6 | 9.4 |
| Median displacement (km) | 29.3 | 0.00 | 0.9 | 20.8 | 0.0* |
| Max displacement (km) | 108.8 | 1.4 | 11.1 | 37.8 | 108.8 |
| Mean speed (km/day) | 4.75 | 0.01 | 0.37 | 3.22 | 1.34 |
| Mean bearing (°) | 214.7 | 12.5 | 126.7 | 150.0 | 92.3 |

*Median is ~0 because D23's 49 near-zero-displacement pairs dominate the count.

---

## 7. Prediction Horizon

**Δt = 7 days (1 week)** — determined by the observation frequency.

| Horizon | Value | Justification |
|---|---|---|
| **Primary** | **7 days** | Matches the nominal weekly observation interval; this is the natural prediction cadence |
| **Alternative** | 14 days (2 steps) | Two-step-ahead prediction; fewer samples available (95 vs 103 pairs) |
| **Not recommended** | < 7 days | No intermediate observations available to serve as ground truth |

**For the prototype, a 7-day single-step prediction horizon is recommended.** The model predicts the iceberg's position one week ahead, given its current state and environmental conditions.

---

## 8. Feature–Observation Association

### 8.1 Spatial Extraction

Observation lat/lon coordinates do **not** fall on the 0.25° feature-grid centers. Feature values must be extracted at each observation's exact coordinates.

**Recommended method: bilinear interpolation** from the four nearest grid cells.

```
Given observation at (lat_obs, lon_obs):
  1. Find four surrounding grid cells: (i,j), (i+1,j), (i,j+1), (i+1,j+1)
  2. Bilinear weight based on fractional position
  3. Weighted average of the four cell values
```

This provides exact environmental values at the observation point, physically correct for smooth fields (wind, temperature, pressure, currents). For `sea_ice_concentration` (which has sharp boundaries), **nearest-neighbor** is preferable to avoid interpolating across the ice edge.

### 8.2 Temporal Extraction

| Approach | Method | Use Case |
|---|---|---|
| **Snapshot** | Feature values at obs timestamp (00:00 UTC) | Simple baseline |
| **Daily mean** | Average of 24 hourly values on the obs date | Recommended (smoother, robust) |
| **Lookback mean** | Mean over the 7-day window preceding the obs | For sequence models |

### 8.3 Available Feature Variables (at each observation point)

| Feature | Source | Extraction Method |
|---|---|---|
| `sea_ice_concentration` | NSIDC | Nearest-neighbor (sharp ice edge) |
| `wind_u_10m` | ERA5 | Bilinear interpolation, daily mean |
| `wind_v_10m` | ERA5 | Bilinear interpolation, daily mean |
| `temperature_2m` | ERA5 | Bilinear interpolation, daily mean |
| `mean_sea_level_pressure` | ERA5 | Bilinear interpolation, daily mean |
| `total_precipitation` | ERA5 | Bilinear interpolation, daily sum |
| `bathymetry_elevation` | GEBCO | Bilinear interpolation (static, same for all t) |
| `ocean_current_u` | GLORYS | Bilinear interpolation, daily mean |
| `ocean_current_v` | GLORYS | Bilinear interpolation, daily mean |

### 8.4 Additional Engineered Features

| Feature | Definition | Rationale |
|---|---|---|
| `wind_speed` | sqrt(u² + v²) | Total wind forcing magnitude |
| `wind_direction` | atan2(u, v) | Wind direction (meteorological convention) |
| `ocean_speed` | sqrt(u² + v²) | Total current magnitude |
| `ocean_direction` | atan2(u, v) | Current direction |
| `wind_ocean_angle` | angle between wind and current vectors | Drag coupling efficiency |
| `ice_fraction` | 1 − sea_ice_concentration | Exposed water fraction (higher drag on iceberg) |
| `prev_lat`, `prev_lon` | Position at previous observation | Lag-1 autoregressive input |
| `prev_displacement_km` | Displacement from previous step | Momentum proxy |
| `prev_bearing` | Bearing from previous step | Directional persistence |

---

## 9. Is the Data Sufficient for Supervised ML?

### 9.1 Sample Count Assessment

| Configuration | Usable Samples | Assessment |
|---|---|---|
| lookback=1 (current pos + env → next pos) | **103 pairs** | Marginal for any ML |
| lookback=2 (2 prior positions → next) | 99 pairs | Slightly reduced |
| lookback=3 (3 prior positions → next) | 95 pairs | Reduced further |
| lookback=5 (5 prior positions → next) | 87 pairs | Insufficient for deep learning |

### 9.2 Verdict

**The data is SUFFICIENT for a prototype/baseline ML model, but NOT for a deep learning approach.**

| Approach | Feasibility | Rationale |
|---|---|---|
| Linear regression / Ridge | ✅ Feasible | Low sample requirement |
| Random Forest / XGBoost | ✅ Feasible | Works with ~100 samples, handles mixed features |
| Simple MLP (1–2 layers) | ⚠️ Marginal | ~103 samples, risk of overfitting |
| LSTM / GRU | ⚠️ Marginal | Sequence model, needs careful regularization |
| Transformer / Attention | ❌ Not feasible | Requires orders of magnitude more data |
| Physics-informed NN (PINN) | ✅ **Best fit** | Embeds drift physics as inductive bias, reduces data requirement |

**Recommendation:** Use a **physics-informed approach** or **gradient-boosted trees (XGBoost)** as the primary model, with a **simple LSTM baseline** for comparison. The 103-sample constraint makes regularization and inductive bias critical.

### 9.3 D23 Grounded-Iceberg Consideration

D23 contributes 49 of 103 training pairs but is essentially stationary (mean speed 0.011 km/day). This creates a **class imbalance** toward zero-displacement. Strategies:

1. **Include D23** — it teaches the model when icebergs do NOT move (grounding detection is valuable)
2. **Downsample D23** — balance active vs. stationary samples
3. **Weighted loss** — penalize active-drift errors more heavily
4. **Two-stage model** — first classify grounded vs. drifting, then predict drift magnitude

**Recommended: Include D23 with balanced sampling** — grounding detection is operationally important for navigation safety.

---

## 10. Missing Observations and Irregular Time Intervals

### 10.1 Irregular Intervals

| Iceberg | Gap Count | Max Gap | Notes |
|---|---|---|---|
| B39 | 1 | 35 days | Between 2019-12-20 and 2020-01-24 (missing reports) |
| D23 | 1 | 21 days | Between 2020-08-21 and 2020-09-11 |
| D27 | 1 | 21 days | Between 2020-07-31 and 2020-09-11 |
| D28 | 1 | 147 days | Between 2019-11-08 and 2020-02-21 (cross-year gap) |

### 10.2 Handling Strategy

1. **Primary: 7-day pairs only** — filter to consecutive observations where dt = 7 days
2. **Secondary: dt-normalized** — divide displacement by actual dt, predict velocity (km/day)
3. **Reject gaps > 14 days** — missing intermediate observations make the trajectory unreliable

After filtering to dt = 7 days, the usable sample count remains high (approximately 90–95 pairs).

### 10.3 Missing Observation Sources

NIC weekly reports occasionally skip a week due to:
- Satellite revisit gaps (cloud cover, orbital timing)
- Antarctic winter reduced observation frequency
- Iceberg leaving the region temporarily
- Reporting delays

These gaps are **not** systematic (no seasonal pattern in missingness) and do not introduce temporal bias.

---

## 11. Target Definition (Formal)

### Task: Single-Step Trajectory Prediction

**Input at time *t*:**
- Iceberg position: (lat_t, lon_t)
- Environmental features at (lat_t, lon_t): 9 gridded variables
- Optional: previous position (lat_{t-1}, lon_{t-1}) for autoregressive input
- Optional: iceberg dimensions (length, width) — static per iceberg

**Output:**
- Predicted next position: (lat_{t+1}, lon_{t+1})
- Where t+1 = t + 7 days (next NIC weekly observation)

**Derived evaluation targets:**
- Displacement: Δd = haversine((lat_t, lon_t), (lat_{t+1}, lon_{t+1})) in km
- Speed: Δd / 7 days in km/day
- Bearing: initial bearing from (lat_t, lon_t) to (lat_{t+1}, lon_{t+1}) in degrees

---

## 12. Input Features (Formal)

### 12.1 Static Features (per iceberg)

| Feature | Source | Values |
|---|---|---|
| `iceberg_length_nm` | NIC CSV | 7–29 NM (varies per iceberg) |
| `iceberg_width_nm` | NIC CSV | 2–19 NM (varies per iceberg) |

### 12.2 Dynamic Features (per observation timestamp)

| Feature | Source | Extraction |
|---|---|---|
| `sea_ice_concentration` | Feature stack | Nearest-neighbor at (lat, lon) |
| `wind_u_10m` | Feature stack | Bilinear at (lat, lon), daily mean |
| `wind_v_10m` | Feature stack | Bilinear at (lat, lon), daily mean |
| `temperature_2m` | Feature stack | Bilinear at (lat, lon), daily mean |
| `mean_sea_level_pressure` | Feature stack | Bilinear at (lat, lon), daily mean |
| `total_precipitation` | Feature stack | Bilinear at (lat, lon), daily sum |
| `bathymetry_elevation` | Feature stack | Bilinear at (lat, lon), static |
| `ocean_current_u` | Feature stack | Bilinear at (lat, lon), daily mean |
| `ocean_current_v` | Feature stack | Bilinear at (lat, lon), daily mean |

### 12.3 Engineered Features

| Feature | Definition |
|---|---|
| `wind_speed` | sqrt(u² + v²) |
| `wind_dir` | atan2(wind_u, wind_v) in degrees |
| `ocean_speed` | sqrt(u² + v²) |
| `ocean_dir` | atan2(ocean_u, ocean_v) in degrees |
| `wind_ocean_angle` | Angle between wind and current vectors |
| `exposed_water_fraction` | 1 − sea_ice_concentration |
| `prev_lat`, `prev_lon` | Previous observation position |
| `prev_delta_lat`, `prev_delta_lon` | Displacement from previous step |
| `prev_speed` | Speed from previous step |
| `prev_bearing` | Bearing from previous step |

### 12.4 Total Feature Count

- Static: 2
- Dynamic (raw): 9
- Engineered: 10
- **Total: 21 features**

---

## 13. Train / Validation / Test Strategy

### 13.1 Primary Strategy: Chronological Time-Based Split

**No random splitting.** Sequential observations from the same trajectory must not leak between splits.

| Split | Date Range | Obs Count | Icebergs | Purpose |
|---|---|---|---|---|
| **Train** | 2020-01-03 → 2020-08-21 | ~74 | B39, D23, D27, D28 | Model fitting |
| **Validation** | 2020-08-21 → 2020-10-30 | ~16 | D23, D27 | Hyperparameter tuning, early stopping |
| **Test** | 2020-10-30 → 2020-12-25 | ~17 | D23, D27 | Final performance evaluation |

**Split rationale:**
- **Chronological:** train on earlier observations, test on later — prevents temporal leakage
- **No iceberg in both train and test at overlapping times** — prevents identity leakage
- **B39 and D28 appear only in train** (they exit the region before August)
- **D23 and D27 span all three splits** — their early observations train, middle validates, late tests
- The test set represents **forward-in-time generalization**: given environment + position in late 2020, predict where the iceberg goes

### 13.2 Secondary Strategy: Leave-One-Iceberg-Out Cross-Validation

For robust performance estimation, train on 3 icebergs, test on the held-out one:

| Held-out | Train Icebergs | Test Samples | Challenge |
|---|---|---|---|
| B39 | D23, D27, D28 | 21 | Active drift, strong signal |
| D23 | B39, D27, D28 | 49 | Grounded — tests generalization to stationary |
| D27 | B39, D23, D28 | 24 | Moderate drift |
| D28 | B39, D23, D27 | 9 | Active drift, small test set |

**Note:** This is a challenging evaluation — each iceberg has different drift characteristics, and the model must generalize across iceberg types.

### 13.3 What Must NOT Be Done

| Prohibited | Reason |
|---|---|
| Random train/test split | Temporal autocorrelation → inflated test scores |
| Shuffle across trajectories | Identity leakage — model memorizes iceberg-specific drift |
| Use future observations as input | Look-ahead bias |
| Include test-set icebergs' future data in training | Temporal leakage |

---

## 14. Leakage Risks

| Risk | Mitigation |
|---|---|
| **Temporal leakage** — using future obs to predict past | Chronological split; never shuffle time |
| **Identity leakage** — same iceberg in train and test at same time | Leave-one-iceberg-out CV; chronological split ensures no time overlap |
| **Spatial leakage** — gridded features from future timesteps | Features extracted at obs timestamp only; no look-ahead in feature construction |
| **Feature leakage** — target-derived features in input | Never include target lat/lon or future displacement in features |
| **Data leakage** — using 2020+ data to improve 2020 predictions | Feature stack is 2020-only; no external data used |

---

## 15. Proposed Evaluation Metrics

### 15.1 Primary Metrics

| Metric | Definition | Unit | Target |
|---|---|---|---|
| **Mean Displacement Error (MDE)** | Average haversine distance between predicted and actual next position | km | Lower is better |
| **RMSE of displacement** | Root mean square haversine distance | km | Lower is better |
| **Mean Absolute Error (MAE) lat** | Average absolute latitude error | degrees | Lower is better |
| **Mean Absolute Error (MAE) lon** | Average absolute longitude error | degrees | Lower is better |

### 15.2 Derived Metrics

| Metric | Definition | Use Case |
|---|---|---|
| **Bearing Error** | Angular difference between predicted and actual bearing | Directional accuracy |
| **Hit Rate @ threshold** | % of predictions within N km of actual position | Operational threshold (e.g., 10 km, 25 km, 50 km) |
| **Bias (lat)** | Mean signed latitude error (N/S systematic bias) | Directional bias detection |
| **Bias (lon)** | Mean signed longitude error (E/W systematic bias) | Directional bias detection |

### 15.3 Baseline Comparison

| Baseline | Description | Expected MDE |
|---|---|---|
| **Persistence** | Assume iceberg stays at same position | Mean displacement (~9.4 km) |
| **Linear extrapolation** | Continue previous-step velocity | Depends on trajectory smoothness |
| **Climatological** | Use mean seasonal drift for the region | Region-dependent |

The ML model must **outperform the persistence baseline** (MDE < 9.4 km) to demonstrate learning.

---

## 16. Limitations

### 16.1 Data Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| **Very small dataset** (103 pairs in 2020) | Overfitting risk, limited generalization | Regularization, simple architectures, physics-informed approach |
| **Only 4 icebergs in 2020** | Limited diversity of drift patterns | Include all 4; use leave-one-iceberg-out CV |
| **D23 is grounded** (49/103 pairs) | Dominates sample count with near-zero displacement | Balanced sampling, two-stage classification |
| **Weekly observation frequency** | Cannot predict sub-weekly motion; 7-day horizon is coarse | Accept as operational constraint; document as limitation |
| **Feature stack is 2020-only** | Cannot use multi-year environmental data for training | Accept; note as limitation for future work |
| **NIC position accuracy** | ~0.01° resolution (~1 km) due to rounding in CSV | Accept; sufficient for weekly-scale prediction |
| **No iceberg velocity observations** | Must derive from consecutive positions | Derive velocity from position pairs; adds noise at short intervals |

### 16.2 Physical Limitations

| Limitation | Impact |
|---|---|
| **Ocean current vertical structure** | Feature stack uses surface currents (0.494 m depth); deep-draft icebergs feel deeper currents |
| **Sea-ice drag parameterization** | Concentration only; no ice thickness or floe size information |
| **Wave drift (Stokes drift)** | Not represented in ERA5 winds or GLORYS currents |
| **Calving/breakup events** | Not modeled; iceberg dimensions are static in the CSV |
| **Tidal currents** | GLORYS does not resolve tides; may matter for grounded/nearshore icebergs |

### 16.3 Model Limitations

| Limitation | Impact |
|---|---|
| **No uncertainty quantification** (initially) | Single-point predictions only; no confidence intervals |
| **No physics constraints** (initially) | Model may predict physically implausible trajectories |
| **Prototype quality** | This is a first iteration; not suitable for operational use |

---

## 17. Recommended ML Workflow

### Phase 3 Step-by-Step Plan

| Step | Description | Dependencies |
|---|---|---|
| **Step 2** | Feature extraction: bilinear interpolation of 9 variables + engineered features at each iceberg observation point | Feature stack, iceberg CSV |
| **Step 3** | Dataset construction: (X, y) pairs with chronological train/val/test split | Step 2 |
| **Step 4a** | Baseline models: persistence, linear extrapolation, Ridge regression | Step 3 |
| **Step 4b** | ML models: Random Forest, XGBoost, simple MLP | Step 3 |
| **Step 4c** | Sequence model: LSTM with lookback window | Step 3 |
| **Step 5** | Evaluation against baselines; error analysis | Steps 4a–c |
| **Step 6** | Physics-informed enhancement (optional): constrain predictions with drift dynamics | Steps 4–5 |
| **Step 7** | Model selection and reporting | Step 5 |

### Recommended Architecture for Prototype

**Primary: XGBoost with engineered features**
- Input: 21 features (9 raw + 10 engineered + 2 static)
- Output: 2 targets (delta_lat, delta_lon)
- Advantages: handles small data well, interpretable, fast training
- Hyperparameters: n_estimators=100, max_depth=4–6, learning_rate=0.05–0.1

**Secondary: Simple LSTM for comparison**
- Input: sequence of (position, env_features) over lookback=3–5 steps
- Output: next position (delta_lat, delta_lon)
- Architecture: 1 LSTM layer (32 units) + FC output
- Regularization: dropout=0.3, weight decay

**Baseline: Persistence model**
- Predict next position = current position
- Expected MDE: ~9.4 km (mean displacement)

---

## 18. Summary Table

| Property | Value |
|---|---|
| **Task** | Iceberg single-step trajectory prediction (next position) |
| **Prediction horizon** | 7 days |
| **Target variables** | Latitude, longitude (next position) |
| **Input features** | 21 (9 gridded + 10 engineered + 2 static) |
| **Training samples** | ~103 (2020 window, 4 icebergs) |
| **Train/val/test** | Chronological 70/15/15 split |
| **Primary model** | XGBoost (gradient-boosted trees) |
| **Evaluation** | Mean displacement error (km), hit rate @ threshold |
| **Baseline** | Persistence (assume no movement) |
| **Key limitation** | Very small dataset (103 samples); D23 is grounded |
| **Recommended approach** | Physics-informed or regularized ML; NOT deep learning |

---

## 19. Files and Data Referenced

| File | Role |
|---|---|
| `data/processed/icebergs/east_prydz_bay_icebergs.csv` | Iceberg observations (796 records) |
| `data/processed/integration/east_prydz_bay_2020_feature_stack.nc` | Environmental features (9 variables, 8784 hourly steps) |
| `config/region.yaml` | Bounding box and CRS |
| `config/datasets.yaml` | Dataset registry |
| `config/models.yaml` | Model configuration placeholders |

**No files were modified in this analysis.** All data sources remain in their Phase 2 state.

---

*Report generated 2026-09-04. Read-only analysis for Phase 3 Step 1. No models trained, no data modified.*
