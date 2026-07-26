# Visualizador AF — pestaña Categoría + panel de detalle con PDF — Diseño

Estado: aprobado por el usuario (brainstorming), pendiente de plan de implementación.

## 1. Contexto

El Visualizador Web de Análisis Financiero (`Sistema Analisis Financiero/Visualizador Web/`)
ya está implementado y publicado: pestañas Proyectos y Clientes, KPIs +
gráficos + tabla buscable en cada una, datos recomputados en Python desde
`Análisis de Proyectos.xlsx` y embebidos en base64 dentro de un
`build/index.html` autocontenido (Claude Artifact privado, gate de
contraseña). Ver
[`docs/superpowers/specs/2026-07-23-analisis-financiero-visualizador-web-design.md`](2026-07-23-analisis-financiero-visualizador-web-design.md).

Este spec agrega dos piezas nuevas sobre esa base:

1. Una tercera pestaña **"Categoría"** — agregados financieros agrupados por
   la columna "Categoría" de la hoja Proyectos (poblada automáticamente
   desde Centro de Costos, ver `Sistema Analisis Financiero/CLAUDE.md`).
2. Un **panel de detalle expandible**, al hacer click en una fila de
   Proyectos o de Categoría, con KPIs/gráfico/tabla completos del proyecto
   (o de la categoría) — incluyendo un botón para ver/descargar el reporte
   PDF que genera el skill `Reportes_Analisis_Financiero`, si existe.

## 2. Restricción arquitectónica clave: los PDF viajan embebidos

El Visualizador es un HTML autocontenido sin backend ni `fetch` (mandato ya
vigente: Claude Artifact privado, sandbox sin acceso a red ni al disco
local del visor). Un link a una ruta local (`Análisis Financiero/Reportes/
Proyectos/UMAG.pdf`) no resuelve para nadie que abra el Artifact publicado.

**Decisión (confirmada con el usuario)**: `build_visualizador.py` escanea
`Análisis Financiero/Reportes/{Proyectos,Categorías}/*.pdf` en cada build y
embebe en base64 el PDF de cada proyecto/categoría que ya tenga uno
generado, igual que ya se hace con los datos y el logo/fuente. El archivo
`build/index.html` crece proporcionalmente a la cantidad de proyectos con
reporte (~100KB por PDF) — aceptado como trade-off mientras el volumen sea
de decenas de proyectos, no cientos; revisar si crece mucho más.

**Fuera de alcance (decisión explícita)**: el dashboard **no** detecta si
un PDF embebido quedó desactualizado respecto a los datos actuales — esa
lógica (hash del paquete de datos vs. manifiesto) ya vive en
`Sistema Analisis Financiero/Reportes/estado_reportes.py` y se consulta por
separado vía `python driver.py status` del skill `Reportes_Analisis_
Financiero`. Duplicarla aquí agregaría una dependencia de recompute
significativa (recrear el mismo paquete de datos que arma
`datos_reportes.py`) para un beneficio marginal. El dashboard solo muestra
"hay reporte generado" o "sin reporte", con la fecha de generación tomada
del propio archivo (o, si existe, del manifiesto — ver §4).

Reportes de **Clientes** (`Análisis Financiero/Reportes/Clientes/*.pdf`)
quedan fuera de este spec — el usuario pidió detalle+PDF para proyectos, y
la pestaña Categoría nueva; extenderlo a Clientes es una adición natural
futura, no incluida aquí (YAGNI).

## 3. Pestaña "Categoría"

Mismo patrón visual que Proyectos/Clientes:

- **KPIs**: N° de categorías, categoría líder por Margen Real total.
- **Gráficos**: barras de Margen Real total por categoría; donut de
  distribución de N° de proyectos por categoría.
- **Tabla**: Categoría, N° proyectos, Margen Real total, Nota promedio —
  ordenada por Margen Real total descendente, buscable (mismo patrón de
  `buscarProyectos`/`buscarClientes`). Filas clickeables → panel de detalle
  de categoría (ver §5).

**Agrupación**: se arma agrupando `kpis_proyectos_completos` (los mismos
proyectos completos que ya alimentan Proyectos/Clientes) por su campo
`categoria`. Un proyecto sin categoría asignada (columna vacía en Excel) va
a un bucket **"Sin categoría"** — nunca se excluye de la pestaña.

## 4. Datos nuevos en `build_visualizador.py`

`calcular_kpis_proyecto` debe agregar a su dict de salida (ya usado por
Proyectos/Clientes) los campos que el detalle necesita y que hoy no
expone:

- `categoria` (columna "Categoría" de Proyectos; `None`/vacío → se
  normaliza a `"Sin categoría"` en el punto de agregación, no en el KPI
  individual — el proyecto conserva su valor crudo).
- `fecha_inicio`, `fecha_cierre` (ya se leen en `leer_proyectos`, solo
  faltan propagarse al dict de salida).
- Desglose completo Proyectado vs. Real por categoría de costo:
  `costos_proyectados = {materiales, equipos, mo, otros}` y
  `costos_reales = {materiales, equipos, mo, otros}` (ya se calculan
  internamente en `calcular_kpis_proyecto`/`sumar_costos_reales_por_bucket`,
  solo faltan incluirse en el dict devuelto en vez de colapsarse
  directamente al total).

