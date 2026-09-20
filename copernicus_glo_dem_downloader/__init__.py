"""QGIS plugin entry point."""


def classFactory(iface):
    from .plugin import CopernicusGloDemDownloaderPlugin

    return CopernicusGloDemDownloaderPlugin(iface)
