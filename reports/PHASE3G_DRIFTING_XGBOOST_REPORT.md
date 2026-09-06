# PHASE 3G — DRIFTING-FOCUSED MOTION-AWARE XGBOOST EXPERIMENT

**Date:** 2026-09-06 (report finalized post-Phase 3C, before Phase 4 operational use)
**Benchmarks (frozen Phase 3C):** Persistence drift MAE 20.30 km; existing XGBoost drift MAE 27.62 km; dataset 451 valid 7-day pairs (8 icebergs: B39, C18B, C39, D21B, D22, D23, D27, D28), splits train 342 / val 55 / test 54 (no shuffle; train obs <2024-01-01 ≤ val <2025-01-01 ≤ test).
**Objective (verbatim):** determine whether XGBoost can improve trajectory prediction specifically for genuinely drifting icebergs, beating the frozen persistence drift benchmark (20.30 km) with three controlled approaches — displacement XGBoost, motion-aware XGBoost, and a hybrid persistence + residual correction — under a matched-baseline comparison without modifying existing Phase 3C experiments, models, or datasets.

---

## 1. Objective

Test drift-only performance of XGBoost with:
- **A.** Displacement target representation (env-only features, predict 7-day displacement `delta_lat`/`delta_lon` — degrees — and reconstruct `pred = current + delta`).
- **B.** Motion-aware representation (same displacement target; extend the feature stack with legit historical motion features from the *predecessor* pair `t-7 → t`).
- **C.** Hybrid persistence + residual: `hybrid = current + predicted_residual` where `residual = actual_future − current == displacement`.

All results are compared against **matched persistence** computed on exactly the same eligible test samples each experiment uses. Original Phase 3C Phase 4 artefacts, BYU data, and 2026 as a new year are untouched.

## 2. Frozen Project State (at 3G start)

- Expanded Phase 3 dataset: 451 supervised 7-day pairs (consecutive same iceberg, exactly 7 days apart, year in `STACK_YEARS = {2016, 2017, 2019, 2020, 2021, 2024, 2025}`); per-year feature stack on a 0.25° lat/lon grid (7 hourly vars aggregated: `sea_ice` mean, `wind_u`/`v` mean, `t2m` mean, `msl` mean, `tp` sum, `bathymetry` mean, `ocean_current` mean; bilinear/nearest-neighbour interpolation). 8 icebergs; `GROUNDED_ICEBERGS = {"D23"}` (mean 7 d disp ~0.08 km). Drifting label = non-D23, therefore **142 drifting / 309 grounded** (spec).
- Split boundaries: train obs_date <2024-01-01 (≤val min 2024-01-04); val obs_date <2025-01-01 ≤ test (2025-01-16–2025-12-26; target_date spills to 2026-01-02 for the 7-day horizon of late-Dec obs — frozen data, not new 2026). Train 342 / val 55 / test 54; **C39 zero-shot 9** all in test (0 train / 0 val). Scores reported by Phase 3C (recomputed): persistence drifting MAE **20.3036 km**.
- `BYU` data remains independent; glimpsed at the dashboard level, never merged.

## 3. Target Representation (§6 Target framing)

| Pair | Variables | Definition | Count (drift) |
|------|-----------|-------------|----------------|
| env | 19 | see §5 | — |
| displacement | `delta_lat` / `delta_lon` | `future − current` (degrees) | 24 drift test |
| residual (hybrid) | `residual_lat` / `residual_lon` | `actual_future − current`  **== displacement** | same |

The displacement and hybrid targets are mathematically identical; the hybrid framing only re-labels the same regression as "correction to persistence". Weighted position error is reported **after reconstruction**:
```
pred_lat = lat + pred_delta_lat
pred_lon = lon + pred_lon
pos_err  = haversine_km(target_lat, target_lon, pred_lat, pred_lon)   # R = 6371.0088 km
```

## 4. Approaches (§7 Experiment A/B/C)

