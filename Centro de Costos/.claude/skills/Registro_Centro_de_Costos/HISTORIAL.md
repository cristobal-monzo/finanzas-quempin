# Historial de ejecuciones: Registro_Centro_de_Costos

Bitácora fechada de corridas reales del pipeline (cifras, hallazgos y
decisiones puntuales de cada `run`). Se separó de [MEMORY.md](MEMORY.md) el
2026-07-27 para que las reglas de negocio vigentes (que sí hay que releer
en cada corrida) no queden mezcladas con este registro histórico, que solo
se necesita al investigar cuándo/por qué pasó algo puntual.

## 2026-07-16 — primera corrida tras la reconstrucción del pipeline
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

## 2026-07-17 — renombrado retroactivo de los 24 documentos del bootstrap
- `status` reportaba "24 fila(s) sin archivo fisico encontrado para
  renombrar" pese a que los archivos físicos existían — bug en
  `resolver_ruta_actual()`, corregido (ver `ERRORES.md`).
- Tras el fix, `run` renombró/convirtió los 24: 22 en UMAG (HEIC→JPG) + 1 en
  Cesfam Limache (CFLI-001) + 1 en Gastos Generales (GGEN-001), todos a
  `<N° Ref.>_<TagProveedor>_<Fecha ISO>.<ext>`. `status` posterior confirmó
  0 pendientes de renombrar y 0 "archivo no encontrado".
- 0 documentos nuevos registrados en esta corrida (solo renombrado
  retroactivo).

## 2026-07-17 — 2 facturas nuevas, proyecto "Microturbina LER"
- `status` inicial: 2 pendientes, ambos sin datos en el JSON (fotos
  WhatsApp de facturas Danus Conexiones SpA N° 382870 y 383431). Se leyeron
  las fotos directamente, se agregaron entradas a `datos_extraidos.json` y
  se agregó el proyecto a `PREFIJOS_PROYECTO`.
- `run`: registró `MLER-001` (doc 383431, 4 ítems, con descuento 10%
  modelado como ítem negativo) y `MLER-002` (doc 382870, 2 ítems). Creó la
  hoja de proyecto "Microturbina LER". Sin inconsistencias, sin duplicados.
  Renombró/convirtió los 2 archivos físicos a la convención
  `<N° Ref.>_<TagProveedor>_<Fecha ISO>.jpeg`.

## 2026-07-17 — factura Beckman (CCON-004), columna nueva y corrección de N° Documento
- `status` inicial: 1 pendiente sin datos en el JSON (foto WhatsApp de
  Cesfam Constitución). Se leyó la foto directamente y se agregó al JSON —
  primer intento quedó como 1 solo ítem resumen (mal ingreso, ver
  `ERRORES.md`), corregido después a 5 ítems legibles + 1 "Materiales
  varios" para las 6 líneas tapadas por el timbre "CANCELADO".
- `run` registró `CCON-004` (doc 130020, Beckman). Se corrigió manualmente
  el desglose de `Detalle` tras el reporte del usuario.
- Se agregó la columna **"Total con IVA (CLP)"** al final de `Detalle`
  (pedido del usuario) — cada ítem usa la tasa real IVA/Neto del documento
  (no 19% fijo), para que sirva también en documentos exentos/Zona Franca;
  puede haber una diferencia de $1 por redondeo entre la suma de esta
  columna por N° Ref y el "Total con IVA" de `Master` (mismo tipo de
  redondeo que ya existe en otros totales de este libro). Migración
  retroactiva `migrar_columna_total_con_iva_detalle()` la rellenó para las
  106 filas de `Detalle` existentes en esa corrida.
- Se implementó y aplicó retroactivamente la regla "N° Documento sin ceros a
  la izquierda" (42 celdas corregidas entre `Master` y `Detalle`, ver
  `ERRORES.md`).
