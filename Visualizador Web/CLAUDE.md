# CLAUDE.md — Visualizador Web (maestro)

Este documento aplica a **los visualizadores web de todos los módulos** de
`Finanzas QUEMPIN` (Centro de Costos, Cotizador Historico, Flujo de Caja, y
cualquier módulo futuro). Cada módulo tiene su propia carpeta
`<Módulo>/Visualizador Web/` con un `CLAUDE.md` de contenido que enlaza aquí
— este archivo no se auto-carga en esas subcarpetas (no son ancestro/
descendiente en el árbol), así que léelo explícitamente antes de tocar
cualquier visualizador.

Ver el spec de diseño original en
[`docs/specs/2026-07-19-visualizador-web-design.md`](../docs/specs/2026-07-19-visualizador-web-design.md).

## Rol

Al trabajar en cualquier `Visualizador Web/` de un módulo, actúa como
desarrollador experto en HTML/UI/UX: maquetación responsiva (mobile-first),
accesibilidad básica (contraste suficiente, foco de teclado visible, texto
alternativo en imágenes), y HTML/CSS/JS simple sin frameworks pesados salvo
que el propio módulo lo justifique explícitamente en su `CLAUDE.md` de
contenido.

## Manual de marca

Fuente de verdad única para colores, tipografía y logo:
`Material gráfico QUEMPIN/OFICIAL MANUAL DE MARCA GRÁFICA QUEMPIN.pdf`, más
`Material gráfico QUEMPIN/LOGO QUEMPIN.PNG` y el resto de esa carpeta
(fotografías, piezas gráficas de referencia). Nunca inventar paleta,
tipografía o variante de logo. Si el manual no cubre un caso puntual de UI
(ej. color de un estado de error en una tabla), extrapolar de forma
conservadora a partir de la paleta oficial y anotar la decisión en el
`CLAUDE.md` de contenido del módulo correspondiente.

## Mandato de herramientas dinámicas

Todo visualizador debe incluir, como mínimo:

- Al menos **un gráfico interactivo** (tooltip/hover al pasar el mouse — no
  una imagen estática exportada).
- Al menos **una tabla dinámica**: ordenable por columna, con búsqueda y
  filtro.
- **Un buscador de texto libre.**
- **Filtros** por las dimensiones relevantes de ese módulo específico
  (definidas en el `CLAUDE.md` de contenido de cada módulo).
- Un **"consultor IA"** que responda preguntas en lenguaje natural sobre los
  datos del módulo es **deseable pero opcional por módulo** — requiere un
  backend o una llamada a una API con key (no es 100% estático como el
  resto del sitio), así que cada módulo decide si lo implementa y cómo,
  cuando le toque su propio ciclo de diseño.

## Teléfono — obligatorio, y se verifica emulando uno (2026-09-24)

Pedido del usuario: todos los tableros tienen que poder revisarse en el
teléfono. Hasta esta fecha, Centro de Costos y Cotizador (Chile y Perú) y el
hub no declaraban `<meta name="viewport">`: el teléfono los dibujaba a ~980 px
y los achicaba, así que **el diseño móvil que Centro de Costos y Cotizador ya
tenían escrito nunca se activó en un teléfono real**. Tampoco declaraban
DOCTYPE (corrían en modo quirks). Análisis Financiero sí tenía viewport, pero
deslizaba de lado tablas de 9 columnas, con el detalle del proyecto cortado.
Nada de eso se ve en un escritorio, ni achicando la ventana del navegador.

Lo que tiene que cumplir cualquier tablero (actual o futuro):

- **Cabecera**: `<!DOCTYPE html>`, `<meta charset="utf-8">` y
  `<meta name="viewport" content="width=device-width, initial-scale=1">`, sin
  bloquear el zoom. Lo exige `Visualizador Web/tests/test_tableros_movil.py`
  para toda plantilla `*/Visualizador Web/template.html`, incluida la de un
  módulo nuevo.
