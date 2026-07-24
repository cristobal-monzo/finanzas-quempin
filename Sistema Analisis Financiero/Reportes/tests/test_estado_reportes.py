# -*- coding: utf-8 -*-
import estado_reportes as er


def test_calcular_hash_es_estable_para_los_mismos_datos():
    datos = {"b": 2, "a": 1}
    assert er.calcular_hash_entidad(datos) == er.calcular_hash_entidad({"a": 1, "b": 2})


def test_calcular_hash_cambia_si_cambian_los_datos():
    h1 = er.calcular_hash_entidad({"margen": 100})
    h2 = er.calcular_hash_entidad({"margen": 200})
    assert h1 != h2


def test_cargar_estado_devuelve_vacio_si_no_existe(tmp_path):
    assert er.cargar_estado(tmp_path / "no-existe.json") == {}


def test_guardar_y_cargar_estado_hacen_roundtrip(tmp_path):
    ruta = tmp_path / "sub" / "estado_reportes.json"
    er.guardar_estado(ruta, {"proyecto:UMAG": {"hash": "abc", "generado_el": "2026-07-21"}})
    assert er.cargar_estado(ruta) == {"proyecto:UMAG": {"hash": "abc", "generado_el": "2026-07-21"}}


def test_detectar_desactualizados_marca_entidad_nueva():
    paquetes = {"proyecto:UMAG": {"margen": 100}}
    assert er.detectar_desactualizados(paquetes, {}) == ["proyecto:UMAG"]


def test_detectar_desactualizados_marca_si_el_hash_cambio():
    datos_viejos = {"margen": 100}
    datos_nuevos = {"margen": 150}
    estado = {"proyecto:UMAG": {"hash": er.calcular_hash_entidad(datos_viejos), "generado_el": "x"}}
    assert er.detectar_desactualizados({"proyecto:UMAG": datos_nuevos}, estado) == ["proyecto:UMAG"]


def test_detectar_desactualizados_no_marca_si_no_cambio():
    datos = {"margen": 100}
    estado = {"proyecto:UMAG": {"hash": er.calcular_hash_entidad(datos), "generado_el": "x"}}
    assert er.detectar_desactualizados({"proyecto:UMAG": datos}, estado) == []


def test_marcar_generado_actualiza_el_estado_sin_mutar_el_original():
    datos = {"margen": 100}
    estado_original = {}
    nuevo_estado = er.marcar_generado(estado_original, "proyecto:UMAG", datos, "2026-07-21")
    assert estado_original == {}
    assert nuevo_estado["proyecto:UMAG"]["hash"] == er.calcular_hash_entidad(datos)
    assert nuevo_estado["proyecto:UMAG"]["generado_el"] == "2026-07-21"
