# Publicación en el repositorio oficial de QGIS

## Comprobaciones previas

1. Prueba el flujo completo en una instalación limpia de QGIS 3.44.x con:
   geometrías de la misma capa, capas distintas, CRS distintos, Deshacer y
   descarte de cambios.
2. Comprueba que la versión de `metadata.txt` coincide con la versión que se va
   a publicar.
3. Ejecuta:

```bash
python -m unittest discover -s tests -v
python tools/build_plugin.py
python tools/validate_package.py dist/qgis_sustituir_geometria.zip
```

4. Confirma que funcionan estas direcciones:

- Página: <https://github.com/motacj/qgis_sustituir_geometria#readme>
- Código: <https://github.com/motacj/qgis_sustituir_geometria>
- Incidencias: <https://github.com/motacj/qgis_sustituir_geometria/issues>

## Primera publicación

1. Accede a <https://plugins.qgis.org/> con un **OSGeo ID**.
2. Elige **Upload a plugin**.
3. Sube únicamente `dist/qgis_sustituir_geometria.zip`.
4. Revisa los metadatos detectados y envía la versión.
5. Espera el correo del análisis automático. El portal comprueba la estructura,
   Bandit, detect-secrets, Flake8 y los archivos incluidos.
6. Si no eres un publicador de confianza, la versión quedará pendiente de la
   revisión manual del equipo de QGIS tras superar el análisis.

## Versiones posteriores

- Incrementa `version` y actualiza `changelog` en `metadata.txt`.
- Añade la misma versión a `CHANGELOG.md`.
- Publica el código y crea una etiqueta con el formato `vX.Y.Z`.
- Descarga o genera el nuevo ZIP, repite las validaciones y súbelo al portal.

No cambies el nombre visible ni la carpeta raíz del complemento en una
actualización. No subas el ZIP dentro del repositorio de código fuente.
