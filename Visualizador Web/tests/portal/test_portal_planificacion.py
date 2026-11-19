# -*- coding: utf-8 -*-
"""Portal QUEMPIN: Planificación semanal.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- Planificación semanal (2026-10-20) -------------------------------------------------------------


def test_el_uso_del_portal_se_cuenta_anonimo_y_llega_a_la_carpeta(navegador, sitio):
    """2026-11-09: para saber qué herramientas usa el equipo. Cada apertura de una herramienta cuenta una vez por día
    (volver a la misma pestaña sin pasar por otra no); al dejar la pestaña se guarda en publicado/uso-portal/, sin usuario."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC")       # abre la Planificación semanal
    for _ in range(2):
        pagina.locator("#pestanas .ir", has_text="Inicio").click()
        pagina.locator('.ini-item[data-herr="flujo-caja"]').click()
        _marco(pagina, "flujo-caja", "fc")
    pagina.locator("#pestanas .ir", has_text="Flujo de Caja").click()     # la misma pestaña: no cuenta
    hoy = date.today().isoformat()
    local = json.loads(pagina.evaluate("localStorage.getItem('quempin_portal_uso')"))
    assert local[hoy]["flujo-caja"] == 2 and local[hoy]["planificacion"] == 1 and "inicio" not in local[hoy]
    pagina.evaluate("""() => { Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
        document.dispatchEvent(new Event('visibilitychange')); }""")
    sobre = _esperar_archivo(pagina, f"publicado/uso-portal/{DISPOSITIVO}.json")
    assert sobre["herramienta"] == "portal" and "autor" not in sobre and "usuario" not in json.dumps(sobre["datos"])
    assert {(d["herramienta"], d["aperturas"]) for d in sobre["datos"]["dias"]} >= {("flujo-caja", 2), ("planificacion", 1)}
    assert not errores
    pagina.context.close()


def test_la_planificacion_acepta_el_n_temporal():
    """2026-11-09: un proyecto con N° temporal («001t», de Gestión sin N° de la Planilla) no se guardaba en la
    planificación: «req:001t» no pasaba las claves del portal (ni el esquema). Toda clave «req:» acepta el temporal."""
    import re
    portal = texto_portal()
    assert "req:\\d{1,6}|" not in portal and "req:\\d{1,6})" not in portal, "una clave req: sin el N° temporal"
    for nombre in ("PL_CLAVE", "PL_CLAVE_CIERRE", "EJ_CLAVE"):
        m = re.search(r"const " + nombre + r" = /(.+?)/;", portal)
        assert m, nombre
        patron = re.compile(m.group(1).replace("\\d", "[0-9]"))
        assert patron.fullmatch("req:001t") and patron.fullmatch("req:289"), nombre
        assert not patron.fullmatch("req:001x") and not patron.fullmatch("req:1t"), nombre


def test_la_planificacion_semanal_en_el_registro():
    """Pedido del 2026-10-20: planificar la semana con el personal NB, ES, LC, CM, MP y EV, como máximo 3 proyectos
    por persona en un día. Lee y guarda en la carpeta del equipo, y Configuración y conexiones lo dice."""
    reg = _registro()
    h = {x["id"]: x for x in reg["herramientas"]}["planificacion"]
    assert h["tipo"] == "vista" and h["vista"] == "vistaPlan" and h["grupo"] == "ejecutar"
    assert reg["personal"] == ["NB", "ES", "LC", "CM", "MP", "EV", "RL"]
    assert set(reg["usuarios"]) <= set(reg["personal"]), "quien usa las herramientas también se planifica"
    # Nombre y apellido de cada uno (pedido del usuario, 2026-11-18): van en el correo de las rendiciones
    assert set(reg["nombres"]) <= set(reg["personal"]) and all(len(n.split()) >= 2 for n in reg["nombres"].values())
    usan = {e["id"]: e["usan"] for e in _conexiones()["elementos"]}
    assert "planificacion" in usan["biblioteca"] and "planificacion" in usan["intercambio"]
    portal = texto_portal()
    assert "const PL_MAX = 3;" in portal
    # Lo que escribe es una publicación del catálogo del intercambio
    esquemas = _cargar("esquemas_para_test_portal", RAIZ / "Sistema Intercambio" / "esquemas.py")
    assert "planificacion-semana" in esquemas.publicaciones()


def test_la_planificacion_sin_biblioteca_dice_que_conectar(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.locator('.ini-item[data-herr="planificacion"]').click()
    assert _pestanas(pagina) == ["Inicio", "Planificación"]
    assert pagina.url.endswith("#/planificacion") and pagina.locator("iframe").count() == 0
    pagina.locator("#plVacio").wait_for()
    texto = pagina.locator("#plVacio").inner_text()
    if pagina.evaluate("typeof showDirectoryPicker === 'function'"):
        assert "Conecta la biblioteca del equipo" in texto and "La planificación lee los proyectos en ejecución" in texto
    else:
        assert "Chrome o Edge" in texto
    assert pagina.locator("#plContenido").is_hidden()
    # Sin datos no se sabe nada: no hay alarma
    assert pagina.locator("#plAlertaCab").is_hidden() and pagina.locator(".pl-alerta-n").count() == 0
    assert not errores
    pagina.context.close()


def test_la_alarma_muestra_los_proyectos_activos_sin_asignar(navegador, sitio):
    """Pedido del 2026-10-20: si un proyecto activo no se asigna en la semana actual, una alarma. Se ve en el menú y en
    el Inicio (en la cabecera ya no, a pedido del 2026-10-28), y la vista dice cuáles son."""
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC")
    item = pagina.locator('.ini-item[data-herr="planificacion"]')
    pagina.locator(ALERTA_N).wait_for(state="attached")
    assert pagina.locator("#plAlertaCab, .cab-alerta").count() == 0
    assert item.locator(".pl-alerta-n").count() == 0, "en el Inicio ya no (2026-11-18)"
    assert item.locator(".ini-fuera").count() == 0, "se abre dentro del portal"
    pagina.locator("#btnMenu").click()
    pagina.locator("#grupo-ejecutar").click()
    assert pagina.locator('#menu .menu-item[data-herr="planificacion"] .pl-alerta-n').inner_text() == "3"
    pagina.keyboard.press("Escape")
    item.click()
    _alarma(pagina).wait_for()
    assert _pestanas(pagina) == ["Inicio", "Planificación"]
    assert pagina.locator("#plAlarma").get_attribute("data-nivel") == "bad"
    assert pagina.locator("#plAlarma .pl-alarma-tit").inner_text() == "3 proyectos activos sin nadie asignado esta semana"
    assert _alarma(pagina).locator(".pl-alarma-p").all_inner_texts() == list(ACTIVOS.values())
    assert [int(x) for x in pagina.locator("#plResumen .rc-kpi-n").all_inner_texts()][:2] == [3, 3]
    assert pagina.locator("#plSemanaRango").inner_text().startswith("Esta semana · ") and pagina.locator("#plHoy").is_disabled()
    # Cada proyecto de la alarma lleva a su fila en «Por proyecto», donde los sin asignar van primero
    _alarma(pagina).locator(".pl-alarma-p", has_text="En obra").click()
    assert pagina.locator('.pl-vista[data-vista="proyecto"]').get_attribute("aria-pressed") == "true"
    assert pagina.locator("#plProyecto tr[data-clave]").evaluate_all("ts => ts.map((t) => t.dataset.clave)") == list(ACTIVOS)
    assert pagina.locator("#plProyecto tr.alarma").count() == 3
    # El nombre abre su detalle del Recorrido
    pagina.locator('#plProyecto tr[data-clave="req:908"] .pl-proy').click()
    assert pagina.locator("#dlgRcTit").inner_text() == "N° 908 · En obra"
    pagina.keyboard.press("Escape")
    assert not errores
    pagina.context.close()


def test_asignar_por_personal_queda_en_la_carpeta_del_equipo(navegador, sitio):
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    assert list(pagina.evaluate(JS_PERSONAL)) == ["NB", "ES", "LC", "CM", "MP", "EV", "RL"]
    assert pagina.locator("#plPersonal tr.tuya").get_attribute("data-persona") == "LC"
    _celda_personal(pagina, "LC", 0).click()
    pop = pagina.locator("#plPop")
    assert pop.is_visible() and pagina.locator("#plPopTit").inner_text().startswith("LC · Lunes ")
    assert pagina.locator("#plPopSub").inner_text() == "0 de 3 proyectos este día"
    pop.locator('input[data-op="c|req:908"]').check()
    assert pagina.evaluate(JS_PERSONAL)["LC"][0] == ["En obra"]
    assert "LC va a En obra el lunes" in pagina.locator("#aviso").inner_text()
    assert pagina.locator(ALERTA_N).inner_text() == "2"
    # Queda en la carpeta, en el archivo de este navegador, con quién lo hizo; y cumple el esquema del catálogo
    archivo = f"publicado/planificacion/{semana}/{DISPOSITIVO}.json"
    sobre = _esperar_archivo(pagina, archivo)
    d = sobre["datos"]
    assert (sobre["herramienta"], d["semana"], d["desde"], d["dispositivo"]) == ("planificacion", semana, lunes.isoformat(), DISPOSITIVO)
    assert [(x["dia"], x["persona"], x["proyecto"], x["activa"], x["por"]) for x in d["asignaciones"]] == [
        (lunes.isoformat(), "LC", "req:908", True, "LC")]
    assert d["proyectos"]["req:908"]["titulo"] == "En obra"
    esquemas = _cargar("esquemas_para_test_portal", RAIZ / "Sistema Intercambio" / "esquemas.py")
    assert esquemas.validar_publicacion("planificacion-semana", sobre) == []
    pagina.wait_for_function("document.getElementById('plFrescura').textContent === 'Guardado · OneDrive lo lleva al equipo'")
    # Al volver a abrir el portal sigue ahí
    pagina.reload()
    pagina.locator('#plPersonal tr[data-persona="LC"] .pl-chip').first.wait_for()
    assert pagina.evaluate(JS_PERSONAL)["LC"][0] == ["En obra"]
    # Quitarla también se guarda (manda el cambio más reciente)
    _celda_personal(pagina, "LC", 0).click()
    pop.locator('input[data-op="c|req:908"]').uncheck()
    assert pagina.evaluate(JS_PERSONAL)["LC"][0] == []
    sobre = _esperar_archivo(pagina, archivo, lambda s: not s["datos"]["asignaciones"][0]["activa"])
    assert len(sobre["datos"]["asignaciones"]) == 1
    # Escape cierra la ventanita y vuelve a la casilla
    pagina.keyboard.press("Escape")
    assert pop.is_hidden()
    assert pagina.evaluate("document.activeElement.dataset.ancla") == "p|LC|" + lunes.isoformat()
    assert not errores
    pagina.context.close()


def test_como_maximo_tres_proyectos_por_persona_en_un_dia(navegador, sitio):
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    pop = pagina.locator("#plPop")
    _celda_personal(pagina, "LC", 1).click()
    for c in ACTIVOS:
        pop.locator(f'input[data-op="c|{c}"]').check()
    assert pagina.locator("#plPopSub").inner_text() == "3 de 3 proyectos este día"
    assert "ya tiene 3 proyectos el martes" in pop.locator(".pl-pop-nota").inner_text()
    # La nota va dentro de la ventanita (con la clase del aviso de abajo quedaba flotando sobre él)
    nota, caja = pop.locator(".pl-pop-nota").bounding_box(), pop.bounding_box()
    assert caja["y"] <= nota["y"] and nota["y"] + nota["height"] <= caja["y"] + caja["height"], (nota, caja)
    assert pop.locator('input[data-op="otra"]').count() == 0, "tampoco otra actividad"
    assert _celda_personal(pagina, "LC", 1).locator(".pl-lleno").inner_text() == "Completo"
    pagina.keyboard.press("Escape")
    # NB ese día en otra actividad; LC no puede sumarse: ya está completo
    _celda_personal(pagina, "NB", 1).click()
    pop.locator('input[data-op="otra"]').fill("oficina")
    pop.locator('input[data-op="otra"]').press("Enter")
    assert pagina.evaluate(JS_PERSONAL)["NB"][1] == ["Oficina"]
    pagina.keyboard.press("Escape")
    pagina.locator('.pl-vista[data-vista="proyecto"]').click()
    assert "Otra actividad" in pagina.locator('#plProyecto tr[data-clave="otra:oficina"]').inner_text()
    _celda_proyecto(pagina, "otra:oficina", 1).click()
    lc = pop.locator('input[data-op="c|LC"]')
    assert lc.is_disabled() and not lc.is_checked()
    assert "Completo: ya tiene 3 proyectos ese día" in pop.locator("li:has(input[data-op='c|LC'])").inner_text()
    assert pop.locator('input[data-op="c|NB"]').is_checked() and pop.locator('input[data-op="c|ES"]').is_enabled()
    pagina.keyboard.press("Escape")
    # Dos computadores a la vez pueden pasarse del máximo: la casilla queda en rojo para corregirla
    semana, lunes = _semana_de(date.today())
    martes = (lunes + timedelta(days=1)).isoformat()
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {f"publicado/planificacion/{semana}/otro0001.json": _sobre_plan(semana, lunes, "otro0001",
        asignaciones=[{"dia": martes, "persona": "LC", "proyecto": "otra:bodega", "activa": True, "t": _instante(5), "por": "NB"}],
        proyectos={"otra:bodega": {"titulo": "Bodega"}})})
    pagina.locator('.pl-vista[data-vista="personal"]').click()
    pagina.locator("#plActualizar").click()
    pagina.locator('#plPersonal tr[data-persona="LC"] td[data-dia="1"] .pl-celda.exceso').wait_for()
    assert _celda_personal(pagina, "LC", 1).locator(".pl-lleno").inner_text() == "4 de 3: quita 1"
    assert "Bodega" in pagina.evaluate(JS_PERSONAL)["LC"][1]
    assert not errores
    pagina.context.close()


def test_toda_la_semana_una_ausencia_y_deshacer(navegador, sitio):
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    pop = pagina.locator("#plPop")
    fila = lambda clave: pagina.locator(f'#plProyecto tr[data-clave="{clave}"] td[data-dia]').evaluate_all(
        "tds => tds.map((td) => [...td.querySelectorAll('.pl-per')].map((p) => p.textContent).join(','))")
    _celda_proyecto(pagina, "req:907", 0).click()
    # «Toda la semana» en «Qué días»: lo que se marca vale para los cinco días, en un solo paso
    pop.locator('[data-op="d|todos"]').click()
    assert pagina.locator("#plPopSub").inner_text() == "Lo que marques vale de lunes a viernes"
    pop.locator('input[data-op="c|ES"]').check()
    assert fila("req:907") == ["ES"] * 5
    assert "ES va a Adjudicada sin ficha de lunes a viernes." in pagina.locator("#aviso").inner_text()
    assert "5 días · 1 persona" in pagina.locator('#plProyecto tr[data-clave="req:907"] th').inner_text()
    pagina.keyboard.press("Escape")
    # Ausente el miércoles: queda fuera de sus proyectos de ese día y no se le puede asignar
    pagina.locator('.pl-vista[data-vista="personal"]').click()
    _celda_personal(pagina, "ES", 2).click()
    pop.locator('[data-op="a|vacaciones"]').click()
    assert pagina.evaluate(JS_PERSONAL)["ES"] == [["Adjudicada sin ficha"], ["Adjudicada sin ficha"], ["Vacaciones"],
                                                   ["Adjudicada sin ficha"], ["Adjudicada sin ficha"]]
    assert pop.locator('input[data-op="c|req:907"]').is_disabled()
    assert pop.locator('[data-op="a|vacaciones"]').get_attribute("aria-pressed") == "true"
    aviso = pagina.locator("#aviso")
    assert "ES queda ausente el miércoles" in aviso.inner_text() and "se quitó de Adjudicada sin ficha" in aviso.inner_text()
    # «Deshacer» en el aviso lo deja como estaba, sin cerrar la ventanita
    aviso.locator("button", has_text="Deshacer").click()
    assert pagina.evaluate(JS_PERSONAL)["ES"][2] == ["Adjudicada sin ficha"]
    assert pop.is_visible() and pop.locator('[data-op="a|vacaciones"]').get_attribute("aria-pressed") == "false"
    # Ctrl Z deshace el cambio anterior: los cinco días juntos
    pagina.keyboard.press("Escape")
    pagina.keyboard.press("Control+z")
    assert pagina.evaluate(JS_PERSONAL)["ES"] == [[], [], [], [], []]
    assert not errores
    pagina.context.close()


def test_varios_dias_cambiar_y_ausencia_en_un_paso(navegador, sitio):
    """Pedido del 2026-10-23 (asignar rápido): en la ventanita se eligen varios días y lo que se marca vale para todos, con
    un solo aviso y un solo «Deshacer». «Cambiar» pasa a la persona de un proyecto a otro en un clic."""
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    _, lunes = _semana_de(date.today())
    iso = lambda i: (lunes + timedelta(days=i)).isoformat()
    pop = pagina.locator("#plPop")
    _celda_personal(pagina, "LC", 0).click()
    assert pop.locator(f'[data-op="d|{iso(0)}"]').get_attribute("aria-pressed") == "true"
    assert pop.locator('.pl-dia-op[aria-pressed="true"]').count() == 1
    pop.locator(f'[data-op="d|{iso(1)}"]').click()
    pop.locator(f'[data-op="d|{iso(2)}"]').click()
    assert pagina.locator("#plPopTit").inner_text() == "LC · 3 días"
    assert pagina.locator("#plPopSub").inner_text() == "Lo que marques vale de lunes a miércoles"
    pop.locator('input[data-op="c|req:908"]').check()
    assert [d[:1] for d in pagina.evaluate(JS_PERSONAL)["LC"]] == [["En obra"]] * 3 + [[], []]
    assert pagina.locator("#aviso").inner_text().startswith("LC va a En obra de lunes a miércoles.")
    # Con toda la semana, la casilla queda a medias (va solo algunos días) y marcarla completa los que faltan
    pop.locator('[data-op="d|todos"]').click()
    casilla = pop.locator('input[data-op="c|req:908"]')
    assert casilla.evaluate("c => c.indeterminate") and not casilla.is_checked()
    assert f"va lun {lunes.day}, mar " in pop.locator("li:has(input[data-op='c|req:908'])").inner_text()
    casilla.click()
    assert pagina.evaluate(JS_PERSONAL)["LC"] == [["En obra"]] * 5
    assert pagina.locator("#aviso").inner_text().startswith("LC va a En obra el jueves y el viernes.")
    # «Cambiar»: de En obra a Adjudicada sin ficha los cinco días, en un paso; Escape vuelve de «Cambiar» sin cerrar
    pop.locator('[data-op="k|req:908"]').click()
    assert "Pasar a LC de En obra a otro proyecto de lunes a viernes" in pop.locator(".pl-pop-nota").inner_text()
    pagina.keyboard.press("Escape")
    assert pop.is_visible() and pop.locator('[data-op="k|req:908"]').count() == 1
    pop.locator('[data-op="k|req:908"]').click()
    pop.locator('[data-op="x|req:907"]').click()
    assert pagina.evaluate(JS_PERSONAL)["LC"] == [["Adjudicada sin ficha"]] * 5
    assert pagina.locator("#aviso").inner_text().startswith("LC cambia de En obra a Adjudicada sin ficha de lunes a viernes.")
    assert pagina.evaluate("document.activeElement.dataset.op") == "c|req:907"
    # Un solo Ctrl Z deshace el cambio entero
    pagina.keyboard.press("Escape")
    pagina.keyboard.press("Control+z")
    assert pagina.evaluate(JS_PERSONAL)["LC"] == [["En obra"]] * 5
    # Ausente el jueves y el viernes de una vez: se quita de sus proyectos esos días
    _celda_personal(pagina, "LC", 3).click()
    pop.locator(f'[data-op="d|{iso(4)}"]').click()
    pop.locator('[data-op="a|permiso"]').click()
    assert pagina.evaluate(JS_PERSONAL)["LC"] == [["En obra"]] * 3 + [["Permiso"]] * 2
    assert pagina.locator("#aviso").inner_text().startswith("LC queda ausente el jueves y el viernes (permiso); se quitó de En obra.")
    assert pop.locator('[data-op="a|permiso"]').get_attribute("aria-pressed") == "true"
    # Con toda la semana, la ventanita dice qué días se saltan; «Quitar ausencia» la quita donde está
    pop.locator('[data-op="d|todos"]').click()
    assert "Al agregar se saltan el jueves" in pop.locator(".pl-pop-nota").inner_text()
    assert pop.locator(f'[data-op="d|{iso(3)}"]').evaluate("b => b.classList.contains('bloq')")
    pop.locator('[data-op="a|"]').click()
    assert pagina.evaluate(JS_PERSONAL)["LC"] == [["En obra"]] * 3 + [[], []]
    assert not errores
    pagina.context.close()


