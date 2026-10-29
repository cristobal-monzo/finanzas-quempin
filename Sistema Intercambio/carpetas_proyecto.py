# -*- coding: utf-8 -*-
"""
carpetas_proyecto.py -- La carpeta de facturas de cada proyecto adjudicado, y
«Facturas del proyecto» de Gestión de Proyectos conectada al Centro de Costos.

Pedido del usuario (2026-10-28): cuando un proyecto se adjudica o pasa a
ejecución (en el Formulador o en el Portal), que se cree su carpeta para
recibir las facturas del Centro de Costos aunque todavía no haya ninguna; y
que la carpeta del proyecto en «Gestión de Proyectos» tenga una subcarpeta
«Facturas del proyecto» por donde también se puedan ingresar facturas al
Centro de Costos. QUEMPIN.exe 1.3.15 arma esa carpeta al pasar la oferta a
Gestión (``Formulación/`` con la copia de la oferta y ``Facturas del
proyecto/``; Sistema QUEMPIN app/carpetas.py).

Un acceso directo no sirve: un ``.lnk`` guarda la ruta de OneDrive de un solo
computador y el sitio del Centro de Costos no está sincronizado en todos. Por
eso «Facturas del proyecto» es una carpeta común y este paso, que corre en el
equipo que sí tiene el sitio, hace tres cosas:

1. **Crea la carpeta del Centro de Costos** («Facturas y Boletas/<país>/
   <N°. Nombre>») de cada proyecto que se adjudica: el Formulador lo marca
   «Adjudicada», la Planilla lo pasa a «Adjudicado» o aparece en el Análisis
   Financiero con su N°. También de cada carpeta de Gestión que ya tiene
   «Facturas del proyecto». Solo si no hay ya una carpeta con ese N°. Lo que
   estaba adjudicado la primera vez que corrió este paso queda anotado como
   conocido y no se toca: muchas de esas carpetas existen sin N° («UMAG»,
   «H2 Green») y crear otra las duplicaría.
2. **Crea «Facturas del proyecto»** en cada carpeta de proyecto de la raíz de
   Gestión que ya tiene su carpeta en el Centro de Costos, una sola vez por
   proyecto: si alguien la borra, no vuelve.
3. **Copia al Centro de Costos** las facturas y boletas (pdf e imágenes) que
   se dejan en «Facturas del proyecto», también de los proyectos ya
   entregados (las facturas llegan tarde). Cada archivo se copia una vez,
   nunca se pisa uno que ya está (mismo contenido = repetido, mismo nombre =
   «(2)», como ``documentos_cc``) y espera ``MINUTOS_QUIETO`` desde su último
   cambio, por si todavía se está guardando. El original queda en Gestión.

Lo que hizo queda en ``carpetas_proyecto_estado.json`` (junto a este archivo,
gitignoreado: lleva nombres de proveedores).

Una carpeta del Centro de Costos sin N° («H2 Green») no se renombra para
ponérselo: el Centro de Costos reconoce las facturas ya registradas por
«carpeta\\archivo» (Archivo origen) y con otro nombre las tomaría por nuevas.
Se anota en ``equivalencias`` del mismo estado, {"281": "Chile/H2 Green"}, y
cuenta como la carpeta de ese N° (pedido del usuario, 2026-10-29).
"""

import json
import os
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import documentos_cc
import formulaciones
import intercambio
import ubicacion

SUB_FACTURAS = "Facturas del proyecto"   # el mismo nombre de Sistema QUEMPIN app/carpetas.py
RUTA_ESTADO = Path(__file__).resolve().parent / "carpetas_proyecto_estado.json"
MINUTOS_QUIETO = 5
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


def carpetas_gestion(gestion: Path | None) -> list[tuple[str, Path, bool]]:
    """[(req, carpeta, en_la_raiz)] de las carpetas de proyecto con N° de
    Gestión: las de la raíz (en curso) y las de los grupos «0 …»
    (entregados), un nivel."""
    salida = []
    if gestion is None or not Path(gestion).is_dir():
        return salida

    def recorrer(carpeta: Path, raiz: bool):
        for h in documentos_cc._subcarpetas(carpeta):
            m = _CON_NUMERO.match(h.name)
            if m and _req(m.group(1)):
                salida.append((_req(m.group(1)), h, raiz))
            elif raiz and h.name.startswith("0 "):
                recorrer(h, False)

    recorrer(Path(gestion), True)
    return salida


def subcarpeta_facturas(proyecto: Path) -> Path | None:
    return next((h for h in documentos_cc._subcarpetas(proyecto) if _clave(h.name) == _clave(SUB_FACTURAS)), None)


# ── LA COPIA ─────────────────────────────────────────────────────────────────

def _archivos(carpeta: Path) -> list[Path]:
    salida = []
    for base, dirs, nombres in os.walk(carpeta):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for n in sorted(nombres):
            if n.startswith((".", "~$")) or Path(n).suffix.lower() not in documentos_cc.EXTENSIONES:
                continue
            salida.append(Path(base) / n)
    return salida


