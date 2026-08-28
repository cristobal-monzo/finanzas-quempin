# Análisis Financiero Perú Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a working Análisis Financiero Perú web dashboard (own GitHub Pages URL, own hub card) backed by a real, correctly-shaped `Análisis de Proyectos Perú.xlsx` workbook — the third and final Peru dashboard from the expansion spec.

**Architecture:** `Sistema Analisis Financiero/Sistema/analisis_financiero.py` gains a `pais="CL"|"PE"` parameter (shared, parametrized script, not cloned — same pattern as `cotizador_historico.py`). The scope turns out smaller than Cotizador's: `ejecutar()`/`confirmar_clientes_pendientes()` already accept path overrides, and `asegurar_estructura_workbook()` is already 100% path-generic (no currency-specific logic at all) — only `leer_detalle_centro_costos()` has one hardcoded column name (`"Total sin IVA (CLP)"`) that needs to become country-aware, and `actualizar_visualizador_af()` needs to resolve its Visualizador Web folder per country. `Centro de Costos/Sistema/auditor_centro_costos.py`'s PASO 12d currently hard-gates AF to Chile only (`if pais == "CL": actualizar_analisis_financiero() else: print("aún no implementado")`) — that gate is removed once AF is país-aware. The Visualizador Web layer stays a separate file pair per country (`Peru/Análisis Financiero/Visualizador Web/build_visualizador.py` + `template.html`), same pattern as the other 2 Peru dashboards.

**Tech Stack:** Python 3.14 + openpyxl, static HTML/CSS/vanilla JS, pytest, Playwright (manual visual verification only).

**Spec:** `docs/superpowers/specs/2026-08-21-peru-expansion-design.md` (sub-project 3: "Análisis Financiero Perú — parametrizar `analisis_financiero.py`, crear `Análisis de Proyectos Perú.xlsx`, skill `Registro_Analisis_Financiero` (+ `Actualizar_AF`) con `--pais`. Depende de 1.").

## Global Constraints

