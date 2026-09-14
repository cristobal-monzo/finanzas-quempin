---
name: Revision_de_Errores
description: Usar cuando el usuario escribe "/Revision_de_Errores" explícitamente. Si en cambio pide en lenguaje natural (sin el "/") revisar errores, corregir datos ilegibles, resolver celdas rojas, desglosar ítems agrupados/no identificados, o repasar el registro de correcciones manuales del Centro de Costos, pedir confirmación antes de invocarlo (ver CLAUDE.md raíz § Invocación de skills) -- nunca activarlo automático. Recorrido guiado, uno por uno, de (a) los hallazgos abiertos del registro de errores (cualquier clase: impuesto, fecha, proveedor, categoría, tipo de documento, duplicados), (b) las celdas de "Centro de Costos.xlsx" marcadas en rojo (requieren revisión) y (c) las filas de Detalle que agrupan en 1 solo ítem una parte de una compra que no se pudo identificar línea por línea (ej. "Materiales varios") -- muestra la foto del documento asociado, pide al usuario el valor correcto o el desglose correcto, lo aplica en el Excel con fuente azul marino oscuro, actualiza el registro de correcciones, y refleja el resultado en ambas copias del libro.
---

# Revisión de errores: Centro de Costos

Complementa a [Registro_Centro_de_Costos](../Registro_Centro_de_Costos/SKILL.md):
esa skill detecta correcciones que el usuario **ya hizo a mano** directo en
el `.xlsx` (comparando contra el backup anterior) y requiere un paso de
confirmación aparte (`driver.py confirmar`). Esta skill invierte el orden:
el **agente** recorre las celdas rojas (y los ítems agrupados, ver más abajo),
muestra el documento, y le pregunta al usuario el valor correcto **en la
conversación** -- sin que el usuario tenga que abrir Excel y editar la celda
él mismo. El resultado final es el mismo (celda/fila azul marino oscuro,
propagada a Detalle/Master, registrada como "Aplicado"), solo cambia cómo se
obtiene el valor.

Tres tipos de hallazgo, con su comando de lectura y el de escritura -- ver
"Qué cuenta como..." de cada uno más abajo:

| Tipo | Listar (solo lectura) | Aplicar |
|---|---|---|
| **Hallazgo del registro** (cualquier clase) | `hallazgos` | `resolver <ID> "<VALOR>"` / `descartar <ID> "<motivo>"` |
| Celda roja de Master | `errores` | `corregir <N_REF> <CAMPO> <VALOR>` |
| Ítem agrupado de Detalle | `agrupados` | `desglosar <N_REF> '<ITEMS_JSON>' [--fila N]` |
| **Neto mal cargado** (cantidad/precio de un ítem) | `items <N_REF>` | `corregir-item <N_REF> <FILA> --precio N` |

**`hallazgos`/`resolver` es el camino preferido desde 2026-09-10** y cubre a
`errores`/`corregir` (que siguen funcionando igual, para las dos columnas
rojas). La diferencia es el alcance: `errores` solo ve las dos columnas que
el script pinta de rojo (N° Documento e impuesto), mientras que `hallazgos`
lee el **registro persistente** que `run` deja en
`Sistema/errores_detectados.json` y que incluye todo lo que la validación
temprana detecta: fechas ilegibles o futuras, proveedor o categoría en
blanco, tipos de documento fuera del vocabulario, notas de crédito con signo
o impuesto incoherente, compras con neto ≤ 0, cantidades ≤ 0, duplicados y
documentos sin entrada en el JSON. Antes ninguno de esos tenía un camino de
corrección que dejara rastro: había que editar el `.xlsx` a mano y la
comparación contra el backup no los detectaba (solo mira celdas rojas).

### `hallazgos` / `resolver` / `descartar`

```
py -3.14 ".claude/skills/Revision_de_Errores/driver.py" hallazgos            # todos
py -3.14 ".claude/skills/Revision_de_Errores/driver.py" hallazgos error      # solo los seguros
py -3.14 ".claude/skills/Revision_de_Errores/driver.py" resolver <ID> "<VALOR>"
py -3.14 ".claude/skills/Revision_de_Errores/driver.py" descartar <ID> "<motivo>"
```

