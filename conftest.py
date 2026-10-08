# -*- coding: utf-8 -*-
"""Config comun a todas las suites del repo (ver pytest.ini)."""
import pytest


@pytest.fixture(autouse=True)
def _contrasena_de_prueba_para_los_tableros(monkeypatch):
    """Los builds de los tableros cifran sus datos con la contrasena de los
    tableros (Visualizador Web/candado.py). Los tests usan esta, de prueba:
    la real no esta en CI y no debe aparecer nunca en un test."""
    monkeypatch.setenv("QUEMPIN_TABLEROS_CONTRASENA", "clave ficticia solo para los tests")


@pytest.fixture(autouse=True)
def _ultima_uf_en_carpeta_temporal(monkeypatch, tmp_path):
    """El Cotizador guarda la ultima UF que respondio mindicador.cl como
    respaldo (cotizador_historico.RUTA_ULTIMA_UF). Muchos tests simulan esa
    respuesta: sin esto, una UF inventada quedaria como respaldo real."""
    monkeypatch.setenv("QUEMPIN_UF_ULTIMA", str(tmp_path / "uf_ultima.json"))
