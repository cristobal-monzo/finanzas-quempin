import analisis_financiero as af


def test_formula_nota_referencia_margen_y_desviacion_total_sin_abs(tmp_path):
    """Corregido 2026-07-28: el componente de desviación ya no usa ABS() --
    MAX(0, desviación) anula el término para proyectos en o bajo presupuesto
    (solo penaliza sobrecosto real, Real > Proyectado)."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])

    ws = wb[af.HOJA_INDICADORES]
    l = af.LETRA_COL_PROYECTOS
    margen_real, venta = l["Margen Real"], l["Monto de Venta (sin IVA)"]
    desviacion_total = l["Desviación % (Real vs Proyectado)"]
    formula_nota = ws.cell(row=2, column=22).value
    assert formula_nota == (
        f"=ROUND(0.7*MIN(100,MAX(0,(Proyectos!{margen_real}2/Proyectos!{venta}2)/0.25*100))"
        f"+0.3*MIN(100,MAX(0,100-MAX(0,Proyectos!{desviacion_total}2)*100)),0)"
    )


def test_formula_evaluacion_referencia_la_nota_de_la_misma_fila(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 4, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ])

    ws = wb[af.HOJA_INDICADORES]
    # segunda fila válida queda compacta en la fila 3 de "Indicadores" pero
    # su Nota (columna V) también está en la fila 3, no en la 4.
    assert ws.cell(row=3, column=23).value == (
        '=IF(V3>=85,"Excelente",IF(V3>=70,"Bueno",'
        'IF(V3>=55,"Aprobado","Requiere atención")))'
    )


def test_constantes_de_calibracion_de_la_nota():
    assert af.MARGEN_OBJETIVO_NOTA == 0.25
    assert af.PESO_RENTABILIDAD_NOTA == 0.7
    assert af.PESO_DESVIACION_NOTA == 0.3


def test_nota_umag_sube_con_el_fix_porque_ahorro_ya_no_se_penaliza():
    """Verificación a mano contra el caso real de UMAG (2026-07-28): Venta
    14.563.245, Total Real 5.472.679, Total Proyectado 7.713.765 -> Margen
    Real 9.090.566, margen neto 62.42% (score tope 100), desviación total
    -29.05% (Real < Proyectado, ahorro). Con ABS() el score de desviación
    era 70.95 -> Nota=91. Sin ABS(), un proyecto que ahorra obtiene el
    puntaje máximo del componente (100) -> Nota=100."""
    import math

    venta, total_real, total_proy = 14563245, 5472679, 7713765
    margen_real = venta - total_real
    margen_neto = margen_real / venta
    desviacion = total_real / total_proy - 1

    def redondear_excel(x):
        return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)

    score_margen = min(100, max(0, (margen_neto / af.MARGEN_OBJETIVO_NOTA) * 100))

    score_desviacion_con_abs = min(100, max(0, 100 - abs(desviacion) * 100))
    nota_con_abs = redondear_excel(
        af.PESO_RENTABILIDAD_NOTA * score_margen + af.PESO_DESVIACION_NOTA * score_desviacion_con_abs
    )
    assert nota_con_abs == 91  # comportamiento previo, confirma el punto de partida

    score_desviacion_sin_abs = min(100, max(0, 100 - max(0, desviacion) * 100))
    nota_sin_abs = redondear_excel(
        af.PESO_RENTABILIDAD_NOTA * score_margen + af.PESO_DESVIACION_NOTA * score_desviacion_sin_abs
    )
    assert nota_sin_abs == 100
    assert nota_sin_abs > nota_con_abs
