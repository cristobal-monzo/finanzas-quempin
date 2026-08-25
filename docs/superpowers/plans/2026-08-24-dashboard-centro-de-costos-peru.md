# Dashboard de Centro de Costos Perú Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a working Centro de Costos Perú web dashboard (own GitHub Pages URL, own hub card) so Perú's data — currently invisible — shows up the same way Chile's does, even while it has 0 documents.

**Architecture:** Duplicate the existing `Centro de Costos/Visualizador Web/build_visualizador.py` + `template.html` pair into `Peru/Centro de Costos/Visualizador Web/`, adapted for PEN/IGV headers and QUEMPIN SAC branding — mirrors how `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py:cmd_visualizador` already resolves a **per-country** `Visualizador Web/` folder (`acc.RAIZ_VISUALIZADOR_WEB`, `PAISES["PE"]["ruta_visualizador_web"] = RAIZ_PERU / "Visualizador Web"`) and imports whatever `build_visualizador.py` it finds there. No shared/parametrized script — same pattern as the 3 existing modules, which already have homonymous files loaded via `sys.path` tricks specifically to avoid cross-module coupling.

**Tech Stack:** Python 3.14 + openpyxl (export), static HTML/CSS/vanilla JS (dashboard), pytest (tests), Playwright (manual visual verification only, no new automated screenshot tests — matches existing precedent).

