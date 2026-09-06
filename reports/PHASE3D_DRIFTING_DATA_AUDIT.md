# Phase 3D — Drifting-Iceberg Data Availability Audit

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-05

**Status:** ✅ AUDIT COMPLETE — NO DOWNLOADS, NO MODEL TRAINING, NO DATA MODIFICATION

---

## 1. Executive Summary

This audit examines whether additional genuine drifting-iceberg trajectory data is available and whether acquiring it would materially improve the current trajectory-prediction experiment. The current Phase 3C expanded dataset (451 pairs, 8 icebergs, 142 drifting / 309 grounded) has been validated 19/19, with persistence remaining the best overall and best drifting predictor. No ML model beats persistence on drifting icebergs.

**Key finding:** The bottleneck is **drifting-trajectory scarcity and iceberg diversity**, not total dataset size. The NIC archive on disk already contains 643 valid 7-day pairs across 11 icebergs (2016–2026), but only 172 are drifting. The expanded Phase 3C dataset used 7 feature-stack years (2016, 2017, 2019, 2020, 2021, 2024, 2025) capturing 142 drifting pairs. The remaining 30 drifting pairs are in years blocked by missing environmental data (2018, 2022, 2023, 2026).

---

## 2. Iceberg Trajectory Inventory

### 2.1 Current Source: NIC Weekly Archive (Primary & Only Operational Source)

| Property | Value |
|---|---|
| **Source name** | US National Ice Center (NIC) Antarctic Icebergs CSV archive |
| **Raw files** | 608 weekly CSVs, 2014-11-07 → 2026-08-27 (Antarctic-wide) |
| **Processed file** | `data/processed/icebergs/east_prydz_bay_icebergs.csv` (796 obs, 11 IDs) |
| **Access** | Public HTTP, no auth (`scripts/data/download_icebergs.py`) |
| **Temporal resolution** | Weekly (nominal); actual gaps: 643×7-day, 67×6-day, 62×8-day, 6×14-day |
| **Spatial coverage** | East Prydz Bay bbox (S−70 N−66 W72 E80) |
| **Variables** | Iceberg ID, Length/Width (NM), Lat/Lon, Last Update, observation_date |
| **Observation type** | Directly observed centroid positions (analyst-interpreted satellite imagery) |
| **Schema stability** | Two schemas handled by `process_icebergs.py` (Nov 2014–Apr 2024: 7-col + Remarks; Apr 2024–Aug 2026: 9-col + Area) |

### 2.2 Icebergs in Processed CSV (796 obs, East Prydz Bay)

| Iceberg | NIC Obs | Valid 7-day Pairs | Years Present | Drift Style | Mean Weekly Disp (km) |
|---|---:|---:|---|---|---|
| **D23** | 551 | 471 | 2016–2026 | **Grounded** (stationary ~0.1 km/week) | 0.11 |
| **C18B** | 75 | 40 | 2024–2025 | **Fast drifter** (cross-bay, >100 km) | 14.7 |
| **D27** | 40 | 38 | 2020–2021 | Drifter (moderate) | 10.3 |
| **B39** | 30 | 28 | 2019–2020 | Drifter (moderate-fast) | 31.7 |
| **C39** | 30 | 21 | 2025–2026 | Drifter (moderate) | 15.7 |
| **D22** | 14 | 11 | 2019 | Drifter (moderate) | 23.3 |
| **D28** | 11 | 9 | 2019–2020 | Short track (moderate) | 22.6 |
| **D21B** | 8 | 7 | 2017 | Short track | 30.5 |
| **D15C** | 19 | 9 | **2026 only** | **Quasi-stationary** | 1.97 |
| **D15D** | 17 | 9 | **2026 only** | **Quasi-stationary** | 1.10 |
| **B09I** | 1 | 0 | 2019 | Single observation | — |

### 2.3 Icebergs in Current 451-Pair Expanded Dataset (8 IDs)

