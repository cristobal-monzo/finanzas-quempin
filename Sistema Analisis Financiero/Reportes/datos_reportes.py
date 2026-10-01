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

from analisis_financiero import (  # noqa: E402
    HOJA_DETALLE_COSTOS_REALES, HOJA_PROYECTOS, alertas_proyecto,
    calcular_peso_cartera, concentracion_cartera, percentil_inclusivo,
    sesgo_por_categoria, tiene_datos_completos,
)

from kpis_recalculados import (  # noqa: E402
    calcular_clientes_reporte, costos_reales_por_proyecto, recalcular_proyecto,
)

class DatosIncompletosError(ValueError):
    """Un proyecto no tiene todos sus campos manuales requeridos cargados."""


def proyecto_tiene_datos_completos(proyecto: dict) -> bool:
    """Regla unica compartida con el visualizador web -- ver la nota en
    analisis_financiero.py, seccion "COMPLETITUD DE UN PROYECTO". Los dicts
    de este modulo vienen keyed por encabezado, asi que el accesor es un
    .get() directo."""
    return tiene_datos_completos(proyecto.get)


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


def _todas_las_filas(ws, mapa: dict[str, int]) -> list[dict]:
    """Todas las filas (>=2), como dicts encabezado->valor."""
    return [
        {h: ws.cell(row=fila_idx, column=c).value for h, c in mapa.items()}
        for fila_idx in range(2, ws.max_row + 1)
    ]


def _todos_los_proyectos_recalculados(wb) -> list[dict]:
    """Lee 'Proyectos' + 'Detalle Costos Reales' (ambas data_only=True --
    'Detalle Costos Reales' sí trae valores literales, nunca fórmulas,
    analisis_financiero.py:612-635) y devuelve una entrada por proyecto con
    TAG: {"proyecto": <dict recalculado>, "indicadores": <dict
    recalculado>}. Nunca lee 'Indicadores'/'Clientes' -- openpyxl no
    cachea el resultado de una fórmula que él mismo escribe, así que esas
    hojas quedan en None hasta que alguien abre el Excel a mano (ver
    kpis_recalculados.py)."""
    ws_p = wb[HOJA_PROYECTOS]
    mapa_p = _mapa_encabezados(ws_p)
    ws_d = wb[HOJA_DETALLE_COSTOS_REALES]
    mapa_d = _mapa_encabezados(ws_d)

    costos_reales = costos_reales_por_proyecto(_todas_las_filas(ws_d, mapa_d))

    entradas = []
    for proyecto in _todas_las_filas(ws_p, mapa_p):
        tag = proyecto.get("TAG proyecto")
        if not tag:
            continue
        proyecto_actualizado, indicadores = recalcular_proyecto(
            proyecto, costos_reales.get(tag, {})
        )
        entradas.append({"proyecto": proyecto_actualizado, "indicadores": indicadores})
    return entradas


def abrir_libro(ruta_excel: Path):
    """Abre el libro de solo lectura. Existe para poder abrirlo UNA vez y
    pasarlo a varias paquete_datos_*: calcular los 20 reportes de la cartera
    abria el mismo archivo 20 veces (openpyxl cuesta ~0,3-0,8 s por
    apertura, ver CLAUDE.md raiz)."""
    return openpyxl.load_workbook(ruta_excel, data_only=True)


def _libro(ruta_excel: Path, wb):
    return wb if wb is not None else abrir_libro(ruta_excel)


def contexto_cartera(entradas: list[dict]) -> dict:
    """Numeros de TODA la cartera contra los que se lee una entidad: sin
    ellos, "margen 24%" no dice si es bueno o malo para QUEMPIN. Viaja en el
    paquete bajo la clave "_contexto" -- el "_" lo deja fuera del hash del
    manifiesto a proposito: cambia con cualquier proyecto ajeno, y si entrara
    al hash, tocar un solo proyecto dejaria los 20 reportes desactualizados.

    `entradas`: las de _todos_los_proyectos_recalculados (TODOS los proyectos
    del libro, completos o no)."""
    kpis = [
        {**e["indicadores"], **{
            k: e["proyecto"].get(k) for k in (
                "Cliente", "Categoría", "% Avance", "Monto de Venta (sin IVA)",
                "Costos Materiales Proyectados", "Costos Equipos Proyectados",
                "Mano de Obra Proyectada", "Otros Costos Proyectados",
                "Costos Materiales Reales", "Costos Equipos Reales",
                "Otros Costos Reales", "Mano de Obra Real",
            )
        }, "Datos completos": "Sí" if proyecto_tiene_datos_completos(e["proyecto"]) else "No"}
        for e in entradas
    ]
    completos = [k for k in kpis if k["Datos completos"] == "Sí"]
    ventas_por_cliente: dict[str, float] = {}
    for e in entradas:
        cliente = e["proyecto"].get("Cliente")
        venta = e["proyecto"].get("Monto de Venta (sin IVA)")
        if cliente and venta:
            ventas_por_cliente[cliente] = ventas_por_cliente.get(cliente, 0.0) + venta

    margenes = [
        k["Margen estimado al cierre %"] for k in completos
        if k["Margen estimado al cierre %"] is not None
    ]
    notas = [k["Nota del Proyecto"] for k in completos if k["Nota del Proyecto"] is not None]
    return {
        "n_proyectos_completos": len(completos),
        "peso_cartera": calcular_peso_cartera({
            e["proyecto"]["TAG proyecto"]: e["proyecto"].get("Monto de Venta (sin IVA)")
            for e in entradas
        }),
        "venta_total": sum(ventas_por_cliente.values()),
        "margen_mediano": percentil_inclusivo(margenes, 0.5) if margenes else None,
        "nota_mediana": percentil_inclusivo(notas, 0.5) if notas else None,
        "sesgo_por_categoria": sesgo_por_categoria(completos),
        "concentracion": concentracion_cartera(ventas_por_cliente),
    }


