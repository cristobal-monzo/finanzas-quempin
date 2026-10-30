# Portal — Planificación semanal

Detalle de referencia: léelo solo al tocar esta parte. Las reglas generales están en `../CLAUDE.md`.

**Planificación semanal** (2026-10-20, pedido del usuario: planificar cada semana
según el personal y los proyectos activos, «Lunes, ES en Llay Llay, LC en
Limache», como máximo 3 proyectos por persona en un día, una alarma si un
proyecto activo no se asigna en la semana actual, y verla por personal, por
proyecto y en general, con UX profesional):
- **Qué es**: la vista `planificacion` (`tipo: vista`, `#vistaPlan`, primera de
  Control y finanzas, así está en el Inicio). Tres vistas de la misma semana
  (`quempin_portal_plan` recuerda cuál y si se muestra el sábado): **General**
  (un tablero por día con cada proyecto y quiénes van, quiénes quedan sin
  proyecto y quiénes faltan; abajo, lo que cubre cada proyecto y la carga de cada
  persona), **Por personal** y **Por proyecto** (tablas de lunes a viernes; el
  sábado aparece si se pide o si ya tiene algo). Cada casilla se toca y abre una
  ventanita junto a ella (`#plPop`; en el teléfono sube desde abajo y las tablas
  muestran un día a la vez): proyectos o personas con casillas, otra actividad
  (oficina, visita técnica) y la ausencia (vacaciones, licencia, permiso), que
  quita a la persona de sus proyectos de esos días. Cada cambio se puede deshacer
  (el aviso o Ctrl Z). También: copiar la semana anterior (solo agrega).
- **Asignar rápido** (2026-10-23, pedido del usuario: «rápido de asignar e
  intuitivo»): arriba de la ventanita, la franja **«Qué días»** (`#plPopDias`,
  `planif.pop.dias`; al abrir, el día de la casilla) con los días, «Toda la
  semana», «Días libres» / «Días sin nadie» y «Solo <día>»: lo que se marca vale
  para todos los días elegidos en una sola tanda (`plAsignarDias`,
  `plAusentarDias`: un aviso y un «Deshacer»); se salta lo que no se puede
  (ausencia, 3 proyectos) y la ventanita lo dice. Con varios días, una casilla
  a medias (`indeterminate`) es un proyecto o una persona que va solo algunos:
  marcarla completa los que faltan. **«Cambiar»** (`planif.pop.cambiar`) pasa a
  la persona a otro proyecto (`plCambiarPor`) o pone a otra persona en su lugar
  (`plReemplazar`), en un paso; Escape sale de «Cambiar» antes de cerrar.
  Enter en el buscador elige la primera opción a la vista. En las tablas, las
  flechas van de casilla en casilla (`plTeclasTabla`) y lo recién cambiado se
  ilumina un momento (`planif.recien`). Tocar un proyecto de la alarma abre su
  ventanita, con «Sin trabajo esta semana» arriba y «Siguiente sin nadie» en el
  pie (`#plPopSiguiente`). En «Asignar» del tablero general van primero los
  proyectos sin nadie ese día, y desde el proyecto se vuelve a la lista. Las
  notas de la ventanita usan `.pl-pop-nota.tinte`: la clase `.aviso` es la del
  mensaje flotante de abajo.
- **Compartir e imprimir** (2026-10-23, pedido: «que la exportación sea clara en
  la asignación»): «Compartir» (`#dlgPlTexto`) arma el texto por persona, día por
  día con el lugar y con quién va, o por día como antes (`planif.texto`, en
  `quempin_portal_plan`). «Imprimir o PDF» abre `#dlgPlExportar`: la tabla de la
  semana (persona × día, A4 horizontal) y una hoja para cada persona elegida
  (A4 vertical, página con nombre `plVertical`: día, proyecto, lugar y con quién
  va); de entrada, quienes tienen algo esa semana. `plDocumento` lo arma en
  `#plDoc`, que solo se ve al imprimir (`body.pl-imprimiendo`); el título de la
  página es el nombre del PDF. Sale igual desde cualquier vista.
