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

| Fecha | Hoja | N° Ref. | Campo / Columna | Valor anterior (rojo) | Valor corregido | Estado | Nota |
|---|---|---|---|---|---|---|---|
| 2026-07-17 | Detalle | CCON-004 | Ítems agrupados (desglose) | Materiales varios (Resto de la factura: cañería de cobre recta 1 1/4" y 1 1/2" (cod. CAN2125, CAN2126), espuma aislante térmica 1 1/2x2mt (cod. CAN2276), soldadura de plata al 6% (cod. SOL2005), fundente para soldar plata (cod. SOL2018), tubo de gas MAPP (cod. GAS24548). Cantidades y precios individuales de estas 6 líneas NO son legibles: el timbre 'CANCELADO' del 19/06/2026 tapa la columna de cantidad/precio desde esta línea en adelante. Monto = saldo entre el Neto impreso ($174.118) y la suma de los 5 ítems sí legibles ($58.912) = $115.206.) | Cañería cobre; Cañería cobre; Espuma aislante; Soldadura plata; Fundente soldar; Tubo gas MAPP | Aplicado (2026-07-17) |  |
| 2026-07-17 | Master | UMAG-003 | IVA 19% (CLP) | 718 | 719 | Aplicado (2026-07-17) |  |
| 2026-07-17 | Master | UMAG-004 | N° Documento | 11111111 | 2222222 | Aplicado (2026-07-17) |  |
| 2026-07-17 | Master | UMAG-005 | IVA 19% (CLP) | 0 | 0 | Aplicado (2026-07-17) |  |
| 2026-07-17 | Master | UMAG-006 | N° Documento | 407866 | 407866 | Aplicado (2026-07-17) |  |
| 2026-07-17 | Master | UMAG-009 | IVA 19% (CLP) | 0 | 0 | Aplicado (2026-07-17) |  |
| 2026-07-17 | Master | UMAG-020 | IVA 19% (CLP) | 0 | 0 | Aplicado (2026-07-17) |  |
| 2026-08-19 | Master | CCHI-005 | IVA 19% (CLP) | 1873 | 1873 | Aplicado (2026-08-19) | IVA: $7280 (confirmado) / IEF e IEV/FEPP: no legibles con precision -- combinado ajustado desde Total $40191 - Neto $38318 |
| 2026-08-19 | Master | CCHI-006 | N° Documento | S/N (comprobante debito Dolce Luna 17-03-2026) | 800056347184 | Aplicado (2026-08-19) |  |
| 2026-08-19 | Detalle | CCHI-006 | Ítems agrupados (desglose) | Compra varios (Compra en Dolce Luna, sin desglose de boleta (solo vale de tarjeta débito)) | Alimentación | Aplicado (2026-08-19) |  |
| 2026-08-19 | Master | CCHI-008 | IVA 19% (CLP) | 1905 | 1905 | Aplicado (2026-08-19) | IVA: $7403 / IEF+IEV-FEPP (combinado): $-5498 -- ajustado para que Neto ($38964) + IVA + Impuestos = Total pagado $40869 |
| 2026-08-19 | Master | COMC-006 | IVA 19% (CLP) | 3178 | 3178 | Aplicado (2026-08-19) | IVA: $725 / IEF: $2413 / IEV/FEPP: $40 |
| 2026-08-19 | Master | COMC-007 | IVA 19% (CLP) | 10890 | 10890 | Aplicado (2026-08-19) | IVA: $2540 / IEF: $8190 / IEV/FEPP: $160 |
| 2026-08-19 | Master | CPMO-019 | N° Documento | S/N (Comprobante 000510) | 6857 | Aplicado (2026-08-19) |  |
| 2026-08-19 | Master | CPMO-023 | IVA 19% (CLP) | 4399 | 4399 | Aplicado (2026-08-19) | IVA: $2014 / IEF: $1511 / IEV/FEPP: $874 |
| 2026-08-19 | Master | CREM-006 | IVA 19% (CLP) | 1525 | 6973 | Aplicado (2026-08-19) | IVA: $1525 / IEF: $5238 / IEV/FEPP: $210 |
| 2026-08-19 | Master | CREM-014 | IVA 19% (CLP) | 5925 | 14077 | Aplicado (2026-08-19) | IVA: $5925 / IEF (Impuesto Especifico): $8152 |
| 2026-08-19 | Master | CREM-015 | IVA 19% (CLP) | 7231 | 17678 | Aplicado (2026-08-19) | IVA: $7231 / IEF: $5505 / IEV/FEPP: $4942 |
| 2026-08-19 | Master | CVAL-002 | N° Documento | S/N (peajes Documento 10) | N/A | Aplicado (2026-08-19) |  |
| 2026-08-19 | Master | CVAL-003 | N° Documento | S/N (peajes Documento 11) | N/A | Aplicado (2026-08-19) |  |
| 2026-08-19 | Master | CVAL-004 | N° Documento | S/N (comprobante debito San Ignacio 08-07-2026) | 321782 | Aplicado (2026-08-19) |  |
| 2026-08-19 | Master | CVAL-005 | N° Documento | S/N (peajes Documento 13) | N/A | Aplicado (2026-08-19) |  |
| 2026-08-19 | Master | CVAL-011 | IVA 19% (CLP) | 13639 | 13699 | Aplicado (2026-08-19) |  |
| 2026-08-19 | Master | CVAL-014 | IVA 19% (CLP) | 7956 | 7956 | Aplicado (2026-08-19) | IVA: $6470 / IEF: $3791 / IEV/FEPP: $-2305 |
| 2026-08-19 | Master | CVAL-015 | IVA 19% (CLP) | 10937 | 10937 | Aplicado (2026-08-19) | IVA: $8884 / IEF: $5241 / IEV/FEPP: $-3188 |
| 2026-08-19 | Master | CVAL-016 | IVA 19% (CLP) | 5443 | 8896 | Aplicado (2026-08-19) |  |
| 2026-08-19 | Master | CVAL-017 | IVA 19% (CLP) | 4767 | 4767 | Aplicado (2026-08-19) | IVA: $7898 / IEF: $1 / IEV/FEPP: $0 (según factura; total pagado $46.335 respetado como ancla) |
| 2026-08-19 | Master | CVAL-018 | IVA 19% (CLP) | 8799 | 8799 | Aplicado (2026-08-19) | IVA: $7188 / IEF: $4111 / IEV/FEPP: $-2500 |
| 2026-08-19 | Master | CVAL-020 | IVA 19% (CLP) | 11999 | 11999 | Aplicado (2026-08-19) | IVA: $7765 / IEF: $4226 / IEV/FEPP: $8 (no incluye propina $200) |
| 2026-08-20 | Detalle | CCON-007 | P. Unitario/Total sin IVA (typo) | 96604 | 98604 | Aplicado (2026-08-20) |  |
| 2026-08-20 | Master | CCON-007 | IVA 19% (CLP) | 18735 | 18735 | Aplicado (2026-08-20) | IVA ya era correcto (18735, factura Anwo N 1913608); la celda estaba roja porque el item en Detalle tenia un typo (96604 en vez de 98604 = Neto real del documento). Corregido el item ademas de esta celda. |
| 2026-08-20 | Master | CCON-008 | IVA 19% (CLP) | 3010 | 3010 | Aplicado (2026-08-20) | IVA ya era correcto (3010, factura Ferreteria El Experto N 144358: Neto 15840, IVA 3010, Total 18850). No se identifico ninguna inconsistencia real en Detalle. |
| 2026-08-20 | Master | CCON-012 | N° Documento | S/N (Documento (17).pdf) | 2133669 | Aplicado (2026-08-20) |  |
| 2026-08-20 | Detalle | CCON-012 | Diesel: P.Unitario/Total sin IVA | 43513 | 31496 | Aplicado (2026-08-20) |  |
| 2026-08-20 | Master | CCON-012 | IVA 19% (CLP) | 0 | 12017 | Aplicado (2026-08-20) | IVA: $5984 / IEF: $3203 / IEV-FEPP: $2830 |
| 2026-08-20 | Master/Detalle | CCON-012/013 | Restructuracion: documentos mezclados separados | CCON-012 (Diesel+Snack) y CCON-013 (Estacionamiento+Combo comida) mezclaban 2 documentos cada uno | CCON-012=Diesel, CCON-013=Estacionamiento, CCON-024=Snack, CCON-025=Combo Nuggets, CCON-026=Compra $65.673 (sin desglose) | Aplicado (2026-08-20) |  |
| 2026-08-20 | Master | CCON-013 | N° Documento | S/N (Documento (18).pdf) | 9669 | Aplicado (2026-08-20) |  |
| 2026-08-20 | Master | CCON-017 | IVA 19% (CLP) | 179869 | 179889 | Aplicado (2026-08-20) |  |
| 2026-08-20 | Detalle | CCON-019 | Ítems (descuento agregado + recalculo Total con IVA) | 4 items sin descuento, Total sin IVA=21854 | 5 items con Descuento(-4155), Total sin IVA=17699, tasa real=0.1900 | Aplicado (2026-08-20) |  |
| 2026-08-20 | Master | CCON-019 | IVA 19% (CLP) | 3363 | 3363 | Aplicado (2026-08-20) | IVA ya era correcto (3363, boleta Easy N 3011208173); la celda estaba roja porque Detalle no incluia el descuento de -4155 del documento. Se agrego la linea Descuento y se recalculo Total con IVA de los 5 items con la tasa real (~19.0%). |
| 2026-08-20 | Detalle | MLER-004 | Items (descuento agregado + recalculo Total con IVA) | 3 items sin descuento, Total sin IVA=78908 | 4 items con Descuento(-7891), Total sin IVA=71017, tasa real=0.1900 | Aplicado (2026-08-20) |  |
| 2026-08-20 | Master | MLER-004 | N° Documento | S/N (Documento (2).pdf) | Ilegible | Aplicado (2026-08-20) |  |
| 2026-08-20 | Master | MLER-004 | IVA 19% (CLP) | 13493 | 13493 | Aplicado (2026-08-20) | IVA ya era correcto (13493, factura Hojalateria Clinica del Hogar: Neto 71017 tras descuento de 7891, IVA 13493, Total 84510). Se agrego la linea Descuento a Detalle y se recalculo Total con IVA de los 3 items con la tasa real. |
| 2026-08-20 | Master/Detalle | UMAG-028/029/030/031 | Restructuracion: documentos mezclados separados | UMAG-028 (7 docs), UMAG-029 (7 docs), UMAG-030 (2 docs) mezclaban varios documentos cada uno | UMAG-028=Tur Bus, UMAG-029=El Horreo(19-01), UMAG-030=Rendic(24-01), UMAG-031=El Horreo(21-01, ya estaba separado), UMAG-032..037=6 docs de UMAG-028, UMAG-038..043=6 docs de UMAG-029, UMAG-044=Rendic(20-01) de UMAG-030 | Aplicado (2026-08-20) |  |
| 2026-08-26 | Master | HPIN-148 | IVA 19% (CLP) | 6883 | 6883 | Aplicado (2026-08-26) | IVA: $2492 / Impuesto Especifico: $4391 |
| 2026-08-26 | Master | JUNJ-001 | IVA 19% (CLP) | 10661 | 10661 | Aplicado (2026-08-26) | IVA: $3674 / IEF: $9019 / IEV/FEPP: $-2032 |
| 2026-08-26 | Master | JUNJ-002 | IVA 19% (CLP) | 9219 | 9219 | Aplicado (2026-08-26) | IVA: $3948 / IEF: $9019 / IEV/FEPP: $-3748 |
| 2026-08-26 | Master | JUNJ-015 | IVA 19% (CLP) | 10661 | 10661 | Aplicado (2026-08-26) | IVA: $3674 / IEF: $9019 / IEV/FEPP: $-2032 |
| 2026-08-26 | Master | JUNJ-018 | IVA 19% (CLP) | 2142 | 2142 | Aplicado (2026-08-26) | IVA correcto segun factura: Neto $11.275 x 19% = $2.142 |
| 2026-08-26 | Master | JUNJ-020 | IVA 19% (CLP) | 10410 | 10410 | Aplicado (2026-08-26) | IVA correcto segun factura: Neto $54.789 x 19% = $10.410 |
| 2026-08-26 | Master | JUNJ-022 | IVA 19% (CLP) | 7663 | 7663 | Aplicado (2026-08-26) | IVA: $2344 / IEF: $6012 / IEV/FEPP: $-693 |
| 2026-08-26 | Master | JUNJ-023 | IVA 19% (CLP) | 10661 | 10661 | Aplicado (2026-08-26) | IVA: $3674 / IEF: $9019 / IEV/FEPP: $-2032 |
| 2026-08-26 | Master | JUNJ-053 | IVA 19% (CLP) | 23149 | 23149 | Aplicado (2026-08-26) | IVA: $8081 / IEF: $17462 / IEV/FEPP: $-2394 |
| 2026-09-03 | Master | FCH2-014 | IVA 19% (CLP) | 6956 | 12010 | Aplicado (2026-09-03) | IVA: $4.398 / IEF: $10.002 / IEV/FEPP: $-2.390. Total factura: $35.156. Propina de $300 excluida. |
| 2026-09-03 | Master/Detalle | FCH2-014/FCH2-040 | Reestructuración: documentos mezclados separados | FCH2-014 mezclaba facturas 161847 (01-09-2026) y 233462 (28-08-2026) en un solo registro | FCH2-014=factura 233462; FCH2-040=factura 161847; archivos físicos duplicados | Aplicado (2026-09-03) |  |
| 2026-09-03 | Master | FCH2-021 | IVA 19% (CLP) | 31438 | 26804 | Aplicado (2026-09-03) | Neto impreso $141.076; IVA $26.804; Total $167.880. |
| 2026-09-03 | Master/Detalle | FCH2-021/FCH2-046 | Reestructuración: documentos mezclados separados | FCH2-021 mezclaba la factura Sodimac 149001852 y la boleta Aliservice 0002801098 en un solo registro | FCH2-021=factura Sodimac 149001852; FCH2-046=boleta Aliservice 2801098; archivos físicos duplicados | Aplicado (2026-09-03) |  |
| 2026-09-03 | Master | FCH2-023 | IVA 19% (CLP) | 13599 | 10613 | Aplicado (2026-09-03) | IVA: $4.572 / Impuesto específico: $6.041. Total factura: $34.676. |
| 2026-09-03 | Master/Detalle | FCH2-023/FCH2-044/FCH2-045 | Reestructuración: documentos mezclados separados | FCH2-023 mezclaba las facturas de combustible 289353, 290041 y 289928 en un solo registro | FCH2-023=factura 289353; FCH2-044=factura 290041; FCH2-045=factura 289928; archivos físicos duplicados | Aplicado (2026-09-03) |  |
| 2026-09-03 | Master | FCH2-024 | IVA 19% (CLP) | 14840 | 13151 | Aplicado (2026-09-03) | IVA: $5.908 / Impuesto específico: $7.243. Total factura: $44.243. |
| 2026-09-03 | Master/Detalle | FCH2-024/FCH2-047/FCH2-048 | Reestructuración: documentos mezclados separados | FCH2-024 mezclaba las facturas de combustible 289151, 289728 y 289532 en un solo registro | FCH2-024=factura 289151; FCH2-047=factura 289728; FCH2-048=factura 289532; archivos físicos duplicados | Aplicado (2026-09-03) |  |
| 2026-09-03 | Master | FCH2-025 | IVA 19% (CLP) | 9377 | 5818 | Aplicado (2026-09-03) | Precios netos derivados de los importes con IVA por línea; Neto impreso $30.622; IVA $5.818; Total $36.440. |
| 2026-09-03 | Master/Detalle | FCH2-025/FCH2-049 | Reestructuración: documentos mezclados separados | FCH2-025 mezclaba las facturas Easy 38729190 y Sodimac 149110252 en un solo registro; Easy usaba precios con IVA como netos | FCH2-025=factura Easy 38729190 con precios netos corregidos; FCH2-049=factura Sodimac 149110252; archivos físicos duplicados | Aplicado (2026-09-03) |  |
| 2026-09-03 | Master | FCH2-028 | IVA 19% (CLP) | 6641 | 2453 | Aplicado (2026-09-03) | Precios unitarios netos derivados del Neto impreso ($12.907); IVA impreso $2.453; Total $15.360. |
| 2026-09-03 | Master/Detalle | FCH2-028/FCH2-041 | Reestructuración: documentos mezclados separados | FCH2-028 mezclaba las facturas Easy 38877338 y Sodimac 149340471 en un solo registro | FCH2-028=factura Easy 38877338; FCH2-041=factura Sodimac 149340471; archivos físicos duplicados | Aplicado (2026-09-03) |  |
| 2026-09-03 | Master | FCH2-030 | IVA 19% (CLP) | 14267 | 13945 | Aplicado (2026-09-03) | IVA: $5.062 / Impuesto específico: $8.883. Total factura: $40.585. |
| 2026-09-03 | Master/Detalle | FCH2-030/FCH2-042/FCH2-043 | Reestructuración: documentos mezclados separados | FCH2-030 mezclaba las facturas de combustible 289726, 289448 y 289447 en un solo registro | FCH2-030=factura 289726; FCH2-042=factura 289448; FCH2-043=factura 289447; archivos físicos duplicados | Aplicado (2026-09-03) |  |
| 2026-09-03 | Master | FCH2-031 | IVA 19% (CLP) | 7019 | 13239 | Aplicado (2026-09-03) | IVA impreso: $4.345 / IEF+IEV-FEPP combinado inferido: $8.894. Neto imponible inferido desde IVA/19%: $22.868; Total boleta: $36.107. |
| 2026-09-03 | Master/Detalle | FCH2-031/FCH2-050/FCH2-051 | Reestructuración: documentos mezclados separados | FCH2-031 mezclaba la boleta Copec 3128047, la factura Librería Babu 42968 y registraba erróneamente un estacionamiento 0092226332; el tercer documento real es la boleta Donde Camilo 250241 | FCH2-031=boleta Copec 3128047; FCH2-050=factura Librería Babu 42968; FCH2-051=boleta Donde Camilo 250241; archivos físicos duplicados | Aplicado (2026-09-03) |  |
| 2026-09-03 | Master | FCH2-040 | IVA 19% (CLP) | Nuevo registro separado | 7304 | Aplicado (2026-09-03) | IVA: $2.558 / IEF: $6.125 / IEV/FEPP: $-1.379. Total factura: $20.767. |
| 2026-09-03 | Master | FCH2-041 | IVA 19% (CLP) | Nuevo registro separado | 4188 | Aplicado (2026-09-03) | Neto impreso $22.042; IVA $4.188; Total $26.230. |
| 2026-09-03 | Master | FCH2-042 | IVA 19% (CLP) | Nuevo registro separado | 12230 | Aplicado (2026-09-03) | IVA: $4.245 / Impuesto específico: $7.985. Total factura: $34.572. Propina de $500 excluida. |
| 2026-09-03 | Master | FCH2-043 | IVA 19% (CLP) | Nuevo registro separado | 13665 | Aplicado (2026-09-03) | IVA: $4.960 / Impuesto específico: $8.705. Total factura: $39.773. Propina de $500 excluida. |
| 2026-09-03 | Master | FCH2-044 | IVA 19% (CLP) | Nuevo registro separado | 13853 | Aplicado (2026-09-03) | IVA: $4.454 / Impuesto específico: $9.399. Total factura: $37.292. |
| 2026-09-03 | Master | FCH2-045 | IVA 19% (CLP) | Nuevo registro separado | 12598 | Aplicado (2026-09-03) | IVA: $4.573 / Impuesto específico: $8.025. Total factura: $36.667. Propina de $500 excluida. |
| 2026-09-03 | Master | FCH2-046 | IVA 19% (CLP) | Nuevo registro separado | 4630 | Aplicado (2026-09-03) | Neto impreso $24.370; IVA correcto $4.630 (la extracción anterior registró $4.634); Total $29.000. |
| 2026-09-03 | Master | FCH2-047 | IVA 19% (CLP) | Nuevo registro separado | 12192 | Aplicado (2026-09-03) | IVA: $4.232 / Impuesto específico: $7.960. Total factura: $34.464. |
| 2026-09-03 | Master | FCH2-048 | IVA 19% (CLP) | Nuevo registro separado | 12948 | Aplicado (2026-09-03) | IVA: $4.700 / Impuesto específico: $8.248. Total factura: $37.685. Propina de $500 excluida. |
| 2026-09-03 | Master | FCH2-049 | IVA 19% (CLP) | Nuevo registro separado | 3559 | Aplicado (2026-09-03) | Neto impreso $18.731; IVA $3.559; Total $22.290. |
| 2026-09-03 | Master | FCH2-050 | IVA 19% (CLP) | Nuevo registro separado | 2323 | Aplicado (2026-09-03) | Precios netos derivados de los importes con IVA por línea; Neto impreso $12.227; IVA $2.323; Total $14.550. |
| 2026-09-03 | Master | FCH2-051 | IVA 19% (CLP) | Nuevo registro separado | 3113 | Aplicado (2026-09-03) | Venta neta $16.387; IVA $3.113; subtotal $19.500. Propina de $1.950 excluida del total pagado de $21.450. |
| 2026-09-07 | Master | FCH1-021 | IVA 19% (CLP) | 15491 | 13383 | Aplicado (2026-09-07) | IVA: $6.012 / IEF: $7.371. Total factura: $45.025. |
| 2026-09-07 | Master/Detalle | FCH1-021/046/047 | Reestructuración: documentos mezclados separados | FCH1-021 mezclaba las facturas Copec 288946, 289533 y 289351 en un solo registro | FCH1-021=factura 288946; FCH1-046=factura 289533; FCH1-047=factura 289351; archivo físico duplicado | Aplicado (2026-09-07) |  |
| 2026-09-07 | Master | FCH1-024 | IVA 19% (CLP) | 15830 | 10585 | Aplicado (2026-09-07) | IVA: $4.757 / IEF: $5.828. Total factura: $35.621. Propina de $500 excluida. |
| 2026-09-07 | Master/Detalle | FCH1-024/048/049 | Reestructuración: documentos mezclados separados | FCH1-024 mezclaba las facturas Copec 288841, 289251 y 289258 en un solo registro | FCH1-024=factura 288841; FCH1-048=factura 289251; FCH1-049=factura 289258; archivo físico duplicado | Aplicado (2026-09-07) |  |
| 2026-09-07 | Master | FCH1-026 | IVA 19% (CLP) | 10578 | 13355 | Aplicado (2026-09-07) | IVA: $5.867 / IEF: $12.779 / IEV-FEPP: $-5.291. Total factura: $44.231. |
| 2026-09-07 | Master/Detalle | FCH1-026/050 | Reestructuración: documentos mezclados separados | FCH1-026 mezclaba la factura Valencia y Pacheco (diesel) 2147334 y la factura Comercial Silva (gasolina) 285726 en un solo registro | FCH1-026=factura 285726; FCH1-050=factura 2147334; archivo físico duplicado | Aplicado (2026-09-07) |  |
| 2026-09-07 | Master | FCH1-027 | IVA 19% (CLP) | 7061 | 2844 | Aplicado (2026-09-07) | IVA: $2.310 / IEF: $1.362 / IEV-FEPP: $-828 (diesel). Total factura: $15.000. |
| 2026-09-07 | Master/Detalle | FCH1-027/051 | Reestructuración: documentos mezclados separados | FCH1-027 mezclaba la factura Horta y Horta (diesel) 231680 y la factura Comercial Silva (gasolina) 286868 en un solo registro | FCH1-027=factura 231680; FCH1-051=factura 286868; archivo físico duplicado | Aplicado (2026-09-07) |  |
| 2026-09-07 | Master | FCH1-028 | Categoría / IVA 19% (CLP) | Ferreteria / 8158 | Combustible / 20209 | Aplicado (2026-09-07) | IVA: $6.552 / IEF: $13.657. Total factura: $54.691. |
| 2026-09-07 | Master/Detalle | FCH1-028/052 | Reestructuración: documentos mezclados separados | FCH1-028 mezclaba la factura ferretería Milan Fabjanovic 3415592 y la factura Comercial Silva (gasolina) 285811 en un solo registro | FCH1-028=factura 285811 (gasolina); FCH1-052=factura 3415592 (ferretería, 5 ítems); archivo físico duplicado | Aplicado (2026-09-07) |  |
| 2026-09-07 | Master | FCH1-046 | IVA 19% (CLP) | Nuevo registro separado | 11752 | Aplicado (2026-09-07) | IVA: $4.079 / IEF: $7.673. Total factura: $33.224. |
| 2026-09-07 | Master | FCH1-047 | IVA 19% (CLP) | Nuevo registro separado | 12021 | Aplicado (2026-09-07) | IVA: $5.400 / IEF: $6.621. Total factura: $40.444. |
| 2026-09-07 | Master | FCH1-048 | IVA 19% (CLP) | Nuevo registro separado | 10917 | Aplicado (2026-09-07) | IVA: $4.703 / IEF: $6.214. Total factura: $35.668. |
| 2026-09-07 | Master | FCH1-049 | IVA 19% (CLP) | Nuevo registro separado | 14180 | Aplicado (2026-09-07) | IVA: $6.370 / IEF: $7.810. Total factura: $47.704. |
| 2026-09-07 | Master | FCH1-050 | IVA 19% (CLP) | Nuevo registro separado | 5796 | Aplicado (2026-09-07) | IVA: $4.711 / IEF: $1.085 (diesel). Total factura: $30.591. |
| 2026-09-07 | Master | FCH1-051 | IVA 19% (CLP) | Nuevo registro separado | 10982 | Aplicado (2026-09-07) | IVA: $4.751 / IEF: $6.231. Total factura: $35.989. |
| 2026-09-07 | Master | FCH1-052 | IVA 19% (CLP) | Nuevo registro separado | 1606 | Aplicado (2026-09-07) | IVA 19% puro (ferretería, sin impuesto específico). Total factura: $10.059. |
| 2026-09-07 | Master | FCH2-017 | Categoría / IVA 19% (CLP) | Ferreteria / 67073 | Combustible / 18279 | Aplicado (2026-09-07) | IVA: $6.757 / IEF: $11.522. Total factura: $53.844. |
| 2026-09-07 | Master/Detalle | FCH2-017/052 | Reestructuración: documentos mezclados separados | FCH2-017 mezclaba la factura ferretería Pernos KIM 771530 y la factura Comercial Silva (gasolina) 285135 en un solo registro | FCH2-017=factura 285135 (gasolina); FCH2-052=factura 771530 (ferretería, 3 ítems); archivo físico duplicado | Aplicado (2026-09-07) |  |
| 2026-09-07 | Master | FCH2-029 | IVA 19% (CLP) | 12086 | 8447 | Aplicado (2026-09-07) | IVA 19% puro (ferretería, sin impuesto específico). Total factura: $52.908. |
| 2026-09-07 | Master/Detalle | FCH2-029/053 | Reestructuración: documentos mezclados separados | FCH2-029 mezclaba la factura ferretería Pernos ZAP 101241 y la factura A y D Ltda. (gasolina) 358094 en un solo registro | FCH2-029=factura 101241 (ferretería, 4 ítems); FCH2-053=factura 358094 (gasolina); archivo físico duplicado | Aplicado (2026-09-07) |  |
| 2026-09-07 | Master | FCH2-052 | IVA 19% (CLP) | Nuevo registro separado | 60316 | Aplicado (2026-09-07) | IVA 19% puro (ferretería, sin impuesto específico). Total factura: $377.766. |
| 2026-09-07 | Master | FCH2-053 | IVA 19% (CLP) | Nuevo registro separado | 11051 | Aplicado (2026-09-07) | IVA: $3.639 / IEF: $8.497 / IEV-FEPP: $-1.085. Total factura: $30.202. |
| 2026-09-07 | Master/Detalle | GGEN-002 | Signo de IVA / P.Unitario / Totales (AYRSA) | Negativo (IVA -13990; P.Unit -8386) | Positivo (IVA 13990; P.Unit 8386) | Aplicado (2026-09-07) | Factura Aislantes y Recubrimiento S.A. (AYRSA) N.35470 se habia registrado en negativo el 2026-08-20 interpretandola como reposicion de material a favor de la empresa; el usuario confirmo 2026-09-07 que es una factura normal (costo), se revierte el signo a positivo. |
| 2026-09-10 | Detalle | FCH1-031 | Ítems agrupados (desglose) | Materiales varios (Trabavolante de tablero Datrak y set 10 sacos escombro 25kg 60x90cm, Factura N°38659653 (23-07-2026)) | Trabavolante tablero; Sacos escombro | Aplicado (2026-09-10) |  |
| 2026-09-10 | Detalle | FCH1-031 | Ítems agrupados (desglose) | Materiales varios (Cinta Temflex 19mmx18m (2 colores) y martillo soldador 500W, Boleta N°271883989 (29-07-2026)) | Cinta Temflex negra; Cinta Temflex roja; Martillo soldador | Aplicado (2026-09-10) |  |
| 2026-09-10 | Detalle | HPIN-017 | Item 'Sellante' (cantidad x precio unitario) | 1 x 10490 | 1 x 8815.126050420167 | Aplicado (2026-09-10) | Factura Electronica Easy N 373090 (03-03-2026) imprime NETO 22.580 + IVA 4.290 = TOTAL 26.870. Los tres items estaban cargados con el precio CON IVA incluido, por eso el neto del documento quedaba igual al bruto. Precio neto = precio con IVA / 1,19. |
| 2026-09-10 | Detalle | HPIN-017 | Item 'Silicona' (cantidad x precio unitario) | 1 x 9490 | 1 x 7974.789915966387 | Aplicado (2026-09-10) | Factura Electronica Easy N 373090 (03-03-2026) imprime NETO 22.580 + IVA 4.290 = TOTAL 26.870. Los tres items estaban cargados con el precio CON IVA incluido, por eso el neto del documento quedaba igual al bruto. Precio neto = precio con IVA / 1,19. |
| 2026-09-10 | Detalle | HPIN-017 | Item 'Cinta aluminio' (cantidad x precio unitario) | 1 x 6890 | 1 x 5789.915966386555 | Aplicado (2026-09-10) | Factura Electronica Easy N 373090 (03-03-2026) imprime NETO 22.580 + IVA 4.290 = TOTAL 26.870. Los tres items estaban cargados con el precio CON IVA incluido, por eso el neto del documento quedaba igual al bruto. Precio neto = precio con IVA / 1,19. |
| 2026-09-10 | Detalle | HPIN-157 | Item 'Perno' (cantidad x precio unitario) | 40 x 599 | 48 x 599 | Aplicado (2026-09-10) | Factura Sodiper N 181734 (02-02-2026): la linea 'PS HEX ZIN G2 3/4 X 3 1/2' dice 48 x 599 = 28.752, no 40 x 599 = 23.960. Con 48 el neto del documento da 73.710 y el IVA declarado (14.005) pasa a ser exactamente su 19%. La diferencia eran 8 unidades = 4.792. |
| 2026-09-10 | Master | HPIN-176 | Tipo Documento | Arriendo | Factura | Aplicado (2026-09-10) | El documento es una FACTURA ELECTRONICA de Teckup por 'TERMINO ARRIENDO SEGUN DEVOLUCION AL 05-03-2026'; neto 55.940 + IVA 19% 10.629 = 66.569. 'Arriendo' era el concepto de la compra, no el tipo de documento tributario. |
| 2026-09-10 | Master | HPIN-180 | N° Documento | S/N (Documento (28).pdf) | 8597488 | Aplicado (2026-09-10) | Factura Electronica Esmax Red Ltda (RUT 79706120-4) N 8597488, 24-02-2026. Leida rotando el escaneo 270 grados. OJO: el neto registrado (21.291) tampoco calza con el documento -- Gasolina 95 neto 16.394 + Imp. Especifico 10.491 + IVA 3.115 = Total 30.000. |
| 2026-09-10 | Detalle | HPIN-180 | Item 'Combustible' (cantidad x precio unitario) | 1 x 21291 | 1 x 16394 | Aplicado (2026-09-10) | Factura Esmax 8597488 (24-02-2026): Gasolina 95, 24,71 L, TOTAL NETO 16.394. El valor anterior (21.291) no corresponde a ninguna cifra del documento -- el escaneo estaba de cabeza y mal leido. El impuesto especifico (10.491) pasa a la columna de impuesto junto con el IVA, que es la convencion del modulo (Neto + iva = total pagado). |
| 2026-09-10 | Master | HPIN-180 | IVA 19% (CLP) | 3115 | 13606 | Aplicado (2026-09-10) | IVA: $3.115 / Impuesto Especifico Gasolina: $10.491. Total pagado 16.394 + 13.606 = 30.000, que es el TOTAL impreso en la factura Esmax 8597488. |
| 2026-09-10 | Detalle | JUNJ-004 | Item 'Diesel' (cantidad x precio unitario) | 1 x 21008.4034 | 1 x 18994 | Aplicado (2026-09-10) | Factura Comercial San Agustin N 509.413 del 05-03-2026: TOTAL NETO 18.994, IVA 19% 3.609, IE 2.733, IEV/FEPP -336, TOTAL 25.000. El neto registrado (21.008) era el total dividido por 1,19 porque la extraccion no trajo el IVA desglosado; el total ya era correcto. |
| 2026-09-10 | Master | JUNJ-004 | IVA 19% (CLP) | 3992 | 6006 | Aplicado (2026-09-10) | IVA: $3.609 / Impuesto Especifico: $2.733 / IEV-FEPP: $-336. Neto 18.994 + 6.006 = 25.000, el TOTAL impreso en la factura San Agustin 509.413. |
| 2026-09-10 | Detalle | JUNJ-009 | Item 'Gasolina' (cantidad x precio unitario) | 15.642 x 1050.3396 | 15.642 x 869.9655 | Aplicado (2026-09-10) | Factura Enex (V&P Estaciones de Servicio) N 16892 del 21-03-2026: Gasolina 93, 15,642 x 869,9655 = TOTAL NETO 13.608. El precio unitario registrado (1.050,3396) daba un neto de 16.429 y un total de 19.551, pero el documento dice Monto Total 18.551 -- en palabras: 'dieciocho mil quinientos cincuenta y un pesos'. Eran 1.000 pesos de mas. |
| 2026-09-10 | Master | JUNJ-009 | IVA 19% (CLP) | 3122 | 4943 | Aplicado (2026-09-10) | IVA: $2.586 / Impuesto Especifico: $2.357. Neto 13.608 + 4.943 = 18.551, el Monto Total impreso en la factura Enex 16892. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Soplador' (cantidad x precio unitario) | 1 x 39990 | 1 x 33605.584138330756 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Compresor de aire' (cantidad x precio unitario) | 2 x 1390 | 1 x 25202.087229520865 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Cinta sella hilo' (cantidad x precio unitario) | 2 x 1090 | 2 x 1168.0860703245748 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Cinta sella hilo' (cantidad x precio unitario) | 1 x 2590 | 2 x 915.9811630602782 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Puntas torsion' (cantidad x precio unitario) | 1 x 1290 | 1 x 2176.505699381762 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Disco desbaste' (cantidad x precio unitario) | 9 x 550 | 1 x 1084.0511012364761 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Disco de corte' (cantidad x precio unitario) | 1 x 6990 | 9 x 462.192329984544 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Cuchilla' (cantidad x precio unitario) | 1 x 2990 | 1 x 5874.044339258115 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Panos' (cantidad x precio unitario) | 1 x 4290 | 1 x 2512.645575734158 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Set brochas' (cantidad x precio unitario) | 1 x 3490 | 1 x 3605.1001738794434 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Destornillador' (cantidad x precio unitario) | 1 x 1990 | 1 x 2932.8204211746524 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-072 | Item 'Destornillador' (cantidad x precio unitario) | 1 x 2990 | 1 x 1672.2958848531684 | Aplicado (2026-09-10) | Factura Easy Retail N 37918880 (20-04-2026): NETO 86.993 + IVA 16.527 = 103.520. En el libro los montos estaban CORRIDOS una linea (cada descripcion llevaba el monto del item siguiente) y ademas en precio bruto. Reconstruido segun el documento, en precio neto proporcional. |
| 2026-09-10 | Detalle | JUNJ-077 | Item 'Guantes' (cantidad x precio unitario) | 1 x 2390 | 1 x 2008.4033613445379 | Aplicado (2026-09-10) | Boleta Easy Quilpue (14-04-2026) imprime NETO 9.126 + IVA 1.734 = TOTAL 10.860. Los items estaban cargados con el precio CON IVA incluido. Precio neto = precio con IVA / 1,19. |
| 2026-09-10 | Detalle | JUNJ-077 | Item 'Esponja' (cantidad x precio unitario) | 1 x 2490 | 1 x 2092.436974789916 | Aplicado (2026-09-10) | Boleta Easy Quilpue (14-04-2026) imprime NETO 9.126 + IVA 1.734 = TOTAL 10.860. Los items estaban cargados con el precio CON IVA incluido. Precio neto = precio con IVA / 1,19. |
| 2026-09-10 | Detalle | JUNJ-077 | Item 'Panos' (cantidad x precio unitario) | 2 x 2990 | 2 x 2512.6050420168067 | Aplicado (2026-09-10) | Boleta Easy Quilpue (14-04-2026) imprime NETO 9.126 + IVA 1.734 = TOTAL 10.860. Los items estaban cargados con el precio CON IVA incluido. Precio neto = precio con IVA / 1,19. |
| 2026-09-10 | Master | JUNJ-080 | N° Documento | 1913313 | 1843273 | Aplicado (2026-09-10) | Guia de Despacho Anwo N 1843273 (leida del PDF). Estaba registrada con 1913313, que es el N de la FACTURA JUNJ-020. |
| 2026-09-10 | Master | JUNJ-081 | N° Documento | 1913313 | 1843272 | Aplicado (2026-09-10) | Guia de Despacho Anwo N 1843272 (leida del PDF). Estaba registrada con 1913313, que es el N de la FACTURA JUNJ-020. |
| 2026-09-10 | Master | JUNJ-082 | N° Documento | 1913014 | 1843044 | Aplicado (2026-09-10) | Guia de Despacho Anwo N 1843044 (leida del PDF). Estaba registrada con 1913014, que es el N de la FACTURA del mismo panel (JUNJ-024). |

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