| Iceberg | Pairs | Split Distribution | Drift Status |
|---|---:|---|---|
| **D23** | 309 | train=249, val=30, test=30 | **Grounded** (68.5% of all pairs) |
| **C18B** | 40 | val=25, test=15 | Drifting (8.9%) |
| **D27** | 38 | train=38 | Drifting (8.4%) |
| **B39** | 28 | train=28 | Drifting (6.2%) |
| **D22** | 11 | train=11 | Drifting (2.4%) |
| **C39** | 9 | test=9 | Drifting (2.0%) |
| **D28** | 9 | train=9 | Drifting (2.0%) |
| **D21B** | 7 | train=7 | Drifting (1.6%) |

**Critical bias:** D23 (grounded) = **68.5% of all pairs, 61% of train, 55% of val, 56% of test**.

---

## 3. Additional Candidate Icebergs Not in 451-Pair Set

### 3.1 From NIC Archive (3 IDs)

| Iceberg | NIC Obs | Valid 7-day Pairs | Years | Drift Assessment | Suitable for ML? |
|---|---:|---:|---|---|---|
| **D15C** | 19 | 9 | 2026 | Quasi-stationary (mean 1.97 km/wk) | **NO** — 2026 data explicitly banned; grounded-like |
| **D15D** | 17 | 9 | 2026 | Quasi-stationary (mean 1.10 km/wk) | **NO** — 2026 data explicitly banned; grounded-like |
| **B09I** | 1 | 0 | 2019 | Single obs, 0 pairs possible | **NO** — no trajectory |

### 3.2 From Feature-Stack Blocked Years (Potential if Environmental Data Acquired)

| Year | Missing Environmental Input | Drifting Pairs Blocked | Icebergs Affected |
|---|---|---|---|
| **2018** | ERA5 (0/12 monthly files) | 0 (D23 only) | D23 |
| **2022** | ERA5, NSIDC, GLORYS all missing | 0 (D23 only) | D23 |
| **2023** | ERA5, NSIDC, GLORYS all missing | 0 (D23 only) | D23 |
| **2026** | ERA5 missing, NSIDC missing, GLORYS partial (174 d) | **30 drifting** | C39 (12), D15C (9), D15D (9), D23 (21) |

**Additional drifting pairs available if environmental data acquired:**
- **2018:** 0 drifting pairs (D23 only)
- **2022:** 0 drifting pairs (D23 only)
- **2023:** 0 drifting pairs (D23 only)
- **2026:** 30 drifting pairs (C39=12, D15C=9, D15D=9) — but D15C/D are quasi-stationary; **only C39 (12 pairs) is genuinely drifting**

### 3.3 External Sources (Documented in Phase 3A Audit)

| Source | Trajectory Type | Verified Individual Trajectories? | Temporal Res | Integration Effort | Leakage Risk |
|---|---|---|---|---|---|
| **BYU Antarctic Iceberg Database** | Scatterometer (25 km) + NIC merge | **YES** — per-iceberg CSVs (consolidated DB) | Daily (statistical, gap-filled) / Weekly | Medium (new ingest mapper + dedup) | Moderate (duplicate IDs with NIC; interpolated days) |
| **NSIDC-0684 MEaSUREs (IR)** | AVHRR/MODIS infrared centroids | **YES** — large named bergs only | Daily (cloud-gap interpolated) | Medium–High (HDF5 ingest + centroid + flag filter) | Moderate–High (cloud-gap interpolation = synthetic) |
| **Sentinel-1 SAR** | SAR-derived (custom tracking) | **NO** — no off-the-shelf trajectory catalogue | 2–12 day revisit (polar) | High (custom detection/tracking pipeline) | Low (independent observations) |
| **MODIS/VIIRS (optical)** | Research workflows only | **NO** — no operational catalogue | Daily (cloud-blocked) | N/A | N/A |
| **AMSR2 (passive microwave)** | Cho et al. 2025 study | **NO** — single-berg demo, no catalogue | Daily (all-weather) | N/A | N/A |
| **ESA CCI / NSIDC-0615 / "HEAD DB"** | **NON-EXISTENT** | **VERIFIED ABSENT** | — | — | — |

