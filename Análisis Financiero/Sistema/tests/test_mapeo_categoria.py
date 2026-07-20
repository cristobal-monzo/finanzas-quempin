import analisis_financiero as af


def test_materiales_mapea_a_materiales():
    assert af.mapear_categoria_a_bucket("Materiales") == ("Materiales", True)


def test_consumibles_mapea_a_materiales():
    assert af.mapear_categoria_a_bucket("Consumibles") == ("Materiales", True)


def test_equipos_herramientas_mapea_a_equipos():
    assert af.mapear_categoria_a_bucket("Equipos-Herramientas") == ("Equipos", True)


def test_categoria_no_mapeada_cae_a_otros_sin_mapeo_explicito():
    assert af.mapear_categoria_a_bucket("Combustible") == ("Otros", False)


def test_categoria_none_cae_a_otros_sin_mapeo_explicito():
    assert af.mapear_categoria_a_bucket(None) == ("Otros", False)
