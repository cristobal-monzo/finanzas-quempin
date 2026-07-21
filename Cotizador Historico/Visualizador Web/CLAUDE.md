# CLAUDE.md — Visualizador Web de Cotizador Historico

Contenido a presentar en el HTML del visualizador de **Cotizador
Historico**. Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de
datos, hosting) — este archivo solo cubre el contenido específico de este
módulo. Ver también [`../CLAUDE.md`](../CLAUDE.md) para el detalle completo
de la lógica de búsqueda difusa y reajuste por UF que este visualizador
expone.

**Estado: implementación real (2026-07-20, ampliada 2026-07-21).** Este
archivo documenta lo que efectivamente se construyó — no un borrador de
contenido a definir.

Diseño original completo:
[`../docs/superpowers/specs/2026-07-20-visualizador-cotizador-historico-design.md`](../docs/superpowers/specs/2026-07-20-visualizador-cotizador-historico-design.md).
**Su sección "Exportación" quedó superada mid-implementación** (ver más
abajo, "Exportación a Excel") — este `CLAUDE.md` es la fuente de verdad
sobre qué se exporta y cómo, no ese spec.

## Estructura del módulo

```
Cotizador Historico/Visualizador Web/
├── CLAUDE.md               # este archivo
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
corregido — es la misma clase de imprecisión heurística ya documentada, el
chip erróneo no oculta la descripción completa, que sigue visible debajo.

## Taxonomía y explorador de carpetas (2026-07-21)

El gráfico de Top 10 y la tabla plana "Índice de productos" de la versión
2026-07-20 se **eliminaron** (pedido explícito del usuario) y se
reemplazaron por un explorador de carpetas de 3 niveles — **Categoría →
Subcategoría → Hoja** — que reemplaza la sección "Índice de productos".

- `clasificarItem(item)` — heurística por palabras clave (mismo criterio
  best-effort que `extraerSpecs`) que asigna a cada ítem: `categoria`
  (dominio, ej. "Piping Bronce", "Herramientas Eléctricas", "Otros /
  Servicios" como categoría de respaldo), `material` (Cobre/Bronce/
  Galvanizado/Inoxidable/PPR, detectado por palabra clave en nombre+
  descripción), `medida` (misma extracción que antes usaba solo
  `extraerMedidaFitting`, ahora generalizada a `extraerMedida` — pulgadas
  con fracción mixta, mm, cm), y las banderas `requiereMaterial`/
  `requiereMedida` que gatillan la regla de visibilidad de abajo.
- **`limpiarGenericoDeMaterial`**: el campo "Nombre Ítem" del Excel a veces
  ya trae el material incluido (ej. "Codo bronce", pese a que la
  convención documentada en `../CLAUDE.md` pide que sea genérico sin
  material) — sin esta limpieza, la subcarpeta terminaba diciendo "Codo
  bronces de Bronce" (duplicado). Se le quita la palabra de material
  detectada antes de construir subcategoría/hoja.
- `subcategoriaDe`/`hojaDe` construyen las etiquetas de carpeta: la
  subcategoría es la **primera palabra** del genérico, pluralizada (+ " de
  <Material>" si aplica, ej. "Codos de Bronce", "Llaves", "Destornilladores")
  — usar el nombre completo como subcategoría fue el primer intento
  (2026-07-21) y fragmentaba cada variante en su propia carpeta de 1 ítem
  (ej. "Destornillador p/electricista PH1x80mm" y "Destornillador PL
  1000V 4x100mm" quedaban en subcarpetas distintas en vez de agruparse en
  "Destornilladores"; "Llave francesa"/"Llave ajustable"/"Llave inglesa"
  no se agrupaban en "Llaves") — corregido el mismo día tras que el
  usuario lo detectara con datos reales. La hoja usa el genérico completo
  (no solo la primera palabra) + material/medida, evitando duplicar el
  material o la medida si ya están contenidos en el nombre (`contieneTexto`).
  `pluralizar` es un heurístico simple (vocal final → +s, consonante →
  +es) — no maneja plurales irregulares del español perfectamente (ej.
  "Setes" en vez de "Sets", "Unión americanas" en vez de "Uniones
  americanas"), aceptado como limitación conocida de una heurística, no
  un bug a perseguir.
- **Regla de visibilidad ampliada** (antes solo cubría "fittings" por
  nombre): tuberías/fittings (`GRUPOS_PIPING`) exigen **medida Y
  material** — sin material no hay categoría de piping a la que asignarlo,
  así que el ítem queda fuera del dashboard completo (no solo oculto)
  hasta que se corrija el dato de origen. Pernos/tornillos/remaches/
  autoperforantes/soldadura/fundente/electrodos (`GRUPOS_CONSUMIBLE_MEDIDA`)
  exigen solo medida. El resto de las categorías no exige nada. Pedido
  explícito del usuario: "una cañería de cobre de 1/2 no es lo mismo que
  una de 2".
- `buildLeafIndex`/`MARKET_STATS` agrupan por **hoja** (no por
  `nombre_item` crudo) — dos codos de bronce de distinta medida nunca se
  promedian/comparan como si fueran el mismo producto. Cada hoja trae
  `n_compras`, `promedio_con_iva`, `precio_min_con_iva`,
  `proveedor_min_con_iva` (con IVA, porque es lo que ve el comprador final
  — el rango sin IVA de una versión anterior ya no se usa para esta
  comparación).
- `buildCategoryTree` arma el árbol navegable; el estado de navegación
  (`folderState.categoria/subcategoria/hoja`) se renderiza con
  `renderFolderBrowser` + `renderBreadcrumb` sobre `#folderBrowser`/
  `#folderBreadcrumb`. Abrir una hoja muestra el resumen agregado
  (promedio, más barato + proveedor) y reutiliza `renderRefCard` para cada
  compra individual de esa hoja — incluyendo el "Agregar al cotizador" de
  cada una.
