# CLAUDE.md

## Qué es este módulo

`Cotizador Historico` estima el costo actual de un ítem (material, equipo,
herramienta) a partir de sus compras registradas en el módulo **Centro de
Costos**, reajustando cada precio histórico por la variación de la UF entre
la fecha de esa compra y la fecha de la consulta. Es de **solo lectura**:
nunca escribe `Centro de Costos.xlsx` ni ningún otro archivo de ese módulo.

Ver `../CLAUDE.md` (raíz de `Finanzas QUEMPIN/`) para el contexto general de
los módulos financieros de QUEMPIN SpA, y `../Centro de Costos/CLAUDE.md`
para el detalle de la estructura de `Centro de Costos.xlsx` que este módulo
consume.

## Alcance actual (v1)

- Única fuente de datos: hojas `Detalle` (ítems de línea) + `Master`
  (fecha por documento) de `Centro de Costos/Excel/Centro de Costos.xlsx`,
  cruzadas por `N° Ref.`.
- El precio base de cada ítem es `P. Unitario sin IVA` (comparable entre
  compras de distinta cantidad). El ajuste con IVA se deriva de la tasa
  real del documento (`Total con IVA` / `Total sin IVA` de esa fila de
  `Detalle`), igual que hace Centro de Costos — nunca asume 19% fijo, para
  ser correcto también en documentos exentos o de Zona Franca
  (`tasa_iva_real`).
- El reajuste es solo por UF (no IPC, no dólar) — valores obtenidos de la
  API pública `mindicador.cl`, con caché local de fechas históricas en
  `Sistema/uf_cache.json`. La UF del día de la consulta siempre se pide
  fresca. Desde el 2026-10-08 la última que respondió queda en
  `Sistema/uf_ultima.json` (gitignoreado): si mindicador.cl no responde, y no
  se pasó un valor manual, se usa esa, si tiene hasta 3 días
  (`DIAS_UF_RESPALDO`), y el tablero dice de qué día es. Antes un timeout
  dejaba la corrida programada sin tablero del Cotizador (pasó el
  2026-10-05). En los tests la variable `QUEMPIN_UF_ULTIMA` (fijada por el
  `conftest.py` raíz) la manda a `tmp_path`.
- Búsqueda de ítem por texto: **motor de relevancia propio**
  (`Sistema/busqueda.py`, reescrito 2026-09-16, ver sección siguiente), sin
  dependencias nuevas. Busca contra nombre, descripción, nombre canónico de
  la taxonomía, categoría, material, marca, código, proveedor y proyecto, y
  ordena por cobertura de la consulta, peso del campo y medida.
- **Sin respaldo por categoría**: si ningún término de la consulta existe en
  el catálogo, la respuesta es "no encontrado" (con sugerencias si las hay).
  Si la consulta se cumple **a medias** ("válvula de compuerta" en un
  catálogo que solo tiene de bola) sí se devuelven los resultados parciales,
  pero declarando qué término no se encontró
  (`Indice.terminos_sin_resultado`) — una pantalla vacía cuando existe un
  pariente cercano no ayuda a nadie, y no avisar haría creer que el pariente
  es lo que se pidió.
- **Taxonomía propia** (reestructurada 2026-09-08, ver sección siguiente):
  cada compra se clasifica en categoría > subcategoría > hoja, y la **hoja**
  (`familia + material + medida`) es la unidad de comparación de precios.
- **No incluye cotizaciones** (presupuestos no comprados) — no existen hoy
  en un formato estructurado. Si aparecen más adelante, se integrarían como
  una fuente adicional junto a Centro de Costos, no reemplazándola (ver spec
  de diseño).

Diseño completo, incluyendo las alternativas consideradas:
[`docs/specs/2026-07-17-cotizador-historico-design.md`](docs/specs/2026-07-17-cotizador-historico-design.md).

## Clasificación y atributos: qué es cada ítem

Reestructurada dos veces: el **2026-09-08** (categoría > subcategoría > hoja,
con las medidas bien leídas) y el **2026-09-22**, cuando el material, las
dimensiones y las especificaciones pasaron a ser **atributos independientes**.
El pedido del usuario de esa segunda vuelta es el principio que ordena todo:

