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
- El CONTENIDO de una fila de datos ya escrita (items en Detalle, documentos en
  Master) NUNCA se vuelve a tocar una vez creado -- es historial editable a mano
  por el usuario. Su POSICION si se reordena en cada corrida (ver
  reordenar_por_fecha): fila 2 = documento con la fecha mas reciente, fondo de la
  tabla = el mas antiguo. Reordenar mueve valores/formato tal cual, nunca los
  reescribe con datos distintos.
- Las filas de pie (TOTAL GENERAL + leyenda) y las hojas de proyecto SI se regeneran
  en cada corrida, porque son 100% derivadas.
- Backup siempre antes de escribir.
"""

import importlib
import json
import re
import shutil
import sys
import time
import unicodedata
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter, column_index_from_string

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────

RAIZ = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ.parent
# Desde 2026-07-17 la fuente oficial de documentos es el acceso directo de
# OneDrive "Sitio de comunicacion - Centro de Costos 1" (carpeta compartida
# donde suben facturas/boletas los colegas), no la carpeta local "Facturas y
# Boletas/" -- ver CLAUDE.md seccion "Sitio de comunicacion".
RAIZ_SITIO_COMUNICACION = RAIZ_MODULO / "Sitio de comunicación - Centro de Costos 1"
# Carpeta COMPARTIDA por ambos paises (desde 2026-08-21): contiene las
# subcarpetas "Chile/" y "Perú/", cada una con sus carpetas de proyecto
# adentro -- ver docs/superpowers/specs/2026-08-21-peru-expansion-design.md.
# RAIZ_DOCS (mas abajo, mutable) es la version YA resuelta para el pais activo.
RAIZ_DOCS_BASE = RAIZ_SITIO_COMUNICACION / "Facturas y Boletas"
RUTA_EXCEL = RAIZ_MODULO / "Excel" / "Centro de Costos.xlsx"
RUTA_EXCEL_SITIO_COMUNICACION = RAIZ_SITIO_COMUNICACION / "Centro de Costos.xlsx"
RUTA_JSON = RAIZ / "datos_extraidos.json"
RUTA_RECONCILIACION = RAIZ / "reconciliacion_archivos.json"
RUTA_BACKUPS = RAIZ_MODULO / "Excel" / "Respaldos"
RUTA_CORRECCIONES = RAIZ / "correcciones_manuales.json"
RUTA_ERRORES_MD = RAIZ_MODULO / ".claude" / "skills" / "Registro_Centro_de_Costos" / "ERRORES.md"
RUTA_LOGS = RAIZ / "logs"
RAIZ_VISUALIZADOR_WEB = RAIZ_MODULO / "Visualizador Web"
RAIZ_ANALISIS_FINANCIERO = RAIZ_MODULO.parent / "Sistema Analisis Financiero"
# Perú no tiene codigo propio (ver spec maestro): solo aloja Excel/respaldos/
# JSON/dashboards. El codigo de arriba (este archivo) es compartido.
RAIZ_PERU = RAIZ_MODULO.parent / "Peru" / "Centro de Costos"

PREFIJOS_PROYECTO = {
    "UMAG": "UMAG",
    "Cesfam Limache": "CFLI",
    "Cesfam Constitución": "CCON",
    "Gastos Generales": "GGEN",
    "Microturbina LER": "MLER",
    "Fiscalía Quilpué y Quintero": "FQYQ",
    "ESFOCAR": "ESFO",
    "CONAF Puerto Montt": "CPMO",
    "Bomba Wilo Conchalí": "BWIL",
    "CESFAM Chillán": "CCHI",
    "Caldera Valdivia": "CVAL",
    "Calderas Antofagasta": "CANT",
    "Comisaría Conchalí": "COMC",
    "Cremación Concepción": "CREM",
    "Junji's Valparaiso": "JUNJ",
    "Putaendo Hospital Pinel": "HPIN",
    "FACH2": "FCH2",
    "FACH1": "FCH1",
    "Junji V2": "JUN2",
}

# Config por pais -- moneda/impuesto/rutas que varian entre Chile y Peru.
# Los valores de "CL" son literalmente las constantes de arriba (cero cambio
# de comportamiento); "PE" son las mismas rutas dentro de Peru/Centro de
# Costos/ (sin codigo propio, ver RAIZ_PERU) mas IGV 18% y soles.
PAISES = {
    "CL": {
        "razon_social": "QUEMPIN SpA",
        "moneda": "CLP", "simbolo": "$",
        "nombre_impuesto_corto": "IVA", "tasa_impuesto": 0.19,
        "ruta_excel": RUTA_EXCEL,
        "ruta_docs": RAIZ_DOCS_BASE / "Chile",
        "ruta_backups": RUTA_BACKUPS,
        "ruta_json": RUTA_JSON,
        "ruta_reconciliacion": RUTA_RECONCILIACION,
        "ruta_correcciones": RUTA_CORRECCIONES,
        "ruta_errores_md": RUTA_ERRORES_MD,
        "ruta_logs": RUTA_LOGS,
        "ruta_visualizador_web": RAIZ_VISUALIZADOR_WEB,
        "ruta_excel_sitio_comunicacion": RUTA_EXCEL_SITIO_COMUNICACION,
        "prefijos_proyecto": PREFIJOS_PROYECTO,
    },
    "PE": {
        # Razón social a la que van dirigidos los documentos de Perú (pedido
        # del usuario 2026-08-21) -- entidad distinta a "QUEMPIN SpA" (Chile).
        "razon_social": "QUEMPIN SAC",
        "moneda": "PEN", "simbolo": "S/",
        "nombre_impuesto_corto": "IGV", "tasa_impuesto": 0.18,
        "ruta_excel": RAIZ_PERU / "Excel" / "Centro de Costos Perú.xlsx",
        "ruta_docs": RAIZ_DOCS_BASE / "Perú",
        "ruta_backups": RAIZ_PERU / "Excel" / "Respaldos",
        "ruta_json": RAIZ_PERU / "datos_extraidos_peru.json",
        "ruta_reconciliacion": RAIZ_PERU / "reconciliacion_archivos_peru.json",
        "ruta_correcciones": RAIZ_PERU / "correcciones_manuales_peru.json",
        "ruta_errores_md": (
            RAIZ_MODULO / ".claude" / "skills" / "Registro_Centro_de_Costos" / "ERRORES_PERU.md"
        ),
        "ruta_logs": RAIZ_PERU / "logs",
        "ruta_visualizador_web": RAIZ_PERU / "Visualizador Web",
        # Peru no tiene (todavia) un sitio de comunicacion SharePoint propio.
        "ruta_excel_sitio_comunicacion": None,
        "prefijos_proyecto": {},
    },
}


def configurar_pais(pais="CL"):
    """Reconfigura las rutas/constantes globales del modulo para operar sobre
    el pais pedido -- 'CL' (Chile, default, preserva el comportamiento actual)
    o 'PE' (Peru). Debe llamarse ANTES de cualquier otra funcion del modulo
    que dependa de estas rutas -- main() ya lo hace como primer paso (ver
    PASO 0), y cada comando de driver.py lo hace antes de tocar acc.* .
    Lanza ValueError si 'pais' no esta en PAISES, sin dejar el modulo a medio
    configurar (se valida antes de reasignar nada)."""
    if pais not in PAISES:
        raise ValueError(f"País desconocido: {pais!r}. Usar uno de {sorted(PAISES)}.")

    global PAIS_ACTUAL, RUTA_EXCEL, RAIZ_DOCS, RUTA_BACKUPS, RUTA_JSON
    global RUTA_RECONCILIACION, RUTA_CORRECCIONES, RUTA_ERRORES_MD, RUTA_LOGS
    global RAIZ_VISUALIZADOR_WEB, RUTA_EXCEL_SITIO_COMUNICACION, PREFIJOS_PROYECTO
    global MONEDA, SIMBOLO_MONEDA, NOMBRE_IMPUESTO_CORTO, TASA_IMPUESTO, NOMBRE_IMPUESTO_PCT
    global ENCABEZADOS_MASTER, ENCABEZADOS_DETALLE, ENCABEZADOS_PROYECTO
    global MONEY_FORMAT, LEYENDA_MASTER, RAZON_SOCIAL

    cfg = PAISES[pais]
    PAIS_ACTUAL = pais
    RAZON_SOCIAL = cfg["razon_social"]
    RUTA_EXCEL = cfg["ruta_excel"]
    RAIZ_DOCS = cfg["ruta_docs"]
    RUTA_BACKUPS = cfg["ruta_backups"]
    RUTA_JSON = cfg["ruta_json"]
    RUTA_RECONCILIACION = cfg["ruta_reconciliacion"]
    RUTA_CORRECCIONES = cfg["ruta_correcciones"]
    RUTA_ERRORES_MD = cfg["ruta_errores_md"]
    RUTA_LOGS = cfg["ruta_logs"]
    RAIZ_VISUALIZADOR_WEB = cfg["ruta_visualizador_web"]
    RUTA_EXCEL_SITIO_COMUNICACION = cfg["ruta_excel_sitio_comunicacion"]
    PREFIJOS_PROYECTO = cfg["prefijos_proyecto"]

    MONEDA = cfg["moneda"]
    SIMBOLO_MONEDA = cfg["simbolo"]
    NOMBRE_IMPUESTO_CORTO = cfg["nombre_impuesto_corto"]
    TASA_IMPUESTO = cfg["tasa_impuesto"]
    NOMBRE_IMPUESTO_PCT = f"{NOMBRE_IMPUESTO_CORTO} {round(TASA_IMPUESTO * 100)}%"

    ENCABEZADOS_MASTER = [
        "N° Ref.", "Proyecto", "Tipo de Proyecto", "Fecha", "N° Documento",
        "Tipo Documento", "Proveedor", "Proveedor (Razón Social)", "Categoría",
        "Resumen Ítems", f"Total sin {NOMBRE_IMPUESTO_CORTO} ({MONEDA})",
        f"{NOMBRE_IMPUESTO_PCT} ({MONEDA})",
        f"Total con {NOMBRE_IMPUESTO_CORTO} ({MONEDA})", "Estado", "Archivo origen",
        "Fecha modificación",
    ]
    ENCABEZADOS_DETALLE = [
        "N° Ref.", "Proyecto", "Tipo de Proyecto", "N° Documento", "Nombre Ítem",
        "Descripción", "Categoría Ítem", "Cantidad",
        f"P. Unitario sin {NOMBRE_IMPUESTO_CORTO}",
        f"Total sin {NOMBRE_IMPUESTO_CORTO} ({MONEDA})",
        f"Total con {NOMBRE_IMPUESTO_CORTO} ({MONEDA})",
    ]
    ENCABEZADOS_PROYECTO = [
        "N° Ref.", "Proyecto", "Tipo de Proyecto", "Fecha", "N° Documento",
        "Tipo Documento", "Proveedor", "Proveedor (Razón Social)", "Categoría",
        "Resumen Ítems", f"Total sin {NOMBRE_IMPUESTO_CORTO} ({MONEDA})",
        f"Total con {NOMBRE_IMPUESTO_CORTO} ({MONEDA})", "Estado",
    ]
    MONEY_FORMAT = f'"{SIMBOLO_MONEDA}"#,##0'
    LEYENDA_MASTER = [
        "Cursiva = celda editable a mano",
        "Rojo = valor que requiere revisión (pasa el cursor por la celda para ver el motivo)",
        "Azul marino = valor corregido a mano por ti (Claude lo respeta y no lo sobreescribe)",
        "Fondo de color = proyecto (se pinta solo según la columna 'Proyecto'; si la cambias, "
        "el color se actualiza) · la foto de cada documento lleva su N° como nombre de archivo",
        f"⚠️ 'Total sin {NOMBRE_IMPUESTO_CORTO}' y 'Total con {NOMBRE_IMPUESTO_CORTO}' se calculan "
        "desde Detalle. 'Archivo origen' y 'Fecha modificación' son el registro de lo ya "
        "procesado: no editar.",
    ]

PALETA = [
    "FFB7CE", "FFBE9D", "E9CF87", "B6DFA0", "86E6D3", "89DFFF",
    "B9CFFF", "E9BFFC",
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
    "Ortuzar SpA": "Dezar",  # mismo proveedor que la entrada de arriba (pedido 2026-09-07)
    "Engas Chile SpA": "Engas",
    "Antonio Ruiz Ch. e Hijos Ltda.": "Antonio Ruiz",
    "Comercial Anwo S.A.": "Anwo",
    "Comercial ANWO S.A.": "Anwo",  # variante en mayusculas del mismo proveedor (pedido 2026-09-07)
    "ANWO S.A.": "Anwo",
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
            # rstrip: la marca puede venir seguida de una coma antes del resto
            # del descriptor (ej. "(Copec, por cuenta y orden de ...)") -- sin
            # esto, "Copec," quedaba como tag distinto de "Copec" (mismo
            # proveedor duplicado bajo dos tags, corregido 2026-09-07).
            return contenido.split()[0].rstrip(",.;:")

    base = _SUFIJOS_LEGALES_RE.sub("", razon_social)
    palabras = [
        p for p in re.split(r"\s+", base.strip(" .,"))
        if p and p.strip(".,").lower() not in _PALABRAS_GENERICAS_TAG
    ]
    tag = " ".join(palabras[:2]).strip(" .,")
    return tag or razon_social

EXTENSIONES_VALIDAS = {".png", ".jpg", ".jpeg", ".heic", ".pdf"}
EXTENSIONES_IGNORAR = {".html", ".txt", ".ini", ".tmp"}

# Columna (1-indexada) de "Proveedor (Razón Social)" en Master y en las hojas
# de proyecto -- se usa para ocultarla y para el mapeo de columnas al migrar.
COL_PROVEEDOR_TAG_MASTER = 7
COL_PROVEEDOR_RAZON_SOCIAL_MASTER = 8

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

PATRON_NREF = re.compile(r"^[A-Za-zÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ0-9]*-\d+$")

# ── TIPO DE DOCUMENTO: UNA SOLA FUENTE DE VERDAD ────────────────────────────
# El tipo lo escribe un agente al extraer el documento, asi que la misma cosa
# entra con y sin tilde: datos_extraidos.json tiene hoy 3 "Guía de Despacho"
# y 8 "Guia de Despacho", 7 "Nota de Crédito" y 1 "Nota de Credito".
# Comparar el string crudo contra la tupla literal ("Factura", "Guía de
# Despacho") -- que es lo que se hacia en 3 lugares distintos del archivo --
# dejaba esas 8 guias de despacho fuera de TODA verificacion aritmetica, y
# les habria calculado impuesto 0 si no hubieran traido 'iva' explicito.
# Normalizar en un solo lugar cierra las tres puertas a la vez.
TIPOS_AFECTOS = frozenset({"factura", "guia de despacho"})


def clave_tipo_documento(valor):
    """Forma comparable de un tipo de documento: sin tildes, en minusculas y
    con los espacios colapsados. 'Guía de Despacho', 'Guia de despacho' y
    '  GUIA  DE  DESPACHO ' colapsan todas al mismo valor."""
    descompuesto = unicodedata.normalize("NFD", str(valor or ""))
    sin_tildes = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.lower().split())


def es_documento_afecto(tipo_documento):
    """True si el documento paga impuesto sobre el neto (Factura o Guia de
    Despacho). Las boletas ya vienen con el impuesto incluido en el precio y
    las notas de credito son el reverso de una compra, no una compra."""
    return clave_tipo_documento(tipo_documento) in TIPOS_AFECTOS


# Tolerancia al cuadrar Neto contra impuesto declarado. El impuesto de un
# documento real se calcula sobre el neto TOTAL, no item por item, asi que
# sumar los items puede desviarse unos pesos por redondeo. El umbral anterior
# (+-1) convertia diferencias de 5 pesos sobre 31.758 en "inconsistencia".
TOLERANCIA_IMPUESTO = 2

# Categorias donde el precio pagado lleva, ademas del IVA, un impuesto
# especifico (en Chile: IEC + FEPP sobre combustibles). En esos documentos el
# campo 'iva' agrupa los tres a proposito, para que Neto + iva sea el total
# realmente pagado -- ver las notas de los propios documentos en el JSON.
CATEGORIAS_CON_IMPUESTO_ESPECIFICO = frozenset({"combustible"})

NAVY = "1F4E79"
NAVY_OSCURO = "1F3864"
ROJO = "C00000"
BLANCO = "FFFFFF"
NEGRO = "000000"

HEADER_FILL = PatternFill("solid", fgColor=NAVY)
HEADER_FONT = Font(name="Calibri", bold=True, size=11, color=BLANCO)
NORMAL_FONT = Font(name="Calibri", size=11, color=NEGRO)
ROJO_FONT = Font(name="Calibri", size=11, color=ROJO)
AZUL_MARINO_FONT = Font(name="Calibri", size=11, color=NAVY_OSCURO)

# Columnas de Master que se repiten en Detalle -- si una correccion manual
# confirmada toca una de estas columnas en Master, se propaga tambien a la
# columna correspondiente de Detalle (una fila por cada item del N Ref).
CAMPOS_PROPAGADOS_A_DETALLE = {5: 4}  # N Documento: Master col E -> Detalle col D
# Formato fijo DD-MM-AAAA -- pedido del usuario 2026-07-28, reemplaza el numFmtId 14
# ("Fecha corta" nativo, adaptable a la configuracion regional) usado desde 2026-07-17.
DATE_FORMAT = "DD-MM-YYYY"
THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)

configurar_pais("CL")  # valores por defecto al importar -- ver docstring de configurar_pais()


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

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def carpeta_mes(ruta_backups, fecha):
    """Subcarpeta del mes correspondiente (ej. 'Julio 2026') dentro de ruta_backups,
    creandola si todavia no existe."""
    ruta = ruta_backups / f"{MESES_ES[fecha.month]} {fecha.year}"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def hacer_backup(ruta_excel, ruta_backups=None):
    ruta_backups = ruta_backups or RUTA_BACKUPS
    if not ruta_excel.exists():
        print(f"[WARN] El archivo {ruta_excel} no existe, se creara desde cero.")
        return None
    ahora_dt = datetime.now()
    ruta_carpeta_mes = carpeta_mes(ruta_backups, ahora_dt)
    ahora = ahora_dt.strftime("%Y-%m-%d %H%M")
    ruta_backup = ruta_carpeta_mes / f"Centro de Costos - backup {ahora}.xlsx"
    shutil.copy2(str(ruta_excel), str(ruta_backup))
    print(f"[OK] Backup creado: Respaldos/{ruta_carpeta_mes.name}/{ruta_backup.name}")
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
        if es_n_documento_real(n_doc):
            docs_registrados.add(str(n_doc))
            docs_registrados.add(normalizar_n_documento(n_doc))

        filas.append({
            "fila": r, "n_ref": n_ref, "proyecto": proyecto,
            "archivo_origen": archivo_origen,
            "proveedor_tag": ws_master.cell(row=r, column=7).value,
            "fecha": ws_master.cell(row=r, column=4).value,
        })

    return filas, max_seq, docs_registrados


def _mapa_n_documento_a_n_ref(ws_master):
    """N Documento normalizado -> N Ref, SOLO para los numeros que aparecen una
    unica vez en Master. Un N Documento es unico por emisor, no globalmente
    (ver CLAUDE.md del modulo), asi que un numero repetido entre dos emisores
    distintos no identifica una fila: esos se omiten a proposito en vez de
    devolver cualquiera de las dos."""
    mapa = {}
    repetidos = set()
    for r in range(2, ultima_fila_datos(ws_master) + 1):
        n_ref = ws_master.cell(row=r, column=1).value
        if not isinstance(n_ref, str) or not PATRON_NREF.match(n_ref):
            continue
        n_doc = ws_master.cell(row=r, column=5).value
        if not es_n_documento_real(n_doc):
            continue
        clave = normalizar_n_documento(n_doc)
        if clave in mapa:
            repetidos.add(clave)
        mapa[clave] = n_ref
    for clave in repetidos:
        mapa.pop(clave, None)
    return mapa


def cargar_reconciliacion():
    if not RUTA_RECONCILIACION.exists():
        return {}
    with open(RUTA_RECONCILIACION, "r", encoding="utf-8") as f:
        return json.load(f).get("mapeo", {})


def guardar_reconciliacion(mapeo, ruta=None):
    """Reescribe SOLO la clave 'mapeo' de reconciliacion_archivos.json,
    conservando el resto del archivo (la descripcion y las notas escritas a
    mano, que son la bitacora de por que existe cada entrada)."""
    ruta = Path(ruta or RUTA_RECONCILIACION)
    contenido = {}
    if ruta.exists():
        with open(ruta, "r", encoding="utf-8") as f:
            contenido = json.load(f)
    contenido["mapeo"] = mapeo
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)


# ── CORRECCIONES MANUALES (celda roja -> azul marino, con confirmacion) ────
#
# Flujo (ver Sistema/tests/test_correcciones_manuales.py y
# .claude/skills/Registro_Centro_de_Costos/ERRORES.md):
#   1. 'run' detecta (detectar_correcciones_manuales) comparando el backup mas
#      reciente que YA existia contra el estado actual, y las deja anotadas
#      como "Pendiente" (registrar_correcciones_pendientes) -- no toca el
#      Excel todavia.
#   2. Un comando aparte, 'confirmar', aplica: recolorea azul marino oscuro y
#      propaga a Detalle (confirmar_correcciones). Nunca se aplica solo,
#      sin que alguien lo pida explicitamente.

def backup_mas_reciente(ruta_backups=None):
    """El backup mas reciente que YA existia (por mtime), antes de que esta
    corrida cree el suyo. Es el punto de comparacion para detectar ediciones
    manuales hechas desde la corrida anterior."""
    ruta_backups = ruta_backups or RUTA_BACKUPS
    if not ruta_backups.exists():
        return None
    archivos = list(ruta_backups.rglob("*.xlsx"))
    if not archivos:
        return None
    return max(archivos, key=lambda p: p.stat().st_mtime)


def _mapa_filas_por_n_ref(ws):
    mapa = {}
    for r in range(2, ultima_fila_datos(ws) + 1):
        n_ref = ws.cell(row=r, column=1).value
        if isinstance(n_ref, str) and PATRON_NREF.match(n_ref):
            mapa[n_ref] = r
    return mapa


def _celda_es_roja(cell):
    font = cell.font
    color = font.color.rgb if font and font.color else None
    return isinstance(color, str) and color.upper().endswith(ROJO)


def detectar_correcciones_manuales(wb_anterior, wb_actual):
    """Compara la hoja Master de wb_anterior (backup mas reciente antes de esta
    corrida) contra wb_actual (estado actual, antes de escribir nada nuevo) y
    devuelve las celdas que estaban en rojo en wb_anterior y cambiaron de
    valor -- candidatas a correccion manual. Empareja filas por N Ref, no por
    numero de fila (reordenar_por_fecha puede haber movido las filas)."""
    if "Master" not in wb_anterior.sheetnames or "Master" not in wb_actual.sheetnames:
        return []
    ws_ant = wb_anterior["Master"]
    ws_act = wb_actual["Master"]
    filas_ant = _mapa_filas_por_n_ref(ws_ant)
    filas_act = _mapa_filas_por_n_ref(ws_act)

    detectadas = []
    for n_ref, fila_ant in filas_ant.items():
        fila_act = filas_act.get(n_ref)
        if fila_act is None:
            continue
        for col in range(1, len(ENCABEZADOS_MASTER) + 1):
            cell_ant = ws_ant.cell(row=fila_ant, column=col)
            if not _celda_es_roja(cell_ant):
                continue
            valor_anterior = cell_ant.value
            valor_actual = ws_act.cell(row=fila_act, column=col).value
            if valor_actual in (None, "") or valor_actual == valor_anterior:
                continue
            detectadas.append({
                "n_ref": n_ref, "hoja": "Master", "columna": col,
                "campo": ENCABEZADOS_MASTER[col - 1],
                "valor_anterior": valor_anterior, "valor_corregido": valor_actual,
            })
    return detectadas


def cargar_correcciones_manuales(ruta=None):
    ruta = ruta or RUTA_CORRECCIONES
    if not ruta.exists():
        return []
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_correcciones_manuales(correcciones, ruta=None):
    ruta = ruta or RUTA_CORRECCIONES
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(correcciones, f, ensure_ascii=False, indent=2)


ENCABEZADO_TABLA_CORRECCIONES = "## Correcciones manuales pendientes de recolorear"


def regenerar_tabla_errores_md(correcciones, ruta_errores=None):
    """Reescribe SOLO la tabla bajo ENCABEZADO_TABLA_CORRECCIONES en
    ERRORES.md a partir de correcciones_manuales.json -- es 100% derivada
    (mismo espiritu que los pies de tabla de Master/Detalle), el resto del
    archivo (historial de errores en prosa) no se toca."""
    ruta_errores = ruta_errores or RUTA_ERRORES_MD
    if not ruta_errores.exists():
        return
    texto = ruta_errores.read_text(encoding="utf-8")
    inicio = texto.find(ENCABEZADO_TABLA_CORRECCIONES)
    if inicio == -1:
        return
    resto = texto[inicio + len(ENCABEZADO_TABLA_CORRECCIONES):]
    m = re.search(r"\n## ", resto)
    fin = inicio + len(ENCABEZADO_TABLA_CORRECCIONES) + (m.start() if m else len(resto))

    filas = sorted(correcciones, key=lambda c: (c["fecha_detectado"], c["n_ref"]))
    lineas = [
        "| Fecha | Hoja | N° Ref. | Campo / Columna | Valor anterior (rojo) | Valor corregido | Estado | Nota |",
        "|---|---|---|---|---|---|---|---|",
    ]
    if filas:
        for c in filas:
            estado = c["estado"] if c["estado"] == "Pendiente" else f"Aplicado ({c.get('fecha_aplicado') or ''})"
            lineas.append(
                f"| {c['fecha_detectado']} | {c['hoja']} | {c['n_ref']} | {c['campo']} | "
                f"{c['valor_anterior']} | {c['valor_corregido']} | {estado} | {c.get('nota') or ''} |"
            )
    else:
        lineas.append("| *(sin entradas todavía)* | | | | | | | |")

    nuevo_bloque = ENCABEZADO_TABLA_CORRECCIONES + "\n\n" + "\n".join(lineas) + "\n"
    ruta_errores.write_text(texto[:inicio] + nuevo_bloque + texto[fin:], encoding="utf-8")


def registrar_correcciones_pendientes(detectadas, escribir=True,
                                       ruta_correcciones=None, ruta_errores=None):
    """Fusiona las candidatas detectadas con correcciones_manuales.json:
    - Si no habia entrada para (n_ref, columna): la agrega como "Pendiente".
    - Si ya habia una "Pendiente": actualiza su valor_corregido/fecha (el
      usuario volvio a editar la celda antes de confirmar) -- no duplica.
    - Si ya habia una "Aplicado" con el mismo valor_corregido: la ignora (ya
      se confirmo en una corrida anterior; el backup "anterior" de esta
      corrida todavia puede mostrar la celda en rojo, asi que sin este
      chequeo se re-detectaria como nueva indefinidamente).
    Con escribir=False (usado por 'status', de solo lectura) no toca
    correcciones_manuales.json ni ERRORES.md -- solo devuelve el preview."""
    ruta_correcciones = ruta_correcciones or RUTA_CORRECCIONES
    ruta_errores = ruta_errores or RUTA_ERRORES_MD
    hoy = datetime.now().strftime("%Y-%m-%d")
    correcciones = cargar_correcciones_manuales(ruta_correcciones)
    # .get(): el archivo tambien guarda entradas de bitacora escritas a mano
    # (arreglos que no caen en una sola celda de Master, ya "Aplicado", hoja
    # "Master/Detalle") que no tienen "columna". Nunca colisionan con una
    # candidata detectada -- esas siempre traen columna int -- y ningun otro
    # uso de c["columna"] las alcanza, porque los demas filtran "Pendiente".
    indice = {(c["n_ref"], c.get("columna")): c for c in correcciones}

    pendientes_para_reportar = []
    for d in detectadas:
        clave = (d["n_ref"], d["columna"])
        existente = indice.get(clave)
        if existente is None:
            nueva = {
                "n_ref": d["n_ref"], "hoja": d["hoja"], "columna": d["columna"],
                "campo": d["campo"], "valor_anterior": d["valor_anterior"],
                "valor_corregido": d["valor_corregido"], "estado": "Pendiente",
                "fecha_detectado": hoy, "fecha_aplicado": None,
            }
            correcciones.append(nueva)
            indice[clave] = nueva
            pendientes_para_reportar.append(nueva)
        elif existente["estado"] == "Pendiente":
            if existente["valor_corregido"] != d["valor_corregido"]:
                existente["valor_corregido"] = d["valor_corregido"]
                existente["fecha_detectado"] = hoy
            pendientes_para_reportar.append(existente)
        elif existente["estado"] == "Aplicado" and existente["valor_corregido"] == d["valor_corregido"]:
            continue  # ya confirmada en una corrida anterior, no es nueva

    if escribir:
        guardar_correcciones_manuales(correcciones, ruta_correcciones)
        regenerar_tabla_errores_md(correcciones, ruta_errores)

    return pendientes_para_reportar


def _n_ref_a_filas_detalle(ws_detalle, n_ref):
    return [
        r for r in range(2, ultima_fila_datos(ws_detalle) + 1)
        if ws_detalle.cell(row=r, column=1).value == n_ref
    ]


def _aplicar_correccion_en_libro(ws_master, ws_detalle, fila_m, columna, valor_nuevo,
                                  nota=None):
    """Escribe UNA correccion ya decidida en el libro abierto: normaliza el
    valor si la columna lo exige, lo escribe, recolorea la fuente a azul
    marino oscuro y lo propaga a Detalle si la columna se repite ahi.

    No abre, no respalda y no guarda el libro: eso es responsabilidad de
    quien llama, que es justamente lo que permite aplicar N correcciones con
    una sola apertura. Es el cuerpo comun de confirmar_correcciones() (que ya
    trabajaba por lote) y de corregir_valor_manual() (que lo hacia de a una);
    hasta la auditoria del 2026-09-10 eran dos copias del mismo bloque que
    podian divergir -- de hecho ya divergian en si escribian o no un
    comentario de Excel.

    Devuelve (valor_anterior, valor_aplicado, columna_detalle_o_None).
    """
    cell = ws_master.cell(row=fila_m, column=columna)
    valor_anterior = cell.value
    valor_nuevo = coaccionar_valor_columna(columna, valor_nuevo)

    cell.value = valor_nuevo
    cell.font = AZUL_MARINO_FONT
    if columna == 4 and isinstance(valor_nuevo, datetime):
        cell.number_format = DATE_FORMAT
    elif columna == 12:
        cell.number_format = MONEY_FORMAT
    elif columna == COL_PROVEEDOR_RAZON_SOCIAL_MASTER:
        # El tag corto de la columna 7 es 100% derivado de la razon social: si
        # se corrige una sin la otra, Master queda mostrando el proveedor viejo
        # con la razon social nueva.
        tag = ws_master.cell(row=fila_m, column=COL_PROVEEDOR_TAG_MASTER)
        tag.value = generar_tag_proveedor(valor_nuevo) if valor_nuevo else ""
        tag.font = AZUL_MARINO_FONT
    if nota:
        cell.comment = Comment(nota, "Revision_de_Errores")

    col_detalle = CAMPOS_PROPAGADOS_A_DETALLE.get(columna)
    if col_detalle and ws_detalle is not None:
        for fila_d in _n_ref_a_filas_detalle(ws_detalle, ws_master.cell(row=fila_m, column=1).value):
            ws_detalle.cell(row=fila_d, column=col_detalle, value=valor_nuevo).font = AZUL_MARINO_FONT

    return valor_anterior, valor_nuevo, col_detalle


def confirmar_correcciones(objetivo=None, ruta_excel=None, ruta_correcciones=None,
                            ruta_errores=None, ruta_backups=None):
    """objetivo=None -> preview de solo lectura (no toca el Excel).
    objetivo="TODOS" o lista de N Ref -> aplica: recolorea azul marino
    oscuro en Master (y en Detalle si el campo esta en
    CAMPOS_PROPAGADOS_A_DETALLE) y marca la correccion como "Aplicado"."""
    ruta_excel = ruta_excel or RUTA_EXCEL
    ruta_correcciones = ruta_correcciones or RUTA_CORRECCIONES
    ruta_errores = ruta_errores or RUTA_ERRORES_MD
    ruta_backups = ruta_backups or RUTA_BACKUPS
    correcciones = cargar_correcciones_manuales(ruta_correcciones)
    pendientes = [c for c in correcciones if c["estado"] == "Pendiente"]

    if objetivo is None:
        print(f"\nCorrecciones manuales pendientes de confirmar: {len(pendientes)}")
        for c in pendientes:
            print(f"  - {c['n_ref']} / {c['campo']}: '{c['valor_anterior']}' -> '{c['valor_corregido']}'")
        if pendientes:
            print("\nPara aplicar: python driver.py confirmar --todos"
                  " (o 'python driver.py confirmar <N_REF> ...' para solo algunas)")
        return pendientes

    seleccion = pendientes if objetivo == "TODOS" else [c for c in pendientes if c["n_ref"] in set(objetivo)]
    if not seleccion:
        print("\nNo hay correcciones pendientes que coincidan con lo pedido.")
        return []

    if excel_esta_bloqueado(ruta_excel):
        print("\n[ERROR] El archivo esta abierto en Excel (o bloqueado). Cierralo antes de confirmar.")
        return []

    hacer_backup(ruta_excel, ruta_backups)
    wb = openpyxl.load_workbook(str(ruta_excel), data_only=False)
    ws_master = wb["Master"]
    ws_detalle = wb["Detalle"] if "Detalle" in wb.sheetnames else None
    filas_master = _mapa_filas_por_n_ref(ws_master)

    aplicadas = []
    for c in seleccion:
        fila_m = filas_master.get(c["n_ref"])
        if fila_m is None:
            print(f"  [WARN] {c['n_ref']}: ya no existe en Master, se salta.")
            continue
        cell = ws_master.cell(row=fila_m, column=c["columna"])
        if cell.value != c["valor_corregido"] and str(cell.value) != str(c["valor_corregido"]):
            print(f"  [WARN] {c['n_ref']} / {c['campo']}: el valor cambio de nuevo desde que se "
                  f"detecto ('{cell.value}' != '{c['valor_corregido']}'), se salta -- correr 'run' "
                  f"de nuevo para re-detectarlo.")
            continue

        # El valor se valida arriba contra lo que el usuario escribio tal cual;
        # el helper es quien escribe la version normalizada.
        _, _, col_detalle = _aplicar_correccion_en_libro(
            ws_master, ws_detalle, fila_m, c["columna"], c["valor_corregido"]
        )

        c["estado"] = "Aplicado"
        c["fecha_aplicado"] = datetime.now().strftime("%Y-%m-%d")
        aplicadas.append(c)
        propagado = ", propagado a Detalle" if col_detalle else ""
        print(f"  [OK] {c['n_ref']} / {c['campo']} -> '{c['valor_corregido']}' (azul marino{propagado}).")

    if aplicadas:
        try:
            _guardar_y_suprimir_aviso(wb, ruta_excel)
        except PermissionError:
            print("\n[ERROR] El archivo esta abierto en Excel. Cierralo y vuelve a confirmar.")
            return []
        guardar_correcciones_manuales(correcciones, ruta_correcciones)
        regenerar_tabla_errores_md(correcciones, ruta_errores)

    print(f"\n{len(aplicadas)} correccion(es) aplicada(s).")
    return aplicadas


# ── REVISIÓN GUIADA DE ERRORES (skill Revision_de_Errores) ─────────────────
#
# Camino distinto al de arriba: en vez de que el usuario edite la celda a
# mano en Excel y 'run' la detecte comparando contra el backup anterior, el
# agente recorre las celdas rojas UNA A UNA en la conversacion (mostrando el
# documento origen), pregunta el valor correcto, y lo aplica de inmediato con
# corregir_valor_manual -- mismo resultado final (celda azul marino, propagada
# a Detalle, registrada como "Aplicado" en correcciones_manuales.json y
# ERRORES.md) sin pasar por el estado "Pendiente".

# Unicas columnas de Master que el script pinta de rojo hoy (ver
# escribir_fila_master): N Documento ilegible/"S/N" y IVA que no cuadra con
# el 19% del Neto. Si en el futuro se pinta de rojo otra columna, agregarla
# aqui para que listar_celdas_rojas() la detecte.
COLUMNAS_REVISABLES = (5, 12)


def listar_celdas_rojas(ws_master):
    """Todas las celdas de Master actualmente en rojo (requieren revision),
    sin importar si ya fueron detectadas comparando backups -- es la fuente
    del recorrido guiado de la skill Revision_de_Errores. Una entrada por
    celda roja: {n_ref, fila, columna, campo, valor_actual, proyecto,
    archivo_origen}."""
    encontradas = []
    for r in range(2, ultima_fila_datos(ws_master) + 1):
        n_ref = ws_master.cell(row=r, column=1).value
        if not isinstance(n_ref, str) or not PATRON_NREF.match(n_ref):
            continue
        for col in COLUMNAS_REVISABLES:
            cell = ws_master.cell(row=r, column=col)
            if _celda_es_roja(cell):
                encontradas.append({
                    "n_ref": n_ref, "fila": r, "columna": col,
                    "campo": ENCABEZADOS_MASTER[col - 1],
                    "valor_actual": cell.value,
                    "proyecto": ws_master.cell(row=r, column=2).value,
                    "archivo_origen": ws_master.cell(row=r, column=15).value,
                })
    return encontradas


# Convencion ya usada en el modulo desde CCON-004 (ver MEMORY.md / ERRORES.md):
# cuando una parte de la factura es fisicamente ilegible, esas lineas se
# agrupan en 1 item aparte cuyo nombre incluye la palabra "varios" (ej.
# "Materiales varios"). No hay celda pintada de ningun color para este caso
# (a diferencia de listar_celdas_rojas) -- se detecta por el nombre del item.
PATRON_ITEM_AGRUPADO = re.compile(r"\bvarios\b", re.IGNORECASE)


def listar_items_agrupados(ws_detalle):
    """Filas de Detalle que agrupan en 1 sola linea una parte de la compra
    que no se pudo desglosar item por item (ver PATRON_ITEM_AGRUPADO) -- es
    la fuente de la parte "items agrupados" del recorrido de
    Revision_de_Errores, complementaria a listar_celdas_rojas. Una entrada
    por fila agrupada: {n_ref, fila, proyecto, nombre_item, descripcion,
    cantidad, p_unitario_sin_iva, total_sin_iva}."""
    encontradas = []
    for r in range(2, ultima_fila_datos(ws_detalle) + 1):
        n_ref = ws_detalle.cell(row=r, column=1).value
        if not isinstance(n_ref, str) or not PATRON_NREF.match(n_ref):
            continue
        nombre_item = ws_detalle.cell(row=r, column=5).value
        if isinstance(nombre_item, str) and PATRON_ITEM_AGRUPADO.search(nombre_item):
            encontradas.append({
                "n_ref": n_ref, "fila": r,
                "proyecto": ws_detalle.cell(row=r, column=2).value,
                "nombre_item": nombre_item,
                "descripcion": ws_detalle.cell(row=r, column=6).value,
                "cantidad": ws_detalle.cell(row=r, column=8).value,
                "p_unitario_sin_iva": ws_detalle.cell(row=r, column=9).value,
                "total_sin_iva": ws_detalle.cell(row=r, column=10).value,
            })
    return encontradas


def corregir_valor_manual(n_ref, columna, valor_nuevo, ruta_excel=None,
                           ruta_correcciones=None, ruta_errores=None,
                           ruta_backups=None, nota=None):
    """Aplica UNA correccion manual directa (valor ya confirmado por el
    usuario en la conversacion, no detectado comparando backups): backup,
    escribe valor_nuevo en Master (fila de n_ref, columna dada), recolorea la
    fuente a azul marino oscuro, propaga a Detalle si la columna esta en
    CAMPOS_PROPAGADOS_A_DETALLE, y deja el cambio como "Aplicado" en
    correcciones_manuales.json + ERRORES.md -- mismo destino final que
    confirmar_correcciones(), pero en un solo paso.

    Solo opera sobre celdas actualmente en rojo: si la celda de
    (n_ref, columna) no esta en rojo, no toca nada y devuelve None (evita
    pisar un dato ya bueno por un N Ref o columna equivocados).

    `nota` (opcional): texto libre que queda como comentario de Excel sobre
    la celda corregida en Master (ademas de guardarse en la entrada de
    correcciones_manuales.json / la tabla de ERRORES.md) -- pensado para
    documentar un desglose que no cabe en un solo valor, ej. IVA de compras
    de combustible que incluye IEF/IEV-FEPP ademas del 19% (ver MEMORY.md de
    Registro_Centro_de_Costos)."""
    ruta_excel = ruta_excel or RUTA_EXCEL
    ruta_correcciones = ruta_correcciones or RUTA_CORRECCIONES
    ruta_errores = ruta_errores or RUTA_ERRORES_MD
    ruta_backups = ruta_backups or RUTA_BACKUPS

    if excel_esta_bloqueado(ruta_excel):
        print("\n[ERROR] El archivo esta abierto en Excel (o bloqueado). Cierralo antes de corregir.")
        return None

    wb = openpyxl.load_workbook(str(ruta_excel), data_only=False)
    if "Master" not in wb.sheetnames:
        print("\n[ERROR] No existe la hoja Master.")
        return None
    ws_master = wb["Master"]
    fila_m = _mapa_filas_por_n_ref(ws_master).get(n_ref)
    if fila_m is None:
        print(f"\n[ERROR] {n_ref} no existe en Master.")
        return None

    cell = ws_master.cell(row=fila_m, column=columna)
    if not _celda_es_roja(cell):
        print(f"\n[WARN] {n_ref} / columna {columna} no esta en rojo (no requiere revision); no se toca.")
        return None

    hacer_backup(ruta_excel, ruta_backups)
    ws_detalle = wb["Detalle"] if "Detalle" in wb.sheetnames else None
    valor_anterior, valor_nuevo, col_detalle = _aplicar_correccion_en_libro(
        ws_master, ws_detalle, fila_m, columna, valor_nuevo, nota=nota
    )

    try:
        _guardar_y_suprimir_aviso(wb, ruta_excel)
    except PermissionError:
        print("\n[ERROR] El archivo esta abierto en Excel. Cierralo y vuelve a intentar.")
        return None

    hoy = datetime.now().strftime("%Y-%m-%d")
    campo = ENCABEZADOS_MASTER[columna - 1]
    correcciones = cargar_correcciones_manuales(ruta_correcciones)
    entrada = next((c for c in correcciones if c["n_ref"] == n_ref and c["columna"] == columna), None)
    if entrada is None:
        entrada = {"n_ref": n_ref, "hoja": "Master", "columna": columna, "campo": campo}
        correcciones.append(entrada)
    entrada.update({
        "valor_anterior": valor_anterior, "valor_corregido": valor_nuevo,
        "estado": "Aplicado", "fecha_detectado": entrada.get("fecha_detectado", hoy),
        "fecha_aplicado": hoy,
    })
    if nota:
        entrada["nota"] = nota
    guardar_correcciones_manuales(correcciones, ruta_correcciones)
    regenerar_tabla_errores_md(correcciones, ruta_errores)

    propagado = ", propagado a Detalle" if col_detalle else ""
    print(f"  [OK] {n_ref} / {campo}: '{valor_anterior}' -> '{valor_nuevo}' (azul marino{propagado}).")
    return entrada


def desglosar_item_agrupado(n_ref, items_nuevos, ruta_excel=None, ruta_correcciones=None,
                             ruta_errores=None, ruta_backups=None):
    """Reemplaza la UNICA fila de Detalle 'agrupada' de n_ref (ver
    listar_items_agrupados) por una fila nueva por cada item de
    items_nuevos -- cada uno un dict {"nombre_item", "descripcion",
    "categoria_item", "cantidad", "p_unitario_sin_iva"}, ya confirmado por el
    usuario en la conversacion (misma logica que corregir_valor_manual, pero
    para Detalle en vez de una celda de Master).

    Recalcula "Total sin IVA"/"Total con IVA" de cada fila nueva con la
    misma formula que escribir_items_detalle (tasa real del documento = IVA
    de Master, que no se toca, sobre el Total sin IVA recalculado del
    documento con el desglose nuevo), reconstruye "Resumen Item" en Master
    leyendo Detalle ya actualizado, y regenera el pie de Detalle (la cantidad
    de filas de la hoja cambia salvo que items_nuevos traiga exactamente 1
    elemento). Las filas nuevas quedan en azul marino (valor corregido a
    mano), heredando el relleno de color de proyecto de la fila que
    reemplazan. Excepcion deliberada a la regla de oro de "nunca tocar una
    fila ya escrita" -- mismo tipo de excepcion que corregir_valor_manual.

    Solo actua si encuentra EXACTAMENTE una fila agrupada para n_ref -- si no
    encuentra ninguna, o mas de una, no toca nada y devuelve None (evita
    adivinar cual fila reemplazar; un documento con mas de 1 fila agrupada
    hoy no esta soportado por este comando, se resuelve a mano)."""
    from copy import copy as _copy

    ruta_excel = ruta_excel or RUTA_EXCEL
    ruta_correcciones = ruta_correcciones or RUTA_CORRECCIONES
    ruta_errores = ruta_errores or RUTA_ERRORES_MD
    ruta_backups = ruta_backups or RUTA_BACKUPS

    if excel_esta_bloqueado(ruta_excel):
        print("\n[ERROR] El archivo esta abierto en Excel (o bloqueado). Cierralo antes de desglosar.")
        return None

    wb = openpyxl.load_workbook(str(ruta_excel), data_only=False)
    if "Master" not in wb.sheetnames or "Detalle" not in wb.sheetnames:
        print("\n[ERROR] Faltan hojas Master/Detalle.")
        return None
    ws_master = wb["Master"]
    ws_detalle = wb["Detalle"]

    fila_master = _mapa_filas_por_n_ref(ws_master).get(n_ref)
    if fila_master is None:
        print(f"\n[ERROR] {n_ref} no existe en Master.")
        return None

    agrupados = [f for f in listar_items_agrupados(ws_detalle) if f["n_ref"] == n_ref]
    if len(agrupados) != 1:
        print(f"\n[ERROR] Se esperaba exactamente 1 fila agrupada para {n_ref} en Detalle, "
              f"se encontraron {len(agrupados)}.")
        return None
    fila_vieja = agrupados[0]["fila"]
    nombre_item_anterior = agrupados[0]["nombre_item"]
    descripcion_anterior = agrupados[0]["descripcion"]

    ncols_detalle = len(ENCABEZADOS_DETALLE)
    ultima_detalle = ultima_fila_datos(ws_detalle)
    snapshot_vieja = capturar_fila(ws_detalle, fila_vieja, ncols_detalle)
    fill_proyecto = snapshot_vieja[0]["fill"]  # relleno de color por proyecto, igual en toda la fila
    n_doc_str = ws_detalle.cell(row=fila_vieja, column=4).value
    tipo_proyecto = ws_detalle.cell(row=fila_vieja, column=3).value

    # Total sin IVA del documento CON el desglose nuevo (todas las demas filas
    # de este n_ref, mas los items nuevos) -- para recalcular la tasa real de
    # IVA del documento, igual que escribir_items_detalle.
    total_otros_items = sum(
        (ws_detalle.cell(row=r, column=10).value or 0)
        for r in range(2, ultima_detalle + 1)
        if ws_detalle.cell(row=r, column=1).value == n_ref and r != fila_vieja
    )
    total_items_nuevos = sum(it["cantidad"] * it["p_unitario_sin_iva"] for it in items_nuevos)
    total_sin_iva_doc = total_otros_items + total_items_nuevos

    iva_doc = ws_master.cell(row=fila_master, column=12).value or 0
    tasa_iva_doc = (iva_doc / total_sin_iva_doc) if total_sin_iva_doc else 0

    hacer_backup(ruta_excel, ruta_backups)

    snapshots_todas = [capturar_fila(ws_detalle, r, ncols_detalle) for r in range(2, ultima_detalle + 1)]
    indice_vieja = fila_vieja - 2

    nuevas_filas_snapshot = []
    for item in items_nuevos:
        total_item = item["cantidad"] * item["p_unitario_sin_iva"]
        total_item_con_iva = round(total_item * (1 + tasa_iva_doc))
        valores = [
            n_ref, agrupados[0]["proyecto"], tipo_proyecto, n_doc_str,
            item["nombre_item"], item.get("descripcion", ""), item.get("categoria_item", ""),
            item["cantidad"], item["p_unitario_sin_iva"], total_item, total_item_con_iva,
        ]
        nuevas_filas_snapshot.append([
            {
                "value": v,
                "font": _copy(AZUL_MARINO_FONT),
                "fill": _copy(fill_proyecto),
                "border": _copy(THIN_BORDER),
                "alignment": _copy(snapshot_vieja[c - 1]["alignment"]),
                "number_format": MONEY_FORMAT if c in (9, 10, 11) else "General",
            }
            for c, v in enumerate(valores, 1)
        ])

    filas_finales = (
        snapshots_todas[:indice_vieja] + nuevas_filas_snapshot + snapshots_todas[indice_vieja + 1:]
    )
    for i, snap in enumerate(filas_finales):
        escribir_snapshot_fila(ws_detalle, 2 + i, snap)

    primera_fila_libre_detalle = 2 + len(filas_finales)
    limpiar_pie(ws_detalle)
    regenerar_pie(ws_detalle, ncols_detalle, [10, 11], "TOTAL GENERAL", primera_fila_libre_detalle, LEYENDA_DETALLE)

    # "Resumen Item" en Master: reconstruido leyendo Detalle ya actualizado
    # (no reemplazo de texto) para no depender de que el nombre viejo sea unico.
    nombres_finales = [
        ws_detalle.cell(row=r, column=5).value
        for r in range(2, primera_fila_libre_detalle)
        if ws_detalle.cell(row=r, column=1).value == n_ref
    ]
    ws_master.cell(row=fila_master, column=10, value="; ".join(nombres_finales))

    try:
        _guardar_y_suprimir_aviso(wb, ruta_excel)
    except PermissionError:
        print("\n[ERROR] El archivo esta abierto en Excel. Cierralo y vuelve a intentar.")
        return None

    hoy = datetime.now().strftime("%Y-%m-%d")
    resumen_nuevo = "; ".join(it["nombre_item"] for it in items_nuevos)
    valor_anterior = f"{nombre_item_anterior} ({descripcion_anterior})" if descripcion_anterior else nombre_item_anterior
    correcciones = cargar_correcciones_manuales(ruta_correcciones)
    entrada = {
        "n_ref": n_ref, "hoja": "Detalle", "columna": 5, "campo": "Ítems agrupados (desglose)",
        "valor_anterior": valor_anterior, "valor_corregido": resumen_nuevo,
        "estado": "Aplicado", "fecha_detectado": hoy, "fecha_aplicado": hoy,
    }
    correcciones.append(entrada)
    guardar_correcciones_manuales(correcciones, ruta_correcciones)
    regenerar_tabla_errores_md(correcciones, ruta_errores)

    print(f"  [OK] {n_ref} / Ítems agrupados: '{nombre_item_anterior}' -> "
          f"{len(items_nuevos)} ítem(s) ({resumen_nuevo}) (azul marino).")
    return entrada


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


# Reasignacion de colores por proyecto para la migracion de paleta del
# 2026-07-17 (ver migrar_paleta_colores). Elegida a mano para preservar la
# identidad visual que cada proyecto ya tenia (ej. UMAG se seguia viendo
# rosado antes de la migracion, aunque tapado por el formato condicional
# heredado -- ver Formato Centro de Costos.md SS4/SS9), en vez de reasignar
# en orden alfabetico como hace asignar_colores_proyectos() para proyectos
# nuevos.
REASIGNACION_COLORES_2026_07_17 = {
    "UMAG": "FFB7CE",
    "Cesfam Limache": "89DFFF",
    "Cesfam Constitución": "FFBE9D",
    "Gastos Generales": "B6DFA0",
    "Microturbina LER": "E9CF87",
}


def migrar_paleta_colores(wb, ws_master, ws_detalle):
    """Migracion unica e idempotente (2026-07-17): corrige dos problemas de
    color heredados del pipeline perdido, reportados por el usuario --
    "las hojas no coinciden con el color de las filas, ademas hay proyectos
    con colores demasiado parecidos o los mismos colores":

    1. Master/Detalle tenian 3 reglas de formato condicional heredadas
       (Proyecto = UMAG/Cesfam Limache/Gastos Generales) que pintaban esas
       filas con colores fijos, con prioridad visual sobre el relleno
       directo de celda que sí controla el script -- por eso el color de la
       fila no coincidia con el tabColor de la hoja de ese proyecto. Se
       eliminan: de aqui en adelante el relleno directo (pintar_fila) es la
       unica fuente de color, para cualquier cantidad de proyectos.
    2. La PALETA vieja de 12 pasteles tenia colores casi indistinguibles
       entre si (ej. FCE4D6 vs FBE5D6 vs FDE9D9 -- diferencia de 1 unidad en
       un canal RGB). La PALETA nueva usa 8 tonos espaciados uniformemente
       en el circulo de matices (mismo metodo de color categorico del
       skill dataviz) para que sean distinguibles a simple vista.

    Se detecta si ya corrio revisando si sigue existiendo alguna de las 3
    reglas de formato condicional legado; si no estan, no hace nada."""
    formulas_legado = ('$B2="UMAG"', '$B2="Cesfam Limache"', '$B2="Gastos Generales"')

    def tiene_formato_legado(ws):
        for reglas in ws.conditional_formatting._cf_rules.values():
            for regla in reglas:
                if any(f in str(regla.formula) for f in formulas_legado):
                    return True
        return False

    if not (tiene_formato_legado(ws_master) or tiene_formato_legado(ws_detalle)):
        return

    print("  Migrando colores: quitando formato condicional heredado y repintando con la paleta nueva...")
    from collections import OrderedDict
    ws_master.conditional_formatting._cf_rules = OrderedDict()
    ws_detalle.conditional_formatting._cf_rules = OrderedDict()

    colores = dict(REASIGNACION_COLORES_2026_07_17)
    libres = [c for c in PALETA if c not in colores.values()]

    def color_de(proyecto):
        if proyecto not in colores:
            colores[proyecto] = libres.pop(0) if libres else PALETA[hash(proyecto) % len(PALETA)]
        return colores[proyecto]

    repintadas = 0
    for ws, ncols in ((ws_master, len(ENCABEZADOS_MASTER)), (ws_detalle, len(ENCABEZADOS_DETALLE))):
        ultima = ultima_fila_datos(ws)
        for r in range(2, ultima + 1):
            proyecto = ws.cell(row=r, column=2).value
            if proyecto:
                pintar_fila(ws, r, ncols, color_de(proyecto))
                repintadas += 1

    print(f"  [OK] {repintadas} fila(s) repintada(s) entre Master y Detalle con la paleta nueva.")


def migrar_formato_fecha_corta(ws_master):
    """Migracion de formato (idempotente, 2026-07-17, reformato fijo a DD-MM-AAAA
    2026-07-28): normaliza la columna Fecha (D) de TODAS las filas ya escritas de
    Master al DATE_FORMAT vigente, no solo las filas nuevas -- pedido del usuario.
    Es formato, no contenido: no viola la regla de oro de no tocar filas de datos
    ya escritas (mismo principio que reordenar_por_fecha, que tambien toca solo
    donde/como se ve una fila, nunca su valor). Las hojas de proyecto no necesitan
    esta migracion porque se regeneran completas en cada corrida (ver
    regenerar_hoja_proyecto)."""
    ultima = ultima_fila_datos(ws_master)
    for r in range(2, ultima + 1):
        cell = ws_master.cell(row=r, column=4)
        if cell.number_format != DATE_FORMAT:
            cell.number_format = DATE_FORMAT


def migrar_n_documento_sin_ceros(ws_master, ws_detalle):
    """Migracion idempotente (2026-07-17): la regla 'n_documento no puede empezar
    con 0' (ver MEMORY.md) se agrego a las reglas de negocio del skill pero nunca
    se implemento en el codigo -- documentos como CFLI-001 ('0000130842') y
    UMAG-017 ('0000125796') quedaron registrados con los ceros. Recorre TODAS las
    filas ya escritas de Master (columna E) y Detalle (columna D) y les quita los
    ceros a la izquierda con normalizar_n_documento(), sin tocar font/fill/border
    (incluidas celdas ya corregidas a mano en azul marino -- decision explicita
    del usuario 2026-07-17, es una excepcion deliberada a la regla de oro, igual
    que migrar_columna_proveedor()). Las hojas de proyecto no necesitan tocarse:
    son formulas hacia Master!E, se actualizan solas."""
    corregidas = 0
    ultima_m = ultima_fila_datos(ws_master)
    for r in range(2, ultima_m + 1):
        cell = ws_master.cell(row=r, column=5)
        actual = cell.value
        if isinstance(actual, str):
            nuevo = normalizar_n_documento(actual)
            if nuevo != actual:
                cell.value = nuevo
                corregidas += 1

    ultima_d = ultima_fila_datos(ws_detalle)
    for r in range(2, ultima_d + 1):
        cell = ws_detalle.cell(row=r, column=4)
        actual = cell.value
        if isinstance(actual, str):
            nuevo = normalizar_n_documento(actual)
            if nuevo != actual:
                cell.value = nuevo
                corregidas += 1

    if corregidas:
        print(f"  [OK] {corregidas} celda(s) de N Documento corregida(s): ceros a la izquierda eliminados.")


def migrar_columna_total_con_iva_detalle(ws_master, ws_detalle):
    """Migracion idempotente (2026-07-17): agrega 'Total con IVA (CLP)' como
    ultima columna de Detalle (pedido del usuario) y la rellena para TODAS las
    filas ya escritas -- no solo las nuevas. Se agrega AL FINAL de la hoja
    (columna 11), no en medio, asi que no hace falta desplazar columnas ni
    reescribir formulas existentes (a diferencia de migrar_columna_proveedor).
    Cada fila usa la tasa REAL del documento (IVA de Master columna L / Neto
    sumado desde Detalle columna J), no 19% fijo, para que sirva tambien en
    documentos exentos (pasajes de bus) y de Zona Franca -- misma logica que
    escribir_items_detalle() aplica a filas nuevas. No se lee Master columna K
    (Neto) porque es una formula: openpyxl con data_only=False devuelve el
    texto de la formula, no el numero calculado por Excel; sumar Detalle!J
    directo da el mismo resultado sin depender de que el archivo se haya
    abierto en Excel antes."""
    encabezado_esperado = ENCABEZADOS_DETALLE[10]
    if ws_detalle.cell(row=1, column=11).value == encabezado_esperado:
        return

    print(f"  Migrando Detalle: agregando columna '{encabezado_esperado}'...")
    header_cell = ws_detalle.cell(row=1, column=11, value=encabezado_esperado)
    header_cell.fill = HEADER_FILL
    header_cell.font = HEADER_FONT
    header_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    header_cell.border = THIN_BORDER

    ultima_m = ultima_fila_datos(ws_master)
    iva_por_nref = {
        ws_master.cell(row=r, column=1).value: ws_master.cell(row=r, column=12).value or 0
        for r in range(2, ultima_m + 1)
    }

    ultima_d = ultima_fila_datos(ws_detalle)
    from collections import defaultdict
    from copy import copy as _copy
    neto_por_nref = defaultdict(float)
    for r in range(2, ultima_d + 1):
        n_ref = ws_detalle.cell(row=r, column=1).value
        j = ws_detalle.cell(row=r, column=10).value
        if isinstance(j, (int, float)):
            neto_por_nref[n_ref] += j

    rellenadas = 0
    for r in range(2, ultima_d + 1):
        n_ref = ws_detalle.cell(row=r, column=1).value
        j = ws_detalle.cell(row=r, column=10).value or 0
        neto_doc = neto_por_nref.get(n_ref, 0)
        iva_doc = iva_por_nref.get(n_ref, 0)
        ratio = (iva_doc / neto_doc) if neto_doc else 0
        cell = ws_detalle.cell(row=r, column=11, value=round(j * (1 + ratio)))
        cell.number_format = MONEY_FORMAT
        cell.border = _copy(ws_detalle.cell(row=r, column=10).border)
        cell.font = _copy(ws_detalle.cell(row=r, column=10).font)
        origen_fill = ws_detalle.cell(row=r, column=10).fill
        if origen_fill and origen_fill.patternType:
            cell.fill = _copy(origen_fill)
        rellenadas += 1

    print(f"  [OK] {rellenadas} fila(s) de Detalle con '{encabezado_esperado}' calculado.")


# ── SUPRESION DEL AVISO "NUMERO ALMACENADO COMO TEXTO" (N Documento) ────────
# N Documento se guarda siempre como texto, no como numero (aunque ya no lleve
# ceros a la izquierda desde normalizar_n_documento() -- puede seguir teniendo
# formato "S/N (archivo)" o letras), lo que hace que Excel marque toda la
# columna con el triangulo verde "Numero almacenado como texto". openpyxl no expone
# <ignoredErrors> en su API publica (la clase existe en
# openpyxl.worksheet.errors pero no esta conectada al lector/escritor de
# hojas), asi que hay que inyectar ese XML directo en el .xlsx ya guardado.
# Se debe reaplicar despues de CADA wb.save(): openpyxl descarta este
# elemento (no lo modela) en cualquier ciclo de carga+guardado posterior.

_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
# Elementos de CT_Worksheet que, segun el esquema OOXML, deben ir DESPUES de
# ignoredErrors -- se inserta el bloque justo antes del primero que aparezca
# (o antes de </worksheet> si no hay ninguno) para no corromper el orden.
_TAGS_DESPUES_DE_IGNORED_ERRORS = (
    "<drawing", "<legacyDrawing", "<legacyDrawingHF", "<picture",
    "<oleObjects", "<controls", "<webPublishItems", "<tableParts", "<extLst",
)


def migrar_color_cuadre_impuesto(ws_master, ws_detalle):
    """Repinta la columna de impuesto de Master segun la regla vigente y
    devuelve (limpiadas, marcadas).

    Hace falta una migracion porque el color se escribe una sola vez, cuando
    la fila se crea, y las filas de datos ya escritas no se vuelven a tocar.
    La regla anterior pintaba de rojo cualquier desvio del 19%, asi que el
    libro quedo con 55 celdas rojas de las que la gran mayoria son facturas
    de combustible correctas (IVA + impuesto especifico en un solo campo).
    Ese ruido es lo que recorre '/Revision_de_Errores' uno por uno, y no
    habia nada que corregir en ellas.

    El neto se recalcula sumando la hoja Detalle en vez de leer la columna
    'Total sin IVA' de Master: esa columna es un SUMIF y openpyxl no ve un
    valor cacheado (data_only devuelve None) salvo que Excel haya guardado
    el archivo. Detalle, en cambio, guarda numeros literales.

    Idempotente en los dos sentidos: limpia el rojo que sobra y lo pone donde
    ahora corresponde, asi que correrla de nuevo no cambia nada.
    """
    cols_m = {h: i + 1 for i, h in enumerate(ENCABEZADOS_MASTER)}
    cols_d = {h: i + 1 for i, h in enumerate(ENCABEZADOS_DETALLE)}
    col_total_detalle = cols_d[f"Total sin {NOMBRE_IMPUESTO_CORTO} ({MONEDA})"]
    col_iva_master = cols_m[f"{NOMBRE_IMPUESTO_PCT} ({MONEDA})"]

    neto_por_n_ref = {}
    for fila in range(2, ultima_fila_datos(ws_detalle) + 1):
        n_ref = ws_detalle.cell(row=fila, column=cols_d["N° Ref."]).value
        total = ws_detalle.cell(row=fila, column=col_total_detalle).value
        if not n_ref or not isinstance(total, (int, float)) or isinstance(total, bool):
            continue
        neto_por_n_ref[n_ref] = neto_por_n_ref.get(n_ref, 0) + total

    limpiadas = marcadas = 0
    for fila in range(2, ultima_fila_datos(ws_master) + 1):
        n_ref = ws_master.cell(row=fila, column=cols_m["N° Ref."]).value
        if n_ref not in neto_por_n_ref:
            continue
        celda_iva = ws_master.cell(row=fila, column=col_iva_master)
        iva = celda_iva.value
        if not isinstance(iva, (int, float)) or isinstance(iva, bool):
            continue
        dato = {
            "tipo_documento": ws_master.cell(row=fila, column=cols_m["Tipo Documento"]).value,
            "categoria": ws_master.cell(row=fila, column=cols_m["Categoría"]).value,
            "iva": iva,
        }
        debe_estar_roja = severidad_cuadre_impuesto(dato, neto_por_n_ref[n_ref], iva) == "error"
        esta_roja = _celda_es_roja(celda_iva)
        if esta_roja and not debe_estar_roja:
            celda_iva.font = NORMAL_FONT
            limpiadas += 1
        elif debe_estar_roja and not esta_roja:
            celda_iva.font = ROJO_FONT
            marcadas += 1
    return limpiadas, marcadas


def _hojas_columna_n_documento(wb):
    """N Documento vive en E (col 5) en Master y en las hojas de proyecto, y en
    D (col 4) en Detalle."""
    hojas = {}
    if "Master" in wb.sheetnames:
        hojas["Master"] = "E"
    if "Detalle" in wb.sheetnames:
        hojas["Detalle"] = "D"
    for nombre in wb.sheetnames:
        if nombre not in ("Master", "Detalle", "_Claude"):
            hojas[nombre] = "E"
    return hojas


def _insertar_ignored_errors(xml_hoja, bloque):
    posiciones = [xml_hoja.find(tag) for tag in _TAGS_DESPUES_DE_IGNORED_ERRORS]
    posiciones = [p for p in posiciones if p != -1]
    punto = min(posiciones) if posiciones else xml_hoja.rfind("</worksheet>")
    return xml_hoja[:punto] + bloque + xml_hoja[punto:]


def suprimir_aviso_numero_texto(ruta_excel, hojas_columnas):
    """Post-procesa ruta_excel (ya guardado por openpyxl) para que Excel ignore
    el aviso 'Numero almacenado como texto' en toda la columna de N Documento
    de cada hoja en hojas_columnas (ej. {'Master': 'E', 'Detalle': 'D'})."""
    if not hojas_columnas:
        return

    with zipfile.ZipFile(ruta_excel, "r") as zf:
        infos = zf.infolist()
        contenidos = {n: zf.read(n) for n in zf.namelist()}

    wb_root = ET.fromstring(contenidos["xl/workbook.xml"])
    rels_root = ET.fromstring(contenidos["xl/_rels/workbook.xml.rels"])
    rid_a_target = {rel.get("Id"): rel.get("Target") for rel in rels_root}

    ruta_por_hoja = {}
    for sheet_el in wb_root.find(f"{{{_NS_MAIN}}}sheets"):
        nombre = sheet_el.get("name")
        rid = sheet_el.get(f"{{{_NS_REL}}}id")
        target = rid_a_target.get(rid, "").lstrip("/")
        if target:
            ruta_por_hoja[nombre] = target if target.startswith("xl/") else f"xl/{target}"

    cambiados = {}
    for hoja, col in hojas_columnas.items():
        ruta_hoja = ruta_por_hoja.get(hoja)
        if not ruta_hoja or ruta_hoja not in contenidos:
            continue
        xml_hoja = contenidos[ruta_hoja].decode("utf-8")
        xml_hoja = re.sub(r"<ignoredErrors>.*?</ignoredErrors>", "", xml_hoja, flags=re.DOTALL)
        bloque = (
            f'<ignoredErrors><ignoredError sqref="{col}2:{col}1048576" '
            f'numberStoredAsText="1"/></ignoredErrors>'
        )
        cambiados[ruta_hoja] = _insertar_ignored_errors(xml_hoja, bloque).encode("utf-8")

    if not cambiados:
        return

    ruta_tmp = str(ruta_excel) + ".tmp"
    with zipfile.ZipFile(ruta_tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in infos:
            zout.writestr(info, cambiados.get(info.filename, contenidos[info.filename]))
    shutil.move(ruta_tmp, str(ruta_excel))


def _guardar_y_suprimir_aviso(wb, ruta_excel):
    """Guarda wb en ruta_excel y post-procesa el aviso 'Numero almacenado
    como texto' (suprimir_aviso_numero_texto). Un PermissionError de
    wb.save() (archivo abierto en Excel) se deja propagar tal cual -- cada
    llamador ya lo captura para abortar con un mensaje claro sobre ESE caso.

    La supresion del aviso es puramente cosmetica (Excel abre el archivo
    igual sin ella, solo con el triangulo verde de advertencia en la
    columna) y hace cirugia directa de zip/XML -- a diferencia de wb.save(),
    antes no tenia manejo de errores propio: cualquier falla ahi (zip
    corrupto, XML inesperado, o el mismo PermissionError si OneDrive
    bloquea el archivo un instante para sincronizar justo despues del save)
    quedaba mal atribuida al mensaje de "wb.save() fallo" de cada llamador
    y hacia perder el resultado ya guardado con exito. Ahora se advierte y
    se sigue -- el dato real ya quedo en disco antes de este paso."""
    wb.save(str(ruta_excel))
    try:
        suprimir_aviso_numero_texto(ruta_excel, _hojas_columna_n_documento(wb))
    except Exception as e:
        print(
            f"  [WARN] No se pudo suprimir el aviso 'Numero almacenado como texto' "
            f"({e}). El Excel si quedo guardado correctamente -- Excel solo "
            f"mostrara el triangulo de advertencia en esa columna, sin efecto en "
            f"los datos."
        )


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

def normalizar_nombre_proyecto(nombre_carpeta):
    """Si la carpeta tiene forma 'codigo separador Nombre' (ej. '259. FACH 2',
    '1234_Nombre', '1234-Nombre'), devuelve solo 'Nombre' -- el codigo interno
    (numero de proyecto/cliente) no aporta nada al usuario en dashboards/Excel.
    Ademas, si 'Nombre' termina en 'palabra espacio numero' (ej. 'FACH 2'),
    junta el espacio ('FACH2') -- pedido del usuario 2026-09-03."""
    nombre = re.sub(r"^\d+[.\-_]\s*", "", nombre_carpeta).strip()
    nombre = re.sub(r"^(\S.*\S|\S)\s+(\d+)$", r"\1\2", nombre)
    return nombre or nombre_carpeta


def inventariar_archivos(raiz, archivos_registrados):
    """archivos_registrados: set de 'Proyecto\\archivo.ext' (fisico) ya cubiertos
    (Master + reconciliacion)."""
    pendientes = []
    omitidos = []

    for subdir in sorted(raiz.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith(("_", ".")):
            continue
        # proyecto_fisico = nombre real de la carpeta -- se usa SOLO para ubicar
        # el archivo en disco (ruta_relativa/Archivo origen), nunca para mostrar.
        # proyecto = nombre normalizado (sin codigo) -- va a Master/Detalle/JSON.
        # Mismo split que resolver_ruta_actual() ya hacia por el motivo opuesto
        # (bootstrap con Archivo origen desactualizado): la ruta fisica y el
        # nombre mostrado no tienen por que coincidir.
        proyecto_fisico = subdir.name
        proyecto = normalizar_nombre_proyecto(proyecto_fisico)

        for archivo in sorted(subdir.iterdir()):
            if not archivo.is_file():
                continue
            ext = archivo.suffix.lower()
            if ext in EXTENSIONES_IGNORAR or archivo.name == "desktop.ini":
                continue
            if ext not in EXTENSIONES_VALIDAS:
                continue

            ruta_rel = f"{proyecto_fisico}\\{archivo.name}"
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


# ── SEPARACIÓN DE DOCUMENTOS COMBINADOS (varias facturas/boletas en 1 archivo) ──

def separar_documento_combinado(proyecto_fisico, archivo, cantidad, raiz_docs=None, ruta_backups=None):
    """Cuando una foto/PDF pendiente trae mas de 1 documento tributario distinto
    en el mismo encuadre (ej. 2-3 boletas fotografiadas juntas), genera 'cantidad'
    copias identicas de ese archivo -- '<nombre>_1.<ext>', '<nombre>_2.<ext>', ...
    -- para que cada una se registre como documento independiente en el siguiente
    'run' (el emparejamiento con datos_extraidos.json es por (proyecto, archivo)
    exacto, asi que basta con que cada copia tenga una entrada propia en el JSON).
    Mismo sufijo numerico ya documentado como regla de negocio en MEMORY.md del
    skill (pedido 2026-08-18) -- esta funcion formaliza en codigo (con tests) lo
    que antes era un paso manual del agente.

    Se duplica sin recortar -- pedido explicito del usuario, 2026-09-08: cada
    copia conserva el archivo completo (todas las facturas visibles), nunca se
    intenta aislar visualmente cada una. El archivo original se respalda en
    Excel/Respaldos/<Mes Año>/ (mismo patron que hacer_backup) y se borra de la
    carpeta compartida -- si no, quedaria "pendiente sin datos en el JSON" para
    siempre, porque ningun archivo nuevo se llamara igual que el original.

    Aborta sin tocar nada si el original no existe o si ya existe algun archivo
    destino (mismo nombre '_N'), para no pisar un documento ya separado antes."""
    raiz_docs = raiz_docs if raiz_docs is not None else RAIZ_DOCS
    ruta_backups = ruta_backups if ruta_backups is not None else RUTA_BACKUPS
    if cantidad < 2:
        raise ValueError(f"cantidad debe ser 2 o mas (recibido: {cantidad})")

    carpeta = raiz_docs / proyecto_fisico
    ruta_original = carpeta / archivo
    if not ruta_original.exists():
        raise FileNotFoundError(f"No existe el documento a separar: {ruta_original}")

    stem = ruta_original.stem
    ext = ruta_original.suffix
    destinos = [carpeta / f"{stem}_{n}{ext}" for n in range(1, cantidad + 1)]
    ya_existentes = [d for d in destinos if d.exists()]
    if ya_existentes:
        nombres = ", ".join(d.name for d in ya_existentes)
        raise FileExistsError(f"Ya existe(n) archivo(s) destino: {nombres}")

    for destino in destinos:
        shutil.copy2(ruta_original, destino)

    ahora = datetime.now()
    carpeta_respaldo = carpeta_mes(ruta_backups, ahora)
    marca = ahora.strftime("%Y-%m-%d %H%M")
    respaldo = carpeta_respaldo / f"{stem} - documento combinado - backup {marca}{ext}"
    shutil.copy2(ruta_original, respaldo)
    ruta_original.unlink()

    return destinos


def eliminar_documento(n_ref, ws_master, ws_detalle, raiz_docs=None, ruta_backups=None,
                       archivar_fuente=True):
    """Borra del libro un documento registrado por error (t�picamente el mismo
    documento tributario registrado dos veces desde dos escaneos distintos) y
    devuelve un resumen de lo que se saco.

    Es la unica operacion del modulo que borra una fila de datos ya escrita, y
    existe porque la alternativa es peor: un documento duplicado suma dos veces
    su costo en el proyecto, en los KPIs de Analisis Financiero y en el indice
    de precios del Cotizador, y ninguna de las tres cosas se puede corregir a
    mano sin desalinear las otras.

    Tres cosas, en este orden:
      1. Borra las filas de Detalle de ese N Ref (los items).
      2. Borra su fila de Master.
      3. Archiva el archivo fuente en Excel/Respaldos/<Mes Año>/ y lo saca de
         la carpeta compartida. Este paso NO es opcional en la practica: si el
         archivo se queda, el proximo 'run' lo ve como pendiente y lo vuelve a
         registrar con un N Ref nuevo, reponiendo el duplicado.

    NO renumera los N Ref que quedan: el numero es historico y una fila
    posterior puede estar referenciada en correcciones, notas o respaldos. Queda
    un hueco en la secuencia, que es lo correcto.

    Quien llama es responsable de haber hecho backup, de regenerar los pies y
    las hojas de proyecto, y de guardar el libro."""
    raiz_docs = raiz_docs if raiz_docs is not None else RAIZ_DOCS
    ruta_backups = ruta_backups if ruta_backups is not None else RUTA_BACKUPS

    filas_master = _mapa_filas_por_n_ref(ws_master)
    if n_ref not in filas_master:
        raise ValueError(f"No existe el documento {n_ref!r} en Master.")
    fila_master = filas_master[n_ref]

    archivo_origen = ws_master.cell(row=fila_master, column=15).value
    proyecto = ws_master.cell(row=fila_master, column=2).value

    filas_detalle = sorted(_n_ref_a_filas_detalle(ws_detalle, n_ref), reverse=True)
    for fila in filas_detalle:
        ws_detalle.delete_rows(fila)
    ws_master.delete_rows(fila_master)

    ruta_archivada = None
    if archivar_fuente and archivo_origen:
        # 'Archivo origen' guarda '<carpeta fisica>\<nombre>'.
        relativo = str(archivo_origen).replace("\\", "/")
        ruta_fuente = raiz_docs / relativo
        if ruta_fuente.exists():
            ahora = datetime.now()
            destino_dir = carpeta_mes(ruta_backups, ahora)
            marca = ahora.strftime("%Y-%m-%d %H%M")
            ruta_archivada = destino_dir / (
                f"{ruta_fuente.stem} - eliminado {n_ref} - {marca}{ruta_fuente.suffix}"
            )
            shutil.move(str(ruta_fuente), str(ruta_archivada))

    return {
        "n_ref": n_ref,
        "proyecto": proyecto,
        "archivo_origen": archivo_origen,
        "items_borrados": len(filas_detalle),
        "archivo_archivado": ruta_archivada,
    }


def ejecutar_eliminacion(n_refs, ruta_excel=None, aplicar=False):
    """Orquesta la eliminacion de uno o varios documentos: backup, borrado,
    regeneracion de todo lo derivado y guardado. Con aplicar=False no escribe
    nada y solo describe lo que haria -- es el modo por defecto a proposito,
    porque esto saca plata de la contabilidad.

    Devuelve la lista de resumenes de eliminar_documento()."""
    ruta_excel = ruta_excel if ruta_excel is not None else RUTA_EXCEL
    wb = openpyxl.load_workbook(str(ruta_excel), data_only=False)
    ws_master, ws_detalle = wb["Master"], wb["Detalle"]

    # Previsualizacion: que se sacaria, con su monto, antes de tocar nada.
    filas = _mapa_filas_por_n_ref(ws_master)
    faltantes = [r for r in n_refs if r not in filas]
    if faltantes:
        raise ValueError(f"No estan en Master: {', '.join(faltantes)}")

    previos = []
    for n_ref in n_refs:
        fila = filas[n_ref]
        neto = sum(
            ws_detalle.cell(row=f, column=10).value or 0
            for f in _n_ref_a_filas_detalle(ws_detalle, n_ref)
        )
        previos.append({
            "n_ref": n_ref,
            "proyecto": ws_master.cell(row=fila, column=2).value,
            "n_documento": ws_master.cell(row=fila, column=5).value,
            "proveedor": ws_master.cell(row=fila, column=8).value,
            "fecha": ws_master.cell(row=fila, column=4).value,
            "neto": neto,
            "impuesto": ws_master.cell(row=fila, column=12).value,
        })

    if not aplicar:
        wb.close()
        return previos, []

    hacer_backup(ruta_excel, ruta_backups=RUTA_BACKUPS)

    resultados = []
    for n_ref in n_refs:
        resultados.append(eliminar_documento(n_ref, ws_master, ws_detalle))

    # Todo lo derivado se regenera igual que en PASO 7-9 de main(): pies,
    # orden por fecha y hojas de proyecto. Sin esto el libro queda con totales
    # que no cuadran con sus propias filas y con hojas de proyecto que siguen
    # listando el documento borrado.
    limpiar_pie(ws_detalle)
    limpiar_pie(ws_master)
    fila_master = ultima_fila_datos(ws_master) + 1
    fila_detalle = ultima_fila_datos(ws_detalle) + 1
    reordenar_por_fecha(ws_master, ws_detalle, fila_master, fila_detalle)
    regenerar_pie(ws_detalle, len(ENCABEZADOS_DETALLE), [10, 11],
                  "TOTAL GENERAL", fila_detalle, LEYENDA_DETALLE)
    regenerar_pie(ws_master, len(ENCABEZADOS_MASTER), [11, 12, 13],
                  "TOTAL GENERAL", fila_master, LEYENDA_MASTER)

    ultima_master = fila_master - 1
    proyectos = sorted({r["proyecto"] for r in previos if r["proyecto"]})
    colores = asignar_colores_proyectos(wb, proyectos)
    for proyecto in proyectos:
        filas_de_este_proyecto = [
            r for r in range(2, ultima_master + 1)
            if ws_master.cell(row=r, column=2).value == proyecto
        ]
        if not filas_de_este_proyecto:
            continue
        regenerar_hoja_proyecto(wb, proyecto, filas_de_este_proyecto, colores.get(proyecto))

    _guardar_y_suprimir_aviso(wb, ruta_excel)
    reflejar_a_sitio_comunicacion(ruta_excel=ruta_excel)
    return previos, resultados


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


# Marcadores de "este documento no trae numero": los peajes se registran con
# 'N/A' y las boletas ilegibles con 'S/N (archivo)'. NO son numeros de
# documento, y compararlos entre si convertia cada peaje en "posible
# duplicado" del peaje anterior -- 172 de las 660 entradas del JSON son 'N/A',
# y por eso la corrida del 2026-09-09 emitio 48 avisos de duplicado de los que
# 47 eran peajes distintos.
PLACEHOLDERS_N_DOCUMENTO = frozenset({"", "N/A", "NA", "NONE", "SIN NUMERO", "SIN NÚMERO"})


def es_n_documento_real(valor):
    """False si el 'numero' es solo un marcador de que el documento no lo
    trae. Solo los numeros reales sirven para detectar duplicados."""
    s = str(valor or "").strip().upper()
    return bool(s) and s not in PLACEHOLDERS_N_DOCUMENTO and not s.startswith("S/N")


def normalizar_n_documento(valor):
    """Quita los ceros a la izquierda de un N Documento (pedido 2026-07-17,
    ver MEMORY.md 'Reglas de negocio'): '0000130020' -> '130020'. No toca
    valores que no empiecen con un digito '0' (ej. 'S/N (IMG_1234)'). Si el
    valor es solo ceros (caso extremo, no deberia pasar en la practica), deja
    un solo '0' en vez de vaciar la celda."""
    s = str(valor)
    despojado = s.lstrip("0")
    return despojado if despojado else (s[-1:] if s else s)


def calcular_iva_documento(dato, total_sin_iva):
    """Logica compartida para el IVA a nivel documento: usa el valor explicito
    del JSON si viene, si no calcula 19% del Neto para Factura/Guia de
    Despacho (0 para el resto). La usan tanto escribir_fila_master (columna L
    de Master) como escribir_items_detalle (para prorratear 'Total con IVA'
    por item en Detalle), asi ambas hojas quedan siempre consistentes entre si."""
    iva = dato.get("iva")
    if iva is None:
        iva = (
            round(total_sin_iva * TASA_IMPUESTO)
            if es_documento_afecto(dato.get("tipo_documento")) else 0
        )
    return iva


# ── ESCRITURA: DOCUMENTOS NUEVOS ────────────────────────────────────────────

def escribir_items_detalle(ws_detalle, fila_inicio, n_ref, dato, color):
    n_doc_str = normalizar_n_documento(dato["n_documento"])
    total_sin_iva_doc = total_sin_iva_items(dato["items"])
    iva_doc = calcular_iva_documento(dato, total_sin_iva_doc)
    # Tasa real del documento (IVA / Neto), no 19% fijo -- para que sirva tambien en
    # documentos exentos (pasajes de bus) y de Zona Franca (0%), y para que la suma de
    # "Total con IVA" de Detalle por N Ref coincida siempre con Master (pedido 2026-07-17).
    tasa_iva_doc = (iva_doc / total_sin_iva_doc) if total_sin_iva_doc else 0

    fila = fila_inicio
    for item in dato["items"]:
        total_item = item["cantidad"] * item["p_unitario_sin_iva"]
        total_item_con_iva = round(total_item * (1 + tasa_iva_doc))
        valores = [
            n_ref, dato["proyecto"], dato.get("tipo_proyecto", ""), n_doc_str,
            item["nombre_item"], item.get("descripcion", ""), item.get("categoria_item", ""),
            item["cantidad"], item["p_unitario_sin_iva"], total_item, total_item_con_iva,
        ]
        for c, v in enumerate(valores, 1):
            cell = ws_detalle.cell(row=fila, column=c, value=v)
            cell.font = NORMAL_FONT
            cell.border = THIN_BORDER
        ws_detalle.cell(row=fila, column=9).number_format = MONEY_FORMAT
        ws_detalle.cell(row=fila, column=10).number_format = MONEY_FORMAT
        ws_detalle.cell(row=fila, column=11).number_format = MONEY_FORMAT
        if color:
            pintar_fila(ws_detalle, fila, len(ENCABEZADOS_DETALLE), color)
        fila += 1
    return fila


def celda_requiere_revision(valor):
    return isinstance(valor, str) and ("S/N" in valor.upper() or "SIN_NUMERO" in valor.upper())


def escribir_fila_master(ws_master, fila, n_ref, dato, info_archivo, color):
    resumen_items = "; ".join(it["nombre_item"] for it in dato["items"])
    total_sin_iva = total_sin_iva_items(dato["items"])
    iva = calcular_iva_documento(dato, total_sin_iva)

    fecha_val = dato.get("fecha", "")
    for formato in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            fecha_val = datetime.strptime(dato["fecha"], formato)
            break
        except (ValueError, KeyError):
            continue

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

    n_doc_str = normalizar_n_documento(dato["n_documento"])
    ws_master.cell(row=fila, column=5, value=n_doc_str)
    if celda_requiere_revision(n_doc_str):
        ws_master.cell(row=fila, column=5).font = ROJO_FONT

    if isinstance(fecha_val, datetime):
        ws_master.cell(row=fila, column=4).number_format = DATE_FORMAT

    escribir_formulas_master(ws_master, fila)

    iva_cell = ws_master.cell(row=fila, column=12)
    iva_cell.number_format = MONEY_FORMAT
    # Rojo = "hay algo que corregir aca". Solo se pinta cuando el impuesto es
    # MENOR al que corresponde por ley, que es imposible en un documento
    # afecto. Un impuesto MAYOR al 19% es lo normal en combustibles (IEC +
    # FEPP) y pintarlo dejaba 55 celdas rojas permanentes que nadie iba a
    # corregir nunca -- ruido que enterraba las que si importan.
    if severidad_cuadre_impuesto(dato, total_sin_iva, iva) == "error":
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


# ── REORDENAR POR FECHA (mas reciente arriba) ───────────────────────────────
# Master/Detalle se muestran con el documento mas reciente en la fila 2 y el
# mas antiguo al fondo de la tabla (pedido del usuario 2026-07-17). Es una
# excepcion deliberada a "nunca tocar una fila de datos ya escrita" -- igual
# que migrar_columna_proveedor()/aplicar_renombrados(): el CONTENIDO de cada
# fila (valores, colores, fuentes, correcciones a mano) no cambia, solo su
# POSICION. Corre en cada run (incluso sin documentos nuevos), porque agregar
# hoy un documento con fecha antigua debe intercalarlo en su lugar, no solo
# agregarlo al final.

def capturar_fila(ws, fila, ncols):
    """Snapshot de una fila completa (valores + estilo) para poder reubicarla
    a otra fila sin perder formato manual (fuente, color, borde, formato).
    cell.font/fill/border/alignment devuelven un StyleProxy de solo lectura
    (no un Font/PatternFill real) -- copy.copy() lo desenvuelve a un objeto
    de estilo real que si se puede reasignar a otra celda."""
    from copy import copy as _copy
    return [
        {
            "value": ws.cell(row=fila, column=c).value,
            "number_format": ws.cell(row=fila, column=c).number_format,
            "font": _copy(ws.cell(row=fila, column=c).font),
            "fill": _copy(ws.cell(row=fila, column=c).fill),
            "border": _copy(ws.cell(row=fila, column=c).border),
            "alignment": _copy(ws.cell(row=fila, column=c).alignment),
        }
        for c in range(1, ncols + 1)
    ]


def escribir_snapshot_fila(ws, fila, snapshot):
    for c, datos in enumerate(snapshot, 1):
        cell = ws.cell(row=fila, column=c)
        cell.value = datos["value"]
        cell.number_format = datos["number_format"]
        cell.font = datos["font"]
        cell.fill = datos["fill"]
        cell.border = datos["border"]
        cell.alignment = datos["alignment"]


def _clave_orden_fecha(info):
    """info = (indice_original, fila, n_ref, fecha). Mas reciente primero;
    fechas no interpretables (string/vacio) van al final, en su orden original."""
    idx, _fila, _n_ref, fecha = info
    if isinstance(fecha, datetime):
        return (0, -fecha.timestamp(), idx)
    return (1, 0, idx)


def reordenar_por_fecha(ws_master, ws_detalle, primera_fila_libre_master, primera_fila_libre_detalle):
    """Reordena las filas de datos de Master (fila 2 = fecha mas reciente,
    fondo = mas antigua) y reagrupa los bloques de items de Detalle que le
    corresponden a cada N Ref siguiendo ese mismo orden. No modifica
    valor/formato de ninguna celda, solo la fila donde vive -- ver nota de la
    seccion. Las formulas K/M de Master (que referencian su propia fila, ej.
    $A15) se regeneran para apuntar a la fila nueva; los valores fijos
    (corregidos a mano) se preservan tal cual."""
    ultima_master = primera_fila_libre_master - 1
    if ultima_master < 2:
        return

    ncols_master = len(ENCABEZADOS_MASTER)
    info_filas = [
        (idx, r, ws_master.cell(row=r, column=1).value, ws_master.cell(row=r, column=4).value)
        for idx, r in enumerate(range(2, ultima_master + 1))
    ]
    orden = sorted(info_filas, key=_clave_orden_fecha)
    filas_origen = [f[1] for f in orden]

    if filas_origen == list(range(2, ultima_master + 1)):
        return  # ya esta en el orden correcto, no tocar nada

    snapshots_master = [capturar_fila(ws_master, r, ncols_master) for r in filas_origen]
    for i, snap in enumerate(snapshots_master):
        escribir_snapshot_fila(ws_master, 2 + i, snap)
        escribir_formulas_master(ws_master, 2 + i)  # ajusta $A<fila> de K/M a la nueva posicion

    n_ref_orden = [ws_master.cell(row=2 + i, column=1).value for i in range(len(snapshots_master))]

    ultima_detalle = primera_fila_libre_detalle - 1
    if ultima_detalle < 2:
        return

    ncols_detalle = len(ENCABEZADOS_DETALLE)
    grupos = {}
    orden_original_grupos = []
    for r in range(2, ultima_detalle + 1):
        n_ref_d = ws_detalle.cell(row=r, column=1).value
        if n_ref_d not in grupos:
            grupos[n_ref_d] = []
            orden_original_grupos.append(n_ref_d)
        grupos[n_ref_d].append(capturar_fila(ws_detalle, r, ncols_detalle))

    fila = 2
    vistos = set()
    for n_ref in n_ref_orden + orden_original_grupos:
        if n_ref in vistos:
            continue
        vistos.add(n_ref)
        for snap in grupos.get(n_ref, []):
            escribir_snapshot_fila(ws_detalle, fila, snap)
            fila += 1


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
    de proyecto. El nombre/pestaña de la hoja es el PREFIJO del proyecto (ej. "Cesfam
    Limache" -> "CFLI"), no el nombre completo -- pedido del usuario 2026-07-17, para
    que las pestañas del Excel sean compactas. El nombre completo solo se usa para
    contenido dentro de la hoja (ej. el rótulo "TOTAL <proyecto>" del pie). Si la hoja
    ya existe, se reutiliza el mismo objeto de hoja en vez de borrarla y recrearla --
    borrar+recrear tiraba tambien columnas ocultas, anchos manuales, autofiltro,
    freeze panes y validaciones de datos que el usuario haya dejado en esa hoja. Solo
    se borran las filas de datos/pie/leyenda (fila 2 en adelante); el encabezado (fila
    1) y todo el formato a nivel de columna/hoja quedan intactos."""
    nombre_hoja = prefijo_para_proyecto(proyecto)
    if nombre_hoja in wb.sheetnames:
        ws = wb[nombre_hoja]
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row - 1)
    else:
        ws = wb.create_sheet(title=nombre_hoja, index=len(wb.sheetnames))

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
        ws.cell(row=fila, column=4).number_format = DATE_FORMAT
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