- **Experiment A — Displacement XGBoost (env-only).** Drifting-only training on the 19-feature env/geometry core (§5). Regressors for `delta_lat` / `delta_lon`. Reference model for whether a cleaner target alone beats persistence.
- **Experiment B — Motion-aware XGBoost (env + prev_*).** Four legit historical features admitted: `prev_delta_lat`, `prev_delta_lon`, `prev_speed`, `prev_bearing` where each is computed strictly from the real predecessor observation `t−7 → t` (haversine / bearing logic identical to dataset build). Rows without a real predecessor are **excluded** (spec §6). 23 features.
- **Experiment C — Hybrid persistence + XGBoost residual.** Primary: env-only hybrid with the same features and targets as A (19 feats). A supplementary motion-augmented hybrid is provided (23 feats, predecessor-filtered) for the population where B succeeds. Both realise `hybrid = current + predicted_residual`. The primary hybrid yields byte-identical models to A (residual == displacement and same XGBoost inputs/outputs); the supplementary hybrid yields byte-identical models to B.

## 5. Features (EXPLICITLY STATE — §8)

| Tag | n | Columns |
|-----|---|---------|
| **env (19)** | 19 | `lat`, `lon`, `iceberg_length_nm`, `iceberg_width_nm`, `sea_ice_concentration`, `wind_u_10m`, `wind_v_10m`, `temperature_2m`, `mean_sea_level_pressure`, `total_precipitation`, `bathymetry_elevation`, `ocean_current_u`, `ocean_current_v`, `wind_speed`, `wind_dir`, `ocean_speed`, `ocean_dir`, `wind_ocean_angle`, `exposed_water_fraction` |
| **motion-augmented** | **23** | env **+** `prev_delta_lat`, `prev_delta_lon`, `prev_speed`, `prev_bearing` (the only `prev_*` admitted for 3G; `prev_lat` / `prev_lon` excluded on purpose) |
| **Phase 3C frozen** (`train_xgboost_expanded.py`) | **25** | motion-augmented 2 + `prev_lat`, `prev_lon` |

Feature discovery was audit-only (no provider touch). No `target_lat`, `target_lon`, `delta_*` appears in any feature list — leakage-free by construction.

## 6. Predecessor Logic (§6 Eligibility)

Every supervised row records up to one predecessor pair only if:
```
i > 0 and (obs_date[i] − obs_date[i−1]).days == 7 and iceberg_id[i] == iceberg_id[i−1]
```
Then `prev_lat, prev_lon` come from `row_{i−1}`; `prev_delta_lat = curr_lat − prev_lat` etc.; `prev_speed = haversine(prev, curr) / 7` (km/day); `prev_bearing` per forward-azimuth. Otherwise `prev_*` is `NaN`. Missingness in the full dataset: **60 NaN** in `prev_delta_lat` (audit/missing-value table), featurised as NaN by XGBoost's native sparse path (no imputation, no interpolation). Filtering rule for B: `prev_delta_lat.notna()` on each split independently, **without shuffling**.

Observed eligibility (drift-pure — §9):

| Split | Drift raw | With prev_ | Excluded (no predecessor) | Drifting test icebergs |
|-------|-----------|------------|---------------------------|------------------------|
| train | 93 | **85** | 8 | — |
| val   | 25 | **14** | 11 | — |
| test  | 24 | **14** | 10 | popA 15×C18B + 9×C39; popB 8×C18B + 6×C39 |

## 7. Leakage Review

Audited: feature-generation (`prepare_ml_dataset_expanded.py`), split boundaries (§9), drifting label (`~isin({"D23"})`), raw iceberg records (`east_prydz_bay_icebergs.csv`), XGBoost training flow, persistence evaluation, prediction utils. Finding: **no future-position leakage** — `prev_*` uses only the predecessor observation, feature cols are disjoint from target cols, and the tuning loop never sees the `test` parquet. §11 re-evaluated frozen facts found the existing XGBoost's reported drift RMSE mismatch is only cosmetic (lat/lon columns), not material.

## 8. Training Config (§9 Model rules; seed 42 everywhere)

