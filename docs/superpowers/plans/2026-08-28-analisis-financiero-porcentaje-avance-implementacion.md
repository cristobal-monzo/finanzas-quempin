# % de Avance manual y KPI "Nota Parcial" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar la columna de texto libre `Estado` de la hoja "Proyectos" por un `% Avance` manual, y agregar el KPI `Nota Parcial` (= `Nota del Proyecto` × `% Avance`) a la hoja "Indicadores", al dashboard web y a los reportes PDF.

**Architecture:** El módulo tiene una regla de negocio ⇒ dos renderizados (fórmula de Excel + espejo Python en `analisis_financiero.py`), y tres consumidores que **importan** ese espejo en vez de reimplementarlo (`Reportes/kpis_recalculados.py`, `Visualizador Web/build_visualizador.py`, y las fórmulas del propio libro). La `Nota Parcial` entra por ese mismo carril: `_formula_nota_parcial` + `calcular_nota_parcial` pegadas en el mismo bloque, con `Sistema/tests/test_contrato_kpis.py` fallando si divergen. El renombre de columna no reordena nada (misma posición 5), así que ninguna letra de columna ni fórmula existente cambia; el archivo real se migra con un script de un solo uso porque `asegurar_estructura_workbook` nunca pisa encabezados ya escritos en "Proyectos".

**Tech Stack:** Python 3.14 (`py -3.14`), openpyxl, pytest. HTML/CSS/JS vanilla (sin build step) para el dashboard.

**Spec:** [`docs/superpowers/specs/2026-08-28-analisis-financiero-porcentaje-avance-design.md`](../specs/2026-08-28-analisis-financiero-porcentaje-avance-design.md)

## Global Constraints

- **Intérprete único: `py -3.14`.** Nunca `python` a secas (es 3.11 sin openpyxl en este equipo).
- **La suite se corre completa desde la raíz del repo**: `py -3.14 -m pytest` (7 suites, 471 tests). Correr una carpeta sola fue exactamente el hueco por el que se coló la divergencia de la Nota entre dashboard y Excel.
- **No correr el pipeline real (`ejecutar()`, `/Actualizar_AF`, `driver.py run`) entre la Tarea 1 y la Tarea 8.** Con el código esperando `% Avance` y el archivo real todavía diciendo `Estado`, `datos_reportes._mapa_encabezados` marcaría los 17 proyectos como incompletos. Las Tareas 1-7 trabajan solo sobre libros temporales de test.
- **`Análisis de Proyectos 2026.xlsx` es dato financiero real, gitignored, en OneDrive sincronizado.** Cualquier escritura sobre él va precedida de un respaldo con timestamp.
- **La columna `Estado` de Centro de Costos NO se toca.** `Sistema/tests/test_categoria_proyecto.py:16`, `test_ejecutar.py:32` y `test_proyectos_nuevos_desde_cc.py:16` usan `"Estado"` como encabezado de una hoja de *Centro de Costos* (junto a `"Total con IVA (CLP)"`, `"Archivo origen"`) — es otro campo, de otro módulo. Solo cambia el `Estado` de la hoja "Proyectos" de Análisis Financiero.
- **Valor de `% Avance`: fracción `0`–`1`** (0.75 = 75%), formato Excel `0.0%`. Nunca entero 0–100.
- **Ni Python ni Excel acotan el avance a `[0, 1]`** — un acotamiento en un solo lado es exactamente la divergencia silenciosa que el contrato existe para evitar.
- **`Evaluación` sigue clasificando `Nota del Proyecto`**, y el `nota_promedio` del dashboard también. No usar `Nota Parcial` en ninguno de los dos.
- Mensajes de commit en español, formato `tipo(alcance): descripción`, terminando con `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

---

### Task 1: Renombrar `Estado` → `% Avance` en el esquema de "Proyectos"

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py:91` (`HEADERS_PROYECTOS`), `:197` (`ESTILO_COLUMNAS_PROYECTOS_POR_NOMBRE`), `:322` (`NOMBRES_COLUMNAS_MANUALES_PROYECTOS`), `:1016` (`CAMPOS_MANUALES_REQUERIDOS`)
- Test: `Sistema Analisis Financiero/Sistema/tests/test_estructura_workbook.py:115`, `Sistema Analisis Financiero/Sistema/tests/test_ejecutar.py:154`

**Interfaces:**
- Consumes: nada (primera tarea).
- Produces: el literal de encabezado `"% Avance"` en la posición 5 de `af.HEADERS_PROYECTOS`; `af.LETRA_COL_PROYECTOS["% Avance"] == "E"`; `"% Avance"` presente en `af.CAMPOS_MANUALES_REQUERIDOS` y en `af.NOMBRES_COLUMNAS_MANUALES_PROYECTOS`. Las tareas 2, 3, 6 y 8 dependen de este literal exacto.

- [ ] **Step 1: Escribir el test que falla**

En `Sistema Analisis Financiero/Sistema/tests/test_estructura_workbook.py`, reemplazar la aserción de la línea 115 y agregar un test de esquema nuevo al final del archivo:

```python
def test_columna_5_es_porcentaje_de_avance(tmp_path):
    """2026-08-28: 'Estado' (texto libre Terminado/En Proceso) pasó a ser un
    porcentaje de avance manual, en la MISMA posición 5 -- no se reordenó
    ninguna columna, así que ninguna letra ni fórmula existente cambia."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    assert ws.cell(row=1, column=5).value == "% Avance"
    assert af.LETRA_COL_PROYECTOS["% Avance"] == "E"


def test_porcentaje_de_avance_es_manual_y_requerido():
    """Hereda los dos roles que tenía 'Estado': campo de ingreso manual
    (resaltado amarillo + cursiva) y uno de los 8 campos que definen
    completitud. 'Estado' no debe quedar en ninguna de las dos listas."""
    assert "% Avance" in af.CAMPOS_MANUALES_REQUERIDOS
    assert "% Avance" in af.NOMBRES_COLUMNAS_MANUALES_PROYECTOS
    assert "Estado" not in af.CAMPOS_MANUALES_REQUERIDOS
    assert "Estado" not in af.NOMBRES_COLUMNAS_MANUALES_PROYECTOS
    assert "Estado" not in af.HEADERS_PROYECTOS


def test_porcentaje_de_avance_lleva_formato_de_porcentaje():
    """Se guarda como fracción 0-1: con la celda pre-formateada como
    porcentaje, Excel convierte solo un '75' tecleado a 75,0%."""
    _, formato, _ = af.ESTILO_COLUMNAS_PROYECTOS_POR_NOMBRE["% Avance"]
    assert formato == af.FORMATO_PORCENTAJE
```

Y en la línea 115, cambiar `assert ws.cell(row=1, column=5).value == "Estado"` por `assert ws.cell(row=1, column=5).value == "% Avance"`.

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Sistema/tests/test_estructura_workbook.py" -v`
Expected: FAIL — `assert 'Estado' == '% Avance'` y `KeyError: '% Avance'`.