def severidad_cuadre_impuesto(dato, total_sin_iva, iva):
    """Clasifica el cuadre "Neto vs impuesto declarado" de UN documento.
    Devuelve None si cuadra o si no aplica, o una de tres severidades.

    Por que hay severidades y no una lista plana (auditoria 2026-09-09): la
    version anterior emitia 100 alertas sobre datos_extraidos.json y 73 eran
    documentos CORRECTOS. Son facturas de combustible: en Chile el precio
    pagado lleva IVA 19% MAS impuesto especifico (IEC) y FEPP, y el campo
    'iva' agrupa los tres a proposito para que Neto + iva sea el total
    realmente pagado (las notas de esos documentos lo dicen explicitamente).
    Reportarlas como error en cada corrida enterraba las 27 que si lo son y
    dejaba 55 celdas de IVA pintadas de rojo que nadie iba a corregir nunca.

      'error'    -> el impuesto es MENOR al IVA legal. Imposible en un
                    documento afecto: o los items estan sobrevalorados, o el
                    impuesto quedo mal leido. Siempre hay algo que corregir.
      'revisar'  -> el impuesto EXCEDE el 19% en una categoria que no tiene
                    impuesto especifico conocido. Puede ser legitimo (un
                    tributo que no habiamos visto) o un error de lectura; no
                    se puede afirmar sin mirar el documento.
      'estimado' -> documento afecto SIN campo 'iva': se le calcula 19%.
                    Correcto para la mayoria, pero subestima el total pagado
                    si el documento lleva impuesto especifico.

    El exceso ya explicado por la categoria (combustible) no se reporta: es
    el comportamiento esperado, no un hallazgo.
    """
    if not es_documento_afecto(dato.get("tipo_documento")) or total_sin_iva <= 0:
        return None

    categoria = clave_tipo_documento(dato.get("categoria"))
    tiene_impuesto_especifico = categoria in CATEGORIAS_CON_IMPUESTO_ESPECIFICO

    if dato.get("iva") is None:
        # Se le va a calcular 19% aunque el documento pueda llevar mas.
        return "estimado" if tiene_impuesto_especifico else None

    esperado = round(total_sin_iva * TASA_IMPUESTO)

    # Si el documento DECLARA cuanto de su impuesto no es IVA, el cuadre deja
    # de ser una heuristica por categoria y pasa a ser exacto: no hace falta
    # adivinar si un exceso se explica o no. Es la forma preferida de
    # registrar un combustible (IEC + FEPP) o cualquier tributo adicional.
    otros = dato.get("otros_impuestos")
    if otros is not None:
        if abs(iva - (esperado + otros)) <= TOLERANCIA_IMPUESTO:
            return None
        return "error" if iva < esperado + otros else "revisar"

    if iva < esperado - TOLERANCIA_IMPUESTO:
        return "error"
    if iva > esperado + TOLERANCIA_IMPUESTO and not tiene_impuesto_especifico:
        return "revisar"
    return None


