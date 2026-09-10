---
name: Actualizar_AF
description: Use when the user types "/Actualizar_AF" explicitly. If the user instead says "actualiza af", "actualiza analisis financiero", "actualiza el visualizador/dashboard de analisis financiero" or similar natural language without the leading "/", ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills) — never auto-invoke. Runs el registrador de Registro_Analisis_Financiero y luego republica el dashboard resultante en GitHub Pages, para que el link publicado nunca quede desactualizado.
---

# Actualizar AF (Análisis Financiero + dashboard publicado)

Procedimiento común de los tres skills `/Actualizar_<módulo>` (por qué
existen, los cuatro pasos, cuándo no aplica) en
[`docs/actualizar-un-modulo.md`](../../../../docs/actualizar-un-modulo.md).
Acá va solo lo propio de Análisis Financiero.

## Lo específico de este módulo

**Driver**: `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py`
**Subruta al publicar**: `analisis-financiero`

**Paso 1 — `status`**: muestra qué carpetas de proyecto se crearían,
categorías sin mapeo, y avisos (incluye el de TAG sin match en Centro de
Costos).

**Paso 2 — `run`**: correr si `status` muestra algo pendiente (carpetas
nuevas, avisos que ameriten atención) **o** si el usuario pide un refresco
explícito — por ejemplo corrigió algo a mano en `Análisis de Proyectos
2026.xlsx`, confirmó un cliente pendiente, o Centro de Costos acaba de
correr.

`run` ya deja `Visualizador Web/build/index.html` regenerado como parte de
`ejecutar()`, así que no hace falta `driver.py visualizador` aparte.

**Paso 3 — publicar**: obligatorio si se corrió `run`; el build en disco ya
cambió.
