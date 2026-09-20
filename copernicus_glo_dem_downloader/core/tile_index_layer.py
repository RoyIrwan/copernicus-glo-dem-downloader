"""Builds an in-memory QGIS vector layer showing the 1x1 degree tile grid.

The grid is identical for GLO-30 and GLO-90 (only the pixel resolution inside
each tile differs), so a single universal index layer is used regardless of
which dataset(s) are selected for download.
"""

from __future__ import annotations

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsSimpleFillSymbolLayer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtGui import QColor

from .dataset import TILE_GRID_DEGREES
from . import tile_coordinate_parser as tcp

TILE_NAME_FIELD = "tile_name"
TILE_INDEX_LAYER_NAME = "Copernicus DEM tile index"


def build_tile_index_layer(tile_names: list[str]) -> QgsVectorLayer:
    """Create an in-memory polygon layer, one 1x1 degree square per tile, in EPSG:4326."""
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", TILE_INDEX_LAYER_NAME, "memory")
    provider = layer.dataProvider()
    provider.addAttributes([QgsField(TILE_NAME_FIELD, QVariant.String)])
    layer.updateFields()

    features = []
    for name in tile_names:
        coords = tcp.try_parse_coordinates(name)
        if coords is None:
            continue
        lat, lon = coords

        ring = [
            QgsPointXY(lon, lat),
            QgsPointXY(lon + TILE_GRID_DEGREES, lat),
            QgsPointXY(lon + TILE_GRID_DEGREES, lat + TILE_GRID_DEGREES),
            QgsPointXY(lon, lat + TILE_GRID_DEGREES),
            QgsPointXY(lon, lat),
        ]

        feature = QgsFeature(QgsFields(layer.fields()))
        feature.setGeometry(QgsGeometry.fromPolygonXY([ring]))
        feature.setAttributes([name])
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    _apply_outline_only_style(layer)

    return layer


def _apply_outline_only_style(layer: QgsVectorLayer) -> None:
    """Style the layer as an outline with no fill, so it doesn't obscure the map underneath."""
    symbol = layer.renderer().symbol()
    fill_layer = symbol.symbolLayer(0)
    if isinstance(fill_layer, QgsSimpleFillSymbolLayer):
        fill_layer.setBrushStyle(Qt.NoBrush)
        fill_layer.setStrokeColor(QColor("red"))
        fill_layer.setStrokeWidth(0.5)
    layer.triggerRepaint()


def add_or_replace_tile_index_layer(tile_names: list[str], group_name: str = "Tile Index") -> QgsVectorLayer:
    """Add the universal tile index layer to the project, replacing any previous instance."""
    project = QgsProject.instance()

    for existing in project.mapLayersByName(TILE_INDEX_LAYER_NAME):
        project.removeMapLayer(existing.id())

    layer = build_tile_index_layer(tile_names)

    root = project.layerTreeRoot()
    group = root.findGroup(group_name)
    if group is None:
        group = root.insertGroup(0, group_name)

    project.addMapLayer(layer, addToLegend=False)
    group.addLayer(layer)

    return layer


def find_tile_index_layer():
    """Return the currently loaded tile index layer, or None if not loaded."""
    layers = QgsProject.instance().mapLayersByName(TILE_INDEX_LAYER_NAME)
    return layers[0] if layers else None