- **Iconos por categoría** (`ICONOS_CATEGORIA`) — un emoji plano por
  categoría, reutilizado entre categorías de piping similares con solo el
  color/tono cambiando (🟠 Cobre, 🟡 Bronce, ⚪ Inoxidable, ⚙️ Galvanizado),
  para no inventar un ícono nuevo por cada combinación material/categoría.
- **Destacado de proveedor más barato**: en cualquier tarjeta de
  referencia (`renderRefCard`), si su hoja tiene más de una compra y esta
  tarjeta es la de menor precio con IVA, se le agrega la clase
  `is-cheapest` + una insignia "💲 Proveedor más barato entre N" — visible
  tanto en resultados de búsqueda como dentro del detalle de una hoja.
- **Buscador dual**: `buscarCarpetas(texto)` busca el texto contra los
  nombres de categoría/subcategoría del árbol (no contra hojas
  individuales, que ya cubre la búsqueda normal de ítems) y se muestra en
  una sección aparte ("📁 Categorías encontradas", `#searchFolderMatches`)
  con ícono de carpeta, claramente separada de "Referencias encontradas" —
  para que el usuario distinga si el resultado es una carpeta para
  explorar o un ítem específico.

## Orden del dashboard (2026-07-21)

El buscador (con sus filtros) se movió a la parte superior del panel,
justo debajo del KPI row — antes estaba después de la tabla/gráfico
eliminados. El explorador de carpetas quedó como herramienta secundaria de
navegación, debajo de los resultados de búsqueda.

## Carrito de cotización — garantía de no-persistencia

El carrito vive **solo en una variable JS en memoria** (`var cart = []`,
comentario explícito en `template.html`: "carrito (solo en memoria --
nunca localStorage/sessionStorage)"). Recargar la página lo vacía por
completo. Esto es un requisito no negociable del usuario, no un descuido:
a diferencia del tema visual (que sí usa `localStorage`) o del estado de
"gate desbloqueado" (que usa `sessionStorage`), el contenido del carrito
nunca se escribe en ningún almacenamiento del navegador.

