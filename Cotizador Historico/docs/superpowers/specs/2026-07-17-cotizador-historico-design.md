# Cotizador Historico — Diseño

Fecha: 2026-07-17

## Propósito

Dado el nombre de un ítem (ej. "taladro"), buscar sus compras históricas
registradas en `Centro de Costos.xlsx` y estimar su costo actual reajustando
cada precio encontrado por UF: UF del día de la compra → UF del día de la
consulta.

Sirve para tener una noción rápida de cuánto debería costar hoy algo que ya
se compró antes, sin tener que ir a buscar manualmente facturas viejas.

## Alcance v1

- **Fuente de datos**: únicamente `Centro de Costos/Excel/Centro de
  Costos.xlsx` (hojas `Detalle` + `Master`). No hay integración con
  cotizaciones (presupuestos no comprados) en esta versión — el usuario no
  tiene hoy una fuente estructurada de cotizaciones. El resultado de cada
  compra encontrada se modela como `{fecha, precio, fuente}` para poder sumar
  una fuente "cotizaciones" más adelante sin rehacer la lógica de reajuste.
- **Cotizador Historico es 100% de solo lectura** sobre `Centro de
  Costos.xlsx`: nunca lo abre en modo escritura ni lo modifica. No compite
  con `auditor_centro_costos.py` por el archivo.
- Reajuste por UF, no por otro índice (IPC, dólar, etc.) — así lo pidió el
  usuario explícitamente.

## Fuente de datos: Centro de Costos.xlsx

- **`Detalle`**: una fila por ítem de línea — columnas relevantes `N° Ref.`,
  `Nombre Ítem`, `Descripción`, `Categoría Ítem`, `Cantidad`, `P. Unitario
  sin IVA`, `Total sin IVA (CLP)`, `Total con IVA (CLP)`. No tiene fecha
  propia.
- **`Master`**: una fila por documento — columna `Fecha` (y `N° Ref.` como
  clave de cruce). Cotizador Historico resuelve la fecha de cada ítem de
  `Detalle` uniendo por `N° Ref.` contra `Master`.
- El precio base para reajustar es **`P. Unitario sin IVA`** (no el total de
  línea), porque es comparable entre compras de distinta cantidad — decisión
  explícita del usuario durante brainstorming.

## Flujo de una consulta

1. Abrir `Centro de Costos.xlsx` con `openpyxl.load_workbook(..., data_only=True,
   read_only=True)` — `data_only=True` para traer los valores ya calculados
   de las fórmulas de `Master` (Total sin IVA / Total con IVA), `read_only=True`
   porque Cotizador Historico nunca escribe.
2. Construir un índice en memoria de `Detalle`: por cada fila, resolver su
   `Fecha` vía `N° Ref.` contra `Master`. Filas cuyo `N° Ref.` no aparece en
   `Master`, o cuya `Fecha` no es parseable, quedan marcadas como excluidas
   (no entran a la agregación) y se cuentan para avisar al usuario.
3. Buscar el texto ingresado contra `Nombre Ítem` (principal) y `Descripción`
   (respaldo) de cada fila de `Detalle`, usando `difflib` (stdlib):
   normalizar ambos lados (minúsculas, sin acentos) y usar
   `difflib.SequenceMatcher.ratio()` / `get_close_matches` con un umbral de
   similitud (ej. `0.6`, ajustable) para tolerar variantes y errores de
   tipeo. Sin dependencias nuevas — el proyecto ya usa solo stdlib +
   `openpyxl`.
4. Para cada fila que hace match (y no está excluida por fecha):
   - Obtener `UF(fecha de compra)` y `UF(hoy)` desde la API pública
     `mindicador.cl` (endpoint de serie histórica por fecha), pasando por el
     caché local `Sistema/uf_cache.json` (`{"YYYY-MM-DD": valor_uf}`) — se
     consulta la API solo para fechas que no estén ya cacheadas; los valores
     históricos de UF no cambian una vez publicados, así que el caché es
     válido indefinidamente para fechas pasadas (la UF de "hoy" no se
     cachea de una corrida a otra, se pide siempre fresca).
   - `factor = UF(hoy) / UF(fecha de compra)`
   - `precio_reajustado = P. Unitario sin IVA × factor`
