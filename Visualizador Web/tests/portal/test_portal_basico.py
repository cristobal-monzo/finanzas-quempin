# -*- coding: utf-8 -*-
"""Portal QUEMPIN: el portal en el navegador: menú, pestañas y marcos, buscador, usuario, teléfono y al día sin F5.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- El portal en el navegador, sobre un sitio de mentira ---------------------------------------


def test_inicio_muestra_todas_las_herramientas_por_grupo(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    grupos = pagina.locator("#menu .grupo-cab").all_inner_texts()
    assert [g.strip() for g in grupos] == ["Captar y ofertar", "Ejecutar proyectos", "Control financiero",
                                           "Calculadora", "Ayuda"]
    assert pagina.locator("#iniAreas .ini-area h2").all_text_contents() == ["Ofertar", "Ejecutar", "Controlar", "Calcular"]
    reg = _registro()
    esperadas = [h["id"] for h in reg["herramientas"] if h["grupo"] in {"ofertar", "ejecutar", "controlar", "calcular"}]
    assert pagina.evaluate("[...document.querySelectorAll('#iniAreas .ini-item')].map(b => b.dataset.herr)") == esperadas
    # Lo que se abre fuera del portal (Excel, Sistema QUEMPIN) lleva la flecha ↗; las vistas del portal, no
    fuera = [h["id"] for h in reg["herramientas"] if h["id"] in esperadas and h["tipo"] not in ("marco", "vista")]
    assert fuera == ["cotizacion", "orden-compra"]
    assert pagina.locator("#iniAreas .ini-item:has(.ini-fuera)").count() == len(fuera)
    assert _pestanas(pagina) == ["Inicio"]
    assert pagina.locator("iframe").count() == 0
    # Una herramienta del Inicio se abre en su pestaña
    pagina.locator('.ini-item[data-herr="flujo-caja"]').click()
    _marco(pagina, "flujo-caja", "fc")
    assert _pestanas(pagina) == ["Inicio", "Flujo de Caja"]
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho, alto", [(1366, 657), (1536, 730), (1280, 600), (1024, 640)])
def test_el_inicio_y_el_menu_caben_sin_barras(navegador, sitio, ancho, alto):
    """Pedido del 2026-10-16: el Inicio con todas las herramientas sin desplazarse, y ninguna barra vertical."""
    pagina, errores = _abrir_portal(navegador, sitio, ancho=ancho, alto=alto)
    assert pagina.evaluate(JS_BARRAS) == []
    # Las cuatro áreas, de a dos (2026-11-10)
    columnas = "getComputedStyle(document.getElementById('iniAreas')).gridTemplateColumns.split(' ').length"
    assert pagina.evaluate(columnas) == 2
    assert pagina.evaluate("getComputedStyle(document.querySelector('.menu-lista')).scrollbarWidth") == "none"
    # El menú (☰), con su grupo más largo desplegado, tampoco desborda; va encima y no achica el Inicio
    _menu(pagina, "Seguimiento")
    pagina.locator("#pestanas .ir", has_text="Inicio").click()
    pagina.locator("#btnMenu").click()
    assert pagina.locator('#menu .grupo-cab[aria-expanded="true"]').inner_text().strip() == "Captar y ofertar"
    assert pagina.evaluate(JS_BARRAS) == []
    assert pagina.evaluate(columnas) == 2
    assert not errores
    pagina.context.close()


def test_el_menu_despliega_un_grupo_a_la_vez(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.locator("#btnMenu").click()          # el menú con nombres
    abiertos = lambda: pagina.locator('#menu .grupo-cab[aria-expanded="true"]').all_inner_texts()
    assert [g.strip() for g in abiertos()] == ["Captar y ofertar"]
    pagina.locator("#grupo-ejecutar").click()
    assert [g.strip() for g in abiertos()] == ["Ejecutar proyectos"]
    assert pagina.locator("#items-ofertar").is_hidden()
    pagina.locator("#grupo-ejecutar").click()
    assert abiertos() == []
    # Abrir una herramienta (aquí desde el Inicio) despliega su grupo
    pagina.keyboard.press("Escape")
    pagina.locator('.ini-item[data-herr="gas"]').click()
    _marco(pagina, "calculadora", "gas")
    pagina.locator("#btnMenu").click()
    assert [g.strip() for g in abiertos()] == ["Calculadora"]
    assert not errores
    pagina.context.close()


def test_las_pestanas_se_encogen_en_vez_de_desplazarse(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio, ancho=1366, alto=657)
    ids = ["oportunidades", "formulador", "cotizador", "centro-costos", "analisis", "flujo-caja",
           "diametro", "hidrogeno", "gas", "otros-gases"]
    for herr in ids:
        pagina.locator("#pestanas .ir", has_text="Inicio").click()
        pagina.locator(f'.ini-item[data-herr="{herr}"]').click()
    _marco(pagina, "calculadora", "otros")
    # Las cuatro calculadoras comparten una pestaña: muestra la última elegida
    assert _pestanas(pagina) == ["Inicio", "Oportunidades", "Formulador", "Cotizador", "Centro de Costos", "Análisis",
                                 "Flujo de Caja", "Otros gases"]
    assert pagina.evaluate(JS_BARRAS) == []
    # El nombre completo queda a mano en el title
    assert pagina.locator("#pestanas .ir", has_text="Análisis").get_attribute("title") == "Análisis Financiero"
    assert not errores
    pagina.context.close()


def test_las_pestanas_se_mueven_y_el_orden_queda(navegador, sitio):
    """Pedido del usuario (2026-11-18): dejar primero las herramientas que más usa."""
    pagina, errores = _abrir_portal(navegador, sitio)
    for herr in ["oportunidades", "formulador", "centro-costos"]:
        pagina.locator("#pestanas .ir", has_text="Inicio").click()
        pagina.locator(f'.ini-item[data-herr="{herr}"]').click()
    assert _pestanas(pagina) == ["Inicio", "Oportunidades", "Formulador", "Centro de Costos"]
    activa = pagina.evaluate("estado.activa")

    # Arrastrar Centro de Costos hasta antes de Oportunidades; soltar no cambia la pestaña activa
    def caja(nombre):
        return pagina.locator(".pestana", has=pagina.locator(".ir", has_text=nombre)).bounding_box()
    cc, op = caja("Centro de Costos"), caja("Oportunidades")
    pagina.mouse.move(cc["x"] + 20, cc["y"] + cc["height"] / 2)
    pagina.mouse.down()
    pagina.mouse.move(op["x"] + 10, op["y"] + op["height"] / 2, steps=8)
    pagina.mouse.up()
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos", "Oportunidades", "Formulador"]
    assert pagina.evaluate("estado.activa") == activa

    # Arrastrar hasta la casita no pasa delante de Inicio
    fo, ini = caja("Formulador"), pagina.locator(".pestana.solo").bounding_box()
    pagina.mouse.move(fo["x"] + 20, fo["y"] + fo["height"] / 2)
    pagina.mouse.down()
    pagina.mouse.move(ini["x"] + 2, ini["y"] + ini["height"] / 2, steps=8)
    pagina.mouse.up()
    assert _pestanas(pagina) == ["Inicio", "Formulador", "Centro de Costos", "Oportunidades"]

    # Con el teclado: Ctrl+Shift+→ la corre un lugar y deja el foco en ella
    pagina.locator("#pestanas .ir", has_text="Formulador").focus()
    pagina.keyboard.press("Control+Shift+ArrowRight")
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos", "Formulador", "Oportunidades"]
    assert pagina.evaluate("document.activeElement.textContent") == "Formulador"

    # Un clic corto sigue activando la pestaña
    pagina.locator("#pestanas .ir", has_text="Oportunidades").click()
    assert pagina.evaluate("estado.activa") == "oportunidades"

    # El orden vuelve al abrir el portal otra vez
    pagina.reload()
    pagina.wait_for_function("document.querySelectorAll('#pestanas .ir').length === 4")
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos", "Formulador", "Oportunidades"]
    assert not errores
    pagina.context.close()


def test_una_herramienta_se_abre_dentro_del_portal(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    marco = _marco(pagina, "centro-costos", "cc")
    assert marco.url.endswith("/finanzas-quempin/centro-de-costos/")
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos"]
    assert pagina.url.endswith("#/centro-costos")
    assert pagina.locator('#menu .menu-item[aria-current="page"]').inner_text().strip() == "Centro de Costos"
    assert pagina.locator("#vistaInicio").is_hidden()
    # Volver al inicio no descarga la herramienta
    pagina.locator("#pestanas .ir", has_text="Inicio").click()
    assert pagina.locator("#vistaInicio").is_visible()
    assert pagina.locator("#marco-centro-costos").count() == 1
    assert not errores
    pagina.context.close()


def test_un_enlace_a_otra_herramienta_abre_su_pestana_en_el_portal(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    cc = _marco(pagina, "centro-costos", "cc")
    cc.click("#aAF")
    af = _marco(pagina, "analisis", "af")
    _esperar(pagina, "analisis", "hash", "#proyecto=DEMO")
    assert cc.evaluate("document.body.dataset.herr") == "cc", "el Centro de Costos sigue en su pestaña"
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos", "Análisis"]
    # Un enlace con target=_blank y un window.open también quedan en el portal, sin ventanas nuevas.
    pagina.locator("#pestanas .ir", has_text="Centro de Costos").click()
    cc.click("#aForm")
    _marco(pagina, "formulador", "formulador")
    pagina.locator("#pestanas .ir", has_text="Análisis").click()
    af.click("#bOpen")
    _esperar(pagina, "formulador", "hash", "#/req/7")
    assert len(pagina.context.pages) == 1
    assert _pestanas(pagina).count("Formulador") == 1
    # El window.open('') de los reportes PDF no se toca: abre su ventana como siempre.
    pagina.locator("#pestanas .ir", has_text="Análisis").click()
    with pagina.context.expect_page():
        af.click("#bReporte")
    assert af.evaluate("document.body.dataset.reporte") == "abierta"
    assert not errores
    pagina.context.close()


def test_los_enlaces_dentro_de_la_misma_herramienta_o_a_otra_pagina_navegan_normal(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    cc = _marco(pagina, "centro-costos", "cc")
    cc.click("#aMismo")
    _esperar(pagina, "centro-costos", "hash", "#tag=OTRO")
    # Un enlace al portal mismo no lo anida: vuelve al inicio, y la herramienta sigue donde estaba.
    cc.click("#aPortal")
    pagina.locator("#vistaInicio").wait_for(state="visible")
    assert cc.evaluate("document.body.dataset.herr") == "cc"
    # Una página que no es de ninguna herramienta se abre ahí mismo, como siempre.
    pagina.locator("#pestanas .ir", has_text="Centro de Costos").click()
    cc.click("#aOtra")
    _marco(pagina, "centro-costos", "otra")
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos"]
    assert not errores
    pagina.context.close()


def test_el_buscador_lleva_a_la_pestana_de_una_calculadora(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.locator("#buscar").fill("quemador")
    primero = pagina.locator("#resultados .res").first
    assert primero.locator(".res-tit").inner_text() == "Gas natural / GLP › Quemador atmosférico"
    pagina.keyboard.press("Enter")
    gas = _marco(pagina, "calculadora", "gas")
    _esperar(pagina, "calculadora", "tab", "quemador")
    # Otra pestaña de la misma calculadora: se cambia ahí mismo, sin recargar ni abrir otra.
    pagina.locator("#buscar").fill("combustion")
    pagina.keyboard.press("Enter")
    _esperar(pagina, "calculadora", "tab", "combustion")
    assert gas.evaluate("document.body.dataset.cargas") == "1"
    assert _pestanas(pagina) == ["Inicio", "Gas / GLP"]
    # Volver a elegirla en el menú no la mueve de donde quedó.
    _menu(pagina, "Gas natural / GLP")
    pagina.wait_for_timeout(200)
    assert gas.evaluate("document.body.dataset.tab") == "combustion"
    # Buscar una pestaña de otra calculadora la abre directo en ella.
    pagina.locator("#buscar").fill("memoria hidrogeno")
    pagina.keyboard.press("Enter")
    h2 = _marco(pagina, "calculadora", "hidrogeno")
    _esperar(pagina, "calculadora", "tab", "memoria")
    assert _pestanas(pagina) == ["Inicio", "Hidrógeno"], "otra calculadora va en la misma pestaña"
    # Búsquedas por necesidad
    for consulta, esperado in (("factura", "Centro de Costos"), ("orden de compra", "Orden de compra"),
                               ("caneria", "Diámetro de tubería"), ("licitaciones", "Oportunidades")):
        pagina.locator("#buscar").fill(consulta)
        assert esperado in pagina.locator("#resultados .res-tit").all_inner_texts(), consulta
    pagina.locator("#buscar").fill("zzz sin nada")
    assert "Nada calza" in pagina.locator("#resultados").inner_text()
    pagina.keyboard.press("Escape")
    assert pagina.locator("#resultados").is_hidden()
    assert not errores
    pagina.context.close()


def test_la_calculadora_que_cambia_sola_mueve_su_pestana(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Hidrógeno")
    h2 = _marco(pagina, "calculadora", "hidrogeno")
    h2.select_option("#selector-gas", "../OtrosGases/")
    _marco(pagina, "calculadora", "otros")
    assert _pestanas(pagina) == ["Inicio", "Otros gases"]
    assert pagina.locator('#menu .menu-item[aria-current="page"]').inner_text().strip() == "Otros gases"
    assert not errores
    pagina.context.close()


def test_sin_selector_de_proyecto_cada_herramienta_abre_su_vista_general(navegador, sitio):
    """2026-11-06, pedido del usuario: el selector de proyecto de la cabecera «no aporta» y se quitó."""
    pagina, errores = _abrir_portal(navegador, sitio, proyectos=True)
    assert pagina.locator("#btnProyecto").count() == 0 and pagina.locator("#btnCarpeta").count() == 0
    # Lo que quedó guardado del selector de antes ya no manda
    pagina.evaluate("localStorage.setItem('quempin_portal_proyecto', JSON.stringify('QMPN-2026-001'))")
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    assert pagina.evaluate("localStorage.getItem('quempin_portal_proyecto')") is None
    _menu(pagina, "Carta Gantt")
    _marco(pagina, "gantt", "gantt")
    _esperar(pagina, "gantt", "hash", "#/")
    _menu(pagina, "Formulador")
    formulador = _marco(pagina, "formulador", "formulador")
    _esperar(pagina, "formulador", "hash", "#/")
    assert _pestanas(pagina) == ["Inicio", "Carta Gantt", "Formulador"]
    _menu(pagina, "Centro de Costos")
    _marco(pagina, "centro-costos", "cc")
    _esperar(pagina, "centro-costos", "hash", "")
    # Buscar por N° de requerimiento abre el seguimiento de ese proyecto
    pagina.locator("#buscar").fill("7")
    assert pagina.locator("#resultados .res-tit").first.inner_text() == "QMPN-2026-001 · Obra de prueba"
    pagina.keyboard.press("Enter")
    _esperar(pagina, "formulador", "hash", "#/p/u2/seguimiento")
    # Un proyecto nuevo guardado por el Formulador aparece en el buscador sin recargar el portal
    formulador.evaluate("""k => {
        const d = JSON.parse(localStorage.getItem(k));
        d.proyectos.push({uid: 'u5', codigo: 'QMPN-2026-004', version: 1, titulo: 'Nuevo', estado: 'Borrador', modificado: '2026-10-05T10:00:00Z'});
        localStorage.setItem(k, JSON.stringify(d));
    }""", LS_PROYECTOS)
    pagina.locator("#buscar").fill("QMPN-2026-004")
    pagina.locator("#resultados .res-tit", has_text="QMPN-2026-004").wait_for()
    assert not errores
    pagina.context.close()


def test_ingresar_datos_vive_dentro_del_analisis(navegador, sitio):
    """Pedido del 2026-11-18: «Ingresar avance» no tiene acceso propio en el Inicio ni en el menú; se llega por la
    pestaña «Ingresar datos» del Análisis Financiero, que sigue siendo una sola pestaña del portal."""
    pagina, errores = _abrir_portal(navegador, sitio)
    assert pagina.locator('.ini-item[data-herr="ingresar"]').count() == 0
    pagina.locator("#btnMenu").click()
    assert pagina.locator('#menu .menu-item[data-herr="ingresar"]').count() == 0
    _menu(pagina, "Análisis Financiero")
    af = _marco(pagina, "analisis", "af")
    af.locator("#tabBtnIngreso").click()
    _esperar(pagina, "analisis", "tab", "tabIngreso")
    assert _pestanas(pagina) == ["Inicio", "Análisis"]
    assert af.evaluate("document.body.dataset.cargas") == "1"
    assert not errores
    pagina.context.close()


def test_el_seguimiento_abre_la_lista_del_formulador(navegador, sitio):
    """Sin selector de proyecto (2026-11-06), «Seguimiento» abre la lista del Formulador, donde se elige el proyecto."""
    pagina, errores = _abrir_portal(navegador, sitio, proyectos=True)
    _menu(pagina, "Seguimiento")
    _marco(pagina, "formulador", "formulador")
    _esperar(pagina, "formulador", "hash", "#/")
    assert _pestanas(pagina) == ["Inicio", "Seguimiento"]
    assert not errores
    pagina.context.close()


def test_la_direccion_de_una_herramienta_abre_esa_y_no_su_pareja(navegador, sitio):
    """…/portal/#/ingresar con la pestaña del Análisis Financiero de la visita anterior dejaba el Resumen con
    el nombre «Ingresar avance» (2026-10-25): las dos son la misma página y la pestaña del tablero dice cuál."""
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Análisis Financiero")
    _marco(pagina, "analisis", "af")
    pagina.goto(sitio + "/finanzas-quempin/portal/?otra-visita#/ingresar")
    pagina.locator("#vistaInicio").wait_for(state="attached")
    _marco(pagina, "analisis", "af")
    _esperar(pagina, "analisis", "tab", "tabIngreso")
    assert _pestanas(pagina) == ["Inicio", "Ingresar avance"]
    # La misma herramienta que ya estaba se queda donde la persona la dejó
    pagina.goto(sitio + "/finanzas-quempin/portal/?tercera#/ingresar")
    pagina.locator("#vistaInicio").wait_for(state="attached")
    _marco(pagina, "analisis", "af")
    assert _pestanas(pagina) == ["Inicio", "Ingresar avance"]
    assert not errores
    pagina.context.close()


def test_la_contrasena_escrita_en_una_herramienta_abre_las_demas(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio, clave=False)
    _menu(pagina, "Centro de Costos")
    cc = _marco(pagina, "centro-costos", "cc")
    assert cc.locator("#pwGate").is_visible()
    _menu(pagina, "Análisis Financiero")
    af = _marco(pagina, "analisis", "af")
    af.click("#entrar")
    _esperar(pagina, "centro-costos", "cargas", "2")
    cc = _marco(pagina, "centro-costos", "cc")
    assert cc.locator("#pwGate").is_hidden()
    assert not errores
    pagina.context.close()


def test_excel_y_programa_no_se_abren_dentro(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    # La Planilla de Ingreso es una vista del portal desde el 2026-10-29; su Excel de respaldo se abre aparte, desde Conexiones
    _menu(pagina, "Requerimientos")
    assert pagina.evaluate("window.__abiertas") == []
    assert pagina.locator("#vistaPlanilla").is_visible() and pagina.locator("iframe").count() == 0
    _menu(pagina, "Configuración y conexiones")
    pagina.locator("#cx-planilla .cx-enlace", has_text="Abrir en Excel para la web").click()
    abiertas = pagina.evaluate("window.__abiertas")
    assert len(abiertas) == 1 and abiertas[0].startswith("https://quempinspa2020.sharepoint.com/")
    for nombre in ("Conexiones", "Requerimientos"):
        pagina.locator("#pestanas .pestana", has_text=nombre).locator(".x").click()
    # Cotizar y comprar abre QUEMPIN.exe en su sección con quempin:// (Sistema QUEMPIN 1.3.8)
    _menu(pagina, "Emitir cotización")
    pagina.locator('.ini-item[data-herr="orden-compra"]').click()
    assert pagina.evaluate("window.__lanzados") == ["quempin://cotizacion", "quempin://orden-compra"]
    assert "Abriendo Sistema QUEMPIN" in pagina.locator("#aviso").inner_text()
    assert pagina.locator("#dlgInfo").is_hidden()
    # Si no se abrió, el aviso explica cómo dejarlo listo en ese computador
    pagina.locator("#aviso button", has_text="¿No se abrió?").click()
    assert pagina.locator("#dlgInfo").is_visible()
    assert "QUEMPIN.exe" in pagina.locator("#dlgInfo").inner_text()
    pagina.locator("#dlgInfo button", has_text="Entendido").click()
    _menu(pagina, "Cómo usar el portal")
    assert pagina.locator("#dlgAyuda").is_visible()
    assert _pestanas(pagina) == ["Inicio"]
    assert not errores
    pagina.context.close()


def test_el_pais_elige_el_tablero_de_peru(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    assert pagina.locator("#pais").is_hidden(), "en el Inicio no hay país que elegir"
    _menu(pagina, "Cotizador Histórico")
    _marco(pagina, "cotizador", "cot")
    pagina.select_option("#pais", "pe")
    assert _marco(pagina, "cotizador", "cotpe").url.endswith("/cotizador-historico-peru/")
    _menu(pagina, "Flujo de Caja")
    assert _marco(pagina, "flujo-caja", "fc").url.endswith("/flujo-de-caja/")        # solo existe en Chile
    assert pagina.locator("#pais").is_hidden()
    # De vuelta a Chile desde el Cotizador, que se cambia solo
    pagina.locator("#pestanas .ir", has_text="Cotizador").click()
    assert pagina.locator("#pais").input_value() == "pe"
    pagina.select_option("#pais", "cl")
    _marco(pagina, "cotizador", "cot")
    assert not errores
    pagina.context.close()


def test_las_pestanas_vuelven_al_recargar_y_solo_carga_la_activa(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    _marco(pagina, "centro-costos", "cc")
    pagina.locator("#buscar").fill("memoria hidrogeno")
    pagina.keyboard.press("Enter")
    _marco(pagina, "calculadora", "hidrogeno")
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for(state="attached")
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos", "Hidrógeno"]
    h2 = _marco(pagina, "calculadora", "hidrogeno")
    _esperar(pagina, "calculadora", "tab", "memoria")
    assert pagina.locator("#marco-centro-costos").count() == 0
    pagina.locator("#pestanas .ir", has_text="Centro de Costos").click()
    _marco(pagina, "centro-costos", "cc")
    # Cerrar una pestaña la descarga y deja activa la vecina
    pagina.locator("#pestanas .pestana", has_text="Centro de Costos").locator(".x").click()
    assert _pestanas(pagina) == ["Inicio", "Hidrógeno"]
    pagina.wait_for_function("() => !document.getElementById('marco-centro-costos')")
    assert pagina.locator("#pestanas .pestana.activa").inner_text().strip() == "Hidrógeno"
    assert not errores
    pagina.context.close()


def test_lo_publicado_de_nuevo_se_carga_sin_f5(navegador, tmp_path):
    """Al día sin F5 (2026-11-18): una herramienta escondida que cambió en el sitio se recarga al tiro; la que se ve,
    tras 10 minutos sin tocarla (antes, un aviso con «Actualizar»); el Portal también. Con el reloj de Playwright."""
    _sitio(tmp_path)
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Silencioso, directory=str(tmp_path)))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    sitio = f"http://127.0.0.1:{servidor.server_address[1]}"
    ctx = navegador.new_context(viewport={"width": 1280, "height": 860})
    ctx.add_init_script("if (window === window.top && !localStorage.getItem('quempin_viz_clave')) localStorage.setItem('quempin_viz_clave', 'clave-de-mentira');")
    pagina = ctx.new_page()
    errores = []
    pagina.on("pageerror", lambda e: errores.append(str(e)))
    try:
        pagina.clock.install()
        pagina.goto(sitio + "/finanzas-quempin/portal/")
        pagina.locator("#vistaInicio").wait_for()
        _menu(pagina, "Centro de Costos")
        _marco(pagina, "centro-costos", "cc")
        _menu(pagina, "Flujo de Caja")
        _marco(pagina, "flujo-caja", "fc")
        pagina.evaluate("window.__sinRecargar = 1")
        pagina.clock.run_for(2000)
        # Las bases se leen con fetch de verdad: la del Portal y la de cada herramienta abierta
        pagina.wait_for_function("() => ad.portal && !ad.revisando && estado.pestanas.every((p) => !p.marco || p.ad)")

        def cambiar(ruta):
            f = tmp_path / ruta / "index.html"
            f.write_text(f.read_text(encoding="utf-8") + "\n<!-- otra publicación -->", encoding="utf-8")

        def cargas(familia):
            return pagina.evaluate(f"document.getElementById('marco-{familia}').contentDocument?.body?.dataset.cargas")

        # La escondida (Centro de Costos) se recarga en la próxima revisión; la que se ve (Flujo de Caja), recién tocada, avisa
        cambiar("finanzas-quempin/centro-de-costos")
        cambiar("finanzas-quempin/flujo-de-caja")
        pagina.mouse.move(400, 400)
        pagina.clock.fast_forward(301_000)
        _esperar(pagina, "centro-costos", "cargas", "2")      # tolera el instante en que el marco recargado no tiene body
        _esperar_aviso(pagina, "Hay una versión nueva de «Flujo de Caja»")
        assert cargas("flujo-caja") == "1"
        # Diez minutos sin tocarla: se recarga sola
        pagina.clock.fast_forward(601_000)
        _esperar(pagina, "flujo-caja", "cargas", "2")
        # Lo que cambió en las herramientas no recargó el Portal
        assert pagina.evaluate("window.__sinRecargar") == 1
        # El Portal nuevo, sin tocar nada: se recarga y vuelven sus pestañas
        cambiar("finanzas-quempin/portal")
        pagina.clock.fast_forward(301_000)
        pagina.wait_for_function("() => window.__sinRecargar === undefined")
        pagina.locator("#vistaInicio").wait_for(state="attached")
        assert _pestanas(pagina) == ["Inicio", "Centro de Costos", "Flujo de Caja"]
        assert not errores
    finally:
        ctx.close()
        servidor.shutdown()


def test_una_pestana_por_herramienta_y_no_mas_de_ocho_cargadas(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    nombres = ["Centro de Costos", "Análisis Financiero", "Flujo de Caja", "Cotizador Histórico",
               "Oportunidades", "Formulador", "Carta Gantt", "Seguimiento", "Diámetro de tubería", "Hidrógeno",
               "Gas natural / GLP", "Configuración y conexiones"]
    for nombre in nombres:
        _menu(pagina, nombre)
    assert len(_pestanas(pagina)) == 10                              # Inicio + 9 pestañas (la Carta Gantt, aparte desde 2026-10-20), ni una más
    pagina.locator("#pestanas .ir", has_text="Gas / GLP").click()
    _marco(pagina, "calculadora", "gas")
    pagina.wait_for_function("() => document.querySelectorAll('iframe.marco').length <= 8")
    assert not errores
    pagina.context.close()


def test_ctrl_k_desde_dentro_de_una_herramienta(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Flujo de Caja")
    fc = _marco(pagina, "flujo-caja", "fc")
    fc.click("h1")
    pagina.keyboard.press("Control+k")
    assert pagina.evaluate("document.activeElement && document.activeElement.id") == "buscar"
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [360, 390, 768])
def test_telefono_sin_desbordes_y_menu_desplegable(navegador, sitio, ancho):
    pagina, errores = _abrir_portal(navegador, sitio, ancho=ancho, alto=844, proyectos=True, movil=True)
    d = pagina.evaluate(JS_DESBORDES)
    assert d["ancho"] == ancho and d["doc"] <= ancho and not d["fuera"], d
    campos = pagina.evaluate("""() => [...document.querySelectorAll('input, select')]
        .filter(e => e.offsetParent && parseFloat(getComputedStyle(e).fontSize) < 16).map(e => e.id)""")
    assert ancho > 760 or not campos, campos
    if ancho <= 760:
        assert pagina.locator("#menu").is_hidden()
        pagina.locator("#btnMenu").click()
        assert pagina.locator("#menu").is_visible()
        _menu(pagina, "Centro de Costos")
        assert pagina.locator("#menu").is_hidden()
        _marco(pagina, "centro-costos", "cc")
        pagina.locator("#btnBuscar").click()
        assert pagina.locator("#buscar").is_visible()
        pagina.locator("#buscar").fill("diametro")
        pagina.keyboard.press("Enter")
        _marco(pagina, "calculadora", "diametro")
        assert pagina.locator("#buscar").is_hidden()
        d = pagina.evaluate(JS_DESBORDES)
        assert d["doc"] <= ancho and not d["fuera"], d
    assert not errores
    pagina.context.close()

# ---- Dentro del portal las herramientas no repiten su cabecera (2026-10-16) ----------------------


def test_dentro_del_portal_las_herramientas_no_repiten_su_cabecera(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    cc = _marco(pagina, "centro-costos", "cc")
    pagina.wait_for_function("() => document.getElementById('marco-centro-costos').contentDocument.documentElement.dataset.enPortal === 'tablero'")
    assert _estilo(cc, ".viz-header") == "none"
    # La fecha de los datos, que estaba en esa cabecera, va junto a las pestañas del portal
    pagina.wait_for_function("() => document.getElementById('datoMarco').textContent === 'Datos al 15-10-2026'")
    assert pagina.locator("#datoMarco").is_visible()
    _menu(pagina, "Hidrógeno")
    calc = _marco(pagina, "calculadora", "hidrogeno")
    pagina.wait_for_function("() => document.getElementById('marco-calculadora').contentDocument.documentElement.dataset.enPortal === 'calculadora'")
    assert _estilo(calc, ".viz-header") == "none"
    assert pagina.locator("#datoMarco").is_hidden()
    _menu(pagina, "Formulador")
    form = _marco(pagina, "formulador", "formulador")
    pagina.wait_for_function("() => document.getElementById('marco-formulador').contentDocument.documentElement.dataset.enPortal === 'formulador'")
    # Del Formulador quedan sus secciones y Configuración; no su logo, su título, su menú de herramientas ni su tema
    for oculto in (".viz-logo", ".viz-titleblock", "#herrBtn", "#themeToggle", "#usuarioBtn"):
        assert _estilo(form, oculto) == "none", oculto
    for visible in (".viz-modnav", "#config"):
        assert _estilo(form, visible) != "none", visible
    # Abiertas aparte, en su dirección de siempre, se ven como siempre
    aparte = pagina.context.new_page()
    aparte.goto(sitio + "/finanzas-quempin/centro-de-costos/")
    assert aparte.evaluate("getComputedStyle(document.querySelector('.viz-header')).display") != "none"
    aparte.close()
    assert not errores
    pagina.context.close()


def test_un_solo_modo_oscuro_para_el_portal_y_sus_herramientas(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    _marco(pagina, "centro-costos", "cc")
    oscuro = pagina.evaluate("document.documentElement.getAttribute('data-theme') === 'dark' || matchMedia('(prefers-color-scheme: dark)').matches")
    pagina.locator("#btnTema").click()
    nuevo = "light" if oscuro else "dark"
    assert pagina.evaluate("document.documentElement.getAttribute('data-theme')") == nuevo
    pagina.wait_for_function("t => document.getElementById('marco-centro-costos').contentDocument.documentElement.getAttribute('data-theme') === t", arg=nuevo)
    # Las herramientas que se abran después, y aparte, también
    claves = sorted({h["tema"] for h in _registro()["herramientas"] if h.get("tema")})
    assert pagina.evaluate("ks => ks.map(k => localStorage.getItem(k))", claves) == [nuevo] * len(claves)
    _menu(pagina, "Hidrógeno")
    _marco(pagina, "calculadora", "hidrogeno")
    pagina.wait_for_function("t => document.getElementById('marco-calculadora').contentDocument.documentElement.getAttribute('data-theme') === t", arg=nuevo)
    assert pagina.locator("#btnTema").get_attribute("aria-label") == ("Modo claro" if nuevo == "dark" else "Modo oscuro")
    assert not errores
    pagina.context.close()


def test_el_menu_solo_aparece_con_la_hamburguesa(navegador, sitio):
    """Pedido del 2026-10-16 (tarde): sin la franja de íconos a la izquierda; el menú aparece solo con ☰."""
    pagina, errores = _abrir_portal(navegador, sitio)
    izquierda = "Math.round(document.getElementById('escenario').getBoundingClientRect().left)"
    assert pagina.locator("#riel, #flotante").count() == 0
    assert pagina.locator("#menu").is_hidden() and pagina.evaluate(izquierda) == 0
    assert pagina.locator("#btnMenu").get_attribute("aria-expanded") == "false"
    # ☰ lo abre encima, sin correr la herramienta, con el foco adentro; Esc lo cierra y devuelve el foco
    pagina.locator("#btnMenu").click()
    assert pagina.locator("#menu").is_visible() and pagina.locator("#velo").is_visible()
    assert pagina.locator("#btnMenu").get_attribute("aria-expanded") == "true"
    assert pagina.evaluate(izquierda) == 0
    assert pagina.evaluate("document.getElementById('menu').contains(document.activeElement)")
    pagina.keyboard.press("Escape")
    assert pagina.locator("#menu").is_hidden()
    assert pagina.evaluate("document.activeElement && document.activeElement.id") == "btnMenu"
    # Tocar fuera también lo cierra, y ☰ otra vez lo cierra
    pagina.locator("#btnMenu").click()
    pagina.locator("#velo").click(position={"x": 900, "y": 300})
    assert pagina.locator("#menu").is_hidden()
    pagina.locator("#btnMenu").click()
    pagina.locator("#btnMenu").click()
    assert pagina.locator("#menu").is_hidden()
    # Elegir una herramienta la abre a todo el ancho y cierra el menú
    _menu(pagina, "Flujo de Caja")
    _marco(pagina, "flujo-caja", "fc")
    assert pagina.locator("#menu").is_hidden() and pagina.locator("#velo").is_hidden()
    assert pagina.evaluate(izquierda) == 0
    # Al volver a abrir, marca la herramienta activa; al recargar el menú vuelve cerrado
    pagina.locator("#btnMenu").click()
    assert pagina.locator('#menu .menu-item[aria-current="page"]').inner_text().strip() == "Flujo de Caja"
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for(state="attached")
    assert pagina.locator("#menu").is_hidden()
    assert not errores
    pagina.context.close()


def test_el_inicio_marca_las_herramientas_ya_abiertas(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.locator('.ini-item[data-herr="flujo-caja"]').click()
    _marco(pagina, "flujo-caja", "fc")
    pagina.locator("#pestanas .ir").first.click()
    assert pagina.evaluate("[...document.querySelectorAll('#iniAreas .ini-item.abierta')].map(b => b.dataset.herr)") == ["flujo-caja"]
    assert not errores
    pagina.context.close()

# ---- Usuario (2026-10-16): las iniciales del equipo, elegidas una vez por navegador -------------------


def test_las_iniciales_del_equipo_son_las_mismas_en_las_tres_herramientas():
    """El portal, el Formulador (js/usuario.js) y Sistema QUEMPIN (app/config.py) ofrecen la misma lista."""
    assert _registro()["usuarios"] == USUARIOS
    formulador = _hermano("Formulación de proyectos")
    usuario_js = formulador / "quempin-formulacion" / "js" / "usuario.js" if formulador else None
    if usuario_js and usuario_js.exists():
        texto = usuario_js.read_text(encoding="utf-8")
        assert re.findall(r"'([A-Z]{2})'", re.search(r"const LISTA = \[(.*?)\]", texto).group(1)) == USUARIOS
        assert "const CLAVE = 'quempin_usuario'" in texto
    sistema = _hermano("Sistema QUEMPIN")
    config = sistema / "app" / "config.py" if sistema else None
    if config and config.exists():
        texto = config.read_text(encoding="utf-8")
        assert re.findall(r'"([A-Z]{2})"', re.search(r"^USUARIOS = \((.*?)\)", texto, re.M).group(1)) == USUARIOS


def test_el_usuario_se_elige_una_vez_y_ordena_los_proyectos(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.evaluate("d => localStorage.setItem('qpn.formulacion.proyectos.v1', JSON.stringify(d))", _proyectos_con_responsable())
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    boton = pagina.locator("#btnUsuario")
    assert pagina.locator("#usuarioActual").inner_text() == "¿Quién eres?" and "sin" in boton.get_attribute("class")
    boton.click()
    assert pagina.locator("#listaUsuarios .usr-op").all_inner_texts() == USUARIOS
    assert pagina.locator("#sinUsuario").get_attribute("aria-selected") == "true"
    pagina.locator('#listaUsuarios .usr-op[data-usuario="LC"]').click()
    assert pagina.locator("#popUsuario").is_hidden()
    assert pagina.locator("#usuarioActual").inner_text() == "LC" and "sin" not in boton.get_attribute("class")
    # Se guarda tal cual (no JSON): así lo lee el Formulador
    assert pagina.evaluate("localStorage.getItem('quempin_usuario')") == "LC"
    assert "Trabajas como LC" in pagina.locator("#aviso").inner_text()
    # El buscador dice cuál es suyo y encuentra por iniciales
    pagina.locator("#buscar").fill("cm")
    assert "a cargo de CM" in pagina.locator("#resultados").inner_text()
    pagina.locator("#buscar").fill("")
    # Sin usuario: se guarda vacío y los proyectos van sin grupos
    boton.click()
    pagina.locator("#sinUsuario").click()
    assert pagina.evaluate("localStorage.getItem('quempin_usuario')") == ""
    assert pagina.locator("#usuarioActual").inner_text() == "¿Quién eres?"
    assert not errores
    pagina.context.close()


def test_el_usuario_elegido_en_el_formulador_vale_en_el_portal(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Formulador")
    form = _marco(pagina, "formulador", "formulador")
    # El Formulador (dentro del portal) guarda la misma clave: el portal se entera sin recargar
    form.evaluate("localStorage.setItem('quempin_usuario', 'MP')")
    pagina.wait_for_function("() => document.getElementById('usuarioActual').textContent === 'MP'")
    assert not errores
    pagina.context.close()


def test_el_portal_adopta_las_iniciales_que_el_formulador_tenia_de_antes(navegador, sitio):
    ctx = navegador.new_context(viewport={"width": 1280, "height": 860})
    ctx.add_init_script("""(() => {
        if (window !== window.top || localStorage.getItem('quempin_usuario') !== null) return;
        localStorage.setItem('quempin_viz_clave', 'clave-de-mentira');
        localStorage.setItem('qpn.formulacion.iniciales', 'es');
    })()""")
    pagina = ctx.new_page()
    pagina.goto(sitio + "/finanzas-quempin/portal/")
    pagina.locator("#vistaInicio").wait_for()
    assert pagina.locator("#usuarioActual").inner_text() == "ES"
    assert pagina.evaluate("localStorage.getItem('quempin_usuario')") == "ES"
    ctx.close()


@pytest.mark.parametrize("ancho", [360, 390])
def test_telefono_con_usuario_y_proyecto_sin_desbordes(navegador, sitio, ancho):
    pagina, errores = _abrir_portal(navegador, sitio, ancho=ancho, alto=844, proyectos=True, movil=True)
    pagina.evaluate("localStorage.setItem('quempin_usuario', 'LC'); localStorage.setItem('quempin_portal_proyecto', JSON.stringify('QMPN-2026-001'))")
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    assert pagina.locator("#usuarioActual").inner_text() == "LC"
    d = pagina.evaluate(JS_DESBORDES)
    assert d["doc"] <= ancho and not d["fuera"], d
    caja = pagina.locator("#btnUsuario").bounding_box()
    assert caja["x"] >= 0 and caja["x"] + caja["width"] <= ancho, caja
    pagina.locator("#btnUsuario").click()
    pop = pagina.locator("#popUsuario").bounding_box()
    assert pop["x"] >= 0 and pop["x"] + pop["width"] <= ancho, pop
    assert not errores
    pagina.context.close()

# ---- Las carpetas en el Explorador (2026-10-19, QUEMPIN.exe 1.3.10): hoy desde Proyectos en ejecución -------------------


def test_sistema_quempin_atiende_las_carpetas_que_pide_el_portal():
    """quempin://carpeta/<formulacion|gestion>/… es lo que lee app/carpetas.py de Sistema QUEMPIN."""
    sistema = _hermano("Sistema QUEMPIN")
    carpetas = sistema / "app" / "carpetas.py" if sistema else None
    if not carpetas or not carpetas.exists():
        pytest.skip("Sistema QUEMPIN no está en este equipo")
    fuente = carpetas.read_text(encoding="utf-8")
    assert 'ACCIONES = ("carpeta", "trasladar")' in fuente
    assert '"formulacion": ubicacion.BIBLIOTECA_FORMULACION' in fuente and '"gestion": ubicacion.BIBLIOTECA_GESTION' in fuente
    portal = texto_portal()
    assert "'quempin://carpeta/' + c.biblioteca + '/'" in portal