def test_casos_borde_de_varios_dias_cambiar_e_imprimir(navegador, sitio):
    """Lo que encontró la revisión del 2026-10-23: el sábado que se esconde con la ventanita abierta, la casilla a medias
    que no se podía quitar, «Cambiar» cuando el destino ya estaba, «Siguiente sin nadie» que iba y volvía, la hoja de
    quien está ausente toda la semana, «Salen 2 hojas» y el margen oscuro al imprimir en modo oscuro."""
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    _, lunes = _semana_de(date.today())
    iso = lambda i: (lunes + timedelta(days=i)).isoformat()
    pop = pagina.locator("#plPop")
    aviso = lambda: pagina.locator("#aviso").inner_text()
    # «Siguiente sin nadie» recorre todos los de la alarma, aunque se deje alguno pendiente
    _alarma(pagina).locator(".pl-alarma-p").first.click()
    titulos = [pagina.locator("#plPopTit").inner_text()]
    for _ in range(2):
        pagina.locator("#plPopSiguiente").click()
        titulos.append(pagina.locator("#plPopTit").inner_text())
    assert len(set(titulos)) == 3, titulos
    pagina.keyboard.press("Escape")
    pagina.locator('.pl-vista[data-vista="personal"]').click()
    # El sábado: al quitarle lo último su columna se esconde, pero la ventanita sigue en el sábado (no salta al lunes)
    _mas(pagina, "#plSabado").check()
    _celda_personal(pagina, "ES", 5).click()
    pop.locator('input[data-op="c|req:908"]').check()
    pagina.keyboard.press("Escape")
    _mas(pagina, "#plSabado").click()          # ya no se pide, pero queda a la vista porque tiene algo
    assert pagina.locator("#plSabado").is_disabled()
    _celda_personal(pagina, "ES", 5).click()
    pop.locator('input[data-op="c|req:908"]').uncheck()
    assert pagina.locator('#plPersonal td[data-dia="5"]').count() == 0
    assert pagina.locator("#plPopTit").inner_text().startswith("ES · Sábado ")
    pop.locator('input[data-op="c|req:908"]').check()
    assert aviso().startswith("ES va a En obra el sábado")
    assert pagina.evaluate(JS_PERSONAL)["ES"][0] == []
    pop.locator('input[data-op="c|req:908"]').uncheck()
    pagina.keyboard.press("Escape")
    # Con un día de vacaciones, ir todos los demás días cuenta como marcada (no a medias): al tocarla se quita
    _celda_personal(pagina, "ES", 0).click()
    pop.locator('[data-op="d|todos"]').click()
    pop.locator('input[data-op="c|req:908"]').check()
    pagina.keyboard.press("Escape")
    _celda_personal(pagina, "ES", 4).click()
    pop.locator('[data-op="a|vacaciones"]').click()
    pop.locator('[data-op="d|todos"]').click()
    casilla = pop.locator('input[data-op="c|req:908"]')
    assert casilla.is_checked() and not casilla.evaluate("c => c.indeterminate")
    casilla.uncheck()
    assert pagina.evaluate(JS_PERSONAL)["ES"] == [[], [], [], [], ["Vacaciones"]]
    pagina.keyboard.press("Escape")
    # «Cambiar» cuando el destino ya estaba algún día: ese día solo se quita el origen
    _celda_personal(pagina, "LC", 0).click()
    pop.locator(f'[data-op="d|{iso(1)}"]').click()
    pop.locator('input[data-op="c|req:908"]').check()
    pop.locator('[data-op="d|solo"]').click()
    pop.locator('input[data-op="c|req:907"]').check()
    pop.locator(f'[data-op="d|{iso(1)}"]').click()
    pop.locator('[data-op="k|req:908"]').click()
    assert f"ya va lun {lunes.day}" in pop.locator('[data-op="x|req:907"]').inner_text()
    pop.locator('[data-op="x|req:907"]').click()
    assert pagina.evaluate(JS_PERSONAL)["LC"][:2] == [["Adjudicada sin ficha"], ["Adjudicada sin ficha"]]
    pagina.keyboard.press("Escape")
    # La hoja de quien está ausente toda la semana lo dice; sin la tabla, «Salen 2 hojas»
    _celda_personal(pagina, "ES", 0).click()
    pop.locator('[data-op="d|todos"]').click()
    pop.locator('[data-op="a|licencia"]').click()
    pagina.keyboard.press("Escape")
    pagina.evaluate("""() => { window.print = () => {
        window.__hojas = [...document.querySelectorAll('#plDoc .pl-doc-hoja')].map((s) => s.innerText);
        window.dispatchEvent(new Event('afterprint'));
    }; }""")
    _mas(pagina, "#plImprimir").click()
    dlg = pagina.locator("#dlgPlExportar")
    assert dlg.locator("#plExpPers input:checked").evaluate_all("xs => xs.map((x) => x.value)") == ["ES", "LC"]
    dlg.locator("#plExpTabla").uncheck()
    assert dlg.locator("#plExpCuenta").inner_text() == "Salen 2 hojas de personas."
    dlg.locator("#plExpImprimir").click()
    hojas = pagina.evaluate("window.__hojas")
    assert "Ausente toda la semana" in hojas[0] and "de 5 días con proyecto" in hojas[1]
    # Al imprimir en modo oscuro, la página entera queda en claro (también el margen de cada hoja)
    pagina.locator("#btnTema").click()
    pagina.emulate_media(media="print")
    claro = pagina.evaluate("""() => { document.body.classList.add('pl-imprimiendo');
        const c = getComputedStyle(document.documentElement); const r = [c.colorScheme, c.backgroundColor];
        document.body.classList.remove('pl-imprimiendo'); return r; }""")
    pagina.emulate_media(media="screen")
    assert claro == ["light", "rgb(255, 255, 255)"], claro
    assert not errores
    pagina.context.close()


def test_cambiar_quien_va_y_moverse_con_el_teclado(navegador, sitio):
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    _, lunes = _semana_de(date.today())
    pop = pagina.locator("#plPop")
    _celda_proyecto(pagina, "req:908", 0).click()
    pop.locator('input[data-op="c|ES"]').check()
    # «Cambiar» a ES: va MP en su lugar, en un paso
    pop.locator('[data-op="k|ES"]').click()
    assert pop.locator('[data-op="x|ES"]').count() == 0
    pop.locator('[data-op="x|MP"]').click()
    assert pagina.locator("#aviso").inner_text().startswith(f"MP va a En obra en vez de ES el lunes {lunes.day}.")
    assert pop.locator('input[data-op="c|MP"]').is_checked() and not pop.locator('input[data-op="c|ES"]').is_checked()
    pagina.keyboard.press("Escape")
    # Las flechas van de casilla en casilla; Enter abre la ventanita
    ancla = lambda: pagina.evaluate("document.activeElement.dataset.ancla")
    iso = lambda i: (lunes + timedelta(days=i)).isoformat()
    assert ancla() == f"j|req:908|{iso(0)}"
    pagina.keyboard.press("ArrowRight")
    assert ancla() == f"j|req:908|{iso(1)}"
    claves = pagina.locator("#plProyecto tr[data-clave]").evaluate_all("ts => ts.map((t) => t.dataset.clave)")
    i = claves.index("req:908")
    pagina.keyboard.press("ArrowUp" if i else "ArrowDown")
    assert ancla() == f"j|{claves[i - 1 if i else 1]}|{iso(1)}"
    pagina.keyboard.press("ArrowDown" if i else "ArrowUp")
    pagina.keyboard.press("End")
    assert ancla() == f"j|req:908|{iso(4)}"
    pagina.keyboard.press("Enter")
    assert pop.is_visible() and pagina.locator("#plPopTit").inner_text() == "En obra"
    assert not errores
    pagina.context.close()


def test_la_alarma_abre_el_proyecto_y_sigue_con_el_siguiente(navegador, sitio):
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    nombres = list(ACTIVOS.values())
    pop = pagina.locator("#plPop")
    sig = pagina.locator("#plPopSiguiente")
    _alarma(pagina).locator(".pl-alarma-p", has_text=nombres[0]).click()
    assert pagina.locator('.pl-vista[data-vista="proyecto"]').get_attribute("aria-pressed") == "true"
    assert pop.is_visible() and pagina.locator("#plPopTit").inner_text() == nombres[0]
    assert sig.inner_text() == f"Siguiente sin nadie: {nombres[1]} ›"
    pop.locator('input[data-op="c|LC"]').check()
    assert pagina.locator(ALERTA_N).inner_text() == "2"
    sig.click()
    assert pagina.locator("#plPopTit").inner_text() == nombres[1]
    # Si esa semana no se trabaja en él, se marca desde la misma ventanita
    pop.locator('[data-op="pausa"]').click()
    assert pagina.locator(ALERTA_N).inner_text() == "1"
    assert pop.locator('[data-op="pausa"]').get_attribute("aria-pressed") == "true"
    sig.click()
    assert pagina.locator("#plPopTit").inner_text() == nombres[2] and sig.is_hidden()
    assert not errores
    pagina.context.close()


def test_asignar_en_el_tablero_general_elige_el_proyecto_y_despues_quienes(navegador, sitio):
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="general")
    _, lunes = _semana_de(date.today())
    pop = pagina.locator("#plPop")
    _dia_general(pagina, 0)
    pagina.locator(f'#plGeneral [data-ancla="n|{lunes.isoformat()}"]').click()
    assert pagina.locator("#plPopTit").inner_text() == f"Asignar el lunes {lunes.day}"
    assert pop.locator(".pl-grupo h4").all_text_contents() == ["Sin nadie ese día"]
    pop.locator('[data-op="d|todos"]').click()
    pop.locator('[data-op="n|req:908"]').click()
    # El proyecto, con los mismos días elegidos y la vuelta a la lista
    assert pagina.locator("#plPopTit").inner_text() == "En obra"
    assert pagina.locator("#plPopSub").inner_text() == "Lo que marques vale de lunes a viernes"
    pop.locator('input[data-op="c|NB"]').check()
    pop.locator('[data-op="volver"]').click()
    assert pop.locator(".pl-grupo h4").all_text_contents() == ["Sin nadie esos días", "Ya tienen a alguien"]
    assert "van NB" in pop.locator('[data-op="n|req:908"]').inner_text()
    assert not errores
    pagina.context.close()


