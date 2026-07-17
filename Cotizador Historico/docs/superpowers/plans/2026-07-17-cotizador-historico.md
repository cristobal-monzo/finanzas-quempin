# Cotizador Historico Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `Cotizador Historico` module — a read-only tool that estimates today's cost of an item by fuzzy-matching it against historical line items in `Centro de Costos.xlsx` and inflation-adjusting each matched price using the UF (Unidad de Fomento) value on the purchase date vs. today.

**Architecture:** A single core module (`Sistema/cotizador_historico.py`) with pure, independently-testable functions — read `Detalle`/`Master` from the existing Centro de Costos workbook (read-only, never written), fuzzy-search by item name/description, fetch UF values from the public `mindicador.cl` API with a local JSON cache for historical (immutable) dates, and combine both into a reajuste calculation. A thin `driver.py` (same pattern as `Registro_Centro_de_Costos`) exposes `status`/`consultar` commands; a `SKILL.md` + module `CLAUDE.md` document it.

**Tech Stack:** Python (same interpreter as Centro de Costos), `openpyxl` (already a dependency of Centro de Costos), stdlib only otherwise (`difflib` for fuzzy matching, `urllib.request` for the HTTP call to `mindicador.cl`) — no new third-party dependencies. `pytest` for tests, following the existing `Centro de Costos/Sistema/tests/` convention (plain functions, `conftest.py` doing a `sys.path.insert`, temp `.xlsx` files built directly with `openpyxl.Workbook()` for tests that need Excel data).

## Global Constraints

- **No new third-party dependencies** — stdlib + `openpyxl` only (spec: "sin dependencias nuevas, igual que el resto del proyecto").
- **Cotizador Historico is 100% read-only on `Centro de Costos.xlsx`** — must never open it in write mode or save to it.
- **Reajuste is UF-only** (not IPC, not USD) — explicit user decision.
- **Price basis is `P. Unitario sin IVA`**, not the line total — explicit user decision (comparable across different purchased quantities).
- **No category fallback** when there's no name match — explicit user decision for v1; return "no encontrado" with suggestions instead.
- **No cotizaciones (quotes) source in v1** — Centro de Costos is the only data source; result shape keeps room for adding a quotes source later without a rewrite.
- **Historical UF values are cached indefinitely in `Sistema/uf_cache.json`; today's UF value is never persisted to that cache across runs** — explicit user decision (historical UF never changes once published; today's does, until end of day).
- **Spec:** `../docs/superpowers/specs/2026-07-17-cotizador-historico-design.md` (relative to `Cotizador Historico/Sistema/`) is the source of truth for anything not covered here.

---

### Task 1: Excel reading — `cargar_items_detalle`

**Files:**
- Create: `Cotizador Historico/Sistema/cotizador_historico.py`
- Create: `Cotizador Historico/Sistema/tests/conftest.py`
- Create: `Cotizador Historico/Sistema/tests/test_lectura_excel.py`

**Interfaces:**
- Produces (used by Tasks 2-4):
  - `RUTA_EXCEL_CENTRO_COSTOS: Path` — module constant, default path to `Centro de Costos/Excel/Centro de Costos.xlsx`.
  - `class ExcelNoDisponibleError(Exception)`
  - `mapear_encabezados(hoja) -> dict[str, int]` — header text → 1-based column number, reading row 1 of an openpyxl worksheet.
  - `cargar_items_detalle(ruta_excel: Path | None = None) -> list[dict]` — each dict has keys: `n_ref` (str), `nombre_item` (str), `descripcion` (str), `precio_unitario_sin_iva` (number or None), `fecha` (`datetime` or `None`), `excluido_motivo` (`None`, `"sin_master"`, or `"fecha_invalida"`).

- [ ] **Step 1: Write the failing tests**

Create `Cotizador Historico/Sistema/tests/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

Create `Cotizador Historico/Sistema/tests/test_lectura_excel.py`:

```python
from datetime import datetime

import openpyxl
import pytest

import cotizador_historico as ch


def _crear_excel_prueba(tmp_path, filas_detalle, filas_master):
    """filas_detalle: lista de tuplas (n_ref, nombre_item, descripcion, precio_unitario_sin_iva)
    filas_master: lista de tuplas (n_ref, fecha)"""
    wb = openpyxl.Workbook()
    ws_detalle = wb.active
    ws_detalle.title = "Detalle"
    for c, h in enumerate(["N° Ref.", "Nombre Ítem", "Descripción", "P. Unitario sin IVA"], 1):
        ws_detalle.cell(row=1, column=c, value=h)
    for r, fila in enumerate(filas_detalle, 2):
        for c, valor in enumerate(fila, 1):
            ws_detalle.cell(row=r, column=c, value=valor)

    ws_master = wb.create_sheet("Master")
    for c, h in enumerate(["N° Ref.", "Fecha"], 1):
        ws_master.cell(row=1, column=c, value=h)
    for r, fila in enumerate(filas_master, 2):
        for c, valor in enumerate(fila, 1):
            ws_master.cell(row=r, column=c, value=valor)

    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(ruta)
    return ruta


def test_mapear_encabezados_lee_fila_1(tmp_path):
    ruta = _crear_excel_prueba(tmp_path, filas_detalle=[], filas_master=[])
    wb = openpyxl.load_workbook(ruta, read_only=True)
    cols = ch.mapear_encabezados(wb["Detalle"])
    assert cols["N° Ref."] == 1
    assert cols["Nombre Ítem"] == 2
    assert cols["Descripción"] == 3
    assert cols["P. Unitario sin IVA"] == 4


def test_cargar_items_detalle_resuelve_fecha_via_master(tmp_path):
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-001", "Taladro", "Taladro percutor 20V", 90000)],
        filas_master=[("UMAG-001", datetime(2026, 1, 15))],
    )
    items = ch.cargar_items_detalle(ruta)
    assert len(items) == 1
    item = items[0]
    assert item["n_ref"] == "UMAG-001"
    assert item["nombre_item"] == "Taladro"
    assert item["descripcion"] == "Taladro percutor 20V"
    assert item["precio_unitario_sin_iva"] == 90000
    assert item["fecha"] == datetime(2026, 1, 15)
    assert item["excluido_motivo"] is None


def test_cargar_items_detalle_excluye_item_sin_master(tmp_path):
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-002", "Cemento", "Saco 25kg", 5000)],
        filas_master=[],
    )
    items = ch.cargar_items_detalle(ruta)
    assert items[0]["excluido_motivo"] == "sin_master"
    assert items[0]["fecha"] is None


def test_cargar_items_detalle_excluye_fecha_no_parseable(tmp_path):
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-003", "Cable", "Cable 10m", 3000)],
        filas_master=[("UMAG-003", "sin fecha")],
    )
    items = ch.cargar_items_detalle(ruta)
    assert items[0]["excluido_motivo"] == "fecha_invalida"
    assert items[0]["fecha"] is None


