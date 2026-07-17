from datetime import datetime

import openpyxl
import pytest

import cotizador_historico as ch


def _crear_excel_prueba(tmp_path, filas_detalle, filas_master):
    """filas_detalle: lista de tuplas (n_ref, nombre_item, descripcion, precio_unitario_sin_iva)
    filas_master: lista de tuplas (n_ref, fecha)"""
    wb = openpyxl.Workbook()
    ws_detalle = wb.active
    ws_detalle.title = "Detalle"
    for c, h in enumerate(["N° Ref.", "Nombre Ítem", "Descripción", "P. Unitario sin IVA"], 1):
        ws_detalle.cell(row=1, column=c, value=h)
    for r, fila in enumerate(filas_detalle, 2):
        for c, valor in enumerate(fila, 1):
            ws_detalle.cell(row=r, column=c, value=valor)

    ws_master = wb.create_sheet("Master")
    for c, h in enumerate(["N° Ref.", "Fecha"], 1):
        ws_master.cell(row=1, column=c, value=h)
    for r, fila in enumerate(filas_master, 2):
        for c, valor in enumerate(fila, 1):
            ws_master.cell(row=r, column=c, value=valor)

    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(ruta)
    return ruta


def test_mapear_encabezados_lee_fila_1(tmp_path):
    ruta = _crear_excel_prueba(tmp_path, filas_detalle=[], filas_master=[])
    wb = openpyxl.load_workbook(ruta, read_only=True)
    cols = ch.mapear_encabezados(wb["Detalle"])
    assert cols["N° Ref."] == 1
    assert cols["Nombre Ítem"] == 2
    assert cols["Descripción"] == 3
    assert cols["P. Unitario sin IVA"] == 4


def test_cargar_items_detalle_resuelve_fecha_via_master(tmp_path):
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-001", "Taladro", "Taladro percutor 20V", 90000)],
        filas_master=[("UMAG-001", datetime(2026, 1, 15))],
    )
    items = ch.cargar_items_detalle(ruta)
    assert len(items) == 1
    item = items[0]
    assert item["n_ref"] == "UMAG-001"
    assert item["nombre_item"] == "Taladro"
    assert item["descripcion"] == "Taladro percutor 20V"
    assert item["precio_unitario_sin_iva"] == 90000
    assert item["fecha"] == datetime(2026, 1, 15)
    assert item["excluido_motivo"] is None


def test_cargar_items_detalle_excluye_item_sin_master(tmp_path):
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-002", "Cemento", "Saco 25kg", 5000)],
        filas_master=[],
    )
    items = ch.cargar_items_detalle(ruta)
    assert items[0]["excluido_motivo"] == "sin_master"
    assert items[0]["fecha"] is None


def test_cargar_items_detalle_excluye_fecha_no_parseable(tmp_path):
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-003", "Cable", "Cable 10m", 3000)],
        filas_master=[("UMAG-003", "sin fecha")],
    )
    items = ch.cargar_items_detalle(ruta)
    assert items[0]["excluido_motivo"] == "fecha_invalida"
    assert items[0]["fecha"] is None


def test_cargar_items_detalle_ignora_filas_sin_n_ref(tmp_path):
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-004", "Pintura", "Balde 1 galón", 15000), (None, None, None, None)],
        filas_master=[("UMAG-004", datetime(2026, 2, 1))],
    )
    items = ch.cargar_items_detalle(ruta)
    assert len(items) == 1


def test_cargar_items_detalle_archivo_inexistente_lanza_error(tmp_path):
    ruta = tmp_path / "no existe.xlsx"
    with pytest.raises(ch.ExcelNoDisponibleError):
        ch.cargar_items_detalle(ruta)


def test_cargar_items_detalle_excluye_precio_invalido(tmp_path):
    ruta = _crear_excel_prueba(
        tmp_path,
        filas_detalle=[("UMAG-005", "Guante", "Guante de cuero", None)],
        filas_master=[("UMAG-005", datetime(2026, 2, 1))],
    )
    items = ch.cargar_items_detalle(ruta)
    assert items[0]["excluido_motivo"] == "precio_invalido"
    assert items[0]["fecha"] is None


def test_cargar_items_detalle_falta_hoja_master_lanza_error_claro(tmp_path):
    wb = openpyxl.Workbook()
    ws_detalle = wb.active
    ws_detalle.title = "Detalle"
    for c, h in enumerate(["N° Ref.", "Nombre Ítem", "Descripción", "P. Unitario sin IVA"], 1):
        ws_detalle.cell(row=1, column=c, value=h)
    ruta = tmp_path / "sin_master.xlsx"
    wb.save(ruta)

    with pytest.raises(ch.ExcelNoDisponibleError):
        ch.cargar_items_detalle(ruta)
