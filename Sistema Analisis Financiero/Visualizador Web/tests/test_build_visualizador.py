import base64 as _base64
import importlib.util
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pytest

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
        # "% Avance" es parte de la regla de completitud
        # (af.CAMPOS_MANUALES_REQUERIDOS); "Fecha de inicio" ya no (2026-09-21)
        # pero se carga igual, como en la planilla real.
        "% Avance": 0.5, "Fecha de inicio": datetime(2026, 1, 15),
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
    """Las columnas de af.CAMPOS_MANUALES_REQUERIDOS (más la fecha de
    inicio, que ya no es requerida), en las claves cortas de este módulo."""
    p = {
        "avance": 1.0, "fecha_inicio": datetime(2026, 1, 15),
        "monto_venta": 1_000_000, "materiales_proy": 300_000, "equipos_proy": 200_000,
        "mo_proy": 200_000, "otros_proy": 100_000, "mo_real": 350_000,
    }
    p.update(overrides)
    return p


def test_es_proyecto_completo_true_cuando_las_8_columnas_tienen_valor():
    assert bv.es_proyecto_completo(_proyecto_completo_dict()) is True


def test_es_proyecto_completo_false_si_falta_mano_de_obra_real():
    assert bv.es_proyecto_completo(_proyecto_completo_dict(mo_real=None)) is False


def test_es_proyecto_completo_false_si_falta_avance_pero_no_por_la_fecha_de_inicio():
    """% Avance entró a la regla al unificarla con la de los reportes PDF
    (2026-07-28). Fecha de inicio salió el 2026-09-21: solo la usa el Margen
    por día, y exigirla dejaba fuera proyectos con todo lo demás cargado."""
    assert bv.es_proyecto_completo(_proyecto_completo_dict(avance=None)) is False
    assert bv.es_proyecto_completo(_proyecto_completo_dict(fecha_inicio=None)) is True


def test_es_proyecto_completo_false_con_cadena_vacia():
    assert bv.es_proyecto_completo(_proyecto_completo_dict(avance="")) is False


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
    # Numeros del spec (docs/specs/2026-07-23-analisis-financiero-
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
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 1.0,
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
        "tag": "CFLI", "nombre": "Cesfam Limache", "cliente": "Cesfam", "avance": 0.5,
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
    # como cargado) -- calcular_kpis_proyecto debe manejarlo sin
    # ZeroDivisionError. Desde 2026-09-21 no hay margen % contra una venta
    # nula (None, como la celda vacía del Excel) y por lo tanto tampoco Nota:
    # antes se inventaba un margen de 0% y salía una Nota.
    p = {
        "tag": "ZERO", "nombre": "Proyecto Venta Cero", "cliente": "Cliente X", "avance": 0.5,
        "fecha_inicio": None, "fecha_cierre": None, "categoria": None,
        "monto_venta": 0, "materiales_proy": 100_000, "equipos_proy": 0,
        "mo_proy": 0, "otros_proy": 0, "mo_real": 0,
    }
    costos_reales = {"Materiales": 0.0, "Equipos": 0.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    assert kpis["margen_real"] == 0
    assert kpis["margen_estimado_cierre_pct"] is None
    assert kpis["nota"] is None
    assert kpis["evaluacion"] is None


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
        "tag": "TIE", "nombre": "Empate Redondeo", "cliente": "Cliente Y", "avance": 1.0,
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


def _kpi_cliente(tag, cliente, venta, costo_real):
    """Un proyecto terminado, por el mismo camino que el snapshot real."""
    p = {
        "tag": tag, "nombre": tag, "cliente": cliente, "avance": 1.0,
        "fecha_inicio": None, "fecha_cierre": None, "categoria": "Mantenimiento",
        "monto_venta": venta, "materiales_proy": 0, "equipos_proy": 0,
        "mo_proy": 0, "otros_proy": costo_real, "mo_real": 0,
    }
    return bv.calcular_kpis_proyecto(p, {"Otros": costo_real})


def test_calcular_clientes_suma_margen_y_venta_y_detecta_recompra():
    """2026-09-21: el CLTV (AOV x Frecuencia x Vida x Margen) contaba dos
    veces la cantidad de compras -- con 2 proyectos daba el doble del margen
    realmente dejado. Ahora: venta y margen acumulados, y si volvió a
    comprar."""
    clientes = bv.calcular_clientes([
        _kpi_cliente("AGCI1", "AGCID", 1_000_000, 750_000),
        _kpi_cliente("AGCI2", "AGCID", 2_000_000, 1_500_000),
    ])

    assert len(clientes) == 1
    c = clientes[0]
    assert c["cliente"] == "AGCID"
    assert c["n_proyectos"] == 2
    assert c["venta_acumulada"] == 3_000_000
    assert c["margen_acumulado"] == 750_000  # 250.000 + 500.000, no el doble
    assert c["margen_pct"] == 0.25
    assert c["recurrente"] is True
    assert "cltv" not in c


def test_calcular_clientes_un_solo_proyecto_no_es_recurrente():
    clientes = bv.calcular_clientes([_kpi_cliente("UMAG", "UMAG", 1_000_000, 800_000)])
    assert clientes[0]["n_proyectos"] == 1
    assert clientes[0]["recurrente"] is False


def test_calcular_clientes_ignora_proyectos_sin_cliente_asignado():
    assert bv.calcular_clientes([_kpi_cliente("X", None, 1_000_000, 800_000)]) == []


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


def test_snapshot_trae_el_n_de_requerimiento_para_enlazar_al_formulador(tmp_path):
    """2026-10-06: la ficha enlaza al proyecto en el Formulador por su N° de
    requerimiento (la clave común entre herramientas). La celda puede traer
    280, 280.0 o «280»; lo que no es un N° queda en None."""
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID", af.pf.COLUMNA_REQ: 280.0},
        {"TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache", "Cliente": "Cesfam",
         "Monto de Venta (sin IVA)": None, af.pf.COLUMNA_REQ: "301"},
        {"TAG proyecto": "OTRO", "Nombre del proyecto": "Otro", "Cliente": "X", af.pf.COLUMNA_REQ: "sin n°"},
    ])

    data = bv.extraer_datos_saneados(ruta)

    por_tag = {p["tag"]: p for p in data["proyectos"]}
    assert por_tag["UMAG"]["req"] == "280"
    assert por_tag["OTRO"]["req"] is None
    assert data["pendientes"][0]["tag"] == "CFLI" and data["pendientes"][0]["req"] == "301"


