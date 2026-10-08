# -*- coding: utf-8 -*-
"""
cotizador_historico.py — estima el costo actual de un item a partir de sus
compras historicas en Centro de Costos, reajustando cada precio por UF
(fecha de compra -> fecha de la consulta).

Modulo 100% de solo lectura sobre Centro de Costos.xlsx: nunca lo abre en
modo escritura ni lo modifica. Ver ../docs/specs/
2026-07-17-cotizador-historico-design.md para el diseno completo.
"""

from datetime import date, datetime
from pathlib import Path
import math
import os
import sys
import unicodedata
import json
import urllib.error
import urllib.request
import zipfile

import openpyxl

# taxonomia.py vive junto a este archivo. Se asegura el directorio propio en
# sys.path porque hay llamadores que importan este modulo por ruta (los
# build_visualizador.py de Chile y Peru, y el driver de la skill).
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import busqueda  # noqa: E402
import dimensiones  # noqa: E402
import presentacion  # noqa: E402
import taxonomia  # noqa: E402

RAIZ_MODULO = Path(__file__).resolve().parent.parent
RUTA_EXCEL_CENTRO_COSTOS = RAIZ_MODULO.parent / "Centro de Costos" / "Excel" / "Centro de Costos.xlsx"
RUTA_CACHE_UF = Path(__file__).resolve().parent / "uf_cache.json"

RUTA_EXCEL_CENTRO_COSTOS_PERU = RAIZ_MODULO.parent / "Peru" / "Centro de Costos" / "Excel" / "Centro de Costos Perú.xlsx"

# Config por pais -- solo lo que este modulo necesita (nombres de columna
# que varian entre IVA/CLP y IGV/PEN, y la ruta del Excel por defecto).
# Mismo patron que PAISES en Centro de Costos/Sistema/auditor_centro_costos.py,
# a proposito no comparte esa tabla -- este modulo no importa ese archivo.
PAISES = {
    "CL": {
        "ruta_excel": RUTA_EXCEL_CENTRO_COSTOS,
        "col_precio_unitario": "P. Unitario sin IVA",
        "col_total_sin_iva": "Total sin IVA (CLP)",
        "col_total_con_iva": "Total con IVA (CLP)",
    },
    "PE": {
        "ruta_excel": RUTA_EXCEL_CENTRO_COSTOS_PERU,
        "col_precio_unitario": "P. Unitario sin IGV",
        "col_total_sin_iva": "Total sin IGV (PEN)",
        "col_total_con_iva": "Total con IGV (PEN)",
    },
}


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


def _proyecto_proveedor_por_ref(ws_master):
    """dict {n_ref: (proyecto, proveedor_tag)} -- ambas columnas son
    opcionales (None si Master no las tiene), a diferencia de N Ref./Fecha
    que _fechas_por_ref exige porque son estructurales."""
    cols = mapear_encabezados(ws_master)
    col_ref = cols["N° Ref."]
    col_proyecto = cols.get("Proyecto")
    col_proveedor = cols.get("Proveedor")
    meta = {}
    for fila in ws_master.iter_rows(min_row=2):
        n_ref = fila[col_ref - 1].value
        if n_ref:
            meta[n_ref] = (
                fila[col_proyecto - 1].value if col_proyecto else None,
                fila[col_proveedor - 1].value if col_proveedor else None,
            )
    return meta


