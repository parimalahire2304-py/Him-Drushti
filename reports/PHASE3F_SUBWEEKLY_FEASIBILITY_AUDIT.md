# Phase 3F — Sub-Weekly Trajectory Feasibility Audit

**Project:** Prototype-1 · AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-06  
**Status:** ✅ FEASIBILITY AUDIT COMPLETE — NO MODELS TRAINED, NO EXISTING DATASETS MODIFIED

---

## Executive Summary

This audit evaluates whether the BYU v8.0 **observed-only** consolidated database can support a scientifically valid **sub-weekly** (1, 2, 3, 5, 7-day) iceberg trajectory experiment in East Prydz Bay **without** modifying any existing Phase 1/2/3/3C dataset or split.

**Key finding:** BYU contains substantial **raw** sub-weekly pair counts (7,939 at 1-day → 7,845 at 7-day, 2026 excluded), but these are **highly autocorrelated overlapping windows** (Day 1→2, 2→3, 3→4 each counted as an independent sample). After **independence correction** (non-overlapping windows per iceberg), the usable pairs **collapse by 21–53 %** at 2/3/5/7-day (53 %, 36 %, 23 %, 21 % of raw) and stand at 7,939 / 4,138 / 2,806 / 1,727 / **1,621** over all eras. Restricted to the **7 supported dataset years** that have feature stacks, the corrected counts are **1,618 / 896 / 633 / 409 / 489** at 1 / 2 / 3 / 5 / 7-day, of which **D23 (grounded, scatterometer noise) accounts for 1,148 / 651 / 468 / 295 / 339**. The **non-D23 independent pairs are only 470 / 245 / 165 / 114 / 150** across exactly **7 icebergs** — the *same* 7 icebergs as Phase 3C, **0 new icebergs**, purely densifying (daily vs weekly sampling) the same trajectories.

**Sensor quality is the critical blocker.** Scatterometer positions carry ~0.6–1.0 km jitter per observation: D23 ASCAT **mean 7-day displacement = 0.97 km** vs NIC = **0.42 km** for the same NIC-confirmed-grounded iceberg. **70–75.5 % of all supported pairs fall at or below the 2×-jitter noise ceiling** (about 1.3 km at 1-day, 1.9 km at 7-day) and **cannot be classified as drifting vs grounded** from scatterometer alone. This makes sub-weekly displacement targets unreliable at every horizon.

**Recommendation (Decision C):** BYU observed-only data does **NOT** provide enough independent, diverse, high-quality sub-weekly trajectory information to justify a new controlled experiment. **BYU should remain an independent QA/reference dataset.** It remains invaluable as a cross-source check on the NIC archive and as a dense daily trajectory library for *future* sub-weekly design work — but only if/when the project explicitly changes its temporal-resolution scope with approval.

---

## 1. Data Sources

| Source | Version | Path | Records (observed, in-bbox) | Notes |
|---|---|---|---:|---|
| BYU MERS Consolidated Antarctic Iceberg Database | v8.0 (downloaded 2026-09-05) | `data/raw/icebergs/byu/consolidated_database_v8.0.zip` | 10,076 | SHA256 `47d899c8…ccc40cae`, 647 per-iceberg CSVs, observed/interpolated flag per sensor |
| NIC archive (processed) | 2016–2026 | `data/processed/icebergs/east_prydz_bay_icebergs.csv` | 796 | Phase 1 source; 451 current ML pairs |
| Phase 3C expanded ML dataset | — | `data/processed/ml/expanded/full.parquet` | 451 | 8 icebergs, 342/55/54 train/val/test, chronological split |

All BYU interpolated/gap-filled rows (6,906 in-bbox, flag=0) are **excluded**. 2026 records are excluded. Only exact calendar-day matching of directly observed endpoints (both flag=1) is used — **no interpolation, no fabrication**.

---

## 2. Geographic & Temporal Scope