- **No currency conversion, no combined CLP+PEN view** — Perú reports in PEN only.
- **`analisis_financiero.py` is shared, parametrized code, never cloned** — `pais` defaults to `"CL"` everywhere, preserving every existing call site's exact behavior.
- **Perú starts with 0 projects** (spec § A: "Perú arranca sin proyectos registrados") — the workbook is scaffolded empty; `ejecutar(pais="PE")` must run cleanly against Perú's own `Centro de Costos Perú.xlsx` (currently 0 documents too) without crashing or requiring manual data first.
- Reuse the existing password gate verbatim (`combustion`).
- URL is structural and fixed: `https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero-peru/`.
- Never edit `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py` or `template.html` (Chile's) — only read from them to build Perú's copy.
- **A 4th active Claude Code session is concurrently editing shared files in this same repo** (confirmed live during the Cotizador Perú work — it added/reordered nav-bar entries across all `template.html` files without coordination). Before editing any of the 5 already-shared `template.html`/`Visualizador Web/index.html` files (Task 6), re-check their current content — don't assume the state this plan describes them in is still current.

---

## File Structure

```
Sistema Analisis Financiero/Sistema/analisis_financiero.py       # modified: PAISES, pais param
Sistema Analisis Financiero/Sistema/tests/test_lectura_centro_costos.py  # modified or created: pais="PE" tests
Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py  # modified: --pais flag
Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md   # modified: document --pais
Centro de Costos/Sistema/auditor_centro_costos.py                # modified: PASO 12d calls af.ejecutar(pais=pais)

Peru/Análisis Financiero/
├── Análisis de Proyectos Perú.xlsx    # new — scaffolded by ejecutar(pais="PE"), NOT hand-created
└── Visualizador Web/
    ├── CLAUDE.md              # new
    ├── template.html          # new — copy of CL's, formatoCLP → PEN/es-PE
    ├── build_visualizador.py  # new — copy of CL's, RUTA_EXCEL → Peru path
    ├── tests/
    │   └── test_build_visualizador.py   # new
    ├── data/                  # generated, gitignored
    └── build/                 # generated, gitignored

Visualizador Web/index.html      # modified: add Análisis Financiero Perú card to the Perú row
Visualizador Web/CLAUDE.md       # modified: hosting table + URL list
```

---

### Task 1: `analisis_financiero.py` país-parametrization

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py`
- Test: `Sistema Analisis Financiero/Sistema/tests/test_lectura_centro_costos.py` (create if this exact file doesn't already exist — check first; if a test file already covers `leer_detalle_centro_costos`, add to it instead of creating a duplicate)

**Interfaces:**
- Produces: `leer_detalle_centro_costos(ruta_excel_cc, pais="CL") -> list[dict]` (same shape as today), `ejecutar(ruta_excel_af=None, ruta_excel_cc=None, raiz_facturas_cc=None, raiz_respaldos=RAIZ_RESPALDOS, ruta_clientes_pendientes=RUTA_CLIENTES_PENDIENTES, dry_run=False, pais="CL") -> dict` (same shape as today; the 3 path params now default to `None` and resolve via `PAISES[pais]` when omitted — an explicit path argument still always wins), `actualizar_visualizador_af(pais="CL") -> bool`, `main(pais="CL") -> None`.
- Consumes: nothing new — this task only touches this one file.

Existing behavior for every current call site (`pais` omitted, all path params omitted) must not change — verified by running the full existing test suite (Steps 2 and 6) with zero diffs.

- [ ] **Step 1: Check for an existing test file covering `leer_detalle_centro_costos`, then write the failing tests**

Run: `grep -rl "leer_detalle_centro_costos" "Sistema Analisis Financiero/Sistema/tests/"` to find where it's already tested. Add these tests to that file (or to a new `test_lectura_centro_costos.py` if none covers it):

```python
def _wb_centro_costos_pe(tmp_path, filas_detalle):
    """filas_detalle: lista de tuplas (n_ref, categoria_item, total_sin_igv).
    Headers reales de Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx
    (confirmados via openpyxl) -- IGV/PEN en vez de IVA/CLP."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Detalle"
    headers = ["N° Ref.", "Categoría Ítem", "Total sin IGV (PEN)"]
    for c, h in enumerate(headers, 1):
        ws.cell(row=1, column=c, value=h)
    for r, fila in enumerate(filas_detalle, 2):
        for c, valor in enumerate(fila, 1):
            ws.cell(row=r, column=c, value=valor)
    ruta = tmp_path / "Centro de Costos Perú.xlsx"
    wb.save(ruta)
    return ruta


def test_leer_detalle_centro_costos_pais_pe_lee_columna_igv_pen(tmp_path):
    ruta = _wb_centro_costos_pe(tmp_path, [("LIMA-001", "Materiales", 300.0)])
    items = af.leer_detalle_centro_costos(ruta, pais="PE")
    assert items == [{"n_ref": "LIMA-001", "categoria_item": "Materiales", "total_sin_iva": 300.0}]


def test_leer_detalle_centro_costos_pais_cl_no_cambia_con_el_parametro_default(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Detalle"
    headers = ["N° Ref.", "Categoría Ítem", "Total sin IVA (CLP)"]
    for c, h in enumerate(headers, 1):
        ws.cell(row=1, column=c, value=h)
    ws.cell(row=2, column=1, value="UMAG-001")
    ws.cell(row=2, column=2, value="Materiales")
    ws.cell(row=2, column=3, value=90000.0)
    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(ruta)

    items = af.leer_detalle_centro_costos(ruta, pais="CL")
    assert items == [{"n_ref": "UMAG-001", "categoria_item": "Materiales", "total_sin_iva": 90000.0}]
```

Add `import openpyxl` and `import analisis_financiero as af` at the top if the target file doesn't already import them under those names (check the file's existing imports first — every test file in this module already does, following the same convention as `Cotizador Historico/Sistema/tests/`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Sistema/tests" -v -k pais`
Expected: FAIL — `leer_detalle_centro_costos()` doesn't accept a `pais` keyword yet.

- [ ] **Step 3: Add `PAISES` and thread `pais` into `leer_detalle_centro_costos`**

In `Sistema Analisis Financiero/Sistema/analisis_financiero.py`, after the existing `RAIZ_VISUALIZADOR_WEB_AF = RAIZ_MODULO / "Visualizador Web"` line (line 55), add:

```python
# Config por pais -- solo lo que este modulo necesita (Excel de trabajo,
# Excel/carpeta de facturas de Centro de Costos que lee, columna cuyo
# nombre varia entre IVA/CLP y IGV/PEN, y carpeta del visualizador). Mismo
# patron que PAISES en Cotizador Historico/Sistema/cotizador_historico.py.
RAIZ_PERU = RAIZ_MODULO.parent / "Peru"
PAISES = {
    "CL": {
        "ruta_excel_af": RUTA_EXCEL,
        "ruta_excel_cc": RUTA_EXCEL_CENTRO_COSTOS,
        "raiz_facturas_cc": RAIZ_FACTURAS_CENTRO_COSTOS,
        "raiz_visualizador_web": RAIZ_VISUALIZADOR_WEB_AF,
        "col_total_sin_iva_cc": "Total sin IVA (CLP)",
    },
    "PE": {
        "ruta_excel_af": RAIZ_PERU / "Análisis Financiero" / "Análisis de Proyectos Perú.xlsx",
        "ruta_excel_cc": RAIZ_PERU / "Centro de Costos" / "Excel" / "Centro de Costos Perú.xlsx",
        "raiz_facturas_cc": (
            RAIZ_CENTRO_COSTOS / "Sitio de comunicación - Centro de Costos 1" / "Facturas y Boletas" / "Perú"
        ),
        "raiz_visualizador_web": RAIZ_PERU / "Análisis Financiero" / "Visualizador Web",
        "col_total_sin_iva_cc": "Total sin IGV (PEN)",
    },
}
```

Then change `leer_detalle_centro_costos` (currently line 636):

```python
def leer_detalle_centro_costos(ruta_excel_cc: Path, pais: str = "CL") -> list[dict]:
    """Lee la hoja 'Detalle' de Centro de Costos.xlsx -- SOLO LECTURA, este
    módulo nunca escribe ese archivo. Filas sin N° Ref. o sin Total sin IVA
    se ignoran (no se puede agrupar ni sumar sin esos dos datos).

    'pais' selecciona el nombre de la columna de total via PAISES -- "CL"
    preserva exactamente el comportamiento anterior a este parametro."""
    col_total_nombre = PAISES[pais]["col_total_sin_iva_cc"]
    wb = openpyxl.load_workbook(ruta_excel_cc, data_only=True)
    ws = wb["Detalle"]
    encabezados = [celda.value for celda in ws[1]]
    col_n_ref = encabezados.index("N° Ref.") + 1
    col_categoria = encabezados.index("Categoría Ítem") + 1
    col_total_sin_iva = encabezados.index(col_total_nombre) + 1

    items = []
    for fila in ws.iter_rows(min_row=2):
        n_ref = fila[col_n_ref - 1].value
        total = fila[col_total_sin_iva - 1].value
        if n_ref is None or total is None:
            continue
        categoria = fila[col_categoria - 1].value
        items.append({"n_ref": n_ref, "categoria_item": categoria, "total_sin_iva": float(total)})
    return items
```

(Only the signature and the `col_total_sin_iva` lookup line changed — everything else in the function body is identical to today.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Sistema/tests" -v -k pais`
Expected: PASS.

- [ ] **Step 5: Thread `pais` into `ejecutar`, `actualizar_visualizador_af`, and `main`**

Change `ejecutar`'s signature (currently line 1434) and the top of its body:

```python
def ejecutar(
    ruta_excel_af: Path | None = None,
    ruta_excel_cc: Path | None = None,
    raiz_facturas_cc: Path | None = None,
    raiz_respaldos: Path = RAIZ_RESPALDOS,
    ruta_clientes_pendientes: Path = RUTA_CLIENTES_PENDIENTES,
    dry_run: bool = False,
    pais: str = "CL",
) -> dict:
    """... (keep existing docstring, add:) 'pais' resuelve ruta_excel_af/
    ruta_excel_cc/raiz_facturas_cc via PAISES cuando se omiten -- un valor
    explícito para cualquiera de los 3 sigue ganando (mismo contrato que
    antes de este parámetro, con "CL" como default transparente)."""
    cfg = PAISES[pais]
    if ruta_excel_af is None:
        ruta_excel_af = cfg["ruta_excel_af"]
    if ruta_excel_cc is None:
        ruta_excel_cc = cfg["ruta_excel_cc"]
    if raiz_facturas_cc is None:
        raiz_facturas_cc = cfg["raiz_facturas_cc"]

    resumen = {
        "avisos": [], "carpetas_creadas": [], "categorias_no_mapeadas": [],
        "clientes_pendientes": [], "proyectos_nuevos": [], "error": None,
    }
```

(This replaces the existing `resumen = {...}` initialization as the new first executable statement — the dict literal itself is unchanged.) Further down, change the one call site that reads Centro de Costos' Detalle (currently `items_detalle = leer_detalle_centro_costos(ruta_excel_cc)`):

```python
    items_detalle = leer_detalle_centro_costos(ruta_excel_cc, pais=pais)
```

And change the visualizador call near the end of the function (currently `if not actualizar_visualizador_af():`, inside the final `try` block after `wb.save(ruta_excel_af)`):

```python
    try:
        if not actualizar_visualizador_af(pais=pais):
```

(Only this one line changes — keep the rest of that `try`/`except` block exactly as it is today.)

Change `actualizar_visualizador_af` (currently line 1412):

```python
def actualizar_visualizador_af(pais: str = "CL") -> bool:
    """... (keep existing docstring, add:) 'pais' resuelve la carpeta del
    visualizador via PAISES -- "CL" preserva el comportamiento anterior."""
    raiz_viz = PAISES[pais]["raiz_visualizador_web"]
    ruta_build_script = raiz_viz / "build_visualizador.py"
    if not ruta_build_script.exists():
        return False
    ya_en_path = str(raiz_viz) in sys.path
    if not ya_en_path:
        sys.path.insert(0, str(raiz_viz))
    try:
        sys.modules.pop("build_visualizador", None)
        import build_visualizador as bv
        return bv.build() == 0
    finally:
        if not ya_en_path and str(raiz_viz) in sys.path:
            sys.path.remove(str(raiz_viz))
```

(Only `RAIZ_VISUALIZADOR_WEB_AF` → `raiz_viz` changed throughout — same logic.)

Change `main` (currently line 1544):

```python
def main(pais: str = "CL") -> None:
    resumen = ejecutar(pais=pais)
    print(f"=== Análisis Financiero{' - ' + pais if pais != 'CL' else ''} ===")
```

(Keep the rest of `main`'s body — the `if resumen["proyectos_nuevos"]:` block onward — exactly as it is today.)

- [ ] **Step 6: Run the full module test suite**

Run: `py -3.14 -m pytest "Sistema Analisis Financiero/Sistema/tests" -v`
Expected: all tests PASS (this module has 71+ existing tests per its own `CLAUDE.md` — none of them should change outcome, since every default-`pais="CL"` path is unchanged logic).

- [ ] **Step 7: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests"
git commit -m "feat(analisis-financiero-peru): parametrizar analisis_financiero.py por pais"
```

---

### Task 2: `driver.py` + `SKILL.md` gain `--pais CL|PE`

**Files:**
- Modify: `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py`
- Modify: `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md`

**Interfaces:**
- Consumes: `af.ejecutar(..., pais=...)`, `af.PAISES` (Task 1).
- Produces: `python driver.py status --pais PE`, `python driver.py run --pais PE`, `python driver.py confirmar-cliente --pais PE [--todos|TAG ...]`, `python driver.py visualizador --pais PE` — all default to `CL` when `--pais` is omitted.

No automated test for this file (matches the other 2 modules' drivers — none have one). Verification is running the commands by hand in Step 4.

- [ ] **Step 1: Add the `_extraer_pais` helper**

In `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py`, right after `import analisis_financiero as af` (line 42), add the same helper used by the other 2 skills:

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

- [ ] **Step 2: Thread `pais` through the 4 commands**

Change `cmd_status` (line 45):

```python
def cmd_status(pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    cfg = af.PAISES[pais]
    print("=" * 70)
    print(f"  ESTADO ANÁLISIS FINANCIERO - {pais} (solo lectura, no escribe nada)")
    print("=" * 70)

    print(f"\nExcel de trabajo: {cfg['ruta_excel_af']}")
    print(f"  Existe: {cfg['ruta_excel_af'].exists()}")
    print(f"\nExcel Centro de Costos: {cfg['ruta_excel_cc']}")
    print(f"  Existe: {cfg['ruta_excel_cc'].exists()}")

    resumen = af.ejecutar(dry_run=True, pais=pais)
```

(The rest of `cmd_status` — everything from `if resumen["proyectos_nuevos"]:` onward — stays exactly as it is today.)

Change `cmd_run` (line 87):

```python
def cmd_run(pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    af.main(pais=pais)
    return 0
```

Change `cmd_confirmar_cliente` (line 93) to accept and pass `pais`:

```python
def cmd_confirmar_cliente(args: list[str], pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    cfg = af.PAISES[pais]

    if not args:
        pendientes = af.confirmar_clientes_pendientes(None, ruta_excel=cfg["ruta_excel_af"])
        print(f"\nClientes pendientes de confirmar: {len(pendientes)}")
        for p in pendientes:
            print(
                f"  - {p['tag']}: '{p['nombre_proyecto']}' -> sugerido "
                f"'{p['cliente_sugerido']}' (similitud {p['similitud']})"
            )
        if pendientes:
            print(
                "\nPara aplicar: python driver.py confirmar-cliente --todos"
                " (o 'python driver.py confirmar-cliente <TAG> ...' para solo algunos)"
            )
        return 0

    objetivo = "TODOS" if args == ["--todos"] else args
    aplicados = af.confirmar_clientes_pendientes(objetivo, ruta_excel=cfg["ruta_excel_af"])
    if not aplicados:
        print("\nNo hay clientes pendientes que coincidan con lo pedido.")
    for p in aplicados:
        print(f"  [OK] {p['tag']} -> Cliente '{p['cliente_sugerido']}' confirmado (azul marino).")
    return 0
```

Change `cmd_visualizador` (line 120) to resolve a per-country folder, same pattern as the other 2 skills:

```python
def cmd_visualizador(pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raiz_viz = af.PAISES[pais]["raiz_visualizador_web"]
    ruta_build_script = raiz_viz / "build_visualizador.py"
    if not ruta_build_script.exists():
        print(f"[INFO] Visualizador Web de {pais} aún no implementado -- nada que regenerar.")
        return 0
    ya_en_path = str(raiz_viz) in sys.path
    if not ya_en_path:
        sys.path.insert(0, str(raiz_viz))
    sys.dont_write_bytecode = True
    sys.modules.pop("build_visualizador", None)
    import build_visualizador as bv
    return bv.build()
```

- [ ] **Step 3: Wire `--pais` into `main()`**

Replace `main()` (line 129):

```python
def main() -> int:
    comandos = ("status", "run", "confirmar-cliente", "visualizador")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        print("Uso: python driver.py [status|run|confirmar-cliente [--todos|TAG ...]|visualizador] [--pais CL|PE]")
        return 2
    comando = sys.argv[1]
    pais, resto = _extraer_pais(sys.argv[2:])
    if comando == "status":
        return cmd_status(pais=pais)
    if comando == "confirmar-cliente":
        return cmd_confirmar_cliente(resto, pais=pais)
    if comando == "visualizador":
        return cmd_visualizador(pais=pais)
    return cmd_run(pais=pais)
```

- [ ] **Step 4: Manually verify the 4 commands with `--pais PE`, and confirm CL is unchanged**

Run: `py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" status --pais PE`
Expected: prints Perú's 2 Excel paths, `Existe: False` for `Análisis de Proyectos Perú.xlsx` (Task 4 creates it), `Existe: True` for Perú's Centro de Costos, `Proyectos nuevos que SE CREARÍAN` empty (Perú's `Master` has 0 real project rows), no crash.

Run: `py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" status` (no `--pais`)
Expected: byte-for-byte identical output to before this task.

- [ ] **Step 5: Update `SKILL.md`**

In `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md`, add a short paragraph documenting the new optional `--pais CL|PE` flag on all 4 commands (default `CL`).

- [ ] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md"
git commit -m "feat(analisis-financiero-peru): agregar --pais CL|PE al driver de la skill"
```

---

### Task 3: `auditor_centro_costos.py` PASO 12d stops gating AF to Chile-only

**Files:**
- Modify: `Centro de Costos/Sistema/auditor_centro_costos.py:2278` (`actualizar_analisis_financiero`), `:2580-2584` (PASO 12d call site)

**Interfaces:**
- Consumes: `af.ejecutar(pais=...)` (Task 1) — imported dynamically via the existing `_modulo_hermano_fresco` context manager, unchanged.

- [ ] **Step 1: Add `pais` param to `actualizar_analisis_financiero`**

Change (currently line 2278):

```python
def actualizar_analisis_financiero(pais="CL"):
    """... (keep existing docstring)."""
    ruta_script = RAIZ_ANALISIS_FINANCIERO / "Sistema" / "analisis_financiero.py"
    if not ruta_script.exists():
        print(f"  [WARN] No existe {ruta_script}, se omite este paso.")
        return False
    try:
        with _modulo_hermano_fresco(ruta_script.parent, "analisis_financiero") as af:
            resumen = af.ejecutar(pais=pais)
            if resumen["error"]:
                print(f"  [WARN] Análisis Financiero terminó con error: {resumen['error']}")
                return False
            if pais == "CL":
                _avisar_reportes_pendientes()
            return True
    except Exception as e:
        print(f"  [WARN] No se pudo actualizar Análisis Financiero ({e}).")
        print("         El Excel de Centro de Costos si quedo guardado; correr manualmente "
              "'python driver.py run' en Sistema Analisis Financiero despues.")
        return False
```

(Only the signature, the `af.ejecutar(pais=pais)` call, and gating `_avisar_reportes_pendientes()` to `pais == "CL"` changed — reportes PDF are a Chile-only concept for now, per `Sistema Analisis Financiero/CLAUDE.md`'s "Reportes PDF" section, which never mentions Perú; calling it for `pais="PE"` would just report on Chile's own pending reports, which is misleading noise during a Perú run.)

- [ ] **Step 2: Update the PASO 12d call site**

Change (currently lines 2580-2584):

```python
    print("\n--- PASO 12d: Actualizar Análisis Financiero ---")
    actualizar_analisis_financiero(pais=pais)
```

(Removes the `if pais == "CL": ... else: print("aún no implementado")` gate entirely — `actualizar_analisis_financiero` now handles every país the same way, best-effort as before.)

- [ ] **Step 3: Run the full Centro de Costos test suite**

Run: `py -3.14 -m pytest "Centro de Costos/Sistema/tests" -v`
Expected: all tests PASS — none of them should depend on the removed gate's print text (grep first to confirm: `grep -rn "aún no implementado" "Centro de Costos/Sistema/tests"` should return nothing, or only unrelated matches for the Visualizador Web gate at PASO 12c, which this task does not touch).

- [ ] **Step 4: Commit**

```bash
git add "Centro de Costos/Sistema/auditor_centro_costos.py"
git commit -m "feat(analisis-financiero-peru): encadenar Analisis Financiero Peru desde el run de Centro de Costos"
```

---

### Task 4: Scaffold `Análisis de Proyectos Perú.xlsx`

**Files:** none new by hand — this task runs Task 1/2's code to generate the workbook.

- [ ] **Step 1: Run `status --pais PE` to confirm the file doesn't exist yet**

Run: `py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" status --pais PE`
Expected: `Existe: False` for the Perú Excel.

- [ ] **Step 2: Run `run --pais PE` to create it**

Run: `py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" run --pais PE`
Expected: exit 0, no traceback, prints `=== Análisis Financiero - PE ===` with no "Proyectos nuevos"/"Carpetas de proyecto"/"Categorías sin mapeo" lines (Perú's Centro de Costos has 0 real documents today) — the file gets created and saved.

- [ ] **Step 3: Verify the workbook's structure**

Run:
```bash
py -3.14 -c "
import openpyxl
wb = openpyxl.load_workbook('Peru/Análisis Financiero/Análisis de Proyectos Perú.xlsx')
print(wb.sheetnames)
"
```
Expected: `['Proyectos', 'Detalle Costos Reales', 'Indicadores', 'Clientes', 'Glosario KPIs']` — all 5 sheets, matching `asegurar_estructura_workbook`'s contract.

- [ ] **Step 4: Run `status --pais PE` again to confirm idempotency**

Run: `py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" status --pais PE`
Expected: `Existe: True` now, no errors, no "Nada fue escrito" violated (it's `status`, read-only).

- [ ] **Step 5: No commit** — the `.xlsx` itself is real financial-adjacent data infrastructure, excluded from git by the root `.gitignore`'s `*.xlsx` pattern (verify with `git check-ignore -v "Peru/Análisis Financiero/Análisis de Proyectos Perú.xlsx"` per the root `CLAUDE.md`'s instruction to always verify new data-file locations against `.gitignore`).

---

### Task 5: Perú's `build_visualizador.py` + `template.html`

**Files:**
- Create: `Peru/Análisis Financiero/Visualizador Web/build_visualizador.py`
- Create: `Peru/Análisis Financiero/Visualizador Web/template.html`
- Create: `Peru/Análisis Financiero/Visualizador Web/CLAUDE.md`
- Create: `Peru/Análisis Financiero/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Consumes: `af.PAISES["PE"]` (Task 1) for `RUTA_EXCEL`.
- Produces: `extraer_datos_saneados(ruta_excel) -> dict` (same shape as Chile's), `build() -> int`, both called by `driver.py:cmd_visualizador` (Task 2, already wired to look for this exact file).

Chile's `build_visualizador.py` has **no hardcoded currency-specific column names** (unlike Cotizador's) — it only reads `af.HEADERS_PROYECTOS`/`af.HOJA_*` constants, which are identical between CL and PE (only `analisis_financiero.py`'s `leer_detalle_centro_costos`, called inside `ejecutar()` not here, has that concern, and it's already handled by Task 1). This file only needs its `RUTA_EXCEL` pointed at Perú's workbook and its currency formatter changed.

- [ ] **Step 1: Write the failing test**

Create `Peru/Análisis Financiero/Visualizador Web/tests/test_build_visualizador.py`:

```python
import importlib.util
import sys
from pathlib import Path

import openpyxl

_RUTA_BV = Path(__file__).resolve().parent.parent / "build_visualizador.py"
_spec = importlib.util.spec_from_file_location("build_visualizador_af_pe", _RUTA_BV)
bv = importlib.util.module_from_spec(_spec)
sys.modules["build_visualizador_af_pe"] = bv
_spec.loader.exec_module(bv)


def test_extraer_datos_saneados_sin_proyectos_no_falla(tmp_path):
    wb = openpyxl.Workbook()
    ws_p = wb.active
    ws_p.title = "Proyectos"
    for c, h in enumerate(bv.af.HEADERS_PROYECTOS, 1):
        ws_p.cell(row=1, column=c, value=h)
    ws_d = wb.create_sheet("Detalle Costos Reales")
    for c, h in enumerate(bv.af.HEADERS_DETALLE_COSTOS_REALES, 1):
        ws_d.cell(row=1, column=c, value=h)
    ruta = tmp_path / "Análisis de Proyectos Perú.xlsx"
    wb.save(str(ruta))

    data = bv.extraer_datos_saneados(ruta)
    assert data["proyectos"] == []
    assert data["clientes"] == []
    assert data["pendientes"] == []
    assert data["kpis_proyectos"]["n_completos"] == 0
    assert data["kpis_proyectos"]["nota_promedio"] == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -3.14 -m pytest "Peru/Análisis Financiero/Visualizador Web/tests/test_build_visualizador.py" -v`
Expected: FAIL — `build_visualizador.py` doesn't exist yet.

- [ ] **Step 3: Create `build_visualizador.py`**

Create `Peru/Análisis Financiero/Visualizador Web/build_visualizador.py`. This is Chile's file with only 2 real changes: `sys.path`/import resolve to the shared `analisis_financiero.py` in `Sistema Analisis Financiero/Sistema/` (not moved, per architecture), and `RUTA_EXCEL` points at Perú's workbook via `af.PAISES["PE"]`. Every function body (`leer_proyectos`, `es_proyecto_completo`, `sumar_costos_reales_por_bucket`, `leer_detalle_subcategorias`, `calcular_peso_cartera`, `_fecha_str`, `_kpis_por_categoria`, `_margen_por_dia`, `calcular_kpis_proyecto`, `percentil_inclusivo`, `calcular_clientes`, `calcular_categorias`, `embeber_reportes_pdf`, `extraer_datos_saneados`, `build`) is copied byte-for-byte from `Sistema Analisis Financiero/Visualizador Web/build_visualizador.py` — read that file (already read in full during planning) and reproduce it verbatim below, with only the header block and `RUTA_EXCEL`/`RAIZ_REPORTES`/`URL_PLANILLA_PENDIENTE` changed:

```python
# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el visualizador web de Análisis Financiero Perú.

Copia de Sistema Analisis Financiero/Visualizador Web/build_visualizador.py
-- ninguna de sus funciones depende de nombres de columna que varíen entre
países (a diferencia de Cotizador Histórico), así que el único cambio real
es de dónde lee el Excel. Ver ese archivo para el detalle de cada decisión
de recomputo (por qué nunca lee celdas de fórmula de Indicadores/Clientes).

Ver docs/superpowers/specs/2026-07-23-analisis-financiero-visualizador-web-
design.md para el diseno completo (Chile), y docs/superpowers/specs/
2026-08-21-peru-expansion-design.md para el contexto de Perú.
"""

import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "Sistema Analisis Financiero" / "Sistema"))
import analisis_financiero as af  # noqa: E402

