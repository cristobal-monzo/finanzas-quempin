# CLAUDE.md — Visualizador Web de Cotizador Historico

Contenido a presentar en el HTML del visualizador de **Cotizador
Historico**. Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de
datos, hosting) — este archivo solo cubre el contenido específico de este
módulo. Ver también [`../CLAUDE.md`](../CLAUDE.md) para el detalle completo
de la lógica de búsqueda difusa y reajuste por UF que este visualizador
expone.

**Estado: implementación real (2026-07-20).** Este archivo documenta lo que
efectivamente se construyó — no un borrador de contenido a definir.

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
  combinantes), igual criterio que `normalizar_texto` en Python.
- `similitud` — match 1.0 si la consulta es substring del nombre/
  descripción (o viceversa), o si alguna palabra de ≥4 caracteres de la
  consulta calza como substring; si no hay match directo, cae a un
  coeficiente de Dice sobre bigramas como aproximación tolerante a typos
  (no es idéntico al `SequenceMatcher` de Python, solo sirve para generar
  sugerencias de baja similitud, igual que hace el CLI).
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

## Gráfico y tabla

- `renderBarChart` dibuja un gráfico de barras SVG hecho a mano (sin
  librería externa, mismo criterio de "sin fetch" que el resto de la
  página) para el Top 10 de productos con más compras históricas
  (`renderTopProductosChart`, ordena `PRODUCT_INDEX` por `n_compras`).
- `renderProductTable` construye una tabla ordenable por columna sobre
  `PRODUCT_INDEX` (un ítem indexado agregado por `nombre_item`).

## Carrito de cotización — garantía de no-persistencia

El carrito vive **solo en una variable JS en memoria** (`var cart = []`,
comentario explícito en `template.html`: "carrito (solo en memoria --
nunca localStorage/sessionStorage)"). Recargar la página lo vacía por
completo. Esto es un requisito no negociable del usuario, no un descuido:
a diferencia del tema visual (que sí usa `localStorage`) o del estado de
"gate desbloqueado" (que usa `sessionStorage`), el contenido del carrito
nunca se escribe en ningún almacenamiento del navegador.

- Cada tarjeta de resultado tiene un stepper de cantidad + botón "Agregar
  al carrito" (`bindCartButtons`/`addToCart`); si la referencia ya está en
  el carrito (`cartKey`, indexado por posición en `DATA.items`), la
  cantidad se suma a la existente en vez de duplicar la línea.
- El panel lateral (drawer) del carrito (`renderCart`) muestra una línea
  por ítem con cantidad editable, subtotal, botón de quitar
  (`removeFromCart`), y el total general con y sin IVA.

## Exportación a Excel — textarea + "Copiar todo" (no es descarga de archivo)

El mecanismo real que se implementó es un `<textarea>` de solo lectura
dentro del drawer del carrito que se actualiza en vivo en cada cambio del
carrito (cada llamada a `renderCart()` reconstruye su contenido llamando a
`construirTextoExport()`), más un botón "Copiar todo" que copia ese texto
al portapapeles (`navigator.clipboard.writeText`, con fallback a
`document.execCommand('copy')` sobre el propio textarea si el navegador no
soporta la API moderna) — **no hay descarga de archivo en ningún punto de
este flujo.**

`construirTextoExport()` agrupa las líneas del carrito en tres secciones,
en este orden, cada una con su propio encabezado de columnas separado por
tabulador y su subtotal: **MATERIALES**, **EQUIPOS**, **OTROS**. El mapeo
(`seccionParaCategoria`) es: `"Materiales"` → MATERIALES,
`"Equipos-Herramientas"` → EQUIPOS, cualquier otro valor de
`categoria_item` (o ausencia de categoría) → OTROS — ninguna línea del
carrito queda fuera. El texto incluye encabezado con fecha de generación y
la UF utilizada (la misma fijada en el build), y termina con un
`TOTAL GENERAL`. Al pegar en Excel/Sheets, los tabs hacen que cada columna
caiga en su propia celda.

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
