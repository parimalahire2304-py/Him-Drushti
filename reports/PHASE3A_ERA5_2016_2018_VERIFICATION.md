# PHASE 3A — ERA5 2016 & 2018 DOWNLOAD & VERIFICATION REPORT

**Date:** 2026-09-05  
**Pipeline:** `scripts/data/download_weather.py` (sequential CDS monthly jobs, resume-capable)  
**Scope:** Acquire the only missing ERA5 data blocking the 2016 & 2018 feature stacks. **No other years downloaded.**
**Result:** ✅ **BOTH YEARS COMPLETE & VERIFIED — PASS**

---

## 1. PRE-FLIGHT (before each year)

| Year | Monthly raw files | Combined file | Running process | Decision |
|---|---|---|---|---|
| 2016 | 0/12 | absent | none | genuinely missing → download |
| 2018 | 0/12 (rechecked after 2016 verify) | absent | none | genuinely missing → download |

Per the "verify before download" rule, both years were confirmed **absent before starting** — no redownload of complete files occurred.

---

## 2. ERA5 2016 — MONTHLY DOWNLOAD STATUS

Download window: **12:54 → 14:42 IST** (~1 h 48 m, including a 120-s DNS retry).

| Month | Size (MB) | Hourly steps | Month | Size (MB) | Hourly steps |
|---|---|---|---|---|---|
| 2016-01 | 3.57 | 744 | 2016-07 | 3.77 | 744 |
| 2016-02 | 3.44 | **696** (leap) | 2016-08 | 3.59 | 744 |
| 2016-03 | 3.70 | 744 | 2016-09 | 3.46 | 720 |
| 2016-04 | 3.58 | 720 | 2016-10 | 3.63 | 744 |
| 2016-05 | 3.66 | 744 | 2016-11 | 3.36 | 720 |
| 2016-06 | 3.58 | 720 | 2016-12 | 3.43 | 744 |

- **12/12 present**, each readable & valid, all 5 required vars present.
- **Leap-year-aware step counts correct** (2016 = 366 d → Feb 696 h, total 8,784 h).

### Errors / retries (2016)
- **1 transient `NameResolutionError`** (Failed to resolve `cds.climate.copernicus.eu`) on **2016-12** at ~14:35 → auto-retried after 120 s → **successful**. No data loss.

---

## 3. ERA5 2016 — COMBINED-FILE VERIFICATION

| Property | Value |
|---|---|
| **File** | `data/processed/weather/east_prydz_bay_era5_2016-01-01_2016-12-31.nc` |
| **Size** | **43.46 MB** |
| **Dims** | valid_time **8,784** × latitude 17 × longitude 33 |
| **Coverage** | 2016-01-01T00:00 → 2016-12-31T23:00 |
| **Frequency** | Hourly, uniform (all Δ = 1 h) |
| **Duplicates** | 0 |
| **Missing timestamps** | 0 |
| **Grid** | 17 × 33, uniform 0.25°, lat −70.00…−66.00, lon 72.00…80.00, EPSG:4326 |

| Variable | NaN % | Physical range | Expected OK |
|---|---|---|---|
| `u10` (m s⁻¹) | 0.0000 | −30.36 … 19.61 | ✅ |
| `v10` (m s⁻¹) | 0.0000 | −18.35 … 24.68 | ✅ |
| `t2m` (K) | 0.0000 | 218.17 … 278.68 | ✅ |
| `msl` (Pa) | 0.0000 | 91,487 … 102,760 | ✅ |
| `tp` (m) | 0.0000 | 0 … 0.002336 ( ≥ 0) | ✅ |

**VALIDATION: 13/13 PASS**

---

## 4. ERA5 2018 — MONTHLY DOWNLOAD STATUS

Download window: **14:50 → 16:07 IST** (~1 h 17 m). Error-free.

| Month | Size (MB) | Hourly steps | Month | Size (MB) | Hourly steps |
|---|---|---|---|---|---|
| 2018-01 | 3.49 | 744 | 2018-07 | 3.70 | 744 |
| 2018-02 | 3.30 | 672 | 2018-08 | 3.70 | 744 |
| 2018-03 | 3.77 | 744 | 2018-09 | 3.52 | 720 |
| 2018-04 | 3.56 | 720 | 2018-10 | 3.63 | 744 |
| 2018-05 | 3.74 | 744 | 2018-11 | 3.48 | 720 |
| 2018-06 | 3.56 | 720 | 2018-12 | 3.39 | 744 |

- **12/12 present**, each readable & valid, all 5 required vars present.
- **Step counts correct** (2018 non-leap = 365 d → Feb 672 h, total 8,760 h).

### Errors / retries (2018)
- **None.** Clean log — no DNS, 502, auth, or timeout events.
- **Note:** a transient monitor reading showed 2018-09 at 1.05 MB mid-write; the **final on-disk size is 3.52 MB** and opens with the full 720 timesteps + 0% NaN — no truncation or corruption (the transient read was a filesystem/OneDrive sync artifact during the write).

---

## 5. ERA5 2018 — COMBINED-FILE VERIFICATION

