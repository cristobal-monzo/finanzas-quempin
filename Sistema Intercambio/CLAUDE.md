# CLAUDE.md — Sistema Intercambio

## Qué es / por qué

Protocolo común para que las herramientas de QUEMPIN compartan información
sin depender unas de otras. Pedido del usuario (2026-09-30): que Centro de
Costos, Análisis Financiero y el Formulador de proyectos «se comuniquen o
compartan información entre sí», sin afectar el ingreso de facturas desde
SharePoint. El primer uso: **el Formulador actualiza los costos proyectados
del Análisis Financiero.**

No es un servidor ni una base de datos. Es una carpeta sincronizada por
OneDrive con archivos JSON de formato común (esquema `quempin.intercambio/1`).

**Dónde está (desde el 2026-09-30, pedido explícito del usuario):** en la
biblioteca de SharePoint «Formulación de proyectos - Documentos», en
`.Herramientas formulación/Intercambio/` (en el disco, `.HERRAMIENTAS
FORMULACIÓN`). Antes estaba en `Finanzas QUEMPIN/Intercambio/`. Se movió para
que todos los colegas tengan acceso, y ahí vive también el repositorio de las
formulaciones compartidas. El usuario decidió sabiendo que quien entra a esa
biblioteca ve también `publicado/analisis-financiero.json`, con los costos
proyectados y reales por proyecto.

- Análisis Financiero la ubica con `presupuestos_formulador.ubicar_intercambio()`.
  Sube desde este repo hasta encontrar la biblioteca y no distingue
  mayúsculas. La variable `QUEMPIN_INTERCAMBIO` la fija a mano. Si la
  biblioteca no está sincronizada en el equipo, el intercambio queda inactivo
  con un aviso: nunca se crea una biblioteca falsa ni se vuelve a la carpeta
  antigua.
- «Oculta» solo en parte. El atributo *oculto* de Windows se marcó en el PC
  del usuario, pero OneDrive no lo lleva a los demás equipos, y SharePoint
  muestra la carpeta igual. El modo SharePoint del Formulador ignora las
  carpetas que empiezan con punto, así que no la lista como oferta.

```
Formulación de proyectos - Documentos/.Herramientas formulación/Intercambio/
├── intercambio.json     manifiesto: así se reconoce la carpeta correcta
├── LEEME.md             explicación para personas (vive solo aquí, no en git)
├── buzon/               mensajes que una herramienta le envía a otra
├── procesado/AAAA-MM/   mensajes ya atendidos, con su resultado
└── publicado/           lo que cada herramienta publica para las demás
    ├── analisis-financiero.json
    └── formulador/      repositorio de formulaciones: un archivo por proyecto
```

El Formulador (web, GitHub Pages) abre esa carpeta con la API de acceso a
archivos del navegador (Chrome/Edge de escritorio), sin iniciar sesión en
nada y sin pasar por SharePoint. Los scripts de Python la leen como cualquier
carpeta.

## Reglas del protocolo

- **Cada herramienta es dueña de sus datos** y nunca escribe los archivos de
  otra. Para pedir un cambio deja un mensaje en `buzon/`; el dueño decide si
  lo aplica y cómo (con sus propias validaciones, respaldos y reglas).
- **Un mensaje se atiende una sola vez**: el destinatario lo mueve a
  `procesado/AAAA-MM/` con `resultado = {estado, fecha, detalle, ...}`.
  Estados finales: `aplicado`, `sin-cambios`, `reemplazado`, `rechazado`,
  `descartado`. Si no puede decidir solo, lo deja en el buzón (pendiente) y
  lo informa.
- **Lo publicado se reemplaza completo** en cada corrida, con escritura
  atómica (temporal + `os.replace`): nunca queda un JSON a medio escribir si
  OneDrive sincroniza en ese momento.
- Sobre común de un mensaje: `esquema`, `id` (6–64 letras/números/-/_),
  `tipo`, `destino`, `origen {herramienta, enviado, usuario?}`. El contenido
  propio de cada tipo lo valida su destinatario.

`intercambio.py` implementa solo el sobre (leer y validar el buzón, archivar
con resultado, publicar, leer publicaciones). No conoce ningún tipo de
mensaje: qué hace cada destinatario vive en su módulo.

## El catálogo: `esquemas/` (2026-10-01)

Cada tipo de mensaje y cada publicación tiene su **JSON Schema** en
`esquemas/mensajes/<tipo>.json` y `esquemas/publicaciones/<nombre>.json`
(más `sobre-mensaje.json` y `sobre-publicacion.json`), con ejemplos válidos e
inválidos en `esquemas/ejemplos/`. Es la **fuente única** del formato: la
tabla de abajo y los textos del Formulador lo resumen, no lo definen.

- `esquemas.py` valida (subconjunto de JSON Schema, sin dependencias);
  `esquemas.js` es su gemelo para el navegador. `tests/test_esquemas.py`
  corre los dos sobre los mismos ejemplos y exige el mismo resultado, y
  falla si un esquema usa una palabra que los validadores no entienden.
