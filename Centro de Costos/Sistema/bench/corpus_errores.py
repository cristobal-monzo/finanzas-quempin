# -*- coding: utf-8 -*-
"""
corpus_errores.py -- corpus sintetico ANONIMIZADO para medir el proceso de
deteccion/resolucion de errores del Centro de Costos.

Ningun dato de aca sale de `datos_extraidos.json`: proveedores, RUTs,
proyectos, numeros de documento y montos son generados. Lo unico que se copia
de la realidad es la FORMA (el esquema del JSON) y la PROPORCION aproximada
de tipos de documento y categorias, medida de forma agregada sobre el corpus
real el 2026-09-10:

    Factura 331 / Boleta 330 / Guia de Despacho 11 / Nota de Credito 8
    Transporte 210 / Materiales 129 / Combustible 108 / Alimentacion 95 / ...

El corpus se genera con `random.Random(semilla)` fijo: dos corridas con la
misma semilla producen exactamente los mismos documentos y los mismos
defectos inyectados, que es lo que hace comparable la linea base con el
resultado final.

GROUND TRUTH
------------
`generar_corpus()` devuelve `(documentos, defectos, archivos_sin_entrada)`.
Cada defecto es:

    {"archivo": <clave unica del documento>,
     "clase":   <una de CLASES>,
     "campo":   <campo afectado, o None>,
     "valor_correcto": <el valor que deberia tener, si se puede expresar>}

Un documento lleva 0 o 1 defecto (nunca dos), para que la imputacion
"detectado / no detectado" sea inequivoca.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

# -- Taxonomia de defectos inyectados ---------------------------------------
# El nombre de cada clase describe el DEFECTO REAL del documento, no como lo
# llama el sistema: la gracia del benchmark es medir cuantos de estos el
# sistema logra ver y cerrar, no cuantos alcanza a nombrar.
CLASES = (
    "SIN_ENTRADA_JSON",         # hay foto pero no hay entrada en el JSON
    "SIN_ITEMS",                # entrada sin lista de items
    "N_DOC_ILEGIBLE",           # numero de documento no legible en la foto
    "IMPUESTO_MENOR",           # impuesto declarado < el que corresponde por ley
    "IMPUESTO_EXCESO",          # impuesto declarado > 19% sin explicacion conocida
    "IMPUESTO_ESTIMADO",        # combustible sin impuesto declarado (se subestima)
    "DUPLICADO_EXACTO",         # el mismo documento cargado dos veces
    "DUPLICADO_AMBIGUO",        # mismo N documento, contenido distinto
    "CANTIDAD_INVALIDA",        # cantidad <= 0
    "SIGNO_INVERTIDO_COMPRA",   # compra leida con el signo invertido (neto <= 0)
    "NC_SIGNO_POSITIVO",        # nota de credito con items positivos
    "NC_IMPUESTO_DESCUADRADO",  # nota de credito con impuesto que no cuadra
    "TIPO_DOC_DESCONOCIDO",     # tipo_documento fuera del vocabulario
    "FECHA_INVALIDA",           # fecha no parseable
    "FECHA_FUTURA",             # fecha posterior a hoy
    "ITEM_AGRUPADO",            # una parte de la compra quedo en 1 item "varios"
    "PROVEEDOR_VACIO",          # sin proveedor
    "CATEGORIA_VACIA",          # sin categoria
)

PROYECTOS = ["Proyecto Alfa", "Proyecto Beta", "Proyecto Gamma", "Proyecto Delta"]
TIPOS_PROYECTO = ["Obra", "Mantencion", "Servicio"]
CATEGORIAS = [
    ("Transporte", 210), ("Materiales", 129), ("Combustible", 108),
    ("Alimentacion", 95), ("Ferreteria", 64), ("Equipos-Herramientas", 17),
    ("Seguridad Industrial", 15), ("Arriendo", 14), ("Servicios", 4),
]
TIPOS_DOC = [("Factura", 331), ("Boleta", 330), ("Guia de Despacho", 11)]
ITEMS_POR_CATEGORIA = {
    "Transporte": ["Flete", "Peaje", "Pasaje"],
    "Materiales": ["Perfil acero", "Plancha zincalum", "Tornilleria"],
    "Combustible": ["Diesel", "Gasolina 93"],
    "Alimentacion": ["Almuerzo cuadrilla", "Colacion"],
    "Ferreteria": ["Broca", "Disco corte", "Guante"],
    "Equipos-Herramientas": ["Taladro", "Esmeril"],
    "Seguridad Industrial": ["Casco", "Arnes"],
    "Arriendo": ["Arriendo andamio", "Arriendo generador"],
    "Servicios": ["Servicio tecnico"],
}
TASA = 0.19

AFECTOS = ("Factura", "Guia de Despacho")


def _elegir_ponderado(rng, pares):
    total = sum(p for _, p in pares)
    corte = rng.uniform(0, total)
    acumulado = 0
    for valor, peso in pares:
        acumulado += peso
        if corte <= acumulado:
            return valor
    return pares[-1][0]


def _neto(dato):
    return sum(it["cantidad"] * it["p_unitario_sin_iva"] for it in dato["items"])


def _documento_limpio(rng, indice, hoy):
    categoria = _elegir_ponderado(rng, CATEGORIAS)
    tipo_doc = _elegir_ponderado(rng, TIPOS_DOC)
    fecha = hoy - timedelta(days=rng.randint(1, 400))
    items = []
    for _ in range(rng.randint(1, 4)):
        items.append({
            "nombre_item": rng.choice(ITEMS_POR_CATEGORIA[categoria]),
            "descripcion": "Descripcion generada %d" % rng.randint(1, 999),
            "categoria_item": categoria,
            "cantidad": rng.randint(1, 12),
            "p_unitario_sin_iva": rng.randrange(1000, 400000, 100),
        })
    proveedor_n = rng.randint(1, 60)
    dato = {
        "archivo": "DOC_%04d.jpg" % indice,
        "proyecto": rng.choice(PROYECTOS),
        "tipo_proyecto": rng.choice(TIPOS_PROYECTO),
        "fecha": fecha.strftime("%d-%m-%Y"),
        "n_documento": str(100000 + indice * 7),
        "tipo_documento": tipo_doc,
        "proveedor": "Proveedor Demo %03d SpA" % proveedor_n,
        "rut_proveedor": "7%07d-K" % proveedor_n,
        "categoria": categoria,
        "items": items,
        "estado": "Pendiente",
    }
    neto = _neto(dato)
    if tipo_doc in AFECTOS:
        dato["iva"] = round(neto * TASA)
        if categoria == "Combustible":
            # Combustible real: IVA + impuesto especifico, declarado aparte
            # (es la forma preferida segun severidad_cuadre_impuesto).
            otros = round(neto * 0.11)
            dato["iva"] = round(neto * TASA) + otros
            dato["otros_impuestos"] = otros
    return dato


def _reimpuestar(dato):
    """Recalcula el impuesto declarado a 19% exacto del neto vigente -- para
    que un defecto que NO es de impuesto no arrastre ademas un descuadre que
    nadie inyecto (y que ensuciaria la imputacion del ground truth)."""
    if dato["tipo_documento"] in AFECTOS:
        dato.pop("otros_impuestos", None)
        dato["iva"] = round(_neto(dato) * TASA)
    return dato


def _aplicar_defecto(rng, dato, clase, hoy):
    """Muta `dato` para que lleve el defecto `clase` y devuelve su registro de
    ground truth."""
    gt = {"archivo": dato["archivo"], "clase": clase, "campo": None, "valor_correcto": None}
    neto = _neto(dato)

    if clase == "SIN_ITEMS":
        gt["valor_correcto"] = dato["items"]
        dato["items"] = []
        return gt

    if clase == "N_DOC_ILEGIBLE":
        gt["campo"] = "n_documento"
        gt["valor_correcto"] = dato["n_documento"]
        dato["n_documento"] = "S/N (%s)" % dato["archivo"]
        return gt

    if clase == "IMPUESTO_MENOR":
        dato["tipo_documento"] = "Factura"
        dato["categoria"] = "Materiales"
        dato.pop("otros_impuestos", None)
        gt["campo"] = "iva"
        gt["valor_correcto"] = round(neto * TASA)
        dato["iva"] = round(neto * TASA) - max(50, round(neto * 0.04))
        return gt

    if clase == "IMPUESTO_EXCESO":
        dato["tipo_documento"] = "Factura"
        dato["categoria"] = "Materiales"
        for it in dato["items"]:
            it["categoria_item"] = "Materiales"
        dato.pop("otros_impuestos", None)
        gt["campo"] = "iva"
        gt["valor_correcto"] = round(neto * TASA)
        dato["iva"] = round(neto * TASA) + max(50, round(neto * 0.06))
        return gt

    if clase == "IMPUESTO_ESTIMADO":
        dato["tipo_documento"] = "Factura"
        dato["categoria"] = "Combustible"
        for it in dato["items"]:
            it["categoria_item"] = "Combustible"
        dato.pop("iva", None)
        dato.pop("otros_impuestos", None)
        gt["campo"] = "iva"
        # El impuesto realmente pagado en un combustible es IVA + especifico
        # (misma proporcion que los documentos limpios de esa categoria): eso
        # es lo que hay que declarar para resolver el hallazgo, no el 19%.
        gt["valor_correcto"] = round(neto * TASA) + round(neto * 0.11)
        return gt

    if clase == "CANTIDAD_INVALIDA":
        gt["campo"] = "cantidad"
        gt["valor_correcto"] = dato["items"][0]["cantidad"]
        dato["items"][0]["cantidad"] = 0
        _reimpuestar(dato)
        return gt

    if clase == "SIGNO_INVERTIDO_COMPRA":
        # Modela el incidente real "Signo de IVA / P.Unitario / Totales
        # (AYRSA)" de ERRORES.md: el extractor leyo el documento entero con el
        # signo cambiado. Se invierte TODO el documento, no una sola linea: una
        # linea negativa suelta en una factura es un DESCUENTO legitimo
        # (ERRORES.md registra varios), y marcarla seria un falso positivo.
        dato["tipo_documento"] = "Factura"
        gt["campo"] = "p_unitario_sin_iva"
        gt["valor_correcto"] = [it["p_unitario_sin_iva"] for it in dato["items"]]
        for it in dato["items"]:
            it["p_unitario_sin_iva"] = -it["p_unitario_sin_iva"]
        _reimpuestar(dato)
        return gt

    if clase == "NC_SIGNO_POSITIVO":
        # Nota de credito cuyos items quedaron en positivo: suma costo en vez
        # de restarlo. Los items NO se invierten a proposito.
        dato["tipo_documento"] = "Nota de Credito"
        dato["iva"] = -round(neto * TASA)
        gt["campo"] = "items"
        return gt

    if clase == "NC_IMPUESTO_DESCUADRADO":
        dato["tipo_documento"] = "Nota de Credito"
        for it in dato["items"]:
            it["p_unitario_sin_iva"] = -it["p_unitario_sin_iva"]
        neto2 = _neto(dato)
        gt["campo"] = "iva"
        gt["valor_correcto"] = round(neto2 * TASA)
        dato["iva"] = round(neto2 * TASA) + max(500, abs(round(neto2 * 0.07)))
        return gt

    if clase == "TIPO_DOC_DESCONOCIDO":
        gt["campo"] = "tipo_documento"
        gt["valor_correcto"] = dato["tipo_documento"]
        dato["tipo_documento"] = "Comprobante interno"
        dato.pop("iva", None)
        dato.pop("otros_impuestos", None)
        return gt

    if clase == "FECHA_INVALIDA":
        gt["campo"] = "fecha"
        gt["valor_correcto"] = dato["fecha"]
        dato["fecha"] = "32-13-2026"
        return gt

    if clase == "FECHA_FUTURA":
        gt["campo"] = "fecha"
        gt["valor_correcto"] = dato["fecha"]
        dato["fecha"] = (hoy + timedelta(days=rng.randint(40, 300))).strftime("%d-%m-%Y")
        return gt

    if clase == "ITEM_AGRUPADO":
        primero = dato["items"][0]
        monto = primero["cantidad"] * primero["p_unitario_sin_iva"]
        gt["campo"] = "items"
        gt["valor_correcto"] = [{
            "nombre_item": "Perfil acero", "descripcion": "Desglose recuperado",
            "categoria_item": dato["categoria"] or "Materiales",
            "cantidad": 1, "p_unitario_sin_iva": monto,
        }]
        primero["nombre_item"] = "Materiales varios"
        primero["descripcion"] = "Parte ilegible del documento (timbre)"
        primero["cantidad"] = 1
        primero["p_unitario_sin_iva"] = monto
        _reimpuestar(dato)
        return gt

    if clase == "PROVEEDOR_VACIO":
        gt["campo"] = "proveedor"
        gt["valor_correcto"] = dato["proveedor"]
        dato["proveedor"] = ""
        dato["rut_proveedor"] = ""
        return gt

    if clase == "CATEGORIA_VACIA":
        gt["campo"] = "categoria"
        gt["valor_correcto"] = dato["categoria"]
        dato["categoria"] = ""
        return gt

    raise ValueError("clase no soportada aca: %s" % clase)


# Cuantos documentos de cada clase de defecto se inyectan: 36 defectos sobre
# 240 documentos (15%), proporcion comparable a la del corpus real (35
# descuadres de impuesto + 34 numeros ilegibles + 8 duplicados + 25 items de
# precio invalido sobre 681 documentos).
RECETA = {
    "SIN_ENTRADA_JSON": 2,
    "SIN_ITEMS": 2,
    "N_DOC_ILEGIBLE": 4,
    "IMPUESTO_MENOR": 4,
    "IMPUESTO_EXCESO": 2,
    "IMPUESTO_ESTIMADO": 2,
    "DUPLICADO_EXACTO": 2,
    "DUPLICADO_AMBIGUO": 2,
    "CANTIDAD_INVALIDA": 2,
    "SIGNO_INVERTIDO_COMPRA": 2,
    "NC_SIGNO_POSITIVO": 2,
    "NC_IMPUESTO_DESCUADRADO": 2,
    "TIPO_DOC_DESCONOCIDO": 2,
    "FECHA_INVALIDA": 1,
    "FECHA_FUTURA": 1,
    "ITEM_AGRUPADO": 2,
    "PROVEEDOR_VACIO": 1,
    "CATEGORIA_VACIA": 1,
}

CLASES_INYECTADAS = tuple(RECETA)
TOTAL_DEFECTOS = sum(RECETA.values())


def generar_corpus(n_documentos=240, semilla=20260910, hoy=None):
    """Devuelve (documentos, defectos, archivos_sin_entrada).

    - documentos: lista lista para volcar como datos_extraidos.json
    - defectos:   ground truth, una entrada por defecto inyectado
    - archivos_sin_entrada: [(proyecto, archivo)] que existen en disco pero no
      tienen entrada en el JSON (defecto SIN_ENTRADA_JSON)

    Los primeros 20 documentos quedan SIEMPRE limpios: son el control con el
    que se mide la tasa de falsos positivos.
    """
    rng = random.Random(semilla)
    hoy = hoy or datetime(2026, 9, 10)

    documentos = [_documento_limpio(rng, i, hoy) for i in range(1, n_documentos + 1)]
    defectos = []
    archivos_sin_entrada = []

    disponibles = list(range(20, n_documentos))
    rng.shuffle(disponibles)

    for clase in RECETA:
        for _ in range(RECETA[clase]):
            idx = disponibles.pop()
            dato = documentos[idx]

            if clase == "SIN_ENTRADA_JSON":
                archivos_sin_entrada.append((dato["proyecto"], dato["archivo"]))
                defectos.append({"archivo": dato["archivo"], "clase": clase,
                                 "campo": None, "valor_correcto": None})
                documentos[idx] = None
                continue

            if clase in ("DUPLICADO_EXACTO", "DUPLICADO_AMBIGUO"):
                # El original se toma SIEMPRE de los 20 documentos de control,
                # que nunca reciben defecto: si se tomara del vecino podria
                # heredar un numero ya vuelto ilegible por otro defecto y el
                # duplicado dejaria de ser detectable por razones del corpus,
                # no del sistema. El informe nombra solo la copia, asi que el
                # original no se contamina como falso positivo.
                origen = documentos[len(defectos) % 20]
                dato["n_documento"] = origen["n_documento"]
                dato["proveedor"] = origen["proveedor"]
                dato["rut_proveedor"] = origen["rut_proveedor"]
                dato["tipo_documento"] = origen["tipo_documento"]
                if clase == "DUPLICADO_EXACTO":
                    dato["fecha"] = origen["fecha"]
                    dato["categoria"] = origen["categoria"]
                    dato["items"] = [dict(it) for it in origen["items"]]
                    for campo in ("iva", "otros_impuestos"):
                        if campo in origen:
                            dato[campo] = origen[campo]
                        else:
                            dato.pop(campo, None)
                defectos.append({"archivo": dato["archivo"], "clase": clase,
                                 "campo": "n_documento",
                                 "valor_correcto": origen["archivo"]})
                continue

            defectos.append(_aplicar_defecto(rng, dato, clase, hoy))

    documentos = [d for d in documentos if d is not None]
    return documentos, defectos, archivos_sin_entrada