- [ ] **Step 3: Renombrar en las cuatro constantes**

En `Sistema Analisis Financiero/Sistema/analisis_financiero.py`, cuatro ediciones puntuales:

```python
# línea 91 -- HEADERS_PROYECTOS
    "TAG proyecto", "Nombre del proyecto", "Cliente", "Categoría", "% Avance",
```

```python
# línea 197 -- ESTILO_COLUMNAS_PROYECTOS_POR_NOMBRE
    "% Avance": (COLOR_IDENTIFICACION, FORMATO_PORCENTAJE, 13),
```

```python
# línea 322 -- NOMBRES_COLUMNAS_MANUALES_PROYECTOS
    "TAG proyecto", "Nombre del proyecto", "% Avance", "Fecha de inicio",
```

```python
# línea 1016 -- CAMPOS_MANUALES_REQUERIDOS
    "% Avance", "Fecha de inicio", "Monto de Venta (sin IVA)",
```

Actualizar además el comentario de `CAMPOS_MANUALES_REQUERIDOS` (línea 1012) que menciona `"Estado"` como uno de los campos que el dashboard no exigía:

```python
# (sin "% Avance" -- entonces llamada "Estado" -- ni "Fecha de inicio") y ademas
```

- [ ] **Step 4: Arreglar el test de `ejecutar` que referencia el nombre viejo**

En `Sistema Analisis Financiero/Sistema/tests/test_ejecutar.py`, líneas 152-155:

```python
    # Las columnas manuales de la fila nueva quedan en blanco (las llena el
    # usuario a mano); % Avance es la primera columna manual tras Categoría.
    col_avance = af.HEADERS_PROYECTOS.index("% Avance") + 1
    assert ws_proyectos.cell(row=3, column=col_avance).value is None
```

- [ ] **Step 5: Correr la suite completa**

Run: `py -3.14 -m pytest`
Expected: PASS. Si falla algún test de `Reportes/` o de `Visualizador Web/`, es esperado y se arregla en su propia tarea — anotarlo, **no** arreglarlo acá salvo que sea un `KeyError: 'Estado'` en `CLAVE_POR_ENCABEZADO` (eso es Tarea 6).

- [ ] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_estructura_workbook.py" "Sistema Analisis Financiero/Sistema/tests/test_ejecutar.py"
git commit -m "feat(analisis-financiero): renombrar Estado a % Avance en Proyectos

Misma posición 5, sin reordenar ninguna columna: ninguna letra ni fórmula
existente cambia. Hereda los dos roles de Estado (ingreso manual y campo
requerido de completitud) y suma formato de porcentaje 0.0%.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: `calcular_nota_parcial` + `_formula_nota_parcial` (par espejo)

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py` (bloque "NOTA / EVALUACION: UNA SOLA DEFINICION, DOS RENDERIZADOS", tras `_formula_evaluacion`, ~línea 1148)
- Test: `Sistema Analisis Financiero/Sistema/tests/test_nota_evaluacion.py`, `Sistema Analisis Financiero/Sistema/tests/test_contrato_kpis.py`

**Interfaces:**
- Consumes: `af.HEADERS_PROYECTOS` con `"% Avance"` (Tarea 1); `af._redondear_excel`, `af.LETRA_COL_PROYECTOS`, `af.LETRA_COL_INDICADORES` (ya existen).
- Produces:
  - `af.calcular_nota_parcial(nota: int | None, avance: float | None) -> int | None`
  - `af._formula_nota_parcial(fila_proyectos: int, fila_indicadores: int) -> str`
  Las tareas 3, 5 y 6 consumen estas dos firmas exactas.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `Sistema Analisis Financiero/Sistema/tests/test_nota_evaluacion.py`:

```python
def test_nota_parcial_al_100_por_ciento_es_la_nota_completa():
    assert af.calcular_nota_parcial(88, 1.0) == 88


def test_nota_parcial_pondera_por_el_avance():
    """88 x 0.75 = 66: la ejecución va bien, pero solo tres cuartos del
    resultado están confirmados."""
    assert af.calcular_nota_parcial(88, 0.75) == 66


def test_nota_parcial_redondea_como_excel_no_como_python():
    """90 x 0.75 = 67.5 -> 68 (half away from zero). El round() nativo de
    Python daría 68 acá pero 66 para 66.5; se usa _redondear_excel para que
    el empate exacto en .5 caiga siempre del mismo lado que la fórmula."""
    assert af.calcular_nota_parcial(90, 0.75) == 68
    assert af.calcular_nota_parcial(70, 0.95) == 67  # 66.5 -> 67


def test_nota_parcial_vacia_si_falta_el_avance():
    assert af.calcular_nota_parcial(88, None) is None
    assert af.calcular_nota_parcial(88, "") is None


def test_nota_parcial_vacia_si_no_hay_nota():
    """Gastos Generales: la Nota ya viene vacía, la Parcial también."""
    assert af.calcular_nota_parcial(None, 0.75) is None


def test_nota_parcial_con_avance_cero_es_cero():
    assert af.calcular_nota_parcial(88, 0.0) == 0


def test_nota_parcial_no_acota_un_avance_fuera_de_rango():
    """Ni Python ni Excel acotan: un avance >100% es un error de carga y
    debe verse igual en ambos lados, no corregirse en silencio en uno solo."""
    assert af.calcular_nota_parcial(80, 1.5) == 120


def test_formula_nota_parcial_referencia_la_nota_y_el_avance_con_guardas():
    formula = af._formula_nota_parcial(5, 2)
    col_nota = af.LETRA_COL_INDICADORES["Nota del Proyecto"]
    col_avance = af.LETRA_COL_PROYECTOS["% Avance"]
    assert formula == (
        f'=IF(OR({col_nota}2="",Proyectos!{col_avance}5=""),"",'
        f'ROUND({col_nota}2*Proyectos!{col_avance}5,0))'
    )
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Sistema/tests/test_nota_evaluacion.py" -v`
Expected: FAIL con `AttributeError: module 'analisis_financiero' has no attribute 'calcular_nota_parcial'`.

- [ ] **Step 3: Implementar el par espejo**

En `analisis_financiero.py`, inmediatamente después de `_formula_evaluacion` (~línea 1148), dentro del mismo bloque comentado "NOTA / EVALUACION":

