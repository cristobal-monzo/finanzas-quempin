# CLAUDE.md

## Rol de este agente

Este repositorio es la base de un **agente de automatización financiera para QUEMPIN SpA**. Su propósito es ayudar a construir y mantener herramientas que digitalizan y ordenan procesos financieros de la empresa que hoy se llevan en Excel/carpetas manuales.

El agente no resuelve un único proceso: está pensado para crecer como un conjunto de **módulos interconectados** (cada uno modela una pieza del sistema financiero de la empresa) que comparten convenciones y, eventualmente, se referencian entre sí (por ejemplo, un Centro de Costos que alimenta un Flujo de Caja, que a su vez alimenta un presupuesto consolidado).

Cuando trabajes en este proyecto, ten presente ese objetivo de largo plazo: cada módulo nuevo debería poder integrarse con los existentes, no ser una solución aislada.

## Estado actual

Hoy existe **un solo módulo implementado: Centro de Costos**. Es el caso de referencia para cómo deberían construirse los módulos futuros (estructura de carpetas, manejo de Excel, idempotencia, formato de reportes).

Módulos planeados a futuro (aún no implementados, mencionados por el usuario como dirección del proyecto):
- **Flujo de Caja**
- Otros módulos financieros por definir, que probablemente consuman datos del Centro de Costos (ej. totales por proyecto, montos por proveedor).

### Skill: `/Registro_Centro_de_Costos`

Centro de Costos ya está formalizado como skill de Claude Code en
[.claude/skills/Registro_Centro_de_Costos/](.claude/skills/Registro_Centro_de_Costos/SKILL.md)
(hasta 2026-07-16 se llamaba `run-centro-de-costos`). Expone un driver (`driver.py`) con dos comandos:
- `status` — solo lectura: inventaría documentos, dice qué se registraría y corre la verificación aritmética, sin tocar el Excel.
- `run` — ejecución real (equivalente a `python Sistema/auditor_centro_costos.py`): backup + escritura, idempotente.

La carpeta del skill también tiene dos archivos que complementan a
`SKILL.md` (que documenta solo el procedimiento estable):
- [MEMORY.md](.claude/skills/Registro_Centro_de_Costos/MEMORY.md) —
  preferencias (colores, formato), datos importantes de facturas/
  proveedores, historial de corridas reales y pendientes que dependen del
  usuario.
- [ERRORES.md](.claude/skills/Registro_Centro_de_Costos/ERRORES.md) —
  historial de errores del pipeline (celdas rojas, inconsistencias) y
  bitácora de correcciones manuales hechas directo en el Excel (pensada
  para eventualmente recolorearlas de rojo a azul marino oscuro al
  actualizar el CC; por decisión del usuario, 2026-07-16, esa parte queda
  en pausa por ahora — solo se registra, no se recolorea).

Es el patrón de referencia para futuros módulos (Flujo de Caja, etc.): cada uno debería terminar con su propia skill `Registro_<módulo>` siguiendo esta misma estructura (driver con modo `status` de solo lectura + modo `run`).

### Historia: reconstrucción de julio 2026

Hasta el 2026-07-15 existió un pipeline más avanzado (`build.py`, `rename.py`,
`detectar_duplicados.py`, `verify.py`, `revisar_ediciones.py`) que corría en una
carpeta separada (`OneDrive - QUEMPIN SPA/Plantillas/`, fuera de este módulo) y
producía una estructura de Excel mucho más rica que la que generaba entonces
`auditor_centro_costos.py` aquí. Esos scripts se perdieron (no quedó copia en
disco) antes de integrarse a este módulo; solo sobrevivió su resultado: el
`Centro de Costos.xlsx` con la estructura rica, más un respaldo de las fotos
originales.

El 2026-07-16 se reconstruyó `auditor_centro_costos.py` desde cero, leyendo esa
estructura rica directamente del `.xlsx` sobreviviente, para que el módulo
pueda seguir alimentándola sin depender del pipeline perdido. Esta carpeta
(`Finanzas QUEMPIN/Centro de Costos/`) quedó como la ubicación canónica única
de aquí en adelante — `Sitio de comunicación - Centro de costos` y `Plantillas/`
quedaron con copias desactualizadas/parciales, no se les debe escribir más.
Ver "Estructura de `Centro de Costos.xlsx`" más abajo para el detalle de la
estructura reconstruida, y `reconciliacion_archivos.json` para el mapeo de
bootstrap que permitió reconocer los 24 documentos ya existentes sin volver a
registrarlos.