- **Region:** East Prydz Bay, lat [−70, −66], lon [72, 80], EPSG:4326.
- **Approved temporal scope:** the 7 dataset years **{2016, 2017, 2019, 2020, 2021, 2024, 2025}** (2018 has a stack but was excluded from Phase 3C as D23-only non-drifting; 2022/2023/2026 have no stack).
- **2026 excluded per instruction.**
- No change to geographic or temporal scope. BYU spans 1978–2025 in-bbox; only the 7 supported years are ML-feasible (stacks exist). All other-era pairs are reported but flagged as **not usable** for a Phase 3-style experiment.

---

## 3. Observed-Only Filtering

- 10,076 in-bbox records have `obs_flag == 1` → keep.
- 6,906 have `obs_flag == 0` (interpolated) → **excluded**. 0 interpolated rows remain.
- One position per iceberg per day by sensor preference: NIC > ASCAT > QSCAT > ERS > OSCAT > NSCAT > SASS > SEAWINDS.
- Combined daily series: **9,023 positions across 60 icebergs**.

---

## 4. Observation Cadence Analysis (Audit 1)

**Definition:** for each iceberg — `n_obs`, first/last date, `span_days`, median/mean/min/max gap between consecutive observations, and the count of **consecutive gaps of exactly H days** (`gaps 1d…7d`). The full (t, t+H) candidate-pair counts are given in Sections 5–6. Values from `cadence_per_iceberg.csv`.

| Iceberg | n obs | First | Last | Span (d) | Med gap | Mean gap | gaps=1d | gaps=2d | gaps=3d | gaps=5d | gaps=7d | Year set |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| D23 | 2,195 | 2016-01-01 | 2026-04-22 | 3,764 | 1.0 | 1.72 | 1,715 | 183 | 63 | 21 | 132 | 2016–2026 |
| B15B | 995 | 2006-08-13 | 2009-05-29 | 1,020 | 1.0 | 1.03 | 979 | 11 | 0 | 0 | 1 | 2006–2009 |
| D14 | 687 | 2011-08-30 | 2013-08-19 | 720 | 1.0 | 1.05 | 669 | 11 | 3 | 1 | 1 | 2011–2013 |
| E05 | 674 | 1992-02-12 | 1993-12-17 | 674 | 1.0 | 1.00 | 672 | 1 | 0 | 0 | 0 | 1992–1993 |
| UK249 | 579 | 2008-04-16 | 2009-11-23 | 586 | 1.0 | 1.01 | 573 | 3 | 1 | 0 | 0 | 2008–2009 |
| D27 | 189 | 2020-06-20 | 2021-04-14 | 298 | 1.0 | 1.59 | 161 | 4 | 5 | 1 | 11 | 2020–2021 |
| B09A | 161 | 1998-11-06 | 1999-04-16 | 161 | 1.0 | 1.01 | 159 | 1 | 0 | 0 | 0 | 1998–1999 |
| B39 | 134 | 2019-10-29 | 2020-06-21 | 236 | 1.0 | 1.77 | 118 | 1 | 1 | 1 | 9 | 2019–2020 |
| C18B | 117 | 2024-02-16 | 2025-07-24 | 524 | 6.0 | 4.52 | 49 | 0 | 0 | 0 | 35 | 2024–2025 |
| C39 | 81 | 2025-09-30 | 2026-04-22 | 204 | 1.0 | 2.55 | 42 | 17 | 3 | 0 | 10 | 2025–2026 |
| D22 | 69 | 2019-08-03 | 2019-11-13 | 102 | 1.0 | 1.50 | 58 | 4 | 1 | 1 | 4 | 2019 |
| D28 | 52 | 2019-09-23 | 2020-04-29 | 219 | 1.0 | 4.29 | 37 | 2 | 3 | 0 | 0 | 2019–2020 |
| D21B | 49 | 2017-03-02 | 2017-05-30 | 89 | 1.0 | 1.85 | 40 | 5 | 0 | 1 | 0 | 2017 |

**Supported-year icebergs with usable cadence:** 8 (B39, C18B, C39, D21B, D22, D23, D27, D28). The other 52 icebergs fall entirely in earlier eras or 2026.

