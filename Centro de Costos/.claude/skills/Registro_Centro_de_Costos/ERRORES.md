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

El valor lo corrige el usuario; la detección, el registro en la bitácora y
el recoloreo son automáticos, no algo que el usuario deba llenar a mano.
**Activado el 2026-07-17** (antes solo bitácora, ver historial de la nota
de alcance más abajo), con confirmación explícita antes de aplicar:

1. Al correr `status` o `run`, o al revisar el Excel manualmente, encuentras
   una celda en **rojo** (`requiere revisión`) — típicamente un N° de
   Documento ilegible (`S/N (...)`), un IVA que no cuadra con el 19% del
   Neto, o un dato dudoso marcado por quien extrajo los datos a
   `datos_extraidos.json`.
2. Corriges el valor **a mano, directo en `Centro de Costos.xlsx`** — este
   paso es siempre manual, del usuario.
3. Al correr `driver.py run` la próxima vez, el script compara la versión
   anterior del libro (el backup más reciente que ya existía en
   `Respaldos/`, antes del que crea esta corrida) contra la versión actual,
   detecta qué celda cambió de valor estando en rojo, y la agrega como
   **"Pendiente"** en `Sistema/correcciones_manuales.json` (fuente de
   verdad) y en la tabla de abajo (100% derivada de ese JSON, se
   regenera completa en cada corrida — el usuario no la edita a mano). En
   este paso **todavía no se toca el Excel**: ni se recolorea ni se
   propaga.
4. El usuario (o el agente en su nombre) revisa la lista de pendientes y
   confirma explícitamente con `python driver.py confirmar --todos` (o
   `confirmar <N_REF> ...` para solo algunas). Recién ahí: se recolorea la
   **fuente** de esa celda de rojo a azul marino oscuro (`1F3864`) — el
   color de relleno no cambia —, se propaga el valor a `Detalle` si el
   campo se repite ahí (hoy: N° Documento), y la fila pasa de "Pendiente" a
   "Aplicado (fecha)" en la columna de estado.
   - `python driver.py confirmar` sin argumentos es solo preview (no toca
     nada) — sirve para revisar qué se aplicaría antes de confirmar.
   - Si la celda se volvió a editar después de detectada (el valor actual
     ya no coincide con el "Valor corregido" logueado), `confirmar` la
     salta con una advertencia en vez de aplicar un valor obsoleto — hay
     que correr `run` de nuevo para que la vuelva a detectar.

Implementación: `detectar_correcciones_manuales`,
`registrar_correcciones_pendientes`, `confirmar_correcciones` y
`regenerar_tabla_errores_md` en `Sistema/auditor_centro_costos.py`; tests
en `Sistema/tests/test_correcciones_manuales.py`.

**Camino alternativo (2026-07-17): skill `/Revision_de_Errores`.** En vez de
que el usuario edite la celda a mano en Excel (pasos 1-2 de arriba) y `run`
la detecte comparando backups (paso 3), el agente recorre las celdas rojas
una por una, muestra la foto del documento, y le pregunta el valor correcto
**en la conversación**; al confirmarlo, `corregir_valor_manual()` lo aplica
de inmediato (recolorea + propaga + queda "Aplicado") sin pasar por
"Pendiente". Mismo destino final en esta tabla, solo cambia cómo se obtiene
el valor — ver
[Revision_de_Errores/SKILL.md](../Revision_de_Errores/SKILL.md) y tests en
`Sistema/tests/test_revision_errores.py`.

> Nota histórica: hasta el 2026-07-16 esto era solo bitácora manual (el
> mecanismo estaba diseñado pero no implementado); el 2026-07-17 se activó
> con el paso de confirmación explícita agregado por pedido del usuario
> (no estaba en el diseño original de 2026-07-16, que recoloreaba en la
> misma corrida que detectaba).

## Correcciones manuales pendientes de recolorear

