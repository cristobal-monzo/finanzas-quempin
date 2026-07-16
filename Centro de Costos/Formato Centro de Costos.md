# Formato Centro de Costos.md

Registro del formato **real** de `Centro de Costos.xlsx`: colores, columnas,
formatos de celda, filtros, paneles inmovilizados, validaciones. Este
documento es **específico de este módulo** — para las convenciones
genéricas que cualquier módulo futuro debería seguir (estilo de encabezado,
paleta de colores, regla de oro de no reescribir filas, preservación de
formato manual, etc.), ver [Formato.md](Formato.md).

Complementa también a [CLAUDE.md](CLAUDE.md) (qué hace el módulo) y a
[.claude/skills/Registro_Centro_de_Costos/MEMORY.md](.claude/skills/Registro_Centro_de_Costos/MEMORY.md)
(preferencias de color/formato a nivel de decisión del usuario).

**Cómo se mantiene**: lo que sigue se levantó leyendo directamente el
`.xlsx` con `openpyxl` (no solo el código de `auditor_centro_costos.py`),
porque el libro tiene formato heredado del pipeline perdido (ver
`CLAUDE.md`) que el script actual no reproduce ni corrige. Cuando el
formato real cambie (a mano en Excel, o porque se modifica el script),
agrega una entrada fechada en "Historial de actualizaciones de formato" al
final — no reescribas las secciones de arriba sin dejar rastro del cambio.

⚠️ **Nota de sincronía (2026-07-16)**: el script ya tiene implementada la
migración a la columna oculta "Proveedor (Razón Social)" (§3, §14), pero
**el `.xlsx` real todavía no ha corrido esa migración** — la última vez que
se verificó el archivo directamente (antes de este cambio de código), `Master`
seguía en su layout viejo de 15 columnas (`A:O`, sin columna de Razón Social,
"Proveedor" con la razón social completa). La migración es idempotente y
corre sola al inicio del próximo `run`/`status`. Las tablas de este
documento describen el layout **post-migración** (lo que el script produce
hoy), no necesariamente lo que ves si abres el Excel antes de correr el
pipeline una vez más.

## 1. Hojas del libro

| Hoja | Tipo | Filas con datos | Columnas | Estado |
|---|---|---|---|---|
| `Master` | 1 fila/documento, con fórmulas | 25 antiguas + nuevas | A:P (16) | visible |
| `Detalle` | 1 fila/ítem de línea | ~92 antiguas + nuevas | A:J (10) | visible |
| `UMAG`, `Cesfam Limache`, `Gastos Generales` | hoja de proyecto, 100% fórmulas a `Master` | según docs del proyecto | A:M (13) | visible, se regenera completa en cada `run` |
| `Prueba 1` | hoja de proyecto (mismo formato) | 2 documentos (`PRUE-001`, `PRUE-002`) | A:M (13) | visible — **no está en `PREFIJOS_PROYECTO` ni en la lista de proyectos de `CLAUDE.md`**; confirmar con el usuario si es un proyecto real o una prueba que debería limpiarse |
| `_Claude` | registro interno de una versión anterior del pipeline (perdida) | 1093 filas, 6 columnas | A:F | **oculta**, el script actual no la lee ni la escribe, se conserva intacta |

Orden de hojas: `Master`, `Detalle`, luego proyectos en orden alfabético
(lo fuerza `auditor_centro_costos.py` en cada `run`, PASO 9).

> **Nota sobre `PRUE-002`**: el 2026-07-16 se registró un segundo documento
> en `Prueba 1` (`IMG_7364.JPEG`) que el pipeline marcó como **posible
> duplicado** de un N° Documento (`1913507`) ya existente. Por pedido del
> usuario se dejó tal como quedó ("déjalo ahí"), sin investigar más por
> ahora — si en algún momento hace falta revertirlo, el backup
> `Respaldos/Centro de Costos - backup 2026-07-16 1250.xlsx` tiene el
> estado justo antes de esa corrida.

## 2. Encabezados (fila 1)

