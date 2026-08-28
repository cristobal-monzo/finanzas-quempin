# Diseño: % de Avance manual por proyecto y KPI "Nota Parcial"

Fecha: 2026-08-28
Estado: aprobado por el usuario (brainstorming), pendiente de plan de implementación.

Extiende el módulo `Sistema Analisis Financiero/` (Excel en
`Análisis Financiero/Análisis de Proyectos 2026.xlsx`). No reemplaza ningún
spec anterior; modifica una columna del esquema definido en
[`2026-07-20-analisis-financiero-design.md`](2026-07-20-analisis-financiero-design.md)
y agrega un KPI al playbook de
[`2026-07-21-analisis-financiero-nota-clientes-design.md`](2026-07-21-analisis-financiero-nota-clientes-design.md).

## Problema

La columna `Estado` de la hoja "Proyectos" es texto libre manual
(`Terminado` / `En Proceso`, más un typo real: `Terminas`). Es binaria y no
aporta ninguna señal cuantitativa: un proyecto recién empezado y uno al 90%
se ven idénticos, y ningún indicador distingue "este margen es el resultado
final" de "este margen es lo que va hasta ahora".

Pedido del usuario: reemplazar `Estado` por un **porcentaje de avance
manual**, y que ese avance se refleje en los indicadores y en la
calificación mediante un KPI / nota parcial.

## 1. Esquema del Excel — hoja "Proyectos"

`Estado` (columna 5) se renombra a **`% Avance`**, en la **misma posición**
— no se reordena ninguna columna, así que ninguna letra de columna cambia y
ninguna fórmula existente se recalcula distinto.

| Aspecto | Valor |
|---|---|
| Encabezado | `% Avance` |
| Posición | 5 (donde estaba `Estado`) |
| Origen | Manual (resaltado amarillo + cursiva) |
| Almacenamiento | Fracción `0`–`1` |
| Formato | `FORMATO_PORCENTAJE` (`0.0%`) |
| Grupo de color | `COLOR_IDENTIFICACION` (sin cambio) |

Se guarda como fracción, no como entero 0–100, por dos razones: es el mismo
criterio que el resto de columnas porcentuales del libro (`Desviación %`,
`Margen neto %`, `Estructura %`), y con la celda pre-formateada como
porcentaje Excel convierte solo un `75` tecleado a `75,0%` — mientras que con
formato entero un `0,75` tecleado se redondearía a `1`.

Cambios de código en `analisis_financiero.py`:

- `HEADERS_PROYECTOS`: `"Estado"` → `"% Avance"`.
- `ESTILO_COLUMNAS_PROYECTOS_POR_NOMBRE`: entrada renombrada, formato
  `None` → `FORMATO_PORCENTAJE`.
- `NOMBRES_COLUMNAS_MANUALES_PROYECTOS`: renombrada (sigue siendo manual).
- `CAMPOS_MANUALES_REQUERIDOS`: renombrada — sigue siendo uno de los 8
  campos que definen completitud, en el mismo slot que ocupaba `Estado`.

**No** se agrega validación de rango en Excel (data validation): fuera del
alcance pedido. El espejo Python sí acota el valor al usarlo (ver §3).

## 2. Migración del archivo real

`asegurar_estructura_workbook` **nunca pisa un encabezado ya escrito** en
"Proyectos" (solo rellena celdas `None`) — regla de oro del módulo. Cambiar
`HEADERS_PROYECTOS` no renombra nada en el archivo existente: hace falta una
migración explícita de un solo uso, igual que la del reordenamiento de
`Categoría` (2026-07-28).

La migración, con respaldo con timestamp previo:

1. Renombra `Proyectos!E1` de `Estado` a `% Avance`.
2. Aplica `0.0%` a la columna E.
3. Convierte los valores existentes:

| Proyectos | `Estado` actual | `% Avance` migrado |
|---|---|---|
| 15 proyectos (UMAG, CCON, MLER, BWIL, CANT, CCHI, COMC, CPMO, CREM, CVAL, ESFO, FQYQ, LIMA, HPIN, JUNJ) | `Terminado` | `1.0` (100%) |
| Cesfam Limache (CFLI) | `Terminas` | `1.0` (100%) |
| Gastos Generales (GGEN) | `En Proceso` | *(vacío)* |

