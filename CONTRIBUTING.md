# Contributing

Contributions and reproducible bug reports are welcome.

1. Open an issue before making a substantial behavioural change.
2. Keep the plugin compatible with QGIS 3.28 through 3.99.
3. Do not add external runtime dependencies unless they are strictly necessary
   and documented in `metadata.txt` and `README.md`.
4. Run the local checks before opening a pull request:

```bash
python -m unittest discover -s tests -v
python tools/build_plugin.py
python tools/validate_package.py dist/qgis_sustituir_geometria.zip
```

The ZIP generated in `dist/` is a release artifact and must not be committed.
Source code, comments, commit messages, and new metadata tags should be written
in English when practical so QGIS reviewers and contributors can follow them.
