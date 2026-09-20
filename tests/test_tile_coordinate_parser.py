import pytest

from copernicus_glo_dem_downloader.core.dataset import GLO_30, GLO_90, MaskType
from copernicus_glo_dem_downloader.core import tile_coordinate_parser as tcp


@pytest.mark.parametrize(
    "name,expected_lat,expected_lon",
    [
        ("Copernicus_DSM_COG_10_N45_00_E006_00_DEM", 45.0, 6.0),
        ("Copernicus_DSM_COG_10_S45_00_W006_00_DEM", -45.0, -6.0),
        ("Copernicus_DSM_COG_10_N00_00_E000_00_DEM", 0.0, 0.0),
        ("Copernicus_DSM_COG_30_S89_00_W179_00_DEM", -89.0, -179.0),
    ],
)
def test_try_parse_coordinates_valid_names(name, expected_lat, expected_lon):
    result = tcp.try_parse_coordinates(name)
    assert result is not None
    lat, lon = result
    assert lat == pytest.approx(expected_lat, abs=1e-5)
    assert lon == pytest.approx(expected_lon, abs=1e-5)


@pytest.mark.parametrize("name", ["not_a_tile", "", "random.txt"])
def test_try_parse_coordinates_invalid_returns_none(name):
    assert tcp.try_parse_coordinates(name) is None


def test_retarget_tile_name_glo30_to_glo90():
    name = "Copernicus_DSM_COG_10_N45_00_E006_00_DEM"
    assert tcp.retarget_tile_name(name, GLO_90) == "Copernicus_DSM_COG_30_N45_00_E006_00_DEM"


def test_retarget_tile_name_same_dataset_is_noop():
    name = "Copernicus_DSM_COG_10_N45_00_E006_00_DEM"
    assert tcp.retarget_tile_name(name, GLO_30) == name


def test_retarget_tile_name_unrecognized_format_unchanged():
    assert tcp.retarget_tile_name("not_a_tile_name", GLO_90) == "not_a_tile_name"


def test_matches_mask_filter_excludes_preview():
    key = "Copernicus_DSM_COG_10_N45_00_E006_00_DEM/PREVIEW/Copernicus_DSM_10_N45_00_E006_00_DEM_QL.tif"
    assert tcp.matches_mask_filter(key, MaskType.DEM) is False


def test_matches_mask_filter_tile_folder_layout():
    tile = "Copernicus_DSM_COG_10_N45_00_E006_00_DEM"
    assert tcp.matches_mask_filter(f"{tile}/{tile}.tif", MaskType.DEM) is True
    assert (
        tcp.matches_mask_filter(f"{tile}/AUXFILES/Copernicus_DSM_COG_10_N45_00_E006_00_WBM.tif", MaskType.WBM)
        is True
    )
    assert (
        tcp.matches_mask_filter(f"{tile}/AUXFILES/Copernicus_DSM_COG_10_N45_00_E006_00_WBM.tif", MaskType.DEM)
        is False
    )
