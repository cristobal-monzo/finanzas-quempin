# Nota de Proyecto, CLTV de Clientes y Glosario KPIs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `Análisis de Proyectos.xlsx` with a 0–100 project score ("Nota
del Proyecto"), a client-recurrence/CLTV evaluation ("Cliente" column + new
"Clientes" sheet), and a "Glosario KPIs" sheet documenting every KPI in the
workbook — implementing
[`docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md`](../specs/2026-07-21-analisis-financiero-nota-clientes-design.md).

**Architecture:** All new logic lives in the existing single module
`Sistema Analisis Financiero/Sistema/analisis_financiero.py` (same pattern as
the rest of the module — one code file, one test file per concern under
`Sistema/tests/`). Two new sheets ("Clientes", "Glosario KPIs") and two new
columns ("Cliente" in "Proyectos", "Nota del Proyecto"/"Evaluación" in
"Indicadores") are added by **appending** to existing header lists/style
dicts, never inserting in the middle, so no existing column letter mapping
shifts. Client derivation/fuzzy-matching writes a `clientes_pendientes.json`
file (same pattern as Centro de Costos'
`correcciones_manuales.json`/`confirmar_correcciones`) for a two-step,
non-blocking confirmation flow, since this module runs unattended chained to
Centro de Costos' `run` and can never block on interactive input.

**Tech Stack:** Python 3.14, openpyxl, pytest. No new dependencies — client
fuzzy-matching uses only the stdlib (`difflib.SequenceMatcher`,
`unicodedata`, `json`).

## Global Constraints

- Never write `Centro de Costos.xlsx` — this module only reads it (existing
  rule, unaffected by this plan).
- Manual columns in "Proyectos" (A–J, N, and the new "Cliente" once assigned)
  are never overwritten between runs — only derived/formula columns and the
  fully-regenerated sheets ("Detalle Costos Reales", "Indicadores",
  "Clientes", "Glosario KPIs") are rewritten each run.
- All KPI values are Excel formulas (`=...`), never Python-computed literals
  — they must recalculate live in Excel when inputs change.
- Every write to `Análisis de Proyectos.xlsx` is preceded by a timestamped
  backup to `Respaldos/<Mes Año>/` (existing `hacer_backup`, reused as-is).
- `ejecutar(dry_run=True)` must never write any file to disk — not the
  Excel, not `clientes_pendientes.json`, nothing.
- Nota del Proyecto: margen objetivo = 25%, peso rentabilidad = 70%, peso
  desviación = 30% (spec §1) — kept as named constants, not inlined numbers.
- Fuzzy-match threshold for "Cliente" = 0.6 similarity (spec §2, validated
  against real string pairs during brainstorming — see Task 2).
- Client classification tiers: top 33% CLTV → "Clientes estratégicos", middle
  33% → "Clientes potenciales", bottom 33% → "Clientes de oportunidad" (spec
  §3), computed via Excel `PERCENTILE`, never a fixed CLP cutoff.

---

### Task 1: Esqueleto de esquema — columna "Cliente" y hojas "Clientes"/"Glosario KPIs"

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py:40-58` (headers), `:169-200` (`asegurar_estructura_workbook`)
- Test: Modify `Sistema Analisis Financiero/Sistema/tests/test_estructura_workbook.py`

**Interfaces:**
- Produces: `HOJA_CLIENTES = "Clientes"`, `HOJA_GLOSARIO_KPIS = "Glosario KPIs"`, `HEADERS_CLIENTES: list[str]`, `HEADERS_GLOSARIO_KPIS: list[str]`; `HEADERS_PROYECTOS` gains a 20th entry `"Cliente"`; `HEADERS_INDICADORES` gains a 17th/18th entry `"Nota del Proyecto"`/`"Evaluación"`. All later tasks read these constants.

- [x] **Step 1: Write the failing tests**

Append to `Sistema Analisis Financiero/Sistema/tests/test_estructura_workbook.py`:

```python
def test_hoja_proyectos_incluye_columna_cliente_al_final(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)

    ws = wb[af.HOJA_PROYECTOS]
    assert ws.cell(row=1, column=20).value == "Cliente"


def test_hoja_indicadores_incluye_nota_y_evaluacion(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)

    ws = wb[af.HOJA_INDICADORES]
    assert ws.cell(row=1, column=17).value == "Nota del Proyecto"
    assert ws.cell(row=1, column=18).value == "Evaluación"


def test_crea_hoja_clientes_con_encabezados(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)

    assert af.HOJA_CLIENTES in wb.sheetnames
    ws = wb[af.HOJA_CLIENTES]
    assert ws.cell(row=1, column=1).value == "Cliente"
    assert ws.cell(row=1, column=7).value == "CLTV"
    assert ws.cell(row=1, column=8).value == "Clasificación"


def test_crea_hoja_glosario_kpis_con_encabezados(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)

    assert af.HOJA_GLOSARIO_KPIS in wb.sheetnames
    ws = wb[af.HOJA_GLOSARIO_KPIS]
    assert ws.cell(row=1, column=1).value == "KPI"
    assert ws.cell(row=1, column=4).value == "Qué significa el resultado"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_estructura_workbook.py -v`
Expected: the 4 new tests FAIL (`AttributeError: module 'analisis_financiero' has no attribute 'HOJA_CLIENTES'` or similar / wrong header values).

- [x] **Step 3: Extend the header constants**

In `analisis_financiero.py`, replace lines 36-58:

```python
HOJA_PROYECTOS = "Proyectos"
HOJA_DETALLE_COSTOS_REALES = "Detalle Costos Reales"
HOJA_INDICADORES = "Indicadores"
HOJA_CLIENTES = "Clientes"
HOJA_GLOSARIO_KPIS = "Glosario KPIs"

HEADERS_PROYECTOS = [
    "TAG proyecto", "Nombre del proyecto", "Estado", "Fecha de inicio",
    "Fecha de cierre", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados",
    "Costos Materiales Reales", "Costos Equipos Reales",
    "Otros Costos Reales", "Mano de Obra Real", "Total Proyectado",
    "Total Real", "Margen Proyectado", "Margen Real",
    "Desviación % (Real vs Proyectado)", "Cliente",
]
HEADERS_DETALLE_COSTOS_REALES = ["TAG proyecto", "Subcategoría", "Bucket", "Total sin IVA"]
HEADERS_INDICADORES = [
    "TAG proyecto", "Nombre del proyecto", "Rentabilidad sobre costo",
    "Margen neto %", "Productividad Materiales", "Productividad Equipos",
    "Productividad MO", "Productividad Otros", "Costo Materiales % de venta",
    "Costo Equipos % de venta", "Costo MO % de venta", "Costo Otros % de venta",
    "Desviación % Materiales", "Desviación % Equipos", "Desviación % MO",
    "Desviación % Otros", "Nota del Proyecto", "Evaluación",
]
HEADERS_CLIENTES = [
    "Cliente", "AOV (Valor promedio de venta)",
    "Vida del cliente (n° de proyectos)", "Meses activo",
    "Frecuencia de compra (proyectos/año)", "Margen de utilidad %", "CLTV",
    "Clasificación",
]
HEADERS_GLOSARIO_KPIS = [
    "KPI", "Por qué importa", "Qué elementos usa", "Qué significa el resultado",
]
```

- [x] **Step 4: Register the new sheets in `asegurar_estructura_workbook`**

In `analisis_financiero.py`, inside `asegurar_estructura_workbook` (around line 179), replace:

```python
    for nombre_hoja, headers in (
        (HOJA_PROYECTOS, HEADERS_PROYECTOS),
        (HOJA_DETALLE_COSTOS_REALES, HEADERS_DETALLE_COSTOS_REALES),
        (HOJA_INDICADORES, HEADERS_INDICADORES),
    ):
```

with:

```python
    for nombre_hoja, headers in (
        (HOJA_PROYECTOS, HEADERS_PROYECTOS),
        (HOJA_DETALLE_COSTOS_REALES, HEADERS_DETALLE_COSTOS_REALES),
        (HOJA_INDICADORES, HEADERS_INDICADORES),
        (HOJA_CLIENTES, HEADERS_CLIENTES),
        (HOJA_GLOSARIO_KPIS, HEADERS_GLOSARIO_KPIS),
    ):
```

- [x] **Step 5: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_estructura_workbook.py -v`
Expected: all tests PASS, including the 4 new ones and the 3 pre-existing ones (no regression — column 19 of "Proyectos" is still `"Desviación % (Real vs Proyectado)"`, unaffected by appending column 20).

- [x] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_estructura_workbook.py"
git commit -m "feat(analisis-financiero): esqueleto de columna Cliente y hojas Clientes/Glosario KPIs"
```

---

### Task 2: Derivación de Cliente y emparejamiento fuzzy

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py` (imports at top + new section)
- Test: Create `Sistema Analisis Financiero/Sistema/tests/test_cliente_derivacion.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `UMBRAL_SIMILITUD_CLIENTE: float`, `derivar_cliente(nombre_proyecto: str) -> str`, `normalizar_texto(texto: str) -> str`, `emparejar_cliente(candidato: str, clientes_existentes: list[str]) -> dict` (keys: `"cliente"`, `"estado"` ∈ `{"exacto", "pendiente", "nuevo"}`, `"similitud"`). Task 3 calls all three.

- [x] **Step 1: Write the failing tests**

Create `Sistema Analisis Financiero/Sistema/tests/test_cliente_derivacion.py`:

```python
import analisis_financiero as af


