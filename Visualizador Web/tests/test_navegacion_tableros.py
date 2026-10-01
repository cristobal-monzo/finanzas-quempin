# -*- coding: utf-8 -*-
"""La navegacion entre tableros es la misma en las 5 plantillas.

Desde el 2026-10-01 la cabecera de cada tablero lleva un selector de pais
(Chile / Peru) y solo las 3 pestanas de los modulos; antes eran 6 pestanas,
una por modulo y pais. El HTML y el JavaScript de esa navegacion estan
copiados en cada template (cada tablero es un archivo autocontenido), asi
que estos tests cuidan que las copias no diverjan: lo unico propio de cada
tablero es data-nav-activo, la subruta publicada de la que el JS saca el
pais del selector, los enlaces y la pestana activa.
"""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

# Plantilla -> valor de data-nav-activo. Analisis Financiero usa una sola
# plantilla para los dos paises: su build reemplaza el marcador.
PLANTILLAS = {
    "Centro de Costos/Visualizador Web/template.html": "centro-de-costos",
    "Peru/Centro de Costos/Visualizador Web/template.html": "centro-de-costos-peru",
    "Sistema Analisis Financiero/Visualizador Web/template.html": "__AF_NAV_ACTIVO__",
    "Cotizador Historico/Visualizador Web/template.html": "cotizador-historico",
    "Peru/Cotizador Historico/Visualizador Web/template.html": "cotizador-historico-peru",
}
MODULOS = ["centro-de-costos", "analisis-financiero", "cotizador-historico"]


def _leer(rel):
    ruta = RAIZ / rel
    if not ruta.exists():
        pytest.skip(f"no esta {rel}")
    return ruta.read_text(encoding="utf-8")


def _nav(html):
    bloques = re.findall(r'<nav class="viz-modnav".*?</nav>', html, re.S)
    assert len(bloques) == 1, "tiene que haber exactamente una barra de navegacion entre tableros"
    return bloques[0]


def _js_nav(html):
    ini = html.index("// ---------- navegación entre tableros: país + pestaña activa")
    return html[ini:html.index("})();", ini)]


def test_cada_plantilla_declara_su_subruta():
    for rel, activo in PLANTILLAS.items():
        assert f'data-nav-activo="{activo}"' in _nav(_leer(rel)), rel


def test_el_html_de_la_navegacion_es_igual_en_todas():
    navs = {rel: re.sub(r'data-nav-activo="[^"]*"', "", _nav(_leer(rel))) for rel in PLANTILLAS}
    referencia = navs["Centro de Costos/Visualizador Web/template.html"]
    distintas = [rel for rel, nav in navs.items() if nav != referencia]
    assert not distintas, f"la navegacion cambio solo en: {distintas}"


def test_el_js_de_la_navegacion_es_igual_en_todas():
    bloques = {rel: _js_nav(_leer(rel)) for rel in PLANTILLAS}
    referencia = bloques["Centro de Costos/Visualizador Web/template.html"]
    distintas = [rel for rel, js in bloques.items() if js != referencia]
    assert not distintas, f"el JS de la navegacion cambio solo en: {distintas}"


def test_tres_pestanas_y_un_selector_de_pais():
    nav = _nav(_leer("Centro de Costos/Visualizador Web/template.html"))
    assert re.findall(r'data-modulo="([^"]+)"', nav) == MODULOS
    selector = re.search(r'<select[^>]*id="modNavPais"[^>]*>(.*?)</select>', nav, re.S)
    assert selector, "falta el selector de pais"
    # value = sufijo de la subruta: "" es Chile, "-peru" es Peru.
    assert re.findall(r'<option value="([^"]*)"', selector.group(1)) == ["", "-peru"]
    assert "aria-label" in selector.group(0), "el selector necesita un nombre accesible"
