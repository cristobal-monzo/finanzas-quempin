# Visualizador Web (scaffolding) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan produces documentation/scaffolding only (no code, no automated tests) — each task's "test cycle" is a content-completeness check, not a unit test.

**Goal:** Crear la estructura de carpetas `Visualizador Web/` (raíz + una por módulo) y los `CLAUDE.md` que documentan cómo debe construirse a futuro cada visualizador web, según el spec aprobado.

**Architecture:** Cuatro archivos `CLAUDE.md` nuevos (uno maestro en la raíz, tres de contenido por módulo) + una referencia añadida al `CLAUDE.md` raíz existente + una regla nueva en `.gitignore`. Ningún código ejecutable se crea en este plan.

**Tech Stack:** Markdown puro. Sin dependencias.

## Global Constraints

- Nombrar todos los archivos nuevos `CLAUDE.md` (no un nombre genérico) — consistente con la convención existente del repo, ver spec §"Por qué CLAUDE.md".
- Cada `CLAUDE.md` de módulo debe enlazar explícitamente a `../../Visualizador Web/CLAUDE.md` (ruta relativa correcta desde `<Módulo>/Visualizador Web/`) — no hay auto-carga entre ramas del árbol.
- El maestro debe cubrir, sin excepción: rol de dev experto, manual de marca + material gráfico, mandato de herramientas dinámicas (gráfico interactivo, tabla dinámica, buscador, filtros; IA opcional), export estático saneado obligatorio, hosting GitHub Pages con subrutas, y el punto abierto de control de acceso (no bloqueante).
- No escribir HTML/CSS/JS ni instalar ninguna librería en este plan — spec §"Fuera de alcance".
- Datos financieros reales del repo nunca se versionan — ver `.gitignore` raíz existente; la nueva regla debe seguir el mismo patrón (comentario + rutas).

---

### Task 1: Doc maestro compartido + referencia desde la raíz + `.gitignore`

**Files:**
- Create: `Visualizador Web/CLAUDE.md`
- Modify: `CLAUDE.md` (raíz) — tabla de módulos y sección de precauciones
- Modify: `.gitignore` (raíz)

**Interfaces:**
- Produces: la ruta `Visualizador Web/CLAUDE.md` que las Tasks 2-4 deben enlazar como `../../Visualizador Web/CLAUDE.md` desde `<Módulo>/Visualizador Web/CLAUDE.md`.

- [ ] **Step 1: Crear `Visualizador Web/CLAUDE.md`** con este contenido exacto:

```markdown
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

## Hosting

GitHub Pages recomendado: **un solo sitio** servido desde este repo, con
subrutas por módulo (`/centro-de-costos/`, `/cotizador-historico/`,
`/flujo-de-caja/`) en vez de tres despliegues independientes. Migrar a otro
host (Netlify, Vercel) más adelante no debería requerir rediseño, porque
todo es HTML estático que lee un JSON local.

## Punto abierto — control de acceso (no bloqueante, pero obligatorio de resolver antes de publicar datos reales)

GitHub Pages sobre un repositorio público sirve el sitio a cualquiera con el
link (o indexable por buscadores). Los datos de origen son financieros
reales de QUEMPIN SpA. **Antes de publicar el primer visualizador con datos
reales** (no con datos de ejemplo), hay que decidir explícitamente con el
usuario una de:

- Repositorio privado + GitHub Pages de pago (requiere plan Pro/Team/
  Enterprise).
- Alguna gate de acceso del lado del cliente (ej. contraseña simple) —
  nota: esto es una barrera débil, no seguridad real, solo disuade acceso
  casual.
- Servir detrás de un proxy con autenticación real.

No se debe publicar un visualizador con datos financieros reales sin haber
resuelto este punto con el usuario primero.

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
```

- [ ] **Step 2: Verificar que el archivo se creó con las 7 secciones esperadas**

