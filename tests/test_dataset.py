from copernicus_glo_dem_downloader.core.dataset import (
    GLO_30,
    GLO_90,
    KNOWN_DATASETS,
    MaskType,
    individual_masks,
    mask_file_suffix,
)


def test_known_datasets():
    assert set(KNOWN_DATASETS.keys()) == {"GLO-30", "GLO-90"}
    assert KNOWN_DATASETS["GLO-30"] is GLO_30
    assert KNOWN_DATASETS["GLO-90"] is GLO_90


def test_glo30_bucket_and_resolution():
    assert GLO_30.bucket == "copernicus-dem-30m"
    assert GLO_30.resolution_code == "10"
    assert GLO_30.resolution_m == 30


def test_glo90_bucket_and_resolution():
    assert GLO_90.bucket == "copernicus-dem-90m"
    assert GLO_90.resolution_code == "30"
    assert GLO_90.resolution_m == 90


def test_mask_all_includes_every_individual_mask():
    result = individual_masks(MaskType.ALL)
    assert set(result) == {MaskType.DEM, MaskType.EDM, MaskType.FLM, MaskType.HEM, MaskType.WBM}


def test_mask_file_suffix():
    assert mask_file_suffix(MaskType.DEM) == "_DEM.tif"
    assert mask_file_suffix(MaskType.WBM) == "_WBM.tif"
