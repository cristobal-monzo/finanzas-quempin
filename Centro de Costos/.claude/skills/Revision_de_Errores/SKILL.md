---
name: Revision_de_Errores
description: Recorrido guiado, uno por uno, de (a) las celdas de "Centro de Costos.xlsx" marcadas en rojo (requieren revisión) y (b) las filas de Detalle que agrupan en 1 solo ítem una parte de una compra que no se pudo identificar línea por línea (ej. "Materiales varios") -- muestra la foto del documento asociado, pide al usuario el valor correcto o el desglose correcto, lo aplica en el Excel con fuente azul marino oscuro, actualiza el registro de correcciones, y refleja el resultado en ambas copias del libro. Usar cuando el usuario pida revisar errores, corregir datos ilegibles, resolver celdas rojas, desglosar ítems agrupados/no identificados, o repasar el registro de correcciones manuales del Centro de Costos.
---

# Revisión de errores: Centro de Costos

Complementa a [Registro_Centro_de_Costos](../Registro_Centro_de_Costos/SKILL.md):
esa skill detecta correcciones que el usuario **ya hizo a mano** directo en
el `.xlsx` (comparando contra el backup anterior) y requiere un paso de
confirmación aparte (`driver.py confirmar`). Esta skill invierte el orden:
el **agente** recorre las celdas rojas (y los ítems agrupados, ver más abajo),
muestra el documento, y le pregunta al usuario el valor correcto **en la
conversación** -- sin que el usuario tenga que abrir Excel y editar la celda
él mismo. El resultado final es el mismo (celda/fila azul marino oscuro,
propagada a Detalle/Master, registrada como "Aplicado"), solo cambia cómo se
obtiene el valor.

Dos tipos de hallazgo, dos comandos de lectura y dos de escritura -- ver
"Qué cuenta como..." de cada uno más abajo:

| Tipo | Listar (solo lectura) | Aplicar |
|---|---|---|
| Celda roja de Master | `errores` | `corregir <N_REF> <CAMPO> <VALOR>` |
| Ítem agrupado de Detalle | `agrupados` | `desglosar <N_REF> '<ITEMS_JSON>'` |

**Siempre, al terminar el recorrido (haya o no correcciones aplicadas en la
sesión), correr `python driver.py reflejar`** -- copia
`Excel/Centro de Costos.xlsx` encima de `Sitio de comunicación - Centro de
Costos 1/Centro de Costos.xlsx`. `corregir` y `desglosar` solo tocan el
Excel local (no pasan por `main()`/`run`, que es el único lugar que hacía
este reflejo hasta ahora), así que sin este paso la copia compartida que ven
los colegas queda desactualizada. Es el mismo paso que hace `run` en su
PASO 12b (`reflejar_a_sitio_comunicacion()` en `auditor_centro_costos.py`,
factorizado para reutilizarse acá), idempotente y seguro de repetir.

Todas las rutas son relativas a la raíz del módulo (`Centro de Costos/`), no
a esta carpeta de skill. El driver vive en
`.claude/skills/Revision_de_Errores/driver.py`.

**Datos financieros reales** -- igual que el resto del módulo, no hay nada
que fotografiar de la herramienta en sí (es un script), pero sí se muestran
fotos reales de facturas/boletas de la empresa durante el recorrido.

## Qué cuenta como "error" en esta skill

Únicamente las celdas de `Master` que el script pinta de rojo hoy
(`acc.COLUMNAS_REVISABLES`, ver `auditor_centro_costos.py`):

- **N° Documento** (columna E) ilegible o no leído -- queda como
  `"S/N (<archivo o voucher>)"`.
- **IVA 19% (CLP)** (columna L) que no cuadra con el 19% del Neto (tolerancia
  ±1 CLP) para Facturas/Guías de Despacho.

