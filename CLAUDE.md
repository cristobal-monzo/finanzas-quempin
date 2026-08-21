# CLAUDE.md

Este archivo guía a Claude Code (claude.ai/code) al trabajar con código en este repositorio.

## Qué es este directorio

`Finanzas QUEMPIN` es el punto de consolidación de las herramientas de automatización financiera de QUEMPIN SpA. No es un codebase en sí mismo — es un contenedor pensado para tener una subcarpeta por cada módulo financiero, donde cada módulo es una herramienta independiente en Python/openpyxl que mantiene un proceso manual de Excel sincronizado con sus documentos fuente (facturas, boletas, etc.).

**Sí hay repositorio git en esta raíz** (rama `master`), que versiona el
código, los tests, las skills y la documentación — nunca los datos
financieros, excluidos por `.gitignore`. Ver "Entorno" más abajo para las
herramientas a nivel raíz.

## Entorno

Todo el repo corre con **un solo intérprete**: `py -3.14`.

```
py -3.14 -m pip install -r requirements.txt
py -3.14 -m playwright install chromium      # solo para los reportes PDF
py -3.14 -m pytest                           # las 7 suites juntas (471 tests)
```

**No uses `python` a secas**: en este equipo el `python` del PATH es 3.11 y
no tiene openpyxl instalado, así que cualquier driver falla con
`ModuleNotFoundError`. Los `SKILL.md` que dicen `python driver.py ...` se
refieren a este intérprete.

`pytest.ini` (raíz) configura las 7 suites como una sola corrida. Hasta el
2026-07-28 solo se podía testear carpeta por carpeta, y por ese hueco se coló
una divergencia real entre el KPI "Nota del Proyecto" del dashboard web y el
del Excel/PDF — corre siempre la suite completa antes de dar algo por bueno.

## Invocación de skills: siempre con "/", nunca automática por lenguaje natural

