"""
PHASE 3E (cont.) — Build 7-day pairs from BYU observed-only daily trajectories,
classify drifting/grounded using the project's exact 0.5 km mean-7-day-
displacement threshold, restrict to supported feature-stack years, and
separate NIC (dedup) vs scatterometer (new) contributions.

Acquisition + verification only. Does NOT merge into ML dataset or train models.
"""
import json
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_byu import (
    ANALYSIS, DRIFT_THRESHOLD_KM_7D, haversine_km, jd_to_date, SENSOR_COLS,
)

# Supported feature-stack years in the expanded ML dataset (7 stacks; 2018 exists
# but was excluded as D23-only non-drifting). 2022/2023/2026 have no stacks.
SUPPORTED_YEARS = {2016, 2017, 2019, 2020, 2021, 2024, 2025}
# 2018 stack exists; count separately but flag as not-in-dataset.
STACK_YEARS_EXISTS = {2016, 2017, 2018, 2019, 2020, 2021, 2024, 2025}

# Icebergs already in the expanded 451-pair dataset (dedup identity).
CURRENT_ICEBERGS = {"B39", "C18B", "C39", "D21B", "D22", "D23", "D27", "D28"}

SCATTEROMETER_SENSORS = {"ascat", "ers", "nscat", "oscat", "qscat", "sass", "seawinds"}


def load_observed():
    obs = pd.read_csv(os.path.join(ANALYSIS, "byu_in_bbox_observed.csv"),
                      parse_dates=["date"])
    return obs


def build_pairs_for_iceberg(series, dt_days=7):
    """Given a sorted, deduped daily series of (date, lat, lon), build all
    observation pairs separated by exactly dt_days, returning per-pair rows.

    Uses the project methodology: a valid pair requires observations at t and
    t+dt_days both present (no interpolation, no gap-filling).
    """
    s = series.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates = s["date"].values
    lat = s["lat"].values
    lon = s["lon"].values
    rows = []
    # map each date to its day-number for fast lookup
    day0 = dates[0]
    daynums = np.array([(d - day0) / np.timedelta64(1, "D") for d in dates], dtype=int)
    idx_by_day = {int(dn): i for i, dn in enumerate(daynums)}
    for i, dn in enumerate(daynums):
        j = idx_by_day.get(dn + dt_days)
        if j is None:
            continue
        d0 = dates[i]
        rows.append({
            "obs_date": d0,
            "target_date": dates[j],
            "dt_days": dt_days,
            "lat0": lat[i], "lon0": lon[i],
            "lat1": lat[j], "lon1": lon[j],
            "displacement_km": float(haversine_km(lat[i], lon[i], lat[j], lon[j])),
        })
    return pd.DataFrame(rows)


