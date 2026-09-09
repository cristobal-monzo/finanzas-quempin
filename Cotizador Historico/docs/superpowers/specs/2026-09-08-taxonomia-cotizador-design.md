# Reestructuración de la categorización del Cotizador Histórico

**Fecha:** 2026-09-08
**Estado:** implementado
**Pedido del usuario:** "mejorar el flujo de trabajo, sobre todo la
categorización del cotizador histórico. Hay elementos que son de 1.1/4" y
que se indican como si fueran de 1/4"... quiero una reestructuración bien
pensada y que tenga sentido, revisando cada ítem."

## 1. El problema, medido

El diagnóstico se hizo portando el clasificador JavaScript de
`Visualizador Web/template.html` a Python y corriéndolo sobre las **1193
compras reales** del catálogo (snapshot del 07-09-2026). No son estimaciones:

| Síntoma | Medición |
|---|---|
| Compras ocultas del dashboard sin aviso | **136 (11,4%)** |
| Compras en el cajón de sastre "Otros / Servicios" | **287 (24,1%)** |
| Hojas (unidad de comparación) con una sola compra | **77%** |
| Subcategorías distintas, muchas de 1 ítem | **248** (123 con un solo ítem) |
| Medidas leídas correctamente (banco de 55 casos reales) | **15 / 55** |

### 1.1 La medida mal leída (el caso que reportó el usuario)

`PATRON_MEDIDA` no reconocía la fracción mixta chilena. Sobre datos reales:

- `Codo SO BR (05) 1.1/4 plg` → leía `1/4` (se perdía la pulgada entera)
- `Niple galvanizado ISO BSP-BSP 08cm (09) 1.1/2 plg` → leía `08cm`, que es
  el **largo**, no el diámetro
- `Kit bomba DAB ... VA 65/180 X, unión 1.1/4"` → leía `65/180`, que es el
  **modelo** de la bomba
- `Caldera Anwo ... NB2-40/42-LPG` → leía `40/42`, que es el **código**
- `Copla SO cobre (04) 1 plg` → no leía nada: `plg`, la abreviatura más usada
  del catálogo, no estaba en el patrón. Ese ítem quedaba invisible.

**Consecuencia en plata**, verificada sobre el índice real:

| Hoja actual | Promedio que mostraba | Lo que realmente mezclaba |
|---|---|---|
| `Valvula bola` | $38.152 | una de 2" ($48.349) con una de 1" ($7.561) |
| `Copla de Bronce 1/2` | $3.395 | una copla de 1/2" ($1.934) con una reducción 1.1/2x1.1/4" ($6.317) |
| `Punta negra 10cm` | $2.385 | 3/4" ($879) con 2.1/2" ($8.135) |
| `Bushing de Galvanizado 1/4` | $1.824 | tres variantes de 1.1/4", ninguna de 1/4" |

### 1.2 La clasificación por substring

`contieneAlguna` buscaba la palabra clave como **substring**, sin límite de
palabra. Errores reales encontrados:

- `Buzo desechable Steelgen Plus L blanco` → Piping, porque "S-**tee**-lgen"
  contiene "tee".
- `Gasolina 95 octanos... dado que la boleta...` → Herramienta manual, porque
  "**dado** que" contiene "dado".
- `Soplete gas ... s/manguera s/abrazadera` → Válvula, por "abrazadera", que
  en el texto viene **negada** ("sin abrazadera").
- `Pasaje interurbano Tur Bus | Terminal 20998...` → Piping, por "terminal".
- `Lija al agua` → Alimentación, por el hack `'agua '`.
- `Quemador Riello 40 G10 petróleo` → Transporte, por "petróleo".

### 1.3 Estructura

- **El material era la categoría** (`Piping Cobre`, `Piping Bronce`, …), así
  que los 5 materiales conocidos fragmentaban el árbol y los que no estaban
  en la lista (PVC, PEX, acero negro, y la abreviatura "BR" que el catálogo
  usa todo el tiempo) dejaban **76 fittings sin categoría y ocultos**.
- **La subcategoría salía de "la primera palabra del nombre"**, lo que
  producía carpetas como `Compras`, `Redes` (por "Red Bull"), `Muffines`,
  `Bushinges de Galvanizado`, y separaba `Valvulas` de `Válvulas`.
- **El 27,5% del catálogo eran peajes, combustible y comida** compitiendo en
  el mismo árbol con los productos que sí se cotizan.
- **Todo esto vivía en JavaScript dentro de `template.html`**, duplicado en
  Chile y Perú, **ya divergente** (Perú nunca recibió la categoría
  Instrumentación agregada el 2026-08-31), sin ningún test, y **la consulta
  por consola no lo usaba**: `consultar "codo"` promediaba de un saque codos
  de 1/2" y de 2".

## 2. Diseño

### 2.1 Una sola fuente de verdad, en Python

