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
.pdf-pagina { page-break-after: always; }
.pdf-pagina:last-child { page-break-after: auto; }
.reporte-header--pagina { padding: 8px 0 14px; margin-bottom: 10px; border-bottom: 2px solid var(--brand-orange); }
.reporte-header--pagina .reporte-logo { height: 30px; }
.reporte-header--pagina h1 { font-size: 15px; }
.reporte-header--pagina .reporte-fecha { font-size: 10px; }
.kpi-fila { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
.kpi-tarjeta { flex: 1 1 160px; border: 1px solid var(--brand-gray-light); border-radius: 8px; padding: 12px 16px; }
.kpi-tarjeta .valor { font-size: 24px; font-weight: 900; color: var(--brand-orange); }
.kpi-tarjeta .etiqueta { font-size: 12px; color: var(--brand-gray-dark); }
table.tabla-reporte { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
table.tabla-reporte th, table.tabla-reporte td { border: 1px solid var(--brand-gray-light); padding: 6px 10px; font-size: 12px; text-align: right; }
table.tabla-reporte th { background: var(--brand-black); color: white; text-align: left; }
table.tabla-reporte td:first-child, table.tabla-reporte th:first-child { text-align: left; }
table.tabla-reporte td.alerta { font-weight: 900; color: var(--brand-orange); }
.leyenda-graficos { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 2px 0 10px; font-size: 11px; color: var(--brand-gray-dark); }
.leyenda-item { display: inline-flex; align-items: center; gap: 4px; }
.leyenda-swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.leyenda-nota { font-size: 8.5px; color: var(--brand-gray-dark); margin: -4px 0 8px; font-style: italic; }
.reporte-footer { padding: 12px 32px; font-size: 10px; color: var(--brand-gray-dark); border-top: 1px solid var(--brand-gray-light); }

/* Panel de verificacion (pagina 1 del estandar de 2 paginas): compacto,
   2 columnas -- ver SKILL.md de Reportes_Analisis_Financiero. */
.pdf-pagina.p1 { padding: 4px 0 0; }
.pdf-pagina.p1 h2 { font-size: 16px; margin: 0 0 8px; }
.pdf-pagina.p1 h3 { font-size: 11.5px; margin: 10px 0 4px; text-transform: uppercase; color: var(--brand-gray-dark); }
.pdf-pagina.p1 table.tabla-reporte { margin-bottom: 6px; }
.pdf-pagina.p1 table.tabla-reporte td, .pdf-pagina.p1 table.tabla-reporte th { padding: 3px 7px; font-size: 10px; }
.pdf-pagina.p1 table.tabla-reporte td.referencia { color: var(--brand-gray-dark); font-size: 9px; text-align: left; }
.pdf-pagina.p1 .kpi-fila { gap: 10px; margin-bottom: 10px; }
.pdf-pagina.p1 .kpi-tarjeta { padding: 6px 10px; flex-basis: 130px; }
.pdf-pagina.p1 .kpi-tarjeta .valor { font-size: 16px; }
.pdf-pagina.p1 .kpi-tarjeta .etiqueta { font-size: 9px; }
.pdf-pagina.p1 .leyenda-graficos { font-size: 9.5px; margin: 2px 0 8px; }
.pdf-pagina.p1 .fila-2-col { display: flex; gap: 20px; align-items: flex-start; }
.pdf-pagina.p1 .fila-2-col > div { flex: 1 1 0; }

/* Analisis narrativo (pagina 2): mas espacio, listas escaneables. */
.pdf-pagina.p2 { padding: 4px 0 0; }
.pdf-pagina.p2 h2 { font-size: 18px; margin: 4px 0 10px; }
.pdf-pagina.p2 h3 { font-size: 13.5px; margin: 12px 0 5px; color: var(--brand-orange); }
.pdf-pagina.p2 p { font-size: 13px; line-height: 1.45; margin: 0 0 8px; }
.pdf-pagina.p2 .lista-analisis { font-size: 13px; line-height: 1.4; margin: 0 0 6px; padding-left: 18px; }
.pdf-pagina.p2 .lista-analisis li { margin-bottom: 5px; }
.pdf-pagina.p2 .fila-2-col { display: flex; gap: 24px; align-items: flex-start; }
.pdf-pagina.p2 .fila-2-col > div { flex: 1 1 0; }
"""

# Umbrales del criterio "KPI fuera de lo esperado" (se destaca en negrita/
# naranjo en la tabla, clase CSS `alerta`). Mismos umbrales para todo
# reporte -- si un caso concreto amerita otro criterio, es decision del
# agente al redactar, pero el default vive aca para no repetirlo copiado
# en cada script.
OBJETIVO_MARGEN_NETO = 0.25          # objetivo del playbook (ver CLAUDE.md)
UMBRAL_DESVIACION_ALERTA = 0.30      # |desviacion| >= 30% se destaca

# Texto de referencia/objetivo del playbook por KPI, para la columna
# "Referencia" de la tabla de Indicadores -- que la tabla se explique sola
# sin depender de leer la pagina 2.
REFERENCIA_KPI = {
    "Rentabilidad sobre costo": "Referencia: > 1x (margen positivo)",
    "Margen neto %": f"Objetivo playbook: {OBJETIVO_MARGEN_NETO:.0%}",
    "Desviación % Materiales": "Ideal: cercano a 0%",
    "Desviación % Equipos": "Ideal: cercano a 0%",
    "Desviación % MO": "Ideal: cercano a 0%",
    "Desviación % Otros": "Ideal: cercano a 0%",
}


def es_kpi_fuera_de_rango(nombre_kpi: str, valor: float) -> bool:
    """Criterio centralizado de "KPI fuera de lo esperado" para destacarlo
    en negrita/naranjo (clase `alerta`) en la tabla de un reporte. Cubre
    los KPIs con umbral objetivo conocido (margen neto, desviaciones);
    para el resto de los KPIs devuelve False -- no hay un umbral universal
    razonable para Productividad o Costo % de venta sin contexto de
    categoria/cliente."""
    if nombre_kpi == "Margen neto %":
        return valor >= OBJETIVO_MARGEN_NETO * 1.5 or valor < 0
    if nombre_kpi == "Rentabilidad sobre costo":
        return valor < 1.0 or valor >= 4.0
    if nombre_kpi.startswith("Desviación %"):
        return abs(valor) >= UMBRAL_DESVIACION_ALERTA
    return False


def referencia_kpi(nombre_kpi: str) -> str:
    """Texto corto de referencia/objetivo del playbook para un KPI, o
    cadena vacia si ese KPI no tiene una referencia fija definida."""
    return REFERENCIA_KPI.get(nombre_kpi, "")

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
<footer class="reporte-footer">QUEMPIN SpA -- Analisis Financiero{nota_fuente}</footer>
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


def encabezado_html(titulo: str, generado_el: str) -> str:
    """Bloque de encabezado (logo + titulo + fecha) reutilizable, en version
    compacta (clase `reporte-header--pagina`). El documento ya trae su
    propio encabezado completo antes de la pagina 1 (ver PLANTILLA_DOCUMENTO);
    esta version la usa el agente para repetir el encabezado al inicio de
    cada `pdf-pagina` siguiente, de forma que el PDF impreso lleve marca en
    todas sus paginas fisicas, no solo en la primera."""
    return f"""<header class="reporte-header reporte-header--pagina">
  <img src="{cargar_logo_base64()}" alt="QUEMPIN" class="reporte-logo">
  <div class="reporte-titulos">
    <h1>{titulo}</h1>
    <p class="reporte-fecha">Generado el {generado_el}</p>
  </div>
</header>"""


def construir_html(
    titulo: str, generado_el: str, contenido_html: str,
    fecha_corte: str | None = None,
) -> str:
    """Envuelve contenido_html (redactado por el agente) en el documento
    completo con marca QUEMPIN -- header con logo, tipografia y colores
    oficiales, footer. contenido_html debe ser HTML ya armado (tarjetas de
    KPI, tablas, graficos SVG de graficos.py), no se procesa ni se valida.

    `fecha_corte` (opcional) agrega al footer "Datos al {fecha} -- Fuente:
    Centro de Costos + registro manual", para trazabilidad de cuando se
    tomo el dato -- distinto de `generado_el` (cuando se genero el PDF),
    que puede ser un dia despues del cierre de datos."""
    css = CSS_COLORES + cargar_font_face_lato() + CSS_BASE_REPORTE
    nota_fuente = (
        f" -- Datos al {fecha_corte} -- Fuente: Centro de Costos + registro manual"
        if fecha_corte else ""
    )
    return PLANTILLA_DOCUMENTO.format(
        titulo=titulo,
        css=css,
        logo=cargar_logo_base64(),
        generado_el=generado_el,
        contenido=contenido_html,
        nota_fuente=nota_fuente,
    )
