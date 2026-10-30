# Centro de Costos — proceso de errores, cuadre de impuesto y duplicados

Detalle de referencia: léelo solo al tocar esto. Las reglas vigentes están en `../CLAUDE.md`.

## Validar antes de escribir, y poder cerrarlos

Reescrito en la auditoría del 2026-09-10. Antes, la detección estaba repartida
en cuatro sitios de `main()` y no dejaba rastro: `limitaciones` y
`alertas_legibilidad` se armaban **dentro** del bucle de escritura (PASO 6),
`posibles_duplicados` también, y el cuadre de impuesto corría en el **PASO 13**
— o sea después de guardar el libro (PASO 12), de reflejarlo al sitio
compartido (12b), de regenerar el visualizador (12c) y de recalcular Análisis
Financiero (12d). Medido sobre un corpus con defectos conocidos, eso significaba
que **el 100 % de los defectos detectados se publicaba en los tres consumidores
antes de que nadie los mirara**, y que si el Excel estaba abierto la corrida
hacía `return` antes del informe y **terminaba sin reportar un solo hallazgo**.

Tres piezas nuevas:

**1. `validar_documento()` / `validar_corpus()` — PASO 5B, antes de escribir.**
Función pura que concentra todos los chequeos y devuelve hallazgos tipados con
causa, contexto, acción recomendada e impacto en pesos. Además del cuadre de
impuesto y el N° Documento ilegible (que ya existían), cubre clases que **antes
no miraba nadie**: cantidad ≤ 0, compra con neto ≤ 0 (el precedente real
"Signo de IVA / P.Unitario / Totales (AYRSA)"), nota de crédito con signo o
impuesto incoherente (`severidad_cuadre_impuesto` no las mira, así que su
impuesto no lo verificaba nadie), tipo de documento fuera del vocabulario (que
además quedaba silenciosamente exento), fecha ilegible o futura, y
proveedor/categoría en blanco. `driver.py status` corre **exactamente** la
misma función, no una versión reducida.

**Una línea de precio negativo en una factura NO es un error** — es un
descuento, y hay varios reales en `ERRORES.md`. Lo que se marca es que el
documento termine con neto ≤ 0. Verificado contra las 681 entradas reales: la
validación nueva no produce **ningún** falso positivo (los mismos 35 hallazgos
de impuesto y 34 de legibilidad que antes, más 1 tipo de documento desconocido
que antes era invisible).

**2. `Sistema/errores_detectados.json` — registro persistente con ciclo de
vida.** Es al informe de auditoría lo que `correcciones_manuales.json` es a las
celdas rojas: la memoria que convierte "lo que se imprimió esta vez" en "lo que
sigue abierto". Cada hallazgo tiene un `id` estable
(`sha1(codigo|proyecto\archivo|campo)`) y estados `abierto` → `auto_resuelto` /
`resuelto` / `descartado`. La identidad usa el `archivo` del **JSON**, no el
nombre físico: el renombrado automático cambia el nombre en disco en la primera
corrida, y usar ese nombre haría que el mismo hallazgo cambiara de identidad
entre corridas y se re-emitiera como nuevo. Está en `.gitignore`
(`**/errores_detectados*.json`): lleva montos y números de documento reales.

Un hallazgo cerrado **no se reabre** mientras el dato de origen no cambie.
`datos_extraidos.json` es entrada del pipeline y no se reescribe nunca, así que
corregir el Excel deja el valor viejo ahí; reabrirlo en cada corrida era
justamente lo que hacía que los mismos 35 descuadres se reimprimieran para
siempre. No se oculta: el informe dice cuántos son con un `[OJO]` y qué hacer.
Si el origen cambia a **otro** valor, se reabre solo.