```python
def calcular_nota_parcial(nota: int | None, avance: float | None) -> int | None:
    """Nota del Proyecto ponderada por el % de avance manual del proyecto
    (2026-08-28). Equivalente Python exacto de _formula_nota_parcial().

    Separa dos preguntas que la Nota sola mezclaba: la Nota mide QUE TAN BIEN
    se esta ejecutando lo ejecutado hasta ahora (margen real vs venta,
    desviacion real vs presupuesto); la Parcial mide CUANTO de ese resultado
    esta confirmado. Un proyecto al 75% con Nota 88 tiene Parcial 66 -- la
    ejecucion va bien, pero un cuarto del proyecto todavia puede mover el
    numero final. Al 100% de avance ambas coinciden.

    None (celda vacia en Excel) si falta cualquiera de los dos insumos: la
    cadena vacia cuenta como faltante porque la formula de Excel guarda con
    ="" y la Nota de "Gastos Generales" llega justamente como "".

    NO acota el avance a [0, 1] -- la formula de Excel tampoco. Un
    acotamiento en un solo lado es exactamente la divergencia silenciosa que
    este bloque existe para evitar; un avance fuera de rango es un error de
    carga y debe verse como tal en los dos caminos."""
    if nota is None or avance is None or avance == "":
        return None
    return _redondear_excel(nota * avance)


def _formula_nota_parcial(fila_proyectos: int, fila_indicadores: int) -> str:
    """Equivalente Excel exacto de calcular_nota_parcial().

    Necesita las DOS filas: el avance vive en 'Proyectos' (que puede tener
    huecos) y la Nota en esta misma hoja 'Indicadores' (compacta, sin
    huecos) -- mismo desfase que ya manejan _formula_evaluacion (fila de
    Indicadores) y _formula_nota (fila de Proyectos).

    La guarda vive DENTRO de la formula, no en Python, para que la celda se
    recalcule sola cuando el usuario complete el avance sin necesidad de
    correr el script -- mismo patron que 'Margen por dia de ejecucion'.
    Cubre los dos casos vacios de una vez: la Nota de 'Gastos Generales'
    (que ya llega como "" por su propio guard en asegurar_hoja_indicadores)
    y un proyecto sin avance cargado."""
    col_nota = LETRA_COL_INDICADORES["Nota del Proyecto"]
    col_avance = LETRA_COL_PROYECTOS["% Avance"]
    nota = f"{col_nota}{fila_indicadores}"
    avance = f"Proyectos!{col_avance}{fila_proyectos}"
    return f'=IF(OR({nota}="",{avance}=""),"",ROUND({nota}*{avance},0))'
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Sistema/tests/test_nota_evaluacion.py" -v`
Expected: PASS (8 tests nuevos).

- [ ] **Step 5: Agregar el test de contrato fórmula-vs-Python**

Agregar al final de `Sistema Analisis Financiero/Sistema/tests/test_contrato_kpis.py`:

```python
def test_formula_nota_parcial_y_espejo_python_usan_las_mismas_piezas():
    """Mismo contrato que ya cubre Nota/Evaluación: si alguien cambia una de
    las dos implementaciones de la Nota Parcial sin cambiar la otra, este
    test falla antes de que el dashboard y el Excel se desincronicen."""
    formula = af._formula_nota_parcial(5, 2)
    assert "ROUND(" in formula, "el redondeo debe estar en la fórmula, no solo en Python"
    assert f'{af.LETRA_COL_INDICADORES["Nota del Proyecto"]}2' in formula
    assert f'Proyectos!{af.LETRA_COL_PROYECTOS["% Avance"]}5' in formula
    assert 'OR(' in formula, "debe guardar contra Nota vacía Y avance vacío"
    assert "MIN(" not in formula and "MAX(" not in formula, (
        "la fórmula no acota el avance; calcular_nota_parcial tampoco debe hacerlo"
    )
    assert af.calcular_nota_parcial(80, 1.5) == 120
```

- [ ] **Step 6: Correr la suite completa**

Run: `py -3.14 -m pytest`
Expected: PASS salvo lo ya anotado en la Tarea 1.

- [ ] **Step 7: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_nota_evaluacion.py" "Sistema Analisis Financiero/Sistema/tests/test_contrato_kpis.py"
git commit -m "feat(analisis-financiero): calcular_nota_parcial y su fórmula Excel espejo

Nota Parcial = Nota del Proyecto x % Avance, en el mismo bloque de doble
implementación que Nota/Evaluación y con contrato en test_contrato_kpis.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Columna "Nota Parcial" en la hoja "Indicadores"

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py:129` (`HEADERS_INDICADORES`), `:258` (`ESTILO_COLUMNAS_INDICADORES`), `:1236-1240` (`asegurar_hoja_indicadores`)
- Test: `Sistema Analisis Financiero/Sistema/tests/test_formulas_indicadores.py`

**Interfaces:**
- Consumes: `af._formula_nota_parcial(fila_proyectos, fila_indicadores)` (Tarea 2).
- Produces: `af.HEADERS_INDICADORES` con `"Nota Parcial"` como último elemento (índice 25, columna Z); la celda 26 de cada fila de "Indicadores" con la fórmula.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `Sistema Analisis Financiero/Sistema/tests/test_formulas_indicadores.py`:

```python
def test_nota_parcial_es_la_ultima_columna_de_indicadores():
    """Se agrega al FINAL (columna Z), sin reordenar ni tocar ninguna columna
    existente -- mismo criterio que los 2 KPIs agregados el 2026-07-28."""
    assert af.HEADERS_INDICADORES[-1] == "Nota Parcial"
    assert af.LETRA_COL_INDICADORES["Nota Parcial"] == "Z"


def test_columna_nota_parcial_lleva_la_formula_con_las_dos_filas(tmp_path):
    """La fila de 'Indicadores' es compacta (2) y la de 'Proyectos' puede
    tener huecos (4): la fórmula tiene que usar cada una donde corresponde."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 4, "tag": "UMAG", "nombre": "UMAG"}])

    ws = wb[af.HOJA_INDICADORES]
    assert ws.cell(row=2, column=26).value == af._formula_nota_parcial(4, 2)


def test_nota_parcial_de_gastos_generales_queda_vacia_por_la_nota_vacia(tmp_path):
    """No necesita su propio guard de 'Gastos Generales': la Nota (columna V)
    ya llega como "" para ese bucket, y la fórmula guarda contra eso."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws_p = wb[af.HOJA_PROYECTOS]
    col_categoria = af.HEADERS_PROYECTOS.index("Categoría") + 1
    ws_p.cell(row=2, column=col_categoria, value=af.CATEGORIA_GASTOS_GENERALES)

    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "GGEN", "nombre": "Gastos Generales"}])

    ws = wb[af.HOJA_INDICADORES]
    col_nota = af.LETRA_COL_INDICADORES["Nota del Proyecto"]
    assert f'{col_nota}2=""' in ws.cell(row=2, column=26).value


def test_nota_parcial_tiene_formato_entero_como_la_nota():
    color, formato, _ = af.ESTILO_COLUMNAS_INDICADORES["Z"]
    assert color == af.COLOR_DERIVADO
    assert formato == af.FORMATO_ENTERO
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Sistema/tests/test_formulas_indicadores.py" -v`
Expected: FAIL — `assert 'Margen por día de ejecución' == 'Nota Parcial'` y `KeyError: 'Z'`.

- [ ] **Step 3: Agregar la columna al esquema, al estilo y al generador**