def test_deriva_cliente_cortando_en_el_primer_parentesis():
    assert af.derivar_cliente("AGCID (I) FEBRERO") == "AGCID"


def test_deriva_cliente_con_flecha_de_fechas_tambien_corta_en_el_parentesis():
    assert af.derivar_cliente("HOSPITAL TALCA (I) MAYO--> MAYO Y DICIEMBRE") == "HOSPITAL TALCA"


def test_deriva_cliente_sin_parentesis_devuelve_nombre_completo():
    assert af.derivar_cliente("UMAG") == "UMAG"


def test_normalizar_texto_quita_tildes_mayusculas_y_espacios_extra():
    assert af.normalizar_texto("  Hospital  Talca ") == "HOSPITAL TALCA"
    assert af.normalizar_texto("Peñalolén") == "PENALOLEN"


def test_emparejar_cliente_coincidencia_exacta_tras_normalizar():
    resultado = af.emparejar_cliente("hospital talca", ["Hospital Talca"])
    assert resultado == {"cliente": "Hospital Talca", "estado": "exacto", "similitud": 1.0}


def test_emparejar_cliente_similar_no_exacto_queda_pendiente():
    # Similitud verificada en brainstorming: SequenceMatcher da 0.667, sobre
    # el umbral 0.6.
    resultado = af.emparejar_cliente("AGCID FEBRERO", ["AGCID MARZO"])
    assert resultado["cliente"] == "AGCID MARZO"
    assert resultado["estado"] == "pendiente"
    assert resultado["similitud"] >= af.UMBRAL_SIMILITUD_CLIENTE


def test_emparejar_cliente_sin_parecido_es_nuevo():
    resultado = af.emparejar_cliente(
        "Bombas de Calor Puerto Montt", ["AGCID", "Hospital Talca"]
    )
    assert resultado == {
        "cliente": "Bombas de Calor Puerto Montt",
        "estado": "nuevo",
        "similitud": 0.0,
    }


def test_emparejar_cliente_sin_existentes_es_siempre_nuevo():
    resultado = af.emparejar_cliente("Cualquier Cliente", [])
    assert resultado["estado"] == "nuevo"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_cliente_derivacion.py -v`
Expected: FAIL with `AttributeError: module 'analisis_financiero' has no attribute 'derivar_cliente'`.

- [x] **Step 3: Add imports and the new section**

In `analisis_financiero.py`, replace the import block (lines 10-16):

```python
import json
import shutil
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.styles.colors import Color
```

Then add a new section right after the `# ── MAPEO DE CATEGORÍAS ──` section (after `mapear_categoria_a_bucket`, before `# ── LECTURA DE CENTRO DE COSTOS ──`, i.e. after line 218 in the original file):

```python
# ── CLIENTE: DERIVACIÓN Y EMPAREJAMIENTO FUZZY ──────────────────────────────
# "Cliente" no existe como dato separado en Centro de Costos ni en "Proyectos"
# -- se deriva del "Nombre del proyecto" (que a veces mezcla cliente +
# iteración/fecha, ej. "AGCID (I) FEBRERO") y se compara contra los clientes
# ya registrados para detectar recurrencia. Nunca pregunta en vivo (ver
# asegurar_columna_cliente): si hay duda, marca "pendiente" para revisión
# posterior vía confirmar_clientes_pendientes.

UMBRAL_SIMILITUD_CLIENTE = 0.6


def derivar_cliente(nombre_proyecto: str) -> str:
    """Corta el nombre del proyecto en el primer paréntesis (donde suele
    empezar la iteración/fecha, ej. "AGCID (I) FEBRERO" -> "AGCID"). Sin
    paréntesis, devuelve el nombre completo tal cual."""
    candidato = nombre_proyecto.split("(")[0].strip()
    return candidato if candidato else nombre_proyecto.strip()


def normalizar_texto(texto: str) -> str:
    """Mayúsculas, sin tildes, sin espacios repetidos -- para comparar
    nombres de cliente sin que un tilde o un espacio extra genere un falso
    "pendiente"."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.upper().split())


def emparejar_cliente(candidato: str, clientes_existentes: list[str]) -> dict:
    """Compara candidato contra clientes_existentes. Devuelve un dict con
    "cliente" (el valor final a escribir), "estado" ("exacto"/"pendiente"/
    "nuevo") y "similitud". Coincidencia exacta tras normalizar -> "exacto"
    (usa el nombre YA registrado, no el candidato, para no crear variantes de
    capitalización del mismo cliente). Similar pero no exacta (>= umbral)
    -> "pendiente", usa el existente como sugerencia. Sin parecido -> "nuevo",
    usa el candidato tal cual."""
    candidato_norm = normalizar_texto(candidato)
    mejor_match = None
    mejor_similitud = 0.0
    for existente in clientes_existentes:
        if normalizar_texto(existente) == candidato_norm:
            return {"cliente": existente, "estado": "exacto", "similitud": 1.0}
        similitud = SequenceMatcher(None, candidato_norm, normalizar_texto(existente)).ratio()
        if similitud > mejor_similitud:
            mejor_similitud = similitud
            mejor_match = existente
    if mejor_match is not None and mejor_similitud >= UMBRAL_SIMILITUD_CLIENTE:
        return {"cliente": mejor_match, "estado": "pendiente", "similitud": mejor_similitud}
    return {"cliente": candidato, "estado": "nuevo", "similitud": 0.0}
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_cliente_derivacion.py -v`
Expected: all 8 tests PASS.

