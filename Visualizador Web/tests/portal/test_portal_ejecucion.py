# -*- coding: utf-8 -*-
"""Portal QUEMPIN: Proyectos en ejecución.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- Proyectos en ejecución (2026-10-28) ------------------------------------------------------------------------------
# Pedido del usuario: el resumen de cada proyecto en ejecución, con su carpeta de Gestión de Proyectos; costos potenciales
# desde cotizaciones reales que se evalúan y se simulan al tiro (no van al Centro de Costos); el avance, que llega a las
# demás herramientas; los días trabajados para estimar la mano de obra real, y los indicadores por día-hombre.


def test_proyectos_en_ejecucion_en_el_registro_y_en_el_esquema():
    reg = _registro()
    h = next(x for x in reg["herramientas"] if x["id"] == "ejecucion")
    assert (h["grupo"], h["tipo"], h["vista"]) == ("ejecutar", "vista", "vistaEjecucion")
    assert [x["id"] for x in reg["herramientas"] if x["grupo"] == "ejecutar"][:2] == ["ejecucion", "planificacion"]
    assert "ejecucion-proyectos" in _esquemas().publicaciones()
    # Lo que carga del Formulador: la ruta que pide el portal y, si el Formulador está en este equipo, el nombre que exporta
    html = texto_portal()
    formulador = _hermano("Formulación de proyectos")
    for nombre, glob in FORMULADOR_JS.items():
        assert "js/" + nombre in html, nombre
        if formulador:
            assert glob in (formulador / "quempin-formulacion" / "js" / nombre).read_text(encoding="utf-8"), nombre
    # Las categorías son las del Análisis Financiero (las mismas claves de datos-proyecto y presupuesto-proyecto)
    cats = _esquemas().cargar("publicaciones/ejecucion-proyectos")["properties"]["items"]["items"]["properties"]["categoria"]["enum"]
    assert cats == ["Materiales", "Equipos", "Mano de Obra", "Otros"]
    assert all(f"k: '{c}'" in html for c in cats)


def test_proyectos_en_ejecucion_sin_biblioteca_dice_que_conectar(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Proyectos en ejecución")
    pagina.locator("#ejVacio").wait_for()
    texto = pagina.locator("#ejVacio").inner_text()
    assert "Conecta" in texto or "Chrome o Edge" in texto
    assert pagina.locator("#ejLista").is_hidden() and pagina.locator("#ejProyecto").is_hidden()
    assert not errores
    pagina.context.close()


def test_proyectos_en_ejecucion_lista_y_resumen(navegador, sitio):
    pagina, errores = _ejecucion_con_datos(navegador, sitio)
    claves = lambda: pagina.locator("#ejTarjetas .ej-tarjeta").evaluate_all("bs => bs.map((b) => b.dataset.clave)")
    # Los que el Recorrido pone en Ejecución; el terminado (909) no, y el adjudicado hace mucho (910) va plegado abajo
    assert {"req-908", "req-907", "tag-SOLO"} <= set(claves()) and "req-909" not in claves() and "req-910" not in claves()
    assert "req-910" in pagina.locator("#ejTarjetasAntiguas .ej-tarjeta").evaluate_all("bs => bs.map((b) => b.dataset.clave)")
    assert claves()[0] == "req-908", "lo de LC primero"
    assert "Margen estimado 33 %" in pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="req-908"]').inner_text()
    pagina.locator("#ejBuscar").fill("sin número")
    assert claves() == ["tag-SOLO"]
    pagina.locator("#ejBuscar").fill("")
    pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="req-908"]').click()
    pagina.locator("#ejProyecto .ej-kpis").wait_for()
    # Venta de su formulación; costo estimado = lo presupuestado (nada se pasa todavía); margen y avance del Análisis
    assert pagina.evaluate(JS_EJ_KPIS) == {"Venta neta": "$3.750.000", "Gastado a la fecha": "$350.000", "Costo estimado al cierre": "$2.500.000",
                                            "Margen estimado": "33 %", "Avance": "40 %"}
    # Materiales: lo gastado más la OC que el Centro de Costos todavía no trae; la que ya está ahí y la que no se sabe no suman
    assert pagina.evaluate(JS_EJ_COMO, "Materiales") == {"Presupuestado": "$1.000.000", "Gastado": "$300.000", "Comprometido": "$120.000",
                                                         "Simulado": "—", "Al cierre": "$1.000.000", "Queda": "$580.000"}
    estados = pagina.locator("#ejProyecto .ej-ocs li").evaluate_all("ls => ls.map((l) => [l.dataset.folio, l.querySelector('.rc-chip').textContent])")
    assert estados == [["612902", "Por confirmar"], ["612900", "Comprometida"], ["612901", "En el gasto"]]
    # Su carpeta de Gestión de Proyectos, con QUEMPIN.exe
    # Sin accesos al Centro de Costos, al Análisis Financiero ni a la Carta Gantt (2026-11-06)
    accesos = pagina.locator("#ejProyecto .ej-cab .cx-acc button").all_inner_texts()
    assert accesos[0] == "Carpeta del proyecto" and not {"Centro de Costos", "Análisis Financiero", "Carta Gantt"} & set(accesos), accesos
    pagina.locator("#ejProyecto .ej-cab .cx-boton", has_text="Carpeta del proyecto").click()
    assert pagina.evaluate("window.__lanzados")[-1] == "quempin://carpeta/gestion/908.%20En%20obra"
    # Quién va esta semana sale de la Planificación semanal
    assert "ES y LC" in pagina.locator("#ejProyecto .ej-equipo").inner_text()
    pagina.locator(".ej-volver").click()
    pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="req-908"]').wait_for()
    assert not errores
    pagina.context.close()


def test_el_mapa_de_salud_ubica_cada_proyecto_y_filtra_por_estado(navegador, sitio):
    """Pedido del usuario (2026-11-09): una herramienta para seguir el estado de cada proyecto y una pestaña más visual.
    El 908 va en línea (40 % de avance, 14 % gastado y comprometido, margen sobre la meta); el que no tiene N° pide atención;
    el 907, sin presupuesto ni avance, queda fuera del mapa en «Sin datos»."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio)
    pagina.locator("#ejMapa .punto").first.wait_for()
    puntos = pagina.locator("#ejMapa .punto").evaluate_all("gs => gs.map((g) => [g.dataset.clave, g.dataset.nivel])")
    assert ["req-908", "ok"] in puntos and not any(c == "req-907" for c, _ in puntos), puntos
    cuentas = pagina.locator("#ejMapa .ej-estado-fil").evaluate_all("bs => Object.fromEntries(bs.map((b) => [b.dataset.nivel, b.dataset.cuenta]))")
    assert cuentas == {"bad": "0", "warn": "1", "ok": "1", "sin": "1"}, cuentas
    assert "N° 907" in pagina.locator("#ejMapa .ej-mapa-nota").inner_text()
    # La tarjeta dice su estado con palabra, no solo con color
    assert "En línea" in pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="req-908"] .ej-salud').inner_text()
    # La leyenda filtra las tarjetas y se vuelve a tocar para ver todas
    pagina.locator('#ejMapa .ej-estado-fil[data-nivel="sin"]').click()
    claves = lambda: pagina.locator("#ejTarjetas .ej-tarjeta").evaluate_all("bs => bs.map((b) => b.dataset.clave)")
    assert claves() == ["req-907"]
    assert pagina.locator('#ejMapa .ej-estado-fil[data-nivel="sin"]').get_attribute("aria-pressed") == "true"
    pagina.locator('#ejMapa .ej-estado-fil[data-nivel="sin"]').click()
    assert "req-908" in claves()
    # Pasar sobre un punto dice por qué y resalta su tarjeta; tocarlo abre el proyecto
    pagina.locator('#ejMapa .punto[data-clave="req-908"]').hover()
    assert "Avance 40 %" in pagina.locator("#ejMapa .ej-mapa-tip").inner_text()
    assert "resalta" in pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="req-908"]').get_attribute("class")
    pagina.locator('#ejMapa .punto[data-clave="req-908"]').click()
    pagina.locator("#ejProyecto .ej-kpis").wait_for()
    assert not errores
    pagina.context.close()


def test_por_hacer_dice_lo_que_espera_el_proyecto_y_lo_hace_ahi_mismo(navegador, sitio):
    """Vuelta 3 del loop de UX (2026-11-09): al abrir un proyecto, primero lo que está esperando de alguien, con su botón."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=_documentos_908)
    tareas = lambda: pagina.locator("#ejProyecto .ej-porhacer .ej-tarea").evaluate_all("ls => ls.map((l) => l.dataset.tarea)")
    pagina.wait_for_function("() => document.querySelectorAll('#ejProyecto .ej-porhacer .ej-tarea').length > 0")
    # Desplegable (2026-11-10): cerrado de entrada, con lo que espera resumido; abierto se queda abierto al repintar
    assert pagina.locator("#ejProyecto details.ej-porhacer").get_attribute("open") is None
    assert "facturas sin asociar" in pagina.locator("#ejProyecto .ej-porhacer-res").inner_text()
    pagina.locator("#ejProyecto .ej-porhacer > summary").click()
    assert {"facturas", "traer"} <= set(tareas()), tareas()
    assert "2 facturas sin asociar" in pagina.locator('#ejProyecto .ej-tarea[data-tarea="facturas"]').inner_text()
    # «Asociar» deja a la vista solo las facturas sin asociar
    pagina.locator('#ejProyecto .ej-tarea[data-tarea="facturas"] button').click()
    pagina.wait_for_function("() => [...document.querySelectorAll('#ejProyecto .ej-filtro')].some((b) => b.textContent.startsWith('Sin asociar') && b.getAttribute('aria-pressed') === 'true')")
    # «Traerlos» anota los días de la Planificación y la tarea se va
    pagina.locator('#ejProyecto .ej-tarea[data-tarea="traer"] button').click()
    _esperar_archivo(pagina, EJ, lambda s: sum(1 for x in s["datos"]["items"] if x["tipo"] == "dia" and x.get("origen") == "planificacion") == 2)
    pagina.wait_for_function("() => !document.querySelector('#ejProyecto .ej-tarea[data-tarea=\"traer\"]')")
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [420, 760, 1280])
def test_la_lista_de_por_hacer_no_se_sale_de_la_columna(navegador, sitio, ancho):
    """2026-11-12, pedido del usuario: la lista flotante de «Por hacer» se cortaba por la izquierda (medía 460 px y se
    anclaba al botón, más angosto). Ahora se ancla a la fila de arriba y nunca pasa del ancho de la columna."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=_documentos_908, ancho=ancho)
    pagina.locator("#ejProyecto .ej-porhacer > summary").click()
    pagina.locator("#ejProyecto .ej-porhacer > ul").wait_for()
    caja = pagina.evaluate("""() => {
        const l = document.querySelector('#ejProyecto .ej-porhacer > ul').getBoundingClientRect();
        const c = document.querySelector('#ejProyecto .ej-v2-arriba').getBoundingClientRect();
        return { izq: l.left, der: l.right, cizq: c.left, cder: c.right };
    }""")
    assert caja["izq"] >= caja["cizq"] - 1 and caja["der"] <= caja["cder"] + 1, caja
    assert caja["izq"] >= 0, caja
    assert not errores
    pagina.context.close()