- **`hallazgos`** imprime, priorizado por severidad y por impacto en pesos:
  el `<ID>` estable con el que se resuelve, el `N° Ref.`, el mensaje con
  causa y contexto, la acción recomendada, y desde cuándo está abierto
  (`visto 4x desde 2026-08-30`). Severidades: `error` (el dato de hoy no
  puede ser bueno), `revisar` (hay que mirar el documento), `estimado` (el
  dato se completó con un supuesto).
- **`resolver` acepta varios pares `<ID> "<VALOR>"` en una sola llamada** y
  los aplica con **una** apertura del libro, **un** respaldo y **un**
  guardado. Resolver de a uno cuesta eso por cada celda (openpyxl tarda
  ~0,3-0,8 s por apertura de este libro), así que si vas a cerrar varios,
  júntalos:
  ```
  py -3.14 driver.py resolver a1b2c3 "Ferreteria" d4e5f6 "03-08-2026" 7g8h9i "Proveedor Real SpA"
  ```
  Hace lo mismo que `corregir` para cada celda (respaldo → valor → fuente
  azul marino → propagación a `Detalle` → entrada en
  `correcciones_manuales.json` + `ERRORES.md`) y además cierra el hallazgo
  en el registro con el detalle del cambio. Acepta `--nota "<texto>"` para
  el último par, que queda como comentario de Excel.
- **`descartar`** cierra un hallazgo porque, mirando el documento, el dato
  está bien. **Exige un motivo** y lo guarda: descartar deja constancia, no
  borra. Nunca lo uses para acortar la lista.
- `resolver` **rechaza** (sin escribir nada) un ID que no exista, uno ya
  cerrado, uno cuyo documento todavía no tenga fila en `Master`, y uno cuya
  clase no se arregle escribiendo una celda (falta la entrada del JSON, hay
  que desglosar ítems, hay que borrar un documento duplicado). El mensaje de
  rechazo dice cuál es la acción que sí corresponde.
- Un hallazgo resuelto **no reaparece** en las corridas siguientes mientras
  el dato de origen no cambie. `datos_extraidos.json` es entrada del
  pipeline y no se reescribe, así que el valor viejo sigue ahí: el informe
  lo dice con un `[OJO] N hallazgo(s) cerrado(s) siguen con el dato viejo en
  datos_extraidos.json`, para que se corrija también ahí si el documento se
  va a re-extraer. Si el dato de origen cambia a **otro** valor, el hallazgo
  se reabre solo.

### `items` / `corregir-item` — cuando el error está en el NETO, no en el impuesto

```
py -3.14 ".claude/skills/Revision_de_Errores/driver.py" items <N_REF>
py -3.14 ".claude/skills/Revision_de_Errores/driver.py" corregir-item <N_REF> <FILA> [--cantidad N] [--precio N] [--nota "<texto>"]
```

El neto de un documento **no vive en `Master`**: es la suma de `cantidad ×
precio unitario` de sus filas de `Detalle`. Hasta la revisión del 2026-09-10
el único camino auditado escribía celdas de `Master`, así que un documento con
el neto mal cargado solo se podía arreglar editando el `.xlsx` a mano — justo
lo que `detectar_correcciones_manuales` existe para cazar. Casos reales que
cerró este comando:

- **el bruto cargado como neto** (`HPIN-017`, `JUNJ-077`): los precios traían
  el IVA incluido, así que `Neto` quedaba igual al total y el impuesto no
  cuadraba con su 19 %;
- **una cantidad mal leída** (`HPIN-157`: 40 pernos en vez de 48 → faltaban
  $4.792);
- **los montos corridos una línea** (`JUNJ-072`: cada descripción llevaba el
  monto del ítem siguiente → faltaban $10.473).

`items` muestra el neto, el impuesto declarado y **cuánto sería el 19 %**, que
es lo que dice de qué lado está el problema. `corregir-item` recalcula el
"Total sin IVA" de la fila y el "Total con IVA" de **todas** las filas del
documento (la tasa real es impuesto de `Master` / neto, así que cambiar un
precio la mueve para todo el documento), deja la fila en azul marino y registra
la corrección en `correcciones_manuales.json` y `ERRORES.md`.

