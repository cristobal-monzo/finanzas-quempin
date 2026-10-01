# Atributos del Cotizador Histórico: qué es un producto, de qué está hecho y cuánto mide

**Fecha:** 2026-09-22 · **Pedido del usuario:** rehacer la categorización, la
normalización y la búsqueda de materiales, con el principio:

> Un producto no debe clasificarse únicamente por su forma o dimensiones. Debe
> identificarse primero qué producto es, de qué material está fabricado y
> posteriormente cuáles son sus características dimensionales y técnicas.

Este documento es el análisis del sistema anterior, las decisiones tomadas y
las mediciones antes/después. El detalle operativo (qué archivo se edita para
qué) vive en [`../../../CLAUDE.md`](../../../CLAUDE.md).

---

## 1. Qué estaba roto (medido sobre las 1.484 compras reales)

El sistema del 2026-09-08 clasificaba por **una palabra y una medida**: la
regla que calzaba definía categoría/subcategoría/familia, un material se
elegía de una lista plana y la medida era **una sola cadena sin rol**.

| Problema | Ejemplo real | Efecto |
|---|---|---|
| El material podía ser un término de producto | `policarbonato` era una palabra que llevaba a la familia "Plancha" | La plancha de policarbonato quedaba **sin material** y dentro de "Perfilería y **Maderas**" |
| Materiales ausentes del diccionario | zincalum, PTFE, grafito, EPDM, MDF, latón, HSS, fibra cerámica | 156 productos sin material donde el material define la hoja |
| Normas leídas como material | `ASTM` era alias de "Acero Negro" | Una plancha `ASTM A-36` (acero al carbono) quedaba como acero negro |
| Material sin ROL | "Disco de corte **para** acero inoxidable", "Mazo de goma **con mango de** acero", "Visor policarbonato **c/marco** aluminio" | El disco era "de inoxidable", el mazo "de acero" y el visor "de aluminio" |
| Una sola medida, sin rol | `0,7 x 812 x 3660 mm` → `"0.7x812x3660mm"` | No se podía filtrar por espesor, ni comparar anchos, ni saber qué era cada número |
| La medida leída era la que no identificaba | `PEX-A Aqualine 32 barra 5.8mts` → `5800mm` (el largo) | Las barras PEX de **16, 20 y 32 mm compartían hoja**: se promediaban entre sí |
| Escuadría perdida | `Pino seco cepillado 2x6 3,2 mt` → `3200mm` | El 2x6 y el 1x6 compartían hoja |
| Un número de catálogo leído como medida | `Hilo tuerca galv tupy 04 3/4` | Se leía `4.3/4"` (cuatro y tres cuartos) en vez de `3/4"` |
| La palabra secundaria le ganaba a la principal | `Kit bomba DAB … unión 1.1/4"` → **Unión**; `Llave de cadena` → **Cadena**; `Bolsas basura c/amarra` → **Amarra**; `Adaptador Schuko` → fitting de piping | El producto quedaba en otra familia |
| El buscador descartaba todo número que no fuera pulgada | `plancha 0.7`, `policarbonato 812`, `electrodo 6011` | Se buscaba solo por la palabra; y `0,7` se partía en "0" y "7" |
| Sin grados ni especificaciones | `SS316`, `AISI 304L`, `SCH 10S`, `PN16`, `NPT`, `G-2` | No se podía buscar ni filtrar por ellos |

## 2. Qué se hizo

### 2.1 Tres niveles independientes, más atributos

```
categoría          Planchas y Perfiles     (la carpeta del dashboard)
familia            Planchas                (el nivel que decide qué filtros se ofrecen)
tipo               Plancha                 (QUÉ es)
material           Policarbonato           (DE QUÉ está hecho)  + familia de material y grado
terminación        Transparente
dimensiones        espesor 0,7 mm · ancho 812 mm · largo 3660 mm      (cada una con su ROL)
especificaciones   schedule, presión, conexión, rosca, norma, grado…
```

El motor de atributos (`Sistema/atributos.py`) es nuevo; los datos
(`Sistema/catalogo_atributos.py`) siguen el mismo reparto motor/datos que ya
tenían la taxonomía y el buscador.

### 2.2 Decisiones que valen la pena recordar

1. **Ninguna palabra de material es término de una regla de producto.** Es la
   causa raíz del caso del policarbonato. La regla está escrita en el
   encabezado de `catalogo_taxonomia.py`.
2. **El material tiene rol**: principal, *componente* (`c/marco aluminio`),
   *aplicación* (`para acero inoxidable`) y *sistema* de tubería (un terminal
   de latón DZR **para PEX** es de latón, y se guarda en la carpeta PEX).
3. **El sustantivo principal manda.** En español el núcleo va primero, así que
   el puntaje suma hasta 12 puntos por estar al principio del nombre y resta
   25 por venir después de "con", "incluye" o "porta". Un término que
   *contiene* al ganador lo reemplaza ("Válvula" + "Válvula bola" → Válvula de
   Bola).