`Terminas` es un typo real de `Terminado` — confirmado con el usuario, migra
a 100% junto con el resto.

GGEN queda **deliberadamente vacío**: es el bucket de gastos internos de la
empresa (`CATEGORIA_GASTOS_GENERALES`), sin `Monto de Venta`, sin
`Fecha de inicio` y sin `Mano de Obra Real`. Ya está excluido de
Nota/Evaluación (`asegurar_hoja_indicadores`), de la hoja "Clientes" y de la
regla de completitud — "avance" no significa nada sobre un bucket de costos,
y dejarlo vacío no cambia su estado: ya era incompleto antes de esta
migración.

La migración se ejecuta una sola vez, sobre el archivo real, verificando
después que las 17 filas quedaron con el valor esperado. Queda registrada en
`Sistema Analisis Financiero/MEMORY.md`.

## 3. KPI nuevo: "Nota Parcial" (hoja "Indicadores")

```
Nota Parcial = ROUND(Nota del Proyecto × % Avance, 0)
```

Columna nueva **al final** de `HEADERS_INDICADORES` (columna Z, después de
`Margen por día de ejecución`) — no reordena ni toca ninguna columna
existente, mismo criterio que los 2 KPIs agregados el 2026-07-28.

Semántica: la `Nota del Proyecto` mide **qué tan bien se está ejecutando** lo
que se ha ejecutado hasta ahora (margen real vs. venta, desviación real vs.
presupuesto). La `Nota Parcial` mide **cuánto de ese resultado está
confirmado**: un proyecto al 75% con Nota 88 tiene Nota Parcial 66 — la
ejecución va bien, pero un cuarto del proyecto todavía puede cambiar el
número final. A 100% de avance, `Nota Parcial == Nota`.

Queda **vacía** cuando:

- El proyecto es `Gastos Generales` (misma guarda que Nota/Evaluación: si la
  Nota está vacía, la Parcial también).
- `% Avance` está vacío — la guarda vive **dentro de la fórmula Excel**
  (`IF(Proyectos!E{r}="","",…)`), no en Python, para que se recalcule sola
  cuando el usuario complete el avance sin necesidad de correr el script,
  mismo patrón que `Margen por día de ejecución`.

Estilo: `ESTILO_COLUMNAS_INDICADORES["Z"] = (COLOR_DERIVADO, FORMATO_ENTERO, 14)`
— igual que `Nota del Proyecto`.

**`Evaluación` NO cambia**: sigue clasificando la `Nota del Proyecto`
(decisión explícita del usuario). La etiqueta cualitativa describe la calidad
de la ejecución; el avance se lee en su propia columna y en la Nota Parcial.

### Doble implementación (Excel + Python)

La sección "NOTA / EVALUACION: UNA SOLA DEFINICION, DOS RENDERIZADOS" de
`analisis_financiero.py` existe porque el cálculo de la Nota estuvo duplicado
en tres archivos y se desincronizó — el mismo proyecto mostraba 94 en el
dashboard y 100 en el Excel/PDF. La Nota Parcial entra por el mismo camino:

- `_formula_nota_parcial(fila_proyectos, fila_indicadores)` — fórmula Excel.
- `calcular_nota_parcial(nota, avance)` — espejo Python, `None` si `nota` es
  `None` o `avance` es `None`; usa `_redondear_excel` (half away from zero).

Ninguna de las dos acota `avance` a `[0, 1]`: un acotamiento en Python que la
fórmula Excel no replica es exactamente la clase de divergencia silenciosa
que esta sección existe para evitar. Un avance fuera de rango es un error de
carga del usuario y debe verse como tal en ambos lados.

Ambas viven pegadas en el mismo bloque, y `Sistema/tests/test_contrato_kpis.py`
falla si divergen. Consumidores: `Reportes/kpis_recalculados.py` y
`Visualizador Web/build_visualizador.py` **importan** la función — nunca la
reimplementan.

## 4. Visualizador Web

`build_visualizador.py`:

- `CLAVE_POR_ENCABEZADO`: `"Estado" → "estado"` pasa a `"% Avance" → "avance"`.
- El snapshot de cada proyecto expone `avance` (fracción o `None`) en vez de
  `estado`, más `nota_parcial` calculada con `af.calcular_nota_parcial`.

`template.html`:

