# -*- coding: utf-8 -*-
"""
esquemas.py -- El catálogo del intercambio, validable.

Antes de esto el formato de cada mensaje y publicación estaba descrito en
tres textos (este CLAUDE.md, el docs/INTERCAMBIO.md del Formulador y el
LEEME.md de la carpeta) y validado a mano por cada destinatario. Ahora hay
un JSON Schema por cada uno en ``esquemas/``:

    esquemas/sobre-mensaje.json         lo común a todo mensaje
    esquemas/sobre-publicacion.json     lo común a publicado/<nombre>.json
    esquemas/mensajes/<tipo>.json       el contenido de cada tipo de mensaje
    esquemas/publicaciones/<nombre>.json  el campo 'datos' de cada publicación

Este módulo implementa solo el subconjunto de JSON Schema que usa el
catálogo (type, const, enum, required, properties, additionalProperties,
items, minItems, minLength, pattern, minimum, exclusiveMinimum, maximum,
anyOf), sin dependencias. ``esquemas.js`` es su gemelo para el navegador:
mismo algoritmo y mismos textos de error, clavados por
``tests/test_esquemas.py`` (corre los dos sobre los mismos ejemplos).

Validar el contenido de un tipo **no reemplaza** las reglas de su
destinatario (por ejemplo, que el TAG exista): solo asegura que el mensaje
tiene la forma acordada.
"""

import json
import math
import re
from pathlib import Path

CARPETA = Path(__file__).resolve().parent / "esquemas"
RAIZ_RUTA = "(raíz)"

NOMBRE_TIPO = {
    "string": "texto", "number": "número", "integer": "número entero", "boolean": "verdadero o falso",
    "array": "lista", "object": "objeto", "null": "vacío",
}

_cache: dict[str, dict] = {}


def cargar(nombre: str) -> dict:
    """'sobre-mensaje', 'mensajes/venta-proyecto', 'publicaciones/folios'..."""
    if nombre not in _cache:
        with open(CARPETA / f"{nombre}.json", encoding="utf-8") as f:
            _cache[nombre] = json.load(f)
    return _cache[nombre]


def _nombres(carpeta: str) -> list[str]:
    return sorted(p.stem for p in (CARPETA / carpeta).glob("*.json"))


def tipos_de_mensaje() -> list[str]:
    return _nombres("mensajes")


def publicaciones() -> list[str]:
    return _nombres("publicaciones")


# ── VALIDADOR ────────────────────────────────────────────────────────────────

def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _es_tipo(v, tipo: str) -> bool:
    if tipo == "null":
        return v is None
    if tipo == "boolean":
        return isinstance(v, bool)
    if tipo == "integer":
        return _es_numero(v) and float(v).is_integer()
    if tipo == "number":
        return _es_numero(v)
    if tipo == "string":
        return isinstance(v, str)
    if tipo == "array":
        return isinstance(v, list)
    if tipo == "object":
        return isinstance(v, dict)
    return False