---

## 4. Drifting-Iceberg Priority Ranking

Ranked by valid drifting pairs, duration, continuity, independence, and chronological utility:

| Rank | Iceberg | Drifting Pairs | Years | Track Duration | Independence | Chronological Utility | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | **C18B** | 40 | 2024–2025 | 17 months | Unique quadrant | Already in val/test | **IN DATASET** |
| 2 | **C39** | 21 | 2025–2026 | 6 months | Unique quadrant | Zero-shot test (9) + 12 more in 2026 | **PARTIAL IN DATASET** |
| 3 | **D27** | 38 | 2020–2021 | 10 months | Unique quadrant | Already in train | **IN DATASET** |
| 4 | **B39** | 28 | 2019–2020 | 8 months | Unique quadrant | Already in train | **IN DATASET** |
| 5 | **D22** | 11 | 2019 | 3 months | Unique quadrant | Already in train | **IN DATASET** |
| 6 | **D21B** | 7 | 2017 | 2 months | Unique quadrant | Already in train | **IN DATASET** |
| 7 | **D28** | 9 | 2019–2020 | 7 months | Overlaps B39/D27 | Already in train | **IN DATASET** |
| 8 | **D15C** | 9 | 2026 only | 4 months | New ID | **Banned year** | EXCLUDED |
| 9 | **D15D** | 9 | 2026 only | 4 months | New ID | **Banned year** | EXCLUDED |
| 10 | **B09I** | 0 | 2019 | Single obs | New ID | 0 pairs | EXCLUDED |

**No new genuine drifting trajectories outside the current dataset are available without:**
- Acquiring ERA5/NSIDC/GLORYS for 2026 (adds 12 C39 drifting pairs, but 2026 is banned)
- Acquiring ERA5 for 2016/2018 (adds 0 drifting pairs — D23 only)
- Building SAR custom tracking (new research effort)

---

## 5. Dataset Bias Analysis

### 5.1 Pairs per Iceberg

| Iceberg | Pairs | % of Total | Cumulative % |
|---|---:|---:|---:|
| D23 | 309 | 68.5% | 68.5% |
| C18B | 40 | 8.9% | 77.4% |
| D27 | 38 | 8.4% | 85.8% |
| B39 | 28 | 6.2% | 92.0% |
| D22 | 11 | 2.4% | 94.4% |
| C39 | 9 | 2.0% | 96.4% |
| D28 | 9 | 2.0% | 98.4% |
| D21B | 7 | 1.6% | 100.0% |

**D23 dominates with 68.5% of all pairs.**

### 5.2 Drifting vs Grounded

| Category | Pairs | Percentage |
|---|---:|---:|
| Grounded (D23) | 309 | 68.5% |
| Drifting (7 icebergs) | 142 | 31.5% |

### 5.3 Pairs per Year

| Year | Total | Drifting | Grounded | Feature Stack |
|---|---:|---:|---:|---|
| 2016 | 49 | 0 | 49 | ✅ Built |
| 2017 | 57 | 7 | 50 | ✅ Built |
| 2018 | 50 | 0 | 50 | ❌ BLOCKED (ERA5 missing) |
| 2019 | 66 | 18 | 48 | ✅ Built |
| 2020 | 103 | 54 | 49 | ✅ Built (baseline) |
| 2021 | 67 | 14 | 53 | ✅ Built |
| 2022 | 52 | 0 | 52 | ❌ BLOCKED (all missing) |
| 2023 | 39 | 0 | 39 | ❌ BLOCKED (all missing) |
| 2024 | 55 | 25 | 30 | ✅ Built |
| 2025 | 54 | 24 | 30 | ✅ Built |
| 2026 | 51 | 30 | 21 | ❌ BLOCKED (ERA5/NSIDC missing) |

### 5.4 Drifting Pairs per Year

