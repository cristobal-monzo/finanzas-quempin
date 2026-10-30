# Portal — interfaz, registro y enlaces

Detalle de referencia: léelo solo al tocar esta parte. Las reglas generales están en `../CLAUDE.md`.

**Cambios del 2026-10-16** (pedido del usuario):
- **Cuatro grupos y la ayuda**: Formulación de proyectos, Control y
  finanzas, Cotizar y comprar, Calculadora (al final, antes de Ayuda).
  `test_los_grupos_del_pedido_del_2026_10_16` fija el orden.
- **Inicio minimalista**: todas las herramientas en cuatro columnas, una por
  grupo, con su línea `breve`; lo que se abre fuera (Excel, QUEMPIN.exe)
  lleva ↗. Cabe sin desplazarse desde 1024×640: con menos ancho van dos
  columnas y, si falta alto, se esconden las líneas breves (container
  queries sobre `.vista-inicio`). Se quitaron Mi día, atajos, las fichas de
  calculadora y los proyectos recientes.
- **Sin barras de desplazamiento** en el portal (clase `sin-barra`): el menú
  despliega un solo grupo a la vez (`quempin_portal_menu.abierto`; al
  cambiar de herramienta se abre su grupo) y las pestañas se encogen como
  las de un navegador, con su nombre `corto` (el completo va en el title) y
  la ✕ encima del nombre. Si una pantalla muy baja no alcanza, se desplaza
  con la rueda, sin barra. Las herramientas abiertas dentro conservan la
  suya. `test_el_inicio_y_el_menu_caben_sin_barras` mide 4 tamaños.
- **Cotizar y comprar abre QUEMPIN.exe** con `quempin://cotizacion`,
  `quempin://orden-compra` y `quempin://clientes` (campo `enlace`): el
  programa 1.3.8 se anota en Windows al abrirse y abre esa sección, o trae al
  frente la ventana abierta (Sistema QUEMPIN `app/protocolo.py`, CLAUDE.md
  §11). El portal muestra «Abriendo Sistema QUEMPIN… ¿No se abrió?», que
  explica cómo dejarlo listo en ese computador.
- **Segunda vuelta del 2026-10-16** (pedido: que no se repitan los logos ni los
nombres de QUEMPIN en cada herramienta, que no se abran demasiadas pestañas y
mejor navegación):
- **Herramientas sin su cabecera dentro del portal**: el portal marca el
  `<html>` de cada marco con `data-en-portal="tablero|calculadora|formulador|gantt"`
  (campo `incrustar` del registro) y le agrega `ESTILO_INCRUSTADO`. Tableros,
  calculadoras y la Carta Gantt pierden su `.viz-header` (logo, título, país,
  tableros, modo oscuro); el Formulador conserva su barra de secciones y Configuración, en
  una barra clara. Se aplica apenas existe cada página (un vigilante cada
  100 ms), sin tocar las herramientas: abiertas aparte se ven como siempre.
  `test_lo_que_esconde_el_portal_existe_en_cada_herramienta` revisa los
  selectores contra los templates, la Calculadora y el Formulador.
- **Lo que traía esa cabecera**: la fecha de los datos (`#vizGenerated`) va
  junto a las pestañas; el país, en un selector ahí mismo que solo aparece en
  los tableros con versión Perú; el modo claro/oscuro es uno solo (☾ en la
  cabecera), que fija también la clave de tema de cada herramienta (campo
  `tema`: `cc_viz_theme`, `quempin_h2_theme`, `quempin_fp_theme`…).
- **Una pestaña por herramienta**: las cuatro calculadoras son la familia
  `calculadora` (páginas hermanas con su propia ruta: elegir otra navega la
  misma pestaña). Con el Formulador (Gantt, Seguimiento) y el Análisis
  (Ingresar avance) quedan 8 pestañas como máximo.
- Pestañas con el ícono de su grupo e Inicio como casita; en el Inicio, un
  punto naranjo marca las herramientas que ya tienen pestaña.
- **Tercera vuelta del 2026-10-16** (pedido: quitar la franja de íconos, que el
menú aparezca solo con ☰; sacar «Índice anterior» de la Ayuda y agregar una
sección de configuración con todo lo que hay que conectar, bien referenciado):
- **Sin franja**: el menú con nombres se despliega encima de la herramienta
  solo con ☰ (clase `menu-abierto`, igual en el computador y el teléfono) y
  se cierra al elegir, con Esc o tocando fuera. La herramienta usa todo el
  ancho. `test_el_menu_solo_aparece_con_la_hamburguesa`.
- **Sin «Índice anterior»**: un enlace al índice viejo (`/finanzas-quempin/`)
  desde una herramienta lleva al Inicio del portal (`RUTA_INDICE`).
- **Configuración y conexiones** (Ayuda; herramienta `tipo: vista`, una
  pestaña sin marco con la sección `#vistaConexiones`): lo arma el bloque
  `<script type="application/json" id="portal-conexiones">`, una tarjeta por
  carpeta, programa o acceso con su ruta, su enlace a SharePoint, cómo dejarlo
  listo, quién lo usa y qué pasa si falta, más el computador del procesador y
  sus tres tareas. Arriba, «Preparar este computador» (2026-10-19): un paso por
  cosa que se conecta, en orden, con su estado y su botón (solo el primero
  pendiente va destacado) y «n de 6 pasos listos». Revisa solo si conecta
  carpetas, la biblioteca (IndexedDB `qpn-intercambio`, compartida con el
  Formulador por ser el mismo sitio), el pulso del procesador
  (`publicado/estado.json`, leído con el `js/pulso.js` del Formulador), la
  contraseña y el usuario. «Conectar biblioteca» la conecta aquí mismo y la guarda
  con las mismas claves que `js/intercambio.js` (nunca crea un Intercambio nuevo).
  OneDrive y QUEMPIN.exe no se pueden ver desde el navegador: se marcan a mano
  (`quempin_portal_conexiones`, solo en ese navegador). Las rutas se comprobaron en el disco y en
  SharePoint el 2026-10-16; `test_las_rutas_de_conexiones_son_las_del_intercambio`
  las compara con `Sistema Intercambio/ubicacion.py`. Si cambia una carpeta,
  una tarea o lo que necesita una herramienta, se corrige ese bloque.