def test_cargar_items_detalle_ignora_filas_sin_n_ref(tmp_path):
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-004", "Pintura", "Balde 1 galón", 15000), (None, None, None, None)],
        filas_master=[("UMAG-004", datetime(2026, 2, 1))],
    )
    items = ch.cargar_items_detalle(ruta)
    assert len(items) == 1


def test_cargar_items_detalle_archivo_inexistente_lanza_error(tmp_path):
    ruta = tmp_path / "no existe.xlsx"
    with pytest.raises(ch.ExcelNoDisponibleError):
        ch.cargar_items_detalle(ruta)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/test_lectura_excel.py" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cotizador_historico'` (the module doesn't exist yet).

- [ ] **Step 3: Write the implementation**

Create `Cotizador Historico/Sistema/cotizador_historico.py`:

```python
# -*- coding: utf-8 -*-
"""
cotizador_historico.py — estima el costo actual de un item a partir de sus
compras historicas en Centro de Costos, reajustando cada precio por UF
(fecha de compra -> fecha de la consulta).

Modulo 100% de solo lectura sobre Centro de Costos.xlsx: nunca lo abre en
modo escritura ni lo modifica. Ver ../docs/superpowers/specs/
2026-07-17-cotizador-historico-design.md para el diseno completo.
"""

from datetime import datetime
from pathlib import Path

import openpyxl

RAIZ_MODULO = Path(__file__).resolve().parent.parent
RUTA_EXCEL_CENTRO_COSTOS = RAIZ_MODULO.parent / "Centro de Costos" / "Excel" / "Centro de Costos.xlsx"
RUTA_CACHE_UF = Path(__file__).resolve().parent / "uf_cache.json"


class ExcelNoDisponibleError(Exception):
    """El archivo Centro de Costos.xlsx no existe o no se pudo abrir para lectura."""


def mapear_encabezados(hoja):
    """dict {texto_encabezado: numero_columna (1-based)} leyendo la fila 1."""
    fila = next(hoja.iter_rows(min_row=1, max_row=1))
    return {celda.value: celda.column for celda in fila if celda.value}


def _fechas_por_ref(ws_master):
    cols = mapear_encabezados(ws_master)
    col_ref = cols["N° Ref."]
    col_fecha = cols["Fecha"]
    fechas = {}
    for fila in ws_master.iter_rows(min_row=2):
        n_ref = fila[col_ref - 1].value
        if n_ref:
            fechas[n_ref] = fila[col_fecha - 1].value
    return fechas


def cargar_items_detalle(ruta_excel=None):
    """Lee Detalle+Master de Centro de Costos.xlsx (solo lectura) y devuelve
    una lista de dicts, uno por item de linea de Detalle, con su fecha ya
    resuelta via Master (cruce por N Ref.).

    Items cuyo N Ref. no tiene fila en Master, o cuya Fecha en Master no es
    un datetime valido, quedan con excluido_motivo poblado ("sin_master" o
    "fecha_invalida") y fecha=None -- no deben entrar a ninguna busqueda ni
    agregacion posterior."""
    ruta = Path(ruta_excel) if ruta_excel is not None else RUTA_EXCEL_CENTRO_COSTOS
    try:
        wb = openpyxl.load_workbook(str(ruta), data_only=True, read_only=True)
    except FileNotFoundError as exc:
        raise ExcelNoDisponibleError(f"No existe {ruta}") from exc
    except PermissionError as exc:
        raise ExcelNoDisponibleError(f"No se pudo abrir {ruta} para lectura: {exc}") from exc

    try:
        ws_detalle = wb["Detalle"]
        ws_master = wb["Master"]
        fechas = _fechas_por_ref(ws_master)
        cols = mapear_encabezados(ws_detalle)
        col_ref = cols["N° Ref."]
        col_nombre = cols["Nombre Ítem"]
        col_desc = cols["Descripción"]
        col_precio = cols["P. Unitario sin IVA"]

        items = []
        for fila in ws_detalle.iter_rows(min_row=2):
            n_ref = fila[col_ref - 1].value
            if not n_ref:
                continue
            fecha = fechas.get(n_ref)
            if n_ref not in fechas:
                excluido_motivo = "sin_master"
            elif not isinstance(fecha, datetime):
                excluido_motivo = "fecha_invalida"
            else:
                excluido_motivo = None
            items.append({
                "n_ref": n_ref,
                "nombre_item": fila[col_nombre - 1].value or "",
                "descripcion": fila[col_desc - 1].value or "",
                "precio_unitario_sin_iva": fila[col_precio - 1].value,
                "fecha": fecha if excluido_motivo is None else None,
                "excluido_motivo": excluido_motivo,
            })
        return items
    finally:
        wb.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/test_lectura_excel.py" -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add "Cotizador Historico/Sistema/cotizador_historico.py" "Cotizador Historico/Sistema/tests/conftest.py" "Cotizador Historico/Sistema/tests/test_lectura_excel.py"
git commit -m "feat(cotizador-historico): leer Detalle+Master de Centro de Costos.xlsx"
```

---

### Task 2: Text normalization and fuzzy search

**Files:**
- Modify: `Cotizador Historico/Sistema/cotizador_historico.py` (append)
- Create: `Cotizador Historico/Sistema/tests/test_busqueda.py`

**Interfaces:**
- Consumes: the item dict shape produced by `cargar_items_detalle` (Task 1) — specifically the keys `nombre_item`, `descripcion`, `excluido_motivo`.
- Produces (used by Task 4):
  - `UMBRAL_SIMILITUD: float = 0.6`, `UMBRAL_SUGERENCIA: float = 0.4`, `MAX_SUGERENCIAS: int = 5` — module constants.
  - `normalizar_texto(texto: str) -> str` — lowercase, accents stripped.
  - `similitud(a: str, b: str) -> float` — 1.0 if either is a substring of the other, else `difflib.SequenceMatcher.ratio()`.
  - `buscar_items(items: list[dict], texto_busqueda: str, umbral: float = UMBRAL_SIMILITUD, umbral_sugerencia: float = UMBRAL_SUGERENCIA) -> tuple[list[dict], list[str]]` — returns `(coincidencias, sugerencias)`; `coincidencias` is the subset of `items` (unmodified dicts) sorted by descending similarity; `sugerencias` is up to `MAX_SUGERENCIAS` distinct `nombre_item` strings with similarity in `[umbral_sugerencia, umbral)`. Items with `excluido_motivo is not None` are always skipped.

- [ ] **Step 1: Write the failing tests**

Create `Cotizador Historico/Sistema/tests/test_busqueda.py`:

