---
name: Registro_Centro_de_Costos
description: Direct pipeline commands (status/run/confirmar/visualizador) for the Centro de Costos cost-center system — inventories invoice/receipt files under "Facturas y Boletas/", cross-checks them against datos_extraidos.json (per-line-item schema), and writes Master (1 row/documento con fórmulas)/Detalle (1 row/ítem)/hojas de proyecto (solo lectura, fórmulas) into "Centro de Costos.xlsx" with automatic backup, and regenerates the web visualizer locally. Invoke ONLY via explicit "/Registro_Centro_de_Costos" — do NOT auto-trigger on loose phrases like "actualiza el centro de costos" or "actualiza cc" said without the leading slash; ask the user for confirmation instead, since they may mean this skill, /Actualizar_CC, or /Actualizar_Base_de_Datos (see root CLAUDE.md § Invocación de skills). Use this skill directly for status checks, dry runs, audits, registering facturas, or confirming manual corrections when the user names it explicitly.
---

# Registro: Centro de Costos

Herramienta de línea de comandos (Python + openpyxl), no una app con interfaz
gráfica ni servidor. No hay nada que fotografiar: el "driver" es un script
que corre el pipeline y verifica su resultado leyendo el `.xlsx` con
openpyxl.

Todas las rutas de este documento son relativas a la raíz del módulo
(`Centro de Costos/`), **no** a esta carpeta de skill. El driver vive en
`.claude/skills/Registro_Centro_de_Costos/driver.py`.

**No es una demo desechable: `Centro de Costos.xlsx` y `datos_extraidos.json`
tienen datos financieros reales de la empresa.** El comando `status` es de
solo lectura (no toca el Excel). El comando `run` sí escribe — pero es
idempotente (las filas de datos ya escritas nunca se vuelven a tocar; solo
se regeneran los pies de tabla y las hojas de proyecto, que son 100%
derivadas) y siempre crea un backup con timestamp antes de escribir.

Ver `../../CLAUDE.md` para el detalle completo de la estructura "rica"
(Master = 1 fila por documento con fórmulas, Detalle = 1 fila por ítem de
línea, hojas de proyecto = solo lectura por fórmula) y su historia — este
módulo reemplazó en julio 2026 una versión anterior mucho más simple cuyo
pipeline (`build.py`/`rename.py`/etc.) se perdió; la estructura actual se
reconstruyó leyendo el `.xlsx` resultante.

Este documento describe el procedimiento estable (comandos, esquema del
JSON, troubleshooting). Ver [MEMORY.md](MEMORY.md) para reglas de negocio
vigentes y datos importantes de facturas, [HISTORIAL.md](HISTORIAL.md) para
el historial fechado de corridas reales, y [ERRORES.md](ERRORES.md) para el
historial de errores del pipeline y el registro de correcciones manuales
hechas directo en el Excel — no dupliques ese contenido acá.

## Países

Todos los comandos (`status`/`run`/`confirmar`/`visualizador`) aceptan un
flag opcional `--pais CL|PE` (default `CL`, así que ninguna invocación
existente cambia). `PE` (Perú) opera sobre un árbol de datos totalmente
separado — su propio `Centro de Costos Perú.xlsx` (en `Peru/Centro de
Costos/Excel/`), su propio `datos_extraidos_peru.json`, su propia carpeta de
facturas (`Facturas y Boletas/Perú/`), IGV 18% en vez de IVA 19%, valores en
soles. Perú no tiene visualizador web todavía (sub-proyecto 4 del spec de
expansión) — `visualizador --pais PE` lo informa y no falla.

```
python ".claude/skills/Registro_Centro_de_Costos/driver.py" status --pais PE
python ".claude/skills/Registro_Centro_de_Costos/driver.py" run --pais PE
```

Ver [`docs/superpowers/specs/2026-08-21-peru-expansion-design.md`](../../../../docs/superpowers/specs/2026-08-21-peru-expansion-design.md) (raíz de `Finanzas QUEMPIN/`) para la arquitectura completa.

## Prerequisitos

```
python --version      # Python 3.14.6
python -c "import openpyxl; print(openpyxl.__version__)"   # 3.1.5
```

Si falta openpyxl: `pip install openpyxl`.

## Run (ruta del agente) — usar esto primero

**Paso 1 — SIEMPRE correr `status` antes que `run`.** Es de solo lectura:
no crea backup, no escribe el Excel. Reporta qué se registraría.

