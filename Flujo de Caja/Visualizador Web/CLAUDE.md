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
- **Saldo inicial de prueba**: campo sobre el gráfico, con el del archivo
  por defecto; un valor distinto recalcula KPIs y gráfico, se recuerda solo
  en ese navegador (`fc_saldo_inicial`, junto con el oficial: si este
  cambia, la prueba se descarta) y «Volver a …» lo restablece.
- **Tabla**: movimientos con búsqueda, filtros por sentido, clase y mes,
  orden por columna; en móvil, tarjetas (`data-label`).
- **¿Cuánto de lo proyectado está respaldado?** (2026-10-14, bajo los KPIs):
  qué parte de lo proyectado desde el mes en curso sale de documentos (cuotas
  de cotizaciones, facturas y OC) y qué parte de estimaciones (ventas del AF
  con fecha estimada, costo por ejecutar y, si se marca la casilla, ofertas
  ponderadas), en una barra para ingresos y otra para egresos. Debajo, lo que
  lo mejora, desde `calidad` del snapshot (`flujo_caja.armar`): las
  cotizaciones sin N° de requerimiento, con dónde se corrigen (Historial de
  Sistema QUEMPIN › «Solo sin N° de requerimiento»), y si el saldo inicial es
  una estimación. Las notas de la corrida (`avisos`), que antes eran un bloque
  de viñetas arriba de todo, van plegadas al pie («Notas sobre los datos»).
- **Supuestos**: con un nombre legible (`NOMBRE_SUPUESTO` en el template); la
  clave de `parametros_flujo_caja.json` queda en el `title` de la celda.
