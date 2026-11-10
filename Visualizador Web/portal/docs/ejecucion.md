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
  `quempin_portal_ejecucion`), su resumen.
- **Todo lo de Gestión de Proyectos** (2026-11-03, pedido del usuario: «todos los proyectos que se encuentran en la carpeta
  de gestión de proyectos deben verse», sin las carpetas complementarias): el procesador publica en `proyectos.json` las
  carpetas de la raíz de Gestión (`gestion`, sin las agrupadoras «0 …» ni archivos) y `ejTarjetas` suma cada proyecto con
  carpeta ahí (`t.gestion`), nunca plegado. Si ya terminó (Cierre en el Recorrido) va al final, con el aviso de mover su
  carpeta a «0 Proyectos Entregados». Una carpeta sin N° se une por el nombre con un proyecto adjudicado (`rcGestionDe`:
  el mismo nombre o dos palabras en común, ≥ 75 % y uno solo) y pide el N°; sin parecido va sola (`gestion-<carpeta>`):
  se ve con su carpeta, pero sin N° ni TAG no se le anota nada (`ejSinClaveEl`) ni recibe cotizaciones de «Llevar». Y
  el Recorrido la abre desde su ficha («Su resumen en ejecución»), desde «Registrar avance» y desde su columna Ejecución
  (`RC_ETAPAS`, `RC_IR.ejecucion`).
- **Dos pestañas y «Solo con datos anotados»** (2026-11-09, pedido del usuario: «solo deben aparecer proyectos que se
  encuentren dentro de la carpeta de Gestión de Proyectos»; los que ya se cerraron, en una segunda pestaña con los de la
  carpeta de entregados; y una casilla para ver solo los que tienen al menos un dato en su página): `ejTarjetas(pestana)`.
  «En ejecución» = solo lo que tiene carpeta en la raíz de Gestión (`t.gestion`); un adjudicado sin carpeta ahí ya no sale
  (el Recorrido lo sigue abriendo por su clave). Si `proyectos.json` aún no trae `gestion` (`rc.datos.hayGestion`), la
  regla de antes. «Entregados» = lo que tiene carpeta en una «0 Proyectos Entregados <año>» (`entregados` de
  `proyectos.json`, `proyectos_entregados`) y no en la raíz, nunca plegado. `rcEntregadas` corre tras `rcArmar`: une cada
  carpeta con su proyecto por el N° o, sin N°, por el nombre (`rcGestionDe`, sin los que están en la raíz) y marca
  `t.entregado = {carpeta, grupo}`; las que no calzan son tarjetas aparte (`entregado-<N° o carpeta>`, en `rc.entregadas`)
  que el Recorrido no muestra. Una carpeta en la raíz y otra en los entregados lo avisa y va en «En ejecución».
  «Solo con datos anotados» (`#ejConDatos`, `ejConDatosSet`): con al menos una cosa sin borrar en `publicado/ejecucion/`
  con su N° o su TAG. La pestaña y la casilla se recuerdan (`quempin_portal_ejecucion`: `pestana`, `conDatos`); las
  pestañas se cambian con las flechas. Prueba: `test_ejecucion_solo_lo_de_gestion_y_los_entregados_en_su_pestana`.
- **De dónde sale cada cifra** (`ejModelo`, solo calcula): la venta es la escrita aquí o, si no, el precio neto de su
  formulación, su cotización emitida o el valor adjudicado de la Planilla sin IVA (el monto del Análisis Financiero no
  viaja por la carpeta). Por categoría (las cuatro del Análisis Financiero): lo presupuestado (sus proyectados o, si no,
  los costos de su formulación), lo gastado (sus reales; la mano de obra, la de los días anotados aquí si hay), lo
  comprometido (las OC del cruce de proyectos con `enCentroCostos: false`, más lo marcado comprado cuya OC aún no aparece)
  y lo simulado (lo marcado en «Simular»). El costo estimado al cierre de cada categoría es lo presupuestado o, si se
  pasa, gastado + comprometido + simulado (`ejCuentas`): lo que todavía no se compra se estima con el presupuesto. Sin
  presupuesto, el margen es «con lo anotado» y no lleva semáforo; sin presupuesto ni nada anotado, no hay margen. Una OC
  sin `enCentroCostos` (el procesador no lo sabe) no se suma: así nunca se cuenta dos veces.
