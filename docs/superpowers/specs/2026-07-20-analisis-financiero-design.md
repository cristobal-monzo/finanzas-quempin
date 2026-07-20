# Diseño: módulo Análisis Financiero

Fecha: 2026-07-20
Estado: aprobado por el usuario (brainstorming), pendiente de plan de implementación.

## Qué es

`Análisis Financiero` es un módulo nuevo de `Finanzas QUEMPIN` cuyo rol es **consolidar
cross-módulo**: toma los costos reales que ya calcula Centro de Costos (por proyecto,
por categoría de ítem) y los cruza contra ventas y costos proyectados que el usuario
carga a mano, para dar una vista de rentabilidad por proyecto. No reemplaza a Centro
de Costos ni le duplica lógica — solo lo lee.

A futuro debería poder incorporar Flujo de Caja como fuente adicional, cuando ese
módulo exista.

## Rol del agente (no solo automatización — análisis)

A diferencia de Centro de Costos (que es un pipeline de registro), este módulo
también define un **rol consultivo**: cuando se invoque en esta carpeta, o se le
pida análisis financiero de QUEMPIN en general, el agente actúa como **analista
financiero experto para una PYME**, no solo como ejecutor de un script:

- **Evalúa proyectos**: rentabilidad real vs. proyectada, riesgo, desviaciones que
  ameritan atención — usando `Análisis de Proyectos.xlsx` + los datos fuente de
  Centro de Costos.
- **Propone y depura KPIs**: sugiere métricas nuevas cuando detecta una pregunta de
  negocio sin métrica que la responda, y señala explícitamente cuándo un KPI
  existente no aporta señal (vanity metrics, redundancias matemáticas entre dos
  KPIs, promedios no ponderados que un outlier distorsiona) — nunca acumula
  métricas por acumularlas. Ver "Playbook de KPIs" más abajo para el primer set.
- **Decide cómo presentar**: para cada análisis, elige la forma más clara de
  mostrarlo (tabla, resumen ejecutivo, o delegar a un gráfico) según la audiencia.
  La forma de presentación pensada a mediano plazo es un **dashboard HTML** (mismo
  patrón que ya existe para Centro de Costos en `Visualizador Web/`) — **no se
  construye en v1**, pero el diseño de datos de este módulo (hoja "Indicadores"
  100% fórmulas, un valor limpio por proyecto y KPI) ya queda listo para que un
  futuro `build_visualizador.py` de este módulo lo consuma sin rediseñar el Excel.
- **Análisis financiero total**: puede cruzar todos los módulos (Centro de Costos,
  Cotizador Historico, y Flujo de Caja cuando exista) para dar una vista
  consolidada de la empresa, no solo por módulo aislado.
- Hereda el principio no negociable de rigurosidad numérica ya establecido para
  QUEMPIN (ver `.claude/agents/analista-financiero-quempin.md`): nunca inventa
  cifras, siempre trazable a la fuente, señala inconsistencias en vez de
  ocultarlas o "arreglarlas" en silencio.

## Por qué

El usuario ya tiene una carpeta `Análisis Financiero/` con un Excel en blanco
(`Análisis de Proyectos.xlsx`) pensado para llevar, por proyecto: monto de venta,
costos proyectados por categoría, y costos reales por categoría — para poder ver
margen y desviación real vs. proyectado a medida que el proyecto avanza. Hoy ese
cruce (costos reales por proyecto) ya existe en Centro de Costos pero no en una
vista consolidada por proyecto con venta y proyección.

## Alcance v1

- **Fuente de datos real**: solo Centro de Costos (`Centro de Costos/Excel/Centro de
  Costos.xlsx`, hoja `Detalle`). Solo lectura — este módulo nunca escribe ahí.
- **Categorías con costo real automático**: Materiales y Equipos (agregadas desde
  `categoria_item` de Centro de Costos). **Mano de Obra Real queda 100% manual** —
  hoy no existe esa categoría en los datos de Centro de Costos (boletas de
  honorarios, planillas); si aparece una fuente en el futuro, se automatiza en una
  iteración posterior, no en esta.
