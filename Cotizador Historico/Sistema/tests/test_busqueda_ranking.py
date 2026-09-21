# -*- coding: utf-8 -*-
"""Los casos minimos de prueba del buscador, sobre un corpus versionado.

El benchmark grande (Sistema/benchmark_busqueda.py) corre contra el catalogo
real, que esta gitignoreado por ser informacion financiera de la empresa.
Este archivo cubre las mismas garantias sobre un corpus chico escrito a mano
y versionado, para que la suite siga significando algo en una maquina que no
tenga el Excel -- y para que un cambio de pesos que rompa el ranking se note
en `pytest`, no recien al publicar el dashboard.

El corpus imita la forma real del catalogo: el MISMO producto escrito de
varias maneras (a veces el Nombre Item dice "Valvula" a secas y la medida
solo esta en la descripcion), que es justo lo que hacia fallar al buscador
anterior.
"""
import busqueda


def _item(n_ref, nombre, descripcion, **extra):
    base = {
        "n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
        "precio_unitario_sin_iva": 1000, "fecha": None, "excluido_motivo": None,
    }
    base.update(extra)
    return base


# Corpus: valvulas de varios calibres + vecinos que NO deben ganarles.
CORPUS = [
    _item("V-2", "Valvula bola", 'Válvula bola italiana p/estopa Enolgas (08) 2 plg'),
    _item("V-2b", "Válvula", 'Válvula bola Bugatti P/T 2" HI-HI M/MET'),
    _item("V-12", "Valvula bola", "Válvula bola Bugatti P/T 1/2 HI HI M/MET"),
    _item("V-34", "Válvula de bola", 'Válvula bola paso 3/4" acero'),
    _item("V-114", "Valvula bola", "Válvula bola paso total 1 1/4"),
    _item("V-212", "Valvula bola", 'Válvula bola paso total 2.1/2"'),
    _item("V-RET", "Valvula retencion", "Válvula retención vertical Bugatti 2 A/BR HI HI"),
    _item("V-PPR", "Válvula bola", "Válvula bola PPR 50mm 2UA fusión/fusión"),
    _item("C-BR114", "Codo bronce", "Codo SO BR (05) 1.1/4 plg"),
    _item("C-BR112", "Codo bronce", "Codo SO BR (06) 1.1/2 plg"),
    _item("CA-CU12", "Cañeria de cobre", "Cañeria de cobre tipo L 1/2 x 1 metro"),
    _item("G-1", "Guante", "Guante de trabajo cuero spandex"),
    _item("T-1", "Taladro percutor 20V 13mm s/carbones DCD7781", "Cod. 885911729369"),
    _item("M-1", "Manometro", "Manómetro c/glicerina 0-10 bar"),
    _item("TAP-1", "Tapón auditivo", "Tapones reusables para oídos con cordel"),
    _item("TAP-2", "Tapagorro", "Tapagorro BR NI 1/2"),
]


def _indice():
    return busqueda.Indice(CORPUS)


def _top(consulta, k=5):
    resultados, _sug = _indice().buscar(consulta)
    return [r["item"]["n_ref"] for r in resultados[:k]]


# ── el caso central: la misma valvula escrita de 8 formas ─────────────────

ESCRITURAS_VALVULA_BOLA_2 = [
    'Válvula de bola de 2"',
    "valvula bola 2",
    "válvula 2 pulgadas",
    'bola 2"',
    "válvula esférica 2 in",
    'válbula de vola 2"',
    "valvula de bola dn50",
    'Valvula 2" bola',
]


def test_todas_las_escrituras_encuentran_la_valvula_de_dos_pulgadas():
    """El criterio de exito pedido: el item esperado entre los 5 primeros."""
    for consulta in ESCRITURAS_VALVULA_BOLA_2:
        top = _top(consulta)
        assert {"V-2", "V-2b"} & set(top), f"{consulta!r} devolvio {top}"


def test_todas_las_escrituras_la_ponen_primera():
    for consulta in ESCRITURAS_VALVULA_BOLA_2:
        top = _top(consulta)
        assert top[0] in ("V-2", "V-2b"), f"{consulta!r} abrio con {top[0]}"


def test_escrituras_equivalentes_dan_el_mismo_conjunto_de_resultados():
    referencia = set(_top('Válvula de bola de 2"'))
    for consulta in ESCRITURAS_VALVULA_BOLA_2:
        assert set(_top(consulta)) == referencia, consulta


# ── medidas parecidas no se confunden ─────────────────────────────────────

def test_dos_pulgadas_no_prioriza_media_pulgada_ni_dos_y_media():
    top = _top('valvula de bola 2"', k=3)
    assert "V-12" not in top and "V-212" not in top and "V-34" not in top


def test_cada_calibre_encuentra_el_suyo():
    assert _top('valvula bola 1/2"')[0] == "V-12"
    assert _top('valvula bola 3/4"')[0] == "V-34"
    assert _top("valvula bola 2.1/2")[0] == "V-212"
    assert _top("valvula bola 1.1/4")[0] == "V-114"


def test_la_fraccion_mixta_no_se_lee_como_la_simple():
    # "hay elementos que son de 1.1/4 y que se indican como si fueran de 1/4"
    top = _top("codo bronce 1.1/4")
    assert top[0] == "C-BR114"
    assert "C-BR112" not in top[:1]


# ── categoria, codigo, material ───────────────────────────────────────────

def test_codigo_exacto_devuelve_solo_ese_item():
    assert _top("DCD7781") == ["T-1"]


def test_busca_por_material_aunque_no_este_en_el_nombre():
    assert _top("cañeria de cobre")[0] == "CA-CU12"


def test_el_ppr_se_encuentra_por_su_medida_en_milimetros():
    assert _top("valvula bola ppr 50mm")[0] == "V-PPR"


def test_una_pulgada_no_trae_el_ppr_en_milimetros():
    assert "V-PPR" not in _top('valvula de bola 2"', k=3)


# ── tolerancias ───────────────────────────────────────────────────────────

def test_plural_y_singular_son_lo_mismo():
    assert _top("guantes") == _top("guante")


def test_el_epp_le_gana_al_piping_cuando_se_buscan_tapones_de_oido():
    # "Tapones para oidos" contiene "tapon", que en piping es otra cosa.
    assert _top("tapones para los oidos")[0] == "TAP-1"


def test_sin_resultados_devuelve_vacio():
    resultados, _sug = _indice().buscar("helicoptero")
    assert resultados == []


def test_la_consulta_a_medias_avisa_que_termino_falto():
    assert _indice().terminos_sin_resultado("valvula de compuerta") == ("compuerta",)


# ── explicacion de por que aparecio cada resultado ────────────────────────

def test_cada_resultado_explica_por_que_aparecio():
    resultados, _sug = _indice().buscar('valvula de bola de 2"')
    motivos = resultados[0]["motivos"]
    campos = {m["campo"] for m in motivos}
    assert "medida" in campos
    assert any(c in campos for c in ("nom", "hoja"))
    assert all(m["etiqueta"] for m in motivos)
