---
name: Actualizar_CC
description: Use when the user types "/Actualizar_CC" explicitly. If the user instead says "actualiza cc", "actualiza el centro de costos", "actualiza el visualizador/dashboard de centro de costos" or similar natural language without the leading "/", ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills) — never auto-invoke. Runs the Registro_Centro_de_Costos pipeline and then republishes the resulting dashboard on GitHub Pages, so the published link never goes stale.
---

# Actualizar CC (Centro de Costos + dashboard publicado)

Envoltorio de un solo comando sobre dos pasos que hoy existen por separado:
correr el registrador de `/Registro_Centro_de_Costos` y luego **publicar**
el dashboard regenerado en GitHub Pages (los Claude Artifacts que se usaban
antes ya no se actualizan, pedido explícito del usuario 2026-08-19). El
primer paso ya regenera
`Visualizador Web/build/index.html` en disco solo (PASO 12c de
`auditor_centro_costos.py`), pero **no lo sube** — subirlo seguía siendo un
paso manual (ver `Registro_Centro_de_Costos/MEMORY.md` § Visualizador web).
Este skill cierra ese hueco: nunca termines la tarea con el registrador
corrido pero el link publicado desactualizado.

Acepta el mismo `--pais CL|PE` que expone `/Registro_Centro_de_Costos`
(default `CL`) y lo pasa sin cambios al driver en el paso 1. El paso 3
(publicar en GitHub Pages) sigue aplicando solo a Chile: Perú todavía no
tiene visualizador propio (sub-proyecto 4, fuera de alcance acá), así que
con `--pais PE` este skill corre el registro igual pero no hay nada que
publicar.

## Pasos

1. **`status`** (solo lectura) — usar el driver de `/Registro_Centro_de_Costos`:
   ```
   python "Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py" status
   ```
2. **Si hay pendientes (con datos o sin ellos), completar y correr `run`** —
   seguir el flujo completo de
   [Registro_Centro_de_Costos/SKILL.md](../Registro_Centro_de_Costos/SKILL.md)
   tal cual, Pasos 2 a 5: primero completar interactivamente
   `datos_extraidos.json` para los pendientes sin datos (Paso 2 — preguntas
   al usuario agrupadas por proyecto/documento, pedido 2026-08-18), luego
   correr `run` (Paso 3), la tabla-resumen de posibles errores (Paso 4), y
   la confirmación explícita si el informe reporta cambios manuales
   pendientes (Paso 5). `run` ya deja `Visualizador Web/build/index.html`
   regenerado en disco como parte de su propia ejecución — no hace falta
   correr `driver.py visualizador` aparte en este caso.
3. **Publicar en GitHub Pages** cuando corresponda:
   - Si `run` reportó **"Documentos nuevos registrados: N" con N > 0**,
     publicar es obligatorio.
   - Si el usuario pidió explícitamente refrescar el dashboard aunque no
     haya documentos nuevos (ej. corrigió algo a mano en el Excel, o solo
     cambió `template.html`), correr primero
     `python "Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py" visualizador`
     y publicar igual.
   - Si `status` no mostró pendientes y el usuario no pidió un refresco
     forzado, no hay nada que publicar — decirlo en una línea y terminar
     ahí.

   Receta y comandos exactos (subruta de este módulo: `centro-de-costos`) en
   [`../../../../Visualizador Web/CLAUDE.md`](../../../../Visualizador%20Web/CLAUDE.md)
   § Hosting (raíz del repo, no el `Visualizador Web/CLAUDE.md` de este
   módulo) — es la única copia de esta receta, no la dupliques acá.

4. **Reportar al usuario en una respuesta corta**: cuántos documentos
   nuevos se registraron (si alguno), si se publicó en GitHub Pages o no
   hacía falta, y el link (el mismo de siempre).

## Cuándo NO aplica

Si el usuario solo pide "corre el centro de costos" sin mencionar el
dashboard/visualizador, usa `/Registro_Centro_de_Costos` directo — ese skill
ya deja el HTML regenerado en disco por su cuenta. Reserva este skill para
cuando además se espera que el link publicado quede al día.

Si el usuario quiere actualizar los datos pero explícitamente **no** quiere
publicar todavía (ej. va a acumular varias corridas a lo largo del día y
publicar todo junto al final), usa
[`/Actualizar_Base_de_Datos`](../Actualizar_Base_de_Datos/SKILL.md) en vez
de este — corre el mismo `status`→`run` pero nunca toca el worktree
`gh-pages`.

**Si el usuario pide actualizar TODO** ("actualiza las finanzas", "deja todo
al día"), usa `/Actualizar_Finanzas` (raíz del repo) en vez de este: cubre
los tres módulos y los tres tableros publicados, no solo Centro de Costos.
Este skill sigue siendo el correcto cuando el usuario nombra explícitamente
solo Centro de Costos.