def test_los_accesos_marcan_la_parte_a_la_vista_y_las_cifras_llevan_su_grafico(navegador, sitio):
    """Vuelta 5 del loop de UX (2026-11-09)."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=_documentos_908, alto=700)
    actual = lambda: pagina.evaluate("() => (document.querySelector('#ejProyecto .ej-salto[aria-current=\"true\"]') || {}).dataset?.sec || null")
    # En la página nueva (2026-11-12) el índice va al costado: arriba de todo marca el resumen
    assert actual() == "ejSecResumen", "arriba de todo, el resumen"
    pagina.locator("#ejProyecto .ej-salto", has_text="Facturas").click()
    pagina.wait_for_function("() => (document.querySelector('#ejProyecto .ej-salto[aria-current=\"true\"]') || {}).dataset?.sec === 'ejSecFacturas'")
    # Gastado, costo al cierre, margen y avance llevan su barra chica; la venta no
    con = pagina.locator("#ejProyecto .ej-kpi").evaluate_all("ks => ks.map((k) => [k.querySelector('.ej-kpi-et').textContent, !!k.querySelector('.ej-mini')])")
    assert dict(con) == {"Venta neta": False, "Gastado a la fecha": True, "Costo estimado al cierre": True, "Margen estimado": True, "Avance": True}, con
    assert not errores
    pagina.context.close()


def test_la_pagina_del_proyecto_tiene_todos_los_proyectos_arriba_del_indice(navegador, sitio):
    """2026-11-12, pedido del usuario: un resumen grande, un índice angosto que se pliega, «Por hacer» como un botón chico
    arriba. Después (mismo día): la página anterior se eliminó y «Todos los proyectos» es lo primero del índice lateral."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=_documentos_908)
    assert pagina.locator("#ejProyecto.ej-v2 #ejSecResumen .ej-v2-medidor").count() == 1
    assert pagina.locator("#ejSecResumen .ej-v2-barra").is_visible()
    assert pagina.locator("#ejSecResumen .ej-v2-raya").inner_text().startswith("Avance")
    # Las cifras de abajo: la venta y el cierre (las KPI de siempre) más lo comprometido y la mano de obra
    visibles = pagina.locator("#ejSecResumen .ej-kpis > *").evaluate_all(
        "ks => ks.filter((k) => k.offsetParent).map((k) => k.querySelector('.ej-kpi-et').textContent)")
    assert visibles == ["Venta neta", "Costo estimado al cierre", "Comprometido en OC", "Mano de obra real"], visibles
    # «Por hacer» va en la fila de arriba, cerrado
    assert pagina.locator("#ejProyecto .ej-v2-arriba details.ej-porhacer").get_attribute("open") is None
    # Lo que espera se ve como número en el índice
    assert pagina.locator("#ejProyecto .ej-salto[data-sec='ejSecFacturas'] .ej-hay").count() == 1
    # El índice se pliega a íconos
    pagina.locator(".ej-idx-plegar").click()
    pagina.wait_for_function("() => document.querySelector('#ejProyecto').classList.contains('ej-plegado')")
    assert not pagina.locator("#ejProyecto .ej-salto[data-sec='ejSecFacturas'] > span").is_visible()
    # «Todos los proyectos» es el primer elemento del índice (incluso plegado, solo con ícono) y no hay página anterior
    assert pagina.locator("#ejProyecto .ej-v2-idx > :first-child").evaluate("e => e.classList.contains('ej-volver')")
    assert pagina.locator("#ejProyecto .ej-v2-idx .ej-volver").is_visible()
    assert pagina.locator("#ejProyecto .ej-v2-arriba .ej-volver").count() == 0
    assert pagina.locator(".ej-cambiar-vista").count() == 0
    assert "vistaAnterior" not in json.loads(pagina.evaluate("() => localStorage.getItem('quempin_portal_ejecucion')"))
    assert not errores
    pagina.context.close()


def test_el_avance_se_cambia_con_botones_rapidos_y_el_boton_dice_que_guarda(navegador, sitio):
    """Vuelta 6 del loop de UX (2026-11-09): sin cambios no se guarda; +10 muestra 40 % → 50 % y lo guarda."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    boton = pagina.locator("#ejProyecto .ej-av-form .cx-boton")
    pagina.wait_for_function("() => document.querySelector('#ejProyecto .ej-av-form .cx-boton').disabled")
    assert boton.inner_text() == "Sin cambios que guardar"
    pagina.locator("#ejProyecto .ej-av-chip", has_text="+10").click()
    assert pagina.locator("#ejAvNum").input_value() == "50"
    assert pagina.locator("#ejAvCambio").inner_text() == "→ 50 %"
    assert pagina.locator("#ejAvPrevia").is_visible()
    assert boton.inner_text() == "Guardar 50 % en el Análisis Financiero" and boton.is_enabled()
    # «Como estaba» vuelve atrás
    pagina.locator("#ejProyecto .ej-av-chip", has_text="Como estaba").click()
    assert pagina.locator("#ejAvNum").input_value() == "40" and boton.is_disabled()
    pagina.locator("#ejProyecto .ej-av-chip", has_text="+10").click()
    boton.click()
    _esperar_aviso(pagina, "Avance 50 %")
    assert not errores
    pagina.context.close()


def test_la_mano_de_obra_se_ve_en_grafico_y_el_calendario_se_abre_al_anotar(navegador, sitio):
    """Vuelta 7 del loop de UX (2026-11-09): con días anotados, arriba lo trabajado por persona y el calendario plegado."""
    from datetime import date, timedelta
    ayer = (date.today() - timedelta(days=1)).isoformat()

    def con_dias(archivos):
        archivos["publicado/ejecucion/otronavegador1.json"] = json.loads(_sobre_de_otro(*[
            {"id": f"dia-{p.lower()}-{ayer}", "proyecto": "req:908", "tipo": "dia", "t": _instante(-60), "por": "LC", "persona": p, "fecha": ayer,
             "jornada": j, "nivel": 2} for p, j in (("ES", 1), ("LC", 0.5))])[1])
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=con_dias)
    pagina.locator("#ejProyecto .ej-mo-pers li").first.wait_for()
    pers = pagina.locator("#ejProyecto .ej-mo-pers li").all_inner_texts()
    assert pers[0].startswith("ES") and "1 DH" in pers[0] and "0,5 DH" in pers[1], pers
    assert "1,5 DH" in pagina.locator("#ejProyecto .ej-mo-num").inner_text()
    assert pagina.locator("#ejCalCaja").is_hidden()
    pagina.locator("#ejProyecto .ej-cal-abrir").click()
    pagina.locator("#ejCalCaja").wait_for()
    assert pagina.locator("#ejProyecto .ej-cal-abrir").get_attribute("aria-expanded") == "true"
    assert not errores
    pagina.context.close()


def test_las_facturas_y_las_compras_se_resumen_en_barras(navegador, sitio):
    """Vuelta 8 del loop de UX (2026-11-09): cuánto de lo facturado está asociado y las compras por estado, que filtran."""
    def con_todo(archivos):
        _documentos_908(archivos)
        archivos["publicado/ejecucion/otronavegador1.json"] = json.loads(_sobre_de_otro(
            _item_de_prueba("cgrupouno00001", "Ferretería Uno", 210000, grupo="cgrupouno00001"),
            _item_de_prueba("cgrupodos00001", "Aceros Dos", 500000, grupo="cgrupodos00001", estado="comprada"))[1])
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=con_todo)
    pagina.locator("#ejProyecto .ej-prog").wait_for()
    assert pagina.locator("#ejProyecto .ej-prog-txt").inner_text().startswith("0 asociadas de 2")
    et = lambda e: pagina.locator(f'#ejProyecto .ej-embudo-et[data-estado="{e}"]')
    assert "$210.000" in et("evaluar").inner_text() and "$500.000" in et("comprada").inner_text()
    assert et("aprobada").is_disabled()
    et("comprada").click()
    pagina.wait_for_function("() => [...document.querySelectorAll('#ejSecGastos .ej-filtro')].some((b) => b.textContent.startsWith('Compradas') && b.getAttribute('aria-pressed') === 'true')")
    assert not errores
    pagina.context.close()


def test_lo_que_espera_al_equipo_se_cuenta_y_filtra_la_lista(navegador, sitio):
    """Vuelta 11 del loop de UX (2026-11-09): sobre las tarjetas, lo que espera en todos los proyectos; tocarlo filtra."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, cambiar=_documentos_908)
    pagina.locator('#ejEspera [data-espera="facturas"]').wait_for()
    assert " ".join(pagina.locator('#ejEspera [data-espera="facturas"]').inner_text().split()) == "2 facturas sin asociar en 1 proyecto"
    pagina.locator('#ejEspera [data-espera="facturas"]').click()
    claves = lambda: pagina.locator("#ejTarjetas .ej-tarjeta").evaluate_all("bs => bs.map((b) => b.dataset.clave)")
    assert claves() == ["req-908"]
    pagina.locator('#ejEspera [data-espera="facturas"]').click()
    assert len(claves()) > 1
    assert not errores
    pagina.context.close()


