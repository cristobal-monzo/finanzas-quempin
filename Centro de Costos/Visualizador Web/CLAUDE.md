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
  eventual hosting en GitHub Pages, hoy el snapshot va **incrustado como
  base64** dentro del propio HTML en vez de cargarse en runtime desde
  `data/*.json`. Motivo: el canal de consumo real hoy es un **Claude
  Artifact privado** (no GitHub Pages — el punto de control de acceso del
  maestro sigue sin resolverse), y los Artifacts corren en un sandbox que no
  permite `fetch` a archivos locales — necesitan un único archivo
  autocontenido. Si más adelante se decide publicar en GitHub Pages, migrar
  a `fetch` contra `data/centro-de-costos.json` es directo (el snapshot ya
  existe con ese formato); por ahora el snapshot en `data/` es solo un
  subproducto auditable del build, el HTML no lo lee.
- **Gate de contraseña** (pedido del usuario 2026-07-19): pantalla previa
  que pide contraseña antes de mostrar cualquier dato (acepta variantes de
  mayúsculas/tilde). Es una barrera del lado del cliente, **no seguridad
  real** — el propio HTML lo dice en su pie de página — solo disuade acceso
  casual a quien tenga el link. La contraseña vive como constante en
  `template.html`; los datos van en base64 (no JSON plano) como capa extra
  liviana, pero siguen siendo recuperables por cualquiera con el HTML —
  no lo trates como control de acceso real.
- **Publicación**: se sube como Claude Artifact (privado por defecto) desde
  una sesión de Claude Code, apuntando siempre al **mismo link** — nunca se
  genera uno nuevo (pedido explícito del usuario). El link real vive en
  [MEMORY.md del skill](../.claude/skills/Registro_Centro_de_Costos/MEMORY.md),
  no en este archivo.
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
- Ver spec y plan completos en `docs/superpowers/specs/2026-07-19-
  visualizador-cc-copy-archivo-y-notas-info-design.md` y el plan homónimo en
  `docs/superpowers/plans/`.

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
