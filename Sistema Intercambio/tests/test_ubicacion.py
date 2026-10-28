# -*- coding: utf-8 -*-
import pytest

import ubicacion as ub


@pytest.fixture(autouse=True)
def _sin_variables(monkeypatch):
    for v in ("QUEMPIN_INTERCAMBIO", "QUEMPIN_PLANILLA_REQUERIMIENTOS", "QUEMPIN_ONEDRIVE",
              "QUEMPIN_CARPETA_COMPARTIDA"):
        monkeypatch.delenv(v, raising=False)


def _onedrive(tmp_path):
    base = tmp_path / "OneDrive - QUEMPIN SPA"
    biblioteca = base / "Formulación de proyectos - Documentos"
    (biblioteca / ".HERRAMIENTAS FORMULACIÓN" / "Intercambio").mkdir(parents=True)
    (biblioteca / "Planilla de Ingreso de Requerimientos.xlsx").write_bytes(b"x")
    (base / "Cotizaciones y OC - Documentos" / "Carpeta compartida QUEMPIN").mkdir(parents=True)
    return base


def test_sube_desde_cualquier_carpeta_hasta_la_biblioteca(tmp_path):
    base = _onedrive(tmp_path)
    desde = base / "Cotizaciones y OC - Documentos" / "Carpeta compartida QUEMPIN"
    assert ub.raiz_onedrive(desde) == base
    # Sin distinguir mayúsculas: en el disco quedó «.HERRAMIENTAS FORMULACIÓN».
    assert ub.ubicar_intercambio(desde).name == "Intercambio"
    assert ub.ubicar_intercambio(desde).parent.name == ".HERRAMIENTAS FORMULACIÓN"
    assert ub.ubicar_planilla(desde).name == "Planilla de Ingreso de Requerimientos.xlsx"


def test_sin_biblioteca_devuelve_none(tmp_path):
    otra = tmp_path / "sin onedrive" / "algo"
    otra.mkdir(parents=True)
    assert ub.ubicar_intercambio(otra) is None
    assert ub.ubicar_planilla(otra) is None


def test_variables_de_entorno_mandan(tmp_path, monkeypatch):
    monkeypatch.setenv("QUEMPIN_INTERCAMBIO", str(tmp_path / "X"))
    assert ub.ubicar_intercambio(tmp_path) == tmp_path / "X"


def test_carpeta_compartida_de_sistema_quempin(tmp_path, monkeypatch):
    base = _onedrive(tmp_path)
    assert ub.ubicar_carpeta_quempin(base / "Formulación de proyectos - Documentos") == (
        base / "Cotizaciones y OC - Documentos" / "Carpeta compartida QUEMPIN")
    assert ub.ubicar_carpeta_quempin(tmp_path) is None
    monkeypatch.setenv("QUEMPIN_CARPETA_COMPARTIDA", str(tmp_path / "Y"))
    assert ub.ubicar_carpeta_quempin(tmp_path) == tmp_path / "Y"
