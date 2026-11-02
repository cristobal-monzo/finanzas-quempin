# -*- coding: utf-8 -*-
"""Fuentes y logos de la marca: una sola copia, que cada build pone en su tablero.

Por que existe (2026-10-30): cada plantilla llevaba 161 KB de base64 identicos
(las 3 fuentes Lato, el logo dos veces y el favicon). Eran 5 copias que nadie
cambia, y mirar las primeras lineas de una plantilla costaba decenas de miles de
tokens. Ahora la plantilla lleva marcadores y candado.incrustar() los reemplaza,
asi que un tablero sigue siendo un solo archivo autocontenido, como antes.

El hub y el Portal no se construyen: enlazan marca/fuentes.css directamente, y
publicar.py lo copia con ellos.
"""
import base64
from functools import lru_cache
from pathlib import Path

CARPETA = Path(__file__).resolve().with_name("marca")
MARCADOR_FUENTES = "__MARCA_FUENTES__"
MARCADOR_LOGO = "__MARCA_LOGO__"
MARCADOR_FAVICON = "__MARCA_FAVICON__"


@lru_cache(maxsize=None)
def fuentes() -> str:
    """Las 3 reglas @font-face de Lato (400/700/900), con la fuente en base64."""
    return (CARPETA / "fuentes.css").read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _imagen(nombre: str) -> str:
    return "data:image/png;base64," + base64.b64encode((CARPETA / nombre).read_bytes()).decode("ascii")


def logo() -> str:
    """El logo como data URI, para un <img> o el encabezado de un PDF."""
    return _imagen("logo.png")


def favicon() -> str:
    return _imagen("favicon.png")


def incrustar(html: str) -> str:
    """Reemplaza en una plantilla los marcadores que traiga."""
    return (html.replace(MARCADOR_FUENTES, fuentes())
            .replace(MARCADOR_LOGO, logo())
            .replace(MARCADOR_FAVICON, favicon()))