- **Corte en 640 px** (`@media (max-width: 640px)`), con el mismo lenguaje en
  todos: navegación entre tableros en una sola fila (selector de país fijo +
  las 3 pestañas con etiqueta corta, que se deslizan centrando la activa si
  no caben); el botón de tema junto al logo; KPIs en 2 columnas.
- **Tablas → tarjetas**, no scroll horizontal: primera celda como título y el
  resto en pares etiqueta/valor. Análisis Financiero toma las etiquetas del
  `<thead>` (`etiquetarCeldas()`, un solo `MutationObserver` para las 4
  tablas); si la tabla se ordena por columna, sus encabezados quedan como una
  tira "Ordenar". **Selectores siempre con `>`** (`table.viz-table > tbody`,
  `tr.detail-row > td`): el detalle expandido lleva tablas anidadas, y con
  selectores de descendiente la tabla de ítems de Centro de Costos perdía su
  encabezado y ponía cada celda en su propia fila. Solo una matriz (mapa de
  calor) o una subtabla dentro de un detalle se desliza de lado, con la
  primera columna fija.
- **Campos a 16 px en móvil**: con menos, Safari de iPhone hace zoom al tocar
  el buscador o un filtro y descuadra la página.

Cómo verificarlo, con los `build/index.html` ya regenerados:

```
py -3.14 "Visualizador Web/auditoria_movil.py"            # 8 tableros, el hub y el portal × 360/390/768 px
py -3.14 "Visualizador Web/auditoria_movil.py" cc --capturas <carpeta fuera del repo>
```

Emula un teléfono de verdad (`isMobile` de Chromium, que es lo que respeta el
viewport), pasa la contraseña, recorre pestañas y una interacción típica
(expandir un documento, buscar, abrir filtros), y termina con código 1 si algo
se sale de la pantalla o si queda un campo bajo 16 px. **Córrelo después de
tocar cualquier plantilla**: la auditoría encontró campos de cantidad a 14 px
que solo aparecen tras una búsqueda, algo que no se ve mirando la pantalla
inicial. Las capturas muestran datos reales: nunca dentro del repo.

## Datos — export estático saneado (obligatorio)

El HTML publicado **nunca** lee directamente el `.xlsx`/JSON fuente de un
módulo (ej. `Centro de Costos/Excel/Centro de Costos.xlsx`). Cada módulo
define su propio paso de export (script o función) que genera un snapshot
JSON agregado/saneado hacia `<Módulo>/Visualizador Web/data/`; el HTML solo
lee ese snapshot, nunca el archivo fuente. "Saneado" (qué columnas/
agregaciones se exponen) se define en el `CLAUDE.md` de contenido de cada
módulo, no aquí.

La carpeta `<Módulo>/Visualizador Web/data/` se agrega a `.gitignore` en
cada módulo cuando se cree (el código que genera el export sí se
versiona) — ver regla ya agregada en el `.gitignore` raíz.

## Índice (hub) de los tableros

**Desde el 2026-10-19 la dirección del hub abre el Portal** (`portal/`, un script al
inicio del `<head>`; decisión del usuario: una sola puerta). Dentro de un marco o con
`?indice` se ve el índice de siempre.

`Visualizador Web/index.html` (raíz, junto a este `CLAUDE.md`) es una
página estática que **no muestra datos** — una tarjeta por tablero
publicado (4 desde que se agregó Centro de Costos Perú, 2026-08-25),
cada una con un botón que abre en pestaña nueva el tablero de ese
módulo/país. Reutiliza el mismo sistema de marca que los visualizadores
(paleta oficial, Lato embebida, cabecera negra con filete naranjo, toggle
de tema). No hay `build_visualizador.py` para este archivo porque no lee
ningún Excel/JSON: se edita a mano y se vuelve a copiar a
`.worktrees/gh-pages/index.html` para republicar.

- **Sin gate de contraseña** (decisión explícita del usuario, 2026-07-29,
  sigue vigente): el hub no expone información financiera, cada tarjeta
  lleva a un sitio que sí pide su propia contraseña.