- **Gastos proyectados y cotizaciones**: cada ítem con categoría, la línea del presupuesto que reemplaza (las de su
  formulación, con las reglas del Formulador: `js/calc.js`; para uno nuevo se propone la más parecida), cantidad y uno o
  varios proveedores (nombre, precio sin IVA, N° de cotización, fecha y nota), estado (por decidir, aprobada, comprada con
  su OC, descartada) y si se simula. El diálogo (`#dlgEjCosto`) evalúa al proveedor elegido mientras se escribe, al lado
  del formulario (`ejEvaluar`): contra su línea (hasta 3 % más cara
  bien, hasta 15 % revisar), contra lo que QUEMPIN pagó (`publicado/precios-referencia.json` con el buscador del Cotizador,
  `js/busqueda.js`; se compara sola con la hoja más parecida si cubre la mitad de lo pedido, y se elige otra o ninguna),
  contra los otros proveedores, contra lo que queda en su categoría y contra el margen. Una más barata que su línea no
  queda «No conviene» aunque la categoría ya venga gastada. «Pegar una cotización» lee las filas con el lector del
  Formulador (`js/pegar.js`) y deja un ítem por fila, con un proveedor. Una OC del proyecto con el mismo proveedor y neto
  (±2 %) se ofrece para marcarla comprada.
- **Varios proveedores por ítem** (2026-10-30, pedido del usuario: «distintos proveedores a un mismo item» y en la tabla
  «un menú desplegable en una columna que sea de proveedor», con el nombre y el valor, para comparar y elegir): cada
  proveedor es una cotización guardada aparte con el mismo `grupo` (el `id` de la primera), así que dos navegadores pueden
  agregar proveedores sin pisarse. La tabla muestra una fila por ítem (`ejItems`) con los datos del proveedor elegido
  (`ejElegida`: comprada, aprobada, `elegida`, simulada o, si no, la más barata); el menú (`ejMenuProveedor`) los lista de
  más barato a más caro y termina en «+ Agregar otro proveedor…». Se simula uno a la vez: elegir otro le pasa el estado y el
  «Simular» (`ejElegirProveedor`). El estado de la fila es del ítem: aprobar, comprar o descartar deja descartados a los
  demás y volver a «Por decidir» los trae de vuelta (`ejEstadoOtra`); comprado, el menú se bloquea. En el diálogo, la
  cantidad es una sola para todos, el IVA se marca por proveedor, un ítem nuevo elige solo al más barato mientras no se
  elija otro a mano, y un proveedor en blanco no cuenta. El basurero de la fila elimina el ítem completo; un proveedor se
  quita con la ✕ de su tarjeta en el diálogo.
- **Mano de obra**: los días trabajados, una cosa por persona y día (id fijo: el mismo día de la misma persona no se
  duplica entre navegadores), con jornada y nivel; su costo, a las tarifas del proyecto, de su formulación o del
  Formulador. Se traen de la Planificación semanal (las últimas 4 semanas, hasta hoy), y «Llevarle» manda su total al
  Análisis Financiero como «Mano de Obra Real». No es la única forma: esa celda se sigue escribiendo en «Ingresar avance».
- **Indicadores** (`ejIndicadores`): días-hombre, costo por día-hombre, utilidad y venta por día-hombre, incidencia de
  la mano de obra y margen, presupuestados (los `kpis` de `js/calc.js`) y estimados hoy; los días-hombre al cierre son
  los presupuestados o, si ya se pasaron, los trabajados.
- **El nombre que se ve** (2026-11-09): el lápiz ✎ junto al título de la cabecera pide al Análisis Financiero solo el **Apodo** (`datos-proyecto`, `ejGuardarNombre`); vacío = se ve el «Nombre del proyecto». El nombre pedido se ve desde ya (`rcArmar`).
- **Marcar «Cerrado»** (2026-11-10, pedido del usuario: que en Proyectos en ejecución también se pueda cambiar el estado a
  «Cerrado»): el acceso «Marcar «Cerrado»» de la cabecera (`ejCierreDe`, `ejAbrirCerrar`, `ejGuardarCerrar`, `#dlgEjCerrar`)
  manda el mismo `editar-requerimiento` que Requerimientos (`pqEnviar`, con el N° entero de la Planilla) y, marcada de
  entrada si tiene carpeta con su N° en la raíz de Gestión, el `mover-carpeta` a «0 Proyectos Entregados <año>»
  (`pqEnviarMover`) más una vuelta del procesador. Si la Planilla ya dice «Cerrado» y la carpeta sigue en Gestión, el
  acceso dice «Llevar su carpeta a entregados» y solo pide moverla. Sin N° o sin fila en la Planilla, no aparece. Pruebas:
  `test_marcar_cerrado_desde_proyectos_en_ejecucion`, `test_marcar_cerrado_sin_mover_y_ya_cerrado_solo_mueve`.