**No** entran acá los hallazgos de la tabla "Posible error" que se arma tras
cada `run` (legibilidad general, posibles duplicados, imprecisiones de dato
que el agente nota pero el script no marca) -- esos no son una sola celda con
un valor a reemplazar, se resuelven caso a caso siguiendo el Paso 3 de
`Registro_Centro_de_Costos/SKILL.md`, no con este recorrido.

## Qué cuenta como "ítem agrupado" en esta skill

Filas de `Detalle` cuyo **Nombre Ítem** contiene la palabra "varios" (ej.
"Materiales varios", "Insumos varios" -- `acc.PATRON_ITEM_AGRUPADO`,
insensible a mayúsculas). Es la convención que ya usa el módulo desde el
precedente `CCON-004` (ver `MEMORY.md`/`ERRORES.md` de
`Registro_Centro_de_Costos`): cuando una parte de una factura/boleta es
físicamente ilegible (timbre, doblez, foto cortada), las líneas que sí se
leen se registran cada una por separado y **solo** las ilegibles se agrupan
en 1 ítem aparte por el saldo entre el Neto impreso y la suma de las líneas
legibles -- nunca se agrupa el documento completo. Ese ítem-saldo es lo que
esta skill puede desglosar, si en algún momento se consigue leer el detalle
real (otra foto, el documento físico, etc.).

No hay ninguna celda pintada de un color especial para este caso (a
diferencia de las celdas rojas de Master) -- se detecta por el nombre del
ítem, no por formato. Si el usuario nombra un ítem agrupado de otra forma
que no incluya "varios", esta skill no lo va a encontrar solo con
`agrupados`; avisar al usuario y ofrecer desglosarlo igual si él lo señala
en la conversación.

## Procedimiento

**Paso 1 -- listar los errores (solo lectura):**

```
python ".claude/skills/Revision_de_Errores/driver.py" errores
```

Imprime, por cada celda roja: `N° Ref.`, proyecto, campo, valor actual, y la
ruta a la foto del documento original (resuelta con el mismo mecanismo que
usa el renombrado automático -- prueba "Archivo origen" y si no existe en
disco cae a `reconciliacion_archivos.json`). Si dice "No hay errores
pendientes de revisión", termina acá y avísale al usuario.

**Paso 2 -- recorrer las celdas UNA A LA VEZ** (no todas de golpe: el usuario
necesita ver cada documento antes de decidir el valor correcto):

Para cada celda de la lista del Paso 1:

1. **Mostrar el error**: `N° Ref.`, proyecto, campo, y por qué está en rojo
   (N° Documento ilegible / IVA no cuadra con el 19% del Neto -- calcula el
   valor esperado si es IVA, ayuda al usuario a decidir).
2. **Mostrar la foto**: usar la herramienta de lectura de archivos sobre la
   ruta que imprimió `errores` para que la imagen se vea en la conversación.
   - Si la ruta es `.heic` (no debería pasar para documentos ya registrados,
     el renombrado automático los convierte a `.jpg`, pero puede pasar si
     el archivo aún no pasó por un `run`), avisar que no se puede previsualizar
     inline y pedirle al usuario que lo abra manualmente para confirmar el
     valor.
   - Si `errores` marcó `[WARN] No se encontró la foto en disco`, decirlo tal
     cual y pedir el valor correcto igual (sin foto de respaldo).
3. **Preguntar el valor correcto** directamente en la conversación (texto
   libre, no es una decisión de diseño así que no uses AskUserQuestion).
   Si el usuario dice que no sabe o quiere dejarlo pendiente, saltar esa
   celda y seguir con la siguiente -- no hay que resolver todas en la misma
   sesión.
