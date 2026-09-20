from copernicus_glo_dem_downloader.core.bounding_box import BoundingBox


def test_intersects_tile_fully_inside():
    bbox = BoundingBox(-10, 35, 30, 60)
    assert bbox.intersects_tile(5, 45) is True


def test_intersects_tile_edge_touch():
    bbox = BoundingBox(-10, 35, 30, 60)
    assert bbox.intersects_tile(-11, 34) is True  # touches corner
    assert bbox.intersects_tile(29, 59) is True


def test_intersects_tile_outside():
    bbox = BoundingBox(-10, 35, 30, 60)
    assert bbox.intersects_tile(-20, 45) is False
    assert bbox.intersects_tile(10, 25) is False


def test_str_format():
    bbox = BoundingBox(-10.5, 35.25, 30.75, 60.0)
    s = str(bbox)
    assert "-10.50" in s
    assert "35.25" in s
    assert "30.75" in s
    assert "60.00" in s
