# Análisis Financiero — lo que llega por el Intercambio

Detalle de referencia: léelo solo al tocar esto. Las reglas vigentes están en `../CLAUDE.md`.

## Costos proyectados desde el Formulador

Pedido del usuario: que las herramientas compartan información entre sí y,
en concreto, que el **Formulador de proyectos** (web) pueda actualizar los
costos proyectados de este módulo. Canal de entrada auditado a las 4
columnas "... Proyectado(s)" de "Proyectos" — **la única excepción a la
regla de oro de las columnas manuales**, por pedido explícito. Protocolo
común en `../Sistema Intercambio/CLAUDE.md`; lógica en
`Sistema/presupuestos_formulador.py`, enganchada en `ejecutar()`.

- El Formulador deja un mensaje `presupuesto-proyecto` (TAG + costos por
  categoría; gastos generales e imprevistos no viajan) en el `buzon/` de la
  carpeta de intercambio: desde el 2026-09-30,
  `Formulación de proyectos - Documentos/.Herramientas formulación/Intercambio/`
  (antes `Finanzas QUEMPIN/Intercambio/`), ubicada por
  `presupuestos_formulador.ubicar_intercambio()`; sin la biblioteca
  sincronizada queda inactivo con un aviso en `status`/`run`. Cada `run` lo aplica **después del
  respaldo y antes de fórmulas/Indicadores/Clientes**, así la misma corrida
  y el dashboard ya lo usan.
- **Solo escribe cuando es seguro**: celda vacía, valor que el propio
  Formulador escribió antes (registro de procedencia
  `Sistema/presupuestos_formulador.json`, gitignoreado), o valor que quien
  envió **vio** en el Formulador ("reemplaza", como un If-Match). Un valor
  escrito a mano que no se vio deja el envío **pendiente** en el buzón:
  `driver.py intercambio confirmar|descartar <id>`. Nunca aplica un envío a
  medias; varios envíos al mismo TAG: gana el último.
- Cada celda escrita lleva una **nota de Excel** con la procedencia (autor
  `Formulador (Intercambio)`). Si alguien la cambia a mano después, la
  corrida siguiente quita la nota y la trata como manual.
- Los envíos se archivan en `procesado/` y el registro se guarda **solo si el
  Excel se guardó**: con el libro abierto, todo queda en el buzón para la
  próxima. Nunca aborta el run (queda como aviso).
- TAG que no existe: pendiente hasta que aparezca (lo crea Centro de Costos
  con la primera factura), salvo que el envío diga `crear` con un nombre:
  ahí crea la fila (TAG + Nombre), en la primera fila libre (no sobre una a
  medio cargar).
