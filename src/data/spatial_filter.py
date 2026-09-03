"""
Spatial filtering for the Prototype-1 East Prydz Bay region.

All spatial subsetting reads the bounding box from config/region.yaml
via src.utils.region, so the operational area is never hard-coded.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from src.utils.region import BoundingBox, load_region

logger = logging.getLogger(__name__)


def load_bounding_box(config_path: Path | str | None = None) -> BoundingBox:
    """Load the Prototype-1 bounding box from configuration."""
    region = load_region(config_path)
    return region.bounding_box


def filter_points_to_bbox(
    lats: Any,
    lons: Any,
    bbox: BoundingBox | None = None,
    config_path: Path | str | None = None,
) -> np.ndarray:
    """
    Return a boolean mask for points that fall inside the bounding box.

    Parameters
    ----------
    lats : array-like
        Latitude values in degrees.
    lons : array-like
        Longitude values in degrees.
    bbox : BoundingBox, optional
        If provided, use this directly instead of loading from config.
    config_path : Path or str, optional
        Path to region.yaml if loading from config.

    Returns
    -------
    np.ndarray of bool
        True where the point is inside the bounding box.
    """
    if bbox is None:
        bbox = load_bounding_box(config_path)

    lat = np.asarray(lats, dtype=float)
    lon = np.asarray(lons, dtype=float)

    if lat.shape != lon.shape:
        raise ValueError(
            f"Shape mismatch: lats {lat.shape} vs lons {lon.shape}"
        )

    mask = (
        (lat >= bbox.south)
        & (lat <= bbox.north)
        & (lon >= bbox.west)
        & (lon <= bbox.east)
    )

    n_total = lat.size
    n_kept = int(mask.sum())
    logger.info(
        "Spatial filter: %d / %d records inside bbox "
        "(S=%.1f N=%.1f W=%.1f E=%.1f)",
        n_kept,
        n_total,
        bbox.south,
        bbox.north,
        bbox.west,
        bbox.east,
    )
    return mask
