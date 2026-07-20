# Visualizador Web — diseño

Fecha: 2026-07-19

## Contexto

`Finanzas QUEMPIN` consolida módulos financieros independientes (Centro de
Costos, Cotizador Historico, y a futuro Flujo de Caja y otros). Cada módulo
hoy solo se puede consultar abriendo su Excel o corriendo su skill de Claude
Code. El usuario quiere que cada módulo, a futuro, tenga además un
visualizador web — un HTML publicado online con la interfaz, información y
herramientas (gráficos, tablas dinámicas, buscadores, filtros, y
eventualmente un consultor IA) de ese módulo específico.

Este spec cubre **solo la etapa de scaffolding**: crear la carpeta
`Visualizador Web/` para cada módulo (más una a nivel raíz para el doc
maestro compartido) y los `CLAUDE.md` que guiarán el desarrollo futuro de
cada HTML. **No cubre escribir el HTML/CSS/JS real** — eso es trabajo
posterior, uno por módulo, cada uno con su propio ciclo de diseño cuando se
aborde.

## Alcance

Incluye:
- `Finanzas QUEMPIN/Visualizador Web/CLAUDE.md` — doc maestro compartido por
  los tres (y futuros) visualizadores.
- `Centro de Costos/Visualizador Web/CLAUDE.md` — borrador de contenido a
  presentar.
- `Cotizador Historico/Visualizador Web/CLAUDE.md` — borrador de contenido a
  presentar.
- `Flujo de Caja/Visualizador Web/CLAUDE.md` — placeholder (el módulo base
  todavía no existe).
- Referencia desde `Finanzas QUEMPIN/CLAUDE.md` (raíz) hacia el maestro.
- Regla nueva en `.gitignore` para las futuras carpetas `data/` de exports.

No incluye: elegir/instalar ninguna librería de gráficos, escribir ningún
`index.html`, ni decidir el mecanismo final de control de acceso del sitio
publicado (queda como decisión pendiente explícita, ver más abajo).

## Por qué `CLAUDE.md` y no un nombre genérico

El repo ya tiene la convención de que cada módulo trae su propio `CLAUDE.md`
con instrucciones de cómo trabajar ahí. Nombrar así también estos archivos
significa que una sesión futura de Claude Code que trabaje dentro de
`Centro de Costos/Visualizador Web/` carga ese archivo automáticamente como
contexto de proyecto. El maestro de la raíz (`Visualizador Web/CLAUDE.md`)
**no** se auto-carga en las subcarpetas de módulo — no son ancestro/
descendiente en el árbol de directorios — así que cada `CLAUDE.md` de módulo
debe enlazarlo explícitamente en su texto, igual que hoy
`Cotizador Historico/CLAUDE.md` enlaza a `../CLAUDE.md` y a
`../Centro de Costos/CLAUDE.md`.

## Estructura de carpetas

```
Finanzas QUEMPIN/
├── CLAUDE.md                          # editado: referencia nueva a Visualizador Web/CLAUDE.md
├── docs/superpowers/specs/            # NUEVO a nivel raíz (mismo patrón que cada módulo)
│   └── 2026-07-19-visualizador-web-design.md
├── Visualizador Web/                  # NUEVO
│   └── CLAUDE.md                      # doc maestro compartido
├── Centro de Costos/
│   └── Visualizador Web/              # NUEVO
│       └── CLAUDE.md                  # contenido a presentar (borrador)
├── Cotizador Historico/
│   └── Visualizador Web/              # NUEVO
│       └── CLAUDE.md
└── Flujo de Caja/
    └── Visualizador Web/              # NUEVO
        └── CLAUDE.md                  # placeholder
```

Cuando más adelante se construya el HTML real de un módulo, su carpeta
`Visualizador Web/` crecerá con `index.html`, `css/`, `js/`, `assets/` (copia
o referencia al material gráfico necesario) y `data/` (exports saneados,
gitignored) — documentado como convención esperada en el maestro, pero no
creado todavía en este scaffolding.

## Contenido del maestro (`Visualizador Web/CLAUDE.md`)

1. **Rol**: comportarse como desarrollador experto en HTML/UI/UX —
   maquetación responsiva, accesibilidad básica (contraste, foco de
   teclado), sin frameworks pesados salvo que el propio módulo lo justifique.
2. **Manual de marca**: fuente de verdad es
   `Material gráfico QUEMPIN/OFICIAL MANUAL DE MARCA GRÁFICA QUEMPIN.pdf` +
   `LOGO QUEMPIN.PNG` (y el resto de `Material gráfico QUEMPIN/`) — nunca
   inventar colores/tipografía/logo; si el manual no cubre un caso puntual
   de UI, extrapolar de forma conservadora y dejarlo anotado en el
   `CLAUDE.md` del módulo correspondiente.
3. **Mandato de herramientas dinámicas**: todo visualizador debe incluir,
   como mínimo:
   - Al menos un gráfico interactivo (tooltip/hover, no imagen estática).
   - Al menos una tabla dinámica (orden por columna, búsqueda, filtro).
   - Un buscador de texto libre.
   - Filtros por las dimensiones relevantes de ese módulo (definidas en su
     propio `CLAUDE.md` de contenido).
   - Un "consultor IA" que responda preguntas sobre los datos del módulo es
     **deseable pero opcional por módulo** — requiere backend o llamada a
     una API con key (no es 100% estático), así que cada módulo decide si y
     cómo lo implementa cuando le toque su propio diseño.
