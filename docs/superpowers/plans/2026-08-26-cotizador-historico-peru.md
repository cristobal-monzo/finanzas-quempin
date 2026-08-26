# Cotizador Histórico Perú Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a working Cotizador Histórico Perú web dashboard (own GitHub Pages URL, own hub card in the Perú row) reading Perú's own Centro de Costos workbook, with no currency conversion and no index-based reajuste (Perú shows nominal historical soles, per an explicit spec decision).

**Architecture:** `Cotizador Historico/Sistema/cotizador_historico.py` gains a `pais="CL"|"PE"` parameter (shared, parametrized script — not cloned, per the master spec's explicit architecture decision #1), covering the 3 country-varying column names (`P. Unitario sin IVA`/`IGV`, `Total sin IVA (CLP)`/`Total sin IGV (PEN)`, `Total con IVA (CLP)`/`Total con IGV (PEN)`) and a brand-new no-op "reajuste" path for PE that never calls `mindicador.cl` (there's no Peruvian equivalent) and returns the nominal historical price unchanged. The Visualizador Web layer stays a **separate file pair per country** (`Peru/Cotizador Historico/Visualizador Web/build_visualizador.py` + `template.html`, copied from Chile's and adapted) — same pattern already used for Centro de Costos Perú, matching how `Registro_Centro_de_Costos/driver.py:cmd_visualizador` already resolves a per-country `Visualizador Web/` folder.

**Tech Stack:** Python 3.14 + openpyxl (data layer, no new deps), static HTML/CSS/vanilla JS (dashboard — includes a taxonomy classifier, cart, and clipboard export, all currency-agnostic and reused unchanged), pytest, Playwright (manual visual verification only).

**Spec:** `docs/superpowers/specs/2026-08-21-peru-expansion-design.md` (sub-project 2: "Cotizador Histórico Perú — parametrizar `cotizador_historico.py` (lee el Excel de Perú, sin reajuste por índice), skill `Cotizador_Historico` (+ `Actualizar_Cotizador`) con `--pais`"), specifically decisions #1 (shared parametrized core script) and #5 ("Cotizador Histórico Perú no reajusta por ningún índice — muestra el precio nominal en soles tal cual").

## Global Constraints

- **No currency conversion, no combined CLP+PEN view** — Perú reports in PEN only (spec § "Fuera de alcance").
- **No reajuste by any index for Perú** — nominal historical soles shown as-is; no dependency on a new external API (spec decision #5).
- **`cotizador_historico.py` is shared, parametrized code, never cloned** — `pais` defaults to `"CL"` everywhere, preserving every existing call site's behavior exactly (spec decision #1, mirrors `auditor_centro_costos.py`'s `configurar_pais` precedent).
- Reuse the existing password gate verbatim (`combustion`) — no new/different password for Perú.
- URL is structural and fixed: `https://cristobal-monzo.github.io/finanzas-quempin/cotizador-historico-peru/`.
- Never edit `Cotizador Historico/Visualizador Web/build_visualizador.py` or `template.html` (Chile's) — only read from them to build Perú's copy.
- `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx` currently has 0 rows in `Master`/`Detalle` — Perú's Cotizador dashboard must render a correct empty state (0 referencias indexadas), not crash.

---

## File Structure

```
Cotizador Historico/Sistema/cotizador_historico.py   # modified: pais param, PAISES dict, no-reajuste path
Cotizador Historico/Sistema/tests/test_lectura_excel.py     # modified: pais="PE" column tests
Cotizador Historico/Sistema/tests/test_consultar_item.py    # modified: pais="PE" consultar_item tests
Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py   # modified: --pais flag, PE-specific table
Cotizador Historico/.claude/skills/Cotizador_Historico/SKILL.md    # modified: document --pais

Peru/Cotizador Historico/Visualizador Web/
├── CLAUDE.md              # new — short, links to master + Chile's content doc
├── template.html          # new — copy of CL's, PEN/es-PE + reajuste-wording removed
├── build_visualizador.py  # new — copy of CL's, calls ch.*(pais="PE"), no UF fields
├── tests/
│   └── test_build_visualizador.py   # new
├── data/                  # generated, gitignored (**/Visualizador Web/data/)
└── build/                 # generated, gitignored (**/Visualizador Web/build/)

Visualizador Web/index.html      # modified: add Cotizador Histórico Perú card to the Perú row
Visualizador Web/CLAUDE.md       # modified: hosting table + URL list
```

---

### Task 1: `cotizador_historico.py` país-parametrization

**Files:**
- Modify: `Cotizador Historico/Sistema/cotizador_historico.py`
- Test: `Cotizador Historico/Sistema/tests/test_lectura_excel.py`
- Test: `Cotizador Historico/Sistema/tests/test_consultar_item.py`

**Interfaces:**
- Produces: `cargar_items_detalle(ruta_excel=None, pais="CL") -> list[dict]` (same item shape as today, `pais` only changes which column names/default path it reads), `armar_compra_sin_reajuste(item) -> dict` (same shape as `reajustar_item`'s return, minus the possibility of `None`), `armar_indice_completo_sin_reajuste(items) -> (list[dict], int)` (same contract as `reajustar_todos`, `sin_uf_count` always `0`), `consultar_item(texto_busqueda, ruta_excel=None, fecha_hoy=None, uf_manual=None, fuente_manual=None, pais="CL") -> dict` (same shape as today; for `pais="PE"`, `uf_fuente` is `None` and `sin_uf_count` is always `0`).
- Consumes: nothing new — this task only touches this one file.

Existing behavior for every current call site (`pais` omitted, defaults to `"CL"`) must not change — verified by running the full existing test suite for this module (Steps 2 and 6 below) with zero diffs in outcome.

- [ ] **Step 1: Write the failing tests for the PE column names**

Add to `Cotizador Historico/Sistema/tests/test_lectura_excel.py` (after the existing `_crear_excel_prueba` helper — this test needs its own PE-shaped workbook, so add a second helper alongside it, not a modification of the existing one):

```python
def _crear_excel_prueba_pe(tmp_path, filas_detalle, filas_master):
    """Mismo shape que _crear_excel_prueba, pero con los encabezados de
    Peru (IGV/PEN en vez de IVA/CLP) -- ver Peru/Centro de Costos/Excel/
    Centro de Costos Perú.xlsx, headers reales confirmados via openpyxl."""
    wb = openpyxl.Workbook()
    ws_detalle = wb.active
    ws_detalle.title = "Detalle"
    encabezados = [
        "N° Ref.", "Nombre Ítem", "Descripción", "P. Unitario sin IGV",
        "Total sin IGV (PEN)", "Total con IGV (PEN)",
    ]
    for c, h in enumerate(encabezados, 1):
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

    ruta = tmp_path / "Centro de Costos Perú.xlsx"
    wb.save(ruta)
    return ruta


def test_cargar_items_detalle_pais_pe_lee_columnas_igv_pen(tmp_path):
    ruta = _crear_excel_prueba_pe(
        tmp_path,
        filas_detalle=[("LIMA-001", "Taladro", "Taladro percutor 20V", 300, 300, 354)],
        filas_master=[("LIMA-001", datetime(2026, 1, 15))],
    )
    items = ch.cargar_items_detalle(ruta, pais="PE")
    assert len(items) == 1
    item = items[0]
    assert item["precio_unitario_sin_iva"] == 300
    assert item["total_sin_iva"] == 300
    assert item["total_con_iva"] == 354
    assert item["excluido_motivo"] is None


def test_cargar_items_detalle_pais_cl_no_cambia_con_el_parametro_default(tmp_path):
    # Mismo test que test_cargar_items_detalle_resuelve_fecha_via_master,
    # pero pasando pais="CL" explicito -- confirma que el default sigue
    # siendo identico a antes de este cambio.
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, 90000, 107100)],
        filas_master=[("UMAG-001", datetime(2026, 1, 15))],
    )
    items = ch.cargar_items_detalle(ruta, pais="CL")
    assert items[0]["precio_unitario_sin_iva"] == 90000
    assert items[0]["total_con_iva"] == 107100
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `py -3.14 -m pytest "Cotizador Historico/Sistema/tests/test_lectura_excel.py" -v -k pais`
Expected: FAIL — `cargar_items_detalle()` doesn't accept a `pais` keyword yet, and the PE column names aren't found (`KeyError: 'P. Unitario sin IGV'` wrapped in `ExcelNoDisponibleError`, or a `TypeError` on the unexpected kwarg).

- [ ] **Step 3: Add `PAISES` + `pais` param to `cargar_items_detalle`**

In `Cotizador Historico/Sistema/cotizador_historico.py`, after the existing `RUTA_CACHE_UF = ...` line (line 25), add:

```python
RUTA_EXCEL_CENTRO_COSTOS_PERU = RAIZ_MODULO.parent / "Peru" / "Centro de Costos" / "Excel" / "Centro de Costos Perú.xlsx"

# Config por pais -- solo lo que este modulo necesita (nombres de columna
# que varian entre IVA/CLP y IGV/PEN, y la ruta del Excel por defecto).
# Mismo patron que PAISES en Centro de Costos/Sistema/auditor_centro_costos.py,
# a proposito no comparte esa tabla -- este modulo no importa ese archivo.
PAISES = {
    "CL": {
        "ruta_excel": RUTA_EXCEL_CENTRO_COSTOS,
        "col_precio_unitario": "P. Unitario sin IVA",
        "col_total_sin_iva": "Total sin IVA (CLP)",
        "col_total_con_iva": "Total con IVA (CLP)",
    },
    "PE": {
        "ruta_excel": RUTA_EXCEL_CENTRO_COSTOS_PERU,
        "col_precio_unitario": "P. Unitario sin IGV",
        "col_total_sin_iva": "Total sin IGV (PEN)",
        "col_total_con_iva": "Total con IGV (PEN)",
    },
}
```

This references `RUTA_EXCEL_CENTRO_COSTOS` (the existing module-level constant, line 24) rather than duplicating the Chile path — so `PAISES["CL"]["ruta_excel"]` can never drift from the real default.

Then change the signature and body of `cargar_items_detalle` (currently starting at line 69):

```python
def cargar_items_detalle(ruta_excel=None, pais="CL"):
    """... (keep the existing docstring, add one line:) 'pais' selecciona
    los nombres de columna y la ruta por defecto via PAISES -- "CL"
    preserva exactamente el comportamiento anterior a este parametro."""
    cfg = PAISES[pais]
    ruta = Path(ruta_excel) if ruta_excel is not None else cfg["ruta_excel"]
```

(This replaces the existing `ruta = Path(ruta_excel) if ruta_excel is not None else RUTA_EXCEL_CENTRO_COSTOS` line.) Further down, inside the `try/except KeyError` block that builds `cols`, replace the 3 hardcoded lookups:

```python
            col_precio = cols[cfg["col_precio_unitario"]]
            col_total_sin_iva = cols[cfg["col_total_sin_iva"]]
            col_total_con_iva = cols[cfg["col_total_con_iva"]]
```

(replacing the existing `cols["P. Unitario sin IVA"]` / `cols["Total sin IVA (CLP)"]` / `cols["Total con IVA (CLP)"]` lines). Everything else in the function is unchanged.

- [ ] **Step 4: Run the tests again to verify they pass**

Run: `py -3.14 -m pytest "Cotizador Historico/Sistema/tests/test_lectura_excel.py" -v`
Expected: all tests PASS, including the 2 new ones and every pre-existing one (no regression for the CL default path).

- [ ] **Step 5: Write the failing tests for the no-reajuste path**

Add to `Cotizador Historico/Sistema/tests/test_consultar_item.py` (near the bottom, after the existing UF-fallback tests):

```python
# ── Perú: sin reajuste por indice ────────────────────────────────────────

def test_armar_compra_sin_reajuste_devuelve_precio_nominal():
    item = _item("LIMA-001", "Taladro", "Taladro percutor 20V", 300, datetime(2026, 1, 15),
                 total_sin_iva=300, total_con_iva=354)
    compra = ch.armar_compra_sin_reajuste(item)
    assert compra == {
        "n_ref": "LIMA-001",
        "fecha": "2026-01-15",
        "precio_original_sin_iva": 300,
        "precio_reajustado_hoy": 300,
        "precio_reajustado_hoy_con_iva": 354,
    }


def test_armar_indice_completo_sin_reajuste_omite_excluidos_y_agrega_metadata():
    items = [
        _item("LIMA-001", "Bomba", "Bomba centrífuga 1.5HP", 900, datetime(2026, 1, 1),
              total_sin_iva=900, total_con_iva=1062),
        _item("LIMA-002", "Cemento", "Saco 25kg", 50, None, excluido="sin_master"),
    ]
    reajustados, sin_uf_count = ch.armar_indice_completo_sin_reajuste(items)
    assert sin_uf_count == 0
    assert len(reajustados) == 1
    assert reajustados[0]["n_ref"] == "LIMA-001"
    assert reajustados[0]["precio_reajustado_hoy"] == 900


def test_consultar_item_pais_pe_no_llama_a_la_api_de_uf(monkeypatch, tmp_path):
    items = [_item("LIMA-001", "Taladro", "Taladro percutor 20V", 300, datetime(2026, 1, 15),
                    total_sin_iva=300, total_con_iva=354)]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None, pais="CL": items)

    def _falla_si_se_llama(fecha):
        raise AssertionError("no deberia consultar UF para pais='PE'")
    monkeypatch.setattr(ch, "consultar_uf_api", _falla_si_se_llama)

    resultado = ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17), pais="PE")

    assert resultado["encontrado"] is True
    assert resultado["compras"] == [{
        "n_ref": "LIMA-001", "fecha": "2026-01-15",
        "precio_original_sin_iva": 300,
        "precio_reajustado_hoy": 300, "precio_reajustado_hoy_con_iva": 354,
    }]
    assert resultado["sin_uf_count"] == 0
    assert resultado["uf_fuente"] is None


