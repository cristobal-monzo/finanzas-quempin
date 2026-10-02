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
py -3.14 -m pytest                           # las 7 suites juntas (972 tests)
```

**No uses `python` a secas**: en este equipo el `python` del PATH es 3.11 y
no tiene openpyxl instalado, así que cualquier driver falla con
`ModuleNotFoundError`. Los `SKILL.md` que dicen `python driver.py ...` se
refieren a este intérprete.

`pytest.ini` (raíz) configura las 7 suites como una sola corrida. Hasta el
2026-07-28 solo se podía testear carpeta por carpeta, y por ese hueco se coló
una divergencia real entre el KPI "Nota del Proyecto" del dashboard web y el
del Excel/PDF — corre siempre la suite completa antes de dar algo por bueno.

## Observabilidad: cada corrida dice dónde se fue el tiempo

Desde la auditoría del 2026-09-09, `run` imprime dos desgloses que antes no
existían y que son la forma de detectar una regresión de rendimiento sin
tener que perfilar a mano:

- **`/Actualizar_Finanzas`** cierra con una tabla `TIEMPOS` por módulo. Los
  pasos que corren en paralelo se marcan `(P)`; lo que se compara contra el
  total es la **unión** de sus intervalos, no la suma (por eso los
  porcentajes pueden pasar de 100).
- **Centro de Costos** cierra con `TIEMPO POR ETAPA` (los PASO 1..13 de
  `auditor_centro_costos.main()`), ocultando las etapas de menos de 0,05 s.

Reglas aprendidas midiendo, que conviene no reaprender a golpes:

- **El cuello de botella casi nunca está donde uno cree.** El tablero del
  Cotizador se llevaba más de un tercio del total por re-normalizar los
  mismos términos del catálogo 2,1 millones de veces; Análisis Financiero se
  llevaba otro 42 % de Centro de Costos por abrir `Centro de Costos.xlsx`
  tres veces seguidas. Mide antes de optimizar.
- **`load_workbook` de openpyxl cuesta ~0,3–0,8 s por apertura** de este
  libro. Si un módulo necesita leerlo más de una vez, ábrelo una sola vez y
  pasa el `wb`.
- **No midas contra producción.** `main()` llama a `configurar_pais()` como
  primera línea, que **reescribe todos los globals de ruta**: parchearlos
  desde afuera no aísla nada. Para correr el pipeline sin tocar los datos
  reales, registra un país ficticio en `acc.PAISES` y llama
  `main(pais="<ese>")`, más un guard que aborte si alguna ruta de escritura
  quedó fuera del sandbox.

## Errores: se validan antes de escribir y se cierran, no se reimprimen

Desde la auditoría del 2026-09-10, Centro de Costos valida cada documento
**antes** de escribirlo (PASO 5B) y lleva un registro persistente de errores
con ciclo de vida (`Sistema/errores_detectados.json`, gitignoreado — lleva
montos reales). Antes, el cuadre de impuesto corría en el PASO 13, después de
publicar el libro en sus tres consumidores, y los hallazgos solo existían como
texto de consola: no había forma de cerrarlos ni de evitar que se reimprimieran
idénticos en cada corrida.

Lo que conviene no reaprender, medido con `Centro de Costos/Sistema/bench/`:

- **Un hallazgo que solo se imprime no es un hallazgo resuelto.** Sobre un
  corpus con 36 defectos conocidos, el proceso anterior cerraba 10; el actual,
  24. La diferencia no es mejor detección (eso también subió, de 61 % a 100 %
  de recall) sino que existan canales de cierre auditados para más clases de
  error.
- **Resolver de a una celda cuesta una apertura de libro cada vez.** Corregir
  por lote bajó el tiempo medio por resolución de 0,71 s a 0,14 s.
- **Dos caminos calculando lo mismo terminan divergiendo** — ya pasó con el KPI
  "Nota del Proyecto" (2026-07-28) y con la taxonomía duplicada en JavaScript
  (2026-09-08). Por eso `status` y `run` corren ahora *la misma* función de
  validación, y el detector de duplicados que vivía dentro del bucle de
  escritura se eliminó (ignoraba el emisor y producía 2 falsos positivos sobre
  las 681 entradas reales).

- **Un banco de pruebas que parte de cero no prueba un sistema que ya tiene
  historial.** El benchmark daba 100 % de recall y 24 de 36 defectos cerrados, y
  aun así la revisión de errores no podía cerrar **ni uno solo** sobre los datos
  reales: su sandbox arranca vacío y registra todo en la corrida que mide, así
  que ejercitaba un camino que en producción —728 filas ya escritas, 0
  pendientes— nunca se recorre. Cuando midas un proceso incremental, mide
  también la segunda vez: con los datos ya cargados y con correcciones previas
  encima.

**Si agregas un módulo que valide documentos, reutiliza `validar_documento()` /
el registro de errores en vez de escribir otro** — mismo criterio que con el
motor de taxonomía del Cotizador.

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
| [Flujo de Caja/](Flujo%20de%20Caja/CLAUDE.md) | Implementado (2026-10-02), solo Chile: consumidor puro de CC, Sistema QUEMPIN, Planilla de Ingreso y AF | `Flujo de Caja/CLAUDE.md` |
| [Visualizador Web/](Visualizador%20Web/CLAUDE.md) | Implementado en los 4 módulos (CC 2026-07-19, AF 2026-07-23, Cotizador, Flujo de Caja 2026-10-02) | `Visualizador Web/CLAUDE.md` |
| [Sistema Intercambio/](Sistema%20Intercambio/CLAUDE.md) | Implementado (2026-09-30), ampliado el 2026-10-01 con el plan de integración: catálogo de esquemas, procesador cada 15 min, Planilla de Ingreso, registro de proyectos | `Sistema Intercambio/CLAUDE.md` |

## Cómo se comunican las herramientas: carpeta de intercambio

Desde el 2026-09-30 las herramientas comparten información por una carpeta
de intercambio sincronizada por OneDrive. **Ya no vive en este repo**: por
pedido del usuario está en la biblioteca de SharePoint «Formulación de
proyectos - Documentos», en `.Herramientas formulación/Intercambio/`, para
que todos los colegas tengan acceso; ahí vive también el repositorio de las
formulaciones. Ubicación, alcance y cuidados en `Sistema Intercambio/CLAUDE.md`.
Usa un protocolo común (`Sistema Intercambio/intercambio.py`):
cada herramienta es dueña de sus datos, **pide** cambios a otra dejando un
mensaje en `buzon/` y **comparte** lo suyo en `publicado/`; el destinatario
decide, aplica con sus propias reglas y archiva el mensaje con su resultado.
Lo usa también el Formulador de proyectos (web, fuera de este repo), que
abre la carpeta desde el navegador sin iniciar sesión en nada.

Primer flujo: el Formulador envía los costos de una oferta adjudicada y
Análisis Financiero los aplica como costos proyectados en su `run` (ver
`Sistema Analisis Financiero/CLAUDE.md` § "Costos proyectados desde el
Formulador"). Desde el 2026-10-01 (plan de integración,
`../2026-09-30-plan-integracion-herramientas.md`) también viajan la venta,
los precios de referencia del Cotizador, la Planilla de Ingreso, las
cotizaciones de Sistema QUEMPIN y el sesgo del presupuesto; el formato de
cada cosa está en `Sistema Intercambio/esquemas/` y un **procesador** la
mantiene al día cada 15 minutos (`Sistema Intercambio/procesar.py`). La
clave común de proyecto es el **N° de la Planilla de Ingreso**. **Centro de Costos no se tocó** (ni su ingreso de facturas
desde SharePoint): sus costos reales llegan al Formulador por la publicación
de Análisis Financiero. **Si un módulo nuevo necesita pedir o compartir
datos con otra herramienta, usa este protocolo** en vez de leer o escribir
los archivos de otro módulo.

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

**Al agregar un módulo nuevo, engánchalo ahí** (así entró Flujo de Caja el
2026-10-02, después del procesador del intercambio), no dentro de
`auditor_centro_costos.main()`.

**Centro de Costos** registra el gasto por centro de costos: lee fotos de facturas/boletas depositadas en carpetas por proyecto más un `datos_extraidos.json` ya extraído (con desglose en ítems de línea), y mantiene `Centro de Costos.xlsx` (Master = 1 fila/documento con fórmulas, Detalle = 1 fila/ítem, una hoja de solo lectura por proyecto), de forma idempotente y con backup automático con timestamp antes de cada escritura. La arquitectura completa, el flujo del script, el esquema del JSON y el skill `/Registro_Centro_de_Costos` (comandos `status`/`run`) están documentados en su propio `CLAUDE.md` — léelo antes de tocar cualquier cosa bajo `Centro de Costos/`.

**Visualizador Web** es transversal a todos los módulos: cada uno tendrá, en su propia carpeta, una subcarpeta `Visualizador Web/` con un HTML publicado online (gráficos, tablas dinámicas, buscadores, filtros). El doc maestro compartido (marca, mandato de herramientas dinámicas, política de datos, hosting) vive en `Visualizador Web/CLAUDE.md` a nivel raíz; cada módulo tiene su propio `<Módulo>/Visualizador Web/CLAUDE.md` con el contenido específico a presentar. **Centro de Costos ya tiene una implementación real** (2026-07-19): `Centro de Costos/Visualizador Web/template.html` (estructura, versionada) + `build_visualizador.py` (export + build, corrible vía `driver.py visualizador` del skill `/Registro_Centro_de_Costos`) generan un `build/index.html` autocontenido con los datos incrustados, publicado en GitHub Pages (único canal desde la migración del 2026-08-05 — los Claude Artifacts privados que se usaban antes ya no se actualizan, pedido explícito del usuario 2026-08-19). **Los cuatro módulos tienen su visualizador real** (Centro de Costos 2026-07-19, Análisis Financiero 2026-07-23, Cotizador Historico, Flujo de Caja 2026-10-02). Ver el spec original en `docs/specs/2026-07-19-visualizador-web-design.md`.

**Los tres se regeneran en disco, y los tres tienen ahora su propio skill "run + publicar" en un solo paso** (2026-08-05): `/Actualizar_CC` (Centro de Costos), `/Actualizar_AF` (Análisis Financiero), `/Actualizar_Cotizador` (Cotizador Histórico) — cada uno corre su registrador/visualizador y republica el dashboard existente en GitHub Pages (URL estructural fija, nunca un link nuevo). Úsalos cuando el usuario nombra un solo módulo; para los tres a la vez sigue siendo `/Actualizar_Finanzas` (que no publica por sí solo — deja los 3 builds listos en disco y reporta cuáles se regeneraron, la publicación de cada uno la hace el agente siguiendo la sección de arriba de ese skill). **El procedimiento común de los tres vive una sola vez** en [`docs/actualizar-un-modulo.md`](docs/actualizar-un-modulo.md) (por qué existen, los cuatro pasos, cuándo no aplican); cada `SKILL.md` solo agrega lo propio de su módulo. Antes los tres repetían ese texto casi palabra por palabra, y había que acordarse de sincronizarlos a mano.

**Análisis Financiero** es distinto a los demás: no es solo un pipeline de registro, es un rol consultivo — actúa como analista financiero experto (evalúa proyectos, propone/depura KPIs, decide cómo presentar la información, cruza todos los módulos), sobre un Excel (`Análisis de Proyectos.xlsx`) que consolida costos reales de Centro de Costos contra ventas y proyecciones manuales por proyecto. **Reorganizado 2026-07-21**: `Análisis Financiero/` contiene únicamente el Excel de trabajo; el código, los tests y el skill viven en la carpeta hermana `Sistema Analisis Financiero/` (ver su `CLAUDE.md` para el diseño completo). Implementado y encadenado al `run` de Centro de Costos (PASO 12d) — ver `Sistema Analisis Financiero/CLAUDE.md`. Desde 2026-07-23 también tiene un Visualizador Web propio (`Sistema Analisis Financiero/Visualizador Web/`, mismo patrón que Centro de Costos: proyectos completos con sus KPIs + Clientes/CLTV, excluyendo del cálculo cualquier proyecto sin información manual completa).

**Lo que no tiene decisión editorial se genera, no se redacta** (2026-09-24,
reportes PDF de Análisis Financiero). La página 1 de esos reportes lleva por
estándar *todos* los KPIs de la entidad "sin selección editorial" — o sea, no
tiene ninguna decisión — y aun así la escribía el agente a mano, en HTML, una
vez por reporte: 20 entidades, 20 veces el mismo panel, y dos reportes de
sesiones distintas nunca quedaban idénticos. Ahora la arma
`Sistema Analisis Financiero/Reportes/panel.py` y el agente escribe solo el
análisis. Tres cosas que sirven para cualquier módulo que produzca
documentos:

- **Si el formato está fijo por un estándar escrito, ese estándar es código
  que todavía no se escribió.** El mismo texto que describía cómo armar la
  página a mano se borró del `SKILL.md` (194 → 115 líneas) al existir el
  generador.
- **Un color sin dirección no informa.** El criterio anterior pintaba del
  mismo naranjo un margen de 61% y un sobrecosto de +40%: había que leer el
  número igual. El semáforo (`brand.estado_kpi`) reusa los colores y los
  cortes ya calibrados del dashboard en vez de definir otros.
- **Dale al que redacta los números ya comparados.** `driver.py contexto`
  entrega ~20 líneas con la mediana de la cartera y el sesgo por categoría al
  lado de cada cifra del proyecto; antes había que volcar los dicts crudos y
  escribir Python suelto para obtener lo mismo.

**Cotizador Histórico tiene su propia taxonomía de productos** (reestructurada
2026-09-08 y 2026-09-22): clasifica cada compra en categoría > familia > tipo,
más los atributos del producto, y la hoja (`tipo + material + medida`) es la
unidad de comparación de precios — una cañería de cobre de 1/2" nunca se
promedia con una de 2". Vive en `Cotizador Historico/Sistema/taxonomia.py` +
`catalogo_taxonomia.py` (Python, testeada, compartida por Chile y Perú y por la
consulta de consola y el dashboard). **Antes vivía en JavaScript dentro de cada
`template.html`**, duplicada por país y ya divergente — mismo tipo de hueco que
la divergencia del KPI "Nota del Proyecto" de 2026-07-28. Si agregas un módulo
que necesite clasificar ítems, reutiliza ese motor en vez de escribir otro.
Auditoría:
`py -3.14 "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" categorias`.

**Un producto no es su forma: es qué es, de qué está hecho y cuánto mide**
(pedido del usuario 2026-09-22, motor en `Cotizador Historico/Sistema/
atributos.py` + `catalogo_atributos.py`). El material, la terminación, cada
dimensión **con su rol** (espesor, ancho, largo, diámetro, diámetro de salida)
y las especificaciones técnicas (SCH, PN, NPT, norma, grado) son atributos
independientes, con su confianza. Tres cosas que aprendió este módulo y sirven
para cualquier otro que clasifique cosas:

- **Una palabra de material nunca puede ser el término que define el tipo de
  producto.** Mientras `policarbonato` fue un término de la regla "Plancha",
  una plancha de policarbonato quedó sin material y dentro de "Perfilería y
  Maderas", junto al pino.
- **El mismo material cambia de significado según dónde aparece**: "disco de
  corte **para** acero inoxidable" no es de inoxidable, y "mazo de goma **con
  mango de** acero" es de goma. Sin rol, el material es una palabra suelta.
- **Un número solo significa algo dentro de una familia**: "40x2" es un perfil
  de 40 mm de lado y 2 de espesor; "2x6", una escuadría de pino en pulgadas.
  Leerlos con una sola regla genérica hacía que tres barras PEX de 16, 20 y 32
  mm compartieran hoja (la única medida leída era el largo de la barra).

Si un módulo nuevo necesita describir materiales, reutiliza ese motor;
`driver.py atributos` lista lo que todavía no sabe interpretar y `driver.py
evaluacion` dice si un cambio mejoró o empeoró.

**Un valor y su escritura son dos cosas distintas** (2026-09-23,
`Cotizador Historico/Sistema/presentacion.py`). "20000mm" y "20 m" son la
misma extensión eléctrica: la primera es la que hace falta para *comparar*
medidas entre sí, la segunda es la única que un comprador reconoce. Mientras
vivieron en el mismo campo, el catálogo mostraba la escritura de la máquina.
Dos cosas que dejó separarlas, y valen para cualquier módulo que muestre
datos que también indexa:

- **La cadena que se muestra no puede ser la que se compara.** Al pasar la
  hoja a la escritura legible, "Reducción de Cobre 3/4x1/2"" quedó
  `3/4" x 1/2"` y la consulta `reduccion cobre 3/4 x 1/2` —que el buscador
  junta en un solo término `3/4x1/2`— dejó de encontrarla. Se ve en la
  evaluación (P@1 0,982 → 0,955), no mirando la pantalla.
- **La escritura correcta se puede leer de los propios datos.** El mismo
  proveedor llega como "Quilpue" y "Quilpué", y la misma marca como "ANWO" y
  "Anwo". En vez de una lista a mano, gana la forma con tilde y después la
  más frecuente del catálogo: determinista, explicable y no envejece cuando
  entra un proveedor nuevo.

**El buscador del Cotizador es otro motor reutilizable** (reescrito
2026-09-16): `Cotizador Historico/Sistema/busqueda.py` +
`catalogo_busqueda.py` resuelven tildes, plurales, palabras vacías,
sinónimos, errores de tipeo, códigos y **medidas equivalentes** (`2"` =
`2 pulgadas` = `DN50`, pero nunca `1/2"`), y rankean por cobertura de la
consulta y peso del campo. Si agregas un módulo que necesite buscar ítems,
reutilízalo en vez de escribir otro `difflib`.

