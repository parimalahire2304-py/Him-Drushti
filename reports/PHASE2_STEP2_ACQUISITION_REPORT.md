# Phase 2 · Step 2 — Environmental Data Acquisition Report

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory,
and Navigation Decision Support System

**Date:** 2026-09-04
**Region:** East Prydz Bay (S −70.0, N −66.0, W 72.0, E 80.0, EPSG:4326)
**Analysis window:** 2020-01-01 → 2020-12-31 (107 regional iceberg records, D23 &
D27 active, full seasonal cycle)
**Source of truth:** `config/region.yaml` · `config/datasets.yaml` ·
`docs/ACQUISITION_PLAN.md`

---

## 1. Summary

| Dataset | Status | Raw → Processed | Validation |
|---|---|---|---|
| NSIDC-0051 sea-ice (daily) | ✅ **ACQUIRED** | 366 granules (25 MB) → 1.1 MB NetCDF | PASS — seasonal cycle correct |
| ERA5 weather (hourly) | ⛔ **BLOCKED** | none | CDS licence not accepted in profile |
| GLORYS ocean currents | ⛔ **BLOCKED** | none | CMEMS identity server DNS-unreachable |
| Sentinel-1 EW_GRDM SAR | ✅ **ACQUIRED** | 3 scenes (1.28 GB) | PASS — 3/3 SAFE zips CRC-valid |

**Phase 1 datasets (icebergs, bathymetry) untouched** — no Phase 1 files were
modified, deleted, or overwritten. `data/raw/icebergs/`,
`data/processed/icebergs/`, `data/processed/bathymetry/` unchanged.

---

## 2. Acquired: NSIDC-0051 sea-ice concentration (2020)

**Provider:** NASA NSIDC DAAC (Earthdata Cloud) · **Access:** Earthdata Login
bearer token + NASA CMR discovery.

### Acquisition
- 366 daily granules (2020-01-01 → 2020-12-31), ~59 KB each, 25 MB total.
- Subset in native polar-stereographic grid (EPSG:3412) to bbox, then
  geolocated (lat/lon) via pyproj.

### Processing fix applied this step
The raw NetCDF ships **already unpacked** (`F17_ICECON` float64, 0.0–1.0,
`scale_factor` applied). The first processing run double-unpacked (`/250.0`),
yielding a bogus 0.000–0.004 concentration with **no seasonal cycle**. Fixed in
`scripts/data/download_sea_ice.py`: flags (>1.0) are now masked to NaN instead.
Also fixed the "flagged cells" count (used `np.isnan`, not `== np.nan`).

### Validation (post-fix) — PASS
- Shape: `{time: 366, y: 17, x: 21}` = 130,662 grid-cell-days.
- Valid concentration cells: 84,180 · Flagged (pole_hole/coast/land): 46,482
  (35.6% — expected: the bbox edge overlaps the Amery sector / coastal mask).
- Concentration range: **0.000 … 1.000** (fraction).
- Seasonal cycle (mean fraction): Jan 0.30 · Feb 0.10 (min) · Apr 0.81 ·
  Jul–Sep 0.83–0.85 (max) · Dec 0.55. Physically correct for East Prydz Bay.

### Files
- `data/raw/sea_ice/NSIDC0051_20200101_v2.0.nc` … `…_20201231_v2.0.nc` (366)
- `data/processed/sea_ice/east_prydz_bay_sea_ice_concentration_2020-01-01_2020-12-31.nc`
- `data/processed/sea_ice/east_prydz_bay_sea_ice_metadata.json`
- Variable: `sea_ice_concentration` (fraction 0–1, flags masked).

---

## 3. Blocked: ERA5 atmospheric forcing

**Provider:** ECMWF Climate Data Store (CDS) · **Access:** `cdsapi` with
`CDS_API_URL` / `CDS_API_KEY`.

### Status
- Credential **auth test PASSES** (HTTP 202 on the API base) — the key
  `<uid>:<token>` is valid.
- The actual dataset request (`reanalysis-era5-single-levels`) returns
  **HTTP 403 “required licences not accepted”**. This is a profile-level
  licence gate, not a code or credential issue.

### Required manual action
1. Sign in at https://cds.climate.copernicus.eu
2. Open
   https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=download#manage-licences
3. Accept the ERA5 single-levels licence.
4. Re-run: `python scripts/data/download_weather.py --start 2020-01-01 --end 2020-12-31`

The downloader is written and smoke-ready (5 variables, hourly, monthly-loop,
bbox subset `area=[-66, 72, -70, 80]`).

**No silent substitution was made** — ERA5 remains genuinely required for the
wind/melt forcing in the drift model.

---

## 4. Blocked: GLORYS ocean currents

**Provider:** Copernicus Marine Service (CMEMS) · **Access:** Marine Data Store
OAuth2.

### Status
- Credentials present and correctly formatted.
- CMEMS identity server `identity.marine.copernicus.eu` is
  **DNS-unreachable from this build environment** (verified again this step,
  exit 3):
  ```
  NameResolutionError: Failed to resolve 'identity.marine.copernicus.eu'
  ([Errno 11001] getaddrinfo failed)
  ```
- This is an **environment/network limitation, not a credential problem**.
- **No download attempted and no auth bypass** was used (per project rule).

### Required action
Re-run `python scripts/data/access_tests/test_glorys.py` (then
`scripts/data/download_ocean.py`) from a network that can resolve
`identity.marine.copernicus.eu`.