def test_consultar_item_pais_pe_promedia_precios_nominales(monkeypatch, tmp_path):
    items = [
        _item("LIMA-001", "Taladro", "Taladro percutor 20V", 300, datetime(2026, 1, 1),
              total_sin_iva=300, total_con_iva=354),
        _item("LIMA-002", "Taladro", "Taladro inalámbrico", 500, datetime(2026, 3, 1),
              total_sin_iva=500, total_con_iva=590),
    ]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None, pais="CL": items)

    resultado = ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17), pais="PE")

    assert resultado["promedio_reajustado"] == round((300 + 500) / 2)
    assert resultado["rango_minimo"] == 300
    assert resultado["rango_maximo"] == 500
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `py -3.14 -m pytest "Cotizador Historico/Sistema/tests/test_consultar_item.py" -v -k "sin_reajuste or pais_pe"`
Expected: FAIL — `armar_compra_sin_reajuste`/`armar_indice_completo_sin_reajuste` don't exist yet (`AttributeError`), and `consultar_item()` doesn't accept `pais` yet.

- [ ] **Step 7: Implement the no-reajuste helpers and wire `pais` into `consultar_item`**

In `Cotizador Historico/Sistema/cotizador_historico.py`, add these 2 functions right after `reajustar_todos` (which ends around line 380):

