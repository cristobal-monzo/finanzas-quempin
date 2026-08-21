---
name: Actualizar_AF
description: Use when the user types "/Actualizar_AF" explicitly. If the user instead says "actualiza af", "actualiza analisis financiero", "actualiza el visualizador/dashboard de analisis financiero" or similar natural language without the leading "/", ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills) — never auto-invoke. Runs el registrador de Registro_Analisis_Financiero y luego republica el dashboard resultante en GitHub Pages, para que el link publicado nunca quede desactualizado.
---

# Actualizar AF (Análisis Financiero + dashboard publicado)

Envoltorio de un solo comando sobre dos pasos que hoy existen por separado:
correr el registrador de `/Registro_Analisis_Financiero` y luego **publicar**
el dashboard regenerado en GitHub Pages (los Claude Artifacts que se usaban
antes ya no se actualizan, pedido explícito del usuario 2026-08-19). El
primer paso (`run`) ya regenera
`Visualizador Web/build/index.html` en disco solo (encadenado dentro de
`ejecutar()`), pero **no lo sube** — subirlo seguía siendo un paso manual
(ver `Registro_Analisis_Financiero/MEMORY.md` § Visualizador Web). Este
skill cierra ese hueco: nunca termines la tarea con el registrador corrido
pero el link publicado desactualizado. Mismo patrón que `/Actualizar_CC`
para Centro de Costos.

## Pasos

1. **`status`** (solo lectura) — usar el driver de `/Registro_Analisis_Financiero`:
   ```
   python "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" status
   ```
   Muestra qué carpetas de proyecto se crearían, categorías sin mapeo, y
   avisos (incluye el de TAG sin match en Centro de Costos).

2. **Si `status` muestra algo pendiente** (carpetas nuevas, avisos que
   ameriten atención) **o el usuario pide un refresco explícito** (ej.
   corrigió algo a mano en `Análisis de Proyectos 2026.xlsx`, confirmó un
   cliente pendiente, o Centro de Costos acaba de correr), **correr `run`**
   con el mismo driver:
   ```
   python "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" run
   ```
   `run` ya deja `Visualizador Web/build/index.html` regenerado en disco
   como parte de su propio flujo (`ejecutar()` encadena la regeneración) —
   no hace falta correr `driver.py visualizador` aparte.

3. **Publicar en GitHub Pages** cuando corresponda:
   - Si se corrió `run` en el paso anterior, publicar es obligatorio — el
     build en disco ya cambió.
   - Si `status` no mostró nada pendiente y el usuario no pidió un
     refresco forzado, no hay nada que publicar — decirlo en una línea y
     terminar ahí.

   Receta y comandos exactos (subruta de este módulo: `analisis-financiero`)
   en [`../../../../Visualizador Web/CLAUDE.md`](../../../../Visualizador%20Web/CLAUDE.md)
   § Hosting (raíz del repo, no el `Visualizador Web/CLAUDE.md` de este
   módulo) — es la única copia de esta receta, no la dupliques acá.

4. **Reportar al usuario en una respuesta corta**: qué cambió (carpetas
   creadas, avisos relevantes), si se publicó en GitHub Pages o no hacía
   falta, y el link (el mismo de siempre).

## Cuándo NO aplica

Si el usuario solo pide "corre análisis financiero" sin mencionar el
dashboard/visualizador, usa `/Registro_Analisis_Financiero` directo — ese
skill ya deja el HTML regenerado en disco por su cuenta. Reserva este
skill para cuando además se espera que el link publicado quede al día.

**Si el usuario pide actualizar TODO** ("actualiza las finanzas", "deja
todo al día"), usa `/Actualizar_Finanzas` (raíz del repo) en vez de este:
cubre los tres módulos y los tres tableros publicados, no solo Análisis
Financiero. Este skill sigue siendo el correcto cuando el usuario nombra
explícitamente solo Análisis Financiero.
