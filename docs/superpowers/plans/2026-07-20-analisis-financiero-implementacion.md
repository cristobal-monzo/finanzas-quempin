# Análisis Financiero — Implementación Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir `Sistema/analisis_financiero.py` (el script del módulo Análisis Financiero) más su skill `/Registro_Analisis_Financiero`, para que `Análisis de Proyectos.xlsx` mantenga automáticamente sus costos reales por categoría y su hoja de KPIs, encadenado al `run` de Centro de Costos.

**Architecture:** Un único script `analisis_financiero.py` (Python + openpyxl, mismo stack que Centro de Costos y Cotizador Historico) que lee `Centro de Costos.xlsx` en modo **solo lectura**, y lee/escribe `Análisis de Proyectos.xlsx` (3 hojas: "Proyectos" con columnas manuales + fórmulas derivadas, "Detalle Costos Reales" 100% regenerada, "Indicadores" 100% fórmulas). Se invoca vía su propio skill (`status`/`run`) o encadenado desde `auditor_centro_costos.py`.

**Tech Stack:** Python 3, `openpyxl` (ya instalado, sin dependencias nuevas), `pytest` para tests.

## Global Constraints

- Todo en `Análisis de Proyectos.xlsx` (venta, costos proyectados, costos reales) va **sin IVA** — nunca mezclar con IVA incluido.
- `TAG proyecto` = el mismo prefijo que usa Centro de Costos (`PREFIJOS_PROYECTO` / `N° Ref.`), nunca un código aparte.
- Este módulo **nunca escribe `Centro de Costos.xlsx`** — solo lectura ahí, siempre.
- Las carpetas de proyecto nuevas se crean en `Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/<Nombre>/` — **nunca** en `Centro de Costos/Facturas y Boletas/` (legado, ya no la lee Centro de Costos desde 2026-07-17).
- `Mano de Obra Real` es 100% manual en v1 — no automatizar, no hay fuente de datos hoy.
- Ningún paso de este módulo aborta el `run` de Centro de Costos si falla (archivo abierto, permisos, etc.) — solo advierte en consola.
- Las columnas manuales de la hoja "Proyectos" (TAG, Nombre, Estado, fechas, Venta, proyectados, Mano de Obra Real) **nunca se sobrescriben** entre corridas — regla de oro heredada de Centro de Costos.
- Referencia de diseño completa: `docs/superpowers/specs/2026-07-20-analisis-financiero-design.md`.

---

## File Structure

```
Análisis Financiero/
├── Sistema/
│   ├── analisis_financiero.py             # todo el módulo (construido incrementalmente, tareas 1-10)
│   └── tests/
│       ├── conftest.py                    # solo path setup, mismo patrón que Cotizador Historico
│       ├── test_estructura_workbook.py    # Tarea 1
│       ├── test_mapeo_categoria.py        # Tarea 2
│       ├── test_lectura_agrupacion_cc.py  # Tarea 3
│       ├── test_lectura_proyectos.py      # Tarea 4
│       ├── test_carpetas_proyecto.py      # Tarea 5
│       ├── test_backup.py                 # Tarea 6
│       ├── test_hoja_detalle_costos_reales.py  # Tarea 7
│       ├── test_formulas_proyectos.py     # Tarea 8
│       ├── test_formulas_indicadores.py   # Tarea 9
│       └── test_ejecutar.py               # Tarea 10
└── .claude/skills/Registro_Analisis_Financiero/
    ├── SKILL.md                           # Tarea 11
    └── driver.py                          # Tarea 11

Centro de Costos/Sistema/
├── auditor_centro_costos.py               # Modify: Tarea 12 (nuevo PASO 12d)
└── tests/
    └── test_actualizar_analisis_financiero.py  # Tarea 12
```

---

### Task 1: Estructura inicial del workbook

**Files:**
- Create: `Análisis Financiero/Sistema/analisis_financiero.py`
- Test: `Análisis Financiero/Sistema/tests/conftest.py`
- Test: `Análisis Financiero/Sistema/tests/test_estructura_workbook.py`

**Interfaces:**
- Produces: `HOJA_PROYECTOS: str`, `HOJA_DETALLE_COSTOS_REALES: str`, `HOJA_INDICADORES: str`, `HEADERS_PROYECTOS: list[str]`, `HEADERS_DETALLE_COSTOS_REALES: list[str]`, `HEADERS_INDICADORES: list[str]`, `asegurar_estructura_workbook(ruta_excel: Path) -> openpyxl.Workbook`

- [ ] **Step 1: Crear `conftest.py` (path setup, mismo patrón que Cotizador Historico/Centro de Costos)**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 2: Escribir el test que falla**

```python
# Análisis Financiero/Sistema/tests/test_estructura_workbook.py
import openpyxl

import analisis_financiero as af


def test_crea_las_3_hojas_con_encabezados_si_no_existe_el_archivo(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)

    assert af.HOJA_PROYECTOS in wb.sheetnames
    assert af.HOJA_DETALLE_COSTOS_REALES in wb.sheetnames
    assert af.HOJA_INDICADORES in wb.sheetnames

    ws = wb[af.HOJA_PROYECTOS]
    assert ws.cell(row=1, column=1).value == "TAG proyecto"
    assert ws.cell(row=1, column=2).value == "Nombre del proyecto"
    assert ws.cell(row=1, column=19).value == "Desviación % (Real vs Proyectado)"


def test_elimina_hoja1_vacia_al_migrar_un_archivo_existente(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb_previo = openpyxl.Workbook()
    wb_previo.active.title = "Hoja1"
    wb_previo.save(ruta)

    wb = af.asegurar_estructura_workbook(ruta)

    assert "Hoja1" not in wb.sheetnames
    assert af.HOJA_PROYECTOS in wb.sheetnames


def test_no_toca_una_hoja_proyectos_que_ya_existe(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb_previo = openpyxl.Workbook()
    ws_previo = wb_previo.active
    ws_previo.title = af.HOJA_PROYECTOS
    ws_previo.cell(row=2, column=1, value="UMAG")
    ws_previo.cell(row=2, column=2, value="UMAG")
    wb_previo.save(ruta)

    wb = af.asegurar_estructura_workbook(ruta)

    ws = wb[af.HOJA_PROYECTOS]
    assert ws.cell(row=2, column=1).value == "UMAG"
```

- [ ] **Step 3: Correr los tests, confirmar que fallan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_estructura_workbook.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'analisis_financiero'` (el archivo todavía no existe).

- [ ] **Step 4: Crear `analisis_financiero.py` con la configuración y la función**

```python
# -*- coding: utf-8 -*-
"""
analisis_financiero.py -- Consolidador de costos reales por proyecto para
QUEMPIN SpA. Lee Centro de Costos.xlsx (SOLO LECTURA, nunca lo escribe) y
mantiene Análisis de Proyectos.xlsx (3 hojas: Proyectos, Detalle Costos
Reales, Indicadores). Ver docs/superpowers/specs/2026-07-20-analisis-
financiero-design.md para el diseño completo.
"""

from pathlib import Path

import openpyxl

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────

RAIZ = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ.parent
RUTA_EXCEL = RAIZ_MODULO / "Análisis de Proyectos.xlsx"
RAIZ_RESPALDOS = RAIZ_MODULO / "Respaldos"

RAIZ_CENTRO_COSTOS = RAIZ_MODULO.parent / "Centro de Costos"
RUTA_EXCEL_CENTRO_COSTOS = RAIZ_CENTRO_COSTOS / "Excel" / "Centro de Costos.xlsx"
RAIZ_FACTURAS_CENTRO_COSTOS = (
    RAIZ_CENTRO_COSTOS / "Sitio de comunicación - Centro de Costos 1" / "Facturas y Boletas"
)

HOJA_PROYECTOS = "Proyectos"
HOJA_DETALLE_COSTOS_REALES = "Detalle Costos Reales"
HOJA_INDICADORES = "Indicadores"

HEADERS_PROYECTOS = [
    "TAG proyecto", "Nombre del proyecto", "Estado", "Fecha de inicio",
    "Fecha de cierre", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados",
    "Costos Materiales Reales", "Costos Equipos Reales",
    "Otros Costos Reales", "Mano de Obra Real", "Total Proyectado",
    "Total Real", "Margen Proyectado", "Margen Real",
    "Desviación % (Real vs Proyectado)",
]
HEADERS_DETALLE_COSTOS_REALES = ["TAG proyecto", "Subcategoría", "Bucket", "Total sin IVA"]
HEADERS_INDICADORES = [
    "TAG proyecto", "Nombre del proyecto", "Rentabilidad sobre costo",
    "Margen neto %", "Productividad Materiales", "Productividad Equipos",
    "Productividad MO", "Productividad Otros", "Costo Materiales % de venta",
    "Costo Equipos % de venta", "Costo MO % de venta", "Costo Otros % de venta",
    "Desviación % Materiales", "Desviación % Equipos", "Desviación % MO",
    "Desviación % Otros",
]


