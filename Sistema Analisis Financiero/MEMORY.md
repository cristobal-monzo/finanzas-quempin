# MEMORY.md — Análisis Financiero

Memoria del módulo: decisiones tomadas, historial, y pendientes que dependen del
usuario. El diseño técnico completo vive en el spec (ver `CLAUDE.md`); acá se
registra lo que no está en el código — decisiones de diseño, contexto de
brainstorming — más los pendientes reales que quedan tras la implementación.

## Decisiones tomadas (brainstorming, 2026-07-20)

- **Rol**: el módulo no es solo un pipeline de datos — actúa como analista
  financiero experto (evalúa proyectos, propone/depura KPIs, decide presentación,
  cruza todos los módulos). Ver "Rol de este agente" en `CLAUDE.md`.
- **TAG de proyecto = prefijo de Centro de Costos** (`PREFIJOS_PROYECTO`), no un
  código aparte — evita mantener un mapeo duplicado.
- **Mano de Obra Real queda 100% manual** — hoy no existe esa categoría en los
  datos de Centro de Costos (`categoria_item` solo tiene `Materiales`,
  `Consumibles`, `Equipos-Herramientas`). Se automatiza en una iteración futura
  si aparece una fuente (boletas de honorarios, planillas).
- **Carpetas de proyecto nuevas van en la fuente real** (`Sitio de comunicación -
  Centro de Costos 1/Facturas y Boletas/<Nombre>/`), no en la legado
  (`Centro de Costos/Facturas y Boletas/`) — el usuario confirmó explícitamente
  este punto porque el nombre que él mencionó al pedir la funcionalidad era el
  de la carpeta legado (fácil de confundir, ya pasó antes con Centro de Costos).
- **Disparo encadenado al `run` de Centro de Costos** (no un comando 100% aparte)
  — mismo patrón que el Visualizador Web (paso 12c). Igual queda disponible como
  skill propio para refrescar sin correr todo Centro de Costos.
- **"Rentabilidad por cliente (ROI)" se renombra a "Rentabilidad sobre costo"**
  — el cálculo (Utilidad Neta / Costos Totales) es un markup, no un ROI de
  capital invertido en sentido estricto. Decisión explícita del usuario para
  evitar comparaciones engañosas con un ROI financiero real.
- **Las 4 categorías (Materiales/Equipos/MO/Otros) tienen el mismo tratamiento
  de KPIs** (Productividad + Costo % de venta + Desviación) — el archivo de
  ejemplo original solo cubría Materiales y MO; se extendió por consistencia,
  a pedido del usuario.

## Reorganización de carpetas (2026-07-21)

El usuario pidió que `Análisis Financiero/` (carpeta hermana de esta) quede
**solo** con el Excel de trabajo — todo el código, docs y skill se movieron
acá, a `Sistema Analisis Financiero/`. `RAIZ_DATOS` en
`Sistema/analisis_financiero.py` apunta explícitamente a la carpeta del
Excel; `RAIZ_ANALISIS_FINANCIERO` en
`Centro de Costos/Sistema/auditor_centro_costos.py` apunta a esta carpeta
(la del código). Si en el futuro alguien busca el script "dentro de Análisis
Financiero", no está ahí — está acá.

## Origen del playbook de KPIs

El 2026-07-20 el usuario dejó temporalmente `Ejemplo de indicadores.xlsx` en la
raíz de `Finanzas QUEMPIN/` — un análisis real de 4 proyectos anteriores de la
empresa (con tablas dinámicas y referencias a RRHH/Órdenes de Compra externas).
**Ese archivo se elimina del repo y no se debe buscar ni depender de él** — las
fórmulas extraídas, los 2 bugs encontrados en él (fórmula de "Productividad
Materiales" inconsistente entre proyectos; mezcla de bases IVA entre ingreso y
costos) y las correcciones aplicadas quedan documentadas en el spec
(`docs/superpowers/specs/2026-07-20-analisis-financiero-design.md`, sección
"Playbook de KPIs") y resumidas en `CLAUDE.md`. Si en el futuro aparece un
archivo con nombre parecido, no asumir que es el mismo ni que sigue vigente.

## Estilo visual replicado desde el Excel armado a mano (2026-07-21)

