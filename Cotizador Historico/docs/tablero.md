# Cotizador Histórico: tablero en detalle

Detalle de referencia: léelo solo al tocar esto. Las reglas vigentes están en `../Visualizador Web/CLAUDE.md`.

## Por qué la UF se fija al momento del build, no en vivo

El HTML publicado no pide la UF del día a `mindicador.cl` desde el
navegador. Los Artifacts de Claude no exponen una capability genérica de
"fetch a cualquier API externa" (solo `downloads` y `mcp`, y
`mindicador.cl` no es un conector MCP) — ese fetch quedaría bloqueado por
el sandbox del Artifact. Por eso `build_visualizador.py` pide la UF de hoy
una sola vez en tiempo de build y la incrusta en el snapshot; el header del
visualizador la muestra de forma visible ("UF utilizada: $X — actualizada
DD-MM-AAAA HH:MM"). Refrescarla requiere volver a correr
`driver.py visualizador` y republicar — mismo mecanismo que usa Centro de
Costos para su "última actualización de los datos".

**Fallback si `mindicador.cl` no responde al momento del build** (agregado
2026-08-20, ver `../CLAUDE.md` § La UF):
`build_visualizador.py` acepta `uf_manual`/`fuente_manual` (el driver los
expone como `--uf-manual`/`--uf-fuente`), un valor que el agente busca en
internet solo cuando mindicador.cl falla — mindicador.cl sigue siendo la
fuente prioritaria. Cuando se usa ese fallback, el snapshot trae
`"uf_fuente"` con el texto de la fuente (en vez de `"mindicador.cl"`) y el
header/KPI/pie de exportación del visualizador le agregan el sufijo
"· fuente: &lt;texto&gt;" junto a "UF utilizada" (`ufFuenteSufijo()` en
`template.html`) — transparencia obligatoria: quien vea el dashboard debe
poder distinguir un valor manual de uno de mindicador.cl.

## Búsqueda

La búsqueda ocurre **100% en el navegador** contra el índice ya precalculado
incrustado en el HTML — no hay ninguna llamada de red en tiempo de uso.

**El motor no vive acá.** Desde el rediseño del 2026-09-16 el buscador es
`../Visualizador Web/busqueda.js`, **un solo archivo que comparten Chile y
Perú**, inyectado por cada `build_visualizador.py` en el placeholder
`__CH_BUSQUEDA_JS__`. Sus tablas (sinónimos, palabras vacías, pesos por
campo, alias de medida, umbrales) llegan en el snapshot desde
`../Sistema/catalogo_busqueda.py`, y los términos de cada ítem vienen ya
calculados desde Python (`_bt`, `_bm`). El diseño completo y el porqué están
en [`busqueda.md`](busqueda.md).

**Lo que había antes** (y por qué se cambió): ~60 líneas de JavaScript en
este template —`normalizeText`, `diceCoefficient`, `similitud`,
`buscarItems`— que devolvían `1.0` en cuanto el ítem compartía una palabra
de 4 letras con la consulta. Sobre el catálogo real eso dejaba 41 válvulas
empatadas y el orden lo decidía el Excel. Estaban además duplicadas en el
template de Perú, el mismo patrón que ya había causado la divergencia de la
taxonomía. Se eliminaron.

**Lo que sí hace este template** es la pantalla. Su orden responde a una
sola idea: **se viene a buscar un precio**, así que la búsqueda va primero y
todo lo demás le deja espacio (rediseño del 2026-09-21, ver [`HISTORIA.md`](../Visualizador%20Web/HISTORIA.md)).

- **Buscador arriba y grande** ("¿Qué necesitas cotizar?"), con ejemplos
  reales, botón de limpiar, atajo de teclado `/` y **autocompletado**
  (`renderAutocomplete`) alimentado por `DATA.sugerencias` — los nombres
  reales del catálogo (producto, familia, categoría, marca, material,
  medida) calculados en Python, no una lista escrita a mano. Navegable con
  flechas y Enter, con el tipo de cada sugerencia a la vista. El campo usa
  16px: con menos, Safari de iPhone hace zoom al tocarlo.
- **Los KPIs del catálogo van debajo del buscador y se ocultan mientras hay
  una búsqueda activa** (`#kpiWrap`): con una consulta escrita no aportan y
  empujaban los resultados fuera de la pantalla.
- **Filtros en un panel plegable** (`#btnFiltros` / `#filterPanel`, cerrado
  por defecto) con el número de filtros activos en el botón. Los 11
  controles abiertos ocupaban media pantalla antes de buscar nada. Son
  combinables y dependientes (`opcionesDe`): Categoría, **Familia**,
  Subcategoría, Material, Medida, Marca, Proveedor, Proyecto, rango de fechas
  y rango de precio; cada desplegable se calcula contra **lo que la búsqueda
  actual encontró** más los otros filtros, con el conteo en cada opción, así
  que nunca ofrece una combinación que da cero. Los filtros activos se ven
  como chips junto al botón aunque el panel esté cerrado, y se quitan de a uno
  o con "Limpiar todo".
- **Filtros que dependen de la familia del producto** (`#filtrosFamilia`,
  2026-09-22): al elegir una familia —o cuando todo lo encontrado es de una
  sola— aparecen los filtros que tienen sentido para ella, con los valores que
  existen: **Planchas** → Material, Espesor, Ancho, Largo, Terminación, Grado;
  **Cañerías y Tubos** → Material, Diámetro, Schedule, Tipo de pared, Presión,
  Norma, Largo; **Pernos** → Diámetro, Largo, Material, Grado, Rosca. No tiene
  sentido ofrecer "Schedule" para una plancha ni "Ancho" para una válvula. La
  tabla de qué atributo va con qué familia es
  `Sistema/catalogo_atributos.FACETAS_POR_FAMILIA` y viaja en el snapshot
  (`DATA.facetas`); los valores vienen ya formateados en `item.atr`, que arma
  `cotizador_historico.compactar_atributos`. **Acá no se calcula ningún
  atributo**: el HTML solo lee lo que el build dejó listo.
- **Refinar en un clic** (`renderRefinar`): las opciones de Medida, Material
  o Categoría que existen en lo encontrado, como chips con su conteo. Es el
  mismo cálculo que los desplegables, a la vista: buscar "codo" y quedarse
  con los de bronce ya no obliga a abrir el panel. En celular cada faceta es
  una fila deslizable.
- **Barra de resultados** (`#searchToolbar`): cuántos productos y compras,
  el rango de precio y la medida pedida, más el orden (relevancia, precio
  asc/desc, compra más reciente) y "Agrupar por producto". No muestra un
  promedio general a propósito: con productos distintos (válvulas de varias
  medidas) ese número no describe a ninguno.
- **Resultados agrupados por producto** (`agruparResultados` +
  `renderGrupoCard`): una tarjeta por hoja con la ruta de categoría, el
  precio **más barato** destacado con su proveedor, el promedio, cuántas
  compras y proveedores hay, la última compra, y un **rango de precios**
  (`renderRango`): cada compra como un punto sobre la línea del más barato al
  más caro, con el promedio marcado y tooltip por punto. Sin agrupar, las
  tres compras idénticas de la misma válvula ocupaban tres de los cinco
  primeros lugares. Si la búsqueda encuentra **un solo producto**, la
  tarjeta se abre sola.
- **Comparar las compras en una tabla** (`renderTablaCompras`): precio hoy
  c/IVA y s/IVA, lo pagado, proveedor, fecha, proyecto y el detalle
  resaltado, con la más barata marcada. Reemplazó a una grilla de tarjetas
  que repetía en cada compra el mismo título y los mismos chips: con 5
  compras había que leer 5 tarjetas para comparar 5 precios. En celular
  (≤720px) cada fila se apila como tarjeta con sus etiquetas. La vista de
  una hoja en el explorador usa **la misma tarjeta y la misma tabla**
  (`resumirCompras` es la única cuenta de promedio/mínimo/proveedores).
- **Abrir la factura de una compra** (2026-10-29, pedido del usuario: «igual
  que el botón del Centro de Costos»): junto al N° Ref., en la tabla de
  compras y en la tarjeta sin agrupar, el mismo ícono del Centro de Costos
  abre el documento en SharePoint, en otra pestaña (`refConDocumento`). El
  build arma **un enlace por documento**, no por ítem, en `DATA.documentos`
  (`{N° Ref.: enlace}`, `enlaces_documentos()`), desde "Archivo origen" de
  `Master` —que `cargar_items_detalle` ahora lee— con la regla compartida de
  `../../Visualizador Web/documentos.py`: la misma del Centro de Costos, sin
  enlace si el archivo ya no está en la carpeta sincronizada (al 2026-10-29,
  811 de 812 documentos; al que falta le cambiaron la carpeta). Sin
  enlace solo se ve el N° Ref. Lo abre quien tiene acceso al sitio, también
  en el teléfono. El carrito no lleva el ícono: su foco atrapado solo recorre
  botones y campos.
- **Por qué apareció cada resultado** (`chipsMotivos`): chips que dicen qué
  término calzó en qué campo, con la medida destacada, usando **la palabra
  que escribió el usuario** (`palabrasDeConsulta`) y no la raíz interna del
  motor — "bronc" se leía como un error de tipeo. Un match aproximado se
  marca "(aprox.)".
- **Resaltado por palabra** (`BUSCADOR.resaltar`): marca cada palabra que
  calzó, incluyendo plurales, sinónimos y la medida. El resaltado anterior
  buscaba la consulta completa como substring, así que en "valvula de bola
  2" no marcaba nada.
- **Aviso de consulta a medias** (`#searchAviso`): si un término no existe
  en el catálogo, se dice explícitamente en vez de dejar creer que los
  resultados son lo que se pidió.
- **Estado vacío útil** (`renderEstadoVacio`): qué término falló, qué
  escribir en su lugar, un atajo para quitar los filtros y categorías
  cotizables para explorar (nunca las de gastos de operación).
- **Historial de búsquedas** en `sessionStorage` (`ch_viz_recientes`, máximo
  8): vive lo mismo que el desbloqueo del gate y se va al cerrar la pestaña.
  No es `localStorage` a propósito — son consultas escritas por el usuario y
  no hay razón para que sobrevivan a la sesión.
- **Celular y accesibilidad**: las pestañas de tableros son una fila
  deslizable con la activa centrada; ningún texto largo (ej. la fuente de la
  UF) desborda el ancho de la pantalla; foco de teclado visible en todo lo
  operable (`:focus-visible`); animaciones apagadas con
  `prefers-reduced-motion`.

`.viz-compras` fija `color` explícito: viene de cuando la página corría en modo quirks (sin eso, en
modo oscuro las celdas quedaban negras sobre negro). Hoy declara `<!DOCTYPE>`.

**Chile y Perú comparten este template línea por línea**, salvo las ~14
líneas propias del país (título, pestaña activa, moneda, pie, UF/soles y el
`S/` de los rangos de precio). `tests/test_template.py` lo exige: un cambio
de pantalla aplicado a un solo país hace fallar la suite. Para propagar un
cambio, se edita el de Chile y se aplica igual al de Perú.

**La marca ya no se adivina.** `extraerMarcaModelo` ("la primera palabra
capitalizada que no sea preposición") producía chips como "Precio" o "Cod".
Se reemplazó por una lista curada en `../Sistema/catalogo_busqueda.py`
(`MARCAS`), aplicada por palabra completa: si no está en la lista, el ítem
simplemente no tiene marca. Una marca mal detectada no es solo un chip feo,
es un filtro que promete agrupar y agrupa cualquier cosa.

## Taxonomía y explorador de carpetas

El dashboard organiza el catálogo en un explorador de carpetas de 3
niveles — **Categoría → Subcategoría → Hoja** — en vez de una tabla plana o
un ranking Top N.

**La clasificación ya no se hace acá** (cambio del 2026-09-08). Hasta esa
fecha este template tenía ~290 líneas de JavaScript con listas de palabras
clave (`clasificarItem`, `GRUPOS_*`, `extraerMedida`, `detectarTipoGenerico`,
`subcategoriaDe`/`hojaDe`), duplicadas en el template de Perú y **ya
divergentes** entre ambos, sin ningún test, y que la consulta por consola no
usaba. Todo eso se movió a `../Sistema/taxonomia.py` +
`../Sistema/catalogo_taxonomia.py`; el motivo, las mediciones sobre el
catálogo real y las decisiones de diseño están en
[`../docs/specs/2026-09-08-taxonomia-cotizador-design.md`](../docs/specs/2026-09-08-taxonomia-cotizador-design.md)
y resumidas en [`clasificacion.md`](clasificacion.md).

Lo que hace hoy el template:

- `build_visualizador.py` deja cada ítem del snapshot con `categoria`,
  `subcategoria`, `familia`, `material`, `medida`, `hoja` y `cotizable` ya
  resueltos, más un mapa `DATA.categorias` con el ícono y si la categoría es
  cotizable.
- El template solo copia esos campos a `it._clasif` (32 líneas) y arma el
  árbol. **Para cambiar cómo se clasifica algo se edita
  `catalogo_taxonomia.py` y se regenera el build; acá no hay nada que
  tocar.**
- `ITEMS_VISIBLES` es ahora `DATA.items` completo: **ningún ítem se oculta**.
  La `esVisible` anterior descartaba del dashboard cualquier fitting sin
  medida o material detectable — 136 de 1193 compras (11,4%), en silencio.
  Ahora esos quedan en una hoja marcada `(sin medida)`, visibles y contados.
- El filtro "Categoría" del buscador usa la categoría de la taxonomía, no la
  columna `Categoría Ítem` del Excel (que tiene 16 valores con duplicados
  por tilde: `Ferreteria`/`Ferretería`, `Alimentacion`/`Alimentación`).
- Los KPIs muestran ahora **Catálogo cotizable** (productos vs gastos de
  operación) y **Sin clasificar**, que es una cola de trabajo visible: si
  crece, hay que agregarle reglas al catálogo.
- `buildLeafIndex`/`MARKET_STATS` siguen agrupando por **hoja**
  (`familia + material + medida`) — dos codos de bronce de distinta medida
  nunca se promedian como si fueran el mismo producto. Cada hoja trae
  `n_compras`, `promedio_con_iva`, `precio_min_con_iva`,
  `proveedor_min_con_iva` (con IVA, porque es lo que ve el comprador final).
- `buildCategoryTree` arma el árbol navegable; el estado de navegación
  (`folderState.categoria/subcategoria/hoja`) se renderiza con
  `renderFolderBrowser` + `renderBreadcrumb` sobre `#folderBrowser`/
  `#folderBreadcrumb`. Abrir una hoja muestra el resumen agregado
  (promedio, más barato + proveedor) y reutiliza `renderRefCard` para cada
  compra individual de esa hoja — incluyendo el "Agregar al cotizador" de
  cada una.

## Carrito de cotización — garantía de no-persistencia

El carrito vive **solo en una variable JS en memoria** (`var cart = []`,
comentario explícito en `template.html`: "carrito (solo en memoria --
nunca localStorage/sessionStorage)"). Recargar la página lo vacía por
completo. Esto es un requisito no negociable del usuario, no un descuido:
a diferencia del tema visual (que sí usa `localStorage`) o del estado de
"gate desbloqueado" (que usa `sessionStorage`), el contenido del carrito
nunca se escribe en ningún almacenamiento del navegador.

- **«Copiar para el Formulador»** (2026-10-14, Chile y Perú): copia al
  portapapeles las líneas del carrito como `Descripción · Unidad · Cantidad ·
  Costo unitario neto` (la hoja, `Un.`, la cantidad y `precio_reajustado_hoy`
  redondeado), el formato que reconoce «Pegar desde Excel» del Formulador
  (`js/pegar.js`, paso 3). Va por el portapapeles y no por el navegador: el
  carrito sigue sin persistir. `test_template.py` lo exige en los dos países.

- **«Llevar a un proyecto…»** (2026-10-29, Chile y Perú; pedido del usuario:
  que el carrito exporte sus costos a un proyecto específico en formulación o
  en ejecución): es la acción principal del panel, sobre la tabla para Excel.
  Los proyectos del equipo los conoce el **Portal QUEMPIN** (lee la carpeta del
  equipo), así que el carrito le manda sus líneas como mensaje entre ventanas
  (`postMessage`, tipo `quempin-cotizacion`, armado por `datosParaProyecto()`):
  dentro del Portal (`<html data-en-portal>`), a la ventana de arriba; abierto
  suelto, abre `…/portal/#/llevar-cotizacion` en otra pestaña y le contesta
  cuando el Portal avisa `quempin-portal-listo` (solo a esa ventana y desde
  `cristobal-monzo.github.io`). Cada línea lleva el costo **neto** (como
  «Copiar para el Formulador»; en soles con centavos), su proveedor, su
  `hoja_clave` (con ella «Proyectos en ejecución» compara contra lo pagado), la
  categoría del Centro de Costos y la compra de donde sale el precio. La moneda
  sale del país del tablero (`data-nav-activo`). Nada pasa por el
  almacenamiento del navegador ni por la dirección: `test_template.py` lo
  vigila. Qué hace el Portal con ellas:
  `../../Visualizador Web/portal/docs/llevar-cotizacion.md`.

- Cada tarjeta de producto, cada fila de la tabla de compras y cada
  tarjeta de la vista sin agrupar tienen el mismo bloque cantidad (−/+) +
  "Agregar" (`renderAgregar`), atendido por **un solo listener delegado**
  sobre `document` (`addToCart`) — ya no hay que volver a enlazar botones
  después de cada render. Si la referencia ya está en el carrito
  (`cartKey`, indexado por `it._idx`, la posición en `DATA.items`), la
  cantidad se suma a la existente en vez de duplicar la línea, y junto al
  botón aparece "✓ N en la cotización" (`actualizarMarcasCarrito`). Cada
  línea guarda también su `hoja` y su proveedor, usados por la exportación
  y el panel.
- Al agregar, un aviso abajo ("Agregado: … × N · Ver cotización",
  `mostrarToast`) confirma qué entró y lleva al panel. El botón vuelve a su
  texto original ("Agregar el más barato" o "Agregar") — antes volvía
  siempre a "Agregar al cotizador", aunque dijera otra cosa.
- El botón flotante (círculo 🧾 con el número de unidades) abre el panel.
  Es un círculo compacto a propósito: como pastilla con texto tapaba el
  "Agregar" del borde derecho en pantallas de 1366px.
- El panel (`renderCart`) es un **diálogo modal**: fondo oscurecido que lo
  cierra al tocarlo, Escape para cerrar, foco atrapado adentro y devuelto al
  botón al cerrar. Muestra una línea por ítem con cantidad (−/+), proveedor,
  fecha, subtotal y quitar (`removeFromCart`); "Vaciar" (con confirmación);
  y el total c/IVA destacado con el neto s/IVA y las unidades.

## Exportación a Excel — textarea + "Copiar todo" (no es descarga de archivo)

El mecanismo es un `<textarea>` de solo lectura dentro del drawer del
carrito que se actualiza en vivo en cada cambio del carrito (cada llamada
a `renderCart()` reconstruye su contenido llamando a
`construirTextoExport()`), más un botón "Copiar tabla para Excel" que copia ese texto
al portapapeles (`navigator.clipboard.writeText`, con fallback a
`document.execCommand('copy')` sobre el propio textarea si el navegador no
soporta la API moderna) — **no hay descarga de archivo en ningún punto de
este flujo** (los Artifacts de Claude solo permiten descargar extensiones
de un allowlist que no incluye `.xlsx`/`.csv`; ver `HISTORIA.md` para el
porqué completo de este diseño).

La tabla copiable es comparativa de mercado: una fila por línea del
carrito, con columnas `Elemento` (la `hoja`, ej. "Codo de Bronce 1
1/2\""), `Promedio de costo`, `Costo más barato`, `Proveedor más barato`
(los tres desde `MARKET_STATS[hoja]`, es decir contra **todas** las
compras históricas de esa hoja exacta, no solo las que trajo la búsqueda
que la agregó al carrito) y `Costo actualizado según UF` (el precio
reajustado de la compra específica que el usuario eligió agregar — puede
diferir del "costo más barato" si el usuario agregó una referencia que no
es la más económica). La fecha de generación y la UF utilizada se muestran
aparte, en `#exportMeta` (fuera de la caja de copia), para que la caja de
copia sea solo la tabla que se pega en Excel.

## Fuera de alcance de esta versión

- Consultor IA en lenguaje natural sobre los datos del índice (opcional
  según el doc maestro, no implementado).
- Persistencia del carrito entre sesiones o recargas — rechazada
  explícitamente por el usuario (ver "Carrito de cotización" arriba).
- Un archivo `.xlsx` real descargable — bloqueado hoy por el allowlist de
  `downloads`, y en cualquier caso superado por la decisión de copiar/
  pegar en vez de descargar (ver "Exportación a Excel" arriba e
  [`HISTORIA.md`](../Visualizador%20Web/HISTORIA.md)).
