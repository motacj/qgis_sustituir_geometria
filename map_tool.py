"""Herramienta de mapa para sustituir una geometría conservando atributos."""

from __future__ import annotations

from dataclasses import dataclass

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QCursor
from qgis.PyQt.QtWidgets import QInputDialog, QMessageBox
from qgis.core import (
    Qgis,
    QgsCoordinateTransform,
    QgsCsException,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsHighlight, QgsMapTool

PLUGIN_TITLE = "Sustituir geometría"


@dataclass(frozen=True)
class FeatureCandidate:
    """Copia estable de la entidad localizada por un clic."""

    layer: QgsVectorLayer
    feature_id: int
    geometry: QgsGeometry
    label: str
    distance: float
    layer_order: int


class GeometryReplacementMapTool(QgsMapTool):
    """Primer clic: destino. Segundo clic: geometría que se copiará."""

    SEARCH_TOLERANCE_PIXELS = 8

    def __init__(self, iface):
        super().__init__(iface.mapCanvas())
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.target = None
        self.target_highlight = None
        self.source_highlight = None
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def start(self):
        self.reset()
        self._info(
            "Primer clic: señala la entidad cuyos atributos y FID "
            "se conservarán.",
            duration=8,
        )

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.reset()
            self._info(
                "Selección cancelada. Señala de nuevo la primera geometría."
            )
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.target is None:
            candidate = self._choose_candidate(event.mapPoint(), target=None)
            if candidate is None:
                self._warning(
                    "No se encontró ninguna geometría vectorial "
                    "bajo el cursor."
                )
                return
            self.target = candidate
            self._set_target_highlight(candidate)
            self._info(
                f"Destino: {candidate.label}. Segundo clic: señala "
                "la geometría que se copiará.",
                duration=8,
            )
            return

        source = self._choose_candidate(event.mapPoint(), target=self.target)
        if source is None:
            self._warning(
                "No se encontró una segunda geometría compatible. "
                "Debe ser de la misma familia geométrica."
            )
            return
        self._set_source_highlight(source)
        try:
            self._confirm_and_replace(self.target, source)
        finally:
            self._clear_source_highlight()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reset()
            self._info(
                "Selección cancelada. Señala de nuevo la primera geometría."
            )
            return
        super().keyPressEvent(event)

    def deactivate(self):
        self.reset()
        super().deactivate()

    def reset(self):
        self.target = None
        self._delete_highlight("target_highlight")
        self._delete_highlight("source_highlight")

    def _choose_candidate(self, map_point, target):
        candidates = self._candidates_at(map_point, target)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        options = [
            f"{index + 1}. {candidate.label}"
            for index, candidate in enumerate(candidates)
        ]
        selected, accepted = QInputDialog.getItem(
            self.iface.mainWindow(),
            PLUGIN_TITLE,
            "Hay varias entidades bajo el cursor. Elige una:",
            options,
            0,
            False,
        )
        if not accepted:
            return None
        return candidates[options.index(selected)]

    def _candidates_at(self, map_point, target):
        tolerance = (
            self.canvas.mapUnitsPerPixel() * self.SEARCH_TOLERANCE_PIXELS
        )
        map_rectangle = QgsRectangle(
            map_point.x() - tolerance,
            map_point.y() - tolerance,
            map_point.x() + tolerance,
            map_point.y() + tolerance,
        )
        map_crs = self.canvas.mapSettings().destinationCrs()
        context = QgsProject.instance().transformContext()
        target_type = (
            QgsWkbTypes.geometryType(target.layer.wkbType())
            if target is not None
            else None
        )
        candidates = []

        for layer_order, layer in enumerate(self.canvas.layers()):
            if (
                not isinstance(layer, QgsVectorLayer)
                or not layer.isValid()
                or not layer.isSpatial()
            ):
                continue
            if (
                target_type is not None
                and QgsWkbTypes.geometryType(layer.wkbType()) != target_type
            ):
                continue
            try:
                coordinate_transform = QgsCoordinateTransform(
                    map_crs, layer.crs(), context
                )
                layer_rectangle = coordinate_transform.transformBoundingBox(
                    map_rectangle
                )
                layer_point = coordinate_transform.transform(
                    QgsPointXY(map_point)
                )
            except (QgsCsException, TypeError, ValueError):
                layer_rectangle = None
                layer_point = None
            if layer_rectangle is None or layer_point is None:
                continue

            point_geometry = QgsGeometry.fromPointXY(QgsPointXY(layer_point))
            layer_tolerance = (
                max(layer_rectangle.width(), layer_rectangle.height()) / 2.0
            )
            request = QgsFeatureRequest().setFilterRect(layer_rectangle)
            for feature in layer.getFeatures(request):
                if (
                    target is not None
                    and layer.id() == target.layer.id()
                    and feature.id() == target.feature_id
                ):
                    continue
                geometry = feature.geometry()
                if geometry is None or geometry.isEmpty():
                    continue
                distance = geometry.distance(point_geometry)
                if distance < 0 or distance > layer_tolerance:
                    continue
                candidates.append(
                    FeatureCandidate(
                        layer=layer,
                        feature_id=feature.id(),
                        geometry=QgsGeometry(geometry),
                        label=self._feature_label(layer, feature),
                        distance=distance,
                        layer_order=layer_order,
                    )
                )

        return sorted(
            candidates,
            key=lambda item: (
                item.layer_order,
                item.distance,
                item.feature_id,
            ),
        )

    @staticmethod
    def _feature_label(layer, feature):
        detail = ""
        field_name = layer.displayField()
        if field_name and layer.fields().indexOf(field_name) >= 0:
            value = feature[field_name]
            if value is not None and str(value).strip():
                detail = f" · {field_name}: {value}"
        return f"{layer.name()}{detail} · FID {feature.id()}"

    def _confirm_and_replace(self, target, source):
        if not self._layer_still_exists(
            target.layer
        ) or not self._layer_still_exists(source.layer):
            self._error(
                "Una de las capas ya no está disponible en el proyecto."
            )
            self.reset()
            return

        try:
            replacement = self._replacement_geometry(target, source)
        except (TypeError, ValueError, RuntimeError) as exception:
            self._error(str(exception))
            return

        crs_note = ""
        if target.layer.crs() != source.layer.crs():
            crs_note = (
                "\n\nLa geometría se transformará al CRS de la capa "
                "de destino."
            )
        question = (
            "Se sustituirá únicamente la geometría de:\n"
            f"{target.label}\n\n"
            "por la geometría de:\n"
            f"{source.label}\n\n"
            "Se conservarán el FID y todos los atributos de la primera "
            "entidad. "
            "La segunda entidad no se modificará."
            f"{crs_note}\n\n¿Deseas continuar?"
        )
        answer = QMessageBox.question(
            self.iface.mainWindow(),
            PLUGIN_TITLE,
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self._info(
                "Operación cancelada. Puedes elegir otra segunda geometría."
            )
            return

        target_layer = target.layer
        if not target_layer.isEditable() and not target_layer.startEditing():
            self._error(
                "La capa de destino no permite iniciar la edición. "
                "Comprueba sus permisos y el proveedor de datos."
            )
            return

        target_layer.beginEditCommand("Sustituir geometría mediante dos clics")
        try:
            changed = target_layer.changeGeometry(
                target.feature_id, replacement, True
            )
            if not changed:
                raise RuntimeError(
                    "QGIS no pudo sustituir la geometría de la "
                    "primera entidad."
                )
            target_layer.endEditCommand()
        except Exception as exception:
            target_layer.destroyEditCommand()
            self._error(str(exception))
            return

        target_layer.triggerRepaint()
        self.canvas.refresh()
        self.reset()
        self.iface.messageBar().pushMessage(
            PLUGIN_TITLE,
            "Geometría sustituida. Los atributos se han conservado "
            "y el cambio está disponible para Deshacer. QGIS no lo "
            "ha guardado automáticamente.",
            level=Qgis.MessageLevel.Success,
            duration=10,
        )

    @staticmethod
    def _replacement_geometry(target, source):
        target_type = QgsWkbTypes.geometryType(target.layer.wkbType())
        source_type = QgsWkbTypes.geometryType(source.layer.wkbType())
        if target_type != source_type:
            raise TypeError(
                "Las dos entidades deben pertenecer a la misma "
                "familia geométrica."
            )

        geometry = QgsGeometry(source.geometry)
        if target.layer.crs() != source.layer.crs():
            if (
                not target.layer.crs().isValid()
                or not source.layer.crs().isValid()
            ):
                raise ValueError(
                    "No se puede transformar la geometría porque "
                    "uno de los CRS no es válido."
                )
            transform = QgsCoordinateTransform(
                source.layer.crs(),
                target.layer.crs(),
                QgsProject.instance().transformContext(),
            )
            geometry.transform(transform)

        coerced = geometry.coerceToType(target.layer.wkbType())
        if len(coerced) != 1 or coerced[0].isEmpty():
            raise ValueError(
                "La segunda geometría no puede convertirse sin "
                "pérdida en el tipo exacto de la capa de destino."
            )
        return coerced[0]

    def _set_target_highlight(self, candidate):
        self._delete_highlight("target_highlight")
        self.target_highlight = self._create_highlight(
            candidate,
            QColor(220, 45, 45, 255),
            QColor(220, 45, 45, 65),
        )

    def _set_source_highlight(self, candidate):
        self._delete_highlight("source_highlight")
        self.source_highlight = self._create_highlight(
            candidate,
            QColor(25, 150, 70, 255),
            QColor(25, 150, 70, 65),
        )

    def _clear_source_highlight(self):
        self._delete_highlight("source_highlight")

    def _create_highlight(self, candidate, outline, fill):
        highlight = QgsHighlight(
            self.canvas, candidate.geometry, candidate.layer
        )
        highlight.setColor(outline)
        highlight.setFillColor(fill)
        highlight.setWidth(3)
        highlight.show()
        return highlight

    def _delete_highlight(self, attribute_name):
        highlight = getattr(self, attribute_name)
        if highlight is not None:
            highlight.hide()
            scene = highlight.scene()
            if scene is not None:
                scene.removeItem(highlight)
            setattr(self, attribute_name, None)

    @staticmethod
    def _layer_still_exists(layer):
        return QgsProject.instance().mapLayer(layer.id()) is not None

    def _info(self, message, duration=5):
        self.iface.messageBar().pushMessage(
            PLUGIN_TITLE,
            message,
            level=Qgis.MessageLevel.Info,
            duration=duration,
        )

    def _warning(self, message):
        self.iface.messageBar().pushMessage(
            PLUGIN_TITLE,
            message,
            level=Qgis.MessageLevel.Warning,
            duration=6,
        )

    def _error(self, message):
        QMessageBox.critical(self.iface.mainWindow(), PLUGIN_TITLE, message)
