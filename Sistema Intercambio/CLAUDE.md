# CLAUDE.md — Sistema Intercambio

Protocolo común para que las herramientas de QUEMPIN compartan información sin
depender unas de otras. No es un servidor ni una base de datos: es una carpeta
sincronizada por OneDrive con JSON de formato común (`quempin.intercambio/1`).

| Tema | Detalle (léelo solo al tocarlo) |
|---|---|
| Qué hace cada tipo de mensaje y publicación | [docs/tipos.md](docs/tipos.md) |
| El Excel y el Portal: columnas, quién gana, frenos (`planilla_escritura.py`) | [docs/planilla.md](docs/planilla.md) |
| Monitor de resultados (`mercado_publico.py`) | [docs/mercado-publico.md](docs/mercado-publico.md) |
| Oportunidades, compras ágiles, calibración, correo y bases (`oportunidades.py`, `compra_agil.py`, `calibrar_oportunidades.py`, `alertas_oportunidades.py`, `bases_oportunidades.py`) | [docs/oportunidades.md](docs/oportunidades.md) |
| Carpetas de facturas de los proyectos (`carpetas_proyecto.py`) | [docs/carpetas-proyecto.md](docs/carpetas-proyecto.md) |
| Tablero de Oportunidades | `Visualizador Web/CLAUDE.md` de esta carpeta |

## Dónde está

Biblioteca de SharePoint «Formulación de proyectos - Documentos»,
`.Herramientas formulación/Intercambio/` (en el disco, `.HERRAMIENTAS FORMULACIÓN`).
El usuario decidió ponerla ahí sabiendo que quien entra a la biblioteca ve
`publicado/analisis-financiero.json`, con costos proyectados y reales.

- `ubicacion.py` la encuentra: sube desde el repo hasta la biblioteca, sin distinguir
  mayúsculas. `QUEMPIN_INTERCAMBIO` la fija a mano. Si la biblioteca no está
  sincronizada, el intercambio queda inactivo con un aviso: **nunca se crea una
  biblioteca falsa**.
- Está oculta solo en parte: el atributo de Windows no viaja por OneDrive y SharePoint
  la muestra igual.
- El Formulador (web) la abre con la API de archivos del navegador (Chrome/Edge de
  escritorio), sin iniciar sesión. Python la lee como cualquier carpeta.

```
.Herramientas formulación/Intercambio/
├── intercambio.json     manifiesto: así se reconoce la carpeta correcta
├── esquemas.json        el catálogo completo, para las herramientas de otros repos
├── LEEME.md             lo deja el procesador desde LEEME-carpeta.md: edita ese
├── buzon/               mensajes entre herramientas (adjuntos/<id>/: archivos de un documento-cc o imágenes de una observacion)
├── procesado/AAAA-MM/   mensajes ya atendidos, con su resultado
└── publicado/           lo que cada herramienta comparte
    ├── formulador/      repositorio de formulaciones: un archivo por proyecto
    ├── planificacion/   <AAAA-Www>/, lista/ y cierres/: un archivo por navegador
    └── ejecucion/       Proyectos en ejecución: un archivo por navegador
```

Lleva montos y nombres reales. **Las pruebas usan siempre `tmp_path`, nunca esta carpeta**
(`Sistema Intercambio/tests/`).

## Reglas del protocolo

- **Cada herramienta es dueña de sus datos** y nunca escribe los de otra. Para pedir un
  cambio deja un mensaje en `buzon/`; el dueño decide, con sus validaciones y respaldos.
- **Un mensaje se atiende una sola vez**: el destinatario lo mueve a `procesado/AAAA-MM/`
  con `resultado = {estado, fecha, detalle, ...}`. Estados finales: `aplicado`,
  `sin-cambios`, `reemplazado`, `rechazado`, `descartado`. Si no puede decidir, queda en
  el buzón y lo informa.
- **Una ficha, una carpeta, un N°** (`mismo_proyecto.py`, 2026-11-03): si la ficha del AF tiene su carpeta con
  facturas en el Centro de Costos y el N° tiene otra, son dos proyectos. El AF deja pendiente el envío del N° a esa
  ficha y el cruce (`proyectos.py`) no los une: `fichaAjena` del N°, `conflictos` y la bandeja. Caso: la ficha UMAG
  («UMAG Linea de H2», entregado) llevaba el N° 280 («280. UMAG - Conexión y PH Lab 1»).