**3. `corregir_hallazgos()` — un canal de resolución, auditado y por lote.**
Antes, el único camino auditado para corregir un dato eran las dos columnas que
el script pinta de rojo. Si el extractor dejaba la categoría en blanco, el
proveedor vacío o la fecha ilegible, **no había forma soportada de arreglarlo**:
había que editar el `.xlsx` a mano y esperar que la comparación contra el backup
lo notara — y esa comparación solo mira celdas **rojas**, así que no lo notaba
nunca. El dato quedaba corregido sin constancia de quién lo cambió.

Ahora cualquier hallazgo cuya clase declare una columna de `Master`
(`COLUMNAS_CORREGIBLES`) se resuelve por el mismo camino auditado, y **N
correcciones comparten una apertura del libro, un respaldo y un guardado**.
La puerta de entrada es "hay un hallazgo abierto que dice que esta celda está
mal", no "escríbeme cualquier celda". Ver
[Revision_de_Errores/SKILL.md](.claude/skills/Revision_de_Errores/SKILL.md) §
`hallazgos`/`resolver`/`descartar`.

**Copias exactas: se resuelven solas.** Dos entradas con el mismo emisor,
número, tipo, fecha y neto son la misma compra fotografiada dos veces —
registrarlas duplica el costo. La segunda no se escribe: se anota en
`reconciliacion_archivos.json` contra el `N° Ref.` de la original y queda
`auto_resuelto` en el registro. Es exactamente el remedio que ya se aplicó **a
mano** en el incidente del 2026-08-19 (CCON-005/CCON-011, ver
`notas_reconciliacion`), ahora automático y reversible (basta borrar la entrada
del mapeo). Si algo difiere entre las dos, es `DUPLICADO_AMBIGUO` y lo resuelve
una persona: hay que comparar las fotos.

**El neto no vive en `Master`, y por eso faltaba un canal.** Recorriendo los 80
hallazgos reales (2026-09-10) resultó que en varios documentos el error no
estaba en el impuesto sino en el **neto**, que es la suma de `cantidad ×
precio unitario` de `Detalle`. El único camino auditado escribía celdas de
`Master`, así que esos casos solo se podían arreglar editando el `.xlsx` a mano
— justo lo que `detectar_correcciones_manuales` existe para cazar.
`corregir_item_detalle()` cierra ese hueco con el mismo rastro que
`corregir_valor_manual` (azul marino + `correcciones_manuales.json` +
`ERRORES.md`). Los cuatro casos reales, por si el patrón se repite:

| Documento | Qué pasó | Efecto |
|---|---|---|
| `HPIN-017`, `JUNJ-077` | precios de Easy cargados **con IVA incluido**, así que el neto quedó igual al total | +$4.290 y +$1.734 de sobrecosto |
| `HPIN-157` | cantidad mal leída: 40 pernos en vez de 48 | −$4.792 |
| `JUNJ-072` | **montos corridos una línea**: cada descripción con el monto del ítem siguiente | −$10.473 |
| `JUNJ-009` | precio unitario mal leído; el documento dice "dieciocho mil quinientos cincuenta y un pesos" y el libro tenía 19.551 | +$1.000 |

**La evidencia de que un hallazgo se resolvió tiene que buscarse donde vive el
dato, no en una celda fija.** Al principio el cierre automático solo miraba la
celda de `Master` del hallazgo, y por eso los cuatro casos de arriba seguían
abiertos después de corregirlos. Ahora hay tres pruebas, y las dos nuevas miran
el **libro** en vez de `datos_extraidos.json`:

- `cuadre_en_el_libro()` — rehace el cuadre neto-vs-impuesto con lo que dice el
  libro. Si el documento cuadra, no hay nada que arreglar ahí.
- para `ITEM_AGRUPADO`, que no declara columna: que ya no quede ninguna fila
  "varios" de ese documento en `Detalle`.

**`IMPUESTO_ESTIMADO` queda deliberadamente fuera** de la primera: su celda de
impuesto se escribió calculando el 19 %, así que el libro cuadra **por
construcción** y cerrarlo por "ya cuadra" sería taparlo. Ese hallazgo dice
"este dato se completó con un supuesto, verifícalo", y solo lo cierra una
persona mirando el documento.

