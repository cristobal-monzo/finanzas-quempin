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
├── template.html           # estructura/CSS/JS + logo, SIN datos — versionado
├── build_visualizador.py   # export + build — versionado
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
   del placeholder `__CH_DATA_B64__`) para producir `build/index.html` —
   un solo archivo autocontenido, sin servidor, sin llamadas de red en
   tiempo de uso.

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

## Búsqueda difusa y extracción de specs

La búsqueda ocurre **100% en el navegador** contra el índice ya
precalculado incrustado en el HTML — no hay ninguna llamada de red en
tiempo de uso. `template.html` porta a JS la lógica de
`Sistema/cotizador_historico.py`:

- `normalizeText` — minúsculas, sin tildes (Unicode NFD + strip de marcas
  combinantes); el Python original usa NFKD (`normalizar_texto`) — son
  formas de normalización distintas, pero coinciden en el resultado para
  los acentos españoles simples que efectivamente aparecen en estos datos.
- `similitud` — match 1.0 si la consulta es substring del nombre/
  descripción (o viceversa), o si alguna palabra de ≥4 caracteres del
  nombre/descripción del ítem calza como substring de la consulta (o
  viceversa); si no hay match directo, cae a un coeficiente de Dice sobre
  bigramas como aproximación tolerante a typos (no es idéntico al
  `SequenceMatcher` de Python, solo sirve para generar sugerencias de baja
  similitud, igual que hace el CLI).
- `buscarItems` — aplica `similitud` contra `nombre_item` y `descripcion`
  de cada ítem del índice, filtra por umbral (`UMBRAL_SIMILITUD = 0.6`) y
  devuelve hasta 5 sugerencias (`UMBRAL_SUGERENCIA = 0.4`) cuando no hay
  coincidencia directa.

Además, cada tarjeta de resultado extrae, a partir del texto libre de
`descripcion`, chips de specs técnicas y marca/modelo:

- `extraerSpecs` — un set de expresiones regulares (`PATRONES_SPECS`)
  reconoce potencia (HP/CV/kW/W), caudal (L/min, GPM, m³/h), voltaje (V),
  presión (bar/psi), capacidad (L/kg/gal) y dimensión (mm/cm/pulgadas).
- `extraerMarcaModelo` — heurística por posición y forma de palabra
  (primera palabra capitalizada tras el inicio, que no sea una preposición
  común, se toma como marca; el siguiente token alfanumérico mixto
  adyacente se toma como modelo).

Ambos son **best-effort**: si el parser no reconoce nada en una
descripción dada, no se fuerza ningún chip — la descripción completa
siempre queda visible como respaldo, nunca se oculta información detrás de
un chip que no se pudo extraer.

**Limitación conocida de `extraerMarcaModelo`**: al ser "primera palabra
capitalizada que no sea preposición común", ocasionalmente confunde una
palabra capitalizada por estar después de un punto (ej. "Precio" al inicio
de una frase nueva dentro de la descripción) con una marca real. No se ha
corregido — el chip erróneo no oculta la descripción completa, que sigue
visible debajo.

## Taxonomía y explorador de carpetas

El dashboard organiza el catálogo en un explorador de carpetas de 3
niveles — **Categoría → Subcategoría → Hoja** — en vez de una tabla plana o
un ranking Top N.

