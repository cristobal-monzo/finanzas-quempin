---
name: Sugerencias_Requerimientos
description: Use when the user types "/Sugerencias_Requerimientos" explicitly. If the user instead asks in natural language without the leading "/" — "qué hay que pasar a la planilla de ingreso", "sugerencias de la planilla", "qué requerimientos se adjudicaron según el Formulador" — ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills), never auto-invoke. Lists the suggestions other tools sent for the Planilla de Ingreso de Requerimientos (estado, valor ofertado/adjudicado) that still need to be typed in by hand, closes the ones already in the sheet, and discards one on request. Never writes the Planilla.
---

# Sugerencias para la Planilla de Ingreso de Requerimientos

La Planilla de Ingreso de Requerimientos (raíz de la biblioteca «Formulación
de proyectos - Documentos») es de las personas. El Formulador y Sistema
QUEMPIN mandan el mensaje `actualizar-requerimiento` cuando un requerimiento
pasa a **Ofertado** o **Adjudicado**, con el valor ofertado o adjudicado (IVA
incluido). **Ninguna herramienta escribe la planilla**: guardarla con
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
