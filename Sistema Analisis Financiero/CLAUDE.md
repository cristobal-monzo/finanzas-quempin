# CLAUDE.md — Análisis Financiero

Consolidador cross-módulo: cruza los costos reales de Centro de Costos (por proyecto y categoría) con las
ventas y los costos proyectados de `Análisis de Proyectos 2026.xlsx`, para dar rentabilidad por proyecto,
desviación y KPIs. No le duplica lógica a CC: solo lo lee.

**Rol**: actúa como **analista financiero experto para una PYME**, no solo como ejecutor del script.

- Evalúa proyectos: rentabilidad real contra proyectada, riesgo y desviaciones que ameritan atención.
- Propone y depura KPIs: sugiere una métrica si hay una pregunta de negocio sin respuesta y señala los que no
  aportan (redundancias matemáticas, promedios que un outlier distorsiona). Nunca acumula métricas.
- Elige la presentación más clara para la audiencia; puede cruzar todos los módulos.
- **Rigor numérico** ([`analista-financiero-quempin.md`](../.claude/agents/analista-financiero-quempin.md)): nunca
  inventa cifras, todo es trazable a la fuente y señala las inconsistencias en vez de ocultarlas.

| Tema | Detalle (léelo solo al tocarlo) |
|---|---|
| Hojas y columnas del libro, playbook completo de KPIs, Nota del Proyecto, auditorías del 2026-09-21 | [docs/libro-y-kpis.md](docs/libro-y-kpis.md) |
| Lo que llega por el Intercambio (presupuesto, venta, ingreso manual) | [docs/intercambio.md](docs/intercambio.md) |
| Reportes PDF | [docs/reportes.md](docs/reportes.md) |
| Tablero | `Visualizador Web/CLAUDE.md` |
| Decisiones y pendientes (81 KB: Grep, no lo leas entero) | `MEMORY.md` |

`Sistema/analisis_financiero.py` pesa 140 KB: busca la función con Grep.

## Dónde está cada cosa

```
Finanzas QUEMPIN/
├── Análisis Financiero/            # SOLO lo que el usuario abre: el Excel y sus reportes PDF
└── Sistema Analisis Financiero/    # el código: Sistema/, Reportes/, Visualizador Web/, Respaldos/, docs/
```

`RAIZ_MODULO` y `RAIZ_DATOS` salen de `Path(__file__)`: **nunca asumas que están juntas**. Skills:
`/Registro_Analisis_Financiero` (`status`, `run`, `confirmar-cliente`, `intercambio …`, `formulaciones …`) y
`/Reportes_Analisis_Financiero`. Corre encadenado al `run` de CC (PASO 12d), que no puede abortarse por esto.

## El libro

- **Proyectos**: una fila por proyecto. TAG (= prefijo de CC), Nombre, Cliente y Categoría (se completan solos;
  lo escrito a mano no se pisa; con duda quedan «Pendiente de revisión» y se resuelven con `driver.py
  confirmar-cliente`), % Avance (fracción 0–1), fechas, Monto de Venta **sin IVA**, costos proyectados (4 categorías,
  manuales), costos reales (Materiales, Equipos y Otros por fórmula desde CC; **Mano de Obra Real es manual**),
  derivados por fórmula y «N° Requerimiento» (la clave común).
- **Detalle Costos Reales**: proyecto + subcategoría, sin perder granularidad. **Indicadores**: los KPIs, 100 %
  fórmulas. **Clientes**: 100 % fórmulas, solo con proyectos de «Datos completos» = Sí. **Glosario KPIs**: se reescribe
  entero en cada corrida.
- **Regla de oro** (heredada de CC): las columnas manuales no se tocan entre corridas; solo se regeneran «Detalle
  Costos Reales» y las fórmulas. Única excepción: el Intercambio, abajo.
- `asegurar_estructura_workbook` nunca pisa encabezados ya escritos: cambiar `HEADERS_PROYECTOS` no reordena un archivo
  existente. Las columnas se referencian por nombre, no por letra: ya hubo un desalineamiento real.
