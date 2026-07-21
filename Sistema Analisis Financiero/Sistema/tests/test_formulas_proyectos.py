import analisis_financiero as af


def test_asegura_formulas_sumifs_y_derivadas_en_la_fila_del_proyecto(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="UMAG")
    ws.cell(row=2, column=2, value="UMAG")
    filas_validas = [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}]

    af.asegurar_formulas_proyectos(ws, filas_validas)

    assert ws.cell(row=2, column=11).value == (
        "=SUMIFS('Detalle Costos Reales'!$D:$D,"
        "'Detalle Costos Reales'!$A:$A,$A2,"
        "'Detalle Costos Reales'!$C:$C,\"Materiales\")"
    )
    assert ws.cell(row=2, column=12).value == (
        "=SUMIFS('Detalle Costos Reales'!$D:$D,"
        "'Detalle Costos Reales'!$A:$A,$A2,"
        "'Detalle Costos Reales'!$C:$C,\"Equipos\")"
    )
    assert ws.cell(row=2, column=13).value == (
        "=SUMIFS('Detalle Costos Reales'!$D:$D,"
        "'Detalle Costos Reales'!$A:$A,$A2,"
        "'Detalle Costos Reales'!$C:$C,\"Otros\")"
    )
    assert ws.cell(row=2, column=15).value == "=G2+H2+I2+J2"
    assert ws.cell(row=2, column=16).value == "=K2+L2+M2+N2"
    assert ws.cell(row=2, column=17).value == "=F2-O2"
    assert ws.cell(row=2, column=18).value == "=F2-P2"
    assert ws.cell(row=2, column=19).value == "=P2/O2-1"


def test_no_toca_columnas_manuales(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="UMAG")
    ws.cell(row=2, column=2, value="UMAG")
    ws.cell(row=2, column=6, value=1000000)  # Monto de Venta, manual
    filas_validas = [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}]

    af.asegurar_formulas_proyectos(ws, filas_validas)

    assert ws.cell(row=2, column=6).value == 1000000
