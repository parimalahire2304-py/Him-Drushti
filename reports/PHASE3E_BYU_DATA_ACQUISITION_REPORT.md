# Phase 3E — BYU Drifting-Iceberg Data Acquisition and Verification Report

**Project:** Prototype-1 · SIH: AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory, and Navigation Decision Support System

**Date:** 2026-09-06
**Status:** ✅ ACQUISITION + VERIFICATION COMPLETE (no merge, no retraining)

---

## Executive Summary

The **BYU MERS Consolidated Antarctic Iceberg Tracking Database v8.0** was acquired, filtered to East Prydz Bay, filtered to observed-only positions, gap-QC'd, and deduplicated against the existing NIC archive. The finding is decisive but **negative for the drift-scarcity bottleneck**:

| Claim | Result |
|---|---|
| Source verified from official documentation | ✅ YES |
| Data acquired with integrity record | ✅ YES (SHA256 `47d89…40cae`) |
| Observed-only filtering works | ✅ YES (0 interpolated rows in observed set) |
| **New icebergs added in the dataset's supported years (2016–2021, 2024–2025)** | **0** |
| **Genuine independent additional drifting pairs (7-day, non-overlapping)** | **~8** |
| D23 pseudo-"drifting" pairs produced by naive threshold (scatterometer noise) | **~914 raw / +30 non-overlapping — must NOT be added** |
| C39 leakage risk (all C39 pairs fall in the 2025 test window) | ⚠️ MODERATE — test-set modification only, not train leakage |

**Bottom line:** BYU's consolidated database provides **no genuinely new independent drifting trajectories** for East Prydz Bay within the years the ML dataset already covers. It densifies (daily vs weekly) the **same** trajectories of the **same 8 icebergs** on the **same time windows**. Under the project's fixed 7-day single-step pair protocol, that density is autocorrelated and adds only ~8 effective independent pairs (0 new icebergs). Its real scientific value lies in (a) an **independent cross-source check** of the NIC archive, and (b) dense daily scatterometer data that only becomes usable if the project ever moves to a sub-weekly forecast resolution — a model-design change, not this phase.

**Recommendation: NEEDS REVIEW — DO NOT auto-integrate the raw BYU pairs.** A narrowly-scoped, reviewed integration of only the non-D23 scatterometer positions *within existing trajectory windows* could add ~6–8 genuinely drifting samples, but does not address the Phase 3D bottleneck.

---

## Step 1 — Source Verification (from official documentation)

Verified from the official BYU page `https://www.scp.byu.edu/data/iceberg/database1.html` (no undocumented properties assumed):

| Property | Verified Value |
|---|---|
| Exact name | **BYU MERS Consolidated Antarctic Iceberg Database** (a.k.a. BYU/NIC Iceberg Tracking Database) |
| Institution / PI | Brigham Young University, Microwave Earth Remote Sensing (MERS) Lab / SCP Project; PI Dr. D. G. Long |
| Access location | https://www.scp.byu.edu/data/iceberg/consolidated_database_v8.0.zip |
| Version | **v8.0** (4.1 MB zip); nominal coverage "1978 through April 22, 2025"; observed record spans to 2026-04-30 for some icebergs |
| Spatial coverage | Antarctic (Southern Hemisphere high latitudes) |
| Observation frequency | Daily where possible; "mostly daily position updates" |
| Individual iceberg trajectories? | **YES — one CSV per named iceberg, 647 files** |
| Observed vs derived | **Explicit per-day flag per sensor:** `sensor_3` = 1 (observation) or 0 (interpolated). Interpolation only when gap < 14 d AND displacement < 3°; interpolated-over-land dropped. `0,0` = no data sentinel |
| Iceberg identifiers | NIC designation (prefix a/b/c/d) or scatterometer-only (prefix sa/e/uk) |
| Coordinate convention | Decimal degrees, **positive North and East** |
| Date convention | Julian date `YYYYDDD` |
| Quality flags | Yes — the `_3` binany observed/interpolated flag per sensor |
| Gap indicators | No explicit gap column; gaps implied by date spacing (0,0 rows serve as per-sensor no-data) |
| Sensor set | sass (1978), ers (1992–2001), nscat, qscat (1999–2009), seawinds, oscat, ascat (2006–present) |
| Licensing | No explicit license page; NASA/NSF funded research database; citation Budge & Long, IEEE JSTARS 2017, doi:10.1109/JSTARS.2017.2784186 |

