# -*- coding: utf-8 -*-
"""
analisis_financiero.py -- Consolidador de costos reales por proyecto para
QUEMPIN SpA. Lee Centro de Costos.xlsx (SOLO LECTURA, nunca lo escribe) y
mantiene Análisis de Proyectos.xlsx (3 hojas: Proyectos, Detalle Costos
Reales, Indicadores). Ver docs/specs/2026-07-20-analisis-
financiero-design.md para el diseño completo.
"""

import json
import math
import re
import shutil
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.styles.colors import Color
from openpyxl.utils import get_column_letter

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────

RAIZ = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ.parent
# Reorganizado 2026-07-21: el código/skill vive en "Sistema Analisis
# Financiero/" (esta carpeta), separado de "Análisis Financiero/" que
# contiene solo el Excel de trabajo -- ambas son carpetas hermanas bajo la
# raíz de Finanzas QUEMPIN/. RAIZ_DATOS apunta a la carpeta con el Excel.
RAIZ_DATOS = RAIZ_MODULO.parent / "Análisis Financiero"
# Renombrado 2026-08-19: "Análisis de Proyectos.xlsx" quedó con un conflicto
# de sincronización de OneDrive sin resolver (generaba un "-QUEMPIN.xlsx" de
# conflicto y revertía cualquier escritura a una versión vieja en la nube) --
# se recreó con nombre nuevo para que OneDrive lo trate como un ítem sin
# historial previo. Ver MEMORY.md.
RUTA_EXCEL = RAIZ_DATOS / "Análisis de Proyectos 2026.xlsx"
RAIZ_RESPALDOS = RAIZ_MODULO / "Respaldos"
RUTA_CLIENTES_PENDIENTES = RAIZ / "clientes_pendientes.json"

RAIZ_CENTRO_COSTOS = RAIZ_MODULO.parent / "Centro de Costos"
RUTA_EXCEL_CENTRO_COSTOS = RAIZ_CENTRO_COSTOS / "Excel" / "Centro de Costos.xlsx"
# Snapshot saneado que produce el visualizador de Centro de Costos (PASO 12c,
# justo antes de que corra este modulo en 12d). Trae exactamente los mismos
# datos que se leian del .xlsx -- verificado: 1.406 items, 776 grupos
# (N Ref, categoria) y el mismo total al centavo -- pero cuesta ~20 ms de
# json.loads en vez de ~0,5 s de openpyxl. Se usa solo si esta al dia; si no,
# se cae al Excel (ver cargar_datos_centro_costos).
RUTA_SNAPSHOT_CENTRO_COSTOS = (
    RAIZ_CENTRO_COSTOS / "Visualizador Web" / "data" / "centro-de-costos.json"
)
RAIZ_FACTURAS_CENTRO_COSTOS = (
    RAIZ_CENTRO_COSTOS / "Sitio de comunicación - Centro de Costos 1" / "Facturas y Boletas" / "Chile"
)

RAIZ_VISUALIZADOR_WEB_AF = RAIZ_MODULO / "Visualizador Web"

# Canal de entrada desde el Formulador de proyectos por la carpeta de
# Intercambio (2026-09-30): costos proyectados que el Formulador envía para
# un TAG. Lógica y garantías en presupuestos_formulador.py (junto a este
# archivo); el protocolo común, en "Sistema Intercambio/intercambio.py".
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
import presupuestos_formulador as pf  # noqa: E402

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
        # Intercambio con el Formulador (Chile: el Formulador trabaja en CLP).
        # Un país ficticio de pruebas debe sobrescribir estas dos rutas.
        # None si la biblioteca de Formulación no está sincronizada aquí.
        "raiz_intercambio": pf.RAIZ_INTERCAMBIO,
        "ruta_estado_intercambio": pf.RUTA_ESTADO,
        "aviso_sin_intercambio": None if pf.RAIZ_INTERCAMBIO else pf.AVISO_SIN_INTERCAMBIO,
    },
    "PE": {
        "ruta_excel_af": RAIZ_PERU / "Análisis Financiero" / "Análisis de Proyectos Perú.xlsx",
        "ruta_excel_cc": RAIZ_PERU / "Centro de Costos" / "Excel" / "Centro de Costos Perú.xlsx",
        "raiz_facturas_cc": (
            RAIZ_CENTRO_COSTOS / "Sitio de comunicación - Centro de Costos 1" / "Facturas y Boletas" / "Perú"
        ),
        "raiz_visualizador_web": RAIZ_PERU / "Análisis Financiero" / "Visualizador Web",
        "col_total_sin_iva_cc": "Total sin IGV (PEN)",
        "raiz_intercambio": None,
        "ruta_estado_intercambio": None,
    },
}

HOJA_PROYECTOS = "Proyectos"
HOJA_DETALLE_COSTOS_REALES = "Detalle Costos Reales"
HOJA_INDICADORES = "Indicadores"
HOJA_CLIENTES = "Clientes"
HOJA_GLOSARIO_KPIS = "Glosario KPIs"

# "Categoría" (= "Tipo de Proyecto" más frecuente en Centro de Costos, ver
# leer_tipo_proyecto_centro_costos) que marca un bucket de gastos internos de
# la empresa, no una venta a un cliente real -- nunca tiene Monto de Venta ni
# tiene sentido evaluarlo por rentabilidad. Excluido de la hoja "Clientes"
# (asegurar_hoja_clientes) y de Nota/Evaluación en "Indicadores"
# (2026-08-20, a pedido del usuario: "Gastos Generales" aparecía como
# pseudo-cliente con CLTV sin sentido).
CATEGORIA_GASTOS_GENERALES = "Gastos Generales"

HEADERS_PROYECTOS = [
    "TAG proyecto", "Nombre del proyecto", "Cliente", "Categoría", "% Avance",
    "Fecha de inicio", "Fecha de cierre", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados",
    "Costos Materiales Reales", "Costos Equipos Reales",
    "Otros Costos Reales", "Mano de Obra Real", "Total Proyectado",
    "Total Real", "Margen Proyectado", "Margen Real",
    "Desviación % (Real vs Proyectado)",
]
HEADERS_DETALLE_COSTOS_REALES = [
    "TAG proyecto", "Subcategoría", "Bucket", "Total sin IVA",
    "% del Total Real del proyecto",
]
# Playbook depurado 2026-07-28: se eliminaron "Rentabilidad sobre costo" y las
# 4 "Productividad" (Materiales/Equipos/MO/Otros) -- eran redundancias
# matemáticas exactas de "Margen neto %" y de "Costo % de venta" (ver
# CLAUDE.md, sección "Playbook de KPIs", y MEMORY.md 2026-07-28). Se agregaron
# 4 KPIs nuevos: Estructura % del costo real (mix, suma 100%), Desviación %
# Total (ya existía en "Proyectos", ahora también visible acá), y
# Ahorro/Sobrecosto neto en $ por categoría y total.
HEADERS_INDICADORES = [
    "TAG proyecto", "Nombre del proyecto", "Margen neto %",
    "Costo Materiales % de venta", "Costo Equipos % de venta",
    "Costo MO % de venta", "Costo Otros % de venta",
    "Estructura % Materiales", "Estructura % Equipos", "Estructura % MO",
    "Estructura % Otros",
    "Desviación % Materiales", "Desviación % Equipos", "Desviación % MO",
    "Desviación % Otros", "Desviación % Total",
    "Ahorro/Sobrecosto Materiales", "Ahorro/Sobrecosto Equipos",
    "Ahorro/Sobrecosto MO", "Ahorro/Sobrecosto Otros",
    "Ahorro/Sobrecosto Total",
    "Nota del Proyecto", "Evaluación",
    # 2 KPIs nuevos agregados 2026-07-28 (aprobados por el usuario; un
    # tercero propuesto, "Cumplimiento de plazo", quedó fuera a propósito
    # porque necesitaba un dato manual nuevo que el usuario decidió no
    # agregar por ahora -- ver MEMORY.md).
    "Peso del proyecto en la cartera de ventas (%)",
    "Margen por día de ejecución",
    # 2026-09-21 (auditoría, fase 1): la "Nota Parcial" (Nota x % Avance) se
    # reemplazó por la estimación al cierre -- castigaba el avance, no el
    # riesgo, y no avisaba de un proyecto a medio camino con el presupuesto ya
    # agotado. La Nota del Proyecto se calcula ahora sobre estas columnas.
    "Costo estimado al cierre", "Margen estimado al cierre",
    "Margen estimado al cierre %", "Desviación estimada al cierre %",
    "Margen al cierre % (escenario índice de costo)",
    # Fase 2 de la auditoría (2026-09-21): cuánto se equivocó el presupuesto
    # POR CATEGORÍA, sin que los errores se cancelen entre sí en el total.
    "Error del presupuesto %",
    # Columnas de apoyo para que la hoja "Clientes" sume solo proyectos con
    # los datos completos, igual que el dashboard y los reportes (antes el
    # Excel sumaba también proyectos a medio cargar).
    "Cliente", "Monto de Venta (sin IVA)", "Datos completos",
]
# Reemplaza AOV/Vida/Meses activo/Frecuencia/CLTV (2026-09-21, ver
# calcular_clientes para el porqué).
HEADERS_CLIENTES = [
    "Cliente", "N° de proyectos", "Venta acumulada (sin IVA)",
    "Margen acumulado", "Margen %", "Cliente recurrente", "Clasificación",
]
HEADERS_GLOSARIO_KPIS = [
    "KPI", "Por qué importa", "Qué elementos usa", "Qué significa el resultado",
]

# Letra de columna de "Proyectos" por nombre de encabezado -- centraliza el
# mapeo para que las fórmulas nunca hardcodeen letras directamente (si el
# orden de HEADERS_PROYECTOS cambia, las fórmulas se recalculan solas).
LETRA_COL_PROYECTOS = {
    nombre: get_column_letter(idx) for idx, nombre in enumerate(HEADERS_PROYECTOS, start=1)
}
# Mismo patrón para "Indicadores" -- las fórmulas de Nota/Evaluación
# referencian columnas de esta misma hoja (no de "Proyectos") y no pueden
# hardcodear la letra, para no romperse si el playbook de KPIs cambia de
# nuevo (ya pasó una vez, 2026-07-28: se sacaron 5 columnas y se agregaron 9).
LETRA_COL_INDICADORES = {
    nombre: get_column_letter(idx) for idx, nombre in enumerate(HEADERS_INDICADORES, start=1)
}


# ── ESTILO VISUAL ────────────────────────────────────────────────────────────
# Formato que el usuario armó a mano en "Proyectos" (encabezado en negrita,
# centrado, con wrap, relleno por color de theme según grupo de columna,
# formato moneda/porcentaje) -- replicado acá para que se mantenga en cada
# corrida y se extienda a "Detalle Costos Reales" e "Indicadores", que hasta
# 2026-07-21 quedaban 100% regeneradas sin ningún estilo.

ALTURA_FILA_ENCABEZADO = 46.2
FUENTE_ENCABEZADO = Font(name="Calibri", size=11, bold=True)
ALINEACION_ENCABEZADO = Alignment(vertical="center", wrap_text=True)

FORMATO_MONEDA = '_ "$"* #,##0_ ;_ "$"* \\-#,##0_ ;_ "$"* "-"_ ;_ @_ '
FORMATO_PORCENTAJE = "0.0%"
FORMATO_RATIO = "0.00"
FORMATO_ENTERO = "0"
# Formato fijo DD-MM-AAAA para columnas de fecha -- pedido del usuario 2026-07-28,
# mismo estandar que Centro de Costos (ver DATE_FORMAT en auditor_centro_costos.py).
FORMATO_FECHA = "DD-MM-YYYY"


def _color_tema(theme: int, tint: float) -> Color:
    return Color(theme=theme, tint=tint)


# Mismos 4 colores que ya usaba "Proyectos" a mano, uno por grupo semántico
# de columna -- se reutilizan en las 3 hojas para que el libro se lea como
# un solo sistema visual.
COLOR_IDENTIFICACION = _color_tema(5, 0.3999755851924192)    # TAG/Nombre/% Avance/fechas/venta
COLOR_COSTO_PROYECTADO = _color_tema(8, 0.3999755851924192)  # columnas "...Proyectado(s)"
COLOR_COSTO_REAL = _color_tema(9, 0.3999755851924192)        # columnas "...Real(es)"
COLOR_DERIVADO = _color_tema(3, 0.499984740745262)           # totales, márgenes, KPIs finales

# Por nombre de encabezado, no por letra -- se convierte a letra-keyed más
# abajo vía LETRA_COL_PROYECTOS. Evita el bug real que ya pasó el 2026-07-28
# al reordenar el playbook de Indicadores (ver asegurar_estructura_workbook):
# un dict hardcodeado por letra queda mal alineado apenas cambia el orden de
# HEADERS_PROYECTOS (ej. al mover "Categoría" junto a "Cliente").
ESTILO_COLUMNAS_PROYECTOS_POR_NOMBRE = {
    "TAG proyecto": (COLOR_IDENTIFICACION, None, 10),
    "Nombre del proyecto": (COLOR_IDENTIFICACION, None, 22),
    "Cliente": (COLOR_IDENTIFICACION, None, 22),
    "Categoría": (COLOR_IDENTIFICACION, None, 16),
    "% Avance": (COLOR_IDENTIFICACION, FORMATO_PORCENTAJE, 13),
    "Fecha de inicio": (COLOR_IDENTIFICACION, FORMATO_FECHA, 13),
    "Fecha de cierre": (COLOR_IDENTIFICACION, FORMATO_FECHA, 13),
    "Monto de Venta (sin IVA)": (COLOR_IDENTIFICACION, FORMATO_MONEDA, 16),
    "Costos Materiales Proyectados": (COLOR_COSTO_PROYECTADO, FORMATO_MONEDA, 14),
    "Costos Equipos Proyectados": (COLOR_COSTO_PROYECTADO, FORMATO_MONEDA, 14),
    "Mano de Obra Proyectada": (COLOR_COSTO_PROYECTADO, FORMATO_MONEDA, 14),
    "Otros Costos Proyectados": (COLOR_COSTO_PROYECTADO, FORMATO_MONEDA, 14),
    "Costos Materiales Reales": (COLOR_COSTO_REAL, FORMATO_MONEDA, 14),
    "Costos Equipos Reales": (COLOR_COSTO_REAL, FORMATO_MONEDA, 14),
    "Otros Costos Reales": (COLOR_COSTO_REAL, FORMATO_MONEDA, 14),
    "Mano de Obra Real": (COLOR_COSTO_REAL, FORMATO_MONEDA, 14),
    "Total Proyectado": (COLOR_DERIVADO, FORMATO_MONEDA, 14),
    "Total Real": (COLOR_DERIVADO, FORMATO_MONEDA, 14),
    "Margen Proyectado": (COLOR_DERIVADO, FORMATO_MONEDA, 14),
    "Margen Real": (COLOR_DERIVADO, FORMATO_MONEDA, 14),
    "Desviación % (Real vs Proyectado)": (COLOR_DERIVADO, FORMATO_PORCENTAJE, 16),
}
# columna (letra) -> (color de encabezado, formato numérico o None, ancho sugerido)
ESTILO_COLUMNAS_PROYECTOS = {
    LETRA_COL_PROYECTOS[nombre]: estilo
    for nombre, estilo in ESTILO_COLUMNAS_PROYECTOS_POR_NOMBRE.items()
}

ESTILO_COLUMNAS_DETALLE_COSTOS_REALES = {
    "A": (COLOR_IDENTIFICACION, None, 10),
    "B": (COLOR_COSTO_REAL, None, 22),
    "C": (COLOR_COSTO_REAL, None, 13),
    "D": (COLOR_COSTO_REAL, FORMATO_MONEDA, 14),
    "E": (COLOR_DERIVADO, FORMATO_PORCENTAJE, 18),
}

