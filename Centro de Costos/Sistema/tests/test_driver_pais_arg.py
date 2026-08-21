import importlib.util
import sys
from pathlib import Path

import auditor_centro_costos as acc

_DRIVER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".claude" / "skills" / "Registro_Centro_de_Costos" / "driver.py"
)
_spec = importlib.util.spec_from_file_location("driver_bajo_prueba", _DRIVER_PATH)
driver = importlib.util.module_from_spec(_spec)
sys.modules["driver_bajo_prueba"] = driver
_spec.loader.exec_module(driver)


def test_extraer_pais_default_es_cl():
    pais, resto = driver._extraer_pais(["status"])
    assert pais == "CL"
    assert resto == ["status"]


def test_extraer_pais_detecta_flag_en_cualquier_posicion():
    pais, resto = driver._extraer_pais(["confirmar", "--pais", "PE", "--todos"])
    assert pais == "PE"
    assert resto == ["confirmar", "--todos"]


def test_cmd_status_con_pais_pe_usa_rutas_de_peru(tmp_path, monkeypatch, capsys):
    # cmd_status(pais="PE") llama acc.configurar_pais("PE") como primera linea,
    # que PISA cualquier monkeypatch.setattr(acc, "RAIZ_DOCS", ...) hecho antes
    # de la llamada -- hay que parchear el DICCIONARIO PAISES["PE"] en vez de
    # los globals, para que configurar_pais() resuelva a rutas de tmp_path.
    raiz_docs = tmp_path / "Facturas" / "Perú"
    raiz_docs.mkdir(parents=True)
    ruta_json = tmp_path / "datos_extraidos_peru.json"
    ruta_json.write_text("[]", encoding="utf-8")

    pe_cfg = dict(acc.PAISES["PE"])
    pe_cfg["ruta_docs"] = raiz_docs
    pe_cfg["ruta_json"] = ruta_json
    pe_cfg["ruta_excel"] = tmp_path / "Centro de Costos Perú.xlsx"  # no existe -- cmd_status lo tolera
    pe_cfg["ruta_reconciliacion"] = tmp_path / "reconciliacion_archivos_peru.json"
    pe_cfg["ruta_backups"] = tmp_path / "Respaldos"
    monkeypatch.setitem(acc.PAISES, "PE", pe_cfg)

    driver.cmd_status(pais="PE")

    salida = capsys.readouterr().out
    assert "IGV 18%" in salida
    assert acc.PAIS_ACTUAL == "PE"  # el fixture autouse restaura "CL" despues, para el proximo test


def test_cmd_status_consulta_backups_del_pais_activo_no_los_de_cl(tmp_path, monkeypatch, capsys):
    """cmd_status() llama acc.backup_mas_reciente() SIN pasar ruta_backups
    explicito -- ese parametro tiene un default (=RUTA_BACKUPS) atado en
    tiempo de definicion (modulo Chile), asi que si el call site no lo pasa
    explicito, seguiria mirando SIEMPRE la carpeta de respaldos de Chile
    aunque configurar_pais('PE') ya haya corrido. Este test detecta esa
    regresion poniendo un backup falso SOLO en la carpeta de Peru."""
    raiz_docs = tmp_path / "Facturas" / "Perú"
    raiz_docs.mkdir(parents=True)
    ruta_json = tmp_path / "datos_extraidos_peru.json"
    ruta_json.write_text("[]", encoding="utf-8")
    respaldos_pe = tmp_path / "Respaldos Peru"
    carpeta_mes = respaldos_pe / "Enero 2026"
    carpeta_mes.mkdir(parents=True)
    (carpeta_mes / "Centro de Costos - backup 2026-01-01 0000.xlsx").write_bytes(b"x")

    pe_cfg = dict(acc.PAISES["PE"])
    pe_cfg["ruta_docs"] = raiz_docs
    pe_cfg["ruta_json"] = ruta_json
    pe_cfg["ruta_excel"] = tmp_path / "Centro de Costos Perú.xlsx"
    pe_cfg["ruta_reconciliacion"] = tmp_path / "reconciliacion_archivos_peru.json"
    pe_cfg["ruta_backups"] = respaldos_pe
    monkeypatch.setitem(acc.PAISES, "PE", pe_cfg)

    llamadas = []
    original = acc.backup_mas_reciente

    def _espia(ruta_backups=None):
        llamadas.append(ruta_backups)
        return original(ruta_backups) if ruta_backups is not None else original()

    monkeypatch.setattr(acc, "backup_mas_reciente", _espia)
    driver.cmd_status(pais="PE")

    assert llamadas == [respaldos_pe]
