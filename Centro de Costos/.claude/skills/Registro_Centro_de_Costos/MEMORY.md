# Memoria: Registro_Centro_de_Costos

Bitácora de observaciones, preferencias y decisiones que surgen de **usar**
el pipeline sobre datos reales. Complementa a [SKILL.md](SKILL.md) (el
procedimiento estable: comandos, esquema del JSON, troubleshooting),
[HISTORIAL.md](HISTORIAL.md) (bitácora fechada de corridas reales) y
[ERRORES.md](ERRORES.md) (historial de errores del pipeline + correcciones
manuales pendientes de recolorear en el Excel).

## Qué va en cada archivo

- **SKILL.md** — cómo correr el driver, qué esperar de cada comando, formato
  del JSON, gotchas *estructurales* (comportamiento del script que es
  siempre así, sin importar la fecha), troubleshooting genérico.
- **MEMORY.md (este archivo)** — reglas de negocio y criterios de
  clasificación **vigentes**, datos importantes de facturas/proveedores que
  vale la pena recordar, pendientes que dependen de una decisión del
  usuario. **No** historial fechado de corridas (va en
  [HISTORIAL.md](HISTORIAL.md)) ni preferencias de color/formato (van en
  [Formato Centro de Costos.md](../../../Formato%20Centro%20de%20Costos.md)
  / [Formato.md](../../../Formato.md) si son genéricas para todos los
  módulos) — así este archivo se mantiene corto y solo con lo que hay que
  releer en cada corrida.
- **HISTORIAL.md** — bitácora fechada de corridas reales del pipeline:
  cifras, hallazgos y decisiones puntuales de cada `run`. Se consulta solo
  para investigar cuándo/por qué pasó algo específico, no para reglas
  vigentes.
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

## Convenciones de `/Revision_de_Errores`

- **Siempre abrir el documento fuente antes de preguntarle al usuario el
  valor correcto** (confirmado 2026-08-20, durante un recorrido real):
  aunque el driver `errores` ya imprime la ruta a la foto/PDF, el agente
  debe leerla con la herramienta de archivos y comparar el valor propio
  contra lo impreso en el documento **antes** de preguntar — no preguntar en
  seco esperando que el usuario abra el archivo por su cuenta. Refuerza el
  Paso 2 de [SKILL.md](../Revision_de_Errores/SKILL.md) (que ya lo pedía);
  esta entrada lo deja explícito porque el usuario lo señaló como algo a no
  olvidar. Aplica igual al recorrido de ítems agrupados (Paso 5).

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
- **Cuando un archivo trae varios documentos distintos (varias boletas/
  comprobantes en la misma foto/PDF), cada uno se registra como un N° Ref.
  separado — nunca se mezclan sus ítems bajo 1 solo N° Ref.** (pedido
  2026-08-20, corrigiendo un error real: `CCON-012` había juntado una carga
  de diesel + una boleta de snack de Pronto como si fueran 1 documento, y
  `CCON-013` había juntado un ticket de estacionamiento + un combo de
  comida de fechas distintas — ambos casos detectados y corregidos vía
  `/Revision_de_Errores`, ver `ERRORES.md`). Esto es más estricto que la
  regla de duplicación física de abajo (que ya cubre el caso de *registrar*
  documentos nuevos): aplica también al **corregir** un registro ya escrito
  que mezcló documentos por error — hay que separarlo en N° Ref. distintos,
  no dejarlo "arreglado" dentro de 1 solo N° Ref con 2+ documentos fuente
  distintos (fechas/N° de documento/proveedor propios cada uno).