**Cómo se mide todo esto**: `Sistema/bench/` monta un Centro de Costos
desechable con un corpus anonimizado de defectos conocidos y reporta recall,
falsos positivos, tasa de errores sin resolver, resolución automática y tiempos.
Ver [bench/README.md](Sistema/bench/README.md). Si tocas el proceso de errores,
corre el benchmark antes y después — es la única forma de saber si mejoraste
algo o solo moviste texto de consola.

**El benchmark no cubre el caso real: un corpus que YA está registrado.** Se
descubrió al día siguiente (2026-09-10), la primera vez que se corrió la
revisión sobre los datos de verdad. El sandbox del benchmark arranca vacío y
escribe todos sus documentos en la corrida que mide, así que `anotar_n_ref()`
—que vive **dentro** del bucle de escritura del PASO 6— siempre disparaba. En
producción hay 728 filas en Master y 0 pendientes: `run` no escribe ninguna
fila, ningún hallazgo recibía su `N° Ref.` y `corregir_hallazgos()` los
rechazaba **todos** con "el documento todavía no tiene fila en Master". El
registro quedaba completo y a la vez inservible.

Dos reglas que salieron de ahí, y que conviene no reaprender:

- **El puente entre un hallazgo y su fila no puede ser el nombre del archivo.**
  El renombrado automático reescribe el nombre físico a
  `<N Ref>_<Proveedor>_<Fecha>`: medido, **0 de las 681** claves del JSON
  calzaban contra `Archivo origen`. `mapa_documento_a_n_ref()` usa el
  `N° Documento`, que sí sobrevive, y solo cuando identifica una única fila y
  un único documento de origen — un número repetido no identifica nada y se
  omite a propósito. Para los que ya fueron corregidos a mano (Master tiene el
  valor bueno y el JSON el viejo) el segundo puente es
  `correcciones_manuales.json`, que guarda el par `valor_anterior → N° Ref` de
  esa misma celda: el enlace exacto que se perdió, sin adivinar nada.
- **Validar la entrada implica re-reportar lo ya corregido.**
  `datos_extraidos.json` es la entrada del pipeline y no se reescribe nunca, así
  que un documento arreglado hace meses vuelve a producir el mismo hallazgo. Con
  el registro recién creado sobre un corpus con 105 correcciones aplicadas, eso
  era pedirle al operador que arreglara de nuevo lo ya arreglado: 19 de 80
  hallazgos. `cerrar_hallazgos_ya_corregidos()` los cierra con su evidencia, y
  la evidencia exigida es **por celda**, no por documento (azul marino en esa
  celda, o una entrada para ese `(N° Ref, columna)` en la bitácora). Si el dato
  de origen cambia a *otro* valor, `fusionar_hallazgos()` lo reabre igual.

Efecto medido sobre los 681 documentos reales: de **0** hallazgos resolubles a
**25**, más 19 cerrados con evidencia en vez de vueltos a preguntar. Quedan 26
sin `N° Ref.` porque su número no identifica una fila única (números repetidos
entre emisores, duplicados, peajes con `N/A`, y entradas del JSON que traen
varios números en un campo, como `"288946, 289533 y 289351"`): esos se resuelven
mirando el documento, con `corregir <N_REF>` directo.

## Cuadre de impuesto y duplicados: por qué hay severidades

Reescrito en la auditoría del 2026-09-09. Las dos verificaciones que emitían
alertas lo hacían comparando strings crudos, y el resultado era ruido que
enterraba los hallazgos reales.

**Tipo de documento — una sola fuente de verdad.** El tipo lo escribe un
agente al extraer, así que la misma cosa entra con y sin tilde: el JSON tiene
hoy 3 `Guía de Despacho` y 8 `Guia de Despacho`, 7 `Nota de Crédito` y 1
`Nota de Credito`. Se comparaba contra la tupla literal
`("Factura", "Guía de Despacho")` en **tres** lugares distintos, así que esas
8 guías quedaban fuera de toda verificación — y `calcular_iva_documento` les
habría puesto impuesto **0** de no venir con `iva` explícito. Ahora todo pasa
por `es_documento_afecto()` / `clave_tipo_documento()`. **Si agregas una
comparación por tipo de documento, usa esas funciones, nunca el literal.**