RAIZ = Path(__file__).resolve().parent  # Peru/Análisis Financiero/Visualizador Web/
RUTA_EXCEL = af.PAISES["PE"]["ruta_excel_af"]
RUTA_TEMPLATE = RAIZ / "template.html"
RUTA_DATA_JSON = RAIZ / "data" / "analisis-financiero-peru.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"
RAIZ_REPORTES = RAIZ.parent / "Reportes"

# Perú no tiene todavía un link de SharePoint real para su planilla (no
# existe fuera de este repo) -- el mensaje de "pendientes" queda sin link
# hasta que se publique una. Con 0 proyectos hoy, "pendientes" siempre está
# vacío igual, así que esto no tiene efecto visible por ahora.
URL_PLANILLA_PENDIENTE = None

CLAVE_POR_ENCABEZADO = {
    "Estado": "estado",
    "Fecha de inicio": "fecha_inicio",
    "Monto de Venta (sin IVA)": "monto_venta",
    "Costos Materiales Proyectados": "materiales_proy",
    "Costos Equipos Proyectados": "equipos_proy",
    "Mano de Obra Proyectada": "mo_proy",
    "Otros Costos Proyectados": "otros_proy",
    "Mano de Obra Real": "mo_real",
}


def _valor_columna(ws, fila, nombre_columna):
    col = af.HEADERS_PROYECTOS.index(nombre_columna) + 1
    return ws.cell(row=fila, column=col).value


