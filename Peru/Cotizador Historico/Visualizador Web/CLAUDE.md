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
