---
name: Actualizar_CC
description: Use when the user says "actualiza cc", "actualiza el centro de costos", "actualiza el visualizador/dashboard de centro de costos" (loose natural-language phrasing, without a leading "/"), or wants Centro de Costos and its published web dashboard brought up to date in one go — runs the Registro_Centro_de_Costos pipeline and then republishes the resulting dashboard as the existing Claude Artifact, so the published link never goes stale. This is the default for those phrases; Registro_Centro_de_Costos itself only runs on explicit "/Registro_Centro_de_Costos" invocation.
---

# Actualizar CC (Centro de Costos + dashboard publicado)

Envoltorio de un solo comando sobre dos pasos que hoy existen por separado:
correr el registrador de `/Registro_Centro_de_Costos` y luego **publicar**
el dashboard regenerado como Artifact. El primer paso ya regenera
`Visualizador Web/build/index.html` en disco solo (PASO 12c de
`auditor_centro_costos.py`), pero **no lo sube** — subirlo seguía siendo un
paso manual (ver `Registro_Centro_de_Costos/MEMORY.md` § Visualizador web).
Este skill cierra ese hueco: nunca termines la tarea con el registrador
corrido pero el link publicado desactualizado.

## Pasos

1. **`status`** (solo lectura) — usar el driver de `/Registro_Centro_de_Costos`:
   ```
   python "Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py" status
   ```
2. **Si hay pendientes > 0, correr `run`** (mismo driver) — eso ya es el
   Paso 2 de [Registro_Centro_de_Costos/SKILL.md](../Registro_Centro_de_Costos/SKILL.md)
   — y luego seguir sus Pasos 3-4 tal cual (tabla-resumen de posibles
   errores, confirmación de cambios manuales pendientes si el informe los
   reporta). `run` ya deja `Visualizador Web/build/index.html` regenerado en
   disco como parte de su propia ejecución — no hace falta correr
   `driver.py visualizador` aparte en este caso.
3. **Publicar el Artifact** cuando corresponda:
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

   Para publicar: usar el tool `Artifact` con `file_path` apuntando a
   `Centro de Costos/Visualizador Web/build/index.html` y `url` igual al
   link fijo documentado en
   [Registro_Centro_de_Costos/MEMORY.md](../Registro_Centro_de_Costos/MEMORY.md)
   § Visualizador web — **nunca generar un link nuevo**. Si el tool pide ver
   la versión más reciente antes de sobrescribir, hacer un `WebFetch` de ese
   mismo URL primero.

4. **Reportar al usuario en una respuesta corta**: cuántos documentos
   nuevos se registraron (si alguno), si se publicó el Artifact o no hacía
   falta, y el link (el mismo de siempre).

## Cuándo NO aplica

Si el usuario solo pide "corre el centro de costos" sin mencionar el
dashboard/visualizador, usa `/Registro_Centro_de_Costos` directo — ese skill
ya deja el HTML regenerado en disco por su cuenta. Reserva este skill para
cuando además se espera que el link publicado quede al día.