**No toca la columna de impuesto de `Master`.** Si el impuesto declarado era el
correcto, arreglar el neto hace que el cuadre pase a dar exacto y el hallazgo
se cierra solo. Si además hay que corregir el impuesto (combustible con
específico), eso va por `resolver`.

**Siempre, al terminar el recorrido (haya o no correcciones aplicadas en la
sesión), correr `python driver.py reflejar`** -- copia
`Excel/Centro de Costos.xlsx` encima de `Sitio de comunicación - Centro de
Costos 1/Centro de Costos.xlsx`. `corregir` y `desglosar` solo tocan el
Excel local (no pasan por `main()`/`run`, que es el único lugar que hacía
este reflejo hasta ahora), así que sin este paso la copia compartida que ven
los colegas queda desactualizada. Es el mismo paso que hace `run` en su
PASO 12b (`reflejar_a_sitio_comunicacion()` en `auditor_centro_costos.py`,
factorizado para reutilizarse acá), idempotente y seguro de repetir.

Todas las rutas son relativas a la raíz del módulo (`Centro de Costos/`), no
a esta carpeta de skill. El driver vive en
`.claude/skills/Revision_de_Errores/driver.py`.

**Datos financieros reales** -- igual que el resto del módulo, no hay nada
que fotografiar de la herramienta en sí (es un script), pero sí se muestran
fotos reales de facturas/boletas de la empresa durante el recorrido.

## Qué cuenta como "error" en esta skill

Únicamente las celdas de `Master` que el script pinta de rojo hoy
(`acc.COLUMNAS_REVISABLES`, ver `auditor_centro_costos.py`):

- **N° Documento** (columna E) ilegible o no leído -- queda como
  `"S/N (<archivo o voucher>)"`.
- **IVA 19% (CLP)** (columna L) que no cuadra con el 19% del Neto (tolerancia
  ±1 CLP) para Facturas/Guías de Despacho. **Compras de combustible**: el
  valor correcto para esta columna es la suma de TODOS los impuestos del
  documento (IVA + IEF + IEV/FEPP, este último puede ser negativo), no solo
  el 19% -- ver regla y ejemplo en `MEMORY.md` de `Registro_Centro_de_Costos`
  § Reglas de negocio. Como el valor combinado no coincide con 19% del Neto,
  usar `corregir ... --nota "IVA: $X / IEF: $Y / IEV/FEPP: $Z"` para dejar el
  desglose documentado (queda como comentario de Excel en la celda).

**No** entran acá los hallazgos de la tabla "Posible error" que se arma tras
cada `run` (legibilidad general, posibles duplicados, imprecisiones de dato
que el agente nota pero el script no marca) -- esos no son una sola celda con
un valor a reemplazar, se resuelven caso a caso siguiendo el Paso 3 de
`Registro_Centro_de_Costos/SKILL.md`, no con este recorrido.

## Qué cuenta como "ítem agrupado" en esta skill

Filas de `Detalle` cuyo **Nombre Ítem** contiene la palabra "varios" (ej.
"Materiales varios", "Insumos varios" -- `acc.PATRON_ITEM_AGRUPADO`,
insensible a mayúsculas). Es la convención que ya usa el módulo desde el
precedente `CCON-004` (ver `MEMORY.md`/`ERRORES.md` de
`Registro_Centro_de_Costos`): cuando una parte de una factura/boleta es
físicamente ilegible (timbre, doblez, foto cortada), las líneas que sí se
leen se registran cada una por separado y **solo** las ilegibles se agrupan
en 1 ítem aparte por el saldo entre el Neto impreso y la suma de las líneas
legibles -- nunca se agrupa el documento completo. Ese ítem-saldo es lo que
esta skill puede desglosar, si en algún momento se consigue leer el detalle
real (otra foto, el documento físico, etc.).

