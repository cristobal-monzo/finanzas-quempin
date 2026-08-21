import auditor_centro_costos as acc


def test_configurar_pais_cl_es_el_default_al_importar():
    assert acc.PAIS_ACTUAL == "CL"
    assert acc.TASA_IMPUESTO == 0.19
    assert acc.NOMBRE_IMPUESTO_CORTO == "IVA"
    assert acc.MONEDA == "CLP"
    assert acc.SIMBOLO_MONEDA == "$"
    assert acc.PREFIJOS_PROYECTO["UMAG"] == "UMAG"
    assert acc.RAIZ_DOCS.name == "Chile"
    assert acc.RUTA_EXCEL.name == "Centro de Costos.xlsx"
    assert acc.MONEY_FORMAT == '"$"#,##0'
    assert acc.ENCABEZADOS_MASTER[10] == "Total sin IVA (CLP)"
    assert acc.ENCABEZADOS_MASTER[11] == "IVA 19% (CLP)"
    assert acc.ENCABEZADOS_DETALLE[8] == "P. Unitario sin IVA"
    assert acc.RAZON_SOCIAL == "QUEMPIN SpA"


def test_configurar_pais_pe_cambia_moneda_impuesto_y_rutas():
    acc.configurar_pais("PE")
    try:
        assert acc.PAIS_ACTUAL == "PE"
        assert acc.TASA_IMPUESTO == 0.18
        assert acc.NOMBRE_IMPUESTO_CORTO == "IGV"
        assert acc.MONEDA == "PEN"
        assert acc.SIMBOLO_MONEDA == "S/"
        assert acc.PREFIJOS_PROYECTO == {}
        assert acc.RAIZ_DOCS.name == "Perú"
        assert acc.RUTA_EXCEL.name == "Centro de Costos Perú.xlsx"
        assert acc.RUTA_EXCEL_SITIO_COMUNICACION is None
        assert acc.MONEY_FORMAT == '"S/"#,##0'
        assert acc.ENCABEZADOS_MASTER[10] == "Total sin IGV (PEN)"
        assert acc.ENCABEZADOS_MASTER[11] == "IGV 18% (PEN)"
        assert acc.ENCABEZADOS_DETALLE[8] == "P. Unitario sin IGV"
        assert acc.RAZON_SOCIAL == "QUEMPIN SAC"
    finally:
        acc.configurar_pais("CL")


def test_configurar_pais_pais_desconocido_lanza_value_error():
    try:
        acc.configurar_pais("AR")
        assert False, "debia lanzar ValueError"
    except ValueError as e:
        assert "AR" in str(e)
    assert acc.PAIS_ACTUAL == "CL"  # no quedo a medio configurar