- `esquemas.paquete()` es el catálogo completo en un objeto: el procesador lo
  deja en la carpeta como `esquemas.json`, para que una herramienta de otro
  repositorio (Sistema QUEMPIN, el Formulador) valide con el catálogo
  vigente sin copiarlo.
- **Copias en otros repositorios**: Sistema QUEMPIN lleva copias textuales de
  `intercambio.py`, `ubicacion.py` y `esquemas.py` (su
  `tests/test_copias_intercambio.py` avisa si se desfasan), y el Formulador,
  de `esquemas.js`. Si cambias uno de estos archivos, vuelve a copiarlo.
- **Agregar un tipo**: su esquema + ejemplos (válido e inválido) + una fila en
  la tabla de abajo. El destinatario sigue validando sus propias reglas de
  negocio; el esquema solo asegura la forma.

## Tipos de mensaje y publicaciones en uso

| Nombre | Quién escribe | Quién lee | Dónde se implementa |
|---|---|---|---|
| mensaje `presupuesto-proyecto` → `analisis-financiero` | Formulador (`js/intercambio.js`) | Análisis Financiero | `Sistema Analisis Financiero/Sistema/presupuestos_formulador.py` |
| `publicado/analisis-financiero.json` | Análisis Financiero (fin de cada `run`, o `driver.py intercambio publicar`) | Formulador; Flujo de Caja (`porEjecutar` y `cierre`) | mismo archivo |
| `publicado/formulador/<uid>.json`: un archivo por presupuesto, el repositorio de formulaciones, con `historia`, `resumen` (costo, precio, margen y `costosAF`, calculados por el Formulador) y `datos` | Formulador de cada equipo (`js/compartida.js`, 2026-09-30); también `formulaciones.incorporar_buzon()` con las entregas por archivo | Formulador de los demás equipos; Claude (`formulaciones.py`, driver AF `formulaciones`) | `Sistema Intercambio/formulaciones.py` |
| mensaje `formulacion` → `formulador`: un presupuesto entregado por archivo desde un navegador sin acceso a la carpeta | Formulador («Descargar para el equipo»; se deja a mano en `buzon/`) | `formulaciones.incorporar_buzon()` (procesador, y paso 0 del `run` de `/Actualizar_Finanzas`), con las mismas reglas de quién gana del Formulador; en conflicto queda como copia | `Sistema Intercambio/formulaciones.py` |
| mensaje `venta-proyecto` → `analisis-financiero`: monto de venta sin IVA de un proyecto adjudicado (de la cotización emitida, o del precio neto del Formulador) | Formulador | Análisis Financiero, por el **mismo** canal y garantías que `presupuesto-proyecto` | `presupuestos_formulador.py` |
| mensaje `datos-proyecto` → `analisis-financiero` (2026-10-02): valores manuales de un proyecto (% avance, fechas, venta, los 4 proyectados, mano de obra real, N° de requerimiento), uno por proyecto; puede crear el proyecto o dejar una celda vacía | pestaña «Ingresar datos» del tablero de Análisis Financiero (`Visualizador Web/ingreso.js`), o un archivo descargado de ella que se deja a mano en `buzon/` (`driver.py intercambio cargar`) | Análisis Financiero, por el mismo canal y la misma regla de lo visto; varios al mismo proyecto se aplican todos, en orden, y quedan como valor manual (sin nota) | `presupuestos_formulador.py` |
| mensaje `borrador-cotizacion` → `sistema-quempin`: una cotización prellenada por partida | Formulador | Sistema QUEMPIN (aviso arriba de «Nueva Cotización» y botón «Borradores del Formulador»: una persona la revisa y la emite; al emitir se archiva con el folio) | `Sistema QUEMPIN/app/integraciones/ecosistema.py` |
| mensaje `registro-documento` → `sistema-quempin`: registrar en el Control de Documentos la evaluación de costos (81) del Formulador | Formulador | Sistema QUEMPIN (la app cada minuto, y el procesador); si el folio ya se usó, asigna el siguiente | mismo archivo |
| mensaje `actualizar-requerimiento` → `planilla-requerimientos`: estado y valor ofertado o adjudicado | Formulador | **nadie lo escribe**: una persona lo pasa a la Planilla y el procesador lo cierra cuando ya está (`/Sugerencias_Requerimientos`) | `Sistema Intercambio/requerimientos.py` |
| `publicado/requerimientos.json`: la Planilla de Ingreso, de solo lectura | procesador (cuando cambia la planilla) | Formulador, Sistema QUEMPIN, registro de proyectos, Flujo de Caja | `requerimientos.py` |
| `publicado/precios-referencia.json`: precio reajustado por UF por hoja, sin proveedores ni documentos | Cotizador Histórico (`driver.py precios`, y tras cada `visualizador`); procesador cuando cambia la foto del tablero | Formulador | `Cotizador Historico/Sistema/precios_referencia.py` |
| `publicado/documentos-comerciales.json`, `contrapartes.json`, `folios.json` | Sistema QUEMPIN (al emitir/editar/eliminar en el equipo donde se hizo, y el procesador) | Formulador, Análisis Financiero, registro de proyectos, Flujo de Caja | `Sistema QUEMPIN/app/integraciones/ecosistema.py` |
| `publicado/licitaciones.json` (2026-10-13): resultado en Mercado Público de cada requerimiento con código, quién ganó y por cuánto, OC emitidas a QUEMPIN y lo que debe revisar una persona; también deja mensajes `actualizar-requerimiento` con `fuente.herramienta = mercado-publico` y `fuente.motivo` | procesador (`mercado_publico.py`, cada vuelta) | Formulador (Seguimiento, «Oferta y adjudicación»), bandeja de pendientes, `/Sugerencias_Requerimientos` | `Sistema Intercambio/mercado_publico.py` |
| `publicado/oportunidades.json` (2026-10-13): licitaciones publicadas del rubro con su evaluación previa (8 criterios de 0 a 100, ponderado, categoría, motivos, a favor / en contra, parecidas de la Planilla, precedentes de mercado y las reglas que dependen de la fecha) | procesador (`oportunidades.py`, solo con `enProcesador` en su configuración) | otras herramientas; el equipo la mira en el tablero de GitHub Pages (`oportunidades/`, con contraseña), que arma `Visualizador Web/build_visualizador.py` con la misma evaluación | `Sistema Intercambio/oportunidades.py` |
| `publicado/proyectos.json`: cruce `req` ↔ TAG ↔ formulaciones ↔ cotizaciones/OC ↔ carpetas | procesador | Formulador, Claude | `Sistema Intercambio/proyectos.py` |
| `publicado/estado.json`: el pulso (última vuelta del procesador, pendientes por destino, cuán nueva es cada publicación) | procesador | Formulador («al día hace 6 min», y aviso rojo en la lista si está detenido) y la pestaña «Ingresar datos» del tablero AF, los dos con `pulso.js` | `Sistema Intercambio/procesar.py` |
| `esquemas.json` (raíz de la carpeta): el catálogo completo | procesador | Sistema QUEMPIN, Formulador | `esquemas.paquete()` |