```python
def armar_compra_sin_reajuste(item):
    """Version 'PE' de reajustar_item: sin UF ni reajuste por indice --
    decision explicita del spec de expansion a Peru (no existe hoy una
    fuente publica equivalente a la UF chilena, ver docs/superpowers/specs/
    2026-08-21-peru-expansion-design.md decision 5). El precio historico se
    muestra tal cual (factor implicito 1) -- mismo shape de salida que
    reajustar_item para que consultar_item/build_visualizador.py/
    template.html no necesiten dos formatos distintos. A diferencia de
    reajustar_item, nunca devuelve None: no hay llamada de red que pueda
    fallar."""
    tasa_iva = tasa_iva_real(item.get("total_sin_iva"), item.get("total_con_iva"))
    precio = item["precio_unitario_sin_iva"]
    return {
        "n_ref": item["n_ref"],
        "fecha": item["fecha"].strftime("%Y-%m-%d"),
        "precio_original_sin_iva": precio,
        "precio_reajustado_hoy": precio,
        "precio_reajustado_hoy_con_iva": round(precio * tasa_iva),
    }


def armar_indice_completo_sin_reajuste(items):
    """Version 'PE' de reajustar_todos: aplica armar_compra_sin_reajuste a
    TODOS los items indexables (excluido_motivo is None), agregando la
    misma metadata de producto. sin_uf_count siempre 0 -- mismo contrato de
    retorno (lista, sin_uf_count) que reajustar_todos, para que
    build_visualizador.py de Peru pueda llamar a cualquiera de las dos sin
    ramificar el resto de su logica."""
    resultado = []
    for item in items:
        if item["excluido_motivo"] is not None:
            continue
        compra = armar_compra_sin_reajuste(item)
        compra["nombre_item"] = item["nombre_item"]
        compra["descripcion"] = item["descripcion"]
        compra["categoria_item"] = item.get("categoria_item")
        compra["proyecto"] = item.get("proyecto")
        compra["proveedor_tag"] = item.get("proveedor_tag")
        resultado.append(compra)
    return resultado, 0
```

Then change `consultar_item`'s signature (currently line 383) and the body between loading items and building the final result:

```python
def consultar_item(texto_busqueda, ruta_excel=None, fecha_hoy=None, uf_manual=None, fuente_manual=None, pais="CL"):
    """... (keep existing docstring, add:) 'pais'="PE" salta el reajuste
    por UF por completo (ver armar_compra_sin_reajuste) -- nunca llama a
    mindicador.cl ni al cache de disco para ese pais."""
    hoy = fecha_hoy or date.today()
    items = cargar_items_detalle(ruta_excel, pais=pais)
    excluidos_count = sum(1 for it in items if it["excluido_motivo"] is not None)

    coincidencias, sugerencias = buscar_items(items, texto_busqueda)
    if not coincidencias:
        return {
            "encontrado": False, "compras": [], "promedio_reajustado": None,
            "promedio_reajustado_con_iva": None, "rango_minimo": None, "rango_maximo": None,
            "excluidos_count": excluidos_count, "sugerencias": sugerencias,
            "sin_uf_count": 0, "uf_fuente": None,
        }

    if pais == "PE":
        compras = [armar_compra_sin_reajuste(item) for item in coincidencias]
        sin_uf_count = 0
        uf_fuente = None
    else:
        uf_hoy, uf_fuente = obtener_uf_hoy(hoy, uf_manual=uf_manual, fuente_manual=fuente_manual)
        cache_uf = cargar_cache_uf()
        compras = []
        sin_uf_count = 0
        for item in coincidencias:
            compra = reajustar_item(item, uf_hoy, cache_uf)
            if compra is None:
                sin_uf_count += 1
                continue
            compras.append(compra)
        guardar_cache_uf(cache_uf)
```

The rest of the function (the `if not compras:` early return and the final `return {...}` block building `reajustados`/`reajustados_con_iva`/averages) stays exactly as it is today — it already only references the local `compras`/`sin_uf_count`/`uf_fuente`/`excluidos_count` names, all of which are now set by either branch above.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `py -3.14 -m pytest "Cotizador Historico/Sistema/tests/test_consultar_item.py" -v`
Expected: all tests PASS, including every pre-existing CL test (the CL branch is untouched logic, just moved under `else:`).

- [ ] **Step 9: Run the full module test suite**

Run: `py -3.14 -m pytest "Cotizador Historico/Sistema/tests" -v`
Expected: all tests PASS (this also exercises `test_busqueda.py`/`test_uf.py`, neither of which this task touches, confirming no accidental regression).

- [ ] **Step 10: Commit**

```bash
git add "Cotizador Historico/Sistema/cotizador_historico.py" "Cotizador Historico/Sistema/tests/test_lectura_excel.py" "Cotizador Historico/Sistema/tests/test_consultar_item.py"
git commit -m "feat(cotizador-historico-peru): parametrizar cotizador_historico.py por pais"
```

---

### Task 2: `driver.py` + skill docs gain `--pais CL|PE`

**Files:**
- Modify: `Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py`
- Modify: `Cotizador Historico/.claude/skills/Cotizador_Historico/SKILL.md`

**Interfaces:**
- Consumes: `ch.consultar_item(..., pais=...)`, `ch.PAISES` (Task 1).
- Produces: `python driver.py status --pais PE`, `python driver.py consultar "<texto>" --pais PE`, `python driver.py visualizador --pais PE` — all default to `CL` when `--pais` is omitted, matching every existing invocation's current behavior exactly.

