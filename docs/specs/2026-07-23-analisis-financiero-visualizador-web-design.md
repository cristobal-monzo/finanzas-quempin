# Diseño: Visualizador Web de Análisis Financiero

Fecha: 2026-07-23
Estado: aprobado por el usuario (brainstorming), pendiente de plan de implementación.

Primer dashboard HTML del módulo `Sistema Analisis Financiero/` (hasta ahora
explícitamente fuera de alcance en los specs anteriores de este módulo). Sigue
el mismo patrón ya implementado y validado en
[`Centro de Costos/Visualizador Web/`](../../Centro%20de%20Costos/Visualizador%20Web/CLAUDE.md):
export saneado + `template.html` con datos incrustados + publicación como
Claude Artifact privado con gate de contraseña. Ver también el doc maestro
compartido [`Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(marca, mandato de herramientas dinámicas, política de datos, hosting).

Fuente de datos: `Análisis Financiero/Análisis de Proyectos.xlsx`, que ya
tiene implementadas las hojas Proyectos (con columna Cliente), Indicadores
(Nota del Proyecto, Evaluación), Clientes (CLTV) y Glosario KPIs — ver
[`Sistema Analisis Financiero/CLAUDE.md`](../../Sistema%20Analisis%20Financiero/CLAUDE.md).

## 1. Requisito que dispara este diseño

Pedido explícito del usuario: si un proyecto no tiene toda su información de
carga manual en "Proyectos", **no debe mostrarse con sus KPIs** en el
dashboard. En su lugar, debe aparecer en una lista de pendientes con el
formato `"<Nombre del proyecto> — Falta ingresar información en 'Análisis de
Proyectos'"` y un link a la planilla real:
`https://quempinspa2020.sharepoint.com/:x:/g/IQB005ljfV3VQp6CNg8pSS0tAdjFPmF8jOcQOeU3y0vIaIE?e=kaFVjO`

## 2. Problema técnico de fondo: fórmulas vs. valores cacheados

Las hojas "Indicadores" y "Clientes" son 100% fórmulas de Excel que
`analisis_financiero.py` **reescribe en cada corrida** (`asegurar_hoja_
indicadores`, `asegurar_hoja_clientes`). openpyxl nunca calcula fórmulas —
solo lee el último valor cacheado que había al abrir el archivo. Si el
dashboard se generara automáticamente justo después de guardar (como se
quiere, encadenado al `run`), leería celdas vacías/obsoletas hasta que
alguien abra el `.xlsx` en Excel de verdad y recalcule.

Centro de Costos ya encontró este mismo bug (`Master!"Total sin IVA"` como
`SUMIF` reescrito en cada `run`, ver su
[`Visualizador Web/CLAUDE.md`](../../Centro%20de%20Costos/Visualizador%20Web/CLAUDE.md)
§"Automático desde run") y lo resolvió recomputando en Python en vez de leer
el caché. Este spec aplica la misma solución: **`build_visualizador.py` de
este módulo nunca lee las celdas de "Indicadores"/"Clientes" con fórmulas
complejas** — recomputa Total Real, Margen Real, Desviación %, Nota del
Proyecto, Evaluación, CLTV y Clasificación directamente en Python, leyendo
solo:

- Columnas 100% manuales de "Proyectos" (TAG, Nombre, Cliente, Estado,
  fechas, Monto de Venta, los 4 Costos Proyectados, Mano de Obra Real).
- Columnas de Costos Reales (Materiales/Equipos/Otros) que en "Proyectos" son
  `SUMIFS` hacia "Detalle Costos Reales" — esa hoja sí es 100% valores (no
  fórmulas anidadas), así que se recomputa la misma suma directamente desde
  ahí, no leyendo el caché de la fórmula.

Las fórmulas de negocio a replicar en Python (deben coincidir exactamente
con `analisis_financiero.py`, ver `_formula_nota`/`_formula_evaluacion`/
`asegurar_hoja_clientes`):

```
total_real = costo_materiales_real + costo_equipos_real + costo_mo_real + costo_otros_real
margen_real = monto_venta - total_real
desviacion_pct = total_real / total_proyectado - 1
score_margen = clamp(0, 100, (margen_real / monto_venta) / 0.25 * 100)
score_desviacion = clamp(0, 100, 100 - abs(desviacion_pct) * 100)
nota = round(0.7 * score_margen + 0.3 * score_desviacion)
evaluacion = "Excelente" (>=85) | "Bueno" (>=70) | "Aprobado" (>=55) | "Requiere atención"

# Por cliente, usando SOLO sus proyectos completos:
aov = promedio(monto_venta)
vida = conteo(proyectos)
meses_activo = max(1, (fecha_inicio_max - fecha_inicio_min) en días / 30)
frecuencia = vida / (meses_activo / 12)
margen_pct = suma(margen_real) / suma(monto_venta)
cltv = aov * frecuencia * vida * margen_pct
clasificacion = percentil de CLTV vs. todos los clientes (>=p67 estratégico, >=p33 potencial, resto oportunidad)
```

## 3. Criterio de completitud

Un proyecto (fila válida: TAG + Nombre no vacíos) es **completo** si además
tiene valor no vacío en las 6 columnas: Monto de Venta (sin IVA), Costos
Materiales/Equipos/MO/Otros Proyectados, y Mano de Obra Real. Fechas y Estado
quedan fuera del criterio — no alimentan ninguna fórmula de KPI.

- **Completo** → se recomputan sus KPIs (§2) y entra a la sección
  "Proyectos" del dashboard.
- **Incompleto** → no se calcula ningún KPI. Entra a la lista "Pendientes de
  completar" (§5) con el mensaje y link de §1. Nunca se "adivina" ni se
  rellena con 0 — un costo proyectado en 0 real (ítem que de verdad no
  aplica) no es lo mismo que un campo vacío (no cargado todavía); solo el
  segundo caso cuenta como incompleto.

**Clientes con proyectos mixtos**: CLTV/AOV/Clasificación de un cliente se
calculan usando **solo sus proyectos completos** (como si los incompletos no
existieran todavía). Si tiene ≥1 proyecto incompleto, se agrega una nota
bajo su fila en la tabla: `"N proyecto(s) pendiente(s) de completar"`. Si
**todos** sus proyectos están incompletos, el cliente no tiene fila en la
tabla de Clientes (no hay nada que promediar) — solo aparece indirectamente a
través de sus proyectos en la lista de pendientes.

## 4. Estructura de archivos

Mismo patrón que Centro de Costos, dentro de `Sistema Analisis Financiero/`
(donde vive el código de este módulo desde la reorganización de 2026-07-21 —
no en `Análisis Financiero/`, que solo tiene el Excel):

```
Sistema Analisis Financiero/
└── Visualizador Web/
    ├── CLAUDE.md              # doc de este visualizador — versionado
    ├── template.html          # estructura/CSS/JS + brand kit, SIN datos — versionado
    ├── build_visualizador.py  # export saneado (recomputado en Python) + build — versionado
    ├── data/                  # snapshot intermedio (analisis-financiero.json) — gitignored
    └── build/                 # index.html final con datos incrustados — gitignored
```

`build_visualizador.py` importa `analisis_financiero` (mismo directorio
`Sistema/` en `sys.path`) para reutilizar `RUTA_EXCEL`, `HEADERS_PROYECTOS`,
`LETRA_COL_PROYECTOS` y `leer_filas_proyectos` — nunca sus funciones de
escritura de fórmulas.

## 5. Contenido del dashboard

- **Gate de contraseña**: misma contraseña que ya usa el visualizador de
  Centro de Costos (decisión del usuario) — barrera del lado del cliente,
  no seguridad real, mismo texto de aviso al pie que el de Centro de Costos.
- **Banner "Pendientes de completar"**: visible arriba de todo cuando hay
  ≥1 proyecto incompleto. Contador + lista expandible, cada ítem con el
  mensaje exacto de §1 y un botón/link a la URL de SharePoint dada por el
  usuario.
- **Pestaña "Proyectos"**:
  - KPIs: N° proyectos completos, Margen Real total, Nota promedio, N°
    proyectos en "Requiere atención".
  - Gráficos: ranking de Nota del Proyecto (barras), donut de distribución
    de Evaluación (Excelente/Bueno/Aprobado/Requiere atención).
  - Tabla: Proyecto, Cliente, Estado, Monto de Venta, Margen Real,
    Desviación %, Nota, Evaluación — buscable/ordenable, paginada de a 25
    (mismo patrón que Centro de Costos). **Descope en implementación** (ver
    nota al final de esta sección).
- **Pestaña "Clientes"**:
  - KPIs: cliente top por CLTV, CLTV promedio, conteo por Clasificación.
  - Gráficos: top 8 clientes por CLTV (barras), donut de Clasificación.
  - Tabla: Cliente, AOV, Vida del cliente, Meses activo, Frecuencia, Margen
    de utilidad %, CLTV, Clasificación, nota de proyectos pendientes si
    aplica (§3). Misma nota de descope que la tabla de Proyectos.
- **Tooltips "i"**: en cada KPI/gráfico, reutilizando el texto ya escrito en
  la constante `GLOSARIO_KPIS` de `analisis_financiero.py` — no se redacta
  contenido nuevo ni se construye una sección "Glosario" aparte en el HTML.
- **Marca**: mismos 4 colores oficiales (`#ff5100`, `#000000`, `#98989a`,
  `#54565a`) y Lato embebido, reexportados desde
  `Centro de Costos/Visualizador Web/template.html` (no se re-derivan del
  PDF de marca de nuevo).
- **Datos incrustados** (base64 dentro del HTML, no `fetch`) — mismo motivo
  que Centro de Costos: el canal de consumo es un Claude Artifact privado,
  cuyo sandbox no permite `fetch` a archivos locales.

**Nota (post-implementación, revisión final de rama)**: la paginación de a
25 y el orden de columnas clickeable descritos arriba para ambas tablas se
descartaron deliberadamente durante la implementación — no fue un olvido.
Los volúmenes de datos de este módulo son decenas de proyectos/clientes, no
los cientos de documentos que justificaron ese patrón en Centro de Costos;
buscador + orden fijo (Nota / CLTV descendente) cubren la necesidad
práctica actual. Ver `Sistema Analisis Financiero/Visualizador Web/CLAUDE.md`
§Contenido. Revisar si el N° de proyectos crece lo suficiente para
justificar implementarlo.

## 6. Automatización

Se agrega un paso nuevo al final de `ejecutar()` en `analisis_financiero.py`
(después de `aplicar_estilo_visual(wb)` y `wb.save(...)`): llama a
`Visualizador Web/build_visualizador.py`, envuelto en try/except para que un
fallo del build **nunca aborte** `ejecutar()` — mismo contrato que PASO 12c
de Centro de Costos (`actualizar_visualizador()`), solo agrega un aviso a
`resumen["avisos"]` si falla.

Como Análisis Financiero ya corre encadenado al final del `run` de Centro de
Costos (PASO 12d de `auditor_centro_costos.py`), un solo `run` de Centro de
Costos termina regenerando **ambos** dashboards sin pasos manuales
adicionales.

## 7. Skill y publicación

- Se agrega el comando `visualizador` a `driver.py` de
  `.claude/skills/Registro_Analisis_Financiero/` (`python driver.py
  visualizador`), mismo patrón que `Registro_Centro_de_Costos`.
- Publicación como Claude Artifact privado. Al ser el primer dashboard de
  este módulo, se genera un link nuevo (no hay uno previo que reutilizar).
  Una vez publicado, el link se documenta en
  `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/MEMORY.md`
  (archivo nuevo, misma convención que el `MEMORY.md` del skill de Centro de
  Costos: preferencias/link ahí, nunca en el `CLAUDE.md` del módulo) y no se
  debe regenerar después salvo pedido explícito del usuario.

## 8. Testing

Infraestructura, no contenido visual final:

- Cómputo de completitud: proyecto con las 6 columnas llenas → completo; con
  alguna vacía (incluyendo 0 vs. `None` distinguidos correctamente) →
  incompleto, aparece en pendientes con el mensaje y link exactos.
- Recomputo en Python de Total Real/Margen Real/Desviación %/Nota/Evaluación
  coincide con la fórmula de Excel para los mismos casos que ya cubren
  `test_formulas_proyectos.py`/`test_nota_evaluacion.py` — paridad exacta,
  no aproximada.
- CLTV/AOV/Clasificación recalculados excluyendo proyectos incompletos de un
  cliente con proyectos mixtos.
- Cliente con el 100% de sus proyectos incompletos no genera fila en la
  tabla de Clientes.
- Smoke test: `build_visualizador.py` produce un `build/index.html` no
  vacío con el snapshot incrustado, a partir de un workbook temporal de
  prueba (nunca contra el Excel real de la empresa).

## 9. Fuera de alcance de este spec (explícito)

- Reportes PDF por proyecto/cliente/categoría/comparación ad-hoc — spec
  aparte ya aprobado y sin implementar
  ([`2026-07-21-analisis-financiero-reportes-pdf-design.md`](2026-07-21-analisis-financiero-reportes-pdf-design.md)),
  no se rediseña ni se implementa acá.
- Consultor IA conversacional sobre los datos del dashboard.
- Envío automático del link del dashboard (email, Slack, etc.).
- Hosting en GitHub Pages — igual que Centro de Costos, el punto de control
  de acceso del maestro sigue sin resolverse; se publica como Claude
  Artifact privado por ahora.
