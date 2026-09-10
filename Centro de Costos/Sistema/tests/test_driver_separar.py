import importlib.util
import sys
from pathlib import Path

import auditor_centro_costos as acc

_DRIVER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".claude" / "skills" / "Registro_Centro_de_Costos" / "driver.py"
)
_spec = importlib.util.spec_from_file_location("driver_bajo_prueba_separar", _DRIVER_PATH)
driver = importlib.util.module_from_spec(_spec)
sys.modules["driver_bajo_prueba_separar"] = driver
_spec.loader.exec_module(driver)


def test_extraer_flag_encuentra_valor_y_lo_saca_de_argv():
    valor, resto = driver._extraer_flag(["--proyecto", "UMAG", "--archivo", "a.jpg"], "--proyecto")
    assert valor == "UMAG"
    assert resto == ["--archivo", "a.jpg"]


def test_extraer_flag_falla_si_no_esta_el_flag():
    import pytest

    with pytest.raises(ValueError):
        driver._extraer_flag(["--archivo", "a.jpg"], "--proyecto")


def test_cmd_separar_crea_copias_y_reporta_nombres(tmp_path, monkeypatch, capsys):
    # cmd_separar() llama acc.configurar_pais("CL") como primera linea, que
    # PISA cualquier monkeypatch.setattr(acc, "RAIZ_DOCS", ...) hecho antes de
    # la llamada -- hay que parchear el diccionario PAISES["CL"] en vez de los
    # globals (mismo gotcha que test_cmd_status_con_pais_pe_usa_rutas_de_peru
    # en test_driver_pais_arg.py).
    raiz_docs = tmp_path / "docs"
    carpeta = raiz_docs / "UMAG"
    carpeta.mkdir(parents=True)
    (carpeta / "IMG_1234.jpg").write_bytes(b"contenido")
    cl_cfg = dict(acc.PAISES["CL"])
    cl_cfg["ruta_docs"] = raiz_docs
    cl_cfg["ruta_backups"] = tmp_path / "backups"
    monkeypatch.setitem(acc.PAISES, "CL", cl_cfg)

    codigo = driver.cmd_separar(["--proyecto", "UMAG", "--archivo", "IMG_1234.jpg", "--cantidad", "3"])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "IMG_1234_1.jpg" in salida
    assert "IMG_1234_2.jpg" in salida
    assert "IMG_1234_3.jpg" in salida
    assert (carpeta / "IMG_1234_1.jpg").exists()


def test_cmd_separar_reporta_error_si_falta_flag(capsys):
    codigo = driver.cmd_separar(["--proyecto", "UMAG", "--cantidad", "2"])
    salida = capsys.readouterr().out
    assert codigo == 2
    assert "--archivo" in salida


def test_cmd_separar_reporta_error_si_archivo_no_existe(tmp_path, monkeypatch, capsys):
    raiz_docs = tmp_path / "docs"
    (raiz_docs / "UMAG").mkdir(parents=True)
    cl_cfg = dict(acc.PAISES["CL"])
    cl_cfg["ruta_docs"] = raiz_docs
    cl_cfg["ruta_backups"] = tmp_path / "backups"
    monkeypatch.setitem(acc.PAISES, "CL", cl_cfg)

    codigo = driver.cmd_separar(["--proyecto", "UMAG", "--archivo", "NoExiste.jpg", "--cantidad", "2"])

    salida = capsys.readouterr().out
    assert codigo == 1
    assert "[ERROR]" in salida
