"""Parte portal/index.html en portal.css y portal/js/<vista>.js (fase B de docs/plans/2026-11-18-mejoras-portal.md).

Uso, desde la raíz del repo o desde portal/:

    py -3.14 "Visualizador Web/portal/partir_portal.py"            # parte index.html en su lugar
    py -3.14 "Visualizador Web/portal/partir_portal.py" --revisar  # solo revisa que se pueda partir

Corta por los títulos de sección (`// ---- <título>`), no por número de línea: sirve igual en otra rama que cambió el
Portal antes de partirse (carpetas-estados, cotizador-exportar). Antes de escribir nada comprueba que los trozos, unidos
de nuevo en su orden original y con la sangría del IIFE, son exactamente el original. Uso único: se borra cuando las
ramas que tocaban el index.html entero ya están partidas.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

# Cada tramo empieza en su título y sigue hasta el título del tramo siguiente. El orden de esta lista es el del archivo
# original; ORDEN es el orden de carga. Un archivo puede juntar tramos que en el original no eran vecinos
# (la Planificación quedó partida por Subir y Rendiciones): esos tramos solo declaran, así que se pueden mover.
TRAMOS = [
    (None, "base.js"),                                                   # desde 'use strict'
    ("Configuración y conexiones", "conexiones.js"),
    ("Recorrido de proyectos (2026-10-20)", "recorrido.js"),
    ("Inicio: las herramientas por área (2026-11-10)", "inicio.js"),
    ("Planificación semanal (2026-10-20)", "planificacion.js"),
    ("Subir documentos al Centro de Costos (2026-10-23)", "subir.js"),
    ("Rendiciones (2026-11-18)", "rendiciones.js"),
    ("La alarma, fuera de la vista", "planificacion.js"),
    ("Planilla de Ingreso (2026-10-29)", "planilla.js"),
    ("Proyectos en ejecución (2026-10-28)", "ejecucion.js"),
    ("La cotización del Cotizador Histórico, a un proyecto (2026-10-29)", "llevar.js"),
    ("Buscador", "buscador.js"),
    ("Clic derecho: el menú del portal (2026-10-30)", "observaciones.js"),
    ("Tema", "tema.js"),
    ("Arranque", "arranque.js"),
]
ORDEN = ["base.js", "conexiones.js", "recorrido.js", "inicio.js", "planificacion.js", "subir.js", "rendiciones.js",
         "planilla.js", "ejecucion.js", "llevar.js", "buscador.js", "observaciones.js", "tema.js", "arranque.js"]
QUE_ES = {
    "base.js": "utilidades, estado, menú, pestañas y marcos, al día sin F5, usuario y diálogos",
    "conexiones.js": "Configuración y conexiones: la carpeta del equipo y lo que necesita cada herramienta",
    "recorrido.js": "Recorrido de proyectos (rc*)",
    "inicio.js": "Inicio: las herramientas por área y la semana (ini*)",
    "planificacion.js": "Planificación semanal (pl*, planif)",
    "subir.js": "Subir documentos al Centro de Costos (sc*)",
    "rendiciones.js": "Rendiciones (rd*)",
    "planilla.js": "Requerimientos, antes Planilla de Ingreso (pq*)",
    "ejecucion.js": "Proyectos en ejecución (ej*)",
    "llevar.js": "Llevar la cotización del Cotizador Histórico a un proyecto (ll*)",
    "buscador.js": "Buscador (Ctrl K)",
    "observaciones.js": "Clic derecho, reportar errores y observaciones, errores sin aviso (ctx*, obs*, er*)",
    "tema.js": "Tema claro u oscuro y lo que el Portal esconde de cada herramienta",
    "arranque.js": "Arranque: engancha los botones y abre la herramienta pedida. Va última",
}

INICIO_CSS = "<style>\n"
FIN_CSS = "</style>\n</head>\n"
INICIO_JS = "<script>\n(function () {\n  'use strict';\n"
FIN_JS = "})();\n</script>\n</body>\n</html>\n"
# El return temprano del IIFE (un portal dentro de otro) no puede ir en un script sin función: pasa a un script en
# línea antes de los demás, que en ese caso detiene la carga de la página (window.stop) y así no corre ninguno.
ANIDADO = """
  // Un enlace al portal desde una herramienta abierta en él no anida otro portal: vuelve al inicio.
  if (window.top !== window.self) {
    try {
      if (window.top.location.pathname === window.location.pathname) {
        document.body.textContent = '';
        window.top.location.hash = '#/';
        return;
      }
    } catch (e) { /* lo abre otro sitio: sigue normal */ }
  }
