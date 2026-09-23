"""Integración del complemento con la interfaz de QGIS."""

from __future__ import annotations

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .map_tool import GeometryReplacementMapTool

PLUGIN_TITLE = "Sustituir geometría"


class ReplaceGeometryPlugin:
    """Añade una herramienta de dos clics para copiar una geometría."""

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.map_tool = None
        self.previous_map_tool = None

    def initGui(self):
        icon = QIcon(os.path.join(self.plugin_dir, "icon.png"))
        self.action = QAction(
            icon,
            "Sustituir geometría mediante dos clics",
            self.iface.mainWindow(),
        )
        self.action.setObjectName("ReplaceGeometryTwoClicksAction")
        self.action.setCheckable(True)
        self.action.setToolTip(
            "Primer clic: entidad que se modificará. "
            "Segundo clic: geometría que se copiará."
        )
        self.map_tool = GeometryReplacementMapTool(self.iface)
        self.map_tool.deactivated.connect(self._on_tool_deactivated)
        self.action.triggered.connect(self._toggle_tool)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu(PLUGIN_TITLE, self.action)

    def unload(self):
        self._deactivate_tool(restore_previous=True)
        if self.action is None:
            return
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginVectorMenu(PLUGIN_TITLE, self.action)
        self.action.deleteLater()
        self.action = None
        self.map_tool = None
        self.previous_map_tool = None

    def _toggle_tool(self, checked):
        if checked:
            self._activate_tool()
        else:
            self._deactivate_tool(restore_previous=True)

    def _activate_tool(self):
        if self.map_tool is None:
            return
        current = self.canvas.mapTool()
        if current is not self.map_tool:
            self.previous_map_tool = current
        self.canvas.setMapTool(self.map_tool)
        self.map_tool.start()

    def _deactivate_tool(self, restore_previous):
        if self.map_tool is None:
            return
        self.map_tool.reset()
        if self.canvas.mapTool() is not self.map_tool:
            return
        previous = self.previous_map_tool
        self.previous_map_tool = None
        if (
            restore_previous
            and previous is not None
            and previous is not self.map_tool
        ):
            try:
                self.canvas.setMapTool(previous)
                return
            except RuntimeError:
                pass
        self.canvas.unsetMapTool(self.map_tool)

    def _on_tool_deactivated(self):
        if self.map_tool is not None:
            self.map_tool.reset()
        if self.action is not None and self.action.isChecked():
            self.action.blockSignals(True)
            self.action.setChecked(False)
            self.action.blockSignals(False)
