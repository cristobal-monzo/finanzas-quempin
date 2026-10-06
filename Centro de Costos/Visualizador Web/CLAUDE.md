# CLAUDE.md — Visualizador Web de Centro de Costos

Contenido a presentar en el HTML del visualizador de **Centro de Costos**.
Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de
datos, hosting) — este archivo solo cubre el contenido específico de este
módulo. Ver también [`../CLAUDE.md`](../CLAUDE.md) para el detalle completo
de la estructura de `Centro de Costos.xlsx` que este visualizador consume.

**Estado: implementado (2026-07-19).** Este archivo ya no es solo el
borrador de contenido — documenta también la arquitectura real. Ver
"Implementación real" más abajo antes de tocar `template.html` o
`build_visualizador.py`.

## Implementación real

```
Centro de Costos/Visualizador Web/
├── CLAUDE.md              # este archivo — versionado
├── template.html          # estructura/CSS/JS + logo de marca, SIN datos — versionado
├── build_visualizador.py  # export + build — versionado
├── data/                  # snapshot intermedio (centro-de-costos.json) — gitignored
└── build/                 # index.html final, con datos incrustados — gitignored
```

- **Un solo comando regenera todo**: `python driver.py visualizador` (desde
  la skill `Registro_Centro_de_Costos`, ver su `SKILL.md`) lee `Centro de
  Costos.xlsx`, arma el snapshot saneado, y lo incrusta en `template.html`
  para producir `build/index.html`. Correrlo tras cada `run` del registrador
  es lo único necesario para que el visualizador refleje los documentos
  nuevos — **nunca hay que editar `template.html` a mano para actualizar
  datos**, solo cuando cambie el diseño/estructura.
- **Datos incrustados (embebidos), no via `fetch`** — a diferencia de lo que
  sugiere el maestro (`../../Visualizador Web/CLAUDE.md` § Datos) para un
  hosting en GitHub Pages, el snapshot va **incrustado como base64** dentro
  del propio HTML en vez de cargarse en runtime desde `data/*.json`.
  Herencia de cuando el canal de consumo era un **Claude Artifact privado**:
  su sandbox no permitía `fetch` a archivos locales, necesitaba un único
  archivo autocontenido. La migración a GitHub Pages (2026-08-05) no cambió
  este mecanismo, solo dónde se publica el archivo ya armado. Migrar a
  `fetch` contra `data/centro-de-costos.json` sigue siendo directo (el
  snapshot ya existe con ese formato) si en algún momento se decide
  hacerlo; por ahora el snapshot en `data/` es solo un subproducto auditable
  del build, el HTML no lo lee.
- **Contraseña** (pedido del usuario 2026-07-19): pantalla previa que la
  pide antes de mostrar cualquier dato (acepta variantes de
  mayúsculas/tilde). Desde 2026-10-05 los datos van cifrados con ella y no
  está escrita en la página: ver § "Punto de control de acceso" del
  [doc maestro](../../Visualizador%20Web/CLAUDE.md).