- **Vehículos** (2026-10-25, pedido del usuario: «a una persona en un proyecto
  se le pueda asignar uno de los dos vehículos de la empresa, Quempineta y RAM;
  la asignación debe ser sencilla y se debe poder ver en el resumen»): bloque
  `"vehiculos"` del registro (`id`, `nombre`, `articulo`; el `id` va en el
  archivo y el enum del esquema debe ser el mismo, `test_portal.py` los compara).
  En la ventanita, bajo cada persona (o proyecto) marcada, «Vehículo» con un
  botón por vehículo (`plVehOps`, `data-op="v|<persona o clave>|<id>"`): un toque
  lo asigna los días elegidos en que va (`plVehiculoDias`, una tanda), otro lo
  quita; a medias (`aria-pressed="mixed"`) si lo lleva solo algunos días. Se ve
  como etiqueta (`.pl-veh`) en las tres vistas, en la cifra «Vehículos en uso»
  del resumen (`.pl-kpi-veh`, lleva al panel) y en **«Vehículos en la semana»**
  (`#plVehiculos`, vista General: un día por fila, un vehículo por columna,
  «Libre» si nadie lo lleva). Un vehículo con personas que ese día no comparten
  proyecto está en dos lugares a la vez (`usoVeh` del modelo, en grupos): se
  avisa en naranjo (etiqueta, resumen, panel, el punto del botón y el aviso), sin
  impedirlo. Quitar una asignación le quita el vehículo; «Cambiar» y el reemplazo
  se lo llevan a la otra persona o proyecto; copiar la semana anterior lo copia;
  Compartir e Imprimir lo dicen (columna «Vehículo» en las hojas si alguien va en
  uno esa semana). En el archivo es `vehiculos` (una casilla por persona, proyecto
  y día, `vehiculo: ''` lo quita, manda el más reciente).
- **Guardar** (arreglo del 2026-10-25): `plGuardar` saca la semana de
  `porGuardar` antes de escribir, así un cambio hecho mientras se escribe (marcar
  a alguien y tocar su vehículo enseguida) vuelve a la lista y se guarda en la
  vuelta siguiente; antes quedaba fuera del archivo hasta el próximo cambio.
- **Revisión de usabilidad del 2026-10-29** (pedido del usuario: «un loop de 10 vueltas analizando la usabilidad y
  claridad de información y el UX/UI del planificador completo»), con capturas de los datos reales fuera del repo:
  - **Hoy y lo pasado**: cada día lleva `hoy` o `pasado` (`plDiaDe(...).pasado`, `plClaseDia`) en las tablas, el
    tablero, los días del teléfono y «Qué días». Lo pasado va apagado (sigue editable); hoy, en «Qué días» y en los días
    del teléfono, es un punto naranjo y no un borde, que se confundía con el día elegido.
  - **Casillas vacías**: con mouse (`@media (hover: hover)`), solo un «+» tenue; «Asignar» aparece al pasar encima o
    con el teclado. Con el dedo, entero como antes.
  - **Por proyecto con grupos**: «Sin nadie asignado esta semana», «Con alguien asignado» y «Sin trabajo esta semana»,
    cada uno con su cuenta (`tr.pl-sep`, `.pl-sep-n`; solo si hay más de un grupo). `.pl-pausar` es un botón, no un
    enlace rojo subrayado.
  - **Una cifra para el equipo**: «22 de 45 jornadas con proyecto» (cada persona cada día es una jornada; libres y
    ausencias en su detalle) reemplaza «días asignados» y «días libres», que se leían como días del calendario.
  - **Teléfono**: General muestra un día a la vez, como las tablas (`.pl-tablero[data-foco]`, `#plDiasMovil` también
    en General); el panel para asignar tocando va plegado en una línea («Asignar tocando», `planif.arrAbierto`,
    `.pl-arr.abierto`; con algo elegido queda abierto y «Ocultar» lo suelta); «Agregar» con su nombre y sin «Esta
    semana» deshabilitado.
  - **Vehículos**: en la ventanita, uno que ese día va a otra parte dice quién lo lleva (`.pl-veh-op-q`, «la lleva
    EV»; antes, un punto naranjo); en las etiquetas, quién lo lleva va separado («RAM │ EV»).
  - **Semana vacía** (esta o una que viene, sin asignaciones ni ausencias): `#plSemanaVacia` ofrece «Copiar la semana
    N» a la vista (`plPintarVacia` → `plCopiarAnterior`), que antes estaba solo en «Más».
  - Compartir por persona: quien no tiene nada en la semana va en una línea («Sin proyectos esta semana»).
  - Pruebas: desde `test_diez_vueltas_dias_grupos_jornadas_y_compartir`.
