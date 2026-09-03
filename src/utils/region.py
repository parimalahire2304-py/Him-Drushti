"""
Region configuration loader for Prototype-1.

Loads the East Prydz Bay bounding box and related parameters
from config/region.yaml. All spatial filtering in the pipeline
should use this module to stay consistent with the configured region.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "region.yaml"


@dataclass(frozen=True)
class BoundingBox:
    """Geographic bounding box in degrees (WGS 84)."""

    south: float
    north: float
    west: float
    east: float

    def contains_point(self, lat: float, lon: float) -> bool:
        """Check if a latitude/longitude point falls inside this box."""
        return (
            self.south <= lat <= self.north
            and self.west <= lon <= self.east
        )

    def overlaps(self, other: "BoundingBox") -> bool:
        """Check whether two bounding boxes overlap."""
        return not (
            self.north < other.south
            or self.south > other.north
            or self.east < other.west
            or self.west > other.east
        )


@dataclass(frozen=True)
class RegionConfig:
    """Full region configuration loaded from YAML."""

    region_name: str
    country_or_region: str
    bounding_box: BoundingBox
    coordinate_reference_system: str
    timezone: str
    default_forecast_horizon_hours: int


def load_region(config_path: Path | str | None = None) -> RegionConfig:
    """
    Load region configuration from a YAML file.

    Parameters
    ----------
    config_path : Path or str, optional
        Path to region.yaml. Defaults to config/region.yaml at the
        project root.

    Returns
    -------
    RegionConfig
        Parsed region configuration.
    """
    path = Path(config_path) if config_path else _DEFAULT_CONFIG

    if not path.exists():
        raise FileNotFoundError(f"Region config not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    bb_raw = raw["bounding_box"]
    bb = BoundingBox(
        south=float(bb_raw["south"]),
        north=float(bb_raw["north"]),
        west=float(bb_raw["west"]),
        east=float(bb_raw["east"]),
    )

    return RegionConfig(
        region_name=raw["region_name"],
        country_or_region=raw["country_or_region"],
        bounding_box=bb,
        coordinate_reference_system=raw["coordinate_reference_system"],
        timezone=raw["timezone"],
        default_forecast_horizon_hours=int(raw["default_forecast_horizon_hours"]),
    )
