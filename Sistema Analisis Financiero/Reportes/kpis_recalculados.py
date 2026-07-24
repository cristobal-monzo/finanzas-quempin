# -*- coding: utf-8 -*-
"""
kpis_recalculados.py -- Recalcula en Python los KPIs derivados que
'analisis_financiero.py' escribe como fórmulas de Excel (Proyectos/
Indicadores/Clientes). openpyxl no cachea el resultado de una fórmula que
él mismo escribe -- solo el texto "=A1+B1" -- así que leerlas con
data_only=True devuelve None hasta que un humano abre el archivo en Excel/
LibreOffice y lo guarda. Este módulo replica exactamente esas mismas
fórmulas para que los reportes PDF nunca dependan de ese paso manual. Ver
'analisis_financiero.py' para el original de cada fórmula -- si esa lógica
cambia, esta debe actualizarse en espejo.
"""

import math
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ_REPORTES = Path(__file__).resolve().parent
RAIZ_SISTEMA = RAIZ_REPORTES.parent / "Sistema"
if str(RAIZ_SISTEMA) not in sys.path:
    sys.path.insert(0, str(RAIZ_SISTEMA))

from analisis_financiero import (  # noqa: E402
    MARGEN_OBJETIVO_NOTA, PESO_DESVIACION_NOTA, PESO_RENTABILIDAD_NOTA,
)


def _dividir(a, b):
    """Mirror de una división de Excel: denominador None o 0 -> None (mismo
    significado que '#DIV/0!' -- nunca se inventa un 0 en su lugar)."""
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


def _redondear_excel(x: float) -> int:
    """Excel ROUND redondea 'half away from zero', NO 'half to even' como
    el round() nativo de Python (round(0.5)==0, round(2.5)==2). Los
    valores que redondeamos con esto (Nota del Proyecto) son siempre no
    negativos."""
    return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)


def _a_fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def costos_reales_por_proyecto(filas_detalle: list[dict]) -> dict[str, dict[str, float]]:
    """Agrupa filas de 'Detalle Costos Reales' (TAG proyecto/Bucket/Total
    sin IVA) por (tag, bucket), sumando -- mirror exacto de la fórmula
    SUMIFS de 'analisis_financiero.asegurar_formulas_proyectos'
    (analisis_financiero.py:656-660). Un bucket sin filas para ese tag no
    aparece en el dict resultante -- el llamador debe usar
    .get(bucket, 0.0), igual que SUMIFS sin coincidencias devuelve 0."""
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


def recalcular_proyecto(proyecto: dict, costos_reales: dict[str, float]) -> tuple[dict, dict]:
    """Recalcula las columnas derivadas de 'Proyectos' (mirror de
    'asegurar_formulas_proyectos', analisis_financiero.py:640-681) y la fila
    de 'Indicadores' (mirror de 'asegurar_hoja_indicadores',
    analisis_financiero.py:717-759) para un proyecto. No muta ninguno de
    los dos argumentos. costos_reales: dict con claves
    'Materiales'/'Equipos'/'Otros' -> total (buckets ausentes se tratan
    como 0.0, igual que SUMIFS sin coincidencias)."""
    venta = proyecto.get("Monto de Venta (sin IVA)")
    mat_p = proyecto.get("Costos Materiales Proyectados")
    eq_p = proyecto.get("Costos Equipos Proyectados")
    mo_p = proyecto.get("Mano de Obra Proyectada")
    otros_p = proyecto.get("Otros Costos Proyectados")
    mat_r = costos_reales.get("Materiales", 0.0)
    eq_r = costos_reales.get("Equipos", 0.0)
    otros_r = costos_reales.get("Otros", 0.0)
    mo_r = proyecto.get("Mano de Obra Real")

    total_proyectado = _sumar(mat_p, eq_p, mo_p, otros_p)
    total_real = _sumar(mat_r, eq_r, otros_r, mo_r)
    margen_proyectado = _restar(venta, total_proyectado)
    margen_real = _restar(venta, total_real)
    desviacion_total = _dividir(total_real, total_proyectado)
    if desviacion_total is not None:
        desviacion_total -= 1

    proyecto_actualizado = dict(proyecto)
    proyecto_actualizado.update({
        "Costos Materiales Reales": mat_r,
        "Costos Equipos Reales": eq_r,
        "Otros Costos Reales": otros_r,
        "Total Proyectado": total_proyectado,
        "Total Real": total_real,
        "Margen Proyectado": margen_proyectado,
        "Margen Real": margen_real,
        "Desviación % (Real vs Proyectado)": desviacion_total,
    })

    margen_neto = _dividir(margen_real, venta)
    rentabilidad_costo = _dividir(margen_real, total_real)

    def _desviacion_bucket(real, proyectado):
        d = _dividir(real, proyectado)
        return None if d is None else d - 1

    nota = None
    evaluacion = None
    if margen_neto is not None and desviacion_total is not None:
        score_margen = min(100, max(0, (margen_neto / MARGEN_OBJETIVO_NOTA) * 100))
        score_desviacion = min(100, max(0, 100 - abs(desviacion_total) * 100))
        nota = _redondear_excel(
            PESO_RENTABILIDAD_NOTA * score_margen + PESO_DESVIACION_NOTA * score_desviacion
        )
        evaluacion = (
            "Excelente" if nota >= 85 else
            "Bueno" if nota >= 70 else
            "Aprobado" if nota >= 55 else
            "Requiere atención"
        )

    indicadores = {
        "Rentabilidad sobre costo": rentabilidad_costo,
        "Margen neto %": margen_neto,
        "Productividad Materiales": _dividir(venta, mat_r),
        "Productividad Equipos": _dividir(venta, eq_r),
        "Productividad MO": _dividir(venta, mo_r),
        "Productividad Otros": _dividir(venta, otros_r),
        "Costo Materiales % de venta": _dividir(mat_r, venta),
        "Costo Equipos % de venta": _dividir(eq_r, venta),
        "Costo MO % de venta": _dividir(mo_r, venta),
        "Costo Otros % de venta": _dividir(otros_r, venta),
        "Desviación % Materiales": _desviacion_bucket(mat_r, mat_p),
        "Desviación % Equipos": _desviacion_bucket(eq_r, eq_p),
        "Desviación % MO": _desviacion_bucket(mo_r, mo_p),
        "Desviación % Otros": _desviacion_bucket(otros_r, otros_p),
        "Nota del Proyecto": nota,
        "Evaluación": evaluacion,
    }
    return proyecto_actualizado, indicadores


