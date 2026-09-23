#!/usr/bin/env python3
"""Construye el ZIP instalable del complemento."""

from __future__ import annotations

import zipfile
from pathlib import Path


PLUGIN_NAME = "qgis_sustituir_geometria"
ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ARCHIVE = DIST / f"{PLUGIN_NAME}.zip"
EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".pytest_cache",
    "__pycache__",
    "dist",
    "docs",
    "tests",
    "tools",
}
EXCLUDED_NAMES = {
    ".gitignore",
    ".DS_Store",
    "CONTRIBUTING.md",
    "PUBLICACION_QGIS.md",
    "SECURITY.md",
    "Thumbs.db",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip", ".qgs", ".qgz"}


def package_files() -> list[Path]:
    """Devuelve únicamente los archivos necesarios en la instalación."""
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def build() -> Path:
    """Crea el ZIP con una única carpeta raíz reconocible por QGIS."""
    DIST.mkdir(exist_ok=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for source in package_files():
            package.write(source, Path(PLUGIN_NAME) / source.relative_to(ROOT))
    return ARCHIVE


if __name__ == "__main__":
    result = build()
    print(f"Built {result} ({result.stat().st_size} bytes)")
