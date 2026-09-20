"""Parses tile coordinates and mask suffixes from Copernicus DEM file/folder names."""

from __future__ import annotations

import re

from .dataset import DatasetInfo, MaskType, individual_masks, mask_file_suffix

# Matches coordinate patterns like _N45_00_E006_00_ or _S13_00_E021_00_
# Example folder name: Copernicus_DSM_COG_10_S13_00_E021_00_DEM
_TILE_COORD_RE = re.compile(r"_([NS])(\d+)_(\d+)_([EW])(\d+)_(\d+)_?")

# Matches the resolution-code segment shared by every tile name, e.g. the "10" in
# "Copernicus_DSM_COG_10_N45_00_E006_00_DEM" (GLO-30) or "30" for GLO-90.
_RESOLUTION_CODE_RE = re.compile(r"^(Copernicus_DSM_COG_)(\d+)(_.*)$")


def try_parse_coordinates(name: str) -> tuple[float, float] | None:
    """Extract (lat, lon) from a tile name/key. Returns None if the format doesn't match."""
    match = _TILE_COORD_RE.search(name)
    if not match:
        return None

    ns, lat_deg, lat_min, ew, lon_deg, lon_min = match.groups()

    lat = int(lat_deg) + int(lat_min) / 60.0
    if ns == "S":
        lat = -lat

    lon = int(lon_deg) + int(lon_min) / 60.0
    if ew == "W":
        lon = -lon

    return lat, lon


def retarget_tile_name(tile_name: str, dataset: DatasetInfo) -> str:
    """Rewrite a tile name's resolution-code segment to match the given dataset.

    The tile index grid is built once from GLO-30's tile list (grid is identical for
    both datasets), so a name like "Copernicus_DSM_COG_10_N45_00_E006_00_DEM" must be
    retargeted to "Copernicus_DSM_COG_30_N45_00_E006_00_DEM" before it's valid for GLO-90.
    Returns the name unchanged if it doesn't match the expected pattern.
    """
    match = _RESOLUTION_CODE_RE.match(tile_name)
    if not match:
        return tile_name
    prefix, _old_code, suffix = match.groups()
    return f"{prefix}{dataset.resolution_code}{suffix}"


def matches_mask_filter(key: str, masks: MaskType) -> bool:
    """Check if a file matches the requested mask types.

    Excludes files under PREVIEW/ (quicklook *_QL.tif images), which share the same
    mask suffixes as the real data files but are not actual DEM/mask rasters.
    """
    if "/PREVIEW/" in key or "\\PREVIEW\\" in key:
        return False

    key_lower = key.lower()
    for mask in individual_masks(masks):
        if key_lower.endswith(mask_file_suffix(mask).lower()):
            return True
    return False
