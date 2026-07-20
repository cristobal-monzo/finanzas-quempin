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

**Solo existe el charter (este archivo) + el Excel de trabajo, vacío.** El diseño
completo está aprobado (ver spec) pero **el script `analisis_financiero.py` y el
skill `/Registro_Analisis_Financiero` todavía no están implementados** — es la
siguiente iteración, análoga a cómo "Flujo de Caja" queda documentado sin
implementar hasta que se decida construirlo.

Diseño completo, con todas las fórmulas, el playbook de KPIs (incluyendo hallazgos
de un archivo de ejemplo del usuario que ya no existe en el repo) y las decisiones
tomadas durante el brainstorming:
[`docs/superpowers/specs/2026-07-20-analisis-financiero-design.md`](../docs/superpowers/specs/2026-07-20-analisis-financiero-design.md)
(ruta relativa a la raíz de `Finanzas QUEMPIN/`).

## Estructura del módulo (planeada — ver spec para el detalle completo)

```
Análisis Financiero/
├── CLAUDE.md                              # este archivo
├── MEMORY.md                              # decisiones, historial, pendientes
├── Análisis de Proyectos.xlsx             # libro de trabajo (ya existe, hoy vacío)
├── Respaldos/                             # (a crear) backups automáticos por mes
├── Sistema/                               # (a crear) analisis_financiero.py + tests
└── .claude/skills/Registro_Analisis_Financiero/  # (a crear) SKILL.md + driver.py
```

## `Análisis de Proyectos.xlsx` — resumen del esquema (detalle completo en el spec)

Tres hojas, todas dentro del mismo libro:

- **"Proyectos"** (una fila por proyecto): TAG (= prefijo de Centro de Costos, ej.
  `UMAG`/`CFLI`/`CCON`/`GGEN`/`MLER`), Nombre, Estado, fechas, Monto de Venta
  **sin IVA**, costos proyectados por categoría (manual, las 4: Materiales,
  Equipos, Mano de Obra, Otros), costos reales por categoría (Materiales/Equipos/
  Otros = fórmula automática desde Centro de Costos; Mano de Obra Real = manual,
  sin fuente automática hoy), y totales/márgenes/desviación derivados por fórmula.
- **"Detalle Costos Reales"** (una fila por proyecto + subcategoría): preserva el
  detalle real de cada `categoria_item` de Centro de Costos (Consumibles,
  Equipos-Herramientas, Combustible si aparece, etc.) aunque "Proyectos" solo
  muestre 3 buckets agregados — nunca se pierde granularidad al resumir.
- **"Indicadores"** (una fila por proyecto): los KPIs del playbook, 100% fórmulas
  sobre "Proyectos" — ver sección siguiente.

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
- Vive dentro de OneDrive, sincronizada — antes de sobrescribir
  `Análisis de Proyectos.xlsx`, considerar que puede tener ediciones manuales
  recientes hechas fuera de un script.
- Contiene datos financieros reales de la empresa (ventas, márgenes, costos por
  proyecto) — tratar como sensible, igual que el resto de `Finanzas QUEMPIN/`.
