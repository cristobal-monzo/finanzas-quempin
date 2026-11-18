# -*- coding: utf-8 -*-
"""Portal QUEMPIN partido en archivos (2026-11-18, fase B de portal/docs/plans/2026-11-18-mejoras-portal.md).

El código está en portal/js/<vista>.js: scripts clásicos sin función que los envuelva, que index.html carga en orden. Lo
de primer nivel de cada uno es común a todos: un nombre repetido en dos archivos falla al cargar el segundo
(«Identifier has already been declared») y uno que ya tiene el navegador (open, name, status...) lo tapa sin avisar.
"""
import re

import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403

# Nombres del navegador que más fácil se tapan sin querer; con Chromium se revisan además todos los de una ventana vacía.
DEL_NAVEGADOR = {"print", "open", "close", "stop", "find", "name", "status", "top", "parent", "self", "length", "origin",
                 "event", "history", "location", "document", "window", "frames", "screen", "closed", "opener", "alert",
                 "confirm", "prompt", "focus", "blur", "scroll", "fetch", "navigator", "crypto", "performance", "external",
                 "menubar", "toolbar", "statusbar", "localStorage", "sessionStorage", "indexedDB", "caches"}
DECLARACION = re.compile(r"^(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)|^(?:const|let|var|class)\s+([A-Za-z_$][\w$]*)")


def _nombres_de_primer_nivel():
    """{archivo: [nombres]}. Sin el IIFE, lo de primer nivel es justo lo que empieza en la columna 0."""
    salida = {}
    for archivo in archivos_js():
        nombres = []
        for n, linea in enumerate((PORTAL.parent / "js" / archivo).read_text(encoding="utf-8").split("\n"), 1):
            if re.match(r"^(?:const|let|var)\s", linea):
                assert re.match(r"^(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*(=|;)", linea) and not re.match(r"^[^=]*,", linea), \
                    f"{archivo}:{n}: un nombre por declaración, sin desarmar objetos: {linea[:80]}"
            m = DECLARACION.match(linea)
            if m:
                nombres.append(m.group(1) or m.group(2))
        salida[archivo] = nombres
    return salida


def test_index_carga_cada_js_una_vez_base_primero_y_arranque_al_final():
    orden = archivos_js()
    en_carpeta = sorted(p.name for p in (PORTAL.parent / "js").glob("*.js"))
    assert sorted(orden) == en_carpeta and len(orden) == len(set(orden)), "un <script> por cada archivo de js/, sin repetir"
    assert orden[0] == "base.js" and orden[-1] == "arranque.js"
    html = PORTAL.read_text(encoding="utf-8")
    # El aviso de errores escucha antes que todo; el freno del portal anidado va justo antes de los js/
    assert html.index("window.__qpnErrores") < html.index("window.stop()") < html.index('<script src="js/base.js">')
    assert "<style>" not in html, "el CSS va en portal.css"


def test_cada_js_es_un_script_clasico_en_modo_estricto():
    for archivo in archivos_js():
        texto = (PORTAL.parent / "js" / archivo).read_text(encoding="utf-8")
        sin_comentario = re.sub(r"^/\*.*?\*/\s*", "", texto, flags=re.S)
        assert sin_comentario.startswith("'use strict';\n"), archivo
        # Sin función que lo envuelva entero: hay código de primer nivel en la columna 0
        assert re.search(r"^(?:async function|function|const|let) ", sin_comentario, re.M), f"{archivo}: sin función que lo envuelva"
        assert not re.search(r"^\s*(import|export)\s", texto, re.M), f"{archivo}: no es un módulo"


def test_ningun_nombre_de_primer_nivel_se_repite_ni_tapa_uno_del_navegador():
    vistos = {}
    for archivo, nombres in _nombres_de_primer_nivel().items():
        for nombre in nombres:
            assert nombre not in vistos, f"«{nombre}» está en {vistos[nombre]} y en {archivo}"
            vistos[nombre] = archivo
    assert len(vistos) > 900
    tapados = sorted(set(vistos) & DEL_NAVEGADOR)
    assert not tapados, f"tapan nombres del navegador: {tapados}"


