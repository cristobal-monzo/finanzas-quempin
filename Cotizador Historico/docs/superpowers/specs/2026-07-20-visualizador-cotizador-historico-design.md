# Diseño: Visualizador Web de Cotizador Historico

Fecha: 2026-07-20. Ver `../../CLAUDE.md` (diseño del módulo Cotizador
Historico) y `../../../Visualizador Web/CLAUDE.md` (doc maestro de todos los
visualizadores — rol, manual de marca, mandato de herramientas dinámicas,
política de datos, hosting) para el contexto que este documento no repite.
Ver también `../../../Centro de Costos/Visualizador Web/CLAUDE.md` — este
diseño reutiliza deliberadamente su arquitectura, paleta y patrones ya
probados en producción, en vez de reinventarlos.

## Objetivo

Un visualizador web para Cotizador Historico que permita buscar un ítem por
palabra clave (ej. "bomba") y ver cada compra histórica que calza como una
referencia individual — con sus características técnicas, su costo
revalorizado a la UF vigente al momento de publicar, destacado con
claridad — y armar una "cotización" seleccionando una o varias referencias
(con cantidad) en un carrito de sesión, exportable a un archivo listo para
abrir en Excel, separado por Materiales/Equipos/Otros.

## Arquitectura

Mismo patrón que Centro de Costos, con datos incrustados en un solo HTML
autocontenido (sin `fetch`, apto para Claude Artifact):

```
Cotizador Historico/Visualizador Web/
├── CLAUDE.md               # contenido — se actualiza al implementar
├── template.html           # estructura/CSS/JS + logo, SIN datos — versionado
├── build_visualizador.py   # export + build — versionado
├── data/                   # snapshot intermedio (gitignored)
└── build/                  # index.html final, autocontenido (gitignored)
```

Un solo comando regenera todo: nuevo subcomando `visualizador` en
`.claude/skills/Cotizador_Historico/driver.py` (mismo patrón que
`driver.py visualizador` de Centro de Costos), que invoca
`build_visualizador.py`.

### Por qué no hay UF "en vivo"

Se evaluó que el HTML publicado pidiera la UF del día directo a
`mindicador.cl` al abrirse. Se descartó: los Artifacts de Claude solo
exponen las capabilities `downloads` y `mcp` — no existe una capability de
"fetch a cualquier API externa", y `mindicador.cl` no es un conector MCP.
El sandbox del Artifact bloquea ese fetch (misma razón por la que Centro de
Costos incrusta todo). **Decisión: la UF se fija al momento del build**,
igual que Centro de Costos fija su "última actualización de los datos" —
`build_visualizador.py` pide la UF de hoy una sola vez (vía
`Sistema/cotizador_historico.py::consultar_uf_api`) y la incrusta en el
snapshot. El header del visualizador muestra, bien visible: "UF utilizada:
$X — actualizada DD-MM-AAAA HH:MM". Regenerar y republicar (mismo link,
igual que Centro de Costos) es el mecanismo para refrescarla.

### Branding y gate — reutilizados sin cambios

- Mismos 4 colores oficiales del manual de marca QUEMPIN: `#ff5100`
  (Pantone Orange 021 C), `#000000` (Black C), `#98989a` (Cool Gray 7 C),
  `#54565a` (Cool Gray 11 C). Sin colores "parecidos" nuevos.
- Misma tipografía Lato embebida en base64 (sin CDN).
- Mismo header negro con logo + wordmark, mismo botón claro/oscuro con las
  variables CSS `--surface-*`/`--text-*` ya definidas para ambos temas.
- Mismo gate de contraseña — **contraseña "combustion"** (normalizada igual
  que en Centro de Costos: minúsculas, sin tilde), con el mismo disclaimer
  de "no es seguridad real". Vive como constante en `template.html`, igual
  patrón que el otro módulo.
- Publicación: Claude Artifact privado, mismo mecanismo de "siempre
  actualizar el mismo link" que ya usa Centro de Costos (una vez publicado
  por primera vez, el link se registra en el `MEMORY.md` del skill
  `Cotizador_Historico`).

## Datos — export saneado

`build_visualizador.py` lee `Centro de Costos/Excel/Centro de Costos.xlsx`
(Detalle + Master, solo lectura — este módulo nunca lo escribe, igual que
`cotizador_historico.py`) y arma un índice de **todos los ítems
indexables** de `Detalle` (mismo criterio de exclusión que
`cargar_items_detalle`: fuera del índice si no tiene fila en `Master`, la
fecha no es válida, o el precio unitario no es un número), enriquecido con
campos que `cotizador_historico.py` no expone hoy porque el CLI no los
necesita:

