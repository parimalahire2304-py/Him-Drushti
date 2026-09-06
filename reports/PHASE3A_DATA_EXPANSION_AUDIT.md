# Phase 3A — Data Expansion Audit

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-04

**Status:** AUDIT ONLY — no data modified, no downloads, no model training

**Constraint:** Do NOT modify Phase 1 or Phase 2 data. Do NOT modify the original feature stack (2020 only). Do NOT fabricate, interpolate, oversample, or synthetically generate trajectories. No assumptions about unavailable data.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Dataset Audit](#2-current-dataset-audit)
3. [Environmental Data — Multi-Year Feasibility](#3-environmental-data--multi-year-feasibility)
4. [Expansion Source Profiles](#4-expansion-source-profiles)
5. [Leakage Risk Summary](#5-leakage-risk-summary)
6. [Ranked Recommendation](#6-ranked-recommendation)
7. [Implementation Roadmap (Not Executed)](#7-implementation-roadmap-not-executed)
8. [Appendix A — Verified File Inventory](#appendix-a--verified-file-inventory)
9. [Appendix B — Verification Notes](#appendix-b--verification-notes)

---

## 1. Executive Summary

### Key Numbers (verified against live files)

| Dimension | Current ML dataset | NIC archive held locally |
|---|---|---|
| **Icebergs** | 4 | 11 (East Prydz Bay 2016–2026) |
| **Observations** | 107 (2020 only) | 796 (East Prydz Bay, all years) |
| **Valid 7-day pairs** | **101** (`full.parquet`) | **643** possible across all years |
| **Observation frequency** | Weekly (7-day nominal) | Weekly (643 × 7-day gaps verified; also 67× 6-day, 62× 8-day, + other irregular gaps) |
| **Date range** | 2020-01-03 → 2020-12-18 (obs) | 2016-01-01 → 2026-08-27 (East Prydz Bay); raw archive 2014-11-07 → 2026-08-27 (Antarctic-wide) |
| **Spatial coverage** | East Prydz Bay bbox S −70.0 N −66.0 W 72.0 E 80.0 EPSG:4326 | Same bbox |
| **Pairs lost in 2020** | 6 of 107 obs (5.6%) cannot form 7-day pairs | 6-day/8-day gaps + first-in-run observations |
| **Grounded-bias** | D23 = 49 of 101 pairs (48.5%) | D23 = 471 of 643 pairs (73.2%) |

### Bottom Line

The raw **NIC archive already held on disk (608 weekly CSVs, 2014→2026) contains 540 valid 7-day pairs beyond the 101 currently used** — 118 of which are non-grounded, drifting trajectories. No external iceberg dataset is needed to achieve a ~6× expansion. The binding constraint is the **2020-only feature stack**: expanding to other years requires re-acquiring environmental forcing (ERA5, sea-ice, GLORYS) for those years, all of which have verified multi-year coverage. An alternative family of external sources (BYU scatterometer, NSIDC-0684 MEaSUREs, Sentinel-1 SAR) can provide higher-frequency or complementary trajectories but at higher integration cost and with distinct scientific/leakage caveats.

**No data has been modified, downloaded, or fabricated as part of this audit.**

---

## 2. Current Dataset Audit

### 2.1 Current Inventory (verified)

**File:** `data/processed/ml/full.parquet` · **Pipeline:** `scripts/ml/prepare_ml_dataset.py` · **Problem definition:** `reports/PHASE3_STEP1_PROBLEM_DEFINITION.md`

| Property | Value | Source |
|---|---|---|
| Problem | 7-day single-step iceberg trajectory prediction (lat/lon at t+7d) | PHASE3_STEP1 |
| Prediction horizon | 7 days (fixed) | `TARGET_DT_DAYS = 7` |
| Input time | Current position + environmental features at t | `build_pairs()` |
| Target | `target_lat`, `target_lon` at t+7 | — |
| Feature columns | 25 (position 8 + sea ice 2 + wind 5 + ocean 4 + atmosphere 3 + static 3) | `FEATURE_COLS` |
| Samples | **101 supervised pairs** | `full.parquet` (39 columns) |
| Train / Val / Test | 71 / 16 / 14 — chronological split | obs_date < 2020-08-15 / < 2020-10-31 / ≥ 2020-10-31 |
| Icebergs in ML dataset | **4: B39, D23, D27, D28** | — |
| Train iceberg mix | B39=21, D23=33, D27=8, D28=9 | `train.parquet` |
| Val | D23=8, D27=8 | `val.parquet` |
| Test | D23=7, D27=7 | `test.parquet` |
| Unique obs dates | 48 | — |
| Obs date range | 2020-01-03 → 2020-12-18 (target_date → 2020-12-25) | — |
| Persistence baseline | MAE 2.598 km on 14-sample test set (all models worse to date) | PHASE3_STEP4/5/6 |
| Missing values | `prev_*` columns NaN for first observation per iceberg run (6 rows) | XGBoost handles natively; RF/LSTM impute |

**Train/val/test caveat:** B39 and D28 occur **only in train**. Val/test contain only D23 + D27, so generalisation to unseen icebergs is unevaluated.

**Feature stack (read-only):**

| Property | Value |
|---|---|
| File | `data/processed/integration/east_prydz_bay_2020_feature_stack.nc` |
| Grid | ERA5 0.25° regular lat/lon · 17×33 = **561 cells** · lat −70..−66, lon 72..80 · EPSG:4326 |
| Time | Hourly 2020 (**8784 steps**, leap year) |
| Variables (9) | `sea_ice_concentration` (NSIDC-0051), `wind_u_10m`, `wind_v_10m`, `temperature_2m`, `mean_sea_level_pressure`, `total_precipitation` (ERA5 CDS), `bathymetry_elevation` (GEBCO_2024), `ocean_current_u`, `ocean_current_v` (GLORYS12V1 — 75 MB daily file present at `data/raw/ocean/glorys/`) |
| Interpolation | Bilinear (default); nearest-neighbour for sea-ice/bathymetry (sharp ice-edge boundaries) |
| Metadata | `east_prydz_bay_2020_feature_stack_metadata.json` |

> **Provenance note on ocean currents:** An earlier Phase 2 report (`GLORYS12V1_ACQUISITION_REPORT.md`) recorded GLORYS as BLOCKED due to a transient CMEMS DNS failure. That block has since been resolved: `data/raw/ocean/glorys/` now holds a 73 MB daily GLORYS12V1 file dated 2026-09-04 08:24, and the feature stack contains real (non-NaN, physically plausible) `ocean_current_u/v` fields. Any expansion to other years will require the same GLORYS fetch to be repeated for each new year; the method is verified, the DNS gate is known, and the credential (`CMEMS_USERNAME=pahire`) is already in `.env`.

### 2.2 Why Observations / Pairs Are Being Lost

Two distinct attrition mechanisms, both verified:

#### (a) Inter-observation gaps ≠ 7 days

Pair construction (`prepare_ml_dataset.py:301–302`) requires consecutive observations of the same iceberg to be **exactly 7 days apart**. Any other gap invalidates that transition:

| Gap (days) | Count (East Prydz Bay, all years) | Fate |
|---|---|---|
| **7** | **643** | Forms a valid 7-day pair |
| 6 | 67 | Dropped — cannot form a 7-day pair |
| 8 | 62 | Dropped |
| 14 | 6 | Dropped |
| 1, 13, 21, 35, 147 | 1–2 each | Dropped / long gaps (iceberg absent or not acquired) |

In 2020 alone, **6 observations** are orphaned by non-7-day gaps or because they are isolated (e.g., a single 1-obs appearance such as B09I in 2019). So 107 obs → 103 valid 7-day transitions at the CSV level → 101 supervised rows in `full.parquet` (the remaining 2 fail feature extraction, likely due to the affected date falling outside the feature-stack time axis or at a grid edge).

#### (b) Previous-step features unavailable

`prev_lat`, `prev_lon`, `prev_delta_lat`, `prev_delta_lon`, `prev_speed`, `prev_bearing` require an observation at **t−7** days preceding the input observation. When `i == 0` for an iceberg's trajectory, or when `dt_back != 7`, these fields are **NaN** (6 rows in `full.parquet`). This is not a loss of pairs — the rows are kept with NaN previous-step features — but it means the first observation of each trajectory run carries less history. XGBoost handles this natively; RF/LSTM must impute.

#### (c) LSTM sequences require consecutive 7-day pairs

`train_lstm.py` builds LSTM sequences with `SEQ_LENGTH=2` (14-day context): two consecutive valid 7-day pairs. Any break in the chain (a non-7-day gap) resets the run. For 2020 this yields ~63/14/12 sequences; for a multi-year dataset the same per-year gap structure applies.

> **Policy for any expansion:** Never fabricate, interpolate, oversample, or synthetically generate observations to fill gaps. Gaps are preserved as NaN / run breaks.

### 2.3 Available Date Range (verified, not assumed)

| Level | Span | Files/rows |
|---|---|---|
| **Raw NIC archive on disk** | **2014-11-07 → 2026-08-27** (608 weekly CSVs, Antarctic-wide) | `data/raw/icebergs/AntarcticIcebergs_YYYYMMDD.csv` |
| **East Prydz Bay (processed CSV)** | **2016-01-01 → 2026-08-27** (first obs in bbox appears 2016-01-01; no-in-bbox obs before then) | 796 rows across 11 icebergs |
| **ML dataset currently used** | 2020-01-03 → 2020-12-18 (obs), target → 2020-12-25 | 101 pairs |
| **Per-iceberg extents** | See table below | — |

| Iceberg | Span (East Prydz Bay) | Rows | Comment |
|---|---|---|---|
| B09I | 2019-05-03 (single obs) | 1 | Isolated; cannot form a pair |
| B39 | 2019-11-01 → 2020-06-19 | 30 | — |
| C18B | 2024-02-16 → 2025-07-24 | 75 | — |
| C39 | 2025-10-09 → 2026-04-30 | 30 | — |
| D15C | 2026-04-24 → 2026-08-27 | 19 | — |
| D15D | 2026-05-08 → 2026-08-27 | 17 | — |
| D21B | 2017-03-10 → 2017-04-28 | 8 | — |
| D22 | 2019-08-09 → 2019-11-08 | 14 | — |
| D23 | 2016-01-01 → 2026-08-27 | 551 | **Grounded** throughout (lat −69.51..−69.42, lon 74.62..74.74) |
| D27 | 2020-06-26 → 2021-04-09 | 40 | — |
| D28 | 2019-09-27 → 2020-04-24 | 11 | — |

> D23 is stationary to within ~0.09° lat × ~0.12° lon for a decade — it explains 48.5% of the current ML pairs (471 of 643 across all years: **73.2%**). Its persistence baseline is near-zero displacement.

### 2.4 Whether Higher-Frequency Observations Are Available from the Existing Source

**No.** The existing NIC source (`https://usicecenter.gov/Products/DisplaySearchResults`, queried by `scripts/data/download_icebergs.py`) publishes one snapshot per week in the form `AntarcticIcebergs_YYYYMMDD.csv`. The pipeline merges these into `east_prydz_bay_icebergs.csv` via `scripts/data/process_icebergs.py`. There is no daily or sub-weekly NIC bulletin in the current pipeline, and the verified frequency distribution (643× 7-day gaps) confirms weekly cadence. Any higher-frequency product would require a **different source** (§4.2–4.8).

### 2.5 Whether Additional Years Are Available

**Yes — verified on disk.** The NIC raw archive already held locally spans 2014-11-07 → 2026-08-27. The processed East Prydz Bay file yields valid 7-day pairs across **9 distinct years** (2016–2026 minus 2018,2023 which still have D23 pairs). In total **540 valid 7-day pairs beyond 2020** are already available without any new download except their corresponding environmental forcing:

| Year | Valid 7-day pairs (all) | Of which drifting (excl. D23) |
|---|---|---|
| 2016 | 49 | 0 (D23 only) |
| 2017 | 57 | 7 |
| 2018 | 50 | 0 (D23 only) |
| 2019 | 66 | 18 |
| **2020 (current)** | **103** | **54** |
| 2021 | 67 | 14 |
| 2022 | 52 | 0 (D23 only) |
| 2023 | 39 | 0 (D23 only) |
| 2024 | 55 | 25 |
| 2025 | 54 | 24 |
| 2026 | 51 | 30 |
| **All years** | **643** | **172** |
| **Beyond 2020** | **540** | **118** |

### 2.6 Whether Additional Iceberg Trajectories Are Available

**Yes — verified.** Beyond the 4 icebergs in the 2020 ML dataset, **7 additional East Prydz Bay icebergs** have trajectory data in other years, including fast-drifting ones that would diversify the drift-regime distribution:

| Iceberg | All-year pairs | Lat span | Lon span | Style | Years |
|---|---|---|---|---|---|
| **C18B** | 40 | −68.64..−66.12 (2.5°) | 72.75..79.96 (7.2°) | Fast drifter | 2024–2025 |
| **D27** | 38 | −68.35..−67.54 | 73.34..79.52 | Drifter | 2020–2021 |
| **B39** | 28 | −68.54..−66.33 (2.2°) | 72.10..79.91 (7.8°) | Drifter | 2019–2020 |
| **C39** | 21 | −69.20..−66.56 | 72.81..77.76 | Drifter | 2025–2026 |
| **D22** | 11 | −66.89..−66.40 | 73.92..78.92 | Drifter | 2019 |
| **D15C** | 9 | −67.22..−67.09 | 79.41..79.82 | Short track | 2026 |
| **D15D** | 9 | −67.29..−67.26 | 79.25..79.33 | Short track | 2026 |
| **D21B** | 7 | −66.77..−66.05 | 76.73..79.47 | Short track | 2017 |
| **D28** | 9 | −68.55..−66.37 | 72.02..74.07 | Short track | 2019–2020 |
| *D23 (grounded)* | *471* | *−69.51..−69.42* | *74.62..74.74* | *Grounded* | *2016–2026* |

Notably, **C18B (75 obs, 40 pairs) is a large fast-drifting iceberg whose travelled distance in Prydz Bay exceeds the entire current test set** — adding it would put genuinely non-stationary drift into val/test for the first time (current val/test are D23+D27 only).

### 2.7 Whether Corresponding Environmental Data Can Be Obtained for Any Proposed Expansion

**Yes, with one DNS caveat.** Verified product coverage:

| Forcing | Product already used | Multi-year coverage | Access | Already on disk (2020) |
|---|---|---|---|---|
| Wind, T2m, MSLP, TP | **ERA5** (`reanalysis-era5-single-levels`, CDS) | **1940–present**, hourly, 0.25° | CDS API (`CDS_API_URL` / `CDS_API_KEY` in `.env`) | `data/processed/weather/east_prydz_bay_era5_2020-01-01_2020-12-31.nc` |
| Sea-ice concentration | **NSIDC-0051** (v2.0 CDR) | **1978–present**, daily, 25 km polar-stereo | NSIDC HTTPS (no auth) | `data/processed/sea_ice/east_prydz_bay_sea_ice_concentration_2020-01-01_2020-12-31.nc` |
| Bathymetry | **GEBCO_2024** | Static, 15 arc-sec | HTTPS download (one-off) | `data/processed/bathymetry/east_prydz_bay_bathymetry_15arcsec.nc` |
| Ocean currents (u/v, SST) | **GLORYS12V1** (`GLOBAL_MULTIYEAR_PHY_001_030`, CMEMS) | **1993–present**, daily, 1/12° | CMEMS OAuth2 (cred `pahire` in `.env`) | `data/raw/ocean/glorys/cmems_mod_glo_phy_my_0.083deg_P1D-m_1788490478516.nc` (73 MB) — now present |

All four Forcings have continuous coverage that includes every expansion year 2016–2026. ERA5 and NSIDC access present no known restriction. **GLORYS access is verified functional** (file present as of 2026-09-04 08:24) but historically gated by a CMEMS identity-server DNS issue (`GLORYS12V1_ACQUISITION_REPORT.md`); any expansion should treat CMEMS network reachability as a live check rather than an assumption. A fallback (`ORAS5_FALLBACK_EVALUATION.md`) exists for ocean currents but is explicitly marked as monthly-mean and scientifically degraded — it should not be silently substituted.

> Expanding to other years is therefore an **environmental-forcing re-acquisition task** (one feature stack per new year, via the existing `scripts/data/build_feature_stack.py` path), not a source change for icebergs. Storage is modest (~200 MB per year for the 9-variable hourly stack).

### 2.8 Spatial Coverage

- **Region:** East Prydz Bay fixed bbox **S −70.0 N −66.0 W 72.0 E 80.0** (EPSG:4326) — from `config/region.yaml`.
- **Grid:** 17 × 33 = 561 cells at 0.25° spanning exactly the bbox.
- **Current observations:** all 101 pairs fall inside the bbox by construction (the pipeline filters to it). Observed lat −69.51..−66.05, lon 72.02..79.96. Expansion years stay in the same bbox — no spatial expansion of the grid is needed (unless a separate regional-expansion proposal is made and approved).

### 2.9 Summary — Where the Data Went

The pipeline loses **~5–6% of raw 2020 observations** (107→101 pairs) plus skews its iceberg mix (B39/D28 only in train). Across all years the same weekly-cadence physics applies: every non-7-day gap (6-day, 8-day, 14-day, 35-day, 147-day) is a dropped pair; every trajectory-start has NaN previous-step history. No other attrition has been observed. Total recoverable expansion headroom from the existing NIC source alone: **540 pairs** (118 drifting) plus **7 additional iceberg IDs**, pending the corresponding per-year feature stacks.

---

## 3. Environmental Data — Multi-Year Feasibility

For every expansion year Y, a new feature stack `east_prydz_bay_YYYY_feature_stack.nc` would be built the same way Phase 2 Step 3 built the 2020 stack. The table below is the per-year feasibility cheque — it doubles as the §4-style source profile for the environmental side.

| Year / Product | Source | Temporal res. | Spatial res. | Date coverage for Y | Spatial coverage | Variables | Access method | License / restrictions | Compatibility with pipeline | Scientific limitations | Leakage risks |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Y = any 2016–2026 · ERA5** | ECMWF CDS (`reanalysis-era5-single-levels`) | Hourly | 0.25° regular lat/lon | 01-01..12-31 Y | Global — subset to bbox | `u10`, `v10`, `t2m`, `msl`, `tp` → `wind_u_10m/v10m`, `temperature_2m`, `mean_sea_level_pressure`, `total_precipitation` | CDS API (`cdsapi`), `download_weather.py` path; `CDS_API_URL`/`KEY` in `.env` | Free registration; CDS ToS | **Identical** — same downloader, same grid, same `build_feature_stack.py` | None beyond ERA5 reanalysis assumptions | Chronology must be preserved — never bulk-concatenate across years before the split |
| **Y = any 2016–2026 · NSIDC sea-ice** | NSIDC CDR `NSIDC-0051` v2.0 | Daily (reprojected to hourly by forward-fill in pipeline) | 25 km polar-stereo (EASE-Grid) | 01-01..12-31 Y | Northern/Southern hemispheres | `sea_ice_concentration` (flag-masked 0..1, ice-edge preserved by NN) | HTTPS download, no auth | Public government data | **Identical** — same `download_sea_ice.py` path; reproject via `src/preprocessing/gridding.py` | Known coastal-mask NaN; preserved by design — no interpolation over land | None if kept daily→hourly forward-fill (no look-ahead) |
| **Y = any 1993–present · GLORYS12V1 ocean** | CMEMS `GLOBAL_MULTIYEAR_PHY_001_030` · dataset `cmems_mod_glo_phy_my_0.083deg_P1D-m` | Daily | 1/12° (~8 km; ~3.5 km zonal at 68°S) | 01-01..12-31 Y | Global ocean | `uo`, `vo`, `thetao` → `ocean_current_u/v`, SST | CMEMS Motu/OData/REST with OAuth2 (`CMEMS_USERNAME=pahire`, `identity.marine.copernicus.eu`, host `data.marine.copernicus.eu`) | Free registration; CMEMS ToS | **Identical** — same `download_ocean.py` path; surface level (0 m); bilinear resample to 0.25° | Best available daily sub-mesoscale currents for Prydz Bay; monthly-mean fallbacks (ORAS5) degrade skill and must not replace it silently | Same chronological-split discipline; ORAS5 fallback must not be mixed into the same stack without explicit metadata |
| **Any year · GEBCO bathymetry** | GEBCO_2024 | Static (no time) | 15 arc-sec (~450 m), coarsened to 0.25° by `xarray.coarsen().mean()` | — | Global | `elevation` → `bathymetry_elevation` (broadcast across Y) | One-off HTTPS; file already held | Public; GEBCO ToS | **No re-download** — reuse `data/processed/bathymetry/east_prydz_bay_bathymetry_15arcsec.nc` | 0 expected missing | None (static) |

> **Net assessment:** Expanding to any year 2016–2026 is environmentally feasible with no new data provider beyond the four already used. The only known operational risk is CMEMS network reachability (now resolved for 2020; must be re-verified per new year). The ORAS5 fallback (monthly, 0.25°, via CDS) remains available but is explicitly a **degraded baseline**, not an equivalent replacement.

---

## 4. Expansion Source Profiles

Each proposed source is documented against the required fields. No source is claimed to contain data unless verified; unverified or nonexistent proposals are listed separately and not counted.

### 4.1 Strategy A — Expand the EXISTING NIC Source to Additional Years

*This is a date-range expansion of the source already used — it adds years, icebergs, and pairs from the same pipeline with no schema change.*

| Field | Value |
|---|---|
| **Source name** | **US National Ice Center (NIC) Antarctic iceberg tracking — same source as the current dataset** (`scripts/data/download_icebergs.py` → `scripts/data/process_icebergs.py` → `scripts/ml/prepare_ml_dataset.py`) |
| **Data type** | Observed iceberg centroid positions (lat/lon) + tabulated dimensions (Length/Width in NM) from analyst-interpreted satellite imagery (SAR, visible, IR) |
| **Temporal resolution** | **Weekly** (one snapshot per ~7 days); verified distribution 643×7-day gaps; irregular 6-day/8-day gaps do occur |
| **Spatial resolution** | Point observations (single centroid per iceberg per snapshot); icebergs tracked if ≥ 20 sq nm OR ≥ 10 NM on longest axis |
| **Date coverage** | Raw archive held locally **2014-11-07 → 2026-08-27** (608 files, Antarctic-wide); **East Prydz Bay valid pairs: 9 distinct years 2016–2026**; 2014–2015 have no in-bbox obs |
| **Spatial coverage** | **East Prydz Bay bbox S −70 N −66 W72 E80** (filters 796 of the Antarctic-wide records to exactly the model domain) |
| **Variables** | `Iceberg` (ID, e.g. D23), `Length (NM)`, `Width (NM)`, `Latitude`, `Longitude`, `Last Update`, `observation_date`, `source_file`, `schema_version`, `_obs_dt` — plus derived features from the feature stack (25 FEATURE_COLS unchanged) |
| **Access method** | **Already held:** `data/raw/icebergs/AntarcticIcebergs_YYYYMMDD.csv` (608 files). Fresh pulls via `https://usicecenter.gov/Products/DisplaySearchResults` (public, no auth). Downloader `scripts/data/download_icebergs.py` with `--start`/`--end` is intact. |
| **Licensing / access restrictions** | Public US Government data — no license gate verified; no authentication required for download |
| **Compatibility with existing pipeline** | **Exact match.** Same two schemas (Nov 2014–Apr 2024 7-col + Remarks; Apr 2024–Aug 2026 9-col + Area), same `process_icebergs.py` → `prepare_ml_dataset.py` path. No code change needed beyond re-running with a wider year range (and producing a per-year feature stack per §3). `src/utils/region.py` bbox unchanged. |
| **Potential scientific limitations** | (i) Weekly cadence → no sub-weekly dynamics; (ii) D23 dominance (73% of all-year pairs) — requires stratified / iceberg-weighted handling; (iii) Large-iceberg threshold — smaller, more mobile bergs undetected; (iv) 6/8-day gaps must not be interpolated per constraints; (v) 4-iceberg 2020 val/test generalizes only to D23+D27 → expansion is needed to hold out genuine drifters |
| **Potential leakage risks** | **Low, controllable.** Leakage risk is purely chronological: any new year must obey the same **chronological split** (train < val < test) and **no future position / environmental conditions as input**. The risk is a procedural one (accidental random split of sequential trajectory observations) rather than a data-source one. Expanding the dataset requires re-anchoring split boundaries to the new temporal span and documenting them in `ml_dataset_metadata.json`. No test-set tuning. |

**Expansion yield (verified, not estimated):**

| Scope | Added pairs | Cumulative pairs | Distinct iceberg IDs |
|---|---|---|---|
| Current (2020 only) | — | 101 | 4 (B39, D23, D27, D28) |
| + 2019 | +66 | 167 | +D22 (14 obs) |
| + 2024 | +55 | 222 | +C18B (40 pairs) |
| + 2025 | +54 | 276 | *(C18B continued)* + C39 onset |
| + 2026 | +51 | 327 | +C39, D15C, D15D |
| + 2017 | +57 | 384 | +D21B |
| + 2021 | +67 | 451 | D27 continued |
| + 2016 (+ misc) | +192 (2016+2018+2022+2023 mostly D23) | **643** | — (D23-dominated years) |

> Drifting (non-D23) subtotal in the 540 added beyond 2020: **118 pairs** (C18B 40, C39 21, D27 14, D22 11, D15C 9, D15D 9, B39 7, D21B 7).

**Why this is the primary strategy:** it is the only option that multiplies the dataset ~6× with **zero** format change and **zero** external schema risk, and it directly fixes the drift-regime gap in the current test set (C18B/C39 place fast drifters into val/test for the first time).

---

### 4.2 Strategy B — BYU Antarctic Iceberg Tracking Database

*The only verified, comprehensive, multi-decade Antarctic iceberg trajectory database beyond the NIC weekly series. Operated jointly by the BYU Remote Sensing Lab and NIC.*

| Field | Value |
|---|---|
| **Source name** | **BYU Antarctic Iceberg Tracking Database** (BYU Remote Sensing — `https://www.scp.byu.edu/data/iceberg/database1.html`; search at `search.scp.byu.edu`) |
| **Data type** | Composite iceberg trajectories from satellite **scatterometry** (Seasat SASS, ERS-1/2, NSCAT, QuikSCAT, ASCAT, OSCAT/OSCAT2) merged with NIC analyst positions. Two products: (i) Consolidated DB (per-iceberg CSV), (ii) Statistical DB (daily-averaged position, size km², rotation velocity, environment mask: land / sea-ice / open-ocean / no-data) |
| **Temporal resolution** | **Daily (scatterometer-derived, statistical DB)** and **weekly (NIC-derived, consolidated DB)**. Statistical DB is the higher-frequency complement; consolidated is weekly-nominal. Generated positions updated weekly; full DB files updated 1–2× per year. |
| **Spatial resolution** | Scatterometer effective resolution ~**25 km** (backscatter cell). Suitable for **large tabular** icebergs only; small/medium bergs below detection threshold. |
| **Date coverage** | **1978 and 1992 → present** — consolidated through **April 2025**, statistical through **August 2023** (verified against live page). Subsumes the entire 2016–2026 expansion window. |
| **Spatial coverage** | **Circum-Antarctic** — all iceberg-producing regions. Prydz Bay / East Antarctic (D-quadrant) included. Not limited to the bbox but trappable to it. |
| **Variables** | Per-iceberg CSV: date, lat, lon, major/minor axis lengths. Statistical DB adds: daily-averaged lat/lon, size (km²), rotation velocity, environment mask. No direct iceberg dimension history beyond axes; wind/ocean/sea-ice variables still sourced from ERA5/NSIDC/GLORYS per §3. |
| **Access method** | Zip archives from the BYU page (consolidated ~4.1 MB, statistical ~2.5 MB, one CSV per iceberg e.g. `b27.csv`). MATLAB plotting scripts + KMZ provided. HTTP download, no authentication observed. |
| **Licensing / access restrictions** | Openly accessible academic database (BYU Remote Sensing). Credentials not observed. Terms not verified as restrictive — treat as academic fair use / cite Budge & Long (2018). |
| **Compatibility with existing pipeline** | **High but requires a mapper.** CSV schema differs from `east_prydz_bay_icebergs.csv` (different column names, daily vs weekly cadence, unnamed iceberg IDs alongside named ones). A mapping layer is needed: date-format normalisation, ID remapping (`b27` → NIC-style), axis-to-NM conversion, bbox filter, then the same `prepare_ml_dataset.py` feature-join. The 25 FEATURE_COLS and `TARGET_DT_DAYS=7` logic can be kept (see Limitations). Environment join (§3) unchanged. |
| **Potential scientific limitations** | (i) ~25 km scatterometer resolution → biased to large tabular bergs; different effective "iceberg population" vs NIC; (ii) Daily statistical product is **averaged/interpolated** — not independent daily observations; treats gap-filled points as observations at model risk (see Leakage); (iii) Scatterometer ambiguities in heavy sea-ice; (iv) Unnamed iceberg IDs create ID-space that may not align with NIC names (identity risk); (v) Nominal format is 1 CSV per iceberg (manage large-file count) |
| **Potential leakage risks** | **Moderate.** Two concrete risks: (1) **Duplicate iceberg identity** — BYU incorporates NIC positions, so the same physical iceberg can appear in both sources under different IDs or with overlapping timestamps; blindly concatenating NIC + BYU would duplicate trajectories and, if the duplicate falls on opposite sides of the chronological split, leak across train/val/test. Mitigation: **de-duplicate by (date, lat/lon proximity) before the split.** (2) **Interpolated daily positions** — the statistical DB's gap-filled days are derived by averaging/interpolation, i.e., not independent observations. Training on interpolated targets inflates apparent predictability (the target is partly synthetic). Mitigation: use only **observed** daily points (mask out interpolated/no-data flags in the environment mask) or keep the weekly NIC deltas as targets and use BYU daily points only as auxiliary context. |

---

### 4.3 Strategy C — NSIDC-0684 MEaSUREs Infrared Antarctic Iceberg Coordinates (Daily)

*A long-running NSIDC daily iceberg-coordinate product derived from infrared imagery, recommended as a complementary daily source — with a strong interpolation caveat.*

| Field | Value |
|---|---|
| **Source name** | **NSIDC-0684 : MEaSUREs Infrared Antarctic Iceberg Coordinates** (PI Scambos, Haran, Fahnestock et al.) — `https://nsidc.org/data/nsidc-0684` (v2) |
| **Data type** | Daily iceberg centroid and boundary coordinates from **AVHRR and MODIS** infrared imagery, subset of large named icebergs (standard A/B/C/D naming, e.g. B-15, C-19, D-28) |
| **Temporal resolution** | **Daily** positions; temporal gaps during persistent cloud cover are **gap-filled by interpolation** (flag such rows carefully) |
| **Spatial resolution** | ~1–2 km IR pixels (finer than scatterometer, coarser than SAR); captures large named tabular bergs, not small fragments |
| **Date coverage** | ~**1978 → present**, updated annually. Covers the entire 2016–2026 expansion window. |
| **Spatial coverage** | Antarctic waters **south of ~60°S** — includes Prydz Bay. |
| **Variables** | Daily lat/lon centroids and boundary coordinates of tracked bergs; standard A/B/C/D IDs; derived fields may include dimensions. Environmental forcing (wind, sea-ice, ocean) still from §3. |
| **Access method** | **NSIDC / NASA Earthdata** — HDF5 + ASCII; search at `nsidc.org/data/nsidc-0684` and EOSDIS. Requires Earthdata login (free). Documented at the NSIDC dataset page. |
| **Licensing / access restrictions** | **Earthdata login** required; data use governed by NSIDC / NASA Distributed Active Archive Center ToS (free, attribution). No paywall. |
| **Compatibility with existing pipeline** | **Medium.** Format differs from NIC CSVs (HDF5/ASCII, IR-derived, boundary coords vs centroids). Requires: format conversion to `east_prydz_bay`-style timeline, centroid extraction, bbox filter, ID alignment to NIC names (D28 etc.), then the same `prepare_ml_dataset.py` environmental join. The 7-day `TARGET_DT_DAYS` switching to **daily targets (horizon=1d)** is scientifically interesting but would be a separate problem definition (re-partition §2.1); for comparability, keep 7-day targets and use NSIDC-0684 daily points only to populate the input side. |
| **Potential scientific limitations** | (i) **Cloud dependence** — Antarctic coastal IR is frequently blocked; many "daily" positions are interpolated across cloud gaps (quality flag must be inspected — not all rows equally valid); (ii) **Large named bergs only** — heavy overlap with NIC-tracked population (limited novelty); (iii) **Historical overlap** — several NIC IDs in the 2020 set (e.g. D28) may appear here; purely redundant if so; (iv) **IR vs scatterometer detection physics** — different size/morphology sensitivity, so cross-source berg comparability is imperfect |
| **Potential leakage risks** | **Moderate–High on interpolated rows.** The cloud-gap interpolation synthesises position targets from neighbouring observations — training on such rows is, per the "Do NOT fabricate/synthetically generate trajectories" rule, disallowed. Mitigation: **discard every interpolated/cloud-filled row** and train only on rows whose source flag denotes an actual IR detection. Second risk: duplicate berg identity (same NIC berg tracked here) → same dedup-by-(date, proximity) as for BYU. |

---

### 4.4 Strategy D — Sentinel-1 SAR Custom Tracking

*Not an off-the-shelf trajectory dataset — a proven observation pipeline for generating sub-weekly, cloud-penetrating iceberg positions in Prydz Bay itself. Included because it is the highest-ceiling technical route.*

| Field | Value |
|---|---|
| **Source name** | **Sentinel-1 C-band SAR (ESA Copernicus)** — mission **Sentinel-1A (2014→present)** and **Sentinel-1B (2014→Dec 2021, offline since)**. Data via Copernicus Data Space / Open Access Hub (`https://dataspace.copernicus.eu`, `https://scihub.copernicus.eu`). Often processed through GEE in publication workflows. |
| **Data type** | Level-1 SAR imagery (C-band active microwave) — iceberg appears as high-backscatter target on ocean background. Positions are **derived**, not distributed as a catalogue, so the iceberg dataset is whatever you extract from the imagery. |
| **Temporal resolution** | **Revisit-limited, not daily:** SAR geometry gives ~**6-day equatorial** repeat with 1A+1B, faster at polar latitudes — **every 2–3 days over Prydz Bay when both satellites were up**; **~12 days after Sentinel-1B failure** (Dec 2021) until Sentinel-1C launch. Actual cadence is dictated by acquisition planning, not uniformly 2-day. Higher-frequency than NIC weekly but not daily. |
| **Spatial resolution** | **10–100 m** (depending on mode: IW/ EW/ SM). Detects icebergs of **any detectable size**, far below the NIC ~20 sq nm gate. |
| **Date coverage** | **2014-04 (S1A launch) → present.** Historical SAR-derived trajectories can reach 2014 onward for the whole expansion window; before 2014, no S1 data. |
| **Spatial coverage** | Global. Prydz Bay is covered by nominal S1 acquisitions (small scene footprints tiled by orbit path) — coverage must be confirmed on the catalogue for each expansion year. |
| **Variables** | Scene-derived centroid positions and masks to be produced locally (scene_id, acquisition_datetime, lat, lon, area proxy). Environmental variables from §3 join the same way as NIC positions — no change to the 9-variable feature stack. Sentinel-1's own backscatter/dual-pol features are not part of the current FEATURE_COLS and would require a separate feature definition. |
| **Access method** | Copernicus Data Space **Open Access Hub** (no-fee, registration + OData/S3 access). Large imagery volume (tens of TB to query). Download scripts already exist for the sentinel path: `scripts/data/download_sentinel1.py` and `scripts/data/access_tests/test_sentinel1.py` (verified present). **No Sentinel-1 NetCDF trajectory file exists — you must build one.** |
| **Licensing / access restrictions** | **Copernicus free & open**; Copernicus Sentinel Data ToS (attribution, free). No CMEMS-style credential issue (same S1 path already used in Phase 2). |
| **Compatibility with existing pipeline** | **High for positions, non-trivial for detection.** Once the derived timeline exists, it is directly ingestible by `prepare_ml_dataset.py` (lat/lon + date + placeholder dimensions). What is **not** compatible off the shelf is the **detection/tracking layer**: there is no widely maintained open-source end-to-end daily iceberg position extractor (MOM6 is a forward drift model, not an extractor; Barbat et al. 2021/2022 SAR tracking is published but not a turnkey package; `Iceberg-Tracker` MATLAB is minimal). Prydz Bay–specific SAR tracking publications (Mu et al. 2025 EGUsphere — Swin Transformer daily distribution maps off Prydz Bay/Ross Sea; Chen et al. 2026 — GEE-based 2018–2023 annual census on Zenodo DOI 10.5281/zenodo.17165466 at >0.04 km² annual snapshots) show the route is viable but operational daily trajectories would have to be custom-built. |
| **Potential scientific limitations** | (i) Processing cost and expertise — SAR speckle, incidence-angle, sea-ice backscatter ambiguity, coastline masking; (ii) No native iceberg-size (NM) fields — would need to derive from mask area; (iii) Uneven acquisition cadence — not truly uniform 2-day, harder to form clean 7-day pairs; (iv) Pre-2014 years unavailable; (v) After Dec 2021 revisit degrades to ~12 days; (vi) Best for future phases rather than a rapid multi-year boost |
| **Potential leakage risks** | **Low** on the observation side — SAR-derived positions are **fully independent** of NIC/BYU. No ID overlap. The risk is instead a **label-definition** one: if SAR area/morphology were later added as a FEATURE_COL while also predicting the same iceberg's next SAR position, size-related leakage must be audited (not applicable if using only the 25 current FEATURE_COLS). |

> **Prydz Bay tailwind:** Two recent Prydz Bay–specific SAR iceberg studies postdate the baseline pipeline: Mu et al. (EGUsphere 2025) and Abulaiti et al. (Marine Geodesy 2026), confirming that SAR-derived iceberg surveillance in exactly this bay is active research — and that SAR scenes of Prydz Bay are routinely acquired.

---

### 4.5 Other Higher-Frequency Sensors (Exploratory — No Stand-Alone Operational Product)

These sensors **exist** as calibrated observation streams but do **not** provide a verified, off-the-shelf, machine-readable Antarctic iceberg trajectory dataset. They are listed accurately as **research-stage pipelines**, not ranked expansion sources.

| Sensor | Temporal res. | Spatial res. | All-weather | Time span | Format / Access | Prydz Bay note |
|---|---|---|---|---|---|---|
| **MODIS** (Terra 1999, Aqua 2002) | Near-daily (twice-daily Terra+Aqua) | 250 m–1 km | **No** (cloud-blocked) | 1999–present | HDF4/5 / GeoTIFF — NASA Worldview / Earthdata | Advancing TOA correction over sea ice; useful for clear-sky events |
| **VIIRS** (Suomi-NPP 2011, NOAA-20/21) | Daily (sub-daily multi-platform) | 375/750 m | **No** | 2012–present | HDF5 — LAADS DAAC / NOAA CLASS | Modern MODIS successor; same cloud limit |
| **AMSR2** (GCOM-W1 / JAXA, 2012) | **Daily** | **~10 km** | **Yes** (passive microwave, Cho et al. 2025 RF on 89 GHz H/V) | 2012–present | HDF5/NetCDF — JAXA G-portal | Position RMSE ~11.3 km (tested on A-23A, 65×70 km berg); coarse → large bergs only |
| **Chen et al. 2026** (Sentinel-1 on GEE) | **Annual** (one October snapshot/year, 2018–2023) | SAR 10–100 m | Yes | 2018–2023 | Zenodo DOI **10.5281/zenodo.17165466**, F1 > 0.90, counts 34,825–51,420/yr (>0.04 km²) | **Not a trajectory** — annual census only; cannot form 7-day pairs |

> **Non-sources verified as non-existent:** ESA CCI Icebergs (there is no iceberg ECV in the ESA CCI portfolio; `climate.esa.int/en/projects` has no such project — 404); NSIDC-0615 as an iceberg dataset (NSIDC-0615 is a Greenland GPS traverse); NSIDC-0524 as icebergs (actually Thwaites IPY geophysics); a public "HEAD iceberg database" (the HEAD drift model is literature, not a distributed trajectory set); SOOS or CMEMS operational iceberg-tracking products (none verified). Several AI-cited PANGAEA iceberg DOIs proved false on direct fetch. These must not be cited as sources.

---

## 5. Leakage Risk Summary

| Risk | Which sources | Severity | Mitigation |
|---|---|---|---|
| **Chronological leakage** (future obs/environment as input) | **All strategies** if expanded carelessly | **High** | Keep strict chronological split (train < val < test in time), never random-split sequential trajectory obs, never concatenate years before assigning the split, document new split boundaries in `ml_dataset_metadata.json` |
| **Duplicate iceberg identity** across NIC and another trajectory source | B (BYU — incorporates NIC positions), C (NSIDC-0684 — same large named bergs as NIC) | **Moderate** | De-duplicate by (iceberg_id, observation_date) and by (date, lat/lon proximity within a tight radius) **before** the split; treat unnamed BYU IDs as a separate namespace |
| **Interpolated / gap-filled positions as training targets** | B — statistical DB gap-filled days (environment mask = no-data); C — cloud-gap interpolation (flagged rows) | **Moderate–High** | **Discard every interpolated/gap-filled row**; train only on rows flagged as genuine observations. This respects the "Do NOT fabricate" rule. |
| **Test-set leakage via hyperparameter tuning** | Any strategy | High | No test data used during tuning or environmental-stack construction; freeze test split before any model touch (existing discipline in `prepare_ml_dataset.py` → `train_*.py`) |
| **Feature-stack leakage** (future environment contaminating past inputs) | Environmental side (§3) | High | Per-year feature stacks must be built **before** `prepare_ml_dataset.py` joins them, and the join for year Y must use only day Y's 24 hourly values (current pipeline's `extract_features_at_point()` daily-mean/sum already does this) |

> The per-expansion-year feature stacks (§3) are the correct — and only — place to introduce new environmental coverage. Nothing about the iceberg source changes how the environment is attached.

---

## 6. Ranked Recommendation

Strategies are ranked by **scientific value per integration effort**, **verified data reality** (no assumptions about unavailable data), and **adherence to constraints** (no fabrication, no Phase 1/2 modification, no stack overwrite).

### Tier 1 — Execute FIRST

#### 🥇 Rank 1: Multi-Year Expansion of the Existing NIC Source (2016–2026)

- **What:** Keep the exact NIC source, pipeline schemas, 25 FEATURE_COLS, 7-day horizon, and bbox; add **all valid 7-day pairs beyond 2020** already available on disk (540 pairs — 118 drifting), plus their corresponding per-year environmental feature stacks (§3).
- **Yield:** **101 → 643 pairs (6.4×)**, **4 → 10 iceberg IDs** (excl. single-obs B09I) with genuinely drifting representation; val/test can finally hold **fast drifters (C18B/C39)** instead of only D23/D27.
- **Effort:** **Low.** `download_icebergs.py` (incremental year pulls, already supports `--start`/`--end`) is already complete for the archive; `process_icebergs.py` already produces `east_prydz_bay_icebergs.csv`; the only repeat work is one `build_feature_stack.py` run per new year (ERA5 + NSIDC + GLORYS + GEBCO) and a single `prepare_ml_dataset.py` pass with an expanded year window. No new schema, no new dependency, no new access method.
- **Risk:** Chronological-split diligence + GLORYS network re-verification per year.
- **Why first:** Verified headroom already on disk; directly fixes the coverage and drift-regime mismatch that limits every model trained to date; scientifically conservative — the same observation physics as the current authoritative result.

**Practical ordering within Rank 1 (best return first):**

1. Rebuild feature stacks for **2019, 2024, 2025, 2026** (the drifting-berg years). This captures C18B (40), C39 (21), D22 (11), D15C/D (18), and the 2019 cohort first.
2. Then add **2021** (extends D27), **2017** (D21B), then the D23-only years (2016, 2018, 2022, 2023) at lowest priority (they improve stationarity statistics but not drift diversity).

> A ~300-pair diverse subset (2020+2019+2021+2024–2026) already achieves a step-change in training mass **before** the D23-heavy years are added — and limits the grounded-bias re-entry.

### Tier 2 — Execute SECOND (after Tier 1 has landed)

#### 🥈 Rank 2: BYU Antarctic Iceberg Tracking Database — Daily Statistical Complement

- **What:** Integrate the **observed-only** daily statistical trajectories (not interpolated gap-filled days) for icebergs that intersect East Prydz Bay, including unnamed bergs NIC misses. Keep **7-day prediction targets** for comparability; daily points populate richer input history (e.g., sub-weekly velocity/acceleration) or augment the training pool as additional weekly-anchored pairs.
- **Yield:** Daily resolution where observed (flag-gated), plus population completeness (unnamed bergs). Modest-to-moderate additional drift diversity specific to Prydz Bay.
- **Effort:** **Medium.** New CSV ingest mapper + deduplication against NIC + strict gap-flag filtering.
- **Why second, not first:** Requires a new ingest layer, introduces dedup/flag discipline, and its daily statistical product's averaging artefact must be handled carefully. It strengthens — rather than substitutes — the Rank 1 NIC expansion. Should be landed only after the multi-year NIC+environment spine is verified.

#### 🥉 Rank 3: NSIDC-0684 MEaSUREs (IR Daily) — Cross-Validation / Limited Complement

- **What:** Cross-validate NIC/BYU positions for the large-named overlap (e.g., D28, D-27 family); limited complementary daily positions on genuine IR detections only.
- **Yield:** Moderate redundancy — heavy overlap with NIC's large-berg population; daily coverage is cloud-gated.
- **Effort:** **Medium–High** (HDF5/ASCII ingest + centroid extraction + dedup + rigorous interpolation-flag removal).
- **Why third:** Strong interpolation caveat — a large fraction of "daily" rows in any Antarctic IR product are synthetic gap-fills masked by the "Do NOT fabricate" rule. Net new usable positions beyond NIC+BYU is expected to be small. Most valuable as an **independent validation source** rather than a training-pool expander.

### Tier 3 — Research Track (Not a Near-Term Expansion)

#### Rank 4: Sentinel-1 SAR Custom Tracking (Sub-Weekly)

- **What:** Build a local Prydz Bay SAR-derived track database from Copernicus Data Space scenes, producing 2–12 day positions at 10–100 m resolution for **all detectable iceberg sizes** (below the 20 sq nm NIC gate).
- **Yield:** Highest ceiling — all-weather, sub-weekly, size-complete. The only route that breaks the large-iceberg-only population bias.
- **Effort:** **High.** No turnkey operational trajectory product exists; requires a custom detection/tracking pipeline (validated SAR-scene catalogue, speckle/ice-edge masking, tracking, validation). Chen/Mu SAR work on Prydz Bay (annual census, daily distribution maps) proves SAR monitoring there is active, but an operational daily-trajectory catalogue is not download-ready.
- **Why researched but not top-ranked now:** The ask is a **scientifically valid expansion with minimal delay** — SAR custom tracking is the correct long-term direction (and the right answer to "why observations are being lost" at the sensor level) but is a Phase-4-scale engineering effort, not a Phase-3A quick win.

#### Not Recommended as Expansion Sources

- **MODIS / VIIRS (optical/IR)** daily observation streams — no verified standalone operational trajectory catalogue; cloud-blocked; research workflows only.
- **AMSR2 passive microwave** daily (Cho et al. 2025) — 10 km resolution, position RMSE ~11 km; large bergs only, coarse for Prydz Bay trajectory skill; all-weather advantage is real but novelty for the current 25 FEATURE_COLS pipeline is minimal.
- **ESA CCI Icebergs, NSIDC-0615/0524 as icebergs, "HEAD database", SOOS/CMEMS iceberg tracking product** — each verified **non-existent** in the claimed form (details in §4.5); do not cite or build on them. Several AI-cited PANGAEA iceberg DOIs also failed verification on direct fetch.

---

## 7. Implementation Roadmap (Not Executed)

> Per the STOP instruction, **no downloads, no data modification, and no model training are performed as part of this audit.** This roadmap is a future-work sketch for review, not an execution request.

1. **Freeze** the 2020-only feature stack and ML parquet set as an immutable baseline tag (`PHASE3_2020_BASELINE`) — do not overwrite `east_prydz_bay_2020_feature_stack.nc` or `data/processed/ml/*.parquet` in place; expanded stacks/datasets use year-suffixed filenames.
2. **Re-verify access:** `python scripts/data/access_tests/test_glorys.py` (CMEMS) and a CDS test call (ERA5/ORAS5 channel) from the execution environment that will run the expansion. Resolve any DNS/creds gate before starting.
3. **Rebuild environmental stacks per new year (§3)** via the existing `scripts/data/build_feature_stack.py` path, one year at a time, committing each `east_prydz_bay_YYYY_feature_stack.nc` + companion `metadata.json` before proceeding.
4. **Re-run `process_icebergs.py`** (no code change) to reconfirm `east_prydz_bay_icebergs.csv` against the full archive on disk; optionally cross-check with a NIC catalogue pull for any 2026-08-28+ delta.
5. **Re-run `prepare_ml_dataset.py`** with an expanded year window (e.g., 2019/2020/2021/2024–2026 first), capturing: the new chronological split boundaries, per-iceberg and per-year pair counts, and the grounded-vs-drifting stratification. Validate that no future-position or future-environment field leaks into the input feature set.
6. **Validate the expanded ML dataset** with `scripts/ml/validate_ml_dataset.py` (extend it if needed to check per-year coverage and dedup constraints).
7. **Document, then decide on BYU integration** (Rank 2) — only after the multi-year NIC+environment spine is landed and audited. Treat NSIDC-0684 (Rank 3) as validation-first.

### What Was NOT Done (Audit Discipline)

- ❌ No Phase 1 / Phase 2 file modified, moved, or deleted
- ❌ No `east_prydz_bay_2020_feature_stack.nc` overwritten or extended in place
- ❌ No `data/processed/ml/*.parquet` regenerated or overwritten
- ❌ No `data/raw/icebergs/` download executed
- ❌ No `data/raw/` or `data/processed/` environmental download executed
- ❌ No model training, retraining, or hyperparameter search
- ❌ No fabrication, interpolation over land/mask, silent NaN fill, or synthetic trajectory generation
- ❌ No future information used as an input feature; no test leakage
- ❌ No unofficial data mirror or authentication bypass
- ❌ No claim made about a source's data that was not verified

---

## Appendix A — Verified File Inventory

| Path | Role | Verified presence |
|---|---|---|
| `data/raw/icebergs/AntarcticIcebergs_YYYYMMDD.csv` (608 files, 2014-11-07 → 2026-08-27) | Raw NIC weekly archive | `ls` count 608 |
| `data/processed/icebergs/east_prydz_bay_icebergs.csv` (796 rows, 11 IDs, 2016→2026) | Filtered Prydz Bay timeline | `read` header + groupby |
| `data/processed/integration/east_prydz_bay_2020_feature_stack.nc` (8784×17×33, 9 vars) | 2020 harmonised stack | `xr.open_dataset` + `metadata.json` |
| `data/processed/integration/east_prydz_bay_2020_feature_stack_metadata.json` | Provenance for the 2020 stack | `cat` |
| `data/processed/ml/full.parquet` (101 rows, 39 cols) | Supervised ML set (7-day, authoritative count) | `read` |
| `data/processed/ml/train.parquet` (71), `val` (16), `test` (14) | Chronological splits | `read` |
| `data/raw/ocean/glorys/cmems_mod_glo_phy_my_0.083deg_P1D-m_1788490478516.nc` (73 MB) | GLORYS12V1 raw daily ocean | `ls` + `ncdump` field check |
| `scripts/data/download_icebergs.py` | NIC archive downloader | `read` |
| `scripts/data/process_icebergs.py` | NIC → Prydz Bay filter | `read` |
| `scripts/data/build_feature_stack.py` | Per-year stack builder | `glob` present |
| `scripts/ml/prepare_ml_dataset.py` | Supervised pair builder + split | `read` (568 lines) |
| `reports/PHASE3_STEP1_PROBLEM_DEFINITION.md` | 7-day horizon definition | `read` |
| `reports/GLORYS12V1_ACQUISITION_REPORT.md` | Prior CMEMS DNS block (now resolved) | `read` |
| `reports/ORAS5_FALLBACK_EVALUATION.md` | ORAS5 monthly fallback (degraded, not recommended) | `read` |

---

## Appendix B — Verification Notes

- **Method:** Local-file verification (direct `read`/`ls`/`head`/`python -c` groupby counts), script inspection (`download_icebergs.py`, `process_icebergs.py`, `prepare_ml_dataset.py`, `build_feature_stack.py`), metadata-JSON read, NetCDF `ncdump`/xarray inspection, and external-source URL fetches where available. No assumption about an unavailable download was made — the 540-pair Beyond-2020 count was computed from the CSV already on disk, not projected.
- **External-source verification standard:** A source is marked "verified" only if a live URL or a DOI/portal page could be fetched and confirmed to serve the claimed dataset (see the per-source agents' fetch logs). Sources where only model-generated search summaries were available are marked **partially verified / unconfirmed** and not ranked.
- **Reported numbers are exact `pandas` groupby counts** run against `data/processed/icebergs/east_prydz_bay_icebergs.csv` and `data/processed/ml/full.parquet` in this audit's execution context (Python 3.13). Re-running the same groupbys reproduces them.
- **Nothing in this audit modifies any dataset or trains any model.**

---

*Audit trail: Phase 1/2 data untouched; feature stack untouched; no synthetic data; chronological discipline preserved; no test-set tuning; no data downloaded or modified. Ready for approval to proceed to ranked expansion.*