def cargar_items_detalle(ruta_excel=None, pais="CL"):
    """Lee Detalle+Master de Centro de Costos.xlsx (solo lectura) y devuelve
    una lista de dicts, uno por item de linea de Detalle, con su fecha ya
    resuelta via Master (cruce por N Ref.). Incluye "total_sin_iva"/
    "total_con_iva" de esa misma fila (permiten derivar la tasa real de IVA
    del documento, ver tasa_iva_real, sin asumir 19% fijo).

    'pais' ("CL" o "PE") selecciona los nombres de columna y la ruta por
    defecto via PAISES -- "CL" preserva exactamente el comportamiento
    anterior a este parametro.

    Items cuyo N Ref. no tiene fila en Master, cuya Fecha en Master no es un
    datetime valido, cuyo precio unitario no es un numero, o cuyo precio
    unitario es negativo, quedan con excluido_motivo poblado ("sin_master",
    "fecha_invalida", "precio_invalido", "precio_negativo" o "precio_cero")
    y fecha=None -- no deben entrar a ninguna busqueda ni agregacion
    posterior.

    "precio_cero" es la defensa contra los items que la factura trae en $0
    (pedido explicito del usuario 2026-09-08, tras ver una "Bomba DAB
    circuladora" figurando en $0 en el cotizador): son lineas incluidas sin
    cargo dentro de un documento, no una observacion de precio, y arrastran
    hacia abajo el promedio de su hoja. Se filtra solo el cero exacto, no
    los precios bajos: el item mas barato del catalogo real es un remache de
    $29 y es perfectamente legitimo, asi que cualquier umbral minimo
    arbitrario borraria datos buenos.

    "precio_negativo" es la defensa contra Notas de Credito (devoluciones):
    sus items de Detalle vienen con P. Unitario sin IVA negativo (ver
    UMAG-025, ej. real), y promediarlos junto a compras reales produce un
    "costo actual" mas barato que cualquier compra real -- no sirve para
    evaluar costos futuros. Se filtra por signo del precio, no por "Tipo
    Documento" de Master (que este modulo no lee), porque cargar_items_detalle
    opera a nivel de Detalle y una devolucion siempre es negativa
    independiente de como haya quedado tipificado el documento. Pedido
    explicito del usuario 2026-07-28 -- no reintroducir Notas de Credito al
    indice de este modulo."""
    cfg = PAISES[pais]
    ruta = Path(ruta_excel) if ruta_excel is not None else cfg["ruta_excel"]
    try:
        wb = openpyxl.load_workbook(str(ruta), data_only=True, read_only=True)
    except FileNotFoundError as exc:
        raise ExcelNoDisponibleError(f"No existe {ruta}") from exc
    except PermissionError as exc:
        raise ExcelNoDisponibleError(f"No se pudo abrir {ruta} para lectura: {exc}") from exc
    except (zipfile.BadZipFile, KeyError) as exc:
        # zipfile.BadZipFile: el archivo no es un .xlsx valido (ej. quedo a
        # medio escribir por un corte de OneDrive/energia durante un guardado
        # de Centro de Costos). KeyError: es un zip valido pero le faltan las
        # partes internas que openpyxl espera de un xlsx (mismo tipo de
        # corrupcion parcial). Antes de este fix, cualquiera de las dos
        # tumbaba con una traza cruda de zipfile/openpyxl en vez de un error
        # claro y accionable, unico caso de este modulo sin ese tratamiento.
        raise ExcelNoDisponibleError(f"{ruta} existe pero no es un .xlsx valido/legible: {exc}") from exc

    try:
        try:
            ws_detalle = wb["Detalle"]
            ws_master = wb["Master"]
            fechas = _fechas_por_ref(ws_master)
            meta = _proyecto_proveedor_por_ref(ws_master)
            cols = mapear_encabezados(ws_detalle)
            col_ref = cols["N° Ref."]
            col_nombre = cols["Nombre Ítem"]
            col_desc = cols["Descripción"]
            col_precio = cols[cfg["col_precio_unitario"]]
            col_total_sin_iva = cols[cfg["col_total_sin_iva"]]
            col_total_con_iva = cols[cfg["col_total_con_iva"]]
            col_categoria = cols.get("Categoría Ítem")
        except KeyError as exc:
            raise ExcelNoDisponibleError(
                f"Estructura inesperada en {ruta}: falta hoja o columna {exc}"
            ) from exc

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

            precio = fila[col_precio - 1].value
            if excluido_motivo is None and (not isinstance(precio, (int, float))
                                             or isinstance(precio, bool)
                                             or not math.isfinite(precio)):
                # isfinite descarta NaN e infinito: son "numeros" para
                # isinstance pero envenenan cualquier promedio en silencio
                # (NaN no es igual ni mayor ni menor a nada).
                excluido_motivo = "precio_invalido"
            elif excluido_motivo is None and precio < 0:
                excluido_motivo = "precio_negativo"
            elif excluido_motivo is None and precio == 0:
                excluido_motivo = "precio_cero"

            proyecto, proveedor_tag = meta.get(n_ref, (None, None))
            items.append({
                "n_ref": n_ref,
                "nombre_item": fila[col_nombre - 1].value or "",
                "descripcion": fila[col_desc - 1].value or "",
                "categoria_item": fila[col_categoria - 1].value if col_categoria else None,
                "proyecto": proyecto,
                "proveedor_tag": proveedor_tag,
                "precio_unitario_sin_iva": precio,
                "total_sin_iva": fila[col_total_sin_iva - 1].value,
                "total_con_iva": fila[col_total_con_iva - 1].value,
                "fecha": fecha if excluido_motivo is None else None,
                "excluido_motivo": excluido_motivo,
            })
        return items
    finally:
        wb.close()


