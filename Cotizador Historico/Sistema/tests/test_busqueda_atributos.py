# -*- coding: utf-8 -*-
"""El buscador entendiendo ATRIBUTOS, no solo palabras.

Corpus chico y versionado, igual que test_busqueda_ranking: la suite tiene
que significar algo en una maquina sin el Excel. Incluye el caso exacto que
pidio el usuario (2026-09-22) -- "plancha policarbonato 0.7" tiene que poner
la plancha de policarbonato muy por encima de la de MDF del mismo espesor --
y el resto de las consultas de su lista: combinaciones parciales, medidas
equivalentes, grados de material, especificaciones y errores de tipeo.
"""
import busqueda


def _item(n_ref, nombre, descripcion, **extra):
    base = {"n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
            "precio_unitario_sin_iva": 1000, "fecha": None, "excluido_motivo": None}
    base.update(extra)
    return base


CORPUS = [
    # planchas: mismo tipo y mismo espesor, distinto material
    _item("P-POLI", "Plancha policarbonato",
          "Plancha policarbonato transparente 0,7 x 812 x 3660 mm"),
    _item("P-MDF", "Plancha MDF", "Plancha MDF 0,7 x 1000 x 2000"),
    _item("P-GALV", "Plancha", "Plancha galvanizada lisa 0,8 x 1000 x 3000 mm"),
    _item("P-INOX", "Placa inox", "Placa inox. 1mm"),
    _item("P-POLI4", "Policarbonato", "Plancha policarbonato 4mm"),
    # perfiles
    _item("PF-40", "Perfil cuadrado", "Perfil cuadrado 40x40x2.0mm, 6 metros"),
    _item("PF-80", "Perfil rectangular", "Perfil rectangular 80x40x3.0mm"),
    # piping
    _item("V-2", "Valvula bola", 'Válvula bola italiana p/estopa Enolgas (08) 2 plg'),
    _item("V-INOX", "Válvula", 'Válvula de bola 3/4", inoxidable, paso total'),
    _item("C-12", "Codo 45 galvanizado 1/2", "Cod. 4508C150-JM"),
    _item("C-INOX", "Codo", 'Codo unión inoxidable 3/4"'),
    _item("T-316", "Tubo", "Tubo 1/4 acero inoxidable 316 x 6mts"),
    _item("CA-SCH", "Cañería", 'Cañería de acero inoxidable ASTM A312 304L, 6" SCH10S'),
    _item("PEX-20", "Cañeria PEX", "PEX-A Aqualine 20 barra 5.8mt"),
    _item("PEX-32", "Cañeria PEX", "PEX-A Aqualine 32 barra 5.8mts"),
    # fijaciones
    _item("PN-58", "Perno hexagonal", "Perno hexagonal G-2 (30) 5x5/8 plg"),
    _item("PN-M12", "Perno", "Perno de 12x50 C/T"),
    # abrasivos
    _item("D-115", "Disco de corte", "Disco de corte 115x1x22,23mm"),
]


def _indice():
    return busqueda.Indice([dict(it) for it in CORPUS])


def _top(consulta, k=5):
    resultados, _sug = _indice().buscar(consulta)
    return [r["item"]["n_ref"] for r in resultados[:k]]


# ── el caso del pedido: el material manda sobre la medida ─────────────────

def test_el_policarbonato_le_gana_al_mdf_del_mismo_espesor():
    assert _top("plancha policarbonato 0.7")[0] == "P-POLI"


def test_la_coma_decimal_es_lo_mismo_que_el_punto():
    assert _top("plancha policarbonato 0,7")[0] == "P-POLI"
    assert _top("plancha policarbonato 0.70")[0] == "P-POLI"


def test_se_encuentra_por_una_dimension_que_no_es_la_principal():
    # 812 es el ancho: antes cualquier numero que no fuera pulgada se tiraba
    assert _top("policarbonato 812")[0] == "P-POLI"
    assert _top("plancha 3660")[0] == "P-POLI"


def test_combinaciones_parciales_del_pedido():
    for consulta in ("plancha policarbonato", "policarbonato transparente",
                     "plancha policarbonato 0.7 812"):
        assert _top(consulta)[0] in ("P-POLI", "P-POLI4"), consulta
    # "plancha 0.7" no dice el material: las dos planchas de 0,7 mm son una
    # respuesta correcta, y las dos van antes que cualquier otra plancha.
    assert set(_top("plancha 0.7")[:2]) == {"P-POLI", "P-MDF"}


def test_un_error_de_tipeo_en_el_material_igual_encuentra():
    assert "P-POLI" in _top("policarbonsto")
    assert _top("valvula vola 2")[0] == "V-2"


# ── material, grado y sistema ─────────────────────────────────────────────

def test_se_busca_por_grado_de_inoxidable_escrito_de_varias_formas():
    for consulta in ("ss316", "aisi 316", "inox 316", "tubo 316"):
        assert "T-316" in _top(consulta), consulta


def test_se_busca_por_la_familia_del_material():
    # "plastico" encuentra el policarbonato y el PEX, que son plasticos
    top = _top("plancha plastico")
    assert "P-POLI" in top or "P-POLI4" in top


def test_la_abreviatura_del_catalogo_encuentra_el_material_completo():
    assert _top("codo galv 1/2")[0] == "C-12"


def test_el_pex_de_20_no_es_el_de_32():
    assert _top("pex 20")[0] == "PEX-20"
    assert _top("pex 32")[0] == "PEX-32"


# ── especificaciones ──────────────────────────────────────────────────────

def test_se_busca_por_schedule():
    assert _top("cañeria sch 10s")[0] == "CA-SCH"
    assert _top("sch10s")[0] == "CA-SCH"


def test_se_busca_por_medida_metrica_de_perno():
    assert _top("perno m12")[0] == "PN-M12"


def test_el_disco_se_encuentra_en_pulgadas_y_en_milimetros():
    # 115 mm es el "4 1/2 pulgadas" de ferreteria
    assert _top("disco corte 115")[0] == "D-115"
    assert _top("disco corte 4 1/2")[0] == "D-115"


# ── el tipo pesa mas que el texto suelto ─────────────────────────────────

def test_el_tipo_de_producto_manda_sobre_la_mencion_en_otro_campo():
    # "perfil 40x40" tiene que abrir con el perfil de 40x40, no con el de 80x40
    assert _top("perfil 40x40")[0] == "PF-40"
    assert _top("perfil rectangular 80x40")[0] == "PF-80"


def test_material_y_medida_juntos_ordenan_mejor_que_cada_uno_por_separado():
    # una consulta con material + medida pone primero el que cumple los dos
    assert _top('valvula bola 3/4 inoxidable')[0] == "V-INOX"
    assert _top('valvula bola 2')[0] == "V-2"


def test_ningun_resultado_se_inventa():
    resultados, sugerencias = _indice().buscar("helicoptero")
    assert resultados == [] and sugerencias == []