> Un producto no debe clasificarse únicamente por su forma o dimensiones. Debe
> identificarse primero **qué** producto es, **de qué** material está fabricado
> y posteriormente cuáles son sus características dimensionales y técnicas.

Diseño completo, con el análisis de lo que estaba roto y las mediciones, en
[`docs/specs/2026-09-22-atributos-cotizador-design.md`](docs/specs/2026-09-22-atributos-cotizador-design.md)
(el de la primera vuelta, en
[`2026-09-08-taxonomia-cotizador-design.md`](docs/specs/2026-09-08-taxonomia-cotizador-design.md)).

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

## Búsqueda: cómo encuentra un ítem

Reescrita el **2026-09-16**. Motor en `Sistema/busqueda.py`, datos en
`Sistema/catalogo_busqueda.py` (sinónimos, marcas, pesos por campo,
equivalencias DN↔pulgada, umbrales) — misma separación motor/datos que
`taxonomia.py` + `catalogo_taxonomia.py`, y **el archivo que se edita cuando
una búsqueda real no encontró lo que debía es el catálogo**.

**Qué estaba roto.** El buscador anterior puntuaba con una función que
devolvía `1.0` en cuanto el ítem compartía una palabra de ≥4 letras con la
consulta. Medido sobre el catálogo real: `Válvula de bola de 2"` y `valvula`
devolvían exactamente lo mismo —41 compras, **todas empatadas en 1.0**— y el
desempate lo hacía el orden de las filas del Excel. La válvula de 1/2" salía
segunda. No había ranking: había un filtro binario disfrazado de ranking.

**Cómo puntúa ahora**, en orden de impacto:

1. **Cobertura de la consulta.** Un ítem que calza los 3 términos vale mucho
   más que uno que calza 1, y cada término pesa por IDF (cuánto discrimina).
2. **Un campo por ATRIBUTO, con el peso en el orden que pidió el usuario**
   (2026-09-22): código 12, **tipo de producto 11**, `Nombre Ítem` 10, hoja 9,
   **material (con su familia de material y su grado) 8**, **dimensiones 7**,
   **especificaciones 5**, categoría 5, terminación y aplicación 4,5, marca 4,
   descripción 3,5, proveedor y proyecto 2. Más un descuento por campo largo:
   que "teflón" sea el nombre completo de un ítem dice más que verlo dentro de
   una frase de 8 palabras.
3. **La medida principal es un multiplicador, no un término.** 2" contra 2"
   multiplica por 1,6; contra 1/2" por 0,18. **Una medida distinta es otro
   producto.** Las demás dimensiones sí suman como términos: por eso "plancha
   policarbonato 0.7" encuentra su plancha y "policarbonato 812" también.
4. **Tolerancia**, resuelta antes de puntuar con las mismas funciones de la
   taxonomía: tildes, mayúsculas, plurales, palabras vacías, orden de las
   palabras, sinónimos, abreviaturas (`galv`, `inox`, `valv`, `perf`) y
   errores de tipeo (1 error desde 4 caracteres, 2 desde 7).

**Qué entiende de un número** (2026-09-22; antes se descartaba todo número que
no fuera una pulgada):

| Se escribe | Se entiende |
|---|---|
| `0,7` · `0.7` · `0.70` | el mismo espesor |
| `812` · `3660` | ancho y largo de una plancha |
| `5.8m` | 5800 mm (y también se busca como "5.8") |
| `40x20x2` | tres dimensiones, no un código |
| `SS316` · `AISI 316` · `inox 316` | material inoxidable + grado 316 |
| `sch 40` · `SCH40` · `cédula 40` | la misma especificación |
| `M12` | rosca métrica de 12 mm |
| `15%` | la ley de una soldadura, **nunca** 15 pulgadas |
| `plancha 4` | 4 mm de espesor **o** 4 pulgadas: la lectura blanda no hunde al que lo tiene en milímetros |

**Medidas equivalentes.** `2"`, `2”`, `2 pulgadas`, `2 pulg`, `2 plg`,
`2 in`, `Ø2"` y `DN50` son la misma medida; `2"`, `1/2"`, `3/4"` y `2.1/2"`
son cuatro medidas distintas. Desde 2026-09-22 hay además dos equivalencias
**de familia**, escritas en `catalogo_atributos.py`: un disco abrasivo de
4.1/2" es el de 115 mm, y un electrodo de 1/8" es el de 3,2 mm. Se resuelve con una **tabla de alias**
generada desde `taxonomia.parsear_medidas` y validada contra él entrada por
entrada (`tests/test_busqueda_medidas.py`) — así el dashboard no necesita
reimplementar la gramática de medidas en JavaScript.