def normalizar_texto(texto):
    """Minusculas y sin tildes. Se conserva porque es la normalizacion que
    exponen el driver y los tests; la del buscador vive en busqueda.raiz y
    hace bastante mas (plural, sinonimos, palabras vacias)."""
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def buscar_items(items, texto_busqueda, indice=None, aplicar_medida=True):
    """Busqueda por relevancia de texto_busqueda contra todos los campos del
    item. Devuelve (coincidencias, sugerencias): coincidencias son los items
    (dicts sin modificar) ordenados de mas a menos relevante; sugerencias son
    nombres canonicos que escribir en su lugar cuando lo que se busco no
    aparecio. Items con excluido_motivo != None se ignoran siempre.

    La logica vive en busqueda.py -- la misma que usa el dashboard, para que
    la consola y la web nunca respondan distinto a la misma consulta. Hasta
    2026-09-15 esta funcion tenia su propio puntaje (difflib + "comparten una
    palabra de 4 letras"), que devolvia 1.0 para cualquier item que
    compartiera una palabra con la consulta: sobre el catalogo real, las 41
    valvulas empataban y el orden lo terminaba decidiendo el Excel.

    'indice' permite reutilizar un Indice ya construido entre varias
    consultas; sin el, se arma uno por llamada. 'aplicar_medida' se pasa tal
    cual a Indice.buscar (ver su docstring)."""
    indexables = [it for it in items if it.get("excluido_motivo") is None]
    if indice is None:
        indice = busqueda.Indice(indexables)
    resultados, sugerencias = indice.buscar(texto_busqueda, aplicar_medida=aplicar_medida)
    return [r["item"] for r in resultados], sugerencias


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
    try:
        return serie[0]["valor"]
    except (KeyError, TypeError) as exc:
        raise UFNoDisponibleError(f"Respuesta inesperada de mindicador.cl para {fecha}: {exc}") from exc


# Ultima UF "de hoy" que respondio mindicador.cl, para cuando no responde
# (2026-10-08: la corrida programada del 2026-10-05 perdio el tablero del
# Cotizador por un timeout). uf_cache.json no sirve de respaldo: solo guarda
# fechas de compras, la mas reciente con semanas de antiguedad. La variable
# de entorno la redirige; el conftest.py raiz la apunta a tmp_path en todos
# los tests, para que una UF simulada nunca quede como respaldo real.
RUTA_ULTIMA_UF = Path(__file__).resolve().parent / "uf_ultima.json"
VARIABLE_RUTA_ULTIMA_UF = "QUEMPIN_UF_ULTIMA"
# La UF cambia unas centesimas por dia: una de hasta 3 dias atras cambia los
# precios reajustados en menos de 0,1 %, y el tablero dice de que dia es.
DIAS_UF_RESPALDO = 3


def _ruta_ultima_uf():
    return Path(os.environ.get(VARIABLE_RUTA_ULTIMA_UF) or RUTA_ULTIMA_UF)


def _fecha_iso(fecha):
    return fecha.strftime("%Y-%m-%d")


def guardar_ultima_uf(fecha, valor):
    """Recuerda la UF de 'hoy' recien obtenida. Nunca frena a quien la pidio."""
    ruta = _ruta_ultima_uf()
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    try:
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump({"fecha": _fecha_iso(fecha), "valor": valor}, f, ensure_ascii=False)
        os.replace(temporal, ruta)
    except OSError:
        pass


