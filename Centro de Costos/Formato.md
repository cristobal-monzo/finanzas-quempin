# Formato.md — patrón genérico de formato para módulos financieros QUEMPIN

**Este documento es genérico**: describe el patrón de formato de Excel que
cualquier módulo de este repositorio (Centro de Costos, Flujo de Caja,
futuros módulos) debería seguir para mantener consistencia entre ellos. No
contiene datos ni decisiones específicas de un módulo en particular — para
eso, cada módulo tiene su propio `Formato <Módulo>.md` (ej.
[Formato Centro de Costos.md](Formato%20Centro%20de%20Costos.md)) con el
estado real y verificado de su `.xlsx`: columnas exactas, anchos, colores
asignados, validaciones, y cualquier discrepancia heredada.

Complementa al `CLAUDE.md` raíz (rol del agente, módulos) y al `CLAUDE.md`
de cada módulo (qué hace ese módulo específicamente).

**Cómo se mantiene**: esto es un documento de *reglas*, no de estado. Si
decides cambiar una convención acá (ej. otro esquema de color, otro formato
de número), hazlo explícitamente y evalúa si los módulos existentes deberían
migrar o quedan documentados como excepción en su `Formato <Módulo>.md`. No
mezcles acá detalles de un módulo puntual — si algo es específico de un
`.xlsx` real, va en el documento de ese módulo.

## 1. Estructura de libro (Master / Detalle / hojas derivadas)

Patrón de tres tipos de hoja, usado por Centro de Costos y pensado para
reutilizarse en módulos futuros:

- **`Master`** — una fila por **registro/documento**, con fórmulas que
  agregan desde `Detalle` (nunca valores fijos, salvo que el usuario los
  reemplace a mano a propósito — ver §7 "regla de oro").
- **`Detalle`** — la hoja de edición real: una fila por **ítem de línea**
  (o el nivel de granularidad que aplique al módulo). Varias filas pueden
  compartir la misma clave de `Master` cuando un registro tiene varias
  líneas.
- **Hojas de solo lectura por categoría** (proyecto, centro de costos, mes,
  lo que aplique) — 100% fórmulas `=Master!<col><fila>`, se regeneran
  completas en cada corrida a partir de la columna de categorización actual
  de `Master`. Ninguna celda ahí es editable; si el usuario reclasifica un
  registro en `Master`, la próxima corrida lo mueve solo a la hoja correcta.

## 2. Encabezados (fila 1)

Estilo estándar para todas las hojas (`Master`, `Detalle`, hojas derivadas):

- Relleno sólido navy (`1F4E79`).
- Fuente Calibri 11 negrita, color blanco (`FFFFFF`).
- Alineación centrada horizontal y vertical, con ajuste de texto
  (`wrap_text`).
- Borde fino en los 4 lados.
- Alto de fila 1 suficiente para acomodar el texto envuelto (en Centro de
  Costos, 28.05 — no es un valor mágico, solo lo que quedó bien para esos
  encabezados; ajustar según el contenido real de cada módulo).

## 3. Convención de colores y fuente

Misma convención en todos los módulos (documentada también en la leyenda al
pie de cada hoja, para que quien abra el Excel la vea sin necesitar este
documento):

- **Cursiva** = celda editable a mano.
- **Rojo** (`C00000`) = valor que requiere revisión.
- **Azul marino oscuro** (`1F3864`) = valor corregido a mano por el usuario
  (el script lo respeta, no lo sobreescribe).
- **Azul marino** (`1F4E79`) = color de encabezado / texto informativo de
  la leyenda — no es un marcador de estado de celda de datos.
- **Fondo de color por fila** = categoría/proyecto, de una paleta fija de 12
  pasteles reutilizada de forma determinista: se reutiliza el color que ya
  tenga esa categoría en `Master`, y solo se toma uno libre de la lista para
  categorías nuevas. Paleta sugerida (la que usa Centro de Costos):
  `FCE4D6, DDEBF7, E2EFDA, FFF2CC, EAD1DC, D9E1F2, FBE5D6, D6DCE4, E4DFEC,
  FDE9D9, DAEEF3, F2DCDB`.

## 4. Formato de números y fechas

- Montos: formato moneda con el signo de moneda automático de Excel
  (símbolo de la configuración regional, ej. `"$"#,##0` para pesos), con
  separador de miles y sin decimales.
- Fechas: `DD/MM/YYYY` al escribir — nota general: Excel puede colapsar esto
  al formato incorporado "fecha corta" (`numFmtId` 14) y mostrarlo según la
  configuración regional de quien abre el archivo (MM/DD/YY vs DD/MM/YYYY).
  No es un bug de escritura si una fecha se ve en el orden "raro" para
  alguien — es interpretación regional de Excel, no del dato guardado.

## 5. Bordes

