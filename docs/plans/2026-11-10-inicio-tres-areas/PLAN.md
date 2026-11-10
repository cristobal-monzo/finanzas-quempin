# Inicio del Portal: «Tres áreas» (opción 2, la C4 pulida)

> **Cómo terminó (2026-11-10):** se implementó «Tres áreas» y, al verla en la vista previa, el usuario pidió otra
> versión con **solo las herramientas y sus íconos nuevos, sin la franja «Hoy» ni gráficos**, y publicó esa. Lo que se
> publicó está en `Visualizador Web/portal/docs/interfaz.md` («El Inicio: las herramientas por área»).

Decisión del usuario del 2026-11-10, después de cinco rondas de maquetas. La primera versión (un «centro de
trabajo» con etapas, «Requiere atención», «Continuar» y herramientas) le pareció **«mucha información y algo
confusa»**. Eligió esta: `maqueta-elegida.png` (fuente: `maqueta-elegida.html`, sección `#f2`; las secciones
`#f3` y `#f4` son finalistas descartadas). Datos de la maqueta: de ejemplo.

## El proceso que pidió el usuario (vale más que la regla 11 del CLAUDE.md raíz)

Implementar en local → abrir la vista previa en su navegador → recibir comentarios → ajustar → pedir aprobación →
recién ahí merge y publicar. **Nada de merge, push ni `publicar.py` sin su OK explícito.**

## Lo que lleva la pantalla (de arriba abajo)

1. **Saludo**: «Buenos días, LC» (el usuario elegido). Sin usuario, sus iniciales para elegirse con un clic (ya
   existe: `#iniQuien`, `iniPintarSaludo`).
2. **Franja negra «HOY · N»**: fichas con un punto (rojo urgente, ámbar atención), el N° y el verbo de lo que sigue
   y su plazo corto («N° 900 · Formular · 2 días»). Tocar una ficha hace la acción (`rcIr(t.accion.ir)`). Fuente:
   lo mismo que hoy calcula «Por hacer» de lo propio (`INI_FILTRO.hacer` + `iniDeAlcance`) más los avisos del
   equipo (`iniAvisos`: Planificación sin asignar, obras en riesgo, procesador detenido…), lo urgente primero. Las
   que no caben, en «Ver todo →» (el Recorrido con «Te esperan»: `rcAbrirDesdeInicio('accion')`). Sin usuario: lo
   del equipo.
3. **Cuatro tarjetas**, cada una con su etiqueta, su acción principal (botón naranjo), su cifra, su gráfico simple y
   sus herramientas como botones con ícono (la flecha ↗ en las que abren fuera; el punto naranjo en las que ya
   tienen pestaña, como hoy):
   - **Ofertar** · «+ Requerimiento» (el «Nuevo requerimiento» de la vista Requerimientos: `pqAbrir(null)`) ·
     proyectos vivos de Requerimiento a Oferta · barras por etapa (Requerimiento, Formulación, Cotización,
     Oferta), lo tuyo en naranjo y el resto gris · herramientas del grupo `ofertar`.
   - **Ejecutar** · «Planificar» (`abrir('planificacion')`) · obras en curso (`ejTarjetas('ejecucion')` sin las
     plegadas) · barra de salud (`ejSalud`: en línea, atención, en riesgo) y «N sin nadie» (`plSinAsignarHoy`) ·
     grupo `ejecutar`.
   - **Controlar** · «Subir factura» (`abrir('subir-cc')`) · fecha de los datos financieros =
     `rc.datos.estado.publicaciones['analisis-financiero'].generado` (lo publica el procesador en `estado.json`) ·
     facturas sin asociar (suma de `ejEspera(...).facturas`) y la próxima actualización (el lunes siguiente: tarea
     «Actualizar Finanzas QUEMPIN», lunes 10:00) · grupo `controlar`.
   - **Calcular** (tarjeta angosta) · una línea («Redes, estanques y memorias») · las 4 calculadoras.
4. **Íconos**: dibujos de trazo en la maqueta (`<symbol id="i-…">`), del mismo estilo que `ICONOS` del portal: se
   agregan ahí.
5. **Sin** «Continuar», «Lo que más usas», etapas en tubería ni la lista larga: el usuario pidió menos información.
   Si los pide de vuelta, el código está en el worktree (ver abajo).

