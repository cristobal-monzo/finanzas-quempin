# CLAUDE.md — Visualizador Web de Análisis Financiero

Contenido y arquitectura real del dashboard HTML de **Análisis Financiero**.
Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de datos,
hosting). Ver también [`../CLAUDE.md`](../CLAUDE.md) para el esquema completo
de `Análisis de Proyectos 2026.xlsx`, y el spec de diseño
[`docs/superpowers/specs/2026-07-23-analisis-financiero-visualizador-web-design.md`](../../docs/superpowers/specs/2026-07-23-analisis-financiero-visualizador-web-design.md).

**Estado: implementado (2026-07-23).**

## Implementación real

```
Sistema Analisis Financiero/Visualizador Web/
├── CLAUDE.md              # este archivo — versionado
├── template.html          # estructura/CSS/JS + brand kit, SIN datos — versionado
├── build_visualizador.py  # export saneado (recomputado en Python) + build — versionado
├── tests/                 # pytest de este visualizador — versionado
├── data/                  # snapshot intermedio (analisis-financiero.json) — gitignored
└── build/                 # index.html final con datos incrustados — gitignored
```

- **Un solo comando regenera todo**: `python driver.py visualizador` (desde
  la skill `Registro_Analisis_Financiero`). Correrlo tras cada `run` (o
  automáticamente, ya encadenado en `ejecutar()`) es lo único necesario.
- **Nunca lee celdas de fórmula**: las hojas "Indicadores"/"Clientes" del
  Excel son 100% fórmulas reescritas en cada corrida — `build_visualizador.py`
  recomputa Total Real/Margen Real/Desviación %/Nota/Evaluación/CLTV/
  Clasificación directamente en Python a partir de las columnas manuales de
  "Proyectos" y de "Detalle Costos Reales" (100% valores). Ver spec §2 para
  el detalle y el precedente en Centro de Costos.
- **Proyectos incompletos**: un proyecto sin las 8 columnas manuales de
  `af.CAMPOS_MANUALES_REQUERIDOS` cargadas (% Avance, Fecha de inicio, Monto
  de Venta, 4 Costos Proyectados, Mano de Obra Real) nunca recibe KPIs —
  aparece en el banner "Pendientes de completar" con un link a la planilla
  real. Clientes con proyectos mixtos calculan su CLTV solo con los
  proyectos completos. Regla única desde 2026-07-28 (antes el dashboard
  usaba solo 6 campos, distinto de los reportes PDF — ver
  `analisis_financiero.CAMPOS_MANUALES_REQUERIDOS` y
  `Sistema/tests/test_contrato_kpis.py`). Ver spec §3.
- **Datos incrustados** (base64, no `fetch`) — mismo motivo que Centro de
  Costos: el canal de consumo es un Claude Artifact privado.
- **Gate de contraseña**: misma contraseña que Centro de Costos (decisión
  del usuario, 2026-07-23) — ver `template.html`.

## Contenido

- **Pestaña Proyectos**: KPIs (N° completos, Margen Real total, Nota
  promedio, N° "Requiere atención"), ranking de Nota del Proyecto (barras),
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
- **`% Avance` y `Nota Parcial` en la tabla (2026-08-31)**: la tabla
  principal de la pestaña pasó de 7 a 9 columnas (Proyecto, Cliente,
  **% Avance**, Monto Venta, Margen Real, Desviación %, Nota, **Nota
  Parcial**, Evaluación — `colspan` del panel de detalle actualizado a 9 en
  el mismo cambio); el panel de detalle suma una tarjeta **Nota Parcial**
  junto a Margen/Desviación/Nota, con el % de avance entre paréntesis. Los
  KPIs de cabecera de la pestaña (Nota promedio, N° "Requiere atención") y
  el ranking/donut **siguen usando la Nota financiera, no la Parcial** —
  mismo criterio que el resto del módulo (ver `CLAUDE.md`, "Nota Parcial").
- **Pestaña Clientes**: KPIs (top CLTV, CLTV promedio, conteo por
  Clasificación), top 8 clientes por CLTV (barras), distribución de
  Clasificación (donut), tabla buscable con nota de proyectos pendientes
  por cliente (orden fijo por CLTV descendente).
- **Sin paginación ni orden de columnas clickeable** (a diferencia del
  visualizador de Centro de Costos): con decenas de proyectos/clientes —no
  cientos de documentos— el orden fijo (Nota/CLTV descendente) más el buscador
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
- **Perú no recibió estos cambios**: su `template.html` y su
  `build_visualizador.py` son copias completas de los de Chile. Portar la
  Fase 0 duplicaría de nuevo la lógica; conviene primero unificarlos (un solo
  template + un build parametrizado por país, como en el Cotizador).
- **Pendiente de la Fase 0, a propósito**: cifrar los datos con la
  contraseña. Solo protege si Centro de Costos y Cotizador dejan de
  publicarla en texto plano (es la misma contraseña), así que es un cambio
  de los tres módulos, no de este.

## Publicación

GitHub Pages, único canal desde la migración del 2026-08-05 — el Claude
Artifact privado que se usaba antes ya no se actualiza (pedido explícito
del usuario, 2026-08-19). Receta y comandos exactos en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
§ Hosting; URL fija:
`https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero/`.