No hay ninguna celda pintada de un color especial para este caso (a
diferencia de las celdas rojas de Master) -- se detecta por el nombre del
ítem, no por formato. Si el usuario nombra un ítem agrupado de otra forma
que no incluya "varios", esta skill no lo va a encontrar solo con
`agrupados`; avisar al usuario y ofrecer desglosarlo igual si él lo señala
en la conversación.

## Procedimiento

**Paso 0 -- listar los hallazgos abiertos (empieza por acá):**

```
py -3.14 ".claude/skills/Revision_de_Errores/driver.py" hallazgos
```

Pone el registro al día y muestra la vista completa y priorizada; no toca el
Excel ni ningún dato del negocio. Recórrela de arriba hacia abajo (primero
los `error`, dentro de cada severidad primero los de mayor impacto en pesos),
mostrando la foto del documento igual que en el Paso 2, y ciérralos con
`resolver`/`descartar`. **Junta varios `<ID> "<VALOR>"` en una sola llamada a
`resolver`** en vez de una llamada por celda.

Los Pasos 1-3 de abajo son el recorrido histórico por celdas rojas: siguen
siendo válidos y llegan al mismo resultado, pero solo cubren las dos columnas
que el script pinta de rojo. Úsalos si el usuario pide explícitamente "las
celdas rojas"; si no, el Paso 0 ya las incluye.

**Paso 1 -- listar los errores (solo lectura):**

```
python ".claude/skills/Revision_de_Errores/driver.py" errores
```

Imprime, por cada celda roja: `N° Ref.`, proyecto, campo, valor actual, y la
ruta a la foto del documento original (resuelta con el mismo mecanismo que
usa el renombrado automático -- prueba "Archivo origen" y si no existe en
disco cae a `reconciliacion_archivos.json`). Si dice "No hay errores
pendientes de revisión", termina acá y avísale al usuario.

**Paso 2 -- recorrer las celdas UNA A LA VEZ** (no todas de golpe: el usuario
necesita ver cada documento antes de decidir el valor correcto):

Para cada celda de la lista del Paso 1:

1. **Mostrar el error**: `N° Ref.`, proyecto, campo, y por qué está en rojo
   (N° Documento ilegible / IVA no cuadra con el 19% del Neto -- calcula el
   valor esperado si es IVA, ayuda al usuario a decidir).
2. **Mostrar la foto**: usar la herramienta de lectura de archivos sobre la
   ruta que imprimió `errores` para que la imagen se vea en la conversación.
   - Si la ruta es `.heic` (no debería pasar para documentos ya registrados,
     el renombrado automático los convierte a `.jpg`, pero puede pasar si
     el archivo aún no pasó por un `run`), avisar que no se puede previsualizar
     inline y pedirle al usuario que lo abra manualmente para confirmar el
     valor.
   - Si `errores` marcó `[WARN] No se encontró la foto en disco`, decirlo tal
     cual y pedir el valor correcto igual (sin foto de respaldo).
3. **Preguntar el valor correcto** directamente en la conversación (texto
   libre, no es una decisión de diseño así que no uses AskUserQuestion).
   Si el usuario dice que no sabe o quiere dejarlo pendiente, saltar esa
   celda y seguir con la siguiente -- no hay que resolver todas en la misma
   sesión.
4. **Aplicar la corrección**:
   ```
   python ".claude/skills/Revision_de_Errores/driver.py" corregir <N_REF> <CAMPO> "<VALOR>"
   ```
   `<CAMPO>` acepta el número de columna (5 o 12) o un fragmento del nombre
   ("N° Documento", "documento", "IVA", ...). Ejemplos:
   ```
   python driver.py corregir UMAG-014 "N° Documento" 12345
   python driver.py corregir CFLI-002 IVA 190
   ```
   Para compras de combustible (IVA = IVA + IEF + IEV/FEPP, ver arriba),
   agregar el desglose con `--nota`:
   ```
   python driver.py corregir CVAL-018 IVA 8799 --nota "IVA: $7188 / IEF: $4111 / IEV/FEPP: $-2500"
   ```
   Esto hace, en un solo paso: backup de `Centro de Costos.xlsx` →
   escribe el valor nuevo en `Master` → recolorea esa celda a azul marino
   oscuro (`1F3864`) → si el campo es N° Documento, propaga el mismo valor a
   las filas de `Detalle` con ese `N° Ref.` (también en azul marino) → marca
   la corrección como "Aplicado" en `Sistema/correcciones_manuales.json` y en
   la tabla de [ERRORES.md](../Registro_Centro_de_Costos/ERRORES.md).
