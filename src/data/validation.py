"""
Dataset validation framework for Phase 1.

Provides structured validation checks for every acquired dataset.
Reports quality problems clearly — never silently drops bad records.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    """Accumulates validation results for a single dataset."""

    dataset_name: str
    file_path: str
    checks: list[dict[str, Any]] = field(default_factory=list)

    # Summary counters
    records_before_filtering: int | None = None
    records_after_filtering: int | None = None

    def add_check(
        self,
        name: str,
        passed: bool,
        detail: str,
        severity: str = "INFO",
    ) -> None:
        """Record a single validation check."""
        self.checks.append(
            {
                "name": name,
                "passed": passed,
                "detail": detail,
                "severity": severity,
            }
        )
        level = logging.WARNING if severity == "WARNING" else logging.INFO
        status = "PASS" if passed else "FAIL"
        logger.log(level, "[%s] %s: %s — %s", self.dataset_name, status, name, detail)

    @property
    def all_passed(self) -> bool:
        """True if every check passed."""
        return all(c["passed"] for c in self.checks)

    @property
    def failed_checks(self) -> list[dict[str, Any]]:
        """Return only the failed checks."""
        return [c for c in self.checks if not c["passed"]]

    def summary(self) -> str:
        """Return a human-readable summary."""
        total = len(self.checks)
        failed = len(self.failed_checks)
        lines = [
            f"=== Validation Report: {self.dataset_name} ===",
            f"File: {self.file_path}",
            f"Checks: {total} total, {total - failed} passed, {failed} failed",
        ]
        if self.records_before_filtering is not None:
            lines.append(
                f"Records before filtering: {self.records_before_filtering:,}"
            )
        if self.records_after_filtering is not None:
            lines.append(
                f"Records after filtering:  {self.records_after_filtering:,}"
            )
        for c in self.checks:
            mark = "✓" if c["passed"] else "✗"
            lines.append(f"  {mark} [{c['severity']}] {c['name']}: {c['detail']}")
        return "\n".join(lines)


def validate_file_exists(report: ValidationReport, path: Path) -> bool:
    """Check 1: File exists on disk."""
    exists = path.is_file()
    report.add_check(
        name="File exists",
        passed=exists,
        detail=str(path),
        severity="CRITICAL" if not exists else "INFO",
    )
    return exists


def validate_file_readable(report: ValidationReport, path: Path) -> bool:
    """Check 2: File can be opened for reading."""
    try:
        with open(path, "rb") as fh:
            fh.read(1)
        report.add_check(name="File readable", passed=True, detail="OK")
        return True
    except Exception as exc:
        report.add_check(
            name="File readable",
            passed=False,
            detail=str(exc),
            severity="CRITICAL",
        )
        return False


def validate_columns_exist(
    report: ValidationReport,
    columns: list[str],
    available: list[str],
) -> bool:
    """Check 3: Required fields/columns are present."""
    missing = [c for c in columns if c not in available]
    passed = len(missing) == 0
    report.add_check(
        name="Required columns present",
        passed=passed,
        detail=f"Missing: {missing}" if missing else "All present",
        severity="CRITICAL" if not passed else "INFO",
    )
    return passed


def validate_lat_lon_range(
    report: ValidationReport,
    lat_values: Any,
    lon_values: Any,
) -> None:
    """Check 5: Latitude and longitude are within valid ranges."""
    import numpy as np

    lat = np.asarray(lat_values, dtype=float)
    lon = np.asarray(lon_values, dtype=float)

    lat_valid = np.all(np.isfinite(lat)) and np.all(lat >= -90) and np.all(lat <= 90)
    lon_valid = np.all(np.isfinite(lon)) and np.all(lon >= -180) and np.all(lon <= 180)

    report.add_check(
        name="Latitude range valid",
        passed=lat_valid,
        detail=f"min={np.nanmin(lat):.4f}, max={np.nanmax(lat):.4f}",
    )
    report.add_check(
        name="Longitude range valid",
        passed=lon_valid,
        detail=f"min={np.nanmin(lon):.4f}, max={np.nanmax(lon):.4f}",
    )


def validate_missing_values(
    report: ValidationReport,
    column_name: str,
    values: Any,
    total_records: int,
) -> int:
    """Check 7: Report number of missing values in a column."""
    import numpy as np

    arr = np.asarray(values)
    n_missing = int(np.sum(np.isnan(arr.astype(float))))
    pct = (n_missing / total_records * 100) if total_records > 0 else 0.0
    report.add_check(
        name=f"Missing values: {column_name}",
        passed=True,  # informational
        detail=f"{n_missing:,} missing ({pct:.1f}% of {total_records:,})",
        severity="WARNING" if pct > 10 else "INFO",
    )
    return n_missing


def validate_duplicates(
    report: ValidationReport,
    df: Any,
    subset: list[str] | None = None,
) -> int:
    """Check 8: Report number of duplicate records."""
    n_dup = int(df.duplicated(subset=subset).sum())
    total = len(df)
    pct = (n_dup / total * 100) if total > 0 else 0.0
    report.add_check(
        name="Duplicate records",
        passed=True,  # informational
        detail=f"{n_dup:,} duplicates ({pct:.1f}% of {total:,})",
        severity="WARNING" if pct > 5 else "INFO",
    )
    return n_dup


def validate_spatial_extent(
    report: ValidationReport,
    lat_values: Any,
    lon_values: Any,
) -> None:
    """Check 9: Report spatial extent of the data."""
    import numpy as np

    lat = np.asarray(lat_values, dtype=float)
    lon = np.asarray(lon_values, dtype=float)
    report.add_check(
        name="Spatial extent",
        passed=True,
        detail=(
            f"Lat: [{np.nanmin(lat):.4f}, {np.nanmax(lat):.4f}], "
            f"Lon: [{np.nanmin(lon):.4f}, {np.nanmax(lon):.4f}]"
        ),
    )


def validate_temporal_extent(
    report: ValidationReport,
    timestamps: Any,
    column_name: str = "timestamp",
) -> None:
    """Check 10: Report temporal extent of the data."""
    import pandas as pd

    ts = pd.to_datetime(timestamps, errors="coerce")
    valid_ts = ts.dropna()
    if len(valid_ts) == 0:
        report.add_check(
            name="Temporal extent",
            passed=False,
            detail="No valid timestamps found",
            severity="WARNING",
        )
    else:
        report.add_check(
            name="Temporal extent",
            passed=True,
            detail=f"{column_name}: [{valid_ts.min()} to {valid_ts.max()}]",
        )
