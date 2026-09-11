# -*- coding: utf-8 -*-
"""
Tests de la validacion temprana (validar_documento / validar_corpus) y del
registro persistente de errores (fusionar_hallazgos / cerrar_hallazgo).

Cubren las clases de error que hasta la auditoria del 2026-09-10 no miraba
ningun validador -- cantidad <= 0, compra con neto <= 0, nota de credito con
signo o impuesto incoherente, tipo de documento fuera del vocabulario, fecha
ilegible o futura, proveedor/categoria en blanco -- mas la deduplicacion por
id estable, que es lo que evita que el mismo hallazgo se re-emita como nuevo
en cada corrida.
"""

from datetime import datetime, timedelta

import pytest

import auditor_centro_costos as acc


def documento(**kwargs):
    """Documento valido de referencia: sin hallazgos. Cada test lo ensucia
    solo en lo que quiere medir."""
    base = {
        "archivo": "DOC_0001.jpg",
        "proyecto": "Proyecto Alfa",
        "tipo_proyecto": "Obra",
        "fecha": "15-07-2026",
        "n_documento": "12345",
        "tipo_documento": "Factura",
        "proveedor": "Proveedor Demo SpA",
        "rut_proveedor": "76123456-7",
        "categoria": "Materiales",
        "estado": "Pagado",
        "items": [{"nombre_item": "Perfil", "descripcion": "d",
                   "categoria_item": "Materiales", "cantidad": 2,
                   "p_unitario_sin_iva": 50000}],
    }
    base["iva"] = round(acc.total_sin_iva_items(base["items"]) * 0.19)
    base.update(kwargs)
    return base


def codigos(dato):
    return {h["codigo"] for h in acc.validar_documento(dato)}


# ── El caso sano no genera ruido ────────────────────────────────────────────

def test_documento_correcto_no_genera_hallazgos():
    assert acc.validar_documento(documento()) == []


def test_boleta_sin_iva_no_genera_hallazgos():
    """Las boletas traen el impuesto incluido en el precio: no se les calcula
    ni se les exige un campo 'iva'."""
    d = documento(tipo_documento="Boleta")
    d.pop("iva")
    assert acc.validar_documento(d) == []


# ── Clases que antes no miraba nadie ────────────────────────────────────────

def test_cantidad_cero_se_detecta():
    d = documento()
    d["items"][0]["cantidad"] = 0
    assert "ITEM_CANTIDAD_INVALIDA" in codigos(d)


def test_cantidad_negativa_se_detecta():
    d = documento()
    d["items"][0]["cantidad"] = -1
    assert "ITEM_CANTIDAD_INVALIDA" in codigos(d)


def test_compra_con_neto_negativo_se_detecta():
    """Precedente real 'Signo de IVA / P.Unitario / Totales (AYRSA)' de
    ERRORES.md: el extractor leyo el documento entero con el signo invertido."""
    d = documento()
    d["items"][0]["p_unitario_sin_iva"] = -50000
    d["iva"] = -19000
    assert "DOC_NETO_NO_POSITIVO" in codigos(d)


def test_descuento_no_es_error_mientras_el_neto_siga_positivo():
    """Una linea negativa en una factura es un descuento, no un error: solo
    importa que el documento no termine costando cero o menos."""
    d = documento()
    d["items"].append({"nombre_item": "Descuento", "descripcion": "",
                       "categoria_item": "Materiales", "cantidad": 1,
                       "p_unitario_sin_iva": -10000})
    d["iva"] = round(acc.total_sin_iva_items(d["items"]) * 0.19)
    assert acc.validar_documento(d) == []


def test_nota_credito_con_neto_positivo_se_detecta():
    d = documento(tipo_documento="Nota de Credito")
    assert "NC_SIGNO" in codigos(d)


def test_nota_credito_bien_firmada_no_genera_hallazgos():
    d = documento(tipo_documento="Nota de Credito")
    d["items"][0]["p_unitario_sin_iva"] = -50000
    d["iva"] = round(acc.total_sin_iva_items(d["items"]) * 0.19)
    assert acc.validar_documento(d) == []