- **Lo publicado se reemplaza completo**, con escritura atómica (temporal + `os.replace`).
  **Si los datos no cambiaron, no se reescribe** (OneDrive subiría y bajaría copias
  idénticas). `generado` dice cuándo cambió el dato; el pulso está en `estado.json`.
- Sobre de un mensaje: `esquema`, `id` (6–64 letras/números/-/_), `tipo`, `destino`,
  `origen {herramienta, enviado, usuario?}`. El contenido lo valida su destinatario.
- `intercambio.py` solo implementa el sobre (leer y validar el buzón, archivar, publicar,
  leer publicaciones, `enviar(raiz, mensaje)`): no conoce ningún tipo.
- **`publicar` valida contra el catálogo antes de escribir** (2026-11-06): lo que no cumple el esquema de esa
  publicación levanta `PublicacionInvalida` y no toca el archivo (un nombre sin esquema se publica igual).
  `paquete=` valida con el `esquemas.json` de la carpeta (Sistema QUEMPIN no tiene `esquemas/`); `validar=False`
  solo para fixtures parciales de pruebas. El Portal hace lo mismo con `esquemas.js` antes de escribir.
- `estado.json` dice además qué código corrió la vuelta (`codigo {rama, commit, sucio}`: fuera de `master`, o con
  código modificado sin commit, el pulso lo avisa) y si está la tarea de pedidos (`pedidos.tarea`: sin ella, un
  «Actualizar datos» del Portal espera la vuelta de cada 5 minutos).

## Catálogo: `esquemas/`

**Fuente única del formato**: `esquemas/mensajes/<tipo>.json`,
`esquemas/publicaciones/<nombre>.json` y los dos sobres, con ejemplos válidos e inválidos
en `esquemas/ejemplos/`. `esquemas.py` valida; `esquemas.js` es su gemelo para el navegador,
y `tests/test_esquemas.py` exige el mismo resultado en ambos.

- **Mensajes**: `presupuesto-proyecto`, `venta-proyecto` y `datos-proyecto` → Análisis
  Financiero; `formulacion` → Formulador; `borrador-cotizacion` y `registro-documento` →
  Sistema QUEMPIN; `actualizar-requerimiento`, `nuevo-requerimiento` y `editar-requerimiento` → Planilla;
  `documento-cc` → Centro de Costos; `observacion` → mejora continua (la atiende una persona con
  `/Observaciones_Portal`, `observaciones.py`); `pedir-vuelta` → procesador; `mover-carpeta` → carpetas
  de los proyectos (`cierre_entregados.py`).
- **Publicaciones**: `analisis-financiero`, `formulador-proyecto`, `requerimientos`,
  `precios-referencia`, `documentos-comerciales`, `contrapartes`, `folios`, `licitaciones`,
  `oportunidades`, `proyectos`, `centro-costos-carpetas`, `documentos-proyecto`, `estado`, `planificacion-semana`,
  `planificacion-lista`, `planificacion-cierres`, `ejecucion-proyectos`, `presencia` (quién tiene abierta qué
  semana o proyecto en el Portal, para trabajar a la vez) y `uso-portal` (qué abre el
  equipo en el Portal, anónimo; `py -3.14 uso_portal.py --dias 30` lo suma).
- **Copias en otros repositorios** (si cambias uno, vuelve a copiarlo): Sistema QUEMPIN lleva
  `intercambio.py`, `ubicacion.py` y `esquemas.py` (`tests/test_copias_intercambio.py` avisa);
  el Formulador, `esquemas.js`.
- Centro de Costos no publica aquí: sus totales llegan por la publicación de AF, y sus documentos
  uno por uno los publica el procesador (`documentos-proyecto`, desde el snapshot de su tablero). Flujo
  de Caja tampoco, a propósito: su resultado es la caja de la empresa y esta carpeta la ve toda
  la biblioteca.

### Agregar un flujo nuevo

1. Su esquema y ejemplos (válido e inválido) en `esquemas/`, su fila en
   [docs/tipos.md](docs/tipos.md), su nombre en la lista de arriba y en `LEEME-carpeta.md`.