- **TAG de proyecto = prefijo de Centro de Costos** (`PREFIJOS_PROYECTO` /
  `N° Ref.`, ej. `UMAG`, `CFLI`, `CCON`, `GGEN`, `MLER`) — mismo identificador en
  ambos módulos, sin mapeo aparte que mantener sincronizado.
- **Disparo**: encadenado al `run` de Centro de Costos (`Sistema/
  auditor_centro_costos.py`, nuevo paso 12d, después del paso 12c del Visualizador
  Web) — cada corrida de Centro de Costos deja `Análisis de Proyectos.xlsx` al día
  solo. También disponible como skill aparte para refrescar sin correr todo Centro
  de Costos.
- **Creación de carpetas de proyecto**: si una fila nueva aparece en
  `Análisis de Proyectos.xlsx` (TAG que no tiene carpeta), el módulo crea
  `Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/
  <Nombre del proyecto>/` (fuente real que lee Centro de Costos hoy — **no** la
  carpeta legado `Centro de Costos/Facturas y Boletas/`, que el script ya no lee
  desde 2026-07-17). Nombre completo del proyecto, no el TAG, para calzar con la
  convención de nombres de carpeta que ya usa Centro de Costos.
- Sin registro de estado aparte: la existencia de la carpeta en disco es la fuente
  de verdad de "¿ya se creó?" — no se mantiene un JSON de "proyectos conocidos".

## Estructura del módulo

```
Análisis Financiero/
├── CLAUDE.md                              # charter del módulo
├── Análisis de Proyectos.xlsx             # libro de trabajo (ya existe, hoy vacío)
├── Respaldos/                             # backups automáticos, por mes, antes de cada escritura
├── Sistema/
│   ├── analisis_financiero.py             # lógica: leer Centro de Costos.xlsx, agregar reales, crear carpetas
│   └── tests/
├── docs/superpowers/                      # este spec + futuros planes
└── .claude/skills/Registro_Analisis_Financiero/
    ├── SKILL.md
    ├── MEMORY.md                          # preferencias/histórico del skill
    └── driver.py                          # comandos: status | run
```

## `Análisis de Proyectos.xlsx`

### Hoja "Proyectos" (resumen, una fila por proyecto)

| Columna | Origen | Notas |
|---|---|---|
| TAG proyecto | manual | = prefijo de Centro de Costos |
| Nombre del proyecto | manual | usado para nombrar la carpeta en Centro de Costos |
| Estado | manual | ej. Adjudicado / En curso / Cerrado |
| Fecha de inicio | manual | |
| Fecha de cierre | manual | |
| Monto de Venta (sin IVA) | manual | |
| Costos Materiales Proyectados | manual | |
| Costos Equipos Proyectados | manual | |
| Mano de Obra Proyectada | manual | |
| Otros Costos Proyectados | manual | |
| Costos Materiales Reales | **fórmula** `SUMIFS` sobre hoja "Detalle Costos Reales" (TAG + Bucket=Materiales) |
| Costos Equipos Reales | **fórmula** `SUMIFS` (TAG + Bucket=Equipos) |
| Otros Costos Reales | **fórmula** `SUMIFS` (TAG + Bucket=Otros) |
| Mano de Obra Real | manual | sin fuente automática en v1 |
| Total Proyectado | fórmula: suma de los 4 proyectados |
| Total Real | fórmula: suma de los 4 reales (3 automáticos + MO manual) |
| Margen Proyectado | fórmula: Venta − Total Proyectado |
| Margen Real | fórmula: Venta − Total Real |
| Desviación % (Real vs Proyectado) | fórmula: Total Real / Total Proyectado − 1 |

Todas las columnas manuales se respetan entre corridas (regla de oro heredada de
Centro de Costos) — el script nunca las toca, solo escribe la hoja "Detalle Costos
Reales" y las fórmulas de la hoja "Proyectos" si faltan.

### Hoja "Detalle Costos Reales" (una fila por proyecto + subcategoría)

100% regenerada en cada corrida desde `Centro de Costos.xlsx` (mismo patrón que las
hojas de proyecto de Centro de Costos: se recalcula completa, no se acumula a mano).

| TAG proyecto | Subcategoría (`categoria_item` tal cual) | Bucket | Total sin IVA |
|---|---|---|---|
| CFLI | Consumibles | Materiales | 123.456 |
| CFLI | Equipos-Herramientas | Equipos | 80.000 |
| CFLI | Combustible | Otros | 45.000 |