| Year | Drifting Pairs | Cumulative Drifting |
|---|---:|---:|
| 2017 | 7 | 7 |
| 2019 | 18 | 25 |
| 2020 | 54 | 79 |
| 2021 | 14 | 93 |
| 2024 | 25 | 118 |
| 2025 | 24 | 142 |
| **Total** | **142** | — |

### 5.5 Observations per Iceberg (Raw NIC)

| Iceberg | NIC Obs | Years Span |
|---|---:|---|
| D23 | 551 | 2016–2026 |
| C18B | 75 | 2024–2025 |
| D27 | 40 | 2020–2021 |
| B39 | 30 | 2019–2020 |
| C39 | 30 | 2025–2026 |
| D22 | 14 | 2019 |
| D28 | 11 | 2019–2020 |
| D21B | 8 | 2017 |
| D15C | 19 | 2026 |
| D15D | 17 | 2026 |
| B09I | 1 | 2019 |

### 5.6 Train/Val/Test Distribution by Iceberg

| Split | Iceberg | Pairs |
|---|---|---:|
| **Train (342)** | D23 | 249 |
| | D27 | 38 |
| | B39 | 28 |
| | D22 | 11 |
| | D28 | 9 |
| | D21B | 7 |
| **Val (55)** | D23 | 30 |
| | C18B | 25 |
| **Test (54)** | D23 | 30 |
| | C18B | 15 |
| | C39 | 9 |

### 5.7 Train/Val/Test Distribution by Drifting Status

| Split | Drifting | Grounded | Total |
|---|---:|---:|---:|
| Train | 93 | 249 | 342 |
| Val | 25 | 30 | 55 |
| Test | 24 | 30 | 54 |

---

## 6. Test-Set Diversity Assessment

| Metric | Value |
|---|---:|
| **Test icebergs** | 3 (D23, C18B, C39) |
| **Drifting test samples** | 24 (C18B=15, C39=9) |
| **Grounded test samples** | 30 (D23=30) |
| **C39 zero-shot** | **YES** — 9 test pairs, 0 train/val |
| **Single iceberg dominates?** | **YES** — D23 = 56% of test set |

**Critical limitation:** The test set contains only **2 drifting icebergs** (C18B seen in val, C39 zero-shot). Both drifting icebergs in test have **0 training pairs** (C18B only in val/test; C39 only in test). This means the experiment has **never evaluated a drifting iceberg with training representation**. Grounded D23 (30/54 = 56%) dominates test metrics, making overall MAE heavily biased toward the easy persistence task for stationary icebergs.

---

## 7. External Source Assessment

### 7.1 BYU Antarctic Iceberg Tracking Database (Tier 2 in Phase 3A)

- **What it provides:** Per-iceberg CSVs (consolidated DB) + daily statistical DB with environment mask (land/sea-ice/open-ocean/no-data)
- **Individual trajectories:** **YES** — verified CSV per iceberg (e.g., `b27.csv`)
- **Temporal coverage:** 1992 → April 2025 (consolidated); 1978 → August 2023 (statistical)
- **Spatial resolution:** ~25 km (scatterometer) — large tabular bergs only
- **Overlap with NIC:** Incorporates NIC positions → **duplicate iceberg identity risk**
- **Leakage:** Statistical DB interpolates gap days (environment mask = no-data) — **must discard interpolated rows**
- **Integration:** New mapper needed; dedup by (date, proximity) before split; keep 7-day targets

### 7.2 NSIDC-0684 MEaSUREs (Tier 3 in Phase 3A)

- **What it provides:** Daily IR centroids + boundaries for large named bergs (A/B/C/D naming)
- **Individual trajectories:** **YES** — but heavy overlap with NIC large-berg population
- **Temporal coverage:** ~1978 → present, updated annually
- **Cloud gaps:** Interpolated across cloud cover — **must discard interpolated rows**
- **Leakage:** Moderate–High (interpolated positions = synthetic targets)

### 7.3 Sentinel-1 SAR Custom Tracking (Tier 4 in Phase 3A)

