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

## Qué NO hace (a propósito)

- **No genera los reportes PDF.** Cada PDF lleva análisis redactado por el
  agente (página 2 del estándar de 2 páginas), no es una salida mecánica —
  se generan con `/Reportes_Analisis_Financiero run` cuando corresponda.
- **No publica los Artifacts.** Regenera los tres `build/index.html` en
  disco; publicarlos sigue siendo un paso aparte (`/Actualizar_CC` para
  Centro de Costos; los otros dos a mano contra su link fijo, ver el
  `MEMORY.md` de cada skill). Cerrar este hueco para los tres es el
  siguiente paso natural de este skill.

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
