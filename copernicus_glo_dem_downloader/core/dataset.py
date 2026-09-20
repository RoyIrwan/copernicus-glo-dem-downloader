"""Dataset catalog and mask flags for Copernicus DEM on AWS Open Data."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, auto


@dataclass(frozen=True)
class DatasetInfo:
    key: str
    label: str
    bucket: str
    resolution_code: str  # resolution token embedded in tile file names ("10" or "30")
    resolution_m: int
    description: str


# Copernicus DEM is published as two public AWS Open Data buckets, one per resolution.
# Both use the same 1x1 degree tile grid; only the pixel resolution inside each tile differs.
GLO_30 = DatasetInfo(
    key="GLO-30",
    label="GLO-30 (30m)",
    bucket="copernicus-dem-30m",
    resolution_code="10",
    resolution_m=30,
    description="30m global Copernicus DEM (public)",
)

GLO_90 = DatasetInfo(
    key="GLO-90",
    label="GLO-90 (90m)",
    bucket="copernicus-dem-90m",
    resolution_code="30",
    resolution_m=90,
    description="90m global Copernicus DEM (public)",
)

KNOWN_DATASETS: dict[str, DatasetInfo] = {
    GLO_30.key: GLO_30,
    GLO_90.key: GLO_90,
}

TILE_GRID_DEGREES = 1.0  # every Copernicus DEM tile covers 1x1 degree, regardless of resolution


class MaskType(Flag):
    NONE = 0
    DEM = auto()
    EDM = auto()
    FLM = auto()
    HEM = auto()
    WBM = auto()


MaskType.ALL = MaskType.DEM | MaskType.EDM | MaskType.FLM | MaskType.HEM | MaskType.WBM

_MASK_DESCRIPTIONS = {
    MaskType.DEM: "Digital Elevation Model (elevation data)",
    MaskType.EDM: "Editing Mask (areas that were edited/corrected)",
    MaskType.FLM: "Filling Mask (areas filled from other sources)",
    MaskType.HEM: "Height Error Mask (estimated vertical accuracy)",
    MaskType.WBM: "Water Body Mask (ocean/lake areas)",
}

_MASK_SUFFIXES = {
    MaskType.DEM: "_DEM.tif",
    MaskType.EDM: "_EDM.tif",
    MaskType.FLM: "_FLM.tif",
    MaskType.HEM: "_HEM.tif",
    MaskType.WBM: "_WBM.tif",
}

_INDIVIDUAL_MASKS = (MaskType.DEM, MaskType.EDM, MaskType.FLM, MaskType.HEM, MaskType.WBM)


def mask_description(mask: MaskType) -> str:
    return _MASK_DESCRIPTIONS.get(mask, mask.name or str(mask))


def mask_file_suffix(mask: MaskType) -> str:
    return _MASK_SUFFIXES.get(mask, ".tif")


def individual_masks(masks: MaskType) -> list[MaskType]:
    return [m for m in _INDIVIDUAL_MASKS if m in masks]