# Por nombre de encabezado, no por letra (2026-09-21) -- mismo motivo que
# ESTILO_COLUMNAS_PROYECTOS_POR_NOMBRE: la fase 1 de la auditoría sacó una
# columna y agregó ocho, y un dict por letra habría quedado desalineado.
_ESTILO_INDICADORES_POR_NOMBRE = {
    "TAG proyecto": (COLOR_IDENTIFICACION, None, 10),
    "Nombre del proyecto": (COLOR_IDENTIFICACION, None, 22),
    "Margen neto %": (COLOR_DERIVADO, FORMATO_PORCENTAJE, 16),
    **{f"Costo {c} % de venta": (COLOR_COSTO_REAL, FORMATO_PORCENTAJE, 14)
       for c in ("Materiales", "Equipos", "MO", "Otros")},
    **{f"Estructura % {c}": (COLOR_COSTO_REAL, FORMATO_PORCENTAJE, 14)
       for c in ("Materiales", "Equipos", "MO", "Otros")},
    **{f"Desviación % {c}": (COLOR_COSTO_PROYECTADO, FORMATO_PORCENTAJE, 14)
       for c in ("Materiales", "Equipos", "MO", "Otros")},
    "Desviación % Total": (COLOR_COSTO_PROYECTADO, FORMATO_PORCENTAJE, 16),
    **{f"Ahorro/Sobrecosto {c}": (COLOR_DERIVADO, FORMATO_MONEDA, 16)
       for c in ("Materiales", "Equipos", "MO", "Otros", "Total")},
    "Nota del Proyecto": (COLOR_DERIVADO, FORMATO_ENTERO, 12),
    "Evaluación": (COLOR_DERIVADO, None, 20),
    "Peso del proyecto en la cartera de ventas (%)": (COLOR_DERIVADO, FORMATO_PORCENTAJE, 18),
    "Margen por día de ejecución": (COLOR_DERIVADO, FORMATO_MONEDA, 18),
    "Costo estimado al cierre": (COLOR_DERIVADO, FORMATO_MONEDA, 16),
    "Margen estimado al cierre": (COLOR_DERIVADO, FORMATO_MONEDA, 16),
    "Margen estimado al cierre %": (COLOR_DERIVADO, FORMATO_PORCENTAJE, 16),
    "Desviación estimada al cierre %": (COLOR_COSTO_PROYECTADO, FORMATO_PORCENTAJE, 16),
    "Margen al cierre % (escenario índice de costo)": (COLOR_DERIVADO, FORMATO_PORCENTAJE, 18),
    "Error del presupuesto %": (COLOR_COSTO_PROYECTADO, FORMATO_PORCENTAJE, 16),
    "Cliente": (COLOR_IDENTIFICACION, None, 22),
    "Monto de Venta (sin IVA)": (COLOR_IDENTIFICACION, FORMATO_MONEDA, 16),
    "Datos completos": (COLOR_IDENTIFICACION, None, 12),
}
ESTILO_COLUMNAS_INDICADORES = {
    LETRA_COL_INDICADORES[nombre]: estilo
    for nombre, estilo in _ESTILO_INDICADORES_POR_NOMBRE.items()
}

ESTILO_COLUMNAS_CLIENTES = {
    get_column_letter(HEADERS_CLIENTES.index(nombre) + 1): estilo
    for nombre, estilo in {
        "Cliente": (COLOR_IDENTIFICACION, None, 22),
        "N° de proyectos": (COLOR_DERIVADO, FORMATO_ENTERO, 12),
        "Venta acumulada (sin IVA)": (COLOR_DERIVADO, FORMATO_MONEDA, 18),
        "Margen acumulado": (COLOR_DERIVADO, FORMATO_MONEDA, 18),
        "Margen %": (COLOR_DERIVADO, FORMATO_PORCENTAJE, 12),
        "Cliente recurrente": (COLOR_DERIVADO, None, 12),
        "Clasificación": (COLOR_DERIVADO, None, 22),
    }.items()
}

ESTILO_COLUMNAS_GLOSARIO_KPIS = {
    "A": (COLOR_IDENTIFICACION, None, 30),
    "B": (COLOR_IDENTIFICACION, None, 50),
    "C": (COLOR_IDENTIFICACION, None, 40),
    "D": (COLOR_IDENTIFICACION, None, 50),
}


def aplicar_estilo_visual(wb) -> None:
    """Aplica a las 3 hojas el mismo lenguaje visual que el usuario armó a
    mano en 'Proyectos': encabezado en negrita, centrado y con wrap, alto de
    fila 46.2, relleno por color de theme según grupo de columna, y formato
    moneda/porcentaje/ratio en las columnas correspondientes. Solo toca
    estilo, nunca valores; el ancho de columna se deja intacto si el usuario
    ya lo fijó a mano (no se sobrescribe una vez seteado)."""
    for nombre_hoja, estilo_columnas in (
        (HOJA_PROYECTOS, ESTILO_COLUMNAS_PROYECTOS),
        (HOJA_DETALLE_COSTOS_REALES, ESTILO_COLUMNAS_DETALLE_COSTOS_REALES),
        (HOJA_INDICADORES, ESTILO_COLUMNAS_INDICADORES),
        (HOJA_CLIENTES, ESTILO_COLUMNAS_CLIENTES),
        (HOJA_GLOSARIO_KPIS, ESTILO_COLUMNAS_GLOSARIO_KPIS),
    ):
        ws = wb[nombre_hoja]
        ws.row_dimensions[1].height = ALTURA_FILA_ENCABEZADO
        for columna, (color, formato_numero, ancho) in estilo_columnas.items():
            # ws.column_dimensions[columna] autovivifica la entrada con un
            # width por defecto (13.0) apenas se accede -- por eso el "ya
            # tiene ancho manual" se revisa ANTES de tocar la columna, con
            # el operador "in" sobre el dict, no con ".width is None".
            ya_tenia_ancho_manual = columna in ws.column_dimensions
            celda_encabezado = ws[f"{columna}1"]
            celda_encabezado.font = FUENTE_ENCABEZADO
            celda_encabezado.alignment = ALINEACION_ENCABEZADO
            celda_encabezado.fill = PatternFill(fgColor=color, fill_type="solid")
            if formato_numero is not None:
                ws.column_dimensions[columna].number_format = formato_numero
            if not ya_tenia_ancho_manual:
                ws.column_dimensions[columna].width = ancho


# ── RESALTADO DE CELDAS DE INGRESO MANUAL ("Proyectos") ─────────────────────
# Pedido del usuario (2026-07-28): que las celdas que se llenan a mano nunca
# se confundan con las de fórmula/autocompletado. "Cliente" y "Categoría"
# quedan afuera aunque viven en el mismo bloque que nunca se reescribe entre
# corridas (asegurar_formulas_proyectos) -- se autocompletan solas
# (asegurar_columna_cliente / asegurar_categoria_proyectos) y ya tienen su
# propio lenguaje visual (rojo/azul marino). Las columnas L/M/N/P-T tampoco
# entran: son 100% fórmula (Materiales/Equipos/Otros Reales, Total
# Proyectado/Real, Margen Proyectado/Real, Desviación %).
NOMBRES_COLUMNAS_MANUALES_PROYECTOS = [
    "TAG proyecto", "Nombre del proyecto", "% Avance", "Fecha de inicio",
    "Fecha de cierre", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados", "Mano de Obra Real",
]
COLOR_RESALTADO_MANUAL = "FFF2CC"  # amarillo pastel -- no se reutiliza en ningún otro relleno del libro
FUENTE_RESALTADO_MANUAL = Font(name="Calibri", size=11, italic=True)
FILAS_MINIMAS_RESALTADO_MANUAL = 60  # deja filas vacías pre-formateadas como plantilla aunque el libro no tenga proyectos cargados todavía
BUFFER_FILAS_RESALTADO_MANUAL = 20   # margen de filas nuevas pre-formateadas más allá de la última fila con datos reales
LEYENDA_RESALTADO_MANUAL = (
    "Relleno amarillo + cursiva = ingreso manual.\nSin relleno = fórmula o "
    "autocompletado (Cliente, Categoría) -- no editar a mano."
)


def migrar_formato_fecha_proyectos(wb) -> None:
    """Migracion de formato (idempotente, 2026-07-28, mismo patron que
    migrar_formato_fecha_corta de Centro de Costos): fuerza FORMATO_FECHA
    celda por celda en 'Fecha de inicio'/'Fecha de cierre' de TODAS las
    filas ya escritas de 'Proyectos'. Necesario porque el number_format a
    nivel de columna (aplicar_estilo_visual, via ws.column_dimensions) NO
    pisa el formato que Excel ya asigno a una celda cuando el usuario
    escribio la fecha a mano -- el formato por celda gana sobre el de
    columna para cualquier celda que ya tenga uno propio. Es formato, no
    contenido: no toca valores, misma excepcion a la regla de oro que el
    resaltado de celdas manuales de abajo."""
    ws = wb[HOJA_PROYECTOS]
    col_tag = LETRA_COL_PROYECTOS["TAG proyecto"]
    letras_fecha = [LETRA_COL_PROYECTOS["Fecha de inicio"], LETRA_COL_PROYECTOS["Fecha de cierre"]]

    for fila in range(2, ws.max_row + 1):
        if ws[f"{col_tag}{fila}"].value is None:
            continue
        for letra in letras_fecha:
            ws[f"{letra}{fila}"].number_format = FORMATO_FECHA


def aplicar_resaltado_celdas_manuales(wb) -> None:
    """Rellena de amarillo + cursiva las columnas de ingreso manual de
    'Proyectos' (ver NOMBRES_COLUMNAS_MANUALES_PROYECTOS), en un rango que
    siempre cubre al menos FILAS_MINIMAS_RESALTADO_MANUAL filas (para que el
    libro sirva de plantilla incluso sin proyectos cargados) y se extiende
    BUFFER_FILAS_RESALTADO_MANUAL más allá de la última fila con TAG real --
    calculado leyendo valores de la columna A, nunca ws.max_row a secas (que
    quedaría inflado por el relleno ya aplicado en corridas previas y
    crecería sin límite en cada corrida). Nunca toca valores, solo relleno/
    fuente -- se reaplica en cada corrida igual que aplicar_estilo_visual."""
    ws = wb[HOJA_PROYECTOS]
    col_tag = LETRA_COL_PROYECTOS["TAG proyecto"]

    ultima_fila_con_datos = 1
    for fila in range(2, ws.max_row + 1):
        if ws[f"{col_tag}{fila}"].value is not None:
            ultima_fila_con_datos = fila

    ultima_fila = max(
        FILAS_MINIMAS_RESALTADO_MANUAL, ultima_fila_con_datos + BUFFER_FILAS_RESALTADO_MANUAL
    )
    relleno = PatternFill(fgColor=COLOR_RESALTADO_MANUAL, fill_type="solid")
    letras = [LETRA_COL_PROYECTOS[nombre] for nombre in NOMBRES_COLUMNAS_MANUALES_PROYECTOS]

    for letra in letras:
        for fila in range(2, ultima_fila + 1):
            celda = ws[f"{letra}{fila}"]
            celda.fill = relleno
            celda.font = FUENTE_RESALTADO_MANUAL

    col_leyenda = len(HEADERS_PROYECTOS) + 1
    celda_leyenda = ws.cell(row=1, column=col_leyenda)
    celda_leyenda.value = LEYENDA_RESALTADO_MANUAL
    celda_leyenda.font = Font(name="Calibri", size=9, italic=True, color="808080")
    celda_leyenda.alignment = Alignment(wrap_text=True, vertical="center")
    letra_leyenda = get_column_letter(col_leyenda)
    if letra_leyenda not in ws.column_dimensions:
        ws.column_dimensions[letra_leyenda].width = 45


def asegurar_estructura_workbook(ruta_excel: Path) -> openpyxl.Workbook:
    """Abre ruta_excel si existe, o crea un libro nuevo. Garantiza que las 5
    hojas existan con encabezados en la fila 1.

    "Proyectos" es la única hoja con datos MANUALES del usuario: nunca se
    pisa un encabezado ya escrito ahí, solo se completan columnas nuevas al
    final del esquema (ej. "Cliente" en un archivo real creado antes de que
    esa columna existiera) -- regla de oro del módulo.

    Las otras 4 hojas ("Detalle Costos Reales"/"Indicadores"/"Clientes"/
    "Glosario KPIs") son 100% regeneradas cada corrida -- sus DATOS ya se
    reescriben completos en cada `ejecutar()` (ver regenerar_hoja_detalle_
    costos_reales / asegurar_hoja_indicadores / etc.), así que su fila de
    encabezados también se reescribe completa acá si no coincide con el
    esquema actual (incluye borrar columnas sobrantes si el esquema nuevo
    tiene menos columnas que el anterior). **Bug real encontrado y corregido
    2026-07-28**: antes esta función usaba el mismo criterio "solo llenar
    vacíos" para las 5 hojas -- al reordenar/depurar el playbook de KPIs de
    "Indicadores" (quitar 5 columnas, agregar 9, reordenar el resto), los
    encabezados viejos quedaron pisando columnas con fórmulas del esquema
    NUEVO (ej. columna C decía "Rentabilidad sobre costo" pero tenía la
    fórmula de "Margen neto %"), y aparecieron "Nota del Proyecto"/
    "Evaluación" duplicados en las columnas nuevas del final -- un archivo
    financiero real quedó con encabezados y datos desalineados. Se corrió
    contra el Excel real antes de detectarse (restaurado desde backup) --
    ver MEMORY.md 2026-07-28 para el detalle completo del incidente."""
    if ruta_excel.exists():
        wb = openpyxl.load_workbook(ruta_excel)
    else:
        wb = openpyxl.Workbook()

    for nombre_hoja, headers in (
        (HOJA_PROYECTOS, HEADERS_PROYECTOS),
        (HOJA_DETALLE_COSTOS_REALES, HEADERS_DETALLE_COSTOS_REALES),
        (HOJA_INDICADORES, HEADERS_INDICADORES),
        (HOJA_CLIENTES, HEADERS_CLIENTES),
        (HOJA_GLOSARIO_KPIS, HEADERS_GLOSARIO_KPIS),
    ):
        ws = wb[nombre_hoja] if nombre_hoja in wb.sheetnames else wb.create_sheet(nombre_hoja)
        if nombre_hoja == HOJA_PROYECTOS:
            for col, encabezado in enumerate(headers, start=1):
                if ws.cell(row=1, column=col).value is None:
                    ws.cell(row=1, column=col, value=encabezado)
            continue

        max_col_previo = ws.max_column if ws.max_row >= 1 else 0
        for col in range(1, max(max_col_previo, len(headers)) + 1):
            nuevo_valor = headers[col - 1] if col <= len(headers) else None
            celda = ws.cell(row=1, column=col)
            if celda.value != nuevo_valor:
                celda.value = nuevo_valor
            if col > len(headers):
                # Columna que el esquema nuevo ya no tiene: sin esto quedaba un
                # encabezado vacío pero todavía pintado (ej. la 8ª columna de
                # "Clientes" al pasar de 8 a 7 columnas, 2026-09-21).
                celda.fill = PatternFill(fill_type=None)

    for nombre_default in ("Hoja1", "Sheet"):
        if nombre_default in wb.sheetnames:
            ws_default = wb[nombre_default]
            esta_vacia = all(
                celda.value is None
                for fila in ws_default.iter_rows()
                for celda in fila
            )
            if esta_vacia:
                del wb[nombre_default]

    return wb


# ── MAPEO DE CATEGORÍAS ──────────────────────────────────────────────────────

# Ampliado 2026-09-21 (auditoría, fase 1 -- decisión del usuario): Ferretería
# resultó ser casi todo material de obra (válvulas, cañerías, fittings) y
# Arriendo casi todo arriendo de equipos (camiones, vehículos, andamios), pero
# caían en "Otros" -- así la desviación por categoría comparaba el presupuesto
# de Materiales/Equipos contra un real al que le faltaba parte de su gasto.
# "Herramientas" es la misma cosa que "Equipos-Herramientas" escrita distinto.
# "Servicios" (subcontratos, incluida mano de obra subcontratada) queda en
# "Otros" a propósito: "Mano de Obra Real" es manual y moverlo ahí la contaría
# dos veces si ya lo incluye. El total y el margen de cada proyecto no cambian,
# solo su reparto entre categorías.
MAPEO_CATEGORIA_BUCKET = {
    "Materiales": "Materiales",
    "Consumibles": "Materiales",
    "Ferretería": "Materiales",
    "Reposición de Material": "Materiales",
    "Equipos-Herramientas": "Equipos",
    "Herramientas": "Equipos",
    "Arriendo": "Equipos",
    # "Otros" explícito (misma fecha): son gastos indirectos que ya caían ahí,
    # y declararlos evita que cada corrida avise ~50 veces "sin mapeo
    # explícito" -- el aviso queda solo para subcategorías nuevas de verdad.
    "Servicios": "Otros",
    "Combustible": "Otros",
    "Transporte": "Otros",
    "Alimentación": "Otros",
    "Viáticos/Alojamiento": "Otros",
    "Despachos": "Otros",
    "Seguridad Industrial": "Otros",
    "Oficina": "Otros",
    "Descuento": "Otros",
}


