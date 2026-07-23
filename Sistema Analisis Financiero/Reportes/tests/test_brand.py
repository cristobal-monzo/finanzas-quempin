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