def leer_proyectos(ws_proyectos) -> list[dict]:
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
            "fecha_cierre": _valor_columna(ws_proyectos, fila, "Fecha de cierre"),
            "categoria": _valor_columna(ws_proyectos, fila, "Categoría"),
            "monto_venta": _valor_columna(ws_proyectos, fila, "Monto de Venta (sin IVA)"),
            "materiales_proy": _valor_columna(ws_proyectos, fila, "Costos Materiales Proyectados"),
            "equipos_proy": _valor_columna(ws_proyectos, fila, "Costos Equipos Proyectados"),
            "mo_proy": _valor_columna(ws_proyectos, fila, "Mano de Obra Proyectada"),
            "otros_proy": _valor_columna(ws_proyectos, fila, "Otros Costos Proyectados"),
            "mo_real": _valor_columna(ws_proyectos, fila, "Mano de Obra Real"),
        })
    return proyectos


def es_proyecto_completo(p: dict) -> bool:
    return af.tiene_datos_completos(lambda campo: p.get(CLAVE_POR_ENCABEZADO[campo]))


def sumar_costos_reales_por_bucket(ws_detalle, tag: str) -> dict:
    sumas = {"Materiales": 0.0, "Equipos": 0.0, "Otros": 0.0}
    for fila in range(2, ws_detalle.max_row + 1):
        fila_tag = ws_detalle.cell(row=fila, column=1).value
        bucket = ws_detalle.cell(row=fila, column=3).value
        total = ws_detalle.cell(row=fila, column=4).value
        if fila_tag == tag and bucket in sumas and total is not None:
            sumas[bucket] += total
    return sumas