5. **Confirmar al usuario** que se aplicó (el driver ya imprime
   `[OK] <N_REF> / <campo>: '<anterior>' -> '<nuevo>' (azul marino...)`) y
   seguir con la siguiente celda de la lista.

**Estos cambios se ven reflejados en todo el libro sin pasos extra**: la
hoja de proyecto correspondiente es 100% fórmulas hacia `Master` (se
recalcula sola en el próximo `run`, o ya se ve actualizada si solo abres el
archivo porque lee `Master` en vivo), y `Detalle` recibe la propagación
automática cuando el campo se repite ahí.

**Paso 3 -- si `Centro de Costos.xlsx` está abierto en Excel**, `corregir`
falla con un `[ERROR] El archivo esta abierto en Excel` controlado (no
corrompe el archivo) -- pedirle al usuario que lo cierre y reintentar esa
celda.

**Paso 4 -- listar los ítems agrupados (solo lectura):**

```
python ".claude/skills/Revision_de_Errores/driver.py" agrupados
```

Imprime, por cada fila agrupada de `Detalle`: `N° Ref.`, proyecto, nombre del
ítem agrupado, monto, la descripción completa (normalmente explica qué
líneas quedaron dentro y por qué no se pudieron leer), y la foto del
documento. Si dice "No hay ítems agrupados pendientes de desglosar", saltar
al Paso 6.

**Paso 5 -- recorrer los ítems agrupados UNA A LA VEZ** (mismo criterio que
el Paso 2: el usuario necesita ver el documento antes de dar el desglose):

Para cada ítem agrupado de la lista del Paso 4:

1. **Mostrar el hallazgo**: `N° Ref.`, proyecto, nombre y descripción del
   ítem agrupado, monto total que representa.
2. **Mostrar la foto** (mismo mecanismo que el Paso 2 -- si es `.heic` o no
   se encontró en disco, avisar igual que ahí).
3. **Preguntar el desglose correcto** directamente en la conversación: por
   cada línea real que el usuario identifique, pedir nombre del ítem,
   descripción, categoría, cantidad y precio unitario sin IVA. Si el usuario
   no puede leer el documento tampoco (mismo motivo por el que quedó
   agrupado -- timbre, doblez, foto cortada), dejarlo pendiente y seguir con
   el siguiente; no hay que resolver todos en la misma sesión.
4. **Aplicar el desglose**:
   ```
   python ".claude/skills/Revision_de_Errores/driver.py" desglosar <N_REF> '<ITEMS_JSON>'
   ```
   `<ITEMS_JSON>` es una lista JSON de objetos, mismo esquema que un ítem de
   `datos_extraidos.json`: `nombre_item`, `descripcion`, `categoria_item`,
   `cantidad`, `p_unitario_sin_iva`. Ejemplo:
   ```
   python driver.py desglosar CCON-004 "[{\"nombre_item\": \"Cañería cobre\", \"descripcion\": \"1 1/4 y 1 1/2 pulg\", \"categoria_item\": \"Materiales\", \"cantidad\": 2, \"p_unitario_sin_iva\": 30000}, {\"nombre_item\": \"Soldadura plata\", \"descripcion\": \"Soldadura al 6% + fundente\", \"categoria_item\": \"Materiales\", \"cantidad\": 1, \"p_unitario_sin_iva\": 55206}]"
   ```
   Esto hace, en un solo paso: backup → reemplaza la fila agrupada de
   `Detalle` por una fila nueva por cada ítem (azul marino, heredando el
   relleno de color del proyecto) → recalcula "Total sin IVA"/"Total con
   IVA" de cada fila nueva con la tasa real del documento → reconstruye
   "Resumen Ítems" en `Master` → regenera el pie de `Detalle` → marca el
   cambio como "Aplicado" en `Sistema/correcciones_manuales.json` y en la
   tabla de [ERRORES.md](../Registro_Centro_de_Costos/ERRORES.md).
