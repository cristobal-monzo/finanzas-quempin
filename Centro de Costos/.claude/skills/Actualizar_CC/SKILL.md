---
name: Actualizar_CC
description: Use when the user types "/Actualizar_CC" explicitly. If the user instead says "actualiza cc", "actualiza el centro de costos", "actualiza el visualizador/dashboard de centro de costos" or similar natural language without the leading "/", ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills) — never auto-invoke. Runs the Registro_Centro_de_Costos pipeline and then republishes the resulting dashboard on GitHub Pages, so the published link never goes stale.
---

# Actualizar CC (Centro de Costos + dashboard publicado)

Procedimiento común de los tres skills `/Actualizar_<módulo>` (por qué
existen, los cuatro pasos, cuándo no aplica) en
[`docs/actualizar-un-modulo.md`](../../../../docs/actualizar-un-modulo.md).
Acá va solo lo propio de Centro de Costos.

Acepta el mismo `--pais CL|PE` que `/Registro_Centro_de_Costos` (default
`CL`) y lo pasa sin cambios al driver. Publicar sigue aplicando solo a
Chile: Perú todavía no tiene visualizador propio, así que con `--pais PE`
este skill registra igual pero no hay nada que publicar.

## Lo específico de este módulo

**Driver**: `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py`
**Subruta al publicar**: `centro-de-costos`

**Paso 1 — `status`**: dice cuántos documentos quedarían registrados y
cuáles están pendientes *sin datos* en `datos_extraidos.json`.

**Paso 2 — `run`**: si hay pendientes, con datos o sin ellos, seguir el
flujo completo de
[Registro_Centro_de_Costos/SKILL.md](../Registro_Centro_de_Costos/SKILL.md),
Pasos 2 a 5 — **este es el matiz que distingue a este módulo**: primero se
completa interactivamente `datos_extraidos.json` para los pendientes sin
datos (preguntas al usuario agrupadas por proyecto/documento, pedido
2026-08-18), y solo después se corre `run`. Sin ese paso previo, cada
documento sin entrada en el JSON queda sin registrar.

`run` ya deja `Visualizador Web/build/index.html` regenerado por su cuenta
(PASO 12c), así que no hace falta correr `driver.py visualizador` aparte.

**Paso 3 — publicar**: obligatorio si `run` reportó "Documentos nuevos
registrados: N" con N > 0. Si el usuario pidió un refresco explícito sin
documentos nuevos, correr antes `driver.py visualizador`.
