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


def test_combustible_con_impuesto_bajo_el_19_es_revisar_no_error():
    """Corregido el 2026-09-10 con el documento en la mano. Este test afirmaba
    "el impuesto nunca puede ser MENOR al IVA legal, ni en combustible", y
    JUNJ-238 (Copec, factura 94279) lo desmiente: neto 8.142, IVA 1.547,
    IEV Diesel -3.463, IEF Diesel 774, TOTAL PAGADO 7.000. El impuesto
    combinado es -1.142, muy por debajo del 19%, y el dato esta bien.

    El FEPP/IEV es un mecanismo de estabilizacion: puede devolver plata. Por
    eso el perdon por categoria no puede aplicarse solo del lado del exceso.
    Sigue reportandose -- no se oculta ninguna -- pero como 'revisar'.
    """
    doc = _doc(iva=-1142, neto=8142, categoria="Combustible")
    hallazgos = acc.verificar_aritmetica([doc])
    assert len(hallazgos) == 1
    assert hallazgos[0]["severidad"] == "revisar"


def test_deficit_de_impuesto_fuera_de_combustible_sigue_siendo_error():
    """El contrapeso: sin impuesto especifico que lo explique, un impuesto bajo
    el 19% sigue siendo algo seguro que corregir."""
    doc = _doc(iva=1873, neto=38318, categoria="Ferreteria")
    hallazgos = acc.verificar_aritmetica([doc])
    assert len(hallazgos) == 1
    assert hallazgos[0]["severidad"] == "error"


def test_el_deficit_en_combustible_no_se_llama_exceso():
    """'revisar' significa dos cosas distintas segun de que lado del 19% cayo
    el impuesto; el codigo del hallazgo tiene que decir cual."""
    def _codigos_de_impuesto(doc):
        return [h["codigo"] for h in acc.validar_documento(doc)
                if h["codigo"].startswith("IMPUESTO_")]

    assert _codigos_de_impuesto(
        _doc(iva=-1142, neto=8142, categoria="Combustible")) == ["IMPUESTO_MENOR_ESPECIFICO"]
    assert _codigos_de_impuesto(
        _doc(iva=16527, neto=76520, categoria="Ferreteria")) == ["IMPUESTO_EXCESO"]


def test_con_otros_impuestos_declarado_el_deficit_vuelve_a_ser_error():
    """Si el documento DECLARA cuanto de su impuesto no es IVA, el cuadre deja
    de ser una heuristica por categoria y pasa a ser exacto: quedarse corto
    respecto de esa declaracion si es un error, tambien en combustible."""
    doc = _doc(iva=5000, neto=19339, categoria="Combustible", otros_impuestos=6987)
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


def test_factura_exenta_no_cuadra_contra_el_19_por_ciento():
    """Zona Franca (UMAG-005/020, Crosur Punta Arenas, 2026-09-14): la venta
    es exenta y el documento solo lleva el impuesto Art. 11 Ley 18.211
    (0,15% sobre el CIF, incluido en el precio), nunca el 19%. Sin un tipo
    propio, toda "Factura" se cuadraba contra el 19% y la celda volvia a rojo
    en cada corrida hiciera lo que hiciera el usuario.
    """
    assert not acc.es_documento_afecto("Factura Exenta")
    assert acc.severidad_cuadre_impuesto(_doc("Factura Exenta", iva=0), 20800, 0) is None
    assert acc.verificar_aritmetica([_doc("Factura Exenta", iva=0, neto=20800)]) == []


def test_factura_exenta_esta_en_el_vocabulario():
    """Si no esta, validar_documento la reporta como TIPO_DOC_DESCONOCIDO en
    cada corrida: se cambia un hallazgo permanente por otro."""
    assert "factura exenta" in acc.TIPOS_DOCUMENTO_CONOCIDOS
    codigos = [h["codigo"] for h in acc.validar_documento(
        _doc("Factura Exenta", iva=0, neto=20800, categoria="Materiales"))]
    assert "TIPO_DOC_DESCONOCIDO" not in codigos
