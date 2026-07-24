# Prototipo OCR local para Centro de Costos

Esta carpeta contiene una propuesta aislada para evaluar extracción OCR local
de facturas y boletas antes de integrarla al Centro de Costos productivo.

Estado actual: **diseño aprobado, implementación pendiente de planificación**.

El prototipo tendrá estas restricciones:

- Solo podrá leer las facturas y datos de referencia existentes.
- No modificará `Centro de Costos.xlsx`.
- No modificará `Sistema/datos_extraidos.json`.
- No renombrará, moverá ni copiará los documentos originales.
- Mantendrá sus resultados financieros locales fuera de Git.
- No podrá registrar automáticamente documentos durante la fase de prueba.

La especificación completa se encuentra en
[`docs/specs/2026-07-24-ocr-local-centro-costos-design.md`](docs/specs/2026-07-24-ocr-local-centro-costos-design.md).
