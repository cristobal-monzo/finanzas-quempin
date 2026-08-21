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
  reglas de negocio vigentes, datos importantes de facturas/proveedores y
  pendientes que dependen del usuario (el historial fechado de corridas
  reales se separó a
  [HISTORIAL.md](.claude/skills/Registro_Centro_de_Costos/HISTORIAL.md) el
  2026-07-27, para que MEMORY.md no crezca sin límite).
- [ERRORES.md](.claude/skills/Registro_Centro_de_Costos/ERRORES.md) —
  historial de errores del pipeline (celdas rojas, inconsistencias) y
  bitácora de correcciones manuales hechas directo en el Excel (pensada
  para eventualmente recolorearlas de rojo a azul marino oscuro al
  actualizar el CC; por decisión del usuario, 2026-07-16, esa parte queda
  en pausa por ahora — solo se registra, no se recolorea).

Es el patrón de referencia para futuros módulos (Flujo de Caja, etc.): cada uno debería terminar con su propia skill `Registro_<módulo>` siguiendo esta misma estructura (driver con modo `status` de solo lectura + modo `run`).

### Skill: `/Revision_de_Errores`

Complementa a `/Registro_Centro_de_Costos` — agregada 2026-07-17 en
[.claude/skills/Revision_de_Errores/](.claude/skills/Revision_de_Errores/SKILL.md).
Recorrido guiado, uno por uno, de las celdas de `Master` actualmente en rojo
(`listar_celdas_rojas()`): el agente muestra la foto del documento asociado,
pregunta al usuario el valor correcto en la conversación, y lo aplica de
inmediato con `corregir_valor_manual()` — recolorea la celda a azul marino
oscuro, propaga a `Detalle` si corresponde, y la registra como "Aplicado" en
`Sistema/correcciones_manuales.json` + la tabla de
[ERRORES.md](.claude/skills/Registro_Centro_de_Costos/ERRORES.md). Mismo
destino final que el flujo `run` → `confirmar` de `Registro_Centro_de_Costos`
(ver más abajo), pero sin que el usuario tenga que editar el `.xlsx` a mano
él mismo ni pasar por el estado intermedio "Pendiente".

Desde 2026-07-17 también recorre los **ítems de `Detalle` agrupados** —
filas cuyo Nombre Ítem indica que una parte de la compra no se pudo
identificar línea por línea y se agrupó en 1 solo ítem por el saldo (ej.
"Materiales varios", convención del precedente `CCON-004`;
`listar_items_agrupados()`/`desglosar_item_agrupado()`): el agente muestra
la foto y la descripción del grupo, pregunta el desglose real, y lo aplica
reemplazando esa fila por una fila por ítem (azul marino), recalculando
totales y "Resumen Ítems" de `Master`. Al terminar cualquier recorrido de
esta skill hay que correr `python driver.py reflejar`
(`reflejar_a_sitio_comunicacion()`) para copiar el Excel local a `Sitio de
comunicación - Centro de Costos 1/` — a diferencia de `run`, `corregir`/
`desglosar` no hacen ese reflejo por sí solos.

### Skill: `/Actualizar_CC`

Agregada 2026-07-27 en
[.claude/skills/Actualizar_CC/](.claude/skills/Actualizar_CC/SKILL.md).
Envoltorio sobre `/Registro_Centro_de_Costos`: corre su flujo `status`→`run`
y, si se registraron documentos nuevos (o el usuario pide forzarlo),
**publica** el `Visualizador Web/build/index.html` regenerado en el sitio de
GitHub Pages del proyecto (receta y URL fija en
[`../Visualizador Web/CLAUDE.md`](../Visualizador%20Web/CLAUDE.md) §
Hosting — hasta 2026-08-05 se publicaba como Claude Artifact, texto
corregido acá el 2026-08-18 porque había quedado desactualizado tras esa
migración). Cierra el paso manual que quedaba pendiente tras cada `run`: el
registrador ya regenera el HTML en disco solo (PASO 12c), pero subirlo no
era automático.

### Skill: `/Actualizar_Base_de_Datos`

