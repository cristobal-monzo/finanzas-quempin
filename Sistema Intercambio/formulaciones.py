# -*- coding: utf-8 -*-
"""
formulaciones.py -- El repositorio de presupuestos del Formulador de proyectos,
visto desde Python, para que Claude los resuma y los lleve a otras herramientas.

Pedido del usuario (2026-09-30): «cuando alguien genere un nuevo presupuesto
quiero que se guarde, o que al menos quede un input para que yo, usando
Claude, pueda actualizar». El Formulador (web) guarda cada presupuesto en
``publicado/formulador/<uid>.json`` de la carpeta de intercambio (ver
``js/compartida.js`` en su repo). Cada archivo es un sobre con:

- ``historia``: las versiones anteriores que pasaron por la carpeta;
- ``resumen``: los números que calculó el propio Formulador (costo, precio,
  margen y costos por categoría del Análisis Financiero);
- ``datos``: el proyecto completo.

Este módulo:

- lee el repositorio (``leer_repositorio``);
- incorpora los presupuestos que llegaron **por archivo** al buzón (mensaje
  ``formulacion``, desde navegadores sin acceso a la carpeta), con las mismas
  reglas de quién gana que usa el Formulador (``incorporar_buzon``);
- lleva la cuenta de qué presupuestos ya revisó el usuario con Claude
  (``novedades`` / ``marcar_revisadas``).

Nunca calcula precios: eso lo hace el Formulador, porque dos cálculos
terminan divergiendo. Tampoco borra archivos del repositorio.
"""

import re
import secrets
from datetime import datetime
from pathlib import Path

import intercambio

RUTA_REPOSITORIO = (intercambio.CARPETA_PUBLICADO, "formulador")
TIPO_ENTREGA = "formulacion"
DESTINO = "formulador"
MAX_HISTORIA = 50
# Qué revisó el usuario con Claude: {"revisadas": {uid: modificado}, "fecha": iso}.
# Solo lleva identificadores y fechas, pero se ignora en git igual que los
# demás estados.
RUTA_REVISADAS = Path(__file__).resolve().parent / "formulaciones_revisadas.json"

_CARACTER_INVALIDO = re.compile(r"[^A-Za-z0-9_-]")


def nombre_archivo(uid) -> str:
    """El mismo que usa el Formulador (js/compartida.js)."""
    return _CARACTER_INVALIDO.sub("_", str(uid)) + ".json"


def carpeta_repositorio(raiz: Path) -> Path:
    return Path(raiz).joinpath(*RUTA_REPOSITORIO)


# ── LECTURA ──────────────────────────────────────────────────────────────────

def _item(sobre, ruta: Path) -> dict | None:
    datos = sobre.get("datos") if isinstance(sobre, dict) else None
    if not (isinstance(sobre, dict) and sobre.get("esquema") == intercambio.ESQUEMA
            and sobre.get("tipo") == "proyecto" and isinstance(datos, dict) and datos.get("uid")
            and nombre_archivo(datos["uid"]) == ruta.name):
        return None
    return {
        "uid": str(datos["uid"]),
        "mod": str(datos.get("modificado") or ""),
        "historia": [h for h in (sobre.get("historia") or []) if isinstance(h, str)],
        "resumen": sobre.get("resumen") if isinstance(sobre.get("resumen"), dict) else {},
        "autor": str(sobre.get("autor") or ""),
        "datos": datos,
        "archivo": ruta,
    }


def leer_repositorio(raiz: Path) -> list[dict]:
    """Presupuestos del repositorio. Solo cuenta el archivo con el nombre de
    su uid: las copias que deja OneDrive en un conflicto se ignoran, igual que
    en el Formulador."""
    carpeta = carpeta_repositorio(raiz)
    if not carpeta.is_dir():
        return []
    items = []
    for ruta in sorted(carpeta.glob("*.json")):
        try:
            sobre = intercambio._leer_json(ruta)
        except (OSError, ValueError):
            continue
        item = _item(sobre, ruta)
        if item:
            items.append(item)
    return items


