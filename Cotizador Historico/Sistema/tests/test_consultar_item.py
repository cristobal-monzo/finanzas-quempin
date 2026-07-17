from datetime import date, datetime

import cotizador_historico as ch


def _item(n_ref, nombre, descripcion, precio, fecha, excluido=None):
    return {
        "n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
        "precio_unitario_sin_iva": precio, "fecha": fecha, "excluido_motivo": excluido,
    }


# ── calcular_precio_reajustado ──────────────────────────────────────────

def test_calcular_precio_reajustado_aplica_factor_uf():
    # UF subio de 36000 a 39000: factor 39000/36000 = 1.08333...
    assert ch.calcular_precio_reajustado(90000, 36000, 39000) == round(90000 * 39000 / 36000)


def test_calcular_precio_reajustado_uf_sin_cambio_no_altera_precio():
    assert ch.calcular_precio_reajustado(50000, 38000, 38000) == 50000


# ── consultar_item ─────────────────────────────────────────────────────

def _mapa_uf(fecha):
    mapa = {"2026-01-01": 36000.0, "2026-03-01": 37000.0, "2026-07-17": 39000.0}
    return mapa[fecha.strftime("%Y-%m-%d")]


def test_consultar_item_calcula_reajuste_y_agregados(monkeypatch, tmp_path):
    items = [
        _item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1)),
        _item("UMAG-002", "Taladro", "Taladro inalambrico", 100000, datetime(2026, 3, 1)),
    ]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")
    monkeypatch.setattr(ch, "consultar_uf_api", _mapa_uf)

    resultado = ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17))

    esperado_1 = round(90000 * 39000 / 36000)
    esperado_2 = round(100000 * 39000 / 37000)

    assert resultado["encontrado"] is True
    assert resultado["compras"] == [
        {"n_ref": "UMAG-001", "fecha": "2026-01-01", "precio_original_sin_iva": 90000, "precio_reajustado_hoy": esperado_1},
        {"n_ref": "UMAG-002", "fecha": "2026-03-01", "precio_original_sin_iva": 100000, "precio_reajustado_hoy": esperado_2},
    ]
    assert resultado["promedio_reajustado"] == round((esperado_1 + esperado_2) / 2)
    assert resultado["rango_minimo"] == min(esperado_1, esperado_2)
    assert resultado["rango_maximo"] == max(esperado_1, esperado_2)
    assert resultado["excluidos_count"] == 0
    assert resultado["sugerencias"] == []


def test_consultar_item_persiste_uf_historica_en_cache_pero_no_la_de_hoy(monkeypatch, tmp_path):
    items = [_item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1))]
    ruta_cache = tmp_path / "uf_cache.json"
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", ruta_cache)
    monkeypatch.setattr(ch, "consultar_uf_api", _mapa_uf)

    ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17))

    cache_final = ch.cargar_cache_uf(ruta_cache)
    assert cache_final == {"2026-01-01": 36000.0}  # la fecha de compra si, "hoy" no


def test_consultar_item_sin_match_devuelve_no_encontrado(monkeypatch):
    items = [_item("UMAG-001", "Cemento", "Saco 25kg", 5000, datetime(2026, 1, 1))]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)

    resultado = ch.consultar_item("bicicleta", fecha_hoy=date(2026, 7, 17))

    assert resultado["encontrado"] is False
    assert resultado["compras"] == []
    assert resultado["promedio_reajustado"] is None
    assert resultado["rango_minimo"] is None
    assert resultado["rango_maximo"] is None


def test_consultar_item_sin_match_no_llama_a_la_api_de_uf(monkeypatch):
    items = [_item("UMAG-001", "Cemento", "Saco 25kg", 5000, datetime(2026, 1, 1))]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)

    def _falla_si_se_llama(fecha):
        raise AssertionError("no deberia consultar UF si no hubo match")
    monkeypatch.setattr(ch, "consultar_uf_api", _falla_si_se_llama)

    ch.consultar_item("bicicleta", fecha_hoy=date(2026, 7, 17))


def test_consultar_item_cuenta_excluidos(monkeypatch, tmp_path):
    items = [
        _item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1)),
        _item("UMAG-002", "Cemento", "Saco 25kg", 5000, None, excluido="sin_master"),
    ]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)
    monkeypatch.setattr(ch, "consultar_uf_api", _mapa_uf)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")

    resultado = ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17))
    assert resultado["excluidos_count"] == 1