- **Un PDF/foto subido con varias facturas/boletas se duplica físicamente,
  nunca se referencia dos veces** (pedido 2026-08-18): si un solo archivo
  contiene N documentos distintos, se crean N copias físicas en la carpeta
  del proyecto (`Sitio de comunicación - Centro de Costos 1/Facturas y
  Boletas/<Proyecto>/`) con sufijo numérico antes de la extensión —
  `<nombre-original>_1.pdf`, `<nombre-original>_2.pdf`, etc. — y una entrada
  de `datos_extraidos.json` por copia, cada una con su propio `"archivo"`.
  El sufijo es temporal: el siguiente `run` le asigna N° Ref. a cada copia y
  las renombra según la convención habitual
  (`<N° Ref.>_<TagProveedor>_<Fecha>.<ext>`). Motivo: `buscar_dato_por_archivo()`
  empareja por `(proyecto, archivo)` y devuelve solo la primera coincidencia
  — si dos entradas del JSON compartieran el mismo nombre de archivo, la
  segunda factura se perdería en silencio (nunca se escribe en Excel).
  Duplicar preserva la regla implícita "1 archivo físico = 1 documento" que
  ya usa todo el pipeline (inventario, columna "Archivo origen", renombrado),
  sin tocar el código del script.
- **Notas de Crédito SÍ se registran, como documento con montos negativos**
  (confirmado explícitamente por el usuario 2026-08-18, formaliza un
  precedente tácito que ya existía sin documentar — `UMAG-025`, Danus
  Conexiones, `fecha_modificacion` 2026-07-24): `"tipo_documento":
  "Nota de Crédito"` y `"estado": "Nota de Crédito"`; cada ítem lleva
  `"cantidad"` **positiva** (la cantidad devuelta) y `"p_unitario_sin_iva"`
  **negativo** (no al revés — no uses cantidad negativa), con
  `"descripcion"` prefijada `"Devolución - "`; `"iva"` del documento también
  negativo. El resultado es que `total_sin_iva`/`iva`/`total_con_iva`
  quedan negativos y se restan solos del acumulado del proyecto vía las
  fórmulas `SUMIF` de `Master` — no hace falta tocar el script (
  `verificar_aritmetica`/el cálculo por defecto de IVA solo aplican a
  `tipo_documento` Factura/Guía de Despacho con total positivo, así que una
  Nota de Crédito con IVA explícito los evita automáticamente). Si la
  factura original que corrige SÍ está en el mismo lote de pendientes,
  regístrala también normal; si no está (caso típico), anótalo en
  `"notas"` con el N° de la factura original y su fecha, no bloquea el
  registro de la nota de crédito. **Distinto del criterio de Cotizador
  Histórico** (ver `feedback_cotizador_no_notas_credito` en la memoria
  global): ese módulo SÍ excluye estas líneas de su índice de precios (por
  signo negativo, no por `tipo_documento`) porque ahí una devolución
  distorsionaría la estimación de costo por ítem — pero en `Master`/
  `Detalle` de este módulo sí deben quedar registradas, para que el gasto
  neto del proyecto sea correcto.
