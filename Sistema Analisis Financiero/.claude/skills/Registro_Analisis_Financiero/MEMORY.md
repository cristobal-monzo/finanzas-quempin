# MEMORY.md — Registro_Analisis_Financiero

Preferencias y datos operativos de este skill (mismo rol que el MEMORY.md
del skill de Centro de Costos — no confundir con
[`Sistema Analisis Financiero/MEMORY.md`](../../../MEMORY.md), que es la
memoria de diseño/decisiones del módulo completo).

## Visualizador Web

- Gate de contraseña: misma que Centro de Costos (decisión del usuario,
  2026-07-23) — ver `../../../Visualizador Web/template.html`.
- Link del Claude Artifact publicado (primera publicación, 2026-07-28):
  `https://claude.ai/code/artifact/70801be3-a58d-4424-b8cf-53d2b3630934`.
  **Regla explícita (mismo patrón que Centro de Costos): siempre actualizar
  este mismo link, nunca generar uno nuevo.** Al republicar, pasar este URL
  como `url` al tool `Artifact` (o, si la sesión que lo publicó sigue
  abierta, redeployar con el mismo `file_path`).
