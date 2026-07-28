---
name: Actualizar_Finanzas
description: Use when the user wants ALL of Finanzas QUEMPIN brought up to date at once — "actualiza las finanzas", "actualiza todo", "corre todo el pipeline", "deja todo al día" — or wants a single read-only status across every module. Runs Centro de Costos (which chains Análisis Financiero and the CC/AF dashboards), then regenerates the Cotizador Histórico dashboard (which nothing else invokes) and reports which PDF reports went stale. Use /Registro_Centro_de_Costos or /Actualizar_CC instead when the user explicitly names only Centro de Costos.
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

## Paso obligatorio tras `run`: publicar los 3 tableros

**Regenerar los `build/index.html` en disco NO cambia lo que ve la gente.**
El canal real de consumo son tres Claude Artifacts privados con links fijos
que los colegas tienen guardados. Si corres `run` y no publicas, el Excel
queda al día y los tres tableros publicados siguen mostrando datos viejos —
que es exactamente el problema que este skill existe para cerrar.

Al final de `run` (y de `status`) el driver imprime la sección **"TABLEROS
PARA PUBLICAR"** con, por cada tablero: si se regeneró en esta corrida, la
ruta absoluta de su `index.html` y su link fijo. **Usa esos valores tal
cual** — el driver los lee del `MEMORY.md` de cada skill, que es la fuente
de verdad de los links.

Para cada uno de los tres, llama al tool `Artifact` con:
- `file_path` = la ruta que imprimió el driver
- `url` = el link que imprimió el driver
- `favicon` = **el mismo de siempre** para ese tablero (Cotizador: 🧾). Un
  favicon distinto se lee como si fuera otra página.

**Nunca generes un link nuevo** para un tablero que ya tiene uno. Si el tool
pide ver la versión más reciente antes de sobrescribir, haz `WebFetch` de ese
mismo URL primero y vuelve a publicar.

Criterio de cuándo publicar cada uno:
- Si el driver lo marcó **REGENERADO en esta corrida** → publicar.
- Si lo marcó **sin cambios** y el usuario no pidió un refresco forzado → no
  hace falta; dilo en una línea.
- Si dice **SIN BUILD** → ese módulo nunca generó su tablero; no inventes un
  Artifact, repórtalo.

## Qué NO hace (a propósito)

- **No genera los reportes PDF.** Cada PDF lleva análisis redactado por el
  agente (página 2 del estándar de 2 páginas), no es una salida mecánica —
  se generan con `/Reportes_Analisis_Financiero run` cuando corresponda.
- **No publica solo.** El tool `Artifact` vive en el agente, no en el
  proceso del driver: por eso el driver deja todo listo e impreso, y la
  publicación la hace el agente siguiendo la sección de arriba.

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