def test_general_muestra_un_dia_en_grande_y_la_semana_al_lado(navegador, sitio):
    """General (2026-11-16, el usuario eligió «Hoy con la semana al lado»): hoy en grande y, al lado, una línea por día
    con cuántos tienen algo y una barra con el color de cada proyecto; tocar un día lo muestra en grande. Abajo, los
    avisos de la semana: los proyectos sin nadie abren su lista."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="general")
    _, lunes = _semana_de(date.today())
    hoy = date.today().weekday()
    hoy = hoy if hoy < 5 else 0
    dias = pagina.locator("#plGeneral .pl-sem-dia")
    assert dias.evaluate_all("bs => bs.map((b) => b.getAttribute('aria-pressed'))") == ["true" if i == hoy else "false" for i in range(5)]
    assert pagina.locator("#plGeneral .pl-dia").evaluate_all("ds => ds.map((d) => d.dataset.dia)") == [str(hoy)]
    aviso = pagina.locator("#plGeneral .pl-sem-aviso", has_text="sin nadie")
    assert aviso.inner_text() == "3 proyectos sin nadie esta semana"
    aviso.click()
    assert pagina.locator("#plAlarma").is_visible()
    # Asignar dos personas el miércoles: su línea las cuenta y lleva el color del proyecto
    _dia_general(pagina, 2)
    assert pagina.evaluate("() => document.activeElement.dataset.dia") == "2"
    mie = _dias_de(lunes)[2].isoformat()
    pagina.locator(f'#plGeneral [data-ancla="n|{mie}"]').click()
    pop = pagina.locator("#plPop")
    pop.locator('[data-op="n|req:908"]').click()
    pop.locator('input[data-op="c|NB"]').check()
    pop.locator('input[data-op="c|ES"]').check()
    pagina.keyboard.press("Escape")
    linea = pagina.locator('#plGeneral .pl-sem-dia[data-dia="2"]')
    assert linea.locator(".pl-sem-n").inner_text() == "2"
    assert linea.locator(".pl-sem-barra i").count() == 1
    assert "2 personas en 1 proyecto (En obra)" in linea.get_attribute("title")
    assert pagina.locator('#plGeneral .pl-sem-dia[data-dia="1"] .pl-sem-barra.vacia').count() == 1
    assert pagina.locator(f'#plGeneral .pl-bloque[data-ancla="j|req:908|{mie}"] .pl-per').all_inner_texts() == ["NB", "ES"]
    assert pagina.locator("#plGeneral .pl-sem-aviso", has_text="sin nadie").inner_text() == "2 proyectos sin nadie esta semana"
    assert not errores
    pagina.context.close()


def test_general_avisa_el_vehiculo_en_dos_lugares_y_las_ausencias(navegador, sitio):
    """En «La semana» de General, el día con un vehículo en dos lugares lleva su ícono y un aviso que lo muestra en
    grande; las ausencias van en una línea por persona."""
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    _, lunes = _semana_con_vehiculos(pagina)
    _celda_personal(pagina, "EV", 3).click()
    pagina.locator('#plPop [data-op="a|vacaciones"]').click()
    pagina.keyboard.press("Escape")
    pagina.locator('.pl-vista[data-vista="general"]').click()
    alertas = pagina.locator("#plGeneral .pl-sem-dia").evaluate_all("bs => bs.map((b) => !!b.querySelector('.pl-sem-alerta svg'))")
    assert alertas == [False, True, False, False, False]
    assert "La RAM en 2 lugares a la vez" in pagina.locator('#plGeneral .pl-sem-dia[data-dia="1"]').get_attribute("title")
    avisos = pagina.locator("#plGeneral .pl-sem-aviso")
    martes = _dias_de(lunes)[1]
    assert avisos.all_inner_texts()[-2:] == [f"Mar {martes.day}: RAM en 2 lugares", "EV: vacaciones, 1 día"]
    avisos.filter(has_text="RAM en 2 lugares").click()
    assert pagina.locator("#plGeneral .pl-dia-grande").get_attribute("data-dia") == "1"
    assert pagina.locator('#plGeneral .pl-sem-dia[data-dia="1"]').get_attribute("aria-pressed") == "true"
    assert not errores
    pagina.context.close()


def test_sin_trabajo_esta_semana_no_cuenta_como_alarma(navegador, sitio):
    pagina, errores = _plan_con_datos(navegador, sitio, vista="proyecto")
    fila = pagina.locator('#plProyecto tr[data-clave="tag:SOLO"]')
    fila.locator(".pl-pausar").click()
    assert pagina.locator(ALERTA_N).inner_text() == "2"
    assert "pausa" in fila.get_attribute("class") and fila.locator(".rc-chip:not(.pl-avance)").inner_text() == "Sin trabajo esta semana"
    assert "Obra sin número" not in pagina.locator("#plAlarma").inner_text()
    assert pagina.locator("#plResumen .rc-kpi").nth(1).locator(".rc-kpi-sub").inner_text() == "Y 1 sin trabajo esta semana"
    # Los que no se trabajan van al final
    assert pagina.locator("#plProyecto tr[data-clave]").evaluate_all("ts => ts.map((t) => t.dataset.clave)")[-1] == "tag:SOLO"
    fila.locator(".pl-pausar", has_text="Volver a planificar").click()
    assert pagina.locator(ALERTA_N).inner_text() == "3"
    # Asignarle a alguien también lo saca de la pausa
    fila.locator(".pl-pausar").click()
    _celda_proyecto(pagina, "tag:SOLO", 3).click()
    pagina.locator('#plPop input[data-op="c|MP"]').check()
    assert "Ya no está «sin trabajo esta semana»" in pagina.locator("#aviso").inner_text()
    assert "pausa" not in (fila.get_attribute("class") or "") and pagina.locator(ALERTA_N).inner_text() == "2"
    assert not errores
    pagina.context.close()


def test_los_cambios_de_otro_computador_se_unen_y_manda_el_mas_reciente(navegador, sitio):
    """Cada navegador escribe su propio archivo de la semana (OneDrive nunca tiene que juntar dos versiones del mismo):
    la semana es la unión de todos, y en cada casilla manda el cambio más reciente, también si es quitar."""
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    lun, mar = lunes.isoformat(), (lunes + timedelta(days=1)).isoformat()
    for dia in (0, 1):
        _celda_personal(pagina, "LC", dia).click()
        pagina.locator('#plPop input[data-op="c|req:908"]').check()
        pagina.keyboard.press("Escape")
    _esperar_archivo(pagina, f"publicado/planificacion/{semana}/{DISPOSITIVO}.json", lambda s: len(s["datos"]["asignaciones"]) == 2)
    # Otro computador, después: quita a LC del lunes y pone a MP el martes. Un cambio suyo de antes (quitar a LC del
    # martes, hace una hora) no manda. Un archivo a medio sincronizar se salta.
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {f"publicado/planificacion/{semana}/otro0001.json": _sobre_plan(semana, lunes, "otro0001", [
        {"dia": lun, "persona": "LC", "proyecto": "req:908", "activa": False, "t": _instante(60), "por": "NB"},
        {"dia": mar, "persona": "MP", "proyecto": "tag:SOLO", "activa": True, "t": _instante(60), "por": "NB"},
        {"dia": mar, "persona": "LC", "proyecto": "req:908", "activa": False, "t": _instante(-3600), "por": "NB"},
        {"dia": mar, "persona": "XX", "proyecto": "req:908", "activa": True, "t": _instante(60), "por": "NB"},
    ])})
    pagina.evaluate(JS_ESCRIBIR_TEXTO, [f"publicado/planificacion/{semana}/roto.json", '{"esquema": "quempin.intercambio/1", "datos": {'])
    pagina.locator("#plActualizar").click()
    pagina.locator('#plPersonal tr[data-persona="MP"] td[data-dia="1"] .pl-chip').wait_for()
    p = pagina.evaluate(JS_PERSONAL)
    assert p["LC"][:2] == [[], ["En obra"]] and p["MP"][1] == ["Obra sin número"]
    assert "XX" not in p, "solo el personal de la planificación"
    # El archivo de este navegador sigue diciendo solo lo suyo: no copia lo del otro
    mio = pagina.evaluate(JS_LEER_INTERCAMBIO, f"publicado/planificacion/{semana}/{DISPOSITIVO}.json")
    assert {(x["dia"], x["persona"]) for x in mio["datos"]["asignaciones"]} == {(lun, "LC"), (mar, "LC")}
    assert not errores
    pagina.context.close()


def test_otras_semanas_copiar_la_anterior_compartir_e_imprimir(navegador, sitio):
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    _, lunes = _semana_de(date.today())
    numero = lunes.isocalendar()[1]
    anterior = (lunes - timedelta(days=7)).isocalendar()[1]
    pagina.locator("#plAntes").click()
    assert pagina.locator("#plSemanaN").inner_text().split()[:2] == ["Semana", str(anterior)]
    assert not pagina.locator("#plSemanaRango").inner_text().startswith("Esta semana") and pagina.locator("#plHoy").is_enabled()
    pagina.locator("#plPersonal .pl-celda").first.wait_for()
    # La semana pasada: LC en «En obra» el jueves. Una semana que ya pasó no se marca en rojo.
    _celda_personal(pagina, "LC", 3).click()
    pagina.locator('#plPop input[data-op="c|req:908"]').check()
    pagina.keyboard.press("Escape")
    assert pagina.locator("#plAlarma").get_attribute("data-nivel") == ""
    pagina.locator("#plDespues").click()
    assert pagina.locator("#plSemanaRango").inner_text().startswith("Esta semana")
    pagina.locator("#plPersonal .pl-celda").first.wait_for()
    _mas(pagina, "#plCopiar").click()
    pagina.wait_for_function("document.getElementById('aviso').textContent.startsWith('Se copió')")
    assert pagina.locator("#aviso").inner_text().startswith(f"Se copió 1 asignación de la semana {anterior}.")
    assert pagina.evaluate(JS_PERSONAL)["LC"][3] == ["En obra"]
    # Compartir (2026-10-23): por persona, lo de cada uno día por día; también por día, como antes
    jueves = (lunes + timedelta(days=3)).day
    _mas(pagina, "#plCompartir").click()
    texto = pagina.locator("#plTextoArea").input_value()
    assert texto.startswith(f"*Planificación semana {numero} · ")
    assert f"\n*LC*\n• Lun {lunes.day}: sin proyecto\n" in texto and f"\n• Jue {jueves}: En obra\n" in texto
    assert texto.endswith("⚠ Sin nadie asignado: Adjudicada sin ficha, Obra sin número")
    pagina.locator('#plTextoModo [data-modo="dia"]').click()
    texto = pagina.locator("#plTextoArea").input_value()
    assert "\n*Jueves " in texto and "• En obra: LC" in texto and "Sin asignaciones" in texto
    pagina.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=sitio)
    pagina.locator("#plCopiarTexto").click()
    assert pagina.evaluate("navigator.clipboard.readText()").replace("\r\n", "\n") == texto     # Windows lo guarda con \r\n
    assert pagina.locator("#dlgPlTexto").is_hidden()
    # El orden elegido queda para la próxima vez
    _mas(pagina, "#plCompartir").click()
    assert pagina.locator('#plTextoModo [data-modo="dia"]').get_attribute("aria-pressed") == "true"
    pagina.keyboard.press("Escape")
    # Imprimir o PDF (2026-10-23): un documento propio para el papel, el mismo desde cualquier vista: la tabla de la
    # semana y una hoja para cada persona elegida (de entrada, quienes tienen algo esa semana: aquí solo LC)
    pagina.evaluate("""() => { window.print = () => {
        window.__impreso = document.body.classList.contains('pl-imprimiendo');
        window.__titulo = document.title;
        window.__hojas = [...document.querySelectorAll('#plDoc section')].map((s) => s.className + ':' + s.querySelector('h1').textContent);
        window.__tabla = [...document.querySelectorAll('#plDoc .pl-doc-t tbody tr')].map((tr) => [...tr.cells].map((c) => c.innerText.trim()));
        window.__hoja = document.querySelector('#plDoc .pl-doc-hoja') ? document.querySelector('#plDoc .pl-doc-hoja').innerText : '';
        window.dispatchEvent(new Event('afterprint'));
    }; }""")
    _mas(pagina, "#plImprimir").click()
    dlg = pagina.locator("#dlgPlExportar")
    assert dlg.is_visible()
    assert dlg.locator("#plExpPers input:checked").evaluate_all("xs => xs.map((x) => x.value)") == ["LC"]
    assert dlg.locator("#plExpCuenta").inner_text() == "Sale la tabla de la semana y 1 hoja de persona."
    dlg.locator("#plExpImprimir").click()
    assert pagina.evaluate("window.__impreso") is True and dlg.is_hidden()
    assert pagina.evaluate("window.__titulo").startswith(f"Planificación semana {numero} (")
    assert pagina.evaluate("window.__hojas") == ["pl-doc-tabla:Quién va a qué proyecto", "pl-doc-hoja:LC"]
    tabla = pagina.evaluate("window.__tabla")
    assert [f[0] for f in tabla] == ["NB", "ES", "LC", "CM", "MP", "EV", "RL"]
    assert tabla[2][4].startswith("En obra") and tabla[2][1] == "Sin proyecto"
    hoja = pagina.evaluate("window.__hoja")
    assert "En obra" in hoja and "Nadie más" in hoja and "Sin proyecto asignado" in hoja and "tú" not in hoja
    # Al terminar, el documento se vacía y la página vuelve a su título
    assert pagina.evaluate("document.body.classList.contains('pl-imprimiendo')") is False
    assert pagina.evaluate("document.getElementById('plDoc').childElementCount") == 0
    assert not pagina.evaluate("document.title").startswith("Planificación semana")
    # Sin nada elegido no se imprime
    _mas(pagina, "#plImprimir").click()
    dlg.locator("#plExpTabla").uncheck()
    dlg.locator("#plExpHojas").uncheck()
    assert dlg.locator("#plExpImprimir").is_disabled() and dlg.locator("#plExpCuenta").inner_text() == "Elige qué imprimir."
    assert not errores
    pagina.context.close()


def test_las_semanas_cruzan_el_cambio_de_ano(navegador, sitio):
    """La semana ISO 8601 es del año de su jueves: el 1 de enero de 2027 cae en la semana 53 de 2026."""
    from datetime import datetime
    pagina, errores = _portal_con_datos(navegador, sitio)
    pagina.clock.set_system_time(datetime(2027, 1, 1, 10, 0))
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Planificación semanal")
    pagina.locator("#plSemanaN").wait_for()
    assert pagina.locator("#plSemanaN").inner_text() == "Semana 53 de 2026"
    assert pagina.locator("#plSemanaRango").inner_text() == "Esta semana · 28 de diciembre al 1 de enero"
    pagina.locator("#plDespues").click()
    assert pagina.locator("#plSemanaN").inner_text() == "Semana 1"
    assert pagina.locator("#plSemanaRango").inner_text() == "4 al 8 de enero"
    pagina.locator("#plAntes").click()
    pagina.locator("#plAntes").click()
    assert (pagina.locator("#plSemanaN").inner_text(), pagina.locator("#plSemanaRango").inner_text()) == (
        "Semana 52 de 2026", "21 al 25 de diciembre")
    assert not errores
    pagina.context.close()

# ---- La vista simple y el arrastre (2026-10-28) ------------------------------------------------------------------


def test_la_vista_simple_sin_alarma_en_la_cabecera(navegador, sitio):
    """Pedido del 2026-10-28: «demasiada información en pantalla». La alarma ya no va en la cabecera del portal (sigue en
    el Inicio y el menú); las cifras van en una línea y la lista de los sin asignar se despliega desde la suya; lo de
    vez en cuando va en «Más»; los paneles de General van plegados y se recuerda cuál se abrió."""
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="general", ancho=1366, alto=768)
    assert pagina.locator("#plAlertaCab, .cab-alerta").count() == 0
    assert pagina.locator(ALERTA_N).inner_text() == "3"
    # Las cifras, en una sola línea y bajas
    cajas = pagina.locator("#plResumen .rc-kpi").evaluate_all("bs => bs.map((b) => b.getBoundingClientRect().toJSON())")
    assert len({round(c["y"]) for c in cajas}) == 1 and max(c["height"] for c in cajas) <= 34, cajas
    # La lista de los sin asignar, plegada hasta tocar su cifra
    alarma = pagina.locator("#plResumen .pl-kpi-alarma")
    assert pagina.locator("#plAlarma").is_hidden() and alarma.get_attribute("aria-expanded") == "false"
    assert (alarma.locator(".rc-kpi-n").inner_text(), alarma.locator(".rc-kpi-et").inner_text()) == ("3", "sin asignar")
    alarma.click()
    assert pagina.locator("#plAlarma").is_visible() and alarma.get_attribute("aria-expanded") == "true"
    assert _alarma(pagina).locator(".pl-alarma-p").all_inner_texts() == list(ACTIVOS.values())
    alarma.click()
    assert pagina.locator("#plAlarma").is_hidden()
    # «Más»: copiar, compartir, imprimir, el estado de los proyectos y el sábado; se cierra al tocar fuera o con Esc
    for id_ in ("#plCopiar", "#plCompartir", "#plImprimir", "#plProyectos", "#plSabado"):
        assert pagina.locator(id_).is_hidden(), id_
    pagina.locator("#plMas").click()
    assert pagina.locator("#plMas").get_attribute("aria-expanded") == "true"
    assert [" ".join(t.split()) for t in pagina.locator("#plMasLista .pl-mas-op").all_inner_texts()] == [
        "Copiar la semana anterior", "Compartir", "Imprimir o PDF", "Estado de los proyectos", "Mostrar el sábado"]
    pagina.keyboard.press("Escape")
    assert pagina.locator("#plMasLista").is_hidden() and pagina.locator("#plMas").get_attribute("aria-expanded") == "false"
    pagina.locator("#plMas").click()
    pagina.locator("#tituloPlan").click()
    assert pagina.locator("#plMasLista").is_hidden()
    pagina.locator("#plMas").click()
    _mas(pagina, "#plProyectos").click()
    assert pagina.locator("#dlgPlProyectos").is_visible() and pagina.locator("#plMasLista").is_hidden()
    pagina.keyboard.press("Escape")
    # Los paneles de General: plegados, con una línea de lo que dicen; el abierto queda abierto al volver
    paneles = pagina.locator("#plGeneral details.pl-panel")
    assert paneles.evaluate_all("ds => ds.map((d) => [d.dataset.panel, d.open])") == [
        ["proyectos", False], ["personal", False], ["vehiculos", False]]
    assert pagina.locator('#plGeneral [data-panel="proyectos"] .pl-panel-res').inner_text() == "0 con alguien · 3 sin asignar"
    pagina.locator('#plGeneral [data-panel="personal"] summary').click()
    # El navegador avisa que se abrió un momento después del clic: recargar antes perdería lo que se guarda ahí
    pagina.wait_for_function("(JSON.parse(localStorage.getItem('quempin_portal_plan')).paneles || []).includes('personal')")
    pagina.reload()
    # Los paneles se pintan antes de que la vista recupere cuál estaba abierto: se espera ese estado en vez de leerlo
    # apenas aparece el primero (en el runner de GitHub se leía [False, False, False]).
    pagina.wait_for_function("""() => [...document.querySelectorAll('#plGeneral details.pl-panel')]
        .map((d) => d.open).join() === 'false,true,false'""")
    assert pagina.locator("#plGeneral details.pl-panel").evaluate_all("ds => ds.map((d) => d.open)") == [False, True, False]
    assert not errores
    pagina.context.close()


def test_arrastrar_un_proyecto_a_una_persona_y_moverlo(navegador, sitio):
    """Pedido del 2026-10-28: en «Por personal», los proyectos activos a la vista para arrastrarlos al día y la persona.
    Lo ya asignado se arrastra a otra casilla y se mueve, en un paso que se deshace."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    lun, mar = _dias_de(lunes)[:2]
    panel = pagina.locator("#plPersonal .pl-arr")
    assert panel.locator("h2").inner_text() == "Proyectos activos"
    # Los tres sin nadie, juntos y primero
    assert panel.locator(".pl-arr-grupo").all_inner_texts()[0].upper() == "SIN ASIGNAR · 3"
    assert panel.locator(".pl-arr-item").evaluate_all("bs => bs.map((b) => b.dataset.clave)") == ["req:907", "req:908", "tag:SOLO"]
    panel.locator('.pl-arr-item[data-clave="req:908"]').drag_to(_celda_personal(pagina, "LC", 0))
    assert pagina.evaluate(JS_PERSONAL)["LC"][0] == ["En obra"]
    assert f"LC va a En obra el lunes {lun.day}" in pagina.locator("#aviso").inner_text()
    assert pagina.locator("#plPop").is_hidden(), "soltar no abre la ventanita"
    # Ya no está entre los sin asignar
    assert panel.locator(".pl-arr-grupo").all_inner_texts()[0].upper() == "SIN ASIGNAR · 2"
    assert panel.locator('.pl-arr-item[data-clave="req:908"] .pl-arr-marca').inner_text() == "1 día"
    # Soltarlo donde ya está no hace nada
    panel.locator('.pl-arr-item[data-clave="req:908"]').drag_to(_celda_personal(pagina, "LC", 0))
    assert pagina.evaluate(JS_PERSONAL)["LC"][0] == ["En obra"]
    # Moverlo a otra persona y otro día
    _celda_personal(pagina, "LC", 0).locator(".pl-chip", has_text="En obra").drag_to(_celda_personal(pagina, "ES", 1))
    vista = pagina.evaluate(JS_PERSONAL)
    assert vista["LC"][0] == [] and vista["ES"][1] == ["En obra"]
    assert (f"ES va a En obra el martes {mar.day} en vez de LC, que ya no va a En obra el lunes {lun.day}"
            in pagina.locator("#aviso").inner_text())
    archivo = f"publicado/planificacion/{semana}/{DISPOSITIVO}.json"
    sobre = _esperar_archivo(pagina, archivo, lambda s: any(x["persona"] == "ES" and x["activa"] for x in s["datos"]["asignaciones"]))
    activas = sorted((x["dia"], x["persona"], x["proyecto"]) for x in sobre["datos"]["asignaciones"] if x["activa"])
    assert activas == [(mar.isoformat(), "ES", "req:908")]
    # Mover también es una sola tanda: un Ctrl Z lo deja como antes de moverlo
    pagina.locator("#tituloPlan").click()
    pagina.keyboard.press("Control+z")
    vista = pagina.evaluate(JS_PERSONAL)
    assert vista["LC"][0] == ["En obra"] and vista["ES"][1] == []
    # El mismo día, a otra persona: va ella en vez de la primera
    _celda_personal(pagina, "LC", 0).locator(".pl-chip").drag_to(_celda_personal(pagina, "NB", 0))
    vista = pagina.evaluate(JS_PERSONAL)
    assert vista["LC"][0] == [] and vista["NB"][0] == ["En obra"]
    assert f"NB va a En obra el lunes {lun.day} en vez de LC." in pagina.locator("#aviso").inner_text()
    assert not errores
    pagina.context.close()


def test_elegir_en_el_panel_y_tocar_las_casillas(navegador, sitio):
    """Sin arrastrar (con el dedo, o para varias casillas seguidas): se toca el proyecto del panel y después las casillas;
    otra vez en la misma lo quita; «Listo» o Esc lo termina y la casilla vuelve a abrir su ventanita."""
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    item = pagina.locator('#plPersonal .pl-arr-item[data-clave="tag:SOLO"]')
    item.click()
    assert pagina.locator('#plPersonal .pl-arr-item[data-clave="tag:SOLO"]').get_attribute("aria-pressed") == "true"
    assert "Toca las casillas donde va Obra sin número" in pagina.locator("#plPersonal .pl-arr-colocando").inner_text()
    _celda_personal(pagina, "MP", 0).click()
    _celda_personal(pagina, "MP", 1).click()
    _celda_personal(pagina, "EV", 1).click()
    vista = pagina.evaluate(JS_PERSONAL)
    assert vista["MP"][:2] == [["Obra sin número"], ["Obra sin número"]] and vista["EV"][1] == ["Obra sin número"]
    assert pagina.locator("#plPop").is_hidden()
    _celda_personal(pagina, "MP", 1).click()
    assert pagina.evaluate(JS_PERSONAL)["MP"][1] == []
    pagina.keyboard.press("Escape")
    assert pagina.locator("#plPersonal .pl-arr-colocando").count() == 0
    assert pagina.locator('#plPersonal .pl-arr-item[aria-pressed="true"]').count() == 0
    _celda_personal(pagina, "MP", 2).click()
    assert pagina.locator("#plPop").is_visible()
    pagina.keyboard.press("Escape")
    # «Listo» también lo termina
    pagina.locator('#plPersonal .pl-arr-item[data-clave="req:907"]').click()
    pagina.locator("#plPersonal .pl-arr-listo").click()
    assert pagina.locator('#plPersonal .pl-arr-item[aria-pressed="true"]').count() == 0
    assert not errores
    pagina.context.close()