- [x] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_cliente_derivacion.py"
git commit -m "feat(analisis-financiero): derivacion de cliente y emparejamiento fuzzy"
```

---

### Task 3: Completar la columna "Cliente" en "Proyectos" + `clientes_pendientes.json`

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py` (new constants + new function, near the top-level `RUTA_*` constants and after Task 2's section)
- Test: Create `Sistema Analisis Financiero/Sistema/tests/test_clientes_pendientes.py`

**Interfaces:**
- Consumes: `derivar_cliente`, `emparejar_cliente` (Task 2); `HEADERS_PROYECTOS` (Task 1, for `col_cliente`).
- Produces: `RUTA_CLIENTES_PENDIENTES: Path`, `FUENTE_PENDIENTE_REVISION_CLIENTE: Font`, `FUENTE_CONFIRMADO_CLIENTE: Font`, `leer_clientes_pendientes(ruta_pendientes: Path) -> list[dict]`, `asegurar_columna_cliente(ws_proyectos, filas_validas: list[dict], ruta_pendientes: Path) -> list[dict]`. Task 4 and Task 9 call these.

- [x] **Step 1: Write the failing tests**

Create `Sistema Analisis Financiero/Sistema/tests/test_clientes_pendientes.py`:

```python
import json

import analisis_financiero as af


def _preparar_hoja(tmp_path, filas):
    """filas: list[(tag, nombre)] -- escribe TAG/Nombre en Proyectos y
    devuelve (wb, ws, filas_validas)."""
    ruta_excel = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta_excel)
    ws = wb[af.HOJA_PROYECTOS]
    filas_validas = []
    for i, (tag, nombre) in enumerate(filas, start=2):
        ws.cell(row=i, column=1, value=tag)
        ws.cell(row=i, column=2, value=nombre)
        filas_validas.append({"fila": i, "tag": tag, "nombre": nombre})
    return wb, ws, filas_validas


def test_deriva_y_asigna_cliente_cuando_coincide_exacto_tras_normalizar(tmp_path):
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb, ws, filas_validas = _preparar_hoja(tmp_path, [
        ("HTAL1", "Hospital Talca (I) Mayo"),
        ("HTAL2", "Hospital Talca (I) Mayo Y Diciembre"),
    ])
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1

    pendientes = af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)

    assert ws.cell(row=2, column=col_cliente).value == "Hospital Talca"
    assert ws.cell(row=3, column=col_cliente).value == "Hospital Talca"
    assert pendientes == []
    assert not ruta_pendientes.exists()


def test_marca_pendiente_cuando_es_similar_pero_no_exacto(tmp_path):
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb, ws, filas_validas = _preparar_hoja(tmp_path, [
        ("AGCI1", "AGCID Febrero"),
        ("AGCI2", "AGCID Marzo"),
    ])
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1

    pendientes = af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)

    assert ws.cell(row=2, column=col_cliente).value == "AGCID Febrero"
    assert len(pendientes) == 1
    assert pendientes[0]["tag"] == "AGCI2"
    assert pendientes[0]["fila"] == 3
    assert pendientes[0]["cliente_derivado"] == "AGCID Marzo"
    assert pendientes[0]["cliente_sugerido"] == "AGCID Febrero"
    assert pendientes[0]["estado"] == "Pendiente"
    assert ws.cell(row=3, column=col_cliente).value == "AGCID Febrero"
    assert ws.cell(row=3, column=col_cliente).font.color.rgb == "00C00000"

    assert ruta_pendientes.exists()
    guardado = json.loads(ruta_pendientes.read_text(encoding="utf-8"))
    assert guardado == pendientes


def test_sin_parecido_queda_como_cliente_nuevo_sin_marca(tmp_path):
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb, ws, filas_validas = _preparar_hoja(tmp_path, [
        ("AGCI1", "AGCID Febrero"),
        ("BOMB1", "Bombas de Calor Puerto Montt"),
    ])
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1

    pendientes = af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)

    assert ws.cell(row=3, column=col_cliente).value == "Bombas de Calor Puerto Montt"
    assert pendientes == []


def test_no_toca_una_celda_cliente_ya_llena_a_mano(tmp_path):
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb, ws, filas_validas = _preparar_hoja(tmp_path, [("UMAG", "UMAG (I) Enero")])
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1
    ws.cell(row=2, column=col_cliente, value="Universidad de Magallanes")

    af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)

    assert ws.cell(row=2, column=col_cliente).value == "Universidad de Magallanes"


def test_pendientes_se_acumulan_entre_corridas(tmp_path):
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb, ws, filas_validas = _preparar_hoja(tmp_path, [
        ("AGCI1", "AGCID Febrero"),
        ("AGCI2", "AGCID Marzo"),
    ])
    af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)

    wb2, ws2, filas_validas2 = _preparar_hoja(tmp_path, [
        ("AGCI3", "AGCID Abril"),
    ])
    # Simula que "AGCID Febrero" ya está registrado en la columna Cliente de
    # otra fila de la MISMA hoja -- acá se prueba con una hoja nueva para
    # aislar el caso, así que se pre-llena la columna a mano.
    ws2.cell(row=2, column=af.HEADERS_PROYECTOS.index("Cliente") + 1, value=None)
    af.asegurar_columna_cliente(ws2, filas_validas2, ruta_pendientes)

    guardado = json.loads(ruta_pendientes.read_text(encoding="utf-8"))
    assert len(guardado) == 2
    assert {p["tag"] for p in guardado} == {"AGCI2", "AGCI3"}
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_clientes_pendientes.py -v`
Expected: FAIL with `AttributeError: module 'analisis_financiero' has no attribute 'asegurar_columna_cliente'`.

- [x] **Step 3: Add `RUTA_CLIENTES_PENDIENTES` near the other path constants**

In `analisis_financiero.py`, in the `# ── CONFIGURACIÓN ──` block, right after the line defining `RAIZ_RESPALDOS = RAIZ_MODULO / "Respaldos"`, add:

```python
RUTA_CLIENTES_PENDIENTES = RAIZ / "clientes_pendientes.json"
```

- [x] **Step 4: Add fonts and `asegurar_columna_cliente`/`leer_clientes_pendientes`**

Append to the end of the "CLIENTE: DERIVACIÓN Y EMPAREJAMIENTO FUZZY" section added in Task 2 (after `emparejar_cliente`):

```python
# Mismos hex que Centro de Costos (auditor_centro_costos.py: ROJO="C00000",
# NAVY_OSCURO="1F3864") -- mismo lenguaje visual "rojo = revisar, azul marino
# = corregido a mano" en todo Finanzas QUEMPIN.
FUENTE_PENDIENTE_REVISION_CLIENTE = Font(name="Calibri", size=11, color="C00000")
FUENTE_CONFIRMADO_CLIENTE = Font(name="Calibri", size=11, color="1F3864")


def leer_clientes_pendientes(ruta_pendientes: Path) -> list[dict]:
    """Lee clientes_pendientes.json. Devuelve [] si el archivo no existe
    todavía (primera corrida)."""
    if not ruta_pendientes.exists():
        return []
    with open(ruta_pendientes, "r", encoding="utf-8") as f:
        return json.load(f)


def asegurar_columna_cliente(ws_proyectos, filas_validas: list[dict], ruta_pendientes: Path) -> list[dict]:
    """Completa la columna 'Cliente' de las filas válidas que la tengan
    vacía: deriva un candidato del nombre del proyecto y lo empareja contra
    los clientes ya asignados (incluyendo los que se van asignando en esta
    misma corrida). Si el emparejamiento queda 'pendiente', pinta la celda de
    rojo y agrega una entrada a clientes_pendientes.json -- nunca pregunta en
    vivo (este módulo corre encadenado y no bloqueante al run de Centro de
    Costos). Devuelve solo las entradas pendientes NUEVAS de esta corrida."""
    col_cliente = HEADERS_PROYECTOS.index("Cliente") + 1

    clientes_existentes = []
    for fila_info in filas_validas:
        valor = ws_proyectos.cell(row=fila_info["fila"], column=col_cliente).value
        if valor:
            clientes_existentes.append(valor)

    pendientes_nuevos = []
    for fila_info in filas_validas:
        r = fila_info["fila"]
        celda = ws_proyectos.cell(row=r, column=col_cliente)
        if celda.value:
            continue

        candidato = derivar_cliente(fila_info["nombre"])
        resultado = emparejar_cliente(candidato, clientes_existentes)
        celda.value = resultado["cliente"]

        if resultado["estado"] == "pendiente":
            celda.font = FUENTE_PENDIENTE_REVISION_CLIENTE
            pendientes_nuevos.append({
                "tag": fila_info["tag"],
                "fila": r,
                "nombre_proyecto": fila_info["nombre"],
                "cliente_derivado": candidato,
                "cliente_sugerido": resultado["cliente"],
                "similitud": round(resultado["similitud"], 2),
                "estado": "Pendiente",
            })

        clientes_existentes.append(resultado["cliente"])

    if pendientes_nuevos:
        pendientes_totales = leer_clientes_pendientes(ruta_pendientes) + pendientes_nuevos
        with open(ruta_pendientes, "w", encoding="utf-8") as f:
            json.dump(pendientes_totales, f, ensure_ascii=False, indent=2)

    return pendientes_nuevos
```

- [x] **Step 5: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_clientes_pendientes.py -v`
Expected: all 5 tests PASS.

- [x] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_clientes_pendientes.py"
git commit -m "feat(analisis-financiero): completar columna Cliente con deteccion fuzzy y cola de pendientes"
```

---

### Task 4: `confirmar_clientes_pendientes` + comando `confirmar-cliente` del skill

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py` (new function in the same section)
- Modify: `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py`
- Test: Create `Sistema Analisis Financiero/Sistema/tests/test_confirmar_clientes.py`

**Interfaces:**
- Consumes: `leer_clientes_pendientes`, `HEADERS_PROYECTOS`, `FUENTE_CONFIRMADO_CLIENTE` (Task 3); `hacer_backup` (existing); `HOJA_PROYECTOS`, `RUTA_EXCEL`, `RUTA_CLIENTES_PENDIENTES`, `RAIZ_RESPALDOS` (existing/Task 3 constants).
- Produces: `confirmar_clientes_pendientes(objetivo=None, ruta_excel=None, ruta_pendientes=None, ruta_respaldos=None) -> list[dict]`. Consumed by `driver.py`'s new `confirmar-cliente` command; same call contract as Centro de Costos' `confirmar_correcciones` (`objetivo=None` → preview only, `"TODOS"` → apply all pending, `list[str]` of tags → apply only those).

- [x] **Step 1: Write the failing tests**

Create `Sistema Analisis Financiero/Sistema/tests/test_confirmar_clientes.py`:

```python
import json

import openpyxl

import analisis_financiero as af


def _armar_pendiente(tmp_path):
    ruta_excel = tmp_path / "Análisis de Proyectos.xlsx"
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb = af.asegurar_estructura_workbook(ruta_excel)
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="AGCI1")
    ws.cell(row=2, column=2, value="AGCID Febrero")
    ws.cell(row=3, column=1, value="AGCI2")
    ws.cell(row=3, column=2, value="AGCID Marzo")
    filas_validas = [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero"},
        {"fila": 3, "tag": "AGCI2", "nombre": "AGCID Marzo"},
    ]
    af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)
    wb.save(ruta_excel)
    return ruta_excel, ruta_pendientes


def test_preview_no_toca_el_excel_ni_el_json(tmp_path):
    ruta_excel, ruta_pendientes = _armar_pendiente(tmp_path)
    contenido_antes = ruta_pendientes.read_text(encoding="utf-8")

    resultado = af.confirmar_clientes_pendientes(
        None, ruta_excel=ruta_excel, ruta_pendientes=ruta_pendientes,
        ruta_respaldos=tmp_path / "Respaldos",
    )

    assert len(resultado) == 1
    assert resultado[0]["tag"] == "AGCI2"
    assert ruta_pendientes.read_text(encoding="utf-8") == contenido_antes
    assert not (tmp_path / "Respaldos").exists()


def test_todos_aplica_la_sugerencia_y_recolorea_azul_marino(tmp_path):
    ruta_excel, ruta_pendientes = _armar_pendiente(tmp_path)

    aplicados = af.confirmar_clientes_pendientes(
        "TODOS", ruta_excel=ruta_excel, ruta_pendientes=ruta_pendientes,
        ruta_respaldos=tmp_path / "Respaldos",
    )

    assert len(aplicados) == 1
    wb = openpyxl.load_workbook(ruta_excel)
    ws = wb[af.HOJA_PROYECTOS]
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1
    celda = ws.cell(row=3, column=col_cliente)
    assert celda.value == "AGCID Febrero"
    assert celda.font.color.rgb == "001F3864"

    guardado = json.loads(ruta_pendientes.read_text(encoding="utf-8"))
    assert guardado[0]["estado"] == "Confirmado"


