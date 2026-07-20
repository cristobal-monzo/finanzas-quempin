# Visualizador CC — botón copiar archivo + notas "i" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a subtle copy-filename button next to each document row and four static "i" info notes to the Centro de Costos web visualizer, per the approved spec.

**Architecture:** Two-layer change — (1) `build_visualizador.py` starts exporting the `Archivo origen` column from `Master` as `archivo_origen` in the JSON snapshot (currently missing entirely), and (2) `template.html` gets pure client-side additions: a copy-to-clipboard icon button (with an `execCommand` fallback for sandboxed contexts) and a reusable `.info-badge` component that reuses the existing `.viz-tooltip` element with a new `info-mode` CSS modifier for wrapped text.

**Tech Stack:** Python 3 + openpyxl (backend export), vanilla JS/CSS/HTML (no framework, no build step) for `template.html`, pytest for backend tests, Playwright (Node) for browser verification.

**Spec:** `docs/superpowers/specs/2026-07-19-visualizador-cc-copy-archivo-y-notas-info-design.md`

## Global Constraints

- El botón de copiar debe copiar **solo el nombre de archivo** (sin ruta ni proyecto).
- Feedback de copiado: el ícono cambia a ✓ por ~1200ms y vuelve a su estado normal. Sin toast.
- Debe funcionar con fallback (`document.execCommand('copy')`) si `navigator.clipboard.writeText` falla o no existe (contexto sandboxeado de Claude Artifacts).
- Si un documento no tiene `archivo_origen`, no se renderiza el botón para esa fila.
- El clic en el botón de copiar debe hacer `stopPropagation()` — no debe expandir/colapsar la fila.
- Exactamente 4 notas "i", en estas ubicaciones y con este texto exacto (del spec, no parafrasear):
  1. KPI "Pendientes de revisión" → "Documentos con algún dato que no se pudo leer con certeza desde la foto original (ej. N° de documento). Se incluyen en los totales igual, marcados con ● en la tabla, hasta que alguien los revise."
  2. KPI "Gasto total (s/IVA)" → "Monto neto, sin el Impuesto al Valor Agregado. Es la base sobre la que se calcula el IVA de cada documento."
  3. Gráfico "Top proveedores" → "Los 8 proveedores con mayor gasto acumulado en el rango filtrado. El resto no se oculta: se resume en una nota aparte con el monto total fuera del top 8."
  4. Gráfico "Gasto mensual acumulado" → "La línea muestra el acumulado corrido mes a mes, no el gasto de cada mes por separado. Pasa el mouse sobre un punto para ver ambos valores."
- No se agrega ninguna nota "i" a otro KPI/gráfico/filtro.
- Notas "i": hover en desktop (dispositivos con `(hover: hover)`), tap para mostrar/ocultar en touch.
- No tocar `RAIZ_DOCS`, el renombrado de archivos, ni ningún otro campo del snapshot existente.

---

## File Structure

- **Modify:** `Centro de Costos/Visualizador Web/build_visualizador.py` — agrega `archivo_origen` al export, parametriza `extraer_datos_saneados()` para que sea testeable sin tocar el Excel real.
- **Create:** `Centro de Costos/Visualizador Web/tests/conftest.py` — agrega el directorio del módulo a `sys.path` (mismo patrón que `Sistema/tests/conftest.py`).
- **Create:** `Centro de Costos/Visualizador Web/tests/test_build_visualizador.py` — pytest para el campo nuevo.
- **Modify:** `Centro de Costos/Visualizador Web/template.html` — CSS + HTML + JS del botón de copiar y de las notas "i" (versionado, sin datos reales).

---

### Task 1: Exportar `archivo_origen` en `build_visualizador.py`

**Files:**
- Modify: `Centro de Costos/Visualizador Web/build_visualizador.py:46-92`
- Create: `Centro de Costos/Visualizador Web/tests/conftest.py`
- Create: `Centro de Costos/Visualizador Web/tests/test_build_visualizador.py`

**Interfaces:**
- Produces: `extraer_datos_saneados(ruta_excel=RUTA_EXCEL)` — cada dict en `output["documentos"]` gana la clave `"archivo_origen"` (string o `None`). Usado por Task 2/3 vía el snapshot embebido (`d.archivo_origen` en JS).

