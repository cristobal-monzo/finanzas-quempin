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

import math
import sys
from datetime import datetime
from pathlib import Path

import openpyxl

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


def _round_excel(valor: float) -> int:
    """round-half-away-from-zero, igual que ROUND() de Excel -- round() nativo
    de Python usa banker's rounding (redondeo al par mas cercano) y puede
    dejar la Nota en el bucket de evaluacion equivocado justo en un empate
    exacto en .5 (ej. 96.5 -> 96 en Python vs 97 en Excel). `nota` siempre es
    un valor 0-100 (no negativo) tras los MIN/MAX de los scores, asi que
    floor(x+0.5) alcanza."""
    return math.floor(valor + 0.5)


def calcular_kpis_proyecto(p: dict, costos_reales: dict) -> dict:
    """Recomputa, en Python, las mismas formulas que asegurar_formulas_
    proyectos/_formula_nota/_formula_evaluacion escriben en el Excel."""
    total_proyectado = p["materiales_proy"] + p["equipos_proy"] + p["mo_proy"] + p["otros_proy"]
    total_real = costos_reales["Materiales"] + costos_reales["Equipos"] + costos_reales["Otros"] + p["mo_real"]
    margen_real = p["monto_venta"] - total_real
    desviacion_pct = (total_real / total_proyectado - 1) if total_proyectado else 0.0

    if p["monto_venta"]:
        score_margen = min(100, max(0, (margen_real / p["monto_venta"]) / MARGEN_OBJETIVO_NOTA * 100))
    else:
        # Venta en 0 es un dato "completo" valido (ver es_proyecto_completo),
        # pero no hay ratio de margen que calcular contra una venta nula.
        score_margen = 0
    score_desviacion = min(100, max(0, 100 - abs(desviacion_pct) * 100))
    nota = _round_excel(PESO_RENTABILIDAD_NOTA * score_margen + PESO_DESVIACION_NOTA * score_desviacion)
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


def percentil_inclusivo(valores: list[float], p: float) -> float:
    """Replica PERCENTILE (legacy/inclusive) de Excel: interpolacion lineal
    sobre la lista ordenada, rango 0-indexado = p*(n-1). Con un solo valor,
    Excel tambien devuelve ese unico valor."""
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
    """Agrupa kpis_proyectos_completos por 'cliente' y recomputa AOV/Vida/
    Meses activo/Frecuencia/Margen%/CLTV -- mismas formulas que
    asegurar_hoja_clientes en analisis_financiero.py, pero usando SOLO
    proyectos completos (spec §3: un proyecto incompleto de un cliente no
    contamina su CLTV, como si todavia no existiera)."""
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
            meses_activo = max(1.0, (max(fechas) - min(fechas)).days / 30)
        else:
            meses_activo = 1.0
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


def extraer_datos_saneados(ruta_excel=RUTA_EXCEL) -> dict:
    """Arma el snapshot saneado completo: proyectos completos + sus KPIs,
    clientes + su CLTV (excluyendo incompletos), y la lista de proyectos
    pendientes de completar con el mensaje y link fijos (spec §1/§3).
    `ruta_excel` es parametrizable para testear contra un workbook temporal,
    nunca el Excel real de la empresa."""
    wb = openpyxl.load_workbook(str(ruta_excel), data_only=True)
    ws_proyectos = wb[af.HOJA_PROYECTOS]
    ws_detalle = wb[af.HOJA_DETALLE_COSTOS_REALES]

    proyectos = leer_proyectos(ws_proyectos)
    proyectos_por_tag = {p["tag"]: p for p in proyectos}

    completos = []
    pendientes = []
    for p in proyectos:
        if es_proyecto_completo(p):
            costos_reales = sumar_costos_reales_por_bucket(ws_detalle, p["tag"])
            completos.append(calcular_kpis_proyecto(p, costos_reales))
        else:
            pendientes.append({
                "tag": p["tag"],
                "nombre": p["nombre"],
                "mensaje": f"{p['nombre']} — Falta ingresar información en 'Análisis de Proyectos'",
                "link": URL_PLANILLA_PENDIENTE,
            })

    clientes = calcular_clientes(completos, proyectos_por_tag)

    pendientes_por_cliente: dict[str, int] = {}
    for p in proyectos:
        if not es_proyecto_completo(p) and p["cliente"]:
            pendientes_por_cliente[p["cliente"]] = pendientes_por_cliente.get(p["cliente"], 0) + 1
    for c in clientes:
        c["proyectos_pendientes"] = pendientes_por_cliente.get(c["cliente"], 0)

    n_completos = len(completos)
    return {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "kpis_proyectos": {
            "n_completos": n_completos,
            "margen_real_total": sum(k["margen_real"] for k in completos),
            "nota_promedio": (sum(k["nota"] for k in completos) / n_completos) if n_completos else 0,
            "n_requiere_atencion": sum(1 for k in completos if k["evaluacion"] == "Requiere atención"),
        },
        "proyectos": completos,
        "clientes": clientes,
        "pendientes": pendientes,
    }