Preserva el detalle real de cada subcategoría (Combustible, Herramientas manuales,
etc.) aunque la hoja "Proyectos" solo muestre 3 buckets agregados — así no se pierde
granularidad al resumir.

**Mapeo `categoria_item` → Bucket** (constante en `analisis_financiero.py`, mismo
patrón que `PREFIJOS_PROYECTO` en Centro de Costos):

- `Materiales`, `Consumibles` → **Materiales**
- `Equipos-Herramientas` → **Equipos**
- cualquier `categoria_item` no mapeado explícitamente → **Otros**, con aviso en
  consola (para decidir después si merece su propio mapeo, nunca se pierde en
  silencio)

## Playbook de KPIs

### Origen: análisis de un archivo de ejemplo (ya no existe en el repo)

El 2026-07-20 el usuario dejó temporalmente `Ejemplo de indicadores.xlsx` en la
raíz de `Finanzas QUEMPIN/` (un análisis real de proyectos anteriores de la
empresa, con tablas dinámicas y referencias externas a RRHH/Órdenes de Compra) —
**se elimina del repo, este módulo no depende de él**, solo se documentan aquí
las fórmulas y hallazgos para no perderlos.

Extraídas las fórmulas reales de esos 4 proyectos, se encontraron:

1. **Bug real en el archivo**: para el proyecto "Academia Politécnica Naval", el
   indicador "Productividad Materiales" estaba calculado como
   `Ingreso / Costos TOTALES` en vez de `Ingreso / Costo Materiales` — los otros 3
   proyectos del mismo archivo sí usaban el costo de materiales solo (error de
   copiar/pegar la fórmula entre columnas). Este módulo implementa la definición
   correcta y consistente para todos los proyectos.
2. **"Rentabilidad por cliente (ROI)" está mal nombrado**: lo que calculaban
   (Utilidad Neta / Costos Totales) es una **rentabilidad sobre costo** (markup),
   no un ROI en sentido estricto (que divide por capital invertido, no por
   costos). Se renombra a "Rentabilidad sobre costo" en este módulo — decisión
   del usuario, 2026-07-20 — para no confundirlo con un ROI de inversión real.
3. **Mezcla de bases IVA** en el archivo original: "Ingreso" estaba IVA incluido
   contra costos (MO, materiales) que no lo llevan — infla los indicadores
   ~19% de forma artificial. No aplica acá: `Análisis de Proyectos.xlsx` usa
   "sin IVA" de forma consistente en todas sus columnas (ver más arriba), así
   que los indicadores replicados quedan correctos por diseño, sin ese sesgo.
4. **Redundancia matemática, dos veces**: "Costo de MO/Materiales por unidad de
   ingreso" del archivo original es el recíproco exacto de "Productividad
   MO/Materiales" (misma señal, forma inversa) — se mantienen ambas por
   legibilidad (distintas audiencias leen mejor una u otra). Y al diseñar el
   agregado de "estructura de costos como % de venta" propuesto en el
   brainstorming, se detectó que es **el mismo número** que "costo por unidad de
   ingreso" (Costo Categoría / Venta) — no se duplica esa columna, queda 1 sola.
5. El archivo original solo cubría MO y Materiales, sin Equipos ni Otros. Este
   módulo cubre las 4 categorías por consistencia (decisión del usuario,
   2026-07-20) — igual tratamiento para las 4, no solo 2.

### Hoja "Indicadores" (una fila por proyecto, 100% fórmulas sobre la hoja "Proyectos")