Agregada 2026-08-18 en
[.claude/skills/Actualizar_Base_de_Datos/](.claude/skills/Actualizar_Base_de_Datos/SKILL.md).
Envoltorio sobre `/Registro_Centro_de_Costos` que corre `status`→`run` y se
detiene ahí — a diferencia de `/Actualizar_CC`, deliberadamente **no**
publica el dashboard (nunca toca el worktree `gh-pages`). Pensado para
acumular varias corridas de registro de datos y publicar todo junto después
con `/Actualizar_CC` o `/Actualizar_Finanzas`. Desde 2026-08-18, si `status`
muestra documentos pendientes sin entrada en `datos_extraidos.json`, el
agente los completa de forma interactiva antes de `run` (Paso 2 de
`Registro_Centro_de_Costos/SKILL.md`: abre cada foto/PDF, extrae lo legible,
y pregunta al usuario solo lo que el documento no resuelve por sí solo,
agrupando por proyecto) — ningún documento nuevo queda sin registrar solo
porque falte poblar el JSON. Mismo comportamiento heredado por `/Actualizar_CC`
y (con una nota aparte, porque corre `run` como subproceso) por
`/Actualizar_Finanzas`.

### Historia: reconstrucción de julio 2026

Movida a [HISTORIA.md](HISTORIA.md) (2026-07-27) — relato de cómo se perdió
el pipeline anterior (`build.py`/`rename.py`/etc.) y cómo se reconstruyó
`auditor_centro_costos.py` leyendo el `.xlsx` sobreviviente. Solo hace falta
abrirlo para entender ese origen, no para trabajar en el módulo día a día.

## Estructura del repositorio

```
/
├── CLAUDE.md                              # este archivo
├── Excel/
│   ├── Centro de Costos.xlsx              # libro maestro (Master + Detalle + hoja por proyecto) — el script escribe SOLO aquí
│   └── Respaldos/                         # backups automáticos, en subcarpetas por mes ("Julio 2026") + manuales
├── Facturas y Boletas/                    # LEGADO desde 2026-07-17: ya no la lee el script, ver "Sitio de comunicación" más abajo
│   ├── UMAG/
│   ├── Cesfam Limache/
│   └── Gastos Generales/
├── Sitio de comunicación - Centro de Costos 1/  # acceso directo de OneDrive (SharePoint) — fuente oficial de documentos desde 2026-07-17
│   ├── Facturas y Boletas/                #   el script LEE los documentos pendientes de aquí (RAIZ_DOCS), no de la carpeta local de arriba
│   │   ├── Chile/                        #   split por país agregado 2026-08-21 — todos los proyectos actuales viven aquí
│   │   │   ├── UMAG/
│   │   │   ├── Cesfam Limache/
│   │   │   └── ...
│   │   └── Perú/                         #   nueva, para documentos de Perú (ver Peru/Centro de Costos/ más abajo en la raíz del repo)
│   └── Centro de Costos.xlsx              #   reflejo de solo lectura: el script lo sobrescribe con una copia de Excel/Centro de Costos.xlsx en cada 'run'
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
    └── skills/
        ├── Registro_Centro_de_Costos/  # skill /Registro_Centro_de_Costos (antes /run-centro-de-costos)
        └── Revision_de_Errores/        # skill /Revision_de_Errores (agregada 2026-07-17)
```

Reorganizado el 2026-07-16 (ver `docs/superpowers/specs/2026-07-16-reorganizacion-carpetas-design.md`)
para que la raíz sea navegable para un usuario no técnico: `Excel/` contiene
el único archivo que se abre a mano (`Centro de Costos.xlsx`), `Facturas y
Boletas/` son las fuentes, y `Sistema/` agrupa todo lo técnico
(script, JSON de entrada, docs de formato, tests, legado).

Renombrado el 2026-07-17: `Documentos Centro de Costos/` pasó a llamarse
`Facturas y Boletas/` (mismo contenido, mismo rol).

`Facturas y Boletas/<Proyecto>/` es la unidad de organización: cada subcarpeta de primer nivel es un **proyecto/centro de costos**. Agregar un proyecto nuevo es tan simple como crear la subcarpeta y dejar caer los documentos ahí — el script los detecta solo (aunque para que el `N° Ref.` tenga un prefijo elegido por ti, agrégalo a `PREFIJOS_PROYECTO` en `Sistema/auditor_centro_costos.py`; si no, usa uno derivado automático y avisa por consola).

