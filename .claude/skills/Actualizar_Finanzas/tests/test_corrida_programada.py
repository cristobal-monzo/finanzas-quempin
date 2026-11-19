"""La corrida programada lee facturas con Claude Code sin poder romper nada (2026-11-19)."""
import importlib.util
import os
import re
from pathlib import Path

import pytest

CARPETA = Path(__file__).resolve().parents[1]
CMD = (CARPETA / "tarea_programada.cmd").read_text(encoding="utf-8")


def _llamadas_claude():
    return [linea for linea in CMD.splitlines() if 'call "%CLAUDE%"' in linea]


def test_claude_lee_con_las_reglas_de_la_corrida_programada():
    assert (CARPETA / "corrida_programada.md").exists()
    for linea in _llamadas_claude():
        assert '--append-system-prompt-file "%SKILL%corrida_programada.md"' in linea
        assert "--permission-mode dontAsk" in linea, "sin nadie al frente, lo no permitido se niega, no se pregunta"


def test_claude_solo_escribe_datos_extraidos_y_nunca_corre_run_ni_publica():
    llamadas = _llamadas_claude()
    assert len(llamadas) == 2
    for linea in llamadas:
        for prohibido in ("Bash(* run*)", "Bash(*publicar*)", "Bash(*separar*)", "Bash(*eliminar*)"):
            assert prohibido in linea
        permitidos = linea.split("--allowedTools", 1)[1].split("--disallowedTools", 1)[0]
        assert not re.search(r"(^|\s)\"?(Edit|Write|Bash)\"?(\s|$)", permitidos), "nada de Edit, Write o Bash sin límite"
    assert 'set "PUEDE_ESCRIBIR=Edit(./Centro de Costos/Sistema/datos_extraidos.json)"' in CMD
    assert "--disallowedTools Edit Write" in llamadas[1], "el modo prueba no escribe nada"


def test_el_run_corre_siempre_despues_aunque_claude_falle():
    paso1 = CMD.index('call "%CLAUDE%"')
    run = CMD.index('"%PYTHON%" "%DRIVER%" run --con-pendientes')
    assert paso1 < run
    entre = CMD[paso1:run]
    salida = entre.index("exit /b")
    assert entre.count("exit /b") == 1 and entre.rfind('if /i "%MODO%"=="prueba"', 0, salida) != -1, \
        "antes del run solo sale el modo prueba"
    assert "exit /b %CODIGO%" in CMD[run:], "el código de salida de la tarea es el del run"


def test_el_token_no_queda_en_el_entorno_del_run():
    assert CMD.index('set "CLAUDE_CODE_OAUTH_TOKEN="') < CMD.index('"%DRIVER%" run')


@pytest.mark.skipif(os.name != "nt", reason="DPAPI es de Windows")
def test_el_token_se_guarda_cifrado_y_se_vuelve_a_leer(tmp_path):
    spec = importlib.util.spec_from_file_location("token_claude", CARPETA / "token_claude.py")
    tc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tc)
    token = "sk-ant-oat01-" + "x" * 40
    ruta = tc.guardar(token, tmp_path / "claude.token")
    assert token.encode() not in ruta.read_bytes()
    assert tc.leer(ruta) == token
    assert tc.leer(tmp_path / "no-existe") is None
    with pytest.raises(ValueError):
        tc.guardar("corto", tmp_path / "otro")