- Encabezado y filas de datos: borde fino en los 4 lados.
- Filas de pie (totales) y filas de leyenda: sin borde.

## 6. Backup e idempotencia

- **Backup con timestamp antes de escribir, siempre** — ninguna corrida
  debería escribir sin respaldo previo del archivo anterior.
- **Idempotente**: correr el pipeline sin registros nuevos no debería
  modificar ninguna fila de datos ya escrita — solo regenerar lo derivado
  (pies de tabla, hojas de categoría), que da el mismo resultado si nada
  cambió en `Master`.

## 7. Regla de oro: nunca reescribir una fila de datos ya creada

Las filas de datos ya escritas (ítems en `Detalle`, registros en `Master`)
nunca se vuelven a tocar una vez creadas — son historial editable a mano
por el usuario. Las fórmulas de columnas siempre-derivadas (ej. totales que
suman desde `Detalle`) se reescriben en cada corrida *solo si siguen siendo
fórmula*; si el usuario ya reemplazó una por un valor fijo a mano, se
respeta y no se toca. Los pies de tabla y las hojas de categoría sí se
regeneran completos en cada corrida porque son 100% derivados, no datos
originales.

## 8. Formato manual del usuario se respeta entre corridas

Cualquier columna/hoja que el usuario ajuste a mano en Excel debe sobrevivir
a la siguiente corrida del pipeline — esto incluye ancho de columnas, tipo
de casilla (formato de número), columnas ocultas, autofiltro, freeze panes y
validaciones de datos. Dos reglas de implementación para lograrlo con
`openpyxl`:

1. **Ancho de columnas**: solo fijar el ancho de una columna la primera vez
   que existe (si `column_dimensions[letra].width` ya tiene un valor —
   puesto por el script antes, o a mano por el usuario — no se vuelve a
   tocar).
2. **Hojas derivadas (categoría/proyecto)**: si la hoja ya existe, no
   borrarla y recrearla desde cero — reutilizar el mismo objeto de hoja y
   solo borrar/reescribir las filas de datos+pie+leyenda. Borrar y recrear
   la hoja completa destruye cualquier formato a nivel de columna/hoja
   (columnas ocultas, anchos, autofiltro, freeze panes, validaciones) que el
   usuario haya dejado ahí.

Una columna oculta sigue siendo perfectamente legible/escribible por
`openpyxl` — estar oculta es un atributo de visualización, no afecta el
acceso a la celda por fila/columna. El pipeline debe seguir leyendo y
actualizando esas columnas con normalidad.

## 9. Documento específico por módulo

Este documento no debe crecer con datos de un módulo puntual (nombres de
proyecto real, colores ya asignados, columnas exactas con sus anchos
actuales, discrepancias heredadas de un pipeline anterior, etc.). Esa
información va en `Formato <Módulo>.md`, dentro de la carpeta del módulo,
que sí se mantiene leyendo el `.xlsx` real con `openpyxl` (no solo el
código) y se actualiza con una entrada fechada en su propio historial cada
vez que el formato real cambia.

## Historial de cambios a este patrón

### 2026-07-16 — montos con signo de moneda (antes: sin signo)
A pedido del usuario ("los montos monetarios van en formato moneda con el
signo de moneda automático de excel, con separador de miles y sin
decimales"), §4 cambió de `#,##0` (sin signo) a formato moneda con el signo
automático de Excel (ej. `"$"#,##0`). Detalle de la migración en Centro de
Costos (constante `MONEY_FORMAT`) en el historial de
[Formato Centro de Costos.md](Formato%20Centro%20de%20Costos.md).

### 2026-07-16 — separación en documento genérico + específico por módulo
A pedido del usuario ("quiero que el documento de formato sea genérico para
que [sirva para] cualquier proyecto futuro. Las características específicas
de cada proyecto pueden asignarse en otro .md"), este archivo se reescribió
para contener solo el patrón reutilizable (§1-8). Todo el contenido
específico de Centro de Costos (hojas reales, columnas con sus anchos
actuales, colores asignados, prefijos de N° Ref., discrepancias heredadas
del pipeline perdido, validaciones de datos, formato condicional heredado,
hoja oculta `_Claude`, migración de la columna Proveedor/Razón Social, etc.)
se movió a [Formato Centro de Costos.md](Formato%20Centro%20de%20Costos.md).

### 2026-07-16 — el script respeta formato manual (anchos, columnas ocultas)
Origen de la regla en §8: a pedido del usuario ("quiero que el formato que
modifique manualmente lo mantengas..."), se corrigió `auditor_centro_costos.py`
en Centro de Costos (`ajustar_anchos` y `regenerar_hoja_proyecto`) para dejar
de pisar formato manual en cada corrida. Detalle específico de esa corrección
en el historial de [Formato Centro de Costos.md](Formato%20Centro%20de%20Costos.md).
