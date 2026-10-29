# -*- coding: utf-8 -*-
"""
carpetas_proyecto.py -- La carpeta de facturas de cada proyecto adjudicado, y
el acceso directo «Facturas del proyecto» de Gestión de Proyectos a ella.

Pedido del usuario (2026-10-28): cuando un proyecto se adjudica o pasa a
ejecución (en el Formulador o en el Portal), que se cree su carpeta para
recibir las facturas del Centro de Costos aunque todavía no haya ninguna; y
que la carpeta del proyecto en «Gestión de Proyectos» tenga «Facturas del
proyecto», un acceso directo a esa carpeta del Centro de Costos.

Primero fue una carpeta común que este paso copiaba al Centro de Costos; el
2026-10-29 el usuario la vio vacía y sin enlace con las facturas y eligió un
acceso directo web: ``Facturas del proyecto.url`` abre en el navegador la
carpeta del proyecto en SharePoint, con las facturas que ya tiene, y lo que
se sube ahí entra directo al Centro de Costos. Un ``.lnk`` no sirve: guarda la
ruta de OneDrive de un solo computador, y el sitio del Centro de Costos no
está sincronizado en todos. La dirección web es la misma en todos (necesita
acceso al sitio).

Este paso corre en el equipo que tiene el sitio sincronizado y hace dos cosas:

1. **Crea la carpeta del Centro de Costos** («Facturas y Boletas/<país>/
   <N°. Nombre>») de cada proyecto que se adjudica: el Formulador lo marca
   «Adjudicada», la Planilla lo pasa a «Adjudicado» o aparece en el Análisis
   Financiero con su N°. También de cada carpeta de la raíz de Gestión que ya
   tiene «Formulación» (la arma QUEMPIN.exe al pasar la oferta a Gestión).
   Solo si no hay ya una carpeta con ese N°. Lo que estaba adjudicado la
   primera vez que corrió este paso queda anotado como conocido y no se toca:
   muchas de esas carpetas existen sin N° («UMAG», «H2 Green») y crear otra
   las duplicaría.
2. **Deja «Facturas del proyecto.url»** en cada carpeta de proyecto de la raíz
   de Gestión con carpeta en el Centro de Costos. Si la carpeta del CC cambia,
   lo actualiza; si alguien lo borra, no vuelve. Una carpeta «Facturas del
   proyecto» vacía (la versión anterior) se reemplaza; con archivos no se toca
   y se avisa, para pasarlos a mano al Centro de Costos.

Una carpeta del Centro de Costos sin N° («H2 Green») no se renombra para
ponérselo: el Centro de Costos reconoce las facturas ya registradas por
«carpeta\\archivo» (Archivo origen) y con otro nombre las tomaría por nuevas.
Se anota en ``equivalencias`` del estado, {"281": "Chile/H2 Green"}, y cuenta
como la carpeta de ese N° (pedido del usuario, 2026-10-29).

Lo que hizo queda en ``carpetas_proyecto_estado.json`` (junto a este archivo,
gitignoreado).
"""

import json
import os
import re
import stat
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import documentos_cc
import formulaciones
import intercambio

SUB_FACTURAS = "Facturas del proyecto"
ACCESO_FACTURAS = SUB_FACTURAS + ".url"
SUB_FORMULACION = "Formulación"           # la misma de Sistema QUEMPIN app/carpetas.py
# La carpeta «Facturas y Boletas» en SharePoint (la misma de Centro de Costos/
# Visualizador Web/build_visualizador.py, que abre cada documento desde el tablero)
SHAREPOINT = "https://quempinspa2020.sharepoint.com"
RUTA_WEB_FACTURAS = ("Documentos compartidos", "Centro de Costos", "Facturas y Boletas")
RUTA_ESTADO = Path(__file__).resolve().parent / "carpetas_proyecto_estado.json"
LARGO_NOMBRE = 80
_CON_NUMERO = re.compile(r"^\s*(\d{1,4})\s*[.\-_)]\s*(.*)$")
_PROHIBIDOS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _req(valor) -> str | None:
    texto = str(valor or "").strip()
    return str(int(texto)) if texto.isdigit() and int(texto) > 0 else None


def _clave(nombre: str) -> str:
    return unicodedata.normalize("NFC", nombre).strip().casefold()


def nombre_carpeta(req: str, nombre: str) -> str:
    """«N°. Nombre» apto para una carpeta: sin caracteres que Windows no
    acepta, sin el N° repetido y de largo razonable."""
    nombre = unicodedata.normalize("NFC", str(nombre or ""))
    m = _CON_NUMERO.match(nombre)
    if m and _req(m.group(1)) == req:
        nombre = m.group(2)
    nombre = re.sub(r"\s+", " ", _PROHIBIDOS.sub(" ", nombre)).strip(" .")
    completo = f"{req}. {nombre}" if nombre else f"{req}. Proyecto"
    return completo[:LARGO_NOMBRE].rstrip(" .")


def _pais(texto) -> str:
    t = _clave(str(texto or ""))
    return "PE" if t.startswith(("perú", "peru")) or t == "pe" else "CL"