def test_nota_credito_con_impuesto_descuadrado_se_detecta():
    """severidad_cuadre_impuesto() no mira las notas de credito (para ella
    'afecto' es lo que paga impuesto sobre el neto), asi que hasta hoy su
    impuesto no lo verificaba nadie."""
    d = documento(tipo_documento="Nota de Credito")
    d["items"][0]["p_unitario_sin_iva"] = -50000
    d["iva"] = -30000  # deberia ser -19000
    assert "NC_IMPUESTO_DESCUADRADO" in codigos(d)
    assert acc.severidad_cuadre_impuesto(d, acc.total_sin_iva_items(d["items"]),
                                         d["iva"]) is None  # sigue sin mirarla


def test_tipo_documento_desconocido_se_detecta():
    """Antes se registraba con impuesto 0 sin decir nada."""
    d = documento(tipo_documento="Comprobante interno")
    d.pop("iva")
    assert "TIPO_DOC_DESCONOCIDO" in codigos(d)


@pytest.mark.parametrize("tipo", ["Factura", "Boleta", "Guía de Despacho",
                                  "Guia de despacho", "Nota de Crédito"])
def test_tipos_conocidos_no_se_marcan(tipo):
    d = documento(tipo_documento=tipo)
    d["items"][0]["p_unitario_sin_iva"] = -50000 if "cr" in tipo.lower() else 50000
    d["iva"] = round(acc.total_sin_iva_items(d["items"]) * 0.19)
    assert "TIPO_DOC_DESCONOCIDO" not in codigos(d)


def test_fecha_invalida_se_detecta():
    assert "FECHA_INVALIDA" in codigos(documento(fecha="32-13-2026"))


def test_fecha_con_barras_sigue_siendo_valida():
    """El parser historico acepta DD/MM/AAAA como fallback."""
    assert "FECHA_INVALIDA" not in codigos(documento(fecha="15/07/2026"))


def test_fecha_futura_se_detecta():
    futura = (datetime.now() + timedelta(days=90)).strftime("%d-%m-%Y")
    assert "FECHA_FUTURA" in codigos(documento(fecha=futura))


def test_fecha_de_hoy_no_se_marca_como_futura():
    hoy = datetime.now().strftime("%d-%m-%Y")
    assert "FECHA_FUTURA" not in codigos(documento(fecha=hoy))


def test_proveedor_y_categoria_vacios_se_detectan():
    c = codigos(documento(proveedor="   ", categoria=""))
    assert {"PROVEEDOR_VACIO", "CATEGORIA_VACIA"} <= c


# ── Clases que ya se detectaban: no deben cambiar de comportamiento ─────────

def test_n_documento_ilegible_se_detecta():
    assert "N_DOC_ILEGIBLE" in codigos(documento(n_documento="S/N (IMG_1.jpg)"))


def test_impuesto_menor_se_detecta_como_error():
    d = documento(iva=1000)
    h = [x for x in acc.validar_documento(d) if x["codigo"] == "IMPUESTO_MENOR"]
    assert h and h[0]["severidad"] == "error"
    assert h[0]["valor_esperado"] == round(100000 * 0.19)


def test_combustible_con_otros_impuestos_declarados_cuadra():
    d = documento(categoria="Combustible")
    d["otros_impuestos"] = 11000
    d["iva"] = round(100000 * 0.19) + 11000
    assert acc.validar_documento(d) == []


def test_documento_sin_items_solo_reporta_eso():
    d = documento(items=[])
    assert codigos(d) == {"DOC_SIN_ITEMS"}


def test_item_agrupado_se_detecta_una_sola_vez():
    d = documento()
    d["items"] = [
        {"nombre_item": "Materiales varios", "descripcion": "ilegible",
         "categoria_item": "Materiales", "cantidad": 1, "p_unitario_sin_iva": 50000},
        {"nombre_item": "Insumos varios", "descripcion": "ilegible",
         "categoria_item": "Materiales", "cantidad": 1, "p_unitario_sin_iva": 50000},
    ]
    d["iva"] = round(100000 * 0.19)
    assert [h["codigo"] for h in acc.validar_documento(d)].count("ITEM_AGRUPADO") == 1