def asegurar_estructura_workbook(ruta_excel: Path) -> openpyxl.Workbook:
    """Abre ruta_excel si existe, o crea un libro nuevo. Garantiza que las 3
    hojas existan con encabezados en la fila 1 -- si una hoja ya existe, no
    la toca (regla de oro: no reescribir datos ya presentes). Elimina hojas
    default vacías ("Hoja1"/"Sheet") si quedaron de un libro recién creado."""
    if ruta_excel.exists():
        wb = openpyxl.load_workbook(ruta_excel)
    else:
        wb = openpyxl.Workbook()

    for nombre_hoja, headers in (
        (HOJA_PROYECTOS, HEADERS_PROYECTOS),
        (HOJA_DETALLE_COSTOS_REALES, HEADERS_DETALLE_COSTOS_REALES),
        (HOJA_INDICADORES, HEADERS_INDICADORES),
    ):
        if nombre_hoja not in wb.sheetnames:
            ws = wb.create_sheet(nombre_hoja)
            for col, encabezado in enumerate(headers, start=1):
                ws.cell(row=1, column=col, value=encabezado)

    for nombre_default in ("Hoja1", "Sheet"):
        if nombre_default in wb.sheetnames:
            ws_default = wb[nombre_default]
            esta_vacia = all(
                celda.value is None
                for fila in ws_default.iter_rows()
                for celda in fila
            )
            if esta_vacia:
                del wb[nombre_default]

    return wb
```

- [ ] **Step 5: Correr los tests, confirmar que pasan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_estructura_workbook.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add "Análisis Financiero/Sistema/analisis_financiero.py" "Análisis Financiero/Sistema/tests/conftest.py" "Análisis Financiero/Sistema/tests/test_estructura_workbook.py"
git commit -m "feat(analisis-financiero): estructura inicial del workbook (3 hojas)"
```

---

### Task 2: Mapeo categoría_item → Bucket

**Files:**
- Modify: `Análisis Financiero/Sistema/analisis_financiero.py` (agregar al final)
- Test: `Análisis Financiero/Sistema/tests/test_mapeo_categoria.py`

**Interfaces:**
- Consumes: nada (función pura)
- Produces: `MAPEO_CATEGORIA_BUCKET: dict[str, str]`, `mapear_categoria_a_bucket(categoria_item: str | None) -> tuple[str, bool]`

- [ ] **Step 1: Escribir el test que falla**

```python
# Análisis Financiero/Sistema/tests/test_mapeo_categoria.py
import analisis_financiero as af


def test_materiales_mapea_a_materiales():
    assert af.mapear_categoria_a_bucket("Materiales") == ("Materiales", True)


def test_consumibles_mapea_a_materiales():
    assert af.mapear_categoria_a_bucket("Consumibles") == ("Materiales", True)


def test_equipos_herramientas_mapea_a_equipos():
    assert af.mapear_categoria_a_bucket("Equipos-Herramientas") == ("Equipos", True)


def test_categoria_no_mapeada_cae_a_otros_sin_mapeo_explicito():
    assert af.mapear_categoria_a_bucket("Combustible") == ("Otros", False)


def test_categoria_none_cae_a_otros_sin_mapeo_explicito():
    assert af.mapear_categoria_a_bucket(None) == ("Otros", False)
```

- [ ] **Step 2: Correr el test, confirmar que falla**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_mapeo_categoria.py -v`
Expected: FAIL con `AttributeError: module 'analisis_financiero' has no attribute 'mapear_categoria_a_bucket'`

- [ ] **Step 3: Agregar la constante y la función al final de `analisis_financiero.py`**

```python
# ── MAPEO DE CATEGORÍAS ──────────────────────────────────────────────────────

MAPEO_CATEGORIA_BUCKET = {
    "Materiales": "Materiales",
    "Consumibles": "Materiales",
    "Equipos-Herramientas": "Equipos",
}


def mapear_categoria_a_bucket(categoria_item: str | None) -> tuple[str, bool]:
    """Devuelve (bucket, es_mapeo_explicito). Cualquier categoria_item que no
    esté en MAPEO_CATEGORIA_BUCKET (incluyendo None) cae en "Otros" con
    es_mapeo_explicito=False, para poder avisar sin perder el monto."""
    if categoria_item in MAPEO_CATEGORIA_BUCKET:
        return MAPEO_CATEGORIA_BUCKET[categoria_item], True
    return "Otros", False
```

- [ ] **Step 4: Correr el test, confirmar que pasa**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_mapeo_categoria.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add "Análisis Financiero/Sistema/analisis_financiero.py" "Análisis Financiero/Sistema/tests/test_mapeo_categoria.py"
git commit -m "feat(analisis-financiero): mapeo categoria_item -> bucket"
```

---

### Task 3: Lectura y agrupación de `Detalle` de Centro de Costos

**Files:**
- Modify: `Análisis Financiero/Sistema/analisis_financiero.py`
- Test: `Análisis Financiero/Sistema/tests/test_lectura_agrupacion_cc.py`

**Interfaces:**
- Consumes: nada nuevo
- Produces: `prefijo_de_n_ref(n_ref: str) -> str`, `leer_detalle_centro_costos(ruta_excel_cc: Path) -> list[dict]` (cada dict: `{"n_ref": str, "categoria_item": str | None, "total_sin_iva": float}`), `agrupar_por_proyecto_y_subcategoria(items_detalle: list[dict]) -> dict[tuple[str, str], float]`

- [ ] **Step 1: Escribir el test que falla**

```python
# Análisis Financiero/Sistema/tests/test_lectura_agrupacion_cc.py
import openpyxl

import analisis_financiero as af


def _crear_excel_cc_minimo(tmp_path, filas):
    """filas: lista de tuplas (n_ref, categoria_item, total_sin_iva)"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Detalle"
    encabezados = [
        "N° Ref.", "Proyecto", "Tipo de Proyecto", "N° Documento", "Nombre Ítem",
        "Descripción", "Categoría Ítem", "Cantidad", "P. Unitario sin IVA",
        "Total sin IVA (CLP)", "Total con IVA (CLP)",
    ]
    for col, encabezado in enumerate(encabezados, start=1):
        ws.cell(row=1, column=col, value=encabezado)
    for fila_idx, (n_ref, categoria_item, total_sin_iva) in enumerate(filas, start=2):
        ws.cell(row=fila_idx, column=1, value=n_ref)
        ws.cell(row=fila_idx, column=7, value=categoria_item)
        ws.cell(row=fila_idx, column=10, value=total_sin_iva)
    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(ruta)
    return ruta


def test_prefijo_de_n_ref_toma_lo_anterior_al_guion():
    assert af.prefijo_de_n_ref("UMAG-001") == "UMAG"
    assert af.prefijo_de_n_ref("CFLI-014") == "CFLI"


def test_leer_detalle_centro_costos_lee_las_3_columnas_relevantes(tmp_path):
    ruta = _crear_excel_cc_minimo(tmp_path, [("UMAG-001", "Materiales", 50000)])
    items = af.leer_detalle_centro_costos(ruta)
    assert items == [{"n_ref": "UMAG-001", "categoria_item": "Materiales", "total_sin_iva": 50000.0}]


def test_leer_detalle_centro_costos_ignora_filas_sin_total(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Detalle"
    ws.cell(row=1, column=1, value="N° Ref.")
    ws.cell(row=1, column=7, value="Categoría Ítem")
    ws.cell(row=1, column=10, value="Total sin IVA (CLP)")
    ws.cell(row=2, column=1, value="UMAG-001")
    ws.cell(row=2, column=7, value="Materiales")
    # sin valor en Total sin IVA (CLP)
    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(ruta)
    assert af.leer_detalle_centro_costos(ruta) == []


def test_agrupar_por_proyecto_y_subcategoria_suma_por_prefijo_y_categoria():
    items = [
        {"n_ref": "UMAG-001", "categoria_item": "Materiales", "total_sin_iva": 50000.0},
        {"n_ref": "UMAG-002", "categoria_item": "Materiales", "total_sin_iva": 20000.0},
        {"n_ref": "UMAG-003", "categoria_item": "Equipos-Herramientas", "total_sin_iva": 90000.0},
        {"n_ref": "CFLI-001", "categoria_item": "Materiales", "total_sin_iva": 15000.0},
    ]
    agrupado = af.agrupar_por_proyecto_y_subcategoria(items)
    assert agrupado == {
        ("UMAG", "Materiales"): 70000.0,
        ("UMAG", "Equipos-Herramientas"): 90000.0,
        ("CFLI", "Materiales"): 15000.0,
    }
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_lectura_agrupacion_cc.py -v`
Expected: FAIL con `AttributeError` (las 3 funciones no existen todavía).

- [ ] **Step 3: Agregar las funciones al final de `analisis_financiero.py`**