**Split por país (2026-08-21)**: `Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/` ahora tiene dos subcarpetas de primer nivel, `Chile/` y `Perú/` — el `<Proyecto>/` de arriba vive un nivel más adentro, dentro de la que corresponda. Este mismo script (parametrizado por `pais="CL"|"PE"`, ver `configurar_pais()` en `Sistema/auditor_centro_costos.py`) lee de una u otra según el país activo; Perú no tiene código propio, solo su propio Excel/JSON/respaldos en `Peru/Centro de Costos/` (carpeta hermana a esta, en la raíz de `Finanzas QUEMPIN/`). Ver `docs/superpowers/specs/2026-08-21-peru-expansion-design.md` (raíz del repo) para la arquitectura completa.

### Sitio de comunicación (fuente compartida, desde 2026-07-17)

Desde el 2026-07-17, `Sitio de comunicación - Centro de Costos 1/` (acceso
directo de OneDrive a un sitio SharePoint, dentro de este módulo) es la
**fuente oficial de documentos** — reemplaza a la `Facturas y Boletas/` local
como origen que lee el script. Objetivo: que los colegas puedan subir
facturas/boletas directo a `Sitio de comunicación - Centro de Costos 1/
Facturas y Boletas/<Proyecto>/` sin tocar este repositorio, y que vean el
Excel actualizado sin necesitar acceso al PC del usuario.

- `RAIZ_DOCS` en `Sistema/auditor_centro_costos.py` apunta a `Sitio de
  comunicación - Centro de Costos 1/Facturas y Boletas/` (antes apuntaba a la
  `Facturas y Boletas/` local). Es el único cambio de fuente: inventario,
  registro de documentos nuevos, y renombrado/conversión de fotos
  (`<N° Ref.>_<TagProveedor>_<Fecha DD-MM-AAAA>.<ext>`, HEIC→JPG) ahora operan sobre
  esa carpeta compartida, no la local.
- La `Facturas y Boletas/` local queda como **legado/histórico**: ya no la
  lee el script. No se borra (evita perder los documentos que ya tenía), pero
  no hay que seguir depositando ahí — los documentos nuevos van directo a la
  carpeta compartida.
- El libro de trabajo real sigue siendo únicamente `Excel/Centro de
  Costos.xlsx` (local) — ahí es donde el script hace backup, escribe filas,
  regenera fórmulas, etc., exactamente igual que antes. Al final de cada
  `run` (PASO 12b, `shutil.copy2`), esa copia se sobrescribe encima de `Sitio
  de comunicación - Centro de Costos 1/Centro de Costos.xlsx` — ese archivo
  compartido es un **reflejo de solo lectura**: nunca se lee ni se le escribe
  nada excepto esa copia final. Si el archivo está bloqueado (alguien lo
  tiene abierto), el paso queda como advertencia (`[WARN]`) y no aborta el
  `run` — el Excel local igual quedó guardado correctamente.
- Migración inicial (2026-07-17): el usuario ya copió a mano el contenido de
  `Facturas y Boletas/` (29 documentos, mismos nombres ya renombrados) dentro
  de la carpeta compartida antes de este cambio, así que el primer `run` con
  la fuente nueva no encontró pendientes ni renombrados — el punto de partida
  quedó idéntico entre ambas carpetas.
- Plan a futuro (palabras del usuario): con el tiempo, `Sitio de comunicación
  - Centro de Costos 1/Facturas y Boletas/` debería pasar a ser la carpeta
  oficial única de estos registros.

## Módulo: Centro de Costos

### Qué hace

`Sistema/auditor_centro_costos.py` mantiene `Excel/Centro de Costos.xlsx` sincronizado con los documentos (facturas/boletas) que se van agregando a `Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/<Proyecto>/` (ver sección de arriba — antes leía la `Facturas y Boletas/` local). No hace OCR/extracción de datos por sí mismo: consume `Sistema/datos_extraidos.json`, que se asume ya poblado (por el usuario o por un paso de extracción previo, ej. IA leyendo las fotos de las facturas) con los datos estructurados de cada documento, **incluyendo el desglose en ítems de línea**.

