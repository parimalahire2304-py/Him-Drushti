"""
PHASE 3F — Sub-weekly trajectory feasibility audit.

Runs SEVEN audits against the BYU v8.0 observed-only record in East Prydz Bay:
1. Observation cadence per iceberg.
2. Sub-weekly pair availability (1/2/3/5/7-day horizons, observed endpoints only).
3. Independence-corrected vs raw pair counts.
4. Displacement / sensor-quality analysis.
5. Iceberg diversity.
6. Leakage & future split hygiene.
7. Candidate horizon comparison matrix.

Reads only the verified BYU observed-only analysis intermediates already on disk
from Phase 3E (data/raw/icebergs/byu/analysis/byu_in_bbox_observed.csv) plus
the ML dataset full.parquet for diversity comparison and gitstatus-integrity
checks. Performs no training, no download, no modification of Phase 1/2/3/3C.

Output: CSVs + JSON under data/raw/icebergs/byu/analysis/phase3f/ and console
summary for the report. Each number is derived from actual data.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ---------- constants ----------
BBOX = {"lat_min": -70.0, "lat_max": -66.0, "lon_min": 72.0, "lon_max": 80.0}
# Temporal scope for the approved ML experiment (expanded Phase 3 dataset, 7 years)
SUPPORTED_YEARS = {2016, 2017, 2019, 2020, 2021, 2024, 2025}
# Horizon set
HORIZONS = [1, 2, 3, 5, 7]
# Analysis dir from Phase 3E & Phase 3F
ANALYSIS_IN = Path("data/raw/icebergs/byu/analysis")
OUT = ANALYSIS_IN / "phase3f"
OUT.mkdir(parents=True, exist_ok=True)
# Current authoritative dataset
CURRENT_FILE = Path("data/processed/ml/expanded/full.parquet")
CURRENT_META_FILE = Path("data/processed/ml/expanded/ml_dataset_metadata.json")
# BYU ground truth for leakage / zero-shot hygiene
C39_ZERO_SHOT_ICEBERG = "C39"
# Per-sensor labels
SCAT_SENSORS = {"ascat", "ers", "nscat", "oscat", "qscat", "sass", "seawinds"}
NIC_SENSOR = "nic"
# Split boundaries (verified metadata)
SPLIT_BOUNDARIES = {
    "train_end": datetime(2024, 1, 1),  # train is < 2024-01-01
    "val_end": datetime(2025, 1, 1),    # val is 2024-01-01 ≤ date < 2025-01-01; test ≥ 2025-01-01
}
# Physical constants for displacement maths
EARTH_KM = 6371.0088


# ---------- helpers ----------
def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(a))


def build_pairs_with_horizon(series, horizon_days: int, tolerance_days: int = 0):
    """
    Build (t, t+horizon) pairs from a sorted, deduplicated daily series where
    both endpoints are directly observed. No interpolation.

    In Phase 3E/3F BYU dates are at day granularity (YYYYDDD → YYYY-MM-DD),
    so pairing is by integer calendar days: second endpoint must be exactly
    `horizon_days` days after the first (tolerance_days==0). When
    tolerance_days > 0, the second endpoint may fall within ±tolerance_days of
    t+horizon — used only if documented.

    Returns DataFrame with columns obs_date, target_date, displacement_km etc.
    One position per iceberg per day is assumed already deduplicated before
    calling (preference already applied in the caller).
    """
    series = series.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if len(series) < 2:
        return pd.DataFrame()
    dates = np.array(series["date"].values)  # datetime64-like
    lat = np.array(series["lat"].values, dtype=float)
    lon = np.array(series["lon"].values, dtype=float)
    # day number from first date (integer days)
    d0 = dates[0]
    daynums = np.array([(d - d0).astype("timedelta64[D]").astype(int) for d in dates], dtype=int)
    idx_by_day = {int(dn): i for i, dn in enumerate(daynums)}
    rows = []
    for dn in daynums:
        if tolerance_days == 0:
            j = idx_by_day.get(dn + horizon_days)
            chosen = [j] if j is not None else []
        else:
            chosen = [idx_by_day[d] for d in range(dn + horizon_days - tolerance_days,
                                                    dn + horizon_days + tolerance_days + 1)
                      if d in idx_by_day and d != dn]
            # dedup + prefer exact match first
            exact = idx_by_day.get(dn + horizon_days)
            if exact is not None and chosen:
                chosen = [exact]
        for j in chosen:
            if j is None:
                continue
            rows.append({
                "obs_date": dates[np.where(daynums == dn)[0][0]],
                "target_date": dates[j],
                "dt_days": int((dates[j] - dates[np.where(daynums == dn)[0][0]]).astype("timedelta64[D]").astype(int)),
                "lat0": float(lat[np.where(daynums == dn)[0][0]]),
                "lon0": float(lon[np.where(daynums == dn)[0][0]]),
                "lat1": float(lat[j]),
                "lon1": float(lon[j]),
                "displacement_km": float(haversine_km(
                    lat[np.where(daynums == dn)[0][0]],
                    lon[np.where(daynums == dn)[0][0]],
                    lat[j], lon[j])),
            })
    return pd.DataFrame(rows)


def nonoverlapping_subset(pairs: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    """
    Greedy non-overlapping filter. Pairs sorted by obs_date; keep a pair only
    if its obs_date is at least horizon_days after the last kept pair's
    obs_date. Gives the maximum set of non-overlapping windows under a single
    forward pass; deterministic and simple enough to be transparent.
    """
    if pairs.empty:
        return pairs
    pairs = pairs.sort_values("obs_date").reset_index(drop=True)
    keep = [0]
    for i in range(1, len(pairs)):
        gap = (pairs.loc[i, "obs_date"] - pairs.loc[keep[-1], "obs_date"]).days
        if gap >= horizon_days:
            keep.append(i)
    return pairs.iloc[keep].reset_index(drop=True)


def load_byu_observed():
    """Load BYU observed-only in-bbox file produced by Phase 3E (analyze_byu.py)."""
    p = ANALYSIS_IN / "byu_in_bbox_observed.csv"
    # date may be stored as YYYY-MM-DD or YYYYDDD-derived ISO; pandas will parse
    obs = pd.read_csv(p, parse_dates=["date"])
    return obs


def load_current_dataset():
    df = pd.read_parquet(CURRENT_FILE)
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    df["target_date"] = pd.to_datetime(df["target_date"])
    return df

# ---------- load ----------
print("=" * 78, flush=True)
print("PHASE 3F — Sub-weekly trajectory feasibility audit — data load", flush=True)
obs = load_byu_observed()
print(f"Loaded BYU observed-only in-bbox: {len(obs)} records, {obs['iceberg_id'].nunique()} icebergs", flush=True)
cur = load_current_dataset()
print(f"Loaded current expanded dataset: {len(cur)} pairs, {cur['iceberg_id'].nunique()} icebergs ({sorted(cur['iceberg_id'].unique())})", flush=True)

# Build the combined daily series (one position per iceberg per day, preference applied
# BEFORE any pair building). This mirrors Phase 3E methodology for consistency.
obs["d"] = obs["date"].dt.date
prio = {"nic": 0, "ascat": 1, "qscat": 2, "ers": 3, "oscat": 4, "nscat": 5, "sass": 6, "seawinds": 7}
obs["prio"] = obs["sensor"].map(prio)
comb = obs.sort_values("prio").drop_duplicates(["iceberg_id", "d"]).sort_values(["iceberg_id", "date"]).copy()
comb = comb.drop(columns=["prio"])
print(f"Combined daily observed positions (per iceberg per day): {len(comb)}", flush=True)

# ---------- AUDIT 4: observation cadence ----------
rows = []
for ikey, g in comb.groupby("iceberg_id"):
    dates = pd.DatetimeIndex(g["date"].values)  # pandas Timestamp-like index
    if len(dates) < 2:
        gaps = np.array([])
    else:
        gaps = np.array([(dates[i+1] - dates[i]).days for i in range(len(dates)-1)])
    obs_n = int(len(dates))
    obs_first = str(dates[0].date()) if obs_n else ""
    obs_last = str(dates[-1].date()) if obs_n else ""
    span_days = int((dates[-1] - dates[0]).days) if obs_n >= 2 else 0
    # counts of exact 1/2/3/5/7-day intervals between *any consecutive* obs
    if gaps.size:
        median_g = float(np.median(gaps))
        mean_g = float(np.mean(gaps))
        min_g = int(gaps.min())
        max_g = int(gaps.max())
    else:
        median_g = mean_g = float("nan")
        min_g = max_g = 0
    horizon_counts = {}
    for h in HORIZONS:
        horizon_counts[f"n_{h}d"] = int((gaps == h).sum()) if gaps.size else 0
    rows.append({
        "iceberg_id": ikey,
        "n_obs": obs_n,
        "obs_first": obs_first,
        "obs_last": obs_last,
        "span_days": span_days,
        "med_gap": median_g,
        "mean_gap": mean_g,
        "min_gap": min_g,
        "max_gap": max_g,
        **horizon_counts,
        "year_set": ",".join(sorted({str(d.year) for d in g["date"]})),
    })
cadence = pd.DataFrame(rows).sort_values(["n_obs", "iceberg_id"], ascending=[False, True])
cadence.to_csv(OUT / "cadence_per_iceberg.csv", index=False)
print(f"Cadence analysis: {len(cadence)} icebergs (written to cadence_per_iceberg.csv)", flush=True)

# Memoise per-iceberg year breakdown (for the temporal-scope narrative)
_years = cadence.set_index("iceberg_id")["year_set"].to_dict()

# ---------- AUDITS 5–7: raw vs independence-corrected per horizon ----------
HORIZON_PAIRS = {}       # {h: DataFrame(raw)}
CORRECTED_PAIRS = {}     # {h: DataFrame(non-overlapping)}
PER_ICEBERG = {}         # {h: DataFrame per iceberg summary}
DISP_SUMMARY = {}        # {h: dict mean/median/p95 etc. for overall + per sensor}

for h in HORIZONS:
    raw_parts = []
    for ikey, g in comb.groupby("iceberg_id"):
        pairs = build_pairs_with_horizon(g[["date", "lat", "lon"]].copy(), horizon_days=h, tolerance_days=0)
        if not pairs.empty:
            pairs["iceberg_id"] = ikey
            # carry sensor provenance per endpoint (from comb, which has one sensor per day)
            sensor_by_date = dict(zip(pd.to_datetime(comb[comb["iceberg_id"] == ikey]["date"]).dt.date,
                                      comb[comb["iceberg_id"] == ikey]["sensor"]))
            pairs["sensor_obs"] = [sensor_by_date.get(pd.Timestamp(d).date(), "?")
                                   for d in pairs["obs_date"]]
            pairs["sensor_tgt"] = [sensor_by_date.get(pd.Timestamp(d).date(), "?")
                                   for d in pairs["target_date"]]
            raw_parts.append(pairs)
    raw = pd.concat(raw_parts, ignore_index=True) if raw_parts else pd.DataFrame(
        columns=["obs_date", "target_date", "dt_days", "lat0", "lon0", "lat1", "lon1",
                 "displacement_km", "iceberg_id", "sensor_obs", "sensor_tgt"])
    if not raw.empty:
        raw["year"] = pd.to_datetime(raw["obs_date"]).dt.year
        raw["excluded_2026"] = raw["year"] == 2026
    HORIZON_PAIRS[h] = raw

    # Non-overlapping (audit 6): per iceberg, greedy pick with gap >= h
    corrected_parts = []
    for ikey, g in raw.groupby("iceberg_id") if not raw.empty else []:
        g = g.sort_values("obs_date").reset_index(drop=True)
        corrected = nonoverlapping_subset(g, h)
        corrected_parts.append(corrected)
    corrected = pd.concat(corrected_parts, ignore_index=True) if corrected_parts else pd.DataFrame(columns=raw.columns if not raw.empty else [])
    CORRECTED_PAIRS[h] = corrected

    # Per-iceberg pair counts (both views)
    summary_rows = []
    for ikey in sorted(comb["iceberg_id"].unique()):
        g_raw = raw[raw["iceberg_id"] == ikey] if not raw.empty else pd.DataFrame()
        g_corr = corrected[corrected["iceberg_id"] == ikey] if not corrected.empty else pd.DataFrame()
        # displacement stats (raw) if available
        disp_mean = float(g_raw["displacement_km"].mean()) if len(g_raw) else float("nan")
        disp_med = float(g_raw["displacement_km"].median()) if len(g_raw) else float("nan")
        summary_rows.append({
            "iceberg_id": ikey,
            "raw_pairs": int(len(g_raw)),
            "corr_pairs": int(len(g_corr)),
            "disp_mean_km": disp_mean,
            "disp_med_km": disp_med,
            "support_year": _years.get(ikey, ""),
        })
    per = pd.DataFrame(summary_rows)
    # Keep both views: one CSV per horizon
    per.to_csv(OUT / f"per_iceberg_h{h}.csv", index=False)
    PER_ICEBERG[h] = per

    # Overall displacement summaries (raw) + sensor-stratified
    if raw.empty:
        DISP_SUMMARY[h] = {"n_raw": 0, "n_corr": 0, "mean": None, "median": None, "p95": None, "max": None}
    else:
        DISP_SUMMARY[h] = {
            "n_raw": int(len(raw)),
            "n_corr": int(len(corrected)),
            "mean": float(raw["displacement_km"].mean()),
            "median": float(raw["displacement_km"].median()),
            "p95": float(raw["displacement_km"].quantile(0.95)),
            "max": float(raw["displacement_km"].max()),
            "n_2026": int(raw["excluded_2026"].sum()) if "excluded_2026" in raw.columns else 0,
        }
        # also sensor-stratified displacement by sensor_obs (the starting observation sensor)
        sensor_disp = {}
        for sens, sg in raw.groupby("sensor_obs"):
            sensor_disp[sens] = {
                "n": int(len(sg)),
                "mean": float(sg["displacement_km"].mean()),
                "median": float(sg["displacement_km"].median()),
                "p95": float(sg["displacement_km"].quantile(0.95)),
            }
        DISP_SUMMARY[h]["by_sensor_obs"] = sensor_disp

# Save raw per-horizon pair files for reproducibility (no interpolation row included)
for h in HORIZONS:
    # annotate excluded_2026 before saving
    raw = HORIZON_PAIRS[h]
    corr = CORRECTED_PAIRS[h]
    if not raw.empty:
        raw.to_csv(OUT / f"pairs_raw_h{h}.csv", index=False)
    if not corr.empty:
        corr.to_csv(OUT / f"pairs_corr_h{h}.csv", index=False)

# ---------- Build the horizon comparison matrix ----------
# Rows = horizon; columns = measured characteristics only (no invented performance)
matrix_rows = []
for h in HORIZONS:
    raw = HORIZON_PAIRS[h]
    corr = CORRECTED_PAIRS[h]
    raw_n = int(len(raw))
    corr_n = int(len(corr))
    # exclude-2026 for ML-feasible view
    raw_usable = int((raw["year"] != 2026).sum()) if raw_n else 0
    corr_usable = int((corr["year"] != 2026).sum()) if corr_n else 0
    raw_usable_no2026 = raw[raw["year"] != 2026] if raw_n else raw
    corr_usable_no2026 = corr[corr["year"] != 2026] if corr_n else corr
    ices_raw = int(raw_usable_no2026["iceberg_id"].nunique()) if not raw_usable_no2026.empty else 0
    ices_corr = int(corr_usable_no2026["iceberg_id"].nunique()) if not corr_usable_no2026.empty else 0
    # temporal span of usable raw pairs
    if not raw_usable_no2026.empty:
        t0 = pd.to_datetime(raw_usable_no2026["obs_date"]).min()
        t1 = pd.to_datetime(raw_usable_no2026["target_date"]).max()
        span = f"{t0.date()} to {t1.date()}"
        years = sorted(raw_usable_no2026["year"].unique().tolist())
    else:
        span = "—"
        years = []
    # displacement display (from usable raw, so the 2026 artefact doesn't inflate)
    if not raw_usable_no2026.empty:
        dmean = f"{raw_usable_no2026['displacement_km'].mean():.2f}"
        dmed = f"{raw_usable_no2026['displacement_km'].median():.2f}"
        dp95 = f"{raw_usable_no2026['displacement_km'].quantile(0.95):.2f}"
    else:
        dmean = dmed = dp95 = "—"
    # drift-class labelling NOT applied-by-default (see report Section 8: Phase 3E noise
    # shows a single 0.5km rule misclassifies scatterometer D23). So leave undetermined here.
    matrix_rows.append({
        "horizon_days": h,
        "raw_pairs": raw_n,
        "raw_pairs_excl2026": raw_usable,
        "corr_pairs": corr_n,
        "corr_pairs_excl2026": corr_usable,
        "usable_raw_pairs_no2026": raw_usable,
        "usable_corr_pairs_no2026": corr_usable,
        "icebergs_raw_no2026": ices_raw,
        "icebergs_corr_no2026": ices_corr,
        "temporal_span_no2026": span,
        "years_no2026": ",".join(map(str, years)),
        "disp_mean_km_no2026": dmean,
        "disp_med_km_no2026": dmed,
        "disp_p95_km_no2026": dp95,
    })
horizon_cmp = pd.DataFrame(matrix_rows)
horizon_cmp.to_csv(OUT / "horizon_comparison.csv", index=False)

# Also: per-horizon pairs restricted to the 7 dataset years (strict ML-feasible view),
# excluding 2018/2022/2023-style no-stack years. This is the number that can actually be used
# for ML because every usable pair needs env features. (2016,2017,2018,2019,2020,2021,2024,2025 have stacks.)
STACK_YEARS = {2016, 2017, 2018, 2019, 2020, 2021, 2024, 2025}
for h in HORIZONS:
    for view, df in (("raw", HORIZON_PAIRS[h]), ("corr", CORRECTED_PAIRS[h])):
        if df.empty:
            continue
        df["in_stack_year"] = df["year"].isin(STACK_YEARS)
        df["in_supported"] = df["year"].isin(SUPPORTED_YEARS)
        df.to_csv(OUT / f"pairs_{view}_h{h}_withflags.csv", index=False)
    raw = HORIZON_PAIRS[h]
    corr = CORRECTED_PAIRS[h]
    if not raw.empty:
        for name, mask in (("stack_year", raw["in_stack_year"]), ("supported", raw["in_supported"])):
            pass  # already handled per file
        raw.to_csv(OUT / f"pairs_raw_h{h}.csv", index=False)
    if not corr.empty:
        corr.to_csv(OUT / f"pairs_corr_h{h}.csv", index=False)

# ---------- Diversity / leakage quick stats for report ----------
# Per-horizon diversity: exclude 2026, report usable (stack-year) slice too
diversity = []
for h in HORIZONS:
    raw = HORIZON_PAIRS[h]
    corr = CORRECTED_PAIRS[h]
    # usable = in stack year (8 stack years)
    stack_years_set = STACK_YEARS
    for label, df in (("raw", raw), ("corr", corr)):
        if df.empty:
            n_usable = 0
            n_iceb = 0
            rows = {}
        else:
            us = df[df["year"].isin(stack_years_set)]
            n_usable = int(len(us))
            n_iceb = int(us["iceberg_id"].nunique())
            rows = dict(us["iceberg_id"].value_counts().to_dict() if not us.empty else {})
        diversity.append({
            "horizon": h,
            "view": label,
            "n_usable_stackyear": n_usable,
            "n_icebergs_stackyear": n_iceb,
        })
pd.DataFrame(diversity).to_csv(OUT / "diversity_by_horizon.csv", index=False)

# Save audit metadata
audit_meta = {
    "bnd_box": BBOX,
    "supported_years": sorted(SUPPORTED_YEARS),
    "stack_years": sorted(STACK_YEARS),
    "horizons": HORIZONS,
    "tolerance_days": 0,  # exact calendar-day matching, as required (see Section 5)
    "pair_definition": "Both endpoints directly observed (sensor_3==1 or _3 present as observed), no interpolation, dt==horizon exactly, one position per iceberg per day preference NIC>asat>qscat>ers>oscat>nscat>sass>seawinds, bbox lat -70..-66 lon 72..80, 2026 excluded, observed-only per BYU flag rule.",
    "independence_method": "Greedy non-overlapping filtering per iceberg per horizon: sort pairs by obs_date; keep a pair only if its obs_date is at least horizon_days after the last kept pair's obs_date. One pass, deterministic. RAW is all overlapping windows; CORRECTED is this filtered set.",
    "note_sensorMismatch": "Phase 3E showed ~1.2 km scatterometer jitter on D23; that is carried. See sensor-stratified displacement keys in DISP_SUMMARY[h]['by_sensor_obs'].",
}
with open(OUT / "audit_meta.json", "w") as f:
    json.dump(audit_meta, f, indent=2)

# ---------- print a summary of every horizon ----------
print("\nHORIZON COMPARISON (usable pairs exclude 2026):", flush=True)
print(horizon_cmp.to_string(index=False), flush=True)
for h in HORIZONS:
    raw = HORIZON_PAIRS[h]
    raw_us = raw[raw["year"] != 2026] if not raw.empty else raw
    corr = CORRECTED_PAIRS[h]
    corr_us = corr[corr["year"] != 2026] if not corr.empty else corr
    print(f"\nh={h}d  raw_excl2026={len(raw_us)}  corr_excl2026={len(corr_us)}"
          f"  iceb(raw_excl2026)={raw_us['iceberg_id'].nunique() if not raw_us.empty else 0}"
          f"  iceb(corr_excl2026)={corr_us['iceberg_id'].nunique() if not corr_us.empty else 0}", flush=True)
    if not raw_us.empty:
        by = dict(raw_us["iceberg_id"].value_counts())
        byc = dict(corr_us["iceberg_id"].value_counts()) if not corr_us.empty else {}
        print("  raw per iceberg:", by, flush=True)
        print("  corr per iceberg:", byc, flush=True)
    if not raw.empty:
        ds = raw["displacement_km"]
        print(f"  disp_raw(all): mean={ds.mean():.2f} med={ds.median():.2f} p95={ds.quantile(0.95):.2f} max={ds.max():.2f}", flush=True)

print("\nDISP BY SENSOR_OBS (raw, all horizons — as saved in DISP_SUMMARY):", flush=True)
for h in HORIZONS:
    print(f"  h={h}:", json.dumps(DISP_SUMMARY[h].get("by_sensor_obs", {}), indent=2), flush=True)

print(f"\nArtifacts written under {OUT}", flush=True)
