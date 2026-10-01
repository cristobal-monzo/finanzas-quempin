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

import sys
from functools import lru_cache
from pathlib import Path

from graficos import formatear_valor

RAIZ = Path(__file__).resolve().parent
if str(RAIZ.parent / "Sistema") not in sys.path:
    sys.path.insert(0, str(RAIZ.parent / "Sistema"))

# Los cortes de la Nota (85/70/55) viven en analisis_financiero y se leen de
# ahi, no se repiten aca: el semaforo del PDF tiene que mover sus colores el
# dia que se muevan esos cortes, sin que nadie se acuerde de sincronizarlos.
from analisis_financiero import clasificar_evaluacion  # noqa: E402
RUTA_TEMPLATE_CC = (
    RAIZ.parent.parent / "Centro de Costos" / "Visualizador Web" / "template.html"
)

COLOR_NARANJO = "#ff5100"      # Pantone Orange 021 C
COLOR_NEGRO = "#000000"        # Black C
COLOR_GRIS_CLARO = "#98989a"   # Cool Gray 7 C
COLOR_GRIS_OSCURO = "#54565a"  # Cool Gray 11 C

# Semaforo y tinta naranja: los mismos valores ya calibrados para el
# dashboard de Analisis Financiero (Visualizador Web/template.html), no
# tonos nuevos -- ahi se oscurecieron hasta pasar contraste AA (4.5:1) sobre
# fondo blanco, y el PDF se imprime sobre el mismo fondo. Mismos cortes de
# Evaluacion que el tablero: Excelente/Bueno = bueno, Aprobado = medio,
# Requiere atencion = malo.
COLOR_BUENO = "#087a08"
COLOR_MEDIO = "#8c5900"
COLOR_MALO = "#d1282e"
COLOR_NARANJO_TINTA = "#b23a00"  # naranjo oficial oscurecido, para texto chico

