---
name: Reportes_Analisis_Financiero
description: Genera y mantiene al día los reportes PDF de Análisis Financiero por proyecto, cliente y categoría, con la marca QUEMPIN. Usar SOLO si el usuario escribe "/Reportes_Analisis_Financiero"; si pide con palabras un reporte PDF, una comparación o ver qué reportes quedaron desactualizados, confirma primero.
---

# Reportes de Análisis Financiero

PDF de 2 páginas. **La página 1 (panel de verificación) la arma `Reportes/panel.py`**: todos los KPIs de la entidad, sin
selección. **La página 2 (el análisis) la escribe el agente**, y es lo único. Diseño:
`docs/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md` (raíz de `Finanzas QUEMPIN/`).

```
D=".claude/skills/Reportes_Analisis_Financiero/driver.py"   # desde Sistema Analisis Financiero/

py -3.14 "$D" status                       # pendientes y desactualizados
py -3.14 "$D" contexto "proyecto:UMAG"     # los números para redactar; acepta varias claves
py -3.14 "$D" generar "proyecto:UMAG" --narrativa analisis_umag.html
py -3.14 "$D" generar --lote lote.json     # {"proyecto:UMAG": "analisis_umag.html", "cliente:X": "analisis_x.html"}
```

`generar` arma el documento, renderiza en `Análisis Financiero/Reportes/{Proyectos,Clientes,Categorías}/`, avisa si no quedó
en 2 páginas y actualiza el manifiesto de obsolescencia. No llames a `estado_reportes` a mano.

## Flujo

1. `status` da las claves (`proyecto:TAG`, `cliente:Nombre`, `categoria:Nombre`).
2. `contexto <clave>` trae ~20 líneas con todo: identificación, venta y peso en la cartera, presupuesto → real → estimado al
   cierre, margen y Nota contra la mediana, categorías con el sesgo de la cartera, alertas y concentración. No abras el Excel.
3. Escribe **solo el análisis** en un `.html` suelto y pásalo a `generar`.

Sin datos manuales completos la entidad no aparece en `status` y `generar` falla con `DatosIncompletosError`: explica qué
campo falta, nunca lo inventes.

## La página 2

Solo el cuerpo; `generar` pone encabezado, salto de página y pie:

```html
<h2>Análisis — Proyecto UMAG</h2>
<div class="destacado"><p>Resumen ejecutivo, 2-4 oraciones.</p></div>
<h3>Fortalezas</h3>
<ul class="lista-analisis"><li>Cifra concreta + <strong>conclusión</strong>.</li></ul>
<h3>Debilidades / riesgos</h3>
<ul class="lista-analisis">...</ul>
<h3>Análisis de KPIs</h3>
<p>Prosa corta: cada KPI contra una referencia (objetivo, mediana de la cartera, sesgo de la categoría).</p>
<div class="decision"><h3>Qué hacer con esto</h3>
<ol class="lista-analisis"><li>Implicancia para una decisión futura.</li></ol></div>
```

- Listas con `<strong>` en la cifra o la conclusión; prosa solo en el resumen y en el análisis de KPIs.
- **Interpretar, no repetir**: la página 1 ya muestra los números.
- **Todo monto** con `brand.formatear_moneda` («$1.293.765») o copiado de `contexto`. Nunca `f"{valor:,.0f}"`.
- Clases: `destacado`, `decision`, `lista-analisis`, `fila-2-col` (en `brand.CSS_BASE_REPORTE`; extiende ahí, sin `<style>` inline).
- Un proyecto `EN DESARROLLO` no se presenta como cerrado.

## Cuidados

- **Nunca genera contenido sin que se le pida.**
- **La comparación ad-hoc no tiene layout definido** y `panel.panel()` la rechaza: define su estructura con el usuario antes
  de redactar. No pasa por el manifiesto.
- **El contexto de cartera no entra al hash del manifiesto** (clave `_contexto`): si entrara, tocar un proyecto dejaría ~20
  reportes desactualizados.
- Requiere `playwright` con Chromium.
- **«OJO: N paginas»**: la página 2 se pasó; acorta las listas, no achiques la página 1.
- **Un cambio en `panel.py` o el CSS se verifica mirando el PDF**: renderiza a PNG con PyMuPDF
  (`fitz.open(ruta)[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(png)`) y lee la imagen.
- **Un KPI nuevo en `HEADERS_INDICADORES` va en un bloque de `panel.BLOQUES_INDICADORES`**: `tests/test_panel.py` falla si no.
