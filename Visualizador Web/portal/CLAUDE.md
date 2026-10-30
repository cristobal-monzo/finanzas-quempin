# CLAUDE.md — Portal QUEMPIN

`index.html`: un solo archivo sin build ni datos, publicado en
<https://cristobal-monzo.github.io/finanzas-quempin/portal/>. Es la puerta única
del equipo (el hub redirige aquí; `?indice` muestra el índice antiguo). Una
ventana: menú ☰, buscador (Ctrl K), proyecto elegido una vez y pestañas con las
herramientas dentro (iframes del mismo sitio). Sin contraseña propia: cada
herramienta pide la del equipo, que el navegador recuerda.

## Cómo moverse por el archivo

**~12 000 líneas y 850 KB: nunca lo leas entero.** Mapa de secciones:
`Grep "^\s*(//|/\*) ---- "` en `index.html`; después `Read` con `offset`/`limit`.
Orden: CSS, HTML de las vistas, `portal-registro`, `portal-conexiones`, JS.

| Vista (`id` en el registro) | Sección | Funciones y estado | Detalle |
|---|---|---|---|
| Recorrido (`recorrido`) | `#vistaRecorrido` | `rc*`, `rc` | [docs/recorrido.md](docs/recorrido.md) |
| Planificación semanal (`planificacion`) | `#vistaPlan` | `pl*`, `planif` | [docs/planificacion.md](docs/planificacion.md) |
| Proyectos en ejecución (`ejecucion`) | `#vistaEjecucion` | `ej*`, `ej` | [docs/ejecucion.md](docs/ejecucion.md) |
| Subir documentos (`subir-cc`) | `#vistaSubir` | `sc*`, `sc` | Abajo y `Sistema Intercambio/documentos_cc.py` |
| Configuración y conexiones (`conexiones`) | `#vistaConexiones` | `portal-conexiones` | [docs/interfaz.md](docs/interfaz.md) |

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
  `test_portal.py` compara el registro con lo publicado, `usuarios` con el
  Formulador y con Sistema QUEMPIN (`app/config.py`, `USUARIOS`) y `vehiculos`
  con su esquema.
- **Las herramientas no se tocan para adaptarlas**: el portal marca el `<html>`
  de cada marco con `data-en-portal` y le agrega `ESTILO_INCRUSTADO`. Si cambias
  la cabecera de una herramienta, corre
  `test_lo_que_esconde_el_portal_existe_en_cada_herramienta`.
- **Sin barras de desplazamiento y sin desplazarse en el Inicio** (clase
  `sin-barra`; lo miden `test_el_inicio_y_el_menu_caben_sin_barras` y compañía).
- **Lo que no se abre dentro**: Planilla (Excel web, `url` del registro), Control
  de Documentos (aún sin enlace web) y QUEMPIN.exe (`quempin://`).
- **Datos**: en la página no va ningún dato; todo se arma en el navegador desde la
  carpeta de Intercambio, con la conexión guardada (IndexedDB `qpn-intercambio`,
  la del Formulador). Nunca crea un Intercambio nuevo. El Recorrido solo lee.
- **Escritura en la carpeta**: un archivo por navegador
  (`quempin_portal_dispositivo`), para que OneDrive nunca junte dos versiones; se
  une todo y en cada casilla manda el cambio más reciente (`t`), también si es
  borrar. Lo que no alcanza a guardarse espera en `quempin_portal_*_pendiente`.
  Formatos en `Sistema Intercambio/esquemas/`.
- **Sin datos reales en el repositorio**: las pruebas usan datos de mentira; las
  vistas previas con datos reales se arman fuera del repo, en un Chromium aislado.

## Subir documentos (`sc*`)

Sube archivos asignados a un proyecto: escribe `buzon/adjuntos/<id>/<archivo>` y
después el mensaje `buzon/<ts>_portal_documento-cc_<id>.json`. El paso
`documentos-cc` del procesador los verifica (tamaño y sha256) y los copia a la
carpeta del proyecto en el Centro de Costos; nunca sobrescribe. Registrarlos sigue
siendo `/Registro_Centro_de_Costos`. Solo Chrome y Edge de escritorio
(`showDirectoryPicker`).

## Probar, publicar y revertir

- `py -3.14 -m pytest "Visualizador Web/tests/test_portal.py"`: el registro, los
  enlaces que leen AF, CC, Formulador y Calculadora, y el portal en Chromium sobre
  un sitio de mentira. Teléfono: `py -3.14 "Visualizador Web/auditoria_movil.py" portal`.
- **Publicar**: avisa a las otras sesiones, copia `index.html` a
  `.worktrees/gh-pages/portal/index.html`, commit y push ahí. `publicar.py` no lo
  toca.
- **Revertir**: `git revert` del commit en `gh-pages`.
- Pendientes: los contadores de «Pendientes del equipo» leídos de la carpeta y un
  enlace web al Control de Documentos.
