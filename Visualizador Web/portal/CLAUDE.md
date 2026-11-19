# CLAUDE.md — Portal QUEMPIN

`index.html` + `portal.css` + `js/<vista>.js`, sin build ni datos, publicado en
<https://cristobal-monzo.github.io/finanzas-quempin/portal/>. Es la puerta única
del equipo (el hub redirige aquí; `?indice` muestra el índice antiguo). Una
ventana: menú ☰, buscador (Ctrl K) y pestañas con las
herramientas dentro (iframes del mismo sitio). Sin contraseña propia: cada
herramienta pide la del equipo, que el navegador recuerda.

## Cómo moverse por el archivo

Partido el 2026-11-18 (fase B de `docs/plans/2026-11-18-mejoras-portal.md`; antes, un archivo de 21 000 líneas):

- `index.html` (~1 200 líneas): cabecera, HTML de las vistas, `portal-registro`, `portal-conexiones`, el aviso de errores
  que escucha desde el principio, el freno del portal anidado y los `<script src="js/…">` **en orden**.
- `portal.css` (~3 300 líneas): todo el estilo.
- `js/`: un **script clásico por vista, sin función que lo envuelva** (`'use strict'` arriba). Lo de primer nivel
  es común a todos los archivos: se llaman entre sí sin importar nada, y desde una prueba se puede leer `estado`,
  `planif`, `ej`... Por eso **un nombre de primer nivel no se repite en dos archivos ni tapa uno del navegador**
  (`open`, `name`, `status`, `find`...): lo revisa `tests/portal/test_portal_archivos.py`. Lo que corre al cargar un
  archivo solo puede usar lo de archivos anteriores; lo que corre después (clics, temporizadores), lo de cualquiera.
  `base.js` va primero y `arranque.js` al final: ahí se engancha todo y se abre la herramienta pedida. Un archivo
  nuevo = un `<script>` en `index.html` (la prueba exige uno por archivo).
- Mapa de secciones de un archivo: `Grep "^(//|/\*) ---- "`; los grandes (`ejecucion.js` 5 000 líneas,
  `planificacion.js` 4 000) se leen con `offset`/`limit`.

| Vista (`id` en el registro) | Sección | Archivo | Funciones y estado | Detalle |
|---|---|---|---|---|
| Lo común: utilidades, estado, menú, pestañas y marcos, al día sin F5, usuario, diálogos | — | `base.js` | `ad*`, `estado` | [docs/interfaz.md](docs/interfaz.md) |
| Configuración y conexiones (`conexiones`) | `#vistaConexiones` | `conexiones.js` | `portal-conexiones` | [docs/interfaz.md](docs/interfaz.md) |
| Sin la carpeta (el teléfono): el resumen cifrado, solo para leer | `#mvFranja` | `resumen.js` | `mv*`, `mv`, `soloLectura()`, `mvNoSe()` | Abajo, «Datos» |
| Inicio, las herramientas por área | `#vistaInicio` | `inicio.js` | `ini*`, `ini` | [docs/interfaz.md](docs/interfaz.md) |
| Recorrido (`recorrido`) | `#vistaRecorrido` | `recorrido.js` | `rc*`, `rc` | [docs/recorrido.md](docs/recorrido.md) |
| Planificación semanal (`planificacion`) | `#vistaPlan` | `planificacion.js` | `pl*`, `planif` | [docs/planificacion.md](docs/planificacion.md) |
| Subir documentos (`subir-cc`) | `#vistaSubir` | `subir.js` | `sc*`, `sc` | Abajo y `Sistema Intercambio/documentos_cc.py` |
| Rendiciones (`rendiciones`): fotos de boletas → tabla → PDF y Centro de Costos | `#vistaRendir` | `rendiciones.js` | `rd*`, `rd` | [docs/rendiciones.md](docs/rendiciones.md) |
| Requerimientos, antes «Planilla de Ingreso» (`planilla`) | `#vistaPlanilla` | `planilla.js` | `pq*`, `pq` | [docs/planilla.md](docs/planilla.md) |
| Proyectos en ejecución (`ejecucion`) | `#vistaEjecucion` | `ejecucion.js` | `ej*`, `ej` | [docs/ejecucion.md](docs/ejecucion.md) |
| Llevar la cotización a un proyecto (diálogo, no está en el registro) | `#dlgLlevar` | `llevar.js` | `ll*`, `ll` | [docs/llevar-cotizacion.md](docs/llevar-cotizacion.md) |
| Buscador (Ctrl K) | `#buscar` | `buscador.js` | `resultados` | [docs/interfaz.md](docs/interfaz.md) |
| Clic derecho (menú del portal) y reportar errores y observaciones (`observaciones`); los errores de JavaScript se envían solos | `#menuCtx`, `#dlgObs`, `#vistaObservaciones` | `observaciones.js` | `ctx*`, `obs*`, `obs`, `er*`, `er` | [docs/observaciones.md](docs/observaciones.md) |
| Tema y lo que el Portal esconde de cada herramienta | `#btnTema` | `tema.js` | `ESTILO_INCRUSTADO` | [docs/interfaz.md](docs/interfaz.md) |
| Arranque y «Qué buscamos» de Oportunidades | — | `arranque.js` | `opGuardarAjustes` | [docs/interfaz.md](docs/interfaz.md) |

