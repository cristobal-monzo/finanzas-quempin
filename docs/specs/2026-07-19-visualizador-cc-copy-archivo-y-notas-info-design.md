# Visualizador Centro de Costos — botón de copiar archivo + notas "i"

**Estado**: aprobado, listo para plan de implementación.
**Módulo afectado**: `Centro de Costos/Visualizador Web/` (`template.html` + `build_visualizador.py`).
Ver [`Centro de Costos/Visualizador Web/CLAUDE.md`](../../../Centro%20de%20Costos/Visualizador%20Web/CLAUDE.md)
para la arquitectura completa del visualizador antes de tocar estos archivos.

## Motivación

Dos pedidos del usuario para mejorar la usabilidad del visualizador ya
implementado:

1. Poder ubicar rápido la foto original de un documento sin tener que
   buscarla a mano por fecha/proveedor en la carpeta compartida.
2. Que los KPIs y gráficos que no son autoexplicativos (qué es "Neto", qué
   significa el ● rojo, qué corta el "top 8") tengan una nota corta al
   alcance, sin recargar visualmente el resto del dashboard.

## 1. Botón de copiar nombre de archivo

### Hallazgo previo (bloqueante)

`build_visualizador.py::extraer_datos_saneados()` hoy **no exporta** la
columna "Archivo origen" de `Master` al snapshot JSON — el dato existe en el
Excel pero nunca llega al HTML. Es un cambio de pipeline, no solo de plantilla.

### Cambio en `build_visualizador.py`

Agregar `"archivo_origen": d.get("Archivo origen")` al diccionario que arma
cada documento en `extraer_datos_saneados()` (junto al resto de campos que
ya se leen de `Master`). Se propaga tal cual al `data/centro-de-costos.json`
y al build embebido — no requiere saneado adicional (es solo un nombre de
archivo, ya sin datos sensibles per se).

### Cambio en `template.html`

- **Ubicación**: un ícono de copiar pequeño en la fila principal de la
  tabla (`doc-row`), junto a la celda de N° Ref., al lado del indicador ●
  de "pendiente de revisión" cuando corresponde. Visible sin necesidad de
  expandir la fila (decisión del usuario: preferible tenerlo siempre a la
  vista antes que solo dentro del panel expandido).
- **Contenido copiado**: solo el nombre de archivo (ej.
  `UMAG-001_Shell_2026-07-15.jpg`), sin ruta ni proyecto.
- **Ícono**: SVG inline (clipboard), color `var(--text-muted)` en reposo,
  `var(--brand-orange-ink, var(--brand-orange))` en hover/focus — mismo
  lenguaje visual que el resto de acentos del sitio. `aria-label="Copiar
  nombre de archivo"` + `title` para accesibilidad.
- **Feedback de copiado**: el ícono se reemplaza por un ✓ (mismo color de
  acento) durante ~1200ms y vuelve a su estado normal. Sin toast, sin
  cambios de layout — debe ser sutil.
- **Mecanismo de copiado** (robustez ante el sandbox de Claude Artifacts):
  1. Intentar `navigator.clipboard.writeText(nombreArchivo)`.
  2. Si falla o la API no existe (`catch`), fallback síncrono: crear un
     `<textarea>` fuera de pantalla, setear su valor, `select()`,
     `document.execCommand('copy')`, remover el elemento.
  3. Si ambos fallan, no romper nada silenciosamente: dejar el ícono en su
     estado normal (sin mostrar el ✓) — un fallo de copiado no debe generar
     un error visible ni bloquear el resto de la fila.
- **Sin archivo_origen**: si el documento no tiene `archivo_origen` (dato
  legado o campo vacío), no renderizar el botón para esa fila.
- El `click` en el ícono debe hacer `stopPropagation()` para no disparar
  también el toggle de expandir/colapsar la fila (que ya escucha click en
  el `<tr>`).

## 2. Notas "i" explicativas

### Componente

Un badge circular pequeño (~14px), borde `1px solid var(--text-muted)`,
"i" en el centro, mismo color. Reutiliza el componente `.viz-tooltip` que
ya existe para los gráficos (mismo estilo visual de burbuja), pero con
contenido estático en vez de datos calculados.

### Interacción

- **Desktop** (dispositivos con hover, detectado vía
  `window.matchMedia('(hover: hover)').matches`): `mouseenter`/`mousemove`
  muestra el tooltip siguiendo el cursor (mismo patrón que
  `showTooltip`/`moveTooltip` ya usado en los gráficos), `mouseleave` lo
  oculta.
- **Touch** (sin hover): `click`/`touchstart` alterna mostrar/ocultar un
  tooltip fijo cerca del ícono (no sigue al dedo). Un tap fuera del
  tooltip lo cierra.
- Accesible por teclado: el badge es focuseable (`tabindex="0"`), `Enter`/
  `Espacio` alterna el tooltip igual que el tap.

### Ubicaciones y contenido (4 puntos acordados)

| Ubicación | Texto de la nota |
|---|---|
| KPI "Pendientes de revisión" | "Documentos con algún dato que no se pudo leer con certeza desde la foto original (ej. N° de documento). Se incluyen en los totales igual, marcados con ● en la tabla, hasta que alguien los revise." |
| KPI "Gasto total (s/IVA)" | "Monto neto, sin el Impuesto al Valor Agregado. Es la base sobre la que se calcula el IVA de cada documento." |
| Gráfico "Top proveedores" | "Los 8 proveedores con mayor gasto acumulado en el rango filtrado. El resto no se oculta: se resume en una nota aparte con el monto total fuera del top 8." |
| Gráfico "Gasto mensual acumulado" | "La línea muestra el acumulado corrido mes a mes, no el gasto de cada mes por separado. Pasa el mouse sobre un punto para ver ambos valores." |

No se agrega nota a ningún otro KPI/gráfico/filtro — el resto se considera
autoexplicativo por su label.

## Fuera de alcance

- No se toca la lógica de `RAIZ_DOCS`, el renombrado de archivos, ni ningún
  otro campo del snapshot.
- No se implementa un visor de la imagen en sí (el visualizador no aloja
  las fotos) — el botón solo resuelve "encontrar el archivo por nombre",
  no mostrarlo embebido.
- No se agregan notas "i" a la tabla de documentos ni a los filtros — solo
  a los 4 puntos listados arriba.

## Verificación

Siguiendo la convención ya documentada en `Visualizador Web/CLAUDE.md`
(dos bugs visuales reales solo se detectaron con navegador real, no con
revisión de código): tras implementar, correr `python driver.py
visualizador`, abrir `build/index.html` con Playwright (`npx playwright
install chromium` ya disponible en este equipo), entrar con la contraseña,
y verificar con screenshots en modo claro y oscuro:

- El ícono de copiar aparece junto al N° Ref., copia el nombre correcto
  (verificable leyendo el clipboard o el estado ✓), y no dispara el
  expand/collapse de la fila.
- Las 4 notas "i" muestran el texto correcto al hover (desktop) — probar
  también con `hasTouch: true` en el contexto de Playwright para simular
  el comportamiento táctil.
- Ambos elementos se ven bien en modo oscuro (el bug histórico de tooltip
  invisible en dark mode fue justo en este componente).
