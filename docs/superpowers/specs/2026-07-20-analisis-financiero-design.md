# Diseño: módulo Análisis Financiero

Fecha: 2026-07-20
Estado: aprobado por el usuario (brainstorming), pendiente de plan de implementación.

## Qué es

`Análisis Financiero` es un módulo nuevo de `Finanzas QUEMPIN` cuyo rol es **consolidar
cross-módulo**: toma los costos reales que ya calcula Centro de Costos (por proyecto,
por categoría de ítem) y los cruza contra ventas y costos proyectados que el usuario
carga a mano, para dar una vista de rentabilidad por proyecto. No reemplaza a Centro
de Costos ni le duplica lógica — solo lo lee.

A futuro debería poder incorporar Flujo de Caja como fuente adicional, cuando ese
módulo exista.

## Por qué

El usuario ya tiene una carpeta `Análisis Financiero/` con un Excel en blanco
(`Análisis de Proyectos.xlsx`) pensado para llevar, por proyecto: monto de venta,
costos proyectados por categoría, y costos reales por categoría — para poder ver
margen y desviación real vs. proyectado a medida que el proyecto avanza. Hoy ese
cruce (costos reales por proyecto) ya existe en Centro de Costos pero no en una
vista consolidada por proyecto con venta y proyección.

## Alcance v1

- **Fuente de datos real**: solo Centro de Costos (`Centro de Costos/Excel/Centro de
  Costos.xlsx`, hoja `Detalle`). Solo lectura — este módulo nunca escribe ahí.
- **Categorías con costo real automático**: Materiales y Equipos (agregadas desde
  `categoria_item` de Centro de Costos). **Mano de Obra Real queda 100% manual** —
  hoy no existe esa categoría en los datos de Centro de Costos (boletas de
  honorarios, planillas); si aparece una fuente en el futuro, se automatiza en una
  iteración posterior, no en esta.
- **TAG de proyecto = prefijo de Centro de Costos** (`PREFIJOS_PROYECTO` /
  `N° Ref.`, ej. `UMAG`, `CFLI`, `CCON`, `GGEN`, `MLER`) — mismo identificador en
  ambos módulos, sin mapeo aparte que mantener sincronizado.
- **Disparo**: encadenado al `run` de Centro de Costos (`Sistema/
  auditor_centro_costos.py`, nuevo paso 12d, después del paso 12c del Visualizador
  Web) — cada corrida de Centro de Costos deja `Análisis de Proyectos.xlsx` al día
  solo. También disponible como skill aparte para refrescar sin correr todo Centro
  de Costos.
- **Creación de carpetas de proyecto**: si una fila nueva aparece en
  `Análisis de Proyectos.xlsx` (TAG que no tiene carpeta), el módulo crea
  `Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/
  <Nombre del proyecto>/` (fuente real que lee Centro de Costos hoy — **no** la
  carpeta legado `Centro de Costos/Facturas y Boletas/`, que el script ya no lee
  desde 2026-07-17). Nombre completo del proyecto, no el TAG, para calzar con la
  convención de nombres de carpeta que ya usa Centro de Costos.
- Sin registro de estado aparte: la existencia de la carpeta en disco es la fuente
  de verdad de "¿ya se creó?" — no se mantiene un JSON de "proyectos conocidos".

## Estructura del módulo

```
Análisis Financiero/
├── CLAUDE.md                              # charter del módulo
├── Análisis de Proyectos.xlsx             # libro de trabajo (ya existe, hoy vacío)
├── Respaldos/                             # backups automáticos, por mes, antes de cada escritura
├── Sistema/
│   ├── analisis_financiero.py             # lógica: leer Centro de Costos.xlsx, agregar reales, crear carpetas
│   └── tests/
├── docs/superpowers/                      # este spec + futuros planes
└── .claude/skills/Registro_Analisis_Financiero/
    ├── SKILL.md
    ├── MEMORY.md                          # preferencias/histórico del skill
    └── driver.py                          # comandos: status | run
```

## `Análisis de Proyectos.xlsx`

### Hoja "Proyectos" (resumen, una fila por proyecto)

| Columna | Origen | Notas |
|---|---|---|
| TAG proyecto | manual | = prefijo de Centro de Costos |
| Nombre del proyecto | manual | usado para nombrar la carpeta en Centro de Costos |
| Estado | manual | ej. Adjudicado / En curso / Cerrado |
| Fecha de inicio | manual | |
| Fecha de cierre | manual | |
| Monto de Venta (sin IVA) | manual | |
| Costos Materiales Proyectados | manual | |
| Costos Equipos Proyectados | manual | |
| Mano de Obra Proyectada | manual | |
| Otros Costos Proyectados | manual | |
| Costos Materiales Reales | **fórmula** `SUMIFS` sobre hoja "Detalle Costos Reales" (TAG + Bucket=Materiales) |
| Costos Equipos Reales | **fórmula** `SUMIFS` (TAG + Bucket=Equipos) |
| Otros Costos Reales | **fórmula** `SUMIFS` (TAG + Bucket=Otros) |
| Mano de Obra Real | manual | sin fuente automática en v1 |
| Total Proyectado | fórmula: suma de los 4 proyectados |
| Total Real | fórmula: suma de los 4 reales (3 automáticos + MO manual) |
| Margen Proyectado | fórmula: Venta − Total Proyectado |
| Margen Real | fórmula: Venta − Total Real |
| Desviación % (Real vs Proyectado) | fórmula: Total Real / Total Proyectado − 1 |