Flujo de ejecución (`main()`):
1. **Backup** — copia `Excel/Centro de Costos.xlsx` a `Excel/Respaldos/<Mes Año>/Centro de Costos - backup <fecha> <hora>.xlsx` antes de tocar nada (ej. `Excel/Respaldos/Julio 2026/...`; la subcarpeta del mes actual se crea sola si no existe — `carpeta_mes()`, agregado 2026-07-17). `backup_mas_reciente()` busca recursivamente (`rglob`) para encontrar el backup más reciente aunque haya quedado en el mes anterior.
2. **Leer `Master`** — determina qué `N° Ref.` ya existen (y su secuencia máxima por proyecto), y qué archivos ya están cubiertos (columna "Archivo origen" de filas escritas por este script, más `Sistema/reconciliacion_archivos.json` para las filas preexistentes que no tienen esa columna poblada).
3. **Inventariar archivos** — recorre `Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/`, clasifica cada archivo como pendiente / omitido (ya registrado).
4. **Cargar `Sistema/datos_extraidos.json`** y buscar la entrada de cada archivo pendiente (por `proyecto` + `archivo`).
5. **Escribir en Excel** por cada documento con datos completos (con `items`): asigna el siguiente `N° Ref.` del proyecto, escribe un renglón en `Detalle` por cada ítem de línea, y una fila-resumen en `Master` (con fórmulas `SUMIF`/suma hacia `Detalle`).
6. **Reordenar por fecha** (`reordenar_por_fecha`, agregado 2026-07-17) — reubica las filas de `Master` (y los bloques de ítems de `Detalle` que le corresponden a cada `N° Ref.`) para que la fila 2 sea el documento con la fecha más reciente y el fondo de la tabla el más antiguo. No reescribe valores/formato de ninguna celda, solo la fila donde vive cada una (fórmulas K/M de `Master`, que referencian su propia fila, se regeneran con la fila nueva; fechas no interpretables quedan al final). Corre en cada `run`, incluso sin documentos nuevos, para que un documento con fecha antigua agregado hoy se intercale en su lugar. Como las hojas de proyecto se arman a partir del orden de `Master`, heredan el mismo orden automáticamente.
7. **Regenerar derivados** — los pies "TOTAL GENERAL" de `Master`/`Detalle` y las hojas de proyecto (100% fórmulas hacia `Master`, se recalculan completas cada corrida a partir de la columna `Proyecto` actual).
8. **Verificaciones aritméticas**: IVA = 19% del Neto (suma de ítems) para Facturas/Guías de Despacho (tolerancia ±1 CLP).
9. **Informe de auditoría** impreso en consola: alertas de legibilidad, inconsistencias aritméticas, posibles duplicados (mismo N° Documento en más de un archivo), limitaciones de registro (archivos sin datos, o sin `items`, en el JSON).
10. **Reflejo a Sitio de comunicación** (PASO 12b, agregado 2026-07-17) — copia (`shutil.copy2`) el `Excel/Centro de Costos.xlsx` recién guardado encima de `Sitio de comunicación - Centro de Costos 1/Centro de Costos.xlsx`. No falla el `run` si el destino está bloqueado, solo advierte.
11. **Actualizar visualizador web** (PASO 12c, agregado 2026-07-19) — regenera `Visualizador Web/build/index.html` a partir del Excel recién guardado (`actualizar_visualizador()`, llama a `Visualizador Web/build_visualizador.py`). Solo lee el Excel, nunca lo modifica; si falla no aborta el `run`, solo advierte. Ver [Visualizador Web/CLAUDE.md](Visualizador%20Web/CLAUDE.md).
12. **Actualizar Análisis Financiero** (PASO 12d, agregado 2026-07-20) — `actualizar_analisis_financiero()` importa `Sistema Analisis Financiero/Sistema/analisis_financiero.py` y corre `af.ejecutar()`, que recalcula costos reales/KPIs de ese módulo a partir del `Centro de Costos.xlsx` recién guardado (y, dentro de ese `ejecutar()`, también regenera el visualizador de Análisis Financiero). Mismo patrón "best-effort" que PASO 12b/12c: solo lee este Excel, nunca lo modifica, y si falla o el módulo no existe, no aborta el `run` — solo advierte. Al terminar, `_avisar_reportes_pendientes()` avisa por consola (sin generarlos) si quedaron reportes PDF de Análisis Financiero desactualizados. Los tres pasos (12b/12c/12d) comparten el mismo patrón de import cross-módulo vía el helper `_modulo_hermano_fresco` (inserta el directorio en `sys.path`, descarta cualquier módulo cacheado con ese nombre — los 3 módulos financieros tienen archivos homónimos como `build_visualizador.py`/`driver.py` — y restaura `sys.path` al salir, incluso si falla).

