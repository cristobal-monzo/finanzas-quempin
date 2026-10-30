# CLAUDE.md — Finanzas QUEMPIN

Repositorio público (nada de datos reales) con los módulos financieros de
QUEMPIN SpA: herramientas Python/openpyxl que mantienen un Excel al día desde
sus documentos fuente, cada una con su tablero web. **Antes de tocar un módulo
lee su `CLAUDE.md`** (carga solo al leer archivos de esa carpeta).

| Carpeta | Qué hace |
|---|---|
| `Centro de Costos/` | Facturas y boletas → `Centro de Costos.xlsx`, idempotente y con respaldo antes de cada escritura |
| `Sistema Analisis Financiero/` | Código de AF (el Excel vive en `Análisis Financiero/`): rentabilidad por proyecto, reportes PDF; rol de analista experto |
| `Cotizador Historico/` | Precio de hoy de un material: taxonomía, atributos y buscador (motores reutilizables) |
| `Flujo de Caja/` | Proyección de caja, solo Chile; consumidor puro de CC, Sistema QUEMPIN, Planilla y AF |
| `Sistema Intercambio/` | Protocolo entre herramientas, procesador, Planilla, Oportunidades de Mercado Público |
| `Visualizador Web/` | Reglas comunes de los tableros, hub, Portal QUEMPIN, candado y publicación |
| `Peru/` | Tableros de Perú (CC, AF, Cotizador) con `template.html` propio: un cambio en un tablero de Chile suele valer también allí |
| `docs/` | `actualizar-un-modulo.md` (procedimiento común de las skills), `specs/` (diseños), `plans/` (ya ejecutados; no leer salvo que se pida) |

## Entorno y ramas

- Intérprete único: `py -3.14`. El `python` del PATH es 3.11 sin openpyxl; los
  `SKILL.md` que dicen `python driver.py` se refieren a `py -3.14`.
- Instalar: `py -3.14 -m pip install -r requirements.txt` y
  `py -3.14 -m playwright install chromium` (solo reportes PDF).
- Pruebas: `py -3.14 -m pytest` desde esta raíz (`pytest.ini` junta todas las
  suites). Corre la suite completa antes de dar algo por bueno: por probar
  carpeta por carpeta se coló una divergencia entre el tablero y el Excel.
- Rama de trabajo: la del árbol principal, `auditoria-proceso-errores`
  (`master` quedó atrás el 2026-10-20). Las otras sesiones trabajan en
  `.worktrees/<rama>` y mergean aquí.
- **Las 4 tareas programadas corren el código de este árbol** (`Sistema
  Intercambio/tarea_procesador.cmd` y `tarea_planilla.cmd`,
  `.claude/skills/Actualizar_Finanzas/tarea_programada.cmd` y
  `tarea_oportunidades.cmd`). Un cambio de código se prueba en un worktree;
  aquí solo entra terminado.

## Skills: solo con «/»

Pedido del usuario: las 9 skills se invocan únicamente si escribe su nombre con
«/». Si describe la intención con palabras («actualiza el centro de costos»,
«¿cuánto debería costar un taladro?»), pregunta «¿Te refieres a
`/Registro_Centro_de_Costos`?» y espera el sí; vale también para las de solo
lectura. Las frases-gatillo de cada `SKILL.md` sirven para saber cuál ofrecer,
no para invocar. Un nombre antiguo (`/Actualizar_CC`,
`/Actualizar_Base_de_Datos`, `/Actualizar_AF`, `/Actualizar_Cotizador`) es la
skill nueva: dilo en una línea y sigue.

| Cuándo | Skill |
|---|---|
| Todo al día (4 módulos y tableros) y qué espera a una persona | `/Actualizar_Finanzas` |
| Registrar facturas y boletas; publicar el tablero de CC | `/Registro_Centro_de_Costos` |
| Revisar hallazgos, celdas rojas o ítems agrupados de CC | `/Revision_de_Errores` |
| Recalcular AF, confirmar clientes o envíos; publicar su tablero | `/Registro_Analisis_Financiero` |
| Reportes PDF de un proyecto, cliente o categoría | `/Reportes_Analisis_Financiero` |
| Cuánto debería costar algo hoy; publicar el tablero del Cotizador | `/Cotizador_Historico` |
| Flujo de caja (Excel y tablero) | `/Registro_Flujo_de_Caja` |
| Sugerencias del Formulador para la Planilla de Ingreso | `/Sugerencias_Requerimientos` |
| Reorganizar las carpetas de un proyecto | `/Organizar_Proyecto` |

Cada skill de registro publica su tablero al terminar (URL fija, nunca un link
nuevo) salvo que el usuario diga «sin publicar». Procedimiento común:
[`docs/actualizar-un-modulo.md`](docs/actualizar-un-modulo.md); cada `SKILL.md`
agrega solo lo propio.

