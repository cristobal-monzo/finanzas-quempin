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
  `Sistema/uf_cache.json`. La UF del día de la consulta nunca se cachea
  entre corridas — siempre se pide fresca.
- Búsqueda de ítem por texto: difusa (`difflib`, stdlib) contra `Nombre
  Ítem` y `Descripción` de `Detalle`, sin dependencias nuevas.
- **Sin respaldo por categoría**: si no hay match de nombre, la respuesta es
  "no encontrado" (con sugerencias de baja similitud si las hay) — decisión
  explícita del usuario para v1, no un olvido.
- **Taxonomía propia** (reestructurada 2026-09-08, ver sección siguiente):
  cada compra se clasifica en categoría > subcategoría > hoja, y la **hoja**
  (`familia + material + medida`) es la unidad de comparación de precios.
- **No incluye cotizaciones** (presupuestos no comprados) — no existen hoy
  en un formato estructurado. Si aparecen más adelante, se integrarían como
  una fuente adicional junto a Centro de Costos, no reemplazándola (ver spec
  de diseño).

Diseño completo, incluyendo las alternativas consideradas:
[`docs/superpowers/specs/2026-07-17-cotizador-historico-design.md`](docs/superpowers/specs/2026-07-17-cotizador-historico-design.md).

## Taxonomía: cómo se categoriza cada ítem

Reestructurada el **2026-09-08** a pedido del usuario ("hay elementos que son
de 1.1/4" y que se indican como si fueran de 1/4""). Diseño completo, con
las mediciones sobre las 1193 compras reales que lo justifican, en
[`docs/superpowers/specs/2026-09-08-taxonomia-cotizador-design.md`](docs/superpowers/specs/2026-09-08-taxonomia-cotizador-design.md).

**Vive en Python, no en el HTML.** `Sistema/taxonomia.py` (motor) +
`Sistema/catalogo_taxonomia.py` (datos: categorías, materiales, reglas). La
usan por igual `consultar_item` (consola y conversación) y los dos
`build_visualizador.py` (Chile y Perú). Antes vivía en JavaScript dentro de
`Visualizador Web/template.html`, duplicada por país y **ya divergente**
(Perú nunca recibió la categoría Instrumentación agregada el 2026-08-31),
sin tests, y la consulta por consola no la usaba.

**Cuatro etapas** (cada una testeada por separado en `Sistema/tests/test_taxonomia.py`):

1. `normalizar`/`raiz` — sin tildes, sin plural, sin palabras vacías, para
   que `guantes`/`guante` y `Valvula`/`Válvula` sean lo mismo.
2. `parsear_medidas` — gramática de medidas. Reconoce la fracción mixta
   chilena en sus tres escrituras (`1.1/4`, `1-1/4`, `1 1/4`), la
   abreviatura `plg`, las compuestas (`1.1/2x1.1/4`), y **rechaza** lo que
   no es medida: modelos (`VA 65/180`), códigos (`NB2-40/42`), magnitudes
   que no son longitud (220V, 280ml, 25kg) y ángulos de fitting
   (`Codo 90 3/4` es de 3/4", no de noventa y tres cuartos).
3. `clasificar` — categoría/subcategoría/familia con un catálogo de reglas.
   El match es **por palabra completa**, nunca substring: así "S-tee-lgen"
   no activa "tee" y "dado que" no activa "dado" (dos errores reales del
   sistema anterior). Un término negado (`sin`, `s/`) no activa su regla.
4. `clave_hoja` — `familia + material + medida`. Dos compras solo se
   promedian si comparten hoja: **una cañería de cobre de 1/2 nunca se
   promedia con una de 2**.

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

**Para cambiar cómo se clasifica algo** se edita
`Sistema/catalogo_taxonomia.py` (nunca el HTML), se corre
`py -3.14 -m pytest` y después `driver.py categorias`, y se compara que no
se haya movido nada que ya estaba bien.

## Estructura del módulo

```
Cotizador Historico/
├── CLAUDE.md                              # este archivo
├── docs/superpowers/                      # specs/plans de Claude Code
├── Sistema/
│   ├── cotizador_historico.py             # lógica: leer Excel, indexar, fuzzy search, reajuste UF
│   ├── taxonomia.py                       # motor: medidas + clasificación + clave de hoja
│   ├── catalogo_taxonomia.py              # datos: categorías, materiales, reglas (esto es lo que se edita)
│   ├── uf_cache.json                      # caché fecha ISO -> valor UF (se crea solo en la primera corrida)
│   └── tests/                             # tests de pytest
└── .claude/
    └── skills/
        └── Cotizador_Historico/
            ├── SKILL.md
            └── driver.py                  # comandos: status | consultar "<texto>" | visualizador | categorias
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
- `buscar_items(items, texto_busqueda)` — búsqueda difusa contra `Nombre
  Ítem`/`Descripción`; devuelve `(coincidencias, sugerencias)`.
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
