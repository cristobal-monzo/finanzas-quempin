import analisis_financiero as af


def test_una_fila_referencia_las_columnas_correctas_de_proyectos(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    filas_validas = [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}]

    af.asegurar_hoja_indicadores(wb, filas_validas)

    ws = wb[af.HOJA_INDICADORES]
    assert ws.cell(row=2, column=1).value == "=Proyectos!A2"
    assert ws.cell(row=2, column=2).value == "=Proyectos!B2"
    assert ws.cell(row=2, column=3).value == "=Proyectos!R2/Proyectos!P2"
    assert ws.cell(row=2, column=4).value == "=Proyectos!R2/Proyectos!F2"
    assert ws.cell(row=2, column=5).value == "=Proyectos!F2/Proyectos!K2"
    assert ws.cell(row=2, column=6).value == "=Proyectos!F2/Proyectos!L2"
    assert ws.cell(row=2, column=7).value == "=Proyectos!F2/Proyectos!N2"
    assert ws.cell(row=2, column=8).value == "=Proyectos!F2/Proyectos!M2"
    assert ws.cell(row=2, column=9).value == "=Proyectos!K2/Proyectos!F2"
    assert ws.cell(row=2, column=10).value == "=Proyectos!L2/Proyectos!F2"
    assert ws.cell(row=2, column=11).value == "=Proyectos!N2/Proyectos!F2"
    assert ws.cell(row=2, column=12).value == "=Proyectos!M2/Proyectos!F2"
    assert ws.cell(row=2, column=13).value == "=Proyectos!K2/Proyectos!G2-1"
    assert ws.cell(row=2, column=14).value == "=Proyectos!L2/Proyectos!H2-1"
    assert ws.cell(row=2, column=15).value == "=Proyectos!N2/Proyectos!I2-1"
    assert ws.cell(row=2, column=16).value == "=Proyectos!M2/Proyectos!J2-1"


def test_fila_con_hueco_en_proyectos_queda_compacta_en_indicadores_pero_referencia_la_fila_real(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    # Proyectos fila 3 fue invalida y se salto -- el segundo proyecto valido
    # esta en la fila 4 de "Proyectos".
    filas_validas = [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 4, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ]

    af.asegurar_hoja_indicadores(wb, filas_validas)

    ws = wb[af.HOJA_INDICADORES]
    assert ws.cell(row=2, column=1).value == "=Proyectos!A2"
    assert ws.cell(row=3, column=1).value == "=Proyectos!A4"
    assert ws.cell(row=3, column=3).value == "=Proyectos!R4/Proyectos!P4"


def test_regenerar_borra_filas_de_la_corrida_anterior(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "CFLI", "nombre": "Cesfam Limache"}])

    ws = wb[af.HOJA_INDICADORES]
    assert ws.max_row == 2