4. **El significado de un número depende de la familia**: hay un esquema por
   familia (`lamina`, `perfil`, `madera`, `tuberia`, `fitting`, `perno`,
   `tornillo`, `remache`, `disco`, `electrodo`, `cinta`, `aislación`,
   `instrumento`). El mismo "40x2" es un perfil de 40 mm de lado y 2 de
   espesor; "2x6" es una escuadría en pulgadas; "0,7 x 812 x 3660" es
   espesor × ancho × largo.
5. **Un entero sin unidad se lee según el sistema**: en PEX/PPR/PVC son
   milímetros ("PEX 32"), en cobre/acero son pulgadas nominales ("Copla cobre
   2"). Un 90 sin unidad en un codo son grados; con unidad, 90 mm.
6. **Se conserva la única pasarela métrico↔pulgada que existía**: DN (DN50 =
   2"). No se divide por 25,4. Se agregaron dos equivalencias **de familia**:
   discos abrasivos (4.1/2" = 115 mm) y electrodos (1/8" = 3,2 mm).
7. **Confianza por atributo** y motivo de revisión. Nada se fuerza: una
   palabra que ninguna tabla explica queda como "sin interpretar" y se reporta
   en `driver.py atributos` con una sugerencia (¿abreviatura?, ¿error de
   tipeo?, ¿marca?).
8. **El buscador indexa atributos, no un saco de palabras**: un campo por
   tipo, material, dimensiones, especificaciones, terminación, aplicación,
   marca y texto, con el peso en el orden que pidió el usuario.

### 2.3 Lo que NO se hizo, a propósito

- **No se reemplazó el motor de búsqueda** (ranking por cobertura + IDF +
  peso de campo + multiplicador de medida, 2026-09-16): funcionaba. Se le
  agregaron campos y se le enseñó a leer números, grados y especificaciones.
- **No se convierte mm ↔ pulgada aritméticamente** (ver decisión 6).
- **No se oculta nada.** Sigue valiendo la regla de oro: lo que no se puede
  medir queda marcado "(sin medida)" y visible.

## 3. Medición

Dos instrumentos nuevos, ambos **independientes del sistema que miden**:

- `Sistema/referencia_atributos.py`: 203 productos reales etiquetados a mano
  (familia, tipo, material, dimensiones con su rol).
- `Sistema/evaluacion.py`: 110 consultas cuya relevancia es un predicado
  sobre el **texto crudo** del producto, no sobre la clasificación de ninguna
  versión, y agrupadas por producto (no por hoja).

```
py -3.14 ".claude/skills/Cotizador_Historico/driver.py" evaluacion [--detalle]
```

| Métrica | Antes (motor 2026-09-16) | Ahora |
|---|---|---|
| Material correcto | 0,824 | **1,000** |
| Dimensiones: valores correctos | 0,644 | **1,000** |
| Dimensiones: **con su rol** | 0,000 | **1,000** |
| Categoría correcta (casos en disputa) | 0,235 | **1,000** |
| Búsqueda P@1 | 0,764 | **0,982** |
| Búsqueda P@5 | 0,287 | **0,342** |
| Búsqueda P@5 normalizada | 0,762 | **0,895** |
| Búsqueda Success@5 | 0,882 | **1,000** |
| Búsqueda MRR | 0,813 | **0,991** |
| Compras en "Sin Clasificar" | 20 | **0** |
| Sin material donde el material define la hoja | 156 | **118** |
| Piping en "Otros materiales" | 29 | **24** |
| Clasificaciones ambiguas | 17 | **11** |
| Casos marcados para revisión (confianza < 0,7) | — | **4** |

23 de las 110 consultas pasaron a acertar en el primer lugar y **ninguna
empeoró**. El benchmark de 48 consultas del 2026-09-16 (que juzga con la
clasificación del propio sistema) también subió: P@5 normalizada 0,935 →
0,983, con Success@5 y MRR en 1,000.

**Cuidado al leer estos números**: la referencia de 203 productos se escribió
mirando el catálogo *antes* de implementar, pero se iteró contra ella, así que
es un set de desarrollo, no una muestra ciega. Los conteos sobre las 1.484
compras (sin clasificar, sin material, ambiguas) sí son independientes.

## 4. Casos que quedaron abiertos

- **118 productos sin material** donde el material define la hoja: casi todos
  son textos que de verdad no lo dicen ("Válvula bola italiana p/estopa
  Enolgas 2 plg"). Se informan en `driver.py atributos`, no se inventan.
- **11 clasificaciones ambiguas** (dos categorías a menos de 10 puntos), cada
  una con su alternativa anotada: "Marcador de pintura" (¿Lápiz o Pintura?),
  "Codo radiador" (¿Codo o Radiador?), "Niple tuerca" (¿Niple o Tuerca?).
- **4 productos con confianza < 0,7**, todos por decir dos materiales
  ("U Amer Aj Br galvanizada": ¿bronce o galvanizada?).
- **120 palabras sin interpretar** en el catálogo, la mayoría marcas
  (Suvinil, KWB, Uyustools, Temflex) que se pueden agregar a
  `catalogo_busqueda.MARCAS`.
- **Pesos y equivalencias por familia**: hoy discos y electrodos tienen
  equivalencia mm↔pulgada. Si aparecen otras (brocas, sierras copa), se
  agregan a `catalogo_atributos.py`.
