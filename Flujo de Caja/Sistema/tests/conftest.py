import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _sin_ordenes_del_centro_de_costos(tmp_path_factory, monkeypatch):
    """armar() lee el registro de OC del Centro de Costos real si no se le
    pasa otro: ningun test debe depender de el."""
    import flujo_caja as fc
    monkeypatch.setattr(fc, "RUTA_ORDENES_CC", tmp_path_factory.mktemp("cc") / "ordenes_compra.json")