def test_la_ficha_enlaza_al_formulador_y_el_tablero_abre_enlaces_por_tag():
    """La ficha lleva «Ver la formulación ↗» (por N° de requerimiento o por
    TAG) y #proyecto=TAG, el enlace que deja el Formulador al pasar a
    ejecución, abre la ficha o «Ingresar datos»."""
    html = (Path(__file__).resolve().parent.parent / "template.html").read_text(encoding="utf-8")
    assert "formulacion-proyectos-quempin/" in html
    assert "'#/req/' + encodeURIComponent(p.req)" in html and "'#/tag/' + encodeURIComponent(p.tag)" in html
    assert "enlaceFormuladorHtml(p) + pdf" in html, "el enlace va en la cabecera de la ficha"
    assert "/^#proyecto=([^&]+)/" in html and "window.addEventListener('hashchange', abrirDesdeEnlace)" in html
    assert "if (abrirIngresoDe(tag)) return;" in html


def test_pendientes_dicen_que_campo_falta_y_cuanta_venta_queda_fuera(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
        {
            "TAG proyecto": "ESFO", "Nombre del proyecto": "ESFOCAR", "Cliente": "ESFOCAR",
            "Fecha de inicio": None, "Monto de Venta (sin IVA)": 4_000_000,
        },
        {
            "TAG proyecto": "BWIL", "Nombre del proyecto": "Bomba Wilo", "Cliente": "Wilo",
            "Monto de Venta (sin IVA)": None, "Mano de Obra Real": None,
        },
        {
            "TAG proyecto": "FCH1", "Nombre del proyecto": "FACH1", "Cliente": "FACH",
            "Monto de Venta (sin IVA)": 9_000_000, "Mano de Obra Real": None,
        },
    ])

    data = bv.extraer_datos_saneados(ruta)

    # ESFO solo no tenía Fecha de inicio: desde 2026-09-21 entra al análisis.
    assert "ESFO" in [p["tag"] for p in data["proyectos"]]
    # Orden: mas venta fuera del analisis primero; sin venta cargada al final.
    assert [p["tag"] for p in data["pendientes"]] == ["FCH1", "BWIL"]
    por_tag = {p["tag"]: p for p in data["pendientes"]}
    assert por_tag["FCH1"]["campos_faltantes"] == ["Mano de Obra Real"]
    assert por_tag["FCH1"]["monto_venta"] == 9_000_000
    assert por_tag["BWIL"]["campos_faltantes"] == ["Monto de Venta (sin IVA)", "Mano de Obra Real"]
    assert por_tag["BWIL"]["monto_venta"] is None


