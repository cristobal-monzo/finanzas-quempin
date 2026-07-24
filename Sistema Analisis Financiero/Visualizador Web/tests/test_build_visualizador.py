import analisis_financiero as af
import build_visualizador as bv


def _fila_proyecto_completa(ws, fila, **overrides):
    valores = {
        "TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID",
        "Estado": "En Proceso", "Monto de Venta (sin IVA)": 1_000_000,
        "Costos Materiales Proyectados": 300_000, "Costos Equipos Proyectados": 200_000,
        "Mano de Obra Proyectada": 200_000, "Otros Costos Proyectados": 100_000,
        "Mano de Obra Real": 350_000,
    }
    valores.update(overrides)
    for nombre_col, valor in valores.items():
        col = af.HEADERS_PROYECTOS.index(nombre_col) + 1
        ws.cell(row=fila, column=col, value=valor)


def _fila_detalle(ws, fila, tag, bucket, total):
    ws.cell(row=fila, column=1, value=tag)
    ws.cell(row=fila, column=2, value=bucket)
    ws.cell(row=fila, column=3, value=bucket)
    ws.cell(row=fila, column=4, value=total)


def test_es_proyecto_completo_true_cuando_las_6_columnas_tienen_valor():
    p = {
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    assert bv.es_proyecto_completo(p) is True


def test_es_proyecto_completo_false_si_falta_mano_de_obra_real():
    p = {
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": None,
    }
    assert bv.es_proyecto_completo(p) is False


def test_es_proyecto_completo_true_con_costo_en_cero():
    # 0 es un dato cargado, no un vacío -- no debe contar como incompleto.
    p = {
        "monto_venta": 1_000_000, "materiales_proy": 0, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    assert bv.es_proyecto_completo(p) is True


def test_leer_proyectos_salta_filas_sin_tag_o_nombre(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    _fila_proyecto_completa(ws, 2)
    ws.cell(row=3, column=1, value=None)
    ws.cell(row=3, column=2, value="Fila incompleta de encabezados")

    proyectos = bv.leer_proyectos(ws)
    assert len(proyectos) == 1
    assert proyectos[0]["tag"] == "UMAG"


def test_sumar_costos_reales_por_bucket_agrupa_por_tag_y_bucket(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws_detalle = wb[af.HOJA_DETALLE_COSTOS_REALES]
    _fila_detalle(ws_detalle, 2, "UMAG", "Materiales", 250_000)
    _fila_detalle(ws_detalle, 3, "UMAG", "Equipos", 150_000)
    _fila_detalle(ws_detalle, 4, "CFLI", "Materiales", 999_999)  # otro proyecto, no debe sumar

    sumas = bv.sumar_costos_reales_por_bucket(ws_detalle, "UMAG")
    assert sumas == {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}


def test_calcular_kpis_proyecto_recomputa_igual_que_formula_excel():
    # Mismos numeros que documenta el spec (docs/superpowers/specs/2026-07-23-
    # analisis-financiero-visualizador-web-design.md §2): total_proyectado=800000,
    # total_real=750000 -> desviacion=-6.25%, margen_real=250000 (25% de venta,
    # exactamente el objetivo) -> nota=98, "Excelente".
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["total_proyectado"] == 800_000
    assert kpis["total_real"] == 750_000
    assert kpis["margen_real"] == 250_000
    assert round(kpis["desviacion_pct"], 4) == -0.0625
    assert kpis["nota"] == 98
    assert kpis["evaluacion"] == "Excelente"


def test_calcular_kpis_proyecto_evaluacion_requiere_atencion_bajo_55():
    p = {
        "tag": "CFLI", "nombre": "Cesfam Limache", "cliente": "Cesfam", "estado": "En Proceso",
        "monto_venta": 1_000_000, "materiales_proy": 100_000, "equipos_proy": 100_000,
        "mo_proy": 100_000, "otros_proy": 100_000, "mo_real": 700_000,
    }
    costos_reales = {"Materiales": 300_000.0, "Equipos": 300_000.0, "Otros": 100_000.0}
    # total_real = 300000+300000+100000+700000 = 1400000 -> margen_real negativo

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["margen_real"] < 0
    assert kpis["evaluacion"] == "Requiere atención"


def test_calcular_kpis_proyecto_monto_venta_cero_no_explota():
    # monto_venta=0 es "completo" segun es_proyecto_completo (0 SI cuenta
    # como cargado) -- calcular_kpis_proyecto debe manejarlo sin ZeroDivisionError,
    # con score_margen=0 (no hay ratio de margen que calcular contra venta nula).
    p = {
        "tag": "ZERO", "nombre": "Proyecto Venta Cero", "cliente": "Cliente X", "estado": "En Proceso",
        "monto_venta": 0, "materiales_proy": 100_000, "equipos_proy": 0,
        "mo_proy": 0, "otros_proy": 0, "mo_real": 0,
    }
    costos_reales = {"Materiales": 0.0, "Equipos": 0.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["margen_real"] == 0
    assert isinstance(kpis, dict)
    assert kpis["nota"] >= 0


def test_calcular_kpis_proyecto_redondeo_estilo_excel_en_empate_exacto():
    # Construimos margen_real/monto_venta y desviacion_pct tal que
    # 0.7*score_margen + 0.3*score_desviacion == 96.5 exactamente.
    # score_margen = 100 (margen_real/monto_venta = 25% = MARGEN_OBJETIVO_NOTA).
    # 0.7*100 = 70 -> falta 26.5 de 0.3*score_desviacion -> score_desviacion = 26.5/0.3 = 88.333...
    # Para evitar decimales feos, usamos score_margen=95 y score_desviacion=100:
    # 0.7*95 + 0.3*100 = 66.5 + 30 = 96.5 exacto.
    # score_margen=95 -> margen_real/monto_venta = 0.95*0.25 = 0.2375
    # score_desviacion=100 -> desviacion_pct = 0
    monto_venta = 1_000_000
    margen_real_objetivo = 0.2375 * monto_venta  # 237_500
    total_real = monto_venta - margen_real_objetivo  # 762_500
    total_proyectado = total_real  # desviacion_pct = 0 -> score_desviacion = 100
    p = {
        "tag": "TIE", "nombre": "Empate Redondeo", "cliente": "Cliente Y", "estado": "En Proceso",
        "monto_venta": monto_venta,
        "materiales_proy": total_proyectado, "equipos_proy": 0, "mo_proy": 0, "otros_proy": 0,
        "mo_real": total_real,
    }
    costos_reales = {"Materiales": 0.0, "Equipos": 0.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    # Verificamos que efectivamente armamos el empate exacto en 96.5 antes de redondear.
    score_margen = min(100, max(0, (kpis["margen_real"] / monto_venta) / af.MARGEN_OBJETIVO_NOTA * 100))
    score_desviacion = min(100, max(0, 100 - abs(kpis["desviacion_pct"]) * 100))
    valor_sin_redondear = af.PESO_RENTABILIDAD_NOTA * score_margen + af.PESO_DESVIACION_NOTA * score_desviacion
    assert valor_sin_redondear == 96.5
    assert round(96.5) == 96  # banker's rounding de Python -- lo que NO queremos
    assert kpis["nota"] == 97  # ROUND-half-away-from-zero de Excel
