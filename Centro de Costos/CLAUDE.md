# CLAUDE.md — Centro de Costos

`Sistema/auditor_centro_costos.py` mantiene `Excel/Centro de Costos.xlsx` al día con las
facturas y boletas de cada proyecto: una fila por documento en `Master`, una por ítem en
`Detalle` y una hoja de solo lectura por proyecto. No extrae datos: consume
`Sistema/datos_extraidos.json`, que llena el agente leyendo las fotos. El mismo código sirve a
Chile y Perú (`configurar_pais()`, `pais="CL"|"PE"`); Perú solo tiene sus datos en
`../Peru/Centro de Costos/`.

**El script pesa ~300 KB: nunca lo leas entero.** Busca la función con Grep; `Grep "PASO "` da
el mapa de `main()`.

| Tema | Detalle (léelo solo al tocarlo) |
|---|---|
| Flujo de `main()` paso a paso, columnas del libro, Sitio de comunicación, split por país | [docs/flujo-y-libro.md](docs/flujo-y-libro.md) |
| Proceso de errores, cuadre de impuesto y duplicados, con sus casos reales | [docs/proceso-errores.md](docs/proceso-errores.md) |
| Esquema del JSON con sus precedentes | [docs/datos-extraidos.md](docs/datos-extraidos.md) |
| Formato real del libro; patrón genérico | `Sistema/Formato Centro de Costos.md` (vivo: registra cada cambio con fecha); `Sistema/Formato.md` |
| Reglas de negocio de facturas y proveedores; bitácoras | `.claude/skills/Registro_Centro_de_Costos/MEMORY.md`; `HISTORIAL.md` y `ERRORES.md` (no los leas enteros: Grep) |
| Medir el proceso de errores | `Sistema/bench/README.md` |
| Origen del módulo (no hace falta para trabajar) | `HISTORIA.md` |

## Skills

- **`/Registro_Centro_de_Costos`**: `driver.py status` (solo lectura: inventario, qué se
  registraría, verificación aritmética) y `run` (respaldo + escritura, idempotente). Publica el
  tablero al terminar salvo «sin publicar» ([procedimiento común](../docs/actualizar-un-modulo.md)).
  Si `status` muestra documentos sin entrada en el JSON, el agente los completa antes de `run`
  (Paso 2 del `SKILL.md`): **ningún documento queda sin registrar solo porque falte el JSON**.
- **`/Revision_de_Errores`**: recorrido guiado de las celdas rojas de `Master` y de los ítems
  agrupados de `Detalle` (muestra la foto, pregunta y aplica). `corregir` y `desglosar` no reflejan
  al sitio compartido: **al terminar hay que correr `driver.py reflejar`**.

## Carpetas

| Ruta | Qué es |
|---|---|
| `Excel/Centro de Costos.xlsx` | El libro maestro: el único que el script escribe |
| `Excel/Respaldos/<Mes Año>/` | Respaldos automáticos de cada `run`. No borrar sin confirmar con el usuario |
| `Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/<Chile\|Perú>/<Proyecto>/` | **Fuente oficial** (`RAIZ_DOCS`, acceso directo de OneDrive a SharePoint): aquí suben los colegas |
| `Sitio de comunicación - Centro de Costos 1/Centro de Costos.xlsx` y `Centro de Costos Perú.xlsx` | Reflejo de solo lectura (PASO 12b; Perú desde 2026-11-02); lo abre el símbolo de carpeta del Portal. Si está bloqueado, `[WARN]` sin abortar |
| `Facturas y Boletas/` | Legado: el script no la lee. No se borra ni se deposita ahí |
| `Sistema/reconciliacion_archivos.json` | Mapeo de los 24 documentos del bootstrap y de las copias exactas. **No lo borres** o se verían como pendientes |
| `Sistema/correcciones_manuales.json` | Bitácora de correcciones (azul marino) |
| `Sistema/errores_detectados.json`, `ordenes_compra.json` | Registro de hallazgos y de OC; llevan montos: en `.gitignore` |
| `Sistema/Legado/` | Solo trazabilidad |

