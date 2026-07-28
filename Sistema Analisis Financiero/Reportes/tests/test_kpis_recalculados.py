# -*- coding: utf-8 -*-
from datetime import date

import pytest

import kpis_recalculados as kr


def test_redondear_excel_difiere_de_round_nativo_en_mitades():
    assert kr._redondear_excel(0.5) == 1
    assert kr._redondear_excel(2.5) == 3
    assert round(0.5) == 0 and round(2.5) == 2  # confirma que round() nativo SI redondea distinto


def test_percentil_excel_interpolacion_lineal():
    ordenados = [10, 20, 30, 40, 50]
    assert kr._percentil_excel(ordenados, 0.5) == 30
    assert kr._percentil_excel(ordenados, 0.25) == 20
    assert kr._percentil_excel(ordenados, 0.1) == pytest.approx(14)


def test_costos_reales_por_proyecto_agrupa_por_tag_y_bucket():
    filas = [
        {"TAG proyecto": "UMAG", "Subcategoría": "Consumibles", "Bucket": "Materiales", "Total sin IVA": 60000},
        {"TAG proyecto": "UMAG", "Subcategoría": "Ferretería", "Bucket": "Materiales", "Total sin IVA": 5000},
        {"TAG proyecto": "UMAG", "Subcategoría": "Equipos-Herramientas", "Bucket": "Equipos", "Total sin IVA": 70000},
        {"TAG proyecto": "CFLI", "Subcategoría": "Consumibles", "Bucket": "Materiales", "Total sin IVA": 1000},
    ]
    resultado = kr.costos_reales_por_proyecto(filas)
    assert resultado["UMAG"]["Materiales"] == 65000
    assert resultado["UMAG"]["Equipos"] == 70000
    assert resultado["CFLI"]["Materiales"] == 1000
    assert "Otros" not in resultado["UMAG"]


def test_recalcular_proyecto_kpis_felices():
    proyecto = {
        "Monto de Venta (sin IVA)": 1000000,
        "Costos Materiales Proyectados": 100000, "Costos Equipos Proyectados": 100000,
        "Mano de Obra Proyectada": 100000, "Otros Costos Proyectados": 100000,
        "Mano de Obra Real": 90000,
    }
    costos_reales = {"Materiales": 60000, "Equipos": 70000, "Otros": 20000}
    proyecto_actualizado, indicadores = kr.recalcular_proyecto(proyecto, costos_reales)

    assert proyecto_actualizado["Total Real"] == 240000
    assert proyecto_actualizado["Margen Real"] == 760000
    assert proyecto_actualizado["Margen Proyectado"] == 600000
    assert proyecto_actualizado["Desviación % (Real vs Proyectado)"] == pytest.approx(-0.4)
    assert indicadores["Margen neto %"] == pytest.approx(0.76)
    assert "Rentabilidad sobre costo" not in indicadores  # eliminado del playbook 2026-07-28
    # Desviación total = -0.4 (Real < Proyectado, el proyecto ahorró) -> con
    # el fix de la Nota (sin ABS) el componente de desviación da el puntaje
    # máximo (100), no se penaliza. Nota = round(0.7*100 + 0.3*100) = 100.
    assert indicadores["Nota del Proyecto"] == 100
    assert indicadores["Evaluación"] == "Excelente"
    assert "Total Real" not in proyecto  # no muta el argumento original

    # 4 KPIs nuevos del playbook 2026-07-28
    assert indicadores["Desviación % Total"] == pytest.approx(-0.4)
    assert indicadores["Estructura % Materiales"] == pytest.approx(60000 / 240000)
    assert indicadores["Estructura % Equipos"] == pytest.approx(70000 / 240000)
    assert indicadores["Estructura % MO"] == pytest.approx(90000 / 240000)
    assert indicadores["Estructura % Otros"] == pytest.approx(20000 / 240000)
    assert sum(
        indicadores[f"Estructura % {c}"] for c in ("Materiales", "Equipos", "MO", "Otros")
    ) == pytest.approx(1.0)
    assert indicadores["Ahorro/Sobrecosto Materiales"] == pytest.approx(40000)
    assert indicadores["Ahorro/Sobrecosto Equipos"] == pytest.approx(30000)
    assert indicadores["Ahorro/Sobrecosto MO"] == pytest.approx(10000)
    assert indicadores["Ahorro/Sobrecosto Otros"] == pytest.approx(80000)
    assert indicadores["Ahorro/Sobrecosto Total"] == pytest.approx(160000)


