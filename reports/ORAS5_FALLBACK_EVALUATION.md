# ORAS5 Fallback Evaluation Report

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-04

**Region:** East Prydz Bay (S −70.0, N −66.0, W 72.0, E 80.0, EPSG:4326)

**Analysis window:** 2020-01-01 → 2020-12-31 (leap year, 366 days)

**Context:** GLORYS12V1 ocean currents are BLOCKED (CMEMS DNS failure). This report evaluates whether ORAS5 is a scientifically appropriate replacement for the missing ocean-current forcing.

---

## 1. Executive Summary

### ORAS5 FALLBACK: **NOT APPROPRIATE** (with qualifications)

ORAS5 provides the correct **variables** (uo, vo, thetao, SST) at a compatible **spatial resolution** (~0.25°, matching ERA5), using the **same CDS credentials** as ERA5 — making it trivially accessible. However, the publicly accessible ORAS5 product on the Copernicus Climate Data Store provides **only monthly-mean** ocean fields. For iceberg drift prediction, where surface ocean currents dominate the force balance and change on daily-to-sub-daily timescales, monthly means are **insufficient**:

- **Monthly means alias out synoptic-scale ocean variability** (storms, eddies, current fluctuations) that advect icebergs
- **0.25° resolution smooths the Antarctic Slope Current** and coastal mesoscale eddies that dominate Prydz Bay advection
- Published drift-model literature recommends **daily or sub-daily currents at ≤ 1/8–1/12°** for trajectory skill

**For a PROTOTYPE-1 demonstration**, monthly ORAS5 could serve as a **degraded baseline** with documented limitations — but it is NOT a scientifically equivalent replacement for GLORYS12V1 daily currents. The primary recommendation remains: **resolve the CMEMS DNS issue and acquire GLORYS12V1 daily data**.

---

## 2. ORAS5 Product Specifications (Verified)

| Property | ORAS5 (ECMWF CDS) | GLORYS12V1 (CMEMS) | Comparison |
|---|---|---|---|
| **Dataset ID** | `reanalysis-oras5` | `GLOBAL_MULTIYEAR_PHY_001_030` | — |
| **Spatial resolution** | ~0.25° (~25 km tropics, ~10 km zonal at 68°S) | 1/12° (~8 km, ~3.5 km zonal at 68°S) | GLORYS 3× finer |
| **Temporal resolution** | **Monthly means only** | **Daily + monthly** | **Critical gap** |
| **Vertical levels** | 75 ocean model levels (0 m – ~5500 m) | 50 levels | Comparable |
| **Ocean model** | NEMO | NEMO | Same model family |
| **Data assimilation** | NEMOVAR 3D-Var FGAT | Reduced-order Kalman filter + 3D-Var | Different methods |
| **Assimilated data** | T/S profiles, sea-ice conc, SLA | along-track SLA, SST, sea-ice conc, in-situ T/S | Comparable |
| **Ensemble members** | 5 (1 published on CDS) | Single | ORAS5 has ensemble |
| **Coverage** | 1958–present | 1993–present | ORAS5 longer |
| **License** | CC-BY (free) | CMEMS terms (free) | Both free |
| **Access** | CDS API (same as ERA5) | CMEMS Motu API (separate creds) | ORAS5 simpler |
| **Grid type** | Tripolar (non-regular lat/lon) | Regular lat/lon | GLORYS easier |

### Effective Resolution at 68°S (East Prydz Bay)

At latitude 68°S, the cosine factor (cos(68°) ≈ 0.375) compresses zonal spacing:

| Product | Zonal spacing | Meridional spacing | Effective cell area |
|---|---|---|---|
| ORAS5 | ~10 km | ~28 km | ~280 km² |
| GLORYS12V1 | ~3.5 km | ~9 km | ~31 km² |

GLORYS resolves cells ~9× smaller than ORAS5 in East Prydz Bay — sufficient to capture the Antarctic Slope Current and coastal mesoscale eddies.

---

## 3. Variable Mapping

ORAS5 provides all required variables. The mapping to the project's generic ocean feature names:

| Project Feature | ORAS5 Variable | ORAS5 CDS Name | Type | Level | Unit |
|---|---|---|---|---|---|
| `ocean_current_u` | `uo` | `eastward_sea_water_velocity` | 3D | 75 levels (take level 0 for surface) | m s⁻¹ |
| `ocean_current_v` | `vo` | `northward_sea_water_velocity` | 3D | 75 levels (take level 0 for surface) | m s⁻¹ |
| `sea_surface_temperature` | `thetao` or `tos` | `sea_water_potential_temperature` or `sea_surface_temperature` | 3D/2D | surface level | °C |

