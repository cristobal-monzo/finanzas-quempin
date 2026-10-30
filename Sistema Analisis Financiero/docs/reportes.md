# Análisis Financiero — reportes PDF

Detalle de referencia: léelo solo al tocar esto. Las reglas vigentes están en `../CLAUDE.md`.

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
