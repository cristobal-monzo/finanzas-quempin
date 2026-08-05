import auditor_centro_costos as acc


def _doc(tipo_documento, iva, items, **extra):
    d = {
        "archivo": "IMG_1.jpg", "n_documento": "123",
        "tipo_documento": tipo_documento, "iva": iva, "items": items,
    }
    d.update(extra)
    return d


def test_flags_iva_distinto_del_19_por_ciento_del_neto():
    doc = _doc("Factura", iva=1000, items=[{"cantidad": 1, "p_unitario_sin_iva": 100000}])

    inconsistencias = acc.verificar_aritmetica([doc])

    assert len(inconsistencias) == 1
    assert inconsistencias[0]["neto"] == 100000
    assert inconsistencias[0]["iva"] == 1000
    assert inconsistencias[0]["iva_esperado"] == 19000


def test_no_flags_iva_correcto_al_19_por_ciento():
    doc = _doc("Factura", iva=19000, items=[{"cantidad": 1, "p_unitario_sin_iva": 100000}])
    assert acc.verificar_aritmetica([doc]) == []


def test_tolera_diferencia_de_redondeo_de_1_clp():
    # 100003 * 0.19 = 19000.57 -> round() = 19001; iva=19000 difiere en 1.
    doc = _doc("Factura", iva=19000, items=[{"cantidad": 1, "p_unitario_sin_iva": 100003}])
    assert acc.verificar_aritmetica([doc]) == []


def test_ignora_documentos_sin_iva_explicito_en_el_json():
    doc = _doc("Factura", iva=None, items=[{"cantidad": 1, "p_unitario_sin_iva": 100000}])
    assert acc.verificar_aritmetica([doc]) == []


def test_ignora_tipos_de_documento_que_no_son_factura_ni_guia_despacho():
    doc = _doc("Boleta", iva=0, items=[{"cantidad": 1, "p_unitario_sin_iva": 100000}])
    assert acc.verificar_aritmetica([doc]) == []


def test_guia_de_despacho_tambien_se_verifica():
    doc = _doc("Guía de Despacho", iva=1000, items=[{"cantidad": 1, "p_unitario_sin_iva": 100000}])
    assert len(acc.verificar_aritmetica([doc])) == 1


def test_suma_items_multiples_para_el_neto():
    doc = _doc(
        "Factura", iva=1000,
        items=[
            {"cantidad": 2, "p_unitario_sin_iva": 30000},
            {"cantidad": 1, "p_unitario_sin_iva": 40000},
        ],
    )
    inconsistencias = acc.verificar_aritmetica([doc])
    assert inconsistencias[0]["neto"] == 100000  # 2*30000 + 1*40000