Run: `grep -c "^## " "Visualizador Web/CLAUDE.md"`
Expected: `7` (Rol, Manual de marca, Mandato de herramientas dinámicas, Datos, Hosting, Punto abierto, Convenciones técnicas)

- [ ] **Step 3: Editar `CLAUDE.md` raíz — agregar fila a la tabla de módulos**

Localizar la tabla de módulos (busca la línea que empieza con
`| Módulo | Estado | Documentación |`) y agregar una fila nueva
inmediatamente después de la fila de `Flujo de Caja`:

```markdown
| [Visualizador Web/](Visualizador%20Web/CLAUDE.md) | Scaffolding (2026-07-19) | `Visualizador Web/CLAUDE.md` |
```

Agregar también, después del párrafo que describe Centro de Costos (antes
del párrafo "Se espera que los módulos futuros..."), este párrafo nuevo:

```markdown
**Visualizador Web** es transversal a todos los módulos: cada uno tendrá,
en su propia carpeta, una subcarpeta `Visualizador Web/` con un HTML
publicado online (gráficos, tablas dinámicas, buscadores, filtros). El doc
maestro compartido (marca, mandato de herramientas dinámicas, política de
datos, hosting) vive en `Visualizador Web/CLAUDE.md` a nivel raíz; cada
módulo tiene su propio `<Módulo>/Visualizador Web/CLAUDE.md` con el
contenido específico a presentar. Hoy es solo scaffolding — ningún HTML
real existe todavía, ver el spec en
`docs/superpowers/specs/2026-07-19-visualizador-web-design.md`.
```

- [ ] **Step 4: Verificar el edit de la raíz**

Run: `grep -n "Visualizador Web" "CLAUDE.md"`
Expected: al menos 2 líneas de match (la fila de la tabla + el párrafo nuevo).

- [ ] **Step 5: Agregar regla a `.gitignore` raíz**

Añadir al final del bloque de comentario existente
`# Datos financieros reales de QUEMPIN SpA -- nunca versionar (ver CLAUDE.md).`
(mismo bloque, no uno nuevo) esta línea:

```
*/Visualizador Web/data/
```

- [ ] **Step 6: Verificar el patrón del `.gitignore`**

Run: `grep -n "Visualizador Web" .gitignore`
Expected: 1 línea de match: `*/Visualizador Web/data/`

- [ ] **Step 7: Commit**

```bash
git add "Visualizador Web/CLAUDE.md" "CLAUDE.md" ".gitignore"
git commit -m "docs(visualizador-web): crear doc maestro y referenciarlo desde la raíz

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Contenido borrador — Centro de Costos

**Files:**
- Create: `Centro de Costos/Visualizador Web/CLAUDE.md`

**Interfaces:**
- Consumes: enlaza a `../../Visualizador Web/CLAUDE.md` (producido en Task 1).

- [ ] **Step 1: Crear el archivo** con este contenido exacto:

```markdown
# CLAUDE.md — Visualizador Web de Centro de Costos

Contenido a presentar en el HTML del visualizador de **Centro de Costos**.
Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de
datos, hosting) — este archivo solo cubre el contenido específico de este
módulo. Ver también [`../CLAUDE.md`](../CLAUDE.md) para el detalle completo
de la estructura de `Centro de Costos.xlsx` que este visualizador consume.

**Estado: borrador de contenido, sin HTML todavía.** Este archivo es el
espacio de trabajo para refinar qué mostrar antes de construir la interfaz.

## Fuente de datos

`Centro de Costos/Excel/Centro de Costos.xlsx`, hojas `Master` (una fila
por documento) y `Detalle` (una fila por ítem de línea). Ver
`../CLAUDE.md` §"Estructura de `Centro de Costos.xlsx`" para el esquema
completo de columnas.

## KPIs (resumen en la parte superior)

- Gasto total (con IVA y sin IVA).
- Gasto por proyecto (los 5-8 proyectos activos).
- Gasto por categoría.
- Cantidad de documentos registrados.
- Documentos pendientes de revisión (celdas rojas / sin N° de documento
  legible) — conteo, no el detalle sensible.

