# Diseño: Reportes PDF de Análisis Financiero (Proyecto / Cliente / Categoría / Comparación ad-hoc)

Fecha: 2026-07-21
Estado: aprobado por el usuario (brainstorming), pendiente de plan de implementación.

Extiende el módulo `Sistema Analisis Financiero/` (Excel en `Análisis
Financiero/Análisis de Proyectos.xlsx`). Se apoya en dos specs previos del
mismo módulo:

- [`2026-07-20-analisis-financiero-design.md`](2026-07-20-analisis-financiero-design.md)
  — esquema base (hojas Proyectos/Detalle Costos Reales/Indicadores, playbook
  de KPIs original).
- [`2026-07-21-analisis-financiero-nota-clientes-design.md`](2026-07-21-analisis-financiero-nota-clientes-design.md)
  — Nota del Proyecto, columna "Cliente" + hoja "Clientes" (CLTV), Glosario
  KPIs. **Ya tiene plan de implementación escrito y no ejecutado**
  (`docs/superpowers/plans/2026-07-21-analisis-financiero-nota-clientes-implementacion.md`).

**Prerrequisito explícito**: este spec depende de que el plan de
Cliente/CLTV de arriba esté implementado — el reporte PDF "por cliente" usa
la columna "Cliente" (con su derivación/fuzzy-match) y la hoja "Clientes"
(CLTV, AOV, Vida, Frecuencia, Margen ponderado, Clasificación) como fuente de
datos real, no un sustituto simplificado. Si al ejecutar el plan de este spec
esas piezas todavía no existen en el código, hay que implementarlas primero
(son un prerrequisito de secuencia, no una alternativa de diseño).

## 1. Qué se pide

Un PDF con análisis financiero especializado — indicadores clave, apoyo
visual (tablas/gráficos siempre presentes, aunque no siempre haya
comparación), y enfoque estratégico — para:

1. **Cada proyecto.**
2. **Cada cliente.**
3. **Cada categoría de proyecto** (I+D+i, Mantenimiento, Gastos Generales,
   etc.).
