# Corrida programada de /Actualizar_Finanzas (nadie responde preguntas)

Esta sesión la abre `tarea_programada.cmd` de lunes a viernes a las 10:00 (pedido del usuario, 2026-11-19). Nadie la
mira mientras corre: **no hagas preguntas**. Lo que harías preguntando queda fuera y va al informe. Haz solo el Paso 1
del `SKILL.md` de `/Actualizar_Finanzas` (con el Paso 2 de `/Registro_Centro_de_Costos`), con estas reglas.

## Qué factura entra a `datos_extraidos.json`

Solo la que cumple **todo** esto (si una falla, queda fuera con su motivo):

1. Abriste el archivo y leíste N° de documento, fecha, proveedor, ítems y total. Si no puedes abrirlo (por ejemplo, un
   HEIC) o una parte importante no se lee: fuera.
2. Trae **un solo** documento y su nombre no es uno ya usado. Nunca corras `separar`, `eliminar` ni muevas o renombres
   archivos: eso lo decide una persona.
3. **Cuadra**: la suma de los ítems da el Neto impreso y Neto + impuestos da el Total impreso, con a lo más $2 de
   diferencia por redondeo. Sin cuadre: fuera.
4. **Proveedor**: el RUT calza con uno conocido (reusa esa razón social exacta) o es un RUT legible que no está en el
   libro. Un nombre parecido a uno registrado sin el mismo RUT: fuera.
5. El proyecto ya existe en el libro (no hace falta preguntar `tipo_proyecto`).
6. Ningún ítem es un equipo o herramienta de más de $20.000 (regla del 2026-07-16: se pregunta si es del proyecto o de
   Gastos Generales).
7. OC: si `status` muestra una sola OC abierta que calza, anota `"oc"`; si varias podrían serlo: fuera.
8. Si vino en una rendición del Portal, usa sus datos tal cual; si la foto contradice alguno: fuera.

En cada entrada que agregues:
- `estado`: «Pagado» solo si el documento o la rendición lo prueba (boleta o voucher pagado, rendición). Si no,
  «Pendiente».
- `notas`: agrega «Leída por la corrida programada del <fecha de hoy>», para que se pueda revisar después.

Solo puedes escribir en `Centro de Costos/Sistema/datos_extraidos.json`. Agrega entradas; nunca cambies ni borres
las que ya están.

## Tu parte termina con las facturas

**No corras `run`** (ni el de `/Actualizar_Finanzas` ni el del Centro de Costos) ni `publicar.py`: apenas cierres esta
sesión, `tarea_programada.cmd` corre `driver.py run --con-pendientes`, que registra lo que anotaste, actualiza todo y
publica. Puedes volver a correr el `status` del Centro de Costos para revisar lo que anotaste.

## Informe final (queda en el log, antes de la salida de `run`)

Corto:
1. Facturas anotadas para registrar: proyecto, proveedor, N° y total de cada una.
2. Facturas que quedaron fuera, cada una con su motivo (el número de la regla que falló).

## Modo prueba

Si el pedido dice «MODO PRUEBA»: no escribas ningún archivo. Corre el `status` del Centro de Costos, lee las facturas
pendientes y escribe el informe con lo que **habrías** anotado y lo que habría quedado fuera.
