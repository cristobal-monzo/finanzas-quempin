# -*- coding: utf-8 -*-
from datetime import date

import openpyxl
import pytest

import datos_reportes as dr

HEADERS_PROYECTOS_TEST = [
    "TAG proyecto", "Nombre del proyecto", "Cliente", "Estado",
    "Fecha de inicio", "Fecha de cierre", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados",
    "Costos Materiales Reales", "Costos Equipos Reales",
    "Otros Costos Reales", "Mano de Obra Real", "Total Proyectado",
    "Total Real", "Margen Proyectado", "Margen Real",
    "Desviación % (Real vs Proyectado)", "Categoría",
]  # mismo orden real que master (Cliente es la 3a columna, Categoria la ultima)


def _fila_proyecto_completa(**overrides) -> dict:
    """Fila 'feliz' con todos los campos manuales requeridos cargados --
    los tests parten de esto y sobreescriben lo que quieran romper/variar."""
    base = {
        "TAG proyecto": "UMAG", "Nombre del proyecto": "UMAG", "Cliente": "UMAG",
        "Estado": "Activo", "Fecha de inicio": date(2026, 1, 10),
        "Fecha de cierre": None, "Monto de Venta (sin IVA)": 1000000,
        "Costos Materiales Proyectados": 100000, "Costos Equipos Proyectados": 100000,
        "Mano de Obra Proyectada": 100000, "Otros Costos Proyectados": 100000,
        "Costos Materiales Reales": 90000, "Costos Equipos Reales": 90000,
        "Otros Costos Reales": 90000, "Mano de Obra Real": 90000,
        "Total Proyectado": 400000, "Total Real": 360000,
        "Margen Proyectado": 600000, "Margen Real": 640000,
        "Desviación % (Real vs Proyectado)": -0.1, "Categoría": "I+D+i",
    }
    base.update(overrides)
    return base


def _crear_excel_af(tmp_path, filas_proyectos: list[dict], filas_clientes: list[dict] | None = None):
    wb = openpyxl.Workbook()
    ws_p = wb.active
    ws_p.title = "Proyectos"
    for col, h in enumerate(HEADERS_PROYECTOS_TEST, start=1):
        ws_p.cell(row=1, column=col, value=h)
    for fila_idx, fila in enumerate(filas_proyectos, start=2):
        for col, h in enumerate(HEADERS_PROYECTOS_TEST, start=1):
            ws_p.cell(row=fila_idx, column=col, value=fila.get(h))

    ws_i = wb.create_sheet("Indicadores")
    headers_i = ["TAG proyecto", "Nombre del proyecto", "Rentabilidad sobre costo", "Margen neto %"]
    for col, h in enumerate(headers_i, start=1):
        ws_i.cell(row=1, column=col, value=h)
    ws_i.cell(row=2, column=1, value="UMAG")
    ws_i.cell(row=2, column=2, value="UMAG")
    ws_i.cell(row=2, column=4, value=0.2)

    ws_c = wb.create_sheet("Clientes")
    headers_c = ["Cliente", "AOV (Valor promedio de venta)", "CLTV", "Clasificación"]
    for col, h in enumerate(headers_c, start=1):
        ws_c.cell(row=1, column=col, value=h)
    for fila_idx, fila in enumerate(filas_clientes or [], start=2):
        for col, h in enumerate(headers_c, start=1):
            ws_c.cell(row=fila_idx, column=col, value=fila.get(h))

    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb.save(ruta)
    return ruta


def test_paquete_datos_proyecto_incluye_proyecto_indicadores_y_en_desarrollo(tmp_path):
    ruta = _crear_excel_af(
        tmp_path,
        [_fila_proyecto_completa()],  # Fecha de cierre = None -> en desarrollo
        [{"Cliente": "UMAG", "AOV (Valor promedio de venta)": 1000000, "CLTV": 200000, "Clasificación": "Clientes estratégicos"}],
    )
    paquete = dr.paquete_datos_proyecto(ruta, "UMAG")
    assert paquete["tipo"] == "proyecto"
    assert paquete["proyecto"]["Categoría"] == "I+D+i"
    assert paquete["indicadores"]["Margen neto %"] == 0.2
    assert paquete["en_desarrollo"] is True


def test_paquete_datos_proyecto_en_desarrollo_false_si_fecha_de_cierre_ya_paso(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(**{"Fecha de cierre": date(2020, 1, 1)}),
    ])
    paquete = dr.paquete_datos_proyecto(ruta, "UMAG")
    assert paquete["en_desarrollo"] is False


def test_paquete_datos_proyecto_lanza_valueerror_si_no_existe(tmp_path):
    ruta = _crear_excel_af(tmp_path, [_fila_proyecto_completa()])
    with pytest.raises(ValueError):
        dr.paquete_datos_proyecto(ruta, "NOEXISTE")


