# Visualizador Web de Análisis Financiero — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el primer dashboard HTML (Visualizador Web) del módulo `Sistema Analisis Financiero/`, con dos secciones (Proyectos, Clientes/CLTV), que excluye del cálculo de KPIs cualquier proyecto sin información manual completa y lo muestra en su lugar en una lista de pendientes con link a la planilla.

**Architecture:** Mismo patrón ya implementado en `Centro de Costos/Visualizador Web/`: un script `build_visualizador.py` recomputa en Python (nunca lee fórmulas de Excel cacheadas) un snapshot JSON saneado, lo incrusta en `template.html` (estructura/CSS/JS versionado, sin datos) produciendo `build/index.html` autocontenido, publicado como Claude Artifact privado con gate de contraseña. Encadenado al final de `ejecutar()` en `analisis_financiero.py`.

**Tech Stack:** Python 3 + openpyxl (ya usado en el repo), HTML/CSS/JS vanilla sin frameworks (SVG hecho a mano para gráficos, mismo criterio que Centro de Costos). Sin dependencias nuevas.

## Global Constraints

- Fuente de datos real: `Análisis Financiero/Análisis de Proyectos.xlsx` — nunca se escribe desde este visualizador, solo lectura (`data_only=True`).
- Las hojas "Indicadores"/"Clientes" del Excel son 100% fórmulas reescritas en cada `run` — **nunca leer esas celdas**; todo KPI se recomputa en Python replicando exactamente las fórmulas de `analisis_financiero.py` (`_formula_nota`, `_formula_evaluacion`, `asegurar_hoja_clientes`).
- Un proyecto es **completo** solo si tiene valor no vacío (no `None`) en las 6 columnas: `Monto de Venta (sin IVA)`, `Costos Materiales Proyectados`, `Costos Equipos Proyectados`, `Mano de Obra Proyectada`, `Otros Costos Proyectados`, `Mano de Obra Real`. Un valor `0` cuenta como cargado; solo `None`/vacío cuenta como incompleto.
- Proyecto incompleto → nunca se le calculan KPIs; entra a la lista de pendientes con el mensaje exacto `"<Nombre> — Falta ingresar información en 'Análisis de Proyectos'"` y el link `https://quempinspa2020.sharepoint.com/:x:/g/IQB005ljfV3VQp6CNg8pSS0tAdjFPmF8jOcQOeU3y0vIaIE?e=kaFVjO`.
- Cliente con proyectos mixtos → CLTV/AOV/Clasificación se calculan solo con sus proyectos completos; cliente con el 100% de sus proyectos incompletos no genera fila en la tabla de Clientes.
- Gate de contraseña: reutilizar la misma contraseña que ya usa Centro de Costos (`GATE_PASSWORD_NORM = 'combustion'` en `Centro de Costos/Visualizador Web/template.html`) — pedido explícito del usuario, no inventar una nueva.
- Datos incrustados en base64 dentro del HTML (no `fetch`) — mismo motivo que Centro de Costos (sandbox de Claude Artifact).
- Nunca testear contra el Excel real de la empresa — todos los tests usan workbooks temporales (`tmp_path`).
- Ver el spec completo: [`docs/superpowers/specs/2026-07-23-analisis-financiero-visualizador-web-design.md`](../specs/2026-07-23-analisis-financiero-visualizador-web-design.md).

---

### Task 1: Completitud + recomputo de KPIs de proyecto

**Files:**
- Create: `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py`
- Test: `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`
- Create: `Sistema Analisis Financiero/Visualizador Web/tests/conftest.py`

**Interfaces:**
- Consumes: `analisis_financiero.RUTA_EXCEL`, `analisis_financiero.HOJA_PROYECTOS`, `analisis_financiero.HOJA_DETALLE_COSTOS_REALES`, `analisis_financiero.HEADERS_PROYECTOS`, `analisis_financiero.MARGEN_OBJETIVO_NOTA`, `analisis_financiero.PESO_RENTABILIDAD_NOTA`, `analisis_financiero.PESO_DESVIACION_NOTA`, `analisis_financiero.asegurar_estructura_workbook` (solo en tests, para bootstrapear un Excel de prueba).
- Produces: `leer_proyectos(ws_proyectos) -> list[dict]`, `es_proyecto_completo(p: dict) -> bool`, `sumar_costos_reales_por_bucket(ws_detalle, tag: str) -> dict`, `calcular_kpis_proyecto(p: dict, costos_reales: dict) -> dict` (claves: `tag, nombre, cliente, estado, monto_venta, total_proyectado, total_real, margen_real, desviacion_pct, nota, evaluacion`) — usados por Task 3.

- [ ] **Step 1: Crear `tests/conftest.py`** (mismo patrón que `Sistema Analisis Financiero/Sistema/tests/conftest.py`):

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Sistema"))
```

- [ ] **Step 2: Escribir el test que falla primero**

```python
# Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py
import analisis_financiero as af
import build_visualizador as bv


def _fila_proyecto_completa(ws, fila, **overrides):
    valores = {
        "TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID",
        "Estado": "En Proceso", "Monto de Venta (sin IVA)": 1_000_000,
        "Costos Materiales Proyectados": 300_000, "Costos Equipos Proyectados": 200_000,
        "Mano de Obra Proyectada": 200_000, "Otros Costos Proyectados": 100_000,
        "Mano de Obra Real": 350_000,
    }
    valores.update(overrides)
    for nombre_col, valor in valores.items():
        col = af.HEADERS_PROYECTOS.index(nombre_col) + 1
        ws.cell(row=fila, column=col, value=valor)


def _fila_detalle(ws, fila, tag, bucket, total):
    ws.cell(row=fila, column=1, value=tag)
    ws.cell(row=fila, column=2, value=bucket)
    ws.cell(row=fila, column=3, value=bucket)
    ws.cell(row=fila, column=4, value=total)


