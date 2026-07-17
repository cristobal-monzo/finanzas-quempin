# Errores y correcciones manuales: Registro_Centro_de_Costos

Dos cosas viven en este archivo:

1. **Historial de errores** detectados por el pipeline (celdas marcadas en
   rojo, inconsistencias aritméticas, posibles duplicados, archivos
   ilegibles) — antes vivía en `MEMORY.md`, se movió acá para separar
   "preferencias/datos" (MEMORY.md) de "errores" (este archivo).
2. **Registro de correcciones manuales** hechas directo en
   `Centro de Costos.xlsx` — la bitácora que permite, al actualizar el CC,
   recolorear la **fuente** (no el relleno) de esas celdas de rojo
   (`C00000`, "requiere revisión") a azul marino oscuro (`1F3864`,
   "corregido a mano"), según la convención de colores ya definida en el
   propio libro (ver leyenda al pie de `Master`/`Detalle`/hojas de proyecto,
   y el detalle de hex en
   [MEMORY.md](MEMORY.md#preferencias-de-formato-y-color)).

## Cómo usar este archivo

El valor lo corrige el usuario; la detección y el registro en la bitácora
son automáticos, no algo que el usuario deba llenar a mano:

1. Al correr `status` o `run`, o al revisar el Excel manualmente, encuentras
   una celda en **rojo** (`requiere revisión`) — típicamente un N° de
   Documento ilegible (`S/N (...)`), un IVA que no cuadra con el 19% del
   Neto, o un dato dudoso marcado por quien extrajo los datos a
   `datos_extraidos.json`.
2. Corriges el valor **a mano, directo en `Centro de Costos.xlsx`** — este
   paso es siempre manual, del usuario.
3. Al correr el skill de actualizar CC la próxima vez, el script compara
   la versión anterior del libro (el backup mas reciente en 
   `Respaldos/`) contra la versión actual, detecta qué celda cambió de
   valor estando en rojo, y agrega solo la fila correspondiente a la tabla
   de abajo — el usuario no edita esa tabla directamente.
4. En esa misma corrida, el script recolorea la **fuente** de esa celda de
   rojo a azul marino oscuro (`1F3864`) — el color de relleno no cambia — y
   la fila pasa de "Pendiente" a "Aplicado" en la columna de estado.

> **Nota de alcance (2026-07-16, decisión del usuario):** por ahora este
> archivo es **solo bitácora** — el mecanismo de detección por comparación
> de versiones y el recoloreo automático de los puntos 3-4 ya están
> diseñados (como se describe arriba) pero **no implementados todavía** en
> `auditor_centro_costos.py`. Mientras tanto, registra las correcciones acá
> a mano a medida que ocurran para no perder el historial; cuando el
> usuario pida activar esto, retomar desde aquí para programar la
> comparación de versiones + recoloreo de fuente en el script.

## Correcciones manuales pendientes de recolorear

| Fecha | Hoja | N° Ref. | Campo / Columna | Valor anterior (rojo) | Valor corregido | Estado |
|---|---|---|---|---|---|---|
| *(sin entradas todavía)* | | | | | | |

## Historial de errores detectados

- **2026-07-17 — `resolver_ruta_actual` no encontraba los 24 documentos del
  bootstrap para renombrar**: `CLAUDE.md` documentaba como "esperado" que
  esos 24 documentos salieran como "archivo no encontrado" al renombrar,
  porque su columna `Archivo origen` en `Master` quedó con el nombre que les
  dio el pipeline perdido (ej. `UMAG\000164.jpg`, por N° Documento) y ese
  archivo ya no existe en disco — el archivo real sigue con su nombre de
  cámara (`IMG_7530.HEIC`). El bug real: `resolver_ruta_actual()`
  (`Sistema/auditor_centro_costos.py`) probaba solo `Archivo origen` y nunca
  caía al mapeo de `reconciliacion_archivos.json`, que sí apunta al archivo
  físico real. Corregido: ahora prueba `Archivo origen` primero y, si esa
  ruta no existe en disco, usa la de `reconciliacion_archivos.json`. Tras el
  fix, los 24 documentos se renombraron/convirtieron correctamente en un
  `run` (22 HEIC→JPG en UMAG + 1 en Cesfam Limache + 1 en Gastos Generales,
  ver detalle de nombres nuevos en el historial de corridas de `MEMORY.md`).
  `CLAUDE.md` §"Estructura de Centro de Costos.xlsx" ya no refleja esta
  limitación — estaba describiendo el bug, no una limitación real.

- **2026-07-17 — Duplicado `PRUE-001`/`PRUE-002` en proyecto "Prueba 1"**:
  durante la sesión de reconstrucción del script del 2026-07-16 (corridas
  entre las 10:12 y las 13:05), dos `run` consecutivos (~12:50 y ~12:53)
  registraron el mismo archivo físico (`IMG_7364.JPEG`) dos veces — la
  detección de "archivo ya cubierto" falló transitoriamente en esa ventana
  de desarrollo (no se repitió en corridas posteriores ni afecta a ningún
  otro proyecto, se verificó que las 26 filas restantes de `Master` no
  tienen otro `Archivo origen` repetido). Al revisar el detalle, el
  documento no era de prueba: es una factura real de Anwo (N° 1913507,
  $2.255.194) cuyas notas indican obra "Cesfam Constitución" — quedó
  guardada bajo una carpeta de prueba durante el desarrollo del pipeline.
  Corrección aplicada: se eliminaron ambas filas duplicadas de
  `Master`/`Detalle` y la hoja "Prueba 1" (edición manual directa sobre el
  `.xlsx`, con backup manual previo en `Respaldos/`), se movió la foto a
  `Documentos Centro de Costos/Cesfam Constitución/`, se corrigió el
  `"proyecto"` en `datos_extraidos.json`, se agregó el prefijo
  `"Cesfam Constitución": "CCON"` a `PREFIJOS_PROYECTO`, y se registró
  limpio como `CCON-001` vía `run` (con renombrado automático de foto a
  `CCON-001_Anwo_2026-06-04.jpeg`). "Cesfam Constitución" es un proyecto
  nuevo, distinto de "Cesfam Limache".
