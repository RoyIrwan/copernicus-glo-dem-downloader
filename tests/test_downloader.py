import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from copernicus_glo_dem_downloader.core.bounding_box import BoundingBox
from copernicus_glo_dem_downloader.core.dataset import GLO_30, GLO_90
from copernicus_glo_dem_downloader.core.download_state import FileState
from copernicus_glo_dem_downloader.core.downloader import (
    MAX_TILES,
    DownloaderCore,
    DownloadOptions,
    TooManyTilesError,
    format_bytes,
)


class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read(self, amount=-1):
        if amount is None or amount < 0:
            chunk = self._data[self._pos :]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + amount]
        self._pos += len(chunk)
        return chunk


def _make_options(tmp_path: Path, **overrides) -> DownloadOptions:
    defaults = dict(dataset=GLO_30, output_directory=str(tmp_path))
    defaults.update(overrides)
    return DownloadOptions(**defaults)


def test_format_bytes():
    assert format_bytes(500) == "500.0 B"
    assert format_bytes(1536) == "1.5 KB"


def test_download_one_writes_file_and_reports_completed(tmp_path):
    options = _make_options(tmp_path)
    client = MagicMock()
    client.get_object.return_value = {"Body": _FakeBody(b"hello world")}
    core = DownloaderCore(client, options)

    key = "Copernicus_DSM_COG_10_N45_00_E006_00_DEM/Copernicus_DSM_COG_10_N45_00_E006_00_DEM.tif"
    obj = {"Key": key, "Size": 11, "ETag": "etag"}

    outcome, size = core._download_one(obj)

    assert outcome == "completed"
    assert size == 11
    local_path = tmp_path / key.replace("/", os.sep)
    assert local_path.read_bytes() == b"hello world"


def test_download_one_skips_existing_matching_state(tmp_path):
    options = _make_options(tmp_path)
    core = DownloaderCore(MagicMock(), options)

    key = "Copernicus_DSM_COG_10_N45_00_E006_00_DEM/Copernicus_DSM_COG_10_N45_00_E006_00_DEM.tif"
    local_path = tmp_path / key.replace("/", os.sep)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(b"x" * 10)

    core._downloaded_files[key] = FileState.now(10, "etag")

    outcome, size = core._download_one({"Key": key, "Size": 10, "ETag": "etag"})

    assert outcome == "skipped"
    assert size == 0


def test_run_reports_progress_and_can_be_cancelled(tmp_path):
    options = _make_options(tmp_path)
    client = MagicMock()
    client.get_object.side_effect = lambda **kwargs: {"Body": _FakeBody(b"data")}
    core = DownloaderCore(client, options)

    objects = [
        {"Key": f"tile{i}/tile{i}_DEM.tif", "Size": 4, "ETag": f"e{i}"} for i in range(3)
    ]

    calls = []

    def progress_callback(completed, skipped, failed, total):
        calls.append((completed, skipped, failed, total))
        return len(calls) < 2  # cancel after the second call

    result = core.run(objects, progress_callback=progress_callback)

    assert result.cancelled is True
    assert result.completed_files == 1  # only one file downloaded before cancellation


def test_resolve_objects_raises_when_selected_tiles_exceed_max(tmp_path):
    options = _make_options(
        tmp_path,
        selected_tile_names=[f"Copernicus_DSM_COG_10_N45_00_E{i:03d}_00_DEM" for i in range(MAX_TILES + 1)],
    )
    core = DownloaderCore(MagicMock(), options)

    with pytest.raises(TooManyTilesError) as exc_info:
        core.resolve_objects()

    assert exc_info.value.tile_count == MAX_TILES + 1


def test_resolve_objects_allows_exactly_max_tiles(tmp_path):
    options = _make_options(
        tmp_path,
        selected_tile_names=[f"Copernicus_DSM_COG_10_N45_00_E{i:03d}_00_DEM" for i in range(MAX_TILES)],
    )
    client = MagicMock()
    _paginator_returning(client, {})  # no matching files, but resolution itself must not raise
    core = DownloaderCore(client, options)

    objects = core.resolve_objects()

    assert objects == []