**Insufficient observation:** 8 icebergs with ≤ 3 observations (C09, D10, D15C, B09I, B15L, C02, C07, D06) — cannot form any sub-weekly pair.

**Cadence note:** C18B and B15R have multi-day (6–7 day) median gaps → their 1/2/3-day sub-weekly sampling is inherently coarse; D28 has irregular gaps (max 137 d) limiting daily cadence.

---

## 5. Raw Pair Counts (Audit 2 — all overlapping windows)

**Pair definition:** observation at *t* **and** exactly *t + H* days (H ∈ {1, 2, 3, 5, 7}); both endpoints directly observed (flag=1); no interpolation; exact calendar-day match (**tolerance_days = 0**); 2026 start-obs excluded.

### Raw pairs, all eras (2026 excluded)

| Horizon | Raw pairs | Icebergs | Temporal span (start obs → latest end obs) | Years |
|---:|---:|---:|---|---|
| 1-day | 7,939 | 49 | 1978-07-23 → 2025-12-26 | 30 yrs |
| 2-day | 7,815 | 49 | 1978-07-23 → 2025-12-28 | 30 yrs |
| 3-day | 7,718 | 48 | 1978-07-23 → 2025-12-21 | 30 yrs |
| 5-day | 7,589 | 49 | 1978-07-23 → 2026-01-02\* | 30 yrs |
| 7-day | 7,845 | 50 | 1978-07-23 → 2026-01-02\* | 30 yrs |

\* The 2026-01-02 figures are *target endpoints* of pairs whose start obs is 2025-12-28 or earlier; the pair is retained because its `obs_date` (the start) is inside the approved window. No 2026 **start** obs is used.

### Raw pairs, supported years (ML-feasible)

| Horizon | Raw pairs | NIC pairs | ASCAT pairs |
|---:|---:|---:|---:|
| 1-day | 1,618 | 197 | 1,421 |
| 2-day | 1,566 | 192 | 1,374 |
| 3-day | 1,540 | 175 | 1,365 |
| 5-day | 1,515 | 179 | 1,336 |
| 7-day | 1,683 | 411 | 1,272 |

---

## 6. Independence-Corrected Pair Counts (Audit 3)

**Method (deterministic, documented):** per iceberg per horizon, sort pairs by `obs_date`; keep a pair only if its `obs_date` is **≥ H days** after the last kept pair's `obs_date`. Single forward pass → maximum non-overlapping set. RAW = all overlapping windows; CORRECTED = this set.

### All-eras corrected (2026 excluded)

| Horizon | Corrected pairs | Icebergs | Raw→Corr ratio |
|---:|---:|---:|---:|
| 1-day | 7,939 | 49 | 1.00 (no overlap at 1-day) |
| 2-day | 4,138 | 49 | 0.53 |
| 3-day | 2,806 | 48 | 0.36 |
| 5-day | 1,727 | 49 | 0.23 |
| 7-day | **1,621** | 50 | 0.21 |

### Supported-years corrected (ML-feasible)

| Horizon | Corrected | D23 | Non-D23 | Non-D23 icebergs |
|---:|---:|---:|---:|---:|
| 1-day | 1,618 | 1,148 | **470** | 7 |
| 2-day | 896 | 651 | **245** | 7 |
| 3-day | 633 | 468 | **165** | 7 |
| 5-day | 409 | 295 | **114** | 7 |
| 7-day | **489** | 339 | **150** | 7 |

The 7 non-D23 icebergs are B39, C18B, C39, D21B, D22, D27, D28 — identical to Phase 3C's 7 non-D23 icebergs.

**Why it matters:** Raw counts treat Day 1→2, 2→3, 3→4 as three independent samples. In trajectory prediction they are one continuous drift segment; the corrected set is the actual independent sample count and the only defensible basis for model training.

---

## 7. Drifting / Grounded / Unknown Analysis (Audit 4)

### Displacement distributions — raw, supported years