En `analisis_financiero.py`, tres ediciones:

```python
# HEADERS_INDICADORES -- agregar como ÚLTIMO elemento, tras "Margen por día de ejecución"
    "Margen por día de ejecución",
    # KPI nuevo 2026-08-28: Nota del Proyecto ponderada por el "% Avance"
    # manual de "Proyectos". Al final, sin reordenar nada, igual que los 2
    # KPIs agregados el 2026-07-28.
    "Nota Parcial",
```

```python
# ESTILO_COLUMNAS_INDICADORES -- agregar tras la entrada "Y"
    "Z": (COLOR_DERIVADO, FORMATO_ENTERO, 14),
```

En `asegurar_hoja_indicadores`, tras el bloque de la columna 25 ("Margen por día de ejecución") y antes de `fila_destino += 1`:

```python
        # Z: Nota Parcial -- Nota del Proyecto (columna V de esta misma hoja)
        # ponderada por el "% Avance" manual de "Proyectos". No necesita un
        # guard propio de "Gastos Generales": la Nota ya llega como "" para
        # ese bucket y la fórmula guarda contra eso, igual que contra un
        # proyecto sin avance cargado.
        ws.cell(row=f, column=26, value=_formula_nota_parcial(r, f))
```

Actualizar además el docstring de `asegurar_hoja_indicadores` (línea ~1161), última línea de la enumeración de columnas:

```python
    ahorro/sobrecosto neto en $ por categoría (4) + total; nota; evaluación;
    peso en cartera; margen por día; nota parcial."""
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Sistema/tests/test_formulas_indicadores.py" -v`
Expected: PASS.

- [ ] **Step 5: Correr la suite completa**

Run: `py -3.14 -m pytest`
Expected: PASS salvo lo ya anotado.

- [ ] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_formulas_indicadores.py"
git commit -m "feat(analisis-financiero): columna Nota Parcial en la hoja Indicadores

Columna Z, al final del playbook, sin reordenar ninguna existente.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Entradas de "% Avance" y "Nota Parcial" en el Glosario KPIs

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py:1308` (`GLOSARIO_KPIS`)
- Test: `Sistema Analisis Financiero/Sistema/tests/test_glosario_kpis.py`

**Interfaces:**
- Consumes: nada de tareas previas más allá de los nombres `"% Avance"` y `"Nota Parcial"`.
- Produces: dos tuplas nuevas en `af.GLOSARIO_KPIS`.

- [ ] **Step 1: Escribir el test que falla**

Agregar al final de `Sistema Analisis Financiero/Sistema/tests/test_glosario_kpis.py`:

```python
def test_glosario_documenta_avance_y_nota_parcial():
    """El Excel se explica solo: todo KPI del libro tiene su fila en
    'Glosario KPIs' (pedido explícito del usuario, spec 2026-07-21)."""
    kpis = [fila[0] for fila in af.GLOSARIO_KPIS]
    assert "% Avance" in kpis
    assert "Nota Parcial" in kpis
    assert all(len(fila) == 4 for fila in af.GLOSARIO_KPIS)
    assert all(texto.strip() for fila in af.GLOSARIO_KPIS for texto in fila)
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Sistema/tests/test_glosario_kpis.py::test_glosario_documenta_avance_y_nota_parcial" -v`
Expected: FAIL con `assert '% Avance' in [...]`.

- [ ] **Step 3: Agregar las dos entradas**

En `GLOSARIO_KPIS`, insertar la entrada de `% Avance` **antes** de la de `"Nota del Proyecto"` (es un insumo, no un derivado), y la de `Nota Parcial` **inmediatamente después** de la de `"Evaluación"`:

```python
    (
        "% Avance",
        "Permite leer todo KPI de un proyecto en curso como resultado parcial y no como resultado final -- sin él, un proyecto recién empezado y uno casi terminado se veían idénticos. Reemplazó al campo de texto 'Estado' (Terminado / En Proceso) el 2026-08-28.",
        "Ingreso manual en la hoja 'Proyectos' (celda amarilla en cursiva), como porcentaje de 0% a 100%",
        "100% = ejecución terminada, los costos reales ya no deberían crecer. Bajo 100%, el Margen Real y la Desviación % de ese proyecto todavía pueden moverse: son el resultado de lo ejecutado hasta ahora, no el final.",
    ),
```

```python
    (
        "Nota Parcial",
        "Separa dos preguntas que la Nota sola mezclaba: qué tan bien se está ejecutando el proyecto, y cuánto de ese resultado ya está confirmado. Evita darle el mismo peso a un proyecto terminado con Nota 88 que a uno recién empezado con la misma nota sobre una fracción del trabajo.",
        "Nota del Proyecto x % Avance",
        "Nota 88 con 75% de avance da 66: la ejecución va bien, pero un cuarto del proyecto todavía puede mover el número final. Al 100% de avance coincide exactamente con la Nota del Proyecto. Queda vacía si falta el avance, o si es 'Gastos Generales' (que tampoco recibe Nota).",
    ),
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Sistema/tests/test_glosario_kpis.py" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_glosario_kpis.py"
git commit -m "docs(analisis-financiero): glosario de % Avance y Nota Parcial

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: "Nota Parcial" en el camino de los reportes PDF

**Files:**
- Modify: `Sistema Analisis Financiero/Reportes/kpis_recalculados.py:34` (import), `:129-160` (`recalcular_proyecto`)
- Test: `Sistema Analisis Financiero/Reportes/tests/test_datos_reportes.py:10,31`, `Sistema Analisis Financiero/Reportes/tests/test_driver_reportes.py:9,23`

**Interfaces:**
- Consumes: `af.calcular_nota_parcial` (Tarea 2); el encabezado `"% Avance"` (Tarea 1).
- Produces: `indicadores["Nota Parcial"]` en el dict que devuelve `recalcular_proyecto`, consumido por la Tarea 9 (contrato) y por los PDFs.

**Nota:** `datos_reportes.py` **no** necesita cambios. Lee la hoja con `_mapa_encabezados` (encabezados reales del archivo), así que `paquete["proyecto"]["% Avance"]` llega solo tras la migración, y `paquete["indicadores"]["Nota Parcial"]` llega por este cambio. La página 1 del PDF lleva *todos* los indicadores de la entidad sin selección editorial (SKILL.md de `Reportes_Analisis_Financiero`), así que ambos aparecen sin tocar la plantilla.

- [ ] **Step 1: Escribir el test que falla**

Agregar al final de `Sistema Analisis Financiero/Reportes/tests/test_datos_reportes.py`:

```python
def test_indicadores_incluyen_nota_parcial(tmp_path):
    """La Nota Parcial viaja en el mismo dict de indicadores que el resto del
    playbook, para que la página 1 del PDF la muestre sin tocar plantilla."""
    import kpis_recalculados as kr

    proyecto = {
        "TAG proyecto": "UMAG", "% Avance": 0.75,
        "Monto de Venta (sin IVA)": 10_000_000,
        "Costos Materiales Proyectados": 4_000_000,
        "Costos Equipos Proyectados": 2_000_000,
        "Mano de Obra Proyectada": 1_000_000,
        "Otros Costos Proyectados": 1_000_000,
        "Mano de Obra Real": 800_000,
    }
    reales = {"Materiales": 3_200_000, "Equipos": 1_600_000, "Otros": 800_000}

    _, indicadores = kr.recalcular_proyecto(proyecto, reales)

    assert indicadores["Nota Parcial"] == af.calcular_nota_parcial(
        indicadores["Nota del Proyecto"], 0.75
    )
    assert indicadores["Nota Parcial"] < indicadores["Nota del Proyecto"]


