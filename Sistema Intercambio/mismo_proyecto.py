# -*- coding: utf-8 -*-
"""
mismo_proyecto.py -- ¿Una ficha del Análisis Financiero y un N° de la Planilla
son el mismo proyecto? Lo dicen las carpetas del Centro de Costos.

Caso real (2026-11-03, pedido del usuario: que no vuelva a pasar): la ficha
«UMAG» del Análisis Financiero es el proyecto «UMAG Linea de H2» (entregado en
2026; su carpeta de facturas es «UMAG»). El 2026-10-13 una revisión le puso el
N° 280, que es otro proyecto, «280. UMAG - Conexión y PH Lab 1», con su propia
carpeta. Desde ahí el Portal le mostraba al 280 los costos del otro, y el
Formulador le mandó el presupuesto del 280 a la ficha antigua.

La regla: cada carpeta de proyecto del Centro de Costos es un proyecto. Si la
ficha tiene su carpeta con facturas («UMAG», 45) y el N° tiene otra («280. …»),
son dos proyectos y no se unen. Sin alguna de las dos no se sabe, y no se frena
nada.

La ficha se reconoce por su Nombre, que el Análisis Financiero toma del
Centro de Costos: el nombre de la carpeta sin su N° (``nombre_de_carpeta``,
copia de ``normalizar_nombre_proyecto`` del Centro de Costos; un test compara
las dos).

Lo usan el Análisis Financiero (no acepta un envío del N° X a la ficha de otra
carpeta) y el procesador (``proyectos.py``: no une ese TAG con ese N° y lo
publica como conflicto).
"""

import re
import unicodedata


def nombre_de_carpeta(nombre: str) -> str:
    """«280. UMAG - Conexión y PH Lab 1» → «UMAG - Conexión y PH Lab1»: lo
    mismo que hace el Centro de Costos con la carpeta (sin el N° adelante y
    con «palabra número» del final junto)."""
    nombre = str(nombre or "")
    limpio = re.sub(r"^\d+[.\-_]\s*", "", nombre).strip()
    limpio = re.sub(r"^(\S.*\S|\S)\s+(\d+)$", r"\1\2", limpio)
    return limpio or nombre


def clave(nombre) -> str:
    """Para comparar nombres: sin tildes, sin mayúsculas, sin espacios de más."""
    texto = unicodedata.normalize("NFKD", str(nombre or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def req_de_carpeta(nombre) -> str | None:
    m = re.match(r"^\s*(\d+)\s*[.\-_]", str(nombre or ""))
    return str(int(m.group(1))) if m else None


def _req(valor) -> str | None:
    texto = str(valor if valor is not None else "").strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return str(int(texto)) if texto.isdigit() else None


def carpeta_ajena(nombre_ficha, req, carpetas) -> dict | None:
    """Si la ficha (por su nombre) tiene su propia carpeta y el N° 'req' tiene
    otra, {'ficha': carpeta de la ficha, 'req': carpeta del N°}; si no, None.
    carpetas: [{'nombre': nombre de la carpeta, 'req': N° o None}] (lo que
    publica centro-costos-carpetas, de Chile)."""
    req = _req(req)
    if not req or not clave(nombre_ficha):
        return None
    del_req, de_ficha = [], []
    for c in carpetas or []:
        if not isinstance(c, dict) or not c.get("nombre"):
            continue
        n = _req(c.get("req")) or req_de_carpeta(c["nombre"])
        if n == req:
            del_req.append(c["nombre"])
        # Solo una carpeta con facturas es otro proyecto: una vacía puede ser la
        # que quedó cuando el mismo proyecto se pasó a su carpeta con N° (KPH2:
        # «Instalación H2 KeyProcess» vacía y las facturas en «289. KeyProcess»).
        if clave(nombre_de_carpeta(c["nombre"])) == clave(nombre_ficha) and (c.get("documentos") or 0) > 0:
            de_ficha.append(c["nombre"])
    if not del_req or not de_ficha or set(de_ficha) & set(del_req):
        return None
    return {"ficha": de_ficha[0], "req": del_req[0]}


def motivo(tag, nombre_ficha, req, ajena: dict) -> str:
    return (f"La ficha {tag} «{nombre_ficha}» y el N° {_req(req)} son proyectos distintos: cada uno tiene su "
            f"carpeta en el Centro de Costos («{ajena['ficha']}» y «{ajena['req']}»). El N° {_req(req)} "
            f"necesita su propia ficha, con el TAG de sus facturas.")
