# -*- coding: utf-8 -*-
import contrapartes as cp
import intercambio as ic


def test_buscar_por_rut_sin_importar_el_formato(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    ic.publicar(raiz, "contrapartes", "sistema-quempin", {
        "clientes": [{"id": "1", "rut": "76.123.456-7", "razon_social": "Cliente SpA"}],
        "proveedores": [{"id": "2", "rut": "77.888.999-k", "razon_social": "Sodimac S.A."}],
    })
    (p,) = cp.buscar_por_rut(raiz, "77888999-K")
    assert p["razon_social"] == "Sodimac S.A." and p["tipo"] == "proveedor"
    assert cp.buscar_por_rut(raiz, "76123456-7")[0]["tipo"] == "cliente"
    assert cp.buscar_por_rut(raiz, "1-9") == []


def test_sin_publicacion_no_falla(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    assert cp.buscar_por_rut(raiz, "76.123.456-7") == []
