# PHASE 3A — 2016 & 2018 FEATURE STACK BUILD & VERIFICATION REPORT

**Date:** 2026-09-05  
**Pipeline:** `scripts/data/build_feature_stack_year.py --year YYYY`  
**Status:** ✅ BOTH YEARS BUILT & VERIFIED — **PASS**

---

## 1. INPUT FILES USED

### 2016 (leap year)

| Input | Path | Status |
|---|---|---|
| ERA5 2016 combined | `data/processed/weather/east_prydz_bay_era5_2016-01-01_2016-12-31.nc` | ✅ 43.46 MB, 8784 h, 5 vars, 0% NaN |
| NSIDC sea-ice 2016 | `data/processed/sea_ice/east_prydz_bay_sea_ice_concentration_2016-01-01_2016-12-31.nc` | ✅ 366 d, reprojected + ffill |
| GLORYS 2016 | `data/raw/ocean/glorys/glorys12v1_east_prydz_bay_2016.nc` | ✅ 6.96 MB, 366 d, uo/vo |
| Bathymetry (static) | `data/processed/bathymetry/east_prydz_bay_bathymetry_15arcsec.nc` | ✅ 15 arc-sec, static (reused) |

### 2018 (non-leap year)

| Input | Path | Status |
|---|---|---|
| ERA5 2018 combined | `data/processed/weather/east_prydz_bay_era5_2018-01-01_2018-12-31.nc` | ✅ 43.54 MB, 8760 h, 5 vars, 0% NaN |
| NSIDC sea-ice 2018 | `data/processed/sea_ice/east_prydz_bay_sea_ice_concentration_2018-01-01_2018-12-31.nc` | ✅ 365 d, reprojected + ffill |
| GLORYS 2018 | `data/raw/ocean/glorys/glorys12v1_east_prydz_bay_2018.nc` | ✅ 6.96 MB, 365 d, uo/vo |
| Bathymetry (static) | `data/processed/bathymetry/east_prydz_bay_bathymetry_15arcsec.nc` | ✅ 15 arc-sec, static (reused) |

All required inputs **verified present before build** — no missing data, no substitution.

---

## 2. OUTPUT FILES

| Property | 2016 | 2018 |
|---|---|---|
| **Path** | `data/processed/integration/east_prydz_bay_2016_feature_stack.nc` | `data/processed/integration/east_prydz_bay_2018_feature_stack.nc` |
| **Metadata** | `east_prydz_bay_2016_feature_stack_metadata.json` | `east_prydz_bay_2018_feature_stack_metadata.json` |
| **Size** | **200.66 MB** | **200.32 MB** |

---

## 3. DIMENSIONS

| Dimension | 2016 | 2018 |
|---|---|---|
| `time` | **8,784** (leap: 366 × 24) | **8,760** (non-leap: 365 × 24) |
| `lat` | **17** | **17** |
| `lon` | **33** | **33** |
| **Total grid cells** | 561 (17 × 33) | 561 (17 × 33) |
| **Total data points / var** | 4,927,824 | 4,914,360 |

---

## 4. TEMPORAL COVERAGE

| Property | 2016 | 2018 |
|---|---|---|
| **Start** | 2016-01-01T00:00 | 2018-01-01T00:00 |
| **End** | 2016-12-31T23:00 | 2018-12-31T23:00 |
| **Steps** | 8,784 | 8,760 |
| **Frequency** | Hourly, uniform Δ=1h | Hourly, uniform Δ=1h |
| **Duplicates** | 0 | 0 |
| **Missing timestamps** | 0 | 0 |

---

## 5. SPATIAL COVERAGE

| Property | 2016 | 2018 |
|---|---|---|
| **CRS** | EPSG:4326 (WGS 84) | EPSG:4326 (WGS 84) |
| **Lat bounds** | −70.00 .. −66.00 (17 pts, 0.25°) | −70.00 .. −66.00 (17 pts, 0.25°) |
| **Lon bounds** | 72.00 .. 80.00 (33 pts, 0.25°) | 72.00 .. 80.00 (33 pts, 0.25°) |
| **Uniform spacing** | ✅ | ✅ |
| **Identical to 2020 baseline** | ✅ lat, lon identical | ✅ lat, lon identical |

---

## 6. VARIABLES (9) & MISSING-VALUE STATISTICS

### 2016