2. El destinatario lo atiende con `intercambio.leer_buzon(raiz, destino=..., tipo=...)` y
   `intercambio.archivar(...)`, **después** de guardar sus datos: si falla, el mensaje debe
   seguir en el buzón. El esquema solo asegura la forma; las reglas de negocio son del dueño.
3. Pruebas con `tmp_path`. Un módulo usa la carpeta real solo al correr contra sus libros reales
   (ver cómo `ejecutar()` de AF decide `raiz_intercambio`).

## El procesador (`procesar.py`)

Cada 5 minutos (tarea «Procesar intercambio QUEMPIN», `tarea_procesador.cmd`; pedido del usuario 2026-11-11, antes
cada 2 horas) y al final de cada `run` de `/Actualizar_Finanzas` y de cada registro del Centro de Costos (`--forzar`).
En orden y **solo si algo cambió** (firmas en `procesador_estado.json`, gitignoreado):

`esquemas.json` y `LEEME.md` → entregas de formulaciones por archivo → requerimientos y cierre
de sugerencias → Análisis Financiero (`run` solo si llegaron envíos no intentados, de los tipos
cuyo esquema declara `destino: analisis-financiero`; si no, y cambió CC o el libro, solo
`intercambio publicar`) → precios de referencia → Sistema QUEMPIN (`python -m
app.integraciones.ecosistema procesar`, con su Python 3.11) → Mercado Público (**cada 3 horas**) → la UF del día
(`Cotizador_Historico/driver.py uf`, una vez al día) → proyectos entregados (`cierre_entregados.py`, cada vuelta) →
carpetas de facturas → documentos del Portal (`documentos_cc.py`) → `proyectos.json` → `estado.json`.

- **Turnos** (`TURNO_SEG`): Mercado Público y Oportunidades consultan la API cada 3 horas (eran 50–170 s de cada vuelta);
  la última vez queda en `_turnos` de `procesador_estado.json`. Entre turnos, `estado.json` repite su último resultado
  con `ultimaVez`. Lo que falla (la API, mindicador.cl, el respaldo) se reintenta a la media hora, no en cada vuelta;
  si la API quedó a medias (tope de llamadas), sigue en la vuelta siguiente. `--forzar` **no adelanta** el turno.
- **La API una sola vez a la vez**: el tablero de Oportunidades marca `%LOCALAPPDATA%\QUEMPIN\mercado-publico-en-uso.lock`
  mientras consulta (`mercado_publico.usando_api`) y el procesador deja su turno para la vuelta siguiente; la tarea de
  Oportunidades, a su vez, espera el candado del procesador.
- **Sin cargar OneDrive** (2026-11-11): una vuelta sin novedades no escribe nada sincronizado. `estado.json` se
  reescribe si cambió su contenido (sin contar horas ni duraciones), si la vuelta atendió un pedido o `--forzar`, o
  cada 15 minutos (`LATIDO_SEG`) para que el pulso siga vivo; `procesador_estado.json` y
  `carpetas_proyecto_estado.json`, solo si cambiaron; `git status` corre con `--no-optional-locks`.
- **A pedido**: «Actualizar datos» del Recorrido en el Portal deja un `pedir-vuelta` en el buzón. La tarea «Pedidos al
  procesador QUEMPIN» (`tarea_pedidos.cmd`, cada minuto) corre `procesar.py --si-hay-pedido`: sin pedido termina sin
  escribir nada; con uno da una vuelta normal (sin adelantar el turno de Mercado Público), salvo que la última sea de
  hace menos de un minuto (el pedido espera). Cada vuelta archiva los pedidos que vio al empezar. Tarda un par de
  minutos más lo que OneDrive demore en llevar y traer (más de una hora, si está atrasado).
- **Un paso que falla no frena a los demás**: queda en `estado.json` y en `logs/procesador_AAAA-MM.log` (una línea por
  vuelta **con novedades**: cambió el estado, atendió pedidos, corrió Mercado Público, `--forzar` o un paso de 10 s o
  más, con sus segundos; una falla que se repite igual se anota la primera vez).