- **Publicación**: GitHub Pages, único canal desde la migración del
  2026-08-05 — los Claude Artifacts privados que se usaban antes ya no se
  actualizan (pedido explícito del usuario, 2026-08-19). Receta y comandos
  exactos en [`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
  § Hosting; URL fija:
  `https://cristobal-monzo.github.io/finanzas-quempin/centro-de-costos/`.
- **Decisiones de saneado ya tomadas** (resuelven los puntos que este
  archivo dejaba abiertos):
  - Proveedor: tag corto en la tabla; razón social completa visible solo al
    expandir el detalle de una fila (no en la vista de tabla/gráficos).
  - Documentos pendientes de revisión (celdas rojas): **se incluyen**, con
    un indicador visual (●) junto al N° Ref. — no se excluyen del export.
  - `Fecha modificación` de `Master` se expone (como "última actualización
    de los datos" en el header) — no estaba contemplado en el borrador
    original.

## Botón de copiar archivo + notas "i" (2026-07-20)

- **Botón de copiar nombre de archivo**: junto al N° Ref. de cada fila de la
  tabla, un ícono pequeño copia al portapapeles el nombre del archivo de
  origen (ej. `UMAG-001_Shell_2026-07-15.jpg`) — pensado para ubicar rápido
  la foto original en `Sitio de comunicación - Centro de Costos 1/` sin tener
  que buscarla a mano por fecha/proveedor. Solo copia el nombre, nunca la
  ruta ni el proyecto. Requirió agregar `archivo_origen` (columna "Archivo
  origen" de `Master`) al snapshot exportado por `build_visualizador.py` —
  antes no viajaba al HTML en absoluto. Si no hay `archivo_origen` para un
  documento, no se renderiza el botón en esa fila. Usa
  `navigator.clipboard.writeText` con fallback a `document.execCommand
  ('copy')` (necesario porque el clipboard API moderno no siempre está
  disponible dentro del sandbox de un Claude Artifact).
- **Notas "i" explicativas**: 4 círculos con "i" (KPI "Gasto total (s/IVA)",
  KPI "Pendientes de revisión", gráfico "Top proveedores", gráfico "Gasto
  mensual acumulado") muestran una explicación corta al pasar el mouse
  (desktop) o al tocar (touch), reutilizando el mismo `.viz-tooltip` de los
  gráficos. Deliberadamente no se agregó a ningún otro KPI/gráfico/filtro —
  se consideran autoexplicativos por su label.
- Ver spec y plan completos en `docs/specs/2026-07-19-
  visualizador-cc-copy-archivo-y-notas-info-design.md` y el plan homónimo en
  `docs/plans/`.

## Ciclo de mejora continua (2026-07-19) — colores, tipografía, rendimiento

Tras la primera versión funcional, se corrió un loop autónomo de 4
iteraciones (auditoría → cambio → auto-validación → decisión, por pilar) que
dejó cambios importantes documentados acá para que no se repitan a mano ni
se reviertan por accidente:

- **Fuente de color oficial correcta**: el naranjo de marca usado en la
  primera versión (`#e9540d`) salió de muestrear píxeles del PNG del logo —
  aproximado, no exacto. El manual (`Material gráfico QUEMPIN/OFICIAL MANUAL
  DE MARCA GRÁFICA QUEMPIN.pdf`, página "SISTEMA CROMÁTICO CORPORATIVO")
  imprime los 4 hex oficiales explícitamente: `#ff5100` (Pantone Orange 021
  C), `#000000` (Black C), `#98989a` (Cool Gray 7 C), `#54565a` (Cool Gray
  11 C) — son los únicos 4 que usa `template.html` ahora para cualquier
  elemento de identidad de marca (header, gate, acentos, paleta categórica).
  Si se necesita releer el manual, `pip install pymupdf` permite
  renderizarlo página por página (no hay `pdftoppm`/poppler instalado en
  este equipo).
- **Paleta categórica con solo 4 colores oficiales**: el manual prohíbe
  explícitamente sustituir los colores por "parecidos" — pero un dashboard
  necesita distinguir más de 4 proyectos/categorías. Solución: los primeros
  4 (por gasto descendente) usan los 4 colores sólidos oficiales; el resto
  usa una textura de rayas diagonales (naranjo o gris oscuro) en vez de
  inventar un 5° color — mecanismo `buildColorMap`/`fillFor`/`swatchStyleFor`
  en el script del visualizador dentro de `template.html`.
- **Tipografía Lato embebida**: el manual reserva "Squ721Rm" (modificada)
  para el isologotipo — no está licenciada para reproducir en código y no
  hay archivo de fuente disponible. Para texto de datos en presentaciones
  digitales, el propio manual prescribe **Lato** (página "PRESENTACIÓN
  PPT.") — se embebió Lato 400/700/900 en woff2→base64 directo en
  `template.html` (sin CDN, los Artifacts bloquean requests externos).
- **2 bugs reales encontrados y corregidos con navegador real** (no solo
  revisión de código — `npx playwright install chromium` deja un Chromium
  headless disponible en este equipo para futuras verificaciones): el
  tooltip quedaba invisible en modo oscuro (fondo ligado a una variable que
  se resolvía casi blanca) y la pantalla de contraseña heredaba Times New
  Roman en vez de Lato por estar fuera del árbol de `.viz-root`. Antes de
  dar por buena cualquier modificación visual futura, correr un script
  Playwright que abra `build/index.html`, entre con la contraseña, y
  capture screenshots — el review de código solo no detectó ninguno de
  los dos bugs.
- **Rendimiento a futuro**: la tabla pagina de a 25 filas (antes dibujaba
  todas de una) y la búsqueda de texto tiene debounce de 150ms — pensado
  para cuando este módulo tenga cientos o miles de documentos, no solo los
  30 actuales.

## Ciclo UX/UI (2026-09-21) — el tablero como herramienta de exploración

Auditoría con navegador real (escritorio, 390 px, modo oscuro) sobre los 724
documentos reales. Lo que cambió, y por qué, para no revertirlo sin querer:

- **Los gráficos filtran.** Tenían `cursor:pointer` pero un clic no hacía
  nada. Ahora una barra de proyecto/proveedor, una porción o ítem de leyenda
  de la dona, o un mes del gráfico mensual filtran todo el tablero (un
  segundo clic lo quita; "Otros" abre el desglose). El proveedor no tiene
  select: se filtra desde el gráfico o desde el detalle de un documento
  ("Ver todo lo de <proveedor>").
- **Todo cambio de filtro pasa por `setFilters()`** (selects, chips, clics
  en gráficos, detalle, link). Si agregas un filtro, agrégalo a
  `EMPTY_FILTERS`, `CHIPS`, `HASH_KEYS` y `getFiltered()`; no escribas otro
  camino que toque `state` y llame a `render()` por su cuenta.
- **Chips de filtros activos** bajo la barra de filtros, cada uno removible.
  Antes la única pista de un filtro puesto era "N de 724".
- **Filtros y orden viajan en el hash** (`#proyecto=…&cat=…&orden=total_con_iva.asc`):
  recargar no los pierde y el link copiado abre la misma vista. Un valor que
  ya no existe en los datos (link viejo) se ignora.
- **Selector de período** (mes en curso, mes anterior, 3/12 meses, año en
  curso/anterior) que rellena Desde/Hasta.
- **Búsqueda por términos**: "easy cinta" exige las dos palabras en
  cualquier campo (antes, la frase completa como un trozo contiguo). Busca
  también en proyecto, categoría, tipo de documento y nombre + descripción
  de cada ítem; el texto se normaliza una sola vez por documento
  (`d._hay`). Coincidencias resaltadas; atajo `/` y `Esc`. **No es el motor
  de `Cotizador Historico/Sistema/busqueda.py`**: aquí se filtran documentos,
  no se rankean ítems. Si el tablero llegara a necesitar sinónimos o medidas
  equivalentes, reutiliza ese motor en vez de crecer este.
- **Eje mensual continuo**: `aggregateMensual` rellena los meses sin gasto.
  Antes Dic 2024 → May 2025 se dibujaba a la misma distancia que Jul → Ago, y
  la curva acumulada exageraba la pendiente de los tramos con huecos. El eje
  y usa marcas redondas (`niceScale`), y toda la columna de cada mes responde
  al mouse (antes había que acertarle a un punto de 4 px).
- **Montos negativos (notas de crédito)**: `fmt()` pone el signo antes del
  `$` ("−$194.979"; es-CL da "$-194.979"). Los gráficos grafican solo montos
  positivos y, si no queda ninguno, lo dicen. La nota de crédito tiene su
  propio badge gris — antes salía en el ámbar de "Pendiente".
- **Tabla**: el resumen de ítems va bajo el proveedor (o el ítem que calzó
  con la búsqueda), filas por página 25/50/100 (recordado en
  `localStorage`), cabeceras ordenables con teclado, el foco sobrevive a
  expandir/colapsar, y seleccionar texto no colapsa la fila.
- **Exportar CSV**: los documentos filtrados en el orden de la tabla, con
  `;` y BOM UTF-8 (lo que espera Excel es-CL), montos enteros, fechas
  DD-MM-AAAA. Solo lleva lo que ya está en el snapshot.
- **Móvil (≤ 640 px)**: la tabla pasa a tarjetas (antes Total y Estado
  quedaban fuera de pantalla), la navegación entre tableros a una sola fila
  deslizable (antes 3 filas) y los KPIs a 2 columnas.
- **Accesibilidad**: foco visible uniforme, el foco entra al modal y vuelve
  al botón que lo abrió, `aria-label` con resumen en cada gráfico,
  `prefers-reduced-motion` respetado. En oscuro, barras y muestras llevan un
  contorno (`--bar-outline`): el slot negro oficial sobre la tarjeta oscura
  quedaba en 1,3:1.
- **Bugs corregidos de paso**: la dona quedaba vacía al filtrar por una
  categoría (un arco de 360° tiene inicio = fin y SVG no lo dibuja; ver
  `donutPath`); el tooltip quedaba detrás del overlay de los modales
  (z-index 1000 < 1500); en móvil, el `resize` que dispara la barra de
  direcciones al hacer scroll redibujaba todo el tablero.

**Etiquetas unificadas en el build, no en el HTML.** El extractor escribe la
misma etiqueta con y sin tilde ("Ferreteria"/"Ferretería", "Nota de
Credito"/"Nota de Crédito", "Alimentacion"/"Alimentación"): el tablero las
mostraba como dos opciones de filtro y dos porciones de la dona.
`unificar_variantes()` en `build_visualizador.py` las junta (gana la forma
con tilde) en el snapshot, con test. **No corrige el Excel**: las variantes
siguen en `Master` y conviene corregirlas en origen.

**Cómo se verificó**: un script Playwright de 36 chequeos (clic en cada tipo
de gráfico, chips, búsqueda, período, solo notas de crédito, modal, orden por
teclado, CSV, link con hash, foco) que además compara el KPI "Gasto total"
contra la suma del snapshot en cada filtro, y la suma del CSV contra el
total. Vivió en el scratchpad de la sesión, no en el repo.

**Perú no recibió estos cambios.** `Peru/Centro de Costos/Visualizador
Web/template.html` es una copia de esta plantilla (cambia título, moneda,
pestaña activa y pie) que ya venía divergiendo. Portarlos es copiar este
archivo y reaplicar esas diferencias; mejor aún, generar la de Perú a partir
de esta.

## Automático desde `run` (2026-07-19) — y el bug de fórmulas sin recalcular

Pedido del usuario: que actualizar Centro de Costos actualice el
visualizador solo, sin correr un comando aparte. Implementado como **PASO
12c** dentro de `main()` en `Sistema/auditor_centro_costos.py`
(`actualizar_visualizador()`, ver ese archivo) — corre al final de cada
`run`, por las dos rutas (`driver.py run` y `python auditor_centro_costos.py`
directo), igual que el reflejo a Sitio de comunicación (PASO 12b). No falla
el `run` si el build del visualizador falla.

**Bug real encontrado al implementarlo, importante si se vuelve a tocar
`build_visualizador.py`**: `Master!"Total sin IVA (CLP)"` y `Master!"Total
con IVA (CLP)"` son **fórmulas de Excel** (`SUMIF` y `K+L`, ver `../CLAUDE.md`
§"Estructura de `Centro de Costos.xlsx`"). openpyxl nunca calcula fórmulas —
solo guarda el último valor cacheado que había cuando abrió el archivo. Como
PASO 6 (`reordenar_por_fecha`) **reescribe esas fórmulas en cada `run`** (para
que referencien la fila nueva tras reordenar), su valor cacheado queda vacío
en el `.xlsx` recién guardado hasta que alguien lo abra en Excel de verdad y
lo recalcule. El primer intento de PASO 12c automático leyó esas celdas
justo después del `wb.save()` de PASO 12 y mostró "$0" de gasto total pese a
que `Detalle` tenía los montos correctos. **Fix**: `build_visualizador.py`
nunca lee `total_sin_iva`/`total_con_iva` de `Master` — los recalcula
sumando los ítems de `Detalle` (`P. Unitario × Cantidad` ya escrito por
Python, nunca fórmula, siempre confiable). Puede haber una diferencia de
1-2 CLP por redondeo frente a lo que mostraría la fórmula de `Master` una
vez recalculada — mismo tipo de diferencia menor ya documentada en
`../CLAUDE.md` para otros totales de este libro, no es un error nuevo.

## Bug real corregido: "pendientes de revisión" nunca se marcaba (2026-08-05)

`extraer_datos_saneados` detecta celdas rojas comparando el ARGB de la
fuente contra un set fijo de strings (antes `{"FFFF0000", "FFC00000"}`),
reimplementado por separado de `_celda_es_roja` en
`Sistema/auditor_centro_costos.py` (que usa `endswith` sobre el sufijo
`"C00000"`). Un test que cruza ambos caminos contra los `Font()` reales del
módulo que sí escribe el Excel (`test_pendiente_coincide_con_el_color_real_
de_auditor_centro_costos`) encontró que **ninguno de los dos colores del
set coincidía con lo que openpyxl realmente devuelve** al releer un `.xlsx`
guardado (`"00C00000"`, no `"FFC00000"`) — el dashboard nunca marcó ningún
documento como pendiente de revisión, sin importar cuántas celdas rojas
hubiera. Corregido reusando el mismo criterio `endswith("C00000")` que
`_celda_es_roja`. **Cualquier tablero ya publicado antes de esta fecha
tiene el conteo de "Pendientes de revisión" en 0 de forma incorrecta** —
hay que regenerar (`python driver.py visualizador`) y republicar para que
refleje los pendientes reales.

## Fuente de datos

`Centro de Costos/Excel/Centro de Costos.xlsx`, hojas `Master` (una fila
por documento) y `Detalle` (una fila por ítem de línea). Ver
`../CLAUDE.md` §"Estructura de `Centro de Costos.xlsx`" para el esquema
completo de columnas.

## KPIs (resumen en la parte superior)

- Gasto total (con IVA y sin IVA).
- Gasto por proyecto (los 5-8 proyectos activos).
- Gasto por categoría.
- Cantidad de documentos registrados.
- Documentos pendientes de revisión (celdas rojas / sin N° de documento
  legible) — conteo, no el detalle sensible.

## Tabla dinámica

Una fila por documento (`Master`), expandible a sus ítems (`Detalle`).
Columnas mínimas: N° Ref., Proyecto, Fecha, Proveedor (tag corto, no la
razón social completa — ver punto de saneado más abajo), Categoría, Total
con IVA, Estado. Ordenable por cualquier columna. Búsqueda de texto libre
sobre proveedor/ítem/N° de documento.

## Gráficos

- Barras: gasto por proyecto.
- Dona: gasto por categoría.
- Línea temporal: gasto mensual acumulado.
- Ranking: top 8 proveedores por monto (el resto se resume en una nota
  "+N proveedores más fuera del top 8 ($monto)", no se ocultan sin avisar).

## Filtros

- Proyecto.
- Tipo de proyecto (I+D+i, Mantenimiento, Gastos Generales, etc.).
- Categoría.
- Estado (Pagado/Pendiente/etc.).
- Rango de fechas.

## Export saneado sugerido (`data/centro-de-costos.json`)

Agregados por proyecto/categoría/mes/proveedor, más un detalle de
documento con las columnas de la tabla dinámica de arriba. Puntos a
decidir antes de generar el primer export real:

- ¿Se expone la razón social completa del proveedor, o solo el tag corto
  (ej. "Shell") que ya usa `Master`? Recomendado: solo el tag, salvo que el
  sitio quede con control de acceso resuelto (ver punto abierto del
  maestro).
- ¿Se incluyen los documentos marcados en rojo (pendientes de revisión),
  o se excluyen del export hasta que se corrijan?

## Consultor IA (opcional, no obligatorio para la v1)

Si se implementa, debería poder responder preguntas del tipo "¿cuánto
gastamos en UMAG en julio?" o "¿quién es el proveedor con más gasto
acumulado?" contra el export saneado — no contra el Excel fuente.
