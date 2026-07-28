import pytest

import analisis_financiero as af


def test_regenerar_escribe_una_fila_por_clave_con_bucket_calculado(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    agrupado = {
        ("UMAG", "Materiales"): 70000.0,
        ("UMAG", "Equipos-Herramientas"): 90000.0,
        ("CFLI", "Combustible"): 45000.0,
    }

    avisos = af.regenerar_hoja_detalle_costos_reales(wb, agrupado)

    ws = wb[af.HOJA_DETALLE_COSTOS_REALES]
    filas = [
        (ws.cell(row=r, column=1).value, ws.cell(row=r, column=2).value,
         ws.cell(row=r, column=3).value, ws.cell(row=r, column=4).value)
        for r in range(2, ws.max_row + 1)
    ]
    assert ("UMAG", "Materiales", "Materiales", 70000.0) in filas
    assert ("UMAG", "Equipos-Herramientas", "Equipos", 90000.0) in filas
    assert ("CFLI", "Combustible", "Otros", 45000.0) in filas
    assert len(filas) == 3
    assert len(avisos) == 1
    assert "Combustible" in avisos[0]


def test_regenerar_borra_filas_de_la_corrida_anterior(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.regenerar_hoja_detalle_costos_reales(wb, {("UMAG", "Materiales"): 1000.0})
    af.regenerar_hoja_detalle_costos_reales(wb, {("CFLI", "Materiales"): 2000.0})

    ws = wb[af.HOJA_DETALLE_COSTOS_REALES]
    filas = [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]
    assert filas == ["CFLI"]


def test_regenerar_con_agrupado_vacio_deja_solo_el_encabezado(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.regenerar_hoja_detalle_costos_reales(wb, {})
    ws = wb[af.HOJA_DETALLE_COSTOS_REALES]
    assert ws.max_row == 1


def test_columna_porcentaje_es_relativa_a_la_suma_del_mismo_proyecto_en_esta_hoja(tmp_path):
    """% del Total Real del proyecto = Total sin IVA de la fila / suma de
    TODAS las filas de ese proyecto en esta misma hoja -- no el Total Real
    de 'Proyectos' (que además incluye Mano de Obra Real manual, sin
    detalle por subcategoría acá). Debe sumar ~100% por proyecto."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    agrupado = {
        ("UMAG", "Materiales"): 1116967.0,
        ("UMAG", "Equipos-Herramientas"): 503741.0,
        ("UMAG", "Consumibles"): 9000.0,
        ("UMAG", "Combustible"): 21292.0,
        ("UMAG", "Servicios"): 2352941.0,
        ("UMAG", "Transporte"): 468738.0,
        ("CFLI", "Equipos-Herramientas"): 18479.0,
    }

    af.regenerar_hoja_detalle_costos_reales(wb, agrupado)

    ws = wb[af.HOJA_DETALLE_COSTOS_REALES]
    filas_umag = [
        (ws.cell(row=r, column=2).value, ws.cell(row=r, column=4).value, ws.cell(row=r, column=5).value)
        for r in range(2, ws.max_row + 1)
        if ws.cell(row=r, column=1).value == "UMAG"
    ]
    total_umag = sum(total for _, total, _ in filas_umag)
    assert total_umag == pytest.approx(4472679.0)
    for subcategoria, total, porcentaje in filas_umag:
        assert porcentaje == pytest.approx(total / total_umag)
    assert sum(porcentaje for _, _, porcentaje in filas_umag) == pytest.approx(1.0)

    # Un único proyecto en la hoja (CFLI) queda en 100% -- caso trivial.
    fila_cfli = [
        ws.cell(row=r, column=5).value for r in range(2, ws.max_row + 1)
        if ws.cell(row=r, column=1).value == "CFLI"
    ]
    assert fila_cfli == [1.0]
