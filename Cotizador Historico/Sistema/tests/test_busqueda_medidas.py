# -*- coding: utf-8 -*-
"""Medidas: que 2", 2 pulgadas, 2 plg, Ø2" y DN50 sean la misma cosa, y que
2" NO sea lo mismo que 1/2", 3/4" ni 2.1/2".

La tabla de alias (busqueda.ALIAS_MEDIDA) existe para que el JavaScript del
dashboard no tenga que reimplementar la gramatica de medidas de taxonomia.py.
Eso solo es seguro si cada entrada de la tabla dice lo mismo que diria el
parser real -- de ahi el primer test, que las valida una por una.
"""
import busqueda
import taxonomia


# ── la tabla de alias no puede mentirle al parser ─────────────────────────

def test_cada_alias_de_pulgada_coincide_con_lo_que_diria_el_parser_real():
    """Cada alias, pasado por taxonomia.parsear_medidas, tiene que dar la
    medida canonica que la tabla promete.

    Sin este test la tabla es una segunda fuente de verdad que puede
    divergir en silencio del parser -- exactamente el problema que dejo la
    taxonomia duplicada en JavaScript hasta 2026-09-08."""
    revisados = 0
    for alias, canonico in busqueda.ALIAS_MEDIDA.items():
        if not canonico.endswith('"'):
            continue                          # los metricos se validan aparte
        if alias.startswith("dn"):
            continue                          # DN es una tabla, no gramatica
        medidas = taxonomia.parsear_medidas(busqueda._limpiar_para_medidas(alias))
        if not medidas:
            # Un entero pelado sin unidad ("2") no es medida para el parser
            # general; solo lo es en una consulta (ver parsear_consulta).
            entero = taxonomia.entero_pelado_como_pulgada([alias])
            assert entero is not None, f"alias {alias!r} no lo entiende nadie"
            assert entero.canonico() == canonico, f"alias {alias!r}"
        else:
            assert medidas[0].canonico() == canonico, f"alias {alias!r}"
        revisados += 1
    assert revisados > 200, "la tabla de alias quedo sospechosamente chica"


# ── todas las escrituras de 2 pulgadas son la misma medida ────────────────

ESCRITURAS_DE_DOS_PULGADAS = [
    '2"', "2''", "2”", "2“", "2 plg", "2 pulg", "2 pulgs",
    "2 pulgada", "2 pulgadas", "2 pg", "2 in", "2 inch",
    "Ø2\"", "Ø 2 pulg", "DN50", "dn 50",
]


def test_todas_las_escrituras_de_dos_pulgadas_dan_la_misma_medida():
    for escritura in ESCRITURAS_DE_DOS_PULGADAS:
        assert busqueda.medidas_de_consulta(escritura) == {'2"'}, escritura


def test_la_medida_se_detecta_dentro_de_una_frase():
    for frase in ('valvula de bola de 2"', "valvula bola 2 pulgadas",
                  "valvula esferica 2 in", "valvula de bola dn50"):
        assert '2"' in busqueda.medidas_de_consulta(frase), frase


def test_un_entero_suelto_en_una_consulta_es_el_calibre():
    # "valvula bola 2" es una valvula de 2 pulgadas, no dos valvulas.
    assert busqueda.medidas_de_consulta("valvula bola 2") == {'2"'}


# ── medidas parecidas son medidas distintas ───────────────────────────────

def test_dos_pulgadas_no_es_media_pulgada_ni_dos_y_media():
    dos = busqueda.medidas_de_consulta('2"')
    assert dos != busqueda.medidas_de_consulta('1/2"')
    assert dos != busqueda.medidas_de_consulta('2.1/2"')
    assert dos != busqueda.medidas_de_consulta('3/4"')


def test_la_fraccion_mixta_chilena_se_lee_en_sus_tres_escrituras():
    for escritura in ("1.1/4", "1-1/4", "1 1/4", '1.1/4"', "1.1/4 plg"):
        assert busqueda.medidas_de_consulta(escritura) == {'1.1/4"'}, escritura


def test_una_y_cuarto_no_se_confunde_con_un_cuarto():
    assert busqueda.medidas_de_consulta("1.1/4") != busqueda.medidas_de_consulta("1/4")


# ── DN: la unica pasarela metrico/pulgada, y en un solo sentido ───────────

def test_dn_se_traduce_a_pulgada_segun_la_tabla():
    assert busqueda.medidas_de_consulta("DN15") == {'1/2"'}
    assert busqueda.medidas_de_consulta("DN25") == {'1"'}
    assert busqueda.medidas_de_consulta("DN50") == {'2"'}


def test_una_pulgada_no_arrastra_los_milimetros():
    """2" NO trae los PPR de 50mm.

    Un tubo PPR de 50mm es diametro EXTERIOR y corresponde a DN40 (1.1/2"),
    no a DN50. Ligar 2" con "50mm" mezclaria calibres distintos -- lo mismo
    que la taxonomia evita al separar las hojas por medida."""
    assert busqueda.medidas_de_consulta('2"') == {'2"'}
    assert busqueda.medidas_de_consulta("50mm") == {"50mm"}


def test_los_milimetros_del_catalogo_se_reconocen_tal_cual():
    for escritura in ("32mm", "32 mm", "PPR 32mm"):
        assert "32mm" in busqueda.medidas_de_consulta(escritura), escritura


# ── la comilla es una unidad, nunca un operador ───────────────────────────

def test_la_comilla_no_se_interpreta_como_frase_exacta():
    """Soportar comillas como "frase exacta" romperia la consulta mas comun
    del modulo, donde la comilla son pulgadas."""
    terminos, medidas = busqueda.parsear_consulta('valvula de bola de 2"')
    assert medidas == {'2"'}
    assert "valvula" in terminos and "bola" in terminos


def test_las_palabras_de_la_medida_no_quedan_como_terminos_sueltos():
    # 'pulgada' no es un termino que ningun item cumpla: los items dicen 2".
    terminos, _medidas = busqueda.parsear_consulta("valvula 2 pulgadas")
    assert "pulgada" not in terminos
    assert terminos == ("valvula",)


# ── medidas del item: todas, no solo la principal ─────────────────────────

def test_el_item_aporta_todas_las_medidas_que_menciona():
    medidas = busqueda.medidas_de_item(
        "Termopozo", 'Termopozo SS316 PN40 1/2"NPT F x 1/2"NPT M, largo 100mm')
    assert '1/2"' in medidas
    assert "100mm" in medidas


def test_el_item_escrito_en_dn_responde_a_la_busqueda_en_pulgadas():
    medidas = busqueda.medidas_de_item("Válvula", "Válvula bola DN50 HI-HI")
    assert '2"' in medidas