5. **Confirmar al usuario** que se aplicó (el driver imprime
   `[OK] <N_REF> / Ítems agrupados: '<anterior>' -> N ítem(s) (...)`) y
   seguir con el siguiente ítem agrupado de la lista.

**Paso 6 -- reflejar en Sitio de comunicación (SIEMPRE, al terminar):**

```
python ".claude/skills/Revision_de_Errores/driver.py" reflejar
```

Correr esto al final de la sesión sin excepción, haya o no correcciones/
desgloses aplicados -- copia el Excel local encima de la copia en `Sitio de
comunicación - Centro de Costos 1/`. Si el destino está bloqueado (alguien
lo tiene abierto), el driver imprime un `[WARN]` pero no falla; avisar al
usuario y sugerirle reintentar `reflejar` más tarde.

**Paso 7 -- al terminar todo el recorrido** (se acabaron las celdas rojas y
los ítems agrupados, o el usuario quiere parar), resumir cuántas celdas se
corrigieron, cuántos ítems se desglosaron, y cuántos quedaron pendientes
(los que el usuario dijo que no sabía) -- esos siguen igual, aparecerán de
nuevo la próxima vez que se corra `errores`/`agrupados`.

## Gotchas

- **`corregir` solo toca la celda si está en rojo** -- si el `N_REF`/campo ya
  no está en rojo (alguien ya lo corrigió, o el N° Ref no existe), no hace
  nada y no rompe nada; revisar el mensaje de consola.
- **`desglosar` pide `--fila` si el documento tiene más de un ítem agrupado**
  (pasa cuando una foto trae dos boletas, como `FCH1-031`): lista las opciones
  y no toca nada hasta que se le diga cuál. Antes ese caso abortaba sin
  alternativa. Si encuentra 0 filas agrupadas -- si no encuentra ninguna (ya se desglosó, o el N° Ref no
  existe) o encuentra más de una (un documento con 2+ ítems agrupados, no
  soportado hoy), no hace nada; revisar el mensaje de consola y resolver a
  mano si hace falta.
- **No hay "deshacer" automático** más allá del backup que crean `corregir`/
  `desglosar` antes de escribir (`Excel/Respaldos/`) -- si el usuario se
  equivoca de valor, corregir de nuevo sobre la misma celda YA NO funciona
  porque quedó en azul marino (ya no está roja), y `desglosar` de nuevo
  tampoco porque el nombre del ítem ya no tiene "varios"; restaurar desde el
  backup más reciente si hace falta deshacer.
- **El valor de IVA se pasa como número** -- el driver intenta convertirlo a
  `int`/`float` automáticamente cuando el campo es IVA; si el usuario da un
  valor no numérico para esa columna, se guarda como string tal cual (Excel
  lo mostrará como texto, revisar a mano si pasa).
- **`reflejar` no se ejecuta solo** -- a diferencia de `run` (que lo hace al
  final de cada corrida, PASO 12b), `corregir`/`desglosar` NUNCA tocan la
  copia de Sitio de comunicación por sí mismos; es un paso aparte (Paso 6)
  que hay que correr siempre al terminar.
- **`resolver` no puede escribir una celda cualquiera**: solo actúa si hay un
  hallazgo ABIERTO en el registro que diga que esa celda está mal. Es a
  propósito -- la puerta de entrada es el hallazgo, no la celda.
- **`hallazgos` pone el registro al día por sí solo**, no hace falta un `run`
  previo. Sobre un corpus ya registrado `run` escribe 0 filas, así que
  exigirlo solo para poder mirar la lista significaba reescribir el libro, el
  sitio compartido, el visualizador y Análisis Financiero sin cambiar un solo
  dato. `hallazgos` lee el Excel pero no lo guarda; lo único que escribe es
  `Sistema/errores_detectados.json`.
