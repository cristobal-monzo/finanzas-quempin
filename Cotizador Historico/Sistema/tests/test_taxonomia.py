# -*- coding: utf-8 -*-
"""Tests de la taxonomia del Cotizador Historico (medidas + clasificacion).

Los casos vienen del catalogo real de Centro de Costos, pero SOLO con
nombre/descripcion de producto: nunca montos, proveedores ni numeros de
documento (ver CLAUDE.md raiz: los datos financieros no entran a git).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import taxonomia as tx


# ── gramatica de medidas: fracciones mixtas ───────────────────────────────
# El bug original: "1.1/4" (una pulgada y cuarto) se leia "1/4", y una
# canieria de 1.1/4 terminaba promediada con una de 1/4.

def test_fraccion_mixta_con_punto_no_se_lee_como_fraccion_sola():
    assert tx.medida_canonica("Codo bronce", "Codo SO BR (05) 1.1/4 plg") == '1.1/4"'


def test_fraccion_mixta_con_espacio_no_se_lee_como_fraccion_impropia():
    # "1 1/2" no es "11/2" (once medios): el espacio separa entero y fraccion
    assert tx.medida_canonica("Tee galvanizada 1 1/2", "") == '1.1/2"'


def test_fraccion_mixta_con_guion():
    assert tx.medida_canonica("Electrodo", "Electrodo E6011 2,5-3/32 1KG") == '3/32"'


def test_fraccion_simple_se_mantiene():
    assert tx.medida_canonica("Copla", "Copla Hi-Hi BR 1/2 plg") == '1/2"'


def test_cuatro_y_medio_no_es_un_medio():
    assert tx.medida_canonica("Disco de corte", "Disco de corte acero inox 4.1/2 plg") == '4.1/2"'


# ── unidades ──────────────────────────────────────────────────────────────

def test_plg_es_pulgada():
    # "plg" es la abreviatura que usa el catalogo real; sin ella el item
    # quedaba sin medida y (antes) invisible en el dashboard.
    assert tx.medida_canonica("Copla cobre", "Copla SO cobre (04) 1 plg") == '1"'


def test_pulgadas_escrito_completo():
    assert tx.medida_canonica("Caneria", "Caneria ERW ASTM A53 GR B 8 pulgadas") == '8"'


def test_comilla_es_pulgada():
    assert tx.medida_canonica("Válvula bola", 'Válvula bola 1.1/4" Taumm') == '1.1/4"'


def test_milimetros():
    assert tx.medida_canonica("Copla PVC", "Copla PVC cementada de 50 mm") == "50mm"


def test_centimetros_se_normalizan_a_milimetros():
    assert tx.medida_canonica("Aislante", "Aislante flexible 10 cm") == "100mm"


# ── prioridad: el diametro nominal manda sobre el largo ────────────────────

def test_pulgada_gana_sobre_el_largo_en_centimetros():
    # El 08cm es el largo del niple; su medida identificatoria es 1.1/2"
    assert tx.medida_canonica("Niple galvanizado",
                              "Niple galvanizado ISO BSP-BSP 08cm (09) 1.1/2 plg") == '1.1/2"'


def test_una_fraccion_es_pulgada_aunque_el_grupo_traiga_unidad_metrica():
    assert tx.medida_canonica("Punta negra", "Punta negra trefilada BSP 2.1/2x10cm") == '2.1/2"'


# ── medidas compuestas (reducciones) ──────────────────────────────────────

def test_compuesta_conserva_ambos_diametros():
    # Un bushing 1.1/2x1.1/4 no es el mismo producto que uno 1.1/2x1
    assert tx.medida_canonica("Bushing", "Bushing galv Tupy 1.1/2x1.1/4 plg") == '1.1/2x1.1/4"'


def test_compuesta_hereda_la_unidad_del_final_del_grupo():
    assert tx.medida_canonica("Tee reductora", "Tee reduc SO BR 2x3/4 plg") == '2x3/4"'


def test_compuesta_de_componentes_iguales_se_muestra_una_vez():
    assert tx.medida_canonica("Conector", "Conector macho inoxidable 1/2x1/2") == '1/2"'


# ── la medida tambien se lee del nombre, no solo de la descripcion ─────────

def test_medida_en_el_nombre_del_item():
    assert tx.medida_canonica("Codo 45 galvanizado 1/2", "Cod. 988100064") == '1/2"'


# ── lo que NO es una medida ───────────────────────────────────────────────

def test_modelo_con_barra_no_es_una_medida():
    # "VA 65/180" es el modelo de la bomba; la medida es la union de 1.1/4"
    assert tx.medida_canonica("Kit bomba",
                              'Kit bomba DAB rotor humedo VA 65/180 X, union 1.1/4" 220V') == '1.1/4"'


def test_denominador_que_no_es_de_pulgada_se_descarta():
    assert tx.medida_canonica("Termostato", "Termostato 105C Power HT+ 1.50/1.70/1.90") is None


def test_codigo_de_producto_no_es_una_medida():
    assert tx.medida_canonica("Caldera", "Caldera Anwo Agua Plus 2.0, 40/42 LPG") is None


def test_entero_pelado_sin_unidad_no_es_una_medida():
    assert tx.medida_canonica("Gasolina 93", "Gasolina 93 octanos") is None


def test_magnitudes_que_no_son_longitud_no_son_medidas():
    assert tx.medida_canonica("Silicona", "Silicona alta temperatura 280ml") is None
    assert tx.medida_canonica("Enchufe", "Enchufe macho 10A 2P+T blanco") is None


# ── clasificacion: match por palabra completa, nunca por substring ─────────

def test_no_clasifica_por_substring_dentro_de_otra_palabra():
    # "Steelgen" contiene "tee": con match por substring caia en Piping
    c = tx.clasificar("Buzo desechable", "Buzo desechable Steelgen Plus L blanco")
    assert c["categoria"] == "Seguridad Industrial (EPP)"


def test_conector_de_lenguaje_no_activa_una_familia():
    # "dado que" hacia que un combustible se clasificara como herramienta
    c = tx.clasificar("Combustible", "Gasolina 95 octanos, dado que la boleta es ilegible")
    assert c["categoria"] == "Transporte y Logística"


def test_negacion_no_activa_la_regla():
    # "s/abrazadera" (SIN abrazadera) no convierte un soplete en fitting
    c = tx.clasificar("Soplete de gas", "Soplete gas c/2 boquillas s/manguera s/abrazadera")
    assert c["categoria"] == "Soldadura y Gases"


def test_plural_y_singular_caen_en_la_misma_familia():
    a = tx.clasificar("Guante", "Guante cabritilla sin forro gris")
    b = tx.clasificar("Guantes", "Pack de guantes de cabritilla sin forro, 10 pares")
    assert a["familia"] == b["familia"] == "Guante"


def test_acentos_y_mayusculas_no_separan_familias():
    a = tx.clasificar("Valvula bola", "Valvula bola 2 plg")
    b = tx.clasificar("Válvula de bola", "Válvula de bola 2 plg")
    assert a["familia"] == b["familia"]


def test_el_nombre_pesa_mas_que_la_descripcion():
    # "lija al agua": lija (nombre) manda sobre agua (descripcion)
    c = tx.clasificar("Lija", "Lija al agua para fierro")
    assert c["categoria"] == "Abrasivos y Corte"


def test_frase_especifica_gana_a_la_palabra_generica():
    c = tx.clasificar("Tapones para oídos", "Tapones de protección para oídos, par")
    assert c["categoria"] == "Seguridad Industrial (EPP)"


def test_item_de_transporte_no_es_piping_por_mencionar_caneria():
    c = tx.clasificar("Flete expreso a domicilio", "2 bultos, 12 kg - abrazaderas / canerias")
    assert c["categoria"] == "Transporte y Logística"


# ── material como faceta ──────────────────────────────────────────────────

def test_detecta_materiales_que_el_sistema_anterior_no_conocia():
    assert tx.clasificar("Copla PVC", "Copla PVC cementada de 50 mm")["material"] == "PVC"
    assert tx.clasificar("Cañeria PEX", "PEX-A Aqualine 32 barra")["material"] == "PEX"


def test_abreviatura_de_material_del_catalogo():
    assert tx.clasificar("Codo", "Codo BR 90 3/4 SO/HE")["material"] == "Bronce"
    assert tx.clasificar("Bushing", "Bushing galv Tupy 1.1/2 plg")["material"] == "Galvanizado"


def test_piping_es_una_sola_categoria_con_el_material_como_faceta():
    cobre = tx.clasificar("Codo cobre", "Codo SO cobre (05) 1 plg")
    bronce = tx.clasificar("Codo bronce", "Codo SO BR (05) 1 plg")
    assert cobre["categoria"] == bronce["categoria"] == "Piping y Fittings"
    assert cobre["material"] != bronce["material"]


# ── clave de hoja: la unidad de comparacion de precios ────────────────────

def test_la_hoja_separa_medidas_distintas():
    a = tx.clave_hoja(tx.clasificar("Codo bronce", "Codo SO BR (05) 1.1/4 plg"))
    b = tx.clave_hoja(tx.clasificar("Codo bronce", "Codo SO BR (05) 1/4 plg"))
    assert a != b


def test_la_hoja_separa_materiales_distintos():
    a = tx.clave_hoja(tx.clasificar("Codo cobre", "Codo SO cobre 1/2 plg"))
    b = tx.clave_hoja(tx.clasificar("Codo bronce", "Codo SO BR 1/2 plg"))
    assert a != b


def test_la_hoja_une_el_mismo_producto_escrito_distinto():
    a = tx.clave_hoja(tx.clasificar("Copla cobre", "Copla SO cobre (04) 1 plg"))
    b = tx.clave_hoja(tx.clasificar("Copla de cobre", 'Copla cobre 1"'))
    assert a == b


def test_hoja_sin_medida_queda_marcada_pero_no_se_oculta():
    c = tx.clasificar("Codo bronce", "Codo bronce SO-SO")
    assert c["medida"] is None
    assert c["requiere_medida"] is True
    assert "sin medida" in tx.clave_hoja(c)


# ── gastos vs productos cotizables ────────────────────────────────────────

def test_los_gastos_de_operacion_no_son_cotizables():
    assert tx.clasificar("Peaje", "Peaje de autopista")["cotizable"] is False
    assert tx.clasificar("Almuerzo", "Almuerzo equipo en terreno")["cotizable"] is False


def test_los_productos_si_son_cotizables():
    assert tx.clasificar("Codo bronce", "Codo SO BR 1/2 plg")["cotizable"] is True


# ── nada se pierde: todo item cae en alguna categoria ─────────────────────

def test_item_irreconocible_cae_en_sin_clasificar_no_en_un_cajon_de_sastre():
    c = tx.clasificar("Zxqwy", "Producto sin ninguna palabra conocida")
    assert c["categoria"] == "Sin Clasificar"
    assert c["familia"] == "Zxqwy"


def test_toda_categoria_de_una_regla_existe_en_el_catalogo():
    from catalogo_taxonomia import CATEGORIAS, REGLAS
    for terminos, categoria, sub, familia, extra in REGLAS:
        assert categoria in CATEGORIAS, "categoria fuera del catalogo: %s" % categoria


# ── entero pelado como pulgada (solo en familias que requieren medida) ─────
# "Copla cobre 2 SO" es una copla de 2 pulgadas: en el catalogo de piping el
# diametro nominal se escribe a veces sin unidad. Fuera de esas familias un
# entero suelto no es una medida (ver test_entero_pelado_sin_unidad...).

def test_entero_pelado_es_pulgada_en_una_familia_de_piping():
    assert tx.medida_canonica("Copla", "Copla cobre 2 SO", aceptar_entero=True) == '2"'
    assert tx.clasificar("Copla", "Copla cobre 2 SO")["medida"] == '2"'


def test_entero_pelado_ignora_los_angulos_del_fitting():
    # el 90 de "Codo 90 galvanizado 1 NPT" son grados, no pulgadas
    assert tx.clasificar("Codo 90 galvanizado 1 NPT", "")["medida"] == '1"'


def test_entero_pelado_ignora_la_cantidad_del_envase():
    # "Pack 2 curva..." -> el 2 son unidades del pack, no el diametro
    assert tx.medida_canonica("Curva", "Pack 2 curva PVC cementar", aceptar_entero=True) is None


def test_entero_pelado_ignora_un_rango_metrico():
    # "8-12mm" es un rango en milimetros, no una abrazadera de 8 pulgadas
    assert tx.medida_canonica("Abrazadera", "Abrazadera p/manguera inox. 8-12",
                              aceptar_entero=True) is None


def test_entero_pelado_no_aplica_fuera_de_las_familias_con_medida():
    # una herramienta con un numero suelto no gana una medida inventada
    assert tx.clasificar("Martillo", "Martillo carpintero 16 oz")["medida"] is None


# ── convenciones metricas del catalogo: 032 (PPR) y DN50 ──────────────────

def test_medida_ppr_con_cero_a_la_izquierda_es_milimetros():
    # El catalogo escribe las medidas PPR como "032" = 32 mm
    assert tx.medida_canonica("Codo", "Codo PPR 90 032", aceptar_entero=True) == "32mm"
    assert tx.medida_canonica("Tee PPR", "Tee PPR 032", aceptar_entero=True) == "32mm"


def test_dn_es_diametro_nominal_en_milimetros():
    assert tx.medida_canonica("Flange", "Flange DN50 PN16", aceptar_entero=True) == "50mm"


def test_pn_no_se_confunde_con_dn():
    # PN16 es presion nominal (bar), no un diametro
    assert tx.medida_canonica("Valvula", "Valvula PN16", aceptar_entero=True) is None


def test_el_angulo_no_es_la_parte_entera_de_una_fraccion_mixta():
    # "Codo BR 90 3/4 SO/HE" es un codo de 90 grados y 3/4 de pulgada,
    # no un codo de noventa y tres cuartos de pulgada.
    assert tx.medida_canonica("Codo", "Codo BR 90 3/4 SO/HE") == '3/4"'


def test_la_parte_entera_de_una_medida_no_supera_las_24_pulgadas():
    # No existe fitting de 100 pulgadas: si aparece, es otro numero
    assert tx.medida_canonica("Pieza", "Pieza 100 1/2 codigo interno") != '100.1/2"'


# ── el material es faceta solo donde define el producto ───────────────────

def test_un_color_no_es_un_material():
    # "Polerón térmico negro" es ropa negra, no acero negro
    assert tx.clasificar("Poleron", "Polerón térmico negro talla L")["material"] is None


def test_acero_negro_se_detecta_por_la_frase_no_por_el_color():
    assert tx.clasificar("Canieria negra", "Cañería negra ASTM A-53 3/4 plg")["material"] == "Acero Negro"


def test_el_material_no_parte_la_hoja_fuera_de_las_familias_donde_define():
    # un guante de plastico y un guante son el mismo producto para comparar
    # precio; un codo de cobre y uno de bronce no.
    guante = tx.clasificar("Guante", "Guante de plástico desechable")
    simple = tx.clasificar("Guante", "Guante cabritilla sin forro")
    assert tx.clave_hoja(guante) == tx.clave_hoja(simple)

    cobre = tx.clasificar("Codo cobre", "Codo SO cobre 1/2 plg")
    bronce = tx.clasificar("Codo bronce", "Codo SO BR 1/2 plg")
    assert tx.clave_hoja(cobre) != tx.clave_hoja(bronce)


def test_el_marco_de_aluminio_no_convierte_un_visor_en_producto_de_aluminio():
    visor = tx.clasificar("Visor", "Visor policarbonato c/marco aluminio")
    lente = tx.clasificar("Lente", "Lente protección claro")
    assert tx.clave_hoja(visor) == tx.clave_hoja(lente)


# ═══════════════════════════════════════════════════════════════════════
# Pedidos del usuario, 2026-09-09
# ═══════════════════════════════════════════════════════════════════════

# ── 1. los equipos se identifican por su modelo ───────────────────────────

def test_la_hoja_de_un_equipo_muestra_su_modelo():
    c = tx.clasificar("Bomba", "Kit bomba DAB circuladora rotor húmedo A 80/180XM unión 1.1/4\" 220V")
    assert "80/180XM" in tx.clave_hoja(c)


def test_dos_modelos_distintos_del_mismo_equipo_no_comparten_hoja():
    a = tx.clasificar("Caldera", "Caldera Anwo Agua Plus 2.0, 40/42 LPG, código NB2-40/42-LPG")
    b = tx.clasificar("Caldera", "Caldera Baxi Luna Duo-Tec MP+ 1.60, código 0")
    assert tx.clave_hoja(a) != tx.clave_hoja(b)


def test_el_titulo_del_equipo_no_arrastra_el_texto_administrativo():
    c = tx.clasificar("Caldera", "Caldera Anwo Agua Plus 2.0, 40/42 LPG, código NB2-40/42-LPG")
    hoja = tx.clave_hoja(c)
    assert "código" not in hoja.lower() and "cod." not in hoja.lower()


def test_el_mismo_modelo_escrito_distinto_cae_en_la_misma_hoja():
    a = tx.clasificar("Estanque de expansion", "Estanque de expansion R24 lts rojo 8 bar")
    b = tx.clasificar("Estanque de expansión", "Estanque de expansión R 24 LTS rojo 8 BAR, código 00.151.03")
    assert tx.clave_agrupacion(a) == tx.clave_agrupacion(b)


def test_un_consumible_no_usa_titulo_de_modelo():
    # un codo se compara por material y medida, no por su texto completo
    c = tx.clasificar("Codo bronce", "Codo SO BR (05) 1.1/4 plg")
    assert tx.clave_hoja(c) == 'Codo de Bronce 1.1/4"'


# ── 2. la soldadura de plata es su propia subcategoría ────────────────────

def test_soldadura_de_plata_tiene_subcategoria_propia():
    plata = tx.clasificar("Soldadura plata", "Soldadura plata 15% display (2 barras)")
    comun = tx.clasificar("Soldadura", "Soldadura estaño 50% (kg)")
    assert plata["categoria"] == comun["categoria"] == "Soldadura y Gases"
    assert plata["subcategoria"] == "Soldadura de Plata"
    assert comun["subcategoria"] == "Aportes"


def test_soldadura_de_plata_en_varilla_tambien():
    c = tx.clasificar("Soldadura plata", "Soldadura plata al 6% en varilla, cod. SOL20")
    assert c["subcategoria"] == "Soldadura de Plata"


# ── 3. el piping se separa por material ───────────────────────────────────

def test_la_subcategoria_de_piping_es_el_material():
    assert tx.clasificar("Codo cobre", "Codo SO cobre 1/2 plg")["subcategoria"] == "Cobre"
    assert tx.clasificar("Tee", "Tee PPR 32mm")["subcategoria"] == "PPR"
    assert tx.clasificar("Terminal", "Terminal DZR PEX HE 32x1")["subcategoria"] == "PEX"


def test_piping_sin_material_reconocible_cae_en_otros_materiales():
    c = tx.clasificar("Niple", "Niple 3/4")
    assert c["categoria"] == "Piping y Fittings"
    assert c["subcategoria"] == "Otros materiales"


def test_lo_cementado_es_pvc():
    # "cementar/cementada" es la union por cemento solvente: PVC
    assert tx.clasificar("Unión americana", "Unión americana cementada de 50 mm")["material"] == "PVC"


def test_fuera_del_piping_la_subcategoria_sigue_siendo_el_tipo():
    assert tx.clasificar("Guante", "Guante cabritilla")["subcategoria"] == "Guantes"


# ── 4. categorías secundarias ─────────────────────────────────────────────

def test_las_categorias_de_gasto_y_sin_clasificar_son_secundarias():
    for cat in ("Transporte y Logística", "Alimentación", "Arriendos y Servicios", "Sin Clasificar"):
        assert tx.es_secundaria(cat) is True, cat


def test_las_categorias_de_producto_no_son_secundarias():
    for cat in ("Piping y Fittings", "Herramientas Manuales", "Soldadura y Gases"):
        assert tx.es_secundaria(cat) is False, cat


def test_el_fundente_para_plata_no_es_soldadura_de_plata():
    # "Fundente para plata" es un fundente: va en Fundentes, no en la
    # subcategoría de soldadura de plata que se creó para el aporte.
    c = tx.clasificar("Fundente para plata", "Fundente para plata 050 GR")
    assert c["subcategoria"] == "Fundentes"


def test_dos_leyes_de_plata_no_comparten_hoja():
    # La soldadura al 6% y la al 15% cuestan 2,6x distinto: no son el mismo
    # producto ni se promedian.
    seis = tx.clasificar("Soldadura plata", "Soldadura plata al 6% en varilla, cod. SOL2005")
    quince = tx.clasificar("Soldadura plata", "Soldadura plata 15% display (2 barras)")
    assert tx.clave_agrupacion(seis) != tx.clave_agrupacion(quince)


def test_dos_designaciones_de_electrodo_no_comparten_hoja():
    # Un 6010 y un 7018 son electrodos distintos con precios distintos
    a = tx.clasificar("Electrodo", "Electrodo 6010 1/8 1kg")
    b = tx.clasificar("Electrodo", "Electrodo 7018 1/8 5kg Bauker")
    assert tx.clave_agrupacion(a) != tx.clave_agrupacion(b)


def test_la_pinza_porta_electrodo_no_se_promedia_con_los_electrodos():
    pinza = tx.clasificar("Pinza", "Pinza porta electrodo 300a")
    electrodo = tx.clasificar("Electrodo", "Electrodo 6010 1/8 1kg")
    assert tx.clave_agrupacion(pinza) != tx.clave_agrupacion(electrodo)


def test_las_abreviaturas_con_y_sin_no_abren_dos_hojas():
    # "c/hilo amarillo" y "con hilo amarillo" son el mismo tubo de gas
    a = tx.clasificar("Tubo de gas", "Tubo gas especial MAPP 400cc c/hilo amarillo")
    b = tx.clasificar("Tubo de gas", "Tubo gas especial MAPP 400cc con hilo amarillo")
    assert tx.clave_agrupacion(a) == tx.clave_agrupacion(b)
