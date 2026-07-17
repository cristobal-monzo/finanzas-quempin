# -*- coding: utf-8 -*-
"""
auditor_centro_costos.py — Registro incremental de facturas/boletas para QUEMPIN SpA.

Estructura "rica" (reconstruida el 2026-07-16 a partir de Centro de Costos.xlsx,
ver reconciliacion_archivos.json para el detalle):
- Detalle: hoja de edicion, una fila por ITEM de linea de cada documento.
- Master: una fila por DOCUMENTO (N Ref), con formulas SUMIF hacia Detalle.
- Una hoja de solo lectura por proyecto, 100% formulas hacia Master.

La hoja _Claude (registro interno de una version anterior del pipeline, ya
perdida) se deja intacta si existe, pero esta version no escribe en ella: no
lo necesita porque nunca vuelve a tocar una fila de datos ya creada (ver
regla siguiente), asi que no hay nada que la corrija a mano.

Reglas:
- Las filas de datos ya escritas (items en Detalle, documentos en Master) NUNCA se
  vuelven a tocar una vez creadas -- son historial editable a mano por el usuario.
- Las filas de pie (TOTAL GENERAL + leyenda) y las hojas de proyecto SI se regeneran
  en cada corrida, porque son 100% derivadas.
- Backup siempre antes de escribir.
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter, column_index_from_string

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────

RAIZ = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ.parent
RAIZ_DOCS = RAIZ_MODULO / "Documentos Centro de Costos"
RUTA_EXCEL = RAIZ_MODULO / "Excel" / "Centro de Costos.xlsx"
RUTA_JSON = RAIZ / "datos_extraidos.json"
RUTA_RECONCILIACION = RAIZ / "reconciliacion_archivos.json"
RUTA_BACKUPS = RAIZ_MODULO / "Excel" / "Respaldos"

PREFIJOS_PROYECTO = {
    "UMAG": "UMAG",
    "Cesfam Limache": "CFLI",
    "Gastos Generales": "GGEN",
}

PALETA = [
    "FCE4D6", "DDEBF7", "E2EFDA", "FFF2CC", "EAD1DC", "D9E1F2",
    "FBE5D6", "D6DCE4", "E4DFEC", "FDE9D9", "DAEEF3", "F2DCDB",
]

# Tag corto (mas facil de reconocer visualmente) por razon social completa del
# proveedor. La razon social completa siempre se conserva en la columna oculta
# "Proveedor (Razon Social)" -- este diccionario solo controla que se MUESTRA
# en la columna "Proveedor". Curado a mano para los proveedores ya conocidos;
# para uno nuevo que no este aqui, generar_tag_proveedor() aplica una
# heuristica automatica (ver esa funcion) -- si el resultado no queda
# representativo, agregar la entrada correcta aqui.
TAGS_PROVEEDOR_CURADOS = {
    "Comercial Beckman SpA": "Beckman",
    "Easy Retail S.A.": "Easy",
    "Air Express Cargo SpA": "Air Express",
    "Sociedad Comercial Patagonica SpA": "Patagónica",
    "Soc. Com. El Estuche Ltda.": "El Estuche",
    "Comercial e Inversiones Crosur Ltda.": "Crosur",
    "Esteban Guic y Cia. Ltda. (RECASUR)": "RECASUR",
    "Ferreteria El Aguila SpA": "El Águila",
    "Sebastian Prado y Compania Ltda. (BOLT)": "BOLT",
    "Empresas Tur Bus": "Tur Bus",
    "Estaciones de Servicios Fandos Ltda. (Shell Ruta 68)": "Shell",
    "ACO S.A.": "ACO",
    "Danus Conexiones SpA": "Danus",
    "Undurraga Tecnica y Comercial S.A. (UTECSA)": "UTECSA",
    "LATAM Airlines Group S.A.": "LATAM",
    "Ortuzar SpA (Dezar Rent a Car)": "Dezar",
    "Engas Chile SpA": "Engas",
    "Antonio Ruiz Ch. e Hijos Ltda.": "Antonio Ruiz",
    "Comercial Anwo S.A.": "Anwo",
}

_SUFIJOS_LEGALES_RE = re.compile(
    r"\b(S\.?A\.?|SpA|Ltda\.?|E\.?I\.?R\.?L\.?|Group)\b\.?", re.IGNORECASE
)
_PALABRAS_GENERICAS_TAG = {
    "comercial", "sociedad", "soc", "com", "empresas", "compañía", "compania",
    "cia", "inversiones", "e", "y", "de", "del", "la", "el", "los", "las",
    "servicios", "grupo", "group",
}


def generar_tag_proveedor(razon_social):
    """Deriva un tag corto y representativo de una razon social completa.
    1) Si esta en TAGS_PROVEEDOR_CURADOS, se usa ese (fuente de verdad manual).
    2) Si el nombre trae una marca entre parentesis (ej. "... (Shell Ruta 68)"),
       se usa la primera palabra de ese parentesis (la marca, sin el
       descriptor que suele acompañarla).
    3) Si no, se limpia la razon social de sufijos legales (SpA, S.A., Ltda.,
       etc.) y palabras genericas (Comercial, Sociedad, Inversiones, ...) y se
       toman las 1-2 palabras significativas que queden.
    Es un fallback heuristico para proveedores nuevos -- si el resultado no es
    representativo, agregar la entrada correcta a TAGS_PROVEEDOR_CURADOS."""
    if razon_social in TAGS_PROVEEDOR_CURADOS:
        return TAGS_PROVEEDOR_CURADOS[razon_social]

    m = re.search(r"\(([^)]+)\)", razon_social)
    if m:
        contenido = m.group(1).strip()
        if contenido:
            return contenido.split()[0]

    base = _SUFIJOS_LEGALES_RE.sub("", razon_social)
    palabras = [
        p for p in re.split(r"\s+", base.strip(" .,"))
        if p and p.strip(".,").lower() not in _PALABRAS_GENERICAS_TAG
    ]
    tag = " ".join(palabras[:2]).strip(" .,")
    return tag or razon_social

EXTENSIONES_VALIDAS = {".png", ".jpg", ".jpeg", ".heic", ".pdf"}
EXTENSIONES_IGNORAR = {".html", ".txt", ".ini", ".tmp"}

ENCABEZADOS_MASTER = [
    "N° Ref.", "Proyecto", "Tipo de Proyecto", "Fecha", "N° Documento",
    "Tipo Documento", "Proveedor", "Proveedor (Razón Social)", "Categoría",
    "Resumen Ítems", "Total sin IVA (CLP)", "IVA 19% (CLP)",
    "Total con IVA (CLP)", "Estado", "Archivo origen", "Fecha modificación",
]
ENCABEZADOS_DETALLE = [
    "N° Ref.", "Proyecto", "Tipo de Proyecto", "N° Documento", "Nombre Ítem",
    "Descripción", "Categoría Ítem", "Cantidad", "P. Unitario sin IVA",
    "Total sin IVA (CLP)",
]
ENCABEZADOS_PROYECTO = [
    "N° Ref.", "Proyecto", "Tipo de Proyecto", "Fecha", "N° Documento",
    "Tipo Documento", "Proveedor", "Proveedor (Razón Social)", "Categoría",
    "Resumen Ítems", "Total sin IVA (CLP)", "Total con IVA (CLP)", "Estado",
]

# Columna (1-indexada) de "Proveedor (Razón Social)" en Master y en las hojas
# de proyecto -- se usa para ocultarla y para el mapeo de columnas al migrar.
COL_PROVEEDOR_TAG_MASTER = 7
COL_PROVEEDOR_RAZON_SOCIAL_MASTER = 8

LEYENDA_MASTER = [
    "Cursiva = celda editable a mano",
    "Rojo = valor que requiere revisión (pasa el cursor por la celda para ver el motivo)",
    "Azul marino = valor corregido a mano por ti (Claude lo respeta y no lo sobreescribe)",
    "Fondo de color = proyecto (se pinta solo según la columna 'Proyecto'; si la cambias, "
    "el color se actualiza) · la foto de cada documento lleva su N° como nombre de archivo",
    "⚠️ 'Total sin IVA' y 'Total con IVA' se calculan desde Detalle. 'Archivo origen' y "
    "'Fecha modificación' son el registro de lo ya procesado: no editar.",
]
LEYENDA_DETALLE = [
    "Cursiva = celda editable a mano",
    "Rojo = valor que requiere revisión (pasa el cursor por la celda para ver el motivo)",
    "Azul marino = valor corregido a mano por ti (Claude lo respeta y no lo sobreescribe)",
    "Fondo de color = proyecto (se pinta solo según la columna 'Proyecto'; si la cambias, "
    "el color se actualiza) · la foto de cada documento lleva su N° como nombre de archivo",
    "✔ Ésta es la hoja de edición: Master y las hojas de proyecto se calculan desde aquí.",
]
LEYENDA_PROYECTO = [
    "Cursiva = celda editable a mano",
    "Rojo = valor que requiere revisión (pasa el cursor por la celda para ver el motivo)",
    "Azul marino = valor corregido a mano por ti (Claude lo respeta y no lo sobreescribe)",
    "Fondo de color = proyecto (se pinta solo según la columna 'Proyecto'; si la cambias, "
    "el color se actualiza) · la foto de cada documento lleva su N° como nombre de archivo",
    "⚠️ Vista de sólo lectura: ninguna celda es editable. Editar los ítems en la hoja Detalle.",
]

PATRON_NREF = re.compile(r"^[A-Za-zÁÉÍÓÚÑ]+-\d+$")

NAVY = "1F4E79"
NAVY_OSCURO = "1F3864"
ROJO = "C00000"
BLANCO = "FFFFFF"
NEGRO = "000000"

HEADER_FILL = PatternFill("solid", fgColor=NAVY)
HEADER_FONT = Font(name="Calibri", bold=True, size=11, color=BLANCO)
NORMAL_FONT = Font(name="Calibri", size=11, color=NEGRO)
ROJO_FONT = Font(name="Calibri", size=11, color=ROJO)
MONEY_FORMAT = '"$"#,##0'
DATE_FORMAT = "DD/MM/YYYY"
THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)


# ── UTILIDADES DE FORMATO ────────────────────────────────────────────────────

def formato_encabezado(ws, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=1, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER


def pintar_fila(ws, row, ncols, hex_color):
    fill = PatternFill("solid", fgColor=hex_color)
    for c in range(1, ncols + 1):
        ws.cell(row=row, column=c).fill = fill


def ajustar_anchos(ws):
    """Autoajusta el ancho SOLO de columnas que todavia no tienen un ancho fijado.
    Si la columna ya tiene width (fijado por el script en una corrida anterior, o a
    mano por el usuario en Excel), se respeta y no se vuelve a tocar -- asi el
    usuario puede angostar/ensanchar columnas en Excel sin que el proximo run se lo
    pise."""
    for col in ws.columns:
        column_letter = get_column_letter(col[0].column)
        dim = ws.column_dimensions[column_letter]
        if dim.width:
            continue
        max_length = 0
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except TypeError:
                pass
        dim.width = min(max(max_length + 2, 10), 40)


def escribir_leyenda(ws, fila, textos, ncols):
    colores = [NAVY, ROJO, NAVY_OSCURO, NAVY, NAVY]
    for i, texto in enumerate(textos):
        cell = ws.cell(row=fila + i, column=1, value=texto)
        cell.font = Font(name="Calibri", size=9, italic=(i == 0), color=colores[i % len(colores)])
    return fila + len(textos)


# ── BACKUP ───────────────────────────────────────────────────────────────────

def hacer_backup(ruta_excel, ruta_backups=RUTA_BACKUPS):
    if not ruta_excel.exists():
        print(f"[WARN] El archivo {ruta_excel} no existe, se creara desde cero.")
        return None
    ruta_backups.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now().strftime("%Y-%m-%d %H%M")
    ruta_backup = ruta_backups / f"Centro de Costos - backup {ahora}.xlsx"
    shutil.copy2(str(ruta_excel), str(ruta_backup))
    print(f"[OK] Backup creado: Respaldos/{ruta_backup.name}")
    return ruta_backup


# ── LECTURA DE ESTADO EXISTENTE ─────────────────────────────────────────────

def ultima_fila_datos(ws):
    """Ultima fila (desde la 2) cuya columna A calza con el patron N Ref (PROYECTO-NNN)."""
    fila = 1
    r = 2
    while True:
        v = ws.cell(row=r, column=1).value
        if isinstance(v, str) and PATRON_NREF.match(v):
            fila = r
            r += 1
        else:
            break
    return fila


def leer_master(ws_master):
    """
    Devuelve:
    - filas: lista de dicts por documento ya registrado (fila, n_ref, proyecto, ...)
    - max_seq: {prefijo: numero_max_usado}
    - docs_registrados: set de N Documento (tal cual, mas version sin ceros a la izquierda)
    """
    filas = []
    max_seq = {}
    docs_registrados = set()

    ultima = ultima_fila_datos(ws_master)
    for r in range(2, ultima + 1):
        n_ref = ws_master.cell(row=r, column=1).value
        if not isinstance(n_ref, str) or not PATRON_NREF.match(n_ref):
            continue
        prefijo, seq = n_ref.rsplit("-", 1)
        max_seq[prefijo] = max(max_seq.get(prefijo, 0), int(seq))

        proyecto = ws_master.cell(row=r, column=2).value
        archivo_origen = ws_master.cell(row=r, column=15).value
        n_doc = ws_master.cell(row=r, column=5).value
        if n_doc:
            docs_registrados.add(str(n_doc))
            docs_registrados.add(str(n_doc).lstrip("0") or "0")

        filas.append({
            "fila": r, "n_ref": n_ref, "proyecto": proyecto,
            "archivo_origen": archivo_origen,
            "proveedor_tag": ws_master.cell(row=r, column=7).value,
            "fecha": ws_master.cell(row=r, column=4).value,
        })

    return filas, max_seq, docs_registrados


def cargar_reconciliacion():
    if not RUTA_RECONCILIACION.exists():
        return {}
    with open(RUTA_RECONCILIACION, "r", encoding="utf-8") as f:
        return json.load(f).get("mapeo", {})


# ── MIGRACIÓN: COLUMNA "PROVEEDOR (RAZÓN SOCIAL)" (2026-07-16) ─────────────

def _desplazar_rango_columna(rango_str, punto_insercion):
    """Desplaza en +1 cualquier letra de columna >= punto_insercion dentro de
    un rango tipo 'H2:H225'. Se usa para corregir validaciones de datos y
    formato condicional despues de insertar una columna con ws.insert_cols
    (openpyxl no ajusta esos rangos solo -- ver "Formato Centro de Costos.md" #8/#9/#14)."""
    def desplazar_letra(letra):
        idx = column_index_from_string(letra)
        return get_column_letter(idx + 1) if idx >= punto_insercion else letra

    m = re.match(r"^([A-Z]+)(\d+):([A-Z]+)(\d+)$", rango_str)
    if not m:
        return rango_str
    c1, r1, c2, r2 = m.groups()
    return f"{desplazar_letra(c1)}{r1}:{desplazar_letra(c2)}{r2}"


def _migrar_rangos_columna(ws, punto_insercion):
    for dv in ws.data_validations.dataValidation:
        dv.sqref = " ".join(
            _desplazar_rango_columna(p, punto_insercion) for p in str(dv.sqref).split()
        )

    # ConditionalFormattingList indexa sus reglas en un dict cuya clave es el
    # propio objeto ConditionalFormatting, con hash derivado de su sqref --
    # mutar cf.sqref en el lugar corrompe ese dict (el hash cambia pero la
    # entrada sigue en el bucket viejo). Hay que reconstruir el dict interno
    # con objetos ConditionalFormatting nuevos en vez de mutar los existentes.
    from openpyxl.formatting.formatting import ConditionalFormatting
    from collections import OrderedDict

    cf_list = ws.conditional_formatting
    nuevas_reglas = OrderedDict()
    for cf, reglas in cf_list._cf_rules.items():
        nuevo_sqref = " ".join(
            _desplazar_rango_columna(p, punto_insercion) for p in str(cf.sqref).split()
        )
        nuevo_cf = ConditionalFormatting(sqref=nuevo_sqref)
        nuevas_reglas[nuevo_cf] = reglas
    cf_list._cf_rules = nuevas_reglas


def migrar_columna_proveedor(wb):
    """Migracion unica (idempotente): inserta 'Proveedor (Razón Social)' junto
    a 'Proveedor' en Master, mueve ahi la razon social completa de cada fila
    ya registrada, y deja en 'Proveedor' el tag corto (TAGS_PROVEEDOR_CURADOS
    o generar_tag_proveedor() como fallback). Es una excepcion deliberada a
    "nunca tocar una fila de datos ya escrita" -- decision del usuario
    2026-07-16, porque la columna 'Proveedor' vieja no se toca como dato
    financiero, solo se resume a un tag visual (la razon social completa
    igual queda preservada, en la columna oculta).

    Debe correr ANTES de leer_master/inventariar, apenas se abre el libro,
    porque insertar una columna desplaza las formulas K/M, las validaciones
    de datos y el formato condicional heredado -- ver "Formato Centro de Costos.md" #14."""
    if "Master" not in wb.sheetnames:
        return
    ws = wb["Master"]
    ya_migrado = ws.cell(row=1, column=COL_PROVEEDOR_RAZON_SOCIAL_MASTER).value == (
        ENCABEZADOS_MASTER[COL_PROVEEDOR_RAZON_SOCIAL_MASTER - 1]
    )
    if ya_migrado:
        return

    print("  Migrando Master: agregando columna oculta 'Proveedor (Razón Social)'...")
    ultima = ultima_fila_datos(ws)

    ws.insert_cols(COL_PROVEEDOR_RAZON_SOCIAL_MASTER)
    _migrar_rangos_columna(ws, COL_PROVEEDOR_RAZON_SOCIAL_MASTER)

    header_cell = ws.cell(
        row=1, column=COL_PROVEEDOR_RAZON_SOCIAL_MASTER,
        value=ENCABEZADOS_MASTER[COL_PROVEEDOR_RAZON_SOCIAL_MASTER - 1],
    )
    header_cell.fill = HEADER_FILL
    header_cell.font = HEADER_FONT
    header_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    header_cell.border = THIN_BORDER

    migradas = 0
    for r in range(2, ultima + 1):
        celda_proveedor = ws.cell(row=r, column=COL_PROVEEDOR_TAG_MASTER)
        razon_social = celda_proveedor.value
        if not razon_social:
            continue
        celda_razon = ws.cell(row=r, column=COL_PROVEEDOR_RAZON_SOCIAL_MASTER, value=razon_social)
        celda_razon.font = NORMAL_FONT
        celda_razon.border = THIN_BORDER
        celda_proveedor.value = generar_tag_proveedor(razon_social)
        escribir_formulas_master(ws, r)
        migradas += 1

    ws.column_dimensions[get_column_letter(COL_PROVEEDOR_RAZON_SOCIAL_MASTER)].hidden = True
    print(f"  [OK] {migradas} fila(s) migrada(s) (tag en 'Proveedor', razón social movida a columna oculta).")


def prefijo_para_proyecto(proyecto):
    if proyecto in PREFIJOS_PROYECTO:
        return PREFIJOS_PROYECTO[proyecto]
    letras = re.sub(r"[^A-Za-zÁÉÍÓÚÑ]", "", proyecto).upper()
    derivado = (letras[:4] or "PROY")
    print(f"  [WARN] Proyecto '{proyecto}' no tiene prefijo de N Ref definido en "
          f"PREFIJOS_PROYECTO. Usando '{derivado}' derivado automaticamente -- "
          f"agregalo a PREFIJOS_PROYECTO si no es el que quieres.")
    return derivado


def siguiente_n_ref(proyecto, max_seq):
    prefijo = prefijo_para_proyecto(proyecto)
    siguiente = max_seq.get(prefijo, 0) + 1
    max_seq[prefijo] = siguiente
    return f"{prefijo}-{siguiente:03d}"


# ── INVENTARIO DE ARCHIVOS ──────────────────────────────────────────────────

def inventariar_archivos(raiz, archivos_registrados):
    """archivos_registrados: set de 'Proyecto\\archivo.ext' ya cubiertos (Master + reconciliacion)."""
    pendientes = []
    omitidos = []

    for subdir in sorted(raiz.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith(("_", ".")):
            continue
        proyecto = subdir.name

        for archivo in sorted(subdir.iterdir()):
            if not archivo.is_file():
                continue
            ext = archivo.suffix.lower()
            if ext in EXTENSIONES_IGNORAR or archivo.name == "desktop.ini":
                continue
            if ext not in EXTENSIONES_VALIDAS:
                continue

            ruta_rel = f"{proyecto}\\{archivo.name}"
            stat = archivo.stat()
            info = {
                "archivo": archivo.name,
                "proyecto": proyecto,
                "ruta_relativa": ruta_rel,
                "ruta_absoluta": str(archivo),
                "fecha_mod": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            }
            if ruta_rel in archivos_registrados:
                omitidos.append(info)
            else:
                pendientes.append(info)

    return pendientes, omitidos


# ── DATOS EXTRAÍDOS (JSON) ──────────────────────────────────────────────────

def cargar_datos_json(ruta_json):
    if not ruta_json.exists():
        return []
    with open(ruta_json, "r", encoding="utf-8") as f:
        return json.load(f)


def buscar_dato_por_archivo(datos, proyecto, archivo):
    for d in datos:
        if d.get("archivo") == archivo and d.get("proyecto") == proyecto:
            return d
    return None


def total_sin_iva_items(items):
    return sum(it["cantidad"] * it["p_unitario_sin_iva"] for it in items)


# ── ESCRITURA: DOCUMENTOS NUEVOS ────────────────────────────────────────────

def escribir_items_detalle(ws_detalle, fila_inicio, n_ref, dato, color):
    fila = fila_inicio
    for item in dato["items"]:
        total_item = item["cantidad"] * item["p_unitario_sin_iva"]
        valores = [
            n_ref, dato["proyecto"], dato.get("tipo_proyecto", ""), dato["n_documento"],
            item["nombre_item"], item.get("descripcion", ""), item.get("categoria_item", ""),
            item["cantidad"], item["p_unitario_sin_iva"], total_item,
        ]
        for c, v in enumerate(valores, 1):
            cell = ws_detalle.cell(row=fila, column=c, value=v)
            cell.font = NORMAL_FONT
            cell.border = THIN_BORDER
        ws_detalle.cell(row=fila, column=9).number_format = MONEY_FORMAT
        ws_detalle.cell(row=fila, column=10).number_format = MONEY_FORMAT
        if color:
            pintar_fila(ws_detalle, fila, len(ENCABEZADOS_DETALLE), color)
        fila += 1
    return fila


def celda_requiere_revision(valor):
    return isinstance(valor, str) and ("S/N" in valor.upper() or "SIN_NUMERO" in valor.upper())


def escribir_fila_master(ws_master, fila, n_ref, dato, info_archivo, color):
    resumen_items = "; ".join(it["nombre_item"] for it in dato["items"])
    total_sin_iva = total_sin_iva_items(dato["items"])
    iva = dato.get("iva")
    if iva is None:
        iva = round(total_sin_iva * 0.19) if dato.get("tipo_documento") in ("Factura", "Guía de Despacho") else 0

    try:
        fecha_val = datetime.strptime(dato["fecha"], "%d/%m/%Y")
    except (ValueError, KeyError):
        fecha_val = dato.get("fecha", "")

    for c in range(1, len(ENCABEZADOS_MASTER) + 1):
        cell = ws_master.cell(row=fila, column=c)
        cell.font = NORMAL_FONT
        cell.border = THIN_BORDER

    proveedor_completo = dato.get("proveedor", "")
    valores = {
        1: n_ref, 2: dato["proyecto"], 3: dato.get("tipo_proyecto", ""), 4: fecha_val,
        6: dato.get("tipo_documento", ""),
        7: generar_tag_proveedor(proveedor_completo) if proveedor_completo else "",
        8: proveedor_completo,
        9: dato.get("categoria", ""), 10: resumen_items, 12: iva,
        14: dato.get("estado", "Pendiente"), 15: info_archivo["ruta_relativa"],
        16: info_archivo["fecha_mod"],
    }
    for c, v in valores.items():
        ws_master.cell(row=fila, column=c, value=v)

    n_doc_str = str(dato["n_documento"])
    ws_master.cell(row=fila, column=5, value=n_doc_str)
    if celda_requiere_revision(n_doc_str):
        ws_master.cell(row=fila, column=5).font = ROJO_FONT

    if isinstance(fecha_val, datetime):
        ws_master.cell(row=fila, column=4).number_format = DATE_FORMAT

    escribir_formulas_master(ws_master, fila)

    iva_cell = ws_master.cell(row=fila, column=12)
    iva_cell.number_format = MONEY_FORMAT
    if dato.get("tipo_documento") in ("Factura", "Guía de Despacho") and total_sin_iva > 0:
        esperado = round(total_sin_iva * 0.19)
        if abs(iva - esperado) > 1:
            iva_cell.font = ROJO_FONT

    if color:
        pintar_fila(ws_master, fila, len(ENCABEZADOS_MASTER), color)


def escribir_formulas_master(ws_master, fila):
    """(Re)escribe K y M como formulas -- son siempre derivadas, nunca se editan a mano.
    Si la celda ya tiene un valor NO-formula (corregida a mano), se respeta y no se toca.
    (Hasta antes de la columna "Proveedor (Razón Social)" estas eran J y L --
    se corrieron una posición al agregar esa columna, ver migrar_columna_proveedor.)"""
    k_actual = ws_master.cell(row=fila, column=11).value
    if k_actual is None or (isinstance(k_actual, str) and k_actual.startswith("=")):
        ws_master.cell(row=fila, column=11, value=f"=SUMIF(Detalle!$A:$A,$A{fila},Detalle!$J:$J)")
    ws_master.cell(row=fila, column=11).number_format = MONEY_FORMAT

    m_actual = ws_master.cell(row=fila, column=13).value
    if m_actual is None or (isinstance(m_actual, str) and m_actual.startswith("=")):
        ws_master.cell(row=fila, column=13, value=f"=K{fila}+L{fila}")
    ws_master.cell(row=fila, column=13).number_format = MONEY_FORMAT


# ── PIES DE TABLA (regenerados en cada corrida) ─────────────────────────────

def regenerar_pie(ws, ncols, col_totales, etiqueta_total, primera_fila_libre, leyenda):
    fila = primera_fila_libre
    if primera_fila_libre > 2:
        fila += 1  # fila en blanco separadora
        etiqueta_fila = fila
        ws.cell(row=etiqueta_fila, column=col_totales[0] - 1, value=etiqueta_total)
        for c in col_totales:
            letra = get_column_letter(c)
            ws.cell(row=etiqueta_fila, column=c, value=f"=SUM({letra}2:{letra}{primera_fila_libre - 1})")
            ws.cell(row=etiqueta_fila, column=c).number_format = MONEY_FORMAT
        for c in range(1, ncols + 1):
            cell = ws.cell(row=etiqueta_fila, column=c)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
        fila += 2
    return escribir_leyenda(ws, fila, leyenda, ncols)


def limpiar_pie(ws):
    ultima = ultima_fila_datos(ws)
    if ws.max_row > ultima:
        ws.delete_rows(ultima + 1, ws.max_row - ultima)
    return ultima


# ── HOJAS DE PROYECTO (100% derivadas, se regeneran completas) ─────────────

def regenerar_hoja_proyecto(wb, proyecto, filas_master, color):
    """Regenera el CONTENIDO (filas 2 en adelante: datos + pie + leyenda) de la hoja
    de proyecto. Si la hoja ya existe, se reutiliza el mismo objeto de hoja en vez de
    borrarla y recrearla -- borrar+recrear tiraba tambien columnas ocultas, anchos
    manuales, autofiltro, freeze panes y validaciones de datos que el usuario haya
    dejado en esa hoja. Solo se borran las filas de datos/pie/leyenda (fila 2 en
    adelante); el encabezado (fila 1) y todo el formato a nivel de columna/hoja
    quedan intactos."""
    if proyecto in wb.sheetnames:
        ws = wb[proyecto]
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row - 1)
    else:
        ws = wb.create_sheet(title=proyecto, index=len(wb.sheetnames))

    for c, h in enumerate(ENCABEZADOS_PROYECTO, 1):
        ws.cell(row=1, column=c, value=h)
    formato_encabezado(ws, len(ENCABEZADOS_PROYECTO))
    ws.column_dimensions[get_column_letter(COL_PROVEEDOR_RAZON_SOCIAL_MASTER)].hidden = True

    # Columnas de Master que se muestran en la hoja de proyecto (se salta L =
    # IVA, que no se repite aca). Refleja el layout de ENCABEZADOS_MASTER
    # despues de agregar "Proveedor (Razón Social)" en H.
    columnas_master = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "M", "N"]
    fila = 2
    for fila_m in filas_master:
        for c, col_m in enumerate(columnas_master, 1):
            ws.cell(row=fila, column=c, value=f"=Master!{col_m}{fila_m}")
        for c in range(1, len(ENCABEZADOS_PROYECTO) + 1):
            ws.cell(row=fila, column=c).font = NORMAL_FONT
            ws.cell(row=fila, column=c).border = THIN_BORDER
        ws.cell(row=fila, column=11).number_format = MONEY_FORMAT
        ws.cell(row=fila, column=12).number_format = MONEY_FORMAT
        if color:
            pintar_fila(ws, fila, len(ENCABEZADOS_PROYECTO), color)
        fila += 1

    if fila > 2:
        fila += 1
        etiqueta = f"TOTAL {proyecto.upper()}"
        ws.cell(row=fila, column=10, value=etiqueta)
        ws.cell(row=fila, column=11, value=f"=SUM(K2:K{fila - 2})")
        ws.cell(row=fila, column=12, value=f"=SUM(L2:L{fila - 2})")
        for c in range(1, len(ENCABEZADOS_PROYECTO) + 1):
            cell = ws.cell(row=fila, column=c)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
        ws.cell(row=fila, column=11).number_format = MONEY_FORMAT
        ws.cell(row=fila, column=12).number_format = MONEY_FORMAT
        fila += 2

    escribir_leyenda(ws, fila, LEYENDA_PROYECTO, len(ENCABEZADOS_PROYECTO))
    if color:
        ws.sheet_properties.tabColor = color
    ajustar_anchos(ws)
    return ws


