#!/usr/bin/env python3
"""
Download the GEBCO gridded bathymetry for the East Prydz Bay region.

The full global GEBCO grid (~7.4 GB) is too large to store locally.
Instead, this script uses the CEDA OPeNDAP server to request only the
East Prydz Bay spatial subset directly (server-side subsetting).

The subset is written to data/processed/bathymetry/.

The raw global grid is NOT downloaded to data/raw/bathymetry/ because
of its size. The subset is derived from GEBCO_2024 via OPeNDAP and is
recorded in DATASETS.md for provenance.

Usage:
    python scripts/data/download_gebco.py
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Ensure the project root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import xarray as xr

from src.utils.region import load_region

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# CEDA OPeNDAP DODS endpoint for the GEBCO_2024 sub-ice topography grid
ODAP_URL = (
    "https://dap.ceda.ac.uk/thredds/dodsC/"
    "bodc/gebco/global/gebco_2024/sub_ice_topography_bathymetry/"
    "netcdf/GEBCO_2024_sub_ice_topo.nc"
)
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "bathymetry"
OUT_FILENAME = "east_prydz_bay_bathymetry_15arcsec.nc"


def main() -> None:
    region = load_region()
    bb = region.bounding_box

    logger.info("Opening GEBCO_2024 grid via OPeNDAP...")
    ds = xr.open_dataset(ODAP_URL, engine="netcdf4")

    logger.info(
        "Subsetting to bbox S=%.1f N=%.1f W=%.1f E=%.1f",
        bb.south,
        bb.north,
        bb.west,
        bb.east,
    )
    sub = ds.sel(lat=slice(bb.south, bb.north), lon=slice(bb.west, bb.east))

    # Preserve only the elevation array + coordinates
    out = sub[["elevation"]].copy()
    out.attrs["source"] = "GEBCO_2024 sub-ice topography grid"
    out.attrs["source_url"] = ODAP_URL
    out.attrs["subset_bounding_box"] = str(bb)
    out.attrs["region_name"] = region.region_name
    out.attrs[
        "description"
    ] = "East Prydz Bay bathymetry subset for Prototype-1 (server-side OPeNDAP subset of global GEBCO_2024)."

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / OUT_FILENAME
    out.to_netcdf(dest)
    logger.info("Saved subset -> %s", dest)
    logger.info("Shape: %s", dict(out.sizes))
    logger.info("Elevation min/max: %d / %d", int(out["elevation"].min()), int(out["elevation"].max()))


if __name__ == "__main__":
    main()