def leer_detalle_subcategorias(ws_detalle) -> dict[str, list[dict]]:
    filas_por_tag: dict[str, list[dict]] = {}
    for fila in range(2, ws_detalle.max_row + 1):
        tag = ws_detalle.cell(row=fila, column=1).value
        total = ws_detalle.cell(row=fila, column=4).value
        if not tag or total is None:
            continue
        filas_por_tag.setdefault(tag, []).append({
            "subcategoria": ws_detalle.cell(row=fila, column=2).value,
            "bucket": ws_detalle.cell(row=fila, column=3).value,
            "total": total,
        })

    resultado: dict[str, list[dict]] = {}
    for tag, filas in filas_por_tag.items():
        total_proyecto = sum(f["total"] for f in filas)
        resultado[tag] = [
            dict(f, pct=(f["total"] / total_proyecto) if total_proyecto else None)
            for f in filas
        ]
    return resultado


def calcular_peso_cartera(proyectos: list[dict]) -> dict[str, float]:
    total_venta = sum(p["monto_venta"] for p in proyectos if p["monto_venta"] is not None)
    return {
        p["tag"]: (p["monto_venta"] / total_venta if total_venta and p["monto_venta"] is not None else 0.0)
        for p in proyectos
    }


def _fecha_str(valor):
    if valor is None:
        return None
    if hasattr(valor, "strftime"):
        return valor.strftime("%d-%m-%Y")
    return str(valor)