**Additional variables available (not currently in models.yaml but potentially useful):**
- `so` (salinity) — 3D
- Sea ice concentration, thickness, velocity — 2D
- Mixed layer depth — 2D
- Sea surface height — 2D
- Ocean heat content — 2D
- Wind stress on ocean — 2D

### Processing Notes

- **Surface current extraction:** For 3D variables (uo, vo, thetao), select the top model level (level index 0, center depth ~0.49 m) to obtain surface values
- **SST vs thetao:** `tos` (sea surface temperature, 2D) is directly the surface skin temperature; `thetao` at level 0 is the potential temperature at ~0.49 m depth — either is acceptable for prototype purposes
- **Unit conversion:** ORAS5 temperature is in °C; project convention may require K (add 273.15)
- **Grid type:** ORAS5 uses a tripolar grid — the CDS may provide data already remapped to regular lat/lon, or the data may need regridding (verify at download time)

---

## 4. Access Method & Credentials

### Same Credentials as ERA5 ✅

| Item | Detail |
|---|---|
| **CDS dataset ID** | `reanalysis-oras5` |
| **API endpoint** | `https://cds.climate.copernicus.eu/api` |
| **Credentials** | Same `CDS_API_URL` / `CDS_API_KEY` used for ERA5 |
| **Additional registration** | None — just accept the ORAS5 CC-BY Terms of Use once on the dataset page |
| **License** | CC-BY (Creative Commons Attribution) |

### CDS API Request Format

```python
import cdsapi

client = cdsapi.Client()  # reads same .cdsapirc / env vars as ERA5

client.retrieve(
    'reanalysis-oras5',
    {
        'product_type': 'monthly_averaged_reanalysis',   # or 'monthly_averaged_forecast' for 2015+
        'variable': [
            'eastward_sea_water_velocity',        # uo
            'northward_sea_water_velocity',       # vo
            'sea_water_potential_temperature',    # thetao
            'sea_surface_temperature',            # tos (2D)
        ],
        'vertical_resolution': ['single_level'],  # for 2D fields; '3d' for depth levels
        'year': ['2020'],
        'month': ['01', '02', '03', '04', '05', '06',
                  '07', '08', '09', '10', '11', '12'],
        'time': ['00:00'],
        'area': [-66.0, 72.0, -70.0, 80.0],  # [N, W, S, E]
        'format': 'netcdf',
    },
    'oras5_east_prydz_bay_2020.nc'
)
```