- **El avance** (y la fecha de término) se pide al Análisis Financiero con un `datos-proyecto` al buzón (`ejEnviarAF`, el
  mismo que usa ahora «Dar por cerrado»); un pedido sobre otro que todavía espera lleva en `reemplaza` el valor del
  anterior (`ejVisto`). `rcLeer` lee esos pedidos del buzón (`datosProyecto`) y lo que dijo el Análisis de cada uno
  (`afMensajes`): el Recorrido muestra «Avance 60 % por aplicar» y la Planificación lo cuenta, sin cambiar la etapa. Un
  pedido se retira mientras espera. Sin ficha en el Análisis, propone unirlo con una ficha sin N° del mismo nombre que su
  carpeta del Centro de Costos (manda su «N° Requerimiento») o crearla en «Ingresar avance».
- **Lo demás del resumen**: sus accesos (ver abajo, 2026-11-06), sus OC con
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

## Mejoras del 2026-11-06

Pedido del usuario: abrir la carpeta del proyecto en el Explorador con «Facturas del proyecto» en segundo lugar y sin
los accesos al Centro de Costos, al Análisis Financiero ni a la Carta Gantt; ver en cada proyecto sus costos registrados
en el Centro de Costos y asociar cada factura a uno o varios de sus gastos proyectados y cotizados; una tabla «Cómo va el
proyecto» más clara y con lo gastado; la mano de obra en un calendario del mes con día completo o medio día, para anotar
varios días de una vez; y una revisión de la interfaz.

- **Accesos** (`ejCabEl`): «Carpeta del proyecto» (la de Gestión o, si no pasó ahí, la de la oferta, por
  `quempin://carpeta`; no en el teléfono), «Facturas del proyecto» (SharePoint), «Pasar a Gestión de Proyectos» si
  corresponde, «Seguimiento» y «Subir documentos». Sin «Carpeta de la oferta» cuando ya está en Gestión (su copia está
  en «Formulación»).
- **Las facturas del Centro de Costos** (`ejLeerDocumentos`, `ejDocumentosEl`): las lee de
  `publicado/documentos-proyecto.json` (esquema `documentos-proyecto`, paso `documentos-proyecto` del procesador, desde el
  snapshot del tablero del CC), por el TAG o el N° del proyecto (`ejDocumentosDe`). Tabla con fecha, N° Ref. (abre el
  documento en SharePoint), proveedor y detalle, neto y «Corresponde a»; filtros Todas / Sin asociar / Asociadas, búsqueda
  que solo esconde filas (no repinta) y las 12 primeras con «Ver las N». Un documento en rojo en el CC dice «Por revisar».
- **Lo gastado** de materiales, equipos y otros sale de esas facturas, sumando sus ítems con la categoría del Análisis
  Financiero (`ejDocPorCat`): es lo mismo que suma el Análisis (comprobado el 2026-11-06: 27 de 27 proyectos iguales),
  pero al día con el último registro del CC. Sin la publicación o sin documentos del proyecto, los reales del Análisis
  (`m.gastoFuente`). La mano de obra no cambia: los días anotados o la «Mano de Obra Real».
- **Asociar** (`ejAbrirAsociar`, `#dlgEjAsociar`, se arma en JS): una cosa del archivo por factura, tipo `asociacion`
  (id `as-<clave>-<ref>`, su `ref` y `destinos`: `i:<grupo o id>` de un ítem y `l:<uid>` de una línea del presupuesto de su
  formulación; vacía = «No es de ningún gasto anotado»). El diálogo propone primero lo parecido (lo que dice la factura,
  el mismo proveedor, la categoría: «Parece») y puede marcar como comprados los ítems por decidir o aprobados (sin OC:
  la cuenta su factura). **Lo facturado** de cada destino (`ejFacturado`) reparte el neto de la factura entre sus destinos
  según lo cotizado o presupuestado de cada uno; en `ejCuentas` un ítem simulado o comprometido cuenta solo lo que falta
  facturar, para no sumar dos veces lo que ya está en lo gastado. La fila del ítem dice «Facturado $X de $Y» (en rojo si
  pasa lo cotizado en más de 2 %).