def verificar_aritmetica(datos):
    """Cuadra el impuesto de cada documento contra el 19% del neto y devuelve
    los hallazgos con severidad (ver severidad_cuadre_impuesto). Ordenados
    con los 'error' primero: son los unicos donde hay algo seguro que
    corregir."""
    hallazgos = []
    for d in datos:
        total_sin_iva = total_sin_iva_items(d["items"])
        iva = calcular_iva_documento(d, total_sin_iva)
        severidad = severidad_cuadre_impuesto(d, total_sin_iva, iva)
        if severidad is None:
            continue
        hallazgos.append({
            "severidad": severidad,
            "archivo": d["archivo"], "n_documento": d["n_documento"],
            "categoria": d.get("categoria", ""),
            "neto": total_sin_iva,
            "iva": d.get("iva"),
            "iva_esperado": round(total_sin_iva * TASA_IMPUESTO),
            "nota": d.get("notas", ""),
        })
    orden = {"error": 0, "revisar": 1, "estimado": 2}
    hallazgos.sort(key=lambda h: orden[h["severidad"]])
    return hallazgos


# ── TAXONOMÍA DE ERRORES Y VALIDACIÓN TEMPRANA ──────────────────────────────
#
# Antes de esto (auditoria 2026-09-10) la deteccion de errores estaba repartida
# en cuatro sitios de main() y no dejaba rastro: 'limitaciones' y
# 'alertas_legibilidad' se armaban DENTRO del bucle de escritura (PASO 6),
# 'posibles_duplicados' tambien, y el cuadre de impuesto corria en PASO 13,
# DESPUES de guardar el libro (PASO 12), de reflejarlo al sitio compartido
# (12b), de regenerar el visualizador (12c) y de recalcular Analisis
# Financiero (12d). Consecuencias medidas:
#
#   * un documento con impuesto mal leido se publicaba en tres destinos antes
#     de que nadie lo mirara;
#   * si el Excel estaba bloqueado, main() hacia 'return' antes del PASO 13 y
#     la corrida terminaba SIN informe: todo el trabajo de deteccion se perdia;
#   * los hallazgos solo existian como texto en consola, asi que no habia forma
#     de cerrarlos, priorizarlos ni evitar que se re-emitieran identicos en
#     cada corrida (35 descuadres reales se reimprimian indefinidamente);
#   * clases enteras de error no se miraban nunca: cantidad <= 0, documento de
#     compra con neto negativo (el precedente real "Signo de IVA / P.Unitario /
#     Totales (AYRSA)" de ERRORES.md), nota de credito con signo o impuesto
#     incoherente, tipo de documento fuera del vocabulario (que ademas quedaba
#     silenciosamente exento), fecha ilegible o futura, proveedor/categoria en
#     blanco.
#
# validar_documento() concentra todos esos chequeos en una sola funcion pura,
# que corre ANTES de escribir nada, y devuelve hallazgos tipados con causa,
# contexto, accion recomendada e impacto en pesos.