def mapear_categoria_a_bucket(categoria_item: str | None) -> tuple[str, bool]:
    """Devuelve (bucket, es_mapeo_explicito). Cualquier categoria_item que no
    esté en MAPEO_CATEGORIA_BUCKET (incluyendo None) cae en "Otros" con
    es_mapeo_explicito=False, para poder avisar sin perder el monto."""
    if categoria_item in MAPEO_CATEGORIA_BUCKET:
        return MAPEO_CATEGORIA_BUCKET[categoria_item], True
    return "Otros", False


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
    paréntesis, devuelve el nombre completo tal cual.

    Quita además el código numérico de carpeta ("261. FACH 1" -> "FACH 1"),
    con la misma regla que normalizar_nombre_proyecto_carpeta: en la planilla
    real quedó un cliente "261. FACH 1" heredado del nombre de carpeta, que
    ningún otro proyecto del mismo cliente iba a igualar nunca."""
    candidato = nombre_proyecto.split("(")[0].strip()
    candidato = re.sub(r"^\d+[.\-_]\s*", "", candidato).strip()
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


# ── LECTURA DE CENTRO DE COSTOS (SOLO LECTURA) ───────────────────────────────

def prefijo_de_n_ref(n_ref: str) -> str:
    """'UMAG-001' -> 'UMAG'. Mismo prefijo que PREFIJOS_PROYECTO en
    Centro de Costos/Sistema/auditor_centro_costos.py."""
    return n_ref.split("-")[0]


def leer_detalle_centro_costos(ruta_excel_cc: Path, pais: str = "CL", wb=None) -> list[dict]:
    """Lee la hoja 'Detalle' de Centro de Costos.xlsx -- SOLO LECTURA, este
    módulo nunca escribe ese archivo. Filas sin N° Ref. o sin Total sin IVA
    se ignoran (no se puede agrupar ni sumar sin esos dos datos).

    'pais' selecciona el nombre de la columna de total via PAISES -- "CL"
    preserva exactamente el comportamiento anterior a este parametro."""
    col_total_nombre = PAISES[pais]["col_total_sin_iva_cc"]
    wb = wb if wb is not None else openpyxl.load_workbook(ruta_excel_cc, data_only=True)
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


def leer_tipo_proyecto_centro_costos(ruta_excel_cc: Path, wb=None) -> dict[str, str]:
    """Lee la hoja 'Master' de Centro de Costos.xlsx (SOLO LECTURA) y devuelve,
    por prefijo de proyecto, el 'Tipo de Proyecto' más frecuente entre sus
    documentos. Filas sin N° Ref. o sin Tipo de Proyecto se ignoran. Si la
    hoja 'Master' no existe, devuelve dict vacío."""
    wb = wb if wb is not None else openpyxl.load_workbook(ruta_excel_cc, data_only=True)
    if "Master" not in wb.sheetnames:
        return {}
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


def leer_nombres_proyecto_centro_costos(ruta_excel_cc: Path, wb=None) -> dict[str, str]:
    """Lee la hoja 'Master' de Centro de Costos.xlsx (SOLO LECTURA) y devuelve,
    por prefijo de proyecto, el 'Proyecto' (nombre completo) más frecuente
    entre sus documentos -- mismo patrón que leer_tipo_proyecto_centro_costos.
    Filas sin N° Ref. o sin Proyecto se ignoran. Si la hoja 'Master' no
    existe, devuelve dict vacío."""
    wb = wb if wb is not None else openpyxl.load_workbook(ruta_excel_cc, data_only=True)
    if "Master" not in wb.sheetnames:
        return {}
    ws = wb["Master"]
    encabezados = [celda.value for celda in ws[1]]
    col_n_ref = encabezados.index("N° Ref.") + 1
    col_proyecto = encabezados.index("Proyecto") + 1

    nombres_por_prefijo: dict[str, Counter] = {}
    for fila in ws.iter_rows(min_row=2):
        n_ref = fila[col_n_ref - 1].value
        nombre = fila[col_proyecto - 1].value
        if not n_ref or not nombre:
            continue
        prefijo = prefijo_de_n_ref(n_ref)
        nombres_por_prefijo.setdefault(prefijo, Counter())[nombre] += 1

    return {
        prefijo: contador.most_common(1)[0][0]
        for prefijo, contador in nombres_por_prefijo.items()
    }


def _mas_frecuente_por_prefijo(documentos, campo):
    """{prefijo de N Ref: valor mas frecuente de 'campo' entre sus documentos}.
    Mismo criterio que usan leer_tipo_proyecto_centro_costos y
    leer_nombres_proyecto_centro_costos sobre la hoja Master."""
    por_prefijo: dict[str, Counter] = {}
    for doc in documentos:
        n_ref, valor = doc.get("ref"), doc.get(campo)
        if not n_ref or not valor:
            continue
        por_prefijo.setdefault(prefijo_de_n_ref(n_ref), Counter())[valor] += 1
    return {p: c.most_common(1)[0][0] for p, c in por_prefijo.items()}


def snapshot_al_dia(ruta_snapshot=None, ruta_excel=None) -> bool:
    """True si el snapshot de Centro de Costos refleja el libro actual.

    El criterio es la fecha de modificacion: el snapshot lo escribe el
    visualizador de Centro de Costos (PASO 12c) leyendo el .xlsx recien
    guardado (PASO 12), asi que en una cadena normal queda mas nuevo. Si
    alguien edito el Excel a mano despues -- o el visualizador fallo -- el
    snapshot queda viejo y NO se puede usar: costos desactualizados en los
    KPIs serian peores que unos decimos de segundo de mas.
    """
    ruta_snapshot = ruta_snapshot or RUTA_SNAPSHOT_CENTRO_COSTOS
    ruta_excel = ruta_excel or RUTA_EXCEL_CENTRO_COSTOS
    if not ruta_snapshot.exists() or not ruta_excel.exists():
        return False
    return ruta_snapshot.stat().st_mtime >= ruta_excel.stat().st_mtime


def leer_centro_costos_desde_snapshot(ruta_snapshot=None, pais: str = "CL"):
    """Las tres lecturas que este modulo necesita de Centro de Costos, sacadas
    del snapshot JSON en vez del .xlsx. Devuelve
    (items_detalle, tipos_por_prefijo, nombres_por_prefijo) o None si el
    snapshot no sirve (no existe, esta corrupto o le falta alguna clave).

    Equivalencia verificada contra la lectura por openpyxl sobre los datos
    reales: 1.406 items, 776 grupos (N Ref, categoria item) y el mismo total
    al centavo, mas los dos mapas por prefijo identicos. El snapshot ya viene
    saneado por el visualizador, que descarta las mismas filas que
    descartaba leer_detalle_centro_costos (sin N Ref o sin total).

    'pais' se acepta por simetria con leer_detalle_centro_costos pero no
    cambia nada: el snapshot solo existe para Chile (Peru tiene el suyo, con
    su propio visualizador) y ya trae los montos en su moneda.
    """
    ruta_snapshot = ruta_snapshot or RUTA_SNAPSHOT_CENTRO_COSTOS
    try:
        datos = json.loads(ruta_snapshot.read_text(encoding="utf-8"))
        documentos = datos["documentos"]
        items = [
            {
                "n_ref": doc["ref"],
                "categoria_item": item.get("categoria_item"),
                "total_sin_iva": float(item["total_sin_iva"]),
            }
            for doc in documentos
            for item in doc["items"]
            if doc.get("ref") and item.get("total_sin_iva") is not None
        ]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return (items,
            _mas_frecuente_por_prefijo(documentos, "tipo_proyecto"),
            _mas_frecuente_por_prefijo(documentos, "proyecto"))


def crear_filas_proyectos_nuevos(
    ws_proyectos, filas_validas: list[dict], nombres_nuevos: dict[str, str],
) -> list[dict]:
    """Escribe una fila nueva (solo TAG + Nombre, columnas 1 y 2) por cada
    (prefijo, nombre) de 'nombres_nuevos' -- quien llama ya filtró los
    prefijos que faltan en filas_validas. El resto de las columnas queda en
    blanco: las autocompletadas (Cliente, Categoría, fórmulas de costos
    reales) las llena el resto de ejecutar() al recibir la fila en su propio
    filas_validas; las manuales (% Avance, fechas, Monto de Venta, etc.) las
    llena el usuario a mano. Devuelve las filas creadas, mismo formato que
    leer_filas_proyectos, para que el llamador las sume a filas_validas."""
    siguiente_fila = max((f["fila"] for f in filas_validas), default=1) + 1
    nuevas = []
    for prefijo in sorted(nombres_nuevos):
        nombre = nombres_nuevos[prefijo]
        ws_proyectos.cell(row=siguiente_fila, column=1, value=prefijo)
        ws_proyectos.cell(row=siguiente_fila, column=2, value=nombre)
        nuevas.append({"fila": siguiente_fila, "tag": prefijo, "nombre": nombre})
        siguiente_fila += 1
    return nuevas


def asegurar_categoria_proyectos(
    ws_proyectos, filas_validas: list[dict], categoria_por_prefijo: dict[str, str],
    columna: int,
) -> list[str]:
    """Escribe la 'Categoría' de cada fila válida (columna indicada por
    'columna' -- quien llama la calcula desde HEADERS_PROYECTOS, nunca
    hardcodeada acá) desde categoria_por_prefijo -- valor plano, no fórmula
    (no hay agregación posible, es un lookup 1 a 1). Si un proyecto no tiene
    ningún documento en Centro de Costos todavía, limpia la celda y avisa."""
    avisos = []
    for fila_info in filas_validas:
        prefijo = fila_info["tag"]
        categoria = categoria_por_prefijo.get(prefijo)
        cell = ws_proyectos.cell(row=fila_info["fila"], column=columna)
        if categoria is None:
            # Mismo prefijo que usa asegurar_formulas_proyectos para el SUMIFS
            # de Materiales/Equipos/Otros Reales -- si nunca hay documentos con
            # este TAG (por ser un proyecto nuevo, O por un TAG mal escrito en
            # "Proyectos" que nunca calzara con ningun N° Ref real de Centro de
            # Costos), tanto la Categoría como los 3 costos reales quedan en
            # blanco/0 sin ningún error de Excel -- este aviso es la única
            # señal de que algo puede estar mal escrito, no solo "aún sin
            # facturas". Ver "Reglas de negocio" en SKILL.md.
            avisos.append(
                f"Proyecto '{fila_info['nombre']}' ({prefijo}) sin documentos en "
                f"Centro de Costos todavía -- Categoría queda vacía y los costos "
                f"reales (Materiales/Equipos/Otros) quedan en 0. Si el proyecto ya "
                f"tiene facturas registradas, revisa que '{prefijo}' sea el TAG "
                f"correcto (debe calzar exacto con el prefijo del N° Ref en Centro "
                f"de Costos, ej. 'UMAG')."
            )
            cell.value = None
            continue
        cell.value = categoria
    return avisos


def agrupar_por_proyecto_y_subcategoria(items_detalle: list[dict]) -> dict[tuple[str, str], float]:
    """Suma total_sin_iva agrupado por (prefijo de proyecto, categoria_item
    original -- sin colapsar a bucket todavía, eso lo hace la hoja 'Detalle
    Costos Reales' al escribir, para no perder la subcategoría real)."""
    agrupado: dict[tuple[str, str], float] = {}
    for item in items_detalle:
        prefijo = prefijo_de_n_ref(item["n_ref"])
        clave = (prefijo, item["categoria_item"])
        agrupado[clave] = agrupado.get(clave, 0.0) + item["total_sin_iva"]
    return agrupado


# ── LECTURA DE LA HOJA "PROYECTOS" ───────────────────────────────────────────

def leer_filas_proyectos(ws_proyectos) -> tuple[list[dict], list[str]]:
    """Recorre la hoja 'Proyectos' desde la fila 2. Filas sin TAG o sin
    Nombre se saltan con aviso. TAG duplicado: se queda con la primera
    fila, avisa de las siguientes."""
    filas_validas = []
    avisos = []
    tags_vistos = set()

    for fila_idx in range(2, ws_proyectos.max_row + 1):
        tag = ws_proyectos.cell(row=fila_idx, column=1).value
        nombre = ws_proyectos.cell(row=fila_idx, column=2).value

        if not tag or not nombre:
            if tag or nombre:
                avisos.append(f"Fila {fila_idx}: falta TAG o Nombre, se salta.")
            continue

        if tag in tags_vistos:
            avisos.append(f"Fila {fila_idx}: TAG '{tag}' duplicado, se usa la primera fila.")
            continue

        tags_vistos.add(tag)
        filas_validas.append({"fila": fila_idx, "tag": tag, "nombre": nombre})

    return filas_validas, avisos


# ── CARPETAS DE PROYECTO ─────────────────────────────────────────────────────

def normalizar_nombre_proyecto_carpeta(nombre_carpeta: str) -> str:
    """Espejo de normalizar_nombre_proyecto() en auditor_centro_costos.py
    (Centro de Costos) -- se duplica en vez de importar porque cada modulo
    corre en su propio proceso (ver CLAUDE.md raiz). Debe cambiar en ambos
    lugares a la vez si cambia la regla."""
    nombre = re.sub(r"^\d+[.\-_]\s*", "", nombre_carpeta).strip()
    nombre = re.sub(r"^(\S.*\S|\S)\s+(\d+)$", r"\1\2", nombre)
    return nombre or nombre_carpeta


def carpeta_proyecto_existe(nombre_proyecto: str, raiz_facturas: Path) -> bool:
    """True si raiz_facturas ya tiene una carpeta para nombre_proyecto -- con
    ese nombre exacto o con codigo (ej. '261. FACH 1' para 'FACH1'), para no
    tratar como faltante un proyecto que ya tiene documentos registrados bajo
    su nombre de carpeta fisico original."""
    if (raiz_facturas / nombre_proyecto).exists():
        return True
    if raiz_facturas.exists():
        for existente in raiz_facturas.iterdir():
            if existente.is_dir() and normalizar_nombre_proyecto_carpeta(existente.name) == nombre_proyecto:
                return True
    return False


def asegurar_carpeta_proyecto(nombre_proyecto: str, raiz_facturas: Path) -> bool:
    """Crea raiz_facturas/<nombre_proyecto>/ si no existe (ver
    carpeta_proyecto_existe). Devuelve True si la creó, False si ya existía.
    raiz_facturas debe ser la fuente REAL que lee Centro de Costos hoy (Sitio
    de comunicación - Centro de Costos 1/Facturas y Boletas/), nunca la
    carpeta legado."""
    if carpeta_proyecto_existe(nombre_proyecto, raiz_facturas):
        return False
    (raiz_facturas / nombre_proyecto).mkdir(parents=True, exist_ok=True)
    return True


def asegurar_carpetas_proyectos(filas_validas: list[dict], raiz_facturas: Path) -> list[str]:
    """Aplica asegurar_carpeta_proyecto a cada fila válida. Devuelve los
    nombres de las carpetas que se crearon (para el informe de consola)."""
    creadas = []
    for fila_info in filas_validas:
        if asegurar_carpeta_proyecto(fila_info["nombre"], raiz_facturas):
            creadas.append(fila_info["nombre"])
    return creadas


# ── BACKUP ────────────────────────────────────────────────────────────────

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre",
    12: "Diciembre",
}


def hacer_backup(ruta_excel: Path, raiz_respaldos: Path) -> Path | None:
    """Copia ruta_excel a raiz_respaldos/<Mes Año>/Análisis de Proyectos -
    backup <fecha> <hora>.xlsx antes de escribir -- mismo patrón que
    Centro de Costos. Devuelve None si ruta_excel todavía no existe (nada
    que respaldar)."""
    if not ruta_excel.exists():
        return None
    ahora = datetime.now()
    carpeta_mes = raiz_respaldos / f"{MESES_ES[ahora.month]} {ahora.year}"
    carpeta_mes.mkdir(parents=True, exist_ok=True)
    marca_tiempo = ahora.strftime("%Y-%m-%d %H%M%S")
    destino = carpeta_mes / f"Análisis de Proyectos - backup {marca_tiempo}.xlsx"
    shutil.copy2(ruta_excel, destino)
    return destino


# ── HOJA "DETALLE COSTOS REALES" (100% regenerada cada corrida) ─────────────

