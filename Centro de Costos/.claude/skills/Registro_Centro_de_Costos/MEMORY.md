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

- **`Detalle` siempre lleva el desglose línea por línea de la compra, nunca
  un ítem resumen** (pedido 2026-07-17, tras corregir `CCON-004`): cada línea
  de la factura/boleta va como su propio ítem en `datos_extraidos.json`
  (`nombre_item`, `cantidad`, `p_unitario_sin_iva` reales de esa línea), no
  un solo ítem "Materiales varios" o similar por el total del documento.
  **Excepción explícita, no una salida fácil**: si una PARTE de la factura es
  físicamente ilegible (timbre, doblez, foto cortada), desglosa las líneas
  que SÍ se leen cada una por separado, y agrupa SOLO las ilegibles en 1
  ítem aparte (ej. "Materiales varios") por el saldo entre el Neto impreso y
  la suma de las líneas legibles — nunca agrupes TODO el documento en 1 ítem
  cuando alguna línea es legible. Precedente: `CCON-004` (factura Beckman
  N° 130020, ver `ERRORES.md`) — 5 de 11 líneas legibles se registraron cada
  una por separado, las 6 tapadas por el timbre "CANCELADO" se agruparon en
  1 ítem "Materiales varios".
- **IVA por defecto** si el JSON no trae `"iva"`: 19% del Neto (suma de
  ítems) para Factura/Guía de Despacho, 0 para el resto.
- **Extensiones válidas** de documentos: `.png .jpg .jpeg .heic .pdf`.
  Ignoradas: `.html .txt .ini .tmp` y `desktop.ini`.
- **`n_documento` no puede empezar con "0"** (pedido 2026-07-17, implementado
  ese mismo día tras detectarse que la regla se había documentado pero nunca
  codificado — ver `ERRORES.md`): si el N° de Documento extraído de la
  factura/boleta parte con uno o más ceros a la izquierda, hay que
  quitarlos hasta que el primer dígito sea distinto de cero antes de
  registrarlo (ej. `"0456"` → `"456"`). Aplica al poblar
  `datos_extraidos.json` y a cualquier corrección manual del campo.
  Implementado en `normalizar_n_documento()` (`Sistema/auditor_centro_costos.py`),
  usado al escribir documentos nuevos y al aplicar correcciones manuales de
  esa columna; migración retroactiva `migrar_n_documento_sin_ceros()` corrió
  sobre todo `Master`/`Detalle` el 2026-07-17 (42 celdas corregidas).
- **Proveedores de Punta Arenas / Patagonia (Zona Franca)** (pedido
  2026-07-17): el IVA puede **no** venir incluido en la factura por el
  régimen de Zona Franca. Al extraer/verificar `"iva"` de un documento de un
  proveedor de esa zona, no asumir automáticamente 19% del Neto — revisar si
  la factura realmente desglosa IVA o no antes de completar el campo.
- **Pasajes de bus (transporte de pasajeros) están exentos de IVA**
  (confirmado por el usuario 2026-07-17): tanto servicios urbanos como
  rurales e interurbanos — el valor del pasaje no incluye el 19% de IVA. Al
  extraer/verificar `"iva"` de una boleta de pasaje de bus (Tur Bus y
  similares), el valor correcto es 0, no 19% del Neto. Precedente: boleta
  Tur Bus N° 0000162354 (`UMAG-009`).

## Criterios de clasificación

- **Por defecto, asumir Factura como `tipo_documento`** (pedido 2026-07-17):
  solo preguntar al usuario si es Boleta cuando haya una sospecha clara (ej.
  el documento se ve claramente como boleta simplificada, sin desglose de
  IVA/razón social). Motivo: los vouchers/comprobantes de pago dicen "Válido
  como boleta" impreso de forma estándar **incluso cuando la compra en
  realidad se hizo con factura** — ese texto no es evidencia de que el
  documento sea una boleta, así que no debe gatillar la pregunta por sí
  solo.
