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


def test_mostrar_preview_renombrados_lista_pendientes_y_no_encontrados(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "CFLI").mkdir()
    (tmp_path / "CFLI" / "factura_original.pdf").write_bytes(b"contenido")

    filas_master = [
        {"fila": 5, "n_ref": "CFLI-003", "archivo_origen": "CFLI\\factura_original.pdf",
         "proveedor_tag": "Beckman", "fecha": "01/02/2026"},
        {"fila": 9, "n_ref": "UMAG-030", "archivo_origen": "UMAG\\NoExiste.jpg",
         "proveedor_tag": "Anwo", "fecha": "20/03/2026"},
    ]

    driver.mostrar_preview_renombrados(filas_master, {})

    salida = capsys.readouterr().out
    assert "renombrarian/convertirian si corres 'run': 1" in salida
    assert "CFLI-003" in salida
    assert "factura_original.pdf -> CFLI-003_Beckman_01-02-2026.pdf" in salida
    assert "1 fila(s) sin archivo fisico encontrado" in salida
    assert "UMAG-030" in salida
