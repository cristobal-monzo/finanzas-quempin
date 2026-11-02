# CLAUDE.md — Tablero de Centro de Costos

Reglas comunes (marca, teléfono, candado, publicar): [`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md).
Decisiones y arreglos en detalle: [`../docs/tablero.md`](../docs/tablero.md). URL fija:
`https://cristobal-monzo.github.io/finanzas-quempin/centro-de-costos/`.

## Piezas

- `template.html` (123 KB: Grep, no lo leas entero): estructura, CSS y JS, sin datos. Se edita solo si cambia el diseño.
- `build_visualizador.py`: lee `Centro de Costos.xlsx`, arma el snapshot saneado (`data/centro-de-costos.json`, solo un
  subproducto auditable) y lo incrusta cifrado en `build/index.html`. `driver.py visualizador` lo regenera; también corre
  al final de cada `run` (PASO 12c) y, si falla, no aborta el `run`.
- `../../Peru/Centro de Costos/Visualizador Web/template.html` es una copia que **ya divergió**: un cambio aquí no llega a
  Perú solo.

## Reglas

- **Los totales se recalculan sumando `Detalle`; nunca se leen de `Master`.** Sus «Total sin/con IVA» son fórmulas de Excel,
  openpyxl no las calcula y `reordenar_por_fecha` las reescribe, así que su valor cacheado queda vacío tras cada `run` (salía
  «$0»). Puede haber 1–2 CLP de diferencia por redondeo.
- **Una celda roja se detecta con `endswith("C00000")`, igual que `_celda_es_roja`**: openpyxl devuelve `00C00000` al releer.
  Lo vigila `test_pendiente_coincide_con_el_color_real_de_auditor_centro_costos`.
- **Etiquetas**: `unificar_variantes()` junta las escritas con y sin tilde en el snapshot (gana la forma con tilde); no corrige
  el Excel.
- **Saneado**: el proveedor va como tag corto en la tabla y con razón social solo al expandir la fila. Los pendientes de
  revisión se incluyen, con un ● junto al N° Ref. `Fecha modificación` es la «última actualización» de la cabecera.
- **Todo cambio de filtro pasa por `setFilters()`**. Un filtro nuevo va en `EMPTY_FILTERS`, `CHIPS`, `HASH_KEYS` y
  `getFiltered()`; no escribas otro camino que toque `state`. Filtros y orden viajan en el hash, y un valor que ya no existe
  se ignora.
- **Búsqueda**: filtra documentos por términos (`d._hay`). No es el motor del Cotizador; si llegara a necesitar sinónimos o
  medidas, reutiliza `Cotizador Historico/Sistema/busqueda.py`.
- **Ícono del N° Ref.**: abre el documento en SharePoint (`enlace_documento()` → `enlace_archivo`, regla única en
  `../../Visualizador Web/documentos.py`). Si la carpeta está en el equipo y el archivo ya no, la fila no lleva ícono.
- **Color**: solo los 4 oficiales (`#ff5100`, `#000000`, `#98989a`, `#54565a`). Más categorías = tonos aclarados
  (`BRAND_TINTS`, `buildColorMap`, `fillFor`), nunca un quinto color. Lato embebida, sin CDN. En oscuro, las barras llevan
  `--bar-outline`.
- **Negativos**: `fmt()` pone el signo antes del `$`; los gráficos solo grafican positivos y, si no queda ninguno, lo dicen.
- **CSV**: los documentos filtrados en el orden de la tabla, con `;` y BOM UTF-8, enteros y fechas `DD-MM-AAAA`.
- **Verifica con un navegador real** todo cambio visual (abrir `build/index.html`, entrar y capturar): el review de código no
  detectó los bugs de tooltip en oscuro ni de la fuente en la pantalla de contraseña. Las capturas, fuera del repo.

## Contenido

KPIs: gasto total con y sin IVA, por proyecto y por categoría, N° de documentos y pendientes de revisión. Tabla: una fila por
documento, expandible a sus ítems, 25/50/100 por página, ordenable. Gráficos que **filtran al hacer clic**: barras por proyecto,
dona por categoría, gasto mensual acumulado (eje continuo, `aggregateMensual`) y top 8 proveedores. Filtros: proyecto, tipo de
proyecto, categoría, estado, fechas con selector de período y proveedor (desde el gráfico o el detalle).