def test_recalcular_proyecto_nota_penaliza_sobrecosto_real():
    """Caso espejo del anterior pero con sobrecosto real (Real > Proyectado)
    -- el componente de desviación SÍ debe restar puntos."""
    proyecto = {
        "Monto de Venta (sin IVA)": 1000000,
        "Costos Materiales Proyectados": 100000, "Costos Equipos Proyectados": 100000,
        "Mano de Obra Proyectada": 100000, "Otros Costos Proyectados": 100000,
        "Mano de Obra Real": 90000,
    }
    # Total real = 60000+70000+90000+140000 = 360000 vs proyectado 400000+
    # ... usamos Otros mucho más alto para forzar Real > Proyectado.
    costos_reales = {"Materiales": 200000, "Equipos": 200000, "Otros": 200000}
    _, indicadores = kr.recalcular_proyecto(proyecto, costos_reales)

    # Total real = 200000+200000+200000+90000 = 690000; proyectado = 400000
    # desviacion_total = 690000/400000 - 1 = 0.725 (sobrecosto)
    assert indicadores["Desviación % Total"] == pytest.approx(0.725)
    assert indicadores["Ahorro/Sobrecosto Total"] == pytest.approx(400000 - 690000)
    # score_desviacion = max(0, 100 - 0.725*100) = 27.5 (sí penaliza)
    margen_neto = (1000000 - 690000) / 1000000
    score_margen = min(100, max(0, (margen_neto / 0.25) * 100))
    score_desviacion = min(100, max(0, 100 - max(0, 0.725) * 100))
    nota_esperada = round(0.7 * score_margen + 0.3 * score_desviacion)
    assert indicadores["Nota del Proyecto"] == nota_esperada
    assert indicadores["Ahorro/Sobrecosto Total"] < 0  # confirma que es sobrecosto, no ahorro


def test_recalcular_proyecto_division_por_cero_da_none_no_inventa_numero():
    proyecto = {
        "Monto de Venta (sin IVA)": 1000000,
        "Costos Materiales Proyectados": 0, "Costos Equipos Proyectados": 100000,
        "Mano de Obra Proyectada": 100000, "Otros Costos Proyectados": 100000,
        "Mano de Obra Real": 90000,
    }
    costos_reales = {"Materiales": 60000, "Equipos": 70000, "Otros": 20000}
    _, indicadores = kr.recalcular_proyecto(proyecto, costos_reales)
    assert indicadores["Desviación % Materiales"] is None


def test_recalcular_proyecto_costo_real_faltante_por_bucket_se_trata_como_cero():
    proyecto = {
        "Monto de Venta (sin IVA)": 1000000,
        "Costos Materiales Proyectados": 100000, "Costos Equipos Proyectados": 100000,
        "Mano de Obra Proyectada": 100000, "Otros Costos Proyectados": 100000,
        "Mano de Obra Real": 90000,
    }
    proyecto_actualizado, _ = kr.recalcular_proyecto(proyecto, {})
    assert proyecto_actualizado["Costos Materiales Reales"] == 0.0
    assert proyecto_actualizado["Total Real"] == 90000


def test_calcular_cltv_clientes_clasifica_por_percentil():
    proyectos = [
        {"Cliente": "A", "Monto de Venta (sin IVA)": 100000, "Margen Real": 50000, "Fecha de inicio": date(2026, 1, 1)},
        {"Cliente": "B", "Monto de Venta (sin IVA)": 200000, "Margen Real": 100000, "Fecha de inicio": date(2026, 1, 1)},
        {"Cliente": "C", "Monto de Venta (sin IVA)": 300000, "Margen Real": 150000, "Fecha de inicio": date(2026, 1, 1)},
    ]
    resultado = kr.calcular_cltv_clientes(proyectos)
    assert resultado["A"]["CLTV"] == pytest.approx(600000)
    assert resultado["B"]["CLTV"] == pytest.approx(1200000)
    assert resultado["C"]["CLTV"] == pytest.approx(1800000)
    assert resultado["A"]["Clasificación"] == "Clientes de oportunidad"
    assert resultado["B"]["Clasificación"] == "Clientes potenciales"
    assert resultado["C"]["Clasificación"] == "Clientes estratégicos"