```python
# ── LECTURA DE CENTRO DE COSTOS (SOLO LECTURA) ───────────────────────────────

def prefijo_de_n_ref(n_ref: str) -> str:
    """'UMAG-001' -> 'UMAG'. Mismo prefijo que PREFIJOS_PROYECTO en
    Centro de Costos/Sistema/auditor_centro_costos.py."""
    return n_ref.split("-")[0]


def leer_detalle_centro_costos(ruta_excel_cc: Path) -> list[dict]:
    """Lee la hoja 'Detalle' de Centro de Costos.xlsx -- SOLO LECTURA, este
    módulo nunca escribe ese archivo. Filas sin N° Ref. o sin Total sin IVA
    se ignoran (no se puede agrupar ni sumar sin esos dos datos)."""
    wb = openpyxl.load_workbook(ruta_excel_cc, data_only=True)
    ws = wb["Detalle"]
    encabezados = [celda.value for celda in ws[1]]
    col_n_ref = encabezados.index("N° Ref.") + 1
    col_categoria = encabezados.index("Categoría Ítem") + 1
    col_total_sin_iva = encabezados.index("Total sin IVA (CLP)") + 1

    items = []
    for fila in ws.iter_rows(min_row=2):
        n_ref = fila[col_n_ref - 1].value
        total = fila[col_total_sin_iva - 1].value
        if n_ref is None or total is None:
            continue
        categoria = fila[col_categoria - 1].value
        items.append({"n_ref": n_ref, "categoria_item": categoria, "total_sin_iva": float(total)})
    return items


def agrupar_por_proyecto_y_subcategoria(items_detalle: list[dict]) -> dict[tuple[str, str], float]:
    """Suma total_sin_iva agrupado por (prefijo de proyecto, categoria_item
    original -- sin colapsar a bucket todavía, eso lo hace la hoja 'Detalle
    Costos Reales' al escribir, para no perder la subcategoría real)."""
    agrupado: dict[tuple[str, str], float] = {}
    for item in items_detalle:
        prefijo = prefijo_de_n_ref(item["n_ref"])
        clave = (prefijo, item["categoria_item"])
        agrupado[clave] = agrupado.get(clave, 0.0) + item["total_sin_iva"]
    return agrupado
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_lectura_agrupacion_cc.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add "Análisis Financiero/Sistema/analisis_financiero.py" "Análisis Financiero/Sistema/tests/test_lectura_agrupacion_cc.py"
git commit -m "feat(analisis-financiero): lectura solo-lectura de Detalle de Centro de Costos y agrupacion por proyecto/subcategoria"
```

---

### Task 4: Lectura y validación de la hoja "Proyectos"

**Files:**
- Modify: `Análisis Financiero/Sistema/analisis_financiero.py`
- Test: `Análisis Financiero/Sistema/tests/test_lectura_proyectos.py`

**Interfaces:**
- Consumes: `HOJA_PROYECTOS` (Task 1)
- Produces: `leer_filas_proyectos(ws_proyectos) -> tuple[list[dict], list[str]]` (cada dict de la lista: `{"fila": int, "tag": str, "nombre": str}`)

- [ ] **Step 1: Escribir el test que falla**

```python
# Análisis Financiero/Sistema/tests/test_lectura_proyectos.py
import analisis_financiero as af


def _ws_proyectos_con_filas(tmp_path, filas):
    """filas: lista de tuplas (tag, nombre) o (tag, nombre) con alguno en None."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    for idx, (tag, nombre) in enumerate(filas, start=2):
        ws.cell(row=idx, column=1, value=tag)
        ws.cell(row=idx, column=2, value=nombre)
    return ws


def test_lee_filas_validas_con_tag_y_nombre(tmp_path):
    ws = _ws_proyectos_con_filas(tmp_path, [("UMAG", "UMAG"), ("CFLI", "Cesfam Limache")])
    filas_validas, avisos = af.leer_filas_proyectos(ws)
    assert filas_validas == [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 3, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ]
    assert avisos == []


def test_fila_sin_tag_se_salta_con_aviso(tmp_path):
    ws = _ws_proyectos_con_filas(tmp_path, [(None, "Proyecto sin tag"), ("UMAG", "UMAG")])
    filas_validas, avisos = af.leer_filas_proyectos(ws)
    assert filas_validas == [{"fila": 3, "tag": "UMAG", "nombre": "UMAG"}]
    assert len(avisos) == 1
    assert "Fila 2" in avisos[0]


def test_fila_sin_nombre_se_salta_con_aviso(tmp_path):
    ws = _ws_proyectos_con_filas(tmp_path, [("UMAG", None)])
    filas_validas, avisos = af.leer_filas_proyectos(ws)
    assert filas_validas == []
    assert len(avisos) == 1


def test_tag_duplicado_usa_la_primera_fila_y_avisa_de_la_segunda(tmp_path):
    ws = _ws_proyectos_con_filas(tmp_path, [("UMAG", "UMAG"), ("UMAG", "UMAG duplicado")])
    filas_validas, avisos = af.leer_filas_proyectos(ws)
    assert filas_validas == [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}]
    assert len(avisos) == 1
    assert "duplicado" in avisos[0]


def test_hoja_sin_filas_de_datos_no_produce_avisos(tmp_path):
    ws = _ws_proyectos_con_filas(tmp_path, [])
    filas_validas, avisos = af.leer_filas_proyectos(ws)
    assert filas_validas == []
    assert avisos == []
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_lectura_proyectos.py -v`
Expected: FAIL con `AttributeError: module 'analisis_financiero' has no attribute 'leer_filas_proyectos'`

- [ ] **Step 3: Agregar la función al final de `analisis_financiero.py`**

```python
# ── LECTURA DE LA HOJA "PROYECTOS" ───────────────────────────────────────────

def leer_filas_proyectos(ws_proyectos) -> tuple[list[dict], list[str]]:
    """Recorre la hoja 'Proyectos' desde la fila 2. Filas sin TAG o sin
    Nombre se saltan con aviso. TAG duplicado: se queda con la primera
    fila, avisa de las siguientes."""
    filas_validas = []
    avisos = []
    tags_vistos = set()

    for fila_idx in range(2, ws_proyectos.max_row + 1):
        tag = ws_proyectos.cell(row=fila_idx, column=1).value
        nombre = ws_proyectos.cell(row=fila_idx, column=2).value

        if not tag or not nombre:
            if tag or nombre:
                avisos.append(f"Fila {fila_idx}: falta TAG o Nombre, se salta.")
            continue

        if tag in tags_vistos:
            avisos.append(f"Fila {fila_idx}: TAG '{tag}' duplicado, se usa la primera fila.")
            continue

        tags_vistos.add(tag)
        filas_validas.append({"fila": fila_idx, "tag": tag, "nombre": nombre})

    return filas_validas, avisos
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_lectura_proyectos.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add "Análisis Financiero/Sistema/analisis_financiero.py" "Análisis Financiero/Sistema/tests/test_lectura_proyectos.py"
git commit -m "feat(analisis-financiero): lectura y validacion de filas de la hoja Proyectos"
```

---

### Task 5: Creación de carpetas de proyecto

**Files:**
- Modify: `Análisis Financiero/Sistema/analisis_financiero.py`
- Test: `Análisis Financiero/Sistema/tests/test_carpetas_proyecto.py`

**Interfaces:**
- Consumes: salida de `leer_filas_proyectos` (Task 4): `list[dict]` con clave `"nombre"`
- Produces: `asegurar_carpeta_proyecto(nombre_proyecto: str, raiz_facturas: Path) -> bool`, `asegurar_carpetas_proyectos(filas_validas: list[dict], raiz_facturas: Path) -> list[str]`

- [ ] **Step 1: Escribir el test que falla**

```python
# Análisis Financiero/Sistema/tests/test_carpetas_proyecto.py
import analisis_financiero as af


def test_asegurar_carpeta_proyecto_crea_la_carpeta_si_no_existe(tmp_path):
    creada = af.asegurar_carpeta_proyecto("Cesfam Limache", tmp_path)
    assert creada is True
    assert (tmp_path / "Cesfam Limache").is_dir()


def test_asegurar_carpeta_proyecto_no_duplica_si_ya_existe(tmp_path):
    (tmp_path / "UMAG").mkdir()
    creada = af.asegurar_carpeta_proyecto("UMAG", tmp_path)
    assert creada is False


def test_asegurar_carpetas_proyectos_devuelve_solo_las_nuevas(tmp_path):
    (tmp_path / "UMAG").mkdir()
    filas_validas = [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 3, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ]
    creadas = af.asegurar_carpetas_proyectos(filas_validas, tmp_path)
    assert creadas == ["Cesfam Limache"]
    assert (tmp_path / "Cesfam Limache").is_dir()
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_carpetas_proyecto.py -v`
Expected: FAIL con `AttributeError`

- [ ] **Step 3: Agregar las funciones al final de `analisis_financiero.py`**

