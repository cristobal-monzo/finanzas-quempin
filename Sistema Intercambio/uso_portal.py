# -*- coding: utf-8 -*-
"""
uso_portal.py -- qué herramientas abre el equipo en el Portal (2026-11-09).

El Portal deja en `publicado/uso-portal/<dispositivo>.json` cuántas veces se
abrió cada herramienta o vista por día en ese navegador (anónimo: sin usuario).
Este script solo lee y suma: no escribe nada.

    py -3.14 uso_portal.py [--dias 30]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

CARPETA = "uso-portal"


def leer(raiz: Path) -> list[dict]:
    """Los `datos` de cada navegador; un archivo a medio sincronizar se salta."""
    salida = []
    for f in sorted((Path(raiz) / "publicado" / CARPETA).glob("*.json")):
        try:
            sobre = json.loads(f.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        datos = sobre.get("datos") if isinstance(sobre, dict) else None
        if isinstance(datos, dict) and isinstance(datos.get("dias"), list):
            salida.append(datos)
    return salida


def resumen(navegadores: list[dict], desde: date) -> dict:
    """{'aperturas': Counter(herramienta), 'navegadores': Counter(herramienta), 'total', 'activos'}."""
    aperturas, quienes = Counter(), Counter()
    activos = 0
    for nav in navegadores:
        vistas = set()
        for d in nav["dias"]:
            try:
                if date.fromisoformat(d["fecha"]) < desde:
                    continue
                n = int(d["aperturas"])
            except (KeyError, TypeError, ValueError):
                continue
            aperturas[d["herramienta"]] += n
            vistas.add(d["herramienta"])
        quienes.update(vistas)
        activos += bool(vistas)
    return {"aperturas": aperturas, "navegadores": quienes, "total": sum(aperturas.values()), "activos": activos}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--dias", type=int, default=30)
    args = ap.parse_args(argv)
    import ubicacion
    raiz = ubicacion.ubicar_intercambio(Path(__file__).resolve().parent)
    if raiz is None:
        print("No se encontró la carpeta de intercambio.")
        return 1
    r = resumen(leer(raiz), date.today() - timedelta(days=args.dias))
    print(f"Últimos {args.dias} días: {r['total']} aperturas en {r['activos']} navegador(es).")
    for herr, n in r["aperturas"].most_common():
        print(f"  {herr:<28} {n:>5}  ({r['navegadores'][herr]} navegador(es))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