Sigue el estándar genérico de [Formato.md](Formato.md) §2 sin variaciones:
navy `1F4E79`, Calibri 11 negrita blanca, centrado + wrap, borde fino. Alto
de fila 1 = **28.05** en `Master`/`Detalle`; las hojas de proyecto no tienen
alto de fila forzado.

## 3. Columnas por hoja

### `Master` (A:P)

**Desde 2026-07-16** hay una columna nueva, `H`, insertada junto a
`Proveedor` (ver "Historial" al final — migración de tag de proveedor). Todo
lo que antes era `H:O` se corrió una posición a la derecha (`I:P`).

| Col | Encabezado | Ancho actual | Formato número |
|---|---|---|---|
| A | N° Ref. | 40 | texto |
| B | Proyecto | 18 | texto (lista desplegable, ver §8) |
| C | Tipo de Proyecto | default (~8.4) | texto (lista desplegable) |
| D | Fecha | 21 | fecha, ver [Formato.md](Formato.md) §4 |
| E | N° Documento | 16 | texto |
| F | Tipo Documento | default | texto (lista desplegable) |
| G | Proveedor | 40 | texto — **tag corto** (ver "Historial" 2026-07-16), no la razón social |
| H | Proveedor (Razón Social) | auto | texto — **columna oculta**, razón social completa |
| I | Categoría | 22 | texto (lista desplegable) |
| J | Resumen Ítems | 40 | texto |
| K | Total sin IVA (CLP) | default | dinero — fórmula `SUMIF` |
| L | IVA 19% (CLP) | 15 | dinero |
| M | Total con IVA (CLP) | 21 | dinero — fórmula `=K+L` |
| N | Estado | 10 | texto (lista desplegable) |
| O | Archivo origen | 31 | texto — no editar |
| P | Fecha modificación | 21 | texto — no editar |

### `Detalle` (A:J)

| Col | Encabezado | Ancho actual | Formato número |
|---|---|---|---|
| A | N° Ref. | ~15.7 | texto |
| B | Proyecto | 18 | texto |
| C | Tipo de Proyecto | default | texto |
| D | N° Documento | 16 | texto |
| E | Nombre Ítem | 40 | texto |
| F | Descripción | default | texto |
| G | Categoría Ítem | 22 | texto (lista desplegable) |
| H | Cantidad | 10 | número |
| I | P. Unitario sin IVA | 21 | dinero |
| J | Total sin IVA (CLP) | default | dinero |

`Detalle` no tiene columna de proveedor — la migración de Razón Social solo
aplica a `Master` y a las hojas de proyecto.

### Hojas de proyecto (A:M, 100% fórmulas `=Master!<col><fila>`)

**Desde 2026-07-16**, 13 encabezados (antes 12) — se agregó `Proveedor
(Razón Social)` en `H`, también oculta: N° Ref., Proyecto, Tipo de Proyecto,
Fecha, N° Documento, Tipo Documento, Proveedor, Proveedor (Razón Social),
Categoría, Resumen Ítems, Total sin IVA (CLP), Total con IVA (CLP), Estado.

Anchos: patrón genérico de [Formato.md](Formato.md) §8 — solo se fijan la
primera vez, no se recalculan si ya existen.

## 3b. Prefijos de N° Ref. por proyecto

Constante `PREFIJOS_PROYECTO` en `auditor_centro_costos.py`: UMAG → `UMAG`,
Cesfam Limache → `CFLI`, Gastos Generales → `GGEN`. Un proyecto sin prefijo
definido ahí usa uno derivado automático y el script avisa por consola para
que se agregue a mano si el resultado no gusta (ver `Prueba 1` → `PRUE`,
§13).

## 4. Color de fondo por fila (paleta de proyecto)

Usa la paleta genérica de [Formato.md](Formato.md) §3. Asignación actual
real (leída del `tabColor` de cada hoja de proyecto, que el script
sincroniza con el color de fila):

| Proyecto | Color asignado por el script |
|---|---|
| Cesfam Limache | `FCE4D6` |
| Gastos Generales | `DDEBF7` |
| Prueba 1 | `E2EFDA` |
| UMAG | `FFF2CC` |

