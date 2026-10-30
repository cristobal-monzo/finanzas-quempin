---
name: Registro_Centro_de_Costos
description: Registra facturas y boletas en Centro de Costos.xlsx (status, run, confirmar, visualizador, separar, separar-registrado, eliminar) y publica su tablero salvo «sin publicar». Usar SOLO si el usuario escribe "/Registro_Centro_de_Costos" (antes /Actualizar_CC y /Actualizar_Base_de_Datos). Ante «actualiza el centro de costos» sin la barra, pregunta primero, porque puede querer esta skill o /Actualizar_Finanzas.
---

# Registro: Centro de Costos

Las rutas son relativas a `Centro de Costos/`. En los comandos, `driver.py` es
`.claude/skills/Registro_Centro_de_Costos/driver.py`, corrido con `py -3.14`. **Son datos reales**:
`status` solo lee; `run` escribe, idempotente y con respaldo previo.

- Reglas, esquema del JSON y proceso de errores: `../../CLAUDE.md`.
- Reglas de negocio y criterios de clasificación: [MEMORY.md](MEMORY.md).
- Bitácoras, para buscar con Grep y no leer enteras: [HISTORIAL.md](HISTORIAL.md) (corridas) y
  [ERRORES.md](ERRORES.md) (errores y correcciones).

**Perú**: todos los comandos aceptan `--pais PE` (árbol aparte en `Peru/Centro de Costos/`,
`datos_extraidos_peru.json`, `Facturas y Boletas/Perú/`, IGV 18 %, soles). Sin el flag es `CL`.

## Paso 1: `driver.py status`, siempre antes de `run`

Reporta qué se registraría, los pendientes sin datos en el JSON y las OC de Sistema QUEMPIN: las
que `run` traería (sin pasar por el Paso 2: sus datos salen de Sistema QUEMPIN) y las que ya están
en el libro con su factura encontrada o dudosa.

## Paso 2: completar los pendientes sin datos

Si hay «Pendientes SIN datos (o sin items) en el JSON», arma tú cada entrada, sin pedirle el JSON
al usuario. Agrupa por proyecto las preguntas que se repiten.

0. **¿El archivo trae más de un documento?** Solo si tiene N° de Documento genuinamente distintos.
   Nunca separes un multipágina que es una sola factura (factura + guía del mismo N°, página de
   continuación), y nunca juntes los números en una entrada (`DOCUMENTOS_MEZCLADOS`). Si trae N:
   ```
   driver.py separar --proyecto "<Proyecto>" --archivo "<archivo>" --cantidad N
   ```
   Genera `<archivo>_1.<ext>`… (copias completas, sin recortar), respalda y borra el original. Trata
   cada copia como un pendiente aparte, con su propio N° de Documento, proveedor e ítems.
1. **Abre la foto o PDF** (`Sitio de comunicación - Centro de Costos 1/Facturas y
   Boletas/<País>/<Proyecto>/<archivo>`) y extrae lo legible, según el esquema de `../../CLAUDE.md`
   y [MEMORY.md](MEMORY.md) § Reglas de negocio. Un documento girado se lee igual y se anota `rotacion`.
   **Antes de fijar `proveedor`**, busca uno conocido con ese RUT o nombre parecido
   (`TAGS_PROVEEDOR_CURADOS`, columna oculta «Proveedor (Razón Social)») y reusa esa razón social. Si el
   RUT es legible y no está en el libro, consulta los proveedores de Sistema QUEMPIN (solo lee, desde
   la raíz de Finanzas): `py -3.14 "Sistema Intercambio/contrapartes.py" <RUT>`.
2. **Pregunta solo lo que el documento no resuelve**: `tipo_proyecto` si el proyecto es nuevo, `estado`
   (Pagado/Pendiente), lo ilegible o ambiguo, y **si un proveedor se parece a uno registrado sin calzar
   exacto: nunca asumas que es el mismo**. Aplica [MEMORY.md](MEMORY.md) § Criterios de clasificación
   (asumir Factura salvo sospecha clara de Boleta; confirmar si un equipo de más de $20.000 es de ese
   proyecto o de Gastos Generales).
3. **Agrega la entrada** a `Sistema/datos_extraidos.json`. **Si es la factura de una OC** (cita su N°, o
   `status` lista una OC abierta del mismo proyecto y proveedor), agrega `"oc": "<folio>"`; si `status`
   dice que varias podrían serlo, pregunta cuál.
4. Lo que no se pueda completar queda fuera del JSON y va en la tabla del Paso 4: no bloquea el resto.

## Paso 3: `driver.py run`

