import analisis_financiero as af


def test_columna_cliente_de_proyectos_tiene_estilo(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_estilo_visual(wb)

    ws = wb[af.HOJA_PROYECTOS]
    assert ws["T1"].fill.fgColor.theme == af.COLOR_IDENTIFICACION.theme


def test_columnas_nota_y_evaluacion_de_indicadores_tienen_estilo(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_estilo_visual(wb)

    ws = wb[af.HOJA_INDICADORES]
    assert ws.column_dimensions["Q"].number_format == af.FORMATO_ENTERO
    assert ws["Q1"].fill.fgColor.theme == af.COLOR_DERIVADO.theme
    assert ws["R1"].fill.fgColor.theme == af.COLOR_DERIVADO.theme


def test_hoja_clientes_tiene_estilo_en_las_8_columnas(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_estilo_visual(wb)

    ws = wb[af.HOJA_CLIENTES]
    for columna in "ABCDEFGH":
        assert ws[f"{columna}1"].font.bold is True
    assert ws.column_dimensions["G"].number_format == af.FORMATO_MONEDA
    assert ws.column_dimensions["F"].number_format == af.FORMATO_PORCENTAJE


def test_hoja_glosario_kpis_tiene_encabezado_en_negrita(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_estilo_visual(wb)

    ws = wb[af.HOJA_GLOSARIO_KPIS]
    for columna in "ABCD":
        assert ws[f"{columna}1"].font.bold is True
    assert ws.column_dimensions["B"].width >= 40