Cómo funciona la interfaz (menú, pestañas, registro, enlaces, usuario):
[docs/interfaz.md](docs/interfaz.md). Lee solo el documento de lo que vayas a
tocar. Una vista nueva lleva su documento ahí, no un bloque en este archivo.

## Reglas que no se pueden romper

- **Mismo sitio** (`cristobal-monzo.github.io`): el portal abre dentro al
  Formulador, los tableros y la Calculadora, ve adónde lleva cada enlace y
  comparte con ellos el `localStorage`. Usa claves propias
  (`quempin_portal_*`, `quempin_usuario`) y no borres las de otra herramienta.
  Proyectos del Formulador: lee `qpn.formulacion.proyectos.v1`, nunca escribe.
- **El registro** (`<script type="application/json" id="portal-registro">`) es
  lo único que define grupos, herramientas, `usuarios`, `personal` y `vehiculos`.
  Herramienta nueva = una entrada ahí; tablero nuevo = además en `publicar.py`.
  `tests/portal/test_portal_estructura.py` compara el registro con lo publicado, `usuarios` con el
  Formulador y con Sistema QUEMPIN (`app/config.py`, `USUARIOS`) y `vehiculos`
  con su esquema.
- **Las herramientas no se tocan para adaptarlas**: el portal marca el `<html>`
  de cada marco con `data-en-portal` y le agrega `ESTILO_INCRUSTADO`. Si cambias
  la cabecera de una herramienta, corre
  `test_lo_que_esconde_el_portal_existe_en_cada_herramienta`.
- **Sin barras de desplazamiento y sin desplazarse en el Inicio** en el computador (clase
  `sin-barra`; lo miden `test_el_inicio_y_el_menu_caben_sin_barras` y
  `test_las_herramientas_caben_en_el_inicio`). Excepción (pedido del usuario, 2026-11-19): la semana de la
  Planificación muestra todos los proyectos de cada día, sin «+N más»; si un día tiene muchos, el Inicio se desplaza.
- **Lo que no se abre dentro**: el Excel de respaldo de la Planilla (`url` del
  registro), Control de Documentos (aún sin enlace web) y QUEMPIN.exe (`quempin://`).
- **Datos**: en la página no va ningún dato; todo se arma en el navegador desde la
  carpeta de Intercambio, con la conexión guardada (IndexedDB `qpn-intercambio`,
  la del Formulador). Nunca crea un Intercambio nuevo. El Recorrido solo lee, salvo el
  pedido de «Actualizar datos» al procesador ([docs/recorrido.md](docs/recorrido.md)).