- Al final de cada `run` publica `publicado/analisis-financiero.json` en esa
  carpeta (TAG, nombre, cliente, categoría, avance, proyectados con su
  origen, reales por categoría y estado de los envíos; sin "Gastos
  Generales" ni venta). La ve todo el que entra a la biblioteca de
  Formulación: el usuario lo aceptó al moverla ahí. `driver.py intercambio
  publicar` hace lo mismo **sin escribir el Excel**.
- El intercambio corre solo contra el libro del país (`ruta_excel_af`
  omitida; `PAISES["CL"]["raiz_intercambio"]`) o con una `raiz_intercambio`
  explícita: un test con Excel temporal nunca toca la carpeta real. **Un país
  ficticio de verificación debe sobrescribir `raiz_intercambio` y
  `ruta_estado_intercambio`** (si copia `PAISES["CL"]`, apuntarían a los
  reales). Perú: desactivado.
- Centro de Costos no se tocó; `cargar_datos_centro_costos()` (extraída de
  `ejecutar()`) es la única lectura de sus datos, compartida con
  `publicar_intercambio()`.

## Venta, N° de requerimiento y sesgo

- **`venta-proyecto`** usa el **mismo** canal y las mismas garantías: el
  monto de venta sin IVA de un proyecto adjudicado (de la cotización emitida
  en Sistema QUEMPIN, `fuente.folio`, o del precio neto del Formulador) va a
  «Monto de Venta (sin IVA)». Es otra clave (`CLAVE_VENTA`) del mismo
  registro de procedencia, no un segundo canal: dos implementaciones de "solo
  escribir cuando es seguro" terminarían divergiendo. Una venta a un TAG que
  no existe espera (no crea el proyecto). Un presupuesto y una venta del
  mismo TAG son independientes.
- **Un envío del N° X a la ficha de otro proyecto queda pendiente** (2026-11-03, `_otro_proyecto`): el N° sale de
  `proyecto.req`, del código de la oferta («280. …») o del valor que escribe el tablero; si la ficha tiene su carpeta
  con facturas en el Centro de Costos y el N° otra (`publicado/centro-costos-carpetas.json`, Sistema
  Intercambio/`mismo_proyecto.py`), no se aplica. `confirmar` lo deja pasar. Caso real: el presupuesto del 280 pisó
  los proyectados de UMAG («UMAG Linea de H2»).
- **«N° Requerimiento»** (columna nueva al final de "Proyectos", manual,
  amarilla): el N° de la Planilla de Ingreso, la clave común de proyecto.
  Un envío que trae `proyecto.req` la completa **solo si está vacía**. Al
  agregarla, la leyenda del resaltado manual (que vivía justo en esa celda,
  V1) se corre una columna: `asegurar_estructura_workbook` reconoce la
  leyenda y la reemplaza por el encabezado (verificado sobre una copia del
  libro real: las 21 columnas anteriores quedan idénticas).
- La publicación lleva ahora `req`, `venta: {cargada, origen}` (**nunca el
  monto**: la carpeta la ve todo el que entra a la biblioteca) y `sesgo`
  (`sesgo_cartera()` = `sesgo_por_categoria()` del tablero, en la forma del
  catálogo), que el Formulador usa para precargar su simulador de
  sobrecostos. `mensajes` incluye solo lo que iba a este módulo.
- El formato de cada mensaje y de la publicación está en
  `../Sistema Intercambio/esquemas/`; `test_la_publicacion_trae_el_sesgo_y_cumple_su_esquema`
  valida lo publicado contra él.

Tests: `Sistema/tests/test_presupuestos_formulador.py` (sandbox en
`tmp_path`). Verificado además de punta a punta con el Formulador real en
Chrome contra una copia del libro real (país ficticio, archivos reales sin
cambios).

## Ingreso manual desde el tablero (`datos-proyecto`)

Pedido del usuario: un lugar donde ingresar los valores manuales sin abrir el
Excel, que «genere un descargable» o deje el dato «listo para cargar». Eligió
(entre las opciones que se le dieron) **una pestaña en el mismo tablero** y
**el buzón de Intercambio** como camino al Excel, sabiendo que esa carpeta la
ve toda la biblioteca de Formulación.

- **La pestaña** («Ingresar datos», ver `Visualizador Web/CLAUDE.md`) deja un
  mensaje `datos-proyecto` **por proyecto** en el buzón: así un proyecto en
  conflicto no frena a los demás. Campos: todas las columnas manuales de
  «Proyectos» menos TAG y Nombre (`CAMPOS_TABLERO`, que es también lo que la
  pestaña muestra: no hay otra lista). Nombre solo al crear un proyecto.
- **Mismo canal y misma regla** que el Formulador, en
  `presupuestos_formulador.py`: la celda vacía se escribe; una con valor solo
  si todavía tiene lo que la persona vio en el tablero (`reemplaza`); si no,
  pendiente (`intercambio confirmar|descartar <id>`). Todo o nada por envío.
  Costos y venta usan **las mismas claves** que el Formulador (`Materiales`,
  `Monto de Venta`...), así los dos hablan de la misma celda.
- **Tres diferencias**, porque esto es ingreso manual y no la copia del
  estado de otra herramienta: (1) varios envíos al mismo proyecto se aplican
  **todos, en orden**, cada uno sobre lo que dejó el anterior (`planificar`
  decide en orden de envío y con los valores que van quedando; «gana el
  último» sigue solo para los dos tipos del Formulador); (2) **sin nota ni
  registro de procedencia**: queda como valor manual, y si pisa uno del
  Formulador le quita su nota y lo saca del registro; (3) puede dejar una
  celda vacía (`null`) y crear un proyecto con todos sus datos.
- **Tipos de valor**: el avance viaja como fracción (0,35) igual que en el
  Excel, las fechas como `AAAA-MM-DD` y se escriben como fecha de Excel, pesos
  y N° de requerimiento como enteros. La comparación «¿es el mismo valor?»
  (`_mismo_valor`) tiene su gemela en `ingreso.js` y un test las compara.
- **Formato**: lo que escribe el buzón (de cualquiera de los dos orígenes)
  toma el formato de su columna (`FORMATOS_COLUMNAS_PROYECTOS`) solo si la
  celda no tenía uno propio: en el libro real las celdas manuales ya traen el
  formato que les puso el usuario, y se respeta.
- **Archivo descargado** (navegador sin acceso a la carpeta): se deja tal cual
  en `buzon/`, o `driver.py intercambio cargar <archivo>` lo valida y lo deja
  ahí (mismo id, nunca dos veces).
- El procesador toma ahora los tipos que atiende AF **del catálogo** (cada
  esquema declara su destino), no de una lista suya; un test exige que
  coincidan con `pf.TIPOS`.

Verificado de punta a punta: un envío generado por la pestaña en Chrome
(carpeta simulada en el almacenamiento privado del navegador) aplicado con
`ejecutar()` sobre una copia del libro real, con los archivos reales (AF,
Centro de Costos, registro y buzón) sin cambios.