# codigo -> (severidad, titulo, accion recomendada, columna de Master corregible)
#
# severidad, de mas a menos accionable (mismo vocabulario que
# severidad_cuadre_impuesto, para no inventar un segundo eje):
#   'error'    -> hay algo seguro que corregir; el dato de hoy no puede ser bueno.
#   'revisar'  -> puede ser legitimo o no; hay que mirar el documento.
#   'estimado' -> el dato se completo con un supuesto; conviene verificarlo.
#
# La columna es la de Master donde vive el valor a corregir, o None si el
# hallazgo no se arregla escribiendo una celda (falta una entrada del JSON,
# hay que desglosar items, hay que borrar un documento entero...).
TAXONOMIA_ERRORES = {
    "DOC_SIN_DATOS": (
        "error", "Documento sin entrada en el JSON",
        "Agregar la entrada (con 'items') a datos_extraidos.json y volver a correr.", None),
    "DOC_SIN_ITEMS": (
        "error", "Entrada del JSON sin items",
        "Agregar al menos un item con nombre_item/cantidad/p_unitario_sin_iva.", None),
    "DOC_NETO_NO_POSITIVO": (
        "error", "Documento de compra con neto <= 0",
        "Revisar el signo de los precios: una compra no puede costar cero o menos "
        "(precedente 'Signo de IVA / P.Unitario / Totales' en ERRORES.md).", None),
    "ITEM_CANTIDAD_INVALIDA": (
        "error", "Item con cantidad <= 0",
        "Corregir la cantidad en datos_extraidos.json: un item con cantidad 0 no "
        "aporta al total y descuadra el neto del documento.", None),
    "NC_SIGNO": (
        "error", "Nota de credito con neto positivo",
        "Una nota de credito revierte una compra: sus items van en negativo. "
        "Invertir el signo en datos_extraidos.json.", None),
    "NC_IMPUESTO_DESCUADRADO": (
        "error", "Nota de credito con impuesto que no cuadra",
        "Verificar el impuesto impreso en la nota de credito y corregirlo.", 12),
    "TIPO_DOC_DESCONOCIDO": (
        "revisar", "Tipo de documento fuera del vocabulario conocido",
        "Confirmar si es un documento afecto (Factura/Guia de Despacho) o exento: "
        "hoy se le calcula impuesto 0 sin avisar.", 6),
    "FECHA_INVALIDA": (
        "error", "Fecha no interpretable",
        "Corregir la fecha a DD-MM-AAAA: una fecha no interpretable se escribe como "
        "texto y deja el documento al final del orden cronologico.", 4),
    "FECHA_FUTURA": (
        "revisar", "Fecha posterior a hoy",
        "Confirmar la fecha contra el documento: una compra no puede estar fechada "
        "en el futuro.", 4),
    "PROVEEDOR_VACIO": (
        "revisar", "Documento sin proveedor",
        "Completar la razon social del proveedor (revisar antes si ya existe uno con "
        "el mismo RUT, ver MEMORY.md).", 8),
    "CATEGORIA_VACIA": (
        "revisar", "Documento sin categoria",
        "Asignar la categoria del documento: sin ella no entra en ningun corte por "
        "categoria de Analisis Financiero.", 9),
    "N_DOC_ILEGIBLE": (
        "revisar", "N Documento ilegible",
        "Leer el numero en la foto del documento y corregirlo.", 5),
    "IMPUESTO_MENOR": (
        "error", "Impuesto declarado menor al que corresponde",
        "Imposible en un documento afecto: revisar el impuesto impreso o el precio "
        "de los items.", 12),
    "IMPUESTO_EXCESO": (
        "revisar", "Impuesto sobre el 19% sin impuesto especifico conocido",
        "Mirar el documento: si lleva un tributo adicional, declararlo en "
        "'otros_impuestos' para que el cuadre pase a ser exacto.", 12),
    "IMPUESTO_ESTIMADO": (
        "estimado", "Documento afecto sin impuesto declarado",
        "Se calcula 19% del neto; si el documento lleva impuesto especifico "
        "(combustible), el total pagado queda subestimado. Declarar 'iva'.", 12),
    "DUPLICADO_EXACTO": (
        "error", "El mismo documento cargado dos veces",
        "El mismo emisor, numero, fecha y neto: es la misma compra fotografiada dos "
        "veces. Se resuelve sola al registrar (no se escribe la segunda copia).", None),
    "DUPLICADO_AMBIGUO": (
        "error", "Mismo N Documento del mismo emisor, contenido distinto",
        "Comparar ambas fotos: o una esta mal leida, o son documentos distintos. Si "
        "sobra una fila ya registrada, borrarla con 'driver.py eliminar <N_REF>'.", None),
    "ITEM_AGRUPADO": (
        "revisar", "Parte de la compra agrupada en un item 'varios'",
        "Si se consigue leer el detalle real, desglosarlo con "
        "'Revision_de_Errores/driver.py desglosar <N_REF>'.", None),
}

