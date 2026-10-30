# Cotizador Histórico: búsqueda

Detalle de referencia: léelo solo al tocar esto. Las reglas vigentes están en `../CLAUDE.md`.

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
