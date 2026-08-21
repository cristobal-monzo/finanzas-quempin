# Núcleo País + Centro de Costos Perú — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Centro de Costos/Sistema/auditor_centro_costos.py` and its skill operate on either Chile or Perú (parametrized by país, `CL` default), and stand up an empty, working `Centro de Costos Perú.xlsx` fed from a new `Perú/` subfolder inside the existing shared "Facturas y Boletas" folder.

**Architecture:** One shared, country-parametrized codebase (no cloned scripts) — a `PAISES` config dict plus a `configurar_pais(pais)` function that reassigns the module's existing path/format/tax-rate globals at the start of every entry point (`main()`, and each `driver.py` command). Chile's behavior is byte-for-byte unchanged when `pais="CL"` (the default everywhere); Perú is a new, empty, parallel data tree.

**Tech Stack:** Python 3.14, openpyxl 3.1.5, pytest — same as the rest of the repo. No new dependencies.

**Spec:** [`docs/superpowers/specs/2026-08-21-peru-expansion-design.md`](../specs/2026-08-21-peru-expansion-design.md) (master spec — this plan implements only its sub-project 1)

## Global Constraints

- `pais` defaults to `"CL"` everywhere (function signatures, CLI flags) — every existing invocation (`main()`, `driver.py status`, etc.) with no `--pais` must behave **exactly** as it does today. This is the single most important constraint: Centro de Costos Chile is in daily production use with real financial data.
- IGV Perú = **18%** (`tasa_impuesto=0.18`, `nombre_impuesto_corto="IGV"`). IVA Chile stays **19%** (`0.19`), unchanged.
- Perú's currency is **PEN**, symbol **`S/`**. Chile stays **CLP**, symbol **`$`**.
- Perú starts with **zero projects** (`PREFIJOS_PROYECTO = {}`) and **zero documents** — this plan only needs to prove an empty `run` works end-to-end, not register any real document.
- Code is **never duplicated** per country — `Peru/` holds only data (Excel, JSON, backups, logs), never a `.py` file. This is the core decision from the master spec's brainstorming.
- **This entire plan is one deployment unit.** Tasks 1–7 change the code to read "Facturas y Boletas/Chile/" instead of "Facturas y Boletas/" directly. Chile's real `/Registro_Centro_de_Costos run` will break (folder not found) until Task 8 physically moves the real folders. Do not stop, pause across sessions, or consider this plan "done enough for now" between Task 7 and Task 8 — they must land together.
- Cotizador Histórico, Análisis Financiero, the 3 web dashboards, and `/Actualizar_Finanzas` orchestration are **out of scope** (sub-projects 2–5 in the master spec). Where `main()` currently chains into those (PASO 12c/12d), this plan makes Perú skip them gracefully with an `[INFO]` message, not build them.

---

### Task 1: `PAISES` config + `configurar_pais()` + test-isolation fixture

**Files:**
- Modify: `Centro de Costos/Sistema/auditor_centro_costos.py` (lines 44–230, the "CONFIGURACIÓN" section)
- Modify: `Centro de Costos/Sistema/tests/conftest.py`
- Create: `Centro de Costos/Sistema/tests/test_configurar_pais.py`

**Interfaces:**
- Produces: `acc.PAISES` (dict, keys `"CL"`/`"PE"`), `acc.configurar_pais(pais="CL")` (raises `ValueError` for unknown país), `acc.RAIZ_PERU` (Path), and the following globals that `configurar_pais` reassigns: `PAIS_ACTUAL`, `RUTA_EXCEL`, `RAIZ_DOCS`, `RUTA_BACKUPS`, `RUTA_JSON`, `RUTA_RECONCILIACION`, `RUTA_CORRECCIONES`, `RUTA_ERRORES_MD`, `RUTA_LOGS`, `RAIZ_VISUALIZADOR_WEB`, `RUTA_EXCEL_SITIO_COMUNICACION`, `PREFIJOS_PROYECTO`, `MONEDA`, `SIMBOLO_MONEDA`, `NOMBRE_IMPUESTO_CORTO`, `TASA_IMPUESTO`, `NOMBRE_IMPUESTO_PCT`, `ENCABEZADOS_MASTER`, `ENCABEZADOS_DETALLE`, `ENCABEZADOS_PROYECTO`, `MONEY_FORMAT`, `LEYENDA_MASTER`.
- Consumes: nothing yet (later tasks read these globals).

Why this file/line range: every one of these globals is currently a static constant computed once at import time (lines 46–230 of `auditor_centro_costos.py`). This task turns the country-varying ones into values computed by a function, called once at import time with `"CL"` so existing behavior is unchanged by default.

- [ ] **Step 1: Write the failing tests**

Create `Centro de Costos/Sistema/tests/test_configurar_pais.py`:

```python
import auditor_centro_costos as acc


def test_configurar_pais_cl_es_el_default_al_importar():
    assert acc.PAIS_ACTUAL == "CL"
    assert acc.TASA_IMPUESTO == 0.19
    assert acc.NOMBRE_IMPUESTO_CORTO == "IVA"
    assert acc.MONEDA == "CLP"
    assert acc.SIMBOLO_MONEDA == "$"
    assert acc.PREFIJOS_PROYECTO["UMAG"] == "UMAG"
    assert acc.RAIZ_DOCS.name == "Chile"
    assert acc.RUTA_EXCEL.name == "Centro de Costos.xlsx"
    assert acc.MONEY_FORMAT == '"$"#,##0'
    assert acc.ENCABEZADOS_MASTER[10] == "Total sin IVA (CLP)"
    assert acc.ENCABEZADOS_MASTER[11] == "IVA 19% (CLP)"
    assert acc.ENCABEZADOS_DETALLE[8] == "P. Unitario sin IVA"


def test_configurar_pais_pe_cambia_moneda_impuesto_y_rutas():
    acc.configurar_pais("PE")
    try:
        assert acc.PAIS_ACTUAL == "PE"
        assert acc.TASA_IMPUESTO == 0.18
        assert acc.NOMBRE_IMPUESTO_CORTO == "IGV"
        assert acc.MONEDA == "PEN"
        assert acc.SIMBOLO_MONEDA == "S/"
        assert acc.PREFIJOS_PROYECTO == {}
        assert acc.RAIZ_DOCS.name == "Perú"
        assert acc.RUTA_EXCEL.name == "Centro de Costos Perú.xlsx"
        assert acc.RUTA_EXCEL_SITIO_COMUNICACION is None
        assert acc.MONEY_FORMAT == '"S/"#,##0'
        assert acc.ENCABEZADOS_MASTER[10] == "Total sin IGV (PEN)"
        assert acc.ENCABEZADOS_MASTER[11] == "IGV 18% (PEN)"
        assert acc.ENCABEZADOS_DETALLE[8] == "P. Unitario sin IGV"
    finally:
        acc.configurar_pais("CL")


def test_configurar_pais_pais_desconocido_lanza_value_error():
    try:
        acc.configurar_pais("AR")
        assert False, "debia lanzar ValueError"
    except ValueError as e:
        assert "AR" in str(e)
    assert acc.PAIS_ACTUAL == "CL"  # no quedo a medio configurar
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests/test_configurar_pais.py" -v`
Expected: FAIL — `AttributeError: module 'auditor_centro_costos' has no attribute 'PAIS_ACTUAL'` (or similar) for all three tests.

- [ ] **Step 3: Add the autouse país-reset fixture**

`configurar_pais` mutates shared module globals directly (not via `monkeypatch`), so a test that calls `acc.configurar_pais("PE")` and forgets to reset it (or errors before reaching a `finally`) would leak `PE` config into every later test in the same pytest run. Add an autouse fixture so this can never happen silently.

Edit `Centro de Costos/Sistema/tests/conftest.py` — replace the entire file content with:

```python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _resetear_pais_activo():
    """auditor_centro_costos.configurar_pais() muta globals compartidos del
    modulo (no via monkeypatch), asi que un test que llame configurar_pais('PE')
    y no la restaure explicitamente (o falle antes de un finally) dejaria ese
    estado filtrado a los tests siguientes. Este fixture autouse garantiza
    'CL' al empezar y al terminar cada test, sin que cada test tenga que
    acordarse."""
    import auditor_centro_costos as acc
    acc.configurar_pais("CL")
    yield
    acc.configurar_pais("CL")
```

