# -*- coding: utf-8 -*-
"""Escribe requirements.lock: las versiones exactas que usa este equipo.

    py -3.14 fijar_dependencias.py            # reescribe requirements.lock
    py -3.14 fijar_dependencias.py --revisar  # código 1 si el lock no coincide con lo instalado

Por qué existe (2026-11-06, auditoría del flujo de entrega): requirements.txt pide rangos
(«openpyxl>=3.1.5») y el CI instalaba en cada push la última versión de todo. Así una versión nueva
de una librería podía romper el CI sin que cambiara el código, y lo que pasaba en el CI no era lo
que corría en el equipo de la oficina. El CI instala desde requirements.lock; requirements.txt
sigue diciendo qué se usa y por qué.

Toma los paquetes de requirements.txt y, de cada uno, sus dependencias instaladas (las que
corresponden a esta plataforma: Windows con Python 3.14, igual que el runner del CI). Para
actualizar una librería: instálala con pip, corre las pruebas y vuelve a correr este script.
"""
import argparse
import importlib.metadata as md
import re
import sys
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement

RAIZ = Path(__file__).resolve().parent
REQUISITOS = RAIZ / "requirements.txt"
LOCK = RAIZ / "requirements.lock"
CABECERA = """\
# Versiones exactas de Finanzas QUEMPIN, tal como están instaladas en el equipo de la oficina.
# NO se edita a mano: lo escribe `py -3.14 fijar_dependencias.py` (qué se usa y por qué: requirements.txt).
# Lo instala el CI (.github/workflows/tests.yml): pip install -r requirements.lock
"""


def _normalizar(nombre: str) -> str:
    return re.sub(r"[-_.]+", "-", nombre).lower()


def _requisitos_directos(ruta: Path = REQUISITOS) -> list[Requirement]:
    salida = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if linea:
            salida.append(Requirement(linea))
    return salida


def cierre(directos: list[Requirement]) -> dict[str, str]:
    """{nombre normalizado: versión instalada} de los directos y todas sus dependencias."""
    entorno = default_environment()
    versiones: dict[str, str] = {}
    pendientes = [(r, "") for r in directos]
    while pendientes:
        req, extra = pendientes.pop()
        if req.marker is not None and not req.marker.evaluate(dict(entorno, extra=extra)):
            continue
        nombre = _normalizar(req.name)
        if nombre in versiones:
            continue
        try:
            dist = md.distribution(req.name)
        except md.PackageNotFoundError:
            raise SystemExit(f"[ERROR] {req.name} no está instalado: py -3.14 -m pip install -r requirements.txt")
        versiones[nombre] = dist.version
        for sub in dist.requires or []:
            sub_req = Requirement(sub)
            if sub_req.marker is not None and "extra" in str(sub_req.marker):
                # Solo los extras que pidió quien lo requiere (p. ej. «paquete[extra]»).
                for e in req.extras:
                    if sub_req.marker.evaluate(dict(entorno, extra=e)):
                        pendientes.append((sub_req, e))
                continue
            pendientes.append((sub_req, ""))
    return versiones


def texto_lock(versiones: dict[str, str]) -> str:
    return CABECERA + "".join(f"{n}=={v}\n" for n, v in sorted(versiones.items()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--revisar", action="store_true", help="no escribe: dice si el lock está al día")
    args = ap.parse_args(argv)
    nuevo = texto_lock(cierre(_requisitos_directos()))
    if args.revisar:
        actual = LOCK.read_text(encoding="utf-8") if LOCK.exists() else ""
        if actual != nuevo:
            print("[AVISO] requirements.lock no coincide con lo instalado: py -3.14 fijar_dependencias.py")
            return 1
        print("requirements.lock al día.")
        return 0
    LOCK.write_text(nuevo, encoding="utf-8", newline="\n")
    print(f"requirements.lock: {nuevo.count(chr(10)) - CABECERA.count(chr(10))} paquetes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