Todas las columnas manuales se respetan entre corridas (regla de oro heredada de
Centro de Costos) — el script nunca las toca, solo escribe la hoja "Detalle Costos
Reales" y las fórmulas de la hoja "Proyectos" si faltan.

### Hoja "Detalle Costos Reales" (una fila por proyecto + subcategoría)

100% regenerada en cada corrida desde `Centro de Costos.xlsx` (mismo patrón que las
hojas de proyecto de Centro de Costos: se recalcula completa, no se acumula a mano).

| TAG proyecto | Subcategoría (`categoria_item` tal cual) | Bucket | Total sin IVA |
|---|---|---|---|
| CFLI | Consumibles | Materiales | 123.456 |
| CFLI | Equipos-Herramientas | Equipos | 80.000 |
| CFLI | Combustible | Otros | 45.000 |

Preserva el detalle real de cada subcategoría (Combustible, Herramientas manuales,
etc.) aunque la hoja "Proyectos" solo muestre 3 buckets agregados — así no se pierde
granularidad al resumir.

**Mapeo `categoria_item` → Bucket** (constante en `analisis_financiero.py`, mismo
patrón que `PREFIJOS_PROYECTO` en Centro de Costos):

- `Materiales`, `Consumibles` → **Materiales**
- `Equipos-Herramientas` → **Equipos**
- cualquier `categoria_item` no mapeado explícitamente → **Otros**, con aviso en
  consola (para decidir después si merece su propio mapeo, nunca se pierde en
  silencio)

## Flujo de ejecución (`analisis_financiero.py`, llamado desde el `run` de Centro de Costos o desde su propio driver)

1. **Backup** de `Análisis de Proyectos.xlsx` a `Respaldos/<Mes Año>/...` (si el
   archivo ya existe con datos).
2. **Leer hoja "Proyectos"**: por cada fila con TAG y Nombre válidos, verificar si
   `Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/
   <Nombre>/` existe; si no, crearla. Filas sin TAG o sin Nombre se saltan con
   aviso. TAG duplicado: se usa la primera fila, se avisa de las siguientes.
3. **Leer `Centro de Costos.xlsx` → `Detalle`** (solo lectura): agrupar
   `Total sin IVA` por (prefijo de `N° Ref.`, `categoria_item`).
4. **Regenerar hoja "Detalle Costos Reales"** completa a partir de ese agrupamiento.
5. **Asegurar fórmulas** de las columnas automáticas/derivadas en la hoja
   "Proyectos" (`SUMIFS`, totales, márgenes, desviación) para cada fila — sin tocar
   columnas manuales.
6. **Informe en consola**: proyectos nuevos detectados (carpeta creada), categorías
   no mapeadas caídas en "Otros", filas saltadas por datos incompletos.

Ningún paso de este flujo aborta el `run` de Centro de Costos si falla (archivo
abierto, permisos de carpeta, etc.) — solo advierte, mismo patrón que el paso del
Visualizador Web (12c).

## Tests (`Sistema/tests/`)

- Mapeo `categoria_item` → Bucket, incluyendo el caso "no mapeado → Otros con aviso".
- Detección de carpeta de proyecto faltante → se crea; si ya existe → no se
  duplica ni se toca.
- Agrupamiento de `Detalle` de Centro de Costos por (prefijo, categoria_item) con
  datos de ejemplo.
- Idempotencia: correr dos veces sin cambios en Centro de Costos deja la
  hoja "Detalle Costos Reales" y las fórmulas de "Proyectos" idénticas.
- Filas con TAG/Nombre faltante o duplicado no rompen la corrida.

## Fuera de alcance v1 (explícito)

- Automatizar Mano de Obra Real (no hay fuente de datos hoy).
- Integrar Flujo de Caja (módulo no iniciado todavía).
- Validaciones de datos en Excel (dropdowns para "Estado", etc.) — se puede agregar
  después sin romper nada, no es parte del cruce de datos que es el objetivo de v1.
- Editar `PREFIJOS_PROYECTO` de Centro de Costos automáticamente: si el TAG que el
  usuario usa en Análisis de Proyectos.xlsx no coincide con el prefijo que Centro de
  Costos derivaría solo del nombre del proyecto, el módulo solo avisa en consola —
  agregarlo a mano a `PREFIJOS_PROYECTO` queda en manos del usuario, para no hacer
  que este módulo edite el código fuente de otro.
