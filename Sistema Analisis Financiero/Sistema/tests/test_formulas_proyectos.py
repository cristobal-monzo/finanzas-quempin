import analisis_financiero as af


def _col(nombre):
    return af.HEADERS_PROYECTOS.index(nombre) + 1


def test_asegura_formulas_sumifs_y_derivadas_en_la_fila_del_proyecto(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="UMAG")
    ws.cell(row=2, column=2, value="UMAG")
    filas_validas = [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}]

    af.asegurar_formulas_proyectos(ws, filas_validas)

    l = af.LETRA_COL_PROYECTOS
    assert ws.cell(row=2, column=_col("Costos Materiales Reales")).value == (
        "=SUMIFS('Detalle Costos Reales'!$D:$D,"
        "'Detalle Costos Reales'!$A:$A,$A2,"
        "'Detalle Costos Reales'!$C:$C,\"Materiales\")"
    )
    assert ws.cell(row=2, column=_col("Costos Equipos Reales")).value == (
        "=SUMIFS('Detalle Costos Reales'!$D:$D,"
        "'Detalle Costos Reales'!$A:$A,$A2,"
        "'Detalle Costos Reales'!$C:$C,\"Equipos\")"
    )
    assert ws.cell(row=2, column=_col("Otros Costos Reales")).value == (
        "=SUMIFS('Detalle Costos Reales'!$D:$D,"
        "'Detalle Costos Reales'!$A:$A,$A2,"
        "'Detalle Costos Reales'!$C:$C,\"Otros\")"
    )
    h, i, j, k = (l[n] for n in (
        "Costos Materiales Proyectados", "Costos Equipos Proyectados",
        "Mano de Obra Proyectada", "Otros Costos Proyectados",
    ))
    mat_r, eq_r, otros_r, mo_r = (l[n] for n in (
        "Costos Materiales Reales", "Costos Equipos Reales",
        "Otros Costos Reales", "Mano de Obra Real",
    ))
    venta, total_proy, total_real = (
        l["Monto de Venta (sin IVA)"], l["Total Proyectado"], l["Total Real"],
    )
    assert ws.cell(row=2, column=_col("Total Proyectado")).value == f"={h}2+{i}2+{j}2+{k}2"
    assert ws.cell(row=2, column=_col("Total Real")).value == f"={mat_r}2+{eq_r}2+{otros_r}2+{mo_r}2"
    assert ws.cell(row=2, column=_col("Margen Proyectado")).value == f"={venta}2-{total_proy}2"
    assert ws.cell(row=2, column=_col("Margen Real")).value == f"={venta}2-{total_real}2"
    assert ws.cell(row=2, column=_col("Desviación % (Real vs Proyectado)")).value == (
        f"={total_real}2/{total_proy}2-1"
    )


def test_no_toca_columnas_manuales(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    ws.cell(row=2, column=1, value="UMAG")
    ws.cell(row=2, column=2, value="UMAG")
    col_venta = _col("Monto de Venta (sin IVA)")
    ws.cell(row=2, column=col_venta, value=1000000)  # Monto de Venta, manual
    filas_validas = [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}]

    af.asegurar_formulas_proyectos(ws, filas_validas)

    assert ws.cell(row=2, column=col_venta).value == 1000000