```
python ".claude/skills/Registro_Centro_de_Costos/driver.py" status
```

Formato de salida (estructura estable; los números cambian en cada corrida —
ver [HISTORIAL.md](HISTORIAL.md) para el historial de resultados reales por
fecha):

```
======================================================================
  ESTADO CENTRO DE COSTOS (solo lectura, no escribe nada)
======================================================================

Hojas existentes: ['Master', 'Detalle', <hoja por proyecto>, ...]

Documentos ya en Master: N
N° Documento distintos ya registrados: N
Archivos ya cubiertos (Master + reconciliación): N

Inventario de Facturas y Boletas/:
  Pendientes (no registrados):            N
  Omitidos (ya registrados):               N

Proyectos detectados (N): ...

Entradas en datos_extraidos.json: N

Si corres 'run' ahora se registrarían: N documento(s).

======================================================================
  Nada fue escrito. Para ejecutar de verdad: python driver.py run
======================================================================
```

**Paso 2 — si `status` reporta "Pendientes SIN datos (o sin items) en el
JSON: N > 0", completar esas entradas antes de seguir a `run`** (pedido del
usuario, 2026-08-18): esos documentos no necesitan que el usuario prepare el
JSON de antemano — el agente arma la entrada leyendo el documento y
preguntando solo lo que la foto/PDF no resuelve por sí sola.

Para cada documento pendiente sin datos (agrupando por proyecto cuando
varios comparten la misma respuesta, ej. `tipo_proyecto`, para no repetir la
misma pregunta N veces):