```python
import cotizador_historico as ch


def _item(n_ref, nombre, descripcion="", excluido=None):
    return {
        "n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
        "precio_unitario_sin_iva": 1, "fecha": None, "excluido_motivo": excluido,
    }


# ── normalizar_texto ──────────────────────────────────────────────────────

def test_normalizar_texto_quita_acentos_y_mayusculas():
    assert ch.normalizar_texto("Ítem Eléctrico") == "item electrico"


def test_normalizar_texto_recorta_espacios():
    assert ch.normalizar_texto("  Taladro  ") == "taladro"


# ── similitud ──────────────────────────────────────────────────────────────

def test_similitud_exacta_es_1():
    assert ch.similitud("taladro", "taladro") == 1.0


def test_similitud_substring_es_1():
    assert ch.similitud("taladro", "taladro percutor 20v") == 1.0
    assert ch.similitud("taladro percutor 20v", "taladro") == 1.0


def test_similitud_texto_no_relacionado_es_baja():
    assert ch.similitud("taladro", "cemento") < 0.4


def test_similitud_con_typo_es_alta():
    assert ch.similitud("taladro", "taladr0") > 0.7


def test_similitud_con_texto_vacio_es_0():
    assert ch.similitud("taladro", "") == 0.0
    assert ch.similitud("", "taladro") == 0.0


# ── buscar_items ───────────────────────────────────────────────────────────

def test_buscar_items_encuentra_por_nombre_o_descripcion():
    items = [
        _item("A", "Taladro", "Taladro percutor 20V"),
        _item("B", "Cemento", "Saco 25kg"),
    ]
    coincidencias, sugerencias = ch.buscar_items(items, "taladro")
    assert [it["n_ref"] for it in coincidencias] == ["A"]
    assert sugerencias == []


def test_buscar_items_ignora_items_excluidos():
    items = [_item("A", "Taladro", excluido="sin_master")]
    coincidencias, sugerencias = ch.buscar_items(items, "taladro")
    assert coincidencias == []
    assert sugerencias == []


def test_buscar_items_sin_match_devuelve_listas_vacias():
    items = [_item("A", "Cemento", "Saco 25kg")]
    coincidencias, sugerencias = ch.buscar_items(items, "taladro")
    assert coincidencias == []
    assert sugerencias == []


def test_buscar_items_separa_coincidencias_y_sugerencias_por_umbral(monkeypatch):
    items = [_item("A", "Uno"), _item("B", "Dos"), _item("C", "Tres")]
    puntajes = {"uno": 0.9, "dos": 0.5, "tres": 0.1}
    monkeypatch.setattr(ch, "similitud", lambda a, b: puntajes.get(b, 0.0))

    coincidencias, sugerencias = ch.buscar_items(items, "consulta")

    assert [it["n_ref"] for it in coincidencias] == ["A"]
    assert sugerencias == ["Dos"]


def test_buscar_items_ordena_coincidencias_de_mayor_a_menor_similitud(monkeypatch):
    items = [_item("A", "Uno"), _item("B", "Dos")]
    puntajes = {"uno": 0.7, "dos": 0.95}
    monkeypatch.setattr(ch, "similitud", lambda a, b: puntajes.get(b, 0.0))

    coincidencias, _sugerencias = ch.buscar_items(items, "consulta")

    assert [it["n_ref"] for it in coincidencias] == ["B", "A"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/test_busqueda.py" -v`
Expected: FAIL with `AttributeError: module 'cotizador_historico' has no attribute 'normalizar_texto'`

- [ ] **Step 3: Write the implementation**

Append to `Cotizador Historico/Sistema/cotizador_historico.py` (add these imports to the top, next to the existing `from pathlib import Path` / `import openpyxl` lines):

```python
import unicodedata
from difflib import SequenceMatcher
```

Then append at the end of the file:

```python
UMBRAL_SIMILITUD = 0.6
UMBRAL_SUGERENCIA = 0.4
MAX_SUGERENCIAS = 5


def normalizar_texto(texto):
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def similitud(a, b):
    """1.0 si uno es substring del otro (Nombre Item ya viene normalizado a
    terminos genericos, ver Centro de Costos/CLAUDE.md); si no, ratio de
    difflib para tolerar typos/variantes."""
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def buscar_items(items, texto_busqueda, umbral=UMBRAL_SIMILITUD, umbral_sugerencia=UMBRAL_SUGERENCIA):
    """Busqueda difusa de texto_busqueda contra Nombre Item/Descripcion.
    Devuelve (coincidencias, sugerencias): coincidencias son items (dicts
    sin modificar) con similitud >= umbral, ordenados de mayor a menor;
    sugerencias son hasta MAX_SUGERENCIAS nombre_item distintos con
    similitud en [umbral_sugerencia, umbral), para cuando no hay match
    directo. Items con excluido_motivo != None se ignoran siempre."""
    consulta = normalizar_texto(texto_busqueda)
    puntuadas = []
    for item in items:
        if item["excluido_motivo"] is not None:
            continue
        s = max(
            similitud(consulta, normalizar_texto(item["nombre_item"])),
            similitud(consulta, normalizar_texto(item["descripcion"])),
        )
        puntuadas.append((s, item))
    puntuadas.sort(key=lambda par: -par[0])

    coincidencias = [item for s, item in puntuadas if s >= umbral]

    sugerencias = []
    for s, item in puntuadas:
        if umbral_sugerencia <= s < umbral and item["nombre_item"] not in sugerencias:
            sugerencias.append(item["nombre_item"])
        if len(sugerencias) >= MAX_SUGERENCIAS:
            break
    return coincidencias, sugerencias
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/test_busqueda.py" -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Run the full test suite so far**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/" -v`
Expected: PASS (17 tests total)

- [ ] **Step 6: Commit**

```bash
git add "Cotizador Historico/Sistema/cotizador_historico.py" "Cotizador Historico/Sistema/tests/test_busqueda.py"
git commit -m "feat(cotizador-historico): busqueda difusa de items por nombre/descripcion"
```

---

### Task 3: UF value fetching and local cache

**Files:**
- Modify: `Cotizador Historico/Sistema/cotizador_historico.py` (append)
- Create: `Cotizador Historico/Sistema/tests/test_uf.py`

