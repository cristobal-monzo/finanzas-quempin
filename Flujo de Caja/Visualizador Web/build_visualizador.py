# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el tablero web de Flujo de Caja (solo Chile).

Pide los datos a flujo_caja.armar() -- la misma función que escribe el
Excel -- y los inyecta en template.html junto con las fuentes Lato y el logo,
que se toman del módulo de marca (brand.py) en vez de duplicarlos aquí.

Salidas (gitignoreadas, son datos de la empresa):
  data/flujo-caja.json   snapshot de lo inyectado
  build/index.html       la página autocontenida

Uso:  py -3.14 build_visualizador.py
"""

import base64
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent                 # Flujo de Caja/Visualizador Web
RAIZ_FINANZAS = RAIZ.parents[1]
sys.path.insert(0, str(RAIZ.parent / "Sistema"))
sys.path.insert(0, str(RAIZ_FINANZAS / "Sistema Analisis Financiero" / "Reportes"))
import brand  # noqa: E402
import flujo_caja as fc  # noqa: E402

RUTA_TEMPLATE = RAIZ / "template.html"
RUTA_DATA_JSON = RAIZ / "data" / "flujo-caja.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"
MARCADORES = ("__FC_FUENTES__", "__FC_LOGO__", "__FC_DATA_B64__")


def renderizar(datos: dict, template: str | None = None) -> str:
    template = RUTA_TEMPLATE.read_text(encoding="utf-8") if template is None else template
    for marcador in MARCADORES:
        if marcador not in template:
            raise ValueError(f"Falta {marcador} en template.html")
    data_b64 = base64.b64encode(json.dumps(datos, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return (template.replace("__FC_FUENTES__", brand.cargar_font_face_lato())
            .replace("__FC_LOGO__", brand.cargar_logo_base64())
            .replace("__FC_DATA_B64__", data_b64))


def _escribir(ruta: Path, texto: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(texto, encoding="utf-8")
    temporal.replace(ruta)


def construir(datos: dict | None = None, ruta_json: Path = RUTA_DATA_JSON, ruta_html: Path = RUTA_BUILD_HTML) -> Path:
    datos = fc.ejecutar(escribir=False) if datos is None else datos
    datos = {k: v for k, v in datos.items() if k != "excel"}
    _escribir(ruta_json, json.dumps(datos, ensure_ascii=False, indent=1))
    _escribir(ruta_html, renderizar(datos))
    return ruta_html


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    ruta = construir()
    print(f"[OK] Tablero de Flujo de Caja: {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
