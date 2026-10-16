import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import alertas_oportunidades  # noqa: E402
import bases_oportunidades  # noqa: E402
import compra_agil  # noqa: E402
import mercado_publico  # noqa: E402
import oportunidades  # noqa: E402


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