`intercambio.enviar(raiz, mensaje)` deja un mensaje en el buzón con el mismo
nombre que usa el Formulador (`nombre_mensaje`, `nuevo_id`). Así lo usa el
driver AF `formulaciones cargar` para dejar un `presupuesto-proyecto` a
partir de un presupuesto adjudicado del repositorio.

Centro de Costos **no se modificó**: sus costos reales llegan al Formulador a
través de la publicación del Análisis Financiero (que ya los lee de su
snapshot). El ingreso de facturas desde SharePoint sigue igual.

Flujo de Caja **no publica nada aquí** (decidido 2026-10-02): lee
`requerimientos`, `documentos-comerciales` y `analisis-financiero`, pero su
resultado es la caja de la empresa y esta carpeta la ve toda la biblioteca de
Formulación. Sale solo a su Excel y a su tablero con contraseña.

## El procesador (`procesar.py`, cada 2 horas)

Antes el lado Python solo se movía en el `run` de `/Actualizar_Finanzas`
(dom/mar/jue a las 23:00, o a la mañana siguiente con el PC apagado): un
envío hecho un miércoles se aplicaba el viernes. `procesar.py` corre con su
propia tarea programada («Procesar intercambio QUEMPIN», `tarea_procesador.cmd`)
y al final de cada `run` de `/Actualizar_Finanzas` (con `--forzar`). Hace, en
orden y **solo si algo cambió** desde la vuelta anterior (firmas en
`procesador_estado.json`, gitignoreado): `esquemas.json`; entregas de
formulaciones por archivo; requerimientos y cierre de sugerencias; Análisis
Financiero (`run` solo si llegaron envíos que no se intentaron, de cualquiera
de los tipos cuyo esquema declara `destino: analisis-financiero` -- desde el
2026-10-02 se leen del catálogo, no de una lista del procesador; si no, y
cambió Centro de Costos o el libro, solo `intercambio publicar`); precios de
referencia; Sistema QUEMPIN (`python -m app.integraciones.ecosistema
procesar` con su Python 3.11); Mercado Público (este paso consulta siempre:
lo que cambia está en la API, no en la carpeta); `proyectos.json`, y
`estado.json`.

- **Un paso que falla no frena a los demás** y queda en `estado.json` y en
  `logs/procesador_AAAA-MM.log` (una línea por vuelta).
- **Un envío que queda pendiente no dispara un `run` en cada vuelta**: se
  reintenta cuando cambia algo (un envío nuevo, el libro, Centro de Costos).
- Los módulos de Finanzas corren **en su propio proceso** (archivos
  homónimos, igual que en `/Actualizar_Finanzas`); un candado
  (`.procesador.lock`, vence a los 30 min) evita dos vueltas a la vez.