def test_gastos_generales_no_aparece_como_pendiente(tmp_path):
    """Gastos Generales nunca tiene venta: listarlo como 'falta completar'
    pide un dato que por diseño no existe."""
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
        {
            "TAG proyecto": "GGEN", "Nombre del proyecto": "Gastos Generales",
            "Categoría": af.CATEGORIA_GASTOS_GENERALES, "Monto de Venta (sin IVA)": None,
        },
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert data["pendientes"] == []
    assert data["cobertura"]["n_proyectos"] == 1


def test_cobertura_compara_lo_analizado_contra_toda_la_venta_cargada(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
        {
            "TAG proyecto": "FCH1", "Nombre del proyecto": "FACH1", "Cliente": "FACH",
            "Monto de Venta (sin IVA)": 3_000_000, "Mano de Obra Real": None,
        },
        {
            "TAG proyecto": "BWIL", "Nombre del proyecto": "Bomba Wilo", "Cliente": "Wilo",
            "Monto de Venta (sin IVA)": None,
        },
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert data["cobertura"] == {
        "n_proyectos": 3,
        "n_completos": 1,
        "venta_cargada_total": 4_000_000,
        "venta_completos": 1_000_000,
    }


def test_snapshot_trae_los_umbrales_de_evaluacion_del_modulo_compartido(tmp_path):
    """El template colorea la Nota con estos umbrales: si viajan en el
    snapshot, el JS no puede quedar con una copia desactualizada."""
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ])

    data = bv.extraer_datos_saneados(ruta)

    assert data["umbrales"] == {
        "excelente": af.UMBRAL_EXCELENTE, "bueno": af.UMBRAL_BUENO, "aprobado": af.UMBRAL_APROBADO,
        "sobrecosto_nota_cero": af.SOBRECOSTO_NOTA_CERO,
        "margen_objetivo": af.MARGEN_OBJETIVO_NOTA,
        "peso_rentabilidad": af.PESO_RENTABILIDAD_NOTA,
        "peso_control": af.PESO_DESVIACION_NOTA,
        "alerta_sobrecosto": af.UMBRAL_ALERTA_SOBRECOSTO,
        "alerta_costo_incompleto": af.UMBRAL_ALERTA_COSTO_INCOMPLETO,
    }


def test_template_declara_doctype_charset_y_viewport():
    """Sin DOCTYPE el navegador renderiza en modo quirks; sin charset, un
    servidor que no mande UTF-8 rompe la regex del gate y el tablero no abre;
    sin viewport, un telefono lo dibuja a ancho de escritorio."""
    template = bv.RUTA_TEMPLATE.read_text(encoding="utf-8")
    assert template.lstrip().lower().startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in template.lower()
    assert 'name="viewport"' in template


def test_template_no_depende_del_encoding_para_la_regex_del_gate():
    """La regex que quita tildes a la contraseña iba con los caracteres
    combinantes literales -- leidos como Latin-1 forman un rango invalido y
    tiran abajo todo el script. Con escapes \\u no depende del encoding.
    Desde 2026-10-05 esa regex vive en el candado compartido (candado.js)."""
    template = bv.RUTA_TEMPLATE.read_text(encoding="utf-8")
    candado_js = bv.candado.RUTA_JS.read_text(encoding="utf-8")
    for texto in (template, candado_js):
        assert chr(0x300) not in texto and chr(0x36F) not in texto
    assert "\\u0300-\\u036f" in candado_js


def test_extraer_datos_saneados_kpis_proyectos_resumen(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ])

    data = bv.extraer_datos_saneados(ruta)

    kp, proyecto = data["kpis_proyectos"], data["proyectos"][0]
    assert kp["n_completos"] == 1
    # Margen de la cartera = el estimado al cierre (el proyecto está al 50%).
    assert kp["margen_estimado_total"] == proyecto["margen_estimado_cierre"]
    assert kp["costo_estimado_total"] == proyecto["costo_estimado_cierre"]
    assert kp["monto_venta_total"] == proyecto["monto_venta"]
    assert kp["margen_ponderado_pct"] == proyecto["margen_estimado_cierre"] / proyecto["monto_venta"]
    assert kp["n_en_curso"] == 1
    assert kp["nota_promedio"] == proyecto["nota"]
    assert kp["n_con_alertas"] == (1 if proyecto["alertas"] else 0)
    assert "margen_real_total" not in kp


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