> ⚠️ **Esta asignación NO es lo que se ve hoy al abrir el Excel** para
> UMAG, Cesfam Limache y Gastos Generales — ver "Formato condicional
> heredado" (§9): hay reglas de formato condicional del pipeline perdido
> que pintan esas 3 hojas con OTROS colores y tienen prioridad visual sobre
> el relleno directo de celda. Solo las filas de `Prueba 1` (el único
> proyecto sin regla condicional) muestran el color de la tabla de arriba
> tal cual.

## 5. Fuente y color de texto

Convención genérica de [Formato.md](Formato.md) §3, sin variaciones.

**Discrepancia real entre filas antiguas y nuevas** (por la regla de oro
"nunca tocar una fila de datos ya escrita"):

| | Filas antiguas (pre 2026-07-16, del pipeline perdido) | Filas nuevas (escritas por `auditor_centro_costos.py`) |
|---|---|---|
| Fuente | Arial 10 | Calibri 11 |
| Alineación | centrada horizontal y vertical | sin alineación forzada (default de Excel) |

O sea, hoy el Excel se ve visualmente distinto entre documentos antiguos y
nuevos — no es un error del script, es consecuencia directa de la regla de
no reescribir filas ya creadas. Si se quiere una apariencia uniforme habría
que decidirlo explícitamente (repasar todas las filas antiguas una vez), no
es algo que el script deba hacer solo dado que rompería la regla de oro.

## 6. Formato de números y fechas

Convención genérica de [Formato.md](Formato.md) §4.

**Desde 2026-07-16**, `MONEY_FORMAT` (`auditor_centro_costos.py`) es
`"$"#,##0` — mismo formato que ya usaban las filas antiguas del pipeline
perdido, así que la discrepancia que había entre filas antiguas y nuevas
(antes: nuevas sin signo, `#,##0`) queda resuelta para todo documento
registrado de aquí en adelante. Las filas ya escritas con `#,##0` (sin
signo) entre el levantamiento inicial y este cambio no se retocan (regla de
oro, §7 de `Formato.md`) — quedan como excepción histórica puntual, no como
una categoría "antigua vs. nueva" permanente.

| | Formato |
|---|---|
| Montos (Total sin IVA, IVA, Total con IVA, P. Unitario) | `"$"#,##0` |
| Fecha (`Master!D`) | `mm-dd-yy` |

## 7. Filtros y paneles inmovilizados (freeze panes)

| Hoja | Autofiltro (`auto_filter.ref`) | Freeze panes |
|---|---|---|
| `Master` | `A1:M25` (heredado — rango viejo, ver nota) | `A2` (solo fila de encabezado) |
| `Detalle` | `A1:J79` | `A3` (encabezado + primera fila de datos) |
| Hojas de proyecto | ninguno | ninguno |
| `_Claude` | ninguno | ninguno |

**Ninguno de estos rangos los crea ni los actualiza
`auditor_centro_costos.py`** (no hay `auto_filter` ni `freeze_panes` en el
script) — son 100% heredados del pipeline perdido y quedaron "congelados"
en el estado en que se guardaron por última vez ahí:

- El autofiltro de `Master` llega solo hasta la fila 25 y la columna M del
  layout **viejo** (15 columnas) — con el layout nuevo de 16 columnas, ese
  rango ya no corresponde ni siquiera a las mismas columnas (la M vieja era
  "Estado", la M nueva es "Total con IVA"). No cubre las filas agregadas
  desde entonces ni las columnas O/P. Los desplegables de filtro de Excel no
  van a mostrar esos datos hasta que alguien reaplique el filtro a mano
  (`Datos > Filtro` sobre el rango completo).
- El autofiltro de `Detalle` llega solo hasta la fila 79 — no cubre las
  filas agregadas después.
- El freeze panes de `Detalle` en `A3` (en vez de `A2`) deja fija en
  pantalla también la primera fila de datos (`CFLI-001`), no solo el
  encabezado — es asimétrico respecto a `Master` y probablemente no fue
  intencional, solo quedó así del pipeline perdido.
- Cada vez que se agreguen documentos nuevos, hay que reaplicar/expandir el
  filtro a mano si se quiere que cubra las filas nuevas — el script no lo
  hace por ahora.