def _kpis_por_categoria(p: dict, costos_reales: dict, total_real: float) -> dict:
    reales = {
        "materiales": costos_reales["Materiales"], "equipos": costos_reales["Equipos"],
        "mo": p["mo_real"], "otros": costos_reales["Otros"],
    }
    proyectados = {
        "materiales": p["materiales_proy"], "equipos": p["equipos_proy"],
        "mo": p["mo_proy"], "otros": p["otros_proy"],
    }
    venta = p["monto_venta"]

    costo_pct_venta = {k: (v / venta if venta else 0.0) for k, v in reales.items()}
    estructura_pct = {k: (v / total_real if total_real else 0.0) for k, v in reales.items()}
    desviacion_pct_categoria = {
        k: (reales[k] / proyectados[k] - 1) if proyectados[k] else 0.0 for k in reales
    }
    ahorro_sobrecosto = {k: proyectados[k] - reales[k] for k in reales}

    return {
        "costo_pct_venta": costo_pct_venta,
        "estructura_pct": estructura_pct,
        "desviacion_pct_categoria": desviacion_pct_categoria,
        "ahorro_sobrecosto": ahorro_sobrecosto,
    }


def _margen_por_dia(p: dict, margen_real: float):
    fecha_inicio, fecha_cierre = p["fecha_inicio"], p["fecha_cierre"]
    if fecha_inicio is None or fecha_cierre is None:
        return None
    dias = (fecha_cierre - fecha_inicio).days
    return margen_real / max(1, dias)


def calcular_kpis_proyecto(p: dict, costos_reales: dict) -> dict:
    total_proyectado = p["materiales_proy"] + p["equipos_proy"] + p["mo_proy"] + p["otros_proy"]
    total_real = costos_reales["Materiales"] + costos_reales["Equipos"] + costos_reales["Otros"] + p["mo_real"]
    margen_real = p["monto_venta"] - total_real
    desviacion_pct = (total_real / total_proyectado - 1) if total_proyectado else 0.0

    margen_neto = (margen_real / p["monto_venta"]) if p["monto_venta"] else 0.0
    nota = af.calcular_nota(margen_neto, desviacion_pct)
    evaluacion = af.clasificar_evaluacion(nota)

    resultado = {
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
        "ahorro_sobrecosto_total": total_proyectado - total_real,
        "margen_por_dia": _margen_por_dia(p, margen_real),
    }
    resultado.update(_kpis_por_categoria(p, costos_reales, total_real))
    return resultado


def percentil_inclusivo(valores: list[float], p: float) -> float:
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
            meses_activo = max(12.0, (max(fechas) - min(fechas)).days / 30)
        else:
            meses_activo = 12.0
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


def calcular_categorias(kpis_proyectos_completos: list[dict]) -> list[dict]:
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


def embeber_reportes_pdf(proyectos: list[dict], categorias: list[dict]) -> dict[str, str]:
    reportes: dict[str, str] = {}
    if not RAIZ_REPORTES.exists():
        return reportes

    for p in proyectos:
        ruta = RAIZ_REPORTES / "Proyectos" / f"{p['tag']}.pdf"
        if ruta.exists():
            reportes[f"proyecto:{p['tag']}"] = base64.b64encode(ruta.read_bytes()).decode("ascii")

    for c in categorias:
        ruta = RAIZ_REPORTES / "Categorías" / f"{c['categoria']}.pdf"
        if ruta.exists():
            reportes[f"categoria:{c['categoria']}"] = base64.b64encode(ruta.read_bytes()).decode("ascii")

    return reportes


