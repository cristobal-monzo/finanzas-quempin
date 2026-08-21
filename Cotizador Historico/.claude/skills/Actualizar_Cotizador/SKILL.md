---
name: Actualizar_Cotizador
description: Use when the user types "/Actualizar_Cotizador" explicitly. If the user instead says "actualiza el cotizador", "actualiza cotizador historico", "actualiza el visualizador/dashboard del cotizador" or similar natural language without the leading "/", ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills) — never auto-invoke. Regenera el visualizador de Cotizador Histórico y lo republica en GitHub Pages con los documentos más recientes de Centro de Costos y la UF del día, para que el link publicado nunca quede desactualizado. A diferencia de Centro de Costos/Análisis Financiero, este módulo nunca escribe datos (es de solo lectura sobre Centro de Costos.xlsx), así que no hay un paso "run" que decida si algo cambió — regenerar el visualizador siempre tiene sentido cuando se pide.
---

# Actualizar Cotizador (Cotizador Histórico + dashboard publicado)

Envoltorio de un solo comando sobre dos pasos que hoy existen por separado:
regenerar el visualizador de `/Cotizador_Historico` y luego **publicarlo**
en GitHub Pages (los Claude Artifacts que se usaban antes ya no se
actualizan, pedido explícito del usuario 2026-08-19). Mismo patrón que
`/Actualizar_CC` (Centro de Costos) y
`/Actualizar_AF` (Análisis Financiero), simplificado porque este módulo no
escribe ningún archivo: no hay "documentos nuevos" ni "carpetas por crear"
que decidan si conviene regenerar — el snapshot depende solo de lo que ya
haya en `Centro de Costos.xlsx` y de la UF del día, así que regenerar
siempre es seguro y barato (salvo que falle `mindicador.cl`, ver abajo).

## Pasos

1. **`status`** (solo lectura, diagnóstico) — usar el driver de
   `/Cotizador_Historico`:
   ```
   python "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" status
   ```
   Confirma que `Centro de Costos.xlsx` existe, cuántos ítems quedan
   excluidos del índice (sin fecha resoluble, precio inválido, o Notas de
   Crédito/devoluciones), y si hay conexión a `mindicador.cl` — el
   visualizador necesita la UF de **hoy**, que nunca se cachea y siempre se
   pide fresca.

2. **Regenerar el visualizador**:
   ```
   python "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" visualizador
   ```
   Esto reescribe `Visualizador Web/build/index.html` en disco con el
   catálogo completo indexado y la UF vigente incrustada.

   **Si falla por `mindicador.cl` caído** (pedido explícito del usuario,
   2026-08-20; mecanismo completo en
   [`../../CLAUDE.md`](../../CLAUDE.md) § Precauciones): no detenerse a
   avisarle al usuario sin más — `mindicador.cl` sigue siendo la fuente
   prioritaria (intentarla siempre primero, como hace el comando de
   arriba), pero si no responde, el agente debe:
   1. Buscar en internet (`WebSearch`) el valor de la UF de **hoy** en una
      fuente confiable (ej. Banco Central de Chile, SII, o un sitio
      financiero reconocido) — nunca inventarlo ni usar un valor cacheado
      antiguo de `uf_cache.json` (ese caché es solo para fechas históricas
      de compras, no para "hoy").
   2. Reintentar con el valor encontrado y su fuente:
      ```
      python "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" visualizador --uf-manual VALOR --uf-fuente "<de donde salio, ej. Banco Central de Chile, DD-MM-AAAA>"
      ```
      Esto queda marcado en el snapshot (`uf_fuente`) y visible en el
      visualizador publicado (sufijo "· fuente: ..." junto a "UF
      utilizada") — nunca se publica un valor manual sin dejar constancia
      de su origen.
   3. Si tampoco se encuentra un valor confiable por ningún medio, recién
      ahí avisar al usuario y detenerse — no se puede regenerar sin la UF
      de hoy.

3. **Publicar**. Receta y comandos exactos (subruta de este módulo:
   `cotizador-historico`) en
   [`../../../../Visualizador Web/CLAUDE.md`](../../../../Visualizador%20Web/CLAUDE.md)
   § Hosting (raíz del repo, no el `Visualizador Web/CLAUDE.md` de este
   módulo) — es la única copia de esta receta, no la dupliques acá.

4. **Reportar al usuario en una respuesta corta**: cuántos ítems quedan
   indexados/excluidos (del `status`), que se publicó en GitHub Pages, y el
   link (el mismo de siempre).

## Cuándo NO aplica

Si el usuario solo pide una cotización puntual ("¿cuánto debería costar un
taladro?"), usa `/Cotizador_Historico` (`consultar`) directo — no hace
falta tocar el dashboard publicado para responder una consulta
conversacional.

**Si el usuario pide actualizar TODO** ("actualiza las finanzas", "deja
todo al día"), usa `/Actualizar_Finanzas` (raíz del repo) en vez de este:
cubre los tres módulos y los tres tableros publicados, no solo Cotizador
Histórico. Este skill sigue siendo el correcto cuando el usuario nombra
explícitamente solo el Cotizador.
