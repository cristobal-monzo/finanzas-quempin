# CLAUDE.md

## Rol de este agente

`Análisis Financiero` no es un módulo de puro registro como Centro de Costos —
cuando se invoque en esta carpeta, o se le pida análisis financiero de QUEMPIN en
general, actúa como **analista financiero experto para una PYME**, no solo como
ejecutor de un script:

- **Evalúa proyectos**: rentabilidad real vs. proyectada, riesgo, desviaciones que
  ameritan atención — usando `Análisis de Proyectos.xlsx` + los datos fuente de
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
proyectados que el usuario carga a mano en `Análisis de Proyectos.xlsx`, para dar
una vista de rentabilidad por proyecto — margen, desviación real vs. proyectado, y
un set de KPIs de productividad/estructura de costos. No reemplaza a Centro de
Costos ni le duplica lógica — solo lo lee (igual que Cotizador Historico).

A futuro debería poder incorporar Flujo de Caja como fuente adicional, cuando ese
módulo exista.

## Estado actual (2026-07-20)

**Implementado y probado.** Las 12 tareas del plan de implementación están
completas, revisadas y commiteadas: `Sistema/analisis_financiero.py` (bootstrap
del workbook, mapeo categoría→bucket, lectura solo-lectura de Centro de Costos,
validación de la hoja "Proyectos", creación de carpetas de proyecto, backup con
timestamp, regeneración de "Detalle Costos Reales", fórmulas de "Proyectos" e
"Indicadores", y el orquestador `ejecutar()`/`main()` con modo `dry_run`),
`Sistema/tests/` (34 tests, todos pasando) y el skill
`.claude/skills/Registro_Analisis_Financiero/` (`SKILL.md` + `driver.py`, comandos
`status`/`run`). Centro de Costos ya invoca este módulo automáticamente al final
de su propio `run` (PASO 12d en `auditor_centro_costos.py`), envuelto para que
nunca pueda abortar la corrida de Centro de Costos.

Lo que sigue pendiente de verdad: `Análisis de Proyectos.xlsx` todavía no tiene
proyectos reales cargados, así que nada de esto se ha ejercitado contra datos
reales de QUEMPIN SpA; y el dashboard HTML (Visualizador Web de este módulo)
sigue fuera de alcance, como estaba planeado desde el inicio.

**Extensión 2026-07-21**: agregadas Nota del Proyecto, columna "Cliente" +
hoja "Clientes" (CLTV) y hoja "Glosario KPIs" — ver
[`docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md`](../docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md)
y el plan de implementación
[`docs/superpowers/plans/2026-07-21-analisis-financiero-nota-clientes-implementacion.md`](../docs/superpowers/plans/2026-07-21-analisis-financiero-nota-clientes-implementacion.md).

Diseño original (fórmulas, playbook de KPIs, decisiones del brainstorming):
[`docs/superpowers/specs/2026-07-20-analisis-financiero-design.md`](../docs/superpowers/specs/2026-07-20-analisis-financiero-design.md).
Detalle e historial de la implementación (las 12 tareas, orden, decisiones
tomadas al construir):
[`docs/superpowers/plans/2026-07-20-analisis-financiero-implementacion.md`](../docs/superpowers/plans/2026-07-20-analisis-financiero-implementacion.md)
(rutas relativas a la raíz de `Finanzas QUEMPIN/`).

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
│   └── Análisis de Proyectos.xlsx             # libro de trabajo (existe, sin proyectos cargados aún)
└── Sistema Analisis Financiero/               # este archivo vive acá
    ├── CLAUDE.md                              # este archivo
    ├── MEMORY.md                              # decisiones, historial, pendientes
    ├── Respaldos/                             # backups automáticos por mes (se crea en la primera corrida real)
    ├── Sistema/                               # analisis_financiero.py + tests/ (71 tests)
    └── .claude/skills/Registro_Analisis_Financiero/  # SKILL.md + driver.py (status/run/confirmar-cliente)
```

## `Análisis de Proyectos.xlsx` — resumen del esquema (detalle completo en el spec)

Cinco hojas, todas dentro del mismo libro:

- **"Proyectos"** (una fila por proyecto): TAG (= prefijo de Centro de Costos, ej.
  `UMAG`/`CFLI`/`CCON`/`GGEN`/`MLER`), Nombre, Estado, fechas, Monto de Venta
  **sin IVA**, costos proyectados por categoría (manual, las 4: Materiales,
  Equipos, Mano de Obra, Otros), costos reales por categoría (Materiales/Equipos/
  Otros = fórmula automática desde Centro de Costos; Mano de Obra Real = manual,
  sin fuente automática hoy), totales/márgenes/desviación derivados por fórmula, y
  "Cliente" (última columna, se completa sola — ver más abajo).
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

**Regla de oro heredada de Centro de Costos**: las columnas manuales nunca se
tocan entre corridas; solo se regeneran "Detalle Costos Reales" y las fórmulas
derivadas de "Proyectos"/"Indicadores".

## Playbook de KPIs (hoja "Indicadores")

| KPI | Fórmula |
|---|---|
| Rentabilidad sobre costo | Margen Real / Total Real |
| Margen neto % | Margen Real / Monto de Venta |
| Productividad Materiales / Equipos / MO / Otros | Monto de Venta / Costo Real de esa categoría |
| Costo Materiales / Equipos / MO / Otros % de venta | Costo Real de esa categoría / Monto de Venta |
| Desviación % Materiales / Equipos / MO / Otros | Real / Proyectado − 1, por categoría |
| Nota del Proyecto (0-100) | 70% margen neto % (vs. objetivo 25%) + 30% control de desviación total |
| CLTV (hoja Clientes) | AOV × Frecuencia de compra × Vida del cliente × Margen de utilidad % |

Origen y hallazgos de rigor (por qué "ROI" se llama "Rentabilidad sobre costo",
por qué no hay columnas duplicadas de "costo por unidad de ingreso" +
"estructura %", el bug de fórmula encontrado en el archivo de ejemplo del
usuario): ver "Playbook de KPIs" en el spec — no se repite acá para no
desincronizarse.

## Precauciones

- **Nunca escribe `Centro de Costos.xlsx`** — solo lectura ahí, igual que
  Cotizador Historico. Si algo se ve desactualizado, correr Centro de Costos
  (`/Registro_Centro_de_Costos`), no este módulo.
- Las carpetas de proyecto nuevas se crean en
  `Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y
  Boletas/<Nombre>/` (fuente real que lee Centro de Costos hoy) — **nunca** en
  `Centro de Costos/Facturas y Boletas/` (legado, el script ya no la lee desde
  2026-07-17).
- `Análisis de Proyectos.xlsx` vive en la carpeta hermana `../Análisis
  Financiero/`, no acá — `RUTA_EXCEL` en `analisis_financiero.py` ya apunta
  ahí, no asumir que está junto al código. Vive dentro de OneDrive,
  sincronizada — antes de sobrescribirlo, considerar que puede tener
  ediciones manuales recientes hechas fuera de un script.
- Contiene datos financieros reales de la empresa (ventas, márgenes, costos por
  proyecto) — tratar como sensible, igual que el resto de `Finanzas QUEMPIN/`.