| Horizon | n pairs | Mean (km) | Median (km) | P95 (km) | Max (km) |
|---:|---:|---:|---:|---:|---:|
| 1-day | 1,618 | 2.05 | 0.00 | 12.21 | 47.4 |
| 2-day | 1,566 | 2.89 | 0.00 | 17.69 | 47.4 |
| 3-day | 1,540 | 3.84 | 0.00 | 24.50 | 64.4 |
| 5-day | 1,515 | 5.45 | 0.00 | 33.44 | 77.6 |
| 7-day | 1,683 | 6.33 | 0.00 | 39.97 | 121.9 |

**Median = 0.0 km at every horizon**, because D23's 1,210–1,148 raw supported pairs cluster at ~0 km displacement (scatterometer jitter). The means are inflated by the few genuinely drifting icebergs (B39, D27, D21B, D22, C18B, D28).

### Sensor-stratified displacement — raw, supported years

| Horizon | Sensor | n pairs | Mean (km) | Median (km) | P95 (km) |
|---:|---|---:|---:|---:|---:|
| 1-day | ASCAT | 1,421 | 1.80 | 0.00 | 11.94 |
| 1-day | NIC | 197 | 3.87 | 1.18 | 13.49 |
| 2-day | ASCAT | 1,374 | 2.71 | 0.00 | 17.65 |
| 2-day | NIC | 192 | 4.13 | 1.18 | 16.95 |
| 3-day | ASCAT | 1,365 | 3.66 | 0.00 | 24.47 |
| 3-day | NIC | 175 | 5.20 | 1.18 | 25.89 |
| 5-day | ASCAT | 1,336 | 5.20 | 0.00 | 33.33 |
| 5-day | NIC | 179 | 7.31 | 1.39 | 34.30 |
| 7-day | ASCAT | 1,272 | 6.53 | 0.00 | 42.20 |
| 7-day | NIC | 411 | 5.74 | 0.00 | 34.25 |

### Sensor-quality diagnostics (mean 7-day displacement, supported years)

| Iceberg / set | Sensor | Mean 7-d disp (km) | Interpretation |
|---|---|---:|---|
| **D23** | ASCAT | **0.97** | **Jitter-noise band** (grounded iceberg) |
| **D23** | NIC | 0.42 | Consistent with grounded (≪ 0.5 km Phase-3 threshold) |
| **Non-D23** | ASCAT | 21.29 | Genuine drift signal (median 14.2) |
| **Non-D23** | NIC | 17.92 | Genuine drift signal (median 8.3) |
| D27 | all | 10.52 | Cross-sensor drift agreement |
| B39 | all | 31.53 | Cross-sensor drift agreement |

### Noise-ceiling (classification) decision

The 0.5 km / 7-day threshold from Phase 3 was calibrated on **NIC point observations**. It **does not transfer** to scatterometer data: D23's ASCAT 7-day mean (0.97 km) already exceeds it for an iceberg NIC confirms grounded (0.42 km). Applying it would mislabel D23 scatterometer pairs as "drifting". Therefore **scatterometer pairs at or below 2× the D23-ASCAT mean (the jitter ceiling) are labeled UNKNOWN** — never forced into drifting or grounded.

Measured noise-ceiling fractions (supported raw pairs):

| Horizon | D23-ASCAT mean (km) | Ceiling = 2× (km) | % pairs ≤ ceiling (UNKNOWN) | % pairs > ceiling (classifiable) |
|---:|---:|---:|---:|---:|
| 1-day | 0.65 | 1.31 | 75.5 % | 24.5 % |
| 2-day | 0.62 | 1.23 | 72.3 % | 27.7 % |
| 3-day | 0.87 | 1.74 | 72.9 % | 27.1 % |
| 5-day | 0.84 | 1.68 | 70.0 % | 30.0 % |
| 7-day | 0.97 | 1.93 | 72.0 % | 28.0 % |

**72 ± 3 % of supported pairs are inside the scatterometer jitter band at every horizon.**

---

## 8. Iceberg Diversity (Audit 5)

