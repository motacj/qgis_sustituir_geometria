"""Entrada del complemento Sustituir geometría."""


def classFactory(iface):
    """Devuelve la instancia utilizada por QGIS."""
    from .plugin import ReplaceGeometryPlugin

    return ReplaceGeometryPlugin(iface)
