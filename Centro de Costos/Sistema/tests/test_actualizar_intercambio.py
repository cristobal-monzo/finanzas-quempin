"""PASO 12e: cada 'run' del Centro de Costos termina con una vuelta del
procesador del Intercambio (pedido del usuario, 2026-11-09)."""
import subprocess
import sys

import auditor_centro_costos as acc


class _Proceso:
    def __init__(self, returncode=0, stdout="  OK    ejecucion  listo  (1.0 s)\n"):
        self.returncode, self.stdout, self.stderr = returncode, stdout, ""


def _espiar(monkeypatch, tmp_path, proceso=None):
    script = tmp_path / "procesar.py"
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(acc, "PROCESADOR_INTERCAMBIO", script)
    monkeypatch.delenv(acc.VARIABLE_SIN_INTERCAMBIO, raising=False)
    llamadas = []

    def falso_run(args, **kw):
        llamadas.append((args, kw))
        return proceso or _Proceso()

    monkeypatch.setattr(subprocess, "run", falso_run)
    return script, llamadas


def test_corre_el_procesador_con_forzar(monkeypatch, tmp_path, capsys):
    script, llamadas = _espiar(monkeypatch, tmp_path)
    assert acc.actualizar_intercambio("CL") is True
    assert llamadas[0][0] == [sys.executable, str(script), "--forzar"]
    assert llamadas[0][1]["cwd"] == str(tmp_path)
    assert "ejecucion" in capsys.readouterr().out


def test_la_variable_lo_apaga(monkeypatch, tmp_path):
    _, llamadas = _espiar(monkeypatch, tmp_path)
    monkeypatch.setenv(acc.VARIABLE_SIN_INTERCAMBIO, "1")
    assert acc.actualizar_intercambio("CL") is False
    assert llamadas == []


def test_peru_no_lo_corre(monkeypatch, tmp_path):
    _, llamadas = _espiar(monkeypatch, tmp_path)
    assert acc.actualizar_intercambio("PE") is False
    assert llamadas == []


def test_si_falla_solo_advierte(monkeypatch, tmp_path, capsys):
    _espiar(monkeypatch, tmp_path, _Proceso(returncode=1, stdout="boom\n"))
    assert acc.actualizar_intercambio("CL") is False
    assert "[WARN]" in capsys.readouterr().out


def test_sin_procesador_se_omite(monkeypatch, tmp_path):
    monkeypatch.setattr(acc, "PROCESADOR_INTERCAMBIO", tmp_path / "no-existe.py")
    monkeypatch.delenv(acc.VARIABLE_SIN_INTERCAMBIO, raising=False)
    assert acc.actualizar_intercambio("CL") is False


def test_main_lo_llama_despues_de_analisis_financiero():
    import inspect
    fuente = inspect.getsource(acc.main)
    assert fuente.index("actualizar_analisis_financiero(pais=pais)") < fuente.index(
        "actualizar_intercambio(pais=pais)")