- [ ] **Step 4: Replace the CONFIGURACIÓN section in `auditor_centro_costos.py`**

Find this exact block (starts at line 44):

```python
# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────

RAIZ = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ.parent
# Desde 2026-07-17 la fuente oficial de documentos es el acceso directo de
# OneDrive "Sitio de comunicacion - Centro de Costos 1" (carpeta compartida
# donde suben facturas/boletas los colegas), no la carpeta local "Facturas y
# Boletas/" -- ver CLAUDE.md seccion "Sitio de comunicacion".
RAIZ_SITIO_COMUNICACION = RAIZ_MODULO / "Sitio de comunicación - Centro de Costos 1"
RAIZ_DOCS = RAIZ_SITIO_COMUNICACION / "Facturas y Boletas"
RUTA_EXCEL = RAIZ_MODULO / "Excel" / "Centro de Costos.xlsx"
RUTA_EXCEL_SITIO_COMUNICACION = RAIZ_SITIO_COMUNICACION / "Centro de Costos.xlsx"
RUTA_JSON = RAIZ / "datos_extraidos.json"
RUTA_RECONCILIACION = RAIZ / "reconciliacion_archivos.json"
RUTA_BACKUPS = RAIZ_MODULO / "Excel" / "Respaldos"
RUTA_CORRECCIONES = RAIZ / "correcciones_manuales.json"
RUTA_ERRORES_MD = RAIZ_MODULO / ".claude" / "skills" / "Registro_Centro_de_Costos" / "ERRORES.md"
RUTA_LOGS = RAIZ / "logs"
RAIZ_VISUALIZADOR_WEB = RAIZ_MODULO / "Visualizador Web"
RAIZ_ANALISIS_FINANCIERO = RAIZ_MODULO.parent / "Sistema Analisis Financiero"

PREFIJOS_PROYECTO = {
    "UMAG": "UMAG",
    "Cesfam Limache": "CFLI",
    "Cesfam Constitución": "CCON",
    "Gastos Generales": "GGEN",
    "Microturbina LER": "MLER",
    "Fiscalía Quilpué y Quintero": "FQYQ",
    "ESFOCAR": "ESFO",
    "CONAF Puerto Montt": "CPMO",
    "Bomba Wilo Conchalí": "BWIL",
    "CESFAM Chillán": "CCHI",
    "Caldera Valdivia": "CVAL",
    "Calderas Antofagasta": "CANT",
    "Comisaría Conchalí": "COMC",
    "Cremación Concepción": "CREM",
}
```

Replace it with:

```python
# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────

RAIZ = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ.parent
# Desde 2026-07-17 la fuente oficial de documentos es el acceso directo de
# OneDrive "Sitio de comunicacion - Centro de Costos 1" (carpeta compartida
# donde suben facturas/boletas los colegas), no la carpeta local "Facturas y
# Boletas/" -- ver CLAUDE.md seccion "Sitio de comunicacion".
RAIZ_SITIO_COMUNICACION = RAIZ_MODULO / "Sitio de comunicación - Centro de Costos 1"
# Carpeta COMPARTIDA por ambos paises (desde 2026-08-21): contiene las
# subcarpetas "Chile/" y "Perú/", cada una con sus carpetas de proyecto
# adentro -- ver docs/superpowers/specs/2026-08-21-peru-expansion-design.md.
# RAIZ_DOCS (mas abajo, mutable) es la version YA resuelta para el pais activo.
RAIZ_DOCS_BASE = RAIZ_SITIO_COMUNICACION / "Facturas y Boletas"
RUTA_EXCEL = RAIZ_MODULO / "Excel" / "Centro de Costos.xlsx"
RUTA_EXCEL_SITIO_COMUNICACION = RAIZ_SITIO_COMUNICACION / "Centro de Costos.xlsx"
RUTA_JSON = RAIZ / "datos_extraidos.json"
RUTA_RECONCILIACION = RAIZ / "reconciliacion_archivos.json"
RUTA_BACKUPS = RAIZ_MODULO / "Excel" / "Respaldos"
RUTA_CORRECCIONES = RAIZ / "correcciones_manuales.json"
RUTA_ERRORES_MD = RAIZ_MODULO / ".claude" / "skills" / "Registro_Centro_de_Costos" / "ERRORES.md"
RUTA_LOGS = RAIZ / "logs"
RAIZ_VISUALIZADOR_WEB = RAIZ_MODULO / "Visualizador Web"
RAIZ_ANALISIS_FINANCIERO = RAIZ_MODULO.parent / "Sistema Analisis Financiero"
# Perú no tiene codigo propio (ver spec maestro): solo aloja Excel/respaldos/
# JSON/dashboards. El codigo de arriba (este archivo) es compartido.
RAIZ_PERU = RAIZ_MODULO.parent / "Peru" / "Centro de Costos"

PREFIJOS_PROYECTO = {
    "UMAG": "UMAG",
    "Cesfam Limache": "CFLI",
    "Cesfam Constitución": "CCON",
    "Gastos Generales": "GGEN",
    "Microturbina LER": "MLER",
    "Fiscalía Quilpué y Quintero": "FQYQ",
    "ESFOCAR": "ESFO",
    "CONAF Puerto Montt": "CPMO",
    "Bomba Wilo Conchalí": "BWIL",
    "CESFAM Chillán": "CCHI",
    "Caldera Valdivia": "CVAL",
    "Calderas Antofagasta": "CANT",
    "Comisaría Conchalí": "COMC",
    "Cremación Concepción": "CREM",
}

# Config por pais -- moneda/impuesto/rutas que varian entre Chile y Peru.
# Los valores de "CL" son literalmente las constantes de arriba (cero cambio
# de comportamiento); "PE" son las mismas rutas dentro de Peru/Centro de
# Costos/ (sin codigo propio, ver RAIZ_PERU) mas IGV 18% y soles.
PAISES = {
    "CL": {
        "moneda": "CLP", "simbolo": "$",
        "nombre_impuesto_corto": "IVA", "tasa_impuesto": 0.19,
        "ruta_excel": RUTA_EXCEL,
        "ruta_docs": RAIZ_DOCS_BASE / "Chile",
        "ruta_backups": RUTA_BACKUPS,
        "ruta_json": RUTA_JSON,
        "ruta_reconciliacion": RUTA_RECONCILIACION,
        "ruta_correcciones": RUTA_CORRECCIONES,
        "ruta_errores_md": RUTA_ERRORES_MD,
        "ruta_logs": RUTA_LOGS,
        "ruta_visualizador_web": RAIZ_VISUALIZADOR_WEB,
        "ruta_excel_sitio_comunicacion": RUTA_EXCEL_SITIO_COMUNICACION,
        "prefijos_proyecto": PREFIJOS_PROYECTO,
    },
    "PE": {
        "moneda": "PEN", "simbolo": "S/",
        "nombre_impuesto_corto": "IGV", "tasa_impuesto": 0.18,
        "ruta_excel": RAIZ_PERU / "Excel" / "Centro de Costos Perú.xlsx",
        "ruta_docs": RAIZ_DOCS_BASE / "Perú",
        "ruta_backups": RAIZ_PERU / "Excel" / "Respaldos",
        "ruta_json": RAIZ_PERU / "datos_extraidos_peru.json",
        "ruta_reconciliacion": RAIZ_PERU / "reconciliacion_archivos_peru.json",
        "ruta_correcciones": RAIZ_PERU / "correcciones_manuales_peru.json",
        "ruta_errores_md": (
            RAIZ_MODULO / ".claude" / "skills" / "Registro_Centro_de_Costos" / "ERRORES_PERU.md"
        ),
        "ruta_logs": RAIZ_PERU / "logs",
        "ruta_visualizador_web": RAIZ_PERU / "Visualizador Web",
        # Peru no tiene (todavia) un sitio de comunicacion SharePoint propio.
        "ruta_excel_sitio_comunicacion": None,
        "prefijos_proyecto": {},
    },
}


def configurar_pais(pais="CL"):
    """Reconfigura las rutas/constantes globales del modulo para operar sobre
    el pais pedido -- 'CL' (Chile, default, preserva el comportamiento actual)
    o 'PE' (Peru). Debe llamarse ANTES de cualquier otra funcion del modulo
    que dependa de estas rutas -- main() ya lo hace como primer paso (ver
    PASO 0), y cada comando de driver.py lo hace antes de tocar acc.* .
    Lanza ValueError si 'pais' no esta en PAISES, sin dejar el modulo a medio
    configurar (se valida antes de reasignar nada)."""
    if pais not in PAISES:
        raise ValueError(f"País desconocido: {pais!r}. Usar uno de {sorted(PAISES)}.")

    global PAIS_ACTUAL, RUTA_EXCEL, RAIZ_DOCS, RUTA_BACKUPS, RUTA_JSON
    global RUTA_RECONCILIACION, RUTA_CORRECCIONES, RUTA_ERRORES_MD, RUTA_LOGS
    global RAIZ_VISUALIZADOR_WEB, RUTA_EXCEL_SITIO_COMUNICACION, PREFIJOS_PROYECTO
    global MONEDA, SIMBOLO_MONEDA, NOMBRE_IMPUESTO_CORTO, TASA_IMPUESTO, NOMBRE_IMPUESTO_PCT
    global ENCABEZADOS_MASTER, ENCABEZADOS_DETALLE, ENCABEZADOS_PROYECTO
    global MONEY_FORMAT, LEYENDA_MASTER

    cfg = PAISES[pais]
    PAIS_ACTUAL = pais
    RUTA_EXCEL = cfg["ruta_excel"]
    RAIZ_DOCS = cfg["ruta_docs"]
    RUTA_BACKUPS = cfg["ruta_backups"]
    RUTA_JSON = cfg["ruta_json"]
    RUTA_RECONCILIACION = cfg["ruta_reconciliacion"]
    RUTA_CORRECCIONES = cfg["ruta_correcciones"]
    RUTA_ERRORES_MD = cfg["ruta_errores_md"]
    RUTA_LOGS = cfg["ruta_logs"]
    RAIZ_VISUALIZADOR_WEB = cfg["ruta_visualizador_web"]
    RUTA_EXCEL_SITIO_COMUNICACION = cfg["ruta_excel_sitio_comunicacion"]
    PREFIJOS_PROYECTO = cfg["prefijos_proyecto"]

    MONEDA = cfg["moneda"]
    SIMBOLO_MONEDA = cfg["simbolo"]
    NOMBRE_IMPUESTO_CORTO = cfg["nombre_impuesto_corto"]
    TASA_IMPUESTO = cfg["tasa_impuesto"]
    NOMBRE_IMPUESTO_PCT = f"{NOMBRE_IMPUESTO_CORTO} {round(TASA_IMPUESTO * 100)}%"

    ENCABEZADOS_MASTER = [
        "N° Ref.", "Proyecto", "Tipo de Proyecto", "Fecha", "N° Documento",
        "Tipo Documento", "Proveedor", "Proveedor (Razón Social)", "Categoría",
        "Resumen Ítems", f"Total sin {NOMBRE_IMPUESTO_CORTO} ({MONEDA})",
        f"{NOMBRE_IMPUESTO_PCT} ({MONEDA})",
        f"Total con {NOMBRE_IMPUESTO_CORTO} ({MONEDA})", "Estado", "Archivo origen",
        "Fecha modificación",
    ]
    ENCABEZADOS_DETALLE = [
        "N° Ref.", "Proyecto", "Tipo de Proyecto", "N° Documento", "Nombre Ítem",
        "Descripción", "Categoría Ítem", "Cantidad",
        f"P. Unitario sin {NOMBRE_IMPUESTO_CORTO}",
        f"Total sin {NOMBRE_IMPUESTO_CORTO} ({MONEDA})",
        f"Total con {NOMBRE_IMPUESTO_CORTO} ({MONEDA})",
    ]
    ENCABEZADOS_PROYECTO = [
        "N° Ref.", "Proyecto", "Tipo de Proyecto", "Fecha", "N° Documento",
        "Tipo Documento", "Proveedor", "Proveedor (Razón Social)", "Categoría",
        "Resumen Ítems", f"Total sin {NOMBRE_IMPUESTO_CORTO} ({MONEDA})",
        f"Total con {NOMBRE_IMPUESTO_CORTO} ({MONEDA})", "Estado",
    ]
    MONEY_FORMAT = f'"{SIMBOLO_MONEDA}"#,##0'
    LEYENDA_MASTER = [
        "Cursiva = celda editable a mano",
        "Rojo = valor que requiere revisión (pasa el cursor por la celda para ver el motivo)",
        "Azul marino = valor corregido a mano por ti (Claude lo respeta y no lo sobreescribe)",
        "Fondo de color = proyecto (se pinta solo según la columna 'Proyecto'; si la cambias, "
        "el color se actualiza) · la foto de cada documento lleva su N° como nombre de archivo",
        f"⚠️ 'Total sin {NOMBRE_IMPUESTO_CORTO}' y 'Total con {NOMBRE_IMPUESTO_CORTO}' se calculan "
        "desde Detalle. 'Archivo origen' y 'Fecha modificación' son el registro de lo ya "
        "procesado: no editar.",
    ]
```