- `clasificarItem(item)` — heurística por palabras clave que asigna a cada
  ítem: `categoria` (dominio, ej. "Piping Bronce", "Herramientas
  Eléctricas", "Otros / Servicios" como categoría de respaldo), `material`
  (Cobre/Bronce/Galvanizado/Inoxidable/PPR, detectado por palabra clave en
  nombre+descripción), `medida` (`extraerMedida` — pulgadas con fracción
  mixta, mm, cm), y las banderas `requiereMaterial`/`requiereMedida` que
  gatillan la regla de visibilidad de abajo.
- **`limpiarGenericoDeMaterial`**: el campo "Nombre Ítem" del Excel a veces
  ya trae el material incluido (ej. "Codo bronce", pese a que la
  convención documentada en `../CLAUDE.md` pide que sea genérico sin
  material) — sin esta limpieza, la subcarpeta terminaría diciendo "Codo
  bronces de Bronce" (duplicado). Se le quita la palabra de material
  detectada antes de construir subcategoría/hoja.
- **`detectarTipoGenerico`** — busca, palabra por palabra, si el nombre (o
  si no encuentra nada ahí, la descripción) contiene alguna palabra ya
  conocida por el clasificador (`PALABRAS_TIPO_CONOCIDAS`, la unión de
  todos los `GRUPOS_*` de una sola palabra) y usa esa palabra real como
  subcategoría — fusiona automáticamente accesorios/variantes/sets con el
  tipo de producto real (ej. "Set 16 pzas destornillador precision" se une
  a "Destornilladores" en vez de generar su propia carpeta). La palabra
  detectada se normaliza con `capitalizar()` para que no queden
  subcategorías duplicadas por mayúscula/minúscula.
- `subcategoriaDe`/`hojaDe` construyen las etiquetas de carpeta: la
  subcategoría es la **primera palabra** del genérico (vía
  `detectarTipoGenerico` si aplica), pluralizada (+ " de <Material>" si
  aplica, ej. "Codos de Bronce", "Llaves", "Destornilladores"). La hoja usa
  el genérico completo (no solo la primera palabra) + material/medida,
  evitando duplicar el material o la medida si ya están contenidos en el
  nombre (`contieneTexto`). `pluralizar` es un heurístico simple (vocal
  final → +s, consonante → +es, "-ión" → "-iones") — no maneja plurales
  irregulares del español perfectamente (ej. "Setes" en vez de "Sets"),
  aceptado como limitación conocida de una heurística, no un bug a
  perseguir.
- **Regla de visibilidad**: tuberías/fittings (`GRUPOS_PIPING`, incluido
  inoxidable) exigen **medida Y material** — sin material no hay categoría
  de piping a la que asignarlo, así que el ítem queda fuera del dashboard
  completo (no solo oculto) hasta que se corrija el dato de origen.
  Pernos/tornillos/remaches/autoperforantes/brocas (`GRUPOS_CONSUMIBLE_MEDIDA`)
  exigen solo medida. El resto de las categorías no exige nada.
- `buildLeafIndex`/`MARKET_STATS` agrupan por **hoja** (no por
  `nombre_item` crudo) — dos codos de bronce de distinta medida nunca se
  promedian/comparan como si fueran el mismo producto. Cada hoja trae
  `n_compras`, `promedio_con_iva`, `precio_min_con_iva`,
  `proveedor_min_con_iva` (con IVA, porque es lo que ve el comprador
  final).
- `buildCategoryTree` arma el árbol navegable; el estado de navegación
  (`folderState.categoria/subcategoria/hoja`) se renderiza con
  `renderFolderBrowser` + `renderBreadcrumb` sobre `#folderBrowser`/
  `#folderBreadcrumb`. Abrir una hoja muestra el resumen agregado
  (promedio, más barato + proveedor) y reutiliza `renderRefCard` para cada
  compra individual de esa hoja — incluyendo el "Agregar al cotizador" de
  cada una.
- **Iconos por categoría** (`ICONOS_CATEGORIA`) — un emoji plano por
  categoría, reutilizado entre categorías de piping similares con solo el
  color/tono cambiando (🟠 Cobre, 🟡 Bronce, ⚪ Inoxidable, ⚙️ Galvanizado).
- **Destacado de proveedor más barato**: en cualquier tarjeta de
  referencia (`renderRefCard`), si su hoja tiene más de una compra y esta
  tarjeta es la de menor precio con IVA, se le agrega la clase
  `is-cheapest` + una insignia "💲 Proveedor más barato entre N" — visible
  tanto en resultados de búsqueda como dentro del detalle de una hoja.
- **Buscador dual**: `buscarCarpetas(texto)` busca el texto contra los
  nombres de categoría/subcategoría del árbol (no contra hojas
  individuales, que ya cubre la búsqueda normal de ítems) y se muestra en
  una sección aparte ("📁 Categorías encontradas", `#searchFolderMatches`)
  con ícono de carpeta, claramente separada de "Referencias encontradas".
- **Layout**: el buscador (con sus filtros) va en la parte superior del
  panel, justo debajo del KPI row; el explorador de carpetas es
  herramienta secundaria de navegación, debajo de los resultados de
  búsqueda.

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
   sea una herramienta** (`GRUPOS_HERRAMIENTA` = eléctricas + manuales) —
   tiene prioridad incluso sobre Válvulas y Control/Bombas. Requiere medida
   igual que el resto de piping.
3. `GRUPOS_PIPING` (cobre/bronce/galvanizado/PPR — el inoxidable ya se
   interceptó en el paso 2). Incluye "tubería"/"tapagorro" desde 2026-08-19
   — antes solo estaban ahí los accesorios (codo, tee, copla, etc.) y las
   tuberías/tapagorros PPR reales caían en el catch-all "Otros / Servicios"
   en vez de "Piping PPR" (bug real, no solo cobertura nueva).
4. **`GRUPOS_SOLDADURA`** ("Soldadura" 🔥): gas MAPP, soldadura, fundente,
   electrodos, varillas — no exige medida.
5. Válvulas y Control, Bombas y Equipos Mecánicos, Herramientas Eléctricas,
   Herramientas Manuales (incluye huincha, cortatubos/corta tubos,
   cuchillo, calafatera, dado, remachadora — evaluada antes que "remache"
   la capture como consumible, porque la contiene como substring).
6. **`GRUPOS_MATERIALES_ELECTRICOS`** ("Materiales Eléctricos" ⚡):
   "conduit" (casi cualquier ítem que diga conduit es eléctrico),
   "eléctrico".
7. **`GRUPOS_QUIMICOS`** ("Productos Químicos" 🧪): Solutech,
   tapagotera(s).
8. **`GRUPOS_CALEFACCION`** ("Calefacción y Control" 🌡️, agregada
   2026-08-19): presostato, termostato, termocupla, sonda, contactor,
   caldera, radiador — cluster real de 8 ítems, evaluada antes que
   Transporte para no perder items que además dijeran algo transportable.
9. **`GRUPOS_TRANSPORTE`** ("Transporte" 🚚): flete, arriendo, peaje,
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
10. **`GRUPOS_ALIMENTOS`** ("Alimentos" 🍽️, agregada 2026-08-19): toda la
    comida/bebida en una sola categoría — sandwich, café, muffin, agua
    (con espacio final para no matchear "aguarrás"), leche, bebida,
    colación, Red Bull, alimentación, ingrediente, almuerzo, desayuno,
    restaurant(e), supermercado, panadería. Antes repartida sin estructura
    propia entre las etiquetas manuales `Alimentación`/`Viáticos-
    Alojamiento` del Excel de Centro de Costos.
11. Consumibles con medida obligatoria (pernos, tornillos, remaches,
    autoperforantes, brocas) y sin medida (esmalte, pintura, rodillo,
    brocha, aguarrás, espuma, cinta, lubricante, bolsas, libros,
    marcadores).
12. Seguridad (EPP, incluye "overol", y desde 2026-08-19 cofia, cubre
    calzado, visor, plantilla, desinfectante).
13. "Otros / Servicios" como categoría de respaldo final.

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