**Interfaces:**
- Produces (used by Task 4):
  - `class UFNoDisponibleError(Exception)`
  - `URL_MINDICADOR_UF: str` — module constant, format string with a `{fecha}` placeholder (`%d-%m-%Y`).
  - `consultar_uf_api(fecha: date | datetime) -> float` — calls `mindicador.cl`, returns the UF value for that date; raises `UFNoDisponibleError` on network failure, bad JSON, or an empty `serie`.
  - `cargar_cache_uf(ruta_cache: Path | None = None) -> dict[str, float]` — reads the JSON cache (`{}` if the file doesn't exist).
  - `guardar_cache_uf(cache: dict, ruta_cache: Path | None = None) -> None` — writes the JSON cache.
  - `obtener_valor_uf(fecha: date | datetime, cache_uf: dict) -> float` — returns `cache_uf[fecha_iso]` if present, else calls `consultar_uf_api(fecha)` and stores the result into `cache_uf` (mutated in place; the caller decides whether/when to persist via `guardar_cache_uf`). **Only for historical dates** — callers must never route "today" through this function if they don't want it cached to disk (see Task 4).

- [ ] **Step 1: Write the failing tests**

Create `Cotizador Historico/Sistema/tests/test_uf.py`:

```python
import json
from datetime import date

import pytest

import cotizador_historico as ch


class _FakeRespuesta:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._payload


# ── consultar_uf_api ─────────────────────────────────────────────────────

def test_consultar_uf_api_devuelve_valor_de_la_serie(monkeypatch):
    payload = {"serie": [{"fecha": "2026-07-15T04:00:00.000Z", "valor": 39123.45}]}
    monkeypatch.setattr(ch.urllib.request, "urlopen", lambda url, timeout=10: _FakeRespuesta(payload))
    valor = ch.consultar_uf_api(date(2026, 7, 15))
    assert valor == 39123.45


def test_consultar_uf_api_sin_serie_lanza_error(monkeypatch):
    payload = {"serie": []}
    monkeypatch.setattr(ch.urllib.request, "urlopen", lambda url, timeout=10: _FakeRespuesta(payload))
    with pytest.raises(ch.UFNoDisponibleError):
        ch.consultar_uf_api(date(2026, 7, 15))


def test_consultar_uf_api_sin_conexion_lanza_error(monkeypatch):
    def _falla(url, timeout=10):
        raise ch.urllib.error.URLError("sin conexion")
    monkeypatch.setattr(ch.urllib.request, "urlopen", _falla)
    with pytest.raises(ch.UFNoDisponibleError):
        ch.consultar_uf_api(date(2026, 7, 15))


# ── cargar_cache_uf / guardar_cache_uf ──────────────────────────────────

def test_cargar_cache_uf_archivo_inexistente_devuelve_vacio(tmp_path):
    assert ch.cargar_cache_uf(tmp_path / "no_existe.json") == {}


def test_guardar_y_cargar_cache_uf_roundtrip(tmp_path):
    ruta = tmp_path / "uf_cache.json"
    ch.guardar_cache_uf({"2026-07-15": 39123.45}, ruta)
    assert ch.cargar_cache_uf(ruta) == {"2026-07-15": 39123.45}


# ── obtener_valor_uf ─────────────────────────────────────────────────────

def test_obtener_valor_uf_usa_cache_si_existe(monkeypatch):
    def _falla_si_se_llama(fecha):
        raise AssertionError("no deberia llamar a la API si ya esta en cache")
    monkeypatch.setattr(ch, "consultar_uf_api", _falla_si_se_llama)

    cache = {"2026-07-15": 39100.0}
    valor = ch.obtener_valor_uf(date(2026, 7, 15), cache)
    assert valor == 39100.0


def test_obtener_valor_uf_consulta_api_y_actualiza_cache_si_falta(monkeypatch):
    monkeypatch.setattr(ch, "consultar_uf_api", lambda fecha: 40000.0)
    cache = {}
    valor = ch.obtener_valor_uf(date(2026, 7, 1), cache)
    assert valor == 40000.0
    assert cache == {"2026-07-01": 40000.0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/test_uf.py" -v`
Expected: FAIL with `AttributeError: module 'cotizador_historico' has no attribute 'urllib'` (or similar — the module hasn't imported `urllib`/`json` or defined these functions yet).

- [ ] **Step 3: Write the implementation**

Add these imports to the top of `Cotizador Historico/Sistema/cotizador_historico.py` (next to the other imports):

```python
import json
import urllib.error
import urllib.request
```

Append at the end of the file:

```python
class UFNoDisponibleError(Exception):
    """No se pudo obtener el valor de la UF para una fecha desde mindicador.cl."""


URL_MINDICADOR_UF = "https://mindicador.cl/api/uf/{fecha}"


def consultar_uf_api(fecha):
    """Llama a mindicador.cl y devuelve el valor UF (float) para 'fecha'
    (date o datetime). Lanza UFNoDisponibleError si falla la conexion, la
    respuesta no es JSON valido, o no trae serie de datos. Nunca cachea en
    disco -- eso lo hace el llamador via obtener_valor_uf/guardar_cache_uf."""
    url = URL_MINDICADOR_UF.format(fecha=fecha.strftime("%d-%m-%Y"))
    try:
        with urllib.request.urlopen(url, timeout=10) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UFNoDisponibleError(f"No se pudo consultar mindicador.cl para {fecha}: {exc}") from exc

    serie = datos.get("serie") or []
    if not serie:
        raise UFNoDisponibleError(f"mindicador.cl no tiene valor de UF para {fecha}")
    return serie[0]["valor"]


def cargar_cache_uf(ruta_cache=None):
    ruta = Path(ruta_cache) if ruta_cache is not None else RUTA_CACHE_UF
    if not ruta.exists():
        return {}
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_cache_uf(cache, ruta_cache=None):
    ruta = Path(ruta_cache) if ruta_cache is not None else RUTA_CACHE_UF
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def obtener_valor_uf(fecha, cache_uf):
    """Valor UF para una fecha HISTORICA (compra pasada), usando cache_uf
    (dict fecha_iso->valor, mutado in-place) para no repetir llamadas a la
    API. El llamador decide si persiste cache_uf con guardar_cache_uf. No
    usar esta funcion para la UF de "hoy" -- ver consultar_item (Task 4),
    que llama a consultar_uf_api directo para hoy, sin pasar por el cache
    de archivo."""
    fecha_iso = fecha.strftime("%Y-%m-%d")
    if fecha_iso in cache_uf:
        return cache_uf[fecha_iso]
    valor = consultar_uf_api(fecha)
    cache_uf[fecha_iso] = valor
    return valor
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/test_uf.py" -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Run the full test suite so far**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/" -v`
Expected: PASS (24 tests total)

- [ ] **Step 6: Commit**

```bash
git add "Cotizador Historico/Sistema/cotizador_historico.py" "Cotizador Historico/Sistema/tests/test_uf.py"
git commit -m "feat(cotizador-historico): obtener valor UF desde mindicador.cl con cache local"
```

---

### Task 4: Reajuste calculation and `consultar_item` orchestration

**Files:**
- Modify: `Cotizador Historico/Sistema/cotizador_historico.py` (append)
- Create: `Cotizador Historico/Sistema/tests/test_consultar_item.py`

**Interfaces:**
- Consumes:
  - `cargar_items_detalle(ruta_excel=None) -> list[dict]` (Task 1)
  - `buscar_items(items, texto_busqueda) -> tuple[list[dict], list[str]]` (Task 2)
  - `cargar_cache_uf(ruta_cache=None) -> dict`, `guardar_cache_uf(cache, ruta_cache=None)`, `consultar_uf_api(fecha) -> float`, `obtener_valor_uf(fecha, cache_uf) -> float` (Task 3)
- Produces (used by Task 5's `driver.py`):
  - `calcular_precio_reajustado(precio_original: float, uf_fecha_compra: float, uf_hoy: float) -> int` — `round(precio_original * uf_hoy / uf_fecha_compra)`.
  - `consultar_item(texto_busqueda: str, ruta_excel: Path | None = None, fecha_hoy: date | None = None) -> dict` — the full result:
    ```python
    {
        "encontrado": bool,
        "compras": [
            {"n_ref": str, "fecha": "YYYY-MM-DD", "precio_original_sin_iva": number, "precio_reajustado_hoy": int},
            ...
        ],
        "promedio_reajustado": int | None,
        "rango_minimo": int | None,
        "rango_maximo": int | None,
        "excluidos_count": int,
        "sugerencias": list[str],
    }
    ```
    `fecha_hoy` defaults to `date.today()`; it's an explicit parameter so tests don't depend on the real date.

- [ ] **Step 1: Write the failing tests**

Create `Cotizador Historico/Sistema/tests/test_consultar_item.py`:

```python
from datetime import date, datetime

import cotizador_historico as ch


def _item(n_ref, nombre, descripcion, precio, fecha, excluido=None):
    return {
        "n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
        "precio_unitario_sin_iva": precio, "fecha": fecha, "excluido_motivo": excluido,
    }


# ── calcular_precio_reajustado ──────────────────────────────────────────

def test_calcular_precio_reajustado_aplica_factor_uf():
    # UF subio de 36000 a 39000: factor 39000/36000 = 1.08333...
    assert ch.calcular_precio_reajustado(90000, 36000, 39000) == round(90000 * 39000 / 36000)


def test_calcular_precio_reajustado_uf_sin_cambio_no_altera_precio():
    assert ch.calcular_precio_reajustado(50000, 38000, 38000) == 50000


# ── consultar_item ─────────────────────────────────────────────────────

def _mapa_uf(fecha):
    mapa = {"2026-01-01": 36000.0, "2026-03-01": 37000.0, "2026-07-17": 39000.0}
    return mapa[fecha.strftime("%Y-%m-%d")]


def test_consultar_item_calcula_reajuste_y_agregados(monkeypatch, tmp_path):
    items = [
        _item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1)),
        _item("UMAG-002", "Taladro", "Taladro inalambrico", 100000, datetime(2026, 3, 1)),
    ]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")
    monkeypatch.setattr(ch, "consultar_uf_api", _mapa_uf)

    resultado = ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17))

    esperado_1 = round(90000 * 39000 / 36000)
    esperado_2 = round(100000 * 39000 / 37000)

    assert resultado["encontrado"] is True
    assert resultado["compras"] == [
        {"n_ref": "UMAG-001", "fecha": "2026-01-01", "precio_original_sin_iva": 90000, "precio_reajustado_hoy": esperado_1},
        {"n_ref": "UMAG-002", "fecha": "2026-03-01", "precio_original_sin_iva": 100000, "precio_reajustado_hoy": esperado_2},
    ]
    assert resultado["promedio_reajustado"] == round((esperado_1 + esperado_2) / 2)
    assert resultado["rango_minimo"] == min(esperado_1, esperado_2)
    assert resultado["rango_maximo"] == max(esperado_1, esperado_2)
    assert resultado["excluidos_count"] == 0
    assert resultado["sugerencias"] == []


def test_consultar_item_persiste_uf_historica_en_cache_pero_no_la_de_hoy(monkeypatch, tmp_path):
    items = [_item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1))]
    ruta_cache = tmp_path / "uf_cache.json"
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", ruta_cache)
    monkeypatch.setattr(ch, "consultar_uf_api", _mapa_uf)

    ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17))

    cache_final = ch.cargar_cache_uf(ruta_cache)
    assert cache_final == {"2026-01-01": 36000.0}  # la fecha de compra si, "hoy" no


def test_consultar_item_sin_match_devuelve_no_encontrado(monkeypatch):
    items = [_item("UMAG-001", "Cemento", "Saco 25kg", 5000, datetime(2026, 1, 1))]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)

    resultado = ch.consultar_item("bicicleta", fecha_hoy=date(2026, 7, 17))

    assert resultado["encontrado"] is False
    assert resultado["compras"] == []
    assert resultado["promedio_reajustado"] is None
    assert resultado["rango_minimo"] is None
    assert resultado["rango_maximo"] is None


def test_consultar_item_sin_match_no_llama_a_la_api_de_uf(monkeypatch):
    items = [_item("UMAG-001", "Cemento", "Saco 25kg", 5000, datetime(2026, 1, 1))]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)

    def _falla_si_se_llama(fecha):
        raise AssertionError("no deberia consultar UF si no hubo match")
    monkeypatch.setattr(ch, "consultar_uf_api", _falla_si_se_llama)

    ch.consultar_item("bicicleta", fecha_hoy=date(2026, 7, 17))


def test_consultar_item_cuenta_excluidos(monkeypatch, tmp_path):
    items = [
        _item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1)),
        _item("UMAG-002", "Cemento", "Saco 25kg", 5000, None, excluido="sin_master"),
    ]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)
    monkeypatch.setattr(ch, "consultar_uf_api", _mapa_uf)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")

    resultado = ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17))
    assert resultado["excluidos_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/test_consultar_item.py" -v`
Expected: FAIL with `AttributeError: module 'cotizador_historico' has no attribute 'calcular_precio_reajustado'`

- [ ] **Step 3: Write the implementation**

Add this import to the top of `Cotizador Historico/Sistema/cotizador_historico.py`:

```python
from datetime import date
```

(This is in addition to the existing `from datetime import datetime` — combine into one line: `from datetime import date, datetime`.)

Append at the end of the file:

```python
def calcular_precio_reajustado(precio_original, uf_fecha_compra, uf_hoy):
    factor = uf_hoy / uf_fecha_compra
    return round(precio_original * factor)


def consultar_item(texto_busqueda, ruta_excel=None, fecha_hoy=None):
    """Orquesta una consulta completa: carga Detalle, busca por texto,
    reajusta cada compra encontrada por UF, y agrega promedio/rango.
    fecha_hoy es inyectable para tests (default: date.today())."""
    hoy = fecha_hoy or date.today()
    items = cargar_items_detalle(ruta_excel)
    excluidos_count = sum(1 for it in items if it["excluido_motivo"] is not None)

    coincidencias, sugerencias = buscar_items(items, texto_busqueda)
    if not coincidencias:
        return {
            "encontrado": False,
            "compras": [],
            "promedio_reajustado": None,
            "rango_minimo": None,
            "rango_maximo": None,
            "excluidos_count": excluidos_count,
            "sugerencias": sugerencias,
        }

    uf_hoy = consultar_uf_api(hoy)
    cache_uf = cargar_cache_uf()
    compras = []
    for item in coincidencias:
        uf_compra = obtener_valor_uf(item["fecha"], cache_uf)
        precio_reajustado = calcular_precio_reajustado(
            item["precio_unitario_sin_iva"], uf_compra, uf_hoy,
        )
        compras.append({
            "n_ref": item["n_ref"],
            "fecha": item["fecha"].strftime("%Y-%m-%d"),
            "precio_original_sin_iva": item["precio_unitario_sin_iva"],
            "precio_reajustado_hoy": precio_reajustado,
        })
    guardar_cache_uf(cache_uf)

    reajustados = [c["precio_reajustado_hoy"] for c in compras]
    return {
        "encontrado": True,
        "compras": compras,
        "promedio_reajustado": round(sum(reajustados) / len(reajustados)),
        "rango_minimo": min(reajustados),
        "rango_maximo": max(reajustados),
        "excluidos_count": excluidos_count,
        "sugerencias": [],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/test_consultar_item.py" -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/" -v`
Expected: PASS (33 tests total, 0 failures, no network calls made — every test mocks `consultar_uf_api`/`urlopen`)

- [ ] **Step 6: Commit**

```bash
git add "Cotizador Historico/Sistema/cotizador_historico.py" "Cotizador Historico/Sistema/tests/test_consultar_item.py"
git commit -m "feat(cotizador-historico): reajuste por UF y orquestacion consultar_item"
```

---

### Task 5: `driver.py` skill + `SKILL.md`

**Files:**
- Create: `Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py`
- Create: `Cotizador Historico/.claude/skills/Cotizador_Historico/SKILL.md`

**Interfaces:**
- Consumes: `cotizador_historico.RUTA_EXCEL_CENTRO_COSTOS`, `cotizador_historico.ExcelNoDisponibleError`, `cotizador_historico.UFNoDisponibleError`, `cotizador_historico.cargar_items_detalle`, `cotizador_historico.cargar_cache_uf`, `cotizador_historico.RUTA_CACHE_UF`, `cotizador_historico.consultar_uf_api`, `cotizador_historico.consultar_item` (all from Tasks 1-4).
- Produces: CLI commands `status` and `consultar "<texto>"`, invoked as `python driver.py status` / `python driver.py consultar "<texto>"`.

There's no automated test for `driver.py` itself (it's a thin I/O wrapper, same as `Registro_Centro_de_Costos/driver.py`, which also has no direct unit test for its `main()`/`cmd_status()` print logic — see `Centro de Costos/Sistema/tests/`). It's verified manually in this task's steps and again in Task 6's final smoke test.

- [ ] **Step 1: Write `driver.py`**

Create `Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py`:

```python
# -*- coding: utf-8 -*-
"""
driver.py — arnes de ejecucion para la skill Cotizador_Historico.

No reimplementa la logica: importa cotizador_historico.py desde Sistema/ y
expone dos comandos, ambos de solo lectura sobre Centro de Costos.xlsx (este
modulo nunca lo escribe):

  status              -> Diagnostico: cuantos items indexables hay en
                          Detalle, cuantos quedan excluidos (sin fecha
                          resoluble via Master), cuantas fechas hay en el
                          cache de UF, y si hay conexion a mindicador.cl.

  consultar "<texto>" -> Busca el texto contra Nombre Item/Descripcion
                          (busqueda difusa) y muestra cada compra
                          encontrada con su precio original y su precio
                          reajustado a hoy por UF, mas promedio y rango.

Uso:
  python driver.py status
  python driver.py consultar "taladro"
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Sistema"))

sys.dont_write_bytecode = True
import cotizador_historico as ch  # noqa: E402


def cmd_status():
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    print("=" * 70)
    print("  ESTADO COTIZADOR HISTORICO (solo lectura, no escribe nada)")
    print("=" * 70)

    print(f"\nExcel Centro de Costos: {ch.RUTA_EXCEL_CENTRO_COSTOS}")
    print(f"  Existe: {ch.RUTA_EXCEL_CENTRO_COSTOS.exists()}")

    if not ch.RUTA_EXCEL_CENTRO_COSTOS.exists():
        print("\n[ERROR] No se encontro Centro de Costos.xlsx. Abortando status.")
        return 1

    try:
        items = ch.cargar_items_detalle()
    except ch.ExcelNoDisponibleError as exc:
        print(f"\n[ERROR] {exc}")
        return 1

    excluidos = [it for it in items if it["excluido_motivo"] is not None]
    print(f"\nItems indexables en Detalle: {len(items)}")
    print(f"  Excluidos (sin fecha resoluble via Master): {len(excluidos)}")

    cache = ch.cargar_cache_uf()
    print(f"\nCache UF ({ch.RUTA_CACHE_UF.name}): {len(cache)} fecha(s) guardadas")

    print("\nProbando conexion a mindicador.cl (UF de hoy)...")
    try:
        uf_hoy = ch.consultar_uf_api(date.today())
        print(f"  OK. UF hoy = {uf_hoy}")
    except ch.UFNoDisponibleError as exc:
        print(f"  [WARN] Sin conexion o sin dato: {exc}")

    print("\n" + "=" * 70)
    print('  Nada fue escrito. Para consultar un item: python driver.py consultar "<texto>"')
    print("=" * 70)
    return 0


def cmd_consultar(args):
    if not args:
        print('Uso: python driver.py consultar "<texto a buscar>"')
        return 2

    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    texto = " ".join(args)

    try:
        resultado = ch.consultar_item(texto)
    except (ch.ExcelNoDisponibleError, ch.UFNoDisponibleError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    if not resultado["encontrado"]:
        print(f'No se encontraron compras para "{texto}".')
        if resultado["sugerencias"]:
            print("Quizas quisiste decir:")
            for s in resultado["sugerencias"]:
                print(f"  - {s}")
        return 0

    print(f'Compras encontradas para "{texto}":\n')
    for c in resultado["compras"]:
        print(
            f"  {c['n_ref']} ({c['fecha']}): "
            f"${c['precio_original_sin_iva']:,.0f} -> "
            f"${c['precio_reajustado_hoy']:,.0f} reajustado a hoy"
        )

    print(f"\nPromedio reajustado: ${resultado['promedio_reajustado']:,.0f}")
    print(f"Rango: ${resultado['rango_minimo']:,.0f} - ${resultado['rango_maximo']:,.0f}")

    if resultado["excluidos_count"]:
        print(
            f"\n[INFO] {resultado['excluidos_count']} item(s) de Detalle excluido(s) "
            "del indice por no tener fecha resoluble via Master."
        )
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "consultar"):
        print('Uso: python driver.py [status|consultar "<texto>"]')
        return 2
    if sys.argv[1] == "status":
        return cmd_status()
    return cmd_consultar(sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test `status` manually against the real Centro de Costos.xlsx**

Run: `python "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" status`
Expected: exit code `0`, output showing `Excel Centro de Costos: ... Existe: True`, a real count of `Items indexables en Detalle`, and either `OK. UF hoy = <numero>` or a `[WARN]` about connectivity (both are acceptable — this step is read-only and does not fail the task if there's no internet, but the Excel-reading part must succeed).

- [ ] **Step 3: Smoke-test `consultar` manually with a real item name from Centro de Costos**

Pick any `Nombre Ítem` value that actually exists in `Centro de Costos/Excel/Centro de Costos.xlsx` (check the `Detalle` sheet, or reuse a term already known from `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/MEMORY.md`) and run:

Run: `python "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" consultar "<ese nombre>"`
Expected: exit code `0`, either a list of `Compras encontradas` with a reajuste per line plus `Promedio reajustado`/`Rango`, or (if there's no network) an `[ERROR]` naming `UFNoDisponibleError` — in that second case, re-run once connectivity is confirmed before considering this step done.

- [ ] **Step 4: Write `SKILL.md`**

Create `Cotizador Historico/.claude/skills/Cotizador_Historico/SKILL.md`:

```markdown
---
name: Cotizador_Historico
description: Estima el costo actual de un ítem (material, equipo, herramienta) a partir de sus compras históricas en Centro de Costos, reajustando el precio por la variación de la UF entre la fecha de compra y hoy. Usar cuando el usuario pregunte cuánto debería costar algo hoy, pida una cotización aproximada basada en compras anteriores, o quiera saber el precio histórico reajustado de un ítem ya comprado.
---

# Cotizador Historico

Herramienta de línea de comandos (Python + openpyxl + `mindicador.cl`), de
**solo lectura** sobre `Centro de Costos/Excel/Centro de Costos.xlsx` — nunca
lo escribe. Todas las rutas de este documento son relativas a la raíz del
módulo (`Cotizador Historico/`), no a esta carpeta de skill. El driver vive
en `.claude/skills/Cotizador_Historico/driver.py`.

Ver `../../CLAUDE.md` para el diseño completo (fuente de datos, algoritmo de
búsqueda, reajuste por UF, alcance v1).

## Prerequisitos

```
python --version      # mismo interprete que usa Centro de Costos
python -c "import openpyxl; print(openpyxl.__version__)"   # 3.1.5
```

Requiere conexión a internet para consultar `mindicador.cl` en fechas que no
estén todavía en `Sistema/uf_cache.json` (la UF de "hoy" siempre se pide
fresca, nunca se cachea entre corridas).

## Comandos

**`status`** — solo lectura: cuenta ítems indexables en `Detalle`, cuántos
quedan excluidos (sin fecha resoluble vía `Master`), cuántas fechas hay en
el caché de UF, y prueba la conexión a `mindicador.cl`.

```
python ".claude/skills/Cotizador_Historico/driver.py" status
```

**`consultar "<texto>"`** — busca el texto contra `Nombre Ítem`/`Descripción`
de `Detalle` (búsqueda difusa) y muestra cada compra encontrada con su
precio original y su precio reajustado a hoy, más promedio y rango.

```
python ".claude/skills/Cotizador_Historico/driver.py" consultar "taladro"
```

Salida esperada (estructura estable; los números cambian según los datos
reales de Centro de Costos y la UF del día):

```
Compras encontradas para "taladro":

  UMAG-014 (2026-03-10): $90,000 -> $94,200 reajustado a hoy
  UMAG-021 (2026-05-02): $85,000 -> $87,100 reajustado a hoy

Promedio reajustado: $90,650
Rango: $87,100 - $94,200
```

Si no hay match: `No se encontraron compras para "<texto>".`, con una lista
de sugerencias si hubo coincidencias de similitud baja.

## Uso conversacional

El agente puede responder la consulta directamente en el chat (ej. "¿cuánto
debería costar hoy un taladro?") invocando la misma lógica de
`Sistema/cotizador_historico.py` (función `consultar_item`), sin pasar por
el driver — igual que `/Registro_Centro_de_Costos` puede correr `status`/`run`
conversacionalmente.

## Gotchas

- **Depende de que `Centro de Costos.xlsx` tenga la estructura actual**
  (encabezados en la fila 1 de `Detalle`/`Master`, columna `Fecha` como
  fecha real en `Master`, no texto) — si Centro de Costos cambia su esquema,
  hay que revisar `mapear_encabezados`.
- **La UF de "hoy" nunca se cachea entre corridas** — cada consulta pide un
  valor fresco a `mindicador.cl` para la fecha de hoy, aunque los valores
  históricos de las compras sí queden en `Sistema/uf_cache.json`
  indefinidamente (no cambian una vez publicados).
- **Sin cotizaciones todavía**: este cotizador solo ve compras ya
  realizadas (Factura/Boleta/Guía de Despacho en Centro de Costos), no
  presupuestos. Ver "Alcance actual (v1)" en `../../CLAUDE.md`.
- **Ítems sin fecha resoluble quedan fuera silenciosamente del índice** —
  `status` reporta cuántos son; si un ítem que debería aparecer no
  aparece en una búsqueda, revisar primero si está en ese conteo de
  excluidos.

## Troubleshooting

| Síntoma | Causa / fix |
|---|---|
| `[ERROR] No existe .../Centro de Costos.xlsx` | Confirmar que `Centro de Costos/Excel/Centro de Costos.xlsx` existe y no se movió/renombró |
| `UFNoDisponibleError` al consultar | Sin conexión a internet, o `mindicador.cl` no tiene dato para esa fecha (ej. fecha futura) — revisar la fecha del ítem en Master |
| Un ítem que sé que existe no aparece en `consultar` | Correr `status`: revisar el conteo de "Excluidos" — probablemente su `N° Ref.` no tiene fila en `Master`, o su `Fecha` no es una fecha válida |
| `ModuleNotFoundError: No module named 'openpyxl'` | `pip install openpyxl` |
```

- [ ] **Step 5: Commit**

```bash
git add "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" "Cotizador Historico/.claude/skills/Cotizador_Historico/SKILL.md"
git commit -m "feat(cotizador-historico): driver.py (status/consultar) + SKILL.md"
```

---

### Task 6: Module `CLAUDE.md` and final verification

**Files:**
- Create: `Cotizador Historico/CLAUDE.md`
- Modify: `Finanzas QUEMPIN/CLAUDE.md:14` (the module table — add a row for Cotizador Historico)

**Interfaces:**
- Consumes: everything from Tasks 1-5 (this task only documents and cross-links; no new code).

- [ ] **Step 1: Write `Cotizador Historico/CLAUDE.md`**

Create `Cotizador Historico/CLAUDE.md`:

```markdown
# CLAUDE.md

## Qué es este módulo

`Cotizador Historico` estima el costo actual de un ítem (material, equipo,
herramienta) a partir de sus compras registradas en el módulo **Centro de
Costos**, reajustando cada precio histórico por la variación de la UF entre
la fecha de esa compra y la fecha de la consulta. Es de **solo lectura**:
nunca escribe `Centro de Costos.xlsx` ni ningún otro archivo de ese módulo.

Ver `../CLAUDE.md` (raíz de `Finanzas QUEMPIN/`) para el contexto general de
los módulos financieros de QUEMPIN SpA, y `../Centro de Costos/CLAUDE.md`
para el detalle de la estructura de `Centro de Costos.xlsx` que este módulo
consume.

## Alcance actual (v1)

- Única fuente de datos: hojas `Detalle` (ítems de línea) + `Master`
  (fecha por documento) de `Centro de Costos/Excel/Centro de Costos.xlsx`,
  cruzadas por `N° Ref.`.
- El precio base de cada ítem es `P. Unitario sin IVA` (comparable entre
  compras de distinta cantidad).
- El reajuste es solo por UF (no IPC, no dólar) — valores obtenidos de la
  API pública `mindicador.cl`, con caché local de fechas históricas en
  `Sistema/uf_cache.json`. La UF del día de la consulta nunca se cachea
  entre corridas — siempre se pide fresca.
- Búsqueda de ítem por texto: difusa (`difflib`, stdlib) contra `Nombre
  Ítem` y `Descripción` de `Detalle`, sin dependencias nuevas.
- **Sin respaldo por categoría**: si no hay match de nombre, la respuesta es
  "no encontrado" (con sugerencias de baja similitud si las hay) — decisión
  explícita del usuario para v1, no un olvido.
- **No incluye cotizaciones** (presupuestos no comprados) — no existen hoy
  en un formato estructurado. Si aparecen más adelante, se integrarían como
  una fuente adicional junto a Centro de Costos, no reemplazándola (ver spec
  de diseño).

Diseño completo, incluyendo las alternativas consideradas:
[`docs/superpowers/specs/2026-07-17-cotizador-historico-design.md`](docs/superpowers/specs/2026-07-17-cotizador-historico-design.md).

## Estructura del módulo

```
Cotizador Historico/
├── CLAUDE.md                              # este archivo
├── docs/superpowers/                      # specs/plans de Claude Code
├── Sistema/
│   ├── cotizador_historico.py             # lógica: leer Excel, indexar, fuzzy search, reajuste UF
│   ├── uf_cache.json                      # caché fecha ISO -> valor UF (se crea solo en la primera corrida)
│   └── tests/                             # tests de pytest
└── .claude/
    └── skills/
        └── Cotizador_Historico/
            ├── SKILL.md
            └── driver.py                  # comandos: status | consultar "<texto>"
```

## Cómo se usa

Como skill de Claude Code: pedirlo conversacionalmente (ej. "¿cuánto
debería costar hoy un taladro?") o correr el driver directamente. Ver
[`.claude/skills/Cotizador_Historico/SKILL.md`](.claude/skills/Cotizador_Historico/SKILL.md)
para los comandos (`status`/`consultar`) y ejemplos de salida.

## Funciones clave de `Sistema/cotizador_historico.py`

- `cargar_items_detalle(ruta_excel=None)` — lee `Detalle`+`Master`, resuelve
  la fecha de cada ítem vía `N° Ref.`; ítems sin `Master` correspondiente o
  con fecha no parseable quedan con `excluido_motivo` poblado (`"sin_master"`
  o `"fecha_invalida"`) y no entran a ninguna búsqueda ni agregación.
- `buscar_items(items, texto_busqueda)` — búsqueda difusa contra `Nombre
  Ítem`/`Descripción`; devuelve `(coincidencias, sugerencias)`.
- `obtener_valor_uf(fecha, cache_uf)` / `consultar_uf_api(fecha)` — UF
  histórica cacheada localmente; la UF de "hoy" se pide siempre fresca vía
  `consultar_uf_api` directo (no pasa por el caché de archivo).
- `consultar_item(texto_busqueda, ruta_excel=None, fecha_hoy=None)` —
  orquesta todo lo anterior y devuelve el resultado completo: compras
  individuales, promedio, rango, y sugerencias si no hubo match.

## Precauciones

- Este módulo **nunca escribe** `Centro de Costos.xlsx` — si necesitas que
  se actualice, corre el módulo Centro de Costos
  (`/Registro_Centro_de_Costos`), no este.
- Depende de que `Centro de Costos/Excel/Centro de Costos.xlsx` exista con
  su estructura actual (hojas `Detalle`/`Master`, encabezados en fila 1,
  `Fecha` de `Master` como fecha real, no texto) — si `Centro de
  Costos/CLAUDE.md` documenta un cambio de esquema, revisar
  `mapear_encabezados`/`cargar_items_detalle` acá.
- Requiere conexión a internet para fechas de UF que no estén ya en
  `Sistema/uf_cache.json` (incluida siempre la UF de hoy). Sin conexión,
  esas compras quedan fuera del resultado con un aviso claro — nunca se
  inventa un valor de UF.
- `Sistema/uf_cache.json` contiene solo valores públicos de UF (no datos
  financieros de la empresa) — a diferencia de los datos de Centro de
  Costos, no es sensible.
```

- [ ] **Step 2: Link the new module from the root `CLAUDE.md`**

Read `Finanzas QUEMPIN/CLAUDE.md` around line 14 first to confirm the exact current table text, then replace the module table row for "Flujo de Caja" (still "No iniciado") by adding a new row above it for Cotizador Historico. The table currently reads:

```markdown
| Módulo | Estado | Documentación |
|---|---|---|
| [Centro de Costos/](Centro%20de%20Costos/CLAUDE.md) | Implementado | `Centro de Costos/CLAUDE.md` |
| Flujo de Caja | No iniciado | — |
```

Change it to:

```markdown
| Módulo | Estado | Documentación |
|---|---|---|
| [Centro de Costos/](Centro%20de%20Costos/CLAUDE.md) | Implementado | `Centro de Costos/CLAUDE.md` |
| [Cotizador Historico/](Cotizador%20Historico/CLAUDE.md) | Implementado | `Cotizador Historico/CLAUDE.md` |
| Flujo de Caja | No iniciado | — |
```

- [ ] **Step 3: Run the full test suite one last time**

Run: `python -m pytest "Cotizador Historico/Sistema/tests/" -v`
Expected: PASS (33 tests, 0 failures)

- [ ] **Step 4: Re-run the manual driver smoke tests from Task 5 to confirm nothing broke**

Run: `python "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" status`
Expected: same shape of output as Task 5 Step 2 (exit code `0`).

- [ ] **Step 5: Commit**

```bash
git add "Cotizador Historico/CLAUDE.md" "CLAUDE.md"
git commit -m "docs(cotizador-historico): CLAUDE.md del modulo y enlace desde la raiz"
```
