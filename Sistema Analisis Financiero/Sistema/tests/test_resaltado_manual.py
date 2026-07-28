import analisis_financiero as af


def test_columna_manual_tiene_relleno_amarillo_y_cursiva(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_resaltado_celdas_manuales(wb)

    ws = wb[af.HOJA_PROYECTOS]
    celda = ws["G2"]  # "Monto de Venta (sin IVA)"
    assert celda.fill.fgColor.rgb == "00" + af.COLOR_RESALTADO_MANUAL
    assert celda.font.italic is True


def test_columnas_formula_y_autocompletadas_no_se_resaltan(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_resaltado_celdas_manuales(wb)

    ws = wb[af.HOJA_PROYECTOS]
    l = af.LETRA_COL_PROYECTOS
    for nombre in ("Cliente", "Categoría", "Costos Materiales Reales", "Total Proyectado"):
        celda = ws[f"{l[nombre]}2"]
        assert celda.fill.fill_type is None


def test_resalta_filas_minimas_aunque_no_haya_proyectos_cargados(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_resaltado_celdas_manuales(wb)

    ws = wb[af.HOJA_PROYECTOS]
    celda = ws[f"G{af.FILAS_MINIMAS_RESALTADO_MANUAL}"]
    assert celda.fill.fgColor.rgb == "00" + af.COLOR_RESALTADO_MANUAL


def test_extiende_buffer_mas_alla_de_la_ultima_fila_con_datos(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    fila_con_dato = af.FILAS_MINIMAS_RESALTADO_MANUAL + 30
    ws.cell(row=fila_con_dato, column=1, value="TEST")

    af.aplicar_resaltado_celdas_manuales(wb)

    fila_dentro_del_buffer = fila_con_dato + af.BUFFER_FILAS_RESALTADO_MANUAL
    fila_fuera_del_buffer = fila_dentro_del_buffer + 5
    assert ws[f"G{fila_dentro_del_buffer}"].fill.fgColor.rgb == "00" + af.COLOR_RESALTADO_MANUAL
    assert ws[f"G{fila_fuera_del_buffer}"].fill.fill_type is None


def test_no_crece_sin_limite_al_correr_varias_veces_sin_datos_nuevos(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_resaltado_celdas_manuales(wb)
    af.aplicar_resaltado_celdas_manuales(wb)
    af.aplicar_resaltado_celdas_manuales(wb)

    ws = wb[af.HOJA_PROYECTOS]
    fila_fuera_de_rango = af.FILAS_MINIMAS_RESALTADO_MANUAL + 5
    assert ws[f"G{fila_fuera_de_rango}"].fill.fill_type is None


def test_leyenda_se_escribe_despues_de_la_ultima_columna(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.aplicar_resaltado_celdas_manuales(wb)

    ws = wb[af.HOJA_PROYECTOS]
    col_leyenda = len(af.HEADERS_PROYECTOS) + 1
    celda = ws.cell(row=1, column=col_leyenda)
    assert "ingreso manual" in celda.value.lower()
