import cotizador_historico as ch


def _item(n_ref, nombre, descripcion="", excluido=None):
    return {
        "n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
        "precio_unitario_sin_iva": 1, "fecha": None, "excluido_motivo": excluido,
    }


# ── normalizar_texto ──────────────────────────────────────────────────────

def test_normalizar_texto_quita_acentos_y_mayusculas():
    assert ch.normalizar_texto("Ítem Eléctrico") == "item electrico"


def test_normalizar_texto_recorta_espacios():
    assert ch.normalizar_texto("  Taladro  ") == "taladro"


# ── similitud ──────────────────────────────────────────────────────────────

def test_similitud_exacta_es_1():
    assert ch.similitud("taladro", "taladro") == 1.0


def test_similitud_substring_es_1():
    assert ch.similitud("taladro", "taladro percutor 20v") == 1.0
    assert ch.similitud("taladro percutor 20v", "taladro") == 1.0


def test_similitud_texto_no_relacionado_es_baja():
    assert ch.similitud("taladro", "cemento") < 0.4


def test_similitud_con_typo_es_alta():
    assert ch.similitud("taladro", "taladr0") > 0.7


def test_similitud_con_texto_vacio_es_0():
    assert ch.similitud("taladro", "") == 0.0
    assert ch.similitud("", "taladro") == 0.0


def test_similitud_coincide_por_palabra_significativa_de_nombre_no_simplificado():
    # Nombre Item real sin simplificar (ver Centro de Costos/CLAUDE.md): el
    # primer termino calza con la consulta en plural, pero el string
    # completo no es substring uno del otro.
    assert ch.similitud("guantes", "guante de trabajo cuero spandex") == 1.0


def test_similitud_ignora_palabras_cortas_para_evitar_ruido():
    # "dab" (3 letras) no debe bastar para enganchar una consulta larga no
    # relacionada solo por compartir esa palabra corta.
    assert ch.similitud("caldera dab 150/280", "bomba dab circulacion en linea cp 50/2200 t-ie3") < 0.6


# ── buscar_items ───────────────────────────────────────────────────────────

def test_buscar_items_encuentra_nombre_no_simplificado_en_plural():
    items = [
        _item("A", "Guante", "Guante de cuero natural"),
        _item("B", "Guante de trabajo cuero spandex", "Cod. 123"),
    ]
    coincidencias, _sugerencias = ch.buscar_items(items, "guantes")
    assert {it["n_ref"] for it in coincidencias} == {"A", "B"}


def test_buscar_items_encuentra_por_nombre_o_descripcion():
    items = [
        _item("A", "Taladro", "Taladro percutor 20V"),
        _item("B", "Cemento", "Saco 25kg"),
    ]
    coincidencias, sugerencias = ch.buscar_items(items, "taladro")
    assert [it["n_ref"] for it in coincidencias] == ["A"]
    assert sugerencias == []


def test_buscar_items_ignora_items_excluidos():
    items = [_item("A", "Taladro", excluido="sin_master")]
    coincidencias, sugerencias = ch.buscar_items(items, "taladro")
    assert coincidencias == []
    assert sugerencias == []


def test_buscar_items_sin_match_devuelve_listas_vacias():
    items = [_item("A", "Cemento", "Saco 25kg")]
    coincidencias, sugerencias = ch.buscar_items(items, "taladro")
    assert coincidencias == []
    assert sugerencias == []


def test_buscar_items_separa_coincidencias_y_sugerencias_por_umbral(monkeypatch):
    items = [_item("A", "Uno"), _item("B", "Dos"), _item("C", "Tres")]
    puntajes = {"uno": 0.9, "dos": 0.5, "tres": 0.1}
    monkeypatch.setattr(ch, "similitud", lambda a, b: puntajes.get(b, 0.0))

    coincidencias, sugerencias = ch.buscar_items(items, "consulta")

    assert [it["n_ref"] for it in coincidencias] == ["A"]
    assert sugerencias == ["Dos"]


def test_buscar_items_ordena_coincidencias_de_mayor_a_menor_similitud(monkeypatch):
    items = [_item("A", "Uno"), _item("B", "Dos")]
    puntajes = {"uno": 0.7, "dos": 0.95}
    monkeypatch.setattr(ch, "similitud", lambda a, b: puntajes.get(b, 0.0))

    coincidencias, _sugerencias = ch.buscar_items(items, "consulta")

    assert [it["n_ref"] for it in coincidencias] == ["B", "A"]