# ── ENTREGAS POR ARCHIVO (mensaje «formulacion» en el buzón) ──────────────────

def validar_entrega(mensaje: dict) -> list[str]:
    datos = mensaje.get("datos")
    if not isinstance(datos, dict):
        return ["falta el presupuesto ('datos')"]
    errores = []
    if not isinstance(datos.get("uid"), str) or not datos["uid"].strip():
        errores.append("el presupuesto no tiene uid")
    if not isinstance(datos.get("modificado"), str):
        errores.append("el presupuesto no tiene fecha de modificación")
    if not isinstance(mensaje.get("historia", []), list):
        errores.append("'historia' debe ser una lista")
    return errores


def decidir_entrega(mensaje: dict, actual: dict | None) -> str:
    """'nuevo' | 'aplicar' | 'sin-cambios' | 'reemplazado' | 'conflicto'.
    Mismas reglas que el Formulador: la entrega reemplaza lo que hay solo si
    viene de esa versión. Si la carpeta ya tiene algo más nuevo que viene de
    la entrega, no se toca. Si cambiaron por separado, la entrega queda como
    copia."""
    mod = str(mensaje["datos"].get("modificado") or "")
    if actual is None:
        return "nuevo"
    if actual["mod"] == mod:
        return "sin-cambios"
    if actual["mod"] in set(mensaje.get("historia") or []):
        return "aplicar"
    if mod in set(actual["historia"]):
        return "reemplazado"
    return "conflicto"


def _escribir(raiz: Path, datos: dict, historia: list, resumen, autor: str) -> Path:
    ruta = carpeta_repositorio(raiz) / nombre_archivo(datos["uid"])
    intercambio._escribir_json_atomico(ruta, {
        "esquema": intercambio.ESQUEMA, "herramienta": "formulador", "tipo": "proyecto",
        "generado": intercambio.ahora_iso(), "autor": autor,
        "historia": [h for h in historia if isinstance(h, str)][-MAX_HISTORIA:],
        "resumen": resumen if isinstance(resumen, dict) else {}, "datos": datos,
    })
    return ruta


def titulo_legible(datos: dict) -> str:
    return f"{datos.get('codigo') or '—'} v{datos.get('version') or 1} «{datos.get('titulo') or 'Sin título'}»"


def incorporar_buzon(raiz: Path) -> list[dict]:
    """Lleva al repositorio los presupuestos entregados por archivo y archiva
    cada mensaje con su resultado. Devuelve [{uid, decision, estado, detalle}]."""
    mensajes, _ = intercambio.leer_buzon(raiz, destino=DESTINO, tipo=TIPO_ENTREGA)
    if not mensajes:
        return []
    actuales = {i["uid"]: i for i in leer_repositorio(raiz)}
    resultados = []
    for m in mensajes:
        errores = validar_entrega(m)
        if errores:
            intercambio.archivar(raiz, m, "rechazado", errores)
            resultados.append({"uid": None, "decision": "rechazado", "estado": "rechazado", "detalle": errores})
            continue
        datos, autor = m["datos"], str(m["origen"].get("usuario") or "")
        uid = datos["uid"]
        decision = decidir_entrega(m, actuales.get(uid))
        if decision in ("nuevo", "aplicar"):
            _escribir(raiz, datos, m.get("historia") or [], m.get("resumen"), autor)
            estado, detalle = "aplicado", [f"{titulo_legible(datos)} quedó en el repositorio de formulaciones."]
        elif decision == "conflicto":
            copia = dict(datos, uid=secrets.token_hex(6),
                         titulo=f"{datos.get('titulo') or 'Presupuesto'} (entregado por archivo)")
            copia.pop("vinculos", None)
            _escribir(raiz, copia, [], m.get("resumen"), autor)
            estado = "aplicado"
            detalle = [f"{titulo_legible(datos)} también cambió en la carpeta: la entrega quedó como copia "
                       f"«{copia['titulo']}» para no perder ningún cambio."]
        elif decision == "sin-cambios":
            estado, detalle = "sin-cambios", [f"{titulo_legible(datos)} ya estaba igual en el repositorio."]
        else:
            estado, detalle = "reemplazado", [f"El repositorio ya tiene una versión más nueva de {titulo_legible(datos)}."]
        intercambio.archivar(raiz, m, estado, detalle, extra={"uid": uid, "decision": decision})
        resultados.append({"uid": uid, "decision": decision, "estado": estado, "detalle": detalle})
        actuales = {i["uid"]: i for i in leer_repositorio(raiz)}
    return resultados


