# CLAUDE.md — Visualizador Web de Cotizador Historico

Contenido a presentar en el HTML del visualizador de **Cotizador
Historico**. Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de
datos, hosting) — este archivo solo cubre el contenido específico de este
módulo. Ver también [`../CLAUDE.md`](../CLAUDE.md) para el detalle completo
de la lógica de búsqueda difusa y reajuste por UF que este visualizador
expone.

**Estado: implementado.** Este archivo documenta el estado actual — qué se
construyó y cómo funciona hoy, no un borrador ni un changelog. Para el
recorrido de cómo se llegó acá (decisiones revertidas, bugs encontrados con
datos reales, versiones anteriores) ver [`HISTORIA.md`](HISTORIA.md); solo
hace falta abrirlo para entender el origen de una regla puntual, no para
trabajar en el módulo día a día.

Diseño original: [`../docs/superpowers/specs/2026-07-20-visualizador-cotizador-historico-design.md`](../docs/superpowers/specs/2026-07-20-visualizador-cotizador-historico-design.md)
— su sección "Exportación" quedó superada (ver `HISTORIA.md`); este
`CLAUDE.md` es la fuente de verdad sobre qué se exporta y cómo.

## Estructura del módulo

```
Cotizador Historico/Visualizador Web/
├── CLAUDE.md               # este archivo
├── HISTORIA.md             # changelog/decisiones — no hace falta para el día a día
├── template.html           # estructura/CSS/JS de pantalla + logo, SIN datos — versionado
├── busqueda.js             # motor de búsqueda del navegador — COMPARTIDO con Perú, versionado
├── build_visualizador.py   # export + build (inyecta busqueda.js) — versionado
├── data/                    # snapshot intermedio (cotizador-historico.json) — gitignored
└── build/                   # index.html final, autocontenido — gitignored
```

`data/` y `build/` están excluidos vía las reglas genéricas
`*/Visualizador Web/data/` y `*/Visualizador Web/build/` del `.gitignore`
raíz (mismo patrón que Centro de Costos) — ambos se regeneran completos en
cada corrida, nunca editar nada dentro a mano.

## Un solo comando regenera todo

```
python driver.py visualizador
```

desde `.claude/skills/Cotizador_Historico/` (o directamente `python
"Visualizador Web/build_visualizador.py"` desde la raíz del módulo). El
comando `visualizador` de `driver.py` (`cmd_visualizador`) solo agrega
`Visualizador Web/` a `sys.path` e invoca `build_visualizador.build()` —
misma idea que el `driver.py visualizador` de Centro de Costos.

`build_visualizador.py`:
1. Lee `Centro de Costos/Excel/Centro de Costos.xlsx` (hojas `Detalle` +
   `Master`) vía `Sistema/cotizador_historico.py::cargar_items_detalle` —
   **solo lectura**, este módulo nunca escribe ese archivo.
2. Pide la UF de hoy **una sola vez** (`consultar_uf_api`) y reajusta todo
   el índice contra ese valor (`reajustar_todos`) — nunca una llamada de
   UF por ítem.
3. Escribe el snapshot saneado en `data/cotizador-historico.json`
   (auditable, formato legible).
4. Incrusta ese mismo JSON en base64 dentro de `template.html` (reemplazo
   del placeholder `__CH_DATA_B64__`) **y el motor de búsqueda compartido**
   (`busqueda.js` en el placeholder `__CH_BUSQUEDA_JS__`) para producir
   `build/index.html` — un solo archivo autocontenido, sin servidor, sin
   llamadas de red en tiempo de uso.