**El registro** (`<script type="application/json" id="portal-registro">`):
grupos y herramientas. Cada herramienta lleva:
- `tipo`: marco, excel, programa, archivo, ayuda, inicio o vista (una sección
  propia del portal, en su pestaña: `vista` es su id).
- `ruta` y `peru`.
- `requiereProyecto`: sin proyecto elegido, abre el selector en vez de la
  herramienta. Lo lleva Seguimiento desde el 2026-10-25: sin proyecto era la
  misma lista del Formulador con otro nombre.
- `familia` y `alias`: la misma página va en una sola pestaña. El
  Formulador incluye Seguimiento; el Análisis incluye Ingresar datos. Una
  dirección `…/portal/#/<herramienta>` abre esa y no su pareja aunque la
  pestaña de la visita anterior mostrara la otra (2026-10-25: `#/ingresar`
  dejaba el Resumen). La
  Carta Gantt dejó de ser parte del Formulador el 2026-10-20 (pedido del
  usuario: «una herramienta aparte, no una extensión del formulador»): es su
  propia página, `/formulacion-proyectos-quempin/gantt/` (en el repositorio
  del Formulador, carpeta `gantt/`), con su pestaña, su tema
  (`quempin_gantt_theme`) y sus datos (`publicado/gantt/` en la carpeta de
  intercambio). Con un proyecto elegido abre `#/proyecto/<uid>`; sin él, su
  lista de cartas.
- `proyecto`: cómo se abre con el proyecto elegido.
- `pestanas` de cada calculadora (los `data-tab` de `Calculadora
  Técnica/assets/gases.js`).

Una herramienta nueva es una entrada ahí. Un tablero nuevo va además en
`publicar.py`: `test_portal.py` exige que los dos tengan los mismos.
- **Enlaces entre herramientas**: el portal engancha cada marco del mismo sitio.
- Un clic o un `window.open` hacia otra herramienta abre la pestaña de esa
  herramienta en el portal, no una ventana nueva. Esto vale también para los
  enlaces absolutos de los tableros.
- Dentro de la misma herramienta se navega normal.
- `window.open('')` (los reportes PDF del Análisis) no se toca.
- Si una herramienta se va a otra por su cuenta (el selector de
  calculadora), la pestaña la sigue.
- **Proyecto elegido**: lee, nunca escribe, `qpn.formulacion.proyectos.v1` del
Formulador, con la última versión de cada código. Se abre así:

| Herramienta | Dirección |
|---|---|
| Formulador | `#/req/<N°>`, o `#/tag/` o `#/p/<uid>/ficha` |
| Carta Gantt | `#/p/<uid>/gantt` |
| Seguimiento | `#/p/<uid>/seguimiento` |
| Centro de Costos (Chile) | `#tag=` |
| Análisis Financiero | `#proyecto=` |

Si el proyecto cambia, las pestañas abiertas se van a él.
- **Lo que no se abre dentro**:
- Planilla de Ingreso: Excel para la web en una pestaña nueva, con el campo
  `url` de su entrada en el registro.
- Control de Documentos: el portal dice dónde está, porque aún no tiene
  enlace web.
- QUEMPIN.exe (cotización, OC, clientes): se abre por `quempin://`, fuera
  del navegador.
- **En el navegador**: guarda `quempin_portal_pestanas` (vuelven sin cargar,
solo la activa), `quempin_portal_proyecto`, `quempin_portal_menu` y
`quempin_portal_pais`. El tema usa `quempin_hub_theme`, el del índice. Cuando
una herramienta guarda la contraseña, las que esperaban con el candado se
recargan solas. Se mantienen 8 herramientas cargadas como máximo.

**Usuario** (2026-10-16, pedido del usuario: «un selector de usuario» con
NB, ES, LC, CM, MP, SV): botón `#btnUsuario` junto a Proyecto. Guarda las
iniciales **tal cual, sin JSON**, en `quempin_usuario`, la misma clave del
Formulador (`js/usuario.js`), que las usa como responsable de lo que se crea,
autor en el Control de Documentos y «Mis proyectos»; cada uno se entera del
cambio del otro por el evento `storage`. El selector de proyectos muestra
primero «Tus proyectos» (el `responsable` del Formulador). Sin elección, adopta
las iniciales que el Formulador tenía antes (`qpn.formulacion.iniciales` o su
«Responsable por defecto»), solo leyéndolas. La lista va en el registro
(`"usuarios"`) y debe ser la misma del Formulador y de Sistema QUEMPIN
(`app/config.py`, `USUARIOS`): `test_portal.py` las compara. Dentro del portal
se oculta el botón de usuario del Formulador (`#usuarioBtn`). En el teléfono el
botón muestra solo las iniciales (o un ícono sin usuario) y su ventana va fija
a la pantalla; bajo 380 px la cabecera se junta un poco.
