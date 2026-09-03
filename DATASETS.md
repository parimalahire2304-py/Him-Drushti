# Dataset Documentation

## Overview

This document describes the six priority data sources for the Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System (Prototype-1, East Prydz Bay). It records **verified findings** from Phase 1 — what was actually acquired, what requires manual authentication, and what remains pending. Where a value is unverified it is explicitly marked "Not verified yet." rather than guessed.

All spatial references use the Prototype-1 bounding box: **East Prydz Bay (-70.0° to -66.0° S, 72.0° to 80.0° E)** — a configurable demonstration box, not an official geographic boundary.

**Access status summary:**

| # | Dataset | Status | Auth required? |
|---|---------|--------|----------------|
| 1 | Antarctic iceberg tracks (NIC) | **Acquired + processed** | No |
| 2 | NSIDC sea-ice concentration | Investigated — blocked | Yes (Earthdata) |
| 3 | ERA5 meteorology | Investigated — blocked | Yes (CDS API) |
| 4 | GLORYS ocean | Investigated — blocked | Yes (CMEMS) |
| 5 | GEBCO bathymetry | **Acquired + processed** | No |
| 6 | Sentinel-1 SAR | Investigated — blocked | Yes (Data Space) |

---

## Dataset Registry

### 1. Antarctic Iceberg Track Data — ACQUIRED ✅

| Field | Details |
|-------|---------|
| **Dataset** | US National Ice Center (NIC) Antarctic Iceberg positions |
| **Provider** | US National Ice Center (usicecenter.gov); data originator NIC |
| **Product** | Antarctic Icebergs CSV archive (weekly snapshots) |
| **Purpose** | Historical iceberg positions for trajectory model training/validation |
| **Variables** | Iceberg ID/name, Length (NM), Width (NM), Latitude, Longitude, Last Update |
| **Spatial Resolution** | Point observations |
| **Temporal Resolution** | Weekly archive snapshots, 2014-11 to 2026-08 |
| **Coverage** | Antarctic waters (global Antarctic iceberg bulletin) |
| **Access Method** | Public HTTP, no authentication. `usicecenter.gov/Products/DisplaySearchResults` |
| **License/Usage** | Public U.S. Government data. Attribution to NIC appreciated. |
| **Prototype Usage** | Trajectory prediction training/validation (future phases) |
| **Raw location** | `data/raw/icebergs/` — 608 CSV files |
| **Processed location** | `data/processed/icebergs/east_prydz_bay_icebergs.csv` |
| **Status** | **Acquired + processed.** 796 East Prydz Bay records from 11 icebergs |

**Details:** 608 weekly CSVs (Nov 2014 – Aug 2026, ~2.7 MB total). Two CSV schemas over time (7-column with `Remarks`, and 9-column with `Area` fields) handled by extracting common columns. 27,759 total records; 796 records fall inside the East Prydz Bay bounding box, from 11 distinct icebergs (D23=551, C18B=75, D27=40, C39=30, B39=30, D15C=19, D15D=17, D22=14, D28=11, D21B=8, B09I=1). Temporal coverage within the box: 2016–2026.

**Data-quality findings:** 42 invalid lat/lon (0.2% of all records, outside region filter), 34 duplicate (Iceberg + date) records, 190 unique iceberg IDs globally. Missing `Length (NM)` common in the older schema. These are reported, not silently dropped.

**Reproduce:**
```
python scripts/data/download_icebergs.py --start 01/01/2014 --end 12/31/2026
python scripts/data/process_icebergs.py
```

> ⚠️ **Note on provenance:** The originally intended BYU/NIC database (nicicebergs.org) was unreachable from this environment (DNS/no route), and natice.noaa.gov did not respond. The US Ice Center hosts the same NIC-originated data and was used as the authoritative working source. This is documented rather than silently substituted.

---

### 2. NSIDC Sea-Ice Concentration — INVESTIGATED (blocked on auth) 🔒