- Nunca escribe la Planilla de Ingreso ni publica en GitHub.
- **Si deja de correr, las herramientas lo dicen** (2026-10-08). La tarea
  estuvo deshabilitada del 05-10 al 08-10 sin que nadie lo notara: los envíos
  al AF esperaron hasta 28 horas. `pulso.js` (una sola copia de la regla, que
  el Formulador lleva textual y el tablero AF inserta en su build) cuenta las
  horas hábiles (lunes a viernes, 08:30–19:00, hora del navegador) desde la
  última vuelta: con más de 4 (dos vueltas perdidas) el Formulador pone un
  aviso rojo en su lista de proyectos y en Seguimiento, y la pestaña «Ingresar
  datos» del AF otro arriba de sus envíos. Las noches y los fines de semana no
  cuentan: con el PC apagado el procesador espera, y eso no es una falla. La
  tarea corre también a batería desde ese día.

## Monitor de Mercado Público (`mercado_publico.py`, 2026-10-13)

El 97 % de los requerimientos viene de Mercado Público y su resultado se
pasaba a mano (análisis del 2026-10-08, §6 punto 1). En cada vuelta del
procesador, con la API pública de ChileCompra:

1. Consulta las licitaciones de la Planilla con código en «ID o Referencia»
   que esperan resultado (Ofertado, Evaluación); después barre las órdenes
   de compra emitidas a QUEMPIN (proveedor 1717812, 60 días hacia atrás la
   primera vez; después solo hoy y ayer), y por último verifica una vez las
   ya cerradas (de nuevo al mes, por si se revoca).
2. Sugiere a la Planilla **solo lo que Mercado Público prueba** (`decidir`):
   - ganada, o con OC: «Adjudicado» y el valor con IVA. Usa el total de las OC
     si suman el neto adjudicado; si no, el neto del acta más 19 %. Nunca pisa
     un valor ya escrito.
   - adjudicada a otro, desierta o revocada, con la Planilla en «Ofertado»:
     «No adjudicado».
   - Lo dudoso va a `revisar` y a la bandeja, no al buzón. Por ejemplo, la
     Planilla dice «Adjudicado» y Mercado Público dice otro ganador, o una
     licitación resuelta sigue en «Evaluación» (no se sabe si se ofertó).
   - Una sugerencia no se repite: ni si ya hay una igual en el buzón (de
     cualquier herramienta), ni si alguien la descartó (claves en la caché).
3. Las Compras Ágiles (COT) no existen como licitación en la API: se sabe que
   se ganaron solo por la OC, que nombra la COT en su título. Las OC que no
   calzan con ningún requerimiento van a la bandeja.

**Seguridad:**
- El ticket es personal (ClaveÚnica). Va cifrado con DPAPI en
  `%LOCALAPPDATA%\QUEMPIN\mercado-publico.ticket`, fuera de OneDrive y del
  repo. Solo el mismo usuario de Windows lo descifra, y la tarea programada
  corre como ese usuario.
- Se ingresa con `py -3.14 mercado_publico.py configurar`, sin eco y nunca
  por argumento. Antes de guardarlo se prueba contra la API.
- `QUEMPIN_MP_TICKET` lo reemplaza en pruebas o en otro equipo.
- Se censura en todo mensaje de error.
- Solo HTTPS a api.mercadopublico.cl, con tiempo límite y tope de 5 MB por
  respuesta. Los códigos se validan con regex antes de armar la URL.
- Los textos de la API se limpian de caracteres de control y se acortan.
- Los enlaces se limitan a https://www.mercadopublico.cl.
- No se publican nombres ni contactos de funcionarios del comprador.
- El Formulador vuelve a validar el enlace y escapa todo: la carpeta la
  puede editar cualquiera con acceso a la biblioteca.

**Límites de la API (medido el 2026-10-13):**
- Rechaza consultas seguidas con el error 10500: 2 s entre llamadas y
  reintento con espera creciente.
- El 203 es ticket inválido: corta la vuelta y la bandeja lo muestra.
- Tope de 120 llamadas por vuelta (unos 4 minutos). La primera vez necesitó
  dos vueltas.

`py -3.14 mercado_publico.py status` dice qué sugeriría sin escribir en la
carpeta. La caché (`mercado_publico_estado.json`, gitignoreada) solo lleva
datos públicos. Las pruebas cortan la red y el ticket en `tests/conftest.py`:
ninguna consulta la API real.

## Oportunidades de negocio (`oportunidades.py`, 2026-10-13)

Pedido del usuario: una herramienta que, con el historial de Mercado
Público, identifique buenas oportunidades y haga una **evaluación previa**
por rubro, monto, dificultad, visita técnica y tiempos de ejecución. Antes se
revisaba Mercado Público a mano, y de 305 requerimientos de la Planilla 202
terminaron descartados.

En cada vuelta (con el mismo cliente y ticket del monitor):

1. **Busca**: el listado de licitaciones publicadas (`estado=activas`, unas
   5.000, una consulta). Después aplica un **prefiltro por el nombre**: frases
   del rubro (`nucleo`, `afines`), o mucho parecido (≥ 0,6 y al menos 2
   palabras en común) con un título que QUEMPIN ofertó. Con una palabra de
   `excluir` en el nombre queda fuera sin gastar la ficha. Solo para las
   candidatas pide la ficha, que se guarda en caché 3 días. El 2026-10-13
   quedaron 46 a 48 candidatas de 4.932.