- Un envío pendiente no dispara un `run` en cada vuelta: se reintenta cuando cambia algo.
- Los módulos de Finanzas corren **en su propio proceso** (archivos homónimos); un candado
  (`%LOCALAPPDATA%\QUEMPIN\procesador.lock`, fuera de OneDrive; vence a los 30 min) evita dos vueltas a la vez. La
  tarea programada además ignora un inicio si la anterior sigue (`IgnoreNew`). `--forzar` espera hasta 10 minutos a
  la vuelta en curso en vez de saltarse la suya.
- **Nunca escribe la Planilla de Ingreso ni publica en GitHub.**
- **Si deja de correr, las herramientas lo dicen**: `pulso.js` (una sola copia de la regla; el
  Formulador la lleva textual y el tablero AF la inserta en su build) cuenta horas hábiles (lunes
  a viernes, 08:30–19:00) desde la última vuelta. Con más de 4, aviso rojo. Las noches y los fines
  de semana no cuentan.

## Lo que se escribe en la Planilla (`planilla_escritura.py`, cada minuto)

Tarea «Registrar en la Planilla QUEMPIN» (`tarea_planilla.cmd`, sesión interactiva del usuario).
Solo abre Excel si hay un pedido o la planilla cambió y tiene un N° en fórmula; log en
`logs/planilla_AAAA-MM.log`.

- **Solo el Portal da N°** (2026-11-12, plan `Documentación/Planes y análisis/2026-11-11-n-de-requerimiento-sin-choques.md`):
  el Formulador ya no manda `nuevo-requerimiento` («Ingresar en Requerimientos» abre el Portal) y **la hoja entera
  está protegida con contraseña** (`PROTEGER_HOJA`). La genera `planilla_escritura.py` una vez y la guarda cifrada
  con DPAPI en `%LOCALAPPDATA%\QUEMPIN\planilla.clave`; `py -3.14 planilla_escritura.py clave` la muestra (guárdala
  aparte: sin ella, solo este usuario de este computador desprotege la hoja). El `.ps1` la recibe por el entorno,
  desprotege solo con ella (nunca `Unprotect()` sin contraseña: Excel oculto la pediría y la tarea se colgaría),
  escribe y deja todas las celdas bloqueadas (filtrar sí, ordenar no). Corre **cada minuto**: el N° provisorio de
  un requerimiento del Portal se confirma en un par de minutos más lo que tarde OneDrive.

- **El N° no se mueve** aunque alguien ordene la tabla. Una vez, con el N° como fórmula
  `=SI(B<>"";FILA()-1;"")`, un orden cambió 55 N°. Toda fila con datos pasa a número fijo, con el N°
  de la última publicación si ya estaba (por título y referencia) o el que muestra la fórmula si
  es nueva. Una fila nueva cuyo N° ya tiene otro requerimiento no se renumera: queda el aviso.
- **Freno**: `requerimientos.json` no se publica si la planilla le cambió el N° a 3 o más
  requerimientos (`requerimientos.renumerados`): queda la anterior y el paso falla en `estado.json`.
- **Fila borrada** (2026-11-09): un N° publicado que ya no está, ni con otro N°, va a `desaparecidos` (con la
  fecha en que faltó) y a `avisos`, que el Portal muestra. Se arrastra de una publicación a otra hasta que vuelva.
- **Bandeja**: un envío que espera más de 5 días hábiles en el buzón sube a «alto» (`ESTANCADO_DIAS_HABILES`).
- **Siempre con Excel** (`planilla_excel.ps1`, por COM; **nunca openpyxl**, ver `requerimientos.py`).
  Excel abre el archivo como documento de SharePoint con coautoría; `Workbooks.Open` puede volver
  antes de que el libro esté listo. Abierto solo para lectura: no escribe y reintenta. Respaldo antes
  de cada escritura en `%LOCALAPPDATA%\QUEMPIN\respaldos-planilla` (30).
- **El Excel y el Portal se actualizan mutuamente** ([docs/planilla.md](docs/planilla.md)): escribe los
  `nuevo-requerimiento` y `editar-requerimiento` del buzón, y si el archivo cambió republica
  `requerimientos.json` sin abrir Excel. Si una casilla cambió en los dos lados, manda el cambio más reciente.
- **Registra** una fila nueva en la primera vacía después del último N°, con N° fijo. Del Formulador, con los
  datos del proyecto al escribir; del Portal, con los del pedido y el siguiente N° libre si ya lo tomaron.