**DN va en un solo sentido: DN50 significa 2".** No existe la conversión
inversa ni `mm → pulgada` dividiendo por 25,4. Los milímetros de este
catálogo son diámetros **exteriores** de PPR/PVC: un tubo PPR de 50mm es
DN40 (1.1/2"), no DN50. Ligar `2"` con `50mm` mezclaría calibres distintos,
justo lo que la taxonomía evita al separar las hojas por medida.

**La comilla NO es un operador de frase exacta.** En este catálogo la
comilla es la unidad de medida más frecuente. Soportar frases entre comillas
rompería la consulta más común del módulo.

**Dónde corre cada cosa (y por qué no hay dos buscadores).** El dashboard
busca en el navegador y la consola en Python. Para que no diverjan —como ya
pasó con la taxonomía duplicada en JavaScript (2026-09-08) y con el KPI
"Nota del Proyecto" (2026-07-28)— se partió así:

| | Dónde vive | Cómo llega al navegador |
|---|---|---|
| Términos y medidas de cada ítem | Python (`indexar_para_snapshot`) | precalculados en el snapshot (`_bt`, `_bm`) |
| Tablas (sinónimos, alias, pesos) | `catalogo_busqueda.py` | `config_para_snapshot()` → `DATA.busqueda` |
| Procesar la consulta y puntuar | escrito dos veces | `Visualizador Web/busqueda.js`, **un solo archivo** que los builds de Chile y Perú inyectan |

Lo único escrito dos veces es el lado de la consulta, y está clavado por
`tests/test_paridad_busqueda_js.py`: corre 45 consultas por los dos motores
con Node y exige el **mismo orden**. Si ese test falla, no se ajusta el
JavaScript hasta que pase — se averigua cuál de los dos tiene razón.

**Cómo saber si un cambio mejoró o empeoró.** Hay dos instrumentos, y miden
cosas distintas:

```
py -3.14 ".claude/skills/Cotizador_Historico/driver.py" benchmark [--detalle]
py -3.14 ".claude/skills/Cotizador_Historico/driver.py" evaluacion [--detalle]
```

`benchmark` (2026-09-16) son 48 consultas cuya respuesta esperada es un
predicado sobre la clasificación del propio sistema: sirve para comparar dos
rankings sobre la misma taxonomía, pero **no puede ver un error de la
taxonomía** (si tres barras PEX comparten hoja, las cuenta como un acierto).

`evaluacion` (2026-09-22) es independiente del sistema: 203 productos reales
etiquetados a mano (`Sistema/referencia_atributos.py`) y 110 consultas cuya
relevancia es un predicado sobre el **texto crudo** del producto
(`Sistema/evaluacion.py`). Mide material, dimensiones con su rol, P@1, P@5,
Success@5 y MRR, más los conteos sobre las 1.484 compras. Estado al
2026-09-22 (antes = motor del 2026-09-16):

| Métrica | Antes | Ahora |
|---|---|---|
| Material correcto | 0,824 | **1,000** |
| Dimensiones: valores | 0,644 | **1,000** |
| Dimensiones: **con su rol** | 0,000 | **1,000** |
| P@1 | 0,764 | **0,982** |
| P@5 normalizada | 0,762 | **0,895** |
| Success@5 | 0,882 | **1,000** |
| MRR | 0,813 | **0,991** |
| Compras en "Sin Clasificar" | 20 | **0** |
| Clasificaciones ambiguas | 17 | **11** |

23 consultas pasaron a acertar en el primer lugar y ninguna empeoró. La
referencia se escribió mirando el catálogo antes de implementar, pero se
iteró contra ella: es un set de desarrollo, no una muestra ciega (los
conteos sobre las 1.484 compras sí son independientes).

Y el benchmark de 48 consultas, para comparar contra el motor de 2026-09-16:

| Métrica | Antes (difflib) | 2026-09-16 | Ahora |
|---|---|---|---|
| Success@5 | 0,792 | 1,000 | **1,000** |
| P@5 | 0,317 | 0,479 | **0,475** |
| P@5 normalizada (sobre lo alcanzable) | 0,655 | 0,935 | **0,983** |
| MRR | 0,654 | 1,000 | **1,000** |

El P@5 crudo tiene techo bajo porque la mayoría de las consultas tiene **una
sola** hoja correcta (hay un solo producto `Válvula de Bola 2"`): contra eso
el P@5 no puede pasar de 0,2 por mucho que acierte. Por eso se informa
también el normalizado.

**Cuidado al agregar casos al benchmark**: dos de los casos iniciales
(`amoladora`, `esmeril angular`) daban por esperado un producto que el
catálogo real **no tiene**. Una consulta cuya respuesta no existe en los
datos no mide al buscador, mide a quien escribió el test — pasaron a
`CASOS_SIN_RESULTADO`.

## Estructura del módulo

```
Cotizador Historico/
├── CLAUDE.md                              # este archivo
├── docs/                                  # specs y planes de diseño (specs/, plans/)
├── Sistema/
│   ├── cotizador_historico.py             # lógica: leer Excel, indexar, buscar, reajuste UF
│   ├── taxonomia.py                       # motor: medidas + clasificación + clave de hoja
│   ├── catalogo_taxonomia.py              # datos: categorías y reglas de TIPO de producto (esto se edita)
│   ├── atributos.py                       # motor: material con rol, especificaciones, terminación, confianza
│   ├── dimensiones.py                     # motor: cuánto mide y qué es cada número (esquema por familia)
│   ├── catalogo_atributos.py              # datos: materiales, abreviaturas, terminaciones, esquemas, facetas (esto se edita)
│   ├── presentacion.py                    # motor: unidad práctica de cada medida + una sola escritura por nombre
│   ├── catalogo_presentacion.py           # datos: siglas técnicas con su escritura correcta (esto se edita)
│   ├── busqueda.py                        # motor de búsqueda: normalizar, medidas, índice, ranking
│   ├── catalogo_busqueda.py               # datos: sinónimos, marcas, pesos, umbrales (esto se edita)
│   ├── benchmark_busqueda.py              # 48 consultas juzgadas con la clasificación del sistema
│   ├── evaluacion.py                      # 110 consultas juzgadas contra el texto crudo + métricas de atributos
│   ├── referencia_atributos.py            # 203 productos reales etiquetados a mano (el patrón de comparación)
│   ├── uf_cache.json                      # caché fecha ISO -> valor UF (se crea solo en la primera corrida)
│   └── tests/                             # tests de pytest
└── .claude/
    └── skills/
        └── Cotizador_Historico/
            ├── SKILL.md
            └── driver.py                  # comandos: status | consultar "<texto>" | visualizador |
                                           #           categorias | benchmark | evaluacion | atributos
```

## Cómo se usa

Como skill de Claude Code: pedirlo conversacionalmente (ej. "¿cuánto
debería costar hoy un taladro?") o correr el driver directamente. Ver
[`.claude/skills/Cotizador_Historico/SKILL.md`](.claude/skills/Cotizador_Historico/SKILL.md)
para los comandos (`status`/`consultar`) y ejemplos de salida.

## Funciones clave de `Sistema/cotizador_historico.py`

- `cargar_items_detalle(ruta_excel=None)` — lee `Detalle`+`Master`, resuelve
  la fecha de cada ítem vía `N° Ref.` e incluye `total_sin_iva`/
  `total_con_iva` de esa misma fila; ítems sin `Master` correspondiente,
  con fecha no parseable, cuya celda `P. Unitario sin IVA` no es un número
  finito, o cuyo `P. Unitario sin IVA` es negativo o **cero**, quedan con
  `excluido_motivo` poblado (`"sin_master"`, `"fecha_invalida"`,
  `"precio_invalido"`, `"precio_negativo"` o `"precio_cero"`) y no entran a
  ninguna búsqueda ni agregación.
  `"precio_cero"` (2026-09-08, pedido explícito del usuario tras ver una
  "Bomba DAB circuladora" figurando en $0 en el cotizador): una línea en $0
  es algo incluido sin cargo dentro de un documento, no una observación de
  precio. **Se filtra el cero exacto, nunca un umbral mínimo**: el ítem más
  barato del catálogo real es un remache de $29 y es legítimo. Revierte la
  decisión del 2026-07-28 que trataba el $0 como caso válido.
  `"precio_negativo"` es la exclusión de Notas de Crédito/devoluciones
  (pedido explícito del usuario 2026-07-28, tras encontrar una devolución
  real —`UMAG-025`— colándose como "el ítem más barato" de una consulta):
  se filtra por signo del precio unitario, no por `Tipo Documento` de
  `Master` (que este módulo no lee), porque una devolución siempre viene
  con precio negativo en `Detalle` independiente de cómo haya quedado
  tipificado el documento. **No agregar más Notas de Crédito al índice de
  este módulo.**
- `buscar_items(items, texto_busqueda, aplicar_medida=True)` — búsqueda por
  relevancia contra todos los campos del ítem (delega en `busqueda.Indice`);
  devuelve `(coincidencias, sugerencias)` con las coincidencias ordenadas de
  más a menos relevante. `aplicar_medida=False` apaga el ranking por medida
  y devuelve las coincidencias de texto puras — lo usa `consultar_item`,
  que necesita **todas** las compras de la familia para poder informar
  cuántas descartó por ser de otro calibre.
- `obtener_valor_uf(fecha, cache_uf)` / `consultar_uf_api(fecha)` — UF
  histórica cacheada localmente; la UF de "hoy" se pide siempre fresca (no
  pasa por el caché de archivo).
- `obtener_uf_hoy(fecha, uf_manual=None, fuente_manual=None)` — la UF de
  "hoy" con fallback (agregado 2026-08-20): intenta `consultar_uf_api`
  primero; si `mindicador.cl` no responde y se pasó un valor manual (ver
  "Precauciones" abajo), lo usa y devuelve `(valor, fuente)`. Sin valor
  manual, relanza `UFNoDisponibleError` igual que siempre. `consultar_item`
  y `build_visualizador.py::extraer_indice_saneado` llaman a esta función,
  no a `consultar_uf_api` directo, para heredar el fallback.
- `tasa_iva_real(total_sin_iva, total_con_iva)` — tasa real de IVA del
  documento original; `1.0` (sin IVA adicional) como respaldo si los
  totales no son numéricos o el total sin IVA es 0.
- `agregar_taxonomia(compra)` / `agrupar_por_hoja(compras)` — agregan la
  clasificación a una compra y agrupan por hoja con su propio promedio,
  rango y dispersión. Se aplican en los dos caminos (dashboard y consulta)
  para que ambos clasifiquen idéntico.
- `consultar_item(texto_busqueda, ruta_excel=None, fecha_hoy=None)` —
  orquesta todo lo anterior y devuelve el resultado completo: compras
  individuales (cada una con su categoría/familia/material/medida/hoja),
  promedio y rango globales, **`grupos`** (una entrada por hoja, con su
  propio promedio: es el número que responde la pregunta real, el global
  mezcla hojas distintas), y sugerencias si no hubo match. Si el texto
  buscado trae una medida (`"codo bronce 1.1/4"`), solo entran las compras
  de esa medida y las demás se cuentan en `descartadas_por_medida`.

## Precios de referencia para el Formulador (2026-10-01)

`Sistema/precios_referencia.py` publica `publicado/precios-referencia.json`
en la carpeta de intercambio: una entrada por **hoja** con el promedio, el
rango y el último precio reajustados por UF (sin IVA), el n° de compras y el
índice de búsqueda ya calculado. El Formulador busca sobre esas hojas con una
**copia textual** de `Visualizador Web/busqueda.js` (el test
`test_copia_del_formulador_es_textual` avisa si se desfasa) y la
configuración que viaja en la publicación: un solo buscador.

- **No recalcula nada**: parte de la foto del tablero
  (`Visualizador Web/data/cotizador-historico.json`) y agrupa con la misma
  `agrupar_por_hoja`. La UF se pide una sola vez, en el build del tablero.
- **Sin proveedores ni proyectos** (decisión del 2026-10-01: la carpeta la
  ve toda la biblioteca). Tampoco viajan los campos `prov`, `proy` ni `cod`
  del índice, y de la descripción se sacan los N° Ref, los números de 5+
  dígitos (n° de factura) y las palabras de nombres de proveedor que no son
  vocabulario de producto (`palabras_privadas`): medido sobre el catálogo
  real, 16 hojas traían «sodimac» y n° de factura en la descripción.
- Se publica con `driver.py precios`, automáticamente después de cada
  `driver.py visualizador` de Chile, y desde el procesador del intercambio
  cuando cambia la foto del tablero.

## Precauciones

- Este módulo **nunca escribe** `Centro de Costos.xlsx` — si necesitas que
  se actualice, corre el módulo Centro de Costos
  (`/Registro_Centro_de_Costos`), no este.
- Depende de que `Centro de Costos/Excel/Centro de Costos.xlsx` exista con
  su estructura actual (hojas `Detalle`/`Master`, encabezados en fila 1,
  `Fecha` de `Master` como fecha real, no texto) — si `Centro de
  Costos/CLAUDE.md` documenta un cambio de esquema, revisar
  `mapear_encabezados`/`cargar_items_detalle` acá.
- Requiere conexión a internet para fechas de UF que no estén ya en
  `Sistema/uf_cache.json`. Dos casos distintos: si falla la UF de una
  compra puntual (fecha histórica sin caché ni conexión), esa compra se
  excluye del resultado con un aviso claro y el resto sí se muestra — nunca
  se inventa un valor de UF para una fecha histórica, y este caso **no**
  tiene fallback (ver siguiente punto, distinto). Si falla la UF de **hoy**
  (necesaria para reajustar cualquier compra por igual, se pide siempre
  fresca, nunca tiene caché) y no hay valor manual, la consulta completa
  aborta con un error — no hay resultado parcial posible en ese caso.
- **Fallback de la UF de "hoy" cuando `mindicador.cl` no responde**
  (pedido explícito del usuario, 2026-08-20 — ocurrió en producción ese
  mismo día): `mindicador.cl` sigue siendo la fuente prioritaria, se
  intenta siempre primero. Solo si falla, el agente debe
  buscar en internet (`WebSearch`) el valor de la UF del día en una fuente
  confiable (ej. Banco Central de Chile, SII, o un sitio financiero
  reconocido) y pasarlo explícitamente via `--uf-manual VALOR --uf-fuente
  "<texto>"` a `driver.py visualizador`/`driver.py consultar` (o
  `uf_manual=`/`fuente_manual=` si llama a `consultar_item` directo en
  conversación) — nunca lo inventa ni lo asume del caché histórico. El
  valor usado y su fuente quedan visibles: en el snapshot (`uf_fuente`), en
  el aviso de consola (`[AVISO] mindicador.cl no respondio...`), y en el
  visualizador publicado (sufijo "· fuente: ..." junto a "UF utilizada").
  Detalle del mecanismo (`obtener_uf_hoy`) en "Funciones clave" arriba;
  procedimiento paso a paso para el flujo de publicación en
  `.claude/skills/Actualizar_Cotizador/SKILL.md`.
- **El buscador no se edita en `template.html`.** Mismo criterio que la
  taxonomía: el motor está en `Sistema/busqueda.py` + `catalogo_busqueda.py`
  y el lado navegador en `Visualizador Web/busqueda.js`, **un solo archivo
  compartido con Perú** que los builds inyectan. Perú no debe tener su
  propia copia (hay un test que lo verifica). Para cambiar cómo encuentra
  algo se edita `catalogo_busqueda.py`, se corre `py -3.14 -m pytest` y
  después `driver.py benchmark`, comparando que no se haya movido nada que
  ya estaba bien.
- **La taxonomía no se edita en `template.html`.** Desde 2026-09-08 el
  template solo lee lo que el snapshot ya trae calculado; si se vuelve a
  clasificar en JavaScript reaparece la divergencia Chile/Perú que este
  cambio eliminó. Editar `Sistema/catalogo_taxonomia.py` y regenerar.
- **Ningún ítem se oculta por no tener medida** — si un fitting no aparece
  donde debería, revisar `driver.py categorias` (cola de "requieren medida
  y no la tienen"), no asumir que se filtró.
- `Sistema/uf_cache.json` contiene solo valores públicos de UF (no datos
  financieros de la empresa) — a diferencia de los datos de Centro de
  Costos, no es sensible.
