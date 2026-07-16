# Diseño: renombrado y conversión HEIC→JPG de fotos de documentos

**Fecha:** 2026-07-16
**Módulo:** Centro de Costos
**Estado:** Aprobado por el usuario, pendiente de plan de implementación

## Contexto

El pipeline anterior (perdido, corría en `Plantillas/`) renombraba fotos según
el `N° Ref.` asignado y convertía `.HEIC` → `.jpg`. Ninguna de las dos
capacidades se reconstruyó en `auditor_centro_costos.py` — está documentado
como pendiente conocido en
[MEMORY.md](../../.claude/skills/Registro_Centro_de_Costos/MEMORY.md#pendientes-conocidos-requieren-decisión-del-usuario-no-son-bugs).
Este spec define cómo reconstruirla.

## Objetivo

Que cada archivo en `Documentos Centro de Costos/<Proyecto>/` que corresponda
a un documento ya registrado en `Master` tenga como nombre físico
`<N° Ref>_<TagProveedor>_<Fecha ISO>.<ext>`, y que los `.HEIC` queden
convertidos a `.jpg`. Esto aplica tanto a documentos nuevos que se registren
de ahora en adelante como, retroactivamente, a los ya existentes en `Master`
(incluidos los 24 del bootstrap).

## Mecanismo: un paso idempotente, no una migración separada

Se agrega un nuevo paso a `main()` en `auditor_centro_costos.py`, después de
escribir los documentos nuevos en `Master` (paso 5) y antes del informe de
auditoría final. Este paso recorre **todas** las filas de `Master` — nuevas
y antiguas por igual — y por cada una:

1. Determina el nombre del archivo actual en disco:
   - Si `Master.Archivo origen` está poblada → ese es el nombre actual.
   - Si está vacía (caso de los 24 documentos del bootstrap) → se busca el
     `N° Ref` de esa fila en `reconciliacion_archivos.json` (lookup inverso:
     archivo original → N° Ref) para obtener el nombre original.
2. Calcula el nombre esperado: `<N° Ref>_<TagProveedor>_<Fecha ISO>.<ext>`.
3. Si el nombre actual ya coincide con el esperado, no hace nada (idempotente).
4. Si no coincide:
   - Para `.heic`/`.HEIC`: convierte a `.jpg` (ver detalle abajo) y borra el
     original tras una conversión exitosa.
   - Para `.png`/`.jpg`/`.jpeg`/`.pdf`: renombra/mueve el archivo sin
     recodificar (se preservan los bytes originales).
5. Actualiza (o llena, si estaba vacía) `Master.Archivo origen` con el nombre
   nuevo, y `Master.Fecha modificación` con la fecha/hora de esta corrida.

**Por qué un solo mecanismo y no un script de migración aparte:** con este
enfoque, "retroactivo" y "de ahora en adelante" son el mismo código — no hay
dos rutas que mantener sincronizadas, y correr el script sin cambios
pendientes no vuelve a tocar nada (mismo principio de idempotencia que ya
usa el resto del pipeline para pies de tabla y hojas de proyecto).

**Excepción deliberada a la regla de oro:** actualizar `Master.Archivo
origen` en filas ya escritas es una excepción intencional a "las filas de
datos ya escritas no se vuelven a tocar" — mismo tipo de excepción que la
corrección pendiente de nombre/descripción de ítems ya documentada en
`MEMORY.md`. Se debe registrar en
[ERRORES.md](../../.claude/skills/Registro_Centro_de_Costos/ERRORES.md)
como bitácora de esta excepción, siguiendo el patrón existente.

## Patrón de nombre

`<N° Ref>_<TagProveedor>_<Fecha ISO>.<ext>` — ej. `UMAG-001_Shell_2026-07-15.jpg`

- **`N° Ref`**: tal cual está en `Master` (ej. `UMAG-001`).
- **`TagProveedor`**: el tag corto que ya usa `Master.Proveedor` (no la razón
  social completa, que sigue viviendo solo en la columna oculta `Proveedor
  (Razón Social)`).
- **`Fecha ISO`**: la fecha del documento (`Master.Fecha`, almacenada como
  `dd/mm/yyyy`) convertida a `yyyy-mm-dd`, para que los nombres ordenen
  cronológicamente en el explorador de archivos.
- **Sanitización**: espacios y caracteres inválidos en nombres de archivo
  Windows (`\ / : * ? " < > |`) se reemplazan por `_`.
- **Colisiones**: no son posibles — `N° Ref` ya es único por proyecto y
  secuencia, así que ninguna combinación de nombre se repite.

## Conversión HEIC→JPG

- Librerías: `pillow_heif` (decodificar HEIC) + `Pillow` (guardar JPG) — ya
  instaladas en el entorno, no se agregan dependencias nuevas.
- Se aplica `ImageOps.exif_transpose()` antes de guardar, para respetar la
  orientación EXIF que traen las fotos de celular (sin esto, algunas
  quedarían rotadas).
- Calidad JPEG: 90. Sin redimensionar — se mantiene la resolución completa
  porque son documentos tributarios que pueden necesitar zoom para leer
  montos/RUT.
- El `.heic`/`.HEIC` original se borra únicamente tras una conversión
  exitosa. Si la conversión falla (archivo corrupto, etc.), el original
  queda intacto sin renombrar, con una advertencia en el informe de
  auditoría.

## Integración con `status` / `run`

- **`status`** (solo lectura): agrega a su vista previa qué archivos se
  renombrarían/convertirían y a qué nombre nuevo, sin tocar nada — mismo
  patrón que ya usa para previsualizar documentos nuevos a registrar.
- **`run`**: ejecuta los renombrados/conversiones como parte del flujo
  normal.

## Manejo de errores

No interrumpen la corrida; se agregan al informe de auditoría por consola
junto a las demás alertas existentes (legibilidad, inconsistencias
aritméticas, posibles duplicados):

- **Archivo no encontrado en disco** con el nombre esperado (según `Archivo
  origen` o `reconciliacion_archivos.json`) → advertencia, se omite esa fila,
  no se modifica `Master`.
- **Falla la conversión HEIC** → advertencia, el archivo original queda sin
  tocar (ni renombrado ni borrado).

## Fuera de alcance

- Detección/bloqueo automático de duplicados (`detectar_duplicados.py` del
  pipeline perdido) — el script ya avisa de posibles duplicados por N°
  Documento repetido; eso no cambia con este spec.
- Respaldo adicional de `Documentos Centro de Costos/` antes de la corrida
  retroactiva — decisión explícita del usuario (2026-07-16): se confía en
  que `N° Ref` + `Fecha` + `Proveedor` ya quedan trazados en `Master`, sin
  duplicar espacio con un respaldo extra de fotos. **Riesgo aceptado
  explícitamente**: la pasada retroactiva borra `.HEIC` originales de los 24
  documentos del bootstrap (y de cualquier otro ya registrado) sin una copia
  de respaldo dedicada de esos archivos — solo queda el respaldo con
  timestamp del `.xlsx` (que no contiene las fotos) como red de seguridad.
- Recoloreo rojo→azul marino (pendiente aparte, en pausa).
- Migración retroactiva de nombre/descripción de ítems (pendiente aparte).

## Testing

- Unitarias sobre las funciones nuevas (cálculo de nombre esperado,
  sanitización, detección de "ya coincide"), sin depender del `.xlsx` real.
- Prueba de conversión HEIC→JPG con un archivo de prueba pequeño (verificar
  que el JPG resultante se puede abrir y que la orientación EXIF se
  respeta).
- Prueba de idempotencia: correr el paso dos veces seguidas sobre el mismo
  estado no debe volver a renombrar/tocar nada en la segunda corrida.
- **No se ejecuta contra `Centro de Costos.xlsx` ni
  `Documentos Centro de Costos/` reales durante el desarrollo** — se usan
  fixtures/copias de prueba, dado que son datos financieros reales y la
  operación es destructiva (borra archivos). La validación final contra los
  datos reales la hace el usuario corriendo `/Registro_Centro_de_Costos
  status` primero para revisar la vista previa.