2. **Historial de mercado**, de a poco y solo con las consultas que sobran
   (completarlo no cuenta como vuelta incompleta). Lee el listado de unos
   días hacia atrás (una consulta por día, hasta 365) y pide la ficha de las
   adjudicadas del rubro: ganador, monto neto y oferentes. Se suma lo que el
   monitor ya trajo de las licitaciones de la Planilla. Con eso salen los
   competidores y los «precedentes» de cada comprador.
3. **Evalúa** con 8 criterios de 0 a 100, cada uno con su motivo: rubro,
   monto, dificultad, visita a terreno, ubicación, comprador y competencia,
   plazo para ofertar y tiempo de ejecución. Calcula el ponderado y la
   categoría.
   - **Descartan solos**: cierra en menos de un día; visita **obligatoria** ya
     pasada; palabra de `excluir` en el nombre; sin palabras del rubro ni
     parecido; monto sobre un `maximo` puesto a mano. El máximo que sale de la
     historia solo orienta, porque QUEMPIN ya ha ofertado licitaciones varias veces mayores que lo habitual.
   - **Tope por rubro**: con rubro < 40 la categoría no pasa de «Baja», con
     < 50 de «Evaluar» y con < 70 de «Buena». El tablero repite esta regla al
     mover los pesos: si cambias una, cambia la otra (hay una prueba en
     Chromium, `tests/test_tablero_oportunidades.py`).
   - Se ordena por categoría y después por puntaje: una «Buena» por tope no
     pasa delante de una «Prioritaria».
4. **Publica** `oportunidades.json` (paso del procesador, si está activo).
   Para cada licitación deja también `aFavor` / `enContra` (frases cortas
   según hacia dónde empuja cada criterio), `descartarFijo` (los motivos que
   no dependen de la fecha) y, para todas, `reglas` (tramos del plazo y la
   visita ya pasada).
5. **El tablero** (2026-10-13, pedido del usuario: «que sea más claro cuáles
   son las oportunidades más relevantes» y publicado «con contraseña, con la
   estética del resto»): `Visualizador Web/` de esta carpeta, publicado en
   `oportunidades/` de gh-pages como los demás tableros, con la pestaña en la
   navegación de los 7 y la tarjeta en el hub. Ver su `CLAUDE.md`. Reemplazó a
   la página suelta que se dejaba junto a la Planilla: un solo lugar, cifrado.

**Decisiones medidas contra los datos reales (2026-10-13):**
- **No se corta a raíces de 6 letras**, solo se pasa a singular. Con el corte,
  «hidrogeológico» era «hidrógeno».
- Para decir que dos títulos se parecen, las palabras genéricas no cuentan
  (`_GENERICAS`: mantención, revisión, servicio, sistema, agua, meses, años,
  tipos de comprador y ciudades). Tampoco las que salen en menos de 3 títulos
  de la Planilla (lugares, siglas).
- Las palabras desconocidas sí cuentan en la norma y **diluyen** el
  parecido.
- Sin palabras del rubro hacen falta **2 palabras en común**. Con una sola
  («piscina», «carabineros», «meses») pasaban 376 de 4.932 publicadas, casi
  todas ajenas. Antes de estas reglas, «Revisión de prótesis» y
  «radiotaxis» salían prioritarias.
- El parecido se busca **solo por el nombre**, porque la Planilla guarda
  títulos. La categoría de los ítems no entra al rubro: la de climatización
  junta calefacción con aire acondicionado.
- Las frases del rubro que aparecen **solo en la descripción** valen menos:
  núcleo 60 en vez de 85, afín 35 en vez de 55. «Guardavidas para la piscina
  temperada» no es climatizar una piscina.
- «Varios recintos» se busca en plural, sin pasar a singular: «al
  establecimiento» es uno solo.
- La historia pesa un 25 % del rubro. Muchos descartes de calderas fueron por
  distancia o plazo, y eso ya lo miden otros criterios.
- Sin ficha (tope de consultas), visita, dificultad y duración quedan en 50,
  nunca en 100. La visita sale de la ficha de las bases, no de la API (ver
  «La visita en el tablero», más abajo).

**Compras ágiles (2026-10-14, pedido del usuario: «licitaciones y compras
ágiles»)**: la API de licitaciones no las expone. Las trae `compra_agil.py`
desde la **API Compra Ágil v2** de ChileCompra (mayo 2026, mismo ticket, que
va en un header; cuota diaria con error 429).
- No hay listado por rubro: se hace **una búsqueda por palabra**
  (`compraAgil.busquedas`). La API distingue tildes y plurales («calderas» trae
  3, «caldera» 26), y una búsqueda muy amplia («gas») termina en 504.
