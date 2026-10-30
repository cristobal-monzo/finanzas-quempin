# Portal — Llevar la cotización a un proyecto

Detalle de referencia: léelo solo al tocar esta parte. Las reglas generales están en `../CLAUDE.md`.

**Llevar la cotización a un proyecto** (2026-10-29, pedido del usuario: que el carrito del Cotizador Histórico exporte
sus costos a un proyecto específico en formulación o en ejecución). No es una vista: es el diálogo `#dlgLlevar`, funciones
`ll*`, estado `ll`.

- **Cómo llega**: el botón «Llevar a un proyecto…» del carrito manda sus líneas como mensaje `quempin-cotizacion` (ver
  `Cotizador Historico/Visualizador Web/CLAUDE.md`). Se atiende solo si viene del mismo sitio y de una herramienta
  abierta aquí dentro o de la pestaña que abrió el Portal; abierto como `…/portal/#/llevar-cotizacion`, el Portal le avisa
  `quempin-portal-listo` a esa pestaña y quita el `#`. Lo que llega se valida (`llLeer`) y vive solo en `ll.datos` mientras
  el diálogo está abierto: la cotización no se guarda en el navegador.
- **El diálogo**: resumen, sus líneas, la categoría de todas (Materiales, Equipos u Otros; se propone la de más plata según
  la categoría del Centro de Costos de cada compra, con la tabla `MAPEO_CATEGORIA_BUCKET` del Análisis Financiero copiada
  en `LL_BUCKET`, que `test_portal.py` compara), un buscador y los proyectos en dos grupos: **En ejecución** (`ejTarjetas`,
  solo si la cotización está en pesos: esa vista lleva sus cuentas en CLP) y **En formulación** (los del Recorrido con
  formulación antes de ofertar, sin los antiguos, en la moneda de la cotización: el Formulador no convierte). Queda elegido
  el proyecto de arriba del portal, o el único posible. Sin la biblioteca conectada dice qué falta (`pintarSinCarpeta`).
- **En ejecución**: cada línea entra como gasto por decidir y simulado (`ejPoner`, se deshace con el aviso), con el
  proveedor de la compra, `ref` = la hoja del Cotizador, la línea del presupuesto más parecida y una nota con la fecha y el
  N° Ref. de la compra. No llega al Centro de Costos. La vista se abre en ese proyecto.
- **En formulación**: abre el Formulador en `#/p/<uid>/<tabla>` (la dirección que la pestaña recuerda no lleva la
  cotización) y, cuando ya muestra ese proyecto en esa tabla, sin candado ni diálogo encima (`llEntregar`, hasta 3 minutos),
  le manda `quempin-pegar-costos` con las filas en el formato de «Copiar para el Formulador». El Formulador abre su «Pegar
  desde Excel» con ellas: ahí se elige la partida y se agregan (`js/app.js`, `pegarFilas(list, llegada)`).
- **Pruebas**: desde `test_la_categoria_propuesta_sale_de_la_tabla_del_analisis_financiero` en `test_portal.py` (datos de
  mentira); la del Formulador es `.prueba/pegar/portal.js` en su repositorio.