- `nombre_item`, `descripcion` (ya existían)
- `categoria_item` (columna "Categoría Ítem" de `Detalle`, columna nueva a
  leer — necesaria para el export del carrito)
- `proyecto`, `proveedor_tag` (vía `Master`, cruzado por `N° Ref.`, mismo
  join que ya hace `Master`↔`Detalle`)
- `n_ref`, `fecha`

Para cada ítem indexable se precalcula, con la UF de hoy fijada al momento
del build (ver arriba) y la tasa real de IVA del documento
(`tasa_iva_real`, igual que el CLI — nunca 19% fijo):
`precio_reajustado_hoy_sin_iva`, `precio_reajustado_hoy_con_iva`.

**La búsqueda ocurre 100% en el navegador**, contra este índice ya
precalculado — no hay ninguna llamada de red en tiempo de uso. Se necesita
portar a JS la lógica de `similitud()`/`buscar_items()` de
`cotizador_historico.py`:

- Normalización (minúsculas, sin tildes — igual que `normalizar_texto`).
- Match 1.0 si la consulta es substring del nombre/descripción o viceversa,
  o si alguna palabra de ≥4 caracteres de la consulta es substring del
  nombre/descripción (o viceversa) — cubre "guantes" contra "Guante de
  trabajo cuero spandex".
- Si no hay match directo: ratio de similitud aproximado tipo
  Dice/bigramas como fallback tolerante a typos, para generar sugerencias
  cuando no hay coincidencia (no necesita ser idéntico al `SequenceMatcher`
  de Python — es solo para sugerencias de baja similitud, no para el
  resultado principal).

Snapshot intermedio auditable en `data/cotizador-historico.json` (mismo rol
que `data/centro-de-costos.json` de Centro de Costos), incrustado en
base64 dentro de `template.html` para producir `build/index.html`.

## UI — estado inicial (antes de buscar)

Cumple el mandato del maestro (gráfico interactivo + tabla dinámica +
buscador + filtros) desde la carga:

- **KPI row**: total de ítems indexados en el índice, N° de productos
  distintos (por `nombre_item`), cobertura (cuántos quedan excluidos por
  falta de fecha/precio válido), UF utilizada + fecha de esa UF.
- **Gráfico de barras**: Top 10 productos (`nombre_item`) con más compras
  históricas registradas.
- **Tabla dinámica — índice de productos**: una fila por `nombre_item`
  distinto, con N° de compras, rango de precio reajustado (min-max) y
  proyectos involucrados; ordenable por columna. Al hacer clic en una fila,
  carga ese texto en el buscador y dispara la búsqueda (conecta la tabla
  con el flujo principal).
- **Filtros**: Proyecto, Categoría, rango de fechas — acotan qué compras
  entran a la búsqueda y a la tabla índice.

## UI — buscador y resultados

- Input de texto libre con debounce de 150ms (mismo valor que usa la tabla
  de Centro de Costos).
- Resultado: lista plana de tarjetas, **una por compra individual** (no
  agrupadas por producto) — decisión explícita: cada compra puede tener
  marca/modelo/specs distintos aunque comparta `nombre_item`, así que
  agrupar escondería esa diferencia.
- Cada tarjeta trae:
  - `nombre_item` como título.
  - **Chips de specs técnicas** extraídos de `descripcion` con un parser
    por patrones (best-effort, heurístico): marca (palabra capitalizada
    tras la primera posición, excluyendo coincidencias de specs),
    modelo (token alfanumérico mixto adyacente a la marca), y unidades
    técnicas vía regex — potencia (HP/kW/W/CV), caudal (L/min, GPM, m³/h),
    voltaje (V), presión (bar/psi), capacidad (L, kg), dimensión (mm, cm,
    pulgadas). Si el parser no encuentra nada reconocible, no se fuerza
    ningún chip — solo queda la descripción completa.
  - Descripción completa siempre visible como respaldo (nunca se oculta
    información, los chips son un resumen visual encima, no un reemplazo).
  - N° Ref., proyecto, proveedor (tag corto), fecha de la compra original.
  - **Costo revalorizado a la UF actual, destacado en tamaño grande**
    (con IVA como cifra principal, sin IVA como secundaria) — precio
    original histórico en texto pequeño/muted debajo, para contexto.
  - Término buscado resaltado (bold) dentro de nombre/descripción.
- Ordenadas por relevancia (score de `similitud`). Se muestran las **5 más
  relevantes**; si hay más, un botón "Ver las N referencias" despliega el
  resto (sin recargar ni perder el scroll).
- Barra de resumen sobre las tarjetas: promedio reajustado, rango
  (mín-máx), conteo total de referencias encontradas.
- Sin match: "No se encontraron referencias para '<texto>'." + hasta 5
  sugerencias de similitud baja (igual criterio que el CLI).
