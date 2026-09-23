"""
Análisis de cartera (fase 2 de la auditoría 2026-09-21): los números que no
son de un proyecto sino del conjunto -- en qué se equivoca sistemáticamente
el presupuesto y de cuántos clientes depende el ingreso -- más el error de
presupuesto por proyecto, que sí tiene columna en "Indicadores".
"""

import pytest

import analisis_financiero as af


def _kpis(avance, proy, real, completo="Sí"):
    """Sale de calcular_kpis_proyecto, no de un dict a mano: un fixture
    armado a mano puede tener claves que la salida real no trae, y el
    sesgo por categoría falló justamente así contra los datos reales
    (2026-09-21) con la suite en verde."""
    valores = {
        "% Avance": avance, "Monto de Venta (sin IVA)": 1_000_000 if completo == "Sí" else None,
        "Costos Materiales Proyectados": proy[0], "Costos Equipos Proyectados": proy[1],
        "Mano de Obra Proyectada": proy[2], "Otros Costos Proyectados": proy[3],
        "Mano de Obra Real": real[2],
    }
    k = af.calcular_kpis_proyecto(
        valores, {"Materiales": real[0], "Equipos": real[1], "Otros": real[3]}
    )
    assert k["Datos completos"] == completo, "el caso no quedó como se esperaba"
    return k


# ── Error del presupuesto por proyecto ──────────────────────────────────────

def test_error_del_presupuesto_ve_lo_que_la_desviacion_total_esconde():
    """Caso real de la auditoría: el total calzó (-1%) porque materiales muy
    por sobre lo previsto se compensó con equipos muy por debajo."""
    k = af.calcular_kpis_proyecto(
        {
            "% Avance": 1.0, "Monto de Venta (sin IVA)": 160.0,
            "Costos Materiales Proyectados": 20.0, "Costos Equipos Proyectados": 40.0,
            "Mano de Obra Proyectada": 30.0, "Otros Costos Proyectados": 10.0,
            "Mano de Obra Real": 30.0,
        },
        {"Materiales": 60.0, "Equipos": 0.0, "Otros": 10.0},
    )
    assert k["Desviación % Total"] == 0.0  # el total calza exacto
    # |60-20| + |0-40| + |30-30| + |10-10| = 80 sobre 100 de presupuesto
    assert k["Error del presupuesto %"] == pytest.approx(0.8)


def test_error_del_presupuesto_es_cero_con_el_presupuesto_clavado():
    k = af.calcular_kpis_proyecto(
        {
            "% Avance": 1.0, "Monto de Venta (sin IVA)": 160.0,
            "Costos Materiales Proyectados": 20.0, "Costos Equipos Proyectados": 40.0,
            "Mano de Obra Proyectada": 30.0, "Otros Costos Proyectados": 10.0,
            "Mano de Obra Real": 30.0,
        },
        {"Materiales": 20.0, "Equipos": 40.0, "Otros": 10.0},
    )
    assert k["Error del presupuesto %"] == 0.0


def test_error_del_presupuesto_vacio_sin_presupuesto():
    assert af.error_presupuesto({"a": 10.0}, {"a": 0.0}, 0) is None
    assert af.error_presupuesto({"a": None}, {"a": 10.0}, 100) is None


# ── Sesgo por categoría en toda la cartera ─────────────────────────────────

def test_sesgo_por_categoria_agrega_toda_la_cartera_terminada():
    filas = af.sesgo_por_categoria([
        _kpis(1.0, (100.0, 100.0, 100.0, 100.0), (120.0, 80.0, 100.0, 90.0)),
        _kpis(1.0, (100.0, 100.0, 100.0, 100.0), (140.0, 60.0, 100.0, 110.0)),
    ])
    por_categoria = {f["categoria"]: f for f in filas}
    assert por_categoria["Materiales"]["sesgo"] == pytest.approx(0.3)  # 260/200 - 1
    assert por_categoria["Equipos"]["sesgo"] == pytest.approx(-0.3)
    assert por_categoria["Mano de Obra"]["sesgo"] == 0.0
    assert por_categoria["Materiales"]["n_proyectos"] == 2


def test_sesgo_por_categoria_ignora_proyectos_en_curso_e_incompletos():
    """Un proyecto a medio ejecutar todavía va a gastar más: contarlo haría
    ver un sesgo a la baja que no existe."""
    filas = af.sesgo_por_categoria([
        _kpis(1.0, (100.0, 100.0, 100.0, 100.0), (120.0, 100.0, 100.0, 100.0)),
        _kpis(0.5, (100.0, 100.0, 100.0, 100.0), (10.0, 10.0, 10.0, 10.0)),
        _kpis(1.0, (100.0, 100.0, 100.0, 100.0), (10.0, 10.0, 10.0, 10.0), completo="No"),
    ])
    por_categoria = {f["categoria"]: f for f in filas}
    assert por_categoria["Materiales"]["n_proyectos"] == 1
    assert por_categoria["Materiales"]["sesgo"] == pytest.approx(0.2)


def test_sesgo_por_categoria_sin_proyectos_terminados_no_explota():
    filas = af.sesgo_por_categoria([_kpis(0.5, (100.0,) * 4, (10.0,) * 4)])
    assert all(f["sesgo"] is None and f["n_proyectos"] == 0 for f in filas)


# ── Concentración del ingreso por cliente ──────────────────────────────────

def test_concentracion_mide_de_cuantos_clientes_depende_el_ingreso():
    c = af.concentracion_cartera({"A": 100.0, "B": 60.0, "C": 40.0})
    assert c["top_1"] == 0.5
    assert c["top_3"] == 1.0
    assert c["hhi"] == 0.5 ** 2 + 0.3 ** 2 + 0.2 ** 2
    assert round(c["clientes_equivalentes"], 2) == 2.63  # menos que los 3 reales
    assert [r["cliente"] for r in c["ranking"]] == ["A", "B", "C"]
    assert c["ranking"][-1]["acumulado"] == 1.0


def test_concentracion_con_un_solo_cliente_es_dependencia_total():
    c = af.concentracion_cartera({"Único": 500.0})
    assert c["top_1"] == 1.0
    assert c["hhi"] == 1.0
    assert c["clientes_equivalentes"] == 1.0


def test_concentracion_ignora_clientes_sin_venta_y_no_explota_vacia():
    c = af.concentracion_cartera({"A": 100.0, "B": None, "C": 0})
    assert c["n_clientes"] == 1
    vacia = af.concentracion_cartera({})
    assert vacia["total"] == 0 and vacia["hhi"] is None and vacia["ranking"] == []