Pedido explícito del usuario, 2026-08-18: todos los skills de `Finanzas
QUEMPIN` (los de esta raíz y los de cada módulo) se invocan por su nombre
explícito con "/" (ej. `/Actualizar_CC`, `/Registro_Centro_de_Costos`,
`/Cotizador_Historico`). Si el usuario describe la misma intención en
lenguaje natural sin escribir el "/" (ej. "actualiza el centro de costos",
"revisa los errores del excel", "¿cuánto debería costar un taladro?"), el
agente **no invoca el skill directamente** — primero pregunta en la
conversación a cuál skill se refiere (ej. "¿Te refieres a
`/Actualizar_CC`?") y espera confirmación explícita antes de llamarlo. Esto
aplica a los 11 skills del proyecto por igual, incluyendo los de solo
lectura/consulta (`/Cotizador_Historico`, `status` de cualquier
registrador) — no solo los que escriben o publican algo.

Cada `SKILL.md` sigue documentando sus frases-gatillo en lenguaje natural
en su `description` (necesarias para que el agente sepa cuál skill ofrecer
como opción), pero esa frase dispara una pregunta de confirmación, nunca
una invocación automática. Reemplaza la política anterior de varios skills
("esto es el default para esas frases" / "rutea automáticamente a X"), que
quedó desactualizada con este pedido.

## Módulos

| Módulo | Estado | Documentación |
|---|---|---|
| [Centro de Costos/](Centro%20de%20Costos/CLAUDE.md) | Implementado | `Centro de Costos/CLAUDE.md` |
| [Cotizador Historico/](Cotizador%20Historico/CLAUDE.md) | Implementado | `Cotizador Historico/CLAUDE.md` |
| [Análisis Financiero/](Sistema%20Analisis%20Financiero/CLAUDE.md) | Implementado (2026-07-20) | `Sistema Analisis Financiero/CLAUDE.md` |
| Flujo de Caja | No iniciado | — |
| [Visualizador Web/](Visualizador%20Web/CLAUDE.md) | Implementado en los 3 módulos (CC 2026-07-19, AF 2026-07-23, Cotizador) | `Visualizador Web/CLAUDE.md` |

## Cómo se actualiza todo: `/Actualizar_Finanzas`

Punto de entrada único (`.claude/skills/Actualizar_Finanzas/`), agregado el
2026-07-28:

```
py -3.14 ".claude/skills/Actualizar_Finanzas/driver.py" status   # solo lectura
py -3.14 ".claude/skills/Actualizar_Finanzas/driver.py" run      # cadena completa
```

Corre Centro de Costos (que ya encadena Análisis Financiero + los tableros de
CC y AF), regenera el tablero de Cotizador Histórico —que antes no
regeneraba nadie, pese a leer el mismo `Centro de Costos.xlsx`— y reporta qué
reportes PDF quedaron desactualizados. Cada módulo corre en **su propio
proceso**: los tres tienen archivos homónimos (`build_visualizador.py`,
`driver.py`) que colisionan en `sys.modules` si se importan juntos.

**Al agregar un módulo nuevo (ej. Flujo de Caja), engánchalo ahí**, no dentro
de `auditor_centro_costos.main()`.

**Centro de Costos** registra el gasto por centro de costos: lee fotos de facturas/boletas depositadas en carpetas por proyecto más un `datos_extraidos.json` ya extraído (con desglose en ítems de línea), y mantiene `Centro de Costos.xlsx` (Master = 1 fila/documento con fórmulas, Detalle = 1 fila/ítem, una hoja de solo lectura por proyecto), de forma idempotente y con backup automático con timestamp antes de cada escritura. La arquitectura completa, el flujo del script, el esquema del JSON y el skill `/Registro_Centro_de_Costos` (comandos `status`/`run`) están documentados en su propio `CLAUDE.md` — léelo antes de tocar cualquier cosa bajo `Centro de Costos/`.

**Visualizador Web** es transversal a todos los módulos: cada uno tendrá, en su propia carpeta, una subcarpeta `Visualizador Web/` con un HTML publicado online (gráficos, tablas dinámicas, buscadores, filtros). El doc maestro compartido (marca, mandato de herramientas dinámicas, política de datos, hosting) vive en `Visualizador Web/CLAUDE.md` a nivel raíz; cada módulo tiene su propio `<Módulo>/Visualizador Web/CLAUDE.md` con el contenido específico a presentar. **Centro de Costos ya tiene una implementación real** (2026-07-19): `Centro de Costos/Visualizador Web/template.html` (estructura, versionada) + `build_visualizador.py` (export + build, corrible vía `driver.py visualizador` del skill `/Registro_Centro_de_Costos`) generan un `build/index.html` autocontenido con los datos incrustados, publicado en GitHub Pages (único canal desde la migración del 2026-08-05 — los Claude Artifacts privados que se usaban antes ya no se actualizan, pedido explícito del usuario 2026-08-19). **Los tres módulos implementados ya tienen su visualizador real** (Centro de Costos 2026-07-19, Análisis Financiero 2026-07-23, Cotizador Historico); solo Flujo de Caja sigue con el scaffolding de `CLAUDE.md`. Ver el spec original en `docs/superpowers/specs/2026-07-19-visualizador-web-design.md`.

**Los tres se regeneran en disco, y los tres tienen ahora su propio skill "run + publicar" en un solo paso** (2026-08-05): `/Actualizar_CC` (Centro de Costos), `/Actualizar_AF` (Análisis Financiero), `/Actualizar_Cotizador` (Cotizador Histórico) — cada uno corre su registrador/visualizador y republica el dashboard existente en GitHub Pages (URL estructural fija, nunca un link nuevo). Úsalos cuando el usuario nombra un solo módulo; para los tres a la vez sigue siendo `/Actualizar_Finanzas` (que no publica por sí solo — deja los 3 builds listos en disco y reporta cuáles se regeneraron, la publicación de cada uno la hace el agente siguiendo la sección de arriba de ese skill).

**Análisis Financiero** es distinto a los demás: no es solo un pipeline de registro, es un rol consultivo — actúa como analista financiero experto (evalúa proyectos, propone/depura KPIs, decide cómo presentar la información, cruza todos los módulos), sobre un Excel (`Análisis de Proyectos.xlsx`) que consolida costos reales de Centro de Costos contra ventas y proyecciones manuales por proyecto. **Reorganizado 2026-07-21**: `Análisis Financiero/` contiene únicamente el Excel de trabajo; el código, los tests y el skill viven en la carpeta hermana `Sistema Analisis Financiero/` (ver su `CLAUDE.md` para el diseño completo). Implementado y encadenado al `run` de Centro de Costos (PASO 12d) — ver `Sistema Analisis Financiero/CLAUDE.md`. Desde 2026-07-23 también tiene un Visualizador Web propio (`Sistema Analisis Financiero/Visualizador Web/`, mismo patrón que Centro de Costos: proyectos completos con sus KPIs + Clientes/CLTV, excluyendo del cálculo cualquier proyecto sin información manual completa).

Se espera que los módulos futuros (ej. Flujo de Caja) consuman datos que ya producen módulos anteriores (ej. totales por proyecto de Centro de Costos) en vez de construirse de forma aislada — revisa qué datos ya calculan los módulos existentes antes de duplicar esa lógica en uno nuevo.

## Al trabajar en este directorio

- **Datos financieros reales, excluidos de git**: todo lo que hay bajo cada módulo (JSON extraído, fotos de documentos fuente, los libros `.xlsx`, los reportes PDF) es información financiera real de la empresa — montos, proveedores, números de documentos tributarios. Trátalo como sensible. El `.gitignore` de la raíz los excluye **por patrón** (`*.xlsx`, `**/datos_extraidos*.json`, `**/backup_*/`, `Análisis Financiero/Reportes/`, …), no por ruta exacta: una auditoría del 2026-07-28 encontró el libro maestro y `datos_extraidos.json` expuestos dentro de `Centro de Costos/backup_centro_costos_original/` justamente porque las reglas viejas apuntaban a rutas puntuales. **Si agregas una fuente de datos nueva, agrégala como patrón** y verifica con `git check-ignore -v <ruta>` antes de commitear.
- **Esta es una carpeta de OneDrive sincronizada**, potencialmente editada por más de una persona/dispositivo en paralelo. Antes de sobrescribir cualquier `.xlsx`, considera que puede tener ediciones manuales recientes hechas fuera de un script.
- **Ubicación duplicada — resuelta el 2026-07-16**: `Finanzas QUEMPIN/Centro de Costos/` es ahora la única ubicación canónica del módulo (rutas de `auditor_centro_costos.py` recalculadas desde `Path(__file__)`, ya no hardcodeadas a otra carpeta). Existen otras dos copias con datos desactualizados/parciales que **no** hay que editar ni usar como fuente de verdad: `OneDrive - QUEMPIN SPA/Sitio de comunicación - Centro de costos/` (quedó con una estructura simple antigua) y `OneDrive - QUEMPIN SPA/Plantillas/` (ahí corrió un pipeline más avanzado — `build.py`/`rename.py`/etc. — que se perdió antes de integrarse aquí; su resultado final fue la base para reconstruir la estructura actual, ver `Centro de Costos/CLAUDE.md`). Si en el futuro aparece contenido nuevo en cualquiera de esas dos carpetas, confírmalo con el usuario antes de asumir que reemplaza lo que hay aquí.