1. Abrir la foto/PDF (`Sitio de comunicación - Centro de Costos 1/Facturas y
   Boletas/<Proyecto>/<archivo>`) y extraer lo que se lea con claridad:
   fecha, N° de documento, proveedor, tipo de documento, categoría, IVA, y
   el desglose de ítems línea por línea (ver "Formato de
   `datos_extraidos.json`" más abajo, y las reglas de `nombre_item`/
   `descripción` y de partes ilegibles en `../../CLAUDE.md` y
   [MEMORY.md](MEMORY.md) § Reglas de negocio). **Si el documento está girado
   90/180/270°** (hay que ladear la cabeza o el archivo para leerlo), extraer
   los datos igual (leyéndolo rotado mentalmente) — nunca marcarlo ilegible
   solo por la rotación — y agregar `"rotacion"` a la entrada con los grados
   en sentido horario necesarios para dejarlo derecho (ver "Formato de
   `datos_extraidos.json`" más abajo). El siguiente `run` corrige el archivo
   físico solo; no hace falta rotarlo a mano.
2. Preguntar al usuario solo lo que el documento no resuelve por sí solo:
   `tipo_proyecto` si el proyecto es nuevo, `estado` (Pagado/Pendiente, casi
   nunca viene impreso), y cualquier monto/N° de documento/categoría
   ilegible o ambiguo — aplicar también los criterios ya vigentes en
   [MEMORY.md](MEMORY.md) § Criterios de clasificación (ej. asumir Factura
   salvo sospecha clara de Boleta; confirmar si un equipo/herramienta >
   $20.000 corresponde de verdad a ese proyecto o a Gastos Generales).
3. Agregar la entrada a `Sistema/datos_extraidos.json` con el esquema
   completo y seguir con el siguiente pendiente.
4. Si un documento resulta ilegible al punto de no poder completarlo, o el
   usuario no tiene la respuesta a mano, dejarlo fuera del JSON por ahora y
   anotarlo en la tabla del Paso 4 en vez de bloquear el resto — `run` solo
   registra los que quedaron con datos completos; el resto sigue apareciendo
   como pendiente en el próximo `status`.

Con las entradas que se pudieron completar ya en el JSON, seguir al Paso 3.

**Paso 3 — correr la ejecución real** (el número de documentos registrables
puede haber subido tras completar el Paso 2):

```
python ".claude/skills/Registro_Centro_de_Costos/driver.py" run
```

Esto es exactamente `python auditor_centro_costos.py` (el driver solo
importa `acc.main()`). Hace backup → lee Excel → inventaría archivos →
para cada pendiente con datos en el JSON: asigna el siguiente `N° Ref.` del
proyecto (`UMAG-023`, `CFLI-002`, ...), escribe sus ítems en `Detalle` y su
fila-resumen (con fórmulas `SUMIF`) en `Master` → regenera los pies TOTAL
GENERAL y las hojas de proyecto (100% fórmulas hacia `Master`, se
reconstruyen completas en cada corrida) → imprime el informe de auditoría.

Comportamiento confirmado en producción (ver historial detallado con cifras
reales en [HISTORIAL.md](HISTORIAL.md)): si no hay documentos registrables, `run`
no toca ninguna fila de datos existente — solo crea el backup y regenera
pies de tabla + hojas de proyecto. Las hojas de proyecto se recalculan desde
la columna `Proyecto` actual de `Master` (no desde un estado guardado), así
que una reasignación manual de proyecto hecha directo en `Master` se refleja
sola en la hoja de proyecto la próxima vez que corra `run`.

**Paso 4 — al terminar `run`, presentar siempre una tabla-resumen al usuario**
(pedido 2026-07-16, ampliado 2026-07-16). Debe registrar **errores,
inconsistencias e imprecisiones** — no solo lo que el script marca
automáticamente. Directa y simple, columnas fijas:

| Posible error | Ubicación en Master | Descripción | Solución posible |
|---|---|---|---|

Dos fuentes, ambas obligatorias:

1. **Lo que ya reporta la consola** (secciones 1-4 del "INFORME DE
   AUDITORIA": alertas de legibilidad, inconsistencias aritméticas, posibles
   duplicados, limitaciones de registro).
2. **Imprecisiones que el agente note al leer `datos_extraidos.json` y la
   fila escrita en Master/Detalle durante esta corrida**, aunque el script
   no las marque: campo `"notas"` con alguna ambigüedad, nombre de
   proveedor o categoría que luce inconsistente con corridas anteriores,
   monto redondeado o estimado a ojo, N° Documento con formato raro pero
   "legible", fecha dudosa, etc. Si algo se ve raro al pasar los datos
   nuevos, va en la tabla aunque no dispare ningún check del script.

- **Posible error**: tipo de hallazgo (Legibilidad / Inconsistencia IVA /
  Posible duplicado / Sin datos en JSON / Imprecisión de dato — este último
  para lo detectado por el agente, no por el script).
- **Ubicación en Master**: `N° Ref.` de la fila si el documento ya se
  registró en esta corrida (buscarlo por N° Documento o archivo en la
  columna correspondiente); si el documento **no** se registró
  (limitaciones), no tiene fila en Master todavía — poner la ruta
  `Facturas y Boletas/<Proyecto>/<archivo>` en su lugar.
- **Descripción**: el detalle concreto (el que da la consola, o lo que
  notó el agente al revisar el dato).
- **Solución posible**: acción concreta y corta (ej. "revisar N° Documento
  ilegible en la foto", "confirmar con el usuario si es duplicado real",
  "agregar entrada con items al JSON", "confirmar monto exacto con la
  boleta original").

Si no hay nada que reportar en ninguna de las dos fuentes, decirlo en una
sola línea (no generar una tabla vacía). No es necesario tocar
`auditor_centro_costos.py` para esto — la tabla se arma leyendo la salida
de consola más una revisión rápida del agente sobre los datos nuevos, es un
paso posterior a `run`, no una función nueva del script.

**Paso 5 — si `run` reporta "CAMBIOS MANUALES PENDIENTES DE CONFIRMAR"
(sección 6 del informe)**, alguien corrigió a mano una celda que el script
había marcado en rojo (ej. `N° Documento`: `"S/N (IMG_7533)"` → `"12345"`).
Esto es distinto de la tabla del Paso 4: son ediciones manuales detectadas
comparando contra el backup anterior, no errores del pipeline. El agente
debe:

1. Mostrarle al usuario la lista tal cual la imprime `run` (o
   `driver.py confirmar` sin argumentos, que da el mismo preview de solo
   lectura) — qué N° Ref., qué campo, de qué valor a qué valor.
2. **Pedir confirmación explícita antes de aplicar** — nunca correr
   `confirmar --todos` sin que el usuario haya confirmado el cambio en la
   conversación. El script mismo nunca aplica el recoloreo/propagación por
   su cuenta; siempre requiere este comando aparte.
3. Una vez confirmado, aplicar con:
   ```
   python ".claude/skills/Registro_Centro_de_Costos/driver.py" confirmar --todos
   ```
   (o `confirmar <N_REF> ...` si el usuario solo quiere aplicar algunas).
   Esto recolorea la celda de `Master` a azul marino oscuro (`1F3864`),
   propaga el valor a las filas de `Detalle` con el mismo `N° Ref.` cuando
   el campo se repite ahí (hoy: N° Documento), y marca la corrección como
   "Aplicado" en `Sistema/correcciones_manuales.json` y en la tabla de
   [ERRORES.md](ERRORES.md).

Detalle completo del mecanismo (detección por comparación de backups,
por qué no se auto-aplica, qué pasa si la celda se vuelve a editar antes de
confirmar) en [ERRORES.md](ERRORES.md).

## Visualizador web

**Regeneración local automática desde 2026-07-19: no hace falta correrla
aparte.** Tanto `run` del driver como `python auditor_centro_costos.py`
directo regeneran `Visualizador Web/build/index.html` solos, como último
paso de la corrida (PASO 12c, dentro de `main()` en
`auditor_centro_costos.py` — cubre las dos rutas, agente y humana). Si falla
(ej. `build_visualizador.py` movido o roto), no aborta el `run`: el Excel ya
quedó guardado igual, solo imprime un `[WARN]` y hay que regenerar el
visualizador a mano después.

**Publicarlo en GitHub Pages es obligatorio, no manual/opcional** (corregido
2026-07-27 — antes este documento decía "sigue siendo manual", lo que
contradecía la política real). Si `run` registró documentos nuevos (N > 0),
el agente debe publicar el `build/index.html` recién regenerado
inmediatamente después, sin esperar a que el usuario lo pida. Receta y
comandos exactos (subruta `centro-de-costos`) en
[../../../Visualizador Web/CLAUDE.md](../../../Visualizador%20Web/CLAUDE.md)
§ Hosting: copiar a `.worktrees/gh-pages/centro-de-costos/index.html` y
`git add`/`commit`/`push` desde ese worktree. **Los Claude Artifacts ya no
se actualizan** (pedido explícito del usuario, 2026-08-19) — GitHub Pages es
el único canal de publicación desde la migración del 2026-08-05.
`/Actualizar_CC` hace exactamente este paso extra sobre este mismo pipeline;
si en cambio corriste `/Registro_Centro_de_Costos` directo por invocación
explícita, el paso de publicar sigue siendo tuyo al terminar — no lo saltes.

Para regenerar el HTML local aparte sin correr todo el registrador (ej. solo
cambió el diseño en `template.html`, no hay documentos nuevos):

```
python ".claude/skills/Registro_Centro_de_Costos/driver.py" visualizador
```

Ninguno de los dos caminos toca el Excel — ambos son de solo lectura sobre
él. Ver [../../../Visualizador Web/CLAUDE.md](../../../Visualizador%20Web/CLAUDE.md)
para la arquitectura completa (por qué está incrustado y no via fetch, el
gate de contraseña, qué campos se sanean, y el bug de fórmulas de Excel sin
recalcular que hay que recordar si se vuelve a tocar `build_visualizador.py`).

## Run (ruta humana)

Idéntico a `run` del driver, sin el wrapper:

```
python auditor_centro_costos.py
```

## Formato de `datos_extraidos.json` (esquema con ítems de línea)

**`"items"` = CADA línea de la compra por separado, nunca 1 solo ítem
resumen por el total del documento** — ver la excepción para partes
ilegibles y el precedente `CCON-004` en `../../CLAUDE.md` → "Esquema de
`datos_extraidos.json`" y en [MEMORY.md](MEMORY.md).

Cada documento pendiente necesita una entrada así (ver detalle completo del
esquema y las reglas de `N° Ref.`/categorías en `../../CLAUDE.md`):

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
  "rotacion": 90,
  "notas": "opcional"
}
```

`"nombre_item"` = nombre simple del producto; `"descripcion"` = el detalle
(modelo/medidas/specs). No anotar el código de producto en ninguno de los
dos (pedido 2026-07-16, ver `CLAUDE.md`).

`"iva"` es opcional (si se omite, se calcula 19% para Factura/Guía de
Despacho y 0 para el resto). Si no se puede leer el N° de documento, usar
`"S/N (<archivo>)"` — el script lo pinta rojo automáticamente para revisión.

`"rotacion"` es opcional: grados en sentido horario (`90`, `180` o `270`)
para dejar derecho un documento girado — ver Paso 2 más arriba. Se omite si
ya está bien orientado.

## Invocación directa (para checks puntuales)

```python
import sys; sys.path.insert(0, ".")
import auditor_centro_costos as acc

datos = acc.cargar_datos_json(acc.RUTA_JSON)
inconsistencias = acc.verificar_aritmetica(datos)   # solo lee el JSON, no toca Excel
```

## Gotchas

- **El emparejamiento es por (proyecto, nombre exacto de archivo)** —
  `"archivo"` y `"proyecto"` en el JSON deben calzar con la ubicación real
  en `Facturas y Boletas/<Proyecto>/<archivo>`. Si no calzan, el
  archivo queda "pendiente sin datos en el JSON" indefinidamente sin error
  explícito.
- **Los 24 documentos ya registrados antes de julio 2026 no tienen su
  archivo original en `Master`** (esa versión del pipeline los renombraba a
  su N° Documento y ese renombrado ya no existe). `reconciliacion_archivos.json`
  es el mapeo de bootstrap que reconstruye esa relación; no lo borres. Los
  documentos nuevos no lo necesitan — su ruta real queda escrita
  directamente en `Master` (columna "Archivo origen").
- **Las hojas de proyecto se regeneran completas en cada `run`**, leyendo
  la columna `Proyecto` actual de `Master` fila por fila. Si reasignas a
  mano el proyecto de un documento en `Master`, la próxima corrida mueve su
  fila a la hoja de proyecto correcta sola.
- **`Master` y `Detalle` nunca reescriben una fila de datos ya creada** —
  solo se tocan sus pies de tabla (TOTAL GENERAL + leyenda), que se borran y
  reescriben en cada corrida porque son 100% derivados.
- **Sí hay renombrado de fotos y conversión HEIC→JPG** (agregado el
  2026-07-16): cada `run` renombra cada documento a
  `<N° Ref.>_<TagProveedor>_<Fecha DD-MM-AAAA>.<ext>` (`.heic`→`.jpg`,
  formato de fecha con guiones desde 2026-07-28, antes `<Fecha ISO>`
  `YYYY-MM-DD`) si el
  nombre físico actual difiere del esperado, y actualiza "Archivo origen"
  en `Master` — cubre documentos nuevos y, retroactivamente, los ya
  registrados. `status` muestra un preview sin tocar disco. Detección
  automática de duplicados **no** existe todavía (`build.py`/
  `detectar_duplicados.py` del pipeline perdido, no reconstruidos): el
  script solo avisa "posibles duplicados" cuando un N° Documento nuevo
  coincide con uno ya registrado, pero no bloquea el registro — verificar
  a mano contra `Master` si dos filas apuntan al mismo archivo físico
  (pasó una vez, ver `ERRORES.md` 2026-07-17).
- **Cada `run` crea un backup nuevo dentro de `Respaldos/`** (no en la raíz
  del módulo), incluso si no hay nada que escribir. Son desechables pero no
  se auto-limpian.
- **`run` detecta correcciones manuales en celdas rojas pero nunca las
  aplica solo** — las deja "Pendiente"; hace falta correr
  `driver.py confirmar --todos` (con confirmación del usuario primero) para
  que recoloree a azul marino y propague a `Detalle`. Ver Paso 4 más arriba
  y [ERRORES.md](ERRORES.md).
- **Si `Centro de Costos.xlsx` está abierto en Excel**, `run` falla al
  guardar con un `PermissionError` controlado — no corrompe el archivo,
  solo hay que cerrarlo y reintentar.

## Troubleshooting

| Síntoma | Causa / fix |
|---|---|
| `ModuleNotFoundError: No module named 'openpyxl'` | `pip install openpyxl` |
| `[ERROR] El archivo esta abierto en Excel...` al correr `run` | Cerrar `Centro de Costos.xlsx` en Excel y volver a correr |
| Un archivo nuevo no aparece registrado tras `run` | Correr `status` primero: casi siempre está en la lista "SIN datos (o sin items) en el JSON" — falta agregarle una entrada con `items` a `datos_extraidos.json` |
| `[WARN] Proyecto '...' no tiene prefijo de N Ref definido` | Agregar el proyecto nuevo a `PREFIJOS_PROYECTO` en `auditor_centro_costos.py` con el prefijo que prefieras (si no, usa uno derivado automático) |
| `ERROR: No existe la carpeta raiz` / `No existe el JSON de datos` | El script usa `Path(__file__).resolve().parent` como raíz: solo funciona corrido desde/contra `Centro de Costos/` (la copia canónica) |