| Field | Details |
|-------|---------|
| **Dataset** | NSIDC Sea-Ice Concentration (passive microwave) |
| **Provider** | National Snow and Ice Data Center (NSIDC DAAC) |
| **Product** | NSIDC-0051 (NASA Team) / NSIDC-0079 (Bootstrap) / NSIDC-0081 (near-real-time) |
| **Purpose** | Sea-ice concentration & extent for environmental context and sea-ice risk |
| **Variables** | Sea-ice concentration (%), extent flag; some include uncertainty |
| **Spatial Resolution** | ~25 km (polar stereographic grid) |
| **Temporal Resolution** | Daily |
| **Coverage** | Polar regions, 1978–present |
| **Access Method** | NASA Earthdata Login + NSIDC DAAC HTTPS/OpenDAP |
| **License/Usage** | NSIDC data use policies apply; free registration |
| **Prototype Usage** | Sea-ice boundary for risk assessment and route optimization (future) |
| **Status** | **Investigated — NOT acquired.** Requires NASA Earthdata Login. |

**Manual action required:**
1. Register a free account at `https://urs.earthdata.nasa.gov`
2. Approve the "NSIDC DAAC" application in your Earthdata profile.
3. Export `NSIDC_USERNAME` / `NSIDC_PASSWORD` (or populate `.env`) and run `python scripts/data/download_sea_ice.py`.

The NSIDC data server was unreachable from this environment (connection refused), so no subset was obtained. Reprojection (polar stereographic → EPSG:4326) and bbox subsetting are deferred until credentials are available. Resolution/coverage/units above are from product documentation; **variable names and missing-value fill: Not verified yet** (requires opening an actual file).

---

### 3. ERA5 Meteorological Reanalysis — INVESTIGATED (blocked on auth) 🔒

| Field | Details |
|-------|---------|
| **Dataset** | ERA5 Atmospheric Reanalysis (single levels) |
| **Provider** | ECMWF via Climate Data Store (CDS) |
| **Product** | `reanalysis-era5-single-levels` |
| **Purpose** | Atmospheric forcing — wind, temperature, pressure, precipitation |
| **Variables (selected)** | 10m u/v wind, 2m temperature, mean sea level pressure, total precipitation |
| **Spatial Resolution** | ~0.25° (~31 km) |
| **Temporal Resolution** | Hourly |
| **Coverage** | Global, 1940–present |
| **Access Method** | ECMWF CDS API v2 (key = `<uid>:<token>`) |
| **License/Usage** | ECMWF licence terms; free registration |
| **Prototype Usage** | Wind forcing for iceberg drift and sea-ice forecasting (future) |
| **Status** | **Investigated — NOT acquired.** Requires CDS API key. |

**Manual action required:**
1. Register a free account at `https://cds.climate.copernicus.eu`
2. Generate your personal API key in your profile.
3. Export `CDS_API_URL` / `CDS_API_KEY` (or populate `.env`) and run `python scripts/data/download_weather.py`.

The legacy CDS API v2 endpoint used by older `cdsapi` clients was retired; the current key format is `<uid>:<token>`. Only the five required variables are requested (no bulk download).

---

### 4. GLORYS Ocean Reanalysis — INVESTIGATED (blocked on auth) 🔒

| Field | Details |
|-------|---------|
| **Dataset** | GLORYS Ocean Reanalysis |
| **Provider** | Copernicus Marine Service (CMEMS) |
| **Product** | GLORYS12V1 (1/12° daily) |
| **Purpose** | Ocean currents, temperature for iceberg-trajectory forcing |
| **Variables (preferred)** | Surface uo/vos (currents), thetao (SST) |
| **Spatial Resolution** | 1/12° (~8 km) |
| **Temporal Resolution** | Daily |
| **Coverage** | Global ocean |
| **Access Method** | CMEMS Marine Data Store (Motu/OData) with personal credentials |
| **License/Usage** | CMEMS data access terms; free registration |
| **Prototype Usage** | Ocean-current forcing for iceberg trajectory prediction (future) |
| **Status** | **Investigated — NOT acquired.** Requires CMEMS account. |

**Manual action required:**
1. Register a free account at `https://data.marine.copernicus.eu/register`
2. Subscribe to GLORYS12V1.
3. Export `CMEMS_USERNAME` / `CMEMS_PASSWORD` (or populate `.env`) and run `python scripts/data/download_ocean.py`.

---

### 5. GEBCO Bathymetry — ACQUIRED ✅