**Step 1 PASS.** The consolidated DB (not the statistical DB) was chosen because it (i) retains the observed/interpolated flag required by the Phase 3E observed-only rule, (ii) contains raw sensor positions rather than statistically reconstructed means, and (iii) is the most current version.

---

## Step 2 — Preflight Inventory

Checked `data/raw/icebergs/byu/` before download: **no BYU data present**. No earlier BYU acquisition exists in the repository. The existing NIC archive (`data/raw/icebergs/AntarcticIcebergs_*.csv`, 608 weekly files → processed `data/processed/icebergs/east_prydz_bay_icebergs.csv`, 796 obs / 11 IDs) is the only iceberg-track source.

**Step 2 PASS** — download was genuinely new; nothing was overwritten.

---

## Step 3 — Acquisition

| Field | Value |
|---|---|
| URL | https://www.scp.byu.edu/data/iceberg/consolidated_database_v8.0.zip |
| Download date | 2026-09-05 |
| Local file | `data/raw/icebergs/byu/consolidated_database_v8.0.zip` |
| Size | 4,065,659 bytes (4.1 MB) |
| MD5 | `33724d79c71461ea0c4f6cd02b3a5068` |
| SHA256 | `47d899c8bb1c3266d0b8c94a6f87c435dc68827a53f39dea3d78fe68ccc40cae` |
| Zip contents | 650 entries: `updated7_consol/` + 647 `.csv` (one per iceberg) + `README_consolidated.TXT` + a stray `#d15b.csv#` editor artefact |
| Extraction | `data/raw/icebergs/byu/updated7_consol/` (original zip preserved in place) |
| Log | `data/raw/icebergs/byu/acquisition_log.json` |

`zipfile.testzip()` → **no bad files; integrity OK.** The original ZIP is preserved; extracted CSVs are a derived copy.

---

## Step 4 — East Prydz Bay BBOX Filter

Applied region bbox **lat −70.0…−66.0, lon 72.0…80.0 (EPSG:4326)** to all parsed records (coordinates unchanged).

| Filter stage | Records | Icebergs |
|---|---:|---:|
| All sensors, all Antarctica (BYU-wide) | 738,679 | 647 files |
| **In bbox (all sensors)** | **16,982** | 61 |
| In bbox, observed only | 10,076 | 60 |
| In bbox, interpolated (excluded) | 6,906 | (part of above) |

In-bbox icebergs include the project's **8 ML icebergs** (B39, C18B, C39, D21B, D22, D23, D27, D28) plus 52 others tracked through the bay in earlier eras (B15-series 2003–2009, B09-series, UK unnamed 2002–2009, D03 1978, D14 2011–2013, C28B 2013–2014, D21A 2014, etc.).

---

## Step 5 — Observed-Only Rule

Used the per-sensor `_3` flag: keep rows with `flag = 1`, drop rows with `flag = 0` (interpolated) and the `0,0` no-data sentinel.

- **Observed positions kept (in bbox): 10,076** — ascat 3,854, qscat 3,325, ers 1,174, nic 1,088, oscat 367, nscat 196, sass 72 (scatterometer = 8,988; NIC = 1,088).
- **Interpolated/gap-filled rows excluded (in bbox): 6,906** (nic 5,913, ascat 833, qscat 126, oscat 29, ers 3, nscat 2).
- **0 interpolated rows remain in the observed set** (verification passed).

**Step 5 PASS.** The flag reliably distinguishes observed from interpolated, so no arbitrary judgement was needed.

> Combined-sensor daily series (one position per iceberg per day) → 9,023 daily observed positions; 60 in-bbox icebergs represented.

---

## Step 6 — Gap QC

Gap statistics on the combined observed daily series per in-bbox iceberg (no interpolation performed anywhere):