- Favicon 🗂️ del hub (distinto a los de los 4 módulos: 🏗️ Centro de
  Costos, 📊 Análisis Financiero, 🧾 Cotizador Histórico, 💵 Flujo de Caja) — aplica solo si
  se sigue publicando alguna copia como Claude Artifact; en GitHub Pages no
  hay favicon de "Artifact" que fijar, el `<link rel="icon">` del propio
  HTML basta.
- Las URLs de destino son estructurales (`/centro-de-costos/`,
  `/centro-de-costos-peru/`, `/analisis-financiero/`,
  `/cotizador-historico/`, `/flujo-de-caja/`, `/oportunidades/`) — no deberían cambiar nunca, a diferencia de los
  links opacos de Artifact que sí podían regenerarse por error.
- **Desde el 2026-10-06 es «Herramientas QUEMPIN»** (pedido del usuario: que
  las herramientas se sientan como un solo recorrido). Arriba, el botón «Abrir
  el Formulador de proyectos →» (ahí empieza cada proyecto) y las seis etapas
  del recorrido, cada una con la herramienta que la hace; Sistema QUEMPIN es un
  programa del computador, así que se nombra pero no se enlaza. Abajo, las
  tarjetas de los tableros con la etapa a la que sirven. Sigue sin datos.
- **Oportunidades en Mercado Público** (2026-10-13) es la primera tarjeta: es
  donde empieza un requerimiento (etapa 1), y la etapa 1 del recorrido la
  nombra junto a la Planilla de Ingreso.
- **Desde el 2026-10-14 las tarjetas van en el orden del recorrido**
  (Oportunidades, Cotizador, Centro de Costos, Análisis Financiero y, al final,
  Flujo de Caja), y bajo el botón del Formulador una línea dice que su sección
  «Pendientes del equipo» muestra lo que espera a alguien.

## Portal QUEMPIN (2026-10-15, en prueba)

Pedido del usuario (2026-10-15): un menú por temática para llegar a todas las
herramientas «sin tener que usar tantos links», con las calculadoras incluidas,
y que se pueda revertir si no le gusta.

- **Qué es**: `Visualizador Web/portal/index.html`, publicado en
  `https://cristobal-monzo.github.io/finanzas-quempin/portal/`. Una sola
  ventana: menú por necesidad (☰), buscador (Ctrl K), proyecto elegido una vez
  y pestañas con las herramientas abiertas dentro (iframes del mismo sitio).
  No lleva datos ni contraseña: cada herramienta pide la suya (la del equipo,
  que el navegador recuerda).
- **Cambios del 2026-10-16** (pedido del usuario):
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
- **Por qué funciona**: el Formulador, los tableros y la Calculadora están en el
  mismo sitio (`cristobal-monzo.github.io`). Eso permite tres cosas:
  - el portal los abre dentro;
  - ve a qué herramienta lleva cada enlace;
  - comparte con ellos el `localStorage`: la contraseña recordada y los
    proyectos del Formulador.

  Verificado el 2026-10-15:
  - GitHub Pages no manda X-Frame-Options ni CSP.
  - Dentro del portal el Formulador sí puede pedir la carpeta
    (`showDirectoryPicker`), algo que un sitio distinto tiene prohibido.
- **El registro** (`<script type="application/json" id="portal-registro">`):
  grupos y herramientas. Cada herramienta lleva:
  - `tipo`: marco, excel, programa, archivo, ayuda, inicio o vista (una sección
    propia del portal, en su pestaña: `vista` es su id).
  - `ruta` y `peru`.
  - `familia` y `alias`: la misma página va en una sola pestaña. El
    Formulador incluye Seguimiento; el Análisis incluye Ingresar datos. La
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
  - Planilla de Ingreso: Excel para la web en una pestaña nueva, con el enlace
    de `js/m365-config.js` del Formulador.
  - Control de Documentos: el portal dice dónde está, porque aún no tiene
    enlace web.
  - QUEMPIN.exe (cotización, OC, clientes): se abre por `quempin://`, fuera
    del navegador.