Un **proyecto** = una subcarpeta: basta crearla y dejar caer los documentos. Para que el `N° Ref.`
(`<PREFIJO>-<secuencia>`) tenga un prefijo elegido, agrégalo a `PREFIJOS_PROYECTO`; si no, se deriva
uno y se avisa por consola. **El prefijo es el TAG del proyecto en todas las herramientas: nunca se repite.**
Uno derivado salta los que ya usa otro proyecto (`registrar_duenos_prefijo`, desde Master): «280. UMAG - Conexión y PH
Lab 1» derivaba «UMAG», el de otro proyecto, y el Portal le sumaba sus costos (2026-11-03; ahora `UML1`).

**¡Cuidado con los nombres!** `Sitio de comunicación - Centro de Costos 1/` (dentro de este módulo) es
la fuente; `OneDrive - QUEMPIN SPA/Sitio de comunicación - Centro de costos/` (fuera, minúscula, sin
«1») y `OneDrive - QUEMPIN SPA/Plantillas/` son copias viejas: no las uses ni les escribas.

## Reglas de oro (no negociables)

- **El contenido de las filas ya escritas no se vuelve a tocar**, ni en `Detalle` ni en `Master`
  (salvo sus columnas J/L, fórmulas derivadas, que se respetan si alguien las fijó a mano). Su
  **posición** sí cambia: `reordenar_por_fecha` deja lo más reciente arriba en cada `run`.
- **Excepciones**: `eliminar_documento` (un documento registrado dos veces; reescribe las fórmulas K/M
  de las filas que suben, porque openpyxl no las traduce), el renombrado de archivos y las **órdenes de
  compra**: las escribe el script desde Sistema QUEMPIN y cambian cuando llega su factura (PASO 6B).
- **Idempotente**: sin documentos nuevos no cambia ninguna fila de datos.
- **Respaldo siempre antes de escribir.**
- Si el Excel está abierto, debe fallar con un mensaje claro (`PermissionError`), nunca corromperlo.
- **Se respeta el formato manual**: anchos, formato de casilla y columnas ocultas (se siguen leyendo).
- Extensiones válidas: `.png .jpg .jpeg .heic .pdf`; se ignoran `.html .txt .ini .tmp` y `desktop.ini`.
- `main()` reconfigura `stdout`/`stderr` a UTF-8 por la consola de Windows: mantén esa línea.
- Nombre físico: `<N° Ref.>_<TagProveedor>_<Fecha DD-MM-AAAA>.<ext>` (HEIC→JPG). `run` renombra y
  actualiza «Archivo origen»; `status` lo muestra sin tocar el disco.

## Órdenes de compra

PASO 3B: copia el PDF de cada OC (tipo 61) **con proyecto** a la carpeta del proyecto como `OC
<folio>.pdf` y la registra como documento (tipo «Orden de Compra», estado «Pendiente»); sin proyecto no
entra. PASO 6B (`cerrar_ordenes`): la factura **reemplaza** a su OC. Si las facturas suman su neto (±2 %),
la OC sale del libro y su PDF se archiva; si suman menos, queda por el saldo. Una factura es de una OC si
su entrada dice `"oc": "<folio>"` o, si ninguna lo dice, si es la **única** del mismo proyecto y proveedor
con neto a ±2 % y fechada desde 30 días antes. Si calzan varias no se adivina: se pide anotar `"oc"`.

## Esquema de `datos_extraidos.json`

Una entrada por documento (precedentes en [docs/datos-extraidos.md](docs/datos-extraidos.md)):

```json
{
  "archivo": "IMG_9999.HEIC", "proyecto": "UMAG", "tipo_proyecto": "I+D+i", "fecha": "15-07-2026",
  "n_documento": "12345", "tipo_documento": "Factura", "proveedor": "Proveedor SpA",
  "rut_proveedor": "76.123.456-7", "categoria": "Materiales", "estado": "Pagado", "iva": 190,
  "items": [{"nombre_item": "Taladro", "descripcion": "Taladro percutor 20V 13mm s/carbones DCD7781",
             "categoria_item": "Equipos-Herramientas", "cantidad": 1, "p_unitario_sin_iva": 90000}],
  "rotacion": 90, "notas": "opcional"
}
```

- **`items`: cada línea por separado, nunca un ítem resumen.** Si una parte es físicamente ilegible,
  agrupa solo esa parte en un ítem aparte («Materiales varios») por el saldo contra el Neto impreso.
