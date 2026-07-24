# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el visualizador web de Análisis Financiero.

Las hojas "Indicadores"/"Clientes" de Análisis de Proyectos.xlsx son 100%
formulas que analisis_financiero.py reescribe en cada corrida -- openpyxl
nunca las calcula, asi que su valor cacheado queda obsoleto justo despues de
guardar. Este script NUNCA lee esas celdas: recomputa las mismas formulas en
Python a partir de las columnas manuales de "Proyectos" y de la hoja
"Detalle Costos Reales" (100% valores, no formulas anidadas). Mismo patron ya
resuelto en Centro de Costos/Visualizador Web/build_visualizador.py.

Ver docs/superpowers/specs/2026-07-23-analisis-financiero-visualizador-web-
design.md para el diseno completo.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Sistema"))
import analisis_financiero as af  # noqa: E402

RAIZ = Path(__file__).resolve().parent  # Sistema Analisis Financiero/Visualizador Web/
RUTA_EXCEL = af.RUTA_EXCEL
RUTA_TEMPLATE = RAIZ / "template.html"
RUTA_DATA_JSON = RAIZ / "data" / "analisis-financiero.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"

URL_PLANILLA_PENDIENTE = (
    "https://quempinspa2020.sharepoint.com/:x:/g/"
    "IQB005ljfV3VQp6CNg8pSS0tAdjFPmF8jOcQOeU3y0vIaIE?e=kaFVjO"
)

MARGEN_OBJETIVO_NOTA = af.MARGEN_OBJETIVO_NOTA
PESO_RENTABILIDAD_NOTA = af.PESO_RENTABILIDAD_NOTA
PESO_DESVIACION_NOTA = af.PESO_DESVIACION_NOTA

COLUMNAS_MANUALES_COMPLETITUD = (
    "monto_venta", "materiales_proy", "equipos_proy", "mo_proy", "otros_proy", "mo_real",
)


def _valor_columna(ws, fila, nombre_columna):
    col = af.HEADERS_PROYECTOS.index(nombre_columna) + 1
    return ws.cell(row=fila, column=col).value


def leer_proyectos(ws_proyectos) -> list[dict]:
    """Lee todas las filas validas (TAG y Nombre no vacios) de 'Proyectos'
    con sus columnas manuales crudas -- solo lectura, nunca toca el Excel."""
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
            "monto_venta": _valor_columna(ws_proyectos, fila, "Monto de Venta (sin IVA)"),
            "materiales_proy": _valor_columna(ws_proyectos, fila, "Costos Materiales Proyectados"),
            "equipos_proy": _valor_columna(ws_proyectos, fila, "Costos Equipos Proyectados"),
            "mo_proy": _valor_columna(ws_proyectos, fila, "Mano de Obra Proyectada"),
            "otros_proy": _valor_columna(ws_proyectos, fila, "Otros Costos Proyectados"),
            "mo_real": _valor_columna(ws_proyectos, fila, "Mano de Obra Real"),
        })
    return proyectos


def es_proyecto_completo(p: dict) -> bool:
    """Completo = las 6 columnas de carga manual que alimentan Total Real/
    Margen/Nota tienen un valor no vacio -- 0 SI cuenta como cargado (un
    costo real en cero es un dato, no un vacio todavia sin ingresar)."""
    return all(p[campo] is not None for campo in COLUMNAS_MANUALES_COMPLETITUD)


def sumar_costos_reales_por_bucket(ws_detalle, tag: str) -> dict:
    """Recomputa las 3 sumas que en 'Proyectos' son SUMIFS hacia 'Detalle
    Costos Reales' -- lee esa hoja directo (100% valores) en vez de confiar
    en el cache de la formula."""
    sumas = {"Materiales": 0.0, "Equipos": 0.0, "Otros": 0.0}
    for fila in range(2, ws_detalle.max_row + 1):
        fila_tag = ws_detalle.cell(row=fila, column=1).value
        bucket = ws_detalle.cell(row=fila, column=3).value
        total = ws_detalle.cell(row=fila, column=4).value
        if fila_tag == tag and bucket in sumas and total is not None:
            sumas[bucket] += total
    return sumas


def calcular_kpis_proyecto(p: dict, costos_reales: dict) -> dict:
    """Recomputa, en Python, las mismas formulas que asegurar_formulas_
    proyectos/_formula_nota/_formula_evaluacion escriben en el Excel."""
    total_proyectado = p["materiales_proy"] + p["equipos_proy"] + p["mo_proy"] + p["otros_proy"]
    total_real = costos_reales["Materiales"] + costos_reales["Equipos"] + costos_reales["Otros"] + p["mo_real"]
    margen_real = p["monto_venta"] - total_real
    desviacion_pct = (total_real / total_proyectado - 1) if total_proyectado else 0.0

    score_margen = min(100, max(0, (margen_real / p["monto_venta"]) / MARGEN_OBJETIVO_NOTA * 100))
    score_desviacion = min(100, max(0, 100 - abs(desviacion_pct) * 100))
    nota = round(PESO_RENTABILIDAD_NOTA * score_margen + PESO_DESVIACION_NOTA * score_desviacion)
    if nota >= 85:
        evaluacion = "Excelente"
    elif nota >= 70:
        evaluacion = "Bueno"
    elif nota >= 55:
        evaluacion = "Aprobado"
    else:
        evaluacion = "Requiere atención"

    return {
        "tag": p["tag"], "nombre": p["nombre"], "cliente": p["cliente"], "estado": p["estado"],
        "monto_venta": p["monto_venta"], "total_proyectado": total_proyectado,
        "total_real": total_real, "margen_real": margen_real, "desviacion_pct": desviacion_pct,
        "nota": nota, "evaluacion": evaluacion,
    }