Nueva función `calcular_categorias(kpis_proyectos_completos: list[dict]) ->
list[dict]`: agrupa por `categoria` (normalizando vacío → `"Sin
categoría"`) y devuelve, por categoría, `{categoria, n_proyectos,
margen_real_total, nota_promedio, tags_proyectos}` (`tags_proyectos` para
que el panel de detalle de categoría pueda listar/filtrar sus proyectos).

Nueva función `embeber_reportes_pdf(proyectos: list[dict], categorias:
list[dict]) -> dict[str, str]`: para cada proyecto (por `tag`) y cada
categoría (por nombre), busca `af.RAIZ_DATOS / "Reportes" / "Proyectos" /
f"{tag}.pdf"` / `.../ "Categorías" / f"{categoria}.pdf"`; si existe, lo
lee y lo codifica en base64; devuelve un dict plano `{"proyecto:TAG":
"<b64>", "categoria:Nombre": "<b64>"}` solo con las entradas que
efectivamente tienen PDF (nunca claves con valor vacío/null — la ausencia
de la clave ES la señal de "sin reporte"). `extraer_datos_saneados` agrega
este dict al snapshot bajo la clave `"reportes_pdf"`.

`extraer_datos_saneados` pasa a incluir en su dict de salida:
`categorias` (de `calcular_categorias`) y `reportes_pdf` (de
`embeber_reportes_pdf`), junto a los ya existentes `proyectos`, `clientes`,
`pendientes`, `kpis_proyectos`, `generado`.

## 5. Panel de detalle expandible

**Interacción**: al hacer click en una fila de la tabla de Proyectos (o de
Categoría), se expande un panel debajo de esa fila — mismo patrón de fila
expandible que ya tiene `template.html` sin usar, heredado de Centro de
Costos (clases `tr.detail-row`, `.detail-panel`, `.detail-grid` — ya
definidas en el CSS copiado en la Tarea 4 del plan anterior, nunca
activadas). Un solo panel abierto a la vez; click de nuevo en la misma fila
lo cierra.

**Contenido — detalle de Proyecto** (mismos datos que ya usa la página 1
del PDF de `Reportes_Analisis_Financiero` para ese proyecto, visualizados
en el dashboard en vez de en PDF):

- KPI cards: Margen Real, Margen Proyectado (`monto_venta -
  total_proyectado`), Desviación %, Nota + Evaluación (con el mismo color
  de pill que ya usa la tabla de Proyectos si aplica).
- Gráfico de barras comparativo Proyectado vs. Real por categoría de costo
  (Materiales/Equipos/Mano de Obra/Otros) — nueva función genérica
  `renderBarChartComparativo(containerId, items, labelKey, valorAKey,
  valorBKey, etiquetaA, etiquetaB)` (2 series, mismo estilo SVG que
  `renderBarChart`/`renderDonutChart`, reutilizable si más adelante se
  necesita otra comparación de 2 series).
- Tabla completa de montos: Monto de Venta, los 4 costos proyectados, los
  4 costos reales, Total Proyectado, Total Real, Margen Proyectado, Margen
  Real, Desviación %, Fecha de inicio, Fecha de cierre, Estado, Categoría.
- Botón **"Ver/Descargar PDF"**: si `DATA.reportes_pdf["proyecto:" + tag]`
  existe, el botón construye un Blob URL desde el base64 decodificado
  (`type: "application/pdf"`) y lo abre en una pestaña nueva (el visor de
  PDF nativo del navegador permite guardar desde ahí) — no se usa un
  `href="data:...` gigante inline. Si no existe, se muestra en su lugar el
  texto "Sin reporte generado" (no un botón deshabilitado).

**Contenido — detalle de Categoría**: mismo patrón, con el alcance de la
categoría en vez de un proyecto: KPI cards (N° proyectos, Margen Real
total, Nota promedio), gráfico de barras de Margen Real por proyecto
dentro de esa categoría (reutiliza `renderBarChart` genérico), tabla de
los proyectos de esa categoría (Proyecto, Cliente, Margen Real, Nota), y el
mismo botón de PDF apuntando a `DATA.reportes_pdf["categoria:" + nombre]`.

## 6. Testing

- `build_visualizador.py`: tests para `calcular_categorias` (agrupación
  correcta, bucket "Sin categoría", nota promedio/margen total correctos)
  y `embeber_reportes_pdf` (con `tmp_path`: PDF existente → se embebe en
  base64 correctamente decodificable; PDF ausente → la clave no aparece en
  el dict devuelto — nunca testear contra los PDFs reales de la empresa).
- `template.html`: sin test automatizado para el JS (mismo criterio que el
  resto del dashboard) — verificación manual en navegador como en las
  tareas anteriores del visualizador.

## 7. Fuera de alcance

- Detalle+PDF para Clientes (solo Proyectos y Categoría, por pedido
  explícito del usuario).
- Detección de reportes PDF desactualizados dentro del dashboard (ver §2).
- Paginación/orden por columna en las tablas nuevas (Categoría) — mismo
  descope ya documentado para Proyectos/Clientes en
  `Sistema Analisis Financiero/Visualizador Web/CLAUDE.md`, por el mismo
  motivo (volumen de datos bajo).
- Republicar el Artifact — acción manual del usuario tras la
  implementación, como ya ocurre hoy.