| Field | Details |
|-------|---------|
| **Dataset** | GEBCO_2024 gridded bathymetry (sub-ice topography) |
| **Provider** | General Bathymetric Chart of the Oceans (GEBCO) via CEDA |
| **Product** | GEBCO_2024 sub-ice topography grid (15 arc-second) |
| **Purpose** | Seafloor depth for grounding risk and navigation constraints |
| **Variables** | `elevation` (m; negative = depth below sea level) |
| **Spatial Resolution** | 15 arc-second (~450 m) |
| **Temporal Resolution** | Static (release-based) |
| **Coverage** | Global ocean |
| **Access Method** | CEDA OPeNDAP server-side subsetting (no auth) |
| **License/Usage** | GEBCO data licence; free and open |
| **Prototype Usage** | Depth constraints for grounding risk and route optimization (future) |
| **Raw location** | None (global grid too large; subset derived directly via OPeNDAP) |
| **Processed location** | `data/processed/bathymetry/east_prydz_bay_bathymetry_15arcsec.nc` |
| **Status** | **Acquired + processed.** 960×1920 subset, elevation −3202 m to +410 m, ~3.7 MB |

**Reproduce:**
```
python scripts/data/download_gebco.py
```

---

### 6. Sentinel-1 SAR Imagery — INVESTIGATED (blocked on auth) 🔒

| Field | Details |
|-------|---------|
| **Dataset** | Sentinel-1 C-band SAR |
| **Provider** | ESA / Copernicus Programme |
| **Product** | Sentinel-1 EW (Extra-Wide swath) — GRDM recommended |
| **Purpose** | SAR imagery for future deep-learning iceberg detection (YOLO) |
| **Variables** | SAR intensity, polarization (dual-pol DH: HV/VV or HH/HV) |
| **Spatial Resolution** | EW_GRDM ~40 m; EW_GRD wide swath |
| **Temporal Resolution** | Revisit ~3 days in polar regions |
| **Coverage** | Global; polar enhanced revisit |
| **Access Method** | Copernicus Data Space OData API (catalog public; download requires OAuth2) |
| **License/Usage** | Copernicus data licence (free and open) |
| **Status** | **Investigated — NOT acquired.** 15,030 EW scenes available; download requires account. |

**Findings (verified via Copernicus Data Space OData API):**
- **15,030 EW-mode scenes** fall within the East Prydz Bay bounding box (2014-11-06 → 2026-09-03).
- **EW_GRDM** (Ground Range Detected Medium, ~40 m, dual-pol) is the recommended product for Antarctic iceberg detection — wide swath covers the box in one pass, medium resolution balances footprint and detail for YOLO.
- Recent representative scenes include `S1D_EW_GRDM_1SDH_20260903T160029...` (Sep 3, 2026), ~350–470 MB each.
- **Catalog search is public** (no auth). **Scene download returns HTTP 401 without credentials** — requires Copernicus Data Space OAuth2 credentials.

**Manual action required:**
1. Register a free account at `https://dataspace.copernicus.eu/`
2. Export `COPERNICUS_USERNAME` / `COPERNICUS_PASSWORD` (or populate `.env`).
3. Then a small number of representative scenes can be downloaded (not the full archive).

**Acquisition metadata recorded:** `data/raw/sar/sentinel1_acquisition_metadata.json`

---

## Data Pipeline Stages

All data flows through three stages as defined in the project directory structure:

| Stage | Directory | Description |
|-------|-----------|-------------|
| **Raw** | `data/raw/` | Original, unmodified data files. Never modified directly. |
| **Interim** | `data/interim/` | Intermediate processing outputs (regridded, subsetted, cleaned). |
| **Processed** | `data/processed/` | Final analysis-ready data ready for model input. |

## Data Access Notes

- Two datasets acquired (iceberg tracks, GEBCO bathymetry); four require manual account registration (NSIDC, ERA5/CDS, GLORYS/CMEMS, Sentinel-1/Data Space).
- Raw data is never overwritten or modified in place.
- Spatial subsetting to the Prototype-1 bounding box is performed during ingestion; the box is read from `config/region.yaml`, never hard-coded.
- All processed data preserves metadata and provenance (source URLs, acquisition date, region, schema).
- This dataset inventory is **not** sufficient for operational maritime navigation. It supports a research prototype only; limitations are recorded in `LIMITATIONS.md`.
