"""QgsTask wrapper: runs DownloaderCore on a background thread with progress + cancel support."""

from __future__ import annotations

from pathlib import Path

from qgis.core import Qgis, QgsMessageLog, QgsTask

from .download_state import FileState  # noqa: F401  (re-exported for convenience)
from .downloader import DownloaderCore, DownloadOptions, DownloadResult
from .s3_client import create_client

LOG_TAG = "Copernicus GLO DEM Downloader"

# The resolve phase (fetching the tile list + listing each matching tile's folder)
# can take a while for a large area, before any file has actually started downloading.
# It gets its own slice of the progress bar so it never looks stuck at 0%.
RESOLVE_PROGRESS_SHARE = 30.0


class DownloadTask(QgsTask):
    """Resolves matching tiles, then downloads them, reporting progress via QgsTask.setProgress.

    `status_text` is updated throughout the run and can be polled by the dialog
    (e.g. on a timer) since QgsTask has no built-in text-status signal.
    """

    def __init__(self, options: DownloadOptions, cache_dir: Path | None = None):
        super().__init__("Downloading Copernicus DEM tiles", QgsTask.CanCancel)
        self._options = options
        self._cache_dir = cache_dir
        self.result: DownloadResult | None = None
        self.error: str | None = None
        self.status_text: str = "Starting..."

    def run(self) -> bool:
        try:
            client = create_client()
            core = DownloaderCore(client, self._options)

            self.status_text = f"Fetching tile list for {self._options.dataset.key}..."
            self.setProgress(0.0)

            def on_resolve_progress(listed: int, total: int) -> bool:
                if self.isCanceled():
                    return False
                self.status_text = f"Finding matching files... ({listed}/{total} tile folders checked)"
                if total:
                    self.setProgress(RESOLVE_PROGRESS_SHARE * listed / total)
                return True

            objects = core.resolve_objects(
                log=self._log, cache_dir=self._cache_dir, resolve_progress_callback=on_resolve_progress
            )
            if objects is None or self.isCanceled():
                self.result = DownloadResult(cancelled=True)
                return False

            total = len(objects)
            self.status_text = f"Downloading {total} file(s)..."

            def on_progress(completed: int, skipped: int, failed: int, _total: int) -> bool:
                if self.isCanceled():
                    return False
                done = completed + skipped + failed
                self.status_text = (
                    f"Downloading... {done}/{total} files "
                    f"({completed} downloaded, {skipped} skipped, {failed} failed)"
                )
                if total:
                    download_share = 100.0 - RESOLVE_PROGRESS_SHARE
                    self.setProgress(RESOLVE_PROGRESS_SHARE + download_share * done / total)
                return True

            self.result = core.run(objects, progress_callback=on_progress, log=self._log)
            return not self.result.cancelled
        except Exception as exc:  # noqa: BLE001 - surfaced to the dialog via self.error
            self.error = str(exc)
            return False

    def _log(self, message: str) -> None:
        QgsMessageLog.logMessage(message, LOG_TAG, level=Qgis.Info)
