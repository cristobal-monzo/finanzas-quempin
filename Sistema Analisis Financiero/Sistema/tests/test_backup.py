from datetime import datetime

import openpyxl

import analisis_financiero as af


def test_hacer_backup_devuelve_none_si_el_archivo_no_existe(tmp_path):
    ruta = tmp_path / "no existe.xlsx"
    assert af.hacer_backup(ruta, tmp_path / "Respaldos") is None


def test_hacer_backup_copia_el_archivo_a_una_subcarpeta_del_mes(tmp_path):
    ruta_excel = tmp_path / "Análisis de Proyectos.xlsx"
    openpyxl.Workbook().save(ruta_excel)
    raiz_respaldos = tmp_path / "Respaldos"

    destino = af.hacer_backup(ruta_excel, raiz_respaldos)

    assert destino is not None
    assert destino.exists()
    ahora = datetime.now()
    assert destino.parent.name == f"{af.MESES_ES[ahora.month]} {ahora.year}"
    assert destino.name.startswith("Análisis de Proyectos - backup ")
    assert destino.suffix == ".xlsx"