# ── Duplicados: el numero es unico POR EMISOR ──────────────────────────────

def test_mismo_numero_distinto_emisor_no_es_duplicado():
    a = documento(archivo="A.jpg", n_documento="999", rut_proveedor="76111111-1")
    b = documento(archivo="B.jpg", n_documento="999", rut_proveedor="76222222-2")
    hallazgos, _ = acc.detectar_duplicados([a, b])
    assert hallazgos == []


def test_duplicado_exacto_se_marca_y_es_auto_resoluble():
    a = documento(archivo="A.jpg")
    b = documento(archivo="B.jpg")
    hallazgos, copias = acc.detectar_duplicados([a, b])
    assert [h["codigo"] for h in hallazgos] == ["DUPLICADO_EXACTO"]
    assert copias == {"Proyecto Alfa\\B.jpg": "Proyecto Alfa\\A.jpg"}


def test_duplicado_con_monto_distinto_es_ambiguo_y_no_auto_resoluble():
    a = documento(archivo="A.jpg")
    b = documento(archivo="B.jpg")
    b["items"][0]["p_unitario_sin_iva"] = 70000
    b["iva"] = round(140000 * 0.19)
    hallazgos, copias = acc.detectar_duplicados([a, b])
    assert [h["codigo"] for h in hallazgos] == ["DUPLICADO_AMBIGUO"]
    assert copias == {}


def test_placeholders_no_generan_duplicados():
    """172 peajes comparten el literal 'N/A' y no son el mismo documento."""
    docs = [documento(archivo=f"P{i}.jpg", n_documento="N/A") for i in range(5)]
    hallazgos, _ = acc.detectar_duplicados(docs)
    assert hallazgos == []


# ── Identidad estable de los hallazgos ─────────────────────────────────────

def test_id_es_estable_entre_corridas():
    d = documento(n_documento="S/N (IMG_1.jpg)")
    assert [h["id"] for h in acc.validar_documento(d)] == \
           [h["id"] for h in acc.validar_documento(d)]


def test_id_distingue_documento_y_campo():
    a = acc.validar_documento(documento(archivo="A.jpg", n_documento="S/N (a)"))[0]
    b = acc.validar_documento(documento(archivo="B.jpg", n_documento="S/N (b)"))[0]
    assert a["id"] != b["id"]


def test_archivos_sin_datos_entran_como_hallazgo():
    hallazgos, _ = acc.validar_corpus(
        [], archivos_sin_datos=[{"proyecto": "Proyecto Alfa", "archivo": "X.jpg"}])
    assert [h["codigo"] for h in hallazgos] == ["DOC_SIN_DATOS"]


def test_orden_pone_los_errores_primero():
    hallazgos, _ = acc.validar_corpus([
        documento(archivo="A.jpg", categoria=""),     # revisar
        documento(archivo="B.jpg", iva=1),            # error
    ])
    assert hallazgos[0]["severidad"] == "error"


# ── Registro persistente: deduplicacion y ciclo de vida ────────────────────

def registro_vacio():
    return {"version": 1, "errores": []}


def test_hallazgo_repetido_no_se_duplica():
    reg = registro_vacio()
    hallazgos, _ = acc.validar_corpus([documento(iva=1)])
    acc.fusionar_hallazgos(reg, hallazgos, hoy="2026-09-10")
    acc.fusionar_hallazgos(reg, hallazgos, hoy="2026-09-11")
    assert len(reg["errores"]) == 1
    assert reg["errores"][0]["corridas_vistas"] == 2
    assert reg["errores"][0]["primera_deteccion"] == "2026-09-10"
    assert reg["errores"][0]["ultima_deteccion"] == "2026-09-11"


def test_hallazgo_que_desaparece_se_cierra_solo():
    reg = registro_vacio()
    hallazgos, _ = acc.validar_corpus([documento(iva=1)])
    acc.fusionar_hallazgos(reg, hallazgos, hoy="2026-09-10")
    _, _, desaparecidos = acc.fusionar_hallazgos(reg, [], hoy="2026-09-11")
    assert len(desaparecidos) == 1
    assert reg["errores"][0]["estado"] == "resuelto"
    assert reg["errores"][0]["fecha_cierre"] == "2026-09-11"


