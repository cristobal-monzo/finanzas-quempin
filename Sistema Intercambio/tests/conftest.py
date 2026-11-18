import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import alertas_oportunidades  # noqa: E402
import bases_oportunidades  # noqa: E402
import compra_agil  # noqa: E402
import mercado_publico  # noqa: E402
import oportunidades  # noqa: E402
import procesar  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "con_git_real: no reemplaza procesar.codigo_en_uso (la prueba usa su propio repo)")


@pytest.fixture(autouse=True)
def _sin_git_ni_tareas_del_equipo(request, monkeypatch):
    """estado.json dice qué rama corre el procesador y si está la tarea de pedidos (2026-11-06). En las pruebas eso
    no depende de la rama del worktree ni de las tareas del equipo que las corre: producción limpia, con la tarea."""
    monkeypatch.setattr(procesar, "tarea_de_pedidos_instalada", lambda: True)
    if request.node.get_closest_marker("con_git_real"):
        return
    monkeypatch.setattr(procesar, "codigo_en_uso", lambda repo=None: {"rama": "master", "commit": "abc1234", "sucio": False})


@pytest.fixture(autouse=True)
def _sin_mercado_publico_real(tmp_path, monkeypatch):
    """Ninguna prueba consulta la API real, lee el ticket del equipo ni
    escribe la caché real del monitor de Mercado Público."""
    def _sin_red(url, tiempo):
        raise AssertionError("una prueba intentó consultar Mercado Público de verdad")
    monkeypatch.setattr(mercado_publico, "_abrir_https", _sin_red)
    monkeypatch.setattr(mercado_publico, "RUTA_ESTADO", tmp_path / "mp_estado.json")
    monkeypatch.setattr(oportunidades, "RUTA_ESTADO", tmp_path / "oportunidades_estado.json")
    monkeypatch.setattr(mercado_publico, "ruta_ticket", lambda: tmp_path / "sin-ticket" / "mp.ticket")
    monkeypatch.delenv(mercado_publico.VARIABLE_TICKET, raising=False)
    # El candado del procesador y la marca «API en uso» viven en %LOCALAPPDATA% (2026-11-11): ninguna prueba
    # bloquea ni libera los del equipo que las corre.
    monkeypatch.setattr(mercado_publico, "ruta_api_en_uso", lambda: tmp_path / "mp-en-uso.lock")
    monkeypatch.setattr(procesar, "RUTA_CANDADO", tmp_path / "procesador.lock")
    # El respaldo diario nunca escribe en %LOCALAPPDATA% real (2026-11-09).
    monkeypatch.setenv("QUEMPIN_RESPALDO_DESTINO", str(tmp_path / "respaldos"))

    # Compra Ágil (otra API) y el correo de alertas: ninguna prueba sale a la
    # red ni manda un correo de verdad (2026-10-14).
    def _sin_red_ca(url, tiempo, encabezados):
        raise AssertionError("una prueba intentó consultar Compra Ágil de verdad")

    def _sin_outlook(*args, **kwargs):
        raise AssertionError("una prueba intentó enviar un correo de verdad")
    monkeypatch.setattr(compra_agil, "_abrir_https", _sin_red_ca)
    monkeypatch.setattr(alertas_oportunidades, "enviar_outlook", _sin_outlook)
    monkeypatch.setattr(alertas_oportunidades, "RUTA_REGISTRO", tmp_path / "oportunidades_estado_correos.json")
    monkeypatch.setattr(alertas_oportunidades, "RUTA_DESTINATARIOS", tmp_path / "sin-destinatarios.json")

    # La revisión de las bases antes del correo (2026-10-15): ninguna prueba
    # baja una ficha de verdad. Las del correo que no miran las bases pasan
    # por una revisión sin observaciones; las que sí, traen su propio revisor.
    def _sin_red_ficha(url, tiempo):
        raise AssertionError("una prueba intentó bajar una ficha de Mercado Público de verdad")

    def _bases_sin_observaciones(o, ahora, config):
        return {"codigo": o["codigo"], "ok": True, "revisado": ahora.isoformat(timespec="minutes"), "puntos": [],
                "descarta": None, "correcciones": {}, "remiten": 0, "fuente": "una ficha de prueba"}
    monkeypatch.setattr(bases_oportunidades, "_abrir_ficha", _sin_red_ficha)
    monkeypatch.setattr(alertas_oportunidades, "revisar_bases", _bases_sin_observaciones)
