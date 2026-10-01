# -*- coding: utf-8 -*-
"""El nombre corto con que se reconoce a cada proveedor.

Lo que hay entre parentesis en una razon social NO siempre es la marca: en el
libro real tambien aparece el local, la comuna, el dueño o una nota del
ticket. Quedarse siempre con la primera palabra de ahi producia etiquetas
como "San", "Viña" o "concesionaria", que ademas juntaban empresas sin
relacion (revision 2026-09-23).
"""
import auditor_centro_costos as acc
import pytest


@pytest.fixture(autouse=True)
def sin_registro():
    """Cada test declara los proveedores que el libro conoce; ninguno hereda
    los del anterior."""
    acc.PROVEEDORES_CONOCIDOS.clear()
    yield
    acc.PROVEEDORES_CONOCIDOS.clear()


def test_el_parentesis_con_una_marca_sigue_mandando():
    assert acc.generar_tag_proveedor("Comercial Silva Ltda. (Copec)") == "Copec"
    assert acc.generar_tag_proveedor(
        "Estaciones de Servicios Fandos Ltda. (Shell Ruta 68)") == "Shell"


def test_el_parentesis_con_una_comuna_no_parte_al_proveedor():
    """Sodimac aparecia bajo cuatro etiquetas: "Sodimac", "San", "Belloto" y
    "Sodimac /"."""
    acc.registrar_proveedores_conocidos(["Sodimac S.A."])
    assert acc.generar_tag_proveedor("Sodimac S.A. (San Felipe)") == "Sodimac"
    assert acc.generar_tag_proveedor("Sodimac S.A. (Belloto)") == "Sodimac"


def test_sin_el_registro_no_se_inventa_un_proveedor_conocido():
    # Mismo nombre, pero el libro no conoce a Sodimac a secas: cae a la regla
    # de limpieza, no a un tag adivinado.
    assert acc.generar_tag_proveedor("Sodimac S.A. (San Felipe)") == "Sodimac"


def test_la_marca_le_gana_al_proveedor_conocido():
    """"Horta y Horta Limitada" existe sola en el libro, pero
    "Horta y Horta Limitada (Copec)" es una estacion Copec."""
    acc.registrar_proveedores_conocidos(["Horta y Horta Limitada"])
    assert acc.generar_tag_proveedor("Horta y Horta Limitada (Copec)") == "Copec"
    assert acc.generar_tag_proveedor("Horta y Horta Limitada") == "Horta Horta"


def test_un_articulo_solo_no_identifica_a_nadie():
    # "El" agrupaba tres proveedores distintos; el nombre de fantasia son dos
    # palabras.
    assert acc.generar_tag_proveedor(
        "Gastronomia Condell Limitada (El Guaton, Valparaiso)") == "El Guaton"
    assert acc.generar_tag_proveedor(
        "Luis Enrique Cachay Rebaza (Donde Camilo)") == "Donde Camilo"


def test_un_articulo_seguido_de_comuna_no_es_nombre_de_fantasia():
    assert acc.generar_tag_proveedor("Hashtags (El Quisco)") == "Hashtags"


def test_una_direccion_entre_parentesis_no_es_marca():
    assert acc.generar_tag_proveedor("Dolce Luna (1 Sur 26, Longaví)") == "Dolce Luna"


def test_un_documento_de_dos_empresas_se_atribuye_a_la_primera():
    # El tag quedaba literalmente "Sodimac /".
    acc.registrar_proveedores_conocidos(["Sodimac S.A."])
    assert acc.generar_tag_proveedor(
        "Sodimac S.A. / Estacionar S.A. / Central Parking System Chile S.A.") == "Sodimac"


def test_el_tag_no_termina_en_una_palabra_que_no_dice_nada():
    assert acc.generar_tag_proveedor("Ferreteria San Luis (Putaendo)") == "Ferreteria San Luis"
    assert acc.generar_tag_proveedor("Sabor a Cris (Quilpue)") == "Sabor a Cris"


def test_la_cola_despues_de_la_coma_no_cambia_el_proveedor():
    """Dos documentos del mismo proveedor traian la fecha pegada al nombre y
    quedaban como dos proveedores distintos."""
    a = acc.generar_tag_proveedor("Administradora de Franquicias El Horreo, 21-01-2026")
    b = acc.generar_tag_proveedor("Administradora de Franquicias El Horreo, 19-01-2026")
    assert a == b == "El Horreo"


def test_lo_curado_manda_sobre_toda_regla():
    assert acc.generar_tag_proveedor("Comercial ANWO S.A.") == "Anwo"
    assert acc.generar_tag_proveedor(
        "Jose Manuel Martinez Michelis y Compañia Limitada") == "Martínez Michelis"


def test_el_registro_solo_admite_nombres_sin_ambiguedad():
    """Una razon social con parentesis o con "/" nombra a mas de una cosa: no
    sirve como referencia de "quien es este proveedor a secas"."""
    acc.registrar_proveedores_conocidos([
        "Sodimac S.A.",
        "Comercial Silva Ltda. (Copec)",
        "Sodimac S.A. / Estacionar S.A.",
    ])
    assert list(acc.PROVEEDORES_CONOCIDOS.values()) == ["Sodimac"]