def main():
    obs = load_observed()
    obs["year"] = obs["date"].dt.year

    print("=" * 78)
    print("STEP 6-7: 7-DAY PAIR BUILDING + DRIFT CLASSIFICATION (observed-only)")
    print("=" * 78)

    # Build a combined trajectory per iceberg from ALL observed sensors,
    # preferring NIC for identity (dedup) but combining independent scatterometer
    # sensors as distinct daily positions. To avoid double-counting the same
    # physical position from two sensors on the same day, take one position per
    # iceberg per day: prefer NIC if present, else the scatterometer sensor.
    # (A single daily position per iceberg avoids inflating counts.)
    rows = []
    for ikey, g in obs.groupby("iceberg_id"):
        # one position per day: priority NIC > ascat > qscat > ers > oscat > nscat > sass > seawinds
        prio = {"nic": 0, "ascat": 1, "qscat": 2, "ers": 3, "oscat": 4,
                "nscat": 5, "sass": 6, "seawinds": 7}
        g = g.copy()
        g["prio"] = g["sensor"].map(prio)
        g = g.sort_values("prio").drop_duplicates("date", keep="first")
        g = g.sort_values("date")
        rows.append(g)
    comb = pd.concat(rows)
    comb = comb.drop(columns=["prio"])

    print("Combined daily observed positions (per iceberg per day):", len(comb))
    print("Sensors retained after per-day merge:")
    print(comb["sensor"].value_counts().head(10))

    # Build pairs per iceberg
    results = []
    pair_rows = []
    for ikey, g in comb.groupby("iceberg_id"):
        pairs = build_pairs_for_iceberg(g[["date", "lat", "lon"]])
        if pairs.empty:
            results.append({
                "iceberg_id": ikey, "n_obs_days": int(g["date"].nunique()),
                "n_pairs_all": 0, "n_pairs_supported": 0,
                "mean_7d_disp_km": None, "drift_class": "INSUFFICIENT",
            })
            continue
        mean_disp = pairs["displacement_km"].mean()
        drift_class = "GROUNDED" if mean_disp <= DRIFT_THRESHOLD_KM_7D else "DRIFTING"
        # supported-year pairs
        sup = pairs[pairs["obs_date"].dt.year.isin(SUPPORTED_YEARS)]
        results.append({
            "iceberg_id": ikey,
            "n_obs_days": int(g["date"].nunique()),
            "n_pairs_all": int(len(pairs)),
            "n_pairs_supported": int(len(sup)),
            "mean_7d_disp_km": round(float(mean_disp), 3),
            "drift_class": drift_class,
            "date_first": str(g["date"].min().date()),
            "date_last": str(g["date"].max().date()),
        })
        p = pairs.copy()
        p["iceberg_id"] = ikey
        p["drift_class"] = drift_class
        pair_rows.append(p)

    res = pd.DataFrame(results)
    res.to_csv(os.path.join(ANALYSIS, "byu_iceberg_pairs_summary.csv"), index=False)
    print("\nPer-iceberg pair summary (sorted by supported pairs desc):")
    show = res.sort_values("n_pairs_supported", ascending=False)
    print(show.to_string(index=False))

    if pair_rows:
        allpairs = pd.concat(pair_rows)
        allpairs.to_csv(os.path.join(ANALYSIS, "byu_all_7d_pairs.csv"), index=False)
        # Supported-year pairs only, annotated with current/new status
        sup = allpairs[allpairs["obs_date"].dt.year.isin(SUPPORTED_YEARS)].copy()
        sup["in_current"] = sup["iceberg_id"].isin(CURRENT_ICEBERGS)
        sup.to_csv(os.path.join(ANALYSIS, "byu_supported_pairs.csv"), index=False)

        print("\n=== SUPPORTED-YEAR 7-DAY PAIRS (across 7 dataset years) ===")
        print("Total supported pairs:", len(sup))
        print("By drift class:\n", sup["drift_class"].value_counts())
        print("By in_current:\n", sup["in_current"].value_counts())
        print("\nPairs per iceberg (supported years):")
        pb = sup.pivot_table(index="iceberg_id", columns="drift_class",
                             values="obs_date", aggfunc="count", fill_value=0)
        pb["total"] = pb.sum(axis=1)
        print(pb.sort_values("total", ascending=False).to_string())

        # Which are NEW (not in current set) vs current
        new = sup[~sup["in_current"]]
        cur = sup[sup["in_current"]]
        print("\n=== NEW icebergs (not in current 8) supported pairs ===")
        print("NEW total:", len(new), " NEW drifting:", int((new["drift_class"]=="DRIFTING").sum()),
              " NEW grounded:", int((new["drift_class"]=="GROUNDED").sum()))
        print("CURRENT icebergs supported pairs (scatterometer supplement):",
              len(cur), " drifting:", int((cur["drift_class"]=="DRIFTING").sum()))

        # breakdown by year
        print("\nSupported pairs by year (all / drifting):")
        yr = sup.groupby(sup["obs_date"].dt.year).size()
        yrd = sup[sup["drift_class"] == "DRIFTING"].groupby(sup["obs_date"].dt.year).size()
        print(pd.DataFrame({"all": yr, "drifting": yrd}).to_string())

    # Save summary JSON
    n_sup = int(sup["obs_date"].count()) if pair_rows else 0
    summary = {
        "threshold_km_7d": DRIFT_THRESHOLD_KM_7D,
        "supported_years": sorted(SUPPORTED_YEARS),
        "current_icebergs": sorted(CURRENT_ICEBERGS),
        "n_icebergs_in_bbox": int(res["iceberg_id"].nunique()),
        "n_icebergs_with_supported_pairs": int((res["n_pairs_supported"] > 0).sum()),
        "n_supported_pairs_total": n_sup,
    }
    with open(os.path.join(ANALYSIS, "byu_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print("\nSaved analysis intermediates to", ANALYSIS)


if __name__ == "__main__":
    main()