def _igual(a, b) -> bool:
    """Igualdad estricta, como === en JavaScript: True no es 1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _es_numero(a) and _es_numero(b):
        return a == b
    return type(a) is type(b) and a == b


def _fmt(valor) -> str:
    if _es_numero(valor) and float(valor).is_integer():
        return str(int(valor))
    if isinstance(valor, str):
        return f"'{valor}'"
    return json.dumps(valor, ensure_ascii=False)


def _hija(ruta: str, clave) -> str:
    if isinstance(clave, int):
        return f"{ruta}[{clave}]"
    return clave if ruta == RAIZ_RUTA else f"{ruta}.{clave}"


def validar(valor, esquema: dict, ruta: str = RAIZ_RUTA) -> list[str]:
    """Errores de 'valor' contra 'esquema' (vacío = válido)."""
    errores: list[str] = []
    _validar(valor, esquema, ruta, errores)
    return errores


def _validar(v, s: dict, ruta: str, errores: list[str]) -> None:
    if "anyOf" in s:
        if not any(not validar(v, rama, ruta) for rama in s["anyOf"]):
            errores.append(f"{ruta}: no cumple ninguna de las formas permitidas")
        return
    if "type" in s:
        tipos = s["type"] if isinstance(s["type"], list) else [s["type"]]
        if not any(_es_tipo(v, t) for t in tipos):
            errores.append(f"{ruta}: debe ser {' o '.join(NOMBRE_TIPO.get(t, t) for t in tipos)}")
            return
    if "const" in s and not _igual(v, s["const"]):
        errores.append(f"{ruta}: debe ser {_fmt(s['const'])}")
        return
    if "enum" in s and not any(_igual(v, op) for op in s["enum"]):
        errores.append(f"{ruta}: valor no permitido (se acepta: {', '.join(_fmt(op) for op in s['enum'])})")
        return
    if isinstance(v, str):
        if "minLength" in s and len(v) < s["minLength"]:
            errores.append(f"{ruta}: debe tener al menos {s['minLength']} caracter(es)")
        if "pattern" in s and not re.search(s["pattern"], v, re.ASCII):
            errores.append(f"{ruta}: no tiene el formato esperado")
    if _es_numero(v):
        if "minimum" in s and v < s["minimum"]:
            errores.append(f"{ruta}: debe ser mayor o igual a {_fmt(s['minimum'])}")
        if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
            errores.append(f"{ruta}: debe ser mayor que {_fmt(s['exclusiveMinimum'])}")
        if "maximum" in s and v > s["maximum"]:
            errores.append(f"{ruta}: debe ser menor o igual a {_fmt(s['maximum'])}")
    if isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]:
            errores.append(f"{ruta}: debe tener al menos {s['minItems']} elemento(s)")
        if isinstance(s.get("items"), dict):
            for i, x in enumerate(v):
                _validar(x, s["items"], _hija(ruta, i), errores)
    if isinstance(v, dict):
        for campo in s.get("required", []):
            if campo not in v:
                errores.append(f"{ruta}: falta '{campo}'")
        propiedades = s.get("properties", {})
        for clave, sub in propiedades.items():
            if clave in v:
                _validar(v[clave], sub, _hija(ruta, clave), errores)
        adicionales = s.get("additionalProperties", True)
        if adicionales is not True:
            for clave in v:
                if clave in propiedades:
                    continue
                if adicionales is False:
                    errores.append(f"{ruta}: campo no permitido '{clave}'")
                elif isinstance(adicionales, dict):
                    _validar(v[clave], adicionales, _hija(ruta, clave), errores)


# ── MENSAJES Y PUBLICACIONES ─────────────────────────────────────────────────

def validar_mensaje(mensaje, paquete: dict | None = None) -> list[str]:
    """Sobre + contenido del tipo, si el tipo está en el catálogo. Un tipo
    desconocido solo se valida por el sobre: su destinatario decide.
    'paquete' (el esquemas.json de la carpeta, ver paquete()) reemplaza a los
    archivos de esquemas/: así valida una copia de este módulo que vive en
    otro repositorio (Sistema QUEMPIN) sin llevar los esquemas consigo."""
    paquete = paquete or paquete_local()
    errores = validar(mensaje, paquete["sobreMensaje"])
    esquema = None if errores else paquete["mensajes"].get(mensaje["tipo"])
    if esquema is None:
        return errores
    destino = esquema.get("destino")
    if destino and mensaje["destino"] != destino:
        errores.append(f"destino: el tipo '{mensaje['tipo']}' va a '{destino}', no a '{mensaje['destino']}'")
    return errores + validar(mensaje, esquema)


def validar_publicacion(nombre: str, sobre, paquete: dict | None = None) -> list[str]:
    """'nombre' sin '.json' ('folios', 'precios-referencia'...). El
    repositorio del Formulador se valida con 'formulador-proyecto'."""
    paquete = paquete or paquete_local()
    esquema = paquete["publicaciones"].get(nombre)
    if esquema is None:
        return [f"publicación desconocida: '{nombre}'"]
    if nombre == "formulador-proyecto":
        return validar(sobre, esquema)
    errores = validar(sobre, paquete["sobrePublicacion"])
    if errores:
        return errores
    return validar(sobre["datos"], esquema, "datos")


def paquete_local() -> dict:
    """El paquete armado desde los archivos de esquemas/ (cacheado)."""
    if "__paquete__" not in _cache:
        _cache["__paquete__"] = paquete()
    return _cache["__paquete__"]


def catalogo() -> dict:
    """Título, descripción y destino o dueño de cada tipo y publicación --
    para la documentación y para estado.json."""
    def ficha(nombre):
        e = cargar(nombre)
        return {k: e[k] for k in ("title", "description", "destino", "dueno") if k in e}
    return {
        "mensajes": {t: ficha(f"mensajes/{t}") for t in tipos_de_mensaje()},
        "publicaciones": {p: ficha(f"publicaciones/{p}") for p in publicaciones()},
    }


def paquete() -> dict:
    """Todos los esquemas en un solo objeto: lo que el procesador deja en la
    carpeta (esquemas.json) para que las herramientas web validen con el
    mismo catálogo sin copiarlo."""
    return {
        "sobreMensaje": cargar("sobre-mensaje"),
        "sobrePublicacion": cargar("sobre-publicacion"),
        "mensajes": {t: cargar(f"mensajes/{t}") for t in tipos_de_mensaje()},
        "publicaciones": {p: cargar(f"publicaciones/{p}") for p in publicaciones()},
    }
