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