- **Compras de combustible (diésel/bencina): el campo "IVA 19% (CLP)" de
  Master debe incluir el conjunto de impuestos de la boleta/factura, no solo
  el IVA literal** (pedido 2026-08-19, durante un recorrido de
  `/Revision_de_Errores`; extendido el mismo día — "cuando sea combustible,
  aplica esta regla siempre que ingreses facturas, no me debes preguntar
  cada vez"): esta es una regla **fija, aplicar sin pedir confirmación** al
  usuario, tanto al poblar `"iva"` en `datos_extraidos.json` para un
  documento de combustible nuevo como al resolver la celda roja después vía
  `/Revision_de_Errores` — el desglose sale directo del propio documento
  (siempre trae impresos IVA/IEF/IEV·FEPP y el TOTAL final), no es una
  decisión que dependa del usuario. Estos documentos suelen traer, además del
  "IVA (19%)", un **IEF** (Impuesto Específico a los Combustibles) y un
  **IEV/FEPP** (mecanismo de estabilización, puede ser negativo) que también
  forman parte de lo efectivamente cobrado. Como `Master` no tiene columnas
  separadas para estos impuestos, el valor que va en "IVA 19% (CLP)" (columna
  L, alimenta "Total con IVA" = K+L) debe ser la **suma de los tres**
  (IVA + IEF + IEV/FEPP), de forma que "Total con IVA" cuadre con el "TOTAL"/
  "TOTAL A PAGAR" real impreso en el documento — no con 19% del Neto a
  secas. Ejemplo (factura Comercial La Punta Limitada, `CVAL-018`,
  20-07-2026): Neto $37.831, IVA $7.188, IEF $4.111, IEV/FEPP -$2.500 → 
  "IVA 19% (CLP)" = 7188+4111-2500 = **$8.799** (= Total $46.630 - Neto
  $37.831). Esto hace que `verificar_aritmetica` siga marcando la celda en
  rojo (no coincide con el 19% literal) — es esperado, no un bug: se
  resuelve con `/Revision_de_Errores`, que además debe dejar el desglose
  individual como nota de la celda (`corregir ... --nota "IVA: $X / IEF: $Y
  / IEV/FEPP: $Z"`, agregado 2026-08-19 a `corregir_valor_manual()` — queda
  como comentario de Excel en la celda + en la columna "Nota" de la tabla de
  [ERRORES.md](.claude/skills/Registro_Centro_de_Costos/ERRORES.md)), ya que
  el valor combinado por sí solo no es auto-explicativo.
  **Cuando el IVA/IEF/IEV impresos no cuadran entre sí** (pedido 2026-08-19,
  extiende la regla de arriba): en varios documentos reales el "IVA (19%)"
  impreso SÍ coincide con el 19% del Neto (osea, IVA y Neto son
  mutuamente consistentes), pero Neto + IVA + IEF + IEV impresos **no**
  suman el "TOTAL"/"TOTAL A PAGAR" real del documento — la diferencia es
  demasiado grande para ser redondeo (ver `CVAL-017`, `CCHI-005`,
  `CCHI-008`, todos con este patrón, gaps de -$3.131 a -$5.498). En vez de
  perseguir el motivo exacto (probablemente el IEF/IEV impreso no
  corresponde a esta venta puntual, o el diseño de boleta no lo desglosa
  bien), **el error se absorbe en el conjunto IEF+IEV/FEPP, tratado como
  una sola incógnita**: se respeta el Neto ya registrado en `Detalle` y el
  "TOTAL"/"TOTAL A PAGAR" real como ancla, y se calcula
  `IEF+IEV/FEPP (combinado) = Total - Neto - IVA impreso` (puede dar
  negativo). El valor final de "IVA 19% (CLP)" en `Master` sigue siendo
  `Total - Neto` (no cambia), y la nota pasa a documentar el IVA impreso
  por separado del combinado IEF+IEV/FEPP resultante, ej.: `"IVA: $7403 /
  IEF+IEV-FEPP (combinado): $-5498 -- ajustado para que Neto + IVA +
  Impuestos = Total pagado $40869"`. **Aplicar esto automáticamente
  (sin preguntar) mientras el IEF+IEV/FEPP combinado resultante quede en un
  rango similar a los ya vistos** (aprox. -$6.000 a +$6.000, mismo orden de
  magnitud que los ejemplos de este módulo) — **consultar al usuario si el
  valor sale mucho más alto, muy distinto en signo de lo esperado, o el IVA
  impreso ni siquiera se acerca al 19% del Neto** (señal de que el problema
  es otro, no solo IEF/IEV mal impresos).
- **En comprobantes (vouchers de tarjeta, comprobantes de débito, etc.) sin
  un N° de Documento como tal, usar el código de autorización** (pedido
  2026-08-19, decidido durante un recorrido de `/Revision_de_Errores`): estos
  comprobantes de venta con tarjeta traen "NUMERO DE OPERACION", "CODIGO DE
  AUTORIZACION" y "NUM TRANSACCION" en vez de un número de factura/boleta —
  usar el código de autorización como `n_documento`. Distinto de los
  **comprobantes de peaje** (Concesionaria Temuco-Río Bueno, Ruta de la
  Araucanía, Autopista Los Andes, etc.), que no traen ningún número
  reutilizable como documento (solo un código de barras largo sin relación
  clara con la transacción) — esos van como `"N/A"` (mismo pedido
  2026-08-19; aplicado retroactivo a `CVAL-002`, `CVAL-003`, `CVAL-005` vía
  `/Revision_de_Errores`).
- **Pasajes de bus (transporte de pasajeros) están exentos de IVA**
  (confirmado por el usuario 2026-07-17): tanto servicios urbanos como
  rurales e interurbanos — el valor del pasaje no incluye el 19% de IVA. Al
  extraer/verificar `"iva"` de una boleta de pasaje de bus (Tur Bus y
  similares), el valor correcto es 0, no 19% del Neto. Precedente: boleta
  Tur Bus N° 0000162354 (`UMAG-009`).

## Perú (`--pais PE`)

- **Los documentos de Perú están dirigidos a "QUEMPIN SAC"** (pedido del
  usuario 2026-08-21) — entidad legal distinta de "QUEMPIN SpA" (Chile), que
  sigue siendo la razón social por defecto. Al extraer/verificar un
  documento para `datos_extraidos_peru.json`, confirmar que el destinatario
  impreso en la factura/boleta sea "QUEMPIN SAC" — un documento dirigido a
  otra razón social probablemente no corresponde a este centro de costos.
  Ver `PAISES["PE"]["razon_social"]` en `auditor_centro_costos.py`, usado en
  el banner de consola de `run --pais PE`.
- Los documentos de Perú se guardan en
  `Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/Perú/<Proyecto>/`
  (paralelo a `.../Chile/<Proyecto>/` para los documentos chilenos, ambos
  dentro de la misma carpeta compartida) — ver
  `docs/superpowers/specs/2026-08-21-peru-expansion-design.md` (raíz del
  repo) para la arquitectura completa.

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

- **Publicado en GitHub Pages desde 2026-08-05** (reemplaza al Claude
  Artifact que se usaba antes — link viejo:
  `https://claude.ai/code/artifact/1b82085c-c63c-407c-8f03-e4db9f2b551e`,
  ya no se actualiza). URL fija actual:
  `https://cristobal-monzo.github.io/finanzas-quempin/centro-de-costos/`
  — ver [`../../../../Visualizador Web/CLAUDE.md`](../../../../Visualizador%20Web/CLAUDE.md)
  § Hosting (raíz del repo) para los comandos exactos de publicación, la
  arquitectura completa (rama `gh-pages`) y el trade-off de control de
  acceso.
- **Publicar es obligatorio tras cada `run` que registre documentos
  nuevos** (pedido explícito del usuario, 2026-07-23): si el resumen final
  de `run` reporta "Documentos nuevos registrados: N" con N > 0, hay que
  publicar el `build/index.html` regenerado como paso final de la tarea, no
  solo dejarlo regenerado en disco — receta exacta consolidada en
  `../../../../Visualizador Web/CLAUDE.md` § Hosting (raíz del repo), no se
  repite acá. No
  hace falta este paso si `run` no registró documentos nuevos, ni si se
  usó [`/Actualizar_Base_de_Datos`](../Actualizar_Base_de_Datos/SKILL.md)
  a propósito para no publicar todavía.
- Flujo para actualizar: `python driver.py visualizador` (regenera
  `Visualizador Web/build/index.html` desde el Excel actual) → publicar
  como arriba.
- La contraseña de acceso del gate vive como constante en
  `Visualizador Web/template.html` (no se repite acá — ya es visible en el
  HTML publicado, ver nota de "no es seguridad real" en ese `CLAUDE.md`).

## Historial de ejecuciones

Movido a [HISTORIAL.md](HISTORIAL.md) (2026-07-27) — bitácora fechada de
corridas reales (cifras, hallazgos puntuales). Solo hace falta abrirlo si
necesitas investigar cuándo/por qué pasó algo específico; para reglas de
negocio vigentes basta este archivo.

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
