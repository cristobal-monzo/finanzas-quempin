# Portal — Clic derecho y observaciones

Detalle de referencia: léelo solo al tocar esta parte. Las reglas generales están en `../CLAUDE.md`.

**Clic derecho y observaciones** (2026-10-30, pedido del usuario: que el clic derecho sea propio del Portal y que una
opción sirva para reportar un error u observación, con su localización, en una carpeta como la de intercambio, para
evaluarlo y aplicarlo después con Claude Code). Funciones `ctx*` (el menú) y `obs*` (reportar y la vista), estado `obs`.

- **El menú** (`#menuCtx`, un `<dialog>` modal: queda encima de las otras ventanas, y su fondo transparente recibe el clic
  que lo cierra): lo abre `contextmenu` en el portal y en cada herramienta (`enganchar`), en la fase de burbuja, así que si
  una herramienta tiene su propio menú y hace `preventDefault` se respeta. Hoy ninguna lo hace. **Shift + clic derecho deja
  el del navegador**, y adentro de `#dlgObs` también (corrector, pegar). Otro clic derecho con el menú abierto lo reabre en
  ese punto (`ctxOtroPunto`), también dentro de un marco. Primero lo que depende del punto (pestaña, botón del Inicio o del
  menú, campo, selección, enlace), después «Reportar…» y al final lo de siempre (`ctxOpciones`).
- **Copiar, cortar y pegar**: con `navigator.clipboard` y `execCommand('insertText' | 'delete')` en el documento del campo:
  el campo avisa `input` y Ctrl Z lo deshace, como al teclear. Un campo de clave no ofrece copiar ni cortar.
- **El lugar** (`ctxLugar`, se toma en el clic; `obsDonde`, se fija al abrir la ventana porque la herramienta de atrás puede
  recargarse): herramienta, dirección, pestañas internas (`OBS_PESTANAS`), título más cercano, ventana abierta, y el elemento
  (el botón, celda o campo más cercano, `OBS_ELEMENTO`) con su selector, texto y atributos. Nunca el valor de una clave.
- **La imagen** (`obsSacarFoto`): sin librerías. Copia la página a un `<svg><foreignObject>`, la dibuja en un canvas y marca
  con naranja el punto y el elemento. Clic en una herramienta: esa herramienta. Clic en el portal: el portal, con la
  herramienta activa dibujada en su marco. La copia se hace en el acto; dibujarla espera a que la ventana se pinte. Una
  imagen SVG no carga nada de afuera, así que `obsCopiarPagina` incrusta las hojas de estilo (`sheet.cssRules`) y las
  imágenes (canvas a data URL), y copia el valor de los campos. **No se ve igual en todo**: sin fuentes web ni fondos con
  `url()`, y lo sticky queda en su lugar. Si falla, tarda más de `OBS_CAPTURA_MS` o la página pasa de `OBS_NODOS_MAX`
  elementos, no hay imagen y se avisa; se puede pegar una. Además la persona puede agregar hasta `OBS_IMAGENES_MAX`.
- **Flujo de Caja no guarda nada de su pantalla**: lleva `"sinCaptura": true` en el registro (`obsSinCaptura`, también si el
  clic fue en el portal con ella a la vista). Sin imagen, sin imágenes pegadas, sin texto del elemento ni selección, porque su
  resultado no debe quedar en la carpeta que ve toda la biblioteca (decisión del 2026-10-02, `Sistema Intercambio/CLAUDE.md`).
  Una herramienta nueva con ese problema lleva lo mismo. Las demás sí: la ventana muestra la imagen, avisa que la ve toda la
  biblioteca y se puede quitar con la ✕.
- **Enviar** (`obsEnviar`): las imágenes en `buzon/adjuntos/<id>/` y al final `buzon/<ts>_portal_observacion_<id>.json`,
  formato en `Sistema Intercambio/esquemas/mensajes/observacion.json`. Según `obsPreparar`: con permiso, envía; sin permiso,
  lo pide al enviar; sin biblioteca, ofrece conectarla; sin `showDirectoryPicker` (teléfono, Firefox), el botón copia el
  reporte como texto y, si hay `navigator.share`, se puede compartir. ✕ y Escape guardan lo escrito hasta la próxima vez;
  Cancelar lo borra. En un error, lo escrito sigue ahí.
- **La vista** (`observaciones`, `#vistaObservaciones`): lee `buzon/` y `procesado/` de los últimos `OBS_MESES` meses; lo
  mismo en los dos, manda `procesado`. Dice en palabras de una persona qué pasó (`OBS_ESTADOS`) y muestra el `detalle` como
  respuesta. Quien reportó puede retirar lo suyo mientras espera: se borra el mensaje y después sus imágenes.
- **Quién lo atiende**: una persona, con `/Observaciones_Portal` (`.claude/skills/Observaciones_Portal/SKILL.md`), que usa
  `Sistema Intercambio/observaciones.py`. El procesador solo lo cuenta en `estado.json` y la bandeja de pendientes avisa.
- **Pruebas**: desde `test_el_clic_derecho_abre_el_menu_del_portal_y_no_el_del_navegador` en `test_portal.py` (datos de
  mentira; la de punta a punta corre el esquema y la línea de comandos reales) y `Sistema Intercambio/tests/test_observaciones.py`.
