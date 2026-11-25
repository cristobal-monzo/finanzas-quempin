# Portal — Rendiciones

Detalle de referencia: léelo solo al tocar esta parte. Las reglas generales están en `../CLAUDE.md`.

Pedido del usuario (2026-11-18): rendir vales, recuperaciones de gastos y caja chica. Se suben las fotos o PDF de las
boletas y facturas, se leen solas al subirlas, se corrigen en una tabla y el resultado es un PDF: el resumen con la
estética de los informes QUEMPIN y una página por documento con su foto. Cada documento lleva su proyecto (una rendición
puede juntar gastos de varios) y la rendición se envía al Centro de Costos.

## Dónde está

- Herramienta `rendiciones` del registro (`tipo: vista`, grupo `controlar`), sección `#vistaRendir`, funciones `rd*`,
  estado `rd`, diálogos `#dlgRdDoc` (ver la foto, girar, volver a leer) y `#dlgRdLector` (lector con IA).
- `rdAlMostrar` (desde `abrir`) y `rdAlRecorrido` (desde el `.then` de `rcCargar`) cargan la lista de proyectos.
- Pruebas: `tests/portal/test_portal_rendiciones.py`. El lector de texto se prueba solo con `window.QRendiciones.interpretar`.

## Cómo lee

1. **PDF electrónico**: pdf.js saca el texto (no hay OCR). Se guardan hasta `RD_MAX_PAGINAS` páginas como imagen.
2. **Foto**: con el lector con IA configurado, la foto va al Worker (`lector-rendiciones/`); si falla, avisa una vez y
   sigue en el navegador. Sin él, Tesseract (`spa`) lee la foto **original** (no la copia achicada que se guarda) con un
   tope de 6 MP (`area`): una boleta larga y angosta no se achica por su largo. Si la confianza es menor que 45, prueba
   la foto girada.
3. `rdInterpretar(texto, {fuente, confianza, hoy})` saca tipo, N°, fecha, proveedor, RUT, detalle y valor. Lo dudoso va a
   `dudas` y se pinta en naranjo:
   - RUT con módulo 11; nunca el de QUEMPIN; se prefiere el de una empresa (≥ 50 millones).
   - Fecha solo dentro de los últimos 400 días; un año imposible se corrige y queda en duda.
   - Valor: el total que cuadra con neto + IVA (+ exento); si no cuadra, el total más probable, en duda.
   - Proveedor: una línea con SpA/Ltda./S.A. (al menos 4 letras sin el sufijo) o una marca conocida (`MARCAS`).
   - Detalle por palabras clave (`REGLAS`), de la lista `RD_DETALLES`.
4. Las librerías (Tesseract.js 5.1.1, pdf.js 3.11.174, jsPDF 2.5.1) se bajan del CDN solo al usarlas (`rdLib`).

La lectura en el navegador acierta bien con boletas y vouchers nítidos y se equivoca con papel arrugado o fotos oscuras:
por eso cada dato dudoso queda en naranjo y el envío con datos en naranjo pide un segundo clic.

## Lo que guarda

- El borrador vive en IndexedDB `qpn-rendiciones` (almacén `borrador`, clave `actual`), con los archivos: sigue ahí al
  volver a abrir el Portal. «Nueva rendición» pide un segundo toque si no se envió ni se descargó.
- `quempin_portal_rendiciones_lector` (dirección y clave del lector con IA) y `quempin_portal_rendiciones_deudor`.
- Número de la rendición: `R-AAAAMMDD-HHMM-<usuario>`.

## El PDF

jsPDF, carta, en mm (`rdGenerarPdf`): cabecera con el logo (`../marca/logo.png`, que `publicar.py` copia) y la línea
naranja; ficha del deudor; tres cifras (total, documentos, saldo); la tabla; totales; «Distribución por proyecto»;
firmas «Firma Deudor» y «Firma Director Proyecto»; una página por documento con la foto girada y ajustada. Nombre:
`<Tipo> <deudor> - <período>.pdf`. Se descarga también en el celular, sin la carpeta del equipo.

## Envío al Centro de Costos