`Visualizador Web/template.html` (JS)  →  `Sistema/taxonomia.py` (motor) +
`Sistema/catalogo_taxonomia.py` (datos).

Lo consumen los dos caminos: `consultar_item` (consola y conversación) y
`build_visualizador.py` (dashboard de Chile y de Perú). El template pasó de
~290 líneas de listas de palabras clave a un adaptador de 32 que lee lo ya
calculado. Se eliminó la divergencia Chile/Perú por construcción.

### 2.2 Cuatro etapas independientes

1. **`normalizar` / `raiz`** — minúsculas, sin tildes, sin plural, sin
   palabras vacías. `guantes`/`guante`, `Valvula`/`Válvula` y
   `tapón para oído`/`tapón oído` colapsan a la misma forma.
2. **`parsear_medidas`** — gramática de medidas (§2.3).
3. **`clasificar`** — categoría/subcategoría/familia por catálogo de reglas
   con score (§2.4).
4. **`clave_hoja`** — `familia + material + medida`: la unidad de
   comparación de precios.

### 2.3 Gramática de medidas

```
medida    := componente (x componente)* unidad?
componente:= mixta | fracción | decimal | entero
mixta     := entero [.-· ] fracción        (1.1/4, 1-1/4, 1 1/4)
unidad    := " | '' | plg | pulg | pulgadas | pg | in | mm | cm | m | mt
```

Decisiones, cada una respaldada por un caso real:

- **Una fracción es siempre pulgada**, aunque el grupo traiga unidad métrica
  al final: `2.1/2x10cm` es 2.1/2" de diámetro por 10 cm de largo.
- **La pulgada gana sobre el métrico** cuando conviven: en este catálogo el
  diámetro nominal va en pulgadas y el largo en cm/mm.
- **Las compuestas se conservan enteras**: un bushing `1.1/2x1.1/4"` no es
  el mismo producto que uno `1.1/2x1"`. Si los componentes son iguales se
  muestra uno solo (`1/2x1/2` → `1/2"`).
- **Denominadores válidos**: 2, 3, 4, 8, 16, 32, 64. Cualquier otro es un
  código de modelo (`65/180`, `40/42`, `1.50/1.70`).
- **El texto administrativo se corta**: todo lo que sigue a `cod.`,
  `factura`, `doc.`, más los códigos de catálogo entre paréntesis (`(04)`),
  los folios y los códigos alfanuméricos (`SS316`, `A234`, `VFB50-A`).
- **Las magnitudes que no son longitud no son medidas**: V, W, kg, ml, lt,
  psi, bar, octanos, unidades.
- **Un entero pelado no es una medida**, salvo en las familias que comparan
  por medida (piping, fijaciones, válvulas), donde el catálogo escribe el
  diámetro sin unidad (`Copla cobre 2 SO`). Ahí se acepta, con tres guardas
  que salieron de medirlo: no toma **ángulos** de fitting (`Codo 90`), no
  toma la **cantidad** de un envase (`Pack 2 curva`), y no toma el extremo
  de un **rango métrico** (`abrazadera 8-12mm`). El ángulo tampoco puede ser
  la parte entera de una fracción mixta: `Codo BR 90 3/4` es un codo de 90°
  y 3/4", no uno de noventa y tres cuartos.
- **Dos convenciones métricas propias del catálogo**: `DN50` (diámetro
  nominal ISO) y el `032` con cero a la izquierda del PPR, ambos milímetros.

Resultado sobre el banco de 55 casos reales: **55/55** (antes 15/55).

### 2.4 Catálogo de reglas

Cada regla es `(términos, categoría, subcategoría, familia, prioridad)`:

- El match es **por palabra completa** sobre la raíz, nunca por substring.
- Un término **negado** (`sin`, `s/`, `no`) no activa la regla.
- El score es `100 + prioridad + 30 si matchea en el nombre + 10 por palabra
  del término`. Así una frase específica le gana a una palabra genérica, y
  el nombre del ítem le gana a la descripción sin necesidad de ordenar la
  lista a mano (el sistema anterior dependía del orden de los `if`).
- La **familia es explícita**, nunca "la primera palabra del nombre".

### 2.5 El árbol nuevo

**21 categorías**, con el material como **faceta** (entra a la hoja y al
filtro) en vez de como categoría:

| Productos cotizables | Gastos de operación |
|---|---|
| Piping y Fittings · Válvulas y Control de Flujo · Instrumentación y Medición · Bombas y Equipos Hidráulicos · Calefacción y Combustión · Aislación y Refractarios · Soldadura y Gases · Abrasivos y Corte · Fijaciones · Sellado y Lubricantes · Herramientas Manuales · Herramientas Eléctricas · Materiales Eléctricos · Pinturas y Recubrimientos · Perfilería y Maderas · Seguridad Industrial (EPP) · Aseo y Oficina | Alimentación · Transporte y Logística · Arriendos y Servicios |