CSS_COLORES = f"""
:root {{
  --brand-orange: {COLOR_NARANJO};
  --brand-orange-ink: {COLOR_NARANJO_TINTA};
  --brand-black: {COLOR_NEGRO};
  --brand-gray-light: {COLOR_GRIS_CLARO};
  --brand-gray-dark: {COLOR_GRIS_OSCURO};
  --estado-bueno: {COLOR_BUENO};
  --estado-medio: {COLOR_MEDIO};
  --estado-malo: {COLOR_MALO};
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
.kpi-tarjeta { flex: 1 1 160px; border: 1px solid var(--brand-gray-light); border-radius: 8px; padding: 12px 16px; box-sizing: border-box; }
.kpi-tarjeta .valor { font-size: 24px; font-weight: 900; color: var(--brand-orange); }
.kpi-tarjeta .etiqueta { font-size: 12px; color: var(--brand-gray-dark); }
table.tabla-reporte { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
table.tabla-reporte th, table.tabla-reporte td { border: 1px solid var(--brand-gray-light); padding: 6px 10px; font-size: 12px; text-align: right; }
table.tabla-reporte th { background: var(--brand-black); color: white; text-align: left; }
table.tabla-reporte td:first-child, table.tabla-reporte th:first-child { text-align: left; }
table.tabla-reporte td.alerta { font-weight: 900; color: var(--brand-orange-ink); }
table.tabla-reporte td.estado-bueno { font-weight: 900; color: var(--estado-bueno); }
table.tabla-reporte td.estado-medio { font-weight: 900; color: var(--estado-medio); }
table.tabla-reporte td.estado-malo { font-weight: 900; color: var(--estado-malo); }
table.tabla-reporte tr.bloque th { background: var(--brand-gray-dark); font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.04em; }
.leyenda-graficos { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 2px 0 10px; font-size: 11px; color: var(--brand-gray-dark); }
.leyenda-item { display: inline-flex; align-items: center; gap: 4px; }
.leyenda-swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.leyenda-nota { font-size: 8.5px; color: var(--brand-gray-dark); margin: -4px 0 8px; font-style: italic; }
.reporte-footer { padding: 12px 32px; font-size: 10px; color: var(--brand-gray-dark); border-top: 1px solid var(--brand-gray-light); }

/* Panel de verificacion (pagina 1 del estandar de 2 paginas): lo arma
   panel.py, no el agente a mano -- ver SKILL.md de
   Reportes_Analisis_Financiero. 2 columnas, pensado para llenar el alto
   completo de la pagina (no comprimir de mas). */
.pdf-pagina.p1 { padding: 4px 0 10px; }
.pdf-pagina.p1 h2 { font-size: 17px; margin: 0 0 10px; }

/* Ficha de identificacion: el nombre de la entidad y sus atributos (cliente,
   categoria, avance, estado) como chips, en vez de repetir el titulo del
   documento en un h2 y dejar los atributos para la prosa de la pagina 2. */
.ficha { border-left: 4px solid var(--brand-orange); padding: 0 0 0 10px; margin: 0 0 12px; }
.ficha h2 { font-size: 18px; margin: 0 0 5px; }
.ficha .chips { display: flex; flex-wrap: wrap; gap: 5px; }
.chip { font-size: 9.5px; padding: 2px 8px; border-radius: 10px; background: #f0f0f0; color: var(--brand-gray-dark); }
.chip strong { color: var(--brand-black); font-weight: 700; }
.chip--abierto { background: var(--brand-orange); color: white; font-weight: 900; letter-spacing: 0.04em; }
.chip--cerrado { background: var(--estado-bueno); color: white; font-weight: 700; }

/* Tarjeta de KPI con semaforo: el borde izquierdo y el valor toman el color
   del estado (bueno/medio/malo). Antes todo valor destacado era naranjo,
   asi que un margen excelente se leia igual que un sobrecosto. */
.kpi-tarjeta.estado-bueno { border-left: 5px solid var(--estado-bueno); }
.kpi-tarjeta.estado-medio { border-left: 5px solid var(--estado-medio); }
.kpi-tarjeta.estado-malo { border-left: 5px solid var(--estado-malo); }
.kpi-tarjeta.estado-bueno .valor { color: var(--estado-bueno); }
.kpi-tarjeta.estado-medio .valor { color: var(--estado-medio); }
.kpi-tarjeta.estado-malo .valor { color: var(--estado-malo); }
.kpi-tarjeta .contexto { font-size: 9px; color: var(--brand-gray-dark); margin-top: 3px; }

/* Alertas de alertas_proyecto(): hasta ahora solo salian por consola y en el
   dashboard; el PDF impreso es justamente donde se revisa un proyecto. */
.alertas { border: 1px solid var(--estado-medio); border-left: 5px solid var(--estado-medio); border-radius: 6px; padding: 7px 12px; margin: 0 0 12px; }
.alertas h3 { margin: 0 0 4px !important; color: var(--estado-medio) !important; }
.alertas ul { margin: 0; padding-left: 16px; font-size: 10px; line-height: 1.35; }
.alertas li { margin-bottom: 2px; }

/* Tabla completa de indicadores en 2 columnas: el set del playbook son 28
   filas -- en una sola columna no cabe con los graficos en la misma pagina,
   y partirla no es seleccion editorial (siguen estando todas). */
.tabla-kpis-2col { display: flex; gap: 14px; align-items: flex-start; }
.tabla-kpis-2col > table { flex: 1 1 0; }
.pdf-pagina.p1 h3 { font-size: 11.5px; margin: 7px 0 4px; text-transform: uppercase; letter-spacing: 0.02em; color: var(--brand-gray-dark); }
.pdf-pagina.p1 h3:first-child { margin-top: 0; }
.pdf-pagina.p1 table.tabla-reporte { margin-bottom: 7px; }
.pdf-pagina.p1 table.tabla-reporte td, .pdf-pagina.p1 table.tabla-reporte th { padding: 3px 9px; font-size: 10.5px; }
.pdf-pagina.p1 table.tabla-reporte td.referencia { color: var(--brand-gray-dark); font-size: 9.5px; text-align: left; }
.pdf-pagina.p1 .kpi-fila { gap: 12px; margin-bottom: 14px; }
.pdf-pagina.p1 .kpi-tarjeta { padding: 10px 14px; flex-basis: 145px; }
.pdf-pagina.p1 .kpi-tarjeta .valor { font-size: 19px; }
.pdf-pagina.p1 .kpi-tarjeta .etiqueta { font-size: 9.5px; }
.pdf-pagina.p1 .leyenda-graficos { font-size: 10.5px; margin: 3px 0 9px; }
.pdf-pagina.p1 .leyenda-nota { font-size: 9px; margin: -4px 0 9px; }
.pdf-pagina.p1 .fila-2-col { display: flex; gap: 24px; align-items: stretch; }
.pdf-pagina.p1 .fila-2-col > div { flex: 1 1 0; display: flex; flex-direction: column; }
.pdf-pagina.p1 .dona-con-leyenda { display: flex; align-items: center; gap: 16px; margin-bottom: 2px; }
.pdf-pagina.p1 .dona-con-leyenda svg { flex-shrink: 0; }
.pdf-pagina.p1 .dona-con-leyenda .leyenda-graficos { flex-direction: column; gap: 6px; margin: 0; }

/* Analisis narrativo (pagina 2): mas espacio, listas escaneables. */
.pdf-pagina.p2 { padding: 4px 0 0; }
.pdf-pagina.p2 h2 { font-size: 18px; margin: 4px 0 10px; }
.pdf-pagina.p2 h3 { font-size: 13.5px; margin: 12px 0 5px; color: var(--brand-orange); }
.pdf-pagina.p2 p { font-size: 13px; line-height: 1.45; margin: 0 0 8px; }
.pdf-pagina.p2 .lista-analisis { font-size: 13px; line-height: 1.4; margin: 0 0 6px; padding-left: 18px; }
.pdf-pagina.p2 .lista-analisis li { margin-bottom: 5px; }
.pdf-pagina.p2 .fila-2-col { display: flex; gap: 24px; align-items: flex-start; }
.pdf-pagina.p2 .fila-2-col > div { flex: 1 1 0; }
/* Resumen ejecutivo y cierre: destacados en caja para que la pagina 2 tenga
   jerarquia visual y no sea un bloque uniforme de texto. */
.pdf-pagina.p2 .destacado { background: #f7f7f7; border-left: 4px solid var(--brand-orange); padding: 9px 14px; margin: 0 0 12px; }
.pdf-pagina.p2 .destacado p:last-child { margin-bottom: 0; }
.pdf-pagina.p2 .decision { border: 1px solid var(--brand-gray-light); border-top: 3px solid var(--brand-black); padding: 9px 14px; margin: 12px 0 0; }
.pdf-pagina.p2 .decision h3 { margin-top: 0; }
"""

