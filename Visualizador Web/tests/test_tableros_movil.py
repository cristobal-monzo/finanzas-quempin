# -*- coding: utf-8 -*-
"""Todo tablero publicado tiene que poder revisarse en un telefono.

Hasta el 2026-09-24, cuatro de los seis tableros (Centro de Costos y
Cotizador, Chile y Peru) y el indice no declaraban <meta name="viewport">.
Sin esa etiqueta el telefono dibuja la pagina a ~980 px de ancho y la
achica: las reglas @media de movil que Centro de Costos y Cotizador ya
tenian escritas nunca se activaban en un telefono real. Tampoco declaraban
DOCTYPE, asi que corrian en modo quirks. Nada de eso se ve abriendo el
tablero en un escritorio, que es donde se revisaban.

Analisis Financiero ya lo habia corregido para si mismo el 2026-09-21
(test_template_declara_doctype_charset_y_viewport); este test lo extiende a
todas las plantillas, incluidas las de modulos que se agreguen despues.
"""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _plantillas():
    candidatas = (
        list(RAIZ.glob("*/Visualizador Web/template.html"))
        + list(RAIZ.glob("Peru/*/Visualizador Web/template.html"))
        + [RAIZ / "Visualizador Web" / "index.html"]
    )
    return sorted(p for p in candidatas
                  if p.exists() and not any(parte.startswith(".") for parte in p.relative_to(RAIZ).parts))


PLANTILLAS = _plantillas()


def _id(ruta):
    return str(ruta.relative_to(RAIZ).parent.parent if ruta.name == "template.html" else ruta.relative_to(RAIZ))


def test_se_encuentran_todas_las_plantillas():
    # Si el glob deja de encontrarlas (carpeta renombrada), los tests de
    # abajo pasarian sin revisar nada.
    assert len(PLANTILLAS) >= 6, [str(p) for p in PLANTILLAS]


@pytest.mark.parametrize("ruta", PLANTILLAS, ids=_id)
def test_declara_doctype_charset_y_viewport(ruta):
    html = ruta.read_text(encoding="utf-8")
    assert html.lstrip().lower().startswith("<!doctype html>"), "sin DOCTYPE corre en modo quirks"
    assert '<meta charset="utf-8">' in html.lower()
    viewport = re.search(r'<meta\s+name="viewport"\s+content="([^"]*)"', html)
    assert viewport, "sin viewport un telefono lo dibuja a ancho de escritorio"
    assert "width=device-width" in viewport.group(1)


@pytest.mark.parametrize("ruta", PLANTILLAS, ids=_id)
def test_no_bloquea_el_zoom(ruta):
    # Pellizcar para ampliar es la unica salida cuando una cifra o un grafico
    # queda chico; bloquearlo es una falla de accesibilidad (WCAG 1.4.4).
    viewport = re.search(r'<meta\s+name="viewport"\s+content="([^"]*)"', ruta.read_text(encoding="utf-8"))
    contenido = viewport.group(1).replace(" ", "") if viewport else ""
    assert "user-scalable=no" not in contenido and "maximum-scale=1" not in contenido


@pytest.mark.parametrize("ruta", PLANTILLAS, ids=_id)
def test_tiene_reglas_para_pantalla_angosta(ruta):
    html = ruta.read_text(encoding="utf-8")
    assert re.search(r"@media\s*\(max-width:\s*\d+px\)", html), "sin ninguna regla @media para telefono"