4. **Aplicar la corrección**:
   ```
   python ".claude/skills/Revision_de_Errores/driver.py" corregir <N_REF> <CAMPO> "<VALOR>"
   ```
   `<CAMPO>` acepta el número de columna (5 o 12) o un fragmento del nombre
   ("N° Documento", "documento", "IVA", ...). Ejemplos:
   ```
   python driver.py corregir UMAG-014 "N° Documento" 12345
   python driver.py corregir CFLI-002 IVA 190
   ```
   Esto hace, en un solo paso: backup de `Centro de Costos.xlsx` →
   escribe el valor nuevo en `Master` → recolorea esa celda a azul marino
   oscuro (`1F3864`) → si el campo es N° Documento, propaga el mismo valor a
   las filas de `Detalle` con ese `N° Ref.` (también en azul marino) → marca
   la corrección como "Aplicado" en `Sistema/correcciones_manuales.json` y en
   la tabla de [ERRORES.md](../Registro_Centro_de_Costos/ERRORES.md).
5. **Confirmar al usuario** que se aplicó (el driver ya imprime
   `[OK] <N_REF> / <campo>: '<anterior>' -> '<nuevo>' (azul marino...)`) y
   seguir con la siguiente celda de la lista.

**Estos cambios se ven reflejados en todo el libro sin pasos extra**: la
hoja de proyecto correspondiente es 100% fórmulas hacia `Master` (se
recalcula sola en el próximo `run`, o ya se ve actualizada si solo abres el
archivo porque lee `Master` en vivo), y `Detalle` recibe la propagación
automática cuando el campo se repite ahí.

**Paso 3 -- si `Centro de Costos.xlsx` está abierto en Excel**, `corregir`
falla con un `[ERROR] El archivo esta abierto en Excel` controlado (no
corrompe el archivo) -- pedirle al usuario que lo cierre y reintentar esa
celda.

**Paso 4 -- listar los ítems agrupados (solo lectura):**

```
python ".claude/skills/Revision_de_Errores/driver.py" agrupados
```

Imprime, por cada fila agrupada de `Detalle`: `N° Ref.`, proyecto, nombre del
ítem agrupado, monto, la descripción completa (normalmente explica qué
líneas quedaron dentro y por qué no se pudieron leer), y la foto del
documento. Si dice "No hay ítems agrupados pendientes de desglosar", saltar
al Paso 6.

**Paso 5 -- recorrer los ítems agrupados UNA A LA VEZ** (mismo criterio que
el Paso 2: el usuario necesita ver el documento antes de dar el desglose):

Para cada ítem agrupado de la lista del Paso 4:

1. **Mostrar el hallazgo**: `N° Ref.`, proyecto, nombre y descripción del
   ítem agrupado, monto total que representa.
2. **Mostrar la foto** (mismo mecanismo que el Paso 2 -- si es `.heic` o no
   se encontró en disco, avisar igual que ahí).
3. **Preguntar el desglose correcto** directamente en la conversación: por
   cada línea real que el usuario identifique, pedir nombre del ítem,
   descripción, categoría, cantidad y precio unitario sin IVA. Si el usuario
   no puede leer el documento tampoco (mismo motivo por el que quedó
   agrupado -- timbre, doblez, foto cortada), dejarlo pendiente y seguir con
   el siguiente; no hay que resolver todos en la misma sesión.
4. **Aplicar el desglose**:
   ```
   python ".claude/skills/Revision_de_Errores/driver.py" desglosar <N_REF> '<ITEMS_JSON>'
   ```
   `<ITEMS_JSON>` es una lista JSON de objetos, mismo esquema que un ítem de
   `datos_extraidos.json`: `nombre_item`, `descripcion`, `categoria_item`,
   `cantidad`, `p_unitario_sin_iva`. Ejemplo:
   ```
   python driver.py desglosar CCON-004 "[{\"nombre_item\": \"Cañería cobre\", \"descripcion\": \"1 1/4 y 1 1/2 pulg\", \"categoria_item\": \"Materiales\", \"cantidad\": 2, \"p_unitario_sin_iva\": 30000}, {\"nombre_item\": \"Soldadura plata\", \"descripcion\": \"Soldadura al 6% + fundente\", \"categoria_item\": \"Materiales\", \"cantidad\": 1, \"p_unitario_sin_iva\": 55206}]"
   ```
   Esto hace, en un solo paso: backup → reemplaza la fila agrupada de
   `Detalle` por una fila nueva por cada ítem (azul marino, heredando el
   relleno de color del proyecto) → recalcula "Total sin IVA"/"Total con
   IVA" de cada fila nueva con la tasa real del documento → reconstruye
   "Resumen Ítems" en `Master` → regenera el pie de `Detalle` → marca el
   cambio como "Aplicado" en `Sistema/correcciones_manuales.json` y en la
   tabla de [ERRORES.md](../Registro_Centro_de_Costos/ERRORES.md).