### Reglas de oro (no negociables)

- **El contenido de las filas de datos ya escritas no se vuelve a tocar**: ni los ítems en `Detalle` ni las filas de documento en `Master` (salvo sus columnas J/L, que son fórmulas siempre-derivadas y se dejan intactas si alguien ya las reemplazó a mano por un valor fijo). Es la regla de oro de esta versión — reemplaza al "solo anexa" de la versión simple anterior, porque la estructura rica sí tiene contenido derivado (fórmulas, pies de tabla, hojas de proyecto) que necesita regenerarse. Su **posición** sí se reordena en cada corrida (ver paso 6, `reordenar_por_fecha`, 2026-07-17): más reciente arriba, más antiguo al fondo — mover una fila preserva su formato/correcciones a mano tal cual, solo cambia dónde vive.
- **Idempotente**: correr el script sin documentos nuevos no modifica ninguna fila de datos (solo regenera pies de tabla y hojas de proyecto, que dan el mismo resultado si nada cambió en `Master`).
- **Backup siempre antes de escribir**: si vas a modificar la lógica de escritura, no rompas este paso.
- **Extensiones válidas**: `.png .jpg .jpeg .heic .pdf`. Se ignoran `.html .txt .ini .tmp` y `desktop.ini` (archivos de sincronización de OneDrive).
- Si el Excel está abierto en otra aplicación al momento de guardar, el script debe fallar con un mensaje claro (`PermissionError`), no corromper el archivo.
- **El formato que el usuario modifique a mano en el `.xlsx` se respeta entre corridas**: ancho de columnas, formato de casilla, columnas ocultas (siguen ocultas, pero el script las sigue leyendo/actualizando igual que antes). Desde 2026-07-16, `ajustar_anchos` solo fija el ancho de una columna si todavía no tiene uno, y `regenerar_hoja_proyecto` reutiliza la hoja de proyecto existente en vez de borrarla y recrearla — ver [Formato.md](Sistema/Formato.md) §8 (patrón genérico) y [Formato Centro de Costos.md](Sistema/Formato%20Centro%20de%20Costos.md) §3/§11 (verificación sobre el archivo real).

### Esquema de `datos_extraidos.json`

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
[MEMORY.md](.claude/skills/Registro_Centro_de_Costos/MEMORY.md) del skill):

