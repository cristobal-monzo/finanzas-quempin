# Visualizador AF — Pestaña Categoría + Panel de Detalle con PDF — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar al Visualizador Web de Análisis Financiero una tercera pestaña "Categoría" (agregados financieros por categoría de proyecto) y un panel de detalle expandible (proyecto y categoría) con KPIs/gráfico comparativo/tabla completa y el botón para ver/descargar el reporte PDF correspondiente, generado por el skill `Reportes_Analisis_Financiero`.

**Architecture:** Todo el cómputo nuevo vive en `build_visualizador.py` (mismo patrón: recomputar en Python desde datos crudos, nunca leer fórmulas del Excel), agregando `categoria`/fechas/desglose de costos a cada proyecto, una función `calcular_categorias()` y una `embeber_reportes_pdf()` que escanea el disco y embebe los PDFs existentes en base64. El HTML/JS de `template.html` gana una pestaña nueva y un panel de detalle por fila, reutilizando el CSS `tr.detail-row`/`.detail-panel`/`.detail-grid` ya presente en el archivo (heredado sin uso de Centro de Costos) y una función de gráfico de barras comparativo (2 series) genérica y reutilizable.

**Tech Stack:** Python 3 + openpyxl + pytest (lado de datos), HTML/CSS/JS vanilla sin frameworks (lado de dashboard) — mismo stack que el resto del Visualizador Web.

## Global Constraints

- Los PDFs viajan **embebidos en base64** dentro del mismo `build/index.html` — el dashboard es un HTML autocontenido sin backend ni `fetch`, un link a una ruta local no resuelve para quien abre el Artifact publicado.
- El botón "Ver/Descargar PDF" construye un **Blob URL** desde el base64 decodificado (`new Blob([...], {type:'application/pdf'})` + `URL.createObjectURL` + `window.open`) — nunca un `href="data:application/pdf;base64,..."` gigante inline en el DOM.
- Un proyecto sin categoría asignada (columna vacía) cae en el bucket **"Sin categoría"** — nunca se excluye de la pestaña Categoría.
- La ausencia de una clave en `reportes_pdf` (ej. `"proyecto:TAG"` no está en el dict) ES la señal de "sin reporte" — nunca se agrega una clave con valor `None`/vacío.
- El dashboard **no** detecta reportes PDF desactualizados — solo muestra "hay reporte" o "sin reporte generado". Esa detección ya la cubre `Sistema Analisis Financiero/Reportes/estado_reportes.py` por separado.
- Nunca testear `embeber_reportes_pdf`/`calcular_categorias`/etc. contra los PDFs o el Excel reales de la empresa — todos los tests usan `tmp_path` y PDFs/workbooks sintéticos.
- Solo un panel de detalle abierto a la vez (por tabla — Proyectos y Categoría son independientes entre sí).
- Reutilizar el CSS ya existente en `template.html` para el panel expandible (`tr.doc-row`, `.is-expanded`, `.expand-toggle`, `tr.detail-row`, `.detail-panel`, `.detail-grid`, `.dk`/`.dv`/`.dv.accent`, `table.viz-itemtable`) — no escribir CSS nuevo para el panel salvo que un caso puntual lo requiera.
- Nombres de carpeta con tilde exactos: `Análisis Financiero/Reportes/Proyectos/{TAG}.pdf` y `Análisis Financiero/Reportes/Categorías/{Categoria}.pdf` (con tilde en "Categorías") — acceder vía `af.RAIZ_DATOS`, nunca hardcodear una ruta distinta.
- Fuera de alcance: detalle+PDF para Clientes; paginación/orden por columna en la tabla de Categoría (mismo descope ya documentado en `Visualizador Web/CLAUDE.md` para Proyectos/Clientes); republicar el Artifact (acción manual del usuario).
- Ver el spec completo: [`docs/superpowers/specs/2026-07-26-analisis-financiero-visualizador-categoria-detalle-design.md`](../specs/2026-07-26-analisis-financiero-visualizador-categoria-detalle-design.md).

---

### Task 1: `categoria`/fechas/desglose de costos en `leer_proyectos` y `calcular_kpis_proyecto`

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py`
- Test: `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Consumes: `af.HEADERS_PROYECTOS` (ya incluye `"Fecha de cierre"` en índice 6 y `"Categoría"` en índice 21).
- Produces: `leer_proyectos` ahora incluye `"fecha_cierre"`/`"categoria"` (valores crudos) en cada dict de proyecto. `calcular_kpis_proyecto` ahora incluye en su dict de salida: `"fecha_inicio"`, `"fecha_cierre"` (strings `"YYYY-MM-DD"` o `None`, nunca objetos `datetime` — deben ser JSON-serializables tal cual, sin `default=str`), `"categoria"` (valor crudo, `None` si no está asignada — la normalización a `"Sin categoría"` ocurre en `calcular_categorias`, Task 2, no acá), `"costos_proyectados"` (`dict` con claves `materiales`/`equipos`/`mo`/`otros`), `"costos_reales"` (mismo shape).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# agregar a tests/test_build_visualizador.py