- **What it provides:** SAR imagery from Copernicus Data Space; trajectories must be **derived locally**
- **Individual trajectories:** **NO** — no off-the-shelf catalogue exists
- **Potential:** Sub-weekly (2–12 day), 10–100 m, all-weather, size-complete (below NIC 20 sq nm gate)
- **Effort:** High — custom detection/tracking pipeline (Phase-4 scale)
- **Recent Prydz Bay SAR studies:** Mu et al. 2025 (EGUsphere, daily distribution maps), Chen et al. 2026 (GEE annual census 2018–2023, Zenodo DOI 10.5281/zenodo.17165466)

### 7.4 Rejected Sources (Verified Non-Existent or Inappropriate)

- **ESA CCI Icebergs** — no such ECV project (404 on climate.esa.int)
- **NSIDC-0615** — Greenland GPS traverse, not icebergs
- **NSIDC-0524** — Thwaites IPY geophysics, not icebergs
- **"HEAD iceberg database"** — HEAD is a drift model, not a distributed trajectory set
- **SOOS / CMEMS operational iceberg tracking** — no verified product
- **PANGAEA iceberg DOIs** — multiple AI-cited DOIs failed direct fetch verification

---

## 8. Data Quality / Fabrication Risk

**Explicitly rejected as violating constraints:**

- ❌ Fabricated trajectories from interpolation (6-day/8-day/14-day gaps → not 7-day)
- ❌ Gap-filled positions as training targets (BYU statistical DB, NSIDC-0684 cloud gaps)
- ❌ Inferred iceberg IDs from unnamed scatterometer tracks
- ❌ Mixing incompatible coordinate definitions across sources without dedup
- ❌ Future information leakage (2026 data banned; any new year must obey chronological split)
- ❌ Silent substitution of ORAS5 monthly for GLORYS daily (degraded baseline, explicitly marked)
- ❌ 2022, 2023, 2026 data downloads (banned by current phase instructions)

---

## 9. Actual Bottleneck Determination

### 9.1 Primary Bottleneck: **Drifting-Trajectory Scarcity + Iceberg Diversity**

| Evidence | Value |
|---|---|
| Total pairs | 451 (not small per se) |
| Drifting pairs | 142 (31.5%) |
| Distinct drifting icebergs | 7 |
| Drifting icebergs with >20 pairs | 3 (C18B=40, D27=38, B39=28) |
| Drifting icebergs in train | 5 (B39, D27, D22, D28, D21B) |
| Drifting icebergs in val | 1 (C18B) |
| Drifting icebergs in test | 2 (C18B, C39) — **both zero training pairs** |
| Test drifting samples | 24 (vs 30 grounded) |

**This is a sample diversity problem, not a total-N problem.** The 142 drifting pairs span only 7 icebergs, with the two test drifters having no training representation at all.

### 9.2 Secondary Bottleneck: **Grounded-Iceberg Dominance (D23 = 68.5%)**

- Overall metrics are pulled toward persistence (easy for grounded)
- Models optimized on total loss learn the grounded regime, fail on drifting
- Feature importance dominated by position/static (D23 has no drift signal)

### 9.3 Tertiary: **Temporal Resolution (Weekly Only)**

- 6/8/14-day gaps drop ~25% of raw observations
- No sub-weekly dynamics available from NIC source
- Previous-step features NaN for trajectory starts (6 rows in 451 pairs)

### 9.4 NOT the bottleneck:
- ❌ Total dataset size (451 is adequate for baseline)
- ❌ Feature limitations (25 features cover wind/ocean/ice/position/static)
- ❌ Environmental data availability (ERA5/NSIDC/GLORYS available for all years 2016–2025 if downloaded)

---

## 10. Would Adding Grounded Observations Help?

**NO.** Adding D23-dominated years (2016, 2018, 2022, 2023) would:
- Increase total pairs (to ~643)
- **Increase grounded fraction** (D23 already 73% of all-year NIC pairs)
- **Worsen the drift/grounded ratio** in train/val/test
- Not add a single new drifting iceberg
- Make overall MAE even more persistence-biased