- **`nombre_item` debe ser el tipo de producto genérico, sin marca ni
  adjetivos** (pedido 2026-07-17, endurece la regla del 2026-07-16): ej.
  "Hidrolavadora Karcher portátil" → `nombre_item` = "Hidrolavadora",
  `descripcion` = "Hidrolavadora Karcher portátil" (con el resto del detalle
  que traiga la factura — modelo, medidas — pero sin el código de
  producto). Motivo: "Resumen Ítems" en `Master` se arma uniendo los
  `nombre_item` de cada documento, así que mientras más genérico el
  nombre, más legible queda ese resumen. Ver esquema actualizado en
  `CLAUDE.md` → "Esquema de `datos_extraidos.json`".
- **Equipos/herramientas de costo > $20.000, aunque la factura venga
  asociada a un proyecto** (pedido 2026-07-16): antes de registrar el
  documento, preguntar al usuario si corresponde efectivamente al proyecto
  indicado o si debería ir a Gastos Generales. Motivo: equipos/herramientas
  de ese monto muchas veces se compran a nombre de un proyecto pero en
  realidad son de uso general de la empresa, no un gasto exclusivo de ese
  centro de costos.

## Datos importantes de facturas / proveedores

- **Proyecto nuevo "Microturbina LER"** (detectado 2026-07-17): prefijo de
  N° Ref. `MLER` (decisión del usuario, evita colisión con `MICR` que se
  habría derivado automáticamente), `tipo_proyecto` = `I+D+i` (decisión del
  usuario). Ambos agregados a `PREFIJOS_PROYECTO` en
  `Sistema/auditor_centro_costos.py`.
- **Facturas con descuento global (no por ítem)**: el esquema de
  `datos_extraidos.json` no tiene campo de descuento a nivel documento. Se
  modela agregando un ítem adicional `{"nombre_item": "Descuento", ...,
  "p_unitario_sin_iva": -<monto>}` para que la suma de ítems en `Detalle`
  cuadre exactamente con el Neto impreso en la factura (necesario para que
  `verificar_aritmetica` no marque falsa inconsistencia). Precedente:
  factura Danus Conexiones N° 383431 (`MLER-001`, 2026-07-17), descuento
  10% sobre Sub Total.

## Visualizador web

- **Link del Artifact publicado**: `https://claude.ai/code/artifact/1b82085c-c63c-407c-8f03-e4db9f2b551e`.
  **Regla explícita del usuario (2026-07-19): siempre actualizar este mismo
  link, nunca generar uno nuevo.** Al republicar, pasar este URL como `url`
  al tool `Artifact` (o, si la sesión que lo publicó originalmente sigue
  abierta, redeployar con el mismo `file_path` — ambos casos apuntan al
  mismo link; sin uno de los dos, una sesión nueva mintea un link distinto).
- Flujo para actualizar: `python driver.py visualizador` (regenera
  `Visualizador Web/build/index.html` desde el Excel actual) → publicar ese
  archivo como Artifact con el `url` de arriba. Ver arquitectura completa en
  [../../Visualizador Web/CLAUDE.md](../../Visualizador%20Web/CLAUDE.md).
- La contraseña de acceso del gate vive como constante en
  `Visualizador Web/template.html` (no se repite acá — ya es visible en el
  HTML publicado, ver nota de "no es seguridad real" en ese `CLAUDE.md`).

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

### 2026-07-17 — renombrado retroactivo de los 24 documentos del bootstrap
- `status` reportaba "24 fila(s) sin archivo fisico encontrado para
  renombrar" pese a que los archivos físicos existían — bug en
  `resolver_ruta_actual()`, corregido (ver `ERRORES.md`).
- Tras el fix, `run` renombró/convirtió los 24: 22 en UMAG (HEIC→JPG) + 1 en
  Cesfam Limache (CFLI-001) + 1 en Gastos Generales (GGEN-001), todos a
  `<N° Ref.>_<TagProveedor>_<Fecha ISO>.<ext>`. `status` posterior confirmó
  0 pendientes de renombrar y 0 "archivo no encontrado".
- 0 documentos nuevos registrados en esta corrida (solo renombrado
  retroactivo).

