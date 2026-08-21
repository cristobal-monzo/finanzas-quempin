# HISTORIA — Visualizador Web de Cotizador Historico

Bitácora cronológica de cómo llegó el visualizador a su estado actual:
decisiones que se revirtieron o cambiaron mid-implementación, bugs
encontrados probando con datos reales, y ajustes puntuales ya superados por
una versión posterior. El `CLAUDE.md` de esta carpeta documenta solo el
**estado actual** — solo hace falta abrir este archivo para entender el
origen de una regla o por qué algo no se hizo de la forma "obvia", no para
trabajar en el módulo día a día. Movido acá el 2026-08-05 (auditoría de todo
el repo) porque `CLAUDE.md` había crecido a 445 líneas mezclando estado
actual con changelog fechado — mismo patrón ya aplicado en
`Centro de Costos/HISTORIA.md` y en la compresión de historial de
`Sistema Analisis Financiero/CLAUDE.md` (2026-07-27).

## 2026-07-20 — Exportación: de descarga de archivo a copiar/pegar

El diseño original (`../docs/superpowers/specs/2026-07-20-visualizador-cotizador-historico-design.md`,
sección "Exportación") contemplaba descargar un archivo. Primer intento:
`.xlsx`/`.csv` vía la capability `downloads` de los Artifacts de Claude —
pero esa capability solo acepta `gif png jpg jpeg webp mp4 webm txt json md`
(`window.claude.downloads.save()` rechaza cualquier otra extensión). El
diseño bajó entonces a un `.txt` con columnas separadas por tabulador,
abrible en Excel renombrando la extensión o vía "Archivo > Abrir".

**Mid-implementación, el usuario revisó el plan y pidió cambiar el
mecanismo por completo**: en vez de descargar cualquier archivo, un
`<textarea>` de solo lectura que siempre muestra el texto actual del
carrito, más un botón "Copiar todo" que copia al portapapeles. Esto evita
el allowlist de extensiones de `downloads` (ya no aplica) y es más simple:
no hay que declarar ninguna capability al publicar el Artifact, ni
distinguir el caso "dentro del sandbox del Artifact" del caso "abierto
localmente". Ver `../docs/superpowers/plans/2026-07-20-visualizador-cotizador-historico.md`,
sección "Task 8", para el registro completo del cambio de decisión.

## 2026-07-21 — Taxonomía y explorador de carpetas reemplazan el Top 10

El gráfico de Top 10 y la tabla plana "Índice de productos" de la versión
2026-07-20 se **eliminaron** (pedido explícito del usuario) y se
reemplazaron por el explorador de carpetas de 3 niveles que documenta
`CLAUDE.md` hoy.

- **Primer intento de `subcategoriaDe` fue el nombre completo del genérico**
  (no la primera palabra) — fragmentaba cada variante en su propia carpeta
  de 1 ítem (ej. "Destornillador p/electricista PH1x80mm" y "Destornillador
  PL 1000V 4x100mm" en subcarpetas distintas en vez de agruparse en
  "Destornilladores"; "Llave francesa"/"Llave ajustable"/"Llave inglesa" sin
  agruparse en "Llaves"). Corregido el mismo día tras que el usuario lo
  detectara con datos reales — la versión vigente (primera palabra
  pluralizada) está en `CLAUDE.md`.
- **`detectarTipoGenerico`** se agregó esa misma tarde porque la
  subcategoría-por-primera-palabra fallaba cuando el nombre empieza con un
  cuantificador genérico (ej. "Set 16 pzas destornillador precision"
  generaba su propia carpeta "Setes" en vez de unirse a
  "Destornilladores").
- **`SINONIMOS_TIPO_GENERICO`** — nombres de marca/término técnico
  investigados uno por uno vía búsqueda web: `"alimat"` → `Valvula`
  (confirmado: válvula de llenado automático, marca Watts ALM, con
  manómetro integrado) y `"flow control"` → `Valvula` (válvula de control
  de flujo).
- **Bugs reales encontrados probando con datos reales**:
  - `PATRON_MEDIDA` no reconocía una fracción pelada sin comilla ni unidad
    (ej. "1/2x1/2") — sin esto, ítems inoxidables reales quedaban
    invisibles (medida no detectada → excluidos). Se agregó `\b\d+\/\d+\b`
    como alternativa final del regex.
  - `pluralizar` duplicaba el plural si el nombre ya terminaba en "s" (ej.
    "Bolsas" → "Bolsases") — ahora si ya termina en "s" se devuelve sin
    cambios. Más tarde ese mismo día se agregó también el patrón "-ión" →
    "-iones" (unión → uniones).
  - Palabras clave que no calzaban por diferencias exactas de texto real:
    "cortatubos" (el dato real decía "Corta tubos", con espacio) y
    "tapagoteras" (el dato real decía "Tapagotera", singular — la clave
    plural nunca es substring de la singular).
- **Ajustes visuales de la misma tarde**: `.viz-leafrow` pasó de
  `display:flex` a `display:grid` (con flex, la columna "N compra(s)" no
  quedaba alineada entre filas de largo distinto); `.viz-root` pasó de
  `min-height:100%` a `min-height:100vh` (al navegar a una
  categoría/subcategoría con poco contenido, el fondo temático se encogía
  y dejaba ver el fondo blanco por defecto debajo).