def ultima_uf_guardada(fecha, dias=DIAS_UF_RESPALDO):
    """(fecha_iso, valor) de la ultima UF guardada si es de 'fecha' o de hasta
    'dias' antes; None si no hay o es mas antigua (o posterior a 'fecha')."""
    try:
        with open(_ruta_ultima_uf(), "r", encoding="utf-8") as f:
            guardada = json.load(f)
        dia = datetime.strptime(guardada["fecha"], "%Y-%m-%d").date()
        valor = float(guardada["valor"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    hoy = fecha.date() if isinstance(fecha, datetime) else fecha
    if not 0 <= (hoy - dia).days <= dias:
        return None
    return guardada["fecha"], valor


def obtener_uf_hoy(fecha, uf_manual=None, fuente_manual=None):
    """UF de 'hoy': intenta mindicador.cl primero (consultar_uf_api) y la
    recuerda. Si falla, usa en este orden el valor manual que se haya pasado
    (buscado por el agente en una fuente confiable) o la ultima UF que si
    respondio, de hasta DIAS_UF_RESPALDO dias atras, diciendo de que dia es.
    Devuelve (valor, fuente). Sin ninguno de los dos, relanza
    UFNoDisponibleError: nunca se inventa un valor de UF, solo se reutiliza
    uno que mindicador.cl ya entrego."""
    try:
        valor = consultar_uf_api(fecha)
    except UFNoDisponibleError:
        if uf_manual is not None:
            return uf_manual, fuente_manual or "fuente manual (sin especificar)"
        respaldo = ultima_uf_guardada(fecha)
        if respaldo is None:
            raise
        dia, valor = respaldo
        return valor, f"UF del {dia[8:10]}-{dia[5:7]}-{dia[:4]}, la última disponible: mindicador.cl no respondió"
    guardar_ultima_uf(fecha, valor)
    return valor, "mindicador.cl"


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


def tasa_iva_real(total_sin_iva, total_con_iva):
    """Tasa real de IVA del documento (Total con IVA / Total sin IVA de esa
    fila de Detalle) -- igual que hace Centro de Costos, nunca asume 19%
    fijo, para que tambien sea correcta en documentos exentos o de Zona
    Franca. Si cualquiera de los dos totales no es un numero utilizable, o
    el total sin IVA es 0 (ej. items que figuran en $0 en la factura),
    devuelve 1.0 (sin IVA adicional) como respaldo seguro."""
    if not isinstance(total_sin_iva, (int, float)) or not total_sin_iva:
        return 1.0
    if not isinstance(total_con_iva, (int, float)):
        return 1.0
    return total_con_iva / total_sin_iva


def reajustar_item(item, uf_hoy, cache_uf):
    """Reajusta un item de cargar_items_detalle a la UF de hoy. Devuelve el
    dict de compra reajustada, o None si no se pudo obtener la UF de la
    fecha de compra (UFNoDisponibleError) -- el llamador decide como contar
    ese caso (ver consultar_item y reajustar_todos). 'fecha' queda en ISO
    'YYYY-MM-DD' a proposito (no DD-MM-AAAA): el visualizador web filtra/
    compara este campo como string (item.fecha < desde en template.html),
    lo que solo funciona en orden cronologico correcto en formato ISO;
    cada consumidor (driver.py, visualizador) formatea a DD-MM-AAAA solo
    para mostrarlo, nunca se reformatea en el origen."""
    try:
        uf_compra = obtener_valor_uf(item["fecha"], cache_uf)
    except UFNoDisponibleError:
        return None
    precio_reajustado = calcular_precio_reajustado(item["precio_unitario_sin_iva"], uf_compra, uf_hoy)
    tasa_iva = tasa_iva_real(item.get("total_sin_iva"), item.get("total_con_iva"))
    return {
        "n_ref": item["n_ref"],
        "fecha": item["fecha"].strftime("%Y-%m-%d"),
        "precio_original_sin_iva": item["precio_unitario_sin_iva"],
        "precio_reajustado_hoy": precio_reajustado,
        "precio_reajustado_hoy_con_iva": round(precio_reajustado * tasa_iva),
    }


def agregar_taxonomia(compra):
    """Agrega a una compra ya armada su clasificacion (categoria,
    subcategoria, familia, material, medida y hoja).

    La hoja es la unidad de comparacion de precios: dos compras solo se
    promedian entre si si comparten hoja, es decir misma familia, mismo
    material y misma medida -- "una caneria de cobre de 1/2 no es lo mismo
    que una de 2" (pedido explicito del usuario). Se aplica en los dos
    caminos (reajustar_todos para el dashboard, consultar_item para la
    consulta puntual) para que ambos clasifiquen identico."""
    clasif = taxonomia.clasificar(compra.get("nombre_item"), compra.get("descripcion"))
    for campo in ("categoria", "subcategoria", "familia", "material", "medida", "medida_texto",
                  "medida_mm", "cotizable", "secundaria", "requiere_medida",
                  # atributos (2026-09-22): el tipo y la familia de producto,
                  # el material con su familia y su grado, el sistema de
                  # tuberia, la terminacion, las dimensiones con su rol y las
                  # especificaciones tecnicas. El buscador los indexa como
                  # campos separados y el dashboard arma con ellos los
                  # filtros de cada familia.
                  "tipo", "familia_producto", "material_base", "material_grado", "sistema",
                  "aplicacion", "terminacion", "color", "dimensiones", "especificaciones",
                  "esquema", "numeros", "medidas_equivalentes", "confianza", "revisar",
                  "motivos_revision", "nombre_normalizado"):
        compra[campo] = clasif[campo]
    compra["hoja"] = taxonomia.clave_hoja(clasif)
    # La misma hoja escrita para leerla: es la que ve el usuario en la ficha
    # y en el filtro. La de arriba es la que se indexa y agrupa.
    compra["hoja_texto"] = taxonomia.clave_hoja(clasif, presentable=True)
    # La clave de agrupacion va aparte del texto que se muestra: el mismo
    # producto puede venir escrito distinto ("Estanque R24 lts rojo 8 bar" y
    # "Estanque R 24 LTS rojo 8 BAR"), y sin normalizar abriria dos hojas.
    compra["hoja_clave"] = taxonomia.clave_agrupacion(clasif)
    return compra


def compactar_atributos(compras):
    """Deja cada compra con sus atributos en la forma que consume el
    dashboard y devuelve la tabla de facetas por familia.

    La ficha completa (dimensiones con su rol, especificaciones, motivos de
    revision) es util en Python pero pesada dentro del HTML publicado, que
    viaja entera al navegador. Aca se aplana a `atr` -- {clave: texto} listo
    para mostrar en un filtro -- y se sueltan los campos que el navegador no
    usa (el buscador ya recibe sus terminos en _bt/_bm).

    Devuelve {familia: [[clave, etiqueta], ...]} con los filtros que tienen
    sentido para cada familia: "Schedule" no existe para una plancha ni
    "Ancho" para una valvula (pedido del usuario, 2026-09-22)."""
    from catalogo_atributos import FACETAS_POR_DEFECTO, FACETAS_POR_FAMILIA
    usadas = {}
    for compra in compras:
        dims = compra.get("dimensiones") or {}
        specs = compra.get("especificaciones") or {}
        familia = compra.get("familia_producto") or ""
        atr = {}
        for clave, etiqueta in FACETAS_POR_FAMILIA.get(familia, FACETAS_POR_DEFECTO):
            if clave.startswith("dim:"):
                d = dims.get(clave[4:])
                valor = dimensiones.texto_dimension(clave[4:], d) if d else None
            elif clave.startswith("spec:"):
                valor = specs.get(clave[5:])
            elif clave == "tipo":
                valor = compra.get("tipo")
            elif clave == "terminacion":
                valor = ", ".join(compra.get("terminacion") or []) or None
            else:
                valor = compra.get(clave)
            if valor:
                atr[clave] = str(valor)
        compra["atr"] = atr
        if familia:
            usadas[familia] = [list(f) for f in
                               FACETAS_POR_FAMILIA.get(familia, FACETAS_POR_DEFECTO)]
        for campo in ("dimensiones", "especificaciones", "esquema", "numeros",
                      "medidas_equivalentes", "motivos_revision", "nombre_normalizado",
                      "materiales_secundarios"):
            compra.pop(campo, None)
        # Las escrituras legibles viajan solo cuando dicen algo distinto de
        # la canonica: en la mayoria del catalogo la medida esta en pulgadas
        # y las dos cadenas son identicas. El template ya cae a la canonica
        # cuando no vienen (hoja_texto || hoja).
        for legible, canonico in (("hoja_texto", "hoja"), ("medida_texto", "medida")):
            if compra.get(legible) == compra.get(canonico):
                compra.pop(legible, None)
    return usadas


def agrupar_por_hoja(compras):
    """Agrupa compras por hoja y calcula el precio de mercado de cada una.

    Devuelve una lista de grupos ordenada por cantidad de compras. Un grupo
    con una sola compra no tiene con que compararse: se informa igual, pero
    su 'promedio' es esa unica compra (el consumidor decide como mostrarlo).
    Los grupos no cotizables (peajes, combustible, alimentacion) se marcan
    con cotizable=False: su precio unitario promedio no significa nada
    porque cada compra es de una cantidad distinta."""
    grupos = {}
    for compra in compras:
        clave = (compra.get("hoja_clave") or compra.get("hoja")
                 or compra.get("nombre_item") or "sin nombre")
        grupo = grupos.setdefault(clave, {
            # El nombre del grupo se MUESTRA (consola, tablero, cotizacion),
            # asi que va en la escritura legible; la clave de agrupacion es
            # la de arriba y no cambia.
            "hoja": (compra.get("hoja_texto") or compra.get("hoja")
                     or compra.get("nombre_item") or "Sin nombre"),
            "hoja_clave": clave,
            "categoria": compra.get("categoria"),
            "subcategoria": compra.get("subcategoria"),
            "familia": compra.get("familia"),
            "material": compra.get("material"),
            "medida": compra.get("medida_texto") or compra.get("medida"),
            "cotizable": compra.get("cotizable", True),
            "secundaria": compra.get("secundaria", False),
            "compras": [],
        })
        grupo["compras"].append(compra)

    salida = []
    for grupo in grupos.values():
        sin_iva = [c["precio_reajustado_hoy"] for c in grupo["compras"]]
        con_iva = [c["precio_reajustado_hoy_con_iva"] for c in grupo["compras"]]
        grupo["n_compras"] = len(sin_iva)
        grupo["promedio_reajustado"] = round(sum(sin_iva) / len(sin_iva))
        grupo["promedio_reajustado_con_iva"] = round(sum(con_iva) / len(con_iva))
        grupo["rango_minimo"] = min(sin_iva)
        grupo["rango_maximo"] = max(sin_iva)
        # dispersion: cuantas veces el mas caro al mas barato. Alta dispersion
        # en una hoja cotizable es senal de que la hoja todavia mezcla
        # productos distintos (o presentaciones distintas: unidad vs pack).
        grupo["dispersion"] = round(grupo["rango_maximo"] / grupo["rango_minimo"], 1) if grupo["rango_minimo"] else None
        salida.append(grupo)
    salida.sort(key=lambda g: (-g["n_compras"], g["hoja"]))
    return salida


def reajustar_todos(items, uf_hoy, cache_uf=None):
    """Reajusta TODOS los items indexables (excluido_motivo is None) a la
    UF de hoy, sin filtrar por texto de busqueda -- lo usa el visualizador
    web, que necesita el indice completo, no solo los resultados de una
    consulta puntual. Devuelve (reajustados, sin_uf_count); cada dict de
    reajustados trae ademas nombre_item/descripcion/categoria_item/
    proyecto/proveedor_tag del item original, para no tener que volver a
    cruzarlos despues.

    Si cache_uf es None, carga y persiste el cache de disco el mismo que
    usa consultar_item; si se pasa un dict ya cargado (tests, o un
    llamador que quiere controlar el I/O), se muta in-place y no se
    persiste aqui -- mismo contrato que obtener_valor_uf."""
    propio_cache = cache_uf is None
    if propio_cache:
        cache_uf = cargar_cache_uf()

    reajustados = []
    sin_uf_count = 0
    for item in items:
        if item["excluido_motivo"] is not None:
            continue
        compra = reajustar_item(item, uf_hoy, cache_uf)
        if compra is None:
            sin_uf_count += 1
            continue
        compra["nombre_item"] = item["nombre_item"]
        compra["descripcion"] = item["descripcion"]
        compra["categoria_item"] = item.get("categoria_item")
        compra["proyecto"] = item.get("proyecto")
        compra["proveedor_tag"] = item.get("proveedor_tag")
        reajustados.append(agregar_taxonomia(compra))

    unificar_escritura(reajustados)
    if propio_cache:
        guardar_cache_uf(cache_uf)
    return reajustados, sin_uf_count


def armar_compra_sin_reajuste(item):
    """Version 'PE' de reajustar_item: sin UF ni reajuste por indice --
    decision explicita del spec de expansion a Peru (no existe hoy una
    fuente publica equivalente a la UF chilena, ver docs/specs/
    2026-08-21-peru-expansion-design.md decision 5). El precio historico se
    muestra tal cual (factor implicito 1) -- mismo shape de salida que
    reajustar_item para que consultar_item/build_visualizador.py/
    template.html no necesiten dos formatos distintos. A diferencia de
    reajustar_item, nunca devuelve None: no hay llamada de red que pueda
    fallar."""
    tasa_iva = tasa_iva_real(item.get("total_sin_iva"), item.get("total_con_iva"))
    precio = item["precio_unitario_sin_iva"]
    return {
        "n_ref": item["n_ref"],
        "fecha": item["fecha"].strftime("%Y-%m-%d"),
        "precio_original_sin_iva": precio,
        "precio_reajustado_hoy": precio,
        "precio_reajustado_hoy_con_iva": round(precio * tasa_iva),
    }


def unificar_escritura(compras):
    """Una sola escritura por nombre en todo el catalogo.

    El Excel es la fuente y este modulo es de solo lectura, asi que el mismo
    proveedor llega escrito de varias formas ("Quilpue" con y sin tilde) y la
    misma marca tambien ("ANWO" y "Anwo" en dos radiadores seguidos). Verlo
    dos veces en un filtro hace dudar de si son dos cosas distintas.

    Es un paso sobre el catalogo COMPLETO y no por compra porque la forma
    correcta se decide comparando todas las escrituras entre si (ver
    presentacion.unificar_nombres / unificar_ortografia).

    Solo toca las etiquetas que se muestran -- la hoja, el proveedor, el
    proyecto. El nombre y la descripcion originales del documento quedan
    intactos: son el registro de lo que decia la factura.

    Devuelve cuantas escrituras se unificaron, para poder reportarlo."""
    ortografia = presentacion.unificar_ortografia(
        [c.get("hoja_texto") for c in compras]
        + [c.get("nombre_item") for c in compras]
        + [c.get("descripcion") for c in compras])
    proveedores = presentacion.unificar_nombres([c.get("proveedor_tag") for c in compras])
    proyectos = presentacion.unificar_nombres([c.get("proyecto") for c in compras])

    for compra in compras:
        if compra.get("hoja_texto"):
            compra["hoja_texto"] = presentacion.aplicar_ortografia(
                compra["hoja_texto"], ortografia)
        for campo, mapa in (("proveedor_tag", proveedores), ("proyecto", proyectos)):
            if compra.get(campo):
                compra[campo] = mapa.get(compra[campo], compra[campo])

    return {"palabras": len(ortografia),
            "proveedores": sum(1 for k, v in proveedores.items() if k != v),
            "proyectos": sum(1 for k, v in proyectos.items() if k != v)}


def armar_indice_completo_sin_reajuste(items):
    """Version 'PE' de reajustar_todos: aplica armar_compra_sin_reajuste a
    TODOS los items indexables (excluido_motivo is None), agregando la
    misma metadata de producto. sin_uf_count siempre 0 -- mismo contrato de
    retorno (lista, sin_uf_count) que reajustar_todos, para que
    build_visualizador.py de Peru pueda llamar a cualquiera de las dos sin
    ramificar el resto de su logica."""
    resultado = []
    for item in items:
        if item["excluido_motivo"] is not None:
            continue
        compra = armar_compra_sin_reajuste(item)
        compra["nombre_item"] = item["nombre_item"]
        compra["descripcion"] = item["descripcion"]
        compra["categoria_item"] = item.get("categoria_item")
        compra["proyecto"] = item.get("proyecto")
        compra["proveedor_tag"] = item.get("proveedor_tag")
        resultado.append(agregar_taxonomia(compra))
    unificar_escritura(resultado)
    return resultado, 0


def consultar_item(texto_busqueda, ruta_excel=None, fecha_hoy=None, uf_manual=None, fuente_manual=None, pais="CL"):
    """Orquesta una consulta completa: carga Detalle, busca por texto,
    reajusta cada compra encontrada por UF, y agrega promedio/rango.

    Si la UF de una compra puntual no esta disponible (sin internet, o
    mindicador.cl sin dato para esa fecha), esa compra se excluye del
    resultado (contada en "sin_uf_count") sin abortar la consulta completa
    -- solo si NINGUNA compra pudo reajustarse el resultado queda como "no
    encontrado". La UF de "hoy" (unica para toda la consulta) se pide via
    obtener_uf_hoy: mindicador.cl primero, y si falla y se paso un valor
    manual (buscado en una fuente confiable), lo usa en su lugar -- sin
    valor manual, sigue abortando la consulta completa (UFNoDisponibleError)
    porque sin ella no se puede reajustar nada.

    fecha_hoy es inyectable para tests (default: date.today()).

    'pais'="PE" salta el reajuste por UF por completo (ver
    armar_compra_sin_reajuste) -- nunca llama a mindicador.cl ni al cache
    de disco para ese pais.

    Agrupacion por hoja (2026-09-08): cada compra vuelve clasificada (ver
    agregar_taxonomia) y el resultado trae ademas "grupos", una entrada por
    hoja (familia+material+medida) con su propio promedio y rango. El
    promedio global sigue existiendo por compatibilidad, pero el que
    responde la pregunta real es el del grupo: promediar un codo de 1/2 con
    uno de 2 no estima el costo de ninguno de los dos.

    Si el texto buscado incluye una medida ("codo bronce 1/2"), solo entran
    al resultado las compras de esa misma medida; las demas se cuentan en
    "descartadas_por_medida" y la medida detectada queda en
    "medida_consultada". Sin medida en la consulta no se filtra nada."""
    hoy = fecha_hoy or date.today()
    items = cargar_items_detalle(ruta_excel, pais=pais)
    excluidos_count = sum(1 for it in items if it["excluido_motivo"] is not None)

    # Las medidas equivalentes de la consulta: 2", 2 pulgadas, 2 plg, Ø2" y
    # DN50 son la misma, y filtrar por cualquiera de ellas tiene que dar el
    # mismo resultado. Antes se usaba taxonomia.medida_canonica, que lee una
    # sola escritura y no conoce la equivalencia DN.
    medidas_consultadas = busqueda.medidas_de_consulta(texto_busqueda)
    medida_consultada = sorted(medidas_consultadas)[0] if medidas_consultadas else None

    # aplicar_medida=False: aca la medida NO ordena, filtra. Se quieren
    # todas las compras de la familia para poder contar cuantas quedaron
    # fuera por ser de otro calibre (descartadas_por_medida).
    coincidencias, sugerencias = buscar_items(items, texto_busqueda, aplicar_medida=False)
    if not coincidencias:
        return {
            "encontrado": False,
            "compras": [],
            "grupos": [],
            "promedio_reajustado": None,
            "promedio_reajustado_con_iva": None,
            "rango_minimo": None,
            "rango_maximo": None,
            "excluidos_count": excluidos_count,
            "sugerencias": sugerencias,
            "sin_uf_count": 0,
            "uf_fuente": None,
            "medida_consultada": medida_consultada,
            "descartadas_por_medida": 0,
        }

    if pais == "PE":
        pares = [(armar_compra_sin_reajuste(item), item) for item in coincidencias]
        sin_uf_count = 0
        uf_fuente = None
    else:
        uf_hoy, uf_fuente = obtener_uf_hoy(hoy, uf_manual=uf_manual, fuente_manual=fuente_manual)
        cache_uf = cargar_cache_uf()
        pares = []
        sin_uf_count = 0
        for item in coincidencias:
            compra = reajustar_item(item, uf_hoy, cache_uf)
            if compra is None:
                sin_uf_count += 1
                continue
            pares.append((compra, item))
        guardar_cache_uf(cache_uf)

    # Cada compra se lleva su clasificacion (el item original tiene el
    # nombre/descripcion; la compra reajustada no los copiaba). La compra va
    # emparejada con SU item, no por posicion: cuando una compra se cae por
    # no tener UF, un zip(compras, coincidencias) corre el resto una casilla
    # y a partir de ahi cada compra queda con el nombre de otra.
    compras = []
    for compra, item in pares:
        compra["nombre_item"] = item["nombre_item"]
        compra["descripcion"] = item["descripcion"]
        agregar_taxonomia(compra)
        compras.append(compra)

    descartadas_por_medida = 0
    if medidas_consultadas:
        del_tamano_pedido = [c for c in compras if c.get("medida") in medidas_consultadas]
        descartadas_por_medida = len(compras) - len(del_tamano_pedido)
        compras = del_tamano_pedido

    if not compras:
        return {
            "encontrado": False,
            "compras": [],
            "grupos": [],
            "promedio_reajustado": None,
            "promedio_reajustado_con_iva": None,
            "rango_minimo": None,
            "rango_maximo": None,
            "excluidos_count": excluidos_count,
            "sugerencias": [],
            "sin_uf_count": sin_uf_count,
            "uf_fuente": uf_fuente,
            "medida_consultada": medida_consultada,
            "descartadas_por_medida": descartadas_por_medida,
        }

    reajustados = [c["precio_reajustado_hoy"] for c in compras]
    reajustados_con_iva = [c["precio_reajustado_hoy_con_iva"] for c in compras]
    return {
        "encontrado": True,
        "compras": compras,
        "grupos": agrupar_por_hoja(compras),
        "promedio_reajustado": round(sum(reajustados) / len(reajustados)),
        "promedio_reajustado_con_iva": round(sum(reajustados_con_iva) / len(reajustados_con_iva)),
        "rango_minimo": min(reajustados),
        "rango_maximo": max(reajustados),
        "excluidos_count": excluidos_count,
        "sugerencias": [],
        "sin_uf_count": sin_uf_count,
        "uf_fuente": uf_fuente,
        "medida_consultada": medida_consultada,
        "descartadas_por_medida": descartadas_por_medida,
    }
