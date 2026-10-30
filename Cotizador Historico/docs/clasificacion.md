# Cotizador Histórico: clasificación y atributos

Detalle de referencia: léelo solo al tocar esto. Las reglas vigentes están en `../CLAUDE.md`.

Reestructurada dos veces: el **2026-09-08** (categoría > subcategoría > hoja,
con las medidas bien leídas) y el **2026-09-22**, cuando el material, las
dimensiones y las especificaciones pasaron a ser **atributos independientes**.
El pedido del usuario de esa segunda vuelta es el principio que ordena todo:

> Un producto no debe clasificarse únicamente por su forma o dimensiones. Debe
> identificarse primero **qué** producto es, **de qué** material está fabricado
> y posteriormente cuáles son sus características dimensionales y técnicas.

Diseño completo, con el análisis de lo que estaba roto y las mediciones, en
[`specs/2026-09-22-atributos-cotizador-design.md`](specs/2026-09-22-atributos-cotizador-design.md)
(el de la primera vuelta, en
[`2026-09-08-taxonomia-cotizador-design.md`](specs/2026-09-08-taxonomia-cotizador-design.md)).

**Vive en Python, no en el HTML.** Dos motores, cada uno con sus datos al lado:

| Archivo | Qué hace | Qué se edita ahí |
|---|---|---|
| `Sistema/taxonomia.py` | motor: medidas, clasificación, hoja | casi nunca |
| `Sistema/catalogo_taxonomia.py` | datos: categorías y qué palabras llevan a cada **tipo** | una regla de producto nueva |
| `Sistema/atributos.py` | motor: material con su rol, especificaciones, terminación, confianza | casi nunca |
| `Sistema/dimensiones.py` | motor: cuánto mide y **qué es cada número** (un esquema por familia) | casi nunca |
| `Sistema/catalogo_atributos.py` | datos: **materiales**, abreviaturas, terminaciones, esquemas de medida, facetas | un material, una abreviatura o un filtro nuevo |
| `Sistema/presentacion.py` | motor: cómo se **escribe** lo que ya se entendió (unidad práctica, una sola ortografía por nombre) | casi nunca |
| `Sistema/catalogo_presentacion.py` | datos: siglas técnicas con su escritura correcta | una sigla nueva que salga en mayúsculas a medias |

Los usan por igual `consultar_item` (consola y conversación) y los dos
`build_visualizador.py` (Chile y Perú). Antes de 2026-09-08 esto vivía en
JavaScript dentro de `Visualizador Web/template.html`, duplicado por país y
**ya divergente** (Perú nunca recibió la categoría Instrumentación agregada el
2026-08-31), sin tests, y la consulta por consola no lo usaba.

**La ficha de un producto** (lo que devuelve `taxonomia.clasificar`):

```
Plancha policarbonato transparente 0,7 x 812 x 3660 mm

  categoría        Planchas y Perfiles      (la carpeta del dashboard)
  familia          Planchas                 (decide qué filtros se ofrecen)
  tipo             Plancha                  (QUÉ es)
  material         Policarbonato            (DE QUÉ está hecho) · familia: Plásticos
  terminación      Transparente
  dimensiones      espesor 0,7 mm · ancho 812 mm · largo 3660 mm   (cada una con su ROL)
  especificaciones (schedule, presión, conexión, rosca, norma, grado...)
  confianza        0,85   ·   revisar: no
```

En la ficha, `familia` es el **tipo** (se conserva el nombre de esa clave
desde 2026-09-08 porque la hoja, el dashboard y el benchmark la usan) y
`familia_producto` es el nivel de arriba.

**Seis reglas que conviene no reaprender a golpes:**

1. **Ninguna palabra de material es término de una regla de producto.** Cuando
   `policarbonato` era un término que llevaba a "Plancha", una plancha de
   policarbonato quedaba **sin material** y dentro de "Perfilería y Maderas",
   junto al pino.
2. **El material tiene ROL**: principal, *componente* ("mazo de goma **con
   mango de** acero" es de goma), *aplicación* ("disco de corte **para** acero
   inoxidable" no es de inoxidable) y *sistema* de tubería (un terminal de
   latón DZR **para PEX** es de latón, y va en la carpeta PEX).