### Current Phase 3C population (reference)

| Iceberg | Phase 3C pairs | Type |
|---|---:|---|
| B39 | 28 | Drifting |
| C18B | 40 | Drifting |
| C39 | 9 | Drifting (zero-shot) |
| D21B | 7 | Drifting |
| D22 | 11 | Drifting |
| D23 | 309 | Grounded |
| D27 | 38 | Drifting |
| D28 | 9 | Drifting |
| **Total** | **451** | 8 icebergs (142 drift / 309 grounded) |

### BYU supported-year corrected population by horizon

| Horizon | Non-D23 corr | Per iceberg (descending) | D23 corr | New icebergs vs Phase 3C |
|---:|---:|---:|---:|---:|
| 1-day | 470 | D27 161, B39 118, D22 58, C18B 49, D21B 40, D28 37, C39 7 | 1,148 | 0 |
| 2-day | 245 | D27 82, B39 59, D22 32, C18B 24, D21B 24, D28 19, C39 5 | 651 | 0 |
| 3-day | 165 | D27 57, B39 40, D22 21, C18B 16, D21B 15, D28 10, C39 6 | 468 | 0 |
| 5-day | 114 | D27 37, B39 25, D22 14, D28 13, D21B 11, C18B 9, C39 5 | 295 | 0 |
| 7-day | **150** | C18B 42, D27 39, B39 28, D22 13, C39 10, D28 10, D21B 8 | 339 | **0** |

**Diversity conclusion:**
- **0 new icebergs** at any horizon in the supported years.
- The 7 drifting icebergs are exactly Phase 3C's drifting set; D23 is the same grounded iceberg.
- BYU only **densifies** (daily vs weekly) the same trajectories — no trajectory-diversity gain.

---

## 9. Leakage & Split Design (Audit 6 — hypothetical, nothing created)

### C39 zero-shot integrity (critical)

All supported-year C39 pairs fall in the **test window (≥ 2025-01-01)**:

| Horizon | C39 raw | C39 corr | C39 supported date range |
|---:|---:|---:|---|
| 1-day | 7 | 7 | 2025-11-27 → 2025-12-25 |
| 2-day | 6 | 5 | 2025-11-27 → 2025-12-18 |
| 3-day | 6 | 6 | 2025-11-27 → 2025-12-18 |
| 5-day | 7 | 5 | 2025-11-28 → 2025-12-21 |
| 7-day | 13 | 10 | 2025-10-09 → 2025-12-26 |

**Zero C39 pairs fall in train or val at any horizon** under existing boundaries (train < 2024-01-01, val 2024, test ≥ 2025). If BYU C39 pairs were added to a sub-weekly test set, the frozen 9-pair zero-shot composition would become **10 (corrected) / 13 (raw) at 7-day**. This is disallowed without explicit approval — one reason decision C is chosen.

### Hypothetical future split design (if ever approved)
- **Chronological split at sub-weekly resolution** would need redefinition (e.g. train < 2024-01-01, val 2024, test ≥ 2025 at daily steps) — a *new* split, not the existing one.
- **Iceberg-level generalization:** only C39 qualifies as an unseen iceberg (same as Phase 3C) — no additional generalization leverage.
- **Overlap leakage:** sub-weekly windows overlap by (H−1) days; naive K-Fold on raw pairs leaks the same drift segment across folds. Future CV must operate on the **corrected (non-overlapping)** set with a **blocked** (time-series) split.

---

## 10. Environmental Feature Availability (Audit 7)

### Feature stacks on disk (8 years, 9 variables each, hourly, 0.25° grid)

| Year | File | Time steps | Variables |
|---:|---|---:|---:|
| 2016 | east_prydz_bay_2016_feature_stack.nc | 8,784 | 9 |
| 2017 | east_prydz_bay_2017_feature_stack.nc | 8,760 | 9 |
| 2018 | east_prydz_bay_2018_feature_stack.nc | 8,760 | 9 |
| 2019 | east_prydz_bay_2019_feature_stack.nc | 8,760 | 9 |
| 2020 | east_prydz_bay_2020_feature_stack.nc | 8,784 | 9 |
| 2021 | east_prydz_bay_2021_feature_stack.nc | 8,760 | 9 |
| 2024 | east_prydz_bay_2024_feature_stack.nc | 8,784 | 9 |
| 2025 | east_prydz_bay_2025_feature_stack.nc | 8,760 | 9 |

