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
  la fecha de cada ítem vía `N° Ref.` e incluye `total_sin_iva`/
  `total_con_iva` de esa misma fila; ítems sin `Master` correspondiente,
  con fecha no parseable, cuya celda `P. Unitario sin IVA` no es un número,
  o cuyo `P. Unitario sin IVA` es negativo, quedan con `excluido_motivo`
  poblado (`"sin_master"`, `"fecha_invalida"`, `"precio_invalido"` o
  `"precio_negativo"`) y no entran a ninguna búsqueda ni agregación.
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
- `consultar_item(texto_busqueda, ruta_excel=None, fecha_hoy=None)` —
  orquesta todo lo anterior y devuelve el resultado completo: compras
  individuales (con su ajuste sin IVA y con IVA), promedio de ambos, rango
  (sin IVA), y sugerencias si no hubo match.

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
- `Sistema/uf_cache.json` contiene solo valores públicos de UF (no datos
  financieros de la empresa) — a diferencia de los datos de Centro de
  Costos, no es sensible.