## 8. Validación de datos (listas desplegables)

Son listas fijas de Excel (`Datos > Validación de datos`), heredadas del
pipeline perdido; el script actual no las crea pero sí las mantiene
consistentes con el layout de columnas cuando inserta la columna de Razón
Social (`_migrar_rangos_columna` en `auditor_centro_costos.py`):

| Hoja!Rango | Columna | Opciones de la lista |
|---|---|---|
| `Master!B2:B225` | Proyecto | `Cesfam Limache, Gastos Generales, UMAG` (**no incluye `Prueba 1`**) |
| `Master!C2:C225` | Tipo de Proyecto | `Certificación, Mantenimiento, I+D+i, Gastos Generales` |
| `Master!F2:F225` | Tipo Documento | `Factura, Boleta, Guía de Despacho` |
| `Master!I2:I225` | Categoría | `Materiales, Consumibles, Equipos-Herramientas, Transporte, Combustible` |
| `Master!N2:N225` | Estado | `Pendiente, Pagado` |
| `Detalle!G2:G279` | Categoría Ítem | mismas 5 opciones que `Master!I` |

**Desde 2026-07-16**, `Categoría` y `Estado` viven en `I`/`N` (antes
`H`/`M`) — el script desplazó estos rangos automáticamente al insertar la
columna `H` nueva (`migrar_columna_proveedor`/`_migrar_rangos_columna` en
`auditor_centro_costos.py`), no fue un ajuste manual.

Si se agrega un proyecto/categoría/tipo de documento nuevo que no está en
estas listas, Excel puede mostrar advertencia o simplemente no ofrecerlo en
el desplegable (dependiendo de si la validación tiene "detener" o solo
"advertir" — no verificado). El rango de cada validación (`...225` /
`...279`) da margen para más filas de las que hay hoy, así que datos nuevos
dentro de ese rango sí quedan cubiertos por la lista, a diferencia del
autofiltro (§7).

## 9. Formato condicional heredado (del pipeline perdido)

`Master!A2:P225` (antes `A2:O225` — extendido a `P` el 2026-07-16 al agregar
la columna `H`, ver "Historial") y `Detalle!A2:J279` tienen reglas de formato
condicional tipo "fórmula", tres reglas por hoja, todas comparando la
columna Proyecto:

| Prioridad | Fórmula | Color de relleno (dxf) |
|---|---|---|
| 1 | `$B2="UMAG"` | `D9E8FB` (celeste) |
| 2 | `$B2="Cesfam Limache"` | `D9F0D9` (verde pálido) |
| 3 | `$B2="Gastos Generales"` | `FCE4D6` (durazno) |

**Estas reglas tienen prioridad visual sobre el relleno directo de celda**
que aplica `auditor_centro_costos.py` (`pintar_fila`) — es una regla
general de Excel: el formato condicional se muestra en vez del formato
manual cuando su condición es verdadera. Por eso, hoy en la práctica:

- Filas con Proyecto = UMAG se ven **celeste** (`D9E8FB`), no amarillo
  pálido (`FFF2CC`, el color que le asignó el script en la tabla de §4).
- Filas con Proyecto = Cesfam Limache se ven **verde pálido** (`D9F0D9`),
  no durazno (`FCE4D6`).
- Filas con Proyecto = Gastos Generales se ven **durazno** (`FCE4D6`), no
  celeste (`DDEBF7`).
- Filas con Proyecto = Prueba 1 sí muestran su color real de relleno
  (`E2EFDA`), porque no hay regla condicional para ese proyecto.

Comprobado directamente: las filas antiguas (pre-2026-07-16) de
`Master`/`Detalle` no tienen ningún relleno directo de celda (`00000000` =
sin relleno) — todo su color visible viene de estas reglas condicionales.
Solo las filas nuevas (escritas desde la reconstrucción del script en
adelante) tienen relleno directo real.