def test_arrastrar_un_vehiculo_a_un_proyecto_asignado(navegador, sitio):
    """Observación del equipo del 2026-11-12, «los vehículos deberían poder arrastrarse»: la Quempineta y la RAM van
    arriba del panel. Se sueltan sobre un proyecto ya asignado (o se tocan y después el proyecto; otra vez lo quita); en
    «Por proyecto», sobre la casilla de un proyecto, a todos los que van ese día. Queda en el archivo como en la ventanita."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    lun = _dias_de(lunes)[0]
    # LC va a dos proyectos el lunes y ES a uno
    pagina.locator('#plPersonal .pl-arr-item[data-clave="req:907"]').click()
    _celda_personal(pagina, "LC", 0).click()
    _celda_personal(pagina, "ES", 0).click()
    pagina.locator('#plPersonal .pl-arr-item[data-clave="req:908"]').click()
    _celda_personal(pagina, "LC", 0).click()
    pagina.keyboard.press("Escape")
    panel = pagina.locator("#plPersonal .pl-arr")
    assert panel.locator(".pl-arr-veh").evaluate_all("bs => bs.map((b) => b.dataset.vehiculo)") == ["quempineta", "ram"]
    vehs = lambda celda, proy: celda.locator(".pl-chip", has_text=proy).locator(".pl-veh .n").all_inner_texts()
    # A la casilla de ES, que ese día tiene un solo proyecto
    panel.locator('.pl-arr-veh[data-vehiculo="ram"]').drag_to(_celda_personal(pagina, "ES", 0))
    assert vehs(_celda_personal(pagina, "ES", 0), "Adjudicada sin ficha") == ["RAM"]
    assert "ES va en la RAM a Adjudicada sin ficha" in pagina.locator("#aviso").inner_text()
    assert pagina.locator("#plPop").is_hidden(), "soltar no abre la ventanita"
    # A un proyecto de LC, que tiene dos: solo a ese
    # (a mano y en pasos: al empezar a arrastrar se esconde el «+» de la casilla y el proyecto se corre de lugar)
    panel.locator('.pl-arr-veh[data-vehiculo="quempineta"]').hover()
    pagina.mouse.down()
    pagina.mouse.move(400, 300, steps=3)
    caja = _celda_personal(pagina, "LC", 0).locator(".pl-chip", has_text="En obra").bounding_box()
    pagina.mouse.move(caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2, steps=5)
    pagina.mouse.up()
    assert vehs(_celda_personal(pagina, "LC", 0), "En obra") == ["Quempineta"]
    assert vehs(_celda_personal(pagina, "LC", 0), "Adjudicada sin ficha") == []
    archivo = f"publicado/planificacion/{semana}/{DISPOSITIVO}.json"
    sobre = _esperar_archivo(pagina, archivo, lambda s: len([v for v in s["datos"].get("vehiculos", []) if v["vehiculo"]]) == 2)
    assert sorted((v["dia"], v["persona"], v["proyecto"], v["vehiculo"]) for v in sobre["datos"]["vehiculos"] if v["vehiculo"]) == [
        (lun.isoformat(), "ES", "req:907", "ram"), (lun.isoformat(), "LC", "req:908", "quempineta")]
    # Tocando: la RAM y después el proyecto de ES, donde ya va, la quita
    panel.locator('.pl-arr-veh[data-vehiculo="ram"]').click()
    assert pagina.locator('#plPersonal .pl-arr-veh[data-vehiculo="ram"]').get_attribute("aria-pressed") == "true"
    assert "Toca los proyectos donde va la RAM" in pagina.locator("#plPersonal .pl-arr-colocando").inner_text()
    _celda_personal(pagina, "ES", 0).locator(".pl-chip").click()
    assert vehs(_celda_personal(pagina, "ES", 0), "Adjudicada sin ficha") == []
    assert pagina.locator("#plPop").is_hidden()
    # …y en la casilla de LC, con dos proyectos, pide tocar uno
    _celda_personal(pagina, "LC", 0).locator(".pl-chip", has_text="Adjudicada sin ficha").click()
    assert vehs(_celda_personal(pagina, "LC", 0), "Adjudicada sin ficha") == ["RAM"]
    pagina.keyboard.press("Escape")
    assert pagina.locator('#plPersonal .pl-arr-veh[aria-pressed="true"]').count() == 0
    # Por proyecto: sobre la casilla del proyecto, a todos los que van ese día, en un paso que se deshace
    pagina.locator('.pl-vista[data-vista="proyecto"]').click()
    pagina.locator('#plProyecto .pl-arr-veh[data-vehiculo="quempineta"]').drag_to(_celda_proyecto(pagina, "req:907", 0))
    assert "van en la Quempineta a Adjudicada sin ficha" in pagina.locator("#aviso").inner_text()
    pagina.locator('.pl-vista[data-vista="personal"]').click()
    assert vehs(_celda_personal(pagina, "ES", 0), "Adjudicada sin ficha") == ["Quempineta"]
    assert vehs(_celda_personal(pagina, "LC", 0), "Adjudicada sin ficha") == ["Quempineta"]
    pagina.locator("#tituloPlan").click()
    pagina.keyboard.press("Control+z")
    assert vehs(_celda_personal(pagina, "ES", 0), "Adjudicada sin ficha") == []
    assert vehs(_celda_personal(pagina, "LC", 0), "Adjudicada sin ficha") == ["RAM"]
    assert not errores
    pagina.context.close()


def test_quitar_una_asignacion_con_un_toque(navegador, sitio):
    """Observación del equipo del 2026-11-06, «acceso rápido para eliminar asignaciones»: cada proyecto de una casilla
    lleva una ✕ que lo quita sin abrir la ventanita, en un paso que se deshace y queda en el archivo; con el teclado,
    Supr en la casilla quita lo de ese día y la casilla sigue con el foco. En «Por proyecto» y en General la ✕ va en
    cada persona. Con el mouse se ve solo sobre la casilla."""
    import re
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    lun = _dias_de(lunes)[0]
    # Dos proyectos a LC y uno a ES el lunes, eligiendo en el panel y tocando las casillas
    pagina.locator('#plPersonal .pl-arr-item[data-clave="req:907"]').click()
    _celda_personal(pagina, "LC", 0).click()
    _celda_personal(pagina, "ES", 0).click()
    pagina.locator('#plPersonal .pl-arr-item[data-clave="req:908"]').click()
    _celda_personal(pagina, "LC", 0).click()
    pagina.keyboard.press("Escape")
    assert sorted(pagina.evaluate(JS_PERSONAL)["LC"][0]) == ["Adjudicada sin ficha", "En obra"]
    celda = _celda_personal(pagina, "LC", 0)
    x = celda.locator(".pl-chip", has_text="En obra").locator(".pl-quitar")
    assert x.get_attribute("title") == f"Quitar: LC ya no va a En obra el lunes {lun.day}"
    # Quieta, la ✕ no se ve, tampoco sobre otra parte de la casilla; sobre su proyecto, sí, y el «+» de la esquina se
    # esconde (quedaba encima de la ✕ del último proyecto)
    chip = celda.locator(".pl-chip", has_text="En obra")
    mas = celda.locator(".pl-mas.flota")
    oculta = "e => getComputedStyle(e).opacity === '0' && getComputedStyle(e).pointerEvents === 'none'"
    pagina.mouse.move(1, 1)
    pagina.wait_for_function(oculta, arg=x.element_handle())
    celda.hover(position={"x": 4, "y": 4})
    pagina.wait_for_function(oculta, arg=x.element_handle())
    pagina.wait_for_function("e => getComputedStyle(e).opacity === '1'", arg=mas.element_handle())
    chip.hover()
    pagina.wait_for_function("e => getComputedStyle(e).opacity === '1'", arg=x.element_handle())
    pagina.wait_for_function(oculta, arg=mas.element_handle())
    x.click()
    assert pagina.evaluate(JS_PERSONAL)["LC"][0] == ["Adjudicada sin ficha"]
    assert pagina.locator("#plPop").is_hidden(), "la ✕ no abre la ventanita"
    assert f"LC ya no va a En obra el lunes {lun.day}" in pagina.locator("#aviso").inner_text()
    archivo = f"publicado/planificacion/{semana}/{DISPOSITIVO}.json"
    _esperar_archivo(pagina, archivo, lambda s: any(a["persona"] == "LC" and a["proyecto"] == "req:908" and not a["activa"]
                                                   for a in s["datos"]["asignaciones"]))
    # Se deshace como cualquier cambio
    pagina.locator("#tituloPlan").click()
    pagina.keyboard.press("Control+z")
    assert sorted(pagina.evaluate(JS_PERSONAL)["LC"][0]) == ["Adjudicada sin ficha", "En obra"]
    # Supr en la casilla quita los dos del día, en un solo paso, y la casilla sigue con el foco
    assert celda.get_attribute("aria-keyshortcuts") == "Delete"
    celda.focus()
    pagina.keyboard.press("Delete")
    assert pagina.evaluate(JS_PERSONAL)["LC"][0] == []
    assert re.search(rf"LC ya no va a (Adjudicada sin ficha y En obra|En obra y Adjudicada sin ficha) el lunes {lun.day}\.",
                     pagina.locator("#aviso").inner_text())
    assert pagina.evaluate("() => document.activeElement.dataset.ancla") == f"p|LC|{lun.isoformat()}"
    pagina.keyboard.press("Delete")          # vacía: no pasa nada
    assert pagina.evaluate(JS_PERSONAL)["ES"][0] == ["Adjudicada sin ficha"]
    # Por proyecto: la ✕ en la persona
    pagina.locator('.pl-vista[data-vista="proyecto"]').click()
    c907 = _celda_proyecto(pagina, "req:907", 0)
    assert c907.locator(".pl-per").all_inner_texts() == ["ES"]
    c907.locator(".pl-per", has_text="ES").hover()
    c907.locator(".pl-per", has_text="ES").locator(".pl-quitar").click()
    assert c907.locator(".pl-per").count() == 0
    assert pagina.locator("#plPop").is_hidden()
    assert f"ES ya no va a Adjudicada sin ficha el lunes {lun.day}" in pagina.locator("#aviso").inner_text()
    pagina.locator("#tituloPlan").click()
    pagina.keyboard.press("Control+z")
    # En General, también
    pagina.locator('.pl-vista[data-vista="general"]').click()
    _dia_general(pagina, 0)
    bloque = pagina.locator(f'#plGeneral [data-ancla="j|req:907|{lun.isoformat()}"]')
    assert bloque.locator(".pl-per").all_inner_texts() == ["ES"]
    bloque.locator(".pl-per").hover()
    bloque.locator(".pl-quitar").click()
    assert pagina.locator(f'#plGeneral [data-ancla="j|req:907|{lun.isoformat()}"]').count() == 0
    assert pagina.locator("#plPop").is_hidden()
    assert not errores
    pagina.context.close()


def test_arrastrar_personas_por_proyecto_y_en_general(navegador, sitio):
    """«Algo similar para las otras formas»: en «Por proyecto» se arrastra a las personas del panel al proyecto y el día
    (y de un proyecto a otro); en General, a alguien sin proyecto a un proyecto de ese día."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    _, lunes = _semana_de(date.today())
    panel = pagina.locator("#plProyecto .pl-arr")
    assert panel.locator("h2").inner_text() == "Personal"
    assert panel.locator(".pl-arr-item").evaluate_all("bs => bs.map((b) => b.dataset.persona)") == ["NB", "ES", "LC", "CM", "MP", "EV", "RL"]
    panel.locator('.pl-arr-item[data-persona="ES"]').drag_to(_celda_proyecto(pagina, "req:908", 2))
    assert _celda_proyecto(pagina, "req:908", 2).locator(".pl-per").all_inner_texts() == ["ES"]
    assert panel.locator('.pl-arr-item[data-persona="ES"] .s').inner_text() == "1 de 5 días"
    # De un proyecto a otro el mismo día: cambia de proyecto
    _celda_proyecto(pagina, "req:908", 2).locator(".pl-per").drag_to(_celda_proyecto(pagina, "tag:SOLO", 2))
    assert _celda_proyecto(pagina, "req:908", 2).locator(".pl-per").count() == 0
    assert _celda_proyecto(pagina, "tag:SOLO", 2).locator(".pl-per").all_inner_texts() == ["ES"]
    assert "ES cambia de En obra a Obra sin número" in pagina.locator("#aviso").inner_text()
    # En General: alguien sin proyecto el miércoles, al proyecto de ese día
    pagina.locator('.pl-vista[data-vista="general"]').click()
    mie = _dias_de(lunes)[2].isoformat()
    _dia_general(pagina, 2)
    bloque = pagina.locator(f'#plGeneral [data-ancla="j|tag:SOLO|{mie}"]')
    pagina.locator(f'#plGeneral [data-ancla="p|NB|{mie}"]').drag_to(bloque)
    assert bloque.locator(".pl-per").all_inner_texts() == ["NB", "ES"]
    assert pagina.locator(f'#plGeneral [data-ancla="p|NB|{mie}"]').count() == 0
    assert not errores
    pagina.context.close()


def test_diez_vueltas_dias_grupos_jornadas_y_compartir(navegador, sitio):
    """Revisión de usabilidad del 2026-10-29 (diez vueltas): hoy lleva su marca y los días que ya pasaron van apagados,
    también en «Qué días»; una casilla vacía muestra «Asignar» solo al pasar el mouse; «Por proyecto» titula sus grupos
    con su cuenta y «Sin trabajo esta semana» es un botón; las dos cifras de días son una sola, en jornadas; y en
    Compartir, quien no tiene nada en la semana va en una línea."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    hoy = date.today().weekday()
    clases = pagina.locator("#plProyecto thead th[data-dia]").evaluate_all("ths => ths.map((t) => t.className)")
    assert clases == ["hoy" if i == hoy else "pasado" if i < hoy else "" for i in range(len(clases))]
    # «Asignar» aparece al pasar encima; quieta, la casilla vacía muestra solo el «+»
    asignar = _celda_proyecto(pagina, "req:907", 2).locator(".pl-mas > span")
    assert asignar.is_hidden()
    _celda_proyecto(pagina, "req:907", 2).hover()
    assert asignar.is_visible()
    # Los tres activos sin nadie: un solo grupo, sin título
    assert pagina.locator("#plProyecto tr.pl-sep").count() == 0
    _celda_proyecto(pagina, "req:908", 0).click()
    pop = pagina.locator("#plPop")
    assert pop.locator(".pl-dia-op.hoy").count() == (1 if hoy < 5 else 0)
    assert pop.locator(".pl-dia-op.pasado").count() == min(hoy, 5)
    pop.locator('input[data-op="c|LC"]').check()
    pagina.keyboard.press("Escape")
    pagina.locator('#plProyecto tr[data-clave="tag:SOLO"] .pl-pausar').click()
    grupos = pagina.locator("#plProyecto tr.pl-sep th").evaluate_all(
        "ths => ths.map((t) => [t.firstChild.textContent, (t.querySelector('.pl-sep-n') || {}).textContent])")
    assert grupos == [["Sin nadie asignado esta semana", "1"], ["Con alguien asignado", "1"], ["Sin trabajo esta semana", "1"]]
    claves = pagina.locator("#plProyecto tr[data-clave]").evaluate_all("ts => ts.map((t) => t.dataset.clave)")
    assert claves == ["req:907", "req:908", "tag:SOLO"]
    assert pagina.locator("#plProyecto .pl-pausar").evaluate_all("bs => bs.map((b) => b.tagName)") == ["BUTTON", "BUTTON"]
    # Una cifra para el equipo: cada persona cada día es una jornada
    jornadas = len(_registro()["personal"]) * 5
    kpi = pagina.locator("#plResumen .rc-kpi").nth(2)
    assert (kpi.locator(".rc-kpi-n").inner_text(), kpi.locator(".rc-kpi-et").inner_text()) == ("1", f"de {jornadas} jornadas con proyecto")
    assert kpi.locator(".rc-kpi-sub").text_content() == f"Cada persona cada día es una jornada: {jornadas - 1} libres (sin proyecto)"
    assert pagina.locator("#plResumen .rc-kpi").count() == 4
    # Compartir: NB no tiene nada en la semana, una línea; LC, día por día
    _mas(pagina, "#plCompartir").click()
    texto = pagina.locator("#plTextoArea").input_value()
    assert "\n*NB*\n• Sin proyectos esta semana\n" in texto and "\n*LC*\n• Lun " in texto
    assert not errores
    pagina.context.close()


def test_diez_vueltas_en_el_telefono(navegador, sitio):
    """En el teléfono General muestra un día a la vez, como las tablas (hoy, si es de la semana); la lista para asignar
    tocando va plegada en una línea hasta pedirla; «Agregar» dice su nombre y «Esta semana» no se muestra en ella."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="general", ancho=390, alto=844, movil=True)
    hoy = date.today().weekday()
    a_la_vista = "ds => ds.filter((d) => d.getClientRects().length).map((d) => d.dataset.dia)"
    assert pagina.locator("#plDiasMovil").is_visible()
    assert pagina.locator("#plGeneral .pl-dia").evaluate_all(a_la_vista) == [str(hoy if hoy < 5 else 0)]
    pagina.locator("#plDiasMovil .pl-dia-tab").nth(1).click()
    assert pagina.locator("#plGeneral .pl-dia").evaluate_all(a_la_vista) == ["1"]
    assert pagina.locator("#plAgregar").inner_text().strip() == "Agregar"
    assert pagina.locator("#plHoy").is_hidden()
    pagina.locator('.pl-vista[data-vista="personal"]').click()
    panel = pagina.locator("#plPersonal .pl-arr")
    abrir = panel.locator(".pl-arr-abrir")
    assert panel.locator(".pl-arr-lista").is_hidden() and abrir.get_attribute("aria-expanded") == "false"
    assert abrir.inner_text().strip() == "Asignar tocando"
    abrir.click()
    assert panel.locator(".pl-arr-lista").is_visible() and panel.locator(".pl-arr-pista-corta").is_visible()
    panel.locator('.pl-arr-item[data-clave="req:908"]').click()
    assert "Toca las casillas donde va En obra" in panel.locator(".pl-arr-colocando").inner_text()
    # Ocultar la lista también deja de poner lo elegido
    panel.locator(".pl-arr-abrir").click()
    assert panel.locator(".pl-arr-lista").is_hidden() and panel.locator(".pl-arr-colocando").count() == 0
    d = pagina.evaluate(JS_DESBORDES)
    assert d["doc"] <= 390 and not d["fuera"], d
    assert not errores
    pagina.context.close()


def test_diez_vueltas_vehiculo_ocupado_y_semana_vacia(navegador, sitio):
    """Un vehículo que ese día va a otra parte dice quién lo lleva (antes, solo un punto naranjo). Una semana que viene
    sin nada ofrece «Copiar la semana N» a la vista (antes, solo en «Más»), y se va al copiar; una que ya pasó, no."""
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    semana, lunes = _semana_con_vehiculos(pagina)
    _celda_proyecto(pagina, "req:908", 1).click()
    ram = pagina.locator('#plPop [data-op="v|ES|ram"]')
    assert "ocupado" in ram.get_attribute("class") and ram.locator(".pl-veh-op-q").inner_text() == "la lleva NB"
    assert pagina.locator('#plPop [data-op="v|ES|quempineta"] .pl-veh-op-q').inner_text() == "la lleva MP"     # a Obra sin número
    pagina.keyboard.press("Escape")
    # Esta semana tiene algo: sin franja. La siguiente está vacía: «Copiar la semana N»
    assert pagina.locator("#plSemanaVacia").is_hidden()
    pagina.locator("#plDespues").click()
    franja = pagina.locator("#plSemanaVacia")
    franja.wait_for()
    numero = lunes.isocalendar()[1]
    assert franja.locator("button").inner_text() == f"Copiar la semana {numero}"
    franja.locator("button").click()
    pagina.wait_for_function("document.getElementById('aviso').textContent.startsWith('Se copiaron')")
    assert pagina.locator("#plSemanaVacia").is_hidden()
    siguiente = (lunes + timedelta(days=7)).isocalendar()
    _esperar_archivo(pagina, f"publicado/planificacion/{siguiente[0]}-W{siguiente[1]:02d}/{DISPOSITIVO}.json",
                     lambda sobre: len(sobre["datos"]["asignaciones"]) == 7)
    # Una semana que ya pasó, aunque esté vacía, no la ofrece
    pagina.locator("#plHoy").click()
    pagina.locator("#plAntes").click()
    pagina.locator("#plProyecto .pl-celda").first.wait_for()
    assert pagina.locator("#plSemanaVacia").is_hidden()
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [390, 1024, 1366])
def test_la_planificacion_cabe_sin_desbordes(navegador, sitio, ancho):
    movil = ancho < 760
    for vista in ("general", "personal", "proyecto"):
        pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista=vista, ancho=ancho, alto=844, movil=movil)
        pagina.locator(f"#pl{vista.capitalize()}").wait_for()
        d = pagina.evaluate(JS_DESBORDES)
        assert d["doc"] <= ancho and not d["fuera"], (vista, d)
        derecha = pagina.evaluate("""() => Math.max(...[...document.querySelectorAll('#vistaPlan *')]
            .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))""")
        assert derecha <= ancho + 0.5, (vista, derecha)
        chicos = pagina.evaluate("""() => [...document.querySelectorAll('#vistaPlan *')]
            .filter((e) => e.getClientRects().length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
            .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12).map((e) => e.className || e.tagName)""")
        assert not chicos, (vista, chicos)
        if vista != "general":
            # En el teléfono las tablas muestran un día a la vez, el de hoy si es de la semana; arriba se elige otro
            visibles = pagina.locator(f"#pl{vista.capitalize()} thead th[data-dia]").evaluate_all(
                "ths => ths.filter((t) => t.getClientRects().length).length")
            assert visibles == (1 if movil else 5), (vista, visibles)
            assert pagina.locator("#plDiasMovil").is_visible() == movil
        # La ventanita queda dentro de la pantalla
        pagina.locator("#plGeneral .pl-nuevo >> visible=true" if vista == "general" else f"#pl{vista.capitalize()} .pl-celda >> visible=true").first.click()
        caja = pagina.locator("#plPop").bounding_box()
        assert caja["x"] >= 0 and caja["x"] + caja["width"] <= ancho and caja["y"] >= 0 and caja["y"] + caja["height"] <= 844, (vista, caja)
        # Dentro de ella, con la franja «Qué días» y toda la semana elegida, nada se sale de lado ni queda con letra chica
        pagina.locator('#plPop [data-op="d|todos"]').click()
        dentro = pagina.evaluate("""() => { const r = document.getElementById('plPop').getBoundingClientRect();
            const vis = [...document.querySelectorAll('#plPop *')].filter((e) => e.getClientRects().length);
            return { fuera: vis.filter((e) => e.getBoundingClientRect().right > r.right + 0.5).map((e) => e.className || e.tagName),
                     chicos: vis.filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
                       .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12).map((e) => e.className || e.tagName) }; }""")
        assert not dentro["fuera"] and not dentro["chicos"], (vista, dentro)
        if movil:
            assert pagina.evaluate("parseFloat(getComputedStyle(document.querySelector('#plPop .pl-otra input, #plPop .pl-buscar') || document.body).fontSize)") >= 16
            # El aviso de un cambio (con «Deshacer») no tapa la ventanita, que sube desde abajo
            if vista != "general":
                pagina.locator("#plPop .pl-ops input:not([disabled])").first.click()
                pagina.locator("#aviso").wait_for()
                assert pagina.locator("#aviso").bounding_box()["y"] + pagina.locator("#aviso").bounding_box()["height"] <= pagina.locator("#plPop").bounding_box()["y"]
        assert not errores
        pagina.context.close()