| Variable | Source | NaN count | NaN % | Physical Range |
|---|---|---|---|---|
| `sea_ice_concentration` | NSIDC-0051 | 0 | 0.000% | 0 .. 1 |
| `wind_u_10m` | ERA5 (u10) | 0 | 0.000% | −30.36 .. 19.61 m/s |
| `wind_v_10m` | ERA5 (v10) | 0 | 0.000% | −18.35 .. 24.68 m/s |
| `temperature_2m` | ERA5 (t2m) | 0 | 0.000% | 218.17 .. 278.68 K |
| `mean_sea_level_pressure` | ERA5 (msl) | 0 | 0.000% | 91,487 .. 102,760 Pa |
| `total_precipitation` | ERA5 (tp) | 0 | 0.000% | 0 .. 0.00234 m |
| `bathymetry_elevation` | GEBCO (coarsened) | **843,264** | **17.112%** | −2,893.6 .. 73.2 m |
| `ocean_current_u` | GLORYS12V1 (uo) | 0 | 0.000% | −0.529 .. 0.283 m/s |
| `ocean_current_v` | GLORYS12V1 (vo) | 0 | 0.000% | −0.610 .. 0.910 m/s |

### 2018

| Variable | Source | NaN count | NaN % | Physical Range |
|---|---|---|---|---|
| `sea_ice_concentration` | NSIDC-0051 | 0 | 0.000% | 0 .. 1 |
| `wind_u_10m` | ERA5 (u10) | 0 | 0.000% | −27.90 .. 17.48 m/s |
| `wind_v_10m` | ERA5 (v10) | 0 | 0.000% | −15.85 .. 24.42 m/s |
| `temperature_2m` | ERA5 (t2m) | 0 | 0.000% | 227.12 .. 277.84 K |
| `mean_sea_level_pressure` | ERA5 (msl) | 0 | 0.000% | 94,835 .. 103,050 Pa |
| `total_precipitation` | ERA5 (tp) | 0 | 0.000% | 0 .. 0.00237 m |
| `bathymetry_elevation` | GEBCO (coarsened) | **840,960** | **17.112%** | −2,893.6 .. 73.2 m |
| `ocean_current_u` | GLORYS12V1 (uo) | 0 | 0.000% | −0.664 .. 0.387 m/s |
| `ocean_current_v` | GLORYS12V1 (vo) | 0 | 0.000% | −0.575 .. 0.863 m/s |

**Bathymetry NaN (17.1%)** = 96 land cells × timesteps — **expected**. NaN mask **identical to 2020 baseline**.

---

## 7. GLORYS VALIDATION

### 2016
- `ocean_current_u`: 4,927,824 / 4,927,824 non-NaN (100%), **99.4% > 1e-6 m/s**
- `ocean_current_v`: 4,927,824 / 4,927,824 non-NaN (100%), **99.4% > 1e-6 m/s**
- Cross-correlation u/v = **0.239** (non-degenerate)

### 2018
- `ocean_current_u`: 4,914,360 / 4,914,360 non-NaN (100%), **99.4% > 1e-6 m/s**
- `ocean_current_v`: 4,914,360 / 4,914,360 non-NaN (100%), **99.4% > 1e-6 m/s**
- Cross-correlation u/v = **0.262** (non-degenerate)

**GLORYS present and non-empty: ✅** for both years.

---

## 8. BATHYMETRY VALIDATION

Both years:
- Static over time: ✅ `b[0] == b[5000]` (allclose, equal_nan)
- NaN mask identical to 2020 baseline: ✅
- Elevation values identical to 2020 baseline: ✅ (atol 0.01 m)

**Bathymetry static and consistent with baseline: ✅**

---

## 9. PROCESSING STEPS (unchanged pipeline)

1. Define common grid from ERA5 (0.25° 17×33, EPSG:4326)
2. Standardise ERA5 (rename u10→wind_u_10m, etc.)
3. Reproject sea ice (polar-stereo → 0.25° nearest-neighbor, daily→hourly ffill)
4. Coarsen bathymetry (15 arc-sec → 0.25°, factor=60); broadcast across time
5. Resample GLORYS (1/12° daily → 0.25° hourly nearest-neighbor + ffill)
6. Merge 9 variables → single Dataset; write NC + metadata JSON

**No new methodology introduced.**

---

## 10. VALIDATION RESULTS (15 CHECKS)

| # | Check | 2016 | 2018 |
|---|---|---|---|
| 1 | File exists and readable | ✅ 200.66 MB | ✅ 200.32 MB |
| 2 | Temporal coverage | ✅ 01-01→12-31 | ✅ 01-01→12-31 |
| 3 | Timestep count (leap-aware) | ✅ 8,784 (leap) | ✅ 8,760 |
| 4 | No missing timestamps | ✅ 0 | ✅ 0 |
| 5 | No duplicate timestamps | ✅ 0 | ✅ 0 |
| 6 | Spatial grid 17×33 | ✅ | ✅ |
| 7 | Coords match 2020 baseline | ✅ | ✅ |
| 8 | All 9 variables present | ✅ | ✅ |
| 9 | Variable dims correct | ✅ | ✅ |
| 10 | Missing-value stats | ✅ bathy 17.1% | ✅ bathy 17.1% |
| 11 | Physical ranges valid | ✅ | ✅ |
| 12 | GLORYS present & non-empty | ✅ corr=0.239 | ✅ corr=0.262 |
| 13 | Bathymetry static & baseline-consistent | ✅ | ✅ |
| 14 | Sea-ice coverage | ✅ 100% finite | ✅ 100% finite |
| 15 | No schema changes + files untouched | ✅ | ✅ |