def test_calcular_clientes_clasificacion_por_percentil_de_margen_acumulado():
    # 3 clientes con margen acumulado muy distinto -- el mayor cae en
    # "Clientes estrategicos" (>=p67), el menor en "de oportunidad" (<p33).
    clientes = {c["cliente"]: c for c in bv.calcular_clientes([
        _kpi_cliente("A", "Bajo", 100_000, 90_000),
        _kpi_cliente("B", "Medio", 1_000_000, 800_000),
        _kpi_cliente("C", "Alto", 10_000_000, 7_000_000),
    ])}

    assert clientes["Alto"]["clasificacion"] == "Clientes estratégicos"
    assert clientes["Bajo"]["clasificacion"] == "Clientes de oportunidad"


def test_snapshot_trae_resumen_de_recompra(tmp_path):
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "A1", "Nombre del proyecto": "A1", "Cliente": "A"},
        {"TAG proyecto": "A2", "Nombre del proyecto": "A2", "Cliente": "A"},
        {"TAG proyecto": "B1", "Nombre del proyecto": "B1", "Cliente": "B"},
    ])
    data = bv.extraer_datos_saneados(ruta)
    assert data["clientes_resumen"] == {"n_clientes": 2, "n_recurrentes": 1, "tasa_recompra": 0.5}


def test_build_genera_html_no_vacio_con_snapshot_incrustado(tmp_path, monkeypatch):
    ruta_excel = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ])
    ruta_data = tmp_path / "data" / "analisis-financiero.json"
    ruta_build = tmp_path / "build" / "index.html"

    monkeypatch.setattr(bv, "RUTA_EXCEL", ruta_excel)
    monkeypatch.setattr(bv, "RUTA_DATA_JSON", ruta_data)
    monkeypatch.setattr(bv, "RUTA_BUILD_HTML", ruta_build)
    monkeypatch.setattr(bv, "RAIZ_REPORTES", tmp_path / "sin-reportes")

    resultado = bv.build()

    assert resultado == 0
    assert ruta_data.exists()
    assert ruta_build.exists()
    contenido = ruta_build.read_text(encoding="utf-8")
    assert "__AF_DATA_B64__" not in contenido
    assert len(contenido) > 1000
    # El pulso del procesador (Sistema Intercambio/pulso.js) va insertado, no copiado (2026-10-08).
    assert "__AF_PULSO_JS__" not in contenido and bv.RUTA_PULSO_JS.read_text(encoding="utf-8") in contenido


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
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 0.5,
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
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 0.5,
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
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 0.5,
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
        "tag": "ZERO", "nombre": "Proyecto Venta Cero", "cliente": "Cliente X", "avance": 0.5,
        "fecha_inicio": None, "fecha_cierre": None, "categoria": None,
        "monto_venta": 0, "materiales_proy": 0, "equipos_proy": 0,
        "mo_proy": 0, "otros_proy": 0, "mo_real": 0,
    }
    costos_reales = {"Materiales": 0.0, "Equipos": 0.0, "Otros": 0.0}

    kpis = bv.calcular_kpis_proyecto(p, costos_reales)

    # Vacío (None -> "—" en el tablero), no 0,0 %: un cero inventado se lee
    # como "sin desviación", que no es lo mismo que "sin presupuesto contra
    # qué medirla" (2026-09-21, mismo criterio que la celda vacía del Excel).
    vacio = {"materiales": None, "equipos": None, "mo": None, "otros": None}
    assert kpis["costo_pct_venta"] == vacio
    assert kpis["estructura_pct"] == vacio
    assert kpis["desviacion_pct_categoria"] == vacio


def test_calcular_kpis_proyecto_margen_por_dia_none_sin_fecha_cierre():
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 0.5,
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
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 0.5,
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
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 0.5,
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

    assert pesos == {"A": None, "B": None}  # sin venta cargada no hay peso


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
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 0.5,
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