# ---- Vehículos de la Planificación (2026-10-25) -------------------------------------------------------------------


def test_los_vehiculos_en_el_registro_y_en_el_esquema():
    """Pedido del 2026-10-25: a una persona en un proyecto se le asigna uno de los dos vehículos de la empresa, la
    Quempineta o la RAM. Salen del registro del portal, y el esquema del archivo de la semana acepta los mismos."""
    reg = _registro()
    assert [(v["id"], v["nombre"], v["articulo"]) for v in reg["vehiculos"]] == [("quempineta", "Quempineta", "la"), ("ram", "RAM", "la")]
    esquema = json.loads((RAIZ / "Sistema Intercambio" / "esquemas" / "publicaciones" / "planificacion-semana.json").read_text(encoding="utf-8"))
    assert esquema["properties"]["vehiculos"]["items"]["properties"]["vehiculo"]["enum"] == [""] + [v["id"] for v in reg["vehiculos"]]
    assert "vehiculos" not in esquema["required"], "los archivos de antes del 2026-10-25 no lo traen"


def test_asignar_un_vehiculo_a_una_persona_en_un_proyecto(navegador, sitio):
    """Un toque en la ventanita de la casilla: bajo cada persona asignada, la Quempineta y la RAM. Se ve en las tres
    vistas y en el resumen de arriba, queda en la carpeta, otro toque lo quita y quitar a la persona también se lo quita."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    semana, lunes = _semana_de(date.today())
    lun = lunes.isoformat()
    pop = pagina.locator("#plPop")
    aviso = lambda: pagina.locator("#aviso").inner_text()
    celda = _celda_proyecto(pagina, "req:908", 0)
    # Sin vehículos asignados, el resumen los cuenta libres
    kpi = pagina.locator("#plResumen .pl-kpi-veh")
    assert (kpi.locator(".rc-kpi-n").inner_text(), kpi.locator(".rc-kpi-et").inner_text()) == ("0", "vehículos en uso")
    assert kpi.locator(".rc-kpi-sub").inner_text() == "Quempineta libre · RAM libre"
    celda.click()
    assert pop.locator(".pl-op-veh").count() == 0, "solo bajo quienes van"
    pop.locator('input[data-op="c|ES"]').check()
    pop.locator('input[data-op="c|LC"]').check()
    assert pop.locator("li:has(input[data-op='c|ES']) .pl-veh-op").all_inner_texts() == ["Quempineta", "RAM"]
    assert pop.locator('[data-op="v|ES|ram"]').get_attribute("aria-pressed") == "false"
    pop.locator('[data-op="v|ES|ram"]').click()
    assert aviso().startswith(f"ES va en la RAM a En obra el lunes {lunes.day}.") and "Ojo" not in aviso()
    assert pop.locator('[data-op="v|ES|ram"]').get_attribute("aria-pressed") == "true"
    assert pagina.evaluate("document.activeElement.dataset.op") == "v|ES|ram", "el foco sigue en el botón al repintarse"
    assert _vehs(celda) == [["RAM", "ES"]]
    # Los dos en la RAM: una sola etiqueta, sin iniciales
    pop.locator('[data-op="v|LC|ram"]').click()
    assert _vehs(celda) == [["RAM", ""]]
    # Queda en el archivo de este navegador y cumple el esquema del catálogo
    archivo = f"publicado/planificacion/{semana}/{DISPOSITIVO}.json"
    sobre = _esperar_archivo(pagina, archivo, lambda s: len(s["datos"].get("vehiculos", [])) == 2)
    assert sorted((x["dia"], x["persona"], x["proyecto"], x["vehiculo"], x["por"]) for x in sobre["datos"]["vehiculos"]) == [
        (lun, "ES", "req:908", "ram", "LC"), (lun, "LC", "req:908", "ram", "LC")]
    esquemas = _cargar("esquemas_para_test_portal", RAIZ / "Sistema Intercambio" / "esquemas.py")
    assert esquemas.validar_publicacion("planificacion-semana", sobre) == []
    # Otro toque lo quita; elegir el otro lo cambia
    pop.locator('[data-op="v|ES|ram"]').click()
    assert aviso().startswith(f"ES ya no lleva la RAM a En obra el lunes {lunes.day}.")
    assert _vehs(celda) == [["RAM", "LC"]]
    pop.locator('[data-op="v|ES|quempineta"]').click()
    assert _vehs(celda) == [["Quempineta", "ES"], ["RAM", "LC"]]
    pagina.keyboard.press("Escape")
    # Por personal: el vehículo va junto al proyecto de ese día
    pagina.locator('.pl-vista[data-vista="personal"]').click()
    assert _vehs(_celda_personal(pagina, "ES", 0)) == [["Quempineta", ""]]
    assert pagina.evaluate(JS_PERSONAL)["ES"][0] == ["En obra"]
    assert "en la Quempineta" in _celda_personal(pagina, "ES", 0).locator(".pl-chip").get_attribute("title")
    # El resumen: cuántos vehículos se usan y cuántos días cada uno; lleva a «Vehículos en la semana», en General
    assert kpi.locator(".rc-kpi-n").inner_text() == "2" and kpi.locator(".rc-kpi-sub").inner_text() == "Quempineta 1 día · RAM 1 día"
    kpi.click()
    assert pagina.locator('.pl-vista[data-vista="general"]').get_attribute("aria-pressed") == "true"
    assert pagina.locator("#plVehiculos h2").inner_text() == "Vehículos en la semana"
    assert pagina.locator("#plVehiculos").evaluate("e => e.classList.contains('resaltada')")
    panel = pagina.evaluate(JS_PANEL_VEHICULOS)
    assert panel[0] == [lun, {"quempineta": "En obra ES", "ram": "En obra LC"}]
    assert all(dia[1] == {"quempineta": "Libre", "ram": "Libre"} for dia in panel[1:]) and len(panel) == 5
    assert pagina.locator("#plVehiculos tfoot td").all_inner_texts() == ["1 de 5 días", "1 de 5 días"]
    _dia_general(pagina, 0)
    assert _vehs(pagina.locator(f'#plGeneral .pl-bloque[data-ancla="j|req:908|{lun}"]')) == [["Quempineta", "ES"], ["RAM", "LC"]]
    # Un uso del panel abre ese proyecto ese día; quitar a LC le quita también la RAM, y deshacer devuelve las dos cosas
    pagina.locator("#plVehiculos .pl-veh-uso", has_text="LC").click()
    assert pagina.locator("#plPopTit").inner_text() == "En obra" and pop.locator('[data-op="v|LC|ram"]').get_attribute("aria-pressed") == "true"
    pop.locator('input[data-op="c|LC"]').uncheck()
    assert pagina.evaluate(JS_PANEL_VEHICULOS)[0][1]["ram"] == "Libre"
    _esperar_archivo(pagina, archivo, lambda s: any(x["persona"] == "LC" and x["vehiculo"] == "" for x in s["datos"]["vehiculos"]))
    pagina.keyboard.press("Escape")
    pagina.keyboard.press("Control+z")
    assert pagina.evaluate(JS_PANEL_VEHICULOS)[0][1]["ram"] == "En obra LC"
    # Volver a asignar a alguien empieza sin vehículo
    pagina.locator(f'#plGeneral .pl-bloque[data-ancla="j|req:908|{lun}"]').click()
    pop.locator('input[data-op="c|LC"]').uncheck()
    pop.locator('input[data-op="c|LC"]').check()
    assert pop.locator('[data-op="v|LC|ram"]').get_attribute("aria-pressed") == "false"
    assert not errores
    pagina.context.close()


def test_vehiculo_varios_dias_cambiar_y_copiar_la_semana(navegador, sitio):
    """Con varios días elegidos, el vehículo vale para todos los días en que la persona va (a medias si lo lleva solo
    algunos). Al pasarla a otro proyecto, o poner a otra en su lugar, el vehículo se va con ella; copiar la semana
    anterior copia también los vehículos."""
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    _, lunes = _semana_de(date.today())
    pop = pagina.locator("#plPop")
    aviso = lambda: pagina.locator("#aviso").inner_text()
    _celda_personal(pagina, "MP", 0).click()
    pop.locator('[data-op="d|todos"]').click()
    pop.locator('input[data-op="c|req:907"]').check()
    pop.locator('[data-op="v|req:907|quempineta"]').click()
    assert aviso().startswith("MP va en la Quempineta a Adjudicada sin ficha de lunes a viernes.")
    assert [_vehs(_celda_personal(pagina, "MP", i)) for i in range(5)] == [[["Quempineta", ""]]] * 5
    # Solo el lunes, la RAM: con toda la semana, los dos quedan a medias; tocar uno lo pone todos los días
    pop.locator('[data-op="d|solo"]').click()
    pop.locator('[data-op="v|req:907|ram"]').click()
    pop.locator('[data-op="d|todos"]').click()
    estados = lambda: [pop.locator(f'[data-op="v|req:907|{v}"]').get_attribute("aria-pressed") for v in ("quempineta", "ram")]
    assert estados() == ["mixed", "mixed"]
    pop.locator('[data-op="v|req:907|quempineta"]').click()
    assert estados() == ["true", "false"] and aviso().startswith("MP va en la Quempineta a Adjudicada sin ficha el lunes")
    # «Cambiar»: MP pasa a En obra los cinco días y la Quempineta se va con ella
    pop.locator('[data-op="k|req:907"]').click()
    pop.locator('[data-op="x|req:908"]').click()
    assert pagina.evaluate(JS_PERSONAL)["MP"] == [["En obra"]] * 5
    assert [_vehs(_celda_personal(pagina, "MP", i)) for i in range(5)] == [[["Quempineta", ""]]] * 5
    pagina.keyboard.press("Escape")
    # Desde el proyecto, EV va en vez de MP el lunes: también se lleva la Quempineta
    pagina.locator('.pl-vista[data-vista="proyecto"]').click()
    _celda_proyecto(pagina, "req:908", 0).click()
    pop.locator('[data-op="k|MP"]').click()
    pop.locator('[data-op="x|EV"]').click()
    assert pop.locator('[data-op="v|EV|quempineta"]').get_attribute("aria-pressed") == "true"
    assert _vehs(_celda_proyecto(pagina, "req:908", 0)) == [["Quempineta", ""]]
    # Un solo Ctrl Z deshace el reemplazo entero, con el vehículo
    pagina.keyboard.press("Escape")
    pagina.keyboard.press("Control+z")
    assert _celda_proyecto(pagina, "req:908", 0).locator(".pl-per").all_inner_texts() == ["MP"]
    assert _vehs(_celda_proyecto(pagina, "req:908", 0)) == [["Quempineta", ""]]
    # La semana que viene: copiar esta trae las asignaciones con sus vehículos
    pagina.locator("#plDespues").click()
    pagina.locator("#plProyecto .pl-celda").first.wait_for()
    _mas(pagina, "#plCopiar").click()
    pagina.wait_for_function("document.getElementById('aviso').textContent.startsWith('Se copiaron')")
    assert aviso().startswith(f"Se copiaron 5 asignaciones de la semana {lunes.isocalendar()[1]} (con sus vehículos).")
    assert [_vehs(_celda_proyecto(pagina, "req:908", i)) for i in range(5)] == [[["Quempineta", ""]]] * 5
    assert not errores
    pagina.context.close()


def test_un_vehiculo_en_dos_lugares_a_la_vez_se_avisa_y_se_comparte(navegador, sitio):
    """Personas que no comparten proyecto ese día en el mismo vehículo: está en dos lugares a la vez. La ventanita lo
    dice antes de elegirlo, el aviso al elegirlo, y el resumen y «Vehículos en la semana» lo marcan en naranjo (no se
    impide). Compartir e imprimir dicen en qué vehículo va cada uno."""
    from datetime import timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    semana, lunes = _semana_con_vehiculos(pagina)
    lun, mar = lunes.isoformat(), (lunes + timedelta(days=1)).isoformat()
    pop = pagina.locator("#plPop")
    kpi = pagina.locator("#plResumen .pl-kpi-veh")
    # Lo de otro computador: el martes la RAM está en En obra (ES) y en Adjudicada sin ficha (NB)
    assert kpi.get_attribute("data-nivel") == "warn"
    assert kpi.locator(".rc-kpi-sub").inner_text() == f"La RAM en 2 lugares el martes {(lunes + timedelta(days=1)).day}"
    # Esas casillas llevan la etiqueta en naranjo, y su título dice dónde más está
    choque = _celda_proyecto(pagina, "req:907", 1).locator(".pl-veh")
    assert "choque" in choque.get_attribute("class")
    assert choque.get_attribute("title").startswith(f"La RAM va a 2 lugares a la vez el martes {(lunes + timedelta(days=1)).day}: Adjudicada sin ficha (NB) y En obra (ES)")
    assert _celda_proyecto(pagina, "req:908", 0).locator(".pl-veh.choque").count() == 0
    # En la ventanita, la RAM ya va a otra parte ese día: un punto naranjo y su título dicen dónde
    _celda_proyecto(pagina, "tag:SOLO", 3).click()
    pop.locator('input[data-op="c|CM"]').check()
    assert "ocupado" not in pop.locator('[data-op="v|CM|ram"]').get_attribute("class"), "el jueves la RAM está libre"
    pagina.keyboard.press("Escape")
    _celda_proyecto(pagina, "tag:SOLO", 0).click()
    ram = pop.locator('[data-op="v|MP|ram"]')
    assert "ocupado" in ram.get_attribute("class") and "la RAM también va a En obra (ES y LC)" in ram.get_attribute("title")
    ram.click()
    assert f"MP va en la RAM a Obra sin número el lunes {lunes.day}. Ojo: el lunes {lunes.day} la RAM también va a En obra (ES y LC)." in pagina.locator("#aviso").inner_text()
    assert kpi.locator(".rc-kpi-sub").inner_text() == f"La RAM en 2 lugares el lunes {lunes.day} y 1 más"
    pagina.keyboard.press("Escape")
    kpi.click()
    lunes_ram = pagina.locator(f'#plVehiculos tr[data-iso="{lun}"] td[data-veh="ram"]')
    assert lunes_ram.get_attribute("data-nivel") == "warn" and "En 2 lugares a la vez" in lunes_ram.inner_text()
    assert pagina.evaluate(JS_PANEL_VEHICULOS)[0][1]["ram"] == "En obra ES LC / Obra sin número MP"
    # Si ES también va a Obra sin número en la RAM, viajan juntos: ya no está en dos lugares el lunes
    _dia_general(pagina, 0)
    pagina.locator(f'#plGeneral .pl-bloque[data-ancla="j|tag:SOLO|{lun}"]').click()
    pop.locator('input[data-op="c|ES"]').check()
    pop.locator('[data-op="v|ES|ram"]').click()
    assert "Ojo" not in pagina.locator("#aviso").inner_text()
    pagina.keyboard.press("Escape")
    assert lunes_ram.get_attribute("data-nivel") is None
    assert pagina.locator(f'#plVehiculos tr[data-iso="{mar}"] td[data-veh="ram"]').get_attribute("data-nivel") == "warn"
    # Compartir: por persona, en qué vehículo va a cada proyecto; por día, quiénes van y en qué
    _mas(pagina, "#plCompartir").click()
    texto = pagina.locator("#plTextoArea").input_value()
    linea_es = next(x for x in texto.split("\n*ES*\n")[1].split("\n") if x.startswith(f"• Lun {lunes.day}:"))
    assert "En obra, con LC, en la RAM" in linea_es and "Obra sin número" in linea_es and linea_es.endswith("en la RAM")
    pagina.locator('#plTextoModo [data-modo="dia"]').click()
    texto = pagina.locator("#plTextoArea").input_value()
    assert "• En obra: ES, LC (RAM)" in texto and "• Obra sin número: ES, MP (RAM)" in texto
    assert f"• Adjudicada sin ficha: NB (RAM)" in texto
    pagina.keyboard.press("Escape")
    # Imprimir: el vehículo en la tabla y en la hoja de cada persona (su columna), y abajo dónde va cada uno
    pagina.evaluate("""() => { window.print = () => {
        window.__tabla = [...document.querySelectorAll('#plDoc .pl-doc-t tbody tr')].map((tr) => [...tr.cells].map((c) => c.innerText.trim()));
        window.__notas = [...document.querySelectorAll('#plDoc .pl-doc-notas li')].map((li) => li.innerText);
        window.__hoja = [...document.querySelectorAll('#plDoc .pl-doc-hoja')].map((s) => [s.querySelector('h1').textContent,
            [...s.querySelectorAll('thead th')].map((th) => th.textContent), [...s.querySelectorAll('td.veh')].map((td) => td.textContent)]);
        window.dispatchEvent(new Event('afterprint'));
    }; }""")
    _mas(pagina, "#plImprimir").click()
    pagina.locator("#plExpImprimir").click()
    tabla = pagina.evaluate("window.__tabla")
    assert "Vehículo: RAM" in tabla[1][1], tabla[1]           # ES, el lunes
    assert "Vehículo: RAM" in tabla[4][1] and "Vehículo: Quempineta" in tabla[4][2], tabla[4]    # MP: se pasó a la RAM el lunes
    notas = pagina.evaluate("window.__notas")
    assert any(n.startswith("Quempineta: ") and "Obra sin número (MP)" in n for n in notas), notas
    ram = next(n for n in notas if n.startswith("RAM: "))
    assert f"lun {lunes.day}, En obra (ES y LC) y Obra sin número (ES y MP);" in ram, ram
    assert ram.endswith(f"mar {(lunes + timedelta(days=1)).day}, Adjudicada sin ficha (NB) y En obra (ES) — en 2 lugares a la vez."), ram
    hojas = {h[0]: h for h in pagina.evaluate("window.__hoja")}
    assert hojas["ES"][1] == ["Día", "Proyecto", "Lugar", "Con quién va", "Vehículo"] and hojas["ES"][2].count("RAM") == 3
    assert not errores
    pagina.context.close()


def test_un_cambio_mientras_se_guarda_tambien_llega_a_la_carpeta(navegador, sitio):
    """Revisión del 2026-10-25: un cambio hecho mientras se escribía el anterior quedaba fuera del archivo hasta el
    próximo cambio (y si se cerraba la página, se perdía), justo lo que pasa al marcar a alguien y tocar su vehículo
    enseguida. Ahora vuelve a la lista y se guarda en la vuelta siguiente."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    semana, _ = _semana_de(date.today())
    # Cada escritura tarda un segundo: el segundo cambio llega con la primera a medio escribir
    pagina.evaluate("""() => { const original = FileSystemFileHandle.prototype.createWritable;
        FileSystemFileHandle.prototype.createWritable = async function (...a) { await new Promise((r) => setTimeout(r, 1000)); return original.apply(this, a); }; }""")
    pop = pagina.locator("#plPop")
    _celda_proyecto(pagina, "req:908", 0).click()
    pop.locator('input[data-op="c|ES"]').check()
    pagina.wait_for_timeout(650)          # la primera escritura empezó a los 450 ms y espera su segundo
    pop.locator('[data-op="v|ES|ram"]').click()
    archivo = f"publicado/planificacion/{semana}/{DISPOSITIVO}.json"
    sobre = _esperar_archivo(pagina, archivo, lambda s: [x["vehiculo"] for x in s["datos"].get("vehiculos", [])] == ["ram"])
    assert [(x["persona"], x["activa"]) for x in sobre["datos"]["asignaciones"]] == [("ES", True)]
    pagina.wait_for_function("document.getElementById('plFrescura').textContent === 'Guardado · OneDrive lo lleva al equipo'")
    assert pagina.evaluate("localStorage.getItem('quempin_portal_plan_pendiente')") is None, "nada quedó esperando"
    assert not errores
    pagina.context.close()


