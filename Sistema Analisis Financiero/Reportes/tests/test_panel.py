# -*- coding: utf-8 -*-
from datetime import date

import kpis_recalculados as kr
import panel


def _fila_proyecto(**overrides) -> dict:
    base = {
        "TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG",
        "Cliente": "Universidad de Magallanes", "Categoría": "I+D+i",
        "% Avance": 1.0, "Fecha de inicio": date(2026, 1, 10),
        "Fecha de cierre": date(2026, 2, 1), "Monto de Venta (sin IVA)": 1000000,
        "Costos Materiales Proyectados": 100000, "Costos Equipos Proyectados": 100000,
        "Mano de Obra Proyectada": 100000, "Otros Costos Proyectados": 100000,
        "Mano de Obra Real": 90000,
    }
    base.update(overrides)
    return base


def _paquete_proyecto(**overrides) -> dict:
    fila = _fila_proyecto(**overrides)
    proyecto, indicadores = kr.recalcular_proyecto(
        fila, {"Materiales": 60000, "Equipos": 70000, "Otros": 20000},
    )
    return {
        "tipo": "proyecto", "tag": fila["TAG proyecto"], "proyecto": proyecto,
        "indicadores": indicadores, "en_desarrollo": False, "alertas": [],
        "_contexto": {},
    }


def test_los_bloques_cubren_exactamente_los_indicadores_del_playbook():
    """El estandar de la pagina 1 es "todos los KPIs de la entidad, sin
    seleccion editorial". Si manana se agrega un KPI a HEADERS_INDICADORES y
    nadie lo suma a un bloque, este test falla en vez de dejarlo fuera del
    PDF en silencio (que es lo que paso con los 2 KPIs de 2026-07-28)."""
    _, indicadores = kr.recalcular_proyecto(_fila_proyecto(), {})
    en_bloques = [nombre for _, _, nombres in panel.BLOQUES_INDICADORES for nombre in nombres]

    assert len(en_bloques) == len(set(en_bloques)), "hay un KPI repetido en dos bloques"
    assert set(en_bloques) == set(indicadores)


def test_panel_de_proyecto_trae_ficha_tarjetas_y_la_tabla_completa():
    html = panel.panel(_paquete_proyecto())
    assert html.startswith(panel.APERTURA_PAGINA_1)
    assert "Universidad de Magallanes" in html
    assert "93/100" in html or "96/100" in html  # Nota, formateada por brand
    for _, titulo, _ in panel.BLOQUES_INDICADORES:
        assert titulo in html
    assert "Margen al cierre % (escenario índice de costo)" in html


def test_panel_de_proyecto_en_desarrollo_lleva_el_indicador_visual():
    paquete = _paquete_proyecto()
    paquete["en_desarrollo"] = True
    assert "EN DESARROLLO" in panel.panel(paquete)
    paquete["en_desarrollo"] = False
    assert "EN DESARROLLO" not in panel.panel(paquete)


def test_panel_muestra_las_alertas_del_proyecto():
    paquete = _paquete_proyecto()
    paquete["alertas"] = ["Terminado con un costo real de solo 72,9 % del presupuesto"]
    html = panel.panel(paquete)
    assert "Alertas de datos y de presupuesto" in html
    assert "72,9 %" in html
    # Sin alertas no se dibuja la caja: ese alto lo necesita la tabla.
    paquete["alertas"] = []
    assert "Alertas de datos" not in panel.panel(paquete)


def test_panel_escapa_el_texto_que_viene_del_excel():
    html = panel.panel(_paquete_proyecto(**{"Nombre del proyecto": 'Torre <b>"A"</b> & B'}))
    assert "<b>" not in html.split('<div class="ficha">')[1].split("</h2>")[0]
    assert "&amp; B" in html


def test_panel_rechaza_la_comparacion_adhoc():
    # La comparacion ad-hoc no tiene layout de 2 paginas definido (spec §10).
    try:
        panel.panel({"tipo": "comparacion", "entidades": []})
    except ValueError as error:
        assert "comparacion" in str(error).lower()
    else:
        raise AssertionError("se esperaba ValueError")