- **El personal** es el bloque `"personal"` del registro (NB, ES, LC, CM, MP,
  SV, EV y, desde el 2026-10-26, RL): incluye a todos los `"usuarios"` y puede
  tener más (EV y RL se planifican pero no eligen usuario en las herramientas).
  El usuario elegido va en naranjo.
- **Agregar a mano** (2026-10-26, pedido del usuario: «agregar una persona
  escribiendo su nombre para asignarla a los proyectos» y «agregar proyectos
  escribiéndolos en el planificador»): «Agregar» arriba (`#plAgregar`, abre
  `#dlgPlAgregar` en Persona o Proyecto según la vista), los botones del pie de
  «Por personal» y «Por proyecto» (`.pl-agregar-pie`), «Otra persona» en la
  ventanita de un proyecto (`data-op="persona-nueva"`: la agrega y la asigna esos
  días) y «Proyecto que no está en la lista» en la de una persona y en «Asignar»
  del tablero (`data-op="proyecto-nuevo"`). Una persona escrita es `x-<nombre>`
  (`PL_PER_MANO`; se ve con su nombre, «Juan P.» en las etiquetas, iniciales en un
  círculo punteado; `plNom`, `plNomCorto`, `plIniciales`) y entra en las filas de
  la semana (`m.personas`: el equipo, las de la lista y las que tienen algo esa
  semana aunque ya no estén). Un proyecto escrito es `pro:<nombre>`, o
  `req:<N°>` si se escribió con su N° de la Planilla adelante («281. H2 Green»:
  sirve para uno que el Recorrido plegó por antiguo y, cuando entre en ejecución,
  es el mismo); cuenta como proyecto activo (`plActivos`, `mano: true`), también
  en la alarma. Son **temporales** (pedido del 2026-10-26: quien se agrega a
  mano no trabaja en la empresa fuera de esas tareas): cada uno vale solo para
  la semana a la vista cuando se agregó (`semana`, clave `semana|id` en la
  lista, `plKLista`; `plManoActivas(s)`, `plProyManoActivos(s)`,
  `plActivos(s)`). No pasa a las semanas siguientes: «Copiar la semana
  anterior» lleva los que van en lo copiado (y su Deshacer los quita), y el
  diálogo «Agregar» ofrece los de semanas anteriores («Sumar a esta», hasta 6,
  el más reciente primero). Uno guardado antes del cambio, sin `semana`, es de la
  semana de su `t`. Van en la lista
  `publicado/planificacion/lista/<dispositivo>.json` (esquema
  `planificacion-lista`; `plLista`, `plLeerLista`, `plEscribirLista`, misma unión
  por navegador y el más reciente manda). Quitar (en el diálogo) es `activa:
  false` en esa semana: lo ya asignado se sigue viendo con su nombre, porque el
  archivo de la semana guarda el de cada persona escrita (`personas`) como el de
  los proyectos. Agregar y quitar se deshacen (aviso o Ctrl Z, `u.listas` en
  `plDeshacer`).
- **Proyectos activos**: los que el Recorrido pone en Ejecución (`rcArmar`, sin
  los de más de 60 días), con la clave `req:<N°>` o `tag:<TAG>`. Un proyecto
  cerrado (formulación «Cerrada» o 100 % de avance) sale, también si se agregó a
  mano con su N° (`test_un_proyecto_cerrado_sale_de_la_planificacion`); una asignación
  hecha con el TAG sigue siendo del mismo proyecto cuando este recibe su N°.
  El nombre de cada uno queda en el archivo, así una semana pasada se sigue
  leyendo cuando el proyecto terminó.
