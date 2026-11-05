# Portal — Exportar la cotización a un proyecto

Detalle de referencia: léelo solo al tocar esta parte. Las reglas generales están en `../CLAUDE.md`.

**Exportar la cotización a un proyecto** (2026-10-29, pedido del usuario: que el carrito del Cotizador Histórico exporte
sus costos a un proyecto específico en formulación o en ejecución; 2026-10-30: una categoría por ítem, y reemplaza a «Copiar
para el Formulador»). No es una vista: es el diálogo `#dlgLlevar`, funciones `ll*`, estado `ll`.

- **Cómo llega**: el botón «Exportar a un proyecto…» del carrito manda sus líneas como mensaje `quempin-cotizacion` (ver
  `Cotizador Historico/Visualizador Web/CLAUDE.md`). Se atiende solo si viene del mismo sitio y de una herramienta
  abierta aquí dentro o de la pestaña que abrió el Portal; abierto como `…/portal/#/llevar-cotizacion`, el Portal le avisa
  `quempin-portal-listo` a esa pestaña y quita el `#`. Lo que llega se valida (`llLeer`) y vive solo en `ll.datos` mientras
  el diálogo está abierto: la cotización no se guarda en el navegador.
- **El diálogo**: resumen, sus líneas con la categoría de cada una (Materiales, Equipos u Otros, y se cambia ahí mismo), un
  buscador y los proyectos en dos grupos: **En ejecución** (`ejTarjetas`,
  solo si la cotización está en pesos: esa vista lleva sus cuentas en CLP) y **En formulación** (los del Recorrido con
  formulación antes de ofertar, sin los antiguos, en la moneda de la cotización: el Formulador no convierte). Queda elegido
  el proyecto de arriba del portal, o el único posible. Sin la biblioteca conectada dice qué falta (`pintarSinCarpeta`).
- **La categoría de cada ítem** (`llCategoria`): la del Centro de Costos de su compra pasada por `LL_BUCKET`, copia de la tabla
  `MAPEO_CATEGORIA_BUCKET` del Análisis Financiero que `test_portal.py` compara, para que coincida con cómo allá se reparte el
  gasto real: Seguridad Industrial y Oficina caen en Otros, y todo Arriendo en Equipos. Una categoría que la tabla no tiene va
  a Otros, como allá. **Un ítem sin categoría va a Materiales** (pedido del usuario).
- **En ejecución**: cada línea entra como gasto por decidir y simulado, en su categoría (`ejPoner`, se deshace con el aviso),
  con el proveedor de la compra, `ref` = la hoja del Cotizador, la línea del presupuesto más parecida y una nota con la fecha y el
  N° Ref. de la compra. No llega al Centro de Costos. La vista se abre en ese proyecto.
- **En formulación**: abre el Formulador en `#/p/<uid>/<tabla>`, la primera tabla que recibe algo (la dirección que la
  pestaña recuerda no lleva la cotización) y, cuando ya muestra ese proyecto en esa tabla, sin candado ni diálogo encima
  (`llEntregar`, hasta 3 minutos), le manda `quempin-costos-cotizacion` con las filas, cada una con su tabla. El Formulador
  abre un solo diálogo con todas: ahí se elige la partida, se puede cambiar la categoría y se agregan (`js/app.js`,
  `traerCostos`; acota lo que llega `QPegar.filasTraidas`).
- **Pruebas**: desde `test_la_categoria_propuesta_sale_de_la_tabla_del_analisis_financiero` en `test_portal.py` (datos de
  mentira); la del Formulador es `.prueba/pegar/portal.js` en su repositorio.
