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
- **Gate de contraseña**: misma contraseña que Centro de Costos (decisión
  del usuario, 2026-07-23) — ver `template.html`.

## Contenido

- **Pestaña Proyectos** (tarjetas y tabla rehechas en la Fase 1, ver abajo):
  KPIs (N° completos, Margen al cierre de la cartera, Nota promedio, N°
  "Requiere atención", N° con alertas), ranking de Nota del Proyecto (barras),
  distribución de Evaluación (donut), tabla buscable (orden fijo por Nota
  descendente). El panel de detalle por proyecto (click en la fila) muestra
  además los KPIs agregados 2026-07-28 al playbook de "Indicadores": **Peso
  en cartera de ventas** y **Margen por día** (tarjetas junto a
  Margen/Desviación/Nota); una tabla ampliada por categoría (Materiales/
  Equipos/MO/Otros) con Proyectado, Real, Desviación %, Estructura % (mix),
  Costo % de venta y Ahorro/Sobrecosto, con fila Total; y una subtabla
  **Detalle real por subcategoría** (granularidad de "Detalle Costos
  Reales" — Consumibles, Equipos-Herramientas, Combustible, etc. — con su
  `% del Total Real del proyecto`). Todo recomputado en Python en
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

## Publicación

GitHub Pages, único canal desde la migración del 2026-08-05 — el Claude
Artifact privado que se usaba antes ya no se actualiza (pedido explícito
del usuario, 2026-08-19). Receta y comandos exactos en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
§ Hosting; URL fija:
`https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero/`.
