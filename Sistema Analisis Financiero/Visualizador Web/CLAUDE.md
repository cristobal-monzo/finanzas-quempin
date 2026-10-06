# CLAUDE.md — Visualizador Web de Análisis Financiero

Contenido y arquitectura real del dashboard HTML de **Análisis Financiero**.
Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de datos,
hosting). Ver también [`../CLAUDE.md`](../CLAUDE.md) para el esquema completo
de `Análisis de Proyectos 2026.xlsx`, y el spec de diseño
[`docs/specs/2026-07-23-analisis-financiero-visualizador-web-design.md`](../../docs/specs/2026-07-23-analisis-financiero-visualizador-web-design.md).

**Estado: implementado (2026-07-23).**

## Implementación real

```
Sistema Analisis Financiero/Visualizador Web/
├── CLAUDE.md              # este archivo — versionado
├── template.html          # estructura/CSS/JS + brand kit, SIN datos — versionado
├── ingreso.js             # lógica de la pestaña «Ingresar datos» (2026-10-02), la inserta el build — versionado
├── build_visualizador.py  # export saneado (recomputado en Python) + build — versionado
├── tests/                 # pytest de este visualizador — versionado
├── data/                  # snapshot intermedio (analisis-financiero.json) — gitignored
└── build/                 # index.html final con datos incrustados — gitignored
```

- **Un solo comando regenera todo**: `python driver.py visualizador` (desde
  la skill `Registro_Analisis_Financiero`). Correrlo tras cada `run` (o
  automáticamente, ya encadenado en `ejecutar()`) es lo único necesario.
- **Nunca lee celdas de fórmula**: las hojas "Indicadores"/"Clientes" del
  Excel son 100% fórmulas reescritas en cada corrida. Desde 2026-09-21
  `build_visualizador.py` tampoco recalcula nada por su cuenta: le pide cada
  KPI a `af.calcular_kpis_proyecto()` / `af.calcular_clientes()` (la misma
  implementación que usan los reportes PDF, espejo de las fórmulas del
  Excel) a partir de las columnas manuales de "Proyectos" y de "Detalle
  Costos Reales" (100% valores), y solo lo traduce a las claves cortas del
  snapshot.
- **Proyectos incompletos**: un proyecto sin las 7 columnas manuales de
  `af.CAMPOS_MANUALES_REQUERIDOS` cargadas (% Avance, Monto de Venta, 4
  Costos Proyectados, Mano de Obra Real) nunca recibe KPIs — aparece en el
  aviso de pendientes con qué le falta y un link a la planilla real. Los
  clientes suman solo sus proyectos completos. Regla única desde 2026-07-28 (antes el dashboard
  usaba solo 6 campos, distinto de los reportes PDF — ver
  `analisis_financiero.CAMPOS_MANUALES_REQUERIDOS` y
  `Sistema/tests/test_contrato_kpis.py`). Ver spec §3.
- **Datos incrustados** (base64, no `fetch`) — mismo motivo que Centro de
  Costos: el canal de consumo es un Claude Artifact privado.
- **Contraseña**: la misma de todos los tableros (decisión del usuario,
  2026-07-23); desde 2026-10-05 cifra los datos, reportes PDF incrustados
  incluidos — ver § "Punto de control de acceso" del doc maestro.

## Contenido

- **Pestaña Proyectos** (tarjetas y tabla rehechas en la Fase 1, ver abajo):
  KPIs (N° completos, Margen al cierre de la cartera, Nota promedio, N°
  "Requiere atención", N° con alertas), ranking de Nota del Proyecto (barras),
  distribución de Evaluación (donut), tabla buscable (orden fijo por Nota
  descendente). Click en la fila abre la **ficha del proyecto** (rehecha el
  2026-10-05, ver § «Ficha del proyecto»): venta, costo, margen y Nota contra
  el presupuesto, los gráficos que explican el resultado, la tabla ampliada
  por categoría (Presupuesto, Real, Desviación %, Estructura % (mix), Costo %
  de venta y Ahorro/Sobrecosto, con fila Total), el gasto por subcategoría de
  "Detalle Costos Reales" y los KPIs agregados el 2026-07-28 (**Peso en
  cartera de ventas**, **Margen por día**). Todo recomputado en Python en
  `build_visualizador.py` (`_kpis_por_categoria`, `calcular_peso_cartera`,
  `leer_detalle_subcategorias`), nunca leído del cache de fórmulas del
  Excel — mismo principio que el resto del snapshot.