| Iceberg | n obs days | Span | median gap | max gap | gaps > 7 d |
|---|---:|---:|---:|---:|---:|
| D23 | 2,195 | 3764 d (2016–2026) | 1 d | 22 d | 15 |
| D27 | 189 | 298 d (2020–2021) | 1 d | 8 d | 1 |
| B39 | 134 | 236 d (2019–2020) | 1 d | 35 d | 1 |
| C18B | 117 | 524 d (2024–2025) | 6 d | 14 d | 16 |
| C39 | 81 | 204 d (2025–2026) | 1 d | 9 d | 2 |
| D22 | 69 | 102 d (2019) | 1 d | 7 d | 0 |
| D28 | 52 | 219 d (2019–2020) | 1 d | 137 d | 1 |
| D21B | 49 | 89 d (2017) | 1 d | 30 d | 1 |

Scatterometer series are essentially **gap-free daily** (median gap 1 d). 7-day pairs were built **only where an observation exists at both t and t+7** (project methodology, no interpolation): e.g., D23 by NIC = 382 pairs (mean 7-d disp **0.104 km**, matching the project's NIC-derived 0.083 km grounding); D23 by ASAT = 1,493 pairs (mean 7-d disp **1.236 km** — scatterometer noise, see Step 7).

---

## Step 7 — Identify Drifting Icebergs

Reused the project's **exact** approved threshold: **an iceberg is GROUNDED if mean 7-day displacement ≤ 0.5 km, else DRIFTING** (Phase 3A Expanded Dataset Build Report, Metric 4; D23 → grounded, 0.08 km).

**CRITICAL METHODOLOGICAL FINDING — the threshold does not transfer to scatterometer positions:**

| Iceberg | Mean 7-d disp via NIC (km) | Mean 7-d disp via ASAT (km) | Project class |
|---|---:|---:|---:|
| **D23** | **0.104** (archive: 0.083) | **1.236** (jitter noise; median 0.000, p95 8.4) | **GROUNDED** |
| D27 | 10.96 | 10.48 | DRIFTING |
| B39 | 31.06 | 31.87 | DRIFTING |
| C39 | 15.98 | 26.08 | DRIFTING |
| C18B | 15.74 | 2.50 *(ASAT center mismatch)* | DRIFTING |

For genuinely drifting icebergs the ASAT displacement agrees with NIC within measurement uncertainty (D27, B39). But for the grounded D23, **ASAT 25-km scatterometer jitter inflates apparent 7-day "displacement" to ~1.2 km — above the 0.5 km threshold — which would spuriously classify D23 as DRIFTING.** Consequently:

- **Classification based on NIC/archive point observations is retained** (the project's approved protocol and the only one consistent with the 0.5 km threshold).
- **Naively classifying BYU scatterometer pairs would inject ~914 D23 pseudo-"drifting" samples** — catastrophic for drift modeling (1270% of current drifting-pair count, all noise).
- Per the Phase 3E instruction ("if ambiguous STOP"): the D23 classifications are ambiguous under scatterometer data, so those pairs are flagged NOT-USEABLE; only the NIC-consistent classification is relied on.

---

## Step 8 — Deduplication vs NIC

Went pair-by-pair on **(iceberg, observation-date)** identity (project's identity matching; no forced matching of ambiguous IDs, e.g., C18B ASAT/NIC center mismatch explicitly NOT merged).

Current dataset reference: 451 pairs (342 train / 55 val / 54 test; B39 28, C18B 40, C39 9, D21B 7, D22 11, D23 309, D27 38, D28 9).

| BYU supported-year (iceberg, obs_date) pairs | Count |
|---|---:|
| Total in the 7 dataset years (2016, 2017, 2019, 2020, 2021, 2024, 2025) | 1,683 |
| — provenance NIC (identical source as archive) | 239 |
| — provenance NIC+Ascat same day (BOTH) | 172 |
| — provenance scatterometer-only (independent) | 1,272 |
| **Exact duplicates of current 451 pairs (removed)** | **434** (train 325/342 = 95%, val 55/55, test 54/54) |
| **Marginal additional (iceberg, obs_date) pairs** | **1,249** (all scatterometer) |

**Key result:** BYU's NIC positions are the *same* observations already in the archive — 95–100% of current train/val/test pairs are reproduced one-to-one by BYU (the 17 train-date gaps = NIC weekly positions BYU's consolidated files do not carry). The extractable NEW content is the **scatterometer daily density** (1,272 pairs raw), which does not duplicate NIC dates.

---

## Step 9 — Candidate Value Ranking (per iceberg)

Marginal additional BYU-supported pairs, in order of genuine ML usefulness:

| Iceberg | Current pairs | BYU marginal (obs_date) | Non-overlapping effective add | Drift-class | ML value |
|---|---:|---:|---:|---:|---|
| D27 | 38 | 112 | **+1** | DRIFTING | Densify 2020–21 window; +1 independent |
| C18B | 40 | 38 | **+2** | DRIFTING (ASAT center mismatch) | +2 independent; ASAT/NIC conflict unresolved |
| D22 | 11 | 39 | **+2** | DRIFTING | +2 independent |
| D21B | 7 | 32 | **+1** | DRIFTING | +1 independent |
| D28 | 9 | 22 | **+1** | DRIFTING | +1 independent |
| C39 | 9 | 4 | **+1** | DRIFTING | **test-window only** (step 11) |
| B39 | 28 | 88 | **+0** | DRIFTING | window fully covered by NIC; nothing new |
| D23 | 309 | 914 | **+30** | GROUNDED (noise) | **NOT USEABLE — scatterometer jitter** |
| New icebergs (D14, C28B, D21A, UK*, B15*, …) | 0 | 0 (supported years) | **0** | — | **0 new icebergs in supported years** |

Ranking by effective contribution: **D27 = C18B > D22 > D21B = D28 > C39(?) > B39 = 0 > D23 (excluded) > 0 new icebergs.**

---

## Step 10 — Dataset Impact Estimate (VERIFIED vs ESTIMATE)

All of the following are **ESTIMATES of an unbuilt merge** (nothing modified; current dataset untouched at 451/8/142/309).

**Independent-sample-corrected view (scientifically valid for the 7-day pair protocol):**

| Indicator | Current (VERIFIED) | Potential with BYU (ESTIMATE) |
|---|---:|---:|
| Total pairs | 451 | ~451 + **~38** (≈489) |
| — of which D23 (grounded, noise) | 309 | +~30 **excluded** (not useable) |
| — of which genuinely drifting, non-C39 | ... | **+~6–8** |
| — of which C39 (test) | 9 | +~1 (test only) |
| Drifting pairs | 142 | ~148–150 |
| Icebergs | 8 | **8** (no new) |
| New icebergs | — | **0** |

**Raw/window-uncorrected view** (informational only; NOT recommended because daily windows overlap ~72–78%):

| Indicator | Raw value (iceberg, obs_date) |
|---|---:|---:|
| Marginal additional pairs | 1,249 (→ 1,700 total if all added) |
| of which would pass naive 0.5 km rule as "drifting" | 1,249 (incl. 914 D23 noise) |
| Interpolated rows excluded (bbox) | 6,906 |

**Genuine independent BYU contribution ≈ +6–8 drifting pairs, +0 icebergs, +0 independent B39 pairs.** This is far below the Phase 3D requirement (≈200–300 additional drifting pairs to begin challenging persistence), so **BYU does not move the bottleneck.**

---

## Step 11 — Leakage and Test-Set Safety

| Risk | Assessment |
|---|---|
| Leak into TRAIN (pre-2024) | **None.** BYU adds no new pre-2024 (iceberg, date) pairs outside the current train set's own dates; the only 2024-derived BYU extras are C18B, inside the validation window. |
| Leak into VAL (2024) | None beyond C18B (already in val). |
| Modify TEST / C39 zero-shot | ⚠️ **All 13 C39 supported pairs lie in/after the test window (≥ 2025-01-16)**; 9 are the current test pairs, +4 marginal (of which only ~1 independent). Merging would **change the C39 zero-shot test composition**, which is disallowed without approval. C39 must remain frozen (0 train / 0 val / 9 test). |
| Temporal overlap | BYU windows are coterminous with current NIC windows; no extension of any trajectory beyond the archive's end (2026 is out of scope and contains C39/D15C only). |
| Spatial overlap / twin-mapping | C18B ASAT center vs NIC center mismatch (2.50 vs 15.74 km mean disp) — identities are NOT unambiguously the same geometric point; not forced. |
| Conclusion | Test set untouched now; any future merge MUST exclude C39 and MUST keep the split boundaries and C39 isolation. |

---

## Step 12 — Validation

| Check | Result |
|---|---|
| Zip readable / `testzip()` | ✅ PASS (no bad files) |
| Original file preserved | ✅ ZIP untouched at 4,065,659 bytes |
| All coordinates in valid range | ✅ 100% (lat [−90,90], lon [−180,180]) |
| All dates valid (≥ 1978, JD parsed) | ✅ 1978-07-23 … 2026-04-30 |
| No-fabrication rule | ✅ No positions created; observed-only filter excludes all 6,906 interpolated rows; 0 remain |
| No duplicates | ✅ One position per iceberg per day after dedup; duplicate (iceberg, date) removed |
| BBOX correct | ✅ lat −70…−66, lon 72…80 applied to coordinates, not approximated |
| Observed-only rule functional | ✅ flag present for all 10,076 observed records |
| D23 grounding reproduced from BYU NIC | ✅ 0.104 km (archive 0.083 km) |
| Phase 1 files | ✅ `git status` clean for `data/processed/icebergs`, `data/processed/sea_ice`, `data/processed/weather`, `data/processed/ocean` (data/ is gitignored; no mtime writes this phase) |
| Phase 2 / Phase 3 original | ✅ untouched (original `data/processed/ml/full.parquet` 101 pairs not modified) |
| Phase 3C expanded dataset | ✅ untouched (451/8/142/309 intact; metadata unchanged) |
| Models | ✅ No model trained, none modified |
| New files created (this phase only) | `data/raw/icebergs/byu/**` (zip, extraction, `acquisition_log.json`, `analysis/*`), `scripts/data/analyze_byu.py`, `scripts/data/analyze_byu_pairs.py`, this report |

---

## Files Produced (Phase 3E)

```
data/raw/icebergs/byu/
├── consolidated_database_v8.0.zip       ← original (preserved, SHA256 recorded)
├── acquisition_log.json                  ← Step 3 record
├── updated7_consol/                      ← extracted 647 per-iceberg CSVs + README
└── analysis/
    ├── byu_in_bbox_all_sensors.csv       ← all in-bbox records
    ├── byu_in_bbox_observed.csv          ← flag=1 only
    ├── byu_in_bbox_interpolated.csv      ← flag=0 (excluded)
    ├── byu_gap_qc.csv                    ← per iceberg/sensor gap stats
    ├── byu_iceberg_pairs_summary.csv     ← per-iceberg pair + drift class
    ├── byu_all_7d_pairs.csv              ← all 7-day pairs
    ├── byu_supported_pairs.csv           ← 7-dataset-year pairs
    └── byu_summary.json
scripts/data/analyze_byu.py               ← parse/bbox/observed/gap-qc
scripts/data/analyze_byu_pairs.py         ← pair building, classification, dedup
reports/PHASE3E_BYU_DATA_ACQUISITION_REPORT.md
```

Analysis intermediates are reproducible from the two scripts against the original ZIP.

---

## Conclusion

BYU consolidated v8.0 is a high-quality, well-flagged, **independently observed** database, and its acquisition brings a genuine cross-source reference for the NIC archive. But within East Prydz Bay and the dataset's supported years it contains **no new icebergs and only ~6–8 effective independent drifting pairs** beyond what the NIC archive already provides; the remaining apparent additions are (i) autocorrelated overlapping daily windows and (ii) ~914 D23 scatterometer-noise rows that would corrupt the drift class balance. It therefore **does not solve the drifting-trajectory scarcity/diversity bottleneck identified in Phase 3D.**

Its defensible uses: (1) **cross-validation / QA** of the existing NIC-derived pairs; (2) a **dense daily trajectory library** should a future experiment adopt a sub-weekly forecast horizon (a model-design decision outside this phase); (3) re-examination in a later "BYU-only east-Prydz-bay daily experiment" if the project ever approves changing temporal resolution.

---

## FINAL OUTPUT

| Field | Value |
|---|---|
| **STATUS** | COMPLETE |
| **BYU SOURCE VERIFIED** | **YES** (name, URL, v8.0, coverage, freq, per-iceberg files, observed/interpolated flags, coords, licensing — all from official docs) |
| **DATA ACQUIRED** | **YES** (4.1 MB zip; SHA256 `47d899c8…ccc40cae`; zip test passed) |
| **OBSERVED-ONLY DATA VERIFIED** | **YES** (10,076 in-bbox observed; 6,906 interpolated excluded; 0 remain) |
| **BYU OBSERVATIONS** | 738,679 records all-sensors Antarctic-wide; **10,076 observed in East Prydz Bay** (8,988 scatterometer + 1,088 NIC) |
| **BYU ICEBERGS** | 647 individual trajectory files |
| **EAST PRYDZ BAY ICEBERGS** | 60 with observed records in bbox |
| **UNIQUE ICEBERGS AFTER NIC DEDUPLICATION** | **8** (the current set; 0 new) |
| **ADDITIONAL VALID 7-DAY PAIRS** | Raw marginal (iceberg, obs_date): **1,249**; **independence-corrected: ~38** (B39 +0, D27 +1, C18B +2, D22 +2, D21B +1, D28 +1, C39 +1 test, D23 +30 excluded) |
| **ADDITIONAL DRIFTING PAIRS** | **~6–8 genuine** (D27 +1, C18B +2, D22 +2, D21B +1, D28 +1); D23-scatterometer (+~914 raw) NOT classifiable as drifting |
| **ADDITIONAL GROUNDED PAIRS** | **0 genuine** (D23 remains grounded at 0.10 km NIC; its ASAT 1.24 km is noise) |
| **CURRENT PAIRS: 451** | unchanged |
| **CURRENT DRIFTING PAIRS: 142** | unchanged |
| **POTENTIAL NEW TOTAL PAIRS** | ~489 (independent-corrected); 1,700 if all raw windows were naively added (**not recommended**) |
| **POTENTIAL NEW TOTAL DRIFTING PAIRS** | ~148–150 (independent-corrected, C39-excluded) |
| **POTENTIAL NEW ICEBERG COUNT** | 8 (no new) |
| **DUPLICATES REMOVED** | 434 of 1,683 BYU-supported pairs matched current (iceberg, obs_date); NIC-derived 411 rows not double-counted |
| **INTERPOLATED/GAP-FILLED ROWS EXCLUDED** | 6,906 (in-bbox flag=0) |
| **LEAKAGE RISK** | None to train/val. ⚠️ All C39 pairs fall in the test window (would alter zero-shot C39 composition — must remain frozen). No trajectory extended beyond NIC archive end. |
| **DATA QUALITY** | Good. Explicit observed/interpolated flags; daily scatterometer independent of NIC; BUT 25-km scatterometer jitter (~1.2 km on D23) means **the 0.5 km drift threshold only applies to NIC-class point observations — scatterometer pairs are unusable for grounded-iceberg classification** |
| **PHASE 1/2/3/3C MODIFIED** | **NO** (git clean for tracked files this phase; dataset/metadata/models untouched) |
| **RECOMMENDATION** | **NEEDS REVIEW — DO NOT INTEGRATE raw BYU pairs.** Value is real but orthogonal to the Phase 3D bottleneck: use as independent QA/cross-check of the NIC archive now; retain the dense daily library for a future sub-weekly-horizon experiment. A reviewed, C39-excluded, non-D23 subset (≈+6–8 drifting pairs) is optional, not a bottleneck fix. |

## STOP HERE — WAIT FOR EXPLICIT APPROVAL BEFORE MERGING

No merge into the ML dataset, no feature-stack rebuild, no split change, and no model training were performed. **PHASE 1/2/3/3C DATA AND MODELS ARE UNTOUCHED.**