## Tabla dinámica

Una fila por documento (`Master`), expandible a sus ítems (`Detalle`).
Columnas mínimas: N° Ref., Proyecto, Fecha, Proveedor (tag corto, no la
razón social completa — ver punto de saneado más abajo), Categoría, Total
con IVA, Estado. Ordenable por cualquier columna. Búsqueda de texto libre
sobre proveedor/ítem/N° de documento.

## Gráficos

- Barras: gasto por proyecto.
- Dona: gasto por categoría.
- Línea temporal: gasto mensual acumulado.
- Ranking: top 10 proveedores por monto.

## Filtros

- Proyecto.
- Tipo de proyecto (I+D+i, Mantenimiento, Gastos Generales, etc.).
- Categoría.
- Estado (Pagado/Pendiente/etc.).
- Rango de fechas.

## Export saneado sugerido (`data/centro-de-costos.json`)

Agregados por proyecto/categoría/mes/proveedor, más un detalle de
documento con las columnas de la tabla dinámica de arriba. Puntos a
decidir antes de generar el primer export real:

- ¿Se expone la razón social completa del proveedor, o solo el tag corto
  (ej. "Shell") que ya usa `Master`? Recomendado: solo el tag, salvo que el
  sitio quede con control de acceso resuelto (ver punto abierto del
  maestro).
- ¿Se incluyen los documentos marcados en rojo (pendientes de revisión),
  o se excluyen del export hasta que se corrijan?

## Consultor IA (opcional, no obligatorio para la v1)

Si se implementa, debería poder responder preguntas del tipo "¿cuánto
gastamos en UMAG en julio?" o "¿quién es el proveedor con más gasto
acumulado?" contra el export saneado — no contra el Excel fuente.
```

- [ ] **Step 2: Verificar secciones**

Run: `grep -c "^## " "Centro de Costos/Visualizador Web/CLAUDE.md"`
Expected: `7`

- [ ] **Step 3: Verificar el enlace al maestro**

Run: `grep -n "Visualizador%20Web/CLAUDE.md" "Centro de Costos/Visualizador Web/CLAUDE.md"`
Expected: 1 línea de match.

- [ ] **Step 4: Commit**

```bash
git add "Centro de Costos/Visualizador Web/CLAUDE.md"
git commit -m "docs(visualizador-web): borrador de contenido para Centro de Costos

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Contenido borrador — Cotizador Historico

**Files:**
- Create: `Cotizador Historico/Visualizador Web/CLAUDE.md`

**Interfaces:**
- Consumes: enlaza a `../../Visualizador Web/CLAUDE.md` (Task 1).

- [ ] **Step 1: Crear el archivo** con este contenido exacto:

