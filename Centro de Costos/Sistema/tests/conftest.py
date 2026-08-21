import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _resetear_pais_activo():
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