- Tabla de proyectos: encabezado `Estado` → `% Avance`, celda muestra el
  porcentaje formateado (`75%`), `—` si está vacío. **Solo el porcentaje**,
  sin etiqueta derivada (decisión del usuario).
- Columna nueva `Nota Parcial` inmediatamente después de `Nota`.

Los KPIs de cabecera **no cambian**: `nota_promedio` sigue promediando la
`Nota del Proyecto` (decisión del usuario), tanto el global como el de
Clientes/Categorías.

## 5. Reportes PDF

`Reportes/datos_reportes.py`: el paquete de datos de proyecto agrega `avance`
y `nota_parcial` junto al `en_desarrollo` que ya expone. Ambos se muestran en
la **página 1** (panel de verificación, que lleva *todos* los KPIs de la
entidad sin selección editorial, según el estándar de 2 páginas de
`2026-07-21-analisis-financiero-reportes-pdf-design.md` §10).

`proyecto_esta_en_desarrollo()` **no cambia**: sigue derivándose de
`Fecha de cierre`. Avance y fecha de cierre son campos independientes, sin
validación cruzada (decisión del usuario) — un proyecto puede llegar a 100%
de avance antes de que se cargue su fecha de cierre, y seguirá marcado como
"en desarrollo" hasta que se cargue.

## 6. Glosario KPIs

Dos entradas nuevas en `FILAS_GLOSARIO_KPIS`:

- **`% Avance`** — por qué importa (permite leer todo KPI de un proyecto en
  curso como resultado parcial, no final), qué usa (ingreso manual), qué
  significa (100% = ejecución terminada; los costos reales de un proyecto
  bajo 100% siguen creciendo).
- **`Nota Parcial`** — por qué importa (separa "se está ejecutando bien" de
  "cuánto de ese resultado está confirmado"), qué usa (Nota del Proyecto ×
  % Avance), qué significa (Nota 88 al 75% → 66; a 100% coincide con la
  Nota; vacía si falta el avance o es Gastos Generales).

## 7. Tests

- Actualizar los que construyen filas con `estado="Terminado"` /
  `"Estado": "Activo"` → `avance` / `"% Avance"`:
  `Sistema/tests/test_contrato_kpis.py`,
  `Visualizador Web/tests/test_build_visualizador.py`,
  `Reportes/tests/test_datos_reportes.py`,
  `Reportes/tests/test_driver_reportes.py`.
- Nuevos, para `calcular_nota_parcial`: 100% → igual a la Nota; 75% de una
  Nota 88 → 66; avance `None` → `None`; Nota `None` (Gastos Generales) →
  `None`; avance 0 → 0; avance fuera de rango (ej. 1.5) no se acota, en
  Python ni en Excel.
- Nuevo de contrato: la fórmula Excel y el espejo Python producen el mismo
  valor para los casos del punto anterior (extendiendo el patrón ya usado
  para Nota/Evaluación en `test_contrato_kpis.py`).
- Nuevo de esquema: `"% Avance"` está en `CAMPOS_MANUALES_REQUERIDOS` y en
  `NOMBRES_COLUMNAS_MANUALES_PROYECTOS`, y `"Estado"` ya no aparece en
  ninguno de los dos.

## 8. Verificación

1. Suite completa desde la raíz: `py -3.14 -m pytest` (471 tests + los
   nuevos) — nunca carpeta por carpeta; correr solo una suite fue
   exactamente el hueco por el que se coló la divergencia de la Nota entre
   dashboard y Excel.
2. Migración del archivo real con respaldo previo, y verificación posterior
   de las 17 filas.
3. Comprobación a mano de la Nota Parcial contra 2–3 proyectos reales
   (Nota × avance, redondeo incluido) antes de dar el cambio por bueno.
4. Regenerar el libro y el dashboard, y confirmar que ningún proyecto cambió
   de estado de completitud respecto de antes de la migración.

## Fuera de alcance (explícito)

- Validación de rango 0–100% en Excel (data validation).
- Que el avance pondere dentro de la fórmula de la Nota (se evaluó y se
  descartó: cambiaría la calibración 70/30 vigente).
- Que `Evaluación` o el `Nota promedio` del dashboard usen la Nota Parcial.
- Acoplar `% Avance` con `Fecha de cierre`.
- Estimar costos "a terminación" proyectando el avance (ej.
  `Total Real / avance`) — un KPI plausible, pero no pedido.
