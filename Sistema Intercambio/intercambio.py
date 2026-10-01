# -*- coding: utf-8 -*-
"""
intercambio.py -- Protocolo común para que las herramientas de QUEMPIN
(Formulador de proyectos, Centro de Costos, Análisis Financiero, Cotizador,
Flujo de Caja...) compartan información sin depender unas de otras.

No es un servidor ni una base de datos: es una carpeta sincronizada por
OneDrive con archivos JSON de formato común. Desde el 2026-09-30 está en la
biblioteca de SharePoint «Formulación de proyectos - Documentos», en
``.Herramientas formulación/Intercambio/``, para que todo el equipo tenga
acceso. Este módulo recibe la ruta; quien la ubica es cada herramienta. La puede leer y escribir un script de Python y también una página web
(el Formulador la abre con la API de acceso a archivos del navegador), sin
iniciar sesión en ningún servicio.

    Intercambio/
      intercambio.json     manifiesto: esquema y para qué es la carpeta
      LEEME.md             explicación para personas
      buzon/               mensajes que una herramienta le envía a otra
      procesado/AAAA-MM/   mensajes ya atendidos, con su resultado
      publicado/           lo que cada herramienta publica para las demás

Reglas (ver LEEME.md):

- Cada herramienta es dueña de sus datos y nunca escribe los archivos de
  otra. Para pedir un cambio deja un mensaje en ``buzon/``; el dueño decide
  si lo aplica y cómo.
- Un mensaje se atiende una sola vez: al atenderlo, su destinatario lo mueve
  a ``procesado/`` con el resultado. Si no puede decidir solo (por ejemplo,
  pisaría un valor escrito a mano), lo deja en el buzón y lo informa.
- Lo publicado se reemplaza completo en cada corrida, con escritura atómica
  (nunca queda un JSON a medio escribir si OneDrive sincroniza en ese
  momento).

Este módulo no conoce ningún tipo de mensaje en particular: solo el sobre
(esquema, id, tipo, origen, destino). Qué hace cada destinatario con cada
tipo vive en su propio módulo (ej. ``presupuestos_formulador.py`` en
Análisis Financiero).
"""

import json
import os
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path

ESQUEMA = "quempin.intercambio/1"
MANIFIESTO = "intercambio.json"
CARPETA_BUZON = "buzon"
CARPETA_PROCESADO = "procesado"
CARPETA_PUBLICADO = "publicado"

# Estados finales de un mensaje (los que lo mueven a procesado/). Un mensaje
# "pendiente" no tiene estado final: sigue en el buzón.
ESTADOS_FINALES = ("aplicado", "sin-cambios", "reemplazado", "rechazado", "descartado")

_ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


def ahora_iso() -> str:
    """Fecha y hora local con zona horaria, a segundos (2026-09-30T15:30:12-03:00)."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _escribir_json_atomico(ruta: Path, datos) -> None:
    """Escribe a un temporal en la misma carpeta y lo renombra encima: un
    lector (o OneDrive) nunca ve el archivo a medio escribir."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temporal, ruta)


def _leer_json(ruta: Path):
    with open(ruta, encoding="utf-8-sig") as f:
        return json.load(f)


# ── CARPETA ──────────────────────────────────────────────────────────────────

def asegurar_carpeta(raiz: Path) -> Path:
    """Crea la estructura (idempotente) y el manifiesto si falta. El
    Formulador reconoce la carpeta correcta por ese manifiesto."""
    raiz = Path(raiz)
    for sub in (CARPETA_BUZON, CARPETA_PROCESADO, CARPETA_PUBLICADO):
        (raiz / sub).mkdir(parents=True, exist_ok=True)
    manifiesto = raiz / MANIFIESTO
    if not manifiesto.exists():
        _escribir_json_atomico(manifiesto, {
            "esquema": ESQUEMA,
            "descripcion": (
                "Carpeta de intercambio de las herramientas de QUEMPIN. "
                "Ver LEEME.md. No editar ni mover estos archivos a mano."
            ),
            "carpetas": {
                CARPETA_BUZON: "Mensajes que una herramienta le envía a otra.",
                CARPETA_PROCESADO: "Mensajes ya atendidos, con su resultado.",
                CARPETA_PUBLICADO: "Lo que cada herramienta publica para las demás.",
            },
            "creado": ahora_iso(),
        })
    return raiz


