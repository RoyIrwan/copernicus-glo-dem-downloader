"""Simple lon/lat bounding box helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @classmethod
    def from_qgis_rectangle(cls, rect, source_crs, dest_crs=None) -> "BoundingBox":
        """Build from a QgsRectangle, optionally reprojecting from source_crs to dest_crs (EPSG:4326)."""
        from qgis.core import QgsCoordinateTransform, QgsProject

        if dest_crs is not None and source_crs != dest_crs:
            transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
            rect = transform.transformBoundingBox(rect)

        return cls(
            min_lon=rect.xMinimum(),
            min_lat=rect.yMinimum(),
            max_lon=rect.xMaximum(),
            max_lat=rect.yMaximum(),
        )

    def intersects_tile(
        self, tile_lon: float, tile_lat: float, tile_width: float = 1.0, tile_height: float = 1.0
    ) -> bool:
        """Check whether a tile (given by its SW corner) overlaps this bbox. Edge-touching counts."""
        return (
            self.min_lon <= tile_lon + tile_width
            and self.max_lon >= tile_lon
            and self.min_lat <= tile_lat + tile_height
            and self.max_lat >= tile_lat
        )

    def __str__(self) -> str:
        return f"[{self.min_lon:.2f},{self.min_lat:.2f}] to [{self.max_lon:.2f},{self.max_lat:.2f}]"
