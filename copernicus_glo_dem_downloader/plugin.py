"""Main plugin class registered with QGIS via classFactory."""

from __future__ import annotations

import os
from pathlib import Path

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

PLUGIN_DIR = os.path.dirname(__file__)

BOTO3_INSTALL_MESSAGE = (
    "This plugin requires the 'boto3' Python package, which is not installed in "
    "QGIS's Python environment.\n\n"
    "Install it by running this in the OSGeo4W Shell (Windows) or a terminal where "
    "QGIS's Python is on PATH:\n\n"
    "    python -m pip install boto3\n\n"
    "Then restart QGIS."
)


class CopernicusGloDemDownloaderPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.actions: list[QAction] = []
        self.menu = "&Copernicus GLO DEM Downloader"
        self.dialog = None

    def initGui(self) -> None:
        icon_path = os.path.join(PLUGIN_DIR, "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        action = QAction(icon, "Download Copernicus GLO DEM...", self.iface.mainWindow())
        action.triggered.connect(self.run)
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToRasterMenu(self.menu, action)
        self.actions.append(action)

    def unload(self) -> None:
        for action in self.actions:
            self.iface.removePluginRasterMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        self.actions = []

    def run(self) -> None:
        try:
            import boto3  # noqa: F401
        except ImportError:
            QMessageBox.critical(self.iface.mainWindow(), "Missing dependency", BOTO3_INSTALL_MESSAGE)
            return

        from .dialog import CopernicusGloDemDownloaderDialog

        cache_dir = Path.home() / ".copernicus_glo_dem_downloader" / "cache"
        if self.dialog is None:
            self.dialog = CopernicusGloDemDownloaderDialog(
                self.iface, cache_dir, parent=self.iface.mainWindow()
            )
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
