"""Tests del arnes de la skill Registro_Analisis_Financiero (driver.py):
antes sin cobertura directa, a diferencia de Reportes_Analisis_Financiero
(ver Reportes/tests/test_driver_reportes.py) y del driver de Centro de
Costos (ver Centro de Costos/Sistema/tests/test_driver_preview_renombrados.py).

No ejercitan analisis_financiero.py de verdad (eso ya lo cubren sus propios
tests) -- mockean 'af.ejecutar'/'af.confirmar_clientes_pendientes' para
probar solo la logica propia del driver: que arma con el resumen, y el
dispatch de comandos de main()."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import analisis_financiero as af

# Nombre unico: los 3 modulos financieros (y sus dos skills, Registro_ y
# Reportes_) tienen su propio "driver.py" -- sys.modules cachea por nombre,
# asi que un "import driver" plano en un modulo cacheado por otro test
# entregaria el driver equivocado. Mismo patron que
# Centro de Costos/Sistema/tests/test_driver_preview_renombrados.py.
_RUTA_DRIVER = (
    Path(__file__).resolve().parent.parent.parent
    / ".claude" / "skills" / "Registro_Analisis_Financiero" / "driver.py"
)
_spec = importlib.util.spec_from_file_location("driver_registro_af", _RUTA_DRIVER)
driver = importlib.util.module_from_spec(_spec)
sys.modules["driver_registro_af"] = driver
_spec.loader.exec_module(driver)


# ── cmd_status ────────────────────────────────────────────────────────────

def _resumen(**overrides):
    base = {"carpetas_creadas": [], "categorias_no_mapeadas": [], "avisos": []}
    base.update(overrides)
    return base


def test_status_avisa_si_no_hay_carpetas_nuevas(capsys):
    with patch.object(af, "ejecutar", return_value=_resumen()):
        driver.cmd_status()
    salida = capsys.readouterr().out
    assert "No hay carpetas de proyecto nuevas por crear." in salida
    assert "Nada fue escrito" in salida


def test_status_lista_carpetas_que_se_crearian(capsys):
    with patch.object(af, "ejecutar", return_value=_resumen(carpetas_creadas=["UMAG", "CFLI"])):
        driver.cmd_status()
    salida = capsys.readouterr().out
    assert "SE CREARÍAN: UMAG, CFLI" in salida


def test_status_lista_categorias_sin_mapeo(capsys):
    with patch.object(af, "ejecutar", return_value=_resumen(categorias_no_mapeadas=["Peajes"])):
        driver.cmd_status()
    salida = capsys.readouterr().out
    assert "Peajes" in salida
    assert "'Otros'" in salida


def test_status_lista_avisos(capsys):
    with patch.object(af, "ejecutar", return_value=_resumen(avisos=["algo raro paso"])):
        driver.cmd_status()
    salida = capsys.readouterr().out
    assert "[AVISO] algo raro paso" in salida


def test_status_llama_a_ejecutar_en_modo_dry_run():
    with patch.object(af, "ejecutar", return_value=_resumen()) as mock_ejecutar:
        driver.cmd_status()
    mock_ejecutar.assert_called_once_with(dry_run=True)


# ── cmd_confirmar_cliente ─────────────────────────────────────────────────

def test_confirmar_cliente_sin_args_lista_pendientes(capsys):
    pendientes = [
        {"tag": "UMAG", "nombre_proyecto": "UMAG", "cliente_sugerido": "AGCID", "similitud": 0.87},
    ]
    with patch.object(af, "confirmar_clientes_pendientes", return_value=pendientes) as mock_fn:
        codigo = driver.cmd_confirmar_cliente([])
    mock_fn.assert_called_once_with(None)
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "Clientes pendientes de confirmar: 1" in salida
    assert "UMAG" in salida and "AGCID" in salida
    assert "confirmar-cliente --todos" in salida


def test_confirmar_cliente_sin_args_y_sin_pendientes_no_sugiere_todos(capsys):
    with patch.object(af, "confirmar_clientes_pendientes", return_value=[]):
        driver.cmd_confirmar_cliente([])
    salida = capsys.readouterr().out
    assert "Clientes pendientes de confirmar: 0" in salida
    assert "--todos" not in salida


def test_confirmar_cliente_todos_pasa_el_literal_todos_a_la_funcion():
    with patch.object(af, "confirmar_clientes_pendientes", return_value=[]) as mock_fn:
        driver.cmd_confirmar_cliente(["--todos"])
    mock_fn.assert_called_once_with("TODOS")


def test_confirmar_cliente_con_tags_especificos_pasa_la_lista():
    with patch.object(af, "confirmar_clientes_pendientes", return_value=[]) as mock_fn:
        driver.cmd_confirmar_cliente(["UMAG-014", "CFLI-002"])
    mock_fn.assert_called_once_with(["UMAG-014", "CFLI-002"])


def test_confirmar_cliente_aplicados_se_imprimen_ok(capsys):
    aplicados = [{"tag": "UMAG", "cliente_sugerido": "AGCID"}]
    with patch.object(af, "confirmar_clientes_pendientes", return_value=aplicados):
        driver.cmd_confirmar_cliente(["--todos"])
    salida = capsys.readouterr().out
    assert "[OK] UMAG -> Cliente 'AGCID' confirmado" in salida


def test_confirmar_cliente_sin_coincidencias_avisa(capsys):
    with patch.object(af, "confirmar_clientes_pendientes", return_value=[]):
        driver.cmd_confirmar_cliente(["TAG-INEXISTENTE"])
    salida = capsys.readouterr().out
    assert "No hay clientes pendientes que coincidan" in salida


# ── main(): dispatch de comandos ─────────────────────────────────────────

def test_main_sin_comando_valido_devuelve_2_y_no_llama_nada(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["driver.py", "no-existe"])
    with patch.object(driver, "cmd_status") as mock_status, \
         patch.object(driver, "cmd_run") as mock_run:
        codigo = driver.main()
    assert codigo == 2
    mock_status.assert_not_called()
    mock_run.assert_not_called()
    assert "Uso:" in capsys.readouterr().out


def test_main_status_llama_a_cmd_status(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["driver.py", "status"])
    with patch.object(driver, "cmd_status", return_value=0) as mock_status:
        assert driver.main() == 0
    mock_status.assert_called_once()


def test_main_confirmar_cliente_pasa_los_argumentos_restantes(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["driver.py", "confirmar-cliente", "--todos"])
    with patch.object(driver, "cmd_confirmar_cliente", return_value=0) as mock_fn:
        driver.main()
    mock_fn.assert_called_once_with(["--todos"])


def test_main_visualizador_llama_a_cmd_visualizador(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["driver.py", "visualizador"])
    with patch.object(driver, "cmd_visualizador", return_value=0) as mock_fn:
        driver.main()
    mock_fn.assert_called_once()


def test_main_cualquier_otro_comando_valido_cae_a_cmd_run(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["driver.py", "run"])
    with patch.object(driver, "cmd_run", return_value=0) as mock_fn:
        driver.main()
    mock_fn.assert_called_once()
