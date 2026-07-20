# -*- coding: utf-8 -*-
"""
analisis_financiero.py -- Consolidador de costos reales por proyecto para
QUEMPIN SpA. Lee Centro de Costos.xlsx (SOLO LECTURA, nunca lo escribe) y
mantiene Análisis de Proyectos.xlsx (3 hojas: Proyectos, Detalle Costos
Reales, Indicadores). Ver docs/superpowers/specs/2026-07-20-analisis-
financiero-design.md para el diseño completo.
"""

from pathlib import Path

import openpyxl

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────

RAIZ = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ.parent
RUTA_EXCEL = RAIZ_MODULO / "Análisis de Proyectos.xlsx"
RAIZ_RESPALDOS = RAIZ_MODULO / "Respaldos"

RAIZ_CENTRO_COSTOS = RAIZ_MODULO.parent / "Centro de Costos"
RUTA_EXCEL_CENTRO_COSTOS = RAIZ_CENTRO_COSTOS / "Excel" / "Centro de Costos.xlsx"
RAIZ_FACTURAS_CENTRO_COSTOS = (
    RAIZ_CENTRO_COSTOS / "Sitio de comunicación - Centro de Costos 1" / "Facturas y Boletas"
)

HOJA_PROYECTOS = "Proyectos"
HOJA_DETALLE_COSTOS_REALES = "Detalle Costos Reales"
HOJA_INDICADORES = "Indicadores"

HEADERS_PROYECTOS = [
    "TAG proyecto", "Nombre del proyecto", "Estado", "Fecha de inicio",
    "Fecha de cierre", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados",
    "Costos Materiales Reales", "Costos Equipos Reales",
    "Otros Costos Reales", "Mano de Obra Real", "Total Proyectado",
    "Total Real", "Margen Proyectado", "Margen Real",
    "Desviación % (Real vs Proyectado)",
]
HEADERS_DETALLE_COSTOS_REALES = ["TAG proyecto", "Subcategoría", "Bucket", "Total sin IVA"]
HEADERS_INDICADORES = [
    "TAG proyecto", "Nombre del proyecto", "Rentabilidad sobre costo",
    "Margen neto %", "Productividad Materiales", "Productividad Equipos",
    "Productividad MO", "Productividad Otros", "Costo Materiales % de venta",
    "Costo Equipos % de venta", "Costo MO % de venta", "Costo Otros % de venta",
    "Desviación % Materiales", "Desviación % Equipos", "Desviación % MO",
    "Desviación % Otros",
]


def asegurar_estructura_workbook(ruta_excel: Path) -> openpyxl.Workbook:
    """Abre ruta_excel si existe, o crea un libro nuevo. Garantiza que las 3
    hojas existan con encabezados en la fila 1 -- si una hoja ya existe, no
    la toca (regla de oro: no reescribir datos ya presentes). Elimina hojas
    default vacías ("Hoja1"/"Sheet") si quedaron de un libro recién creado."""
    if ruta_excel.exists():
        wb = openpyxl.load_workbook(ruta_excel)
    else:
        wb = openpyxl.Workbook()

    for nombre_hoja, headers in (
        (HOJA_PROYECTOS, HEADERS_PROYECTOS),
        (HOJA_DETALLE_COSTOS_REALES, HEADERS_DETALLE_COSTOS_REALES),
        (HOJA_INDICADORES, HEADERS_INDICADORES),
    ):
        if nombre_hoja not in wb.sheetnames:
            ws = wb.create_sheet(nombre_hoja)
            for col, encabezado in enumerate(headers, start=1):
                ws.cell(row=1, column=col, value=encabezado)

    for nombre_default in ("Hoja1", "Sheet"):
        if nombre_default in wb.sheetnames:
            ws_default = wb[nombre_default]
            esta_vacia = all(
                celda.value is None
                for fila in ws_default.iter_rows()
                for celda in fila
            )
            if esta_vacia:
                del wb[nombre_default]

    return wb
