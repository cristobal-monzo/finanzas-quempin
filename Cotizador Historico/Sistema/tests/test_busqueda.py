# -*- coding: utf-8 -*-
"""Contrato de buscar_items: que encuentra, que descarta y en que orden.

Estos tests estaban escritos contra la funcion interna `similitud()` del
motor anterior (monkeypatcheandola para inyectar puntajes). Al reemplazar ese
motor por busqueda.py se reescribieron contra el COMPORTAMIENTO observable --
que encuentre el plural, que tolere el tipeo, que no enganche por una palabra
corta -- que es lo que los casos originales realmente protegian. Los tests de
puntaje fino viven ahora en test_busqueda_ranking.py.
"""
import busqueda
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


# ── buscar_items: que encuentra ───────────────────────────────────────────

def test_buscar_items_encuentra_nombre_no_simplificado_en_plural():
    # Nombre Item real sin simplificar (ver Centro de Costos/CLAUDE.md): el
    # primer termino calza con la consulta en plural, pero el string
    # completo no es substring uno del otro.
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


def test_buscar_items_tolera_un_error_de_tipeo():
    items = [_item("A", "Taladro", "Taladro percutor 20V"), _item("B", "Cemento", "Saco")]
    coincidencias, _sugerencias = ch.buscar_items(items, "taladr0")
    assert [it["n_ref"] for it in coincidencias] == ["A"]


def test_buscar_items_ignora_el_orden_de_las_palabras():
    items = [_item("A", "Válvula de bola", 'Válvula bola 2" HI-HI')]
    por_orden = ch.buscar_items(items, "valvula bola")[0]
    al_reves = ch.buscar_items(items, "bola valvula")[0]
    assert [i["n_ref"] for i in por_orden] == [i["n_ref"] for i in al_reves] == ["A"]


def test_buscar_items_ignora_palabras_vacias():
    items = [_item("A", "Tapón", "Tapón para oídos reusable")]
    assert ch.buscar_items(items, "tapon oido")[0] == ch.buscar_items(items, "tapon de oido")[0]


# ── buscar_items: que descarta ────────────────────────────────────────────

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


def test_buscar_items_no_inventa_un_producto_que_no_existe():
    items = [_item("A", "Bomba DAB", "Bomba dab circulacion en linea cp 50/2200 t-ie3")]
    coincidencias, _sugerencias = ch.buscar_items(items, "caldera")
    assert coincidencias == []


def test_buscar_items_no_engancha_por_una_palabra_corta_compartida():
    # "dab" (3 letras) es la marca, no el producto: compartirla no debe
    # bastar para que la bomba le gane a la caldera cuando se busca caldera.
    items = [
        _item("A", "Bomba DAB", "Bomba dab circulacion en linea cp 50/2200 t-ie3"),
        _item("B", "Caldera", "Caldera mural a gas 24 kW"),
    ]
    coincidencias, _sugerencias = ch.buscar_items(items, "caldera dab 150/280")
    assert coincidencias[0]["n_ref"] == "B"


# ── buscar_items: en que orden ────────────────────────────────────────────

def test_buscar_items_ordena_por_relevancia_no_por_orden_del_excel():
    # El que calza los dos terminos va primero, este donde este en la lista.
    items = [
        _item("A", "Válvula", "Válvula de retención vertical 2"),
        _item("B", "Válvula de bola", 'Válvula bola Bugatti 2"'),
    ]
    coincidencias, _sugerencias = ch.buscar_items(items, "valvula de bola")
    assert coincidencias[0]["n_ref"] == "B"


def test_buscar_items_prioriza_el_nombre_sobre_la_descripcion():
    items = [
        _item("A", "Grata circular", "Grata circular 3x3/35 para taladro"),
        _item("B", "Taladro", "Percutor 20V"),
    ]
    coincidencias, _sugerencias = ch.buscar_items(items, "taladro")
    assert coincidencias[0]["n_ref"] == "B"


# ── cuando la consulta se cumple solo a medias ────────────────────────────

def test_buscar_items_devuelve_el_pariente_cuando_el_producto_exacto_no_existe():
    # Preferible a una pantalla vacia: quien busca una valvula de compuerta
    # en un catalogo que solo tiene de bola quiere ver la de bola.
    items = [_item("A", "Válvula de bola", 'Válvula bola Bugatti 2"')]
    coincidencias, _sugerencias = ch.buscar_items(items, "valvula de compuerta")
    assert [it["n_ref"] for it in coincidencias] == ["A"]


def test_el_indice_declara_que_termino_no_encontro():
    # ...pero tiene que decir que "compuerta" no existe, o el usuario cree
    # que la valvula de bola es lo que pidio.
    items = [_item("A", "Válvula de bola", 'Válvula bola Bugatti 2"')]
    indice = busqueda.Indice(items)
    assert indice.terminos_sin_resultado("valvula de compuerta") == ("compuerta",)
    assert indice.terminos_sin_resultado("valvula de bola") == ()