def _kpi_proyecto(tag, categoria, margen_estimado, nota, venta=1_000_000):
    return {
        "tag": tag, "nombre": tag, "cliente": "Cliente", "avance": 0.5,
        "fecha_inicio": None, "fecha_cierre": None, "categoria": categoria,
        "monto_venta": venta, "total_proyectado": 0, "total_real": 0,
        "margen_real": margen_estimado, "margen_estimado_cierre": margen_estimado,
        "desviacion_pct": 0.0, "nota": nota, "evaluacion": "Bueno",
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
    assert por_nombre["I+D+i"]["margen_estimado_total"] == 300_000
    assert por_nombre["I+D+i"]["venta_total"] == 2_000_000
    assert por_nombre["I+D+i"]["margen_pct"] == 0.15  # ponderado por venta, no promedio de %
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


def test_reportes_pdf_publicables_incluye_solo_proyectos_con_pdf_existente(tmp_path, monkeypatch):
    raiz_reportes = tmp_path / "Reportes"
    (raiz_reportes / "Proyectos").mkdir(parents=True)
    (raiz_reportes / "Proyectos" / "UMAG.pdf").write_bytes(b"%PDF-1.4 contenido de prueba")
    monkeypatch.setattr(bv, "RAIZ_REPORTES", raiz_reportes)

    reportes = bv.reportes_pdf_publicables(
        [{"tag": "UMAG"}, {"tag": "SINPDF"}], [],
    )

    assert set(reportes) == {"proyecto:UMAG"}
    meta = reportes["proyecto:UMAG"]
    # El PDF ya no viaja en los datos (2026-10-08): solo dónde está cifrado, su fecha y su estado.
    assert meta["archivo"] == bv.candado.nombre_archivo(b"%PDF-1.4 contenido de prueba")
    assert re.fullmatch(r"\d{2}-\d{2}-\d{4}", meta["fecha"])
    assert meta["desactualizado"] is None
    assert "contenido de prueba" not in str(reportes)
    assert _base64.b64encode(b"%PDF-1.4").decode("ascii") not in str(reportes)


def test_reportes_pdf_publicables_incluye_categorias_con_pdf_existente(tmp_path, monkeypatch):
    raiz_reportes = tmp_path / "Reportes"
    (raiz_reportes / "Categorías").mkdir(parents=True)
    (raiz_reportes / "Categorías" / "I+D+i.pdf").write_bytes(b"%PDF fake categoria")
    monkeypatch.setattr(bv, "RAIZ_REPORTES", raiz_reportes)

    reportes = bv.reportes_pdf_publicables(
        [], [{"categoria": "I+D+i"}, {"categoria": "Sin categoría"}],
    )

    assert set(reportes) == {"categoria:I+D+i"}


def test_reportes_pdf_publicables_devuelve_vacio_si_no_hay_carpeta_reportes(tmp_path, monkeypatch):
    monkeypatch.setattr(bv, "RAIZ_REPORTES", tmp_path / "esta-carpeta-no-existe")

    reportes = bv.reportes_pdf_publicables([{"tag": "X"}], [{"categoria": "Y"}])

    assert reportes == {}


def test_reportes_pdf_publicables_marca_los_desactualizados(tmp_path):
    raiz_reportes = tmp_path / "Reportes"
    (raiz_reportes / "Proyectos").mkdir(parents=True)
    for tag in ("UMAG", "CFLI"):
        (raiz_reportes / "Proyectos" / f"{tag}.pdf").write_bytes(b"%PDF " + tag.encode())

    reportes = bv.reportes_pdf_publicables([{"tag": "UMAG"}, {"tag": "CFLI"}], [], raiz_reportes,
                                           desactualizados={"proyecto:UMAG"})

    assert reportes["proyecto:UMAG"]["desactualizado"] is True
    assert reportes["proyecto:CFLI"]["desactualizado"] is False


def test_build_deja_cada_reporte_cifrado_aparte_y_borra_los_que_sobran(tmp_path, monkeypatch):
    ruta_excel = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ])
    raiz_reportes = tmp_path / "Reportes"
    (raiz_reportes / "Proyectos").mkdir(parents=True)
    pdf = b"%PDF-1.7 reporte de prueba que no debe ir dentro del tablero"
    (raiz_reportes / "Proyectos" / "UMAG.pdf").write_bytes(pdf)
    ruta_build = tmp_path / "build" / "index.html"
    sobrante = tmp_path / "build" / "reportes" / ("0" * 24 + ".json")
    sobrante.parent.mkdir(parents=True)
    sobrante.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bv, "RUTA_EXCEL", ruta_excel)
    monkeypatch.setattr(bv, "RUTA_DATA_JSON", tmp_path / "data" / "analisis-financiero.json")
    monkeypatch.setattr(bv, "RUTA_BUILD_HTML", ruta_build)
    monkeypatch.setattr(bv, "RAIZ_REPORTES", raiz_reportes)

    assert bv.build() == 0

    html = ruta_build.read_text(encoding="utf-8")
    contrasena = bv.candado.leer_contrasena()            # la de prueba (conftest.py raíz)
    datos = bv.candado.leer_datos(html, "af-data-b64", contrasena)
    archivo = datos["reportes_pdf"]["proyecto:UMAG"]["archivo"]
    cifrado = (ruta_build.parent / archivo).read_text(encoding="utf-8")
    assert bv.candado.descifrar_bytes(cifrado, contrasena) == pdf
    assert not sobrante.exists()
    assert _base64.b64encode(pdf).decode("ascii")[:40] not in html
    assert bv.candado.abre_con(html, contrasena, carpeta=ruta_build.parent)


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
    monkeypatch.setattr(bv, "_reportes_desactualizados",
                        lambda: pytest.fail("con un Excel de prueba no se consulta el manifiesto real"))

    data = bv.extraer_datos_saneados(ruta_excel)

    proyecto = data["proyectos"][0]
    assert data["categorias"] == [{
        "categoria": "I+D+i", "n_proyectos": 1,
        "venta_total": proyecto["monto_venta"],
        "margen_estimado_total": proyecto["margen_estimado_cierre"],
        "margen_pct": proyecto["margen_estimado_cierre"] / proyecto["monto_venta"],
        "nota_promedio": proyecto["nota"],
        "tags_proyectos": ["UMAG"],
    }]
    assert data["reportes_pdf"]["proyecto:UMAG"]["archivo"].startswith("reportes/")
    assert data["reportes_pdf"]["proyecto:UMAG"]["desactualizado"] is None


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


