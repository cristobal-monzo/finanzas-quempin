import pytest

import graficos


def test_grafico_barras_svg_produce_una_barra_por_valor():
    svg = graficos.grafico_barras_svg(["UMAG", "CFLI"], [100000, 50000])
    assert svg.count("<rect") == 2
    assert svg.startswith("<svg")


def test_grafico_barras_svg_valida_longitudes_distintas():
    with pytest.raises(ValueError):
        graficos.grafico_barras_svg(["UMAG"], [100000, 50000])


def test_grafico_barras_svg_valida_lista_vacia():
    with pytest.raises(ValueError):
        graficos.grafico_barras_svg([], [])


def test_grafico_dona_svg_produce_un_segmento_por_valor():
    svg = graficos.grafico_dona_svg(["Materiales", "Equipos", "Otros"], [50, 30, 20])
    assert svg.count("<path") == 3
    assert svg.startswith("<svg")


def test_grafico_dona_svg_valida_suma_cero():
    with pytest.raises(ValueError):
        graficos.grafico_dona_svg(["A", "B"], [0, 0])


def test_grafico_dona_svg_segmento_unico_dibuja_circulo():
    # Un solo segmento (~100% del total) no puede ser un arco degenerado:
    # debe renderizarse como un circulo visible, no como una linea invisible.
    svg = graficos.grafico_dona_svg(["Materiales"], [100])
    assert svg.count("<circle") == 2  # 1 del segmento + 1 del hueco central
    assert svg.count("<path") == 0


def test_grafico_dona_svg_segmento_dominante_dibuja_circulo():
    # Un segmento que redondea a ~100% (el resto es despreciable) tambien
    # se dibuja como circulo: 1 del dominante + 1 del hueco central.
    svg = graficos.grafico_dona_svg(["A", "B"], [99.999999, 0.000001])
    assert svg.count("<circle") == 2


def test_grafico_barras_svg_acepta_color_por_barra():
    svg = graficos.grafico_barras_svg(
        ["Materiales", "MO"], [100, 50], colores=["#ff5100", "#54565a"]
    )
    assert 'fill="#ff5100"' in svg
    assert 'fill="#54565a"' in svg


def test_grafico_barras_svg_valida_largo_de_colores():
    with pytest.raises(ValueError):
        graficos.grafico_barras_svg(["A", "B"], [1, 2], colores=["#ff5100"])


def test_grafico_barras_svg_acepta_opacidad_por_barra():
    svg = graficos.grafico_barras_svg(
        ["Proyectado", "Real"], [100, 50], opacidades=[0.4, 1]
    )
    assert 'fill-opacity="0.4"' in svg
    assert 'fill-opacity="1"' in svg


def test_grafico_barras_svg_valida_largo_de_opacidades():
    with pytest.raises(ValueError):
        graficos.grafico_barras_svg(["A", "B"], [1, 2], opacidades=[0.5])


def test_leyenda_html_produce_un_item_por_etiqueta():
    html = graficos.leyenda_html(["Materiales", "Equipos"], ["#ff5100", "#54565a"])
    assert html.count("leyenda-item") == 2
    assert "#ff5100" in html and "#54565a" in html


def test_leyenda_html_valida_lista_vacia():
    with pytest.raises(ValueError):
        graficos.leyenda_html([])


def test_grafico_dona_svg_con_porcentaje_agrega_texto_por_segmento_grande():
    svg = graficos.grafico_dona_svg(
        ["Materiales", "Otros"], [90, 10], mostrar_porcentaje=True
    )
    assert "90%" in svg
    # El segmento de 10% (justo bajo el umbral de 6%... en este caso 10%>=6%
    # tambien se muestra) -- ambos etiquetados.
    assert "10%" in svg


def test_grafico_dona_svg_sin_porcentaje_no_agrega_texto():
    svg = graficos.grafico_dona_svg(["A", "B"], [50, 50])
    assert "<text" not in svg


def test_grafico_dona_svg_segmento_muy_chico_no_muestra_porcentaje():
    svg = graficos.grafico_dona_svg(
        ["Grande", "Chico"], [99, 1], mostrar_porcentaje=True
    )
    assert svg.count("<text") == 1
