# Actualizar un módulo y dejar su tablero publicado al día

Procedimiento común de los tres skills de registro cuando terminan en un
tablero publicado: `/Registro_Centro_de_Costos`,
`/Registro_Analisis_Financiero` y `/Cotizador_Historico`. Vive acá una sola
vez; cada `SKILL.md` agrega solo lo propio de su módulo.

## Por qué los skills se fusionaron (2026-10-13)

Hasta el 2026-10-13 cada módulo tenía dos o tres skills con alcances que se
pisaban: `/Actualizar_CC` (registrar + publicar), `/Actualizar_Base_de_Datos`
(registrar sin publicar) y `/Registro_Centro_de_Costos` (registrar, y
publicar «era tuyo»); lo mismo con `/Actualizar_AF` y `/Actualizar_Cotizador`.
Eran el mismo pipeline con un paso más o un paso menos, y había que elegir
entre nombres casi iguales. El usuario pidió fusionarlos: ahora **el skill de
registro de cada módulo publica su tablero al terminar**, y «sin publicar»
es una instrucción, no otro skill.

| Antes | Ahora |
|---|---|
| `/Actualizar_CC` | `/Registro_Centro_de_Costos` (publica al terminar) |
| `/Actualizar_Base_de_Datos` | `/Registro_Centro_de_Costos`, diciendo «sin publicar» |
| `/Actualizar_AF` | `/Registro_Analisis_Financiero` (publica al terminar) |
| `/Actualizar_Cotizador` | `/Cotizador_Historico visualizador` (publica al terminar) |

Si el usuario escribe uno de los nombres antiguos, es el skill nuevo de la
tabla: dilo en una línea y sigue.

## Los cuatro pasos

1. **`status`** — solo lectura. Cada skill indica qué mira.

2. **`run`** (o `visualizador` en el Cotizador, que no escribe datos) — la
   ejecución real, cuando corresponda.

3. **Publicar en GitHub Pages** cuando corresponda:
   - Si el paso 2 escribió algo o regeneró el tablero, publicar es
     **obligatorio**. Nunca termines con los datos al día y el link viejo.
   - Si el usuario pidió un refresco explícito (corrigió algo a mano en el
     Excel, o solo cambió `template.html`), regenerar el visualizador y
     publicar igual.
   - **Si el usuario dijo «sin publicar»** («solo el Excel», «después publico
     todo junto»; lo que antes era `/Actualizar_Base_de_Datos`), no publiques
     y termina diciendo que el tablero publicado sigue desactualizado.
   - Si `status` no mostró nada pendiente y no hubo pedido de refresco, no
     hay nada que publicar: dilo en una línea y termina ahí.

   La receta está en
   [`Visualizador Web/CLAUDE.md`](../Visualizador%20Web/CLAUDE.md) § Hosting
   (el de la **raíz** del repo, no el del módulo): `publicar.py` con la clave
   del módulo (`cc`, `af` o `cot`), y después commit y push en gh-pages. No se
   copia el `index.html` a mano: el del AF lleva sus reportes PDF cifrados
   aparte.

4. **Reportar en una respuesta corta**: qué cambió, si se publicó o no hacía
   falta, y el link (el mismo de siempre, la URL es estructural y fija).

## Cuándo no aplica

**Si el usuario pide actualizar TODO** («actualiza las finanzas», «deja todo
al día»), usa `/Actualizar_Finanzas` (raíz del repo): cubre los cuatro
módulos y los cuatro tableros, y cierra con la bandeja de pendientes.
