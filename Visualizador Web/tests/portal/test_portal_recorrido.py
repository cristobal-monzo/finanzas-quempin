# -*- coding: utf-8 -*-
"""Portal QUEMPIN: Recorrido de proyectos e Inicio.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- Recorrido de proyectos (2026-10-20) -----------------------------------------------------------------
# Todos los proyectos del equipo en las seis etapas, armado con lo que publica la carpeta de intercambio.


def test_el_recorrido_tiene_las_etapas_del_formulador():
    """Las seis etapas del tablero son las del Seguimiento del Formulador (js/flujo.js), en el mismo orden."""
    portal = texto_portal()
    bloque = re.search(r"const RC_ETAPAS = \[(.*?)\];", portal, re.S).group(1)
    titulos = re.findall(r"titulo: '([^']+)'", bloque)
    assert titulos == ["Requerimiento", "Formulación", "Cotización", "Oferta y adjudicación", "Ejecución", "Cierre"]
    reg = {h["id"]: h for h in _registro()["herramientas"]}
    assert all(h in reg for h in re.findall(r"herr: '([a-z-]+)'", bloque))
    assert reg["recorrido"]["tipo"] == "vista" and reg["recorrido"]["grupo"] == "arriba"
    formulador = _hermano("Formulación de proyectos")
    flujo = formulador / "quempin-formulacion" / "js" / "flujo.js" if formulador else None
    if flujo and flujo.exists():
        etapas = re.search(r"const ETAPAS = \[(.*?)\];", flujo.read_text(encoding="utf-8"), re.S).group(1)
        assert re.findall(r"titulo: '([^']+)'", etapas) == titulos
    # El recorrido lee la carpeta del equipo: Configuración y conexiones lo dice
    usan = {e["id"]: e["usan"] for e in _conexiones()["elementos"]}
    assert "recorrido" in usan["biblioteca"] and "recorrido" in usan["intercambio"]


def test_el_recorrido_sin_biblioteca_dice_que_conectar(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Recorrido de proyectos")
    assert _pestanas(pagina) == ["Inicio", "Recorrido"]
    assert pagina.url.endswith("#/recorrido") and pagina.locator("iframe").count() == 0
    pagina.locator("#rcVacio").wait_for()
    texto = pagina.locator("#rcVacio").inner_text()
    if pagina.evaluate("typeof showDirectoryPicker === 'function'"):
        assert "Conecta la biblioteca del equipo" in texto
        assert pagina.locator("#rcVacio .cx-boton").inner_text() == "Conectar biblioteca"
        # Solo mira: no crea la base del Formulador
        assert "qpn-intercambio" not in pagina.evaluate("indexedDB.databases().then((d) => d.map((x) => x.name))")
        pagina.locator("#rcVacio .cx-enlace", has_text="Configuración y conexiones").click()
        assert pagina.locator("#vistaConexiones").is_visible()
    else:
        assert "Chrome o Edge" in texto
    assert pagina.locator("#rcContenido").is_hidden()
    assert not errores
    pagina.context.close()


def test_el_recorrido_pone_cada_proyecto_en_su_etapa(navegador, sitio):
    pagina, errores = _recorrido_con_datos(navegador, sitio)
    col = pagina.evaluate(JS_COLUMNAS)
    assert col == {
        "requerimiento": ["req-900", "f-fz", "req-912"],      # lo urgente primero: cierra en 2 días; después, sin N°
        "formulacion": ["req-901"],
        "cotizacion": ["req-903", "req-902"],                  # el que cierra antes, arriba
        "oferta": ["req-904", "req-906", "req-913", "req-905"],
        "ejecucion": ["req-907", "req-908", "tag-SOLO"],
        "cierre": ["req-909"],
    }, col
    # Lo descartado en la Planilla y lo eliminado en el Formulador no está; lo de hace más de 60 días va plegado
    assert pagina.locator('.rc-tarjeta[data-clave="req-911"], .rc-tarjeta[data-clave="f-fx"]').count() == 0
    assert pagina.locator('.rc-col[data-etapa="ejecucion"] .rc-antiguos .rc-tarjeta').evaluate_all("ts => ts.map((t) => t.dataset.clave)") == ["req-910"]
    accion = lambda c: pagina.locator(f'.rc-tarjeta[data-clave="{c}"] .rc-accion, .rc-tarjeta[data-clave="{c}"] .rc-espera').inner_text().strip()
    assert accion("req-900") == "Formular"
    assert accion("f-fz") == "Escribir el N° de requerimiento"
    assert accion("req-912") == "Actualizar Requerimientos"
    assert accion("req-901") == "Seguir formulando"
    assert accion("req-902") == "Preparar la cotización"
    assert accion("req-903") == "Emitir en Sistema QUEMPIN"
    assert accion("req-904") == "Marcar como Enviada"
    assert accion("req-905") == "Esperando respuesta"
    assert accion("req-906") == "Marcar como Adjudicada"
    assert accion("req-913") == "Avisar en Requerimientos"
    assert accion("req-907") == "Crear su ficha en el Análisis"
    assert accion("req-908") == "Registrar avance"
    assert accion("req-909") == "Ver su resultado"
    tarjeta = lambda c: pagina.locator(f'.rc-tarjeta[data-clave="{c}"]').inner_text()
    # El nombre de la carpeta manda; un título de la Planilla en mayúsculas se lee normal
    assert "Liceo de prueba" in tarjeta("req-900") and "Cierra en 2 días" in tarjeta("req-900") and "Visita mañana" in tarjeta("req-900")
    assert pagina.locator('.rc-tarjeta[data-clave="req-900"]').get_attribute("data-nivel") == "bad"
    assert "Mantención de Calderas del Cesfam y GLP" in tarjeta("req-901")
    assert "40 %" in tarjeta("req-908") and "DEMO" in tarjeta("req-908")
    assert "Sin N°" in tarjeta("tag-SOLO") and "Sin N°" in tarjeta("f-fz")
    assert "Ganada en Mercado Público" in tarjeta("req-906")
    # Sin usuario: lo que requiere acción es de todo el equipo
    assert _cifras(pagina) == {"accion": 10, "cierran": 2, "esperan": 1, "ejecucion": 3}
    assert pagina.locator("#rcMios").is_disabled() and pagina.locator("#rcElegir").is_visible()
    assert "Datos del procesador hace 30 min" in pagina.locator("#rcFrescura").inner_text()
    assert not errores
    pagina.context.close()


def test_una_ficha_de_otro_proyecto_no_se_une_con_el_n(navegador, sitio):
    """2026-11-03, caso real: la ficha UMAG («UMAG Linea de H2», ya entregado) llevaba el N° 280, que es otro proyecto con
    su propia carpeta en el Centro de Costos, y el 280 mostraba sus costos. El procesador lo marca en fichaAjena."""
    pagina, errores = _abrir_portal(navegador, sitio)
    if not pagina.evaluate("typeof showDirectoryPicker === 'function'"):
        pagina.context.close()
        pytest.skip("este Chromium no conecta carpetas")
    archivos = _intercambio_de_prueba()
    reqs = archivos["publicado/requerimientos.json"]["datos"]["requerimientos"]
    reqs.append({"numero": 914, "estado": "Adjudicado", "evaluador": "CM", "titulo": "Conexión del laboratorio", "cierre": _dia(-12)})
    archivos["publicado/proyectos.json"]["datos"]["proyectos"].append(
        {"req": "914", "tag": None, "fichaAjena": ["VIEJ"], "formulaciones": [], "cotizaciones": [], "ordenes": [], "carpetas": {}})
    archivos["publicado/analisis-financiero.json"]["datos"]["proyectos"].append(
        {"tag": "VIEJ", "nombre": "Laboratorio antiguo", "avance": 1, "req": "914", "cierre": _dia(-250), "venta": {"cargada": True}})
    pagina.evaluate(JS_CONECTAR, 30)
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, archivos)
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Recorrido de proyectos")
    pagina.locator("#rcTablero .rc-tarjeta").first.wait_for()
    tarjeta = lambda c: pagina.locator(f'.rc-tarjeta[data-clave="{c}"]')
    assert tarjeta("req-914").count() == 1 and "VIEJ" not in tarjeta("req-914").inner_text()
    assert tarjeta("tag-VIEJ").count() == 1       # la ficha antigua sigue como su propio proyecto
    assert not errores
    pagina.context.close()


def test_actualizar_datos_pide_una_vuelta_y_espera_que_llegue(navegador, sitio):
    pagina, errores = _recorrido_con_datos(navegador, sitio, usuario="LC")
    boton = pagina.locator("#rcPedirVuelta")
    assert boton.inner_text() == "Actualizar datos" and boton.is_enabled()
    boton.click()
    pagina.locator("#rcFrescura", has_text="Actualización pedida").wait_for()
    assert boton.is_disabled() and boton.inner_text() == "Actualizando…"
    # Deja en el buzón un mensaje que cumple su esquema, con el nombre de siempre
    enviados = pagina.evaluate(JS_BUZON_VUELTA)
    assert len(enviados) == 1
    m = enviados[0]["mensaje"]
    assert _esquemas().validar_mensaje(m) == [] and m["origen"]["usuario"] == "LC"
    intercambio = _cargar("intercambio_para_test_portal", RAIZ / "Sistema Intercambio" / "intercambio.py")
    assert intercambio.nombre_mensaje(m) == enviados[0]["nombre"]
    # Recargar no lo olvida: lo pendiente es lo que hay en el buzón
    pagina.reload()
    pagina.locator("#vistaRecorrido").wait_for()
    pagina.locator("#rcFrescura", has_text="Actualización pedida").wait_for()
    assert boton.is_disabled()
    # Con solo una de las dos cosas todavía no terminó: lo que se ve sigue siendo lo de antes
    pagina.evaluate(JS_PROCESADOR_ATIENDE, {"borrar": True, "pulso": False})
    pagina.locator("#rcActualizar").click()
    pagina.locator("#rcFrescura", has_text="Actualización pedida").wait_for()
    assert boton.is_disabled()
    # Con el pulso nuevo termina solo, sin tocar nada, y relee
    pagina.evaluate(JS_PROCESADOR_ATIENDE, {"borrar": False, "pulso": True})
    pagina.locator("#rcFrescura", has_text="Datos del procesador hace un momento").wait_for(timeout=15000)
    assert boton.is_enabled() and boton.inner_text() == "Actualizar datos"
    assert "actualizados" in pagina.locator("#aviso").inner_text()
    assert not errores
    pagina.context.close()


def test_la_vuelta_del_horario_no_da_por_atendido_un_pedido_que_sigue_en_el_buzon(navegador, sitio):
    pagina, errores = _recorrido_con_datos(navegador, sitio)
    pagina.locator("#rcPedirVuelta").click()
    pagina.locator("#rcFrescura", has_text="Actualización pedida").wait_for()
    pagina.evaluate(JS_PROCESADOR_ATIENDE, {"borrar": False, "pulso": True})
    pagina.locator("#rcActualizar").click()
    pagina.wait_for_function("!document.querySelector('#rcFrescura').textContent.startsWith('Actualizando')")
    assert "Actualización pedida" in pagina.locator("#rcFrescura").inner_text()
    assert pagina.locator("#rcPedirVuelta").is_disabled()
    assert not errores
    pagina.context.close()


def test_un_pedido_de_un_colega_que_lleva_mucho_dice_que_no_responde(navegador, sitio):
    from datetime import datetime, timedelta
    pagina, errores = _portal_con_datos(navegador, sitio)
    enviado = (datetime.now().astimezone() - timedelta(minutes=40)).isoformat(timespec="seconds")
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {"buzon/x_portal_pedir-vuelta_abcdef.json": {
        "esquema": "quempin.intercambio/1", "id": "abcdef", "tipo": "pedir-vuelta", "destino": "procesador",
        "origen": {"herramienta": "portal", "usuario": "NB", "enviado": enviado}}})
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Recorrido de proyectos")
    pagina.locator("#rcFrescura", has_text="hace 40 min: el procesador aún no responde").wait_for()
    assert pagina.locator("#rcPedirVuelta").is_disabled()
    assert "warn" in pagina.locator("#rcPunto").get_attribute("class")
    assert "apagado" in pagina.locator("#rcFrescura").get_attribute("title")
    assert not errores
    pagina.context.close()


def test_sin_la_tarea_de_pedidos_dice_que_espera_la_vuelta_de_cada_2_horas(navegador, sitio):
    """Auditoría del 2026-11-06: el botón se publicó antes que la tarea «Pedidos al procesador QUEMPIN» y prometía unos
    5 minutos mientras el pedido esperaba hasta 2 horas. estado.json dice si la tarea está, y el Portal no promete."""
    from datetime import datetime, timedelta
    pagina, errores = _portal_con_datos(navegador, sitio)
    ahora = datetime.now().astimezone()
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {
        "publicado/estado.json": _sobre("procesador", {"procesador": {"ultimaCorrida": ahora.isoformat(timespec="seconds")},
                                                       "publicaciones": {}, "buzon": {}, "pedidos": {"tarea": False}}),
        "buzon/x_portal_pedir-vuelta_abcdef.json": {
            "esquema": "quempin.intercambio/1", "id": "abcdef", "tipo": "pedir-vuelta", "destino": "procesador",
            "origen": {"herramienta": "portal", "usuario": "NB",
                       "enviado": (ahora - timedelta(minutes=40)).isoformat(timespec="seconds")}}})
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Recorrido de proyectos")
    # 40 minutos con la tarea sería «no responde»; sin ella, todavía es lo esperable
    pagina.locator("#rcFrescura", has_text="hace 40 min: se atiende en la próxima vuelta (cada 5 minutos)").wait_for()
    assert "falta la tarea" in pagina.locator("#rcFrescura").get_attribute("title")
    assert "cada 5 minutos" in pagina.locator("#rcPedirVuelta").get_attribute("title")
    assert not errores
    pagina.context.close()


def test_sin_la_carpeta_no_se_ofrece_actualizar_datos(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Recorrido de proyectos")
    pagina.locator("#rcVacio").wait_for()
    assert pagina.locator("#rcPedirVuelta").is_hidden()
    assert not errores
    pagina.context.close()


def test_cada_tarjeta_abre_la_herramienta_donde_se_hace(navegador, sitio):
    pagina, errores = _recorrido_con_datos(navegador, sitio)
    pagina.locator('.rc-tarjeta[data-clave="req-900"] .rc-accion').click()
    _esperar(pagina, "formulador", "hash", "#/req/900")
    pagina.locator("#pestanas .ir", has_text="Recorrido").click()
    pagina.locator('.rc-tarjeta[data-clave="req-903"] .rc-accion').click()
    assert pagina.evaluate("window.__lanzados") == ["quempin://cotizacion"]
    pagina.locator('.rc-tarjeta[data-clave="req-902"] .rc-accion').click()
    _esperar(pagina, "formulador", "hash", "#/p/f902/seguimiento")
    pagina.locator("#pestanas .ir", has_text="Recorrido").click()
    # El detalle: sus seis etapas, lo que sigue, sus datos y sus enlaces
    pagina.locator('.rc-tarjeta[data-clave="req-908"] .rc-abrir').click()
    dlg = pagina.locator("#dlgRecorrido")
    assert dlg.is_visible()
    assert pagina.locator("#dlgRcTit").inner_text() == "N° 908 · En obra"
    assert pagina.locator("#dlgRecorrido .rc-paso").evaluate_all("ps => ps.map((p) => p.dataset.est)") == [
        "hecha", "omitida", "omitida", "hecha", "actual", "pendiente"]
    assert "Registrar avance" in pagina.locator("#dlgRecorrido .rc-sigue").inner_text()
    pagina.locator("#dlgRecorrido .cx-enlace", has_text="Carpeta de ejecución").click()
    assert pagina.evaluate("window.__lanzados")[-1] == "quempin://carpeta/gestion/908.%20En%20obra"
    assert dlg.is_hidden()
    pagina.locator('.rc-tarjeta[data-clave="req-908"] .rc-abrir').click()
    pagina.locator("#dlgRecorrido .cx-enlace", has_text="Análisis Financiero").click()
    _esperar(pagina, "analisis", "hash", "#proyecto=DEMO")
    pagina.locator("#pestanas .ir", has_text="Recorrido").click()
    # Mercado Público se abre aparte, solo con su dirección oficial
    pagina.locator('.rc-tarjeta[data-clave="req-905"] .rc-abrir').click()
    assert pagina.locator("#dlgRecorrido .rc-paso").evaluate_all("ps => ps.map((p) => p.dataset.est)")[3] == "espera"
    pagina.locator("#dlgRecorrido .cx-enlace", has_text="Mercado Público").click()
    assert pagina.evaluate("window.__abiertas")[-1].startswith("https://www.mercadopublico.cl/")
    # La herramienta de cada etapa, desde su columna: la de Ejecución es «Proyectos en ejecución» (2026-10-28)
    pagina.locator('.rc-col[data-etapa="ejecucion"] .rc-donde').click()
    pagina.locator("#vistaEjecucion").wait_for()
    assert "En ejecución" in _pestanas(pagina)
    assert not errores
    pagina.context.close()


def test_el_usuario_marca_lo_suyo_y_filtra_el_recorrido(navegador, sitio):
    """Pedido del 2026-10-20: el recorrido se ve afectado por el usuario elegido, con un filtro para ver solo lo suyo."""
    pagina, errores = _recorrido_con_datos(navegador, sitio, usuario="LC")
    tuyas = lambda: pagina.locator("#rcTablero .rc-tarjeta.tuya").evaluate_all("ts => ts.map((t) => t.dataset.clave).sort()")
    assert tuyas() == sorted(["req-900", "f-fz", "req-903", "req-904", "req-906", "req-908"])
    assert _cifras(pagina) == {"accion": 5, "cierran": 2, "esperan": 1, "ejecucion": 3}
    assert pagina.locator("#rcResumen .rc-kpi").first.inner_text().startswith("5\nTe esperan")
    caja = pagina.locator("#rcMios")
    assert caja.is_enabled() and not caja.is_checked() and pagina.locator("#rcMiosTxt").inner_text() == "Solo mis proyectos LC"
    caja.check()
    assert sorted(sum(pagina.evaluate(JS_COLUMNAS).values(), [])) == tuyas()
    assert pagina.locator("#rcCuenta").inner_text() == "6 proyectos tuyos"
    assert _cifras(pagina) == {"accion": 5, "cierran": 2, "esperan": 0, "ejecucion": 1}
    # Se recuerda en este navegador
    pagina.reload()
    pagina.locator("#rcTablero .rc-tarjeta").first.wait_for()
    assert pagina.locator("#rcMios").is_checked()
    # Otro usuario, elegido arriba: el tablero cambia sin recargar
    pagina.locator("#btnUsuario").click()
    pagina.locator('#listaUsuarios .usr-op[data-usuario="CM"]').click()
    assert sorted(sum(pagina.evaluate(JS_COLUMNAS).values(), [])) == ["req-901", "req-902"]
    assert pagina.locator("#rcMiosTxt").inner_text() == "Solo mis proyectos CM"
    # Sin usuario, el filtro no se puede usar y se ofrece elegirlo
    pagina.locator("#btnUsuario").click()
    pagina.locator("#sinUsuario").click()
    assert pagina.locator("#rcMios").is_disabled() and len(sum(pagina.evaluate(JS_COLUMNAS).values(), [])) == 14
    pagina.locator("#rcElegir").click()
    assert pagina.locator("#popUsuario").is_visible()
    assert not errores
    pagina.context.close()


def test_las_cifras_y_el_buscador_filtran_el_recorrido(navegador, sitio):
    pagina, errores = _recorrido_con_datos(navegador, sitio, usuario="LC")
    pagina.locator('#rcResumen .rc-kpi[data-foco="cierran"]').click()
    assert pagina.locator('#rcResumen .rc-kpi[data-foco="cierran"]').get_attribute("aria-pressed") == "true"
    assert sorted(sum(pagina.evaluate(JS_COLUMNAS).values(), [])) == ["req-900", "req-903"]
    assert pagina.locator("#rcFoco").inner_text().strip() == "Mostrando: Cierran esta semana"
    pagina.locator("#rcFoco").click()
    assert pagina.locator("#rcFoco").is_hidden() and len(sum(pagina.evaluate(JS_COLUMNAS).values(), [])) == 14
    pagina.locator("#rcBuscar").fill("liceo")
    assert sum(pagina.evaluate(JS_COLUMNAS).values(), []) == ["req-900"]
    pagina.locator("#rcBuscar").fill("demo")
    assert sum(pagina.evaluate(JS_COLUMNAS).values(), []) == ["req-908"]
    pagina.locator("#rcBuscar").fill("")
    # Ctrl K también encuentra los proyectos del recorrido y abre su detalle
    pagina.locator("#buscar").fill("908")
    pagina.locator("#resultados .res", has_text="N° 908").first.click()
    assert pagina.locator("#dlgRecorrido").is_visible() and pagina.locator("#dlgRcTit").inner_text() == "N° 908 · En obra"
    pagina.keyboard.press("Escape")
    assert not errores
    pagina.context.close()


def test_el_inicio_son_las_herramientas_por_area(navegador, sitio):
    """Pedido del 2026-11-10: el Inicio con las herramientas de cada área, con sus íconos nuevos; sin la franja «Hoy»,
    cifras ni gráficos. De la carpeta viene, desde el 2026-11-18, la semana de la Planificación bajo las áreas
    (test_el_inicio_muestra_la_semana_de_la_planificacion). La alarma de los sin asignar ya no va en su botón
    (pedido del 2026-11-18): sigue en el menú."""
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC", ancho=1366, alto=657)
    pagina.locator(ALERTA_N).wait_for(state="attached")
    assert pagina.locator(ALERTA_N).inner_text() == "3"
    assert pagina.locator("#iniAreas .pl-alerta-n").count() == 0, "sin alarma en el Inicio"
    assert pagina.locator("#tituloInicio b").inner_text() == "LC" and pagina.locator("#iniQuien").is_hidden()
    # Cuatro áreas de a dos, cada herramienta con su propio ícono (el mismo de su pestaña)
    assert pagina.evaluate("getComputedStyle(document.getElementById('iniAreas')).gridTemplateColumns.split(' ').length") == 2
    reg = _registro()
    for g in ("ofertar", "ejecutar", "controlar", "calcular"):
        ids = pagina.locator(f'.ini-area[data-grupo="{g}"] .ini-item').evaluate_all("bs => bs.map((b) => b.dataset.herr)")
        assert ids == [h["id"] for h in reg["herramientas"] if h["grupo"] == g], g
    iconos = [h.get("icono") for h in reg["herramientas"] if h["grupo"] in {"ofertar", "ejecutar", "controlar", "calcular"}]
    assert all(iconos) and len(set(iconos)) == len(iconos), "cada herramienta con su propio ícono"
    portal = texto_portal()
    assert all(f"\n  {i}: '" in portal.replace("\r\n", "\n") for i in iconos), "un ícono del registro que no está en ICONOS"
    assert pagina.locator("#iniAreas .ini-item .ini-ico svg path, #iniAreas .ini-item .ini-ico svg circle, #iniAreas .ini-item .ini-ico svg rect").count() > 19
    # Nada de lo de antes: ni «Hoy», ni cifras, ni gráficos
    assert pagina.locator("#iniHoy, #iniEmbudo, #iniSalud, .ini-cifra, .ini-pri").count() == 0
    # Un botón abre su herramienta
    pagina.locator('.ini-item[data-herr="planificacion"]').click()
    assert pagina.locator("#vistaPlan").is_visible()
    # Sin usuario: las iniciales para elegirse con un clic
    pagina.locator("#pestanas .ir").first.click()
    pagina.locator("#btnUsuario").click()
    pagina.locator("#sinUsuario").click()
    assert pagina.locator("#iniQuien button").all_inner_texts() == ["NB", "ES", "LC", "CM", "MP"]
    pagina.locator('#iniQuien button[data-usuario="CM"]').click()
    assert pagina.evaluate("localStorage.getItem('quempin_usuario')") == "CM" and pagina.locator("#tituloInicio b").inner_text() == "CM"
    assert not errores
    pagina.context.close()


def test_el_inicio_muestra_la_semana_de_la_planificacion(navegador, sitio):
    """2026-11-18, el usuario eligió la maqueta V4: bajo las áreas, la semana de hoy, un día por columna con sus
    proyectos (los de más gente primero; todos desde el 2026-11-19, sin «+N más») y cuántas personas tienen algo. Un día abre la Planificación con
    ese día en grande; «Abrir», la Planificación."""
    from datetime import date
    pagina, errores = _inicio_con_semana(navegador, sitio, ancho=1366, alto=657)
    dias = pagina.locator("#iniSemana .ini-sem-dia")
    assert dias.count() == 5
    hoy = date.today().weekday()
    assert dias.evaluate_all("bs => bs.map((b) => b.classList.contains('hoy'))") == [i == hoy for i in range(5)]
    lun = dias.nth(0)
    assert lun.locator(".ini-sem-n").inner_text() == "6 pers."
    filas = lun.locator(".ini-sem-pr").evaluate_all("fs => fs.map((f) => [f.children[1].textContent, f.children[2].textContent])")
    assert len(filas) == 4 and filas[0] == ["En obra", "3"], filas
    assert lun.locator(".ini-sem-pr:visible").count() == 4 and "más" not in lun.inner_text()
    assert "6 personas en 4 proyectos" in lun.get_attribute("title") and "Bodega, 1" in lun.get_attribute("title")
    assert dias.nth(1).locator(".ini-sem-nadie").inner_text() == "Nadie asignado"
    assert dias.nth(2).locator(".ini-sem-n").inner_text() == "2 pers."
    # Un día abre la Planificación en General con ese día en grande, aunque la última vista elegida fuera otra
    pagina.evaluate("localStorage.setItem('quempin_portal_plan', JSON.stringify({ v: 2, vista: 'personal' }))")
    pagina.reload()
    dias.first.wait_for()
    dias.nth(2).click()
    assert pagina.locator("#vistaPlan").is_visible()
    pagina.locator("#plGeneral .pl-dia-grande").wait_for()
    assert pagina.locator("#plGeneral .pl-dia-grande").get_attribute("data-dia") == "2"
    # «Abrir» va a la Planificación
    pagina.locator("#pestanas .ir", has_text="Inicio").click()
    pagina.locator("#iniSemAbrir").click()
    assert pagina.locator("#vistaPlan").is_visible()
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho, alto", [(1366, 657), (1536, 730), (1280, 600), (1024, 640), (390, 844)])
def test_la_semana_cabe_en_el_inicio(navegador, sitio, ancho, alto):
    """Con la semana planificada, el Inicio sigue sin barras en el computador; en el teléfono, un día por fila."""
    movil = ancho < 760
    pagina, errores = _inicio_con_semana(navegador, sitio, ancho=ancho, alto=alto, movil=movil)
    pagina.wait_for_timeout(200)
    if not movil:
        assert pagina.evaluate(JS_BARRAS) == []
    d = pagina.evaluate(JS_DESBORDES)
    assert d["doc"] <= ancho and not d["fuera"], d
    xs = pagina.locator("#iniSemana .ini-sem-dia").evaluate_all("bs => bs.map((b) => Math.round(b.getBoundingClientRect().left))")
    assert len(set(xs)) == (1 if movil else 5), xs
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho, alto", [(1366, 657), (1536, 730), (1024, 640), (1280, 600), (390, 844)])
def test_las_herramientas_caben_en_el_inicio(navegador, sitio, ancho, alto):
    """Sin barras en el computador; en el teléfono, una columna que no se sale por el lado. Ningún texto bajo 12 px, y
    desde 1280 px los nombres caben enteros (más angosto, los de una palabra larga se cortan en una sílaba)."""
    movil = ancho < 760
    pagina, errores = _abrir_portal(navegador, sitio, ancho=ancho, alto=alto, movil=movil)
    pagina.locator("#iniAreas .ini-item").first.wait_for()
    pagina.wait_for_timeout(200)
    if not movil:
        assert pagina.evaluate(JS_BARRAS) == []
    columnas = "getComputedStyle(document.getElementById('iniAreas')).gridTemplateColumns.split(' ').length"
    assert pagina.evaluate(columnas) == (1 if movil else 2)
    if ancho >= 1280:
        cortados = pagina.evaluate("""() => [...document.querySelectorAll('#iniAreas .ini-nom')].filter((n) => {
            const una = !n.textContent.includes(' ');
            return una && n.getClientRects().length > 0 && n.getBoundingClientRect().height > parseFloat(getComputedStyle(n).lineHeight) * 1.5;
        }).map((n) => n.textContent)""")
        assert not cortados, cortados
    d = pagina.evaluate(JS_DESBORDES)
    assert d["doc"] <= ancho and not d["fuera"], d
    derecha = pagina.evaluate("""() => Math.max(...[...document.querySelectorAll('#vistaInicio *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))""")
    assert derecha <= ancho + 0.5, derecha
    chicos = pagina.evaluate("""() => [...document.querySelectorAll('#vistaInicio *')]
        .filter((e) => e.getClientRects().length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
        .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12).map((e) => e.className || e.tagName)""")
    assert not chicos, chicos
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [390, 1024])
def test_el_recorrido_cabe_sin_desbordes(navegador, sitio, ancho):
    movil = ancho < 760
    pagina, errores = _recorrido_con_datos(navegador, sitio, usuario="LC", ancho=ancho, alto=844, movil=movil)
    d = pagina.evaluate(JS_DESBORDES)
    assert d["doc"] <= ancho and not d["fuera"], d
    derecha = pagina.evaluate("""() => Math.max(...[...document.querySelectorAll('#vistaRecorrido *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))""")
    assert derecha <= ancho + 0.5, derecha
    chicos = pagina.evaluate("""() => [...document.querySelectorAll('#vistaRecorrido *')]
        .filter((e) => e.getClientRects().length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
        .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12).map((e) => e.className || e.tagName)""")
    assert not chicos, chicos
    columnas = "getComputedStyle(document.getElementById('rcTablero')).gridTemplateColumns.split(' ').length"
    assert pagina.evaluate(columnas) == (1 if movil else 3)
    if movil:
        assert pagina.evaluate("parseFloat(getComputedStyle(document.getElementById('rcBuscar')).fontSize)") >= 16
    pagina.locator('.rc-tarjeta[data-clave="req-908"] .rc-abrir').click()
    caja = pagina.locator("#dlgRecorrido").bounding_box()
    assert caja["x"] >= 0 and caja["x"] + caja["width"] <= ancho, caja
    assert not errores
    pagina.context.close()
