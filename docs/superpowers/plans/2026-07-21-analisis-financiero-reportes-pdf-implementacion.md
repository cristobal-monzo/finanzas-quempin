# Reportes PDF de Análisis Financiero — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir la infraestructura reutilizable (kit de marca QUEMPIN, motor
HTML→PDF, paquetes de datos de solo lectura, detección de obsolescencia, y un
nuevo skill) que le permite al agente `analista-financiero-quempin` redactar y
generar PDFs de análisis financiero por proyecto, por cliente, por categoría, y
comparaciones ad-hoc bajo demanda — implementando
[`docs/superpowers/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md`](../specs/2026-07-21-analisis-financiero-reportes-pdf-design.md).

**Architecture:** Nueva carpeta `Sistema Analisis Financiero/Reportes/` con 5
módulos de responsabilidad única (kit de marca + gráficos SVG, motor de
render PDF, paquetes de datos, manifiesto de obsolescencia, skill), más una
columna nueva ("Categoría") en `Sistema/analisis_financiero.py`. El contenido
real de cada reporte lo redacta el agente en conversación — este plan solo
construye la infraestructura determinística que el agente usa, nunca el
contenido en sí (eso no es testeable de forma determinística, ver spec §7).

**Tech Stack:** Python 3.14, openpyxl (ya en uso), `playwright` (nuevo —
Chromium headless para HTML→PDF, reutiliza el binario ya cacheado en
`%LOCALAPPDATA%\ms-playwright\chromium-1228`), pytest.

## Global Constraints

- **Nunca escribir `Centro de Costos.xlsx`** — todo acceso a ese archivo es
  de solo lectura, igual que el resto del módulo.
- **Columnas nuevas siempre al final** de los headers existentes (`HEADERS_PROYECTOS`,
  etc.) — nunca intercaladas, para no correr las letras de columna que ya usan
  fórmulas/estilos existentes.
- **Kit de marca**: únicamente los 4 colores oficiales `#ff5100` (Pantone
  Orange 021 C), `#000000` (Black C), `#98989a` (Cool Gray 7 C), `#54565a`
  (Cool Gray 11 C) y la tipografía Lato — nunca inventar paleta ni tipografía
  nueva. La fuente Lato (embebida en base64) y el logo se **reextraen en
  tiempo de ejecución** desde `Centro de Costos/Visualizador Web/template.html`
  (no se copian a mano ni se re-embeben archivos binarios nuevos).
- **Sin generación de contenido automática/no supervisada**: el manifiesto de
  obsolescencia (`estado_reportes.py`) solo detecta y marca reportes
  pendientes — nunca dispara redacción ni renderizado por sí solo.
- **PDFs se guardan en** `Análisis Financiero/Reportes/{Proyectos,Clientes,Categorías,Comparativas}/`.
- **Sin reporte si faltan datos manuales**: un proyecto sin todos sus campos
  manuales requeridos (`Estado`, `Fecha de inicio`, `Monto de Venta (sin
  IVA)`, los 4 costos proyectados, `Mano de Obra Real`) no genera ningún
  reporte propio y se excluye de los agregados de cliente/categoría —
  `Fecha de cierre` queda explícitamente fuera de este chequeo (ver punto
  siguiente).
- **Proyectos "en desarrollo"**: sin `Fecha de cierre`, o con una fecha
  posterior a la fecha real actual, el proyecto sí genera reporte (si el
  resto de sus datos está completo) pero marcado `en_desarrollo: true` para
  que el agente incluya un indicador visual explícito.
- **✅ Prerrequisito resuelto (2026-07-21):** el plan de Cliente/CLTV
  (`docs/superpowers/plans/2026-07-21-analisis-financiero-nota-clientes-implementacion.md`)
  ya está completamente ejecutado y mergeado en `master` (commits
  `db070a9`..`ff95f6d`). **Con una diferencia importante frente al spec
  original**: la implementación real puso `"Cliente"` como **3ª columna**
  de `HEADERS_PROYECTOS` (después de `"Nombre del proyecto"`, antes de
  `"Estado"`), no al final como se planeaba — y agregó un dict
  `LETRA_COL_PROYECTOS = {nombre_columna: letra}` (vía
  `openpyxl.utils.get_column_letter`) que las fórmulas usan para no
  hardcodear letras nunca. Las Tareas 1 y 4 de este plan ya están escritas
  contra el orden real de columnas (verificado en `master` antes de
  redactarlas) — sigue usando `HEADERS_PROYECTOS.index(nombre) + 1` o
  `LETRA_COL_PROYECTOS[nombre]` en vez de números de columna hardcodeados,
  igual que el resto del archivo.

---

## Task 1: Columna "Categoría" automática en "Proyectos"

**Files:**
- Modify: `Sistema Analisis Financiero/Sistema/analisis_financiero.py`
- Test: `Sistema Analisis Financiero/Sistema/tests/test_categoria_proyecto.py` (create)

**Interfaces:**
- Consumes: `HOJA_PROYECTOS`, `RUTA_EXCEL_CENTRO_COSTOS`, `leer_filas_proyectos(ws) -> tuple[list[dict], list[str]]` (cada dict tiene claves `fila`, `tag`, `nombre`), `prefijo_de_n_ref(n_ref: str) -> str` — ya existentes en el archivo.
- Produces: `leer_tipo_proyecto_centro_costos(ruta_excel_cc: Path) -> dict[str, str]` (prefijo → tipo_proyecto más frecuente), `asegurar_categoria_proyectos(ws_proyectos, filas_validas: list[dict], categoria_por_prefijo: dict[str, str], columna: int) -> list[str]` (avisos). `HEADERS_PROYECTOS` con `"Categoría"` agregada **al final** de la lista real actual (verificado en `master`: 20 encabezados, terminando en `"Desviación % (Real vs Proyectado)"` — `"Cliente"` ya quedó como 3ª columna, no al final; `"Categoría"` sí se agrega al final porque es la única columna nueva que aporta este plan). Nunca hardcodear el número de columna — siempre `HEADERS_PROYECTOS.index("Categoría") + 1` (o el parámetro `columna` recibido).

- [ ] **Step 1: Write the failing tests**

```python
# -*- coding: utf-8 -*-
import openpyxl

import analisis_financiero as af


def _crear_excel_cc_con_tipo_proyecto(tmp_path, filas):
    """filas: lista de tuplas (n_ref, tipo_proyecto)"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Master"
    encabezados = [
        "N° Ref.", "Proyecto", "Tipo de Proyecto", "Fecha", "N° Documento",
        "Tipo Documento", "Proveedor", "Proveedor (Razón Social)", "Categoría",
        "Resumen Ítems", "Total sin IVA (CLP)", "IVA 19% (CLP)",
        "Total con IVA (CLP)", "Estado", "Archivo origen", "Fecha modificación",
    ]
    for col, encabezado in enumerate(encabezados, start=1):
        ws.cell(row=1, column=col, value=encabezado)
    for fila_idx, (n_ref, tipo_proyecto) in enumerate(filas, start=2):
        ws.cell(row=fila_idx, column=1, value=n_ref)
        ws.cell(row=fila_idx, column=3, value=tipo_proyecto)
    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(ruta)
    return ruta


def test_leer_tipo_proyecto_lee_un_solo_valor_por_proyecto(tmp_path):
    ruta = _crear_excel_cc_con_tipo_proyecto(tmp_path, [
        ("UMAG-001", "I+D+i"),
        ("UMAG-002", "I+D+i"),
        ("CFLI-001", "Mantenimiento"),
    ])
    assert af.leer_tipo_proyecto_centro_costos(ruta) == {
        "UMAG": "I+D+i",
        "CFLI": "Mantenimiento",
    }


def test_leer_tipo_proyecto_usa_el_mas_frecuente_si_hay_inconsistencia(tmp_path):
    ruta = _crear_excel_cc_con_tipo_proyecto(tmp_path, [
        ("UMAG-001", "I+D+i"),
        ("UMAG-002", "I+D+i"),
        ("UMAG-003", "Mantenimiento"),
    ])
    assert af.leer_tipo_proyecto_centro_costos(ruta) == {"UMAG": "I+D+i"}


def test_leer_tipo_proyecto_ignora_filas_sin_tipo(tmp_path):
    ruta = _crear_excel_cc_con_tipo_proyecto(tmp_path, [
        ("UMAG-001", None),
        ("UMAG-002", "I+D+i"),
    ])
    assert af.leer_tipo_proyecto_centro_costos(ruta) == {"UMAG": "I+D+i"}


def test_asegurar_categoria_proyectos_escribe_valor_y_avisa_si_falta(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Proyectos"
    ws.cell(row=1, column=1, value="TAG proyecto")
    ws.cell(row=2, column=1, value="UMAG")
    ws.cell(row=3, column=1, value="MLER")
    col_categoria = 5  # columna arbitraria de prueba, no depende del archivo real
    filas_validas = [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 3, "tag": "MLER", "nombre": "Microturbina LER"},
    ]
    avisos = af.asegurar_categoria_proyectos(
        ws, filas_validas, {"UMAG": "I+D+i"}, columna=col_categoria,
    )
    assert ws.cell(row=2, column=col_categoria).value == "I+D+i"
    assert ws.cell(row=3, column=col_categoria).value is None
    assert len(avisos) == 1
    assert "MLER" in avisos[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_categoria_proyecto.py -v`
