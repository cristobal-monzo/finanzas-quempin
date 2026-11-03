# -*- coding: utf-8 -*-
"""mismo_proyecto.nombre_de_carpeta es copia de normalizar_nombre_proyecto del
Centro de Costos: la ficha del Análisis Financiero lleva ese nombre."""
import sys
from pathlib import Path

import mismo_proyecto as mp

CC = Path(__file__).resolve().parents[2] / "Centro de Costos" / "Sistema"


def test_el_nombre_de_carpeta_es_el_mismo_que_da_el_centro_de_costos():
    sys.path.insert(0, str(CC))
    try:
        import auditor_centro_costos as acc
    finally:
        sys.path.remove(str(CC))
    for nombre in ["280. UMAG - Conexión y PH Lab 1", "259. FACH 2", "UMAG", "1234_Nombre", "1234-Nombre",
                   "317. Quimetal -Flujómetros", "Junji's Valparaiso", "036. Fiscalía Quilpué y Quintero"]:
        assert mp.nombre_de_carpeta(nombre) == acc.normalizar_nombre_proyecto(nombre), nombre


def test_carpeta_ajena():
    carpetas = [{"nombre": "UMAG", "req": None, "documentos": 45},
                {"nombre": "280. UMAG - Conexión y PH Lab 1", "req": "280", "documentos": 1}]
    assert mp.carpeta_ajena("UMAG", "280", carpetas) == {"ficha": "UMAG", "req": "280. UMAG - Conexión y PH Lab 1"}
    assert mp.carpeta_ajena("umag - conexion y ph lab1", 280, carpetas) is None
    assert mp.carpeta_ajena("UMAG", "999", carpetas) is None      # el N° sin carpeta: no se sabe
    assert mp.carpeta_ajena("Otro", "280", carpetas) is None      # la ficha sin carpeta: no se sabe
    assert mp.carpeta_ajena("UMAG", None, carpetas) is None