def test_todos_los_proyectos_de_gestion_de_proyectos_se_ven_en_ejecucion(navegador, sitio):
    """Pedido del usuario (2026-11-03): todos los proyectos de la carpeta de Gestión de Proyectos se ven en «Proyectos en
    ejecución», sin las carpetas complementarias (esas las deja fuera el procesador: proyectos_en_gestion)."""
    def en_gestion(archivos):
        archivos["publicado/proyectos.json"]["datos"]["gestion"] = [
            {"carpeta": "905. Oferta esperando", "req": "905"},          # la Planilla todavía dice «Ofertado»
            {"carpeta": "909. Terminada", "req": "909"},                 # 100 % de avance en el Análisis Financiero
            {"carpeta": "910. Adjudicada hace mucho", "req": "910"},     # iba plegada por antigua
            {"carpeta": "Obra sin número - Valparaíso", "req": None},    # la ficha SOLO del Análisis, por el nombre
            {"carpeta": "Rengo Incinerador", "req": None}]               # sin N° ni nada que se le parezca
    pagina, errores = _ejecucion_con_datos(navegador, sitio, cambiar=en_gestion)
    claves = lambda sel: pagina.locator(sel + " .ej-tarjeta").evaluate_all("bs => bs.map((b) => b.dataset.clave)")
    vivas = claves("#ejTarjetas")
    assert {"req-905", "req-909", "req-910", "tag-SOLO", "gestion-Rengo Incinerador"} <= set(vivas)
    assert "req-910" not in claves("#ejTarjetasAntiguas"), "lo que está en Gestión no va plegado"
    assert vivas[-1] == "req-909", "lo que ya terminó, al final"
    assert [c for c in vivas if c.startswith("gestion-")] == ["gestion-Rengo Incinerador"], "«Obra sin número» no se repite: es SOLO"
    assert "no lleva el N°" in pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="gestion-Rengo Incinerador"]').inner_text()
    avisos = lambda: pagina.locator("#ejProyecto .rc-avisos").inner_text()

    def resumen(clave):
        pagina.locator(f'#ejTarjetas .ej-tarjeta[data-clave="{clave}"]').click()
        pagina.locator("#ejProyecto .ej-cab").wait_for()

    def carpeta():
        pagina.locator("#ejProyecto .ej-cab .cx-boton", has_text="Carpeta del proyecto").click()
        return pagina.evaluate("window.__lanzados")[-1]

    resumen("req-905")
    assert "la Planilla de Ingreso dice «Ofertado» para el N° 905" in avisos()
    assert carpeta() == "quempin://carpeta/gestion/905.%20Oferta%20esperando"
    pagina.locator(".ej-volver").click()
    resumen("req-909")
    assert "Ya no está en ejecución" in pagina.locator("#ejProyecto .ej-cab").inner_text()
    assert "su carpeta sigue en la raíz de Gestión de Proyectos" in avisos()
    pagina.locator(".ej-volver").click()
    resumen("tag-SOLO")
    assert carpeta() == "quempin://carpeta/gestion/Obra%20sin%20n%C3%BAmero%20-%20Valpara%C3%ADso"
    assert "se reconoció por el nombre" in avisos()
    pagina.locator(".ej-volver").click()
    # Sin N° ni TAG no hay a qué anotarle nada: su carpeta y cómo unirla, sin cifras ni compras
    resumen("gestion-Rengo Incinerador")
    assert pagina.locator("#ejProyecto .ej-sin-clave").is_visible()
    assert pagina.locator("#ejProyecto .ej-kpis, #ejProyecto .ej-compras").count() == 0
    assert carpeta() == "quempin://carpeta/gestion/Rengo%20Incinerador"
    # El Recorrido cuenta lo mismo: lo que está en Gestión va en Ejecución
    _menu(pagina, "Recorrido de proyectos")
    pagina.locator("#rcTablero .rc-tarjeta").first.wait_for()
    col = pagina.evaluate(JS_COLUMNAS)
    assert {"req-905", "req-910", "tag-SOLO", "gestion-Rengo Incinerador"} <= set(col["ejecucion"]) and "req-905" not in col["oferta"]
    assert not errores
    pagina.context.close()


def test_ejecucion_solo_lo_de_gestion_y_los_entregados_en_su_pestana(navegador, sitio):
    """Pedido del usuario (2026-11-09): en «Proyectos en ejecución» solo los proyectos con carpeta en Gestión de
    Proyectos; los de «0 Proyectos Entregados <año>», en una segunda pestaña; y una casilla para ver solo los que tienen
    al menos un dato anotado en su resumen."""
    def carpetas(archivos):
        datos = archivos["publicado/proyectos.json"]["datos"]
        datos["gestion"] = [{"carpeta": "908. En obra", "req": "908"}, {"carpeta": "905. Oferta esperando", "req": "905"}]
        datos["entregados"] = [{"carpeta": "909. Terminada", "req": "909", "grupo": "0 Proyectos Entregados 2026"},
                               {"carpeta": "AGCID", "req": None, "grupo": "0 Proyectos Entregados 2025"}]
        # 908 tiene un día anotado en su resumen; 905, 909 y AGCID, nada
        archivos["publicado/ejecucion/otronavegador1.json"] = json.loads(_sobre_de_otro(
            {"id": "dia-es-2026-11-02", "proyecto": "req:908", "tipo": "dia", "t": _instante(-60), "por": "LC", "persona": "ES",
             "fecha": "2026-11-02", "jornada": 1, "nivel": 2})[1])
    pagina, errores = _ejecucion_con_datos(navegador, sitio, cambiar=carpetas)
    claves = lambda: pagina.locator("#ejTarjetas .ej-tarjeta, #ejTarjetasAntiguas .ej-tarjeta").evaluate_all("bs => bs.map((b) => b.dataset.clave)")
    pestana = lambda p: pagina.locator(f'#ejPestanas [data-pestana="{p}"]')
    # En ejecución: solo lo que tiene carpeta en la raíz (910 está adjudicado, pero sin carpeta en Gestión)
    assert sorted(claves()) == ["req-905", "req-908"]
    assert pestana("ejecucion").get_attribute("aria-selected") == "true"
    assert pestana("ejecucion").locator("b").inner_text() == "2" and pestana("entregados").locator("b").inner_text() == "2"
    # Solo con datos anotados
    pagina.locator("#ejConDatos").check()
    pagina.wait_for_function("document.querySelectorAll('#ejTarjetas .ej-tarjeta').length === 1")
    assert claves() == ["req-908"] and pestana("ejecucion").locator("b").inner_text() == "1"
    # Entregados: con N° (se une con su proyecto) y sin N° (va aparte); sin datos anotados no queda ninguno
    pestana("entregados").click()
    assert pestana("entregados").get_attribute("aria-selected") == "true"
    assert claves() == [] and "Quita «Solo con datos anotados»" in pagina.locator("#ejTarjetas").inner_text()
    pagina.locator("#ejConDatos").uncheck()
    pagina.wait_for_function("document.querySelectorAll('#ejTarjetas .ej-tarjeta').length === 2")
    assert sorted(claves()) == ["entregado-AGCID", "req-909"], "lo entregado no se pliega por antiguo"
    # Se recuerda en este navegador
    assert pagina.evaluate("JSON.parse(localStorage.getItem('quempin_portal_ejecucion')).pestana") == "entregados"
    # Su resumen: su carpeta, dentro de la del año; sin N°, cómo unirla. Al volver, sigue en Entregados
    pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="entregado-AGCID"]').click()
    pagina.locator("#ejProyecto .ej-cab").wait_for()
    assert pagina.locator("#ejProyecto .ej-sin-clave").is_visible()
    assert "«AGCID»" in pagina.locator("#ejProyecto .ej-sin-clave").inner_text()
    pagina.locator("#ejProyecto .ej-cab .cx-boton", has_text="Carpeta del proyecto").click()
    assert pagina.evaluate("window.__lanzados")[-1] == "quempin://carpeta/gestion/0%20Proyectos%20Entregados%202025/AGCID"
    pagina.locator(".ej-volver").click()
    pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="req-909"]').wait_for()
    # Con el teclado: las flechas cambian de pestaña
    pestana("entregados").focus()
    pagina.keyboard.press("ArrowLeft")
    assert pestana("ejecucion").get_attribute("aria-selected") == "true"
    assert pagina.evaluate("document.activeElement.dataset.pestana") == "ejecucion"
    # El Recorrido no muestra la carpeta entregada suelta
    _menu(pagina, "Recorrido de proyectos")
    pagina.locator("#rcTablero .rc-tarjeta").first.wait_for()
    assert not any("entregado-" in c for cs in pagina.evaluate(JS_COLUMNAS).values() for c in cs)
    assert not errores
    pagina.context.close()


def test_una_cotizacion_cambia_el_costo_y_el_margen_al_tiro(navegador, sitio):
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    pagina.locator("#ejProyecto .ej-compras .cx-boton").click()
    pagina.locator("#dlgEjCosto").wait_for()
    pagina.locator("#ejCDesc").fill("Estanque inoxidable 100 L")
    _escribir_prov(pagina, 0, "Inox Demo", "950.000")
    evaluacion = pagina.locator("#ejCEval").inner_text()
    assert "Total $950.000 sin IVA" in evaluacion
    assert "materiales se pasa del presupuesto en $370.000" in evaluacion
    if _con_formulador_js("calc.js"):
        # La línea más parecida del presupuesto de su formulación, con su costo unitario
        assert pagina.locator("#ejCLineas .ej-lin").all_inner_texts() == ["M1 (P1) · Estanque inoxidable 100 L $800.000"]
        assert "Presupuestado $800.000 c/u en M1" in evaluacion and "19 % más cara" in evaluacion
    assert pagina.locator("#ejCEval .ej-eval-chip").inner_text() == "No conviene"
    pagina.locator("#ejCGuardar").click()
    pagina.locator("#dlgEjCosto").wait_for(state="hidden")
    _esperar_kpi(pagina, "Margen estimado", "23 %")
    assert pagina.evaluate(JS_EJ_KPIS)["Costo estimado al cierre"] == "$2.870.000"
    sobre = _esperar_archivo(pagina, EJ, lambda s: len(s["datos"]["items"]) == 1)
    it = sobre["datos"]["items"][0]
    assert (it["tipo"], it["proyecto"], it["categoria"], it["precio"], it["estado"], it["simular"]) == ("costo", "req:908", "Materiales", 950000, "evaluar", True)
    assert _esquemas().validar_publicacion("ejecucion-proyectos", sobre) == []
    # Sin simularla, el proyecto vuelve a como estaba
    fila = lambda i: pagina.locator(f'#ejProyecto .ej-tabla tr[data-id="{i}"]')
    fila(it["id"]).locator(".ej-c-sim input").uncheck()
    _esperar_kpi(pagina, "Margen estimado", "33 %")
    # Otro proveedor para lo mismo, más barato, desde el menú de la fila: se evalúa al marcarlo «Elegir»
    fila(it["id"]).locator(".ej-prov").select_option(label="+ Agregar otro proveedor…")
    pagina.locator("#dlgEjCosto").wait_for()
    _escribir_prov(pagina, 1, "Otro Inox", "700.000")
    assert "36 % más cara que la de Otro Inox ($700.000)" in pagina.locator("#ejCEval").inner_text()
    _prov(pagina, 1).locator(".ej-p-el").check()
    evaluacion = pagina.locator("#ejCEval").inner_text()
    assert "La más conveniente de las 2 cotizaciones" in evaluacion
    if _con_formulador_js("calc.js"):
        # Más barata que su línea: si materiales igual se pasa, es por lo ya gastado; se revisa, no es «No conviene»
        assert "13 % más barata" in evaluacion and "ya van $420.000 de $1.000.000" in evaluacion
        assert pagina.locator("#ejCEval .ej-eval-chip").inner_text() == "Revisar"
    _prov(pagina, 0).locator(".ej-p-el").check()
    pagina.locator("#ejCGuardar").click()
    sobre = _esperar_archivo(pagina, EJ, lambda s: len(s["datos"]["items"]) == 2)
    por = {x["proveedor"]: x for x in sobre["datos"]["items"]}
    assert por["Otro Inox"]["grupo"] == por["Inox Demo"]["grupo"] == por["Inox Demo"]["id"]
    assert por["Otro Inox"]["simular"] is False
    # Sigue el elegido; elegir el más barato no simula lo que no se simulaba
    fila(it["id"]).locator(".ej-prov").select_option(label="Otro Inox · $700.000")
    fila(por["Otro Inox"]["id"]).wait_for()
    _esperar_kpi(pagina, "Margen estimado", "33 %")
    # Simularlo: materiales llega a $1.120.000 y el margen a 30 %
    fila(por["Otro Inox"]["id"]).locator(".ej-c-sim input").check()
    _esperar_kpi(pagina, "Margen estimado", "30 %")
    # Aprobarla descarta la otra; Ctrl Z lo deshace
    fila(por["Otro Inox"]["id"]).locator(".ej-estado").select_option("aprobada")
    estados = lambda s: {x["proveedor"]: x["estado"] for x in s["datos"]["items"]}
    _esperar_archivo(pagina, EJ, lambda s: estados(s) == {"Otro Inox": "aprobada", "Inox Demo": "descartada"})
    # Una fila por ítem; la descartada sigue en su menú, como alternativa
    assert fila(por["Inox Demo"]["id"]).count() == 0
    assert fila(por["Otro Inox"]["id"]).locator(".ej-prov option").all_inner_texts()[:2] == ["Otro Inox · $700.000", "Inox Demo · $950.000"]
    pagina.locator("#tituloEjecucion").click()
    pagina.keyboard.press("Control+z")
    _esperar_archivo(pagina, EJ, lambda s: estados(s) == {"Otro Inox": "evaluar", "Inox Demo": "evaluar"})
    assert not errores
    pagina.context.close()