- **Estado de los proyectos y «Dar por cerrado»** (2026-10-26, pedido del
  usuario: un proyecto terminado y entregado que no pasó por el Formulador, solo
  «Adjudicado» en la Planilla o con ficha en el Análisis sin el 100 %, no tenía
  cómo salir). Cada fila de «Por proyecto» lleva su avance o lo que le falta
  (`plEstadoDe`, `.pl-avance`, el detalle en el `title`). El botón «Estado de los
  proyectos» (arriba y al pie de «Por proyecto», `#dlgPlProyectos`,
  `plPintarProyectos`) lista los activos con de dónde sale cada uno (`plFuentes`)
  y «Dar por cerrado», con una nota y, si tiene ficha en el Análisis sin el 100 %,
  la casilla para pedir ahí el 100 % de avance (un `datos-proyecto` al buzón con
  `origen.herramienta` `portal` y `reemplaza` el avance que se vio, como «Ingresar
  avance»). También «Dar por cerrado» / «Reabrir» en la ficha del Recorrido
  (`rcVerDetalle`). El cierre se guarda para todas las claves del proyecto (`req:`
  y `tag:`) en `publicado/planificacion/cierres/<dispositivo>.json` (esquema
  `planificacion-cierres`; `plCierres`, `plLeerCierres`, que lee `rcLeer`,
  `plEscribirCierres`; misma unión por navegador, el más reciente manda;
  reabrir es `cerrado: false`). `rcArmar` pasa a «Cierre» la tarjeta en ejecución
  que tenga uno vigente (`rcCerradoEnPlan`, `t.cierrePlan`), así sale de la
  planificación en todas las semanas, para todo el equipo. Se deshace (aviso del
  diálogo, aviso de abajo o Ctrl Z, `u.cierres` en `plDeshacer` →
  `plDeshacerCierre`), y si el pedido del 100 % sigue en el buzón, se borra.
  Pruebas desde `test_el_estado_de_los_proyectos_y_dar_por_cerrado_uno_sin_formulador`.
- **Máximo 3** (`PL_MAX`): con 3, la persona sale deshabilitada en las ventanitas
  («Completo»). Si dos computadores se pasan a la vez, la casilla queda en rojo
  («4 de 3: quita 1»).
- **La alarma**: un proyecto activo sin nadie ningún día de la semana de hoy,
  salvo que se marque «Sin trabajo esta semana» (una pausa de esa semana, que
  también se quita al asignarle a alguien). Se ve en el menú y en el Inicio (número
  y línea en rojo; desde el 2026-10-28 ya no en la cabecera), y en la vista, la cifra
  «sin asignar» del resumen despliega la lista. Para eso el
  portal lee la carpeta al abrirse aunque no abra en el Inicio, sin pedir permisos.
- **Dónde se guarda**: en la carpeta de intercambio, en
  `publicado/planificacion/<AAAA-Www>/<dispositivo>.json` (esquema
  `planificacion-semana` del catálogo; lo agregado a mano, en
  `publicado/planificacion/lista/`, esquema `planificacion-lista`; lo dado por
  cerrado, en `publicado/planificacion/cierres/`, esquema `planificacion-cierres`). Cada navegador escribe solo su archivo
  (`quempin_portal_dispositivo`), así OneDrive nunca junta dos versiones del
  mismo; la semana es la unión de todos y en cada casilla manda el cambio más
  reciente (`t`), también si es quitar, con un reloj que nunca queda detrás de
  lo ya visto. Lo que no alcanza a guardarse espera en `quempin_portal_plan_pendiente`
  y se reintenta. La vista relee cada 30 segundos (solo los archivos que
  cambiaron). Es la primera vista del portal que escribe en la carpeta.
- Pruebas: `test_portal.py`, desde `test_la_planificacion_semanal_en_el_registro`
  (alarma, máximo, guardado y esquema, unión de dos computadores, ausencias,
  deshacer, semanas y cambio de año, copiar, compartir, imprimir, teléfono; y
  desde el 2026-10-23 varios días, «Cambiar», teclado, alarma → ventanita y
  «Asignar» del tablero general; desde el 2026-10-25 los vehículos, desde
  `test_los_vehiculos_en_el_registro_y_en_el_esquema`, y el cambio que llega
  mientras se guarda).

**Vista más simple y arrastre** (2026-10-28, pedido del usuario: mostraba demasiado a la vez, que «Por personal» permita
arrastrar proyectos a persona + día, como una opción más, y quitar la alerta de la cabecera):
- Sin alarma en la cabecera: el número queda en el Inicio y en el menú.
- Resumen en una línea de pastillas; «N sin asignar» despliega `#plAlarma`. Un choque de vehículo se sigue diciendo con
  todas sus letras en su pastilla.
- «Más» reúne copiar, compartir, imprimir, estado y sábado. Los paneles de General son `<details>` plegados
  (`prefs.paneles` recuerda cuáles). Sin la columna «Semana»: la línea de la persona dice «3 de 5 días · 2 proyectos».
- Panel de arrastre (`.pl-arr`): proyectos en Por personal, personas en Por proyecto. Las etiquetas se arrastran entre
  casillas para mover (Ctrl copia), en un solo paso de deshacer. También se puede elegir en el panel y tocar casillas.
- Bajo 900 px el panel va sobre la tabla y se acomoda en varias filas: nada se desliza de lado (las pruebas lo exigen).