ORDEN_SEVERIDAD = {"error": 0, "revisar": 1, "estimado": 2}

# Vocabulario de tipos de documento que el modulo sabe tratar. Todo lo demas
# cae hoy en "no afecto" sin avisar (y por lo tanto con impuesto 0), que es
# justamente lo que TIPO_DOC_DESCONOCIDO viene a hacer visible.
TIPOS_DOCUMENTO_CONOCIDOS = frozenset({
    "factura", "boleta", "guia de despacho", "nota de credito",
})

# Un documento fechado despues de hoy no existe. Se deja un dia de holgura
# para no marcar como error una compra de hoy registrada con el reloj corrido.
DIAS_HOLGURA_FECHA_FUTURA = 1


def clave_documento(proyecto, archivo):
    """Identidad estable de un documento a lo largo del tiempo. Se usa
    (proyecto, archivo) del JSON y no el nombre fisico en disco porque el
    renombrado automatico cambia el nombre fisico en la primera corrida: usar
    ese nombre como clave haria que el mismo hallazgo cambiara de identidad
    entre la corrida 1 y la 2 y se re-emitiera como nuevo. datos_extraidos.json
    nunca se reescribe, asi que su 'archivo' es estable de por vida."""
    return f"{proyecto or ''}\\{archivo or ''}"


def id_hallazgo(codigo, documento, campo):
    """Identificador corto y estable de un hallazgo. Mismo problema en el
    mismo documento y campo => mismo id, corrida tras corrida: es lo que
    permite deduplicar en vez de re-emitir."""
    import hashlib
    crudo = f"{codigo}|{documento}|{campo or ''}"
    return hashlib.sha1(crudo.encode("utf-8")).hexdigest()[:12]


def _fecha_documento(valor):
    """(datetime, valida) del campo 'fecha' de un documento. Acepta los dos
    formatos que ya acepta escribir_fila_master."""
    if isinstance(valor, datetime):
        return valor, True
    for formato in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(valor), formato), True
        except (ValueError, TypeError):
            continue
    return None, False


def _hallazgo(codigo, dato, campo=None, valor_actual=None, valor_esperado=None,
              impacto=0, detalle=""):
    severidad, titulo, accion, columna = TAXONOMIA_ERRORES[codigo]
    documento = clave_documento(dato.get("proyecto"), dato.get("archivo"))
    campo_nombre = campo
    if campo_nombre is None and columna is not None:
        campo_nombre = ENCABEZADOS_MASTER[columna - 1]
    mensaje = titulo if not detalle else f"{titulo}: {detalle}"
    return {
        "id": id_hallazgo(codigo, documento, campo_nombre),
        "codigo": codigo,
        "severidad": severidad,
        "documento": documento,
        "proyecto": dato.get("proyecto", ""),
        "archivo": dato.get("archivo", ""),
        "campo": campo_nombre,
        "columna": columna,
        "valor_actual": valor_actual,
        "valor_esperado": valor_esperado,
        "impacto": abs(int(impacto or 0)),
        "mensaje": mensaje,
        "accion": accion,
    }