def extraer_datos_saneados(ruta_excel=RUTA_EXCEL) -> dict:
    wb = openpyxl.load_workbook(str(ruta_excel), data_only=True)
    ws_proyectos = wb[af.HOJA_PROYECTOS]
    ws_detalle = wb[af.HOJA_DETALLE_COSTOS_REALES]

    proyectos = leer_proyectos(ws_proyectos)
    proyectos_por_tag = {p["tag"]: p for p in proyectos}
    peso_cartera_por_tag = calcular_peso_cartera(proyectos)
    detalle_subcategorias_por_tag = leer_detalle_subcategorias(ws_detalle)

    completos = []
    pendientes = []
    for p in proyectos:
        if es_proyecto_completo(p):
            costos_reales = sumar_costos_reales_por_bucket(ws_detalle, p["tag"])
            kpi = calcular_kpis_proyecto(p, costos_reales)
            kpi["peso_cartera_pct"] = peso_cartera_por_tag.get(p["tag"], 0.0)
            kpi["detalle_subcategorias"] = detalle_subcategorias_por_tag.get(p["tag"], [])
            completos.append(kpi)
        else:
            pendientes.append({
                "tag": p["tag"],
                "nombre": p["nombre"],
                "mensaje": f"{p['nombre']} — Falta ingresar información en 'Análisis de Proyectos'",
                "link": URL_PLANILLA_PENDIENTE,
            })

    clientes = calcular_clientes(completos, proyectos_por_tag)
    categorias = calcular_categorias(completos)
    reportes_pdf = embeber_reportes_pdf(completos, categorias)

    pendientes_por_cliente: dict[str, int] = {}
    for p in proyectos:
        if not es_proyecto_completo(p) and p["cliente"]:
            pendientes_por_cliente[p["cliente"]] = pendientes_por_cliente.get(p["cliente"], 0) + 1
    for c in clientes:
        c["proyectos_pendientes"] = pendientes_por_cliente.get(c["cliente"], 0)

    n_completos = len(completos)
    return {
        "generado": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "kpis_proyectos": {
            "n_completos": n_completos,
            "margen_real_total": sum(k["margen_real"] for k in completos),
            "monto_venta_total": sum(k["monto_venta"] for k in completos),
            "total_real_total": sum(k["total_real"] for k in completos),
            "nota_promedio": (sum(k["nota"] for k in completos) / n_completos) if n_completos else 0,
            "n_requiere_atencion": sum(1 for k in completos if k["evaluacion"] == "Requiere atención"),
        },
        "proyectos": completos,
        "clientes": clientes,
        "categorias": categorias,
        "pendientes": pendientes,
        "reportes_pdf": reportes_pdf,
    }


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

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -3.14 -m pytest "Peru/Análisis Financiero/Visualizador Web/tests/test_build_visualizador.py" -v`
Expected: PASS.

- [ ] **Step 5: Copy Chile's template.html as the starting point**

```bash
cp "Sistema Analisis Financiero/Visualizador Web/template.html" "Peru/Análisis Financiero/Visualizador Web/template.html"
```

- [ ] **Step 6: Apply the text substitutions**

| old_string | new_string |
|---|---|
| `<title>Análisis Financiero — Visualizador</title>` | `<title>Análisis Financiero Perú — Visualizador</title>` |
| `    <h2>Análisis Financiero — Visualizador</h2>` | `    <h2>Análisis Financiero Perú — Visualizador</h2>` |
| `        <h1>Análisis Financiero — Visualizador</h1>` | `        <h1>Análisis Financiero Perú — Visualizador</h1>` |
| `function formatoCLP(n) { return '$' + Math.round(n).toLocaleString('es-CL'); }` | `function formatoCLP(n) { return 'S/' + Math.round(n).toLocaleString('es-PE'); }` |

(The function keeps its `formatoCLP` name for this copy too — same reasoning as the other 2 Peru dashboards: it's an internal identifier, not user-facing, and renaming it would be a bigger diff against Chile's file for zero functional benefit.)

- [ ] **Step 7: Verify the placeholder survived and no stale CLP/es-CL text remains**

Run: `grep -c "__AF_DATA_B64__" "Peru/Análisis Financiero/Visualizador Web/template.html"`
Expected: `1` or more.

Run: `grep -n "es-CL'\|toLocaleString('es-CL')\|'\\$' +" "Peru/Análisis Financiero/Visualizador Web/template.html"`
Expected: no matches.

- [ ] **Step 8: Create the content doc**

Create `Peru/Análisis Financiero/Visualizador Web/CLAUDE.md`:

```markdown
# CLAUDE.md — Visualizador Web de Análisis Financiero Perú

Mismo contenido/decisiones que
[`../../../Sistema Analisis Financiero/Visualizador Web/CLAUDE.md`](../../../Sistema%20Analisis%20Financiero/Visualizador%20Web/CLAUDE.md)
(pestañas Proyectos/Clientes, recomputo en Python de KPIs, gate de
contraseña) — este archivo solo documenta lo que difiere para Perú.

## Qué difiere de la versión de Chile

- **Fuente de datos**: `Peru/Análisis Financiero/Análisis de Proyectos
  Perú.xlsx` (scaffolded por `analisis_financiero.ejecutar(pais="PE")`,
  nunca creado a mano) — nunca el Excel de Chile.
- **Moneda**: PEN (`S/`), `formatoCLP` (mismo nombre de función que Chile,
  por consistencia con el resto del código copiado) formatea con
  `toLocaleString('es-PE')`.
- **Sin link a planilla pendiente**: Chile linkea a un SharePoint real para
  "proyectos pendientes de completar"; Perú no tiene ese link todavía
  (`URL_PLANILLA_PENDIENTE = None` en `build_visualizador.py`) — sin efecto
  visible mientras haya 0 proyectos.
- **Comando de build**: `python driver.py visualizador --pais PE` (desde
  `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/`).
- **Publicación**: URL propia `analisis-financiero-peru`.

## Estado