- **Un hallazgo sin `N° Ref.` no se puede resolver por celda**, y eso pasa
  cuando su `N° Documento` no identifica una única fila de Master: números
  repetidos entre dos emisores, duplicados, los marcadores `N/A` de los
  peajes, o entradas del JSON que traen varios números en el mismo campo
  (`"288946, 289533 y 289351"`). El listado lo dice caso por caso. No es un
  error: adjudicar cualquiera de las filas candidatas escribiría la
  corrección en el documento equivocado. Se resuelven mirando el documento y
  usando `corregir <N_REF>` directo, o arreglando el `N° Documento` primero.
- **Lo que ya corregiste a mano no se vuelve a pedir.** La validación corre
  sobre `datos_extraidos.json`, que es la entrada del pipeline y nunca se
  reescribe, así que un documento arreglado hace meses seguía produciendo el
  mismo hallazgo. Ahora, si esa celda de Master está en azul marino o figura
  en `correcciones_manuales.json`, el hallazgo nace cerrado con esa evidencia
  escrita. Si el dato de origen cambia a **otro** valor, se reabre igual.
- Implementación del recorrido por registro: `validar_documento`,
  `validar_corpus`, `fusionar_hallazgos`, `sincronizar_registro_errores`,
  `mapa_documento_a_n_ref`, `cerrar_hallazgos_ya_corregidos`,
  `corregir_hallazgos`, `descartar_hallazgo` en
  `Sistema/auditor_centro_costos.py`; tests en `test_enlace_hallazgos.py`,
  `Sistema/tests/test_validacion_documentos.py`,
  `test_resolucion_hallazgos.py` y `test_pipeline_errores.py`.
- Implementación del recorrido por celdas rojas: `listar_celdas_rojas`, `corregir_valor_manual`,
  `listar_items_agrupados`, `desglosar_item_agrupado` y
  `reflejar_a_sitio_comunicacion` en `Sistema/auditor_centro_costos.py`;
  tests en `Sistema/tests/test_revision_errores.py`.

## Cuando el dato no se puede leer: abrir el documento y pedirlo, no dejarlo pendiente

**Pedido explícito del usuario (2026-09-14)**, aplicable a todo hallazgo de
este recorrido: si tras agotar lo automático el dato sigue sin poder
resolverse (ilegible o ambiguo), **no se cierra con un placeholder ni se deja
como pendiente "para más adelante"**. Se procede así:

1. **Abrir el documento y mandárselo** con `SendUserFile`: el PDF/foto
   original **más** un recorte ampliado que marque dónde está el dato.
2. **Presentar el error concreto**: qué parte sí se leyó y qué falta
   exactamente (ej. "11 de los 12 dígitos son ciertos: `#1477268_7948`, falta
   el octavo").
3. **Pedir el ingreso manual** del valor y aplicarlo con `corregir` /
   `resolver` cuando el usuario lo entregue.

Si varios `N° Ref.` comparten la misma foto (pasa seguido: ver la nota de
fotos sin recortar en HISTORIAL.md, 2026-09-14), decirlo y mandar el archivo
una sola vez en vez de copias repetidas.

**Antes de llegar acá, agotar lo automático** — en la revisión del 2026-09-14
eso cerró 20 de 24 celdas. Vale la pena, en este orden:

- extraer la **imagen embebida a resolución nativa** (`fitz` →
  `extract_image`) en vez de renderizar la página: las fotos de este módulo
  llegan a 2479x3229, y renderizar a 150 dpi las baja a 1240 px, perdiendo
  detalle que sí está en el archivo;
- si la imagen es RGB, **separar canales** (un pliegue o una sombra puede
  desaparecer en uno de ellos);
- **umbral** y **resta de fondo** (gaussiano de radio grande) para despegar
  una marca de agua preimpresa del texto térmico;
- buscar el mismo comprobante en **otra foto** del módulo (las fotos agrupan
  varios documentos y uno puede repetirse en dos tomas).

Lo que **no** recupera nada, comprobado: la tinta térmica perdida en una
banda vertical, el papel doblado sobre el número, y el texto de ~10 px de
alto bajo una marca de agua. Ahí se pasa directo a pedir el dato.
