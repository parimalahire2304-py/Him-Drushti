"""
PHASE 3E — BYU Antarctic Iceberg Tracking Database analysis
Acquisition + verification only. Does NOT merge into ML dataset, rebuild
stacks, or train any model.

Parses the BYU consolidated database v8.0 (data/raw/icebergs/byu/), extracts
per-sensor positions with their observed/interpolated flags, converts JD dates
to datetime, filters to the East Prydz Bay bbox, applies the observed-only
rule, runs gap QC, classifies drifting/grounded using the project's existing
threshold, deduplicates against NIC, and ranks candidate value.

Reproducible analysis producing JSON/CSV intermediates under
data/raw/icebergs/byu/analysis/ for the report.
"""
import glob
import json
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

RAW = "data/raw/icebergs/byu/updated7_consol"
ANALYSIS = "data/raw/icebergs/byu/analysis"
os.makedirs(ANALYSIS, exist_ok=True)

# East Prydz Bay bbox from config/region.yaml
LAT_MIN, LAT_MAX = -70.0, -66.0
LON_MIN, LON_MAX = 72.0, 80.0

# Project's scientifically approved drifting threshold (Phase 3A Expanded Dataset
# Build Report, Metric 4): "Grounded vs Drifting (mean 7-day displacement
# threshold = 0.5 km)". An iceberg is GROUNDED if its mean 7-day displacement
# <= 0.5 km, DRIFTING otherwise. Reused exactly.
DRIFT_THRESHOLD_KM_7D = 0.5  # km mean 7-day displacement

SENSOR_COLS = {
    "ascat": ("ascat_1", "ascat_2", "ascat_3"),
    "ers": ("ers_1", "ers_2", "ers_3"),
    "nic": ("nic_1", "nic_2", "nic_3"),
    "nscat": ("nscat_1", "nscat_2", "nscat_3"),
    "oscat": ("oscat_1", "oscat_2", "oscat_3"),
    "qscat": ("qscat_1", "qscat_2", "qscat_3"),
    "sass": ("sass_1", "sass_2", "sass_3"),
    "seawinds": ("seawinds_1", "seawinds_2", "seawinds_3"),
}


def jd_to_date(jd):
    """Convert YYYYDDD Julian date to datetime."""
    jd = int(jd)
    year = jd // 1000
    doy = jd % 1000
    return datetime(year, 1, 1) + timedelta(days=doy - 1)


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def load_all():
    rows = []
    files = sorted(glob.glob(os.path.join(RAW, "*.csv")))
    for f in files:
        ikey = os.path.basename(f)[:-4].upper()
        df = pd.read_csv(f, dtype=str)
        df = df.fillna("")
        if "date" not in df.columns:
            continue
        df["date"] = df["date"].astype(int)
        for sensor, (c1, c2, c3) in SENSOR_COLS.items():
            if c1 not in df.columns:
                continue
            lat = pd.to_numeric(df[c1], errors="coerce")
            lon = pd.to_numeric(df[c2], errors="coerce")
            flag = pd.to_numeric(df[c3], errors="coerce")
            for i in range(len(df)):
                if np.isnan(lat[i]) or np.isnan(lon[i]):
                    continue
                # 0,0 = no data sentinel
                if lat[i] == 0 and lon[i] == 0:
                    continue
                rows.append({
                    "iceberg_id": ikey,
                    "date": jd_to_date(df["date"][i]),
                    "sensor": sensor,
                    "lat": float(lat[i]),
                    "lon": float(lon[i]),
                    "obs_flag": int(flag[i]) if not np.isnan(flag[i]) else None,
                })
    out = pd.DataFrame(rows)
    return out


def main():
    df = load_all()
    print("Total position records (all sensors):", len(df))
    print("Records per sensor:\n", df["sensor"].value_counts())
    print("Date range:", df["date"].min(), "to", df["date"].max())

    # --- Filter to bbox (any sensor) ---
    in_bbox = df[
        (df["lat"] >= LAT_MIN) & (df["lat"] <= LAT_MAX)
        & (df["lon"] >= LON_MIN) & (df["lon"] <= LON_MAX)
    ].copy()
    print("\n=== STEP 4: BBOX FILTER ===")
    print("In-bbox records:", len(in_bbox), "of", len(df))
    print("In-bbox icebergs:", sorted(in_bbox["iceberg_id"].unique()))

    # Save full in-bbox records
    in_bbox.to_csv(os.path.join(ANALYSIS, "byu_in_bbox_all_sensors.csv"), index=False)

    # --- STEP 5: Observed-only ---
    obs = in_bbox[in_bbox["obs_flag"] == 1].copy()
    interp = in_bbox[in_bbox["obs_flag"] == 0]
    noflag = in_bbox[in_bbox["obs_flag"].isna()]
    print("\n=== STEP 5: OBSERVED-ONLY RULE ===")
    print("Observed (flag=1):", len(obs))
    print("Interpolated (flag=0):", len(interp))
    print("No-flag records:", len(noflag))
    print("Observed icebergs:", sorted(obs["iceberg_id"].unique()))
    print("Observed records per sensor:\n", obs["sensor"].value_counts())
    print("Interpolated per sensor:\n", interp["sensor"].value_counts())

    obs.to_csv(os.path.join(ANALYSIS, "byu_in_bbox_observed.csv"), index=False)
    interp.to_csv(os.path.join(ANALYSIS, "byu_in_bbox_interpolated.csv"), index=False)

    # Per iceberg / per sensor observed counts
    pivot = obs.pivot_table(index="iceberg_id", columns="sensor",
                            values="lat", aggfunc="count", fill_value=0)
    print("\nObserved counts per iceberg per sensor:\n", pivot)

    # --- STEP 6: Gap QC on observed daily series (per iceberg, per sensor) ---
    print("\n=== STEP 6: GAP QC (observed-only, per iceberg/sensor) ===")
    qc_rows = []
    for (ikey, sensor), g in obs.groupby(["iceberg_id", "sensor"]):
        g = g.sort_values("date").drop_duplicates("date")
        dates = g["date"].values
        if len(dates) < 2:
            continue
        gaps = np.diff([(d - datetime(1970, 1, 1)).days for d in dates])
        qc_rows.append({
            "iceberg_id": ikey, "sensor": sensor, "n_obs": len(dates),
            "n_days_span": int((dates[-1] - dates[0]).days),
            "min_gap": int(gaps.min()), "median_gap": int(np.median(gaps)),
            "max_gap": int(gaps.max()),
            "gaps_gt_7": int((gaps > 7).sum()),
            "date_first": str(dates[0].date()), "date_last": str(dates[-1].date()),
        })
    qc = pd.DataFrame(qc_rows)
    qc.to_csv(os.path.join(ANALYSIS, "byu_gap_qc.csv"), index=False)
    print(qc.to_string(index=False))

    return df, in_bbox, obs


if __name__ == "__main__":
    main()
