# Phase 2 · Step 1 — Environmental Data Acquisition Plan

Purpose: obtain the four remaining datasets (NSIDC sea-ice, ERA5 weather,
GLORYS ocean, Sentinel-1 SAR) needed as **forcing inputs for iceberg-drift
prediction** in East Prydz Bay. This step covers *access*, *variables*, and
*subsets* only — **no ML modeling**.

Source of truth for the study region: `config/region.yaml`
(East Prydz Bay: lat −70…−66, lon 72…80, EPSG:4326).

---

## Why these variables (iceberg-drift physics)

Iceberg drift is a force balance on the iceberg: **water drag** (submerged
hull, from ocean currents) dominates, then **wind drag** (above-water sail),
plus **Coriolis**, **sea-ice drag/blocking**, and **thermodynamic melt**.
The environmental forcing needed for a drift model is therefore:

| Forcing | Dataset | Variables |
|---|---|---|
| Ocean currents (primary) | GLORYS | `uo`, `vo` (surface), `thetao` (SST) |
| Wind (secondary) | ERA5 | `10u`, `10v`, `2t` (melt), `msl`, `tp` |
| Sea-ice drag/blocking | NSIDC | `siconc` (concentration %) |
| Bathymetry (grounding) | GEBCO ✅ (have) | `elevation` |
| Iceberg state (target) | NIC ✅ (have) | position, size |

---

## 1. NSIDC sea-ice concentration

- **Credential env vars:** `NSIDC_USERNAME`, `NSIDC_PASSWORD`
  (NASA Earthdata Login email + password).
- **Products:** NSIDC-0051 (NASA Team) or NSIDC-0079 (Bootstrap), daily,
  ~25 km polar stereographic; NSIDC-0081 for near-real-time.
- **Variable:** sea-ice concentration `siconc` (%), plus fill-value handling.
- **Spatial subset:** East Prydz Bay bbox; subset in native polar
  stereographic grid, then reproject to EPSG:4326.
- **Temporal subset:** daily; full iceberg-observation window
  **2016-01-01 → 2026-08-27** (moderate volume at 25 km).
- **Manual action:** register at urs.earthdata.nasa.gov → approve "NSIDC
  DAAC" application → set the two env vars → run the test, then downloader.

## 2. ERA5 weather

- **Credential env vars:** `CDS_API_URL`, `CDS_API_KEY`
  (key format `<uid>:<token>`).
- **Dataset:** `reanalysis-era5-single-levels` (~0.25°, hourly).
- **Variables (minimal set):**
  - `10m_u_component_of_wind`, `10m_v_component_of_wind` — wind forcing
  - `2m_temperature` — melt/thermodynamics
  - `mean_sea_level_pressure` — synoptic context
  - `total_precipitation` — optional
- **Spatial subset:** bbox → CDS `area` = `[north, west, south, east]` =
  `[-66, 72, -70, 80]`.
- **Temporal subset:** hourly is very large for 2016–2026. **Recommended:
  start with a focused window (e.g., 2016–2018 or a 2-year test window),
  or sample at 6-hourly** to control volume. Expand later as needed.
- **Manual action:** register at cds.climate.copernicus.eu → generate API
  key → set the two env vars → run test, then downloader.

## 3. GLORYS ocean currents

- **Credential env vars:** `CMEMS_USERNAME`, `CMEMS_PASSWORD`.
- **Dataset:** GLORYS12V1 (1/12°, daily).
- **Variables:** `uo` (eastward current), `vo` (northward current), `thetao`
  (SST) at the surface level.
- **Spatial subset:** bbox (lat −70…−66, lon 72…80) via Marine Data Store.
- **Temporal subset:** daily, **2016-01-01 → 2026-08-27** (manageable at 1/12°).
- **⚠ Network note:** the CMEMS identity server is **DNS-unreachable from
  this build environment** (verified). Credentials must be tested from a
  network that can resolve `identity.marine.copernicus.eu`.
- **Manual action:** register at data.marine.copernicus.eu/register →
  subscribe to GLORYS12V1 → set the two env vars → run test, then downloader.

## 4. Sentinel-1 SAR (future YOLO detection — not drift forcing)

- **Credential env vars:** `COPERNICUS_USERNAME`, `COPERNICUS_PASSWORD`.
- **Product:** Sentinel-1 `EW_GRDM` (~40 m, dual-pol DH). **Verified: 8,405
  EW_GRDM scenes** intersect the bbox (2014-11 → 2026-09).
- **Variables:** SAR backscatter intensity (sigma0), HH/HV polarization.
- **Spatial/temporal subset:** scenes intersecting bbox; download only a
  **small representative sample** (e.g., a handful of recent scenes) for
  future YOLO training — NOT the full archive.
- **Manual action:** register at dataspace.copernicus.eu → set the two env
  vars → run test, then a small-sample downloader.

---

## Manual credential checklist (what you must do)

| # | Provider | Sign-up | Approve/subscribe | Env vars to set |
|---|----------|---------|-------------------|-----------------|
| 1 | NASA Earthdata | urs.earthdata.nasa.gov | Approve "NSIDC DAAC" app | `NSIDC_USERNAME`, `NSIDC_PASSWORD` |
| 2 | ECMWF CDS | cds.climate.copernicus.eu | Generate API key | `CDS_API_URL`, `CDS_API_KEY` |
| 3 | Copernicus Marine | data.marine.copernicus.eu/register | Subscribe GLORYS12V1 | `CMEMS_USERNAME`, `CMEMS_PASSWORD` |
| 4 | Copernicus Data Space | dataspace.copernicus.eu | — (auto on register) | `COPERNICUS_USERNAME`, `COPERNICUS_PASSWORD` |

Place them in the project `.env` (never commit it) or export in the shell.

---

## Access tests (created)

`scripts/data/access_tests/` — each validates credentials with NO data download:

| Test | Env vars | On missing creds | On bad creds |
|------|----------|------------------|--------------|
| `test_nsidc.py` | NSIDC_USERNAME/PASSWORD | exit 2, prints steps | exit 3 (401) |
| `test_era5.py` | CDS_API_URL/CDS_API_KEY | exit 2, prints steps | exit 3 (401/403) |
| `test_glorys.py` | CMEMS_USERNAME/PASSWORD | exit 2, prints steps | exit 3 (401/400) |
| `test_sentinel1.py` | COPERNICUS_USERNAME/PASSWORD | exit 2 (still checks catalog) | exit 3 (401) |

Run all: `for t in scripts/data/access_tests/test_*.py; do python "$t"; done`

**Verified status in this environment:**
- NSIDC Earthdata auth server: reachable.
- ERA5 CDS API: reachable.
- CMEMS identity server: **unreachable (DNS)** — must test from another network.
- Data Space identity server: reachable; invalid creds → HTTP 401 (confirmed).
- Sentinel-1 catalog (public): reachable; **8,405 EW_GRDM scenes** in bbox.
