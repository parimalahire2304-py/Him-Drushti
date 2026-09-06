# PHASE 3A — 2021 FEATURE STACK BUILD & VERIFICATION REPORT

**Date:** 2026-09-05  
**Pipeline:** `scripts/data/build_feature_stack_year.py --year 2021`  
**Status:** ✅ BUILT & VERIFIED — **PASS**

---

## 1. OUTPUT FILE

| Property | Value |
|---|---|
| **Path** | `data/processed/integration/east_prydz_bay_2021_feature_stack.nc` |
| **Metadata** | `data/processed/integration/east_prydz_bay_2021_feature_stack_metadata.json` |
| **Size** | **200.72 MB** (200,719,898 bytes) |
| **Created** | 2026-09-05 02:04:39 |

---

## 2. DIMENSIONS

| Dimension | Value |
|---|---|
| `time` | **8,760** (hourly) |
| `lat` | **17** |
| `lon` | **33** |
| **Total grid cells** | 561 (17 × 33) |
| **Total data points / variable** | 4,914,360 |

---

## 3. VARIABLES (9 approved features)

| Variable | Source | Dims | NaN count | NaN % | Physical Range |
|---|---|---|---|---|---|
| `sea_ice_concentration` | NSIDC-0051 (daily → hourly ffill) | (8760, 17, 33) | 0 | 0.000% | 0.0 .. 1.0 |
| `wind_u_10m` | ERA5 (u10) | (8760, 17, 33) | 0 | 0.000% | −29.05 .. 19.07 m/s |
| `wind_v_10m` | ERA5 (v10) | (8760, 17, 33) | 0 | 0.000% | −23.25 .. 21.93 m/s |
| `temperature_2m` | ERA5 (t2m) | (8760, 17, 33) | 0 | 0.000% | 228.1 .. 278.6 K |
| `mean_sea_level_pressure` | ERA5 (msl) | (8760, 17, 33) | 0 | 0.000% | 93,433 .. 101,600 Pa |
| `total_precipitation` | ERA5 (tp) | (8760, 17, 33) | 0 | 0.000% | 0 .. 0.00403 m |
| `bathymetry_elevation` | GEBCO 2024 (coarsened + broadcast) | (8760, 17, 33) | **840,960** | **17.112%** | −2,893.6 .. 73.2 m |
| `ocean_current_u` | GLORYS12V1 (uo, daily → hourly ffill) | (8760, 17, 33) | 0 | 0.000% | −0.590 .. 0.493 m/s |
| `ocean_current_v` | GLORYS12V1 (vo, daily → hourly ffill) | (8760, 17, 33) | 0 | 0.000% | −0.714 .. 0.820 m/s |

**Bathymetry NaN (17.1%)** = 96 land cells × 8,760 timesteps = 840,960 — **expected** (land points). Mask **identical to 2020 baseline**.

---

## 4. TEMPORAL COVERAGE

| Property | Value |
|---|---|
| **Start** | 2021-01-01T00:00 |
| **End** | 2021-12-31T23:00 |
| **Steps** | 8,760 (2021 non-leap year: 365 × 24) |
| **Frequency** | Hourly, **uniform** (Δ = 1 hour for all 8,759 intervals) |
| **Gaps/Duplicates** | None |

---

## 5. SPATIAL GRID

| Property | Value |
|---|---|
| **CRS** | EPSG:4326 (WGS 84) |
| **Lat bounds** | −70.00 .. −66.00 (17 pts, 0.25° step) |
| **Lon bounds** | 72.00 .. 80.00 (33 pts, 0.25° step) |
| **Uniform spacing** | ✅ lat & lon |
| **Identical to 2020 baseline** | ✅ lat, lon, and variable set |

---

## 6. SOURCE INPUTS (all verified before build)

| Input | Path | Status |
|---|---|---|
| ERA5 2021 combined | `data/processed/weather/east_prydz_bay_era5_2021-01-01_2021-12-31.nc` | ✅ 43.94 MB, 8760 h, 5 vars, 0% NaN |
| NSIDC sea-ice 2021 | `data/processed/sea_ice/east_prydz_bay_sea_ice_concentration_2021-01-01_2021-12-31.nc` | ✅ 365 d, reprojected + ffill |
| GLORYS 2021 | `data/raw/ocean/glorys/glorys12v1_east_prydz_bay_2021.nc` | ✅ 6.96 MB, 365 d, uo/vo |
| Bathymetry | `data/processed/bathymetry/east_prydz_bay_bathymetry_15arcsec.nc` | ✅ 15 arc-sec, static |
| Icebergs (NIC) | `data/processed/icebergs/east_prydz_bay_icebergs.csv` | ✅ 796 rows, 2016–2026 |

---

## 7. VALIDATION RESULTS (12 CHECKS)