The only years adding drifting pairs are **2017, 2019, 2020, 2021, 2024, 2025** — **all already in the expanded dataset**. The 2018/2022/2023/2026 additions are D23-dominated.

---

## 11. Desirable Additional Drifting Pairs

**Recommendation: ~200–300 additional genuine drifting pairs** before the next ML experiment becomes substantially more informative.

**Basis:**
- Current drifting N = 142 across 7 icebergs (median 18 pairs/iceberg)
- ML literature rule of thumb: **≥30–50 samples per class/regime** for reliable non-linear fitting
- Need ≥4–5 additional drifting icebergs with ≥30 pairs each to diversify drift regimes
- C18B (40 pairs) shows fast drift is learnable if represented in train
- Target: 5+ drifting icebergs in **train** with 30+ pairs each, plus **val/test holdout of unseen drifters**

**How to get them (in priority order):**
1. **BYU consolidated DB** — captures additional Prydz Bay drifters NIC misses (unnamed + sub-weekly); filter to observed rows only
2. **ERA5/NSIDC/GLORYS for 2026** — adds C39 (12 more drifting pairs) — but 2026 is currently banned
3. **SAR custom tracking** — the only route to sub-weekly, size-complete, all-weather trajectories (Phase 4)

---

## 12. Recommendations

### RANK 1 — Most Valuable, Lowest Risk
**Integrate BYU Antarctic Iceberg Tracking Database (observed-only daily positions)**

- **Action:** Build ingest mapper for BYU consolidated CSV + statistical DB; dedup against NIC by (date, lat/lon proximity); keep only observed (non-interpolated) rows; append to NIC timeline before chronological split; rebuild expanded dataset with same 25 FEATURE_COLS.
- **Yield:** Daily-resolution input history for existing icebergs + new unnamed bergs in Prydz Bay; potentially 50–150 additional drifting pairs with sub-weekly dynamics.
- **Risk:** Medium (dedup/flag discipline); no new environmental data needed; same 25 features.
- **Why first:** Leverages existing NIC investment; directly addresses drift-diversity gap; no external download risk (BYU HTTP is open).

### RANK 2 — Second Best
**Complete environmental forcing for 2018 (ERA5 only) and re-evaluate**

- **Action:** Download ERA5 2016 & 2018 (2 years × 12 monthly = 24 files, ~2 hrs); build 2016/2018 feature stacks; rebuild expanded dataset to include 2018.
- **Yield:** **+0 drifting pairs** (2018 is D23 only) — but adds **chronological continuity** and better D23 statistics for stationarity modeling.
- **Risk:** Low (verified pipeline, only ERA5 missing).
- **Why second:** Completes the 2016–2021 contiguous train window; but does not fix drift scarcity — pure grounding statistics.

### RANK 3 — Optional (Long-Term)
**Sentinel-1 SAR Custom Tracking for Prydz Bay**

- **Action:** Build SAR detection/tracking pipeline on Copernicus Data Space EW_GRDM scenes; produce sub-weekly trajectory catalogue for all detectable sizes.
- **Yield:** Size-complete, all-weather, 2–12 day trajectories — breaks the large-berg-only bias.
- **Risk:** High effort (Phase-4 scale); no turnkey extractor; requires SAR expertise.
- **Why third:** Correct long-term direction but not a near-term Phase-3D action.

---

## 13. Explicit Do/Don't

| Action | Recommendation |
|---|---|
| **Download BYU data** | **WORTH COLLECTING** — highest value per effort |
| **Download NSIDC-0684** | **WORTH COLLECTING** — as cross-validation only (heavy NIC overlap, interpolation caveat) |
| **Download 2016/2018 ERA5** | **WORTH COLLECTING** — completes contiguous train window, but 0 drifting pairs added |
| **Download 2022/2023 ERA5/NSIDC/GLORYS** | **NOT RECOMMENDED** — 0 drifting pairs added (D23 only) |
| **Download 2026 data** | **BANNED** — explicit instruction for this phase |
| **Build SAR trajectories** | **RESEARCH TRACK** — Phase 4, not this phase |
| **Interpolate 6/8/14-day gaps** | **FORBIDDEN** — fabrication rule |
| **Use ORAS5 as GLORYS substitute** | **FORBIDDEN** — degraded baseline, must not silently replace |
| **Retrain models now** | **NOT RECOMMENDED** — bottleneck is data, not model |

