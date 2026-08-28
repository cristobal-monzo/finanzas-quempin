import analisis_financiero as af


def test_formula_nota_referencia_margen_y_desviacion_total_sin_abs(tmp_path):
    """Corregido 2026-07-28: el componente de desviación ya no usa ABS() --
    MAX(0, desviación) anula el término para proyectos en o bajo presupuesto
    (solo penaliza sobrecosto real, Real > Proyectado).

    Componente de margen corregido 2026-08-20: ya no es MIN(100,...) con
    tope duro en el objetivo -- ver test_score_margen_* más abajo para el
    porqué (efecto techo real detectado contra la cartera de QUEMPIN)."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])

    ws = wb[af.HOJA_INDICADORES]
    l = af.LETRA_COL_PROYECTOS
    margen_real, venta = l["Margen Real"], l["Monto de Venta (sin IVA)"]
    desviacion_total = l["Desviación % (Real vs Proyectado)"]
    formula_nota = ws.cell(row=2, column=22).value
    margen = f"(Proyectos!{margen_real}2/Proyectos!{venta}2)"
    es_gastos_generales = f'Proyectos!{l["Categoría"]}2="Gastos Generales"'
    assert formula_nota == (
        f'=IF({es_gastos_generales},"",'
        f"ROUND(0.7*IF({margen}<=0,0,IF({margen}<=0.25,{margen}/0.25*70,"
        f"70+30*(1-EXP(-({margen}-0.25)/0.3186))))"
        f"+0.3*MIN(100,MAX(0,100-MAX(0,Proyectos!{desviacion_total}2)*100)),0))"
    )


def test_score_margen_no_satura_en_el_objetivo():
    """2026-08-20: con la cartera real de QUEMPIN (15 proyectos, márgenes
    reales de 22%-99.8%), el tope duro en el objetivo (25%) dejaba 6 de 7
    proyectos completos empatados en Nota=100 -- ninguna capacidad de
    distinguir un proyecto al 40% de margen de uno al 99%. La curva nueva
    sigue subiendo (cada vez más despacio) por sobre el objetivo, sin techo
    fijo, en vez de aplanarse en 100 apenas se lo cruza."""
    assert af._score_margen_nota(af.MARGEN_OBJETIVO_NOTA) == af.SCORE_MARGEN_EN_OBJETIVO
    assert af._score_margen_nota(0.40) > af._score_margen_nota(af.MARGEN_OBJETIVO_NOTA)
    assert af._score_margen_nota(0.998) > af._score_margen_nota(0.40)


def test_score_margen_nunca_llega_a_100():
    """Asíntota, no tope duro -- ni un margen extremo (500%) satura."""
    assert af._score_margen_nota(5.0) < 100


def test_score_margen_es_cero_para_margen_no_positivo():
    assert af._score_margen_nota(0) == 0
    assert af._score_margen_nota(-0.5) == 0


def test_score_margen_lineal_por_debajo_del_objetivo():
    # A mitad de camino al objetivo (12.5% de margen), la mitad del puntaje
    # del tramo lineal (35 de 70).
    assert af._score_margen_nota(0.125) == 35.0


def test_formula_evaluacion_referencia_la_nota_de_la_misma_fila(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 4, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ])

    ws = wb[af.HOJA_INDICADORES]
    # segunda fila válida queda compacta en la fila 3 de "Indicadores" pero
    # su Nota (columna V) también está en la fila 3, no en la 4 -- el guard
    # de "Gastos Generales" sí referencia la fila real de "Proyectos" (4),
    # como Categoría vive ahí, no en "Indicadores".
    categoria_col = af.LETRA_COL_PROYECTOS["Categoría"]
    assert ws.cell(row=3, column=23).value == (
        f'=IF(Proyectos!{categoria_col}4="Gastos Generales","",'
        'IF(V3>=85,"Excelente",IF(V3>=70,"Bueno",'
        'IF(V3>=55,"Aprobado","Requiere atención"))))'
    )


def test_constantes_de_calibracion_de_la_nota():
    assert af.MARGEN_OBJETIVO_NOTA == 0.25
    assert af.SCORE_MARGEN_EN_OBJETIVO == 70
    assert af.K_MARGEN_NOTA_SOBRE_OBJETIVO == 0.3186
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


def test_nota_parcial_al_100_por_ciento_es_la_nota_completa():
    assert af.calcular_nota_parcial(88, 1.0) == 88


def test_nota_parcial_pondera_por_el_avance():
    """88 x 0.75 = 66: la ejecución va bien, pero solo tres cuartos del
    resultado están confirmados."""
    assert af.calcular_nota_parcial(88, 0.75) == 66


def test_nota_parcial_redondea_como_excel_no_como_python():
    """90 x 0.75 = 67.5 -> 68 (half away from zero). El round() nativo de
    Python daría 68 acá pero 66 para 66.5; se usa _redondear_excel para que
    el empate exacto en .5 caiga siempre del mismo lado que la fórmula."""
    assert af.calcular_nota_parcial(90, 0.75) == 68
    assert af.calcular_nota_parcial(70, 0.95) == 67  # 66.5 -> 67


def test_nota_parcial_vacia_si_falta_el_avance():
    assert af.calcular_nota_parcial(88, None) is None
    assert af.calcular_nota_parcial(88, "") is None


def test_nota_parcial_vacia_si_no_hay_nota():
    """Gastos Generales: la Nota ya viene vacía, la Parcial también. La
    cadena vacía cuenta igual que None -- es como llega la Nota de ese
    bucket desde Excel, y la fórmula espejo guarda contra ambas
    (IF(OR(V2="",...))): un guard asimétrico entre las dos
    implementaciones es exactamente la divergencia que este bloque
    existe para evitar."""
    assert af.calcular_nota_parcial(None, 0.75) is None
    assert af.calcular_nota_parcial("", 0.75) is None


def test_nota_parcial_con_avance_cero_es_cero():
    assert af.calcular_nota_parcial(88, 0.0) == 0


def test_nota_parcial_no_acota_un_avance_fuera_de_rango():
    """Ni Python ni Excel acotan: un avance >100% es un error de carga y
    debe verse igual en ambos lados, no corregirse en silencio en uno solo."""
    assert af.calcular_nota_parcial(80, 1.5) == 120


def test_formula_nota_parcial_referencia_la_nota_y_el_avance_con_guardas():
    formula = af._formula_nota_parcial(5, 2)
    col_nota = af.LETRA_COL_INDICADORES["Nota del Proyecto"]
    col_avance = af.LETRA_COL_PROYECTOS["% Avance"]
    assert formula == (
        f'=IF(OR({col_nota}2="",Proyectos!{col_avance}5=""),"",'
        f'ROUND({col_nota}2*Proyectos!{col_avance}5,0))'
    )
