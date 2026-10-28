import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _sin_ordenes_compra_reales(tmp_path_factory, monkeypatch):
    """main() trae las OC de la carpeta compartida de Sistema QUEMPIN y anota
    cada una en ordenes_compra.json. Ningun test debe leer las OC reales ni
    escribir el registro real: la carpeta apunta a una que no existe y el
    registro de cada pais a uno temporal. Un test que necesite OC fija los
    suyos encima."""
    import auditor_centro_costos as acc
    base = tmp_path_factory.mktemp("ordenes_compra")
    monkeypatch.setenv("QUEMPIN_CARPETA_COMPARTIDA", str(base / "sin_sistema_quempin"))
    for pais in list(acc.PAISES):
        cfg = dict(acc.PAISES[pais])
        cfg["ruta_ordenes_compra"] = base / f"ordenes_compra_{pais}.json"
        monkeypatch.setitem(acc.PAISES, pais, cfg)


@pytest.fixture(autouse=True)
def _resetear_pais_activo(_sin_ordenes_compra_reales):
    """auditor_centro_costos.configurar_pais() muta globals compartidos del
    modulo (no via monkeypatch), asi que un test que llame configurar_pais('PE')
    y no la restaure explicitamente (o falle antes de un finally) dejaria ese
    estado filtrado a los tests siguientes. Este fixture autouse garantiza
    'CL' al empezar y al terminar cada test, sin que cada test tenga que
    acordarse."""
    import auditor_centro_costos as acc
    acc.configurar_pais("CL")
    yield
    acc.configurar_pais("CL")