def test_una_cotizacion_reemplaza_varias_lineas_del_presupuesto(navegador, sitio):
    """2026-11-10, pedido del usuario: «hay cotizaciones que abordan más de un ítem de lo presupuestado»."""
    if not _con_formulador_js("calc.js"):
        pytest.skip("sin el Formulador en este equipo no hay líneas del presupuesto")
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    pagina.locator("#ejProyecto .ej-compras .cx-boton").click()
    pagina.locator("#dlgEjCosto").wait_for()
    pagina.locator("#ejCDesc").fill("Estanque inoxidable 100 L")
    _escribir_prov(pagina, 0, "Inox Demo", "950.000")
    lineas = lambda: pagina.locator("#ejCLineas .ej-lin").all_inner_texts()
    assert len(lineas()) == 1 and lineas()[0].startswith("M1 ")
    # La propuesta queda y se agrega otra desde el menú, que ya no ofrece la elegida
    menu = pagina.locator("#ejCLinea")
    assert menu.locator("option").first.inner_text() == "+ Agregar otra línea del presupuesto…"
    assert "m1" not in [o.get_attribute("value") for o in menu.locator("option").all()]
    menu.select_option("m2")
    assert [x.split(" ")[0] for x in lineas()] == ["M1", "M2"]
    assert "Suman $1.000.000 presupuestados." in pagina.locator("#ejCLineas").inner_text()
    assert menu.locator("option").first.inner_text() == "No quedan más líneas de materiales"
    evaluacion = pagina.locator("#ejCEval").inner_text()
    assert "Presupuestado $1.000.000 en total en 2 líneas (M1, M2): esta es 5 % más barata." in evaluacion
    assert "y sus líneas M1, M2 estaban presupuestadas en $1.000.000" in evaluacion
    # Cambiar la descripción ya no cambia lo elegido a mano
    pagina.locator("#ejCDesc").fill("Estanque y cañería")
    assert [x.split(" ")[0] for x in lineas()] == ["M1", "M2"]
    pagina.locator("#ejCGuardar").click()
    pagina.locator("#dlgEjCosto").wait_for(state="hidden")
    sobre = _esperar_archivo(pagina, EJ, lambda s: len(s["datos"]["items"]) == 1)
    it = sobre["datos"]["items"][0]
    assert (it["lineas"], it["linea"]) == (["m1", "m2"], "m1")
    assert _esquemas().validar_publicacion("ejecucion-proyectos", sobre) == []
    # Al abrirla de nuevo siguen las dos; la ✕ quita una
    pagina.locator(f'#ejProyecto .ej-tabla tr[data-id="{it["id"]}"] .ej-c-desc').click()
    pagina.locator("#dlgEjCosto").wait_for()
    assert [x.split(" ")[0] for x in lineas()] == ["M1", "M2"]
    pagina.locator("#ejCLineas .ej-lin", has_text="M1").get_by_role("button").click()
    assert [x.split(" ")[0] for x in lineas()] == ["M2"]
    assert pagina.evaluate("document.activeElement.id") == "ejCLinea"
    assert "Presupuestado $200.000 en total en M2" in pagina.locator("#ejCEval").inner_text()
    pagina.locator("#ejCGuardar").click()
    _esperar_archivo(pagina, EJ, lambda s: s["datos"]["items"][0].get("lineas") == ["m2"])
    # Cambiar de categoría deja fuera las líneas de la otra
    pagina.locator(f'#ejProyecto .ej-tabla tr[data-id="{it["id"]}"] .ej-c-desc').click()
    pagina.locator("#dlgEjCosto").wait_for()
    pagina.locator("#ejCCat .pl-vista", has_text="Equipos").click()
    assert lineas() == [] and pagina.locator("#ejCLinea option").first.inner_text() == "Ninguna: no estaba en el presupuesto"
    pagina.locator("#ejCostoX").click()
    assert not errores
    pagina.context.close()


def test_el_presupuesto_completo_y_un_presupuesto_actualizado(navegador, sitio):
    """2026-11-13, pedido del usuario: ver el presupuesto original con el desglose completo de sus costos y generar un
    presupuesto actualizado para evaluar los indicadores al agregar o quitar costos, sin perder el original; en una ventana
    grande, con buscador y orden por precio como la pestaña de costos del Formulador."""
    if not _con_formulador_js("calc.js"):
        pytest.skip("sin el Formulador en este equipo no hay líneas del presupuesto")
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    abrir = pagina.locator("#ejSecComoVa .ej-pr-abrir")
    assert abrir.inner_text() == "Ver el presupuesto"
    abrir.click()
    pagina.locator("#dlgEjPres").wait_for()
    # El original: las cinco líneas de su formulación y los indicadores del Formulador, sin nada que cambiar
    assert pagina.locator("#dlgEjPres .ej-pr-ver.on").inner_text().startswith("Original")
    assert _pr_filas(pagina).count() == 5 and pagina.locator("#ejPrTabla input").count() == 0
    assert (_pr_kpi(pagina, "costo"), _pr_kpi(pagina, "margen"), _pr_kpi(pagina, "dh"), _pr_kpi(pagina, "uDH")) == ("$2.500.000", "33 %", "10 DH", "$125.000")
    # Buscador, que dice cuántas filas suma, y orden por costo unitario o, con un clic en su título, por subtotal
    pagina.locator("#dlgEjPres .ej-pr-q").fill("cobre")
    assert _pr_filas(pagina).count() == 1 and "filtrado · 1 de 5" in pagina.locator("#ejPrTabla tfoot").inner_text()
    pagina.locator("#dlgEjPres .ej-pr-q").fill("")
    pagina.locator('#dlgEjPres select[data-foco="pr-orden"]').select_option("pu-menor")
    assert _pr_filas(pagina).first.locator("td").nth(1).inner_text() == "Cañería de cobre 1/2"
    pagina.locator("#ejPrTabla th.ej-pr-ord", has_text="Subtotal").click()
    assert _pr_filas(pagina).first.locator("td").nth(1).inner_text() == "Estanque inoxidable 100 L"
    assert pagina.locator('#dlgEjPres select[data-foco="pr-orden"]').input_value() == "mayor"
    # Una versión actualizada: 50 m más de cañería, sin el andamio y una válvula nueva
    pagina.locator("#dlgEjPres .ej-pr-vers .cx-enlace", has_text="Crear un presupuesto actualizado").click()
    assert pagina.locator("#dlgEjPres .ej-pr-ver.on").inner_text().startswith("Actualizado 1")
    assert pagina.locator('#ejPrTabla input[data-foco="pr-p-m1"]').input_value() == "800.000"
    pagina.locator('#ejPrTabla input[data-foco="pr-q-m2"]').fill("100")
    pagina.locator('#ejPrTabla input[data-foco="pr-q-m2"]').press("Tab")
    assert "ej-pr-cam" in (_pr_filas(pagina).filter(has_text="Cañería").get_attribute("class") or "")
    pagina.locator('#ejPrTabla button[data-foco="pr-x-e1"]').click()
    assert "quitado" in _pr_filas(pagina).filter(has_text="andamio").inner_text()
    pagina.locator('#dlgEjPres button[data-foco="pr-agregar"]').click()
    nueva = pagina.locator("#ejPrTabla tr.ej-pr-nue")
    nueva.locator("input.ej-pr-dsc").fill("Válvula de bola")
    nueva.locator("input.ej-pr-dsc").press("Tab")
    pagina.locator("#ejPrTabla tr.ej-pr-nue td[data-et='Cantidad'] input").fill("2")
    pagina.locator("#ejPrTabla tr.ej-pr-nue td[data-et='Cantidad'] input").press("Tab")
    pagina.locator("#ejPrTabla tr.ej-pr-nue td[data-et='Costo unitario'] input").fill("25.000")
    pagina.locator("#ejPrTabla tr.ej-pr-nue td[data-et='Costo unitario'] input").press("Tab")
    # Los indicadores se recalculan contra el original: 2.500.000 + 200.000 − 500.000 + 50.000
    assert _pr_kpi(pagina, "costo") == "$2.250.000" and _pr_kpi(pagina, "margen") == "40 %"
    assert "Original $2.500.000" in pagina.locator('#dlgEjPres .ej-pr-kpi[data-k="costo"]').inner_text()
    assert pagina.locator("#dlgEjPres .ej-pr-tab.on .ej-pr-cnt").inner_text() == "3"
    pagina.locator('#dlgEjPres input[data-foco="pr-solo"]').check()
    assert _pr_filas(pagina).count() == 3
    pagina.locator('#ejPrAcc input[data-foco="pr-seg"]').check()
    pagina.locator("#ejPrAcc .btn-pri").click()
    sobre = _esperar_archivo(pagina, EJ, lambda s: any(x["tipo"] == "presupuesto" for x in s["datos"]["items"]))
    assert _esquemas().validar_publicacion("ejecucion-proyectos", sobre) == []
    pr = next(x for x in sobre["datos"]["items"] if x["tipo"] == "presupuesto")
    assert (pr["nombre"], pr["seguimiento"], pr["gg"], pr["venta"]) == ("Actualizado 1", True, None, None)
    assert sorted(pr["cambios"], key=lambda c: c["uid"]) == [{"uid": "e1", "quitado": True}, {"uid": "m2", "cantidad": 100}]
    assert [(n["descripcion"], n["categoria"], n["cantidad"], n["unitario"]) for n in pr["nuevos"]] == [("Válvula de bola", "Materiales", 2, 25000)]
    assert "guardado" in pagina.locator("#ejPrAcc .ej-pr-estado").inner_text()
    # El original sigue igual
    pagina.locator("#dlgEjPres .ej-pr-ver", has_text="Original").click()
    assert _pr_kpi(pagina, "costo") == "$2.500.000" and pagina.locator("#ejPrTabla input").count() == 0
    pagina.locator("#dlgEjPres .dlg-x").click()
    pagina.locator("#dlgEjPres").wait_for(state="hidden")
    # «Cómo va el proyecto» lo usa: materiales 1.000.000 + 200.000 + 50.000 y equipos sin el andamio
    pagina.wait_for_function("() => document.querySelector('#ejSecComoVa .ej-pr-abrir').textContent === 'Presupuesto · 1 actualizado'")
    assert "con «Actualizado 1»" in pagina.locator("#ejSecComoVa .ej-panel-cab").inner_text()
    assert pagina.locator('#ejSecComoVa tr.ej-cat[data-cat="Materiales"] td').first.inner_text() == "$1.250.000"
    # Al abrirlo de nuevo muestra el que está en uso
    pagina.locator("#ejSecComoVa .ej-pr-abrir").click()
    assert pagina.locator("#dlgEjPres .ej-pr-ver.on").inner_text().startswith("Actualizado 1")
    assert _pr_kpi(pagina, "costo") == "$2.250.000"
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [700, 900, 1280])
def test_el_presupuesto_no_se_desliza_de_lado(navegador, sitio, ancho):
    """2026-11-25, pedido del usuario: ninguna tabla se desliza de lado, salvo que él lo pida. La del presupuesto
    medía 980 px como mínimo y en el diálogo se deslizaba bajo ~1100 px; ahí pasa a tarjetas."""
    if not _con_formulador_js("calc.js"):
        pytest.skip("sin el Formulador en este equipo no hay líneas del presupuesto")
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", ancho=ancho)
    pagina.locator("#ejSecComoVa .ej-pr-abrir").click()
    pagina.locator("#dlgEjPres").wait_for()
    pagina.locator("#dlgEjPres .ej-pr-vers .cx-enlace", has_text="Crear un presupuesto actualizado").click()
    assert _pr_filas(pagina).count() == 5
    desbordes = pagina.evaluate("""() => [...document.querySelectorAll('#dlgEjPres *')]
        .filter(e => e.offsetParent && e.scrollWidth > e.clientWidth + 1 && ['auto', 'scroll'].includes(getComputedStyle(e).overflowX))
        .map(e => (e.id || e.className) + ' ' + e.clientWidth + '<' + e.scrollWidth)""")
    assert desbordes == []
    assert not errores
    pagina.context.close()


