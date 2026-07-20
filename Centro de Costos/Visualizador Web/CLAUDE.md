# CLAUDE.md — Visualizador Web de Centro de Costos

Contenido a presentar en el HTML del visualizador de **Centro de Costos**.
Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de
datos, hosting) — este archivo solo cubre el contenido específico de este
módulo. Ver también [`../CLAUDE.md`](../CLAUDE.md) para el detalle completo
de la estructura de `Centro de Costos.xlsx` que este visualizador consume.

**Estado: borrador de contenido, sin HTML todavía.** Este archivo es el
espacio de trabajo para refinar qué mostrar antes de construir la interfaz.

## Fuente de datos

`Centro de Costos/Excel/Centro de Costos.xlsx`, hojas `Master` (una fila
por documento) y `Detalle` (una fila por ítem de línea). Ver
`../CLAUDE.md` §"Estructura de `Centro de Costos.xlsx`" para el esquema
completo de columnas.

## KPIs (resumen en la parte superior)

- Gasto total (con IVA y sin IVA).
- Gasto por proyecto (los 5-8 proyectos activos).
- Gasto por categoría.
- Cantidad de documentos registrados.
- Documentos pendientes de revisión (celdas rojas / sin N° de documento
  legible) — conteo, no el detalle sensible.

## Tabla dinámica

Una fila por documento (`Master`), expandible a sus ítems (`Detalle`).
Columnas mínimas: N° Ref., Proyecto, Fecha, Proveedor (tag corto, no la
razón social completa — ver punto de saneado más abajo), Categoría, Total
con IVA, Estado. Ordenable por cualquier columna. Búsqueda de texto libre
sobre proveedor/ítem/N° de documento.

## Gráficos

- Barras: gasto por proyecto.
- Dona: gasto por categoría.
- Línea temporal: gasto mensual acumulado.
- Ranking: top 10 proveedores por monto.

## Filtros

- Proyecto.
- Tipo de proyecto (I+D+i, Mantenimiento, Gastos Generales, etc.).
- Categoría.
- Estado (Pagado/Pendiente/etc.).
- Rango de fechas.

## Export saneado sugerido (`data/centro-de-costos.json`)

Agregados por proyecto/categoría/mes/proveedor, más un detalle de
documento con las columnas de la tabla dinámica de arriba. Puntos a
decidir antes de generar el primer export real:

- ¿Se expone la razón social completa del proveedor, o solo el tag corto
  (ej. "Shell") que ya usa `Master`? Recomendado: solo el tag, salvo que el
  sitio quede con control de acceso resuelto (ver punto abierto del
  maestro).
- ¿Se incluyen los documentos marcados en rojo (pendientes de revisión),
  o se excluyen del export hasta que se corrijan?

## Consultor IA (opcional, no obligatorio para la v1)

Si se implementa, debería poder responder preguntas del tipo "¿cuánto
gastamos en UMAG en julio?" o "¿quién es el proveedor con más gasto
acumulado?" contra el export saneado — no contra el Excel fuente.