- **`% Avance` y `Nota Parcial` en la tabla (2026-08-31, la Nota Parcial
  se reemplazó el 2026-09-21)**: la tabla
  principal de la pestaña pasó de 7 a 9 columnas (Proyecto, Cliente,
  **% Avance**, Monto Venta, Margen Real, Desviación %, Nota, **Nota
  Parcial**, Evaluación — `colspan` del panel de detalle actualizado a 9 en
  el mismo cambio); el panel de detalle suma una tarjeta **Nota Parcial**
  junto a Margen/Desviación/Nota, con el % de avance entre paréntesis. Los
  KPIs de cabecera de la pestaña (Nota promedio, N° "Requiere atención") y
  el ranking/donut **siguen usando la Nota financiera, no la Parcial** —
  mismo criterio que el resto del módulo (ver `CLAUDE.md`, "Nota Parcial").
- **Pestaña Clientes** (rehecha el 2026-09-21): KPIs (N° de clientes, tasa
  de recompra, mayor margen acumulado, conteo por Clasificación), margen
  acumulado por cliente (barras), distribución de Clasificación (donut, con
  aviso si ningún cliente es recurrente todavía), tabla buscable (orden fijo
  por margen acumulado descendente).
- **Sin paginación ni orden de columnas clickeable** (a diferencia del
  visualizador de Centro de Costos): con decenas de proyectos/clientes —no
  cientos de documentos— el orden fijo (Nota/margen descendente) más el buscador
  cubre la necesidad práctica. Descope deliberado, no un olvido — revisar si
  el N° de proyectos crece lo suficiente para justificarlo.
- Tooltips "i" con el texto de `GLOSARIO_KPIS` de `analisis_financiero.py`
  (hardcodeados en `template.html`, no viajan en el JSON — son texto
  estático, no dependen de datos del usuario).

## Fase 0 de la auditoría (2026-09-21)

Arreglos de horas, sin tocar ningún KPI. Versión anterior guardada en el tag
`checkpoint/af-antes-fase-0` (y el build de ese momento, con datos, en
`build/index_antes_fase_0.html`, gitignoreado).

- **Cabecera HTML real** (`<!DOCTYPE>`, `<meta charset>`, `<meta viewport>`)
  y la regex del gate con escapes `\u0300-\u036f` en vez de los caracteres
  combinantes literales. Antes el tablero corría en modo quirks y, servido
  sin cabecera UTF-8 (o abierto como archivo local), la regex quedaba como un
  rango inválido y **el script entero no corría**: el gate nunca abría.
  GitHub Pages sí manda UTF-8, por eso publicado funcionaba. Tests:
  `test_template_declara_doctype_charset_y_viewport`,
  `test_template_no_depende_del_encoding_para_la_regex_del_gate`.
- **Snapshot**: tres campos nuevos, todos calculados en Python.
  - `umbrales`: los cortes de la Evaluación de `af` (nunca copiados en el JS).
  - `cobertura`: proyectos y venta dentro del análisis contra toda la venta
    cargada. La regla de completitud es todo-o-nada; sin este dato no se veía
    que el 40 % de la venta estaba afuera.
  - `pendientes[].campos_faltantes` / `monto_venta`: qué falta a cada
    proyecto, vía `af.campos_faltantes`, que es ahora la base de
    `af.tiene_datos_completos` (contrato en `test_contrato_kpis.py`). Los
    pendientes vienen ordenados por venta, y **Gastos Generales ya no
    aparece como pendiente**: por diseño nunca tiene venta.
- **Template**:
  - El aviso de pendientes pasó de N mensajes idénticos a una lista de qué
    falta y cuánta venta queda afuera.
  - Las clases `.info-icon` y `.viz-search` no tenían CSS (la regla vivía
    como `.info-badge`, copiada de Centro de Costos).
  - El color de la desviación usaba `sem-*`, que solo tiene regla bajo
    `.kpi-card`, así que en tablas nunca se veía. Ahora es `tone-*`.
  - Gráfico de Nota en escala fija 0-100 con los cortes marcados.
  - Formato `es-CL` en todos los números.
  - Tooltip en coordenadas de viewport (antes se corría con el scroll).
  - Filas y tooltips operables con teclado.
  - Nav de tableros en una sola fila en teléfono.
  - Se sacó el CSS muerto heredado de Centro de Costos.
- **Perú no recibió estos cambios** en la Fase 0 (era una copia completa);
  los recibió en la Fase 1, al unificarse (ver abajo).
- **Pendiente de la Fase 0, a propósito**: cifrar los datos con la
  contraseña. Solo protege si Centro de Costos y Cotizador dejan de
  publicarla en texto plano (es la misma contraseña), así que es un cambio
  de los tres módulos, no de este.

## Fase 1 de la auditoría (2026-09-21)