def test_un_item_con_varios_proveedores_se_compara_y_se_elige_en_la_tabla(navegador, sitio):
    """Pedido del usuario (2026-10-30): al agregar un ítem, distintos proveedores; en la tabla, una columna con un menú con el
    nombre y el valor de cada uno, para comparar las cotizaciones y elegir el mejor."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    pagina.locator("#ejProyecto .ej-compras .cx-boton").click()
    pagina.locator("#dlgEjCosto").wait_for()
    # Con un proveedor es un formulario simple, sin «Elegir» ni ✕
    assert pagina.locator("#ejCProvs .ej-prov-cab").is_hidden()
    pagina.locator("#ejCDesc").fill("Estanque inoxidable 100 L")
    pagina.locator("#ejCCant").fill("2")
    _escribir_prov(pagina, 0, "Inox Caro", "475.000")
    pagina.locator("#ejCOtroProv").click()
    assert pagina.evaluate("document.activeElement.closest('.ej-p-prov') !== null"), "el foco va al proveedor nuevo"
    # El IVA es de cada proveedor: se guarda sin IVA. Un ítem nuevo elige solo al más barato
    _escribir_prov(pagina, 1, "Inox Barato", "416.500")
    _prov(pagina, 1).locator(".ej-p-iva input").check()
    assert _prov(pagina, 1).locator(".ej-p-el").is_checked()
    assert _prov(pagina, 1).locator(".ej-prov-dif").inner_text() == "El más barato"
    assert _prov(pagina, 0).locator(".ej-prov-dif").inner_text() == "$250.000 más (36 %)"
    assert "Total $700.000 sin IVA · Inox Barato" in pagina.locator("#ejCEval").inner_text()
    # Un tercero en blanco no cuenta, y uno con nombre sin precio se pide
    pagina.locator("#ejCOtroProv").click()
    _prov(pagina, 2).locator(".ej-p-prov input").fill("Sin Precio")
    pagina.locator("#ejCGuardar").click()
    assert "Escribe el precio unitario de Sin Precio" in pagina.locator("#ejCostoPista").inner_text()
    _prov(pagina, 2).locator(".ej-p-prov input").fill("")
    pagina.locator("#ejCGuardar").click()
    pagina.locator("#dlgEjCosto").wait_for(state="hidden")

    sobre = _esperar_archivo(pagina, EJ, lambda s: len(s["datos"]["items"]) == 2)
    assert _esquemas().validar_publicacion("ejecucion-proyectos", sobre) == []
    por = {x["proveedor"]: x for x in sobre["datos"]["items"]}
    barato, caro = por["Inox Barato"], por["Inox Caro"]
    assert barato["grupo"] == caro["grupo"] == caro["id"] and barato["precio"] == 350000 and barato["cantidad"] == caro["cantidad"] == 2
    assert (barato["elegida"], barato["simular"], caro["elegida"], caro["simular"]) == (True, True, False, False)
    _esperar_kpi(pagina, "Margen estimado", "30 %")

    # Una sola fila, con el menú: de más barato a más caro, con su valor
    filas = pagina.locator("#ejProyecto .ej-tabla > tbody > tr")
    menu = lambda: filas.locator(".ej-prov")
    tot = lambda: filas.locator(".ej-c-tot").inner_text()
    assert filas.count() == 1
    assert "Proveedor" in pagina.locator("#ejProyecto .ej-tabla > thead").inner_text()
    assert menu().locator("option").all_inner_texts() == ["Inox Barato · $350.000", "Inox Caro · $475.000", "+ Agregar otro proveedor…"]
    assert filas.locator(".ej-prov-nota").inner_text() == "2 proveedores · el más barato"
    assert tot() == "$700.000"
    assert pagina.locator("#ejProyecto .ej-filtro", has_text="Por decidir").inner_text() == "Por decidir y aprobadas (1)"

    # Elegir el otro cambia al tiro la fila y el proyecto; el foco sigue en el menú al repintar
    menu().focus()
    menu().select_option(label="Inox Caro · $475.000")
    _esperar_kpi(pagina, "Margen estimado", "23 %")
    assert tot() == "$950.000" and filas.locator(".ej-c-pu").inner_text() == "$475.000"
    assert filas.locator(".ej-prov-nota").inner_text() == "2 proveedores · Inox Barato, $250.000 menos"
    assert "ej-prov" in pagina.evaluate("document.activeElement.className")
    pagina.locator("#tituloEjecucion").click()
    pagina.keyboard.press("Control+z")
    _esperar_kpi(pagina, "Margen estimado", "30 %")
    menu().select_option(label="Inox Caro · $475.000")
    _esperar_kpi(pagina, "Margen estimado", "23 %")
    sel = lambda s: {x["proveedor"]: (x["elegida"], x["simular"]) for x in s["datos"]["items"] if not x.get("borrado")}
    _esperar_archivo(pagina, EJ, lambda s: sel(s) == {"Inox Caro": (True, True), "Inox Barato": (False, False)})

    # La elección sobrevive a no simular nada: «Simular todas» respeta lo elegido, no el más barato
    pagina.locator("#ejProyecto .ej-sim .cx-desmarcar", has_text="No simular ninguna").click()
    _esperar_kpi(pagina, "Margen estimado", "33 %")
    assert menu().locator("option:checked").inner_text() == "Inox Caro · $475.000"
    pagina.locator("#ejProyecto .ej-sim .cx-desmarcar", has_text="Simular todas").click()
    _esperar_kpi(pagina, "Margen estimado", "23 %")

    # Otro proveedor desde el menú: se abre el ítem con el foco en la tarjeta nueva, y no cambia al elegido
    menu().select_option(label="+ Agregar otro proveedor…")
    pagina.locator("#dlgEjCosto").wait_for()
    assert pagina.locator("#ejCProvs .ej-prov-fila").count() == 3
    assert pagina.evaluate("document.activeElement.closest('.ej-p-prov') !== null")
    assert _prov(pagina, 2).locator(".ej-p-prov input").input_value() == ""
    _escribir_prov(pagina, 2, "Inox Medio", "400.000")
    pagina.locator("#ejCGuardar").click()
    pagina.locator("#dlgEjCosto").wait_for(state="hidden")
    assert menu().locator("option").all_inner_texts()[:3] == ["Inox Barato · $350.000", "Inox Medio · $400.000", "Inox Caro · $475.000"]
    assert menu().locator("option:checked").inner_text() == "Inox Caro · $475.000"
    assert filas.locator(".ej-prov-nota").inner_text() == "3 proveedores · Inox Barato, $250.000 menos"

    # Quitar un proveedor en el diálogo: desaparece del menú y de los archivos del equipo
    filas.locator(".ej-c-desc").click()
    pagina.locator("#dlgEjCosto").wait_for()
    assert _prov(pagina, 2).locator(".ej-p-el").is_checked(), "se abre con el elegido marcado"
    _prov(pagina, 0).locator(".ej-p-quitar").click()
    assert pagina.locator("#ejCProvs .ej-prov-fila").count() == 2
    pagina.locator("#ejCGuardar").click()
    pagina.locator("#dlgEjCosto").wait_for(state="hidden")
    assert menu().locator("option").all_inner_texts()[:2] == ["Inox Medio · $400.000", "Inox Caro · $475.000"]
    _esperar_archivo(pagina, EJ, lambda s: next(x for x in s["datos"]["items"] if x["id"] == barato["id"]).get("borrado") is True)

    # El estado es del ítem: aprobar descarta a los demás, que siguen en el menú; elegir otro le pasa la aprobación
    estados = lambda s: {x["proveedor"]: x["estado"] for x in s["datos"]["items"] if not x.get("borrado")}
    filas.locator(".ej-estado").select_option("aprobada")
    _esperar_archivo(pagina, EJ, lambda s: estados(s) == {"Inox Caro": "aprobada", "Inox Medio": "descartada"})
    assert filas.count() == 1 and tot() == "$950.000"
    menu().select_option(label="Inox Medio · $400.000")
    _esperar_archivo(pagina, EJ, lambda s: estados(s) == {"Inox Medio": "aprobada", "Inox Caro": "descartada"})
    assert filas.locator(".ej-estado").input_value() == "aprobada" and tot() == "$800.000"
    # Volver a «Por decidir» trae de vuelta a los demás, y la fila sigue en el elegido
    filas.locator(".ej-estado").select_option("evaluar")
    _esperar_archivo(pagina, EJ, lambda s: estados(s) == {"Inox Medio": "evaluar", "Inox Caro": "evaluar"})
    assert tot() == "$800.000"
    # Descartar descarta el ítem entero: sale de la vista, con un solo conteo en su filtro
    filas.locator(".ej-estado").select_option("descartada")
    _esperar_archivo(pagina, EJ, lambda s: set(estados(s).values()) == {"descartada"})
    assert "Nada en «Por decidir y aprobadas»" in pagina.locator("#ejProyecto .ej-compras").inner_text()
    pagina.locator("#ejProyecto .ej-filtro", has_text="Descartadas").click()
    assert pagina.locator("#ejProyecto .ej-filtro", has_text="Descartadas").inner_text() == "Descartadas (1)"
    assert filas.count() == 1 and "fuera" in filas.get_attribute("class")
    # Comprado, el menú se bloquea: la OC dice a quién se le compró
    filas.locator(".ej-estado").select_option("comprada")
    pagina.locator("#dlgEjCosto").wait_for()
    pagina.locator("#ejCOC").fill("612950")
    pagina.locator("#ejCGuardar").click()
    pagina.locator("#dlgEjCosto").wait_for(state="hidden")
    pagina.locator("#ejProyecto .ej-filtro", has_text="Compradas").click()
    assert menu().is_disabled() and tot() == "$800.000"
    # El basurero elimina el ítem completo; Ctrl Z lo trae de vuelta
    filas.locator(".ej-c-acc .ej-ico").click()
    _esperar_archivo(pagina, EJ, lambda s: not estados(s))
    assert pagina.locator("#ejProyecto .ej-tabla").count() == 0
    pagina.locator("#tituloEjecucion").click()
    pagina.keyboard.press("Control+z")
    _esperar_archivo(pagina, EJ, lambda s: estados(s) == {"Inox Medio": "comprada", "Inox Caro": "descartada"})
    assert not errores
    pagina.context.close()


def test_una_oc_de_otro_proveedor_del_item_lo_marca_comprado(navegador, sitio):
    """La OC puede ser de un proveedor que no es el elegido: al marcarla, ese queda comprado y el otro descartado."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    pagina.locator("#ejProyecto .ej-compras .cx-boton").click()
    pagina.locator("#dlgEjCosto").wait_for()
    pagina.locator("#ejCDesc").fill("Codos y tees")
    _escribir_prov(pagina, 0, "Ferretería Demo", "120.000")
    pagina.locator("#ejCOtroProv").click()
    _escribir_prov(pagina, 1, "Otra Ferretería", "90.000")
    pagina.locator("#ejCGuardar").click()
    pagina.locator("#dlgEjCosto").wait_for(state="hidden")
    fila = pagina.locator("#ejProyecto .ej-tabla > tbody > tr")
    assert fila.locator(".ej-c-tot").inner_text() == "$90.000"
    sugerida = fila.locator(".ej-sugerida")
    assert "¿Es la OC 612900 ($120.000), de Ferretería Demo?" in sugerida.inner_text()
    sugerida.locator("button").click()
    estados = lambda s: {x["proveedor"]: (x["estado"], x["oc"]) for x in s["datos"]["items"]}
    _esperar_archivo(pagina, EJ, lambda s: estados(s) == {"Ferretería Demo": ("comprada", "612900"), "Otra Ferretería": ("descartada", "")})
    assert not errores
    pagina.context.close()


