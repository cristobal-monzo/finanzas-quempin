# -*- coding: utf-8 -*-
"""Precios que no son una observación de precio y no pueden entrar al índice.

Pedido explícito del usuario (2026-09-08), tras ver una bomba figurando en
$0 en el cotizador: un ítem con precio cero no aporta información de costo y
arrastra hacia abajo el promedio de su hoja.
"""
from datetime import date, datetime

import openpyxl
import pytest

import cotizador_historico as ch


ENCABEZADOS_DETALLE = [
    "N° Ref.", "Nombre Ítem", "Descripción", "Categoría Ítem", "Cantidad",
    "P. Unitario sin IVA", "Total sin IVA (CLP)", "Total con IVA (CLP)",
]
ENCABEZADOS_MASTER = ["N° Ref.", "Fecha", "Proyecto", "Proveedor"]


def _excel(tmp_path, filas_detalle):
    """Excel mínimo con Detalle+Master, una fila de Master por cada N° Ref."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Detalle"
    ws.append(ENCABEZADOS_DETALLE)
    for fila in filas_detalle:
        ws.append(fila)

    wm = wb.create_sheet("Master")
    wm.append(ENCABEZADOS_MASTER)
    for ref in dict.fromkeys(f[0] for f in filas_detalle):
        wm.append([ref, datetime(2026, 1, 15), "CCON", "Anwo"])

    ruta = tmp_path / "Centro de Costos.xlsx"
    wb.save(ruta)
    return ruta


def _por_nombre(items, nombre):
    return next(i for i in items if i["nombre_item"] == nombre)


def test_precio_cero_queda_excluido(tmp_path):
    ruta = _excel(tmp_path, [
        ["CCON-001", "Bomba DAB", "Cod. 00.019.19 (figura en $0 en la factura)",
         "Materiales", 1, 0, 0, 0],
    ])
    items = ch.cargar_items_detalle(ruta)
    assert _por_nombre(items, "Bomba DAB")["excluido_motivo"] == "precio_cero"


def test_precio_cero_no_entra_a_la_busqueda(tmp_path):
    ruta = _excel(tmp_path, [
        ["CCON-001", "Bomba DAB", "Bomba en $0", "Materiales", 1, 0, 0, 0],
        ["CCON-002", "Bomba DAB", "Bomba con precio real", "Materiales", 1, 500000, 500000, 595000],
    ])
    items = ch.cargar_items_detalle(ruta)
    coincidencias, _ = ch.buscar_items(items, "bomba")
    assert [c["precio_unitario_sin_iva"] for c in coincidencias] == [500000]


def test_precio_cero_no_arrastra_el_promedio(tmp_path, monkeypatch):
    ruta = _excel(tmp_path, [
        ["CCON-001", "Bomba DAB", "Bomba en $0", "Materiales", 1, 0, 0, 0],
        ["CCON-002", "Bomba DAB", "Bomba con precio real", "Materiales", 1, 100, 100, 119],
    ])
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")
    monkeypatch.setattr(ch, "consultar_uf_api", lambda f: 40000.0)

    r = ch.consultar_item("bomba", ruta_excel=ruta, fecha_hoy=date(2026, 7, 17))

    assert r["promedio_reajustado"] == 100
    assert len(r["compras"]) == 1


def test_un_precio_bajo_pero_real_no_se_excluye(tmp_path):
    # El ítem más barato del catálogo real es un remache de $29: los precios
    # bajos son legítimos en ferretería, el filtro es solo contra el cero.
    ruta = _excel(tmp_path, [
        ["CCON-001", "Remache", "Remache Pop Rerar 4.8x20", "Materiales", 100, 29, 2900, 3451],
    ])
    items = ch.cargar_items_detalle(ruta)
    assert _por_nombre(items, "Remache")["excluido_motivo"] is None


def test_precio_no_finito_queda_excluido(tmp_path):
    # Un NaN pasa el chequeo de "es un número" pero envenena cualquier
    # promedio en silencio: NaN nunca es igual ni mayor ni menor a nada.
    ruta = _excel(tmp_path, [
        ["CCON-001", "Bomba rara", "Precio NaN", "Materiales", 1, float("nan"), 0, 0],
        ["CCON-002", "Bomba infinita", "Precio infinito", "Materiales", 1, float("inf"), 0, 0],
    ])
    items = ch.cargar_items_detalle(ruta)
    assert _por_nombre(items, "Bomba rara")["excluido_motivo"] == "precio_invalido"
    assert _por_nombre(items, "Bomba infinita")["excluido_motivo"] == "precio_invalido"


def test_el_precio_negativo_sigue_teniendo_su_propio_motivo(tmp_path):
    # No se fusiona con "precio_cero": las Notas de Crédito son otra cosa y
    # su motivo está documentado desde 2026-07-28.
    ruta = _excel(tmp_path, [
        ["CCON-001", "Devolución", "Nota de crédito", "Materiales", 1, -5000, -5000, -5950],
    ])
    items = ch.cargar_items_detalle(ruta)
    assert _por_nombre(items, "Devolución")["excluido_motivo"] == "precio_negativo"