Dos lecciones que dejó medirlo, y que valen para cualquier módulo:

- **Un buscador que devuelve resultados no es un buscador que ordena.** El
  anterior daba `1.0` a cualquier ítem que compartiera una palabra con la
  consulta: sobre los datos reales, 41 válvulas empatadas y el orden lo
  decidía el Excel. Eso no se ve mirando una consulta suelta, solo aparece
  con un set fijo de consultas y una respuesta esperada
  (`driver.py benchmark`: Success@5 0,81 → 1,00; MRR 0,69 → 1,00).
- **Un caso de prueba cuya respuesta no existe en los datos no mide el
  sistema, mide a quien escribió el test.** Dos casos del benchmark
  esperaban encontrar un esmeril; el catálogo real no tiene ninguno.

Cuando un módulo tenga que correr la misma lógica en Python y en el
navegador, el patrón que quedó es: calcular en Python todo lo que dependa de
los datos, mandar las tablas en el snapshot, escribir en JavaScript solo lo
que dependa de lo que el usuario teclea, y **clavar la paridad con un test
que corra las dos implementaciones y compare** (ver
`Cotizador Historico/Sistema/tests/test_paridad_busqueda_js.py`). El archivo
JavaScript es **uno solo** para Chile y Perú, inyectado por cada build.

