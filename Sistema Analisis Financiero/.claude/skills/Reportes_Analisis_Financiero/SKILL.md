---
name: Reportes_Analisis_Financiero
description: Genera y mantiene al dia los reportes PDF de Analisis Financiero (por proyecto, por cliente, por categoria, y comparaciones ad-hoc), con marca QUEMPIN. Usar cuando el usuario pida un reporte PDF de un proyecto/cliente/categoria, una comparacion entre proyectos/clientes, o ver que reportes quedaron desactualizados.
---

# Reportes Analisis Financiero

Construye PDFs de analisis financiero especializado (KPIs, graficos, tablas,
comparativas) con la marca oficial de QUEMPIN. El **contenido de cada reporte
lo redacta el agente** en la conversacion -- este skill solo expone la
infraestructura (datos, marca, render) y detecta que reportes quedaron
desactualizados. Ver
`docs/superpowers/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md`
(raiz de `Finanzas QUEMPIN/`) para el diseno completo.

## Comandos

**`status`** -- solo lectura: lista que reportes (proyecto/cliente/categoria)
estan pendientes o desactualizados.

```
python ".claude/skills/Reportes_Analisis_Financiero/driver.py" status
```

**`run`** -- misma deteccion que `status`, pero pensada para que el agente
tome la lista y redacte/renderice cada reporte pendiente a continuacion (este
comando no genera contenido por si solo).

```
python ".claude/skills/Reportes_Analisis_Financiero/driver.py" run
```

## Como redactar y renderizar un reporte (flujo del agente)

1. Armar el paquete de datos: `datos_reportes.paquete_datos_proyecto/cliente/categoria/comparacion(RUTA_EXCEL, ...)`.
   Si el proyecto no tiene todos sus datos manuales cargados, esta llamada
   lanza `DatosIncompletosError` -- **no generar el reporte en ese caso**
   (ni improvisar los datos que faltan).
2. Si el paquete de un proyecto trae `en_desarrollo: true` (sin fecha de
   cierre, o con una posterior a hoy), incluir un indicador visual explícito
   ("EN DESARROLLO") en el reporte -- nunca presentarlo como un proyecto
   cerrado y evaluado en forma definitiva.
3. Redactar el `contenido_html` del reporte envuelto en **exactamente 2**
   `<div class="pdf-pagina">...</div>` (para Proyecto/Cliente/Categoria --
   la comparacion ad-hoc todavia no tiene layout definido, ver Gotchas):
   - **Pagina 1 -- panel de verificacion, misma estructura siempre**: tabla
     **completa** de KPIs (todos los indicadores relevantes a la entidad,
     nunca un subconjunto elegido editorialmente), datos clave (montos,
     costos, desviacion) y el/los grafico(s) estandar de apoyo via
     `graficos.grafico_barras_svg`/`grafico_dona_svg`. El contenido (que
     KPIs/columnas) varia segun el tipo de entidad, pero el orden de
     secciones de esta pagina es siempre el mismo.
     - **Todo grafico de dona o de barras por categoria lleva leyenda de
       color**: `graficos.leyenda_html(etiquetas, colores)`. Si hay mas de
       una categoria de gasto en un mismo grafico de barras, cada categoria
       usa su propio color (parametro `colores` de `grafico_barras_svg`,
       misma paleta que la leyenda) -- no todas las barras del mismo color.
       Para diferenciar Proyectado vs Real dentro de una misma categoria sin
       perder el color de la categoria, usar `opacidades` (ej. Proyectado
       0.4, Real 1.0) en vez de un color distinto.
     - **Los KPIs fuera de lo esperado van en negrita/naranjo** en la tabla
       (clase CSS `alerta` en el `<td>`, ya definida en `brand.py`) --
       criterio del agente segun el caso (ej. desviaciones grandes en
       cualquier sentido, KPIs muy por sobre/bajo el objetivo del playbook),
       no hay umbral fijo en codigo.
   - **Pagina 2 -- el analisis, contenido variable**: resumen ejecutivo
     (2-4 oraciones), fortalezas (evidencia con cifras concretas),
     debilidades/riesgos (simetrico, igual con cifras), analisis de KPIs
     interpretado contra una referencia (objetivo del playbook, promedio de
     categoria, entidad similar -- no solo el valor desnudo), y notas de
     cierre con foco estrategico/financiero/empresarial (implicancia para
     una decision futura, no un resumen repetido). Puede sumar graficos
     puntuales adicionales si el analisis especifico lo amerita -- sin
     estructura fija aca.
     - **Preferir listas (`<ul>`/`<ol>`) con `<strong>` en las cifras/
       conclusiones clave de cada punto** por sobre parrafos largos de
       prosa, salvo en resumen ejecutivo y analisis de KPIs (mas
       explicativos, quedan mejor en prosa corta). Objetivo: que se lea de
       corrido sin tener que releer parrafos densos.
     - Tipografia mas grande que en pagina 1 (pagina 1 compite por espacio
       con graficos/tablas; pagina 2 no) -- partir de ~13px de body text en
       vez de los ~10.5px de pagina 1.
   - El header (logo/titulo/fecha, e indicador "EN DESARROLLO" si aplica)
     va completo arriba de la pagina 1 (ya lo pone `brand.construir_html`);
     **se repite, en version compacta, al inicio de la pagina 2** via
     `brand.encabezado_html(titulo, generado_el)` -- el PDF impreso debe
     llevar marca/identificacion en todas sus paginas fisicas, no solo en
     la primera. El footer si va una sola vez, al final de la pagina 2.