Variables: `sea_ice_concentration`, `wind_u_10m`, `wind_v_10m`, `temperature_2m`, `mean_sea_level_pressure`, `total_precipitation`, `bathymetry_elevation`, `ocean_current_u`, `ocean_current_v` — **all present, hourly**.

### Compatibility check
- Every supported-year pair maps to an existing feature stack (**0 pairs outside stack years**).
- Hourly stacks support any sub-weekly horizon (1/2/3/5/7-day).
- Ocean currents are available (GLORYS resolved in the stacks since Phase 3A).

**Limitation:** stacks are hourly means; a 1-day target needs a defined target-hour policy (nearest hour / midday). Design choice, not a data gap — but added complexity at zero diversity benefit.

---

## 11. Candidate Experiment Comparison A–E (horizons 1/2/3/5/7)

| Metric | 1-day (A) | 2-day (B) | 3-day (C) | 5-day (D) | 7-day (E) |
|---|---:|---:|---:|---:|---:|
| Raw pairs (excl. 2026, all eras) | 7,939 | 7,815 | 7,718 | 7,589 | 7,845 |
| Corrected pairs (excl. 2026) | 7,939 | 4,138 | 2,806 | 1,727 | 1,621 |
| Corr. within stack years (incl. 2018) | 1,861 | 1,027 | 721 | 465 | 541 |
| Corr. within supported 7 yrs | 1,618 | 896 | 633 | 409 | 489 |
| **Non-D23 corr. (ML-relevant)** | 470 | 245 | 165 | 114 | **150** |
| D23 corr. (scatterometer noise) | 1,148 | 651 | 468 | 295 | 339 |
| Usable non-D23 icebergs | 7 | 7 | 7 | 7 | 7 |
| C39 corr. pairs (test-only) | 7 | 5 | 6 | 5 | 10 |
| % classifiable above jitter ceiling | 24.5 % | 27.7 % | 27.1 % | 30.0 % | 28.0 % |
| NIC / ASCAT (raw, supported) | 197 / 1,421 | 192 / 1,374 | 175 / 1,365 | 179 / 1,336 | 411 / 1,272 |
| Env feature coverage | ✅ | ✅ | ✅ | ✅ | ✅ |
| C39 leakage risk | test-only | test-only | test-only | test-only | test-only (changes test composition) |
| ML usefulness | ⚠️ Low | ⚠️ Low | ⚠️ Low | ⚠️ Low | ⚠️ Low–Med |
| Dominant limitation | 75 % in noise band; 0 diversity | 72 % noise; 0 diversity; corr=53 % of raw | 73 % noise; 0 diversity; corr=36 % | 70 % noise; 0 diversity; corr=23 % | 72 % noise; 0 diversity; corr=21 % |

**Verdict A–E:** no horizon rescues the three fundamental blockers (0 new icebergs, ~72 % inside scatterometer noise band, independence-collapse of daily sampling). 7-day (E) has the most NIC-class pairs (411) and the largest per-pair signal-to-noise, but still only **150 non-D23 independent pairs** — insufficient to justify a new controlled experiment.

---

## 12. Limitations