0 proyectos al 2026-08-26 (Perú recién tiene su Excel scaffolding). El
dashboard se publica igual, vacío, listo para cuando se carguen proyectos
reales a mano en la planilla.
```

- [ ] **Step 9: Commit**

```bash
git add "Peru/Análisis Financiero/Visualizador Web/build_visualizador.py" "Peru/Análisis Financiero/Visualizador Web/template.html" "Peru/Análisis Financiero/Visualizador Web/CLAUDE.md" "Peru/Análisis Financiero/Visualizador Web/tests/test_build_visualizador.py"
git commit -m "feat(analisis-financiero-peru): agregar build_visualizador.py, template.html y tests"
```

---

### Task 6: Generate the build, verify it, add the hub card, publish

**Files:**
- Modify: `Visualizador Web/index.html` (Perú `.hub-grid` section — add a 3rd card), `Visualizador Web/CLAUDE.md` (hosting table + URL list)
- Modify (best-effort, re-check current content first per Global Constraints): the 6 `template.html` nav bars (5 existing + this one) — add "Análisis Financiero 🇵🇪" following whatever convention the concurrent session's edits already established (re-read each file immediately before editing; don't assume this plan's earlier description of their content is still accurate)
- (in the `gh-pages` worktree): `.worktrees/gh-pages/analisis-financiero-peru/index.html` (new), `.worktrees/gh-pages/index.html` (updated hub)

- [ ] **Step 1: Generate the build**

Run: `py -3.14 "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py" visualizador --pais PE`
Expected: exit 0, prints `OK — 0 proyecto(s) completo(s), 0 pendiente(s), 0 cliente(s)`.

- [ ] **Step 2: Visual verification with Playwright**

Serve `Peru/Análisis Financiero/Visualizador Web/build/` locally with correct UTF-8 charset (same custom-handler approach used for the other 2 Peru dashboards — plain `python -m http.server` mangles the accented characters). Navigate, enter the password `combustion`, snapshot. Confirm: KPI tiles show `S/ 0` (not `$0` or `NaN`), the Proyectos/Clientes tabs show their empty states cleanly, no visible "undefined".

- [ ] **Step 3: Re-check the 5 existing `template.html` files' current nav content, then add "Análisis Financiero 🇵🇪"**

Run `grep -n "viz-modnav-tab" <file>` on each of the 5 files immediately before editing (their content may have changed since this plan was written — see Global Constraints). Add a new tab entry following whatever pattern is currently there, then add the equivalent 5-entry nav (linking to all other 5 dashboards) to this dashboard's own `template.html`, marking itself `is-active`.

- [ ] **Step 4: Add the hub card**

In `Visualizador Web/index.html`, inside the `<h2 class="hub-section-title">🇵🇪 Perú</h2>` section, add (re-check current card order/content first, same caution as Step 3):

```html
      <article class="hub-card">
        <div class="icon" aria-hidden="true">📊</div>
        <h3>Análisis Financiero — Perú</h3>
        <p class="desc">Costos reales vs. ventas y proyecciones por proyecto en Perú, KPIs de rentabilidad y clientes (CLTV), en soles.</p>
        <a class="btn" href="https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero-peru/" target="_blank" rel="noopener">Abrir tablero →</a>
      </article>
```

- [ ] **Step 5: Update hosting docs**

In `Visualizador Web/CLAUDE.md`, add to the URL list and hosting table:

```
https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero-peru/
```

```
| Análisis Financiero Perú | `analisis-financiero-peru` | `Peru/Análisis Financiero/Visualizador Web/build/index.html` |
```

- [ ] **Step 6: Run the full repo test suite one more time**

Run: `py -3.14 -m pytest`
Expected: all tests PASS (previous count + this plan's new tests, no regressions).

- [ ] **Step 7: Commit the source changes** (narrow `git add` — only the files this task actually touched; re-check `git status` first in case the concurrent session has added its own unrelated changes since Task 5's commit)

```bash
git add "Visualizador Web/index.html" "Visualizador Web/CLAUDE.md" "Centro de Costos/Visualizador Web/template.html" "Peru/Centro de Costos/Visualizador Web/template.html" "Sistema Analisis Financiero/Visualizador Web/template.html" "Cotizador Historico/Visualizador Web/template.html" "Peru/Cotizador Historico/Visualizador Web/template.html" "Peru/Análisis Financiero/Visualizador Web/template.html"
git commit -m "feat(analisis-financiero-peru): agregar tarjeta al hub y al nav, documentar hosting"
```

- [ ] **Step 8: Publish — copy into the gh-pages worktree, review, commit, confirm with the user, push**

```bash
mkdir -p ".worktrees/gh-pages/analisis-financiero-peru"
cp "Peru/Análisis Financiero/Visualizador Web/build/index.html" ".worktrees/gh-pages/analisis-financiero-peru/index.html"
cp "Visualizador Web/index.html" ".worktrees/gh-pages/index.html"
git -C ".worktrees/gh-pages" status
git -C ".worktrees/gh-pages" diff --stat
```

Review the diff — expect exactly 1 new file + 1 modified file (the hub). If the concurrent session has also touched the gh-pages worktree since, reconcile before proceeding rather than overwriting blindly.

```bash
git -C ".worktrees/gh-pages" add "analisis-financiero-peru/index.html" "index.html"
git -C ".worktrees/gh-pages" commit -m "agregar tablero de Analisis Financiero Peru"
```

Confirm with the user before the final push (same standing caution as the other 2 Peru dashboards — this is a push to the public repo):

```bash
git -C ".worktrees/gh-pages" push
git push
```

(The second `push` publishes this task's `master` commit from Step 7.)

---

## Self-Review

**1. Spec coverage:**
- "parametrizar `analisis_financiero.py`, crear `Análisis de Proyectos Perú.xlsx`, skill `Registro_Analisis_Financiero` (+ `Actualizar_AF`) con `--pais`" → Tasks 1, 2, 4. `Actualizar_AF` (a thin publish-wrapper skill) is not modified by this plan — same scope decision as the Cotizador plan's `Actualizar_Cotizador` note: the manual `driver.py visualizador --pais PE` + Task 6's publish steps are sufficient for the immediate ask.
- "Depende de 1" (Centro de Costos país-core) → already done, consumed via `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx`.
- Perú starts with 0 projects → Task 4 verifies `ejecutar(pais="PE")` runs cleanly against an empty Centro de Costos Perú, Task 6 verifies the dashboard's empty state.
- No currency conversion → PEN-only formatting (Task 5), no CLP anywhere in the Peru copy.
- Hub + nav consistency → Task 6, with explicit re-check-before-edit guidance given the demonstrated concurrent-session risk.
- `auditor_centro_costos.py`'s PASO 12d Chile-only gate → Task 3, the one piece of this sub-project that lives outside `Sistema Analisis Financiero/`.

**2. Placeholder scan:** no "TBD"/"add error handling"/"similar to Task N" — Task 5's `build_visualizador.py` is reproduced in full (not by reference) specifically because a fresh implementer can't safely reconstruct 300+ lines of financial KPI math from a description; every other task's steps are exact code or exact commands.

**3. Type/name consistency:** `leer_detalle_centro_costos(ruta_excel_cc, pais="CL")`, `ejecutar(..., pais="CL")`, `actualizar_visualizador_af(pais="CL")`, `main(pais="CL")`, `PAISES` (Task 1) are the exact names Task 2's `driver.py`, Task 3's `auditor_centro_costos.py`, and Task 5's `build_visualizador.py` (`af.PAISES["PE"]["ruta_excel_af"]`) all reference. The JSON snapshot shape from `extraer_datos_saneados` (Task 5) is byte-identical to Chile's (no Peru-specific keys added or removed), matching the "reused JS, only currency formatter changes" design.
