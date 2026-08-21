import base64 as _base64
import importlib.util
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import analisis_financiero as af

# Ver nota en Centro de Costos/Visualizador Web/tests/test_build_visualizador.py:
# los 3 modulos tienen un "build_visualizador.py" y sys.modules cachea por
# nombre, asi que hay que cargarlo por ruta bajo un nombre unico.
_RUTA_BV = Path(__file__).resolve().parent.parent / "build_visualizador.py"
_spec = importlib.util.spec_from_file_location("build_visualizador_af", _RUTA_BV)
bv = importlib.util.module_from_spec(_spec)
sys.modules["build_visualizador_af"] = bv
_spec.loader.exec_module(bv)


def _fila_proyecto_completa(ws, fila, **overrides):
    valores = {
        "TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID",
        # "Estado" y "Fecha de inicio" son parte de la regla de completitud
        # (af.CAMPOS_MANUALES_REQUERIDOS): sin ellos la fila no cuenta como
        # completa y el proyecto no recibe KPIs.
        "Estado": "En Proceso", "Fecha de inicio": datetime(2026, 1, 15),
        "Monto de Venta (sin IVA)": 1_000_000,
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


def _proyecto_completo_dict(**overrides):
    """Las 8 columnas de af.CAMPOS_MANUALES_REQUERIDOS, en las claves cortas
    que usa este módulo."""
    p = {
        "estado": "Terminado", "fecha_inicio": datetime(2026, 1, 15),
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    p.update(overrides)
    return p


def test_es_proyecto_completo_true_cuando_las_8_columnas_tienen_valor():
    assert bv.es_proyecto_completo(_proyecto_completo_dict()) is True


def test_es_proyecto_completo_false_si_falta_mano_de_obra_real():
    assert bv.es_proyecto_completo(_proyecto_completo_dict(mo_real=None)) is False


def test_es_proyecto_completo_false_si_falta_estado_o_fecha_de_inicio():
    """Ambas entraron a la regla al unificarla con la de los reportes PDF
    (2026-07-28): antes el dashboard las ignoraba y un proyecto sin Estado
    salía con KPIs acá pero era rechazado al pedir su PDF."""
    assert bv.es_proyecto_completo(_proyecto_completo_dict(estado=None)) is False
    assert bv.es_proyecto_completo(_proyecto_completo_dict(fecha_inicio=None)) is False


def test_es_proyecto_completo_false_con_cadena_vacia():
    assert bv.es_proyecto_completo(_proyecto_completo_dict(estado="")) is False


def test_es_proyecto_completo_true_con_costo_en_cero():
    # 0 es un dato cargado, no un vacío -- no debe contar como incompleto.
    assert bv.es_proyecto_completo(_proyecto_completo_dict(materiales_proy=0)) is True


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
    # Numeros del spec (docs/superpowers/specs/2026-07-23-analisis-financiero-
    # visualizador-web-design.md §2): total_proyectado=800000, total_real=750000
    # -> desviacion=-6.25%, margen_real=250000 (25% de venta, exactamente el
    # objetivo).
    #
    # OJO: ese spec (y este test hasta el 2026-07-28) esperaba nota=98, porque
    # el visualizador calculaba el componente de control con ABS(desviacion) y
    # descontaba 6.25 puntos por haber gastado MENOS de lo presupuestado. La
    # regla vigente usa MAX(0, desviacion): un proyecto bajo presupuesto no se
    # penaliza, asi que el componente de control da el puntaje maximo (100).
    #
    # Margen neto = 25% = exactamente MARGEN_OBJETIVO_NOTA. Hasta el
    # 2026-08-20 eso tambien topaba el componente de margen en 100 (nota=100).
    # Con la curva nueva, llegar justo al objetivo vale SCORE_MARGEN_EN_OBJETIVO
    # (70), no el tope -- nota = round(0.7*70 + 0.3*100) = 79. Ver
    # test_contrato_kpis.py y test_nota_evaluacion.py::test_score_margen_*.
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": None, "fecha_cierre": None, "categoria": None,
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["total_proyectado"] == 800_000
    assert kpis["total_real"] == 750_000
    assert kpis["margen_real"] == 250_000
    assert round(kpis["desviacion_pct"], 4) == -0.0625
    assert kpis["nota"] == 79
    assert kpis["evaluacion"] == "Bueno"


def test_calcular_kpis_proyecto_evaluacion_requiere_atencion_bajo_55():
    p = {
        "tag": "CFLI", "nombre": "Cesfam Limache", "cliente": "Cesfam", "estado": "En Proceso",
        "fecha_inicio": None, "fecha_cierre": None, "categoria": None,
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
        "fecha_inicio": None, "fecha_cierre": None, "categoria": None,
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
    # 0.7*score_margen + 0.3*score_desviacion == 54.5 exactamente. Nos
    # quedamos en la zona lineal de la curva de margen (margen <= 25% =
    # MARGEN_OBJETIVO_NOTA, curva 2026-08-20) para que el cálculo sea
    # aritmética racional exacta, sin EXP() de por medio (evita ruido de
    # punto flotante al construir el empate).
    # score_desviacion=100 -> desviacion_pct = 0.
    # score_margen=35 (mitad del tramo lineal, 0->70) -> margen_real/monto_venta
    # = 0.5 * MARGEN_OBJETIVO_NOTA = 0.125.
    # 0.7*35 + 0.3*100 = 24.5 + 30 = 54.5 exacto.
    monto_venta = 1_000_000
    margen_real_objetivo = 0.125 * monto_venta  # 125_000
    total_real = monto_venta - margen_real_objetivo  # 875_000
    total_proyectado = total_real  # desviacion_pct = 0 -> score_desviacion = 100
    p = {
        "tag": "TIE", "nombre": "Empate Redondeo", "cliente": "Cliente Y", "estado": "En Proceso",
        "fecha_inicio": None, "fecha_cierre": None, "categoria": None,
        "monto_venta": monto_venta,
        "materiales_proy": total_proyectado, "equipos_proy": 0, "mo_proy": 0, "otros_proy": 0,
        "mo_real": total_real,
    }
    costos_reales = {"Materiales": 0.0, "Equipos": 0.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    # Verificamos que efectivamente armamos el empate exacto en 54.5 antes de redondear.
    ratio_margen = (kpis["margen_real"] / monto_venta) / af.MARGEN_OBJETIVO_NOTA
    score_margen = ratio_margen * af.SCORE_MARGEN_EN_OBJETIVO
    score_desviacion = min(100, max(0, 100 - max(0, kpis["desviacion_pct"]) * 100))
    valor_sin_redondear = af.PESO_RENTABILIDAD_NOTA * score_margen + af.PESO_DESVIACION_NOTA * score_desviacion
    assert valor_sin_redondear == 54.5
    assert round(54.5) == 54  # banker's rounding de Python -- lo que NO queremos
    assert kpis["nota"] == 55  # ROUND-half-away-from-zero de Excel


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
    # 450 dias exactos entre las 2 fechas -- por encima del piso de 12 meses
    # (ver test siguiente), asi que el calculo usa el rango real observado.
    fecha_a = datetime(2026, 1, 1)
    fecha_b = fecha_a + timedelta(days=450)
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
    assert c["meses_activo"] == 15.0  # 450 dias / 30
    assert c["frecuencia"] == 1.6  # 2 / (15.0 / 12)
    assert c["margen_pct"] == 0.25  # (250000+500000)/(1000000+2000000)
    assert c["cltv"] == 1_200_000.0  # 1500000 * 1.6 * 2 * 0.25


def test_calcular_clientes_un_solo_proyecto_meses_activo_minimo_12():
    # Con un unico proyecto no hay forma de observar un intervalo real entre
    # compras -- el piso asume 1 año (12 meses), no 1 mes: un cliente de un
    # solo proyecto da Frecuencia=1 (una compra al año), no 12.
    kpis = [{"tag": "UMAG", "cliente": "UMAG", "monto_venta": 1_000_000, "margen_real": 200_000}]
    proyectos_por_tag = {"UMAG": {"fecha_inicio": datetime(2026, 3, 1)}}

    clientes = bv.calcular_clientes(kpis, proyectos_por_tag)

    assert clientes[0]["meses_activo"] == 12.0
    assert clientes[0]["frecuencia"] == 1.0


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
    assert re.match(r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}$", data["generado"])


def test_extraer_datos_saneados_kpis_proyectos_resumen(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert data["kpis_proyectos"]["n_completos"] == 1
    assert data["kpis_proyectos"]["margen_real_total"] == data["proyectos"][0]["margen_real"]
    assert data["kpis_proyectos"]["monto_venta_total"] == data["proyectos"][0]["monto_venta"]
    assert data["kpis_proyectos"]["total_real_total"] == data["proyectos"][0]["total_real"]
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


def test_leer_proyectos_incluye_fecha_cierre_y_categoria(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    _fila_proyecto_completa(ws, 2, **{"Fecha de cierre": datetime(2026, 3, 15), "Categoría": "I+D+i"})

    proyectos = bv.leer_proyectos(ws)

    assert proyectos[0]["fecha_cierre"] == datetime(2026, 3, 15)
    assert proyectos[0]["categoria"] == "I+D+i"


def test_leer_proyectos_categoria_y_fecha_cierre_none_si_no_estan_cargadas(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    _fila_proyecto_completa(ws, 2)  # sin overrides -- Categoría/Fecha de cierre quedan vacías

    proyectos = bv.leer_proyectos(ws)

    assert proyectos[0]["categoria"] is None
    assert proyectos[0]["fecha_cierre"] is None


def test_calcular_kpis_proyecto_incluye_desglose_de_costos_y_fechas():
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": datetime(2026, 1, 10), "fecha_cierre": datetime(2026, 3, 15),
        "categoria": "I+D+i",
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["fecha_inicio"] == "10-01-2026"
    assert kpis["fecha_cierre"] == "15-03-2026"
    assert kpis["categoria"] == "I+D+i"
    assert kpis["costos_proyectados"] == {
        "materiales": 300_000, "equipos": 200_000, "mo": 200_000, "otros": 100_000,
    }
    assert kpis["costos_reales"] == {
        "materiales": 250_000.0, "equipos": 150_000.0, "mo": 350_000, "otros": 0.0,
    }


def test_calcular_kpis_proyecto_fechas_none_si_no_hay_dato():
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": None, "fecha_cierre": None, "categoria": None,
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["fecha_inicio"] is None
    assert kpis["fecha_cierre"] is None
    assert kpis["categoria"] is None


def test_calcular_kpis_proyecto_kpis_por_categoria():
    # Mismos numeros que test_calcular_kpis_proyecto_recomputa_igual_que_
    # formula_excel: total_proyectado=800000, total_real=750000.
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": None, "fecha_cierre": None, "categoria": None,
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["costo_pct_venta"] == {"materiales": 0.25, "equipos": 0.15, "mo": 0.35, "otros": 0.0}
    estructura = kpis["estructura_pct"]
    assert round(estructura["materiales"], 6) == round(250_000 / 750_000, 6)
    assert round(sum(estructura.values()), 6) == 1.0  # las 4 categorias suman 100% del gasto real
    desviacion = kpis["desviacion_pct_categoria"]
    assert round(desviacion["materiales"], 4) == round(250_000 / 300_000 - 1, 4)
    assert round(desviacion["otros"], 4) == -1.0  # otros_proy=100000, real=0
    assert kpis["ahorro_sobrecosto"] == {"materiales": 50_000, "equipos": 50_000, "mo": -150_000, "otros": 100_000}
    assert kpis["ahorro_sobrecosto_total"] == 50_000  # 800000 - 750000


def test_calcular_kpis_proyecto_kpis_por_categoria_guardas_division_cero():
    # venta=0, total_real=0 (todo en 0) y una categoria proyectada en 0 no
    # deben explotar -- mismo principio que monto_venta=0 en
    # calcular_kpis_proyecto (test ya existente).
    p = {
        "tag": "ZERO", "nombre": "Proyecto Venta Cero", "cliente": "Cliente X", "estado": "En Proceso",
        "fecha_inicio": None, "fecha_cierre": None, "categoria": None,
        "monto_venta": 0, "materiales_proy": 0, "equipos_proy": 0,
        "mo_proy": 0, "otros_proy": 0, "mo_real": 0,
    }
    costos_reales = {"Materiales": 0.0, "Equipos": 0.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["costo_pct_venta"] == {"materiales": 0.0, "equipos": 0.0, "mo": 0.0, "otros": 0.0}
    assert kpis["estructura_pct"] == {"materiales": 0.0, "equipos": 0.0, "mo": 0.0, "otros": 0.0}
    assert kpis["desviacion_pct_categoria"] == {"materiales": 0.0, "equipos": 0.0, "mo": 0.0, "otros": 0.0}


def test_calcular_kpis_proyecto_margen_por_dia_none_sin_fecha_cierre():
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": datetime(2026, 1, 10), "fecha_cierre": None, "categoria": None,
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["margen_por_dia"] is None  # proyecto "en desarrollo"


def test_calcular_kpis_proyecto_margen_por_dia_calculado_con_ambas_fechas():
    fecha_inicio = datetime(2026, 1, 10)
    fecha_cierre = datetime(2026, 3, 15)
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": fecha_inicio, "fecha_cierre": fecha_cierre, "categoria": None,
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    dias = (fecha_cierre - fecha_inicio).days
    assert kpis["margen_por_dia"] == kpis["margen_real"] / dias


def test_calcular_kpis_proyecto_margen_por_dia_evita_div_cero_mismo_dia():
    fecha = datetime(2026, 1, 10)
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": fecha, "fecha_cierre": fecha, "categoria": None,
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["margen_por_dia"] == kpis["margen_real"]  # MAX(1, 0 dias) = 1


def test_calcular_peso_cartera_incluye_proyectos_incompletos_en_el_denominador():
    proyectos = [
        {"tag": "A", "monto_venta": 1_000_000},
        {"tag": "B", "monto_venta": 3_000_000},  # incompleto en otros campos, pero venta cuenta
    ]

    pesos = bv.calcular_peso_cartera(proyectos)

    assert pesos == {"A": 0.25, "B": 0.75}


def test_calcular_peso_cartera_ignora_venta_none_y_no_explota_con_total_cero():
    proyectos = [{"tag": "A", "monto_venta": None}, {"tag": "B", "monto_venta": None}]

    pesos = bv.calcular_peso_cartera(proyectos)

    assert pesos == {"A": 0.0, "B": 0.0}


def test_leer_detalle_subcategorias_agrupa_por_tag_y_calcula_pct(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws_detalle = wb[af.HOJA_DETALLE_COSTOS_REALES]
    ws_detalle.cell(row=2, column=1, value="UMAG")
    ws_detalle.cell(row=2, column=2, value="Consumibles")
    ws_detalle.cell(row=2, column=3, value="Materiales")
    ws_detalle.cell(row=2, column=4, value=250_000)
    ws_detalle.cell(row=3, column=1, value="UMAG")
    ws_detalle.cell(row=3, column=2, value="Equipos-Herramientas")
    ws_detalle.cell(row=3, column=3, value="Equipos")
    ws_detalle.cell(row=3, column=4, value=750_000)
    ws_detalle.cell(row=4, column=1, value="CFLI")
    ws_detalle.cell(row=4, column=2, value="Combustible")
    ws_detalle.cell(row=4, column=3, value="Otros")
    ws_detalle.cell(row=4, column=4, value=999_999)  # otro proyecto, no debe mezclarse

    detalle = bv.leer_detalle_subcategorias(ws_detalle)

    assert len(detalle["UMAG"]) == 2
    assert detalle["UMAG"][0] == {
        "subcategoria": "Consumibles", "bucket": "Materiales", "total": 250_000, "pct": 0.25,
    }
    assert detalle["UMAG"][1]["pct"] == 0.75
    assert len(detalle["CFLI"]) == 1


def test_calcular_kpis_proyecto_fechas_son_json_serializables():
    import json
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "estado": "En Proceso",
        "fecha_inicio": datetime(2026, 1, 10), "fecha_cierre": datetime(2026, 3, 15),
        "categoria": "I+D+i",
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    costos_reales = {"Materiales": 250_000.0, "Equipos": 150_000.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    # build() usa json.dump SIN default=str -- un datetime sin convertir
    # explotaria aca con TypeError al momento de escribir el snapshot real.
    json.dumps(kpis, ensure_ascii=False)


def _kpi_proyecto(tag, categoria, margen_real, nota):
    return {
        "tag": tag, "nombre": tag, "cliente": "Cliente", "estado": "En Proceso",
        "fecha_inicio": None, "fecha_cierre": None, "categoria": categoria,
        "monto_venta": 0, "total_proyectado": 0, "total_real": 0,
        "margen_real": margen_real, "desviacion_pct": 0.0, "nota": nota, "evaluacion": "Bueno",
        "costos_proyectados": {"materiales": 0, "equipos": 0, "mo": 0, "otros": 0},
        "costos_reales": {"materiales": 0, "equipos": 0, "mo": 0, "otros": 0},
    }


def test_calcular_categorias_agrupa_y_suma_margen():
    kpis = [
        _kpi_proyecto("P1", "I+D+i", 100_000, 80),
        _kpi_proyecto("P2", "I+D+i", 200_000, 90),
        _kpi_proyecto("P3", "Mantención", 50_000, 60),
    ]

    categorias = bv.calcular_categorias(kpis)
    por_nombre = {c["categoria"]: c for c in categorias}

    assert por_nombre["I+D+i"]["n_proyectos"] == 2
    assert por_nombre["I+D+i"]["margen_real_total"] == 300_000
    assert por_nombre["I+D+i"]["nota_promedio"] == 85.0
    assert por_nombre["I+D+i"]["tags_proyectos"] == ["P1", "P2"]
    assert por_nombre["Mantención"]["n_proyectos"] == 1


def test_calcular_categorias_proyecto_sin_categoria_va_a_bucket_sin_categoria():
    kpis = [_kpi_proyecto("P1", None, 100_000, 80), _kpi_proyecto("P2", "", 50_000, 70)]

    categorias = bv.calcular_categorias(kpis)

    assert len(categorias) == 1
    assert categorias[0]["categoria"] == "Sin categoría"
    assert categorias[0]["n_proyectos"] == 2


def test_calcular_categorias_lista_vacia_devuelve_lista_vacia():
    assert bv.calcular_categorias([]) == []


def test_embeber_reportes_pdf_incluye_solo_proyectos_con_pdf_existente(tmp_path, monkeypatch):
    raiz_reportes = tmp_path / "Reportes"
    (raiz_reportes / "Proyectos").mkdir(parents=True)
    (raiz_reportes / "Proyectos" / "UMAG.pdf").write_bytes(b"%PDF-1.4 contenido de prueba")
    monkeypatch.setattr(bv, "RAIZ_REPORTES", raiz_reportes)

    reportes = bv.embeber_reportes_pdf(
        [{"tag": "UMAG"}, {"tag": "SINPDF"}], [],
    )

    assert "proyecto:UMAG" in reportes
    assert "proyecto:SINPDF" not in reportes
    assert _base64.b64decode(reportes["proyecto:UMAG"]) == b"%PDF-1.4 contenido de prueba"


def test_embeber_reportes_pdf_incluye_categorias_con_pdf_existente(tmp_path, monkeypatch):
    raiz_reportes = tmp_path / "Reportes"
    (raiz_reportes / "Categorías").mkdir(parents=True)
    (raiz_reportes / "Categorías" / "I+D+i.pdf").write_bytes(b"%PDF fake categoria")
    monkeypatch.setattr(bv, "RAIZ_REPORTES", raiz_reportes)

    reportes = bv.embeber_reportes_pdf(
        [], [{"categoria": "I+D+i"}, {"categoria": "Sin categoría"}],
    )

    assert "categoria:I+D+i" in reportes
    assert "categoria:Sin categoría" not in reportes


def test_embeber_reportes_pdf_devuelve_vacio_si_no_hay_carpeta_reportes(tmp_path, monkeypatch):
    monkeypatch.setattr(bv, "RAIZ_REPORTES", tmp_path / "esta-carpeta-no-existe")

    reportes = bv.embeber_reportes_pdf([{"tag": "X"}], [{"categoria": "Y"}])

    assert reportes == {}


def test_extraer_datos_saneados_incluye_categorias_y_reportes_pdf(tmp_path, monkeypatch):
    ruta_excel = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta_excel)
    ws = wb[af.HOJA_PROYECTOS]
    _fila_proyecto_completa(ws, 2, **{"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Categoría": "I+D+i"})
    wb.save(ruta_excel)

    raiz_reportes = tmp_path / "Reportes"
    (raiz_reportes / "Proyectos").mkdir(parents=True)
    (raiz_reportes / "Proyectos" / "UMAG.pdf").write_bytes(b"%PDF fake")
    monkeypatch.setattr(bv, "RAIZ_REPORTES", raiz_reportes)

    data = bv.extraer_datos_saneados(ruta_excel)

    assert data["categorias"] == [{
        "categoria": "I+D+i", "n_proyectos": 1,
        "margen_real_total": data["proyectos"][0]["margen_real"],
        "nota_promedio": data["proyectos"][0]["nota"],
        "tags_proyectos": ["UMAG"],
    }]
    assert "proyecto:UMAG" in data["reportes_pdf"]


def test_extraer_datos_saneados_incluye_peso_cartera_y_detalle_subcategorias(tmp_path):
    ruta_excel = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta_excel)
    ws = wb[af.HOJA_PROYECTOS]
    _fila_proyecto_completa(ws, 2, **{"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG"})
    _fila_proyecto_completa(ws, 3, **{
        "TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache",
        "Monto de Venta (sin IVA)": 3_000_000,
    })
    ws_detalle = wb[af.HOJA_DETALLE_COSTOS_REALES]
    _fila_detalle(ws_detalle, 2, "UMAG", "Materiales", 250_000)
    wb.save(ruta_excel)

    data = bv.extraer_datos_saneados(ruta_excel)

    por_tag = {p["tag"]: p for p in data["proyectos"]}
    assert por_tag["UMAG"]["peso_cartera_pct"] == 0.25  # 1_000_000 / (1_000_000 + 3_000_000)
    assert por_tag["UMAG"]["detalle_subcategorias"] == [
        {"subcategoria": "Materiales", "bucket": "Materiales", "total": 250_000, "pct": 1.0},
    ]
    assert por_tag["CFLI"]["detalle_subcategorias"] == []  # sin filas en 'Detalle Costos Reales'
