# Plan — Mejoras del Portal (2026-11-18)

Pedido del usuario: ejecutar las mejoras 1, 2 y 4 de la revisión del 2026-11-18, con las recomendaciones de Claude.
La 3 (todo depende de un solo PC) y la 5 (contraseña común y usuario declarado) quedan pendientes.

Rama y worktree: `mejoras-portal` (`.worktrees/mejoras-portal`). Cada fase entra a `master` con su propio merge cuando
pasa la suite completa, y se publica según la regla 11.

**Orden: 2 → 1 → 4.** La 2 es pequeña y da datos reales sobre errores. La 1 cambia la forma del archivo y conviene
hacerla antes de agregar la vista de teléfono. La 4 parte con maquetas (preferencia del usuario: maquetas simples antes
de la interfaz).

---

## Fase A (mejora 2) — Errores del navegador llegan solos a Observaciones

**Problema:** no hay `window.onerror` ni `unhandledrejection`. Un error en el PC de un compañero no llega a nadie.

1. **Captura** (sección nueva `// ---- Errores sin aviso`, funciones `er*`):
   - `window.addEventListener('error')` y `'unhandledrejection'` en el Portal y en cada herramienta que abre
     (`enganchar` ya entra a cada marco del mismo sitio).
   - Guarda: mensaje, archivo, línea, columna, pila (máximo 4 KB), herramienta, vista activa, `quempin-version`,
     navegador y usuario (`quempin_usuario`). Nunca el valor de un campo ni de una clave.
   - Flujo de Caja (`sinCaptura`): solo mensaje, archivo y línea; sin pila ni texto de la pantalla.
2. **Freno:** una firma = mensaje + archivo + línea. La misma firma se envía una vez por día y por navegador. Máximo
   5 envíos por sesión. Los errores de extensiones del navegador (`chrome-extension://`) y `ResizeObserver loop` no
   se envían.
3. **Envío:** usa el mismo camino de `obsEnviar`: mensaje `observacion` con `clase: "error"` y un campo nuevo
   `automatico: true` (sin imagen). Sin carpeta conectada, queda en `quempin_portal_errores_pendiente` (máx. 20) y sale
   en la próxima conexión.
4. **Esquema:** `Sistema Intercambio/esquemas/mensajes/observacion.json` acepta `automatico` y `tecnico`
   (mensaje, archivo, línea, columna, pila). La `nota` la arma el Portal («Error automático: …»).
5. **Quién lo atiende:** `/Observaciones_Portal` los agrupa por firma («visto 7 veces por 3 personas») y los muestra
   antes que las notas escritas. `observaciones.py` agrupa; el procesador cuenta los automáticos aparte en `estado.json`.
6. **La vista Observaciones:** los automáticos van en un grupo plegado «Errores detectados solos». No se mezclan con
   lo que escribe el equipo.
7. **Pruebas:** un error a propósito en el Portal y en un marco genera un mensaje válido; la misma firma no se repite;
   Flujo de Caja no lleva pila; sin carpeta queda pendiente y sale después; la pila larga se corta.
8. **Documentar** en `docs/observaciones.md`.

Hecho cuando: la suite completa pasa, se publica y un error de prueba en el sitio real llega al buzón.

---

## Fase B (mejora 1) — Partir el Portal en archivos por vista

**Problema:** `index.html` tiene 20 844 líneas y 1,34 MB (el CLAUDE.md dice 12 000 y 850 KB). Todo el JS vive en un
IIFE de 16 000 líneas. `test_portal.py` tiene 7 712 líneas y el CI falla a veces por pruebas inestables.

**Decisión:** archivos `.js` y `.css` normales junto al `index.html`, sin framework ni build. El Portal sigue sin datos.

### B0. Antes de partir
- Las ramas pausadas `carpetas-estados` y `cotizador-exportar` cambian `portal/index.html`. No se tocan: el script de
  partir es reproducible y se corre también en ellas al retomarlas (ver B2).
- Avisar a las otras sesiones (regla 4): nadie edita `portal/index.html` mientras dura la fase B.
- Medir la línea base: tiempo de carga del Portal (en frío y en caliente) y duración de `test_portal.py`.

