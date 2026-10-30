# CLAUDE.md — Cotizador Histórico

Estima el costo actual de un ítem a partir de sus compras en **Centro de Costos**, reajustando cada precio histórico por
la UF entre la fecha de compra y la de consulta. **Solo lectura**: nunca escribe `Centro de Costos.xlsx`; si necesitas
que se actualice, corre `/Registro_Centro_de_Costos`.

| Tema | Detalle (léelo solo al tocarlo) |
|---|---|
| Ficha del producto, etapas de clasificación, afinamientos, escritura legible | [docs/clasificacion.md](docs/clasificacion.md) |
| Cómo puntúa la búsqueda, medidas, métricas, cuidado con el benchmark | [docs/busqueda.md](docs/busqueda.md) |
| Funciones de `Sistema/cotizador_historico.py` | [docs/funciones.md](docs/funciones.md) |
| Tablero | `Visualizador Web/CLAUDE.md` |
| Comandos y ejemplos | [SKILL.md](.claude/skills/Cotizador_Historico/SKILL.md) |
| Diseño original | [docs/specs/2026-07-17-cotizador-historico-design.md](docs/specs/2026-07-17-cotizador-historico-design.md) |

## Alcance

- **Fuente**: hojas `Detalle` + `Master` de `Centro de Costos/Excel/Centro de Costos.xlsx`, cruzadas por `N° Ref.` (si
  CC documenta un cambio de esquema, revisa `mapear_encabezados` y `cargar_items_detalle`). No incluye cotizaciones no
  compradas; si aparecen, serían una fuente más junto a CC.
- **Precio base**: `P. Unitario sin IVA`. El IVA sale de la tasa real de cada documento (`tasa_iva_real`), **nunca un 19 %
  fijo**. Quedan fuera (`excluido_motivo`): `sin_master`, `fecha_invalida`, `precio_invalido`, `precio_negativo` (Notas
  de Crédito) y `precio_cero` (cero exacto, **sin umbral**: el ítem real más barato vale $29).
- **Reajuste solo por UF**, de `mindicador.cl`, con caché histórica en `Sistema/uf_cache.json` (no es sensible).
- **Sin respaldo por categoría**: sin ningún término en el catálogo, «no encontrado» con sugerencias. Lo que se cumple a
  medias se devuelve declarando qué faltó (`Indice.terminos_sin_resultado`).
- **Hoja** (`familia + material + medida`): la unidad de comparación de precios, dentro de categoría > subcategoría > hoja.
- `consultar_item` devuelve `grupos` y `descartadas_por_medida`; `buscar_items(..., aplicar_medida=True)`,
  `agregar_taxonomia` y `agrupar_por_hoja` hacen el resto.

## La UF

- **Compra puntual sin UF** (fecha histórica sin caché ni conexión): se excluye con un aviso, y el resto se muestra.
  Nunca se inventa, y no tiene respaldo.
- **UF de hoy**: siempre fresca, nunca del caché. Si `mindicador.cl` falla, se usa `Sistema/uf_ultima.json` si tiene
  hasta 3 días (`DIAS_UF_RESPALDO`; el tablero dice de qué día es; en pruebas, `QUEMPIN_UF_ULTIMA`). Sin nada de eso y
  sin valor manual, **la consulta aborta**: no hay resultado parcial.
- **Respaldo manual** (`obtener_uf_hoy(fecha, uf_manual, fuente_manual)`): solo si `mindicador.cl` falló, busca con
  `WebSearch` el valor del día en una fuente confiable (Banco Central, SII) y pásalo con `--uf-manual VALOR --uf-fuente
  "<texto>"` a `driver.py visualizador` o `consultar`. Nunca lo inventes ni lo saques del caché. Valor y fuente quedan
  visibles en el snapshot, en la consola y en el tablero.

## Motores y catálogos: se edita el catálogo, **nunca el HTML**

| Motor | Catálogo (esto se edita) | Qué decide |
|---|---|---|
| `taxonomia.py` | `catalogo_taxonomia.py` | tipo de producto, categoría, hoja (`clave_hoja`, `clave_agrupacion`) |
| `atributos.py`, `dimensiones.py` | `catalogo_atributos.py` | material con rol, abreviaturas, terminaciones, esquemas (`ESQUEMA_POR_TIPO`), facetas |
| `presentacion.py` | `catalogo_presentacion.py` | unidad práctica de cada medida y una sola escritura por nombre |
| `busqueda.py` | `catalogo_busqueda.py` | sinónimos, marcas, pesos, equivalencias DN↔pulgada, umbrales |