- **Cómo va el proyecto** (`ejPresupuestoEl`): «Gastado a la fecha» en grande con su barra contra el presupuesto y una
  raya en el avance, y una tabla por categoría: presupuestado, gastado, comprometido, simulado, al cierre y queda (o se
  pasa), con la barra de antes bajo cada nombre y el total. En ≤ 700 px de vista, tarjetas. El KPI nuevo «Gastado a la
  fecha» va segundo; la tarjeta de la lista también dice lo gastado.
- **Mano de obra** (`ejManoObraEl`, `ejAnotarDias`, `ejQuitarDias`): quiénes (y otra persona escrita a mano), la jornada
  (1 día / ½ día) y el calendario del mes con flechas (no pasa del mes de hoy; los días que no llegan, apagados). Un toque
  marca o desmarca un día; con el mouse, arrastrar marca todos los que toca; «Lunes a viernes» marca los hábiles del mes
  hasta hoy. «Anotar N DH» deja un `dia` por persona y día marcado (uno ya anotado cambia su jornada) y «Quitar N días
  anotados» borra lo de los elegidos (o de todos) en esos días. Cada casilla muestra las iniciales de lo anotado (½ si es
  medio día). Lo marcado vive en `ej.diasForm.dias` y no repinta la página. La lista de días quedó plegada debajo.
- **Accesos a cada parte** (`ejSaltosEl`): una fila fija arriba (Cómo va, Facturas con las sin asociar, Gastos
  proyectados con las por decidir, Mano de obra, OC/equipo/notas) que se envuelve en lo angosto (sin desplazarse de lado).
- Pruebas: `test_las_facturas_del_centro_de_costos_se_ven_y_se_asocian_a_sus_gastos` y
  `test_el_calendario_anota_varios_dias_de_una_vez_y_medio_dia` en `test_portal.py`; `Sistema Intercambio/tests/test_documentos_proyecto.py`.

## Revisión de UX/UI del 2026-11-09 (loop de mejoras)

Pedido del usuario: una herramienta que aporte al seguimiento del estado de cada proyecto, y luego al menos diez vueltas
de mejoras hasta que la pestaña se opere sin explicaciones y sea mucho más visual.

- **Mapa de salud** (`ejMapaEl`, `#ejMapa`, arriba de las tarjetas): cada proyecto es un punto según su avance
  (horizontal) y lo gastado y comprometido sobre el presupuesto (vertical; `ejPosMapa`). La diagonal es «gasta lo que
  avanza»; la franja amarilla, la tolerancia (`EJ_GASTO_SOBRE_AVANCE`), y lo de encima, «gasta más de lo que avanza».
  Al pasar o enfocar un punto dice su estado y por qué, y resalta su tarjeta; al tocarlo abre el proyecto. Se dibuja al
  ancho que tiene (`ejMapaAncho`, se repinta al cambiar la ventana). Al lado, cuántos hay en cada estado: tocar uno filtra
  las tarjetas (`ej.salud`, no se recuerda). Los que no tienen presupuesto o avance van en una línea bajo los estados.
- **El estado** (`ejSalud`, `EJ_SALUD`): «En riesgo», «Atención», «En línea» o «Sin datos», con sus motivos: margen
  estimado contra la meta y el mínimo, lo gastado contra el avance (más del doble de la tolerancia, en riesgo), si
  terminaría sobre el presupuesto y los avisos del Recorrido. La tarjeta lo dice con ícono y palabra (`.ej-salud`) y su
  raya de color sale de ahí. Nunca solo el color: íconos `visto`, `exclama`, `cruz`, `guion`.
- Prueba: `test_el_mapa_de_salud_ubica_cada_proyecto_y_filtra_por_estado`.
- **Vuelta 2, la tarjeta de la lista** (`ejTarjetaEl`, `ejAnilloEl`): el avance en un anillo (naranjo si es un pedido que
  espera), lo gastado y comprometido en una barra contra el presupuesto con la raya naranja del avance (si la barra pasa
  la raya, gasta más de lo que avanza), el margen y, abajo, lo que falta hacer con su número (compras por decidir,
  facturas sin asociar, pendientes). Bajo el título, dónde y su TAG, con el estado y el responsable a la derecha.
- **Vuelta 3, «Por hacer»** (`ejTareas`, `ejPorHacerEl`, bajo los KPI): lo que el proyecto espera, cada cosa con su
  botón: facturas sin asociar (filtra «Sin asociar» y baja a ellas), compras por decidir, días de la Planificación sin
  anotar («Traerlos», `ejTraerPlanificacion`), la mano de obra real que no llegó al Análisis («Llevarla»), el avance de la
  Carta Gantt distinto, sin fecha de término, sin ficha en el Análisis, avance 100 % («Dar por cerrado») y los
  pendientes. Sin nada, «Todo al día». `ejIrA` baja a una parte y la marca un momento (`.ej-destello`); lo usan también
  los accesos. Prueba: `test_por_hacer_dice_lo_que_espera_el_proyecto_y_lo_hace_ahi_mismo`.