### B1. Cómo se parte
- `portal/portal.css`: el CSS entero (hoy líneas 18–3351).
- `portal/js/`: un archivo por sección grande, en el orden actual:
  `base.js` (utilidades, menú, marcos, conexiones), `recorrido.js`, `planificacion.js`, `rendiciones.js`,
  `subir.js`, `planilla.js`, `ejecucion.js`, `observaciones.js`, `tema.js`, `inicio.js` (arranque, al final).
- El registro (`portal-registro`) y las conexiones (`portal-conexiones`) siguen dentro de `index.html`: las pruebas y
  `publicar.py` los leen ahí.
- **Alcance común:** se quita el IIFE. Cada archivo es un `<script>` clásico con `'use strict'`; las funciones y los
  `let`/`const` de nivel superior se comparten entre archivos como hoy dentro del IIFE. El arranque que hoy hace
  `return` temprano (portal dentro de otro portal) pasa a una función `arrancar()` en `inicio.js`.
- **Riesgo de este cambio y su guardia:** sin el IIFE, una función de nivel superior llamada `print`, `open`, `close`,
  `stop`, `find`, `name` o `status` taparía la de `window`. Prueba nueva: ningún nombre de nivel superior choca con
  `window` ni se repite entre archivos.
- Scripts con `defer` y en orden fijo. `numeros.js` sigue igual.

### B2. El script que parte (`portal/partir_portal.py`, se borra al terminar la fase)
- Corta por los marcadores `// ---- ` y verifica que la unión de los pedazos sea idéntica al original, sin el IIFE.
- Se corre igual en `carpetas-estados` y `cotizador-exportar` al retomarlas: así el merge solo choca en lo que esa
  rama cambió de verdad.

### B3. Lo que cambia alrededor
- `publicar.py`: `preparar_estatico("portal")` copia `portal.css` y `portal/js/` y verifica cada archivo en línea.
- «Al día sin F5» ya revisa los scripts y hojas del mismo sitio. Se prueba que un cambio en solo un `.js` se detecta.
- `test_portal.py`: helper `texto_portal()` que une `index.html` + `portal.css` + `js/*.js` para las ~42 pruebas que
  buscan texto; el sitio de mentira copia la carpeta entera.
- `test_lo_que_esconde_el_portal_existe_en_cada_herramienta` y `auditoria_movil.py portal` sin cambios.
- `CLAUDE.md` del Portal: tabla con archivo por vista y tamaños reales. Una línea en `Visualizador Web/CLAUDE.md`.

### B4. Pruebas inestables y división de `test_portal.py`
- Leer los registros del CI de las últimas 2 semanas: qué pruebas necesitaron rerun (`--reruns 2`).
- Cambiar cada `sleep`/espera fija de esas pruebas por una espera por condición (como `_esperar`).
- Partir `test_portal.py` por vista (`tests/portal/test_planificacion.py`, …) con un `conftest.py` común. El CI corre
  el mismo comando sobre la carpeta.
- Meta: CI del Portal sin reruns durante 1 semana; después se quita `--reruns 2`.

Hecho cuando: suite completa y auditoría de teléfono pasan, la carga no es más lenta que la línea base, se publica y
el Portal en línea funciona igual en las 10 vistas.

### Cómo quedó (2026-11-18)
- **Línea base** (antes de partir): `test_portal.py` 262 pruebas en 454,6 s. Portal en línea, mediana de 7 cargas hasta
  que el Inicio muestra sus botones: 449 ms con caché vacía (350 KB comprimidos), 140 ms con caché.
- **Partido** desde master e571165: `index.html` 21 150 → 1 194 líneas, `portal.css` 3 338, y 14 archivos en `js/`
  (los de B1 más `conexiones.js`, `inicio.js` = la vista Inicio, `llevar.js`, `buscador.js` y `arranque.js` = el
  arranque, al final). La Planificación estaba cortada por Subir y Rendiciones: sus dos tramos van juntos en
  `planificacion.js` (el segundo solo declara funciones, así que moverlo no cambia nada al cargar).
- **Cambios contra B1:** scripts clásicos sin `defer` al final del `<body>` (igual que antes: corren antes de
  `DOMContentLoaded`). El `return` del portal anidado no pasó a `arrancar()`: va en un `<script>` en línea antes de
  los `js/` que llama a `window.stop()`, así el portal de adentro no carga ninguno (prueba nueva). Se quitó la
  sangría del IIFE: no había plantillas de texto de varias líneas, así que ningún texto cambia.