## Estructura del repositorio

```
/
├── CLAUDE.md                              # este archivo
├── Excel/
│   ├── Centro de Costos.xlsx              # libro maestro (Master + Detalle + hoja por proyecto)
│   └── Respaldos/                         # backups automáticos con timestamp (generados por el script) + manuales
├── Facturas y Boletas/                    # documentos fuente (facturas/boletas), un subdirectorio por proyecto
│   ├── UMAG/
│   ├── Cesfam Limache/
│   └── Gastos Generales/
├── Sistema/
│   ├── auditor_centro_costos.py           # script principal del módulo Centro de Costos
│   ├── datos_extraidos.json               # datos ya extraídos de facturas/boletas (input del script), esquema con ítems de línea
│   ├── reconciliacion_archivos.json       # bootstrap: archivo original -> N° Ref para los 24 documentos que ya existían al reconstruir la estructura rica (2026-07-16)
│   ├── Formato.md                         # patrón GENÉRICO de formato (reutilizable por módulos futuros)
│   ├── Formato Centro de Costos.md        # formato REAL específico de este módulo: colores, columnas, filtros, validaciones
│   ├── Legado/                            # archivos históricos que el script ya no lee, conservados por trazabilidad
│   │   └── datos_extraidos_legacy_umag.json   # esquema simple anterior (22 docs UMAG), archivado
│   └── tests/                             # tests de pytest del módulo
├── docs/superpowers/                      # specs/plans de Claude Code (brainstorming/writing-plans)
└── .claude/
    ├── settings.json
    └── skills/Registro_Centro_de_Costos/  # skill /Registro_Centro_de_Costos (antes /run-centro-de-costos)
```

Reorganizado el 2026-07-16 (ver `docs/superpowers/specs/2026-07-16-reorganizacion-carpetas-design.md`)
para que la raíz sea navegable para un usuario no técnico: `Excel/` contiene
el único archivo que se abre a mano (`Centro de Costos.xlsx`), `Facturas y
Boletas/` son las fuentes, y `Sistema/` agrupa todo lo técnico
(script, JSON de entrada, docs de formato, tests, legado).

Renombrado el 2026-07-17: `Documentos Centro de Costos/` pasó a llamarse
`Facturas y Boletas/` (mismo contenido, mismo rol).

`Facturas y Boletas/<Proyecto>/` es la unidad de organización: cada subcarpeta de primer nivel es un **proyecto/centro de costos**. Agregar un proyecto nuevo es tan simple como crear la subcarpeta y dejar caer los documentos ahí — el script los detecta solo (aunque para que el `N° Ref.` tenga un prefijo elegido por ti, agrégalo a `PREFIJOS_PROYECTO` en `Sistema/auditor_centro_costos.py`; si no, usa uno derivado automático y avisa por consola).

## Módulo: Centro de Costos

### Qué hace

`Sistema/auditor_centro_costos.py` mantiene `Excel/Centro de Costos.xlsx` sincronizado con los documentos (facturas/boletas) que se van agregando a `Facturas y Boletas/<Proyecto>/`. No hace OCR/extracción de datos por sí mismo: consume `Sistema/datos_extraidos.json`, que se asume ya poblado (por el usuario o por un paso de extracción previo, ej. IA leyendo las fotos de las facturas) con los datos estructurados de cada documento, **incluyendo el desglose en ítems de línea**.

Flujo de ejecución (`main()`):
1. **Backup** — copia `Excel/Centro de Costos.xlsx` a `Excel/Respaldos/Centro de Costos - backup <fecha> <hora>.xlsx` antes de tocar nada.
2. **Leer `Master`** — determina qué `N° Ref.` ya existen (y su secuencia máxima por proyecto), y qué archivos ya están cubiertos (columna "Archivo origen" de filas escritas por este script, más `Sistema/reconciliacion_archivos.json` para las filas preexistentes que no tienen esa columna poblada).
3. **Inventariar archivos** — recorre `Facturas y Boletas/`, clasifica cada archivo como pendiente / omitido (ya registrado).
4. **Cargar `Sistema/datos_extraidos.json`** y buscar la entrada de cada archivo pendiente (por `proyecto` + `archivo`).
5. **Escribir en Excel** por cada documento con datos completos (con `items`): asigna el siguiente `N° Ref.` del proyecto, escribe un renglón en `Detalle` por cada ítem de línea, y una fila-resumen en `Master` (con fórmulas `SUMIF`/suma hacia `Detalle`).
6. **Regenerar derivados** — los pies "TOTAL GENERAL" de `Master`/`Detalle` y las hojas de proyecto (100% fórmulas hacia `Master`, se recalculan completas cada corrida a partir de la columna `Proyecto` actual).
7. **Verificaciones aritméticas**: IVA = 19% del Neto (suma de ítems) para Facturas/Guías de Despacho (tolerancia ±1 CLP).
8. **Informe de auditoría** impreso en consola: alertas de legibilidad, inconsistencias aritméticas, posibles duplicados (mismo N° Documento en más de un archivo), limitaciones de registro (archivos sin datos, o sin `items`, en el JSON).