- [ ] **Step 1: Write the failing tests**

Create `Centro de Costos/Visualizador Web/tests/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

Create `Centro de Costos/Visualizador Web/tests/test_build_visualizador.py`:

```python
import openpyxl

import build_visualizador as bv

HEADERS_MASTER = [
    "N° Ref.", "Proyecto", "Tipo de Proyecto", "Fecha", "N° Documento",
    "Tipo Documento", "Proveedor", "Proveedor (Razón Social)", "Categoría",
    "Resumen Ítems", "Total sin IVA (CLP)", "IVA 19% (CLP)",
    "Total con IVA (CLP)", "Estado", "Archivo origen", "Fecha modificación",
]
HEADERS_DETALLE = [
    "N° Ref.", "Proyecto", "Tipo de Proyecto", "N° Documento", "Nombre Ítem",
    "Descripción", "Categoría Ítem", "Cantidad", "P. Unitario sin IVA",
    "Total sin IVA (CLP)", "Total con IVA (CLP)",
]


def _wb_con_un_documento(tmp_path, archivo_origen):
    wb = openpyxl.Workbook()
    ws_master = wb.active
    ws_master.title = "Master"
    for c, h in enumerate(HEADERS_MASTER, 1):
        ws_master.cell(row=1, column=c, value=h)
    fila = {
        "N° Ref.": "TEST-001", "Proyecto": "UMAG", "Tipo de Proyecto": "I+D+i",
        "Fecha": None, "N° Documento": "123", "Tipo Documento": "Factura",
        "Proveedor": "Proveedor", "Proveedor (Razón Social)": "Proveedor SpA",
        "Categoría": "Materiales", "Resumen Ítems": "Item",
        "Total sin IVA (CLP)": 1000, "IVA 19% (CLP)": 190,
        "Total con IVA (CLP)": 1190, "Estado": "Pagado",
        "Archivo origen": archivo_origen, "Fecha modificación": None,
    }
    for c, h in enumerate(HEADERS_MASTER, 1):
        ws_master.cell(row=2, column=c, value=fila[h])

    ws_detalle = wb.create_sheet("Detalle")
    for c, h in enumerate(HEADERS_DETALLE, 1):
        ws_detalle.cell(row=1, column=c, value=h)

    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(str(ruta))
    return ruta


def test_extraer_datos_saneados_incluye_archivo_origen(tmp_path):
    ruta = _wb_con_un_documento(tmp_path, "TEST-001_Proveedor_2026-07-01.jpg")
    data = bv.extraer_datos_saneados(ruta)
    assert data["documentos"][0]["archivo_origen"] == "TEST-001_Proveedor_2026-07-01.jpg"


def test_extraer_datos_saneados_archivo_origen_ausente_es_none(tmp_path):
    ruta = _wb_con_un_documento(tmp_path, None)
    data = bv.extraer_datos_saneados(ruta)
    assert data["documentos"][0]["archivo_origen"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `Centro de Costos/Visualizador Web/`):
