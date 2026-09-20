from unittest.mock import MagicMock

from copernicus_glo_dem_downloader.core.bounding_box import BoundingBox
from copernicus_glo_dem_downloader.core.dataset import GLO_30
from copernicus_glo_dem_downloader.core import tile_list as tl


class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data


def test_fetch_tile_names_parses_lines_no_cache():
    client = MagicMock()
    client.get_object.return_value = {
        "Body": _FakeBody(b"Copernicus_DSM_COG_10_N00_00_E006_00_DEM\nCopernicus_DSM_COG_10_N00_00_E009_00_DEM\n")
    }

    names = tl.fetch_tile_names(client, GLO_30, cache_dir=None)

    assert names == [
        "Copernicus_DSM_COG_10_N00_00_E006_00_DEM",
        "Copernicus_DSM_COG_10_N00_00_E009_00_DEM",
    ]
    client.get_object.assert_called_once_with(Bucket=GLO_30.bucket, Key="tileList.txt")


def test_fetch_tile_names_uses_cache(tmp_path):
    client = MagicMock()
    client.get_object.return_value = {"Body": _FakeBody(b"tile_a\ntile_b\n")}

    first = tl.fetch_tile_names(client, GLO_30, cache_dir=tmp_path)
    assert first == ["tile_a", "tile_b"]
    assert client.get_object.call_count == 1

    # Second call should hit the cache, not the client again.
    second = tl.fetch_tile_names(client, GLO_30, cache_dir=tmp_path)
    assert second == ["tile_a", "tile_b"]
    assert client.get_object.call_count == 1


def test_filter_tiles_by_bbox_none_returns_all():
    names = ["Copernicus_DSM_COG_10_N00_00_E006_00_DEM", "Copernicus_DSM_COG_10_N70_00_E050_00_DEM"]
    assert tl.filter_tiles_by_bbox(names, None) == names


def test_filter_tiles_by_bbox_keeps_intersecting():
    names = [
        "Copernicus_DSM_COG_10_N45_00_E010_00_DEM",
        "Copernicus_DSM_COG_10_N70_00_E050_00_DEM",
    ]
    bbox = BoundingBox(-10, 35, 30, 60)

    assert tl.filter_tiles_by_bbox(names, bbox) == ["Copernicus_DSM_COG_10_N45_00_E010_00_DEM"]