def test_filtra_por_tag_especifico(tmp_path):
    ruta_excel, ruta_pendientes = _armar_pendiente(tmp_path)

    aplicados = af.confirmar_clientes_pendientes(
        ["NO-EXISTE"], ruta_excel=ruta_excel, ruta_pendientes=ruta_pendientes,
        ruta_respaldos=tmp_path / "Respaldos",
    )

    assert aplicados == []
    guardado = json.loads(ruta_pendientes.read_text(encoding="utf-8"))
    assert guardado[0]["estado"] == "Pendiente"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_confirmar_clientes.py -v`
Expected: FAIL with `AttributeError: module 'analisis_financiero' has no attribute 'confirmar_clientes_pendientes'`.

- [x] **Step 3: Implement `confirmar_clientes_pendientes`**

Append to the same section in `analisis_financiero.py`:

```python
def confirmar_clientes_pendientes(
    objetivo=None,
    ruta_excel: Path | None = None,
    ruta_pendientes: Path | None = None,
    ruta_respaldos: Path | None = None,
) -> list[dict]:
    """objetivo=None -> preview de solo lectura (no toca nada). objetivo=
    "TODOS" o lista de TAGs -> aplica: escribe cliente_sugerido en la celda,
    recolorea azul marino, marca "Confirmado" en clientes_pendientes.json.
    Mismo contrato que confirmar_correcciones de Centro de Costos."""
    ruta_excel = ruta_excel or RUTA_EXCEL
    ruta_pendientes = ruta_pendientes or RUTA_CLIENTES_PENDIENTES
    ruta_respaldos = ruta_respaldos or RAIZ_RESPALDOS

    pendientes = leer_clientes_pendientes(ruta_pendientes)
    seleccion_pendiente = [p for p in pendientes if p["estado"] == "Pendiente"]

    if objetivo is None:
        return seleccion_pendiente

    seleccion = (
        seleccion_pendiente if objetivo == "TODOS"
        else [p for p in seleccion_pendiente if p["tag"] in set(objetivo)]
    )
    if not seleccion:
        return []

    hacer_backup(ruta_excel, ruta_respaldos)
    wb = openpyxl.load_workbook(ruta_excel)
    ws_proyectos = wb[HOJA_PROYECTOS]
    col_cliente = HEADERS_PROYECTOS.index("Cliente") + 1

    for p in seleccion:
        celda = ws_proyectos.cell(row=p["fila"], column=col_cliente)
        celda.value = p["cliente_sugerido"]
        celda.font = FUENTE_CONFIRMADO_CLIENTE
        p["estado"] = "Confirmado"

    wb.save(ruta_excel)
    with open(ruta_pendientes, "w", encoding="utf-8") as f:
        json.dump(pendientes, f, ensure_ascii=False, indent=2)

    return seleccion
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_confirmar_clientes.py -v`
Expected: all 3 tests PASS.

- [x] **Step 5: Add the `confirmar-cliente` command to `driver.py`**

In `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py`, first update the module docstring (lines 1-19) so it lists 3 commands instead of 2 — replace:

```python
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
```

with:

```python
No reimplementa la logica: importa analisis_financiero.py desde Sistema/ y
expone tres comandos:

  status           -> Solo lectura (dry_run=True): que carpetas de proyecto
                      se crearian, que categorias de Centro de Costos caen
                      en "Otros" por no tener mapeo explicito, sin tocar
                      ningun archivo.

  run              -> Ejecucion real: backup, crea carpetas de proyecto
                      nuevas, regenera "Detalle Costos Reales" y las
                      formulas de "Proyectos"/"Indicadores"/"Clientes"/
                      "Glosario KPIs", guarda el Excel.

  confirmar-cliente -> Sin argumentos: lista clientes pendientes de revision
                      (columna "Cliente" en fuente roja). "--todos" o una
                      lista de TAGs: aplica la sugerencia y recolorea azul
                      marino.

Uso:
  python driver.py status
  python driver.py run
  python driver.py confirmar-cliente [--todos|TAG ...]