Expected: FAIL — `AttributeError: module 'analisis_financiero' has no attribute 'leer_tipo_proyecto_centro_costos'`
(4 tests en total: 3 de `leer_tipo_proyecto_centro_costos` + 1 de `asegurar_categoria_proyectos`)

- [ ] **Step 3: Add `leer_tipo_proyecto_centro_costos` and `asegurar_categoria_proyectos`**

En `Sistema Analisis Financiero/Sistema/analisis_financiero.py`, agregar
después de `leer_detalle_centro_costos` (usa `Counter` de `collections`,
agregar el import junto a los demás al inicio del archivo):

```python
from collections import Counter

def leer_tipo_proyecto_centro_costos(ruta_excel_cc: Path) -> dict[str, str]:
    """Lee la hoja 'Master' de Centro de Costos.xlsx (SOLO LECTURA) y devuelve,
    por prefijo de proyecto, el 'Tipo de Proyecto' más frecuente entre sus
    documentos. Filas sin N° Ref. o sin Tipo de Proyecto se ignoran."""
    wb = openpyxl.load_workbook(ruta_excel_cc, data_only=True)
    ws = wb["Master"]
    encabezados = [celda.value for celda in ws[1]]
    col_n_ref = encabezados.index("N° Ref.") + 1
    col_tipo = encabezados.index("Tipo de Proyecto") + 1

    tipos_por_prefijo: dict[str, Counter] = {}
    for fila in ws.iter_rows(min_row=2):
        n_ref = fila[col_n_ref - 1].value
        tipo = fila[col_tipo - 1].value
        if not n_ref or not tipo:
            continue
        prefijo = prefijo_de_n_ref(n_ref)
        tipos_por_prefijo.setdefault(prefijo, Counter())[tipo] += 1

    return {
        prefijo: contador.most_common(1)[0][0]
        for prefijo, contador in tipos_por_prefijo.items()
    }


def asegurar_categoria_proyectos(
    ws_proyectos, filas_validas: list[dict], categoria_por_prefijo: dict[str, str],
    columna: int,
) -> list[str]:
    """Escribe la 'Categoría' de cada fila válida (columna indicada por
    'columna' -- quien llama la calcula desde HEADERS_PROYECTOS, nunca
    hardcodeada acá) desde categoria_por_prefijo -- valor plano, no fórmula
    (no hay agregación posible, es un lookup 1 a 1). Si un proyecto no tiene
    ningún documento en Centro de Costos todavía, no escribe nada y avisa."""
    avisos = []
    for fila_info in filas_validas:
        prefijo = fila_info["tag"]
        categoria = categoria_por_prefijo.get(prefijo)
        if categoria is None:
            avisos.append(
                f"Proyecto '{fila_info['nombre']}' ({prefijo}) sin documentos en "
                f"Centro de Costos todavía -- Categoría queda vacía."
            )
            continue
        ws_proyectos.cell(row=fila_info["fila"], column=columna, value=categoria)
    return avisos
```

Extender `HEADERS_PROYECTOS` agregando `"Categoría"` al final de la lista
real actual (después de `"Desviación % (Real vs Proyectado)"` — la lista
real hoy tiene 20 encabezados con `"Cliente"` ya como 3ª columna, agregada
por el plan de Cliente/CLTV; `"Categoría"` pasa a ser el 21°).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest tests/test_categoria_proyecto.py -v`
Expected: PASS (5 tests — borra el placeholder inerte del Step 1 antes de correr, o falla por sintaxis)

- [ ] **Step 5: Wire into `ejecutar()`**

En `ejecutar()`, después de la llamada a `asegurar_formulas_proyectos(ws_proyectos, filas_validas)`
y antes de `asegurar_hoja_indicadores(wb, filas_validas)`, agregar:

```python
    tipos_por_prefijo = leer_tipo_proyecto_centro_costos(ruta_excel_cc)
    col_categoria = HEADERS_PROYECTOS.index("Categoría") + 1
    resumen["avisos"].extend(
        asegurar_categoria_proyectos(ws_proyectos, filas_validas, tipos_por_prefijo, col_categoria)
    )
```

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest -v`
Expected: PASS — todos los tests existentes siguen pasando, más los 4 nuevos.

- [ ] **Step 7: Commit**

```bash
git add "Sistema Analisis Financiero/Sistema/analisis_financiero.py" "Sistema Analisis Financiero/Sistema/tests/test_categoria_proyecto.py"
git commit -m "feat(analisis-financiero): columna Categoria automatica desde Centro de Costos"
```

---

## Task 2: Kit de marca (CSS/logo/tipografía) y gráficos SVG

**Files:**
- Create: `Sistema Analisis Financiero/Reportes/brand.py`
- Create: `Sistema Analisis Financiero/Reportes/graficos.py`
- Test: `Sistema Analisis Financiero/Reportes/tests/test_brand.py` (create)
- Test: `Sistema Analisis Financiero/Reportes/tests/test_graficos.py` (create)
- Create: `Sistema Analisis Financiero/Reportes/tests/conftest.py`

**Interfaces:**
- Produces: `brand.cargar_font_face_lato() -> str`, `brand.cargar_logo_base64() -> str`,
  `brand.construir_html(titulo: str, generado_el: str, contenido_html: str) -> str`,
  `graficos.grafico_barras_svg(etiquetas: list[str], valores: list[float], color: str = "#ff5100") -> str`,
  `graficos.grafico_dona_svg(etiquetas: list[str], valores: list[float], colores: list[str] | None = None) -> str`.
  Estas cuatro funciones son las que consumirá el agente (vía `datos_reportes.py`
  y directamente) para armar el HTML de cada reporte en tareas posteriores.

- [ ] **Step 1: Write the failing tests**

`Sistema Analisis Financiero/Reportes/tests/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

`Sistema Analisis Financiero/Reportes/tests/test_brand.py`:

```python
import brand


def test_cargar_font_face_lato_trae_las_3_variantes():
    css = brand.cargar_font_face_lato()
    assert css.count("@font-face") == 3
    assert "font-family: 'Lato'" in css


def test_cargar_logo_base64_es_un_data_uri_png():
    logo = brand.cargar_logo_base64()
    assert logo.startswith("data:image/png;base64,")
    assert len(logo) > 1000


def test_construir_html_incluye_titulo_logo_y_contenido():
    html = brand.construir_html(
        titulo="Reporte UMAG",
        generado_el="21/07/2026",
        contenido_html="<p>contenido de prueba</p>",
    )
    assert html.startswith("<!doctype html>")
    assert "Reporte UMAG" in html
    assert "data:image/png;base64," in html
    assert "<p>contenido de prueba</p>" in html
    assert "@font-face" in html
    assert "#ff5100" in html
```

`Sistema Analisis Financiero/Reportes/tests/test_graficos.py`:

```python
import pytest

import graficos


def test_grafico_barras_svg_produce_una_barra_por_valor():
    svg = graficos.grafico_barras_svg(["UMAG", "CFLI"], [100000, 50000])
    assert svg.count("<rect") == 2
    assert svg.startswith("<svg")


def test_grafico_barras_svg_valida_longitudes_distintas():
    with pytest.raises(ValueError):
        graficos.grafico_barras_svg(["UMAG"], [100000, 50000])


def test_grafico_barras_svg_valida_lista_vacia():
    with pytest.raises(ValueError):
        graficos.grafico_barras_svg([], [])


def test_grafico_dona_svg_produce_un_segmento_por_valor():
    svg = graficos.grafico_dona_svg(["Materiales", "Equipos", "Otros"], [50, 30, 20])
    assert svg.count("<path") == 3
    assert svg.startswith("<svg")


