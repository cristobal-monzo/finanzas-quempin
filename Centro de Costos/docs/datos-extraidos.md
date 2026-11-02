# Centro de Costos — esquema de `datos_extraidos.json`, con sus precedentes

Detalle de referencia: léelo solo al tocar esto. Las reglas vigentes están en `../CLAUDE.md`.

Lista de objetos, uno por documento, **con desglose en ítems de línea**.
**`"items"` debe traer CADA línea de la compra por separado, nunca un solo
ítem resumen por el total del documento** — incluso si eso significa una
lista larga para una factura con muchas líneas. Excepción explícita: si una
parte del documento es físicamente ilegible (timbre, doblez, foto cortada),
desglosa las líneas que sí se leen cada una por separado y agrupa SOLO las
ilegibles en 1 ítem aparte (ej. `"nombre_item": "Materiales varios"`) por el
saldo entre el Neto impreso y la suma de las líneas legibles — nunca agrupes
el documento completo en 1 ítem cuando alguna línea sí se puede leer (pedido
2026-07-17, precedente `CCON-004` en
[MEMORY.md](../.claude/skills/Registro_Centro_de_Costos/MEMORY.md) del skill):

```json
{
  "archivo": "IMG_9999.HEIC",
  "proyecto": "UMAG",
  "tipo_proyecto": "I+D+i",
  "fecha": "15-07-2026",
  "n_documento": "12345",
  "tipo_documento": "Factura",
  "proveedor": "Proveedor SpA",
  "rut_proveedor": "76.123.456-7",
  "categoria": "Materiales",
  "estado": "Pagado",
  "iva": 190,
  "items": [
    {"nombre_item": "Taladro inalámbrico", "descripcion": "Taladro percutor 20V 13mm s/carbones DCD7781", "categoria_item": "Equipos-Herramientas", "cantidad": 1, "p_unitario_sin_iva": 90000}
  ],
  "rotacion": 90,
  "notas": "opcional: aclaraciones, cálculos derivados, ambigüedades del documento original"
}
```

- **`"fecha"` va en formato `DD-MM-AAAA`** (guiones, orden día-mes-año — pedido del usuario 2026-07-28, reemplaza el `DD/MM/AAAA` con barras usado antes). El parser (`escribir_fila_master`/`fecha_ddmmaaaa_desde_valor` en `auditor_centro_costos.py`) sigue aceptando `DD/MM/AAAA` como fallback por si algo lo escribe a la antigua, pero las entradas nuevas deben usar guiones.
- `"iva"` es opcional: si se omite, se calcula 19% del total sin IVA (suma de ítems) para Factura/Guía de Despacho, o 0 para el resto.
- `"rut_proveedor"` es opcional (agregado 2026-09-07): el RUT del proveedor, si viene legible en el documento. No se escribe en el Excel (no hay columna para esto en `Master`), es solo una ayuda para el agente al registrar: **antes de fijar `"proveedor"` de un documento nuevo, hay que revisar si ya existe un proveedor conocido con el mismo RUT o un nombre muy similar** (buscar en `TAGS_PROVEEDOR_CURADOS` y en la columna oculta "Proveedor (Razón Social)" de `Master`/en entradas anteriores de este JSON) y, si lo hay, reusar exactamente esa razón social ya existente — no crear una variante nueva del mismo proveedor. Ver la regla completa (con el precedente que la motivó) en [MEMORY.md](../.claude/skills/Registro_Centro_de_Costos/MEMORY.md) § Reglas de negocio.
- `"tipo_proyecto"` es una clasificación a nivel proyecto (ej. `I+D+i`, `Mantenimiento`, `Gastos Generales`), constante para ese proyecto salvo que cambie deliberadamente.
- `"categoria"` es a nivel documento; `"categoria_item"` es a nivel ítem — pueden diferir si un documento mezcla categorías.
- **`"nombre_item"` = tipo de producto genérico, lo más simplificado posible** — sin marca ni adjetivos/variantes (ej. "Hidrolavadora", no "Hidrolavadora Karcher portátil"; "Taladro", no "Taladro inalámbrico") (pedido 2026-07-17, endurece la regla anterior). **`"descripcion"` = todo el detalle** (marca, modelo, medidas, especificaciones — ej. "Hidrolavadora Karcher portátil K3 120 bar", "Taladro percutor 20V 13mm s/carbones DCD7781"). **No anotar el código de producto** en ninguno de los dos campos (pedido 2026-07-16). "Resumen Ítems" en `Master` se arma uniendo los `nombre_item`, así que mantenerlo simplificado ahí también lo mantiene simple en `Master`.
- Si no se pudo leer el N° de documento, usar `"S/N (<archivo o nombre del voucher>)"` — el script pinta esa celda de rojo automáticamente para revisión manual.
- **`"rotacion"` es opcional** (agregado 2026-08-20): grados en **sentido horario** que hay que girar el archivo físico para que quede derecho (`90`, `180` o `270`). Un documento girado **nunca debe quedar fuera del JSON por ilegible solo por eso** — el agente lo lee igual (rotándolo mentalmente) y anota el ángulo aquí; `run` corrige el archivo en disco automáticamente al registrarlo (`rotar_si_corresponde` en `auditor_centro_costos.py`, ver PASO 6), una sola vez por documento — no hace falta rotarlo a mano antes. Se omite si el documento ya está bien orientado.
- Ver `Sistema/Legado/datos_extraidos_legacy_umag.json` como referencia del esquema simple anterior (sin ítems) — ya no lo lee el script, solo queda como archivo histórico.
- **Un archivo físico = 1 entrada = 1 documento**, siempre. Si una foto/PDF pendiente trae más de un documento tributario distinto en el mismo encuadre (ej. 2-3 boletas fotografiadas juntas, cada una con su propio N° de Documento), el agente lo separa automáticamente en el Paso 2 de `SKILL.md` con `driver.py separar` (pedido del usuario, 2026-09-08) — genera `<archivo>_1.<ext>`, `<archivo>_2.<ext>`, ... (duplicando sin recortar, cada copia conserva la foto completa) y respalda/borra el original, antes de agregar una entrada de JSON propia por cada copia. Nunca se agrupan varios documentos reales en 1 sola entrada con un ítem resumen. Ver `separar_documento_combinado()` en `auditor_centro_costos.py` y el Paso 2 de `SKILL.md` para el mecanismo completo.
  **Desde el 2026-09-30 la regla la hace cumplir el código, no solo este texto**: aun escrita, el libro llegó a tener 26 N° Ref. que juntaban 2-4 facturas/boletas (`"n_documento": "6799340 y 0002795546"`, impuesto sumado, la fecha de una sola), y se separaron a mano tres veces. Ahora una entrada cuyo `n_documento` junta varios números levanta `DOCUMENTOS_MEZCLADOS` (severidad `error`) y `run` **no la registra**. Para lo que ya esté registrado así existe `driver.py separar-registrado` (`ejecutar_separacion_registrados()`): mueve los ítems a un N° Ref. por documento sin cambiar el neto, y el hallazgo se cierra solo cuando cada número tiene su propia fila en `Master` (el JSON no se reescribe). No detecta boletas **sin** número juntas en una entrada (peajes `S/N` con varios tickets, como CVAL-002/003/005): esas siguen dependiendo del Paso 2.