## `/Actualizar_Finanzas`

`py -3.14 ".claude/skills/Actualizar_Finanzas/driver.py" status|run`. `run`
corre, cada módulo en **su propio proceso** (los `build_visualizador.py` y
`driver.py` homónimos chocan en `sys.modules`): entregas de presupuestos,
Centro de Costos (encadena AF y los tableros de CC y AF); en paralelo el
tablero del Cotizador, el estado de los PDF y los presupuestos del Formulador;
después el procesador, Flujo de Caja y el tablero de Oportunidades. Publica solo
los tableros que regeneró (`--sin-publicar` lo omite) y cierra con la bandeja de
pendientes y la tabla `TIEMPOS` (`(P)` = en paralelo; se compara la unión de
sus intervalos, por eso los porcentajes pasan de 100). Un módulo nuevo se
engancha aquí, no dentro de `auditor_centro_costos.main()`.

## Intercambio entre herramientas

Todas (también el Formulador y Sistema QUEMPIN, fuera de este repo) se comunican
solo por la carpeta de Intercambio, en la biblioteca de SharePoint «Formulación
de proyectos - Documentos» (`.Herramientas formulación/Intercambio/`): `buzon/`
para pedir, `publicado/` para compartir; protocolo en
`Sistema Intercambio/intercambio.py`, formatos en `Sistema Intercambio/esquemas/`,
clave común = N° de la Planilla de Ingreso. Cada una es dueña de sus datos: nunca
leas ni escribas archivos de otro módulo. Los costos reales de CC llegan al
Formulador por la publicación de AF. Antes de calcular algo nuevo, revisa si
otro módulo ya lo produce. Detalle: `Sistema Intercambio/CLAUDE.md`.

## Tableros

Cada módulo tiene `<Módulo>/Visualizador Web/`: `template.html` (versionado) +
`build_visualizador.py` → `build/index.html` con los datos incrustados. Se
publican solo en GitHub Pages con `Visualizador Web/publicar.py` (los Artifacts
ya no se usan, pedido del usuario). Reglas comunes: `Visualizador Web/CLAUDE.md`.

## Principios aprendidos midiendo (no reaprenderlos)

- **Mide antes de optimizar**: el cuello de botella nunca estuvo donde se creía.
  CC cierra con `TIEMPO POR ETAPA` (PASO 1..13).
- `load_workbook` cuesta 0,3–0,8 s por apertura: abre el libro una vez y pasa el
  `wb`; corrige por lote, no por celda.
- **No midas contra producción**: `main()` llama primero a `configurar_pais()`,
  que reescribe todas las rutas, así que parchearlas no aísla nada. Registra un
  país ficticio en `acc.PAISES`, corre `main(pais="<ese>")` y aborta si una ruta
  de escritura sale del sandbox. En un proceso incremental mide también la
  segunda corrida, con datos e historial ya cargados.
- **Dos caminos que calculan lo mismo terminan divergiendo**: una sola función
  (`status` y `run` usan la misma validación). Si hace falta en Python y en el
  navegador: Python calcula lo que depende de los datos, JS solo lo que depende
  de lo que se teclea, un solo `.js` para Chile y Perú, y un test que corra los
  dos y compare (`Cotizador Historico/Sistema/tests/test_paridad_busqueda_js.py`).
- **Reutiliza los motores, no escribas otro**: `validar_documento()` y el registro
  de errores de CC; taxonomía, atributos, presentación y buscador del Cotizador
  (`Cotizador Historico/Sistema/`).
- **Un hallazgo que solo se imprime no está resuelto**: necesita un canal de cierre
  auditado.
- **Lo que no tiene decisión editorial se genera, no se redacta**
  (`Sistema Analisis Financiero/Reportes/panel.py`). Al que redacta dale los
  números ya comparados; un color sin dirección no informa (`brand.estado_kpi`).
- Un buscador se evalúa con un set fijo de consultas (`driver.py benchmark`); un
  caso cuya respuesta no está en los datos no mide nada.

## Datos y carpeta

- **Datos reales fuera de git, excluidos por patrón** en `.gitignore` (`*.xlsx`,
  `**/datos_extraidos*.json`, `**/backup_*/`, …), no por ruta. Una fuente nueva se
  agrega como patrón y se verifica con `git check-ignore -v <ruta>`.
- Carpeta de OneDrive editada por varias personas: un `.xlsx` puede tener cambios
  manuales recientes; no lo sobrescribas a ciegas.
- `Centro de Costos/` de aquí es la única ubicación del módulo. Las copias
  `OneDrive - QUEMPIN SPA/Sitio de comunicación - Centro de costos/` y
  `OneDrive - QUEMPIN SPA/Plantillas/` son antiguas: no las edites ni las uses
  como fuente; si aparece algo nuevo ahí, pregunta.