Volver a generar el visualizador con documentos nuevos ya registrados en
Centro de Costos, o simplemente para refrescar la UF del día, es correr
este mismo comando otra vez y republicar (ver "Publicación" abajo) — nunca
se toca `template.html` a mano para eso.

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
2026-08-20, ver `../CLAUDE.md` § Precauciones para el mecanismo completo):
`build_visualizador.py` acepta `uf_manual`/`fuente_manual` (el driver los
expone como `--uf-manual`/`--uf-fuente`), un valor que el agente busca en
internet solo cuando mindicador.cl falla — mindicador.cl sigue siendo la
fuente prioritaria. Cuando se usa ese fallback, el snapshot trae
`"uf_fuente"` con el texto de la fuente (en vez de `"mindicador.cl"`) y el
header/KPI/pie de exportación del visualizador le agregan el sufijo
"· fuente: &lt;texto&gt;" junto a "UF utilizada" (`ufFuenteSufijo()` en
`template.html`) — transparencia obligatoria: quien vea el dashboard debe
poder distinguir un valor manual de uno de mindicador.cl.

## Branding y gate — reutilizados de Centro de Costos

- Mismos 4 colores oficiales del manual de marca QUEMPIN, verificados en
  `template.html`: `#ff5100` (Pantone Orange 021 C), `#000000` (Black C),
  `#98989a` (Cool Gray 7 C), `#54565a` (Cool Gray 11 C).
- Misma tipografía Lato (manual QUEMPIN §13), embebida sin depender de un
  CDN.
- Mismo gate de contraseña: constante `GATE_PASSWORD_NORM = 'combustion'`
  en `template.html`, comparada tras normalizar el input (minúsculas, sin
  tilde) — mismo disclaimer de "no es seguridad real" que Centro de Costos.
  El estado de "ya desbloqueado" se guarda en `sessionStorage`
  (`ch_viz_unlocked`) y la preferencia de tema claro/oscuro en
  `localStorage` (`ch_viz_theme`) — ambos persisten intencionalmente
  (sesión y dispositivo respectivamente) y son casos distintos de la regla
  de no-persistencia del carrito, ver abajo.

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
en [`../CLAUDE.md`](../CLAUDE.md) § Búsqueda.

**Lo que había antes** (y por qué se cambió): ~60 líneas de JavaScript en
este template —`normalizeText`, `diceCoefficient`, `similitud`,
`buscarItems`— que devolvían `1.0` en cuanto el ítem compartía una palabra
de 4 letras con la consulta. Sobre el catálogo real eso dejaba 41 válvulas
empatadas y el orden lo decidía el Excel. Estaban además duplicadas en el
template de Perú, el mismo patrón que ya había causado la divergencia de la
taxonomía. Se eliminaron.

**Lo que sí hace este template** es la pantalla:

- Campo de búsqueda con ejemplos reales, botón de limpiar y
  **autocompletado** (`renderAutocomplete`) alimentado por `DATA.sugerencias`
  — los nombres reales del catálogo (producto, familia, categoría, marca,
  material, medida) calculados en Python, no una lista escrita a mano.
  Navegable con flechas y Enter.
- **Resultados agrupados por producto** (`agruparResultados` +
  `renderGrupoCard`): una tarjeta por hoja con su promedio, su más barato y
  su proveedor, desplegable a las compras individuales. Sin agrupar, las
  tres compras idénticas de la misma válvula ocupaban tres de los cinco
  primeros lugares.
- **Por qué apareció cada resultado** (`chipsMotivos`): chips que dicen qué
  término calzó en qué campo, con la medida destacada. Un match aproximado
  se marca "(aprox.)".
- **Resaltado por palabra** (`BUSCADOR.resaltar`): marca cada palabra que
  calzó, incluyendo plurales, sinónimos y la medida. El resaltado anterior
  buscaba la consulta completa como substring, así que en "valvula de bola
  2" no marcaba nada.
- **Filtros combinables y dependientes** (`opcionesDe`): Categoría,
  Subcategoría, Material, Medida, Marca, Proveedor, Proyecto, rango de
  fechas y rango de precio. Cada desplegable se calcula contra **lo que la
  búsqueda actual encontró** más los otros filtros, con el conteo en cada
  opción, así que nunca ofrece una combinación que da cero. Los filtros
  activos se ven como chips y se quitan de a uno o con "Limpiar todo".
