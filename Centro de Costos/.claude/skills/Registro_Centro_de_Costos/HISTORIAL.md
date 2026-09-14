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

## 2026-09-10 — proyecto nuevo "Junji V2" (JUN2), 21 documentos, y una carpeta que era mitad re-subida

Corrida vía `/Actualizar_Finanzas run`. `status` inicial: **36 pendientes sin
datos en el JSON** (4 en `259. FACH 2`, 29 en la carpeta nueva `Junji V2`, 3
en `Junji's Valparaiso`). Tras leer los 36 documentos uno por uno:

- **15 de los 29 archivos de `Junji V2` no eran documentos nuevos.** Los
  `Documento (73)`–`(84)` son exactamente los mismos documentos ya
  registrados como `Junji's Valparaiso/Documento (15)`–`(26)` (offset
  constante de 58 en la numeración del escaneo); `(85)` y `(86)` son las
  guías de despacho 1844884/1844885 de la factura ANWO 1936317, que sí se
  registró vía `(87)`; y `(99)` era una copia byte a byte de `(98)`. Los 15
  se movieron a `Junji V2/Duplicados/` (decisión del usuario). **Ojo para el
  futuro: `inventariar_archivos()` no recursa subcarpetas**, así que
  `<Proyecto>/Duplicados/` es el lugar canónico para parquear un archivo
  que no debe registrarse nunca, sin borrarlo.
- Los 2 vouchers `V2 Documento (17)_3.pdf` y `V2 Documento (18)_3.pdf` de
  `Junji's Valparaiso` —que una corrida anterior ya había dejado fuera a
  propósito por respaldar boletas/facturas registradas (ver notas de
  `V2 Documento (28)_3` y `(24)_1`)— se movieron también a `Duplicados/`.
  Antes reaparecían como pendientes en cada `status`.
- **Proyecto nuevo `Junji V2`**, prefijo `JUN2`, `tipo_proyecto`
  "Mantenimiento" (ambos decisión del usuario). Agregado a
  `PREFIJOS_PROYECTO`.
- **Una factura repartida en dos centros de costo**: la ANWO 1842307
  (25-03-2026, Neto $162.881) incluía una "Prensa PEX c/ abocardador y
  tijera" por $97.033. Por la regla de equipos/herramientas > $20.000 el
  usuario la mandó a Gastos Generales: se copió el PDF a esa carpeta y se
  crearon 2 entradas —`JUN2-007` (resto, Neto $65.848 / IVA $12.511) y
  `GGEN-003` (prensa, Neto $97.033 / IVA $18.436 prorrateado al 19%)—. El
  informe marca "posible duplicado" por el N° Documento repetido: es
  esperado, no un error.
- 2 archivos traían 2 documentos tributarios cada uno y se separaron con
  `driver.py separar`: `Documento (100)` (Enex 5949060 + Sodimac 148181080)
  y `Documento (101)` (Hidroracu 66413 + Covarrubias/Enex 386507).

`run`: **21 documentos nuevos** — `JUN2-001`..`JUN2-016`, `FCH2-054`..
`FCH2-057`, `GGEN-003`. Neto $5.442.770 + IVA $1.080.692 = **$6.523.462**
(FACH2 $5.501.353, Junji V2 $906.640, Gastos Generales $115.469). Hoja
`JUN2` creada; 21 archivos renombrados; 0 inconsistencias aritméticas
nuevas; 0 correcciones manuales pendientes. Quedó 1 pendiente deliberado:
`V2 Documento (40)_5.pdf` (boleta Urtubia Meza N° 51025, $8.700 — el
escaneo corta la fecha de emisión).

Proveedores nuevos: Electricidad Ignacio Adui Zapata Gonzalez E.I.R.L.
(subcontrato eléctrico FACH), Victor Contreras M. y Cia Ltda (Distribuidora
Santa Ines), Flexibles Covarrubias Limitada, Fercomet SpA, Hidroracu
Limitada.

## 2026-09-11 — "Junji V2" no era un proyecto: se fusionó en Junji's Valparaiso

Aclaración del usuario: `Junji V2` **es** Junji's Valparaiso. La carpeta
existía porque en Valparaíso se habían ingresado facturas *cortadas*, sin toda
la información, y `Junji V2` era el reingreso de esas facturas. Sus montos
**suman** a Valparaíso, no son un centro de costos aparte. El proyecto vivió
un solo día (lo creó la corrida del 2026-09-10).

Que sumar fuera aritméticamente correcto no era obvio y se verificó antes de
mover nada: de los 52 archivos que pasaron por esa carpeta, los 21 que sí eran
re-subidas de documentos ya registrados en JUNJ se habían apartado a
`Excel/Respaldos/Septiembre 2026/Junji V2 - re-subidas ya registradas en JUNJ`
y otros 15 a `Junji V2/Duplicados/` (ambas cosas, la corrida del 2026-09-10).
Los 16 que quedaban eran documentos nuevos → **cero doble conteo**.