def _percentil_excel(ordenados: list[float], p: float) -> float:
    """PERCENTILE.INC de Excel: interpolación lineal, rank = p*(n-1)
    (0-indexado)."""
    n = len(ordenados)
    if n == 1:
        return ordenados[0]
    rank = p * (n - 1)
    inferior = int(rank)
    fraccion = rank - inferior
    if inferior + 1 >= n:
        return ordenados[inferior]
    return ordenados[inferior] + fraccion * (ordenados[inferior + 1] - ordenados[inferior])


def calcular_cltv_clientes(proyectos_completos: list[dict]) -> dict[str, dict]:
    """Recalcula la hoja 'Clientes' completa (mirror de
    'asegurar_hoja_clientes', analisis_financiero.py:764-810) a partir de
    la lista de proyectos YA recalculados (con 'Margen Real' recién
    calculado, no leído de Excel). Debe recibir TODOS los proyectos
    completos del libro a la vez -- la Clasificación de cada cliente
    depende del percentil de CLTV entre TODOS los clientes, igual que la
    fórmula Excel referencia 'Clientes!$G:$G' completa."""
    por_cliente: dict[str, list[dict]] = {}
    for p in proyectos_completos:
        cliente = p.get("Cliente")
        if cliente:
            por_cliente.setdefault(cliente, []).append(p)

    resultados: dict[str, dict] = {}
    for cliente, proyectos in por_cliente.items():
        ventas = [p.get("Monto de Venta (sin IVA)") for p in proyectos]
        margenes = [p.get("Margen Real") for p in proyectos]
        fechas = [f for f in (_a_fecha(p.get("Fecha de inicio")) for p in proyectos) if f]

        total_ventas = _sumar(*ventas)
        total_margenes = _sumar(*margenes)
        aov = _dividir(total_ventas, len(ventas)) if ventas else None
        vida = len(proyectos)
        if fechas:
            rango_dias = (max(fechas) - min(fechas)).days
            meses_activo = max(1, rango_dias / 30)
        else:
            meses_activo = 1
        frecuencia = vida / (meses_activo / 12)
        margen_pct = _dividir(total_margenes, total_ventas)
        cltv = None if (aov is None or margen_pct is None) else aov * frecuencia * vida * margen_pct

        resultados[cliente] = {
            "Cliente": cliente,
            "AOV (Valor promedio de venta)": aov,
            "Vida del cliente (n° de proyectos)": vida,
            "Meses activo": meses_activo,
            "Frecuencia de compra (proyectos/año)": frecuencia,
            "Margen de utilidad %": margen_pct,
            "CLTV": cltv,
        }

    cltvs_validos = sorted(r["CLTV"] for r in resultados.values() if r["CLTV"] is not None)
    for r in resultados.values():
        if r["CLTV"] is None or not cltvs_validos:
            r["Clasificación"] = None
            continue
        p67 = _percentil_excel(cltvs_validos, 0.67)
        p33 = _percentil_excel(cltvs_validos, 0.33)
        if r["CLTV"] >= p67:
            r["Clasificación"] = "Clientes estratégicos"
        elif r["CLTV"] >= p33:
            r["Clasificación"] = "Clientes potenciales"
        else:
            r["Clasificación"] = "Clientes de oportunidad"
    return resultados