def test_snapshot_expone_avance_y_estimacion_al_cierre():
    """Reemplazó a la Nota Parcial (2026-09-21): al 75% de avance con 6,4M
    gastados de 8M, lo que falta (25% de 8M) se estima a precio de
    presupuesto -> 8,4M al cierre; la Nota se calcula sobre eso."""
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 0.75,
        "fecha_inicio": None, "fecha_cierre": None, "categoria": "I+D+i",
        "monto_venta": 10_000_000,
        "materiales_proy": 4_000_000, "equipos_proy": 2_000_000,
        "mo_proy": 1_000_000, "otros_proy": 1_000_000, "mo_real": 800_000,
    }
    reales = {"Materiales": 3_200_000, "Equipos": 1_600_000, "Otros": 800_000}

    kpis = bv.calcular_kpis_proyecto(p, reales)

    assert kpis["avance"] == 0.75
    assert kpis["en_curso"] is True
    assert "nota_parcial" not in kpis
    assert kpis["costo_estimado_cierre"] == 8_400_000
    assert kpis["margen_estimado_cierre"] == 1_600_000
    assert kpis["nota"] == af.calcular_nota(0.16, 8_400_000 / 8_000_000 - 1)
    assert kpis["margen_real"] == 3_600_000  # a la fecha: sigue disponible, no se pierde


def test_snapshot_trae_lo_que_la_ficha_compara_contra_el_presupuesto():
    """Ficha del proyecto (2026-10-05). Al 75 % con 6,4M gastados de 8M y
    venta 10M: el presupuesto dejaba 2M (20 %) y el cierre estimado 1,6M, o
    sea 400.000 menos; al ritmo actual el costo terminaría en 6,4M / 0,75. Los
    puntos de la Nota suman la Nota."""
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": 0.75,
        "fecha_inicio": None, "fecha_cierre": None, "categoria": "I+D+i",
        "monto_venta": 10_000_000,
        "materiales_proy": 4_000_000, "equipos_proy": 2_000_000,
        "mo_proy": 1_000_000, "otros_proy": 1_000_000, "mo_real": 800_000,
    }
    reales = {"Materiales": 3_200_000, "Equipos": 1_600_000, "Otros": 800_000}

    kpis = bv.calcular_kpis_proyecto(p, reales)

    assert kpis["margen_proyectado"] == 2_000_000
    assert kpis["margen_proyectado_pct"] == 0.2
    assert kpis["margen_vs_presupuesto"] == -400_000
    assert kpis["presupuesto_gastado_pct"] == 0.8
    assert round(kpis["costo_cierre_pesimista"]) == round(6_400_000 / 0.75)
    assert kpis["nota_puntos"]["rentabilidad"] + kpis["nota_puntos"]["control"] == kpis["nota"]