1. **No new icebergs** → diversity zero.
2. **~72 % of supported pairs are inside the scatterometer jitter band** (ceiling 1.2–1.9 km) — drifting/grounded classification is UNKNOWN for them.
3. **Independence correction collapses daily sampling** (corrected = 21–53 % of raw beyond 1-day); only **150 non-D23 independent 7-day pairs** remain — a re-densification of Phase 3C trajectories, not new signal.
4. **C39 zero-shot would change** if its BYU pairs entered the frozen test set (9 → 10 corrected / 13 raw at 7-day).
5. **30 years of BYU vs 7 supported stack years** — the large raw counts are mostly eras with no environmental forcing available.
6. **NIC vs scatterometer short-horizon disagreement** (D23: NIC ~2.5–3 km at 1–5-day but 0.42 km at 7-day) means even NIC-class sub-weekly displacement is noisy for grounded icebergs at ≤5-day.
7. **The 0.5 km/7-day threshold is NIC-calibrated and does not transfer to scatterometer** — direct application misclassifies D23.
8. **2026 excluded** — D15C/D15D and C39's 2026 segment cannot be used.

---

## 13. Recommendation

### Decision: **C — NO. BYU remains an independent QA/reference dataset.**

**Reasoning (measured):**
- **Diversity:** 0 new icebergs; same 7 drifting icebergs as Phase 3C.
- **Independence:** 150 non-D23 independent 7-day pairs / 470 at 1-day vs 142 drifting pairs already in Phase 3C — gain is density, not information.
- **Quality:** 70–75.5 % of pairs are inside the scatterometer jitter ceiling; classifiable as UNKNOWN.
- **Leakage:** adding C39 sub-weekly pairs would modify the frozen zero-shot test composition.
- **Bottleneck unchanged:** Phase 3D diagnosed scarcity of *independent drifting trajectories and iceberg diversity* — BYU solves neither.

**Defensible uses (in place, or future-with-approval):**
1. **Cross-source QA/validation** of the NIC archive (already used in Phase 3E).
2. **Dense daily trajectory library** for a future sub-weekly design — but any such experiment needs an explicit scope change decision (temporal resolution, new split, C39 re-composition), which is outside this audit.
3. **Methodological sandbox** for sub-weekly feature engineering — not a production experiment.

**Conditional note (if the user later decides sub-weekly is worth pursuing):** the only defensible design would be **B-conditional** — 7-day horizon only, corrected pairs only, chronological split, C39 excluded from train — but it rests on just 150 non-D23 pairs and is NOT justified by the data at this time.

---

## 14. Exact Reproducibility Details

All numbers derive from the original BYU v8.0 ZIP and the immutable Phase 1/2/3/3C datasets. Key parameters (from `audit_meta.json`):

```json
{
  "bnd_box": {"lat_min": -70.0, "lat_max": -66.0, "lon_min": 72.0, "lon_max": 80.0},
  "supported_years": [2016, 2017, 2019, 2020, 2021, 2024, 2025],
  "stack_years": [2016, 2017, 2018, 2019, 2020, 2021, 2024, 2025],
  "horizons": [1, 2, 3, 5, 7],
  "tolerance_days": 0,
  "pair_definition": "Both endpoints directly observed (flag=1); no interpolation; dt==horizon exactly; one position per iceberg per day (NIC>ascat>qscat>ers>oscat>nscat>sass>seawinds); bbox clip; 2026 excluded.",
  "independence_method": "Greedy non-overlapping filter per iceberg per horizon: keep pair only if obs_date >= horizon_days after last kept. One pass, deterministic."
}
```

**Artifacts:** `data/raw/icebergs/byu/analysis/phase3f/` → `cadence_per_iceberg.csv`, `pairs_raw_h{h}.csv`, `pairs_corr_h{h}.csv`, `per_iceberg_h{h}.csv`, `horizon_comparison.csv`, `diversity_by_horizon.csv`, `disp_summary.json`, `audit_meta.json`.

**Regeneration:**
```bash
python scripts/data/analyze_byu.py        # Phase 3E: parse + bbox + observed-only
python scripts/data/analyze_byu_pairs.py  # Phase 3E: 7-day pairs + drift class
python scripts/data/phase3f_audit.py      # Phase 3F: this audit
```
All scripts read only the original BYU ZIP and the immutable datasets. No internet, no downloads, no model training, no writes to protected files.

---

## 15. Files Inspected