- **Columnas por su encabezado, nunca por su letra**: alguien insertó «Cliente» en G el 2026-10-27. Python
  calcula cada letra y Excel revisa que siga teniendo ese encabezado antes de escribir. Antes de cambiar una
  fila se confirma su título.
- **Con ese computador apagado**, lo del Portal espera en el buzón y el Portal lo avisa pasada media hora.
- **PowerShell**: texto y número se escriben en líneas distintas (el binder de COM recuerda el tipo de
  la primera escritura de cada línea), y el `.ps1` va con BOM (PowerShell 5.1 lo lee como ANSI sin él).

## Mercado Público (resumen)

- **Monitor**: cada 3 horas sugiere a la Planilla solo lo que Mercado Público prueba. El ticket es
  personal: cifrado con DPAPI en `%LOCALAPPDATA%\QUEMPIN\mercado-publico.ticket`, se ingresa con
  `py -3.14 mercado_publico.py configurar` y se censura en todo error. `status` dice qué sugeriría sin
  escribir. Las pruebas cortan la red y el ticket en `tests/conftest.py`.
- **Oportunidades**: el tablero y el correo salen todos los días a las 09:00 (tarea «Oportunidades
  Mercado Publico QUEMPIN», `Actualizar_Finanzas/driver.py oportunidades`) y en `/Actualizar_Finanzas
  run`; el paso del procesador está apagado (`enProcesador: false`). `py -3.14 oportunidades.py status`
  evalúa sin publicar (`--sin-red` usa la caché). Si cambias reglas o pesos, repite la medición con
  `calibrar_oportunidades.py medir`. **Cada año hay que agregar los feriados** en `alertas` de la
  configuración.

## Registro de proyectos (`proyectos.py`)

La clave común es el **N° de la Planilla de Ingreso** (`req`); el TAG de AF y CC se asocia al
adjudicarse. Cada herramienta guarda el `req` en su dato (AF: columna «N° Requerimiento»; Formulador:
`vinculos.requerimiento`; Sistema QUEMPIN: `proyecto.req`) y `proyectos.py` **solo junta**: una entrada
por requerimiento vivo o nombrado por algo, con su TAG, formulaciones, cotizaciones, OC y carpetas. Un
`req` con dos TAG va a `conflictos`, no se adivina; un TAG sin `req`, a `sinVincular`.

## Proyectos entregados y el estado «Cerrado» (2026-11-09)

Pedido del usuario: un proyecto cuya carpeta se mueve a mano a «0 Proyectos Entregados <año>» de Gestión de Proyectos
queda «Cerrado» en la Planilla en la vuelta siguiente; y al cambiar uno a «Cerrado» en el Portal, una opción para mover
su carpeta ahí. Paso `entregados` del procesador (`cierre_entregados.py`; detalle en [docs/tipos.md](docs/tipos.md)):

- **El procesador sigue sin escribir la Planilla**: pide el «Cerrado» con un `editar-requerimiento` y lo escribe
  `planilla_escritura.py`. Solo cierra lo que la Planilla tiene «Adjudicado», una vez por N° (`cerrados` en su estado:
  si alguien lo reabre, se respeta), y como máximo 5 por vuelta (`--confirmar` para más).
- **Mover** solo lo pedido desde el Portal (`mover-carpeta`), con un cambio de nombre en el mismo disco; nunca pisa.
- «Cerrado» cuenta como ganado en todo lo que preguntaba por «Adjudicado» (`requerimientos.ESTADOS_GANADOS`: tasa de
  adjudicación, Mercado Público, Oportunidades, Flujo de Caja, carpetas del Centro de Costos, el Portal).
- `py -3.14 cierre_entregados.py` dice qué cerraría, sin tocar nada.

## Respaldo diario (2026-11-09)

Paso `respaldo` del procesador (`respaldo.py`): una vez al día, un zip con `publicado/`, `buzon/`, `procesado/` y la
Planilla en `Proyectos Claude\Copias de seguridad\intercambio-AAAA-MM-DD.zip` (los últimos
30). `QUEMPIN_RESPALDO_DESTINO` lo lleva a otro disco. Restaurar: pausar el procesador, cerrar el Portal y copiar de
vuelta desde el zip.
