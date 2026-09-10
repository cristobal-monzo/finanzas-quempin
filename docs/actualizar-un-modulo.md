# Actualizar un módulo y dejar su tablero publicado al día

Procedimiento común de `/Actualizar_CC`, `/Actualizar_AF` y
`/Actualizar_Cotizador`. Los tres son el mismo envoltorio sobre dos pasos que
existen por separado — correr el registrador del módulo y **publicar** el
tablero regenerado — y antes repetían este texto casi palabra por palabra en
sus tres `SKILL.md`. Vive acá una sola vez; cada skill agrega únicamente lo
que es propio de su módulo.

## Por qué existen estos skills

Correr el registrador deja `Visualizador Web/build/index.html` regenerado
**en disco**, pero no lo sube. Subirlo era un paso manual aparte, y la falla
típica era terminar la tarea con los datos al día y el link publicado viejo.
Estos skills cierran ese hueco: **nunca termines con el registrador corrido y
el link desactualizado.**

Desde el 2026-08-05 el único canal es GitHub Pages. Los Claude Artifacts
privados que se usaban antes ya no se actualizan (pedido explícito del
usuario, 2026-08-19).

## Los cuatro pasos

1. **`status`** — solo lectura. Cada skill indica el driver y qué mira.

2. **`run`** — la ejecución real, cuando corresponda. Cada skill indica
   cuándo corresponde: no todos los módulos escriben datos (el Cotizador es
   de solo lectura sobre `Centro de Costos.xlsx`, así que no tiene `run`).

3. **Publicar en GitHub Pages** cuando corresponda:
   - Si el paso 2 escribió algo, publicar es **obligatorio**.
   - Si el usuario pidió un refresco explícito (corrigió algo a mano en el
     Excel, o solo cambió `template.html`), regenerar el visualizador y
     publicar igual.
   - Si `status` no mostró nada pendiente y no hubo pedido de refresco, no
     hay nada que publicar: dilo en una línea y termina ahí.

   La receta y los comandos exactos están en
   [`Visualizador Web/CLAUDE.md`](../Visualizador%20Web/CLAUDE.md) § Hosting
   (el de la **raíz** del repo, no el del módulo). Es la única copia — no la
   dupliques. Cada skill aporta solo su subruta (`centro-de-costos`,
   `analisis-financiero`, `cotizador-historico`).

4. **Reportar en una respuesta corta**: qué cambió, si se publicó o no hacía
   falta, y el link (el mismo de siempre, la URL es estructural y fija).

## Cuándo NO aplica

**Si el usuario pide actualizar TODO** ("actualiza las finanzas", "deja todo
al día"), usa `/Actualizar_Finanzas` (raíz del repo): cubre los tres módulos
y los tres tableros, no solo uno. Estos skills son los correctos cuando el
usuario nombra explícitamente un solo módulo.

**Si el usuario quiere los datos al día pero explícitamente NO quiere
publicar todavía** (va a acumular varias corridas y publicar todo junto al
final), usa `/Actualizar_Base_de_Datos` — corre el mismo `status`→`run` de
Centro de Costos pero nunca toca el worktree `gh-pages`.

**Si el usuario solo pide correr el registrador** sin mencionar el
dashboard, usa el skill de registro del módulo directo
(`/Registro_Centro_de_Costos`, `/Registro_Analisis_Financiero`,
`/Cotizador_Historico`): esos ya dejan el HTML regenerado en disco por su
cuenta.
