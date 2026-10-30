---
name: Sugerencias_Requerimientos
description: Lista las sugerencias de otras herramientas para la Planilla de Ingreso (estado, valor ofertado o adjudicado) que faltan por escribir a mano, cierra las que ya están y descarta una si se pide. Nunca escribe la Planilla. Usar SOLO si el usuario escribe "/Sugerencias_Requerimientos"; ante «qué hay que pasar a la planilla» o «sugerencias de la planilla», confirma primero.
---

# Sugerencias para la Planilla de Ingreso de Requerimientos

La Planilla de Ingreso de Requerimientos (raíz de la biblioteca «Formulación
de proyectos - Documentos») es de las personas. El Formulador y Sistema
QUEMPIN mandan el mensaje `actualizar-requerimiento` cuando un requerimiento
pasa a **Ofertado** o **Adjudicado**, con el valor ofertado o adjudicado (IVA
incluido). Desde el 2026-10-05 el Formulador también avisa **No adjudicado**
(oferta Perdida) y **Descartado**, sin valor: con los no adjudicados la
planilla calcula la tasa de adjudicación que usa el Flujo de Caja.
Desde el 2026-10-13 también sugiere el **monitor de Mercado Público**
(`Sistema Intercambio/mercado_publico.py`, en cada vuelta del procesador):
«Adjudicado» con el valor, o «No adjudicado», según lo que publica
ChileCompra. Sus sugerencias traen una línea «Por qué», con el código, la
fecha, el ganador y el monto. Al mostrarlas, cítala tal cual.
**Ninguna herramienta escribe la planilla**: guardarla con
openpyxl borra sus matrices dinámicas y sus imágenes en celdas (medido el
2026-10-01, ver `Sistema Intercambio/requerimientos.py`). Una persona pasa la
sugerencia a mano y el procesador del intercambio la cierra sola cuando la
planilla ya la muestra.

## Comandos

```
py -3.14 ".claude/skills/Sugerencias_Requerimientos/driver.py" status
py -3.14 ".claude/skills/Sugerencias_Requerimientos/driver.py" descartar <id>
```

- **`status`** — lee la planilla en ese momento, cierra lo que ya está pasado
  y lista, por requerimiento, qué escribir en qué columna. Marca con «OJO»
  las que quedaron en conflicto (alguien cambió la planilla después de que se
  hizo la sugerencia): ahí hay que decidir, no copiar.
- **`descartar <id>`** — archiva una sugerencia que no corresponde. La
  herramienta que la envió verá que se descartó.

## Procedimiento

1. Correr `status` y mostrarle al usuario la lista tal cual.
2. Si pide pasar alguna, **no** abrir ni guardar la planilla con código:
   decirle qué escribir y dónde (N°, columna, valor). La pasa él en Excel.
3. Volver a correr `status`: lo que ya quedó en la planilla se cierra solo.
