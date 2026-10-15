---
name: Actualizar_Finanzas
description: Use when the user types "/Actualizar_Finanzas" explicitly. If the user instead describes the same intent in natural language without the leading "/" — "actualiza las finanzas", "actualiza todo", "corre todo el pipeline", "deja todo al día", or a read-only status across every module — ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills), never auto-invoke. Runs Centro de Costos (which chains Análisis Financiero and the CC/AF dashboards), then regenerates the Cotizador Histórico dashboard (which nothing else invokes), reports which PDF reports went stale, runs the exchange-folder processor, rebuilds Flujo de Caja (Excel and dashboard) and the Mercado Público opportunities dashboard. Ends with a pending-items tray (bandeja de pendientes). Use /Registro_Centro_de_Costos instead when the user explicitly names only Centro de Costos.
---

# Actualizar Finanzas (orquestador de todos los módulos)

Punto de entrada único de `Finanzas QUEMPIN`. Existe porque la cadena de
actualización estaba incompleta: `run` de Centro de Costos ya encadenaba
Análisis Financiero y dos de los tres tableros, pero **el visualizador de
Cotizador Histórico no lo invocaba nadie** pese a leer el mismo
`Centro de Costos.xlsx`, y los reportes PDF solo se avisaban de pasada.

## Comandos

```
py -3.14 ".claude/skills/Actualizar_Finanzas/driver.py" status
py -3.14 ".claude/skills/Actualizar_Finanzas/driver.py" run
```

**Usar `py -3.14`, no `python`** — el `python` del PATH es 3.11 y no tiene
openpyxl (ver `requirements.txt`).

- **`status`** — solo lectura sobre los 5 drivers (Centro de Costos, Análisis
  Financiero, Reportes PDF, Cotizador Histórico, Flujo de Caja) más la sección
  **Presupuestos del Formulador**. No escribe Excel, ni archivos, ni
  tableros. Es el paso previo obligatorio antes de `run`.
- **`run`** — cadena completa, en orden de dependencias:
  0. Presupuestos entregados por archivo (desde navegadores sin acceso a la
     carpeta): se incorporan al repositorio de formulaciones. Solo escribe en
     `publicado/formulador/` y, si falla, no frena lo demás.
  1. Centro de Costos `run` — registra documentos nuevos. Su propio flujo ya
     encadena Análisis Financiero (PASO 12d), el tablero de Centro de Costos
     (12c) y, dentro de Análisis Financiero, el tablero de Análisis
     Financiero. **Si este paso falla, la cadena se detiene**: no se
     actualiza ningún tablero sobre datos a medio escribir.
  2. Cotizador Histórico `visualizador` — el eslabón que faltaba.
  3. Reportes PDF `status` — lista los que quedaron desactualizados.
  4. Presupuestos del Formulador (solo lectura, después del run de AF).
  5. Carpeta de intercambio — una vuelta completa del procesador
     (`Sistema Intercambio/procesar.py --forzar`): republica requerimientos,
     la lista de proyectos de Análisis Financiero con su sesgo, los precios
     de referencia del Cotizador, lo de Sistema QUEMPIN, el registro de
     proyectos y `estado.json`. Entre una corrida y otra, el procesador corre
     solo cada 2 horas con su propia tarea programada. Si falla, no frena
     nada.
  6. Flujo de Caja `run` — Excel y tablero, armados con lo que el procesador
     acaba de publicar y la foto del Centro de Costos del paso 1 (ver
     [Registro_Flujo_de_Caja](../../../Flujo%20de%20Caja/.claude/skills/Registro_Flujo_de_Caja/SKILL.md)).
     Si falla, no frena nada.
  7. Oportunidades en Mercado Público (2026-10-13) — consulta la API de
     Mercado Público (unos 3 minutos) y arma su tablero
     (`Sistema Intercambio/Visualizador Web/build_visualizador.py`). Sin
     respuesta de la API usa la última evaluación guardada y lo avisa en el
     tablero. Si falla, no frena nada.
