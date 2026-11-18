# -*- coding: utf-8 -*-
"""
documentos_cc.py -- Los documentos que se suben desde el Portal («Subir
documentos») llegan a la carpeta del Centro de Costos.

Pedido del usuario (2026-10-23): otra manera de subir facturas y boletas al
Centro de Costos, eligiendo el proyecto en el Portal, a través de la carpeta
de intercambio. Así no hace falta tener sincronizado el sitio del Centro de
Costos en cada equipo: basta la biblioteca «Formulación de proyectos».

El Portal escribe primero los archivos en ``buzon/adjuntos/<id>/`` y después
el mensaje ``documento-cc``. OneDrive puede traerlos en otro orden, así que un
mensaje cuyos archivos todavía no llegan (o llegan con otro tamaño o sha256)
**espera** en el buzón; a los ``DIAS_ESPERA`` días se rechaza.

Cada archivo se copia a «Facturas y Boletas/<país>/<carpeta>/» del sitio del
Centro de Costos, la misma carpeta que lee ``/Registro_Centro_de_Costos``: de
ahí en adelante es un documento pendiente más, igual que uno subido a
SharePoint a mano. Nunca se pisa un archivo: si ya hay uno con el mismo
contenido se informa como repetido, y si solo coincide el nombre se guarda
como «nombre (2).pdf».

También publica ``centro-costos-carpetas.json``: las carpetas de proyecto
que existen, para que el Portal ofrezca dónde subir.

Rendiciones (2026-11-18): un ``documento-cc`` que trae ``rendicion`` viene de
«Rendiciones» del Portal, con lo que una persona revisó de cada documento.
Además de copiar los archivos, el procesador agrega esos datos a
``rendiciones.json``, con el nombre con que quedó cada archivo en la carpeta,
para que ``/Registro_Centro_de_Costos`` los use al registrar
(``driver.py rendiciones``). Un documento de la rendición que no viene en
``archivos`` rechaza el mensaje.
"""

import hashlib
import os
import re
import shutil
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import esquemas
import intercambio

TIPO = "documento-cc"
DESTINO = "centro-costos"
PUBLICACION = "centro-costos-carpetas"
PUBLICACION_RENDICIONES = "rendiciones"
MAX_RENDICIONES = 300
CARPETA_ADJUNTOS = "adjuntos"
DIAS_ESPERA = 7
EXTENSIONES = {".pdf", ".png", ".jpg", ".jpeg", ".heic"}   # las de auditor_centro_costos.EXTENSIONES_VALIDAS
_CON_NUMERO = re.compile(r"^\s*(\d{1,4}t?)\s*[.\-_)]", re.IGNORECASE)


def _clave(nombre: str) -> str:
    return unicodedata.normalize("NFC", nombre).strip().casefold()


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _subcarpetas(base: Path) -> list[Path]:
    try:
        return sorted((h for h in base.iterdir() if h.is_dir() and not h.name.startswith(".")), key=lambda h: _clave(h.name))
    except OSError:
        return []


def _carpeta_existente(base: Path, nombre: str) -> Path | None:
    """La carpeta del proyecto sin distinguir mayúsculas ni la forma Unicode
    del nombre (macOS/OneDrive pueden traer «Conchalí» descompuesto)."""
    buscado = _clave(nombre)
    return next((h for h in _subcarpetas(base) if _clave(h.name) == buscado), None)