| File | Purpose |
|---|---|
| `data/raw/icebergs/byu/consolidated_database_v8.0.zip` | Source data (SHA256 recorded) |
| `data/raw/icebergs/byu/updated7_consol/*.csv` | 647 per-iceberg trajectory files |
| `data/raw/icebergs/byu/acquisition_log.json` | Acquisition metadata |
| `data/raw/icebergs/byu/analysis/byu_in_bbox_observed.csv` | Observed-only filter output (Phase 3E) |
| `data/raw/icebergs/byu/analysis/byu_gap_qc.csv` | Gap QC |
| `data/raw/icebergs/byu/analysis/phase3f/*.csv` + `.json` | This audit's computed artifacts |
| `data/processed/ml/expanded/full.parquet` | Phase 3C ML dataset (451 pairs, authority) |
| `data/processed/ml/expanded/ml_dataset_metadata.json` | Split boundaries, feature columns |
| `data/processed/icebergs/east_prydz_bay_icebergs.csv` | NIC archive |
| `data/processed/integration/east_prydz_bay_*_feature_stack.nc` | 8 feature stacks |

---

## 16. Commands / Scripts Used

```bash
# Phase 3E (already executed, unchanged)
python scripts/data/analyze_byu.py
python scripts/data/analyze_byu_pairs.py

# Phase 3F (this audit)
python scripts/data/phase3f_audit.py

# Post-hoc verification of every number in this report (read-only pandas over artifacts)
# e.g. per-horizon splits by iceberg/sensor, noise-ceiling fractions, C39 date ranges.
git status   # confirmed: no protected file modified
```

No `.env`, no credentials, no network access. All verification queries were read-only.

---

## 17. Validation Checks — 18/18 PASS

| # | Check | Result |
|---|---|---|
| 1 | BYU source unchanged (ZIP + SHA256) | ✅ PASS |
| 2 | Phase 1 dataset unchanged | ✅ PASS |
| 3 | Phase 2 dataset unchanged | ✅ PASS |
| 4 | Phase 3 original dataset unchanged | ✅ PASS |
| 5 | Phase 3C expanded dataset unchanged (451 pairs, 8 icebergs) | ✅ PASS |
| 6 | ML models unchanged | ✅ PASS |
| 7 | Train/val/test split unchanged (342/55/54) | ✅ PASS |
| 8 | C39 zero-shot composition unchanged (no merge performed) | ✅ PASS |
| 9 | No interpolated observations used | ✅ PASS (0 interpolated rows) |
| 10 | No fabricated/interpolated observations; no invented trajectories | ✅ PASS |
| 11 | No 2026 data used | ✅ PASS (0 start-obs in 2026) |
| 12 | No new environmental downloads | ✅ PASS |
| 13 | No ML training performed | ✅ PASS |
| 14 | No model files modified | ✅ PASS |
| 15 | Raw AND corrected counts both reported | ✅ PASS |
| 16 | Sensor differences explicitly handled (NIC vs scatterometer) | ✅ PASS |
| 17 | UNKNOWN used, not forced; threshold not transferred | ✅ PASS |
| 18 | All numbers reproducible from artifacts | ✅ PASS |

**18 / 18 PASS**

---

## 18. Git / File Safety

```text
$ git status
On branch main
Changes not staged for commit:
  modified:   scripts/data/download_sea_ice.py        (pre-existing, untouched this phase)
Untracked:
  reports/PHASE3F_SUBWEEKLY_FEASIBILITY_AUDIT.md      <- this report (new)
  data/raw/icebergs/byu/analysis/phase3f/             <- audit artifacts (new)
  scripts/data/phase3f_audit.py                       <- audit script (new)
  (plus pre-existing untracked Phase 3A-3E reports/scripts)
```
No commit, no delete, no overwrite performed this phase. **No protected dataset, model, or report modified.**

---

**PHASE 3F COMPLETE — FEASIBILITY AUDIT ONLY.  
NO MODELS TRAINED.  
NO EXISTING DATASETS MODIFIED.  
STOPPING FOR EXPLICIT APPROVAL.**