---
name: Revision_de_Errores
description: Recorrido guiado, uno por uno, de los hallazgos abiertos, las celdas rojas y los ítems agrupados del Centro de Costos: muestra la foto, pide el valor correcto y lo aplica con rastro. Usar SOLO si el usuario escribe "/Revision_de_Errores"; si pide con palabras revisar errores, celdas rojas o ítems agrupados, confirma primero.
---

# Revisión de errores: Centro de Costos

El agente recorre lo pendiente, muestra el documento y pregunta el valor **en la conversación**, sin que el
usuario edite el Excel. (`/Registro_Centro_de_Costos` hace lo inverso: detecta lo que ya se corrigió a mano.)
Son fotos y datos reales. Las rutas son relativas a `Centro de Costos/`; `driver.py` es
`.claude/skills/Revision_de_Errores/driver.py`, corrido con `py -3.14`.

| Tipo | Listar (solo lee) | Aplicar |
|---|---|---|
| **Hallazgo del registro** (cualquier clase; camino preferido, incluye las celdas rojas) | `hallazgos [error]` | `resolver <ID> "<VALOR>"` / `descartar <ID> "<motivo>"` |
| Celda roja de `Master` (solo si el usuario pide «las celdas rojas») | `errores` | `corregir <N_REF> <CAMPO> "<VALOR>"` |
| Ítem agrupado de `Detalle` | `agrupados` | `desglosar <N_REF> '<ITEMS_JSON>' [--fila N]` |
| Neto mal cargado (cantidad o precio de un ítem) | `items <N_REF>` | `corregir-item <N_REF> <FILA> [--cantidad N] [--precio N] [--nota "<texto>"]` |

## Procedimiento

1. **`driver.py hallazgos`**: pone el registro al día, sin `run` previo (lee el Excel sin guardarlo; solo escribe
   `Sistema/errores_detectados.json`). Recórrelo de arriba abajo: primero `error`, luego `revisar` y `estimado`, y
   en cada una por impacto en pesos. Muestra para cada uno `<ID>`, `N° Ref.`, causa, acción y desde cuándo está abierto.
2. **Uno a la vez**: di el `N° Ref.`, el campo y por qué está mal (si es impuesto, calcula el esperado) y **muestra
   la foto** con la herramienta de lectura. `.heic` no se previsualiza: pide que lo abran. Con `[WARN] No se encontró
   la foto`, dilo y pide el valor igual.
3. **Pregunta el valor** con texto libre (no uses AskUserQuestion). Si no lo sabe, sigue con el siguiente, salvo lo
   que indica «Cuando el dato no se puede leer».
4. **Aplica**, juntando varios en una llamada: `driver.py resolver a1b2c3 "Ferreteria" d4e5f6 "03-08-2026"` usa una
   sola apertura, un respaldo y un guardado (`--nota "<texto>"` vale para el último par y queda como comentario de
   Excel). Cada corrección deja azul marino (`1F3864`), propaga a `Detalle`, anota en
   `Sistema/correcciones_manuales.json` y en [ERRORES.md](../Registro_Centro_de_Costos/ERRORES.md) y cierra el hallazgo.
5. **Ítems agrupados**: `driver.py agrupados`; muestra la foto y pregunta por cada línea real nombre, descripción,
   categoría, cantidad y precio sin IVA. `<ITEMS_JSON>` sigue el esquema de ítem de `datos_extraidos.json`:
   ```
   driver.py desglosar CCON-004 "[{\"nombre_item\": \"Soldadura plata\", \"descripcion\": \"Al 6% + fundente\", \"categoria_item\": \"Materiales\", \"cantidad\": 1, \"p_unitario_sin_iva\": 55206}]"
   ```
6. **`driver.py reflejar`: siempre al terminar, sin excepción.** `corregir` y `desglosar` no copian el Excel al sitio
   compartido, a diferencia de `run`. Con `[WARN]` (destino bloqueado), avisa y sugiere reintentar más tarde.
7. **Resume**: cuánto se corrigió, cuánto se desglosó y qué sigue pendiente.

## Qué cierra cada comando

- **`descartar`**: mirando el documento, el dato está bien. **Exige motivo** y deja constancia. Nunca lo uses para
  acortar la lista.
- **`resolver`** solo actúa si hay un hallazgo ABIERTO sobre esa celda. Rechaza sin escribir un ID inexistente o
  cerrado, un documento sin fila en `Master` y una clase que no se arregla con una celda (falta la entrada del JSON,
  desglosar, borrar un duplicado); el mensaje dice qué corresponde.
