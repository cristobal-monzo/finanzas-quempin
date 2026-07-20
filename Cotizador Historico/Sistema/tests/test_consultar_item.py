from datetime import date, datetime

import cotizador_historico as ch


def _item(n_ref, nombre, descripcion, precio, fecha, excluido=None, total_sin_iva=None, total_con_iva=None):
    return {
        "n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
        "precio_unitario_sin_iva": precio, "fecha": fecha, "excluido_motivo": excluido,
        "total_sin_iva": total_sin_iva, "total_con_iva": total_con_iva,
    }


# ── calcular_precio_reajustado ──────────────────────────────────────────

def test_calcular_precio_reajustado_aplica_factor_uf():
    # UF subio de 36000 a 39000: factor 39000/36000 = 1.08333...
    assert ch.calcular_precio_reajustado(90000, 36000, 39000) == round(90000 * 39000 / 36000)


def test_calcular_precio_reajustado_uf_sin_cambio_no_altera_precio():
    assert ch.calcular_precio_reajustado(50000, 38000, 38000) == 50000


# ── tasa_iva_real ────────────────────────────────────────────────────────

def test_tasa_iva_real_deriva_tasa_del_documento():
    # Documento con 19%: Total con IVA = Total sin IVA * 1.19
    assert ch.tasa_iva_real(100000, 119000) == 1.19


def test_tasa_iva_real_documento_exento_devuelve_1():
    assert ch.tasa_iva_real(5000, 5000) == 1.0


def test_tasa_iva_real_sin_datos_devuelve_1_como_respaldo():
    assert ch.tasa_iva_real(None, None) == 1.0
    assert ch.tasa_iva_real(0, 0) == 1.0
    assert ch.tasa_iva_real(100000, None) == 1.0


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
        {"n_ref": "UMAG-001", "fecha": "2026-01-01", "precio_original_sin_iva": 90000,
         "precio_reajustado_hoy": esperado_1, "precio_reajustado_hoy_con_iva": esperado_1},
        {"n_ref": "UMAG-002", "fecha": "2026-03-01", "precio_original_sin_iva": 100000,
         "precio_reajustado_hoy": esperado_2, "precio_reajustado_hoy_con_iva": esperado_2},
    ]
    assert resultado["promedio_reajustado"] == round((esperado_1 + esperado_2) / 2)
    assert resultado["promedio_reajustado_con_iva"] == round((esperado_1 + esperado_2) / 2)
    assert resultado["rango_minimo"] == min(esperado_1, esperado_2)
    assert resultado["rango_maximo"] == max(esperado_1, esperado_2)
    assert resultado["excluidos_count"] == 0
    assert resultado["sugerencias"] == []
    assert resultado["sin_uf_count"] == 0


def test_consultar_item_aplica_tasa_iva_real_del_documento(monkeypatch, tmp_path):
    items = [_item(
        "CCON-002", "Guante", "Guante de cuero natural", 2513, datetime(2026, 1, 1),
        total_sin_iva=2513, total_con_iva=2990,  # tasa real ~1.19
    )]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")
    monkeypatch.setattr(ch, "consultar_uf_api", _mapa_uf)

    resultado = ch.consultar_item("guante", fecha_hoy=date(2026, 7, 17))

    esperado_sin_iva = ch.calcular_precio_reajustado(2513, _mapa_uf(datetime(2026, 1, 1)), 39000.0)
    tasa = ch.tasa_iva_real(2513, 2990)
    esperado_con_iva = round(esperado_sin_iva * tasa)

    assert resultado["compras"][0]["precio_reajustado_hoy"] == esperado_sin_iva
    assert resultado["compras"][0]["precio_reajustado_hoy_con_iva"] == esperado_con_iva
    assert resultado["promedio_reajustado_con_iva"] == esperado_con_iva


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