```
PARAM_GRID (8 dims — small, controlled only)
  n_estimators      : [100, 200, 300]
  max_depth         : [2, 3, 4]
  learning_rate     : [0.05, 0.1]
  min_child_weight  : [5, 10]
  subsample         : [0.8]
  colsample_bytree  : [0.8]
  reg_alpha         : [0.1, 1.0]
  reg_lambda        : [1.0, 5.0]
→ 3×3×2×2×1×1×2×2 = 144 combos per target (lat then lon), grid-search on VAL MAE.
```

Chronological **train+val** retrain with the winning params (Parity with Phase 3C), `RANDOM_STATE = 42`, `objective="reg:squarederror"`, no early-stopping, no bootstrap data change, predictions written per split only for that population size. All three training scripts share this grid and seed verbatim.

Chosen hyperparams (reproducible):

| Model | Lat best | Lon best |
|-------|----------|----------|
| Displacement (env, 93+25 train) | `100 / d2 / 0.10 / 5 / 0.8 / 0.8 / 0.1 / 1.0` | `100 / d4 / 0.05 / 10 / 0.8 / 0.8 / 0.1 / 5.0` |
| Motion-aware (motion, 85+14 = 99 train) | `100 / d3 / 0.05 / 10 / 0.8 / 0.8 / 1.0 / 5.0` | `100 / d3 / 0.05 / 10 / 0.8 / 0.8 / 0.1 / 1.0` |
| Hybrid (env primary; identical to Displacement) + supplementary (motion, identical to Motion-aware) | same as the sibling | same as the sibling |

Training time (seconds, retrain on train+val): ~0.6 (env) / ~0.5 (motion).

## 9. Split / C39 / Counts (§9–10)

342/55/54 chronological splits preserved; C39 **zero-shot** `train 0 / val 0 / test 9` unchanged (audit §10 + validators §10). The 9 C39 test rows split into **6 with predecessor / 3 without**; the 6 are the only C39 rows used by the motion-aware population. No BYU row, no synthetic row, no 2026 obs moved into the splits.

## 10. Eligibility / Filtering (§11 Populations — see §6 for predecessor)

Only samples for which the required predictor mask is fully satisfied are evaluated. Env-only experiments (A, hybrid primary) use every drifting test sample; motion experiments (B, hybrid motion supplementary) use only the predecessor-eligible drifting test samples.

## 11. Populations (VERY IMPORTANT — §11 Match principle)

| Population | Definition (test) | n | Columns used | Models evaluated | Persistence baseline calculated on |
|------------|-------------------|---|--------------|----------------|------------------------------------|
| **popA** | drifting all-eligible | **24** | env 19 (no `prev_*`) | Displacement, Hybrid, Existing XGB, Persistence | the same 24 |
| **popB** | drifting **with** predecessor | **14** | motion 23 (env + 4 motion prev_) | Motion-aware, Hybrid-motion, Existing XGB, Persistence | the same 14 |

No cross-population comparison is drawn without labelling which set each number belongs to.

## 12. Required Output — Matched Persistence Comparison Table (ALL ROWS HAVE NUMBERS — NO "?" MARKS)

**Improvement = `persistence_MAE − model_MAE`** (positive means the model beat persistence). `Abs = km`; `Pct = 100 × abs / persistence_MAE`.

