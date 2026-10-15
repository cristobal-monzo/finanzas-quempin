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
  Inicio muestra Mi día, atajos, calculadoras y proyectos recientes. No lleva
  datos ni contraseña: cada herramienta pide la suya (la del equipo, que el
  navegador recuerda).
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
  - `tipo`: marco, excel, programa, archivo, ayuda o inicio.
  - `ruta` y `peru`.
  - `familia` y `alias`: la misma página va en una sola pestaña. El
    Formulador incluye Proyectos y Carta Gantt; el Análisis incluye Ingresar
    datos.
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
  - QUEMPIN.exe (cotización, OC, clientes): el portal dice cómo abrirlo.
- **En el navegador**: guarda `quempin_portal_pestanas` (vuelven sin cargar,
  solo la activa), `quempin_portal_proyecto`, `quempin_portal_menu` y
  `quempin_portal_pais`. El tema usa `quempin_hub_theme`, el del índice. Cuando
  una herramienta guarda la contraseña, las que esperaban con el candado se
  recargan solas. Se mantienen 8 herramientas cargadas como máximo.
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
  - un botón que abra QUEMPIN.exe (protocolo `quempin://` que registre el
    programa);
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
