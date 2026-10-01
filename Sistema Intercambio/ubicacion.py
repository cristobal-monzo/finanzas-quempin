# -*- coding: utf-8 -*-
"""
ubicacion.py -- Dónde están, en este computador, las carpetas compartidas que
usan las herramientas: la carpeta de intercambio, la Planilla de Ingreso de
Requerimientos y las bibliotecas de proyectos.

Cada colega tiene OneDrive en una ruta propia (C:\\Users\\<usuario>\\OneDrive -
QUEMPIN SPA), así que nada de esto se guarda como ruta fija: se busca subiendo
desde un punto de partida (este repositorio, o la carpeta compartida de
Sistema QUEMPIN) hasta la carpeta de OneDrive que contiene la biblioteca.
Misma regla que ``presupuestos_formulador.ubicar_intercambio`` de Análisis
Financiero: si la biblioteca no está sincronizada, se devuelve None y quien
llama queda inactivo con un aviso; nunca se crea una biblioteca falsa.

Variables de entorno para fijarlas a mano (pruebas, otro equipo):
QUEMPIN_INTERCAMBIO, QUEMPIN_PLANILLA_REQUERIMIENTOS, QUEMPIN_ONEDRIVE.
"""

import os
import unicodedata
from pathlib import Path

BIBLIOTECA_FORMULACION = "Formulación de proyectos - Documentos"
BIBLIOTECA_GESTION = "Gestión de Proyectos - Documentos"
CARPETA_HERRAMIENTAS = ".Herramientas formulación"
CARPETA_INTERCAMBIO = "Intercambio"
# La planilla vive en la raíz de la biblioteca (es la que abre el equipo).
# En .Herramientas formulación quedó una copia más antigua: no se lee.
PLANILLA_REQUERIMIENTOS = "Planilla de Ingreso de Requerimientos.xlsx"

AQUI = Path(__file__).resolve().parent


def _clave(nombre: str) -> str:
    return unicodedata.normalize("NFC", nombre).casefold()


def hija(padre: Path, nombre: str) -> Path:
    """La subcarpeta o archivo con ese nombre sin distinguir mayúsculas ni la
    forma de las tildes (en el disco está como «.HERRAMIENTAS FORMULACIÓN»).
    Si no existe, devuelve la ruta con el nombre tal cual."""
    clave = _clave(nombre)
    try:
        for h in padre.iterdir():
            if _clave(h.name) == clave:
                return h
    except OSError:
        pass
    return padre / nombre


def raiz_onedrive(desde: Path | None = None) -> Path | None:
    """La carpeta de OneDrive que contiene la biblioteca de Formulación."""
    fija = os.environ.get("QUEMPIN_ONEDRIVE")
    if fija:
        return Path(fija)
    for base in Path(desde or AQUI).resolve().parents:
        if hija(base, BIBLIOTECA_FORMULACION).is_dir():
            return base
    return None


def biblioteca(nombre: str, desde: Path | None = None) -> Path | None:
    base = raiz_onedrive(desde)
    if base is None:
        return None
    ruta = hija(base, nombre)
    return ruta if ruta.is_dir() else None


def ubicar_intercambio(desde: Path | None = None) -> Path | None:
    fija = os.environ.get("QUEMPIN_INTERCAMBIO")
    if fija:
        return Path(fija)
    formulacion = biblioteca(BIBLIOTECA_FORMULACION, desde)
    if formulacion is None:
        return None
    return hija(hija(formulacion, CARPETA_HERRAMIENTAS), CARPETA_INTERCAMBIO)


def ubicar_planilla(desde: Path | None = None) -> Path | None:
    fija = os.environ.get("QUEMPIN_PLANILLA_REQUERIMIENTOS")
    if fija:
        return Path(fija)
    formulacion = biblioteca(BIBLIOTECA_FORMULACION, desde)
    if formulacion is None:
        return None
    ruta = hija(formulacion, PLANILLA_REQUERIMIENTOS)
    return ruta if ruta.is_file() else None