def test_lo_que_cambia_un_colega_llega_solo_y_se_ve_quien_fue(navegador, sitio):
    """Pedido del 2026-11-02: que el equipo pueda trabajar a la vez. Sin tocar nada, lo que llega a la carpeta aparece en
    segundos (antes, hasta 35), iluminado y con quién fue. Lo propio no se anuncia como ajeno."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    _celda_personal(pagina, "LC", 0).click()
    pagina.locator('#plPop input[data-op="c|req:908"]').check()
    pagina.keyboard.press("Escape")
    _esperar_archivo(pagina, f"publicado/planificacion/{semana}/{DISPOSITIVO}.json", lambda s: len(s["datos"]["asignaciones"]) == 1)
    pagina.wait_for_timeout(3500)      # una vuelta de lectura completa con lo propio ya en la carpeta
    assert "acaba de cambiar" not in pagina.locator("#plFrescura").inner_text(), "lo propio no es de un colega"
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, _cambio_de_otro(semana, lunes, 1))
    pagina.locator('#plPersonal tr[data-persona="MP"] td[data-dia="1"] .pl-chip').wait_for(timeout=5000)
    assert pagina.locator("#plFrescura").inner_text() == "NB acaba de cambiar 1 casilla"
    assert "ajeno" in _celda_personal(pagina, "MP", 1).get_attribute("class")
    assert not errores
    pagina.context.close()


def test_si_un_colega_reemplaza_lo_que_acabas_de_cambiar_se_avisa_y_se_puede_volver(navegador, sitio):
    """2026-11-10, pedido del usuario: trabajar a la vez sin pisarse sin saberlo. En cada casilla manda el cambio más
    reciente; si el de un colega reemplaza uno tuyo de hace poco, una franja dice quién y qué, y «Volver a lo mío» lo
    repone como un cambio nuevo. Lo de un colega que no toca lo tuyo no la muestra."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    mio = f"publicado/planificacion/{semana}/{DISPOSITIVO}.json"
    _celda_personal(pagina, "LC", 0).click()
    pagina.locator('#plPop input[data-op="c|req:908"]').check()
    pagina.keyboard.press("Escape")
    _esperar_archivo(pagina, mio, lambda s: len(s["datos"]["asignaciones"]) == 1)
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, _cambio_de_otro(semana, lunes, 1))
    pagina.locator('#plPersonal tr[data-persona="MP"] td[data-dia="1"] .pl-chip').wait_for(timeout=5000)
    assert pagina.locator("#plPisado").is_hidden(), "lo de otro que no toca lo tuyo no es un reemplazo"
    # NB quita lo que LC acababa de asignar
    otro = _cambio_de_otro(semana, lunes, 0, persona="LC", dispositivo="otro0002")
    cambio = next(iter(otro.values()))["datos"]["asignaciones"][0]
    cambio["activa"] = False
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, otro)
    franja = pagina.locator("#plPisado")
    franja.wait_for(timeout=6000)
    txt = franja.inner_text()
    assert "NB cambió algo que tú acababas de cambiar" in txt and "Asignaste a LC el lunes" in txt and "NB quitó esa asignación" in txt, txt
    assert pagina.locator('#plPersonal tr[data-persona="LC"] td[data-dia="0"] .pl-chip').count() == 0
    franja.get_by_role("button", name="Volver a lo mío").click()
    assert franja.is_hidden()
    pagina.locator('#plPersonal tr[data-persona="LC"] td[data-dia="0"] .pl-chip').wait_for(timeout=2000)
    _esperar_aviso(pagina, "Volvió lo tuyo")
    _esperar_archivo(pagina, mio, lambda s: any(a["persona"] == "LC" and a["activa"] and a["t"] > cambio["t"] for a in s["datos"]["asignaciones"]))
    assert not errores
    pagina.context.close()


def test_se_ve_quien_mas_esta_en_la_misma_semana(navegador, sitio):
    """2026-11-10: cada navegador deja en publicado/presencia/ qué semana o proyecto tiene a la vista, y al salir lo
    vacía. Se nombra solo a quien está en la misma semana y lo renovó hace poco (no a quien cerró sin salir)."""
    from datetime import date
    esquemas = _cargar("esquemas_para_test_portal", RAIZ / "Sistema Intercambio" / "esquemas.py")
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, _ = _semana_de(date.today())
    propia = f"publicado/presencia/{DISPOSITIVO}.json"
    sobre = _esperar_archivo(pagina, propia, lambda s: s["datos"]["vista"] == "planificacion")
    assert sobre["datos"]["donde"] == semana and sobre["datos"]["por"] == "LC"
    assert esquemas.validar_publicacion("presencia", sobre) == []
    assert pagina.locator("#plConmigo").is_hidden()
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {
        "publicado/presencia/otro0001.json": _presencia("otro0001", "NB", "planificacion", semana),
        "publicado/presencia/otro0002.json": _presencia("otro0002", "ES", "planificacion", "2020-W01"),
        "publicado/presencia/otro0003.json": _presencia("otro0003", "MP", "planificacion", semana, -600)})
    pagina.wait_for_function("document.getElementById('plConmigo').textContent === 'NB también está en esta semana'", timeout=20000)
    assert pagina.locator("#plConmigo").is_visible()
    pagina.locator("#pestanas .ir", has_text="Inicio").click()
    _esperar_archivo(pagina, propia, lambda s: s["datos"]["vista"] == "" and s["datos"]["donde"] == "")
    assert not errores
    pagina.context.close()


def test_lo_que_llega_no_interrumpe_el_arrastre_ni_el_foco(navegador, sitio):
    """Con revisiones cada pocos segundos, repintar en cualquier momento botaría lo que se lleva en la mano o el foco."""
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    # El foco sigue en la casilla donde se estaba moviendo con las flechas
    _celda_personal(pagina, "LC", 2).focus()
    ancla = pagina.evaluate("document.activeElement.dataset.ancla")
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, _cambio_de_otro(semana, lunes, 1))
    pagina.locator('#plPersonal tr[data-persona="MP"] td[data-dia="1"] .pl-chip').wait_for(timeout=5000)
    assert pagina.evaluate("document.activeElement.dataset.ancla") == ancla
    # A medio arrastrar no se repinta: lo arrastrado sigue en la página y lo nuevo aparece al soltar
    pagina.evaluate("""() => {
        const el = document.querySelector('#plPersonal .pl-arrastrable, #vistaPlan .pl-arr .pl-arrastrable');
        window.__llevado = el;
        el.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: new DataTransfer() }));
    }""")
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, _cambio_de_otro(semana, lunes, 3, por="ES", dispositivo="otro0002"))
    pagina.wait_for_function("document.getElementById('plFrescura').textContent === 'ES acaba de cambiar 1 casilla'", timeout=6000)
    assert pagina.evaluate("window.__llevado.isConnected"), "lo que se lleva en la mano sigue ahí"
    assert pagina.locator('#plPersonal tr[data-persona="MP"] td[data-dia="3"] .pl-chip').count() == 0
    pagina.evaluate("window.__llevado.dispatchEvent(new DragEvent('dragend', { bubbles: true }))")
    pagina.locator('#plPersonal tr[data-persona="MP"] td[data-dia="3"] .pl-chip').wait_for(timeout=1000)
    assert not errores
    pagina.context.close()


def test_lo_que_no_cumple_el_esquema_de_la_carpeta_no_se_escribe(navegador, sitio):
    """Auditoría 2026-11-06: el Portal valida con el catálogo de la carpeta (esquemas.json) antes de crear el archivo.
    Aquí el catálogo pide un campo que el Portal no manda: la semana no se escribe y la vista lo dice."""
    import copy
    import json
    from datetime import date
    esquemas = _cargar("esquemas_para_test_portal", RAIZ / "Sistema Intercambio" / "esquemas.py")
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, _ = _semana_de(date.today())
    paquete = copy.deepcopy(esquemas.paquete())      # paquete() guarda el suyo: no se toca
    paquete["publicaciones"]["planificacion-semana"]["required"].append("campoNuevo")
    pagina.evaluate(JS_ESCRIBIR_TEXTO, ["esquemas.json", json.dumps(paquete, ensure_ascii=False)])
    _celda_personal(pagina, "LC", 0).click()
    pagina.locator('#plPop input[data-op="c|req:908"]').check()
    pagina.keyboard.press("Escape")
    pagina.wait_for_function("document.getElementById('plFrescura').textContent.startsWith('No se pudo guardar')")
    assert "campoNuevo" in pagina.locator("#plFrescura").get_attribute("title")
    assert pagina.evaluate(JS_LEER_INTERCAMBIO, f"publicado/planificacion/{semana}/{DISPOSITIVO}.json") is None
    # Con el catálogo de verdad (el que deja el procesador) se guarda
    pagina.evaluate(JS_ESCRIBIR_TEXTO, ["esquemas.json", json.dumps(esquemas.paquete(), ensure_ascii=False)])
    pagina.locator("#plReintentar").click()
    sobre = _esperar_archivo(pagina, f"publicado/planificacion/{semana}/{DISPOSITIVO}.json")
    assert esquemas.validar_publicacion("planificacion-semana", sobre) == []
    pagina.wait_for_function("document.getElementById('plFrescura').textContent === 'Guardado · OneDrive lo lleva al equipo'")
    assert not errores
    pagina.context.close()


def test_si_la_carpeta_no_responde_la_vista_lo_dice(navegador, sitio):
    """Un aviso que sigue en verde sin estar recibiendo nada es lo que ya pasó en el Formulador (2026-10-27)."""
    from datetime import datetime, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    pagina.evaluate("() => { FileSystemDirectoryHandle.prototype.getDirectoryHandle = () => new Promise(() => {}); }")
    pagina.wait_for_timeout(4500)      # empezó una lectura que nunca termina
    pagina.clock.set_system_time(datetime.now() + timedelta(minutes=2))
    pagina.wait_for_function("document.getElementById('plFrescura').textContent.includes('no responde')", timeout=4000)
    assert "bad" in pagina.locator("#plPunto").get_attribute("class")
    assert not errores
    pagina.context.close()


def test_un_error_al_guardar_se_reintenta_solo_sin_parpadear(navegador, sitio):
    from datetime import date
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, _ = _semana_de(date.today())
    # La presencia (2026-11-10) también escribe, una vez al abrir y luego cada 90 s: que no entre en la cuenta
    _esperar_archivo(pagina, f"publicado/presencia/{DISPOSITIVO}.json")
    pagina.evaluate("""() => { window.__original = FileSystemFileHandle.prototype.createWritable; window.__intentos = 0;
        FileSystemFileHandle.prototype.createWritable = async function () { window.__intentos++; throw new Error('sin permiso'); }; }""")
    _celda_personal(pagina, "LC", 0).click()
    pagina.locator('#plPop input[data-op="c|req:908"]').check()
    pagina.keyboard.press("Escape")
    pagina.wait_for_function("document.getElementById('plFrescura').textContent.startsWith('No se pudo guardar')")
    primero = pagina.evaluate("window.__intentos")
    pagina.wait_for_timeout(7000)      # varias vueltas de lectura
    assert pagina.evaluate("window.__intentos") == primero, "no insiste en cada vuelta"
    pagina.evaluate("() => { FileSystemFileHandle.prototype.createWritable = window.__original; }")
    pagina.locator("#plReintentar").click()
    _esperar_archivo(pagina, f"publicado/planificacion/{semana}/{DISPOSITIVO}.json", lambda s: len(s["datos"]["asignaciones"]) == 1)
    assert len(errores) <= primero + 1 and all("sin permiso" in e for e in errores)
    pagina.context.close()


@pytest.mark.parametrize("ancho", [390, 1024, 1366])
def test_los_vehiculos_caben_sin_desbordes(navegador, sitio, ancho):
    """Las etiquetas de vehículo en las tres vistas, «Vehículos en la semana», la cifra del resumen y los botones de la
    ventanita caben sin salirse de lado ni quedar con letra chica, también en el teléfono."""
    movil = ancho < 760
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="general", ancho=ancho, alto=844, movil=movil)
    _, lunes = _semana_con_vehiculos(pagina)
    lun = lunes.isoformat()
    for vista in ("general", "personal", "proyecto"):
        pagina.locator(f'.pl-vista[data-vista="{vista}"]').click()
        if movil:
            pagina.locator('#plDiasMovil .pl-dia-tab').first.click()      # el teléfono muestra hoy; los vehículos van el lunes
        elif vista == "general":
            # En el computador, General muestra hoy en grande (2026-11-16): de jueves a sábado no había vehículos y la
            # prueba fallaba según el día (visto el 2026-11-19 en el CI, en hora UTC). Se elige el lunes.
            pagina.evaluate("() => { planif.diaMovil = 0; plPintar(); }")
        pagina.locator(f"#pl{vista.capitalize()} .pl-veh >> visible=true").first.wait_for()
        d = pagina.evaluate(JS_DESBORDES)
        assert d["doc"] <= ancho and not d["fuera"], (vista, d)
        fuera = pagina.evaluate("""(ancho) => [...document.querySelectorAll('#vistaPlan *')].filter((e) => e.getClientRects().length
            && e.getBoundingClientRect().right > ancho + 0.5).map((e) => e.className || e.tagName)""", ancho)
        assert not fuera, (vista, fuera)
        chicos = pagina.evaluate("""() => [...document.querySelectorAll('#vistaPlan *')]
            .filter((e) => e.getClientRects().length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
            .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12).map((e) => e.className || e.tagName)""")
        assert not chicos, (vista, chicos)
    # La cifra de los vehículos se lee entera (en el teléfono ocupa su fila)
    kpi = pagina.locator("#plResumen .pl-kpi-veh .rc-kpi-sub")
    assert kpi.is_visible() and kpi.evaluate("e => e.scrollWidth <= e.clientWidth + 1"), kpi.inner_text()
    # La ventanita con los vehículos bajo cada persona
    if movil:
        pagina.locator('#plDiasMovil .pl-dia-tab').first.click()
    _celda_proyecto(pagina, "req:908", 0).click()
    caja = pagina.locator("#plPop").bounding_box()
    assert caja["x"] >= 0 and caja["x"] + caja["width"] <= ancho and caja["y"] >= 0 and caja["y"] + caja["height"] <= 844, caja
    dentro = pagina.evaluate("""() => { const r = document.getElementById('plPop').getBoundingClientRect();
        const vis = [...document.querySelectorAll('#plPop *')].filter((e) => e.getClientRects().length);
        return { fuera: vis.filter((e) => e.getBoundingClientRect().right > r.right + 0.5).map((e) => e.className || e.tagName),
                 chicos: vis.filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
                   .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12).map((e) => e.className || e.tagName),
                 botones: vis.filter((e) => e.matches('.pl-veh-op')).map((e) => e.getBoundingClientRect().height) }; }""")
    assert not dentro["fuera"] and not dentro["chicos"], dentro
    assert len(dentro["botones"]) == 4 and min(dentro["botones"]) >= (36 if movil else 30), dentro["botones"]
    pagina.keyboard.press("Escape")
    # «Vehículos en la semana» entero a la vista: sus columnas no se salen del panel
    pagina.locator('.pl-vista[data-vista="general"]').click()
    panel = pagina.locator("#plVehiculos")
    panel.scroll_into_view_if_needed()
    p = panel.bounding_box()
    assert all(b["x"] + b["width"] <= p["x"] + p["width"] + 0.5 for b in
               pagina.locator("#plVehiculos .pl-veh-uso, #plVehiculos th").evaluate_all("es => es.map((e) => e.getBoundingClientRect().toJSON())")), p
    assert pagina.locator(f'#plVehiculos tr[data-iso="{lun}"] .pl-veh-uso').count() == 2      # la RAM a En obra, la Quempineta a Obra sin número
    assert not errores
    pagina.context.close()

# ---- Personas y proyectos escritos a mano en la Planificación (2026-10-26) ---------------------------------------


def test_agregar_una_persona_escrita_y_asignarla(navegador, sitio):
    """Pedido del 2026-10-26: agregar a alguien que no está en la lista escribiendo su nombre, para asignarlo a proyectos.
    Es temporal (pedido del mismo día): queda solo en la semana a la vista, con su nombre en las tres vistas; la semana
    siguiente no aparece, pero en «Agregar» se suma con un toque. Quitarlo no borra lo ya asignado."""
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    aviso = lambda: pagina.locator("#aviso").inner_text()
    dlg = pagina.locator("#dlgPlAgregar")
    # «Agregar», arriba, abre el diálogo en «Persona» desde «Por personal»; sin nombre no se cierra y lo dice ahí mismo
    pagina.locator("#plAgregar").click()
    assert dlg.is_visible()
    assert pagina.locator('#plAgregarModo [data-modo="persona"]').get_attribute("aria-pressed") == "true"
    assert pagina.locator("#plAgregarLugarCampo").is_hidden()
    pagina.locator("#plAgregarOk").click()
    assert dlg.is_visible() and pagina.locator("#plAgregarPista").inner_text() == "Escribe el nombre de la persona."
    # Alguien del equipo ya está
    pagina.locator("#plAgregarNombre").fill("rl")
    pagina.locator("#plAgregarOk").click()
    assert dlg.is_visible() and pagina.locator("#plAgregarPista").inner_text() == "RL ya está en la planificación."
    pagina.locator("#plAgregarNombre").fill("juan pérez")
    pagina.locator("#plAgregarNombre").press("Enter")
    assert dlg.is_hidden()
    assert aviso().startswith("Juan Pérez queda solo en esta semana")
    fila = pagina.locator('#plPersonal tr[data-persona="x-juan-perez"]')
    assert fila.locator(".pl-quien-txt b").inner_text() == "Juan Pérez"
    assert fila.locator(".pl-avatar").inner_text() == "JP"
    assert fila.locator(".pl-quien-txt span").inner_text() == "Sin proyectos"
    assert "pl-avatar mano" in fila.locator(".pl-avatar").get_attribute("class"), "círculo punteado"
    assert list(pagina.evaluate(JS_PERSONAL))[-1] == "x-juan-perez", "después del equipo"
    # La lista queda en su archivo y cumple el esquema
    sobre = _esperar_archivo(pagina, LISTA, lambda s: len(s["datos"]["personas"]) == 1)
    assert [(x["id"], x["nombre"], x["semana"], x["activa"], x["por"]) for x in sobre["datos"]["personas"]] == [("x-juan-perez", "Juan Pérez", semana, True, "LC")]
    assert _esquemas().validar_publicacion("planificacion-lista", sobre) == []
    # Se le asigna un proyecto como a cualquiera
    _celda_personal(pagina, "x-juan-perez", 0).click()
    assert pagina.locator("#plPopTit").inner_text().startswith("Juan Pérez · ")
    pagina.locator('#plPop input[data-op="c|req:908"]').check()
    assert aviso().startswith(f"Juan Pérez va a En obra el lunes {lunes.day}.")
    pagina.keyboard.press("Escape")
    archivo = f"publicado/planificacion/{semana}/{DISPOSITIVO}.json"
    sobre = _esperar_archivo(pagina, archivo, lambda s: any(x["persona"] == "x-juan-perez" for x in s["datos"]["asignaciones"]))
    assert sobre["datos"]["personas"] == {"x-juan-perez": {"nombre": "Juan Pérez"}}
    assert _esquemas().validar_publicacion("planificacion-semana", sobre) == []
    # En «Por proyecto» va con su nombre corto, y el texto para WhatsApp con el entero
    pagina.locator('.pl-vista[data-vista="proyecto"]').click()
    assert _celda_proyecto(pagina, "req:908", 0).locator(".pl-per").all_inner_texts() == ["Juan P."]
    _mas(pagina, "#plCompartir").click()
    assert "*Juan Pérez*" in pagina.locator("#plTextoArea").input_value()
    pagina.keyboard.press("Escape")
    # La semana siguiente no está: es temporal. En «Agregar» aparece entre los de semanas anteriores y se suma con un toque
    pagina.locator('.pl-vista[data-vista="personal"]').click()
    pagina.locator("#plDespues").click()
    pagina.locator('#plPersonal tr[data-persona="RL"]').wait_for()
    assert pagina.locator('#plPersonal tr[data-persona="x-juan-perez"]').count() == 0
    siguiente = _semana_de(lunes + timedelta(days=7))[0]
    pagina.locator('#plPersonal [data-agregar="persona"]').click()
    assert "no pasa a las siguientes" in pagina.locator("#plAgregarPista").inner_text()
    assert pagina.locator("#plAgregados h3").all_text_contents() == ["De semanas anteriores"]
    assert pagina.locator("#plAgregados li .pl-agr-txt").all_inner_texts()[0].split("\n") == ["Juan Pérez", f"semana {int(semana[-2:])}"]
    pagina.locator('#plAgregados button[data-k="x-juan-perez"][data-accion="sumar"]').click()
    assert pagina.locator("#plAgregados h3").all_text_contents() == [f"Personas agregadas a mano en la semana {int(siguiente[-2:])}"]
    pagina.locator("#plAgregarCerrar").click()
    fila = pagina.locator('#plPersonal tr[data-persona="x-juan-perez"]')
    assert fila.locator(".pl-quien-txt span").inner_text() == "Sin proyectos"
    # Quitarlo de esa semana: sale; en la suya, donde tiene algo, se sigue viendo
    pagina.locator('#plPersonal [data-agregar="persona"]').click()
    pagina.locator('#plAgregados button[data-k="x-juan-perez"][data-accion="quitar"]').click()
    pagina.locator("#plAgregarCerrar").click()
    assert aviso().startswith(f"Juan Pérez ya no está en la semana {int(siguiente[-2:])}.")
    assert pagina.locator('#plPersonal tr[data-persona="x-juan-perez"]').count() == 0
    pagina.locator("#plHoy").click()
    fila.wait_for()
    assert fila.locator(".pl-quien-txt span").inner_text() == "1 de 5 días · 1 proyecto"
    pagina.locator('#plPersonal [data-agregar="persona"]').click()
    pagina.locator('#plAgregados button[data-k="x-juan-perez"][data-accion="quitar"]').click()
    pagina.locator("#plAgregarCerrar").click()
    assert aviso().startswith("Juan Pérez ya no está en esta semana.")
    assert fila.locator(".pl-quien-txt span").inner_text() == "Fuera de la lista"
    # Ctrl Z lo vuelve a la lista
    pagina.locator("#tituloPlan").click()
    pagina.keyboard.press("Control+z")
    assert fila.locator(".pl-quien-txt span").inner_text() == "1 de 5 días · 1 proyecto"
    sobre = _esperar_archivo(pagina, LISTA, lambda s: sorted((x["semana"], x["activa"]) for x in s["datos"]["personas"]) == [(semana, True), (siguiente, False)])
    assert _esquemas().validar_publicacion("planificacion-lista", sobre) == []
    assert not errores
    pagina.context.close()