- Cada tarjeta de resultado tiene un stepper de cantidad + botón "Agregar
  al cotizador" (`bindCartButtons`/`addToCart`; texto del botón cambiado
  desde "Agregar al carrito" el 2026-07-21, pedido del usuario) — si la
  referencia ya está en el carrito (`cartKey`, indexado por posición en
  `DATA.items`), la cantidad se suma a la existente en vez de duplicar la
  línea. Cada línea guarda también su `hoja` (ver taxonomía arriba), usada
  por la exportación.
- El botón flotante que abre el panel usa el ícono 🧾 (recibo) en vez de
  🛒 (pedido del usuario, 2026-07-21) — el título del panel ("Carrito de
  cotización") no cambió, solo el ícono y el texto del botón de agregar.
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
este flujo.**

**Formato de la tabla copiable (rediseñado 2026-07-21, pedido del
usuario)**: ya no son secciones Materiales/Equipos/Otros con cantidad y
subtotal — es una tabla comparativa de mercado, una fila por línea del
carrito, con columnas `Elemento` (la `hoja`, ej. "Codo de Bronce 1
1/2\""), `Promedio de costo`, `Costo más barato`, `Proveedor más barato`
(los tres desde `MARKET_STATS[hoja]`, es decir contra **todas** las
compras históricas de esa hoja exacta, no solo las que trajo la búsqueda
que la agregó al carrito) y `Costo actualizado según UF` (el precio
reajustado de la compra específica que el usuario eligió agregar — puede
diferir del "costo más barato" si el usuario agregó una referencia que no
es la más económica). La fecha de generación y la UF utilizada **ya no
van dentro del texto copiable** — se muestran aparte, en `#exportMeta`
(fuera de la caja de copia), pedido explícito del usuario para que la caja
sea solo la tabla que se pega en Excel.

### Por qué no es una descarga de archivo

El diseño original (ver spec, sección "Exportación") sí contemplaba
descargar un archivo — primero se evaluó `.xlsx`/`.csv` vía la capability
`downloads` de los Artifacts de Claude, pero esa capability solo acepta
`gif png jpg jpeg webp mp4 webm txt json md` (`window.claude.downloads.save()`
rechaza cualquier otra extensión); el diseño bajó entonces a un archivo
`.txt` con columnas separadas por tabulador, abrible en Excel renombrando
la extensión o vía "Archivo > Abrir". **Mid-implementación (2026-07-20),
el usuario revisó el plan y pidió cambiar el mecanismo**: en vez de
descargar cualquier archivo, un textarea que siempre muestra el texto
actual del carrito más un botón para copiarlo al portapapeles. Esto evita
por completo el allowlist de extensiones de `downloads` (ya no aplica) y
es más simple de implementar: no hay que declarar ninguna capability al
publicar el Artifact, ni distinguir el caso "dentro del sandbox del
Artifact" del caso "abierto localmente fuera de un Artifact". Ver
`../docs/superpowers/plans/2026-07-20-visualizador-cotizador-historico.md`,
sección "Task 8", para el registro completo de ese cambio de decisión.

## Publicación

Mismo mecanismo que Centro de Costos: publicar `build/index.html` como
Claude Artifact privado, actualizando siempre el mismo link en corridas
sucesivas (registrar el link en el `MEMORY.md` del skill
`Cotizador_Historico` una vez publicado por primera vez). El punto abierto
de control de acceso del doc maestro (`../../Visualizador Web/CLAUDE.md`)
sigue sin resolverse — el gate de contraseña es una barrera débil, no
seguridad real.

## Fuera de alcance de esta versión

- Consultor IA en lenguaje natural sobre los datos del índice (opcional
  según el doc maestro, no implementado).
- Persistencia del carrito entre sesiones o recargas — rechazada
  explícitamente por el usuario (ver "Carrito de cotización" arriba).
- Un archivo `.xlsx` real descargable — bloqueado hoy por el allowlist de
  `downloads`, y en cualquier caso superado por la decisión de copiar/
  pegar en vez de descargar (ver "Exportación a Excel" arriba).