- Pasan el mismo prefiltro y la misma evaluación que una licitación, con tres
  diferencias. El monto se compara con las compras ágiles que QUEMPIN cotizó
  (`rango_ca`). Los tramos de plazo están en horas (`compraAgil.plazoOferta`,
  menos de 6 horas descarta). Y la visita se lee en la descripción, porque la
  ficha no tiene ese campo.
- La ficha se vuelve a pedir solo si la compra cambió (`fecha_ultimo_cambio`).
  Una búsqueda que falla no borra lo que seguía abierto.
- **Es lenta.** El 2026-10-15 tardaba 15 a 20 s por búsqueda, y «caldera»
  daba 504 a los 30 s aunque se acotara por fecha o por tamaño de página. Por
  eso cada vuelta tiene un **presupuesto de tiempo** (`limiteMinutos`, 8).
  Las búsquedas van en orden de importancia (14 palabras). Lo que no alcanza
  sigue en la próxima vuelta, y las licitaciones se publican igual. Sin ese
  tope, la tarea diaria pasó 15 minutos atascada y habría chocado con su
  límite de 45.
- Las búsquedas usan como máximo el 60 % de ese tiempo
  (`fraccionTiempoBusquedas`); el resto queda para las fichas. En la primera
  vuelta real las búsquedas se comieron todo y ninguna compra ágil tuvo
  ficha.
- Sin ficha, la evaluación por el nombre usa la región, el monto y el
  organismo que trae el listado. Igual queda marcada «solo por el nombre», y
  sin ficha nunca se manda correo.
- El enlace va a la ficha pública `https://buscador.mercadopublico.cl/ficha?code=…`
  (el esquema acepta `www` y `buscador`).

**Calibración (2026-10-14, pedido del usuario: «mejora la precisión de las
notas»)**: `calibrar_oportunidades.py` evalúa cada requerimiento de la
Planilla con código como si se viera al día siguiente de publicado (una
compra ágil, a las 3 horas). Lo evalúa sin sí mismo en la historia y lo
compara con lo que decidió QUEMPIN: ofertó o descartó. `descargar` baja las
fichas una vez a `oportunidades_estado_calibracion.json` (gitignoreado);
`medir` da el AUC y la tasa de oferta por tramo de nota, sin consultar la API.
Lo que se encontró y se cambió:
- **La etiqueta tiene mucho ruido.** De los N° 100 a 249 se ofertó entre el
  8 y el 26 %; desde el N° 250, el 80 %. Con «evaluador» vacío se ofertó 1 de
  109. Entre los casos que alguien sí evaluó, **ningún criterio predice la
  decisión** (AUC ≈ 0,5): ahí pesan la capacidad del momento, las garantías y
  los requisitos de las bases. La nota sirve para separar lo que es del
  rubro de lo que no, no para adivinar esas decisiones.
- **Error corregido**: una palabra de `excluir` que aparecía solo en la
  descripción restaba 35 aunque el nombre fuera del núcleo («alimentación»
  eléctrica, «capacitación», «pavimento» de la sala). De 8 casos así se
  ofertaron 4. Ahora resta `restaExcluirSoloDescripcion` (10).
- **El monto estimado por tipo** (cuando no se publica, la mitad de los casos)
  separaba peor que el azar (AUC 0,45, contra 0,57 con el monto publicado).
  Ahora queda casi neutro (`confianzaEstimadoPorTipo` 0,3).
- **Pesos**: visita, plazo y ejecución daban 100 a casi todo e inflaban la
  nota sin separar nada; ejecución incluso iba al revés en todas las épocas.
  Nuevos pesos: rubro 30, monto 10, dificultad 15, visita 5, ubicación 15,
  comprador 15, plazo 5, ejecución 5.
- **Exclusiones nuevas**: «aditivo» (por «Provisión de sal y aditivos para
  caldera», que tenía 88), «granel» y «petróleo para calderas de
  calefacción» (combustible). También vehículos y muebles («radiador de
  motor», «camioneta», «mueble»…).
- **«radiador» pasó de núcleo a afín.** En las compras ágiles casi siempre es
  el de un vehículo, y salían como prioritarias. «Caldera y radiadores» sigue
  siendo núcleo por «caldera».
- **Ojo con las frases**: las palabras vacías («para», «por») no cuentan.
  «petróleo para caldera» calzaba con «cambio de caldera **a petróleo por
  caldera** a gas», que se ofertó. Medir siempre después de agregar una
  frase.
- Resultado en las 247 licitaciones: el AUC pasó de 0,757 a 0,79. Con nota 85
  o más se ofertaba el 67 % (10 de 15); ahora el 80 % (4 de 5). Hay que
  repetir la medición cuando cambien reglas o pesos.

