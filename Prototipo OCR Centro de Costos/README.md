# Prototipo OCR local para Centro de Costos

Esta carpeta contiene una propuesta aislada para evaluar extracción OCR local
de facturas y boletas antes de integrarla al Centro de Costos productivo.

Estado actual: **evaluado y descartado (2026-07-26)**. Se implementó y
benchmarkeó Tesseract vs. PaddleOCR como motores candidatos en la rama
`feat/ocr-local-prototype` (nunca fusionada a `master` — el resultado fue
detener este enfoque, no adoptarlo) y su worktree (`.worktrees/ocr-local-prototype`).
Ver el último commit de esa rama para el benchmark comparativo completo. Si
se retoma la idea de OCR local más adelante, partir de ese benchmark en vez
de repetirlo desde cero.

El prototipo tenía estas restricciones (vigentes si se retoma):

- Solo podrá leer las facturas y datos de referencia existentes.
- No modificará `Centro de Costos.xlsx`.
- No modificará `Sistema/datos_extraidos.json`.
- No renombrará, moverá ni copiará los documentos originales.
- Mantendrá sus resultados financieros locales fuera de Git.
- No podrá registrar automáticamente documentos durante la fase de prueba.

La especificación completa se encuentra en
[`docs/specs/2026-07-24-ocr-local-centro-costos-design.md`](docs/specs/2026-07-24-ocr-local-centro-costos-design.md).
