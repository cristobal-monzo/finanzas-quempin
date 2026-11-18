# -*- coding: utf-8 -*-
"""Portal QUEMPIN: «Qué buscamos» del tablero de Oportunidades.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ── «Qué buscamos» del tablero de Oportunidades (2026-11-16) ─────────────────


def test_que_buscamos_del_tablero_de_oportunidades_llega_al_buzon(navegador, sitio):
    """El tablero de Oportunidades no tiene la carpeta del equipo: manda «Qué buscamos» al Portal, que deja un
    «ajustes-oportunidades» en el buzón (lo aplica oportunidades.py) y le contesta al tablero."""
    esquemas = _cargar("esquemas_para_test_portal", RAIZ / "Sistema Intercambio" / "esquemas.py")
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="NB")
    _menu(pagina, "Oportunidades")
    marco = _marco(pagina, "oportunidades", "op")
    ajustes = {"temas": {"climatizacion": {"interes": "no", "frases": ["climatización"]}}, "regiones": {"arica": 0},
               "monto": {"minimo": 2000000, "minimoCompraAgil": 300000, "maximo": None}}
    r = marco.evaluate(JS_GUARDAR_DESDE_EL_TABLERO, ajustes)
    assert r["ok"] and r["id"] and r["enviado"]
    [msg] = pagina.evaluate(JS_AJUSTES_EN_EL_BUZON)
    assert msg["id"] == r["id"] and msg["ajustes"] == ajustes and msg["origen"]["usuario"] == "NB"
    assert (msg["tipo"], msg["destino"]) == ("ajustes-oportunidades", "oportunidades")
    assert esquemas.validar_mensaje(msg) == []
    _esperar_aviso(pagina, "«Qué buscamos» guardado")
    # Desde la ventana del Portal (no desde una pestaña suya) no se atiende.
    pagina.evaluate("(a) => window.postMessage({ tipo: 'quempin-ajustes-oportunidades', pedido: 'x', ajustes: a }, location.origin)", ajustes)
    pagina.wait_for_timeout(400)
    assert len(pagina.evaluate(JS_AJUSTES_EN_EL_BUZON)) == 1
    assert not errores
    pagina.context.close()


def test_que_buscamos_sin_la_carpeta_dice_que_no_se_guardo(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Oportunidades")
    marco = _marco(pagina, "oportunidades", "op")
    r = marco.evaluate(JS_GUARDAR_DESDE_EL_TABLERO, {"regiones": {"arica": 0}})
    assert r["ok"] is False and "carpeta" in r["error"]
    assert not errores
    pagina.context.close()