- **2026-09-07 — 8 documentos duplicados registrados en FACH2 (`FCH2-052`
  a `FCH2-059`)**: un `run` de `/Actualizar_Finanzas` registró 8 archivos
  nuevos (`FACH2\Documento (1).pdf` a `Documento (8).pdf`) que resultaron
  ser las mismas 8 facturas ya registradas antes como `FCH2-001`, `FCH2-012`,
  `FCH2-022`, `FCH2-033`, `FCH2-034`, `FCH2-035`, `FCH2-036` y `FCH2-037`
  (mismo proveedor, misma fecha, mismo N° Documento) — alguien volvió a subir
  esas fotos/PDF a la carpeta compartida con nombres genéricos, y el
  inventario las vio como pendientes nuevas. El informe de auditoría del
  propio `run` las marcó correctamente en "POSIBLES DUPLICADOS", lo que
  permitió detectarlas antes de publicar. Duplicaron $672.592 CLP de gasto en
  el proyecto FACH2. Corrección aplicada (backup manual previo, script
  puntual reutilizando `capturar_fila`/`escribir_snapshot_fila`/
  `escribir_formulas_master`/`regenerar_pie`/`regenerar_hoja_proyecto` de
  `auditor_centro_costos.py` para eliminar las 8 filas de `Master`/`Detalle`
  y regenerar correctamente las fórmulas y las 21 hojas de proyecto
  afectadas por el corrimiento de filas): Master volvió a 542 documentos,
  Detalle a 1220 ítems, gasto total con IVA de $49.266.831 a $48.594.239.
  Los 3 tableros (Centro de Costos, Análisis Financiero, Cotizador Histórico)
  se regeneraron después de la corrección. Los 8 archivos físicos duplicados
  se movieron a `259. FACH 2/Duplicados/` (no se borraron) para que no se
  vuelvan a registrar por error en un `run` futuro.

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