```json
{
  "archivo": "IMG_9999.HEIC",
  "proyecto": "UMAG",
  "tipo_proyecto": "I+D+i",
  "fecha": "15-07-2026",
  "n_documento": "12345",
  "tipo_documento": "Factura",
  "proveedor": "Proveedor SpA",
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
- `"tipo_proyecto"` es una clasificación a nivel proyecto (ej. `I+D+i`, `Mantenimiento`, `Gastos Generales`), constante para ese proyecto salvo que cambie deliberadamente.
- `"categoria"` es a nivel documento; `"categoria_item"` es a nivel ítem — pueden diferir si un documento mezcla categorías.
- **`"nombre_item"` = tipo de producto genérico, lo más simplificado posible** — sin marca ni adjetivos/variantes (ej. "Hidrolavadora", no "Hidrolavadora Karcher portátil"; "Taladro", no "Taladro inalámbrico") (pedido 2026-07-17, endurece la regla anterior). **`"descripcion"` = todo el detalle** (marca, modelo, medidas, especificaciones — ej. "Hidrolavadora Karcher portátil K3 120 bar", "Taladro percutor 20V 13mm s/carbones DCD7781"). **No anotar el código de producto** en ninguno de los dos campos (pedido 2026-07-16). "Resumen Ítems" en `Master` se arma uniendo los `nombre_item`, así que mantenerlo simplificado ahí también lo mantiene simple en `Master`.
- Si no se pudo leer el N° de documento, usar `"S/N (<archivo o nombre del voucher>)"` — el script pinta esa celda de rojo automáticamente para revisión manual.
- **`"rotacion"` es opcional** (agregado 2026-08-20): grados en **sentido horario** que hay que girar el archivo físico para que quede derecho (`90`, `180` o `270`). Un documento girado **nunca debe quedar fuera del JSON por ilegible solo por eso** — el agente lo lee igual (rotándolo mentalmente) y anota el ángulo aquí; `run` corrige el archivo en disco automáticamente al registrarlo (`rotar_si_corresponde` en `auditor_centro_costos.py`, ver PASO 6), una sola vez por documento — no hace falta rotarlo a mano antes. Se omite si el documento ya está bien orientado.
- Ver `Sistema/Legado/datos_extraidos_legacy_umag.json` como referencia del esquema simple anterior (sin ítems) — ya no lo lee el script, solo queda como archivo histórico.

### Estructura de `Centro de Costos.xlsx`

Reconstruida el 2026-07-16 leyendo directamente el `.xlsx` resultante de un
pipeline anterior perdido (ver "Historia" más arriba). Tres tipos de hoja:

- **`Detalle`** — la hoja de edición real: una fila por **ítem de línea** de cada documento — `N° Ref., Proyecto, Tipo de Proyecto, N° Documento, Nombre Ítem, Descripción, Categoría Ítem, Cantidad, P. Unitario sin IVA, Total sin IVA (CLP), Total con IVA (CLP)`. Varias filas comparten el mismo `N° Ref.` cuando un documento tiene varios ítems. **Cada línea de la compra va como su propio ítem — nunca un solo ítem resumen por el total del documento** (pedido 2026-07-17, tras corregir `CCON-004`; excepción: si una parte de la factura es físicamente ilegible, agrupar SOLO esa parte en 1 ítem aparte, no el documento completo — ver detalle en `MEMORY.md` del skill). `Total con IVA (CLP)` (agregada 2026-07-17, última columna) es un valor calculado en Python al escribir (no una fórmula de Excel): `Total sin IVA × (1 + tasa real del documento)`, donde la tasa sale de `IVA / Neto` del documento en `Master` (no 19% fijo), para que también sea correcta en documentos exentos (pasajes de bus) o de Zona Franca. Puede haber una diferencia de ±$1 frente al `Total con IVA` de `Master` por redondeo por ítem — mismo tipo de diferencia menor que ya existe en otros totales de este libro.
- **`Master`** — una fila por **documento** (no por proyecto) — `N° Ref., Proyecto, Tipo de Proyecto, Fecha, N° Documento, Tipo Documento, Proveedor, Proveedor (Razón Social), Categoría, Resumen Ítems, Total sin IVA (CLP), IVA 19% (CLP), Total con IVA (CLP), Estado, Archivo origen, Fecha modificación`. "Total sin IVA" es `=SUMIF(Detalle!$A:$A,$A<fila>,Detalle!$J:$J)` y "Total con IVA" es `=K<fila>+L<fila>` — ambas fórmulas, nunca valores fijos (a menos que alguien las reemplace a mano, en cuyo caso el script las respeta). Desde 2026-07-16, "Proveedor" muestra un **tag corto** (ej. "Shell") derivado de la razón social completa vía `TAGS_PROVEEDOR_CURADOS`/`generar_tag_proveedor()`; la razón social completa (ej. "Estaciones de Servicios Fandos Ltda. (Shell Ruta 68)") queda en la columna contigua "Proveedor (Razón Social)", **oculta**. Mismo par tag/razón social en cada hoja de proyecto. Ver `Sistema/Formato.md` §3/§14 e historial.
- **Una hoja de solo lectura por proyecto** — 100% fórmulas `=Master!<col><fila>` apuntando a las filas de `Master` cuya columna `Proyecto` calza con esa hoja. Se reconstruye completa en cada corrida, así que si reasignas a mano el proyecto de un documento en `Master`, su fila se mueve sola a la hoja correcta la próxima vez que corra el script. **Desde 2026-07-17, el título de la pestaña es el prefijo del proyecto** (`UMAG`, `CFLI`, `CCON`, `GGEN`, `MLER`), no el nombre completo — pedido del usuario para pestañas compactas; `Master!Proyecto` sigue con el nombre completo (ej. "Cesfam Limache"), solo cambió el título de la hoja. `regenerar_hoja_proyecto()` calcula el nombre con `prefijo_para_proyecto()`. Ver detalle y migración del `.xlsx` real en [Formato Centro de Costos.md](Sistema/Formato%20Centro%20de%20Costos.md) §3b.
- **`N° Ref.`** es la clave: `<PREFIJO>-<secuencia>` (ej. `UMAG-001`, `CFLI-002`), con prefijo fijo por proyecto en `PREFIJOS_PROYECTO` (`Sistema/auditor_centro_costos.py`).
- Cada proyecto tiene un color asignado de una paleta fija de 8 tonos pasteles (antes 12, varios casi idénticos entre sí — corregido 2026-07-17), reutilizado de forma determinista (se lee de `Master` antes de asignar uno nuevo). El color de fila y el `tabColor` de la hoja de cada proyecto se mantienen sincronizados por relleno directo de celda, sin formato condicional de Excel de por medio (una regla heredada de un pipeline anterior tapaba esa sincronía hasta 2026-07-17 — ver historial en `Formato Centro de Costos.md`).
- Convención de colores de fuente (documentada también en la leyenda al pie de cada hoja): cursiva = editable a mano, rojo = requiere revisión, azul marino = corregido a mano (no se sobreescribe). Códigos hex exactos (fuente y paleta por proyecto) y detalle completo del formato real (columnas, anchos, filtros, validaciones, y dónde el formato heredado del pipeline perdido no coincide con lo que hace hoy el script) en [Formato Centro de Costos.md](Sistema/Formato%20Centro%20de%20Costos.md) (el patrón genérico reutilizable por futuros módulos está en [Formato.md](Sistema/Formato.md)). El recoloreo rojo→azul marino oscuro al corregir algo a mano está implementado desde 2026-07-17, **con confirmación explícita en dos pasos** (no automático al detectar): `run` compara el backup más reciente contra el estado actual, detecta qué celda roja cambió de valor, y la deja "Pendiente" en `Sistema/correcciones_manuales.json` + la tabla de [ERRORES.md](.claude/skills/Registro_Centro_de_Costos/ERRORES.md) (no toca el Excel todavía); `python driver.py confirmar --todos` (o con N° Ref puntuales) recién ahí recolorea la fuente a azul marino y propaga el valor corregido a `Detalle` si el campo se repite ahí (hoy: N° Documento). Ver el detalle del flujo en ERRORES.md.
- **Sí hay renombrado de fotos y conversión HEIC→JPG** (agregado el 2026-07-16, después de la reconstrucción inicial): cada `run` compara el nombre físico actual de cada documento contra el esperado (`<N° Ref.>_<TagProveedor>_<Fecha DD-MM-AAAA>.<ext>`, `.heic`→`.jpg`) y renombra/convierte en disco si difiere, actualizando "Archivo origen" en `Master` — cubre documentos nuevos y, retroactivamente, los ya registrados (excepción explícita a la regla de oro, igual que `migrar_columna_proveedor()`). `status` muestra un preview de qué se renombraría sin tocar disco. `resolver_ruta_actual()` prueba primero "Archivo origen"; si esa ruta no existe en disco (caso de los 24 documentos del bootstrap, cuyo "Archivo origen" quedó con el nombre que les daba el pipeline perdido) cae al mapeo de `reconciliacion_archivos.json`, que apunta al archivo físico real — corregido 2026-07-17, ver `ERRORES.md`. Los 24 documentos del bootstrap ya se renombraron con este fix (22 UMAG + 1 Cesfam Limache + 1 Gastos Generales) a la convención `<N° Ref.>_<TagProveedor>_<Fecha>`. **Desde 2026-07-28 el sufijo de fecha del nombre de archivo pasó de `<Fecha ISO>` (`YYYY-MM-DD`) a `<Fecha DD-MM-AAAA>`** (pedido del usuario) — el primer `run` tras el cambio renombra en disco todos los documentos que aún tengan el sufijo viejo, igual que cualquier otra discrepancia de nombre.

### Archivos auxiliares

- **`Excel/Respaldos/<Mes Año>/Centro de Costos - backup *.xlsx`**: se acumulan con cada corrida del script, agrupados en una subcarpeta por mes (ej. `Julio 2026/`). Son desechables/limpiables, pero no borrar sin confirmar con el usuario (podrían ser el único respaldo de una corrida específica si el archivo principal se corrompe).
- **`Sistema/reconciliacion_archivos.json`**: mapeo de bootstrap (archivo original → N° Ref) para los 24 documentos que ya existían al reconstruir la estructura rica. No lo borres — sin él, esos 24 archivos se verían como "pendientes" en el próximo `status`/`run`. Los documentos registrados de aquí en adelante no lo necesitan.
- **`Sistema/Legado/datos_extraidos_legacy_umag.json`**: esquema simple anterior (sin ítems), ya no lo lee el script — solo queda como referencia histórica.

**`Sistema/Formato.md`**: patrón **genérico** de formato (estilo de encabezado, paleta, convención de colores, regla de oro, preservación de formato manual) pensado para reutilizarse en módulos futuros — no contiene datos específicos de este módulo.

**`Sistema/Formato Centro de Costos.md`**: registro del formato real **de este módulo** — colores, columnas, formatos de celda, dónde hay filtros/paneles inmovilizados/validaciones de datos, y las discrepancias entre lo que hace hoy el script y lo heredado del pipeline perdido (ver "Historia" arriba). Es un documento vivo: cada cambio de formato (a mano o por código) se registra ahí con fecha, no solo se pisa la sección correspondiente.

### Convenciones de carpetas auxiliares

- **`Excel/Respaldos/`**: copias de seguridad automáticas (una por cada `run`, incluso sin cambios), organizadas en una subcarpeta por mes (ej. `Julio 2026/`), más cualquier backup manual. Desechables, pero no borrar sin confirmar con el usuario.
- **`Sistema/Legado/`**: archivos históricos que el script ya no lee, conservados solo por trazabilidad.

## Precauciones

- **Esta carpeta (`Finanzas QUEMPIN/Centro de Costos/`) es la ubicación canónica única para el código/Excel de trabajo** desde 2026-07-16. **¡Cuidado con el nombre!** Hay tres carpetas con nombres casi idénticos, y solo una es válida como fuente:
  - `Centro de Costos/Sitio de comunicación - Centro de Costos 1/` (**dentro** de este módulo, con "1" y "Costos" en mayúscula) — acceso directo de OneDrive agregado 2026-07-17, **es la fuente oficial de documentos actual** (ver sección "Sitio de comunicación" más arriba). `RAIZ_DOCS` apunta aquí.
  - `OneDrive - QUEMPIN SPA/Sitio de comunicación - Centro de costos/` (**fuera** de este módulo, sin "1", "costos" en minúscula) — copia vieja y desactualizada de antes de la reconstrucción del 2026-07-16. No confundir con la de arriba; no escribirle ni confiar en su "estado actual".
  - `OneDrive - QUEMPIN SPA/Plantillas/` — ahí corrió el pipeline perdido; tampoco escribirle.
  Si necesitas consultar cualquiera de estas dos últimas, verifica primero con el usuario.
- Esta carpeta igual vive dentro de OneDrive, sincronizada y potencialmente editada por más de una persona/dispositivo. Antes de sobrescribir el `.xlsx` principal, considera que puede haber cambios recientes hechos a mano fuera de este script (el propio script está diseñado para tolerarlo: nunca reescribe una fila de datos ya creada). Esto aplica con más razón a `Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/`, ya que ahí suben documentos los colegas directamente.
- `Sistema/datos_extraidos.json`, los documentos en `Facturas y Boletas/` (legado) y los de `Sitio de comunicación - Centro de Costos 1/` (fuente actual, incluyendo su copia de `Centro de Costos.xlsx`) contienen **datos financieros reales de la empresa** (montos, proveedores, N° de documentos tributarios). El código (`Sistema/auditor_centro_costos.py`, tests, skill) sí está versionado en git; estos datos están explícitamente excluidos vía `.gitignore` en la raíz de `Finanzas QUEMPIN/` (incluye la carpeta `Sitio de comunicación - Centro de Costos 1/` completa, agregada 2026-07-17) — verifica ese archivo antes de asumir que algo nuevo bajo este módulo quedará (o no) fuera de control de versiones.
- El script reconfigura `stdout`/`stderr` a UTF-8 explícitamente por errores de encoding típicos de consola en Windows — mantener esa línea si se toca `main()`.
- Si aparece una carpeta `__pycache__/`, es caché de bytecode de Python (regenerable, seguro de borrar) — no es parte de la estructura intencional del módulo, no confundirla con datos.