- **Un hallazgo cerrado no reaparece** mientras el origen no cambie. `datos_extraidos.json` no se reescribe, así que el
  informe avisa con `[OJO] N hallazgo(s) cerrado(s) siguen con el dato viejo`. Si cambia a otro valor, se reabre.
  Lo ya corregido (azul marino o en `correcciones_manuales.json`) nace cerrado con esa evidencia.
- **Hallazgo sin `N° Ref.`**: su N° Documento no identifica una única fila (repetidos entre emisores, duplicados,
  `N/A`, varios números en un campo). Asignar una candidata escribiría en el documento equivocado: mira el documento y
  usa `corregir <N_REF>` directo, o arregla primero el N° Documento.

## Celdas rojas (`acc.COLUMNAS_REVISABLES`)

- **N° Documento** (columna E) ilegible: `"S/N (<archivo o voucher>)"`.
- **IVA 19 % (CLP)** (columna L) que no cuadra con el 19 % del Neto (±1 CLP) en Facturas y Guías. **En combustible, el
  valor correcto es la suma de todos los impuestos** (IVA + IEF + IEV/FEPP, que puede ser negativo); deja el desglose:
  `driver.py corregir CVAL-018 IVA 8799 --nota "IVA: $7188 / IEF: $4111 / IEV/FEPP: $-2500"`.

`<CAMPO>` acepta el número de columna (5 o 12) o parte del nombre. `corregir` solo actúa si la celda está en rojo; si
no, no hace nada. El IVA se convierte a número; un valor no numérico queda como texto. Lo de la tabla «Posible error»
del registro (imprecisiones que no son una celda) se resuelve caso a caso, no aquí.

## Neto mal cargado

El neto **no vive en `Master`**: es la suma de cantidad × precio de `Detalle`. Casos reales: precios con IVA incluido
(`HPIN-017`, `JUNJ-077`), cantidad mal leída (`HPIN-157`), montos corridos una línea (`JUNJ-072`). `items` muestra el
neto, el impuesto declarado y cuánto sería el 19 %, que dice de qué lado está el problema. `corregir-item` recalcula la
fila y el «Total con IVA» de **todo** el documento. **No toca el impuesto de `Master`**: si era correcto, el cuadre da
exacto y el hallazgo se cierra solo; si también está mal, va por `resolver`.

## Ítems agrupados (`acc.PATRON_ITEM_AGRUPADO`)

Filas de `Detalle` cuyo nombre contiene «varios» (precedente `CCON-004`): las líneas ilegibles de una factura se agrupan
por el saldo. Se detectan solo por el nombre: si el usuario señala uno nombrado de otra forma, avísale y ofrécelo igual.
`desglosar` reemplaza la fila por una por ítem y rehace «Resumen Ítems» y el pie. Con más de un ítem agrupado pide
`--fila` y no toca nada hasta que se le diga cuál; con ninguno, no hace nada.

## Cuidados

- **Excel abierto**: `[ERROR] El archivo esta abierto en Excel`, sin corromper. Pide cerrarlo y reintenta.
- **No hay deshacer** salvo el respaldo de `Excel/Respaldos/`: una celda azul ya no se corrige con `corregir`, ni un
  ítem desglosado con `desglosar`. Restaura desde el respaldo.
- Implementación en `Sistema/auditor_centro_costos.py` (`validar_documento`, `sincronizar_registro_errores`,
  `mapa_documento_a_n_ref`, `corregir_hallazgos`, `descartar_hallazgo`, `listar_celdas_rojas`, `corregir_valor_manual`,
  `listar_items_agrupados`, `desglosar_item_agrupado`, `reflejar_a_sitio_comunicacion`); pruebas en `Sistema/tests/`
  (`test_validacion_documentos`, `test_enlace_hallazgos`, `test_resolucion_hallazgos`, `test_pipeline_errores`,
  `test_revision_errores`).

## Cuando el dato no se puede leer

Pedido del usuario: **no se cierra con un marcador ni se deja «para más adelante»**. Tras agotar lo automático:

1. Manda con `SendUserFile` el PDF o la foto original **y** un recorte ampliado que marque el dato. Si varios `N° Ref.`
   comparten la foto, dilo y mándala una sola vez.
2. Di qué se leyó y qué falta (ej. «11 de 12 dígitos: `#1477268_7948`, falta el octavo»).
3. Pide el valor y aplícalo con `corregir` o `resolver`.

Antes agota, en este orden: la **imagen embebida a resolución nativa** (`fitz` → `extract_image`; renderizar a 150 dpi
pierde detalle), **separar canales** RGB (un pliegue puede desaparecer en uno), **umbral y resta de fondo** (gaussiano
grande, para despegar una marca de agua) y buscar el comprobante en **otra foto** del módulo. No se recupera: tinta
térmica perdida en una banda, papel doblado sobre el número, texto de ~10 px bajo una marca de agua.
