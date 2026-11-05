# Portal — Planilla de Ingreso

Detalle de referencia: léelo solo al tocar esta parte. Las reglas generales están en `../CLAUDE.md`.

**Planilla de Ingreso** (2026-10-29, pedido del usuario: «que la planilla de proyectos sea replicada en el portal», que desde
ahora los proyectos se ingresen ahí y que el Excel quede de respaldo, «actualizándose mutuamente», solo con las columnas
que de verdad se usan).

- **Qué es**: la herramienta `planilla` (`tipo: vista`, `#vistaPlanilla`; antes `tipo: excel`), funciones `pq*`, estado `pq`,
  diálogo `#dlgPlanilla`. El registro conserva su `url`: es el botón «Excel de respaldo» y el de Configuración y conexiones.
- **El puente con el Excel** no está aquí: es `Sistema Intercambio/planilla_escritura.py`, cada 10 minutos. Su detalle, con la
  medición de cada columna, está en `Sistema Intercambio/docs/planilla.md`.
- **Lee** `publicado/requerimientos.json` y pone encima lo que espera en el buzón (`pqMezclar`, llamado desde `rcLeer`): por eso
  el Recorrido y las demás vistas también ven al instante lo ingresado.
  - `rc.datos.requerimientosExcel`: lo publicado, tal cual.
  - `rc.datos.requerimientos`: lo mezclado.
  - `rc.datos.planillaMeta`: un WeakMap por fila con lo que falta pasar al Excel, para no agregarles campos a filas que
    leen las demás vistas.
- **Escribe en el buzón**, no en un archivo por navegador como las demás vistas: el dueño del dato es el Excel y este tiene un
  solo escritor. Un requerimiento nuevo es `nuevo-requerimiento` (con `numeroLibre`); un cambio, `editar-requerimiento` con
  solo lo que cambió y lo que se veía (`reemplaza`).
  - Lo que cambió se compara contra el formulario recién abierto (`pq.inicial`), no contra el dato: una fecha antigua «-» se
    ve vacía y no debe contar como cambio. Por lo mismo, un Estado o Canal vacío o fuera de la lista se muestra tal cual.
  - El N° nuevo es el siguiente al mayor de la Planilla, lo que espera, las carpetas y las formulaciones (`pqSiguienteN`). Si
    dos personas lo toman a la vez, el Excel le da al segundo el siguiente libre y el resultado lo dice.
- **Las columnas** (`PQ_COLUMNAS`) son las mismas del esquema `editar-requerimiento` y de `planilla_escritura.EDITABLES`; lo
  revisa `test_las_columnas_de_la_planilla_son_las_del_esquema_y_del_excel`. Para agregar una, en los tres.
- **Se dice todo** en la franja `#pqSinc`:
  - lo que espera y desde cuándo (más de media hora: ¿está encendido el computador del procesador?);
  - lo que no quedó en el Excel esta semana (`rechazado`, `reemplazado`);
  - las filas del Excel que aquí no se ven: N° repetido o sin N°, de `datos.avisos` de la publicación;
  - lo último del portal con su resultado, con «Retirar» para lo que todavía espera.
- **El Recorrido** abre la fila de un N° con `RC_IR.planilla(n)` → `pqIrA(n)`.
- **Sin carpeta conectada** (un teléfono, otro computador) la vista dice qué falta y ofrece abrir el Excel, que era lo que
  hacía antes de ser una vista.
- **No se borran filas**: el N° es la clave de carpetas, formulaciones y fichas. Lo que no sigue queda «Descartado».
- Mientras se mira, relee la carpeta cada 2 minutos, nunca con el diálogo abierto. Con un contenedor de 1240 px o menos, cada
  fila es una tarjeta.
- **Pruebas**: desde `test_las_columnas_de_la_planilla_son_las_del_esquema_y_del_excel` en `test_portal.py` (datos de mentira,
  sobre `_intercambio_de_prueba`). El escritor tiene las suyas en `Sistema Intercambio/tests/test_planilla_escritura.py`.

## El estado y la carpeta de cada proyecto (2026-11-02)

Pedido del usuario: al crearse un proyecto en la Planilla, su carpeta en «Formulación de proyectos» con la estructura de siempre,
como carpeta principal del proyecto; cambiar el estado desde la Planilla, con **Post-venta** (entregado, se sigue atendiendo) y
**Cerrado** (adjudicado y terminado); que un cambio hecho en cualquier parte se vea en todo el portal, y un aviso antes de que la
carpeta se mueva. Funciones `est*` y `pqCarpetasDe`, `pqPlanCarpeta`, `pqNombreCarpeta`, `pqCrearCarpeta`; diálogo `#dlgEstado`.

- **El Estado vive en la Planilla.** Toda vista lo cambia con `estCambiar(n, nuevo)`: la Planilla (la etiqueta de cada fila es una
  lista, `estSelector`, y su diálogo), el detalle del Recorrido, «Proyectos en ejecución» y «Dar por cerrado» de la Planificación.
  Deja un `editar-requerimiento`, que `pqMezclar` muestra al instante en todas las vistas, y `rcArmar` le da precedencia sobre lo
  que dice la formulación (`x.estadoPedido`, `RC_FORM_DE`) hasta que el procesador se la lleve al Formulador.
- **El aviso** (`estPreguntar`): si el nuevo estado mueve la carpeta, dice de dónde a dónde (`estPasos`) antes de cambiar nada; al
  aceptar se deja también un `mover-carpeta`. Para Cerrado o Post-venta con ficha en el Análisis bajo el 100 %, ofrece pedirlo.
- **Adónde va** (`PQ_CARPETA`): la misma tabla de `Sistema Intercambio/carpetas_oferta.py` (`DESTINOS`) y del Formulador
  (`js/oferta.js`); `test_la_carpeta_de_cada_estado_es_la_misma_en_el_portal_el_procesador_y_el_formulador` compara las tres, el
  nombre y las subcarpetas (con `QUEMPIN_FORMULADOR_REPO` apunta a una rama de trabajo del Formulador). Dónde está ahora cada
  carpeta lo dice `proyectos.json` (`carpetas.oferta`, `carpetas.ejecucion`), más lo creado en este navegador (`pq.nuevas`).
- **Quién mueve**: el computador del procesador, en la vuelta de 10 minutos (`carpetas_oferta.py`). El navegador no puede mover
  carpetas, y QUEMPIN.exe (`quempin://trasladar`, que lo hacía antes) dependía del computador de quien lo pedía.
- **La carpeta nueva** se crea aquí al guardar el requerimiento (`pqCrearCarpeta`, en la raíz de la biblioteca, con
  `PQ_ESTRUCTURA`), si este navegador tiene la biblioteca completa; si no, la crea el procesador. Una fila sin carpeta tiene
  «Crear carpeta» en su diálogo. Lo que entra «Descartado» o «No adjudicado» no lleva carpeta.
- **Lo cambiado en el Excel** no mueve nada solo (ahí no hay cómo avisar antes): la franja `#pqSinc` lista las carpetas de
  proyectos en curso que no están donde dice su estado (`estFueraDeLugar`), cada una con «Mover», y el diálogo de cada fila lo dice.
- **Retirar** un cambio de estado retira también el pedido de mover su carpeta.
- **«Dar por cerrado»** de un proyecto con fila en la Planilla cambia su Estado a Cerrado y además deja la marca (quién, cuándo,
  nota). Una marca sola cierra un proyecto sin fila, o uno que la Planilla todavía tiene «Adjudicado» (con un aviso).