| # | Check | Result | Notes |
|---|---|---|---|
| 1 | File exists & readable | ✅ PASS | xarray opens without error |
| 2 | 2021 temporal coverage | ✅ PASS | 2021-01-01 → 2021-12-31 |
| 3 | 8,760 hourly timesteps | ✅ PASS | 365 × 24 = 8,760 |
| 4 | 17 × 33 spatial grid | ✅ PASS | Uniform 0.25°, correct bbox |
| 5 | 9 approved variables present | ✅ PASS | Exact set matches spec |
| 6 | No coordinate changes vs 2020 | ✅ PASS | lat/lon/vars identical |
| 7 | Missing values per variable | ✅ PASS | Bathymetry 17.1% = land (expected) |
| 8 | Physical ranges valid | ✅ PASS | All 9 in expected bounds |
| 9 | Temporal continuity | ✅ PASS | Uniform hourly, no gaps/duplicates |
| 10 | Variable alignment | ✅ PASS | All share (8760, 17, 33) |
| 11 | GLORYS ocean currents incorporated | ✅ PASS | 99.3–99.4% non-zero, corr=0.188 |
| 12 | Bathymetry static over time | ✅ PASS | Identical slice at t=0 and t=5000 |

---

## 8. GLORYS VERIFICATION DETAIL

- `ocean_current_u`: 4,914,360 / 4,914,360 non-NaN (100%), **99.3% > 1e-6 m/s**, range −0.590 .. 0.493 m/s
- `ocean_current_v`: 4,914,360 / 4,914,360 non-NaN (100%), **99.4% > 1e-6 m/s**, range −0.714 .. 0.820 m/s
- Cross-correlation u/v = **0.188** (non-degenerate, physically plausible)
- Resampled from GLORYS 1/12° daily (49 × 97) → 0.25° hourly (17 × 33) via nearest-neighbor + ffill

---

## 9. FILES CREATED

| File | Size | Timestamp |
|---|---|---|
| `data/processed/integration/east_prydz_bay_2021_feature_stack.nc` | 200.72 MB | 2026-09-05 02:04:39 |
| `data/processed/integration/east_prydz_bay_2021_feature_stack_metadata.json` | 6.7 KB | 2026-09-05 02:04:39 |

---

## 10. FILES MODIFIED

**None.** The pipeline only **writes** the two new files above. No existing file was overwritten or altered.

---

## 11. FILES CONFIRMED UNTOUCHED (Phase 1 / Phase 2 / earlier 3A)

| File | Last Modified | Status |
|---|---|---|
| `data/processed/icebergs/east_prydz_bay_icebergs.csv` | 2026-09-04 02:21:09 | ✅ Before 2021 build |
| `data/processed/bathymetry/east_prydz_bay_bathymetry_15arcsec.nc` | 2026-09-04 02:16:11 | ✅ Before 2021 build |
| `data/processed/sea_ice/east_prydz_bay_sea_ice_concentration_2021-01-01_2021-12-31.nc` | 2026-09-05 00:22:44 | ✅ Input, not modified |
| `data/raw/ocean/glorys/glorys12v1_east_prydz_bay_2021.nc` | 2026-09-04 22:37:20 | ✅ Input, not modified |
| `data/processed/weather/east_prydz_bay_era5_2021-01-01_2021-12-31.nc` | 2026-09-05 01:58:14 | ✅ Input, not modified |
| `data/processed/integration/east_prydz_bay_2020_feature_stack.nc` | 2026-09-04 08:52:49 | ✅ **Baseline — untouched** |
| `data/processed/integration/east_prydz_bay_2024_feature_stack.nc` | 2026-09-05 00:03:50 | ✅ Earlier 3A stack |
| `data/processed/integration/east_prydz_bay_2025_feature_stack.nc` | 2026-09-05 01:09:07 | ✅ Earlier 3A stack |

All source files pre-date the 2021 feature stack creation (02:04:39). **Zero Phase 1 or Phase 2 data modified.**

---

## 12. LIMITATIONS / NOTES

- Bathymetry NaN on 96 land cells (17.1% of grid) is **expected and correct** — identical to 2020 baseline; not interpolated.
- GLORYS 2021 has full 365-day coverage (verified earlier). No synthetic data introduced.
- Feature definitions, coordinate system, spatial grid, and variable schema **exactly preserved** from the 2020 prototype pipeline.

---

## 13. EXPANSION STATUS

**2021 FEATURE STACK: ✅ PASS**

Ready for downstream ML dataset construction (`prepare_ml_dataset.py`) alongside 2019, 2020, 2024, 2025 stacks.

---

## 14. NEXT STEP (manual approval required)

> **Do NOT start ERA5 2017 or any other year automatically.**  
> Await explicit instruction to:
> 1. Build 2021 ML dataset via `prepare_ml_dataset.py` (expanded window), OR
> 2. Launch ERA5 2017 download, OR
> 3. Proceed with any other Phase 3A task.