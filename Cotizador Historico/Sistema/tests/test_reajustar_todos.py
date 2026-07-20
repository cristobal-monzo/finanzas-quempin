from datetime import datetime

import cotizador_historico as ch


def _item(n_ref, nombre, descripcion, precio, fecha, excluido=None,
          categoria_item=None, proyecto=None, proveedor_tag=None):
    return {
        "n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
        "precio_unitario_sin_iva": precio, "fecha": fecha, "excluido_motivo": excluido,
        "total_sin_iva": precio, "total_con_iva": precio,
        "categoria_item": categoria_item, "proyecto": proyecto, "proveedor_tag": proveedor_tag,
    }


def test_reajustar_todos_incluye_metadata_de_producto():
    items = [_item("UMAG-014", "Bomba", "Bomba centrífuga 1.5HP", 90000, datetime(2026, 1, 1),
                    categoria_item="Equipos-Herramientas", proyecto="UMAG", proveedor_tag="Ferretería XYZ")]
    cache = {"2026-01-01": 36000.0}

    reajustados, sin_uf_count = ch.reajustar_todos(items, 39000.0, cache)

    assert sin_uf_count == 0
    assert len(reajustados) == 1
    r = reajustados[0]
    assert r["n_ref"] == "UMAG-014"
    assert r["nombre_item"] == "Bomba"
    assert r["descripcion"] == "Bomba centrífuga 1.5HP"
    assert r["categoria_item"] == "Equipos-Herramientas"
    assert r["proyecto"] == "UMAG"
    assert r["proveedor_tag"] == "Ferretería XYZ"
    assert r["precio_reajustado_hoy"] == round(90000 * 39000 / 36000)


def test_reajustar_todos_omite_items_excluidos():
    items = [
        _item("UMAG-014", "Bomba", "Bomba centrífuga 1.5HP", 90000, datetime(2026, 1, 1)),
        _item("UMAG-015", "Cemento", "Saco 25kg", 5000, None, excluido="sin_master"),
    ]
    cache = {"2026-01-01": 36000.0}

    reajustados, sin_uf_count = ch.reajustar_todos(items, 39000.0, cache)

    assert len(reajustados) == 1
    assert reajustados[0]["n_ref"] == "UMAG-014"


def test_reajustar_todos_cuenta_items_sin_uf_disponible(monkeypatch):
    items = [_item("UMAG-014", "Bomba", "Bomba centrífuga 1.5HP", 90000, datetime(2026, 1, 1))]

    def _falla(fecha, cache):
        raise ch.UFNoDisponibleError("simulado")
    monkeypatch.setattr(ch, "obtener_valor_uf", _falla)

    reajustados, sin_uf_count = ch.reajustar_todos(items, 39000.0, {})

    assert reajustados == []
    assert sin_uf_count == 1


def test_reajustar_todos_usa_cache_propio_si_no_se_pasa_uno(monkeypatch, tmp_path):
    items = [_item("UMAG-014", "Bomba", "Bomba centrífuga 1.5HP", 90000, datetime(2026, 1, 1))]
    ruta_cache = tmp_path / "uf_cache.json"
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", ruta_cache)
    monkeypatch.setattr(ch, "consultar_uf_api", lambda fecha: 36000.0)

    ch.reajustar_todos(items, 39000.0)  # cache_uf no provisto

    assert ch.cargar_cache_uf(ruta_cache) == {"2026-01-01": 36000.0}