def test_nota_parcial_vacia_si_el_proyecto_no_tiene_avance_cargado(tmp_path):
    import kpis_recalculados as kr

    proyecto = {
        "TAG proyecto": "UMAG", "% Avance": None,
        "Monto de Venta (sin IVA)": 10_000_000,
        "Costos Materiales Proyectados": 4_000_000,
        "Costos Equipos Proyectados": 2_000_000,
        "Mano de Obra Proyectada": 1_000_000,
        "Otros Costos Proyectados": 1_000_000,
        "Mano de Obra Real": 800_000,
    }
    reales = {"Materiales": 3_200_000, "Equipos": 1_600_000, "Otros": 800_000}

    _, indicadores = kr.recalcular_proyecto(proyecto, reales)

    assert indicadores["Nota del Proyecto"] is not None
    assert indicadores["Nota Parcial"] is None
```

Ese archivo necesita `import analisis_financiero as af` en el encabezado si todavía no lo tiene (su `conftest.py` ya pone `Sistema/` en `sys.path`).

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Reportes/tests/test_datos_reportes.py" -v`
Expected: FAIL con `KeyError: 'Nota Parcial'`.

- [ ] **Step 3: Implementar**

En `Sistema Analisis Financiero/Reportes/kpis_recalculados.py`, extender el import de la línea 34:

```python
    _redondear_excel, calcular_nota, calcular_nota_parcial, clasificar_evaluacion,
```

En `recalcular_proyecto`, tras `evaluacion = clasificar_evaluacion(nota)` (línea 130):

```python
    nota_parcial = calcular_nota_parcial(nota, proyecto.get("% Avance"))
```

Y en el dict `indicadores`, tras `"Evaluación": evaluacion,`:

```python
        "Nota Parcial": nota_parcial,
```

- [ ] **Step 4: Renombrar `Estado` en las fixtures de los tests de reportes**

En `Sistema Analisis Financiero/Reportes/tests/test_datos_reportes.py` línea 10 y `test_driver_reportes.py` línea 9, cambiar el encabezado de la fixture:

```python
    "TAG proyecto", "Nombre del proyecto", "Cliente", "% Avance",
```

Y en `test_datos_reportes.py` línea 31 / `test_driver_reportes.py` línea 23, el valor:

```python
        "% Avance": 1.0, "Fecha de inicio": date(2026, 1, 10),
```

- [ ] **Step 5: Correr la suite de reportes**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Reportes/tests" -v`
Expected: PASS.

- [ ] **Step 6: Correr la suite completa**

Run: `py -3.14 -m pytest`
Expected: PASS salvo lo anotado (queda pendiente `Visualizador Web`, Tarea 6).

- [ ] **Step 7: Commit**

```bash
git add "Sistema Analisis Financiero/Reportes/kpis_recalculados.py" "Sistema Analisis Financiero/Reportes/tests/test_datos_reportes.py" "Sistema Analisis Financiero/Reportes/tests/test_driver_reportes.py"
git commit -m "feat(analisis-financiero): Nota Parcial en los indicadores de los reportes PDF

Importa calcular_nota_parcial de analisis_financiero en vez de reimplementarla.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: `% Avance` y `Nota Parcial` en el snapshot del dashboard

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py:47` (`CLAVE_POR_ENCABEZADO`), `:77` (`leer_proyectos`), `:226-235` (`calcular_kpis_proyecto`)
- Test: `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`, `Sistema Analisis Financiero/Sistema/tests/test_contrato_kpis.py`

**Interfaces:**
- Consumes: `af.calcular_nota_parcial` (Tarea 2); `af.HEADERS_PROYECTOS` con `"% Avance"` (Tarea 1).
- Produces: cada dict de proyecto del snapshot lleva `"avance"` (fracción o `None`) en vez de `"estado"`, y `"nota_parcial"` junto a `"nota"`. La Tarea 7 (`template.html`) consume esos dos nombres exactos.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`:

```python
def test_snapshot_expone_avance_y_nota_parcial():
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 0.75,
        "fecha_inicio": None, "fecha_cierre": None, "categoria": "I+D+i",
        "monto_venta": 10_000_000,
        "materiales_proy": 4_000_000, "equipos_proy": 2_000_000,
        "mo_proy": 1_000_000, "otros_proy": 1_000_000, "mo_real": 800_000,
    }
    reales = {"Materiales": 3_200_000, "Equipos": 1_600_000, "Otros": 800_000}

    kpis = bv.calcular_kpis_proyecto(p, reales)

    assert kpis["avance"] == 0.75
    assert "estado" not in kpis
    assert kpis["nota_parcial"] == af.calcular_nota_parcial(kpis["nota"], 0.75)


def test_snapshot_deja_nota_parcial_vacia_sin_avance():
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": None,
        "fecha_inicio": None, "fecha_cierre": None, "categoria": "I+D+i",
        "monto_venta": 10_000_000,
        "materiales_proy": 4_000_000, "equipos_proy": 2_000_000,
        "mo_proy": 1_000_000, "otros_proy": 1_000_000, "mo_real": 800_000,
    }
    reales = {"Materiales": 3_200_000, "Equipos": 1_600_000, "Otros": 800_000}

    kpis = bv.calcular_kpis_proyecto(p, reales)

    assert kpis["nota"] is not None
    assert kpis["nota_parcial"] is None
```

Ese archivo necesita `import analisis_financiero as af` si todavía no lo tiene.

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py" -v`
Expected: FAIL con `KeyError: 'estado'` (el dict de entrada ya no lo trae).

- [ ] **Step 3: Implementar**

En `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py`, tres ediciones:

```python
# línea 47 -- CLAVE_POR_ENCABEZADO
    "% Avance": "avance",
```

```python
# línea 77 -- leer_proyectos
            "avance": _valor_columna(ws_proyectos, fila, "% Avance"),
```

```python
# línea 230 -- calcular_kpis_proyecto, dentro del dict `resultado`
        "tag": p["tag"], "nombre": p["nombre"], "cliente": p["cliente"], "avance": p["avance"],
```

Y tras `evaluacion = af.clasificar_evaluacion(nota)` (línea 227):