**Implicación a futuro**: si se registra un documento nuevo de UMAG,
Cesfam Limache o Gastos Generales, el script sí le va a asignar el color
"correcto" de la paleta (§4) como relleno directo, pero como esas 3 reglas
condicionales lo siguen tapando, se va a seguir viendo con el color viejo
del pipeline perdido — no con el de `PALETA`. Solo notarías el color real
de `PALETA` si el proyecto es nuevo (como `Prueba 1`) o si en algún momento
se decide borrar estas 3 reglas condicionales. No se toca nada de esto sin
que el usuario lo pida explícitamente — se deja registrado acá para que la
próxima vez que algo "se vea mal" en colores, se sepa por qué.

## 10. Bordes

Convención genérica de [Formato.md](Formato.md) §5, sin variaciones.

## 11. Columnas ocultas y formato manual (hojas de proyecto)

**Desde 2026-07-16**, `regenerar_hoja_proyecto` ya no borra y recrea la hoja
de proyecto en cada `run` — reutiliza el mismo objeto de hoja y solo borra
las filas de datos/pie/leyenda (fila 2 en adelante). Antes, borrar+recrear
la hoja completa tiraba cualquier formato manual a nivel de columna/hoja:
columnas ocultas, anchos fijados a mano, autofiltro, freeze panes,
validaciones de datos. Ahora ese formato persiste entre corridas — si
ocultas una columna en una hoja de proyecto, sigue oculta después del
próximo `run` (el script igual lee/escribe esa columna con normalidad; estar
oculta no afecta el acceso por celda en `openpyxl`).

Esto no aplica a `Master`/`Detalle`: esas dos hojas nunca se borraban ni se
recreaban (el script solo hace `wb["Master"]`/`wb["Detalle"]`), así que
columnas ocultas ahí ya se preservaban antes de este cambio. Lo único que sí
se corrigió para esas dos hojas es el mismo problema de ancho de columna
(ver §3).

**Excepción deliberada**: la columna `H` ("Proveedor (Razón Social)") sí se
fuerza oculta en cada `run`, tanto en `Master` como en las hojas de
proyecto (`ws.column_dimensions[...].hidden = True` explícito en el
script) — a diferencia de los anchos (que si se respetan entre corridas),
si la desocultas a mano en Excel para revisarla, el próximo `run` la vuelve
a ocultar. Ver §14.

## 12. Hoja oculta `_Claude`

Registro interno de una versión anterior del pipeline (la que corría en
`Plantillas/`, perdida). Columnas: `Hoja, Clave, Col, Valor escrito por
Claude, (vacía), NO EDITAR NI BORRAR: ...`. 1093 filas. El script actual no
la lee ni la escribe — se conserva intacta solo por si algún día se
recupera o se necesita para entender qué escribió el pipeline anterior.

## 13. Pendientes / inconsistencias detectadas (no son bugs del script actual, son estado heredado)

- Hoja `Prueba 1`: proyecto con datos (`PRUE-001`, Comercial Anwo S.A.,
  2026-06-04; `PRUE-002`, 2026-07-16, marcado posible duplicado — ver §1)
  pero no está en `PREFIJOS_PROYECTO` ni mencionado en `CLAUDE.md` como
  proyecto vigente — confirmar con el usuario si es un proyecto real que
  falta documentar o una prueba que se debería limpiar.
- Formato condicional heredado (§9) tapa el color de 3 de los 4 proyectos —
  decidir en algún momento si se borran esas reglas para que el color de
  `PALETA` se vea de verdad, o si se dejan así porque total el efecto
  visual (colores distintos por proyecto) es el mismo aunque el hex no
  coincida con lo que el script "cree" que pintó.
- Autofiltro y freeze panes (§7) no se actualizan solos — quedaron fijos en
  el estado del pipeline perdido y no cubren filas/columnas agregadas
  después; con el layout nuevo de 16 columnas, el rango del autofiltro de
  `Master` ya ni siquiera corresponde a las mismas columnas.
- Fuente/alineación (§5) distintos entre filas antiguas y nuevas — visual,
  no aritmético, pero notorio si se mira la planilla completa. (El formato
  de moneda, §6, ya no es parte de esta discrepancia desde 2026-07-16 —
  quedó unificado a `"$"#,##0`, salvo el puñado de filas escritas sin signo
  entre el levantamiento inicial y ese cambio.)