- **Revisado con acorn** (fuera del repo): ningún nombre de primer nivel se repite ni tapa uno de `window`, y nada que
  corre al cargar un archivo usa algo de un archivo posterior (4 avisos, los 4 falsos: funciones pasadas a
  `setInterval`/`addEventListener`).
- **Scripts de uso único:** `portal/partir_portal.py` (`--desde <ref>` lee el `index.html` de git) y
  `tests/partir_test_portal.py` quedan en el commit de la fase B y se borran en el siguiente. Para
  `carpetas-estados` y `cotizador-exportar`: traer los dos scripts de ese commit, correrlos sobre su versión de una
  pieza y después hacer el merge.
- **publicar.py:** `PARTES` (`portal.css`, `js/`), `?v=<huella>` en cada parte (sin eso, recién publicado, un
  `index.html` nuevo podía correr con un `.js` viejo del caché de 10 min de GitHub Pages), borra los `.js` que ya no
  están, no publica si un script u hoja local enlazado falta, y revisa cambios sin commit también en las partes.
- **Pruebas:** `tests/portal/test_portal_<vista>.py` (13 archivos + `test_portal_archivos.py`), lo común en
  `portal_comun.py`, fixtures por archivo en `conftest.py`. Inestables: en 2 semanas, 5 corridas usaron reintento;
  fallaron más de una vez `test_lo_publicado_de_nuevo_se_carga_sin_f5` (espera fija de 500 ms → espera a que
  `ad.portal` y cada `p.ad` estén leídos) y `test_subir_documentos_llega_a_la_carpeta_del_centro_de_costos` (fallas
  del 2026-11-18 en 4 corridas del mismo minuto, junto con otras pruebas: muy probablemente el código de ese momento,
  no la prueba; no se cambió). El CI sigue con
  `--reruns 2` y ahora `-rR`, que nombra cada reintento: **el 2026-11-25, si ningún log dice RERUN, se quitan**.

---

## Fase C (mejora 4) — El Portal en el teléfono, solo lectura

**Problema:** los datos se arman desde la carpeta de Intercambio con `showDirectoryPicker`, que solo existe en Chrome
y Edge de escritorio. En el teléfono (y en Safari o Firefox) el Portal queda casi vacío, aunque Planificación y
Ejecución ya tienen diseño para teléfono.

**Decisión:** el procesador publica un resumen **cifrado** con el candado de los tableros; el Portal lo lee cuando no
hay carpeta conectada. Solo lectura: escribir desde el teléfono queda fuera de este plan.

### C0. Maquetas primero
- 2 o 3 maquetas simples (imágenes) de cómo se ve en el teléfono: la semana de la Planificación, «cómo va» de un
  proyecto en ejecución y la lista de Requerimientos. El usuario elige antes de programar.
- Se decide en esta ronda qué vistas entran. Propuesta: Planificación (semana, quién va dónde, vehículos), Ejecución
  (avance y alertas por proyecto, sin precios de proveedores) y Requerimientos (lista y estado).
- **Fuera:** Flujo de Caja (decisión del 2026-10-02), precios de referencia, observaciones y rendiciones.

### C1. El resumen (`Sistema Intercambio/resumen_movil.py`)
- Paso nuevo del procesador. Arma `resumen-movil` desde `publicado/` (lo que el Portal ya lee) y lo cifra con
  `candado.cifrar_bytes` (gzip + AES-GCM, contraseña del equipo de `.contrasena_tableros`).
- Esquema nuevo: `esquemas/publicaciones/resumen-movil.json` (regla 2: dato nuevo que viaja = esquema nuevo).
- Lleva su hora de armado; el Portal la muestra siempre («Datos de las 14:35»).

### C2. Cómo llega al teléfono
- Se publica en `gh-pages` como `portal/datos/resumen.json` (cifrado), con `publicar.py` y su guardia de candado
  (nunca se publica algo que no abre con la contraseña del equipo).
