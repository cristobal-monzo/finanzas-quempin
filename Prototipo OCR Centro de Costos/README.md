# Prototipo OCR local para Centro de Costos

Esta carpeta contiene una propuesta aislada para evaluar extracción OCR local
de facturas y boletas antes de integrarla al Centro de Costos productivo.

Estado actual: **evaluado y descartado (2026-07-26)**. Se implementó y
benchmarkeó Tesseract vs. PaddleOCR como motores candidatos en la rama
`feat/ocr-local-prototype` (nunca fusionada a `master` — el resultado fue
detener este enfoque, no adoptarlo). La rama y su worktree se limpiaron el
2026-08-05 (checkout pesado con venv + node_modules propios); el código y el
benchmark completo quedan preservados en el tag `archive/ocr-local-prototype`
(`git show archive/ocr-local-prototype` o `git checkout -b retomar-ocr
archive/ocr-local-prototype` para volver a tenerlo como working tree). Si se
retoma la idea de OCR local más adelante, partir de ese benchmark en vez de
repetirlo desde cero.

El prototipo tenía estas restricciones (vigentes si se retoma):

- Solo podrá leer las facturas y datos de referencia existentes.
- No modificará `Centro de Costos.xlsx`.
- No modificará `Sistema/datos_extraidos.json`.
- No renombrará, moverá ni copiará los documentos originales.
- Mantendrá sus resultados financieros locales fuera de Git.
- No podrá registrar automáticamente documentos durante la fase de prueba.

La especificación completa se encuentra en
[`docs/specs/2026-07-24-ocr-local-centro-costos-design.md`](docs/specs/2026-07-24-ocr-local-centro-costos-design.md).