def validar_documento(dato):
    """Todos los hallazgos de UN documento del JSON, sin tocar disco ni Excel.

    Funcion pura: mismo documento => mismos hallazgos, en el mismo orden. No
    cubre los hallazgos que solo existen mirando el corpus completo
    (duplicados) ni los que dependen del inventario en disco (archivo sin
    entrada en el JSON) -- esos los agrega validar_corpus().
    """
    hallazgos = []
    items = dato.get("items") or []

    if not items:
        hallazgos.append(_hallazgo("DOC_SIN_ITEMS", dato))
        return hallazgos  # sin items no hay neto ni impuesto que verificar

    for i, item in enumerate(items, 1):
        cantidad = item.get("cantidad")
        if cantidad is None or cantidad <= 0:
            hallazgos.append(_hallazgo(
                "ITEM_CANTIDAD_INVALIDA", dato, campo=f"item {i}: cantidad",
                valor_actual=cantidad,
                detalle=f"'{item.get('nombre_item', '')}' quedo con cantidad {cantidad!r}"))

    neto = total_sin_iva_items(items)
    iva = calcular_iva_documento(dato, neto)
    tipo = clave_tipo_documento(dato.get("tipo_documento"))
    es_nota_credito = tipo.startswith("nota de cr")

    if tipo not in TIPOS_DOCUMENTO_CONOCIDOS:
        hallazgos.append(_hallazgo(
            "TIPO_DOC_DESCONOCIDO", dato, valor_actual=dato.get("tipo_documento"),
            detalle=f"'{dato.get('tipo_documento')}' no esta en "
                    f"{sorted(TIPOS_DOCUMENTO_CONOCIDOS)}; se registra con impuesto 0"))

    if es_nota_credito:
        if neto > 0:
            hallazgos.append(_hallazgo(
                "NC_SIGNO", dato, campo="items", valor_actual=neto, impacto=neto * 2,
                detalle=f"neto {neto:,.0f} en positivo: suma costo en vez de restarlo"))
        elif dato.get("iva") is not None and neto < 0:
            # Una nota de credito con impuesto declarado tiene que cuadrar
            # igual que la factura que revierte. severidad_cuadre_impuesto()
            # no la mira (para ella "afecto" es lo que PAGA impuesto sobre el
            # neto), asi que hasta hoy el impuesto de las notas de credito no
            # lo verificaba nadie.
            esperado = round(neto * TASA_IMPUESTO)
            otros = dato.get("otros_impuestos") or 0
            if abs(iva - (esperado + otros)) > TOLERANCIA_IMPUESTO:
                hallazgos.append(_hallazgo(
                    "NC_IMPUESTO_DESCUADRADO", dato, valor_actual=iva,
                    valor_esperado=esperado + otros, impacto=iva - (esperado + otros),
                    detalle=f"neto {neto:,.0f} => impuesto esperado "
                            f"{esperado + otros:,.0f}, declarado {iva:,.0f}"))
    elif neto <= 0:
        hallazgos.append(_hallazgo(
            "DOC_NETO_NO_POSITIVO", dato, campo="items", valor_actual=neto,
            impacto=neto, detalle=f"neto {neto:,.0f}"))

    fecha, fecha_valida = _fecha_documento(dato.get("fecha"))
    if not fecha_valida:
        hallazgos.append(_hallazgo(
            "FECHA_INVALIDA", dato, valor_actual=dato.get("fecha"),
            detalle=f"'{dato.get('fecha')}' no es DD-MM-AAAA"))
    elif (fecha - datetime.now()).days > DIAS_HOLGURA_FECHA_FUTURA:
        hallazgos.append(_hallazgo(
            "FECHA_FUTURA", dato, valor_actual=dato.get("fecha"),
            detalle=f"{fecha.strftime('%d-%m-%Y')} es posterior a hoy"))

    if not str(dato.get("proveedor") or "").strip():
        hallazgos.append(_hallazgo("PROVEEDOR_VACIO", dato, valor_actual=""))
    if not str(dato.get("categoria") or "").strip():
        hallazgos.append(_hallazgo("CATEGORIA_VACIA", dato, valor_actual=""))

    n_doc = str(dato.get("n_documento", ""))
    if celda_requiere_revision(n_doc):
        hallazgos.append(_hallazgo(
            "N_DOC_ILEGIBLE", dato, valor_actual=n_doc,
            detalle=f"quedo como '{n_doc}'"))

    severidad_impuesto = severidad_cuadre_impuesto(dato, neto, iva)
    if severidad_impuesto is not None:
        codigo = {"error": "IMPUESTO_MENOR", "revisar": "IMPUESTO_EXCESO",
                  "estimado": "IMPUESTO_ESTIMADO"}[severidad_impuesto]
        esperado = round(neto * TASA_IMPUESTO)
        hallazgos.append(_hallazgo(
            codigo, dato, valor_actual=dato.get("iva"), valor_esperado=esperado,
            impacto=(iva - esperado) if dato.get("iva") is not None else 0,
            detalle=f"neto {neto:,.0f} => {NOMBRE_IMPUESTO_PCT} {esperado:,.0f}, "
                    f"declarado {dato.get('iva')!r}"))

    for item in items:
        if PATRON_ITEM_AGRUPADO.search(str(item.get("nombre_item") or "")):
            hallazgos.append(_hallazgo(
                "ITEM_AGRUPADO", dato, campo="items",
                valor_actual=item.get("nombre_item"),
                impacto=(item.get("cantidad") or 0) * (item.get("p_unitario_sin_iva") or 0),
                detalle=f"'{item.get('nombre_item')}' agrupa una parte no identificada"))
            break

    return hallazgos


def _clave_emisor(dato):
    """Un N Documento es unico POR EMISOR, no globalmente (ver CLAUDE.md del
    modulo). Se prefiere el RUT; si no viene, la razon social normalizada."""
    rut = str(dato.get("rut_proveedor") or "").strip()
    if rut:
        return re.sub(r"[^0-9kK]", "", rut).upper()
    return clave_tipo_documento(dato.get("proveedor"))


def _huella_documento(dato):
    """Lo que tiene que coincidir para poder afirmar, sin mirar las fotos, que
    dos entradas son el MISMO documento y no dos compras distintas."""
    fecha, _ = _fecha_documento(dato.get("fecha"))
    return (
        clave_tipo_documento(dato.get("tipo_documento")),
        fecha.strftime("%Y-%m-%d") if fecha else str(dato.get("fecha")),
        round(total_sin_iva_items(dato.get("items") or [])),
    )


def detectar_duplicados(datos):
    """Hallazgos de duplicado sobre el corpus completo. Devuelve
    (hallazgos, copias_exactas), donde copias_exactas mapea la clave de la
    copia sobrante -> clave del documento original que ya la cubre.

    Distingue dos casos que hasta hoy se reportaban como uno solo:
      * DUPLICADO_EXACTO  -- mismo emisor, numero, tipo, fecha y neto. Es la
        misma compra cargada dos veces; se puede resolver sin preguntar.
      * DUPLICADO_AMBIGUO -- mismo emisor y numero, algo mas distinto. Hay que
        comparar las fotos.
    """
    hallazgos = []
    copias_exactas = {}
    vistos = {}
    for dato in datos:
        n_doc = str(dato.get("n_documento", ""))
        if not es_n_documento_real(n_doc):
            continue
        clave = (_clave_emisor(dato), normalizar_n_documento(n_doc))
        primero = vistos.get(clave)
        if primero is None:
            vistos[clave] = dato
            continue
        exacto = _huella_documento(primero) == _huella_documento(dato)
        codigo = "DUPLICADO_EXACTO" if exacto else "DUPLICADO_AMBIGUO"
        original = clave_documento(primero.get("proyecto"), primero.get("archivo"))
        hallazgos.append(_hallazgo(
            codigo, dato, campo="N° Documento", valor_actual=n_doc,
            impacto=total_sin_iva_items(dato.get("items") or []),
            detalle=f"mismo emisor y numero que {original}"))
        hallazgos[-1]["documento_original"] = original
        if exacto:
            copias_exactas[clave_documento(dato.get("proyecto"), dato.get("archivo"))] = original
    return hallazgos, copias_exactas


def validar_corpus(datos, archivos_sin_datos=()):
    """Todos los hallazgos del corpus: los de cada documento, los de duplicado
    y los archivos que estan en disco pero no tienen entrada en el JSON.

    `archivos_sin_datos`: iterable de dicts con 'proyecto' y 'archivo' (el
    mismo shape que devuelve inventariar_archivos).

    Devuelve (hallazgos ordenados por severidad e impacto, copias_exactas).
    """
    hallazgos = []
    for dato in datos:
        hallazgos.extend(validar_documento(dato))

    dup, copias_exactas = detectar_duplicados(datos)
    hallazgos.extend(dup)

    for info in archivos_sin_datos:
        hallazgos.append(_hallazgo("DOC_SIN_DATOS", {
            "proyecto": info.get("proyecto"), "archivo": info.get("archivo"),
        }))

    hallazgos.sort(key=lambda h: (ORDEN_SEVERIDAD[h["severidad"]], -h["impacto"], h["documento"]))
    return hallazgos, copias_exactas


# ── REGISTRO PERSISTENTE DE ERRORES ─────────────────────────────────────────
#
# errores_detectados.json es al informe de auditoria lo que
# correcciones_manuales.json es a las celdas rojas: la memoria que convierte
# "lo que se imprimio esta vez" en "lo que sigue abierto". Sin el, cada
# corrida re-emitia los mismos hallazgos sin forma de cerrarlos ni de saber
# desde cuando estaban ahi.
#
# Vive junto a correcciones_manuales.json del pais activo (se deriva de
# RUTA_CORRECCIONES a proposito, para que no pueda quedar apuntando al
# registro de otro pais si alguien agrega un pais nuevo y olvida una clave).

ESTADOS_HALLAZGO = ("abierto", "auto_resuelto", "resuelto", "descartado")
ESTADOS_CERRADOS = frozenset({"auto_resuelto", "resuelto", "descartado"})

# Centinela: distingue "se cerro sin anotar contra que valor de origen" (los
# cierres viejos, que se reabren para volver a mirarlos) de "se cerro contra un
# valor de origen que casualmente era None".
_SIN_ADJUDICAR = object()


def ruta_registro_errores(ruta_correcciones=None):
    ruta_correcciones = ruta_correcciones or RUTA_CORRECCIONES
    return Path(ruta_correcciones).parent / "errores_detectados.json"


def cargar_registro_errores(ruta=None):
    ruta = Path(ruta or ruta_registro_errores())
    if not ruta.exists():
        return {"version": 1, "errores": []}
    with open(ruta, "r", encoding="utf-8") as f:
        registro = json.load(f)
    registro.setdefault("version", 1)
    registro.setdefault("errores", [])
    return registro


def guardar_registro_errores(registro, ruta=None):
    ruta = Path(ruta or ruta_registro_errores())
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)


def fusionar_hallazgos(registro, hallazgos, hoy=None):
    """Mezcla los hallazgos de esta corrida con el registro persistente.

    - id nuevo                -> se agrega como 'abierto'.
    - id ya abierto           -> se refresca (valor actual, mensaje, impacto) y
                                 se le suma una corrida vista. NO se duplica.
    - id ya cerrado y el dato de origen CAMBIO -> se REABRE: es un valor que
      nadie adjudico todavia. Taparlo seria esconder un error para que las
      metricas se vean mejor.
    - id ya cerrado y el dato de origen sigue IGUAL -> queda cerrado y se
      cuenta en 'origen_sin_corregir'. Es el caso normal de una correccion
      hecha en el Excel: datos_extraidos.json es la entrada del pipeline y no
      se reescribe nunca, asi que el valor viejo sigue ahi. Reabrir el
      hallazgo en cada corrida era justamente lo que hacia que los mismos 35
      descuadres se reimprimieran para siempre. No se oculta: el informe dice
      cuantos son y que hay que corregir el JSON para que no reaparezcan si
      alguna vez se re-extrae el documento.
    - id que estaba abierto y ya no aparece -> se cierra como 'resuelto' con
      la nota de que desaparecio solo (el dato de origen se corrigio).

    Devuelve (nuevos, reabiertos, desaparecidos).
    """
    hoy = hoy or datetime.now().strftime("%Y-%m-%d")
    por_id = {e["id"]: e for e in registro["errores"]}
    vistos = set()
    nuevos, reabiertos = [], []

    for h in hallazgos:
        vistos.add(h["id"])
        existente = por_id.get(h["id"])
        if existente is None:
            entrada = dict(h)
            entrada.update({
                "estado": "abierto", "primera_deteccion": hoy, "ultima_deteccion": hoy,
                "corridas_vistas": 1, "fecha_cierre": None, "resolucion": None,
                "n_ref": None,
            })
            registro["errores"].append(entrada)
            por_id[h["id"]] = entrada
            nuevos.append(entrada)
            continue

        estaba_cerrado = existente["estado"] in ESTADOS_CERRADOS
        origen_adjudicado = existente.get("valor_origen_al_cerrar", _SIN_ADJUDICAR)
        origen_cambio = (origen_adjudicado is _SIN_ADJUDICAR
                         or origen_adjudicado != h["valor_actual"])

        if estaba_cerrado and not origen_cambio:
            # Ya se adjudico exactamente este valor: se cuenta, no se reabre.
            existente["ultima_deteccion"] = hoy
            existente["origen_sin_corregir"] = True
            continue

        existente.update({
            "severidad": h["severidad"], "valor_actual": h["valor_actual"],
            "valor_esperado": h["valor_esperado"], "impacto": h["impacto"],
            "mensaje": h["mensaje"], "accion": h["accion"],
            "ultima_deteccion": hoy,
            "corridas_vistas": existente.get("corridas_vistas", 0) + 1,
        })
        if estaba_cerrado:
            existente.update({
                "estado": "abierto", "fecha_cierre": None,
                "origen_sin_corregir": False,
                "resolucion": f"Reabierto el {hoy}: el dato de origen cambio a "
                              f"{h['valor_actual']!r} despues de haberse cerrado.",
            })
            reabiertos.append(existente)

    desaparecidos = []
    for entrada in registro["errores"]:
        if entrada["id"] in vistos or entrada["estado"] in ESTADOS_CERRADOS:
            continue
        entrada.update({
            "estado": "resuelto", "fecha_cierre": hoy,
            "resolucion": "Dejo de detectarse: el dato de origen ya no presenta el problema.",
        })
        desaparecidos.append(entrada)

    return nuevos, reabiertos, desaparecidos


def hallazgos_abiertos(registro, severidad=None):
    abiertos = [e for e in registro["errores"] if e["estado"] == "abierto"]
    if severidad:
        abiertos = [e for e in abiertos if e["severidad"] == severidad]
    abiertos.sort(key=lambda e: (ORDEN_SEVERIDAD[e["severidad"]], -e.get("impacto", 0),
                                 e["documento"]))
    return abiertos


def cerrar_hallazgo(registro, id_hallazgo_, estado, resolucion, hoy=None):
    """Cierra un hallazgo del registro. `estado` debe ser 'auto_resuelto',
    'resuelto' o 'descartado'; 'descartado' es una decision humana explicita
    ("mire el documento y no es un error") y por eso exige una justificacion
    -- nunca se descarta solo para que el listado se vea corto."""
    if estado not in ESTADOS_CERRADOS:
        raise ValueError(f"estado de cierre invalido: {estado!r}")
    if not str(resolucion or "").strip():
        raise ValueError("cerrar un hallazgo exige dejar escrito como se resolvio")
    hoy = hoy or datetime.now().strftime("%Y-%m-%d")
    for entrada in registro["errores"]:
        if entrada["id"] == id_hallazgo_:
            entrada.update({
                "estado": estado, "fecha_cierre": hoy, "resolucion": resolucion,
                # Cerrar es adjudicar un valor concreto: se deja anotado cual
                # era para que fusionar_hallazgos() sepa distinguir "el origen
                # sigue igual" (queda cerrado) de "el origen cambio" (se
                # reabre). Se estampa aca y no en cada llamador para que ningun
                # camino de cierre se olvide -- el cierre automatico de copias
                # exactas se olvidaba, y por eso el hallazgo se reabria en la
                # corrida siguiente (lo encontro tests/test_pipeline_errores.py).
                "valor_origen_al_cerrar": entrada.get("valor_actual"),
            })
            return entrada
    return None


# ── RESOLUCIÓN DE HALLAZGOS (canal unico, con trazabilidad) ────────────────
#
# Hasta la auditoria del 2026-09-10 el unico camino soportado para corregir un
# dato dejando rastro era corregir_valor_manual(), y solo funcionaba sobre las
# dos columnas que el script pinta de rojo (N Documento e impuesto). Si el
# extractor dejaba la categoria en blanco, el proveedor vacio, la fecha
# ilegible o un tipo de documento fuera del vocabulario, no habia forma
# soportada de arreglarlo: habia que editar el .xlsx a mano y esperar que la
# comparacion contra el backup lo notara -- y esa comparacion solo mira celdas
# ROJAS, asi que no lo notaba nunca. El dato quedaba corregido sin ninguna
# constancia de quien lo cambio ni por que.
#
# corregir_hallazgos() cierra ese hueco: cualquier hallazgo del registro cuya
# clase declare una columna de Master se puede resolver por el mismo camino
# auditado (respaldo -> valor -> fuente azul marino -> propagacion a Detalle ->
# entrada en correcciones_manuales.json + ERRORES.md -> hallazgo cerrado).
# Y lo hace por LOTE: una apertura del libro, un respaldo y un guardado para N
# correcciones, en vez de uno por correccion.

COLUMNAS_CORREGIBLES = tuple(sorted({
    columna for _, _, _, columna in TAXONOMIA_ERRORES.values() if columna is not None
}))


def coaccionar_valor_columna(columna, valor):
    """Lleva `valor` al tipo que espera la columna de Master. Un valor que no
    se puede convertir se deja tal cual: Excel lo mostrara como texto y quedara
    visible que hay que revisarlo, que es mejor que romper la correccion."""
    if columna == 5 and isinstance(valor, str):
        # N Documento nunca queda con ceros a la izquierda, tampoco al
        # corregirlo a mano (MEMORY.md "Reglas de negocio", pedido 2026-07-17).
        return normalizar_n_documento(valor)
    if columna == 4:
        fecha, valida = _fecha_documento(valor)
        return fecha if valida else valor
    if columna == 12 and isinstance(valor, str):
        try:
            return int(valor)
        except ValueError:
            try:
                return float(valor)
            except ValueError:
                return valor
    return valor


def valor_para_bitacora(valor):
    """Forma serializable y legible de un valor de celda para las bitacoras.
    Las fechas de Master son datetime y json.dump no las sabe escribir: sin
    esto, corregir la columna Fecha reventaba al guardar
    correcciones_manuales.json (lo encontro
    tests/test_resolucion_hallazgos.py). Se guardan en DD-MM-AAAA, el formato
    fijo del modulo (pedido 2026-07-28)."""
    if isinstance(valor, datetime):
        return valor.strftime("%d-%m-%Y")
    return valor


def _registrar_correccion_auditada(correcciones, n_ref, columna, valor_anterior,
                                    valor_nuevo, hoy, nota=None, id_hallazgo_=None):
    """Deja la correccion en correcciones_manuales.json -- la misma bitacora
    que ya usan 'confirmar' y corregir_valor_manual, para que todo cambio a
    mano viva en un solo lugar sin importar por que canal entro."""
    campo = ENCABEZADOS_MASTER[columna - 1]
    valor_anterior = valor_para_bitacora(valor_anterior)
    valor_nuevo = valor_para_bitacora(valor_nuevo)
    entrada = next((c for c in correcciones
                    if c["n_ref"] == n_ref and c.get("columna") == columna), None)
    if entrada is None:
        entrada = {"n_ref": n_ref, "hoja": "Master", "columna": columna, "campo": campo}
        correcciones.append(entrada)
    entrada.update({
        "valor_anterior": valor_anterior, "valor_corregido": valor_nuevo,
        "estado": "Aplicado", "fecha_detectado": entrada.get("fecha_detectado", hoy),
        "fecha_aplicado": hoy,
    })
    if nota:
        entrada["nota"] = nota
    if id_hallazgo_:
        entrada["id_hallazgo"] = id_hallazgo_
    return entrada


def corregir_hallazgos(correcciones_pedidas, ruta_excel=None, ruta_correcciones=None,
                       ruta_errores=None, ruta_backups=None, ruta_registro=None):
    """Resuelve uno o varios hallazgos del registro escribiendo el valor
    correcto en Master.

    `correcciones_pedidas`: lista de (id_hallazgo, valor_nuevo) o de
    (id_hallazgo, valor_nuevo, nota).

    Todo el lote comparte UNA apertura del libro, UN respaldo y UN guardado:
    corregir 20 celdas de a una costaba 20 aperturas de openpyxl (~0,3-0,8 s
    cada una segun CLAUDE.md raiz) mas 20 respaldos del libro completo.

    Rechaza, sin escribir nada, un hallazgo que: no exista, ya este cerrado,
    todavia no tenga N Ref (el documento aun no llego a Master), o cuya clase
    no se arregle escribiendo una celda (falta la entrada del JSON, hay que
    desglosar items, hay que borrar un documento). Ese rechazo es deliberado:
    la puerta de entrada es "hay un hallazgo abierto que dice que esta celda
    esta mal", no "escribeme cualquier celda".

    Devuelve (aplicadas, rechazadas) donde cada rechazada es (id, motivo).
    """
    ruta_excel = ruta_excel or RUTA_EXCEL
    ruta_correcciones = ruta_correcciones or RUTA_CORRECCIONES
    ruta_errores = ruta_errores or RUTA_ERRORES_MD
    ruta_backups = ruta_backups or RUTA_BACKUPS
    ruta_registro = ruta_registro or ruta_registro_errores(ruta_correcciones)

    registro = cargar_registro_errores(ruta_registro)
    por_id = {e["id"]: e for e in registro["errores"]}

    pedidos, rechazadas = [], []
    for pedido in correcciones_pedidas:
        id_h, valor = pedido[0], pedido[1]
        nota = pedido[2] if len(pedido) > 2 else None
        entrada = por_id.get(id_h)
        if entrada is None:
            rechazadas.append((id_h, "no existe en el registro de errores"))
        elif entrada["estado"] != "abierto":
            rechazadas.append((id_h, f"ya esta {entrada['estado']}"))
        elif entrada.get("columna") not in COLUMNAS_CORREGIBLES:
            rechazadas.append((id_h, f"'{entrada['codigo']}' no se arregla escribiendo "
                                     f"una celda de Master: {entrada['accion']}"))
        elif not entrada.get("n_ref"):
            rechazadas.append((id_h, "el documento todavia no tiene fila en Master"))
        else:
            pedidos.append((entrada, valor, nota))

    if not pedidos:
        return [], rechazadas

    if excel_esta_bloqueado(ruta_excel):
        return [], rechazadas + [(e["id"], "el Excel esta abierto o bloqueado")
                                 for e, _, _ in pedidos]

    wb = openpyxl.load_workbook(str(ruta_excel), data_only=False)
    if "Master" not in wb.sheetnames:
        return [], rechazadas + [(e["id"], "no existe la hoja Master") for e, _, _ in pedidos]
    ws_master = wb["Master"]
    ws_detalle = wb["Detalle"] if "Detalle" in wb.sheetnames else None
    filas = _mapa_filas_por_n_ref(ws_master)

    hacer_backup(ruta_excel, ruta_backups)
    hoy = datetime.now().strftime("%Y-%m-%d")
    correcciones = cargar_correcciones_manuales(ruta_correcciones)
    aplicadas = []

    for entrada, valor, nota in pedidos:
        fila_m = filas.get(entrada["n_ref"])
        if fila_m is None:
            rechazadas.append((entrada["id"], f"{entrada['n_ref']} ya no existe en Master"))
            continue
        anterior, aplicado, col_detalle = _aplicar_correccion_en_libro(
            ws_master, ws_detalle, fila_m, entrada["columna"], valor, nota=nota
        )
        _registrar_correccion_auditada(correcciones, entrada["n_ref"], entrada["columna"],
                                       anterior, aplicado, hoy, nota=nota,
                                       id_hallazgo_=entrada["id"])
        cerrar_hallazgo(
            registro, entrada["id"], "resuelto",
            f"Corregido en Master ({entrada['campo']}): "
            f"{valor_para_bitacora(anterior)!r} -> {valor_para_bitacora(aplicado)!r}"
            + (f". Nota: {nota}" if nota else ""),
            hoy=hoy)
        entrada["propagado_a_detalle"] = bool(col_detalle)
        aplicadas.append(entrada)

    if aplicadas:
        try:
            _guardar_y_suprimir_aviso(wb, ruta_excel)
        except PermissionError:
            return [], rechazadas + [(e["id"], "el Excel esta abierto en Excel") for e in aplicadas]
        guardar_correcciones_manuales(correcciones, ruta_correcciones)
        regenerar_tabla_errores_md(correcciones, ruta_errores)
        guardar_registro_errores(registro, ruta_registro)

    return aplicadas, rechazadas