# Umbrales del semaforo de KPIs (ver estado_kpi). Mismos umbrales para todo
# reporte -- si un caso concreto amerita otro criterio, es decision del
# agente al redactar, pero el default vive aca para no repetirlo copiado
# en cada script.
OBJETIVO_MARGEN_NETO = 0.25          # objetivo del playbook (ver CLAUDE.md)
UMBRAL_DESVIACION_ALERTA = 0.30      # |desviacion| >= 30%: presupuesto descalibrado
UMBRAL_SOBRECOSTO = 0.10             # desviacion > +10%: sobrecosto (mismo que las alertas)
UMBRAL_ERROR_PRESUPUESTO_MEDIO = 0.30
UMBRAL_ERROR_PRESUPUESTO_ALTO = 0.60

# Cortes de la Nota, los mismos que clasifican la Evaluacion en
# analisis_financiero (UMBRAL_BUENO=70, UMBRAL_APROBADO=55) y los mismos
# niveles de color que el dashboard: Excelente/Bueno = bueno, Aprobado =
# medio, Requiere atencion = malo.
NIVEL_EVALUACION = {
    "Excelente": "bueno", "Bueno": "bueno",
    "Aprobado": "medio", "Requiere atención": "malo",
}

# Texto de referencia/objetivo del playbook por KPI, para la columna
# "Referencia" de la tabla de Indicadores -- que la tabla se explique sola
# sin depender de leer la pagina 2.
#
# 2026-07-28: se quitó "Rentabilidad sobre costo" (KPI eliminado del
# playbook, era margen/(1-margen) de "Margen neto %" en otra escala -- ver
# CLAUDE.md/MEMORY.md). Se agregó "Desviación % Total" (mismo criterio que
# las desviaciones por categoría) y las 5 entradas de "Ahorro/Sobrecosto"
# (positivo = ahorro es el resultado deseado).
REFERENCIA_KPI = {
    "Margen neto %": f"Objetivo playbook: {OBJETIVO_MARGEN_NETO:.0%}",
    "Margen estimado al cierre %": f"Objetivo playbook: {OBJETIVO_MARGEN_NETO:.0%}",
    "Margen al cierre % (escenario índice de costo)": "Escenario pesimista",
    "Desviación estimada al cierre %": f"Sobrecosto sobre +{UMBRAL_SOBRECOSTO:.0%}",
    "Error del presupuesto %": "Ideal: cercano a 0%",
    "Nota del Proyecto": "Bueno ≥70 · Excelente ≥85",
    "Evaluación": "Clasifica la Nota",
    "Desviación % Materiales": "Ideal: cercano a 0%",
    "Desviación % Equipos": "Ideal: cercano a 0%",
    "Desviación % MO": "Ideal: cercano a 0%",
    "Desviación % Otros": "Ideal: cercano a 0%",
    "Desviación % Total": "Ideal: cercano a 0%",
    "Ahorro/Sobrecosto Materiales": "Ideal: positivo (ahorro)",
    "Ahorro/Sobrecosto Equipos": "Ideal: positivo (ahorro)",
    "Ahorro/Sobrecosto MO": "Ideal: positivo (ahorro)",
    "Ahorro/Sobrecosto Otros": "Ideal: positivo (ahorro)",
    "Ahorro/Sobrecosto Total": "Ideal: positivo (ahorro)",
}