**Correo de alertas (2026-10-14, `alertas_oportunidades.py`)**: cuando hay
una oportunidad nueva con **nota 85 o más**, se envía un resumen (monto,
tiempo restante, región, visita técnica, ejecución o plazo de entrega,
comprador, a favor y en contra) a quienes estén en
`oportunidades_destinatarios.json` (gitignoreado porque el repo es público;
desde el 2026-10-15 son dos personas). Reglas en `alertas` de la
configuración:
- **Solo en horario laboral** (2026-10-15, pedido del usuario: «nunca debes
  mandar un correo fuera de los días u horarios laborales, siempre de lunes a
  viernes y en horarios entre las 9.00 a las 17.00»): `horario` (a las 17:00
  ya no) y los feriados nacionales de `feriados`, verificados en feriados.cl.
  2027 trae un feriado adicional el 17 de septiembre. Fuera de horario lo
  elegible **espera** sin marcarse como enviado y sale en la primera vuelta
  en horario si sigue abierto. Se revisa dos veces: al decidir y justo antes
  de entregar a Outlook (`exigir_horario_laboral`). **Cada año hay que
  agregar los feriados del año nuevo**; si faltan, el comando lo avisa.
- **Como máximo 3 correos en 7 días corridos.** Si en una vuelta hay varias,
  van juntas en un solo correo.
- **Nunca se repite una oportunidad**: lo enviado queda en
  `oportunidades_estado_correos.json`.
- No se avisa lo que ya está en la Planilla, lo descartado, lo que no tiene
  ficha, ni lo que cierra antes de 48 horas (una compra ágil, 12 horas).
- **Cómo sale**: lo envía Outlook de este equipo por COM
  (`enviar_correo_outlook.ps1`, que recibe un JSON y no texto por la línea de
  comandos). No se guarda ninguna contraseña nueva.
- **Cuándo**: lo corre `Actualizar_Finanzas/driver.py` después de publicar el
  tablero, y solo si Mercado Público respondió.
- **Si Outlook falla**, no se marca como enviada y se reintenta en la próxima
  vuelta.
- Comandos: `status` (qué se enviaría), `vista` (escribe el correo como
  .html, sin enviar). Las pruebas cortan Outlook en el `conftest`.

**Revisión de las bases antes del correo (2026-10-15, `bases_oportunidades.py`)**,
pedido del usuario: «antes de enviar los correos de alerta [...] se analicen
los anexos buscando las bases técnicas y administrativas y verifiques los
puntos más relevantes, luego de eso envías el correo».
- **Los PDF de las bases no se pueden bajar solos, y no se intenta.** En una
  licitación, «Ver adjuntos» exige reCAPTCHA Enterprise; en una compra ágil,
  buscador.mercadopublico.cl bloquea todo lo que no sea un navegador
  (CloudFront). Ninguna API los entrega: la de licitaciones no los nombra, la
  de Compra Ágil da solo nombre e id, y la OCDS
  (`apis.mercadopublico.cl/OCDS/data/...`) no trae documentos ni las
  licitaciones recién publicadas. Verificado el 2026-10-15.
- **Lo que sí se lee**: la ficha pública de la licitación
  (`DetailsAcquisition.aspx`, sin captcha), con el «Contenido de las bases»
  que el comprador llena en el portal. Se lee por id de elemento (ASP.NET):
  `lblFicha1Estado`, `lblFicha3Cierre`, `grvFechasUsuario_ctlNN_*` (ahí está la
  **visita a terreno**: la API la deja en 1900-01-02), `grvCriterios_*`,
  `grvGarantias_*`, `grvRequerimientosTecnicos_*` (multas), `lblFicha7*`
  (monto, duración, pago, subcontratación) y `grvAdministrativo/Tecnico/Economico_*`.
  Una L1 (menos de 100 UTM) tiene una ficha corta sin ese contenido. De una
  compra ágil se vuelve a pedir el detalle a su API: estado, cierre,
  presupuesto, entrega, descripción y nombres de los adjuntos.
- **Qué verifica**: estado y cierre, visita (obligatoria, voluntaria o sin
  decir, y si ya pasó), monto y duración contra la evaluación previa,
  garantías, criterios (precio bajo 40 %, experiencia 25 % o más, puntaje por
  certificación o marca), pago a más de 30 días, 50 o más reclamos por pago,
  subcontratación prohibida, multas, y las `senales` de la configuración (SEC,
  representación de marca, experiencia mínima, registros, seguros, ISO). Cuenta
  cuántos campos solo dicen «según bases adjuntas».
- **Qué hace con eso**: lo que descarta sola (no publicada, cierre que quedó
  bajo `horasMinimasParaCerrar`, visita **obligatoria** ya pasada) no se envía,
  deja su lugar a la siguiente y queda en `descartadasBases` del registro (no
  se vuelve a revisar). Lo demás va al correo en «Revisión de las bases», con
  ! / ✓ / ·, y corrige las filas de visita, monto y cierre. Si la ficha no
  responde, la oportunidad espera; sale con el aviso solo si en la próxima
  vuelta hábil (`proxima_vuelta`) ya no cerraría con tiempo.
- Medido el 2026-10-15 con 10 fichas reales: la licitación enviada ese día
  tenía visita a terreno el 20-10 que la evaluación no veía; otra, visita
  obligatoria al día siguiente. Revisar 3 tomó 21 s (la compra ágil, por su
  API lenta, la mayor parte).