El usuario había formateado a mano solo la hoja "Proyectos" (encabezado en
negrita/centrado/wrap, alto de fila 46.2, relleno de color por grupo de
columna usando 4 colores de theme, formato moneda en columnas de montos).
"Detalle Costos Reales" e "Indicadores" quedaban sin ningún estilo porque se
regeneran 100% en cada corrida. A pedido explícito del usuario ("utiliza un
formato similar para todas las hojas"), se agregó `aplicar_estilo_visual(wb)`
en `Sistema/analisis_financiero.py` que replica ese mismo lenguaje visual en
las 3 hojas y se llama en `ejecutar()` justo antes de `wb.save()`.

- Los 4 colores (`COLOR_IDENTIFICACION`/`COLOR_COSTO_PROYECTADO`/
  `COLOR_COSTO_REAL`/`COLOR_DERIVADO`) son theme colors extraídos del archivo
  original del usuario, reutilizados por grupo semántico de columna en las
  3 hojas (no son una paleta inventada).
- **Bug encontrado al implementar**: `ws.column_dimensions[col].width` NO es
  `None` por defecto en openpyxl -- autovivifica a `13.0` apenas se accede.
  Para detectar "el usuario ya fijó un ancho a mano" hay que revisar
  `columna in ws.column_dimensions` **antes** de tocar esa columna, nunca
  `.width is None` (eso nunca dispara y pisaría anchos por defecto sin
  querer). Ver comentario en el código junto a `aplicar_estilo_visual`.
- Solo se fija ancho de columna si no había uno manual ya guardado; el color
  de encabezado y el formato numérico sí se reaplican siempre (son
  estructurales, no datos del usuario).

## Resaltado de celdas de ingreso manual en "Proyectos" (2026-07-28)

A pedido explícito del usuario ("que se destaquen todas las casillas que
requieren ingreso manual, para que nadie se confunda a la hora de ingresar
datos"), se agregó `aplicar_resaltado_celdas_manuales(wb)` en
`Sistema/analisis_financiero.py`, llamada en `ejecutar()` justo después de
`aplicar_estilo_visual(wb)`.

- **Rellena de amarillo (`FFF2CC`) + cursiva** las 11 columnas que el usuario
  escribe a mano en "Proyectos": TAG, Nombre, Estado, Fecha de inicio, Fecha
  de cierre, Monto de Venta, las 4 columnas "...Proyectado(s)" y "Mano de
  Obra Real". Reutiliza la convención "cursiva = editable a mano" que ya
  usa Centro de Costos, sumando relleno propio para que se note más.
- **"Cliente" y "Categoría" quedan explícitamente afuera** aunque viven en
  el mismo bloque que `asegurar_formulas_proyectos` nunca reescribe: ambas
  se autocompletan solas (`asegurar_columna_cliente` /
  `asegurar_categoria_proyectos`) y ya tienen su propio lenguaje visual
  (rojo = pendiente de revisión, azul marino = confirmado). Las columnas de
  fórmula (Materiales/Equipos/Otros Reales, Totales, Márgenes, Desviación %)
  tampoco se resaltan — el contraste sin relleno hace evidente qué no se
  debe tocar a mano.
- **Pre-formatea un mínimo de 60 filas** aunque no haya proyectos cargados
  todavía, para que el libro sirva de plantilla vacía; se extiende 20 filas
  más allá de la última fila con TAG real. La última fila con datos se
  calcula leyendo valores de la columna A, nunca `ws.max_row` a secas —
  `ws.max_row` queda inflado por el propio relleno aplicado en corridas
  anteriores (openpyxl cuenta cualquier celda con estilo, no solo con
  valor) y usarlo directo habría hecho crecer el rango sin límite en cada
  corrida.
- Se agrega una celda de leyenda en la columna siguiente a la última
  (`V1`, ancho 45, wrap) explicando la convención, mismo patrón que la
  leyenda al pie de cada hoja de Centro de Costos.
- Aplicado al archivo real (`Análisis de Proyectos 2026.xlsx`, con backup previo
  vía `hacer_backup`) el mismo día — 5 proyectos ya cargados (UMAG, CFLI,
  CCON, GGEN, MLER) quedaron con sus columnas manuales resaltadas sin que
  se tocara ningún valor.

## Reordenamiento de "Categoría" y corrección de Cliente UMAG (2026-07-28)

A pedido del usuario: (1) mover la columna "Categoría" de "Proyectos" para
que quede inmediatamente a la derecha de "Cliente" (antes era la última
columna), "siguiendo el formato visual"; (2) corregir el Cliente del
proyecto UMAG, que había quedado como "UMAG" (auto-derivado del nombre del
proyecto, que también es "UMAG") en vez de su nombre real, "Universidad de
Magallanes".

- **Código**: `HEADERS_PROYECTOS` reordenado. `ESTILO_COLUMNAS_PROYECTOS`
  (hardcodeado por letra) se refactorizó a `ESTILO_COLUMNAS_PROYECTOS_POR_
  NOMBRE` + conversión vía `LETRA_COL_PROYECTOS` — un dict por letra fija se
  desalinea apenas cambia el orden de columnas, exactamente el tipo de bug
  que ya causó el incidente real de Indicadores este mismo día (ver
  `asegurar_estructura_workbook`, docstring). `NOMBRES_COLUMNAS_MANUALES_
  PROYECTOS` (resaltado de celdas manuales, sección anterior) no necesitó
  ningún cambio — ya estaba indexado por nombre, no por letra, así que el
  reordenamiento fue gratis para esa función. Categoría entra al grupo
  visual `COLOR_IDENTIFICACION` (mismo que Cliente/Estado/fechas).
- **11 tests rotos por letras hardcodeadas** (`test_formulas_proyectos.py`,
  `test_formulas_indicadores.py`, `test_nota_evaluacion.py`,
  `test_hoja_clientes.py`, `test_ejecutar.py`, `test_estructura_workbook.py`,
  `test_resaltado_manual.py`) — todos reescritos para resolver columnas por
  nombre vía `af.HEADERS_PROYECTOS.index(...)` / `af.LETRA_COL_PROYECTOS`,
  nunca por letra o índice fijo, para que un futuro reordenamiento no vuelva
  a romperlos uno por uno.
- **Migración del archivo real**: `asegurar_estructura_workbook` nunca pisa
  un encabezado ya escrito en "Proyectos" (regla de oro) — cambiar el código
  no reordena solo un archivo ya existente. Se migró a mano
  `Análisis de Proyectos 2026.xlsx` (con backup previo): se leyeron los valores
  manuales de las 5 filas de proyecto (UMAG, CFLI, CCON, GGEN, MLER) en el
  layout viejo, se recreó la hoja "Proyectos" en blanco, se regeneró con el
  esquema nuevo (`asegurar_estructura_workbook` ya actualizado) y se
  reescribieron los valores manuales en sus columnas nuevas. Categoría,
  Materiales/Equipos/Otros Reales, Totales, Márgenes y Desviación % no se
  preservaron a mano — se recalculan solos en el siguiente `ejecutar()`
  (nunca son "manuales" en sentido estricto, ver sección anterior).
- **Cliente de UMAG**: se escribió "Universidad de Magallanes" directo en la
  celda al momento de reescribir los valores manuales, en vez de dejar que
  `asegurar_columna_cliente` la auto-derivara (que habría vuelto a poner
  "UMAG", igual al nombre del proyecto). Como esa función solo completa
  celdas vacías (`if celda.value: continue`), el valor corregido queda a
  salvo en corridas futuras sin necesitar el flujo de "pendiente"/
  "confirmado".

## Nota de Proyecto, CLTV de Clientes y Glosario KPIs (brainstorming, 2026-07-21)

- **"Nota" es 100% automática** (no manual, no híbrida) — decisión explícita
  del usuario tras preguntarle las 3 opciones. Escala 0-100, aprobatoria
  ≥55, rentabilidad domina el peso (70% margen neto % vs. objetivo 25%, 30%
  control de desviación total).
- **"CLTV" es sobre CLIENTES, no proveedores** — el usuario pidió
  proveedores primero (confundiendo con el "Proveedor" de Centro de Costos,
  que es un dato de COSTOS/compras) y corrigió a mitad del brainstorming: lo
  que quería era evaluar a quién QUEMPIN le VENDE (clientes), usando el
  archivo de ejemplo AGORA (CLTV por proyecto) como referencia. Si en el
  futuro se pide "evaluar proveedores", es un feature DISTINTO y nuevo, no
  este.
- **"Cliente" se deriva automáticamente + fuzzy-match**, nunca pregunta en
  vivo (el módulo corre encadenado y no bloqueante al `run` de Centro de
  Costos) — coincidencia exacta se asigna sola, similar-no-exacta queda
  "Pendiente de revisión" (mismo patrón rojo/azul marino que Centro de
  Costos), sin parecido se registra como cliente nuevo sin marca.
- **Ambigüedad resuelta del archivo de ejemplo AGORA**: "Vida del cliente" y
  "Frecuencia de compra" del archivo original mezclaban conceptos sin
  fórmula consistente entre filas — este módulo define "Vida del cliente" =
  conteo total de proyectos, "Meses activo" = ventana entre el primer y
  último proyecto (mínimo 1 mes), "Frecuencia" = Vida ÷ (Meses activo ÷ 12).
  Verificado aritméticamente contra los totales del archivo de ejemplo
  (`CLTV = AOV × Frecuencia × Vida × Margen` reproduce el CLTV total como
  promedio simple de los CLTV individuales).
- **Glosario KPIs es una hoja nueva, no comentarios de celda** — a pedido
  explícito del usuario ("que elementos utiliza y en qué se traduce"),
  elegido sobre comentarios de encabezado por ser más legible de corrido y
  más simple de mantener en openpyxl.
- **KPIs adicionales que el usuario mencionó querer agregar después
  quedaron fuera de este spec a propósito** — decisión explícita de cerrar
  este diseño primero en vez de mezclar alcance con features aún sin
  definir.
- **Bug encontrado en el propio test del plan**: el test 5 de
  `test_clientes_pendientes.py` (`test_pendientes_se_acumulan_entre_corridas`)
  seteaba `ws2.cell(..., value=None)` para "simular" un cliente ya
  registrado en otra fila — eso es un no-op (la celda ya era `None`), así
  que el escenario nunca se armaba. Se corrigió para pre-llenar la celda con
  el valor real (`"AGCID Febrero"`), que es lo que el comentario del test ya
  describía.

Diseño completo:
[`docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md`](../docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md)
(ruta relativa a la raíz de `Finanzas QUEMPIN/`).

## Reportes PDF (implementación, 2026-07-24)

- **El contenido de cada reporte lo redacta el agente, no un script** — a
  diferencia del resto del módulo (Excel 100% generado por
  `analisis_financiero.py`), `Reportes/` solo prepara los datos
  (`datos_reportes.py`), el layout/marca (`brand.py`, `graficos.py`) y el
  renderizado a PDF (`motor_reportes.py`); la redacción del análisis en sí
  (qué destacar, cómo interpretar una desviación, el resumen ejecutivo) la
  hace el agente en el momento de generar cada reporte, no está hardcodeada
  en Python.
- **El manifiesto de obsolescencia (`estado_reportes.py`) no dispara
  generación automática** — `detectar_desactualizados` solo informa qué
  entidades tienen datos más nuevos que su último reporte generado (o nunca
  tuvieron uno); generar el PDF sigue siendo una acción explícita (`driver.py
  run` del skill, o el aviso de Centro de Costos que solo recomienda correr
  `status`). Decisión deliberada para no regenerar PDFs caros/costosos en
  cada `run` de Centro de Costos sin que el usuario lo pida.
- **Dependencia con el plan de Cliente/CLTV**: los reportes por cliente
  (`paquete_datos_cliente`) necesitaban la columna "Cliente" y la hoja
  "Clientes" (CLTV) del plan de nota-clientes. Esa dependencia ya estaba
  resuelta en `master` antes de esta tarea — el plan de nota-clientes quedó
  marcado completo en el commit `ccbeb05` ("docs(analisis-financiero): marcar
  completado el plan de nota-clientes"), sobre la integración funcional
  hecha en `b8717d1` ("feat(analisis-financiero): integrar Cliente/CLTV/
  Glosario KPIs al flujo de ejecutar()"); ambos son ancestros del HEAD de
  `master` al momento de implementar Reportes PDF.

## Estándar de contenido y layout de 2 páginas (brainstorming, 2026-07-24)

- **El contenido sigue redactándolo el agente** (sin cambios ahí), pero
  ahora hay un checklist obligatorio (resumen ejecutivo, fortalezas,
  debilidades, análisis de KPIs interpretado, ≥1 gráfico puntual, notas de
  cierre estratégicas) y la tabla de KPIs **ya no es una selección
  editorial — siempre van todos los indicadores relevantes de la entidad**.
  Solo la prosa (qué se comenta) sigue siendo discreción del agente.
- **Layout fijo de 2 páginas** vía `<div class="pdf-pagina">` (CSS nuevo en
  `Reportes/brand.py`, `page-break-after: always` / `auto` en la última):
  página 1 = panel de verificación 100% visual/tabular con estructura fija
  (mismo orden de secciones siempre, aunque el contenido varíe por tipo de
  entidad); página 2 = el análisis narrativo, con estructura libre y
  gráficos puntuales adicionales si el agente los considera necesarios.
- Aplica a Proyecto/Cliente/Categoría. **La comparación ad-hoc queda
  explícitamente fuera** — no tiene layout definido todavía.
  **Recordatorio pendiente**: la próxima vez que el usuario pida trabajar
  o generar un reporte de comparación, hay que definir su estructura con
  él antes de redactarlo — no reutilizar el layout de arriba sin más.
- Diseño completo: addendum §10 de
  [`docs/superpowers/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md`](../docs/superpowers/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md).
- **Verificado generando `proyecto:UMAG` real (2026-07-24)**: la primera
  versión del contenido (tarjetas de KPI + 2 tablas + 2 gráficos en página 1,
  5 párrafos en página 2, con el CSS base de `brand.py` sin más) se
  desbordó a **3 páginas** (confirmado con `pypdf`, no solo a ojo). Hizo
  falta agregar un `<style>` compacto al `contenido_html` (fuentes ~9.5-11px,
  paddings de tabla reducidos a `2px 6px`, tarjetas de KPI más chicas, radio
  de dona 48 en vez de 80, alto de barra 180 en vez de 220-280) y organizar
  la página 1 en 2 columnas (`.fila-2-col`) en vez de todo apilado — recién
  ahí quedó en 2 páginas exactas. **Al redactar cualquier reporte nuevo,
  partir directamente con este nivel de densidad** (no con el tamaño de
  fuente/padding por defecto de `CSS_BASE_REPORTE`, pensado para una sola
  página de contenido liviano) y verificar el conteo de páginas con `pypdf`
  antes de darlo por bueno, no asumir que "se ve como 2 páginas" en el HTML.

## Revisión de estándar tras feedback visual del PDF (2026-07-24)

Tras ver el PDF real de `proyecto:UMAG` (v1 del estándar de 2 páginas), el
usuario pidió 7 ajustes concretos, todos ya implementados en `graficos.py`/
`brand.py` (funciones nuevas, reusables por cualquier reporte futuro) y
aplicados en el reproceso de `proyecto:UMAG`:

- **Los gráficos de dona/barras ahora requieren leyenda de color** —
  `graficos.leyenda_html(etiquetas, colores)` (función nueva) genera el
  HTML de swatches; ninguno de los dos gráficos SVG trae leyenda propia.
- **Las barras comparativas por categoría de gasto ya no son todas del
  mismo color** — `grafico_barras_svg` acepta `colores` (una por barra) y
  `opacidades` (para diferenciar Proyectado/Real dentro de la misma
  categoría sin cambiar el color base). Paleta usada en UMAG: Materiales =
  naranjo, Equipos = gris oscuro, Mano de Obra = negro, Otros = gris claro
  — mismo mapeo color↔categoría en la dona y en las barras, para que una
  sola leyenda sirva para ambas.
- **Los KPIs fuera de lo esperado van en negrita/naranjo** — nueva clase
  CSS `table.tabla-reporte td.alerta` en `brand.py`. Qué cuenta como "fuera
  de lo esperado" es criterio del agente al redactar (en UMAG: desviaciones
  ≥30% en cualquier sentido, y KPIs muy por sobre el objetivo del
  playbook) — no hay un umbral hardcodeado en código.
- **El encabezado (logo + título + fecha) ahora se repite en cada página
  física, no solo en la 1ª** — función nueva `brand.encabezado_html(titulo,
  generado_el)` (versión compacta, clase `reporte-header--pagina`) que el
  agente inserta a mano al inicio de cada `pdf-pagina` siguiente a la
  primera. **Esto reemplaza la regla anterior** ("el header va una sola vez
  arriba de la página 1") — ver SKILL.md y el addendum del spec, ya
  actualizados.
- **Página 1 usa el espacio de forma menos apretada** que la v1 (que dejaba
  bastante blanco abajo): radio de dona 48→58, alto de barras 180→210,
  fuentes de tabla 9.5px→10px, tarjetas de KPI un poco más grandes — sigue
  siendo un layout compacto de 2 columnas, pero menos al límite.
- **Página 2 pasa de prosa densa a listas escaneables** (`<ul>`/`<ol>` con
  `<strong>` en los datos clave de cada punto) para Fortalezas/Debilidades/
  Notas estratégicas, en 2 columnas (Fortalezas | Debilidades) para
  aprovechar el ancho; Resumen ejecutivo y Análisis de KPIs siguen en
  prosa (son explicativos, no una lista de puntos). Tamaño de fuente subió
  de ~10.5px a 13px — página 2 tiene más margen de espacio que página 1
  porque ya no compite por altura con 2 gráficos + 2 tablas.
- **Reverificado con `pypdf` tras todos los cambios**: sigue en exactamente
  2 páginas pese a sumar el encabezado repetido y aumentar tamaños de
  fuente — el ahorro de las listas (vs. párrafos largos) compensó el
  espacio adicional que toma el encabezado + letra más grande en página 2.

## 5 mejoras autónomas de calidad (financiera + visual, 2026-07-25)

A pedido explícito del usuario ("realiza 5 loops buscando mejorar la
calidad de los reportes, desde una perspectiva financiera profesional y
visual, sin preguntar"), se hicieron 5 mejoras concretas al estándar
vigente (no un rediseño — todas construyen sobre `graficos.py`/`brand.py`
ya existentes) y se aplicaron a los 3 reportes reales generados hasta
ahora:

1. **CSS de página 1/2 centralizado en `brand.py`** (`.pdf-pagina.p1` /
   `.pdf-pagina.p2` dentro de `CSS_BASE_REPORTE`) — antes cada script
   ad-hoc copiaba su propio `<style>` inline, con riesgo de divergencia
   visual entre reportes. Ahora los 3 scripts solo usan las clases.
2. **Criterio "KPI fuera de rango" centralizado y con umbral explícito**:
   `brand.es_kpi_fuera_de_rango(nombre_kpi, valor)` (margen neto muy sobre
   objetivo o negativo, rentabilidad sobre costo fuera de [1x, 4x),
   |desviación| ≥ 30%) reemplaza el `set` hardcodeado que se copiaba en
   cada script. `brand.OBJETIVO_MARGEN_NETO` / `UMBRAL_DESVIACION_ALERTA`
   documentan los umbrales en un solo lugar.
3. **Columna "Referencia" en la tabla completa de KPIs**
   (`brand.referencia_kpi(nombre_kpi)`) — cada fila muestra el
   objetivo/rango esperado del playbook (ej. "Objetivo playbook: 25%"),
   para que la tabla se explique sola sin depender de leer la página 2.
4. **Porcentaje por segmento en la dona** (`grafico_dona_svg(...,
   mostrar_porcentaje=True)`) — segmentos con ≥6% del total muestran su %
   en texto blanco sobre el color, no solo diferenciación por color.
5. **Pie de página con fecha de corte y fuente de los datos**
   (`brand.construir_html(..., fecha_corte=...)` → "Datos al {fecha} --
   Fuente: Centro de Costos + registro manual") — usa la fecha de cierre
   real del proyecto (o la más reciente entre proyectos de un cliente/
   categoría), distinta de `generado_el` (cuándo se generó el PDF).

**Reverificado con `pypdf` tras las 5 mejoras**: los 3 reportes
(`proyecto:UMAG`, `cliente:UMAG`, `categoria:I+D+i`) siguen en exactamente
2 páginas, con la nota de fuente presente en el footer de la página 2.
Suite de tests de `Reportes/`: 59 tests, todos pasando (9 nuevos: 3 sobre
porcentaje en dona, 6 sobre `es_kpi_fuera_de_rango`/`referencia_kpi`/nota
de fuente).

## Corrección visual de página 1 tras revisión con imagen real (2026-07-26)

El usuario pidió 3 ajustes sobre `proyecto:UMAG` — colores por categoría de
gasto en las barras comparativas (ya estaba implementado desde el
2026-07-24, pero lo repitió), que el valor numérico de cada barra sea
**siempre** visible, y usar mejor el espacio de la página 1 (llenar la
página completa). Esta vez, en vez de razonar sobre el HTML/CSS a ciegas,
se renderizó la página 1 a PNG con PyMuPDF (`fitz`, ya estaba instalado) y
se inspeccionó la imagen antes y después de cada cambio — reveló un bug
real que el conteo de páginas de `pypdf` nunca iba a detectar:

- **Bug encontrado**: la barra "Otros Proyectado" (el valor más grande,
  3.720.000) llegaba justo al borde del `viewBox` de
  `grafico_barras_svg` y su número quedaba cortado — la función escalaba
  la barra más larga al 100% del ancho disponible sin reservar espacio
  para el texto del valor. Fix: nuevo parámetro `margen_valor` (default 76)
  que reserva ese espacio siempre; documentado en `graficos.py` y en el
  Gotcha correspondiente de `SKILL.md` para que no se repita al ajustar
  tamaños en un reporte futuro.
- **Nuevo parámetro `decimales`/`sufijo`** en `grafico_barras_svg` — los
  "Costo % de venta" (0,9%-6,9%) redondeados a entero perdían precisión
  visible; ahora se puede pedir `decimales=1, sufijo="%"`.
- **Página 1 ya no está sobre-comprimida**: la densidad de fuente/padding
  del 2026-07-24 (pensada para garantizar que cupiera en 1 página) dejaba
  casi la mitad de la página en blanco una vez renderizada — la página SÍ
  tenía margen de sobra. Se relajó la densidad en `brand.py`
  (`.pdf-pagina.p1`) y se agregó contenido que faltaba: gráfico nuevo
  "Estructura de costos (% de venta)" (una serie por categoría, mismo
  color que la dona/leyenda) que responde una pregunta que antes solo
  estaba en la tabla como números sueltos. La dona y su leyenda ahora van
  lado a lado (`div.dona-con-leyenda`, clase nueva en `brand.py`) en vez de
  apiladas, para un uso más compacto de esa columna.
- **Iteración de tamaño**: agrandar demasiado (radio de dona 85, alto de
  barra 260, fuente de tabla 12px) volvió a desbordar a 3 páginas —
  confirmado con `pypdf`, luego se ajustó hacia abajo (radio 64, alto 225,
  fuente 11px) hasta volver a 2 páginas exactas, verificado de nuevo con
  la imagen (ya no queda ~45% de blanco, sí un margen razonable ~10-15%).
- **Aplicado a los 3 reportes reales** (`proyecto:UMAG`, `cliente:UMAG`,
  `categoria:I+D+i`) — los 3 siguen en 2 páginas (`pypdf`) y se
  inspeccionaron visualmente uno por uno.
- **Lección para reportes futuros**: `pypdf` (conteo de páginas) y la
  inspección visual con `fitz` cubren cosas distintas — usar ambos. El
  conteo de páginas no detecta texto cortado en el borde de un SVG ni
  espacio en blanco mal distribuido; la imagen no reemplaza verificar que
  sigue siendo exactamente 2 páginas.

## Gráfico comparativo Proyectado vs Real rediseñado (2 iteraciones, 2026-07-26)

El usuario insistió en que, pese al fix de recorte de valores del
2026-07-26 anterior, seguía sin distinguirse bien la diferencia entre
tipos de costo en el gráfico "Costos Proyectados vs. Reales por
categoría" — pidió explícitamente 2 iteraciones de un `/loop` autónomo
para resolverlo. Diagnóstico: el enfoque anterior (`grafico_barras_svg`
con `opacidades`) usaba el mismo tono para Proyectado/Real de una
categoría, solo más claro/oscuro — visualmente insuficiente para separar
"Equipos" de "Otros" (ambos grises) o para agrupar el par Proyectado/Real
de una misma categoría.

- **Iteración 1**: función nueva `graficos.grafico_barras_comparativo_svg`
  — agrupa por categoría (nombre una sola vez, no repetido en cada barra),
  Proyectado con relleno **achurado** (patrón SVG diagonal, no opacidad) y
  Real con relleno sólido, banda de fondo alternada por categoría, línea
  separadora entre grupos. Reemplaza el patrón "opacidad" documentado en
  `SKILL.md`/`MEMORY.md` del 2026-07-24 — ese patrón queda obsoleto para
  este caso de uso (Proyectado vs Real), aunque `opacidades` sigue
  existiendo en `grafico_barras_svg` para otros usos futuros.
- **Iteración 2**: cuadro de color + acento vertical junto al nombre de
  cada categoría, mismo color que sus barras — refuerza la identificación
  por color incluso antes de leer el achurado/relleno o las etiquetas.
- **Verificación por imagen, no solo `pypdf`**: como el bug de recorte
  anterior no lo detectaba el conteo de páginas, se generó cada iteración
  a una ruta temporal (`RUTA_SALIDA_OVERRIDE` vía variable de entorno en
  los 3 scripts ad-hoc, para no pelear con el lock de OneDrive/visor de
  PDF sobre el archivo real) y se inspeccionó con `fitz` antes de aplicar
  el cambio a los 3 reportes.
- **Aplicado a los 3 reportes** (proyecto/cliente/categoría), 64 tests
  pasando (6 nuevos para `grafico_barras_comparativo_svg`).
- **Bloqueo de escritura final (resuelto)**: los 3 PDF reales estaban
  abiertos en el visor y `motor_reportes.renderizar_pdf` no pudo
  sobrescribirlos (`PermissionError` de Windows/OneDrive, no un bug del
  código). Se verificó todo por imagen contra copias temporales primero;
  una vez cerrados los PDF, se re-corrieron los 3 scripts sobre las rutas
  reales sin problema.

## Depuración del playbook de KPIs + fix de sesgo en la Nota (2026-07-28)

A pedido explícito del usuario (3 decisiones de diseño ya aprobadas antes
de implementar, tras un análisis previo del agente sobre el Excel real de
QUEMPIN con 5 proyectos cargados, solo UMAG "Terminado" con datos
completos):

1. **Se eliminaron 5 KPIs redundantes de "Indicadores"/"Glosario KPIs"/
   `brand.py`**: "Rentabilidad sobre costo" (= margen/(1-margen) de "Margen
   neto %", misma información en otra escala) y las 4 "Productividad
   Materiales/Equipos/MO/Otros" (= 1 / "Costo % de venta" de esa categoría,
   invertidas). No aportaban señal nueva sobre lo que ya daban "Margen neto
   %" y "Costo % de venta".
2. **Se corrigió el sesgo de la Nota del Proyecto**: el componente de
   control de desviación (30%) usaba `ABS(desviación total)`, penalizando
   gastar de menos igual que gastar de más -- pese a que ahorrar ya sube el
   margen (capturado en el 70% de rentabilidad), era una especie de doble
   castigo. Ahora `MAX(0, desviación)` anula el término para cualquier
   proyecto en o bajo presupuesto: ese componente da el puntaje máximo
   (100) sin premio ni castigo extra. Solo resta puntos si Real >
   Proyectado (sobrecosto real).
   - **Verificación a mano contra UMAG** (Venta 14.563.245, Total Real
     5.472.679, Total Proyectado 7.713.765, Margen Real 9.090.566, margen
     neto 62.42%, desviación total -29.05% -- UMAG ahorró): con ABS(), Nota
     = 91. Sin ABS(), Nota = **100** (score margen ya tope 100, score
     desviación ahora también tope 100 al no penalizar el ahorro).
3. **4 KPIs nuevos** (de los 6 que un análisis previo del agente había
   propuesto como "útiles ya con 1 proyecto" -- se implementaron solo estos
   4, no los otros 2 que quedaban para cuando haya más proyectos/clientes:
   "Margen Real por mes de ejecución" e "Ingreso/Margen acumulado por
   cliente"):
   - **Ahorro/Sobrecosto neto en $** (Costo Proyectado − Costo Real, por
     categoría y total) -- traduce la desviación % a pesos concretos.
   - **Desviación % Total** como columna visible en "Indicadores" (ya
     existía embebida en la fórmula de la Nota, referenciando
     `Proyectos!T`, ahora también expuesta directamente).
   - **Estructura % del costo real (mix)** por categoría (Costo Real de la
     categoría / Costos Totales Real, suma 100%) -- distinto de "Costo %
     de venta" (que no suma 100%, no se tocó).
   - **% del Total Real del proyecto** en "Detalle Costos Reales" (Total
     sin IVA de la subcategoría / suma de las filas de ese proyecto EN ESA
     MISMA HOJA -- no el Total Real completo de "Proyectos", que incluye
     Mano de Obra Real manual sin detalle por subcategoría). Verificado que
     suma ~100% por proyecto (UMAG: 6 subcategorías, suma exacta 1.0).

Valores nuevos verificados en UMAG tras correr el pipeline real: Ahorro
Materiales $167.798, Equipos $396.259, MO $800.000, Otros $877.029, Total
$2.241.086 (todo ahorro, ningún sobrecosto); Estructura % Materiales
20.6%, Equipos 9.2%, MO 18.3%, Otros 51.9% (suma 100%); Desviación % Total
-29.05% (columna nueva, mismo valor que ya tenía "Proyectos").

- **Bug real encontrado y corregido durante la implementación**:
  `asegurar_estructura_workbook` usaba el mismo criterio "solo llenar
  encabezados vacíos, nunca pisar uno existente" para las 5 hojas -- correcto
  para "Proyectos" (datos manuales del usuario), pero al reordenar/depurar
  el esquema de columnas de "Indicadores" (18 → 23 columnas, con
  eliminación y reordenamiento, no solo columnas nuevas al final), los
  encabezados viejos se quedaron pisando columnas con fórmulas del esquema
  NUEVO -- ej. la columna C decía "Rentabilidad sobre costo" pero tenía la
  fórmula de "Margen neto %", y aparecieron "Nota del Proyecto"/
  "Evaluación" duplicados en las columnas nuevas del final. **Esto se
  corrió una vez contra el Excel real de la empresa** antes de detectarse
  en la verificación posterior a la corrida -- se restauró desde el backup
  automático inmediatamente anterior (`Respaldos/Julio 2026/Análisis de
  Proyectos - backup 2026-07-28 104326.xlsx`) sin pérdida de datos, se
  corrigió el código (`asegurar_estructura_workbook` ahora reescribe
  completa la fila de encabezados de las 4 hojas 100%-regeneradas --
  "Detalle Costos Reales"/"Indicadores"/"Clientes"/"Glosario KPIs" -- cada
  vez que no coincide con el esquema actual, incluyendo limpiar columnas
  sobrantes si el esquema nuevo es más corto; "Proyectos" mantiene el
  comportamiento append-only original) y se re-corrió con éxito. Se agregó
  un test de regresión (`test_hoja_indicadores_con_esquema_viejo_se_
  reescribe_completa_al_esquema_nuevo` en `test_estructura_workbook.py`)
  que simula exactamente este escenario. **Lección**: "no reescribir datos
  ya presentes" es una regla que aplica a datos MANUALES del usuario, no a
  hojas que el propio script regenera al 100% -- tratarlas igual fue el
  error.
- **Efecto colateral positivo, ya esperado**: al cambiar el set de KPIs,
  `estado_reportes.py` marcó los 3 PDF ya generados (`proyecto:UMAG`,
  `cliente:UMAG`, `categoria:I+D+i`) como desactualizados automáticamente
  (cambia el hash de los datos de entrada) -- no se regeneraron, es una
  tarea aparte que el usuario pedirá si quiere.
- **Bug operativo de CLTV resuelto de paso**: el Excel real tenía
  `_xludf.MAXIFS`/`_xludf.MINIFS` en la hoja "Clientes" (marca que deja
  LibreOffice/Google Sheets al re-guardar el archivo fuera de Excel) --
  no era un bug de código (el script siempre escribió `MAXIFS`/`MINIFS`
  nativos), se resolvió solo al correr el pipeline real de nuevo, que
  reescribe esas fórmulas. Confirmado con `zipfile` + búsqueda de texto
  sobre el XML interno: cero ocurrencias de `_xludf` en el archivo tras la
  corrida.
- Suite completa tras los 3 cambios: 195 tests (93 `Sistema/` + 68
  `Reportes/` + 33 `Visualizador Web/`), todos pasando.

## Segunda tanda de KPIs nuevos: Peso en cartera + Margen por día (2026-07-28)

Misma fecha que la depuración anterior, tras un nuevo análisis del agente
que propuso 6 KPIs candidatos. El usuario aprobó 2 de 3 que ya estaban
"listos con los datos actuales" (el tercero, "Cumplimiento de plazo",
necesitaba un dato manual nuevo -- fecha de plazo comprometido -- que el
usuario decidió NO agregar por ahora; los otros 3 candidatos ya habían
quedado descartados en el análisis previo del 2026-07-28 por necesitar más
proyectos/clientes cargados).

- **Peso del proyecto en la cartera de ventas (%)**: `Monto de Venta del
  proyecto / Σ Monto de Venta de TODOS los proyectos con venta cargada`
  (cualquier Estado, no solo "Terminado" -- criterio explícito del
  encargo). Columna X de "Indicadores". Mide riesgo de concentración de
  ingresos en un solo proyecto.
- **Margen por día de ejecución**: `Margen Real / (Fecha de cierre − Fecha
  de inicio, en días)`. Columna Y. Si Fecha de cierre está vacía (proyecto
  "en desarrollo"), la fórmula misma queda en `""` vía
  `IF(Fecha de cierre="","",...)` -- no hay una rama de código Python que
  decida "esta fila no lleva fórmula"; el guard vive dentro de la fórmula
  de Excel para que se recalcule solo si el usuario completa la fecha
  después. `MAX(1, días)` evita `#DIV/0!` si Fecha de cierre = Fecha de
  inicio (mismo patrón que "Meses activo" en la hoja "Clientes").
- **Ambas son columnas nuevas al final de "Indicadores"** (no reordenan ni
  tocan ninguna de las 23 columnas existentes) -- decisión deliberada para
  minimizar el riesgo de repetir el incidente de desalineación de
  encabezados del punto anterior; con el fix de `asegurar_estructura_
  workbook` ya en el código, un reordenamiento también habría sido seguro,
  pero agregar al final es más simple de verificar.
- Se agregaron ambas entradas a "Glosario KPIs" (mismo formato que las
  existentes).
- **No se tocó `Reportes/kpis_recalculados.py` ni `Reportes/brand.py`** --
  fuera del alcance pedido explícitamente para esta tarea. Efecto: estos 2
  KPIs no aparecen todavía en los reportes PDF (que leen del espejo
  Python, no de las fórmulas de Excel). Si se quiere que los reportes los
  incluyan, es una extensión aparte.

**Precaución explícita seguida en esta tarea** (pedida por el coordinador
tras un incidente): no se usó ningún recálculo externo (LibreOffice,
Google Sheets, etc.) sobre el Excel real para "verificar valores" -- toda
verificación fue por lectura de fórmulas con openpyxl (`data_only=False`,
confirma que la fórmula está bien escrita) más aritmética manual en Python
sobre los valores fuente leídos con `data_only=True`, nunca guardando el
archivo con otra herramienta que no sea el propio `driver.py run`. Los
valores en caché de las fórmulas quedan `None` hasta que el usuario abre
el archivo en Excel real -- eso es esperado, no es un bug.

Verificación a mano en UMAG (venta 14.563.245, Fecha de inicio 2026-01-01,
Fecha de cierre 2026-02-01 = 31 días, Margen Real 9.090.566): Margen por
día = 9.090.566 / 31 ≈ $293.244/día. Peso en cartera depende de la suma
total de venta de los 5 proyectos cargados (solo UMAG tiene venta
cargada hoy) -- con un solo proyecto con venta, su peso da 100%; se
recalculará solo cuando se carguen ventas de otros proyectos, sin correr
el script de nuevo.

## Pendientes que dependen del usuario

El script (`Sistema/analisis_financiero.py`, 71 tests), el skill
(`.claude/skills/Registro_Analisis_Financiero/`, comandos
`status`/`run`/`confirmar-cliente`) y el enganche automático al `run` de
Centro de Costos (PASO 12d de `auditor_centro_costos.py`) ya están
implementados — ver detalle e historial de las 12 tareas originales en
`docs/superpowers/plans/2026-07-20-analisis-financiero-implementacion.md` y
de la extensión de Nota/Clientes/Glosario en
`docs/superpowers/plans/2026-07-21-analisis-financiero-nota-clientes-implementacion.md`
(rutas relativas a la raíz de `Finanzas QUEMPIN/`). Lo que queda pendiente:

- `Análisis de Proyectos 2026.xlsx` está vacío — no hay proyectos cargados todavía,
  así que nada de esto se ha ejercitado contra datos reales de QUEMPIN SpA.
- El dashboard HTML (Visualizador Web de este módulo) está fuera de alcance v1
  a propósito — el usuario ya indicó que esa es la forma de presentación a
  mediano plazo, pero no se construye hasta más adelante.

## Fix: `#NOMBRE?` en hoja "Clientes" — MAXIFS/MINIFS sin prefijo `_xlfn.` (2026-07-28)

Las columnas "Meses activo" y "Frecuencia de compra" (que depende de ella) daban
`#NOMBRE?` en TODAS las filas de la hoja "Clientes", y eso se propagaba en
cascada a CLTV/Clasificación. El usuario reportó "puede ser que la formula
esta en ingles y el excel en español" — **el diagnóstico real no es
traducción de idioma** (los `.xlsx` siempre guardan las fórmulas en inglés
canónico internamente; Excel las traduce solo para mostrarlas en pantalla,
sin importar el idioma de la UI). El bug real es un **gotcha conocido de
openpyxl**: `MAXIFS`/`MINIFS` son funciones "nuevas" (Excel 2016+, parte de
las "future functions" del spec OOXML) y openpyxl las escribe crudas en el
XML — Excel exige el prefijo `_xlfn.` para reconocer esas funciones cuando
se escriben así (no vía la UI de Excel); sin el prefijo, Excel las trata
como función desconocida/definida por el usuario → `#NAME?`/`#NOMBRE?`.

Fix en `asegurar_hoja_clientes` (columna "Meses activo",
`analisis_financiero.py`): `MAXIFS(` → `_xlfn.MAXIFS(` y `MINIFS(` →
`_xlfn.MINIFS(`. Excel sigue mostrando `MAXIFS`/`MINIFS` sin el prefijo al
abrir el archivo — el prefijo es solo la representación interna que
openpyxl necesita escribir. Test actualizado en
`test_hoja_clientes.py::test_formulas_agregan_sobre_proyectos_filtrando_por_columna_cliente`.
Si en el futuro se agregan otras funciones post-2007 (`IFS`, `SWITCH`,
`TEXTJOIN`, `MODE.SNGL`, etc.) escritas directamente vía openpyxl, revisar
si necesitan el mismo prefijo — `SUMIFS`/`AVERAGEIF`/`COUNTIF`/`PERCENTILE`
son anteriores a 2007 y no lo necesitan.

## Dashboard: Margen neto %, concentración de cartera, y fix de tablas angostas (2026-07-28)

A pedido explícito del usuario, tras un análisis previo sobre qué KPIs del
playbook depurado ese mismo día convenía graficar o faltaban en el
dashboard (ver sección "Segunda tanda de KPIs nuevos" más arriba):

- **Tile "Margen neto %"** en el panel de detalle de cada proyecto
  (`detalleProyectoHtml`, `Visualizador Web/template.html`) — Margen Real /
  Monto de Venta, calculado inline en JS (no requirió tocar
  `build_visualizador.py`: ambos valores ya viajaban en el snapshot). Era
  el único KPI del playbook que no se mostraba en ninguna parte del
  dashboard pese a ser el componente de mayor peso (70%) de la Nota.
- **Gráfico "Concentración de cartera (peso en ventas)"** — nueva 3ª
  chart-card en la pestaña Proyectos (`chartPesoCartera`, ranking de barras
  igual patrón que "Nota del Proyecto"), usando `peso_cartera_pct` que ya
  calculaba `calcular_peso_cartera()` pero que antes solo se veía un
  proyecto a la vez dentro de su propio panel de detalle — no había forma
  de comparar la concentración de riesgo entre proyectos de un vistazo.
  Tampoco requirió cambios en `build_visualizador.py`.
- **Bug real encontrado con revisión visual en navegador** (Playwright,
  viewport 480px — mismo método que ya encontró bugs reales en el
  visualizador de Centro de Costos, ver su CLAUDE.md "Ciclo de mejora
  continua"): las tablas angostas del panel de detalle (`tabla-costos-
  categoria`, 7 columnas; `tabla-subcategorias`, 4 columnas; la tabla de
  proyectos dentro del detalle de "Categoría") no tenían contenedor de
  scroll horizontal propio ni `min-width` — con `table-layout:fixed` se
  achicaban hasta que los encabezados de columnas vecinas se superponían
  visualmente unos con otros (ilegible). Las 3 tablas principales
  (Proyectos/Clientes/Categoría, `table.viz-table`) tenían el problema
  inverso y más grave: la CSS ya traía `.viz-tablewrap`/`.viz-tablescroll`
  y `min-width:640px` en `table.viz-table` (mismo patrón que Centro de
  Costos), pero el HTML nunca envolvía el `<table>` en esos divs — el
  `min-width` sin contenedor de scroll forzaba a **toda la página** a
  desbordarse horizontalmente (764px de contenido en un viewport de 480px)
  en vez de scrollear solo la tabla.
  - Fix: se envolvieron los 3 `<table class="viz-table">` en
    `<div class="viz-tablewrap"><div class="viz-tablescroll">` (mismo
    patrón ya usado en Centro de Costos), y se agregó `min-width` (480px
    base, 620px para `tabla-costos-categoria`) + su propio
    `.viz-tablescroll` a las 3 tablas del panel de detalle. Verificado con
    Playwright a 480px: `document.body.scrollWidth` volvió a igualar
    `window.innerWidth` (sin overflow de página), y cada tabla ancha
    scrollea dentro de su propio contenedor sin superposición de texto.
  - De paso, la tabla de proyectos dentro del detalle de "Categoría"
    (`tabla-proyectos-categoria`, nueva subclase CSS) heredaba anchos de
    columna pensados para otra tabla de 3 columnas — se le dieron anchos
    propios y se agregó `class="num"` a los `<th>` de Margen Real/Nota para
    que alineen con sus `<td class="num">` (inconsistencia menor, ya
    presente antes de esta tarea).
- Suite completa (209 tests) sigue pasando — ninguno de estos cambios tocó
  `build_visualizador.py` ni la forma del snapshot, solo `template.html`
  (HTML/CSS/JS puro).
- Republicado en el mismo Artifact (ver MEMORY.md del skill
  `Registro_Analisis_Financiero`).

## Filas de proyecto nuevas se crean solas desde Centro de Costos (2026-08-19)

- **Causa del reporte "no se ha actualizado el Excel de Análisis Financiero"**:
  la hoja "Proyectos" es 100% manual — nada creaba una fila nueva cuando
  aparecía un proyecto en Centro de Costos. El mismo día se habían agregado 9
  proyectos nuevos a Centro de Costos (Cremación Concepción, CESFAM Chillán,
  CONAF Puerto Montt, Bomba Wilo Conchalí, Caldera Valdivia, Calderas
  Antofagasta, Comisaría Conchalí, ESFOCAR, Fiscalía Quilpué y Quintero), cada
  uno con costos reales ya calculados en Centro de Costos, pero **ninguno**
  tenía fila en "Proyectos" — por eso no aparecían en ningún lado de Análisis
  Financiero, aunque el resto del Excel sí estaba al día (verificado a $0 de
  diferencia contra Centro de Costos para los proyectos que sí tenían fila).
  Se agregaron las 9 filas a mano esa vez (TAG + Nombre; Cliente/Categoría se
  autocompletaron solos al correr `driver.py run`) y quedaron 2 clientes en
  rojo pendientes de revisión (ver más abajo).
- **Fix permanente, a pedido del usuario**: `ejecutar()` ahora detecta solo
  los prefijos de proyecto que existen en `Master` de Centro de Costos
  (`leer_nombres_proyecto_centro_costos()`, mismo patrón que
  `leer_tipo_proyecto_centro_costos()`) y no tienen fila todavía en
  "Proyectos", y crea la fila con **TAG + Nombre únicamente**
  (`crear_filas_proyectos_nuevos()`) — el resto de columnas queda en blanco.
  Como la fila nueva se agrega a `filas_validas` antes de que corra el resto
  del pipeline, Cliente/Categoría/fórmulas de costos reales/resaltado
  amarillo se aplican solos, igual que a cualquier fila preexistente — no
  hizo falta duplicar esa lógica. `status` (dry_run) previsualiza qué
  proyectos se crearían sin escribir nada; `run` los crea de verdad y lo
  imprime en consola. Corre en los 4 caminos que llaman `ejecutar()`
  (`Registro_Analisis_Financiero run`, `Actualizar_AF`, `Actualizar_CC`,
  `Actualizar_Finanzas`), sin tocar ninguno de esos otros skills.
- **Deliberadamente no se agregó** un fallback para "prefijo sin nombre en
  Master" (contemplado en el diseño original) — al usar `Master` como única
  fuente de qué proyectos existen, todo prefijo candidato tiene nombre por
  construcción; ese caso no puede darse en la práctica, así que no había
  nada que probar ni manejar (YAGNI).
- **Los 2 clientes en rojo pendientes de esa corrida manual siguen
  pendientes** (no los toca este fix, es a propósito): CESFAM Chillán quedó
  sugerido como cliente "Cesfam Limache" y Comisaría Conchalí como "Bomba
  Wilo Conchalí" — coincidencias por nombre de comuna/establecimiento, no por
  ser el mismo cliente real. Corregir a mano en la columna Cliente, no con
  `driver.py confirmar-cliente --todos`.
- Tests nuevos: `Sistema/tests/test_proyectos_nuevos_desde_cc.py` (unitarios
  de las 2 funciones nuevas) + casos en `test_ejecutar.py` (integración,
  incluye dry_run) + `test_driver_registro_af.py` (preview en `status`).
  Suite completa: 430 tests.
- **Actualización el mismo día**: los 2 clientes en rojo de arriba ya se
  corrigieron a mano (`cliente_derivado` en vez de `cliente_sugerido` --
  ambos coincidían con el nombre del propio proyecto) y quedaron en azul
  marino, "Confirmado" en `clientes_pendientes.json` con una nota explicando
  por qué no se usó la sugerencia automática.

## Archivo renombrado a "Análisis de Proyectos 2026.xlsx" (2026-08-19)

- **Motivo**: el usuario reportó sincronización de OneDrive bloqueada en
  `Análisis de Proyectos.xlsx` sin saber por qué. Al intentar el fix que pidió
  (copiar + borrar el original) OneDrive generó un archivo de conflicto
  (`Análisis de Proyectos-QUEMPIN.xlsx`, sufijo = nombre del equipo) y, en los
  segundos siguientes, sobrescribió repetidamente cualquier contenido nuevo
  escrito en esa ruta -- incluso con un nombre de archivo que nunca había
  existido antes. Diagnóstico inicial (mal) fue "alguien lo tiene abierto en
  vivo en otro dispositivo" (metadata interna mostraba `lastModifiedBy:
  Cristobal Monzo`, guardado por Excel real, no por openpyxl). Diagnóstico
  correcto, confirmado dejando pasar ~35s con chequeos de hash cada 5s: era
  OneDrive/Office terminando de procesar la cola de cambios de toda la sesión
  (creación del archivo + 9 filas nuevas + 3 corridas del registrador + fix
  de Cliente + el propio experimento de copiar/borrar) -- no una edición en
  vivo de otra persona. El archivo convergió solo a un estado correcto y
  estable.
- **No se perdió nada**: antes de tocar cualquier cosa se guardó un respaldo
  verificado por hash SHA-256 **fuera de OneDrive** (scratchpad de la sesión);
  cuando se detectó la reversión se restauró desde ahí antes de seguir. Los 2
  archivos que quedaron con contenido viejo/de conflicto se movieron (no se
  borraron) a `Análisis Financiero/_OBSOLETO no usar (conflicto OneDrive
  2026-08-19)/` -- limpiar esa carpeta a mano cuando el usuario confirme que
  ya no los necesita.
- **Fix real**: en vez de pelear más por el mismo nombre de archivo, se creó
  el libro con nombre nuevo (`Análisis de Proyectos 2026.xlsx`, nunca existió
  antes en OneDrive, así que no hereda ningún historial de conflicto) y se
  actualizó `RUTA_EXCEL` en `Sistema/analisis_financiero.py` -- único punto
  del código que fija esa ruta, todo lo demás (`build_visualizador.py`,
  `Reportes/datos_reportes.py`) ya importaba `RUTA_EXCEL` en vez de tener el
  nombre hardcodeado. También se actualizaron las menciones en `CLAUDE.md`
  (este módulo y `Visualizador Web/CLAUDE.md`), este `MEMORY.md`, y los 2
  `SKILL.md` (`Registro_Analisis_Financiero`, `Actualizar_AF`) -- no se tocó
  el nombre de archivo dentro de los tests (usan rutas de `tmp_path`
  aisladas, el nombre literal ahí es arbitrario).
- Verificado estable 35+ segundos sin cambiar de hash, contenido completo (14
  proyectos, fórmulas de costos reales, las 5 hojas) y `driver.py status`
  corriendo de punta a punta contra el archivo real sin errores. Suite
  completa (430 tests) sigue pasando.

## Fix del percentil de Clasificación (Clientes) + curva de la Nota del Proyecto (2026-08-20)

El usuario reportó `#DIV/0!` en la columna "Clasificación" de la hoja
"Clientes" para **todos** los clientes (captura de pantalla), y pidió
además evaluar cómo se estaban calificando los proyectos ahora que hay más
datos reales cargados (15 proyectos, 7 con datos completos).

**Bug 1 — propagación de error en el percentil (root cause, no un fix
superficial)**: `asegurar_hoja_clientes` (columna H, "Clasificación") usaba
`PERCENTILE(Clientes!$G:$G,...)`. `PERCENTILE` de Excel devuelve error para
**todo el rango** si una sola celda es un error — y 5 de los 15 clientes
(Bomba Wilo Conchalí, CONAF Puerto Montt, Calderas Antofagasta, Comisaría
Conchalí, Gastos Generales) tienen `#DIV/0!` en su propio CLTV por no tener
"Monto de Venta" cargado todavía. Eso bastaba para romper la Clasificación
de los otros 10 clientes con CLTV perfectamente válido. Fix: `PERCENTILE` →
`_xlfn.AGGREGATE(16,6,...)` (PERCENTILE.INC con la opción 6, "ignorar
errores") — contiene el error a la fila del cliente afectado, no lo
propaga. Verificado contra el archivo real: los 5 clientes sin venta
cargada son exactamente los de la captura del usuario. Test nuevo:
`test_hoja_clientes.py::test_clasificacion_ignora_errores_de_otros_clientes_en_el_percentil`.
El dashboard web y los reportes PDF nunca tuvieron este bug — ya excluían
clientes con proyectos incompletos antes de calcular el percentil
(`build_visualizador.calcular_clientes` / `kpis_recalculados.calcular_cltv_clientes`,
que sí filtran `CLTV is not None` antes del percentil); solo la fórmula
cruda del Excel lo tenía.

**Hallazgo 2 — efecto techo en la Nota del Proyecto**: de los 7 proyectos
completos, 6 sacaban Nota=100 y el séptimo (Cesfam Constitución) 90 — el
100% caía en "Excelente". Causa: el componente de margen (70% de la Nota)
usaba `MIN(100, margen/0.25*100)` — cualquier margen ≥25% (el objetivo)
topaba en 100. Los márgenes reales de la cartera van de 22% a 99.8%
(mediana ≈68%), muy por sobre el objetivo, así que casi todos saturaban.
El componente de desviación (30%) tenía el mismo efecto por otro motivo
(6 de 7 proyectos vienen 15%-99% bajo presupuesto) pero **no se tocó** --
es una decisión deliberada del 2026-07-28 (no duplicar el premio por
ahorrar, ya capturado en el margen), distinta del caso de margen que sí era
un techo accidental.

- **Propuesta discutida con el usuario antes de implementar** (3 opciones:
  subir el objetivo fijo, curva no lineal, o separar "¿es rentable?" de
  "¿es más rentable que el resto de la cartera?" al estilo percentil de
  Clasificación) — eligió desarrollar la curva no lineal.
- **Curva implementada** (`_score_margen_nota` en `analisis_financiero.py`,
  espejo Excel en `_formula_nota`): lineal 0→`SCORE_MARGEN_EN_OBJETIVO` (70)
  hasta `MARGEN_OBJETIVO_NOTA` (25%, sin cambios), luego
  `70 + 30*(1-EXP(-(margen-0.25)/K))` con `K_MARGEN_NOTA_SOBRE_OBJETIVO =
  0.3186` — asíntota hacia 100 que nunca la toca. K calibrado para que 60%
  de margen (cerca de la mediana real) puntúe ~90.
- **Un solo punto de cambio Python**: a diferencia del bug de Nota de
  2026-07-28 (que estaba duplicado en 3 archivos y se desincronizó),
  `Reportes/kpis_recalculados.py` y `Visualizador Web/build_visualizador.py`
  ya no reimplementan la fórmula — ambos importan y llaman directamente
  `calcular_nota`/`clasificar_evaluacion` de `analisis_financiero.py` (
  refactor que salió de aquel mismo incidente). Solo hubo que tocar
  `analisis_financiero.py`; `test_contrato_kpis.py` sigue verificando que
  los 3 caminos (Excel/reportes/dashboard) coincidan.
- **Valores verificados contra los 7 proyectos reales** (margen real →
  Nota antes → Nota nueva): CCON 22.3%→90→**71**, CVAL 39.6%→100→**87**,
  UMAG 61.5%→100→**93**, CREM 68.3%→100→**95**, MLER 77.8%→100→**96**, ESFO
  80.6%→100→**96**, FQYQ 99.8%→100→**98**. Rango pasó de 90-100 (10 puntos,
  6 empatados) a 71-98 (27 puntos, orden coherente con el margen real). Con
  desviación perfecta (100), hace falta ~35.7% de margen para llegar a
  "Excelente" (85+), contra 25% antes.
- **Tests actualizados** (7 archivos tenían casos que asumían el tope
  duro — todos fallaban por la razón correcta al escribir el test antes
  del fix, confirmado con la suite antes de tocar `analisis_financiero.py`):
  `test_nota_evaluacion.py` (fórmula + 4 tests nuevos de la forma de la
  curva), `test_contrato_kpis.py` (constantes), `Reportes/tests/
  test_kpis_recalculados.py`, `Reportes/tests/test_datos_reportes.py`,
  `Visualizador Web/tests/test_build_visualizador.py` (2 tests, incluyendo
  el de redondeo Excel-vs-Python que se reconstruyó con números limpios en
  la zona lineal de la curva para evitar ruido de punto flotante de
  `EXP()` al construir el empate exacto en .5).
- **Glosario KPIs y CLAUDE.md actualizados** para describir la curva nueva
  (antes decían "vs. objetivo de 25%" sin mencionar que por sobre el
  objetivo seguía puntuando).
- Suite completa: 448 tests, todos pasando.
- **Pendiente que depende del usuario, resuelto el mismo día** (ver
  siguiente entrada): el componente de desviación y "Gastos Generales"
  como pseudo-cliente. También sigue pendiente: 8 de 15 proyectos (53%)
  sin Nota por falta de datos manuales.

## Aclaraciones sobre los 2 pendientes anteriores + exclusión de "Gastos Generales" (2026-08-20, mismo día)

- **Desviación de presupuesto: NO se toca la fórmula**. El usuario confirmó
  que "Costos Proyectados" es la cotización/presupuesto real manejado
  *antes* de que empezara el proyecto, no una estimación rellenada al
  cierre. Eso significa que el patrón real (6 de 7 proyectos completos
  vinieron 15%-99% bajo presupuesto) es una señal de negocio genuina — ya
  sea que QUEMPIN cotiza con colchón grande o que el control de costos en
  terreno es muy bueno — y no un problema de calidad de dato. El diseño
  actual de ese componente (MAX(0, desviación), no penalizar el ahorro,
  decisión 2026-07-28) sigue siendo correcto tal cual; no se abrió ninguna
  tarea de código nueva a partir de esto. Queda como hallazgo de negocio
  para que el usuario decida si quiere indagar más (¿cuánto colchón es
  intencional vs. cuánto es margen de mejora en la cotización?), no como
  pendiente técnico.
- **"Gastos Generales" excluido estructuralmente** de la hoja "Clientes" y
  de Nota/Evaluación en "Indicadores" — el usuario eligió la opción
  recomendada (filtrar por Categoría, no por la ausencia de venta que era
  el mecanismo implícito anterior). Nueva constante
  `CATEGORIA_GASTOS_GENERALES = "Gastos Generales"` en
  `analisis_financiero.py`. Dos cambios:
  1. `asegurar_hoja_clientes`: salta cualquier fila de "Proyectos" cuya
     Categoría sea "Gastos Generales" al construir la lista de clientes
     únicos — ya no aparece como pseudo-cliente aunque su columna "Cliente"
     tenga un valor cargado (hoy coincide con el nombre de la categoría).
  2. `asegurar_hoja_indicadores`: Nota y Evaluación quedan envueltas en
     `IF(Proyectos!<col Categoría><fila>="Gastos Generales","",<fórmula
     original>)`. El guard vive en el sitio de escritura (mismo patrón que
     "Margen por día"), no dentro de `_formula_nota`/`_formula_evaluacion`
     -- esas funciones y sus tests existentes quedaron intactos. **Detalle
     no obvio**: Evaluación necesita su propio guard, no alcanza con vaciar
     Nota -- si Nota quedara "" sin vaciar Evaluación también, la
     comparación `""_>=85` de Excel evalúa TRUE (el texto siempre "gana"
     al compararse con un número), y "Gastos Generales" mostraría
     "Excelente" en vez de quedar vacío.
  3. `Reportes/kpis_recalculados.py` y `Visualizador Web/
     build_visualizador.py` no necesitaron cambios -- "Gastos Generales"
     nunca tiene Monto de Venta ni las demás columnas de
     `CAMPOS_MANUALES_REQUERIDOS`, así que ya estaba excluido de ambos por
     la regla de completitud existente; el gap era solo en la hoja Excel
     cruda (100% fórmulas, no gateada por completitud, mismo espíritu que
     el resto del módulo de "nunca ocultar" -- pero un pseudo-cliente con
     `#DIV/0!` no era "mostrar una inconsistencia real", era ruido de un
     concepto que no aplica).
- Tests nuevos: `test_hoja_clientes.py::test_categoria_gastos_generales_no_aparece_como_cliente`,
  `test_formulas_indicadores.py::test_categoria_gastos_generales_deja_nota_y_evaluacion_vacias`,
  más 2 tests existentes actualizados (`test_nota_evaluacion.py`, las
  fórmulas ahora vienen envueltas en el guard). Suite completa: 450 tests.

## Piso de "Meses activo" corregido de 1 mes a 12 (2026-08-20)

Pedido del usuario: "arregla la frecuencia de compra... por lo general cada
proyecto corresponde a una compra por año, no a 12". Root cause (systematic
debugging): `Meses activo` (hoja Clientes) se calculaba como
`MAX(1, (fecha más reciente − fecha más antigua)/30)` — un piso de **1
mes**, pensado solo para evitar `#DIV/0!` cuando ambas fechas coinciden.
Pero con un solo proyecto (el caso más común: `vida=1` → mismo fecha máx y
mín → rango=0) ese piso de 1 mes hacía `Frecuencia = vida/(meses_activo/12)
= 1/(1/12) = 12` compras/año — un cliente de una sola compra aparecía
comprando mensualmente. El mismo piso distorsionaba también clientes con 2+
proyectos muy juntos en el tiempo (ej. 2 proyectos en 20 días → 24/año).

**Fix**: piso subido de 1 a **12 meses** (1 año) en las 3 implementaciones
espejo (nunca se leen fórmulas de Excel, cada una recalcula por su cuenta —
ver contrato en `Sistema/tests/test_contrato_kpis.py`):
- `Sistema/analisis_financiero.py` (`asegurar_hoja_clientes`, fórmula Excel
  de la columna "Meses activo"): `MAX(1,...)` → `MAX(12,...)`.
- `Reportes/kpis_recalculados.py` (`calcular_cltv_clientes`): `max(1,
  rango_dias/30)` → `max(12, rango_dias/30)`, default sin fechas `1` → `12`.
- `Visualizador Web/build_visualizador.py` (`calcular_clientes`): mismo
  cambio, `1.0` → `12.0`.

Razonamiento del piso de 12 (no solo un parche para `vida=1`): no tiene
sentido anualizar una frecuencia a partir de menos de un año real de
historial de compras — con 2 proyectos en 3 meses, extrapolar a "8
compras/año" es sobre-ajuste con un solo intervalo observado. El piso de 12
meses hace que la frecuencia nunca se calcule sobre una ventana más corta
que un año completo; con historial real ≥ 12 meses, el cálculo usa el
rango real sin cambios (verificado con 450 días en
`test_build_visualizador.py::test_calcular_clientes_agrupa_y_calcula_cltv`).

**Efecto en CLTV**: al bajar la Frecuencia de clientes de un solo proyecto
de 12 a 1, su CLTV también baja (factor ~12x) — es una corrección, no una
regresión: el CLTV anterior sobrestimaba sistemáticamente a cualquier
cliente nuevo/de una sola compra.

Tests actualizados (ya no hardcodeaban el bug, lo verificaban):
`test_hoja_clientes.py` (fórmula `MAX(1,...)` → `MAX(12,...)`),
`test_build_visualizador.py` (`test_calcular_clientes_un_solo_proyecto_meses_activo_minimo_1`
renombrado a `..._minimo_12`, más el caso de 450 días para no perder
cobertura del cálculo con rango real), `test_kpis_recalculados.py::
test_calcular_cltv_clientes_clasifica_por_percentil` y `test_datos_reportes.py::
test_paquete_datos_cliente_incluye_cltv_recalculado_y_sus_proyectos` (CLTV
esperado recalculado con el nuevo piso). `test_contrato_kpis.py` no
necesitó cambios (solo compara consistencia entre las 3 implementaciones,
no valores fijos). Suite completa: 458 tests, todos pasando.

**Pendiente para la próxima corrida real**: el Excel de produción
(`Análisis de Proyectos 2026.xlsx`) tiene la fórmula vieja escrita en la
hoja "Clientes" hasta que corra `/Registro_Analisis_Financiero` o
`/Actualizar_AF` de nuevo — esa hoja se regenera 100% en cada corrida, así
que no requiere migración manual (a diferencia del reordenamiento de
columnas de 2026-07-28).