def regenerar_hoja_detalle_costos_reales(wb, agrupado: dict[tuple[str, str], float]) -> list[str]:
    """Borra todas las filas de datos (fila 2 en adelante) y las reescribe
    completas desde 'agrupado' -- mismo patrón que las hojas de proyecto de
    Centro de Costos: se recalcula entera, nunca se acumula a mano. Devuelve
    avisos de subcategorías sin mapeo explícito (caen en 'Otros').

    Columna E ("% del Total Real del proyecto", agregada 2026-07-28) = Total
    sin IVA de la fila / suma de TODAS las filas de ese mismo proyecto EN
    ESTA MISMA HOJA (no el Total Real de 'Proyectos', que además incluye
    Mano de Obra Real manual -- esa categoría no tiene detalle por
    subcategoría acá). Se calcula en Python, como el resto de esta hoja
    (nunca fórmula), para que sume ~100% de forma verificable sin depender
    de que Excel recalcule."""
    ws = wb[HOJA_DETALLE_COSTOS_REALES]
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)

    total_por_proyecto: dict[str, float] = {}
    for (tag, _), total in agrupado.items():
        total_por_proyecto[tag] = total_por_proyecto.get(tag, 0.0) + total

    avisos = []
    fila = 2
    for (tag, subcategoria), total in sorted(agrupado.items()):
        bucket, es_explicito = mapear_categoria_a_bucket(subcategoria)
        if not es_explicito:
            avisos.append(
                f"Categoría '{subcategoria}' (proyecto {tag}) sin mapeo explícito, va a 'Otros'."
            )
        total_proyecto = total_por_proyecto[tag]
        porcentaje = (total / total_proyecto) if total_proyecto else None
        ws.cell(row=fila, column=1, value=tag)
        ws.cell(row=fila, column=2, value=subcategoria)
        ws.cell(row=fila, column=3, value=bucket)
        ws.cell(row=fila, column=4, value=total)
        ws.cell(row=fila, column=5, value=porcentaje)
        fila += 1

    return avisos


# ── FÓRMULAS DE LA HOJA "PROYECTOS" ──────────────────────────────────────────

def asegurar_formulas_proyectos(ws_proyectos, filas_validas: list[dict]) -> None:
    """Escribe las columnas derivadas (Materiales/Equipos/Otros Reales =
    SUMIFS hacia 'Detalle Costos Reales'; Total Proyectado/Real, Margen
    Proyectado/Real, Desviación % = fórmulas sobre 'Proyectos') para cada
    fila válida -- todas resueltas por nombre vía LETRA_COL_PROYECTOS, nunca
    por letra fija, para no romperse si HEADERS_PROYECTOS cambia de orden.
    Nunca toca las columnas de ingreso manual (ver
    NOMBRES_COLUMNAS_MANUALES_PROYECTOS) ni Cliente/Categoría
    (autocompletadas)."""
    col = {nombre: HEADERS_PROYECTOS.index(nombre) + 1 for nombre in HEADERS_PROYECTOS}
    letra = LETRA_COL_PROYECTOS

    for fila_info in filas_validas:
        r = fila_info["fila"]
        tag_ref = f"$A{r}"

        for nombre, bucket in (
            ("Costos Materiales Reales", "Materiales"),
            ("Costos Equipos Reales", "Equipos"),
            ("Otros Costos Reales", "Otros"),
        ):
            ws_proyectos.cell(row=r, column=col[nombre], value=(
                f"=SUMIFS('{HOJA_DETALLE_COSTOS_REALES}'!$D:$D,"
                f"'{HOJA_DETALLE_COSTOS_REALES}'!$A:$A,{tag_ref},"
                f"'{HOJA_DETALLE_COSTOS_REALES}'!$C:$C,\"{bucket}\")"
            ))

        g, h, i, j = (letra[n] for n in (
            "Costos Materiales Proyectados", "Costos Equipos Proyectados",
            "Mano de Obra Proyectada", "Otros Costos Proyectados",
        ))
        l, m, n, o = (letra[n] for n in (
            "Costos Materiales Reales", "Costos Equipos Reales",
            "Otros Costos Reales", "Mano de Obra Real",
        ))
        venta = letra["Monto de Venta (sin IVA)"]
        total_proy = letra["Total Proyectado"]
        total_real = letra["Total Real"]

        ws_proyectos.cell(row=r, column=col["Total Proyectado"], value=f"={g}{r}+{h}{r}+{i}{r}+{j}{r}")
        ws_proyectos.cell(row=r, column=col["Total Real"], value=f"={l}{r}+{m}{r}+{n}{r}+{o}{r}")
        ws_proyectos.cell(row=r, column=col["Margen Proyectado"], value=f"={venta}{r}-{total_proy}{r}")
        ws_proyectos.cell(row=r, column=col["Margen Real"], value=f"={venta}{r}-{total_real}{r}")
        # Presupuesto total en 0 (o vacío) -> celda vacía, no #DIV/0!: mismo
        # significado que el None de calcular_kpis_proyecto (2026-09-21).
        ws_proyectos.cell(
            row=r, column=col["Desviación % (Real vs Proyectado)"],
            value=f'=IF({total_proy}{r}=0,"",{total_real}{r}/{total_proy}{r}-1)',
        )


# ── NOTA DEL PROYECTO (hoja "Indicadores") ──────────────────────────────────
# 0-100, aprobatorio >=55. Rentabilidad domina el peso (70/30) -- decision
# del usuario en brainstorming, spec 2026-07-21 seccion 1. Constantes
# separadas de la formula para que recalibrar el benchmark no implique
# reescribir la logica, solo estos valores.
MARGEN_OBJETIVO_NOTA = 0.25
# Curva del componente de margen corregida 2026-08-20: antes el score topaba
# en 100 apenas margen_neto cruzaba MARGEN_OBJETIVO_NOTA (MIN(100,...)) --
# contra la cartera real de QUEMPIN (15 proyectos, margenes reales de
# 22%-99.8%) eso dejaba 6 de 7 proyectos completos empatados en Nota=100, sin
# ninguna capacidad de distinguir un proyecto al 40% de margen de uno al 99%.
# Ahora es una curva de dos tramos (ver _score_margen_nota): lineal
# 0->SCORE_MARGEN_EN_OBJETIVO hasta el objetivo, y una asintota que sigue
# subiendo (cada vez mas despacio, sin tocar 100 nunca) por sobre el
# objetivo. K_MARGEN_NOTA_SOBRE_OBJETIVO esta calibrada para que un margen de
# 60% (cerca de la mediana real observada) puntue ~90.
SCORE_MARGEN_EN_OBJETIVO = 70
K_MARGEN_NOTA_SOBRE_OBJETIVO = 0.3186
PESO_RENTABILIDAD_NOTA = 0.7
PESO_DESVIACION_NOTA = 0.3
# Sobrecosto con el que el componente de control (30%) llega a 0 puntos.
# Hasta 2026-09-21 era implícitamente +100% (100 - desviacion*100): un
# proyecto real con casi +28% de sobrecosto perdía solo 8 puntos y seguía
# "Bueno". Decisión del usuario en la fase 1 de la auditoría:
# +30% ya es un descontrol total del presupuesto.
SOBRECOSTO_NOTA_CERO = 0.30

UMBRAL_EXCELENTE, UMBRAL_BUENO, UMBRAL_APROBADO = 85, 70, 55


# ── COMPLETITUD DE UN PROYECTO: UNA SOLA DEFINICION ─────────────────────────
# Un proyecto sin estos campos cargados a mano no recibe KPIs: ni reporte PDF
# ni fila en el dashboard (aparece como "pendiente de completar"). "Fecha de
# cierre" queda deliberadamente FUERA -- su ausencia marca al proyecto como
# "en desarrollo", no como incompleto. "Cliente"/"Categoría" tampoco cuentan:
# se autocompletan, no son carga del usuario.
#
# Hasta el 2026-07-28 esta regla estaba duplicada y los dos consumidores no
# coincidian: los reportes exigian estos 8 campos, el visualizador solo 6
# (sin "% Avance" -- entonces llamada "Estado" -- ni "Fecha de inicio") y ademas
# aceptaba la cadena vacia como valor cargado. Resultado: un proyecto podia
# salir con KPIs completos en el dashboard y a la vez ser rechazado con
# DatosIncompletosError al pedir su PDF.
#
# "Fecha de inicio" salió de la lista el 2026-09-21 (auditoría, fase 1): solo
# la usa "Margen por día de ejecución", que ya queda vacío si falta. Exigirla
# dejaba proyectos enteros sin ningún KPI -- con venta, presupuesto y costos
# cargados -- por un dato que no entra en su margen ni en su Nota.
# Cada campo que queda acá sí entra en la Nota: venta y costos en el margen,
# presupuesto en la desviación, % Avance en la estimación al cierre.
CAMPOS_MANUALES_REQUERIDOS = [
    "% Avance", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados", "Mano de Obra Real",
]


def campos_faltantes(valor_de_campo) -> list[str]:
    """Los campos de CAMPOS_MANUALES_REQUERIDOS que el proyecto no tiene
    cargados, en ese mismo orden. `valor_de_campo` es un callable que recibe
    el nombre de encabezado de "Proyectos" y devuelve su valor -- asi sirve
    igual para un dict keyed por encabezado (reportes) que para uno de claves
    cortas (visualizador), sin que ninguno de los dos reimplemente la regla.

    0 SI cuenta como cargado (un costo real en cero es un dato, no un vacio);
    None y la cadena vacia no."""
    return [campo for campo in CAMPOS_MANUALES_REQUERIDOS if valor_de_campo(campo) in (None, "")]


def tiene_datos_completos(valor_de_campo) -> bool:
    """True si el proyecto tiene los campos manuales requeridos cargados -- definido
    sobre campos_faltantes para que el dashboard, al decir QUE falta, nunca
    discrepe de la regla que decide si falta algo."""
    return not campos_faltantes(valor_de_campo)


# ── NOTA / EVALUACION: UNA SOLA DEFINICION, DOS RENDERIZADOS ────────────────
# La misma regla de negocio se expresa de dos formas: como formula de Excel
# (_formula_nota, para que el libro recalcule solo) y como calculo en Python
# (calcular_nota, para los consumidores que no pueden leer el resultado de una
# formula -- openpyxl nunca la evalua). Las dos viven pegadas A PROPOSITO:
# hasta el 2026-07-28 el calculo Python estaba duplicado en dos archivos
# distintos (Reportes/kpis_recalculados.py y Visualizador Web/
# build_visualizador.py) y se desincronizaron -- el visualizador siguio usando
# ABS() despues de que la regla cambio, y el MISMO proyecto mostraba nota 94 en
# el dashboard y 100 en el Excel/PDF. Si cambias una de las dos funciones de
# abajo, cambia la otra en el mismo commit; test_contrato_kpis.py falla si no.


def _redondear_excel(x: float) -> int:
    """ROUND() de Excel: 'half away from zero'. El round() nativo de Python
    usa banker's rounding (round(96.5) == 96), lo que puede dejar la Nota en
    el bucket de Evaluacion equivocado justo en un empate exacto en .5."""
    return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)


def _score_margen_nota(margen_neto: float) -> float:
    """Curva del componente de margen de la Nota del Proyecto (corregida
    2026-08-20). Lineal 0->SCORE_MARGEN_EN_OBJETIVO hasta MARGEN_OBJETIVO_NOTA
    (llegar justo al objetivo vale SCORE_MARGEN_EN_OBJETIVO/100, no el tope);
    por sobre el objetivo sigue subiendo -- cada vez mas despacio, asintota
    hacia 100 sin tocarlo nunca -- en vez de aplanarse de golpe en el tope
    (MIN(100,...) de antes). Ver comentario junto a las constantes para el
    porque: con margenes reales de 22%-99.8%, un tope en el objetivo de 25%
    dejaba casi toda la cartera empatada en el maximo."""
    if margen_neto <= 0:
        return 0.0
    if margen_neto <= MARGEN_OBJETIVO_NOTA:
        return (margen_neto / MARGEN_OBJETIVO_NOTA) * SCORE_MARGEN_EN_OBJETIVO
    extra = 100 - SCORE_MARGEN_EN_OBJETIVO
    return SCORE_MARGEN_EN_OBJETIVO + extra * (
        1 - math.exp(-(margen_neto - MARGEN_OBJETIVO_NOTA) / K_MARGEN_NOTA_SOBRE_OBJETIVO)
    )


def _score_desviacion_nota(desviacion_total: float) -> float:
    """Componente de control del presupuesto (30%) de la Nota: 100 en o bajo
    presupuesto, 0 con SOBRECOSTO_NOTA_CERO o más de sobrecosto, lineal entre
    medio. Equivalente Excel en _formula_nota()."""
    return min(100, max(0, 100 - max(0, desviacion_total) / SOBRECOSTO_NOTA_CERO * 100))


def calcular_nota(margen_neto: float | None, desviacion_total: float | None) -> int | None:
    """Equivalente Python exacto de _formula_nota(). None si falta cualquiera
    de los dos insumos (mismo significado que una celda vacia en Excel).

    Desde 2026-09-21 los dos insumos son los ESTIMADOS AL CIERRE (ver
    calcular_kpis_proyecto): en un proyecto terminado coinciden con los
    reales; en uno en curso ya no se evalúa el costo gastado a la fecha
    contra la venta completa, que inflaba el margen.

    El componente de desviacion (30%) usa MAX(0, desviacion), NO ABS():
    penaliza solo el sobrecosto real (Real > Proyectado). Un proyecto en o
    bajo presupuesto obtiene el puntaje maximo de ese componente -- el
    beneficio de haber ahorrado ya esta capturado en el 70% de rentabilidad,
    asi que castigarlo aca ademas seria doble penalizacion (decision del
    usuario, 2026-07-28)."""
    if margen_neto is None or desviacion_total is None:
        return None
    score_margen = _score_margen_nota(margen_neto)
    score_desviacion = _score_desviacion_nota(desviacion_total)
    return _redondear_excel(
        PESO_RENTABILIDAD_NOTA * score_margen + PESO_DESVIACION_NOTA * score_desviacion
    )


def clasificar_evaluacion(nota: int | None) -> str | None:
    """Equivalente Python exacto de _formula_evaluacion()."""
    if nota is None:
        return None
    if nota >= UMBRAL_EXCELENTE:
        return "Excelente"
    if nota >= UMBRAL_BUENO:
        return "Bueno"
    if nota >= UMBRAL_APROBADO:
        return "Aprobado"
    return "Requiere atención"


def _formula_nota(fila_indicadores: int) -> str:
    """Equivalente Excel exacto de calcular_nota(), sobre las columnas de
    estimación al cierre de esta misma hoja ('Indicadores').

    Corregido 2026-07-28 (aprobado por el usuario): el componente de
    control de desviación (30%) ya NO usa ABS() -- antes penalizaba gastar
    de menos igual que gastar de más, pese a que ahorrar ya sube el margen
    (capturado en el 70% de rentabilidad). MAX(0, desviación) anula el
    término para cualquier proyecto en o bajo presupuesto.

    Componente de margen corregido 2026-08-20: equivalente Excel exacto de
    _score_margen_nota() -- ver esa función para el porqué. EXP() no
    necesita prefijo _xlfn. (función anterior a 2007).

    2026-09-21 (auditoría, fase 1): los insumos pasan a ser el margen y la
    desviación ESTIMADOS AL CIERRE, y el componente de control llega a 0 con
    SOBRECOSTO_NOTA_CERO de sobrecosto en vez de +100%. Queda vacía si falta
    cualquiera de los dos insumos, como el None de calcular_nota()."""
    li = LETRA_COL_INDICADORES
    margen = f"{li['Margen estimado al cierre %']}{fila_indicadores}"
    desviacion = f"{li['Desviación estimada al cierre %']}{fila_indicadores}"
    extra = 100 - SCORE_MARGEN_EN_OBJETIVO
    score_margen = (
        f"IF({margen}<=0,0,IF({margen}<={MARGEN_OBJETIVO_NOTA},"
        f"{margen}/{MARGEN_OBJETIVO_NOTA}*{SCORE_MARGEN_EN_OBJETIVO},"
        f"{SCORE_MARGEN_EN_OBJETIVO}+{extra}*(1-EXP(-({margen}-{MARGEN_OBJETIVO_NOTA})/{K_MARGEN_NOTA_SOBRE_OBJETIVO}))))"
    )
    score_desviacion = (
        f"MIN(100,MAX(0,100-MAX(0,{desviacion})/{SOBRECOSTO_NOTA_CERO}*100))"
    )
    return (
        f'=IF(OR({margen}="",{desviacion}=""),"",'
        f"ROUND({PESO_RENTABILIDAD_NOTA}*{score_margen}+{PESO_DESVIACION_NOTA}*{score_desviacion},0))"
    )