```python
# ── CARPETAS DE PROYECTO ─────────────────────────────────────────────────────

def asegurar_carpeta_proyecto(nombre_proyecto: str, raiz_facturas: Path) -> bool:
    """Crea raiz_facturas/<nombre_proyecto>/ si no existe. Devuelve True si
    la creó, False si ya existía. raiz_facturas debe ser la fuente REAL que
    lee Centro de Costos hoy (Sitio de comunicación - Centro de Costos 1/
    Facturas y Boletas/), nunca la carpeta legado."""
    carpeta = raiz_facturas / nombre_proyecto
    if carpeta.exists():
        return False
    carpeta.mkdir(parents=True)
    return True


def asegurar_carpetas_proyectos(filas_validas: list[dict], raiz_facturas: Path) -> list[str]:
    """Aplica asegurar_carpeta_proyecto a cada fila válida. Devuelve los
    nombres de las carpetas que se crearon (para el informe de consola)."""
    creadas = []
    for fila_info in filas_validas:
        if asegurar_carpeta_proyecto(fila_info["nombre"], raiz_facturas):
            creadas.append(fila_info["nombre"])
    return creadas
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_carpetas_proyecto.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add "Análisis Financiero/Sistema/analisis_financiero.py" "Análisis Financiero/Sistema/tests/test_carpetas_proyecto.py"
git commit -m "feat(analisis-financiero): creacion de carpetas de proyecto nuevas"
```

---

### Task 6: Backup con timestamp

**Files:**
- Modify: `Análisis Financiero/Sistema/analisis_financiero.py`
- Test: `Análisis Financiero/Sistema/tests/test_backup.py`

**Interfaces:**
- Consumes: nada nuevo
- Produces: `hacer_backup(ruta_excel: Path, raiz_respaldos: Path) -> Path | None`

- [ ] **Step 1: Escribir el test que falla**

```python
# Análisis Financiero/Sistema/tests/test_backup.py
from datetime import datetime

import openpyxl

import analisis_financiero as af


def test_hacer_backup_devuelve_none_si_el_archivo_no_existe(tmp_path):
    ruta = tmp_path / "no existe.xlsx"
    assert af.hacer_backup(ruta, tmp_path / "Respaldos") is None


def test_hacer_backup_copia_el_archivo_a_una_subcarpeta_del_mes(tmp_path):
    ruta_excel = tmp_path / "Análisis de Proyectos.xlsx"
    openpyxl.Workbook().save(ruta_excel)
    raiz_respaldos = tmp_path / "Respaldos"

    destino = af.hacer_backup(ruta_excel, raiz_respaldos)

    assert destino is not None
    assert destino.exists()
    ahora = datetime.now()
    assert destino.parent.name == f"{af.MESES_ES[ahora.month]} {ahora.year}"
    assert destino.name.startswith("Análisis de Proyectos - backup ")
    assert destino.suffix == ".xlsx"
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_backup.py -v`
Expected: FAIL con `AttributeError`

- [ ] **Step 3: Agregar la constante y la función al final de `analisis_financiero.py`**

```python
# ── BACKUP ────────────────────────────────────────────────────────────────

import shutil
from datetime import datetime

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre",
    12: "Diciembre",
}


def hacer_backup(ruta_excel: Path, raiz_respaldos: Path) -> Path | None:
    """Copia ruta_excel a raiz_respaldos/<Mes Año>/Análisis de Proyectos -
    backup <fecha> <hora>.xlsx antes de escribir -- mismo patrón que
    Centro de Costos. Devuelve None si ruta_excel todavía no existe (nada
    que respaldar)."""
    if not ruta_excel.exists():
        return None
    ahora = datetime.now()
    carpeta_mes = raiz_respaldos / f"{MESES_ES[ahora.month]} {ahora.year}"
    carpeta_mes.mkdir(parents=True, exist_ok=True)
    marca_tiempo = ahora.strftime("%Y-%m-%d %H%M%S")
    destino = carpeta_mes / f"Análisis de Proyectos - backup {marca_tiempo}.xlsx"
    shutil.copy2(ruta_excel, destino)
    return destino
```

Nota: mover el `import shutil` y `from datetime import datetime` al bloque de imports al inicio del archivo (junto a `from pathlib import Path` y `import openpyxl`) en vez de dejarlos a mitad de archivo -- se muestran acá junto a la función por claridad de este step, pero al aplicar el diff van arriba.

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_backup.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add "Análisis Financiero/Sistema/analisis_financiero.py" "Análisis Financiero/Sistema/tests/test_backup.py"
git commit -m "feat(analisis-financiero): backup con timestamp antes de escribir"
```

---

### Task 7: Regenerar la hoja "Detalle Costos Reales"

**Files:**
- Modify: `Análisis Financiero/Sistema/analisis_financiero.py`
- Test: `Análisis Financiero/Sistema/tests/test_hoja_detalle_costos_reales.py`

**Interfaces:**
- Consumes: `mapear_categoria_a_bucket` (Task 2), `HOJA_DETALLE_COSTOS_REALES` (Task 1), salida de `agrupar_por_proyecto_y_subcategoria` (Task 3): `dict[tuple[str, str], float]`
- Produces: `regenerar_hoja_detalle_costos_reales(wb, agrupado: dict[tuple[str, str], float]) -> list[str]` (lista de avisos de categorías sin mapeo explícito)

- [ ] **Step 1: Escribir el test que falla**

```python
# Análisis Financiero/Sistema/tests/test_hoja_detalle_costos_reales.py
import analisis_financiero as af


def test_regenerar_escribe_una_fila_por_clave_con_bucket_calculado(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    agrupado = {
        ("UMAG", "Materiales"): 70000.0,
        ("UMAG", "Equipos-Herramientas"): 90000.0,
        ("CFLI", "Combustible"): 45000.0,
    }

    avisos = af.regenerar_hoja_detalle_costos_reales(wb, agrupado)

    ws = wb[af.HOJA_DETALLE_COSTOS_REALES]
    filas = [
        (ws.cell(row=r, column=1).value, ws.cell(row=r, column=2).value,
         ws.cell(row=r, column=3).value, ws.cell(row=r, column=4).value)
        for r in range(2, ws.max_row + 1)
    ]
    assert ("UMAG", "Materiales", "Materiales", 70000.0) in filas
    assert ("UMAG", "Equipos-Herramientas", "Equipos", 90000.0) in filas
    assert ("CFLI", "Combustible", "Otros", 45000.0) in filas
    assert len(filas) == 3
    assert len(avisos) == 1
    assert "Combustible" in avisos[0]


def test_regenerar_borra_filas_de_la_corrida_anterior(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.regenerar_hoja_detalle_costos_reales(wb, {("UMAG", "Materiales"): 1000.0})
    af.regenerar_hoja_detalle_costos_reales(wb, {("CFLI", "Materiales"): 2000.0})

    ws = wb[af.HOJA_DETALLE_COSTOS_REALES]
    filas = [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]
    assert filas == ["CFLI"]


def test_regenerar_con_agrupado_vacio_deja_solo_el_encabezado(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.regenerar_hoja_detalle_costos_reales(wb, {})
    ws = wb[af.HOJA_DETALLE_COSTOS_REALES]
    assert ws.max_row == 1
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_hoja_detalle_costos_reales.py -v`
Expected: FAIL con `AttributeError`

- [ ] **Step 3: Agregar la función al final de `analisis_financiero.py`**

```python
# ── HOJA "DETALLE COSTOS REALES" (100% regenerada cada corrida) ─────────────

def regenerar_hoja_detalle_costos_reales(wb, agrupado: dict[tuple[str, str], float]) -> list[str]:
    """Borra todas las filas de datos (fila 2 en adelante) y las reescribe
    completas desde 'agrupado' -- mismo patrón que las hojas de proyecto de
    Centro de Costos: se recalcula entera, nunca se acumula a mano. Devuelve
    avisos de subcategorías sin mapeo explícito (caen en 'Otros')."""
    ws = wb[HOJA_DETALLE_COSTOS_REALES]
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)

    avisos = []
    fila = 2
    for (tag, subcategoria), total in sorted(agrupado.items()):
        bucket, es_explicito = mapear_categoria_a_bucket(subcategoria)
        if not es_explicito:
            avisos.append(
                f"Categoría '{subcategoria}' (proyecto {tag}) sin mapeo explícito, va a 'Otros'."
            )
        ws.cell(row=fila, column=1, value=tag)
        ws.cell(row=fila, column=2, value=subcategoria)
        ws.cell(row=fila, column=3, value=bucket)
        ws.cell(row=fila, column=4, value=total)
        fila += 1

    return avisos
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_hoja_detalle_costos_reales.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add "Análisis Financiero/Sistema/analisis_financiero.py" "Análisis Financiero/Sistema/tests/test_hoja_detalle_costos_reales.py"
git commit -m "feat(analisis-financiero): regenerar hoja Detalle Costos Reales"
```

---

### Task 8: Fórmulas de la hoja "Proyectos"

**Files:**
- Modify: `Análisis Financiero/Sistema/analisis_financiero.py`
- Test: `Análisis Financiero/Sistema/tests/test_formulas_proyectos.py`

**Interfaces:**
- Consumes: `HOJA_DETALLE_COSTOS_REALES` (Task 1), salida de `leer_filas_proyectos` (Task 4): `list[dict]` con clave `"fila"`
- Produces: `asegurar_formulas_proyectos(ws_proyectos, filas_validas: list[dict]) -> None`

- [ ] **Step 1: Escribir el test que falla**

```python
# Análisis Financiero/Sistema/tests/test_formulas_proyectos.py
import analisis_financiero as af


def test_asegura_formulas_sumifs_y_derivadas_en_la_fila_del_proyecto(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="UMAG")
    ws.cell(row=2, column=2, value="UMAG")
    filas_validas = [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}]

    af.asegurar_formulas_proyectos(ws, filas_validas)

    assert ws.cell(row=2, column=11).value == (
        "=SUMIFS('Detalle Costos Reales'!$D:$D,"
        "'Detalle Costos Reales'!$A:$A,$A2,"
        "'Detalle Costos Reales'!$C:$C,\"Materiales\")"
    )
    assert ws.cell(row=2, column=12).value == (
        "=SUMIFS('Detalle Costos Reales'!$D:$D,"
        "'Detalle Costos Reales'!$A:$A,$A2,"
        "'Detalle Costos Reales'!$C:$C,\"Equipos\")"
    )
    assert ws.cell(row=2, column=13).value == (
        "=SUMIFS('Detalle Costos Reales'!$D:$D,"
        "'Detalle Costos Reales'!$A:$A,$A2,"
        "'Detalle Costos Reales'!$C:$C,\"Otros\")"
    )
    assert ws.cell(row=2, column=15).value == "=G2+H2+I2+J2"
    assert ws.cell(row=2, column=16).value == "=K2+L2+M2+N2"
    assert ws.cell(row=2, column=17).value == "=F2-O2"
    assert ws.cell(row=2, column=18).value == "=F2-P2"
    assert ws.cell(row=2, column=19).value == "=P2/O2-1"


def test_no_toca_columnas_manuales(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="UMAG")
    ws.cell(row=2, column=2, value="UMAG")
    ws.cell(row=2, column=6, value=1000000)  # Monto de Venta, manual
    filas_validas = [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}]

    af.asegurar_formulas_proyectos(ws, filas_validas)

    assert ws.cell(row=2, column=6).value == 1000000
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_formulas_proyectos.py -v`
Expected: FAIL con `AttributeError`

- [ ] **Step 3: Agregar la función al final de `analisis_financiero.py`**

```python
# ── FÓRMULAS DE LA HOJA "PROYECTOS" ──────────────────────────────────────────

