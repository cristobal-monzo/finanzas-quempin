# -*- coding: utf-8 -*-
"""Guardas de accesibilidad del Portal (revisión 2026-11-18/19, ver Documentación/Planes y análisis/
2026-11-18-loop-revision-portal.md). Se midió con axe-core y recorriendo con Tab; estas pruebas, sin navegador, cuidan
que no vuelvan los patrones que se corrigieron."""
import re

from portal_comun import *  # noqa: F401,F403

CSS = (VISUALIZADOR / "portal" / "portal.css").read_text(encoding="utf-8")
JS_DIR = VISUALIZADOR / "portal" / "js"

# Quitan el contorno a propósito porque marcan el foco de otra forma (y se revisó que se vea):
#   .ctx-item: el menú del clic derecho pinta el fondo; .ej-mapa .punto: el punto crece y cambia de borde.
FOCO_PROPIO = (".ctx-item", ".ej-mapa .punto")


def _reglas(css):
    sin_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", sin_comentarios):
        yield m.group(1).strip(), m.group(2)


def test_el_foco_del_teclado_no_se_esconde():
    """Un control que quita el contorno al recibir el foco se ve igual que con el ratón encima (2026-11-19: tres así)."""
    malos = []
    for selector, cuerpo in _reglas(CSS):
        if not re.search(r"outline\s*:\s*(none|0)\b", cuerpo):
            continue
        for s in selector.split(","):
            s = s.strip()
            if ":focus" in s and not s.startswith(FOCO_PROPIO):
                malos.append(s)
    assert not malos, f"quitan el contorno del foco: {malos}"


def test_las_vistas_no_usan_aside_dentro_de_main():
    """Un <aside> dentro de <main> es un landmark mal anidado para los lectores de pantalla (axe, 2026-11-18): section."""
    index = (VISUALIZADOR / "portal" / "index.html").read_text(encoding="utf-8")
    assert "<aside" not in index
    con_aside = [p.name for p in JS_DIR.glob("*.js") if re.search(r"crear\(\s*['\"]aside['\"]", p.read_text(encoding="utf-8"))]
    assert not con_aside, con_aside