def paquete_datos_proyecto(ruta_excel: Path, tag: str, wb=None) -> dict:
    """Datos de 'Proyectos' + KPIs derivados (recalculados en Python, ver
    kpis_recalculados.py) para un proyecto por su TAG. Lanza
    DatosIncompletosError si le faltan campos manuales requeridos."""
    entradas = _todos_los_proyectos_recalculados(_libro(ruta_excel, wb))
    entrada = next(
        (e for e in entradas if e["proyecto"].get("TAG proyecto") == tag), None,
    )
    if entrada is None:
        raise ValueError(f"TAG de proyecto '{tag}' no encontrado en '{HOJA_PROYECTOS}'.")
    proyecto = entrada["proyecto"]
    if not proyecto_tiene_datos_completos(proyecto):
        raise DatosIncompletosError(
            f"Proyecto '{tag}' no tiene todos sus datos manuales cargados -- "
            f"no se genera reporte hasta que se complete."
        )

    return {
        "tipo": "proyecto",
        "tag": tag,
        "proyecto": proyecto,
        "indicadores": entrada["indicadores"],
        "en_desarrollo": proyecto_esta_en_desarrollo(proyecto),
        # Las alertas ya existian (consola del run y dashboard) pero no
        # llegaban al PDF, que es justo donde se revisa un proyecto uno por
        # uno. Van en el paquete y por lo tanto en el hash: si aparece o se
        # cierra una alerta, ese reporte queda desactualizado.
        # ("Datos completos" no viaja en `indicadores` -- no es un KPI del
        # proyecto, es la columna de apoyo de la hoja Clientes; acá ya se
        # sabe que es "Sí" porque el guard de arriba no lanzó.)
        "alertas": alertas_proyecto(
            proyecto, {**proyecto, **entrada["indicadores"], "Datos completos": "Sí"},
        ),
        "_contexto": contexto_cartera(entradas),
    }


def _proyecto_plano(entrada: dict) -> dict:
    """Un proyecto con sus columnas de 'Proyectos' y sus indicadores en un
    solo dict. Los reportes de cliente/categoría listan un proyecto por fila
    con su Nota y su margen estimado al cierre, que viven en 'Indicadores';
    los nombres de columna de las dos hojas no se pisan entre sí."""
    return {**entrada["proyecto"], **entrada["indicadores"]}


def paquete_datos_cliente(ruta_excel: Path, nombre_cliente: str, wb=None) -> dict:
    """KPIs del cliente (hoja 'Clientes', recalculados en Python: N° de
    proyectos, venta y margen acumulados, margen %, si es recurrente y su
    Clasificación) + sus proyectos con datos completos -- los incompletos se
    excluyen del agregado, no bloquean el reporte. Los KPIs se calculan
    sobre TODOS los proyectos del libro (la Clasificación es un percentil
    entre todos los clientes) y luego se toma la fila de este cliente.

    'kpis_cliente' reemplazó a la clave 'cltv' el 2026-09-21, junto con el
    CLTV (ver analisis_financiero.calcular_clientes)."""
    entradas = _todos_los_proyectos_recalculados(_libro(ruta_excel, wb))
    proyectos_cliente = [
        _proyecto_plano(e) for e in entradas
        if proyecto_tiene_datos_completos(e["proyecto"]) and e["proyecto"].get("Cliente") == nombre_cliente
    ]
    kpis_cliente = calcular_clientes_reporte(entradas).get(nombre_cliente, {})

    if not proyectos_cliente and not kpis_cliente:
        raise ValueError(
            f"Cliente '{nombre_cliente}' no encontrado, o ninguno de sus "
            f"proyectos tiene datos completos."
        )

    return {
        "tipo": "cliente", "cliente": nombre_cliente,
        "kpis_cliente": kpis_cliente, "proyectos": proyectos_cliente,
        "_contexto": contexto_cartera(entradas),
    }


def paquete_datos_categoria(ruta_excel: Path, categoria: str, wb=None) -> dict:
    """Proyectos con datos completos (recalculados en Python) cuya
    Categoría calza -- los incompletos se excluyen del agregado."""
    entradas = _todos_los_proyectos_recalculados(_libro(ruta_excel, wb))
    proyectos = [
        _proyecto_plano(e) for e in entradas
        if proyecto_tiene_datos_completos(e["proyecto"]) and e["proyecto"].get("Categoría") == categoria
    ]
    if not proyectos:
        raise ValueError(f"Ningún proyecto con datos completos y Categoría '{categoria}'.")
    return {
        "tipo": "categoria", "categoria": categoria, "proyectos": proyectos,
        "_contexto": contexto_cartera(entradas),
    }


_FUNCIONES_POR_TIPO = {
    "proyecto": paquete_datos_proyecto,
    "cliente": paquete_datos_cliente,
    "categoria": paquete_datos_categoria,
}


def paquete_datos_comparacion(ruta_excel: Path, entidades: list[tuple[str, str]], wb=None) -> dict:
    """entidades: lista de (tipo, identificador), tipo en 'proyecto'/'cliente'/'categoria'."""
    wb = _libro(ruta_excel, wb)
    paquetes = []
    for tipo, identificador in entidades:
        funcion = _FUNCIONES_POR_TIPO.get(tipo)
        if funcion is None:
            raise ValueError(f"Tipo de entidad desconocido: '{tipo}'.")
        paquetes.append(funcion(ruta_excel, identificador, wb))
    return {"tipo": "comparacion", "entidades": paquetes}
