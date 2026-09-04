#!/usr/bin/env python3
"""
Download a small representative sample of Sentinel-1 EW_GRDM scenes
for the East Prydz Bay region.

Product: Sentinel-1 Extra-Wide Ground Range Detected Medium (EW_GRDM),
C-band SAR, dual-polarization (DH: HH/HV or VV/VH), ~40 m resolution.

Access: Copernicus Data Space OData API with OAuth2 (client_credentials
or password grant). Uses COPERNICUS_USERNAME / COPERNICUS_PASSWORD.

Strategy:
  1. Public catalog query (OData) to list EW_GRDM scenes intersecting
     the East Prydz Bay bbox (from config/region.yaml).
  2. Sort by date descending; take the most recent N scenes (default 3).
  3. Download each scene via the Products/<id>/$value endpoint with
     bearer token auth.
  4. Save to data/raw/sar/ and create a simple metadata record.

This is a REPRESENTATIVE SAMPLE ONLY — not the full archive.

Usage:
    python scripts/data/download_sentinel1.py [--count 3]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import requests

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.region import load_region

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CATALOG = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CLIENT_ID = "cdse-public"

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "sar"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "sar"


def load_creds() -> tuple[str, str]:
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except ImportError:
        pass
    u = os.getenv("COPERNICUS_USERNAME", "").strip()
    p = os.getenv("COPERNICUS_PASSWORD", "").strip()
    if not u or not p:
        raise RuntimeError(
            "COPERNICUS_USERNAME / COPERNICUS_PASSWORD not set. "
            "Register at https://dataspace.copernicus.eu and set them in .env."
        )
    return u, p


def get_token(username: str, password: str) -> str:
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": CLIENT_ID,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def build_polygon() -> str:
    """Build OData polygon string from config/region.yaml."""
    bb = load_region().bounding_box
    return (
        f"geography'SRID=4326;POLYGON(({bb.west} {bb.south},"
        f"{bb.east} {bb.south},{bb.east} {bb.north},"
        f"{bb.west} {bb.north},{bb.west} {bb.south}))'"
    )


def list_recent_ew_grdm(n: int) -> list[dict]:
    """Return up to n most recent EW_GRDM scenes intersecting the bbox."""
    bb = load_region().bounding_box
    # The OData spatial endpoint rejects float formatting (72.0); use integers.
    w, s, e, ng = int(bb.west), int(bb.south), int(bb.east), int(bb.north)
    polygon = f"geography'SRID=4326;POLYGON(({w} {s},{e} {s},{e} {ng},{w} {ng},{w} {s}))'"
    params = {
        "$filter": (
            f"Collection/Name eq 'SENTINEL-1' and "
            f"contains(Name,'EW_GRDM') and "
            f"OData.CSC.Intersects(area={polygon})"
        ),
        "$top": n,
        "$select": "Id,Name,ContentDate/Start,ContentLength,Online",
        "$orderby": "ContentDate/Start desc",
    }
    r = requests.get(CATALOG, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("value", [])


def download_scene(token: str, prod_id: str, name: str, dest_dir: Path) -> Path:
    """
    Download one SAFE archive to dest_dir, streaming.

    Uses the dedicated download host directly (no redirect) so the Bearer
    token is not stripped by requests on the cross-host redirect from the
    catalogue service. The download endpoint rejects quoted UUIDs.
    """
    url = f"https://download.dataspace.copernicus.eu/odata/v1/Products({prod_id})/$value"
    # Scene names already end in ".SAFE"; avoid double suffix.
    stem = name if name.endswith(".SAFE") else f"{name}.SAFE"
    dest = dest_dir / f"{stem}.zip"
    dest_dir.mkdir(parents=True, exist_ok=True)

    if dest.exists() and dest.stat().st_size > 0:
        logger.info("Already present: %s", dest.name)
        return dest

    logger.info("Downloading %s (%s) ...", name, prod_id)
    with requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
        timeout=300,
    ) as r:
        r.raise_for_status()
        total = 0
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
                    total += len(chunk)
    logger.info("Saved %.2f MB -> %s", total / 1e6, dest)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=3,
                        help="Number of most recent scenes to download")
    args = parser.parse_args()

    region = load_region()
    bb = region.bounding_box
    logger.info("Region %s | bbox S=%.1f N=%.1f W=%.1f E=%.1f",
                region.region_name, bb.south, bb.north, bb.west, bb.east)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    username, password = load_creds()
    token = get_token(username, password)
    logger.info("OAuth2 token acquired")

    scenes = list_recent_ew_grdm(args.count)
    if not scenes:
        logger.warning("No EW_GRDM scenes found for the bbox.")
        return

    logger.info("Found %d scenes; downloading up to %d", len(scenes), args.count)

    raw_files = []
    for s in scenes[: args.count]:
        prod_id = s["Id"]
        name = s["Name"]
        start = s.get("ContentDate", {}).get("Start", "unknown")[:19]
        size_mb = s.get("ContentLength", 0) / 1e6
        logger.info("  %s  %.1f MB  %s", name, size_mb, start)
        f = download_scene(token, prod_id, name, RAW_DIR)
        raw_files.append(f)

    # Write metadata JSON (no SAR processing in this phase).
    meta = {
        "provider": "ESA / Copernicus Data Space",
        "product": "Sentinel-1 EW_GRDM",
        "variables": ["sigma0", "polarization"],
        "polarizations": "DH (dual)",
        "crs": "EPSG:4326 (scene geolocation)",
        "spatial_bounds": {"south": bb.south, "north": bb.north, "west": bb.west, "east": bb.east},
        "acquisition_date": datetime.utcnow().isoformat(),
        "n_requested": args.count,
        "n_downloaded": len(raw_files),
        "raw_dir": str(RAW_DIR),
        "processed_dir": str(PROCESSED_DIR),
        "scenes": [
            {
                "product_id": s["Id"],
                "name": s["Name"],
                "start": s.get("ContentDate", {}).get("Start", "")[:19],
                "size_mb": round(s.get("ContentLength", 0) / 1e6, 1),
                "product_type": "EW_GRDM",
                "online": s.get("Online", ""),
            }
            for s in scenes[: args.count]
        ],
    }
    meta_file = PROCESSED_DIR / f"east_prydz_bay_sentinel1_metadata.json"
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Saved metadata -> %s", meta_file)

    logger.info("=== VALIDATION ===")
    logger.info("Files downloaded: %d", len(raw_files))
    for f in raw_files:
        size_mb = f.stat().st_size / 1e6
        logger.info("  %s  %.1f MB  exists=%s", f.name, size_mb, f.exists())


if __name__ == "__main__":
    main()