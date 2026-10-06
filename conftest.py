# -*- coding: utf-8 -*-
"""Config comun a todas las suites del repo (ver pytest.ini)."""
import pytest


@pytest.fixture(autouse=True)
def _contrasena_de_prueba_para_los_tableros(monkeypatch):
    """Los builds de los tableros cifran sus datos con la contrasena de los
    tableros (Visualizador Web/candado.py). Los tests usan esta, de prueba:
    la real no esta en CI y no debe aparecer nunca en un test."""
    monkeypatch.setenv("QUEMPIN_TABLEROS_CONTRASENA", "clave ficticia solo para los tests")
