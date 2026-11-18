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

---

## Fuera de este plan
- Mejora 3: segunda máquina o aviso fuera del Portal cuando el procesador no corre. Nota: la fase C depende del
  mismo PC; si está apagado, el teléfono muestra datos viejos con la franja ámbar.
- Mejora 5: identidad real y acceso por persona (p. ej. Cloudflare Access).
- Escribir desde el teléfono (Planificación, rendiciones).