def _enviado(mensaje: dict) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(mensaje["origen"]["enviado"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _libre(carpeta: Path, nombre: str) -> Path:
    destino = carpeta / nombre
    n = 2
    while destino.exists():
        destino = carpeta / f"{Path(nombre).stem} ({n}){Path(nombre).suffix}"
        n += 1
    return destino


def _repetido(carpeta: Path, archivo: dict) -> Path | None:
    """Un archivo de la carpeta con el mismo contenido. Solo se lee el de
    igual tamaño (el tamaño no baja el archivo de OneDrive; leerlo sí)."""
    for h in carpeta.iterdir():
        try:
            if h.is_file() and h.stat().st_size == archivo["bytes"] and _sha256(h) == archivo["sha256"]:
                return h
        except OSError:
            continue
    return None


def _faltantes(adjuntos: Path, archivos: list[dict]) -> list[str]:
    salida = []
    for a in archivos:
        ruta = adjuntos / a["nombre"]
        try:
            if ruta.stat().st_size != a["bytes"] or _sha256(ruta) != a["sha256"]:
                salida.append(f"{a['nombre']} (todavía incompleto)")
        except OSError:
            salida.append(a["nombre"])
    return salida


def _copiar(origen: Path, destino: Path, sha: str) -> None:
    temporal = destino.with_name(f".{destino.name}.subiendo")
    shutil.copyfile(origen, temporal)
    if _sha256(temporal) != sha:
        temporal.unlink(missing_ok=True)
        raise OSError(f"la copia de {origen.name} no quedó igual al original")
    os.replace(temporal, destino)


def atender(raiz: Path, raices: dict[str, Path], ahora: datetime | None = None) -> dict:
    """Atiende los documento-cc del buzón. 'raices' = {'CL': .../Chile, 'PE': .../Perú}.
    Devuelve {'aplicados', 'archivos', 'esperan', 'rechazados'}."""
    ahora = ahora or datetime.now(timezone.utc)
    raiz = Path(raiz)
    mensajes, _ = intercambio.leer_buzon(raiz, destino=DESTINO, tipo=TIPO)
    r = {"aplicados": 0, "archivos": 0, "esperan": 0, "rechazados": 0}

    for m in mensajes:
        adjuntos = raiz / intercambio.CARPETA_BUZON / CARPETA_ADJUNTOS / m["id"]

        def rechazar(motivo: str):
            intercambio.archivar(raiz, m, "rechazado", [motivo])
            shutil.rmtree(adjuntos, ignore_errors=True)
            r["rechazados"] += 1

        errores = esquemas.validar_mensaje(m)
        if errores:
            rechazar("mensaje inválido: " + "; ".join(errores[:3]))
            continue
        if m.get("rendicion"):
            nombres = {_clave(a["nombre"]) for a in m["archivos"]}
            ajenos = [d["archivo"] for d in m["rendicion"]["documentos"] if _clave(d["archivo"]) not in nombres]
            if ajenos:
                rechazar("la rendición nombra documentos que no vienen en el envío: " + ", ".join(ajenos[:3]))
                continue
        base = raices.get(m["pais"])
        if base is None or not Path(base).is_dir():
            r["esperan"] += 1      # el sitio del Centro de Costos no está sincronizado en este equipo
            continue
        enviado = _enviado(m)
        vencido = enviado is not None and ahora - enviado > timedelta(days=DIAS_ESPERA)
        faltan = _faltantes(adjuntos, m["archivos"])
        if faltan:
            if vencido:
                rechazar(f"después de {DIAS_ESPERA} días no llegaron: " + ", ".join(faltan))
            else:
                r["esperan"] += 1
            continue
        carpeta = _carpeta_existente(Path(base), m["carpeta"])
        if carpeta is None:
            if not m.get("nueva"):
                rechazar(f"no existe la carpeta «{m['carpeta']}» en Facturas y Boletas/{Path(base).name}")
                continue
            carpeta = Path(base) / m["carpeta"].strip()
            carpeta.mkdir()

        guardados, detalle = [], []
        for a in m["archivos"]:
            previo = _repetido(carpeta, a)
            if previo is not None:
                guardados.append({"nombre": a["nombre"], "guardado": previo.name, "repetido": True})
                detalle.append(f"{a['nombre']}: ya estaba como «{previo.name}»")
                continue
            destino = _libre(carpeta, a["nombre"])
            _copiar(adjuntos / a["nombre"], destino, a["sha256"])
            guardados.append({"nombre": a["nombre"], "guardado": destino.name, "repetido": False})
            detalle.append(f"{a['nombre']} → {carpeta.name}/{destino.name}")
            r["archivos"] += 1
        if m.get("rendicion"):
            # Los documentos ya están en su carpeta: si la publicación falla, se archiva igual (quien registra lee la
            # foto, como con cualquier documento) y el detalle lo dice.
            try:
                publicar_rendicion(raiz, m, carpeta.name, guardados)
            except (OSError, ValueError, intercambio.PublicacionInvalida) as e:
                detalle.append(f"rendiciones.json no se actualizó: {e}")
        intercambio.archivar(raiz, m, "aplicado", detalle,
                             {"carpeta": f"{Path(base).name}/{carpeta.name}", "archivos": guardados})
        shutil.rmtree(adjuntos, ignore_errors=True)
        r["aplicados"] += 1

    _limpiar_huerfanos(raiz, ahora)
    return r


# ── LAS RENDICIONES, PARA EL REGISTRO DEL CENTRO DE COSTOS ──────────────────

def publicar_rendicion(raiz: Path, mensaje: dict, carpeta: str, guardados: list[dict]) -> None:
    """Agrega a rendiciones.json los documentos de un documento-cc con «rendicion», con el nombre con que quedó
    cada uno en la carpeta. Idempotente: un archivo de la carpeta ya publicado no se repite (un reenvío trae los
    mismos archivos, que el paso anterior informa como repetidos con su nombre en la carpeta)."""
    previo = intercambio.leer_publicacion(raiz, PUBLICACION_RENDICIONES)
    lista = list(((previo or {}).get("datos") or {}).get("rendiciones") or [])
    ren = mensaje["rendicion"]
    entrada = next((x for x in lista if x.get("id") == ren["id"]), None)
    if entrada is None:
        entrada = {c: ren[c] for c in ("id", "numero", "tipo", "deudor", "periodo", "unidad", "total", "cantidad") if c in ren}
        origen = mensaje.get("origen") or {}
        if origen.get("usuario"):
            entrada["usuario"] = origen["usuario"]
        if origen.get("enviado"):
            entrada["enviado"] = origen["enviado"]
        entrada["documentos"] = []
        lista.append(entrada)
    guardado = {_clave(g["nombre"]): g for g in guardados}
    ya = {(d.get("pais"), _clave(d.get("carpeta", "")), _clave(d.get("archivo", ""))) for d in entrada["documentos"]}
    for doc in ren["documentos"]:
        g = guardado.get(_clave(doc["archivo"]))
        if g is None or (mensaje["pais"], _clave(carpeta), _clave(g["guardado"])) in ya:
            continue
        nuevo = {"pais": mensaje["pais"], "carpeta": carpeta, "archivo": g["guardado"], "mensaje": mensaje["id"]}
        if g.get("repetido"):
            nuevo["repetido"] = True
        nuevo.update({c: doc[c] for c in ("n", "tipo", "numero", "fecha", "proveedor", "rut", "detalle", "valor") if c in doc})
        entrada["documentos"].append(nuevo)
    entrada["documentos"].sort(key=lambda d: (d.get("n") or 0, d["archivo"]))
    lista.sort(key=lambda x: x.get("enviado") or "", reverse=True)
    intercambio.publicar(raiz, PUBLICACION_RENDICIONES, "procesador", {"rendiciones": lista[:MAX_RENDICIONES]})


def _limpiar_huerfanos(raiz: Path, ahora: datetime) -> None:
    """Adjuntos sin mensaje (el navegador se cerró antes de escribirlo): se
    borran a los DIAS_ESPERA días. Con mensaje en el buzón, nunca."""
    base = raiz / intercambio.CARPETA_BUZON / CARPETA_ADJUNTOS
    if not base.is_dir():
        return
    con_mensaje = {m.name.rsplit("_", 1)[-1][:-5] for m in (raiz / intercambio.CARPETA_BUZON).glob("*.json")}
    limite = (ahora - timedelta(days=DIAS_ESPERA)).timestamp()
    for carpeta in base.iterdir():
        try:
            if carpeta.is_dir() and carpeta.name not in con_mensaje and carpeta.stat().st_mtime < limite:
                shutil.rmtree(carpeta, ignore_errors=True)
        except OSError:
            pass


# ── LAS CARPETAS, PARA EL PORTAL ─────────────────────────────────────────────

def listar(base: Path | None) -> list[dict]:
    salida = []
    if base is None or not Path(base).is_dir():
        return salida
    for h in _subcarpetas(Path(base)):
        n = _CON_NUMERO.match(h.name)
        try:
            documentos = sum(1 for f in h.rglob("*") if f.is_file() and f.suffix.lower() in EXTENSIONES)
        except OSError:
            documentos = 0
        salida.append({"nombre": h.name, "req": (n.group(1).lower() if n.group(1)[-1:].lower() == "t" else str(int(n.group(1)))) if n else None, "documentos": documentos})
    return salida


def publicar_carpetas(raiz: Path, raices: dict[str, Path]) -> dict:
    datos = {"paises": {pais: listar(base) for pais, base in raices.items()}}
    intercambio.publicar(raiz, PUBLICACION, "procesador", datos)
    return {pais: len(lista) for pais, lista in datos["paises"].items()}
