---
name: Actualizar_Cotizador
description: Use when the user says "actualiza el cotizador", "actualiza cotizador historico", "actualiza el visualizador/dashboard del cotizador" (loose natural-language phrasing, without a leading "/"), or wants el dashboard publicado de Cotizador Histórico refrescado con los documentos más recientes de Centro de Costos y la UF del día — regenera el visualizador y lo republica como el Claude Artifact existente, para que el link publicado nunca quede desactualizado. A diferencia de Centro de Costos/Análisis Financiero, este módulo nunca escribe datos (es de solo lectura sobre Centro de Costos.xlsx), así que no hay un paso "run" que decida si algo cambió — regenerar el visualizador siempre tiene sentido cuando se pide.
---

# Actualizar Cotizador (Cotizador Histórico + dashboard publicado)

Envoltorio de un solo comando sobre dos pasos que hoy existen por separado:
regenerar el visualizador de `/Cotizador_Historico` y luego **publicarlo**
como Artifact. Mismo patrón que `/Actualizar_CC` (Centro de Costos) y
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

2. **Regenerar el visualizador** (a menos que `status` haya mostrado que no
   hay conexión a `mindicador.cl` — en ese caso, avisar al usuario y
   detenerse; no se puede regenerar sin la UF de hoy):
   ```
   python "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" visualizador
   ```
   Esto reescribe `Visualizador Web/build/index.html` en disco con el
   catálogo completo indexado y la UF vigente incrustada.

3. **Publicar el Artifact**: usar el tool `Artifact` con `file_path`
   apuntando a `Cotizador Historico/Visualizador Web/build/index.html` y
   `url` igual al link fijo documentado en
   [Cotizador_Historico/MEMORY.md](../Cotizador_Historico/MEMORY.md)
   § Visualizador web (favicon 🧾, deliberadamente distinto al de Centro de
   Costos — mantenerlo igual siempre) — **nunca generar un link nuevo**. Si
   el tool pide ver la versión más reciente antes de sobrescribir, hacer un
   `WebFetch` de ese mismo URL primero.

4. **Reportar al usuario en una respuesta corta**: cuántos ítems quedan
   indexados/excluidos (del `status`), que se publicó el Artifact, y el
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