| Fecha | Hoja | N° Ref. | Campo / Columna | Valor anterior (rojo) | Valor corregido | Estado |
|---|---|---|---|---|---|---|
| 2026-07-17 | Detalle | CCON-004 | Ítems agrupados (desglose) | Materiales varios (Resto de la factura: cañería de cobre recta 1 1/4" y 1 1/2" (cod. CAN2125, CAN2126), espuma aislante térmica 1 1/2x2mt (cod. CAN2276), soldadura de plata al 6% (cod. SOL2005), fundente para soldar plata (cod. SOL2018), tubo de gas MAPP (cod. GAS24548). Cantidades y precios individuales de estas 6 líneas NO son legibles: el timbre 'CANCELADO' del 19/06/2026 tapa la columna de cantidad/precio desde esta línea en adelante. Monto = saldo entre el Neto impreso ($174.118) y la suma de los 5 ítems sí legibles ($58.912) = $115.206.) | Cañería cobre; Cañería cobre; Espuma aislante; Soldadura plata; Fundente soldar; Tubo gas MAPP | Aplicado (2026-07-17) |
| 2026-07-17 | Master | UMAG-003 | IVA 19% (CLP) | 718 | 719 | Aplicado (2026-07-17) |
| 2026-07-17 | Master | UMAG-004 | N° Documento | 11111111 | 2222222 | Aplicado (2026-07-17) |
| 2026-07-17 | Master | UMAG-005 | IVA 19% (CLP) | 0 | 0 | Aplicado (2026-07-17) |
| 2026-07-17 | Master | UMAG-006 | N° Documento | 407866 | 407866 | Aplicado (2026-07-17) |
| 2026-07-17 | Master | UMAG-009 | IVA 19% (CLP) | 0 | 0 | Aplicado (2026-07-17) |
| 2026-07-17 | Master | UMAG-020 | IVA 19% (CLP) | 0 | 0 | Aplicado (2026-07-17) |

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

- **2026-07-17 — `CCON-004` (factura Beckman N° 130020) se registró con 1
  solo ítem resumen en vez del desglose completo**: al leer la foto, el
  timbre "CANCELADO" tapaba la columna de cantidad/precio de 6 de las 11
  líneas, y en vez de dejar esas 6 sin desglosar y registrar las 5 sí
  legibles por separado, el agente agrupó **las 11** en 1 solo ítem
  "Materiales de ferretería" por el Neto total — el usuario lo marcó como
  mal ingreso: **`Detalle` siempre debe llevar el desglose línea por línea
  de la compra, nunca un ítem resumen**, incluso cuando parte de la factura
  no sea legible (ver regla nueva en
  [MEMORY.md](MEMORY.md#reglas-de-negocio-no-son-formato)). Corrección
  aplicada (edición manual directa sobre `Detalle`/`Master`, con backup
  manual previo en `Respaldos/`): se reemplazó la fila única por 6 filas —
  las 5 líneas legibles con su cantidad/precio real (efecto del descuento de
  línea absorbido en el precio unitario efectivo, ver `datos_extraidos.json`)
  y 1 ítem "Materiales varios" agrupando las 6 líneas tapadas por el timbre,
  por el saldo entre el Neto impreso y la suma de las 5 legibles. Si en algún
  momento se consigue una foto sin el timbre encima, desglosar también esas
  6 líneas y actualizar `datos_extraidos.json` + `Detalle`.

- **2026-07-17 — `CCON-004` "Materiales varios" desglosado**: la skill
  `/Revision_de_Errores` agregó soporte para detectar y desglosar ítems de
  `Detalle` agrupados (`listar_items_agrupados`/`desglosar_item_agrupado`,
  convención: nombre con la palabra "varios"). Al probarla contra el Excel
  real, encontró exactamente el caso pendiente documentado más abajo
  (`CCON-004`). La foto del documento resultó ser completamente legible (el
  timbre "CANCELADO" no tapaba los números como se pensó al registrarla la
  primera vez) — los 6 códigos agrupados (CAN2125, CAN2126, CAN2276,
  SOL2005, SOL2018, GAS24548) se leyeron directo de la factura y reconcilian
  exacto con el Neto impreso ($174.118). Se reemplazó la fila "Materiales
  varios" por las 6 filas reales (azul marino), confirmado por el usuario
  antes de aplicar. El pendiente correspondiente en MEMORY.md queda resuelto.

- **2026-07-17 — Regla "N° Documento sin ceros a la izquierda" documentada
  pero nunca implementada**: la regla se agregó a `MEMORY.md` el 2026-07-17
  (mismo día) pero el código nunca se tocó — `escribir_fila_master` y
  `escribir_items_detalle` seguían guardando el N° Documento tal cual venía
  del JSON, y un comentario en el código incluso justificaba lo contrario
  ("se guarda como texto para no perder los ceros"). El usuario lo detectó
  al revisar `CCON-004` (quedó `"0000130020"`) y notó que documentos
  anteriores (`CFLI-001` `"0000130842"`, `UMAG-017` `"0000125796"`, y otros)
  tenían el mismo problema. Corregido: se agregó `normalizar_n_documento()`
  (usada al escribir filas nuevas en Master/Detalle y también al aplicar
  correcciones manuales de esa columna, sea por `confirmar_correcciones` o
  por `corregir_valor_manual`/skill `Revision_de_Errores`) y una migración
  retroactiva idempotente (`migrar_n_documento_sin_ceros`) que corrió sobre
  **todo** el libro existente el 2026-07-17: 42 celdas corregidas entre
  `Master` y `Detalle` (incluye las de todos los proyectos, no solo las
  mencionadas por el usuario).