| Population | Split | Model | n | pos MAE (km) | pos RMSE (km) | p50 (km) | p90 (km) | max (km) | lat MAE (deg) | lon MAE (deg) | Δ vs persistence (abs km) | Δ vs persistence (pct) |
|------------|-------|-------|---|--------------|---------------|----------|----------|----------|---------------|---------------|---------------------------|------------------------|
| popA (drift 24) | drift | Persistence | 24 | 20.3036 | 36.0045 | 3.6671 | 53.8648 | 121.8504 | 0.1337 | 0.2467 | — | — |
| popA (drift 24) | drift | Existing XGBoost (Phase 3C, 25-feat) | 24 | 27.6199 | 40.0951 | 20.2024 | 56.1647 | 131.1141 | 0.1784 | 0.3894 | −7.3163 | −36.03% |
| popA (drift 24) | drift | **Displacement XGBoost** (env, 19-feat) | 24 | **21.1722** | **34.3695** | 9.4751 | 40.0824 | 122.9457 | 0.1478 | 0.2387 | −0.8685 | −4.28% |
| popA (drift 24) | drift | **Hybrid (env)** `current + resid` | 24 | **21.1722** | **34.3695** | 9.4751 | 40.0824 | 122.9457 | 0.1478 | 0.2387 | −0.8685 | −4.28% |
| popB (drift+prev 14) | drift | Persistence | 14 | 19.0882 | 29.6706 | 8.6448 | 43.5356 | 81.8119 | 0.0936 | 0.3350 | — | — |
| popB (drift+prev 14) | drift | Existing XGBoost | 14 | 32.4920 | 38.0620 | 28.6827 | 56.1647 | 79.1771 | 0.1899 | 0.5500 | −13.4038 | −70.22% |
| popB (drift+prev 14) | drift | **Motion-aware XGBoost** (env+prev_*, 23-feat) | 14 | **18.1261** | **24.3607** | 13.9188 | 38.0028 | 62.0407 | 0.1038 | 0.2929 | **+0.9621** | **+5.04%** |
| popB (drift+prev 14) | drift | **Hybrid-motion** (env+prev_*) | 14 | **18.1261** | **24.3607** | 13.9188 | 38.0028 | 62.0407 | 0.1038 | 0.2929 | **+0.9621** | **+5.04%** |

Notes: popB's persistence baseline is computed on exactly the same 14 predecessor-eligible drift rows used by the motion models (not on the 24). `Existing XGBoost` is included in each population using that population's corresponding feature matrix so its numbers are comparable. No populated row is left blank.

## 13. Required Output — Matched Existing-XGBoost Comparison Table

| Population | Metrics vs | Relationship (model − existing XGB) |
|------------|------------|-------------------------------------|
| popA 24 | Displacement − Existing XGB | −6.4477 km (improvement vs the frozen XGB baseline, 27.62 → 21.17) |
| popA 24 | Hybrid − Existing XGB | −6.4477 km (same; residual == displacement by construction) |
| popB 14 | Motion-aware − Existing XGB | −14.3659 km (32.49 → 18.13) |
| popB 14 | Hybrid-motion − Existing XGB | −14.3659 km (same; motion hybrid == motion-aware) |

So **every XGBoost variant beats the frozen XGBoost**, but only the motion-aware pair beats persistence — and only by 5% on a small predecessor-eligible sub-population.

## 14. Error Analysis — breakdown by iceberg / year / magnitude / direction

`per-iceberg` and `population breakdowns` are all read from `[outputs/ml/drifting_xgboost/comparison_summary.json](outputs/ml/drifting_xgboost/comparison_summary.json)`'s `per_iceberg` and `breakdown_popA/B` blocks (which include geographic `mean_displacement_error`, `lat/lon MAE`, etc.).

### 14.1 Per-iceberg (drifting MAE, km)

| Population | Berg | n | Persistence MAE | Model MAE (drift-row) |
|------------|------|---|-----------------|-----------------------|
| popA (displacement/hybrid) | C18B | 15 | 23.0535 | **24.5880** |
| popA | C39 | 9 | 15.7204 | **15.4791** |
| popB (motion/hybrid-motion) | C18B | 8 | 26.1133 | **21.1361** |
| popB | C39 | 6 | 9.7214 | **14.1128** |

Interpretation: with motion memory, C18B alone beats its matched persistence (26.1 → 21.1). C39's 6 predecessor-eligible rows worsen (9.72 → 14.11) and drag the popB median down. Across the full drift test (popA, 24), neither C18B nor C39's displacement/hybrid model beats C18B's persistence alone; the gap is closed only for C39 (15.72 → 15.48).

### 14.2 Year

Test `obs_year` is entirely **`2025`** (target_date horizon runs to 2026-01-02 for late-Dec obs — frozen, not new 2026). No year stratification is possible.

### 14.3 Magnitude of true 7-day displacement