- **Vuelta 4, la cabecera** (`ejCabEl`): una tarjeta con la raya del color de su estado; N°, nombre y una línea con dónde,
  quién lo lleva, su TAG, su formulación y sus avisos; a la derecha (abajo en lo angosto) su estado con el motivo
  principal (`.ej-cab-estado`); abajo, los accesos. «Todos los proyectos» (`.ej-volver`) es un enlace discreto arriba.
- **Vuelta 5, accesos y cifras**: los accesos (`ejSaltosEl`, ahora con «Avance») marcan con `aria-current` la parte a la
  vista (`ejMarcarSalto`, al desplazar `#vistaEjecucion`; arriba de todo ninguna, al fondo la última, Cómo va y Avance
  lado a lado cuentan como la primera). Cada KPI salvo la venta lleva un gráfico chico (`ejMini`): gastado y
  comprometido con la raya del avance, el cierre contra el presupuesto (lo que se pasa en rojo), el margen contra el
  mínimo y la meta, y el avance. Prueba: `test_los_accesos_marcan_la_parte_a_la_vista_y_las_cifras_llevan_su_grafico`.
- **Vuelta 6, cambiar el avance** (`ejAvanceForm`): botones +5, +10, +25 y «Terminado 100 %», «Como estaba» para
  volver; la barra del panel muestra en naranjo rayado el tramo que se va a guardar (`#ejAvPrevia`; rojo si baja) y
  junto al número «→ 50 %» (`#ejAvCambio`). El botón dice qué guarda («Guardar 50 % en el Análisis Financiero», «… y la
  fecha», «Guardar la fecha…») y sin cambios queda en «Sin cambios que guardar», desactivado. Lo escrito sobrevive al
  repintado. Prueba: `test_el_avance_se_cambia_con_botones_rapidos_y_el_boton_dice_que_guarda`.
- **Vuelta 7, mano de obra** (`ejMoResumenEl`): arriba, lo trabajado en gráfico (días-hombre contra los presupuestados,
  con la raya del avance y si va con más o menos días de los que el avance supone; cada persona con su barra, sus DH y
  su costo). El calendario (`#ejCalCaja`) se abre con «Anotar días trabajados» (`ej.diasForm.abierto`; abierto de
  entrada si no hay nada anotado). Prueba: `test_la_mano_de_obra_se_ve_en_grafico_y_el_calendario_se_abre_al_anotar`.
- **Vuelta 8, facturas y compras en barras**: en las facturas, cuánto de lo facturado ya está asociado (`.ej-prog`:
  oscuro lo asociado, rayado lo que falta; reemplaza la línea final «N documentos sin asociar») y «Asociar» es un botón
  (`.ej-asociar`; «Cambiar» sigue discreto). En los gastos proyectados, las compras por estado (`.ej-embudo`: por
  decidir, aprobadas, compradas, con su monto y cuántas); tocar uno filtra la tabla. Prueba:
  `test_las_facturas_y_las_compras_se_resumen_en_barras`.
- **Vuelta 9, teléfono y oscuro**: revisados a 360 px (nada se sale) y en oscuro. En ≤ 640 px de vista, las cifras van
  más compactas (número de 20 px, su detalle en dos líneas, la quinta a todo el ancho) y el detalle de cada tarea de
  «Por hacer» en una línea, para que lo que hay que hacer quede cerca.
- **Vuelta 10, equipo de la semana** (`ejEquipoEl`): la semana en una tira (`.ej-semana`): cada día con las iniciales de
  quién va (lo tuyo en naranjo) y su vehículo, hoy marcado y los días sin nadie punteados; abajo, «Esta semana: …».
- **Vuelta 11, lo que espera al equipo** (`ejEspera`, `EJ_ESPERA`, `ejEsperaEl`, `#ejEspera`): sobre las tarjetas,
  cuántas compras por decidir, facturas sin asociar y pendientes hay en los proyectos a la vista y en cuántos; tocar uno
  deja solo esos proyectos (`ej.espera`, se combina con el estado del mapa). La tarjeta y «Por hacer» cuentan lo mismo.
  Prueba: `test_lo_que_espera_al_equipo_se_cuenta_y_filtra_la_lista`.