| Columna | Fórmula (sobre hoja "Proyectos") |
|---|---|
| TAG proyecto | referencia directa |
| Nombre del proyecto | referencia directa |
| Rentabilidad sobre costo | Margen Real / Total Real |
| Margen neto % | Margen Real / Monto de Venta |
| Productividad Materiales | Monto de Venta / Costos Materiales Reales |
| Productividad Equipos | Monto de Venta / Costos Equipos Reales |
| Productividad MO | Monto de Venta / Mano de Obra Real |
| Productividad Otros | Monto de Venta / Otros Costos Reales |
| Costo Materiales % de venta | Costos Materiales Reales / Monto de Venta |
| Costo Equipos % de venta | Costos Equipos Reales / Monto de Venta |
| Costo MO % de venta | Mano de Obra Real / Monto de Venta |
| Costo Otros % de venta | Otros Costos Reales / Monto de Venta |
| Desviación % Materiales (Real vs. Proyectado) | Materiales Reales / Materiales Proyectados − 1 |
| Desviación % Equipos (Real vs. Proyectado) | Equipos Reales / Equipos Proyectados − 1 |
| Desviación % MO (Real vs. Proyectado) | MO Real / MO Proyectada − 1 |
| Desviación % Otros (Real vs. Proyectado) | Otros Reales / Otros Proyectados − 1 |

Todas fórmulas de Excel (no valores escritos por Python), mismo patrón que la
hoja "Proyectos" — se recalculan solas si cambia cualquier dato de entrada
(manual o automático), nunca se desincronizan entre hojas.

## Flujo de ejecución (`analisis_financiero.py`, llamado desde el `run` de Centro de Costos o desde su propio driver)

1. **Backup** de `Análisis de Proyectos.xlsx` a `Respaldos/<Mes Año>/...` (si el
   archivo ya existe con datos).
2. **Leer hoja "Proyectos"**: por cada fila con TAG y Nombre válidos, verificar si
   `Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/
   <Nombre>/` existe; si no, crearla. Filas sin TAG o sin Nombre se saltan con
   aviso. TAG duplicado: se usa la primera fila, se avisa de las siguientes.
3. **Leer `Centro de Costos.xlsx` → `Detalle`** (solo lectura): agrupar
   `Total sin IVA` por (prefijo de `N° Ref.`, `categoria_item`).
4. **Regenerar hoja "Detalle Costos Reales"** completa a partir de ese agrupamiento.
5. **Asegurar fórmulas** de las columnas automáticas/derivadas en la hoja
   "Proyectos" (`SUMIFS`, totales, márgenes, desviación) para cada fila — sin tocar
   columnas manuales.
6. **Asegurar fórmulas de la hoja "Indicadores"** (una fila por proyecto,
   referenciando la hoja "Proyectos" — ver "Playbook de KPIs" arriba).
7. **Informe en consola**: proyectos nuevos detectados (carpeta creada), categorías
   no mapeadas caídas en "Otros", filas saltadas por datos incompletos.

Ningún paso de este flujo aborta el `run` de Centro de Costos si falla (archivo
abierto, permisos de carpeta, etc.) — solo advierte, mismo patrón que el paso del
Visualizador Web (12c).

## Tests (`Sistema/tests/`)

- Mapeo `categoria_item` → Bucket, incluyendo el caso "no mapeado → Otros con aviso".
- Detección de carpeta de proyecto faltante → se crea; si ya existe → no se
  duplica ni se toca.
- Agrupamiento de `Detalle` de Centro de Costos por (prefijo, categoria_item) con
  datos de ejemplo.
- Idempotencia: correr dos veces sin cambios en Centro de Costos deja la
  hoja "Detalle Costos Reales" y las fórmulas de "Proyectos" idénticas.
- Filas con TAG/Nombre faltante o duplicado no rompen la corrida.

## Fuera de alcance v1 (explícito)

- Dashboard HTML de presentación (ver "Rol del agente" arriba) — la hoja
  "Indicadores" ya queda lista para alimentarlo, pero el build/publish es una
  iteración posterior, análoga a `Visualizador Web/` de Centro de Costos.
- Automatizar Mano de Obra Real (no hay fuente de datos hoy).
- Integrar Flujo de Caja (módulo no iniciado todavía).
- Validaciones de datos en Excel (dropdowns para "Estado", etc.) — se puede agregar
  después sin romper nada, no es parte del cruce de datos que es el objetivo de v1.
- Editar `PREFIJOS_PROYECTO` de Centro de Costos automáticamente: si el TAG que el
  usuario usa en Análisis de Proyectos.xlsx no coincide con el prefijo que Centro de
  Costos derivaría solo del nombre del proyecto, el módulo solo avisa en consola —
  agregarlo a mano a `PREFIJOS_PROYECTO` queda en manos del usuario, para no hacer
  que este módulo edite el código fuente de otro.