5. Responder con:
   - El detalle de cada compra encontrada: fecha, `N° Ref.`, precio
     original (sin IVA), precio reajustado a hoy.
   - Un resumen final: promedio y rango (mín–máx) de los precios
     reajustados.
   - Si no hay ningún match → `"no encontrado"`, y si hubo coincidencias de
     baja similitud (por debajo del umbral pero no lejísimos) se listan como
     sugerencia para que el usuario reformule la búsqueda.

## Estructura de carpetas

Mismo patrón que `Centro de Costos/` (módulo de referencia del proyecto):

```
Cotizador Historico/
├── CLAUDE.md                              # documentación del módulo (rol, flujo, estructura)
├── docs/superpowers/                      # specs/plans de Claude Code
│   └── specs/2026-07-17-cotizador-historico-design.md   # este archivo
├── Sistema/
│   ├── cotizador_historico.py             # lógica: leer Excel, indexar, fuzzy search, reajuste UF
│   ├── uf_cache.json                      # caché fecha->valor UF (se crea solo en la primera corrida)
│   └── tests/                             # tests de pytest del módulo
└── .claude/
    └── skills/
        └── Cotizador_Historico/
            ├── SKILL.md                   # documenta el procedimiento estable
            └── driver.py                  # comandos: status | consultar "<texto>"
```

`driver.py` expone:
- `status` — diagnóstico de solo lectura: cuántos ítems indexables hay en
  `Detalle`, si el Excel de Centro de Costos es accesible, si hay caché UF y
  cuántas fechas tiene, si hay conexión a `mindicador.cl` (sin escribir
  nada).
- `consultar "<texto>"` — corre la búsqueda + reajuste completo y muestra el
  resultado en consola.

El agente también puede responder la consulta directamente en la
conversación (skill conversacional) invocando la misma lógica de
`cotizador_historico.py`, igual que hoy hace `/Registro_Centro_de_Costos`
para status/run.

## Manejo de errores

- **Sin internet y sin caché para una fecha necesaria**: avisar claramente
  que no se pudo obtener la UF de esa fecha específica; esa compra queda
  excluida del resultado (no se inventa ni se aproxima un valor de UF).
- **`Centro de Costos.xlsx` no encontrado o bloqueado para lectura**:
  mensaje de error claro, sin intentar reintentos silenciosos.
- **Ningún match de nombre**: `"no encontrado"`, con sugerencias de baja
  similitud si las hay.
- **Filas de `Detalle` con `N° Ref.` sin `Master` correspondiente, o con
  `Fecha` no parseable**: excluidas de la agregación, se informa cuántas se
  excluyeron para que el resultado no parezca completo cuando no lo es.

## Testing

Con datos de ejemplo controlados (no el `Centro de Costos.xlsx` real, no
llamadas reales a `mindicador.cl` — la función que llama a la API se mockea
en tests):
- Fuzzy match encuentra variantes razonables (typos, singular/plural) y
  rechaza términos no relacionados.
- Cálculo de reajuste UF es aritméticamente correcto dado un par fijo de
  valores UF.
- Agregación de rango/promedio es correcta con varias compras del mismo
  ítem en fechas distintas.
- Caso "no encontrado" y caso de sugerencias por baja similitud.
- Filas excluidas por `N° Ref.` sin `Master` o fecha no parseable no entran
  a la agregación y se cuentan correctamente.

## Fuera de alcance (para más adelante)

- Integrar una fuente de cotizaciones (presupuestos no comprados) cuando
  exista en algún formato estructurado.
- Respaldo por `Categoría Ítem` cuando no hay match de nombre — descartado
  explícitamente para v1 por el usuario.
- Otros índices de reajuste (IPC, dólar) — solo UF por ahora.