def test_en_ejecucion_se_ve_quien_cambio_algo_y_lo_tuyo_que_reemplazo(navegador, sitio):
    """2026-11-10, trabajar a la vez: como en la Planificación, lo que llega de otro dice quién fue, y si reemplaza una
    cotización que este navegador acababa de cambiar, la franja lo dice y «Volver a lo mío» la repone."""
    def con_lo_mio(archivos):
        archivos[EJ] = {"esquema": "quempin.intercambio/1", "herramienta": "ejecucion", "tipo": "ejecucion-proyectos", "generado": _instante(-60),
                        "datos": {"dispositivo": DISPOSITIVO, "items": [_item_de_prueba("cgrupoprueba1", "Ferretería Uno", 210000, por="LC")]}}
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=con_lo_mio)
    suyo = _item_de_prueba("cgrupoprueba1", "Ferretería Uno", 250000, t=0)
    pagina.evaluate(JS_ESCRIBIR_TEXTO, _sobre_de_otro(suyo))
    franja = pagina.locator("#ejPisado")
    franja.wait_for(timeout=20000)
    assert pagina.locator("#ejFrescura").inner_text() == "NB acaba de cambiar 1 cosa"
    txt = franja.inner_text()
    assert "NB cambió algo que tú acababas de cambiar" in txt and "NB cambió la cotización «Estanque inoxidable" in txt and "(N° 908)" in txt, txt
    franja.get_by_role("button", name="Volver a lo mío").click()
    assert franja.is_hidden()
    _esperar_aviso(pagina, "Volvió lo tuyo")
    _esperar_archivo(pagina, EJ, lambda s: any(i["id"] == "cgrupoprueba1" and i["precio"] == 210000 and i["t"] > suyo["t"] for i in s["datos"]["items"]))
    assert not errores
    pagina.context.close()


def test_dos_navegadores_que_eligen_a_la_vez_no_cuentan_el_item_dos_veces(navegador, sitio):
    """En cada id manda el cambio más reciente, así que dos elecciones a la vez dejan dos marcados: cuenta solo el más reciente."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    pagina.evaluate(JS_ESCRIBIR_TEXTO, _sobre_de_otro(
        _item_de_prueba("cgrupoprueba1", "Primero", 950000, t=-90, simular=True, elegida=True),
        _item_de_prueba("cgrupoprueba2", "Segundo", 700000, t=-30, simular=True, elegida=True)))
    pagina.locator("#ejActualizar").click()
    fila = pagina.locator('#ejProyecto .ej-tabla > tbody > tr[data-item="cgrupoprueba1"]')
    fila.wait_for()
    assert fila.get_attribute("data-id") == "cgrupoprueba2" and fila.locator(".ej-c-tot").inner_text() == "$700.000"
    assert "Simulando 1 gasto por $700.000" in pagina.locator("#ejProyecto .ej-sim").inner_text()
    _esperar_kpi(pagina, "Margen estimado", "30 %")
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [780, 900, 1024, 1100, 1280])
def test_la_tabla_de_compras_no_se_sale_del_panel(navegador, sitio, ancho):
    """Con la columna Proveedor son nueve: en cada ancho cabe y «Qué se compra» se puede leer, o pasa a tarjetas."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", ancho=ancho, alto=900)
    pagina.evaluate(JS_ESCRIBIR_TEXTO, _sobre_de_otro(
        _item_de_prueba("cgrupoprueba1", "Proveedor con un nombre bastante largo SpA", 950000, simular=True),
        _item_de_prueba("cgrupoprueba2", "Otro proveedor con el nombre igual de largo Ltda.", 1250000)))
    pagina.locator("#ejActualizar").click()
    pagina.locator('#ejProyecto .ej-tabla > tbody > tr[data-item="cgrupoprueba1"]').wait_for()
    medida = pagina.evaluate("""() => {
        const t = document.querySelector('#ejProyecto .ej-tabla');
        const v = document.querySelector('#vistaEjecucion');
        return { sobra: t.getBoundingClientRect().right - t.parentElement.getBoundingClientRect().right, desplaza: v.scrollWidth > v.clientWidth,
                 que: t.querySelector('.ej-c-que').getBoundingClientRect().width };
    }""")
    assert medida["sobra"] <= 0.5 and not medida["desplaza"], medida
    assert medida["que"] >= 200, medida
    assert not errores
    pagina.context.close()


def test_pegar_una_cotizacion_agrega_sus_filas(navegador, sitio):
    if not _con_formulador_js("pegar.js"):
        pytest.skip("el Formulador (js/pegar.js) no está en este equipo")
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    pagina.locator("#ejProyecto .ej-compras .cx-enlace", has_text="Pegar").click()
    pagina.locator("#dlgEjPegar").wait_for()
    pagina.locator("#ejPegarTexto").fill("Codo de cobre 1/2\t10\tUn.\t1.190\nTee de cobre 1/2\t5\tUn.\t2.380\nTotal\t\t\t35.700")
    pagina.locator("#ejPProv").fill("Ferretería Demo")
    pagina.locator("#ejPIva").check()
    assert pagina.locator("#ejPAgregar").inner_text() == "Agregar 2 filas"
    assert "2 filas por $20.000 sin IVA" in pagina.locator("#ejPPrevia").inner_text()
    pagina.locator("#ejPAgregar").click()
    sobre = _esperar_archivo(pagina, EJ, lambda s: len(s["datos"]["items"]) == 2)
    assert sorted((x["descripcion"], x["cantidad"], x["precio"], x["proveedor"], x["simular"]) for x in sobre["datos"]["items"]) == [
        ("Codo de cobre 1/2", 10, 1000, "Ferretería Demo", True), ("Tee de cobre 1/2", 5, 2000, "Ferretería Demo", True)]
    assert "Simulando 2 gastos por $20.000" in pagina.locator("#ejProyecto .ej-sim").inner_text()
    assert not errores
    pagina.context.close()