Decisiones del usuario al fusionar:

- **Los 16 PDF a la raíz** de `Junji's Valparaiso/`, no a una subcarpeta
  `Junji's Valparaiso/Junji V2/`. Es obligatorio, no cosmético:
  `inventariar_archivos()` no recursa subcarpetas, así que una subcarpeta los
  habría dejado fuera del registro —el mismo mecanismo por el que
  `Duplicados/` funciona como estacionamiento— y sus montos se habrían caído
  del total de Valparaíso, justo lo contrario de lo pedido.
- **Renumerar** `JUN2-001`..`016` → `JUNJ-240`..`255` (no mantener los JUN2-*
  dentro de la hoja JUNJ): el prefijo se deriva del proyecto vía
  `prefijo_para_proyecto()`, así que dejarlos habría dado una hoja con
  numeración mixta.

Migración (script de un uso, con dry-run y respaldo previo del libro y de los
dos JSON en `Excel/Respaldos/Septiembre 2026/... antes de fusionar JUN2 en
JUNJ ...`): 16 filas de Master (N° Ref + Proyecto + `Archivo origen` +
relleno `FFB7CE`), 64 de Detalle, 16 PDF movidos y renombrados, 15 de
`Duplicados/`, 16 entradas de `datos_extraidos.json`, hoja `JUN2` borrada,
`Junji V2` fuera de `PREFIJOS_PROYECTO`. Monto reasignado: Neto $722.751 +
IVA $183.889 = **$906.640** (idéntico al que reportó la corrida del 09-10 para
Junji V2, o sea nada se perdió ni se duplicó). Junji's Valparaiso queda con
**256 documentos**, $13.620.125 c/IVA. La carpeta residual —solo artefactos
del escáner (`PP11Thumbs.ptn`, `MaxDesk.ini`, `.ppinfocache`), ningún
documento— se apartó a `Excel/Respaldos/Septiembre 2026/Junji V2 - carpeta
residual tras fusionar en JUNJ`, y el espejo vacío de Perú se eliminó.

Tres cosas que hubo que verificar antes de escribir, y que conviene repetir en
cualquier fusión/renombre de proyecto futuro:

- **El relleno de fila hay que repintarlo a mano.** Cambiar `Master.Proyecto`
  **no** repinta nada en una corrida normal: `pintar_fila()` sobre Master solo
  corre desde `escribir_fila_master()` (filas nuevas), y
  `asignar_colores_proyectos()` *lee* el color desde las filas existentes. Con
  16 filas del proyecto pintadas de un color y 239 de otro, el mapa
  proyecto→color se resuelve por "gana la última fila leída" y
  `regenerar_hoja_proyecto()` habría pintado la hoja JUNJ entera con el color
  equivocado. (La leyenda del libro dice que el color "se actualiza solo" al
  cambiar el proyecto; eso vale para `migrar_paleta_colores()`, no para el
  `run`.) Repintar es seguro: rojo y azul marino son color de **fuente**, no
  de relleno, así que `pintar_fila()` no se los come.
- **Los hallazgos se clavan a `(proyecto, archivo)`**, vía
  `clave_documento()` → `id_hallazgo()`. Cambiar el proyecto cambia el id de
  todo hallazgo de esos documentos, y uno ya cerrado se **reabriría** como
  nuevo. Se verificó antes de aplicar que ninguno de los 80 hallazgos del
  registro estuviera claveado a un documento de `Junji V2` (el único que lo
  menciona está claveado a `Gastos Generales\...`, por el reparto de la ANWO
  1842307 entre GGEN-003 y el ex JUN2-007, hoy JUNJ-246; solo se le actualizó
  el texto). Si alguno lo hubiera estado, había que migrar su id.
- **El renombrado del pipeline no mueve archivos entre carpetas**:
  `planificar_renombrado_fila()` calcula `ruta_actual.parent / nombre_nuevo`.
  Por eso el mover fue parte de la migración y no algo que el `run` arreglara
  después. Se usó `nombre_esperado_archivo()` del propio módulo para generar
  los nombres nuevos, y el `status` posterior confirmó **0 archivos por
  renombrar** y **0 cambios manuales detectados**.

`run` posterior: 0 documentos nuevos (lo esperado — no entró nada, solo se
reasignó), 21 hojas regeneradas, hoja `JUNJ` de 239 → 256 filas. 796 tests
pasando. Tablero republicado en GitHub Pages (19 proyectos, ya no 20).

**Ojo con las corridas en paralelo**: mientras esta fusión corría, otra sesión
de Claude trabajaba sobre el mismo módulo y registró `JUNJ-256`
(`V2 Documento (40)_5.pdf`, el pendiente deliberado del 09-10) entre mi `run`
y mi verificación. Los dos conjuntos de cambios sobrevivieron porque la otra
corrida leyó el libro ya guardado por la mía, pero fue suerte de secuencia, no
de diseño: dos `run` simultáneos sobre `Centro de Costos.xlsx` se pisan sin
aviso.

