# Diseño: Nota de Proyecto, evaluación de Clientes (CLTV) y Glosario de KPIs

Fecha: 2026-07-21
Estado: aprobado por el usuario (brainstorming), pendiente de plan de implementación.

Extiende el diseño de
[`2026-07-20-analisis-financiero-design.md`](2026-07-20-analisis-financiero-design.md)
— no lo reemplaza. Agrega tres piezas nuevas al mismo módulo (`Sistema Analisis
Financiero/`, Excel en `Análisis Financiero/Análisis de Proyectos.xlsx`):

1. **Nota del Proyecto**: una nota 0–100 que resume rentabilidad + control de
   presupuesto en un solo número por proyecto.
2. **Cliente + hoja "Clientes" (CLTV)**: identifica cuándo un mismo cliente se
   repite entre proyectos a lo largo del tiempo, y calcula su valor de vida
   (CLTV) para priorizar atención comercial.
3. **Glosario KPIs**: una hoja que documenta, para cada KPI del libro (los ya
   existentes + los nuevos de este spec), por qué importa, qué elementos usa y
   qué significa el resultado — a pedido explícito del usuario, para que el
   Excel se explique solo sin depender de este spec.

Los KPIs del playbook original (`Rentabilidad sobre costo`, `Margen neto %`,
`Productividad`, `Costo % de venta`, `Desviación %` por categoría) no cambian
— ver spec 2026-07-20 para su definición completa.

## 1. Nota del Proyecto (hoja "Indicadores")

Escala **0–100**, aprobatorio **≥55**. Rentabilidad domina el peso, control de
desviación pesa menos:

- **Score de rentabilidad (peso 70%)**: `Margen neto %` normalizado contra un
  margen objetivo de referencia de **25%** = 100 puntos, escala lineal, con
  tope en 100 y piso en 0 si el margen es negativo.
  `score_margen = MIN(100, MAX(0, [Margen neto %] / 0.25 * 100))`
- **Score de control de desviación (peso 30%)**: basado en
  `Desviación % (Real vs Proyectado)` **total** (hoja "Proyectos", columna
  "Desviación % (Real vs Proyectado)") — mientras más cerca de 0% mejor,
  penaliza tanto sobregasto como subgasto extremo (señal de mala estimación,
  no solo de sobrecosto).
  `score_desviacion = MIN(100, MAX(0, 100 - ABS([Desviación % Total]) * 100))`
- **Nota** = `ROUND(0.7 * score_margen + 0.3 * score_desviacion, 0)`
- **Columna "Evaluación"** (etiqueta según tramo de la nota):
  - ≥85 → "Excelente"
  - 70–84 → "Bueno"
  - 55–69 → "Aprobado"
  - <55 → "Requiere atención"

Ambas columnas son 100% fórmulas de Excel sobre "Proyectos"/"Indicadores",
mismo patrón que el resto de la hoja — se recalculan solas.

El margen objetivo (25%) y los pesos (70/30) quedan como constantes en
`analisis_financiero.py` (mismo patrón que `PREFIJOS_PROYECTO`), ajustables
sin tocar fórmulas si el benchmark cambia.

## 2. Cliente (columna nueva en "Proyectos") + flujo de confirmación

Hoy no existe un campo "Cliente" — solo "Nombre del proyecto", que a veces
mezcla cliente + iteración/fecha (ej. `"AGCID (I) FEBRERO"`, cliente real
`"AGCID"`). Se agrega una columna nueva **"Cliente"** al final de "Proyectos"
(se agrega al final, no intercalada, para no correr las letras de columna que
ya usa `ESTILO_COLUMNAS_PROYECTOS`).

### Derivación automática

Cuando aparece una fila nueva en "Proyectos" con "Cliente" vacío:

1. **Derivar candidato** del "Nombre del proyecto": cortar desde el primer
   paréntesis o patrón de fecha/mes (ej. `"AGCID (I) FEBRERO"` → `"AGCID"`),
   normalizar (mayúsculas, sin espacios extra, sin tildes).