No automated test for this file (it has none today — this module's CLI layer is exercised manually/via the skill, same as `Registro_Centro_de_Costos/driver.py`). Verification is running the 3 commands by hand in Step 4.

- [ ] **Step 1: Add the `_extraer_pais` helper**

In `Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py`, right after the `import cotizador_historico as ch` line (line 52), add the same helper already used by `Registro_Centro_de_Costos/driver.py`:

```python
def _extraer_pais(argv):
    """Busca '--pais VALOR' en cualquier posicion de argv y lo separa del
    resto -- devuelve (pais, argv_sin_ese_flag). Default 'CL' si no aparece.
    Misma implementacion que Centro de Costos/.claude/skills/
    Registro_Centro_de_Costos/driver.py -- no se comparte el archivo entre
    skills (cada modulo financiero es su propio codebase, ver CLAUDE.md
    raiz), pero sí el patron."""
    argv = list(argv)
    if "--pais" in argv:
        idx = argv.index("--pais")
        pais = argv[idx + 1]
        del argv[idx:idx + 2]
        return pais, argv
    return "CL", argv
```

- [ ] **Step 2: Thread `pais` through `cmd_status`/`cmd_consultar`/`cmd_visualizador`**

Change `cmd_status` (line 64) to accept and use `pais`:

```python
def cmd_status(pais="CL"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    cfg = ch.PAISES[pais]
    print("=" * 70)
    print(f"  ESTADO COTIZADOR HISTORICO - {pais} (solo lectura, no escribe nada)")
    print("=" * 70)

    print(f"\nExcel Centro de Costos: {cfg['ruta_excel']}")
    print(f"  Existe: {cfg['ruta_excel'].exists()}")

    if not cfg["ruta_excel"].exists():
        print("\n[ERROR] No se encontro el Excel. Abortando status.")
        return 1

    try:
        items = ch.cargar_items_detalle(pais=pais)
    except ch.ExcelNoDisponibleError as exc:
        print(f"\n[ERROR] {exc}")
        return 1

    excluidos = [it for it in items if it["excluido_motivo"] is not None]
    print(f"\nItems indexables en Detalle: {len(items)}")
    print(
        f"  Excluidos (sin fecha resoluble via Master, sin precio unitario valido, "
        f"o Notas de Credito/devoluciones con precio negativo): {len(excluidos)}"
    )

    if pais == "CL":
        cache = ch.cargar_cache_uf()
        print(f"\nCache UF ({ch.RUTA_CACHE_UF.name}): {len(cache)} fecha(s) guardadas")
        print("\nProbando conexion a mindicador.cl (UF de hoy)...")
        try:
            uf_hoy = ch.consultar_uf_api(date.today())
            print(f"  OK. UF hoy = {uf_hoy}")
        except ch.UFNoDisponibleError as exc:
            print(f"  [WARN] Sin conexion o sin dato: {exc}")
    else:
        print("\nPerú no reajusta por indice (sin equivalente a la UF chilena) -- "
              "los precios se muestran nominales, no hay UF que consultar.")

    print("\n" + "=" * 70)
    print('  Nada fue escrito. Para consultar un item: python driver.py consultar "<texto>"')
    print("=" * 70)
    return 0
```

Change `cmd_consultar` (line 107) to accept `pais` and branch its table header/currency symbol:

```python
def cmd_consultar(args, pais="CL"):
    uf_manual, fuente_manual, args = _extraer_flags_uf(args)
    if not args:
        print('Uso: python driver.py consultar "<texto a buscar>" [--uf-manual VALOR --uf-fuente "<texto>"] [--pais CL|PE]')
        return 2

    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    texto = " ".join(args)
    simbolo = "S/" if pais == "PE" else "$"

    try:
        resultado = ch.consultar_item(texto, uf_manual=uf_manual, fuente_manual=fuente_manual, pais=pais)
    except (ch.ExcelNoDisponibleError, ch.UFNoDisponibleError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    if not resultado["encontrado"]:
        if resultado["sin_uf_count"]:
            print(
                f'Se encontraron {resultado["sin_uf_count"]} compra(s) para "{texto}", pero no '
                "se pudo obtener la UF de ninguna de sus fechas (sin conexion, o mindicador.cl "
                "no tiene dato para esas fechas)."
            )
        else:
            print(f'No se encontraron compras para "{texto}".')
            if resultado["sugerencias"]:
                print("Quizas quisiste decir:")
                for s in resultado["sugerencias"]:
                    print(f"  - {s}")
        return 0

    print(f'Compras encontradas para "{texto}":\n')
    if pais == "PE":
        print("| Fecha | N° Ref. | Precio (sin IGV) | Precio (con IGV) |")
        print("|---|---|---|---|")
        for c in resultado["compras"]:
            print(
                f"| {_fmt_fecha(c['fecha'])} | {c['n_ref']} | "
                f"{simbolo}{c['precio_reajustado_hoy']:,.0f} | "
                f"{simbolo}{c['precio_reajustado_hoy_con_iva']:,.0f} |"
            )
        print(
            f"| **Promedio** | | "
            f"{simbolo}{resultado['promedio_reajustado']:,.0f} | "
            f"{simbolo}{resultado['promedio_reajustado_con_iva']:,.0f} |"
        )
        print(f"\nRango: {simbolo}{resultado['rango_minimo']:,.0f} - {simbolo}{resultado['rango_maximo']:,.0f}")
    else:
        print("| Fecha | N° Ref. | Precio original (sin IVA) | Ajuste actual sin IVA | Ajuste actual con IVA |")
        print("|---|---|---|---|---|")
        for c in resultado["compras"]:
            print(
                f"| {_fmt_fecha(c['fecha'])} | {c['n_ref']} | "
                f"${c['precio_original_sin_iva']:,.0f} | "
                f"${c['precio_reajustado_hoy']:,.0f} | "
                f"${c['precio_reajustado_hoy_con_iva']:,.0f} |"
            )
        print(
            f"| **Promedio** | | | "
            f"${resultado['promedio_reajustado']:,.0f} | "
            f"${resultado['promedio_reajustado_con_iva']:,.0f} |"
        )
        print(f"\nRango (sin IVA): ${resultado['rango_minimo']:,.0f} - ${resultado['rango_maximo']:,.0f}")

    if resultado["excluidos_count"]:
        print(
            f"\n[INFO] {resultado['excluidos_count']} item(s) de Detalle excluido(s) "
            "del indice por no tener fecha resoluble via Master, por no tener precio "
            "unitario valido, o por ser Notas de Credito/devoluciones (precio negativo)."
        )

    if pais == "CL":
        if resultado["sin_uf_count"]:
            print(
                f"\n[INFO] {resultado['sin_uf_count']} compra(s) encontrada(s) se excluyeron del "
                "resultado por no poder obtener su UF (sin conexion, o mindicador.cl no tiene "
                "dato para esa fecha)."
            )
        if resultado.get("uf_fuente") and resultado["uf_fuente"] != "mindicador.cl":
            print(f"\n[AVISO] mindicador.cl no respondio -- se uso UF manual (fuente: {resultado['uf_fuente']}).")
    return 0
```

Change `cmd_visualizador` (line 173) to resolve a per-country `Visualizador Web/` folder, same pattern as `Registro_Centro_de_Costos/driver.py:cmd_visualizador`:

```python
def cmd_visualizador(pais="CL", uf_manual=None, fuente_manual=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raiz_modulo = Path(__file__).resolve().parents[3]
    if pais == "CL":
        ruta_viz = raiz_modulo / "Visualizador Web"
    else:
        ruta_viz = raiz_modulo.parent / "Peru" / "Cotizador Historico" / "Visualizador Web"
    ruta_build_script = ruta_viz / "build_visualizador.py"
    if not ruta_build_script.exists():
        print(f"[INFO] Visualizador Web de {pais} aún no implementado -- nada que regenerar.")
        return 0
    sys.path.insert(0, str(ruta_viz))
    sys.dont_write_bytecode = True
    import build_visualizador as bv  # noqa: E402
    if pais == "PE":
        return bv.build()
    return bv.build(uf_manual=uf_manual, fuente_manual=fuente_manual)
```

- [ ] **Step 3: Wire `--pais` into `main()`**

Replace `main()` (line 203):

```python
def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "consultar", "visualizador"):
        print(
            'Uso: python driver.py [status|consultar "<texto>"|'
            'visualizador] [--uf-manual VALOR --uf-fuente "<texto>"] [--pais CL|PE]'
        )
        return 2
    comando = sys.argv[1]
    pais, resto = _extraer_pais(sys.argv[2:])
    if comando == "status":
        return cmd_status(pais=pais)
    if comando == "visualizador":
        uf_manual, fuente_manual, _resto = _extraer_flags_uf(resto)
        return cmd_visualizador(pais=pais, uf_manual=uf_manual, fuente_manual=fuente_manual)
    return cmd_consultar(resto, pais=pais)
```

- [ ] **Step 4: Manually verify the 3 commands with `--pais PE`**

Run: `py -3.14 "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" status --pais PE`
Expected: prints the Perú Excel path (`Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx`), `Existe: True`, `Items indexables en Detalle: 0`, the "Perú no reajusta por indice" note, no mindicador.cl connection attempt.

Run: `py -3.14 "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" consultar "taladro" --pais PE`
Expected: `No se encontraron compras para "taladro".` (0 documents in Perú's workbook today — this is the correct, expected empty-catalog behavior, not a bug).

Run: `py -3.14 "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" visualizador --pais PE`
Expected at this point in the plan (before Task 3 creates the Perú build script): `[INFO] Visualizador Web de PE aún no implementado -- nada que regenerar.`, exit 0.

Run: `py -3.14 "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" status` (no `--pais`) and `... consultar "taladro"` (no `--pais`)
Expected: byte-for-byte identical output to before this task (Chile's `RUTA_EXCEL_CENTRO_COSTOS`, real item count, real mindicador.cl probe) — confirms the CL default path is untouched.

- [ ] **Step 5: Update `SKILL.md`**

In `Cotizador Historico/.claude/skills/Cotizador_Historico/SKILL.md`, add a short paragraph (near wherever the existing commands are documented) noting the new optional `--pais CL|PE` flag on all 3 commands (default `CL`), and that Perú never reajusta por indice — its `consultar`/`visualizador` output shows nominal historical soles.

- [ ] **Step 6: Commit**

```bash
git add "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" "Cotizador Historico/.claude/skills/Cotizador_Historico/SKILL.md"
git commit -m "feat(cotizador-historico-peru): agregar --pais CL|PE al driver de la skill"
```

---

### Task 3: Perú's `build_visualizador.py` + `template.html`

**Files:**
- Create: `Peru/Cotizador Historico/Visualizador Web/build_visualizador.py`
- Create: `Peru/Cotizador Historico/Visualizador Web/template.html`
- Create: `Peru/Cotizador Historico/Visualizador Web/CLAUDE.md`
- Create: `Peru/Cotizador Historico/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Consumes: `ch.cargar_items_detalle(ruta_excel, pais="PE")`, `ch.armar_indice_completo_sin_reajuste(items)` (Task 1).
- Produces: `extraer_indice_saneado(ruta_excel=None) -> dict` (keys: `generado`, `excluidos_count`, `sin_uf_count`, `items` — **no** `uf_hoy`/`uf_fecha`/`uf_fuente`, deliberately dropped since Perú has no such concept), `build() -> int`, both called by `driver.py:cmd_visualizador` (Task 2, already wired to look for this exact file).

- [ ] **Step 1: Write the failing test**

Create `Peru/Cotizador Historico/Visualizador Web/tests/test_build_visualizador.py`:

```python
import importlib.util
import sys
from pathlib import Path

import openpyxl

# Mismo patron que los otros pares CL/PE de este repo (ver Centro de
# Costos/Visualizador Web/tests/test_build_visualizador.py): "importlib"
# import-mode evita colisiones de test por basename, pero el MODULO FUENTE
# se carga por ruta bajo un nombre unico para que sys.modules no le
# entregue a este test el build_visualizador.py de otro pais/modulo.
_RUTA_BV = Path(__file__).resolve().parent.parent / "build_visualizador.py"
_spec = importlib.util.spec_from_file_location("build_visualizador_ch_pe", _RUTA_BV)
bv = importlib.util.module_from_spec(_spec)
sys.modules["build_visualizador_ch_pe"] = bv
_spec.loader.exec_module(bv)

HEADERS_DETALLE = [
    "N° Ref.", "Nombre Ítem", "Descripción", "P. Unitario sin IGV",
    "Total sin IGV (PEN)", "Total con IGV (PEN)",
]


def _wb_con_un_item(tmp_path):
    wb = openpyxl.Workbook()
    ws_detalle = wb.active
    ws_detalle.title = "Detalle"
    for c, h in enumerate(HEADERS_DETALLE, 1):
        ws_detalle.cell(row=1, column=c, value=h)
    fila = ("LIMA-001", "Taladro", "Taladro percutor 20V", 300, 300, 354)
    for c, v in enumerate(fila, 1):
        ws_detalle.cell(row=2, column=c, value=v)

    ws_master = wb.create_sheet("Master")
    for c, h in enumerate(["N° Ref.", "Fecha"], 1):
        ws_master.cell(row=1, column=c, value=h)
    from datetime import datetime
    ws_master.cell(row=2, column=1, value="LIMA-001")
    ws_master.cell(row=2, column=2, value=datetime(2026, 1, 15))

    ruta = tmp_path / "Centro de Costos Perú.xlsx"
    wb.save(str(ruta))
    return ruta


def test_extraer_indice_saneado_no_tiene_campos_de_uf(tmp_path):
    ruta = _wb_con_un_item(tmp_path)
    data = bv.extraer_indice_saneado(ruta)
    assert "uf_hoy" not in data
    assert "uf_fecha" not in data
    assert "uf_fuente" not in data


def test_extraer_indice_saneado_precio_es_nominal(tmp_path):
    ruta = _wb_con_un_item(tmp_path)
    data = bv.extraer_indice_saneado(ruta)
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["precio_reajustado_hoy"] == 300
    assert item["precio_reajustado_hoy_con_iva"] == 354


def test_extraer_indice_saneado_sin_items_no_falla(tmp_path):
    wb = openpyxl.Workbook()
    ws_detalle = wb.active
    ws_detalle.title = "Detalle"
    for c, h in enumerate(HEADERS_DETALLE, 1):
        ws_detalle.cell(row=1, column=c, value=h)
    ws_master = wb.create_sheet("Master")
    for c, h in enumerate(["N° Ref.", "Fecha"], 1):
        ws_master.cell(row=1, column=c, value=h)
    ruta = tmp_path / "Centro de Costos Perú.xlsx"
    wb.save(str(ruta))

    data = bv.extraer_indice_saneado(ruta)
    assert data["items"] == []
    assert data["excluidos_count"] == 0
    assert data["sin_uf_count"] == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -3.14 -m pytest "Peru/Cotizador Historico/Visualizador Web/tests/test_build_visualizador.py" -v`
Expected: FAIL — `Peru/Cotizador Historico/Visualizador Web/build_visualizador.py` doesn't exist yet.

- [ ] **Step 3: Create `build_visualizador.py`**

Create `Peru/Cotizador Historico/Visualizador Web/build_visualizador.py`:

```python
# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el visualizador web de Cotizador Historico Peru.

Copia de Cotizador Historico/Visualizador Web/build_visualizador.py
adaptada a Peru: lee Centro de Costos Peru.xlsx (pais="PE"), y en vez de
pedir la UF de hoy y reajustar, usa armar_indice_completo_sin_reajuste --
Peru no reajusta por ningun indice (ver docs/superpowers/specs/
2026-08-21-peru-expansion-design.md decision 5). El snapshot resultante NO
trae uf_hoy/uf_fecha/uf_fuente -- esos campos no existen para Peru.

Salidas (gitignoradas, se regeneran completas en cada corrida):
  data/cotizador-historico-peru.json  -- snapshot saneado intermedio (auditable)
  build/index.html                     -- visualizador final con datos incrustados

Uso:
  python build_visualizador.py
  (o, desde el driver de la skill: python driver.py visualizador --pais PE)
"""

import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent            # Peru/Cotizador Historico/Visualizador Web/
RAIZ_MODULO = RAIZ.parent                          # Peru/Cotizador Historico/
sys.path.insert(0, str(RAIZ_MODULO.parent.parent / "Cotizador Historico" / "Sistema"))
import cotizador_historico as ch  # noqa: E402

RUTA_EXCEL = ch.RUTA_EXCEL_CENTRO_COSTOS_PERU
RUTA_TEMPLATE = RAIZ / "template.html"
RUTA_DATA_JSON = RAIZ / "data" / "cotizador-historico-peru.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"


def extraer_indice_saneado(ruta_excel=None):
    """Lee Detalle+Master de Centro de Costos Peru.xlsx (pais="PE") y arma
    el indice completo SIN reajuste (ver ch.armar_indice_completo_sin_reajuste)
    -- a diferencia de la version de Chile, no pide ninguna UF ni incrusta
    uf_hoy/uf_fecha/uf_fuente en el snapshot."""
    items = ch.cargar_items_detalle(ruta_excel, pais="PE")
    excluidos_count = sum(1 for it in items if it["excluido_motivo"] is not None)
    reajustados, sin_uf_count = ch.armar_indice_completo_sin_reajuste(items)

    return {
        "generado": datetime.now().strftime("%d-%m-%Y %H:%M"),
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

    print(f"OK — {len(data['items'])} referencias indexadas (sin reajuste, precios nominales en soles)")
    print(f"Excluidos (sin fecha/precio valido, o Notas de Credito/devoluciones): {data['excluidos_count']}")
    print(f"Snapshot: {RUTA_DATA_JSON}")
    print(f"Visualizador: {RUTA_BUILD_HTML}")
    print("Para verlo: copialo a .worktrees/gh-pages/cotizador-historico-peru/index.html y "
          "haz git push, o abrelo directo en el navegador.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(build())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -3.14 -m pytest "Peru/Cotizador Historico/Visualizador Web/tests/test_build_visualizador.py" -v`
Expected: FAIL still — `template.html` doesn't exist yet, so `RUTA_TEMPLATE.exists()` check inside... actually `extraer_indice_saneado` doesn't check the template, only `build()` does. Re-check: `extraer_indice_saneado` only needs the Excel, so all 3 tests should PASS now (they call `bv.extraer_indice_saneado(ruta)` directly, never `bv.build()`).
Expected: 3 tests PASS.

- [ ] **Step 5: Copy Chile's template.html as the starting point**

```bash
cp "Cotizador Historico/Visualizador Web/template.html" "Peru/Cotizador Historico/Visualizador Web/template.html"
```

- [ ] **Step 6: Apply the text substitutions**

Use the Edit tool on `Peru/Cotizador Historico/Visualizador Web/template.html` with each of these `old_string`/`new_string` pairs (each `old_string` is unique in the file, confirmed by grep against the real file during planning):

| old_string | new_string |
|---|---|
| `<title>Cotizador Historico — Visualizador</title>` | `<title>Cotizador Historico Perú — Visualizador</title>` |
| `    <h2>Cotizador Historico — Visualizador</h2>` | `    <h2>Cotizador Historico Perú — Visualizador</h2>` |
| `        <h1>Cotizador Historico — Visualizador</h1>` | `        <h1>Cotizador Historico Perú — Visualizador</h1>` |
| `var CLP = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });` | `var CLP = new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN', maximumFractionDigits: 0 });` |
| `function fmtNum(n) { return new Intl.NumberFormat('es-CL').format(n); }` | `function fmtNum(n) { return new Intl.NumberFormat('es-PE').format(n); }` |
| `      Cotizador Historico — datos reales de <strong>Centro de Costos.xlsx</strong>, reajustados a\n      la UF vigente al generar este archivo. Snapshot generado el <span id="vizGeneratedFooter">—</span>.` | `      Cotizador Historico Perú — datos reales de <strong>Centro de Costos Perú.xlsx</strong>, precios históricos\n      en soles, sin reajuste por índice (Perú no tiene un equivalente a la UF chilena). Snapshot generado el <span id="vizGeneratedFooter">—</span>.` |
| `  document.getElementById('vizGenerated').innerHTML = 'UF utilizada <strong>' + fmt(DATA.uf_hoy) + '</strong> (actualizada ' + esc(DATA.uf_fecha) + ufFuenteSufijo() + ')';` | `  document.getElementById('vizGenerated').innerHTML = 'Precios históricos <strong>sin reajuste</strong> (nominal en soles)';` |
| `  document.getElementById('exportMeta').textContent = 'Generado ' + new Date().toLocaleString('es-CL') + ' · UF utilizada ' + fmt(DATA.uf_hoy) + ' (actualizada ' + DATA.uf_fecha + ufFuenteSufijo() + ')';` | `  document.getElementById('exportMeta').textContent = 'Generado ' + new Date().toLocaleString('es-PE') + ' · precios históricos, sin reajuste';` |
| `      '<div class="viz-kpi accent"><div class="label">Referencias indexadas</div><div class="value">' + fmtNum(ITEMS_VISIBLES.length) + '</div><div class="sub">disponibles para buscar</div></div>' +\n      '<div class="viz-kpi"><div class="label">UF utilizada</div><div class="value">' + fmt(DATA.uf_hoy) + '</div><div class="sub">actualizada ' + esc(DATA.uf_fecha) + ufFuenteSufijo() + '</div></div>';` | `      '<div class="viz-kpi accent"><div class="label">Referencias indexadas</div><div class="value">' + fmtNum(ITEMS_VISIBLES.length) + '</div><div class="sub">disponibles para buscar</div></div>' +\n      '<div class="viz-kpi"><div class="label">Moneda</div><div class="value">S/ Soles</div><div class="sub">precios históricos, sin reajuste</div></div>';` |
| `      '<div class="rc-price-main">' + fmt(item.precio_reajustado_hoy_con_iva) + '</div>' +\n      '<div class="rc-price-sub">c/IVA · ' + fmt(item.precio_reajustado_hoy) + ' s/IVA reajustado hoy</div>' +\n      '<div class="rc-original">Precio original: ' + fmt(item.precio_original_sin_iva) + ' (s/IVA, al momento de la compra)</div>' +` | `      '<div class="rc-price-main">' + fmt(item.precio_reajustado_hoy_con_iva) + '</div>' +\n      '<div class="rc-price-sub">c/IVA · ' + fmt(item.precio_reajustado_hoy) + ' s/IVA</div>' +` |
| `      '<span>Promedio reajustado (c/IVA): <b>' + fmt(promedio) + '</b></span>' +` | `      '<span>Promedio (c/IVA): <b>' + fmt(promedio) + '</b></span>' +` |
| `__CH_DATA_B64__` | *(leave every occurrence of this placeholder unchanged — it's the data-injection point `build()` replaces, not a Chile-specific string)* |

Apply each row above except the last (informational) one as one Edit call.

- [ ] **Step 7: Verify the placeholder survived and no stale UF/CLP text remains**

Run: `grep -c "__CH_DATA_B64__" "Peru/Cotizador Historico/Visualizador Web/template.html"`
Expected: `1` or more (the placeholder appears once as the injection point — confirm it's still present at all).

Run: `grep -n "UF utilizada\|UF vigente\|reajustado hoy\|Promedio reajustado\|CLP\|es-CL'\|Centro de Costos\.xlsx\b" "Peru/Cotizador Historico/Visualizador Web/template.html"`
Expected: no matches (every one of these was covered by the substitution table above).

- [ ] **Step 8: Create the content doc**

Create `Peru/Cotizador Historico/Visualizador Web/CLAUDE.md`:

```markdown
# CLAUDE.md — Visualizador Web de Cotizador Histórico Perú

Mismo contenido/decisiones que
[`../../../Cotizador Historico/Visualizador Web/CLAUDE.md`](../../../Cotizador%20Historico/Visualizador%20Web/CLAUDE.md)
(taxonomía de categorías, carrito de cotización sin persistencia, export
por copiar/pegar, gate de contraseña) — este archivo solo documenta lo que
difiere para Perú.

## Qué difiere de la versión de Chile

- **Fuente de datos**: `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx`
  (vía `ch.cargar_items_detalle(pais="PE")`), nunca el Excel de Chile.
- **Sin reajuste por índice**: Perú no tiene un equivalente a la UF
  chilena (decisión 5 del spec de expansión a Perú) — el precio que
  muestra cada tarjeta/carrito/export es el histórico nominal en soles,
  tal cual estaba al momento de la compra. El campo JSON
  `precio_reajustado_hoy` sigue existiendo (mismo shape que Chile, para
  reutilizar toda la lógica de taxonomía/carrito/export sin cambios) pero
  para Perú siempre es idéntico a `precio_original_sin_iva` —
  `ch.armar_compra_sin_reajuste` en vez de `ch.reajustar_item`.
- **Sin KPI de "UF utilizada"**: reemplazado por un KPI estático "Moneda:
  S/ Soles — precios históricos, sin reajuste".
- **Moneda**: PEN (`S/`), `Intl.NumberFormat('es-PE', {currency:'PEN'})`.
- **Comando de build**: `python driver.py visualizador --pais PE` (desde
  `Cotizador Historico/.claude/skills/Cotizador_Historico/`).
- **Publicación**: URL propia `cotizador-historico-peru`.

## Estado

0 documentos al 2026-08-26 (Perú aún no tiene facturas/boletas
registradas en Centro de Costos) — el dashboard se publica igual, vacío,
listo para cuando empiecen a fluir documentos reales.
```

- [ ] **Step 9: Commit**

```bash
git add "Peru/Cotizador Historico/Visualizador Web/build_visualizador.py" "Peru/Cotizador Historico/Visualizador Web/template.html" "Peru/Cotizador Historico/Visualizador Web/CLAUDE.md" "Peru/Cotizador Historico/Visualizador Web/tests/test_build_visualizador.py"
git commit -m "feat(cotizador-historico-peru): agregar build_visualizador.py, template.html y tests"
```

---

### Task 4: Generate the build and verify it renders correctly with 0 items

**Files:** none new — runs Task 1–3's code and inspects the output.

- [ ] **Step 1: Run the driver's visualizador command for Perú**

Run: `py -3.14 "Cotizador Historico/.claude/skills/Cotizador_Historico/driver.py" visualizador --pais PE`
Expected: exit 0, prints `OK — 0 referencias indexadas (sin reajuste, precios nominales en soles)` and the paths to `data/cotizador-historico-peru.json` and `build/index.html`.

- [ ] **Step 2: Confirm the build artifact exists**

Run: `ls "Peru/Cotizador Historico/Visualizador Web/build/index.html"`
Expected: file exists.

- [ ] **Step 3: Visual verification with Playwright**

Serve the `build/` folder locally with correct UTF-8 charset (a plain `python -m http.server` sends `text/html` with no charset, which mangles the accented characters this template has throughout — use a small custom handler that sets `Content-Type: text/html; charset=utf-8`, or any equivalent static server that sets that header). Using the `mcp__playwright__browser_navigate`/`browser_snapshot`/`browser_type`/`browser_click` tools:
1. Navigate to the served URL.
2. Enter the password `combustion` and submit.
3. Take a snapshot of the resulting empty-state dashboard.
4. Confirm: KPI row shows `Referencias indexadas: 0` and the `Moneda: S/ Soles` tile (not a UF value formatted as `$NaN` or similar), no visible "NaN"/"undefined" anywhere, the search/folder-browser area shows its empty state instead of erroring, and the header text reads "Precios históricos sin reajuste" rather than any mention of UF.

If any check fails, fix the specific line in `template.html` or `build_visualizador.py` and re-run Step 1.

- [ ] **Step 4: No commit** — this task only generates gitignored build output and does a manual check.

---

### Task 5: Add the hub card and update the hosting docs

**Files:**
- Modify: `Visualizador Web/index.html` (Perú `.hub-grid` section, added in the prior Centro de Costos Perú work — insert the new card there, after the existing "Centro de Costos — Perú" card)
- Modify: `Visualizador Web/CLAUDE.md` (hosting table + URL list)

**Interfaces:**
- Consumes: nothing new — static hand-edited HTML, no build step.

- [ ] **Step 1: Insert the new hub card into the existing Perú section**

In `Visualizador Web/index.html`, inside the `<h2 class="hub-section-title">🇵🇪 Perú</h2>` section's `.hub-grid`, after the existing "Centro de Costos — Perú" `</article>`, add:

```html
      <article class="hub-card">
        <div class="icon" aria-hidden="true">🧾</div>
        <h3>Cotizador Histórico — Perú</h3>
        <p class="desc">Historial de precios de materiales por proveedor en Perú, precios nominales en soles (sin reajuste por índice).</p>
        <a class="btn" href="https://cristobal-monzo.github.io/finanzas-quempin/cotizador-historico-peru/" target="_blank" rel="noopener">Abrir tablero →</a>
      </article>
```

- [ ] **Step 2: Update the hosting docs**

In `Visualizador Web/CLAUDE.md`, add to the URL list:

```
https://cristobal-monzo.github.io/finanzas-quempin/cotizador-historico-peru/
```

And add a row to the hosting table:

```
| Cotizador Histórico Perú | `cotizador-historico-peru` | `Peru/Cotizador Historico/Visualizador Web/build/index.html` |
```

- [ ] **Step 3: Verify with Playwright**

Navigate to the locally-served hub `index.html` (same UTF-8-charset server approach as Task 4 Step 3), snapshot, confirm the Perú section now shows 2 cards (Centro de Costos — Perú, Cotizador Histórico — Perú) with correct titles/links, in both light and dark theme.

- [ ] **Step 4: Commit**

```bash
git add "Visualizador Web/index.html" "Visualizador Web/CLAUDE.md"
git commit -m "feat(cotizador-historico-peru): agregar tarjeta al hub y documentar hosting"
```

---

### Task 6: Publish to GitHub Pages

**Files:** (in the `gh-pages` worktree, not `master`): `.worktrees/gh-pages/cotizador-historico-peru/index.html` (new), `.worktrees/gh-pages/index.html` (updated hub)

Same push-to-public-repo caution as prior Perú dashboard work — confirm with the user before the final `git push`. Steps 1–3 are local/reversible.

- [ ] **Step 1: Copy both files into the gh-pages worktree**

```bash
mkdir -p ".worktrees/gh-pages/cotizador-historico-peru"
cp "Peru/Cotizador Historico/Visualizador Web/build/index.html" ".worktrees/gh-pages/cotizador-historico-peru/index.html"
cp "Visualizador Web/index.html" ".worktrees/gh-pages/index.html"
```

- [ ] **Step 2: Review what's about to be published**

```bash
git -C ".worktrees/gh-pages" status
git -C ".worktrees/gh-pages" diff --stat
```

Expected: 1 new file (`cotizador-historico-peru/index.html`) + 1 modified file (`index.html`) — nothing else.

- [ ] **Step 3: Stage and commit in the worktree**

```bash
git -C ".worktrees/gh-pages" add "cotizador-historico-peru/index.html" "index.html"
git -C ".worktrees/gh-pages" commit -m "agregar tablero de Cotizador Historico Peru"
```

- [ ] **Step 4: Confirm with the user, then push**

```bash
git -C ".worktrees/gh-pages" push
```

Expected: push succeeds; `https://cristobal-monzo.github.io/finanzas-quempin/cotizador-historico-peru/` and the updated hub go live within a minute or two.

---

## Self-Review

**1. Spec coverage:**
- "parametrizar `cotizador_historico.py` (lee el Excel de Perú, sin reajuste por índice)" → Task 1.
- "skill `Cotizador_Historico` (+ `Actualizar_Cotizador`) con `--pais`" → Task 2 covers `Cotizador_Historico`'s own `driver.py`/`SKILL.md`. `Actualizar_Cotizador` (a thin wrapper skill that runs `driver.py visualizador` + publishes) is **not modified by this plan** — it's a separate skill file this plan doesn't touch; if the user wants `/Actualizar_Cotizador` itself to gain a `--pais` passthrough, that's a small follow-up against `Cotizador Historico/.claude/skills/Actualizar_Cotizador/SKILL.md`, out of scope here since the immediate ask was the dashboard, and the manual `driver.py visualizador --pais PE` command (Task 4) is sufficient to build/publish it today.
- "Depende de 1" (Centro de Costos país-core) → already done (prior work), consumed directly (`Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx`).
- Decision 5 (no reajuste, nominal soles, no new external dependency) → Task 1's `armar_compra_sin_reajuste`/`armar_indice_completo_sin_reajuste` never call any network API.
- Dashboard + hub row → Tasks 3–6, placed in the existing Perú section (added by the prior Centro de Costos Perú work), not a new row.

**2. Placeholder scan:** every step has literal code, exact commands, or (Task 3 Step 6) a complete, unambiguous substitution table against a file created by a literal `cp` in the preceding step — no "TBD"/"add error handling"/"similar to Task N".

**3. Type/name consistency:** `cargar_items_detalle(ruta_excel=None, pais="CL")`, `armar_compra_sin_reajuste(item)`, `armar_indice_completo_sin_reajuste(items) -> (list, int)`, `consultar_item(..., pais="CL")` (Task 1) are the exact names/signatures Task 2's `driver.py` and Task 3's `build_visualizador.py` call. The JSON shape `extraer_indice_saneado` produces (Task 3) — `generado`/`excluidos_count`/`sin_uf_count`/`items`, items shaped like `armar_compra_sin_reajuste`'s return plus the 5 metadata fields `armar_indice_completo_sin_reajuste` adds — matches what Task 3's template.html substitutions assume (no `uf_hoy`/`uf_fecha`/`uf_fuente` reads left in the Perú template after Step 6/7).
