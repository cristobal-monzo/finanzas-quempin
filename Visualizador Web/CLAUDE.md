# CLAUDE.md — Visualizador Web (maestro)

Este documento aplica a **los visualizadores web de todos los módulos** de
`Finanzas QUEMPIN` (Centro de Costos, Cotizador Historico, Flujo de Caja, y
cualquier módulo futuro). Cada módulo tiene su propia carpeta
`<Módulo>/Visualizador Web/` con un `CLAUDE.md` de contenido que enlaza aquí
— este archivo no se auto-carga en esas subcarpetas (no son ancestro/
descendiente en el árbol), así que léelo explícitamente antes de tocar
cualquier visualizador.

Ver el spec de diseño original en
[`docs/superpowers/specs/2026-07-19-visualizador-web-design.md`](../docs/superpowers/specs/2026-07-19-visualizador-web-design.md).

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

## Índice (hub) de los 3 tableros

`Visualizador Web/index.html` (raíz, junto a este `CLAUDE.md`) es una
página estática que **no muestra datos** — solo 3 tarjetas, una por
módulo, cada una con un botón que abre en pestaña nueva el tablero de ese
módulo. Reutiliza el mismo sistema de marca que los 3 visualizadores
(paleta oficial, Lato embebida, cabecera negra con filete naranjo, toggle
de tema). No hay `build_visualizador.py` para este archivo porque no lee
ningún Excel/JSON: se edita a mano y se vuelve a copiar a
`.worktrees/gh-pages/index.html` para republicar.

- **Sin gate de contraseña** (decisión explícita del usuario, 2026-07-29,
  sigue vigente): el hub no expone información financiera, cada tarjeta
  lleva a un sitio que sí pide su propia contraseña.
- Favicon 🗂️ del hub (distinto a los de los 3 módulos: 🏗️ Centro de
  Costos, 📊 Análisis Financiero, 🧾 Cotizador Histórico) — aplica solo si
  se sigue publicando alguna copia como Claude Artifact; en GitHub Pages no
  hay favicon de "Artifact" que fijar, el `<link rel="icon">` del propio
  HTML basta.
- Las 3 URLs de destino son estructurales (`/centro-de-costos/`,
  `/analisis-financiero/`, `/cotizador-historico/`) — no deberían cambiar
  nunca, a diferencia de los links opacos de Artifact que sí podían
  regenerarse por error.

## Hosting — GitHub Pages (decidido y migrado, 2026-08-05)

Los 3 Claude Artifacts privados se reemplazaron por **un solo sitio en
GitHub Pages**, repo público `cristobal-monzo/finanzas-quempin`, servido
desde la rama huérfana `gh-pages` (separada de `master`: solo contiene los
4 archivos estáticos publicados, nunca el código fuente ni
`docs/superpowers/`):

```
https://cristobal-monzo.github.io/finanzas-quempin/                     # hub
https://cristobal-monzo.github.io/finanzas-quempin/centro-de-costos/
https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero/
https://cristobal-monzo.github.io/finanzas-quempin/cotizador-historico/
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
| Análisis Financiero | `analisis-financiero` | `Sistema Analisis Financiero/Visualizador Web/build/index.html` |
| Cotizador Histórico | `cotizador-historico` | `Cotizador Historico/Visualizador Web/build/index.html` |

```
cp "<Origen de la tabla>" ".worktrees/gh-pages/<subruta>/index.html"
git -C ".worktrees/gh-pages" add <subruta>/index.html
git -C ".worktrees/gh-pages" commit -m "actualizar tablero de <módulo>"
git -C ".worktrees/gh-pages" push
```

**Esta es la única copia de esta receta** (consolidado 2026-08-18 — antes
estaba repetida casi textual en `Actualizar_CC`, `Actualizar_AF`,
`Actualizar_Cotizador`, `Actualizar_Finanzas` y en el `MEMORY.md` de
`Registro_Centro_de_Costos`, con el riesgo real de que una futura migración
de hosting quedara aplicada a medias — ya pasó una vez, con la migración de
Artifacts a GitHub Pages). Esos skills solo enlazan acá para el "cómo" —
si necesitas cambiar la mecánica de publicación, cámbiala una sola vez,
en esta sección.

## Punto de control de acceso — resuelto (2026-08-05), con este trade-off explícito

**GitHub Pages no ofrece un sitio realmente privado fuera de GitHub
Enterprise Cloud**: un repositorio privado + plan Pro/Team sigue
publicando el sitio de Pages *públicamente alcanzable* por cualquiera con
el link — la visibilidad del repo protege el código fuente, no el sitio
publicado (verificado 2026-08-05, ver fuentes abajo). Dado esto, decisión
explícita del usuario: **repo público + el mismo gate de contraseña que ya
tenían los 3 dashboards** (barrera débil, no seguridad real — ya se
documentaba así antes de esta migración). Esto es objetivamente **menos
privado** que los Artifacts anteriores (privados por defecto, no
indexables); el usuario aceptó ese trade-off a cambio de un solo dominio y
poder automatizar el deploy vía `git push` en vez de depender de que un
agente llame al tool `Artifact` cada vez.

Si en el futuro se necesita control de acceso real, las opciones que
quedan (no implementadas): un proxy con autenticación real delante del
sitio estático (ej. Cloudflare Access), o volver a Artifacts privados para
el/los tableros que lo requieran.

Fuentes: [GitHub Docs — Changing the visibility of your GitHub Pages site](https://docs.github.com/en/enterprise-cloud@latest/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site),
[GitHub Community Discussion #58203](https://github.com/orgs/community/discussions/58203).

## CI

`.github/workflows/tests.yml` (raíz del repo) corre la suite completa de
pytest en cada push/PR a `master` — ninguno de los tests toca datos
financieros reales (todos usan workbooks sintéticos en `tmp_path`), así
que el runner de GitHub no necesita ni puede acceder a los archivos reales
de Centro de Costos (viven solo en el OneDrive local).

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
