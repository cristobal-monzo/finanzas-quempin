# -*- coding: utf-8 -*-
"""
cotizador_historico.py — estima el costo actual de un item a partir de sus
compras historicas en Centro de Costos, reajustando cada precio por UF
(fecha de compra -> fecha de la consulta).

Modulo 100% de solo lectura sobre Centro de Costos.xlsx: nunca lo abre en
modo escritura ni lo modifica. Ver ../docs/superpowers/specs/
2026-07-17-cotizador-historico-design.md para el diseno completo.
"""

from datetime import datetime
from pathlib import Path

import openpyxl

RAIZ_MODULO = Path(__file__).resolve().parent.parent
RUTA_EXCEL_CENTRO_COSTOS = RAIZ_MODULO.parent / "Centro de Costos" / "Excel" / "Centro de Costos.xlsx"
RUTA_CACHE_UF = Path(__file__).resolve().parent / "uf_cache.json"


class ExcelNoDisponibleError(Exception):
    """El archivo Centro de Costos.xlsx no existe o no se pudo abrir para lectura."""


def mapear_encabezados(hoja):
    """dict {texto_encabezado: numero_columna (1-based)} leyendo la fila 1."""
    fila = next(hoja.iter_rows(min_row=1, max_row=1))
    return {celda.value: celda.column for celda in fila if celda.value}


def _fechas_por_ref(ws_master):
    cols = mapear_encabezados(ws_master)
    col_ref = cols["N° Ref."]
    col_fecha = cols["Fecha"]
    fechas = {}
    for fila in ws_master.iter_rows(min_row=2):
        n_ref = fila[col_ref - 1].value
        if n_ref:
            fechas[n_ref] = fila[col_fecha - 1].value
    return fechas


def cargar_items_detalle(ruta_excel=None):
    """Lee Detalle+Master de Centro de Costos.xlsx (solo lectura) y devuelve
    una lista de dicts, uno por item de linea de Detalle, con su fecha ya
    resuelta via Master (cruce por N Ref.).

    Items cuyo N Ref. no tiene fila en Master, o cuya Fecha en Master no es
    un datetime valido, quedan con excluido_motivo poblado ("sin_master" o
    "fecha_invalida") y fecha=None -- no deben entrar a ninguna busqueda ni
    agregacion posterior."""
    ruta = Path(ruta_excel) if ruta_excel is not None else RUTA_EXCEL_CENTRO_COSTOS
    try:
        wb = openpyxl.load_workbook(str(ruta), data_only=True, read_only=True)
    except FileNotFoundError as exc:
        raise ExcelNoDisponibleError(f"No existe {ruta}") from exc
    except PermissionError as exc:
        raise ExcelNoDisponibleError(f"No se pudo abrir {ruta} para lectura: {exc}") from exc

    try:
        ws_detalle = wb["Detalle"]
        ws_master = wb["Master"]
        fechas = _fechas_por_ref(ws_master)
        cols = mapear_encabezados(ws_detalle)
        col_ref = cols["N° Ref."]
        col_nombre = cols["Nombre Ítem"]
        col_desc = cols["Descripción"]
        col_precio = cols["P. Unitario sin IVA"]

        items = []
        for fila in ws_detalle.iter_rows(min_row=2):
            n_ref = fila[col_ref - 1].value
            if not n_ref:
                continue
            fecha = fechas.get(n_ref)
            if n_ref not in fechas:
                excluido_motivo = "sin_master"
            elif not isinstance(fecha, datetime):
                excluido_motivo = "fecha_invalida"
            else:
                excluido_motivo = None
            items.append({
                "n_ref": n_ref,
                "nombre_item": fila[col_nombre - 1].value or "",
                "descripcion": fila[col_desc - 1].value or "",
                "precio_unitario_sin_iva": fila[col_precio - 1].value,
                "fecha": fecha if excluido_motivo is None else None,
                "excluido_motivo": excluido_motivo,
            })
        return items
    finally:
        wb.close()