def test_snapshot_sin_avance_no_tiene_estimacion_ni_nota():
    p = {
        "tag": "UMAG", "nombre": "UMAG", "cliente": "AGCID", "avance": None,
        "fecha_inicio": None, "fecha_cierre": None, "categoria": "I+D+i",
        "monto_venta": 10_000_000,
        "materiales_proy": 4_000_000, "equipos_proy": 2_000_000,
        "mo_proy": 1_000_000, "otros_proy": 1_000_000, "mo_real": 800_000,
    }
    reales = {"Materiales": 3_200_000, "Equipos": 1_600_000, "Otros": 800_000}

    kpis = bv.calcular_kpis_proyecto(p, reales)

    assert kpis["en_curso"] is False
    assert kpis["costo_estimado_cierre"] is None
    assert kpis["nota"] is None


def test_snapshot_trae_las_alertas_del_proyecto():
    """Al 75% con el 99% del presupuesto gastado: sobrecosto estimado al
    cierre de +24%, sobre el umbral de alerta."""
    p = {
        "tag": "JX", "nombre": "JX", "cliente": "X", "avance": 0.75,
        "fecha_inicio": None, "fecha_cierre": None, "categoria": "Mantenimiento",
        "monto_venta": 160.0, "materiales_proy": 40.0, "equipos_proy": 20.0,
        "mo_proy": 30.0, "otros_proy": 10.0, "mo_real": 30.0,
    }
    kpis = bv.calcular_kpis_proyecto(p, {"Materiales": 50.0, "Equipos": 9.0, "Otros": 10.0})
    assert any("Sobrecosto estimado al cierre" in a for a in kpis["alertas"])


def test_pendientes_traen_las_alertas_de_fechas(tmp_path):
    """Avance 100% con fecha de cierre futura: aunque le falten datos, la
    inconsistencia de fechas se avisa."""
    from datetime import date, timedelta as td
    ruta = _wb_con_proyectos(tmp_path, [{
        "TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache", "Cliente": "Cesfam",
        "% Avance": 1.0, "Fecha de cierre": datetime.combine(date.today() + td(days=400), datetime.min.time()),
        "Mano de Obra Real": None,
    }])
    data = bv.extraer_datos_saneados(ruta)
    assert any("fecha de cierre futura" in a for a in data["pendientes"][0]["alertas"])


def test_build_de_peru_usa_el_mismo_template_con_su_titulo_y_moneda(tmp_path, monkeypatch):
    """Perú no tiene template propio desde 2026-09-21: el mismo build lo
    genera con PAISES_VIZ["PE"]."""
    ruta_excel = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "LIMA", "Nombre del proyecto": "LIMA", "Cliente": "ACME"},
    ])
    cfg = dict(bv.PAISES_VIZ["PE"])
    cfg.update({
        "ruta_excel": ruta_excel,
        "ruta_data_json": tmp_path / "pe" / "data.json",
        "ruta_build_html": tmp_path / "pe" / "index.html",
        "raiz_reportes": tmp_path / "pe" / "Reportes",
    })
    monkeypatch.setitem(bv.PAISES_VIZ, "PE", cfg)

    assert bv.build("PE") == 0
    html = (tmp_path / "pe" / "index.html").read_text(encoding="utf-8")
    assert "<title>Análisis Financiero Perú — Visualizador</title>" in html
    assert 'data-nav-activo="analisis-financiero-peru"' in html
    assert "__AF_" not in html
    data = bv.extraer_datos_saneados(ruta_excel, pais="PE")
    assert data["moneda"] == {"simbolo": "S/", "locale": "es-PE"}
    assert data["pendientes"] == [] and data["proyectos"][0]["tag"] == "LIMA"


def test_template_no_tiene_restos_del_esquema_anterior():
    """El template lee exactamente las claves del snapshot nuevo: ninguna
    referencia a CLTV, Nota Parcial o al margen a la fecha como total."""
    template = bv.RUTA_TEMPLATE.read_text(encoding="utf-8")
    for resto in ("nota_parcial", ".cltv", "margen_real_total", "c.aov", "meses_activo"):
        assert resto not in template, resto
    for marcador in ("__AF_DATA_B64__", "__AF_TITULO__", "__AF_NAV_ACTIVO__"):
        assert marcador in template


# ── Fase 2 de la auditoría (2026-09-21): análisis de cartera en el snapshot ──