def asignar_colores_proyectos(wb, proyectos):
    colores = {}
    if "Master" in wb.sheetnames:
        ws_master = wb["Master"]
        ultima = ultima_fila_datos(ws_master)
        for r in range(2, ultima + 1):
            proy = ws_master.cell(row=r, column=2).value
            fill = ws_master.cell(row=r, column=2).fill
            if proy and fill and fill.fgColor and fill.fgColor.rgb and fill.fgColor.rgb not in ("00000000", None):
                rgb = fill.fgColor.rgb
                colores[proy] = rgb[2:] if len(rgb) == 8 else rgb

    usados = set(colores.values())
    libres = [c for c in PALETA if c not in usados]
    for proy in sorted(proyectos):
        if proy not in colores:
            colores[proy] = libres.pop(0) if libres else PALETA[hash(proy) % len(PALETA)]
    return colores


# ── VERIFICACIONES ──────────────────────────────────────────────────────────

def verificar_aritmetica(datos):
    inconsistencias = []
    for d in datos:
        total_sin_iva = total_sin_iva_items(d["items"])
        iva = d.get("iva")
        if iva is None:
            continue
        if d.get("tipo_documento") in ("Factura", "Guía de Despacho") and total_sin_iva > 0:
            esperado = round(total_sin_iva * 0.19)
            if abs(iva - esperado) > 1:
                inconsistencias.append({
                    "archivo": d["archivo"], "n_documento": d["n_documento"],
                    "neto": total_sin_iva, "iva": iva, "iva_esperado": esperado,
                    "nota": d.get("notas", ""),
                })
    return inconsistencias


