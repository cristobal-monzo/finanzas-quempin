# -*- coding: utf-8 -*-
import pytest

import ubicacion as ub


@pytest.fixture(autouse=True)
def _sin_variables(monkeypatch):
    for v in ("QUEMPIN_INTERCAMBIO", "QUEMPIN_PLANILLA_REQUERIMIENTOS", "QUEMPIN_ONEDRIVE"):
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
