"""Main plugin dialog: dataset/mask selection, extent picker, tile index preview, download."""

from __future__ import annotations

import os
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRasterLayer,
)
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox

from .core.bounding_box import BoundingBox
from .core.dataset import GLO_30, GLO_90, KNOWN_DATASETS, MaskType
from .core.download_task import DownloadTask
from .core.downloader import DownloadOptions, format_bytes
from .core.s3_client import create_client
from .core.tile_index_layer import TILE_NAME_FIELD, add_or_replace_tile_index_layer, find_tile_index_layer
from .core.tile_list import fetch_tile_names

UI_PATH = os.path.join(os.path.dirname(__file__), "ui", "dialog_base.ui")
FORM_CLASS, _ = uic.loadUiType(UI_PATH)

WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")


class CopernicusGloDemDownloaderDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, cache_dir: Path, parent=None):
        super().__init__(parent)
        # Qt.Tool (with a parent set to the QGIS main window) keeps this dialog
        # floating above QGIS at all times, without forcing it above other
        # applications the way a global "always on top" hint would.
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        self.setupUi(self)

        self._iface = iface
        self._cache_dir = cache_dir
        self._bbox: BoundingBox | None = None
        self._selected_tile_names: list[str] | None = None
        self._task: DownloadTask | None = None

        self._connect_signals()
        self._update_output_placeholder()
        self._update_save_paths_preview()
        self._maybe_prompt_tile_index()

    def _connect_signals(self) -> None:
        self.btnUseCurrentExtent.clicked.connect(self._on_use_current_extent)
        self.btnBrowseOutput.clicked.connect(self._on_browse_output)
        self.btnPreviewIndex.clicked.connect(self._on_preview_index)
        self.btnDownload.clicked.connect(self._on_download)
        self.btnCancel.clicked.connect(self._on_cancel)
        self.btnClose.clicked.connect(self.close)

        self.checkGlo30.toggled.connect(self._update_save_paths_preview)
        self.checkGlo90.toggled.connect(self._update_save_paths_preview)
        self.outputLineEdit.textChanged.connect(self._update_save_paths_preview)

    # -- dataset selection ----------------------------------------------------

    def _selected_datasets(self) -> list:
        datasets = []
        if self.checkGlo30.isChecked():
            datasets.append(GLO_30)
        if self.checkGlo90.isChecked():
            datasets.append(GLO_90)
        return datasets

    # -- tile index (universal grid, loaded once) ------------------------------

    def _maybe_prompt_tile_index(self) -> None:
        if find_tile_index_layer() is not None:
            return  # already loaded from a previous session/dialog open

        answer = QMessageBox.question(
            self,
            "Tile Index",
            "Show the Copernicus DEM tile index grid on the map?\n\n"
            "This downloads the tile list once and draws the 1°×1° grid "
            "(same for GLO-30 and GLO-90) so you can select an area to download.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            self._load_tile_index_layer()

    def _load_tile_index_layer(self) -> None:
        try:
            client = create_client()
            self.statusLabel.setText("Fetching tile list...")
            QgsApplication.processEvents()
            # The tile grid is identical for GLO-30 and GLO-90; either dataset's
            # tile list can be used to build the shared index layer.
            tile_names = fetch_tile_names(client, GLO_30, cache_dir=self._cache_dir)
            add_or_replace_tile_index_layer(tile_names)
            self.statusLabel.setText(f"Loaded {len(tile_names):,} tiles into the index layer.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Tile index", f"Could not load the tile index:\n{exc}")
            self.statusLabel.setText("")

    def _on_preview_index(self) -> None:
        self._load_tile_index_layer()

    # -- extent -----------------------------------------------------------------

    def _on_use_current_extent(self) -> None:
        index_layer = find_tile_index_layer()
        if index_layer is not None and index_layer.selectedFeatureCount() > 0:
            # Use the exact selected tiles, not their union bounding box: two adjacent
            # selected tiles form a bbox whose edges touch neighboring tiles too, which
            # would pull in tiles the user never selected (intersects_tile treats
            # edge-touching as a match). Sending exact tile names avoids that entirely.
            self._bbox = None
            self._selected_tile_names = [
                feature[TILE_NAME_FIELD] for feature in index_layer.selectedFeatures()
            ]
            self.extentValueLabel.setText(
                f"{len(self._selected_tile_names)} selected tile(s) from the tile index"
            )
            return

        self._selected_tile_names = None
        canvas = self._iface.mapCanvas()
        rect = canvas.extent()
        source_crs = canvas.mapSettings().destinationCrs()
        self._bbox = BoundingBox.from_qgis_rectangle(rect, source_crs, WGS84)
        self.extentValueLabel.setText(str(self._bbox))

    # -- output folder ----------------------------------------------------------

    def _update_output_placeholder(self) -> None:
        if not self.outputLineEdit.text():
            self.outputLineEdit.setPlaceholderText(os.path.join(os.path.expanduser("~"), "CopernicusDEM"))

    def _on_browse_output(self) -> None:
        current = self.outputLineEdit.text() or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(self, "Select output folder", current)
        if chosen:
            self.outputLineEdit.setText(chosen)

    def _resolve_output_dir(self) -> str:
        return self.outputLineEdit.text().strip() or self.outputLineEdit.placeholderText()

    def _update_save_paths_preview(self) -> None:
        """Show exactly which per-dataset subfolder(s) will be created under the output folder,
        so the user isn't surprised by a GLO-30/GLO-90 subfolder being added automatically."""
        datasets = self._selected_datasets()
        if not datasets:
            self.savePathsValueLabel.setText("Select at least one dataset.")
            return

        output_dir = self._resolve_output_dir()
        lines = [os.path.join(output_dir, dataset.key) for dataset in datasets]
        self.savePathsValueLabel.setText("\n".join(lines))

    # -- masks ------------------------------------------------------------------

    def _selected_masks(self) -> MaskType:
        masks = MaskType.DEM
        if self.checkMaskEdm.isChecked():
            masks |= MaskType.EDM
        if self.checkMaskFlm.isChecked():
            masks |= MaskType.FLM
        if self.checkMaskHem.isChecked():
            masks |= MaskType.HEM
        if self.checkMaskWbm.isChecked():
            masks |= MaskType.WBM
        return masks

    # -- download -----------------------------------------------------------------

    def _on_download(self) -> None:
        datasets = self._selected_datasets()
        if not datasets:
            QMessageBox.information(self, "Download", "Select at least one dataset first.")
            return

        if self._bbox is None and not self._selected_tile_names:
            QMessageBox.warning(
                self,
                "No area selected",
                "Downloading the entire dataset (thousands of tiles) is not supported.\n\n"
                "Select tiles in the tile index layer, or click "
                "'Use Extent (selected tiles or map view)' to use the current map view, "
                "before downloading.",
            )
            return

        output_dir = self._resolve_output_dir()
        masks = self._selected_masks()

        self.btnDownload.setEnabled(False)
        self.btnCancel.setEnabled(True)
        self.progressBar.setValue(0)

        self._pending_datasets = list(datasets)
        self._download_output_dir = output_dir
        self._download_masks = masks
        self._auto_load = self.checkAutoLoad.isChecked()
        self._run_next_dataset_download()

    def _run_next_dataset_download(self) -> None:
        if not self._pending_datasets:
            self.btnDownload.setEnabled(True)
            self.btnCancel.setEnabled(False)
            self.statusLabel.setText("All downloads finished.")
            return

        dataset = self._pending_datasets.pop(0)
        dataset_output_dir = os.path.join(self._download_output_dir, dataset.key)

        self.progressBar.setValue(0)

        options = DownloadOptions(
            dataset=dataset,
            output_directory=dataset_output_dir,
            masks=self._download_masks,
            bounding_box=self._bbox,
            selected_tile_names=self._selected_tile_names,
        )

        self.statusLabel.setText(f"Preparing {dataset.key}...")
        self._task = DownloadTask(options, cache_dir=self._cache_dir)
        self._task.taskCompleted.connect(lambda: self._on_task_finished(dataset, dataset_output_dir))
        self._task.taskTerminated.connect(lambda: self._on_task_finished(dataset, dataset_output_dir))
        QgsApplication.taskManager().addTask(self._task)

        # Poll status_text/progress on a timer rather than relying solely on
        # progressChanged, which Qt may not emit if the numeric value repeats
        # (e.g. staying at 0% while the tile list is still being fetched).
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._on_status_timer)
        self._status_timer.start(300)

    def _on_status_timer(self) -> None:
        if self._task is None:
            self._status_timer.stop()
            return
        self.progressBar.setValue(int(self._task.progress()))
        self.statusLabel.setText(self._task.status_text)

    def _on_task_finished(self, dataset, dataset_output_dir: str) -> None:
        if getattr(self, "_status_timer", None) is not None:
            self._status_timer.stop()

        task = self._task
        self._task = None

        if task is None:
            return

        if task.error:
            QMessageBox.warning(self, "Download failed", f"{dataset.key}: {task.error}")
        elif task.result is not None:
            result = task.result
            if not result.cancelled:
                self.progressBar.setValue(100)
            if result.cancelled:
                self.statusLabel.setText(f"{dataset.key}: cancelled.")
            else:
                self.statusLabel.setText(
                    f"{dataset.key}: {result.completed_files} downloaded, "
                    f"{result.skipped_files} skipped, {result.failed_files} failed "
                    f"({format_bytes(result.downloaded_bytes)})."
                )
                if self._auto_load and not result.cancelled:
                    self._load_rasters_into_group(dataset, dataset_output_dir)

        self._run_next_dataset_download()

    def _on_cancel(self) -> None:
        if self._task is not None:
            self._task.cancel()
        self._pending_datasets = []

    # -- auto-load ----------------------------------------------------------------

    def _load_rasters_into_group(self, dataset, dataset_output_dir: str) -> None:
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        group_name = dataset.key
        group = root.findGroup(group_name)
        if group is None:
            group = root.insertGroup(0, group_name)

        tif_paths = sorted(Path(dataset_output_dir).rglob("*.tif"))
        for tif_path in tif_paths:
            layer = QgsRasterLayer(str(tif_path), tif_path.stem)
            if not layer.isValid():
                continue
            project.addMapLayer(layer, addToLegend=False)
            group.addLayer(layer)

        self._iface.messageBar().pushMessage(
            "Copernicus GLO DEM Downloader",
            f"Loaded {len(tif_paths)} raster(s) into group '{group_name}'.",
            level=Qgis.Info,
        )