def test_consultar_item_no_crashea_con_precio_invalido_y_lo_excluye(monkeypatch, tmp_path):
    items = [
        _item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1)),
        _item("UMAG-002", "Taladro", "Taladro sin precio", None, datetime(2026, 1, 1), excluido="precio_invalido"),
    ]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")
    monkeypatch.setattr(ch, "consultar_uf_api", _mapa_uf)

    resultado = ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17))

    assert resultado["encontrado"] is True
    assert len(resultado["compras"]) == 1
    assert resultado["compras"][0]["n_ref"] == "UMAG-001"
    assert resultado["excluidos_count"] == 1


def _mapa_uf_con_fallo(fecha):
    fecha_iso = fecha.strftime("%Y-%m-%d")
    if fecha_iso == "2026-03-01":
        raise ch.UFNoDisponibleError("simulado: sin dato de UF para esta fecha")
    mapa = {"2026-01-01": 36000.0, "2026-07-17": 39000.0}
    return mapa[fecha_iso]


def test_consultar_item_excluye_solo_la_compra_sin_uf_disponible(monkeypatch, tmp_path):
    items = [
        _item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1)),
        _item("UMAG-002", "Taladro", "Taladro inalambrico", 100000, datetime(2026, 3, 1)),
    ]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")
    monkeypatch.setattr(ch, "consultar_uf_api", _mapa_uf_con_fallo)

    resultado = ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17))

    esperado = round(90000 * 39000 / 36000)
    assert resultado["encontrado"] is True
    assert resultado["compras"] == [
        {"n_ref": "UMAG-001", "fecha": "2026-01-01", "precio_original_sin_iva": 90000,
         "precio_reajustado_hoy": esperado, "precio_reajustado_hoy_con_iva": esperado},
    ]
    assert resultado["sin_uf_count"] == 1


def test_consultar_item_todas_sin_uf_disponible_devuelve_no_encontrado(monkeypatch, tmp_path):
    items = [_item("UMAG-002", "Taladro", "Taladro inalambrico", 100000, datetime(2026, 3, 1))]
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None: items)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")
    monkeypatch.setattr(ch, "consultar_uf_api", _mapa_uf_con_fallo)

    resultado = ch.consultar_item("taladro", fecha_hoy=date(2026, 7, 17))

    assert resultado["encontrado"] is False
    assert resultado["compras"] == []
    assert resultado["sin_uf_count"] == 1


# ── reajustar_item ───────────────────────────────────────────────────────

def test_reajustar_item_calcula_precio_y_fecha_string():
    item = _item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1))
    cache = {"2026-01-01": 36000.0}
    compra = ch.reajustar_item(item, 39000.0, cache)
    assert compra == {
        "n_ref": "UMAG-001",
        "fecha": "2026-01-01",
        "precio_original_sin_iva": 90000,
        "precio_reajustado_hoy": round(90000 * 39000 / 36000),
        "precio_reajustado_hoy_con_iva": round(90000 * 39000 / 36000),
    }


def test_reajustar_item_aplica_tasa_iva_real():
    item = _item("CCON-002", "Guante", "Guante de cuero natural", 2513, datetime(2026, 1, 1),
                 total_sin_iva=2513, total_con_iva=2990)
    cache = {"2026-01-01": 36000.0}
    compra = ch.reajustar_item(item, 39000.0, cache)
    esperado_sin_iva = ch.calcular_precio_reajustado(2513, 36000.0, 39000.0)
    esperado_con_iva = round(esperado_sin_iva * ch.tasa_iva_real(2513, 2990))
    assert compra["precio_reajustado_hoy"] == esperado_sin_iva
    assert compra["precio_reajustado_hoy_con_iva"] == esperado_con_iva


def test_reajustar_item_devuelve_none_si_uf_no_disponible(monkeypatch):
    item = _item("UMAG-001", "Taladro", "Taladro percutor 20V", 90000, datetime(2026, 1, 1))
    def _falla(fecha, cache):
        raise ch.UFNoDisponibleError("simulado")
    monkeypatch.setattr(ch, "obtener_valor_uf", _falla)
    assert ch.reajustar_item(item, 39000.0, {}) is None
