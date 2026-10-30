# CLAUDE.md — Sistema Intercambio

Protocolo común para que las herramientas de QUEMPIN compartan información sin
depender unas de otras. No es un servidor ni una base de datos: es una carpeta
sincronizada por OneDrive con JSON de formato común (`quempin.intercambio/1`).

| Tema | Detalle (léelo solo al tocarlo) |
|---|---|
| Qué hace cada tipo de mensaje y publicación | [docs/tipos.md](docs/tipos.md) |
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
├── buzon/               mensajes entre herramientas (adjuntos/<id>/: archivos de un documento-cc)
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
- **Lo publicado se reemplaza completo**, con escritura atómica (temporal + `os.replace`).
  **Si los datos no cambiaron, no se reescribe** (OneDrive subiría y bajaría copias
  idénticas). `generado` dice cuándo cambió el dato; el pulso está en `estado.json`.
- Sobre de un mensaje: `esquema`, `id` (6–64 letras/números/-/_), `tipo`, `destino`,
  `origen {herramienta, enviado, usuario?}`. El contenido lo valida su destinatario.
- `intercambio.py` solo implementa el sobre (leer y validar el buzón, archivar, publicar,
  leer publicaciones, `enviar(raiz, mensaje)`): no conoce ningún tipo.

## Catálogo: `esquemas/`

**Fuente única del formato**: `esquemas/mensajes/<tipo>.json`,
`esquemas/publicaciones/<nombre>.json` y los dos sobres, con ejemplos válidos e inválidos
en `esquemas/ejemplos/`. `esquemas.py` valida; `esquemas.js` es su gemelo para el navegador,
y `tests/test_esquemas.py` exige el mismo resultado en ambos.

- **Mensajes**: `presupuesto-proyecto`, `venta-proyecto` y `datos-proyecto` → Análisis
  Financiero; `formulacion` → Formulador; `borrador-cotizacion` y `registro-documento` →
  Sistema QUEMPIN; `actualizar-requerimiento` y `nuevo-requerimiento` → Planilla;
  `documento-cc` → Centro de Costos.
- **Publicaciones**: `analisis-financiero`, `formulador-proyecto`, `requerimientos`,
  `precios-referencia`, `documentos-comerciales`, `contrapartes`, `folios`, `licitaciones`,
  `oportunidades`, `proyectos`, `centro-costos-carpetas`, `estado`, `planificacion-semana`,
  `planificacion-lista`, `planificacion-cierres` y `ejecucion-proyectos`.
- **Copias en otros repositorios** (si cambias uno, vuelve a copiarlo): Sistema QUEMPIN lleva
  `intercambio.py`, `ubicacion.py` y `esquemas.py` (`tests/test_copias_intercambio.py` avisa);
  el Formulador, `esquemas.js`.
- Centro de Costos no publica aquí: sus costos reales llegan por la publicación de AF. Flujo
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

Cada 2 horas (tarea «Procesar intercambio QUEMPIN», `tarea_procesador.cmd`) y al final de cada
`run` de `/Actualizar_Finanzas` (`--forzar`). En orden y **solo si algo cambió** (firmas en
`procesador_estado.json`, gitignoreado):

`esquemas.json` y `LEEME.md` → entregas de formulaciones por archivo → requerimientos y cierre
de sugerencias → Análisis Financiero (`run` solo si llegaron envíos no intentados, de los tipos
cuyo esquema declara `destino: analisis-financiero`; si no, y cambió CC o el libro, solo
`intercambio publicar`) → precios de referencia → Sistema QUEMPIN (`python -m
app.integraciones.ecosistema procesar`, con su Python 3.11) → Mercado Público (consulta siempre:
lo que cambia está en la API) → la UF del día (`Cotizador_Historico/driver.py uf`) → carpetas de
facturas → documentos del Portal (`documentos_cc.py`) → `proyectos.json` → `estado.json`.

- **Un paso que falla no frena a los demás**: queda en `estado.json` y en
  `logs/procesador_AAAA-MM.log` (una línea por vuelta, con los segundos de cada paso de 10 s o más).
- Un envío pendiente no dispara un `run` en cada vuelta: se reintenta cuando cambia algo.
- Los módulos de Finanzas corren **en su propio proceso** (archivos homónimos); un candado
  (`.procesador.lock`, vence a los 30 min) evita dos vueltas a la vez.
- **Nunca escribe la Planilla de Ingreso ni publica en GitHub.**
- **Si deja de correr, las herramientas lo dicen**: `pulso.js` (una sola copia de la regla; el
  Formulador la lleva textual y el tablero AF la inserta en su build) cuenta horas hábiles (lunes
  a viernes, 08:30–19:00) desde la última vuelta. Con más de 4, aviso rojo. Las noches y los fines
  de semana no cuentan.

## Lo que se escribe en la Planilla (`planilla_escritura.py`, cada 10 minutos)

Tarea «Registrar en la Planilla QUEMPIN» (`tarea_planilla.cmd`, sesión interactiva del usuario).
Solo abre Excel si hay un pedido o la planilla cambió y tiene un N° en fórmula; log en
`logs/planilla_AAAA-MM.log`.

- **El N° no se mueve** aunque alguien ordene la tabla. Una vez, con el N° como fórmula
  `=SI(B<>"";FILA()-1;"")`, un orden cambió 55 N°. Toda fila con datos pasa a número fijo, con el N°
  de la última publicación si ya estaba (por título y referencia) o el que muestra la fórmula si
  es nueva. Una fila nueva cuyo N° ya tiene otro requerimiento no se renumera: queda el aviso.
- **Freno**: `requerimientos.json` no se publica si la planilla le cambió el N° a 3 o más
  requerimientos (`requerimientos.renumerados`): queda la anterior y el paso falla en `estado.json`.
- **Siempre con Excel** (`planilla_excel.ps1`, por COM; **nunca openpyxl**, ver `requerimientos.py`).
  Excel abre el archivo como documento de SharePoint con coautoría; `Workbooks.Open` puede volver
  antes de que el libro esté listo. Abierto solo para lectura: no escribe y reintenta. Respaldo antes
  de cada escritura en `%LOCALAPPDATA%\QUEMPIN\respaldos-planilla` (30).
- **Registra** los `nuevo-requerimiento` del Formulador: una fila en la primera vacía de la tabla,
  con N° fijo y los datos del proyecto al escribir, y republica `requerimientos.json`.
- **PowerShell**: texto y número se escriben en líneas distintas (el binder de COM recuerda el tipo de
  la primera escritura de cada línea), y el `.ps1` va con BOM (PowerShell 5.1 lo lee como ANSI sin él).

## Mercado Público (resumen)

- **Monitor**: en cada vuelta sugiere a la Planilla solo lo que Mercado Público prueba. El ticket es
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
