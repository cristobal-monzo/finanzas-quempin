import re
from datetime import datetime, timedelta

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


def test_percentil_inclusivo_replica_percentile_excel():
    valores = [10, 20, 30, 40, 50]
    # PERCENTILE.INC(rango, 0.5) con 5 valores = el del medio (30).
    assert bv.percentil_inclusivo(valores, 0.5) == 30
    # PERCENTILE.INC(rango, 0) = minimo, PERCENTILE.INC(rango, 1) = maximo.
    assert bv.percentil_inclusivo(valores, 0) == 10
    assert bv.percentil_inclusivo(valores, 1) == 50


def test_percentil_inclusivo_con_un_solo_valor_devuelve_ese_valor():
    assert bv.percentil_inclusivo([42], 0.67) == 42


def test_calcular_clientes_agrupa_y_calcula_cltv():
    # 180 dias exactos entre las 2 fechas -- evita aritmetica de calendario
    # ambigua (dias/mes no calzan limpio con /30) en la asercion.
    fecha_a = datetime(2026, 1, 1)
    fecha_b = fecha_a + timedelta(days=180)
    kpis = [
        {"tag": "AGCI1", "cliente": "AGCID", "monto_venta": 1_000_000, "margen_real": 250_000},
        {"tag": "AGCI2", "cliente": "AGCID", "monto_venta": 2_000_000, "margen_real": 500_000},
    ]
    proyectos_por_tag = {
        "AGCI1": {"fecha_inicio": fecha_a},
        "AGCI2": {"fecha_inicio": fecha_b},
    }

    clientes = bv.calcular_clientes(kpis, proyectos_por_tag)

    assert len(clientes) == 1
    c = clientes[0]
    assert c["cliente"] == "AGCID"
    assert c["aov"] == 1_500_000
    assert c["vida"] == 2
    assert c["meses_activo"] == 6.0  # 180 dias / 30
    assert c["frecuencia"] == 4.0  # 2 / (6.0 / 12)
    assert c["margen_pct"] == 0.25  # (250000+500000)/(1000000+2000000)
    assert c["cltv"] == 3_000_000.0  # 1500000 * 4.0 * 2 * 0.25


def test_calcular_clientes_un_solo_proyecto_meses_activo_minimo_1():
    kpis = [{"tag": "UMAG", "cliente": "UMAG", "monto_venta": 1_000_000, "margen_real": 200_000}]
    proyectos_por_tag = {"UMAG": {"fecha_inicio": datetime(2026, 3, 1)}}

    clientes = bv.calcular_clientes(kpis, proyectos_por_tag)

    assert clientes[0]["meses_activo"] == 1.0


def test_calcular_clientes_ignora_proyectos_sin_cliente_asignado():
    kpis = [{"tag": "X", "cliente": None, "monto_venta": 1_000_000, "margen_real": 200_000}]
    proyectos_por_tag = {"X": {"fecha_inicio": datetime(2026, 1, 1)}}

    assert bv.calcular_clientes(kpis, proyectos_por_tag) == []


def _wb_con_proyectos(tmp_path, filas):
    """filas: list[dict] con al menos tag/nombre/cliente + las columnas
    manuales de _fila_proyecto_completa (usar overrides para omitir alguna
    y simular un proyecto incompleto)."""
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)
    ws = wb[af.HOJA_PROYECTOS]
    for i, fila in enumerate(filas, start=2):
        _fila_proyecto_completa(ws, i, **fila)
    wb.save(ruta)
    return ruta


def test_extraer_datos_saneados_separa_completos_e_incompletos(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
        {
            "TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache", "Cliente": "Cesfam",
            "Monto de Venta (sin IVA)": None,
        },
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert len(data["proyectos"]) == 1
    assert data["proyectos"][0]["tag"] == "UMAG"
    assert len(data["pendientes"]) == 1
    pendiente = data["pendientes"][0]
    assert pendiente["nombre"] == "Cesfam Limache"
    assert pendiente["mensaje"] == "Cesfam Limache — Falta ingresar información en 'Análisis de Proyectos'"
    assert pendiente["link"] == bv.URL_PLANILLA_PENDIENTE
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", data["generado"])


def test_extraer_datos_saneados_kpis_proyectos_resumen(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert data["kpis_proyectos"]["n_completos"] == 1
    assert data["kpis_proyectos"]["margen_real_total"] == data["proyectos"][0]["margen_real"]
    assert data["kpis_proyectos"]["nota_promedio"] == data["proyectos"][0]["nota"]
    assert data["kpis_proyectos"]["n_requiere_atencion"] == 0


def test_extraer_datos_saneados_cliente_con_proyecto_pendiente_muestra_nota(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "AGCI1", "Nombre del proyecto": "AGCID Febrero", "Cliente": "AGCID"},
        {
            "TAG proyecto": "AGCI2", "Nombre del proyecto": "AGCID Agosto", "Cliente": "AGCID",
            "Monto de Venta (sin IVA)": None,
        },
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert len(data["clientes"]) == 1
    assert data["clientes"][0]["cliente"] == "AGCID"
    assert data["clientes"][0]["proyectos_pendientes"] == 1


def test_extraer_datos_saneados_cliente_100pct_incompleto_no_aparece(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {
            "TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache", "Cliente": "Cesfam",
            "Monto de Venta (sin IVA)": None,
        },
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert data["clientes"] == []


def test_calcular_clientes_clasificacion_por_percentil_de_cltv():
    # 3 clientes con CLTV muy distinto -- el de mayor CLTV debe caer en
    # "Clientes estrategicos" (>=p67), el de menor en "Clientes de
    # oportunidad" (<p33).
    kpis = [
        {"tag": "A", "cliente": "Bajo", "monto_venta": 100_000, "margen_real": 10_000},
        {"tag": "B", "cliente": "Medio", "monto_venta": 1_000_000, "margen_real": 200_000},
        {"tag": "C", "cliente": "Alto", "monto_venta": 10_000_000, "margen_real": 3_000_000},
    ]
    proyectos_por_tag = {
        "A": {"fecha_inicio": datetime(2026, 1, 1)},
        "B": {"fecha_inicio": datetime(2026, 1, 1)},
        "C": {"fecha_inicio": datetime(2026, 1, 1)},
    }

    clientes = {c["cliente"]: c for c in bv.calcular_clientes(kpis, proyectos_por_tag)}

    assert clientes["Alto"]["clasificacion"] == "Clientes estratégicos"
    assert clientes["Bajo"]["clasificacion"] == "Clientes de oportunidad"


def test_build_genera_html_no_vacio_con_snapshot_incrustado(tmp_path, monkeypatch):
    ruta_excel = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ])
    ruta_data = tmp_path / "data" / "analisis-financiero.json"
    ruta_build = tmp_path / "build" / "index.html"

    monkeypatch.setattr(bv, "RUTA_EXCEL", ruta_excel)
    monkeypatch.setattr(bv, "RUTA_DATA_JSON", ruta_data)
    monkeypatch.setattr(bv, "RUTA_BUILD_HTML", ruta_build)

    resultado = bv.build()

    assert resultado == 0
    assert ruta_data.exists()
    assert ruta_build.exists()
    contenido = ruta_build.read_text(encoding="utf-8")
    assert "__AF_DATA_B64__" not in contenido
    assert len(contenido) > 1000


def test_build_falla_si_no_existe_el_excel(tmp_path, monkeypatch):
    monkeypatch.setattr(bv, "RUTA_EXCEL", tmp_path / "no-existe.xlsx")
    assert bv.build() == 1