def entregas_en_buzon(raiz: Path) -> list[dict]:
    mensajes, _ = intercambio.leer_buzon(raiz, destino=DESTINO, tipo=TIPO_ENTREGA)
    return mensajes


# ── REVISIÓN CON CLAUDE ──────────────────────────────────────────────────────

def leer_revisadas(ruta: Path | None = None) -> dict:
    """ruta None = RUTA_REVISADAS (leída al llamar: las pruebas la reemplazan)."""
    try:
        datos = intercambio._leer_json(ruta or RUTA_REVISADAS)
    except (OSError, ValueError):
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    if not isinstance(datos.get("revisadas"), dict):
        datos["revisadas"] = {}
    return datos


def novedades(repositorio: list[dict], revisadas: dict) -> dict:
    """{"nuevos": [...], "cambiados": [...]} desde la última revisión."""
    vistas = revisadas.get("revisadas", {})
    nuevos, cambiados = [], []
    for item in repositorio:
        previo = vistas.get(item["uid"])
        if previo is None:
            nuevos.append(item)
        elif previo != item["mod"]:
            cambiados.append(item)
    orden = lambda i: i["mod"]  # noqa: E731
    return {"nuevos": sorted(nuevos, key=orden, reverse=True), "cambiados": sorted(cambiados, key=orden, reverse=True)}


def marcar_revisadas(repositorio: list[dict], ruta: Path | None = None) -> int:
    datos = leer_revisadas(ruta)
    for item in repositorio:
        datos["revisadas"][item["uid"]] = item["mod"]
    datos["fecha"] = intercambio.ahora_iso()
    intercambio._escribir_json_atomico(ruta or RUTA_REVISADAS, datos)
    return len(repositorio)


# ── TEXTO ────────────────────────────────────────────────────────────────────

# Moneda del presupuesto (resumen.moneda del Formulador): pesos enteros; soles, dólares y euros con centavos
_MONEDAS = {"CLP": ("$", 0), "PEN": ("S/ ", 2), "USD": ("US$ ", 2), "EUR": ("€ ", 2)}


def _monto(valor, moneda: str = "CLP") -> str:
    if not isinstance(valor, (int, float)):
        return "—"
    simbolo, dec = _MONEDAS.get(moneda or "CLP", _MONEDAS["CLP"])
    texto = f"{abs(valor):,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return ("-" if round(valor, dec) < 0 else "") + simbolo + texto


def _fecha(iso: str) -> str:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone().strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return str(iso)


def linea(item: dict) -> str:
    """Una línea por presupuesto, para el resumen que lee el usuario."""
    d, r = item["datos"], item["resumen"]
    margen = r.get("margen")
    partes = [
        titulo_legible(d),
        d.get("cliente") or "sin cliente",
        d.get("estado") or "Borrador",
        f"costo {_monto(r.get('costoDirecto'), r.get('moneda'))}",
        f"precio neto {_monto(r.get('precioNeto'), r.get('moneda'))}",
        f"margen {margen * 100:.1f} %".replace(".", ",") if isinstance(margen, (int, float)) else "margen —",
    ]
    if r.get("errores"):
        partes.append(f"{r['errores']} error(es)")
    quien = item["autor"] or d.get("responsable") or ""
    if quien:
        partes.append(f"por {quien}")
    partes.append(f"modificado {_fecha(item['mod'])}")
    if d.get("eliminado"):
        partes.append("EN LA PAPELERA")
    return " · ".join(partes)
