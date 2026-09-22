# -*- coding: utf-8 -*-
"""
kpis_recalculados.py -- KPIs de 'Proyectos'/'Indicadores'/'Clientes' en
Python, para que los reportes PDF nunca dependan de que alguien abra el Excel.
openpyxl no cachea el resultado de una fórmula que él mismo escribe -- solo
el texto "=A1+B1" -- así que leerlas con data_only=True devuelve None hasta
que un humano abre el archivo en Excel/LibreOffice y lo guarda.

Desde 2026-09-21 este módulo NO calcula nada por su cuenta: delega en
analisis_financiero.calcular_kpis_proyecto() / calcular_clientes(), la única
implementación Python de los KPIs (la misma que usa el dashboard). Antes
replicaba cada fórmula "en espejo", y el espejo ya se había desincronizado
una vez (la Nota, 2026-07-28). Acá solo queda la traducción al formato que
consumen los reportes: (proyecto actualizado, indicadores) por proyecto y un
dict por cliente.
"""

import sys
from pathlib import Path

RAIZ_REPORTES = Path(__file__).resolve().parent
RAIZ_SISTEMA = RAIZ_REPORTES.parent / "Sistema"
if str(RAIZ_SISTEMA) not in sys.path:
    sys.path.insert(0, str(RAIZ_SISTEMA))

from analisis_financiero import (  # noqa: E402,F401
    HEADERS_INDICADORES,
    # _redondear_excel/calcular_nota/clasificar_evaluacion se re-exportan
    # aunque este modulo ya no los llame: son parte de la superficie publica
    # que sus tests ejercitan.
    _redondear_excel, calcular_clientes, calcular_kpis_proyecto, calcular_nota,
    clasificar_evaluacion, percentil_inclusivo, tiene_datos_completos,
)

# Columnas de 'Proyectos' que son fórmula (derivadas): el reporte las recibe
# recalculadas dentro del dict del proyecto, igual que si Excel las hubiera
# evaluado.
COLUMNAS_DERIVADAS_PROYECTOS = [
    "Costos Materiales Reales", "Costos Equipos Reales", "Otros Costos Reales",
    "Total Proyectado", "Total Real", "Margen Proyectado", "Margen Real",
    "Desviación % (Real vs Proyectado)",
]

# Columnas de 'Indicadores' que NO son un indicador del proyecto: identidad,
# columnas de apoyo de la hoja 'Clientes', y el peso en cartera (depende de
# toda la cartera, no del proyecto solo). La página 1 del reporte lista
# todos los indicadores sin selección editorial, así que no deben colarse.
_COLUMNAS_NO_INDICADOR = {
    "TAG proyecto", "Nombre del proyecto", "Cliente", "Monto de Venta (sin IVA)",
    "Datos completos", "Peso del proyecto en la cartera de ventas (%)",
}


def _percentil_excel(ordenados: list[float], p: float) -> float:
    """PERCENTILE.INC de Excel -- ver analisis_financiero.percentil_inclusivo."""
    return percentil_inclusivo(ordenados, p)


def costos_reales_por_proyecto(filas_detalle: list[dict]) -> dict[str, dict[str, float]]:
    """Agrupa filas de 'Detalle Costos Reales' (TAG proyecto/Bucket/Total
    sin IVA) por (tag, bucket), sumando -- lo mismo que los SUMIFS de
    'Proyectos'. Un bucket sin filas para ese tag no aparece en el dict
    resultante: calcular_kpis_proyecto lo toma como 0, igual que SUMIFS sin
    coincidencias."""
    resultado: dict[str, dict[str, float]] = {}
    for fila in filas_detalle:
        tag = fila.get("TAG proyecto")
        bucket = fila.get("Bucket")
        total = fila.get("Total sin IVA")
        if not tag or not bucket or total is None:
            continue
        resultado.setdefault(tag, {})
        resultado[tag][bucket] = resultado[tag].get(bucket, 0.0) + total
    return resultado


def recalcular_proyecto(proyecto: dict, costos_reales: dict[str, float], hoy=None) -> tuple[dict, dict]:
    """(proyecto con sus columnas derivadas recalculadas, indicadores del
    proyecto) -- ambos keyed por encabezado. No muta los argumentos.
    `proyecto` es una fila de 'Proyectos' keyed por encabezado;
    `costos_reales`, {'Materiales'/'Equipos'/'Otros': total}."""
    kpis = calcular_kpis_proyecto(proyecto, costos_reales, hoy)
    proyecto_actualizado = dict(proyecto)
    proyecto_actualizado.update({col: kpis[col] for col in COLUMNAS_DERIVADAS_PROYECTOS})
    indicadores = {
        col: kpis[col] for col in HEADERS_INDICADORES
        if col not in _COLUMNAS_NO_INDICADOR
    }
    return proyecto_actualizado, indicadores


def calcular_clientes_reporte(entradas: list[dict]) -> dict[str, dict]:
    """KPIs de la hoja 'Clientes' por nombre de cliente, a partir de
    entradas {"proyecto", "indicadores"} (las de recalcular_proyecto). Debe
    recibir TODOS los proyectos del libro a la vez: la Clasificación de cada
    cliente es un percentil entre todos los clientes. Solo cuentan los
    proyectos con datos completos, igual que la hoja y el dashboard."""
    kpis = []
    for e in entradas:
        proyecto = e["proyecto"]
        kpis.append({
            **e["indicadores"],
            "Cliente": proyecto.get("Cliente"),
            "Categoría": proyecto.get("Categoría"),
            "Monto de Venta (sin IVA)": proyecto.get("Monto de Venta (sin IVA)"),
            "Datos completos": "Sí" if tiene_datos_completos(proyecto.get) else "No",
        })
    return {fila["Cliente"]: fila for fila in calcular_clientes(kpis)}
