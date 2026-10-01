# -*- coding: utf-8 -*-
"""
contrapartes.py -- Consulta por RUT del directorio de clientes y proveedores
que publica Sistema QUEMPIN (``publicado/contrapartes.json``).

Plan de integración (2026-09-30), fase 3c: cada herramienta tenía su propia
lista de proveedores y clientes. Sistema QUEMPIN es la única que los guarda
con RUT (al emitir cotizaciones y órdenes de compra), así que su directorio
sirve de referencia para escribir siempre la misma razón social. Solo
consulta: nunca escribe en Centro de Costos ni en ningún otro módulo (el
ingreso de facturas sigue igual; el agente lo usa en el paso 2 de
/Registro_Centro_de_Costos antes de fijar «proveedor»).

Uso:  py -3.14 contrapartes.py 76.123.456-7
"""

import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import intercambio  # noqa: E402
import ubicacion  # noqa: E402

PUBLICACION = "contrapartes"


def normalizar_rut(rut) -> str:
    """Solo dígitos y K, en mayúscula: «76.123.456-k» -> «76123456K»."""
    return re.sub(r"[^0-9K]", "", str(rut or "").upper())


def buscar_por_rut(raiz: Path, rut) -> list[dict]:
    """Las fichas con ese RUT, de clientes y de proveedores ({'tipo', ...})."""
    clave = normalizar_rut(rut)
    sobre = intercambio.leer_publicacion(raiz, PUBLICACION)
    if not clave or not sobre:
        return []
    datos = sobre.get("datos") or {}
    salida = []
    for tipo in ("proveedores", "clientes"):
        for ficha in datos.get(tipo) or []:
            if normalizar_rut(ficha.get("rut")) == clave:
                salida.append(dict(ficha, tipo=tipo[:-2] if tipo == "proveedores" else "cliente"))
    return salida


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if len(argv) != 1:
        print("Uso: py -3.14 contrapartes.py <RUT>")
        return 2
    raiz = ubicacion.ubicar_intercambio(AQUI)
    if raiz is None or not intercambio.es_carpeta_de_intercambio(raiz):
        print("[AVISO] No se encontró la carpeta de intercambio.")
        return 1
    encontrados = buscar_por_rut(raiz, argv[0])
    if not encontrados:
        print(f"Sin coincidencias para el RUT {argv[0]} en el directorio de Sistema QUEMPIN.")
        return 0
    for f in encontrados:
        print(f"{f['tipo']}: {f.get('razon_social')} (RUT {f.get('rut')}{', ' + f['ciudad'] if f.get('ciudad') else ''})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