5. **Confirmar al usuario** que se aplicó (el driver imprime
   `[OK] <N_REF> / Ítems agrupados: '<anterior>' -> N ítem(s) (...)`) y
   seguir con el siguiente ítem agrupado de la lista.

**Paso 6 -- reflejar en Sitio de comunicación (SIEMPRE, al terminar):**

```
python ".claude/skills/Revision_de_Errores/driver.py" reflejar
```

Correr esto al final de la sesión sin excepción, haya o no correcciones/
desgloses aplicados -- copia el Excel local encima de la copia en `Sitio de
comunicación - Centro de Costos 1/`. Si el destino está bloqueado (alguien
lo tiene abierto), el driver imprime un `[WARN]` pero no falla; avisar al
usuario y sugerirle reintentar `reflejar` más tarde.

**Paso 7 -- al terminar todo el recorrido** (se acabaron las celdas rojas y
los ítems agrupados, o el usuario quiere parar), resumir cuántas celdas se
corrigieron, cuántos ítems se desglosaron, y cuántos quedaron pendientes
(los que el usuario dijo que no sabía) -- esos siguen igual, aparecerán de
nuevo la próxima vez que se corra `errores`/`agrupados`.

## Gotchas

- **`corregir` solo toca la celda si está en rojo** -- si el `N_REF`/campo ya
  no está en rojo (alguien ya lo corrigió, o el N° Ref no existe), no hace
  nada y no rompe nada; revisar el mensaje de consola.
- **`desglosar` solo actúa si encuentra EXACTAMENTE 1 fila agrupada** para
  ese `N_REF` -- si no encuentra ninguna (ya se desglosó, o el N° Ref no
  existe) o encuentra más de una (un documento con 2+ ítems agrupados, no
  soportado hoy), no hace nada; revisar el mensaje de consola y resolver a
  mano si hace falta.
- **No hay "deshacer" automático** más allá del backup que crean `corregir`/
  `desglosar` antes de escribir (`Excel/Respaldos/`) -- si el usuario se
  equivoca de valor, corregir de nuevo sobre la misma celda YA NO funciona
  porque quedó en azul marino (ya no está roja), y `desglosar` de nuevo
  tampoco porque el nombre del ítem ya no tiene "varios"; restaurar desde el
  backup más reciente si hace falta deshacer.
- **El valor de IVA se pasa como número** -- el driver intenta convertirlo a
  `int`/`float` automáticamente cuando el campo es IVA; si el usuario da un
  valor no numérico para esa columna, se guarda como string tal cual (Excel
  lo mostrará como texto, revisar a mano si pasa).
- **`reflejar` no se ejecuta solo** -- a diferencia de `run` (que lo hace al
  final de cada corrida, PASO 12b), `corregir`/`desglosar` NUNCA tocan la
  copia de Sitio de comunicación por sí mismos; es un paso aparte (Paso 6)
  que hay que correr siempre al terminar.
- Implementación: `listar_celdas_rojas`, `corregir_valor_manual`,
  `listar_items_agrupados`, `desglosar_item_agrupado` y
  `reflejar_a_sitio_comunicacion` en `Sistema/auditor_centro_costos.py`;
  tests en `Sistema/tests/test_revision_errores.py`.