def _formula_evaluacion(fila_destino: int) -> str:
    # Referencia a la columna "Nota del Proyecto" de esta misma hoja
    # ("Indicadores"), calculada desde LETRA_COL_INDICADORES -- nunca
    # hardcodeada, para no romperse si el playbook de KPIs vuelve a cambiar
    # de orden/cantidad de columnas. Guarda contra Nota vacía: en Excel un
    # texto "" siempre es >= que un número, así que sin el guard una Nota
    # vacía salía "Excelente".
    col_nota = LETRA_COL_INDICADORES["Nota del Proyecto"]
    ref = f"{col_nota}{fila_destino}"
    return (
        f'=IF({ref}="","",IF({ref}>={UMBRAL_EXCELENTE},"Excelente",IF({ref}>={UMBRAL_BUENO},"Bueno",'
        f'IF({ref}>={UMBRAL_APROBADO},"Aprobado","Requiere atención"))))'
    )


# ── KPIS DE UN PROYECTO: UNA SOLA IMPLEMENTACIÓN PYTHON ─────────────────────
# Hasta 2026-09-21 los KPIs de un proyecto se recalculaban en Python en TRES
# lugares -- Reportes/kpis_recalculados.py (PDF), Visualizador Web/
# build_visualizador.py (dashboard Chile) y su copia peruana -- además de las
# fórmulas de Excel. Ya divergieron dos veces (la Nota el 2026-07-28, la copia
# peruana el 2026-08-31). Ahora los tres consumidores llaman a
# calcular_kpis_proyecto(), que devuelve cada KPI con el MISMO nombre que su
# columna en "Proyectos"/"Indicadores"; las fórmulas de asegurar_hoja_
# indicadores() son su espejo y test_contrato_kpis.py las compara.
#
# Convención de vacíos, igual en los dos lados: None en Python == celda vacía
# en Excel. Una división por cero (venta 0, presupuesto 0) da vacío, nunca 0:
# un 0 inventado se lee como "sin desviación", que no es lo mismo que "sin
# presupuesto contra qué medirla".

# (sufijo de la columna en "Indicadores", columna proyectada, columna real)
CATEGORIAS_KPI = (
    ("Materiales", "Costos Materiales Proyectados", "Costos Materiales Reales"),
    ("Equipos", "Costos Equipos Proyectados", "Costos Equipos Reales"),
    ("MO", "Mano de Obra Proyectada", "Mano de Obra Real"),
    ("Otros", "Otros Costos Proyectados", "Otros Costos Reales"),
)
NOMBRE_LEGIBLE_CATEGORIA = {
    "Materiales": "Materiales", "Equipos": "Equipos", "MO": "Mano de Obra", "Otros": "Otros",
}


def _vacio(valor) -> bool:
    return valor is None or valor == ""


def _num(valor):
    return None if _vacio(valor) else valor


