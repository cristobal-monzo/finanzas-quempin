from unittest.mock import patch

import auditor_centro_costos as acc


def test_devuelve_false_y_no_lanza_si_no_existe_el_script_de_analisis_financiero(monkeypatch, tmp_path):
    ruta_falsa = tmp_path / "no existe" / "analisis_financiero.py"
    monkeypatch.setattr(acc, "RAIZ_ANALISIS_FINANCIERO", ruta_falsa.parent)

    resultado = acc.actualizar_analisis_financiero()

    assert resultado is False


def test_actualizar_analisis_financiero_avisa_reportes_pendientes(capsys):
    with patch.object(acc, "_reportes_pendientes_tras_run", return_value=["proyecto:UMAG"]):
        acc._avisar_reportes_pendientes()
    salida = capsys.readouterr().out
    assert "proyecto:UMAG" in salida
    assert "Reportes_Analisis_Financiero" in salida


def test_actualizar_analisis_financiero_no_avisa_si_no_hay_pendientes(capsys):
    with patch.object(acc, "_reportes_pendientes_tras_run", return_value=[]):
        acc._avisar_reportes_pendientes()
    salida = capsys.readouterr().out
    assert salida == ""