### Reglas de oro (no negociables)

- **Las filas de datos ya escritas no se vuelven a tocar**: ni los ítems en `Detalle` ni las filas de documento en `Master` (salvo sus columnas J/L, que son fórmulas siempre-derivadas y se dejan intactas si alguien ya las reemplazó a mano por un valor fijo). Es la regla de oro de esta versión — reemplaza al "solo anexa" de la versión simple anterior, porque la estructura rica sí tiene contenido derivado (fórmulas, pies de tabla, hojas de proyecto) que necesita regenerarse.
- **Idempotente**: correr el script sin documentos nuevos no modifica ninguna fila de datos (solo regenera pies de tabla y hojas de proyecto, que dan el mismo resultado si nada cambió en `Master`).
- **Backup siempre antes de escribir**: si vas a modificar la lógica de escritura, no rompas este paso.
- **Extensiones válidas**: `.png .jpg .jpeg .heic .pdf`. Se ignoran `.html .txt .ini .tmp` y `desktop.ini` (archivos de sincronización de OneDrive).
- Si el Excel está abierto en otra aplicación al momento de guardar, el script debe fallar con un mensaje claro (`PermissionError`), no corromper el archivo.
- **El formato que el usuario modifique a mano en el `.xlsx` se respeta entre corridas**: ancho de columnas, formato de casilla, columnas ocultas (siguen ocultas, pero el script las sigue leyendo/actualizando igual que antes). Desde 2026-07-16, `ajustar_anchos` solo fija el ancho de una columna si todavía no tiene uno, y `regenerar_hoja_proyecto` reutiliza la hoja de proyecto existente en vez de borrarla y recrearla — ver [Formato.md](Sistema/Formato.md) §8 (patrón genérico) y [Formato Centro de Costos.md](Sistema/Formato%20Centro%20de%20Costos.md) §3/§11 (verificación sobre el archivo real).

### Esquema de `datos_extraidos.json`

Lista de objetos, uno por documento, **con desglose en ítems de línea**:

```json
{
  "archivo": "IMG_9999.HEIC",
  "proyecto": "UMAG",
  "tipo_proyecto": "I+D+i",
  "fecha": "15/07/2026",
  "n_documento": "12345",
  "tipo_documento": "Factura",
  "proveedor": "Proveedor SpA",
  "categoria": "Materiales",
  "estado": "Pagado",
  "iva": 190,
  "items": [
    {"nombre_item": "Taladro inalámbrico", "descripcion": "Taladro percutor 20V 13mm s/carbones DCD7781", "categoria_item": "Equipos-Herramientas", "cantidad": 1, "p_unitario_sin_iva": 90000}
  ],
  "notas": "opcional: aclaraciones, cálculos derivados, ambigüedades del documento original"
}
```

- `"iva"` es opcional: si se omite, se calcula 19% del total sin IVA (suma de ítems) para Factura/Guía de Despacho, o 0 para el resto.
- `"tipo_proyecto"` es una clasificación a nivel proyecto (ej. `I+D+i`, `Mantenimiento`, `Gastos Generales`), constante para ese proyecto salvo que cambie deliberadamente.
- `"categoria"` es a nivel documento; `"categoria_item"` es a nivel ítem — pueden diferir si un documento mezcla categorías.
- **`"nombre_item"` = nombre simple y claro del producto** (ej. "Taladro inalámbrico"); **`"descripcion"` = el detalle** (modelo, medidas, especificaciones — ej. "Taladro percutor 20V 13mm s/carbones DCD7781"). **No anotar el código de producto** en ninguno de los dos campos (pedido 2026-07-16). "Resumen Ítems" en `Master` se arma uniendo los `nombre_item`, así que mantenerlo simple ahí también lo mantiene simple en `Master`.
- Si no se pudo leer el N° de documento, usar `"S/N (<archivo o nombre del voucher>)"` — el script pinta esa celda de rojo automáticamente para revisión manual.
- Ver `Sistema/Legado/datos_extraidos_legacy_umag.json` como referencia del esquema simple anterior (sin ítems) — ya no lo lee el script, solo queda como archivo histórico.