def test_snapshot_trae_el_error_de_presupuesto_por_proyecto(tmp_path):
    """El KPI que ve lo que la desviación total esconde: sale de af, no se
    recalcula acá."""
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ])
    data = bv.extraer_datos_saneados(ruta)
    proyecto = data["proyectos"][0]
    assert proyecto["error_presupuesto_pct"] is not None
    assert proyecto["error_presupuesto_pct"] >= abs(proyecto["desviacion_pct"])


def test_snapshot_trae_sesgo_por_categoria_y_concentracion(tmp_path):
    """Los dos análisis de cartera que no son de un proyecto: en qué se
    equivoca el presupuesto y de cuántos clientes depende el ingreso."""
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "A1", "Nombre del proyecto": "A1", "Cliente": "A", "% Avance": 1.0},
        {"TAG proyecto": "B1", "Nombre del proyecto": "B1", "Cliente": "B", "% Avance": 1.0,
         "Monto de Venta (sin IVA)": 3_000_000},
    ])
    data = bv.extraer_datos_saneados(ruta)

    categorias = [s["categoria"] for s in data["presupuesto"]["sesgo_categorias"]]
    assert categorias == ["Materiales", "Equipos", "Mano de Obra", "Otros"]
    assert all(s["n_proyectos"] == 2 for s in data["presupuesto"]["sesgo_categorias"])

    concentracion = data["concentracion"]
    assert concentracion["n_clientes"] == 2
    assert concentracion["top_1"] == 0.75  # 3.000.000 de 4.000.000
    assert [r["cliente"] for r in concentracion["ranking"]] == ["B", "A"]


def test_concentracion_cuenta_tambien_la_venta_de_proyectos_incompletos(tmp_path):
    """La dependencia de un cliente existe aunque su proyecto todavía no
    tenga todos los datos cargados."""
    ruta = _wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "A1", "Nombre del proyecto": "A1", "Cliente": "A"},
        {"TAG proyecto": "B1", "Nombre del proyecto": "B1", "Cliente": "B",
         "Monto de Venta (sin IVA)": 9_000_000, "Mano de Obra Real": None},
    ])
    data = bv.extraer_datos_saneados(ruta)
    assert len(data["proyectos"]) == 1  # B1 no entra al análisis
    assert data["concentracion"]["n_clientes"] == 2  # pero sí a la concentración
    assert data["concentracion"]["top_1"] == 0.9


def test_template_tiene_las_pestanas_y_los_ganchos_de_la_fase_2():
    """El template y el snapshot tienen que hablar el mismo idioma: si se
    renombra una clave en build_visualizador.py y no acá, la pestaña queda
    vacía sin que ningún test lo note."""
    template = bv.RUTA_TEMPLATE.read_text(encoding="utf-8")
    for panel in ("tabResumen", "tabProyectos", "tabPresupuesto", "tabClientes", "tabCategoria"):
        assert 'id="' + panel + '"' in template
    for gancho in ("listaAtencion", "scatterProyectos", "sesgoCategorias", "mapaCalor",
                   "tablaPresupuestoBody", "paretoClientes", "filtroEstado", "filtroCategoria",
                   "filtroCliente", "filtroAtencion"):
        assert 'id="' + gancho + '"' in template, gancho
    for clave in ("error_presupuesto_pct", "sesgo_categorias", "concentracion",
                  "margen_objetivo", "data-orden"):
        assert clave in template, clave


def test_la_ficha_del_proyecto_solo_lee_claves_que_trae_el_snapshot(tmp_path):
    """Ficha del proyecto (2026-10-05): cada «p.clave» y «UMBRALES.clave» que
    lee existe en el snapshot. Una clave que no calza no da error en el
    navegador: deja una cifra en «—» o un gráfico vacío sin que nadie lo note."""
    template = bv.RUTA_TEMPLATE.read_text(encoding="utf-8")
    ficha = template[template.index("// ---------- ficha del proyecto"):
                     template.index("// ---------- filtros y orden de la tabla de Proyectos")]
    data = bv.extraer_datos_saneados(_wb_con_proyectos(tmp_path, [
        {"TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "AGCID"},
    ]))

    leidas = set(re.findall(r"\bp\.([a-z_]+)", ficha))
    assert {"monto_venta", "costo_estimado_cierre", "nota_puntos"} <= leidas  # el corte del template sigue siendo la ficha
    assert leidas <= set(data["proyectos"][0]), sorted(leidas - set(data["proyectos"][0]))
    umbrales = set(re.findall(r"\bUMBRALES\.([a-z_]+)", ficha))
    assert umbrales <= set(data["umbrales"]), sorted(umbrales - set(data["umbrales"]))
