---
name: Actualizar_AF
description: Use when the user says "actualiza af", "actualiza analisis financiero", "actualiza el visualizador/dashboard de analisis financiero" (loose natural-language phrasing, without a leading "/"), or wants Análisis Financiero and its published web dashboard brought up to date in one go — runs el registrador de Registro_Analisis_Financiero y luego republica el dashboard resultante como el Claude Artifact existente, para que el link publicado nunca quede desactualizado. Este es el default para esas frases; Registro_Analisis_Financiero por sí solo corre solo con invocación explícita "/Registro_Analisis_Financiero".
---

# Actualizar AF (Análisis Financiero + dashboard publicado)

Envoltorio de un solo comando sobre dos pasos que hoy existen por separado:
correr el registrador de `/Registro_Analisis_Financiero` y luego **publicar**
el dashboard regenerado como Artifact. El primer paso (`run`) ya regenera
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
   corrigió algo a mano en `Análisis de Proyectos.xlsx`, confirmó un
   cliente pendiente, o Centro de Costos acaba de correr), **correr `run`**
   con el mismo driver:
   ```
   python "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" run
   ```
   `run` ya deja `Visualizador Web/build/index.html` regenerado en disco
   como parte de su propio flujo (`ejecutar()` encadena la regeneración) —
   no hace falta correr `driver.py visualizador` aparte.

3. **Publicar el Artifact** cuando corresponda:
   - Si se corrió `run` en el paso anterior, publicar es obligatorio — el
     build en disco ya cambió.
   - Si `status` no mostró nada pendiente y el usuario no pidió un
     refresco forzado, no hay nada que publicar — decirlo en una línea y
     terminar ahí.

   Para publicar (desde 2026-08-05, GitHub Pages reemplazó a Artifacts —
   ver [`../../../Visualizador Web/CLAUDE.md`](../../../Visualizador%20Web/CLAUDE.md)
   § Hosting):
   ```
   cp "Sistema Analisis Financiero/Visualizador Web/build/index.html" ".worktrees/gh-pages/analisis-financiero/index.html"
   git -C ".worktrees/gh-pages" add analisis-financiero/index.html
   git -C ".worktrees/gh-pages" commit -m "actualizar tablero de Analisis Financiero"
   git -C ".worktrees/gh-pages" push
   ```
   URL pública (fija, no cambia entre corridas):
   `https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero/`.

4. **Reportar al usuario en una respuesta corta**: qué cambió (carpetas
   creadas, avisos relevantes), si se publicó el Artifact o no hacía
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
