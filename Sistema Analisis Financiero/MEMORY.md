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
- **Bloqueo de escritura final**: los 3 PDF reales seguían abiertos en el
  visor (desde una revisión anterior en la misma conversación) y
  `motor_reportes.renderizar_pdf` no pudo sobrescribirlos —
  `PermissionError` de Windows/OneDrive, no un bug del código. Verificado
  todo por imagen contra las copias temporales; falta correr los 3 scripts
  una vez más sobre las rutas reales cuando el usuario cierre los PDF.

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

- `Análisis de Proyectos.xlsx` está vacío — no hay proyectos cargados todavía,
  así que nada de esto se ha ejercitado contra datos reales de QUEMPIN SpA.
- El dashboard HTML (Visualizador Web de este módulo) está fuera de alcance v1
  a propósito — el usuario ya indicó que esa es la forma de presentación a
  mediano plazo, pero no se construye hasta más adelante.
- **Los 3 PDF reales (proyecto/cliente/categoría UMAG e I+D+i) no tienen
  todavía el gráfico comparativo rediseñado del 2026-07-26** — quedaron
  bloqueados por estar abiertos en el visor. Verificado por imagen contra
  copias temporales (ver sección de arriba); falta re-correr los 3 scripts
  ad-hoc sobre las rutas reales una vez que el usuario los cierre.