**Spec:** `docs/superpowers/specs/2026-08-21-peru-expansion-design.md` § C "Dashboards y hub" (this plan implements sub-project 4 of that spec, scoped to Centro de Costos only — Análisis Financiero Perú and Cotizador Histórico Perú dashboards are blocked: their own backends, sub-projects 2 and 3, haven't started, so there is no `Análisis de Proyectos Perú.xlsx` / Cotizador Perú data source to build a dashboard from yet).

## Global Constraints

- No currency conversion or combined CLP+PEN view anywhere — Perú's dashboard shows PEN only, exactly like Chile's shows CLP only (spec § "Fuera de alcance").
- Reuse the existing password-gate mechanism verbatim — no new/different password for Perú (spec § C, explicit decision).
- URL is structural and fixed once published: `https://cristobal-monzo.github.io/finanzas-quempin/centro-de-costos-peru/` (spec § C, "-peru" suffix pattern).
- Never edit `Centro de Costos/Visualizador Web/build_visualizador.py` or `template.html` (Chile's) — this plan only adds new files under `Peru/`.
- `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx` currently has 0 rows in `Master`/`Detalle` (confirmed via openpyxl inspection) — the dashboard must render a correct empty state, not crash or show "NaN"/"undefined".

---

## File Structure

```
Peru/Centro de Costos/Visualizador Web/
├── CLAUDE.md              # new — short, links to master + Chile's content doc
├── template.html          # new — copy of CL's, PEN/IGV + QUEMPIN SAC substitutions
├── build_visualizador.py  # new — copy of CL's, PEN/IGV header keys + Peru paths
├── tests/
│   └── test_build_visualizador.py   # new — copy of CL's test, PEN/IGV fixtures
├── data/                  # generated, gitignored (already covered by **/Visualizador Web/data/)
└── build/                 # generated, gitignored (already covered by **/Visualizador Web/build/)
```

Modified (existing files):
- `Visualizador Web/index.html` (root hub) — add 4th card.
- `Visualizador Web/CLAUDE.md` (root master doc) — add Perú row/URL to the hosting table.
- `.worktrees/gh-pages/` — new `centro-de-costos-peru/index.html`, updated `index.html` (hub).

---

### Task 1: `build_visualizador.py` for Perú + tests

**Files:**
- Create: `Peru/Centro de Costos/Visualizador Web/build_visualizador.py`
- Create: `Peru/Centro de Costos/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Produces: `extraer_datos_saneados(ruta_excel=RUTA_EXCEL) -> dict` (same shape as Chile's — keys `generado`, `ultima_actualizacion`, `kpis`, `documentos`), `build() -> int` (0 = success), both consumed by `driver.py:cmd_visualizador` via `import build_visualizador as bv; bv.build()`.

Chile's version (`Centro de Costos/Visualizador Web/build_visualizador.py`) reads Master/Detalle headers **by literal string** (`d.get("Total sin IVA (CLP)")`, `d.get("IVA 19% (CLP)")`, `d.get("Total con IVA (CLP)")`) — this is exactly why Perú's rows (headers `"Total sin IGV (PEN)"`, `"IGV 18% (PEN)"`, `"Total con IGV (PEN)"`, confirmed via direct openpyxl inspection of `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx`) never showed up: `Centro de Costos.xlsx` (Chile's own workbook) never even contains Perú rows in the first place — Perú has had its own separate workbook since the 2026-08-21 country split. This task does not touch Chile's file at all; it creates Perú's own copy that reads Perú's own headers.

- [ ] **Step 1: Write the failing test**

Create `Peru/Centro de Costos/Visualizador Web/tests/test_build_visualizador.py`:

```python
import importlib.util
import sys
from pathlib import Path

import openpyxl

# Mismo patron que los otros 3 modulos (ver Centro de Costos/Visualizador
# Web/tests/test_build_visualizador.py): "importlib" import-mode evita que
# pytest choque los 4 archivos de test por basename, pero el MODULO FUENTE
# igual hay que cargarlo por ruta bajo un nombre unico para que
# sys.modules no le entregue a este test el build_visualizador.py de otro
# pais/modulo.
_RUTA_BV = Path(__file__).resolve().parent.parent / "build_visualizador.py"
_spec = importlib.util.spec_from_file_location("build_visualizador_cc_pe", _RUTA_BV)
bv = importlib.util.module_from_spec(_spec)
sys.modules["build_visualizador_cc_pe"] = bv
_spec.loader.exec_module(bv)

HEADERS_MASTER = [
    "N° Ref.", "Proyecto", "Tipo de Proyecto", "Fecha", "N° Documento",
    "Tipo Documento", "Proveedor", "Proveedor (Razón Social)", "Categoría",
    "Resumen Ítems", "Total sin IGV (PEN)", "IGV 18% (PEN)",
    "Total con IGV (PEN)", "Estado", "Archivo origen", "Fecha modificación",
]
HEADERS_DETALLE = [
    "N° Ref.", "Proyecto", "Tipo de Proyecto", "N° Documento", "Nombre Ítem",
    "Descripción", "Categoría Ítem", "Cantidad", "P. Unitario sin IGV",
    "Total sin IGV (PEN)", "Total con IGV (PEN)",
]


def _wb_con_un_documento(tmp_path, archivo_origen):
    wb = openpyxl.Workbook()
    ws_master = wb.active
    ws_master.title = "Master"
    for c, h in enumerate(HEADERS_MASTER, 1):
        ws_master.cell(row=1, column=c, value=h)
    fila = {
        "N° Ref.": "TEST-001", "Proyecto": "Lima Proyecto", "Tipo de Proyecto": "I+D+i",
        "Fecha": None, "N° Documento": "123", "Tipo Documento": "Factura",
        "Proveedor": "Proveedor", "Proveedor (Razón Social)": "Proveedor SAC",
        "Categoría": "Materiales", "Resumen Ítems": "Item",
        "Total sin IGV (PEN)": 1000, "IGV 18% (PEN)": 180,
        "Total con IGV (PEN)": 1180, "Estado": "Pagado",
        "Archivo origen": archivo_origen, "Fecha modificación": None,
    }
    for c, h in enumerate(HEADERS_MASTER, 1):
        ws_master.cell(row=2, column=c, value=fila[h])

    ws_detalle = wb.create_sheet("Detalle")
    for c, h in enumerate(HEADERS_DETALLE, 1):
        ws_detalle.cell(row=1, column=c, value=h)

    ruta = tmp_path / "Centro de Costos Perú.xlsx"
    wb.save(str(ruta))
    return ruta


def test_extraer_datos_saneados_incluye_archivo_origen(tmp_path):
    ruta = _wb_con_un_documento(tmp_path, "TEST-001_Proveedor_2026-08-01.jpg")
    data = bv.extraer_datos_saneados(ruta)
    assert data["documentos"][0]["archivo_origen"] == "TEST-001_Proveedor_2026-08-01.jpg"


def test_extraer_datos_saneados_lee_columnas_igv_pen(tmp_path):
    ruta = _wb_con_un_documento(tmp_path, None)
    data = bv.extraer_datos_saneados(ruta)
    doc = data["documentos"][0]
    assert doc["total_sin_iva"] == 1000
    assert doc["iva"] == 180
    assert doc["total_con_iva"] == 1180


def test_extraer_datos_saneados_sin_documentos_no_falla(tmp_path):
    wb = openpyxl.Workbook()
    ws_master = wb.active
    ws_master.title = "Master"
    for c, h in enumerate(HEADERS_MASTER, 1):
        ws_master.cell(row=1, column=c, value=h)
    ws_detalle = wb.create_sheet("Detalle")
    for c, h in enumerate(HEADERS_DETALLE, 1):
        ws_detalle.cell(row=1, column=c, value=h)
    ruta = tmp_path / "Centro de Costos Perú.xlsx"
    wb.save(str(ruta))

    data = bv.extraer_datos_saneados(ruta)
    assert data["documentos"] == []
    assert data["kpis"]["n_documentos"] == 0
    assert data["kpis"]["total_con_iva"] == 0


def test_pendiente_coincide_con_el_color_real_de_auditor_centro_costos(tmp_path):
    """Misma verificacion cruzada que Centro de Costos/Visualizador Web/tests/
    test_build_visualizador.py -- la deteccion de "celda roja" es una
    reimplementacion independiente de _celda_es_roja (Sistema/
    auditor_centro_costos.py), y el color de "requiere revision" no cambia
    entre paises (configurar_pais() no lo toca), asi que el mismo caso de
    prueba aplica sin adaptar nada mas que la ruta de import."""
    raiz_sistema = Path(__file__).resolve().parents[4] / "Centro de Costos" / "Sistema"
    if str(raiz_sistema) not in sys.path:
        sys.path.insert(0, str(raiz_sistema))
    import auditor_centro_costos as acc

    col_n_documento = HEADERS_MASTER.index("N° Documento") + 1
    casos = (
        (acc.ROJO_FONT, True),
        (acc.AZUL_MARINO_FONT, False),
        (acc.NORMAL_FONT, False),
    )
    for font, debe_marcar in casos:
        ruta = _wb_con_un_documento(tmp_path, "TEST-001_Proveedor_2026-08-01.jpg")
        wb = openpyxl.load_workbook(str(ruta))
        wb["Master"].cell(row=2, column=col_n_documento).font = font
        wb.save(str(ruta))

        data = bv.extraer_datos_saneados(ruta)
        assert data["documentos"][0]["pendiente_revision"] is debe_marcar, (
            f"build_visualizador (Peru) discrepo para {font.color.rgb}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3.14 -m pytest "Peru/Centro de Costos/Visualizador Web/tests/test_build_visualizador.py" -v`
Expected: FAIL / ERROR — `build_visualizador.py` does not exist yet (collection error, `FileNotFoundError` or similar from `spec_from_file_location`).

- [ ] **Step 3: Write the implementation**

Create `Peru/Centro de Costos/Visualizador Web/build_visualizador.py` (copy of `Centro de Costos/Visualizador Web/build_visualizador.py` with paths and the 3 currency/tax-dependent header keys swapped from Chile's CLP/IVA to Perú's PEN/IGV — every other line, including the "Total sin IVA"/"Total con IVA" recompute-from-Detalle comment and logic, the red-cell detection, and the JSON/HTML output steps, is unchanged from Chile's):

```python
# -*- coding: utf-8 -*-
"""
build_visualizador.py — genera el visualizador web de Centro de Costos Perú.

Copia de Centro de Costos/Visualizador Web/build_visualizador.py adaptada a
Perú (IGV 18% / PEN en vez de IVA 19% / CLP) -- ver ese archivo para el
detalle de cada decision (por que se recalculan los totales desde Detalle
en vez de leer las formulas de Master, por que "pendiente_revision" usa
"endswith" sobre el sufijo de color). Perú no comparte el script con Chile
por el mismo motivo que Sistema/auditor_centro_costos.py no importa este
archivo directamente entre modulos: build_visualizador.py es homonimo en
los 3 modulos financieros y colisiona en sys.modules si se importa por
nombre en vez de por ruta -- ver driver.py:cmd_visualizador.

Salidas (ambas gitignoradas, se regeneran completas en cada corrida — nunca
edites nada dentro de `data/` o `build/` a mano):
  data/centro-de-costos-peru.json   — snapshot saneado intermedio (auditable)
  build/index.html                  — visualizador final con los datos incrustados

Uso:
  python build_visualizador.py
  (o, desde el driver de la skill: python driver.py visualizador --pais PE)
"""

import base64
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parent          # Peru/Centro de Costos/Visualizador Web/
RAIZ_MODULO = RAIZ.parent                        # Peru/Centro de Costos/
RUTA_EXCEL = RAIZ_MODULO / "Excel" / "Centro de Costos Perú.xlsx"
RUTA_TEMPLATE = RAIZ / "template.html"
RUTA_DATA_JSON = RAIZ / "data" / "centro-de-costos-peru.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"

REF_RE = re.compile(r"^[A-Z]+-\d+$")
# Debe coincidir con ROJO ("C00000") en Centro de Costos/Sistema/
# auditor_centro_costos.py -- ver esa constante para el detalle del bug
# real que este criterio "endswith" corrige (openpyxl no siempre antepone
# "FF" de alpha al releer un .xlsx guardado).
ROJO_SUFIJO = "C00000"


def extraer_datos_saneados(ruta_excel=RUTA_EXCEL):
    """Lee Master + Detalle y arma el snapshot saneado. Ver la version de
    Chile (Centro de Costos/Visualizador Web/build_visualizador.py) para el
    detalle de cada decision de saneado -- identica aca salvo las 3
    columnas cuyo nombre depende del pais (Total sin/con IGV, IGV 18%)."""
    wb = openpyxl.load_workbook(str(ruta_excel), data_only=True)
    ws_master = wb["Master"]
    ws_detalle = wb["Detalle"]

    headers_m = [c.value for c in ws_master[1]]
    docs = []
    for row in ws_master.iter_rows(min_row=2):
        ref_val = row[0].value
        if not isinstance(ref_val, str) or not REF_RE.match(ref_val):
            continue
        d = {headers_m[i]: row[i].value for i in range(len(headers_m))}

        pendiente = False
        for cell in row:
            color = cell.font.color.rgb if (cell.font and cell.font.color) else None
            if isinstance(color, str) and color.upper().endswith(ROJO_SUFIJO):
                pendiente = True
                break

        fecha = d.get("Fecha")
        fecha_iso = fecha.strftime("%Y-%m-%d") if isinstance(fecha, datetime) else None
        fecha_mod = d.get("Fecha modificación")

        docs.append({
            "ref": d.get("N° Ref."),
            "proyecto": d.get("Proyecto"),
            "tipo_proyecto": d.get("Tipo de Proyecto"),
            "fecha": fecha_iso,
            "fecha_modificacion": str(fecha_mod) if fecha_mod is not None else None,
            "n_documento": str(d.get("N° Documento")) if d.get("N° Documento") is not None else None,
            "tipo_documento": d.get("Tipo Documento"),
            "proveedor_tag": d.get("Proveedor"),
            "proveedor_razon_social": d.get("Proveedor (Razón Social)"),
            "categoria": d.get("Categoría"),
            "resumen_items": d.get("Resumen Ítems"),
            "total_sin_iva": d.get("Total sin IGV (PEN)"),
            "iva": d.get("IGV 18% (PEN)"),
            "total_con_iva": d.get("Total con IGV (PEN)"),
            "estado": d.get("Estado"),
            "pendiente_revision": pendiente,
            "archivo_origen": d.get("Archivo origen"),
            "items": [],
        })

    by_ref = {d["ref"]: d for d in docs}
    headers_d = [c.value for c in ws_detalle[1]]
    for row in ws_detalle.iter_rows(min_row=2, values_only=True):
        if not isinstance(row[0], str) or not REF_RE.match(row[0]):
            continue
        rd = {headers_d[i]: row[i] for i in range(len(headers_d))}
        doc = by_ref.get(rd.get("N° Ref."))
        if doc is not None:
            doc["items"].append({
                "nombre_item": rd.get("Nombre Ítem"),
                "descripcion": rd.get("Descripción"),
                "categoria_item": rd.get("Categoría Ítem"),
                "cantidad": rd.get("Cantidad"),
                "p_unitario_sin_iva": rd.get("P. Unitario sin IGV"),
                "total_sin_iva": rd.get("Total sin IGV (PEN)"),
                "total_con_iva": rd.get("Total con IGV (PEN)"),
            })

    # Master!"Total sin/con IGV (PEN)" son formulas de Excel (SUMIF / K+L) --
    # openpyxl nunca las calcula. Se recalculan sumando los items de Detalle
    # (valores Python, siempre confiables) -- mismo fix que Chile, ver ese
    # build_visualizador.py para el bug real que esto corrige.
    for d in docs:
        if d["items"]:
            d["total_sin_iva"] = sum(it["total_sin_iva"] or 0 for it in d["items"])
            d["total_con_iva"] = sum(it["total_con_iva"] or 0 for it in d["items"])
        else:
            d["total_sin_iva"] = d["total_sin_iva"] or 0
            d["total_con_iva"] = d["total_con_iva"] or 0

    fechas_mod = [d["fecha_modificacion"] for d in docs if d["fecha_modificacion"]]
    output = {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ultima_actualizacion": max(fechas_mod) if fechas_mod else None,
        "kpis": {
            "total_sin_iva": sum(d["total_sin_iva"] or 0 for d in docs),
            "total_iva": sum(d["iva"] or 0 for d in docs),
            "total_con_iva": sum(d["total_con_iva"] or 0 for d in docs),
            "n_documentos": len(docs),
            "n_pendientes": sum(1 for d in docs if d["pendiente_revision"]),
        },
        "documentos": docs,
    }
    return output


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

    data = extraer_datos_saneados()

    RUTA_DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    with io.open(RUTA_DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    data_json_text = json.dumps(data, ensure_ascii=False)
    data_b64 = base64.b64encode(data_json_text.encode("utf-8")).decode("ascii")

    with io.open(RUTA_TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read()
    if "__CC_DATA_B64__" not in template:
        print("[ERROR] template.html no tiene el placeholder __CC_DATA_B64__")
        return 1
    html = template.replace("__CC_DATA_B64__", data_b64)

    RUTA_BUILD_HTML.parent.mkdir(parents=True, exist_ok=True)
    with io.open(RUTA_BUILD_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK — {len(data['documentos'])} documentos, "
          f"{sum(len(d['items']) for d in data['documentos'])} items, "
          f"gasto total c/IGV S/{data['kpis']['total_con_iva']:,}".replace(",", "."))
    print(f"Última actualización de los datos: {data['ultima_actualizacion']}")
    print(f"Snapshot: {RUTA_DATA_JSON}")
    print(f"Visualizador: {RUTA_BUILD_HTML}")
    print("Para verlo: copialo a .worktrees/gh-pages/centro-de-costos-peru/index.html y "
          "haz git push, o abrelo directo en el navegador.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(build())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3.14 -m pytest "Peru/Centro de Costos/Visualizador Web/tests/test_build_visualizador.py" -v`
Expected: 5 tests PASS.

- [ ] **Step 5: Run the full repo suite to confirm no collisions with the other 3 `build_visualizador.py`/test files**

Run: `py -3.14 -m pytest`
Expected: all suites pass, count goes up by 5 (the tests just added), no `sys.modules` collisions reported.

- [ ] **Step 6: Commit**

```bash
git add "Peru/Centro de Costos/Visualizador Web/build_visualizador.py" "Peru/Centro de Costos/Visualizador Web/tests/test_build_visualizador.py"
git commit -m "feat(centro-de-costos-peru): agregar build_visualizador.py y tests"
```

---

### Task 2: `template.html` + `CLAUDE.md` for Perú

**Files:**
- Create: `Peru/Centro de Costos/Visualizador Web/template.html`
- Create: `Peru/Centro de Costos/Visualizador Web/CLAUDE.md`

**Interfaces:**
- Consumes: nothing from Task 1 directly (Task 3 is what wires them together via `build()`).
- Produces: a `template.html` containing the literal placeholder `__CC_DATA_B64__` (required by `build()` from Task 1, Step 3 — `if "__CC_DATA_B64__" not in template: return 1`).

Chile's `template.html` (`Centro de Costos/Visualizador Web/template.html`) has exactly 3 occurrences of Chile-specific text that need swapping for Perú, all confirmed by grep against the real file — no other country-specific strings exist in it (no "Chile", no "QUEMPIN SpA" literal, no other currency mentions):

| Line (Chile's file) | Current | New (Perú's file) |
|---|---|---|
| 1 | `<title>Centro de Costos — Visualizador</title>` | `<title>Centro de Costos Perú — Visualizador</title>` |
| 483 | `<h2>Centro de Costos — Visualizador</h2>` | `<h2>Centro de Costos Perú — Visualizador</h2>` |
| 499 | `<h1>Centro de Costos — Visualizador</h1>` | `<h1>Centro de Costos Perú — Visualizador</h1>` |
| 597 | `datos reales de <strong>Centro de Costos.xlsx</strong>` | `datos reales de <strong>Centro de Costos Perú.xlsx</strong>` |
| 725 | `new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 })` | `new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN', maximumFractionDigits: 0 })` |
| 727 | `new Intl.NumberFormat('es-CL').format(n)` | `new Intl.NumberFormat('es-PE').format(n)` |

(Line 1060's `es-CL` is a comment describing percentage formatting, unrelated to currency — leave as-is, `Intl.NumberFormat('es-CL')` and `'es-PE')` format percentages identically since neither locale changes decimal-comma conventions relevant here; not worth a second parallel edit.)

- [ ] **Step 1: Copy Chile's template.html as the starting point**

```bash
cp "Centro de Costos/Visualizador Web/template.html" "Peru/Centro de Costos/Visualizador Web/template.html"
```

- [ ] **Step 2: Apply the 6 substitutions from the table above**

Use the Edit tool on `Peru/Centro de Costos/Visualizador Web/template.html` with the 6 `old_string`/`new_string` pairs from the table (each `old_string` above is unique in the file — verified by grep in Task 1's investigation, 1 match each except the currency/locale lines which are each unique method calls).

- [ ] **Step 3: Verify the placeholder survived the copy**

Run: `grep -c "__CC_DATA_B64__" "Peru/Centro de Costos/Visualizador Web/template.html"`
Expected: `1`

- [ ] **Step 4: Verify no Chile-specific strings remain**

Run: `grep -n "CLP\|es-CL'\|Centro de Costos.xlsx\b" "Peru/Centro de Costos/Visualizador Web/template.html"`
Expected: no matches (the `es-CL` comment at the old line ~1060 is fine to keep per the note above, but re-check its exact wording doesn't also say "CLP" — if it does, leave the comment or reword it to "PEN", whichever reads correctly in context, since it's a comment with zero functional impact).

- [ ] **Step 5: Create the content doc for this dashboard**

Create `Peru/Centro de Costos/Visualizador Web/CLAUDE.md`:

```markdown
# CLAUDE.md — Visualizador Web de Centro de Costos Perú

Mismo contenido/decisiones de saneado que
[`../../../Centro de Costos/Visualizador Web/CLAUDE.md`](../../../Centro%20de%20Costos/Visualizador%20Web/CLAUDE.md)
(estructura de `template.html`/`build_visualizador.py`, gate de contraseña,
datos incrustados en base64, KPIs, tabla dinámica, gráficos, filtros) — este
archivo solo documenta lo que difiere para Perú. Ver también
[`../../../Visualizador Web/CLAUDE.md`](../../../Visualizador%20Web/CLAUDE.md)
(doc maestro: marca, hosting, mandato de herramientas dinámicas).

## Qué difiere de la versión de Chile

- **Fuente de datos**: `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx`
  (nunca `Centro de Costos/Excel/Centro de Costos.xlsx` — son libros
  completamente separados desde el split por país del 2026-08-21, ver
  `Centro de Costos/CLAUDE.md` § "Split por país").
- **Moneda**: PEN (`S/`), impuesto IGV 18% (no IVA 19% / CLP) — columnas
  `Total sin IGV (PEN)`, `IGV 18% (PEN)`, `Total con IGV (PEN)` en vez de
  las de Chile. `template.html` formatea con `Intl.NumberFormat('es-PE',
  {currency:'PEN'})`.
- **Razón social del proveedor**: sigue mostrando el tag corto en la tabla
  y la razón social completa al expandir, igual que Chile — solo cambia que
  los documentos de Perú se emiten a nombre de "QUEMPIN SAC", no "QUEMPIN
  SpA" (dato que ya vive en `Sistema/auditor_centro_costos.py`
  `PAISES["PE"]["razon_social"]`, no en este visualizador).
- **Gate de contraseña**: reutiliza el mismo mecanismo/contraseña que
  Chile — decisión explícita del spec de expansión a Perú (no una barrera
  nueva).
- **Comando de build**: `python driver.py visualizador --pais PE` (desde
  `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/`) en vez de
  sin `--pais` (default `CL`) — el driver ya resolvía esta ruta antes de
  que este archivo existiera (`cmd_visualizador` imprimía "[INFO]
  Visualizador Web de PE aún no implementado" hasta esta implementación).
- **Publicación**: URL propia `centro-de-costos-peru` (no
  `centro-de-costos`) — ver `../../../Visualizador Web/CLAUDE.md` § Hosting
  para la tabla completa con las 4 subrutas.

## Estado

0 documentos al 2026-08-24 (Perú recién tiene su Excel scaffolding, sin
facturas/boletas registradas todavía — ver `Peru/Centro de Costos/
datos_extraidos_peru.json`, vacío). El dashboard se publica igual, vacío,
para que quede listo apenas empiecen a fluir documentos reales — evita
tener que repetir este trabajo de implementación más adelante.
```

- [ ] **Step 6: Commit**

```bash
git add "Peru/Centro de Costos/Visualizador Web/template.html" "Peru/Centro de Costos/Visualizador Web/CLAUDE.md"
git commit -m "feat(centro-de-costos-peru): agregar template.html y CLAUDE.md"
```

---

### Task 3: Generate the build and verify it renders correctly with 0 documents

**Files:**
- No new files — this task runs Task 1 + Task 2's code and inspects the output.

**Interfaces:**
- Consumes: `Peru/Centro de Costos/Visualizador Web/build_visualizador.py:build()` (Task 1), `template.html` (Task 2), both via `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py:cmd_visualizador(pais="PE")`.
- Produces: `Peru/Centro de Costos/Visualizador Web/build/index.html` (consumed by Task 4/5's publish step).

- [ ] **Step 1: Run the driver's visualizador command for Perú**

Run: `py -3.14 "Centro de Costos/.claude/skills/Registro_Centro_de_Costos/driver.py" visualizador --pais PE`
Expected: exit 0, prints `OK — 0 documentos, 0 items, gasto total c/IGV S/0` and the paths to `data/centro-de-costos-peru.json` and `build/index.html`.

- [ ] **Step 2: Confirm the build artifact exists**

Run: `ls "Peru/Centro de Costos/Visualizador Web/build/index.html"`
Expected: file exists.

- [ ] **Step 3: Visual verification with Playwright — open, unlock, confirm empty state renders cleanly**

This mirrors the precedent already set for Chile's dashboard (`Centro de Costos/Visualizador Web/CLAUDE.md` § "Ciclo de mejora continua": "el review de código solo no detectó ninguno de los dos bugs" — visual bugs need a real browser, not just code review). Use the `mcp__playwright__browser_navigate` / `browser_snapshot` / `browser_type` / `browser_click` tools (already available in this session) to:
1. Navigate to the local `build/index.html` (as a `file://` URL).
2. Enter the password used by the existing Chile dashboard (same gate, reused per spec) and submit.
3. Take a snapshot/screenshot of the resulting empty-state dashboard.
4. Confirm: no visible "NaN", no visible "undefined", the KPI tiles show `S/0` (not `$0` — this is the concrete regression this task exists to catch, since a leftover CLP formatter would silently produce `$0` instead of failing loudly), and the table/charts show an empty state instead of an error.

If any of those checks fail, fix the specific line in `template.html` or `build_visualizador.py` and re-run Step 1.

- [ ] **Step 4: No commit** — this task only generates gitignored build output (`data/`, `build/`) and does a manual check; nothing to commit.

---

### Task 4: Add the hub card and update the hosting docs

**Files:**
- Modify: `Visualizador Web/index.html:217-222` (root hub — insert a new `<article class="hub-card">` after Centro de Costos', before Análisis Financiero's, matching spec § C's "3 Chile arriba, Perú abajo" ordering as closely as a 4-card grid allows — placed right after the existing Centro de Costos card keeps the two Centro de Costos cards adjacent, which reads clearer than splitting them apart)
- Modify: `Visualizador Web/CLAUDE.md` (hosting table + URL list)

**Interfaces:**
- Consumes: nothing new (static hand-edited HTML, no build step — per `Visualizador Web/CLAUDE.md`: "No hay `build_visualizador.py` para este archivo... se edita a mano").

- [ ] **Step 1: Insert the new hub card**

In `Visualizador Web/index.html`, after the existing Centro de Costos `</article>` (line 208) and before the Análisis Financiero `<article>` (line 210), insert:

```html
      <article class="hub-card">
        <div class="icon" aria-hidden="true">🏗️ 🇵🇪</div>
        <h3>Centro de Costos — Perú</h3>
        <p class="desc">Gasto real registrado por proyecto, categoría y proveedor a partir de facturas y boletas de Perú (S/, IGV 18%).</p>
        <a class="btn" href="https://cristobal-monzo.github.io/finanzas-quempin/centro-de-costos-peru/" target="_blank" rel="noopener">Abrir tablero →</a>
      </article>
```

- [ ] **Step 2: Add the new row to the hosting table in the master doc**

In `Visualizador Web/CLAUDE.md`, in the "Hosting" section, add a row to the existing table (currently 3 rows: Centro de Costos, Análisis Financiero, Cotizador Histórico) and a 4th URL line to the URL block above it:

```
https://cristobal-monzo.github.io/finanzas-quempin/centro-de-costos-peru/
```

```
| Centro de Costos Perú | `centro-de-costos-peru` | `Peru/Centro de Costos/Visualizador Web/build/index.html` |
```

- [ ] **Step 3: Open the hub locally and confirm 4 cards render, in both themes**

Use `mcp__playwright__browser_navigate` to open `Visualizador Web/index.html` as a `file://` URL, `browser_snapshot` to confirm 4 `article.hub-card` elements are present with the expected titles/links, then `browser_click` the theme toggle and snapshot again to confirm the new card also respects dark mode (it uses the same `.hub-card`/`.icon` CSS classes as the other 3, so this is a sanity check, not expected to fail).

- [ ] **Step 4: Commit**

```bash
git add "Visualizador Web/index.html" "Visualizador Web/CLAUDE.md"
git commit -m "feat(centro-de-costos-peru): agregar tarjeta al hub y documentar hosting"
```

---

### Task 5: Publish to GitHub Pages

**Files:**
- Modify (in the `gh-pages` worktree, not `master`): `.worktrees/gh-pages/centro-de-costos-peru/index.html` (new), `.worktrees/gh-pages/index.html` (updated hub)

**Interfaces:**
- Consumes: `Peru/Centro de Costos/Visualizador Web/build/index.html` (Task 3), `Visualizador Web/index.html` (Task 4) — copied verbatim, no transformation.

This is a push to the **public** `cristobal-monzo/finanzas-quempin` repo, immediately visible at a live URL — confirm with the user before the final push, per this session's standing policy on actions visible to others. Everything through Step 3 (copying files into the worktree, staging) is local/reversible and safe to do without stopping.

- [ ] **Step 1: Copy both files into the gh-pages worktree**

```bash
mkdir -p ".worktrees/gh-pages/centro-de-costos-peru"
cp "Peru/Centro de Costos/Visualizador Web/build/index.html" ".worktrees/gh-pages/centro-de-costos-peru/index.html"
cp "Visualizador Web/index.html" ".worktrees/gh-pages/index.html"
```

- [ ] **Step 2: Review what's about to be published**

```bash
git -C ".worktrees/gh-pages" status
git -C ".worktrees/gh-pages" diff --stat
```

Expected: 1 new file (`centro-de-costos-peru/index.html`) + 1 modified file (`index.html`, the hub) — nothing else.

- [ ] **Step 3: Stage and commit in the worktree**

```bash
git -C ".worktrees/gh-pages" add "centro-de-costos-peru/index.html" "index.html"
git -C ".worktrees/gh-pages" commit -m "agregar tablero de Centro de Costos Peru"
```

- [ ] **Step 4: Confirm with the user, then push**

Ask the user to confirm before running:

```bash
git -C ".worktrees/gh-pages" push
```

Expected: push succeeds; `https://cristobal-monzo.github.io/finanzas-quempin/centro-de-costos-peru/` and the updated hub go live within a minute or two (GitHub Pages build delay).

---

## Self-Review

**1. Spec coverage** (spec § C "Dashboards y hub", scoped to Centro de Costos only per this plan's stated scope):
- "Los 3 `build_visualizador.py` existentes ganan el mismo parámetro de país" → implemented as a **separate file per country** (Task 1) instead of a shared parametrized script — this follows the pattern `driver.py:cmd_visualizador` already committed to (per-country `RAIZ_VISUALIZADOR_WEB` folder, own `build_visualizador.py` inside it), documented as a deliberate architecture choice in this plan's "Architecture" section, not a spec deviation in substance (same currency/símbolo/datos-per-país outcome the spec asks for).
- "URLs de GitHub Pages para Perú... `/centro-de-costos-peru/`" → Task 5.
- "El hub... pasa de 3 a 6 tarjetas... con la bandera 🇵🇪" → Task 4 (1 of the eventual 3 Perú cards; the other 2 are blocked, called out explicitly in this plan's header and Task 4 won't claim otherwise).
- "Gate de contraseña: se reutiliza el mismo mecanismo" → Task 2 copies the gate as-is, no changes.
- Análisis Financiero Perú / Cotizador Histórico Perú dashboards → explicitly out of scope (spec's own dependency note: "Depende de 1–3", and sub-projects 2/3 haven't started).

**2. Placeholder scan:** no "TBD"/"handle edge cases"/"similar to Task N" — every step has literal file content or an exact command. The one spot that could look like a placeholder (Task 2's substitution table instead of a full file reproduction) is a complete, unambiguous specification (6 exact old→new string pairs against a file created by a literal `cp` in the preceding step), not a vague instruction.

**3. Type/name consistency:** `extraer_datos_saneados(ruta_excel=RUTA_EXCEL) -> dict` and `build() -> int` (Task 1) match what Task 3 calls via `driver.py`. The JSON snapshot's key names (`total_sin_iva`, `iva`, `total_con_iva`, etc.) are unchanged from Chile's — intentional, since `template.html`'s JS reads the same key names regardless of country (only the `Intl.NumberFormat` currency changes, not the JSON shape) — verified by grep showing no other `CLP`/currency-key references in Chile's `template.html` JS beyond the 2 `Intl.NumberFormat` calls already covered in Task 2.