```python
    # Nota Parcial: importada de analisis_financiero, nunca reimplementada
    # aca -- este archivo es uno de los dos que se desincronizaron del Excel
    # en 2026-07-28 al copiar la formula de la Nota en vez de importarla.
    nota_parcial = af.calcular_nota_parcial(nota, p["avance"])
```

Agregando al dict `resultado`, junto a `"nota"`/`"evaluacion"`:

```python
        "nota": nota, "evaluacion": evaluacion, "nota_parcial": nota_parcial,
```

- [ ] **Step 4: Renombrar `estado` en las fixtures existentes del archivo de test**

En `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`, reemplazar en todas las fixtures:
- línea 26: `"Estado": "En Proceso"` → `"% Avance": 0.5`
- línea 49: `"estado": "Terminado"` → `"avance": 1.0`
- líneas 69 y 74: `_proyecto_completo_dict(estado=None)` → `(avance=None)`, `(estado="")` → `(avance="")`
- líneas 123, 142, 161, 191, 420, 443, 461, 486, 502, 518, 534, 594, 611: `"estado": "En Proceso"` → `"avance": 0.5`

- [ ] **Step 5: Correr la suite del visualizador**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Visualizador Web/tests" -v`
Expected: PASS.

- [ ] **Step 6: Cerrar el contrato entre los tres caminos**

En `Sistema Analisis Financiero/Sistema/tests/test_contrato_kpis.py`, en `_caso` (línea 63-79), renombrar la clave del dict `corto` y agregar el avance a `encabezados`:

```python
    corto = {
        "tag": "TEST", "nombre": "Proyecto Test", "cliente": "Cliente X",
        "avance": 0.75, "fecha_inicio": None, "fecha_cierre": None,
        "categoria": "I+D+i", "monto_venta": venta,
        "materiales_proy": mat_p, "equipos_proy": eq_p,
        "mo_proy": mo_p, "otros_proy": otros_p, "mo_real": mo_r,
    }
    encabezados = {
        "% Avance": 0.75,
        "Monto de Venta (sin IVA)": venta,
        "Costos Materiales Proyectados": mat_p,
        "Costos Equipos Proyectados": eq_p,
        "Mano de Obra Proyectada": mo_p,
        "Otros Costos Proyectados": otros_p,
        "Mano de Obra Real": mo_r,
    }
```

Actualizar también las líneas 157-188 (`estado="Terminado"` → `avance=1.0`, `"Estado": "Terminado"` → `"% Avance": 1.0`, `estado=None` → `avance=None`, `estado=""` → `avance=""`) y la línea 233 (`"estado": "Terminado"` → `"avance": 1.0`), y agregar el test de contrato nuevo:

```python
def test_nota_parcial_coincide_entre_visualizador_y_reportes():
    """El tercer KPI que se recalcula por los dos caminos Python. Sin este
    test, un cambio en uno solo repetiría el bug de 2026-07-28: el mismo
    proyecto con dos notas distintas según dónde se lo mirara."""
    kpi_viz, indicadores = _notas_de_ambos_caminos(CASO_BAJO_PRESUPUESTO)
    assert kpi_viz["nota_parcial"] == indicadores["Nota Parcial"]
    assert kpi_viz["nota_parcial"] is not None
    assert kpi_viz["nota_parcial"] < kpi_viz["nota"], "el caso está al 75% de avance"
```

- [ ] **Step 7: Correr la suite completa**

Run: `py -3.14 -m pytest`
Expected: PASS, las 7 suites, sin excepciones pendientes.

- [ ] **Step 8: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/build_visualizador.py" "Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py" "Sistema Analisis Financiero/Sistema/tests/test_contrato_kpis.py"
git commit -m "feat(analisis-financiero): % Avance y Nota Parcial en el snapshot del dashboard

Cierra el contrato de la Nota Parcial entre los tres caminos (Excel,
reportes PDF y dashboard) en test_contrato_kpis.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Columnas `% Avance` y `Nota Parcial` en el dashboard

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/template.html:623-627` (encabezados de tabla), `:1117-1122` (fila + colspan), `:1088` (panel de detalle)

**Interfaces:**
- Consumes: `p.avance` (fracción o `null`) y `p.nota_parcial` (entero o `null`) del snapshot (Tarea 6); las funciones ya existentes `formatoPct(n)` (línea 833) y `esc(s)`.
- Produces: nada que consuman tareas posteriores.

- [ ] **Step 1: Cambiar el encabezado de la tabla**

En `template.html` línea 623, reemplazar `<th>Estado</th>` y agregar la columna de Nota Parcial tras la de Nota (línea 626):

```html
          <tr><th>Proyecto</th><th>Cliente</th>
            <th title="Porcentaje de avance del proyecto, cargado a mano en la planilla. 100% = ejecución terminada; bajo 100% el Margen Real y la Desviación % todavía pueden moverse.">% Avance</th>
            <th>Monto Venta</th>
            <th title="Monto de Venta − Total Real: la utilidad efectivamente generada por el proyecto.">Margen Real</th>
            <th title="Real / Proyectado − 1, sobre el total de costos. +15% o más = sobregasto relevante respecto al presupuesto original.">Desviación %</th>
            <th title="0-100: 70% margen neto % (vs. objetivo 25%) + 30% control de desviación total. Resume rentabilidad y control de presupuesto en un número.">Nota</th>
            <th title="Nota del Proyecto × % Avance: cuánto del resultado ya está confirmado. Al 100% de avance coincide con la Nota.">Nota Parcial</th>
            <th title="Traduce la Nota a una etiqueta rápida: Excelente / Bueno / Aprobado / Requiere atención.">Evaluación</th></tr>
```

- [ ] **Step 2: Cambiar la fila de la tabla y el colspan**

En `renderTablaProyectos` (línea 1117-1122):

```javascript
      var fila = '<tr class="doc-row' + (expandido ? ' is-expanded' : '') + '" data-tag="' + esc(p.tag) + '" tabindex="0">' +
        '<td><span class="expand-toggle">' + (expandido ? '▾' : '▸') + '</span>' + esc(p.nombre) + '</td><td>' + esc(p.cliente || '—') + '</td><td>' + (p.avance == null ? '—' : formatoPct(p.avance)) +
        '</td><td>' + formatoCLP(p.monto_venta) + '</td><td>' + formatoCLP(p.margen_real) + '</td><td>' +
        formatoPctDesviacion(p.desviacion_pct) + '</td><td>' + p.nota + '</td><td>' + (p.nota_parcial == null ? '—' : p.nota_parcial) + '</td><td>' + badgePill(p.evaluacion, NIVEL_EVALUACION[p.evaluacion]) + '</td></tr>';
      if (expandido) {
        fila += '<tr class="detail-row"><td colspan="9">' + detalleProyectoHtml(p) + '</td></tr>';
      }