4. **Comparaciones ad-hoc bajo demanda conversacional** (ej. "compara UMAG
   con Cesfam Limache"), sin restringirse a las 3 vistas anteriores.

Los PDF deben seguir el manual de marca oficial de QUEMPIN (logo, colores,
tipografía). La estructura de cada reporte **no es fija** — varía según qué
información es relevante para esa entidad específica.

## 2. Arquitectura: kit de marca + agente redactor (no script determinístico)

El **agente** (`analista-financiero-quempin`) redacta el contenido de cada
reporte — decide qué KPIs destacar, qué comparación aporta señal, y el
orden/foco de la página. Esto no es un script que arma reportes por reglas
fijas: es la única forma de cumplir "la estructura no debe ser siempre la
misma" y de soportar comparaciones ad-hoc arbitrarias pedidas en
conversación.

Dos piezas de infraestructura sí son código determinístico, reutilizado por
cada reporte:

- **Kit de marca** (`Sistema Analisis Financiero/Reportes/brand/`):
  - CSS con los 4 colores oficiales (`#ff5100` Pantone Orange 021 C,
    `#000000` Black C, `#98989a` Cool Gray 7 C, `#54565a` Cool Gray 11 C) y
    Lato embebido en woff2→base64 — **reexportados desde
    `Centro de Costos/Visualizador Web/template.html`** (ya extraídos ahí
    del manual oficial), no re-derivados del PDF de marca de nuevo.
  - Logo (`Material gráfico QUEMPIN/LOGO QUEMPIN.PNG`) para portada/header
    de cada PDF.
  - Componentes HTML reutilizables (fragmentos, no plantillas de página
    fijas): tarjeta de KPI, tabla comparativa, contenedor de gráfico
    (`<canvas>` + Chart.js embebido offline, mismo patrón que el
    visualizador de Centro de Costos).
- **`renderizar_pdf(html: str, ruta_salida: Path)`**
  (`Sistema Analisis Financiero/Reportes/motor_reportes.py`): usa el paquete
  Python `playwright` para imprimir el HTML a PDF vía Chromium headless.
  Reutiliza el Chromium ya cacheado en este equipo
  (`%LOCALAPPDATA%\ms-playwright\chromium-1228`, instalado previamente para
  verificar el visualizador de Centro de Costos) — requiere
  `pip install playwright`, sin necesitar una descarga nueva de navegador
  (a validar en implementación: confirmar que la revisión que pide el
  paquete Python coincide con la ya cacheada; si no coincide,
  `playwright install chromium` descarga la que falte).
- **`datos_reportes.py`**: helper de solo lectura que arma un "paquete de
  datos" (dict) por proyecto/cliente/categoría/comparación arbitraria,
  leyendo `Análisis de Proyectos.xlsx` (hojas Proyectos, Indicadores,
  Detalle Costos Reales, Clientes). El agente consume este paquete — nunca
  lee celdas de Excel directamente — para que cualquier cifra en el PDF sea
  trazable a una función auditable, nunca inventada ni mal-leída a mano.

## 3. Cambios al modelo de datos (además del prerrequisito de Cliente/CLTV)

Se agrega **"Categoría"** como columna nueva de **solo lectura** en la hoja
"Proyectos", leída automáticamente desde `Centro de Costos.xlsx` (columna
"Tipo de Proyecto" de `Master`, agregada por proyecto) — mismo patrón que
las columnas de Costos Reales (se regenera en cada corrida, nunca se edita a
mano). Se agrega al final de `HEADERS_PROYECTOS`, después de "Cliente" (que
agrega el prerrequisito), para no correr las letras de columna que ya usan
los `ESTILO_COLUMNAS_*` existentes.

Si los documentos de un mismo proyecto en Centro de Costos tienen
`tipo_proyecto` inconsistente entre sí (no debería pasar según ese módulo,
pero no está garantizado), se usa el valor más frecuente y se emite un aviso
de consola — mismo tratamiento que categorías de ítem sin mapeo explícito
hoy.

**No se agrega ninguna otra columna de cliente** — el prerrequisito ya
resuelve esa necesidad con su propia columna "Cliente" + hoja "Clientes".

## 4. Detección de obsolescencia (sin regeneración automática no supervisada)

Nuevo archivo `Reportes/estado_reportes.json`. Por cada reporte generado
(clave: tipo + identificador, ej. `proyecto:UMAG`, `cliente:AGCID`,
`categoria:I+D+i`) guarda:

- Fecha/hora de generación.
- Un hash de los datos de entrada usados (categoría, costos reales totales,
  montos manuales relevantes de "Proyectos"/Indicadores/Clientes para esa
  entidad).

En cada corrida del pipeline existente (encadenado al PASO 12d ya vigente),
se recalcula el hash actual de cada entidad y se compara contra el
manifiesto:

- Si difiere, o la entidad nunca generó reporte, queda marcada
  **"desactualizado"**.
- **No se dispara generación real** — el script solo detecta y deja la
  lista disponible (evita costo/latencia de LLM automático dentro de un
  pipeline no supervisado).

El comando `status` del skill nuevo imprime la lista de reportes
pendientes/desactualizados. La generación real ocurre cuando el usuario la
pide (conversación, o `/Reportes_Analisis_Financiero run`, que en este caso
significa "el agente revisa la lista y redacta/renderiza cada uno
pendiente" — no un `run` 100% script).

Las comparaciones ad-hoc **no** pasan por este manifiesto — se generan
frescas cada vez que se piden, sin quedar registradas como "vigentes" u
"obsoletas" (no hay una versión única "correcta" de una comparación
puntual).

## 5. Tipos de reporte y fuente de datos de cada uno

| Reporte | Fuente principal | Foco sugerido (el agente decide caso a caso) |
|---|---|---|
| **Proyecto** | "Indicadores" (KPIs, Nota del Proyecto, Evaluación), "Proyectos" (montos, desviación), "Detalle Costos Reales" | Rentabilidad y control presupuestario de ESE proyecto; comparación contra el promedio de su categoría cuando aporte señal (no siempre necesaria) |
| **Cliente** | Hoja "Clientes" (CLTV, AOV, Vida del cliente, Frecuencia, Margen ponderado, Clasificación) + sus proyectos asociados (join por "Proyectos"!Cliente) | Valor de la relación comercial completa, no solo ejecución operativa — recurrencia, tendencia de margen entre sus proyectos, por qué está en su tier de Clasificación |
| **Categoría** | Agregado de "Proyectos"/"Indicadores" filtrado por la columna "Categoría" nueva | Rentabilidad promedio y dispersión de la categoría, cuál proyecto es outlier (mejor o peor) dentro de ella |
| **Comparación ad-hoc** | Cualquier combinación de 2+ proyectos/clientes/categorías nombrados en la conversación | Las diferencias más relevantes entre las entidades comparadas — el agente elige qué destacar, no una plantilla fija de "todas las columnas una al lado de la otra" |

Todas comparten los componentes de marca del kit (§2), pero ninguna tiene una
estructura de página fija — el orden y el foco los decide el agente por
reporte, según qué información es relevante para esa entidad específica.
Todo reporte incluye al menos una tabla o un gráfico de apoyo, aunque no
incluya comparación contra otras entidades.

## 6. Completitud de datos y proyectos "en desarrollo"

Reglas de negocio explícitas del usuario (2026-07-21), aplicadas en
`datos_reportes.py` (§2) antes de que cualquier dato llegue al agente:

- **Sin datos manuales completos → sin reporte.** Un proyecto sin todos sus
  campos manuales cargados en "Proyectos" **no genera ningún reporte** (ni
  propio, ni participa en los agregados de cliente/categoría) hasta que se
  complete. Campos requeridos: `Estado`, `Fecha de inicio`, `Monto de Venta
  (sin IVA)`, los 4 costos proyectados (`Costos Materiales/Equipos
  Proyectados`, `Mano de Obra Proyectada`, `Otros Costos Proyectados`) y
  `Mano de Obra Real`. **`Fecha de cierre` queda explícitamente fuera de
  este chequeo** (ver punto siguiente) y `Cliente`/`Categoría` tampoco
  cuentan (se resuelven automáticamente, no son carga manual). Esta lista
  es una decisión de este spec, no un pedido literal del usuario columna
  por columna — si al usar el sistema con datos reales alguna resulta de
  más o de menos, se ajusta.
- **Sin fecha de cierre, o fecha de cierre futura → proyecto "en
  desarrollo", no incompleto.** Si `Fecha de cierre` está vacía, o tiene una
  fecha posterior a la fecha real actual, el proyecto **sí genera reporte**
  (asumiendo que el resto de sus datos manuales está completo), pero el
  paquete de datos marca `en_desarrollo: true` para que el agente incluya un
  indicador visual explícito (ej. una etiqueta "EN DESARROLLO" en el header
  del reporte) — nunca se presenta como si fuera un proyecto cerrado y
  evaluado en forma definitiva.
- **Modificaciones → regeneración.** Ya cubierto mecánicamente por el
  manifiesto de obsolescencia (§4): cualquier cambio en los datos de entrada
  de un proyecto (incluyendo que pase de incompleto a completo, o que su
  `Fecha de cierre` se cumpla y deje de estar "en desarrollo") cambia el
  hash y lo marca desactualizado — no requiere lógica adicional aparte de
  incluir `en_desarrollo` y el resultado de la validación de completitud
  dentro del paquete que se hashea.
- Un cliente o categoría con proyectos mixtos (algunos completos, algunos
  no) igual genera su reporte agregado, **excluyendo silenciosamente** los
  proyectos incompletos del agregado (no bloquea todo el reporte de cliente/
  categoría por un solo proyecto a medio cargar).

## 7. Salida y skill

- PDFs en:
  ```
  Análisis Financiero/Reportes/
  ├── Proyectos/
  ├── Clientes/
  ├── Categorías/
  └── Comparativas/
  ```
- Nuevo skill `.claude/skills/Reportes_Analisis_Financiero/` (mismo patrón
  `driver.py` con `status`/`run` que los demás módulos):
  - `status`: corre la detección de obsolescencia (§4), imprime qué
    reportes están pendientes/desactualizados. Solo lectura.
  - `run`: contexto para que el agente regenere los reportes marcados
    pendientes (no un script que genera contenido solo).
  - `SKILL.md` documenta el flujo: armar paquete de datos
    (`datos_reportes.py`) → redactar HTML con el kit de marca →
    `renderizar_pdf` → actualizar `estado_reportes.json`.
- El PASO 12d ya existente (que invoca este módulo desde Centro de Costos)
  agrega un aviso de consola si quedaron reportes desactualizados tras la
  corrida, sin disparar generación.

## 8. Testing

Infraestructura, no contenido redactado (no es determinístico):

- Cálculo de "Categoría" por proyecto desde Centro de Costos (caso simple,
  caso con `tipo_proyecto` inconsistente entre documentos del mismo
  proyecto).
- Detección de obsolescencia: hash cambia cuando cambian datos de entrada
  relevantes, no cambia si los datos son iguales; entidad nueva sin reporte
  previo queda marcada pendiente.
- `datos_reportes.py`: estructura correcta del paquete para cada tipo de
  entidad (proyecto/cliente/categoría/comparación arbitraria), valores
  trazables a las hojas fuente; validación de completitud (proyecto
  completo/incompleto) y de estado "en desarrollo" (sin fecha de cierre,
  fecha de cierre futura, fecha de cierre pasada) — ver §6.
- `renderizar_pdf`: smoke test — HTML fijo de prueba produce un PDF válido
  y no vacío.

## 9. Fuera de alcance de este spec (explícito)

- El prerrequisito de Cliente/CLTV/Nota del Proyecto/Glosario (§ arriba) —
  ya tiene su propio spec y plan, se ejecuta como prerrequisito, no se
  rediseña acá.
- Dashboard HTML de presentación del módulo — sigue fuera de alcance como en
  los specs anteriores de este módulo.
- Envío automático de los PDFs (email, Slack, etc.) — se generan como
  archivo local, la distribución queda fuera de este spec.
- Ajuste fino del criterio exacto de qué comparación "aporta señal" para
  cada tipo de reporte — es una decisión editorial del agente en cada
  redacción, no una regla codificable de antemano.

## 10. Addendum 2026-07-24: estándar de contenido y layout de 2 páginas

Refina §5 (tipos de reporte) y §7 (skill) tras brainstorming con el usuario.
Aplica a los reportes de **Proyecto, Cliente y Categoría** — la comparación
ad-hoc queda explícitamente fuera de este addendum (ver más abajo).

**Elementos de contenido obligatorios** (siguen sin tener un orden de página
fijo salvo por la división en 2 páginas de abajo; lo obligatorio es que
existan, no cómo se redactan):

1. Resumen ejecutivo (2-4 oraciones).
2. Fortalezas — párrafo de prosa con cifras concretas del paquete de datos
   como evidencia.
3. Debilidades / riesgos — párrafo simétrico, igual con cifras.
4. Análisis de KPIs — interpretación contra una referencia (objetivo del
   playbook, promedio de categoría, u otra entidad similar), no solo el
   valor desnudo.
5. Al menos un gráfico dirigido a un punto específico del análisis (no
   decorativo), con `graficos.grafico_barras_svg`/`grafico_dona_svg`.
6. Notas de cierre con foco estratégico/financiero/empresarial —
   implicancia para una decisión futura, no un resumen repetido.

**Todos los KPIs, siempre.** Se elimina la discreción editorial sobre qué
KPIs mostrar en la tabla de datos: todo reporte incluye la tabla **completa**
de indicadores relevantes a esa entidad (todas las columnas de
"Indicadores" para Proyecto; todas las métricas de la hoja "Clientes" para
Cliente; el agregado completo para Categoría). La discreción editorial se
mantiene solo para qué se **comenta** en prosa (fortalezas/debilidades/notas),
no para qué se **muestra** en la tabla.

**Layout fijo de 2 páginas** (HTML: dos `<div class="pdf-pagina">` dentro de
`contenido_html`; CSS nuevo en `brand.py`, ver Tarea de implementación):

- **Página 1 — panel de verificación, misma estructura en todo reporte**:
  100% visual/tabular. Tabla completa de KPIs (punto anterior), datos clave
  (montos, costos, desviación) y el/los gráfico(s) estándar de apoyo (ej.
  dona de composición de costos). El *contenido* varía según el tipo de
  entidad (qué KPIs/columnas trae), pero el *orden de secciones* de la
  página es siempre el mismo — es el panel de "verificar los números", no
  de análisis.
- **Página 2 — el análisis, contenido variable**: resumen ejecutivo,
  fortalezas, debilidades, notas de cierre (elementos 1-4 y 6 de la lista de
  arriba). Puede incluir gráficos puntuales adicionales si el análisis
  específico lo amerita — sin estructura fija acá, a discreción del agente.
- El header (logo/título/fecha, e indicador "EN DESARROLLO" si aplica) va
  completo arriba de la página 1; **se repite en versión compacta al
  inicio de la página 2** (`brand.encabezado_html`, ver §10.1 — revisa la
  regla original de "una sola vez" de este párrafo). El footer va una sola
  vez, al final de la página 2.

**Comparación ad-hoc: estructura pendiente, explícitamente diferida.** Este
addendum NO define el layout de los reportes de comparación (§5, última
fila de la tabla) — ni el de 2 páginas ni el checklist de contenido
aplican todavía ahí. Cuando el usuario pida trabajar o generar una
comparación, hay que definir su estructura antes de redactarla (no asumir
que se reutiliza este addendum sin más). Ver nota correspondiente en
`Sistema Analisis Financiero/MEMORY.md`.

### 10.1 Addendum 2026-07-24 (revisión): feedback visual sobre el primer PDF real

Tras generar y revisar visualmente `proyecto:UMAG` con el layout de §10, el
usuario pidió 7 ajustes puntuales — todos implementados en `graficos.py` /
`brand.py` como funciones reusables (no hardcodeados en un reporte):

- **Encabezado repetido por página** (reemplaza la frase "una sola vez
  arriba de la página 1" de más arriba): `brand.encabezado_html(titulo,
  generado_el)` genera una versión compacta que el agente inserta al
  inicio de cada `pdf-pagina` después de la primera.
- **Leyenda de color obligatoria** en todo gráfico de dona o de barras por
  categoría: `graficos.leyenda_html(etiquetas, colores)`.
- **Color por categoría de gasto en gráficos de barras comparativos**:
  `grafico_barras_svg(..., colores=[...], opacidades=[...])` — colores
  distintos por categoría (mismo mapeo que la dona/leyenda), `opacidades`
  para diferenciar Proyectado (translúcido) vs Real (sólido) sin perder el
  color de categoría.
- **KPIs fuera de lo esperado en negrita/naranjo**: clase CSS
  `table.tabla-reporte td.alerta` en `brand.py`; qué califica como "fuera
  de lo esperado" queda a criterio del agente (sin umbral fijo en código).
- **Página 1 con densidad algo menos apretada** que la primera pasada
  (radio de dona, alto de barras y tamaños de fuente ligeramente mayores)
  — sigue siendo compacta y de 2 columnas, pero usa mejor el espacio
  disponible.
- **Página 2 prioriza listas escaneables** (`<ul>`/`<ol>` con `<strong>`
  en cifras/conclusiones clave) por sobre párrafos largos, salvo en
  resumen ejecutivo y análisis de KPIs (se mantienen en prosa corta), y
  usa una tipografía de partida mayor (~13px) que la página 1 (~10.5px),
  porque no compite por espacio con gráficos/tablas.

El layout sigue en exactamente 2 páginas tras estos cambios (reverificado
con `pypdf`) — detalle completo en `Sistema Analisis Financiero/MEMORY.md`,
sección "Revisión de estándar tras feedback visual del PDF (2026-07-24)".