Medición: `benchmark_busqueda.py`, `evaluacion.py` y `referencia_atributos.py` (203 productos etiquetados a mano).

**Seis reglas que conviene no reaprender a golpes:**

1. Ninguna palabra de material es término de una regla de producto.
2. El material tiene **rol**: principal, *componente* («mazo de goma con mango de acero» es de goma), *aplicación* («disco
   para inoxidable» no es de inoxidable) y *sistema* de tubería.
3. Manda el sustantivo principal: suma por ir al inicio del nombre y resta tras «con», «incluye» o «porta».
4. El significado de un número depende de la familia (`ESQUEMA_POR_TIPO`).
5. Un entero sin unidad se lee según el sistema: milímetros en PEX/PPR/PVC, pulgadas nominales en cobre o acero.
6. Nada se fuerza: lo que ninguna tabla explica queda sin interpretar, con su motivo, en `driver.py atributos`.

**Ningún ítem se oculta**: sin medida va a la hoja `(sin medida)`; `Sin Clasificar` es una cola de trabajo, no un cajón.
El material es una faceta, no una categoría (`CATEGORIAS_SUBCATEGORIA_POR_MATERIAL`). Los gastos de operación quedan
`cotizable=False` (`CATEGORIAS_SECUNDARIAS`): visibles, fuera de los KPIs de catálogo. `CATEGORIAS_CON_MODELO` lleva el
modelo a la hoja.

**Después de un cambio**: `py -3.14 -m pytest` y `driver.py categorias` (dónde cayó cada compra), `atributos` (qué no se
interpretó), `evaluacion` y `benchmark`, comprobando que no se movió nada que ya estaba bien. `benchmark` mide contra la
clasificación del propio sistema; `evaluacion`, contra el texto crudo: **solo esta ve un error de la taxonomía**.

## Búsqueda

- Puntúa por cobertura de la consulta con IDF, peso por campo y medida como multiplicador (×1,6 si calza, ×0,18 si no).
- **DN va en un solo sentido** (DN50 significa 2"). **La comilla no es un operador**: en este catálogo significa pulgadas.
- **Un solo buscador en dos lenguajes**: términos y medidas se calculan en Python (`indexar_para_snapshot`: `_bt`, `_bm`),
  las tablas viajan con `config_para_snapshot()`, y la consulta se procesa en `Visualizador Web/busqueda.js`, **un archivo
  único para Chile y Perú**, inyectado por los builds. Perú no debe tener su copia (un test lo verifica).
- `tests/test_paridad_busqueda_js.py` exige el mismo orden en los dos motores. **Si falla, no ajustes el JavaScript hasta
  saber cuál de los dos tiene razón.** Ojo con `CASOS_SIN_RESULTADO` al agregar casos al benchmark.

## Precios de referencia para el Formulador

`Sistema/precios_referencia.py` publica `publicado/precios-referencia.json` en el Intercambio: una entrada por hoja con
promedio, rango y último precio reajustados (sin IVA), n° de compras e índice de búsqueda. El Formulador busca con una
**copia textual** de `busqueda.js` (`test_copia_del_formulador_es_textual` avisa si se desfasa).

- **No recalcula**: parte de `Visualizador Web/data/cotizador-historico.json` y agrupa con `agrupar_por_hoja`.
- **Sin proveedores ni proyectos**, porque la carpeta la ve toda la biblioteca: no viajan `prov`, `proy` ni `cod`, y de la
  descripción salen N° Ref, números de 5+ dígitos y nombres de proveedor (`palabras_privadas`).
- Se publica con `driver.py precios`, tras cada `driver.py visualizador` de Chile, y desde el procesador cuando cambia la
  foto del tablero.

## Comandos

`py -3.14 .claude/skills/Cotizador_Historico/driver.py status | consultar "<texto>" | visualizador | categorias |
benchmark | evaluacion | atributos | precios | uf`. Perú: `Peru/Cotizador Historico/` usa este mismo motor (`--pais PE`),
sin reajuste por ningún índice.