- Mini-tendencia (sparkline) en la barra de resumen cuando el mismo
  `nombre_item` de la búsqueda tiene ≥2 compras en fechas distintas —
  evolución del precio reajustado en el tiempo.

## Carrito de cotización

**Sin persistencia entre sesiones** — vive solo en una variable JS en
memoria; recargar la página lo vacía. No se usa `localStorage` ni
`sessionStorage` para esto, es la forma más directa de cumplir "no debe
guardarse entre sesiones".

- Cada tarjeta tiene un stepper de cantidad (mínimo 1, por defecto 1) +
  botón "Agregar al carrito". Si la referencia ya está en el carrito, la
  cantidad se suma a la existente. Confirmación visual breve en el botón.
- Botón flotante con ícono de carrito + badge de contador (con una
  animación breve al cambiar) abre un panel lateral (drawer) con:
  - Una línea por ítem: nombre + chips de specs, cantidad (editable ahí
    también), precio unitario reajustado, subtotal, botón de quitar.
  - Total general (con y sin IVA) del carrito completo.
  - Botón "Exportar cotización" (deshabilitado si el carrito está vacío).

### Exportación

Restricción real de la plataforma verificada contra la documentación de
capabilities: `window.claude.downloads.save()` solo acepta extensiones
`gif png jpg jpeg webp mp4 webm txt json md` — **`.xlsx` y `.csv` están
fuera del allowlist** y se rechazan (`rejected_extension`). No es una
limitación de este diseño, es del runtime del Artifact.

**Decisión**: exportar un archivo `.txt` con columnas separadas por
tabulador — Excel lo abre correctamente vía "Archivo > Abrir" (detecta las
columnas solo) o renombrando la extensión a `.csv`. El botón de exportar
incluye una nota breve explicando ese paso extra.

Contenido del archivo, `cotizacion-QUEMPIN-<fecha ISO>.txt`:

- Encabezado: fecha de generación, UF utilizada (la misma fijada en el
  build).
- Tres secciones con título propio, en este orden: **MATERIALES**,
  **EQUIPOS**, **OTROS**. Mapeo desde `categoria_item` de cada línea del
  carrito: `"Materiales"` → Materiales; `"Equipos-Herramientas"` →
  Equipos; cualquier otro valor (`Transporte`, `Consumibles`,
  `Combustible`, o sin categoría) → Otros. Ninguna línea del carrito se
  descarta por no calzar en las dos categorías principales.
- Columnas por línea: Nombre Ítem, Descripción (specs), Cantidad, Precio
  unitario reajustado sin IVA, Precio unitario reajustado con IVA,
  Subtotal con IVA, N° Ref. de referencia, Fecha de la compra de
  referencia, Proyecto.
- Subtotal al final de cada sección (si tiene ítems) + total general al
  final del archivo.

Mecanismo de descarga: declarar la capability `downloads: true` al
publicar el Artifact, y llamar `window.claude.downloads.save({filename,
data})` con el texto ya armado. Si `window.claude.downloads` no existe
(ej. alguien abre `build/index.html` local, fuera del Artifact), fallback
a una descarga de `Blob` + `<a download>` normal — mismo contenido, mismo
nombre de archivo, sin capability de por medio.

## Testing / verificación

Antes de dar por terminada la implementación:

- Tests de pytest para `build_visualizador.py` (siguiendo el patrón de
  `Centro de Costos/Visualizador Web/tests/test_build_visualizador.py`):
  extracción del índice, join Detalle↔Master, mapeo de categorías a
  Materiales/Equipos/Otros, cálculo del reajuste con UF inyectada (sin
  llamar a la red en tests).
- Verificación visual con Playwright (ya instalado en este equipo, mismo
  approach que usó el ciclo de mejora continua de Centro de Costos): abrir
  `build/index.html`, entrar con la contraseña, buscar un término real que
  exista en los datos, agregar ≥2 referencias distintas al carrito con
  cantidades distintas, exportar, y confirmar visualmente que las
  tarjetas, el destacado de UF, el botón "ver todas", el carrito y el
  archivo exportado se comportan como se espera — no solo revisión de
  código (precedente: 2 bugs reales de Centro de Costos que el review de
  código no detectó).

## Fuera de alcance (v1 de este visualizador)

- Consultor IA en lenguaje natural (opcional/deseable según el maestro, no
  se implementa en esta iteración).
- Edición/guardado del carrito entre sesiones (explícitamente rechazado
  por el usuario).
- Generación de un `.xlsx` real con múltiples hojas — bloqueado por el
  allowlist de la capability `downloads`; si en el futuro el runtime de
  Artifacts agrega esa extensión al allowlist, migrar el export sería un
  cambio acotado a la función de export en `template.html`, sin tocar el
  resto del diseño.
