import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import analisis_financiero as af  # noqa: E402


@pytest.fixture(autouse=True)
def _sin_dashboard_real(monkeypatch):
    """ejecutar() regenera el dashboard al final, y lo hace sobre el Excel y el
    build REALES aunque el test le pase un libro de tmp_path. Hasta 2026-10-05
    solo test_presupuestos_formulador lo evitaba: los tests de ejecutar()
    reescribian el tablero real, ahora cifrado con la contrasena de prueba, y
    asi se publico uno que el equipo no podia abrir. Un test que si quiera
    probar ese paso lo vuelve a parchear (ver test_ejecutar.py)."""
    monkeypatch.setattr(af, "actualizar_visualizador_af", lambda pais="CL": True)
