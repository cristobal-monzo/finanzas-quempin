---
name: Cotizador_Historico
description: Estima el costo actual de un ítem desde sus compras en Centro de Costos, reajustado por UF, y regenera y publica su tablero. Usar SOLO si el usuario escribe "/Cotizador_Historico" (antes /Actualizar_Cotizador); si pregunta con palabras cuánto debería costar algo o pide una cotización aproximada, confirma primero, aunque sea de solo lectura.
---

# Cotizador Histórico

**Solo lectura** sobre `Centro de Costos.xlsx`. Las rutas son relativas a `Cotizador Historico/`; `driver.py` es
`.claude/skills/Cotizador_Historico/driver.py`, corrido con `py -3.14`. Reglas y diseño: `../../CLAUDE.md`.

| Comando | Red | Qué hace |
|---|---|---|
| `status` | prueba | Ítems indexables, excluidos (y por qué), fechas en el caché de UF, conexión a `mindicador.cl` |
| `consultar "<texto>"` | sí | Cada compra (fecha, N° Ref., precio original, ajuste sin y con IVA real), promedio, rango y tabla por hoja |
| `visualizador` | sí | Regenera `Visualizador Web/build/index.html` con la UF de hoy |
| `categorias [--detalle "<cat>"] [--top N]` | no | Distribución, cola `Sin Clasificar`, ítems que requieren medida y no la tienen |
| `atributos [--top N]` | no | Palabras sin interpretar con sugerencia, ambiguas, baja confianza (< 0,7), sin material o medida |
| `evaluacion [--detalle]` | no | Contra 203 productos etiquetados y 110 consultas sobre el texto crudo: material, dimensiones, P@1, P@5, Success@5, MRR |
| `benchmark [--detalle]` | no | 48 consultas sobre la clasificación del sistema: Success@5, P@5, MRR, contra el buscador anterior |
| `precios` | no | Publica los precios de referencia para el Formulador |
| `uf` | sí | Consulta la UF |

- `consultar` muestra la tabla por hoja cuando la búsqueda cae en más de una: **ese es el número que responde**, porque el
  promedio global mezcla productos. Si el texto trae una medida, filtra a esa medida y dice cuántas compras dejó fuera.
  Sin coincidencias: `No se encontraron compras para "<texto>".`, con sugerencias si las hay.
- Para responder en la conversación («¿cuánto debería costar un taladro?») usa `consultar` o `consultar_item` de
  `Sistema/cotizador_historico.py`: no hace falta tocar el tablero.
- **Tras tocar un catálogo**: `py -3.14 -m pytest` y `evaluacion` (distingue una mejora real de una que arregla un caso y
  rompe tres), `categorias` si fue la taxonomía y `benchmark` si fue la búsqueda, comparando que no se movió nada que ya
  estaba bien.

## Perú

`status`, `consultar` y `visualizador` aceptan `--pais PE`: leen `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx` y
**nunca reajustan por índice** ni llaman a `mindicador.cl`; el precio es el histórico en soles (`--uf-manual` se ignora).

## Publicar el tablero

Procedimiento común: [`docs/actualizar-un-modulo.md`](../../../../docs/actualizar-un-modulo.md). Lo propio: **no escribe
datos**, así que no hay `run` que decida si algo cambió; regenerar siempre es seguro.

1. `status`: confirma el Excel, los excluidos y la conexión.
2. `visualizador`.
3. Desde la raíz del repo, `py -3.14 "Visualizador Web/publicar.py" cot` y commit + push en `.worktrees/gh-pages`. Con
   «sin publicar», no publiques y avisa.
4. Reporta cuántos ítems quedan indexados y excluidos.

**Si falla por `mindicador.cl` caído**, no te detengas a avisar sin más:

1. Busca con `WebSearch` la UF de **hoy** en una fuente confiable (Banco Central, SII). Nunca la inventes ni uses un valor
   viejo de `uf_cache.json`, que es solo para fechas de compra.
2. Reintenta: `visualizador --uf-manual 39200.50 --uf-fuente "Banco Central de Chile, 20-08-2026"` (`consultar` también lo
   acepta). Queda en `uf_fuente` y a la vista junto a «UF utilizada».
3. Solo sin un valor confiable, avisa y detente.

## Cuidados

- **Ítems fuera del índice**: sin fecha resoluble, sin precio válido, Notas de Crédito (negativos) y líneas en $0 (cero
  exacto). `status` los cuenta: revisa ahí antes de suponer que la búsqueda falló. No revertir estos filtros.
- **Ningún ítem se oculta por no tener medida**: si no aparece donde debería, revisa `categorias`.
- **Sin cotizaciones**: solo ve compras realizadas (Factura, Boleta, Guía de Despacho en CC), no presupuestos.
- La taxonomía se edita en `Sistema/catalogo_taxonomia.py`, nunca en `template.html`.

| Síntoma | Causa y solución |
|---|---|
| `[ERROR] No existe .../Centro de Costos.xlsx` | Confirma que `Centro de Costos/Excel/Centro de Costos.xlsx` no se movió |
| `UFNoDisponibleError` | Sin la UF de HOY: es lo único que aborta la consulta. Usa `--uf-manual` y `--uf-fuente` (arriba), no reportes solo la falla |
| Faltan compras en el resultado | Aviso `[INFO] N compra(s)... se excluyeron`: esas fechas no se pudieron reajustar; el resto sí se muestra |
| Un ítem que existe no aparece | `status`: sin fila en `Master`, `Fecha` inválida, precio vacío o Nota de Crédito |
| `No module named 'openpyxl'` | Corriste con `python`: usa `py -3.14` |
| Ítem en la categoría equivocada | `categorias --detalle "<cat>"` y ajusta su regla en `catalogo_taxonomia.py`. Si una palabra genérica se lo lleva, sube `prioridad_extra` o escribe la frase completa: 2 palabras pesan más que 1 |
| Una hoja mezcla productos | Mira la dispersión en `consultar`: suele ser presentación distinta (unidad o pack) o una medida no leída. Ver el spec de la taxonomía |
| «Sin Clasificar» en el KPI | Es una cola de trabajo: `categorias` las lista para agregarles regla |
