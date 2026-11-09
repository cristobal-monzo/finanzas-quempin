# Portal — Requerimientos (antes «Planilla de Ingreso»)

Detalle de referencia: léelo solo al tocar esta parte. Las reglas generales están en `../CLAUDE.md`.

Se llama **Requerimientos** en el portal desde el 2026-11-06 (pedido del usuario); el Excel sigue siendo la Planilla de
Ingreso de Requerimientos. **Planilla de Ingreso** (2026-10-29, pedido del usuario: «que la planilla de proyectos sea replicada en el portal», que desde
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
- **«Cerrado» y su carpeta** (2026-11-09, pedido del usuario): «Cerrado» es un estado más (adjudicado y ya entregado). Al
  elegirlo en una fila que ya existe aparece `#pqMoverCampo` (`pqVerMover`): «Mover su carpeta a «0 Proyectos Entregados
  <año>»», con la carpeta de su N° en la raíz de Gestión (`pqCarpetaGestion`, de `rc.datos.gestion`). Marcada si recién se
  cierra; sin marcar si la fila ya estaba «Cerrado»; deshabilitada si no hay una sola carpeta con ese N°. Al guardar deja,
  además del `editar-requerimiento`, un `mover-carpeta` (`pqEnviarMover`) y un `pedir-vuelta` (`rcPedirVuelta`): la mueve el
  procesador (`Sistema Intercambio/cierre_entregados.py`). Al revés también: una carpeta movida a mano a los entregados pasa
  la fila a «Cerrado» en la vuelta siguiente del procesador.
- **El Recorrido** abre la fila de un N° con `RC_IR.planilla(n)` → `pqIrA(n)`. Un «Cerrado» va a su «Cierre»
  (`rcCerradoPlanilla`); para los avisos de «corresponde Adjudicado» cuenta como ganado (`RC_GANADOS`).
- **Sin carpeta conectada** (un teléfono, otro computador) la vista dice qué falta y ofrece abrir el Excel, que era lo que
  hacía antes de ser una vista.
- **No se borran filas**: el N° es la clave de carpetas, formulaciones y fichas. Lo que no sigue queda «Descartado».
- Mientras se mira, relee la carpeta cada 2 minutos, nunca con el diálogo abierto. Con un contenedor de 1240 px o menos, cada
  fila es una tarjeta.
- **Pruebas**: desde `test_las_columnas_de_la_planilla_son_las_del_esquema_y_del_excel` en `test_portal.py` (datos de mentira,
  sobre `_intercambio_de_prueba`). El escritor tiene las suyas en `Sistema Intercambio/tests/test_planilla_escritura.py`.
