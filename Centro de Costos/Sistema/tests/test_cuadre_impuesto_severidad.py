"""Cuadre Neto vs impuesto: normalizacion del tipo y severidades.

Cubre los dos huecos que encontro la auditoria del 2026-09-09 sobre
datos_extraidos.json (660 documentos):

  1. El tipo de documento se comparaba contra la tupla literal
     ("Factura", "Guía de Despacho") en 3 lugares distintos, asi que las 8
     entradas escritas "Guia de Despacho" (sin tilde) quedaban fuera de toda
     verificacion -- y les habria calculado impuesto 0 de no venir con 'iva'.

  2. El validador emitia 100 alertas y 73 eran documentos CORRECTOS: facturas
     de combustible, donde el precio pagado lleva IVA 19% MAS impuesto
     especifico (IEC) y FEPP, y el campo 'iva' agrupa los tres a proposito.
     Eso enterraba las 27 alertas reales y dejaba 55 celdas de IVA en rojo
     permanentes en el libro.
"""

import auditor_centro_costos as acc


def _doc(tipo_documento="Factura", iva=None, neto=100000, categoria=None, **extra):
    d = {
        "archivo": "IMG_1.jpg", "n_documento": "123",
        "tipo_documento": tipo_documento, "iva": iva,
        "items": [{"cantidad": 1, "p_unitario_sin_iva": neto}],
    }
    if categoria is not None:
        d["categoria"] = categoria
    d.update(extra)
    return d


# ── clave_tipo_documento / es_documento_afecto ──────────────────────────────

def test_clave_tipo_documento_colapsa_tildes_mayusculas_y_espacios():
    assert acc.clave_tipo_documento("Guía de Despacho") == "guia de despacho"
    assert acc.clave_tipo_documento("Guia de Despacho") == "guia de despacho"
    assert acc.clave_tipo_documento("  GUIA   DE  DESPACHO ") == "guia de despacho"


def test_clave_tipo_documento_tolera_none():
    assert acc.clave_tipo_documento(None) == ""


def test_guia_de_despacho_sin_tilde_es_afecta():
    """El bug concreto: 8 de las 11 guias del JSON venian sin tilde y no se
    validaban."""
    assert acc.es_documento_afecto("Guia de Despacho") is True
    assert acc.es_documento_afecto("Guía de Despacho") is True


def test_boleta_y_nota_de_credito_no_son_afectas():
    assert acc.es_documento_afecto("Boleta") is False
    assert acc.es_documento_afecto("Nota de Credito") is False
    assert acc.es_documento_afecto("Nota de Crédito") is False


def test_calcular_iva_de_guia_sin_tilde_no_es_cero():
    """Antes devolvia 0 porque el string no matcheaba la tupla con tilde: un
    documento afecto entraba al libro con impuesto 0."""
    assert acc.calcular_iva_documento({"tipo_documento": "Guia de Despacho"}, 100000) == 19000


# ── severidades ────────────────────────────────────────────────────────────

def test_combustible_con_impuesto_sobre_el_19_no_es_hallazgo():
    """Patron normal de una boleta de bencina: IVA + IEC + FEPP en un solo
    campo. Eran 73 de las 100 alertas del validador anterior."""
    doc = _doc(iva=10661, neto=19339, categoria="Combustible")
    assert acc.verificar_aritmetica([doc]) == []


def test_combustible_con_impuesto_bajo_el_19_sigue_siendo_error():
    """El impuesto nunca puede ser MENOR al IVA legal, ni en combustible."""
    doc = _doc(iva=1873, neto=38318, categoria="Combustible")
    hallazgos = acc.verificar_aritmetica([doc])
    assert len(hallazgos) == 1
    assert hallazgos[0]["severidad"] == "error"


def test_exceso_de_impuesto_fuera_de_combustible_es_revisar():
    doc = _doc(iva=16527, neto=76520, categoria="Ferreteria")
    hallazgos = acc.verificar_aritmetica([doc])
    assert len(hallazgos) == 1
    assert hallazgos[0]["severidad"] == "revisar"


def test_combustible_sin_iva_declarado_es_estimado():
    """Se le calcula 19%, que para combustible queda corto: el total pagado
    era mayor. Antes se asumia en silencio."""
    doc = _doc(iva=None, neto=34780, categoria="Combustible")
    hallazgos = acc.verificar_aritmetica([doc])
    assert len(hallazgos) == 1
    assert hallazgos[0]["severidad"] == "estimado"


def test_no_combustible_sin_iva_declarado_no_es_hallazgo():
    doc = _doc(iva=None, neto=34780, categoria="Ferreteria")
    assert acc.verificar_aritmetica([doc]) == []


def test_tolerancia_absorbe_el_redondeo_item_por_item():
    """El impuesto real se calcula sobre el neto total, no item por item."""
    neto = 31758                      # 19% = 6034.02 -> 6034
    assert acc.verificar_aritmetica([_doc(iva=6036, neto=neto)]) == []
    assert acc.verificar_aritmetica([_doc(iva=6032, neto=neto)]) == []


def test_los_errores_se_reportan_primero():
    docs = [
        _doc(iva=None, neto=10000, categoria="Combustible"),        # estimado
        _doc(iva=3000, neto=10000, categoria="Ferreteria"),         # revisar
        _doc(iva=100, neto=10000, categoria="Ferreteria"),          # error
    ]
    assert [h["severidad"] for h in acc.verificar_aritmetica(docs)] == [
        "error", "revisar", "estimado",
    ]


def test_hallazgo_incluye_categoria_para_poder_triar():
    doc = _doc(iva=100, neto=10000, categoria="Ferreteria")
    assert acc.verificar_aritmetica([doc])[0]["categoria"] == "Ferreteria"


# ── otros_impuestos: el cuadre exacto ──────────────────────────────────────
# Cuando el documento declara cuanto de su impuesto NO es IVA, el cuadre deja
# de depender de la categoria y pasa a ser una igualdad verificable. Es la
# forma preferida de registrar un combustible (IEC + FEPP).

def test_otros_impuestos_declarados_cuadran_exacto():
    #  19% de 19.339 = 3.674; el resto (6.987) es impuesto especifico
    doc = _doc(iva=10661, neto=19339, categoria="Combustible", otros_impuestos=6987)
    assert acc.verificar_aritmetica([doc]) == []


def test_otros_impuestos_hacen_innecesaria_la_categoria():
    """Sirve para cualquier rubro, no solo Combustible."""
    doc = _doc(iva=10661, neto=19339, categoria="Ferreteria", otros_impuestos=6987)
    assert acc.verificar_aritmetica([doc]) == []


def test_declarar_de_menos_es_error():
    doc = _doc(iva=5000, neto=19339, categoria="Combustible", otros_impuestos=6987)
    hallazgos = acc.verificar_aritmetica([doc])
    assert len(hallazgos) == 1
    assert hallazgos[0]["severidad"] == "error"


def test_declarar_de_mas_es_revisar():
    doc = _doc(iva=20000, neto=19339, categoria="Combustible", otros_impuestos=6987)
    hallazgos = acc.verificar_aritmetica([doc])
    assert len(hallazgos) == 1
    assert hallazgos[0]["severidad"] == "revisar"


def test_sin_otros_impuestos_sigue_la_regla_por_categoria():
    """Compatibilidad: las 660 entradas existentes no declaran el campo."""
    assert acc.verificar_aritmetica([_doc(iva=10661, neto=19339, categoria="Combustible")]) == []
    assert len(acc.verificar_aritmetica([_doc(iva=10661, neto=19339, categoria="Ferreteria")])) == 1