Then find this line further down (originally ~line 168, right before `ENCABEZADOS_PROYECTO`'s old definition — it no longer exists as a static block, so instead find the now-adjacent):

```python
# Columna (1-indexada) de "Proveedor (Razón Social)" en Master y en las hojas
```

and confirm the **old** static blocks that used to sit between `ENCABEZADOS_DETALLE` and this comment (old `ENCABEZADOS_PROYECTO`) and between `LEYENDA_DETALLE`'s block and `PATRON_NREF` (old `LEYENDA_MASTER`) are gone (they were absorbed into `configurar_pais` above) — `LEYENDA_DETALLE`, `LEYENDA_PROYECTO`, `PATRON_NREF`, `NAVY`/colors/fonts, `CAMPOS_PROPAGADOS_A_DETALLE`, `DATE_FORMAT`, `THIN_BORDER` all stay exactly as they were (no IVA/currency dependency). Find this exact remaining line (old line 223):

```python
MONEY_FORMAT = '"$"#,##0'
```

Delete that single line (it's now set inside `configurar_pais`) — leave the blank line and `DATE_FORMAT = "DD-MM-YYYY"` etc. around it untouched.

Finally, add the bootstrap call. Find the end of the "UTILIDADES DE FORMATO" section marker:

```python
# ── UTILIDADES DE FORMATO ────────────────────────────────────────────────────
```

Insert **immediately before** this line (i.e., right after the block from Step 4 above, before any function definitions):

```python
configurar_pais("CL")  # valores por defecto al importar -- ver docstring de configurar_pais()


```

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests/test_configurar_pais.py" -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Run the full existing Centro de Costos suite to check for regressions**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests" -v`
Expected: PASS — all tests that existed before this task still pass unchanged, since `configurar_pais("CL")` at import time reproduces the exact same constants as before.

- [ ] **Step 7: Commit**

```bash
git add "Centro de Costos/Sistema/auditor_centro_costos.py" "Centro de Costos/Sistema/tests/conftest.py" "Centro de Costos/Sistema/tests/test_configurar_pais.py"
git commit -m "feat(centro-de-costos): agregar configurar_pais() para soportar CL/PE"
```

---

### Task 2: Country-aware tax rate in the arithmetic checks

**Files:**
- Modify: `Centro de Costos/Sistema/auditor_centro_costos.py` (functions `calcular_iva_documento`, `escribir_fila_master`, `verificar_aritmetica`, and the print label in `main()`)
- Create: `Centro de Costos/Sistema/tests/test_verificar_aritmetica_pais.py`

**Interfaces:**
- Consumes: `TASA_IMPUESTO`, `NOMBRE_IMPUESTO_PCT` (globals from Task 1).
- Produces: `calcular_iva_documento`/`verificar_aritmetica` now compute against whichever país is active instead of a hardcoded `0.19`.

There are exactly three hardcoded `0.19` occurrences to fix (found by reading the full file — no others exist).

- [ ] **Step 1: Write the failing test**

Create `Centro de Costos/Sistema/tests/test_verificar_aritmetica_pais.py`:

```python
import auditor_centro_costos as acc


def _doc(tipo_documento, iva, items, **extra):
    d = {"archivo": "IMG_1.jpg", "n_documento": "123",
         "tipo_documento": tipo_documento, "iva": iva, "items": items}
    d.update(extra)
    return d


def test_verificar_aritmetica_usa_18_por_ciento_para_pe():
    acc.configurar_pais("PE")
    try:
        # 100000 * 0.18 = 18000 -- correcto para Peru, pero NO para el 19% de Chile.
        doc = _doc("Factura", iva=18000, items=[{"cantidad": 1, "p_unitario_sin_iva": 100000}])
        assert acc.verificar_aritmetica([doc]) == []

        doc_mal = _doc("Factura", iva=19000, items=[{"cantidad": 1, "p_unitario_sin_iva": 100000}])
        inconsistencias = acc.verificar_aritmetica([doc_mal])
        assert len(inconsistencias) == 1
        assert inconsistencias[0]["iva_esperado"] == 18000
    finally:
        acc.configurar_pais("CL")


def test_calcular_iva_documento_usa_tasa_activa():
    acc.configurar_pais("PE")
    try:
        dato = {"tipo_documento": "Factura"}
        assert acc.calcular_iva_documento(dato, 100000) == 18000
    finally:
        acc.configurar_pais("CL")


def test_calcular_iva_documento_sigue_dando_19_por_ciento_para_cl():
    dato = {"tipo_documento": "Factura"}
    assert acc.calcular_iva_documento(dato, 100000) == 19000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests/test_verificar_aritmetica_pais.py" -v`
Expected: FAIL — the PE assertions get 19% results (18000 expected vs 19000 computed) since the code still hardcodes `0.19`.

- [ ] **Step 3: Fix the three hardcodes**

In `calcular_iva_documento`, find:

```python
    iva = dato.get("iva")
    if iva is None:
        iva = round(total_sin_iva * 0.19) if dato.get("tipo_documento") in ("Factura", "Guía de Despacho") else 0
    return iva
```

Replace with:

```python
    iva = dato.get("iva")
    if iva is None:
        iva = (
            round(total_sin_iva * TASA_IMPUESTO)
            if dato.get("tipo_documento") in ("Factura", "Guía de Despacho") else 0
        )
    return iva
```

In `escribir_fila_master`, find:

```python
    if dato.get("tipo_documento") in ("Factura", "Guía de Despacho") and total_sin_iva > 0:
        esperado = round(total_sin_iva * 0.19)
        if abs(iva - esperado) > 1:
            iva_cell.font = ROJO_FONT
```

Replace with:

```python
    if dato.get("tipo_documento") in ("Factura", "Guía de Despacho") and total_sin_iva > 0:
        esperado = round(total_sin_iva * TASA_IMPUESTO)
        if abs(iva - esperado) > 1:
            iva_cell.font = ROJO_FONT
```

In `verificar_aritmetica`, find:

```python
        if d.get("tipo_documento") in ("Factura", "Guía de Despacho") and total_sin_iva > 0:
            esperado = round(total_sin_iva * 0.19)
```

Replace with:

```python
        if d.get("tipo_documento") in ("Factura", "Guía de Despacho") and total_sin_iva > 0:
            esperado = round(total_sin_iva * TASA_IMPUESTO)
```

In `main()`, find:

```python
    print("\n2. INCONSISTENCIAS ARITMETICAS (Neto vs IVA 19%)")
```

Replace with:

```python
    print(f"\n2. INCONSISTENCIAS ARITMETICAS (Neto vs {NOMBRE_IMPUESTO_PCT})")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests/test_verificar_aritmetica_pais.py" "Centro de Costos/Sistema/tests/test_verificar_aritmetica.py" -v`
Expected: PASS — both the new PE tests and the existing CL tests (`test_verificar_aritmetica.py`, untouched, still expects 19%/CL default) pass.

- [ ] **Step 5: Run the full suite**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add "Centro de Costos/Sistema/auditor_centro_costos.py" "Centro de Costos/Sistema/tests/test_verificar_aritmetica_pais.py"
git commit -m "fix(centro-de-costos): usar TASA_IMPUESTO activa en vez de 19% fijo"
```

---

### Task 3: Fix the "Total con IVA" migration guard to compare dynamically

**Files:**
- Modify: `Centro de Costos/Sistema/auditor_centro_costos.py` (function `migrar_columna_total_con_iva_detalle`)
- Modify: `Centro de Costos/Sistema/tests/test_migraciones_unicas.py`

**Interfaces:**
- Consumes: `ENCABEZADOS_DETALLE[10]` (the "Total con {impuesto} (moneda)" header, from Task 1).

Why: this migration's guard currently checks `ws_detalle.cell(row=1, column=11).value == "Total con IVA (CLP)"` — a hardcoded Chile literal. A brand-new Perú workbook created by `main()` already has the correct Perú header (`"Total con IGV (PEN)"`) at column 11 from the moment the sheet is created, but this guard would never match it, and would silently overwrite the correct Perú header with the wrong Chilean one every single run.

- [ ] **Step 1: Write the failing test**

Add to `Centro de Costos/Sistema/tests/test_migraciones_unicas.py` (append at the end of the file):

```python
def test_migrar_total_con_iva_es_no_op_si_encabezado_ya_es_el_del_pais_activo(tmp_path):
    import openpyxl

    acc.configurar_pais("PE")
    try:
        wb = openpyxl.Workbook()
        ws_master = wb.active
        ws_master.title = "Master"
        ws_detalle = wb.create_sheet("Detalle")
        for c, h in enumerate(acc.ENCABEZADOS_DETALLE, 1):
            ws_detalle.cell(row=1, column=c, value=h)

        acc.migrar_columna_total_con_iva_detalle(ws_master, ws_detalle)

        # Header sigue siendo el de Peru -- no se piso con el literal chileno.
        assert ws_detalle.cell(row=1, column=11).value == "Total con IGV (PEN)"
    finally:
        acc.configurar_pais("CL")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests/test_migraciones_unicas.py::test_migrar_total_con_iva_es_no_op_si_encabezado_ya_es_el_del_pais_activo" -v`
Expected: FAIL — the function overwrites column 11 with the literal `"Total con IVA (CLP)"`, so the assertion `== "Total con IGV (PEN)"` fails.

- [ ] **Step 3: Fix the guard**

In `migrar_columna_total_con_iva_detalle`, find:

```python
    if ws_detalle.cell(row=1, column=11).value == "Total con IVA (CLP)":
        return

    print("  Migrando Detalle: agregando columna 'Total con IVA (CLP)'...")
    header_cell = ws_detalle.cell(row=1, column=11, value="Total con IVA (CLP)")
```

Replace with:

```python
    encabezado_esperado = ENCABEZADOS_DETALLE[10]
    if ws_detalle.cell(row=1, column=11).value == encabezado_esperado:
        return

    print(f"  Migrando Detalle: agregando columna '{encabezado_esperado}'...")
    header_cell = ws_detalle.cell(row=1, column=11, value=encabezado_esperado)
```

And find the final print statement in the same function:

```python
    print(f"  [OK] {rellenadas} fila(s) de Detalle con 'Total con IVA (CLP)' calculado.")
```

Replace with:

```python
    print(f"  [OK] {rellenadas} fila(s) de Detalle con '{encabezado_esperado}' calculado.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests/test_migraciones_unicas.py" -v`
Expected: PASS — including the pre-existing tests in this file (unaffected, since CL's `ENCABEZADOS_DETALLE[10]` is still exactly `"Total con IVA (CLP)"`).

- [ ] **Step 5: Run the full suite**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add "Centro de Costos/Sistema/auditor_centro_costos.py" "Centro de Costos/Sistema/tests/test_migraciones_unicas.py"
git commit -m "fix(centro-de-costos): comparar encabezado dinamico en migracion Total con IVA/IGV"
```

---

### Task 4: Wire `main(pais=...)` end-to-end

**Files:**
- Modify: `Centro de Costos/Sistema/auditor_centro_costos.py` (functions `main`, `reflejar_a_sitio_comunicacion`)
- Create: `Centro de Costos/Sistema/tests/test_main_pais.py`

**Interfaces:**
- Consumes: `configurar_pais` (Task 1), `TASA_IMPUESTO`/`NOMBRE_IMPUESTO_PCT` (Task 2).
- Produces: `main(pais="CL")` — first line calls `configurar_pais(pais)`.

Two call sites inside `main()` rely on **stale-bound default arguments** (`hacer_backup(ruta_excel, ruta_backups=RUTA_BACKUPS)` and `backup_mas_reciente(ruta_backups=RUTA_BACKUPS)` — Python binds `=RUTA_BACKUPS` once at module-load time, so reassigning the global later does **not** change these functions' own defaults). `main()` must pass the current global explicitly at the call site instead of relying on the default.

- [ ] **Step 1: Write the failing test**

Create `Centro de Costos/Sistema/tests/test_main_pais.py`:

```python
from pathlib import Path

import openpyxl

import auditor_centro_costos as acc


def test_main_pe_corre_sin_errores_sobre_arbol_vacio(tmp_path, monkeypatch, capsys):
    """Simula un arbol de carpetas Peru completamente vacio (0 proyectos, 0
    documentos, JSON vacio) y verifica que main(pais='PE') lo procesa sin
    lanzar excepciones, guarda un Excel con los encabezados de Peru, y no
    intenta actualizar el sitio de comunicacion (Peru no tiene uno).

    IMPORTANTE: main(pais="PE") llama configurar_pais("PE") como su PRIMERA
    linea -- eso pisaria cualquier monkeypatch.setattr(acc, "RUTA_EXCEL", ...)
    hecho ANTES de esta llamada. Por eso este test parchea el diccionario
    PAISES["PE"] (via monkeypatch.setitem, que se revierte solo al terminar
    el test) en vez de los globals directamente -- asi configurar_pais("PE")
    resuelve exactamente a estas rutas de tmp_path cuando main() la invoque."""
    raiz_docs = tmp_path / "Facturas" / "Perú"
    raiz_docs.mkdir(parents=True)
    (tmp_path / "Excel").mkdir()  # wb.save() no crea el directorio padre solo
    ruta_excel = tmp_path / "Excel" / "Centro de Costos Perú.xlsx"
    ruta_backups = tmp_path / "Excel" / "Respaldos"
    ruta_json = tmp_path / "datos_extraidos_peru.json"
    ruta_json.write_text("[]", encoding="utf-8")
    ruta_logs = tmp_path / "logs"

    pe_cfg = dict(acc.PAISES["PE"])
    pe_cfg["ruta_docs"] = raiz_docs
    pe_cfg["ruta_excel"] = ruta_excel
    pe_cfg["ruta_backups"] = ruta_backups
    pe_cfg["ruta_json"] = ruta_json
    pe_cfg["ruta_reconciliacion"] = tmp_path / "reconciliacion_archivos_peru.json"
    pe_cfg["ruta_logs"] = ruta_logs
    pe_cfg["ruta_excel_sitio_comunicacion"] = None
    pe_cfg["ruta_visualizador_web"] = tmp_path / "Visualizador Web"
    monkeypatch.setitem(acc.PAISES, "PE", pe_cfg)

    acc.main(pais="PE")

    salida = capsys.readouterr().out
    assert "No se pudo actualizar la copia en Sitio de comunicacion" not in salida
    assert ruta_excel.exists()

    wb = openpyxl.load_workbook(str(ruta_excel))
    assert wb["Master"].cell(row=1, column=11).value == "Total sin IGV (PEN)"
    assert wb["Master"].cell(row=1, column=12).value == "IGV 18% (PEN)"


def test_main_sin_argumentos_sigue_siendo_chile(monkeypatch):
    """main() sin argumentos (la firma que usa hoy driver.py 'run') debe
    seguir apuntando a Chile -- no debe requerir pasar pais explicitamente."""
    llamadas = []
    monkeypatch.setattr(acc, "configurar_pais", lambda pais="CL": llamadas.append(pais))
    # Forzamos que falle temprano (carpeta no existe) para no ejecutar main()
    # completo -- solo nos interesa que configurar_pais("CL") se haya llamado.
    monkeypatch.setattr(acc, "RAIZ_DOCS", Path("Z:/no-existe-de-verdad"))
    acc.main()
    assert llamadas == ["CL"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests/test_main_pais.py" -v`
Expected: FAIL — `main()` doesn't accept a `pais` keyword argument yet (`TypeError: main() got an unexpected keyword argument 'pais'`).

- [ ] **Step 3: Fix `reflejar_a_sitio_comunicacion` to skip gracefully when there's no site configured**

Find:

```python
def reflejar_a_sitio_comunicacion(ruta_excel=None, ruta_sitio=None):
    """Copia (shutil.copy2) el Excel local encima de la copia de solo lectura
    en 'Sitio de comunicacion - Centro de Costos 1/' -- mismo paso que hace
    'run' (PASO 12b) al final de cada corrida. Factorizado para que tambien
    lo puedan llamar comandos que no pasan por main(), como el driver de la
    skill Revision_de_Errores (corregir/desglosar solo tocan el Excel local;
    sin este paso aparte, la copia compartida queda desactualizada). No falla
    si el destino esta bloqueado, solo advierte -- igual que en 'run'.
    Devuelve True si la copia se actualizo, False si no se pudo."""
    ruta_excel = ruta_excel or RUTA_EXCEL
    ruta_sitio = ruta_sitio or RUTA_EXCEL_SITIO_COMUNICACION
    try:
```

Replace with:

```python
def reflejar_a_sitio_comunicacion(ruta_excel=None, ruta_sitio=None):
    """Copia (shutil.copy2) el Excel local encima de la copia de solo lectura
    en 'Sitio de comunicacion - Centro de Costos 1/' -- mismo paso que hace
    'run' (PASO 12b) al final de cada corrida. Factorizado para que tambien
    lo puedan llamar comandos que no pasan por main(), como el driver de la
    skill Revision_de_Errores (corregir/desglosar solo tocan el Excel local;
    sin este paso aparte, la copia compartida queda desactualizada). No falla
    si el destino esta bloqueado, solo advierte -- igual que en 'run'.
    Perú no tiene (todavía) un sitio de comunicación propio configurado
    (ruta_sitio resuelve a None): en ese caso se omite con un [INFO], no se
    intenta copiar a un destino inexistente. Devuelve True si la copia se
    actualizo, False si no se pudo o no aplica."""
    ruta_excel = ruta_excel or RUTA_EXCEL
    ruta_sitio = ruta_sitio if ruta_sitio is not None else RUTA_EXCEL_SITIO_COMUNICACION
    if ruta_sitio is None:
        print("  [INFO] Sin sitio de comunicación configurado para este país -- paso omitido.")
        return False
    try:
```

- [ ] **Step 4: Change `main()`'s signature and gate the two cross-module steps by país**

Find:

```python
def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    print("=" * 70)
    print("  REGISTRO CENTRO DE COSTOS - QUEMPIN SpA")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    ruta_log_run = RUTA_LOGS / f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
```

Replace with:

```python
def main(pais="CL"):
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    configurar_pais(pais)

    print("=" * 70)
    print("  REGISTRO CENTRO DE COSTOS - QUEMPIN SpA")
    print(f"  País: {pais} | Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    ruta_log_run = RUTA_LOGS / f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
```

Find:

```python
    print("\n--- PASO 1: Backup ---")
    ruta_backup_anterior = backup_mas_reciente()
    hacer_backup(RUTA_EXCEL)
```

Replace with (explicit `ruta_backups=` beats the two functions' stale-bound `=RUTA_BACKUPS` defaults):

```python
    print("\n--- PASO 1: Backup ---")
    ruta_backup_anterior = backup_mas_reciente(ruta_backups=RUTA_BACKUPS)
    hacer_backup(RUTA_EXCEL, ruta_backups=RUTA_BACKUPS)
```

Find:

```python
    print("\n--- PASO 12c: Actualizar visualizador web ---")
    actualizar_visualizador()

    print("\n--- PASO 12d: Actualizar Análisis Financiero ---")
    actualizar_analisis_financiero()
```

Replace with:

```python
    print("\n--- PASO 12c: Actualizar visualizador web ---")
    if RAIZ_VISUALIZADOR_WEB.exists():
        actualizar_visualizador()
    else:
        print(f"  [INFO] Visualizador Web de {pais} aún no implementado -- paso omitido.")

    print("\n--- PASO 12d: Actualizar Análisis Financiero ---")
    if pais == "CL":
        actualizar_analisis_financiero()
    else:
        print(f"  [INFO] Análisis Financiero de {pais} aún no implementado -- paso omitido.")
```

(`actualizar_visualizador()` itself already no-ops gracefully with a `[WARN]` if `build_visualizador.py` doesn't exist — the `RAIZ_VISUALIZADOR_WEB.exists()` guard here just avoids creating an empty `Visualizador Web/` directory check crashing when the parent `Peru/Centro de Costos/` tree doesn't exist yet either, and gives a clearer `[INFO]` instead of `[WARN]` for the expected "not built yet" case.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests/test_main_pais.py" -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Update the `if __name__ == "__main__":` tail to accept `--pais`**

Find (end of file):

```python
if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == "--confirmar":
        resto = _sys.argv[2:]
        if not resto:
            confirmar_correcciones(None)
        elif resto == ["--todos"]:
            confirmar_correcciones("TODOS")
        else:
            confirmar_correcciones(resto)
    else:
```

Read the next few lines to find the `else:` branch's body (the final line of the file, likely `main()`) and replace that specific call. Find:

```python
    else:
        main()
```

Replace with:

```python
    else:
        _pais = "CL"
        if "--pais" in _sys.argv:
            _idx = _sys.argv.index("--pais")
            _pais = _sys.argv[_idx + 1]
        main(pais=_pais)
```

- [ ] **Step 7: Run the full suite**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests" -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add "Centro de Costos/Sistema/auditor_centro_costos.py" "Centro de Costos/Sistema/tests/test_main_pais.py"
git commit -m "feat(centro-de-costos): main(pais=...) end-to-end, gatea AF/visualizador no implementados"
```

---

### Task 5: `driver.py` `--pais` support

**Files:**
- Modify: `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py`
- Create: `Centro de Costos/Sistema/tests/test_driver_pais_arg.py`

**Interfaces:**
- Consumes: `acc.configurar_pais`, `acc.main(pais=...)`, `acc.RAIZ_VISUALIZADOR_WEB` (all from Tasks 1 & 4).

- [ ] **Step 1: Write the failing test**

Create `Centro de Costos/Sistema/tests/test_driver_pais_arg.py` (same import convention as `test_driver_preview_renombrados.py`):

```python
import importlib.util
import sys
from pathlib import Path

import auditor_centro_costos as acc

_DRIVER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".claude" / "skills" / "Registro_Centro_de_Costos" / "driver.py"
)
_spec = importlib.util.spec_from_file_location("driver_bajo_prueba", _DRIVER_PATH)
driver = importlib.util.module_from_spec(_spec)
sys.modules["driver_bajo_prueba"] = driver
_spec.loader.exec_module(driver)


def test_extraer_pais_default_es_cl():
    pais, resto = driver._extraer_pais(["status"])
    assert pais == "CL"
    assert resto == ["status"]


def test_extraer_pais_detecta_flag_en_cualquier_posicion():
    pais, resto = driver._extraer_pais(["confirmar", "--pais", "PE", "--todos"])
    assert pais == "PE"
    assert resto == ["confirmar", "--todos"]


def test_cmd_status_con_pais_pe_usa_rutas_de_peru(tmp_path, monkeypatch, capsys):
    # cmd_status(pais="PE") llama acc.configurar_pais("PE") como primera linea,
    # que PISA cualquier monkeypatch.setattr(acc, "RAIZ_DOCS", ...) hecho antes
    # de la llamada -- hay que parchear el DICCIONARIO PAISES["PE"] en vez de
    # los globals, para que configurar_pais() resuelva a rutas de tmp_path.
    raiz_docs = tmp_path / "Facturas" / "Perú"
    raiz_docs.mkdir(parents=True)
    ruta_json = tmp_path / "datos_extraidos_peru.json"
    ruta_json.write_text("[]", encoding="utf-8")

    pe_cfg = dict(acc.PAISES["PE"])
    pe_cfg["ruta_docs"] = raiz_docs
    pe_cfg["ruta_json"] = ruta_json
    pe_cfg["ruta_excel"] = tmp_path / "Centro de Costos Perú.xlsx"  # no existe -- cmd_status lo tolera
    pe_cfg["ruta_reconciliacion"] = tmp_path / "reconciliacion_archivos_peru.json"
    pe_cfg["ruta_backups"] = tmp_path / "Respaldos"
    monkeypatch.setitem(acc.PAISES, "PE", pe_cfg)

    driver.cmd_status(pais="PE")

    salida = capsys.readouterr().out
    assert "IGV 18%" in salida
    assert acc.PAIS_ACTUAL == "CL"  # el fixture autouse ya lo restauro para el proximo test


def test_cmd_status_consulta_backups_del_pais_activo_no_los_de_cl(tmp_path, monkeypatch, capsys):
    """cmd_status() llama acc.backup_mas_reciente() SIN pasar ruta_backups
    explicito -- ese parametro tiene un default (=RUTA_BACKUPS) atado en
    tiempo de definicion (modulo Chile), asi que si el call site no lo pasa
    explicito, seguiria mirando SIEMPRE la carpeta de respaldos de Chile
    aunque configurar_pais('PE') ya haya corrido. Este test detecta esa
    regresion poniendo un backup falso SOLO en la carpeta de Peru."""
    raiz_docs = tmp_path / "Facturas" / "Perú"
    raiz_docs.mkdir(parents=True)
    ruta_json = tmp_path / "datos_extraidos_peru.json"
    ruta_json.write_text("[]", encoding="utf-8")
    respaldos_pe = tmp_path / "Respaldos Peru"
    carpeta_mes = respaldos_pe / "Enero 2026"
    carpeta_mes.mkdir(parents=True)
    (carpeta_mes / "Centro de Costos - backup 2026-01-01 0000.xlsx").write_bytes(b"x")

    pe_cfg = dict(acc.PAISES["PE"])
    pe_cfg["ruta_docs"] = raiz_docs
    pe_cfg["ruta_json"] = ruta_json
    pe_cfg["ruta_excel"] = tmp_path / "Centro de Costos Perú.xlsx"
    pe_cfg["ruta_reconciliacion"] = tmp_path / "reconciliacion_archivos_peru.json"
    pe_cfg["ruta_backups"] = respaldos_pe
    monkeypatch.setitem(acc.PAISES, "PE", pe_cfg)

    llamadas = []
    original = acc.backup_mas_reciente

    def _espia(ruta_backups=None):
        llamadas.append(ruta_backups)
        return original(ruta_backups) if ruta_backups is not None else original()

    monkeypatch.setattr(acc, "backup_mas_reciente", _espia)
    driver.cmd_status(pais="PE")

    assert llamadas == [respaldos_pe]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests/test_driver_pais_arg.py" -v`
Expected: FAIL — `driver._extraer_pais` and `cmd_status(pais=...)` don't exist yet.

- [ ] **Step 3: Add `_extraer_pais` and thread `pais` through every command**

In `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py`, find:

```python
def _imprimir_lista_truncada(items, formatear, limite=15):
```

Insert immediately before it:

```python
def _extraer_pais(argv):
    """Busca '--pais VALOR' en cualquier posicion de argv y lo separa del
    resto -- devuelve (pais, argv_sin_ese_flag). Default 'CL' si no aparece."""
    argv = list(argv)
    if "--pais" in argv:
        idx = argv.index("--pais")
        pais = argv[idx + 1]
        del argv[idx:idx + 2]
        return pais, argv
    return "CL", argv


```

Find:

```python
def cmd_status():
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    print("=" * 70)
    print("  ESTADO CENTRO DE COSTOS (solo lectura, no escribe nada)")
    print("=" * 70)
```

Replace with:

```python
def cmd_status(pais="CL"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    acc.configurar_pais(pais)

    print("=" * 70)
    print(f"  ESTADO CENTRO DE COSTOS - {pais} (solo lectura, no escribe nada)")
    print("=" * 70)
```

Find:

```python
    print("\nVerificación aritmética sobre TODO datos_extraidos.json (Neto vs IVA 19%):")
```

Replace with:

```python
    print(f"\nVerificación aritmética sobre TODO datos_extraidos.json (Neto vs {acc.NOMBRE_IMPUESTO_PCT}):")
```

Find (further down in `cmd_status`, in the "Cambios manuales detectados" section):

```python
    print("\nCambios manuales detectados (preview, no se escribe nada):")
    ruta_backup_anterior = acc.backup_mas_reciente()
```

Replace with (same stale-default risk as `main()`'s original call — `backup_mas_reciente`'s own `ruta_backups=RUTA_BACKUPS` default is bound once at module-load time to Chile's path, so it must be passed explicitly here to follow whichever país `configurar_pais` just set):

```python
    print("\nCambios manuales detectados (preview, no se escribe nada):")
    ruta_backup_anterior = acc.backup_mas_reciente(ruta_backups=acc.RUTA_BACKUPS)
```

Find:

```python
def cmd_run():
    acc.main()
    return 0


def cmd_confirmar(args):
    if not args:
        acc.confirmar_correcciones(None)
    elif args == ["--todos"]:
        acc.confirmar_correcciones("TODOS")
    else:
        acc.confirmar_correcciones(args)
    return 0


def cmd_visualizador():
    visualizador_dir = ROOT / "Visualizador Web"
    sys.path.insert(0, str(visualizador_dir))
    sys.dont_write_bytecode = True
    import build_visualizador as bv  # noqa: E402
    return bv.build()


def main():
    comandos = ("status", "run", "confirmar", "visualizador")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        print("Uso: python driver.py [status|run|confirmar [--todos|N_REF ...]|visualizador]")
        return 2

    if sys.argv[1] == "status":
        return cmd_status()
    if sys.argv[1] == "confirmar":
        return cmd_confirmar(sys.argv[2:])
    if sys.argv[1] == "visualizador":
        return cmd_visualizador()
    return cmd_run()
```

Replace with:

```python
def cmd_run(pais="CL"):
    acc.main(pais=pais)
    return 0


def cmd_confirmar(args, pais="CL"):
    acc.configurar_pais(pais)
    if not args:
        acc.confirmar_correcciones(None)
    elif args == ["--todos"]:
        acc.confirmar_correcciones("TODOS")
    else:
        acc.confirmar_correcciones(args)
    return 0


def cmd_visualizador(pais="CL"):
    acc.configurar_pais(pais)
    visualizador_dir = acc.RAIZ_VISUALIZADOR_WEB
    ruta_build_script = visualizador_dir / "build_visualizador.py"
    if not ruta_build_script.exists():
        print(f"[INFO] Visualizador Web de {pais} aún no implementado -- nada que regenerar.")
        return 0
    sys.path.insert(0, str(visualizador_dir))
    sys.dont_write_bytecode = True
    import build_visualizador as bv  # noqa: E402
    return bv.build()


def main():
    comandos = ("status", "run", "confirmar", "visualizador")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        print("Uso: python driver.py [status|run|confirmar [--todos|N_REF ...]|visualizador] [--pais CL|PE]")
        return 2

    comando = sys.argv[1]
    pais, resto = _extraer_pais(sys.argv[2:])

    if comando == "status":
        return cmd_status(pais=pais)
    if comando == "confirmar":
        return cmd_confirmar(resto, pais=pais)
    if comando == "visualizador":
        return cmd_visualizador(pais=pais)
    return cmd_run(pais=pais)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests/test_driver_pais_arg.py" -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Run the full suite (this driver is exercised by other existing tests too)**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add "Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py" "Centro de Costos/Sistema/tests/test_driver_pais_arg.py"
git commit -m "feat(centro-de-costos): --pais CL|PE en driver.py (status/run/confirmar/visualizador)"
```

---

### Task 6: Bootstrap Perú's data scaffolding (synthetic-safe, no real data touched)

**Files:**
- Create: `Peru/Centro de Costos/Excel/` (empty directory, `.gitkeep` — the Excel itself is created by the first real `run`, not committed to git per the root `.gitignore` patterns for `*.xlsx`)
- Create: `Peru/Centro de Costos/datos_extraidos_peru.json`
- Create: `Peru/Centro de Costos/reconciliacion_archivos_peru.json`
- Create: `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/ERRORES_PERU.md`

This task creates real (but empty/placeholder) files in the new `Peru/` tree — it does **not** touch anything under Chile's existing `Centro de Costos/` data. Safe to run directly, no dry-run needed.

- [ ] **Step 1: Confirm the `.gitignore` patterns already cover the new tree**

Run: `git check-ignore -v "Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx"` — expected: matches the existing `*.xlsx` pattern (prints the matching rule). Run: `git check-ignore -v "Peru/Centro de Costos/datos_extraidos_peru.json"` — expected: **no output** (not ignored — this file's name doesn't match the `**/datos_extraidos*.json` gitignore pattern... check this explicitly): if it prints nothing, read the root `.gitignore` and confirm whether `datos_extraidos_peru.json` needs its own pattern added (the existing pattern is written as `**/datos_extraidos*.json` per the root `CLAUDE.md`, which **does** match `datos_extraidos_peru.json` via the `*` — but verify with the actual command rather than assuming). If `git check-ignore` shows it is NOT ignored, add a line to the root `.gitignore` before proceeding, since this file holds real extracted invoice data once Perú has documents.

- [ ] **Step 2: Create the directories and bootstrap files**

```bash
mkdir -p "Peru/Centro de Costos/Excel/Respaldos"
touch "Peru/Centro de Costos/Excel/.gitkeep"
echo "[]" > "Peru/Centro de Costos/datos_extraidos_peru.json"
echo '{"mapeo": {}}' > "Peru/Centro de Costos/reconciliacion_archivos_peru.json"
```

Create `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/ERRORES_PERU.md`:

```markdown
# Errores — Centro de Costos Perú

Mismo formato que [ERRORES.md](ERRORES.md) (Chile) — historial de errores del
pipeline y correcciones manuales hechas directo en `Centro de Costos
Perú.xlsx`. Documento separado del de Chile porque los N° Ref. de cada país
viven en namespaces de prefijo distintos y no comparten historial.

## Correcciones manuales pendientes de recolorear

| Fecha | Hoja | N° Ref. | Campo / Columna | Valor anterior (rojo) | Valor corregido | Estado | Nota |
|---|---|---|---|---|---|---|---|
| *(sin entradas todavía)* | | | | | | | |
```

- [ ] **Step 3: Verify `reconciliacion_archivos_peru.json`'s shape matches what `cargar_reconciliacion` expects**

Run this quick check (uses the real function against the real new file, read-only):

```bash
py -3.14 -c "
import sys; sys.path.insert(0, 'Centro de Costos/Sistema')
import auditor_centro_costos as acc
acc.configurar_pais('PE')
print(acc.cargar_reconciliacion())
acc.configurar_pais('CL')
"
```

Expected output: `{}` (the empty `mapeo` dict, loaded successfully, no exception).

- [ ] **Step 4: Commit**

```bash
git add "Peru/Centro de Costos/Excel/.gitkeep" "Peru/Centro de Costos/datos_extraidos_peru.json" "Peru/Centro de Costos/reconciliacion_archivos_peru.json" "Centro de Costos/.claude/skills/Registro_Centro_de_Costos/ERRORES_PERU.md"
git commit -m "chore(peru): bootstrap de datos vacios para Centro de Costos Peru"
```

---

### Task 7: Documentation — `SKILL.md` updates for `--pais`

**Files:**
- Modify: `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/SKILL.md`
- Modify: `Centro de Costos/.claude/skills/Actualizar_CC/SKILL.md`
- Modify: `Centro de Costos/.claude/skills/Actualizar_Base_de_Datos/SKILL.md`

No tests apply to documentation — this task is prose only. Each file needs the same addition: a short note that every command now accepts an optional `--pais CL|PE` (default `CL`), and that Perú starts empty (no dashboards yet, sub-project 4).

- [ ] **Step 1: Update `Registro_Centro_de_Costos/SKILL.md`**

Find the `## Prerequisitos` heading and insert a new section immediately before it:

```markdown
## Países

Todos los comandos (`status`/`run`/`confirmar`/`visualizador`) aceptan un
flag opcional `--pais CL|PE` (default `CL`, así que ninguna invocación
existente cambia). `PE` (Perú) opera sobre un árbol de datos totalmente
separado — su propio `Centro de Costos Perú.xlsx` (en `Peru/Centro de
Costos/Excel/`), su propio `datos_extraidos_peru.json`, su propia carpeta de
facturas (`Facturas y Boletas/Perú/`), IGV 18% en vez de IVA 19%, valores en
soles. Perú no tiene visualizador web todavía (sub-proyecto 4 del spec de
expansión) — `visualizador --pais PE` lo informa y no falla.

```
python ".claude/skills/Registro_Centro_de_Costos/driver.py" status --pais PE
python ".claude/skills/Registro_Centro_de_Costos/driver.py" run --pais PE
```

Ver [`docs/superpowers/specs/2026-08-21-peru-expansion-design.md`](../../../../docs/superpowers/specs/2026-08-21-peru-expansion-design.md) (raíz de `Finanzas QUEMPIN/`) para la arquitectura completa.
```

- [ ] **Step 2: Update `Actualizar_CC/SKILL.md` and `Actualizar_Base_de_Datos/SKILL.md`**

Read each file first, then add one short paragraph near the top (after the frontmatter/first heading) noting: `--pais CL|PE` passes through to `Registro_Centro_de_Costos` unchanged; for `Actualizar_CC` specifically, note that the GitHub Pages publish step still only applies to Chile until sub-project 4 ships Perú's dashboard.

- [ ] **Step 3: Commit**

```bash
git add "Centro de Costos/.claude/skills/Registro_Centro_de_Costos/SKILL.md" "Centro de Costos/.claude/skills/Actualizar_CC/SKILL.md" "Centro de Costos/.claude/skills/Actualizar_Base_de_Datos/SKILL.md"
git commit -m "docs(centro-de-costos): documentar --pais CL|PE en los skills"
```

---

### Task 8: Real "Facturas y Boletas" restructuring (Chile/Perú split) — production data, do this last

**Files:**
- Moves real files under: `Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/`

**This is the one task in this plan that touches real, currently-in-use financial documents.** Everything in Tasks 1–7 was validated against synthetic `tmp_path` trees first specifically so this step is the only place real data is touched, and by the time we get here the code is already proven correct.

**Do not start this task if anyone might have a file open inside "Facturas y Boletas/" right now (ask the user first if unsure) — a file lock mid-move can leave a folder half-moved.**

- [ ] **Step 1: Snapshot the "before" state for comparison**

Run (read-only, current code, before any change takes effect — this must run from a clean checkout of the code *before* Task 1–4's changes, or temporarily via `git stash`, since after Task 1 lands, `RAIZ_DOCS` already expects the `Chile/` subfolder to exist):

Actually — since Tasks 1–7 already changed the code to expect `Facturas y Boletas/Chile/`, running `status` now (post-Task-7, pre-move) will correctly report "carpeta raíz no existe" for CL. **Capture the "before" baseline earlier than that instead**: before starting Task 1 in this plan, or from `git log`/`HISTORIAL.md`, note the current document/project counts (see `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/HISTORIAL.md` for the most recent real `run`'s reported totals — documents in Master, distinct projects). Write these numbers down now for the Step 4 comparison.

- [ ] **Step 2: List the current top-level folders (dry run, read-only)**

```bash
ls "Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/"
```

Expected: the ~18 project folders (`UMAG`, `Cesfam Limache`, ... — see the list in `Centro de Costos/CLAUDE.md` § Estructura del repositorio) plus any OneDrive housekeeping files (`.ppinfocache`, `PP11Thumbs.ptn`) that are **not** folders — these stay at the current level, only directories get moved.

- [ ] **Step 3: Move the project folders into a new "Chile/" subfolder, create "Perú/" empty**

```bash
cd "Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y Boletas"
mkdir -p "Chile" "Perú"
for d in */ ; do
  case "$d" in
    "Chile/"|"Perú/") continue ;;
  esac
  mv -- "$d" "Chile/"
done
ls "Chile/"
ls "Perú/"
```

Expected: `Chile/` now contains all ~18 project folders (and their full contents — `mv` on a directory preserves everything inside); `Perú/` is empty; non-directory files (`.ppinfocache`, `PP11Thumbs.ptn`) are untouched at the top level.

- [ ] **Step 4: Verify Chile's real data is unaffected — run `status --pais CL` against production**

```bash
py -3.14 ".claude/skills/Registro_Centro_de_Costos/driver.py" status
```
(run from `Centro de Costos/` — no `--pais` needed, `CL` is the default)

Expected: the exact same "Documentos ya en Master", "N° Documento distintos", and project list as the baseline captured in Step 1 — the move must not change what `status` reports for Chile, only where the files physically live.

- [ ] **Step 5: Verify Perú's tree is genuinely empty and `status --pais PE` doesn't crash**

```bash
py -3.14 ".claude/skills/Registro_Centro_de_Costos/driver.py" status --pais PE
```

Expected: runs to completion, reports "Documentos ya en Master: 0", "Proyectos detectados (0):", no traceback. (`Centro de Costos Perú.xlsx` doesn't exist yet at this point — `status` already handles a missing Excel gracefully per its existing `[INFO] El Excel aún no existe` branch.)

- [ ] **Step 6: Run a real (production) `run --pais PE` to create the actual empty workbook**

```bash
py -3.14 ".claude/skills/Registro_Centro_de_Costos/driver.py" run --pais PE
```

Expected: completes with `Documentos nuevos registrados: 0`, creates `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx` with `Master`/`Detalle` sheets and the IGV/PEN headers verified in Task 1's tests. Open the file (or re-verify via the same `openpyxl.load_workbook` check as Task 4's test) to confirm by hand — this is the first time real (if empty) production output exists for Perú.

- [ ] **Step 7: Run the full pytest suite one final time**

Run: `py -3.14 -m pytest` (from the repo root — runs all 7 suites per root `CLAUDE.md`)
Expected: PASS, all suites, no regressions anywhere in the repo (not just Centro de Costos — this confirms nothing in Cotizador Histórico/Análisis Financiero/Visualizador Web silently depended on the old "Facturas y Boletas/" layout).

- [ ] **Step 8: Update `Centro de Costos/CLAUDE.md`'s folder structure diagram**

Find the ASCII tree under `## Estructura del repositorio` and update the `Facturas y Boletas/` line and its children to show the new `Chile/`/`Perú/` nesting (mirroring what Task 8 Step 3 just did on disk).

- [ ] **Step 9: Commit**

```bash
git add "Centro de Costos/CLAUDE.md"
git commit -m "chore(centro-de-costos): reestructurar Facturas y Boletas en Chile/ y Perú/"
```

(The moved documents themselves are gitignored real data — nothing to `git add` for the move itself, only the doc update.)

---

## Self-Review Notes

- **Spec coverage**: master spec's sub-project 1 items — parametrize `auditor_centro_costos.py` ✅ (Tasks 1–4), IGV 18% ✅ (Task 2), restructure Facturas y Boletas ✅ (Task 8), create empty Perú workbook ✅ (Task 6 scaffolding + Task 8 Step 6 real creation), update `Registro_Centro_de_Costos`/`Actualizar_CC`/`Actualizar_Base_de_Datos` skills ✅ (Task 7), tests without breaking CL ✅ (every task runs the full suite).
- **Placeholder scan**: no TBD/TODO; every step has literal code or literal shell commands.
- **Type/name consistency checked**: `configurar_pais(pais="CL")` (Task 1) → `main(pais="CL")` calls it (Task 4) → `driver.py`'s `cmd_status(pais="CL")`/`cmd_run(pais="CL")`/`cmd_confirmar(args, pais="CL")`/`cmd_visualizador(pais="CL")` (Task 5) all match this exact parameter name and default throughout.
- **Out of scope, confirmed not silently included**: Cotizador Histórico, Análisis Financiero Perú, the 3 dashboards, `/Actualizar_Finanzas` — Task 4 explicitly makes `main()` skip PASO 12c/12d for `PE` with an `[INFO]` rather than attempting them.
