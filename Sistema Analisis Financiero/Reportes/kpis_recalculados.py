# -*- coding: utf-8 -*-
"""
kpis_recalculados.py -- Recalcula en Python los KPIs derivados que
'analisis_financiero.py' escribe como fórmulas de Excel (Proyectos/
Indicadores/Clientes). openpyxl no cachea el resultado de una fórmula que
él mismo escribe -- solo el texto "=A1+B1" -- así que leerlas con
data_only=True devuelve None hasta que un humano abre el archivo en Excel/
LibreOffice y lo guarda. Este módulo replica exactamente esas mismas
fórmulas para que los reportes PDF nunca dependan de ese paso manual.

La Nota del Proyecto y la Evaluación NO se replican acá: se importan de
'analisis_financiero', que es su único dueño. El resto de las fórmulas
(divisiones, sumas, restas por categoría) sí se replican, pero son
aritmética directa sin reglas de negocio: si cambian en
'analisis_financiero.py', hay que actualizarlas acá en espejo.
"""

import sys
from datetime import date, datetime
from pathlib import Path

RAIZ_REPORTES = Path(__file__).resolve().parent
RAIZ_SISTEMA = RAIZ_REPORTES.parent / "Sistema"
if str(RAIZ_SISTEMA) not in sys.path:
    sys.path.insert(0, str(RAIZ_SISTEMA))

# La Nota/Evaluacion NO se recalculan aca: se importan de analisis_financiero,
# que es el unico dueño de esa regla (define a la vez la formula de Excel y su
# equivalente Python). Duplicarla fue el origen de una divergencia real -- ver
# la nota en analisis_financiero.py, seccion "NOTA / EVALUACION".
from analisis_financiero import (  # noqa: E402,F401
    # _redondear_excel se re-exporta aunque este modulo ya no lo llame
    # directamente: es parte de la superficie publica que sus tests ejercitan.
    _redondear_excel, calcular_nota, clasificar_evaluacion,
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

    def _desviacion_bucket(real, proyectado):
        d = _dividir(real, proyectado)
        return None if d is None else d - 1

    nota = calcular_nota(margen_neto, desviacion_total)
    evaluacion = clasificar_evaluacion(nota)

    # Playbook depurado 2026-07-28 (ver analisis_financiero.HEADERS_INDICADORES):
    # se eliminaron "Rentabilidad sobre costo" y las 4 "Productividad"
    # (redundancias matemáticas de "Margen neto %" y "Costo % de venta"). Se
    # agregaron: Estructura % del costo real (mix, sobre total_real), Desviación
    # % Total (mismo valor que Proyectos, expuesto acá también) y
    # Ahorro/Sobrecosto neto en $ (Proyectado - Real) por categoría y total.
    indicadores = {
        "Margen neto %": margen_neto,
        "Costo Materiales % de venta": _dividir(mat_r, venta),
        "Costo Equipos % de venta": _dividir(eq_r, venta),
        "Costo MO % de venta": _dividir(mo_r, venta),
        "Costo Otros % de venta": _dividir(otros_r, venta),
        "Estructura % Materiales": _dividir(mat_r, total_real),
        "Estructura % Equipos": _dividir(eq_r, total_real),
        "Estructura % MO": _dividir(mo_r, total_real),
        "Estructura % Otros": _dividir(otros_r, total_real),
        "Desviación % Materiales": _desviacion_bucket(mat_r, mat_p),
        "Desviación % Equipos": _desviacion_bucket(eq_r, eq_p),
        "Desviación % MO": _desviacion_bucket(mo_r, mo_p),
        "Desviación % Otros": _desviacion_bucket(otros_r, otros_p),
        "Desviación % Total": desviacion_total,
        "Ahorro/Sobrecosto Materiales": _restar(mat_p, mat_r),
        "Ahorro/Sobrecosto Equipos": _restar(eq_p, eq_r),
        "Ahorro/Sobrecosto MO": _restar(mo_p, mo_r),
        "Ahorro/Sobrecosto Otros": _restar(otros_p, otros_r),
        "Ahorro/Sobrecosto Total": _restar(total_proyectado, total_real),
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
