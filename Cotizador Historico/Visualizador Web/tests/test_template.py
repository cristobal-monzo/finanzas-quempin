# -*- coding: utf-8 -*-
"""Garantias estructurales de template.html (Chile) y su copia de Peru.

El template es un solo HTML con su CSS y su JavaScript de pantalla. No hay
tests de navegador en la suite, asi que estos cubren lo que se rompe sin que
nadie lo vea hasta abrir el dashboard publicado:

- que Chile y Peru no vuelvan a divergir (la taxonomia y el buscador ya lo
  hicieron cuando vivian duplicados en los dos templates);
- que el carrito siga sin tocar el almacenamiento del navegador (requisito
  no negociable del usuario, ver CLAUDE.md § Carrito de cotizacion);
- que cada getElementById del JavaScript apunte a un id que exista en el
  HTML (un refactor de la pantalla que renombra un id deja un boton muerto
  sin ningun error visible hasta que alguien lo toca);
- que el JavaScript de la pantalla sea sintacticamente valido.
"""
import difflib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ_MODULO = Path(__file__).resolve().parents[2]
TEMPLATE_CL = RAIZ_MODULO / "Visualizador Web" / "template.html"
TEMPLATE_PE = RAIZ_MODULO.parent / "Peru" / "Cotizador Historico" / "Visualizador Web" / "template.html"

# Lo UNICO en que Peru puede diferir de Chile: nombre del tablero, subruta
# en la navegacion (data-nav-activo: de ahi salen el pais del selector y la
# pestaña activa), moneda (soles, sin UF) y el pie que explica de donde salen
# los datos. Cualquier otra diferencia es una mejora aplicada a un solo pais.
MARCAS_LINEAS_DE_PAIS = (
    "<title>", "<h1>", "<h2>",
    'data-nav-activo="',
    "Cotizador Historico — datos reales", "la UF vigente al generar",
    "var CLP = new Intl.NumberFormat", "function fmtNum",
    "getElementById('vizGenerated')", "getElementById('exportMeta')",
    '<div class="label">UF utilizada</div>',
    'id="fPrecioMin"', 'id="fPrecioMax"',
)


def _leer(ruta):
    return ruta.read_text(encoding="utf-8")


def _script_app(html):
    """El <script> de la pantalla (el que define initApp)."""
    bloques = re.findall(r"<script>(.*?)</script>", html, re.S)
    return next(b for b in bloques if "function initApp" in b)


@pytest.mark.skipif(not TEMPLATE_PE.exists(), reason="no esta el template de Peru")
def test_peru_solo_difiere_de_chile_en_las_lineas_propias_del_pais():
    cl = _leer(TEMPLATE_CL).split("\n")
    pe = _leer(TEMPLATE_PE).split("\n")
    distintas = []
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(a=cl, b=pe, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        assert op == "replace" and (a2 - a1) == (b2 - b1), (
            f"Chile y Peru ya no tienen la misma estructura cerca de la linea {a1 + 1}: "
            "un cambio de pantalla se aplico a un solo pais")
        distintas.extend(cl[a1:a2])
    ajenas = [l.strip()[:100] for l in distintas
              if not any(m in l for m in MARCAS_LINEAS_DE_PAIS)]
    assert not ajenas, f"lineas que solo cambiaron en un pais: {ajenas}"


def test_el_carrito_nunca_usa_el_almacenamiento_del_navegador():
    js = _script_app(_leer(TEMPLATE_CL))
    # Desde la linea siguiente al encabezado, que justamente dice
    # "(solo en memoria -- nunca localStorage/sessionStorage)".
    inicio = js.index("\n", js.index("// ---------- carrito"))
    fin = js.index("// ---------- texto del carrito")
    seccion = js[inicio:fin]
    assert "localStorage" not in seccion and "sessionStorage" not in seccion
    assert "indexedDB" not in js


@pytest.mark.parametrize("ruta", [TEMPLATE_CL, TEMPLATE_PE], ids=["chile", "peru"])
def test_cada_getElementById_apunta_a_un_id_que_existe(ruta):
    if not ruta.exists():
        pytest.skip("no esta el template")
    html = _leer(ruta)
    ids_html = set(re.findall(r'\bid="([^"]+)"', html))
    usados = set(re.findall(r"getElementById\('([^']+)'\)", _script_app(html)))
    faltan = sorted(usados - ids_html)
    assert not faltan, f"el JavaScript busca ids que el HTML no tiene: {faltan}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node no esta instalado en esta maquina")
@pytest.mark.parametrize("ruta", [TEMPLATE_CL, TEMPLATE_PE], ids=["chile", "peru"])
def test_el_javascript_de_la_pantalla_es_valido(ruta, tmp_path):
    if not ruta.exists():
        pytest.skip("no esta el template")
    archivo = tmp_path / "app.js"
    archivo.write_text(_script_app(_leer(ruta)), encoding="utf-8")
    proc = subprocess.run(["node", "--check", str(archivo)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
