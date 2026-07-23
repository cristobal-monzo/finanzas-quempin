import analisis_financiero as af


def test_formula_nota_referencia_margen_y_desviacion_total(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])

    ws = wb[af.HOJA_INDICADORES]
    formula_nota = ws.cell(row=2, column=17).value
    assert formula_nota == (
        "=ROUND(0.7*MIN(100,MAX(0,(Proyectos!R2/Proyectos!F2)/0.25*100))"
        "+0.3*MIN(100,MAX(0,100-ABS(Proyectos!S2)*100)),0)"
    )


def test_formula_evaluacion_referencia_la_nota_de_la_misma_fila(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 4, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ])

    ws = wb[af.HOJA_INDICADORES]
    # segunda fila válida queda compacta en la fila 3 de "Indicadores" pero
    # su Nota (columna Q) también está en la fila 3, no en la 4.
    assert ws.cell(row=3, column=18).value == (
        '=IF(Q3>=85,"Excelente",IF(Q3>=70,"Bueno",'
        'IF(Q3>=55,"Aprobado","Requiere atención")))'
    )


def test_constantes_de_calibracion_de_la_nota():
    assert af.MARGEN_OBJETIVO_NOTA == 0.25
    assert af.PESO_RENTABILIDAD_NOTA == 0.7
    assert af.PESO_DESVIACION_NOTA == 0.3
