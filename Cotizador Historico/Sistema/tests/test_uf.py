import json
from datetime import date

import pytest

import cotizador_historico as ch


class _FakeRespuesta:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._payload


# ── consultar_uf_api ─────────────────────────────────────────────────────

def test_consultar_uf_api_devuelve_valor_de_la_serie(monkeypatch):
    payload = {"serie": [{"fecha": "2026-07-15T04:00:00.000Z", "valor": 39123.45}]}
    monkeypatch.setattr(ch.urllib.request, "urlopen", lambda url, timeout=10: _FakeRespuesta(payload))
    valor = ch.consultar_uf_api(date(2026, 7, 15))
    assert valor == 39123.45


def test_consultar_uf_api_sin_serie_lanza_error(monkeypatch):
    payload = {"serie": []}
    monkeypatch.setattr(ch.urllib.request, "urlopen", lambda url, timeout=10: _FakeRespuesta(payload))
    with pytest.raises(ch.UFNoDisponibleError):
        ch.consultar_uf_api(date(2026, 7, 15))


def test_consultar_uf_api_sin_conexion_lanza_error(monkeypatch):
    def _falla(url, timeout=10):
        raise ch.urllib.error.URLError("sin conexion")
    monkeypatch.setattr(ch.urllib.request, "urlopen", _falla)
    with pytest.raises(ch.UFNoDisponibleError):
        ch.consultar_uf_api(date(2026, 7, 15))


# ── cargar_cache_uf / guardar_cache_uf ──────────────────────────────────

def test_cargar_cache_uf_archivo_inexistente_devuelve_vacio(tmp_path):
    assert ch.cargar_cache_uf(tmp_path / "no_existe.json") == {}


def test_guardar_y_cargar_cache_uf_roundtrip(tmp_path):
    ruta = tmp_path / "uf_cache.json"
    ch.guardar_cache_uf({"2026-07-15": 39123.45}, ruta)
    assert ch.cargar_cache_uf(ruta) == {"2026-07-15": 39123.45}


# ── obtener_valor_uf ─────────────────────────────────────────────────────

def test_obtener_valor_uf_usa_cache_si_existe(monkeypatch):
    def _falla_si_se_llama(fecha):
        raise AssertionError("no deberia llamar a la API si ya esta en cache")
    monkeypatch.setattr(ch, "consultar_uf_api", _falla_si_se_llama)

    cache = {"2026-07-15": 39100.0}
    valor = ch.obtener_valor_uf(date(2026, 7, 15), cache)
    assert valor == 39100.0


def test_obtener_valor_uf_consulta_api_y_actualiza_cache_si_falta(monkeypatch):
    monkeypatch.setattr(ch, "consultar_uf_api", lambda fecha: 40000.0)
    cache = {}
    valor = ch.obtener_valor_uf(date(2026, 7, 1), cache)
    assert valor == 40000.0
    assert cache == {"2026-07-01": 40000.0}