---

## 5. Acquired: Sentinel-1 EW_GRDM SAR (representative sample)

**Provider:** ESA / Copernicus Data Space Ecosystem · **Access:** OData catalogue
+ OAuth2, dedicated download host.

### Acquisition
- Catalog query (bbox `POLYGON((72 -70,80 -70,80 -66,72 -66,72 -70))`,
  `Collection/Name eq 'SENTINEL-1'`, `contains(Name,'EW_GRDM')`) returns the
  15,030 EW-mode scenes; only the **3 most recent** were downloaded.
- 3 scenes, acquired 2026-09-03, total **1.28 GB** (sample only — not the full
  archive, per Phase 2 Step 2 rule).

| Scene (S1D EW_GRDM 1SDH) | Size | Dual-pol |
|---|---|---|
| `…_0082BA_B616` (14:22) | 464.1 MB | HH + HV |
| `…_0082C6_9901_COG` (16:00) | 349.6 MB | HH + HV (COG) |
| `…_0082C6_C2AD` (16:00) | 468.5 MB | HH + HV |

### Validation — PASS
- 3/3 SAFE zips pass CRC (`zipfile.testzip()` → `None`).
- Each contains 26 entries incl. 2 measurement TIFFs (HH, HV), calibration and
  noise annotations, product report.
- Metadata recorded → `data/processed/sar/east_prydz_bay_sentinel1_metadata.json`.

### Access issues fixed this step
1. **400 on catalog query** — the OData `$select` field `ProcessingLevel`
   (and `ProductType`, `ProcessingMode`) does not exist on the `Products`
   entity and the API rejects the whole query. Valid fields: `Id, Name,
   ContentDate, ContentLength, Online, S3Path`. Dropped the invalid ones.
2. **401 on download without redirect** — `requests` strips the `Authorization`
   header on the cross-host redirect (`catalogue.` → `download.`). Fixed by
   requesting the **download host directly**
   (`https://download.dataspace.copernicus.eu/odata/v1/Products({id})/$value`).
3. The download host rejects **quoted UUIDs** (422) — use `Products({id})` with
   no quotes.
4. `$select`/`$filter`/`$top` must use **integer coordinates** (72, not 72.0) in
   the polygon (established earlier; preserved).

> **Temporal note:** the sample is dated 2026-09-03 (most-recent), i.e. outside
> the 2020 analysis window. This is **deliberate and documented**: SAR is not a
> forcing input for the Prototype-1 drift demo (it feeds the later YOLO iceberg
> detection phase); the acquisition plan called for a small representative
> sample, not 2020-matching scenes. A 2020 temporal filter can be added later.

---

## 6. Environment variables used (never exposed)

| Variable | Source |
|---|---|
| `NSIDC_USERNAME` / `NSIDC_PASSWORD` | `.env` (Earthdata Login) |
| `CDS_API_URL` / `CDS_API_KEY` | `.env` (ECMWF CDS) |
| `CMEMS_USERNAME` / `CMEMS_PASSWORD` | `.env` (present, unused — DNS block) |
| `COPERNICUS_USERNAME` / `COPERNICUS_PASSWORD` | `.env` (Data Space) |

`.env` remains untracked (`git status` shows no `.env` in working tree).

---

## 7. Disk usage (Phase 2 Step 2 additions)

| Path | Size |
|---|---|
| `data/raw/sea_ice/` (366 daily) | 25 MB |
| `data/processed/sea_ice/` | 1.1 MB |
| `data/raw/sar/` (3 SAFE zips + catalog JSON) | 1.2 GB |
| `data/processed/sar/` | 4 KB |
| `data/raw/weather/`, `data/processed/weather/` | empty (blocked) |
| `data/raw/ocean/`, `data/processed/ocean/` | empty (blocked) |

Total `data/` ≈ 1.3 GB of 93 GB available. No storage risk.

---

## 8. Problems encountered and resolutions

| # | Problem | Fix |
|---|---|---|
| 1 | NSIDC double-unpacking → ice ≈ 0 everywhere | Used raw values as-is; mask flags (>1.0) to NaN; re-validated seasonal cycle |
| 2 | `== np.nan` never true → bogus flag count | `np.isnan(...)` |
| 3 | OData 400: `ProcessingLevel` invalid in `$select` | Dropped; used valid fields only |
| 4 | OData 401 on `$value` redirect | Direct download host + Bearer |
| 5 | Download host 422 on quoted UUID | `Products({id})` no quotes |
| 6 | `.SAFE.SAFE.zip` double suffix | Script now names `{name}.zip` when name ends in `.SAFE` |
| 7 | ERA5 403 licence not accepted | Manual CDS licence acceptance (documented) |

---

## 9. Next steps (Phase 2 Step 3 + unblocking actions)

1. **ERA5 (user action):** accept licence on CDS → re-run
   `download_weather.py` → validate (5 variables, hourly, 366 days, bbox).
2. **GLORYS (user action):** run from a network resolving CMEMS → test →
   download → validate. Document as environment-limited until then.
3. **Phase 2 Step 3 (data preprocessing / feature assembly):** once ERA5 (and
   optionally GLORYS) are present, combine NSIDC + weather + GEBCO + NIC
   iceberg tracks into a harmonised 2020 forcing stack. No ML until Phase 3.

---

*Report by the data-acquisition pipeline (scripts/data/*) that executed the
approved Phase 2 Step 2 plan. All downloaders are runnable and idempotent.*