```

El `colspan` pasa de 8 a 9: la tabla tiene una columna más.

- [ ] **Step 3: Agregar las dos métricas al panel de detalle**

En `detalleProyectoHtml`, reemplazar la tarjeta "Nota / Evaluación" (línea 1088) por dos:

```javascript
        '<div><div class="dk">Nota / Evaluación</div><div class="dv">' + p.nota + ' — ' + badgePill(p.evaluacion, NIVEL_EVALUACION[p.evaluacion]) + '</div></div>' +
        '<div><div class="dk" title="Nota del Proyecto × % Avance — cuánto del resultado ya está confirmado. Al 100% de avance coincide con la Nota.">Nota Parcial</div><div class="dv">' + (p.nota_parcial == null ? '—' : p.nota_parcial + ' (' + formatoPct(p.avance || 0) + ' de avance)') + '</div></div>' +
```

- [ ] **Step 4: Regenerar el dashboard y verificarlo en el navegador**

```bash
py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" visualizador
```

Abrir `Sistema Analisis Financiero/Visualizador Web/build/index.html` y confirmar visualmente: la columna `% Avance` muestra porcentajes, `Nota Parcial` muestra enteros, la fila expandida no queda descuadrada (colspan correcto), y ningún error en la consola del navegador.

**Nota:** este paso lee el Excel real. Hasta que corra la Tarea 8, la columna `% Avance` saldrá vacía (`—`) para los 17 proyectos y todos aparecerán como "pendientes de completar" — es lo esperado, no un bug. Repetir esta verificación al final de la Tarea 8.

- [ ] **Step 5: Correr la suite completa**

Run: `py -3.14 -m pytest`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/template.html"
git commit -m "feat(analisis-financiero): columnas % Avance y Nota Parcial en el dashboard

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Migrar `Análisis de Proyectos 2026.xlsx`

**Files:**
- Create: `$SCRATCHPAD/migrar_avance.py` (script de un solo uso, no versionado). `$SCRATCHPAD` = el directorio de scratchpad de la sesión que ejecuta el plan (el que el harness anuncia en su system prompt). Es deliberadamente **fuera del repo**: es un script de un solo uso sobre datos reales, no código del módulo.
- Modify: `Análisis Financiero/Análisis de Proyectos 2026.xlsx` (dato real, gitignored)

**Interfaces:**
- Consumes: `af.HEADERS_PROYECTOS`, `af.FORMATO_PORCENTAJE` (Tarea 1).
- Produces: el archivo real con `% Avance` en `Proyectos!E1` y los 17 valores migrados. Nada de código depende de esto; es el paso que habilita volver a correr el pipeline real.

- [ ] **Step 1: Respaldar el archivo real antes de tocarlo**

```bash
py -3.14 -c "
import shutil, datetime, pathlib
src = pathlib.Path('Análisis Financiero/Análisis de Proyectos 2026.xlsx')
dst = pathlib.Path('Sistema Analisis Financiero/Respaldos') / ('pre-migracion-avance-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.xlsx')
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, dst)
print('Respaldo:', dst)
"
```

Confirmar en la salida que el respaldo existe antes de continuar. Es una carpeta de OneDrive sincronizada — si el archivo está abierto en Excel, cerrarlo primero.

- [ ] **Step 2: Escribir el script de migración**

Crear `$SCRATCHPAD/migrar_avance.py`:

```python
# -*- coding: utf-8 -*-
"""Migracion de un solo uso (2026-08-28): Proyectos!Estado -> Proyectos!% Avance.

asegurar_estructura_workbook nunca pisa un encabezado ya escrito en
"Proyectos" (regla de oro del modulo), asi que cambiar HEADERS_PROYECTOS no
renombra nada en el archivo real -- hace falta este paso explicito, igual que
para el reordenamiento de "Categoria" del 2026-07-28.
"""
import sys
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve()
while RAIZ.name != "Finanzas QUEMPIN":
    RAIZ = RAIZ.parent
sys.path.insert(0, str(RAIZ / "Sistema Analisis Financiero" / "Sistema"))
import analisis_financiero as af  # noqa: E402

RUTA = RAIZ / "Análisis Financiero" / "Análisis de Proyectos 2026.xlsx"

# "Terminas" es un typo real de "Terminado" (Cesfam Limache) -- confirmado con
# el usuario, migra a 100% junto con el resto.
TERMINADOS = {"Terminado", "Terminas"}

wb = openpyxl.load_workbook(RUTA)
ws = wb[af.HOJA_PROYECTOS]
col = af.HEADERS_PROYECTOS.index("% Avance") + 1
assert ws.cell(row=1, column=col).value == "Estado", (
    f"E1 dice {ws.cell(row=1, column=col).value!r}, no 'Estado' -- ya migrado?"
)

ws.cell(row=1, column=col, value="% Avance")
migrados = []
for fila in range(2, ws.max_row + 1):
    tag = ws.cell(row=fila, column=1).value
    if not tag:
        continue
    celda = ws.cell(row=fila, column=col)
    anterior = celda.value
    # "Gastos Generales" queda VACIO a proposito: bucket de costos internos,
    # sin Monto de Venta ni Nota -- "avance" no significa nada ahi. Ya era
    # incompleto antes de esta migracion, no cambia de estado.
    celda.value = 1.0 if anterior in TERMINADOS else None
    celda.number_format = af.FORMATO_PORCENTAJE
    migrados.append((tag, anterior, celda.value))

wb.save(RUTA)
for tag, antes, despues in migrados:
    print(f"{tag:6} {antes!r:15} -> {despues!r}")
