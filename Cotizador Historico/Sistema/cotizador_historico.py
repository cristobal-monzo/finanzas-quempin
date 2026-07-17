# -*- coding: utf-8 -*-
"""
cotizador_historico.py — estima el costo actual de un item a partir de sus
compras historicas en Centro de Costos, reajustando cada precio por UF
(fecha de compra -> fecha de la consulta).

Modulo 100% de solo lectura sobre Centro de Costos.xlsx: nunca lo abre en
modo escritura ni lo modifica. Ver ../docs/superpowers/specs/
2026-07-17-cotizador-historico-design.md para el diseno completo.
"""

from datetime import date, datetime
from pathlib import Path
import unicodedata
from difflib import SequenceMatcher
import json
import urllib.error
import urllib.request

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


UMBRAL_SIMILITUD = 0.6
UMBRAL_SUGERENCIA = 0.4
MAX_SUGERENCIAS = 5


def normalizar_texto(texto):
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def similitud(a, b):
    """1.0 si uno es substring del otro (Nombre Item ya viene normalizado a
    terminos genericos, ver Centro de Costos/CLAUDE.md); si no, ratio de
    difflib para tolerar typos/variantes."""
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def buscar_items(items, texto_busqueda, umbral=UMBRAL_SIMILITUD, umbral_sugerencia=UMBRAL_SUGERENCIA):
    """Busqueda difusa de texto_busqueda contra Nombre Item/Descripcion.
    Devuelve (coincidencias, sugerencias): coincidencias son items (dicts
    sin modificar) con similitud >= umbral, ordenados de mayor a menor;
    sugerencias son hasta MAX_SUGERENCIAS nombre_item distintos con
    similitud en [umbral_sugerencia, umbral), para cuando no hay match
    directo. Items con excluido_motivo != None se ignoran siempre."""
    consulta = normalizar_texto(texto_busqueda)
    puntuadas = []
    for item in items:
        if item["excluido_motivo"] is not None:
            continue
        s = max(
            similitud(consulta, normalizar_texto(item["nombre_item"])),
            similitud(consulta, normalizar_texto(item["descripcion"])),
        )
        puntuadas.append((s, item))
    puntuadas.sort(key=lambda par: -par[0])

    coincidencias = [item for s, item in puntuadas if s >= umbral]

    sugerencias = []
    for s, item in puntuadas:
        if umbral_sugerencia <= s < umbral and item["nombre_item"] not in sugerencias:
            sugerencias.append(item["nombre_item"])
        if len(sugerencias) >= MAX_SUGERENCIAS:
            break
    return coincidencias, sugerencias


class UFNoDisponibleError(Exception):
    """No se pudo obtener el valor de la UF para una fecha desde mindicador.cl."""


URL_MINDICADOR_UF = "https://mindicador.cl/api/uf/{fecha}"


def consultar_uf_api(fecha):
    """Llama a mindicador.cl y devuelve el valor UF (float) para 'fecha'
    (date o datetime). Lanza UFNoDisponibleError si falla la conexion, la
    respuesta no es JSON valido, o no trae serie de datos. Nunca cachea en
    disco -- eso lo hace el llamador via obtener_valor_uf/guardar_cache_uf."""
    url = URL_MINDICADOR_UF.format(fecha=fecha.strftime("%d-%m-%Y"))
    try:
        with urllib.request.urlopen(url, timeout=10) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UFNoDisponibleError(f"No se pudo consultar mindicador.cl para {fecha}: {exc}") from exc

    serie = datos.get("serie") or []
    if not serie:
        raise UFNoDisponibleError(f"mindicador.cl no tiene valor de UF para {fecha}")
    return serie[0]["valor"]


def cargar_cache_uf(ruta_cache=None):
    ruta = Path(ruta_cache) if ruta_cache is not None else RUTA_CACHE_UF
    if not ruta.exists():
        return {}
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_cache_uf(cache, ruta_cache=None):
    ruta = Path(ruta_cache) if ruta_cache is not None else RUTA_CACHE_UF
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def obtener_valor_uf(fecha, cache_uf):
    """Valor UF para una fecha HISTORICA (compra pasada), usando cache_uf
    (dict fecha_iso->valor, mutado in-place) para no repetir llamadas a la
    API. El llamador decide si persiste cache_uf con guardar_cache_uf. No
    usar esta funcion para la UF de "hoy" -- ver consultar_item (Task 4),
    que llama a consultar_uf_api directo para hoy, sin pasar por el cache
    de archivo."""
    fecha_iso = fecha.strftime("%Y-%m-%d")
    if fecha_iso in cache_uf:
        return cache_uf[fecha_iso]
    valor = consultar_uf_api(fecha)
    cache_uf[fecha_iso] = valor
    return valor


def calcular_precio_reajustado(precio_original, uf_fecha_compra, uf_hoy):
    factor = uf_hoy / uf_fecha_compra
    return round(precio_original * factor)


def consultar_item(texto_busqueda, ruta_excel=None, fecha_hoy=None):
    """Orquesta una consulta completa: carga Detalle, busca por texto,
    reajusta cada compra encontrada por UF, y agrega promedio/rango.
    fecha_hoy es inyectable para tests (default: date.today())."""
    hoy = fecha_hoy or date.today()
    items = cargar_items_detalle(ruta_excel)
    excluidos_count = sum(1 for it in items if it["excluido_motivo"] is not None)

    coincidencias, sugerencias = buscar_items(items, texto_busqueda)
    if not coincidencias:
        return {
            "encontrado": False,
            "compras": [],
            "promedio_reajustado": None,
            "rango_minimo": None,
            "rango_maximo": None,
            "excluidos_count": excluidos_count,
            "sugerencias": sugerencias,
        }

    uf_hoy = consultar_uf_api(hoy)
    cache_uf = cargar_cache_uf()
    compras = []
    for item in coincidencias:
        uf_compra = obtener_valor_uf(item["fecha"], cache_uf)
        precio_reajustado = calcular_precio_reajustado(
            item["precio_unitario_sin_iva"], uf_compra, uf_hoy,
        )
        compras.append({
            "n_ref": item["n_ref"],
            "fecha": item["fecha"].strftime("%Y-%m-%d"),
            "precio_original_sin_iva": item["precio_unitario_sin_iva"],
            "precio_reajustado_hoy": precio_reajustado,
        })
    guardar_cache_uf(cache_uf)

    reajustados = [c["precio_reajustado_hoy"] for c in compras]
    return {
        "encontrado": True,
        "compras": compras,
        "promedio_reajustado": round(sum(reajustados) / len(reajustados)),
        "rango_minimo": min(reajustados),
        "rango_maximo": max(reajustados),
        "excluidos_count": excluidos_count,
        "sugerencias": [],
    }
