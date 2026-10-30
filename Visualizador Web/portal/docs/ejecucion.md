# Portal — Proyectos en ejecución

Detalle de referencia: léelo solo al tocar esta parte. Las reglas generales están en `../CLAUDE.md`.

**Proyectos en ejecución** (2026-10-28, pedido del usuario: el resumen de cada proyecto en ejecución, que abra su
carpeta de «Gestión de Proyectos», donde se agreguen costos potenciales desde cotizaciones reales para evaluar si una
compra conviene y ver al tiro cómo terminaría el proyecto, donde se fije el avance y llegue a las demás herramientas,
días trabajados para estimar la mano de obra real e indicadores como el costo por día-hombre que se recalculen; «en el
centro de costos solo irán los gastos reales ingresados mediante facturas u OC»):
- **Qué es**: la vista `ejecucion` (`tipo: vista`, `#vistaEjecucion`, segunda de Control y finanzas), funciones `ej*`,
  estado `ej`. La lista son los proyectos que el Recorrido pone en Ejecución (`rcArmar`; los de más de 60 días, plegados
  abajo), con su avance, su margen estimado y lo que hay por decidir; al elegir uno (recordado en
  `quempin_portal_ejecucion`), su resumen. El proyecto elegido arriba en el portal la lleva a él (`ejAlElegirProyecto`), y
  el Recorrido la abre desde su ficha («Su resumen en ejecución»), desde «Registrar avance» y desde su columna Ejecución
  (`RC_ETAPAS`, `RC_IR.ejecucion`).
- **De dónde sale cada cifra** (`ejModelo`, solo calcula): la venta es la escrita aquí o, si no, el precio neto de su
  formulación, su cotización emitida o el valor adjudicado de la Planilla sin IVA (el monto del Análisis Financiero no
  viaja por la carpeta). Por categoría (las cuatro del Análisis Financiero): lo presupuestado (sus proyectados o, si no,
  los costos de su formulación), lo gastado (sus reales; la mano de obra, la de los días anotados aquí si hay), lo
  comprometido (las OC del cruce de proyectos con `enCentroCostos: false`, más lo marcado comprado cuya OC aún no aparece)
  y lo simulado (lo marcado en «Simular»). El costo estimado al cierre de cada categoría es lo presupuestado o, si se
  pasa, gastado + comprometido + simulado (`ejCuentas`): lo que todavía no se compra se estima con el presupuesto. Sin
  presupuesto, el margen es «con lo anotado» y no lleva semáforo; sin presupuesto ni nada anotado, no hay margen. Una OC
  sin `enCentroCostos` (el procesador no lo sabe) no se suma: así nunca se cuenta dos veces.
- **Gastos proyectados y cotizaciones**: cada uno con categoría, la línea del presupuesto que reemplaza (las de su
  formulación, con las reglas del Formulador: `js/calc.js`; para una nueva se propone la más parecida), proveedor,
  cantidad, precio sin IVA, estado (por decidir, aprobada, comprada con su OC, descartada) y si se simula. El diálogo
  (`#dlgEjCosto`) evalúa mientras se escribe, al lado del formulario (`ejEvaluar`): contra su línea (hasta 3 % más cara
  bien, hasta 15 % revisar), contra lo que QUEMPIN pagó (`publicado/precios-referencia.json` con el buscador del Cotizador,
  `js/busqueda.js`; se compara sola con la hoja más parecida si cubre la mitad de lo pedido, y se elige otra o ninguna),
  contra las otras cotizaciones para lo mismo (`grupo`: se simula una a la vez; aprobar o comprar una descarta las demás
  por decidir), contra lo que queda en su categoría y contra el margen. Una más barata que su línea no queda «No conviene»
  aunque la categoría ya venga gastada. «Pegar una cotización» lee las filas con el lector del Formulador (`js/pegar.js`).
  Una OC del proyecto con el mismo proveedor y neto (±2 %) se ofrece para marcarla comprada.
- **Mano de obra**: los días trabajados, una cosa por persona y día (id fijo: el mismo día de la misma persona no se
  duplica entre navegadores), con jornada y nivel; su costo, a las tarifas del proyecto, de su formulación o del
  Formulador. Se traen de la Planificación semanal (las últimas 4 semanas, hasta hoy), y «Llevarle» manda su total al
  Análisis Financiero como «Mano de Obra Real». No es la única forma: esa celda se sigue escribiendo en «Ingresar avance».
- **Indicadores** (`ejIndicadores`): días-hombre, costo por día-hombre, utilidad y venta por día-hombre, incidencia de
  la mano de obra y margen, presupuestados (los `kpis` de `js/calc.js`) y estimados hoy; los días-hombre al cierre son
  los presupuestados o, si ya se pasaron, los trabajados.
- **El avance** (y la fecha de término) se pide al Análisis Financiero con un `datos-proyecto` al buzón (`ejEnviarAF`, el
  mismo que usa ahora «Dar por cerrado»); un pedido sobre otro que todavía espera lleva en `reemplaza` el valor del
  anterior (`ejVisto`). `rcLeer` lee esos pedidos del buzón (`datosProyecto`) y lo que dijo el Análisis de cada uno
  (`afMensajes`): el Recorrido muestra «Avance 60 % por aplicar» y la Planificación lo cuenta, sin cambiar la etapa. Un
  pedido se retira mientras espera. Sin ficha en el Análisis, propone unirlo con una ficha sin N° del mismo nombre que su
  carpeta del Centro de Costos (manda su «N° Requerimiento») o crearla en «Ingresar avance».
- **Lo demás del resumen**: su carpeta de Gestión de Proyectos (y la de la oferta) por `quempin://carpeta`, sus OC con
  su estado, quién va esta semana (de la Planificación), sus pendientes y notas, la Carta Gantt (su avance, con «Usar»),
  y «a este ritmo de gasto» (lo gastado entre el avance).
- **Dónde se guarda**: `publicado/ejecucion/<dispositivo>.json` (esquema `ejecucion-proyectos`), un archivo por navegador
  como la Planificación: en cada `id` manda el cambio más reciente, también si es `borrado`. Lo que no alcanza a
  guardarse espera en `quempin_portal_ejecucion_pendiente`. Se relee cada 30 segundos con la vista abierta. Lo escrito en
  los campos del resumen sobrevive a cada repintado (`ej.sucios`). Ctrl Z deshace (`ejDeshacer`).
- **Colores del gráfico**: gastado gris 11, comprometido gris 7, simulado naranjo (en oscuro, grises más claros), con
  leyenda y las cifras escritas en cada fila: con los grises de la marca el validador de paleta no aprueba el croma, así
  que el color nunca es lo único que distingue.
- Con siete herramientas en Control y finanzas, el Inicio junta un poco sus filas con poco alto (≤ 640 px de marco).
- Pruebas: desde `test_proyectos_en_ejecucion_en_el_registro_y_en_el_esquema` en `test_portal.py` (datos de mentira:
  `_ejecucion_de_prueba`); las que usan `js/calc.js` o `js/pegar.js` del Formulador miran lo de ellos solo si su
  repositorio está en este equipo. La vista previa con datos reales se arma fuera del repositorio.
