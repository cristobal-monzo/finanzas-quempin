# -*- coding: utf-8 -*-
"""El tablero de Flujo de Caja se arma con datos sintéticos y lleva la marca."""
import os
import sys
from datetime import date
from pathlib import Path

import flujo_caja as fc

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Visualizador Web"))
import build_visualizador as bv  # noqa: E402


def test_construir_inyecta_datos_fuentes_y_logo(tmp_path):
    datos = fc.armar(None, tmp_path / "no-existe.json", hoy=date(2026, 10, 1), sup=dict(fc.SUPUESTOS))
    html = bv.construir(datos, tmp_path / "data.json", tmp_path / "index.html").read_text(encoding="utf-8")
    for marcador in bv.MARCADORES:
        assert marcador not in html
    assert "@font-face" in html and 'src="data:image/png;base64,' in html
    publicados = bv.candado.leer_datos(html, "fc-data-b64", os.environ[bv.candado.VARIABLE_CONTRASENA])
    assert publicados["hoy"] == "2026-10-01"                # cifrados con la contraseña de los tableros (2026-10-05)
    assert 'data-nav-activo="flujo-de-caja"' in html and "QuempinCandado.abrir('fc-data-b64', initApp);" in html
    assert 'id="optSaldo"' in html          # el saldo inicial se puede probar en el tablero (2026-10-02)