- **Aviso de consulta a medias** (`#searchAviso`): si un término no existe
  en el catálogo, se dice explícitamente en vez de dejar creer que los
  resultados son lo que se pidió.
- **Estado vacío útil** (`renderEstadoVacio`): qué término falló, qué
  escribir en su lugar, un atajo para quitar los filtros y las categorías
  para explorar.
- **Historial de búsquedas** en `sessionStorage` (`ch_viz_recientes`, máximo
  8): vive lo mismo que el desbloqueo del gate y se va al cerrar la pestaña.
  No es `localStorage` a propósito — son consultas escritas por el usuario y
  no hay razón para que sobrevivan a la sesión.
- Ordenar por relevancia, precio (asc/desc) o compra más reciente.

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
[`../docs/superpowers/specs/2026-09-08-taxonomia-cotizador-design.md`](../docs/superpowers/specs/2026-09-08-taxonomia-cotizador-design.md)
y resumidas en [`../CLAUDE.md`](../CLAUDE.md) § Taxonomía.

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

## Política: ítems que el clasificador no reconoce

La página publicada **nunca** busca en internet — es un HTML estático sin
llamadas de red en tiempo de uso (mismo motivo que la UF: los Artifacts no
tienen una capability de fetch genérico). Cuando un ítem nuevo no calza
bien con las reglas de `clasificarItem` (categoría/subcategoría genérica
sin sentido, ej. un nombre de marca poco conocido), el flujo es: **en la
próxima sesión de mantención, antes de reconstruir el visualizador, buscar
en internet qué es el producto** (marca/modelo/término técnico) y ajustar
`SINONIMOS_TIPO_GENERICO`, `OVERRIDES_CATEGORIA`, o los `GRUPOS_*`
correspondientes según lo que se descubra — no es una función del HTML
publicado, es un paso manual de mantenimiento del clasificador.

## Reglas de clasificación (orden de prioridad de `clasificarItem`)

Cada paso solo se evalúa si el anterior no calzó:

1. **`OVERRIDES_CATEGORIA`** — excepciones de nombre completo a categoría
   (y opcionalmente subcategoría forzada): "adaptador broca" → Herramientas
   Manuales (no Consumibles, aunque contenga "broca"); "bolso" →
   Herramientas Manuales, subcategoría forzada "Contenedores";
   "ferreteria"/"ferretería" → Herramientas Manuales, subcategoría forzada
   "Materiales de Ferretería".
2. Todo lo que diga inox/inoxidable va a "Piping Inoxidable", **salvo que
   sea una herramienta** (`GRUPOS_HERRAMIENTA` = eléctricas + manuales) **o
   un instrumento de medición** (`GRUPOS_INSTRUMENTACION`, excepción
   agregada 2026-08-31 — ver paso 5b) — tiene prioridad incluso sobre
   Válvulas y Control/Bombas. Requiere medida igual que el resto de piping.
   La excepción de instrumentación corrigió un bug real encontrado al
   agregar esa categoría: 2× "Manometro glic. ... inox." y 1×
   "Manovacuómetro ... caja inox" caían en Piping Inoxidable solo por
   mencionar el material de su caja, no por ser piping.
3. `GRUPOS_PIPING` (cobre/bronce/galvanizado/PPR — el inoxidable ya se
   interceptó en el paso 2). Incluye "tubería"/"tapagorro" desde 2026-08-19
   — antes solo estaban ahí los accesorios (codo, tee, copla, etc.) y las
   tuberías/tapagorros PPR reales caían en el catch-all "Otros / Servicios"
   en vez de "Piping PPR" (bug real, no solo cobertura nueva).
4. **`GRUPOS_SOLDADURA`** ("Soldadura" 🔥): gas MAPP, soldadura, fundente,
   electrodos, varillas — no exige medida.