Cambian los KPIs (decisiones del usuario, ver `../CLAUDE.md`, "Fase 1 de la
auditoría"); acá solo lo que toca al tablero.

- **Proyectos**: la tabla muestra el margen **al cierre** (real si el avance
  es 100%, estimado —marcado «est.»— si sigue en curso), su %, la
  desviación al cierre, Nota y Evaluación; la "Nota Parcial" desapareció.
  Cada fila con alertas lleva ⚠ n (texto completo en el `title` y en el
  panel de detalle). El detalle de un proyecto en curso muestra además el
  escenario pesimista, el margen a la fecha y el costo estimado al cierre.
  Tarjeta nueva "Con alertas"; "Margen al cierre" reemplaza a "Margen Real
  total" y lleva debajo el margen % ponderado de la cartera.
- **Clientes**: margen y venta acumulados, recompra y clasificación por
  margen acumulado, en vez del CLTV.
- **Categoría**: margen al cierre, venta y margen % ponderado por venta.
- **Snapshot**: cada KPI sale de `af`; nuevos `clientes_resumen`, `moneda`,
  `titulo`, `pais`, `proyectos[].alertas`/`en_curso`/`*_estimado_*`,
  `pendientes[].alertas` y umbrales de alerta/penalización en `umbrales`
  (el texto de las "i" se arma con ellos, nunca con números copiados).
  Vacío = `None` → "—" en el tablero, nunca un 0 inventado.
- **Perú unificado**: un solo `template.html` y un solo
  `build_visualizador.py` (`build(pais)`, config en `PAISES_VIZ`). El
  template lleva `__AF_TITULO__` y `__AF_NAV_ACTIVO__` (la pestaña activa de
  la navegación la marca el JS con `data-nav-activo`), y la moneda viaja en
  el snapshot. `Peru/Análisis Financiero/Visualizador Web/build_visualizador.py`
  quedó como envoltorio de 10 líneas y su `template.html` se borró.

## Fase 2 de la auditoría (2026-09-21): el tablero responde preguntas

La fase 1 dejó los KPIs correctos; esta cambia **qué pregunta contesta cada
pantalla**. Antes el tablero abría en una tabla de proyectos ordenada por
Nota: para saber qué necesitaba atención había que abrir fila por fila.

- **Pestaña "Resumen" (nueva, es la que abre)**: venta en análisis, margen
  al cierre de la cartera, sobrecosto acumulado (solo de los que se
  pasaron -- un proyecto que ahorró no compensa al que se pasó) y cuántos
  necesitan atención. Debajo, **"Qué mirar primero"**: una línea por
  proyecto con el motivo escrito (su alerta, o su Nota y por qué), ordenada
  por gravedad y tamaño, con un botón que lleva a la fila ya expandida. Al
  lado, la **dispersión margen vs desviación**: separa las dos preguntas que
  la Nota junta en un número (cuánto margen deja / si respetó el
  presupuesto), con el tamaño de burbuja por venta y líneas guía en el
  objetivo de margen y en "en presupuesto".
- **Pestaña "Presupuesto vs Real" (nueva)**: el error del presupuesto
  ponderado de la cartera, la categoría peor estimada, el **sesgo por
  categoría** (barras divergentes) y un **mapa de calor** proyecto ×
  categoría. Es la pestaña que sirve para cotizar mejor, no para juzgar el
  resultado.
- **Pestaña Proyectos**: filtros (estado, categoría, cliente, "solo con
  alertas"/"requieren atención") y **encabezados que ordenan de verdad** --
  antes tenían cursor de mano sin ordenar nada, y el orden era fijo por
  Nota. Los vacíos van siempre al final, en cualquier sentido.
- **Pestaña Clientes**: se suma la **concentración del ingreso** (Pareto con
  acumulado y "clientes equivalentes"), que es la lectura de riesgo que el
  CLTV nunca dio.
- **Móvil**: con 5 pestañas la barra ya no cabía en una línea y estiraba la
  página entera (scroll horizontal en todas las pestañas, no solo en las
  nuevas). Las pestañas envuelven y las tarjetas de gráfico llevan
  `min-width: 0` para que un SVG o una tabla ancha no estire el contenedor.

Todo lo que el tablero muestra sale del snapshot; los números nuevos
(`error_presupuesto_pct`, `presupuesto.sesgo_categorias`, `concentracion`,
`umbrales.margen_objetivo`) se calculan en `analisis_financiero.py`, no en
el JS. Tests: `test_snapshot_trae_sesgo_por_categoria_y_concentracion`,
`test_template_tiene_las_pestanas_y_los_ganchos_de_la_fase_2`.

## Ficha del proyecto (2026-10-05)

Pedido del usuario: que al abrir un proyecto se vean claramente los montos y
valores más relevantes, los gráficos que importan y lo destacable. El panel
anterior ponía 11 datos del mismo tamaño y color en la cabecera (la venta,
las fechas y la categoría quedaban al fondo, después de dos tablas), pintaba
el presupuesto en naranjo —lo más llamativo— y el gasto en gris, repetía esa
misma comparación en la tabla de abajo y nunca decía cuánto margen se perdió
o ganó contra lo presupuestado: había que restarlo a mano.

De arriba abajo:

1. **Contexto**: estado (en curso con barra de avance y % del presupuesto ya
   gastado, o terminado), categoría, fechas, «Ver reporte PDF» y «Cerrar».
2. **Cuatro cifras grandes**, cada una contra el presupuesto: venta (con su
   peso en la cartera), costo al cierre (▲/▼ % sobre o bajo el presupuesto),
   margen al cierre (cuánto más o menos que lo presupuestado, en pesos) y la
   Nota (con su Evaluación y a cuántos puntos está del corte siguiente). El
   color solo va donde hay un juicio, con los cortes de `formatoPctDesviacion`.
3. **Alertas**.
4. **De la venta al margen**: dos barras del largo de la venta partidas en
   costo y margen, una con el presupuesto y otra con el cierre (en curso: lo
   gastado, lo que falta a precio de presupuesto y una raya en el escenario
   pesimista). Debajo, la historia en una frase. Lo que pasa de la venta va en
   rojo («pérdida»).
5. **Por qué tiene esta nota**: rentabilidad sobre 70 y control del
   presupuesto sobre 30, en puntos que suman la Nota (`af.componentes_nota`).
6. **Costos por categoría**: presupuesto (zona clara con su borde), gastado
   (gris) y lo que se pasó (rojo), en la misma escala de pesos; en un
   proyecto terminado, una frase cuando la desviación total esconde errores
   que se compensan (`error_presupuesto_pct` ≥ 15 % y ≥ 2 × |desviación|).
   Debajo, la tabla con todos los montos.
7. **En qué se gastó** (barras por subcategoría de las facturas de Centro de
   Costos; antes una tabla con la columna interna «Bucket») y **Otros
   indicadores** (margen a la fecha y escenario pesimista si sigue en curso,
   error del presupuesto, margen por día).

Colores de la ficha: gris = costo, naranjo = margen, rojo = lo que pasa del
presupuesto o de la venta. Los grises tienen sus propias variables
(`--ficha-costo`, `--ficha-por-gastar`, `--ficha-ppto`, con valores para el
modo oscuro), validadas con el skill `dataviz`: ≥ 3:1 sobre la tarjeta y
ΔE ≥ 12 entre vecinos también simulando daltonismo.

Al abrir un proyecto (desde la tabla, «Qué mirar primero» o la dispersión),
su fila sube al borde de arriba con la ficha a la vista; antes, abierta desde
una fila del fondo, había que bajar a buscarla.

- **Snapshot**: `margen_proyectado`, `margen_proyectado_pct`,
  `margen_vs_presupuesto`, `presupuesto_gastado_pct`,
  `costo_cierre_pesimista`, `nota_puntos` por proyecto, y
  `umbrales.peso_rentabilidad` / `peso_control`. Todo desde `af`; el JS solo
  ordena y dibuja.
- **Tests**: `test_snapshot_trae_lo_que_la_ficha_compara_contra_el_presupuesto`
  y `test_la_ficha_del_proyecto_solo_lee_claves_que_trae_el_snapshot` (cada
  `p.clave` y `UMBRALES.clave` de la ficha existe en el snapshot: una clave
  mal escrita no da error en el navegador, deja una cifra en «—»).
- Se borró `renderBarChartComparativo` (solo lo usaba el panel anterior) y el
  CSS de la tabla de subcategorías.

## Pestaña «Ingresar datos» (2026-10-02)

Pedido del usuario: ingresar los valores manuales del análisis sin abrir el
Excel. Es la única pestaña que **escribe** algo: el resto del tablero sigue
siendo de solo lectura. Diseño del canal en `../CLAUDE.md` § «Ingreso manual
desde el tablero».

- **Qué muestra**: una tabla como la planilla, un proyecto por fila y una
  columna por campo manual, con lo que hoy tiene el Excel y lo que le falta a
  cada proyecto para entrar al análisis. Los campos, su tipo y su orden llegan
  en `DATA.ingreso` (`build_visualizador.datos_para_ingreso`, desde
  `pf.CAMPOS_TABLERO`); el template no repite ninguna columna (un test lo
  exige). Solo Chile: en Perú `ingreso` es `None` y la pestaña no aparece.
- **Lógica en `ingreso.js`**, no en el template: leer lo tecleado (35,5 % →
  0,355; «12.500.000» → 12500000), comparar con lo que había, armar un mensaje
  `datos-proyecto` por proyecto y escribirlo en la carpeta. Funciona en Node:
  `tests/test_ingreso.py` arma mensajes con él desde un snapshot real y los
  pasa por el catálogo y por el plan de Python. El build lo inserta junto con
  `Sistema Intercambio/esquemas.js` (el original, no una copia), con el que la
  pestaña valida cada envío antes de guardarlo.
- **Borrador** en `localStorage` (`af_ingreso_borrador_v1`): lo cambiado queda
  en naranjo y no se pierde al cerrar. Un borrador viejo que el tablero nuevo
  ya trae se descarta solo.
- **«Lo que se vio»** (`reemplaza`) es lo del snapshot, salvo que desde este
  navegador ya se haya enviado algo para ese campo que el tablero todavía no
  muestra (más nuevo que el snapshot, o aún en el buzón): entonces es lo
  enviado. Así un segundo cambio se apoya en el primero en vez de chocar.
- **Enviar**: en Chrome/Edge de escritorio, «Guardar en el buzón» escribe un
  archivo por proyecto en `buzon/` con la API de acceso a archivos. Usa el
  **mismo registro de IndexedDB que el Formulador** (`qpn-intercambio`): los
  dos están en `cristobal-monzo.github.io`, así que la carpeta conectada en
  uno sirve en el otro. En otro navegador, «Descargar» baja los mismos
  archivos para dejarlos a mano en `buzon/` (o `driver.py intercambio
  cargar`).
- **Seguimiento**: «Envíos desde este navegador» (`af_ingreso_envios_v1`, los
  últimos 60) dice si cada uno sigue en el buzón, si se aplicó, si espera una
  decisión o si fue rechazado, leyendo `publicado/analisis-financiero.json`
  (`mensajes`) cuando la carpeta ya tiene permiso; sin carpeta, compara con el
  snapshot.
- **El tablero publicado no cambia solo**: el procesador aplica el envío al
  Excel en ≤ 2 horas, pero GitHub Pages se actualiza cuando se publica
  (`/Actualizar_AF`).
- El aviso de proyectos incompletos lleva «Completarlos aquí», que abre la
  pestaña filtrada en los que les faltan datos.
- En pantallas de más de 1240 px la tabla usa todo el ancho de la ventana (no
  cabe en los 1.140 px del tablero); bajo 640 px cada proyecto es una tarjeta.

## Enlaces con el Formulador (2026-10-06)

Pedido del usuario: que cada herramienta lleve a la siguiente con el proyecto
abierto, sin volver a buscarlo.

- **Entrada `#proyecto=<TAG>`** (`abrirDesdeEnlace`, también al cambiar el
  hash): abre la ficha de ese proyecto; si no está en el análisis pero sí en
  «Ingresar datos», esa pestaña con el proyecto buscado (`abrirIngresoDe`); si
  el tablero todavía no lo trae, un aviso (`.aviso-enlace`) que dice cuándo
  aparece. La usa el Formulador al pasar un proyecto a ejecución y desde su
  seguimiento.
- **Salida «Ver la formulación ↗»** en la cabecera de la ficha
  (`enlaceFormuladorHtml`): abre el Formulador en `#/req/<N°>`, o en
  `#/tag/<TAG>` si el proyecto no trae N° de requerimiento.
- **`req` en el snapshot**: `leer_proyectos` lee la columna del N° de
  requerimiento (`af.pf.COLUMNA_REQ`; `_req` deja 280, 280.0 o «280» como
  `"280"`, y cualquier otra cosa como `None`) y lo pone en cada proyecto y en
  los pendientes de «Ingresar datos».
- Tests: `test_snapshot_trae_el_n_de_requerimiento_para_enlazar_al_formulador`
  y `test_la_ficha_enlaza_al_formulador_y_el_tablero_abre_enlaces_por_tag`.
- La cabecera lleva además el enlace «Formulador de proyectos ↗», igual en los
  6 tableros (ver `../../Visualizador Web/CLAUDE.md` § Navegación).

## Publicación

GitHub Pages, único canal desde la migración del 2026-08-05 — el Claude
Artifact privado que se usaba antes ya no se actualiza (pedido explícito
del usuario, 2026-08-19). Receta y comandos exactos en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
§ Hosting; URL fija:
`https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero/`.