Se espera que los módulos futuros (ej. Flujo de Caja) consuman datos que ya producen módulos anteriores (ej. totales por proyecto de Centro de Costos) en vez de construirse de forma aislada — revisa qué datos ya calculan los módulos existentes antes de duplicar esa lógica en uno nuevo.

## Al trabajar en este directorio

- **Datos financieros reales, excluidos de git**: todo lo que hay bajo cada módulo (JSON extraído, fotos de documentos fuente, los libros `.xlsx`, los reportes PDF) es información financiera real de la empresa — montos, proveedores, números de documentos tributarios. Trátalo como sensible. El `.gitignore` de la raíz los excluye **por patrón** (`*.xlsx`, `**/datos_extraidos*.json`, `**/backup_*/`, `Análisis Financiero/Reportes/`, …), no por ruta exacta: una auditoría del 2026-07-28 encontró el libro maestro y `datos_extraidos.json` expuestos dentro de `Centro de Costos/backup_centro_costos_original/` justamente porque las reglas viejas apuntaban a rutas puntuales. **Si agregas una fuente de datos nueva, agrégala como patrón** y verifica con `git check-ignore -v <ruta>` antes de commitear.
- **Esta es una carpeta de OneDrive sincronizada**, potencialmente editada por más de una persona/dispositivo en paralelo. Antes de sobrescribir cualquier `.xlsx`, considera que puede tener ediciones manuales recientes hechas fuera de un script.
- **Ubicación duplicada — resuelta el 2026-07-16**: `Finanzas QUEMPIN/Centro de Costos/` es ahora la única ubicación canónica del módulo (rutas de `auditor_centro_costos.py` recalculadas desde `Path(__file__)`, ya no hardcodeadas a otra carpeta). Existen otras dos copias con datos desactualizados/parciales que **no** hay que editar ni usar como fuente de verdad: `OneDrive - QUEMPIN SPA/Sitio de comunicación - Centro de costos/` (quedó con una estructura simple antigua) y `OneDrive - QUEMPIN SPA/Plantillas/` (ahí corrió un pipeline más avanzado — `build.py`/`rename.py`/etc. — que se perdió antes de integrarse aquí; su resultado final fue la base para reconstruir la estructura actual, ver `Centro de Costos/CLAUDE.md`). Si en el futuro aparece contenido nuevo en cualquiera de esas dos carpetas, confírmalo con el usuario antes de asumir que reemplaza lo que hay aquí.