- **Frecuencia:** solo si cambió el contenido, como máximo cada 30 minutos, de lunes a sábado de 7:00 a 20:00.
- **Peso del historial de `gh-pages`:** se mide el tamaño del sobre en C1. Si un mes de publicaciones pasa de
  100 MB, se propone al usuario otra salida (rama aparte o recorte del historial); no se hace sin su OK porque pide
  `--force`.
- La tarea programada necesita poder hacer push: se usa la misma credencial que `publicar.py`.

### C3. El Portal sin carpeta
- `obsPreparar` y las vistas ya saben que no hay carpeta. En ese caso, en lugar del aviso «falta la carpeta»,
  cargan `datos/resumen.json`, lo abren con `QuempinCandado.abrirArchivo` (clave ya recordada) y pintan en modo
  lectura: botones de editar ocultos, una franja «Solo lectura · datos de las HH:MM».
- Si el resumen tiene más de 2 horas, la franja se pone ámbar y lo dice.
- Con carpeta conectada todo sigue como hoy; el resumen no se usa.

### C4. Pruebas
- `resumen_movil.py`: con datos de mentira, arma un sobre válido contra el esquema, abre con la contraseña de prueba
  y no lleva Flujo de Caja ni precios.
- Portal en Chromium emulando un teléfono sin `showDirectoryPicker`: las vistas elegidas muestran datos, no hay
  botones de editar y la franja dice la hora.
- `auditoria_movil.py portal` a 360/390/768 px.

Hecho cuando: suite completa pasa, se publica, y en un teléfono real con la contraseña del equipo se ve la semana
de la Planificación con la hora del resumen.

### Cómo quedó (2026-11-18)
- **Maquetas:** 4 ideas (M1 pestañas abajo, M2 todo en una página, M3 el Inicio de siempre, M4 lo mío). El usuario
  eligió **M3** y pidió que las calculadoras queden. En el Inicio del teléfono se apagan solo Subir, Rendiciones,
  Emitir cotización y Orden de compra (`iniApagada`); los tableros y las calculadoras siguen, porque ya funcionaban.
- **Distinto de lo planeado:**
  - Las vistas no se reescribieron para el resumen: `js/resumen.js` arma una carpeta de mentira de solo lectura con
    la misma forma que la de verdad, y `rcCargar` se la pasa a todas. Así entran también el Recorrido y la semana del
    Inicio, y la Ejecución se ve igual que en el computador, con las cotizaciones de las compras: todo va detrás de la
    contraseña del equipo, igual que el tablero del Centro de Costos, que ya muestra cada factura.
  - Sin esquema en `esquemas/`: el resumen no viaja por la carpeta de Intercambio; lleva copias de publicaciones que
    ya tienen el suyo.
  - En vez de un solo `resumen.json`, una parte cifrada por tema (`base`, `planificacion`, `ejecucion`, `formulador`,
    `estado`) e `indice.json` sin cifrar con la hora y las huellas: una parte que no cambió conserva su sobre y no
    agranda el historial de `gh-pages`. Medido: ~300 KB en total (formulador 139, ejecución 84, base 66).
  - La subida no pasa por `.worktrees/gh-pages`: `publicar.subir_carpeta_aparte` arma el commit sobre
    `origin/gh-pages` con un índice temporal, para no chocar con una sesión que esté publicando. `revisar_gh_pages`
    pone al día esa carpeta sola si no tiene nada a medias.
  - Además de «si cambió, cada 30 min», un latido cada hora: sin él, la franja se pondría ámbar con datos al día.
- **Frenos:** cada función que cambia algo empieza con `mvNoSe()` (aviso «Solo lectura…»); lo que corre solo
  (presencia, uso, guardar) con `soloLectura()`; lo que solo sirve para cambiar se esconde con `html.solo-lectura`.
- **Falta (no se puede desde aquí):** abrirlo en un teléfono real con la contraseña del equipo.

---

## Fuera de este plan
- Mejora 3: segunda máquina o aviso fuera del Portal cuando el procesador no corre. Nota: la fase C depende del
  mismo PC; si está apagado, el teléfono muestra datos viejos con la franja ámbar.
- Mejora 5: identidad real y acceso por persona (p. ej. Cloudflare Access).
- Escribir desde el teléfono (Planificación, rendiciones).
