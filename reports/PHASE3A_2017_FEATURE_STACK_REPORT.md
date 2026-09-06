# PHASE 3A — 2017 FEATURE STACK BUILD & VERIFICATION REPORT

**Date:** 2026-09-05  
**Pipeline:** `scripts/data/build_feature_stack_year.py --year 2017`  
**Status:** ✅ BUILT & VERIFIED — **PASS**

---

## 1. INPUT FILES USED

| Input | Path | Status |
|---|---|---|
| ERA5 2017 combined | `data/processed/weather/east_prydz_bay_era5_2017-01-01_2017-12-31.nc` | ✅ 43.70 MB, 8760 h, 5 vars, 0% NaN |
| NSIDC sea-ice 2017 | `data/processed/sea_ice/east_prydz_bay_sea_ice_concentration_2017-01-01_2017-12-31.nc` | ✅ 365 d, reprojected + ffill |
| GLORYS 2017 | `data/raw/ocean/glorys/glorys12v1_east_prydz_bay_2017.nc` | ✅ 6.96 MB, 365 d, uo/vo |
| Bathymetry (static) | `data/processed/bathymetry/east_prydz_bay_bathymetry_15arcsec.nc` | ✅ 15 arc-sec, static (reused) |
| Icebergs (NIC) | `data/processed/icebergs/east_prydz_bay_icebergs.csv` | ✅ 796 rows (not merged into grid) |

All required 2017 inputs **verified present before build** — no missing data, no substitution.

---

## 2. OUTPUT FILE

| Property | Value |
|---|---|
| **Path** | `data/processed/integration/east_prydz_bay_2017_feature_stack.nc` |
| **Metadata** | `data/processed/integration/east_prydz_bay_2017_feature_stack_metadata.json` |
| **Size** | **200.48 MB** (200,480,000 bytes) |

---

## 3. DIMENSIONS

| Dimension | Value |
|---|---|
| `time` | **8,760** (hourly) |
| `lat` | **17** |
| `lon` | **33** |
| **Total grid cells** | 561 (17 × 33) |
| **Total data points / variable** | 4,914,360 |

---

## 4. TEMPORAL COVERAGE

| Property | Value |
|---|---|
| **Start** | 2017-01-01T00:00 |
| **End** | 2017-12-31T23:00 |
| **Steps** | 8,760 (2017 non-leap year: 365 × 24) |
| **Frequency** | Hourly, **uniform** (Δ = 1 hour, all 8,759 intervals) |
| **Duplicates** | 0 |
| **Missing timestamps** | 0 |

---

## 5. SPATIAL COVERAGE

| Property | Value |
|---|---|
| **CRS** | EPSG:4326 (WGS 84) |
| **Lat bounds** | −70.00 .. −66.00 (17 pts, 0.25° step) |
| **Lon bounds** | 72.00 .. 80.00 (33 pts, 0.25° step) |
| **Uniform spacing** | ✅ lat & lon |
| **Identical to 2020 baseline** | ✅ lat, lon identical |
| **Identical to 2021 stack** | ✅ lat, lon identical |

---

## 6. VARIABLES (9) & MISSING-VALUE STATISTICS

| Variable | Source | Dims | NaN count | NaN % | Physical Range |
|---|---|---|---|---|---|
| `sea_ice_concentration` | NSIDC-0051 (daily → hourly ffill) | (8760, 17, 33) | 0 | 0.000% | 0.0 .. 1.0 |
| `wind_u_10m` | ERA5 (u10) | (8760, 17, 33) | 0 | 0.000% | −34.80 .. 24.42 m/s |
| `wind_v_10m` | ERA5 (v10) | (8760, 17, 33) | 0 | 0.000% | −22.29 .. 22.31 m/s |
| `temperature_2m` | ERA5 (t2m) | (8760, 17, 33) | 0 | 0.000% | 223.75 .. 277.35 K |
| `mean_sea_level_pressure` | ERA5 (msl) | (8760, 17, 33) | 0 | 0.000% | 92,966 .. 102,140 Pa |
| `total_precipitation` | ERA5 (tp) | (8760, 17, 33) | 0 | 0.000% | 0 .. 0.00352 m |
| `bathymetry_elevation` | GEBCO 2024 (coarsened + broadcast) | (8760, 17, 33) | **840,960** | **17.112%** | −2,893.6 .. 73.2 m |
| `ocean_current_u` | GLORYS12V1 (uo, daily → hourly ffill) | (8760, 17, 33) | 0 | 0.000% | −0.654 .. 0.486 m/s |
| `ocean_current_v` | GLORYS12V1 (vo, daily → hourly ffill) | (8760, 17, 33) | 0 | 0.000% | −1.074 .. 1.044 m/s |

**Bathymetry NaN (17.1%)** = 96 land cells × 8,760 timesteps = 840,960 — **expected** (land points). NaN mask **identical to 2020 baseline** (diff 0).

---

## 7. GLORYS VALIDATION

- `ocean_current_u`: 4,914,360 / 4,914,360 non-NaN (100%), **99.4% > 1e-6 m/s**, range −0.654 .. 0.486 m/s
- `ocean_current_v`: 4,914,360 / 4,914,360 non-NaN (100%), **99.5% > 1e-6 m/s**, range −1.074 .. 1.044 m/s
- Cross-correlation u/v = **0.222** (non-degenerate, physically plausible)
- Resampled from GLORYS 1/12° daily (49 × 97) → 0.25° hourly (17 × 33) via nearest-neighbor + ffill

**GLORYS present and non-empty: ✅**

---

## 8. BATHYMETRY VALIDATION