5. Válvulas y Control (incluye "alimat" — una válvula de llenado
   automático con manómetro incorporado, así que items como "Alimat 1/2"
   con manómetro intermedio" quedan aquí y no en Instrumentación, evaluados
   en este paso antes de llegar al 5b), Herramientas Eléctricas,
   Herramientas Manuales (incluye huincha, cortatubos/corta tubos,
   cuchillo, calafatera, dado, remachadora — evaluada antes que "remache"
   la capture como consumible, porque la contiene como substring).
5b. **`GRUPOS_INSTRUMENTACION`** ("Instrumentación" 🌡️, agregada
   2026-08-31, pedido explícito del usuario): manómetro, vacuómetro,
   termocupla, termopar, termómetro, multímetro, caudalímetro, sonda,
   medidor, indicador — instrumentos de medición, agrupados aparte de la
   categoría del equipo que miden (antes un manómetro cría bajo "Válvulas y
   Control" y un vacuómetro bajo "Bombas y Equipos Mecánicos", solo porque
   compartían grupo de palabras clave con esos equipos). "manómetro" salió
   de `GRUPOS_VALVULA`, "vacuómetro" de `GRUPOS_BOMBA`, y "termocupla"/
   "sonda" de `GRUPOS_CALEFACCION` (ver paso 8) para venir aquí. Evaluado
   **después** de Válvulas y Control (paso 5, para que "Alimat ... con
   manómetro" siga siendo una válvula) y **antes** de Bombas/Calefacción
   (para que "Sonda ST07-H Caldera Ivar" caiga aquí y no en Calefacción por
   la palabra "Caldera"). "medidor"/"indicador" son deliberadamente
   genéricos (pedido explícito del usuario, riesgo aceptado de que algo
   no-instrumento los contenga a futuro). Ícono repetido con "Calefacción y
   Control" (🌡️) — decisión explícita del usuario pese a la duplicidad
   visual; ya hay precedente de ícono compartido entre dos categorías
   (⚙️ en Bombas y en Piping Acero Galvanizado).
6. Bombas y Equipos Mecánicos (el vacuómetro ya se interceptó en el paso
   5b).
7. **`GRUPOS_MATERIALES_ELECTRICOS`** ("Materiales Eléctricos" ⚡):
   "conduit" (casi cualquier ítem que diga conduit es eléctrico),
   "eléctrico".
8. **`GRUPOS_QUIMICOS`** ("Productos Químicos" 🧪): Solutech,
   tapagotera(s).
9. **`GRUPOS_CALEFACCION`** ("Calefacción y Control" 🌡️, agregada
   2026-08-19): presostato, termostato, contactor, caldera, radiador —
   cluster real de 8 ítems, evaluada antes que Transporte para no perder
   items que además dijeran algo transportable. "termocupla"/"sonda"
   salieron de aquí el 2026-08-31 hacia `GRUPOS_INSTRUMENTACION` (paso 5b)
   — son sensores de medición, no equipos de control de calefacción en sí.
10. **`GRUPOS_TRANSPORTE`** ("Transporte" 🚚): flete, arriendo, peaje,
   combustible/gasolina/bencina/petróleo/diesel/parafina, pasaje, equipaje,
   transporte, estacionamiento, despacho, envío, encomienda, embarque
   (estas últimas seis agregadas 2026-08-19 — la categoría ya existía y el
   dato crudo de Centro de Costos ya los marcaba como Transporte/Despachos,
   pero al clasificador le faltaban las palabras). La subcategoría la
   decide `subcategoriaTransporte`: Combustible (agrupa el ítem del
   combustible con su impuesto específico asociado), Peajes, Arriendo de
   Vehículos, Pasajes y Equipaje, Despachos y Fletes (flete/despacho/envío/
   encomienda), Estacionamiento, o "Otros Gastos de Transporte" (incluye
   "embarque", sin subcategoría propia).
11. **`GRUPOS_ALIMENTOS`** ("Alimentos" 🍽️, agregada 2026-08-19): toda la
    comida/bebida en una sola categoría — sandwich, café, muffin, agua
    (con espacio final para no matchear "aguarrás"), leche, bebida,
    colación, Red Bull, alimentación, ingrediente, almuerzo, desayuno,
    restaurant(e), supermercado, panadería. Antes repartida sin estructura
    propia entre las etiquetas manuales `Alimentación`/`Viáticos-
    Alojamiento` del Excel de Centro de Costos.
12. Consumibles con medida obligatoria (pernos, tornillos, remaches,
    autoperforantes, brocas) y sin medida (esmalte, pintura, rodillo,
    brocha, aguarrás, espuma, cinta, lubricante, bolsas, libros,
    marcadores).
13. Seguridad (EPP, incluye "overol", y desde 2026-08-19 cofia, cubre
    calzado, visor, plantilla, desinfectante).
14. "Otros / Servicios" como categoría de respaldo final.

## Carrito de cotización — garantía de no-persistencia

El carrito vive **solo en una variable JS en memoria** (`var cart = []`,
comentario explícito en `template.html`: "carrito (solo en memoria --
nunca localStorage/sessionStorage)"). Recargar la página lo vacía por
completo. Esto es un requisito no negociable del usuario, no un descuido:
a diferencia del tema visual (que sí usa `localStorage`) o del estado de
"gate desbloqueado" (que usa `sessionStorage`), el contenido del carrito
nunca se escribe en ningún almacenamiento del navegador.

- Cada tarjeta de resultado tiene un stepper de cantidad + botón "Agregar
  al cotizador" (`bindCartButtons`/`addToCart`) — si la referencia ya está
  en el carrito (`cartKey`, indexado por posición en `DATA.items`), la
  cantidad se suma a la existente en vez de duplicar la línea. Cada línea
  guarda también su `hoja` (ver taxonomía arriba), usada por la
  exportación.
- El botón flotante que abre el panel usa el ícono 🧾 (recibo).
- El panel lateral (drawer) del carrito (`renderCart`) muestra una línea
  por ítem con cantidad editable, subtotal, botón de quitar
  (`removeFromCart`), y el total general con y sin IVA.

## Exportación a Excel — textarea + "Copiar todo" (no es descarga de archivo)

El mecanismo es un `<textarea>` de solo lectura dentro del drawer del
carrito que se actualiza en vivo en cada cambio del carrito (cada llamada
a `renderCart()` reconstruye su contenido llamando a
`construirTextoExport()`), más un botón "Copiar todo" que copia ese texto
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

## Publicación

Mismo mecanismo que Centro de Costos: GitHub Pages, único canal desde la
migración del 2026-08-05 — el Claude Artifact privado que se usaba antes ya
no se actualiza (pedido explícito del usuario, 2026-08-19). Receta y
comandos exactos en [`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
§ Hosting; URL fija:
`https://cristobal-monzo.github.io/finanzas-quempin/cotizador-historico/`.
El punto de control de acceso quedó resuelto en esa misma migración (repo
público + el mismo gate de contraseña, ver § "Punto de control de acceso"
del doc maestro) — el gate sigue siendo una barrera débil, no seguridad
real.

## Fuera de alcance de esta versión

- Consultor IA en lenguaje natural sobre los datos del índice (opcional
  según el doc maestro, no implementado).
- Persistencia del carrito entre sesiones o recargas — rechazada
  explícitamente por el usuario (ver "Carrito de cotización" arriba).
- Un archivo `.xlsx` real descargable — bloqueado hoy por el allowlist de
  `downloads`, y en cualquier caso superado por la decisión de copiar/
  pegar en vez de descargar (ver "Exportación a Excel" arriba e
  `HISTORIA.md`).
