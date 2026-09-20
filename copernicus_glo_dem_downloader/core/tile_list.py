"""Fetches, caches, and filters the bucket-wide tile list published by AWS Open Data Copernicus DEM."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .bounding_box import BoundingBox
from .dataset import DatasetInfo
from . import tile_coordinate_parser as tcp

TILE_LIST_KEY = "tileList.txt"
CACHE_TTL_SECONDS = 7 * 24 * 3600  # tile lists change rarely; cache for a week


def _cache_path(cache_dir: Path, dataset: DatasetInfo) -> Path:
    return cache_dir / f"tile_list_{dataset.key}.json"


def fetch_tile_names(client, dataset: DatasetInfo, cache_dir: Path | None = None) -> list[str]:
    """Return the list of tile folder names for a dataset, using a local cache when available."""
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = _cache_path(cache_dir, dataset)
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < CACHE_TTL_SECONDS:
                try:
                    return json.loads(cache_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass  # fall through to re-fetch

    obj = client.get_object(Bucket=dataset.bucket, Key=TILE_LIST_KEY)
    body = obj["Body"].read().decode("utf-8")
    tiles = [line.strip() for line in body.splitlines() if line.strip()]

    if cache_dir is not None:
        try:
            _cache_path(cache_dir, dataset).write_text(json.dumps(tiles), encoding="utf-8")
        except OSError:
            pass  # cache write failure is non-fatal

    return tiles


def filter_tiles_by_bbox(tile_names: list[str], bbox: BoundingBox | None) -> list[str]:
    """Keep only tile names whose parsed coordinates intersect the bbox.

    Tiles that cannot be parsed are kept (fail-open). If bbox is None, all tiles are returned.
    """
    if bbox is None:
        return tile_names

    result = []
    for name in tile_names:
        coords = tcp.try_parse_coordinates(name)
        if coords is None:
            result.append(name)
            continue
        lat, lon = coords
        if bbox.intersects_tile(lon, lat):
            result.append(name)

    return result