def test_el_avance_se_pide_al_analisis_y_lo_ven_las_demas_vistas(navegador, sitio):
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    pagina.locator("#ejAvNum").fill("60")
    pagina.locator("#ejProyecto .ej-av-form .cx-boton").click()
    _esperar_aviso(pagina, "Avance 60 %")
    pedidos = lambda: {n: m for n, m in pagina.evaluate(JS_BUZON).items()
                       if m.get("tipo") == "datos-proyecto" and (m.get("origen") or {}).get("herramienta") == "portal"}
    (nombre, m), = pedidos().items()
    assert m["proyecto"] == {"tag": "DEMO"} and m["valores"] == {"% Avance": 0.6} and m["reemplaza"] == {"% Avance": 0.4}
    assert "_portal_datos-proyecto_" in nombre and m["origen"]["usuario"] == "LC" and _esquemas().validar_mensaje(m) == []
    assert pagina.locator("#ejProyecto .ej-av-num b").inner_text() == "60 %"
    # El Recorrido ya lo muestra, sin cambiar de etapa, y su «Registrar avance» lleva a este resumen
    _menu(pagina, "Recorrido de proyectos")
    tarjeta = pagina.locator('.rc-tarjeta[data-clave="req-908"]')
    assert "Avance 60 % por aplicar" in tarjeta.locator(".rc-chip").all_inner_texts()
    tarjeta.locator(".rc-accion").click()
    pagina.locator("#ejProyecto .ej-kpis").wait_for()
    # Otro pedido encima reemplaza lo pedido (el Análisis los aplica en orden), y la fecha de término va en el mismo
    pagina.locator("#ejAvNum").fill("70")
    pagina.locator("#ejAvFin").fill(_dia(45))
    pagina.locator("#ejProyecto .ej-av-form .cx-boton").click()
    _esperar_aviso(pagina, "Avance 70 %")
    nuevo = next(x for n, x in pedidos().items() if n != nombre)
    assert nuevo["valores"] == {"% Avance": 0.7, "Fecha de cierre": _dia(45)}
    assert nuevo["reemplaza"] == {"% Avance": 0.6, "Fecha de cierre": _dia(30)}
    # Retirar el último pedido lo saca del buzón
    pagina.locator("#ejProyecto .ej-linea.tinte .cx-desmarcar", has_text="Retirar").click()
    _esperar_aviso(pagina, "Se retiró")
    assert list(pedidos()) == [nombre]
    assert pagina.locator("#ejProyecto .ej-av-num b").inner_text() == "60 %"
    assert not errores
    pagina.context.close()


def test_el_nombre_que_se_ve_se_cambia_con_el_lapiz(navegador, sitio):
    """2026-11-09 (pedido del usuario): el lápiz junto al nombre pide al Análisis Financiero solo el apodo."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    pagina.locator("#ejProyecto .ej-cab .ej-renombrar").click()
    pagina.locator("#ejNomTexto").fill("  H2   Green ")
    pagina.locator("#ejNombreForm .btn-pri").click()
    _esperar_aviso(pagina, "Nombre pedido")
    (_, m), = [(n, x) for n, x in pagina.evaluate(JS_BUZON).items()
               if x.get("tipo") == "datos-proyecto" and (x.get("origen") or {}).get("herramienta") == "portal"]
    assert m["valores"] == {"Apodo": "H2 Green"} and list(m["reemplaza"]) == ["Apodo"]
    assert _esquemas().validar_mensaje(m) == []
    assert "H2 Green" in pagina.locator("#ejProyecto .ej-cab h2").inner_text()
    assert not errores
    pagina.context.close()


def test_los_dias_trabajados_estiman_la_mano_de_obra_real(navegador, sitio):
    from datetime import date
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    hoy = date.today().isoformat()
    # El calendario del mes (2026-11-06): se marca el día, se eligen quiénes y se anota de una vez
    pagina.locator(f'#ejProyecto .ej-cal-dia[data-iso="{hoy}"]').click()
    for per in ("NB", "MP"):
        pagina.locator(".ej-quienes label", has_text=per).locator("input").check()
    assert pagina.locator("#ejDiasAnotar").inner_text() == "Anotar 2 DH"
    pagina.locator("#ejDiasAnotar").click()
    dias = lambda s: sorted((x["fecha"], x["persona"], x["nivel"], x.get("origen", "")) for x in s["datos"]["items"]
                            if x["tipo"] == "dia" and not x.get("borrado"))
    sobre = _esperar_archivo(pagina, EJ, lambda s: len(dias(s)) == 2)
    assert dias(sobre) == [(hoy, "MP", 2, ""), (hoy, "NB", 2, "")]
    assert _esquemas().validar_publicacion("ejecucion-proyectos", sobre) == []
    # Su costo, a la tarifa del nivel 2 de la formulación, es la mano de obra real del resumen y de los indicadores
    pagina.wait_for_function("(js) => eval(js)().startsWith('$120.000')", arg=JS_EJ_MO)
    assert pagina.evaluate(JS_EJ_COMO, "Mano de Obra")["Queda"] == "$480.000"
    ind = pagina.evaluate(JS_EJ_IND)
    assert ind["costoDH"][1] == "$60.000" and ind["dh"][1] == "2"
    if _con_formulador_js("calc.js"):
        assert ind["dh"][0] == "10" and ind["costoDH"][0] == "$60.000"
    # Lo que la Planificación tiene de este proyecto (ES y LC el lunes) se trae de una vez
    pagina.locator("#ejProyecto .ej-linea.tinte .cx-desmarcar", has_text="Traerlos").click()
    sobre = _esperar_archivo(pagina, EJ, lambda s: len(dias(s)) == 4)
    assert {(p, o) for f, p, n, o in dias(sobre)} >= {("ES", "planificacion"), ("LC", "planificacion")}
    pagina.wait_for_function("(js) => eval(js)().startsWith('$240.000')", arg=JS_EJ_MO)
    # Subir a ES al nivel 3 recalcula su costo
    pagina.locator('.ej-nivel select[aria-label^="Nivel de ES"]').select_option("3")
    pagina.wait_for_function("(js) => eval(js)().startsWith('$255.000')", arg=JS_EJ_MO)
    # Y se lleva al Análisis Financiero como su mano de obra real (no al Centro de Costos)
    pagina.locator("#ejProyecto .cx-desmarcar", has_text="Llevarle").click()
    _esperar_aviso(pagina, "Se pidió dejar")
    (m,) = [x for x in pagina.evaluate(JS_BUZON).values() if x.get("tipo") == "datos-proyecto" and (x.get("origen") or {}).get("herramienta") == "portal"]
    assert m["valores"] == {"Mano de Obra Real": 255000} and m["reemplaza"] == {"Mano de Obra Real": None}
    assert _esquemas().validar_mensaje(m) == []
    assert not errores
    pagina.context.close()


def test_lo_anotado_en_otro_navegador_aparece_y_manda_lo_mas_reciente(navegador, sitio):
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    otro = {"esquema": "quempin.intercambio/1", "herramienta": "ejecucion", "tipo": "ejecucion-proyectos", "generado": _instante(0),
            "autor": "NB", "datos": {"dispositivo": "otronavegador1", "items": [
                {"id": "cotronavegador001", "proyecto": "req:908", "tipo": "costo", "t": _instante(-30), "creado": _instante(-60), "por": "NB",
                 "descripcion": "Quemador de prueba", "categoria": "Equipos", "cantidad": 1, "precio": 300000, "estado": "evaluar", "simular": True},
                {"id": "notaotronavegador1", "proyecto": "tag:DEMO", "tipo": "nota", "t": _instante(-20), "por": "NB", "texto": "Nota con el TAG"},
                {"id": "cmalaotronavegador", "proyecto": "req:908", "tipo": "costo", "t": _instante(-10), "descripcion": "Categoría que no existe",
                 "categoria": "Herramientas", "cantidad": 1, "precio": 1}]}}
    pagina.evaluate(JS_ESCRIBIR_TEXTO, ["publicado/ejecucion/otronavegador1.json", json.dumps(otro)])
    pagina.locator("#ejActualizar").click()
    fila = pagina.locator('#ejProyecto .ej-tabla tr[data-id="cotronavegador001"]')
    fila.wait_for()
    assert "Categoría que no existe" not in pagina.locator("#ejProyecto").inner_text()
    assert "Nota con el TAG" in pagina.locator("#ejProyecto").inner_text(), "lo anotado con su TAG también es del proyecto"
    # Cabe en equipos: el costo estimado no cambia
    assert "cabe en lo presupuestado" in pagina.locator("#ejProyecto .ej-sim").inner_text()
    # Descartarla aquí gana (es el cambio más reciente), aunque el otro archivo la siga teniendo por decidir
    fila.locator(".ej-estado").select_option("descartada")
    sobre = _esperar_archivo(pagina, EJ, lambda s: any(x["id"] == "cotronavegador001" for x in s["datos"]["items"]))
    assert next(x for x in sobre["datos"]["items"] if x["id"] == "cotronavegador001")["estado"] == "descartada"
    pagina.locator("#ejActualizar").click()
    pagina.locator("#ejProyecto .ej-filtro", has_text="Descartadas").click()
    assert "fuera" in pagina.locator('#ejProyecto .ej-tabla tr[data-id="cotronavegador001"]').get_attribute("class")
    assert not errores
    pagina.context.close()


def test_las_facturas_del_centro_de_costos_se_ven_y_se_asocian_a_sus_gastos(navegador, sitio):
    """Pedido del usuario (2026-11-06): en cada proyecto, los costos registrados en el Centro de Costos, y cada factura
    asociada a uno o varios gastos proyectados y cotizados. Lo facturado ya está en lo gastado: se simula solo lo que falta."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=_documentos_908)
    filas = lambda: pagina.locator("#ejProyecto .ej-docs tbody tr").evaluate_all("ts => ts.map((t) => t.dataset.ref)")
    assert filas() == ["DEMO-002", "DEMO-001"], "solo las de su TAG, la más nueva primero"
    assert pagina.locator('#ejProyecto .ej-docs tr[data-ref="DEMO-002"] a.ej-d-ref').get_attribute("href").endswith("DEMO-002.pdf")
    assert "Por revisar" in pagina.locator('#ejProyecto .ej-docs tr[data-ref="DEMO-001"]').inner_text()
    # Lo gastado sale de sus facturas (más nuevas que el Análisis Financiero): materiales $200.000, otros $30.000
    assert pagina.evaluate(JS_EJ_KPIS)["Gastado a la fecha"] == "$230.000"
    assert pagina.evaluate(JS_EJ_COMO, "Materiales")["Gastado"] == "$200.000"
    # Un estanque cotizado y simulado, de otro navegador
    otro = {"esquema": "quempin.intercambio/1", "herramienta": "ejecucion", "tipo": "ejecucion-proyectos", "generado": _instante(0),
            "datos": {"dispositivo": "otronavegador1", "items": [
                {"id": "cestanque000001", "proyecto": "req:908", "tipo": "costo", "t": _instante(-30), "descripcion": "Estanque inoxidable",
                 "categoria": "Materiales", "cantidad": 1, "precio": 800000, "proveedor": "Aceros Demo SpA", "estado": "evaluar", "simular": True}]}}
    pagina.evaluate(JS_ESCRIBIR_TEXTO, ["publicado/ejecucion/otronavegador1.json", json.dumps(otro)])
    pagina.locator("#ejActualizar").click()
    pagina.locator('#ejProyecto .ej-tabla tr[data-id="cestanque000001"]').wait_for()
    assert pagina.evaluate(JS_EJ_COMO, "Materiales")["Simulado"] == "$800.000"
    # Asociar la factura: el estanque se propone primero («Parece»), y también se puede elegir su línea del presupuesto
    pagina.locator('#ejProyecto .ej-docs tr[data-ref="DEMO-002"] .ej-asociar', has_text="Asociar").click()
    dlg = pagina.locator("#dlgEjAsociar")
    dlg.wait_for()
    primera = dlg.locator(".ej-as-op").first
    assert "Estanque inoxidable" in primera.inner_text() and "Parece" in primera.inner_text()
    primera.locator("input").check()
    pagina.locator("#ejAsComprar").uncheck()
    pagina.locator("#ejAsGuardar").click()
    _esperar_aviso(pagina, "DEMO-002 asociada a 1 gasto")
    sobre = _esperar_archivo(pagina, EJ, lambda s: any(x["tipo"] == "asociacion" for x in s["datos"]["items"]))
    (a,) = [x for x in sobre["datos"]["items"] if x["tipo"] == "asociacion"]
    assert (a["ref"], a["destinos"], a["proyecto"]) == ("DEMO-002", ["i:cestanque000001"], "req:908")
    assert _esquemas().validar_publicacion("ejecucion-proyectos", sobre) == []
    # Lo facturado se ve en la fila del gasto y ya no se simula: quedan $600.000 por facturar
    pagina.wait_for_function("(js) => eval(js)('Materiales')['Simulado'] === '$600.000'", arg=JS_EJ_COMO)
    assert "Facturado $200.000 de $800.000" in pagina.locator('#ejProyecto .ej-tabla tr[data-id="cestanque000001"]').inner_text()
    assert "Estanque inoxidable" in pagina.locator('#ejProyecto .ej-docs tr[data-ref="DEMO-002"] .ej-d-chips').inner_text()
    # Filtrar las que faltan por asociar
    pagina.locator("#ejProyecto .ej-facturas .ej-filtro", has_text="Sin asociar").click()
    pagina.wait_for_function("() => [...document.querySelectorAll('#ejProyecto .ej-docs tbody tr')].map((t) => t.dataset.ref).join() === 'DEMO-001'")
    assert not errores
    pagina.context.close()


