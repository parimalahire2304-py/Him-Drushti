"""
Common grid utilities for Phase 2 Step 3 feature assembly.

Defines the target spatial/temporal grid and provides functions to
reproject/resample each source dataset onto it.

Target grid: ERA5 0.25° lat/lon over East Prydz Bay.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

# Variable renaming: CDS short names → project feature names
ERA5_RENAME = {
    "u10": "wind_u_10m",
    "v10": "wind_v_10m",
    "t2m": "temperature_2m",
    "msl": "mean_sea_level_pressure",
    "tp": "total_precipitation",
}

ERA5_UNITS = {
    "wind_u_10m": "m s-1",
    "wind_v_10m": "m s-1",
    "temperature_2m": "K",
    "mean_sea_level_pressure": "Pa",
    "total_precipitation": "m",
}

# Variable renaming: GLORYS short names → project feature names
GLORYS_RENAME = {
    "uo": "ocean_current_u",
    "vo": "ocean_current_v",
    "thetao": "sea_water_potential_temperature",
    "so": "sea_water_salinity",
    "siconc": "sea_ice_concentration_ocean",
    "sithick": "sea_ice_thickness",
    "usi": "sea_ice_velocity_u",
    "vsi": "sea_ice_velocity_v",
    "bottomT": "bottom_temperature",
    "mlotst": "ocean_mixed_layer_depth",
    "zos": "sea_surface_height",
}

GLORYS_UNITS = {
    "ocean_current_u": "m s-1",
    "ocean_current_v": "m s-1",
    "sea_water_potential_temperature": "degC",
    "sea_water_salinity": "PSU",
}


def get_common_grid(era5_path: Path | str | None = None) -> xr.Dataset:
    """
    Return the target common grid as an xarray Dataset with lat/lon coords.

    The grid is defined by the ERA5 processed file — the coarsest forcing
    grid (0.25° lat/lon, 17×33 over East Prydz Bay).

    If *era5_path* is None, the default processed ERA5 file is used.
    """
    if era5_path is None:
        era5_path = (
            Path(__file__).resolve().parents[2]
            / "data" / "processed" / "weather"
            / "east_prydz_bay_era5_2020-01-01_2020-12-31.nc"
        )
    ds = xr.open_dataset(era5_path)

    # Extract the spatial grid only (drop time and other coords)
    lat = ds["latitude"].values  # shape (17,), decreasing: -66.0 → -70.0
    lon = ds["longitude"].values  # shape (33,), increasing: 72.0 → 80.0

    grid = xr.Dataset(
        {"lat": ("lat", lat), "lon": ("lon", lon)},
        attrs={
            "description": "Common 0.25° lat/lon grid for East Prydz Bay feature assembly",
            "lat_range": [float(lat.min()), float(lat.max())],
            "lon_range": [float(lon.min()), float(lon.max())],
            "grid_shape": f"{len(lat)} lat x {len(lon)} lon",
            "resolution_deg": 0.25,
            "crs": "EPSG:4326",
        },
    )
    ds.close()
    logger.info(
        "Common grid: %d lat x %d lon, lat [%.1f, %.1f], lon [%.1f, %.1f]",
        len(lat), len(lon), lat.min(), lat.max(), lon.min(), lon.max(),
    )
    return grid


def reproject_sea_ice(
    sea_ice_path: Path | str,
    target_lat: np.ndarray,
    target_lon: np.ndarray,
) -> xr.DataArray:
    """
    Reproject NSIDC sea-ice concentration from polar-stereo to regular
    lat/lon using nearest-neighbor interpolation, then forward-fill daily
    values to hourly.

    Parameters
    ----------
    sea_ice_path : path to the processed NSIDC NetCDF
    target_lat : 1-D array of target latitudes (e.g. ERA5 lat)
    target_lon : 1-D array of target longitudes (e.g. ERA5 lon)

    Returns
    -------
    xr.DataArray with dims (time, lat, lon), hourly, fraction units.
    """
    from scipy.interpolate import griddata

    ds = xr.open_dataset(sea_ice_path)
    siconc = ds["sea_ice_concentration"]

    # Source auxiliary coordinates (2D: y × x)
    src_lon = ds["lon"].values.ravel()
    src_lat = ds["lat"].values.ravel()
    src_points = np.column_stack([src_lat, src_lon])

    # Target grid points
    tgt_lat_mesh, tgt_lon_mesh = np.meshgrid(target_lat, target_lon, indexing="ij")
    tgt_points = np.column_stack([tgt_lat_mesh.ravel(), tgt_lon_mesh.ravel()])

    # Reproject each timestep via nearest-neighbor
    n_time = siconc.sizes["time"]
    n_lat = len(target_lat)
    n_lon = len(target_lon)
    reprojected = np.full((n_time, n_lat, n_lon), np.nan)

    for t in range(n_time):
        src_vals = siconc.isel(time=t).values.ravel()  # (y*x,)
        valid = np.isfinite(src_vals)
        if valid.sum() == 0:
            continue
        result = griddata(
            src_points[valid],
            src_vals[valid],
            tgt_points,
            method="nearest",
        )
        reprojected[t] = result.reshape(n_lat, n_lon)

    # Re-mask NaN cells (land/coast from source)
    # After nearest-neighbor, some target cells near source edges may pick
    # up flag values. Re-mask any cells that were NaN in the majority of
    # source timesteps (i.e., land cells).
    nan_fraction = np.isnan(reprojected).mean(axis=0)
    land_mask = nan_fraction > 0.5  # >50% NaN across time → permanent land
    reprojected[:, land_mask] = np.nan

    # Build output DataArray on the target grid
    out = xr.DataArray(
        reprojected,
        dims=["time", "lat", "lon"],
        coords={
            "time": siconc["time"].values,
            "lat": target_lat,
            "lon": target_lon,
        },
        attrs={
            "units": "fraction (0.0-1.0)",
            "long_name": "Sea Ice Concentration (NASA Team)",
            "standard_name": "sea_ice_area_fraction",
            "reprojection": "nearest-neighbor (scipy.griddata)",
            "source_crs": "EPSG:3412 (polar stereographic south)",
            "target_crs": "EPSG:4326",
            "flag_values": "NaN = land/coast/pole-hole mask",
        },
    )
    ds.close()

    # Forward-fill daily → hourly over a full-day hourly axis (explicit index
    # so the final day's trailing hours 01:00–23:00 are included; resample()
    # truncates at the last original timestamp).
    import pandas as pd

    first = out.time.values[0]
    last = out.time.values[-1] + pd.Timedelta(hours=23)
    hourly_index = pd.date_range(start=first, end=last, freq="1h")
    out_hourly = out.reindex(time=hourly_index, method="ffill")

    logger.info(
        "Sea ice reprojected: %s daily → %s hourly, nearest-neighbor",
        dict(out.sizes), dict(out_hourly.sizes),
    )
    return out_hourly


def coarsen_bathymetry(
    bathy_path: Path | str,
    target_lat: np.ndarray,
    target_lon: np.ndarray,
) -> xr.DataArray:
    """
    Coarsen GEBCO bathymetry from 15 arc-sec to 0.25° via spatial averaging.

    Uses xarray's coarsen with boundary='trim' to handle non-exact division,
    then reindexes to the exact target grid. Bathymetry is static (no time
    dimension).

    Parameters
    ----------
    bathy_path : path to the processed GEBCO NetCDF
    target_lat : 1-D target latitudes
    target_lon : 1-D target longitudes

    Returns
    -------
    xr.DataArray with dims (lat, lon), values in metres.
    """
    ds = xr.open_dataset(bathy_path)
    elev = ds["elevation"]  # dims: (lat, lon), int16

    # Compute coarsening factors (GEBCO ~0.00417° → 0.25° ≈ 60x)
    src_lat_res = abs(float(elev.lat[1] - elev.lat[0]))
    src_lon_res = abs(float(elev.lon[1] - elev.lon[0]))
    lat_factor = max(1, int(round(0.25 / src_lat_res)))
    lon_factor = max(1, int(round(0.25 / src_lon_res)))

    logger.info(
        "Bathymetry coarsening: lat_factor=%d, lon_factor=%d (%.5f° → 0.25°)",
        lat_factor, lon_factor, src_lat_res,
    )

    # Coarsen with mean (preserves average depth)
    coarsened = elev.coarsen(lat=lat_factor, lon=lon_factor, boundary="trim").mean()

    # Reindex to exact target grid via interpolation
    # The coarsened grid won't align exactly with ERA5, so interpolate
    coarsened_lat = coarsened["lat"].values
    coarsened_lon = coarsened["lon"].values

    # Use xarray interp to map to the exact target coords
    result = coarsened.interp(
        lat=target_lat,
        lon=target_lon,
        method="linear",
    )

    result = result.assign_attrs({
        "units": "m",
        "long_name": "Elevation relative to sea level",
        "standard_name": "height_above_mean_sea_level",
        "resampling": f"spatial mean coarsen ({lat_factor}x{lon_factor}) + linear interp to 0.25°",
        "source_resolution": "15 arc-sec (~450 m)",
        "target_resolution": "0.25° (~31 km)",
        "note": "negative = ocean depth, positive = land elevation",
    })

    ds.close()
    logger.info(
        "Bathymetry coarsened: %s → %s",
        dict(elev.sizes), dict(result.sizes),
    )
    return result


def standardise_era5(era5_path: Path | str) -> xr.Dataset:
    """
    Rename ERA5 coordinates and variables to match the project convention.

    - valid_time → time
    - latitude → lat
    - longitude → lon
    - u10 → wind_u_10m, v10 → wind_v_10m, t2m → temperature_2m, etc.

    Returns a clean Dataset with only the needed variables and coords.
    """
    ds = xr.open_dataset(era5_path)

    # Rename coordinate dims
    ds = ds.rename({
        "valid_time": "time",
        "latitude": "lat",
        "longitude": "lon",
    })

    # Rename data variables
    ds = ds.rename(ERA5_RENAME)

    # Drop non-essential coordinates
    drop_coords = [c for c in ["number", "expver"] if c in ds.coords]
    if drop_coords:
        ds = ds.drop_vars(drop_coords)

    # Assign clean units
    for var, unit in ERA5_UNITS.items():
        if var in ds:
            ds[var].attrs["units"] = unit

    # Add standard_name attrs
    std_names = {
        "wind_u_10m": "eastward_wind",
        "wind_v_10m": "northward_wind",
        "temperature_2m": "air_temperature",
        "mean_sea_level_pressure": "air_pressure_at_mean_sea_level",
        "total_precipitation": "precipitation_amount",
    }
    for var, sn in std_names.items():
        if var in ds:
            ds[var].attrs["standard_name"] = sn

    logger.info(
        "ERA5 standardised: %d variables, %s",
        len(list(ds.data_vars)), dict(ds.sizes),
    )
    return ds


def resample_glorys(
    glorys_path: Path | str,
    target_lat: np.ndarray,
    target_lon: np.ndarray,
    variables: list[str] | None = None,
) -> xr.Dataset:
    """
    Resample GLORYS12V1 ocean currents from 1/12° daily to 0.25° hourly.

    Performs:
      1. Spatial nearest-neighbor resampling from GLORYS 1/12° to ERA5 0.25° grid
      2. Squeezes the depth dimension (surface-only data, depth=0.494 m)
      3. Forward-fills daily values to hourly (same method as sea ice)
      4. Renames variables per project convention

    Parameters
    ----------
    glorys_path : path to the raw GLORYS NetCDF file
    target_lat : 1-D array of target latitudes (ERA5 grid)
    target_lon : 1-D array of target longitudes (ERA5 grid)
    variables : list of GLORYS variable names to extract (default: uo, vo)

    Returns
    -------
    xr.Dataset with dims (time, lat, lon), hourly, on the ERA5 0.25° grid.
    """
    from scipy.interpolate import griddata as scipy_griddata

    if variables is None:
        variables = ["uo", "vo"]

    ds = xr.open_dataset(glorys_path)

    # Source coordinates
    src_lat = ds["latitude"].values  # (49,), -70 to -66
    src_lon = ds["longitude"].values  # (96,), 72 to 79.9167

    # Target grid mesh
    tgt_lat_mesh, tgt_lon_mesh = np.meshgrid(target_lat, target_lon, indexing="ij")
    tgt_points = np.column_stack([tgt_lat_mesh.ravel(), tgt_lon_mesh.ravel()])

    # Source grid mesh
    src_lat_mesh, src_lon_mesh = np.meshgrid(src_lat, src_lon, indexing="ij")
    src_points = np.column_stack([src_lat_mesh.ravel(), src_lon_mesh.ravel()])

    n_time = ds.sizes["time"]
    n_lat = len(target_lat)
    n_lon = len(target_lon)

    result_datasets = {}

    for var_name in variables:
        if var_name not in ds:
            logger.warning("Variable %s not found in GLORYS file, skipping", var_name)
            continue

        da = ds[var_name]
        # Squeeze depth dimension if present (surface-only data)
        if "depth" in da.dims:
            da = da.squeeze("depth", drop=True)
        # Now dims should be (time, latitude, longitude)

        resampled = np.full((n_time, n_lat, n_lon), np.nan)

        for t in range(n_time):
            src_vals = da.isel(time=t).values.ravel()  # (lat*lon,)
            valid = np.isfinite(src_vals)
            if valid.sum() == 0:
                continue
            result = scipy_griddata(
                src_points[valid],
                src_vals[valid],
                tgt_points,
                method="nearest",
            )
            resampled[t] = result.reshape(n_lat, n_lon)

        # Re-mask land cells (>50% NaN across time → permanent land)
        nan_frac = np.isnan(resampled).mean(axis=0)
        land_mask = nan_frac > 0.5
        resampled[:, land_mask] = np.nan

        # Build DataArray
        proj_name = GLORYS_RENAME.get(var_name, var_name)
        out_da = xr.DataArray(
            resampled,
            dims=["time", "lat", "lon"],
            coords={
                "time": ds["time"].values,
                "lat": target_lat,
                "lon": target_lon,
            },
            attrs={
                "units": ds[var_name].attrs.get("units", "unknown"),
                "long_name": ds[var_name].attrs.get("long_name", var_name),
                "standard_name": proj_name,
                "source": "GLORYS12V1 (Mercator Ocean / CMEMS)",
                "original_variable": var_name,
                "reprojection": "nearest-neighbor (scipy.griddata)",
                "source_resolution": "1/12 deg (~8 km)",
                "target_resolution": "0.25 deg (~31 km)",
            },
        )
        result_datasets[proj_name] = out_da
        logger.info(
            "GLORYS %s → %s: resampled %s daily → hourly",
            var_name, proj_name, dict(da.sizes),
        )

    ds.close()

    # Forward-fill daily → hourly over a full-day hourly axis.
    # Use an explicit hourly index covering every hour of every day so the
    # final day's trailing hours (01:00–23:00) are included and forward-filled
    # (resample().ffill() truncates at the last original timestamp).
    import pandas as pd

    combined = xr.Dataset(result_datasets)
    first = combined.time.values[0]
    last = combined.time.values[-1] + pd.Timedelta(hours=23)
    hourly_index = pd.date_range(start=first, end=last, freq="1h")
    combined_hourly = combined.reindex(time=hourly_index, method="ffill")

    logger.info(
        "GLORYS resampled: %d variables, %s",
        len(result_datasets), dict(combined_hourly.sizes),
    )
    return combined_hourly
