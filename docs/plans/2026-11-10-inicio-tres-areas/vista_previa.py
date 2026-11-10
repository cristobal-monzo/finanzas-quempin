"""Vista previa local del Portal QUEMPIN con el Inicio nuevo.

Sirve el portal y marca/ del worktree; todo lo demás (Formulador, tableros, calculadoras) lo trae del sitio
publicado, así las herramientas se abren dentro del portal igual que en producción. Uso:
    py -3.14 vista_previa.py <carpeta Visualizador Web del worktree> [puerto]
"""
import http.server
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path

VW = Path(sys.argv[1])
PUERTO = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
ORIGEN = "https://cristobal-monzo.github.io"
LOCALES = {
    "/finanzas-quempin/portal/": VW / "portal" / "index.html",
    "/finanzas-quempin/portal/index.html": VW / "portal" / "index.html",
}

class SinRedirigir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


ABRIDOR = urllib.request.build_opener(SinRedirigir)


class Vista(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, codigo, cuerpo, tipo, extra=None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        ruta = self.path.split("?")[0].split("#")[0]
        if ruta in ("/", "/finanzas-quempin", "/finanzas-quempin/portal"):
            self._enviar(302, b"", "text/plain", {"Location": "/finanzas-quempin/portal/"})
            return
        if ruta in LOCALES:
            self._enviar(200, LOCALES[ruta].read_bytes(), "text/html; charset=utf-8")
            return
        if ruta.startswith("/finanzas-quempin/marca/"):
            f = (VW / "marca" / ruta.rsplit("/", 1)[-1])
            if f.is_file():
                tipo = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                self._enviar(200, f.read_bytes(), tipo)
                return
        try:
            with ABRIDOR.open(urllib.request.Request(ORIGEN + self.path, headers={"User-Agent": "quempin-vista-previa"}), timeout=30) as r:
                self._enviar(r.status, r.read(), r.headers.get("Content-Type", "application/octet-stream"))
        except urllib.error.HTTPError as e:
            extra = {}
            if e.headers.get("Location"):
                extra["Location"] = e.headers["Location"].replace(ORIGEN, "")
            self._enviar(e.code, e.read() or b"", e.headers.get("Content-Type", "text/plain"), extra)
        except Exception as e:  # sin conexión
            self._enviar(502, str(e).encode("utf-8"), "text/plain; charset=utf-8")


print(f"Vista previa: http://localhost:{PUERTO}/finanzas-quempin/portal/", flush=True)
http.server.ThreadingHTTPServer(("127.0.0.1", PUERTO), Vista).serve_forever()
