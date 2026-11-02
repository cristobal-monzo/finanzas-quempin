# CLAUDE.md — Tablero del Cotizador Histórico Perú

Usa la plantilla, el motor de búsqueda y la taxonomía de Chile:
[`../../../Cotizador Historico/Visualizador Web/CLAUDE.md`](../../../Cotizador%20Historico/Visualizador%20Web/CLAUDE.md). Aquí solo
vive su `build_visualizador.py`, con lo propio del país en `PLANTILLA_PAIS`.

- **Datos**: `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx` (`ch.cargar_items_detalle(pais="PE")`), nunca el de Chile.
- **Sin reajuste por índice**: Perú no tiene un equivalente a la UF. `precio_reajustado_hoy` existe, para reutilizar la lógica, y
  es igual a `precio_original_sin_iva` (`ch.armar_compra_sin_reajuste`). El snapshot no trae `uf_hoy`, `uf_fecha` ni `uf_fuente`; en
  lugar del KPI de la UF va «Moneda: S/ Soles».
- **Moneda**: PEN, `Intl.NumberFormat('es-PE')`.
- **Build**: `py -3.14 driver.py visualizador --pais PE`, desde `Cotizador Historico/.claude/skills/Cotizador_Historico/`.
- **URL**: `cotizador-historico-peru`.