# ── QUÉ ESTÁ ADJUDICADO ──────────────────────────────────────────────────────

def ganados(requerimientos: list[dict], proyectos_af: list[dict], repositorio: list[dict]) -> dict[str, dict]:
    """{req: {'nombre', 'pais'}} de lo adjudicado o en ejecución, con el mejor
    nombre que se tenga: la carpeta de la oferta, el código del Formulador
    («N°. Nombre»), el título de la Planilla o el nombre del Análisis."""
    salida: dict[str, dict] = {}

    def anotar(req, nombre, pais="CL", fuerza=0):
        if not req:
            return
        previo = salida.get(req)
        if previo is None or fuerza > previo["fuerza"]:
            salida[req] = {"nombre": nombre_carpeta(req, nombre), "pais": pais, "fuerza": fuerza}

    for p in proyectos_af:
        anotar(_req(p.get("req")), p.get("nombre"), _pais(p.get("pais")), 1)
    for r in requerimientos:
        if r.get("estado") == "Adjudicado":
            anotar(_req(r.get("numero")), r.get("titulo"), "CL", 2)
    for item in repositorio:
        d = item.get("datos") or {}
        if d.get("eliminado") or d.get("estado") != "Adjudicada":
            continue
        v = d.get("vinculos") or {}
        req = v.get("requerimiento")
        req = _req(req.get("numero") if isinstance(req, dict) else req)
        carpeta = (v.get("carpetaOferta") or {}).get("nombre")
        codigo = str(d.get("codigo") or "")
        pais = _pais((v.get("controlDocumentos") or {}).get("pais") or carpeta or codigo)
        if carpeta and _req((_CON_NUMERO.match(carpeta) or [None, None])[1]) == req:
            anotar(req, carpeta, pais, 4)
        elif _req((_CON_NUMERO.match(codigo) or [None, None])[1]) == req:
            anotar(req, codigo, pais, 3)
        else:
            anotar(req, d.get("titulo"), pais, 3)
    for v in salida.values():
        v.pop("fuerza")
    return salida


# ── LAS CARPETAS ─────────────────────────────────────────────────────────────

def carpetas_cc(raices: dict[str, Path], equivalencias: dict | None = None) -> dict[str, Path]:
    """{req: carpeta} de «Facturas y Boletas/<país>/» con N° adelante (Chile
    primero), y las sin N° anotadas en 'equivalencias' ({req: «Chile/Nombre»})."""
    salida: dict[str, Path] = {}
    nombres_pais = {Path(b).name.casefold(): p for p, b in raices.items() if b is not None}
    for req, rel in (equivalencias or {}).items():
        pais, _, nombre = str(rel).partition("/")
        base = raices.get(nombres_pais.get(pais.casefold(), ""))
        if _req(req) and base is not None and Path(base).is_dir():
            carpeta = next((h for h in documentos_cc._subcarpetas(Path(base)) if _clave(h.name) == _clave(nombre)), None)
            if carpeta is not None:
                salida[_req(req)] = carpeta
    for pais in ("CL", "PE"):
        base = raices.get(pais)
        if base is None or not Path(base).is_dir():
            continue
        for h in documentos_cc._subcarpetas(Path(base)):
            m = _CON_NUMERO.match(h.name)
            if m and _req(m.group(1)):
                salida.setdefault(_req(m.group(1)), h)
    return salida


def carpetas_gestion(gestion: Path | None) -> list[Path]:
    """Las carpetas de proyecto con N° de la raíz de Gestión (las en curso;
    las de los grupos «0 …» ya se entregaron)."""
    if gestion is None or not Path(gestion).is_dir():
        return []
    return [h for h in documentos_cc._subcarpetas(Path(gestion)) if _req((_CON_NUMERO.match(h.name) or [None, None])[1])]


def _req_de(carpeta: Path) -> str:
    return _req(_CON_NUMERO.match(carpeta.name).group(1))


def _hija(carpeta: Path, nombre: str) -> Path | None:
    try:
        return next((h for h in carpeta.iterdir() if _clave(h.name) == _clave(nombre)), None)
    except OSError:
        return None


def enlace_web(carpeta_cc: Path) -> str:
    """La dirección de la carpeta del Centro de Costos en SharePoint:
    …/Facturas y Boletas/<país>/<carpeta>."""
    partes = (*RUTA_WEB_FACTURAS, carpeta_cc.parent.name, carpeta_cc.name)
    return SHAREPOINT + "/" + "/".join(quote(unicodedata.normalize("NFC", p), safe="") for p in partes)


def contenido_acceso(url: str) -> bytes:
    """Un acceso directo de Internet de Windows (.url): solo ASCII, CRLF."""
    return f"[InternetShortcut]\r\nURL={url}\r\n".encode("ascii")


def url_de_acceso(ruta: Path) -> str | None:
    try:
        for linea in ruta.read_text(encoding="ascii", errors="replace").splitlines():
            if linea.startswith("URL="):
                return linea[4:].strip()
    except OSError:
        pass
    return None