- **Sin la carpeta** (2026-11-18, fase C del plan; el usuario eligió la maqueta M3, el mismo Inicio, y pidió que las
  calculadoras queden): en el teléfono, Safari o Firefox (sin `showDirectoryPicker`), o en Chrome sin la carpeta
  conectada pero con la contraseña de los tableros recordada, `rcCargar` usa `mvAbrir()`: baja `datos/indice.json` y
  `datos/<parte>.json` (los sube la tarea del procesador con `Sistema Intercambio/resumen_movil.py`), los abre con
  `../candado.js` y la clave `quempin_viz_clave`, y arma una carpeta de mentira de solo lectura (`mvCarpeta`) que
  las vistas leen igual. Franja «Solo lectura · datos de las HH:MM» (ámbar con más de 2 h; sin clave, pide la
  contraseña). **Pedido del usuario (2026-11-18, después de verlo en el iPhone): lo que no se puede hacer ahí ni
  siquiera aparece; lo que sí funciona en el teléfono queda operativo.** Por eso, al agregar algo que cambia datos:
  - el control se habilita con `rcEscribe()` (carpeta y no solo lectura), **no con `rc.dir`**: deshabilitado,
    `html.solo-lectura` lo esconde (un menú que muestra un valor se ve como texto); un botón que se pone solo si se puede
    escribir, con `if (rcEscribe())`; lo que no tiene otra marca, en la lista de `html.solo-lectura` de `portal.css`;
  - la función que escribe empieza con `if (mvNoSe()) return;` (o `soloLectura()` si corre sola), por si algo se cuela;
  - un diálogo con los datos de algo se abre igual para mirarlo: `mvSoloVer(dlg)` antes de `showModal()`.
  Sin `showDirectoryPicker`, Subir, Rendiciones y lo de Sistema QUEMPIN no están en el Inicio, el menú ni el buscador
  (`iniApagada`), y `ESTILO_INCRUSTADO` esconde en las herramientas lo que guarda por la carpeta
  (`html[data-portal-solo-ver]`). Siguen operativos: el usuario, el tema, los filtros, las calculadoras y los tableros. Pruebas: `tests/portal/test_portal_movil.py`, también en Safari
  de iPhone emulado si está WebKit (`py -3.14 -m playwright install webkit`; el CI no lo instala y esa prueba se salta).
  Safari necesita iOS 16.4 o más nuevo (`DecompressionStream`); en uno más viejo se ve el aviso de siempre.
- **Escritura en la carpeta**: un archivo por navegador
  (`quempin_portal_dispositivo`), para que OneDrive nunca junte dos versiones; se
  une todo y en cada casilla manda el cambio más reciente (`t`), también si es
  borrar. Lo que no alcanza a guardarse espera en `quempin_portal_*_pendiente`.
  Formatos en `Sistema Intercambio/esquemas/`. Excepción: la Planilla de Ingreso
  escribe en el buzón, porque su dueño es el Excel ([docs/planilla.md](docs/planilla.md)).
- Las pruebas usan datos de mentira; las vistas previas con datos reales se arman
  en un Chromium aislado.

## Subir documentos (`sc*`)

Sube archivos asignados a un proyecto: escribe `buzon/adjuntos/<id>/<archivo>` y
después el mensaje `buzon/<ts>_portal_documento-cc_<id>.json`. El paso
`documentos-cc` del procesador los verifica (tamaño y sha256) y los copia a la
carpeta del proyecto en el Centro de Costos; nunca sobrescribe. Registrarlos sigue
siendo `/Registro_Centro_de_Costos`. Solo Chrome y Edge de escritorio
(`showDirectoryPicker`).

## Probar, publicar y revertir

- `py -3.14 -m pytest "Visualizador Web/tests/portal"` (~8 min): una prueba por vista
  (`test_portal_<vista>.py`), lo común (el sitio de mentira, ayudantes, `texto_portal()` = index + css + js juntos)
  en `portal_comun.py`. Una sola vista: `py -3.14 -m pytest "Visualizador Web/tests/portal/test_portal_planilla.py"`.
  Teléfono: `py -3.14 "Visualizador Web/auditoria_movil.py" portal`. En las pruebas, espera una condición
  (`wait_for_function`), no un tiempo fijo: con el CI lento, los tiempos fijos fallaban.
- **Publicar**: avisa a las otras sesiones, `py -3.14 "Visualizador Web/publicar.py" portal --subir` (espera el CI,
  copia `index.html`, `portal.css`, `js/` (borra los `.js` que ya no están) y lo de `marca/`, pone `?v=<huella>` en
  cada parte, no publica si algo enlazado falta, hace commit y push de `gh-pages` y verifica en línea). Sin datos, no
  pasa por el candado.
- **Revertir**: `git revert` del commit en `gh-pages`.
- Pendientes: los contadores de «Pendientes del equipo» leídos de la carpeta y un
  enlace web al Control de Documentos.