- **2026-09-07 — 7 documentos más de FCH1/FCH2 con facturas mezcladas
  (`FCH1-021`, `FCH1-024`, `FCH1-026`, `FCH1-027`, `FCH1-028`, `FCH2-017`,
  `FCH2-029`)**: durante una revisión completa de las 55 celdas rojas del
  libro (`/Revision_de_Errores`, recorrido de todos los proyectos), 7
  resultaron ser el mismo patrón ya visto el 2026-09-03 en FCH2 —el N°
  Documento venía con 2-3 folios separados por coma ("288946, 289533 y
  289351"), señal de que la foto/PDF escaneó varias facturas juntas bajo un
  solo N° Ref, ocultando sus fechas reales. Se separó cada una en un N° Ref
  propio (`FCH1-046` a `FCH1-052`, `FCH2-052`/`FCH2-053`), con su fecha real,
  y se corrigió el IVA a la convención estándar del libro (Neto = neto
  impreso puro, IVA = 19% + Impuesto Específico + IEV/FEPP combinado para
  combustible) — 5 de los 7 documentos originales tenían el Neto ya
  "plegado" con el Impuesto Específico adentro (convención inversa a la
  estándar, usada solo en estos registros de FCH1/FCH2), lo que hacía que el
  IVA registrado pareciera incorrecto frente al chequeo automático del 19%
  aunque el Total (Neto+IVA) siempre cuadraba con el total pagado impreso.
  3 de los 7 mezclaban además una factura de ferretería (Pernos KIM, Pernos
  ZAP, Milan Fabjanovic) con una de combustible del mismo viaje a la
  estación de servicio — se separaron en N° Ref distintos con su propia
  categoría. Verificado con un diff exacto contra el backup previo a la
  separación: el total del libro (`Detalle.Total con IVA` sumado por
  documento) no cambió salvo $1 de redondeo en los 16 N° Ref involucrados
  (7 originales + 9 nuevos). Bug propio encontrado y corregido en el mismo
  proceso: el script de separación dejó `FCH2-029` con el IVA viejo (12086,
  suma de ambas facturas) en vez del nuevo (8447, solo la ferretería) por
  una línea de código faltante — corregido antes de reflejar/publicar.
  De paso, comparando ese mismo diff se encontró que `GGEN-002` tenía un
  ítem en negativo (-$87.619) heredado de antes de esta sesión, ya
  corregido a positivo por el usuario el mismo día (ver fila de la tabla de
  correcciones arriba) — confirmado como el único caso de signo negativo en
  todo el libro que **no** corresponde a una Nota de Crédito legítima (se
  revisaron los otros 17 ítems negativos del libro: todos pertenecen a
  documentos con Tipo Documento "Nota de Crédito", signo esperado).

- **2026-09-10 — sobreconteo de ~$138.322 neto en `Junji's Valparaiso` por
  registrar guías de despacho junto a su factura (detectado, NO corregido
  todavía)**: al procesar la carpeta `Junji V2` —que resultó ser en parte
  una re-subida de `Junji's Valparaiso/Documento (15)`–`(26)`— se pudieron
  comparar por primera vez las facturas originales contra lo que quedó
  escrito en `Master`. Tres hallazgos, los tres sobre filas ya escritas:
  1. **Factura ANWO 1913313 (28-05-2026) registrada 3 veces**: como factura
     en `Documento (25).pdf` (Neto $65.930) y además como sus dos guías de
     despacho en `Documento (26).pdf` (Neto $70.271) y `Documento (27).pdf`
     (Neto $28.354), ambas **a precio de lista**. El Neto real impreso en la
     factura es **$54.789** (IVA $10.410, Total $65.199) — o sea, además de
     duplicarse, el Neto de la propia fila-factura quedó mal. Sobreconteo:
     $164.555 registrados vs $54.789 reales = **+$109.766**.
  2. **Factura ANWO 1913076 (20-05-2026)**: `Documento (23).pdf` quedó con
     Neto $14.351; el impreso es **$11.275** (y $11.275 × 19% = $2.142, que
     es exactamente el IVA ya registrado — por eso la celda estaba en rojo
     en el cuadre de impuesto, la señal era correcta). Sobreconteo
     **+$3.076**.
  3. **Factura Treck 3082742 + su guía 2930582 (03-08-2026)**: registradas
     las dos, `Documento (19).pdf` y `Documento (20).pdf`, con los mismos 4
     ítems y el mismo monto (Neto $25.480 c/u). Sobreconteo **+$25.480**.

  **Regla que se desprende (aplicada ya en esta corrida)**: cuando una guía
  de despacho y su factura están las dos disponibles, se registra **solo la
  factura** — la guía trae precios de lista sin descuento y el mismo
  despacho, así que registrarla duplica el gasto y además lo infla. En la
  corrida del 2026-09-10 las guías 1844884 y 1844885 se dejaron sin
  registrar por esto y se movieron a `Junji V2/Duplicados/` (sí se registró
  su factura, la ANWO 1936317, como `JUN2-005`). La excepción legítima es
  cuando la factura NO está disponible en la carpeta y la guía es el único
  respaldo del gasto (caso de `Documento (16).pdf`, guía ANWO 1842010).

  **Pendiente de corregir**: las 5 filas afectadas siguen en `Master`/
  `Detalle` tal cual. Corregirlas implica reescribir filas de datos ya
  creadas (excepción deliberada a la regla de oro del módulo), así que
  corresponde hacerlo vía `/Revision_de_Errores` y dejar constancia acá,
  no en un `run` normal.