def test_el_buscador_ofrece_formulador_seguimiento_o_ejecucion_segun_la_etapa(navegador, sitio):
    """Pedido del 2026-11-12: al buscar un proyecto reconocido, botones a su Formulador, su Seguimiento o «En ejecución»
    según la etapa en que va. Un botón no va dentro de otro: la fila los lleva al lado del resultado."""
    pagina, errores = _recorrido_con_datos(navegador, sitio, usuario="LC")
    botones = lambda: pagina.locator("#resultados .res-fila").first.locator(".res-ir").all_inner_texts()
    pagina.locator("#buscar").fill("908")                 # en obra
    assert botones() == ["En ejecución"]
    pagina.locator("#resultados .res-ir", has_text="En ejecución").click()
    assert pagina.locator("#vistaEjecucion").is_visible() and pagina.locator("#ejProyecto").is_visible()
    assert pagina.locator("#resultados").is_hidden()
    pagina.locator("#buscar").fill("900")                 # requerimiento sin formulación: formularlo
    assert botones() == ["Formulador"]
    pagina.locator("#buscar").fill("909")                 # terminada, sin formulación ni obra: solo su detalle
    assert pagina.locator("#resultados .res-fila").count() == 0 and pagina.locator("#resultados .res").count() == 1
    pagina.locator("#buscar").fill("902")                 # con formulación, antes de ofertar
    assert botones() == ["Formulador"]
    pagina.locator("#resultados .res-ir", has_text="Formulador").click()
    _esperar(pagina, "formulador", "hash", "#/p/f902/ficha")
    # El proyecto del Formulador que el Recorrido ya tiene no sale dos veces
    pagina.locator("#buscar").fill("QMPN-2026-902")
    assert pagina.locator("#resultados .res").count() <= 1
    assert not errores
    pagina.context.close()