def test_grafico_dona_svg_valida_suma_cero():
    with pytest.raises(ValueError):
        graficos.grafico_dona_svg(["A", "B"], [0, 0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'brand'` / `'graficos'`

- [ ] **Step 3: Implement `brand.py`**

```python
# -*- coding: utf-8 -*-
"""
brand.py -- Kit de marca QUEMPIN para reportes PDF. Reextrae en tiempo de
ejecucion la tipografia Lato (embebida en base64) y el logo desde
Centro de Costos/Visualizador Web/template.html, que ya los extrajo del
manual oficial (Material grafico QUEMPIN/OFICIAL MANUAL DE MARCA GRAFICA
QUEMPIN.pdf) -- evita reincrustar archivos binarios nuevos y se mantiene
sincronizado si ese template cambia. Los 4 colores oficiales si se
hardcodean acá (son valores triviales, ya usados en 2+ lugares del repo).
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent
RUTA_TEMPLATE_CC = (
    RAIZ.parent.parent / "Centro de Costos" / "Visualizador Web" / "template.html"
)

COLOR_NARANJO = "#ff5100"      # Pantone Orange 021 C
COLOR_NEGRO = "#000000"        # Black C
COLOR_GRIS_CLARO = "#98989a"   # Cool Gray 7 C
COLOR_GRIS_OSCURO = "#54565a"  # Cool Gray 11 C

CSS_COLORES = f"""
:root {{
  --brand-orange: {COLOR_NARANJO};
  --brand-black: {COLOR_NEGRO};
  --brand-gray-light: {COLOR_GRIS_CLARO};
  --brand-gray-dark: {COLOR_GRIS_OSCURO};
}}
"""

CSS_BASE_REPORTE = """
body { font-family: 'Lato', system-ui, sans-serif; color: var(--brand-black); margin: 0; }
.reporte-header { display: flex; align-items: center; gap: 16px; padding: 24px 32px; border-bottom: 3px solid var(--brand-orange); }
.reporte-logo { height: 48px; }
.reporte-titulos h1 { margin: 0; font-size: 22px; }
.reporte-fecha { margin: 4px 0 0; color: var(--brand-gray-dark); font-size: 12px; }
.reporte-contenido { padding: 24px 32px; }
.kpi-fila { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
.kpi-tarjeta { flex: 1 1 160px; border: 1px solid var(--brand-gray-light); border-radius: 8px; padding: 12px 16px; }
.kpi-tarjeta .valor { font-size: 24px; font-weight: 900; color: var(--brand-orange); }
.kpi-tarjeta .etiqueta { font-size: 12px; color: var(--brand-gray-dark); }
table.tabla-reporte { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
table.tabla-reporte th, table.tabla-reporte td { border: 1px solid var(--brand-gray-light); padding: 6px 10px; font-size: 12px; text-align: right; }
table.tabla-reporte th { background: var(--brand-black); color: white; text-align: left; }
table.tabla-reporte td:first-child, table.tabla-reporte th:first-child { text-align: left; }
.reporte-footer { padding: 12px 32px; font-size: 10px; color: var(--brand-gray-dark); border-top: 1px solid var(--brand-gray-light); }
"""

PLANTILLA_DOCUMENTO = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{titulo}</title>
<style>
{css}
</style>
</head>
<body>
<header class="reporte-header">
  <img src="{logo}" alt="QUEMPIN" class="reporte-logo">
  <div class="reporte-titulos">
    <h1>{titulo}</h1>
    <p class="reporte-fecha">Generado el {generado_el}</p>
  </div>
</header>
<main class="reporte-contenido">
{contenido}
</main>
<footer class="reporte-footer">QUEMPIN SpA -- Analisis Financiero</footer>
</body>
</html>"""


def cargar_font_face_lato() -> str:
    """Extrae las 3 reglas @font-face (Lato 400/700/900, base64) desde el
    template del visualizador de Centro de Costos."""
    texto = RUTA_TEMPLATE_CC.read_text(encoding="utf-8")
    bloques = []
    pos = 0
    for _ in range(3):
        inicio = texto.index("@font-face", pos)
        fin = texto.index("}", inicio) + 1
        bloques.append(texto[inicio:fin])
        pos = fin
    return "\n".join(bloques)


def cargar_logo_base64() -> str:
    """Extrae el data URI completo del logo (data:image/png;base64,...) desde
    el header (.viz-logo) del template del visualizador de Centro de Costos."""
    texto = RUTA_TEMPLATE_CC.read_text(encoding="utf-8")
    marcador = 'class="viz-logo">'
    i = texto.index(marcador)
    inicio_src = texto.index('src="data:image/png;base64,', i) + len('src="')
    fin_src = texto.index('"', inicio_src)
    return texto[inicio_src:fin_src]


def construir_html(titulo: str, generado_el: str, contenido_html: str) -> str:
    """Envuelve contenido_html (redactado por el agente) en el documento
    completo con marca QUEMPIN -- header con logo, tipografia y colores
    oficiales, footer. contenido_html debe ser HTML ya armado (tarjetas de
    KPI, tablas, graficos SVG de graficos.py), no se procesa ni se valida."""
    css = CSS_COLORES + cargar_font_face_lato() + CSS_BASE_REPORTE
    return PLANTILLA_DOCUMENTO.format(
        titulo=titulo,
        css=css,
        logo=cargar_logo_base64(),
        generado_el=generado_el,
        contenido=contenido_html,
    )
```

- [ ] **Step 4: Implement `graficos.py`**

```python
# -*- coding: utf-8 -*-
"""
graficos.py -- Graficos SVG puros (sin JS, sin librerias externas) para
incrustar en reportes PDF. Pensados para imprimirse via Chromium headless
(motor_reportes.renderizar_pdf), no para interaccion.
"""

import math

COLORES_POR_DEFECTO = ["#ff5100", "#000000", "#98989a", "#54565a"]


def grafico_barras_svg(
    etiquetas: list[str], valores: list[float], color: str = "#ff5100",
    ancho: int = 480, alto: int = 220,
) -> str:
    """Grafico de barras horizontal simple. valores deben ser >= 0."""
    if not etiquetas or len(etiquetas) != len(valores):
        raise ValueError("etiquetas y valores deben tener la misma longitud y no estar vacios")

    max_valor = max(valores) or 1.0
    alto_barra = alto / len(valores)
    partes = []
    for i, (etiqueta, valor) in enumerate(zip(etiquetas, valores)):
        y = i * alto_barra + alto_barra * 0.15
        ancho_barra = (valor / max_valor) * (ancho - 160)
        partes.append(
            f'<text x="0" y="{y + alto_barra * 0.35:.1f}" font-size="11">{etiqueta}</text>'
            f'<rect x="150" y="{y:.1f}" width="{ancho_barra:.1f}" height="{alto_barra * 0.7:.1f}" fill="{color}"/>'
            f'<text x="{150 + ancho_barra + 6:.1f}" y="{y + alto_barra * 0.35:.1f}" font-size="11">{valor:,.0f}</text>'
        )
    return f'<svg viewBox="0 0 {ancho} {alto}" width="100%" xmlns="http://www.w3.org/2000/svg">{"".join(partes)}</svg>'


def grafico_dona_svg(
    etiquetas: list[str], valores: list[float], colores: list[str] | None = None,
    radio: int = 80,
) -> str:
    """Grafico de dona simple via arcos SVG calculados a mano. La suma de
    valores debe ser mayor que 0."""
    if not etiquetas or len(etiquetas) != len(valores):
        raise ValueError("etiquetas y valores deben tener la misma longitud y no estar vacios")
    total = sum(valores)
    if total <= 0:
        raise ValueError("la suma de valores debe ser mayor que 0")

    colores = colores or COLORES_POR_DEFECTO
    centro = radio + 10
    tam = centro * 2
    partes = []
    angulo_acum = -90.0
    for i, valor in enumerate(valores):
        angulo = (valor / total) * 360.0
        x1 = centro + radio * math.cos(math.radians(angulo_acum))
        y1 = centro + radio * math.sin(math.radians(angulo_acum))
        angulo_acum += angulo
        x2 = centro + radio * math.cos(math.radians(angulo_acum))
        y2 = centro + radio * math.sin(math.radians(angulo_acum))
        gran_arco = 1 if angulo > 180 else 0
        color = colores[i % len(colores)]
        partes.append(
            f'<path d="M{centro},{centro} L{x1:.2f},{y1:.2f} '
            f'A{radio},{radio} 0 {gran_arco} 1 {x2:.2f},{y2:.2f} Z" fill="{color}"/>'
        )
    return (
        f'<svg viewBox="0 0 {tam} {tam}" width="220" height="220" xmlns="http://www.w3.org/2000/svg">'
        f'{"".join(partes)}<circle cx="{centro}" cy="{centro}" r="{radio * 0.55:.1f}" fill="white"/></svg>'
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/ -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/Reportes/brand.py" "Sistema Analisis Financiero/Reportes/graficos.py" "Sistema Analisis Financiero/Reportes/tests/"
git commit -m "feat(analisis-financiero): kit de marca QUEMPIN y graficos SVG para reportes PDF"
```

---

## Task 3: Motor de renderizado PDF

**Files:**
- Create: `Sistema Analisis Financiero/Reportes/motor_reportes.py`
- Test: `Sistema Analisis Financiero/Reportes/tests/test_motor_reportes.py` (create)

**Interfaces:**
- Produces: `motor_reportes.renderizar_pdf(html: str, ruta_salida: Path) -> None`.
  Task 6 (skill) y el agente en conversación lo llaman con el HTML que arma
  `brand.construir_html`.

- [ ] **Step 1: Install playwright and verify the cached Chromium is reused**

Run: `pip install playwright`
Expected: instala el paquete Python (sin descargar navegador todavía).

Run: `python -m playwright install chromium`
Expected: si `%LOCALAPPDATA%\ms-playwright\chromium-1228` ya tiene la
revisión que este playwright espera, termina casi al instante sin descargar
nada (`chromium-1228 is already installed` o similar). Si pide descargar una
revisión distinta, déjalo descargar -- avisa igual en el reporte de la tarea,
no es un bloqueo.

- [ ] **Step 2: Write the failing test**

```python
# -*- coding: utf-8 -*-
import motor_reportes


def test_renderizar_pdf_produce_un_archivo_pdf_valido(tmp_path):
    html = "<html><body><h1>Prueba</h1></body></html>"
    destino = tmp_path / "sub" / "prueba.pdf"

    motor_reportes.renderizar_pdf(html, destino)

    assert destino.exists()
    assert destino.stat().st_size > 0
    assert destino.read_bytes()[:5] == b"%PDF-"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/test_motor_reportes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'motor_reportes'`

- [ ] **Step 4: Implement `motor_reportes.py`**

```python
# -*- coding: utf-8 -*-
"""
motor_reportes.py -- Imprime un documento HTML autocontenido (sin recursos
externos -- CSS/fuentes/imagenes ya embebidos por brand.construir_html) a PDF
via Chromium headless (playwright). No conoce el contenido del reporte, solo
lo renderiza.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright


def renderizar_pdf(html: str, ruta_salida: Path) -> None:
    """Crea las carpetas padre de ruta_salida si no existen y escribe el PDF
    ahi. Lanza la excepcion de playwright tal cual si el render falla (sin
    capturarla) -- quien llama decide como reportarlo."""
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        try:
            pagina = navegador.new_page()
            pagina.set_content(html, wait_until="networkidle")
            pagina.pdf(
                path=str(ruta_salida),
                format="A4",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
        finally:
            navegador.close()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/test_motor_reportes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/Reportes/motor_reportes.py" "Sistema Analisis Financiero/Reportes/tests/test_motor_reportes.py"
git commit -m "feat(analisis-financiero): motor de renderizado HTML a PDF via Chromium headless"
```

---

## Task 4: Paquetes de datos de reporte (proyecto/cliente/categoría/comparación)

**Files:**
- Create: `Sistema Analisis Financiero/Reportes/datos_reportes.py`
- Test: `Sistema Analisis Financiero/Reportes/tests/test_datos_reportes.py` (create)

**Interfaces:**
- Consumes: `RUTA_EXCEL`, `HOJA_PROYECTOS`, `HOJA_INDICADORES`, `HOJA_CLIENTES`
  desde `analisis_financiero` (import cruzado vía `sys.path`, mismo patrón que
  `Centro de Costos/Sistema/auditor_centro_costos.py:actualizar_analisis_financiero`).
- Produces: `DatosIncompletosError` (subclase de `ValueError`),
  `proyecto_tiene_datos_completos(proyecto: dict) -> bool`,
  `proyecto_esta_en_desarrollo(proyecto: dict, hoy: date | None = None) -> bool`,
  `paquete_datos_proyecto(ruta_excel: Path, tag: str) -> dict` (incluye clave
  `"en_desarrollo": bool`; lanza `DatosIncompletosError` si el proyecto no
  tiene todos sus campos manuales requeridos),
  `paquete_datos_cliente(ruta_excel: Path, nombre_cliente: str) -> dict`,
  `paquete_datos_categoria(ruta_excel: Path, categoria: str) -> dict` (ambas
  excluyen silenciosamente del agregado los proyectos incompletos, vía
  `proyecto_tiene_datos_completos`),
  `paquete_datos_comparacion(ruta_excel: Path, entidades: list[tuple[str, str]]) -> dict`
  (cada tupla es `(tipo, identificador)` con `tipo` en `{"proyecto", "cliente", "categoria"}`).
  Task 5 (`estado_reportes.py`) consume los dicts que devuelven estas 4
  funciones para calcular su hash; el agente los consume para redactar HTML
  (incluyendo el indicador visual de `en_desarrollo`, ver spec §6).

- [ ] **Step 1: Write the failing tests**

```python
# -*- coding: utf-8 -*-
from datetime import date

import openpyxl
import pytest

import datos_reportes as dr

HEADERS_PROYECTOS_TEST = [
    "TAG proyecto", "Nombre del proyecto", "Cliente", "Estado",
    "Fecha de inicio", "Fecha de cierre", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados",
    "Costos Materiales Reales", "Costos Equipos Reales",
    "Otros Costos Reales", "Mano de Obra Real", "Total Proyectado",
    "Total Real", "Margen Proyectado", "Margen Real",
    "Desviación % (Real vs Proyectado)", "Categoría",
]  # mismo orden real que master (Cliente es la 3a columna, Categoria la ultima)


def _fila_proyecto_completa(**overrides) -> dict:
    """Fila 'feliz' con todos los campos manuales requeridos cargados --
    los tests parten de esto y sobreescriben lo que quieran romper/variar."""
    base = {
        "TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "UMAG",
        "Estado": "Activo", "Fecha de inicio": date(2026, 1, 10),
        "Fecha de cierre": None, "Monto de Venta (sin IVA)": 1000000,
        "Costos Materiales Proyectados": 100000, "Costos Equipos Proyectados": 100000,
        "Mano de Obra Proyectada": 100000, "Otros Costos Proyectados": 100000,
        "Costos Materiales Reales": 90000, "Costos Equipos Reales": 90000,
        "Otros Costos Reales": 90000, "Mano de Obra Real": 90000,
        "Total Proyectado": 400000, "Total Real": 360000,
        "Margen Proyectado": 600000, "Margen Real": 640000,
        "Desviación % (Real vs Proyectado)": -0.1, "Categoría": "I+D+i",
    }
    base.update(overrides)
    return base


def _crear_excel_af(tmp_path, filas_proyectos: list[dict], filas_clientes: list[dict] | None = None):
    wb = openpyxl.Workbook()
    ws_p = wb.active
    ws_p.title = "Proyectos"
    for col, h in enumerate(HEADERS_PROYECTOS_TEST, start=1):
        ws_p.cell(row=1, column=col, value=h)
    for fila_idx, fila in enumerate(filas_proyectos, start=2):
        for col, h in enumerate(HEADERS_PROYECTOS_TEST, start=1):
            ws_p.cell(row=fila_idx, column=col, value=fila.get(h))

    ws_i = wb.create_sheet("Indicadores")
    headers_i = ["TAG proyecto", "Nombre del proyecto", "Rentabilidad sobre costo", "Margen neto %"]
    for col, h in enumerate(headers_i, start=1):
        ws_i.cell(row=1, column=col, value=h)
    ws_i.cell(row=2, column=1, value="UMAG")
    ws_i.cell(row=2, column=2, value="UMAG")
    ws_i.cell(row=2, column=4, value=0.2)

    ws_c = wb.create_sheet("Clientes")
    headers_c = ["Cliente", "AOV (Valor promedio de venta)", "CLTV", "Clasificación"]
    for col, h in enumerate(headers_c, start=1):
        ws_c.cell(row=1, column=col, value=h)
    for fila_idx, fila in enumerate(filas_clientes or [], start=2):
        for col, h in enumerate(headers_c, start=1):
            ws_c.cell(row=fila_idx, column=col, value=fila.get(h))

    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb.save(ruta)
    return ruta


def test_paquete_datos_proyecto_incluye_proyecto_indicadores_y_en_desarrollo(tmp_path):
    ruta = _crear_excel_af(
        tmp_path,
        [_fila_proyecto_completa()],  # Fecha de cierre = None -> en desarrollo
        [{"Cliente": "UMAG", "AOV (Valor promedio de venta)": 1000000, "CLTV": 200000, "Clasificación": "Clientes estratégicos"}],
    )
    paquete = dr.paquete_datos_proyecto(ruta, "UMAG")
    assert paquete["tipo"] == "proyecto"
    assert paquete["proyecto"]["Categoría"] == "I+D+i"
    assert paquete["indicadores"]["Margen neto %"] == 0.2
    assert paquete["en_desarrollo"] is True


def test_paquete_datos_proyecto_en_desarrollo_false_si_fecha_de_cierre_ya_paso(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(**{"Fecha de cierre": date(2020, 1, 1)}),
    ])
    paquete = dr.paquete_datos_proyecto(ruta, "UMAG")
    assert paquete["en_desarrollo"] is False


def test_paquete_datos_proyecto_lanza_valueerror_si_no_existe(tmp_path):
    ruta = _crear_excel_af(tmp_path, [_fila_proyecto_completa()])
    with pytest.raises(ValueError):
        dr.paquete_datos_proyecto(ruta, "NOEXISTE")


def test_paquete_datos_proyecto_lanza_datosincompletos_si_falta_un_campo_manual(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(**{"Mano de Obra Real": None}),
    ])
    with pytest.raises(dr.DatosIncompletosError):
        dr.paquete_datos_proyecto(ruta, "UMAG")


def test_paquete_datos_proyecto_no_requiere_fecha_de_cierre_para_estar_completo(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(**{"Fecha de cierre": None}),
    ])
    paquete = dr.paquete_datos_proyecto(ruta, "UMAG")  # no lanza DatosIncompletosError
    assert paquete["en_desarrollo"] is True


def test_paquete_datos_cliente_incluye_cltv_y_sus_proyectos(tmp_path):
    ruta = _crear_excel_af(
        tmp_path,
        [_fila_proyecto_completa()],
        [{"Cliente": "UMAG", "AOV (Valor promedio de venta)": 1000000, "CLTV": 200000, "Clasificación": "Clientes estratégicos"}],
    )
    paquete = dr.paquete_datos_cliente(ruta, "UMAG")
    assert paquete["tipo"] == "cliente"
    assert paquete["cltv"]["CLTV"] == 200000
    assert len(paquete["proyectos"]) == 1
    assert paquete["proyectos"][0]["TAG proyecto"] == "UMAG"


def test_paquete_datos_categoria_agrupa_por_categoria(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(),
        _fila_proyecto_completa(**{
            "TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache",
            "Cliente": "Cesfam Limache", "Categoría": "Mantenimiento",
        }),
    ])
    paquete = dr.paquete_datos_categoria(ruta, "Mantenimiento")
    assert paquete["tipo"] == "categoria"
    assert len(paquete["proyectos"]) == 1
    assert paquete["proyectos"][0]["TAG proyecto"] == "CFLI"


def test_paquete_datos_categoria_excluye_proyectos_incompletos(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(**{
            "TAG proyecto": "CFLI", "Cliente": "Cesfam Limache", "Categoría": "Mantenimiento",
        }),
        _fila_proyecto_completa(**{
            "TAG proyecto": "CCON", "Cliente": "Cesfam Constitución", "Categoría": "Mantenimiento",
            "Monto de Venta (sin IVA)": None,  # incompleto -- se excluye del agregado
        }),
    ])
    paquete = dr.paquete_datos_categoria(ruta, "Mantenimiento")
    assert len(paquete["proyectos"]) == 1
    assert paquete["proyectos"][0]["TAG proyecto"] == "CFLI"


def test_paquete_datos_categoria_lanza_valueerror_si_no_hay_proyectos(tmp_path):
    ruta = _crear_excel_af(tmp_path, [_fila_proyecto_completa()])
    with pytest.raises(ValueError):
        dr.paquete_datos_categoria(ruta, "Sin Categoria Real")


def test_paquete_datos_comparacion_combina_entidades(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(),
        _fila_proyecto_completa(**{
            "TAG proyecto": "CFLI", "Cliente": "Cesfam Limache", "Categoría": "Mantenimiento",
        }),
    ])
    paquete = dr.paquete_datos_comparacion(ruta, [("proyecto", "UMAG"), ("proyecto", "CFLI")])
    assert paquete["tipo"] == "comparacion"
    assert len(paquete["entidades"]) == 2
    assert paquete["entidades"][0]["proyecto"]["TAG proyecto"] == "UMAG"


def test_paquete_datos_comparacion_rechaza_tipo_desconocido(tmp_path):
    ruta = _crear_excel_af(tmp_path, [_fila_proyecto_completa()])
    with pytest.raises(ValueError):
        dr.paquete_datos_comparacion(ruta, [("no_existe", "UMAG")])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/test_datos_reportes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'datos_reportes'`

- [ ] **Step 3: Implement `datos_reportes.py`**

```python
# -*- coding: utf-8 -*-
"""
datos_reportes.py -- Paquetes de datos de solo lectura (dict) para que el
agente redacte reportes PDF sin leer celdas de Excel a mano. Nunca escribe
Análisis de Proyectos.xlsx.
"""

import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

RAIZ_REPORTES = Path(__file__).resolve().parent
RAIZ_SISTEMA = RAIZ_REPORTES.parent / "Sistema"
if str(RAIZ_SISTEMA) not in sys.path:
    sys.path.insert(0, str(RAIZ_SISTEMA))

from analisis_financiero import HOJA_CLIENTES, HOJA_INDICADORES, HOJA_PROYECTOS  # noqa: E402

# Campos manuales que un proyecto debe tener cargados para generar reporte
# (spec §6). "Fecha de cierre" queda deliberadamente FUERA -- su ausencia (o
# una fecha futura) marca al proyecto como "en desarrollo", no incompleto.
# "Cliente"/"Categoría" tampoco cuentan -- se resuelven automaticamente, no
# son carga manual del usuario.
CAMPOS_MANUALES_REQUERIDOS = [
    "Estado", "Fecha de inicio", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados", "Mano de Obra Real",
]


class DatosIncompletosError(ValueError):
    """Un proyecto no tiene todos sus campos manuales requeridos cargados."""


def proyecto_tiene_datos_completos(proyecto: dict) -> bool:
    return all(
        proyecto.get(campo) not in (None, "") for campo in CAMPOS_MANUALES_REQUERIDOS
    )


def proyecto_esta_en_desarrollo(proyecto: dict, hoy: date | None = None) -> bool:
    """Sin 'Fecha de cierre', o con una posterior a 'hoy' (fecha real actual
    por defecto), el proyecto se considera en desarrollo. Un valor no
    interpretable como fecha se trata igual (conservador: en desarrollo)."""
    hoy = hoy or date.today()
    fecha_cierre = proyecto.get("Fecha de cierre")
    if not fecha_cierre:
        return True
    if isinstance(fecha_cierre, datetime):
        fecha_cierre = fecha_cierre.date()
    if not isinstance(fecha_cierre, date):
        return True
    return fecha_cierre > hoy


def _mapa_encabezados(ws) -> dict[str, int]:
    return {celda.value: idx + 1 for idx, celda in enumerate(ws[1]) if celda.value}


def _filas_por_columna(ws, mapa: dict[str, int], nombre_columna: str, valor):
    """Todas las filas (>=2) cuya columna nombre_columna == valor, como dicts
    encabezado->valor."""
    col = mapa.get(nombre_columna)
    if col is None:
        return []
    resultado = []
    for fila_idx in range(2, ws.max_row + 1):
        if ws.cell(row=fila_idx, column=col).value == valor:
            resultado.append({h: ws.cell(row=fila_idx, column=c).value for h, c in mapa.items()})
    return resultado


def paquete_datos_proyecto(ruta_excel: Path, tag: str) -> dict:
    """Datos de 'Proyectos' + 'Indicadores' para un proyecto por su TAG.
    Lanza DatosIncompletosError si le faltan campos manuales requeridos."""
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws_p = wb[HOJA_PROYECTOS]
    mapa_p = _mapa_encabezados(ws_p)
    filas = _filas_por_columna(ws_p, mapa_p, "TAG proyecto", tag)
    if not filas:
        raise ValueError(f"TAG de proyecto '{tag}' no encontrado en '{HOJA_PROYECTOS}'.")
    proyecto = filas[0]
    if not proyecto_tiene_datos_completos(proyecto):
        raise DatosIncompletosError(
            f"Proyecto '{tag}' no tiene todos sus datos manuales cargados -- "
            f"no se genera reporte hasta que se complete."
        )

    indicadores = {}
    if HOJA_INDICADORES in wb.sheetnames:
        ws_i = wb[HOJA_INDICADORES]
        mapa_i = _mapa_encabezados(ws_i)
        filas_i = _filas_por_columna(ws_i, mapa_i, "TAG proyecto", tag)
        if filas_i:
            indicadores = filas_i[0]

    return {
        "tipo": "proyecto",
        "tag": tag,
        "proyecto": proyecto,
        "indicadores": indicadores,
        "en_desarrollo": proyecto_esta_en_desarrollo(proyecto),
    }


def paquete_datos_cliente(ruta_excel: Path, nombre_cliente: str) -> dict:
    """CLTV de 'Clientes' + sus proyectos con datos completos de 'Proyectos'
    -- los incompletos se excluyen del agregado, no bloquean el reporte."""
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws_p = wb[HOJA_PROYECTOS]
    mapa_p = _mapa_encabezados(ws_p)
    proyectos = [
        p for p in _filas_por_columna(ws_p, mapa_p, "Cliente", nombre_cliente)
        if proyecto_tiene_datos_completos(p)
    ]

    cltv = {}
    if HOJA_CLIENTES in wb.sheetnames:
        ws_c = wb[HOJA_CLIENTES]
        mapa_c = _mapa_encabezados(ws_c)
        filas_c = _filas_por_columna(ws_c, mapa_c, "Cliente", nombre_cliente)
        if filas_c:
            cltv = filas_c[0]

    if not proyectos and not cltv:
        raise ValueError(
            f"Cliente '{nombre_cliente}' no encontrado, o ninguno de sus "
            f"proyectos tiene datos completos."
        )

    return {"tipo": "cliente", "cliente": nombre_cliente, "cltv": cltv, "proyectos": proyectos}


def paquete_datos_categoria(ruta_excel: Path, categoria: str) -> dict:
    """Proyectos con datos completos de 'Proyectos' cuya Categoría calza --
    los incompletos se excluyen del agregado."""
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws_p = wb[HOJA_PROYECTOS]
    mapa_p = _mapa_encabezados(ws_p)
    proyectos = [
        p for p in _filas_por_columna(ws_p, mapa_p, "Categoría", categoria)
        if proyecto_tiene_datos_completos(p)
    ]
    if not proyectos:
        raise ValueError(f"Ningún proyecto con datos completos y Categoría '{categoria}'.")
    return {"tipo": "categoria", "categoria": categoria, "proyectos": proyectos}


_FUNCIONES_POR_TIPO = {
    "proyecto": paquete_datos_proyecto,
    "cliente": paquete_datos_cliente,
    "categoria": paquete_datos_categoria,
}


def paquete_datos_comparacion(ruta_excel: Path, entidades: list[tuple[str, str]]) -> dict:
    """entidades: lista de (tipo, identificador), tipo en 'proyecto'/'cliente'/'categoria'."""
    paquetes = []
    for tipo, identificador in entidades:
        funcion = _FUNCIONES_POR_TIPO.get(tipo)
        if funcion is None:
            raise ValueError(f"Tipo de entidad desconocido: '{tipo}'.")
        paquetes.append(funcion(ruta_excel, identificador))
    return {"tipo": "comparacion", "entidades": paquetes}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/test_datos_reportes.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Reportes/datos_reportes.py" "Sistema Analisis Financiero/Reportes/tests/test_datos_reportes.py"
git commit -m "feat(analisis-financiero): paquetes de datos de solo lectura para reportes PDF"
```

---

## Task 5: Manifiesto de obsolescencia (`estado_reportes.py`)

**Files:**
- Create: `Sistema Analisis Financiero/Reportes/estado_reportes.py`
- Test: `Sistema Analisis Financiero/Reportes/tests/test_estado_reportes.py` (create)

**Interfaces:**
- Produces: `calcular_hash_entidad(datos: dict) -> str`, `cargar_estado(ruta_estado: Path) -> dict`,
  `guardar_estado(ruta_estado: Path, estado: dict) -> None`,
  `detectar_desactualizados(paquetes_actuales: dict[str, dict], estado: dict) -> list[str]`,
  `marcar_generado(estado: dict, clave: str, datos: dict, generado_el: str) -> dict`.
  Task 6 (skill `status`/`run`) usa las 5.

- [ ] **Step 1: Write the failing tests**

```python
# -*- coding: utf-8 -*-
import estado_reportes as er


def test_calcular_hash_es_estable_para_los_mismos_datos():
    datos = {"b": 2, "a": 1}
    assert er.calcular_hash_entidad(datos) == er.calcular_hash_entidad({"a": 1, "b": 2})


def test_calcular_hash_cambia_si_cambian_los_datos():
    h1 = er.calcular_hash_entidad({"margen": 100})
    h2 = er.calcular_hash_entidad({"margen": 200})
    assert h1 != h2


def test_cargar_estado_devuelve_vacio_si_no_existe(tmp_path):
    assert er.cargar_estado(tmp_path / "no-existe.json") == {}


def test_guardar_y_cargar_estado_hacen_roundtrip(tmp_path):
    ruta = tmp_path / "sub" / "estado_reportes.json"
    er.guardar_estado(ruta, {"proyecto:UMAG": {"hash": "abc", "generado_el": "2026-07-21"}})
    assert er.cargar_estado(ruta) == {"proyecto:UMAG": {"hash": "abc", "generado_el": "2026-07-21"}}


def test_detectar_desactualizados_marca_entidad_nueva():
    paquetes = {"proyecto:UMAG": {"margen": 100}}
    assert er.detectar_desactualizados(paquetes, {}) == ["proyecto:UMAG"]


def test_detectar_desactualizados_marca_si_el_hash_cambio():
    datos_viejos = {"margen": 100}
    datos_nuevos = {"margen": 150}
    estado = {"proyecto:UMAG": {"hash": er.calcular_hash_entidad(datos_viejos), "generado_el": "x"}}
    assert er.detectar_desactualizados({"proyecto:UMAG": datos_nuevos}, estado) == ["proyecto:UMAG"]


def test_detectar_desactualizados_no_marca_si_no_cambio():
    datos = {"margen": 100}
    estado = {"proyecto:UMAG": {"hash": er.calcular_hash_entidad(datos), "generado_el": "x"}}
    assert er.detectar_desactualizados({"proyecto:UMAG": datos}, estado) == []


def test_marcar_generado_actualiza_el_estado_sin_mutar_el_original():
    datos = {"margen": 100}
    estado_original = {}
    nuevo_estado = er.marcar_generado(estado_original, "proyecto:UMAG", datos, "2026-07-21")
    assert estado_original == {}
    assert nuevo_estado["proyecto:UMAG"]["hash"] == er.calcular_hash_entidad(datos)
    assert nuevo_estado["proyecto:UMAG"]["generado_el"] == "2026-07-21"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/test_estado_reportes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'estado_reportes'`

- [ ] **Step 3: Implement `estado_reportes.py`**

```python
# -*- coding: utf-8 -*-
"""
estado_reportes.py -- Manifiesto de que reportes PDF quedaron desactualizados
(cambiaron sus datos de entrada desde la ultima generacion). Solo detecta y
marca -- nunca dispara redaccion ni renderizado.
"""

import hashlib
import json
from pathlib import Path


def calcular_hash_entidad(datos: dict) -> str:
    """Hash sha256 estable (claves ordenadas) de un paquete de datos."""
    payload = json.dumps(datos, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cargar_estado(ruta_estado: Path) -> dict:
    ruta_estado = Path(ruta_estado)
    if not ruta_estado.exists():
        return {}
    return json.loads(ruta_estado.read_text(encoding="utf-8"))


def guardar_estado(ruta_estado: Path, estado: dict) -> None:
    ruta_estado = Path(ruta_estado)
    ruta_estado.parent.mkdir(parents=True, exist_ok=True)
    ruta_estado.write_text(
        json.dumps(estado, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )


def detectar_desactualizados(paquetes_actuales: dict[str, dict], estado: dict) -> list[str]:
    """paquetes_actuales: clave (ej. 'proyecto:UMAG') -> paquete de datos
    actual. Devuelve las claves sin reporte previo o cuyo hash cambio."""
    desactualizados = []
    for clave, datos in paquetes_actuales.items():
        hash_actual = calcular_hash_entidad(datos)
        entrada_previa = estado.get(clave)
        if entrada_previa is None or entrada_previa.get("hash") != hash_actual:
            desactualizados.append(clave)
    return sorted(desactualizados)


def marcar_generado(estado: dict, clave: str, datos: dict, generado_el: str) -> dict:
    """Devuelve un estado NUEVO (no muta el original) con clave actualizada."""
    nuevo_estado = dict(estado)
    nuevo_estado[clave] = {"hash": calcular_hash_entidad(datos), "generado_el": generado_el}
    return nuevo_estado
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/test_estado_reportes.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add "Sistema Analisis Financiero/Reportes/estado_reportes.py" "Sistema Analisis Financiero/Reportes/tests/test_estado_reportes.py"
git commit -m "feat(analisis-financiero): manifiesto de obsolescencia de reportes PDF"
```

---

## Task 6: Skill `Reportes_Analisis_Financiero` (`driver.py status/run` + `SKILL.md`)

**Files:**
- Create: `Sistema Analisis Financiero/.claude/skills/Reportes_Analisis_Financiero/driver.py`
- Create: `Sistema Analisis Financiero/.claude/skills/Reportes_Analisis_Financiero/SKILL.md`
- Test: `Sistema Analisis Financiero/Reportes/tests/test_driver_reportes.py` (create)

**Interfaces:**
- Consumes: `datos_reportes.paquete_datos_proyecto/cliente/categoria`,
  `datos_reportes.proyecto_tiene_datos_completos`,
  `estado_reportes.cargar_estado/detectar_desactualizados`, `analisis_financiero.RUTA_EXCEL`,
  `analisis_financiero.HOJA_PROYECTOS`.
- Produces: `listar_entidades(ruta_excel: Path) -> dict[str, tuple[str, str]]` (clave
  `"proyecto:UMAG"` → `(tipo, identificador)`, para las 3 entidades recurrentes —
  **excluye los proyectos sin datos completos** vía
  `dr.proyecto_tiene_datos_completos`, así nunca llegan a figurar como
  pendientes; no incluye comparaciones ad-hoc, esas no pasan por el
  manifiesto), `calcular_reportes_pendientes(ruta_excel: Path, ruta_estado: Path) -> list[str]`
  (usado por `driver.py status`/`run` y por el aviso de PASO 12d en Task 7).

- [ ] **Step 1: Write the failing test**

```python
# -*- coding: utf-8 -*-
from datetime import date

import openpyxl

import driver as drv

HEADERS_PROYECTOS_TEST = [
    "TAG proyecto", "Nombre del proyecto", "Cliente", "Estado",
    "Fecha de inicio", "Fecha de cierre", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados",
    "Costos Materiales Reales", "Costos Equipos Reales",
    "Otros Costos Reales", "Mano de Obra Real", "Total Proyectado",
    "Total Real", "Margen Proyectado", "Margen Real",
    "Desviación % (Real vs Proyectado)", "Categoría",
]  # mismo orden real que master (ver Task 4)


def _fila_completa(**overrides) -> dict:
    base = {
        "TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "UMAG",
        "Estado": "Activo", "Fecha de inicio": date(2026, 1, 10),
        "Fecha de cierre": None, "Monto de Venta (sin IVA)": 1000000,
        "Costos Materiales Proyectados": 100000, "Costos Equipos Proyectados": 100000,
        "Mano de Obra Proyectada": 100000, "Otros Costos Proyectados": 100000,
        "Costos Materiales Reales": 90000, "Costos Equipos Reales": 90000,
        "Otros Costos Reales": 90000, "Mano de Obra Real": 90000,
        "Total Proyectado": 400000, "Total Real": 360000,
        "Margen Proyectado": 600000, "Margen Real": 640000,
        "Desviación % (Real vs Proyectado)": -0.1, "Categoría": "I+D+i",
    }
    base.update(overrides)
    return base


def _crear_excel_af(tmp_path, filas_proyectos: list[dict]):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Proyectos"
    for col, h in enumerate(HEADERS_PROYECTOS_TEST, start=1):
        ws.cell(row=1, column=col, value=h)
    for fila_idx, fila in enumerate(filas_proyectos, start=2):
        for col, h in enumerate(HEADERS_PROYECTOS_TEST, start=1):
            ws.cell(row=fila_idx, column=col, value=fila.get(h))
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb.save(ruta)
    return ruta


def test_listar_entidades_incluye_proyectos_clientes_y_categorias(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_completa(),
        _fila_completa(**{
            "TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache",
            "Cliente": "Cesfam Limache", "Categoría": "Mantenimiento",
        }),
    ])
    entidades = drv.listar_entidades(ruta)
    assert entidades["proyecto:UMAG"] == ("proyecto", "UMAG")
    assert entidades["cliente:UMAG"] == ("cliente", "UMAG")
    assert entidades["categoria:I+D+i"] == ("categoria", "I+D+i")
    assert entidades["categoria:Mantenimiento"] == ("categoria", "Mantenimiento")


def test_listar_entidades_excluye_proyectos_sin_datos_completos(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_completa(),
        _fila_completa(**{
            "TAG proyecto": "CFLI", "Cliente": "Cesfam Limache",
            "Monto de Venta (sin IVA)": None,  # incompleto
        }),
    ])
    entidades = drv.listar_entidades(ruta)
    assert "proyecto:CFLI" not in entidades
    assert "cliente:Cesfam Limache" not in entidades
    assert "proyecto:UMAG" in entidades


def test_calcular_reportes_pendientes_marca_todo_la_primera_vez(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_completa(),
        _fila_completa(**{
            "TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache",
            "Cliente": "Cesfam Limache", "Categoría": "Mantenimiento",
        }),
    ])
    ruta_estado = tmp_path / "estado_reportes.json"
    pendientes = drv.calcular_reportes_pendientes(ruta, ruta_estado)
    assert set(pendientes) == {
        "proyecto:UMAG", "proyecto:CFLI",
        "cliente:UMAG", "cliente:Cesfam Limache",
        "categoria:I+D+i", "categoria:Mantenimiento",
    }
```

El módulo se importa como `driver` (el nombre real del archivo,
`driver.py`, dentro de la carpeta del skill) — Step 3 agrega esa carpeta al
`sys.path` vía `conftest.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/test_driver_reportes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'driver_reportes'`

- [ ] **Step 3: Implement `driver.py`**

Primero, agregar a `Sistema Analisis Financiero/Reportes/tests/conftest.py`
(además de la línea ya existente):

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent.parent
        / ".claude" / "skills" / "Reportes_Analisis_Financiero"),
)
```

`Sistema Analisis Financiero/.claude/skills/Reportes_Analisis_Financiero/driver.py`
(el archivo se llama `driver.py` en disco; el test del Step 1 lo importa
directamente como `driver` porque su carpeta contenedora ya está en el
`sys.path` gracias al `conftest.py` de arriba):

```python
# -*- coding: utf-8 -*-
"""
driver.py -- Comandos status/run del skill Reportes_Analisis_Financiero.
status: solo lectura, calcula que reportes quedaron pendientes/desactualizados.
run: igual que status, mas contexto para que el AGENTE (no este script) redacte
y renderice cada uno -- este driver nunca genera contenido de reporte.
"""

import sys
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ_SKILL.parent.parent.parent
RAIZ_REPORTES = RAIZ_MODULO / "Reportes"
RAIZ_SISTEMA = RAIZ_MODULO / "Sistema"
for raiz in (RAIZ_REPORTES, RAIZ_SISTEMA):
    if str(raiz) not in sys.path:
        sys.path.insert(0, str(raiz))

import datos_reportes as dr  # noqa: E402
import estado_reportes as er  # noqa: E402
from analisis_financiero import HOJA_PROYECTOS, RUTA_EXCEL  # noqa: E402

import openpyxl  # noqa: E402

RUTA_ESTADO_REPORTES = RAIZ_REPORTES / "estado_reportes.json"


def listar_entidades(ruta_excel: Path = RUTA_EXCEL) -> dict[str, tuple[str, str]]:
    """Recorre 'Proyectos' y arma la clave->tipo/identificador de cada
    proyecto, cliente unico, y categoria unica presentes hoy. Excluye por
    completo los proyectos sin datos manuales completos (spec §6) -- ni
    generan su propia entrada 'proyecto:TAG', ni aportan a 'cliente:'/
    'categoria:' salvo que OTRO proyecto completo ya la haya registrado."""
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws = wb[HOJA_PROYECTOS]
    mapa = {celda.value: idx + 1 for idx, celda in enumerate(ws[1]) if celda.value}
    col_tag = mapa.get("TAG proyecto")

    entidades: dict[str, tuple[str, str]] = {}
    clientes_vistos = set()
    categorias_vistas = set()
    for fila_idx in range(2, ws.max_row + 1):
        tag = ws.cell(row=fila_idx, column=col_tag).value if col_tag else None
        if not tag:
            continue
        fila = {h: ws.cell(row=fila_idx, column=c).value for h, c in mapa.items()}
        if not dr.proyecto_tiene_datos_completos(fila):
            continue

        entidades[f"proyecto:{tag}"] = ("proyecto", tag)

        cliente = fila.get("Cliente")
        if cliente and cliente not in clientes_vistos:
            clientes_vistos.add(cliente)
            entidades[f"cliente:{cliente}"] = ("cliente", cliente)

        categoria = fila.get("Categoría")
        if categoria and categoria not in categorias_vistas:
            categorias_vistas.add(categoria)
            entidades[f"categoria:{categoria}"] = ("categoria", categoria)

    return entidades


_FUNCIONES_POR_TIPO = {
    "proyecto": dr.paquete_datos_proyecto,
    "cliente": dr.paquete_datos_cliente,
    "categoria": dr.paquete_datos_categoria,
}


def calcular_reportes_pendientes(
    ruta_excel: Path = RUTA_EXCEL, ruta_estado: Path = RUTA_ESTADO_REPORTES,
) -> list[str]:
    """Claves de entidades cuyo reporte PDF no existe o quedo desactualizado."""
    entidades = listar_entidades(ruta_excel)
    paquetes_actuales = {
        clave: _FUNCIONES_POR_TIPO[tipo](ruta_excel, identificador)
        for clave, (tipo, identificador) in entidades.items()
    }
    estado = er.cargar_estado(ruta_estado)
    return er.detectar_desactualizados(paquetes_actuales, estado)


def status() -> None:
    pendientes = calcular_reportes_pendientes()
    print("=== Reportes Analisis Financiero -- status ===")
    if not pendientes:
        print("Todos los reportes estan al dia.")
        return
    print(f"{len(pendientes)} reporte(s) pendiente(s)/desactualizado(s):")
    for clave in pendientes:
        print(f"  - {clave}")


def run() -> None:
    pendientes = calcular_reportes_pendientes()
    print("=== Reportes Analisis Financiero -- run ===")
    if not pendientes:
        print("Todos los reportes estan al dia. Nada que generar.")
        return
    print(
        f"{len(pendientes)} reporte(s) pendiente(s) -- este comando NO los genera "
        f"solo (requiere redaccion del agente). Pidele al agente que los redacte "
        f"y renderice uno por uno usando datos_reportes/brand/graficos/motor_reportes."
    )
    for clave in pendientes:
        print(f"  - {clave}")


if __name__ == "__main__":
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    comando = _sys.argv[1] if len(_sys.argv) > 1 else "status"
    {"status": status, "run": run}.get(comando, status)()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/test_driver_reportes.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write `SKILL.md`**

```markdown
---
name: Reportes_Analisis_Financiero
description: Genera y mantiene al dia los reportes PDF de Analisis Financiero (por proyecto, por cliente, por categoria, y comparaciones ad-hoc), con marca QUEMPIN. Usar cuando el usuario pida un reporte PDF de un proyecto/cliente/categoria, una comparacion entre proyectos/clientes, o ver que reportes quedaron desactualizados.
---

# Reportes Analisis Financiero

Construye PDFs de analisis financiero especializado (KPIs, graficos, tablas,
comparativas) con la marca oficial de QUEMPIN. El **contenido de cada reporte
lo redacta el agente** en la conversacion -- este skill solo expone la
infraestructura (datos, marca, render) y detecta que reportes quedaron
desactualizados. Ver
`docs/superpowers/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md`
(raiz de `Finanzas QUEMPIN/`) para el diseno completo.

## Comandos

**`status`** -- solo lectura: lista que reportes (proyecto/cliente/categoria)
estan pendientes o desactualizados.

```
python ".claude/skills/Reportes_Analisis_Financiero/driver.py" status
```

**`run`** -- misma deteccion que `status`, pero pensada para que el agente
tome la lista y redacte/renderice cada reporte pendiente a continuacion (este
comando no genera contenido por si solo).

```
python ".claude/skills/Reportes_Analisis_Financiero/driver.py" run
```

## Como redactar y renderizar un reporte (flujo del agente)

1. Armar el paquete de datos: `datos_reportes.paquete_datos_proyecto/cliente/categoria/comparacion(RUTA_EXCEL, ...)`.
   Si el proyecto no tiene todos sus datos manuales cargados, esta llamada
   lanza `DatosIncompletosError` -- **no generar el reporte en ese caso**
   (ni improvisar los datos que faltan).
2. Si el paquete de un proyecto trae `en_desarrollo: true` (sin fecha de
   cierre, o con una posterior a hoy), incluir un indicador visual explícito
   ("EN DESARROLLO") en el reporte -- nunca presentarlo como un proyecto
   cerrado y evaluado en forma definitiva.
3. Redactar el `contenido_html` del reporte (KPIs relevantes, tablas, graficos
   via `graficos.grafico_barras_svg`/`grafico_dona_svg`) segun lo que aporte
   señal para esa entidad especifica -- la estructura no es fija.
4. Envolver con `brand.construir_html(titulo, generado_el, contenido_html)`.
5. Renderizar: `motor_reportes.renderizar_pdf(html, ruta_salida)` hacia
   `Análisis Financiero/Reportes/{Proyectos,Clientes,Categorías,Comparativas}/`.
6. Actualizar el manifiesto (solo para proyecto/cliente/categoria, NO para
   comparaciones ad-hoc): `estado_reportes.marcar_generado(estado, clave, datos, fecha_de_hoy)`
   y `estado_reportes.guardar_estado(RUTA_ESTADO_REPORTES, nuevo_estado)`.

## Gotchas

- **Nunca genera contenido sin que se le pida** -- `status`/`run` solo
  detectan y listan, la redaccion ocurre en conversacion.
- **Comparaciones ad-hoc no pasan por el manifiesto de obsolescencia** -- se
  generan frescas cada vez, no se marcan como vigentes/desactualizadas.
- **Proyectos sin datos manuales completos nunca aparecen como pendientes**
  (`listar_entidades` los excluye) -- si el usuario pide el reporte de uno
  igual, `paquete_datos_proyecto` lanza `DatosIncompletosError`: explicarle
  qué campo falta, no inventarlo.
- **`en_desarrollo: true` no es un defecto** -- es la señal de que el
  proyecto sigue abierto (sin fecha de cierre, o con una futura); el reporte
  se genera igual, solo con el indicador visual correspondiente.
- **`playwright` debe estar instalado** (`pip install playwright && python -m playwright install chromium`) -- reutiliza el Chromium ya cacheado para Centro de Costos si la revision calza.
```

- [ ] **Step 6: Commit**

```bash
git add "Sistema Analisis Financiero/.claude/skills/Reportes_Analisis_Financiero/" "Sistema Analisis Financiero/Reportes/tests/conftest.py" "Sistema Analisis Financiero/Reportes/tests/test_driver_reportes.py"
git commit -m "feat(analisis-financiero): skill Reportes_Analisis_Financiero (status/run)"
```

---

## Task 7: Aviso en PASO 12d de Centro de Costos + documentación

**Files:**
- Modify: `Centro de Costos/Sistema/auditor_centro_costos.py:1996-2023` (función `actualizar_analisis_financiero`)
- Modify: `Sistema Analisis Financiero/CLAUDE.md`
- Modify: `Sistema Analisis Financiero/MEMORY.md`
- Test: `Centro de Costos/Sistema/tests/test_auditor_centro_costos_aviso_reportes.py` (create — revisar el nombre real del archivo de tests existente de este script antes de crear uno nuevo, para seguir la misma convención de nombres)

**Interfaces:**
- Consumes: `calcular_reportes_pendientes` del `driver.py` de Task 6 (importado igual que ya se importa `analisis_financiero` hoy).

- [ ] **Step 1: Write the failing test**

Antes de escribir, revisa `Centro de Costos/Sistema/tests/` para confirmar el
archivo donde ya se testea `actualizar_analisis_financiero` (buscar
`grep -rn "actualizar_analisis_financiero" "Centro de Costos/Sistema/tests/"`)
y agrega el test ahí en vez de crear uno nuevo si ya existe cobertura de esa
función. Si no existe, crea:

```python
# -*- coding: utf-8 -*-
from unittest.mock import patch

import auditor_centro_costos as acc


def test_actualizar_analisis_financiero_avisa_reportes_pendientes(capsys):
    with patch.object(acc, "_reportes_pendientes_tras_run", return_value=["proyecto:UMAG"]):
        acc._avisar_reportes_pendientes()
    salida = capsys.readouterr().out
    assert "proyecto:UMAG" in salida
    assert "Reportes_Analisis_Financiero" in salida


def test_actualizar_analisis_financiero_no_avisa_si_no_hay_pendientes(capsys):
    with patch.object(acc, "_reportes_pendientes_tras_run", return_value=[]):
        acc._avisar_reportes_pendientes()
    salida = capsys.readouterr().out
    assert salida == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "Centro de Costos/Sistema" && python -m pytest tests/test_auditor_centro_costos_aviso_reportes.py -v`
Expected: FAIL — `AttributeError: module 'auditor_centro_costos' has no attribute '_reportes_pendientes_tras_run'`

- [ ] **Step 3: Add `_reportes_pendientes_tras_run` and `_avisar_reportes_pendientes`, wire into `actualizar_analisis_financiero`**

En `Centro de Costos/Sistema/auditor_centro_costos.py`, agregar antes de
`actualizar_analisis_financiero` (usa la misma constante `RAIZ_ANALISIS_FINANCIERO`
que ya existe en ese archivo):

```python
def _reportes_pendientes_tras_run() -> list[str]:
    """Best-effort: intenta calcular que reportes PDF quedaron pendientes tras
    este run. Devuelve [] si el skill de reportes no existe todavia o falla
    -- nunca aborta el run de Centro de Costos por esto."""
    ruta_driver = (
        RAIZ_ANALISIS_FINANCIERO / ".claude" / "skills"
        / "Reportes_Analisis_Financiero" / "driver.py"
    )
    if not ruta_driver.exists():
        return []
    import sys
    raiz_skill = ruta_driver.parent
    ya_en_path = str(raiz_skill) in sys.path
    if not ya_en_path:
        sys.path.insert(0, str(raiz_skill))
    try:
        sys.modules.pop("driver", None)
        import driver as driver_reportes
        return driver_reportes.calcular_reportes_pendientes()
    except Exception:
        return []
    finally:
        if not ya_en_path and str(raiz_skill) in sys.path:
            sys.path.remove(str(raiz_skill))


def _avisar_reportes_pendientes() -> None:
    pendientes = _reportes_pendientes_tras_run()
    if not pendientes:
        return
    print(
        f"  [AVISO] {len(pendientes)} reporte(s) PDF de Analisis Financiero "
        f"quedaron pendientes/desactualizados -- correr "
        f"'/Reportes_Analisis_Financiero status' para verlos."
    )
```

Al final de `actualizar_analisis_financiero`, justo antes del último `return True`
del bloque `try` exitoso, agregar la llamada:

```python
        resumen = af.ejecutar()
        if resumen["error"]:
            print(f"  [WARN] Análisis Financiero terminó con error: {resumen['error']}")
            return False
        _avisar_reportes_pendientes()
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "Centro de Costos/Sistema" && python -m pytest tests/test_auditor_centro_costos_aviso_reportes.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full test suite of both modules to check for regressions**

Run: `cd "Centro de Costos/Sistema" && python -m pytest -v`
Run: `cd "Sistema Analisis Financiero/Sistema" && python -m pytest -v`
Run: `cd "Sistema Analisis Financiero/Reportes" && python -m pytest tests/ -v`
Expected: PASS en las 3 suites.

- [ ] **Step 6: Update `Sistema Analisis Financiero/CLAUDE.md` and `MEMORY.md`**

En `CLAUDE.md`, agregar una sección `## Reportes PDF (implementado AAAA-MM-DD)`
resumiendo: la carpeta `Reportes/` (brand/graficos/motor_reportes/datos_reportes/estado_reportes),
el skill `Reportes_Analisis_Financiero`, las reglas de completitud/"en
desarrollo" (spec §6 — sin datos manuales completos no hay reporte; sin
fecha de cierre o con una futura, el proyecto es "en desarrollo" y su
reporte lleva un indicador visual), y el enlace a
`docs/superpowers/specs/2026-07-21-analisis-financiero-reportes-pdf-design.md`
y a este plan.

En `MEMORY.md`, agregar una entrada registrando: que el contenido de cada
reporte lo redacta el agente (no un script), que el manifiesto de
obsolescencia no dispara generación automática, y la dependencia resuelta
con el plan de Cliente/CLTV (qué commit lo completó, si al momento de esta
tarea ya está en `master`).

- [ ] **Step 7: Commit**

```bash
git add "Centro de Costos/Sistema/auditor_centro_costos.py" "Centro de Costos/Sistema/tests/" "Sistema Analisis Financiero/CLAUDE.md" "Sistema Analisis Financiero/MEMORY.md"
git commit -m "feat(analisis-financiero): avisar reportes PDF pendientes al final del run de Centro de Costos + docs"
```