def es_carpeta_de_intercambio(raiz: Path) -> bool:
    try:
        return _leer_json(Path(raiz) / MANIFIESTO).get("esquema", "").startswith("quempin.intercambio/")
    except (OSError, ValueError, AttributeError):
        return False


# ── MENSAJES ─────────────────────────────────────────────────────────────────

def validar_mensaje(mensaje) -> list[str]:
    """Errores del sobre del mensaje (vacío = válido). No valida el contenido
    propio de cada tipo: eso lo hace su destinatario."""
    if not isinstance(mensaje, dict):
        return ["no es un objeto JSON"]
    errores = []
    esquema = mensaje.get("esquema")
    if not isinstance(esquema, str) or not esquema.startswith("quempin.intercambio/"):
        errores.append("falta el esquema 'quempin.intercambio/…'")
    elif esquema != ESQUEMA:
        errores.append(f"versión de esquema no soportada: {esquema}")
    if not isinstance(mensaje.get("id"), str) or not _ID_VALIDO.match(mensaje["id"]):
        errores.append("falta un id válido (6 a 64 letras, números, - o _)")
    for campo in ("tipo", "destino"):
        if not isinstance(mensaje.get(campo), str) or not mensaje[campo].strip():
            errores.append(f"falta '{campo}'")
    origen = mensaje.get("origen")
    if not isinstance(origen, dict) or not isinstance(origen.get("herramienta"), str):
        errores.append("falta 'origen.herramienta'")
    elif not isinstance(origen.get("enviado"), str):
        errores.append("falta 'origen.enviado'")
    return errores


def nuevo_id() -> str:
    """24 caracteres hexadecimales, como los que genera el Formulador."""
    return secrets.token_hex(12)


def nombre_mensaje(mensaje: dict) -> str:
    """AAAAMMDD-HHMMSS_<herramienta>_<tipo>_<id>.json: el mismo nombre que da
    el Formulador (js/intercambio.js), así el buzón queda en orden de envío."""
    t = str(mensaje["origen"]["enviado"])[:19].replace("-", "").replace(":", "").replace("T", "-")
    return f"{t}_{mensaje['origen']['herramienta']}_{mensaje['tipo']}_{mensaje['id']}.json"


def enviar(raiz: Path, mensaje: dict) -> Path:
    """Deja un mensaje en el buzón (validado y con escritura atómica)."""
    errores = validar_mensaje(mensaje)
    if errores:
        raise ValueError("mensaje inválido: " + "; ".join(errores))
    ruta = Path(raiz) / CARPETA_BUZON / nombre_mensaje(mensaje)
    _escribir_json_atomico(ruta, _sin_privados(mensaje))
    return ruta


def _es_archivo_de_mensaje(ruta: Path) -> bool:
    # Chrome escribe primero a un «.crswap» y OneDrive/Office dejan «~$…» o
    # «.tmp»: nada de eso es un mensaje (todavía).
    nombre = ruta.name
    return (
        ruta.is_file() and nombre.lower().endswith(".json")
        and not nombre.startswith((".", "~$"))
    )