def descartar_hallazgo(id_hallazgo_, motivo, ruta_correcciones=None, ruta_registro=None):
    """Cierra un hallazgo como 'descartado': alguien miro el documento y
    concluyo que el dato esta bien. Exige un motivo escrito y lo deja en el
    registro -- descartar no es borrar, es dejar constancia de la decision."""
    ruta_correcciones = ruta_correcciones or RUTA_CORRECCIONES
    ruta_registro = ruta_registro or ruta_registro_errores(ruta_correcciones)
    registro = cargar_registro_errores(ruta_registro)
    entrada = cerrar_hallazgo(registro, id_hallazgo_, "descartado", motivo)
    if entrada is None:
        return None
    guardar_registro_errores(registro, ruta_registro)
    return entrada


def anotar_n_ref(registro, documento, n_ref):
    """Pega el N Ref recien asignado a los hallazgos de ese documento -- es lo
    que permite corregirlos despues por celda, sin que el usuario tenga que
    cruzar a mano nombre de archivo contra fila de Master."""
    tocados = 0
    for entrada in registro["errores"]:
        if entrada["documento"] == documento and not entrada.get("n_ref"):
            entrada["n_ref"] = n_ref
            tocados += 1
    return tocados


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


def fecha_ddmmaaaa_desde_valor(valor):
    """Convierte Master.Fecha (datetime/date, o string 'dd/mm/yyyy' o 'dd-mm-yyyy')
    a 'dd-mm-yyyy' (pedido del usuario 2026-07-28, reemplaza el 'yyyy-mm-dd' anterior).
    Si no se puede interpretar, sanitiza el valor tal cual para no romper el nombre."""
    if isinstance(valor, datetime):
        return valor.strftime("%d-%m-%Y")
    if hasattr(valor, "strftime"):
        return valor.strftime("%d-%m-%Y")
    if isinstance(valor, str):
        for formato in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(valor, formato).strftime("%d-%m-%Y")
            except ValueError:
                continue
        return sanitizar_nombre(valor)
    return "sin-fecha"