## 2026-09-14 — recorrido completo de celdas rojas: 24 → 4, y por qué volvían

Revisión de errores sobre las 24 celdas en rojo del libro (el usuario llegó
por el KPI "7 requieren revisión manual" del tablero: eran los 7 de Junji's
Valparaiso, porque `renderKPIs` recalcula sobre los documentos **filtrados**,
no sobre el total. No había divergencia de cálculo).

Se cerraron 20. Las 4 que quedan (`JUNJ-141`, `HPIN-161`, `HPIN-163`,
`HPIN-172`) tienen dígitos físicamente tapados por la marca de agua del
voucher o por un pliegue del papel — se sacan de la cartola de la Mastercard
9309, no de la foto.

Lo que conviene no reaprender:

- **Una corrección de impuesto no sobrevivía a la corrida siguiente.**
  `migrar_color_cuadre_impuesto()` repintaba de rojo toda celda cuyo cuadre
  diera `error`, sin mirar si ya estaba en azul marino. `UMAG-005` se
  corrigió el 2026-07-17 y reapareció idéntica el 2026-09-14, como si nadie
  la hubiera visto. Ahora la función salta las celdas azul marino (test:
  `test_respeta_una_celda_ya_corregida_a_mano`). **Si agregas otra migración
  de color, respeta el azul marino igual**: es la marca de "esto lo adjudicó
  una persona".
- **Había una clase de documento sin representación: la venta exenta.**
  `UMAG-005`/`UMAG-020` son facturas de la Zona Franca de Punta Arenas
  (Crosur), que llevan el impuesto del Art. 11 de la Ley 18.211 (0,15% sobre
  el CIF, incluido en el precio) y nunca el 19%. Registradas como "Factura"
  no había valor posible para su celda de impuesto: cualquiera la dejaba en
  rojo. Se agregó `"factura exenta"` a `TIPOS_DOCUMENTO_CONOCIDOS`, fuera de
  `TIPOS_AFECTOS`. Las dos pasaron a ese tipo.
- **Una celda de IVA en rojo puede ser un problema de neto, no de impuesto.**
  `JUNJ-020` y `JUNJ-018` (facturas Anwo 1913313 y 1913076) tenían el IVA
  impreso correcto; lo que estaba mal era el Detalle, que había cargado la
  columna `TOTAL PREC. LISTA REF` en vez del `TOTAL` con descuento (la
  válvula bola PPR 032 sola: 20.837 cargado vs 10.773 pagado, 48,30% de
  descuento). Corregidas las 5 filas con `corregir-item`, los dos netos
  quedaron exactos al impreso (54.789 y 11.275) y el cuadre dio solo. Mirar
  `items <N_REF>` **antes** de tocar la columna de impuesto.
- **El color de la celda no se recalcula al corregir un ítem.** `corregir-item`
  arregla el neto pero no repinta: las dos celdas siguieron rojas hasta correr
  `migrar_color_cuadre_impuesto()` (que es parte de `run`).
- **Las fotos no se recortan por documento.** Los 12 refs de Mercado Pago
  apuntaban a solo 2 archivos, byte a byte idénticos, copiados 7 y 5 veces;
  cada foto tiene 9 y 6 comprobantes distintos. Los datos están completos y
  sin duplicar (se verificaron los 15 comprobantes contra el libro), pero no
  hay trazabilidad ref → documento. Sin resolver, decisión del usuario.
- **Al cazar un comprobante dentro de una foto, calza por el monto impreso,
  no por el total registrado.** Buscar "$8.500" (TOTAL A PAGAR, redondeado)
  no encuentra nada; el libro guarda 8.505 (TOTAL VENTA). Por ese error
  reporté dos boletas como no registradas cuando eran `JUNJ-123` y
  `JUNJ-124`.
- **Dos fechas corridas de mes**, detectadas al calzar cada ticket con su
  fila: `HPIN-161` figuraba 25-03 y el ticket dice 25/02; `HPIN-172` figuraba
  24-03 y dice 04/03. Corregidas en `Master` y en `datos_extraidos.json`.

Convenciones aplicadas (ya existentes, ver MEMORY.md): comprobante de pago de
derechos municipales por estacionamiento → `N/A`, igual que los peajes (no
trae folio reutilizable); voucher Mercado Pago → el N° de Operación como N°
de Documento.

**Pendiente al cerrar**: las hojas de proyecto (`UMAG`, `HPIN`) y el tablero
publicado todavía muestran los valores viejos de las 4 celdas editadas fuera
del camino auditado (tipo de documento y fechas) — se propagan con un `run`.
