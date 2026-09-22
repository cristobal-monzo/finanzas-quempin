# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el visualizador web de Análisis Financiero Perú.

Desde 2026-09-21 no tiene lógica propia: usa el MISMO build y el MISMO
template.html que Chile (Sistema Analisis Financiero/Visualizador Web/),
parametrizados por país (título, moneda, rutas, pestaña activa). Antes era
una copia completa de los dos archivos, y la copia ya se había quedado atrás
una vez (el renombre Estado -> % Avance, 2026-08-31) y otra con la fase 0 de
la auditoría del dashboard. Este archivo existe solo para que el punto de
entrada de siempre -- analisis_financiero.actualizar_visualizador_af("PE"),
que importa "build_visualizador" desde esta carpeta -- siga funcionando.

Salida: build/index.html y data/analisis-financiero-peru.json de ESTA
carpeta, igual que antes (la receta de publicación no cambia).
"""

import importlib.util
import sys
from pathlib import Path

_RUTA_COMUN = (
    Path(__file__).resolve().parents[3]
    / "Sistema Analisis Financiero" / "Visualizador Web" / "build_visualizador.py"
)
# Nombre distinto de "build_visualizador": este mismo archivo se importa con
# ese nombre, y los dos colisionarían en sys.modules.
_spec = importlib.util.spec_from_file_location("build_visualizador_af_comun", _RUTA_COMUN)
_comun = importlib.util.module_from_spec(_spec)
sys.modules["build_visualizador_af_comun"] = _comun
_spec.loader.exec_module(_comun)

af = _comun.af
PAIS = "PE"
RUTA_EXCEL = _comun.PAISES_VIZ[PAIS]["ruta_excel"]


def extraer_datos_saneados(ruta_excel=None, hoy=None) -> dict:
    return _comun.extraer_datos_saneados(ruta_excel, pais=PAIS, hoy=hoy)


def build() -> int:
    return _comun.build(pais=PAIS)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(build())
