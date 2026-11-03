# Portal — Recorrido de proyectos

Detalle de referencia: léelo solo al tocar esta parte. Las reglas generales están en `../CLAUDE.md`.

**Recorrido de proyectos** (2026-10-20, pedido del usuario: una herramienta
nueva que deje «muy claro» el flujo de trabajo, «clara, visual», afectada por
el usuario elegido y con una casilla para ver solo sus proyectos):
- **Qué es**: la vista `recorrido` (`tipo: vista`, `#vistaRecorrido`, arriba en
  el menú junto a Inicio, y en el Inicio bajo las herramientas). Un tablero con las
  seis etapas del Seguimiento del Formulador (`js/flujo.js`, mismos títulos:
  `test_el_recorrido_tiene_las_etapas_del_formulador`). Cada proyecto del equipo
  es una tarjeta en su etapa, con su N°, quién lo tiene, sus fechas, lo que
  sigue y un botón que abre la herramienta donde se hace. Cada columna nombra
  y abre la herramienta de su etapa.
- **De dónde lee**: de la carpeta de intercambio, con la conexión de la
  biblioteca guardada en este navegador (IndexedDB `qpn-intercambio`, la del
  Formulador). Lee `publicado/requerimientos`, `proyectos`,
  `analisis-financiero`, `licitaciones`, `estado`, `publicado/formulador/*.json`
  y los `borrador-cotizacion` del `buzon/`. **Lo único que escribe en la carpeta
  es el pedido de «Actualizar datos»**, y en la página no va ningún dato: se arma
  en el navegador de cada persona.
  Sin conexión, sin permiso o en un navegador que no abre carpetas, dice qué
  hacer y da el botón (`Conectar biblioteca` reutiliza `conectarBiblioteca`).
- **Una ficha de otro proyecto no se une** (2026-11-03): si el procesador pone su TAG en `fichaAjena` del N° (su
  carpeta del Centro de Costos es otra, `Sistema Intercambio/mismo_proyecto.py`), `rcArmar` no la une aunque lleve
  ese N°, y «Unirla con el N°» de Proyectos en ejecución no la propone (`ejSinFicha`): va como su propio proyecto.
  Caso: la ficha UMAG («UMAG Linea de H2») y el N° 280.
- **Las reglas** (`rcArmar`, `rcTarjetaReq`): entra lo vivo en la Planilla
  (Evaluación, Ofertado, Adjudicado), lo que tiene formulación (si la Planilla
  no lo cerró), lo que tiene ficha en el Análisis, los presupuestos sin N° y
  las fichas del Análisis sin N°. La etapa sale de lo más avanzado que haya:
  formulación «Cerrada» (Cierre, aunque el Análisis no tenga el 100 %: lo avisa;
  `rcCerrada`, desde el 2026-10-26); ficha en el Análisis (Ejecución, o Cierre con
  100 % de avance, que si sigue «Adjudicada» propone marcarla Cerrada); Adjudicado sin
  ficha (Ejecución: «Pasar a ejecución» o «Crear su ficha»); Ofertado,
  formulación Enviada o cotización emitida (Oferta, con el resultado de
  Mercado Público); borrador esperando en Sistema QUEMPIN, o formulación con
  precio y sin errores (Cotización); formulación en curso (Formulación); y si
  no, Requerimiento. **Con carpeta en la raíz de Gestión de Proyectos** (2026-11-03, `gestion` de `proyectos.json`) está
  en Ejecución aunque la Planilla no diga «Adjudicado» (lo avisa: falta marcarlo o la carpeta lleva el N° de otro) y no se
  pliega; una carpeta sin N° se une por el nombre con su proyecto o es una tarjeta sola que pide el N° (`rcTarjetaGestion`). Lo que lleva más de 60 días sin moverse va plegado al pie
  de su etapa; una oferta con más de 45 días sin respuesta pide confirmar el
  resultado. Los datos que no calzan entre herramientas (la Planilla dice
  «Ofertado» y ya hay ficha en el Análisis) salen como «datos por revisar».
- **Quién lo tiene**: las primeras iniciales del equipo entre el responsable
  de la formulación, el evaluador y el captador de la Planilla. Con usuario
  elegido, lo suyo va marcado en naranjo, la primera cifra es «Te esperan» y
  «Solo mis proyectos» (recordado en `quempin_portal_recorrido`) deja solo lo
  suyo; sin usuario, la casilla se desactiva y ofrece elegirlo.
- **Cifras y búsqueda**: las cuatro cifras de arriba (te esperan o requieren
  acción, cierran esta semana, esperan respuesta, en ejecución) filtran el
  tablero; el buscador filtra por N°, nombre, ciudad o TAG, y Ctrl K encuentra
  cada proyecto y abre su detalle (sus seis etapas, lo que sigue, sus datos y
  sus enlaces, incluidas sus carpetas por `quempin://carpeta`).
- **En el Inicio** (2026-10-20, pedido del usuario: una vista previa debajo de
  las herramientas, enfocada en el usuario elegido; si no tiene pendientes, un
  acceso directo): `#iniRc` muestra lo que le espera (la cifra «Te esperan»),
  lo urgente primero, en una fila de hasta cuatro tarjetas del tablero con su
  etapa (`rcTarjetaEl(t, true)`); con más, la última casilla es «+N más» y abre
  el recorrido filtrado. Sin pendientes, sin usuario o sin datos queda el
  acceso directo `#iniRecorrido`, que dice cómo va el equipo. Con poco alto
  (≤ 700 px) los títulos van en una línea y se esconde la línea de ayuda, para
  que el Inicio siga sin desplazarse.
- Se relee al volver a la pestaña si pasó más de un minuto, o con ↻. La
  vista previa con datos reales se arma fuera del repo (almacenamiento privado
  de un Chromium aislado), nunca con capturas dentro del repo.
- **Actualizar datos** (2026-11-02, pedido del usuario: ↻ no cambiaba «Datos del
  procesador hace X», porque solo relee la carpeta). El botón deja un `pedir-vuelta`
  en el `buzon/` (`rcPedirVuelta`) y la tarea del computador del procesador lo toma
  ([Sistema Intercambio/CLAUDE.md](../../../Sistema%20Intercambio/CLAUDE.md)). Mientras espera, el botón se
  desactiva y la línea dice «Actualización pedida hace X: tarda unos 5 min»; desde
  los 15 min, que el procesador aún no responde, con el punto en amarillo. Cada 10 s
  mira solo los nombres del buzón y `estado.json`, y relee todo cuando el pedido
  salió del buzón y el pulso cambió (`rcVueltaRevisar`, `rcVueltaHecha`): OneDrive
  trae esos dos cambios por separado. Lo pendiente sale del buzón, no del navegador:
  sigue al recargar y también se ve el pedido de un colega.
