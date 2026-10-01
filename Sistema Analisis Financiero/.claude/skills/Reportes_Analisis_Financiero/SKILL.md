---
name: Reportes_Analisis_Financiero
description: Usar cuando el usuario escribe "/Reportes_Analisis_Financiero" explícitamente. Si en cambio pide en lenguaje natural (sin el "/") un reporte PDF de un proyecto/cliente/categoria, una comparacion entre proyectos/clientes, o ver que reportes quedaron desactualizados, pedir confirmación antes de invocarlo (ver CLAUDE.md raíz § Invocación de skills) -- nunca activarlo automático. Genera y mantiene al dia los reportes PDF de Analisis Financiero (por proyecto, por cliente, por categoria, y comparaciones ad-hoc), con marca QUEMPIN.
---

# Reportes Analisis Financiero

Reportes PDF de 2 paginas con la marca oficial de QUEMPIN:

- **Pagina 1 -- el panel de verificacion: la arma `Reportes/panel.py`, NO el
  agente.** No tiene decisiones editoriales (el estandar es "todos los KPIs
  de la entidad, sin seleccion"), asi que escribirla a mano era trabajo
  deterministico pagado como redaccion, y dos reportes escritos en sesiones
  distintas no quedaban iguales.
- **Pagina 2 -- el analisis: eso si lo escribe el agente**, y es lo unico.

Diseno completo:
`docs/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md`
(raiz de `Finanzas QUEMPIN/`).

## Comandos

```
D=".claude/skills/Reportes_Analisis_Financiero/driver.py"   # desde Sistema Analisis Financiero/

py -3.14 "$D" status                       # que reportes quedaron pendientes/desactualizados
py -3.14 "$D" contexto "proyecto:UMAG"     # los numeros de esa entidad, para redactar
py -3.14 "$D" generar "proyecto:UMAG" --narrativa analisis_umag.html
py -3.14 "$D" generar --lote lote.json     # varios de una (un solo Chromium)
```

`contexto` acepta varias claves de una. `--lote` toma un JSON
`{"proyecto:UMAG": "analisis_umag.html", "cliente:X": "analisis_x.html"}`.

`generar` arma el documento (pagina 1 + la narrativa), renderiza el PDF en
`Análisis Financiero/Reportes/{Proyectos,Clientes,Categorías}/`, avisa si no
quedo en 2 paginas y actualiza el manifiesto de obsolescencia. No hay que
llamar a `estado_reportes` a mano.

## Flujo del agente

1. `status` -> las claves pendientes (`proyecto:TAG` / `cliente:Nombre` /
   `categoria:Nombre`).
2. `contexto <clave>` -> ~20 lineas con todo lo necesario para el analisis:
   identificacion y estado, venta y su peso en la cartera, presupuesto ->
   real -> estimado al cierre, margen y Nota contra la mediana de la cartera,
   la tabla por categoria de gasto **con el sesgo de la cartera al lado**,
   las alertas del proyecto y la concentracion de clientes. No hay que abrir
   el Excel ni volcar los dicts del paquete.
3. Escribir SOLO el analisis en un `.html` suelto (ver abajo) y pasarlo a
   `generar`.

Si la entidad no tiene sus datos manuales completos no aparece en `status` y
`generar` falla con `DatosIncompletosError`: explicarle al usuario que campo
falta, nunca inventarlo.

## Que escribe el agente (pagina 2)

Solo el cuerpo: `generar` le pone el encabezado con marca, el salto de
pagina y el footer. Estructura esperada:

```html
<h2>Análisis — Proyecto UMAG</h2>
<div class="destacado"><p>Resumen ejecutivo, 2-4 oraciones.</p></div>
<h3>Fortalezas</h3>
<ul class="lista-analisis"><li>Cifra concreta + <strong>conclusión</strong>.</li></ul>
<h3>Debilidades / riesgos</h3>
<ul class="lista-analisis">...</ul>
<h3>Análisis de KPIs</h3>
<p>Prosa corta: cada KPI contra una referencia (objetivo del playbook,
mediana de la cartera, sesgo de la categoría), no el valor desnudo.</p>
<div class="decision"><h3>Qué hacer con esto</h3>
<ol class="lista-analisis"><li>Implicancia para una decisión futura.</li></ol></div>
```

- **Listas con `<strong>` en la cifra o la conclusion de cada punto**, no
  parrafos largos; prosa solo en el resumen ejecutivo y en el analisis de
  KPIs.
- **Interpretar, no repetir**: la pagina 1 ya muestra todos los numeros. La
  pagina 2 dice que significan y contra que se comparan -- para eso
  `contexto` trae la mediana de la cartera y el sesgo por categoria.
- **Todo monto en pesos va con `brand.formatear_moneda`** ("$1.293.765"), o
  copiado tal cual de la salida de `contexto`, que ya viene formateada.
  Nunca `f"{valor:,.0f}"` (da "1,293,765", la coma al reves de la
  convencion chilena).
- Clases disponibles: `destacado` (caja de resumen), `decision` (caja de
  cierre), `lista-analisis`, `fila-2-col`. Estan en `brand.CSS_BASE_REPORTE`;
  si hace falta un ajuste, extender ahi, no poner un `<style>` inline.
- Un proyecto `EN DESARROLLO` ya sale marcado en la pagina 1: no presentarlo
  como cerrado ni evaluado en forma definitiva en la prosa.

## Gotchas

- **Nunca genera contenido sin que se le pida** -- `status`/`run` solo
  detectan y listan.
- **La comparacion ad-hoc NO tiene layout de 2 paginas definido**
  (addendum 2026-07-24 del spec, §10) y `panel.panel()` la rechaza a
  proposito. Si el usuario pide una comparacion, definir su estructura con
  el antes de redactarla. No pasa por el manifiesto de obsolescencia.
- **El contexto de cartera no entra al hash del manifiesto** (viaja en la
  clave `_contexto`): si entrara, tocar un solo proyecto dejaria los ~20
  reportes desactualizados de golpe.
- **`playwright` debe estar instalado** (`py -3.14 -m pip install
  playwright && py -3.14 -m playwright install chromium`).
- **Si `generar` avisa "OJO: N paginas"**, el contenido de la pagina 2 se
  paso de largo: acortar las listas, no achicar la pagina 1.
- **Un cambio en `panel.py` o en el CSS se verifica mirando el PDF**, no
  contando paginas: renderizar a PNG con PyMuPDF y leer la imagen.
  ```python
  import fitz
  doc = fitz.open(ruta_pdf)
  doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(ruta_png)
  ```
- **Un KPI nuevo en `HEADERS_INDICADORES` hay que sumarlo a un bloque de
  `panel.BLOQUES_INDICADORES`** -- `tests/test_panel.py` falla si no, para
  que no quede fuera del PDF en silencio (ya paso con los 2 KPIs de
  2026-07-28).