Sin datos de la carpeta (sin conectar o sin permiso): la franja dice qué falta con su botón (`pintarSinCarpeta`) y
las tarjetas muestran solo herramientas y acciones, sin cifras.

## Qué ya está hecho en este worktree (rama `inicio-centro`, sin commit)

- **Registro y menú por etapa del trabajo**: grupos `ofertar`, `ejecutar`, `controlar`, `calcular` (+ ayuda), con
  Emitir cotización en Ofertar y Orden de compra en Ejecutar; íconos propios para Gantt, OC, Ingresar avance y
  Emitir cotización; textos de la ayuda y de Configuración y conexiones al día. **Se mantiene.**
- **Cálculos que sirven tal cual** (JS, después del Recorrido, prefijo `ini`): `iniSaludEjecucion` (salud y esperas
  de las obras), `iniAvisos`, `INI_FILTRO`, `iniAlcance`/`iniDeAlcance`, `iniPintarSaludo`, `iniPintarPulso`,
  `iniAjustar` (lo que no cabe va a «+N», con `ResizeObserver`) y los enganches: `ejCargar`, `plPintarAlarmaGlobal`
  y `rcCargar` repintan con `pintarInicioRecorrido()` (una vez por cuadro); un cambio de usuario repinta al
  momento (`iniPintarDatos` en `rcAlCambiarUsuario`).
- **Lo que se reemplaza**: el HTML de `#vistaInicio`, su CSS (bloque «Inicio: el centro de trabajo») y
  `iniPintarEtapas`, `iniPintarAtencion`, `iniFilaProyecto`, `iniPintarSeguir`.
- **Pruebas** (`Visualizador Web/tests/test_portal.py`): las de grupos, menú y conexiones ya están al día. Hay que
  reescribir `test_el_inicio_es_el_centro_de_trabajo`, `test_el_centro_de_trabajo_cabe_en_el_inicio` y
  `test_el_inicio_sin_la_carpeta_dice_que_conectar` para la nueva pantalla. Estado al 2026-11-10: 309 pasan, 3 se
  saltan.
- **Documentación**: `Visualizador Web/portal/docs/interfaz.md` tiene la sección «El Inicio como centro de trabajo»:
  reescribirla para este diseño. `portal/CLAUDE.md` ya enlaza ahí.

## Reglas del Inicio que siguen valiendo

- Sin barras ni desplazamiento en el computador: 1366×657, 1536×730, 1280×600 y 1024×640 (`JS_BARRAS`).
- Teléfono (≤ 900 px de ancho del Inicio): una columna que se desplaza sin barra; ningún texto bajo 12 px; campos
  de 16 px. `py -3.14 "Visualizador Web/auditoria_movil.py" portal` tiene que terminar en «Todo cabe en pantalla».
- Modo oscuro con las variables del portal; foco de teclado visible; botones de verdad (`<button>`).
- Interfaz limpia: dato y acción en pantalla, el porqué en un ⓘ (memoria «Interfaz limpia con ⓘ»).

## Vista previa y capturas

- **En el navegador del usuario, con sus datos**: `py -3.14 "docs/plans/2026-11-10-inicio-tres-areas/vista_previa.py"
  "<worktree>/Visualizador Web" 8765` (en segundo plano) y abrir `http://127.0.0.1:8765/finanzas-quempin/portal/`.
  Sirve el portal del worktree (lo relee en cada carga) y trae las demás herramientas del sitio publicado. En ese
  origen el usuario tiene que conectar la biblioteca y escribir la contraseña una vez.
- **Capturas con los datos de prueba** (sin datos reales): `py -3.14 "docs/plans/2026-11-10-inicio-tres-areas/capturas.py"
  "Visualizador Web/tests" <carpeta fuera del repo> 1366x657 1024x640 390x844` desde la raíz del worktree.

## Antes de publicar (cuando el usuario dé el OK)

Otras sesiones tocan el mismo `portal/index.html` (worktrees `ejecucion-ui2`, `ejecucion-cerrado`,
`ejecucion-gestion`): revisar `git log master` y traer master a la rama antes del merge; suite completa;
`publicar.py portal`; avisar a las otras sesiones (regla 4).