def test_otra_persona_y_otro_proyecto_desde_la_ventanita(navegador, sitio):
    """En la ventanita de un proyecto se escribe otra persona y queda asignada a él esos días; en la de una persona, un
    proyecto que no está en la lista, y en «Asignar» del tablero general, también."""
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    _, lunes = _semana_de(date.today())
    aviso = lambda: pagina.locator("#aviso").inner_text()
    pop = pagina.locator("#plPop")
    _celda_proyecto(pagina, "req:907", 0).click()
    pop.locator('[data-op="d|todos"]').click()
    pop.locator('input[data-op="persona-nueva"]').fill("Pedro Soto")
    pop.locator('input[data-op="persona-nueva"]').press("Enter")
    assert aviso().startswith("Pedro Soto va a Adjudicada sin ficha de lunes a viernes.")
    assert pop.locator('input[data-op="c|x-pedro-soto"]').is_checked()
    assert pop.locator('li:has(input[data-op="c|x-pedro-soto"]) .pl-op-txt .t').inner_text() == "Pedro Soto"
    pagina.keyboard.press("Escape")
    assert _celda_proyecto(pagina, "req:907", 4).locator(".pl-per").all_inner_texts() == ["Pedro S."]
    # Desde una persona: un proyecto que no está en la lista
    pagina.locator('.pl-vista[data-vista="personal"]').click()
    _celda_personal(pagina, "ES", 1).click()
    pop.locator('input[data-op="proyecto-nuevo"]').fill("bodega Renca")
    pop.locator('input[data-op="proyecto-nuevo"]').press("Enter")
    martes = lunes + timedelta(days=1)
    assert aviso().startswith(f"ES va a Bodega Renca el martes {martes.day}.")
    assert pop.locator('input[data-op="c|pro:bodega-renca"]').is_checked()
    pagina.keyboard.press("Escape")
    assert pagina.evaluate(JS_PERSONAL)["ES"][1] == ["Bodega Renca"]
    # Desde «Asignar» en el tablero general: el proyecto escrito y después quiénes van
    pagina.locator('.pl-vista[data-vista="general"]').click()
    pagina.locator("#plGeneral .pl-nuevo").first.click()
    pop.locator('input[data-op="proyecto-nuevo"]').fill("Galpón Quilicura")
    pop.locator('input[data-op="proyecto-nuevo"]').press("Enter")
    assert pagina.locator("#plPopTit").inner_text() == "Galpón Quilicura"
    pop.locator('input[data-op="c|MP"]').check()
    assert aviso().startswith("MP va a Galpón Quilicura")
    pagina.keyboard.press("Escape")
    # Los tres quedan en la lista de este navegador, que cumple el esquema
    sobre = _esperar_archivo(pagina, LISTA, lambda s: len(s["datos"]["proyectos"]) == 2 and len(s["datos"]["personas"]) == 1)
    assert sorted(x["clave"] for x in sobre["datos"]["proyectos"]) == ["pro:bodega-renca", "pro:galpon-quilicura"]
    assert _esquemas().validar_publicacion("planificacion-lista", sobre) == []
    assert not errores
    pagina.context.close()


def test_agregar_un_proyecto_escrito_o_con_su_numero(navegador, sitio):
    """Un proyecto escrito queda como un proyecto activo más en la semana a la vista (cuenta en el resumen y en la alarma
    si nadie va; la semana siguiente ya no está). Escrito con su N° de la Planilla queda unido a ese requerimiento, aunque el Recorrido lo tenga plegado
    por antiguo (como H2 Green el 2026-10-26); uno que ya está en ejecución no se repite."""
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    dlg = pagina.locator("#dlgPlAgregar")
    kpi = pagina.locator("#plResumen .rc-kpi").first
    assert kpi.locator(".rc-kpi-n").inner_text() == str(len(ACTIVOS))
    pagina.locator("#plAgregar").click()
    assert pagina.locator('#plAgregarModo [data-modo="proyecto"]').get_attribute("aria-pressed") == "true", "desde «Por proyecto»"
    pagina.locator("#plAgregarNombre").fill("Galpón Quilicura")
    pagina.locator("#plAgregarLugar").fill("Quilicura")
    pagina.locator("#plAgregarOk").click()
    assert dlg.is_hidden()
    fila = pagina.locator('#plProyecto tr[data-clave="pro:galpon-quilicura"]')
    assert fila.locator(".pl-proy-txt .t").inner_text() == "Galpón Quilicura"
    assert fila.locator(".pl-proy-txt .s").inner_text() == "agregado a mano"       # el lugar ya está en el nombre
    assert "alarma" in fila.get_attribute("class").split(), "nadie va: cuenta como sin asignar"
    assert kpi.locator(".rc-kpi-n").inner_text() == str(len(ACTIVOS) + 1)
    assert kpi.locator(".rc-kpi-sub").inner_text() == "Con 1 agregado a mano"
    # Con su N°: el 910 se adjudicó hace mucho y el Recorrido lo plegó, pero se puede planificar
    pagina.locator('#plProyecto [data-agregar="proyecto"]').click()
    pagina.locator("#plAgregarNombre").fill("910. Caldera antigua")
    pagina.locator("#plAgregarOk").click()
    fila = pagina.locator('#plProyecto tr[data-clave="req:910"]')
    assert fila.locator(".pl-proy-txt .t").inner_text() == "Caldera antigua"
    assert fila.locator(".pl-proy-txt .s").inner_text() == "N° 910 · agregado a mano"
    assert fila.locator("button.pl-proy").count() == 1, "abre su tarjeta del Recorrido"
    # Uno en ejecución no se agrega otra vez: lo dice el diálogo, que sigue abierto
    pagina.locator("#plAgregar").click()
    pagina.locator("#plAgregarNombre").fill("907")
    pagina.locator("#plAgregarOk").click()
    assert dlg.is_visible() and pagina.locator("#plAgregarPista").inner_text() == "Adjudicada sin ficha ya está en la planificación."
    assert [x.split("\n")[0] for x in pagina.locator("#plAgregados li").all_inner_texts()] == ["Caldera antigua", "Galpón Quilicura"]
    pagina.locator("#plAgregarX").click()
    sobre = _esperar_archivo(pagina, LISTA, lambda s: len(s["datos"]["proyectos"]) == 2)
    assert {x["clave"]: (x["titulo"], x.get("lugar")) for x in sobre["datos"]["proyectos"]} == {
        "pro:galpon-quilicura": ("Galpón Quilicura", "Quilicura"), "req:910": ("Caldera antigua", "")}
    assert _esquemas().validar_publicacion("planificacion-lista", sobre) == []
    pagina.locator("#plDespues").click()
    pagina.locator('#plProyecto tr[data-clave="req:908"]').wait_for()
    assert pagina.locator('#plProyecto tr[data-clave="pro:galpon-quilicura"]').count() == 0
    assert kpi.locator(".rc-kpi-n").inner_text() == str(len(ACTIVOS))
    assert not errores
    pagina.context.close()


def test_un_proyecto_cerrado_sale_de_la_planificacion(navegador, sitio):
    """Pedido del 2026-10-26: «Cerrada» en el Formulador lleva el proyecto al «Cierre» del Recorrido, aunque el Análisis
    Financiero no tenga el 100 %, y lo saca de la Planificación semanal, también si se había agregado a mano con su N°."""
    from datetime import date
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC")
    semana = _semana_de(date.today())[0]      # lo agregado a mano vale en su semana
    lista = {"esquema": "quempin.intercambio/1", "herramienta": "planificacion", "tipo": "planificacion-lista", "generado": _instante(0),
             "autor": "NB", "datos": {"dispositivo": "otronavegador1", "personas": [], "proyectos": [
                 {"clave": "req:909", "titulo": "Terminada a mano", "lugar": "", "semana": semana, "activa": True, "t": _instante(-60)},
                 {"clave": "pro:obra-externa", "titulo": "Obra externa", "lugar": "Talca", "semana": semana, "activa": True, "t": _instante(-60)}]}}
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {
        "publicado/formulador/f907.json": _formulacion("f907", "QMPN-2026-907", 907, "Cerrada", "NB", precio=900),
        "publicado/formulador/f908.json": _formulacion("f908", "QMPN-2026-908", 908, "Cerrada", "LC", precio=800),
        "publicado/formulador/f909.json": _formulacion("f909", "QMPN-2026-909", 909, "Adjudicada", "NB", precio=700),
        "publicado/formulador/fy.json": _formulacion("fy", "QMPN-2026-779", None, "Cerrada", "LC"),
        "publicado/planificacion/lista/otronavegador1.json": lista})
    pagina.evaluate("d => localStorage.setItem('quempin_portal_dispositivo', d)", DISPOSITIVO)
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Recorrido de proyectos")
    pagina.locator("#rcTablero .rc-tarjeta").first.wait_for()
    col = pagina.evaluate(JS_COLUMNAS)
    assert col["ejecucion"] == ["tag-SOLO"], col
    assert sorted(col["cierre"]) == ["req-907", "req-908", "req-909"], col
    assert pagina.locator('.rc-tarjeta[data-clave="f-fy"]').count() == 0, "cerrada y sin N°: no pide el N°"
    tarjeta = lambda c: pagina.locator(f'.rc-tarjeta[data-clave="{c}"]').inner_text()
    assert "Cerrado" in tarjeta("req-907") and "Cerrado" in tarjeta("req-908")
    # Cerrada con 40 % en el Análisis: lo dice, para que el avance quede en 100 %
    pagina.locator('.rc-tarjeta[data-clave="req-908"] .rc-abrir').click()
    texto = pagina.locator("#dlgRecorrido").inner_text()
    assert "Proyecto cerrado" in texto and "40 % de avance" in texto, texto
    assert pagina.locator("#dlgRecorrido .rc-paso").evaluate_all("ps => ps.map((p) => p.dataset.est)")[4:] == ["hecha", "hecha"]
    pagina.keyboard.press("Escape")
    # 100 % y todavía «Adjudicada»: propone marcarla Cerrada
    pagina.locator('.rc-tarjeta[data-clave="req-909"] .rc-abrir').click()
    assert "márcalo «Cerrada»" in pagina.locator("#dlgRecorrido").inner_text()
    pagina.keyboard.press("Escape")
    # En la Planificación queda solo lo que sigue en obra (y lo agregado a mano que no está cerrado)
    _menu(pagina, "Planificación semanal")
    pagina.locator("#plResumen .rc-kpi").first.wait_for()
    pagina.locator('.pl-vista[data-vista="proyecto"]').click()
    claves = pagina.locator("#plProyecto tr[data-clave]").evaluate_all("ts => ts.map((t) => t.dataset.clave)")
    assert sorted(claves) == ["pro:obra-externa", "tag:SOLO"], claves
    assert pagina.locator(ALERTA_N).inner_text() == "2"
    assert not errores
    pagina.context.close()


def test_el_estado_de_los_proyectos_y_dar_por_cerrado_uno_sin_formulador(navegador, sitio):
    """Pedido del 2026-10-26: ver en la planificación el estado de cada proyecto y dar por cerrado uno que ya terminó y se
    entregó, aunque no haya pasado por el Formulador (el 907 está solo «Adjudicado» en la Planilla). Sale de la
    planificación, pasa al «Cierre» del Recorrido con quién y cuándo lo cerró, y se puede reabrir."""
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    kpi = pagina.locator("#plResumen .rc-kpi").first
    # Cada fila de «Por proyecto» dice cómo va según el Recorrido, con el detalle al pasar encima
    avance = lambda c: pagina.locator(f'#plProyecto tr[data-clave="{c}"] .pl-avance')
    assert avance("req:907").inner_text() == "Sin ficha en el Análisis Financiero"
    assert avance("req:907").get_attribute("data-nivel") == "warn"
    assert "Créala en «Ingresar avance»" in avance("req:907").get_attribute("title")
    assert avance("req:908").inner_text() == "40 % de avance"
    assert avance("tag:SOLO").inner_text() == "50 % de avance"
    # «Estado de los proyectos», arriba o al pie de «Por proyecto»: de dónde sale cada uno y cómo va
    pagina.locator('#plProyecto [data-estado="proyectos"]').click()
    dlg = pagina.locator("#dlgPlProyectos")
    assert dlg.is_visible()
    assert _proyectos_del_dialogo(pagina, "En ejecución") == list(ACTIVOS)
    li = dlg.locator('li[data-clave="req:907"]')
    assert li.locator(".pl-proys-fuentes").inner_text() == "Planilla «Adjudicado» · sin formulación · sin ficha en el Análisis Financiero"
    assert dlg.locator('li[data-clave="req:908"] .pl-proys-fuentes').inner_text().startswith("Planilla «Adjudicado» · sin formulación · Análisis Financiero 40 %, término ")
    assert li.locator(".rc-chip").all_inner_texts() == ["Sin ficha en el Análisis Financiero", "Nadie esta semana"]
    # Darlo por cerrado: sin ficha en el Análisis no ofrece el 100 %; la nota queda con él
    li.locator('[data-accion="cerrar"]').click()
    assert li.locator(".pl-cerrar").is_visible() and dlg.locator("#plCerrarAF").count() == 0
    dlg.locator("#plCerrarNota").fill("Entregado el 20-10, con acta")
    dlg.locator("#plCerrarNota").press("Enter")
    assert dlg.is_visible(), "Enter confirma sin cerrar el diálogo"
    assert dlg.locator("#plProyAviso").inner_text().startswith("Adjudicada sin ficha queda cerrado: pasa al «Cierre» del Recorrido y sale de la planificación.")
    assert _proyectos_del_dialogo(pagina, "En ejecución") == ["req:908", "tag:SOLO"]
    assert _proyectos_del_dialogo(pagina, "Cerrados en la planificación") == ["req-907"]
    assert "Cerrado por LC hoy a las" in dlg.locator('li[data-tarjeta="req-907"]').inner_text()
    assert "«Entregado el 20-10, con acta»" in dlg.locator('li[data-tarjeta="req-907"]').inner_text()
    pagina.locator("#plProyCerrar").click()
    assert dlg.is_hidden()
    # Sale de la planificación (y de la alarma) y queda en su archivo, que cumple el esquema
    assert pagina.locator('#plProyecto tr[data-clave="req:907"]').count() == 0
    assert kpi.locator(".rc-kpi-n").inner_text() == str(len(ACTIVOS) - 1)
    sobre = _esperar_archivo(pagina, CIERRES, lambda s: len(s["datos"]["proyectos"]) == 1)
    assert [(x["clave"], x["cerrado"], x["nota"], x["af"], x["por"]) for x in sobre["datos"]["proyectos"]] == [
        ("req:907", True, "Entregado el 20-10, con acta", False, "LC")]
    assert _esquemas().validar_publicacion("planificacion-cierres", sobre) == []
    # En el Recorrido está en el «Cierre», con quién lo cerró y su nota, y desde ahí se reabre
    _menu(pagina, "Recorrido de proyectos")
    pagina.locator("#rcTablero .rc-tarjeta").first.wait_for()
    col = pagina.evaluate(JS_COLUMNAS)
    assert "req-907" in col["cierre"] and "req-907" not in col["ejecucion"], col
    pagina.locator('.rc-tarjeta[data-clave="req-907"] .rc-abrir').click()
    texto = pagina.locator("#dlgRecorrido").inner_text()
    assert "Dado por cerrado en la Planificación semanal por LC" in texto and "«Entregado el 20-10, con acta»" in texto, texto
    pagina.locator('#dlgRecorrido [data-op="reabrir"]').click()
    assert pagina.locator('#dlgRecorrido [data-op="cerrar"]').is_visible(), "vuelve a ejecución y se puede volver a cerrar"
    pagina.keyboard.press("Escape")
    assert "req-907" in pagina.evaluate(JS_COLUMNAS)["ejecucion"]
    sobre = _esperar_archivo(pagina, CIERRES, lambda s: not s["datos"]["proyectos"][0]["cerrado"])
    assert _esquemas().validar_publicacion("planificacion-cierres", sobre) == []
    _menu(pagina, "Planificación semanal")
    pagina.locator('#plProyecto tr[data-clave="req:907"]').wait_for()
    assert not errores
    pagina.context.close()


