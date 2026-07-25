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


def test_es_kpi_fuera_de_rango_margen_neto_muy_por_sobre_objetivo():
    assert brand.es_kpi_fuera_de_rango("Margen neto %", 0.60) is True
    assert brand.es_kpi_fuera_de_rango("Margen neto %", 0.30) is False


def test_es_kpi_fuera_de_rango_desviacion_grande_en_cualquier_sentido():
    assert brand.es_kpi_fuera_de_rango("Desviación % Materiales", -0.744) is True
    assert brand.es_kpi_fuera_de_rango("Desviación % Materiales", 0.05) is False


def test_es_kpi_fuera_de_rango_kpi_sin_umbral_definido_da_false():
    assert brand.es_kpi_fuera_de_rango("Productividad Materiales", 999) is False


def test_referencia_kpi_devuelve_texto_para_kpi_conocido_y_vacio_para_desconocido():
    assert "25%" in brand.referencia_kpi("Margen neto %")
    assert brand.referencia_kpi("Productividad Materiales") == ""