3. **Manda el sustantivo principal.** En español el núcleo del sintagma va
   primero: el puntaje suma hasta 12 puntos por estar al principio del nombre
   y resta 25 por venir después de "con", "incluye" o "porta". Sin eso, "Kit
   bomba DAB ... unión 1.1/4"" era una Unión y "Bolsas basura c/amarra", una
   Amarra.
4. **El significado de un número depende de la familia.** "40x2" es un perfil
   de 40 mm de lado y 2 de espesor; "2x6", una escuadría de pino en pulgadas;
   "0,7 x 812 x 3660", espesor × ancho × largo. Los esquemas están en
   `catalogo_atributos.ESQUEMA_POR_TIPO`.
5. **Un entero sin unidad se lee según el sistema**: en PEX/PPR/PVC son
   milímetros ("PEX 32"); en cobre o acero, pulgadas nominales ("Copla cobre
   2"). Las tres barras PEX (16, 20 y 32 mm) compartían hoja porque la única
   medida que se leía era el largo de la barra.
6. **Nada se fuerza.** Lo que ninguna tabla explica queda como atributo sin
   interpretar, con su confianza y su motivo, y se reporta en `driver.py
   atributos` con una sugerencia (¿abreviatura?, ¿error de tipeo?, ¿marca?)
   para que una persona decida.

**Cinco etapas** (testeadas por separado en `Sistema/tests/test_taxonomia.py`
y `Sistema/tests/test_atributos.py`):

1. `normalizar`/`raiz` — sin tildes, sin plural, sin palabras vacías, para
   que `guantes`/`guante` y `Valvula`/`Válvula` sean lo mismo.
2. `parsear_medidas` — gramática de medidas. Reconoce la fracción mixta
   chilena en sus tres escrituras (`1.1/4`, `1-1/4`, `1 1/4`), la
   abreviatura `plg`, las compuestas (`1.1/2x1.1/4`), y **rechaza** lo que
   no es medida: modelos (`VA 65/180`), códigos (`NB2-40/42`), magnitudes
   que no son longitud (220V, 280ml, 25kg) y ángulos de fitting
   (`Codo 90 3/4` es de 3/4", no de noventa y tres cuartos).
3. `clasificar` — categoría/familia/**tipo** con un catálogo de reglas. El
   match es **por palabra completa**, nunca substring: así "S-tee-lgen" no
   activa "tee" y "dado que" no activa "dado" (dos errores reales del sistema
   anterior). Un término negado (`sin`, `s/`) no activa su regla, y un
   sustantivo genérico se resuelve por contexto (`DESAMBIGUACION`: un
   "adaptador" con "schuko" es eléctrico; con "broca", el porta sierra de un
   taladro).
4. `atributos` — material con su rol y su grado, dimensiones por esquema de
   familia, especificaciones técnicas (SCH, PN, NPT, HI-HI, tipo de pared,
   norma, grado, corriente), terminación, color y la **confianza** de cada
   dato.
5. `clave_hoja` — `tipo + material (+ grado, + clase de pared) + medida`. Dos
   compras solo se promedian si comparten hoja: **una cañería de cobre de 1/2
   nunca se promedia con una de 2**, ni una tipo L con una tipo K.

**Cuatro afinamientos pedidos el 2026-09-09**, todos en
`catalogo_taxonomia.py`:

1. **Los equipos se identifican por su modelo.** En las categorías de
   `CATEGORIAS_CON_MODELO` (bombas, calefacción, herramientas eléctricas,
   instrumentación, soldadura) la hoja no es un genérico sino el título del
   producto con su modelo: "Bomba DAB circulación en línea CP50/2200 T-IE3".
   Antes las tres calderas del catálogo, de $1,0M a $4,2M, compartían una
   sola hoja llamada "Caldera".
2. **La soldadura de plata es subcategoría propia**, separada de "Aportes":
   cuesta un orden de magnitud más que la de estaño.
3. **En piping la subcategoría es el material** (`CATEGORIAS_SUBCATEGORIA_POR_MATERIAL`),
   no el tipo de pieza: Bronce, PPR, Acero galvanizado, Cobre, Acero
   inoxidable, PVC, Acero negro, PEX, Latón y "Otros materiales" (desde
   2026-09-22 la carpeta es el **sistema** de tubería cuando lo hay: un
   terminal de latón para PEX vive en PEX). El tipo no se pierde, sigue al
   frente del nombre de la hoja, y las hojas se listan **alfabéticamente**
   para que todos los codos queden juntos dentro de cada material.
4. **Las categorías secundarias** (`CATEGORIAS_SECUNDARIAS`: transporte,
   alimentación, arriendos y servicios, sin clasificar) se muestran en una
   sección aparte bajo el listado principal del dashboard.

**La hoja tiene dos formas**: `clave_hoja` es el texto que se muestra y
`clave_agrupacion` es la clave con la que se agrupa (sin tildes, sin
mayúsculas, con "c/" y "s/" expandidos a "con" y "sin", y el modelo pegado:
"R 24" y "R24"). Sin esa separación, el mismo estanque escrito de dos formas
abría dos hojas.

**El material es una faceta, no una categoría.** Todo el piping vive en
`Piping y Fittings` y el material entra a la hoja y al filtro. Antes cada
material era su propia categoría, y los que no estaban en la lista (PVC,
PEX, acero negro, y la abreviatura `BR` que el catálogo usa todo el tiempo)
dejaban 76 fittings sin categoría y **ocultos**.

**Los gastos de operación están separados de los productos.** Alimentación,
Transporte y Logística, y Arriendos y Servicios quedan marcados
`cotizable=False`: el precio unitario promedio de un peaje o un almuerzo no
significa nada (dispersión medida de 101x y 78x contra ~1x en las hojas de
producto). Siguen visibles y navegables, pero fuera de los KPIs de catálogo.

**Regla de oro: ningún ítem se oculta.** Si no se le puede extraer la
medida, la hoja queda marcada `(sin medida)` y el ítem sigue visible y
contado. El sistema anterior descartaba 136 de 1193 compras (11,4%) sin
avisar. Lo que no se puede clasificar cae en `Sin Clasificar`, que **no es
un cajón de sastre sino una cola de trabajo**: aparece como KPI en el
dashboard y como lista en `driver.py categorias`.

**Para cambiar cómo se clasifica algo** se edita el catálogo que corresponda
(`catalogo_taxonomia.py` para un tipo de producto; `catalogo_atributos.py`
para un material, una abreviatura, una terminación o un filtro), **nunca el
HTML**. Después se corre `py -3.14 -m pytest`, `driver.py categorias` (dónde
cayó cada compra), `driver.py atributos` (qué palabras quedaron sin
interpretar) y `driver.py evaluacion` (si el cambio mejoró o empeoró),
comparando que no se haya movido nada que ya estaba bien.

## Lo que se muestra y lo que se compara (`Sistema/presentacion.py`)

**Un valor y su escritura son dos cosas distintas** (2026-09-23,
`Cotizador Historico/Sistema/presentacion.py`). "20000mm" y "20 m" son la
misma extensión eléctrica: la primera es la que hace falta para *comparar*
medidas entre sí, la segunda es la única que un comprador reconoce. Mientras
vivieron en el mismo campo, el catálogo mostraba la escritura de la máquina.
Dos cosas que dejó separarlas, y valen para cualquier módulo que muestre
datos que también indexa:

- **La cadena que se muestra no puede ser la que se compara.** Al pasar la
  hoja a la escritura legible, "Reducción de Cobre 3/4x1/2"" quedó
  `3/4" x 1/2"` y la consulta `reduccion cobre 3/4 x 1/2` —que el buscador
  junta en un solo término `3/4x1/2`— dejó de encontrarla. Se ve en la
  evaluación (P@1 0,982 → 0,955), no mirando la pantalla.
- **La escritura correcta se puede leer de los propios datos.** El mismo
  proveedor llega como "Quilpue" y "Quilpué", y la misma marca como "ANWO" y
  "Anwo". En vez de una lista a mano, gana la forma con tilde y después la
  más frecuente del catálogo: determinista, explicable y no envejece cuando
  entra un proveedor nuevo.