Sin documentos registrables no toca ninguna fila de datos: solo crea el respaldo y regenera pies de tabla
y hojas de proyecto. Regenera además `Visualizador Web/build/index.html`; si eso falla, deja un `[WARN]`,
el Excel queda guardado y se regenera con `driver.py visualizador`.

## Paso 4: tabla de resumen, siempre al terminar

| Posible error | Ubicación en Master | Descripción | Solución posible |
|---|---|---|---|

- **Posible error**: Legibilidad, Inconsistencia IVA, Posible duplicado, Sin datos en JSON o Imprecisión de
  dato (lo que notó el agente).
- **Ubicación**: el `N° Ref.`; si no se registró, `Facturas y Boletas/<País>/<Proyecto>/<archivo>`.
- **Solución**: acción concreta y corta.

Dos fuentes, ambas obligatorias:

1. La consola: el bloque **«HALLAZGOS ABIERTOS»** (por severidad e impacto, con el `<ID>` con que se cierra
   cada uno) y las secciones 5–7 del informe (renombrado, cambios manuales, notas del JSON).
2. **Lo que notes tú** al revisar los datos nuevos, aunque el script no lo marque: `notas` con ambigüedad,
   proveedor o categoría inconsistente con corridas anteriores, monto estimado, N° raro, fecha dudosa.

Si no hay nada, dilo en una línea, sin tabla vacía.

## Paso 5: «CAMBIOS MANUALES PENDIENTES DE CONFIRMAR»

Alguien corrigió a mano una celda roja. Muestra la lista (`driver.py confirmar`, solo lectura) y **pide
confirmación explícita**. Recién entonces: `driver.py confirmar --todos` (o `confirmar <N_REF> ...`), que
recolorea a azul marino (`1F3864`), propaga a `Detalle` si el campo se repite y lo marca «Aplicado» en
`Sistema/correcciones_manuales.json` y [ERRORES.md](ERRORES.md). El script nunca lo aplica solo.

## Publicar el tablero

Si `run` registró documentos (N > 0) o se pidió refrescar, **publica sin esperar a que te lo pidan**: desde
la raíz del repo, `py -3.14 "Visualizador Web/publicar.py" cc` y commit + push en `.worktrees/gh-pages`
([procedimiento común](../../../../docs/actualizar-un-modulo.md); receta en
`Visualizador Web/CLAUDE.md` § Hosting). Si el usuario dijo «sin publicar» o «solo el Excel», no publiques
y avisa que el tablero sigue desactualizado. `driver.py visualizador` regenera el HTML sin registrar; ninguno
de los dos toca el Excel.

## Otros comandos y cuidados

- **El emparejamiento es por (proyecto, nombre exacto de archivo)**. Si no calzan con la ubicación real, el
  archivo sigue «pendiente sin datos» sin error explícito.
- **`driver.py separar-registrado --plan <pedido.json> [--aplicar]`**: para lo **ya registrado** que junta
  varios documentos en un N° Ref. (`separar` es solo para pendientes). Pedido: `{"<N_REF>": [documento, ...]}`,
  cada uno con `n_documento`, `fecha`, `tipo_documento`, `proveedor`, `categoria`, `iva` (el impreso en ese
  documento) e `items` (índices 0-based de sus filas de `Detalle`, o `{"fila": i, "cantidad": q}`). El primero
  conserva el N° Ref. Rechaza el pedido si alguna fila queda sin asignar o las cantidades no suman. Sin
  `--aplicar` solo muestra; después corre `run`. Formato: `planificar_separacion_registrado()`.
- **`driver.py eliminar`**: saca del libro un documento registrado por error (normalmente dos veces) y archiva
  su archivo. No renumera. Sin `--aplicar` solo muestra.
- Una reasignación manual de proyecto en `Master` se refleja sola en la hoja de proyecto en el próximo `run`.
- Dos filas que apuntan al mismo archivo físico se revisan a mano contra `Master` (pasó una vez, ver
  [ERRORES.md](ERRORES.md) 2026-07-17).

| Síntoma | Causa y solución |
|---|---|
| `[ERROR] El archivo esta abierto en Excel...` | Cierra `Centro de Costos.xlsx` y vuelve a correr |
| Un archivo nuevo no aparece tras `run` | Corre `status`: casi siempre falta su entrada con `items` en el JSON |
| `[WARN] Proyecto '...' no tiene prefijo de N Ref definido` | Agrégalo a `PREFIJOS_PROYECTO` (si no, usa uno derivado) |
| `No existe la carpeta raiz` / `No existe el JSON de datos` | Las rutas salen de `Path(__file__)`: corre contra `Centro de Costos/` |