def test_cerrar_sesion_borra_la_clave_y_cierra_las_otras_pestanas(navegador, sitio):
    # 2026-11-18: «Cerrar sesión en este equipo» borra la clave recordada; todas las herramientas la piden otra vez.
    # Sin semilla: la del ayudante vuelve a escribir la clave en cada carga
    pagina, errores = _abrir_portal(navegador, sitio, clave=False)
    pagina.evaluate("localStorage.setItem('quempin_viz_clave', 'clave-de-mentira')")
    otra = pagina.context.new_page()
    otra.goto(sitio + "/finanzas-quempin/portal/")
    otra.locator("#vistaInicio").wait_for()
    otra.evaluate("window.__sinRecargar = true")
    pagina.locator("#btnUsuario").click()
    assert pagina.locator("#cerrarSesion").is_visible()
    dialogos = []
    pagina.on("dialog", lambda d: (dialogos.append(d.message), d.accept()))
    with pagina.expect_navigation():
        pagina.locator("#cerrarSesion").click()
    pagina.locator("#vistaInicio").wait_for()
    assert pagina.evaluate("localStorage.getItem('quempin_viz_clave')") is None
    assert len(dialogos) == 1, dialogos      # nada sin guardar: una sola pregunta
    # La otra pestaña del portal se recarga sola (no tenía nada sin guardar)
    otra.wait_for_function("!window.__sinRecargar")
    # Sin clave guardada, el botón no aparece y el tablero pide la contraseña
    pagina.locator("#btnUsuario").click()
    assert pagina.locator("#cerrarSesion").is_hidden()
    pagina.keyboard.press("Escape")
    _menu(pagina, "Centro de Costos")
    assert _marco(pagina, "centro-costos", "cc").locator("#pwGate").is_visible()
    assert not errores
    pagina.context.close()


def test_cancelar_cerrar_sesion_no_borra_nada(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.locator("#btnUsuario").click()
    pagina.once("dialog", lambda d: d.dismiss())
    pagina.locator("#cerrarSesion").click()
    assert pagina.evaluate("localStorage.getItem('quempin_viz_clave')") == "clave-de-mentira"
    assert not errores
    pagina.context.close()