def _vacia(carpeta: Path) -> bool:
    """Sin nada más que el desktop.ini que pone Windows u OneDrive."""
    try:
        return all(h.is_file() and h.name.lower() == "desktop.ini" for h in carpeta.iterdir())
    except OSError:
        return False


def _quitar(carpeta: Path) -> bool:
    """Borra la carpeta vacía. OneDrive deja las carpetas sincronizadas con el
    atributo «solo lectura», que en Windows impide borrarlas: se le quita antes."""
    try:
        for h in carpeta.iterdir():
            os.chmod(h, stat.S_IWRITE)
            h.unlink()
        os.chmod(carpeta, stat.S_IWRITE)
        carpeta.rmdir()
        return True
    except OSError:
        return False


# ── EL PASO ──────────────────────────────────────────────────────────────────

def leer_estado(ruta: Path = RUTA_ESTADO) -> dict:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar_estado(estado: dict, ruta: Path = RUTA_ESTADO) -> None:
    temporal = Path(ruta).with_suffix(".tmp")
    temporal.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(temporal, ruta)


def _datos(raiz, nombre) -> dict:
    sobre = intercambio.leer_publicacion(raiz, nombre)
    return sobre.get("datos") if isinstance(sobre, dict) and isinstance(sobre.get("datos"), dict) else {}


def atender(raiz: Path, raices: dict[str, Path], gestion: Path | None, ruta_estado: Path = RUTA_ESTADO) -> dict:
    """Las dos cosas del docstring. 'raices' = {'CL': .../Chile, 'PE': .../Perú}.
    Devuelve {'creadasCC', 'accesos', 'conArchivos', 'sinQuitar'}."""
    estado = leer_estado(ruta_estado)
    r = {"creadasCC": [], "accesos": [], "conArchivos": [], "sinQuitar": []}
    if not any(b is not None and Path(b).is_dir() for b in raices.values()):
        return r           # el sitio del Centro de Costos no está en este equipo: nada que hacer
    hoy = datetime.now().isoformat(timespec="seconds")
    adjudicados = ganados(_datos(raiz, "requerimientos").get("requerimientos") or [],
                          _datos(raiz, "analisis-financiero").get("proyectos") or [],
                          formulaciones.leer_repositorio(raiz))
    en_cc = carpetas_cc(raices, estado.get("equivalencias"))
    en_gestion = carpetas_gestion(gestion)

    def crear_cc(req, nombre, pais):
        base = raices.get(pais) if raices.get(pais) is not None and Path(raices[pais]).is_dir() else raices.get("CL")
        if base is None or not Path(base).is_dir():
            return
        destino = Path(base) / nombre
        destino.mkdir(exist_ok=True)
        en_cc[req] = destino
        estado.setdefault("creadasCC", {})[req] = {"carpeta": f"{Path(base).name}/{nombre}", "fecha": hoy}
        r["creadasCC"].append(f"{Path(base).name}/{nombre}")

    # 1. Lo recién adjudicado (la primera vez, todo queda como conocido)
    primera = "conocidos" not in estado
    conocidos = set(estado.get("conocidos") or [])
    for req, g in sorted(adjudicados.items(), key=lambda par: int(par[0])):
        if req in conocidos:
            continue
        if not primera and req not in en_cc:
            crear_cc(req, g["nombre"], g["pais"])
        conocidos.add(req)
    estado["conocidos"] = sorted(conocidos, key=int)
    # ... y lo que QUEMPIN.exe ya pasó a Gestión (tiene «Formulación»)
    for carpeta in en_gestion:
        req = _req_de(carpeta)
        if req not in en_cc and _hija(carpeta, SUB_FORMULACION) is not None:
            g = adjudicados.get(req) or {}
            crear_cc(req, carpeta.name, g.get("pais") or _pais(carpeta.name))

    # 2. «Facturas del proyecto.url» en lo que está en curso y tiene carpeta en el CC
    accesos = estado.setdefault("accesos", {})
    for carpeta in en_gestion:
        req = _req_de(carpeta)
        if req not in en_cc:
            continue
        url = enlace_web(en_cc[req])
        vieja = _hija(carpeta, SUB_FACTURAS)
        if vieja is not None and vieja.is_dir():
            if not _vacia(vieja):
                r["conArchivos"].append(carpeta.name)
            elif not _quitar(vieja):
                r["sinQuitar"].append(carpeta.name)
        archivo = _hija(carpeta, ACCESO_FACTURAS)
        if archivo is None and req in accesos:
            continue       # lo borraron: no vuelve
        if archivo is not None and url_de_acceso(archivo) == url:
            accesos.setdefault(req, url)
            continue
        (archivo or carpeta / ACCESO_FACTURAS).write_bytes(contenido_acceso(url))
        accesos[req] = url
        r["accesos"].append(carpeta.name)

    guardar_estado(estado, ruta_estado)
    return r


def enlaces_web(raices: dict[str, Path], ruta_estado: Path = RUTA_ESTADO) -> dict[str, list[str]]:
    """Para proyectos.json: {req: [dirección web de su carpeta del Centro de Costos]}."""
    return {req: [enlace_web(c)] for req, c in carpetas_cc(raices, leer_estado(ruta_estado).get("equivalencias")).items()}
