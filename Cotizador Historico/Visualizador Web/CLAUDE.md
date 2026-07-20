# CLAUDE.md — Visualizador Web de Cotizador Historico

Contenido a presentar en el HTML del visualizador de **Cotizador
Historico**. Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de
datos, hosting) — este archivo solo cubre el contenido específico de este
módulo. Ver también [`../CLAUDE.md`](../CLAUDE.md) para el detalle completo
de la lógica de búsqueda difusa y reajuste por UF que este visualizador
expone.

**Estado: borrador de contenido, sin HTML todavía.** Este archivo es el
espacio de trabajo para refinar qué mostrar antes de construir la interfaz.

## Fuente de datos

Misma `Centro de Costos/Excel/Centro de Costos.xlsx` (hojas `Master` +
`Detalle`), vía la lógica de `Sistema/cotizador_historico.py`
(`cargar_items_detalle`, `buscar_items`, reajuste por UF). Este módulo es
de solo lectura — el visualizador tampoco escribe nada.

## Buscador difuso de ítem

Campo de texto libre que reproduce `buscar_items`: búsqueda difusa contra
`Nombre Ítem` y `Descripción`. Si no hay match, mostrar las sugerencias de
baja similitud igual que hace el driver hoy (`status`/`consultar`).

## Vista de resultado

Para el ítem consultado:

- Lista de compras individuales encontradas: fecha, proyecto, proveedor,
  precio unitario original, precio ajustado por UF (sin IVA y con IVA
  usando la tasa real del documento).
- Promedio de los precios ajustados.
- Rango (mínimo-máximo) de precio ajustado sin IVA.

## Gráfico

Línea de evolución: precio ajustado por UF en el tiempo, un punto por
compra encontrada para el ítem consultado (eje X = fecha de la compra, eje
Y = precio ajustado a la fecha de hoy).

## Filtros

- Proyecto de origen de la compra.
- Rango de fechas de la compra.

## Export saneado sugerido (`data/cotizador-historico.json`)

Snapshot de ítems indexados: nombre, descripción, categoría, precio
unitario sin IVA, fecha de la compra, proyecto, y el valor de UF ya
resuelto para esa fecha histórica (evita depender de la API de
`mindicador.cl` en vivo desde el navegador). El reajuste a "hoy" se
recalcula client-side contra la UF del día, que si se requiere en vivo
necesita su propia llamada — a decidir si se pide en el momento (requiere
que el visualizador tenga acceso a internet más allá de servir el HTML
estático) o si se muestra "ajustado a la fecha del último export" con una
fecha visible de corte.

## Consultor IA (opcional, no obligatorio para la v1)

Si se implementa, debería responder preguntas del tipo "¿cuánto debería
costar hoy un taladro?" contra el export saneado, replicando la lógica de
`consultar_item` pero sirviéndola desde datos ya exportados.
