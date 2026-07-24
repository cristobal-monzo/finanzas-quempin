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
