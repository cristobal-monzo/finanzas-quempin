# Análisis Financiero — el libro, el playbook de KPIs y las auditorías

Detalle de referencia: léelo solo al tocar esto. Las reglas vigentes están en `../CLAUDE.md`.

## El libro

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

## Playbook de KPIs (hoja «Indicadores»)

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
