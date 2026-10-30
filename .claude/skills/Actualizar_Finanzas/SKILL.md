---
name: Actualizar_Finanzas
description: Corre todo Finanzas en orden (Centro de Costos con AF y sus tableros, Cotizador, reportes desactualizados, procesador del Intercambio, Flujo de Caja y Oportunidades) y termina con la bandeja de pendientes. Usar SOLO si el usuario escribe "/Actualizar_Finanzas"; ante «actualiza todo», «deja todo al día» o un estado de todos los módulos, confirma primero. Si solo nombra Centro de Costos, usa /Registro_Centro_de_Costos.
---

# Actualizar Finanzas

```
py -3.14 ".claude/skills/Actualizar_Finanzas/driver.py" status
py -3.14 ".claude/skills/Actualizar_Finanzas/driver.py" run [--sin-publicar]
py -3.14 ".claude/skills/Actualizar_Finanzas/driver.py" oportunidades
```

## `status`: siempre antes de `run`

Solo lectura sobre los 5 drivers (CC, AF, Reportes PDF, Cotizador, Flujo de Caja) y los Presupuestos del Formulador.

**Si mostró pendientes de CC sin datos en `datos_extraidos.json`, complétalos antes**, con el Paso 2 de
[Registro_Centro_de_Costos](../../../Centro%20de%20Costos/.claude/skills/Registro_Centro_de_Costos/SKILL.md): `run` los
corre como subproceso y no puede preguntar nada. Si te lo saltas, seguirán pendientes después de `run`.

## `run`: la cadena completa

0. Presupuestos entregados por archivo (desde navegadores sin la carpeta): van a `publicado/formulador/`. Si falla, sigue.
1. **CC `run`**: registra documentos y encadena AF (PASO 12d), el tablero de CC (12c) y el de AF. **Si falla, la cadena se
   detiene**: ningún tablero se actualiza sobre datos a medio escribir.
2. Cotizador `visualizador`. 3. Reportes PDF `status`: lista los desactualizados.
4. Presupuestos del Formulador (solo lectura, tras el run de AF).
5. Procesador del Intercambio (`Sistema Intercambio/procesar.py --forzar`): republica requerimientos, proyectos de AF con su
   sesgo, precios de referencia, lo de Sistema QUEMPIN, el registro de proyectos y `estado.json`.
6. Flujo de Caja `run`. 7. Oportunidades: consulta Mercado Público (unos 3 minutos) y arma su tablero; sin respuesta usa la
   última evaluación y lo avisa.
8. **Publica solo los tableros «REGENERADO en esta corrida»** (autorizado por el usuario el 2026-10-13): `publicar.py
   <claves>` verifica con el candado y hace `git add`; luego commit de solo esas subrutas y `git push` en
   `.worktrees/gh-pages`. Si falla, lo demás ya quedó hecho y el driver dice qué correr. `--sin-publicar` lo omite, para
   acumular corridas. Lo hace también la corrida programada de los lunes a las 10:00.

Desde el paso 5, un fallo no frena nada.

## `oportunidades`

Solo ese tablero: consulta la API, lo arma y lo publica. Lo corre la tarea diaria de las 09:00 (`tarea_oportunidades.cmd`,
log en `logs/oportunidades_*.log`). Si Mercado Público no responde, **no publica**: queda el tablero anterior con su fecha.
Después de publicar manda el correo de alertas. Reglas de la API, las bases y el correo: `Sistema Intercambio/docs/oportunidades.md`.

## Presupuestos del Formulador: revisarlos con el usuario

Los muestra `formulaciones` de [Registro_Analisis_Financiero](../../../Sistema%20Analisis%20Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md):

- **`[NUEVO]` / `[CAMBIÓ]`**: **resúmeselos** (quién, qué oferta, precio, margen, si tiene errores) y márcalos con
  `py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" formulaciones revisadas`.
  No los marques sin mostrárselos: la corrida programada nunca los marca, para que lleguen al usuario.
- **`[ELEGIR TAG]` / `[CARGAR]`**: *Adjudicada* sin costos en AF, o que cambió después de cargarla. **Pregunta a qué TAG
  corresponde**, con el sugerido y lo que hoy tiene AF a la vista. Con su sí, `driver.py formulaciones cargar <uid> <TAG>` (o
  `--nombre "..."` si es nuevo) **antes de `run`**, que lo aplica con respaldo y sin pisar lo escrito a mano.
- `[EN BUZÓN]`, `[CARGADO]`: nada que hacer. `[SIN RESUMEN]`: hay que abrirlo y guardarlo de nuevo en el Formulador.

## Al reportar

Corto: documentos registrados, tableros regenerados y publicados, y qué falta. **Resume la BANDEJA DE PENDIENTES**
(`Sistema Intercambio/bandeja.py`, cierra `status` y `run`): `[!]` marca lo detenido o fallando. Si un módulo falló, di cuál
y que el resto se completó.

## Qué no hace

- **No genera los reportes PDF**: llevan análisis redactado; se hacen con `/Reportes_Analisis_Financiero run`.
- Si el usuario solo quiere CC sin publicar: `/Registro_Centro_de_Costos` con «sin publicar».

## Implementación

Corre **cada módulo en su propio proceso**: tienen archivos homónimos (`build_visualizador.py`, `driver.py`) y `sys.modules`
cachea por nombre. Un módulo nuevo se agrega como una línea más en este driver, no en `auditor_centro_costos.main()`.
