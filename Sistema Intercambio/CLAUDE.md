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
procesar` con su Python 3.11); `proyectos.json`, y `estado.json`.

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
