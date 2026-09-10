---
name: Actualizar_Cotizador
description: Use when the user types "/Actualizar_Cotizador" explicitly. If the user instead says "actualiza el cotizador", "actualiza cotizador historico", "actualiza el visualizador/dashboard del cotizador" or similar natural language without the leading "/", ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills) — never auto-invoke. Regenera el visualizador de Cotizador Histórico y lo republica en GitHub Pages con los documentos más recientes de Centro de Costos y la UF del día, para que el link publicado nunca quede desactualizado. A diferencia de Centro de Costos/Análisis Financiero, este módulo nunca escribe datos (es de solo lectura sobre Centro de Costos.xlsx), así que no hay un paso "run" que decida si algo cambió — regenerar el visualizador siempre tiene sentido cuando se pide.
---

# Actualizar Cotizador (Cotizador Histórico + dashboard publicado)

Procedimiento común de los tres skills `/Actualizar_<módulo>` (por qué
existen, los cuatro pasos, cuándo no aplica) en
[`docs/actualizar-un-modulo.md`](../../../../docs/actualizar-un-modulo.md).
Acá va solo lo propio del Cotizador.

**Este módulo no escribe datos**: es de solo lectura sobre
`Centro de Costos.xlsx`, así que no hay un paso `run` que decida si algo
cambió. Regenerar el visualizador siempre tiene sentido cuando se pide, y
siempre es seguro y barato — salvo que falle `mindicador.cl`, ver abajo.

## Lo específico de este módulo

**Driver**: `Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py`
**Subruta al publicar**: `cotizador-historico`

**Paso 1 — `status`**: confirma que `Centro de Costos.xlsx` existe, cuántos
ítems quedan excluidos del índice (sin fecha resoluble, precio inválido, o
Notas de Crédito/devoluciones), y si hay conexión a `mindicador.cl`.

**Paso 2 — regenerar** (reemplaza al `run` de los otros dos):
```
python "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" visualizador
```

### Si falla por `mindicador.cl` caído

Pedido explícito del usuario, 2026-08-20; mecanismo completo en
[`../../CLAUDE.md`](../../CLAUDE.md) § Precauciones. El visualizador necesita
la UF de **hoy**, que nunca se cachea. `mindicador.cl` sigue siendo la fuente
prioritaria — intentarla siempre primero — pero si no responde, **no te
detengas a avisar sin más**:

1. Busca en internet (`WebSearch`) el valor de la UF de **hoy** en una fuente
   confiable (Banco Central de Chile, SII, o un sitio financiero reconocido).
   Nunca lo inventes ni uses un valor viejo de `uf_cache.json` — ese caché es
   solo para fechas históricas de compras, no para "hoy".
2. Reintenta con el valor y su fuente:
   ```
   python "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" visualizador --uf-manual VALOR --uf-fuente "<de dónde salió, ej. Banco Central de Chile, DD-MM-AAAA>"
   ```
   Queda marcado en el snapshot (`uf_fuente`) y visible en el visualizador
   publicado junto a "UF utilizada" — nunca se publica un valor manual sin
   dejar constancia de su origen.
3. Solo si no encuentras un valor confiable por ningún medio, recién ahí
   avisa al usuario y detente: sin la UF de hoy no se puede regenerar.

**Paso 4 — reportar**: incluir cuántos ítems quedan indexados/excluidos
(del `status`).

## Cuándo NO aplica (además de lo común)

Si el usuario solo pide una cotización puntual ("¿cuánto debería costar un
taladro?"), usa `/Cotizador_Historico` (`consultar`) directo — no hace falta
tocar el dashboard para responder una consulta conversacional.
