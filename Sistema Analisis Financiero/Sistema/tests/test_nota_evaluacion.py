import analisis_financiero as af


def test_formula_nota_usa_la_estimacion_al_cierre_sin_abs(tmp_path):
    """Corregido 2026-07-28: el componente de desviación ya no usa ABS() --
    MAX(0, desviación) anula el término para proyectos en o bajo presupuesto.
    Componente de margen corregido 2026-08-20 (curva sin tope duro).

    2026-09-21 (auditoría, fase 1): los insumos son el margen y la desviación
    ESTIMADOS AL CIERRE (columnas de esta misma hoja), la penalización llega
    a 0 con SOBRECOSTO_NOTA_CERO de sobrecosto, y la Nota queda vacía si
    falta cualquiera de los dos insumos."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])

    ws = wb[af.HOJA_INDICADORES]
    li = af.LETRA_COL_INDICADORES
    col_nota = af.HEADERS_INDICADORES.index("Nota del Proyecto") + 1
    margen = f"{li['Margen estimado al cierre %']}2"
    desviacion = f"{li['Desviación estimada al cierre %']}2"
    es_gastos_generales = f'Proyectos!{af.LETRA_COL_PROYECTOS["Categoría"]}2="Gastos Generales"'
    assert ws.cell(row=2, column=col_nota).value == (
        f'=IF({es_gastos_generales},"",IF(OR({margen}="",{desviacion}=""),"",'
        f"ROUND(0.7*IF({margen}<=0,0,IF({margen}<=0.25,{margen}/0.25*70,"
        f"70+30*(1-EXP(-({margen}-0.25)/0.3186))))"
        f"+0.3*MIN(100,MAX(0,100-MAX(0,{desviacion})/0.3*100)),0)))"
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
    # Guard propio de Nota vacía: en Excel "" >= 85 es TRUE (el texto
    # siempre gana contra un número), y una Nota vacía salía "Excelente".
    categoria_col = af.LETRA_COL_PROYECTOS["Categoría"]
    col_eval = af.HEADERS_INDICADORES.index("Evaluación") + 1
    nota = f'{af.LETRA_COL_INDICADORES["Nota del Proyecto"]}3'
    assert ws.cell(row=3, column=col_eval).value == (
        f'=IF(Proyectos!{categoria_col}4="Gastos Generales","",'
        f'IF({nota}="","",IF({nota}>=85,"Excelente",IF({nota}>=70,"Bueno",'
        f'IF({nota}>=55,"Aprobado","Requiere atención")))))'
    )


def test_constantes_de_calibracion_de_la_nota():
    assert af.MARGEN_OBJETIVO_NOTA == 0.25
    assert af.SCORE_MARGEN_EN_OBJETIVO == 70
    assert af.K_MARGEN_NOTA_SOBRE_OBJETIVO == 0.3186
    assert af.PESO_RENTABILIDAD_NOTA == 0.7
    assert af.PESO_DESVIACION_NOTA == 0.3
    assert af.SOBRECOSTO_NOTA_CERO == 0.30


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


# ── Penalización del sobrecosto (2026-09-21) ────────────────────────────────

def test_componente_de_control_llega_a_cero_con_30_por_ciento_de_sobrecosto():
    """Decisión del usuario (fase 1): +30% de sobrecosto ya es un descontrol
    total -- antes el componente recién llegaba a 0 con +100%, y un proyecto
    real con casi +28% seguía 'Bueno'."""
    assert af._score_desviacion_nota(0.30) == 0
    assert af._score_desviacion_nota(0.60) == 0
    assert af._score_desviacion_nota(0.15) == 50
    assert af._score_desviacion_nota(0.0) == 100


def test_ahorrar_sigue_dando_el_maximo_del_componente_de_control():
    assert af._score_desviacion_nota(-0.40) == 100


def test_nota_con_sobrecosto_de_30_por_ciento_pierde_todo_el_componente_de_control():
    margen = 0.50
    assert af.calcular_nota(margen, 0.30) == af._redondear_excel(0.7 * af._score_margen_nota(margen))
    assert af.calcular_nota(margen, 0.30) < af.calcular_nota(margen, 0.10) < af.calcular_nota(margen, 0.0)


# ── Estimación al cierre (reemplaza a la Nota Parcial, 2026-09-21) ──────────

def test_costo_estimado_al_cierre_al_100_por_ciento_es_el_costo_real():
    assert af.costo_estimado_al_cierre(90.0, 100.0, 1.0) == 90.0


def test_costo_estimado_al_cierre_suma_lo_que_falta_a_precio_de_presupuesto():
    """Un proyecto al 75% que ya gastó 99 de 100 presupuestados: lo que falta
    (25%) se estima a precio de presupuesto -> 99 + 25 = 124."""
    assert af.costo_estimado_al_cierre(99.0, 100.0, 0.75) == 124.0


def test_costo_estimado_al_cierre_vacio_sin_avance():
    assert af.costo_estimado_al_cierre(99.0, 100.0, None) is None
    assert af.costo_estimado_al_cierre(99.0, 100.0, "") is None


def test_avance_fuera_de_rango_se_acota_para_estimar():
    """Un avance de 150% no puede "des-gastar" presupuesto: se estima como
    100% (y alertas_proyecto lo avisa como error de carga)."""
    assert af.avance_acotado(1.5) == 1.0
    assert af.avance_acotado(-0.2) == 0.0
    assert af.costo_estimado_al_cierre(90.0, 100.0, 1.5) == 90.0


def test_escenario_indice_de_costo_extrapola_el_ritmo_de_gasto():
    """Pesimista: costo al cierre = real / avance. 99 gastados al 75% ->
    132 al cierre. Sin avance (0%) no hay ritmo que extrapolar."""
    assert af.costo_al_cierre_indice(99.0, 0.75) == 132.0
    assert af.costo_al_cierre_indice(99.0, 0.0) is None
    assert af.costo_al_cierre_indice(99.0, None) is None


def _valores(avance, venta=160.0, proy=(40.0, 20.0, 30.0, 10.0), mo_real=30.0, **extra):
    base = {
        "% Avance": avance, "Monto de Venta (sin IVA)": venta,
        "Costos Materiales Proyectados": proy[0], "Costos Equipos Proyectados": proy[1],
        "Mano de Obra Proyectada": proy[2], "Otros Costos Proyectados": proy[3],
        "Mano de Obra Real": mo_real,
    }
    base.update(extra)
    return base


def test_nota_de_un_proyecto_en_curso_usa_la_estimacion_al_cierre():
    """El caso que la Nota Parcial no veía: al 75% de avance y con 99 de 100
    ya gastados, el margen a la fecha (38%) parece excelente, pero el
    estimado al cierre es 22,5% con +24% de sobrecosto."""
    k = af.calcular_kpis_proyecto(_valores(0.75), {"Materiales": 50.0, "Equipos": 9.0, "Otros": 10.0})
    assert k["Total Real"] == 99.0
    assert k["Margen neto %"] == (160 - 99) / 160
    assert k["Costo estimado al cierre"] == 124.0
    assert k["Margen estimado al cierre %"] == (160 - 124) / 160
    assert k["Desviación estimada al cierre %"] == 124 / 100 - 1
    assert k["Nota del Proyecto"] == af.calcular_nota((160 - 124) / 160, 124 / 100 - 1)
    assert k["Nota del Proyecto"] < af.calcular_nota(k["Margen neto %"], k["Desviación % Total"])


def test_nota_de_un_proyecto_terminado_no_cambia_con_la_estimacion():
    k = af.calcular_kpis_proyecto(_valores(1.0), {"Materiales": 50.0, "Equipos": 9.0, "Otros": 10.0})
    assert k["Margen estimado al cierre %"] == k["Margen neto %"]
    assert k["Desviación estimada al cierre %"] == k["Desviación % Total"]
    assert k["Margen al cierre % (escenario índice de costo)"] == k["Margen neto %"]


def test_gastos_generales_no_tiene_nota_aunque_tenga_datos():
    k = af.calcular_kpis_proyecto(_valores(1.0, **{"Categoría": "Gastos Generales"}), {})
    assert k["Nota del Proyecto"] is None
    assert k["Evaluación"] is None


def test_margen_por_dia_vacio_si_el_cierre_es_futuro_o_falta_una_fecha():
    from datetime import date
    hoy = date(2026, 9, 21)
    assert af.margen_por_dia(date(2026, 1, 1), date(2027, 1, 1), 1000.0, hoy) is None
    assert af.margen_por_dia(None, date(2026, 2, 1), 1000.0, hoy) is None
    assert af.margen_por_dia(date(2026, 1, 1), date(2026, 1, 11), 1000.0, hoy) == 100.0
    # mismo día de inicio y cierre: MAX(1, días), no división por cero
    assert af.margen_por_dia(date(2026, 1, 1), date(2026, 1, 1), 1000.0, hoy) == 1000.0
