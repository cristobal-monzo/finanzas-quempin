# -*- coding: utf-8 -*-
"""Como se ESCRIBE lo que el motor ya entendio.

La regla que ordena todo este archivo: la escritura legible nunca reemplaza
a la canonica, la acompana. Si alguna vez vuelven a ser una sola cadena, el
buscador deja de calzar medidas -- ver test_la_hoja_canonica_no_cambia.
"""
import cotizador_historico as ch
import presentacion as P
import taxonomia


# ---------------------------------------------------------------------------
# MEDIDAS
# ---------------------------------------------------------------------------
def test_de_un_metro_para_arriba_se_escribe_en_metros():
    assert P.medida_texto(20000) == "20 m"
    assert P.medida_texto(3600) == "3,6 m"
    assert P.medida_texto(1000) == "1 m"


def test_bajo_el_metro_se_queda_en_milimetros():
    # 115 mm es un disco de corte; "11,5 cm" seria igual de ilegible al reves.
    assert P.medida_texto(115) == "115 mm"
    assert P.medida_texto(0.7) == "0,7 mm"
    assert P.medida_texto(999) == "999 mm"


def test_la_coma_es_el_separador_decimal():
    assert P.numero(2.5) == "2,5"
    assert P.numero(3) == "3"


def test_un_grupo_de_medidas_comparte_unidad():
    # Una plancha se vende "0,7 x 812 x 3660 mm": pasar solo el largo a metros
    # obligaria a leer dos unidades en la misma linea.
    assert P.grupo_texto([0.7, 812, 3660]) == "0,7 x 812 x 3660 mm"
    # Un rollo de teflon de 1 x 10 m: las dos llegan al metro, las dos cambian.
    assert P.grupo_texto([1000, 10000]) == "1 x 10 m"


# ---------------------------------------------------------------------------
# NOMBRES
# ---------------------------------------------------------------------------
def test_la_marca_se_escribe_como_el_catalogo():
    assert P.nombre_presentable("Radiador doble ANWO DK500/1400") == \
        "Radiador doble Anwo DK500/1400"


def test_las_siglas_tecnicas_no_se_capitalizan_a_medias():
    # Una regla generica de "capitalizar" convierte PVC en Pvc.
    assert P.nombre_presentable("Codo PVC 1/2 bsp") == "Codo PVC 1/2 BSP"


def test_lo_que_no_esta_en_el_catalogo_queda_igual():
    texto = "Bolsa basura jardin 10 un"
    assert P.nombre_presentable(texto) == texto


# ---------------------------------------------------------------------------
# ORTOGRAFIA LEIDA DEL PROPIO CATALOGO
# ---------------------------------------------------------------------------
def test_gana_la_palabra_con_tilde():
    mapa = P.unificar_ortografia(["Hidrolavadora portatil", "Hidrolavadora portátil"])
    assert mapa["portatil"] == "portátil"
    assert P.aplicar_ortografia("Hidrolavadora portatil", mapa) == "Hidrolavadora portátil"


def test_se_respeta_la_mayuscula_del_original():
    mapa = P.unificar_ortografia(["valvula de bola", "válvula de bola", "Valvula de bola"])
    assert P.aplicar_ortografia("Valvula de bola", mapa) == "Válvula de bola"


def test_las_palabras_cortas_no_se_tocan():
    # "mas"/"mas con tilde" y "solo"/"solo con tilde" son palabras DISTINTAS:
    # la regla de tildes elegiria mal la mitad de las veces.
    mapa = P.unificar_ortografia(["mas barato", "más barato", "solo uno", "sólo uno"])
    assert "mas" not in mapa
    assert "solo" not in mapa


def test_la_enye_no_es_una_tilde():
    # En NFD la enye se decompone como una n con tilde: confundirlas
    # convertiria "cana" en "caña" y "ano" en "año".
    mapa = P.unificar_ortografia(["cana de pescar", "caña de pescar"])
    assert "cana" not in mapa


def test_sin_variantes_no_hay_cambios():
    assert P.unificar_ortografia(["tuberia de cobre", "tuberia de cobre"]) == {}


# ---------------------------------------------------------------------------
# NOMBRES QUE SOLO EXISTEN EN LOS DATOS
# ---------------------------------------------------------------------------
def test_un_proveedor_escrito_de_dos_formas_queda_en_una():
    mapa = P.unificar_nombres(["ANWO", "Anwo", "Anwo"])
    assert mapa["ANWO"] == "Anwo"
    assert mapa["Anwo"] == "Anwo"


def test_en_un_nombre_propio_manda_la_tilde_aunque_sea_menos_frecuente():
    # "Quilpue" sin tilde es una falta, no una variante: aparece 6 veces
    # contra 1 y aun asi pierde.
    mapa = P.unificar_nombres(["Quilpue"] * 6 + ["Quilpué"])
    assert mapa["Quilpue"] == "Quilpué"


def test_nombres_distintos_no_se_mezclan():
    mapa = P.unificar_nombres(["Sodimac", "Sodiper"])
    assert mapa["Sodimac"] == "Sodimac"
    assert mapa["Sodiper"] == "Sodiper"


# ---------------------------------------------------------------------------
# LA FICHA COMPLETA
# ---------------------------------------------------------------------------
def test_la_medida_viaja_en_dos_escrituras():
    c = taxonomia.clasificar("Extension Halux de 20 metros", "")
    assert c["medida"] == "20000mm"        # la que compara el buscador
    assert c["medida_texto"] == "20 m"     # la que se lee


def test_la_hoja_canonica_no_cambia():
    """La hoja se indexa: escrita "3/4" x 1/2"" deja de calzar con la
    consulta "reduccion cobre 3/4 x 1/2", que el buscador junta en un solo
    termino. Paso de verdad al escribir esta mejora."""
    c = taxonomia.clasificar("Reduccion cobre 3/4 x 1/2", "")
    assert taxonomia.clave_hoja(c).endswith('3/4x1/2"')
    assert taxonomia.clave_hoja(c, presentable=True).endswith('3/4" x 1/2"')


def test_la_plancha_del_ejemplo_se_lee_entera():
    c = taxonomia.clasificar("Plancha policarbonato transparente 0,7 x 812 x 3660 mm", "")
    assert taxonomia.clave_hoja(c, presentable=True) == \
        "Plancha de Policarbonato 0,7 x 812 x 3660 mm"


def test_unificar_escritura_no_toca_el_texto_original():
    """El nombre y la descripcion son el registro de lo que decia la
    factura: se unifica la etiqueta que se muestra, no la fuente."""
    compras = [ch.agregar_taxonomia({"nombre_item": "Hidrolavadora Karcher portatil",
                                     "descripcion": "", "proveedor_tag": "Quilpue"}),
               ch.agregar_taxonomia({"nombre_item": "Hidrolavadora Karcher portátil",
                                     "descripcion": "", "proveedor_tag": "Quilpué"})]
    ch.unificar_escritura(compras)
    assert compras[0]["nombre_item"] == "Hidrolavadora Karcher portatil"
    assert {c["hoja_texto"] for c in compras} == {"Hidrolavadora Karcher portátil"}
    assert {c["proveedor_tag"] for c in compras} == {"Quilpué"}
