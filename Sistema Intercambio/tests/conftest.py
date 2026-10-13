import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import mercado_publico  # noqa: E402


@pytest.fixture(autouse=True)
def _sin_mercado_publico_real(tmp_path, monkeypatch):
    """Ninguna prueba consulta la API real, lee el ticket del equipo ni
    escribe la caché real del monitor de Mercado Público."""
    def _sin_red(url, tiempo):
        raise AssertionError("una prueba intentó consultar Mercado Público de verdad")
    monkeypatch.setattr(mercado_publico, "_abrir_https", _sin_red)
    monkeypatch.setattr(mercado_publico, "RUTA_ESTADO", tmp_path / "mp_estado.json")
    monkeypatch.setattr(mercado_publico, "ruta_ticket", lambda: tmp_path / "sin-ticket" / "mp.ticket")
    monkeypatch.delenv(mercado_publico.VARIABLE_TICKET, raising=False)