**2016: 15/15 PASS**
**2018: 15/15 PASS**

---

## 11. FILES CREATED

| File | Size |
|---|---|
| `data/processed/integration/east_prydz_bay_2016_feature_stack.nc` | 200.66 MB |
| `data/processed/integration/east_prydz_bay_2016_feature_stack_metadata.json` | ~7 KB |
| `data/processed/integration/east_prydz_bay_2018_feature_stack.nc` | 200.32 MB |
| `data/processed/integration/east_prydz_bay_2018_feature_stack_metadata.json` | ~7 KB |

---

## 12. FILES MODIFIED

**None.** Pipeline only writes new files; no existing dataset was overwritten.

---

## 13. FILES CONFIRMED UNTOUCHED

| File | mtime | Status |
|---|---|---|
| `data/processed/icebergs/east_prydz_bay_icebergs.csv` | 2026-09-04 02:21 | ✅ Phase 1 |
| `data/processed/bathymetry/east_prydz_bay_bathymetry_15arcsec.nc` | 2026-09-04 02:16 | ✅ Phase 1 |
| `east_prydz_bay_2017_feature_stack.nc` | 2026-09-05 12:32 | ✅ |
| `east_prydz_bay_2019_feature_stack.nc` | 2026-09-04 20:31 | ✅ |
| `east_prydz_bay_2020_feature_stack.nc` | 2026-09-04 08:52 | ✅ baseline |
| `east_prydz_bay_2021_feature_stack.nc` | 2026-09-05 02:04 | ✅ |
| `east_prydz_bay_2024_feature_stack.nc` | 2026-09-05 00:03 | ✅ |
| `east_prydz_bay_2025_feature_stack.nc` | 2026-09-05 01:09 | ✅ |

**Zero Phase 1, Phase 2, or existing feature-stack data modified.**

---

## 14. UPDATED MULTI-YEAR STATUS

| Year | Size | Steps | Grid | Vars | Status |
|---|---|---|---|---|---|
| **2016** | **200.66 MB** | **8,784** | **17×33** | **9** | ✅ **NEW — VERIFIED (15/15)** |
| 2017 | 200.48 MB | 8,760 | 17×33 | 9 | ✅ VERIFIED (15/15) |
| **2018** | **200.32 MB** | **8,760** | **17×33** | **9** | ✅ **NEW — VERIFIED (15/15)** |
| 2019 | 200.47 MB | 8,760 | 17×33 | 9 | ✅ VERIFIED |
| 2020 | 201.36 MB | 8,784 | 17×33 | 9 | ✅ baseline |
| 2021 | 200.72 MB | 8,760 | 17×33 | 9 | ✅ VERIFIED (15/15) |
| 2022 | — | — | — | — | ❌ BLOCKED (ERA5/NSIDC/GLORYS absent) |
| 2023 | — | — | — | — | ❌ BLOCKED (ERA5/NSIDC/GLORYS absent) |
| 2024 | 200.89 MB | 8,784 | 17×33 | 9 | ✅ VERIFIED |
| 2025 | 200.28 MB | 8,760 | 17×33 | 9 | ✅ VERIFIED |
| 2026 | — | — | — | — | ❌ BLOCKED (ERA5/NSIDC absent, GLORYS partial) |

**Complete & verified: 8/11 years** (was 6/11 before this step)

---

## 15. FINAL STATUS

| Metric | Value |
|---|---|
| **2016 FEATURE STACK** | **PASS (15/15)** |
| **2018 FEATURE STACK** | **PASS (15/15)** |
| **HOURLY STEPS** | 8,784 (2016 leap) / 8,760 (2018 non-leap) |
| **GRID** | 17 × 33, 0.25°, EPSG:4326 (East Prydz Bay) |
| **VARIABLES** | 9 per year |
| **PHASE 1/2 INTACT** | **YES** |
| **EXISTING STACKS INTACT** | **YES** |
| **FILES MODIFIED** | **NONE** |
| **NEXT STEP** | **Await approval** — remaining: 2022, 2023, 2026 |

---

> **STOPPING HERE.**  
> Do NOT download ERA5/NSIDC/GLORYS for 2022, 2023, or 2026.  
> Do NOT combine years into a multi-year dataset.  
> Do NOT rebuild the ML dataset.  
> Do NOT retrain any model.
