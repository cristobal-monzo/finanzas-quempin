# CLAUDE.md — Visualizador Web de Flujo de Caja

Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, política de datos, hosting) y el módulo en
[`../CLAUDE.md`](../CLAUDE.md).

- **Fuente de datos**: `flujo_caja.armar()` — la misma función que escribe el
  Excel. `build_visualizador.py` guarda el snapshot en `data/flujo-caja.json`
  y la página en `build/index.html` (ambos gitignoreados).
- **Marca**: fuentes Lato y logo desde `brand.py` de Análisis Financiero
  (`cargar_font_face_lato()`, `cargar_logo_base64()`), no copiados aquí.
  Tokens de color, cabecera, gate y navegación iguales a los demás tableros.
- **Navegación**: la pestaña «Flujo de Caja» está en los 6 templates
  (`test_navegacion_tableros.py`). Solo existe para Chile: su pestaña apunta
  siempre a Chile y elegir Perú desde aquí lleva a Centro de Costos Perú.
- **KPIs**: por cobrar, por pagar y por ejecutar, neto proyectado, mes más
  ajustado (acumulado más bajo).
- **Gráfico**: barras apiladas por mes (ingresos arriba, egresos abajo) con el
  acumulado como línea; se dibuja al ancho real del panel. Las ofertas por
  adjudicar se suman solo si se marca la casilla (desmarcada por defecto).
- **Tabla**: movimientos con búsqueda, filtros por sentido, clase y mes,
  orden por columna; en móvil, tarjetas (`data-label`).
- **Supuestos y avisos**: se muestran tal como vienen del cálculo.
