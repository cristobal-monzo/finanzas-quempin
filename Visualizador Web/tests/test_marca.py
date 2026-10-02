# -*- coding: utf-8 -*-
"""Los 4 colores del manual de marca y el naranjo profundo, iguales en
brand.py (reportes PDF), en las plantillas de los tableros y en el hub (plan
de integración, fase 5a, 2026-10-02). Antes se mantenían copiando a mano y
nada avisaba si una copia cambiaba.

El naranjo profundo (#b23a00) es el del texto chico sobre fondo claro; en
tema oscuro los tableros lo aclaran (#ff8a4d)."""
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "Sistema Analisis Financiero" / "Reportes"))
import brand  # noqa: E402

OFICIALES = {
    "orange": "#ff5100",   # Pantone Orange 021 C
    "black": "#000000",    # Black C
    "gray-11": "#54565a",  # Cool Gray 11 C
    "gray-7": "#98989a",   # Cool Gray 7 C
}
NARANJO_PROFUNDO = "#b23a00"
NARANJO_PROFUNDO_OSCURO = "#ff8a4d"

PAGINAS = (sorted(RAIZ.glob("*/Visualizador Web/template.html"))
           + sorted(RAIZ.glob("Peru/*/Visualizador Web/template.html"))
           + [RAIZ / "Visualizador Web" / "index.html"])


def test_brand_py_trae_los_colores_del_manual():
    assert brand.COLOR_NARANJO == OFICIALES["orange"]
    assert brand.COLOR_NEGRO == OFICIALES["black"]
    assert brand.COLOR_GRIS_OSCURO == OFICIALES["gray-11"]
    assert brand.COLOR_GRIS_CLARO == OFICIALES["gray-7"]
    assert brand.COLOR_NARANJO_TINTA == NARANJO_PROFUNDO


def test_estan_todas_las_paginas():
    assert len(PAGINAS) >= 7, [str(p) for p in PAGINAS]


@pytest.mark.parametrize("ruta", PAGINAS, ids=lambda p: str(p.relative_to(RAIZ).parent))
def test_cada_pagina_usa_los_colores_del_manual(ruta):
    texto = ruta.read_text(encoding="utf-8")

    def valores(variable):
        return {v.lower() for v in re.findall(rf"--brand-{variable}:\s*(#[0-9a-fA-F]{{6}})", texto)}

    for nombre, hexa in OFICIALES.items():
        assert valores(nombre) <= {hexa}, (nombre, valores(nombre))
    assert valores("orange") == {OFICIALES["orange"]} and valores("black") == {OFICIALES["black"]}
    tinta = valores("orange-ink")
    assert NARANJO_PROFUNDO in tinta and tinta <= {NARANJO_PROFUNDO, NARANJO_PROFUNDO_OSCURO}, tinta