4. Envolver con `brand.construir_html(titulo, generado_el, contenido_html)`.
5. Renderizar: `motor_reportes.renderizar_pdf(html, ruta_salida)` hacia
   `Análisis Financiero/Reportes/{Proyectos,Clientes,Categorías,Comparativas}/`.
6. Actualizar el manifiesto (solo para proyecto/cliente/categoria, NO para
   comparaciones ad-hoc): `estado_reportes.marcar_generado(estado, clave, datos, fecha_de_hoy)`
   y `estado_reportes.guardar_estado(RUTA_ESTADO_REPORTES, nuevo_estado)`. `clave`
   debe ser EXACTAMENTE la misma clave que le asignó `driver.listar_entidades`
   (`"proyecto:TAG"` / `"cliente:Nombre"` / `"categoria:Nombre"`) y `datos` debe
   ser el mismo paquete completo que armaste en el paso 1 -- si cualquiera de
   los dos difiere, el hash guardado nunca vuelve a calzar con el recalculado
   y ese reporte queda "desactualizado" para siempre aunque esté al día.

## Gotchas

- **Nunca genera contenido sin que se le pida** -- `status`/`run` solo
  detectan y listan, la redaccion ocurre en conversacion.
- **Comparaciones ad-hoc no pasan por el manifiesto de obsolescencia** -- se
  generan frescas cada vez, no se marcan como vigentes/desactualizadas.
- **Proyectos sin datos manuales completos nunca aparecen como pendientes**
  (`listar_entidades` los excluye) -- si el usuario pide el reporte de uno
  igual, `paquete_datos_proyecto` lanza `DatosIncompletosError`: explicarle
  qué campo falta, no inventarlo.
- **`en_desarrollo: true` no es un defecto** -- es la señal de que el
  proyecto sigue abierto (sin fecha de cierre, o con una futura); el reporte
  se genera igual, solo con el indicador visual correspondiente.
- **`playwright` debe estar instalado** (`pip install playwright && python -m playwright install chromium`) -- reutiliza el Chromium ya cacheado para Centro de Costos si la revision calza.
- **`graficos.grafico_barras_svg` no valida valores negativos** -- KPIs como
  "Margen Real" o "Desviación %" pueden ser legítimamente negativos (proyecto
  con pérdida). Un valor negativo produce una barra invisible (ancho negativo)
  y puede distorsionar la escala del resto del gráfico. Para esos KPIs usar
  una tabla o un texto destacado en vez de `grafico_barras_svg`, o graficar el
  valor absoluto con una anotación explícita de signo.
- **La comparación ad-hoc NO tiene layout de 2 páginas definido todavía**
  (addendum 2026-07-24 del spec, §10) -- si el usuario pide una comparación,
  antes de redactarla hay que definir su estructura con él, no reutilizar el
  layout de Proyecto/Cliente/Categoría sin más. Recordárselo explícitamente
  si no lo menciona.