- **En el navegador**: guarda `quempin_portal_pestanas` (vuelven sin cargar,
  solo la activa), `quempin_portal_proyecto`, `quempin_portal_menu` y
  `quempin_portal_pais`. El tema usa `quempin_hub_theme`, el del índice. Cuando
  una herramienta guarda la contraseña, las que esperaban con el candado se
  recargan solas. Se mantienen 8 herramientas cargadas como máximo.
- **Usuario** (2026-10-16, pedido del usuario: «un selector de usuario» con
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
- **Recorrido de proyectos** (2026-10-20, pedido del usuario: una herramienta
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
    y los `borrador-cotizacion` del `buzon/`. **Nunca escribe en la carpeta**, y
    en la página no va ningún dato: se arma en el navegador de cada persona.
    Sin conexión, sin permiso o en un navegador que no abre carpetas, dice qué
    hacer y da el botón (`Conectar biblioteca` reutiliza `conectarBiblioteca`).
  - **Las reglas** (`rcArmar`, `rcTarjetaReq`): entra lo vivo en la Planilla
    (Evaluación, Ofertado, Adjudicado), lo que tiene formulación (si la Planilla
    no lo cerró), lo que tiene ficha en el Análisis, los presupuestos sin N° y
    las fichas del Análisis sin N°. La etapa sale de lo más avanzado que haya:
    ficha en el Análisis (Ejecución, o Cierre con 100 % de avance); Adjudicado sin
    ficha (Ejecución: «Pasar a ejecución» o «Crear su ficha»); Ofertado,
    formulación Enviada o cotización emitida (Oferta, con el resultado de
    Mercado Público); borrador esperando en Sistema QUEMPIN, o formulación con
    precio y sin errores (Cotización); formulación en curso (Formulación); y si
    no, Requerimiento. Lo que lleva más de 60 días sin moverse va plegado al pie
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
- **Planificación semanal** (2026-10-20, pedido del usuario: planificar cada semana
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
    los de más de 60 días), con la clave `req:<N°>` o `tag:<TAG>`; una asignación
    hecha con el TAG sigue siendo del mismo proyecto cuando este recibe su N°.
    El nombre de cada uno queda en el archivo, así una semana pasada se sigue
    leyendo cuando el proyecto terminó.
  - **Máximo 3** (`PL_MAX`): con 3, la persona sale deshabilitada en las ventanitas
    («Completo»). Si dos computadores se pasan a la vez, la casilla queda en rojo
    («4 de 3: quita 1»).
  - **La alarma**: un proyecto activo sin nadie ningún día de la semana de hoy,
    salvo que se marque «Sin trabajo esta semana» (una pausa de esa semana, que
    también se quita al asignarle a alguien). Se ve en la cabecera (`#plAlertaCab`,
    desde cualquier herramienta; no en el teléfono, donde no cabe), en el menú y en
    el Inicio (número y línea en rojo), y la vista la detalla arriba. Para eso el
    portal lee la carpeta al abrirse aunque no abra en el Inicio, sin pedir permisos.
  - **Dónde se guarda**: en la carpeta de intercambio, en
    `publicado/planificacion/<AAAA-Www>/<dispositivo>.json` (esquema
    `planificacion-semana` del catálogo; lo agregado a mano, en
    `publicado/planificacion/lista/`, esquema `planificacion-lista`). Cada navegador escribe solo su archivo
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
- **Publicar**: copiar el archivo a `.worktrees/gh-pages/portal/index.html`,
  hacer commit y push. No tiene build ni datos, y `publicar.py` no lo toca.
- **Revertir**: borrar `portal/` en gh-pages, o hacer `git revert` del commit
  que lo agregó. Para el portal no se cambió el índice ni ninguna herramienta.
- **Pruebas**:
  - `Visualizador Web/tests/test_portal.py` revisa:
    - el registro contra lo publicado;
    - los enlaces que leen el AF, el CC, el Formulador y la Calculadora;
    - el portal en Chromium, sobre un sitio de mentira con las mismas rutas.
  - `auditoria_movil.py portal` revisa el teléfono.
- **Pendiente si se adopta (fase 2)**:
  - los contadores de «Pendientes del equipo» leídos de la carpeta de
    intercambio;
  - el índice apuntando al portal;
  - un enlace web al Control de Documentos.

  Si el Formulador activa SharePoint (`clientId` en `m365-config.js`), su
  ingreso por redirección no funciona dentro de un marco: dentro del portal hay
  que usar una ventana emergente.

## Enlaces por proyecto entre tableros (2026-10-14)

- La ficha de un proyecto del **Análisis Financiero** (Chile, con gasto real)
  lleva **«Ver sus facturas ↗»**: abre el Centro de Costos con
  `#tag=<TAG>`.
- El **Centro de Costos** (Chile) lee `#tag=<TAG>` y elige el proyecto cuyos
  documentos llevan ese prefijo en su N° de referencia (`DEMO-101` → `DEMO`;
  medido: 19 prefijos, ninguno con dos nombres). Con un proyecto elegido, junto
  a «Limpiar filtros» ofrece **«Ficha en Análisis Financiero ↗»**
  (`analisis-financiero/#proyecto=<TAG>`).
- El de Perú no lee `#tag=`: por eso el AF de Perú no muestra el enlace.

## Navegación entre tableros: selector de país + 3 pestañas (2026-10-01)

Pedido del usuario: la cabecera de cada tablero tenía 6 pestañas (3 módulos ×
2 países). Ahora lleva un selector de país (Chile / Perú) y solo las 3
pestañas de módulo; cambiar de país lleva al mismo módulo en el otro país.

- El HTML (`<nav class="viz-modnav">`) y su JS (bloque "navegación entre
  tableros: país + pestaña activa") son **idénticos en los 5 templates**. Lo
  único propio de cada uno es `data-nav-activo`, la subruta publicada (en
  Análisis Financiero la pone el build, `__AF_NAV_ACTIVO__`): de ahí el JS
  saca el país del selector, a qué país apuntan las pestañas y cuál marca.
  `Visualizador Web/tests/test_navegacion_tableros.py` falla si una copia
  diverge — si cambias la navegación, cámbiala en los 5.
- Un módulo nuevo es una pestaña más en todos los templates y en `MODULOS`
  de ese test (así entró Flujo de Caja el 2026-10-02, y Oportunidades en
  Mercado Público el 2026-10-13: hoy son 7 templates y 5 pestañas). Un país
  nuevo es otra `<option>` (su `value` es el sufijo de la subruta, como
  `-peru`) y ese sufijo en el JS, que hoy solo reconoce `-peru`.
- Un módulo que existe solo para Chile va en `SOLO_CHILE` del JS (hoy
  `flujo-de-caja` y `oportunidades`): su pestaña apunta siempre a Chile, y
  elegir otro país desde ese tablero lleva a Centro de Costos de ese país.
- La pestaña de un módulo nuevo solo aparece en los demás tableros cuando se
  regeneran y publican: publícalos todos juntos (`publicar.py --todos`), o
  uno enlaza a un tablero que el resto todavía no muestra.
- **Enlace «Formulador de proyectos ↗»** (`a.viz-modnav-herr`, 2026-10-06), a
  la derecha de las pestañas, dentro del mismo HTML idéntico de los 7
  templates (con su CSS): lleva a los proyectos, su formulación y su
  seguimiento, en pestaña nueva. En pantallas angostas dice solo
  «Formulador ↗» (`.viz-modnav-largo`).

## Menús desplegables con la estética del tablero (2026-10-05)

Pedido del usuario: la lista que abre un `<select>` (la del sistema operativo)
«no parecía pertenecer al dashboard». Cada template lleva, justo después de
`.viz-modnav-pais option`, un **bloque CSS idéntico en los 7**: flecha propia
en todos los `<select>` y, bajo `@supports (appearance: base-select)`, la lista
abierta dibujada con la paleta del tablero (fondo de tarjeta, opción elegida en
naranjo con ✓, hover naranjo suave; la del selector de país, oscura como la
cabecera). Lo dibujan Chrome y Edge desde la versión 135; Safari y Firefox
siguen con la lista del sistema. Un tablero nuevo copia ese bloque tal cual.

- La regla de `appearance: base-select` tiene que pesar lo mismo que la de la
  flecha (`:not(.viz-modnav-pais)` incluido): con menos especificidad, la de la
  flecha (`appearance: none`) le gana y la lista vuelve a ser la del sistema.
- En ese modo el texto largo no termina en «…»: se corta antes de la flecha
  (`overflow: clip; overflow-clip-margin: content-box`).
- El Formulador usa el mismo criterio (`css/styles.css`), y sus campos de texto
  con lista (N° de requerimiento, cliente) usan su lista propia `.pop` en vez de
  `<datalist>`, que no admite estilos.

## Hosting — GitHub Pages (decidido y migrado, 2026-08-05)

Los 3 Claude Artifacts privados se reemplazaron por **un solo sitio en
GitHub Pages**, repo público `cristobal-monzo/finanzas-quempin`, servido
desde la rama huérfana `gh-pages` (separada de `master`: solo contiene los
4 archivos estáticos publicados, nunca el código fuente ni `docs/`):

```
https://cristobal-monzo.github.io/finanzas-quempin/                     # hub
https://cristobal-monzo.github.io/finanzas-quempin/centro-de-costos/
https://cristobal-monzo.github.io/finanzas-quempin/centro-de-costos-peru/
https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero/
https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero-peru/
https://cristobal-monzo.github.io/finanzas-quempin/cotizador-historico/
https://cristobal-monzo.github.io/finanzas-quempin/cotizador-historico-peru/
https://cristobal-monzo.github.io/finanzas-quempin/flujo-de-caja/          # solo Chile (2026-10-02)
https://cristobal-monzo.github.io/finanzas-quempin/oportunidades/          # solo Chile (2026-10-13)
```

**Cómo publicar (reemplaza "usar el tool `Artifact`" en toda la
documentación vieja de cada módulo)**: copiar el `build/index.html` recién
generado a `.worktrees/gh-pages/<subruta>/index.html` (worktree local ya
creado para esto — `git worktree list` lo muestra), `git add`/`commit`/
`push` desde ahí. Ya no hay un link opaco que "nunca hay que regenerar": la
URL de cada tablero es estructural (depende solo de la subruta), así que
tampoco hace falta guardar/leer un link en el `MEMORY.md` de cada skill.

| Módulo | Subruta | Origen (`build/index.html`) |
|---|---|---|
| Centro de Costos | `centro-de-costos` | `Centro de Costos/Visualizador Web/build/index.html` |
| Centro de Costos Perú | `centro-de-costos-peru` | `Peru/Centro de Costos/Visualizador Web/build/index.html` |
| Análisis Financiero | `analisis-financiero` | `Sistema Analisis Financiero/Visualizador Web/build/index.html` |
| Análisis Financiero Perú | `analisis-financiero-peru` | `Peru/Análisis Financiero/Visualizador Web/build/index.html` |
| Cotizador Histórico | `cotizador-historico` | `Cotizador Historico/Visualizador Web/build/index.html` |
| Cotizador Histórico Perú | `cotizador-historico-peru` | `Peru/Cotizador Historico/Visualizador Web/build/index.html` |
| Flujo de Caja | `flujo-de-caja` | `Flujo de Caja/Visualizador Web/build/index.html` |
| Oportunidades en Mercado Público | `oportunidades` | `Sistema Intercambio/Visualizador Web/build/index.html` |

```
py -3.14 "Visualizador Web/publicar.py" cc af cot fc op     # o --todos; claves: cc ccpe af afpe cot cotpe fc op
git -C ".worktrees/gh-pages" commit -m "actualizar tableros: <cuáles>"
git -C ".worktrees/gh-pages" push
```

`publicar.py` (2026-10-08) copia el `build/index.html` de cada uno a
`.worktrees/gh-pages/<subruta>/`, deja su carpeta `reportes/` igual a la del
build, verifica con el candado que el build y la copia abren con la contraseña
de este equipo (también cada archivo cifrado que citan sus datos) y lo deja en
el índice de git. Si algo no abre, no toca gh-pages. **No copies tableros a
mano**: desde ese día el de Análisis Financiero lleva sus reportes PDF en
`reportes/<huella>.json`, cifrados aparte, y un `index.html` copiado solo
tendría botones de reporte que no abren nada. El hub (`index.html` de esta
carpeta, sin datos) se sigue copiando a mano a `.worktrees/gh-pages/index.html`.

**La verificación con `candado.py` no se salta** (2026-10-05; `publicar.py`
la hace sola desde el 2026-10-08): confirma que
el tablero copiado se abre con la contraseña de este equipo. Ese día se
publicó Análisis Financiero cifrado con la contraseña de prueba de los
tests (la suite lo había regenerado entre el build y la copia) y nadie del
equipo podía abrirlo. Los tests que causaban eso ya no tocan los tableros
reales, pero un tablero que no abre no se publica, venga de donde venga.

**Esta es la única copia de esta receta** (consolidado 2026-08-18 — antes
estaba repetida casi textual en `Actualizar_CC`, `Actualizar_AF`,
`Actualizar_Cotizador`, `Actualizar_Finanzas` y en el `MEMORY.md` de
`Registro_Centro_de_Costos`, con el riesgo real de que una futura migración
de hosting quedara aplicada a medias — ya pasó una vez, con la migración de
Artifacts a GitHub Pages). Esos skills (fusionados el 2026-10-13 en los de registro de cada módulo) solo enlazan acá para el "cómo" —
si necesitas cambiar la mecánica de publicación, cámbiala una sola vez,
en esta sección.

## Punto de control de acceso — candado con cifrado real (2026-10-05)

**GitHub Pages no ofrece un sitio realmente privado fuera de GitHub
Enterprise Cloud**: un repositorio privado + plan Pro/Team sigue
publicando el sitio de Pages *públicamente alcanzable* por cualquiera con
el link (verificado 2026-08-05, ver fuentes abajo). Al migrar, el usuario
aceptó repo público + el gate de contraseña de los dashboards, una barrera
débil: los datos iban en base64 y la contraseña escrita en claro en cada
`template.html`, así que cualquiera con el link o el repo leía las cifras.
El 2026-10-05 el clasificador de permisos de Claude Code empezó a bloquear
el push por eso, y el usuario pidió cifrar.

Cómo funciona desde entonces (`Visualizador Web/candado.py` + `candado.js`):

- Cada build guarda sus datos en un **sobre cifrado** (AES-256-GCM, clave
  derivada de la contraseña con PBKDF2-SHA256, 600.000 iteraciones) en vez
  del base64, y `candado.js`, que el build inserta, lo abre en el navegador.
  En la página no hay contraseña contra la cual comparar: sin ella los datos
  son ilegibles, en el sitio y en el repo.
- **Sobre versión 2 (2026-10-08): los datos se comprimen con gzip antes de
  cifrar** (`"comp": "gzip"`), porque lo cifrado ya no se puede comprimir:
  Centro de Costos bajó de 1,0 MB a ~0,1 MB de datos y el Cotizador de 3,0 MB
  a ~0,25 MB. El navegador los descomprime con `DecompressionStream` (Chrome,
  Edge, Safari 16.4+, Firefox 113+); si no puede, el candado lo dice en vez de
  hablar de contraseña incorrecta. Los sobres versión 1 (sin `comp`) se siguen
  abriendo.
- **Archivos cifrados aparte**: lo que no hace falta para dibujar el tablero
  va en `reportes/<huella>.json` junto al `index.html`, cifrado con la misma
  contraseña (`candado.cifrar_bytes`, sin comprimir), y el tablero lo baja al
  usarlo (`QuempinCandado.abrirArchivo`). Hoy, los reportes PDF del AF, que
  eran el 97 % de su tablero. El nombre sale del contenido: un reporte que no
  cambió no se vuelve a subir. `candado.abre_con(..., carpeta=)` exige que
  cada archivo citado esté y abra.
- **La contraseña vive solo en `.contrasena_tableros`** (raíz del repo, una
  línea, gitignored) o en la variable `QUEMPIN_TABLEROS_CONTRASENA`. Sin ella
  el build falla: nunca se genera un tablero sin cifrar. No la escribas en un
  archivo versionado, un test, un doc ni una memoria; `test_candado.py` revisa
  los archivos versionados en el equipo que la tiene. Los tests usan una de
  prueba (`conftest.py` de la raíz).
- El navegador **recuerda la clave derivada** (`localStorage`,
  `quempin_viz_clave`), la misma para los 8 tableros: la contraseña se
  escribe una vez. Si cambia, la recordada deja de abrir y se vuelve a pedir.
- **El Formulador usa la misma contraseña** (2026-10-13): su `index.html`
  (otro repositorio, mismo sitio) lleva un sobre corto cifrado con ella
  (`<script id="llaveFormulador">`) y una copia de `candado.js` en su `js/`
  (`test_candado.py` exige que sea idéntica). Recuerda la misma
  `quempin_viz_clave`: entrar a uno abre los demás.
- **Cambiar la contraseña**: editar `.contrasena_tableros`, regenerar y
  publicar los 8 tableros, regenerar el sobre del Formulador con
  `py -3.14 "Visualizador Web/candado.py" --llave-formulador` y publicarlo, y
  avisar al equipo. El contenido cifrado es
  público y se puede atacar sin conexión, así que tiene que ser larga (la
  actual: 4 palabras al azar + 4 dígitos).
- **Un tablero nuevo**: `<script>__CANDADO_JS__</script>` antes de su
  `<script id="xx-data-b64" type="text/plain">`,
  `QuempinCandado.abrir('xx-data-b64', initApp)` en vez de un gate propio, y
  `candado.incrustar(...)` como último reemplazo del build. `test_candado.py`
  lo exige a toda plantilla.
- **Solo los datos van cifrados**: estructura, rótulos y código siguen siendo
  públicos, igual que las plantillas en `master`. Nada con datos se publica
  fuera de un sobre: los 20 informes PDF que estaban sueltos en
  `analisis-financiero/reportes/` se sacaron ese día (el tablero los lleva
  incrustados en sus datos).
- El historial de `gh-pages` se reemplazó ese día por un solo commit (los
  anteriores dejaban leer los datos). El anterior quedó solo como respaldo
  local en `refs/respaldo/gh-pages-antes-del-cifrado-2026-10-05`. GitHub
  puede conservar un tiempo los commits viejos accesibles por su
  identificador.

Si además hiciera falta ocultar la estructura o saber quién entra, quedan
las opciones de antes: un proxy con autenticación delante del sitio (ej.
Cloudflare Access) o Artifacts privados.

Fuentes: [GitHub Docs — Changing the visibility of your GitHub Pages site](https://docs.github.com/en/enterprise-cloud@latest/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site),
[GitHub Community Discussion #58203](https://github.com/orgs/community/discussions/58203).

## CI

`.github/workflows/tests.yml` (raíz del repo) corre la suite completa de
pytest en cada push y PR de cualquier rama menos `gh-pages` — ninguno de los tests toca datos
financieros reales (todos usan workbooks sintéticos en `tmp_path`), así
que el runner de GitHub no necesita ni puede acceder a los archivos reales
de Centro de Costos (viven solo en el OneDrive local). Instala Chromium
para la prueba de los reportes PDF: sin él, la CI falló desde el
2026-08-26 hasta el 2026-10-08 sin que nadie lo notara, y además solo
corría en `master`, que no es donde se trabaja.

## Convenciones técnicas esperadas (cuando se construya el HTML real)

Cada `<Módulo>/Visualizador Web/` crecerá, en su propio ciclo de diseño, con
algo como:

```
<Módulo>/Visualizador Web/
├── CLAUDE.md           # contenido a presentar (ya existe desde este scaffolding)
├── index.html
├── css/
├── js/
├── assets/             # copia o referencia al material gráfico necesario
└── data/               # exports saneados — gitignored
```

No crear estas subcarpetas/archivos hasta que el módulo correspondiente
aborde su propio diseño e implementación del HTML.