**El campo `iva` es la bolsa de TODOS los impuestos, no solo el 19 %.** En
las facturas de combustible el precio pagado lleva IVA más impuesto
específico (IEC) y FEPP, y el campo los agrupa a propósito para que
`Neto + iva` sea el total realmente pagado (las notas de esos documentos lo
dicen). Asumir 19 % puro producía 100 alertas de las que **73 eran
documentos correctos**, y dejaba 55 celdas de IVA pintadas de rojo que nadie
iba a corregir nunca. `severidad_cuadre_impuesto()` clasifica en:

| severidad | qué significa | acción |
|---|---|---|
| `error` | el impuesto es **menor** al IVA legal en una categoría **sin** impuesto específico | hay algo que corregir, sí o sí |
| `revisar` | excede el 19 % sin impuesto específico conocido, **o** queda por debajo en una categoría que sí lo tiene | mirar el documento |
| `estimado` | documento afecto **sin** `iva`: se calcula 19 %, que en combustible queda corto | verificar el total pagado |

**El perdón por categoría vale para los dos lados del 19 %, no solo para el
exceso** (corregido el 2026-09-10, con la factura en la mano). La regla daba
`error` a *cualquier* impuesto bajo el 19 %, incluso en combustible, sobre la
premisa de que eso era "imposible en un documento afecto". JUNJ-238 (Copec,
factura 94279) lo desmiente: neto 8.142, IVA 1.547, **IEV Diesel −3.463**,
IEF Diesel 774, total pagado 7.000 — el impuesto combinado es −1.142. El
FEPP/IEV es un mecanismo de estabilización y **puede devolver plata**, así que
el total combinado cae legítimamente bajo el 19 %. Eran **10 de los 17**
descuadres `error` sobre los datos reales: facturas de combustible bien
registradas que mandaban al operador a corregir un dato correcto. Ahora salen
como `IMPUESTO_MENOR_ESPECIFICO` / `revisar` — siguen reportándose, con la
severidad que la evidencia soporta. Si el documento declara
`otros_impuestos`, el cuadre vuelve a ser exacto y un déficit contra esa
declaración vuelve a ser `error`, también en combustible.

El exceso ya explicado por la categoría (`CATEGORIAS_CON_IMPUESTO_ESPECIFICO`
= `Combustible`) no se reporta: es el comportamiento esperado. Solo `error`
pinta la celda de rojo. `migrar_color_cuadre_impuesto()` repinta el libro ya
escrito según esta regla (es idempotente en los dos sentidos).

**La forma preferida de registrar un impuesto adicional es declararlo.** El
campo opcional `otros_impuestos` dice cuánto del impuesto **no** es IVA. Con
él, el cuadre deja de ser una heurística por categoría y pasa a ser una
igualdad verificable: `iva == round(neto × tasa) + otros_impuestos`. Sirve
para cualquier rubro, no solo combustible. Las 660 entradas existentes no lo
declaran y siguen validándose por categoría, así que agregarlo es
incremental: cada documento nuevo que lo traiga se valida exacto.

**`N/A` y `S/N` no son números de documento.** 172 de las 660 entradas del
JSON son peajes con `n_documento = "N/A"` y 34 son `S/N (archivo)`. El
detector de duplicados comparaba el string crudo, así que **cada peaje era
"duplicado" del peaje anterior**: la corrida del 2026-09-09 emitió 48 avisos
y 47 eran peajes distintos. Ahora `es_n_documento_real()` filtra los
marcadores antes de comparar. Un duplicado de verdad exige además el mismo
emisor: un N° Documento es único **por emisor**, no globalmente.