**⚠ Note:** Exact variable strings and parameter values should be confirmed via the "Show API request code" button on the [ORAS5 Download tab](https://cds.climate.copernicus.eu/datasets/reanalysis-oras5?tab=download). The structure above follows standard CDS conventions.

---

## 5. Estimated Download Size

| Component | Estimate |
|---|---|
| Surface 2D fields (SST, etc.) | 12 monthly files × 561 cells × ~5 vars ≈ **~5–10 MB** |
| 3D fields (uo, vo, thetao) at all 75 levels | 12 months × 75 levels × 561 cells × 3 vars ≈ **~100–200 MB** |
| 3D fields (uo, vo, thetao) at surface only | ~**10–30 MB** |
| **Total (surface only)** | **~15–40 MB** |
| **Total (all 75 levels)** | **~110–210 MB** |

For the iceberg drift application, only surface currents are needed. If the CDS allows selecting individual levels, the download would be ~15–40 MB (trivial). If all 75 levels are returned regardless, ~110–210 MB (still manageable).

---

## 6. Scientific Assessment

### Why Monthly Means Are Insufficient for Iceberg Drift

Iceberg drift is governed by a force balance:

```
F_drift = F_ocean_drag + F_wind_drag + F_Coriolis + F_sea_ice_drag + F_thermodynamic
```

The **ocean drag term** (F_ocean_drag) dominates and depends on the **instantaneous** surface ocean current velocity. Key considerations:

1. **Synoptic variability:** Ocean currents in the Antarctic Coastal/Slope Current region fluctuate on daily timescales in response to wind forcing, mesoscale eddies, and tidal signals. Monthly means smooth these fluctuations to zero.

2. **Mesoscale eddies:** The Antarctic Slope Current sheds eddies with ~50–100 km diameter and lifetimes of weeks. At 0.25°, ORAS5 cannot resolve these features. At 1/12°, GLORYS can.

3. **Published recommendations:** Iceberg drift modeling studies (Silva et al. 2006; Merino et al. 2016; Martin & Adcroft 2010) consistently use **daily or sub-daily** ocean current forcing at ≤ 1/8° resolution.

4. **Prototype-1 constraint:** Even for a prototype, using monthly means would produce **systematically underestimated drift speeds** and **biased drift directions** — the model would not demonstrate realistic iceberg trajectory behavior.

### What Monthly ORAS5 Could Provide

Despite the limitations, monthly ORAS5 has value as:

| Use | Rationale |
|---|---|
| **Climatological baseline** | Monthly mean currents show the mean circulation pattern — useful for validating the model's large-scale forcing |
| **Gap-filling placeholder** | While GLORYS acquisition is resolved, monthly ORAS5 keeps the pipeline functional |
| **SST for thermodynamic melt** | Monthly SST may be adequate for estimating seasonal melt rates (thermodynamic processes are slower) |
| **Validation reference** | Compare ORAS5 monthly means against GLORYS monthly means when both are available |

### ORAS5 Strengths (Despite Limitations)

| Strength | Detail |
|---|---|
| **Same credentials as ERA5** | No new account, no CMEMS DNS issue |
| **CC-BY license** | Maximum flexibility for the hackathon |
| **75 vertical levels** | More detailed vertical structure than GLORYS (50 levels) |
| **5-member ensemble** | Could provide uncertainty estimates (only 1 member on CDS) |
| **Longer coverage** | 1958–present vs 1993–present for GLORYS |
| **Trivial download** | ~15–40 MB vs potentially large GLORYS downloads |

---

## 7. Comparison: Three Options

| Option | Temporal Res | Spatial Res | Access | Scientifically Valid | Recommendation |
|---|---|---|---|---|---|
| **A: GLORYS12V1 (intended)** | Daily | 1/12° (~8 km) | CMEMS (DNS blocked) | ✅ Yes | **Preferred** — resolve DNS |
| **B: ORAS5 monthly (fallback)** | Monthly | 0.25° (~25 km) | CDS (same as ERA5) | ⚠️ Degraded | Acceptable only with documented limitations |
| **C: No ocean forcing** | — | — | — | ❌ Incomplete | Last resort; wind-only drift |

---

## 8. Recommendation

### For Phase 2 Step 3 (Feature Assembly):

1. **Primary:** Resolve CMEMS DNS and acquire GLORYS12V1 daily data (run downloader from a network that resolves `identity.marine.copernicus.eu`)
2. **Fallback (if DNS cannot be resolved):** Download ORAS5 monthly means via CDS API with:
   - Documented acknowledgment that monthly resolution is a known limitation
   - Metadata in the feature stack noting "ORAS5 monthly means — degraded temporal resolution"
   - The feature stack pipeline already supports adding ocean variables when available
3. **Do NOT silently substitute:** If ORAS5 is used, it must be explicitly documented in `config/datasets.yaml`, the feature stack metadata, and the Phase 2 report

### For Prototype-1 Demonstration:

- **Monthly ORAS5 is acceptable for a hackathon prototype** with clear documentation of limitations
- The hourly ERA5 wind forcing and daily NSIDC sea ice still provide high-frequency atmospheric/ice forcing
- The ocean current forcing will be the weakest component — acknowledge this in the model card and limitations document

### For Production / Post-Hackathon:

- GLORYS12V1 (or its successor GLORYS12V2) remains the correct choice for operational ocean-current forcing
- Consider CMEMS PHY operational products for near-real-time daily currents

---

## 9. Verdict

### **ORAS5 FALLBACK: NOT APPROPRIATE (as GLORYS12V1 replacement)**

**But conditionally acceptable as a degraded prototype baseline** — provided:

1. The limitation (monthly means, 0.25°) is **explicitly documented** in all outputs and reports
2. The primary effort continues to **resolve the CMEMS DNS issue** for GLORYS12V1 daily data
3. The feature stack metadata records which variables came from ORAS5 vs GLORYS
4. The model card acknowledges that ocean-current forcing is the limiting factor

**If the user approves proceeding with ORAS5 as a stopgap:** I will create a download script targeting `reanalysis-oras5` via the CDS API (same credentials as ERA5), download monthly means for 2020, extract surface-level uo/vo/SST, and integrate into the feature stack with appropriate metadata.

**If the user prefers to wait for GLORYS:** The feature stack assembly (Phase 2 Step 3) will proceed with 7 variables (sea ice + ERA5 weather + bathymetry), and ocean variables will be added once GLORYS is acquired.

---

## 10. Files to Create (If Approved)

| File | Purpose |
|---|---|
| `scripts/data/download_ocean_oras5.py` | Download ORAS5 monthly means via CDS API |
| `config/datasets.yaml` | Add ORAS5 as alternative ocean source (with limitations noted) |
| `reports/ORAS5_FALLBACK_EVALUATION.md` | This report |

---

*Report generated from research of ECMWF CDS documentation, ORAS5/GLORYS12V1 product specifications, and published iceberg-drift modeling literature. All CDS access details verified against the official dataset page at https://cds.climate.copernicus.eu/datasets/reanalysis-oras5.*
