# Memoria: Registro_Centro_de_Costos

Bitácora de observaciones, preferencias y decisiones que surgen de **usar**
el pipeline sobre datos reales. Complementa a [SKILL.md](SKILL.md) (el
procedimiento estable: comandos, esquema del JSON, troubleshooting) y a
[ERRORES.md](ERRORES.md) (historial de errores del pipeline + correcciones
manuales pendientes de recolorear en el Excel).

## Qué va en cada archivo

- **SKILL.md** — cómo correr el driver, qué esperar de cada comando, formato
  del JSON, gotchas *estructurales* (comportamiento del script que es
  siempre así, sin importar la fecha), troubleshooting genérico.
- **MEMORY.md (este archivo)** — reglas de negocio y criterios de
  clasificación, datos importantes de facturas/proveedores que vale la pena
  recordar, historial de corridas reales, pendientes que dependen de una
  decisión del usuario. **No** preferencias de color/formato — esas van en
  [Formato Centro de Costos.md](../../../Formato%20Centro%20de%20Costos.md)
  ([Formato.md](../../../Formato.md) si son genéricas para todos los
  módulos).
- **ERRORES.md** — errores detectados por el pipeline (celdas rojas,
  inconsistencias) y el registro de correcciones manuales hechas directo en
  el Excel.

**Convención: "recuérdalo"** — cuando el usuario pida explícitamente
recordar algo sobre este módulo: si es una preferencia de color/formato, va
en `Formato Centro de Costos.md` (o `Formato.md` si aplica a todos los
módulos futuros); si es un dato de una factura, un criterio de
clasificación o una regla de negocio, se agrega en la sección
correspondiente de este archivo; si es sobre un error o una corrección
manual en el Excel, va en `ERRORES.md`.

## Formato y color

Todo lo referente a formato (colores, fuente, formato de número/fecha,
paleta por proyecto, prefijos de N° Ref., preservación de formato manual
entre corridas) vive en
[Formato Centro de Costos.md](../../../Formato%20Centro%20de%20Costos.md)
(estado real específico de este módulo, verificado leyendo el `.xlsx`) y en
[Formato.md](../../../Formato.md) (patrón genérico reutilizable por futuros
módulos) — no se duplica acá. Si el usuario pide "recordar" una preferencia
de formato/color nueva, se agrega como entrada fechada en el historial de
`Formato Centro de Costos.md` (o `Formato.md` si aplica a todos los
módulos), no en este archivo.

## Reglas de negocio (no son formato)

- **IVA por defecto** si el JSON no trae `"iva"`: 19% del Neto (suma de
  ítems) para Factura/Guía de Despacho, 0 para el resto.
- **Extensiones válidas** de documentos: `.png .jpg .jpeg .heic .pdf`.
  Ignoradas: `.html .txt .ini .tmp` y `desktop.ini`.

## Criterios de clasificación

- **Equipos/herramientas de costo > $20.000, aunque la factura venga
  asociada a un proyecto** (pedido 2026-07-16): antes de registrar el
  documento, preguntar al usuario si corresponde efectivamente al proyecto
  indicado o si debería ir a Gastos Generales. Motivo: equipos/herramientas
  de ese monto muchas veces se compran a nombre de un proyecto pero en
  realidad son de uso general de la empresa, no un gasto exclusivo de ese
  centro de costos.

## Datos importantes de facturas / proveedores

*(sin entradas todavía — anotar acá, cuando el usuario pida "recordarlo",
cosas como: forma correcta de escribir el nombre de un proveedor recurrente,
códigos de producto que se repiten, obras/centros de costos que en realidad
son el mismo proyecto con distinto nombre en el documento, criterios de
categorización no obvios, etc.)*

## Historial de ejecuciones

### 2026-07-16 — primera corrida tras la reconstrucción del pipeline
- `status`: 24 documentos ya en `Master`, 34 N° Documento distintos, 48
  archivos cubiertos entre `Master` y `reconciliacion_archivos.json`, 0
  pendientes. 3 proyectos detectados: Cesfam Limache, Gastos Generales,
  UMAG.
- `run` con 0 documentos registrables: no tocó ninguna fila de datos (los 24
  documentos de `Master` quedaron intactos); solo creó backup y regeneró
  pies de tabla + hojas de proyecto.
- **Confirmado en esta corrida**: las hojas de proyecto se recalculan 100%
  desde la columna `Proyecto` actual de `Master` en cada `run`, no desde un
  estado guardado. De hecho corrigió sola la membresía de un documento que
  había sido reasignado a mano a otro proyecto directamente en `Master` —
  o sea, para mover un documento de proyecto basta con editar la celda
  `Proyecto` en `Master` y correr `run`; no hace falta tocar las hojas de
  proyecto a mano.

## Pendientes conocidos (requieren decisión del usuario, no son bugs)

- **Corregir retroactivamente TODOS los ítems ya registrados en el
  documento** (`Centro de Costos.xlsx` completo — `Detalle`/`Master` de
  todos los proyectos, no solo `PRUE-001`) a la nueva convención
  nombre/descripción (pedido 2026-07-16, pospuesto por tokens; ver
  `CLAUDE.md` → esquema de `datos_extraidos.json`): revisar cada fila de
  `Detalle` y, donde el nombre del ítem sea la descripción larga y/o incluya
  el código de producto (ej. "Cod. XXX"), separarlo en nombre simple +
  descripción sin código. En `datos_extraidos.json` hoy solo están los 13
  ítems de `PRUE-001` con este problema confirmado; falta revisar el resto
  de las filas de `Detalle` que vienen del pipeline perdido (no están en
  este JSON) para ver si tienen el mismo patrón. Hay que: (1) actualizar
  `datos_extraidos.json` donde aplique, (2) corregir a mano las filas ya
  escritas en `Detalle` y el "Resumen Ítems" de la fila correspondiente en
  `Master` para cada documento afectado — esto es una excepción deliberada a
  la regla de oro de no reescribir filas ya creadas, documentarla en
  [ERRORES.md](.claude/skills/Registro_Centro_de_Costos/ERRORES.md) cuando
  se haga.

- El pipeline anterior (perdido, corría en `Plantillas/`) tenía renombrado
  automático de fotos, conversión HEIC→JPG y detección automática de
  duplicados (`rename.py`, `detectar_duplicados.py`). Ninguna de las tres
  capacidades se reconstruyó — el script actual solo *avisa* de posibles
  duplicados por N° Documento repetido, no renombra ni convierte ni
  bloquea. Si se decide reconstruir alguna, anotar la decisión acá antes de
  tocar `auditor_centro_costos.py`.
- `Legado/datos_extraidos_legacy_umag.json` (22 documentos de UMAG, esquema
  sin ítems) no se ha migrado al esquema con ítems de línea. Esos 22
  documentos siguen en `Master` sin desglose granular en `Detalle`. No se ha
  decidido si vale la pena reconstruir ese desglose retroactivamente.
- El recoloreo rojo→azul marino oscuro descrito en [ERRORES.md](ERRORES.md)
  está en pausa por decisión del usuario (2026-07-16): por ahora ese
  archivo es solo bitácora, no se aplica ningún recoloreo (ni automático en
  el script ni manual). Cuando se pida activarlo, decidir ahí si se
  automatiza dentro de `auditor_centro_costos.py` o se hace puntual con
  openpyxl.