def test_dar_por_cerrado_pide_el_100_al_analisis_y_se_deshace(navegador, sitio):
    """Con ficha en el Análisis Financiero sin el 100 % (DEMO, 40 %), cerrarlo ofrece dejar ahí el 100 % de avance: un
    «datos-proyecto» al buzón, como «Ingresar avance», que solo reemplaza el 40 % que se vio. El cierre vale para su N° y
    su TAG. «Deshacer» lo reabre y retira el mensaje si todavía no se procesa. Se abre también desde el Recorrido."""
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="proyecto")
    dlg = pagina.locator("#dlgPlProyectos")
    # Desde la ficha del Recorrido (la fila del proyecto la abre): «Dar por cerrado» lleva al formulario
    pagina.locator('#plProyecto tr[data-clave="req:908"] button.pl-proy').click()
    pagina.locator('#dlgRecorrido [data-op="cerrar"]').click()
    assert pagina.locator("#dlgRecorrido").is_hidden() and dlg.is_visible()
    assert dlg.locator('li[data-clave="req:908"] .pl-cerrar').is_visible()
    assert dlg.locator("#plCerrarAF").is_checked()
    assert "hoy tiene 40 %" in dlg.locator(".pl-cerrar-af").inner_text()
    dlg.locator("#plCerrarOk").click()
    pagina.wait_for_function("() => !document.querySelector('#plProyAviso').hidden")      # espera a escribir en el buzón
    assert "El 100 % de avance llega al Análisis Financiero en la próxima vuelta del procesador." in dlg.locator("#plProyAviso").inner_text()
    buzon = {n: m for n, m in pagina.evaluate(JS_BUZON).items() if m.get("tipo") == "datos-proyecto" and m.get("origen", {}).get("herramienta") == "portal"}
    assert len(buzon) == 1, buzon
    nombre, msg = next(iter(buzon.items()))
    assert nombre.endswith("_portal_datos-proyecto_" + msg["id"] + ".json")
    assert (msg["proyecto"], msg["valores"], msg["reemplaza"], msg["origen"]["usuario"]) == ({"tag": "DEMO"}, {"% Avance": 1}, {"% Avance": 0.4}, "LC")
    assert _esquemas().validar_mensaje(msg) == []
    sobre = _esperar_archivo(pagina, CIERRES, lambda s: len(s["datos"]["proyectos"]) == 2)
    assert sorted((x["clave"], x["cerrado"], x["af"]) for x in sobre["datos"]["proyectos"]) == [("req:908", True, True), ("tag:DEMO", True, True)]
    assert _esquemas().validar_publicacion("planificacion-cierres", sobre) == []
    # Deshacer, en el mismo diálogo: vuelve a ejecución y el pedido del 100 % se retira del buzón
    dlg.locator("#plProyAviso button").click()
    pagina.wait_for_function("() => document.querySelector('#plProyAviso').textContent.includes('se retiró')")
    assert "req:908" in _proyectos_del_dialogo(pagina, "En ejecución")
    assert not [m for m in pagina.evaluate(JS_BUZON).values() if m.get("origen", {}).get("herramienta") == "portal"]
    sobre = _esperar_archivo(pagina, CIERRES, lambda s: all(not x["cerrado"] for x in s["datos"]["proyectos"]))
    assert _esquemas().validar_publicacion("planificacion-cierres", sobre) == []
    # Sin N° (solo TAG) y sin pedir el 100 %: se cierra por su TAG y no escribe al buzón
    li = dlg.locator('li[data-clave="tag:SOLO"]')
    li.locator('[data-accion="cerrar"]').click()
    dlg.locator("#plCerrarAF").uncheck()
    dlg.locator("#plCerrarOk").click()
    assert _proyectos_del_dialogo(pagina, "En ejecución") == ["req:907", "req:908"]
    assert not [m for m in pagina.evaluate(JS_BUZON).values() if m.get("origen", {}).get("herramienta") == "portal"]
    sobre = _esperar_archivo(pagina, CIERRES, lambda s: any(x["clave"] == "tag:SOLO" for x in s["datos"]["proyectos"]))
    assert [(x["cerrado"], x["af"]) for x in sobre["datos"]["proyectos"] if x["clave"] == "tag:SOLO"] == [(True, False)]
    # En el Recorrido, el aviso de que el Análisis sigue sin el 100 %
    pagina.locator("#plProyCerrar").click()
    _menu(pagina, "Recorrido de proyectos")
    pagina.locator('.rc-tarjeta[data-clave="tag-SOLO"]').wait_for()
    pagina.locator('.rc-tarjeta[data-clave="tag-SOLO"] .rc-abrir').click()
    assert "tiene 50 % de avance: déjalo en 100 %" in pagina.locator("#dlgRecorrido").inner_text()
    assert not errores
    pagina.context.close()


def test_lo_cerrado_en_otro_navegador_sale_de_la_planificacion(navegador, sitio):
    """Los cierres son la unión de los archivos de todos los navegadores, y por clave manda el más reciente: lo que otro
    cerró no aparece, y lo que cerró y después reabrió, sí."""
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC")
    otro = {"esquema": "quempin.intercambio/1", "herramienta": "planificacion", "tipo": "planificacion-cierres", "generado": _instante(0),
            "autor": "NB", "datos": {"dispositivo": "otronavegador1", "proyectos": [
                {"clave": "req:907", "titulo": "Adjudicada sin ficha", "cerrado": True, "nota": "", "af": False, "t": _instante(-90), "por": "NB"},
                {"clave": "tag:DEMO", "titulo": "En obra", "cerrado": True, "nota": "", "af": False, "t": _instante(-90), "por": "NB"},
                {"clave": "tag:DEMO", "titulo": "En obra", "cerrado": False, "t": _instante(-30), "por": "NB"},
                {"clave": "pro:no-vale", "titulo": "Mal formado", "cerrado": True, "t": _instante(-30)}]}}
    assert _esquemas().validar_publicacion("planificacion-cierres", otro) != [], "la clave pro: no vale en el esquema"
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {"publicado/planificacion/cierres/otronavegador1.json": otro})
    pagina.evaluate("d => localStorage.setItem('quempin_portal_dispositivo', d)", DISPOSITIVO)
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Planificación semanal")
    pagina.locator("#plResumen .rc-kpi").first.wait_for()
    pagina.locator('.pl-vista[data-vista="proyecto"]').click()
    claves = pagina.locator("#plProyecto tr[data-clave]").evaluate_all("ts => ts.map((t) => t.dataset.clave)")
    assert sorted(claves) == ["req:908", "tag:SOLO"], claves
    _mas(pagina, "#plProyectos").click()
    assert _proyectos_del_dialogo(pagina, "Cerrados en la planificación") == ["req-907"]
    assert "Cerrado por NB" in pagina.locator('#dlgPlProyectos li[data-tarjeta="req-907"]').inner_text()
    assert not errores
    pagina.context.close()


def test_lo_agregado_por_otro_navegador_aparece(navegador, sitio):
    """La lista es la unión de los archivos de todos los navegadores: lo que otro agregó aparece al releer, y en cada
    persona manda el cambio más reciente (si otro la quitó después, ya no está)."""
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    otro = {"esquema": "quempin.intercambio/1", "herramienta": "planificacion", "tipo": "planificacion-lista", "generado": _instante(0),
            "autor": "NB", "datos": {"dispositivo": "otronavegador1", "personas": [
                {"id": "x-ana-rojas", "nombre": "Ana Rojas", "activa": True, "t": _instante(-60), "por": "NB"},
                {"id": "x-quitado", "nombre": "Ya quitado", "activa": False, "t": _instante(-30), "por": "NB"}],
                "proyectos": [{"clave": "pro:obra-externa", "titulo": "Obra externa", "lugar": "Talca", "activa": True, "t": _instante(-60)}]}}
    pagina.evaluate(JS_ESCRIBIR_TEXTO, ["publicado/planificacion/lista/otronavegador1.json", json.dumps(otro)])
    pagina.locator("#plActualizar").click()
    pagina.locator('#plPersonal tr[data-persona="x-ana-rojas"]').wait_for()
    assert pagina.locator('#plPersonal tr[data-persona="x-quitado"]').count() == 0
    pagina.locator('.pl-vista[data-vista="proyecto"]').click()
    assert pagina.locator('#plProyecto tr[data-clave="pro:obra-externa"] .pl-proy-txt .s').inner_text() == "Talca · agregado a mano"
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [390, 1280])
def test_agregar_a_mano_cabe_sin_desbordes(navegador, sitio, ancho):
    """El diálogo, el botón de arriba y los del pie de las tablas caben sin salirse ni letra chica, también en el teléfono."""
    movil = ancho < 760
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal", ancho=ancho, alto=844, movil=movil)
    pagina.locator("#plAgregar").click()
    pagina.locator("#plAgregarNombre").fill("Juan Pérez")
    pagina.locator("#plAgregarOk").click()
    pagina.locator("#plAgregar").click()
    caja = pagina.locator("#dlgPlAgregar").bounding_box()
    assert caja["x"] >= 0 and caja["x"] + caja["width"] <= ancho, caja
    dentro = pagina.evaluate("""() => { const r = document.getElementById('dlgPlAgregar').getBoundingClientRect();
        const vis = [...document.querySelectorAll('#dlgPlAgregar *')].filter((e) => e.getClientRects().length);
        return { fuera: vis.filter((e) => e.getBoundingClientRect().right > r.right + 0.5).map((e) => e.className || e.tagName),
                 chicos: vis.filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
                   .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12).map((e) => e.className || e.tagName) }; }""")
    assert not dentro["fuera"] and not dentro["chicos"], dentro
    if movil:
        assert pagina.evaluate("parseFloat(getComputedStyle(document.getElementById('plAgregarNombre')).fontSize)") >= 16
    pagina.locator("#plAgregarX").click()
    for vista in ("personal", "proyecto"):
        pagina.locator(f'.pl-vista[data-vista="{vista}"]').click()
        d = pagina.evaluate(JS_DESBORDES)
        assert d["doc"] <= ancho and not d["fuera"], (vista, d)
        for b in pagina.locator(f"#pl{vista.capitalize()} .pl-agregar-pie").all():      # «Agregar» y «Estado de los proyectos»
            b = b.bounding_box()
            assert b["x"] >= 0 and b["x"] + b["width"] <= ancho, (vista, b)
    assert not errores
    pagina.context.close()


def test_lo_agregado_a_mano_es_de_su_semana_y_se_copia_con_lo_suyo(navegador, sitio):
    """Lo agregado a mano antes del 2026-10-26 (sin «semana») es de la semana en que se escribió: otra semana no lo
    muestra. «Copiar la semana anterior» trae a la persona y al proyecto escritos junto con lo suyo, y su Deshacer los
    vuelve a sacar."""
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    antes, lunes_antes = _semana_de(lunes - timedelta(days=7))
    otro = {"esquema": "quempin.intercambio/1", "herramienta": "planificacion", "tipo": "planificacion-lista", "generado": _instante(0),
            "autor": "NB", "datos": {"dispositivo": "otronavegador1", "personas": [
                # Sin «semana»: la de su instante, hace siete días (la semana anterior)
                {"id": "x-ana-rojas", "nombre": "Ana Rojas", "activa": True, "t": _instante(-7 * 86400)},
                {"id": "x-pedro-soto", "nombre": "Pedro Soto", "semana": antes, "activa": True, "t": _instante(-60)}],
                "proyectos": [{"clave": "pro:obra-externa", "titulo": "Obra externa", "semana": antes, "activa": True, "t": _instante(-60)}]}}
    pagina.evaluate(JS_ESCRIBIR_TEXTO, ["publicado/planificacion/lista/otronavegador1.json", json.dumps(otro)])
    jueves = (lunes_antes + timedelta(days=3)).isoformat()
    a = lambda per, c: {"dia": jueves, "persona": per, "proyecto": c, "activa": True, "t": _instante(-50), "por": "NB"}
    pasada = _sobre_plan(antes, lunes_antes, "otronavegador1", asignaciones=[a("x-pedro-soto", "req:908"), a("LC", "pro:obra-externa")],
                         proyectos={"pro:obra-externa": {"titulo": "Obra externa"}})
    pasada["datos"]["personas"] = {"x-pedro-soto": {"nombre": "Pedro Soto"}}
    pagina.evaluate(JS_ESCRIBIR_TEXTO, [f"publicado/planificacion/{antes}/otronavegador1.json", json.dumps(pasada)])
    pagina.locator("#plActualizar").click()
    pagina.locator('#plPersonal tr[data-persona="RL"]').wait_for()
    pagina.wait_for_timeout(300)
    assert [p for p in pagina.evaluate(JS_PERSONAL) if p.startswith("x-")] == [], "ninguno es de esta semana"
    pagina.locator("#plAntes").click()
    pagina.locator('#plPersonal tr[data-persona="x-pedro-soto"]').wait_for()
    assert [p for p in pagina.evaluate(JS_PERSONAL) if p.startswith("x-")] == ["x-ana-rojas", "x-pedro-soto"]
    # En esta semana, copiar la anterior los trae: Pedro (con lo suyo) y Obra externa como activo; Ana no tenía nada
    pagina.locator("#plDespues").click()
    pagina.locator('#plPersonal tr[data-persona="RL"]').wait_for()
    _mas(pagina, "#plCopiar").click()
    pagina.wait_for_function("document.getElementById('aviso').textContent.startsWith('Se copiaron')")
    p = pagina.evaluate(JS_PERSONAL)
    assert p["x-pedro-soto"][3] == ["En obra"] and p["LC"][3] == ["Obra externa"] and "x-ana-rojas" not in p
    assert pagina.locator('#plPersonal tr[data-persona="x-pedro-soto"] .pl-quien-txt span').inner_text() == "1 de 5 días · 1 proyecto"
    pagina.locator('.pl-vista[data-vista="proyecto"]').click()
    assert pagina.locator('#plProyecto tr[data-clave="pro:obra-externa"] .pl-proy-txt .s').inner_text() == "agregado a mano"
    sobre = _esperar_archivo(pagina, LISTA, lambda s: len(s["datos"]["personas"]) == 1 and len(s["datos"]["proyectos"]) == 1)
    assert (sobre["datos"]["personas"][0]["semana"], sobre["datos"]["proyectos"][0]["semana"]) == (semana, semana)
    assert _esquemas().validar_publicacion("planificacion-lista", sobre) == []
    # Un Deshacer saca lo copiado y también a ellos
    pagina.locator("#tituloPlan").click()
    pagina.keyboard.press("Control+z")
    pagina.locator('#plProyecto tr[data-clave="pro:obra-externa"]').wait_for(state="detached")
    pagina.locator('.pl-vista[data-vista="personal"]').click()
    assert "x-pedro-soto" not in pagina.evaluate(JS_PERSONAL)
    assert not errores
    pagina.context.close()


def test_el_menu_personal_elige_quienes_se_ven_y_agrega_personal_definitivo_o_temporal(navegador, sitio):
    """Pedido del usuario (2026-11-13): un desplegable con una casilla por persona para elegir quiénes se ven en la
    planificación, y dos botones: agregar personal definitivo (queda en todas las semanas desde la que se ve) o temporal
    (solo esta semana). Ocultar es de este navegador y se recuerda; quien tiene algo en la semana sigue con su fila."""
    from datetime import date, timedelta
    pagina, errores = _plan_con_datos(navegador, sitio, usuario="LC", vista="personal")
    semana, lunes = _semana_de(date.today())
    filas = lambda: list(pagina.evaluate(JS_PERSONAL))
    menu, lista = pagina.locator("#plPersonas"), pagina.locator("#plPersonasLista")
    equipo = filas()
    assert "MP" in equipo and menu.inner_text().split("\n")[0].strip() == "Personal"
    menu.click()
    assert lista.is_visible() and menu.get_attribute("aria-expanded") == "true"
    assert lista.locator("input[data-per]").evaluate_all("cs => cs.map((c) => c.dataset.per)") == equipo
    assert lista.locator(".pl-per-cuenta").inner_text() == f"{len(equipo)} de {len(equipo)}"
    # Desmarcar a MP la saca de la tabla; el botón dice cuántos se ven
    lista.locator('input[data-per="MP"]').uncheck()
    assert "MP" not in filas() and lista.is_visible()
    assert menu.locator(".pl-per-n").inner_text() == f"{len(equipo) - 1} de {len(equipo)}"
    # Quien tiene algo en la semana sigue con su fila, y el menú lo dice
    _celda_personal(pagina, "EV", 0).click()
    pagina.locator('#plPop input[data-op="c|req:908"]').check()
    pagina.keyboard.press("Escape")
    menu.click()
    lista.locator('input[data-per="EV"]').uncheck()
    assert "EV" in filas()
    assert "Tiene algo esta semana" in lista.locator('label:has(input[data-per="EV"])').inner_text()
    # «Todos» los vuelve a mostrar; Escape cierra
    lista.locator("#plPersonasTodos").click()
    assert filas() == equipo and menu.locator(".pl-per-n").count() == 0
    lista.locator('input[data-per="MP"]').uncheck()
    pagina.keyboard.press("Escape")
    assert lista.is_hidden()
    # Se recuerda en este navegador
    pagina.reload()
    pagina.locator("#plResumen .rc-kpi").first.wait_for()      # el portal vuelve a la pestaña que estaba abierta
    pagina.locator('#plPersonal tr[data-persona="RL"]').wait_for()
    assert "MP" not in filas()
    # Personal definitivo: desde esta semana y también en la siguiente
    menu.click()
    lista.locator('[data-agregar-fija="1"]').click()
    dlg = pagina.locator("#dlgPlAgregar")
    assert dlg.is_visible() and pagina.locator("#dlgPlAgregarTit").inner_text() == "Agregar personal definitivo"
    assert pagina.locator('#plAgregarDura [data-fija="1"]').get_attribute("aria-pressed") == "true"
    pagina.locator("#plAgregarNombre").fill("pedro soto")
    pagina.locator("#plAgregarOk").click()
    assert dlg.is_hidden() and "x-pedro-soto" in filas()
    sobre = _esperar_archivo(pagina, LISTA, lambda s: any(x["id"] == "x-pedro-soto" for x in s["datos"]["personas"]))
    assert [(x["semana"], x.get("fija"), x["activa"]) for x in sobre["datos"]["personas"] if x["id"] == "x-pedro-soto"] == [(semana, True, True)]
    assert _esquemas().validar_publicacion("planificacion-lista", sobre) == []
    # Personal temporal: solo esta semana (el botón del diálogo cambia de uno a otro)
    menu.click()
    lista.locator('[data-agregar-fija="0"]').click()
    assert pagina.locator("#dlgPlAgregarTit").inner_text() == "Agregar personal temporal"
    pagina.locator('#plAgregarDura [data-fija="1"]').click()
    assert pagina.locator("#dlgPlAgregarTit").inner_text() == "Agregar personal definitivo"
    pagina.locator('#plAgregarDura [data-fija="0"]').click()
    pagina.locator("#plAgregarNombre").fill("ana rojas")
    pagina.locator("#plAgregarOk").click()
    assert {"x-pedro-soto", "x-ana-rojas"} <= set(filas())
    menu.click()
    subs = lista.locator(".pl-per-txt").evaluate_all("ts => Object.fromEntries(ts.map((t) => [t.firstChild.textContent, (t.querySelector('small') || {}).textContent || '']))")
    assert subs["Pedro Soto"] == "Definitivo" and subs["Ana Rojas"] == "Solo esta semana"
    pagina.keyboard.press("Escape")
    pagina.locator("#plDespues").click()
    pagina.locator('#plPersonal tr[data-persona="RL"]').wait_for()
    assert "x-pedro-soto" in filas() and "x-ana-rojas" not in filas()
    # Quitarlo del personal definitivo (en «Agregar») lo saca de todas las semanas
    pagina.locator("#plAgregar").click()
    pagina.locator('#plAgregados button[data-k="x-pedro-soto"]').click()
    pagina.locator("#plAgregarCerrar").click()
    assert "x-pedro-soto" not in filas()
    pagina.locator("#plAntes").click()
    pagina.locator('#plPersonal tr[data-persona="RL"]').wait_for()
    assert "x-pedro-soto" not in filas()