```bash
python -m pytest tests/ -v
```
Expected: both tests **FAIL** with `KeyError: 'archivo_origen'` (the field doesn't exist yet).

- [ ] **Step 3: Parametrize `extraer_datos_saneados` and add the field**

In `Centro de Costos/Visualizador Web/build_visualizador.py`, change the function signature and the `load_workbook` call:

Old (line 46-51):
```python
def extraer_datos_saneados():
    """Lee Master + Detalle y arma el snapshot saneado (sin razón social
    en el nivel de tabla — esa sí se incluye porque el visualizador
    de Detalles la muestra al expandir cada fila, resuelto con el usuario
    2026-07-19: tag corto en la tabla, razón social completa en el detalle)."""
    wb = openpyxl.load_workbook(str(RUTA_EXCEL), data_only=True)
```

New:
```python
def extraer_datos_saneados(ruta_excel=RUTA_EXCEL):
    """Lee Master + Detalle y arma el snapshot saneado (sin razón social
    en el nivel de tabla — esa sí se incluye porque el visualizador
    de Detalles la muestra al expandir cada fila, resuelto con el usuario
    2026-07-19: tag corto en la tabla, razón social completa en el detalle).

    `ruta_excel` es parametrizable para poder testear contra un workbook
    temporal en vez del Excel real (que tiene datos financieros reales)."""
    wb = openpyxl.load_workbook(str(ruta_excel), data_only=True)
```

Then add the new field to the per-document dict (line 74-92):

Old:
```python
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
            "total_sin_iva": d.get("Total sin IVA (CLP)"),
            "iva": d.get("IVA 19% (CLP)"),
            "total_con_iva": d.get("Total con IVA (CLP)"),
            "estado": d.get("Estado"),
            "pendiente_revision": pendiente,
            "items": [],
        })
```

New:
```python
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
            "total_sin_iva": d.get("Total sin IVA (CLP)"),
            "iva": d.get("IVA 19% (CLP)"),
            "total_con_iva": d.get("Total con IVA (CLP)"),
            "estado": d.get("Estado"),
            "pendiente_revision": pendiente,
            "archivo_origen": d.get("Archivo origen"),
            "items": [],
        })
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `Centro de Costos/Visualizador Web/`):
```bash
python -m pytest tests/ -v
```
Expected: `2 passed`.

- [ ] **Step 5: Run the full module test suite to check for regressions**

Run (from `Centro de Costos/Sistema/`):
```bash
python -m pytest tests/ -q
```
Expected: `79 passed` (unchanged — this task doesn't touch `Sistema/`).

- [ ] **Step 6: Commit**

```bash
git add "Centro de Costos/Visualizador Web/build_visualizador.py" "Centro de Costos/Visualizador Web/tests/conftest.py" "Centro de Costos/Visualizador Web/tests/test_build_visualizador.py"
git commit -m "feat(visualizador-cc): exportar archivo_origen en el snapshot"
```

---

### Task 2: Botón de copiar nombre de archivo (`template.html`)

**Files:**
- Modify: `Centro de Costos/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `d.archivo_origen` (string|null) per document, from Task 1's export. `esc(s)` (existing helper, line ~588) for HTML-escaping.
- Produces: `copyArchivoBtnHtml(archivo)` and `copyArchivoOrigen(btn)` — used only within this task; not consumed elsewhere.

- [ ] **Step 1: Add CSS for `.copy-archivo-btn`**

In `template.html`, find this block (around line 204):
```
  .viz-kpi .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; display: inline-block; }

  /* Section headers */
```

Replace with:
```
  .viz-kpi .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; display: inline-block; }

  /* Botón de copiar nombre de archivo (junto a N° Ref. en la tabla) */
  .copy-archivo-btn {
    background: none;
    border: none;
    padding: 2px;
    margin-left: 4px;
    cursor: pointer;
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    vertical-align: middle;
  }
  .copy-archivo-btn:hover, .copy-archivo-btn:focus-visible { color: var(--brand-orange-ink, var(--brand-orange)); }
  .copy-archivo-btn .icon-check { display: none; }
  .copy-archivo-btn.copied .icon-copy { display: none; }
  .copy-archivo-btn.copied .icon-check { display: inline; color: var(--status-good); }

  /* Section headers */
```

- [ ] **Step 2: Add the JS helpers for rendering and copying**

Find this block (around line 588-592):
```
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
```

Replace with:
```
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // ---------- copiar nombre de archivo ----------
  var COPY_ICON_SVG = '<svg class="icon-copy" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
  var CHECK_ICON_SVG = '<svg class="icon-check" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>';
  function copyArchivoBtnHtml(archivo) {
    if (!archivo) return '';
    return ' <button type="button" class="copy-archivo-btn" data-archivo="' + esc(archivo) + '" title="Copiar nombre de archivo" aria-label="Copiar nombre de archivo">' + COPY_ICON_SVG + CHECK_ICON_SVG + '</button>';
  }
  function copyArchivoOrigen(btn) {
    var nombre = btn.dataset.archivo;
    function marcarCopiado() {
      btn.classList.add('copied');
      clearTimeout(btn._copyTimeout);
      btn._copyTimeout = setTimeout(function () { btn.classList.remove('copied'); }, 1200);
    }
    function fallbackCopy() {
      try {
        var ta = document.createElement('textarea');
        ta.value = nombre;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        var ok = document.execCommand('copy');
        document.body.removeChild(ta);
        if (ok) marcarCopiado();
      } catch (e) {}
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(nombre).then(marcarCopiado, fallbackCopy);
    } else {
      fallbackCopy();
    }
  }
```

- [ ] **Step 3: Render the button in the doc row and wire the click**

Find this line (around line 1004):
```
        '<td>' + esc(d.ref) + (d.pendiente_revision ? ' <span title="Pendiente de revisión" style="color:var(--status-warning)">●</span>' : '') + '</td>' +
```

Replace with:
```
        '<td>' + esc(d.ref) + (d.pendiente_revision ? ' <span title="Pendiente de revisión" style="color:var(--status-warning)">●</span>' : '') + copyArchivoBtnHtml(d.archivo_origen) + '</td>' +
```

Find this block (around line 1037-1053, the row-toggle wiring):
```
    tbody.querySelectorAll('tr.doc-row').forEach(function (tr) {
      // role="button" + tabindex + Enter/Espacio: la fila se expande con
      // click, pero hasta ahora no había forma de hacerlo solo con teclado.
      tr.setAttribute('role', 'button');
      tr.setAttribute('tabindex', '0');
      tr.setAttribute('aria-expanded', tr.classList.contains('is-expanded') ? 'true' : 'false');
      tr.setAttribute('aria-label', 'Ver detalle del documento ' + tr.dataset.ref);
      function toggle() {
        var ref = tr.dataset.ref;
        state.expanded[ref] = !state.expanded[ref];
        renderTable(getSorted(getFiltered()));
      }
      tr.addEventListener('click', toggle);
      tr.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
      });
    });

    renderPagination(allDocs.length, totalPages, paginationEl);
```

Replace with:
```
    tbody.querySelectorAll('tr.doc-row').forEach(function (tr) {
      // role="button" + tabindex + Enter/Espacio: la fila se expande con
      // click, pero hasta ahora no había forma de hacerlo solo con teclado.
      tr.setAttribute('role', 'button');
      tr.setAttribute('tabindex', '0');
      tr.setAttribute('aria-expanded', tr.classList.contains('is-expanded') ? 'true' : 'false');
      tr.setAttribute('aria-label', 'Ver detalle del documento ' + tr.dataset.ref);
      function toggle() {
        var ref = tr.dataset.ref;
        state.expanded[ref] = !state.expanded[ref];
        renderTable(getSorted(getFiltered()));
      }
      tr.addEventListener('click', toggle);
      tr.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
      });
    });
    tbody.querySelectorAll('.copy-archivo-btn').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        copyArchivoOrigen(btn);
      });
    });

    renderPagination(allDocs.length, totalPages, paginationEl);
```

- [ ] **Step 4: Manual smoke check in a browser**

Open `Centro de Costos/Visualizador Web/build/index.html` (stale build from before Task 1 is fine for this quick check — the button will just be invisible since `archivo_origen` isn't in that old snapshot yet) directly in a browser to confirm there are no JS console errors after this edit. Full functional verification happens in Task 4 after rebuilding.

Run:
```bash
python -c "import pathlib; print(pathlib.Path('Centro de Costos/Visualizador Web/template.html').read_text(encoding='utf-8').count('copyArchivoOrigen'))"
```
Expected: `2` (one definition, one call site) — a quick sanity check that both edits landed.

- [ ] **Step 5: Commit**

```bash
git add "Centro de Costos/Visualizador Web/template.html"
git commit -m "feat(visualizador-cc): boton de copiar nombre de archivo junto a N Ref"
```

---

### Task 3: Notas "i" explicativas (`template.html`)

**Files:**
- Modify: `Centro de Costos/Visualizador Web/template.html`

**Interfaces:**
- Consumes: `esc(s)` (existing helper), `tooltip` (existing `#vizTooltip` element reference, defined at top of `initApp`).
- Produces: `infoBadgeHtml(key)`, `bindInfoBadges(container)`, `showInfoTooltip(el, key)`, `INFO_NOTES` — used by KPI rendering (this task) and available for any future badge; no other task in this plan consumes them further.

- [ ] **Step 1: Add CSS for `.info-badge` and the tooltip's `info-mode`**

Find this line (around line 283):
```
  .viz-tooltip .tt-title { font-weight: 700; margin-bottom: 2px; }
```

Replace with:
```
  .viz-tooltip .tt-title { font-weight: 700; margin-bottom: 2px; }
  .viz-tooltip.info-mode { white-space: normal; max-width: 230px; line-height: 1.35; }
```

Find this block (the one Task 2 added, around line 210-217 after Task 2 runs):
```
  .copy-archivo-btn:hover, .copy-archivo-btn:focus-visible { color: var(--brand-orange-ink, var(--brand-orange)); }
  .copy-archivo-btn .icon-check { display: none; }
  .copy-archivo-btn.copied .icon-copy { display: none; }
  .copy-archivo-btn.copied .icon-check { display: inline; color: var(--status-good); }

  /* Section headers */
```

Replace with:
```
  .copy-archivo-btn:hover, .copy-archivo-btn:focus-visible { color: var(--brand-orange-ink, var(--brand-orange)); }
  .copy-archivo-btn .icon-check { display: none; }
  .copy-archivo-btn.copied .icon-copy { display: none; }
  .copy-archivo-btn.copied .icon-check { display: inline; color: var(--status-good); }

  /* Notas "i" explicativas junto a KPIs y títulos de gráficos */
  .info-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 1px solid var(--text-muted);
    color: var(--text-muted);
    font-size: 9.5px;
    font-weight: 700;
    font-style: italic;
    line-height: 1;
    margin-left: 5px;
    cursor: default;
    user-select: none;
    vertical-align: middle;
  }
  .info-badge:hover, .info-badge:focus-visible { border-color: var(--brand-orange-ink, var(--brand-orange)); color: var(--brand-orange-ink, var(--brand-orange)); outline: none; }

  /* Section headers */
```

- [ ] **Step 2: Add the info-note data and tooltip logic**

Find this block (around line 745, right after the existing tooltip helpers):
```
  function hideTooltip() { tooltip.classList.remove('show'); }
```

Replace with:
```
  function hideTooltip() {
    tooltip.classList.remove('show');
    tooltip.classList.remove('info-mode');
    tooltip.dataset.infoKey = '';
  }

  // ---------- notas "i" ----------
  var INFO_NOTES = {
    pendientes: { title: 'Pendientes de revisión', text: 'Documentos con algún dato que no se pudo leer con certeza desde la foto original (ej. N° de documento). Se incluyen en los totales igual, marcados con ● en la tabla, hasta que alguien los revise.' },
    gastoSinIva: { title: 'Gasto total (s/IVA)', text: 'Monto neto, sin el Impuesto al Valor Agregado. Es la base sobre la que se calcula el IVA de cada documento.' },
    topProveedores: { title: 'Top proveedores', text: 'Los 8 proveedores con mayor gasto acumulado en el rango filtrado. El resto no se oculta: se resume en una nota aparte con el monto total fuera del top 8.' },
    mensualAcumulado: { title: 'Gasto mensual acumulado', text: 'La línea muestra el acumulado corrido mes a mes, no el gasto de cada mes por separado. Pasa el mouse sobre un punto para ver ambos valores.' }
  };
  var HOVER_CAPABLE = window.matchMedia('(hover: hover)').matches;
  function infoBadgeHtml(key) {
    if (!key) return '';
    return ' <span class="info-badge" data-info="' + key + '" tabindex="0" role="button" aria-label="Más información">i</span>';
  }
  function positionTooltipNear(el) {
    var r = el.getBoundingClientRect();
    var vw = window.innerWidth;
    var x = r.left, y = r.bottom;
    tooltip.style.left = (x + 230 > vw ? Math.max(8, vw - 240) : x) + 'px';
    tooltip.style.top = (y + 8) + 'px';
  }
  function showInfoTooltip(el, key) {
    var note = INFO_NOTES[key];
    if (!note) return;
    tooltip.innerHTML = '<div class="tt-title">' + esc(note.title) + '</div><div>' + esc(note.text) + '</div>';
    tooltip.classList.add('show');
    tooltip.classList.add('info-mode');
    tooltip.dataset.infoKey = key;
    positionTooltipNear(el);
  }
  function bindInfoBadges(container) {
    container.querySelectorAll('.info-badge').forEach(function (b) {
      var key = b.dataset.info;
      if (!INFO_NOTES[key]) return;
      if (HOVER_CAPABLE) {
        b.addEventListener('mouseenter', function () { showInfoTooltip(b, key); });
        b.addEventListener('mouseleave', hideTooltip);
      } else {
        b.addEventListener('click', function (e) {
          e.stopPropagation();
          if (tooltip.dataset.infoKey === key && tooltip.classList.contains('show')) {
            hideTooltip();
          } else {
            showInfoTooltip(b, key);
          }
        });
      }
      b.addEventListener('focus', function () { showInfoTooltip(b, key); });
      b.addEventListener('blur', hideTooltip);
      b.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); showInfoTooltip(b, key); }
      });
    });
  }
  document.addEventListener('click', function (e) {
    if (tooltip.dataset.infoKey && (!e.target.closest || !e.target.closest('.info-badge'))) {
      hideTooltip();
    }
  });
```

- [ ] **Step 3: Add badges to the two static chart headers**

Find (around line 449):
```
        <h3>Gasto mensual acumulado</h3>
```

Replace with:
```
        <h3>Gasto mensual acumulado <span class="info-badge" data-info="mensualAcumulado" tabindex="0" role="button" aria-label="Más información">i</span></h3>
```

Find (around line 453):
```
        <h3>Top proveedores</h3>
```

Replace with:
```
        <h3>Top proveedores <span class="info-badge" data-info="topProveedores" tabindex="0" role="button" aria-label="Más información">i</span></h3>
```

- [ ] **Step 4: Add badges to the two KPI cards and bind them on every render**

Find this block (around line 748-768):
```
  function renderKPIs(docs) {
    var totalConIva = docs.reduce(function (s, d) { return s + (d.total_con_iva || 0); }, 0);
    var totalSinIva = docs.reduce(function (s, d) { return s + (d.total_sin_iva || 0); }, 0);
    var nPend = docs.filter(function (d) { return d.pendiente_revision; }).length;
    var nProy = new Set(docs.map(function (d) { return d.proyecto; })).size;
    var kpis = [
      { label: 'Gasto total (c/IVA)', value: fmt(totalConIva), sub: docs.length + ' documento' + (docs.length === 1 ? '' : 's'), accent: true },
      { label: 'Gasto total (s/IVA)', value: fmt(totalSinIva), sub: 'Neto' },
      { label: 'Proyectos', value: fmtNum(nProy), sub: 'con gasto en el rango filtrado' },
      { label: 'Documentos', value: fmtNum(docs.length), sub: 'Master · 1 fila por documento' },
      { label: 'Pendientes de revisión', value: fmtNum(nPend), sub: nPend > 0 ? 'requieren revisión manual' : 'todo validado', pill: nPend > 0 ? 'warn' : 'ok' }
    ];
    var row = document.getElementById('kpiRow');
    row.innerHTML = kpis.map(function (k) {
      return '<div class="viz-kpi' + (k.accent ? ' accent' : '') + '">' +
        '<div class="label">' + esc(k.label) + '</div>' +
        '<div class="value">' + k.value + '</div>' +
        (k.pill ? '<div class="pill ' + k.pill + '"><span class="dot"></span>' + esc(k.sub) + '</div>' : '<div class="sub">' + esc(k.sub) + '</div>') +
        '</div>';
    }).join('');
  }
```

Replace with:
```
  function renderKPIs(docs) {
    var totalConIva = docs.reduce(function (s, d) { return s + (d.total_con_iva || 0); }, 0);
    var totalSinIva = docs.reduce(function (s, d) { return s + (d.total_sin_iva || 0); }, 0);
    var nPend = docs.filter(function (d) { return d.pendiente_revision; }).length;
    var nProy = new Set(docs.map(function (d) { return d.proyecto; })).size;
    var kpis = [
      { label: 'Gasto total (c/IVA)', value: fmt(totalConIva), sub: docs.length + ' documento' + (docs.length === 1 ? '' : 's'), accent: true },
      { label: 'Gasto total (s/IVA)', value: fmt(totalSinIva), sub: 'Neto', info: 'gastoSinIva' },
      { label: 'Proyectos', value: fmtNum(nProy), sub: 'con gasto en el rango filtrado' },
      { label: 'Documentos', value: fmtNum(docs.length), sub: 'Master · 1 fila por documento' },
      { label: 'Pendientes de revisión', value: fmtNum(nPend), sub: nPend > 0 ? 'requieren revisión manual' : 'todo validado', pill: nPend > 0 ? 'warn' : 'ok', info: 'pendientes' }
    ];
    var row = document.getElementById('kpiRow');
    row.innerHTML = kpis.map(function (k) {
      return '<div class="viz-kpi' + (k.accent ? ' accent' : '') + '">' +
        '<div class="label">' + esc(k.label) + infoBadgeHtml(k.info) + '</div>' +
        '<div class="value">' + k.value + '</div>' +
        (k.pill ? '<div class="pill ' + k.pill + '"><span class="dot"></span>' + esc(k.sub) + '</div>' : '<div class="sub">' + esc(k.sub) + '</div>') +
        '</div>';
    }).join('');
    bindInfoBadges(row);
  }
```

- [ ] **Step 5: Bind the two static chart-header badges once at startup**

Find (near the end of `initApp`, right before the final render call):
```
  window.addEventListener('resize', debounce(render, 200));
  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }

  render();
```

Replace with:
```
  window.addEventListener('resize', debounce(render, 200));
  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }

  bindInfoBadges(document);
  render();
```

- [ ] **Step 6: Sanity check the edits landed**

Run:
```bash
python -c "import pathlib; t = pathlib.Path('Centro de Costos/Visualizador Web/template.html').read_text(encoding='utf-8'); print(t.count('info-badge'), t.count('INFO_NOTES'), t.count('bindInfoBadges'))"
```
Expected: `info-badge` count is `7` (1 in the `.info-badge {` CSS selector + 2 in the `.info-badge:hover, .info-badge:focus-visible` CSS rule + 2 static `<h3>` badges + 1 in the `infoBadgeHtml` template string + 1 in `bindInfoBadges`'s `querySelectorAll('.info-badge')`). `INFO_NOTES` count is `3` (definition + lookup in `showInfoTooltip` + lookup in `bindInfoBadges`). `bindInfoBadges` count is `3` (definition + call in `renderKPIs` + call at startup).

If any of the three counts is `0`, stop and re-check the corresponding step before continuing — full behavioral verification happens in Task 4.

- [ ] **Step 7: Commit**

```bash
git add "Centro de Costos/Visualizador Web/template.html"
git commit -m "feat(visualizador-cc): notas i explicativas en KPIs y graficos"
```

---

### Task 4: Rebuild y verificación en navegador real

**Files:**
- None modified — this task regenerates `Centro de Costos/Visualizador Web/build/index.html` (gitignored, not committed) and runs a throwaway verification script from the scratchpad directory.

**Interfaces:**
- Consumes: everything from Tasks 1-3.
- Produces: nothing consumed by later tasks — this is the final QA gate.

- [ ] **Step 1: Regenerate the build**

Run (from `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/`):
```bash
python driver.py visualizador
```
Expected: `OK — N documentos, ...` printed, and `Centro de Costos/Visualizador Web/build/index.html` gets a fresh timestamp.

- [ ] **Step 2: Write the verification script**

Create a scratch file (use the session's scratchpad directory, e.g.
`verify_visualizador.js`) with this content:

```javascript
const { chromium } = require('playwright');
const path = require('path');

const buildPath = process.argv[2];

(async () => {
  const browser = await chromium.launch();
  const results = {};

  for (const colorScheme of ['light', 'dark']) {
    const context = await browser.newContext({ colorScheme });
    const page = await context.newPage();
    await page.goto('file://' + path.resolve(buildPath));
    await page.fill('#pwInput', 'combustion');
    await page.click('#pwForm button[type=submit]');
    await page.waitForSelector('#kpiRow .viz-kpi');

    const copyBtn = page.locator('.copy-archivo-btn').first();
    await copyBtn.click();
    await page.waitForTimeout(200);
    results[colorScheme + '_copy_marked'] = await copyBtn.evaluate(function (el) { return el.classList.contains('copied'); });

    const infoBadge = page.locator('.info-badge').first();
    await infoBadge.hover();
    await page.waitForTimeout(150);
    results[colorScheme + '_info_shows_on_hover'] = (await page.locator('#vizTooltip.show').count()) > 0;
    results[colorScheme + '_info_text'] = await page.locator('#vizTooltip').innerText();
    await page.mouse.move(0, 0);
    await page.waitForTimeout(150);
    results[colorScheme + '_info_hides_after_hover'] = (await page.locator('#vizTooltip.show').count()) === 0;

    await page.screenshot({ path: 'screenshot-' + colorScheme + '.png', fullPage: true });
    await context.close();
  }

  const touchContext = await browser.newContext({ hasTouch: true, isMobile: true, viewport: { width: 390, height: 844 } });
  const touchPage = await touchContext.newPage();
  await touchPage.goto('file://' + path.resolve(buildPath));
  await touchPage.fill('#pwInput', 'combustion');
  await touchPage.click('#pwForm button[type=submit]');
  await touchPage.waitForSelector('#kpiRow .viz-kpi');
  const touchBadge = touchPage.locator('.info-badge').first();
  await touchBadge.tap();
  await touchPage.waitForTimeout(150);
  results.touch_info_shows_after_first_tap = (await touchPage.locator('#vizTooltip.show').count()) > 0;
  await touchBadge.tap();
  await touchPage.waitForTimeout(150);
  results.touch_info_hides_after_second_tap = (await touchPage.locator('#vizTooltip.show').count()) === 0;
  await touchContext.close();

  console.log(JSON.stringify(results, null, 2));
  await browser.close();
})();
```

- [ ] **Step 3: Install Playwright locally and run the script**

From the scratchpad directory (the one containing `verify_visualizador.js`):
```bash
npm init -y
npm install playwright
npx playwright install chromium
node verify_visualizador.js "<ruta absoluta a Centro de Costos/Visualizador Web/build/index.html>"
```

Expected JSON output: every `*_copy_marked`, `*_info_shows_on_hover`, `*_info_hides_after_hover`, `touch_info_shows_after_first_tap`, and `touch_info_hides_after_second_tap` key is `true`; `*_info_text` contains the "Gasto total (s/IVA)" or "Pendientes de revisión" title text (whichever badge `.info-badge` `.first()` resolved to — confirm it's non-empty and matches one of the four texts from Global Constraints).

If `npm install playwright` fails due to no network access, fall back to a manual check: open `build/index.html` in a real browser, log in with the password, click the copy icon (confirm it turns into a ✓ briefly), and hover/tap each of the 4 "i" badges (confirm the tooltip text matches Global Constraints) — in both light and dark mode (toggle via the "Modo oscuro"/"Modo claro" button in the header).

- [ ] **Step 4: Review the screenshots**

Look at `screenshot-light.png` and `screenshot-dark.png` (in the scratchpad dir). Confirm:
- The copy icon next to N° Ref. is visible and not visually broken in either theme.
- No `.info-badge` circle is invisible or has unreadable contrast against its background in either theme (this exact class of bug — a tooltip invisible in dark mode — happened before on this component per `Visualizador Web/CLAUDE.md`).

- [ ] **Step 5: Clean up the scratch script**

The `verify_visualizador.js` script, its `node_modules/`, and the screenshots live in the scratchpad directory — nothing here needs to be committed or cleaned from the repo itself. Confirm `git status` in the repo shows only the two `template.html`/`build_visualizador.py` commits from Tasks 1-3 plus the regenerated (gitignored) `Centro de Costos/Visualizador Web/build/index.html` and `data/centro-de-costos.json`, with no unexpected tracked changes:

```bash
git status
```

No commit needed for this task — it's verification-only.
