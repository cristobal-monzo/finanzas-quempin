---
name: Actualizar_Base_de_Datos
description: Use when the user types "/Actualizar_Base_de_Datos" explicitly. If the user instead says "actualiza la base de datos", "actualiza el excel del centro de costos" or similar natural language without the leading "/", ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills) — never auto-invoke. Pone Centro de Costos.xlsx al día con los documentos nuevos SIN publicar nada en la web — corre el pipeline de registro (status→completar JSON pendiente interactivamente→run) de Registro_Centro_de_Costos y se detiene ahí, dejando el dashboard publicado (GitHub Pages) intacto y desactualizado a propósito. Útil para acumular varias actualizaciones de datos y publicar todas juntas después con /Actualizar_CC o /Actualizar_Finanzas.
---

# Actualizar Base de Datos (solo Excel, sin publicar)

Envoltorio de un solo paso sobre `/Registro_Centro_de_Costos`: corre
`status`→`run` y **se detiene ahí**. A diferencia de `/Actualizar_CC`, este
skill nunca toca el dashboard publicado en GitHub Pages (los Claude
Artifacts que se usaban antes ya no se actualizan, pedido explícito del
usuario 2026-08-19) — ni lo regenera para subir, ni hace `git push` al
worktree `gh-pages`. Pensado para
cuando el usuario quiere ir acumulando varias corridas de registro de datos
(varios lotes de facturas/boletas a lo largo del día, por ejemplo) y publicar
todo junto una sola vez al final.

## Pasos

1. **`status`** (solo lectura) — usar el driver de `/Registro_Centro_de_Costos`:
   ```
   python "Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py" status
   ```
2. **Si hay pendientes (con datos o sin ellos), completar y correr `run`** —
   seguir el flujo completo de
   [Registro_Centro_de_Costos/SKILL.md](../Registro_Centro_de_Costos/SKILL.md)
   tal cual, Pasos 2 a 5: primero completar interactivamente
   `datos_extraidos.json` para los pendientes que aún no tienen datos
   (Paso 2 — preguntas al usuario agrupadas por proyecto/documento, pedido
   2026-08-18, para que ningún documento nuevo quede sin registrar por
   faltarle su entrada en el JSON), luego correr `run` (Paso 3), la
   tabla-resumen de posibles errores (Paso 4), y la confirmación explícita
   si el informe reporta cambios manuales pendientes (Paso 5).
3. **No publicar nada.** `run` ya deja `Visualizador Web/build/index.html`
   regenerado en disco (PASO 12c de `auditor_centro_costos.py`) y ya
   encadena Análisis Financiero (PASO 12d) — ambos son efectos normales del
   pipeline de registro, no "publicar". Lo que este skill deliberadamente
   **no** hace es el paso final de `/Actualizar_CC` (copiar el HTML al
   worktree `gh-pages` y hacer `git push`). Si el usuario no lo pidió
   explícitamente, no lo hagas.
4. **Reportar al usuario en una respuesta corta**: cuántos documentos nuevos
   se registraron (si alguno), y recordar que el dashboard publicado
   **sigue sin actualizarse** — para publicarlo hay que correr
   `/Actualizar_CC` (solo Centro de Costos) o `/Actualizar_Finanzas` (los
   tres módulos) después.

## Cuándo NO aplica

Si el usuario quiere que el link publicado quede al día en el mismo paso,
usa `/Actualizar_CC` en vez de este. Si quiere actualizar los tres módulos
del proyecto (no solo Centro de Costos), usa `/Actualizar_Finanzas`.