# ── RENOMBRADO Y CONVERSIÓN DE ARCHIVOS ─────────────────────────────────────
# Renombra cada foto/PDF a "<N Ref>_<TagProveedor>_<Fecha ISO>.<ext>" y convierte
# HEIC->JPG. Cubre documentos nuevos y, retroactivamente, los ya registrados en
# Master (incluidos los del bootstrap via reconciliacion_archivos.json), con el
# mismo mecanismo idempotente: se compara el nombre fisico actual contra el
# esperado y solo se actua si difieren.

CARACTERES_INVALIDOS_ARCHIVO = re.compile(r'[\\/:*?"<>|]')


def sanitizar_nombre(texto):
    """Reemplaza espacios y caracteres invalidos en nombres de archivo Windows
    (\\ / : * ? " < > |) por '_'."""
    limpio = CARACTERES_INVALIDOS_ARCHIVO.sub("_", texto)
    limpio = re.sub(r"\s+", "_", limpio.strip())
    return re.sub(r"_+", "_", limpio)


def fecha_iso_desde_valor(valor):
    """Convierte Master.Fecha (datetime/date, o string 'dd/mm/yyyy') a 'yyyy-mm-dd'.
    Si no se puede interpretar, sanitiza el valor tal cual para no romper el nombre."""
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d")
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d")
    if isinstance(valor, str):
        try:
            return datetime.strptime(valor, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return sanitizar_nombre(valor)
    return "sin-fecha"


def nombre_esperado_archivo(n_ref, proveedor_tag, fecha_valor, extension):
    """Nombre de archivo esperado: '<N Ref>_<TagProveedor>_<Fecha ISO><ext>'.
    Los .heic/.HEIC pasan a .jpg (se convierten); el resto conserva su extension."""
    tag = sanitizar_nombre(proveedor_tag or "SinProveedor")
    fecha = fecha_iso_desde_valor(fecha_valor)
    ext = extension.lower()
    if ext == ".heic":
        ext = ".jpg"
    return f"{n_ref}_{tag}_{fecha}{ext}"


def construir_reconciliacion_inversa(reconciliacion):
    """{n_ref: ruta_relativa} a partir del mapeo 'ruta_relativa -> n_ref' de
    reconciliacion_archivos.json."""
    return {n_ref: ruta for ruta, n_ref in reconciliacion.items()}


def resolver_ruta_actual(fila_dict, reconciliacion_inversa):
    """Ruta relativa ('Proyecto\\archivo.ext') del archivo fisico actual para
    una fila de Master, o None si no se puede determinar.

    OJO: la ubicacion fisica puede NO coincidir con Master.Proyecto (ver nota
    de UMAG-002 en reconciliacion_archivos.json) -- por eso se usa el Proyecto
    embebido en la propia ruta relativa (de Archivo origen o de la
    reconciliacion), nunca fila_dict['proyecto']."""
    if fila_dict.get("archivo_origen"):
        return str(fila_dict["archivo_origen"])
    return reconciliacion_inversa.get(fila_dict["n_ref"])


def planificar_renombrado_fila(fila_dict, reconciliacion_inversa):
    """Calcula (sin tocar disco) que accion corresponde para una fila de Master:
    {'n_ref', 'fila', 'accion', 'ruta_actual', 'ruta_nueva', 'nombre_nuevo'}.
    'accion' es uno de: 'ya_correcto', 'renombrar', 'convertir_heic',
    'archivo_no_encontrado'. Se usa tanto para el preview de status como,
    antes de ejecutar, para el run real."""
    base = {
        "n_ref": fila_dict["n_ref"], "fila": fila_dict["fila"],
        "ruta_actual": None, "ruta_nueva": None, "nombre_nuevo": None,
    }

    ruta_relativa = resolver_ruta_actual(fila_dict, reconciliacion_inversa)
    if not ruta_relativa:
        return {**base, "accion": "archivo_no_encontrado"}
    if "\\" not in ruta_relativa:
        return {**base, "accion": "archivo_no_encontrado"}

    proyecto_fisico, nombre_archivo = ruta_relativa.split("\\", 1)
    ruta_actual = RAIZ_DOCS / proyecto_fisico / nombre_archivo
    if not ruta_actual.exists():
        return {**base, "accion": "archivo_no_encontrado", "ruta_actual": ruta_actual}

    extension_actual = ruta_actual.suffix
    nombre_nuevo = nombre_esperado_archivo(
        fila_dict["n_ref"], fila_dict["proveedor_tag"], fila_dict["fecha"], extension_actual
    )
    ruta_nueva = ruta_actual.parent / nombre_nuevo

    if ruta_actual.name == nombre_nuevo:
        return {**base, "accion": "ya_correcto", "ruta_actual": ruta_actual,
                "ruta_nueva": ruta_actual, "nombre_nuevo": nombre_nuevo}

    accion = "convertir_heic" if extension_actual.lower() == ".heic" else "renombrar"
    return {**base, "accion": accion, "ruta_actual": ruta_actual,
            "ruta_nueva": ruta_nueva, "nombre_nuevo": nombre_nuevo}


def planificar_renombrados(filas_master, reconciliacion_inversa):
    """planificar_renombrado_fila() aplicado a cada fila de Master. No toca disco."""
    return [planificar_renombrado_fila(fm, reconciliacion_inversa) for fm in filas_master]


def convertir_heic_a_jpg(ruta_origen, ruta_destino):
    """Decodifica un HEIC y lo guarda como JPG, respetando la orientacion EXIF
    (las fotos de celular la traen y sin esto quedarian rotadas). Calidad 90,
    sin redimensionar -- son documentos tributarios que pueden necesitar zoom."""
    from PIL import Image, ImageOps
    import pillow_heif

    pillow_heif.register_heif_opener()
    with Image.open(ruta_origen) as imagen:
        imagen = ImageOps.exif_transpose(imagen)
        imagen.convert("RGB").save(str(ruta_destino), "JPEG", quality=90)


def ejecutar_plan_renombrado(item):
    """Ejecuta en disco la accion de un item de planificar_renombrado_fila
    ('renombrar' o 'convertir_heic'; 'ya_correcto'/'archivo_no_encontrado' no
    hacen nada). Devuelve (ok, error) -- no toca Master, eso lo hace el
    llamador (Task 5)."""
    if item["accion"] == "renombrar":
        try:
            item["ruta_actual"].rename(item["ruta_nueva"])
        except Exception as e:
            return False, str(e)
        return True, None

    if item["accion"] == "convertir_heic":
        try:
            convertir_heic_a_jpg(item["ruta_actual"], item["ruta_nueva"])
        except Exception as e:
            return False, str(e)
        item["ruta_actual"].unlink()
        return True, None

    return True, None


def excel_esta_bloqueado(ruta_excel):
    """True si ruta_excel existe y no se puede abrir para escritura (ej. porque
    esta abierto en Excel). Se usa como chequeo previo a PASO 9 -- ese paso
    renombra/borra archivos reales en disco sin poder deshacerse, asi que hay
    que confirmar que el Excel es escribible ANTES de tocar ningun archivo,
    no despues (si se descubriera recien al guardar en PASO 11, ya seria
    tarde: las fotos ya estarian renombradas/borradas y el Master actualizado
    solo en memoria, nunca persistido)."""
    if not ruta_excel.exists():
        return False
    try:
        with open(ruta_excel, "r+b"):
            pass
        return False
    except PermissionError:
        return True


def aplicar_renombrados(ws_master, filas_master, reconciliacion_inversa):
    """Recorre filas_master, ejecuta los renombrados/conversiones pendientes y
    actualiza Master.Archivo origen (col 15) y Master.Fecha modificacion
    (col 16, con el mtime real del archivo resultante) en las filas afectadas.
    Excepcion deliberada a la regla de oro de "nunca tocar una fila ya
    escrita" -- mismo tipo de excepcion que migrar_columna_proveedor().
    Devuelve (cantidad_renombrados, advertencias)."""
    renombrados = 0
    advertencias = []

    for item in planificar_renombrados(filas_master, reconciliacion_inversa):
        if item["accion"] == "archivo_no_encontrado":
            advertencias.append({
                "n_ref": item["n_ref"],
                "detalle": "Archivo fisico no encontrado para renombrar/convertir.",
            })
            continue
        if item["accion"] == "ya_correcto":
            continue

        ok, error = ejecutar_plan_renombrado(item)
        if not ok:
            accion_desc = "la conversion HEIC" if item["accion"] == "convertir_heic" else "el renombrado"
            advertencias.append({
                "n_ref": item["n_ref"],
                "detalle": f"Fallo {accion_desc}: {error}",
            })
            continue

        proyecto_fisico = item["ruta_nueva"].parent.name
        ws_master.cell(row=item["fila"], column=15, value=f"{proyecto_fisico}\\{item['nombre_nuevo']}")
        mtime = datetime.fromtimestamp(item["ruta_nueva"].stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        ws_master.cell(row=item["fila"], column=16, value=mtime)
        renombrados += 1

    return renombrados, advertencias


# --- MAIN ---------------------------------------------------------------------

def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    print("=" * 70)
    print("  REGISTRO CENTRO DE COSTOS - QUEMPIN SpA")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if not RAIZ_DOCS.exists():
        print(f"ERROR: No existe la carpeta raiz: {RAIZ_DOCS}")
        return
    if not RUTA_JSON.exists():
        print(f"ERROR: No existe el JSON de datos: {RUTA_JSON}")
        return

    print("\n--- PASO 1: Backup ---")
    hacer_backup(RUTA_EXCEL)

    print("\n--- PASO 2: Abrir Excel ---")
    if RUTA_EXCEL.exists():
        wb = openpyxl.load_workbook(str(RUTA_EXCEL), data_only=False)
        print(f"  Excel abierto. Hojas existentes: {wb.sheetnames}")
    else:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        print("  Excel creado desde cero.")

    migrar_columna_proveedor(wb)

    if "Master" not in wb.sheetnames:
        ws_master = wb.create_sheet("Master", 0)
        for c, h in enumerate(ENCABEZADOS_MASTER, 1):
            ws_master.cell(row=1, column=c, value=h)
        formato_encabezado(ws_master, len(ENCABEZADOS_MASTER))
        ws_master.column_dimensions[get_column_letter(COL_PROVEEDOR_RAZON_SOCIAL_MASTER)].hidden = True
    else:
        ws_master = wb["Master"]

    if "Detalle" not in wb.sheetnames:
        ws_detalle = wb.create_sheet("Detalle", 1)
        for c, h in enumerate(ENCABEZADOS_DETALLE, 1):
            ws_detalle.cell(row=1, column=c, value=h)
        formato_encabezado(ws_detalle, len(ENCABEZADOS_DETALLE))
    else:
        ws_detalle = wb["Detalle"]

    print("\n--- PASO 3: Leer registros existentes ---")
    filas_master, max_seq, docs_registrados = leer_master(ws_master)
    reconciliacion = cargar_reconciliacion()
    archivos_registrados = set(reconciliacion.keys())
    for fm in filas_master:
        if fm["archivo_origen"]:
            archivos_registrados.add(str(fm["archivo_origen"]))
    print(f"  Documentos ya en Master: {len(filas_master)}")
    print(f"  Archivos ya cubiertos (Master + reconciliacion): {len(archivos_registrados)}")

    print("\n--- PASO 4: Inventariar archivos ---")
    pendientes, omitidos = inventariar_archivos(RAIZ_DOCS, archivos_registrados)
    print(f"  Pendientes: {len(pendientes)}")
    print(f"  Omitidos (ya registrados): {len(omitidos)}")

    print("\n--- PASO 5: Cargar datos extraidos ---")
    datos_json = cargar_datos_json(RUTA_JSON)
    print(f"  Entradas en {RUTA_JSON.name}: {len(datos_json)}")

    limpiar_pie(ws_detalle)
    limpiar_pie(ws_master)
    fila_detalle = ultima_fila_datos(ws_detalle) + 1
    fila_master = ultima_fila_datos(ws_master) + 1

    proyectos_tocados = set(fm["proyecto"] for fm in filas_master if fm["proyecto"])
    colores = asignar_colores_proyectos(wb, proyectos_tocados | {p["proyecto"] for p in pendientes})

    registrados_ok = 0
    limitaciones = []
    alertas_legibilidad = []
    posibles_duplicados = []

    print("\n--- PASO 6: Escribir documentos nuevos ---")
    for info in pendientes:
        dato = buscar_dato_por_archivo(datos_json, info["proyecto"], info["archivo"])
        if not dato:
            limitaciones.append({
                "archivo": info["archivo"], "proyecto": info["proyecto"],
                "detalle": "No se encontraron datos extraidos en el JSON para este archivo.",
                "accion": "Agregar manualmente los datos (con items) al JSON y re-ejecutar.",
            })
            print(f"  [WARN] Sin datos para: {info['proyecto']}\\{info['archivo']}")
            continue
        if not dato.get("items"):
            limitaciones.append({
                "archivo": info["archivo"], "proyecto": info["proyecto"],
                "detalle": "La entrada del JSON no tiene 'items' (lista de lineas).",
                "accion": "Agregar al menos un item con nombre_item/cantidad/p_unitario_sin_iva.",
            })
            continue

        n_doc_str = str(dato["n_documento"])
        n_doc_norm = n_doc_str.lstrip("0") or "0"
        if n_doc_str in docs_registrados or n_doc_norm in docs_registrados:
            posibles_duplicados.append({
                "archivo": info["archivo"], "proyecto": info["proyecto"], "n_documento": n_doc_str,
            })

        n_ref = siguiente_n_ref(dato["proyecto"], max_seq)
        color = colores.get(dato["proyecto"])

        fila_detalle = escribir_items_detalle(ws_detalle, fila_detalle, n_ref, dato, color)
        escribir_fila_master(ws_master, fila_master, n_ref, dato, info, color)
        docs_registrados.add(n_doc_str)
        docs_registrados.add(n_doc_norm)

        proyectos_tocados.add(dato["proyecto"])
        registrados_ok += 1
        print(f"  [OK] {info['proyecto']}\\{info['archivo']} -> {n_ref} "
              f"(doc {dato['n_documento']}, {len(dato['items'])} item(s))")

        if celda_requiere_revision(n_doc_str):
            alertas_legibilidad.append({
                "archivo": info["archivo"], "proyecto": dato["proyecto"],
                "detalle": "N Documento requiere revision manual.",
            })
        fila_master += 1

    print("\n--- PASO 7: Regenerar pies de Detalle/Master ---")
    regenerar_pie(ws_detalle, len(ENCABEZADOS_DETALLE), [10], "TOTAL GENERAL", fila_detalle, LEYENDA_DETALLE)
    regenerar_pie(ws_master, len(ENCABEZADOS_MASTER), [11, 12, 13], "TOTAL GENERAL", fila_master, LEYENDA_MASTER)

    print("\n--- PASO 8: Regenerar hojas de proyecto ---")
    ultima_master = fila_master - 1
    for proyecto in sorted(proyectos_tocados):
        filas_de_este_proyecto = [
            r for r in range(2, ultima_master + 1)
            if ws_master.cell(row=r, column=2).value == proyecto
        ]
        if not filas_de_este_proyecto:
            continue
        regenerar_hoja_proyecto(wb, proyecto, filas_de_este_proyecto, colores.get(proyecto))
        print(f"  [OK] Hoja '{proyecto}' regenerada ({len(filas_de_este_proyecto)} documento(s))")

    if excel_esta_bloqueado(RUTA_EXCEL):
        print("\n[ERROR] El archivo esta abierto en Excel (o bloqueado). Cierralo antes de continuar.")
        print("        No se renombro ni convirtio ningun archivo; no se guardaron cambios.")
        return

    print("\n--- PASO 9: Renombrar y convertir archivos ---")
    reconciliacion_inversa = construir_reconciliacion_inversa(reconciliacion)
    filas_master_actual, _, _ = leer_master(ws_master)
    renombrados, advertencias_renombrado = aplicar_renombrados(
        ws_master, filas_master_actual, reconciliacion_inversa
    )
    print(f"  [OK] {renombrados} archivo(s) renombrado(s)/convertido(s).")
    for adv in advertencias_renombrado:
        print(f"  [WARN] {adv['n_ref']}: {adv['detalle']}")

    print("\n--- PASO 10: Formato final ---")
    ajustar_anchos(ws_master)
    ajustar_anchos(ws_detalle)
    orden_deseado = ["Master", "Detalle"] + sorted(proyectos_tocados)
    for i, nombre in enumerate(orden_deseado):
        if nombre in wb.sheetnames:
            wb.move_sheet(nombre, offset=i - wb.sheetnames.index(nombre))
    print(f"  [OK] Hojas ordenadas: {wb.sheetnames}")

    print("\n--- PASO 11: Guardar ---")
    try:
        wb.save(str(RUTA_EXCEL))
        print(f"  [OK] Excel guardado: {RUTA_EXCEL.name}")
    except PermissionError:
        print("  ERROR: El archivo esta abierto en Excel. Cierralo y vuelve a ejecutar.")
        return

    print("\n--- PASO 12: Verificaciones aritmeticas (sobre todo el JSON) ---")
    inconsistencias = verificar_aritmetica(datos_json)

    print("\n" + "=" * 70)
    print("  INFORME DE AUDITORIA")
    print("=" * 70)

    print("\n1. ALERTAS DE LEGIBILIDAD")
    if alertas_legibilidad:
        for a in alertas_legibilidad:
            print(f"   * {a['archivo']} | Proyecto: {a['proyecto']} | {a['detalle']}")
    else:
        print("   Sin hallazgos.")

    print("\n2. INCONSISTENCIAS ARITMETICAS (Neto vs IVA 19%)")
    if inconsistencias:
        for inc in inconsistencias:
            print(f"   * Doc {inc['n_documento']} ({inc['archivo']}): "
                  f"Neto={inc['neto']:,} | IVA registrado={inc['iva']:,} vs esperado={inc['iva_esperado']:,}")
            if inc["nota"]:
                print(f"     Nota: {inc['nota'][:120]}")
    else:
        print("   Sin hallazgos.")

    print("\n3. POSIBLES DUPLICADOS (mismo N Documento que uno ya registrado)")
    if posibles_duplicados:
        for dup in posibles_duplicados:
            print(f"   * {dup['proyecto']}\\{dup['archivo']} | N Documento: {dup['n_documento']}")
    else:
        print("   Sin hallazgos.")

    print("\n4. LIMITACIONES DE REGISTRO")
    if limitaciones:
        for lim in limitaciones:
            print(f"   * {lim['archivo']} | Proyecto: {lim['proyecto']}")
            print(f"     {lim['detalle']} Accion: {lim['accion']}")
    else:
        print("   Sin hallazgos.")

    print("\n5. RENOMBRADO/CONVERSION DE ARCHIVOS")
    if advertencias_renombrado:
        for adv in advertencias_renombrado:
            print(f"   * {adv['n_ref']}: {adv['detalle']}")
    else:
        print("   Sin hallazgos.")

    print("\n" + "-" * 70)
    print("  RESUMEN FINAL")
    print("-" * 70)
    print(f"  {'Documentos nuevos registrados:':<40} {registrados_ok}")
    print(f"  {'Documentos omitidos (ya registrados):':<40} {len(omitidos)}")
    print(f"  {'Posibles duplicados:':<40} {len(posibles_duplicados)}")
    print(f"  {'Limitaciones (faltan datos en JSON):':<40} {len(limitaciones)}")
    print(f"  {'Archivos renombrados/convertidos:':<40} {renombrados}")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