- **Completitud**: una sola definición, `tiene_datos_completos()` (los 7 de `CAMPOS_MANUALES_REQUERIDOS`). Sin fecha de
  cierre o con cierre futuro, el proyecto está «en desarrollo».

## KPIs: reglas

- **Una sola implementación Python**: `calcular_kpis_proyecto()` y `calcular_clientes()`, cada KPI por el nombre de su
  columna; el tablero y los PDF solo traducen claves. Las fórmulas salen de `formulas_indicadores()`, y
  `test_contrato_kpis.py` exige que cubran las mismas columnas. **Un KPI nuevo va en los dos lados.**
- **División por cero = vacío en los dos lados** (celda vacía en Excel, `None` en Python), nunca un 0 inventado.
- **Nota del Proyecto** (0–100): 70 % margen estimado al cierre (lineal hasta el objetivo de 25 %, luego asíntota,
  `_score_margen_nota`) + 30 % control de la desviación estimada (sin ABS, 0 con +30 %, `SOBRECOSTO_NOTA_CERO`).
  `componentes_nota()` da los puntos que suman exactamente la Nota.
- **Estimado al cierre**: Costo Real + Costo Proyectado × (1 − % Avance). Un proyecto en curso se juzga por esto, no
  por lo gastado a la fecha. Al 100 % nada cambia.
- **Mapeo de categorías** (`MAPEO_CATEGORIA_BUCKET`): Servicios queda en Otros **a propósito**, porque Mano de Obra
  Real es manual y podría ya incluirla. El Portal lleva una copia (`LL_BUCKET`, que `test_portal.py` compara).
- **`alertas_proyecto()`** solo avisa; no cambia ningún KPI. `sesgo_por_categoria()` y `concentracion_cartera()` viven en
  `analisis_financiero.py`, no en el tablero.
- **Para verificar un cambio de fórmulas**: corre sobre una **copia** del libro con un país ficticio en `PAISES` (y un
  guard de que los reales no cambiaron), recalcula con Excel real por COM (`CalculateFull`) y compara celda a celda
  con `calcular_kpis_proyecto()`. Los tests comparan el texto de las fórmulas; solo esto compara sus valores.

## Costos proyectados desde el Formulador (Intercambio)

`Sistema/presupuestos_formulador.py`, enganchado en `ejecutar()` después del respaldo y antes de las fórmulas. Es la
única excepción a la regla de oro. Mensajes `presupuesto-proyecto`, `venta-proyecto` y `datos-proyecto`.

- **Solo escribe si es seguro**: celda vacía, valor que el Formulador escribió antes (registro
  `Sistema/presupuestos_formulador.json`, gitignoreado) o valor que el remitente **vio** (`reemplaza`, como un If-Match).
  Si no, queda **pendiente**: `driver.py intercambio confirmar|descartar <id>`. Todo o nada por envío.
- Presupuesto y venta: gana el último, con nota de Excel de procedencia (si alguien cambia la celda, se quita).
  `datos-proyecto`: se aplican todos, en orden, como valor manual (sin nota); puede crear un proyecto o vaciar una celda.
- Se archiva en `procesado/` y se guarda el registro **solo si el Excel se guardó**. Nunca aborta el `run`.
- Un TAG inexistente espera, salvo un `crear` con nombre. El N° de requerimiento se completa solo si está vacío.
- **Publica** `publicado/analisis-financiero.json` al final de cada `run` (`driver.py intercambio publicar` lo hace sin
  escribir el Excel), con `venta: {cargada, origen}` y **nunca el monto**: la carpeta la ve toda la biblioteca.
- **Un país ficticio de verificación debe sobrescribir `raiz_intercambio` y `ruta_estado_intercambio`**, o apuntarían a
  los reales. Perú: desactivado. `cargar_datos_centro_costos()` es la única lectura de los datos de CC.

## Precauciones

- **Nunca escribe `Centro de Costos.xlsx`.** Si algo se ve viejo, corre CC, no este módulo.
- Las carpetas de proyecto nuevas van en `Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y
  Boletas/Chile/<Nombre>/`, **nunca** en `Centro de Costos/Facturas y Boletas/` (legado).
- El libro está en OneDrive y lleva datos reales: puede tener ediciones manuales recientes.
