import analisis_financiero as af


def test_materiales_mapea_a_materiales():
    assert af.mapear_categoria_a_bucket("Materiales") == ("Materiales", True)


def test_consumibles_mapea_a_materiales():
    assert af.mapear_categoria_a_bucket("Consumibles") == ("Materiales", True)


def test_equipos_herramientas_mapea_a_equipos():
    assert af.mapear_categoria_a_bucket("Equipos-Herramientas") == ("Equipos", True)


def test_categoria_no_mapeada_cae_a_otros_sin_mapeo_explicito():
    """Una subcategoría que Centro de Costos invente mañana cae en "Otros"
    pero avisa (es_mapeo_explicito=False) para que alguien decida dónde va."""
    assert af.mapear_categoria_a_bucket("Capacitación") == ("Otros", False)


def test_ferreteria_y_reposicion_de_material_mapean_a_materiales():
    """Auditoría 2026-09-21, fase 1 (decisión del usuario): Ferretería es casi
    todo material de obra (válvulas, cañerías, fittings); caía en "Otros" y la
    desviación de Materiales comparaba contra un real incompleto."""
    assert af.mapear_categoria_a_bucket("Ferretería") == ("Materiales", True)
    assert af.mapear_categoria_a_bucket("Reposición de Material") == ("Materiales", True)


def test_arriendo_y_herramientas_mapean_a_equipos():
    """Arriendo es casi todo arriendo de camiones, vehículos y andamios;
    Herramientas es Equipos-Herramientas escrito distinto."""
    assert af.mapear_categoria_a_bucket("Arriendo") == ("Equipos", True)
    assert af.mapear_categoria_a_bucket("Herramientas") == ("Equipos", True)


def test_servicios_queda_en_otros_explicitamente():
    """Servicios incluye mano de obra subcontratada, pero se deja en "Otros" a
    propósito: 'Mano de Obra Real' es manual y podría ya incluirla (se
    contaría dos veces). Explícito, para que no avise en cada corrida."""
    assert af.mapear_categoria_a_bucket("Servicios") == ("Otros", True)


def test_gastos_indirectos_conocidos_van_a_otros_sin_avisar():
    for sub in ("Combustible", "Transporte", "Alimentación", "Viáticos/Alojamiento",
                "Despachos", "Seguridad Industrial", "Oficina", "Descuento"):
        assert af.mapear_categoria_a_bucket(sub) == ("Otros", True), sub


def test_categoria_none_cae_a_otros_sin_mapeo_explicito():
    assert af.mapear_categoria_a_bucket(None) == ("Otros", False)