- **`oportunidades`** (2026-10-14, pedido del usuario: «que sea diaria») —
  solo el tablero de Oportunidades: consulta la API, lo arma y lo publica en
  GitHub Pages. Lo corre **todos los días a las 08:00** la tarea «Oportunidades
  Mercado Publico QUEMPIN» (`tarea_oportunidades.cmd`, log en
  `logs/oportunidades_*.log`, se guardan 30), aparte de la corrida semanal.
  Si el equipo está apagado a esa hora, corre al encenderlo. Si Mercado
  Público no responde, **no publica**: queda en línea el tablero anterior,
  con su fecha. Si el procesador del intercambio está corriendo (también
  consulta la API), lo espera hasta 15 minutos.
  Desde el 2026-10-14 cubre también las **compras ágiles** (API Compra Ágil
  v2, mismo ticket) y, después de publicar, manda el **correo de alertas**
  (`Sistema Intercambio/alertas_oportunidades.py enviar`, pedido del
  usuario): solo oportunidades con nota 85 o más, como máximo 3 correos en 7
  días y nunca la misma dos veces. Sale por Outlook de este equipo; el
  destinatario está en `oportunidades_destinatarios.json` (gitignoreado). Con
  datos de la caché no se manda nada. `run` hace lo mismo en su paso 7.

## Presupuestos del Formulador: revisarlos y cargarlos con el usuario

Pedido del usuario (2026-09-30): «cuando alguien genere un nuevo presupuesto
quiero que se guarde, o que al menos quede un input para que yo, usando
Claude, pueda actualizar». Cada presupuesto del Formulador queda en el
repositorio de formulaciones (`publicado/formulador/` de la carpeta de
intercambio, en la biblioteca «Formulación de proyectos»). Su sección en
`status`/`run` (comando `formulaciones` de
[Registro_Analisis_Financiero](../../../Sistema%20Analisis%20Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md))
muestra:

- **`[NUEVO]` / `[CAMBIÓ]`** — presupuestos desde la última revisión, con su
  costo, precio neto, margen, estado y autor. **Resúmeselos al usuario** en
  pocas líneas: quién, qué oferta, precio, margen y si tiene errores. Después
  marca la revisión con
  `py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" formulaciones revisadas`.
  No los marques sin habérselos mostrado: la corrida programada de los lunes a las 10:00
  nunca los marca, justamente para que lleguen al usuario.
- **`[ELEGIR TAG]` / `[CARGAR]`** — presupuestos *Adjudicada* cuyos costos no
  están en Análisis Financiero, o que cambiaron después de cargarlos.
  **Pregúntale al usuario a qué proyecto (TAG) corresponde**, con el sugerido
  y lo que hoy tiene Análisis Financiero a la vista. Con su sí, corre
  `driver.py formulaciones cargar <uid> <TAG>` (o `--nombre "..."` si es un
  proyecto nuevo) **antes de `run`**. Así se deja el mismo envío que haría el
  Formulador, y el `run` lo aplica con todas sus garantías: respaldo, y nunca
  pisa un valor escrito a mano que no se vio.
- `[EN BUZÓN]`, `[CARGADO]` — no hay nada que hacer. `[SIN RESUMEN]` — lo
  guardó una versión antigua del Formulador: hay que abrirlo y guardarlo de
  nuevo.

El driver repite al final, en «PRESUPUESTOS DEL FORMULADOR -- para revisar
con el usuario», si queda algo de esto pendiente.

  **Antes de correr este `run`**, si el `status` de arriba mostró
  pendientes de Centro de Costos sin datos en `datos_extraidos.json`, este
  driver los corre como subproceso y no puede preguntarle nada al usuario a
  mitad de camino — completar esas entradas es responsabilidad del agente
  primero, siguiendo el Paso 2 (interactivo, preguntas agrupadas por
  proyecto/documento) de
  [Registro_Centro_de_Costos/SKILL.md](../../../Centro%20de%20Costos/.claude/skills/Registro_Centro_de_Costos/SKILL.md)
  (pedido 2026-08-18) — igual que hace `/Registro_Centro_de_Costos`. Si se salta este paso, esos documentos simplemente
  seguirán apareciendo como pendientes después de `run`.