def leer_buzon(raiz: Path, destino: str | None = None, tipo: str | None = None):
    """Devuelve (validos, invalidos). Cada mensaje válido trae '_archivo'
    (su ruta) y viene ordenado por fecha de envío. Los inválidos traen
    '_archivo' y 'errores'. Filtra por destino/tipo si se indican (los
    mensajes para otras herramientas se ignoran, no se reportan)."""
    carpeta = Path(raiz) / CARPETA_BUZON
    validos, invalidos = [], []
    if not carpeta.is_dir():
        return validos, invalidos
    for ruta in sorted(carpeta.iterdir()):
        if not _es_archivo_de_mensaje(ruta):
            continue
        try:
            mensaje = _leer_json(ruta)
        except (OSError, ValueError) as exc:
            invalidos.append({"_archivo": ruta, "errores": [f"no se pudo leer: {exc}"]})
            continue
        errores = validar_mensaje(mensaje)
        if errores:
            invalidos.append({"_archivo": ruta, "errores": errores})
            continue
        if destino and mensaje["destino"] != destino:
            continue
        if tipo and mensaje["tipo"] != tipo:
            continue
        mensaje["_archivo"] = ruta
        validos.append(mensaje)
    validos.sort(key=lambda m: (m["origen"]["enviado"], m["id"]))
    return validos, invalidos


def _sin_privados(mensaje: dict) -> dict:
    return {k: v for k, v in mensaje.items() if not k.startswith("_")}


def archivar(raiz: Path, mensaje: dict, estado: str, detalle: list[str] | None = None,
             extra: dict | None = None) -> Path:
    """Mueve el mensaje del buzón a procesado/AAAA-MM/ con su resultado.
    Escribe primero la copia y solo después borra el original: si algo
    falla a la mitad, el mensaje sigue en el buzón y se vuelve a atender."""
    if estado not in ESTADOS_FINALES:
        raise ValueError(f"estado final desconocido: {estado}")
    origen = Path(mensaje["_archivo"])
    ahora = datetime.now()
    carpeta = Path(raiz) / CARPETA_PROCESADO / ahora.strftime("%Y-%m")
    destino = carpeta / origen.name
    n = 2
    while destino.exists():
        destino = carpeta / f"{origen.stem} ({n}){origen.suffix}"
        n += 1
    registro = _sin_privados(mensaje)
    registro["resultado"] = dict(extra or {}, estado=estado, fecha=ahora_iso(), detalle=list(detalle or []))
    _escribir_json_atomico(destino, registro)
    try:
        origen.unlink()
    except FileNotFoundError:
        pass
    return destino


def resultados_recientes(raiz: Path, dias: int = 180) -> dict[str, dict]:
    """{id: resultado} de los mensajes procesados en los últimos 'dias' --
    para que cada herramienta publique el estado de lo que le enviaron."""
    base = Path(raiz) / CARPETA_PROCESADO
    if not base.is_dir():
        return {}
    limite = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m")
    salida = {}
    for carpeta_mes in sorted(base.iterdir()):
        if not carpeta_mes.is_dir() or carpeta_mes.name < limite:
            continue
        for ruta in sorted(carpeta_mes.glob("*.json")):
            try:
                registro = _leer_json(ruta)
            except (OSError, ValueError):
                continue
            if isinstance(registro, dict) and isinstance(registro.get("resultado"), dict) and registro.get("id"):
                salida[registro["id"]] = registro["resultado"]
    return salida


# ── PUBLICACIONES ────────────────────────────────────────────────────────────

def publicar(raiz: Path, nombre: str, herramienta: str, datos) -> Path:
    """Reemplaza publicado/<nombre>.json con un sobre común."""
    ruta = Path(raiz) / CARPETA_PUBLICADO / f"{nombre}.json"
    _escribir_json_atomico(ruta, {
        "esquema": ESQUEMA,
        "herramienta": herramienta,
        "generado": ahora_iso(),
        "datos": datos,
    })
    return ruta


def leer_publicacion(raiz: Path, nombre: str):
    """El sobre completo de publicado/<nombre>.json, o None si no existe o
    no se puede leer."""
    try:
        sobre = _leer_json(Path(raiz) / CARPETA_PUBLICADO / f"{nombre}.json")
    except (OSError, ValueError):
        return None
    return sobre if isinstance(sobre, dict) and sobre.get("esquema") == ESQUEMA else None