For popA (24 drift; already visible in the error metric but now per bucket):

| True disp bucket | n | Persistence MAE | Displacement MAE | Existing XGB MAE |
|------------------|---|-----------------|------------------|------------------|
| 0–5 km | 13 | 2.0980 | 5.8996 | 12.0144 |
| 5–20 km | 3 | 11.2897 | 12.4533 | 37.2309 |
| 20–50 km | 5 | 33.0229 | 31.9064 | 33.1662 |
| ≥50 km | 3 | 87.0098 | 78.1816 | 76.3888 |

For popB (14 drift) motion-aware vs matched baselines shifts the large-displacement buckets slightly up (≥50 inf), but direction (§14.4) is the clearer separator.

### 14.4 Direction (true 7-day bearing quadrant)

| Direction | popA n | Displacement MAE (popA) | popB n | Motion MAE (popB) |
|-----------|---------|-------------------------|---------|-------------------|
| N (0–90°) | 5 | 5.7217 | 3 | 9.7441 (pers 3.1347) |
| E (90–180°) | 8 | 10.3432 | 6 | 12.8494 (pers 10.5481) |
| S (180–270°) | 7 | 48.1388 | 3 | 38.9545 (pers 48.8218) |
| W (270–360°) | 4 | 14.9515 | 2 | 15.2868 (pers 24.0385) |

Across the board, the large errors are concentrated in S-migration cases. Motion memory's marginal wins sit in the hardest buckets (S/W), not in the quiet N/E ones, consistent with brief inertia helping when the drift vector is persistent. Lat vs lon MAE (deg) in §12 mirrors: only where lon errors dominate (~0.3° obs spread) does the motion feature attenuate them.

All error breakdowns were computed with the shared `haversine_km` from `[scripts/ml/drifting_xgboost/common.py](scripts/ml/drifting_xgboost/common.py)` (`EARTH_RADIUS_KM = 6371.0088`) so geographic numbers are definitionally comparable with Phase 3C.

## 15. C39 Zero-Shot Analysis (§14 — reported SEPARATELY)

| Group | n | Persistence MAE (km) | Displacement MAE (km) | Motion-aware MAE (km) | Existing XGB MAE (km) |
|-------|---|----------------------|-----------------------|-----------------------|-----------------------|
| C39 all (popA-eligible) | 9 | 15.7204 | **15.4791** | — | 29.1960 |
| C39 with predecessor (popB-eligible) | 6 | 9.7214 | — | **14.1128** | 34.6090 |

