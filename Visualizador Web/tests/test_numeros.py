# -*- coding: utf-8 -*-
"""Cajas de números (pedido del usuario, 2026-11-10).

En todas las herramientas, una caja con números se selecciona entera al hacer clic (lo que se escribe
reemplaza al 0 que había) y muestra el punto de miles mientras se escribe y en lo que se ve. Lo hace
`numeros.js`, una sola copia: los tableros la llevan incrustada (candado.incrustar), el Portal y el hub
la enlazan (../numeros.js, que publicar.py copia a gh-pages), y el Formulador y la Calculadora Técnica
llevan una copia idéntica.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "Visualizador Web"))
import candado  # noqa: E402
import publicar  # noqa: E402

NUMEROS = RAIZ / "Visualizador Web" / "numeros.js"
COPIAS = {
    "Formulador": candado.RUTA_INDEX_FORMULADOR.parent / "js" / "numeros.js",
    "Calculadora Técnica": candado.RAIZ_REPO.parent / "Calculadora Técnica" / "assets" / "numeros.js",
}


@pytest.mark.parametrize("herramienta", list(COPIAS))
def test_las_otras_herramientas_llevan_la_misma_copia(herramienta):
    """Si cambias numeros.js, cópialo tal cual a las otras dos herramientas (son otros repositorios)."""
    copia = COPIAS[herramienta]
    if not copia.parent.parent.exists():
        pytest.skip(f"{herramienta} no está en esta máquina")
    # Sin contar el fin de línea: git deja CRLF en algunos equipos (core.autocrlf)
    assert copia.read_bytes().replace(b"\r\n", b"\n") == NUMEROS.read_bytes().replace(b"\r\n", b"\n"), \
        f"{copia} no es igual a {NUMEROS}"


def test_cada_tablero_la_lleva_incrustada():
    html = candado.incrustar(f"<script>{candado.MARCADOR_JS}</script>"
                             '<script id="x" type="text/plain">__XX__</script>', "__XX__", "{}", "clave")
    assert "var QuempinCandado" in html and "window.QuempinNumeros" in html
    # Nada en numeros.js puede cerrar el <script> en el que va incrustada
    assert "</script" not in NUMEROS.read_text(encoding="utf-8").lower()


@pytest.mark.parametrize("clave,destino", [("hub", "index.html"), ("portal", "portal/index.html")])
def test_el_hub_y_el_portal_se_publican_con_numeros_js(tmp_path, clave, destino):
    gh = tmp_path / "gh-pages"
    gh.mkdir()
    publicar.preparar_estatico(clave, raiz_gh_pages=gh)
    assert (gh / "numeros.js").read_bytes() == NUMEROS.read_bytes()


def test_el_portal_enlaza_numeros_js():
    portal = (RAIZ / "Visualizador Web" / "portal" / "index.html").read_text(encoding="utf-8")
    assert '<script src="../numeros.js"></script>' in portal


@pytest.mark.parametrize("ruta,marca", [
    ("Visualizador Web/portal/index.html", 'id="ejCCant" type="text" inputmode="decimal" data-num'),
    ("Visualizador Web/portal/index.html", 'id="ejVMonto" type="text" inputmode="numeric" data-num="entero"'),
    ("Flujo de Caja/Visualizador Web/template.html", 'id="optSaldo" type="text" inputmode="numeric" data-num="entero"'),
    ("Sistema Analisis Financiero/Visualizador Web/template.html", "' data-num=\"entero\"'"),
])
def test_las_cajas_de_montos_en_texto_piden_el_formato(ruta, marca):
    """Las cajas de texto con su propio lector chileno (no las type="number", que se toman solas) llevan
    data-num. Un N° de OC o de requerimiento no: es un código, no una cantidad."""
    assert marca in (RAIZ / ruta).read_text(encoding="utf-8")


# ---- En el navegador ----------------------------------------------------------------------------------------

PAGINA = """<!doctype html><meta charset="utf-8"><body>
<input id="cant" type="number" step="any" value="0">
<input id="ent" type="number" min="0" step="1" value="1500">
<input id="txt" type="text" inputmode="decimal" data-num value="1234567">
<input id="oc" type="text" inputmode="numeric" value="4500123456">
<input id="nombre" type="text" value="hola">
<div id="zona"></div>
<script>
window.eventos = [];
document.addEventListener('input', (e) => eventos.push(['input', e.target.id, e.target.value]));
document.addEventListener('change', (e) => eventos.push(['change', e.target.id, e.target.value]));
</script>
<script>__JS__</script>"""

VISTO = "(id) => Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').get.call(document.getElementById(id))"


@pytest.fixture(scope="module")
def pagina():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as error:   # sin Chromium instalado (py -3.14 -m playwright install chromium)
            pytest.skip(f"no se pudo abrir Chromium: {error}")
        pag = nav.new_page()
        errores = []
        pag.on("pageerror", lambda e: errores.append(str(e)))
        pag.set_content(PAGINA.replace("__JS__", NUMEROS.read_text(encoding="utf-8")))
        pag.errores = errores
        yield pag
        nav.close()


def _escribir(pag, id_, texto):
    pag.click("#nombre")
    pag.click("#" + id_, position={"x": 5, "y": 5})
    pag.keyboard.type(texto)
    pag.keyboard.press("Tab")
    return pag.evaluate(VISTO, id_), pag.evaluate(f"document.getElementById('{id_}').value")


def test_navegador_al_cargar_muestra_miles_y_el_codigo_lee_el_numero(pagina):
    assert pagina.evaluate("document.getElementById('ent').type") == "text"
    assert pagina.evaluate(VISTO, "ent") == "1.500"
    assert pagina.evaluate("document.getElementById('ent').value") == "1500"
    assert pagina.evaluate(VISTO, "txt") == "1.234.567"
    assert pagina.evaluate(VISTO, "oc") == "4500123456", "un N° de OC no lleva puntos"


@pytest.mark.parametrize("id_", ["cant", "ent", "txt", "oc"])
def test_navegador_un_clic_selecciona_todo(pagina, id_):
    pagina.click("#nombre")
    pagina.click("#" + id_, position={"x": 5, "y": 5})
    ini, fin, largo = pagina.evaluate(
        f"(() => {{ const el = document.getElementById('{id_}'); return [el.selectionStart, el.selectionEnd, ({VISTO})('{id_}').length]; }})()")
    assert (ini, fin) == (0, largo) and largo > 0


def test_navegador_escribir_reemplaza_el_cero_y_pone_miles(pagina):
    pagina.evaluate("eventos.length = 0")
    assert _escribir(pagina, "cant", "1234567,5") == ("1.234.567,5", "1234567.5")
    cambio = pagina.evaluate("eventos.filter((e) => e[0] === 'change').pop()")
    assert cambio == ["change", "cant", "1234567.5"]


@pytest.mark.parametrize("texto,visto,valor", [
    ("1.500.000", "1.500.000", "1500000"),   # puntos tecleados de miles
    ("2.5", "2,5", "2.5"),                   # un punto suelto es decimal
    ("12345.6", "12.345,6", "12345.6"),
])
def test_navegador_un_punto_tecleado_se_lee_como_en_el_resto_de_quempin(pagina, texto, visto, valor):
    assert _escribir(pagina, "cant", texto) == (visto, valor)


def test_navegador_las_cajas_dibujadas_despues_tambien(pagina):
    pagina.evaluate("document.getElementById('zona').innerHTML = '<input id=\"nueva\" type=\"number\" value=\"2500000.5\">'")
    assert pagina.evaluate(VISTO, "nueva") == "2.500.000,5"
    assert pagina.evaluate("document.getElementById('nueva').value") == "2500000.5"
    assert not pagina.errores