- **Reglas de clasificación**: el usuario revisó la taxonomía inicial
  contra datos reales y pidió mover varias categorías — el orden de
  prioridad resultante (`OVERRIDES_CATEGORIA` primero, inox antes que
  Válvulas salvo herramientas, etc.) es el que documenta `CLAUDE.md` hoy;
  nuevas categorías agregadas esa tarde: Soldadura, Materiales Eléctricos,
  Productos Químicos, Transporte.
- **Orden del dashboard**: el buscador se movió a la parte superior del
  panel (antes iba después de la tabla/gráfico ya eliminados); el
  explorador de carpetas quedó como herramienta secundaria debajo.
- **Carrito**: el texto del botón cambió de "Agregar al carrito" a
  "Agregar al cotizador", y el ícono flotante de 🛒 a 🧾 (recibo) — pedido
  del usuario, sin cambiar el título del panel.
- **Exportación**: rediseñada de secciones Materiales/Equipos/Otros con
  cantidad y subtotal a una tabla comparativa de mercado (una fila por
  línea del carrito, columnas Elemento/Promedio/Más barato/Proveedor/Costo
  actualizado) — pedido explícito del usuario. La fecha de generación y la
  UF utilizada se sacaron del texto copiable a `#exportMeta` aparte, para
  que la caja de copia sea solo la tabla.

## 2026-08-19 — Alimentos, Calefacción y Control, y fix de cobertura PPR/Transporte/Seguridad

Pedido explícito del usuario: agrupar toda la comida/bebida en una sola
categoría "Alimentos" y asegurar que los tubos PPR cayeran en "Piping PPR".
Un análisis de los 348 ítems reales del catálogo (script puntual, no
versionado) encontró que el clasificador ya sabía asignar "Piping PPR" a
codos/tees/coplas PPR, pero **`GRUPOS_PIPING` nunca incluyó la palabra
"tubería"** — así que los ítems reales `"Tubería PPR Beta ..."` (los tubos
propiamente tales) y `"Tapagorro PPR ..."` caían en el catch-all "Otros /
Servicios" en vez de "Piping PPR". Se agregaron `tuberia`/`tubería`/
`tapagorro` a `GRUPOS_PIPING` — bug real, no solo cobertura nueva.

El mismo análisis (revisando los 90 ítems que caían en el catch-all)
encontró tres oportunidades más, aprobadas por el usuario junto con las dos
anteriores como una sola restructura:

- **Categoría nueva "Alimentos"** (`GRUPOS_ALIMENTOS`, ícono 🍽️): antes la
  comida/bebida vivía repartida en dos etiquetas manuales del Excel
  (`Alimentación` / `Viáticos-Alojamiento`, ninguna de las 5 categorías
  oficiales del dropdown de Centro de Costos) y sin estructura propia en el
  árbol — 11 ítems reales (sandwich, café, muffin, agua, leche, colación,
  Red Bull, etc.) reclasificados. `agua` se agregó con espacio final
  (`'agua '`) a propósito: sin el espacio matchea también "aguarrás"
  (`GRUPOS_CONSUMIBLE_OTRO`), que no tiene nada que ver.
- **Categoría nueva "Calefacción y Control"** (`GRUPOS_CALEFACCION`, ícono
  🌡️): cluster real de 8 ítems (presostato, termostato, termocupla, sonda,
  contactor, caldera, radiador) lo bastante grande y homogéneo para
  justificar categoría propia en vez de forzarlo en Materiales Eléctricos u
  Otros/Servicios.
- **Cobertura ampliada de Transporte y Seguridad (EPP)**: ambas categorías
  ya existían y el dato crudo de Centro de Costos ya marcaba esos ítems
  como `Transporte`/`Despachos`/`Seguridad Industrial`, pero al
  clasificador JS le faltaban las palabras clave reales — "transporte" (la
  propia categoría no se detectaba a sí misma), "estacionamiento",
  "despacho", "envío", "encomienda", "embarque" (7 ítems); "cofia", "cubre
  calzado", "visor", "plantilla", "desinfectante" (5 ítems). La subcategoría
  de Transporte "Fletes" se renombró a "Despachos y Fletes" (mismo grupo
  conceptual) y se agregó "Estacionamiento" como subcategoría propia.

El resto del catch-all (~25 ítems: policarbonato, moldura, silicona, lápiz,
pilas, etc.) se dejó **sin tocar** a propósito — demasiado heterogéneo,
forzar una categoría por 1-2 ítems sería ruido en vez de señal (mismo
criterio que ya aplicaba la política de "ítems que el clasificador no
reconoce" documentada en `CLAUDE.md`). Verificado con un script puntual que
comparó clasificación vieja vs. nueva sobre los 334 ítems distintos del
catálogo real: 40 cambios, todos saliendo del catch-all hacia la categoría
correcta, cero regresiones (ningún ítem que era visible quedó oculto por
`requiereMaterial`/`requiereMedida`).