### 2026-07-17 — 2 facturas nuevas, proyecto "Microturbina LER"
- `status` inicial: 2 pendientes, ambos sin datos en el JSON (fotos
  WhatsApp de facturas Danus Conexiones SpA N° 382870 y 383431). Se leyeron
  las fotos directamente, se agregaron entradas a `datos_extraidos.json` y
  se agregó el proyecto a `PREFIJOS_PROYECTO`.
- `run`: registró `MLER-001` (doc 383431, 4 ítems, con descuento 10%
  modelado como ítem negativo) y `MLER-002` (doc 382870, 2 ítems). Creó la
  hoja de proyecto "Microturbina LER". Sin inconsistencias, sin duplicados.
  Renombró/convirtió los 2 archivos físicos a la convención
  `<N° Ref.>_<TagProveedor>_<Fecha ISO>.jpeg`.

### 2026-07-17 — factura Beckman (CCON-004), columna nueva y corrección de N° Documento
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

## Pendientes conocidos (requieren decisión del usuario, no son bugs)

- ~~`CCON-004` (factura Beckman N° 130020) tiene 6 de 11 líneas sin
  desglosar~~ — **resuelto 2026-07-17**: la foto resultó completamente
  legible al revisarla con la skill `/Revision_de_Errores` (nueva capacidad
  de desglosar ítems agrupados), el timbre "CANCELADO" no tapaba los números
  como se pensó originalmente. Ver detalle en `ERRORES.md`.

- **Corregir retroactivamente TODOS los ítems ya registrados en el
  documento** (`Centro de Costos.xlsx` completo — `Detalle`/`Master` de
  todos los proyectos, no solo `PRUE-001`) a la nueva convención
  nombre/descripción (pedido 2026-07-16, endurecida 2026-07-17, pospuesto
  por tokens; ver `CLAUDE.md` → esquema de `datos_extraidos.json`): revisar
  cada fila de `Detalle` y, donde `nombre_item` no sea ya el tipo de
  producto genérico sin marca/adjetivos (ej. traiga marca, variante, la
  descripción larga y/o el código de producto), separarlo en nombre
  genérico + descripción con el detalle sin código. En `datos_extraidos.json`
  hoy solo están los 13 ítems de `PRUE-001` con este problema confirmado;
  falta revisar el resto de las filas de `Detalle` que vienen del pipeline
  perdido (no están en este JSON) para ver si tienen el mismo patrón. Hay
  que: (1) actualizar `datos_extraidos.json` donde aplique, (2) corregir a
  mano las filas ya escritas en `Detalle` y el "Resumen Ítems" de la fila
  correspondiente en `Master` para cada documento afectado — esto es una
  excepción deliberada a la regla de oro de no reescribir filas ya creadas,
  documentarla en
  [ERRORES.md](.claude/skills/Registro_Centro_de_Costos/ERRORES.md) cuando
  se haga.

- El pipeline anterior (perdido, corría en `Plantillas/`) tenía renombrado
  automático de fotos, conversión HEIC→JPG y detección automática de
  duplicados (`rename.py`, `detectar_duplicados.py`). El renombrado y la
  conversión HEIC→JPG **sí se reconstruyeron** (2026-07-16, extendido a los
  24 documentos del bootstrap el 2026-07-17, ver `ERRORES.md`). La
  detección automática de duplicados sigue sin reconstruirse — el script
  solo *avisa* de posibles duplicados por N° Documento repetido, no
  bloquea. Si se decide reconstruirla, anotar la decisión acá antes de
  tocar `auditor_centro_costos.py`.
- `Legado/datos_extraidos_legacy_umag.json` (22 documentos de UMAG, esquema
  sin ítems) no se ha migrado al esquema con ítems de línea. Esos 22
  documentos siguen en `Master` sin desglose granular en `Detalle`. No se ha
  decidido si vale la pena reconstruir ese desglose retroactivamente.
- **Recoloreo rojo→azul marino oscuro: activado el 2026-07-17** (ver
  [ERRORES.md](ERRORES.md)) — `run` detecta correcciones manuales en
  celdas rojas y las deja "Pendiente" (JSON + tabla); `driver.py confirmar
  --todos` las aplica (recolorea + propaga a Detalle). Ya no es un
  pendiente.