def test_paquete_datos_proyecto_lanza_datosincompletos_si_falta_un_campo_manual(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(**{"Mano de Obra Real": None}),
    ])
    with pytest.raises(dr.DatosIncompletosError):
        dr.paquete_datos_proyecto(ruta, "UMAG")


def test_paquete_datos_proyecto_no_requiere_fecha_de_cierre_para_estar_completo(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(**{"Fecha de cierre": None}),
    ])
    paquete = dr.paquete_datos_proyecto(ruta, "UMAG")  # no lanza DatosIncompletosError
    assert paquete["en_desarrollo"] is True


def test_paquete_datos_cliente_incluye_cltv_y_sus_proyectos(tmp_path):
    ruta = _crear_excel_af(
        tmp_path,
        [_fila_proyecto_completa()],
        [{"Cliente": "UMAG", "AOV (Valor promedio de venta)": 1000000, "CLTV": 200000, "Clasificación": "Clientes estratégicos"}],
    )
    paquete = dr.paquete_datos_cliente(ruta, "UMAG")
    assert paquete["tipo"] == "cliente"
    assert paquete["cltv"]["CLTV"] == 200000
    assert len(paquete["proyectos"]) == 1
    assert paquete["proyectos"][0]["TAG proyecto"] == "UMAG"


def test_paquete_datos_cliente_excluye_proyectos_incompletos(tmp_path):
    ruta = _crear_excel_af(
        tmp_path,
        [
            _fila_proyecto_completa(**{"TAG proyecto": "UMAG"}),
            _fila_proyecto_completa(**{
                "TAG proyecto": "UMAG2", "Nombre del proyecto": "UMAG Fase 2",
                "Monto de Venta (sin IVA)": None,  # incompleto -- se excluye del agregado
            }),
        ],
        [{"Cliente": "UMAG", "AOV (Valor promedio de venta)": 1000000, "CLTV": 200000, "Clasificación": "Clientes estratégicos"}],
    )
    paquete = dr.paquete_datos_cliente(ruta, "UMAG")
    assert len(paquete["proyectos"]) == 1
    assert paquete["proyectos"][0]["TAG proyecto"] == "UMAG"


def test_paquete_datos_categoria_agrupa_por_categoria(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(),
        _fila_proyecto_completa(**{
            "TAG proyecto": "CFLI", "Nombre del proyecto": "Cesfam Limache",
            "Cliente": "Cesfam Limache", "Categoría": "Mantenimiento",
        }),
    ])
    paquete = dr.paquete_datos_categoria(ruta, "Mantenimiento")
    assert paquete["tipo"] == "categoria"
    assert len(paquete["proyectos"]) == 1
    assert paquete["proyectos"][0]["TAG proyecto"] == "CFLI"


def test_paquete_datos_categoria_excluye_proyectos_incompletos(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(**{
            "TAG proyecto": "CFLI", "Cliente": "Cesfam Limache", "Categoría": "Mantenimiento",
        }),
        _fila_proyecto_completa(**{
            "TAG proyecto": "CCON", "Cliente": "Cesfam Constitución", "Categoría": "Mantenimiento",
            "Monto de Venta (sin IVA)": None,  # incompleto -- se excluye del agregado
        }),
    ])
    paquete = dr.paquete_datos_categoria(ruta, "Mantenimiento")
    assert len(paquete["proyectos"]) == 1
    assert paquete["proyectos"][0]["TAG proyecto"] == "CFLI"


def test_paquete_datos_categoria_lanza_valueerror_si_no_hay_proyectos(tmp_path):
    ruta = _crear_excel_af(tmp_path, [_fila_proyecto_completa()])
    with pytest.raises(ValueError):
        dr.paquete_datos_categoria(ruta, "Sin Categoria Real")


def test_paquete_datos_comparacion_combina_entidades(tmp_path):
    ruta = _crear_excel_af(tmp_path, [
        _fila_proyecto_completa(),
        _fila_proyecto_completa(**{
            "TAG proyecto": "CFLI", "Cliente": "Cesfam Limache", "Categoría": "Mantenimiento",
        }),
    ])
    paquete = dr.paquete_datos_comparacion(ruta, [("proyecto", "UMAG"), ("proyecto", "CFLI")])
    assert paquete["tipo"] == "comparacion"
    assert len(paquete["entidades"]) == 2
    assert paquete["entidades"][0]["proyecto"]["TAG proyecto"] == "UMAG"


def test_paquete_datos_comparacion_rechaza_tipo_desconocido(tmp_path):
    ruta = _crear_excel_af(tmp_path, [_fila_proyecto_completa()])
    with pytest.raises(ValueError):
        dr.paquete_datos_comparacion(ruta, [("no_existe", "UMAG")])
