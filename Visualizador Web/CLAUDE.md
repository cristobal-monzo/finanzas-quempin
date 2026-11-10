# CLAUDE.md — Visualizador Web (maestro)

Reglas de **todos los tableros** de Finanzas. Cada módulo tiene
`<Módulo>/Visualizador Web/` con un `CLAUDE.md` de contenido que enlaza aquí; este
archivo no se carga solo desde esas carpetas, así que **léelo antes de tocar un
tablero**. El Portal tiene el suyo: [`portal/CLAUDE.md`](portal/CLAUDE.md). Diseño
original: `docs/specs/2026-07-19-visualizador-web-design.md`.

## Rol, marca y mínimos

- Actúa como experto en HTML/UI/UX: responsivo (mobile-first), accesibilidad básica
  (contraste, foco de teclado visible, texto alternativo) y HTML/CSS/JS simple, sin
  frameworks pesados salvo que el módulo lo justifique en su `CLAUDE.md`.
- **Marca**: única fuente, `Material gráfico QUEMPIN/OFICIAL MANUAL DE MARCA GRÁFICA
  QUEMPIN.pdf` y `LOGO QUEMPIN.PNG`. Nunca inventes paleta, tipografía ni variante
  de logo. Si el manual no cubre un caso, extrapola de la paleta y anótalo en el
  `CLAUDE.md` del módulo.
- **Fuentes y logos: una sola copia, en `marca/`** (`fuentes.css`, `logo.png`, `favicon.png`; `marca.py`). Las plantillas
  llevan `__MARCA_FUENTES__`, `__MARCA_LOGO__` y `__MARCA_FAVICON__`, que `candado.incrustar()` reemplaza: cada tablero sigue
  siendo un solo archivo. El hub y el Portal enlazan `marca/fuentes.css`. **No pegues base64 en una plantilla**: `test_marca.py`
  lo rechaza.
- **Todo tablero lleva** al menos un gráfico interactivo (no una imagen), una tabla
  ordenable con búsqueda y filtro, un buscador de texto libre y filtros por las
  dimensiones del módulo. Un «consultor IA» es opcional: requiere backend o API key.

## Datos

El HTML publicado nunca lee el `.xlsx`/JSON fuente. Cada módulo exporta un snapshot saneado
(qué se expone lo define su `CLAUDE.md`). `<Módulo>/Visualizador Web/data/` queda en
`.gitignore`; el código del export sí se versiona.

## Teléfono: obligatorio y se verifica emulando uno

Todos los tableros tienen que poder revisarse en el teléfono. Nada de esto se ve en un
escritorio ni achicando la ventana.

- **Cabecera**: `<!DOCTYPE html>`, `<meta charset="utf-8">` y `<meta name="viewport"
  content="width=device-width, initial-scale=1">`, sin bloquear el zoom. Lo exige
  `tests/test_tableros_movil.py` para toda `*/Visualizador Web/template.html`.
- **Corte en 640 px** (`@media (max-width: 640px)`), igual en todos: navegación en una
  fila (país fijo + pestañas cortas que se deslizan centrando la activa), botón de tema
  junto al logo, KPIs en 2 columnas.
- **Tablas → tarjetas**, no scroll horizontal: primera celda como título, el resto en
  pares etiqueta/valor (AF: `etiquetarCeldas()`; si se ordena por columna, sus
  encabezados quedan como tira «Ordenar»). **Selectores siempre con `>`**
  (`table.viz-table > tbody`): el detalle expandido lleva tablas anidadas. Solo una
  matriz o una subtabla dentro de un detalle se desliza, con la primera columna fija.
- **Campos a 16 px en móvil**: con menos, el iPhone hace zoom al tocarlos.
- **Después de tocar una plantilla**, con los `build/index.html` regenerados:

  ```
  py -3.14 "Visualizador Web/auditoria_movil.py"            # tableros, hub y portal × 360/390/768 px
  py -3.14 "Visualizador Web/auditoria_movil.py" cc --capturas <carpeta fuera del repo>
  ```

  Termina con código 1 si algo se sale de la pantalla o queda un campo bajo 16 px. Las
  capturas muestran datos reales: nunca dentro del repo.

## Navegación y código compartido entre plantillas

8 tableros y 6 plantillas: CC en Chile y en Perú (dos plantillas que ya divergieron), AF y el
Cotizador (una para los dos países, con marcadores que pone cada build), Flujo de Caja y
Oportunidades.

