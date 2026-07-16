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

*(sin entradas todavía — anotar acá, con fecha: inconsistencias aritméticas
recurrentes entre IVA y Neto, N° Documento duplicados legítimos vs. errores
de tipeo, proveedores con nombres inconsistentes entre documentos, archivos
ilegibles frecuentes, celdas rojas que llevan mucho tiempo sin corregirse,
etc.)*
