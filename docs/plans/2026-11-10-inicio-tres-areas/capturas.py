"""Capturas del Inicio con el sitio y la carpeta de mentira de test_portal.py (sin datos reales)."""
import functools
import http.server
import sys
import threading
import tempfile
from pathlib import Path

TESTS = Path(sys.argv[1])
SALIDA = Path(sys.argv[2])
TAMANOS = [tuple(map(int, t.split("x"))) for t in (sys.argv[3:] or ["1366x657", "1536x730", "1024x640", "1920x1000", "390x844"])]
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(TESTS.parent.parent))
import test_portal as tp  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

raiz = Path(tempfile.mkdtemp())
tp._sitio(raiz)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(tp._Silencioso, directory=str(raiz)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
sitio = f"http://127.0.0.1:{srv.server_address[1]}"
SALIDA.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    nav = p.chromium.launch()
    for ancho, alto in TAMANOS:
        movil = ancho < 760
        for usuario in ("LC", None):
            pagina, errores = tp._portal_con_datos(nav, sitio, usuario, ancho=ancho, alto=alto, movil=movil, proyectos=True)
            pagina.locator("#iniAreas .ini-item").first.wait_for()
            pagina.wait_for_timeout(600)
            barras = pagina.evaluate(tp.JS_BARRAS)
            nombre = f"inicio-{ancho}x{alto}-{usuario or 'sin'}.png"
            pagina.screenshot(path=str(SALIDA / nombre), full_page=movil)
            print(nombre, "barras:", barras, "errores:", errores)
            pagina.context.close()
    nav.close()
srv.shutdown()