2. **Comparar contra los valores únicos ya existentes** en la columna
   "Cliente" de otras filas:
   - **Coincidencia exacta** (tras normalizar) → se asigna solo, sin marcar
     nada.
   - **Similar pero no exacta** (similitud vía `difflib.SequenceMatcher`,
     umbral configurable — proponer 0.6) → se asigna el cliente existente
     sugerido, pero la celda queda en **fuente roja** ("Pendiente de
     revisión"), mismo convenio visual que las celdas rojas de Centro de
     Costos, y se registra en `clientes_pendientes.json` (mismo patrón que
     `correcciones_manuales.json` de Centro de Costos): TAG proyecto, nombre
     derivado, cliente sugerido, similitud, estado `"Pendiente"`.
   - **Sin parecido a ningún cliente existente** → se usa el nombre derivado
     tal cual (claramente un cliente nuevo), sin marca.
3. El script **nunca pregunta en vivo** — corre encadenado y no bloqueante al
   `run` de Centro de Costos (paso 12d), igual que el resto del módulo.

### Confirmación posterior (comando nuevo del skill)

`python driver.py confirmar-cliente` (análogo a `confirmar --todos` de
Centro de Costos): lista las filas pendientes en `clientes_pendientes.json`,
por cada una permite aceptar la sugerencia o escribir el nombre correcto,
actualiza la celda "Cliente" en "Proyectos", **recolorea la fuente a azul
marino** (convención "corregido a mano, no se sobreescribe"), y marca la
entrada como `"Confirmado"` en el JSON (se conserva para trazabilidad, no se
borra).

## 3. Hoja "Clientes" (CLTV) — una fila por cliente único

100% fórmulas sobre "Proyectos" (agrupando por la columna "Cliente" nueva):

| Columna | Fórmula / definición |
|---|---|
| Cliente | valor único de "Proyectos"!Cliente |
| AOV (Valor promedio de venta) | `AVERAGEIF` del Monto de Venta de sus proyectos |
| Vida del cliente (n° de proyectos) | `COUNTIF` — cuántos proyectos tiene registrados en total |
| Meses activo | meses entre la fecha más antigua y la más reciente de sus proyectos (Fecha de inicio/cierre), **mínimo 1** |
| Frecuencia de compra (proyectos/año) | Vida del cliente ÷ (Meses activo ÷ 12) |
| Margen de utilidad % | SUMA(Margen Real de sus proyectos) ÷ SUMA(Monto de Venta de sus proyectos) — promedio **ponderado** por venta, no simple, para que un proyecto chico no distorsione |
| CLTV | AOV × Frecuencia de compra × Vida del cliente × Margen de utilidad % |
| Clasificación | percentil de CLTV entre todos los clientes: top 33% → "Clientes estratégicos", medio 33% → "Clientes potenciales", bottom 33% → "Clientes de oportunidad" (vía `PERCENTILE` sobre la propia columna CLTV — se recalibra solo a medida que entran más clientes, no un corte fijo en pesos) |

Esto resuelve la ambigüedad del archivo de ejemplo que trajo el usuario (ahí
"Vida del cliente" y "Frecuencia" parecían mezclar conceptos sin fórmula
consistente entre filas) — acá cada columna tiene una definición única y
auditable, verificada aritméticamente contra ese mismo ejemplo
(`CLTV = AOV × Frecuencia × Vida × Margen` reproduce los totales de la fila
"TOTAL" del archivo de ejemplo como promedio simple de los CLTV
individuales).

Estilo visual: misma paleta de 4 colores y formato moneda/porcentaje que el
resto del libro, vía una nueva entrada `ESTILO_COLUMNAS_CLIENTES` siguiendo
el mismo patrón que `ESTILO_COLUMNAS_INDICADORES`.

## 4. Hoja "Glosario KPIs"

Hoja nueva, texto estático (no fórmulas, se re-escribe completa en cada
corrida). Una fila por KPI, columnas: **KPI | Por qué importa | Qué elementos
usa | Qué significa el resultado**. Cubre los KPIs del playbook original
(2026-07-20) más los nuevos de este spec:

| KPI | Por qué importa | Qué elementos usa | Qué significa el resultado |
|---|---|---|---|
| Rentabilidad sobre costo | Mide cuánto margen genera cada peso gastado en el proyecto — un markup, no un ROI de capital invertido | Margen Real, Total Real | Valor alto = el proyecto generó mucho margen por cada peso de costo incurrido; sirve para comparar eficiencia entre proyectos de tamaños distintos |
| Margen neto % | El indicador de rentabilidad más directo y comparable entre proyectos de distinto tamaño | Margen Real, Monto de Venta | 20% significa que de cada $100 vendidos quedan $20 de utilidad tras cubrir todos los costos reales |
| Productividad (Materiales/Equipos/MO/Otros) | Mide cuántos pesos de venta genera cada peso gastado en esa categoría — permite ver qué categoría "rinde" más por peso invertido | Monto de Venta, Costo Real de la categoría | Productividad = 3 → cada $1 gastado en esa categoría generó $3 de venta; útil para priorizar dónde enfocar control de gasto |
| Costo % de venta (por categoría) | Muestra la estructura de costos del proyecto — qué parte de cada peso vendido se va en esa categoría | Costo Real de la categoría, Monto de Venta | 35% en Costo MO % de venta → un tercio de cada venta se destina a mano de obra; detecta categorías que consumen desproporcionadamente el margen |
| Desviación % (por categoría, Real vs Proyectado) | Mide qué tan preciso fue el presupuesto original para esa categoría — clave para mejorar futuras cotizaciones | Costo Real, Costo Proyectado de la categoría | +15% = se gastó 15% más de lo presupuestado; negativo = se gastó menos de lo previsto |
| Nota del Proyecto | Resume rentabilidad y control de presupuesto en un solo número comparable entre proyectos, para priorizar dónde poner atención de gestión | Margen neto % (70%, contra objetivo de 25%) y Desviación % Total (30%) | ≥55 = proyecto en rango aceptable; <55 = requiere revisión (rentabilidad baja y/o descontrol presupuestario) |
| Evaluación | Traduce la nota a una etiqueta rápida de lectura para revisiones ejecutivas | Nota del Proyecto | Excelente / Bueno / Aprobado / Requiere atención |
| AOV (Clientes) | Mide el tamaño promedio de una venta a ese cliente | Monto de Venta de sus proyectos | AOV alto = cliente que trae proyectos grandes por transacción |
| Vida del cliente | Mide cuántas veces ha comprado el cliente en total — la base para saber si es recurrente | Conteo de proyectos del cliente | Vida=1 → cliente de una sola compra hasta ahora; vida>1 → recurrente |
| Meses activo | Mide cuánto tiempo lleva comprando el cliente — el denominador para anualizar la frecuencia | Fecha más antigua y más reciente entre sus proyectos | Meses activo alto + vida baja → cliente esporádico; meses activo bajo + vida alta → cliente muy activo recientemente |
| Frecuencia de compra (Clientes) | Mide qué tan seguido vuelve a comprar el cliente, anualizado — clave para proyectar ingresos futuros de ese cliente | Vida del cliente, Meses activo | Frecuencia=2 → el cliente compra en promedio 2 veces al año |
| Margen de utilidad % (Clientes) | Mide qué tan rentable es la relación completa con ese cliente, ponderado por tamaño de proyecto | Suma de Margen Real y de Monto de Venta de todos sus proyectos | Mismo significado que Margen neto % pero a nivel cliente |
| CLTV | Estima el valor total que el cliente representa para QUEMPIN a lo largo de su relación completa — la métrica central para decidir dónde invertir esfuerzo comercial | AOV × Frecuencia de compra × Vida del cliente × Margen de utilidad % | CLTV alto = cliente que ha generado y probablemente seguirá generando mucho valor; prioridad para retención |
| Clasificación (Clientes) | Traduce el CLTV a un tier accionable, relativo a la cartera actual de QUEMPIN, no a un corte fijo en pesos que quede obsoleto con el crecimiento de la empresa | Percentil del CLTV entre todos los clientes registrados | "Clientes estratégicos" (top 33%) → atención prioritaria; "Clientes de oportunidad" (bottom 33%) → candidatos a desarrollar o repensar la relación |

## Cambios de esquema resumidos

- **"Proyectos"**: + columna "Cliente" (al final, manual/derivada con flujo de
  revisión).
- **"Indicadores"**: + columnas "Nota del Proyecto" (0–100) y "Evaluación".
- **"Clientes"** (hoja nueva): AOV, Vida del cliente, Meses activo, Frecuencia
  de compra, Margen de utilidad %, CLTV, Clasificación.
- **"Glosario KPIs"** (hoja nueva): contenido estático, tabla de arriba.

## Cambios de código (`Sistema/analisis_financiero.py`)

- `HEADERS_PROYECTOS` + "Cliente"; `HEADERS_INDICADORES` + "Nota del
  Proyecto"/"Evaluación"; `HEADERS_CLIENTES` y `HEADERS_GLOSARIO_KPIS` nuevos.
- `ESTILO_COLUMNAS_CLIENTES` nuevo, siguiendo el mismo patrón de color/formato
  que las hojas existentes; "Glosario KPIs" sin color de KPI (es texto largo,
  solo encabezado en negrita + wrap + ancho generoso).
- Función de derivación + fuzzy-match de Cliente, más
  `clientes_pendientes.json` (mismo patrón que `correcciones_manuales.json`).
- Comando `confirmar-cliente` en
  `.claude/skills/Registro_Analisis_Financiero/driver.py`.
- Fórmulas de "Clientes" y de "Nota del Proyecto"/"Evaluación" se escriben en
  el mismo paso que ya escribe fórmulas de "Indicadores" (`ejecutar()`).
- Contenido de "Glosario KPIs" es una constante de texto en el código,
  reescrita completa en cada corrida (no depende de datos del usuario).

## Tests nuevos (`Sistema/tests/`)

- Derivación de Cliente desde "Nombre del proyecto" (casos con paréntesis,
  fechas, sin patrón reconocible).
- Fuzzy-match: coincidencia exacta (sin marca), similar (marca + pendiente),
  sin parecido (nuevo cliente, sin marca).
- `clientes_pendientes.json`: se crea, se lista, `confirmar-cliente` lo marca
  `"Confirmado"` y recolorea la celda.
- Fórmulas de "Clientes": AOV, Vida, Meses activo, Frecuencia, Margen
  ponderado, CLTV y Clasificación (percentiles) con datos de ejemplo con 2+
  proyectos del mismo cliente.
- Fórmula de "Nota del Proyecto"/"Evaluación": casos límite (margen negativo,
  desviación >100%, nota exactamente en los cortes 55/70/85).
- "Glosario KPIs" se escribe completo y no se duplica en corridas sucesivas.
- No-regresión de las hojas y columnas existentes del spec 2026-07-20.

## Fuera de alcance de este spec (explícito)

- Ajustar el margen objetivo (25%) o los pesos (70/30) de la Nota si tras ver
  datos reales de QUEMPIN se detecta que no calibran bien — queda para una
  iteración posterior una vez que haya proyectos reales cargados.
- Nuevos KPIs adicionales que el usuario mencionó querer agregar después de
  este spec — se cierran en una segunda ronda de brainstorming enfocada,
  decisión explícita del usuario (2026-07-21) para no mezclar alcance.
- Dashboard HTML de presentación — sigue fuera de alcance como en el spec
  2026-07-20.
