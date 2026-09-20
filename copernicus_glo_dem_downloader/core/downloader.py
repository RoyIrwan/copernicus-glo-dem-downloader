"""Core download engine for Copernicus DEM tiles (AWS Open Data, public/anonymous access).

Pure Python, no Qt dependency, so it can run inside a QgsTask worker thread
and be unit tested without a running QGIS instance.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .bounding_box import BoundingBox
from .dataset import DatasetInfo, MaskType, individual_masks
from .download_state import DownloadState, FileState
from . import tile_coordinate_parser as tcp
from . import tile_list as tl

MAX_TILES = 500


class TooManyTilesError(Exception):
    """Raised when a requested area matches more tiles than MAX_TILES."""

    def __init__(self, tile_count: int):
        self.tile_count = tile_count
        super().__init__(
            f"The selected area matches {tile_count:,} tiles, which is more than the "
            f"{MAX_TILES:,}-tile limit. Select a smaller area or fewer tiles."
        )


@dataclass
class DownloadOptions:
    dataset: DatasetInfo
    output_directory: str
    masks: MaskType = MaskType.DEM
    bounding_box: BoundingBox | None = None
    # Exact tile folder names to download (e.g. from a tile index selection).
    # When set, this takes precedence over bounding_box and no intersects_tile
    # filtering is applied - only these exact tiles are fetched.
    selected_tile_names: list[str] | None = None
    max_retries: int = 3
    state_file: str = "download_state.json"
    force: bool = False


@dataclass
class DownloadResult:
    total_files: int = 0
    total_bytes: int = 0
    completed_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    downloaded_bytes: int = 0
    elapsed_seconds: float = 0.0
    cancelled: bool = False


def format_bytes(num_bytes: float) -> str:
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    i = 0
    while size >= 1024 and i < len(suffixes) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {suffixes[i]}"


class DownloaderCore:
    """Sequential (single-threaded) downloader driven step-by-step by a QgsTask.

    QgsTask.run() runs on a single worker thread; parallelism for a QGIS plugin
    is better achieved by running one task at a time and relying on the OS/HTTP
    stack for a single connection, keeping cancellation and progress reporting simple.
    """

    def __init__(self, client, options: DownloadOptions):
        self._client = client
        self._options = options
        self._state_file_path = Path(options.output_directory) / options.state_file
        self._downloaded_files: dict[str, FileState] = {}

    def resolve_objects(
        self,
        log: Callable[[str], None] = lambda msg: None,
        cache_dir: Path | None = None,
        resolve_progress_callback: Callable[[int, int], bool] | None = None,
    ) -> list[dict] | None:
        """List (Key, Size, ETag) dicts for files matching the dataset/masks/bbox.

        resolve_progress_callback(tiles_listed, tiles_total) -> continue?; returning False
        aborts and this method returns None (used for cancellation while listing tiles,
        which can take a while when many tiles match).
        """
        opts = self._options
        bucket = opts.dataset.bucket

        if opts.selected_tile_names is not None:
            # Exact tiles were picked (e.g. selected in the tile index layer) - use them
            # as-is, retargeted to this dataset's resolution code. No bbox/intersects_tile
            # filtering is applied, so only the tiles the user actually selected are fetched.
            matching_tiles = [
                tcp.retarget_tile_name(name, opts.dataset) for name in opts.selected_tile_names
            ]
            log(f"{len(matching_tiles):,} tiles explicitly selected.")
        else:
            log(f"Fetching tile list for {opts.dataset.key}...")
            all_tiles = tl.fetch_tile_names(self._client, opts.dataset, cache_dir=cache_dir)
            log(f"{len(all_tiles):,} tiles available in dataset.")

            matching_tiles = tl.filter_tiles_by_bbox(all_tiles, opts.bounding_box)
            log(f"{len(matching_tiles):,} tiles match the requested area.")

        if len(matching_tiles) > MAX_TILES:
            raise TooManyTilesError(len(matching_tiles))

        objects: list[dict] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for i, tile_name in enumerate(matching_tiles):
            if resolve_progress_callback is not None:
                if not resolve_progress_callback(i, len(matching_tiles)):
                    return None

            prefix = tile_name.rstrip("/") + "/"
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    if tcp.matches_mask_filter(obj["Key"], opts.masks):
                        objects.append(obj)

        if resolve_progress_callback is not None:
            resolve_progress_callback(len(matching_tiles), len(matching_tiles))

        return objects

    def run(
        self,
        objects: list[dict],
        progress_callback: Callable[[int, int, int, int], bool] | None = None,
        log: Callable[[str], None] = lambda msg: None,
    ) -> DownloadResult:
        """Download `objects`. progress_callback(completed, skipped, failed, total) -> continue?

        Returning False from progress_callback aborts the download (used for cancellation).
        """
        opts = self._options
        os.makedirs(opts.output_directory, exist_ok=True)
        self._load_state()

        total = len(objects)
        total_bytes = sum(o["Size"] for o in objects)
        completed = skipped = failed = 0
        downloaded_bytes = 0
        start_time = time.monotonic()
        cancelled = False

        for obj in objects:
            if progress_callback is not None:
                should_continue = progress_callback(completed, skipped, failed, total)
                if not should_continue:
                    cancelled = True
                    break

            outcome, size = self._download_one(obj)
            if outcome == "skipped":
                skipped += 1
            elif outcome == "completed":
                completed += 1
                downloaded_bytes += size
            else:
                failed += 1
                log(f"Failed to download {obj['Key']} after {opts.max_retries} attempt(s).")

        self._save_state()

        return DownloadResult(
            total_files=total,
            total_bytes=total_bytes,
            completed_files=completed,
            skipped_files=skipped,
            failed_files=failed,
            downloaded_bytes=downloaded_bytes,
            elapsed_seconds=time.monotonic() - start_time,
            cancelled=cancelled,
        )

    def _download_one(self, obj: dict) -> tuple[str, int]:
        opts = self._options
        key = obj["Key"]
        local_path = Path(opts.output_directory) / key.replace("/", os.sep)
        obj_size = obj["Size"]

        if not opts.force and local_path.exists() and local_path.stat().st_size == obj_size:
            state = self._downloaded_files.get(key)
            if state is not None and state.size == obj_size:
                return "skipped", 0

        local_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, opts.max_retries + 1):
            try:
                self._download_with_retry(key, local_path)
                self._downloaded_files[key] = FileState.now(obj_size, obj.get("ETag", ""))
                return "completed", obj_size
            except Exception:
                if attempt < opts.max_retries:
                    time.sleep(2**attempt)

        return "failed", 0

    def _download_with_retry(self, key: str, local_path: Path) -> None:
        temp_path = local_path.with_suffix(local_path.suffix + ".tmp")
        try:
            response = self._client.get_object(Bucket=self._options.dataset.bucket, Key=key)
            with open(temp_path, "wb") as f:
                shutil.copyfileobj(response["Body"], f)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        os.replace(temp_path, local_path)

    def _load_state(self) -> None:
        if not self._state_file_path.exists():
            return
        try:
            with open(self._state_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            state = DownloadState.from_dict(data)
            self._downloaded_files.update(state.files)
        except Exception:
            pass  # Ignore corrupted state file

    def _save_state(self) -> None:
        try:
            state = DownloadState(files=dict(self._downloaded_files))
            with open(self._state_file_path, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2)
        except Exception:
            pass  # Ignore state save errors
