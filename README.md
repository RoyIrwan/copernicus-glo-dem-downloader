# Copernicus GLO DEM Downloader (QGIS Plugin)

A QGIS plugin for browsing and downloading Copernicus Digital Elevation Model (GLO-30, GLO-90) tiles directly from the public, anonymous-access [AWS Open Data](https://registry.opendata.aws/copernicus-dem/) buckets.

## Features

- **No credentials required** — GLO-30/GLO-90 are public AWS S3 buckets
- **Tile index preview** — toggle a dataset on to see its 1°×1° tile grid drawn on the map before downloading
- **Use current map extent** — one click to set the download bounding box from the active canvas view
- **Mask layer selection** — DEM (always included), EDM, FLM, HEM, WBM
- **Background download** — runs on a `QgsTask` with a progress bar and cancel button; QGIS stays responsive
- **Resumable** — re-running a download with the same output folder skips files already downloaded
- **Optional auto-load** — off by default; when enabled, downloaded rasters are added to the map inside a `GLO-30`/`GLO-90` group layer

## Data Source

- `s3://copernicus-dem-30m` — GLO-30, 30m global resolution
- `s3://copernicus-dem-90m` — GLO-90, 90m global resolution

Both buckets are public and require no AWS account. Each tile folder contains the elevation raster (`_DEM.tif`) plus optional quality layers under `AUXFILES/` (`_EDM.tif`, `_FLM.tif`, `_HEM.tif`, `_WBM.tif`).

> EEA-10 (10m European DEM) is not available here — it is a Copernicus Contributing Missions (CCM) dataset requiring a separate access request via the Copernicus Data Space Ecosystem, and is not part of the public AWS mirror.

## Requirements

- QGIS 3.22+
- `boto3` available to QGIS's Python environment (see Installation)

## Installation

### 1. Install boto3 into QGIS's Python

QGIS uses its own bundled Python. Install `boto3` into it:

**Windows (OSGeo4W shell):**
```
python -m pip install boto3
```

**Linux/macOS (from a terminal where `qgis` Python is on PATH):**
```
pip3 install boto3 --user
```

### 2. Install the plugin

Copy (or symlink) the `copernicus_glo_dem_downloader/` folder into your QGIS profile's plugin directory:

- Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

Then enable it in QGIS via **Plugins → Manage and Install Plugins → Installed**.

## Usage

1. Open the plugin from the toolbar icon or **Raster → Copernicus GLO DEM Downloader**.
2. Check **GLO-30** and/or **GLO-90** — the tile index grid for the enabled dataset(s) is drawn on the map.
3. Optionally click **Use Current Map Extent** to limit the download to your current view, or leave it empty for the full dataset (not recommended without a very large disk).
4. Select which mask layers to download (DEM is always included).
5. Choose an output folder.
6. Optionally enable **Auto-load downloaded rasters into a group layer**.
7. Click **Download**. Progress is shown in the dialog; click **Cancel** to stop.

## Development

The `core/` package has no Qt/QGIS dependency except `tile_index_layer.py` (which builds a `QgsVectorLayer`) and is unit-testable with plain `pytest`:

```bash
pip install -r requirements-dev.txt
pytest
```

`dialog.py`, `plugin.py`, and `core/download_task.py` require a running QGIS Python environment and are exercised manually inside QGIS.

## Scope

This plugin downloads raw Copernicus DEM COG GeoTIFF tiles as-is — no mosaicking, reprojection, or clipping is performed.

## License

Apache 2.0 License

## Acknowledgments

- Data provided by the [Copernicus Digital Elevation Model AWS Open Data registry](https://registry.opendata.aws/copernicus-dem/)
- Copernicus DEM is produced by the European Space Agency (ESA)