def copiar_facturas(req: str, origen: Path, destino: Path, estado: dict, ahora: float) -> list[str]:
    """Copia a 'destino' lo nuevo de 'origen'. Devuelve el detalle de lo copiado."""
    vistos = estado.setdefault("vistos", {})
    copiados = estado.setdefault("copiados", {})
    detalle = []
    for archivo in _archivos(origen):
        rel = f"{req}/{archivo.relative_to(origen).as_posix()}"
        try:
            st = archivo.stat()
        except OSError:
            continue
        if ahora - st.st_mtime < MINUTOS_QUIETO * 60 or st.st_size == 0:
            continue       # todavía se está guardando (o subiendo de otro equipo)
        firma = [st.st_size, st.st_mtime_ns]
        previo = vistos.get(rel)
        if previo and previo[:2] == firma and previo[2] in copiados:
            continue
        try:
            sha = documentos_cc._sha256(archivo)
        except OSError:
            continue       # OneDrive no lo pudo bajar: en la próxima vuelta
        vistos[rel] = firma + [sha]
        if sha in copiados:
            continue
        a = {"nombre": archivo.name, "bytes": st.st_size, "sha256": sha}
        repetido = documentos_cc._repetido(destino, a)
        if repetido is not None:
            guardado = repetido.name
            detalle.append(f"{archivo.name}: ya estaba en {destino.name} como «{guardado}»")
        else:
            final = documentos_cc._libre(destino, archivo.name)
            documentos_cc._copiar(archivo, final, sha)
            guardado = final.name
            detalle.append(f"{archivo.name} → {destino.parent.name}/{destino.name}/{guardado}")
        copiados[sha] = {"req": req, "desde": rel, "guardado": f"{destino.parent.name}/{destino.name}/{guardado}",
                         "repetido": repetido is not None, "fecha": datetime.now().isoformat(timespec="seconds")}
    return detalle


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


def atender(raiz: Path, raices: dict[str, Path], gestion: Path | None,
            ruta_estado: Path = RUTA_ESTADO, ahora: float | None = None) -> dict:
    """Las tres cosas del docstring. 'raices' = {'CL': .../Chile, 'PE': .../Perú}.
    Devuelve {'creadasCC', 'creadasGestion', 'copiados', 'sinCarpetaCC', 'detalle'}."""
    ahora = time.time() if ahora is None else ahora
    estado = leer_estado(ruta_estado)
    r = {"creadasCC": [], "creadasGestion": [], "copiados": 0, "sinCarpetaCC": [], "detalle": []}
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
    # ... y lo que ya tiene «Facturas del proyecto» en Gestión (QUEMPIN.exe 1.3.15 o a mano)
    for req, carpeta, en_raiz in en_gestion:
        if en_raiz and req not in en_cc and subcarpeta_facturas(carpeta) is not None:
            g = adjudicados.get(req) or {}
            crear_cc(req, carpeta.name, g.get("pais") or _pais(carpeta.name))

    # 2. «Facturas del proyecto» en lo que está en curso y ya tiene carpeta en el CC (una vez)
    hechas = estado.setdefault("facturasGestion", {})
    for req, carpeta, en_raiz in en_gestion:
        if not en_raiz or req not in en_cc or req in hechas:
            continue
        if subcarpeta_facturas(carpeta) is None:
            (carpeta / SUB_FACTURAS).mkdir(exist_ok=True)
            r["creadasGestion"].append(carpeta.name)
        hechas[req] = {"carpeta": carpeta.name, "fecha": hoy}

    # 3. Lo que se dejó en «Facturas del proyecto» → Centro de Costos
    for req, carpeta, en_raiz in en_gestion:
        sub = subcarpeta_facturas(carpeta)
        if sub is None:
            continue
        if req not in en_cc:
            if _archivos(sub):
                r["sinCarpetaCC"].append(carpeta.name)
            continue
        detalle = copiar_facturas(req, sub, en_cc[req], estado, ahora)
        r["copiados"] += sum(1 for d in detalle if "→" in d)
        r["detalle"].extend(detalle)

    guardar_estado(estado, ruta_estado)
    return r


def con_facturas(gestion: Path | None, rutas: dict[str, list[str]]) -> dict[str, list[str]]:
    """Para proyectos.json: {req: [«…/<proyecto>/Facturas del proyecto»]} de
    las carpetas de Gestión (rutas relativas) que la tienen."""
    salida: dict[str, list[str]] = {}
    if gestion is None or not Path(gestion).is_dir():
        return salida
    for req, lista in (rutas or {}).items():
        for rel in lista:
            sub = subcarpeta_facturas(Path(gestion) / rel)
            if sub is not None:
                salida.setdefault(req, []).append(f"{rel}/{sub.name}")
    return salida
