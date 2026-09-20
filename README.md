# Copernicus GLO DEM Downloader (QGIS Plugin)

A QGIS plugin for browsing and downloading Copernicus Digital Elevation Model (GLO-30, GLO-90) tiles directly from the public, anonymous-access [AWS Open Data](https://registry.opendata.aws/copernicus-dem/) buckets.

## Features

- **No credentials required** — GLO-30/GLO-90 are public AWS S3 buckets
- **Tile index preview** — a shared 1°×1° tile grid layer (same for both datasets) you can load once and select tiles from
- **Two ways to define the download area** — select exact tiles in the index layer, or use the current map canvas extent
- **Mask layer selection** — DEM (always included), EDM, FLM, HEM, WBM
- **Background download** — runs on a `QgsTask` with a progress bar and cancel button; QGIS stays responsive
- **Resumable** — re-running a download with the same output folder skips files already downloaded
- **Optional auto-load** — off by default; when enabled, downloaded rasters are added to the map inside a `GLO-30`/`GLO-90` group layer
- **Safety limit** — downloads are capped at 500 tiles per run; there's no way to accidentally trigger a full-dataset download

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

If `boto3` isn't installed, the plugin still loads and appears in the toolbar/menu, but clicking it shows a dialog with the exact command to run instead of failing silently.

## Usage

1. Open the plugin from the toolbar icon or **Raster → Copernicus GLO DEM Downloader**.
2. On first open, you'll be asked whether to load the tile index grid — say yes to see the 1°×1° tile boundaries on the map (this is the same grid for both datasets, fetched once).
3. Check **GLO-30** and/or **GLO-90** to pick which dataset(s) to download.
4. Define the area to download — either select tile features in the index layer, or just pan/zoom the map — then click **Use Extent (selected tiles or map view)**. A download always requires an area; there's no "download everything" option, and areas matching more than 500 tiles are rejected.
5. Select which mask layers to download (DEM is always included).
6. Choose an output folder — the exact per-dataset subfolder(s) that will be created are shown live under **Will save to**.
7. Optionally enable **Auto-load downloaded rasters into a group layer**.
8. Click **Download**. Progress and status are shown in the dialog; click **Cancel** to stop.

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