def test_el_calendario_anota_varios_dias_de_una_vez_y_medio_dia(navegador, sitio):
    """Pedido del usuario (2026-11-06): la mano de obra en un calendario del mes, marcando los días trabajados con día
    completo o medio día, en una sola acción."""
    from datetime import date, timedelta
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908")
    hoy = date.today()
    dias = [d for d in (hoy - timedelta(days=k) for k in range(3)) if d.month == hoy.month]
    assert pagina.locator("#ejProyecto .ej-cal-tit b").inner_text().split()[1] == str(hoy.year)
    assert pagina.locator(f'.ej-cal-dia[data-iso="{(hoy + timedelta(days=1)).isoformat()}"]').count() == 0 or \
        pagina.locator(f'.ej-cal-dia[data-iso="{(hoy + timedelta(days=1)).isoformat()}"]').is_disabled(), "un día que no llega no se marca"
    for d in dias:
        pagina.locator(f'#ejProyecto .ej-cal-dia[data-iso="{d.isoformat()}"]').click()
    for per in ("NB", "EV"):
        pagina.locator(".ej-quienes label", has_text=per).locator("input").check()
    pagina.locator('#ejProyecto .ej-jornada .pl-vista[data-jornada="0.5"]').click()
    assert pagina.locator("#ejDiasAnotar").inner_text() == "Anotar " + f"{len(dias) * 2 * 0.5:g}".replace(".", ",") + " DH"
    pagina.locator("#ejDiasAnotar").click()
    lista = lambda s: sorted((x["fecha"], x["persona"], x["jornada"]) for x in s["datos"]["items"] if x["tipo"] == "dia" and not x.get("borrado"))
    sobre = _esperar_archivo(pagina, EJ, lambda s: len(lista(s)) == 2 * len(dias))
    assert lista(sobre) == sorted((d.isoformat(), p, 0.5) for d in dias for p in ("NB", "EV"))
    assert _esquemas().validar_publicacion("ejecucion-proyectos", sobre) == []
    celda = pagina.locator(f'#ejProyecto .ej-cal-dia[data-iso="{hoy.isoformat()}"]')
    celda.locator(".ej-cal-per", has_text="NB½").wait_for()
    # Quitar: el día de hoy de NB (EV queda desmarcado: solo se quita lo de los elegidos)
    pagina.locator(".ej-quienes label", has_text="EV").locator("input").uncheck()
    celda.click()
    assert pagina.locator("#ejDiasQuitar").inner_text() == "Quitar 1 día anotado"
    pagina.locator("#ejDiasQuitar").click()
    sobre = _esperar_archivo(pagina, EJ, lambda s: len(lista(s)) == 2 * len(dias) - 1)
    assert (hoy.isoformat(), "NB", 0.5) not in lista(sobre) and (hoy.isoformat(), "EV", 0.5) in lista(sobre)
    assert not errores
    pagina.context.close()


def test_proyectos_en_ejecucion_abre_facturas_del_proyecto(navegador, sitio):
    """«Facturas del proyecto» (2026-10-29) abre en SharePoint la carpeta del proyecto en el Centro de Costos."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=_carpetas_908(
        oferta=["0 OFERTAS ADJUDICADAS/908. En obra"], ejecucion=["908. En obra"], facturasWeb=[WEB_908]))
    cab = pagina.locator("#ejProyecto .ej-cab")
    boton = cab.locator('[data-foco="carpeta-facturas"]')
    assert "Centro de Costos" in boton.get_attribute("title")
    boton.click()
    assert pagina.evaluate("window.__abiertas")[-1] == WEB_908
    assert cab.locator('[data-foco="trasladar"]').count() == 0 and cab.locator(".ej-pista").count() == 0
    assert not errores
    pagina.context.close()


def test_facturas_del_proyecto_solo_abre_el_sitio_de_quempin(navegador, sitio):
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=_carpetas_908(
        ejecucion=["908. En obra"], facturasWeb=["https://otro.example.com/908"]))
    assert pagina.locator('#ejProyecto .ej-cab [data-foco="carpeta-facturas"]').count() == 0
    assert not errores
    pagina.context.close()


def test_proyectos_en_ejecucion_pasa_la_oferta_a_gestion(navegador, sitio):
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=_carpetas_908(
        oferta=["0 OFERTAS PRESENTADAS/908. En obra"]))
    cab = pagina.locator("#ejProyecto .ej-cab")
    assert cab.locator('[data-foco="carpeta-facturas"]').count() == 0
    # Lo que falta, en pocas palabras; el porqué, en su ⓘ (2026-11-05)
    pista = cab.locator(".ej-pista")
    assert pista.inner_text().strip() == "Sin carpeta en Gestión de Proyectos"
    assert "«Facturas del proyecto»" in pista.locator(".info-txt").text_content()
    cab.locator('[data-foco="trasladar"]').click()
    assert pagina.evaluate("window.__lanzados")[-1] == "quempin://trasladar/formulacion/0%20OFERTAS%20PRESENTADAS/908.%20En%20obra"
    assert not errores
    pagina.context.close()


def test_proyectos_en_ejecucion_sin_facturas_del_proyecto_lo_explica(navegador, sitio):
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=_carpetas_908(
        oferta=["0 OFERTAS ADJUDICADAS/908. En obra"], ejecucion=["908. En obra"]))
    cab = pagina.locator("#ejProyecto .ej-cab")
    assert cab.locator('[data-foco="trasladar"]').count() == 0
    pista = cab.locator(".ej-pista")
    assert pista.inner_text().strip() == "Sin carpeta en el Centro de Costos"
    # La explicación se abre al tocar su ⓘ y se cierra con Esc o tocando fuera
    pop = pagina.locator("#infoPop")
    assert pop.is_hidden()
    pista.locator(".info-i").click()
    pop.wait_for()
    assert "Todavía no tiene carpeta con su N° en el Centro de Costos" in pop.inner_text()
    assert pista.locator(".info-i").get_attribute("aria-expanded") == "true"
    pagina.keyboard.press("Escape")
    pop.wait_for(state="hidden")
    assert pista.locator(".info-i").get_attribute("aria-expanded") == "false"
    pista.locator(".info-i").click()
    pop.wait_for()
    pagina.locator("#ejProyecto .ej-cab h2").click()
    pop.wait_for(state="hidden")
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [360, 390])
def test_proyectos_en_ejecucion_cabe_en_el_telefono(navegador, sitio, ancho):
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", ancho=ancho, alto=844, movil=True)
    item = {"id": "ctelefono00001", "proyecto": "req:908", "tipo": "costo", "t": _instante(-30), "por": "LC",
            "descripcion": "Estanque inoxidable de 100 litros con serpentín de cobre", "categoria": "Materiales", "cantidad": 1,
            "precio": 950000, "proveedor": "Proveedor con un nombre bastante largo SpA", "estado": "evaluar", "simular": True}
    sobre = {"esquema": "quempin.intercambio/1", "herramienta": "ejecucion", "tipo": "ejecucion-proyectos", "generado": _instante(0),
             "datos": {"dispositivo": "otronavegador1", "items": [dict(item, grupo="ctelefono00001"),
                 dict(item, id="ctelefono00002", grupo="ctelefono00001", proveedor="Otro proveedor con el nombre igual de largo Ltda.", precio=1250000, simular=False)]}}
    pagina.evaluate(JS_ESCRIBIR_TEXTO, ["publicado/ejecucion/otronavegador1.json", json.dumps(sobre)])
    pagina.locator("#ejActualizar").click()
    pagina.locator('#ejProyecto .ej-tabla tr[data-id="ctelefono00001"]').wait_for()
    derecha = """() => Math.max(...[...document.querySelectorAll('#vistaEjecucion *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))"""
    assert pagina.evaluate(derecha) <= ancho + 0.5
    chicos = pagina.evaluate("""() => [...document.querySelectorAll('#vistaEjecucion input, #vistaEjecucion select, #vistaEjecucion textarea')]
        .filter((e) => e.getClientRects().length && !['checkbox', 'range'].includes(e.type) && parseFloat(getComputedStyle(e).fontSize) < 16)
        .map((e) => e.id || e.className)""")
    assert chicos == []
    # El ítem con sus dos proveedores en el diálogo también cabe, con los campos a 16 px
    pagina.locator('#ejProyecto .ej-tabla tr[data-id="ctelefono00001"] .ej-c-desc').click()
    pagina.locator("#dlgEjCosto").wait_for()
    assert pagina.locator("#ejCProvs .ej-prov-fila").count() == 2
    assert pagina.evaluate("""() => Math.max(...[...document.querySelectorAll('#dlgEjCosto *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))""") <= ancho + 0.5
    assert pagina.evaluate("""() => [...document.querySelectorAll('#dlgEjCosto input, #dlgEjCosto select')]
        .filter((e) => e.getClientRects().length && !['checkbox', 'radio'].includes(e.type) && parseFloat(getComputedStyle(e).fontSize) < 16)
        .map((e) => e.id || e.parentElement.className)""") == []
    pagina.locator("#ejCCancelar").click()
    # La lista también
    pagina.locator(".ej-volver").click()
    pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="req-908"]').wait_for()
    assert pagina.evaluate(derecha) <= ancho + 0.5
    assert not errores
    pagina.context.close()
