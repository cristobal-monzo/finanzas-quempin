---
name: Registro_Centro_de_Costos
description: Run, check status, audit, or dry-run the Centro de Costos cost-center pipeline for QUEMPIN SpA — inventories invoice/receipt files under "Documentos Centro de Costos/", cross-checks them against datos_extraidos.json (per-line-item schema), and writes Master (1 row/documento con fórmulas)/Detalle (1 row/ítem)/hojas de proyecto (solo lectura, fórmulas) into "Centro de Costos.xlsx" with automatic backup. Use when asked to run centro de costos, actualizar centro de costos, registrar facturas, ver estado del centro de costos, auditar facturas, or check for pending/unregistered invoices.
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
JSON, troubleshooting). Ver [MEMORY.md](MEMORY.md) para preferencias
(colores, formato), datos importantes de facturas e historial de corridas
reales, y [ERRORES.md](ERRORES.md) para el historial de errores del
pipeline y el registro de correcciones manuales hechas directo en el Excel
— no dupliques ese contenido acá.

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
ver [MEMORY.md](MEMORY.md) para el historial de resultados reales por
fecha):

```
======================================================================
  ESTADO CENTRO DE COSTOS (solo lectura, no escribe nada)
======================================================================

Hojas existentes: ['Master', 'Detalle', <hoja por proyecto>, ...]

Documentos ya en Master: N
N° Documento distintos ya registrados: N
Archivos ya cubiertos (Master + reconciliación): N

Inventario de Documentos Centro de Costos/:
  Pendientes (no registrados):            N
  Omitidos (ya registrados):               N

Proyectos detectados (N): ...

Entradas en datos_extraidos.json: N

Si corres 'run' ahora se registrarían: N documento(s).

======================================================================
  Nada fue escrito. Para ejecutar de verdad: python driver.py run
======================================================================
```

**Paso 2 — si `status` muestra "se registrarían: N > 0 documento(s)"**, correr
la ejecución real:

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
reales en [MEMORY.md](MEMORY.md)): si no hay documentos registrables, `run`
no toca ninguna fila de datos existente — solo crea el backup y regenera
pies de tabla + hojas de proyecto. Las hojas de proyecto se recalculan desde
la columna `Proyecto` actual de `Master` (no desde un estado guardado), así
que una reasignación manual de proyecto hecha directo en `Master` se refleja
sola en la hoja de proyecto la próxima vez que corra `run`.

**Paso 3 — al terminar `run`, presentar siempre una tabla-resumen al usuario**
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
  `Documentos Centro de Costos/<Proyecto>/<archivo>` en su lugar.
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

## Run (ruta humana)

Idéntico a `run` del driver, sin el wrapper:

```
python auditor_centro_costos.py
```

## Formato de `datos_extraidos.json` (esquema con ítems de línea)

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
  "notas": "opcional"
}
```

`"nombre_item"` = nombre simple del producto; `"descripcion"` = el detalle
(modelo/medidas/specs). No anotar el código de producto en ninguno de los
dos (pedido 2026-07-16, ver `CLAUDE.md`).

`"iva"` es opcional (si se omite, se calcula 19% para Factura/Guía de
Despacho y 0 para el resto). Si no se puede leer el N° de documento, usar
`"S/N (<archivo>)"` — el script lo pinta rojo automáticamente para revisión.

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
  en `Documentos Centro de Costos/<Proyecto>/<archivo>`. Si no calzan, el
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
- **No hay renombrado de fotos ni conversión HEIC→JPG ni detección
  automática de duplicados en esta versión** (esas capacidades existían en
  el pipeline anterior — `rename.py`/`detectar_duplicados.py` — que se
  perdió; no se reconstruyeron todavía). El script sí avisa "posibles
  duplicados" cuando un N° Documento nuevo coincide con uno ya registrado,
  pero no bloquea el registro.
- **Cada `run` crea un backup nuevo dentro de `Respaldos/`** (no en la raíz
  del módulo), incluso si no hay nada que escribir. Son desechables pero no
  se auto-limpian.
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
