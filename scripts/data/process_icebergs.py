#!/usr/bin/env python3
"""
Combine all US Ice Center Antarctic iceberg position CSVs into a
single processed dataset, with validation and East Prydz Bay spatial filtering.

The raw archive CSVs have two distinct schemas over time:
- Schema 1 (Nov 2014 – Apr 2024): 7 columns including Remarks
- Schema 2 (Apr 2024 – Aug 2026): 9 columns including Area fields

Common columns present in both:
  Iceberg, Length (NM), Width (NM), Latitude, Longitude, Last Update

This script:
  1. Loads each raw CSV (tolerant of formatting issues)
  2. Extracts the common columns
  3. Records which schema each file used
  4. Combines into a single DataFrame
  5. Validates lat/lon, dates, duplicates
  6. Filters to East Prydz Bay bounding box
  7. Saves the result to data/processed/icebergs/
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.region import load_region

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "icebergs"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "icebergs"

COMMON_COLUMNS = ["Iceberg", "Length (NM)", "Width (NM)", "Latitude", "Longitude", "Last Update"]


def combine_raw_files() -> pd.DataFrame:
    """Load all raw iceberg CSVs, extract common columns, combine."""
    raw_files = sorted(RAW_DIR.glob("AntarcticIcebergs_*.csv"))
    logger.info("Found %d raw CSV files in %s", len(raw_files), RAW_DIR)

    frames = []
    for f in raw_files:
        date_str = f.stem.split("_")[-1]  # e.g. 20240125
        try:
            df = pd.read_csv(f, engine="python", on_bad_lines="skip")
        except Exception as e:
            logger.warning("Could not parse %s: %s", f.name, e)
            continue

        # Only keep the common columns that are present
        available = [c for c in COMMON_COLUMNS if c in df.columns]
        missing = [c for c in COMMON_COLUMNS if c not in df.columns]
        if missing:
            logger.debug("File %s missing columns: %s", f.name, missing)
            # Fill missing columns with NaN
            for c in missing:
                df[c] = pd.NA

        df_out = df[COMMON_COLUMNS].copy()
        df_out["observation_date"] = date_str
        df_out["source_file"] = f.name
        df_out["schema_version"] = 1 if "Remarks" in df.columns else 2
        frames.append(df_out)

    combined = pd.concat(frames, ignore_index=True)
    logger.info("Combined %d raw records from %d files", len(combined), len(frames))
    return combined


def validate_and_report(df: pd.DataFrame) -> pd.DataFrame:
    """Run validation checks on the combined DataFrame. Report issues."""
    logger.info("=== Validation Report: Iceberg Tracking Data ===")
    logger.info("Total records: %d", len(df))

    # 3. Required columns exist
    logger.info("Columns present: %s", list(df.columns))

    # 4. Datatypes
    logger.info("Lat dtype: %s, Lon dtype: %s", df["Latitude"].dtype, df["Longitude"].dtype)

    # 5. Lat/Lon validity
    bad_lat = df["Latitude"].isna() | (df["Latitude"] < -90) | (df["Latitude"] > 90)
    bad_lon = df["Longitude"].isna() | (df["Longitude"] < -180) | (df["Longitude"] > 180)
    logger.info("Invalid latitudes: %d", bad_lat.sum())
    logger.info("Invalid longitudes: %d", bad_lon.sum())

    # 6. Temporal validity
    df["_obs_dt"] = pd.to_datetime(df["observation_date"], format="%Y%m%d", errors="coerce")
    bad_date = df["_obs_dt"].isna()
    logger.info("Invalid dates: %d", bad_date.sum())
    if not bad_date.all():
        logger.info(
            "Temporal extent: %s to %s",
            df["_obs_dt"].min(),
            df["_obs_dt"].max(),
        )

    # 7. Missing values per column
    for col in ["Iceberg", "Length (NM)", "Latitude", "Longitude"]:
        n_miss = df[col].isna().sum()
        logger.info("Missing in '%s': %d (%.1f%%)", col, n_miss, n_miss/len(df)*100)

    # 8. Duplicates (same iceberg + same date = should be unique)
    dup_cols = ["Iceberg", "observation_date"]
    n_dup = df.duplicated(subset=dup_cols).sum()
    logger.info("Duplicate (Iceberg + date) records: %d", n_dup)

    # 9. Spatial extent
    logger.info(
        "Spatial extent: Lat [%.4f, %.4f], Lon [%.4f, %.4f]",
        df["Latitude"].min(), df["Latitude"].max(),
        df["Longitude"].min(), df["Longitude"].max(),
    )

    # 10. Unique iceberg count
    n_unique = df["Iceberg"].nunique()
    logger.info("Unique iceberg IDs: %d", n_unique)

    # Schema breakdown
    logger.info(
        "Schema breakdown: v1 (Remarks)=%d, v2 (Area)=%d",
        (df["schema_version"] == 1).sum(),
        (df["schema_version"] == 2).sum(),
    )

    return df


def filter_to_east_prydz(df: pd.DataFrame, config_path: Path | None = None) -> pd.DataFrame:
    """Spatially filter to the East Prydz Bay bounding box."""
    region = load_region(config_path)
    bb = region.bounding_box
    n_before = len(df)

    mask = (
        (df["Latitude"] >= bb.south)
        & (df["Latitude"] <= bb.north)
        & (df["Longitude"] >= bb.west)
        & (df["Longitude"] <= bb.east)
    )
    df_filtered = df[mask].copy()
    n_after = len(df_filtered)

    logger.info("=== East Prydz Bay Spatial Filter ===")
    logger.info("Bounding box: S=%.1f N=%.1f W=%.1f E=%.1f", bb.south, bb.north, bb.west, bb.east)
    logger.info("Records before filtering: %d", n_before)
    logger.info("Records after filtering:  %d", n_after)
    logger.info("Records dropped:          %d (%.1f%%)", n_before - n_after, (n_before - n_after)/n_before*100)

    if n_after > 0:
        logger.info(
            "Filtered spatial extent: Lat [%.4f, %.4f], Lon [%.4f, %.4f]",
            df_filtered["Latitude"].min(), df_filtered["Latitude"].max(),
            df_filtered["Longitude"].min(), df_filtered["Longitude"].max(),
        )
        logger.info(
            "Filtered temporal extent: %s to %s",
            df_filtered["_obs_dt"].min(),
            df_filtered["_obs_dt"].max(),
        )
        logger.info("Unique icebergs in region: %d", df_filtered["Iceberg"].nunique())

    return df_filtered


def save_processed(df: pd.DataFrame) -> Path:
    """Save the processed dataset."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "east_prydz_bay_icebergs.csv"
    df.to_csv(out_path, index=False)
    logger.info("Saved processed dataset -> %s", out_path)
    return out_path


def main() -> None:
    combined = combine_raw_files()
    validated = validate_and_report(combined)
    filtered = filter_to_east_prydz(validated)
    if len(filtered) == 0:
        logger.warning(
            "NO iceberg observations found in the East Prydz Bay bounding box. "
            "This region appears not to have had NIC-tracked icebergs passing through."
        )
    save_processed(filtered)


if __name__ == "__main__":
    main()