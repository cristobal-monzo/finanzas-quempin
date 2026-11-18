"""Parte tests/test_portal.py en tests/portal/test_portal_<vista>.py (fase B de portal/docs/plans/2026-11-18-mejoras-portal.md).

    py -3.14 "Visualizador Web/tests/partir_test_portal.py"

Lo que no es una prueba (constantes, ayudantes, el sitio de mentira, las fixtures) va a tests/portal/portal_comun.py; las
fixtures se enganchan en tests/portal/conftest.py. Cada prueba va al archivo de su sección (# ---- <título>), salvo las de
POR_PRUEBA. Comprueba que ninguna prueba se pierda ni se repita. Uso único, como portal/partir_portal.py: sirve también
en otra rama que agregó pruebas antes de partirse; un título nuevo que no está en SECCIONES lo detiene.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ORIGEN = AQUI / "test_portal.py"
DESTINO = AQUI / "portal"

SECCIONES = [   # (comienzo del título, archivo)
    ("El archivo y su registro", "estructura"),
    ("El portal en el navegador", "basico"),
    ("Dentro del portal las herramientas no repiten", "basico"),
    ("Configuración y conexiones", "conexiones"),
    ("Usuario (2026-10-16)", "basico"),
    ("Las carpetas en el Explorador", "basico"),
    ("Recorrido de proyectos", "recorrido"),
    ("Planificación semanal", "planificacion"),
    ("La vista simple y el arrastre", "planificacion"),
    ("Vehículos de la Planificación", "planificacion"),
    ("Personas y proyectos escritos a mano", "planificacion"),
    ("Subir documentos al Centro de Costos", "subir"),
    ("Rendiciones (2026-11-18)", "rendiciones"),
    ("Proyectos en ejecución", "ejecucion"),
    ("La cotización del Cotizador Histórico", "llevar"),
    ("Planilla de Ingreso en el portal", "planilla"),
    ("«Cerrado» y la carpeta", "planilla"),
    ("Clic derecho y observaciones", "observaciones"),
    ("Errores sin aviso", "observaciones"),
    ("Apodo del proyecto y postventas", "apodo"),
    ("«Qué buscamos» del tablero de Oportunidades", "oportunidades"),
]
# Pruebas que quedaron en otra sección del archivo de una pieza
POR_PRUEBA = {
    "test_lo_agregado_a_mano_es_de_su_semana_y_se_copia_con_lo_suyo": "planificacion",
    "test_el_menu_personal_elige_quienes_se_ven_y_agrega_personal_definitivo_o_temporal": "planificacion",
    "test_el_buscador_ofrece_formulador_seguimiento_o_ejecucion_segun_la_etapa": "basico",
}
QUE_ES = {
    "estructura": "el archivo, su registro y lo que leen las demás herramientas (casi todo sin navegador)",
    "basico": "el portal en el navegador: menú, pestañas y marcos, buscador, usuario, teléfono y al día sin F5",
    "conexiones": "Configuración y conexiones",
    "recorrido": "Recorrido de proyectos e Inicio",
    "planificacion": "Planificación semanal",
    "subir": "Subir documentos al Centro de Costos",
    "rendiciones": "Rendiciones",
    "ejecucion": "Proyectos en ejecución",
    "llevar": "Llevar la cotización del Cotizador Histórico a un proyecto",
    "planilla": "Requerimientos (Planilla de Ingreso) y «Cerrado»",
    "observaciones": "clic derecho, errores y observaciones, y errores sin aviso",
    "apodo": "apodo del proyecto, postventas y N° temporales",
    "oportunidades": "«Qué buscamos» del tablero de Oportunidades",
}
MARCA = re.compile(r"^# (?:----|──) (.*?)\s*(?:[-─]{3,}.*)?$")
FIXTURES = ("sitio", "navegador")

# Cambios al código común: (texto exacto, reemplazo, veces)
CAMBIOS_COMUN = [
    ('AQUI = Path(__file__).resolve().parent\n',
     'AQUI = Path(__file__).resolve().parents[1]          # tests/ (este archivo está en tests/portal/)\n', 1),
    ('    (raiz / "finanzas-quempin" / "portal").mkdir(parents=True)\n'
     '    (raiz / "finanzas-quempin" / "portal" / "index.html").write_bytes(PORTAL.read_bytes())\n',
     '    # El Portal con sus partes (portal.css, js/), como lo deja publicar.py\n'
     '    shutil.copytree(PORTAL.parent, raiz / "finanzas-quempin" / "portal",\n'
     '                    ignore=shutil.ignore_patterns("docs", "*.py", "*.md", "__pycache__"))\n', 1),
]
CAMBIOS_PRUEBAS = [
    ('    # El único script enlazado es el de las cajas de números, del mismo sitio (2026-11-10): publicar.py lo copia con él.\n'
     '    assert re.findall(r"<script[^>]+\\bsrc=[^>]*>", html) == [\'<script src="../numeros.js">\'], "sin scripts externos"\n'
     '    # La única hoja que enlaza es la de las fuentes, del mismo sitio (2026-10-30): publicar.py la copia con él.\n'
     '    assert re.findall(r"<link[^>]+stylesheet[^>]*>", html) == [\'<link rel="stylesheet" href="../marca/fuentes.css">\']\n',
     '    # Los scripts enlazados son el de las cajas de números (2026-11-10) y los del Portal en js/ (2026-11-18), del mismo\n'
     '    # sitio: publicar.py los copia con él.\n'
     '    scripts = re.findall(r"<script[^>]+\\bsrc=[^>]*>", html)\n'
     '    assert scripts == [\'<script src="../numeros.js">\'] + [f\'<script src="js/{a}">\' for a in archivos_js()], "sin scripts externos"\n'
     '    # Las hojas que enlaza son la de las fuentes (2026-10-30) y portal.css (2026-11-18), del mismo sitio.\n'
     '    assert re.findall(r"<link[^>]+stylesheet[^>]*>", html) == [\'<link rel="stylesheet" href="../marca/fuentes.css">\',\n'
     '                                                              \'<link rel="stylesheet" href="portal.css">\']\n', 1),
    # Sin el IIFE, el código tiene 2 espacios menos de sangría
    ('''    assert all(f"\\n    {i}: '" in portal.replace("\\r\\n", "\\n") for i in iconos)''',
     '''    assert all(f"\\n  {i}: '" in portal.replace("\\r\\n", "\\n") for i in iconos)''', 1),
    # Falló en el CI (2026-11-18): con el CI lento, el cambio llegaba antes de que se leyera la base y no se veía. Sin el
    # IIFE, ad y estado se pueden mirar desde la prueba: se espera a que estén leídas, no un tiempo fijo.
    ('        pagina.wait_for_timeout(500)                         # las bases se leen con fetch de verdad\n',
     '        # Las bases se leen con fetch de verdad: la del Portal y la de cada herramienta abierta\n'
     '        pagina.wait_for_function("() => ad.portal && !ad.revisando && estado.pestanas.every((p) => !p.marco || p.ad)")\n', 1),
]

TEXTO_PORTAL = '''

# ---- El Portal partido en archivos (2026-11-18) ---------------------------------------------------------------------

def archivos_js():
    """Los js/ del Portal en el orden en que index.html los carga."""
    return re.findall(r'<script src="js/([^"]+)"></script>', PORTAL.read_text(encoding="utf-8"))


def texto_portal():
    """index.html, portal.css y cada js/ en su orden, juntos: lo que hasta el 2026-11-18 era un solo archivo. Para las
    pruebas que buscan un texto en el código; las que miran el HTML mismo leen PORTAL."""
    partes = [PORTAL, PORTAL.parent / "portal.css", *(PORTAL.parent / "js" / a for a in archivos_js())]
    return "\\n".join(p.read_text(encoding="utf-8") for p in partes)
'''

CONFTEST = '''"""Las pruebas del Portal (tests/portal/): lo común está en portal_comun.py. El repo corre pytest con
--import-mode=importlib, que no agrega esta carpeta a sys.path: se agrega aquí, antes de que se lean las pruebas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from portal_comun import navegador, sitio  # noqa: E402,F401  (un sitio de mentira y un Chromium por archivo)
'''


class NoSePuede(Exception):
    pass


def _reemplazar(texto: str, cambios, donde: str) -> str:
    for viejo, nuevo, veces in cambios:
        if texto.count(viejo) != veces:
            raise NoSePuede(f"{donde}: se esperaba {veces} vez el texto {viejo[:70]!r}, hay {texto.count(viejo)}")
        texto = texto.replace(viejo, nuevo)
    return texto


def partir(src: str) -> dict[str, str]:
    lineas = src.split("\n")
    arbol = ast.parse(src)
    nodos = arbol.body
    if not (isinstance(nodos[0], ast.Expr) and isinstance(nodos[0].value, ast.Constant)):
        raise NoSePuede("falta la docstring")
    # Cada nodo se lleva las líneas desde el fin del anterior (comentarios y líneas en blanco de encima)
    fin_anterior = nodos[0].end_lineno
    seccion = None
    comun, pruebas = [], {}
    nombres_prueba = []
    imports = []
    for n in nodos[1:]:
        inicio = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])])
        hueco = lineas[fin_anterior:inicio - 1]
        cuerpo = "\n".join(lineas[inicio - 1:n.end_lineno])
        fin_anterior = n.end_lineno
        # Los títulos del hueco: cambian la sección; el título y su comentario de abajo van con la sección
        resto, cabeza = [], []
        i = 0
        while i < len(hueco):
            m = MARCA.match(hueco[i])
            if m:
                titulo = m.group(1)
                destino = next((a for t, a in SECCIONES if titulo.startswith(t)), None)
                if destino is None:
                    raise NoSePuede(f"título sin archivo en SECCIONES: {titulo!r}")
                seccion = destino
                bloque = [hueco[i]]
                i += 1
                while i < len(hueco) and hueco[i].startswith("#"):
                    bloque.append(hueco[i])
                    i += 1
                cabeza.append((destino, bloque))
                resto.append(hueco[bloque and i - len(bloque)])      # el título solo, para orientarse en lo común
                continue
            resto.append(hueco[i])
            i += 1
        for destino, bloque in cabeza:
            pruebas.setdefault(destino, []).append("\n\n" + "\n".join(bloque))
        es_prueba = isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            imports.append(cuerpo)
            comun.append("\n".join(resto) + ("\n" if resto else "") + cuerpo)
        elif es_prueba:
            if seccion is None:
                raise NoSePuede(f"{n.name}: prueba antes del primer título")
            destino = POR_PRUEBA.get(n.name, seccion)
            nombres_prueba.append(n.name)
            texto = "\n".join(l for l in resto if not MARCA.match(l)).strip("\n")
            pruebas.setdefault(destino, []).append(("\n\n\n" + texto + "\n" if texto else "\n\n\n") + cuerpo)
        else:
            comun.append("\n".join(resto) + ("\n" if resto else "") + cuerpo)
    if len(nombres_prueba) != len(set(nombres_prueba)):
        raise NoSePuede("hay pruebas con el mismo nombre")

    doc = ast.get_docstring(arbol)
    salida = {}
    texto_comun = ('# -*- coding: utf-8 -*-\n"""' + doc + '\n\nDesde el 2026-11-18 las pruebas están en tests/portal/test_portal_<vista>.py y aquí '
                   'queda lo común: rutas, el sitio de mentira, las fixtures, constantes y ayudantes."""\n'
                   + "\n".join(comun) + "\n" + TEXTO_PORTAL
                   + '\n\n# Lo que importa «from portal_comun import *»: todo menos las fixtures (las engancha conftest.py)\n'
                   + '__all__ = [n for n in dir() if not n.startswith("__") and n not in ' + repr(FIXTURES) + ']\n')
    texto_comun = _reemplazar(texto_comun, CAMBIOS_COMUN, "portal_comun.py")
    texto_comun = texto_comun.replace('PORTAL.read_text(encoding="utf-8")', "texto_portal()")
    texto_comun = texto_comun.replace("def archivos_js():\n    \"\"\"Los js/ del Portal en el orden en que index.html los carga.\"\"\"\n"
                                      "    return re.findall(r'<script src=\"js/([^\"]+)\"></script>', texto_portal())",
                                      "def archivos_js():\n    \"\"\"Los js/ del Portal en el orden en que index.html los carga.\"\"\"\n"
                                      "    return re.findall(r'<script src=\"js/([^\"]+)\"></script>', PORTAL.read_text(encoding=\"utf-8\"))")
    texto_comun = texto_comun.replace("    partes = [PORTAL, PORTAL.parent / \"portal.css\", *(PORTAL.parent / \"js\" / a for a in archivos_js())]\n"
                                      "    return \"\\n\".join(p.read_text(encoding=\"utf-8\") for p in partes)",
                                      "    partes = [PORTAL, PORTAL.parent / \"portal.css\", *(PORTAL.parent / \"js\" / a for a in archivos_js())]\n"
                                      "    return \"\\n\".join(p.read_text(encoding=\"utf-8\") for p in partes)")
    salida["portal_comun.py"] = texto_comun
    salida["conftest.py"] = CONFTEST
    cambios_hechos = {id(c): 0 for c in CAMBIOS_PRUEBAS}
    for archivo, partes in pruebas.items():
        cuerpo = "".join(partes).lstrip("\n")
        for c in CAMBIOS_PRUEBAS:
            if c[0] in cuerpo:
                cuerpo = cuerpo.replace(c[0], c[1])
                cambios_hechos[id(c)] += 1
        cuerpo = cuerpo.replace('PORTAL.read_text(encoding="utf-8")', "texto_portal()")
        salida[f"test_portal_{archivo}.py"] = (
            f'# -*- coding: utf-8 -*-\n"""Portal QUEMPIN: {QUE_ES[archivo]}.\n\n'
            f'Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""\n'
            f"import pytest  # noqa: F401\n\nfrom portal_comun import *  # noqa: F401,F403\n\n\n{cuerpo.rstrip()}\n")
    for c in CAMBIOS_PRUEBAS:
        if cambios_hechos[id(c)] != c[2]:
            raise NoSePuede(f"pruebas: se esperaba {c[2]} vez el texto {c[0][:70]!r}, hay {cambios_hechos[id(c)]}")
    # Ninguna prueba se pierde ni se repite
    repartidas = []
    for archivo, texto in salida.items():
        if archivo.startswith("test_"):
            repartidas += [n.name for n in ast.parse(texto).body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    if sorted(repartidas) != sorted(nombres_prueba):
        raise NoSePuede("las pruebas repartidas no son las del original")
    for archivo, texto in salida.items():
        compile(texto, archivo, "exec")
    return salida


def main() -> int:
    src = ORIGEN.read_bytes().decode("utf-8").replace("\r\n", "\n")
    try:
        salida = partir(src)
    except NoSePuede as e:
        print(f"[NO] {e}")
        return 1
    DESTINO.mkdir(exist_ok=True)
    for archivo, texto in salida.items():
        (DESTINO / archivo).write_bytes(texto.encode("utf-8"))
    ORIGEN.unlink()
    print("[OK] " + ", ".join(f"{a} {t.count(chr(10))}" for a, t in salida.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