def test_indicadores_agregados_ponderan_por_venta_y_no_promedian_kpis():
    """Un proyecto de $200.000 no pesa lo mismo que uno de $14 millones: el
    margen del conjunto es la razon de las sumas, no el promedio de los dos
    margenes (que daria 30%)."""
    proyectos = [
        {"Monto de Venta (sin IVA)": 100000, "Costos Materiales Proyectados": 10000,
         "Costos Materiales Reales": 50000, "Costos Equipos Proyectados": 0,
         "Costos Equipos Reales": 0, "Mano de Obra Proyectada": 0, "Mano de Obra Real": 0,
         "Otros Costos Proyectados": 0, "Otros Costos Reales": 0},
        {"Monto de Venta (sin IVA)": 900000, "Costos Materiales Proyectados": 90000,
         "Costos Materiales Reales": 90000, "Costos Equipos Proyectados": 0,
         "Costos Equipos Reales": 0, "Mano de Obra Proyectada": 0, "Mano de Obra Real": 0,
         "Otros Costos Proyectados": 0, "Otros Costos Reales": 0},
    ]
    indicadores = panel._indicadores_agregados(proyectos, venta=1000000, margen=860000)
    assert indicadores["Margen neto %"] == (1000000 - 140000) / 1000000
    assert indicadores["Desviación % Materiales"] == 140000 / 100000 - 1


def test_fecha_corte_toma_el_cierre_mas_reciente_y_none_si_no_hay():
    paquete = {"tipo": "categoria", "categoria": "I+D+i", "proyectos": [
        {"Fecha de cierre": date(2026, 2, 1)}, {"Fecha de cierre": date(2026, 5, 20)},
        {"Fecha de cierre": None},
    ]}
    assert panel.fecha_corte(paquete) == "20-05-2026"
    assert panel.fecha_corte({"tipo": "categoria", "proyectos": [{"Fecha de cierre": None}]}) is None


def test_fecha_corte_ignora_los_cierres_futuros():
    """Un cierre futuro es un proyecto en desarrollo (misma regla que
    datos_reportes.proyecto_esta_en_desarrollo), no una fecha de corte: el
    reporte de HPIN (2026-09-24) salio con "Datos al 03-03-2027"."""
    hoy = date(2026, 9, 24)
    futuro = {"tipo": "proyecto", "tag": "HPIN", "proyecto": {"Fecha de cierre": date(2027, 3, 3)}}
    assert panel.fecha_corte(futuro, hoy=hoy) is None
    mixto = {"tipo": "categoria", "proyectos": [
        {"Fecha de cierre": date(2026, 5, 20)}, {"Fecha de cierre": date(2027, 3, 3)},
    ]}
    assert panel.fecha_corte(mixto, hoy=hoy) == "20-05-2026"


def test_la_pagina_1_cabe_en_una_hoja_aunque_traiga_muchas_alertas(tmp_path):
    """HPIN (2026-09-24) salio en 3 paginas: la pagina 1 no tenia margen para
    su contenido variable -- 2 alertas y chips que saltaron de linea la
    pasaron por 3 px, y la tabla de indicadores se fue sola a una hoja
    aparte. Caso extremo a proposito: 6 alertas y nombres largos."""
    import motor_reportes
    from pypdf import PdfReader

    paquete = _paquete_proyecto(**{
        "Nombre del proyecto": "Putaendo Hospital Pinel",
        "Cliente": "Putaendo Hospital Pinel", "Categoría": "Montaje e instalación",
    })
    paquete["en_desarrollo"] = True
    paquete["_contexto"] = {"margen_mediano": 0.456, "peso_cartera": {"UMAG": 0.118}}
    paquete["alertas"] = [
        "% Avance fuera de rango (120,0 %): la estimación al cierre usa 100,0 %.",
        "Avance 100 % pero con fecha de cierre futura (03-03-2027): revisar cuál de los dos está desactualizado.",
        "Terminado con sobrecosto de +27,6 % sobre el presupuesto.",
        "Materiales tiene gasto real pero presupuesto 0: su desviación no se puede medir.",
        "Equipos tiene gasto real pero presupuesto 0: su desviación no se puede medir.",
        "Otros tiene gasto real pero presupuesto 0: su desviación no se puede medir.",
    ]
    destino = tmp_path / "reporte.pdf"
    motor_reportes.renderizar_pdf(panel.documento(paquete, "<p>análisis</p>", "24-09-2026"), destino)

    assert len(PdfReader(str(destino)).pages) == 2


def test_pagina_analisis_repite_el_encabezado_con_marca():
    html = panel.pagina_analisis("Proyecto UMAG", "24-09-2026", "<p>análisis</p>")
    assert '<div class="pdf-pagina p2">' in html
    assert "reporte-header--pagina" in html
    assert "<p>análisis</p>" in html


def test_documento_arma_las_2_paginas_dentro_de_la_marca():
    html = panel.documento(_paquete_proyecto(), "<p>análisis</p>", "24-09-2026")
    assert html.startswith("<!doctype html>")
    assert html.count('class="pdf-pagina') == 2
    assert "Datos al 01-02-2026" in html  # fecha_corte del proyecto