```markdown
# CLAUDE.md — Visualizador Web de Cotizador Historico

Contenido a presentar en el HTML del visualizador de **Cotizador
Historico**. Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de
datos, hosting) — este archivo solo cubre el contenido específico de este
módulo. Ver también [`../CLAUDE.md`](../CLAUDE.md) para el detalle completo
de la lógica de búsqueda difusa y reajuste por UF que este visualizador
expone.

**Estado: borrador de contenido, sin HTML todavía.** Este archivo es el
espacio de trabajo para refinar qué mostrar antes de construir la interfaz.

## Fuente de datos

Misma `Centro de Costos/Excel/Centro de Costos.xlsx` (hojas `Master` +
`Detalle`), vía la lógica de `Sistema/cotizador_historico.py`
(`cargar_items_detalle`, `buscar_items`, reajuste por UF). Este módulo es
de solo lectura — el visualizador tampoco escribe nada.

## Buscador difuso de ítem

Campo de texto libre que reproduce `buscar_items`: búsqueda difusa contra
`Nombre Ítem` y `Descripción`. Si no hay match, mostrar las sugerencias de
baja similitud igual que hace el driver hoy (`status`/`consultar`).

## Vista de resultado

Para el ítem consultado:

- Lista de compras individuales encontradas: fecha, proyecto, proveedor,
  precio unitario original, precio ajustado por UF (sin IVA y con IVA
  usando la tasa real del documento).
- Promedio de los precios ajustados.
- Rango (mínimo-máximo) de precio ajustado sin IVA.

## Gráfico

Línea de evolución: precio ajustado por UF en el tiempo, un punto por
compra encontrada para el ítem consultado (eje X = fecha de la compra, eje
Y = precio ajustado a la fecha de hoy).

## Filtros

- Proyecto de origen de la compra.
- Rango de fechas de la compra.

## Export saneado sugerido (`data/cotizador-historico.json`)

Snapshot de ítems indexados: nombre, descripción, categoría, precio
unitario sin IVA, fecha de la compra, proyecto, y el valor de UF ya
resuelto para esa fecha histórica (evita depender de la API de
`mindicador.cl` en vivo desde el navegador). El reajuste a "hoy" se
recalcula client-side contra la UF del día, que si se requiere en vivo
necesita su propia llamada — a decidir si se pide en el momento (requiere
que el visualizador tenga acceso a internet más allá de servir el HTML
estático) o si se muestra "ajustado a la fecha del último export" con una
fecha visible de corte.

## Consultor IA (opcional, no obligatorio para la v1)

Si se implementa, debería responder preguntas del tipo "¿cuánto debería
costar hoy un taladro?" contra el export saneado, replicando la lógica de
`consultar_item` pero sirviéndola desde datos ya exportados.
```

- [ ] **Step 2: Verificar secciones**

Run: `grep -c "^## " "Cotizador Historico/Visualizador Web/CLAUDE.md"`
Expected: `7`

- [ ] **Step 3: Verificar el enlace al maestro**

Run: `grep -n "Visualizador%20Web/CLAUDE.md" "Cotizador Historico/Visualizador Web/CLAUDE.md"`
Expected: 1 línea de match.

- [ ] **Step 4: Commit**

```bash
git add "Cotizador Historico/Visualizador Web/CLAUDE.md"
git commit -m "docs(visualizador-web): borrador de contenido para Cotizador Historico

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Placeholder — Flujo de Caja

**Files:**
- Create: `Flujo de Caja/Visualizador Web/CLAUDE.md`

**Interfaces:**
- Consumes: enlaza a `../../Visualizador Web/CLAUDE.md` (Task 1).

- [ ] **Step 1: Crear el archivo** con este contenido exacto:

```markdown
# CLAUDE.md — Visualizador Web de Flujo de Caja

**Placeholder.** El módulo base `Flujo de Caja` todavía no está iniciado
(ver tabla de módulos en el `CLAUDE.md` raíz) — no existe script, ni
`Sistema/`, ni esquema de datos definido todavía. Este archivo solo reserva
el espacio y la estructura para cuando el módulo se implemente.

Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de
datos, hosting) — aplica igual una vez este módulo exista.

## A completar cuando el módulo Flujo de Caja se implemente

- **Fuente de datos**: qué archivo/hoja consume este visualizador (aún no
  definido — depende del diseño del módulo Flujo de Caja).
- **KPIs**: pendiente.
- **Tabla dinámica**: pendiente.
- **Gráficos**: pendiente.
- **Filtros**: pendiente.
- **Export saneado sugerido**: pendiente.
- **Consultor IA (opcional)**: pendiente.

No construir ningún HTML para este módulo hasta que `Flujo de Caja/
CLAUDE.md` exista y documente su esquema de datos real.
```

- [ ] **Step 2: Verificar el enlace al maestro**

Run: `grep -n "Visualizador%20Web/CLAUDE.md" "Flujo de Caja/Visualizador Web/CLAUDE.md"`
Expected: 1 línea de match.

- [ ] **Step 3: Commit**

```bash
git add "Flujo de Caja/Visualizador Web/CLAUDE.md"
git commit -m "docs(visualizador-web): placeholder de contenido para Flujo de Caja

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