- **Navegación** (`<nav class="viz-modnav">` y su JS): **idéntica en todos**; solo cambia
  `data-nav-activo`, la subruta (en AF y el Cotizador la pone el build: `__AF_NAV_ACTIVO__`,
  `__CH_NAV_ACTIVO__`).
  `tests/test_navegacion_tableros.py` falla si una copia diverge: cámbiala en todas.
- **Módulo nuevo** = una pestaña en todos los templates y en `MODULOS` de ese test.
  Publícalos juntos (`publicar.py --todos`) o uno enlazará a un tablero que el resto no
  muestra. Solo Chile = `SOLO_CHILE` del JS (hoy `flujo-de-caja`, `oportunidades`). **País
  nuevo** = otra `<option>` (su `value` es el sufijo de la subruta) y ese sufijo en el JS.
- **Enlace «Formulador de proyectos ↗»** (`a.viz-modnav-herr`): va en ese mismo HTML.
- **Cajas de números** (`numeros.js`, pedido del usuario 2026-11-10): un clic selecciona todo y lo que se escribe
  lleva punto de miles. Va incrustado junto a `candado.js` (`candado.incrustar`); el Portal y el hub lo enlazan
  (`../numeros.js`, que `publicar.py` copia). Toma solas las `type="number"` (su `.value` sigue sin formato); una
  caja de texto con montos lleva `data-num` (`="entero"` sin decimales). Un N° de OC o de requerimiento no: es un
  código. Copias idénticas en el Formulador (`js/`) y la Calculadora (`assets/`): `tests/test_numeros.py`.
- **Menús desplegables**: bloque CSS idéntico en todos, tras `.viz-modnav-pais option`
  (flecha propia y, con `@supports (appearance: base-select)`, lista con la paleta; Chrome
  y Edge 135+). Un tablero nuevo lo copia tal cual. La regla de `base-select` debe pesar lo
  mismo que la de la flecha (`:not(.viz-modnav-pais)`), o la lista vuelve a la del sistema;
  el texto largo se corta con `overflow: clip; overflow-clip-margin: content-box`.
- **Enlaces por proyecto**: la ficha de AF (Chile, con gasto real) abre CC con `#tag=<TAG>`;
  CC elige el proyecto por el prefijo del N° de referencia y ofrece
  `analisis-financiero/#proyecto=<TAG>`. El CC de Perú no lee `#tag=`, por eso AF Perú no
  muestra el enlace.

## Hub (`index.html` de esta carpeta)

Página estática sin datos ni contraseña («Herramientas QUEMPIN»: las seis etapas y una
tarjeta por tablero, en el orden del recorrido, con Oportunidades primero). Su dirección
abre el Portal; dentro de un marco o con `?indice` se ve el índice. Se edita a mano y se
publica con `publicar.py hub`. Sistema QUEMPIN se nombra pero no se enlaza.

## Hosting: cómo publicar (única copia de esta receta)

GitHub Pages, repo público `cristobal-monzo/finanzas-quempin`, rama huérfana `gh-pages`
(solo los estáticos, nunca código ni `docs/`), worktree en `.worktrees/gh-pages`. Las URL
son estructurales y no cambian: `https://cristobal-monzo.github.io/finanzas-quempin/<subruta>/`.

| Clave | Subruta | Build |
|---|---|---|
| `cc` | `centro-de-costos` | `Centro de Costos/Visualizador Web/build/index.html` |
| `ccpe` | `centro-de-costos-peru` | `Peru/Centro de Costos/Visualizador Web/build/index.html` |
| `af` | `analisis-financiero` | `Sistema Analisis Financiero/Visualizador Web/build/index.html` |
| `afpe` | `analisis-financiero-peru` | `Peru/Análisis Financiero/Visualizador Web/build/index.html` |
| `cot` | `cotizador-historico` | `Cotizador Historico/Visualizador Web/build/index.html` |
| `cotpe` | `cotizador-historico-peru` | `Peru/Cotizador Historico/Visualizador Web/build/index.html` |
| `fc` | `flujo-de-caja` (solo Chile) | `Flujo de Caja/Visualizador Web/build/index.html` |
| `op` | `oportunidades` (solo Chile) | `Sistema Intercambio/Visualizador Web/build/index.html` |

