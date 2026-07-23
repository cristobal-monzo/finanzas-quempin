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