"""
ANIDADO_NUEVO = """<script>
/* Un enlace al portal desde una herramienta abierta en él no anida otro portal: vuelve al inicio. window.stop() detiene
   la lectura de la página, así no se carga ningún script de js/ en el portal de adentro. */
if (window.top !== window.self) {
  try {
    if (window.top.location.pathname === window.location.pathname) {
      document.body.textContent = '';
      window.top.location.hash = '#/';
      window.stop();
    }
  } catch (e) { /* lo abre otro sitio: sigue normal */ }
}
</script>
"""


class NoSePuede(Exception):
    pass


def _sin_sangria(texto: str, que: str) -> str:
    """Quita los 2 espacios del IIFE o del <style>. Toda línea con algo lleva esa sangría, o no se parte."""
    salida = []
    for n, l in enumerate(texto.split("\n"), 1):
        if l.strip() == "":
            salida.append("")
        elif l.startswith("  "):
            salida.append(l[2:])
        else:
            raise NoSePuede(f"{que}, línea {n} sin la sangría de 2 espacios: {l[:80]!r}")
    return "\n".join(salida)


def _con_sangria(texto: str) -> str:
    return "\n".join(("  " + l) if l else "" for l in texto.split("\n"))


def _titulo(l: str) -> str | None:
    m = re.match(r"^  (?://|/\*) ---- (.*?)\s*(?:-{3,}.*)?$", l)
    return m.group(1).strip() if m else None


def partir(html: str) -> tuple[str, str, dict[str, str]]:
    """(index.html nuevo, portal.css, {archivo: js}). Lanza NoSePuede si el original no tiene la forma esperada."""
    if "\r" in html:
        raise NoSePuede("el archivo tiene finales de línea CRLF: léelo desde git (LF)")
    for marca in (INICIO_CSS, FIN_CSS, INICIO_JS, FIN_JS):
        if html.count(marca) != 1:
            raise NoSePuede(f"{marca.strip()!r} aparece {html.count(marca)} veces (se espera 1)")
    i_css, f_css = html.index(INICIO_CSS), html.index(FIN_CSS)
    css = _sin_sangria(html[i_css + len(INICIO_CSS):f_css].rstrip("\n"), "CSS") + "\n"
    i_js, f_js = html.index(INICIO_JS), html.index(FIN_JS)
    if not html.endswith(FIN_JS):
        raise NoSePuede("después del script principal hay algo más que </body></html>")
    cuerpo = html[i_js + len(INICIO_JS):f_js]
    if not cuerpo.startswith(ANIDADO):
        raise NoSePuede("el script principal no empieza con el bloque del portal anidado")
    resto = cuerpo[len(ANIDADO):]
    lineas = resto.split("\n")

    # Dónde empieza cada tramo
    titulos = {}
    for n, l in enumerate(lineas):
        t = _titulo(l)
        if t is not None:
            titulos.setdefault(t, []).append(n)
    inicios = [0]
    for titulo, _ in TRAMOS[1:]:
        donde = titulos.get(titulo, [])
        if len(donde) != 1:
            raise NoSePuede(f"el título «{titulo}» aparece {len(donde)} veces en el JS (se espera 1)")
        inicios.append(donde[0])
    if inicios != sorted(inicios):
        raise NoSePuede("los títulos no están en el orden de TRAMOS")
    inicios.append(len(lineas))
    trozos = ["\n".join(lineas[a:b]) for a, b in zip(inicios, inicios[1:])]

    # Unidos de nuevo, en el orden original, deben dar el original exacto
    if "\n".join(trozos) != resto:
        raise NoSePuede("los trozos unidos no dan el original")
    por_archivo: dict[str, list[str]] = {a: [] for a in ORDEN}
    for (_, archivo), trozo in zip(TRAMOS, trozos):
        por_archivo[archivo].append(_sin_sangria(trozo, archivo).strip("\n"))
    if set(por_archivo) != set(ORDEN) or any(not v for v in por_archivo.values()):
        raise NoSePuede("cada archivo de ORDEN necesita al menos un tramo")
    js = {}
    for archivo in ORDEN:
        cabeza = (f"/* Portal QUEMPIN — {QUE_ES[archivo]}.\n"
                  f"   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan\n"
                  f"   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita\n"
                  f"   ni tape uno del navegador (window.open, name, status...). */\n'use strict';\n\n")
        js[archivo] = cabeza + "\n\n".join(por_archivo[archivo]) + "\n"
    # Vuelta atrás: quitar cabezas y volver a sangrar debe dar cada trozo
    for archivo in ORDEN:
        cuerpo_js = js[archivo].split("'use strict';\n\n", 1)[1].rstrip("\n")
        esperado = "\n\n".join(_sin_sangria(t, archivo).strip("\n")
                               for (_, a), t in zip(TRAMOS, trozos) if a == archivo)
        if cuerpo_js != esperado or _sin_sangria(_con_sangria(esperado), archivo) != esperado:
            raise NoSePuede(f"{archivo}: la vuelta atrás no da el original")

    # Los comentarios que nombraban la prueba de una pieza
    for a in ORDEN:
        js[a] = _sin_test_portal(js[a])
    scripts = "".join(f'<script src="js/{a}"></script>\n' for a in ORDEN)
    nuevo = (html[:i_css]
             + '<link rel="stylesheet" href="portal.css">\n'
             + html[f_css + len("</style>\n"):i_js]
             + ANIDADO_NUEVO
             + "<!-- El código del Portal, una parte por vista (portal/js/). El orden importa: base.js primero y\n"
               "     arranque.js al final, que engancha todo. Ver portal/CLAUDE.md. -->\n"
             + scripts
             + "</body>\n</html>\n")
    return _sin_test_portal(nuevo), css, js


def _sin_test_portal(texto: str) -> str:
    """tests/test_portal.py se partió en tests/portal/ (partir_test_portal.py): los comentarios que la nombran."""
    texto = texto.replace("Visualizador Web/tests/test_portal.py", "Visualizador Web/tests/portal/")
    texto = texto.replace("lo prueba test_portal.py", "lo prueba tests/portal/test_portal_rendiciones.py")
    return texto.replace("test_portal.py", "tests/portal/")


def main(argv: list[str]) -> int:
    indice = AQUI / "index.html"
    if "--desde" in argv:      # --desde <ref>: el index.html de una pieza tal como está en git (para partirlo de nuevo)
        import subprocess
        ref = argv[argv.index("--desde") + 1]
        html = subprocess.run(["git", "-C", str(AQUI), "show", f"{ref}:./index.html"], capture_output=True,
                              check=True).stdout.decode("utf-8")
    else:
        html = indice.read_bytes().decode("utf-8")
    html = html.replace("\r\n", "\n")
    try:
        nuevo, css, js = partir(html)
    except NoSePuede as e:
        print(f"[NO] {e}")
        return 1
    tam = {a: t.count("\n") for a, t in js.items()}
    print(f"[OK] index.html {html.count(chr(10))} -> {nuevo.count(chr(10))} líneas; portal.css {css.count(chr(10))}; "
          + ", ".join(f"{a} {n}" for a, n in tam.items()))
    if "--revisar" in argv:
        return 0
    (AQUI / "js").mkdir(exist_ok=True)
    for a, t in js.items():
        (AQUI / "js" / a).write_bytes(t.encode("utf-8"))
    (AQUI / "portal.css").write_bytes(css.encode("utf-8"))
    indice.write_bytes(nuevo.encode("utf-8"))
    print("[OK] escrito: index.html, portal.css y js/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
