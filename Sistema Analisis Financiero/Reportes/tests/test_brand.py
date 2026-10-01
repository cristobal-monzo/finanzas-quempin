import brand


def test_cargar_font_face_lato_trae_las_3_variantes():
    css = brand.cargar_font_face_lato()
    assert css.count("@font-face") == 3
    assert "font-family: 'Lato'" in css


def test_cargar_logo_base64_es_un_data_uri_png():
    logo = brand.cargar_logo_base64()
    assert logo.startswith("data:image/png;base64,")
    assert len(logo) > 1000


def test_construir_html_incluye_titulo_logo_y_contenido():
    html = brand.construir_html(
        titulo="Reporte UMAG",
        generado_el="21/07/2026",
        contenido_html="<p>contenido de prueba</p>",
    )
    assert html.startswith("<!doctype html>")
    assert "Reporte UMAG" in html
    assert "data:image/png;base64," in html
    assert "<p>contenido de prueba</p>" in html
    assert "@font-face" in html
    assert "#ff5100" in html


def test_css_base_reporte_define_salto_de_pagina_para_pdf_pagina():
    assert ".pdf-pagina { page-break-after: always; }" in brand.CSS_BASE_REPORTE
    assert ".pdf-pagina:last-child { page-break-after: auto; }" in brand.CSS_BASE_REPORTE


def test_encabezado_html_incluye_logo_titulo_y_fecha():
    html = brand.encabezado_html(titulo="Reporte UMAG", generado_el="24/07/2026")
    assert "data:image/png;base64," in html
    assert "Reporte UMAG" in html
    assert "24/07/2026" in html
    assert "reporte-header--pagina" in html


def test_construir_html_sin_fecha_corte_no_agrega_nota_de_fuente():
    html = brand.construir_html(
        titulo="Reporte UMAG", generado_el="24/07/2026", contenido_html="<p></p>",
    )
    assert "Fuente: Centro de Costos" not in html


def test_construir_html_con_fecha_corte_agrega_nota_de_fuente_al_footer():
    html = brand.construir_html(
        titulo="Reporte UMAG", generado_el="24/07/2026", contenido_html="<p></p>",
        fecha_corte="23/07/2026",
    )
    assert "Datos al 23/07/2026" in html
    assert "Fuente: Centro de Costos + registro manual" in html


def test_estado_kpi_margen_verde_sobre_el_objetivo_ambar_bajo_y_rojo_negativo():
    # El criterio anterior (es_kpi_fuera_de_rango) marcaba 60% de margen
    # igual que un sobrecosto: el color no distinguia la buena noticia de la
    # mala. Un margen alto por costos sin registrar lo avisa una alerta
    # explicita, no un color raro.
    assert brand.estado_kpi("Margen neto %", 0.60) == "bueno"
    assert brand.estado_kpi("Margen neto %", 0.30) == "bueno"
    assert brand.estado_kpi("Margen neto %", 0.10) == "medio"
    assert brand.estado_kpi("Margen neto %", -0.05) == "malo"


def test_estado_kpi_desviacion_solo_es_roja_cuando_es_sobrecosto():
    assert brand.estado_kpi("Desviación % Materiales", 0.40) == "malo"
    assert brand.estado_kpi("Desviación % Materiales", -0.744) == "medio"
    assert brand.estado_kpi("Desviación % Materiales", 0.05) == ""


def test_estado_kpi_nota_y_evaluacion_usan_los_cortes_de_analisis_financiero():
    assert brand.estado_kpi("Nota del Proyecto", 93) == "bueno"
    assert brand.estado_kpi("Nota del Proyecto", 60) == "medio"
    assert brand.estado_kpi("Nota del Proyecto", 20) == "malo"
    assert brand.estado_kpi("Evaluación", "Requiere atención") == "malo"


def test_estado_kpi_kpi_sin_umbral_definido_o_sin_valor_no_pinta_nada():
    assert brand.estado_kpi("Estructura % Materiales", 999) == ""
    assert brand.estado_kpi("Margen neto %", None) == ""


def test_estado_kpi_ahorro_sobrecosto_negativo_es_sobrecosto():
    assert brand.estado_kpi("Ahorro/Sobrecosto Materiales", -50000) == "malo"
    assert brand.estado_kpi("Ahorro/Sobrecosto Materiales", 50000) == ""
    assert brand.estado_kpi("Ahorro/Sobrecosto Total", -1) == "malo"


def test_formatear_kpi_distingue_pesos_de_porcentaje_por_el_nombre():
    # "Margen estimado al cierre" y "Margen estimado al cierre %" empiezan
    # igual: el "%" manda sobre la lista de KPIs en pesos.
    assert brand.formatear_kpi("Margen estimado al cierre", 1293765) == "$1.293.765"
    assert brand.formatear_kpi("Margen estimado al cierre %", 0.614) == "61,4%"
    assert brand.formatear_kpi("Nota del Proyecto", 93) == "93/100"
    assert brand.formatear_kpi("Evaluación", "Excelente") == "Excelente"
    assert brand.formatear_kpi("Margen neto %", None) == "—"


def test_referencia_kpi_devuelve_texto_para_kpi_conocido_y_vacio_para_desconocido():
    assert "25%" in brand.referencia_kpi("Margen neto %")
    assert brand.referencia_kpi("Estructura % Materiales") == ""


def test_referencia_kpi_ahorro_sobrecosto_y_desviacion_total():
    assert "positivo" in brand.referencia_kpi("Ahorro/Sobrecosto Total")
    assert "0%" in brand.referencia_kpi("Desviación % Total")