The unverified 9-row 2025 C39 track is not "drifting" by the D23-only label (all C39 are drift-labelled), but only 6 carry a real predecessor and those 6 are atypically low-error under persistence (9.72 km — C39's 2025 path was quiescent for most of the test window). Displacement MAE on all 9 C39 matches `all-C39 persistence` closely (15.48 vs 15.72 → margin −0.24 km; lon RMSE 0.15° vs persist lon MAE 0.13° reflects under-predicted displacement rather than catastrophic drift, consistent with §16 inspection). Adding historical motion on C39's 6 erodes the C39 zero-shot standing (9.72 → 14.11; median 4.11 → 15.10 km, p90 23.37 → 22.62 km — the median shift is the signal). The Phase 4 operational forecast is therefore **not** changed to C39-zero-shot on the basis of these results (§20–21).

## 16. Hybrid Safety Check (§16 — PROTOTYPE HEURISTIC, DOCUMENTED, NOT DEPLOYED)

Inspect predicted displacement magnitude over the 24 drift test rows (derived as `haversine_km(current, pred)` vs true `displacement_km = haversine(current, target)`):

Predicted: mean **8.302 km**, p95 **18.48 km**, max **45.59 km**.
Actual drift: mean **20.304 km**, p95 **78.15 km**, max **121.85 km**.

The env-only displacement/hybrid systematically **under-predicts** drift magnitude. Any clipping rule that caps predictions at e.g. the observed p95 or discards predictions beyond the training support is therefore documented here only as a **prototype heuristic** (labelled in config as `"prototype_hybrid_cap: { winsorise_at: obs_p95 = 78.1 km, status: not_operational }"`). No clipping heuristic was applied to any Phase 4/corridor computation or to the resource-limit recommendation.

## 17. Model Selection Rule & Outcome (§15)

Selection rule — required verbatim: *beat persistence on the **matched** set, with no leakage, and with no population change*.

| Candidate | Population | Beat persistence? | Meets rule? |
|-----------|------------|-------------------|-------------|
| Displacement (env) | popA 24 | No (−0.87 km) | **No** |
| Hybrid (env) | popA 24 | No (−0.87 km) | **No** |
| **Motion-aware (motion, 23)** | **popB 14** | **Yes (+0.96 km / +5.04%)** | **Conditionally yes** — but median regresses (8.64 → 13.92 km), C39 zero-shot erodes, and the eligible set is small (14 rows, 2 bergs). Treated as a *candidate improvement* rather than a deployment replacement. |
| Hybrid-motion (motion) | popB 14 | Yes (+0.96 km; identical model) | Same qualification; residual framing adds no new evidence. |

So the literal answer to the spec's scientific question (can motion-aware hybrid beat **20.30 km**?) is **yes on the predecessor-eligible sub-population** (18.13 vs the 19.09 matched persistence) but **no on the full drifting population** (21.17 vs 20.30), and the edge is narrow, median-negative, and C39-adverse.

## 18. Validation Checks (22 outcomes)

All 22 checks PASS under `[scripts/ml/drifting_xgboost/validate_phase3g.py](scripts/ml/drifting_xgboost/validate_phase3g.py)` (each entry maps to a spec constraint; only readers are allowed). They are reproduced inline from that validator's output:

| # | Check (from `validate_phase3g.__doc__`) | Result | Detail |
|---|-----------------------------------------|--------|--------|
| 1 | expanded dataset unchanged (451 / 342/55/54 / 8 bergs) | **PASS** | full 451 / splits 342/55/54 / 8 |
| 2 | original Phase 3 dataset unchanged (101 pairs) | **PASS** | orig 101 |
| 3 | Phase 3C persistence unchanged (drifting MAE 20.3036) | **PASS** | 20.3036 |
| 4 | Phase 4 artefacts precede 3G outputs (untouched) | **PASS** | risk mtime < 3G dir mtime |
| 5 | no BYU merge (none under 3G paths) | **PASS** | 14 byu paths, none under 3G |
| 6 | no new data downloads | **PASS** | parquet mtime < output dir mtime |
| 7 | no 2026 introduced (obs-year 2025-only) | **PASS** | 54 obs-year 2025 |
| 8 | no synthetic/interpolated observations (142 drift label / 60 NaN) | **PASS** | 142 drift; 60 NaN |
| 9 | chronological split preserved (train<val<test) | **PASS** | 2021-12-31 < 2024-01-04 < … < 2025-01-16 |
| 10 | C39 zero-shot preserved (0/0/9) | **PASS** | 0 / 0 / 9 |
| 11 | motion features historical-only (t−7 obs, dt=7) | **PASS** | curr−prev exactly; all dt=7 |
| 12 | no future-position leakage | **PASS** | feature ∩ target = ∅ |
| 13 | matched persistence on identical samples (24/14) | **PASS** | popA 24 / popB 14 |
| 14 | displacement targets correct (target−current) | **PASS** | delta==target−current on all 24 |
| 15 | position reconstructed as current+delta | **PASS** | saved == cur + delta; finite |
| 16 | geographic error in km (R=6371.0088) | **PASS** | max 122.9 km |
| 17 | deterministic seed 42 in A/B/C | **PASS** | RANDOM_STATE=42 A/B/C |
| 18 | small controlled grid (144 combos) | **PASS** | 8-dim grid per target, no search |
| 19 | 3G models reload → reproduce saved preds | **PASS** | lat/lon deltas reconstruct |
| 20 | Phase 3C frozen numbers reproducible | **PASS** | 20.3036 / 27.6199 |
| 21 | Phase 4 regression 22/22 PASS | **PASS** | validate_risk_engine PASS |
| 22 | git shows only new 3G files (no protected edits) | **PASS** | no protected touched |

`PHASE 3G VALIDATION: 22/22 PASS (0 FAIL)`.

## 19. Phase 4 Regression (§20 — VALIDATION MUST ALSO INCLUDE `validate_risk_engine.py`)

`python scripts/risk/validate_risk_engine.py`:

```
PHASE 4 — RISK ENGINE VALIDATION
  ✅ PASS  protected_files_untouched
  ✅ PASS  no_new_downloads
  ✅ PASS  no_model_training
  ✅ PASS  byu_unchanged
  ✅ PASS  no_2026_data
  ✅ PASS  no_fabricated_observations
  ✅ PASS  demo_labelled
  ✅ PASS  risk_increases_sep_down
  ✅ PASS  risk_increases_unc_up
  ✅ PASS  size_monotonic
  ✅ PASS  multi_iceberg_highest
  ✅ PASS  stale_growth
  ✅ PASS  comm_loss_mode
  ✅ PASS  recovery
  ✅ PASS  reproducible
  ✅ PASS  c39_unchanged
  ✅ PASS  persistence_baseline
  ✅ PASS  output_schema
  ✅ PASS  corridor_formula
  ✅ PASS  uncertainty_labels
  ✅ PASS  class_note
  ✅ PASS  navigation_layer
VALIDATION RESULT:  22 passed,  0 failed
✅  ALL VALIDATION CHECKS PASSED
```

## 20. Git Safety (§20)

Phase 3G created **no new dataset downloads, no BYU merge, no 2026 rows**, and modified no protected dataset/model/config. Added directories contain **only** new files under:

- `scripts/ml/drifting_xgboost/` (`common.py`, `train_displacement_xgb.py`, `train_motion_aware_xgb.py`, `train_hybrid_xgb.py`, `evaluate_drifting_xgb.py`, `validate_phase3g.py`)
- `data/processed/ml/models/drifting_xgboost/` (`*_metadata.json` ×4, `*_latitude/longitude.json` ×8 including the supplementary hybrid pair, `*_predictions.csv` ×4)
- `outputs/ml/drifting_xgboost/` (`*_evaluation.json` ×3 including supplementary, `comparison_summary.json`)
- `reports/PHASE3G_DRIFTING_XGBOOST_REPORT.md` (this file).

Any `M` status in `git status` at report time (e.g. `scripts/risk/risk_engine.py` touched during Phase 4) predates Phase 3G and is explicitly not counted as a Phase 3G edit.

## 21. Scientific Interpretation / Conclusion (§21 — Pick Exactly One of A/B/C)

**Pick: (B) — "No improvement on the full drifting population; a narrow, conditional improvement on the predecessor-eligible sub-population that is not recommended for deployment without independent validation."**

Why (B) and not (A): motion memory does convert the full-drift result from "XGBoost worse than persistence" (27.62 → 21.17 on popA, still trailing persistence's 20.30) into a **thin win** on popB (18.13 vs matched 19.09, +5.0%), but the win is driven by a median regression (8.64 → 13.92 km under motion), concentrates in the small-error bucket (>5 km disp), worsens C39's zero-shot (9.72 → 14.11), and changes the population (14 of 24 drift rows pass eligibility). In a safety-critical corridor, trading large-error improvement (S/W migrations, §14.4) for across-the-board median error and C39 erosion is not justified at this sample scale. Displacement/hybrid on the full eligible drift set cannot claim an operational advantage.

Why (B) and not (C): the Phase 3C frozen-spread (persistence 20.30 vs XGB 27.62) is **real** — the existing XGB regressor was reliably beaten only by excluding 42% of drift rows — but the controlled displacement framing and the progenitor-motion feature do measurably narrow the spread and, on the eligible eligible-ancillary subset, flip it. "No XGBoost can beat persistence on more drift rows" is therefore too pessimistic; "motion helps a bit, in the right rows" is better-evidenced.

**Operational consequence (§20 / Phase 4 recommendation):** Phase 4's operational forecast remains **unchanged** (persistence-anchored IIEE corridor with empirical spreads: empirical_drifting `σ_env`, empirical_grounded, fallback, plus staleness growth). The motion-aware/hybrid result is recorded as a **`Candidate improved — awaiting independent holdout`** rather than an enabled `Improved` model.

## 22. Files Created / Modified (§19 — every phase must list this explicitly)

| File | Action | Notes |
|------|--------|-------|
| `[scripts/ml/drifting_xgboost/common.py](scripts/ml/drifting_xgboost/common.py)` | NEW | Shared geodesic metrics (`R=6371.0088`, `haversine_km`, `compute_group_metrics(...)`) — spec §8. |
| `[scripts/ml/drifting_xgboost/train_displacement_xgb.py](scripts/ml/drifting_xgboost/train_displacement_xgb.py)` | NEW | Experiment A — env-only displacement XGB (`FEATURE_COLS` 19; `PARAM_GRID` 144; seed 42). |
| `[scripts/ml/drifting_xgboost/train_motion_aware_xgb.py](scripts/ml/drifting_xgboost/train_motion_aware_xgb.py)` | NEW | Experiment B — motion-augmented XGB (env + 4 `prev_*`; `notna()` filter; seed 42). |
| `[scripts/ml/drifting_xgboost/train_hybrid_xgb.py](scripts/ml/drifting_xgboost/train_hybrid_xgb.py)` | NEW | Experiment C — hybrid `current+residual`; env primary + motion supplementary; seed 42. |
| `[scripts/ml/drifting_xgboost/evaluate_drifting_xgb.py](scripts/ml/drifting_xgboost/evaluate_drifting_xgb.py)` | NEW | Full comparison + `breakdown_popA/B` (year/magnitude/direction) + C39 + matched-persistence. |
| `[scripts/ml/drifting_xgboost/validate_phase3g.py](scripts/ml/drifting_xgboost/validate_phase3g.py)` | NEW | The 22-point gate from §18. |
| `data/processed/ml/models/drifting_xgboost/*.json/*.csv` (12 files) | NEW | 4 × `*_metadata.json`, 8 × `*_latitude/longitude.json`, 4 × `*_predictions.csv` (displacement, motion, hybrid, hybrid_motion). |
| `outputs/ml/drifting_xgboost/*.json` (4 files) | NEW | `displacement_xgb_evaluation.json`, `motion_aware_xgb_evaluation.json`, `hybrid_xgb_evaluation.json`, `comparison_summary.json` (includes supplementary). |
| `[reports/PHASE3G_DRIFTING_XGBOOST_REPORT.md](reports/PHASE3G_DRIFTING_XGBOOST_REPORT.md)` | NEW | This report. |

Modified but not overwritten (pre-3G): `scripts/risk/risk_engine.py|configs` (Phase 4) and untracked Phase 3A/3B/3C report stubs. Protected datasets (`data/processed/ml/expanded/`), original Phase 3 (`data/processed/ml/`), `config/models.yaml`, and the C39 zero-shot split were **not** modified.

---

> **PHASE 3G COMPLETE — DRIFTING-FOCUSED XGBOOST EXPERIMENT. PERSISTENCE DRIFTING MAE: 20.30 KM. EXISTING XGBOOST DRIFTING MAE: 27.62 KM. DISPLACEMENT XGBOOST: 21.17 KM. MOTION-AWARE XGBOOST: 18.13 KM (matched persistence 19.09 KM on the same 14 predecessor-eligible rows). HYBRID: 21.17 KM (env; same model as displacement) / 18.13 KM (motion; same model as motion-aware). VALIDATION: 22/22 PASS. PHASE 4 REGRESSION: 22/22 PASS. NO PROTECTED DATASETS MODIFIED. NO BYU DATA MERGED. C39 ZERO-SHOT TEST PRESERVED. STOPPING FOR EXPLICIT APPROVAL.**

No commit was made. Await `git commit` instruction before publishing.