4. **Datos — export estático saneado (obligatorio)**: el HTML publicado
   nunca lee directamente el `.xlsx`/JSON fuente de un módulo. Cada módulo
   define su propio paso de export (script o función) que genera un
   snapshot JSON agregado/saneado hacia `<Módulo>/Visualizador Web/data/`;
   el HTML solo lee ese snapshot. "Saneado" se define por módulo (qué
   columnas/agregaciones expone) en su propio `CLAUDE.md` de contenido.
5. **Hosting**: GitHub Pages recomendado — un solo sitio servido desde este
   repo, con subrutas por módulo (`/centro-de-costos/`,
   `/cotizador-historico/`, `/flujo-de-caja/`) en vez de 3 despliegues
   independientes. Puede migrarse a otro host (Netlify/Vercel) sin rediseño
   porque es HTML estático.
6. **Punto abierto — control de acceso (no bloqueante)**: GitHub Pages sobre
   un repositorio público sirve el sitio a cualquiera con el link (o
   indexable por buscadores). Dado que los datos de origen son financieros
   reales de la empresa, **antes de publicar el primer visualizador con
   datos reales** hay que decidir con el usuario: repo privado + Pages de
   pago, alguna gate de acceso client-side, o servir detrás de un proxy con
   autenticación. Este spec no lo resuelve — solo lo deja explícitamente
   anotado para que no se publique data real sin decidirlo antes.
7. **Convención de `data/` y git**: las carpetas `data/` de cada módulo
   (exports saneados) se agregan a `.gitignore` — igual que el resto de
   datos financieros reales del repo — porque incluso "saneado" puede seguir
   conteniendo información no destinada a control de versiones; el código
   que genera el export sí se versiona.

## Contenido borrador por módulo

### Centro de Costos (`Centro de Costos/Visualizador Web/CLAUDE.md`)

Fuente: `Centro de Costos/Excel/Centro de Costos.xlsx` (hojas `Master` +
`Detalle`).

- **KPIs**: gasto total (con/sin IVA), gasto por proyecto, gasto por
  categoría, cantidad de documentos, documentos pendientes de revisión
  (celdas rojas / sin N° de documento).
- **Tabla dinámica**: una fila por documento (`Master`) con expansión a sus
  ítems (`Detalle`); columnas ordenables; búsqueda de texto libre sobre
  proveedor/ítem/N° documento.
- **Gráficos**: barras de gasto por proyecto, dona de gasto por categoría,
  línea temporal de gasto mensual, ranking de top proveedores.
- **Filtros**: proyecto, tipo de proyecto, categoría, estado, rango de
  fechas.
- **Export saneado sugerido**: agregados por proyecto/categoría/mes/
  proveedor, más el detalle de documento (sin exponer campos que el usuario
  no quiera público, ej. posible ocultamiento de razón social completa si el
  sitio termina siendo público — a decidir junto con el punto abierto de
  control de acceso del maestro).

### Cotizador Historico (`Cotizador Historico/Visualizador Web/CLAUDE.md`)

Fuente: misma `Centro de Costos.xlsx` vía la lógica de
`Sistema/cotizador_historico.py` (búsqueda difusa + reajuste UF).

- **Buscador difuso** de ítem (reusa `buscar_items`), con sugerencias de baja
  similitud si no hay match exacto — mismo comportamiento que el driver
  actual, pero en UI.
- **Vista de resultado**: compras individuales encontradas (fecha, proyecto,
  proveedor, precio original y ajustado por UF con/sin IVA), promedio y
  rango.
- **Gráfico**: evolución del precio ajustado por UF en el tiempo para el
  ítem consultado.
- **Filtros**: por proyecto de origen de la compra, rango de fechas.
- **Export saneado sugerido**: snapshot de ítems indexados (nombre,
  descripción, categoría, precio unitario, fecha, proyecto) — sin necesidad
  de llamar a la API de UF en vivo desde el navegador; el reajuste puede
  precalcularse al momento del export o recalcularse client-side si el
  export incluye el valor UF de cada fecha histórica ya resuelto.

### Flujo de Caja (`Flujo de Caja/Visualizador Web/CLAUDE.md`)

Placeholder — el módulo base (`Flujo de Caja/CLAUDE.md`, script,
`Sistema/`) todavía no existe (ver tabla de módulos en el `CLAUDE.md` raíz).
El archivo deja la estructura de secciones vacía (KPIs, tabla dinámica,
gráficos, filtros, export saneado) con una nota de que debe completarse
recién cuando el módulo Flujo de Caja se implemente y su esquema de datos
esté definido — enlaza al maestro igual que los otros dos.

## Fuera de alcance de este spec

- Escribir el HTML/CSS/JS de cualquier visualizador.
- Elegir librería de gráficos/tablas concreta.
- Resolver el control de acceso del sitio publicado (queda como punto
  abierto documentado).
- Cualquier contenido real de Flujo de Caja (el módulo no existe aún).