def formatear_moneda(valor: float, decimales: int = 0) -> str:
    """Formato monetario estandar de los reportes: "$" + "." como separador
    de miles (ej. "$1.293.765") -- usar para TODO monto en pesos que
    aparezca en un reporte (tablas de KPIs, prosa de pagina 2), no solo en
    los graficos de graficos.py, para que el formato sea consistente en
    todo el documento."""
    return formatear_valor(valor, decimales, moneda=True)


def estado_kpi(nombre_kpi: str, valor) -> str:
    """Semaforo centralizado de un KPI: "bueno" / "medio" / "malo", o ""
    cuando ese KPI no tiene una direccion definida (Costo % de venta,
    Estructura %, Margen por dia: no hay umbral universal razonable sin
    contexto de categoria o cliente).

    Reemplaza a `es_kpi_fuera_de_rango` (booleano) el 2026-09-24: ese
    criterio pintaba del mismo naranjo un margen muy sobre el objetivo y un
    sobrecosto del 40%, asi que el color no distinguia una buena noticia de
    una mala -- el lector tenia que leer el numero igual. Tambien se saco la
    rama "margen neto >= 1,5x el objetivo = revisar": ese caso (margen alto
    porque faltan costos por registrar) ya lo cubre una alerta explicita de
    `alertas_proyecto` ("Terminado con un costo real de solo X% del
    presupuesto"), que dice el motivo en vez de dejarlo como un color raro.

    Solo devuelve "bueno" en los KPIs de resultado (Nota, Evaluacion,
    margenes): marcar de verde tambien las 9 filas de desviacion/ahorro que
    estan bien diluye la senal -- en esas, lo que se lee es la ausencia de
    rojo."""
    if valor is None or valor == "":
        return ""
    if nombre_kpi == "Evaluación":
        return NIVEL_EVALUACION.get(valor, "")
    if nombre_kpi == "Nota del Proyecto":
        return NIVEL_EVALUACION.get(clasificar_evaluacion(valor), "")
    if nombre_kpi in ("Margen neto %", "Margen estimado al cierre %"):
        if valor < 0:
            return "malo"
        return "bueno" if valor >= OBJETIVO_MARGEN_NETO else "medio"
    if nombre_kpi.startswith("Desviación %") or nombre_kpi == "Desviación estimada al cierre %":
        if valor > UMBRAL_SOBRECOSTO:
            return "malo"
        return "medio" if abs(valor) >= UMBRAL_DESVIACION_ALERTA else ""
    if nombre_kpi.startswith("Ahorro/Sobrecosto"):
        return "malo" if valor < 0 else ""
    if nombre_kpi == "Error del presupuesto %":
        if valor >= UMBRAL_ERROR_PRESUPUESTO_ALTO:
            return "malo"
        return "medio" if valor >= UMBRAL_ERROR_PRESUPUESTO_MEDIO else ""
    return ""


