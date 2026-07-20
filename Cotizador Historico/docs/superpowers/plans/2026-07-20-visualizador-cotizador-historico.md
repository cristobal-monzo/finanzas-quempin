# Visualizador Web de Cotizador Historico — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Cotizador Historico web visualizador — a searchable index of historical purchases with UF-adjusted pricing, a session-only cart, and a text export grouped by Materiales/Equipos/Otros — following the exact architecture, branding, and password of the existing Centro de Costos visualizador.

**Architecture:** Same pattern as `Centro de Costos/Visualizador Web/`: a versioned `template.html` (structure/CSS/JS, no data) + a versioned `build_visualizador.py` (reads `Centro de Costos.xlsx`, fetches today's UF once, embeds a base64 JSON snapshot into the template) producing a self-contained `build/index.html`. All search/cart/spec-parsing logic runs client-side in JS against the embedded snapshot — no network calls at runtime.

**Tech Stack:** Python 3 + openpyxl (backend, already a dependency of this module) + pytest (tests). Plain HTML/CSS/JS in the browser — no frameworks, no build step, no npm.

## Global Constraints

- Password gate: normalized value `combustion` (lowercase, accents stripped) — identical to Centro de Costos. Never show it in plaintext comments beyond what Centro de Costos' own template already does.
- Brand colors — only these 4 hex values, verbatim, anywhere in new CSS: `#ff5100` (Pantone Orange 021 C), `#000000` (Black C), `#98989a` (Cool Gray 7 C), `#54565a` (Cool Gray 11 C).
- Font: Lato, reused byte-for-byte from Centro de Costos' embedded base64 `@font-face` blocks — never re-encode or re-source it.
- `Cotizador Historico/Sistema/cotizador_historico.py` and `build_visualizador.py` are **read-only** over `Centro de Costos/Excel/Centro de Costos.xlsx` — never open it in write mode, never call `wb.save()` on it.
- The UF used for "costo revalorizado" is fixed at build time (fetched once from `mindicador.cl` by `build_visualizador.py`), never fetched by the published page at runtime — Artifacts have no generic external-fetch capability.
- The cart's "export" is a read-only `<textarea>` with tab-separated content plus a "Copiar todo" clipboard button — never a file download. (Superseded design note, kept for context: an Artifact-published page can only offer file downloads through the `downloads` capability, whose extension allowlist — `gif png jpg jpeg webp mp4 webm txt json md` — excludes `.xlsx`/`.csv`; the user decided against a `.txt` download entirely and asked for copy-paste instead, which also sidesteps that constraint.)
- The cart has **no persistence across sessions** — plain in-memory JS state only, never `localStorage`/`sessionStorage` for cart contents.
- `*/Visualizador Web/data/` and `*/Visualizador Web/build/` are already gitignored repo-wide — never force-add files under those paths.
- Spec: [`../specs/2026-07-20-visualizador-cotizador-historico-design.md`](../specs/2026-07-20-visualizador-cotizador-historico-design.md) — re-read it if a task below seems to contradict it.

---

### Task 1: Backend — enrich `cotizador_historico.py` for the visualizador

**Files:**
- Modify: `Cotizador Historico/Sistema/cotizador_historico.py`
- Test: `Cotizador Historico/Sistema/tests/test_lectura_excel.py`
- Test: `Cotizador Historico/Sistema/tests/test_consultar_item.py`
- Create: `Cotizador Historico/Sistema/tests/test_reajustar_todos.py`

**Interfaces:**
- Consumes: existing `mapear_encabezados(hoja)`, `_fechas_por_ref(ws_master)`, `obtener_valor_uf(fecha, cache_uf)`, `calcular_precio_reajustado(precio_original, uf_fecha_compra, uf_hoy)`, `tasa_iva_real(total_sin_iva, total_con_iva)`, `cargar_cache_uf(ruta_cache=None)`, `guardar_cache_uf(cache, ruta_cache=None)`, `UFNoDisponibleError`.
- Produces (for Task 2 to consume):
  - `cargar_items_detalle(ruta_excel=None)` — same signature/behavior as today, PLUS each returned item dict now also has keys `"categoria_item"`, `"proyecto"`, `"proveedor_tag"` (each `None` if the corresponding column doesn't exist in the workbook — never raises for their absence).
  - `reajustar_item(item, uf_hoy, cache_uf)` → `dict` with keys `n_ref, fecha (str "YYYY-MM-DD"), precio_original_sin_iva, precio_reajustado_hoy, precio_reajustado_hoy_con_iva`, or `None` if `obtener_valor_uf` raised `UFNoDisponibleError` for that item's fecha.
  - `reajustar_todos(items, uf_hoy, cache_uf=None)` → `(reajustados, sin_uf_count)` where `reajustados` is a `list[dict]` — each dict is the `reajustar_item` result merged with `nombre_item, descripcion, categoria_item, proyecto, proveedor_tag` from the source item — and `sin_uf_count` is an `int`. Skips items where `excluido_motivo is not None`. If `cache_uf` is `None`, loads/saves the on-disk cache itself (same file as `consultar_item`); if a `cache_uf` dict is passed in, mutates it and leaves persistence to the caller (this is what tests use, to avoid touching disk/network).

- [ ] **Step 1: Write failing tests for the `categoria_item`/`proyecto`/`proveedor_tag` enrichment**

Add to `Cotizador Historico/Sistema/tests/test_lectura_excel.py` (uses the existing `_crear_excel_prueba` helper already in that file — extend it to accept the two new optional columns via extra kwargs, keeping every existing call site working unchanged):

```python
def _crear_excel_prueba_enriquecido(tmp_path):
    """Detalle con 'Categoría Ítem', Master con 'Proyecto'/'Proveedor' —
    columnas que cargar_items_detalle debe leer si existen, sin exigirlas."""
    wb = openpyxl.Workbook()
    ws_detalle = wb.active
    ws_detalle.title = "Detalle"
    encabezados_d = [
        "N° Ref.", "Nombre Ítem", "Descripción", "Categoría Ítem",
        "P. Unitario sin IVA", "Total sin IVA (CLP)", "Total con IVA (CLP)",
    ]
    for c, h in enumerate(encabezados_d, 1):
        ws_detalle.cell(row=1, column=c, value=h)
    fila_d = ("UMAG-010", "Bomba", "Bomba centrífuga 1.5HP", "Equipos-Herramientas", 90000, 90000, 107100)
    for c, v in enumerate(fila_d, 1):
        ws_detalle.cell(row=2, column=c, value=v)

    ws_master = wb.create_sheet("Master")
    encabezados_m = ["N° Ref.", "Fecha", "Proyecto", "Proveedor"]
    for c, h in enumerate(encabezados_m, 1):
        ws_master.cell(row=1, column=c, value=h)
    fila_m = ("UMAG-010", datetime(2026, 3, 10), "UMAG", "Ferretería XYZ")
    for c, v in enumerate(fila_m, 1):
        ws_master.cell(row=2, column=c, value=v)

    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(ruta)
    return ruta


def test_cargar_items_detalle_incluye_categoria_proyecto_proveedor_si_existen(tmp_path):
    ruta = _crear_excel_prueba_enriquecido(tmp_path)
    items = ch.cargar_items_detalle(ruta)
    assert items[0]["categoria_item"] == "Equipos-Herramientas"
    assert items[0]["proyecto"] == "UMAG"
    assert items[0]["proveedor_tag"] == "Ferretería XYZ"


def test_cargar_items_detalle_categoria_proyecto_proveedor_none_si_no_existen(tmp_path):
    # _crear_excel_prueba (la funcion original, ya existente en este archivo)
    # NO tiene esas columnas -- deben quedar en None, nunca lanzar KeyError.
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, 90000, 107100)],
        filas_master=[("UMAG-001", datetime(2026, 1, 15))],
    )
    items = ch.cargar_items_detalle(ruta)
    assert items[0]["categoria_item"] is None
    assert items[0]["proyecto"] is None
    assert items[0]["proveedor_tag"] is None
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd "Cotizador Historico/Sistema" && python -m pytest tests/test_lectura_excel.py -k "categoria_proyecto_proveedor" -v`
Expected: FAIL — `KeyError: 'categoria_item'` (the dict has no such key yet).

- [ ] **Step 3: Implement the enrichment in `cargar_items_detalle`**

In `Cotizador Historico/Sistema/cotizador_historico.py`, add a new helper right after `_fechas_por_ref` and change `cargar_items_detalle` to use it plus an optional `categoria_item` column:

```python
def _proyecto_proveedor_por_ref(ws_master):
    """dict {n_ref: (proyecto, proveedor_tag)} -- ambas columnas son
    opcionales (None si Master no las tiene), a diferencia de N Ref./Fecha
    que _fechas_por_ref exige porque son estructurales."""
    cols = mapear_encabezados(ws_master)
    col_ref = cols["N° Ref."]
    col_proyecto = cols.get("Proyecto")
    col_proveedor = cols.get("Proveedor")
    meta = {}
    for fila in ws_master.iter_rows(min_row=2):
        n_ref = fila[col_ref - 1].value
        if n_ref:
            meta[n_ref] = (
                fila[col_proyecto - 1].value if col_proyecto else None,
                fila[col_proveedor - 1].value if col_proveedor else None,
            )
    return meta
```

Then in `cargar_items_detalle`, right after `fechas = _fechas_por_ref(ws_master)`, add `meta = _proyecto_proveedor_por_ref(ws_master)`; right after `col_total_con_iva = cols["Total con IVA (CLP)"]`, add `col_categoria = cols.get("Categoría Ítem")`; and in the `items.append({...})` call, add three keys:

```python
            proyecto, proveedor_tag = meta.get(n_ref, (None, None))
            items.append({
                "n_ref": n_ref,
                "nombre_item": fila[col_nombre - 1].value or "",
                "descripcion": fila[col_desc - 1].value or "",
                "categoria_item": fila[col_categoria - 1].value if col_categoria else None,
                "proyecto": proyecto,
                "proveedor_tag": proveedor_tag,
                "precio_unitario_sin_iva": precio,
                "total_sin_iva": fila[col_total_sin_iva - 1].value,
                "total_con_iva": fila[col_total_con_iva - 1].value,
                "fecha": fecha if excluido_motivo is None else None,
                "excluido_motivo": excluido_motivo,
            })
```

- [ ] **Step 4: Run tests to verify they pass, and that nothing else broke**

Run: `cd "Cotizador Historico/Sistema" && python -m pytest tests/ -v`
Expected: PASS — all tests including the two new ones and every pre-existing test in `test_lectura_excel.py`, `test_consultar_item.py`, `test_busqueda.py`, `test_uf.py`.

- [ ] **Step 5: Commit**

```bash
git add "Cotizador Historico/Sistema/cotizador_historico.py" "Cotizador Historico/Sistema/tests/test_lectura_excel.py"
git commit -m "feat(cotizador-historico): categoria_item/proyecto/proveedor_tag opcionales en cargar_items_detalle"
```

- [ ] **Step 6: Write failing tests for `reajustar_item`**

Add to `Cotizador Historico/Sistema/tests/test_consultar_item.py` (reuses the existing `_item(...)` helper and `_mapa_uf` already in that file):

```python
# ── reajustar_item ───────────────────────────────────────────────────────

def test_reajustar_item_calcula_precio_y_fecha_string():
    item = _item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1))
    cache = {"2026-01-01": 36000.0}
    compra = ch.reajustar_item(item, 39000.0, cache)
    assert compra == {
        "n_ref": "UMAG-001",
        "fecha": "2026-01-01",
        "precio_original_sin_iva": 90000,
        "precio_reajustado_hoy": round(90000 * 39000 / 36000),
        "precio_reajustado_hoy_con_iva": round(90000 * 39000 / 36000),
    }


def test_reajustar_item_aplica_tasa_iva_real():
    item = _item("CCON-002", "Guante", "Guante de cuero natural", 2513, datetime(2026, 1, 1),
                 total_sin_iva=2513, total_con_iva=2990)
    cache = {"2026-01-01": 36000.0}
    compra = ch.reajustar_item(item, 39000.0, cache)
    esperado_sin_iva = ch.calcular_precio_reajustado(2513, 36000.0, 39000.0)
    esperado_con_iva = round(esperado_sin_iva * ch.tasa_iva_real(2513, 2990))
    assert compra["precio_reajustado_hoy"] == esperado_sin_iva
    assert compra["precio_reajustado_hoy_con_iva"] == esperado_con_iva


def test_reajustar_item_devuelve_none_si_uf_no_disponible(monkeypatch):
    item = _item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1))
    def _falla(fecha, cache):
        raise ch.UFNoDisponibleError("simulado")
    monkeypatch.setattr(ch, "obtener_valor_uf", _falla)
    assert ch.reajustar_item(item, 39000.0, {}) is None
```

- [ ] **Step 7: Run to verify failure**

Run: `cd "Cotizador Historico/Sistema" && python -m pytest tests/test_consultar_item.py -k reajustar_item -v`
Expected: FAIL — `AttributeError: module 'cotizador_historico' has no attribute 'reajustar_item'`.

- [ ] **Step 8: Extract `reajustar_item` and refactor `consultar_item` to use it**

In `cotizador_historico.py`, add this new function right before `consultar_item`:

```python
def reajustar_item(item, uf_hoy, cache_uf):
    """Reajusta un item de cargar_items_detalle a la UF de hoy. Devuelve el
    dict de compra reajustada, o None si no se pudo obtener la UF de la
    fecha de compra (UFNoDisponibleError) -- el llamador decide como contar
    ese caso (ver consultar_item y reajustar_todos)."""
    try:
        uf_compra = obtener_valor_uf(item["fecha"], cache_uf)
    except UFNoDisponibleError:
        return None
    precio_reajustado = calcular_precio_reajustado(item["precio_unitario_sin_iva"], uf_compra, uf_hoy)
    tasa_iva = tasa_iva_real(item.get("total_sin_iva"), item.get("total_con_iva"))
    return {
        "n_ref": item["n_ref"],
        "fecha": item["fecha"].strftime("%Y-%m-%d"),
        "precio_original_sin_iva": item["precio_unitario_sin_iva"],
        "precio_reajustado_hoy": precio_reajustado,
        "precio_reajustado_hoy_con_iva": round(precio_reajustado * tasa_iva),
    }
```

Then replace the body of the `for item in coincidencias:` loop inside `consultar_item` (currently duplicating this exact logic) with:

```python
    for item in coincidencias:
        compra = reajustar_item(item, uf_hoy, cache_uf)
        if compra is None:
            sin_uf_count += 1
            continue
        compras.append(compra)
```

- [ ] **Step 9: Run tests to verify the new tests pass AND `consultar_item`'s existing tests still pass unchanged**

Run: `cd "Cotizador Historico/Sistema" && python -m pytest tests/test_consultar_item.py -v`
Expected: PASS — every test in the file, including all pre-existing `test_consultar_item_*` tests (this confirms the refactor didn't change `consultar_item`'s output).

- [ ] **Step 10: Commit**

```bash
git add "Cotizador Historico/Sistema/cotizador_historico.py" "Cotizador Historico/Sistema/tests/test_consultar_item.py"
git commit -m "refactor(cotizador-historico): extraer reajustar_item de consultar_item"
```

- [ ] **Step 11: Write failing tests for `reajustar_todos`**

Create `Cotizador Historico/Sistema/tests/test_reajustar_todos.py`:

```python
from datetime import datetime

import cotizador_historico as ch


def _item(n_ref, nombre, descripcion, precio, fecha, excluido=None,
          categoria_item=None, proyecto=None, proveedor_tag=None):
    return {
        "n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
        "precio_unitario_sin_iva": precio, "fecha": fecha, "excluido_motivo": excluido,
        "total_sin_iva": precio, "total_con_iva": precio,
        "categoria_item": categoria_item, "proyecto": proyecto, "proveedor_tag": proveedor_tag,
    }


def test_reajustar_todos_incluye_metadata_de_producto():
    items = [_item("UMAG-014", "Bomba", "Bomba centrífuga 1.5HP", 90000, datetime(2026, 1, 1),
                    categoria_item="Equipos-Herramientas", proyecto="UMAG", proveedor_tag="Ferretería XYZ")]
    cache = {"2026-01-01": 36000.0}

    reajustados, sin_uf_count = ch.reajustar_todos(items, 39000.0, cache)

    assert sin_uf_count == 0
    assert len(reajustados) == 1
    r = reajustados[0]
    assert r["n_ref"] == "UMAG-014"
    assert r["nombre_item"] == "Bomba"
    assert r["descripcion"] == "Bomba centrífuga 1.5HP"
    assert r["categoria_item"] == "Equipos-Herramientas"
    assert r["proyecto"] == "UMAG"
    assert r["proveedor_tag"] == "Ferretería XYZ"
    assert r["precio_reajustado_hoy"] == round(90000 * 39000 / 36000)


def test_reajustar_todos_omite_items_excluidos():
    items = [
        _item("UMAG-014", "Bomba", "Bomba centrífuga 1.5HP", 90000, datetime(2026, 1, 1)),
        _item("UMAG-015", "Cemento", "Saco 25kg", 5000, None, excluido="sin_master"),
    ]
    cache = {"2026-01-01": 36000.0}

    reajustados, sin_uf_count = ch.reajustar_todos(items, 39000.0, cache)

    assert len(reajustados) == 1
    assert reajustados[0]["n_ref"] == "UMAG-014"


def test_reajustar_todos_cuenta_items_sin_uf_disponible(monkeypatch):
    items = [_item("UMAG-014", "Bomba", "Bomba centrífuga 1.5HP", 90000, datetime(2026, 1, 1))]

    def _falla(fecha, cache):
        raise ch.UFNoDisponibleError("simulado")
    monkeypatch.setattr(ch, "obtener_valor_uf", _falla)

    reajustados, sin_uf_count = ch.reajustar_todos(items, 39000.0, {})

    assert reajustados == []
    assert sin_uf_count == 1


def test_reajustar_todos_usa_cache_propio_si_no_se_pasa_uno(monkeypatch, tmp_path):
    items = [_item("UMAG-014", "Bomba", "Bomba centrífuga 1.5HP", 90000, datetime(2026, 1, 1))]
    ruta_cache = tmp_path / "uf_cache.json"
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", ruta_cache)
    monkeypatch.setattr(ch, "consultar_uf_api", lambda fecha: 36000.0)

    ch.reajustar_todos(items, 39000.0)  # cache_uf no provisto

    assert ch.cargar_cache_uf(ruta_cache) == {"2026-01-01": 36000.0}
```

- [ ] **Step 12: Run to verify failure**

Run: `cd "Cotizador Historico/Sistema" && python -m pytest tests/test_reajustar_todos.py -v`
Expected: FAIL — `AttributeError: module 'cotizador_historico' has no attribute 'reajustar_todos'`.

- [ ] **Step 13: Implement `reajustar_todos`**

Add to `cotizador_historico.py`, right after `reajustar_item`:

```python
def reajustar_todos(items, uf_hoy, cache_uf=None):
    """Reajusta TODOS los items indexables (excluido_motivo is None) a la
    UF de hoy, sin filtrar por texto de busqueda -- lo usa el visualizador
    web, que necesita el indice completo, no solo los resultados de una
    consulta puntual. Devuelve (reajustados, sin_uf_count); cada dict de
    reajustados trae ademas nombre_item/descripcion/categoria_item/
    proyecto/proveedor_tag del item original, para no tener que volver a
    cruzarlos despues.

    Si cache_uf es None, carga y persiste el cache de disco el mismo que
    usa consultar_item; si se pasa un dict ya cargado (tests, o un
    llamador que quiere controlar el I/O), se muta in-place y no se
    persiste aqui -- mismo contrato que obtener_valor_uf."""
    propio_cache = cache_uf is None
    if propio_cache:
        cache_uf = cargar_cache_uf()

    reajustados = []
    sin_uf_count = 0
    for item in items:
        if item["excluido_motivo"] is not None:
            continue
        compra = reajustar_item(item, uf_hoy, cache_uf)
        if compra is None:
            sin_uf_count += 1
            continue
        compra["nombre_item"] = item["nombre_item"]
        compra["descripcion"] = item["descripcion"]
        compra["categoria_item"] = item.get("categoria_item")
        compra["proyecto"] = item.get("proyecto")
        compra["proveedor_tag"] = item.get("proveedor_tag")
        reajustados.append(compra)

    if propio_cache:
        guardar_cache_uf(cache_uf)
    return reajustados, sin_uf_count
```

- [ ] **Step 14: Run tests to verify they pass**

Run: `cd "Cotizador Historico/Sistema" && python -m pytest tests/ -v`
Expected: PASS — every test in the whole `Sistema/tests/` directory.

- [ ] **Step 15: Commit**

```bash
git add "Cotizador Historico/Sistema/cotizador_historico.py" "Cotizador Historico/Sistema/tests/test_reajustar_todos.py"
git commit -m "feat(cotizador-historico): reajustar_todos para indexar todo el catalogo a la UF de hoy"
```

---

### Task 2: `build_visualizador.py` — export + embed

**Files:**
- Create: `Cotizador Historico/Visualizador Web/build_visualizador.py`
- Create: `Cotizador Historico/Visualizador Web/tests/conftest.py`
- Create: `Cotizador Historico/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Consumes: `ch.cargar_items_detalle(ruta_excel=None)`, `ch.reajustar_todos(items, uf_hoy, cache_uf=None)`, `ch.consultar_uf_api(fecha)`, `ch.RUTA_EXCEL_CENTRO_COSTOS` (all from Task 1).
- Produces (for Task 5 to consume as the embedded `DATA` object in the browser):
  - `extraer_indice_saneado(ruta_excel=None, fecha_hoy=None)` → `dict` with keys `generado (str), uf_hoy (float), uf_fecha (str "YYYY-MM-DD HH:MM"), excluidos_count (int), sin_uf_count (int), items (list[dict])`. Each item dict has exactly the keys `reajustar_todos` produces: `n_ref, fecha, precio_original_sin_iva, precio_reajustado_hoy, precio_reajustado_hoy_con_iva, nombre_item, descripcion, categoria_item, proyecto, proveedor_tag`.
  - `build()` → `int` exit code (0 success, 1 on missing Excel/template), writes `data/cotizador-historico.json` and `build/index.html`, prints a status summary. `fecha_hoy` param exists only so tests can inject a fixed value — `build()` itself always calls with `fecha_hoy=None` (real "today").

- [ ] **Step 1: Write failing tests**

Create `Cotizador Historico/Visualizador Web/tests/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Sistema"))
```

Create `Cotizador Historico/Visualizador Web/tests/test_build_visualizador.py`:

```python
from datetime import date, datetime

import openpyxl

import build_visualizador as bv

HEADERS_MASTER = ["N° Ref.", "Fecha", "Proyecto", "Proveedor"]
HEADERS_DETALLE = [
    "N° Ref.", "Nombre Ítem", "Descripción", "Categoría Ítem",
    "P. Unitario sin IVA", "Total sin IVA (CLP)", "Total con IVA (CLP)",
]


def _wb_con_dos_items(tmp_path):
    wb = openpyxl.Workbook()
    ws_master = wb.active
    ws_master.title = "Master"
    for c, h in enumerate(HEADERS_MASTER, 1):
        ws_master.cell(row=1, column=c, value=h)
    filas_master = [
        ("UMAG-014", datetime(2026, 1, 1), "UMAG", "Ferretería XYZ"),
        ("UMAG-020", datetime(2026, 1, 1), "UMAG", "Ferretería XYZ"),
    ]
    for r, fila in enumerate(filas_master, 2):
        for c, v in enumerate(fila, 1):
            ws_master.cell(row=r, column=c, value=v)

    ws_detalle = wb.create_sheet("Detalle")
    for c, h in enumerate(HEADERS_DETALLE, 1):
        ws_detalle.cell(row=1, column=c, value=h)
    filas_detalle = [
        ("UMAG-014", "Bomba", "Bomba centrífuga Pedrollo 1.5HP", "Equipos-Herramientas", 90000, 90000, 107100),
        ("UMAG-020", "Brocha", "Brocha 4 pulgadas", "Materiales", 3000, 3000, 3570),
    ]
    for r, fila in enumerate(filas_detalle, 2):
        for c, v in enumerate(fila, 1):
            ws_detalle.cell(row=r, column=c, value=v)

    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(str(ruta))
    return ruta


def test_extraer_indice_saneado_incluye_todos_los_items(tmp_path, monkeypatch):
    ruta = _wb_con_dos_items(tmp_path)
    monkeypatch.setattr(bv.ch, "consultar_uf_api", lambda fecha: 36000.0)
    monkeypatch.setattr(bv.ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")

    data = bv.extraer_indice_saneado(ruta, fecha_hoy=date(2026, 7, 20))

    assert len(data["items"]) == 2
    nombres = sorted(it["nombre_item"] for it in data["items"])
    assert nombres == ["Bomba", "Brocha"]
    assert data["uf_hoy"] == 36000.0
    assert data["excluidos_count"] == 0
    assert data["sin_uf_count"] == 0


def test_extraer_indice_saneado_conserva_categoria_proyecto_proveedor(tmp_path, monkeypatch):
    ruta = _wb_con_dos_items(tmp_path)
    monkeypatch.setattr(bv.ch, "consultar_uf_api", lambda fecha: 36000.0)
    monkeypatch.setattr(bv.ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")

    data = bv.extraer_indice_saneado(ruta, fecha_hoy=date(2026, 7, 20))

    bomba = next(it for it in data["items"] if it["nombre_item"] == "Bomba")
    assert bomba["categoria_item"] == "Equipos-Herramientas"
    assert bomba["proyecto"] == "UMAG"
    assert bomba["proveedor_tag"] == "Ferretería XYZ"
    assert bomba["precio_reajustado_hoy"] == 90000  # UF sin cambio (36000 -> 36000)


def test_build_escribe_snapshot_json_y_html(tmp_path, monkeypatch):
    ruta_excel = _wb_con_dos_items(tmp_path)
    monkeypatch.setattr(bv.ch, "consultar_uf_api", lambda fecha: 36000.0)
    monkeypatch.setattr(bv.ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")
    monkeypatch.setattr(bv, "RUTA_EXCEL", ruta_excel)
    ruta_data = tmp_path / "data" / "cotizador-historico.json"
    ruta_build = tmp_path / "build" / "index.html"
    monkeypatch.setattr(bv, "RUTA_DATA_JSON", ruta_data)
    monkeypatch.setattr(bv, "RUTA_BUILD_HTML", ruta_build)

    codigo = bv.build()

    assert codigo == 0
    assert ruta_data.exists()
    assert ruta_build.exists()
    html = ruta_build.read_text(encoding="utf-8")
    assert "__CH_DATA_B64__" not in html  # el placeholder se reemplazo
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "Cotizador Historico/Visualizador Web" && python -m pytest tests/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_visualizador'`.

- [ ] **Step 3: Implement `build_visualizador.py`**

Create `Cotizador Historico/Visualizador Web/build_visualizador.py`:

```python
# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el visualizador web de Cotizador Historico.

Mismo patron que Centro de Costos/Visualizador Web/build_visualizador.py:
lee Centro de Costos.xlsx (solo lectura), pide la UF de hoy UNA vez, y
embebe un snapshot saneado dentro de template.html para producir un
build/index.html autocontenido (un solo archivo, sin servidor).

Salidas (gitignoradas, se regeneran completas en cada corrida):
  data/cotizador-historico.json  -- snapshot saneado intermedio (auditable)
  build/index.html                -- visualizador final con datos incrustados

Uso:
  python build_visualizador.py
  (o, desde el driver de la skill: python driver.py visualizador)
"""

import base64
import io
import json
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent            # Cotizador Historico/Visualizador Web/
RAIZ_MODULO = RAIZ.parent                          # Cotizador Historico/
sys.path.insert(0, str(RAIZ_MODULO / "Sistema"))
import cotizador_historico as ch  # noqa: E402

RUTA_EXCEL = ch.RUTA_EXCEL_CENTRO_COSTOS
RUTA_TEMPLATE = RAIZ / "template.html"
RUTA_DATA_JSON = RAIZ / "data" / "cotizador-historico.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"


def extraer_indice_saneado(ruta_excel=None, fecha_hoy=None):
    """Lee Detalle+Master (via cargar_items_detalle) y reajusta TODO el
    catalogo indexable a la UF de hoy (via reajustar_todos), pedida UNA
    sola vez -- nunca una por item. fecha_hoy es inyectable para tests
    (default: date.today())."""
    hoy = fecha_hoy or date.today()
    items = ch.cargar_items_detalle(ruta_excel)
    excluidos_count = sum(1 for it in items if it["excluido_motivo"] is not None)

    uf_hoy = ch.consultar_uf_api(hoy)
    reajustados, sin_uf_count = ch.reajustar_todos(items, uf_hoy)

    return {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "uf_hoy": uf_hoy,
        "uf_fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "excluidos_count": excluidos_count,
        "sin_uf_count": sin_uf_count,
        "items": reajustados,
    }


def build():
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

    data = extraer_indice_saneado(RUTA_EXCEL)

    RUTA_DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    with io.open(RUTA_DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    data_json_text = json.dumps(data, ensure_ascii=False)
    data_b64 = base64.b64encode(data_json_text.encode("utf-8")).decode("ascii")

    with io.open(RUTA_TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read()
    if "__CH_DATA_B64__" not in template:
        print("[ERROR] template.html no tiene el placeholder __CH_DATA_B64__")
        return 1
    html = template.replace("__CH_DATA_B64__", data_b64)

    RUTA_BUILD_HTML.parent.mkdir(parents=True, exist_ok=True)
    with io.open(RUTA_BUILD_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK — {len(data['items'])} referencias indexadas, "
          f"UF utilizada ${data['uf_hoy']:,.2f}".replace(",", "."))
    print(f"Excluidos (sin fecha/precio valido): {data['excluidos_count']}")
    print(f"Sin UF disponible para su fecha de compra: {data['sin_uf_count']}")
    print(f"Snapshot: {RUTA_DATA_JSON}")
    print(f"Visualizador: {RUTA_BUILD_HTML}")
    print("Para verlo: publícalo como Claude Artifact o ábrelo directo en el navegador.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(build())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "Cotizador Historico/Visualizador Web" && python -m pytest tests/ -v`
Expected: FAIL at `test_build_escribe_snapshot_json_y_html` — `[ERROR] No existe la plantilla` (returns 1, not 0) — this is expected: `template.html` doesn't exist yet, that's Task 5. The two `extraer_indice_saneado` tests should already PASS.

Run just those two to confirm: `cd "Cotizador Historico/Visualizador Web" && python -m pytest tests/test_build_visualizador.py -k extraer_indice_saneado -v`
Expected: PASS.

- [ ] **Step 5: Commit (template.html arrives in Task 5 — the third test starts passing then, don't force it now)**

```bash
git add "Cotizador Historico/Visualizador Web/build_visualizador.py" "Cotizador Historico/Visualizador Web/tests/"
git commit -m "feat(cotizador-historico): build_visualizador.py (export + embed, sin template aun)"
```

---

### Task 3: Scaffold `template.html` (branding chrome reused from Centro de Costos)

**Files:**
- Create: `Cotizador Historico/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `Centro de Costos/Visualizador Web/template.html` (read as raw bytes/lines only, via the script below — never re-typed by hand) for fonts, CSS variables, header/gate markup, theme toggle, tooltip system, generic helpers (`fmt`, `fmtNum`, `fmtDate`, `esc`, `norm`), and `renderBarChart` (fully generic SVG bar chart, reused verbatim for Task 4's product chart).
- Produces (for Task 4 onward to extend): a working password-gated page with an `initApp(DATA)` function scope where `DATA` is the JSON object from Task 2, containing a `#kpiRow` mount and a footer — this is the insertion point every later task's JS/HTML gets added into, right before the final `} // end initApp\n})();\n</script>` closing.

This task does **not** hand-copy the 1200+ lines of Centro de Costos markup into this plan (its embedded Lato font alone is tens of thousands of characters on 3 single lines) — it runs a small one-off Python script that slices the *sibling, already-versioned* `Centro de Costos/Visualizador Web/template.html` by exact line ranges and reassembles only the generic/reusable parts. The script is not part of the shipped module; run it once and discard it.

- [ ] **Step 1: Run the scaffold script**

From the repository root (`Finanzas QUEMPIN/`), run this via `python -c` (or save to a temp `.py` and run it, then delete the temp file — either way, do not commit this script):

```python
from pathlib import Path

SRC = Path("Centro de Costos/Visualizador Web/template.html")
DST = Path("Cotizador Historico/Visualizador Web/template.html")

lines = SRC.read_text(encoding="utf-8").split("\n")

def rng(a, b):  # 1-based inclusive line numbers, matching a Read/grep view of SRC
    return lines[a - 1:b]

# ---- CSS: fonts + vars + reset + header + gate + KPI row + section-title +
# filterbar + charts-grid + tooltip/bar-rect hover + pagination + footer ----
css = rng(2, 204) + rng(244, 326) + rng(400, 418)

# ---- JS: data-script-tag + theme-persistence + gate + initApp-open +
# theme-toggle + fmt/fmtNum/fmtDate/esc + norm + tooltip show/move/hide +
# generic SVG bar chart (+truncateLabel/fadeIn/fmtCompact) ----
js_core = (
    rng(531, 632)
    + rng(666, 669)
    + ["  var HATCH_DEFS = '';"]
    + rng(806, 825)
    + rng(929, 980)
)
js_text = "\n".join(js_core)
js_text = (
    js_text.replace("cc_viz_theme", "ch_viz_theme")
    .replace("cc_viz_unlocked", "ch_viz_unlocked")
    .replace("cc-data-b64", "ch-data-b64")
    .replace("__CC_DATA_B64__", "__CH_DATA_B64__")
)

gate_html = (
    ['<div class="viz-gate" id="pwGate">', '  <form class="viz-gate-card" id="pwForm">']
    + rng(422, 422)
    + ['    <h2>Cotizador Historico — Visualizador</h2>']
    + rng(424, 428)
    + ['</div>', '']
)

header_html = (
    ['<div class="viz-root" id="vizRoot" style="display:none">',
     '  <header class="viz-header">',
     '    <div class="viz-container">',
     '      <div class="viz-logo">']
    + rng(435, 435)
    + ['        <div class="viz-wordmark">QUEMP<span class="in">IN</span></div>',
       '      </div>',
       '      <div class="viz-titleblock">',
       '        <h1>Cotizador Historico — Visualizador<span class="viz-testbadge">Prueba</span></h1>',
       '        <p id="vizGenerated">Datos actualizados al —</p>',
       '      </div>',
       '      <button class="viz-theme-toggle" id="themeToggle" type="button">Modo oscuro</button>',
       '    </div>',
       '  </header>',
       '']
)

body_html = [
    '  <div class="viz-container">',
    '    <div class="viz-kpis" id="kpiRow"></div>',
    '',
    '    <p class="viz-footer">',
    '      Cotizador Historico — datos reales de <strong>Centro de Costos.xlsx</strong>, reajustados a',
    '      la UF vigente al generar este archivo. Snapshot generado el <span id="vizGeneratedFooter">—</span>.',
    '      Artifact privado, no publicado. La contraseña de acceso es una barrera simple del lado del',
    '      cliente, no seguridad real — no compartas este link fuera del equipo.',
    '    </p>',
    '  </div>',
    '',
    '  <div class="viz-tooltip" id="vizTooltip"></div>',
    '</div>',
    '',
]

closing = (
    [
        "  document.getElementById('vizGenerated').innerHTML = 'UF utilizada <strong>' + fmt(DATA.uf_hoy) + '</strong> (actualizada ' + esc(DATA.uf_fecha) + ')';",
        "  document.getElementById('vizGeneratedFooter').textContent = DATA.generado;",
        "  function renderKPIs() {",
        "    var row = document.getElementById('kpiRow');",
        "    row.innerHTML =",
        "      '<div class=\"viz-kpi accent\"><div class=\"label\">Referencias indexadas</div><div class=\"value\">' + fmtNum(DATA.items.length) + '</div><div class=\"sub\">disponibles para buscar</div></div>' +",
        "      '<div class=\"viz-kpi\"><div class=\"label\">UF utilizada</div><div class=\"value\">' + fmt(DATA.uf_hoy) + '</div><div class=\"sub\">actualizada ' + esc(DATA.uf_fecha) + '</div></div>';",
        "  }",
        "  function render() { renderKPIs(); }",
        "  render();",
    ]
    + rng(1292, 1293)
    + ["</script>"]
)

out = (
    ["<title>Cotizador Historico — Visualizador (prueba)</title>"]
    + css
    + [""]
    + gate_html
    + header_html
    + body_html
    + [js_text]
    + closing
)

DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text("\n".join(out), encoding="utf-8")
print("Escrito:", DST, "-", len(out), "lineas de nivel superior ensambladas")
```

- [ ] **Step 2: Sanity-check the generated file structurally (without dumping its content — it still contains the huge embedded font lines)**

Run: `cd "Cotizador Historico/Visualizador Web" && python -c "
import re
t = open('template.html', encoding='utf-8').read()
assert '__CH_DATA_B64__' in t
assert t.count('@font-face') == 3
assert 'GATE_PASSWORD_NORM = \'combustion\'' in t
assert 'cc_viz_theme' not in t and 'cc-data-b64' not in t and '__CC_DATA_B64__' not in t
assert t.count('function initApp(DATA)') == 1
assert t.rstrip().endswith('</script>')
print('OK — estructura basica correcta')
"`
Expected: `OK — estructura basica correcta`. If any assertion fails, re-check the exact line ranges against a fresh `grep -n` of the source file (Centro de Costos' `template.html` may have shifted lines since this plan was written if it was edited in between — re-derive the ranges from content markers, not blindly trust the numbers above).

- [ ] **Step 3: Run the build and open it for a real visual check**

Run: `cd "Cotizador Historico/Visualizador Web" && python build_visualizador.py`
Expected: `OK — N referencias indexadas, UF utilizada $X` (uses the real `Centro de Costos.xlsx` and a real network call to `mindicador.cl` — requires internet).

Run: `cd "Cotizador Historico/Visualizador Web" && python -m pytest tests/ -v`
Expected: PASS — all three tests from Task 2, including `test_build_escribe_snapshot_json_y_html` which was failing before this task.

Then open `Cotizador Historico/Visualizador Web/build/index.html` directly in a browser (double-click, or `start build/index.html` on Windows) and confirm by eye: the black header shows "Cotizador Historico — Visualizador" with the QUEMPIN logo, the password gate asks for a password (enter `combustion`, it unlocks), the KPI row shows "Referencias indexadas" and "UF utilizada" with real numbers, the light/dark toggle works, and there are no errors in the browser console (F12).

- [ ] **Step 4: Commit**

```bash
git add "Cotizador Historico/Visualizador Web/template.html"
git commit -m "feat(cotizador-historico): scaffold de template.html (chrome de marca reutilizado de Centro de Costos)"
```

---

### Task 4: Initial state — Top-10 chart + product index table

**Files:**
- Modify: `Cotizador Historico/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `DATA.items` (from Task 2/3), `renderBarChart(containerId, items, labelKey, valueKey, colorMap)` (from Task 3's scaffold, generic), `fmt`, `fmtNum`, `esc`, `render()` (extended, not replaced).
- Produces: a `buildProductIndex(items)` function (groups `DATA.items` by `nombre_item`) that Task 5 will reuse to power "click a row → search that term."

- [ ] **Step 1: Add the charts-grid and product-index-table markup**

In `template.html`, insert this right after the `<div class="viz-kpis" id="kpiRow"></div>` line (inside `body_html`'s `.viz-container`):

```html
    <div class="viz-charts">
      <div class="viz-chartcard">
        <h3>Top 10 productos con más compras históricas</h3>
        <div id="chartTopProductos" class="viz-chart-mount"></div>
      </div>
    </div>

    <p class="viz-section-title">Índice de productos</p>
    <div class="viz-tablewrap">
      <div class="viz-tablescroll">
        <table class="viz-table" id="productTable">
          <thead>
            <tr>
              <th data-key="nombre_item" aria-sort="ascending">Producto <span class="arrow">▲</span></th>
              <th data-key="n_compras" class="num" aria-sort="none">N° de compras <span class="arrow"></span></th>
              <th data-key="rango_min" class="num" aria-sort="none">Precio reajustado mín. <span class="arrow"></span></th>
              <th data-key="rango_max" class="num" aria-sort="none">Precio reajustado máx. <span class="arrow"></span></th>
              <th>Proyectos</th>
            </tr>
          </thead>
          <tbody id="productTableBody"></tbody>
        </table>
      </div>
      <div class="viz-empty-state" id="productEmptyState" style="display:none">Sin productos indexados.</div>
    </div>
```

- [ ] **Step 2: Add the CSS this new markup needs**

The scaffold already kept `.viz-charts`/`.viz-chartcard` and the base `.viz-tablewrap`/`table.viz-table thead th`/`tbody td` rules — but not row hover/click styling (that was in the dropped CC-specific table CSS block). Add this right before the scaffold's `</style>` (i.e., append to the end of the CSS, right before the closing `</style>` tag):

```css
  table.viz-table tbody tr.clickable-row { cursor: pointer; }
  table.viz-table tbody tr.clickable-row:hover { background: var(--surface-1); }
  table.viz-table tbody tr.clickable-row:focus-visible { outline: 2px solid var(--brand-orange); outline-offset: -2px; }
  table.viz-table tbody td.num { text-align: right; font-variant-numeric: tabular-nums; }
```

- [ ] **Step 3: Implement `buildProductIndex`, the chart, and the table**

Inside `initApp(DATA)`, right before the `function render() { renderKPIs(); }` line added in Task 3, insert:

```javascript
  // ---------- product index (grouped by nombre_item) ----------
  function buildProductIndex(items) {
    var byName = {};
    items.forEach(function (it) {
      var key = it.nombre_item;
      if (!byName[key]) byName[key] = { nombre_item: key, compras: [], proyectos: {} };
      byName[key].compras.push(it);
      if (it.proyecto) byName[key].proyectos[it.proyecto] = true;
    });
    return Object.keys(byName).map(function (key) {
      var g = byName[key];
      var precios = g.compras.map(function (c) { return c.precio_reajustado_hoy; });
      return {
        nombre_item: key,
        n_compras: g.compras.length,
        rango_min: Math.min.apply(null, precios),
        rango_max: Math.max.apply(null, precios),
        proyectos: Object.keys(g.proyectos).sort(),
      };
    });
  }
  var PRODUCT_INDEX = buildProductIndex(DATA.items);
  var productSort = { key: 'n_compras', dir: 'desc' };

  function renderTopProductosChart() {
    var top10 = PRODUCT_INDEX.slice().sort(function (a, b) { return b.n_compras - a.n_compras; }).slice(0, 10);
    renderBarChart('chartTopProductos', top10, 'nombre_item', 'n_compras', null);
  }

  function renderProductTable() {
    var sorted = PRODUCT_INDEX.slice().sort(function (a, b) {
      var av = a[productSort.key], bv = b[productSort.key];
      var cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return productSort.dir === 'asc' ? cmp : -cmp;
    });
    var body = document.getElementById('productTableBody');
    var empty = document.getElementById('productEmptyState');
    if (!sorted.length) {
      body.innerHTML = '';
      empty.style.display = '';
      return;
    }
    empty.style.display = 'none';
    body.innerHTML = sorted.map(function (p) {
      return '<tr class="clickable-row" tabindex="0" data-nombre="' + esc(p.nombre_item) + '">' +
        '<td>' + esc(p.nombre_item) + '</td>' +
        '<td class="num">' + fmtNum(p.n_compras) + '</td>' +
        '<td class="num">' + fmt(p.rango_min) + '</td>' +
        '<td class="num">' + fmt(p.rango_max) + '</td>' +
        '<td>' + esc(p.proyectos.join(', ')) + '</td>' +
        '</tr>';
    }).join('');
    body.querySelectorAll('tr.clickable-row').forEach(function (tr) {
      function activar() { runSearch(tr.dataset.nombre); }
      tr.addEventListener('click', activar);
      tr.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activar(); } });
    });
  }
  document.querySelectorAll('#productTable thead th[data-key]').forEach(function (th) {
    th.addEventListener('click', function () {
      var key = th.dataset.key;
      if (productSort.key === key) { productSort.dir = productSort.dir === 'asc' ? 'desc' : 'asc'; }
      else { productSort.key = key; productSort.dir = key === 'nombre_item' ? 'asc' : 'desc'; }
      document.querySelectorAll('#productTable thead th[data-key]').forEach(function (h) {
        var arrow = h.querySelector('.arrow');
        var active = h.dataset.key === productSort.key;
        arrow.textContent = active ? (productSort.dir === 'asc' ? '▲' : '▼') : '';
        h.setAttribute('aria-sort', active ? (productSort.dir === 'asc' ? 'ascending' : 'descending') : 'none');
      });
      renderProductTable();
    });
  });
```

`runSearch` is defined in Task 5 — leave the reference as-is, it resolves once that task lands (both functions share the same `initApp` closure).

Then change the `render()` function (added in Task 3) to also draw these two:

```javascript
  function render() { renderKPIs(); renderTopProductosChart(); renderProductTable(); }
```

- [ ] **Step 4: Manual verification**

Run: `cd "Cotizador Historico/Visualizador Web" && python build_visualizador.py`, then open `build/index.html`, enter the password, and confirm: a bar chart titled "Top 10 productos..." renders with real product names, and below it a sortable table lists every distinct product with compra count and price range — clicking a column header re-sorts, clicking a row does nothing yet (expected — `runSearch` doesn't exist until Task 5, check the browser console shows a `ReferenceError` there and nowhere else before that point; that error is expected and temporary).

- [ ] **Step 5: Commit**

```bash
git add "Cotizador Historico/Visualizador Web/template.html"
git commit -m "feat(cotizador-historico): grafico top-10 y tabla indice de productos"
```

---

### Task 5: Client-side search engine + technical-spec parser

**Files:**
- Modify: `Cotizador Historico/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `DATA.items`, `norm` (renamed/reused as `normalizeText` — see below).
- Produces: `normalizeText(s)`, `similitud(a, b)`, `buscarItems(items, texto)` → `{coincidencias, sugerencias}`, `extraerSpecs(descripcion)` → `string[]`, `extraerMarcaModelo(descripcion)` → `{marca, modelo}` — all consumed by Task 6's `runSearch`/card renderer.

- [ ] **Step 1: Implement the search port**

Insert into `initApp(DATA)`, right after the `buildProductIndex`/`PRODUCT_INDEX` block from Task 4:

```javascript
  // ---------- busqueda difusa (puerto de Sistema/cotizador_historico.py) ----------
  function normalizeText(s) {
    return String(s == null ? '' : s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim();
  }
  var LONGITUD_MINIMA_PALABRA_SIGNIFICATIVA = 4;
  function diceCoefficient(a, b) {
    if (!a || !b) return 0;
    if (a === b) return 1;
    function bigrams(s) { var out = []; for (var i = 0; i < s.length - 1; i++) out.push(s.slice(i, i + 2)); return out; }
    var ba = bigrams(a), bb = bigrams(b);
    if (!ba.length || !bb.length) return 0;
    var matches = 0;
    ba.forEach(function (bg) { var idx = bb.indexOf(bg); if (idx !== -1) { matches++; bb.splice(idx, 1); } });
    return (2 * matches) / (ba.length + bigrams(b).length);
  }
  function similitud(a, b) {
    if (!a || !b) return 0;
    if (a.indexOf(b) !== -1 || b.indexOf(a) !== -1) return 1;
    var palabras = b.split(/\s+/);
    for (var i = 0; i < palabras.length; i++) {
      var palabra = palabras[i];
      if (palabra.length >= LONGITUD_MINIMA_PALABRA_SIGNIFICATIVA && (a.indexOf(palabra) !== -1 || palabra.indexOf(a) !== -1)) return 1;
    }
    return diceCoefficient(a, b);
  }
  var UMBRAL_SIMILITUD = 0.6, UMBRAL_SUGERENCIA = 0.4, MAX_SUGERENCIAS = 5;
  function buscarItems(items, textoBusqueda) {
    var consulta = normalizeText(textoBusqueda);
    var puntuadas = items.map(function (item) {
      var s = Math.max(similitud(consulta, normalizeText(item.nombre_item)), similitud(consulta, normalizeText(item.descripcion)));
      return { s: s, item: item };
    });
    puntuadas.sort(function (x, y) { return y.s - x.s; });
    var coincidencias = puntuadas.filter(function (p) { return p.s >= UMBRAL_SIMILITUD; }).map(function (p) { return p.item; });
    var sugerencias = [];
    for (var i = 0; i < puntuadas.length; i++) {
      var p = puntuadas[i];
      if (p.s >= UMBRAL_SUGERENCIA && p.s < UMBRAL_SIMILITUD && sugerencias.indexOf(p.item.nombre_item) === -1) sugerencias.push(p.item.nombre_item);
      if (sugerencias.length >= MAX_SUGERENCIAS) break;
    }
    return { coincidencias: coincidencias, sugerencias: sugerencias };
  }

  // ---------- parser heuristico de specs tecnicas (marca/modelo/potencia/etc.) ----------
  var PATRONES_SPECS = [
    /(\d+(?:[.,]\d+)?)\s?(hp|cv|kw|w)\b/gi,
    /(\d+(?:[.,]\d+)?)\s?(l\/min|lt\/min|l\/h|gpm|m3\/h|m³\/h)\b/gi,
    /(\d+(?:[.,]\d+)?)\s?v\b/gi,
    /(\d+(?:[.,]\d+)?)\s?(bar|psi)\b/gi,
    /(\d+(?:[.,]\d+)?)\s?(lt|litros|kg|gal)\b/gi,
    /(\d+(?:[.,]\d+)?)\s?(mm|cm|pulg(?:adas)?)\b/gi
  ];
  function extraerSpecs(descripcion) {
    var texto = String(descripcion || '');
    var chips = [], vistos = {};
    PATRONES_SPECS.forEach(function (patron) {
      var m;
      patron.lastIndex = 0;
      while ((m = patron.exec(texto))) {
        var chip = m[0].replace(/\s+/g, '');
        if (!vistos[chip]) { vistos[chip] = true; chips.push(chip); }
      }
    });
    return chips;
  }
  var PALABRAS_NO_MARCA = ['de', 'del', 'la', 'el', 'los', 'las', 'con', 'sin', 'para', 'por', 'y', 'o', 'a', 'en'];
  function extraerMarcaModelo(descripcion) {
    var tokens = String(descripcion || '').split(/\s+/);
    var marca = null, modelo = null;
    for (var i = 1; i < tokens.length; i++) {
      var t = tokens[i].replace(/[.,;]+$/, '');
      if (!t) continue;
      var esCapitalizada = /^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]*$/.test(t);
      var esAlfanumericaMixta = /^[A-Za-z]+[0-9]+[A-Za-z0-9]*$/.test(t) || /^[0-9]+[A-Za-z]+[A-Za-z0-9]*$/.test(t);
      if (!marca && esCapitalizada && PALABRAS_NO_MARCA.indexOf(t.toLowerCase()) === -1) { marca = t; continue; }
      if (marca && !modelo && (esAlfanumericaMixta || /^[A-Z0-9]{2,}$/.test(t))) { modelo = t; break; }
    }
    return { marca: marca, modelo: modelo };
  }
```

- [ ] **Step 2: Manual verification via the browser console (no headless JS test runner in this project — verified through the built page directly)**

Run: `cd "Cotizador Historico/Visualizador Web" && python build_visualizador.py`, open `build/index.html`, unlock with the password, open the browser console (F12) and run:

```javascript
buscarItems(DATA.items, "bomba").coincidencias.length
extraerSpecs("Bomba centrífuga Pedrollo CPm158 1.5HP 220V 60L/min")
extraerMarcaModelo("Bomba centrífuga Pedrollo CPm158 1.5HP 220V 60L/min")
```

Expected: the first line returns a number ≥ 0 matching how many real "bomba"-like items exist in the actual `Centro de Costos.xlsx` data (0 is fine if none exist yet — confirms no crash); the second returns an array like `["1.5HP", "220V", "60L/min"]`; the third returns `{marca: "Pedrollo", modelo: "CPm158"}`. If the real data has no pump-like item, substitute a real `nombre_item`/`descripcion` pair that exists in `DATA.items` (inspect via `DATA.items.filter(i => i.nombre_item)` in the console) to confirm `buscarItems` returns it for its own name.

- [ ] **Step 3: Commit**

```bash
git add "Cotizador Historico/Visualizador Web/template.html"
git commit -m "feat(cotizador-historico): puerto JS de la busqueda difusa + parser heuristico de specs"
```

---

### Task 6: Search results UI — cards, top-5/ver todas, filters

**Files:**
- Modify: `Cotizador Historico/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `buscarItems`, `extraerSpecs`, `extraerMarcaModelo`, `fmt`, `fmtDate` (from the scaffold — note: `fmtDate` was NOT in the Task 3 keep-list; add it now, see Step 1), `esc`, `normalizeText`, `PRODUCT_INDEX`.
- Produces: `runSearch(texto)` (called by Task 4's product-table row click and by this task's own search input), and a global `state.filtroProyecto/filtroCategoria/desde/hasta` object that Task 7's cart "Agregar" buttons read `data-*` attributes from (no shared state needed there — cart reads only from the DOM).

- [ ] **Step 1: Add `fmtDate` (missed by the Task 3 scaffold range) and the results markup/CSS**

`fmtDate` exists in Centro de Costos' template right next to `fmt`/`fmtNum` but this plan's Task 3 range (`rng(531,632)`) already includes lines 618-632, which per the source file includes it (`fmt`, `fmtNum`, `fmtDate`, `esc` are lines 620-631) — confirm it's already present: `grep -c "function fmtDate" "Cotizador Historico/Visualizador Web/template.html"` should print `1`. If it prints `0` (range drifted), add it manually right after the `fmtNum` function:

```javascript
  function fmtDate(iso) {
    if (!iso) return '—';
    var parts = iso.split('-');
    return parts[2] + '/' + parts[1] + '/' + parts[0];
  }
```

Add the search bar + results markup right after the `</div>` that closes `.viz-tablewrap` (the product index table from Task 4), still inside `.viz-container`:

```html
    <p class="viz-section-title">Buscar referencias</p>
    <div class="viz-filterbar">
      <div class="viz-field search">
        <label for="fSearch">Buscar por palabra clave</label>
        <input id="fSearch" type="text" placeholder="Ej. bomba, taladro, cemento…" />
      </div>
      <div class="viz-field">
        <label for="fProyecto">Proyecto</label>
        <select id="fProyecto"><option value="">Todos</option></select>
      </div>
      <div class="viz-field">
        <label for="fCategoria">Categoría</label>
        <select id="fCategoria"><option value="">Todas</option></select>
      </div>
      <div class="viz-field dates">
        <div class="viz-field"><label for="fDesde">Desde</label><input id="fDesde" type="date" /></div>
        <div class="viz-field"><label for="fHasta">Hasta</label><input id="fHasta" type="date" /></div>
      </div>
      <span class="viz-resultcount" id="searchResultCount"></span>
    </div>

    <div id="searchSummary" class="viz-searchsummary" style="display:none"></div>
    <div id="searchResults" class="viz-cardgrid"></div>
    <div id="searchMoreWrap" style="display:none;text-align:center;margin:12px 0 24px">
      <button type="button" class="viz-clearbtn" id="btnVerTodas"></button>
    </div>
    <div id="searchEmptyState" class="viz-empty-state" style="display:none"></div>
```

Append this CSS right before the scaffold's closing `</style>` tag:

```css
  .viz-searchsummary { background: var(--surface-card); border: 1px solid var(--border-hairline); border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; font-size: 13px; display: flex; gap: 24px; flex-wrap: wrap; }
  .viz-searchsummary b { color: var(--brand-orange-ink, var(--brand-orange)); }
  .viz-cardgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; margin-bottom: 12px; }
  .viz-refcard { background: var(--surface-card); border: 1px solid var(--border-hairline); border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; }
  .viz-refcard .rc-title { font-size: 14px; font-weight: 700; }
  .viz-refcard .rc-chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .viz-refcard .rc-chip { font-size: 11px; font-weight: 700; background: rgba(255,81,0,0.12); color: var(--brand-orange-ink, var(--brand-orange)); border-radius: 20px; padding: 2px 9px; }
  .viz-refcard .rc-desc { font-size: 12.5px; color: var(--text-secondary); line-height: 1.4; }
  .viz-refcard .rc-meta { font-size: 11.5px; color: var(--text-muted); display: flex; flex-wrap: wrap; gap: 4px 10px; }
  .viz-refcard .rc-price { margin-top: 4px; padding-top: 8px; border-top: 1px solid var(--gridline); }
  .viz-refcard .rc-price .rc-price-main { font-size: 21px; font-weight: 900; color: var(--brand-orange-ink, var(--brand-orange)); font-variant-numeric: tabular-nums; }
  .viz-refcard .rc-price .rc-price-sub { font-size: 11.5px; color: var(--text-muted); }
  .viz-refcard .rc-original { font-size: 11px; color: var(--text-muted); }
  .viz-refcard mark { background: rgba(255,81,0,0.28); color: inherit; border-radius: 2px; padding: 0 1px; }
  .viz-refcard .rc-cartrow { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
  .viz-refcard .rc-qty { width: 52px; font-family: inherit; font-size: 13px; text-align: center; padding: 5px; border-radius: 6px; border: 1px solid var(--border-hairline); background: var(--surface-1); color: var(--text-primary); }
  .viz-refcard .rc-addbtn { flex: 1; font-family: inherit; font-size: 12.5px; font-weight: 700; padding: 7px 10px; border-radius: 7px; border: none; background: var(--brand-orange); color: #000; cursor: pointer; }
  .viz-refcard .rc-addbtn:hover { filter: brightness(1.1); }
  .viz-refcard .rc-addbtn.added { background: var(--status-good); color: #fff; }
```

- [ ] **Step 2: Implement `runSearch` and the filters**

Insert into `initApp(DATA)`, right after the spec-parser block from Task 5:

```javascript
  // ---------- filtros de busqueda ----------
  fillSelectFromValues('fProyecto', DATA.items.map(function (i) { return i.proyecto; }));
  fillSelectFromValues('fCategoria', DATA.items.map(function (i) { return i.categoria_item; }));
  function fillSelectFromValues(id, values) {
    var uniq = Array.from(new Set(values.filter(Boolean))).sort();
    var el = document.getElementById(id);
    uniq.forEach(function (v) {
      var opt = document.createElement('option');
      opt.value = v; opt.textContent = v;
      el.appendChild(opt);
    });
  }
  function itemPasaFiltros(item) {
    var proyecto = document.getElementById('fProyecto').value;
    var categoria = document.getElementById('fCategoria').value;
    var desde = document.getElementById('fDesde').value;
    var hasta = document.getElementById('fHasta').value;
    if (proyecto && item.proyecto !== proyecto) return false;
    if (categoria && item.categoria_item !== categoria) return false;
    if (desde && item.fecha < desde) return false;
    if (hasta && item.fecha > hasta) return false;
    return true;
  }

  // ---------- resultados de busqueda ----------
  var PAGE_SIZE_RESULTADOS = 5;
  var searchState = { texto: '', mostrarTodas: false };

  function runSearch(texto) {
    document.getElementById('fSearch').value = texto;
    searchState.texto = texto;
    searchState.mostrarTodas = false;
    renderSearch();
    document.querySelector('.viz-cardgrid').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function highlight(texto, consulta) {
    if (!consulta) return esc(texto);
    var idx = normalizeText(texto).indexOf(normalizeText(consulta));
    if (idx === -1) return esc(texto);
    var raw = String(texto || '');
    return esc(raw.slice(0, idx)) + '<mark>' + esc(raw.slice(idx, idx + consulta.length)) + '</mark>' + esc(raw.slice(idx + consulta.length));
  }

  function renderRefCard(item, consulta) {
    var specs = extraerSpecs(item.descripcion);
    var marcaModelo = extraerMarcaModelo(item.descripcion);
    var chips = [];
    if (marcaModelo.marca) chips.push(marcaModelo.marca);
    if (marcaModelo.modelo) chips.push(marcaModelo.modelo);
    chips = chips.concat(specs);
    var cardId = 'rc_' + item.n_ref + '_' + item.nombre_item.replace(/\W+/g, '_');
    return '<div class="viz-refcard">' +
      '<div class="rc-title">' + highlight(item.nombre_item, consulta) + '</div>' +
      (chips.length ? '<div class="rc-chips">' + chips.map(function (c) { return '<span class="rc-chip">' + esc(c) + '</span>'; }).join('') + '</div>' : '') +
      '<div class="rc-desc">' + highlight(item.descripcion, consulta) + '</div>' +
      '<div class="rc-meta"><span>' + esc(item.n_ref) + '</span><span>' + esc(item.proyecto || '—') + '</span><span>' + esc(item.proveedor_tag || '—') + '</span><span>' + fmtDate(item.fecha) + '</span></div>' +
      '<div class="rc-price">' +
      '<div class="rc-price-main">' + fmt(item.precio_reajustado_hoy_con_iva) + '</div>' +
      '<div class="rc-price-sub">c/IVA · ' + fmt(item.precio_reajustado_hoy) + ' s/IVA reajustado hoy</div>' +
      '<div class="rc-original">Precio original: ' + fmt(item.precio_original_sin_iva) + ' (s/IVA, al momento de la compra)</div>' +
      '</div>' +
      '<div class="rc-cartrow">' +
      '<input type="number" class="rc-qty" id="qty_' + cardId + '" value="1" min="1" step="1" aria-label="Cantidad" />' +
      '<button type="button" class="rc-addbtn" data-cardid="' + cardId + '" data-nref="' + esc(item.n_ref) + '" data-nombre="' + esc(item.nombre_item) + '">Agregar al carrito</button>' +
      '</div>' +
      '</div>';
  }

  function renderSearch() {
    var texto = searchState.texto;
    var countEl = document.getElementById('searchResultCount');
    var summaryEl = document.getElementById('searchSummary');
    var resultsEl = document.getElementById('searchResults');
    var moreWrapEl = document.getElementById('searchMoreWrap');
    var emptyEl = document.getElementById('searchEmptyState');
    var verTodasBtn = document.getElementById('btnVerTodas');

    if (!texto) {
      countEl.textContent = '';
      summaryEl.style.display = 'none';
      resultsEl.innerHTML = '';
      moreWrapEl.style.display = 'none';
      emptyEl.style.display = 'none';
      return;
    }

    var candidatos = DATA.items.filter(itemPasaFiltros);
    var resultado = buscarItems(candidatos, texto);
    var coincidencias = resultado.coincidencias;

    if (!coincidencias.length) {
      summaryEl.style.display = 'none';
      resultsEl.innerHTML = '';
      moreWrapEl.style.display = 'none';
      countEl.textContent = '0 referencias';
      emptyEl.style.display = '';
      emptyEl.innerHTML = 'No se encontraron referencias para "' + esc(texto) + '".' +
        (resultado.sugerencias.length ? '<br>Quizás quisiste decir: ' + resultado.sugerencias.map(esc).join(', ') : '');
      return;
    }
    emptyEl.style.display = 'none';

    var precios = coincidencias.map(function (c) { return c.precio_reajustado_hoy_con_iva; });
    var promedio = Math.round(precios.reduce(function (a, b) { return a + b; }, 0) / precios.length);
    summaryEl.style.display = '';
    summaryEl.innerHTML =
      '<span>Referencias encontradas: <b>' + coincidencias.length + '</b></span>' +
      '<span>Promedio reajustado (c/IVA): <b>' + fmt(promedio) + '</b></span>' +
      '<span>Rango: <b>' + fmt(Math.min.apply(null, precios)) + ' – ' + fmt(Math.max.apply(null, precios)) + '</b></span>';

    countEl.textContent = coincidencias.length + ' referencia' + (coincidencias.length === 1 ? '' : 's');

    var mostrar = searchState.mostrarTodas ? coincidencias : coincidencias.slice(0, PAGE_SIZE_RESULTADOS);
    resultsEl.innerHTML = mostrar.map(function (item) { return renderRefCard(item, texto); }).join('');
    bindCartButtons(resultsEl);

    if (coincidencias.length > PAGE_SIZE_RESULTADOS && !searchState.mostrarTodas) {
      moreWrapEl.style.display = '';
      verTodasBtn.textContent = 'Ver las ' + coincidencias.length + ' referencias';
      verTodasBtn.onclick = function () { searchState.mostrarTodas = true; renderSearch(); };
    } else {
      moreWrapEl.style.display = 'none';
    }
  }

  var debouncedRunSearchFromInput = debounce(function () { runSearch(document.getElementById('fSearch').value); }, 150);
  document.getElementById('fSearch').addEventListener('input', debouncedRunSearchFromInput);
  ['fProyecto', 'fCategoria', 'fDesde', 'fHasta'].forEach(function (id) {
    document.getElementById(id).addEventListener('change', function () { renderSearch(); });
  });
  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }
```

`bindCartButtons` is defined in Task 7 — leave the reference, it resolves once that task lands (same pattern as `runSearch` in Task 4).

- [ ] **Step 3: Manual verification**

Rebuild (`python build_visualizador.py`), open `build/index.html`, unlock, type a search term that you confirmed exists in `DATA.items` during Task 5's console check. Confirm: a summary bar shows count/average/range, up to 5 cards render with the searched term highlighted, chips show when the description has recognizable specs, the big price is the "c/IVA" reajustado figure, and if there are more than 5 matches a "Ver las N referencias" button appears and expands the list when clicked. Try the Proyecto/Categoría/date filters and confirm results narrow accordingly. Clicking a row in the product-index table (Task 4) should now scroll to and populate these results (the `ReferenceError` from Task 4 Step 4 should be gone).

- [ ] **Step 4: Commit**

```bash
git add "Cotizador Historico/Visualizador Web/template.html"
git commit -m "feat(cotizador-historico): tarjetas de resultados de busqueda, top-5/ver todas, filtros"
```

---

### Task 7: Cart (session-only, no persistence)

**Files:**
- Modify: `Cotizador Historico/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `.rc-addbtn`/`.rc-qty` DOM elements rendered by Task 6's `renderRefCard`, `fmt`, `esc`.
- Produces: `bindCartButtons(container)` (resolves Task 6's forward reference), `cart` (in-memory array, module-scope inside `initApp`), consumed by Task 8's `construirTextoExport()`. This task's own `renderCart()` calls `construirTextoExport()` (Task 8) to populate the `#exportText` textarea live — that function does not exist until Task 8 lands, so until then adding an item to the cart throws `ReferenceError: construirTextoExport is not defined` in the browser console. This is an intentional, temporary forward reference, the same pattern already used for `runSearch` (Task 4→6) and `bindCartButtons` (Task 6→7) — not a bug to fix within this task.

- [ ] **Step 1: Add the floating cart button + drawer markup**

Insert right before the final `<div class="viz-tooltip" id="vizTooltip"></div>` line (still inside `#vizRoot`, so it's hidden behind the gate until unlocked):

```html
  <button type="button" id="cartToggleBtn" class="viz-cart-fab" aria-label="Abrir carrito">
    🛒<span id="cartBadge" class="viz-cart-badge" style="display:none">0</span>
  </button>
  <div id="cartDrawer" class="viz-cart-drawer" style="display:none">
    <div class="viz-cart-header">
      <h3>Carrito de cotización</h3>
      <button type="button" id="cartCloseBtn" aria-label="Cerrar carrito">✕</button>
    </div>
    <div id="cartItemsList" class="viz-cart-items"></div>
    <div id="cartEmptyMsg" class="viz-cart-empty">El carrito está vacío. Agrega referencias desde los resultados de búsqueda.</div>
    <div class="viz-cart-totals" id="cartTotals"></div>
    <label class="viz-cart-label" for="exportText">Texto para copiar a Excel</label>
    <textarea id="exportText" class="viz-cart-textarea" readonly rows="6" placeholder="Agrega referencias al carrito para generar el texto…"></textarea>
    <button type="button" id="btnCopiarTodo" class="viz-cart-copybtn" disabled>Copiar todo</button>
    <p class="viz-cart-note">Pega directo en Excel: las columnas quedan separadas solas (están tabuladas).</p>
  </div>
```

Append this CSS right before the closing `</style>`:

```css
  .viz-cart-fab { position: fixed; bottom: 20px; right: 20px; z-index: 900; width: 52px; height: 52px; border-radius: 50%; border: none; background: var(--brand-orange); color: #000; font-size: 22px; cursor: pointer; box-shadow: 0 6px 18px rgba(0,0,0,0.28); }
  .viz-cart-badge { position: absolute; top: -4px; right: -4px; background: #000; color: #fff; font-size: 11px; font-weight: 900; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; }
  .viz-cart-badge.bump { animation: cartBump 0.25s ease-out; }
  @keyframes cartBump { 0% { transform: scale(1); } 50% { transform: scale(1.35); } 100% { transform: scale(1); } }
  .viz-cart-drawer { position: fixed; top: 0; right: 0; bottom: 0; width: min(360px, 100vw); background: var(--surface-card); border-left: 1px solid var(--border-hairline); box-shadow: -8px 0 24px rgba(0,0,0,0.2); z-index: 950; display: flex; flex-direction: column; padding: 16px; }
  .viz-cart-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
  .viz-cart-header h3 { font-size: 15px; margin: 0; }
  .viz-cart-header button { background: none; border: none; font-size: 16px; cursor: pointer; color: var(--text-secondary); }
  .viz-cart-items { flex: 1 1 auto; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
  .viz-cart-line { border: 1px solid var(--border-hairline); border-radius: 8px; padding: 8px 10px; font-size: 12.5px; }
  .viz-cart-line .cl-title { font-weight: 700; margin-bottom: 4px; }
  .viz-cart-line .cl-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .viz-cart-line input { width: 46px; font-family: inherit; font-size: 12.5px; text-align: center; padding: 3px; border-radius: 5px; border: 1px solid var(--border-hairline); background: var(--surface-1); color: var(--text-primary); }
  .viz-cart-line .cl-removebtn { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 12px; }
  .viz-cart-line .cl-removebtn:hover { color: var(--brand-orange-ink, var(--brand-orange)); }
  .viz-cart-empty { font-size: 12.5px; color: var(--text-muted); text-align: center; padding: 20px 0; }
  .viz-cart-totals { font-size: 13px; font-weight: 700; padding: 10px 0; border-top: 1px solid var(--gridline); margin-top: 8px; }
  .viz-cart-label { font-size: 11px; color: var(--text-muted); font-weight: 600; margin-bottom: 4px; display: block; }
  .viz-cart-textarea { width: 100%; font-family: 'Lato', monospace; font-size: 11px; padding: 8px; border-radius: 7px; border: 1px solid var(--border-hairline); background: var(--surface-1); color: var(--text-primary); resize: vertical; white-space: pre; }
  .viz-cart-copybtn { font-family: inherit; font-size: 13px; font-weight: 900; padding: 10px; border-radius: 8px; border: none; background: var(--brand-orange); color: #000; cursor: pointer; margin-top: 8px; }
  .viz-cart-copybtn:disabled { opacity: 0.4; cursor: default; }
  .viz-cart-note { font-size: 10.5px; color: var(--text-muted); margin: 8px 0 0; line-height: 1.4; }
```

- [ ] **Step 2: Implement cart state + rendering + button wiring**

Insert into `initApp(DATA)`, right after `renderSearch`/the debounce helper block from Task 6:

```javascript
  // ---------- carrito (solo en memoria -- nunca localStorage/sessionStorage) ----------
  var cart = [];

  function cartKey(nRef, nombreItem) { return nRef + '|' + nombreItem; }

  function addToCart(item, cantidad) {
    var key = cartKey(item.n_ref, item.nombre_item);
    var existing = cart.filter(function (l) { return l.key === key; })[0];
    if (existing) {
      existing.cantidad += cantidad;
    } else {
      cart.push({
        key: key, n_ref: item.n_ref, nombre_item: item.nombre_item, descripcion: item.descripcion,
        categoria_item: item.categoria_item, proyecto: item.proyecto, fecha: item.fecha,
        precio_reajustado_hoy: item.precio_reajustado_hoy,
        precio_reajustado_hoy_con_iva: item.precio_reajustado_hoy_con_iva,
        cantidad: cantidad,
      });
    }
    renderCart();
  }

  function removeFromCart(key) {
    cart = cart.filter(function (l) { return l.key !== key; });
    renderCart();
  }

  function bindCartButtons(container) {
    container.querySelectorAll('.rc-addbtn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var cardId = btn.dataset.cardid;
        var qtyInput = document.getElementById('qty_' + cardId);
        var cantidad = Math.max(1, parseInt(qtyInput.value, 10) || 1);
        var item = DATA.items.filter(function (it) { return it.n_ref === btn.dataset.nref && it.nombre_item === btn.dataset.nombre; })[0];
        if (!item) return;
        addToCart(item, cantidad);
        btn.textContent = '✓ Agregado';
        btn.classList.add('added');
        setTimeout(function () { btn.textContent = 'Agregar al carrito'; btn.classList.remove('added'); }, 1200);
      });
    });
  }

  function renderCart() {
    var badge = document.getElementById('cartBadge');
    var totalItems = cart.reduce(function (s, l) { return s + l.cantidad; }, 0);
    if (totalItems > 0) {
      badge.style.display = '';
      badge.textContent = totalItems;
      badge.classList.remove('bump');
      void badge.offsetWidth; // reinicia la animacion aunque el numero no cambie de digitos
      badge.classList.add('bump');
    } else {
      badge.style.display = 'none';
    }

    var listEl = document.getElementById('cartItemsList');
    var emptyEl = document.getElementById('cartEmptyMsg');
    var totalsEl = document.getElementById('cartTotals');
    var exportTextEl = document.getElementById('exportText');
    var copyBtn = document.getElementById('btnCopiarTodo');

    if (!cart.length) {
      listEl.innerHTML = '';
      emptyEl.style.display = '';
      totalsEl.textContent = '';
      exportTextEl.value = '';
      copyBtn.disabled = true;
      return;
    }
    emptyEl.style.display = 'none';
    exportTextEl.value = construirTextoExport();
    copyBtn.disabled = false;

    listEl.innerHTML = cart.map(function (l) {
      var subtotal = l.cantidad * l.precio_reajustado_hoy_con_iva;
      return '<div class="viz-cart-line" data-key="' + esc(l.key) + '">' +
        '<div class="cl-title">' + esc(l.nombre_item) + '</div>' +
        '<div class="cl-row"><span>' + esc(l.n_ref) + '</span><span>' + fmt(l.precio_reajustado_hoy_con_iva) + ' c/u</span></div>' +
        '<div class="cl-row"><input type="number" class="cl-qty" min="1" step="1" value="' + l.cantidad + '" /><span>' + fmt(subtotal) + '</span>' +
        '<button type="button" class="cl-removebtn" data-key="' + esc(l.key) + '">Quitar</button></div>' +
        '</div>';
    }).join('');

    listEl.querySelectorAll('.cl-qty').forEach(function (input) {
      input.addEventListener('change', function () {
        var key = input.closest('.viz-cart-line').dataset.key;
        var linea = cart.filter(function (l) { return l.key === key; })[0];
        if (linea) { linea.cantidad = Math.max(1, parseInt(input.value, 10) || 1); renderCart(); }
      });
    });
    listEl.querySelectorAll('.cl-removebtn').forEach(function (btn) {
      btn.addEventListener('click', function () { removeFromCart(btn.dataset.key); });
    });

    var totalConIva = cart.reduce(function (s, l) { return s + l.cantidad * l.precio_reajustado_hoy_con_iva; }, 0);
    var totalSinIva = cart.reduce(function (s, l) { return s + l.cantidad * l.precio_reajustado_hoy; }, 0);
    totalsEl.textContent = 'Total: ' + fmt(totalConIva) + ' c/IVA (' + fmt(totalSinIva) + ' s/IVA)';
  }

  document.getElementById('cartToggleBtn').addEventListener('click', function () {
    document.getElementById('cartDrawer').style.display = '';
  });
  document.getElementById('cartCloseBtn').addEventListener('click', function () {
    document.getElementById('cartDrawer').style.display = 'none';
  });
```

- [ ] **Step 3: Manual verification**

Rebuild, open, unlock, search a real term, set a card's quantity to `2` and click "Agregar al carrito" — confirm the floating cart badge appears showing `2` with a small bump animation, and clicking the cart button opens a drawer showing that line with a subtotal. Add a second, different reference with quantity `1`. Edit a quantity directly in the drawer and confirm the subtotal/total update. Click "Quitar" on one line and confirm it's removed. **Reload the page (F5)** and confirm the cart is empty again — this is the explicit "no persistence" requirement.

- [ ] **Step 4: Commit**

```bash
git add "Cotizador Historico/Visualizador Web/template.html"
git commit -m "feat(cotizador-historico): carrito de cotizacion (solo en memoria, sin persistencia)"
```

---

### Task 8: Cuadro de texto para copiar a Excel (Materiales/Equipos/Otros)

**Decision change (2026-07-20, mid-implementation):** the original design for this task downloaded a `.txt` file via the Artifact `downloads` capability. The user reviewed the plan and asked for a different mechanism instead: a read-only `<textarea>` inside the cart drawer that always shows the current cart's export text, plus a "Copiar todo" button that copies it to the clipboard — **no file download at all**. This avoids the `downloads` capability's extension allowlist entirely (moot now) and is simpler: no capability to declare when publishing, no distinction between "inside the Artifact sandbox" vs. "opened locally" download paths.

**Files:**
- Modify: `Cotizador Historico/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `cart` (Task 7), `fmt`, `DATA.uf_hoy`, `DATA.uf_fecha`, the `#exportText`/`#btnCopiarTodo` elements Task 7's markup already created.
- Produces: `construirTextoExport()` (resolves Task 7's forward reference — Task 7's `renderCart()` already calls it on every cart change). Nothing else consumed by later tasks — this is the last template.html feature task.

- [ ] **Step 1: Implement `construirTextoExport` and the copy-to-clipboard wiring**

Insert into `initApp(DATA)`, right after the cart drawer open/close listeners from Task 7:

```javascript
  // ---------- texto del carrito para copiar a Excel (Materiales/Equipos/Otros) ----------
  function seccionParaCategoria(categoriaItem) {
    if (categoriaItem === 'Materiales') return 'MATERIALES';
    if (categoriaItem === 'Equipos-Herramientas') return 'EQUIPOS';
    return 'OTROS';
  }

  function construirTextoExport() {
    var secciones = { MATERIALES: [], EQUIPOS: [], OTROS: [] };
    cart.forEach(function (l) { secciones[seccionParaCategoria(l.categoria_item)].push(l); });

    var lineas = [];
    lineas.push('Cotización QUEMPIN — generada ' + new Date().toLocaleString('es-CL'));
    lineas.push('UF utilizada: ' + fmt(DATA.uf_hoy) + ' (actualizada ' + DATA.uf_fecha + ')');
    lineas.push('');

    var totalGeneral = 0;
    ['MATERIALES', 'EQUIPOS', 'OTROS'].forEach(function (nombreSeccion) {
      var lineasSeccion = secciones[nombreSeccion];
      if (!lineasSeccion.length) return;
      lineas.push(nombreSeccion);
      lineas.push(['Nombre Item', 'Descripcion', 'Cantidad', 'Precio unit. s/IVA', 'Precio unit. c/IVA', 'Subtotal c/IVA', 'N Ref.', 'Fecha', 'Proyecto'].join('\t'));
      var subtotal = 0;
      lineasSeccion.forEach(function (l) {
        var sub = l.cantidad * l.precio_reajustado_hoy_con_iva;
        subtotal += sub;
        lineas.push([l.nombre_item, l.descripcion, l.cantidad, l.precio_reajustado_hoy, l.precio_reajustado_hoy_con_iva, sub, l.n_ref, l.fecha, l.proyecto || ''].join('\t'));
      });
      lineas.push('Subtotal ' + nombreSeccion + '\t\t\t\t\t' + subtotal);
      lineas.push('');
      totalGeneral += subtotal;
    });
    lineas.push('TOTAL GENERAL\t\t\t\t\t' + totalGeneral);
    return lineas.join('\n');
  }

  function copiarTextoExport() {
    var textarea = document.getElementById('exportText');
    var btn = document.getElementById('btnCopiarTodo');
    function marcarCopiado() {
      btn.textContent = '✓ Copiado';
      setTimeout(function () { btn.textContent = 'Copiar todo'; }, 1200);
    }
    function fallbackCopy() {
      textarea.focus();
      textarea.select();
      try { if (document.execCommand('copy')) marcarCopiado(); } catch (e) {}
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(textarea.value).then(marcarCopiado, fallbackCopy);
    } else {
      fallbackCopy();
    }
  }

  document.getElementById('btnCopiarTodo').addEventListener('click', copiarTextoExport);
```

- [ ] **Step 2: Manual verification**

Rebuild, open, unlock, add at least two references from **different** categories to the cart if the real data allows it (check `DATA.items.map(i => i.categoria_item)` in the console to find one `"Materiales"` and one `"Equipos-Herramientas"` item — if the real dataset happens to only have one category represented, that's fine, just verify that section appears alone and the others don't). Confirm the `#exportText` textarea already shows the generated text **without clicking anything** — it must update live on every cart change (add/remove/qty edit), since Task 7's `renderCart()` calls `construirTextoExport()` directly. Confirm the text has: a header with generation date + UF used, one section per represented category with a tab-separated header row and one line per cart item, a subtotal per section, and a `TOTAL GENERAL` line. Click "Copiar todo", confirm the button briefly shows "✓ Copiado" (clipboard permission may prompt in some browsers — accept it), then paste into a real spreadsheet (or a plain text editor first, to check the raw shape has literal tab characters between fields) and confirm the columns land in separate cells when pasted into Excel/Sheets, not all-in-one.

- [ ] **Step 3: Commit**

```bash
git add "Cotizador Historico/Visualizador Web/template.html"
git commit -m "feat(cotizador-historico): cuadro de texto del carrito para copiar a Excel (Materiales/Equipos/Otros)"
```

---

### Task 9: `driver.py` command + `SKILL.md`

**Files:**
- Modify: `Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py`
- Modify: `Cotizador Historico/.claude/skills/Cotizador_Historico/SKILL.md`

**Interfaces:**
- Consumes: `Cotizador Historico/Visualizador Web/build_visualizador.py::build()` (Task 2).
- Produces: `python driver.py visualizador` as a documented, working command.

- [ ] **Step 1: Add the `visualizador` command to `driver.py`**

In `driver.py`, add this function right after `cmd_consultar`:

```python
def cmd_visualizador():
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raiz_modulo = Path(__file__).resolve().parents[3]
    ruta_viz = raiz_modulo / "Visualizador Web"
    sys.path.insert(0, str(ruta_viz))
    import build_visualizador as bv  # noqa: E402
    return bv.build()
```

Then update `main()`:

```python
def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "consultar", "visualizador"):
        print('Uso: python driver.py [status|consultar "<texto>"|visualizador]')
        return 2
    if sys.argv[1] == "status":
        return cmd_status()
    if sys.argv[1] == "visualizador":
        return cmd_visualizador()
    return cmd_consultar(sys.argv[2:])
```

- [ ] **Step 2: Run it end-to-end**

Run: `cd "Cotizador Historico" && python ".claude/skills/Cotizador_Historico/driver.py" visualizador`
Expected: same `OK — N referencias indexadas...` output as running `build_visualizador.py` directly (Task 3).

- [ ] **Step 3: Update `SKILL.md`**

In `Cotizador Historico/.claude/skills/Cotizador_Historico/SKILL.md`, add a new subsection right after the existing "`consultar "<texto>"`" command documentation (before "## Uso conversacional"):

```markdown
**`visualizador`** — regenera el visualizador web (`Visualizador Web/build/index.html`)
a partir de `Centro de Costos.xlsx`: indexa todo el catálogo, pide la UF de
hoy una sola vez, y la incrusta en el HTML junto con el resto del snapshot.
Requiere conexión a internet (la UF de hoy nunca se cachea). Ver
`../../../Visualizador Web/CLAUDE.md` para el diseño completo (buscador,
carrito de cotización, texto para copiar a Excel).

```
python ".claude/skills/Cotizador_Historico/driver.py" visualizador
```
```

- [ ] **Step 4: Commit**

```bash
git add "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" "Cotizador Historico/.claude/skills/Cotizador_Historico/SKILL.md"
git commit -m "feat(cotizador-historico): comando 'visualizador' en el driver de la skill"
```

---

### Task 10: Documentation — `Visualizador Web/CLAUDE.md`

**Files:**
- Modify: `Cotizador Historico/Visualizador Web/CLAUDE.md`

- [ ] **Step 1: Replace the scaffolding content with the real implementation doc**

Read the current file first (`Read` tool) — it's still the generic scaffolding from before this feature existed. Replace its content with a doc mirroring the structure of `Centro de Costos/Visualizador Web/CLAUDE.md`'s "Implementación real" section: file tree (`template.html`/`build_visualizador.py`/`data/`/`build/`), the "un solo comando regenera todo" note (`python driver.py visualizador`), the UF-fixed-at-build-time decision and why (no generic fetch capability in Artifacts), the password/branding reuse note, the cart's no-persistence guarantee, the copy-to-clipboard export design (textarea + "Copiar todo" button, no file download — this was a deliberate user decision made mid-implementation, superseding an earlier `.txt`-download design; note briefly why the earlier design was dropped, since a future reader might otherwise wonder why the `downloads` capability is never mentioned), the categoria→sección mapping (Materiales/Equipos-Herramientas/Otros), and a pointer to the full spec at `../docs/superpowers/specs/2026-07-20-visualizador-cotizador-historico-design.md` (note in this doc that the spec's "Exportación" section describes the superseded `.txt`-download design — this `CLAUDE.md` is the source of truth for what actually shipped). Keep it factual and dated (2026-07-20), same tone as the Centro de Costos doc.

- [ ] **Step 2: Commit**

```bash
git add "Cotizador Historico/Visualizador Web/CLAUDE.md"
git commit -m "docs(cotizador-historico): documentar implementacion real del visualizador web"
```

---

### Task 11: End-to-end verification with a real browser

**Files:** none (verification only — fix forward into whichever file above if a bug is found, then re-run this task).

- [ ] **Step 1: Confirm Playwright is available**

Run: `python -c "import playwright; print('ok')"` — if it errors, run `pip install playwright && python -m playwright install chromium` first (per Centro de Costos' precedent, this is already installed on this machine as of 2026-07-19; if it's still there, skip straight to Step 2).

- [ ] **Step 2: Write and run a one-off verification script (not committed — same "temporary tool" status as Task 3's scaffold script)**

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("file:///" + __import__("pathlib").Path("Cotizador Historico/Visualizador Web/build/index.html").resolve().as_posix())

    page.fill("#pwInput", "combustion")
    page.click("#pwForm button[type=submit]")
    page.wait_for_selector("#vizRoot[style*='display: block'], #vizRoot:not([style*='display: none'])", timeout=3000)
    page.screenshot(path="Cotizador Historico/Visualizador Web/_verify_1_unlocked.png", full_page=True)

    # busca un termino real -- ajustar a algo que exista en los datos reales
    page.fill("#fSearch", "a")  # una letra devuelve resultados amplios sin depender de un termino puntual
    page.wait_for_timeout(300)  # debounce de 150ms
    page.screenshot(path="Cotizador Historico/Visualizador Web/_verify_2_resultados.png", full_page=True)

    add_buttons = page.query_selector_all(".rc-addbtn")
    if len(add_buttons) >= 2:
        add_buttons[0].click()
        add_buttons[1].click()
    page.click("#cartToggleBtn")
    page.wait_for_timeout(200)
    page.screenshot(path="Cotizador Historico/Visualizador Web/_verify_3_carrito.png", full_page=True)

    browser.close()
    print("Screenshots escritos en Visualizador Web/_verify_*.png -- revisar a ojo y borrar despues.")
```

- [ ] **Step 3: Inspect the three screenshots by eye**

Open each `_verify_*.png` and confirm: (1) the gate unlocked into the branded page with KPIs/chart/table visible, no visual glitches in either the default light/dark mode; (2) search results show cards with the highlighted term, chips where applicable, and the large UF-adjusted price; (3) the cart drawer shows two lines with correct subtotals and a non-zero total. Also open the browser console manually once (outside the script, just opening the file normally) and confirm zero JS errors across: page load, unlock, typing a search, adding to cart, removing from cart, and exporting.

- [ ] **Step 4: Delete the verification artifacts (not part of the module)**

```bash
rm "Cotizador Historico/Visualizador Web/_verify_1_unlocked.png" "Cotizador Historico/Visualizador Web/_verify_2_resultados.png" "Cotizador Historico/Visualizador Web/_verify_3_carrito.png"
```

- [ ] **Step 5: If any bug was found in Step 3, fix it in the relevant task's file, re-run `python build_visualizador.py`, and repeat from Step 2 before moving on.** If nothing was found, there is nothing to commit for this task — it's a verification gate, not a code change.

---

### Task 12: Publish as a Claude Artifact — requires user confirmation first

**This task is not to be run automatically by an executing agent.** Publishing creates a new externally-accessible (if private) Artifact — per this project's own risk-handling convention, pause and confirm with the user before calling the `Artifact` tool, the same way Centro de Costos' first publish was a deliberate, confirmed step, not an automatic last line of a script.

- [ ] **Step 1: Ask the user for explicit go-ahead to publish `Cotizador Historico/Visualizador Web/build/index.html` as a Claude Artifact**, referencing this task.

- [ ] **Step 2: Once confirmed, publish it** (favicon: pick one distinct from Centro de Costos' own favicon so the two Artifacts are visually distinguishable in a browser tab/gallery — check `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/MEMORY.md` for which emoji that one already uses, and pick a different one).

- [ ] **Step 3: Create `Cotizador Historico/.claude/skills/Cotizador_Historico/MEMORY.md`** (doesn't exist yet) recording the published Artifact URL and the explicit rule, mirroring Centro de Costos' own precedent: **always update this same link on republish, never mint a new one.** Also record here (not in `SKILL.md`, which stays procedure-only) the flow to update it: `python driver.py visualizador` regenerates `build/index.html`, then republish that file with the recorded URL as `url` in the `Artifact` tool call.

- [ ] **Step 4: Commit the new `MEMORY.md`**

```bash
git add "Cotizador Historico/.claude/skills/Cotizador_Historico/MEMORY.md"
git commit -m "docs(cotizador-historico): registrar link del Artifact publicado del visualizador"
```

---

## Self-Review Notes

- **Spec coverage**: buscador con specs técnicas (Task 5-6), top-5/ver-todas (Task 6), UF destacada (Task 6's `.rc-price-main`), carrito sin persistencia (Task 7), texto para copiar a Excel agrupado Materiales/Equipos/Otros (Task 8 — updated 2026-07-20 to a textarea + "Copiar todo" clipboard button, per the user's direct request, superseding the spec's original `.txt`-download design), mismo branding/contraseña (Task 3), UF fija al build (Task 1-2), tabla+gráfico+filtros del mandato del maestro (Task 4, 6), driver command (Task 9), doc (Task 10), verificación con navegador real (Task 11), publicación con confirmación (Task 12). No section of the spec is left without a task.
- **Placeholder scan**: no `TODO`/`TBD` in any step; the two forward references (`runSearch` in Task 4, `bindCartButtons` in Task 6) are explicitly called out as temporary `ReferenceError`s with the exact task that resolves them, not vague placeholders.
- **Type/name consistency checked**: `reajustar_todos` output keys match what `build_visualizador.py` reads and what the JS cards/cart/export read (`n_ref, fecha, precio_original_sin_iva, precio_reajustado_hoy, precio_reajustado_hoy_con_iva, nombre_item, descripcion, categoria_item, proyecto, proveedor_tag`) — traced end to end from Task 1 through Task 8.
- **Scope**: single cohesive feature (one visualizador), no unrelated refactors folded in beyond the minimal, backward-compatible `cargar_items_detalle` extension Task 1 needs.