def asegurar_formulas_proyectos(ws_proyectos, filas_validas: list[dict]) -> None:
    """Escribe las columnas derivadas (K/L/M = SUMIFS hacia 'Detalle Costos
    Reales'; O/P/Q/R/S = totales/márgenes/desviación) para cada fila válida.
    Nunca toca las columnas manuales (A-J, N)."""
    for fila_info in filas_validas:
        r = fila_info["fila"]
        tag_ref = f"$A{r}"

        for columna, bucket in ((11, "Materiales"), (12, "Equipos"), (13, "Otros")):
            ws_proyectos.cell(row=r, column=columna, value=(
                f"=SUMIFS('{HOJA_DETALLE_COSTOS_REALES}'!$D:$D,"
                f"'{HOJA_DETALLE_COSTOS_REALES}'!$A:$A,{tag_ref},"
                f"'{HOJA_DETALLE_COSTOS_REALES}'!$C:$C,\"{bucket}\")"
            ))

        ws_proyectos.cell(row=r, column=15, value=f"=G{r}+H{r}+I{r}+J{r}")
        ws_proyectos.cell(row=r, column=16, value=f"=K{r}+L{r}+M{r}+N{r}")
        ws_proyectos.cell(row=r, column=17, value=f"=F{r}-O{r}")
        ws_proyectos.cell(row=r, column=18, value=f"=F{r}-P{r}")
        ws_proyectos.cell(row=r, column=19, value=f"=P{r}/O{r}-1")
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_formulas_proyectos.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add "Análisis Financiero/Sistema/analisis_financiero.py" "Análisis Financiero/Sistema/tests/test_formulas_proyectos.py"
git commit -m "feat(analisis-financiero): formulas SUMIFS y derivadas de la hoja Proyectos"
```

---

### Task 9: Fórmulas de la hoja "Indicadores"

**Files:**
- Modify: `Análisis Financiero/Sistema/analisis_financiero.py`
- Test: `Análisis Financiero/Sistema/tests/test_formulas_indicadores.py`

**Interfaces:**
- Consumes: `HOJA_INDICADORES`, `HOJA_PROYECTOS` (Task 1), salida de `leer_filas_proyectos` (Task 4): `list[dict]` con clave `"fila"`
- Produces: `asegurar_hoja_indicadores(wb, filas_validas: list[dict]) -> None`

**Nota de diseño importante:** la hoja "Indicadores" se regenera compacta (fila 2, 3, 4... sin huecos), pero las fórmulas deben apuntar a la fila REAL del proyecto en "Proyectos" (que sí puede tener huecos si alguna fila fue inválida) -- por eso el test incluye un caso con hueco.

- [ ] **Step 1: Escribir el test que falla**

```python
# Análisis Financiero/Sistema/tests/test_formulas_indicadores.py
import analisis_financiero as af


def test_una_fila_referencia_las_columnas_correctas_de_proyectos(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    filas_validas = [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}]

    af.asegurar_hoja_indicadores(wb, filas_validas)

    ws = wb[af.HOJA_INDICADORES]
    assert ws.cell(row=2, column=1).value == "=Proyectos!A2"
    assert ws.cell(row=2, column=2).value == "=Proyectos!B2"
    assert ws.cell(row=2, column=3).value == "=Proyectos!R2/Proyectos!P2"
    assert ws.cell(row=2, column=4).value == "=Proyectos!R2/Proyectos!F2"
    assert ws.cell(row=2, column=5).value == "=Proyectos!F2/Proyectos!K2"
    assert ws.cell(row=2, column=6).value == "=Proyectos!F2/Proyectos!L2"
    assert ws.cell(row=2, column=7).value == "=Proyectos!F2/Proyectos!N2"
    assert ws.cell(row=2, column=8).value == "=Proyectos!F2/Proyectos!M2"
    assert ws.cell(row=2, column=9).value == "=Proyectos!K2/Proyectos!F2"
    assert ws.cell(row=2, column=10).value == "=Proyectos!L2/Proyectos!F2"
    assert ws.cell(row=2, column=11).value == "=Proyectos!N2/Proyectos!F2"
    assert ws.cell(row=2, column=12).value == "=Proyectos!M2/Proyectos!F2"
    assert ws.cell(row=2, column=13).value == "=Proyectos!K2/Proyectos!G2-1"
    assert ws.cell(row=2, column=14).value == "=Proyectos!L2/Proyectos!H2-1"
    assert ws.cell(row=2, column=15).value == "=Proyectos!N2/Proyectos!I2-1"
    assert ws.cell(row=2, column=16).value == "=Proyectos!M2/Proyectos!J2-1"


def test_fila_con_hueco_en_proyectos_queda_compacta_en_indicadores_pero_referencia_la_fila_real(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    # Proyectos fila 3 fue invalida y se salto -- el segundo proyecto valido
    # esta en la fila 4 de "Proyectos".
    filas_validas = [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 4, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ]

    af.asegurar_hoja_indicadores(wb, filas_validas)

    ws = wb[af.HOJA_INDICADORES]
    assert ws.cell(row=2, column=1).value == "=Proyectos!A2"
    assert ws.cell(row=3, column=1).value == "=Proyectos!A4"
    assert ws.cell(row=3, column=3).value == "=Proyectos!R4/Proyectos!P4"


def test_regenerar_borra_filas_de_la_corrida_anterior(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "CFLI", "nombre": "Cesfam Limache"}])

    ws = wb[af.HOJA_INDICADORES]
    assert ws.max_row == 2
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_formulas_indicadores.py -v`
Expected: FAIL con `AttributeError`

- [ ] **Step 3: Agregar la función al final de `analisis_financiero.py`**

```python
# ── FÓRMULAS DE LA HOJA "INDICADORES" (100% regenerada cada corrida) ────────