def _paginator_returning(client, keys_by_prefix):
    """Configure client.get_paginator('list_objects_v2').paginate(...) to return
    one page of Contents per prefix, looked up from keys_by_prefix."""

    def get_paginator(name):
        assert name == "list_objects_v2"

        class _Paginator:
            def paginate(self, Bucket, Prefix):  # noqa: N803 - matches boto3 kwarg casing
                keys = keys_by_prefix.get(Prefix, [])
                yield {"Contents": [{"Key": k, "Size": 1, "ETag": "e"} for k in keys]}

        return _Paginator()

    client.get_paginator.side_effect = get_paginator


def test_resolve_objects_with_selected_tile_names_ignores_bbox_and_neighbors(tmp_path):
    """Regression test: selecting 2 adjacent tiles must not pull in neighboring tiles,
    even though their union bounding box touches those neighbors' edges."""
    # A bbox spanning exactly 2 adjacent 1x1 tiles touches 6 neighboring tiles at its edges.
    wide_bbox = BoundingBox(min_lon=10.0, min_lat=45.0, max_lon=12.0, max_lat=46.0)

    options = _make_options(
        tmp_path,
        bounding_box=wide_bbox,  # would over-select if it were used
        selected_tile_names=[
            "Copernicus_DSM_COG_10_N45_00_E010_00_DEM",
            "Copernicus_DSM_COG_10_N45_00_E011_00_DEM",
        ],
    )
    client = MagicMock()
    _paginator_returning(
        client,
        {
            "Copernicus_DSM_COG_10_N45_00_E010_00_DEM/": [
                "Copernicus_DSM_COG_10_N45_00_E010_00_DEM/Copernicus_DSM_COG_10_N45_00_E010_00_DEM.tif"
            ],
            "Copernicus_DSM_COG_10_N45_00_E011_00_DEM/": [
                "Copernicus_DSM_COG_10_N45_00_E011_00_DEM/Copernicus_DSM_COG_10_N45_00_E011_00_DEM.tif"
            ],
        },
    )
    core = DownloaderCore(client, options)

    objects = core.resolve_objects()

    assert objects is not None
    assert len(objects) == 2  # exactly the 2 selected tiles, no neighbors
    # tile_list.fetch_tile_names / filter_tiles_by_bbox must never be consulted.
    client.get_object.assert_not_called()


def test_resolve_objects_retargets_selected_tiles_to_dataset(tmp_path):
    """Tile names from the shared (GLO-30-built) index layer must be retargeted to
    GLO-90's resolution code before listing, not used verbatim."""
    options = _make_options(
        tmp_path,
        dataset=GLO_90,
        selected_tile_names=["Copernicus_DSM_COG_10_N45_00_E010_00_DEM"],
    )
    client = MagicMock()
    _paginator_returning(
        client,
        {
            "Copernicus_DSM_COG_30_N45_00_E010_00_DEM/": [
                "Copernicus_DSM_COG_30_N45_00_E010_00_DEM/Copernicus_DSM_COG_30_N45_00_E010_00_DEM.tif"
            ],
        },
    )
    core = DownloaderCore(client, options)

    objects = core.resolve_objects()

    assert objects is not None
    assert len(objects) == 1
    assert objects[0]["Key"].startswith("Copernicus_DSM_COG_30_")


def test_state_roundtrip(tmp_path):
    options = _make_options(tmp_path, state_file="state.json")
    core = DownloaderCore(MagicMock(), options)

    core._downloaded_files["some/key.tif"] = FileState.now(123, "abc")
    core._save_state()

    state_path = tmp_path / "state.json"
    assert state_path.exists()
    data = json.loads(state_path.read_text())
    assert "some/key.tif" in data["Files"]

    core2 = DownloaderCore(MagicMock(), options)
    core2._load_state()
    assert core2._downloaded_files["some/key.tif"].size == 123
