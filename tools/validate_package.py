#!/usr/bin/env python3
"""Validaciones estructurales y de seguridad del paquete QGIS."""

from __future__ import annotations

import ast
import configparser
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath


PLUGIN_NAME = "qgis_sustituir_geometria"
MAX_BYTES = 25 * 1024 * 1024
REQUIRED_METADATA = (
    "name",
    "qgisMinimumVersion",
    "description",
    "about",
    "version",
    "author",
    "email",
    "homepage",
    "repository",
    "tracker",
)
REQUIRED_FILES = {
    f"{PLUGIN_NAME}/__init__.py",
    f"{PLUGIN_NAME}/plugin.py",
    f"{PLUGIN_NAME}/map_tool.py",
    f"{PLUGIN_NAME}/metadata.txt",
    f"{PLUGIN_NAME}/README.md",
    f"{PLUGIN_NAME}/CHANGELOG.md",
    f"{PLUGIN_NAME}/PRIVACY.md",
    f"{PLUGIN_NAME}/LICENSE",
    f"{PLUGIN_NAME}/icon.png",
}
LEGACY_ENUMS = (
    re.compile(r"QMessageBox\.(?:Yes|No|Ok|Cancel)\b"),
    re.compile(r"Qt\.(?:LeftButton|RightButton|Key_Escape|CrossCursor)\b"),
    re.compile(r"QgsWkbTypes\.(?:PointGeometry|LineGeometry|PolygonGeometry)\b"),
)
NETWORK_PATTERNS = (
    re.compile(r"\brequests\."),
    re.compile(r"\burllib\."),
    re.compile(r"\bQNetworkAccessManager\b"),
    re.compile(r"\bsocket\."),
)


def validate(archive: Path) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    if not archive.is_file():
        return [f"No existe el paquete: {archive}"], warnings
    if archive.stat().st_size > MAX_BYTES:
        errors.append("El paquete supera 25 MB")

    try:
        with zipfile.ZipFile(archive) as package:
            bad = package.testzip()
            if bad:
                errors.append(f"Archivo corrupto dentro del ZIP: {bad}")
            names = [name for name in package.namelist() if not name.endswith("/")]
            roots = {PurePosixPath(name).parts[0] for name in names}
            if roots != {PLUGIN_NAME}:
                errors.append(f"El ZIP debe tener una única carpeta raíz {PLUGIN_NAME}")
                return errors, warnings

            missing = sorted(REQUIRED_FILES - set(names))
            if missing:
                errors.append("Faltan archivos: " + ", ".join(missing))

            metadata_text = package.read(f"{PLUGIN_NAME}/metadata.txt").decode("utf-8")
            metadata = configparser.ConfigParser(interpolation=None)
            metadata.optionxform = str
            metadata.read_string(metadata_text)
            section = metadata["general"]
            for key in REQUIRED_METADATA:
                if not section.get(key, "").strip():
                    errors.append(f"Metadato obligatorio vacío: {key}")
            if section.get("version") != "1.0.1":
                errors.append("La versión del paquete debe ser 1.0.1")
            if section.get("category") != "Vector":
                errors.append("La categoría debe ser Vector")
            expected_urls = {
                "homepage": "https://github.com/motacj/qgis_sustituir_geometria#readme",
                "repository": "https://github.com/motacj/qgis_sustituir_geometria",
                "tracker": "https://github.com/motacj/qgis_sustituir_geometria/issues",
            }
            for key, expected in expected_urls.items():
                if section.get(key) != expected:
                    errors.append(f"URL incorrecta en {key}: se esperaba {expected}")

            python_sources = {}
            for name in names:
                parts = PurePosixPath(name).parts
                if "__pycache__" in parts or name.endswith((".pyc", ".pyo")):
                    errors.append(f"Caché Python incluido: {name}")
                if not name.endswith(".py"):
                    continue
                source = package.read(name).decode("utf-8")
                python_sources[name] = source
                try:
                    ast.parse(source, filename=name)
                except SyntaxError as exception:
                    errors.append(f"Error de sintaxis en {name}: {exception}")
                for pattern in LEGACY_ENUMS:
                    if pattern.search(source):
                        errors.append(
                            f"Enumeración antigua rechazada por QGIS en {name}: {pattern.pattern}"
                        )
                for pattern in NETWORK_PATTERNS:
                    if pattern.search(source):
                        errors.append(f"Acceso de red no previsto en {name}: {pattern.pattern}")

            combined = "\n".join(python_sources.values())
            required_code = {
                "Falta la herramienta de dos clics": "canvasReleaseEvent" in combined,
                "Falta la transformación entre CRS": "QgsCoordinateTransform" in combined,
                "Falta la conversión al WKB de destino": "coerceToType" in combined,
                "Falta la orden reversible": "beginEditCommand" in combined
                and "endEditCommand" in combined,
                "Falta la conservación de valores de campos": re.search(
                    r"changeGeometry\(\s*target\.feature_id,\s*replacement,\s*True\s*\)",
                    combined,
                    re.DOTALL,
                )
                is not None,
                "Se guarda automáticamente la capa": "commitChanges(" not in combined,
                "Falta la opción de cancelar la orden": "destroyEditCommand" in combined,
                "Falta la elección de entidades superpuestas": "QInputDialog.getItem" in combined,
            }
            errors.extend(message for message, passed in required_code.items() if not passed)
    except (OSError, KeyError, UnicodeDecodeError, zipfile.BadZipFile) as exception:
        errors.append(f"No se pudo validar el paquete: {exception}")
    return errors, warnings


def main() -> int:
    archive = Path(sys.argv[1])
    errors, warnings = validate(archive)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASSED: 0 errors, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