- **La visita en el tablero (2026-10-15, el usuario: «no se están
  identificando bien las visitas a terreno»)**: la evaluación previa decía
  «Sin visita a terreno» (100) en todo, porque la API nunca la trae. Leídas las
  fichas, 20 de 35 licitaciones del tablero tenían visita, varias obligatorias
  y ya pasadas. Ahora cada vuelta lee la ficha pública de las candidatas
  (`_leer_visitas_bases`, `consultas.fichaBases`: una cada 2 s, como mucho
  4 minutos; las que faltan siguen en la próxima) y guarda `visitaBases`
  (`resumen_visita`) en la ficha de la caché, que se vuelve a leer al
  refrescarse la de la API. `visitas_de_la_ficha` es la regla única del tablero
  y del correo: es visita una fecha del comprador que la nombra, o cualquiera
  que no sea otro hito (firma, adjudicación...) si un criterio o cláusula
  trata de la visita (hay bases con una fecha por recinto). Con varias fechas
  se muestra la próxima y la visita pasa cuando pasaron todas (`ultima`; la
  página lo repite en `visitaDelDia`). Sin la ficha leída, una L1 o una compra
  ágil sin mención: «Visita sin confirmar», con el valor esperado
  (`visitaSinDato.probabilidadVisita` 0,55, lo medido ese día), nunca 100.
- `py -3.14 bases_oportunidades.py <código>...` revisa y muestra sin enviar ni
  guardar. Configuración en `alertas.revisionBases` (`activa: false` vuelve al
  correo sin revisión). Las pruebas (`tests/test_bases_oportunidades.py`) usan
  fichas sintéticas con los mismos id; el `conftest` corta la red de la ficha.

**Configuración**: `oportunidades_config.json` (versionado, sin datos de la
empresa) guarda pesos, categorías, topes, frases del rubro, puntaje por
región, tramos de duración, señales de dificultad, valor UTM, presupuesto de
consultas (80 por vuelta), compras ágiles y alertas. La UF se lee de la
caché del Cotizador.

**Seguridad**: es el mismo cliente del monitor (HTTPS, tope de tamaño,
ticket DPAPI).
- No se publican funcionarios: no se leen esos campos.
- A la descripción se le borran correos y teléfonos (`_sin_contactos`), sin
  tocar los montos.
- El tablero lleva los datos cifrados (candado de los tableros) y escribe
  todo con `textContent`: un nombre de la API nunca se interpreta como HTML.
- Los enlaces se limitan a https://www.mercadopublico.cl/ y a la ficha
  pública de una compra ágil en buscador.mercadopublico.cl.
- El correo escapa todo texto de la API (`html.escape`). Los destinatarios se
  validan contra una expresión de correo y no están en el repositorio.

**Estado**: el paso del procesador está **apagado** (`enProcesador: false`)
hasta que el usuario lo active. El tablero se refresca y publica **todos los
días a las 09:00** (tarea «Oportunidades Mercado Publico QUEMPIN»,
`Actualizar_Finanzas/driver.py oportunidades`, desde el 2026-10-14; era a las
08:00 hasta que el correo quedó limitado al horario laboral) y también
en `/Actualizar_Finanzas run` (paso 7). `py -3.14 oportunidades.py status`
evalúa sin publicar nada, y `--sin-red` reevalúa con la caché
(`oportunidades_estado.json`, gitignoreada).

## Registro de proyectos (`proyectos.py`)

La clave común de proyecto es el **N° de la Planilla de Ingreso** (`req`);
el TAG de Análisis Financiero y Centro de Costos se le asocia al
adjudicarse. Cada herramienta guarda el `req` en su propio dato (AF:
columna «N° Requerimiento»; Formulador: `vinculos.requerimiento`; Sistema
QUEMPIN: `proyecto.req`) y `proyectos.py` **solo junta**: una entrada por
requerimiento vivo o nombrado por algo, con su TAG, formulaciones,
cotizaciones, OC y carpetas (las bibliotecas ya nombran las carpetas con el
N°: «280. UMAG - …»). Un `req` con dos TAG distintos va a `conflictos`, no se
adivina; un TAG sin `req`, a `sinVincular`.

## Agregar un flujo nuevo

1. Definir el tipo de mensaje (o la publicación): su esquema y ejemplos en
   `esquemas/`, una fila en la tabla de arriba y en el `LEEME.md` de la
   carpeta.
2. El destinatario lo atiende con `intercambio.leer_buzon(raiz, destino=...,
   tipo=...)` y `intercambio.archivar(...)`, **después** de guardar sus
   propios datos (si falla el guardado, el mensaje debe seguir en el buzón).
3. Tests con `tmp_path`: nunca la carpeta real. Los módulos solo usan la
   carpeta real cuando corren contra sus libros reales (ver cómo
   `ejecutar()` de Análisis Financiero decide `raiz_intercambio`).

## Datos

La carpeta lleva montos y nombres de proyectos reales y ya no está dentro de
este repo, así que nada de ella llega a git. Tests: `Sistema Intercambio/tests/`
(siempre en `tmp_path`, nunca la carpeta real).
