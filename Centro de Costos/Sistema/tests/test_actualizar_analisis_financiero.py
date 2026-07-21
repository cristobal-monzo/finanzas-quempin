import auditor_centro_costos as acc


def test_devuelve_false_y_no_lanza_si_no_existe_el_script_de_analisis_financiero(monkeypatch, tmp_path):
    ruta_falsa = tmp_path / "no existe" / "analisis_financiero.py"
    monkeypatch.setattr(acc, "RAIZ_ANALISIS_FINANCIERO", ruta_falsa.parent)

    resultado = acc.actualizar_analisis_financiero()

    assert resultado is False
