# -*- coding: utf-8 -*-
"""Tests de la ficha de atributos: material, dimensiones con su rol,
especificaciones tecnicas, terminacion y confianza.

Los casos vienen del catalogo real de Centro de Costos, pero SOLO con
nombre/descripcion de producto: nunca montos, proveedores ni numeros de
documento (ver CLAUDE.md raiz: los datos financieros no entran a git).

El principio que prueban (pedido del usuario, 2026-09-22):

    Un producto no se clasifica por su forma o sus dimensiones. Primero se
    identifica QUE es, despues DE QUE esta hecho y recien despues sus
    caracteristicas dimensionales y tecnicas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import atributos as at  # noqa: E402
import dimensiones as dm  # noqa: E402
import taxonomia as tx  # noqa: E402


def dims(nombre, descripcion=""):
    c = tx.clasificar(nombre, descripcion)
    return {rol: d["valor_mm"] for rol, d in c["dimensiones"].items()}


def pulgadas(nombre, descripcion=""):
    c = tx.clasificar(nombre, descripcion)
    return {rol: d.get("pulgadas") or dm.texto_dimension(rol, d)
            for rol, d in c["dimensiones"].items()}


# ═══════════════════════════════════════════════════════════════════════
# EL CASO CENTRAL DEL PEDIDO
# ═══════════════════════════════════════════════════════════════════════

def test_la_plancha_de_policarbonato_es_una_plancha_de_policarbonato():
    """El ejemplo del usuario, atributo por atributo."""
    c = tx.clasificar("Plancha policarbonato",
                      "Plancha policarbonato transparente 0,7 x 812 x 3660 mm")
    assert c["familia_producto"] == "Planchas"
    assert c["tipo"] == "Plancha"
    assert c["material"] == "Policarbonato"
    assert c["terminacion"] == ["Transparente"]
    assert dims("Plancha policarbonato",
                "Plancha policarbonato transparente 0,7 x 812 x 3660 mm") == {
        "espesor": 0.7, "ancho": 812.0, "largo": 3660.0}


def test_una_plancha_de_policarbonato_no_esta_en_la_categoria_de_las_maderas():
    policarbonato = tx.clasificar("Plancha policarbonato", "Plancha policarbonato 4mm")
    pino = tx.clasificar("Pino cepillado", "Pino seco cepillado 2x6 3,2 mt")
    assert policarbonato["categoria"] == "Planchas y Perfiles"
    assert pino["categoria"] == "Maderas"
    assert policarbonato["categoria"] != pino["categoria"]


def test_las_planchas_de_distinto_material_no_comparten_hoja():
    """El material define el producto: una plancha de policarbonato y una de
    acero del mismo espesor no se promedian."""
    poli = tx.clasificar("Plancha", "Plancha policarbonato 0,7 x 812 x 3660 mm")
    acero = tx.clasificar("Plancha", "Plancha de acero 0,7 x 812 x 3660 mm")
    assert tx.clave_hoja(poli) != tx.clave_hoja(acero)
    assert "Policarbonato" in tx.clave_hoja(poli)


# ═══════════════════════════════════════════════════════════════════════
# MATERIAL: QUE ES, QUE ES UN COMPONENTE Y QUE ES LA APLICACION
# ═══════════════════════════════════════════════════════════════════════

def test_materiales_que_el_sistema_anterior_no_conocia():
    assert tx.clasificar("Plancha zincalum", "Plancha zincalum 0,35")["material"] == "Zincalum"
    assert tx.clasificar("EPDM", "EPDM 3/16")["material"] == "EPDM"
    assert tx.clasificar("Plancha teflon", "Plancha teflón expandido 1/8")["material"] == "PTFE"
    assert tx.clasificar("Plancha", "Plancha graphinox 1/16")["material"] == "Grafito"


def test_el_grado_de_inoxidable_se_lee_y_no_se_confunde_con_una_medida():
    c = tx.clasificar("Tubo", "Tubo 1/4 acero inoxidable 316 x 6mts")
    assert c["material"] == "Acero inoxidable"
    assert c["material_grado"] == "AISI 316"
    assert c["dimensiones"]["diametro"]["pulgadas"] == '1/4"'


def test_ss316_y_aisi_304l_son_grados_del_mismo_material():
    assert tx.clasificar("Termopozo", 'Termopozo SS316 1/2"NPT')["material_grado"] == "AISI 316"
    assert tx.clasificar("Cañería", 'Cañería inoxidable ASTM A312 304L 6"')["material_grado"] == "AISI 304L"


def test_astm_a36_es_acero_al_carbono_no_acero_negro():
    """"ASTM" a secas era un alias de Acero Negro: una plancha A-36 quedaba
    como cañeria negra."""
    c = tx.clasificar("Plancha", "Plancha de acero 2,5 x 1000 x 3000 mm ASTM A-36")
    assert c["material"] == "Acero carbono"
    assert c["material_grado"] == "ASTM A36"


def test_el_material_de_la_aplicacion_no_es_el_del_producto():
    # un disco "para acero inoxidable" es un disco abrasivo, no de inoxidable
    disco = tx.clasificar("Disco de corte", "Disco de corte acero inoxidable 4.1/2 plg")
    assert disco["material"] is None
    assert disco["aplicacion"] == "Acero inoxidable"
    # ...y un adhesivo "para acero" es epoxico
    adhesivo = tx.clasificar("Adhesivo epoxico", "Adhesivo epoxico para acero")
    assert adhesivo["material"] == "Epoxi"
    assert adhesivo["aplicacion"] == "Acero carbono"


def test_el_material_de_un_componente_no_es_el_del_producto():
    mazo = tx.clasificar("Mazo de goma", "Mazo de goma con mango de acero, 16 oz")
    assert mazo["material"] == "Caucho"
    visor = tx.clasificar("Visor", "Visor policarbonato c/marco aluminio")
    assert visor["material"] == "Policarbonato"


def test_la_herramienta_conserva_el_material_del_que_esta_hecha():
    # "Broca p/metal HSS": corta metal, pero es de acero rapido
    c = tx.clasificar("Broca", "Broca p/metal HSS 12mm")
    assert c["material"] == "Acero rápido (HSS)"


def test_un_fitting_de_laton_para_pex_es_de_laton_y_del_sistema_pex():
    c = tx.clasificar("Terminal", "Terminal DZR PEX HE 32x1")
    assert c["material"] == "Latón"
    assert c["sistema"] == "PEX"
    # la carpeta sigue siendo la del sistema, que es como se busca
    assert c["subcategoria"] == "PEX"


def test_teflon_liquido_no_es_una_pieza_de_ptfe():
    c = tx.clasificar("Teflon liquido", "Teflón líquido anaeróbico 050 ML")
    assert c["material"] is None


# ═══════════════════════════════════════════════════════════════════════
# DIMENSIONES: EL SIGNIFICADO DEPENDE DE LA FAMILIA
# ═══════════════════════════════════════════════════════════════════════

def test_en_un_perfil_los_tres_numeros_son_ancho_alto_y_espesor():
    assert dims("Perfil", "Perfil rectangular 40x20x2 mm") == {
        "ancho": 40.0, "alto": 20.0, "espesor": 2.0}


def test_un_perfil_cuadrado_con_dos_numeros_tiene_el_lado_repetido():
    assert dims("Tubo cuadrado", "Tubo cuad neg 40x2mm") == {
        "ancho": 40.0, "alto": 40.0, "espesor": 2.0}


def test_el_largo_del_perfil_no_se_confunde_con_la_seccion():
    assert dims("Perfil", "Perfil cuadrado 40 x 40 x 2 mm x 6 m") == {
        "ancho": 40.0, "alto": 40.0, "espesor": 2.0, "largo": 6000.0}


def test_en_la_madera_la_escuadria_va_en_pulgadas_y_el_largo_en_metros():
    assert pulgadas("Pino cepillado", "Pino seco cepillado 2x6 3,2 mt") == {
        "ancho": '2"', "alto": '6"', "largo": "3,2 m"}


def test_dos_escuadrias_distintas_de_pino_no_comparten_hoja():
    """El sistema anterior leia solo el largo (3,2 m) y promediaba un 2x6
    con un 1x6."""
    a = tx.clasificar("Pino cepillado", "Pino seco cepillado 2x6 3,2 mt")
    b = tx.clasificar("Pino cepillado", "Pino seco cepillado 1x6 3,2 mt")
    assert tx.clave_agrupacion(a) != tx.clave_agrupacion(b)


def test_en_una_barra_pex_el_numero_suelto_es_el_diametro_no_el_largo():
    """Las tres barras PEX (16, 20 y 32 mm) compartian hoja porque la unica
    medida que se leia era el largo de la barra (5,8 m)."""
    assert dims("Cañeria PEX", "PEX-A Aqualine 32 barra 5.8mts") == {
        "diametro": 32.0, "largo": 5800.0}
    a = tx.clasificar("Cañeria PEX", "PEX-A Aqualine 32 barra 5.8mts")
    b = tx.clasificar("Cañeria PEX", "PEX-A Aqualine 16 barra 5.8mt")
    assert tx.clave_agrupacion(a) != tx.clave_agrupacion(b)


def test_la_caneria_ppr_trae_diametro_exterior_espesor_y_largo():
    assert dims("Cañeria PPR", "Cañeria PPR serie 3.2 (PN-16) 040x5.5, 5.8m") == {
        "diametro": 40.0, "espesor": 5.5, "largo": 5800.0}


def test_una_reduccion_conserva_los_dos_diametros():
    assert pulgadas("Bushing", "Bushing galvanizado 1 1/4\"x1\"") == {
        "diametro": '1.1/4"', "diametro_salida": '1"'}
    # ...aunque entre medio vengan las conexiones
    assert pulgadas("Bushing", "Bushing de bronce para agua 1/2 HE x 3/8 HI") == {
        "diametro": '1/2"', "diametro_salida": '3/8"'}


def test_en_una_tee_el_tercer_diametro_es_la_derivacion():
    assert pulgadas("Tee", 'Tee de bronce 3/4" x 3/4" x 1/2" SO x SO x HI') == {
        "diametro": '3/4"', "diametro_derivacion": '1/2"'}


def test_en_un_perno_el_diametro_es_el_menor_este_escrito_donde_este():
    assert pulgadas("Perno hexagonal", "Perno hexagonal G-2 (30) 5x5/8 plg") == {
        "diametro": '5/8"', "largo": '5"'}
    assert pulgadas("Perno", "Perno hex zincado 3/4x3 1/2") == {
        "diametro": '3/4"', "largo": '3.1/2"'}


def test_la_rosca_de_un_perno_no_es_otra_medida():
    """"5/8-11" es un perno de 5/8" con 11 hilos por pulgada: el sistema
    anterior leia "11x5"."""
    c = tx.clasificar("Perno", 'Perno hexagonal zincado GR.2 UNC 5/8-11 x 5"')
    assert c["dimensiones"]["diametro"]["pulgadas"] == '5/8"'
    assert c["dimensiones"]["largo"]["pulgadas"] == '5"'
    assert c["especificaciones"]["hilos_por_pulgada"] == "11"


def test_un_perno_metrico_se_lee_en_milimetros():
    assert dims("Perno", "Perno M10 x 50") == {"diametro": 10.0, "largo": 50.0}
    assert dims("Tuerca", "Tuerca hexagonal metrica M8") == {"diametro": 8.0}


def test_un_disco_de_4_y_medio_tambien_se_conoce_como_de_115mm():
    c = tx.clasificar("Disco de corte", "Disco corte metal 4 1/2")
    assert c["dimensiones"]["diametro"]["pulgadas"] == '4.1/2"'
    assert "115mm" in c["medidas_equivalentes"]


def test_el_angulo_de_un_codo_no_es_su_diametro():
    assert dims("Codo", "Codo PPR 90 032") == {"diametro": 32.0}
    assert tx.clasificar("Codo", "Codo PPR 90 032")["especificaciones"]["angulo"] == "90°"
    # ...pero un codo de 90 mm si mide 90 mm
    assert dims("Codo", "Codo PPR 90mm PN20") == {"diametro": 90.0}


def test_dn50_son_dos_pulgadas():
    c = tx.clasificar("Flange", "Flange DN50 PN16")
    assert c["dimensiones"]["diametro"]["pulgadas"] == '2"'
    assert c["especificaciones"]["presion"] == "PN16"


def test_el_largo_de_un_niple_no_se_lee_como_su_diametro():
    assert pulgadas("Niple galvanizado", "Niple galvanizado ISO BSP-BSP 08cm (09) 1.1/2 plg") == {
        "diametro": '1.1/2"', "largo": "80 mm"}


def test_una_cinta_se_mide_por_su_ancho_y_su_largo():
    assert dims("Cinta aluminio", "Cinta aluminio 50mmx50mt") == {
        "ancho": 50.0, "largo": 50000.0}


def test_la_coquilla_trae_espesor_diametro_interior_y_largo():
    assert dims("Coquilla aislante", "Coquilla Aiscom espesor 25mm Ø54mm x 2mt") == {
        "espesor": 25.0, "diametro": 54.0, "largo": 2000.0}


def test_una_cantidad_entre_parentesis_no_es_una_medida():
    # "(0,06 planchas)" es cuanto se compro, no cuanto mide
    assert dims("Plancha teflon", "Plancha teflón expandido 1/8 x 1,5mt x 1,5mt (0,06 planchas)") == {
        "espesor": 3.175, "ancho": 1500.0, "largo": 1500.0}


def test_los_amperes_solo_se_leen_en_un_producto_electrico():
    """"Válvula retención Bugatti 2 A/BR" perdia su medida de 2" porque el
    "2 A" se leia como 2 amperes."""
    assert pulgadas("Valvula retencion", "Válvula retención vertical Bugatti 2 A/BR HI HI") == {
        "diametro": '2"'}
    assert tx.clasificar("Contactor", "Contactor 25A AC3 bobina 230VcA")["especificaciones"][
        "corriente"] == "25 A"


# ═══════════════════════════════════════════════════════════════════════
# ESPECIFICACIONES TECNICAS
# ═══════════════════════════════════════════════════════════════════════

def test_schedule_norma_y_grado_de_una_caneria():
    c = tx.clasificar("Cañería", 'Cañería de acero inoxidable con costura ASTM A312 304L, 6" SCH10S')
    assert c["especificaciones"]["schedule"] == "SCH 10S"
    assert c["especificaciones"]["norma"] == "ASTM A312"
    assert c["material_grado"] == "AISI 304L"


def test_conexiones_y_rosca_de_un_fitting():
    c = tx.clasificar("Válvula", 'Válvula bola Bugatti P/T 2" HI-HI M/MET')
    assert c["especificaciones"]["conexion"] == "HI-HI"
    assert c["especificaciones"]["paso"] == "Paso total"
    assert tx.clasificar("Codo 90 galvanizado 1 NPT", "")["especificaciones"]["rosca"] == "NPT"


def test_el_tipo_de_pared_de_una_caneria_de_cobre_parte_la_hoja():
    """Una cañeria de cobre tipo L y una tipo K no valen lo mismo."""
    l = tx.clasificar("Cañería", 'Cañería de cobre tipo L 1/2"')
    k = tx.clasificar("Cañería", 'Cañería de cobre tipo K 1/2"')
    assert l["especificaciones"]["tipo_pared"] == "Tipo L"
    assert tx.clave_hoja(l) != tx.clave_hoja(k)


def test_la_clase_de_un_electrodo_es_su_norma_aws():
    assert tx.clasificar("Electrodo", "Electrodo 7018 1/8 5kg")["especificaciones"]["norma"] == "AWS E7018"


def test_la_ley_de_la_soldadura_de_plata():
    assert tx.clasificar("Soldadura plata", "Soldadura plata 15% display")["especificaciones"]["ley"] == "15%"


# ═══════════════════════════════════════════════════════════════════════
# TERMINACION Y COLOR
# ═══════════════════════════════════════════════════════════════════════

def test_la_terminacion_es_un_atributo_aparte_del_material():
    c = tx.clasificar("Plancha", "Plancha galvanizada lisa 0,8 x 1000 x 3000 mm")
    assert c["material"] == "Acero galvanizado"
    assert "Lisa" in c["terminacion"]


def test_el_color_no_se_confunde_con_la_terminacion_ni_con_el_material():
    c = tx.clasificar("Poleron", "Polerón térmico negro talla L")
    assert c["material"] is None
    assert c["color"] == "Negro"


# ═══════════════════════════════════════════════════════════════════════
# CONFIANZA Y REVISION
# ═══════════════════════════════════════════════════════════════════════

def test_un_producto_bien_descrito_tiene_confianza_alta():
    c = tx.clasificar("Codo bronce", "Codo SO BR (05) 1.1/4 plg")
    assert c["confianza"] >= 0.9
    assert c["revisar"] is False


def test_dos_materiales_en_el_texto_bajan_la_confianza_y_piden_revision():
    c = tx.clasificar("Union americana", "U Amer Aj Br galvanizada Mecha (08) 2 plg")
    assert c["confianza"] < 0.7
    assert c["revisar"] is True
    assert any("dos materiales" in m for m in c["motivos_revision"])


def test_lo_que_no_se_puede_interpretar_queda_anotado_no_inventado():
    c = tx.clasificar("Zxqwy", "Producto sin ninguna palabra conocida")
    assert c["categoria"] == "Sin Clasificar"
    assert c["revisar"] is True
    assert "tipo" in c["faltantes"]


def test_una_palabra_desconocida_se_reporta_con_una_sugerencia():
    conocido = at.vocabulario_conocido()
    assert at.sin_interpretar("Esmalte Suvinil", conocido) == ["suvinil"]
    assert at._sugerencia_para("suvinil", conocido, 1) == "¿marca o modelo?"
    # una palabra que el sistema ya entiende no se reporta
    assert at.sin_interpretar("Codo de bronce", conocido) == []


def test_el_nombre_original_se_conserva_junto_al_normalizado():
    c = tx.clasificar("Plancha policarbonato",
                      "Plancha policarbonato transparente 0,7 x 812 x 3660 mm")
    assert c["nombre_original"].startswith("Plancha policarbonato — Plancha policarbonato")
    assert c["nombre_normalizado"] == "plancha policarbonato transparente 0.7 812 3660 mm"
