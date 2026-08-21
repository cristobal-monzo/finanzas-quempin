import auditor_centro_costos as acc


def _doc(tipo_documento, iva, items, **extra):
    d = {"archivo": "IMG_1.jpg", "n_documento": "123",
         "tipo_documento": tipo_documento, "iva": iva, "items": items}
    d.update(extra)
    return d


def test_verificar_aritmetica_usa_18_por_ciento_para_pe():
    acc.configurar_pais("PE")
    try:
        # 100000 * 0.18 = 18000 -- correcto para Peru, pero NO para el 19% de Chile.
        doc = _doc("Factura", iva=18000, items=[{"cantidad": 1, "p_unitario_sin_iva": 100000}])
        assert acc.verificar_aritmetica([doc]) == []

        doc_mal = _doc("Factura", iva=19000, items=[{"cantidad": 1, "p_unitario_sin_iva": 100000}])
        inconsistencias = acc.verificar_aritmetica([doc_mal])
        assert len(inconsistencias) == 1
        assert inconsistencias[0]["iva_esperado"] == 18000
    finally:
        acc.configurar_pais("CL")


def test_calcular_iva_documento_usa_tasa_activa():
    acc.configurar_pais("PE")
    try:
        dato = {"tipo_documento": "Factura"}
        assert acc.calcular_iva_documento(dato, 100000) == 18000
    finally:
        acc.configurar_pais("CL")


def test_calcular_iva_documento_sigue_dando_19_por_ciento_para_cl():
    dato = {"tipo_documento": "Factura"}
    assert acc.calcular_iva_documento(dato, 100000) == 19000
