# CLAUDE.md — Visualizador Web de Análisis Financiero

Contenido y arquitectura real del dashboard HTML de **Análisis Financiero**.
Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de datos,
hosting). Ver también [`../CLAUDE.md`](../CLAUDE.md) para el esquema completo
de `Análisis de Proyectos.xlsx`, y el spec de diseño
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
  `af.CAMPOS_MANUALES_REQUERIDOS` cargadas (Estado, Fecha de inicio, Monto
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

## Publicación

Claude Artifact privado. El link real vive en
[MEMORY.md de este skill](../.claude/skills/Registro_Analisis_Financiero/MEMORY.md)
— no se regenera salvo pedido explícito del usuario.