Más `Sin Clasificar`, que **no es un cajón de sastre sino una cola de
trabajo**: sale como KPI en el dashboard y como lista en `driver.py
categorias`, para agregarle una regla al catálogo.

Por qué el material dejó de ser categoría:

1. Con 5 materiales × 12 tipos de fitting, cada rama quedaba flaca y los
   materiales que faltaban (PVC, PEX, acero negro) no tenían dónde caer.
2. La pregunta real del negocio es "cuánto cuesta un codo de 1/2" en cada
   material", que ahora se responde en una pantalla.
3. La separación que importa se conserva **donde importa**: la hoja sigue
   siendo `familia + material + medida`, así que un codo de cobre de 1/2"
   nunca se promedia con uno de bronce ni con uno de 2".

El material entra a la hoja **solo en las categorías donde define el
producto** (`CATEGORIAS_CON_MATERIAL`: piping, válvulas, fijaciones,
perfilería). Fuera de ahí se sigue detectando y sirve de filtro, pero no
parte la hoja: sin esta restricción, un "Guante de plástico" quedaba
separado de "Guante" y un visor con marco de aluminio se volvía un producto
de aluminio. Por el mismo motivo `negro`/`negra` no son palabras de
material — en este catálogo son colores ("Polerón térmico negro"); el acero
negro se reconoce por la frase completa o por su norma (ASTM, SCH40, ERW).

Por qué se separan los gastos: el precio unitario promedio de un peaje o de
un almuerzo no significa nada (dispersión medida de 101x y 78x
respectivamente, contra ~1x en las hojas de producto). Quedan visibles y
navegables, marcados `cotizable=False`, fuera de los KPIs de catálogo.

### 2.6 Regla de oro: nada se oculta

El sistema anterior **descartaba del dashboard** cualquier ítem al que no
pudiera extraerle medida o material. Ahora un ítem sin medida cae en una
hoja marcada `(sin medida)`, sigue visible y contado, y aparece en la
auditoría. Se prefiere un dato incompleto y visible antes que un dato
completo e invisible.

## 3. Resultado medido

| Métrica | Antes | Después |
|---|---|---|
| Compras ocultas | 136 (11,4%) | **0** |
| Cajón de sastre / sin clasificar | 287 (24,1%) | **1 (0,1%)** |
| Medidas detectadas | 385 | **475** |
| Medidas correctas (banco de 55 casos) | 15/55 | **55/55** |
| Compras con al menos otra con que compararse | 60% | **72%** |
| Líneas de taxonomía duplicadas en JS (CL+PE) | 572 | **0** |
| Tests de taxonomía | 0 | **57** |

## 4. Flujo de trabajo

- `driver.py categorias` — auditoría: distribución, cola de "Sin
  Clasificar", ítems que requieren medida y no la tienen, y cobertura de
  agrupación. **No usa la red** (no pide UF): revisar categorías no necesita
  reajustar precios.
- `driver.py categorias --detalle "Piping"` — las hojas de una categoría.
- `driver.py consultar "<texto>"` — ahora agrupa por hoja, y si el texto
  trae una medida (`codo bronce 1.1/4`) filtra a esa medida y dice cuántas
  compras de otra medida quedaron fuera.
- Mantención: se edita `Sistema/catalogo_taxonomia.py`, se corre
  `py -3.14 -m pytest` y `driver.py categorias`, y se compara que no se haya
  movido nada que ya estaba bien.

## 5. Alternativas descartadas

- **Arreglar solo el regex de medidas.** Resolvía el caso reportado pero
  dejaba en pie el 24% de cajón de sastre, el 11% de ítems ocultos y la
  divergencia Chile/Perú.
- **Mantener la taxonomía en JavaScript.** Es el único lenguaje donde el
  repo no puede testear (las 7 suites son pytest), y obliga a duplicarla por
  país.
- **Categorizar con la columna `Categoría Ítem` del Excel.** Tiene 16
  valores con duplicados por tilde (`Ferreteria`/`Ferretería`,
  `Alimentacion`/`Alimentación`) y no distingue medidas ni materiales.
  Se sigue leyendo, pero ya no alimenta el filtro del dashboard.
- **Un LLM clasificando cada ítem.** Se descartó por costo y por
  reproducibilidad: la auditoría necesita que dos corridas den lo mismo.

## 6. Pendiente (fase 2)

- **Especificación por familia según la unidad que la define**: un estanque
  se compara por litros, una caldera por kW, un guante por presentación
  (unidad vs pack de 10 pares). Hoy esas hojas quedan con dispersión alta
  (Estanque 20x, Guante 15x) y la auditoría las marca. La gramática
  dimensional actual no las cubre porque su spec no es una longitud.
- **Presentación/envase en la hoja** (unidad, caja de 100, pack de 10).