## Bandeja de pendientes

`status` y `run` cierran con la **BANDEJA DE PENDIENTES**
(`Sistema Intercambio/bandeja.py`, 2026-10-13): todo lo que espera a una
persona, con qué hacer en cada caso. Junta el procesador del intercambio
detenido o con pasos fallando, sus avisos (copias en conflicto incluidas), lo
que espera en el buzón de cada herramienta (sugerencias para la Planilla,
borradores y registros para Sistema QUEMPIN, envíos al AF), proyectos del AF y
cotizaciones de Chile sin N° de requerimiento, reportes PDF desactualizados,
presupuestos del Formulador sin revisar y hallazgos del Centro de Costos por
revisar. Al reportar al usuario, **resume la bandeja**: es la lista de lo que
falta. `[!]` marca lo que está detenido o fallando.

## `run` publica los tableros que regeneró (desde 2026-10-13)

**Regenerar los `build/index.html` en disco no cambia lo que ve la gente**: el
canal es GitHub Pages (repo público, rama `gh-pages`, ver
[`../../../Visualizador Web/CLAUDE.md`](../../../Visualizador%20Web/CLAUDE.md)
§ Hosting). Por eso, con autorización del usuario del 2026-10-13, **`run`
termina publicando solo** los tableros marcados «REGENERADO en esta corrida»:

1. `Visualizador Web/publicar.py <claves>` copia cada tablero con su carpeta
   `reportes/`, verifica con el candado que abre con la contraseña del equipo
   y hace `git add`; si alguno no abre, no se toca gh-pages.
2. Commit de **solo esas subrutas** en `.worktrees/gh-pages` y `git push`.

Lo hace también la corrida programada de los lunes, que antes dejaba los
tableros regenerados sin publicar. El paso aparece en el RESUMEN como
«Publicar tableros en GitHub Pages»; si falla (sin conexión, push rechazado),
el resto de la corrida igual quedó hecho y el driver dice qué correr.

**`run --sin-publicar`** omite ese paso, cuando el usuario quiere acumular
varias corridas y publicar después.

## Qué NO hace (a propósito)

- **No genera los reportes PDF.** Cada PDF lleva análisis redactado por el
  agente (página 2 del estándar de 2 páginas), no es una salida mecánica —
  se generan con `/Reportes_Analisis_Financiero run` cuando corresponda.
- **No es la única forma de actualizar datos sin publicar.** Si el usuario
  solo quiere Centro de Costos y dejar la publicación para después,
  `/Registro_Centro_de_Costos` con «sin publicar» es más directo (antes
  `/Actualizar_Base_de_Datos`, fusionado el 2026-10-13).

## Cómo reportar al usuario

Respuesta corta: cuántos documentos nuevos se registraron, qué tableros se
regeneraron, y qué quedó pendiente (reportes PDF por generar, publicaciones
por hacer). Si algún módulo falló, decir cuál y que el resto sí se completó
— el driver ya distingue fallo bloqueante (Centro de Costos) de fallo
tolerable (un tablero).

## Detalle de implementación relevante

El driver corre **cada módulo en su propio proceso** (`subprocess`), no por
`import`. Los tres módulos tienen archivos homónimos (`build_visualizador.py`,
`driver.py`) y `sys.modules` cachea por nombre, así que importarlos en el
mismo proceso entrega el equivocado. Un proceso por módulo elimina esa clase
de error y evita que un módulo caído voltee a los demás. Si agregas un módulo
nuevo, agrégalo acá como una línea más (así entró Flujo de Caja, 2026-10-02)
— no dentro de `auditor_centro_costos.main()`.
