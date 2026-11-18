"""Las pruebas del Portal (tests/portal/): lo común está en portal_comun.py. El repo corre pytest con
--import-mode=importlib, que no agrega esta carpeta a sys.path: se agrega aquí, antes de que se lean las pruebas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from portal_comun import navegador, sitio  # noqa: E402,F401  (un sitio de mentira y un Chromium por archivo)