| Property | Value |
|---|---|
| **File** | `data/processed/weather/east_prydz_bay_era5_2018-01-01_2018-12-31.nc` |
| **Size** | **43.54 MB** |
| **Dims** | valid_time **8,760** × latitude 17 × longitude 33 |
| **Coverage** | 2018-01-01T00:00 → 2018-12-31T23:00 |
| **Frequency** | Hourly, uniform (all Δ = 1 h) |
| **Duplicates** | 0 |
| **Missing timestamps** | 0 |
| **Grid** | 17 × 33, uniform 0.25°, lat −70.00…−66.00, lon 72.00…80.00, EPSG:4326 |

| Variable | NaN % | Physical range | Expected OK |
|---|---|---|---|
| `u10` (m s⁻¹) | 0.0000 | −27.90 … 17.48 | ✅ |
| `v10` (m s⁻¹) | 0.0000 | −15.85 … 24.42 | ✅ |
| `t2m` (K) | 0.0000 | 227.12 … 277.84 | ✅ |
| `msl` (Pa) | 0.0000 | 94,835 … 103,050 | ✅ |
| `tp` (m) | 0.0000 | 0 … 0.002365 ( ≥ 0) | ✅ |

**VALIDATION: 13/13 PASS**

---

## 6. 13-CHECK VERIFICATION SUMMARY (both years)

| # | Check | 2016 | 2018 |
|---|---|---|---|
| 1 | All monthly files present | ✅ 12/12 | ✅ 12/12 |
| 2 | Each file readable/valid | ✅ (all ZIP→merge OK) | ✅ (all ZIP→merge OK) |
| 3 | Five required variables present | ✅ | ✅ |
| 4 | Correct temporal coverage | ✅ 01-01→12-31 | ✅ 01-01→12-31 |
| 5 | Correct monthly timestep counts | ✅ leap-aware | ✅ |
| 6 | No missing timestamps | ✅ 0 | ✅ 0 |
| 7 | No duplicate timestamps | ✅ 0 | ✅ 0 |
| 8 | Correct spatial coverage | ✅ 17×33 0.25° | ✅ 17×33 0.25° |
| 9 | Correct lat/lon grid | ✅ | ✅ |
| 10 | Missing-value statistics | ✅ 0% all vars | ✅ 0% all vars |
| 11 | Physical ranges valid | ✅ | ✅ |
| 12 | Combined annual file valid | ✅ 43.46 MB / 8,784 h | ✅ 43.54 MB / 8,760 h |
| 13 | No corruption/truncation | ✅ | ✅ (Sep transient resolved) |

**13/13 PASS for both years.**

---

## 7. FILES CREATED

| File | Size | Purpose |
|---|---|---|
| `data/raw/weather/ERA5_2016-01…12_east_prydz_bay.nc` | 12 × ~3.4–3.8 MB | 2016 monthly raw |
| `data/processed/weather/east_prydz_bay_era5_2016-01-01_2016-12-31.nc` | **43.46 MB** | 2016 combined |
| `data/raw/weather/ERA5_2018-01…12_east_prydz_bay.nc` | 12 × ~3.3–3.8 MB | 2018 monthly raw |
| `data/processed/weather/east_prydz_bay_era5_2018-01-01_2018-12-31.nc` | **43.54 MB** | 2018 combined |
| `data/processed/weather/east_prydz_bay_era5_metadata.json` | updated | metadata |
| `data/raw/weather/era5_2016_download.log`, `era5_2018_download.log` | — | download logs |

---

## 8. FILES MODIFIED

**None.** Pipeline only writes new files; no existing dataset was overwritten.

---

## 9. FILES CONFIRMED UNTOUCHED

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
| 2016 / 2018 feature stacks | — | **NOT YET BUILT** (per instruction) |

---

## 10. LIMITATIONS / NOTES

- 2016 is a **leap year** (8,784 h); 2018 is **non-leap** (8,760 h) — both handled correctly.
- Monthly files are **ZIP archives** containing NetCDFs; verified via the pipeline's `_read_month`/`open_month` ZIP logic.
- One transient DNS failure on 2016-12 recovered automatically; no data loss.
- 2022, 2023, and 2026 were **NOT** downloaded (per step scope).

---

## 11. FINAL STATUS

| Metric | Value |
|---|---|
| **ERA5 2016** | **COMPLETE** |
| **ERA5 2018** | **COMPLETE** |
| **2016 MONTHS** | **12/12** |
| **2018 MONTHS** | **12/12** |
| **2016 VALIDATION** | **PASS (13/13)** |
| **2018 VALIDATION** | **PASS (13/13)** |
| **FILES CREATED** | 24 monthly raw + 2 combined + 2 logs + metadata |
| **FILES MODIFIED** | NONE |
| **PHASE 1/2 INTACT** | **YES** |
| **EXISTING FEATURE STACKS INTACT** | **YES** |
| **NEXT STEP** | Build & verify 2016 & 2018 feature stacks after explicit approval |

---

> **STOPPING HERE.**  
> Do **NOT** build the 2016/2018 feature stacks yet.  
> Do **NOT** download 2022/2023/2026.  
> Do **NOT** combine iceberg observations, create a new ML dataset, or train RF/XGBoost/LSTM.