def asegurar_hoja_indicadores(wb, filas_validas: list[dict]) -> None:
    """Regenera 'Indicadores' completa: una fila compacta por proyecto
    válido (sin huecos), pero cada fórmula referencia la fila REAL del
    proyecto en 'Proyectos' (que sí puede tener huecos)."""
    ws = wb[HOJA_INDICADORES]
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)

    fila_destino = 2
    for fila_info in filas_validas:
        r = fila_info["fila"]
        ws.cell(row=fila_destino, column=1, value=f"=Proyectos!A{r}")
        ws.cell(row=fila_destino, column=2, value=f"=Proyectos!B{r}")
        ws.cell(row=fila_destino, column=3, value=f"=Proyectos!R{r}/Proyectos!P{r}")
        ws.cell(row=fila_destino, column=4, value=f"=Proyectos!R{r}/Proyectos!F{r}")
        ws.cell(row=fila_destino, column=5, value=f"=Proyectos!F{r}/Proyectos!K{r}")
        ws.cell(row=fila_destino, column=6, value=f"=Proyectos!F{r}/Proyectos!L{r}")
        ws.cell(row=fila_destino, column=7, value=f"=Proyectos!F{r}/Proyectos!N{r}")
        ws.cell(row=fila_destino, column=8, value=f"=Proyectos!F{r}/Proyectos!M{r}")
        ws.cell(row=fila_destino, column=9, value=f"=Proyectos!K{r}/Proyectos!F{r}")
        ws.cell(row=fila_destino, column=10, value=f"=Proyectos!L{r}/Proyectos!F{r}")
        ws.cell(row=fila_destino, column=11, value=f"=Proyectos!N{r}/Proyectos!F{r}")
        ws.cell(row=fila_destino, column=12, value=f"=Proyectos!M{r}/Proyectos!F{r}")
        ws.cell(row=fila_destino, column=13, value=f"=Proyectos!K{r}/Proyectos!G{r}-1")
        ws.cell(row=fila_destino, column=14, value=f"=Proyectos!L{r}/Proyectos!H{r}-1")
        ws.cell(row=fila_destino, column=15, value=f"=Proyectos!N{r}/Proyectos!I{r}-1")
        ws.cell(row=fila_destino, column=16, value=f"=Proyectos!M{r}/Proyectos!J{r}-1")
        fila_destino += 1
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_formulas_indicadores.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add "Análisis Financiero/Sistema/analisis_financiero.py" "Análisis Financiero/Sistema/tests/test_formulas_indicadores.py"
git commit -m "feat(analisis-financiero): formulas de la hoja Indicadores (playbook de KPIs)"
```

---

### Task 10: Orquestador `ejecutar()` / `main()` + idempotencia

**Files:**
- Modify: `Análisis Financiero/Sistema/analisis_financiero.py`
- Test: `Análisis Financiero/Sistema/tests/test_ejecutar.py`

**Interfaces:**
- Consumes: todas las funciones de las Tasks 1-9
- Produces: `ejecutar(ruta_excel_af: Path, ruta_excel_cc: Path, raiz_facturas_cc: Path, raiz_respaldos: Path, dry_run: bool = False) -> dict` (claves: `"avisos": list[str]`, `"carpetas_creadas": list[str]`, `"categorias_no_mapeadas": list[str]`, `"error": str | None`), `main() -> None`

- [ ] **Step 1: Escribir el test que falla**

```python
# Análisis Financiero/Sistema/tests/test_ejecutar.py
import openpyxl

import analisis_financiero as af


