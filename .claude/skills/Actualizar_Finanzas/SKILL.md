---
name: Actualizar_Finanzas
description: Use when the user types "/Actualizar_Finanzas" explicitly. If the user instead describes the same intent in natural language without the leading "/" — "actualiza las finanzas", "actualiza todo", "corre todo el pipeline", "deja todo al día", or a read-only status across every module — ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills), never auto-invoke. Runs Centro de Costos (which chains Análisis Financiero and the CC/AF dashboards), then regenerates the Cotizador Histórico dashboard (which nothing else invokes) and reports which PDF reports went stale. Use /Registro_Centro_de_Costos or /Actualizar_CC instead when the user explicitly names only Centro de Costos.
---

# Actualizar Finanzas (orquestador de todos los módulos)

Punto de entrada único de `Finanzas QUEMPIN`. Existe porque la cadena de
actualización estaba incompleta: `run` de Centro de Costos ya encadenaba
Análisis Financiero y dos de los tres tableros, pero **el visualizador de
Cotizador Histórico no lo invocaba nadie** pese a leer el mismo
`Centro de Costos.xlsx`, y los reportes PDF solo se avisaban de pasada.

## Comandos

```
py -3.14 ".claude/skills/Actualizar_Finanzas/driver.py" status
py -3.14 ".claude/skills/Actualizar_Finanzas/driver.py" run
```

**Usar `py -3.14`, no `python`** — el `python` del PATH es 3.11 y no tiene
openpyxl (ver `requirements.txt`).

- **`status`** — solo lectura sobre los 4 drivers (Centro de Costos, Análisis
  Financiero, Reportes PDF, Cotizador Histórico). No escribe Excel, ni
  archivos, ni tableros. Es el paso previo obligatorio antes de `run`.
- **`run`** — cadena completa, en orden de dependencias:
  1. Centro de Costos `run` — registra documentos nuevos. Su propio flujo ya
     encadena Análisis Financiero (PASO 12d), el tablero de Centro de Costos
     (12c) y, dentro de Análisis Financiero, el tablero de Análisis
     Financiero. **Si este paso falla, la cadena se detiene**: no se
     actualiza ningún tablero sobre datos a medio escribir.
  2. Cotizador Histórico `visualizador` — el eslabón que faltaba.
  3. Reportes PDF `status` — lista los que quedaron desactualizados.

  **Antes de correr este `run`**, si el `status` de arriba mostró
  pendientes de Centro de Costos sin datos en `datos_extraidos.json`, este
  driver los corre como subproceso y no puede preguntarle nada al usuario a
  mitad de camino — completar esas entradas es responsabilidad del agente
  primero, siguiendo el Paso 2 (interactivo, preguntas agrupadas por
  proyecto/documento) de
  [Registro_Centro_de_Costos/SKILL.md](../../../Centro%20de%20Costos/.claude/skills/Registro_Centro_de_Costos/SKILL.md)
  (pedido 2026-08-18) — igual que hacen `/Actualizar_Base_de_Datos` y
  `/Actualizar_CC`. Si se salta este paso, esos documentos simplemente
  seguirán apareciendo como pendientes después de `run`.

## Paso obligatorio tras `run`: publicar los 3 tableros

**Regenerar los `build/index.html` en disco NO cambia lo que ve la gente.**
Desde 2026-08-05 el canal real de consumo es un sitio en GitHub Pages
(repo público `cristobal-monzo/finanzas-quempin`, rama `gh-pages`) — ver
[`../../../Visualizador Web/CLAUDE.md`](../../../Visualizador%20Web/CLAUDE.md)
§ Hosting para el detalle completo y el trade-off de control de acceso ya
decidido. Si corres `run` y no publicas, el Excel queda al día y los tres
tableros publicados siguen mostrando datos viejos.

Al final de `run` (y de `status`) el driver imprime la sección **"TABLEROS
PARA PUBLICAR"** con, por cada tablero: si se regeneró en esta corrida, la
ruta absoluta de su `index.html`, su URL pública fija, y la ruta destino
dentro del worktree `.worktrees/gh-pages/`.

Para cada uno que corresponda publicar, usa la receta de
[`../../../Visualizador Web/CLAUDE.md`](../../../Visualizador%20Web/CLAUDE.md)
§ Hosting (única copia de esos comandos) con los valores que imprimió el
driver arriba (columnas "Archivo"/"Copiar a") — no repitas la receta acá.
Las URLs son estructurales (no opacas como los links de Artifact) — no hay
que "cuidar" nada especial entre publicaciones, solo confirmar que la
subruta coincida con la que imprimió el driver.

Criterio de cuándo publicar cada uno:
- Si el driver lo marcó **REGENERADO en esta corrida** → publicar.
- Si lo marcó **sin cambios** y el usuario no pidió un refresco forzado → no
  hace falta; dilo en una línea.
- Si dice **SIN BUILD** → ese módulo nunca generó su tablero; repórtalo, no
  hay nada que copiar.

## Qué NO hace (a propósito)

- **No genera los reportes PDF.** Cada PDF lleva análisis redactado por el
  agente (página 2 del estándar de 2 páginas), no es una salida mecánica —
  se generan con `/Reportes_Analisis_Financiero run` cuando corresponda.
- **No publica solo.** `git push` es una acción visible/confirmable que
  corre el agente (o el usuario) de forma explícita, no escondida dentro
  del proceso del driver — por eso el driver deja todo listo e impreso, y
  la publicación sigue la sección de arriba.
- **No es la única forma de actualizar datos sin publicar.** Si el usuario
  solo quiere Centro de Costos y quiere dejar la publicación para después,
  [`/Actualizar_Base_de_Datos`](../../../Centro%20de%20Costos/.claude/skills/Actualizar_Base_de_Datos/SKILL.md)
  es más directo — este orquestador de todas formas nunca publica solo,
  pero sí corre y reporta los 3 módulos, no solo uno.

## Cómo reportar al usuario

Respuesta corta: cuántos documentos nuevos se registraron, qué tableros se
regeneraron, y qué quedó pendiente (reportes PDF por generar, publicaciones
por hacer). Si algún módulo falló, decir cuál y que el resto sí se completó
— el driver ya distingue fallo bloqueante (Centro de Costos) de fallo
tolerable (un tablero).

## Detalle de implementación relevante

El driver corre **cada módulo en su propio proceso** (`subprocess`), no por
`import`. Los tres módulos tienen archivos homónimos (`build_visualizador.py`,
`driver.py`) y `sys.modules` cachea por nombre, así que importarlos en el
mismo proceso entrega el equivocado. Un proceso por módulo elimina esa clase
de error y evita que un módulo caído voltee a los demás. Si agregas un módulo
nuevo (ej. Flujo de Caja), agrégalo acá como una línea más — no dentro de
`auditor_centro_costos.main()`.