### Estructura de `Centro de Costos.xlsx`

Reconstruida el 2026-07-16 leyendo directamente el `.xlsx` resultante de un
pipeline anterior perdido (ver "Historia" más arriba). Tres tipos de hoja:

- **`Detalle`** — la hoja de edición real: una fila por **ítem de línea** de cada documento — `N° Ref., Proyecto, Tipo de Proyecto, N° Documento, Nombre Ítem, Descripción, Categoría Ítem, Cantidad, P. Unitario sin IVA, Total sin IVA (CLP)`. Varias filas comparten el mismo `N° Ref.` cuando un documento tiene varios ítems.
- **`Master`** — una fila por **documento** (no por proyecto) — `N° Ref., Proyecto, Tipo de Proyecto, Fecha, N° Documento, Tipo Documento, Proveedor, Proveedor (Razón Social), Categoría, Resumen Ítems, Total sin IVA (CLP), IVA 19% (CLP), Total con IVA (CLP), Estado, Archivo origen, Fecha modificación`. "Total sin IVA" es `=SUMIF(Detalle!$A:$A,$A<fila>,Detalle!$J:$J)` y "Total con IVA" es `=K<fila>+L<fila>` — ambas fórmulas, nunca valores fijos (a menos que alguien las reemplace a mano, en cuyo caso el script las respeta). Desde 2026-07-16, "Proveedor" muestra un **tag corto** (ej. "Shell") derivado de la razón social completa vía `TAGS_PROVEEDOR_CURADOS`/`generar_tag_proveedor()`; la razón social completa (ej. "Estaciones de Servicios Fandos Ltda. (Shell Ruta 68)") queda en la columna contigua "Proveedor (Razón Social)", **oculta**. Mismo par tag/razón social en cada hoja de proyecto. Ver `Sistema/Formato.md` §3/§14 e historial.
- **Una hoja de solo lectura por proyecto** (`UMAG`, `Cesfam Limache`, `Gastos Generales`, ...) — 100% fórmulas `=Master!<col><fila>` apuntando a las filas de `Master` cuya columna `Proyecto` calza con esa hoja. Se reconstruye completa en cada corrida, así que si reasignas a mano el proyecto de un documento en `Master`, su fila se mueve sola a la hoja correcta la próxima vez que corra el script.
- **`N° Ref.`** es la clave: `<PREFIJO>-<secuencia>` (ej. `UMAG-001`, `CFLI-002`), con prefijo fijo por proyecto en `PREFIJOS_PROYECTO` (`Sistema/auditor_centro_costos.py`).
- Cada proyecto tiene un color asignado de una paleta fija de 12 tonos pasteles, reutilizado de forma determinista (se lee de `Master` antes de asignar uno nuevo).
- Convención de colores de fuente (documentada también en la leyenda al pie de cada hoja): cursiva = editable a mano, rojo = requiere revisión, azul marino = corregido a mano (no se sobreescribe). Códigos hex exactos en [MEMORY.md](.claude/skills/Registro_Centro_de_Costos/MEMORY.md#preferencias-de-formato-y-color); detalle completo del formato real (columnas, anchos, filtros, validaciones, y dónde el formato heredado del pipeline perdido no coincide con lo que hace hoy el script) en [Formato Centro de Costos.md](Sistema/Formato%20Centro%20de%20Costos.md) (el patrón genérico reutilizable por futuros módulos está en [Formato.md](Sistema/Formato.md)). El recoloreo rojo→azul marino oscuro al corregir algo a mano todavía no está implementado (ni automático ni manual) — hoy solo se registra la corrección en [ERRORES.md](.claude/skills/Registro_Centro_de_Costos/ERRORES.md) como bitácora, en pausa por decisión del usuario.
- **Sí hay renombrado de fotos y conversión HEIC→JPG** (agregado el 2026-07-16, después de la reconstrucción inicial): cada `run` compara el nombre físico actual de cada documento contra el esperado (`<N° Ref.>_<TagProveedor>_<Fecha ISO>.<ext>`, `.heic`→`.jpg`) y renombra/convierte en disco si difiere, actualizando "Archivo origen" en `Master` — cubre documentos nuevos y, retroactivamente, los ya registrados (excepción explícita a la regla de oro, igual que `migrar_columna_proveedor()`). `status` muestra un preview de qué se renombraría sin tocar disco. `resolver_ruta_actual()` prueba primero "Archivo origen"; si esa ruta no existe en disco (caso de los 24 documentos del bootstrap, cuyo "Archivo origen" quedó con el nombre que les daba el pipeline perdido) cae al mapeo de `reconciliacion_archivos.json`, que apunta al archivo físico real — corregido 2026-07-17, ver `ERRORES.md`. Los 24 documentos del bootstrap ya se renombraron con este fix (22 UMAG + 1 Cesfam Limache + 1 Gastos Generales) a la convención `<N° Ref.>_<TagProveedor>_<Fecha ISO>`.

### Archivos auxiliares

- **`Excel/Respaldos/Centro de Costos - backup *.xlsx`**: se acumulan con cada corrida del script. Son desechables/limpiables, pero no borrar sin confirmar con el usuario (podrían ser el único respaldo de una corrida específica si el archivo principal se corrompe).
- **`Sistema/reconciliacion_archivos.json`**: mapeo de bootstrap (archivo original → N° Ref) para los 24 documentos que ya existían al reconstruir la estructura rica. No lo borres — sin él, esos 24 archivos se verían como "pendientes" en el próximo `status`/`run`. Los documentos registrados de aquí en adelante no lo necesitan.
- **`Sistema/Legado/datos_extraidos_legacy_umag.json`**: esquema simple anterior (sin ítems), ya no lo lee el script — solo queda como referencia histórica.

**`Sistema/Formato.md`**: patrón **genérico** de formato (estilo de encabezado, paleta, convención de colores, regla de oro, preservación de formato manual) pensado para reutilizarse en módulos futuros — no contiene datos específicos de este módulo.

**`Sistema/Formato Centro de Costos.md`**: registro del formato real **de este módulo** — colores, columnas, formatos de celda, dónde hay filtros/paneles inmovilizados/validaciones de datos, y las discrepancias entre lo que hace hoy el script y lo heredado del pipeline perdido (ver "Historia" arriba). Es un documento vivo: cada cambio de formato (a mano o por código) se registra ahí con fecha, no solo se pisa la sección correspondiente.

### Convenciones de carpetas auxiliares

- **`Excel/Respaldos/`**: copias de seguridad automáticas (una por cada `run`, incluso sin cambios) más cualquier backup manual. Desechables, pero no borrar sin confirmar con el usuario.
- **`Sistema/Legado/`**: archivos históricos que el script ya no lee, conservados solo por trazabilidad.

## Precauciones

- **Esta carpeta (`Finanzas QUEMPIN/Centro de Costos/`) es la ubicación canónica única** desde 2026-07-16. Existen otras dos copias con datos desactualizados/parciales — `OneDrive - QUEMPIN SPA/Sitio de comunicación - Centro de costos/` (estructura simple antigua) y `OneDrive - QUEMPIN SPA/Plantillas/` (donde corrió el pipeline perdido) — no se les debe escribir ni confiar en su "estado actual"; si necesitas consultarlas, verifica primero con el usuario.
- Esta carpeta igual vive dentro de OneDrive, sincronizada y potencialmente editada por más de una persona/dispositivo. Antes de sobrescribir el `.xlsx` principal, considera que puede haber cambios recientes hechos a mano fuera de este script (el propio script está diseñado para tolerarlo: nunca reescribe una fila de datos ya creada).
- `Sistema/datos_extraidos.json` y los documentos en `Facturas y Boletas/` contienen **datos financieros reales de la empresa** (montos, proveedores, N° de documentos tributarios). El código (`Sistema/auditor_centro_costos.py`, tests, skill) sí está versionado en git; estos datos están explícitamente excluidos vía `.gitignore` en la raíz de `Finanzas QUEMPIN/` — verifica ese archivo antes de asumir que algo nuevo bajo este módulo quedará (o no) fuera de control de versiones.
- El script reconfigura `stdout`/`stderr` a UTF-8 explícitamente por errores de encoding típicos de consola en Windows — mantener esa línea si se toca `main()`.
- Si aparece una carpeta `__pycache__/`, es caché de bytecode de Python (regenerable, seguro de borrar) — no es parte de la estructura intencional del módulo, no confundirla con datos.