def _crear_excel_cc(tmp_path, filas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Detalle"
    encabezados = [
        "N° Ref.", "Proyecto", "Tipo de Proyecto", "N° Documento", "Nombre Ítem",
        "Descripción", "Categoría Ítem", "Cantidad", "P. Unitario sin IVA",
        "Total sin IVA (CLP)", "Total con IVA (CLP)",
    ]
    for col, encabezado in enumerate(encabezados, start=1):
        ws.cell(row=1, column=col, value=encabezado)
    for fila_idx, (n_ref, categoria_item, total_sin_iva) in enumerate(filas, start=2):
        ws.cell(row=fila_idx, column=1, value=n_ref)
        ws.cell(row=fila_idx, column=7, value=categoria_item)
        ws.cell(row=fila_idx, column=10, value=total_sin_iva)
    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(ruta)
    return ruta


def _crear_excel_af_con_un_proyecto(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="UMAG")
    ws.cell(row=2, column=2, value="UMAG")
    ws.cell(row=2, column=6, value=1000000)
    wb.save(ruta)
    return ruta


def test_ejecutar_de_punta_a_punta_crea_carpeta_regenera_hojas_y_guarda(tmp_path):
    ruta_af = _crear_excel_af_con_un_proyecto(tmp_path)
    ruta_cc = _crear_excel_cc(tmp_path, [("UMAG-001", "Materiales", 50000.0)])
    raiz_facturas = tmp_path / "Facturas y Boletas"
    raiz_respaldos = tmp_path / "Respaldos"

    resumen = af.ejecutar(ruta_af, ruta_cc, raiz_facturas, raiz_respaldos)

    assert resumen["error"] is None
    assert resumen["carpetas_creadas"] == ["UMAG"]
    assert (raiz_facturas / "UMAG").is_dir()

    wb = openpyxl.load_workbook(ruta_af)
    ws_detalle = wb[af.HOJA_DETALLE_COSTOS_REALES]
    assert ws_detalle.cell(row=2, column=4).value == 50000.0
    ws_proyectos = wb[af.HOJA_PROYECTOS]
    assert ws_proyectos.cell(row=2, column=11).value.startswith("=SUMIFS(")
    assert list((raiz_respaldos).rglob("*.xlsx")) == []  # no habia archivo previo que respaldar


def test_ejecutar_dos_veces_es_idempotente(tmp_path):
    ruta_af = _crear_excel_af_con_un_proyecto(tmp_path)
    ruta_cc = _crear_excel_cc(tmp_path, [("UMAG-001", "Materiales", 50000.0)])
    raiz_facturas = tmp_path / "Facturas y Boletas"
    raiz_respaldos = tmp_path / "Respaldos"

    af.ejecutar(ruta_af, ruta_cc, raiz_facturas, raiz_respaldos)
    wb_1 = openpyxl.load_workbook(ruta_af)
    detalle_1 = [
        [wb_1[af.HOJA_DETALLE_COSTOS_REALES].cell(row=r, column=c).value for c in range(1, 5)]
        for r in range(1, wb_1[af.HOJA_DETALLE_COSTOS_REALES].max_row + 1)
    ]

    af.ejecutar(ruta_af, ruta_cc, raiz_facturas, raiz_respaldos)
    wb_2 = openpyxl.load_workbook(ruta_af)
    detalle_2 = [
        [wb_2[af.HOJA_DETALLE_COSTOS_REALES].cell(row=r, column=c).value for c in range(1, 5)]
        for r in range(1, wb_2[af.HOJA_DETALLE_COSTOS_REALES].max_row + 1)
    ]

    assert detalle_1 == detalle_2
    # la segunda corrida ya no crea la carpeta (ya existia)
    resumen_2 = af.ejecutar(ruta_af, ruta_cc, raiz_facturas, raiz_respaldos)
    assert resumen_2["carpetas_creadas"] == []


def test_ejecutar_dry_run_no_escribe_nada(tmp_path):
    ruta_af = _crear_excel_af_con_un_proyecto(tmp_path)
    ruta_cc = _crear_excel_cc(tmp_path, [("UMAG-001", "Combustible", 10000.0)])
    raiz_facturas = tmp_path / "Facturas y Boletas"
    raiz_respaldos = tmp_path / "Respaldos"
    contenido_antes = ruta_af.read_bytes()

    resumen = af.ejecutar(ruta_af, ruta_cc, raiz_facturas, raiz_respaldos, dry_run=True)

    assert ruta_af.read_bytes() == contenido_antes
    assert not (raiz_facturas / "UMAG").exists()
    assert resumen["carpetas_creadas"] == ["UMAG"]  # lo que SE CREARIA, sin crearlo
    assert resumen["categorias_no_mapeadas"] == ["Combustible"]


def test_ejecutar_sin_centro_de_costos_avisa_y_no_falla(tmp_path):
    ruta_af = _crear_excel_af_con_un_proyecto(tmp_path)
    ruta_cc = tmp_path / "no existe.xlsx"
    raiz_facturas = tmp_path / "Facturas y Boletas"
    raiz_respaldos = tmp_path / "Respaldos"

    resumen = af.ejecutar(ruta_af, ruta_cc, raiz_facturas, raiz_respaldos)

    assert resumen["error"] is None
    assert any("no se encontr" in aviso.lower() for aviso in resumen["avisos"])
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_ejecutar.py -v`
Expected: FAIL con `AttributeError: module 'analisis_financiero' has no attribute 'ejecutar'`

- [ ] **Step 3: Agregar el orquestador al final de `analisis_financiero.py`**

```python
# ── ORQUESTADOR ───────────────────────────────────────────────────────────

def ejecutar(
    ruta_excel_af: Path = RUTA_EXCEL,
    ruta_excel_cc: Path = RUTA_EXCEL_CENTRO_COSTOS,
    raiz_facturas_cc: Path = RAIZ_FACTURAS_CENTRO_COSTOS,
    raiz_respaldos: Path = RAIZ_RESPALDOS,
    dry_run: bool = False,
) -> dict:
    """Orquesta todo el flujo. Con dry_run=True no escribe nada -- ni backup,
    ni carpetas, ni el Excel -- solo reporta qué pasaría (usado por el
    comando 'status' del skill). Ningún paso levanta excepción hacia
    afuera: los errores quedan en resumen['error']/['avisos'] para que un
    caller externo (ej. el 'run' de Centro de Costos) nunca aborte por
    esto."""
    resumen = {"avisos": [], "carpetas_creadas": [], "categorias_no_mapeadas": [], "error": None}

    wb = asegurar_estructura_workbook(ruta_excel_af)
    ws_proyectos = wb[HOJA_PROYECTOS]
    filas_validas, avisos_lectura = leer_filas_proyectos(ws_proyectos)
    resumen["avisos"].extend(avisos_lectura)

    if not ruta_excel_cc.exists():
        resumen["avisos"].append(
            f"No se encontró {ruta_excel_cc}, no se actualizan costos reales."
        )
        return resumen

    items_detalle = leer_detalle_centro_costos(ruta_excel_cc)
    agrupado = agrupar_por_proyecto_y_subcategoria(items_detalle)

    if dry_run:
        for fila_info in filas_validas:
            if not (raiz_facturas_cc / fila_info["nombre"]).exists():
                resumen["carpetas_creadas"].append(fila_info["nombre"])
        categorias_no_mapeadas = set()
        for _, subcategoria in agrupado:
            _, es_explicito = mapear_categoria_a_bucket(subcategoria)
            if not es_explicito:
                categorias_no_mapeadas.add(subcategoria)
        resumen["categorias_no_mapeadas"] = sorted(categorias_no_mapeadas)
        return resumen

    try:
        hacer_backup(ruta_excel_af, raiz_respaldos)
    except PermissionError as exc:
        resumen["avisos"].append(f"No se pudo respaldar (¿archivo abierto?): {exc}")

    try:
        resumen["carpetas_creadas"] = asegurar_carpetas_proyectos(filas_validas, raiz_facturas_cc)
    except OSError as exc:
        resumen["avisos"].append(f"No se pudieron crear una o más carpetas de proyecto: {exc}")

    avisos_detalle = regenerar_hoja_detalle_costos_reales(wb, agrupado)
    resumen["avisos"].extend(avisos_detalle)
    resumen["categorias_no_mapeadas"] = sorted({
        aviso.split("'")[1] for aviso in avisos_detalle
    })

    asegurar_formulas_proyectos(ws_proyectos, filas_validas)
    asegurar_hoja_indicadores(wb, filas_validas)

    try:
        wb.save(ruta_excel_af)
    except PermissionError as exc:
        resumen["error"] = f"No se pudo guardar {ruta_excel_af} (¿archivo abierto?): {exc}"

    return resumen


def main() -> None:
    resumen = ejecutar()
    print("=== Análisis Financiero ===")
    if resumen["carpetas_creadas"]:
        print(f"Carpetas de proyecto creadas: {', '.join(resumen['carpetas_creadas'])}")
    if resumen["categorias_no_mapeadas"]:
        print(
            "Categorías sin mapeo explícito (van a 'Otros'): "
            + ", ".join(resumen["categorias_no_mapeadas"])
        )
    for aviso in resumen["avisos"]:
        print(f"[AVISO] {aviso}")
    if resumen["error"]:
        print(f"[ERROR] {resumen['error']}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/test_ejecutar.py -v`
Expected: 5 passed

- [ ] **Step 5: Correr la suite completa del módulo, confirmar que todo sigue pasando**

Run: `cd "Análisis Financiero/Sistema" && python -m pytest tests/ -v`
Expected: todos los tests de las Tasks 1-10 en PASS (28 tests en total)

- [ ] **Step 6: Commit**

```bash
git add "Análisis Financiero/Sistema/analisis_financiero.py" "Análisis Financiero/Sistema/tests/test_ejecutar.py"
git commit -m "feat(analisis-financiero): orquestador ejecutar()/main(), modo dry_run e idempotencia"
```

---

### Task 11: Skill `/Registro_Analisis_Financiero`

**Files:**
- Create: `Análisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md`
- Create: `Análisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py`

**Interfaces:**
- Consumes: `af.ejecutar(dry_run=...)`, `af.RUTA_EXCEL`, `af.RUTA_EXCEL_CENTRO_COSTOS`, `af.RAIZ_FACTURAS_CENTRO_COSTOS`, `af.RAIZ_RESPALDOS` (Task 10)
- Produces: comandos de CLI `status`/`run` (sin interfaz Python, es el punto de entrada del skill)

- [ ] **Step 1: Crear `driver.py`, mismo patrón que `Cotizador_Historico/driver.py` (status de solo lectura vía `dry_run=True`, run real vía `dry_run=False`)**

```python
# -*- coding: utf-8 -*-
"""
driver.py -- arnes de ejecucion para la skill Registro_Analisis_Financiero.

No reimplementa la logica: importa analisis_financiero.py desde Sistema/ y
expone dos comandos:

  status -> Solo lectura (dry_run=True): que carpetas de proyecto se
            crearian, que categorias de Centro de Costos caen en "Otros"
            por no tener mapeo explicito, sin tocar ningun archivo.

  run    -> Ejecucion real: backup, crea carpetas de proyecto nuevas,
            regenera "Detalle Costos Reales" y las formulas de "Proyectos"/
            "Indicadores", guarda el Excel.

Uso:
  python driver.py status
  python driver.py run
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Sistema"))

sys.dont_write_bytecode = True
import analisis_financiero as af  # noqa: E402


def cmd_status() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    print("=" * 70)
    print("  ESTADO ANÁLISIS FINANCIERO (solo lectura, no escribe nada)")
    print("=" * 70)

    print(f"\nExcel de trabajo: {af.RUTA_EXCEL}")
    print(f"  Existe: {af.RUTA_EXCEL.exists()}")
    print(f"\nCentro de Costos.xlsx: {af.RUTA_EXCEL_CENTRO_COSTOS}")
    print(f"  Existe: {af.RUTA_EXCEL_CENTRO_COSTOS.exists()}")

    resumen = af.ejecutar(dry_run=True)

    if resumen["carpetas_creadas"]:
        print(f"\nCarpetas de proyecto que SE CREARÍAN: {', '.join(resumen['carpetas_creadas'])}")
    else:
        print("\nNo hay carpetas de proyecto nuevas por crear.")

    if resumen["categorias_no_mapeadas"]:
        print(
            "\nCategorías de Centro de Costos sin mapeo explícito (caerían en 'Otros'): "
            + ", ".join(resumen["categorias_no_mapeadas"])
        )

    if resumen["avisos"]:
        print("\nAvisos:")
        for aviso in resumen["avisos"]:
            print(f"  [AVISO] {aviso}")

    print("\n" + "=" * 70)
    print("  Nada fue escrito. Para ejecutar de verdad: python driver.py run")
    print("=" * 70)
    return 0


def cmd_run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    af.main()
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("status", "run"):
        print("Uso: python driver.py [status|run]")
        return 2
    if sys.argv[1] == "status":
        return cmd_status()
    return cmd_run()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Crear `SKILL.md`**

```markdown
---
name: Registro_Analisis_Financiero
description: Consolida los costos reales por proyecto y categoría desde Centro de Costos hacia Análisis de Proyectos.xlsx (hojas Proyectos/Detalle Costos Reales/Indicadores), y crea la carpeta de facturas para proyectos nuevos agregados a mano en el Excel. Usar cuando el usuario pida actualizar Análisis Financiero, refrescar los indicadores de proyectos, ver el estado de Análisis de Proyectos.xlsx, o evaluar rentabilidad/KPIs de un proyecto.
---

# Registro Análisis Financiero

Herramienta de línea de comandos (Python + openpyxl), **solo lectura** sobre
`Centro de Costos/Excel/Centro de Costos.xlsx` -- nunca lo escribe. Todas las
rutas de este documento son relativas a la raíz del módulo
(`Análisis Financiero/`). El driver vive en
`.claude/skills/Registro_Analisis_Financiero/driver.py`.

Ver `../../CLAUDE.md` para el rol del agente (analista financiero, no solo
pipeline) y `docs/superpowers/specs/2026-07-20-analisis-financiero-design.md`
(raíz de `Finanzas QUEMPIN/`) para el diseño completo.

## Comandos

**`status`** -- solo lectura: qué carpetas de proyecto se crearían, qué
categorías de Centro de Costos caen en "Otros" por no tener mapeo explícito.

```
python ".claude/skills/Registro_Analisis_Financiero/driver.py" status
```

**`run`** -- ejecución real: backup de `Análisis de Proyectos.xlsx`, crea
carpetas de proyecto nuevas en
`Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y
Boletas/<Nombre>/`, regenera la hoja "Detalle Costos Reales" y las fórmulas
de "Proyectos"/"Indicadores". Idempotente: correrlo sin cambios en Centro de
Costos no altera nada.

```
python ".claude/skills/Registro_Analisis_Financiero/driver.py" run
```

También corre automáticamente al final de cada `run` de
`/Registro_Centro_de_Costos` (PASO 12d) -- no hace falta correrlo aparte
salvo que se quiera refrescar sin correr todo Centro de Costos.

## Gotchas

- **Mano de Obra Real es 100% manual** -- no hay categoría equivalente en
  Centro de Costos hoy. No esperar que `run` la complete sola.
- **Las columnas manuales de "Proyectos" nunca se tocan** (TAG, Nombre,
  Estado, fechas, Venta, proyectados, Mano de Obra Real) -- si algo ahí se
  ve mal, es un dato cargado a mano, no un bug de este script.
- **TAG proyecto debe calzar con el prefijo de Centro de Costos**
  (`PREFIJOS_PROYECTO` en `auditor_centro_costos.py`) -- si no calzan, los
  costos reales de ese proyecto quedan en $0 (el `SUMIFS` no encuentra
  filas), no hay error explícito por ahora.

## Troubleshooting

| Síntoma | Causa / fix |
|---|---|
| Costos reales en $0 para un proyecto con compras registradas | El TAG en "Proyectos" no calza con el prefijo real del `N° Ref.` en Centro de Costos -- revisar `PREFIJOS_PROYECTO` |
| `[AVISO] No se encontró .../Centro de Costos.xlsx` | Confirmar que `Centro de Costos/Excel/Centro de Costos.xlsx` existe |
| Categoría cae en "Otros" sin avisar en años anteriores pero ahora sí | Es esperado: cualquier `categoria_item` que no esté en `MAPEO_CATEGORIA_BUCKET` cae en "Otros" con aviso -- si merece su propio bucket, hay que agregarla a mano en `analisis_financiero.py` |
| `[ERROR] No se pudo guardar ...` | El Excel está abierto en otra aplicación -- cerrarlo y volver a correr `run` |
```

- [ ] **Step 3: Verificación manual (sin datos reales todavía, solo que el driver corre sin excepciones)**

Run: `cd "Análisis Financiero" && python ".claude/skills/Registro_Analisis_Financiero/driver.py" status`
Expected: imprime el bloque "ESTADO ANÁLISIS FINANCIERO", sin traceback (puede avisar que no hay carpetas nuevas si `Análisis de Proyectos.xlsx` sigue vacío).

- [ ] **Step 4: Commit**

```bash
git add "Análisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md" "Análisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py"
git commit -m "feat(analisis-financiero): skill Registro_Analisis_Financiero (status/run)"
```

---

### Task 12: Encadenar desde el `run` de Centro de Costos

**Files:**
- Modify: `Centro de Costos/Sistema/auditor_centro_costos.py` (agregar función cerca de `actualizar_visualizador` ~línea 1965, y una llamada en `main()` justo después del PASO 12c ~línea 2204)
- Test: `Centro de Costos/Sistema/tests/test_actualizar_analisis_financiero.py`

**Interfaces:**
- Consumes: `Análisis Financiero/Sistema/analisis_financiero.py::ejecutar()` (Task 10)
- Produces: `actualizar_analisis_financiero() -> bool` en `auditor_centro_costos.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# Centro de Costos/Sistema/tests/test_actualizar_analisis_financiero.py
import auditor_centro_costos as acc


def test_devuelve_false_y_no_lanza_si_no_existe_el_script_de_analisis_financiero(monkeypatch, tmp_path):
    ruta_falsa = tmp_path / "no existe" / "analisis_financiero.py"
    monkeypatch.setattr(acc, "RAIZ_ANALISIS_FINANCIERO", ruta_falsa.parent)

    resultado = acc.actualizar_analisis_financiero()

    assert resultado is False
```

- [ ] **Step 2: Correr el test, confirmar que falla**

Run: `cd "Centro de Costos/Sistema" && python -m pytest tests/test_actualizar_analisis_financiero.py -v`
Expected: FAIL con `AttributeError: module 'auditor_centro_costos' has no attribute 'actualizar_analisis_financiero'`

- [ ] **Step 3: Agregar `RAIZ_ANALISIS_FINANCIERO` al bloque de configuración (junto a `RAIZ_VISUALIZADOR_WEB`, línea 58)**

```python
RAIZ_ANALISIS_FINANCIERO = RAIZ_MODULO.parent / "Análisis Financiero"
```

- [ ] **Step 4: Agregar la función `actualizar_analisis_financiero()` inmediatamente después de `actualizar_visualizador()` (~línea 1990, antes de `def main():`)**

```python
def actualizar_analisis_financiero():
    """Actualiza Análisis Financiero/Análisis de Proyectos.xlsx (costos
    reales por proyecto/categoría + hoja Indicadores) a partir del Excel
    recien guardado -- mismo patron que actualizar_visualizador: corre al
    final de cada 'run' (PASO 12d), solo lee Centro de Costos.xlsx (no lo
    modifica), y si falla no aborta el run, solo advierte."""
    ruta_script = RAIZ_ANALISIS_FINANCIERO / "Sistema" / "analisis_financiero.py"
    if not ruta_script.exists():
        print(f"  [WARN] No existe {ruta_script}, se omite este paso.")
        return False
    import sys
    raiz_sistema_af = ruta_script.parent
    ya_en_path = str(raiz_sistema_af) in sys.path
    if not ya_en_path:
        sys.path.insert(0, str(raiz_sistema_af))
    try:
        sys.modules.pop("analisis_financiero", None)
        import analisis_financiero as af
        resumen = af.ejecutar()
        if resumen["error"]:
            print(f"  [WARN] Análisis Financiero terminó con error: {resumen['error']}")
            return False
        return True
    except Exception as e:
        print(f"  [WARN] No se pudo actualizar Análisis Financiero ({e}).")
        print("         El Excel de Centro de Costos si quedo guardado; correr manualmente "
              "'python driver.py run' en Análisis Financiero despues.")
        return False
```

- [ ] **Step 5: Agregar la llamada en `main()`, justo después del PASO 12c (línea 2203-2204)**

```python
    print("\n--- PASO 12c: Actualizar visualizador web ---")
    actualizar_visualizador()

    print("\n--- PASO 12d: Actualizar Análisis Financiero ---")
    actualizar_analisis_financiero()

```

- [ ] **Step 6: Correr el test, confirmar que pasa**

Run: `cd "Centro de Costos/Sistema" && python -m pytest tests/test_actualizar_analisis_financiero.py -v`
Expected: 1 passed

- [ ] **Step 7: Correr la suite completa de Centro de Costos, confirmar que nada se rompió**

Run: `cd "Centro de Costos/Sistema" && python -m pytest tests/ -v`
Expected: todos los tests existentes de Centro de Costos siguen en PASS, más el nuevo.

- [ ] **Step 8: Verificación manual de punta a punta (opcional, requiere datos reales -- confirmar con el usuario antes de correr `run` sobre el Excel real)**

Run: `cd "Centro de Costos" && python ".claude/skills/Registro_Centro_de_Costos/driver.py" status`
Expected: sigue funcionando igual que antes (el status no llama a `actualizar_analisis_financiero`, solo `run` lo hace).

- [ ] **Step 9: Commit**

```bash
git add "Centro de Costos/Sistema/auditor_centro_costos.py" "Centro de Costos/Sistema/tests/test_actualizar_analisis_financiero.py"
git commit -m "feat(centro-de-costos): encadenar Analisis Financiero al final del run (PASO 12d)"
```

---

## Self-Review

**Spec coverage:**
- Estructura de 3 hojas (Task 1), mapeo categoría→bucket (Task 2), lectura solo-lectura de Centro de Costos y agrupación (Task 3), lectura/validación de "Proyectos" (Task 4), creación de carpetas en la fuente real (Task 5), backup con timestamp (Task 6), regeneración de "Detalle Costos Reales" (Task 7), fórmulas de "Proyectos" (Task 8), fórmulas de "Indicadores"/playbook de KPIs (Task 9), orquestador + dry_run + idempotencia (Task 10), skill status/run (Task 11), encadenado al run de Centro de Costos (Task 12) — cubre todas las secciones del spec.
- Explícitamente fuera de alcance (dashboard HTML, automatizar Mano de Obra Real, Flujo de Caja, validaciones de datos, editar `PREFIJOS_PROYECTO`) — ningún task los implementa, consistente con el spec.

**Placeholder scan:** sin TBD/TODO; cada step tiene código completo y comandos con salida esperada.

**Type consistency:** `filas_validas: list[dict]` con claves `"fila"/"tag"/"nombre"` se usa igual en Tasks 4, 5, 8, 9, 10. `agrupado: dict[tuple[str, str], float]` igual en Tasks 3, 7, 10. `resumen: dict` con las mismas 4 claves (`avisos`, `carpetas_creadas`, `categorias_no_mapeadas`, `error`) en Tasks 10, 11, 12.
