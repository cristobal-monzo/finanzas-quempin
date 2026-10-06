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

Historial de extensiones (Nota del Proyecto, CLTV —ya reemplazado—, Glosario KPIs, reportes
PDF, Visualizador Web, etc.) y decisiones de diseño de cada una: comprimido
acá el 2026-07-27 para que esta sección no quede desactualizada cada vez que
se agrega una extensión — ver en vez de eso los archivos
`*analisis-financiero*` en
[`docs/specs/`](../docs/specs/) y
[`docs/plans/`](../docs/plans/) (rutas relativas a
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
    ├── Sistema/                               # analisis_financiero.py + tests/ (167 tests, 2026-08-31)
    └── .claude/skills/Registro_Analisis_Financiero/  # SKILL.md + driver.py (status/run/confirmar-cliente)
```

## `Análisis de Proyectos 2026.xlsx` — resumen del esquema (detalle completo en el spec)

Cinco hojas, todas dentro del mismo libro:

- **"Proyectos"** (una fila por proyecto), en este orden real de columnas: TAG
  (= prefijo de Centro de Costos, ej. `UMAG`/`CFLI`/`CCON`/`GGEN`/`MLER`),
  Nombre, **Cliente** (se completa sola, ver "Clientes" abajo), **Categoría**
  (2026-07-28: movida junto a Cliente, antes vivía al final — también se
  autocompleta, ver más abajo), **% Avance**, fechas, Monto de Venta **sin
  IVA**, costos proyectados por categoría (manual, las 4: Materiales, Equipos,
  Mano de Obra, Otros), costos reales por categoría (Materiales/Equipos/Otros
  = fórmula automática desde Centro de Costos; Mano de Obra Real = manual, sin
  fuente automática hoy), totales/márgenes/desviación derivados por fórmula.

**`Estado` reemplazado por `% Avance` (2026-08-31)**: el campo de texto libre
(`Terminado`/`En Proceso`, más un typo real `Terminas`) pasó a ser un
porcentaje de avance manual, en la **misma posición 5** — no se reordenó
ninguna columna, así que ninguna letra ni fórmula existente cambió. Hereda
los dos roles de `Estado`: campo de ingreso manual (amarillo + cursiva) y uno
de los campos de `CAMPOS_MANUALES_REQUERIDOS`. Se guarda como fracción 0–1
con formato `0.0%`. El archivo real se migró a mano (ver MEMORY.md): los 16
proyectos terminados quedaron en 100% y `Gastos Generales` vacío.
- **"Detalle Costos Reales"** (una fila por proyecto + subcategoría): preserva el
  detalle real de cada `categoria_item` de Centro de Costos (Consumibles,
  Equipos-Herramientas, Combustible si aparece, etc.) aunque "Proyectos" solo
  muestre 3 buckets agregados — nunca se pierde granularidad al resumir.
- **"Indicadores"** (una fila por proyecto): los KPIs del playbook, 100% fórmulas
  sobre "Proyectos" — ver sección siguiente.
- **"Clientes"** (una fila por cliente único, detectado desde la columna
  "Cliente" de "Proyectos"): N° de proyectos, Venta acumulada, Margen
  acumulado, Margen %, Cliente recurrente y Clasificación (percentil del
  margen acumulado) — 100% fórmulas sobre "Indicadores", contando **solo
  proyectos con "Datos completos" = Sí** (desde 2026-09-21; antes CLTV sobre
  todo "Proyectos", ver "Fase 1 de la auditoría"). La columna "Cliente" se
  completa sola (derivación + fuzzy-match contra clientes ya registrados); si
  hay duda queda "Pendiente de revisión" (fuente roja), confirmable con
  `python driver.py confirmar-cliente`. Lo que el usuario escriba a mano en
  esa columna nunca se pisa.
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
manual de "Proyectos" (TAG, Nombre, % Avance, fechas, Monto de Venta, las 4
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
| Peso del proyecto en la cartera de ventas (%) (nuevo) | Monto de Venta del proyecto / Σ Monto de Venta de todos los proyectos con venta cargada (sin filtrar por % Avance) |
| Margen por día de ejecución (nuevo) | Margen Real / (Fecha de cierre − Fecha de inicio, en días) — vacío si falta alguna fecha o si el cierre es futuro ("en desarrollo") |
| Costo estimado al cierre (2026-09-21) | Costo Real + Costo Proyectado × (1 − % Avance acotado a 0–1) — lo que falta, a precio de presupuesto. Al 100% = costo real |
| Margen estimado al cierre (y %) (2026-09-21) | Venta − Costo estimado al cierre (÷ Venta) |
| Desviación estimada al cierre % (2026-09-21) | Costo estimado al cierre / Costo Proyectado − 1 |
| Margen al cierre % (escenario índice de costo) (2026-09-21) | (Venta − Costo Real / % Avance) / Venta — pesimista, solo referencia, no entra en la Nota |
| Nota del Proyecto (0-100) | 70% **margen estimado al cierre %** (curva de 2 tramos: lineal 0→70 hasta el objetivo de 25%, luego asíntota hacia 100 sin tocarlo nunca — ver "Curva de la Nota" abajo) + 30% control de **desviación estimada al cierre**, **sin ABS()** — solo penaliza sobrecosto; 100 puntos en o bajo presupuesto, **0 con +30%** (`SOBRECOSTO_NOTA_CERO`, desde 2026-09-21; antes +100%). Vacía si falta el avance |
| Error del presupuesto % (2026-09-21, fase 2) | Σ \|Costo Real − Costo Proyectado\| de las 4 categorías / Costos Totales Proyectado — cuánto se equivocó el presupuesto sin que los errores se cancelen entre sí en el total |
| Datos completos (2026-09-21, columna de apoyo) | Sí si están los 7 campos de `CAMPOS_MANUALES_REQUERIDOS` — filtra la hoja Clientes |
| Clientes (hoja Clientes, 2026-09-21) | N° de proyectos, Venta y Margen acumulados (margen estimado al cierre), Margen %, Recurrente (≥2 proyectos), Clasificación por percentil 67/33 del margen acumulado. Reemplazan al CLTV |

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

**De dónde salen los puntos de la Nota (2026-10-05)**: `componentes_nota()`
devuelve la rentabilidad (sobre 70) y el control del presupuesto (sobre 30)
en enteros que **suman exactamente** `calcular_nota()`: el control se lleva
lo que el redondeo de la Nota no le dio a la rentabilidad. Lo usa la ficha
del proyecto del tablero («48 + 6 = 54»). No es una tercera implementación:
reusa `_score_margen_nota` y `calcular_nota`. Contrato en
`test_nota_evaluacion.py` (suma exacta en una grilla de márgenes y
desviaciones).

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

**Nota Parcial (2026-08-31, reemplazada el 2026-09-21 — ver "Fase 1 de la
auditoría" abajo)**: columna nueva al final de "Indicadores" (Z),
sin reordenar nada. Separa "qué tan bien se está ejecutando" (la Nota) de
"cuánto de eso está confirmado" (la Parcial). `Evaluación` y el `Nota
promedio` del dashboard **siguen clasificando la Nota financiera**, no la
Parcial — decisión explícita del usuario. Entra por el mismo carril de doble
implementación que la Nota (`calcular_nota_parcial` + `_formula_nota_parcial`,
contrato en `test_contrato_kpis.py`), y a diferencia de los 2 KPIs de
2026-07-28 **sí** llega a los reportes PDF: viaja en el dict `indicadores` de
`kpis_recalculados.recalcular_proyecto`, y la página 1 lleva todos los
indicadores de la entidad sin selección editorial.

Origen y hallazgos de rigor (por qué "ROI" se llamó "Rentabilidad sobre
costo" antes de eliminarse, por qué no hay columnas duplicadas de "costo
por unidad de ingreso" + "estructura %", el bug de fórmula encontrado en el
archivo de ejemplo del usuario): ver "Playbook de KPIs" en el spec original
(2026-07-20) — no se repite acá para no desincronizarse. La depuración/
extensión 2026-07-28 (incluyendo un bug real de desalineación de
encabezados encontrado y corregido en `asegurar_estructura_workbook`) está
en MEMORY.md, no en un spec nuevo.

## Fase 1 de la auditoría (2026-09-21): KPIs correctos

Auditoría completa del módulo el 2026-09-21 (Fase 0 = arreglos del
dashboard, ver `Visualizador Web/CLAUDE.md`; Fase 1 = esto). Las cuatro
decisiones las tomó el usuario, cada una con el impacto medido sobre la
cartera real antes de elegir:

- **Proyecto en curso = estimado al cierre.** La Nota evaluaba el costo
  gastado a la fecha contra la venta completa: un proyecto al 75% de avance
  con el 99% del presupuesto ya gastado salía "Excelente" (margen a la fecha
  39,6%). Ahora la Nota usa el margen y la desviación **estimados al
  cierre** (lo que falta, a precio de presupuesto) → 24,4%, "Requiere
  atención". Se eligió esta estimación y no la de índice de costo (Real /
  avance, más severa) porque no castiga a un proyecto que compró sus
  materiales al inicio; la severa queda como columna de referencia. Reemplaza
  a la Nota Parcial, que castigaba el avance y no el riesgo. Al 100% de
  avance nada cambia.
- **El sobrecosto pesa de verdad**: el componente de control llega a 0 con
  +30% (antes +100%: un proyecto con +27,6% perdía solo 8 puntos y seguía
  "Bueno").
- **Mapeo de categorías ampliado** (`MAPEO_CATEGORIA_BUCKET`): Ferretería y
  Reposición de Material → Materiales; Arriendo y Herramientas → Equipos.
  Servicios (incluye mano de obra subcontratada) queda en Otros **a
  propósito**: "Mano de Obra Real" es manual y podría ya incluirla. El resto
  de los indirectos (Combustible, Transporte, Alimentación…) se declaró
  "Otros" explícito para que el run no avise ~50 veces por corrida.
- **CLTV → margen acumulado + recompra.** AOV × Frecuencia × Vida × Margen
  contaba dos veces la cantidad de compras (AOV × Vida ya es la venta
  total). Con todos los clientes en 1 proyecto no se notaba; el primer
  cliente recurrente habría salido con el doble del margen que dejó.

Correcciones sin decisión de por medio, en el mismo cambio:

- **Una sola implementación Python** de los KPIs de proyecto y de cliente:
  `calcular_kpis_proyecto()` / `calcular_clientes()` en
  `analisis_financiero.py`, cada KPI keyed por el nombre de su columna. El
  dashboard (`build_visualizador.py`) y los PDFs (`kpis_recalculados.py`)
  solo traducen claves; antes cada uno recalculaba todo por su cuenta. Las
  fórmulas de "Indicadores" salen de `formulas_indicadores()` (por nombre de
  columna, no por posición) y `test_contrato_kpis.py` exige que las dos
  cubran exactamente las mismas columnas.
- **División por cero = vacío en los dos lados**: presupuesto o venta en 0
  da celda vacía en el Excel y `None` en Python (antes `#DIV/0!` en el
  Excel y un `0,0%` inventado en el dashboard, que se leía como "sin
  desviación").
- **"Fecha de inicio" ya no es requerida** (`CAMPOS_MANUALES_REQUERIDOS`
  quedó en 7): solo la usa el Margen por día. Dejaba fuera a un proyecto con
  todo lo demás cargado.
- **Margen por día vacío con cierre futuro** (la regla "en desarrollo" de
  los reportes; antes solo se miraba si la fecha estaba vacía).
- **Alertas** (`alertas_proyecto()`, en la consola de `run`/`status` y en el
  dashboard): % Avance fuera de 0–100%, avance 100% con cierre futuro,
  cierre pasado con avance < 100%, terminado con menos del 80% del
  presupuesto gastado (posibles costos sin registrar), sobrecosto (estimado)
  al cierre > +10%, gasto real en una categoría sin presupuesto. No cambian
  ningún KPI, solo avisan.
- `derivar_cliente` quita el código numérico de carpeta ("261. FACH 1" →
  "FACH 1"). Las celdas ya escritas no se tocan: corregirlas a mano.
- Dashboard de Perú unificado con el de Chile (ver
  `Visualizador Web/CLAUDE.md`).

**Cómo se verificó**, reutilizable la próxima vez que cambien fórmulas:
el engine se corrió sobre una **copia** del libro real registrando un país
ficticio en `PAISES` (rutas de escritura en un sandbox, con guard de que los
archivos reales no cambiaron), se recalculó esa copia con **Excel real vía
COM** (`Excel.Application`, `CalculateFull`) y se comparó celda a celda
contra `calcular_kpis_proyecto()` / `calcular_clientes()`: 240 celdas de
"Indicadores" y los 8 clientes, 0 diferencias, 0 `#DIV/0!`. Los tests
comparan el TEXTO de las fórmulas; solo esta prueba compara sus VALORES.

## Fase 2 de la auditoría (2026-09-21): el tablero responde preguntas

El rediseño del tablero está en `Visualizador Web/CLAUDE.md`. Del lado de
los KPIs agregó una columna a "Indicadores" y dos análisis de cartera que
**no** son de un proyecto y por eso no tienen columna en el Excel:

- **`Error del presupuesto %`** (columna nueva): Σ |real − proyectado| de
  las 4 categorías sobre el presupuesto total. La "Desviación % Total" puede
  dar casi 0 con un presupuesto muy mal repartido -- en un proyecto real el
  total calzó en -1,1% con materiales en +307% compensados por equipos en
  -90%. Este número no juzga el resultado del proyecto (eso es el margen):
  juzga la cotización.
- **`sesgo_por_categoria()`**: Σ real / Σ proyectado − 1 por categoría en
  toda la cartera **terminada** (un proyecto a medio ejecutar todavía va a
  gastar más y ensuciaría el sesgo). Con los datos al 2026-09-21: Materiales
  +16,6%, Equipos -11,4%, Mano de Obra +1,0%, Otros -21,5% sobre 7
  proyectos. Eso es lo que hay que corregir al cotizar.
- **`concentracion_cartera()`**: participación de cada cliente en toda la
  venta cargada (también la de proyectos incompletos: la dependencia existe
  igual), con HHI y "clientes equivalentes" (1 / HHI). Hoy: el mayor cliente
  concentra 25%, los 3 mayores 59%, y el ingreso está repartido como si
  hubiera 6,7 clientes iguales de los 13 que hay.

Los dos análisis viven en `analisis_financiero.py` junto al resto, no en el
build del tablero: el día que un reporte PDF o Flujo de Caja los necesite,
ya están.

## Costos proyectados desde el Formulador (Intercambio, 2026-09-30)

Pedido del usuario: que las herramientas compartan información entre sí y,
en concreto, que el **Formulador de proyectos** (web) pueda actualizar los
costos proyectados de este módulo. Canal de entrada auditado a las 4
columnas "... Proyectado(s)" de "Proyectos" — **la única excepción a la
regla de oro de las columnas manuales**, por pedido explícito. Protocolo
común en `../Sistema Intercambio/CLAUDE.md`; lógica en
`Sistema/presupuestos_formulador.py`, enganchada en `ejecutar()`.

- El Formulador deja un mensaje `presupuesto-proyecto` (TAG + costos por
  categoría; gastos generales e imprevistos no viajan) en el `buzon/` de la
  carpeta de intercambio: desde el 2026-09-30,
  `Formulación de proyectos - Documentos/.Herramientas formulación/Intercambio/`
  (antes `Finanzas QUEMPIN/Intercambio/`), ubicada por
  `presupuestos_formulador.ubicar_intercambio()`; sin la biblioteca
  sincronizada queda inactivo con un aviso en `status`/`run`. Cada `run` lo aplica **después del
  respaldo y antes de fórmulas/Indicadores/Clientes**, así la misma corrida
  y el dashboard ya lo usan.
- **Solo escribe cuando es seguro**: celda vacía, valor que el propio
  Formulador escribió antes (registro de procedencia
  `Sistema/presupuestos_formulador.json`, gitignoreado), o valor que quien
  envió **vio** en el Formulador ("reemplaza", como un If-Match). Un valor
  escrito a mano que no se vio deja el envío **pendiente** en el buzón:
  `driver.py intercambio confirmar|descartar <id>`. Nunca aplica un envío a
  medias; varios envíos al mismo TAG: gana el último.
- Cada celda escrita lleva una **nota de Excel** con la procedencia (autor
  `Formulador (Intercambio)`). Si alguien la cambia a mano después, la
  corrida siguiente quita la nota y la trata como manual.
- Los envíos se archivan en `procesado/` y el registro se guarda **solo si el
  Excel se guardó**: con el libro abierto, todo queda en el buzón para la
  próxima. Nunca aborta el run (queda como aviso).
- TAG que no existe: pendiente hasta que aparezca (lo crea Centro de Costos
  con la primera factura), salvo que el envío diga `crear` con un nombre:
  ahí crea la fila (TAG + Nombre), en la primera fila libre (no sobre una a
  medio cargar).
- Al final de cada `run` publica `publicado/analisis-financiero.json` en esa
  carpeta (TAG, nombre, cliente, categoría, avance, proyectados con su
  origen, reales por categoría y estado de los envíos; sin "Gastos
  Generales" ni venta). La ve todo el que entra a la biblioteca de
  Formulación: el usuario lo aceptó al moverla ahí. `driver.py intercambio
  publicar` hace lo mismo **sin escribir el Excel**.
- El intercambio corre solo contra el libro del país (`ruta_excel_af`
  omitida; `PAISES["CL"]["raiz_intercambio"]`) o con una `raiz_intercambio`
  explícita: un test con Excel temporal nunca toca la carpeta real. **Un país
  ficticio de verificación debe sobrescribir `raiz_intercambio` y
  `ruta_estado_intercambio`** (si copia `PAISES["CL"]`, apuntarían a los
  reales). Perú: desactivado.
- Centro de Costos no se tocó; `cargar_datos_centro_costos()` (extraída de
  `ejecutar()`) es la única lectura de sus datos, compartida con
  `publicar_intercambio()`.

### Venta, N° de requerimiento y sesgo (plan de integración, 2026-10-01)

- **`venta-proyecto`** usa el **mismo** canal y las mismas garantías: el
  monto de venta sin IVA de un proyecto adjudicado (de la cotización emitida
  en Sistema QUEMPIN, `fuente.folio`, o del precio neto del Formulador) va a
  «Monto de Venta (sin IVA)». Es otra clave (`CLAVE_VENTA`) del mismo
  registro de procedencia, no un segundo canal: dos implementaciones de "solo
  escribir cuando es seguro" terminarían divergiendo. Una venta a un TAG que
  no existe espera (no crea el proyecto). Un presupuesto y una venta del
  mismo TAG son independientes.
- **«N° Requerimiento»** (columna nueva al final de "Proyectos", manual,
  amarilla): el N° de la Planilla de Ingreso, la clave común de proyecto.
  Un envío que trae `proyecto.req` la completa **solo si está vacía**. Al
  agregarla, la leyenda del resaltado manual (que vivía justo en esa celda,
  V1) se corre una columna: `asegurar_estructura_workbook` reconoce la
  leyenda y la reemplaza por el encabezado (verificado sobre una copia del
  libro real: las 21 columnas anteriores quedan idénticas).
- La publicación lleva ahora `req`, `venta: {cargada, origen}` (**nunca el
  monto**: la carpeta la ve todo el que entra a la biblioteca) y `sesgo`
  (`sesgo_cartera()` = `sesgo_por_categoria()` del tablero, en la forma del
  catálogo), que el Formulador usa para precargar su simulador de
  sobrecostos. `mensajes` incluye solo lo que iba a este módulo.
- El formato de cada mensaje y de la publicación está en
  `../Sistema Intercambio/esquemas/`; `test_la_publicacion_trae_el_sesgo_y_cumple_su_esquema`
  valida lo publicado contra él.

Tests: `Sistema/tests/test_presupuestos_formulador.py` (sandbox en
`tmp_path`). Verificado además de punta a punta con el Formulador real en
Chrome contra una copia del libro real (país ficticio, archivos reales sin
cambios).

### Ingreso manual desde el tablero (`datos-proyecto`, 2026-10-02)

Pedido del usuario: un lugar donde ingresar los valores manuales sin abrir el
Excel, que «genere un descargable» o deje el dato «listo para cargar». Eligió
(entre las opciones que se le dieron) **una pestaña en el mismo tablero** y
**el buzón de Intercambio** como camino al Excel, sabiendo que esa carpeta la
ve toda la biblioteca de Formulación.

- **La pestaña** («Ingresar datos», ver `Visualizador Web/CLAUDE.md`) deja un
  mensaje `datos-proyecto` **por proyecto** en el buzón: así un proyecto en
  conflicto no frena a los demás. Campos: todas las columnas manuales de
  «Proyectos» menos TAG y Nombre (`CAMPOS_TABLERO`, que es también lo que la
  pestaña muestra: no hay otra lista). Nombre solo al crear un proyecto.
- **Mismo canal y misma regla** que el Formulador, en
  `presupuestos_formulador.py`: la celda vacía se escribe; una con valor solo
  si todavía tiene lo que la persona vio en el tablero (`reemplaza`); si no,
  pendiente (`intercambio confirmar|descartar <id>`). Todo o nada por envío.
  Costos y venta usan **las mismas claves** que el Formulador (`Materiales`,
  `Monto de Venta`...), así los dos hablan de la misma celda.
- **Tres diferencias**, porque esto es ingreso manual y no la copia del
  estado de otra herramienta: (1) varios envíos al mismo proyecto se aplican
  **todos, en orden**, cada uno sobre lo que dejó el anterior (`planificar`
  decide en orden de envío y con los valores que van quedando; «gana el
  último» sigue solo para los dos tipos del Formulador); (2) **sin nota ni
  registro de procedencia**: queda como valor manual, y si pisa uno del
  Formulador le quita su nota y lo saca del registro; (3) puede dejar una
  celda vacía (`null`) y crear un proyecto con todos sus datos.
- **Tipos de valor**: el avance viaja como fracción (0,35) igual que en el
  Excel, las fechas como `AAAA-MM-DD` y se escriben como fecha de Excel, pesos
  y N° de requerimiento como enteros. La comparación «¿es el mismo valor?»
  (`_mismo_valor`) tiene su gemela en `ingreso.js` y un test las compara.
- **Formato**: lo que escribe el buzón (de cualquiera de los dos orígenes)
  toma el formato de su columna (`FORMATOS_COLUMNAS_PROYECTOS`) solo si la
  celda no tenía uno propio: en el libro real las celdas manuales ya traen el
  formato que les puso el usuario, y se respeta.
- **Archivo descargado** (navegador sin acceso a la carpeta): se deja tal cual
  en `buzon/`, o `driver.py intercambio cargar <archivo>` lo valida y lo deja
  ahí (mismo id, nunca dos veces).
- El procesador toma ahora los tipos que atiende AF **del catálogo** (cada
  esquema declara su destino), no de una lista suya; un test exige que
  coincidan con `pf.TIPOS`.

Verificado de punta a punta: un envío generado por la pestaña en Chrome
(carpeta simulada en el almacenamiento privado del navegador) aplicado con
`ejecutar()` sobre una copia del libro real, con los archivos reales (AF,
Centro de Costos, registro y buzón) sin cambios.

## Reportes PDF (implementado 2026-07-24)

Genera reportes PDF por proyecto/cliente/categoría y comparativas ad-hoc a
partir de `Análisis de Proyectos 2026.xlsx`, en la carpeta hermana `Reportes/`:

- **`panel.py`** (2026-09-24) — **arma la página 1 completa** (el panel de
  verificación) de proyecto/cliente/categoría desde el paquete de datos:
  ficha con chips, 4 tarjetas de KPI con semáforo, alertas, gráficos y los 28
  indicadores del playbook en 2 columnas agrupadas por bloque. También
  envuelve la página 2 (`pagina_analisis`) y arma el documento completo
  (`documento`). Antes esa página la escribía el agente a mano en cada
  reporte, pese a no tener ninguna decisión editorial — ver MEMORY.md
  2026-09-24.
- **`brand.py`** — fuente Lato embebida (3 variantes, lectura cacheada) y
  logo en base64, `construir_html()` arma el HTML base (título + logo +
  contenido) que luego se renderiza a PDF. `estado_kpi()` es el semáforo
  centralizado (bueno/medio/malo, colores y cortes compartidos con el
  dashboard) y `formatear_kpi()` decide pesos/porcentaje/Nota por el nombre
  de la columna.
- **`graficos.py`** — gráficos SVG propios (barras, dona) sin dependencias
  externas, para incrustar en el HTML del reporte.
- **`motor_reportes.py`** — renderiza el HTML final a un PDF válido
  (`renderizar_pdf`, o `renderizar_pdfs` para un lote entero con un solo
  Chromium).
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
pendiente/desactualizado, vía `calcular_reportes_pendientes`), `contexto
<clave>` (los números de una entidad, ya formateados y comparados contra la
cartera, para redactar la página 2 sin abrir el Excel) y `generar <clave>
--narrativa <html>` / `generar --lote <json>` (arma el documento, renderiza,
avisa si no quedó en 2 páginas y actualiza el manifiesto). Desde 2026-07-24, `Centro de Costos` avisa por consola
al final de su propio `run` (PASO 12d, `auditor_centro_costos.py`,
`_avisar_reportes_pendientes()`) si quedaron reportes pendientes tras
actualizar Análisis Financiero — best-effort: si el skill de reportes no
existe o falla, no aborta el `run` de Centro de Costos, solo omite el aviso.

**Reglas de completitud / "en desarrollo"** (spec §6): un proyecto sin las 7
columnas manuales de `CAMPOS_MANUALES_REQUERIDOS` (% Avance, Monto de Venta,
los 4 Costos Proyectados, Mano de Obra Real — "Fecha de inicio" salió el
2026-09-21) **no genera reporte** — se excluye de `listar_entidades` y de las agregaciones de
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
entidad (sin selección editorial) y estructura de secciones fija, **por eso
desde 2026-09-24 la genera `panel.py` y no el agente**: una página sin
decisiones editoriales no se redacta, se construye; página 2
es el análisis narrativo (resumen ejecutivo, fortalezas, debilidades,
notas estratégicas), con estructura libre y gráficos puntuales adicionales
si el agente los considera necesarios. La comparación ad-hoc queda
explícitamente fuera de este estándar — ver "Pendientes" en `MEMORY.md`.

Ver diseño completo:
[`docs/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md`](../docs/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md)
(addendum §10 para este estándar)
y el plan de implementación
[`docs/plans/2026-07-21-analisis-financiero-reportes-pdf-implementacion.md`](../docs/plans/2026-07-21-analisis-financiero-reportes-pdf-implementacion.md)
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
