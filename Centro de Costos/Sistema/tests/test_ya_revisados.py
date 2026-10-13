# -*- coding: utf-8 -*-
"""
Lo ya adjudicado no vuelve a contarse como pendiente (2026-10-13).

'run' no reabre un hallazgo cerrado contra el mismo valor de origen, pero
'status' y el cuadre de impuesto del PASO 13 los volvian a contar: con los 109
hallazgos reales ya cerrados, 'status' decia "46 errores, 59 por revisar".
"""

import auditor_centro_costos as acc


def _con_impuesto_menor():
    dato = {
        "archivo": "DOC_0001.jpg", "proyecto": "Proyecto Alfa", "tipo_proyecto": "Obra",
        "fecha": "15-07-2026", "n_documento": "12345", "tipo_documento": "Factura",
        "proveedor": "Proveedor Demo SpA", "rut_proveedor": "76123456-7",
        "categoria": "Materiales", "estado": "Pagado",
        "items": [{"nombre_item": "Perfil", "descripcion": "d", "categoria_item": "Materiales",
                   "cantidad": 1, "p_unitario_sin_iva": 100000}],
        "iva": 15000,  # el 19 % seria 19.000
    }
    return dato


def _registro_cerrado(hallazgos):
    reg = {"version": 1, "errores": []}
    acc.fusionar_hallazgos(reg, hallazgos, hoy="2026-09-10")
    for h in hallazgos:
        acc.cerrar_hallazgo(reg, h["id"], "descartado", "mirado el documento: esta bien", hoy="2026-09-11")
    acc.fusionar_hallazgos(reg, hallazgos, hoy="2026-09-12")   # origen igual: queda cerrado
    return reg


def test_un_hallazgo_cerrado_con_el_mismo_origen_es_ya_revisado():
    hallazgos, _ = acc.validar_corpus([_con_impuesto_menor()])
    assert hallazgos, "el documento de prueba debe tener un descuadre"
    reg = _registro_cerrado(hallazgos)
    por_revisar, ya_revisados = acc.separar_ya_revisados(hallazgos, reg)
    assert por_revisar == [] and len(ya_revisados) == len(hallazgos)


def test_si_el_origen_cambia_vuelve_a_estar_por_revisar():
    hallazgos, _ = acc.validar_corpus([_con_impuesto_menor()])
    reg = _registro_cerrado(hallazgos)
    otro = _con_impuesto_menor()
    otro["iva"] = 14000
    nuevos, _ = acc.validar_corpus([otro])
    por_revisar, ya_revisados = acc.separar_ya_revisados(nuevos, reg)
    assert ya_revisados == [] and len(por_revisar) == len(nuevos)


def test_sin_registro_todo_esta_por_revisar():
    hallazgos, _ = acc.validar_corpus([_con_impuesto_menor()])
    por_revisar, ya_revisados = acc.separar_ya_revisados(hallazgos, {"version": 1, "errores": []})
    assert ya_revisados == [] and por_revisar == hallazgos


def test_el_cuadre_del_paso_13_omite_los_documentos_ya_revisados():
    dato = _con_impuesto_menor()
    hallazgos, _ = acc.validar_corpus([dato])
    reg = _registro_cerrado(hallazgos)
    inconsistencias = acc.verificar_aritmetica([dato])
    assert inconsistencias and inconsistencias[0]["documento"] in acc.documentos_impuesto_ya_revisados(reg)


def test_un_hallazgo_de_impuesto_abierto_no_se_omite():
    dato = _con_impuesto_menor()
    hallazgos, _ = acc.validar_corpus([dato])
    reg = {"version": 1, "errores": []}
    acc.fusionar_hallazgos(reg, hallazgos, hoy="2026-09-10")
    assert acc.documentos_impuesto_ya_revisados(reg) == set()