- El `.xlsx` real todavía no tiene la migración de columna Proveedor/Razón
  Social aplicada (ver nota de sincronía al inicio) — corre sola en el
  próximo `run`/`status`.

## 14. Columna oculta "Proveedor (Razón Social)"

**Desde 2026-07-16.** `Master!H` y la columna homóloga (`H`) de cada hoja de
proyecto están ocultas (`column_dimensions[...].hidden = True`, forzado en
cada `run`). Guardan la razón social completa del proveedor; la columna
visible `Proveedor` (`G`) muestra un tag corto derivado de ella —
ver `TAGS_PROVEEDOR_CURADOS` / `generar_tag_proveedor()` en
`auditor_centro_costos.py`. Para desocultarla temporalmente en Excel
(clic derecho sobre las columnas → "Mostrar columnas"): el próximo `run` la
vuelve a ocultar, a diferencia de los anchos de columna (§3), que si se
respetan entre corridas.

## Historial de actualizaciones de formato

### 2026-07-16 — montos con signo de moneda (`MONEY_FORMAT` de `#,##0` a `"$"#,##0`)
A pedido del usuario ("los montos monetarios van en formato moneda con el
signo de moneda automático de excel, con separador de miles y sin
decimales"), se cambió `MONEY_FORMAT` en `auditor_centro_costos.py` de
`#,##0` a `"$"#,##0`. Esto además resuelve la discrepancia que había entre
filas antiguas (pipeline perdido, ya usaban `"$"#,##0`) y nuevas (sin signo)
documentada en §6 — de aquí en adelante todo documento registrado queda con
el mismo formato de moneda que las filas antiguas. Las filas ya escritas
entre el levantamiento inicial (2026-07-16) y este cambio, que quedaron con
`#,##0` sin signo, no se retocan (regla de oro) — quedan como excepción
puntual, no una categoría permanente.

### 2026-07-16 — separación de este documento (específico) del patrón genérico
Este archivo se creó moviendo aquí todo el contenido específico de Centro de
Costos que antes vivía en `Formato.md`, a pedido del usuario ("quiero que el
documento de formato sea genérico para que [sirva para] cualquier proyecto
futuro. Las características específicas de cada proyecto pueden asignarse en
otro .md"). `Formato.md` quedó con solo el patrón reutilizable (estilo de
encabezado, paleta, convención de colores, regla de oro, preservación de
formato manual). Este documento sigue siendo la fuente de verdad del estado
real del `.xlsx` de este módulo — mantenerlo actualizado con fecha en cada
cambio real, igual que antes.

### 2026-07-16 — columna "Proveedor (Razón Social)" + tag corto de proveedor
A pedido del usuario ("quiero que generes una nueva columna para todas las
columnas en donde se muestren los proveedores... la versión simplificada es
la que se muestra y la versión completa queda en una columna a la derecha de
esta que va a estar oculta", ej. "Estaciones de Servicios Fandos Ltda.
(Shell Ruta 68)" → "Shell"), se agregó `Proveedor (Razón Social)` en `Master!H`
(y en `H` de cada hoja de proyecto), oculta — ver §3, §11 y §14. Cambios en
`auditor_centro_costos.py`:
1. `TAGS_PROVEEDOR_CURADOS` — diccionario curado a mano, razón social exacta
   → tag corto, con los proveedores conocidos a esa fecha (Beckman, Easy,
   Air Express, Patagónica, El Estuche, Crosur, RECASUR, El Águila, BOLT,
   Tur Bus, Shell, ACO, Danus, UTECSA, LATAM, Dezar, Engas, Antonio Ruiz,
   Anwo). Si un tag generado automáticamente no queda representativo, la
   corrección es agregar/editar la entrada correcta aquí.
2. `generar_tag_proveedor()` — heurística de respaldo para un proveedor
   nuevo que no esté en el diccionario: usa la marca entre paréntesis si la
   razón social trae una (ej. "(Shell Ruta 68)" → "Shell"), si no limpia
   sufijos legales (SpA, S.A., Ltda...) y palabras genéricas (Comercial,
   Sociedad, Inversiones...) y toma las 1-2 palabras que queden.
3. **Migración única e idempotente** (`migrar_columna_proveedor`, corre al
   inicio de `main()`, apenas se abre el libro): inserta la columna nueva en
   `Master` con `ws.insert_cols(8)`, mueve la razón social completa (que ya
   estaba en `G`) a la `H` nueva, y reemplaza `G` por el tag —
   **excepción deliberada** a "nunca tocar una fila de datos ya escrita"
   (decisión del usuario: sí quiso backfill de las filas antiguas, no solo
   aplicarlo hacia adelante). Como `insert_cols` de openpyxl NO ajusta solo
   fórmulas, validaciones de datos ni formato condicional, la migración
   también corrige a mano: las fórmulas `K`/`M` de cada fila ya existente
   (antes `J`/`L`), los rangos de validación de `Categoría`/`Estado` (antes
   `H`/`M`, ahora `I`/`N` — ver §8) y el rango de formato condicional
   (extendido de `O225` a `P225` — ver §9). Las hojas de proyecto NO
   necesitaron migración manual: se regeneran completas en cada `run`, así
   que basta con haber actualizado `ENCABEZADOS_PROYECTO` y el mapeo de
   columnas de `Master` en `regenerar_hoja_proyecto`.
4. `Detalle` no tiene columna de proveedor, no se tocó.
Verificado corriendo el pipeline completo dos veces sobre una copia de
`Centro de Costos.xlsx` (no el archivo real): la primera corrida migra las
filas existentes y las fórmulas/validaciones/formato condicional quedan
consistentes; la segunda corrida detecta que ya está migrado y no repite la
inserción de columna (idempotente). **El archivo real de producción todavía
no ha corrido esta migración** — ver nota de sincronía al inicio de este
documento.

### 2026-07-16 — el script respeta formato manual (anchos, columnas ocultas)
A pedido del usuario ("quiero que el formato que modifique manualmente lo
mantengas, como ancho de columnas, tipo de casilla, las columnas ocultas las
mantengas ocultas pero que puedas leerlas y las actualices igual que
antes"), se cambió `auditor_centro_costos.py` en dos puntos:
1. `ajustar_anchos` ahora solo fija el ancho de una columna si todavía no
   tiene uno (`column_dimensions[letra].width` vacío) — antes lo
   recalculaba siempre, pisando cualquier ajuste manual. Aplica a `Master`,
   `Detalle` y hojas de proyecto.
2. `regenerar_hoja_proyecto` ya no borra y recrea la hoja de proyecto
   completa en cada `run` — reutiliza la hoja existente y solo borra las
   filas de datos/pie/leyenda. Esto preserva columnas ocultas, autofiltro,
   freeze panes y validaciones de datos que el usuario haya dejado en esa
   hoja (antes se perdían en cada corrida). Ver §11.
Verificado sobre el archivo real (2026-07-16, tras cerrar Excel): las
columnas ocultas ya existentes en `Master` (K=IVA, M=Estado, N=Archivo
origen, O=Fecha modificación, con el layout viejo de 15 columnas) siguieron
ocultas y con su ancho intacto después de un `run` real que además registró
`PRUE-002` (ver §1).
Esto reemplaza lo documentado en versiones anteriores de este archivo
(decía explícitamente "no vale la pena fijar anchos a mano, se pierden en
la próxima corrida" — ya no es cierto).

### 2026-07-16 — primer levantamiento completo
Se creó este archivo (entonces como `Formato.md`) inspeccionando
`Centro de Costos.xlsx` directamente con `openpyxl` (no solo leyendo el
código), para capturar el formato tal como está hoy, incluyendo lo heredado
del pipeline perdido que `auditor_centro_costos.py` no reproduce. Hallazgos
nuevos respecto a lo ya documentado en `CLAUDE.md`/`MEMORY.md`: listas
desplegables de validación de datos (§8), formato condicional heredado que
tapa el color de 3 proyectos (§9), discrepancia de fuente/alineación/formato
de moneda entre filas antiguas y nuevas (§5-6), y rangos de
autofiltro/freeze panes desactualizados (§7). Ninguno de estos hallazgos se
corrigió — solo se registró, a la espera de que el usuario decida qué hacer
con cada uno.
