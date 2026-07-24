# -*- coding: utf-8 -*-
"""
datos_reportes.py -- Paquetes de datos de solo lectura (dict) para que el
agente redacte reportes PDF sin leer celdas de Excel a mano. Nunca escribe
Análisis de Proyectos.xlsx.
"""

import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

RAIZ_REPORTES = Path(__file__).resolve().parent
RAIZ_SISTEMA = RAIZ_REPORTES.parent / "Sistema"
if str(RAIZ_SISTEMA) not in sys.path:
    sys.path.insert(0, str(RAIZ_SISTEMA))

from analisis_financiero import HOJA_CLIENTES, HOJA_INDICADORES, HOJA_PROYECTOS  # noqa: E402

# Campos manuales que un proyecto debe tener cargados para generar reporte
# (spec §6). "Fecha de cierre" queda deliberadamente FUERA -- su ausencia (o
# una fecha futura) marca al proyecto como "en desarrollo", no incompleto.
# "Cliente"/"Categoría" tampoco cuentan -- se resuelven automaticamente, no
# son carga manual del usuario.
CAMPOS_MANUALES_REQUERIDOS = [
    "Estado", "Fecha de inicio", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados", "Mano de Obra Real",
]


class DatosIncompletosError(ValueError):
    """Un proyecto no tiene todos sus campos manuales requeridos cargados."""


def proyecto_tiene_datos_completos(proyecto: dict) -> bool:
    return all(
        proyecto.get(campo) not in (None, "") for campo in CAMPOS_MANUALES_REQUERIDOS
    )


def proyecto_esta_en_desarrollo(proyecto: dict, hoy: date | None = None) -> bool:
    """Sin 'Fecha de cierre', o con una posterior a 'hoy' (fecha real actual
    por defecto), el proyecto se considera en desarrollo. Un valor no
    interpretable como fecha se trata igual (conservador: en desarrollo)."""
    hoy = hoy or date.today()
    fecha_cierre = proyecto.get("Fecha de cierre")
    if not fecha_cierre:
        return True
    if isinstance(fecha_cierre, datetime):
        fecha_cierre = fecha_cierre.date()
    if not isinstance(fecha_cierre, date):
        return True
    return fecha_cierre > hoy


def _mapa_encabezados(ws) -> dict[str, int]:
    return {celda.value: idx + 1 for idx, celda in enumerate(ws[1]) if celda.value}


def _filas_por_columna(ws, mapa: dict[str, int], nombre_columna: str, valor):
    """Todas las filas (>=2) cuya columna nombre_columna == valor, como dicts
    encabezado->valor."""
    col = mapa.get(nombre_columna)
    if col is None:
        return []
    resultado = []
    for fila_idx in range(2, ws.max_row + 1):
        if ws.cell(row=fila_idx, column=col).value == valor:
            resultado.append({h: ws.cell(row=fila_idx, column=c).value for h, c in mapa.items()})
    return resultado


def paquete_datos_proyecto(ruta_excel: Path, tag: str) -> dict:
    """Datos de 'Proyectos' + 'Indicadores' para un proyecto por su TAG.
    Lanza DatosIncompletosError si le faltan campos manuales requeridos."""
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws_p = wb[HOJA_PROYECTOS]
    mapa_p = _mapa_encabezados(ws_p)
    filas = _filas_por_columna(ws_p, mapa_p, "TAG proyecto", tag)
    if not filas:
        raise ValueError(f"TAG de proyecto '{tag}' no encontrado en '{HOJA_PROYECTOS}'.")
    proyecto = filas[0]
    if not proyecto_tiene_datos_completos(proyecto):
        raise DatosIncompletosError(
            f"Proyecto '{tag}' no tiene todos sus datos manuales cargados -- "
            f"no se genera reporte hasta que se complete."
        )

    indicadores = {}
    if HOJA_INDICADORES in wb.sheetnames:
        ws_i = wb[HOJA_INDICADORES]
        mapa_i = _mapa_encabezados(ws_i)
        filas_i = _filas_por_columna(ws_i, mapa_i, "TAG proyecto", tag)
        if filas_i:
            indicadores = filas_i[0]

    return {
        "tipo": "proyecto",
        "tag": tag,
        "proyecto": proyecto,
        "indicadores": indicadores,
        "en_desarrollo": proyecto_esta_en_desarrollo(proyecto),
    }


def paquete_datos_cliente(ruta_excel: Path, nombre_cliente: str) -> dict:
    """CLTV de 'Clientes' + sus proyectos con datos completos de 'Proyectos'
    -- los incompletos se excluyen del agregado, no bloquean el reporte."""
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws_p = wb[HOJA_PROYECTOS]
    mapa_p = _mapa_encabezados(ws_p)
    proyectos = [
        p for p in _filas_por_columna(ws_p, mapa_p, "Cliente", nombre_cliente)
        if proyecto_tiene_datos_completos(p)
    ]

    cltv = {}
    if HOJA_CLIENTES in wb.sheetnames:
        ws_c = wb[HOJA_CLIENTES]
        mapa_c = _mapa_encabezados(ws_c)
        filas_c = _filas_por_columna(ws_c, mapa_c, "Cliente", nombre_cliente)
        if filas_c:
            cltv = filas_c[0]

    if not proyectos and not cltv:
        raise ValueError(
            f"Cliente '{nombre_cliente}' no encontrado, o ninguno de sus "
            f"proyectos tiene datos completos."
        )

    return {"tipo": "cliente", "cliente": nombre_cliente, "cltv": cltv, "proyectos": proyectos}


def paquete_datos_categoria(ruta_excel: Path, categoria: str) -> dict:
    """Proyectos con datos completos de 'Proyectos' cuya Categoría calza --
    los incompletos se excluyen del agregado."""
    wb = openpyxl.load_workbook(ruta_excel, data_only=True)
    ws_p = wb[HOJA_PROYECTOS]
    mapa_p = _mapa_encabezados(ws_p)
    proyectos = [
        p for p in _filas_por_columna(ws_p, mapa_p, "Categoría", categoria)
        if proyecto_tiene_datos_completos(p)
    ]
    if not proyectos:
        raise ValueError(f"Ningún proyecto con datos completos y Categoría '{categoria}'.")
    return {"tipo": "categoria", "categoria": categoria, "proyectos": proyectos}


_FUNCIONES_POR_TIPO = {
    "proyecto": paquete_datos_proyecto,
    "cliente": paquete_datos_cliente,
    "categoria": paquete_datos_categoria,
}


def paquete_datos_comparacion(ruta_excel: Path, entidades: list[tuple[str, str]]) -> dict:
    """entidades: lista de (tipo, identificador), tipo en 'proyecto'/'cliente'/'categoria'."""
    paquetes = []
    for tipo, identificador in entidades:
        funcion = _FUNCIONES_POR_TIPO.get(tipo)
        if funcion is None:
            raise ValueError(f"Tipo de entidad desconocido: '{tipo}'.")
        paquetes.append(funcion(ruta_excel, identificador))
    return {"tipo": "comparacion", "entidades": paquetes}