"""
```

Then replace the `cmd_run`/`main` section (from `def cmd_run() -> int:` to the end) with:

```python
def cmd_run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    af.main()
    return 0


def cmd_confirmar_cliente(args: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    if not args:
        pendientes = af.confirmar_clientes_pendientes(None)
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
    aplicados = af.confirmar_clientes_pendientes(objetivo)
    if not aplicados:
        print("\nNo hay clientes pendientes que coincidan con lo pedido.")
    for p in aplicados:
        print(f"  [OK] {p['tag']} -> Cliente '{p['cliente_sugerido']}' confirmado (azul marino).")
    return 0


def main() -> int:
    comandos = ("status", "run", "confirmar-cliente")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        print("Uso: python driver.py [status|run|confirmar-cliente [--todos|TAG ...]]")
        return 2
    if sys.argv[1] == "status":
        return cmd_status()
    if sys.argv[1] == "confirmar-cliente":
        return cmd_confirmar_cliente(sys.argv[2:])
    return cmd_run()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 6: Manually smoke-test the driver command**

Run: `cd "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero" && python driver.py confirmar-cliente`
Expected: prints `Clientes pendientes de confirmar: 0` (no pendings yet against the real `Análisis de Proyectos.xlsx`, since it's still empty) and exits 0. No traceback.

- [x] **Step 7: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_confirmar_clientes.py" "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/driver.py"
git commit -m "feat(analisis-financiero): comando confirmar-cliente para aplicar pendientes de Cliente"
```

---

### Task 5: Fórmulas de "Nota del Proyecto" y "Evaluación"

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py:394-421` (`asegurar_hoja_indicadores`)
- Test: Create `Sistema Analisis Financiero/Sistema/tests/test_nota_evaluacion.py`

**Interfaces:**
- Consumes: nothing new from other tasks (writes into `HOJA_INDICADORES`, columns already reserved in Task 1).
- Produces: `MARGEN_OBJETIVO_NOTA: float`, `PESO_RENTABILIDAD_NOTA: float`, `PESO_DESVIACION_NOTA: float`; extends `asegurar_hoja_indicadores` to also write columns 17/18. No new public function signature — same function as before, just longer.

- [x] **Step 1: Write the failing tests**

Create `Sistema Analisis Financiero/Sistema/tests/test_nota_evaluacion.py`:

```python
import analisis_financiero as af


def test_formula_nota_referencia_margen_y_desviacion_total(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])

    ws = wb[af.HOJA_INDICADORES]
    formula_nota = ws.cell(row=2, column=17).value
    assert formula_nota == (
        "=ROUND(0.7*MIN(100,MAX(0,(Proyectos!R2/Proyectos!F2)/0.25*100))"
        "+0.3*MIN(100,MAX(0,100-ABS(Proyectos!S2)*100)),0)"
    )


def test_formula_evaluacion_referencia_la_nota_de_la_misma_fila(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 4, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ])

    ws = wb[af.HOJA_INDICADORES]
    # segunda fila válida queda compacta en la fila 3 de "Indicadores" pero
    # su Nota (columna Q) también está en la fila 3, no en la 4.
    assert ws.cell(row=3, column=18).value == (
        '=IF(Q3>=85,"Excelente",IF(Q3>=70,"Bueno",'
        'IF(Q3>=55,"Aprobado","Requiere atención")))'
    )


def test_constantes_de_calibracion_de_la_nota():
    assert af.MARGEN_OBJETIVO_NOTA == 0.25
    assert af.PESO_RENTABILIDAD_NOTA == 0.7
    assert af.PESO_DESVIACION_NOTA == 0.3
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_nota_evaluacion.py -v`
Expected: FAIL — column 17/18 are `None` (not yet written), `AttributeError` for the constants.

- [x] **Step 3: Add the constants and formula helpers**

In `analisis_financiero.py`, right before `# ── FÓRMULAS DE LA HOJA "INDICADORES" ──` (around line 392), add:

```python
# ── NOTA DEL PROYECTO (hoja "Indicadores") ──────────────────────────────────
# 0-100, aprobatorio >=55. Rentabilidad domina el peso (70/30) -- decision
# del usuario en brainstorming, spec 2026-07-21 seccion 1. Constantes
# separadas de la formula para que recalibrar el benchmark no implique
# reescribir la logica, solo estos 3 valores.
MARGEN_OBJETIVO_NOTA = 0.25
PESO_RENTABILIDAD_NOTA = 0.7
PESO_DESVIACION_NOTA = 0.3


def _formula_nota(fila_proyectos: int) -> str:
    r = fila_proyectos
    score_margen = f"MIN(100,MAX(0,(Proyectos!R{r}/Proyectos!F{r})/{MARGEN_OBJETIVO_NOTA}*100))"
    score_desviacion = f"MIN(100,MAX(0,100-ABS(Proyectos!S{r})*100))"
    return f"=ROUND({PESO_RENTABILIDAD_NOTA}*{score_margen}+{PESO_DESVIACION_NOTA}*{score_desviacion},0)"


def _formula_evaluacion(fila_destino: int) -> str:
    q = f"Q{fila_destino}"
    return (
        f'=IF({q}>=85,"Excelente",IF({q}>=70,"Bueno",'
        f'IF({q}>=55,"Aprobado","Requiere atención")))'
    )
```

- [x] **Step 4: Extend `asegurar_hoja_indicadores` to write columns 17/18**

In `analisis_financiero.py`, inside `asegurar_hoja_indicadores`, right after the existing line writing column 16 (`ws.cell(row=fila_destino, column=16, value=f"=Proyectos!M{r}/Proyectos!J{r}-1")`), add:

```python
        ws.cell(row=fila_destino, column=17, value=_formula_nota(r))
        ws.cell(row=fila_destino, column=18, value=_formula_evaluacion(fila_destino))
```

(This is still inside the `for fila_info in filas_validas:` loop, before the trailing `fila_destino += 1`.)

- [x] **Step 5: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_nota_evaluacion.py tests/test_formulas_indicadores.py -v`
Expected: all tests PASS, including the pre-existing `test_formulas_indicadores.py` (unaffected — it only asserts columns 1-16).

- [x] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_nota_evaluacion.py"
git commit -m "feat(analisis-financiero): formula de Nota del Proyecto (0-100) y Evaluacion"
```

---

### Task 6: Hoja "Clientes" (CLTV)

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py` (new function, after `asegurar_hoja_indicadores`)
- Test: Create `Sistema Analisis Financiero/Sistema/tests/test_hoja_clientes.py`

**Interfaces:**
- Consumes: `HOJA_CLIENTES`, `HEADERS_PROYECTOS` (Task 1); reads the "Cliente" column of `ws_proyectos` (populated by Task 3's `asegurar_columna_cliente`, but this function only needs the column to already contain values — doesn't call Task 3 itself, keeping it independently testable).
- Produces: `asegurar_hoja_clientes(wb, filas_validas: list[dict], ws_proyectos) -> None`. Task 9 calls this from `ejecutar()`.

- [x] **Step 1: Write the failing tests**

Create `Sistema Analisis Financiero/Sistema/tests/test_hoja_clientes.py`:

```python
import analisis_financiero as af


def _preparar(tmp_path, filas_proyectos):
    """filas_proyectos: list[dict] con fila/tag/nombre/cliente -- escribe TAG,
    Nombre y Cliente en 'Proyectos' y devuelve (wb, ws_proyectos, filas_validas)."""
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)
    ws = wb[af.HOJA_PROYECTOS]
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1
    filas_validas = []
    for fp in filas_proyectos:
        ws.cell(row=fp["fila"], column=1, value=fp["tag"])
        ws.cell(row=fp["fila"], column=2, value=fp["nombre"])
        ws.cell(row=fp["fila"], column=col_cliente, value=fp["cliente"])
        filas_validas.append({"fila": fp["fila"], "tag": fp["tag"], "nombre": fp["nombre"]})
    return wb, ws, filas_validas


def test_una_fila_por_cliente_unico(tmp_path):
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID"},
        {"fila": 3, "tag": "HTAL1", "nombre": "Hospital Talca Mayo", "cliente": "Hospital Talca"},
        {"fila": 4, "tag": "HTAL2", "nombre": "Hospital Talca Dic", "cliente": "Hospital Talca"},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    valores_cliente = [ws_clientes.cell(row=r, column=1).value for r in (2, 3)]
    assert sorted(valores_cliente) == ["AGCID", "Hospital Talca"]


def test_formulas_agregan_sobre_proyectos_filtrando_por_columna_cliente(tmp_path):
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID"},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    assert ws_clientes.cell(row=2, column=1).value == "AGCID"
    assert ws_clientes.cell(row=2, column=2).value == "=AVERAGEIF(Proyectos!$T:$T,$A2,Proyectos!$F:$F)"
    assert ws_clientes.cell(row=2, column=3).value == "=COUNTIF(Proyectos!$T:$T,$A2)"
    assert ws_clientes.cell(row=2, column=4).value == (
        "=MAX(1,(MAXIFS(Proyectos!$D:$D,Proyectos!$T:$T,$A2)"
        "-MINIFS(Proyectos!$D:$D,Proyectos!$T:$T,$A2))/30)"
    )
    assert ws_clientes.cell(row=2, column=5).value == "=C2/(D2/12)"
    assert ws_clientes.cell(row=2, column=6).value == (
        "=SUMIF(Proyectos!$T:$T,$A2,Proyectos!$R:$R)/SUMIF(Proyectos!$T:$T,$A2,Proyectos!$F:$F)"
    )
    assert ws_clientes.cell(row=2, column=7).value == "=B2*E2*C2*F2"
    assert ws_clientes.cell(row=2, column=8).value == (
        '=IF(G2>=PERCENTILE(Clientes!$G:$G,0.67),"Clientes estratégicos",'
        'IF(G2>=PERCENTILE(Clientes!$G:$G,0.33),"Clientes potenciales","Clientes de oportunidad"))'
    )


def test_filas_sin_cliente_asignado_se_ignoran(tmp_path):
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": None},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    assert ws_clientes.max_row == 1


def test_regenerar_borra_filas_de_la_corrida_anterior(tmp_path):
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID"},
    ])
    af.asegurar_hoja_clientes(wb, filas_validas, ws)
    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    assert ws_clientes.max_row == 2
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_hoja_clientes.py -v`
Expected: FAIL with `AttributeError: module 'analisis_financiero' has no attribute 'asegurar_hoja_clientes'`.

- [x] **Step 3: Implement `asegurar_hoja_clientes`**

In `analisis_financiero.py`, add a new section right after `asegurar_hoja_indicadores` (after the function added/extended in Task 5) and before `# ── ORQUESTADOR ──`:

```python
# ── HOJA "CLIENTES" (CLTV, 100% regenerada cada corrida) ────────────────────

def asegurar_hoja_clientes(wb, filas_validas: list[dict], ws_proyectos) -> None:
    """Regenera 'Clientes' completa: una fila por valor único de la columna
    'Cliente' de 'Proyectos' (filas sin Cliente asignado se ignoran). Todas
    las columnas son fórmulas que agregan sobre 'Proyectos' filtrando por
    Cliente -- nunca valores calculados en Python -- para que un proyecto
    nuevo del mismo cliente se sume solo la próxima vez que Excel recalcule."""
    ws = wb[HOJA_CLIENTES]
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)

    col_cliente = HEADERS_PROYECTOS.index("Cliente") + 1
    clientes_unicos = []
    vistos = set()
    for fila_info in filas_validas:
        cliente = ws_proyectos.cell(row=fila_info["fila"], column=col_cliente).value
        if cliente and cliente not in vistos:
            vistos.add(cliente)
            clientes_unicos.append(cliente)

    for i, cliente in enumerate(sorted(clientes_unicos), start=2):
        ws.cell(row=i, column=1, value=cliente)
        ws.cell(row=i, column=2, value=f"=AVERAGEIF(Proyectos!$T:$T,$A{i},Proyectos!$F:$F)")
        ws.cell(row=i, column=3, value=f"=COUNTIF(Proyectos!$T:$T,$A{i})")
        ws.cell(row=i, column=4, value=(
            f"=MAX(1,(MAXIFS(Proyectos!$D:$D,Proyectos!$T:$T,$A{i})"
            f"-MINIFS(Proyectos!$D:$D,Proyectos!$T:$T,$A{i}))/30)"
        ))
        ws.cell(row=i, column=5, value=f"=C{i}/(D{i}/12)")
        ws.cell(row=i, column=6, value=(
            f"=SUMIF(Proyectos!$T:$T,$A{i},Proyectos!$R:$R)/SUMIF(Proyectos!$T:$T,$A{i},Proyectos!$F:$F)"
        ))
        ws.cell(row=i, column=7, value=f"=B{i}*E{i}*C{i}*F{i}")
        ws.cell(row=i, column=8, value=(
            f'=IF(G{i}>=PERCENTILE(Clientes!$G:$G,0.67),"Clientes estratégicos",'
            f'IF(G{i}>=PERCENTILE(Clientes!$G:$G,0.33),"Clientes potenciales","Clientes de oportunidad"))'
        ))
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_hoja_clientes.py -v`
Expected: all 4 tests PASS.

- [x] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_hoja_clientes.py"
git commit -m "feat(analisis-financiero): hoja Clientes con formulas de CLTV"
```

---

### Task 7: Hoja "Glosario KPIs"

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py` (new constant + new function)
- Test: Create `Sistema Analisis Financiero/Sistema/tests/test_glosario_kpis.py`

**Interfaces:**
- Consumes: `HOJA_GLOSARIO_KPIS`, `HEADERS_GLOSARIO_KPIS` (Task 1).
- Produces: `GLOSARIO_KPIS: list[tuple[str, str, str, str]]`, `asegurar_hoja_glosario_kpis(wb) -> None`. Task 9 calls this from `ejecutar()`.

- [x] **Step 1: Write the failing tests**

Create `Sistema Analisis Financiero/Sistema/tests/test_glosario_kpis.py`:

```python
import analisis_financiero as af


def test_una_fila_por_kpi_del_glosario(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.asegurar_hoja_glosario_kpis(wb)

    ws = wb[af.HOJA_GLOSARIO_KPIS]
    assert ws.max_row == 1 + len(af.GLOSARIO_KPIS)
    assert ws.cell(row=2, column=1).value == af.GLOSARIO_KPIS[0][0]
    assert ws.cell(row=2, column=2).value == af.GLOSARIO_KPIS[0][1]


def test_incluye_los_kpis_nuevos_de_este_spec(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_glosario_kpis(wb)

    nombres = [fila[0] for fila in af.GLOSARIO_KPIS]
    for esperado in ("Nota del Proyecto", "Evaluación", "CLTV", "Clasificación (Clientes)"):
        assert esperado in nombres


def test_se_reescribe_completa_sin_duplicar_entre_corridas(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_glosario_kpis(wb)
    af.asegurar_hoja_glosario_kpis(wb)

    ws = wb[af.HOJA_GLOSARIO_KPIS]
    assert ws.max_row == 1 + len(af.GLOSARIO_KPIS)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_glosario_kpis.py -v`
Expected: FAIL with `AttributeError: module 'analisis_financiero' has no attribute 'asegurar_hoja_glosario_kpis'`.

- [x] **Step 3: Implement the glossary content and writer function**

In `analisis_financiero.py`, add a new section right after `asegurar_hoja_clientes` (Task 6) and before `# ── ORQUESTADOR ──`:

```python
# ── HOJA "GLOSARIO KPIS" (texto estatico, 100% regenerado cada corrida) ─────
# Contenido fijo -- no depende de datos del usuario. Cubre el playbook
# original (spec 2026-07-20) mas los KPIs de este spec (2026-07-21): Nota,
# Evaluacion, y los 6 de la hoja Clientes.

GLOSARIO_KPIS: list[tuple[str, str, str, str]] = [
    (
        "Rentabilidad sobre costo",
        "Mide cuánto margen genera cada peso gastado en el proyecto — un markup, no un ROI de capital invertido.",
        "Margen Real, Total Real",
        "Valor alto = el proyecto generó mucho margen por cada peso de costo incurrido; sirve para comparar eficiencia entre proyectos de tamaños distintos.",
    ),
    (
        "Margen neto %",
        "El indicador de rentabilidad más directo y comparable entre proyectos de distinto tamaño.",
        "Margen Real, Monto de Venta",
        "20% significa que de cada $100 vendidos quedan $20 de utilidad tras cubrir todos los costos reales.",
    ),
    (
        "Productividad (Materiales/Equipos/MO/Otros)",
        "Mide cuántos pesos de venta genera cada peso gastado en esa categoría — permite ver qué categoría 'rinde' más por peso invertido.",
        "Monto de Venta, Costo Real de la categoría",
        "Productividad = 3 → cada $1 gastado en esa categoría generó $3 de venta; útil para priorizar dónde enfocar control de gasto.",
    ),
    (
        "Costo % de venta (por categoría)",
        "Muestra la estructura de costos del proyecto — qué parte de cada peso vendido se va en esa categoría.",
        "Costo Real de la categoría, Monto de Venta",
        "35% en Costo MO % de venta → un tercio de cada venta se destina a mano de obra; detecta categorías que consumen desproporcionadamente el margen.",
    ),
    (
        "Desviación % (por categoría, Real vs Proyectado)",
        "Mide qué tan preciso fue el presupuesto original para esa categoría — clave para mejorar futuras cotizaciones.",
        "Costo Real, Costo Proyectado de la categoría",
        "+15% = se gastó 15% más de lo presupuestado; negativo = se gastó menos de lo previsto.",
    ),
    (
        "Nota del Proyecto",
        "Resume rentabilidad y control de presupuesto en un solo número comparable entre proyectos, para priorizar dónde poner atención de gestión.",
        "Margen neto % (70%, contra objetivo de 25%) y Desviación % Total (30%)",
        "≥55 = proyecto en rango aceptable; <55 = requiere revisión (rentabilidad baja y/o descontrol presupuestario).",
    ),
    (
        "Evaluación",
        "Traduce la nota a una etiqueta rápida de lectura para revisiones ejecutivas.",
        "Nota del Proyecto",
        "Excelente / Bueno / Aprobado / Requiere atención.",
    ),
    (
        "AOV (Clientes)",
        "Mide el tamaño promedio de una venta a ese cliente.",
        "Monto de Venta de sus proyectos",
        "AOV alto = cliente que trae proyectos grandes por transacción.",
    ),
    (
        "Vida del cliente",
        "Mide cuántas veces ha comprado el cliente en total — la base para saber si es recurrente.",
        "Conteo de proyectos del cliente",
        "Vida=1 → cliente de una sola compra hasta ahora; vida>1 → recurrente.",
    ),
    (
        "Meses activo",
        "Mide cuánto tiempo lleva comprando el cliente — el denominador para anualizar la frecuencia.",
        "Fecha más antigua y más reciente entre sus proyectos",
        "Meses activo alto + vida baja → cliente esporádico; meses activo bajo + vida alta → cliente muy activo recientemente.",
    ),
    (
        "Frecuencia de compra (Clientes)",
        "Mide qué tan seguido vuelve a comprar el cliente, anualizado — clave para proyectar ingresos futuros de ese cliente.",
        "Vida del cliente, Meses activo",
        "Frecuencia=2 → el cliente compra en promedio 2 veces al año.",
    ),
    (
        "Margen de utilidad % (Clientes)",
        "Mide qué tan rentable es la relación completa con ese cliente, ponderado por tamaño de proyecto.",
        "Suma de Margen Real y de Monto de Venta de todos sus proyectos",
        "Mismo significado que Margen neto % pero a nivel cliente.",
    ),
    (
        "CLTV",
        "Estima el valor total que el cliente representa para QUEMPIN a lo largo de su relación completa — la métrica central para decidir dónde invertir esfuerzo comercial.",
        "AOV × Frecuencia de compra × Vida del cliente × Margen de utilidad %",
        "CLTV alto = cliente que ha generado y probablemente seguirá generando mucho valor; prioridad para retención.",
    ),
    (
        "Clasificación (Clientes)",
        "Traduce el CLTV a un tier accionable, relativo a la cartera actual de QUEMPIN, no a un corte fijo en pesos que quede obsoleto con el crecimiento de la empresa.",
        "Percentil del CLTV entre todos los clientes registrados",
        "'Clientes estratégicos' (top 33%) → atención prioritaria; 'Clientes de oportunidad' (bottom 33%) → candidatos a desarrollar o repensar la relación.",
    ),
]


def asegurar_hoja_glosario_kpis(wb) -> None:
    """Reescribe 'Glosario KPIs' completa desde la constante GLOSARIO_KPIS --
    texto estático, no depende de datos del usuario ni de fórmulas."""
    ws = wb[HOJA_GLOSARIO_KPIS]
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)

    for i, fila in enumerate(GLOSARIO_KPIS, start=2):
        for col, valor in enumerate(fila, start=1):
            ws.cell(row=i, column=col, value=valor)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_glosario_kpis.py -v`
Expected: all 3 tests PASS.

- [x] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_glosario_kpis.py"
git commit -m "feat(analisis-financiero): hoja Glosario KPIs con descripcion de cada indicador"
```

---

### Task 8: Estilo visual de las columnas y hojas nuevas

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py:72-150` (formats, style dicts, `aplicar_estilo_visual`)
- Test: Create `Sistema Analisis Financiero/Sistema/tests/test_estilo_visual_nuevo.py`

**Interfaces:**
- Consumes: `HOJA_CLIENTES`, `HOJA_GLOSARIO_KPIS` (Task 1); `COLOR_IDENTIFICACION`, `COLOR_DERIVADO`, `FORMATO_MONEDA`, `FORMATO_PORCENTAJE`, `FORMATO_RATIO` (existing).
- Produces: `FORMATO_ENTERO: str`; extends `ESTILO_COLUMNAS_PROYECTOS` (key `"T"`), `ESTILO_COLUMNAS_INDICADORES` (keys `"Q"`, `"R"`); new `ESTILO_COLUMNAS_CLIENTES`, `ESTILO_COLUMNAS_GLOSARIO_KPIS`; extends `aplicar_estilo_visual`'s loop tuple.

- [x] **Step 1: Write the failing tests**

Create `Sistema Analisis Financiero/Sistema/tests/test_estilo_visual_nuevo.py`:

```python
import analisis_financiero as af


def test_columna_cliente_de_proyectos_tiene_estilo(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_estilo_visual(wb)

    ws = wb[af.HOJA_PROYECTOS]
    assert ws["T1"].fill.fgColor.theme == af.COLOR_IDENTIFICACION.theme


def test_columnas_nota_y_evaluacion_de_indicadores_tienen_estilo(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_estilo_visual(wb)

    ws = wb[af.HOJA_INDICADORES]
    assert ws.column_dimensions["Q"].number_format == af.FORMATO_ENTERO
    assert ws["Q1"].fill.fgColor.theme == af.COLOR_DERIVADO.theme
    assert ws["R1"].fill.fgColor.theme == af.COLOR_DERIVADO.theme


def test_hoja_clientes_tiene_estilo_en_las_8_columnas(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_estilo_visual(wb)

    ws = wb[af.HOJA_CLIENTES]
    for columna in "ABCDEFGH":
        assert ws[f"{columna}1"].font.bold is True
    assert ws.column_dimensions["G"].number_format == af.FORMATO_MONEDA
    assert ws.column_dimensions["F"].number_format == af.FORMATO_PORCENTAJE


def test_hoja_glosario_kpis_tiene_encabezado_en_negrita(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_estilo_visual(wb)

    ws = wb[af.HOJA_GLOSARIO_KPIS]
    for columna in "ABCD":
        assert ws[f"{columna}1"].font.bold is True
    assert ws.column_dimensions["B"].width >= 40
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_estilo_visual_nuevo.py -v`
Expected: FAIL — `AttributeError: module 'analisis_financiero' has no attribute 'FORMATO_ENTERO'`, and `"T"`/`"Q"`/`"R"` keys missing from the style dicts (no fill/format applied to those columns).

- [x] **Step 3: Add `FORMATO_ENTERO`**

In `analisis_financiero.py`, right after the line `FORMATO_RATIO = "0.00"` (around line 74), add:

```python
FORMATO_ENTERO = "0"
```

- [x] **Step 4: Extend `ESTILO_COLUMNAS_PROYECTOS` and `ESTILO_COLUMNAS_INDICADORES`**

In `analisis_financiero.py`, inside `ESTILO_COLUMNAS_PROYECTOS`, right after the `"S"` entry, add:

```python
    "T": (COLOR_IDENTIFICACION, None, 22),
```

Inside `ESTILO_COLUMNAS_INDICADORES`, right after the `"P"` entry, add:

```python
    "Q": (COLOR_DERIVADO, FORMATO_ENTERO, 12),
    "R": (COLOR_DERIVADO, None, 20),
```

- [x] **Step 5: Add `ESTILO_COLUMNAS_CLIENTES` and `ESTILO_COLUMNAS_GLOSARIO_KPIS`**

In `analisis_financiero.py`, right after `ESTILO_COLUMNAS_INDICADORES`'s closing `}` (around line 136), add:

```python
ESTILO_COLUMNAS_CLIENTES = {
    "A": (COLOR_IDENTIFICACION, None, 22),
    "B": (COLOR_DERIVADO, FORMATO_MONEDA, 18),
    "C": (COLOR_DERIVADO, FORMATO_ENTERO, 14),
    "D": (COLOR_DERIVADO, FORMATO_RATIO, 14),
    "E": (COLOR_DERIVADO, FORMATO_RATIO, 14),
    "F": (COLOR_DERIVADO, FORMATO_PORCENTAJE, 14),
    "G": (COLOR_DERIVADO, FORMATO_MONEDA, 18),
    "H": (COLOR_DERIVADO, None, 22),
}

ESTILO_COLUMNAS_GLOSARIO_KPIS = {
    "A": (COLOR_IDENTIFICACION, None, 30),
    "B": (COLOR_IDENTIFICACION, None, 50),
    "C": (COLOR_IDENTIFICACION, None, 40),
    "D": (COLOR_IDENTIFICACION, None, 50),
}
```

- [x] **Step 6: Register the 2 new sheets in `aplicar_estilo_visual`**

In `analisis_financiero.py`, inside `aplicar_estilo_visual` (around line 146), replace:

```python
    for nombre_hoja, estilo_columnas in (
        (HOJA_PROYECTOS, ESTILO_COLUMNAS_PROYECTOS),
        (HOJA_DETALLE_COSTOS_REALES, ESTILO_COLUMNAS_DETALLE_COSTOS_REALES),
        (HOJA_INDICADORES, ESTILO_COLUMNAS_INDICADORES),
    ):
```

with:

```python
    for nombre_hoja, estilo_columnas in (
        (HOJA_PROYECTOS, ESTILO_COLUMNAS_PROYECTOS),
        (HOJA_DETALLE_COSTOS_REALES, ESTILO_COLUMNAS_DETALLE_COSTOS_REALES),
        (HOJA_INDICADORES, ESTILO_COLUMNAS_INDICADORES),
        (HOJA_CLIENTES, ESTILO_COLUMNAS_CLIENTES),
        (HOJA_GLOSARIO_KPIS, ESTILO_COLUMNAS_GLOSARIO_KPIS),
    ):
```

- [x] **Step 7: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_estilo_visual_nuevo.py -v`
Expected: all 4 tests PASS.

- [x] **Step 8: Run the full test suite to check for regressions**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/ -v`
Expected: all tests PASS (pre-existing + all added in Tasks 1-8).

- [x] **Step 9: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_estilo_visual_nuevo.py"
git commit -m "feat(analisis-financiero): estilo visual para columnas Cliente/Nota y hojas Clientes/Glosario KPIs"
```

---

### Task 9: Integrar todo en `ejecutar()`/`main()` + tests de integración

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py:426-518` (`ejecutar`, `main`)
- Test: Create `Sistema Analisis Financiero/Sistema/tests/test_ejecutar_nota_clientes.py`

**Interfaces:**
- Consumes: `asegurar_columna_cliente` (Task 3), `asegurar_hoja_clientes` (Task 6), `asegurar_hoja_glosario_kpis` (Task 7), `RUTA_CLIENTES_PENDIENTES` (Task 3, as the new parameter's default).
- Produces: `ejecutar()` gains a 5th parameter `ruta_clientes_pendientes: Path = RUTA_CLIENTES_PENDIENTES` (inserted before `dry_run`); its `resumen` dict gains key `"clientes_pendientes": list[dict]`. This is the last task that touches `analisis_financiero.py`'s core flow — no downstream task depends on new names here.

- [x] **Step 1: Write the failing tests**

Create `Sistema Analisis Financiero/Sistema/tests/test_ejecutar_nota_clientes.py`:

```python
import json

import openpyxl

import analisis_financiero as af


def _armar_centro_costos(tmp_path):
    """Centro de Costos.xlsx mínimo con una hoja 'Detalle' vacía -- basta
    para que ejecutar() no aborte por archivo faltante."""
    ruta_cc = tmp_path / "Centro de Costos.xlsx"
    wb_cc = openpyxl.Workbook()
    ws = wb_cc.active
    ws.title = "Detalle"
    ws.append(["N° Ref.", "Proyecto", "Tipo de Proyecto", "N° Documento",
               "Nombre Ítem", "Descripción", "Categoría Ítem", "Cantidad",
               "P. Unitario sin IVA", "Total sin IVA (CLP)", "Total con IVA (CLP)"])
    wb_cc.save(ruta_cc)
    return ruta_cc


def test_ejecutar_completa_cliente_y_genera_hojas_clientes_y_glosario(tmp_path):
    ruta_af = tmp_path / "Análisis de Proyectos.xlsx"
    ruta_cc = _armar_centro_costos(tmp_path)
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb = af.asegurar_estructura_workbook(ruta_af)
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="AGCI1")
    ws.cell(row=2, column=2, value="AGCID Febrero")
    ws.cell(row=2, column=6, value=1_000_000)
    wb.save(ruta_af)

    resumen = af.ejecutar(
        ruta_excel_af=ruta_af,
        ruta_excel_cc=ruta_cc,
        raiz_facturas_cc=tmp_path / "Facturas y Boletas",
        raiz_respaldos=tmp_path / "Respaldos",
        ruta_clientes_pendientes=ruta_pendientes,
    )

    assert resumen["error"] is None
    wb_final = openpyxl.load_workbook(ruta_af)
    ws_proyectos = wb_final[af.HOJA_PROYECTOS]
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1
    assert ws_proyectos.cell(row=2, column=col_cliente).value == "AGCID Febrero"

    ws_clientes = wb_final[af.HOJA_CLIENTES]
    assert ws_clientes.cell(row=2, column=1).value == "AGCID Febrero"

    ws_glosario = wb_final[af.HOJA_GLOSARIO_KPIS]
    assert ws_glosario.max_row == 1 + len(af.GLOSARIO_KPIS)


def test_resumen_incluye_clientes_pendientes_nuevos(tmp_path):
    ruta_af = tmp_path / "Análisis de Proyectos.xlsx"
    ruta_cc = _armar_centro_costos(tmp_path)
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb = af.asegurar_estructura_workbook(ruta_af)
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="AGCI1")
    ws.cell(row=2, column=2, value="AGCID Febrero")
    ws.cell(row=3, column=1, value="AGCI2")
    ws.cell(row=3, column=2, value="AGCID Marzo")
    wb.save(ruta_af)

    resumen = af.ejecutar(
        ruta_excel_af=ruta_af,
        ruta_excel_cc=ruta_cc,
        raiz_facturas_cc=tmp_path / "Facturas y Boletas",
        raiz_respaldos=tmp_path / "Respaldos",
        ruta_clientes_pendientes=ruta_pendientes,
    )

    assert len(resumen["clientes_pendientes"]) == 1
    assert resumen["clientes_pendientes"][0]["tag"] == "AGCI2"
    assert ruta_pendientes.exists()


def test_dry_run_no_escribe_clientes_pendientes_json(tmp_path):
    ruta_af = tmp_path / "Análisis de Proyectos.xlsx"
    ruta_cc = _armar_centro_costos(tmp_path)
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb = af.asegurar_estructura_workbook(ruta_af)
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="AGCI1")
    ws.cell(row=2, column=2, value="AGCID Febrero")
    ws.cell(row=3, column=1, value="AGCI2")
    ws.cell(row=3, column=2, value="AGCID Marzo")
    wb.save(ruta_af)

    af.ejecutar(
        ruta_excel_af=ruta_af,
        ruta_excel_cc=ruta_cc,
        raiz_facturas_cc=tmp_path / "Facturas y Boletas",
        raiz_respaldos=tmp_path / "Respaldos",
        ruta_clientes_pendientes=ruta_pendientes,
        dry_run=True,
    )

    assert not ruta_pendientes.exists()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_ejecutar_nota_clientes.py -v`
Expected: FAIL — `resumen["clientes_pendientes"]` raises `KeyError`, "Clientes"/"Glosario KPIs" sheets stay empty (columns/functions not called yet from `ejecutar()`).

- [x] **Step 3: Wire the new steps into `ejecutar()`**

In `analisis_financiero.py`, `ejecutar()`'s signature currently is:

```python
def ejecutar(
    ruta_excel_af: Path = RUTA_EXCEL,
    ruta_excel_cc: Path = RUTA_EXCEL_CENTRO_COSTOS,
    raiz_facturas_cc: Path = RAIZ_FACTURAS_CENTRO_COSTOS,
    raiz_respaldos: Path = RAIZ_RESPALDOS,
    dry_run: bool = False,
) -> dict:
```

Replace it with (new parameter `ruta_clientes_pendientes`, following the same
"every path is an explicit parameter with a module-level default" convention
as the other 4 paths, so tests can override it directly instead of
monkeypatching module globals):

```python
def ejecutar(
    ruta_excel_af: Path = RUTA_EXCEL,
    ruta_excel_cc: Path = RUTA_EXCEL_CENTRO_COSTOS,
    raiz_facturas_cc: Path = RAIZ_FACTURAS_CENTRO_COSTOS,
    raiz_respaldos: Path = RAIZ_RESPALDOS,
    ruta_clientes_pendientes: Path = RUTA_CLIENTES_PENDIENTES,
    dry_run: bool = False,
) -> dict:
```

Then replace the initial `resumen = {...}` line:

```python
    resumen = {
        "avisos": [], "carpetas_creadas": [], "categorias_no_mapeadas": [],
        "clientes_pendientes": [], "error": None,
    }
```

And replace the block that currently reads:

```python
    asegurar_formulas_proyectos(ws_proyectos, filas_validas)
    asegurar_hoja_indicadores(wb, filas_validas)
    aplicar_estilo_visual(wb)
```

with:

```python
    resumen["clientes_pendientes"] = asegurar_columna_cliente(
        ws_proyectos, filas_validas, ruta_clientes_pendientes
    )

    asegurar_formulas_proyectos(ws_proyectos, filas_validas)
    asegurar_hoja_indicadores(wb, filas_validas)
    asegurar_hoja_clientes(wb, filas_validas, ws_proyectos)
    asegurar_hoja_glosario_kpis(wb)
    aplicar_estilo_visual(wb)
```

(This block sits after the `if dry_run: ... return resumen` branch, so
`asegurar_columna_cliente`'s JSON write never runs in dry-run mode —
satisfying the Global Constraint.)

- [x] **Step 4: Report pending clients in `main()`**

In `analisis_financiero.py`, inside `main()`, right after the existing `if resumen["categorias_no_mapeadas"]:` block, add:

```python
    if resumen["clientes_pendientes"]:
        print(
            f"[AVISO] {len(resumen['clientes_pendientes'])} cliente(s) nuevo(s) parecido(s) "
            "a uno existente -- revisar con 'python driver.py confirmar-cliente'."
        )
```

- [x] **Step 5: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_ejecutar_nota_clientes.py -v`
Expected: all 3 tests PASS.

- [x] **Step 6: Run the full test suite**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/ -v`
Expected: all tests PASS — no regressions in `test_ejecutar.py` or any other pre-existing file.

- [x] **Step 7: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_ejecutar_nota_clientes.py"
git commit -m "feat(analisis-financiero): integrar Cliente/CLTV/Glosario KPIs al flujo de ejecutar()"
```

---

### Task 10: Documentación — `SKILL.md`, `CLAUDE.md`, `MEMORY.md`

**Files:**
- Modify: `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md`
- Modify: `Sistema Analisis Financiero/CLAUDE.md`
- Modify: `Sistema Analisis Financiero/MEMORY.md`

No tests — documentation only. This task has no interfaces for other tasks to consume; it is a leaf.

- [x] **Step 1: Document the new command in `SKILL.md`**

In `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md`, after the existing `run` section (ends around line 42, before `## Gotchas`), add:

```markdown
**`confirmar-cliente`** -- confirma clientes marcados "Pendiente de revisión"
(fuente roja en la columna "Cliente" de "Proyectos"): sin argumentos, solo
lista los pendientes; `--todos` aplica la sugerencia de todos; una lista de
TAGs aplica solo esos. Recolorea la celda a azul marino y marca la entrada
como "Confirmado" en `Sistema/clientes_pendientes.json`.

```
python ".claude/skills/Registro_Analisis_Financiero/driver.py" confirmar-cliente
python ".claude/skills/Registro_Analisis_Financiero/driver.py" confirmar-cliente --todos
```

Si la sugerencia automática no es el cliente correcto, edita
`cliente_sugerido` en `Sistema/clientes_pendientes.json` antes de confirmar
(mismo patrón que `correcciones_manuales.json` de Centro de Costos).
```

Then update the `description:` line in the YAML frontmatter (line 3) to also mention the new capabilities:

```yaml
description: Consolida los costos reales por proyecto y categoría desde Centro de Costos hacia Análisis de Proyectos.xlsx (hojas Proyectos/Detalle Costos Reales/Indicadores/Clientes/Glosario KPIs), calcula la Nota del Proyecto (0-100) y el CLTV por cliente, y crea la carpeta de facturas para proyectos nuevos agregados a mano en el Excel. Usar cuando el usuario pida actualizar Análisis Financiero, refrescar los indicadores de proyectos, ver el estado de Análisis de Proyectos.xlsx, evaluar rentabilidad/KPIs de un proyecto, o revisar/confirmar un cliente detectado como similar a uno existente.
```

- [x] **Step 2: Update the module schema summary in `CLAUDE.md`**

In `Sistema Analisis Financiero/CLAUDE.md`, in the `## Análisis de Proyectos.xlsx — resumen del esquema` section, replace the 3-sheet description with a 5-sheet one — after the existing bullet for "Detalle Costos Reales", add:

```markdown
- **"Clientes"** (una fila por cliente único, detectado desde la columna
  "Cliente" de "Proyectos"): AOV, Vida del cliente, Meses activo, Frecuencia
  de compra, Margen de utilidad %, CLTV y Clasificación (percentil) — 100%
  fórmulas agregando sobre "Proyectos". La columna "Cliente" se completa
  sola (derivación + fuzzy-match contra clientes ya registrados); si hay
  duda queda "Pendiente de revisión" (fuente roja), confirmable con
  `python driver.py confirmar-cliente`.
- **"Glosario KPIs"** (una fila por KPI del libro): por qué importa, qué
  elementos usa, qué significa el resultado — texto estático, se reescribe
  completo en cada corrida.
```

And in the "Playbook de KPIs" table, add two rows:

```markdown
| Nota del Proyecto (0-100) | 70% margen neto % (vs. objetivo 25%) + 30% control de desviación total |
| CLTV (hoja Clientes) | AOV × Frecuencia de compra × Vida del cliente × Margen de utilidad % |
```

Update the "## Estado actual" date/summary line to note this extension, e.g. append a new paragraph:

```markdown
**Extensión 2026-07-21**: agregadas Nota del Proyecto, columna "Cliente" +
hoja "Clientes" (CLTV) y hoja "Glosario KPIs" — ver
[`docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md`](../docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md)
y el plan de implementación
[`docs/superpowers/plans/2026-07-21-analisis-financiero-nota-clientes-implementacion.md`](../docs/superpowers/plans/2026-07-21-analisis-financiero-nota-clientes-implementacion.md).
```

- [x] **Step 3: Record the decision history in `MEMORY.md`**

In `Sistema Analisis Financiero/MEMORY.md`, add a new section before "## Pendientes que dependen del usuario":

```markdown
## Nota de Proyecto, CLTV de Clientes y Glosario KPIs (brainstorming, 2026-07-21)

- **"Nota" es 100% automática** (no manual, no híbrida) — decisión explícita
  del usuario tras preguntarle las 3 opciones. Escala 0-100, aprobatoria
  ≥55, rentabilidad domina el peso (70% margen neto % vs. objetivo 25%, 30%
  control de desviación total).
- **"CLTV" es sobre CLIENTES, no proveedores** — el usuario pidió
  proveedores primero (confundiendo con el "Proveedor" de Centro de Costos,
  que es un dato de COSTOS/compras) y corrigió a mitad del brainstorming: lo
  que quería era evaluar a quién QUEMPIN le VENDE (clientes), usando el
  archivo de ejemplo AGORA (CLTV por proyecto) como referencia. Si en el
  futuro se pide "evaluar proveedores", es un feature DISTINTO y nuevo, no
  este.
- **"Cliente" se deriva automáticamente + fuzzy-match**, nunca pregunta en
  vivo (el módulo corre encadenado y no bloqueante al `run` de Centro de
  Costos) — coincidencia exacta se asigna sola, similar-no-exacta queda
  "Pendiente de revisión" (mismo patrón rojo/azul marino que Centro de
  Costos), sin parecido se registra como cliente nuevo sin marca.
- **Ambigüedad resuelta del archivo de ejemplo AGORA**: "Vida del cliente" y
  "Frecuencia de compra" del archivo original mezclaban conceptos sin
  fórmula consistente entre filas — este módulo define "Vida del cliente" =
  conteo total de proyectos, "Meses activo" = ventana entre el primer y
  último proyecto (mínimo 1 mes), "Frecuencia" = Vida ÷ (Meses activo ÷ 12).
  Verificado aritméticamente contra los totales del archivo de ejemplo
  (`CLTV = AOV × Frecuencia × Vida × Margen` reproduce el CLTV total como
  promedio simple de los CLTV individuales).
- **Glosario KPIs es una hoja nueva, no comentarios de celda** — a pedido
  explícito del usuario ("que elementos utiliza y en qué se traduce"),
  elegido sobre comentarios de encabezado por ser más legible de corrido y
  más simple de mantener en openpyxl.
- **KPIs adicionales que el usuario mencionó querer agregar después
  quedaron fuera de este spec a propósito** — decisión explícita de cerrar
  este diseño primero en vez de mezclar alcance con features aún sin
  definir.

Diseño completo:
[`docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md`](../docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md)
(ruta relativa a la raíz de `Finanzas QUEMPIN/`).
```

- [x] **Step 4: Commit**

```bash
git add "Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/SKILL.md" "Sistema Analisis Financiero/CLAUDE.md" "Sistema Analisis Financiero/MEMORY.md"
git commit -m "docs(analisis-financiero): documentar Nota de Proyecto, CLTV de Clientes y Glosario KPIs"
```

---

## Fuera de alcance de este plan (ver spec §"Fuera de alcance")

- Ajustar el margen objetivo (25%) o los pesos (70/30) de la Nota contra
  datos reales de QUEMPIN — pendiente hasta que haya proyectos reales
  cargados en `Análisis de Proyectos.xlsx`.
- Nuevos KPIs adicionales mencionados por el usuario tras cerrar este
  diseño — requieren su propia ronda de brainstorming.
- Dashboard HTML de presentación.