- Static over time: ✅ `b[0] == b[5000]` (allclose, equal_nan)
- NaN mask identical to 2020 baseline: ✅
- Elevation values identical to 2020 baseline: ✅ (atol 0.01 m)

**Bathymetry static and consistent with baseline: ✅**

---

## 9. PROCESSING STEPS (unchanged pipeline)

1. **STEP 1** — Define common grid from ERA5 (0.25° 17×33, EPSG:4326)
2. **STEP 2** — Standardise ERA5 (rename u10→wind_u_10m, etc.); 5 vars, 8760 h
3. **STEP 3** — Reproject sea ice (polar-stereo → 0.25° nearest-neighbor, daily→hourly ffill); 365→8760
4. **STEP 4** — Coarsen bathymetry (15 arc-sec → 0.25°, lat_factor=60, lon_factor=60); broadcast across 8760 steps
5. **STEP 5** — Resample GLORYS (1/12° daily → 0.25° hourly nearest-neighbor + ffill)
6. **STEP 6** — Merge 9 variables into single Dataset; write NC + metadata JSON

**No new methodology introduced** — the existing parameterised pipeline processed 2017 identically to 2019/2021/2024/2025.

---

## 10. VALIDATION RESULTS (15 CHECKS)

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | File exists and readable | ✅ PASS | xarray opens without error |
| 2 | 2017 temporal coverage | ✅ PASS | 2017-01-01 → 2017-12-31 |
| 3 | 8,760 hourly timesteps | ✅ PASS | 365 × 24 = 8,760 |
| 4 | No missing timestamps | ✅ PASS | Full 2017 hourly grid present |
| 5 | No duplicate timestamps | ✅ PASS | 0 duplicates, uniform Δ=1h |
| 6 | Spatial dims 17 × 33 | ✅ PASS | Uniform 0.25°, correct bbox |
| 7 | Coords match 2020/2021 | ✅ PASS | lat/lon identical to both |
| 8 | All 9 variables present | ✅ PASS | Exact set matches spec |
| 9 | Variable dimensions correct | ✅ PASS | All share (8760, 17, 33) |
| 10 | Missing values per variable | ✅ PASS | Bathymetry 17.1% = land (expected) |
| 11 | Physical ranges valid | ✅ PASS | All 9 in expected bounds |
| 12 | GLORYS present & non-empty | ✅ PASS | 100% non-NaN, 99.4/99.5% non-zero, corr=0.222 |
| 13 | Bathymetry static & baseline-consistent | ✅ PASS | Static over time; mask+vals = 2020 baseline |
| 14 | No coordinate/schema changes | ✅ PASS | var set identical to 2020 & 2021 |
| 15 | Phase 1/2/2020/2021 untouched | ✅ PASS | mtimes before 2017 build |

**ALL 15 CHECKS PASS**

---

## 11. FILES CREATED

| File | Size | Timestamp |
|---|---|---|
| `data/processed/integration/east_prydz_bay_2017_feature_stack.nc` | 200.48 MB | 2026-09-05 |
| `data/processed/integration/east_prydz_bay_2017_feature_stack_metadata.json` | ~7 KB | 2026-09-05 |

---

## 12. FILES MODIFIED

**None.** The pipeline only **writes** the two new files above. No existing file was overwritten or altered.

---

## 13. FILES CONFIRMED UNTOUCHED

| File | Last Modified | Status |
|---|---|---|
| `data/processed/icebergs/east_prydz_bay_icebergs.csv` | 2026-09-04 02:21:09 | ✅ |
| `data/processed/bathymetry/east_prydz_bay_bathymetry_15arcsec.nc` | 2026-09-04 02:16:11 | ✅ |
| `data/processed/integration/east_prydz_bay_2020_feature_stack.nc` | 2026-09-04 08:52:49 | ✅ **Baseline — untouched** |
| `data/processed/integration/east_prydz_bay_2021_feature_stack.nc` | 2026-09-05 02:04:39 | ✅ |
| `data/processed/integration/east_prydz_bay_2024_feature_stack.nc` | 2026-09-05 00:03:50 | ✅ |
| `data/processed/integration/east_prydz_bay_2025_feature_stack.nc` | 2026-09-05 01:09:07 | ✅ |

**Zero Phase 1, Phase 2, 2020, or 2021 data modified.**

---

## 14. LIMITATIONS / WARNINGS

- Bathymetry NaN on 96 land cells (17.1% of grid) is **expected and correct** — identical to 2020 baseline; not interpolated.
- `sea_ice_concentration` shows 0% NaN for 2017 (full bbox ice coverage) — consistent with the 2021 stack behavior; the NSIDC mask falls outside the bbox for this year. No synthetic data introduced.
- Feature definitions, coordinate system, spatial grid, and variable schema **exactly preserved** from the 2020 prototype pipeline.
- GLORYS 2017 has full 365-day coverage — no synthetic data introduced.

---

## 15. FINAL STATUS

| Metric | Value |
|---|---|
| **STATUS** | **PASS** |
| **2017 FEATURE STACK** | **COMPLETE** |
| **HOURLY STEPS** | **8,760** |
| **GRID** | **17 × 33, 0.25°, EPSG:4326 (East Prydz Bay)** |
| **VARIABLES** | **9** |
| **VALIDATION CHECKS** | **15/15 PASS** |
| **PHASE 1/2/2020/2021 INTACT** | **YES** |
| **NEXT STEP** | **Await approval** |

---

> **STOPPING HERE.**  
> Do NOT start ERA5 2018 or any other year.  
> Do NOT expand to another year.  
> Do NOT rebuild the ML dataset.  
> Do NOT retrain any model.