def test_hallazgo_cerrado_reabre_si_el_dato_de_origen_cambio():
    """Un valor que nadie adjudico todavia vuelve a la lista. Taparlo seria
    esconder un error para que las metricas se vean mejor."""
    reg = registro_vacio()
    hallazgos, _ = acc.validar_corpus([documento(iva=1)])
    acc.fusionar_hallazgos(reg, hallazgos, hoy="2026-09-10")
    acc.cerrar_hallazgo(reg, reg["errores"][0]["id"], "resuelto", "corregido a mano",
                        hoy="2026-09-11")

    otros, _ = acc.validar_corpus([documento(iva=2)])  # el origen cambio
    _, reabiertos, _ = acc.fusionar_hallazgos(reg, otros, hoy="2026-09-12")

    assert len(reabiertos) == 1
    assert reg["errores"][0]["estado"] == "abierto"


def test_hallazgo_cerrado_no_reabre_si_el_dato_de_origen_sigue_igual():
    """datos_extraidos.json es entrada del pipeline y no se reescribe: si el
    hallazgo se reabriera en cada corrida, los mismos descuadres se
    reimprimirian para siempre. Queda cerrado, pero marcado."""
    reg = registro_vacio()
    hallazgos, _ = acc.validar_corpus([documento(iva=1)])
    acc.fusionar_hallazgos(reg, hallazgos, hoy="2026-09-10")
    acc.cerrar_hallazgo(reg, reg["errores"][0]["id"], "resuelto", "corregido a mano",
                        hoy="2026-09-11")

    _, reabiertos, _ = acc.fusionar_hallazgos(reg, hallazgos, hoy="2026-09-12")

    assert reabiertos == []
    assert reg["errores"][0]["estado"] == "resuelto"
    assert reg["errores"][0]["origen_sin_corregir"] is True


def test_descartar_exige_justificacion():
    reg = registro_vacio()
    hallazgos, _ = acc.validar_corpus([documento(iva=1)])
    acc.fusionar_hallazgos(reg, hallazgos)
    with pytest.raises(ValueError):
        acc.cerrar_hallazgo(reg, reg["errores"][0]["id"], "descartado", "  ")


def test_cerrar_con_estado_invalido_falla():
    reg = registro_vacio()
    hallazgos, _ = acc.validar_corpus([documento(iva=1)])
    acc.fusionar_hallazgos(reg, hallazgos)
    with pytest.raises(ValueError):
        acc.cerrar_hallazgo(reg, reg["errores"][0]["id"], "abierto", "x")


def test_registro_ida_y_vuelta_a_disco(tmp_path):
    ruta = tmp_path / "errores_detectados.json"
    reg = registro_vacio()
    hallazgos, _ = acc.validar_corpus([documento(iva=1)])
    acc.fusionar_hallazgos(reg, hallazgos, hoy="2026-09-10")
    acc.guardar_registro_errores(reg, ruta)
    assert acc.cargar_registro_errores(ruta)["errores"] == reg["errores"]


def test_registro_inexistente_devuelve_vacio(tmp_path):
    assert acc.cargar_registro_errores(tmp_path / "no_existe.json")["errores"] == []


def test_anotar_n_ref_pega_la_fila_de_master():
    reg = registro_vacio()
    hallazgos, _ = acc.validar_corpus([documento(iva=1)])
    acc.fusionar_hallazgos(reg, hallazgos)
    assert acc.anotar_n_ref(reg, "Proyecto Alfa\\DOC_0001.jpg", "BALF-007") == 1
    assert reg["errores"][0]["n_ref"] == "BALF-007"


def test_toda_la_taxonomia_declara_accion_y_severidad_valida():
    for codigo, (severidad, titulo, accion, columna) in acc.TAXONOMIA_ERRORES.items():
        assert severidad in acc.ORDEN_SEVERIDAD, codigo
        assert titulo.strip(), codigo
        assert accion.strip(), codigo
        assert columna is None or 1 <= columna <= len(acc.ENCABEZADOS_MASTER), codigo
