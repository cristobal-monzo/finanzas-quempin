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
| `publicado/analisis-financiero.json` | Análisis Financiero (fin de cada `run`, o `driver.py intercambio publicar`) | Formulador | mismo archivo |
| `publicado/formulador/<uid>.json`: un archivo por presupuesto, el repositorio de formulaciones, con `historia`, `resumen` (costo, precio, margen y `costosAF`, calculados por el Formulador) y `datos` | Formulador de cada equipo (`js/compartida.js`, 2026-09-30); también `formulaciones.incorporar_buzon()` con las entregas por archivo | Formulador de los demás equipos; Claude (`formulaciones.py`, driver AF `formulaciones`) | `Sistema Intercambio/formulaciones.py` |
| mensaje `formulacion` → `formulador`: un presupuesto entregado por archivo desde un navegador sin acceso a la carpeta | Formulador («Descargar para el equipo»; se deja a mano en `buzon/`) | `formulaciones.incorporar_buzon()` (paso 0 del `run` de `/Actualizar_Finanzas`), con las mismas reglas de quién gana del Formulador; en conflicto queda como copia | `Sistema Intercambio/formulaciones.py` |

`intercambio.enviar(raiz, mensaje)` deja un mensaje en el buzón con el mismo
nombre que usa el Formulador (`nombre_mensaje`, `nuevo_id`). Así lo usa el
driver AF `formulaciones cargar` para dejar un `presupuesto-proyecto` a
partir de un presupuesto adjudicado del repositorio.

Centro de Costos **no se modificó**: sus costos reales llegan al Formulador a
través de la publicación del Análisis Financiero (que ya los lee de su
snapshot). El ingreso de facturas desde SharePoint sigue igual.

## Agregar un flujo nuevo

1. Definir el tipo de mensaje (o la publicación) y documentarlo en la tabla
   de arriba y en el `LEEME.md` de la carpeta.
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
