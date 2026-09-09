# CLAUDE.md — Visualizador Web de Cotizador Histórico Perú

Mismo contenido/decisiones que
[`../../../Cotizador Historico/Visualizador Web/CLAUDE.md`](../../../Cotizador%20Historico/Visualizador%20Web/CLAUDE.md)
(taxonomía de categorías, carrito de cotización sin persistencia, export
por copiar/pegar, gate de contraseña) — este archivo solo documenta lo que
difiere para Perú.

## Qué difiere de la versión de Chile

- **Fuente de datos**: `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx`
  (vía `ch.cargar_items_detalle(pais="PE")`), nunca el Excel de Chile.
- **Sin reajuste por índice**: Perú no tiene un equivalente a la UF
  chilena (decisión 5 del spec de expansión a Perú) — el precio que
  muestra cada tarjeta/carrito/export es el histórico nominal en soles,
  tal cual estaba al momento de la compra. El campo JSON
  `precio_reajustado_hoy` sigue existiendo (mismo shape que Chile, para
  reutilizar toda la lógica de taxonomía/carrito/export sin cambios) pero
  para Perú siempre es idéntico a `precio_original_sin_iva` —
  `ch.armar_compra_sin_reajuste` en vez de `ch.reajustar_item`.
- **Sin KPI de "UF utilizada"**: reemplazado por un KPI estático "Moneda:
  S/ Soles — precios históricos, sin reajuste".
- **Moneda**: PEN (`S/`), `Intl.NumberFormat('es-PE', {currency:'PEN'})`.
- **Comando de build**: `python driver.py visualizador --pais PE` (desde
  `Cotizador Historico/.claude/skills/Cotizador_Historico/`).
- **Publicación**: URL propia `cotizador-historico-peru`.

## Estado

0 documentos al 2026-08-26 (Perú aún no tiene facturas/boletas
registradas en Centro de Costos) — el dashboard se publica igual, vacío,
listo para cuando empiecen a fluir documentos reales.

## Taxonomía compartida con Chile (2026-09-08)

Este template **ya no clasifica**: lee `categoria`/`subcategoria`/`familia`/
`material`/`medida`/`hoja` que el snapshot trae calculadas por
`../../../Cotizador Historico/Sistema/taxonomia.py`. Antes tenía su propia
copia en JavaScript de las listas de palabras clave, y **había divergido**
de la de Chile: nunca recibió la categoría Instrumentación agregada el
2026-08-31 (los manómetros y termocuplas peruanos seguían cayendo en
Válvulas y en Bombas). Ese es exactamente el problema que el cambio elimina
por construcción — hay una sola fuente y los dos países la comparten.

Para cambiar cómo se clasifica algo se edita
`Cotizador Historico/Sistema/catalogo_taxonomia.py` (una vez, para ambos
países) y se regeneran los dos builds. Ver
`../../../Cotizador Historico/docs/superpowers/specs/2026-09-08-taxonomia-cotizador-design.md`.
