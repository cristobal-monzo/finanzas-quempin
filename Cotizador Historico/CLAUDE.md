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
  compras de distinta cantidad).
- El reajuste es solo por UF (no IPC, no dólar) — valores obtenidos de la
  API pública `mindicador.cl`, con caché local de fechas históricas en
  `Sistema/uf_cache.json`. La UF del día de la consulta nunca se cachea
  entre corridas — siempre se pide fresca.
- Búsqueda de ítem por texto: difusa (`difflib`, stdlib) contra `Nombre
  Ítem` y `Descripción` de `Detalle`, sin dependencias nuevas.
- **Sin respaldo por categoría**: si no hay match de nombre, la respuesta es
  "no encontrado" (con sugerencias de baja similitud si las hay) — decisión
  explícita del usuario para v1, no un olvido.
- **No incluye cotizaciones** (presupuestos no comprados) — no existen hoy
  en un formato estructurado. Si aparecen más adelante, se integrarían como
  una fuente adicional junto a Centro de Costos, no reemplazándola (ver spec
  de diseño).

Diseño completo, incluyendo las alternativas consideradas:
[`docs/superpowers/specs/2026-07-17-cotizador-historico-design.md`](docs/superpowers/specs/2026-07-17-cotizador-historico-design.md).

## Estructura del módulo

```
Cotizador Historico/
├── CLAUDE.md                              # este archivo
├── docs/superpowers/                      # specs/plans de Claude Code
├── Sistema/
│   ├── cotizador_historico.py             # lógica: leer Excel, indexar, fuzzy search, reajuste UF
│   ├── uf_cache.json                      # caché fecha ISO -> valor UF (se crea solo en la primera corrida)
│   └── tests/                             # tests de pytest
└── .claude/
    └── skills/
        └── Cotizador_Historico/
            ├── SKILL.md
            └── driver.py                  # comandos: status | consultar "<texto>"
```

## Cómo se usa

Como skill de Claude Code: pedirlo conversacionalmente (ej. "¿cuánto
debería costar hoy un taladro?") o correr el driver directamente. Ver
[`.claude/skills/Cotizador_Historico/SKILL.md`](.claude/skills/Cotizador_Historico/SKILL.md)
para los comandos (`status`/`consultar`) y ejemplos de salida.

## Funciones clave de `Sistema/cotizador_historico.py`

- `cargar_items_detalle(ruta_excel=None)` — lee `Detalle`+`Master`, resuelve
  la fecha de cada ítem vía `N° Ref.`; ítems sin `Master` correspondiente o
  con fecha no parseable quedan con `excluido_motivo` poblado (`"sin_master"`
  o `"fecha_invalida"`) y no entran a ninguna búsqueda ni agregación.
- `buscar_items(items, texto_busqueda)` — búsqueda difusa contra `Nombre
  Ítem`/`Descripción`; devuelve `(coincidencias, sugerencias)`.
- `obtener_valor_uf(fecha, cache_uf)` / `consultar_uf_api(fecha)` — UF
  histórica cacheada localmente; la UF de "hoy" se pide siempre fresca vía
  `consultar_uf_api` directo (no pasa por el caché de archivo).
- `consultar_item(texto_busqueda, ruta_excel=None, fecha_hoy=None)` —
  orquesta todo lo anterior y devuelve el resultado completo: compras
  individuales, promedio, rango, y sugerencias si no hubo match.

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
  `Sistema/uf_cache.json` (incluida siempre la UF de hoy). Sin conexión,
  esas compras quedan fuera del resultado con un aviso claro — nunca se
  inventa un valor de UF.
- `Sistema/uf_cache.json` contiene solo valores públicos de UF (no datos
  financieros de la empresa) — a diferencia de los datos de Centro de
  Costos, no es sensible.