def formatear_porcentaje(valor: float, decimales: int = 1, signo: bool = False) -> str:
    """Porcentaje con coma decimal (convencion chilena): 0.614 -> "61,4%".
    Con `signo=True` antepone "+" a los positivos -- para desviaciones y
    sesgos, donde el signo ES la lectura (sobrecosto vs. ahorro)."""
    texto = formatear_valor(valor * 100, decimales, sufijo="%")
    return f"+{texto}" if signo and valor > 0 else texto


# KPIs en pesos. Se consultan DESPUES del "%" en el nombre: "Margen estimado
# al cierre" es plata y "Margen estimado al cierre %" es porcentaje, y el
# segundo empieza igual que el primero.
_KPIS_EN_PESOS = (
    "Ahorro/Sobrecosto", "Costo estimado al cierre", "Margen estimado al cierre",
    "Margen por día de ejecución", "Total Proyectado", "Total Real",
    "Margen Proyectado", "Margen Real", "Monto de Venta",
    "Venta acumulada", "Margen acumulado",
)


def formatear_kpi(nombre_kpi: str, valor) -> str:
    """Valor de un KPI ya formateado segun su tipo (pesos / porcentaje /
    Nota / texto), deducido del nombre de la columna. Centralizado aca para
    que ningun reporte vuelva a decidir formato caso a caso: la mezcla de
    "$1.293.765" con "1,293,765" en el mismo PDF ya paso una vez."""
    if valor is None or valor == "":
        return "—"
    if nombre_kpi == "Nota del Proyecto":
        return f"{valor:.0f}/100"
    if not isinstance(valor, (int, float)):
        return str(valor)
    if "%" in nombre_kpi:
        return formatear_porcentaje(valor)
    if nombre_kpi.startswith(_KPIS_EN_PESOS):
        return formatear_moneda(valor)
    return formatear_valor(valor, 0)


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


@lru_cache(maxsize=1)
def _texto_template_cc() -> str:
    """El template de Centro de Costos pesa ~1 MB (fuentes y logo en base64)
    y se leia una vez por cada llamada a cargar_font_face_lato /
    cargar_logo_base64 -- 3 lecturas por reporte, 60 en una corrida de 20.
    Se cachea: es un archivo versionado que no cambia dentro de una corrida."""
    return RUTA_TEMPLATE_CC.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def cargar_font_face_lato() -> str:
    """Extrae las 3 reglas @font-face (Lato 400/700/900, base64) desde el
    template del visualizador de Centro de Costos."""
    texto = _texto_template_cc()
    bloques = []
    pos = 0
    for _ in range(3):
        inicio = texto.index("@font-face", pos)
        fin = texto.index("}", inicio) + 1
        bloques.append(texto[inicio:fin])
        pos = fin
    return "\n".join(bloques)


@lru_cache(maxsize=1)
def cargar_logo_base64() -> str:
    """Extrae el data URI completo del logo (data:image/png;base64,...) desde
    el header (.viz-logo) del template del visualizador de Centro de Costos."""
    texto = _texto_template_cc()
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