def nombre_esperado_archivo(n_ref, proveedor_tag, fecha_valor, extension):
    """Nombre de archivo esperado: '<N Ref>_<TagProveedor>_<Fecha DD-MM-AAAA><ext>'.
    Los .heic/.HEIC pasan a .jpg (se convierten); el resto conserva su extension."""
    tag = sanitizar_nombre(proveedor_tag or "SinProveedor")
    fecha = fecha_ddmmaaaa_desde_valor(fecha_valor)
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
    reconciliacion), nunca fila_dict['proyecto'].

    Prueba 'Archivo origen' primero, pero si esa ruta no existe en disco (caso
    de los 24 documentos del bootstrap, cuyo 'Archivo origen' quedo con el
    nombre que les daba un pipeline anterior ya perdido -- ver
    reconciliacion_archivos.json) cae a la ruta de la reconciliacion, que
    apunta al archivo fisico real."""
    candidatos = []
    if fila_dict.get("archivo_origen"):
        candidatos.append(str(fila_dict["archivo_origen"]))
    ruta_reconciliacion = reconciliacion_inversa.get(fila_dict["n_ref"])
    if ruta_reconciliacion and ruta_reconciliacion not in candidatos:
        candidatos.append(ruta_reconciliacion)

    for candidato in candidatos:
        if "\\" not in candidato:
            continue
        proyecto_fisico, nombre_archivo = candidato.split("\\", 1)
        if (RAIZ_DOCS / proyecto_fisico / nombre_archivo).exists():
            return candidato

    return candidatos[0] if candidatos else None


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


# ── ROTACIÓN DE DOCUMENTOS GIRADOS 90/180/270° ──────────────────────────────
# Corrige la orientacion fisica de un documento pendiente antes de registrarlo,
# a partir del campo opcional "rotacion" (grados en sentido horario) que el
# agente agrega a su entrada de datos_extraidos.json en el Paso 2 del skill al
# notar que la foto/PDF esta girada. Se llama una sola vez, en PASO 6 de
# main(), justo antes de escribir el documento en Master/Detalle -- una vez
# registrado, inventariar_archivos() nunca lo vuelve a listar como pendiente,
# asi que no hay riesgo de re-rotar un archivo ya corregido.

def rotar_imagen(ruta, grados):
    """Rota la imagen en 'ruta' 'grados' en sentido horario (90/180/270) y la
    sobreescribe en el mismo formato (incluye HEIC, via pillow_heif -- se
    registra aqui tambien por si se llama antes de convertir_heic_a_jpg)."""
    from PIL import Image
    import pillow_heif

    pillow_heif.register_heif_opener()
    with Image.open(ruta) as imagen:
        formato = imagen.format
        rotada = imagen.rotate(-grados, expand=True)
        if formato == "JPEG":
            rotada = rotada.convert("RGB")
        rotada.save(str(ruta), format=formato)


def rotar_pdf(ruta, grados):
    """Rota cada pagina del PDF en 'ruta' 'grados' en sentido horario
    (90/180/270), escribiendo el /Rotate de cada pagina -- no re-renderiza el
    contenido, es la forma estandar en que los lectores de PDF interpretan
    paginas giradas."""
    from pypdf import PdfReader, PdfWriter

    lector = PdfReader(str(ruta))
    escritor = PdfWriter()
    escritor.append(lector)
    for pagina in escritor.pages:
        pagina.rotate(grados)
    with open(ruta, "wb") as f:
        escritor.write(f)


def rotar_archivo(ruta, grados):
    """Corrige la orientacion fisica de 'ruta' (imagen o PDF) 'grados' en
    sentido horario (90/180/270). Despacha por extension."""
    if ruta.suffix.lower() == ".pdf":
        rotar_pdf(ruta, grados)
    else:
        rotar_imagen(ruta, grados)


def rotar_si_corresponde(ruta, grados):
    """Si 'grados' es truthy, corrige la orientacion fisica de 'ruta'. Best-
    effort: devuelve el mensaje de error si la rotacion falla, o None si no
    hacia falta rotar o si salio bien -- nunca lanza, para no bloquear el
    registro del documento por un problema de rotacion (mismo patron que
    ejecutar_plan_renombrado)."""
    if not grados:
        return None
    try:
        rotar_archivo(ruta, grados)
        return None
    except Exception as e:
        return str(e)


def reflejar_a_sitio_comunicacion(ruta_excel=None, ruta_sitio=None):
    """Copia (shutil.copy2) el Excel local encima de la copia de solo lectura
    en 'Sitio de comunicacion - Centro de Costos 1/' -- mismo paso que hace
    'run' (PASO 12b) al final de cada corrida. Factorizado para que tambien
    lo puedan llamar comandos que no pasan por main(), como el driver de la
    skill Revision_de_Errores (corregir/desglosar solo tocan el Excel local;
    sin este paso aparte, la copia compartida queda desactualizada). No falla
    si el destino esta bloqueado, solo advierte -- igual que en 'run'.
    Perú no tiene (todavía) un sitio de comunicación propio configurado
    (ruta_sitio resuelve a None): en ese caso se omite con un [INFO], no se
    intenta copiar a un destino inexistente. Devuelve True si la copia se
    actualizo, False si no se pudo o no aplica."""
    ruta_excel = ruta_excel or RUTA_EXCEL
    ruta_sitio = ruta_sitio if ruta_sitio is not None else RUTA_EXCEL_SITIO_COMUNICACION
    if ruta_sitio is None:
        print("  [INFO] Sin sitio de comunicación configurado para este país -- paso omitido.")
        return False
    try:
        shutil.copy2(ruta_excel, ruta_sitio)
        print(f"  [OK] Copia actualizada: {ruta_sitio}")
        return True
    except (PermissionError, OSError) as e:
        print(f"  [WARN] No se pudo actualizar la copia en Sitio de comunicacion ({e}).")
        print("         El Excel local si quedo guardado; reintenta mas tarde (ej. si esta abierto).")
        return False


@contextmanager
def _modulo_hermano_fresco(directorio, nombre_modulo):
    """Inserta 'directorio' en sys.path e importa 'nombre_modulo' fresco
    (descartando cualquier cache previo en sys.modules) para la duracion del
    bloque `with`, restaurando sys.path al salir -- se haya importado bien o
    no. Los 3 modulos hermanos de Finanzas QUEMPIN comparten nombres de
    archivo (build_visualizador.py, driver.py) y sys.modules cachea por
    nombre, asi que importarlos por nombre plano sin este descarte entregaria
    el modulo equivocado si ya se importo uno homonimo antes en el mismo
    proceso. Unifica lo que antes era el mismo bloque copiado 3 veces
    (actualizar_visualizador, _reportes_pendientes_tras_run,
    actualizar_analisis_financiero) -- una de las 3 copias no restauraba
    sys.path al fallar, dejando el directorio insertado para el resto del
    proceso; este helper lo hace siempre, en un solo lugar."""
    directorio = str(directorio)
    ya_en_path = directorio in sys.path
    if not ya_en_path:
        sys.path.insert(0, directorio)
    try:
        sys.modules.pop(nombre_modulo, None)
        yield importlib.import_module(nombre_modulo)
    finally:
        if not ya_en_path and directorio in sys.path:
            sys.path.remove(directorio)


def actualizar_visualizador():
    """Regenera el visualizador web (Visualizador Web/build/index.html) a partir
    del Excel recien guardado -- mismo patron que reflejar_a_sitio_comunicacion:
    corre al final de cada 'run' (PASO 12c), solo lee el Excel (no lo modifica),
    y si falla no aborta el run, solo advierte -- el Excel ya quedo guardado
    igual. Pedido del usuario 2026-07-19: que actualizar el Centro de Costos
    actualice el visualizador automaticamente, sin paso manual aparte. Ver
    Visualizador Web/CLAUDE.md para la arquitectura del build."""
    ruta_build_script = RAIZ_VISUALIZADOR_WEB / "build_visualizador.py"
    if not ruta_build_script.exists():
        print(f"  [WARN] No existe {ruta_build_script}, se omite este paso.")
        return False
    try:
        with _modulo_hermano_fresco(RAIZ_VISUALIZADOR_WEB, "build_visualizador") as bv:
            return bv.build() == 0
    except Exception as e:
        print(f"  [WARN] No se pudo actualizar el visualizador web ({e}).")
        print("         El Excel si quedo guardado; correr manualmente "
              "'python driver.py visualizador' despues.")
        return False


def _reportes_pendientes_tras_run() -> list[str]:
    """Best-effort: intenta calcular que reportes PDF quedaron pendientes tras
    este run. Devuelve [] si el skill de reportes no existe todavia o falla
    -- nunca aborta el run de Centro de Costos por esto."""
    ruta_driver = (
        RAIZ_ANALISIS_FINANCIERO / ".claude" / "skills"
        / "Reportes_Analisis_Financiero" / "driver.py"
    )
    if not ruta_driver.exists():
        return []
    try:
        with _modulo_hermano_fresco(ruta_driver.parent, "driver") as driver_reportes:
            return driver_reportes.calcular_reportes_pendientes()
    except Exception:
        return []


def _avisar_reportes_pendientes() -> None:
    pendientes = _reportes_pendientes_tras_run()
    if not pendientes:
        return
    print(
        f"  [AVISO] {len(pendientes)} reporte(s) PDF de Análisis Financiero "
        f"quedaron pendientes/desactualizados ({', '.join(pendientes)}) -- correr "
        f"'/Reportes_Analisis_Financiero status' para verlos."
    )


def actualizar_analisis_financiero(pais="CL"):
    """Actualiza Análisis Financiero/Análisis de Proyectos.xlsx (costos
    reales por proyecto/categoría + hoja Indicadores) a partir del Excel
    recien guardado -- mismo patron que actualizar_visualizador: corre al
    final de cada 'run' (PASO 12d), solo lee Centro de Costos.xlsx (no lo
    modifica), y si falla no aborta el run, solo advierte."""
    ruta_script = RAIZ_ANALISIS_FINANCIERO / "Sistema" / "analisis_financiero.py"
    if not ruta_script.exists():
        print(f"  [WARN] No existe {ruta_script}, se omite este paso.")
        return False
    try:
        with _modulo_hermano_fresco(ruta_script.parent, "analisis_financiero") as af:
            resumen = af.ejecutar(pais=pais)
            if resumen["error"]:
                print(f"  [WARN] Análisis Financiero terminó con error: {resumen['error']}")
                return False
            # Los reportes PDF son un concepto Chile-only por ahora (ver
            # Sistema Analisis Financiero/CLAUDE.md, seccion "Reportes PDF"
            # -- nunca menciona Peru) -- avisar de "pendientes" durante un
            # run de Peru solo reportaria sobre los reportes de Chile, ruido
            # enganoso.
            if pais == "CL":
                _avisar_reportes_pendientes()
            return True
    except Exception as e:
        print(f"  [WARN] No se pudo actualizar Análisis Financiero ({e}).")
        print("         El Excel de Centro de Costos si quedo guardado; correr manualmente "
              "'python driver.py run' en Sistema Analisis Financiero despues.")
        return False


# --- MAIN ---------------------------------------------------------------------

def _imprimir_lista_truncada(items, formatear, limite=15):
    """Imprime como maximo 'limite' items formateados (via 'formatear', que
    puede devolver texto multilinea); si hay mas, resume el resto en 1
    linea. No cambia ningun dato, solo cuanto texto se imprime -- mismo
    patron que el homonimo en .claude/skills/Registro_Centro_de_Costos/
    driver.py, duplicado aca (no al reves) porque esa carpeta es quien
    importa este modulo, nunca al reves. Antes el INFORME DE AUDITORIA de
    'main()' era la unica salida larga del archivo sin este limite."""
    for item in items[:limite]:
        print(formatear(item))
    restantes = len(items) - limite
    if restantes > 0:
        print(f"   ... y {restantes} mas.")


# ── CRONOMETRO DE ETAPAS ────────────────────────────────────────────────────
# Cada PASO de main() se abre con _paso(), que ademas de imprimir el
# encabezado cierra el paso anterior y anota cuanto duro. Sin esto, saber que
# etapa domina una corrida obligaba a perfilar a mano por fuera (asi se
# descubrio, el 2026-09-09, que guardar el libro se llevaba mas que registrar
# los documentos). El costo es un time.perf_counter() por paso.
_ETAPAS = []
_ETAPA_ACTUAL = None


def _paso(codigo, titulo):
    """Abre una etapa de main(): imprime su encabezado y cierra la anterior."""
    global _ETAPA_ACTUAL
    ahora = time.perf_counter()
    if _ETAPA_ACTUAL is not None:
        _ETAPAS.append((_ETAPA_ACTUAL[0], _ETAPA_ACTUAL[1], ahora - _ETAPA_ACTUAL[2]))
    _ETAPA_ACTUAL = (codigo, titulo, ahora)
    print(f"\n--- {codigo}: {titulo} ---")


def _cerrar_etapas():
    global _ETAPA_ACTUAL
    if _ETAPA_ACTUAL is not None:
        _ETAPAS.append((_ETAPA_ACTUAL[0], _ETAPA_ACTUAL[1],
                        time.perf_counter() - _ETAPA_ACTUAL[2]))
        _ETAPA_ACTUAL = None


def _informe_etapas(total, umbral=0.05):
    """Etapas ordenadas por duracion. Se listan solo las que superan el
    umbral: las 8 etapas de milisegundos solo agregarian ruido."""
    _cerrar_etapas()
    if not _ETAPAS:
        return
    print("\n" + "=" * 70)
    print("  TIEMPO POR ETAPA")
    print("=" * 70)
    visibles = [e for e in _ETAPAS if e[2] >= umbral]
    for codigo, titulo, duracion in sorted(visibles, key=lambda e: -e[2]):
        print(f"   {duracion:7.2f}s  {100 * duracion / total:5.1f}%  {codigo}: {titulo}")
    ocultas = len(_ETAPAS) - len(visibles)
    if ocultas:
        resto = sum(d for _, _, d in _ETAPAS if d < umbral)
        print(f"   {resto:7.2f}s         (+{ocultas} etapas de menos de {umbral:.2f}s)")
    print(f"   {total:7.2f}s  100.0%  TOTAL")


ETIQUETA_SEVERIDAD = {
    "error": "ERROR    (impuesto MENOR al que corresponde -- hay que corregir)",
    "revisar": "REVISAR  (impuesto sobre el 19% sin impuesto especifico conocido)",
    "estimado": "ESTIMADO (sin 'iva' en el JSON: se calcula 19%, puede quedar corto)",
}


def _imprimir_cuadre_impuesto(hallazgos, limite=15):
    """Salida compartida por main() y por 'driver.py status' -- antes cada uno
    formateaba la misma lista por su cuenta. Agrupa por severidad para que un
    'error' real no quede sepultado entre avisos informativos."""
    if not hallazgos:
        print("   Cuadra todo. Sin hallazgos.")
        return
    por_severidad = {}
    for h in hallazgos:
        por_severidad.setdefault(h["severidad"], []).append(h)

    for severidad in ("error", "revisar", "estimado"):
        grupo = por_severidad.get(severidad)
        if not grupo:
            continue
        print(f"\n   [{severidad.upper()}] {len(grupo)} documento(s) -- "
              f"{ETIQUETA_SEVERIDAD[severidad]}")

        def _fmt(h):
            iva = h["iva"] if h["iva"] is not None else "(sin dato)"
            iva_txt = f"{iva:,}" if isinstance(iva, (int, float)) else iva
            texto = (f"   * Doc {h['n_documento']} ({h['archivo']}) [{h['categoria']}]: "
                     f"Neto={h['neto']:,.0f} | impuesto={iva_txt} "
                     f"vs 19%={h['iva_esperado']:,}")
            if h["nota"]:
                texto += f"\n     Nota: {h['nota'][:120]}"
            return texto

        _imprimir_lista_truncada(grupo, _fmt, limite=limite)


def _linea_hallazgo(e):
    donde = e.get("n_ref") or e["documento"]
    plata = f" | impacto ${e['impacto']:,}" if e.get("impacto") else ""
    veces = e.get("corridas_vistas", 1)
    antiguedad = f" | visto {veces}x desde {e['primera_deteccion']}" if veces > 1 else ""
    return (f"   * [{e['id']}] {donde} | {e['mensaje']}{plata}{antiguedad}\n"
            f"     -> {e['accion']}")


def imprimir_informe_hallazgos(registro, duplicados_evitados=(), limite_por_severidad=10):
    """Informe priorizado a partir del registro persistente: primero los
    'error' (hay algo seguro que corregir) y, dentro de cada severidad, los de
    mayor impacto en pesos.

    A diferencia del informe anterior -- que imprimia listas efimeras y
    truncaba a 15 sin decir donde estaba el resto -- cada linea trae el id
    estable del hallazgo (con el que se cierra), desde cuando esta abierto, y
    la accion concreta; y el corte por severidad dice explicitamente cuantos
    quedaron fuera y en que archivo verlos completos."""
    abiertos = hallazgos_abiertos(registro)
    cerrados = [e for e in registro["errores"] if e["estado"] in ESTADOS_CERRADOS]
    auto = [e for e in cerrados if e["estado"] == "auto_resuelto"]

    print("\n" + "=" * 70)
    print("  HALLAZGOS ABIERTOS (registro persistente de errores)")
    print("=" * 70)
    print(f"  Abiertos: {len(abiertos)} | Cerrados historicos: {len(cerrados)} "
          f"(de ellos {len(auto)} resueltos automaticamente)")
    print(f"  Registro completo: {ruta_registro_errores().name}")

    # Un hallazgo cerrado corrigiendo el Excel deja el valor viejo en
    # datos_extraidos.json (que es entrada del pipeline y no se reescribe).
    # No se reabre en cada corrida -- eso era el ruido -- pero tampoco se
    # esconde: se dice cuantos son y que hacer.
    origen_pendiente = [e for e in cerrados if e.get("origen_sin_corregir")]
    if origen_pendiente:
        print(f"  [OJO] {len(origen_pendiente)} hallazgo(s) cerrado(s) siguen con el dato "
              f"viejo en {RUTA_JSON.name}: la correccion vive solo en el Excel. "
              f"Corregir tambien el JSON si el documento se va a re-extraer.")

    if duplicados_evitados:
        print(f"\n  [AUTO] {len(duplicados_evitados)} copia(s) exacta(s) no se registraron "
              f"(costo ya contabilizado):")
        for d in duplicados_evitados[:limite_por_severidad]:
            destino = d["n_ref_original"] or d["original"]
            print(f"    * {d['proyecto']}\\{d['archivo']} == {destino}")

    if not abiertos:
        print("\n  Sin hallazgos abiertos.")
        return

    for severidad in ("error", "revisar", "estimado"):
        grupo = [e for e in abiertos if e["severidad"] == severidad]
        if not grupo:
            continue
        print(f"\n  [{severidad.upper()}] {len(grupo)} hallazgo(s) -- "
              f"{ETIQUETA_SEVERIDAD_HALLAZGO[severidad]}")
        for e in grupo[:limite_por_severidad]:
            print(_linea_hallazgo(e))
        if len(grupo) > limite_por_severidad:
            print(f"   ... y {len(grupo) - limite_por_severidad} mas de esta severidad "
                  f"(lista completa: 'Revision_de_Errores/driver.py hallazgos').")


ETIQUETA_SEVERIDAD_HALLAZGO = {
    "error": "el dato de hoy no puede ser bueno; hay algo seguro que corregir",
    "revisar": "puede ser legitimo o no; hay que mirar el documento",
    "estimado": "el dato se completo con un supuesto; conviene verificarlo",
}


def _resumir_lineas_detalle(lineas, ruta_log, mantener=3):
    """Escribe el detalle linea por linea en un log en disco y devuelve solo
    un resumen truncado para la consola -- no cambia ningun dato del Excel,
    solo cuanto texto se imprime cuando 'run' registra/regenera muchos items
    de una vez."""
    if not lineas:
        return []
    ruta_log.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_log, "a", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    if len(lineas) <= mantener * 2:
        return lineas
    omitidas = len(lineas) - mantener * 2
    return (
        lineas[:mantener]
        + [f"  ... ({omitidas} linea(s) mas, detalle completo en {ruta_log}) ..."]
        + lineas[-mantener:]
    )


def main(pais="CL"):
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    inicio_run = time.perf_counter()
    # El cronometro es global del modulo: si main() se llama dos veces en el
    # mismo proceso (tests), las etapas de la corrida anterior contaminarian
    # el informe.
    _ETAPAS.clear()
    globals()["_ETAPA_ACTUAL"] = None

    configurar_pais(pais)

    print("=" * 70)
    print(f"  REGISTRO CENTRO DE COSTOS - {RAZON_SOCIAL}")
    print(f"  País: {pais} | Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    ruta_log_run = RUTA_LOGS / f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

    if not RAIZ_DOCS.exists():
        print(f"ERROR: No existe la carpeta raiz: {RAIZ_DOCS}")
        return
    if not RUTA_JSON.exists():
        print(f"ERROR: No existe el JSON de datos: {RUTA_JSON}")
        return

    _paso("PASO 1", "Backup")
    ruta_backup_anterior = backup_mas_reciente(ruta_backups=RUTA_BACKUPS)
    hacer_backup(RUTA_EXCEL, ruta_backups=RUTA_BACKUPS)

    _paso("PASO 2", "Abrir Excel")
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

    migrar_paleta_colores(wb, ws_master, ws_detalle)
    migrar_formato_fecha_corta(ws_master)
    migrar_n_documento_sin_ceros(ws_master, ws_detalle)
    migrar_columna_total_con_iva_detalle(ws_master, ws_detalle)
    # Segura antes de PASO 2B: detectar_correcciones_manuales mira el color en
    # el BACKUP y compara VALORES, y esto solo cambia el color del libro actual.
    limpiadas, marcadas = migrar_color_cuadre_impuesto(ws_master, ws_detalle)
    if limpiadas or marcadas:
        print(f"  [MIGRACION] Cuadre de impuesto: {limpiadas} celda(s) destacada(s) "
              f"de más liberada(s), {marcadas} marcada(s) para revisar.")

    _paso("PASO 2B", "Detectar correcciones manuales (celdas rojas editadas a mano)")
    correcciones_pendientes = []
    if ruta_backup_anterior is not None:
        wb_anterior = openpyxl.load_workbook(str(ruta_backup_anterior), data_only=False)
        detectadas = detectar_correcciones_manuales(wb_anterior, wb)
        correcciones_pendientes = registrar_correcciones_pendientes(detectadas)
        if correcciones_pendientes:
            print(f"  [INFO] {len(correcciones_pendientes)} correccion(es) manual(es) detectada(s), "
                  f"pendiente(s) de confirmar:")
            for c in correcciones_pendientes:
                print(f"    - {c['n_ref']} / {c['campo']}: '{c['valor_anterior']}' -> '{c['valor_corregido']}'")
            print("    Registradas en ERRORES.md. Para aplicarlas (recolorear azul marino + propagar "
                  "a Detalle): python driver.py confirmar --todos")
        else:
            print("  Sin correcciones manuales nuevas.")
    else:
        print("  [INFO] No hay backup anterior contra el cual comparar (primera corrida).")

    _paso("PASO 3", "Leer registros existentes")
    filas_master, max_seq, docs_registrados = leer_master(ws_master)
    reconciliacion = cargar_reconciliacion()
    archivos_registrados = set(reconciliacion.keys())
    for fm in filas_master:
        if fm["archivo_origen"]:
            archivos_registrados.add(str(fm["archivo_origen"]))
    print(f"  Documentos ya en Master: {len(filas_master)}")
    print(f"  Archivos ya cubiertos (Master + reconciliacion): {len(archivos_registrados)}")

    _paso("PASO 4", "Inventariar archivos")
    pendientes, omitidos = inventariar_archivos(RAIZ_DOCS, archivos_registrados)
    print(f"  Pendientes: {len(pendientes)}")
    print(f"  Omitidos (ya registrados): {len(omitidos)}")

    _paso("PASO 5", "Cargar datos extraidos")
    datos_json = cargar_datos_json(RUTA_JSON)
    print(f"  Entradas en {RUTA_JSON.name}: {len(datos_json)}")

    # PASO 5B -- ANTES de escribir nada. Hasta la auditoria del 2026-09-10 el
    # cuadre de impuesto corria en el PASO 13, o sea despues de guardar el
    # libro, de copiarlo al sitio compartido, de regenerar el visualizador y de
    # recalcular Analisis Financiero: un documento mal leido se publicaba en
    # tres destinos antes de que nadie lo mirara, y si el Excel estaba
    # bloqueado main() hacia 'return' antes de llegar al informe y la corrida
    # terminaba sin reportar un solo hallazgo. Validar aca cierra las dos.
    _paso("PASO 5B", "Validar documentos (antes de escribir)")
    sin_datos_en_json = [
        info for info in pendientes
        if buscar_dato_por_archivo(datos_json, info["proyecto"], info["archivo"]) is None
    ]
    hallazgos, copias_exactas = validar_corpus(datos_json, archivos_sin_datos=sin_datos_en_json)
    registro_errores = cargar_registro_errores()
    nuevos_hallazgos, reabiertos, desaparecidos = fusionar_hallazgos(registro_errores, hallazgos)
    print(f"  Hallazgos vigentes: {len(hallazgos)} "
          f"({len(nuevos_hallazgos)} nuevo(s), {len(reabiertos)} reabierto(s), "
          f"{len(desaparecidos)} cerrado(s) por dejar de aparecer)")

    # Copias exactas todavia pendientes de registrar: son la MISMA compra
    # fotografiada dos veces (mismo emisor, numero, tipo, fecha y neto), asi
    # que registrarlas duplicaria el costo. Se resuelven solas anotandolas en
    # reconciliacion_archivos.json contra el N Ref del original -- exactamente
    # el remedio que ya se aplico a mano en el incidente del 2026-08-19
    # (CCON-005/CCON-011, ver notas_reconciliacion) -- y queda registrado como
    # auto-resuelto. Es reversible: basta borrar la entrada del mapeo.
    claves_pendientes = {clave_documento(i["proyecto"], i["archivo"]) for i in pendientes}
    duplicados_autoresueltos = {
        copia: original for copia, original in copias_exactas.items()
        if copia in claves_pendientes
    }

    limpiar_pie(ws_detalle)
    limpiar_pie(ws_master)
    fila_detalle = ultima_fila_datos(ws_detalle) + 1
    fila_master = ultima_fila_datos(ws_master) + 1

    proyectos_tocados = set(fm["proyecto"] for fm in filas_master if fm["proyecto"])
    colores = asignar_colores_proyectos(wb, proyectos_tocados | {p["proyecto"] for p in pendientes})

    registrados_ok = 0
    limitaciones = []
    alertas_legibilidad = []
    lineas_registro_ok = []
    notas_documentos_nuevos = []
    duplicados_evitados = []
    # N Documento -> N Ref, solo para los numeros que aparecen UNA vez en
    # Master: sirve para decir "esta copia es la misma compra que UMAG-014"
    # sin arriesgarse a apuntar al documento equivocado si dos emisores
    # distintos comparten numero.
    docs_a_n_ref = _mapa_n_documento_a_n_ref(ws_master)

    _paso("PASO 6", "Escribir documentos nuevos")
    reconciliacion_actualizada = False
    for info in pendientes:
        clave = clave_documento(info["proyecto"], info["archivo"])
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

        original = duplicados_autoresueltos.get(clave)
        if original:
            # Por definicion de copia exacta, el numero de esta copia es el
            # mismo del original, asi que sirve para ubicar su fila en Master.
            n_ref_original = docs_a_n_ref.get(normalizar_n_documento(str(dato["n_documento"])))
            reconciliacion[info["ruta_relativa"]] = n_ref_original or original
            reconciliacion_actualizada = True
            for entrada in registro_errores["errores"]:
                if entrada["documento"] == clave and entrada["codigo"] == "DUPLICADO_EXACTO":
                    cerrar_hallazgo(
                        registro_errores, entrada["id"], "auto_resuelto",
                        f"No se registro: es la misma compra que {original}"
                        f"{f' ({n_ref_original})' if n_ref_original else ''}. "
                        f"El archivo quedo mapeado en {RUTA_RECONCILIACION.name}; "
                        f"para deshacerlo, borrar esa entrada.")
            duplicados_evitados.append({
                "archivo": info["archivo"], "proyecto": info["proyecto"],
                "original": original, "n_ref_original": n_ref_original,
            })
            print(f"  [AUTO] {info['proyecto']}\\{info['archivo']}: copia exacta de "
                  f"{original}, no se registra (costo ya contabilizado).")
            continue

        grados_rotacion = dato.get("rotacion")
        error_rotacion = rotar_si_corresponde(Path(info["ruta_absoluta"]), grados_rotacion)
        if error_rotacion:
            print(f"  [WARN] No se pudo rotar {info['proyecto']}\\{info['archivo']}: {error_rotacion}")
        elif grados_rotacion:
            print(f"  [INFO] Rotado {grados_rotacion}° (sentido horario) antes de registrar: "
                  f"{info['proyecto']}\\{info['archivo']}")

        n_doc_str = str(dato["n_documento"])
        n_doc_norm = normalizar_n_documento(n_doc_str)

        n_ref = siguiente_n_ref(dato["proyecto"], max_seq)
        color = colores.get(dato["proyecto"])

        if dato.get("notas"):
            notas_documentos_nuevos.append({
                "n_ref": n_ref, "archivo": info["archivo"], "notas": dato["notas"],
            })

        fila_detalle = escribir_items_detalle(ws_detalle, fila_detalle, n_ref, dato, color)
        escribir_fila_master(ws_master, fila_master, n_ref, dato, info, color)
        # Los hallazgos de este documento nacieron antes de que existiera su
        # fila en Master: recien ahora se les puede pegar el N Ref, que es lo
        # que permite corregirlos por celda sin cruzar a mano nombre de
        # archivo contra fila.
        anotar_n_ref(registro_errores, clave, n_ref)
        if es_n_documento_real(n_doc_str):
            docs_registrados.add(n_doc_str)
            docs_registrados.add(n_doc_norm)
            docs_a_n_ref.setdefault(n_doc_norm, n_ref)

        proyectos_tocados.add(dato["proyecto"])
        registrados_ok += 1
        lineas_registro_ok.append(
            f"  [OK] {info['proyecto']}\\{info['archivo']} -> {n_ref} "
            f"(doc {dato['n_documento']}, {len(dato['items'])} item(s))"
        )

        if celda_requiere_revision(n_doc_str):
            alertas_legibilidad.append({
                "archivo": info["archivo"], "proyecto": dato["proyecto"],
                "detalle": "N Documento requiere revision manual.",
            })
        fila_master += 1

    for linea in _resumir_lineas_detalle(lineas_registro_ok, ruta_log_run):
        print(linea)

    if reconciliacion_actualizada:
        guardar_reconciliacion(reconciliacion)
        print(f"  [OK] {RUTA_RECONCILIACION.name} actualizado con "
              f"{len(duplicados_evitados)} copia(s) exacta(s) evitada(s).")

    # El registro de errores se persiste ACA, antes de guardar el Excel: si el
    # libro esta bloqueado y la corrida aborta, los hallazgos de esta corrida
    # (y las auto-resoluciones ya aplicadas) igual quedan asentados. Antes de
    # la auditoria del 2026-09-10 un abort dejaba la corrida sin ningun
    # informe.
    guardar_registro_errores(registro_errores)

    _paso("PASO 7", "Reordenar por fecha (mas reciente arriba)")
    reordenar_por_fecha(ws_master, ws_detalle, fila_master, fila_detalle)

    _paso("PASO 8", "Regenerar pies de Detalle/Master")
    regenerar_pie(ws_detalle, len(ENCABEZADOS_DETALLE), [10, 11], "TOTAL GENERAL", fila_detalle, LEYENDA_DETALLE)
    regenerar_pie(ws_master, len(ENCABEZADOS_MASTER), [11, 12, 13], "TOTAL GENERAL", fila_master, LEYENDA_MASTER)

    _paso("PASO 9", "Regenerar hojas de proyecto")
    ultima_master = fila_master - 1
    lineas_hojas_ok = []
    for proyecto in sorted(proyectos_tocados):
        filas_de_este_proyecto = [
            r for r in range(2, ultima_master + 1)
            if ws_master.cell(row=r, column=2).value == proyecto
        ]
        if not filas_de_este_proyecto:
            continue
        regenerar_hoja_proyecto(wb, proyecto, filas_de_este_proyecto, colores.get(proyecto))
        lineas_hojas_ok.append(
            f"  [OK] Hoja '{prefijo_para_proyecto(proyecto)}' ({proyecto}) regenerada "
            f"({len(filas_de_este_proyecto)} documento(s))"
        )
    for linea in _resumir_lineas_detalle(lineas_hojas_ok, ruta_log_run):
        print(linea)

    def _informe_parcial(motivo):
        """El informe de hallazgos NO depende de haber podido guardar el
        libro: se calculo entero en el PASO 5B. Antes de la auditoria del
        2026-09-10 estos dos 'return' salian sin imprimir nada, asi que una
        corrida con el Excel abierto se llevaba consigo todo el trabajo de
        deteccion."""
        print(f"\n[ERROR] {motivo}")
        imprimir_informe_hallazgos(registro_errores, duplicados_evitados)
        _informe_etapas(time.perf_counter() - inicio_run)

    if excel_esta_bloqueado(RUTA_EXCEL):
        _informe_parcial(
            "El archivo esta abierto en Excel (o bloqueado). Cierralo antes de continuar.\n"
            "        No se renombro ni convirtio ningun archivo; no se guardaron cambios.")
        return

    _paso("PASO 10", "Renombrar y convertir archivos")
    reconciliacion_inversa = construir_reconciliacion_inversa(reconciliacion)
    filas_master_actual, _, _ = leer_master(ws_master)
    renombrados, advertencias_renombrado = aplicar_renombrados(
        ws_master, filas_master_actual, reconciliacion_inversa
    )
    print(f"  [OK] {renombrados} archivo(s) renombrado(s)/convertido(s).")
    for adv in advertencias_renombrado:
        print(f"  [WARN] {adv['n_ref']}: {adv['detalle']}")

    _paso("PASO 11", "Formato final")
    ajustar_anchos(ws_master)
    ajustar_anchos(ws_detalle)
    orden_deseado = ["Master", "Detalle"] + [prefijo_para_proyecto(p) for p in sorted(proyectos_tocados)]
    for i, nombre in enumerate(orden_deseado):
        if nombre in wb.sheetnames:
            wb.move_sheet(nombre, offset=i - wb.sheetnames.index(nombre))
    print(f"  [OK] Hojas ordenadas: {wb.sheetnames}")

    _paso("PASO 12", "Guardar")
    try:
        _guardar_y_suprimir_aviso(wb, RUTA_EXCEL)
        print(f"  [OK] Excel guardado: {RUTA_EXCEL.name}")
    except PermissionError:
        _informe_parcial("El archivo esta abierto en Excel. Cierralo y vuelve a ejecutar.")
        return

    _paso("PASO 12b", "Reflejar en Sitio de comunicacion")
    reflejar_a_sitio_comunicacion()

    _paso("PASO 12c", "Actualizar visualizador web")
    if RAIZ_VISUALIZADOR_WEB.exists():
        actualizar_visualizador()
    else:
        print(f"  [INFO] Visualizador Web de {pais} aún no implementado -- paso omitido.")

    _paso("PASO 12d", "Actualizar Análisis Financiero")
    actualizar_analisis_financiero(pais=pais)

    _paso("PASO 13", "Verificaciones aritmeticas (sobre todo el JSON)")
    inconsistencias = verificar_aritmetica(datos_json)

    print("\n" + "=" * 70)
    print("  INFORME DE AUDITORIA")
    print("=" * 70)

    print("\n1. ALERTAS DE LEGIBILIDAD")
    if alertas_legibilidad:
        _imprimir_lista_truncada(
            alertas_legibilidad,
            lambda a: f"   * {a['archivo']} | Proyecto: {a['proyecto']} | {a['detalle']}",
        )
    else:
        print("   Sin hallazgos.")

    print(f"\n2. CUADRE DE IMPUESTO (Neto vs {NOMBRE_IMPUESTO_PCT})")
    _imprimir_cuadre_impuesto(inconsistencias)

    # Los duplicados se reportan en HALLAZGOS ABIERTOS (DUPLICADO_EXACTO /
    # DUPLICADO_AMBIGUO). Aca habia un detector aparte, escrito dentro del
    # bucle de escritura, que comparaba el N Documento GLOBALMENTE ignorando el
    # emisor -- y un numero es unico POR EMISOR (ver CLAUDE.md del modulo).
    # Sobre las 681 entradas reales emitia 8 avisos donde detectar_duplicados()
    # emite 6: los 2 de mas eran emisores distintos que comparten numero. Solo
    # miraba nuevo-contra-ya-registrado (nunca dos filas ya registradas) y era
    # sensible al orden del inventario, asi que marcaba indistintamente a
    # cualquiera de los dos miembros del par. Eliminado el 2026-09-10.
    print("\n3. POSIBLES DUPLICADOS -- ver HALLAZGOS ABIERTOS (DUPLICADO_EXACTO/AMBIGUO)")

    print("\n4. LIMITACIONES DE REGISTRO")
    if limitaciones:
        _imprimir_lista_truncada(
            limitaciones,
            lambda lim: f"   * {lim['archivo']} | Proyecto: {lim['proyecto']}\n     {lim['detalle']} Accion: {lim['accion']}",
        )
    else:
        print("   Sin hallazgos.")

    print("\n5. RENOMBRADO/CONVERSION DE ARCHIVOS")
    if advertencias_renombrado:
        _imprimir_lista_truncada(advertencias_renombrado, lambda adv: f"   * {adv['n_ref']}: {adv['detalle']}")
    else:
        print("   Sin hallazgos.")

    print("\n6. CAMBIOS MANUALES PENDIENTES DE CONFIRMAR")
    if correcciones_pendientes:
        _imprimir_lista_truncada(
            correcciones_pendientes,
            lambda c: f"   * {c['n_ref']} / {c['campo']}: '{c['valor_anterior']}' -> '{c['valor_corregido']}'",
        )
        print("   Aplicar con: python driver.py confirmar --todos")
    else:
        print("   Sin hallazgos.")

    print("\n7. NOTAS DEL JSON (documentos nuevos de esta corrida)")
    if notas_documentos_nuevos:
        _imprimir_lista_truncada(
            notas_documentos_nuevos, lambda n: f"   * {n['n_ref']} ({n['archivo']}): {n['notas']}"
        )
    else:
        print("   Sin hallazgos.")

    imprimir_informe_hallazgos(registro_errores, duplicados_evitados)

    print("\n" + "-" * 70)
    print("  RESUMEN FINAL")
    print("-" * 70)
    abiertos_ahora = hallazgos_abiertos(registro_errores)
    print(f"  {'Documentos nuevos registrados:':<44} {registrados_ok}")
    print(f"  {'Documentos omitidos (ya registrados):':<44} {len(omitidos)}")
    print(f"  {'Copias exactas evitadas (auto-resueltas):':<44} {len(duplicados_evitados)}")
    print(f"  {'Limitaciones (faltan datos en JSON):':<44} {len(limitaciones)}")
    print(f"  {'Archivos renombrados/convertidos:':<44} {renombrados}")
    print(f"  {'Correcciones manuales pendientes de confirmar:':<44} {len(correcciones_pendientes)}")
    print(f"  {'Hallazgos abiertos (error/revisar/estimado):':<44} "
          f"{len(abiertos_ahora)} "
          f"({sum(1 for e in abiertos_ahora if e['severidad'] == 'error')}/"
          f"{sum(1 for e in abiertos_ahora if e['severidad'] == 'revisar')}/"
          f"{sum(1 for e in abiertos_ahora if e['severidad'] == 'estimado')})")
    _informe_etapas(time.perf_counter() - inicio_run)
    print("\n" + "=" * 70)


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == "--confirmar":
        resto = _sys.argv[2:]
        if not resto:
            confirmar_correcciones(None)
        elif resto == ["--todos"]:
            confirmar_correcciones("TODOS")
        else:
            confirmar_correcciones(resto)
    else:
        _pais = "CL"
        if "--pais" in _sys.argv:
            _idx = _sys.argv.index("--pais")
            _pais = _sys.argv[_idx + 1]
        main(pais=_pais)