```
py -3.14 "Visualizador Web/publicar.py" cc af cot fc op     # o --todos
git -C ".worktrees/gh-pages" commit -m "actualizar tableros: <cuáles>"
git -C ".worktrees/gh-pages" push
```

- `publicar.py` copia cada build, deja `reportes/` igual a la del build, **verifica con el
  candado** que abran con la contraseña del equipo (también cada archivo cifrado que citan)
  y lo deja en el índice de git; si algo no abre, no toca gh-pages. **Nunca copies tableros
  a mano** (AF quedaría sin sus reportes) ni te saltes la verificación: una vez se publicó
  AF cifrado con la contraseña de prueba de los tests y nadie pudo abrirlo.
- **El hub y el Portal** no llevan datos: `py -3.14 "Visualizador Web/publicar.py" portal hub` los copia con los archivos de
  `marca/` que enlazan. `--todos` no los incluye. Sin `marca/` en `gh-pages` se verían con la letra del sistema.
- Antes de publicar, `publicar.py` revisa solo (2026-11-06): que `gh-pages` local tenga todo lo de origin (si
  otra sesión publicó después, primero `pull --ff-only`) y, para el hub y el Portal, que su archivo esté
  commiteado y con el CI de ese commit en verde (`gh run list`; sin push no hay CI). `--sin-ci` se salta lo
  segundo. La copia lleva `<meta name="quempin-version" content="rama@commit fecha">`, que las observaciones
  anotan. Igual avisa a las otras sesiones.
- Si cambia la mecánica, cámbiala solo aquí: las skills enlazan a esta sección.

## Punto de control de acceso: el candado (`candado.py` + `candado.js`)

GitHub Pages no ofrece un sitio privado, así que **los datos van cifrados**; estructura,
rótulos y código siguen públicos. Nada con datos se publica fuera de un sobre.

- **Sobre**: AES-256-GCM, clave con PBKDF2-SHA256 (600.000 iteraciones). El build lo incrusta
  y `candado.js` lo abre en el navegador; en la página no hay contraseña contra la cual
  comparar. Versión 2: gzip antes de cifrar (`"comp": "gzip"`, `DecompressionStream`); los
  sobres v1 se siguen abriendo.
- **Archivos aparte**: lo que no hace falta para dibujar va en `reportes/<huella>.json` junto
  al `index.html` (`candado.cifrar_bytes`; hoy los PDF de AF) y se baja al usarlo
  (`QuempinCandado.abrirArchivo`). `candado.abre_con(..., carpeta=)` exige que cada uno abra.
- **Contraseña**: solo en `.contrasena_tableros` (raíz del repo, gitignored) o en
  `QUEMPIN_TABLEROS_CONTRASENA`; sin ella el build falla. **Nunca la escribas** en un archivo
  versionado, test, doc o memoria (`test_candado.py` lo revisa). Los tests usan una de prueba
  (`conftest.py` de la raíz).
- El navegador recuerda la clave derivada (`quempin_viz_clave`), común a los tableros y al
  Formulador (`<script id="llaveFormulador">` y copia idéntica de `candado.js`, lo exige
  `test_candado.py`).
- **Cambiar la contraseña**: edita `.contrasena_tableros`, regenera y publica los 8 tableros,
  regenera el sobre del Formulador (`py -3.14 "Visualizador Web/candado.py" --llave-formulador`)
  y publícalo, y avisa al equipo. Debe ser larga: lo cifrado es público y atacable sin conexión.
- **Tablero nuevo**: `<script>__CANDADO_JS__</script>` antes de su `<script id="xx-data-b64"
  type="text/plain">`, `QuempinCandado.abrir('xx-data-b64', initApp)` en vez de un gate propio,
  y `candado.incrustar(...)` como último reemplazo del build. `test_candado.py` lo exige.
- El historial de `gh-pages` se reemplazó al cifrar (respaldo local en
  `refs/respaldo/gh-pages-antes-del-cifrado-2026-10-05`). Para ocultar también la estructura o
  saber quién entra haría falta un proxy con autenticación (ej. Cloudflare Access).

## CI

`.github/workflows/tests.yml` corre pytest completo en cada push y PR, salvo `gh-pages`. Los
tests usan workbooks sintéticos, nunca datos reales; instala Chromium para los PDF.
Desde 2026-11-06 en dos partes (`modulos` y `portal`, este con `--reruns 2`) e instala `requirements.lock`:
si agregas o subes una librería, `py -3.14 fijar_dependencias.py` y commitea el lock.
