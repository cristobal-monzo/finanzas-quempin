import analisis_financiero as af


def test_deriva_cliente_cortando_en_el_primer_parentesis():
    assert af.derivar_cliente("AGCID (I) FEBRERO") == "AGCID"


def test_deriva_cliente_con_flecha_de_fechas_tambien_corta_en_el_parentesis():
    assert af.derivar_cliente("HOSPITAL TALCA (I) MAYO--> MAYO Y DICIEMBRE") == "HOSPITAL TALCA"


def test_deriva_cliente_sin_parentesis_devuelve_nombre_completo():
    assert af.derivar_cliente("UMAG") == "UMAG"


def test_normalizar_texto_quita_tildes_mayusculas_y_espacios_extra():
    assert af.normalizar_texto("  Hospital  Talca ") == "HOSPITAL TALCA"
    assert af.normalizar_texto("Peñalolén") == "PENALOLEN"


def test_emparejar_cliente_coincidencia_exacta_tras_normalizar():
    resultado = af.emparejar_cliente("hospital talca", ["Hospital Talca"])
    assert resultado == {"cliente": "Hospital Talca", "estado": "exacto", "similitud": 1.0}


def test_emparejar_cliente_similar_no_exacto_queda_pendiente():
    # Similitud verificada en brainstorming: SequenceMatcher da 0.667, sobre
    # el umbral 0.6.
    resultado = af.emparejar_cliente("AGCID FEBRERO", ["AGCID MARZO"])
    assert resultado["cliente"] == "AGCID MARZO"
    assert resultado["estado"] == "pendiente"
    assert resultado["similitud"] >= af.UMBRAL_SIMILITUD_CLIENTE


def test_emparejar_cliente_sin_parecido_es_nuevo():
    resultado = af.emparejar_cliente(
        "Bombas de Calor Puerto Montt", ["AGCID", "Hospital Talca"]
    )
    assert resultado == {
        "cliente": "Bombas de Calor Puerto Montt",
        "estado": "nuevo",
        "similitud": 0.0,
    }


def test_emparejar_cliente_sin_existentes_es_siempre_nuevo():
    resultado = af.emparejar_cliente("Cualquier Cliente", [])
    assert resultado["estado"] == "nuevo"