print(f"\n{len(migrados)} filas migradas.")
```

- [ ] **Step 3: Correr la migración**

Run: `py -3.14 "$SCRATCHPAD/migrar_avance.py"`
Expected: 17 líneas, 16 con `-> 1.0` y `GGEN 'En Proceso' -> None`.

- [ ] **Step 4: Verificar el resultado contra el archivo real**

```bash
py -3.14 -c "
import openpyxl
wb = openpyxl.load_workbook('Análisis Financiero/Análisis de Proyectos 2026.xlsx', data_only=True)
ws = wb['Proyectos']
assert ws.cell(row=1, column=5).value == '% Avance', ws.cell(row=1, column=5).value
filas = [(r[0].value, r[4].value) for r in ws.iter_rows(min_row=2) if r[0].value]
al_100 = [t for t, v in filas if v == 1.0]
vacios = [t for t, v in filas if v is None]
print('Total:', len(filas), '| al 100%:', len(al_100), '| vacíos:', vacios)
assert len(filas) == 17 and len(al_100) == 16 and vacios == ['GGEN'], filas
print('OK')
"
```
Expected: `Total: 17 | al 100%: 16 | vacíos: ['GGEN']` seguido de `OK`.

- [ ] **Step 5: Correr el pipeline real completo**

```bash
py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" run
```

Expected: sin errores. Este es el primer `run` real desde la Tarea 1.

- [ ] **Step 6: Verificar que ningún proyecto cambió de completitud**

```bash
py -3.14 -c "
import sys, pathlib
sys.path.insert(0, 'Sistema Analisis Financiero/Sistema')
sys.path.insert(0, 'Sistema Analisis Financiero/Reportes')
import openpyxl, datos_reportes as dr
wb = openpyxl.load_workbook('Análisis Financiero/Análisis de Proyectos 2026.xlsx', data_only=True)
ws = wb['Proyectos']
mapa = {c.value: i+1 for i, c in enumerate(ws[1]) if c.value}
filas = [{h: ws.cell(row=f, column=c).value for h, c in mapa.items()} for f in range(2, ws.max_row+1)]
completos = [p['TAG proyecto'] for p in filas if p.get('TAG proyecto') and dr.proyecto_tiene_datos_completos(p)]
print(len(completos), 'completos:', completos)
"
```

Comparar contra el conteo previo a la migración (el dashboard decía cuántos "Proyectos completos" antes de empezar). Si bajó, **detenerse e investigar**: significa que algún proyecto perdió su campo requerido.

- [ ] **Step 7: Verificar 3 Notas Parciales a mano**

Abrir `Análisis de Proyectos 2026.xlsx` en Excel (para que recalcule las fórmulas), ir a "Indicadores", y confirmar en tres proyectos con Nota distinta que `Z = ROUND(V × avance, 0)`. Con todos al 100%, `Nota Parcial` debe coincidir exactamente con `Nota del Proyecto`. Confirmar además que la fila de `GGEN` tiene V, W **y Z** vacías.

Luego, para verificar el caso parcial de verdad: poner temporalmente `75%` en el `% Avance` de un proyecto, confirmar que su `Nota Parcial` pasa a `ROUND(Nota × 0.75, 0)` y que su `Evaluación` **no** cambia, y devolver el valor a `100%`.

- [ ] **Step 8: Regenerar y revisar el dashboard**

```bash
py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" visualizador
```

Abrir `Sistema Analisis Financiero/Visualizador Web/build/index.html`: los 16 proyectos con `100%` en `% Avance`, `Nota Parcial` == `Nota`, y el conteo de "Proyectos completos" igual al del Step 6.

- [ ] **Step 9: Confirmar que no se filtró dato real a git**

```bash
git status --short
git check-ignore -v "Análisis Financiero/Análisis de Proyectos 2026.xlsx" "Sistema Analisis Financiero/Visualizador Web/build/index.html"
```
Expected: `git status` sin rastro del `.xlsx` ni del `build/`, y `check-ignore` confirmando que ambos están cubiertos por un patrón del `.gitignore`.

---

### Task 9: Documentación

**Files:**
- Modify: `Sistema Analisis Financiero/CLAUDE.md`, `Sistema Analisis Financiero/MEMORY.md`, `Sistema Analisis Financiero/Visualizador Web/CLAUDE.md`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: nada.

- [ ] **Step 1: `Sistema Analisis Financiero/CLAUDE.md`**

Tres ediciones:

1. En el resumen del esquema de "Proyectos" (~línea 90-98), cambiar `Estado` por `% Avance` en la enumeración de columnas y agregar una línea explicando el cambio:

```markdown
**`Estado` reemplazado por `% Avance` (2026-08-28)**: el campo de texto libre
(`Terminado`/`En Proceso`, más un typo real `Terminas`) pasó a ser un
porcentaje de avance manual, en la **misma posición 5** — no se reordenó
ninguna columna, así que ninguna letra ni fórmula existente cambió. Hereda
los dos roles de `Estado`: campo de ingreso manual (amarillo + cursiva) y uno
de los 8 campos de `CAMPOS_MANUALES_REQUERIDOS`. Se guarda como fracción 0–1
con formato `0.0%`. El archivo real se migró a mano (ver MEMORY.md): los 16
proyectos terminados quedaron en 100% y `Gastos Generales` vacío.
```

2. En la tabla del "Playbook de KPIs" (~línea 148-160), agregar la fila:

```markdown
| Nota Parcial (nuevo 2026-08-28) | Nota del Proyecto × % Avance — cuánto del resultado ya está confirmado; al 100% coincide con la Nota. Vacía si falta el avance o si es "Gastos Generales" |
```

3. Bajo la tabla, la nota de diseño:

```markdown
**Nota Parcial (2026-08-28)**: columna nueva al final de "Indicadores" (Z),
sin reordenar nada. Separa "qué tan bien se está ejecutando" (la Nota) de
"cuánto de eso está confirmado" (la Parcial). `Evaluación` y el `Nota
promedio` del dashboard **siguen clasificando la Nota financiera**, no la
Parcial — decisión explícita del usuario. Entra por el mismo carril de doble
implementación que la Nota (`calcular_nota_parcial` + `_formula_nota_parcial`,
contrato en `test_contrato_kpis.py`), y a diferencia de los 2 KPIs de
2026-07-28 **sí** llega a los reportes PDF: viaja en el dict `indicadores` de
`kpis_recalculados.recalcular_proyecto`, y la página 1 lleva todos los
indicadores de la entidad sin selección editorial.
```

4. En "Reglas de completitud" (~línea 247-259), cambiar la enumeración `(Estado, Fecha de inicio, …)` por `(% Avance, Fecha de inicio, …)`.

- [ ] **Step 2: `Sistema Analisis Financiero/Visualizador Web/CLAUDE.md`**

En la viñeta "Proyectos incompletos", cambiar `(Estado, Fecha de inicio, Monto de Venta, …)` por `(% Avance, Fecha de inicio, Monto de Venta, …)`. En la viñeta "Pestaña Proyectos", agregar que la tabla ahora lleva `% Avance` y `Nota Parcial`, y que los KPIs de cabecera siguen usando la Nota financiera.

- [ ] **Step 3: `Sistema Analisis Financiero/MEMORY.md`**

Agregar una entrada fechada 2026-08-28 con: qué cambió y por qué; la decisión de que `Evaluación` y el promedio del dashboard **no** usan la Nota Parcial (y que fue elección del usuario, no un descuido); el detalle de la migración (17 filas, el typo `Terminas` → 100% confirmado con el usuario, `GGEN` vacío a propósito); y la decisión de no acotar el avance a `[0,1]` en ninguno de los dos lados.

- [ ] **Step 4: Correr la suite completa una última vez**

Run: `py -3.14 -m pytest`
Expected: PASS, las 7 suites.

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/CLAUDE.md" "Sistema Analisis Financiero/MEMORY.md" "Sistema Analisis Financiero/Visualizador Web/CLAUDE.md"
git commit -m "docs(analisis-financiero): documentar % Avance, Nota Parcial y la migración

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Publicar el dashboard actualizado**

El dashboard vive en GitHub Pages con URL fija
(`https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero/`).
Publicar con `/Actualizar_AF`, que corre el registrador y republica en la
misma URL — nunca genera un link nuevo. **Confirmar con el usuario antes de
publicar**: es una acción hacia afuera.