---

## 14. Is Current 451-Pair Dataset Sufficient?

**For a final baseline experiment: YES.**
- 451 pairs with strict chronological split, 25 features, 3 models, persistence baseline, zero-shot C39 isolation, 19/19 validation pass
- Sufficient to establish that **persistence beats all ML at this sample scale and drift/grounded mix**

**For a meaningful ML-vs-persistence comparison on drifting icebergs: NO.**
- Test set has 24 drifting samples from 2 icebergs, both zero training representation
- Grounded bias (D23=56% of test) makes overall MAE uninformative for drift skill
- No drifting iceberg has train+val+test coverage to assess generalization

**Another expansion is JUSTIFIED but must target drifting diversity, not total N.**

---

## 15. File Integrity Verification

| Dataset | Status | Verification |
|---|---|---|
| **Phase 1 data** | **UNCHANGED** | Raw NIC archive (608 CSVs) untouched; `east_prydz_bay_icebergs.csv` mtime 2025-05-04 |
| **Phase 2 data** | **UNCHANGED** | ERA5/NSIDC/GLORYS/GEBCO raw + processed files mtime ≤ 2025-09-04; 2020 feature stack mtime 2025-09-04 |
| **Original Phase 3 dataset** | **UNCHANGED** | `data/processed/ml/full.parquet` = 101 pairs, 4 icebergs, mtime 2025-09-04 |
| **Phase 3C expanded dataset** | **UNCHANGED** | `data/processed/ml/expanded/full.parquet` = 451 pairs, 8 icebergs, mtime 2025-09-05 (build date) |
| **Phase 3C models** | **UNCHANGED** | All models in `data/processed/ml/expanded/models/` reload & reproduce predictions; validation 19/19 PASS |
| **No downloads started** | **CONFIRMED** | No network calls in this session; git status shows only new reports/scripts |
| **No models trained** | **CONFIRMED** | Only validation script run |

---

## 16. Final Audit Output

| Field | Value |
|---|---|
| **STATUS** | AUDIT COMPLETE |
| **CURRENT PAIRS** | 451 |
| **CURRENT ICEBERGS** | 8 |
| **CURRENT DRIFTING PAIRS** | 142 |
| **CURRENT GROUNDED PAIRS** | 309 |
| **ADDITIONAL CANDIDATE ICEBERGS** | 3 (D15C, D15D, B09I — all unsuitable: 2026 banned, 0 pairs) |
| **ADDITIONAL POTENTIAL DRIFTING PAIRS** | 30 (all in 2026: C39=12, D15C=9, D15D=9 — but 2026 banned; 0 in 2018/2022/2023) |
| **CURRENT MAIN BOTTLENECK** | Drifting-trajectory scarcity + iceberg diversity (not total dataset size) |
| **BEST NEXT ACTION** | Integrate BYU observed-only daily trajectories (deduped, gap-flag filtered) |
| **SECOND-BEST ACTION** | Download ERA5 2016/2018 for chronological continuity (0 drifting pairs added) |
| **NOT RECOMMENDED** | 2022/2023/2026 data; gap interpolation; SAR custom tracking this phase |
| **SHOULD WE COLLECT MORE DATA** | **YES** — specifically BYU drifting trajectories |
| **IF YES: EXACTLY WHAT DATA** | BYU consolidated + statistical DB (observed rows only), filtered to East Prydz Bay bbox, deduped against NIC |
| **NO DOWNLOADS PERFORMED** | **YES** |
| **NO MODELS TRAINED** | **YES** |

---

**STOP HERE.**  
**WAIT FOR EXPLICIT APPROVAL BEFORE ANY DOWNLOAD OR DATA MODIFICATION.**