def _dividir(a, b):
    """División de Excel con guard: denominador vacío o 0 -> None (celda
    vacía), nunca un 0 inventado."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def _sumar(*valores):
    if any(v is None for v in valores):
        return None
    return sum(valores)


def _restar(a, b):
    if a is None or b is None:
        return None
    return a - b


def _desviacion(real, proyectado):
    d = _dividir(real, proyectado)
    return None if d is None else d - 1


def _a_fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def avance_acotado(avance):
    """% Avance llevado a [0, 1] para estimar el cierre. Fuera de ese rango
    es un error de carga: se estima con el valor acotado (un avance de 120%
    no puede "des-gastar" presupuesto) y alertas_proyecto() lo avisa, para
    que el error se vea en vez de quedar escondido en un número raro."""
    if _vacio(avance):
        return None
    return min(1.0, max(0.0, avance))


def costo_estimado_al_cierre(total_real, total_proyectado, avance):
    """Costo al cierre = costo real a la fecha + lo que falta ejecutar a
    precio de presupuesto: Real + Proyectado x (1 - avance). Es la
    estimación elegida por el usuario (2026-09-21) para la Nota: no
    extrapola el sobrecosto pasado a lo que falta, así que no castiga a un
    proyecto que compró sus materiales al inicio. Al 100% de avance es
    exactamente el costo real."""
    a = avance_acotado(avance)
    if a is None or total_real is None or total_proyectado is None:
        return None
    return total_real + total_proyectado * (1 - a)


def costo_al_cierre_indice(total_real, avance):
    """Escenario pesimista, solo informativo (no entra en la Nota): el
    ritmo de gasto actual se mantiene hasta el final. Con índice de costo
    CPI = (Proyectado x avance) / Real, el costo al cierre Proyectado / CPI
    se simplifica a Real / avance. Sin avance (0%) no hay ritmo que
    extrapolar."""
    a = avance_acotado(avance)
    if not a or total_real is None:
        return None
    return total_real / a


def margen_por_dia(fecha_inicio, fecha_cierre, margen_real, hoy: date | None = None):
    """Margen Real / días de ejecución. Vacío si falta alguna fecha o si el
    proyecto sigue en desarrollo (fecha de cierre futura, misma regla que
    los reportes PDF): no se divide un margen parcial por una duración que
    todavía no terminó. MAX(1, días) evita dividir por 0."""
    inicio, cierre = _a_fecha(fecha_inicio), _a_fecha(fecha_cierre)
    if inicio is None or cierre is None or margen_real is None:
        return None
    if cierre > (hoy or date.today()):
        return None
    return margen_real / max(1, (cierre - inicio).days)


def calcular_kpis_proyecto(valores: dict, costos_reales: dict, hoy: date | None = None) -> dict:
    """Todos los KPIs de un proyecto, keyed por el nombre de su columna en
    'Proyectos' (derivadas) o 'Indicadores'.

    `valores`: columnas manuales/autocompletadas de 'Proyectos', keyed por
    encabezado (TAG, Cliente, Categoría, % Avance, fechas, venta, los 4
    proyectados y Mano de Obra Real). `costos_reales`: {'Materiales',
    'Equipos', 'Otros'} -> suma de 'Detalle Costos Reales' (un bucket
    ausente vale 0, igual que un SUMIFS sin coincidencias).

    No incluye 'Peso del proyecto en la cartera de ventas (%)': depende de
    toda la cartera, no del proyecto (ver calcular_peso_cartera)."""
    v = lambda campo: _num(valores.get(campo))  # noqa: E731
    venta = v("Monto de Venta (sin IVA)")
    reales = {
        "Costos Materiales Reales": costos_reales.get("Materiales", 0.0),
        "Costos Equipos Reales": costos_reales.get("Equipos", 0.0),
        "Otros Costos Reales": costos_reales.get("Otros", 0.0),
        "Mano de Obra Real": v("Mano de Obra Real"),
    }
    total_proyectado = _sumar(*(v(col_p) for _, col_p, _ in CATEGORIAS_KPI))
    total_real = _sumar(*(reales[col_r] for _, _, col_r in CATEGORIAS_KPI))
    margen_real = _restar(venta, total_real)
    desviacion_total = _desviacion(total_real, total_proyectado)

    avance = v("% Avance")
    costo_estimado = costo_estimado_al_cierre(total_real, total_proyectado, avance)
    margen_estimado = _restar(venta, costo_estimado)
    margen_estimado_pct = _dividir(margen_estimado, venta)
    desviacion_estimada = _desviacion(costo_estimado, total_proyectado)
    margen_indice_pct = _dividir(_restar(venta, costo_al_cierre_indice(total_real, avance)), venta)

    # "Gastos Generales" es un bucket de costos internos: nunca se evalúa por
    # rentabilidad (mismo guard que la fórmula de asegurar_hoja_indicadores).
    es_gastos_generales = valores.get("Categoría") == CATEGORIA_GASTOS_GENERALES
    nota = None if es_gastos_generales else calcular_nota(margen_estimado_pct, desviacion_estimada)

    kpis = {
        **reales,
        "Total Proyectado": total_proyectado,
        "Total Real": total_real,
        "Margen Proyectado": _restar(venta, total_proyectado),
        "Margen Real": margen_real,
        "Desviación % (Real vs Proyectado)": desviacion_total,
        "Margen neto %": _dividir(margen_real, venta),
    }
    proyectados = {col_p: v(col_p) for _, col_p, _ in CATEGORIAS_KPI}
    for sufijo, col_p, col_r in CATEGORIAS_KPI:
        real, proyectado = reales[col_r], proyectados[col_p]
        kpis[f"Costo {sufijo} % de venta"] = _dividir(real, venta)
        kpis[f"Estructura % {sufijo}"] = _dividir(real, total_real)
        kpis[f"Desviación % {sufijo}"] = _desviacion(real, proyectado)
        kpis[f"Ahorro/Sobrecosto {sufijo}"] = _restar(proyectado, real)
    kpis.update({
        "Desviación % Total": desviacion_total,
        "Ahorro/Sobrecosto Total": _restar(total_proyectado, total_real),
        "Nota del Proyecto": nota,
        "Evaluación": clasificar_evaluacion(nota),
        "Margen por día de ejecución": margen_por_dia(
            valores.get("Fecha de inicio"), valores.get("Fecha de cierre"), margen_real, hoy,
        ),
        "Costo estimado al cierre": costo_estimado,
        "Margen estimado al cierre": margen_estimado,
        "Margen estimado al cierre %": margen_estimado_pct,
        "Desviación estimada al cierre %": desviacion_estimada,
        "Margen al cierre % (escenario índice de costo)": margen_indice_pct,
        "Error del presupuesto %": error_presupuesto(
            {col_r: reales[col_r] for _, _, col_r in CATEGORIAS_KPI},
            {col_r: proyectados[col_p] for _, col_p, col_r in CATEGORIAS_KPI},
            total_proyectado,
        ),
        "Cliente": valores.get("Cliente"),
        "Categoría": valores.get("Categoría"),
        # Pasan de largo (no son KPIs): los necesitan sesgo_por_categoria y
        # las alertas -- el avance para distinguir un proyecto terminado de uno
        # en curso, y los costos proyectados para comparar contra los reales.
        "% Avance": avance,
        **proyectados,
        "Monto de Venta (sin IVA)": venta,
        "Datos completos": "Sí" if tiene_datos_completos(valores.get) else "No",
    })
    return kpis


def error_presupuesto(reales: dict, proyectados: dict, total_proyectado) -> float | None:
    """Cuánto se equivocó el presupuesto, sin que los errores de una
    categoría tapen los de otra: suma de |real - proyectado| de las 4
    categorías, sobre el presupuesto total.

    La "Desviación % Total" puede dar casi 0 con un presupuesto muy mal
    repartido -- pasó en un proyecto real: total -1,1% con materiales en
    +307% compensados por equipos en -90%. Este número lo muestra: 0% =
    presupuesto clavado categoría por categoría; 65% = dos tercios del
    presupuesto quedaron en la categoría equivocada. Es el insumo para
    cotizar mejor, no un juicio sobre el resultado del proyecto (ese es el
    margen)."""
    if not total_proyectado:
        return None
    suma = 0.0
    for clave in reales:
        real, proyectado = reales[clave], proyectados[clave]
        if real is None or proyectado is None:
            return None
        suma += abs(real - proyectado)
    return suma / total_proyectado


def calcular_peso_cartera(ventas_por_tag: dict) -> dict:
    """Peso del proyecto en la cartera de ventas (%): venta del proyecto
    sobre la suma de TODAS las ventas cargadas (completas o no), igual que
    la fórmula de Excel, que suma la columna entera de 'Proyectos'. Sin
    venta cargada -> None."""
    total = sum(v for v in ventas_por_tag.values() if not _vacio(v))
    return {
        tag: (_dividir(venta, total) if not _vacio(venta) else None)
        for tag, venta in ventas_por_tag.items()
    }


# ── ANÁLISIS DE CARTERA (Fase 2: solo Python, alimenta el tablero) ──────────
# Números que no son de un proyecto sino del conjunto, y que por eso no
# tienen columna en el Excel: en qué se equivoca sistemáticamente el
# presupuesto, y de cuántos clientes depende el ingreso.


def sesgo_por_categoria(kpis_proyectos: list[dict]) -> list[dict]:
    """Por categoría, cuánto se desvió el gasto real del presupuesto en TODA
    la cartera (Σ real / Σ proyectado - 1), contando solo proyectos
    terminados y completos: un proyecto a medio ejecutar todavía va a gastar
    más y ensuciaría el sesgo.

    Sirve para cotizar: un sesgo estable de +16% en Materiales dice que el
    presupuesto de materiales se queda corto siempre, no que un proyecto
    salió mal."""
    terminados = [
        k for k in kpis_proyectos
        if k.get("Datos completos") == "Sí" and avance_acotado(k.get("% Avance")) == 1.0
    ]
    filas = []
    for sufijo, col_p, col_r in CATEGORIAS_KPI:
        real = sum(k[col_r] for k in terminados if k[col_r] is not None)
        proyectado = sum(k[col_p] for k in terminados if k[col_p] is not None)
        filas.append({
            "categoria": NOMBRE_LEGIBLE_CATEGORIA[sufijo],
            "real": real,
            "proyectado": proyectado,
            "sesgo": _desviacion(real, proyectado),
            "n_proyectos": len(terminados),
        })
    return filas


def concentracion_cartera(ventas_por_cliente: dict) -> dict:
    """De cuántos clientes depende el ingreso. Sobre TODA la venta cargada
    (también la de proyectos que aún no entran al análisis): la dependencia
    existe aunque falte completar la planilla.

    'hhi' es el índice de Herfindahl (suma de los cuadrados de las
    participaciones) y 'clientes_equivalentes' su inverso: 1 = todo el
    ingreso en un cliente; 5 = como si el ingreso estuviera repartido en 5
    clientes iguales."""
    ventas = {c: v for c, v in ventas_por_cliente.items() if v}
    total = sum(ventas.values())
    if not total:
        return {"total": 0, "n_clientes": 0, "top_1": None, "top_3": None,
                "hhi": None, "clientes_equivalentes": None, "ranking": []}
    ranking = sorted(ventas.items(), key=lambda par: -par[1])
    partes = [venta / total for _, venta in ranking]
    hhi = sum(parte ** 2 for parte in partes)
    acumulado, ranking_pct = 0.0, []
    for (cliente, venta), parte in zip(ranking, partes):
        acumulado += parte
        ranking_pct.append({"cliente": cliente, "venta": venta, "parte": parte, "acumulado": acumulado})
    return {
        "total": total,
        "n_clientes": len(ranking),
        "top_1": partes[0],
        "top_3": sum(partes[:3]),
        "hhi": hhi,
        "clientes_equivalentes": 1 / hhi,
        "ranking": ranking_pct,
    }


# ── ALERTAS DE UN PROYECTO (solo Python: consola del run + dashboard) ────────
# Señales de que un dato manual está desactualizado o un proyecto se está
# saliendo de presupuesto -- no cambian ningún KPI, solo lo avisan.
UMBRAL_ALERTA_COSTO_INCOMPLETO = 0.80  # terminado con real < 80% del presupuesto
UMBRAL_ALERTA_SOBRECOSTO = 0.10        # sobrecosto (estimado) al cierre > +10%


def _pct_legible(x: float, signo: bool = False) -> str:
    texto = f"{x * 100:+.1f}" if signo else f"{x * 100:.1f}"
    return texto.replace(".", ",") + " %"


def alertas_proyecto(valores: dict, kpis: dict | None = None, hoy: date | None = None) -> list[str]:
    """Lista de alertas legibles de un proyecto. Las de fechas/avance se
    evalúan siempre; las de costos, solo si el proyecto tiene los datos
    completos (sin presupuesto o sin venta no hay contra qué comparar)."""
    hoy = hoy or date.today()
    alertas = []
    avance = _num(valores.get("% Avance"))
    cierre = _a_fecha(valores.get("Fecha de cierre"))

    if avance is not None and not 0 <= avance <= 1:
        alertas.append(
            f"% Avance fuera de rango ({_pct_legible(avance)}): la estimación al cierre "
            f"usa {_pct_legible(avance_acotado(avance))}."
        )
    if avance is not None and avance >= 1 and cierre and cierre > hoy:
        alertas.append(
            f"Avance 100 % pero con fecha de cierre futura ({cierre:%d-%m-%Y}): "
            f"revisar cuál de los dos está desactualizado."
        )
    if avance is not None and avance < 1 and cierre and cierre < hoy:
        alertas.append(
            f"La fecha de cierre ({cierre:%d-%m-%Y}) ya pasó y el avance va en "
            f"{_pct_legible(avance)}: actualizar el avance o la fecha."
        )

    if not kpis or kpis.get("Datos completos") != "Sí":
        return alertas

    total_real, total_proyectado = kpis["Total Real"], kpis["Total Proyectado"]
    cobertura = _dividir(total_real, total_proyectado)
    if avance >= 1 and cobertura is not None and cobertura < UMBRAL_ALERTA_COSTO_INCOMPLETO:
        alertas.append(
            f"Terminado con un costo real de solo {_pct_legible(cobertura)} del presupuesto: "
            f"revisar si faltan facturas o Mano de Obra por registrar antes de leer su margen."
        )
    desviacion_estimada = kpis["Desviación estimada al cierre %"]
    if desviacion_estimada is not None and desviacion_estimada > UMBRAL_ALERTA_SOBRECOSTO:
        if avance < 1:
            alertas.append(
                f"Sobrecosto estimado al cierre de {_pct_legible(desviacion_estimada, signo=True)}: "
                f"con {_pct_legible(avance)} de avance ya se gastó el "
                f"{_pct_legible(cobertura)} del presupuesto."
            )
        else:
            alertas.append(
                f"Terminado con sobrecosto de {_pct_legible(desviacion_estimada, signo=True)} "
                f"sobre el presupuesto."
            )
    for sufijo, col_p, col_r in CATEGORIAS_KPI:
        real = kpis[col_r]
        if _num(valores.get(col_p)) == 0 and real:
            alertas.append(
                f"{NOMBRE_LEGIBLE_CATEGORIA[sufijo]} tiene gasto real pero presupuesto 0: "
                f"su desviación no se puede medir."
            )
    return alertas


# ── CLIENTES: UNA SOLA IMPLEMENTACIÓN PYTHON ────────────────────────────────
# Reemplaza al CLTV (2026-09-21, auditoría fase 1 -- decisión del usuario).
# La fórmula anterior, AOV x Frecuencia x Vida x Margen %, contaba dos veces
# la cantidad de compras (AOV x Vida ya es la venta total, y Frecuencia
# vuelve a multiplicar por proyectos/año); con todos los clientes en 1
# proyecto no se notaba, pero el primer cliente recurrente iba a aparecer con
# un valor inflado. Con la cartera actual, lo que sí se puede afirmar es el
# margen que cada cliente ya dejó y si volvió a comprar.

CLASIFICACION_SIN_PROYECTOS = "Sin proyectos completos"


def percentil_inclusivo(valores: list[float], p: float) -> float:
    """PERCENTILE.INC de Excel (el que calcula AGGREGATE(16,...)):
    interpolación lineal sobre la lista ordenada, rango 0-indexado =
    p*(n-1). Con un solo valor devuelve ese valor."""
    ordenados = sorted(valores)
    n = len(ordenados)
    if n == 1:
        return ordenados[0]
    rango = p * (n - 1)
    inferior = int(rango)
    superior = min(inferior + 1, n - 1)
    return ordenados[inferior] + (ordenados[superior] - ordenados[inferior]) * (rango - inferior)


def clasificar_cliente(margen_acumulado: float, margenes_de_la_cartera: list[float]) -> str:
    """Tier relativo a la cartera actual (percentiles 67/33 del margen
    acumulado), no un corte fijo en pesos que quede obsoleto al crecer."""
    if margen_acumulado >= percentil_inclusivo(margenes_de_la_cartera, 0.67):
        return "Clientes estratégicos"
    if margen_acumulado >= percentil_inclusivo(margenes_de_la_cartera, 0.33):
        return "Clientes potenciales"
    return "Clientes de oportunidad"


def calcular_clientes(kpis_proyectos: list[dict]) -> list[dict]:
    """Espejo Python de la hoja 'Clientes' (asegurar_hoja_clientes). Recibe
    salidas de calcular_kpis_proyecto -- de cualquier conjunto de
    proyectos: solo cuentan los que tienen 'Datos completos' == 'Sí', igual
    que el COUNTIFS/SUMIFS de la hoja. Devuelve una fila por cliente con al
    menos un proyecto completo, keyed por las columnas de la hoja, ordenada
    por nombre."""
    por_cliente: dict[str, list[dict]] = {}
    for k in kpis_proyectos:
        if k.get("Datos completos") != "Sí" or not k.get("Cliente"):
            continue
        if k.get("Categoría") == CATEGORIA_GASTOS_GENERALES:
            continue
        por_cliente.setdefault(k["Cliente"], []).append(k)

    filas = []
    for cliente in sorted(por_cliente):
        proyectos = por_cliente[cliente]
        venta = sum(p["Monto de Venta (sin IVA)"] for p in proyectos)
        margen = sum(p["Margen estimado al cierre"] for p in proyectos)
        filas.append({
            "Cliente": cliente,
            "N° de proyectos": len(proyectos),
            "Venta acumulada (sin IVA)": venta,
            "Margen acumulado": margen,
            "Margen %": _dividir(margen, venta),
            "Cliente recurrente": "Sí" if len(proyectos) >= 2 else "No",
        })

    margenes = [f["Margen acumulado"] for f in filas]
    for f in filas:
        f["Clasificación"] = clasificar_cliente(f["Margen acumulado"], margenes)
    return filas


def tasa_recompra(clientes: list[dict]) -> float | None:
    """Clientes que ya compraron 2 o más proyectos / clientes con al menos
    un proyecto completo. None sin clientes."""
    if not clientes:
        return None
    return sum(1 for c in clientes if c["Cliente recurrente"] == "Sí") / len(clientes)


# ── FÓRMULAS DE LA HOJA "INDICADORES" (100% regenerada cada corrida) ────────

def formulas_indicadores(r: int, f: int) -> dict[str, str]:
    """Las fórmulas de una fila de 'Indicadores', keyed por encabezado: `r`
    es la fila del proyecto en 'Proyectos' (puede tener huecos) y `f` su
    fila compacta en 'Indicadores'. Espejo de calcular_kpis_proyecto(),
    incluida la convención de vacíos: toda división guarda contra
    denominador 0 o vacío y devuelve "" (== None en Python), nunca #DIV/0!.

    Keyed por nombre (2026-09-21) en vez de escribir por número de columna:
    así el orden de HEADERS_INDICADORES puede cambiar sin que una fórmula
    quede bajo el encabezado equivocado (el incidente real del 2026-07-28)."""
    lp, li = LETRA_COL_PROYECTOS, LETRA_COL_INDICADORES

    def p(nombre):
        return f"Proyectos!{lp[nombre]}{r}"

    def i(nombre):
        return f"{li[nombre]}{f}"

    def dividir(a, b):
        return f'IF({b}=0,"",{a}/{b})'

    venta, total_real, total_proy = p("Monto de Venta (sin IVA)"), p("Total Real"), p("Total Proyectado")
    avance = p("% Avance")
    avance_acotado_xl = f"MIN(1,MAX(0,{avance}))"
    es_gastos_generales = f'{p("Categoría")}="{CATEGORIA_GASTOS_GENERALES}"'
    cargados = ",".join(f'{p(campo)}<>""' for campo in CAMPOS_MANUALES_REQUERIDOS)

    formulas = {
        "TAG proyecto": f"={p('TAG proyecto')}",
        "Nombre del proyecto": f"={p('Nombre del proyecto')}",
        "Margen neto %": f"={dividir(p('Margen Real'), venta)}",
    }
    for sufijo, col_p, col_r in CATEGORIAS_KPI:
        real, proyectado = p(col_r), p(col_p)
        formulas[f"Costo {sufijo} % de venta"] = f"={dividir(real, venta)}"
        formulas[f"Estructura % {sufijo}"] = f"={dividir(real, total_real)}"
        formulas[f"Desviación % {sufijo}"] = f'=IF({proyectado}=0,"",{real}/{proyectado}-1)'
        formulas[f"Ahorro/Sobrecosto {sufijo}"] = f"={proyectado}-{real}"
    formulas.update({
        "Desviación % Total": f"={p('Desviación % (Real vs Proyectado)')}",
        "Ahorro/Sobrecosto Total": f"={total_proy}-{total_real}",
        # Nota/Evaluación vacías para "Gastos Generales" (bucket de costos
        # internos, nunca tiene venta): evaluar su "rentabilidad" no tiene
        # sentido. Mismo guard que calcular_kpis_proyecto().
        "Nota del Proyecto": f'=IF({es_gastos_generales},"",{_formula_nota(f)[1:]})',
        "Evaluación": f'=IF({es_gastos_generales},"",{_formula_evaluacion(f)[1:]})',
        # Venta del proyecto sobre la suma de TODA la columna de venta de
        # "Proyectos" -- SUM ignora celdas vacías, así que un proyecto sin
        # venta cargada no distorsiona el denominador.
        "Peso del proyecto en la cartera de ventas (%)": (
            f'=IF({venta}="","",{venta}/SUM(Proyectos!${lp["Monto de Venta (sin IVA)"]}:'
            f'${lp["Monto de Venta (sin IVA)"]}))'
        ),
        # Vacío si falta una fecha o si el proyecto sigue en desarrollo
        # (cierre futuro). El guard vive en la fórmula: se recalcula solo
        # cuando llega la fecha, sin correr el script. MAX(1, días) evita
        # #DIV/0! si inicio == cierre.
        "Margen por día de ejecución": (
            f'=IF(OR({p("Fecha de cierre")}="",{p("Fecha de inicio")}="",{p("Fecha de cierre")}>TODAY()),"",'
            f"{p('Margen Real')}/MAX(1,{p('Fecha de cierre')}-{p('Fecha de inicio')}))"
        ),
        # Estimación al cierre = real a la fecha + lo que falta a precio de
        # presupuesto (ver costo_estimado_al_cierre).
        "Costo estimado al cierre": (
            f'=IF({avance}="","",{total_real}+{total_proy}*(1-{avance_acotado_xl}))'
        ),
        "Margen estimado al cierre": (
            f'=IF({i("Costo estimado al cierre")}="","",{venta}-{i("Costo estimado al cierre")})'
        ),
        "Margen estimado al cierre %": (
            f'=IF({i("Margen estimado al cierre")}="","",'
            f'{dividir(i("Margen estimado al cierre"), venta)})'
        ),
        "Desviación estimada al cierre %": (
            f'=IF(OR({i("Costo estimado al cierre")}="",{total_proy}=0),"",'
            f'{i("Costo estimado al cierre")}/{total_proy}-1)'
        ),
        # Escenario pesimista: Real / avance (ver costo_al_cierre_indice).
        "Margen al cierre % (escenario índice de costo)": (
            f'=IF(OR({avance}="",{venta}=0),"",IF({avance_acotado_xl}=0,"",'
            f"({venta}-{total_real}/{avance_acotado_xl})/{venta}))"
        ),
        "Error del presupuesto %": (
            f'=IF({total_proy}=0,"",('
            + "+".join(f"ABS({p(col_r)}-{p(col_p)})" for _, col_p, col_r in CATEGORIAS_KPI)
            + f")/{total_proy})"
        ),
        "Cliente": f'=IF({p("Cliente")}="","",{p("Cliente")})',
        "Monto de Venta (sin IVA)": f'=IF({venta}="","",{venta})',
        # Misma regla que tiene_datos_completos(): "" y vacío faltan, 0 no.
        "Datos completos": f'=IF(AND({cargados}),"Sí","No")',
    })
    return formulas


def asegurar_hoja_indicadores(wb, filas_validas: list[dict]) -> None:
    """Regenera 'Indicadores' completa: una fila compacta por proyecto
    válido (sin huecos), pero cada fórmula referencia la fila REAL del
    proyecto en 'Proyectos' (que sí puede tener huecos). Las fórmulas salen
    de formulas_indicadores() y se escriben bajo su encabezado por nombre."""
    ws = wb[HOJA_INDICADORES]
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)

    columna = {nombre: idx for idx, nombre in enumerate(HEADERS_INDICADORES, start=1)}
    for f, fila_info in enumerate(filas_validas, start=2):
        formulas = formulas_indicadores(fila_info["fila"], f)
        faltan = set(HEADERS_INDICADORES) - set(formulas)
        if faltan:
            raise ValueError(f"Columnas de 'Indicadores' sin fórmula: {sorted(faltan)}")
        for nombre, formula in formulas.items():
            ws.cell(row=f, column=columna[nombre], value=formula)


# ── HOJA "CLIENTES" (100% regenerada cada corrida) ──────────────────────────

def asegurar_hoja_clientes(wb, filas_validas: list[dict], ws_proyectos) -> None:
    """Regenera 'Clientes' completa: una fila por valor único de la columna
    'Cliente' de 'Proyectos' (sin "Gastos Generales"). Todas las columnas
    son fórmulas sobre 'Indicadores' que cuentan SOLO proyectos con 'Datos
    completos' = "Sí" -- la misma regla que el dashboard y los reportes
    (calcular_clientes es su espejo Python). Un cliente cuyos proyectos
    están todos a medio cargar queda en la lista con 0 proyectos y
    "Sin proyectos completos", fuera del cálculo de percentiles."""
    ws = wb[HOJA_CLIENTES]
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)

    col_cliente = HEADERS_PROYECTOS.index("Cliente") + 1
    col_categoria = HEADERS_PROYECTOS.index("Categoría") + 1
    clientes_unicos = []
    vistos = set()
    for fila_info in filas_validas:
        if ws_proyectos.cell(row=fila_info["fila"], column=col_categoria).value == CATEGORIA_GASTOS_GENERALES:
            continue
        cliente = ws_proyectos.cell(row=fila_info["fila"], column=col_cliente).value
        if cliente and cliente not in vistos:
            vistos.add(cliente)
            clientes_unicos.append(cliente)

    li = LETRA_COL_INDICADORES

    def rango(nombre):
        return f"Indicadores!${li[nombre]}:${li[nombre]}"

    criterios = f'{rango("Cliente")},$A{{i}},{rango("Datos completos")},"Sí"'
    ultima = 1 + len(clientes_unicos)
    # Percentil solo entre clientes con al menos un proyecto completo: la
    # división por (N° de proyectos > 0) da #DIV/0! en los demás, y la opción
    # 6 de AGGREGATE ignora errores. AGGREGATE(16,...) = PERCENTILE.INC y
    # acepta el arreglo sin Ctrl+Shift+Enter.
    margenes_validos = f"$D$2:$D${ultima}/($B$2:$B${ultima}>0)"

    for i, cliente in enumerate(sorted(clientes_unicos), start=2):
        crit = criterios.format(i=i)
        ws.cell(row=i, column=1, value=cliente)
        ws.cell(row=i, column=2, value=f"=COUNTIFS({crit})")
        ws.cell(row=i, column=3, value=f'=SUMIFS({rango("Monto de Venta (sin IVA)")},{crit})')
        ws.cell(row=i, column=4, value=f'=SUMIFS({rango("Margen estimado al cierre")},{crit})')
        ws.cell(row=i, column=5, value=f'=IF(C{i}=0,"",D{i}/C{i})')
        ws.cell(row=i, column=6, value=f'=IF(B{i}>=2,"Sí","No")')
        ws.cell(row=i, column=7, value=(
            f'=IF(B{i}=0,"{CLASIFICACION_SIN_PROYECTOS}",'
            f'IF(D{i}>=_xlfn.AGGREGATE(16,6,{margenes_validos},0.67),"Clientes estratégicos",'
            f'IF(D{i}>=_xlfn.AGGREGATE(16,6,{margenes_validos},0.33),"Clientes potenciales",'
            f'"Clientes de oportunidad")))'
        ))


# ── HOJA "GLOSARIO KPIS" (texto estatico, 100% regenerado cada corrida) ─────
# Contenido fijo -- no depende de datos del usuario. Cubre el playbook
# original (spec 2026-07-20) mas los KPIs de este spec (2026-07-21): Nota,
# Evaluacion, y los 6 de la hoja Clientes.

GLOSARIO_KPIS: list[tuple[str, str, str, str]] = [
    (
        "Margen neto %",
        "El indicador de rentabilidad más directo y comparable entre proyectos de distinto tamaño.",
        "Margen Real, Monto de Venta",
        "20% significa que de cada $100 vendidos quedan $20 de utilidad tras cubrir todos los costos reales.",
    ),
    (
        "Costo % de venta (por categoría)",
        "Muestra qué parte de cada peso VENDIDO se va en esa categoría de costo — mide el impacto de la categoría sobre el precio de venta.",
        "Costo Real de la categoría, Monto de Venta",
        "35% en Costo MO % de venta → un tercio de cada venta se destina a mano de obra; detecta categorías que consumen desproporcionadamente el margen.",
    ),
    (
        "Estructura % del costo real (mix, por categoría)",
        "Muestra cómo se reparte el GASTO real entre categorías (no contra la venta, sino entre sí) — las 4 categorías suman 100%, a diferencia de 'Costo % de venta' que no suma 100%.",
        "Costo Real de la categoría, Costos Totales Real",
        "60% en Estructura % Otros → 6 de cada $10 gastados en el proyecto fueron en 'Otros'; útil para ver dónde se concentra el gasto real sin importar cuán rentable resultó el proyecto.",
    ),
    (
        "Desviación % (por categoría, Real vs Proyectado)",
        "Mide qué tan preciso fue el presupuesto original para esa categoría — clave para mejorar futuras cotizaciones.",
        "Costo Real, Costo Proyectado de la categoría",
        "+15% = se gastó 15% más de lo presupuestado; negativo = se gastó menos de lo previsto.",
    ),
    (
        "Desviación % Total",
        "Mismo concepto que la desviación por categoría, pero a nivel de todo el proyecto — el número que resume si el presupuesto completo se cumplió.",
        "Costos Totales Real, Costos Totales Proyectado (columna ya existente en 'Proyectos', traída acá como columna visible)",
        "-10% = el proyecto costó 10% menos que lo presupuestado en total; +10% = costó 10% más.",
    ),
    (
        "Ahorro/Sobrecosto neto en $ (por categoría y total)",
        "Traduce la desviación % a pesos concretos — más accionable para decisiones de gestión que un porcentaje solo, sobre todo en categorías con montos grandes.",
        "Costo Proyectado − Costo Real, de cada categoría y del total",
        "Positivo = ahorro (se gastó menos de lo presupuestado); negativo = sobrecosto (se gastó más). $800.000 en Ahorro MO → la mano de obra costó $800.000 menos que lo presupuestado.",
    ),
    (
        "% Avance",
        "Permite leer un proyecto en curso por lo que va a terminar costando, no por lo que lleva gastado -- sin él, un proyecto recién empezado y uno casi terminado se veían idénticos. Reemplazó al campo de texto 'Estado' (Terminado / En Proceso) el 2026-08-28.",
        "Ingreso manual en la hoja 'Proyectos' (celda amarilla en cursiva), como porcentaje de 0% a 100%",
        "100% = ejecución terminada, los costos reales ya no deberían crecer. Bajo 100%, el costo que falta se estima a precio de presupuesto (ver 'Costo estimado al cierre'). Un valor fuera de 0-100% se acota y se avisa como alerta.",
    ),
    (
        "Costo estimado al cierre",
        "Lo que el proyecto va a terminar costando si lo que falta se ejecuta a precio de presupuesto. Evita leer un proyecto en curso como si ya hubiera terminado: el costo gastado a la fecha contra la venta completa infla el margen.",
        "Costos Totales Real, Costos Totales Proyectado, % Avance: Real + Proyectado × (1 − % Avance)",
        "Al 100% de avance es igual al costo real. Un proyecto al 75% de avance que ya gastó el 99% de su presupuesto estima terminar en 124% del presupuesto (99% + el 25% que falta).",
    ),
    (
        "Margen estimado al cierre (y %)",
        "El margen con el que el proyecto va a terminar según la estimación de arriba -- es el margen que usa la Nota del Proyecto y la hoja 'Clientes'.",
        "Monto de Venta − Costo estimado al cierre; el % se divide por el Monto de Venta",
        "En un proyecto terminado es el Margen Real. En uno en curso puede quedar bastante bajo el margen a la fecha si el gasto va adelantado respecto del avance.",
    ),
    (
        "Desviación estimada al cierre %",
        "Si el proyecto va a terminar sobre o bajo presupuesto, incluyendo lo que falta -- el componente de control de la Nota.",
        "Costo estimado al cierre / Costos Totales Proyectado − 1",
        "+10% = va a terminar costando 10% más que lo presupuestado. En un proyecto terminado es igual a 'Desviación % Total'.",
    ),
    (
        "Margen al cierre % (escenario índice de costo)",
        "Escenario pesimista, solo de referencia (no entra en la Nota): supone que el ritmo de gasto actual se mantiene hasta el final.",
        "Monto de Venta, Costos Totales Real, % Avance: costo al cierre = Real / % Avance",
        "Si queda muy por debajo del 'Margen estimado al cierre %', el sobrecosto viene de un ritmo de gasto sostenido, no de una compra puntual al inicio. Al 100% de avance coincide con el Margen neto %.",
    ),
    (
        "Nota del Proyecto",
        "Resume rentabilidad y control de presupuesto en un solo número comparable entre proyectos, para priorizar dónde poner atención de gestión.",
        "Margen estimado al cierre % (70% — curva: sube linealmente hasta el objetivo de 25% donde vale 70/100, y sigue subiendo por sobre el objetivo cada vez más despacio, sin techo fijo) y Desviación estimada al cierre % (30% — solo penaliza sobrecosto: 100 puntos en o bajo presupuesto, 0 puntos con +30% o más)",
        "≥55 = proyecto en rango aceptable; <55 = requiere revisión. Un proyecto en curso se evalúa por cómo va a terminar, no por lo gastado a la fecha. Un proyecto que ahorra obtiene el puntaje máximo del componente de control — ese beneficio ya se refleja en el margen. Llegar justo al objetivo de margen (25%) no basta para 'Excelente' — hace falta ~36% de margen con presupuesto controlado.",
    ),
    (
        "Evaluación",
        "Traduce la nota a una etiqueta rápida de lectura para revisiones ejecutivas.",
        "Nota del Proyecto",
        "Excelente (≥85) / Bueno (≥70) / Aprobado (≥55) / Requiere atención.",
    ),
    (
        "% del Total Real del proyecto (Detalle Costos Reales)",
        "Muestra el peso de cada subcategoría real de Centro de Costos (ej. Consumibles, Equipos-Herramientas, Combustible, Servicios) dentro del gasto detallado del proyecto — más granular que 'Estructura %' de 'Indicadores', que solo agrupa en 4 buckets.",
        "Total sin IVA de la fila, suma de todas las filas de ese proyecto en 'Detalle Costos Reales'",
        "Suma ~100% por proyecto. No incluye Mano de Obra Real (es manual, sin detalle por subcategoría en Centro de Costos) -- el 100% es sobre el gasto SÍ trazado a documentos, no sobre el Total Real completo del proyecto.",
    ),
    (
        "Peso del proyecto en la cartera de ventas (%)",
        "Mide qué tan concentrado está el ingreso de la empresa en un solo proyecto -- riesgo de dependencia si un proyecto grande se cae o se retrasa.",
        "Monto de Venta del proyecto, suma de Monto de Venta de todos los proyectos con venta cargada",
        "25% significa que un cuarto de todo el ingreso de la cartera actual depende de ese único proyecto; valores altos ameritan revisar el riesgo de concentración.",
    ),
    (
        "Margen por día de ejecución",
        "Mide cuánto margen genera el proyecto por unidad de tiempo -- útil para priorizar proyectos que compiten por la misma capacidad de equipo/tiempo, no solo por margen total.",
        "Margen Real, Fecha de cierre − Fecha de inicio (en días)",
        "$50.000/día = el proyecto generó en promedio $50.000 de margen por cada día que duró su ejecución. Queda vacío si falta alguna de las dos fechas o si la fecha de cierre todavía no llega (en desarrollo) -- no se calcula sobre una duración que aún no terminó.",
    ),
    (
        "Error del presupuesto %",
        "Mide qué tan bien repartido estaba el presupuesto entre categorías, sin que un error tape a otro -- la 'Desviación % Total' puede dar casi 0 con materiales muy por sobre lo previsto y equipos muy por debajo. Es el insumo para cotizar mejor.",
        "Suma de |Costo Real − Costo Proyectado| de las 4 categorías, dividida por el presupuesto total",
        "0% = el presupuesto acertó categoría por categoría. 65% = dos tercios del presupuesto quedaron en la categoría equivocada, aunque el total haya calzado. No juzga el resultado del proyecto (eso es el margen), juzga la cotización.",
    ),
    (
        "Datos completos",
        "Dice si el proyecto tiene cargados todos los datos manuales que necesita su Nota. Solo los proyectos completos entran en la hoja 'Clientes', el dashboard y los reportes.",
        "% Avance, Monto de Venta, los 4 costos proyectados y Mano de Obra Real (hoja 'Proyectos')",
        "'No' = falta al menos uno de esos datos; el dashboard lista cuáles. Un 0 cuenta como dato cargado; una celda vacía no.",
    ),
    (
        "N° de proyectos (Clientes)",
        "Cuántos proyectos completos tiene el cliente -- la base para saber si es recurrente.",
        "Proyectos de 'Indicadores' con ese Cliente y 'Datos completos' = Sí",
        "1 = cliente de una sola compra hasta ahora; 2 o más = recurrente. 0 = el cliente existe pero ninguno de sus proyectos tiene los datos completos.",
    ),
    (
        "Venta acumulada y Margen acumulado (Clientes)",
        "El valor que el cliente ya le dejó a QUEMPIN. Reemplazó al CLTV el 2026-09-21: la fórmula anterior (AOV × Frecuencia × Vida × Margen) contaba dos veces la cantidad de compras, y con clientes de un solo proyecto no hay historial para proyectar su valor futuro.",
        "Suma de Monto de Venta y de Margen estimado al cierre de sus proyectos completos",
        "Margen acumulado alto = cliente que ya generó mucho valor; prioridad para retención. En un proyecto en curso cuenta el margen estimado al cierre, no el de la fecha.",
    ),
    (
        "Margen % (Clientes)",
        "Qué tan rentable es la relación completa con ese cliente, ponderada por tamaño de proyecto.",
        "Margen acumulado / Venta acumulada",
        "Mismo significado que el Margen estimado al cierre % pero a nivel cliente.",
    ),
    (
        "Cliente recurrente / Tasa de recompra",
        "La señal más directa de un cliente que vuelve -- lo que el CLTV intentaba proyectar sin tener todavía historial.",
        "N° de proyectos del cliente (Sí con 2 o más); la tasa es recurrentes / clientes con al menos un proyecto completo",
        "Una tasa de recompra baja con clientes grandes es riesgo de concentración: el ingreso depende de conseguir clientes nuevos.",
    ),
    (
        "Clasificación (Clientes)",
        "Traduce el margen acumulado a un tier accionable, relativo a la cartera actual de QUEMPIN, no a un corte fijo en pesos que quede obsoleto con el crecimiento de la empresa.",
        "Percentil del Margen acumulado entre los clientes con al menos un proyecto completo",
        "'Clientes estratégicos' (top 33%) → atención prioritaria; 'Clientes de oportunidad' (bottom 33%) → candidatos a desarrollar o repensar la relación. Con pocos clientes el tier solo ordena por tamaño: leerlo junto al N° de proyectos.",
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


# ── ALERTAS DE TODA LA CARTERA (para la consola del run / status) ───────────

# Columnas de "Proyectos" que calcular_kpis_proyecto necesita como entrada --
# todas manuales o autocompletadas (valores, nunca fórmulas).
COLUMNAS_ENTRADA_KPIS = [
    "TAG proyecto", "Nombre del proyecto", "Cliente", "Categoría", "% Avance",
    "Fecha de inicio", "Fecha de cierre", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados", "Mano de Obra Real",
]


def valores_fila_proyectos(ws_proyectos, fila: int) -> dict:
    """Las COLUMNAS_ENTRADA_KPIS de una fila de 'Proyectos', keyed por
    encabezado del esquema (no del archivo, que puede tener otro texto en
    columnas de fórmula)."""
    return {
        nombre: ws_proyectos.cell(row=fila, column=HEADERS_PROYECTOS.index(nombre) + 1).value
        for nombre in COLUMNAS_ENTRADA_KPIS
    }


def costos_por_bucket(agrupado: dict[tuple[str, str], float]) -> dict[str, dict[str, float]]:
    """{tag: {bucket: total}} -- lo mismo que suman los SUMIFS de 'Proyectos'
    sobre 'Detalle Costos Reales', calculado desde el agrupado en memoria."""
    resultado: dict[str, dict[str, float]] = {}
    for (tag, subcategoria), total in agrupado.items():
        bucket, _ = mapear_categoria_a_bucket(subcategoria)
        resultado.setdefault(tag, {})
        resultado[tag][bucket] = resultado[tag].get(bucket, 0.0) + total
    return resultado


def alertas_de_cartera(ws_proyectos, filas_validas: list[dict], agrupado, hoy: date | None = None) -> list[str]:
    """alertas_proyecto() de cada proyecto válido, prefijadas con su nombre."""
    costos = costos_por_bucket(agrupado)
    salida = []
    for fila_info in filas_validas:
        valores = valores_fila_proyectos(ws_proyectos, fila_info["fila"])
        kpis = calcular_kpis_proyecto(valores, costos.get(fila_info["tag"], {}), hoy)
        for alerta in alertas_proyecto(valores, kpis, hoy):
            salida.append(f"{fila_info['nombre']} ({fila_info['tag']}): {alerta}")
    return salida


# ── INTERCAMBIO CON EL FORMULADOR DE PROYECTOS ──────────────────────────────
# Lógica y garantías en presupuestos_formulador.py; acá solo se le pasa la
# hoja y las filas, y se ordena en qué momento de ejecutar() corre cada parte.

def _columnas_proyectos() -> dict[str, int]:
    return {nombre: idx for idx, nombre in enumerate(HEADERS_PROYECTOS, start=1)}


def _primera_fila_libre(ws_proyectos) -> int:
    """Primera fila después de la última con TAG o Nombre -- no max(fila
    válida)+1: una fila a medio cargar (sin Nombre) no es válida pero tiene
    datos, y una fila nueva no puede caerle encima."""
    ultima = 1
    for fila in range(2, ws_proyectos.max_row + 1):
        if ws_proyectos.cell(row=fila, column=1).value is not None or ws_proyectos.cell(row=fila, column=2).value is not None:
            ultima = fila
    return ultima + 1


def preparar_intercambio(ws_proyectos, filas_validas: list[dict], raiz_intercambio: Path,
                         ruta_estado: Path, dry_run: bool) -> dict:
    """Lee el buzón y decide qué hacer con cada envío del Formulador. Sin
    dry_run, además crea la carpeta si falta, olvida la procedencia de lo que
    se cambió a mano y escribe las decisiones en la hoja (en memoria: el
    guardado es el de siempre, al final de ejecutar())."""
    columnas = _columnas_proyectos()
    filas_por_tag = {pf.normalizar_tag(f["tag"]): f["fila"] for f in filas_validas}
    estado = pf.leer_estado(ruta_estado)
    avisos = []
    if not dry_run:
        pf.intercambio.asegurar_carpeta(raiz_intercambio)
        avisos += pf.sincronizar_procedencia(ws_proyectos, filas_por_tag, columnas, estado)
    mensajes, avisos_buzon = pf.leer_buzon(raiz_intercambio)
    avisos += avisos_buzon
    actuales = {tag: pf.valores_actuales(ws_proyectos, fila, columnas) for tag, fila in filas_por_tag.items()}
    decisiones = pf.planificar(mensajes, filas_por_tag, actuales, estado)
    nuevas = []
    if not dry_run:
        nuevas = pf.aplicar(ws_proyectos, decisiones, filas_por_tag, columnas, _primera_fila_libre(ws_proyectos))
    return {
        "raiz": raiz_intercambio, "ruta_estado": ruta_estado, "estado": estado,
        "decisiones": decisiones, "nuevas": nuevas, "avisos": avisos,
    }


def proyectos_para_catalogo(ws_proyectos, filas_validas: list[dict], agrupado) -> list[dict]:
    """Lo que el Formulador necesita de cada proyecto para elegir a cuál
    enviar y mostrar qué va a cambiar. Sin 'Gastos Generales' (no es un
    proyecto al que se le cotice) ni venta/márgenes (no los necesita)."""
    costos = costos_por_bucket(agrupado)
    salida = []
    for fila_info in filas_validas:
        valores = valores_fila_proyectos(ws_proyectos, fila_info["fila"])
        if valores.get("Categoría") == CATEGORIA_GASTOS_GENERALES:
            continue
        reales = costos.get(fila_info["tag"], {})
        salida.append({
            "tag": pf.normalizar_tag(fila_info["tag"]), "nombre": fila_info["nombre"],
            "cliente": valores.get("Cliente"), "categoria": valores.get("Categoría"),
            "avance": valores.get("% Avance"),
            "proyectados": {c: valores.get(col) for c, col in pf.COLUMNA_POR_CATEGORIA.items()},
            "reales": {
                "Materiales": reales.get("Materiales", 0.0), "Equipos": reales.get("Equipos", 0.0),
                "Mano de Obra": valores.get("Mano de Obra Real"), "Otros": reales.get("Otros", 0.0),
            },
        })
    return salida


def cerrar_intercambio(contexto: dict, ws_proyectos, filas_validas: list[dict], agrupado) -> list[str]:
    """Después de guardar el Excel: registra la procedencia, archiva los
    envíos atendidos y publica el catálogo para el Formulador."""
    avisos = pf.finalizar(contexto["raiz"], contexto["decisiones"], contexto["estado"], contexto["ruta_estado"])
    pf.publicar_catalogo(
        contexto["raiz"], proyectos_para_catalogo(ws_proyectos, filas_validas, agrupado),
        contexto["estado"], contexto["decisiones"],
    )
    return avisos


def publicar_intercambio(pais: str = "CL") -> dict:
    """Publica el catálogo para el Formulador **sin escribir el Excel** (solo
    lo lee, igual que Centro de Costos): para conectar el Formulador o
    refrescar su lista sin esperar un run. No aplica ningún envío del buzón
    -- eso solo lo hace ejecutar(), con respaldo y guardado. Escribe
    únicamente en la carpeta de Intercambio (la crea si falta)."""
    cfg = PAISES[pais]
    raiz = cfg.get("raiz_intercambio")
    if raiz is None:
        return {"error": f"El intercambio con el Formulador no está activo para {pais}.", "ruta": None}
    if not cfg["ruta_excel_af"].exists() or not cfg["ruta_excel_cc"].exists():
        return {"error": "Falta el Excel de Análisis Financiero o el de Centro de Costos.", "ruta": None}
    wb = openpyxl.load_workbook(cfg["ruta_excel_af"])   # nunca se guarda
    ws_proyectos = wb[HOJA_PROYECTOS]
    filas_validas, _ = leer_filas_proyectos(ws_proyectos)
    items_detalle, _, _ = cargar_datos_centro_costos(cfg["ruta_excel_cc"], pais)
    agrupado = agrupar_por_proyecto_y_subcategoria(items_detalle)
    contexto = preparar_intercambio(
        ws_proyectos, filas_validas, raiz, cfg["ruta_estado_intercambio"], dry_run=True,
    )
    pf.intercambio.asegurar_carpeta(raiz)
    proyectos = proyectos_para_catalogo(ws_proyectos, filas_validas, agrupado)
    ruta = pf.publicar_catalogo(raiz, proyectos, contexto["estado"], contexto["decisiones"])
    return {"error": None, "ruta": ruta, "proyectos": len(proyectos)}


# ── ORQUESTADOR ───────────────────────────────────────────────────────────

def cargar_datos_centro_costos(ruta_excel_cc: Path, pais: str = "CL"):
    """(items_detalle, tipos_por_prefijo, nombres_por_prefijo) de Centro de
    Costos, solo lectura.

    Las tres lecturas salen del snapshot JSON que deja su visualizador
    (PASO 12c, inmediatamente antes de este modulo), y solo si esta al dia.
    Antes cada lector abria el .xlsx por su cuenta -- tres load_workbook del
    mismo archivo, dos de ellos sobre la misma hoja Master -- y eso era ~1,6s
    de los 2,8s de ejecutar(), el paso mas caro de toda la cadena. Si el
    snapshot no sirve se cae al Excel, abriendolo una sola vez y compartiendo
    el wb. Nunca se escribe ese libro. (Extraída de ejecutar() el 2026-09-30
    para que publicar_intercambio lea exactamente lo mismo.)"""
    if snapshot_al_dia(ruta_excel=ruta_excel_cc):
        desde_snapshot = leer_centro_costos_desde_snapshot(pais=pais)
        if desde_snapshot is not None:
            return desde_snapshot
    wb_cc = openpyxl.load_workbook(ruta_excel_cc, data_only=True)
    return (
        leer_detalle_centro_costos(ruta_excel_cc, pais=pais, wb=wb_cc),
        leer_tipo_proyecto_centro_costos(ruta_excel_cc, wb=wb_cc),
        leer_nombres_proyecto_centro_costos(ruta_excel_cc, wb=wb_cc),
    )


def actualizar_visualizador_af(pais: str = "CL") -> bool:
    """Regenera el visualizador web (Visualizador Web/build/index.html) a
    partir del Excel recien guardado -- mismo patron que actualizar_
    visualizador() en Centro de Costos: corre al final de ejecutar(), solo
    lee el Excel (no lo modifica), y si falla no aborta el run, solo
    advierte -- el Excel ya quedo guardado igual. Ver Visualizador Web/
    CLAUDE.md para la arquitectura del build.

    'pais' resuelve la carpeta del visualizador via PAISES -- "CL" preserva
    el comportamiento anterior a este parametro."""
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


def ejecutar(
    ruta_excel_af: Path | None = None,
    ruta_excel_cc: Path | None = None,
    raiz_facturas_cc: Path | None = None,
    raiz_respaldos: Path = RAIZ_RESPALDOS,
    ruta_clientes_pendientes: Path = RUTA_CLIENTES_PENDIENTES,
    dry_run: bool = False,
    pais: str = "CL",
    raiz_intercambio: Path | None = None,
    ruta_estado_intercambio: Path | None = None,
) -> dict:
    """Orquesta todo el flujo. Con dry_run=True no escribe nada -- ni backup,
    ni carpetas, ni el Excel -- solo reporta qué pasaría (usado por el
    comando 'status' del skill). Captura PermissionError/OSError de operaciones
    de archivo (backup, carpetas, save); excepciones de lectura de datos
    propagarán hacia afuera.

    'pais' resuelve ruta_excel_af/ruta_excel_cc/raiz_facturas_cc via PAISES
    cuando se omiten -- un valor explícito para cualquiera de los 3 sigue
    ganando (mismo contrato que antes de este parámetro, con "CL" como
    default transparente).

    Intercambio con el Formulador (2026-09-30): corre solo contra el libro
    del país (ruta_excel_af omitida) o si quien llama pasa su propia
    raiz_intercambio -- un test con un Excel temporal nunca lee ni escribe la
    carpeta real. Nunca aborta la corrida: si falla, queda como aviso."""
    cfg = PAISES[pais]
    libro_del_pais = ruta_excel_af is None
    if raiz_intercambio is None and libro_del_pais:
        raiz_intercambio = cfg.get("raiz_intercambio")
    if raiz_intercambio is not None and ruta_estado_intercambio is None:
        ruta_estado_intercambio = (
            (cfg.get("ruta_estado_intercambio") if libro_del_pais else None)
            or Path(raiz_intercambio).parent / pf.RUTA_ESTADO.name
        )
    if ruta_excel_af is None:
        ruta_excel_af = cfg["ruta_excel_af"]
    if ruta_excel_cc is None:
        ruta_excel_cc = cfg["ruta_excel_cc"]
    if raiz_facturas_cc is None:
        raiz_facturas_cc = cfg["raiz_facturas_cc"]

    resumen = {
        "avisos": [], "carpetas_creadas": [], "categorias_no_mapeadas": [],
        "clientes_pendientes": [], "proyectos_nuevos": [], "alertas": [], "error": None,
        "intercambio": {},
    }
    if libro_del_pais and raiz_intercambio is None and cfg.get("aviso_sin_intercambio"):
        resumen["avisos"].append(cfg["aviso_sin_intercambio"])

    wb = asegurar_estructura_workbook(ruta_excel_af)
    ws_proyectos = wb[HOJA_PROYECTOS]
    filas_validas, avisos_lectura = leer_filas_proyectos(ws_proyectos)
    resumen["avisos"].extend(avisos_lectura)

    if not ruta_excel_cc.exists():
        resumen["avisos"].append(
            f"No se encontró {ruta_excel_cc}, no se actualizan costos reales."
        )
        return resumen

    items_detalle, tipos_por_prefijo, nombres_por_prefijo_cc = cargar_datos_centro_costos(ruta_excel_cc, pais)
    agrupado = agrupar_por_proyecto_y_subcategoria(items_detalle)
    tags_existentes = {f["tag"] for f in filas_validas}
    prefijos_faltantes = {
        prefijo: nombre for prefijo, nombre in nombres_por_prefijo_cc.items()
        if prefijo not in tags_existentes
    }

    if dry_run:
        resumen["proyectos_nuevos"] = [prefijos_faltantes[p] for p in sorted(prefijos_faltantes)]
        for fila_info in filas_validas:
            if not carpeta_proyecto_existe(fila_info["nombre"], raiz_facturas_cc):
                resumen["carpetas_creadas"].append(fila_info["nombre"])
        categorias_no_mapeadas = set()
        for _, subcategoria in agrupado:
            _, es_explicito = mapear_categoria_a_bucket(subcategoria)
            if not es_explicito:
                categorias_no_mapeadas.add(subcategoria)
        resumen["categorias_no_mapeadas"] = sorted(categorias_no_mapeadas)
        resumen["alertas"] = alertas_de_cartera(ws_proyectos, filas_validas, agrupado)
        if raiz_intercambio is not None:
            try:
                previo = preparar_intercambio(
                    ws_proyectos, filas_validas, raiz_intercambio, ruta_estado_intercambio, dry_run=True,
                )
                resumen["intercambio"] = pf.resumen_decisiones(previo["decisiones"])
                resumen["avisos"].extend(previo["avisos"])
            except Exception as exc:
                resumen["avisos"].append(f"Intercambio con el Formulador: no se pudo revisar el buzón ({exc}).")
        return resumen

    if prefijos_faltantes:
        proyectos_nuevos = crear_filas_proyectos_nuevos(ws_proyectos, filas_validas, prefijos_faltantes)
        resumen["proyectos_nuevos"] = [f["nombre"] for f in proyectos_nuevos]
        filas_validas.extend(proyectos_nuevos)

    try:
        hacer_backup(ruta_excel_af, raiz_respaldos)
    except PermissionError as exc:
        resumen["avisos"].append(f"No se pudo respaldar (¿archivo abierto?): {exc}")

    # Costos proyectados enviados por el Formulador: se escriben antes de
    # las fórmulas, Clientes e Indicadores para que esta misma corrida (y el
    # dashboard) ya los use. Si algo falla, la corrida sigue sin ellos.
    contexto_intercambio = None
    if raiz_intercambio is not None:
        try:
            contexto_intercambio = preparar_intercambio(
                ws_proyectos, filas_validas, raiz_intercambio, ruta_estado_intercambio, dry_run=False,
            )
            filas_validas.extend(contexto_intercambio["nuevas"])
            resumen["proyectos_nuevos"].extend(f["nombre"] for f in contexto_intercambio["nuevas"])
            resumen["intercambio"] = pf.resumen_decisiones(contexto_intercambio["decisiones"])
            resumen["avisos"].extend(contexto_intercambio["avisos"])
        except Exception as exc:
            contexto_intercambio = None
            resumen["avisos"].append(f"Intercambio con el Formulador: se omitió en esta corrida ({exc}).")

    try:
        resumen["carpetas_creadas"] = asegurar_carpetas_proyectos(filas_validas, raiz_facturas_cc)
    except OSError as exc:
        resumen["avisos"].append(f"No se pudieron crear una o más carpetas de proyecto: {exc}")

    avisos_detalle = regenerar_hoja_detalle_costos_reales(wb, agrupado)
    resumen["avisos"].extend(avisos_detalle)
    categorias_no_mapeadas = set()
    for _, subcategoria in agrupado:
        _, es_explicito = mapear_categoria_a_bucket(subcategoria)
        if not es_explicito:
            categorias_no_mapeadas.add(subcategoria)
    resumen["categorias_no_mapeadas"] = sorted(categorias_no_mapeadas)

    resumen["clientes_pendientes"] = asegurar_columna_cliente(
        ws_proyectos, filas_validas, ruta_clientes_pendientes
    )

    asegurar_formulas_proyectos(ws_proyectos, filas_validas)
    # tipos_por_prefijo ya viene resuelto de arriba, junto con las otras dos
    # lecturas de Centro de Costos -- sea del snapshot o del Excel.
    col_categoria = HEADERS_PROYECTOS.index("Categoría") + 1
    resumen["avisos"].extend(
        asegurar_categoria_proyectos(ws_proyectos, filas_validas, tipos_por_prefijo, col_categoria)
    )
    resumen["alertas"] = alertas_de_cartera(ws_proyectos, filas_validas, agrupado)
    asegurar_hoja_indicadores(wb, filas_validas)
    asegurar_hoja_clientes(wb, filas_validas, ws_proyectos)
    asegurar_hoja_glosario_kpis(wb)
    aplicar_estilo_visual(wb)
    migrar_formato_fecha_proyectos(wb)
    aplicar_resaltado_celdas_manuales(wb)

    try:
        wb.save(ruta_excel_af)
    except PermissionError as exc:
        resumen["error"] = f"No se pudo guardar {ruta_excel_af} (¿archivo abierto?): {exc}"

    # Solo con el Excel ya guardado: si no se pudo guardar, los envíos del
    # Formulador siguen en el buzón y se aplican en la próxima corrida.
    if contexto_intercambio is not None and resumen["error"] is None:
        try:
            resumen["avisos"].extend(cerrar_intercambio(contexto_intercambio, ws_proyectos, filas_validas, agrupado))
        except Exception as exc:
            resumen["avisos"].append(f"Intercambio con el Formulador: el Excel quedó guardado, pero no se pudo "
                                     f"archivar ni publicar ({exc}); se reintenta en la próxima corrida.")

    try:
        if not actualizar_visualizador_af(pais=pais):
            resumen["avisos"].append(
                "No se pudo actualizar el visualizador web -- correr manualmente "
                "'python driver.py visualizador' despues."
            )
    except Exception as exc:
        resumen["avisos"].append(f"No se pudo actualizar el visualizador web: {exc}")

    return resumen


def main(pais: str = "CL") -> None:
    resumen = ejecutar(pais=pais)
    print(f"=== Análisis Financiero{' - ' + pais if pais != 'CL' else ''} ===")
    if resumen["proyectos_nuevos"]:
        print(
            f"Proyectos nuevos agregados desde Centro de Costos (TAG + Nombre; "
            f"Cliente/Categoría autocompletados, el resto queda pendiente a mano): "
            + ", ".join(resumen["proyectos_nuevos"])
        )
    if resumen["carpetas_creadas"]:
        print(f"Carpetas de proyecto creadas: {', '.join(resumen['carpetas_creadas'])}")
    if resumen["categorias_no_mapeadas"]:
        print(
            "Categorías sin mapeo explícito (van a 'Otros'): "
            + ", ".join(resumen["categorias_no_mapeadas"])
        )
    if resumen["clientes_pendientes"]:
        print(
            f"[AVISO] {len(resumen['clientes_pendientes'])} cliente(s) nuevo(s) parecido(s) "
            "a uno existente -- revisar con 'python driver.py confirmar-cliente'."
        )
    imprimir_intercambio(resumen["intercambio"], aplicado=not resumen["error"])
    for aviso in resumen["avisos"]:
        print(f"[AVISO] {aviso}")
    for alerta in resumen["alertas"]:
        print(f"[ALERTA] {alerta}")
    if resumen["error"]:
        print(f"[ERROR] {resumen['error']}")


TITULOS_INTERCAMBIO = {
    "aplicar": ("Costos proyectados aplicados desde el Formulador", "Se aplicarían desde el Formulador"),
    "sin-cambios": ("Envíos del Formulador que ya coincidían con el Excel", "Envíos del Formulador que ya coinciden con el Excel"),
    "pendiente": ("Envíos del Formulador que esperan tu decisión (siguen en el buzón)",) * 2,
    "reemplazado": ("Envíos del Formulador reemplazados por uno más reciente", "Se archivarían por haber uno más reciente"),
    "rechazado": ("Envíos del Formulador rechazados por formato", "Se rechazarían por formato"),
}


def imprimir_intercambio(por_accion: dict, aplicado: bool = True) -> None:
    """Sección de consola de run (aplicado=True) y status (False)."""
    for accion in ("aplicar", "pendiente", "sin-cambios", "reemplazado", "rechazado"):
        if por_accion.get(accion):
            print(f"{TITULOS_INTERCAMBIO[accion][0 if aplicado else 1]}:")
            for linea in por_accion[accion]:
                print(f"  - {linea}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