- Necesita la carpeta de Intercambio conectada (Chrome o Edge de escritorio), como «Subir documentos».
- Un mensaje `documento-cc` por carpeta, con `rendicion` (id común, N°, tipo, deudor, total, cantidad y los datos de cada
  documento). Archivo: `<N° rendición> - <n> <Tipo> <N°><ext>`. Esquema: `Sistema Intercambio/esquemas/mensajes/documento-cc.json`.
- El procesador (`documentos_cc.py`) copia los archivos a «Facturas y Boletas/<país>/<carpeta>/» y publica
  `rendiciones.json`. `driver.py status` del Centro de Costos muestra esos datos para el Paso 2, y la skill los usa tal cual.
- «Rendiciones enviadas» lee lo publicado y lo que espera en el buzón (`rdLeerEnvios`).

## Enviar rendición: registro y correo (2026-11-18)

Pedido del usuario: «Enviar rendición» la guarda en un registro de rendiciones y envía un correo automático, muy
ejecutivo, con el monto total, el período (del documento más antiguo al más reciente) y la persona con nombre y apellido.

- **Persona**: el campo lleva por defecto el nombre de quien usa el portal (`nombres` del registro: NB, ES, CM, LC, MP,
  EV, RL) y ofrece los demás. Sin nombre y apellido no se envía.
- **Registro**: `publicado/rendiciones.json` (todas, la más reciente primero). El panel «Registro de rendiciones» lo junta
  con lo que espera en el buzón (`rdRegistro`): «En camino», «Correo pendiente», «Correo enviado» o «No se pudo».
- **Correo**: el procesador (`Sistema Intercambio/correo_rendiciones.py`, paso `correo-rendiciones`) lo entrega a Outlook
  del PC donde corre, a los destinatarios de `rendiciones_destinatarios.json` (gitignoreado, junto al módulo). Sale una
  vez por rendición, cuando llegaron todos sus documentos (o a las 2 horas, con lo que llegó). Si ese PC está apagado,
  sale en su primera vuelta al encenderse. `py -3.14 correo_rendiciones.py vista` escribe el próximo como `.html`.
- **Vista previa y confirmación** (pedido del usuario, 2026-11-25): «Enviar rendición» arma el PDF y abre `#dlgRdCorreo`
  con el correo tal como saldrá (Para, Asunto, el PDF adjunto, que se abre con un clic, y el cuerpo). Nada llega al
  buzón hasta «Enviar»; «Volver» o cerrar no envían nada. El cuerpo lo arma `rdCorreoArmar`, copia de `armar()` de
  `correo_rendiciones.py`: si cambias una, cambia la otra (`_rd_correo_igual` en la prueba compara las dos). «Para» muestra
  los destinatarios del último correo del registro; el Portal no lee `rendiciones_destinatarios.json`.
- **Siempre con el PDF adjunto** (pedido del usuario, 2026-11-18: «para la revisión de Nicolás y de Gonzalo»):
  «Enviar rendición» arma el PDF (`rdGenerarPdf({ datos: true })`) y lo manda en `rendicion.pdf` del primer mensaje,
  aparte de los documentos (no se copia a la carpeta del proyecto). El procesador lo deja en
  `publicado/rendiciones/<N°>.pdf` y lo anota en `pdf` del registro; el panel lo abre con «Ver PDF». Si el PDF no se
  puede armar, el Portal no envía; si no llega, el correo no sale y a las 2 horas el paso falla en `estado.json`. El
  script de Outlook también se niega si un adjunto falta.

## Datos en naranjo y varias boletas en una foto (2026-11-24)

- **«Están bien»** (`rdConfirmar`): bajo la lectura, si hay datos en naranjo ya escritos, los da por buenos sin cambiarlos.
  Lo vacío sigue en naranjo: hay que llenarlo.
- **«+» Otra boleta de esta foto** (`rdOtra`): una fila nueva justo debajo, con la misma imagen y archivo, y tipo, fecha,
  proveedor, detalle y proyecto copiados; N° y valor quedan por llenar. No se vuelve a leer. Al enviar, cada fila lleva
  su copia del archivo al Centro de Costos, y el PDF muestra la foto en cada documento.

## Lector con IA

`lector-rendiciones/`: Cloudflare Worker con el SDK de Anthropic. Instalación, costo y cuidados en su `LEEME.md`. Necesita
una clave de API de Anthropic y una cuenta de Cloudflare; ninguna clave llega al Portal ni al repositorio.