def test_leer_proyectos_incluye_fecha_cierre_y_categoria(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    _fila_proyecto_completa(ws, 2, **{"Fecha de cierre": datetime(2026, 3, 15), "Categoría": "I+D+i"})

    proyectos = bv.leer_proyectos(ws)

    assert proyectos[0]["fecha_cierre"] == datetime(2026, 3, 15)
    assert proyectos[0]["categoria"] == "I+D+i"


def test_leer_proyectos_categoria_y_fecha_cierre_none_si_no_estan_cargadas(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    _fila_proyecto_completa(ws, 2)  # sin overrides -- Categoría/Fecha de cierre quedan vacías

    proyectos = bv.leer_proyectos(ws)

    assert proyectos[0]["categoria"] is None
    assert proyectos[0]["fecha_cierre"] is None


def test_calcular_kpis_proyecto_incluye_desglose_de_costos_y_fechas():
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": datetime(2026, 1, 10), "fecha_cierre": datetime(2026, 3, 15),
        "categoria": "I+D+i",
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["fecha_inicio"] == "2026-01-10"
    assert kpis["fecha_cierre"] == "2026-03-15"
    assert kpis["categoria"] == "I+D+i"
    assert kpis["costos_proyectados"] == {
        "materiales": 300_000, "equipos": 200_000, "mo": 200_000, "otros": 100_000,
    }
    assert kpis["costos_reales"] == {
        "materiales": 250_000.0, "equipos": 150_000.0, "mo": 350_000, "otros": 0.0,
    }


def test_calcular_kpis_proyecto_fechas_none_si_no_hay_dato():
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": None, "fecha_cierre": None, "categoria": None,
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["fecha_inicio"] is None
    assert kpis["fecha_cierre"] is None
    assert kpis["categoria"] is None


def test_calcular_kpis_proyecto_fechas_son_json_serializables():
    import json
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": datetime(2026, 1, 10), "fecha_cierre": datetime(2026, 3, 15),
        "categoria": "I+D+i",
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    # build() usa json.dump SIN default=str -- un datetime sin convertir
    # explotaria aca con TypeError al momento de escribir el snapshot real.
    json.dumps(kpis, ensure_ascii=False)
```

Nota: `_fila_proyecto_completa` (helper ya existente en este archivo de test) escribe valores por nombre de columna vía `**overrides` -- pasar `"Fecha de cierre"` y `"Categoría"` como claves del override funciona sin cambiar el helper.

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -k "fecha_cierre or categoria or desglose_de_costos or fechas_son_json" -v`
Expected: FAIL — `KeyError: 'fecha_cierre'` (o `'categoria'`) en `leer_proyectos`, y `KeyError`/`AssertionError` en los tests de `calcular_kpis_proyecto` (el dict de salida todavía no trae esas claves).

- [ ] **Step 3: Implementar**

En `leer_proyectos` (agregar dos claves al dict que arma cada proyecto, junto a las ya existentes):

```python
        proyectos.append({
            "fila": fila,
            "tag": tag,
            "nombre": nombre,
            "cliente": _valor_columna(ws_proyectos, fila, "Cliente"),
            "estado": _valor_columna(ws_proyectos, fila, "Estado"),
            "fecha_inicio": _valor_columna(ws_proyectos, fila, "Fecha de inicio"),
            "fecha_cierre": _valor_columna(ws_proyectos, fila, "Fecha de cierre"),
            "categoria": _valor_columna(ws_proyectos, fila, "Categoría"),
            "monto_venta": _valor_columna(ws_proyectos, fila, "Monto de Venta (sin IVA)"),
            "materiales_proy": _valor_columna(ws_proyectos, fila, "Costos Materiales Proyectados"),
            "equipos_proy": _valor_columna(ws_proyectos, fila, "Costos Equipos Proyectados"),
            "mo_proy": _valor_columna(ws_proyectos, fila, "Mano de Obra Proyectada"),
            "otros_proy": _valor_columna(ws_proyectos, fila, "Otros Costos Proyectados"),
            "mo_real": _valor_columna(ws_proyectos, fila, "Mano de Obra Real"),
        })
```

Agregar un helper de formato de fecha (justo antes de `calcular_kpis_proyecto`):

```python
def _fecha_str(valor):
    """Convierte un valor de celda de fecha (datetime, o ya string, o None)
    a 'YYYY-MM-DD' o None -- nunca deja pasar un datetime crudo hacia el
    JSON del snapshot (json.dump en build() no usa default=str, un datetime
    sin convertir explota con TypeError al escribir data/analisis-
    financiero.json)."""
    if valor is None:
        return None
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d")
    return str(valor)
```

Modificar el `return` de `calcular_kpis_proyecto`:

```python
    return {
        "tag": p["tag"], "nombre": p["nombre"], "cliente": p["cliente"], "estado": p["estado"],
        "fecha_inicio": _fecha_str(p["fecha_inicio"]), "fecha_cierre": _fecha_str(p["fecha_cierre"]),
        "categoria": p["categoria"],
        "monto_venta": p["monto_venta"], "total_proyectado": total_proyectado,
        "total_real": total_real, "margen_real": margen_real, "desviacion_pct": desviacion_pct,
        "nota": nota, "evaluacion": evaluacion,
        "costos_proyectados": {
            "materiales": p["materiales_proy"], "equipos": p["equipos_proy"],
            "mo": p["mo_proy"], "otros": p["otros_proy"],
        },
        "costos_reales": {
            "materiales": costos_reales["Materiales"], "equipos": costos_reales["Equipos"],
            "mo": p["mo_real"], "otros": costos_reales["Otros"],
        },
    }
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/ -v`
Expected: todos los tests existentes + los 5 nuevos, todos PASS (ningún test de Clientes/pendientes debería romperse -- ninguno lee las claves nuevas).

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/build_visualizador.py" "Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py"
git commit -m "feat(visualizador-af): categoria/fechas/desglose de costos en KPIs de proyecto

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `calcular_categorias()`

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py`
- Test: `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Consumes: la lista de dicts que devuelve `calcular_kpis_proyecto` (Task 1) — específicamente `tag`, `categoria`, `margen_real_total`... espera, `margen_real` y `nota` (no hay campo `margen_real_total` en un solo KPI, ese nombre es del agregado que arma esta función).
- Produces: `calcular_categorias(kpis_proyectos_completos: list[dict]) -> list[dict]`, cada fila con `{"categoria": str, "n_proyectos": int, "margen_real_total": float, "nota_promedio": float, "tags_proyectos": list[str]}` — usado por Task 4 (`extraer_datos_saneados`) y por Task 8 (panel de detalle de categoría, vía `tags_proyectos` para listar los proyectos de esa categoría).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# agregar a tests/test_build_visualizador.py

def _kpi_proyecto(tag, categoria, margen_real, nota):
    return {
        "tag": tag, "nombre": tag, "cliente": "Cliente", "estado": "En Proceso",
        "fecha_inicio": None, "fecha_cierre": None, "categoria": categoria,
        "monto_venta": 0, "total_proyectado": 0, "total_real": 0,
        "margen_real": margen_real, "desviacion_pct": 0.0, "nota": nota, "evaluacion": "Bueno",
        "costos_proyectados": {"materiales": 0, "equipos": 0, "mo": 0, "otros": 0},
        "costos_reales": {"materiales": 0, "equipos": 0, "mo": 0, "otros": 0},
    }


def test_calcular_categorias_agrupa_y_suma_margen():
    kpis = [
        _kpi_proyecto("P1", "I+D+i", 100_000, 80),
        _kpi_proyecto("P2", "I+D+i", 200_000, 90),
        _kpi_proyecto("P3", "Mantención", 50_000, 60),
    ]

    categorias = bv.calcular_categorias(kpis)
    por_nombre = {c["categoria"]: c for c in categorias}

    assert por_nombre["I+D+i"]["n_proyectos"] == 2
    assert por_nombre["I+D+i"]["margen_real_total"] == 300_000
    assert por_nombre["I+D+i"]["nota_promedio"] == 85.0
    assert por_nombre["I+D+i"]["tags_proyectos"] == ["P1", "P2"]
    assert por_nombre["Mantención"]["n_proyectos"] == 1


def test_calcular_categorias_proyecto_sin_categoria_va_a_bucket_sin_categoria():
    kpis = [_kpi_proyecto("P1", None, 100_000, 80), _kpi_proyecto("P2", "", 50_000, 70)]

    categorias = bv.calcular_categorias(kpis)

    assert len(categorias) == 1
    assert categorias[0]["categoria"] == "Sin categoría"
    assert categorias[0]["n_proyectos"] == 2


def test_calcular_categorias_lista_vacia_devuelve_lista_vacia():
    assert bv.calcular_categorias([]) == []
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -k calcular_categorias -v`
Expected: FAIL — `AttributeError: module 'build_visualizador' has no attribute 'calcular_categorias'`

- [ ] **Step 3: Implementar**

Agregar a `build_visualizador.py`, después de `calcular_clientes`:

```python
def calcular_categorias(kpis_proyectos_completos: list[dict]) -> list[dict]:
    """Agrupa kpis_proyectos_completos (ya filtrados a solo proyectos
    completos, mismo criterio que calcular_clientes) por 'categoria'. Un
    proyecto sin categoria asignada (None o cadena vacia) cae en el bucket
    "Sin categoría" en vez de excluirse -- spec §3."""
    por_categoria: dict[str, list[dict]] = {}
    for kpi in kpis_proyectos_completos:
        categoria = kpi["categoria"] or "Sin categoría"
        por_categoria.setdefault(categoria, []).append(kpi)

    filas = []
    for categoria, kpis in por_categoria.items():
        n = len(kpis)
        filas.append({
            "categoria": categoria,
            "n_proyectos": n,
            "margen_real_total": sum(k["margen_real"] for k in kpis),
            "nota_promedio": sum(k["nota"] for k in kpis) / n,
            "tags_proyectos": [k["tag"] for k in kpis],
        })
    return filas
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/ -v`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/build_visualizador.py" "Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py"
git commit -m "feat(visualizador-af): calcular_categorias agrupa proyectos completos por categoria

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: `embeber_reportes_pdf()`

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py`
- Test: `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Consumes: `af.RAIZ_DATOS` (ya existe en `analisis_financiero.py`, apunta a `Análisis Financiero/`); la lista de proyectos completos (necesita `tag`) y la lista de categorías (necesita `categoria`, de Task 2).
- Produces: `embeber_reportes_pdf(proyectos: list[dict], categorias: list[dict]) -> dict[str, str]`, claves `"proyecto:{TAG}"` / `"categoria:{Nombre}"`, valores = PDF en base64. Sin clave = sin reporte. Usado por Task 4. Módulo expone también `RAIZ_REPORTES` (constante a nivel de módulo, monkeypatcheable en tests, igual que `RUTA_EXCEL`).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# agregar a tests/test_build_visualizador.py
import base64 as _base64  # ya se puede importar 'base64' arriba del archivo si no esta


def test_embeber_reportes_pdf_incluye_solo_proyectos_con_pdf_existente(tmp_path, monkeypatch):
    raiz_reportes = tmp_path / "Reportes"
    (raiz_reportes / "Proyectos").mkdir(parents=True)
    (raiz_reportes / "Proyectos" / "UMAG.pdf").write_bytes(b"%PDF-1.4 contenido de prueba")
    monkeypatch.setattr(bv, "RAIZ_REPORTES", raiz_reportes)

    reportes = bv.embeber_reportes_pdf(
        [{"tag": "UMAG"}, {"tag": "SINPDF"}], [],
    )

    assert "proyecto:UMAG" in reportes
    assert "proyecto:SINPDF" not in reportes
    assert _base64.b64decode(reportes["proyecto:UMAG"]) == b"%PDF-1.4 contenido de prueba"


def test_embeber_reportes_pdf_incluye_categorias_con_pdf_existente(tmp_path, monkeypatch):
    raiz_reportes = tmp_path / "Reportes"
    (raiz_reportes / "Categorías").mkdir(parents=True)
    (raiz_reportes / "Categorías" / "I+D+i.pdf").write_bytes(b"%PDF fake categoria")
    monkeypatch.setattr(bv, "RAIZ_REPORTES", raiz_reportes)

    reportes = bv.embeber_reportes_pdf(
        [], [{"categoria": "I+D+i"}, {"categoria": "Sin categoría"}],
    )

    assert "categoria:I+D+i" in reportes
    assert "categoria:Sin categoría" not in reportes


def test_embeber_reportes_pdf_devuelve_vacio_si_no_hay_carpeta_reportes(tmp_path, monkeypatch):
    monkeypatch.setattr(bv, "RAIZ_REPORTES", tmp_path / "esta-carpeta-no-existe")

    reportes = bv.embeber_reportes_pdf([{"tag": "X"}], [{"categoria": "Y"}])

    assert reportes == {}
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -k embeber_reportes_pdf -v`
Expected: FAIL — `AttributeError: module 'build_visualizador' has no attribute 'embeber_reportes_pdf'` (y `RAIZ_REPORTES` tampoco existe todavía).

- [ ] **Step 3: Implementar**

Agregar la constante junto a las demás rutas, cerca del principio del archivo (junto a `RUTA_EXCEL`/`RUTA_TEMPLATE`):

```python
RAIZ_REPORTES = af.RAIZ_DATOS / "Reportes"
```

Agregar la función después de `calcular_categorias`:

```python
def embeber_reportes_pdf(proyectos: list[dict], categorias: list[dict]) -> dict[str, str]:
    """Escanea RAIZ_REPORTES/{Proyectos,Categorías}/*.pdf y embebe en base64
    los que existen. La ausencia de una clave en el dict devuelto ES la
    señal de "sin reporte" -- nunca se agrega una clave con valor None o
    cadena vacia. Nunca escribe ni modifica ningun PDF, solo lee."""
    reportes: dict[str, str] = {}

    for p in proyectos:
        ruta = RAIZ_REPORTES / "Proyectos" / f"{p['tag']}.pdf"
        if ruta.exists():
            reportes[f"proyecto:{p['tag']}"] = base64.b64encode(ruta.read_bytes()).decode("ascii")

    for c in categorias:
        ruta = RAIZ_REPORTES / "Categorías" / f"{c['categoria']}.pdf"
        if ruta.exists():
            reportes[f"categoria:{c['categoria']}"] = base64.b64encode(ruta.read_bytes()).decode("ascii")

    return reportes
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/ -v`
Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/build_visualizador.py" "Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py"
git commit -m "feat(visualizador-af): embeber_reportes_pdf incrusta en base64 los PDF existentes

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Wiring en `extraer_datos_saneados`

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py`
- Test: `Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Consumes: `calcular_categorias` (Task 2), `embeber_reportes_pdf` (Task 3).
- Produces: el dict que devuelve `extraer_datos_saneados` ahora incluye también `"categorias"` y `"reportes_pdf"`, junto a los ya existentes `proyectos`/`clientes`/`pendientes`/`kpis_proyectos`/`generado`. Consumido por Task 5-8 (JS de `template.html`) y por `build()` (sin cambios — ya serializa el dict completo tal cual).

- [ ] **Step 1: Escribir el test que falla**

```python
# agregar a tests/test_build_visualizador.py

def test_extraer_datos_saneados_incluye_categorias_y_reportes_pdf(tmp_path, monkeypatch):
    ruta_excel = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta_excel)
    ws = wb[af.HOJA_PROYECTOS]
    _fila_proyecto_completa(ws, 2, **{"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Categoría": "I+D+i"})
    wb.save(ruta_excel)

    raiz_reportes = tmp_path / "Reportes"
    (raiz_reportes / "Proyectos").mkdir(parents=True)
    (raiz_reportes / "Proyectos" / "UMAG.pdf").write_bytes(b"%PDF fake")
    monkeypatch.setattr(bv, "RAIZ_REPORTES", raiz_reportes)

    data = bv.extraer_datos_saneados(ruta_excel)

    assert data["categorias"] == [{
        "categoria": "I+D+i", "n_proyectos": 1,
        "margen_real_total": data["proyectos"][0]["margen_real"],
        "nota_promedio": data["proyectos"][0]["nota"],
        "tags_proyectos": ["UMAG"],
    }]
    assert "proyecto:UMAG" in data["reportes_pdf"]
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -k incluye_categorias_y_reportes_pdf -v`
Expected: FAIL — `KeyError: 'categorias'` (el dict devuelto todavía no trae esa clave).

- [ ] **Step 3: Implementar**

En `extraer_datos_saneados`, después de la línea `clientes = calcular_clientes(completos, proyectos_por_tag)`:

```python
    clientes = calcular_clientes(completos, proyectos_por_tag)
    categorias = calcular_categorias(completos)
    reportes_pdf = embeber_reportes_pdf(completos, categorias)
```

Y en el `return` final, agregar las dos claves nuevas junto a las existentes:

```python
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
        "categorias": categorias,
        "pendientes": pendientes,
        "reportes_pdf": reportes_pdf,
    }
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `cd "Sistema Analisis Financiero/Visualizador Web" && python -m pytest tests/ -v`
Expected: todos PASS (incluye el smoke test de `build()` de una tarea anterior, que no debería romperse ya que solo agrega claves, no remueve ninguna).

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/build_visualizador.py" "Sistema Analisis Financiero/Visualizador Web/tests/test_build_visualizador.py"
git commit -m "feat(visualizador-af): extraer_datos_saneados agrega categorias y reportes_pdf al snapshot

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Pestaña "Categoría" — markup + KPIs + gráficos + tabla

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `DATA.categorias` (Task 4); `renderBarChart`/`renderDonutChart`/`formatoCLP`/`esc`/`debounce` (ya existen en `initApp`, ver `template.html:645-849` antes de esta tarea).
- Produces: elementos `#kpiNCategorias`/`#kpiCategoriaLider`/`#chartMargenCategoria`/`#chartDistribucionCategoria`/`#buscarCategorias`/`#tablaCategoriasBody`, y la variable `categoriasOrdenadas` dentro de `initApp` (usada por Task 8 para el panel de detalle de categoría).

- [ ] **Step 1: Agregar el botón de la pestaña nueva** al `<nav class="viz-tabs">` (`template.html:497-500`), después del botón de Clientes:

```html
    <nav class="viz-tabs">
      <button class="viz-tab-btn active" data-tab="tabProyectos" type="button">Proyectos</button>
      <button class="viz-tab-btn" data-tab="tabClientes" type="button">Clientes</button>
      <button class="viz-tab-btn" data-tab="tabCategoria" type="button">Categoría</button>
    </nav>
```

- [ ] **Step 2: Agregar la sección de la pestaña**, después del `</section>` que cierra `tabClientes` (`template.html:566`) y antes del `<p class="viz-footer">` (`template.html:568`):

```html
    <section id="tabCategoria" class="viz-tab-panel">
      <div class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-label">N° categorías</div>
          <div class="kpi-value" id="kpiNCategorias"></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Categoría líder por Margen Real</div>
          <div class="kpi-value" id="kpiCategoriaLider"></div>
        </div>
      </div>
      <div class="chart-row">
        <div class="chart-card"><h3>Margen Real por Categoría</h3><div id="chartMargenCategoria"></div></div>
        <div class="chart-card"><h3>Distribución de Proyectos</h3><div id="chartDistribucionCategoria"></div></div>
      </div>
      <input type="text" id="buscarCategorias" class="viz-search" placeholder="Buscar categoría…">
      <table class="viz-table">
        <thead>
          <tr><th>Categoría</th><th>N° Proyectos</th><th>Margen Real Total</th><th>Nota Promedio</th></tr>
        </thead>
        <tbody id="tablaCategoriasBody"></tbody>
      </table>
    </section>
```

- [ ] **Step 3: Agregar el JS dentro de `initApp(DATA)`**, después del bloque de Clientes (justo antes de `} // end initApp`, `template.html:849`):

```javascript
  // ---------- pestaña Categoría ----------
  var CATEGORIAS = DATA.categorias;
  var categoriasOrdenadas = CATEGORIAS.slice().sort(function (a, b) { return b.margen_real_total - a.margen_real_total; });
  document.getElementById('kpiNCategorias').textContent = categoriasOrdenadas.length;
  document.getElementById('kpiCategoriaLider').textContent = categoriasOrdenadas.length ? categoriasOrdenadas[0].categoria : '—';

  renderBarChart('chartMargenCategoria', categoriasOrdenadas.map(function (c) {
    return { categoria: c.categoria, margen_real_total: c.margen_real_total, valueLabel: formatoCLP(c.margen_real_total) };
  }), 'categoria', 'margen_real_total');
  renderDonutChart('chartDistribucionCategoria', categoriasOrdenadas.map(function (c) {
    return { categoria: c.categoria, n_proyectos: c.n_proyectos };
  }), 'categoria', 'n_proyectos');

  function renderTablaCategorias(items) {
    var tbody = document.getElementById('tablaCategoriasBody');
    tbody.innerHTML = items.map(function (c) {
      return '<tr><td>' + esc(c.categoria) + '</td><td>' + c.n_proyectos + '</td><td>' +
        formatoCLP(c.margen_real_total) + '</td><td>' + c.nota_promedio.toFixed(1) + '</td></tr>';
    }).join('');
  }
  renderTablaCategorias(categoriasOrdenadas);
  document.getElementById('buscarCategorias').addEventListener('input', debounce(function (evt) {
    var q = evt.target.value.toLowerCase();
    renderTablaCategorias(categoriasOrdenadas.filter(function (c) {
      return c.categoria.toLowerCase().indexOf(q) !== -1;
    }));
  }, 150));
```

- [ ] **Step 4: Verificación manual en navegador**

Estos fragmentos de `template.html` no tienen `<!doctype html>`/`<meta charset="utf-8">` (son fragmentos de Claude Artifact, envueltos recién al publicar) — al servirlos sueltos vía `python -m http.server` para probarlos en un navegador real, esto puede producir un falso positivo de encoding ya documentado (un error de regex en el gate que no es un bug real, ver `Sistema Analisis Financiero/Visualizador Web/CLAUDE.md` o el ledger del plan anterior). Para evitarlo, envolver una copia temporal así antes de abrirla:

```python
# ejecutar desde Sistema Analisis Financiero/Visualizador Web/
contenido = open("template.html", encoding="utf-8").read()
shim = "<!doctype html><html><head><meta charset=\"utf-8\"></head><body>" + contenido + "</body></html>"
open("_test_template.html", "w", encoding="utf-8").write(shim)
```

Luego `python -m http.server 8000` y abrir `http://localhost:8000/_test_template.html`, reemplazando temporalmente `__AF_DATA_B64__` por un JSON de prueba en base64 (mismo patrón que las tareas anteriores del visualizador) con 2-3 categorías distintas. Confirmar: las 2 tarjetas KPI muestran los números correctos, el gráfico de barras y el donut se ven proporcionales, la tabla se filtra al escribir en el buscador. Borrar `_test_template.html` al terminar (no commitear).

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/template.html"
git commit -m "feat(visualizador-af): pestaña Categoría con KPIs, gráficos y tabla buscable

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: Utilidades JS genéricas — `renderBarChartComparativo` y `abrirPdfBlob`

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `esc`/`formatoCLP` (ya existen).
- Produces: `renderBarChartComparativo(containerId, items, labelKey, valorAKey, valorBKey, etiquetaA, etiquetaB)` y `abrirPdfBlob(base64, nombreArchivo)` — ambas reutilizadas por Task 7 (detalle Proyectos) y Task 8 (detalle Categoría).

- [ ] **Step 1: Agregar ambas funciones dentro de `initApp(DATA)`**, justo después de `renderDonutChart` (que termina en `template.html:776`, antes del comentario `// ---------- pestaña Proyectos ----------`):

```javascript
  function renderBarChartComparativo(containerId, items, labelKey, valorAKey, valorBKey, etiquetaA, etiquetaB) {
    var el = document.getElementById(containerId);
    var max = Math.max.apply(null, items.map(function (i) {
      return Math.max(i[valorAKey], i[valorBKey]);
    }).concat([1]));
    var legend = '<div class="donut-legend-row"><span class="donut-swatch" style="background:var(--brand-orange)"></span>' +
      esc(etiquetaA) + '</div><div class="donut-legend-row"><span class="donut-swatch" style="background:var(--brand-gray-11)"></span>' +
      esc(etiquetaB) + '</div>';
    var rows = items.map(function (i) {
      var pctA = Math.max(0, i[valorAKey]) / max * 100;
      var pctB = Math.max(0, i[valorBKey]) / max * 100;
      return '<div class="bar-label" style="margin-top:8px;font-weight:600">' + esc(i[labelKey]) + '</div>' +
        '<div class="bar-row"><div class="bar-track"><div class="bar-fill" style="width:' + pctA + '%"></div></div>' +
        '<div class="bar-value">' + formatoCLP(i[valorAKey]) + '</div></div>' +
        '<div class="bar-row"><div class="bar-track"><div class="bar-fill" style="width:' + pctB + '%;background:var(--brand-gray-11)"></div></div>' +
        '<div class="bar-value">' + formatoCLP(i[valorBKey]) + '</div></div>';
    }).join('');
    el.innerHTML = rows ? ('<div class="donut-legend" style="margin-bottom:8px">' + legend + '</div>' + rows) : '<p>Sin datos.</p>';
  }

  function abrirPdfBlob(base64, nombreArchivo) {
    var binario = atob(base64);
    var bytes = new Uint8Array(binario.length);
    for (var i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i);
    var blob = new Blob([bytes], { type: 'application/pdf' });
    var url = URL.createObjectURL(blob);
    window.open(url, '_blank');
  }
```

- [ ] **Step 2: Verificación de sintaxis**

Extraer el bloque `<script>` de `template.html` a un archivo temporal y verificar que sigue siendo JS válido:

```bash
cd "Sistema Analisis Financiero/Visualizador Web"
python -c "import re; open('_script_check.js','w',encoding='utf-8').write(re.search(r'<script>(.*)</script>', open('template.html', encoding='utf-8').read(), re.S).group(1))"
node --check _script_check.js
```
Expected: sin salida (exit code 0). Borrar `_script_check.js` al terminar (no commitear).

No hace falta verificación en navegador para esta tarea — ninguna de las dos funciones se invoca todavía desde ningún lado (son utilidades genéricas sin consumidor propio); Task 7 y Task 8 las conectan y las ejercitan de punta a punta con datos reales en su propia verificación manual.

- [ ] **Step 3: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/template.html"
git commit -m "feat(visualizador-af): renderBarChartComparativo y abrirPdfBlob genericos

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Panel de detalle expandible — Proyectos

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `renderBarChartComparativo`/`abrirPdfBlob` (Task 6); `DATA.reportes_pdf` (Task 4); CSS ya existente `tr.doc-row`/`.is-expanded`/`.expand-toggle`/`tr.detail-row`/`.detail-panel`/`.detail-grid`/`.dk`/`.dv`/`.dv.accent`/`table.viz-itemtable` (confirmar presentes en el `<style>` de `template.html` antes de escribir HTML nuevo — no se necesita CSS adicional).
- Produces: nada consumido por otro task — es la última pieza de la pestaña Proyectos.

- [ ] **Step 1: Reemplazar `renderTablaProyectos` y su wiring** (`template.html:795-809` antes de esta tarea) por la versión con fila expandible. Buscar primero `var proyectoExpandido` — si no existe, agregar la variable justo antes de la función:

```javascript
  var proyectoExpandido = null;

  function detalleProyectoHtml(p) {
    var pdfKey = 'proyecto:' + p.tag;
    var pdfBtn = DATA.reportes_pdf[pdfKey]
      ? '<button type="button" class="pendientes-toggle-btn" data-pdf-key="' + esc(pdfKey) + '">Ver/Descargar PDF</button>'
      : '<span style="color:var(--text-muted);font-size:12px">Sin reporte generado</span>';
    return '<div class="detail-panel">' +
      '<div class="detail-grid">' +
        '<div><div class="dk">Margen Real</div><div class="dv accent">' + formatoCLP(p.margen_real) + '</div></div>' +
        '<div><div class="dk">Margen Proyectado</div><div class="dv">' + formatoCLP(p.monto_venta - p.total_proyectado) + '</div></div>' +
        '<div><div class="dk">Desviación %</div><div class="dv">' + formatoPct(p.desviacion_pct) + '</div></div>' +
        '<div><div class="dk">Nota / Evaluación</div><div class="dv">' + p.nota + ' — ' + esc(p.evaluacion) + '</div></div>' +
      '</div>' +
      '<div id="chartComparativo-' + esc(p.tag) + '" style="margin-bottom:12px"></div>' +
      '<table class="viz-itemtable"><thead><tr><th>Concepto</th><th>Proyectado</th><th>Real</th></tr></thead><tbody>' +
        '<tr><td>Materiales</td><td class="num">' + formatoCLP(p.costos_proyectados.materiales) + '</td><td class="num">' + formatoCLP(p.costos_reales.materiales) + '</td></tr>' +
        '<tr><td>Equipos</td><td class="num">' + formatoCLP(p.costos_proyectados.equipos) + '</td><td class="num">' + formatoCLP(p.costos_reales.equipos) + '</td></tr>' +
        '<tr><td>Mano de Obra</td><td class="num">' + formatoCLP(p.costos_proyectados.mo) + '</td><td class="num">' + formatoCLP(p.costos_reales.mo) + '</td></tr>' +
        '<tr><td>Otros</td><td class="num">' + formatoCLP(p.costos_proyectados.otros) + '</td><td class="num">' + formatoCLP(p.costos_reales.otros) + '</td></tr>' +
        '<tr><td><strong>Total</strong></td><td class="num"><strong>' + formatoCLP(p.total_proyectado) + '</strong></td><td class="num"><strong>' + formatoCLP(p.total_real) + '</strong></td></tr>' +
      '</tbody></table>' +
      '<div class="detail-grid" style="margin-top:12px">' +
        '<div><div class="dk">Monto de Venta</div><div class="dv">' + formatoCLP(p.monto_venta) + '</div></div>' +
        '<div><div class="dk">Fecha de inicio</div><div class="dv">' + esc(p.fecha_inicio || '—') + '</div></div>' +
        '<div><div class="dk">Fecha de cierre</div><div class="dv">' + esc(p.fecha_cierre || '—') + '</div></div>' +
        '<div><div class="dk">Categoría</div><div class="dv">' + esc(p.categoria || 'Sin categoría') + '</div></div>' +
      '</div>' +
      pdfBtn +
      '</div>';
  }

  function proyectosFiltrados() {
    var q = document.getElementById('buscarProyectos').value.toLowerCase();
    return proyectosOrdenados.filter(function (p) {
      return (p.nombre + ' ' + (p.cliente || '')).toLowerCase().indexOf(q) !== -1;
    });
  }

  function renderTablaProyectos(items) {
    var tbody = document.getElementById('tablaProyectosBody');
    tbody.innerHTML = items.map(function (p) {
      var expandido = proyectoExpandido === p.tag;
      var fila = '<tr class="doc-row' + (expandido ? ' is-expanded' : '') + '" data-tag="' + esc(p.tag) + '" tabindex="0">' +
        '<td><span class="expand-toggle">' + (expandido ? '▾' : '▸') + '</span>' + esc(p.nombre) + '</td><td>' + esc(p.cliente || '—') + '</td><td>' + esc(p.estado || '—') +
        '</td><td>' + formatoCLP(p.monto_venta) + '</td><td>' + formatoCLP(p.margen_real) + '</td><td>' +
        formatoPct(p.desviacion_pct) + '</td><td>' + p.nota + '</td><td>' + esc(p.evaluacion) + '</td></tr>';
      if (expandido) {
        fila += '<tr class="detail-row"><td colspan="8">' + detalleProyectoHtml(p) + '</td></tr>';
      }
      return fila;
    }).join('');
    if (proyectoExpandido) {
      var expandidoEnLista = items.filter(function (x) { return x.tag === proyectoExpandido; })[0];
      if (expandidoEnLista) {
        renderBarChartComparativo('chartComparativo-' + proyectoExpandido, [
          { concepto: 'Materiales', proy: expandidoEnLista.costos_proyectados.materiales, real: expandidoEnLista.costos_reales.materiales },
          { concepto: 'Equipos', proy: expandidoEnLista.costos_proyectados.equipos, real: expandidoEnLista.costos_reales.equipos },
          { concepto: 'Mano de Obra', proy: expandidoEnLista.costos_proyectados.mo, real: expandidoEnLista.costos_reales.mo },
          { concepto: 'Otros', proy: expandidoEnLista.costos_proyectados.otros, real: expandidoEnLista.costos_reales.otros },
        ], 'concepto', 'proy', 'real', 'Proyectado', 'Real');
      }
    }
  }
  renderTablaProyectos(proyectosOrdenados);
  document.getElementById('buscarProyectos').addEventListener('input', debounce(function () {
    renderTablaProyectos(proyectosFiltrados());
  }, 150));
  document.getElementById('tablaProyectosBody').addEventListener('click', function (evt) {
    var btnPdf = evt.target.closest('[data-pdf-key]');
    if (btnPdf) {
      abrirPdfBlob(DATA.reportes_pdf[btnPdf.getAttribute('data-pdf-key')], btnPdf.getAttribute('data-pdf-key').replace(':', '_') + '.pdf');
      return;
    }
    var row = evt.target.closest('tr.doc-row');
    if (!row) return;
    var tag = row.getAttribute('data-tag');
    proyectoExpandido = (proyectoExpandido === tag) ? null : tag;
    renderTablaProyectos(proyectosFiltrados());
  });
```

Esto reemplaza por completo el bloque anterior (desde `function renderTablaProyectos(items) {` hasta el `document.getElementById('buscarProyectos').addEventListener(...)` original de la Tarea 6 del plan anterior) — el nuevo `proyectosFiltrados()` reemplaza el filtro que antes estaba inline dentro del listener de búsqueda.

- [ ] **Step 2: Verificación manual en navegador**

Mismo procedimiento de shim de encoding que Task 5. Con un JSON de prueba de 2 proyectos completos (uno con `reportes_pdf["proyecto:TAG1"]` presente en base64 de un PDF mínimo válido, ej. generado con `python -c "import base64; print(base64.b64encode(open('algun.pdf','rb').read()).decode())"` sobre cualquier PDF de prueba, y otro proyecto sin esa clave) confirmar:
- Click en una fila expande el panel de detalle debajo, con los 4 KPI cards, el gráfico comparativo (2 barras por categoría de costo) y la tabla de montos.
- Click de nuevo en la misma fila lo colapsa.
- El proyecto con PDF muestra el botón "Ver/Descargar PDF" y al hacer click abre una pestaña nueva con el PDF renderizado (blob URL, revisar que la URL en la barra de direcciones empiece con `blob:`).
- El proyecto sin PDF muestra el texto "Sin reporte generado", sin botón.
- Buscar un proyecto mientras el panel está abierto no rompe nada (si el proyecto expandido queda filtrado fuera, su panel simplemente desaparece de la vista).

- [ ] **Step 3: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/template.html"
git commit -m "feat(visualizador-af): panel de detalle expandible en tabla de Proyectos

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Panel de detalle expandible — Categoría

**Files:**
- Modify: `Sistema Analisis Financiero/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `renderBarChart`/`abrirPdfBlob` (Task 6, reutiliza `renderBarChart` genérico de Tarea 6 del plan anterior — no `renderBarChartComparativo`, ya que acá se comparan proyectos dentro de una categoría, no Proyectado vs Real); `DATA.reportes_pdf`; `PROYECTOS` (variable ya existente en `initApp`, todos los proyectos completos, para filtrar por `tags_proyectos`); mismo CSS reutilizado que Task 7.
- Produces: nada consumido por otro task — última pieza del panel de detalle.

- [ ] **Step 1: Reemplazar `renderTablaCategorias` y su wiring** (agregados en Task 5) por la versión con fila expandible:

```javascript
  var categoriaExpandida = null;

  function detalleCategoriaHtml(c) {
    var pdfKey = 'categoria:' + c.categoria;
    var pdfBtn = DATA.reportes_pdf[pdfKey]
      ? '<button type="button" class="pendientes-toggle-btn" data-pdf-key-cat="' + esc(pdfKey) + '">Ver/Descargar PDF</button>'
      : '<span style="color:var(--text-muted);font-size:12px">Sin reporte generado</span>';
    var proyectosDeCategoria = PROYECTOS.filter(function (p) { return c.tags_proyectos.indexOf(p.tag) !== -1; });
    var filas = proyectosDeCategoria.map(function (p) {
      return '<tr><td>' + esc(p.nombre) + '</td><td>' + esc(p.cliente || '—') + '</td><td class="num">' +
        formatoCLP(p.margen_real) + '</td><td class="num">' + p.nota + '</td></tr>';
    }).join('');
    return '<div class="detail-panel">' +
      '<div class="detail-grid">' +
        '<div><div class="dk">N° Proyectos</div><div class="dv">' + c.n_proyectos + '</div></div>' +
        '<div><div class="dk">Margen Real Total</div><div class="dv accent">' + formatoCLP(c.margen_real_total) + '</div></div>' +
        '<div><div class="dk">Nota Promedio</div><div class="dv">' + c.nota_promedio.toFixed(1) + '</div></div>' +
      '</div>' +
      '<div id="chartProyectosCategoria-' + esc(c.categoria) + '" style="margin-bottom:12px"></div>' +
      '<table class="viz-itemtable"><thead><tr><th>Proyecto</th><th>Cliente</th><th>Margen Real</th><th>Nota</th></tr></thead>' +
      '<tbody>' + filas + '</tbody></table>' +
      pdfBtn +
      '</div>';
  }

  function categoriasFiltradas() {
    var q = document.getElementById('buscarCategorias').value.toLowerCase();
    return categoriasOrdenadas.filter(function (c) {
      return c.categoria.toLowerCase().indexOf(q) !== -1;
    });
  }

  function renderTablaCategorias(items) {
    var tbody = document.getElementById('tablaCategoriasBody');
    tbody.innerHTML = items.map(function (c) {
      var expandido = categoriaExpandida === c.categoria;
      var fila = '<tr class="doc-row' + (expandido ? ' is-expanded' : '') + '" data-categoria="' + esc(c.categoria) + '" tabindex="0">' +
        '<td><span class="expand-toggle">' + (expandido ? '▾' : '▸') + '</span>' + esc(c.categoria) + '</td><td>' + c.n_proyectos + '</td><td>' +
        formatoCLP(c.margen_real_total) + '</td><td>' + c.nota_promedio.toFixed(1) + '</td></tr>';
      if (expandido) {
        fila += '<tr class="detail-row"><td colspan="4">' + detalleCategoriaHtml(c) + '</td></tr>';
      }
      return fila;
    }).join('');
    if (categoriaExpandida) {
      var expandidaEnLista = items.filter(function (x) { return x.categoria === categoriaExpandida; })[0];
      if (expandidaEnLista) {
        var proyectosDeCategoria = PROYECTOS.filter(function (p) { return expandidaEnLista.tags_proyectos.indexOf(p.tag) !== -1; });
        renderBarChart('chartProyectosCategoria-' + categoriaExpandida, proyectosDeCategoria.map(function (p) {
          return { nombre: p.nombre, margen_real: p.margen_real, valueLabel: formatoCLP(p.margen_real) };
        }), 'nombre', 'margen_real');
      }
    }
  }
  renderTablaCategorias(categoriasOrdenadas);
  document.getElementById('buscarCategorias').addEventListener('input', debounce(function () {
    renderTablaCategorias(categoriasFiltradas());
  }, 150));
  document.getElementById('tablaCategoriasBody').addEventListener('click', function (evt) {
    var btnPdf = evt.target.closest('[data-pdf-key-cat]');
    if (btnPdf) {
      abrirPdfBlob(DATA.reportes_pdf[btnPdf.getAttribute('data-pdf-key-cat')], btnPdf.getAttribute('data-pdf-key-cat').replace(':', '_') + '.pdf');
      return;
    }
    var row = evt.target.closest('tr.doc-row');
    if (!row) return;
    var categoria = row.getAttribute('data-categoria');
    categoriaExpandida = (categoriaExpandida === categoria) ? null : categoria;
    renderTablaCategorias(categoriasFiltradas());
  });
```

Esto reemplaza por completo el bloque `renderTablaCategorias`/wiring agregado en la Task 5 de este mismo plan.

Nota: `data-pdf-key-cat` (en vez de `data-pdf-key`, ya usado en la tabla de Proyectos) evita ambigüedad si algún selector llegara a buscar en todo el documento en vez de en su propio `tbody` — cada listener ya está scopeado a su propio `tbody`, así que en la práctica no colisionan, pero el nombre distinto lo deja explícito.

- [ ] **Step 2: Verificación manual en navegador**

Mismo shim de encoding. Con un JSON de prueba de 2 categorías (una con `reportes_pdf["categoria:Nombre"]` presente, otra sin), y proyectos completos repartidos entre ambas, confirmar:
- Click en una fila de categoría expande el panel con las 3 KPI, el gráfico de barras de proyectos de esa categoría, y la tabla de proyectos.
- Botón de PDF funciona igual que en Task 7 (blob URL, pestaña nueva).
- Categoría sin PDF muestra "Sin reporte generado".
- Buscar y expandir/colapsar no rompen la pestaña Proyectos ni viceversa (son tablas/estado independientes).

- [ ] **Step 3: Correr toda la suite de tests del módulo una última vez**

Run:
```bash
cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/ -v
cd "../Visualizador Web" && python -m pytest tests/ -v
```
Expected: todos PASS, sin regresiones (esta tarea no toca Python, pero confirma que nada quedó roto por las tareas anteriores).

- [ ] **Step 4: Commit**

```bash
git add "Sistema Analisis Financiero/Visualizador Web/template.html"
git commit -m "feat(visualizador-af): panel de detalle expandible en tabla de Categoría

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Después de este plan (fuera de alcance, requiere al usuario)

- Regenerar el visualizador (`python driver.py visualizador`) y republicar el Artifact — acción manual, como ya ocurre hoy.
- Detalle+PDF para Clientes, si se pide más adelante — mismo patrón exacto que Proyectos/Categoría, no incluido aquí (spec §7).