def test_es_proyecto_completo_true_cuando_las_6_columnas_tienen_valor():
    p = {
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    assert bv.es_proyecto_completo(p) is True


def test_es_proyecto_completo_false_si_falta_mano_de_obra_real():
    p = {
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": None,
    }
    assert bv.es_proyecto_completo(p) is False


def test_es_proyecto_completo_true_con_costo_en_cero():
    # 0 es un dato cargado, no un vacío -- no debe contar como incompleto.
    p = {
        "monto_venta": 1_000_000, "materiales_proy": 0, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    assert bv.es_proyecto_completo(p) is True


def test_leer_proyectos_salta_filas_sin_tag_o_nombre(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    _fila_proyecto_completa(ws, 2)
    ws.cell(row=3, column=1, value=None)
    ws.cell(row=3, column=2, value="Fila incompleta de encabezados")

    proyectos = bv.leer_proyectos(ws)
    assert len(proyectos) == 1
    assert proyectos[0]["tag"] == "UMAG"


def test_sumar_costos_reales_por_bucket_agrupa_por_tag_y_bucket(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws_detalle = wb[af.HOJA_DETALLE_COSTOS_REALES]
    _fila_detalle(ws_detalle, 2, "UMAG", "Materiales", 250_000)
    _fila_detalle(ws_detalle, 3, "UMAG", "Equipos", 150_000)
    _fila_detalle(ws_detalle, 4, "CFLI", "Materiales", 999_999)  # otro proyecto, no debe sumar

    sumas = bv.sumar_costos_reales_por_bucket(ws_detalle, "UMAG")
    assert sumas == {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}


def test_calcular_kpis_proyecto_recomputa_igual_que_formula_excel():
    # Mismos numeros que documenta el spec (docs/superpowers/specs/2026-07-23-
    # analisis-financiero-visualizador-web-design.md §2): total_proyectado=800000,
    # total_real=750000 -> desviacion=-6.25%, margen_real=250000 (25% de venta,
    # exactamente el objetivo) -> nota=98, "Excelente".
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["total_proyectado"] == 800_000
    assert kpis["total_real"] == 750_000
    assert kpis["margen_real"] == 250_000
    assert round(kpis["desviacion_pct"], 4) == -0.0625
    assert kpis["nota"] == 98
    assert kpis["evaluacion"] == "Excelente"


def test_calcular_kpis_proyecto_evaluacion_requiere_atencion_bajo_55():
    p = {
        "tag": "CFLI", "nombre": "Cesfam Limache", "cliente": "Cesfam", "estado": "En Proceso",
        "monto_venta": 1_000_000, "materiales_proy": 100_000, "equipos_proy": 100_000,
        "mo_proy": 100_000, "otros_proy": 100_000, "mo_real": 700_000,
    }
    costos_reales = {"Materiales": 300_000.0, "Equipos": 300_000.0, "Otros": 100_000.0}
    # total_real = 300000+300000+100000+700000 = 1400000 -> margen_real negativo

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["margen_real"] < 0
    assert kpis["evaluacion"] == "Requiere atención"
```

- [ ] **Step 3: Correr los tests para verificar que fallan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_visualizador'`

- [ ] **Step 4: Crear `build_visualizador.py` con la implementación mínima de este task**

```python
# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el visualizador web de Análisis Financiero.

Las hojas "Indicadores"/"Clientes" de Análisis de Proyectos.xlsx son 100%
formulas que analisis_financiero.py reescribe en cada corrida -- openpyxl
nunca las calcula, asi que su valor cacheado queda obsoleto justo despues de
guardar. Este script NUNCA lee esas celdas: recomputa las mismas formulas en
Python a partir de las columnas manuales de "Proyectos" y de la hoja
"Detalle Costos Reales" (100% valores, no formulas anidadas). Mismo patron ya
resuelto en Centro de Costos/Visualizador Web/build_visualizador.py.

Ver docs/superpowers/specs/2026-07-23-analisis-financiero-visualizador-web-
design.md para el diseno completo.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Sistema"))
import analisis_financiero as af  # noqa: E402

RAIZ = Path(__file__).resolve().parent  # Sistema Analisis Financiero/Visualizador Web/
RUTA_EXCEL = af.RUTA_EXCEL
RUTA_TEMPLATE = RAIZ / "template.html"
RUTA_DATA_JSON = RAIZ / "data" / "analisis-financiero.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"

URL_PLANILLA_PENDIENTE = (
    "https://quempinspa2020.sharepoint.com/:x:/g/"
    "IQB005ljfV3VQp6CNg8pSS0tAdjFPmF8jOcQOeU3y0vIaIE?e=kaFVjO"
)

MARGEN_OBJETIVO_NOTA = af.MARGEN_OBJETIVO_NOTA
PESO_RENTABILIDAD_NOTA = af.PESO_RENTABILIDAD_NOTA
PESO_DESVIACION_NOTA = af.PESO_DESVIACION_NOTA

COLUMNAS_MANUALES_COMPLETITUD = (
    "monto_venta", "materiales_proy", "equipos_proy", "mo_proy", "otros_proy", "mo_real",
)


def _valor_columna(ws, fila, nombre_columna):
    col = af.HEADERS_PROYECTOS.index(nombre_columna) + 1
    return ws.cell(row=fila, column=col).value


def leer_proyectos(ws_proyectos) -> list[dict]:
    """Lee todas las filas validas (TAG y Nombre no vacios) de 'Proyectos'
    con sus columnas manuales crudas -- solo lectura, nunca toca el Excel."""
    proyectos = []
    for fila in range(2, ws_proyectos.max_row + 1):
        tag = _valor_columna(ws_proyectos, fila, "TAG proyecto")
        nombre = _valor_columna(ws_proyectos, fila, "Nombre del proyecto")
        if not tag or not nombre:
            continue
        proyectos.append({
            "fila": fila,
            "tag": tag,
            "nombre": nombre,
            "cliente": _valor_columna(ws_proyectos, fila, "Cliente"),
            "estado": _valor_columna(ws_proyectos, fila, "Estado"),
            "fecha_inicio": _valor_columna(ws_proyectos, fila, "Fecha de inicio"),
            "monto_venta": _valor_columna(ws_proyectos, fila, "Monto de Venta (sin IVA)"),
            "materiales_proy": _valor_columna(ws_proyectos, fila, "Costos Materiales Proyectados"),
            "equipos_proy": _valor_columna(ws_proyectos, fila, "Costos Equipos Proyectados"),
            "mo_proy": _valor_columna(ws_proyectos, fila, "Mano de Obra Proyectada"),
            "otros_proy": _valor_columna(ws_proyectos, fila, "Otros Costos Proyectados"),
            "mo_real": _valor_columna(ws_proyectos, fila, "Mano de Obra Real"),
        })
    return proyectos


def es_proyecto_completo(p: dict) -> bool:
    """Completo = las 6 columnas de carga manual que alimentan Total Real/
    Margen/Nota tienen un valor no vacio -- 0 SI cuenta como cargado (un
    costo real en cero es un dato, no un vacio todavia sin ingresar)."""
    return all(p[campo] is not None for campo in COLUMNAS_MANUALES_COMPLETITUD)


def sumar_costos_reales_por_bucket(ws_detalle, tag: str) -> dict:
    """Recomputa las 3 sumas que en 'Proyectos' son SUMIFS hacia 'Detalle
    Costos Reales' -- lee esa hoja directo (100% valores) en vez de confiar
    en el cache de la formula."""
    sumas = {"Materiales": 0.0, "Equipos": 0.0, "Otros": 0.0}
    for fila in range(2, ws_detalle.max_row + 1):
        fila_tag = ws_detalle.cell(row=fila, column=1).value
        bucket = ws_detalle.cell(row=fila, column=3).value
        total = ws_detalle.cell(row=fila, column=4).value
        if fila_tag == tag and bucket in sumas and total is not None:
            sumas[bucket] += total
    return sumas


def calcular_kpis_proyecto(p: dict, costos_reales: dict) -> dict:
    """Recomputa, en Python, las mismas formulas que asegurar_formulas_
    proyectos/_formula_nota/_formula_evaluacion escriben en el Excel."""
    total_proyectado = p["materiales_proy"] + p["equipos_proy"] + p["mo_proy"] + p["otros_proy"]
    total_real = costos_reales["Materiales"] + costos_reales["Equipos"] + costos_reales["Otros"] + p["mo_real"]
    margen_real = p["monto_venta"] - total_real
    desviacion_pct = (total_real / total_proyectado - 1) if total_proyectado else 0.0

    score_margen = min(100, max(0, (margen_real / p["monto_venta"]) / MARGEN_OBJETIVO_NOTA * 100))
    score_desviacion = min(100, max(0, 100 - abs(desviacion_pct) * 100))
    nota = round(PESO_RENTABILIDAD_NOTA * score_margen + PESO_DESVIACION_NOTA * score_desviacion)
    if nota >= 85:
        evaluacion = "Excelente"
    elif nota >= 70:
        evaluacion = "Bueno"
    elif nota >= 55:
        evaluacion = "Aprobado"
    else:
        evaluacion = "Requiere atención"

    return {
        "tag": p["tag"], "nombre": p["nombre"], "cliente": p["cliente"], "estado": p["estado"],
        "monto_venta": p["monto_venta"], "total_proyectado": total_proyectado,
        "total_real": total_real, "margen_real": margen_real, "desviacion_pct": desviacion_pct,
        "nota": nota, "evaluacion": evaluacion,
    }
```

- [ ] **Step 5: Correr los tests para verificar que pasan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -v`
Expected: 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/build_visualizador.py" "Sistema Analisis Financiero/Visualizador Web/tests/"
git commit -m "feat(visualizador-af): completitud de proyecto y recomputo de KPIs en Python

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Recomputo de Clientes/CLTV (solo con proyectos completos)

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py`
- Modify: `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Consumes: `calcular_kpis_proyecto` (Task 1) — cada elemento de `kpis_proyectos_completos` trae `tag, cliente, monto_venta, margen_real`; `proyectos_por_tag[tag]["fecha_inicio"]` (de `leer_proyectos`, Task 1).
- Produces: `percentil_inclusivo(valores: list[float], p: float) -> float`, `calcular_clientes(kpis_proyectos_completos: list[dict], proyectos_por_tag: dict) -> list[dict]` (claves: `cliente, aov, vida, meses_activo, frecuencia, margen_pct, cltv, clasificacion`) — usado por Task 3.

- [ ] **Step 1: Agregar los tests que fallan**

```python
# agregar al final de tests/test_build_visualizador.py
from datetime import datetime, timedelta


def test_percentil_inclusivo_replica_percentile_excel():
    valores = [10, 20, 30, 40, 50]
    # PERCENTILE.INC(rango, 0.5) con 5 valores = el del medio (30).
    assert bv.percentil_inclusivo(valores, 0.5) == 30
    # PERCENTILE.INC(rango, 0) = minimo, PERCENTILE.INC(rango, 1) = maximo.
    assert bv.percentil_inclusivo(valores, 0) == 10
    assert bv.percentil_inclusivo(valores, 1) == 50


def test_percentil_inclusivo_con_un_solo_valor_devuelve_ese_valor():
    assert bv.percentil_inclusivo([42], 0.67) == 42


def test_calcular_clientes_agrupa_y_calcula_cltv():
    # 180 dias exactos entre las 2 fechas -- evita aritmetica de calendario
    # ambigua (dias/mes no calzan limpio con /30) en la asercion.
    fecha_a = datetime(2026, 1, 1)
    fecha_b = fecha_a + timedelta(days=180)
    kpis = [
        {"tag": "AGCI1", "cliente": "AGCID", "monto_venta": 1_000_000, "margen_real": 250_000},
        {"tag": "AGCI2", "cliente": "AGCID", "monto_venta": 2_000_000, "margen_real": 500_000},
    ]
    proyectos_por_tag = {
        "AGCI1": {"fecha_inicio": fecha_a},
        "AGCI2": {"fecha_inicio": fecha_b},
    }

    clientes = bv.calcular_clientes(kpis, proyectos_por_tag)

    assert len(clientes) == 1
    c = clientes[0]
    assert c["cliente"] == "AGCID"
    assert c["aov"] == 1_500_000
    assert c["vida"] == 2
    assert c["meses_activo"] == 6.0  # 180 dias / 30
    assert c["frecuencia"] == 4.0  # 2 / (6.0 / 12)
    assert c["margen_pct"] == 0.25  # (250000+500000)/(1000000+2000000)
    assert c["cltv"] == 3_000_000.0  # 1500000 * 4.0 * 2 * 0.25


def test_calcular_clientes_un_solo_proyecto_meses_activo_minimo_1():
    kpis = [{"tag": "UMAG", "cliente": "UMAG", "monto_venta": 1_000_000, "margen_real": 200_000}]
    proyectos_por_tag = {"UMAG": {"fecha_inicio": datetime(2026, 3, 1)}}

    clientes = bv.calcular_clientes(kpis, proyectos_por_tag)

    assert clientes[0]["meses_activo"] == 1.0


def test_calcular_clientes_ignora_proyectos_sin_cliente_asignado():
    kpis = [{"tag": "X", "cliente": None, "monto_venta": 1_000_000, "margen_real": 200_000}]
    proyectos_por_tag = {"X": {"fecha_inicio": datetime(2026, 1, 1)}}

    assert bv.calcular_clientes(kpis, proyectos_por_tag) == []


def test_calcular_clientes_clasificacion_por_percentil_de_cltv():
    # 3 clientes con CLTV muy distinto -- el de mayor CLTV debe caer en
    # "Clientes estrategicos" (>=p67), el de menor en "Clientes de
    # oportunidad" (<p33).
    kpis = [
        {"tag": "A", "cliente": "Bajo", "monto_venta": 100_000, "margen_real": 10_000},
        {"tag": "B", "cliente": "Medio", "monto_venta": 1_000_000, "margen_real": 200_000},
        {"tag": "C", "cliente": "Alto", "monto_venta": 10_000_000, "margen_real": 3_000_000},
    ]
    proyectos_por_tag = {
        "A": {"fecha_inicio": datetime(2026, 1, 1)},
        "B": {"fecha_inicio": datetime(2026, 1, 1)},
        "C": {"fecha_inicio": datetime(2026, 1, 1)},
    }

    clientes = {c["cliente"]: c for c in bv.calcular_clientes(kpis, proyectos_por_tag)}

    assert clientes["Alto"]["clasificacion"] == "Clientes estratégicos"
    assert clientes["Bajo"]["clasificacion"] == "Clientes de oportunidad"
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -k calcular_clientes -v`
Expected: FAIL — `AttributeError: module 'build_visualizador' has no attribute 'percentil_inclusivo'`

- [ ] **Step 3: Agregar la implementación a `build_visualizador.py`**

```python
def percentil_inclusivo(valores: list[float], p: float) -> float:
    """Replica PERCENTILE (legacy/inclusive) de Excel: interpolacion lineal
    sobre la lista ordenada, rango 0-indexado = p*(n-1). Con un solo valor,
    Excel tambien devuelve ese unico valor."""
    ordenados = sorted(valores)
    n = len(ordenados)
    if n == 1:
        return ordenados[0]
    idx = p * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return ordenados[lo] + (ordenados[hi] - ordenados[lo]) * frac


def calcular_clientes(kpis_proyectos_completos: list[dict], proyectos_por_tag: dict) -> list[dict]:
    """Agrupa kpis_proyectos_completos por 'cliente' y recomputa AOV/Vida/
    Meses activo/Frecuencia/Margen%/CLTV -- mismas formulas que
    asegurar_hoja_clientes en analisis_financiero.py, pero usando SOLO
    proyectos completos (spec §3: un proyecto incompleto de un cliente no
    contamina su CLTV, como si todavia no existiera)."""
    por_cliente: dict[str, list[dict]] = {}
    for kpi in kpis_proyectos_completos:
        cliente = kpi["cliente"]
        if not cliente:
            continue
        por_cliente.setdefault(cliente, []).append(kpi)

    filas = []
    for cliente, kpis in por_cliente.items():
        n = len(kpis)
        aov = sum(k["monto_venta"] for k in kpis) / n
        vida = n
        fechas = [proyectos_por_tag[k["tag"]]["fecha_inicio"] for k in kpis]
        fechas = [f for f in fechas if f is not None]
        if len(fechas) >= 2:
            meses_activo = max(1.0, (max(fechas) - min(fechas)).days / 30)
        else:
            meses_activo = 1.0
        frecuencia = vida / (meses_activo / 12)
        suma_venta = sum(k["monto_venta"] for k in kpis)
        suma_margen = sum(k["margen_real"] for k in kpis)
        margen_pct = suma_margen / suma_venta if suma_venta else 0.0
        cltv = aov * frecuencia * vida * margen_pct
        filas.append({
            "cliente": cliente, "aov": aov, "vida": vida, "meses_activo": meses_activo,
            "frecuencia": frecuencia, "margen_pct": margen_pct, "cltv": cltv,
        })

    cltvs = [f["cltv"] for f in filas]
    for f in filas:
        p67 = percentil_inclusivo(cltvs, 0.67)
        p33 = percentil_inclusivo(cltvs, 0.33)
        if f["cltv"] >= p67:
            f["clasificacion"] = "Clientes estratégicos"
        elif f["cltv"] >= p33:
            f["clasificacion"] = "Clientes potenciales"
        else:
            f["clasificacion"] = "Clientes de oportunidad"

    return filas
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -v`
Expected: 13 tests PASS (7 de Task 1 + 6 nuevos)

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/build_visualizador.py" "Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py"
git commit -m "feat(visualizador-af): recomputo de CLTV/clasificacion excluyendo proyectos incompletos

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Export saneado completo (`extraer_datos_saneados`)

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py`
- Modify: `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Consumes: `leer_proyectos`, `es_proyecto_completo`, `sumar_costos_reales_por_bucket`, `calcular_kpis_proyecto` (Task 1); `calcular_clientes` (Task 2); `af.HOJA_PROYECTOS`, `af.HOJA_DETALLE_COSTOS_REALES`.
- Produces: `extraer_datos_saneados(ruta_excel) -> dict` con claves `generado, kpis_proyectos {n_completos, margen_real_total, nota_promedio, n_requiere_atencion}, proyectos (list), clientes (list, con proyectos_pendientes agregado), pendientes (list, con mensaje/link)` — usado por Task 8 (`build()`).

- [ ] **Step 1: Escribir el test que falla**

```python
# agregar a tests/test_build_visualizador.py
def _wb_con_proyectos(tmp_path, filas):
    """filas: list[dict] con al menos tag/nombre/cliente + las columnas
    manuales de _fila_proyecto_completa (usar overrides para omitir alguna
    y simular un proyecto incompleto)."""
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)
    ws = wb[af.HOJA_PROYECTOS]
    for i, fila in enumerate(filas, start=2):
        _fila_proyecto_completa(ws, i, **fila)
    wb.save(ruta)
    return ruta


def test_extraer_datos_saneados_separa_completos_e_incompletos(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
        {
            "TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache", "Cliente": "Cesfam",
            "Monto de Venta (sin IVA)": None,
        },
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert len(data["proyectos"]) == 1
    assert data["proyectos"][0]["tag"] == "UMAG"
    assert len(data["pendientes"]) == 1
    pendiente = data["pendientes"][0]
    assert pendiente["nombre"] == "Cesfam Limache"
    assert pendiente["mensaje"] == "Cesfam Limache — Falta ingresar información en 'Análisis de Proyectos'"
    assert pendiente["link"] == bv.URL_PLANILLA_PENDIENTE


def test_extraer_datos_saneados_kpis_proyectos_resumen(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert data["kpis_proyectos"]["n_completos"] == 1
    assert data["kpis_proyectos"]["margen_real_total"] == data["proyectos"][0]["margen_real"]
    assert data["kpis_proyectos"]["nota_promedio"] == data["proyectos"][0]["nota"]
    assert data["kpis_proyectos"]["n_requiere_atencion"] == 0


def test_extraer_datos_saneados_cliente_con_proyecto_pendiente_muestra_nota(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "AGCI1", "Nombre del proyecto": "AGCID Febrero", "Cliente": "AGCID"},
        {
            "TAG proyecto": "AGCI2", "Nombre del proyecto": "AGCID Agosto", "Cliente": "AGCID",
            "Monto de Venta (sin IVA)": None,
        },
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert len(data["clientes"]) == 1
    assert data["clientes"][0]["cliente"] == "AGCID"
    assert data["clientes"][0]["proyectos_pendientes"] == 1


def test_extraer_datos_saneados_cliente_100pct_incompleto_no_aparece(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {
            "TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache", "Cliente": "Cesfam",
            "Monto de Venta (sin IVA)": None,
        },
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert data["clientes"] == []
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -k extraer_datos_saneados -v`
Expected: FAIL — `AttributeError: module 'build_visualizador' has no attribute 'extraer_datos_saneados'`

- [ ] **Step 3: Agregar `extraer_datos_saneados` a `build_visualizador.py`**

```python
from datetime import datetime


def extraer_datos_saneados(ruta_excel=RUTA_EXCEL) -> dict:
    """Arma el snapshot saneado completo: proyectos completos + sus KPIs,
    clientes + su CLTV (excluyendo incompletos), y la lista de proyectos
    pendientes de completar con el mensaje y link fijos (spec §1/§3).
    `ruta_excel` es parametrizable para testear contra un workbook temporal,
    nunca el Excel real de la empresa."""
    wb = openpyxl.load_workbook(str(ruta_excel), data_only=True)
    ws_proyectos = wb[af.HOJA_PROYECTOS]
    ws_detalle = wb[af.HOJA_DETALLE_COSTOS_REALES]

    proyectos = leer_proyectos(ws_proyectos)
    proyectos_por_tag = {p["tag"]: p for p in proyectos}

    completos = []
    pendientes = []
    for p in proyectos:
        if es_proyecto_completo(p):
            costos_reales = sumar_costos_reales_por_bucket(ws_detalle, p["tag"])
            completos.append(calcular_kpis_proyecto(p, costos_reales))
        else:
            pendientes.append({
                "tag": p["tag"],
                "nombre": p["nombre"],
                "mensaje": f"{p['nombre']} — Falta ingresar información en 'Análisis de Proyectos'",
                "link": URL_PLANILLA_PENDIENTE,
            })

    clientes = calcular_clientes(completos, proyectos_por_tag)

    pendientes_por_cliente: dict[str, int] = {}
    for p in proyectos:
        if not es_proyecto_completo(p) and p["cliente"]:
            pendientes_por_cliente[p["cliente"]] = pendientes_por_cliente.get(p["cliente"], 0) + 1
    for c in clientes:
        c["proyectos_pendientes"] = pendientes_por_cliente.get(c["cliente"], 0)

    n_completos = len(completos)
    return {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "kpis_proyectos": {
            "n_completos": n_completos,
            "margen_real_total": sum(k["margen_real"] for k in completos),
            "nota_promedio": (sum(k["nota"] for k in completos) / n_completos) if n_completos else 0,
            "n_requiere_atencion": sum(1 for k in completos if k["evaluacion"] == "Requiere atención"),
        },
        "proyectos": completos,
        "clientes": clientes,
        "pendientes": pendientes,
    }
```

Agregar también `import openpyxl` y `import json`, `import base64`, `import io`, `import sys` al principio del archivo si no están ya (se usarán en Task 8) — por ahora solo `openpyxl` y `datetime` son necesarios para que este test pase.

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -v`
Expected: 17 tests PASS

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/build_visualizador.py" "Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py"
git commit -m "feat(visualizador-af): ensamblar el snapshot saneado completo con pendientes

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Esqueleto de `template.html` (gate/marca reutilizados + estructura nueva)

**Files:**
- Create: `Sistema Analisis Financiero/Visualizador Web/template.html`

**Interfaces:**
- Produces: el archivo `template.html` que Task 8 (`build()`) incrusta datos en el placeholder `__AF_DATA_B64__`, y que Tasks 5-7 completan con el contenido de `initApp(DATA)`.

- [ ] **Step 1: Copiar el archivo completo de Centro de Costos como base**

Preserva byte a byte la tipografía Lato embebida (base64), las 4 variables de color de marca, el mecanismo de gate de contraseña, el toggle de tema claro/oscuro, el tooltip, y la paginación — no se re-derivan ni se retipean.

Run:
```bash
cp "Centro de Costos/Visualizador Web/template.html" "Sistema Analisis Financiero/Visualizador Web/template.html"
```

- [ ] **Step 2: Renombrar el placeholder de datos** (Centro de Costos usa `__CC_DATA_B64__`/`cc-data-b64`; este módulo usa `__AF_DATA_B64__`/`af-data-b64` para no confundirlos si algún día conviven abiertos a la vez)

Run (PowerShell, ya que el repo corre en Windows):
```powershell
(Get-Content "Sistema Analisis Financiero/Visualizador Web/template.html" -Raw) `
  -replace '__CC_DATA_B64__', '__AF_DATA_B64__' `
  -replace 'cc-data-b64', 'af-data-b64' `
  -replace "cc_viz_unlocked", "af_viz_unlocked" `
  -replace "cc_viz_theme", "af_viz_theme" `
  | Set-Content "Sistema Analisis Financiero/Visualizador Web/template.html" -Encoding utf8
```

- [ ] **Step 3: Verificar el renombrado**

Run: `grep -c "__AF_DATA_B64__\|af-data-b64" "Sistema Analisis Financiero/Visualizador Web/template.html"`
Expected: al menos `2` (el placeholder del `<script>` y su lectura en `unlock()`)

Run: `grep -c "__CC_DATA_B64__\|cc-data-b64" "Sistema Analisis Financiero/Visualizador Web/template.html"`
Expected: `0`

- [ ] **Step 4: Actualizar el `<title>` y el texto del gate**

Abrir el archivo y buscar la etiqueta `<title>` y el párrafo `<p class="hint">Acceso restringido...` dentro de `viz-gate-card` — reemplazar cualquier mención a "Centro de Costos" por "Análisis Financiero". Si no hay ninguna mención literal al nombre del módulo en esas dos líneas, dejarlas tal cual (son genéricas).

- [ ] **Step 5: Reemplazar el cuerpo de `initApp(DATA)` por un esqueleto vacío**

Localizar `function initApp(DATA) {` y su llave de cierre correspondiente (es la última función del `<script>`, justo antes del cierre de la IIFE principal). Reemplazar **todo su contenido** (desde `var DOCS = DATA.documentos;` hasta el final del cuerpo) por:

```javascript
function initApp(DATA) {
  var root = document.getElementById('vizRoot');
  var tooltip = document.getElementById('vizTooltip');
  var PROYECTOS = DATA.proyectos;
  var CLIENTES = DATA.clientes;
  var PENDIENTES = DATA.pendientes;
  var KPIS = DATA.kpis_proyectos;

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(null, args); }, ms);
    };
  }
  function formatoCLP(n) { return '$' + Math.round(n).toLocaleString('es-CL'); }
  function formatoPct(n) { return (n * 100).toFixed(1) + '%'; }

  // Tasks 5-7 agregan aquí: tooltips + tabs + banner de pendientes,
  // pestaña Proyectos, pestaña Clientes.
}
```

Elimina también cualquier función que quedó huérfana y solo era usada por el cuerpo anterior de `initApp` y no por el resto del archivo (usar el Step 6 para confirmar cuáles siguen en uso). Mantener sin tocar todo lo que está **fuera** de `initApp` (gate, tema, fuentes, CSS raíz).

- [ ] **Step 6: Verificar qué utilidades genéricas sobreviven fuera de `initApp`**

Run: `grep -n "function normalizePassword\|function b64ToUtf8\|GATE_PASSWORD_NORM\|function unlock\|vizRootEl" "Sistema Analisis Financiero/Visualizador Web/template.html"`
Expected: todas presentes, sin cambios (viven antes de `initApp`, no se tocaron).

- [ ] **Step 7: Reemplazar el `<body>` — quitar el markup específico de Centro de Costos (filtros, tabla de documentos, botón de copiar archivo) y dejar el esqueleto nuevo**

Dentro de `<div class="viz-root" id="vizRoot" style="display:none">` (después del header/logo, que se mantiene tal cual), reemplazar todo el contenido específico de Centro de Costos (KPIs, selects de filtro `fProyecto`/`fTipoProyecto`/`fCategoria`/`fEstado`/`fDesde`/`fHasta`, tabla de documentos, paginación) por:

```html
<div class="pendientes-banner" id="pendientesBanner" style="display:none">
  <div class="pendientes-header">
    <strong><span id="pendientesCount"></span> proyecto(s) pendiente(s) de completar en Análisis de Proyectos</strong>
    <button id="pendientesToggle" class="pendientes-toggle-btn" type="button">Ver detalle</button>
  </div>
  <ul id="pendientesList" class="pendientes-list" style="display:none"></ul>
</div>

<nav class="viz-tabs">
  <button class="viz-tab-btn active" data-tab="tabProyectos" type="button">Proyectos</button>
  <button class="viz-tab-btn" data-tab="tabClientes" type="button">Clientes</button>
</nav>

<section id="tabProyectos" class="viz-tab-panel active">
  <div class="kpi-row">
    <div class="kpi-card">
      <div class="kpi-label">Proyectos completos</div>
      <div class="kpi-value" id="kpiNCompletos"></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Margen Real total</div>
      <div class="kpi-value" id="kpiMargenTotal"></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">
        Nota promedio
        <span class="info-icon" tabindex="0" data-info="Resume rentabilidad y control de presupuesto en un solo número comparable entre proyectos, para priorizar dónde poner atención de gestión.">i</span>
      </div>
      <div class="kpi-value" id="kpiNotaPromedio"></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Requiere atención</div>
      <div class="kpi-value" id="kpiRequiereAtencion"></div>
    </div>
  </div>
  <div class="chart-row">
    <div class="chart-card"><h3>Nota del Proyecto</h3><div id="chartNotaProyectos"></div></div>
    <div class="chart-card"><h3>Distribución de Evaluación</h3><div id="chartEvaluacion"></div></div>
  </div>
  <input type="text" id="buscarProyectos" class="viz-search" placeholder="Buscar proyecto o cliente…">
  <table class="viz-table">
    <thead>
      <tr><th>Proyecto</th><th>Cliente</th><th>Estado</th><th>Monto Venta</th><th>Margen Real</th><th>Desviación %</th><th>Nota</th><th>Evaluación</th></tr>
    </thead>
    <tbody id="tablaProyectosBody"></tbody>
  </table>
</section>

<section id="tabClientes" class="viz-tab-panel">
  <div class="kpi-row">
    <div class="kpi-card">
      <div class="kpi-label">Top cliente por CLTV</div>
      <div class="kpi-value" id="kpiTopCliente"></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">
        CLTV promedio
        <span class="info-icon" tabindex="0" data-info="Estima el valor total que el cliente representa para QUEMPIN a lo largo de su relación completa — la métrica central para decidir dónde invertir esfuerzo comercial.">i</span>
      </div>
      <div class="kpi-value" id="kpiCltvPromedio"></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Clasificación</div>
      <div class="kpi-value" id="kpiClasificaciones"></div>
    </div>
  </div>
  <div class="chart-row">
    <div class="chart-card"><h3>Top 8 clientes por CLTV</h3><div id="chartTopClientes"></div></div>
    <div class="chart-card"><h3>Distribución de Clasificación</h3><div id="chartClasificacion"></div></div>
  </div>
  <input type="text" id="buscarClientes" class="viz-search" placeholder="Buscar cliente…">
  <table class="viz-table">
    <thead>
      <tr><th>Cliente</th><th>AOV</th><th>Vida</th><th>Meses activo</th><th>Frecuencia</th><th>Margen %</th><th>CLTV</th><th>Clasificación</th></tr>
    </thead>
    <tbody id="tablaClientesBody"></tbody>
  </table>
</section>
```

Mantener sin tocar el `<footer class="viz-footer">` (disclaimer de contraseña) y el `<div class="viz-tooltip" id="vizTooltip">` que están fuera de `vizRoot` — ver el archivo copiado.

- [ ] **Step 8: Agregar CSS nuevo** (buscar el bloque `<style>` y agregar al final, antes del cierre `</style>`; revisar primero el `:root` del archivo copiado para confirmar los nombres exactos de `--brand-orange`, `--brand-gray-11`, `--brand-gray-7`, `--brand-black`, `--surface-1`, `--surface-card`, `--gridline` — son los únicos nombres de variable que este bloque asume, ya confirmados en Centro de Costos):

```css
.viz-tabs { display: flex; gap: 8px; margin: 20px 0 16px; border-bottom: 1px solid var(--gridline); }
.viz-tab-btn {
  background: none; border: none; padding: 10px 16px; font: inherit; cursor: pointer;
  color: var(--brand-gray-11); border-bottom: 2px solid transparent;
}
.viz-tab-btn.active { color: var(--brand-orange); border-bottom-color: var(--brand-orange); font-weight: 700; }
.viz-tab-panel { display: none; }
.viz-tab-panel.active { display: block; }

.pendientes-banner {
  background: var(--surface-card); border: 1px solid var(--brand-orange); border-radius: 8px;
  padding: 12px 16px; margin-bottom: 16px;
}
.pendientes-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.pendientes-toggle-btn {
  background: var(--brand-orange); color: #fff; border: none; border-radius: 6px;
  padding: 6px 12px; font-size: 12px; cursor: pointer;
}
.pendientes-list { margin: 10px 0 0; padding-left: 20px; }
.pendientes-list a { color: var(--brand-orange); }

.kpi-row { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 18px; }
.kpi-card { background: var(--surface-card); border-radius: 8px; padding: 14px 18px; min-width: 160px; flex: 1; }
.kpi-label { font-size: 12px; color: var(--brand-gray-11); display: flex; align-items: center; gap: 5px; }
.kpi-value { font-size: 24px; font-weight: 700; margin-top: 4px; }

.chart-row { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 18px; }
.chart-card { background: var(--surface-card); border-radius: 8px; padding: 14px 18px; flex: 1; min-width: 260px; }
.chart-card h3 { font-size: 13px; margin: 0 0 10px; color: var(--brand-gray-11); }

.bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 12px; }
.bar-label { width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { flex: 1; background: var(--surface-1); border-radius: 4px; height: 14px; overflow: hidden; }
.bar-fill { background: var(--brand-orange); height: 100%; }
.bar-value { width: 70px; text-align: right; }

.donut-wrap { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.donut-legend-row { display: flex; align-items: center; gap: 6px; font-size: 12px; margin-bottom: 4px; }
.donut-swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }

.fila-nota { font-size: 11px; color: var(--brand-gray-11); font-style: italic; }
```

- [ ] **Step 9: Verificar que el archivo sigue siendo HTML válido y que los anclajes clave existen**

Run: `grep -c "id=\"tabProyectos\"\|id=\"tabClientes\"\|id=\"pendientesBanner\"\|id=\"vizRoot\"\|id=\"pwForm\"" "Sistema Analisis Financiero/Visualizador Web/template.html"`
Expected: `5`

- [ ] **Step 10: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/template.html"
git commit -m "feat(visualizador-af): esqueleto de template.html con gate/marca reutilizados

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Tooltips + tabs + banner de pendientes (JS)

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `PENDIENTES` (array, cada uno con `mensaje`/`link`), elementos `#pendientesBanner`/`#pendientesCount`/`#pendientesList`/`#pendientesToggle`, `.viz-tab-btn`/`.viz-tab-panel`, `.info-icon[data-info]`, `#vizTooltip` — todos definidos en Task 4.
- Produces: nada que otro task consuma directamente (es UI terminal), pero deja `tooltip`/`root` disponibles en el scope de `initApp` para Tasks 6-7.

- [ ] **Step 1: Agregar el contenido dentro de `initApp(DATA)`**, justo después de las declaraciones de `formatoCLP`/`formatoPct` del esqueleto de Task 4:

```javascript
  // ---------- tooltip ----------
  function showTooltip(el, text) {
    tooltip.textContent = text;
    tooltip.classList.add('show', 'info-mode');
    var r = el.getBoundingClientRect();
    tooltip.style.left = (r.left + r.width / 2) + 'px';
    tooltip.style.top = (r.top - 8 + window.scrollY) + 'px';
  }
  function hideTooltip() { tooltip.classList.remove('show'); }
  document.querySelectorAll('.info-icon').forEach(function (el) {
    el.addEventListener('mouseenter', function () { showTooltip(el, el.getAttribute('data-info')); });
    el.addEventListener('mouseleave', hideTooltip);
    el.addEventListener('click', function () {
      if (tooltip.classList.contains('show')) hideTooltip(); else showTooltip(el, el.getAttribute('data-info'));
    });
  });

  // ---------- tabs ----------
  var tabButtons = document.querySelectorAll('.viz-tab-btn');
  var tabPanels = document.querySelectorAll('.viz-tab-panel');
  tabButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      tabButtons.forEach(function (b) { b.classList.remove('active'); });
      tabPanels.forEach(function (p) { p.classList.remove('active'); });
      btn.classList.add('active');
      document.getElementById(btn.getAttribute('data-tab')).classList.add('active');
    });
  });

  // ---------- banner de pendientes ----------
  (function renderPendientes() {
    var banner = document.getElementById('pendientesBanner');
    var count = document.getElementById('pendientesCount');
    var list = document.getElementById('pendientesList');
    if (!PENDIENTES.length) { banner.style.display = 'none'; return; }
    banner.style.display = '';
    count.textContent = PENDIENTES.length;
    list.innerHTML = PENDIENTES.map(function (p) {
      return '<li>' + p.mensaje + ' — <a href="' + p.link + '" target="_blank" rel="noopener">Abrir Análisis de Proyectos</a></li>';
    }).join('');
  })();
  document.getElementById('pendientesToggle').addEventListener('click', function () {
    var list = document.getElementById('pendientesList');
    var open = list.style.display !== 'none';
    list.style.display = open ? 'none' : '';
    this.textContent = open ? 'Ver detalle' : 'Ocultar detalle';
  });
```

- [ ] **Step 2: Verificación manual en navegador**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m http.server 8000` y abrir `http://localhost:8000/template.html` — reemplazar temporalmente `__AF_DATA_B64__` por un JSON de prueba en base64 para poder pasar el gate (usar `python -c "import base64,json; print(base64.b64encode(json.dumps({'proyectos':[],'clientes':[],'pendientes':[{'mensaje':'Prueba','link':'https://example.com'}],'kpis_proyectos':{'n_completos':0,'margen_real_total':0,'nota_promedio':0,'n_requiere_atencion':0}}).encode()).decode())"`).
Expected: tras ingresar la contraseña, se ve el banner naranjo con "1 proyecto(s) pendiente(s)...", el botón "Ver detalle" muestra/oculta la lista con el link, y las pestañas Proyectos/Clientes cambian de panel al hacer clic. Revertir el reemplazo temporal del placeholder antes de continuar (no commitear datos de prueba incrustados).

- [ ] **Step 3: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/template.html"
git commit -m "feat(visualizador-af): tooltips, tabs y banner de proyectos pendientes

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: Pestaña "Proyectos" (KPIs + gráficos + tabla)

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `PROYECTOS`, `KPIS` (de `DATA`, Task 4); `formatoCLP`/`formatoPct`/`debounce` (Task 4); elementos `#kpiNCompletos`/`#kpiMargenTotal`/`#kpiNotaPromedio`/`#kpiRequiereAtencion`/`#chartNotaProyectos`/`#chartEvaluacion`/`#buscarProyectos`/`#tablaProyectosBody` (Task 4).
- Produces: `renderBarChart(containerId, items, labelKey, valueKey)` y `renderDonutChart(containerId, items, labelKey, valueKey)` — reutilizadas por Task 7 para la pestaña Clientes.

- [ ] **Step 1: Agregar el contenido dentro de `initApp(DATA)`**, después del bloque de Task 5:

```javascript
  // ---------- gráficos SVG genéricos (barras + donut) ----------
  function renderBarChart(containerId, items, labelKey, valueKey) {
    var el = document.getElementById(containerId);
    var max = Math.max.apply(null, items.map(function (i) { return i[valueKey]; }).concat([1]));
    var rows = items.map(function (i) {
      var pct = Math.max(0, i[valueKey]) / max * 100;
      return '<div class="bar-row">' +
        '<div class="bar-label" title="' + i[labelKey] + '">' + i[labelKey] + '</div>' +
        '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>' +
        '<div class="bar-value">' + i.valueLabel + '</div>' +
        '</div>';
    }).join('');
    el.innerHTML = rows || '<p>Sin datos.</p>';
  }

  function renderDonutChart(containerId, items, labelKey, valueKey) {
    var el = document.getElementById(containerId);
    var total = items.reduce(function (s, i) { return s + i[valueKey]; }, 0);
    var size = 160, r = 60, cx = size / 2, cy = size / 2, circ = 2 * Math.PI * r;
    var offset = 0;
    var colors = ['var(--brand-orange)', 'var(--brand-gray-11)', 'var(--brand-gray-7)', 'var(--brand-black)'];
    var segs = items.map(function (i, idx) {
      var frac = total ? i[valueKey] / total : 0;
      var dash = frac * circ;
      var seg = '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' +
        colors[idx % colors.length] + '" stroke-width="24" stroke-dasharray="' + dash + ' ' + (circ - dash) +
        '" stroke-dashoffset="' + (-offset) + '"/>';
      offset += dash;
      return seg;
    }).join('');
    var legend = items.map(function (i, idx) {
      return '<div class="donut-legend-row"><span class="donut-swatch" style="background:' +
        colors[idx % colors.length] + '"></span>' + i[labelKey] + ' (' + i[valueKey] + ')</div>';
    }).join('');
    el.innerHTML = '<div class="donut-wrap"><svg viewBox="0 0 ' + size + ' ' + size +
      '" width="160" height="160">' + segs + '</svg><div class="donut-legend">' + legend + '</div></div>';
  }

  // ---------- pestaña Proyectos ----------
  document.getElementById('kpiNCompletos').textContent = KPIS.n_completos;
  document.getElementById('kpiMargenTotal').textContent = formatoCLP(KPIS.margen_real_total);
  document.getElementById('kpiNotaPromedio').textContent = Math.round(KPIS.nota_promedio);
  document.getElementById('kpiRequiereAtencion').textContent = KPIS.n_requiere_atencion;

  var proyectosOrdenados = PROYECTOS.slice().sort(function (a, b) { return b.nota - a.nota; });
  renderBarChart('chartNotaProyectos', proyectosOrdenados.map(function (p) {
    return { nombre: p.nombre, nota: p.nota, valueLabel: p.nota };
  }), 'nombre', 'nota');

  var porEvaluacion = {};
  PROYECTOS.forEach(function (p) { porEvaluacion[p.evaluacion] = (porEvaluacion[p.evaluacion] || 0) + 1; });
  renderDonutChart('chartEvaluacion', Object.keys(porEvaluacion).map(function (k) {
    return { evaluacion: k, n: porEvaluacion[k] };
  }), 'evaluacion', 'n');

  function renderTablaProyectos(items) {
    var tbody = document.getElementById('tablaProyectosBody');
    tbody.innerHTML = items.map(function (p) {
      return '<tr><td>' + p.nombre + '</td><td>' + (p.cliente || '—') + '</td><td>' + (p.estado || '—') +
        '</td><td>' + formatoCLP(p.monto_venta) + '</td><td>' + formatoCLP(p.margen_real) + '</td><td>' +
        formatoPct(p.desviacion_pct) + '</td><td>' + p.nota + '</td><td>' + p.evaluacion + '</td></tr>';
    }).join('');
  }
  renderTablaProyectos(proyectosOrdenados);
  document.getElementById('buscarProyectos').addEventListener('input', debounce(function (evt) {
    var q = evt.target.value.toLowerCase();
    renderTablaProyectos(proyectosOrdenados.filter(function (p) {
      return (p.nombre + ' ' + (p.cliente || '')).toLowerCase().indexOf(q) !== -1;
    }));
  }, 150));
```

- [ ] **Step 2: Verificación manual en navegador**

Repetir el procedimiento de Task 5 Step 2 pero con un JSON de prueba que incluya 2-3 proyectos completos con distintos `nota`/`evaluacion`/`margen_real`. Confirmar: las 4 tarjetas KPI muestran los números correctos, el gráfico de barras ordena de mayor a menor Nota, el donut de Evaluación muestra segmentos proporcionales, la tabla se filtra al escribir en el buscador.

- [ ] **Step 3: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/template.html"
git commit -m "feat(visualizador-af): pestaña Proyectos con KPIs, gráficos y tabla buscable

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Pestaña "Clientes" (KPIs + gráficos + tabla)

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `CLIENTES` (de `DATA`, Task 4); `renderBarChart`/`renderDonutChart`/`formatoCLP`/`formatoPct`/`debounce` (Tasks 4/6); elementos `#kpiTopCliente`/`#kpiCltvPromedio`/`#kpiClasificaciones`/`#chartTopClientes`/`#chartClasificacion`/`#buscarClientes`/`#tablaClientesBody` (Task 4).
- Produces: nada consumido por otro task (última sección de `initApp`).

- [ ] **Step 1: Agregar el contenido dentro de `initApp(DATA)`**, al final, después del bloque de Task 6:

```javascript
  // ---------- pestaña Clientes ----------
  var clientesOrdenados = CLIENTES.slice().sort(function (a, b) { return b.cltv - a.cltv; });
  document.getElementById('kpiTopCliente').textContent = clientesOrdenados.length ? clientesOrdenados[0].cliente : '—';
  document.getElementById('kpiCltvPromedio').textContent = clientesOrdenados.length
    ? formatoCLP(clientesOrdenados.reduce(function (s, c) { return s + c.cltv; }, 0) / clientesOrdenados.length)
    : formatoCLP(0);

  var porClasificacion = {};
  CLIENTES.forEach(function (c) { porClasificacion[c.clasificacion] = (porClasificacion[c.clasificacion] || 0) + 1; });
  document.getElementById('kpiClasificaciones').textContent = Object.keys(porClasificacion).map(function (k) {
    return k + ': ' + porClasificacion[k];
  }).join(' · ') || '—';

  renderBarChart('chartTopClientes', clientesOrdenados.slice(0, 8).map(function (c) {
    return { cliente: c.cliente, cltv: c.cltv, valueLabel: formatoCLP(c.cltv) };
  }), 'cliente', 'cltv');
  renderDonutChart('chartClasificacion', Object.keys(porClasificacion).map(function (k) {
    return { clasificacion: k, n: porClasificacion[k] };
  }), 'clasificacion', 'n');

  function renderTablaClientes(items) {
    var tbody = document.getElementById('tablaClientesBody');
    tbody.innerHTML = items.map(function (c) {
      var nota = c.proyectos_pendientes
        ? '<div class="fila-nota">' + c.proyectos_pendientes + ' proyecto(s) pendiente(s) de completar</div>'
        : '';
      return '<tr><td>' + c.cliente + nota + '</td><td>' + formatoCLP(c.aov) + '</td><td>' + c.vida +
        '</td><td>' + c.meses_activo.toFixed(1) + '</td><td>' + c.frecuencia.toFixed(2) + '</td><td>' +
        formatoPct(c.margen_pct) + '</td><td>' + formatoCLP(c.cltv) + '</td><td>' + c.clasificacion + '</td></tr>';
    }).join('');
  }
  renderTablaClientes(clientesOrdenados);
  document.getElementById('buscarClientes').addEventListener('input', debounce(function (evt) {
    var q = evt.target.value.toLowerCase();
    renderTablaClientes(clientesOrdenados.filter(function (c) {
      return c.cliente.toLowerCase().indexOf(q) !== -1;
    }));
  }, 150));
```

- [ ] **Step 2: Verificación manual en navegador**

Repetir el procedimiento de Task 5 Step 2 con un JSON de prueba que incluya 2-3 clientes con distinto CLTV/Clasificación y al menos uno con `proyectos_pendientes > 0`. Confirmar: las 3 tarjetas KPI, el ranking de barras de Top 8 clientes, el donut de Clasificación, la tabla con la nota en cursiva bajo el nombre del cliente que tiene pendientes, y el buscador filtrando por nombre.

- [ ] **Step 3: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/template.html"
git commit -m "feat(visualizador-af): pestaña Clientes con CLTV, clasificación y tabla buscable

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: `build()` — ensamblar snapshot + incrustar en template + smoke test

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py`
- Modify: `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Consumes: `extraer_datos_saneados` (Task 3), `RUTA_EXCEL`/`RUTA_TEMPLATE`/`RUTA_DATA_JSON`/`RUTA_BUILD_HTML` (definidas en Task 1), el placeholder `__AF_DATA_B64__` en `template.html` (Task 4).
- Produces: `build() -> int` (0 = éxito, 1 = error) — usado por Task 9 (`actualizar_visualizador()` en `analisis_financiero.py`) y por el comando `visualizador` de `driver.py`.

- [ ] **Step 1: Escribir el smoke test que falla**

```python
# agregar a tests/test_build_visualizador.py
def test_build_genera_html_no_vacio_con_snapshot_incrustado(tmp_path, monkeypatch):
    ruta_excel = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ])
    ruta_data = tmp_path / "data" / "analisis-financiero.json"
    ruta_build = tmp_path / "build" / "index.html"

    monkeypatch.setattr(bv, "RUTA_EXCEL", ruta_excel)
    monkeypatch.setattr(bv, "RUTA_DATA_JSON", ruta_data)
    monkeypatch.setattr(bv, "RUTA_BUILD_HTML", ruta_build)

    resultado = bv.build()

    assert resultado == 0
    assert ruta_data.exists()
    assert ruta_build.exists()
    contenido = ruta_build.read_text(encoding="utf-8")
    assert "__AF_DATA_B64__" not in contenido
    assert len(contenido) > 1000


def test_build_falla_si_no_existe_el_excel(tmp_path, monkeypatch):
    monkeypatch.setattr(bv, "RUTA_EXCEL", tmp_path / "no-existe.xlsx")
    assert bv.build() == 1
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -k test_build_ -v`
Expected: FAIL — `AttributeError: module 'build_visualizador' has no attribute 'build'`

- [ ] **Step 3: Agregar `build()` a `build_visualizador.py`** (agregar los imports que falten al principio del archivo: `base64, io, json, sys`)

```python
import base64
import io
import json
import sys


def build() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    if not RUTA_EXCEL.exists():
        print(f"[ERROR] No existe el Excel: {RUTA_EXCEL}")
        return 1
    if not RUTA_TEMPLATE.exists():
        print(f"[ERROR] No existe la plantilla: {RUTA_TEMPLATE}")
        return 1

    data = extraer_datos_saneados(RUTA_EXCEL)

    RUTA_DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    with io.open(RUTA_DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    data_json_text = json.dumps(data, ensure_ascii=False)
    data_b64 = base64.b64encode(data_json_text.encode("utf-8")).decode("ascii")

    with io.open(RUTA_TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read()
    if "__AF_DATA_B64__" not in template:
        print("[ERROR] template.html no tiene el placeholder __AF_DATA_B64__")
        return 1
    html = template.replace("__AF_DATA_B64__", data_b64)

    RUTA_BUILD_HTML.parent.mkdir(parents=True, exist_ok=True)
    with io.open(RUTA_BUILD_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK — {len(data['proyectos'])} proyecto(s) completo(s), "
          f"{len(data['pendientes'])} pendiente(s), {len(data['clientes'])} cliente(s)")
    print(f"Snapshot: {RUTA_DATA_JSON}")
    print(f"Visualizador: {RUTA_BUILD_HTML}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(build())
```

Nota: `extraer_datos_saneados` (Task 3) debe recibir `RUTA_EXCEL` explícito (no el default del parámetro) para que el `monkeypatch` del test funcione — confirmar que la llamada dentro de `build()` es `extraer_datos_saneados(RUTA_EXCEL)`, no `extraer_datos_saneados()`.

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/ -v`
Expected: 19 tests PASS

- [ ] **Step 5: Agregar `data/` y `build/` a `.gitignore`** (ya existe la regla genérica `*/Visualizador Web/data/` del scaffolding de 2026-07-19 — confirmar que también cubre `build/`)

Run: `grep -n "Visualizador Web" .gitignore`
Expected: si solo aparece `*/Visualizador Web/data/`, agregar una línea `*/Visualizador Web/build/` al mismo bloque.

- [ ] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/build_visualizador.py" "Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py" .gitignore
git commit -m "feat(visualizador-af): build() genera build/index.html con los datos incrustados

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 9: Encadenar al `run`, comando del skill, y documentación

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py`
- Modify: `Sistema Analisis Financiero/Sistema/tests/test_ejecutar.py`
- Modify: `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py`
- Modify: `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md`
- Create: `Sistema Analisis Financiero/Visualizador Web/CLAUDE.md`
- Create: `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/MEMORY.md`
- Modify: `CLAUDE.md` (raíz)

**Interfaces:**
- Consumes: `build_visualizador.build()` (Task 8).
- Produces: `actualizar_visualizador_af()` en `analisis_financiero.py`, comando `python driver.py visualizador`.

- [ ] **Step 1: Escribir el test que falla** (que un fallo del visualizador nunca aborta `ejecutar()`)

```python
# agregar a Sistema Analisis Financiero/Sistema/tests/test_ejecutar.py
def test_ejecutar_no_aborta_si_falla_el_visualizador(tmp_path, monkeypatch):
    import analisis_financiero as af

    def _falla():
        raise RuntimeError("boom")

    monkeypatch.setattr(af, "actualizar_visualizador_af", _falla)

    ruta_excel_af = tmp_path / "Análisis de Proyectos.xlsx"
    ruta_excel_cc = tmp_path / "Centro de Costos.xlsx"
    # reutilizar el fixture ya existente en este archivo que arma un Centro
    # de Costos.xlsx minimo -- ver la funcion _wb_centro_de_costos_minimo (o
    # equivalente) definida mas arriba en test_ejecutar.py.
    _wb_centro_de_costos_minimo(ruta_excel_cc)  # ya existe en este archivo

    resumen = af.ejecutar(
        ruta_excel_af=ruta_excel_af, ruta_excel_cc=ruta_excel_cc,
        raiz_facturas_cc=tmp_path / "facturas", raiz_respaldos=tmp_path / "respaldos",
        ruta_clientes_pendientes=tmp_path / "pendientes.json",
    )

    assert resumen["error"] is None
    assert any("visualizador" in aviso.lower() for aviso in resumen["avisos"])
    assert ruta_excel_af.exists()  # el Excel si quedo guardado
```

Nota para quien ejecute este task: revisar el helper real ya usado por los tests existentes de `test_ejecutar.py` para armar un `Centro de Costos.xlsx` mínimo (columnas `N° Ref.`/`Categoría Ítem`/`Total sin IVA (CLP)` en hoja `Detalle`) y usar ese mismo nombre/firma en vez de `_wb_centro_de_costos_minimo` si difiere.

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_ejecutar.py -k no_aborta_si_falla_el_visualizador -v`
Expected: FAIL — `AttributeError: module 'analisis_financiero' has no attribute 'actualizar_visualizador_af'`

- [ ] **Step 3: Agregar `actualizar_visualizador_af()` y encadenarla en `ejecutar()`**

En `Sistema Analisis Financiero/Sistema/analisis_financiero.py`, agregar esta función (mismo patrón que `actualizar_visualizador()` en `Centro de Costos/Sistema/auditor_centro_costos.py`):

```python
RAIZ_VISUALIZADOR_WEB_AF = RAIZ_MODULO / "Visualizador Web"


def actualizar_visualizador_af() -> bool:
    """Regenera el visualizador web (Visualizador Web/build/index.html) a
    partir del Excel recien guardado -- mismo patron que actualizar_
    visualizador() en Centro de Costos: corre al final de ejecutar(), solo
    lee el Excel (no lo modifica), y si falla no aborta el run, solo
    advierte -- el Excel ya quedo guardado igual. Ver Visualizador Web/
    CLAUDE.md para la arquitectura del build."""
    ruta_build_script = RAIZ_VISUALIZADOR_WEB_AF / "build_visualizador.py"
    if not ruta_build_script.exists():
        return False
    ya_en_path = str(RAIZ_VISUALIZADOR_WEB_AF) in sys.path
    if not ya_en_path:
        sys.path.insert(0, str(RAIZ_VISUALIZADOR_WEB_AF))
    try:
        sys.modules.pop("build_visualizador", None)
        import build_visualizador as bv
        return bv.build() == 0
    finally:
        if not ya_en_path and str(RAIZ_VISUALIZADOR_WEB_AF) in sys.path:
            sys.path.remove(str(RAIZ_VISUALIZADOR_WEB_AF))
```

Agregar `import sys` al principio del archivo si no está ya (revisar los imports existentes antes de duplicar).

Modificar el final de `ejecutar()` (justo después de `wb.save(...)` y antes del `return resumen`):

```python
    try:
        wb.save(ruta_excel_af)
    except PermissionError as exc:
        resumen["error"] = f"No se pudo guardar {ruta_excel_af} (¿archivo abierto?): {exc}"

    try:
        if not actualizar_visualizador_af():
            resumen["avisos"].append(
                "No se pudo actualizar el visualizador web -- correr manualmente "
                "'python driver.py visualizador' despues."
            )
    except Exception as exc:
        resumen["avisos"].append(f"No se pudo actualizar el visualizador web: {exc}")

    return resumen
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/ -v`
Expected: todos los tests existentes + el nuevo, todos PASS

- [ ] **Step 5: Agregar el comando `visualizador` a `driver.py`**

En `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py`, agregar:

```python
def cmd_visualizador() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    ya_en_path = str(ROOT / "Visualizador Web") in sys.path
    if not ya_en_path:
        sys.path.insert(0, str(ROOT / "Visualizador Web"))
    import build_visualizador as bv
    return bv.build()
```

Y en `main()`, agregar `"visualizador"` a la tupla `comandos` y el `if`:

```python
def main() -> int:
    comandos = ("status", "run", "confirmar-cliente", "visualizador")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        print("Uso: python driver.py [status|run|confirmar-cliente [--todos|TAG ...]|visualizador]")
        return 2
    if sys.argv[1] == "status":
        return cmd_status()
    if sys.argv[1] == "confirmar-cliente":
        return cmd_confirmar_cliente(sys.argv[2:])
    if sys.argv[1] == "visualizador":
        return cmd_visualizador()
    return cmd_run()
```

- [ ] **Step 6: Verificar el comando manualmente**

Run: `cd "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero" && python driver.py visualizador`
Expected: si `Análisis de Proyectos.xlsx` real existe, imprime `OK — N proyecto(s) completo(s)...` y genera `Sistema Analisis Financiero/Visualizador Web/build/index.html`. Si no existe todavía (módulo sin proyectos cargados), imprime `[ERROR] No existe el Excel...` — ambos son comportamiento esperado, no un fallo del task.

- [ ] **Step 7: Actualizar `SKILL.md`** — agregar el comando nuevo a la lista de comandos documentados (mismo formato que los 3 existentes: `status`/`run`/`confirmar-cliente`), describiendo brevemente que regenera el dashboard HTML sin correr todo `run`.

- [ ] **Step 8: Crear `Sistema Analisis Financiero/Visualizador Web/CLAUDE.md`**

```markdown
# CLAUDE.md — Visualizador Web de Análisis Financiero

Contenido y arquitectura real del dashboard HTML de **Análisis Financiero**.
Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, mandato de herramientas dinámicas, política de datos,
hosting). Ver también [`../CLAUDE.md`](../CLAUDE.md) para el esquema completo
de `Análisis de Proyectos.xlsx`, y el spec de diseño
[`docs/superpowers/specs/2026-07-23-analisis-financiero-visualizador-web-design.md`](../../docs/superpowers/specs/2026-07-23-analisis-financiero-visualizador-web-design.md).

**Estado: implementado (2026-07-23).**

## Implementación real

```
Sistema Analisis Financiero/Visualizador Web/
├── CLAUDE.md              # este archivo — versionado
├── template.html          # estructura/CSS/JS + brand kit, SIN datos — versionado
├── build_visualizador.py  # export saneado (recomputado en Python) + build — versionado
├── tests/                 # pytest de este visualizador — versionado
├── data/                  # snapshot intermedio (analisis-financiero.json) — gitignored
└── build/                 # index.html final con datos incrustados — gitignored
```

- **Un solo comando regenera todo**: `python driver.py visualizador` (desde
  la skill `Registro_Analisis_Financiero`). Correrlo tras cada `run` (o
  automáticamente, ya encadenado en `ejecutar()`) es lo único necesario.
- **Nunca lee celdas de fórmula**: las hojas "Indicadores"/"Clientes" del
  Excel son 100% fórmulas reescritas en cada corrida — `build_visualizador.py`
  recomputa Total Real/Margen Real/Desviación %/Nota/Evaluación/CLTV/
  Clasificación directamente en Python a partir de las columnas manuales de
  "Proyectos" y de "Detalle Costos Reales" (100% valores). Ver spec §2 para
  el detalle y el precedente en Centro de Costos.
- **Proyectos incompletos**: un proyecto sin las 6 columnas manuales
  cargadas (Monto de Venta + 4 Costos Proyectados + Mano de Obra Real) nunca
  recibe KPIs — aparece en el banner "Pendientes de completar" con un link a
  la planilla real. Clientes con proyectos mixtos calculan su CLTV solo con
  los proyectos completos. Ver spec §3.
- **Datos incrustados** (base64, no `fetch`) — mismo motivo que Centro de
  Costos: el canal de consumo es un Claude Artifact privado.
- **Gate de contraseña**: misma contraseña que Centro de Costos (decisión
  del usuario, 2026-07-23) — ver `template.html`.

## Contenido

- **Pestaña Proyectos**: KPIs (N° completos, Margen Real total, Nota
  promedio, N° "Requiere atención"), ranking de Nota del Proyecto (barras),
  distribución de Evaluación (donut), tabla buscable.
- **Pestaña Clientes**: KPIs (top CLTV, CLTV promedio, conteo por
  Clasificación), top 8 clientes por CLTV (barras), distribución de
  Clasificación (donut), tabla buscable con nota de proyectos pendientes
  por cliente.
- Tooltips "i" con el texto de `GLOSARIO_KPIS` de `analisis_financiero.py`
  (hardcodeados en `template.html`, no viajan en el JSON — son texto
  estático, no dependen de datos del usuario).

## Publicación

Claude Artifact privado. El link real vive en
[MEMORY.md de este skill](../.claude/skills/Registro_Analisis_Financiero/MEMORY.md)
— no se regenera salvo pedido explícito del usuario.
```

- [ ] **Step 9: Crear `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/MEMORY.md`**

```markdown
# MEMORY.md — Registro_Analisis_Financiero

Preferencias y datos operativos de este skill (mismo rol que el MEMORY.md
del skill de Centro de Costos — no confundir con
[`Sistema Analisis Financiero/MEMORY.md`](../../MEMORY.md), que es la
memoria de diseño/decisiones del módulo completo).

## Visualizador Web

- Gate de contraseña: misma que Centro de Costos (decisión del usuario,
  2026-07-23) — ver `../../Visualizador Web/template.html`.
- Link del Claude Artifact publicado: **pendiente** — completar la primera
  vez que se publique (ver `Visualizador Web/CLAUDE.md` §Publicación). No
  regenerar un link nuevo una vez que exista uno acá.
```

- [ ] **Step 10: Actualizar `CLAUDE.md` raíz**

Localizar el párrafo que describe **Análisis Financiero** en la tabla de módulos (empieza con `**Análisis Financiero** es distinto a los demás...`) y agregar al final, antes del punto que sigue, esta oración:

```markdown
Desde 2026-07-23 también tiene un Visualizador Web propio
(`Sistema Analisis Financiero/Visualizador Web/`, mismo patrón que Centro de
Costos: proyectos completos con sus KPIs + Clientes/CLTV, excluyendo del
cálculo cualquier proyecto sin información manual completa).
```

- [ ] **Step 11: Verificar el edit de la raíz**

Run: `grep -n "Visualizador Web propio" "CLAUDE.md"`
Expected: 1 línea de match.

- [ ] **Step 12: Correr toda la suite de tests del módulo una última vez**

Run:
```bash
cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/ -v
cd "../Visualizador Web" && python -m pytest tests/ -v
```
Expected: todos PASS, sin regresiones.

- [ ] **Step 13: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_ejecutar.py" "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md" "Sistema Analisis Financiero/Visualizador Web/CLAUDE.md" "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/MEMORY.md" "CLAUDE.md"
git commit -m "feat(visualizador-af): encadenar al run, comando del skill y documentación

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Después de este plan (fuera de alcance, requiere al usuario)

- Publicar `build/index.html` como Claude Artifact privado y completar el
  link en el `MEMORY.md` del skill (Task 9, Step 9) — acción manual del
  usuario/una sesión de Claude Code, no un test automatizado.
- Verificación visual con Playwright (como hizo Centro de Costos en su
  ciclo de mejora continua) si se detectan bugs de layout/tema oscuro que
  el review de código no capture — no incluido en este plan porque el spec
  (§8) marca el testing de contenido visual como fuera de alcance de los
  tests automatizados.