def test_ningun_nombre_tapa_uno_de_la_ventana_de_chromium(navegador):
    pagina = navegador.new_page()
    try:
        del_navegador = set(pagina.evaluate("""() => { const s = new Set();
            for (let o = window; o; o = Object.getPrototypeOf(o)) Object.getOwnPropertyNames(o).forEach((n) => s.add(n));
            return [...s]; }"""))
    finally:
        pagina.close()
    assert {"open", "name", "status", "fetch"} <= del_navegador
    nombres = {n for l in _nombres_de_primer_nivel().values() for n in l}
    tapados = sorted(nombres & del_navegador)
    assert not tapados, f"tapan nombres del navegador: {tapados}"


def test_el_portal_carga_sin_errores_y_su_estado_se_ve_desde_afuera(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    # Lo de cada archivo quedó a la vista de los demás y de las pruebas: el estado de la base, de la Planificación, de
    # Ejecución, y el arranque terminó (la vista activa es el Inicio)
    assert pagina.evaluate("typeof estado === 'object' && typeof planif === 'object' && typeof ej === 'object' && "
                           "typeof obs === 'object' && estado.activa") == "inicio"
    assert not errores
    pagina.context.close()


def test_el_portal_dentro_de_un_marco_vuelve_al_inicio_sin_cargar_sus_js(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Recorrido de proyectos")
    pagina.wait_for_function("() => location.hash === '#/recorrido'")
    pagina.evaluate("""() => { const f = document.createElement('iframe');
        f.id = 'anidado'; f.src = location.pathname; document.body.append(f); }""")
    pagina.wait_for_function("() => location.hash === '#/'")
    marco = next(f for f in pagina.frames if f.parent_frame and f.url.split("#")[0].endswith("/portal/"))
    # window.stop() corta la lectura: no llega el evento load, pero la página deja de estar «loading»
    marco.wait_for_function("() => document.readyState !== 'loading'")
    assert marco.evaluate("typeof estado === 'undefined' && typeof leer === 'undefined' && document.body.textContent === ''")
    assert not errores
    pagina.context.close()


def test_un_cambio_en_un_solo_js_del_portal_se_carga_sin_f5(navegador, tmp_path):
    """Al día sin F5 mira también portal.css y cada js/: publicar un cambio en uno solo recarga el Portal."""
    import functools
    import http.server
    import threading
    _sitio(tmp_path)
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Silencioso, directory=str(tmp_path)))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    ctx = navegador.new_context(viewport={"width": 1280, "height": 860})
    pagina = ctx.new_page()
    errores = []
    pagina.on("pageerror", lambda e: errores.append(str(e)))
    try:
        pagina.clock.install()
        pagina.goto(f"http://127.0.0.1:{servidor.server_address[1]}/finanzas-quempin/portal/")
        pagina.locator("#vistaInicio").wait_for()
        pagina.evaluate("window.__sinRecargar = 1")
        pagina.clock.run_for(2000)
        pagina.wait_for_function("() => ad.portal && !ad.revisando")
        vigilados = pagina.evaluate("[...ad.portal.archivos.keys()].map((u) => new URL(u).pathname)")
        assert "/finanzas-quempin/portal/portal.css" in vigilados
        assert {f"/finanzas-quempin/portal/js/{a}" for a in archivos_js()} <= set(vigilados)
        js = tmp_path / "finanzas-quempin" / "portal" / "js" / "tema.js"
        js.write_text(js.read_text(encoding="utf-8") + "\n// otra publicación\n", encoding="utf-8")
        # A la vista y recién abierto: primero avisa; diez minutos sin tocarlo, se recarga solo
        pagina.clock.fast_forward(301_000)
        _esperar_aviso(pagina, "Hay una versión nueva del Portal")
        assert pagina.evaluate("window.__sinRecargar") == 1
        pagina.clock.fast_forward(601_000)
        pagina.wait_for_function("() => window.__sinRecargar === undefined")
        pagina.locator("#vistaInicio").wait_for(state="attached")
        assert not errores
    finally:
        ctx.close()
        servidor.shutdown()
