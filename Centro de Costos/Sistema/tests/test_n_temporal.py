"""N° temporal de proyecto sin N° de la Planilla (2026-11-09): «001t. Nombre» → TAG «001t»."""
import auditor_centro_costos as acc


def test_n_de_nombre_carpeta():
    assert acc._n_de_nombre_carpeta("001t. Hospital San José") == "001t"
    assert acc._n_de_nombre_carpeta("001T-Algo") == "001t"
    assert acc._n_de_nombre_carpeta("036. Fiscalía") == "36"
    assert acc._n_de_nombre_carpeta("Cesfam Limache") is None


def test_normalizar_nombre_quita_el_n_temporal():
    assert acc.normalizar_nombre_proyecto("001t. Hospital San José") == "Hospital San José"
    assert acc.normalizar_nombre_proyecto("259. FACH 2") == "FACH2"