- **Un archivo = una entrada = un documento.** Varios documentos en una foto se separan con `driver.py
  separar` (Paso 2). Un `n_documento` que junta varios números levanta `DOCUMENTOS_MEZCLADOS` y `run` no
  lo registra; lo ya registrado así se arregla con `driver.py separar-registrado`. No detecta boletas sin
  número juntas (peajes `S/N`): eso depende del Paso 2.
- **`nombre_item`**: tipo de producto genérico, sin marca ni adjetivos («Taladro», no «Taladro
  inalámbrico»). **`descripcion`**: todo el detalle. Sin código de producto en ninguno de los dos.
- **`fecha`**: `DD-MM-AAAA`, con guiones.
- **`iva`** (opcional): si falta, 19 % para Factura/Guía de Despacho y 0 para el resto. **Es la bolsa de
  todos los impuestos**: `Neto + iva` es el total pagado. **`otros_impuestos`** (opcional, preferido) dice
  cuánto no es IVA, y el cuadre pasa a ser exacto.
- **`rut_proveedor`** (opcional, no va al Excel): antes de fijar `proveedor`, busca uno conocido con ese RUT
  o nombre parecido (`TAGS_PROVEEDOR_CURADOS`, columna oculta «Proveedor (Razón Social)», entradas
  anteriores) y **reusa esa razón social exacta**.
- **`n_documento` ilegible**: `"S/N (<archivo>)"`, y la celda queda en rojo.
- **`rotacion`** (opcional): 90, 180 o 270 grados en sentido horario. Un documento girado nunca queda
  fuera por eso: se lee y se anota, y `run` corrige el archivo una sola vez.
- `tipo_proyecto` es por proyecto; `categoria` es por documento y `categoria_item` por ítem.

## Proceso de errores (resumen)

- `validar_documento()` / `validar_corpus()` corren **antes de escribir** (PASO 5B); `status` usa la misma
  función. Reutilízalas: no escribas otra validación. Una línea negativa en una factura es un descuento, no
  un error; lo que se marca es que el documento termine con neto ≤ 0.
- `Sistema/errores_detectados.json`: `id` estable (`sha1(codigo|proyecto\archivo|campo)`, con el `archivo`
  del JSON, no el físico) y estados `abierto` → `auto_resuelto` / `resuelto` / `descartado`. **Un hallazgo
  cerrado no se reabre mientras el dato de origen no cambie**; `datos_extraidos.json` es entrada y **no se
  reescribe nunca**.
- **Corregir**: `corregir_hallazgos()` (por lote, solo con un hallazgo abierto y columna en
  `COLUMNAS_CORREGIBLES`), `corregir_valor_manual()` y `corregir_item_detalle()` (el neto vive en `Detalle`).
  Todas dejan rastro: azul marino + `correcciones_manuales.json` + `ERRORES.md`. Editar el `.xlsx` a mano no
  deja constancia. La fila de un hallazgo se encuentra por el N° Documento (`mapa_documento_a_n_ref()`),
  nunca por el nombre del archivo.
- **Copias exactas** (mismo emisor, número, tipo, fecha y neto) se resuelven solas; si algo difiere es
  `DUPLICADO_AMBIGUO` y decide una persona. `IMPUESTO_ESTIMADO` solo lo cierra una persona.
- **Tipo de documento**: compara siempre con `es_documento_afecto()` / `clave_tipo_documento()`, nunca con el
  literal (entra con y sin tilde). `es_n_documento_real()` filtra `N/A` y `S/N`; un duplicado exige el mismo
  emisor.
- **Severidades** (`severidad_cuadre_impuesto()`): `error` (único que pinta rojo), `revisar`, `estimado`. En
  `CATEGORIAS_CON_IMPUESTO_ESPECIFICO` (Combustible) el impuesto puede quedar a ambos lados del 19 %.
- **Si tocas este proceso**, corre `Sistema/bench/` antes y después, y prueba también sobre un corpus ya
  registrado: el banco parte vacío y en producción no se escribe ninguna fila.

## Datos

`datos_extraidos.json`, los documentos y el libro son **datos financieros reales**, excluidos por `.gitignore`
(también toda la carpeta `Sitio de comunicación…`). Verifica ese archivo antes de asumir que algo nuevo queda
fuera. Es una carpeta de OneDrive y los colegas suben documentos ahí: considera cambios hechos a mano fuera del
script.
