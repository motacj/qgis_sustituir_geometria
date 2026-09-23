"""Pruebas que no requieren una instalación de QGIS."""

from __future__ import annotations

import ast
import configparser
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginStaticTests(unittest.TestCase):
    def test_python_sources_have_valid_syntax(self):
        for source_path in ROOT.glob("*.py"):
            ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    def test_metadata_targets_qgis_3(self):
        metadata = configparser.ConfigParser(interpolation=None)
        metadata.optionxform = str
        metadata.read(ROOT / "metadata.txt", encoding="utf-8")
        general = metadata["general"]
        self.assertEqual(general["version"], "1.0.1")
        self.assertEqual(general["qgisMinimumVersion"], "3.28")
        self.assertEqual(general["category"], "Vector")
        self.assertEqual(
            general["repository"],
            "https://github.com/motacj/qgis_sustituir_geometria",
        )
        self.assertEqual(
            general["tracker"],
            "https://github.com/motacj/qgis_sustituir_geometria/issues",
        )

    def test_changes_are_never_committed_automatically(self):
        source = (ROOT / "map_tool.py").read_text(encoding="utf-8")
        self.assertIn("beginEditCommand", source)
        self.assertIn("changeGeometry", source)
        self.assertIn("destroyEditCommand", source)
        self.assertNotIn("commitChanges(", source)

    def test_first_attributes_are_protected(self):
        source = (ROOT / "map_tool.py").read_text(encoding="utf-8")
        self.assertRegex(
            source,
            re.compile(
                r"changeGeometry\(\s*target\.feature_id,\s*replacement,\s*True\s*\)",
                re.DOTALL,
            ),
        )


if __name__ == "__main__":
    unittest.main()
