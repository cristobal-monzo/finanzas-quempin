# CLAUDE.md

## Rol de este agente

`Análisis Financiero` no es un módulo de puro registro como Centro de Costos —
cuando se invoque en esta carpeta, o se le pida análisis financiero de QUEMPIN en
general, actúa como **analista financiero experto para una PYME**, no solo como
ejecutor de un script:

- **Evalúa proyectos**: rentabilidad real vs. proyectada, riesgo, desviaciones que
  ameritan atención — usando `Análisis de Proyectos 2026.xlsx` + los datos fuente de
  Centro de Costos.
- **Propone y depura KPIs**: sugiere métricas nuevas cuando detecta una pregunta de
  negocio sin métrica que la responda, y señala explícitamente cuándo un KPI
  existente no aporta señal (vanity metrics, redundancias matemáticas entre dos
  KPIs, promedios no ponderados que un outlier distorsiona) — nunca acumula
  métricas por acumularlas. Ver "Playbook de KPIs" más abajo para el set actual.
- **Decide cómo presentar**: para cada análisis, elige la forma más clara según la
  audiencia (tabla, resumen ejecutivo, o un gráfico). La forma de presentación
  pensada a mediano plazo es un **dashboard HTML**, mismo patrón que
  `Centro de Costos/Visualizador Web/` — no construido todavía (ver "Estado
  actual"), pero el diseño de datos de este módulo ya queda listo para
  alimentarlo sin rediseñar el Excel el día que se construya.
- **Análisis financiero total**: puede cruzar todos los módulos (Centro de Costos,
  Cotizador Historico, y Flujo de Caja cuando exista) para dar una vista
  consolidada de la empresa, no solo por módulo aislado.
- Hereda el principio no negociable de rigurosidad numérica de
  [`.claude/agents/analista-financiero-quempin.md`](../.claude/agents/analista-financiero-quempin.md)
  (raíz de `Finanzas QUEMPIN/`): nunca inventa cifras, siempre trazable a la
  fuente, señala inconsistencias en vez de ocultarlas o "arreglarlas" en silencio.

## Qué es / por qué

Consolidador **cross-módulo**: toma los costos reales que ya calcula Centro de
Costos (por proyecto, por categoría de ítem) y los cruza contra ventas y costos
proyectados que el usuario carga a mano en `Análisis de Proyectos 2026.xlsx`, para dar
una vista de rentabilidad por proyecto — margen, desviación real vs. proyectado, y
un set de KPIs de productividad/estructura de costos. No reemplaza a Centro de
Costos ni le duplica lógica — solo lo lee (igual que Cotizador Historico).

A futuro debería poder incorporar Flujo de Caja como fuente adicional, cuando ese
módulo exista.

## Estado actual

**Implementado y probado**: `Sistema/analisis_financiero.py` + `Sistema/tests/`
+ skill `.claude/skills/Registro_Analisis_Financiero/` (`status`/`run`),
encadenado al `run` de Centro de Costos (PASO 12d en
`auditor_centro_costos.py`, envuelto para que nunca pueda abortar esa
corrida). Desde 2026-07-23 también tiene Visualizador Web propio (ver
`Visualizador Web/CLAUDE.md`) y reportes PDF (skill
`Reportes_Analisis_Financiero`).

Historial de extensiones (Nota del Proyecto, CLTV, Glosario KPIs, reportes
PDF, Visualizador Web, etc.) y decisiones de diseño de cada una: comprimido
acá el 2026-07-27 para que esta sección no quede desactualizada cada vez que
se agrega una extensión — ver en vez de eso los archivos
`*analisis-financiero*` en
[`docs/superpowers/specs/`](../docs/superpowers/specs/) y
[`docs/superpowers/plans/`](../docs/superpowers/plans/) (rutas relativas a
la raíz de `Finanzas QUEMPIN/`), uno por extensión, orden cronológico por la
fecha en el nombre del archivo.

## Estructura del módulo (implementada — ver spec/plan para el detalle completo)

**Reorganizado 2026-07-21**: el módulo vive repartido en dos carpetas
hermanas bajo la raíz de `Finanzas QUEMPIN/`, a pedido del usuario — quiere
que `Análisis Financiero/` contenga únicamente el Excel que abre a mano, y
todo el código/docs quede en esta carpeta (`Sistema Analisis Financiero/`).
`analisis_financiero.py` calcula ambas rutas por separado (`RAIZ_MODULO` =
esta carpeta, `RAIZ_DATOS` = `Análisis Financiero/`, ambas derivadas de
`Path(__file__)`) — nunca asumas que están juntas.

```
Finanzas QUEMPIN/
├── Análisis Financiero/                       # SOLO el Excel (lo que el usuario abre)
│   └── Análisis de Proyectos 2026.xlsx             # libro de trabajo (existe, sin proyectos cargados aún)
└── Sistema Analisis Financiero/               # este archivo vive acá
    ├── CLAUDE.md                              # este archivo
    ├── MEMORY.md                              # decisiones, historial, pendientes
    ├── Respaldos/                             # backups automáticos por mes (se crea en la primera corrida real)
    ├── Sistema/                               # analisis_financiero.py + tests/ (71 tests)
    └── .claude/skills/Registro_Analisis_Financiero/  # SKILL.md + driver.py (status/run/confirmar-cliente)
```

## `Análisis de Proyectos 2026.xlsx` — resumen del esquema (detalle completo en el spec)

Cinco hojas, todas dentro del mismo libro:

- **"Proyectos"** (una fila por proyecto), en este orden real de columnas: TAG
  (= prefijo de Centro de Costos, ej. `UMAG`/`CFLI`/`CCON`/`GGEN`/`MLER`),
  Nombre, **Cliente** (se completa sola, ver "Clientes" abajo), **Categoría**
  (2026-07-28: movida junto a Cliente, antes vivía al final — también se
  autocompleta, ver más abajo), Estado, fechas, Monto de Venta **sin IVA**,
  costos proyectados por categoría (manual, las 4: Materiales, Equipos, Mano
  de Obra, Otros), costos reales por categoría (Materiales/Equipos/Otros =
  fórmula automática desde Centro de Costos; Mano de Obra Real = manual, sin
  fuente automática hoy), totales/márgenes/desviación derivados por fórmula.
- **"Detalle Costos Reales"** (una fila por proyecto + subcategoría): preserva el
  detalle real de cada `categoria_item` de Centro de Costos (Consumibles,
  Equipos-Herramientas, Combustible si aparece, etc.) aunque "Proyectos" solo
  muestre 3 buckets agregados — nunca se pierde granularidad al resumir.
- **"Indicadores"** (una fila por proyecto): los KPIs del playbook, 100% fórmulas
  sobre "Proyectos" — ver sección siguiente.
- **"Clientes"** (una fila por cliente único, detectado desde la columna
  "Cliente" de "Proyectos"): AOV, Vida del cliente, Meses activo, Frecuencia
  de compra, Margen de utilidad %, CLTV y Clasificación (percentil) — 100%
  fórmulas agregando sobre "Proyectos". La columna "Cliente" se completa
  sola (derivación + fuzzy-match contra clientes ya registrados); si hay
  duda queda "Pendiente de revisión" (fuente roja), confirmable con
  `python driver.py confirmar-cliente`.
- **"Glosario KPIs"** (una fila por KPI del libro): por qué importa, qué
  elementos usa, qué significa el resultado — texto estático, se reescribe
  completo en cada corrida.

**Reordenamiento de "Categoría" (2026-07-28)**: a pedido del usuario, se
movió del final de "Proyectos" a la columna inmediatamente después de
"Cliente" — `HEADERS_PROYECTOS` cambió de orden y `ESTILO_COLUMNAS_PROYECTOS`
se refactorizó a un dict por nombre (`ESTILO_COLUMNAS_PROYECTOS_POR_NOMBRE`,
convertido a letra-keyed vía `LETRA_COL_PROYECTOS`) para no repetir el
incidente real de header/columna desalineados que ya pasó una vez este mismo
día (ver docstring de `asegurar_estructura_workbook`). El archivo real se
migró a mano (ver MEMORY.md) porque `asegurar_estructura_workbook` nunca pisa
encabezados ya escritos en "Proyectos" — cambiar el código solo no reordena
un archivo existente.

**Resaltado de celdas manuales (2026-07-28)**: las 11 columnas de ingreso
manual de "Proyectos" (TAG, Nombre, Estado, fechas, Monto de Venta, las 4
"...Proyectado(s)" y Mano de Obra Real) llevan relleno amarillo + cursiva —
`aplicar_resaltado_celdas_manuales()`, llamada en `ejecutar()` junto a
`aplicar_estilo_visual()`. "Cliente" y "Categoría" quedan afuera (se
autocompletan solas, tienen su propio rojo/azul marino) igual que las
columnas de fórmula. Detalle de la decisión y por qué no se puede usar
`ws.max_row` para calcular el buffer de filas vacías: ver MEMORY.md.

**Regla de oro heredada de Centro de Costos**: las columnas manuales nunca se
tocan entre corridas; solo se regeneran "Detalle Costos Reales" y las fórmulas
derivadas de "Proyectos"/"Indicadores".

## Playbook de KPIs (hoja "Indicadores")

**Depurado 2026-07-28** (decisión aprobada por el usuario): se eliminaron 5
KPIs redundantes ("Rentabilidad sobre costo" = margen/(1-margen) de "Margen
neto %" en otra escala; las 4 "Productividad Materiales/Equipos/MO/Otros" =
1 / "Costo % de venta" de esa categoría, invertidas) y se agregaron 4 KPIs
nuevos. Ver MEMORY.md 2026-07-28 para la verificación a mano contra UMAG.

| KPI | Fórmula |
|---|---|
| Margen neto % | Margen Real / Monto de Venta |
| Costo Materiales / Equipos / MO / Otros % de venta | Costo Real de esa categoría / Monto de Venta |
| Estructura % Materiales / Equipos / MO / Otros (mix, nuevo) | Costo Real de esa categoría / Costos Totales Real — suma 100% |
| Desviación % Materiales / Equipos / MO / Otros | Real / Proyectado − 1, por categoría |
| Desviación % Total (nuevo, ya existía en "Proyectos") | Costos Totales Real / Costos Totales Proyectado − 1, traída como columna visible |
| Ahorro/Sobrecosto Materiales / Equipos / MO / Otros / Total (nuevo) | Costo Proyectado − Costo Real; positivo = ahorro, negativo = sobrecosto |
| % del Total Real del proyecto (nuevo, hoja "Detalle Costos Reales") | Total sin IVA de la subcategoría / suma de las filas de ese proyecto en esa hoja |
| Peso del proyecto en la cartera de ventas (%) (nuevo) | Monto de Venta del proyecto / Σ Monto de Venta de todos los proyectos con venta cargada (cualquier Estado, no solo "Terminado") |
| Margen por día de ejecución (nuevo) | Margen Real / (Fecha de cierre − Fecha de inicio, en días) — vacío si el proyecto no tiene Fecha de cierre ("en desarrollo") |
| Nota del Proyecto (0-100) | 70% margen neto % (curva de 2 tramos: lineal 0→70 hasta el objetivo de 25%, luego asíntota hacia 100 sin tocarlo nunca — ver "Curva de la Nota" abajo) + 30% control de desviación total, **sin ABS()** — solo penaliza sobrecosto real (Real > Proyectado); un proyecto en o bajo presupuesto obtiene el puntaje máximo del componente |
| CLTV (hoja Clientes) | AOV × Frecuencia de compra × Vida del cliente × Margen de utilidad % |

**Segunda tanda de KPIs nuevos (2026-07-28, misma fecha, tras la
depuración anterior)**: "Peso del proyecto en la cartera de ventas (%)" y
"Margen por día de ejecución" — 2 de 3 KPIs que un análisis previo del
agente había propuesto; el tercero ("Cumplimiento de plazo") quedó fuera a
propósito porque requería un dato manual nuevo (fecha de plazo
comprometido) que el usuario decidió no agregar por ahora. Ambos son
columnas nuevas al final de "Indicadores" (X/Y) — no reordenan ni tocan
ninguna columna existente. "Margen por día" usa un `IF(...="","",...)`
dentro de la propia fórmula de Excel para quedar vacío en proyectos sin
Fecha de cierre, en vez de una rama de código en Python — se recalcula
solo si el usuario completa la fecha después, sin correr el script de
nuevo. Ver MEMORY.md 2026-07-28 para el detalle y los valores verificados
en UMAG. **Nota**: estos 2 KPIs no se agregaron al espejo Python de
`Reportes/kpis_recalculados.py` (fuera del alcance pedido) — no aparecen
todavía en los reportes PDF; es una extensión aparte si se pide.

**Curva de la Nota corregida (2026-08-20)**: con la cartera real de QUEMPIN
(15 proyectos) el componente de margen tenía un tope duro (`MIN(100,...)`)
que saturaba en 100 apenas `margen neto % >= 25%` (el objetivo) — 6 de los 7
proyectos completos empataban en Nota=100, sin ninguna capacidad de
distinguir un proyecto al 40% de margen de uno al 99.8%. Reemplazado por una
curva de dos tramos (`_score_margen_nota` en `analisis_financiero.py`):
lineal 0→70 hasta el objetivo, y una asíntota que sigue subiendo (cada vez
más despacio) por sobre el objetivo sin tocar 100 nunca. La constante de la
asíntota (`K_MARGEN_NOTA_SOBRE_OBJETIVO = 0.3186`) está calibrada para que
60% de margen (cerca de la mediana real observada) puntúe ~90 — ajustable
si la cartera cambia. Detalle completo, la propuesta discutida con el
usuario y los valores verificados contra los 7 proyectos reales: ver
MEMORY.md 2026-08-20.

**Piso de "Meses activo" corregido de 1 a 12 meses (2026-08-20, mismo
día)**: la Frecuencia de compra (hoja Clientes) se anualizaba dividiendo
por un piso de solo 1 mes de historial, así que un cliente con un único
proyecto (`vida=1`, sin rango real de fechas) daba `Frecuencia=12`
compras/año en vez de 1. Piso subido a 12 meses (1 año) en las 3
implementaciones espejo (`analisis_financiero.py`, `Reportes/
kpis_recalculados.py`, `Visualizador Web/build_visualizador.py`) — con
historial real ≥ 12 meses el cálculo no cambia. Baja también el CLTV de
clientes nuevos/de una sola compra (~12x), que antes estaba sobrestimado
por el mismo motivo. Detalle y tests actualizados: ver MEMORY.md
2026-08-20.

Origen y hallazgos de rigor (por qué "ROI" se llamó "Rentabilidad sobre
costo" antes de eliminarse, por qué no hay columnas duplicadas de "costo
por unidad de ingreso" + "estructura %", el bug de fórmula encontrado en el
archivo de ejemplo del usuario): ver "Playbook de KPIs" en el spec original
(2026-07-20) — no se repite acá para no desincronizarse. La depuración/
extensión 2026-07-28 (incluyendo un bug real de desalineación de
encabezados encontrado y corregido en `asegurar_estructura_workbook`) está
en MEMORY.md, no en un spec nuevo.

## Reportes PDF (implementado 2026-07-24)

Genera reportes PDF por proyecto/cliente/categoría y comparativas ad-hoc a
partir de `Análisis de Proyectos 2026.xlsx`, en la carpeta hermana `Reportes/`:

- **`brand.py`** — fuente Lato embebida (3 variantes) y logo en base64,
  `construir_html()` arma el HTML base (título + logo + contenido) que luego
  se renderiza a PDF.
- **`graficos.py`** — gráficos SVG propios (barras, dona) sin dependencias
  externas, para incrustar en el HTML del reporte.
- **`motor_reportes.py`** — renderiza el HTML final a un PDF válido
  (`renderizar_pdf`).
- **`datos_reportes.py`** — arma el paquete de datos de cada reporte
  (`paquete_datos_proyecto` / `_cliente` / `_categoria` / `_comparacion`),
  leyendo `Análisis de Proyectos 2026.xlsx` de solo lectura, igual que el resto del
  módulo.
- **`estado_reportes.py`** — manifiesto de obsolescencia: calcula un hash de
  los datos relevantes de cada entidad (proyecto/cliente/categoría), lo
  compara contra el último hash con el que se generó su reporte
  (`detectar_desactualizados`), y permite marcar una entidad como "generada"
  (`marcar_generado`) sin mutar el estado anterior. **Este manifiesto solo
  detecta y lista qué quedó desactualizado — nunca dispara la generación de
  un reporte por sí mismo** (ver `MEMORY.md`).

El skill `Reportes_Analisis_Financiero`
(`.claude/skills/Reportes_Analisis_Financiero/driver.py` + `SKILL.md`) expone
`status` (lista entidades con datos completos y cuáles tienen reporte
pendiente/desactualizado, vía `calcular_reportes_pendientes`) y `run` (genera
los PDFs pendientes). Desde 2026-07-24, `Centro de Costos` avisa por consola
al final de su propio `run` (PASO 12d, `auditor_centro_costos.py`,
`_avisar_reportes_pendientes()`) si quedaron reportes pendientes tras
actualizar Análisis Financiero — best-effort: si el skill de reportes no
existe o falla, no aborta el `run` de Centro de Costos, solo omite el aviso.

**Reglas de completitud / "en desarrollo"** (spec §6): un proyecto sin las 8
columnas manuales de `CAMPOS_MANUALES_REQUERIDOS` (Estado, Fecha de inicio,
Monto de Venta, los 4 Costos Proyectados, Mano de Obra Real) **no genera
reporte** — se excluye de `listar_entidades` y de las agregaciones de
cliente/categoría (`paquete_datos_proyecto` lanza `DatosIncompletos`). Esta
es la única definición de completitud del módulo — hasta el 2026-07-28
estaba duplicada y el dashboard usaba una versión más laxa (6 campos, sin
"Estado" ni "Fecha de inicio"); unificadas en `tiene_datos_completos()`, con
contrato cruzado en `Sistema/tests/test_contrato_kpis.py`. "Fecha de cierre"
queda deliberadamente fuera de este requisito: un proyecto sin ella, o con
una fecha de cierre futura, se considera **"en desarrollo"**: sí genera reporte (no
requiere fecha de cierre para estar completo), pero su reporte lleva un
indicador visual explícito de que el proyecto sigue en curso, no cerrado.

**Estándar de contenido y layout de 2 páginas (2026-07-24)**: para
Proyecto/Cliente/Categoría, todo reporte va en exactamente 2
`<div class="pdf-pagina">` (CSS de salto de página en `brand.py`) — página 1
es un panel de verificación 100% visual/tabular con **todos** los KPIs de la
entidad (sin selección editorial) y estructura de secciones fija; página 2
es el análisis narrativo (resumen ejecutivo, fortalezas, debilidades,
notas estratégicas), con estructura libre y gráficos puntuales adicionales
si el agente los considera necesarios. La comparación ad-hoc queda
explícitamente fuera de este estándar — ver "Pendientes" en `MEMORY.md`.

Ver diseño completo:
[`docs/superpowers/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md`](../docs/superpowers/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md)
(addendum §10 para este estándar)
y el plan de implementación
[`docs/superpowers/plans/2026-07-21-analisis-financiero-reportes-pdf-implementacion.md`](../docs/superpowers/plans/2026-07-21-analisis-financiero-reportes-pdf-implementacion.md)
(rutas relativas a la raíz de `Finanzas QUEMPIN/`).

## Precauciones

- **Nunca escribe `Centro de Costos.xlsx`** — solo lectura ahí, igual que
  Cotizador Historico. Si algo se ve desactualizado, correr Centro de Costos
  (`/Registro_Centro_de_Costos`), no este módulo.
- Las carpetas de proyecto nuevas se crean en
  `Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y
  Boletas/Chile/<Nombre>/` (fuente real que lee Centro de Costos hoy para
  Chile — AF todavía no tiene país-conciencia propia, ver comentario junto a
  `RAIZ_FACTURAS_CENTRO_COSTOS` en `analisis_financiero.py`) — **nunca** en
  `Centro de Costos/Facturas y Boletas/` (legado, el script ya no la lee desde
  2026-07-17).
- `Análisis de Proyectos 2026.xlsx` vive en la carpeta hermana `../Análisis
  Financiero/`, no acá — `RUTA_EXCEL` en `analisis_financiero.py` ya apunta
  ahí, no asumir que está junto al código. Vive dentro de OneDrive,
  sincronizada — antes de sobrescribirlo, considerar que puede tener
  ediciones manuales recientes hechas fuera de un script.
- Contiene datos financieros reales de la empresa (ventas, márgenes, costos por
  proyecto) — tratar como sensible, igual que el resto de `Finanzas QUEMPIN/`.
