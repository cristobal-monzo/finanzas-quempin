# -*- coding: utf-8 -*-
"""Portal QUEMPIN: Llevar la cotización del Cotizador Histórico a un proyecto.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- La cotización del Cotizador Histórico, a un proyecto (2026-10-29) --------------------------------------------------


def test_la_categoria_propuesta_sale_de_la_tabla_del_analisis_financiero():
    """La categoría que el diálogo propone para la cotización sale de la categoría del Centro de Costos de cada compra,
    con la misma tabla con que el Análisis Financiero reparte el gasto real (MAPEO_CATEGORIA_BUCKET): sin tildes, y lo que
    no está va a «Otros» como allá."""
    import ast
    import unicodedata
    fuente = (RAIZ / "Sistema Analisis Financiero" / "Sistema" / "analisis_financiero.py").read_text(encoding="utf-8")
    nodo = next(n for n in ast.parse(fuente).body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "MAPEO_CATEGORIA_BUCKET")
    sin_tildes = lambda s: "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).lower()
    esperado = {sin_tildes(k): v for k, v in ast.literal_eval(nodo.value).items() if v != "Otros"}
    html = texto_portal()
    bloque = re.search(r"const LL_BUCKET = \{(.*?)\};", html, re.S).group(1)
    js = {(a or b): v for a, b, v in re.findall(r"(?:'([^']+)'|([\w-]+)): '(\w+)'", bloque)}
    assert js == esperado


def test_la_cotizacion_del_cotizador_va_a_un_proyecto_en_ejecucion(navegador, sitio):
    """Pedido del 2026-10-29: que el carrito del Cotizador Histórico exporte sus costos a un proyecto específico en
    formulación o en ejecución. El Portal pregunta a cuál; en uno en ejecución cada línea queda como gasto por decidir y
    simulado, con el proveedor de la compra, la hoja del Cotizador con que se compara y de dónde sale el precio."""
    pagina, errores = _llevar(navegador, sitio)
    grupos = pagina.evaluate(JS_LL_GRUPOS)
    # Los de la etapa Ejecución del Recorrido (lo de LC primero) y los que tienen formulación antes de ofertar: la perdida
    # (913), la eliminada (fx) y los que no tienen formulación no
    assert grupos["En ejecución"][0] == "req-908" and set(grupos["En ejecución"]) == {"req-908", "req-907", "tag-SOLO", "req-910"}
    assert grupos["En formulación"][0] == "f-fz" and set(grupos["En formulación"]) == {"f-fz", "req-901", "req-902"}
    assert pagina.locator("#llResumen").inner_text() == "3 líneas por $37.900 sin IVA, con lo que QUEMPIN pagó actualizado por UF (la del 26-10-2026)."
    assert len(pagina.locator("#llLineas tr").all()) == 3
    # La categoría con más plata entre sus compras (ferretería y materiales son Materiales); sin proyecto, no se lleva
    assert pagina.locator("#llCat .pl-vista[aria-pressed='true']").inner_text() == "Materiales"
    assert pagina.locator("#llLlevar").is_disabled() and pagina.locator("#llPista").inner_text() == "Elige el proyecto."
    # El buscador filtra los dos grupos, y Enter elige el primero que coincide
    pagina.locator("#llBuscar").fill("en obra")
    assert pagina.evaluate(JS_LL_GRUPOS) == {"En ejecución": ["req-908"], "En formulación": []}
    assert "Ninguno coincide" in pagina.locator("#llLista .ll-grupo").nth(1).inner_text()
    pagina.locator("#llBuscar").press("Enter")
    assert pagina.locator("#dlgLlevar").is_visible(), "Enter elige, no lleva"
    assert pagina.locator("#llLlevar").inner_text() == "Llevar a N° 908"
    assert "Quedan en materiales de N° 908" in pagina.locator("#llPista").inner_text()
    pagina.locator("#llLlevar").click()
    pagina.locator("#dlgLlevar").wait_for(state="hidden")
    # «Proyectos en ejecución» con el 908 a la vista y lo nuevo simulado
    pagina.locator("#ejProyecto .ej-kpis").wait_for()
    _esperar_aviso(pagina, "3 gastos del Cotizador Histórico en N° 908")
    assert "Simulando 3 gastos por $37.900" in pagina.locator("#ejProyecto .ej-sim").inner_text()
    sobre = _esperar_archivo(pagina, EJ, lambda s: len(s["datos"]["items"]) == 3)
    assert _esquemas().validar_publicacion("ejecucion-proyectos", sobre) == []
    por = {x["descripcion"]: x for x in sobre["datos"]["items"]}
    codo = por['Codo de Cobre 1/2"']
    assert (codo["proyecto"], codo["tipo"], codo["categoria"], codo["cantidad"], codo["precio"], codo["estado"], codo["simular"]) == (
        "req:908", "costo", "Materiales", 10, 1190, "evaluar", True)
    assert (codo["proveedor"], codo["ref"], codo["cotizacion"]) == ("Ferretería Demo", "codo cobre 1 2", "")
    assert codo["nota"] == "Del Cotizador Histórico: lo pagado el 04-09-2026 (N° Ref. DEMO-101), actualizado por UF."
    assert por["Taladro percutor (ficticio)"]["nota"] == "Del Cotizador Histórico: lo pagado, actualizado por UF."
    assert {x["categoria"] for x in por.values()} == {"Materiales"}
    # Se deshace con el aviso, como cualquier cambio de esa vista
    pagina.locator("#aviso button", has_text="Deshacer").click()
    _esperar_archivo(pagina, EJ, lambda s: all(x.get("borrado") for x in s["datos"]["items"]))
    assert not errores
    pagina.context.close()


def test_la_cotizacion_del_cotizador_va_a_un_proyecto_en_formulacion(navegador, sitio):
    """En uno en formulación, el Formulador abre el proyecto en la tabla de esa categoría y, cuando ya lo muestra, recibe
    las filas para su «Pegar desde Excel» (la prueba del Formulador, .prueba/pegar/portal.js, revisa que abra el diálogo
    con ellas). La cotización no queda en el navegador: ni en la dirección que la pestaña recuerda."""
    pagina, errores = _llevar(navegador, sitio)
    pagina.locator('#llCat .pl-vista[data-cat="Equipos"]').click()
    pagina.locator('#llLista .ll-item[data-clave="req-901"]').click()
    assert pagina.locator("#llLlevar").inner_text() == "Llevar a N° 901"
    assert pagina.locator("#llPista").inner_text().startswith("Se abre QMPN-2026-901 en el Formulador, en equipos")
    pagina.locator("#llLlevar").click()
    pagina.locator("#dlgLlevar").wait_for(state="hidden")
    _esperar(pagina, "formulador", "hash", "#/p/f901/equipos")
    marco = _marco(pagina, "formulador")
    pagina.wait_for_timeout(700)
    assert marco.evaluate("() => document.body.dataset.recibido") is None, "espera a que el Formulador muestre su tabla"
    # El Formulador de mentira muestra recién ahora su «Pegar desde Excel», y anota lo que recibe
    marco.evaluate("""() => {
        addEventListener('message', (e) => { document.body.dataset.recibido = JSON.stringify(e.data); });
        const b = document.createElement('button');
        b.dataset.act = 'pegar-filas'; b.dataset.list = 'equipos'; b.textContent = 'Pegar desde Excel';
        document.body.append(b);
    }""")
    pagina.wait_for_function("() => !!document.getElementById('marco-formulador').contentDocument.body.dataset.recibido")
    m = json.loads(marco.evaluate("() => document.body.dataset.recibido"))
    assert (m["tipo"], m["proyecto"], m["lista"]) == ("quempin-pegar-costos", "f901", "equipos")
    assert m["texto"].split("\n") == ["Descripción\tUnidad\tCantidad\tCosto unitario neto", 'Codo de Cobre 1/2"\tUn.\t10\t1190',
                                      'Válvula de Bola Bronce 3/4"\tUn.\t2\t8500', "Taladro percutor (ficticio)\tUn.\t1\t9000"]
    assert m["origen"] == "Costos del Cotizador Histórico: lo que QUEMPIN pagó, actualizado por UF (la del 26-10-2026)."
    assert pagina.evaluate(JS_LEER_INTERCAMBIO, EJ) is None, "nada en «Proyectos en ejecución»"
    guardado = pagina.evaluate("() => JSON.stringify(Object.assign({}, localStorage, sessionStorage))")
    assert "Codo de Cobre" not in guardado and "/p/f901/equipos" in guardado
    assert not errores
    pagina.context.close()


def test_una_cotizacion_en_soles_va_solo_a_formulaciones_en_soles(navegador, sitio):
    """El Cotizador de Perú manda soles: «Proyectos en ejecución» lleva sus cuentas en pesos, y el Formulador no convierte
    monedas, así que solo se ofrecen formulaciones en soles. Si hay una sola, queda elegida."""
    def en_soles(archivos):
        archivos["publicado/formulador/f901.json"]["datos"]["parametros"] = {"moneda": "PEN"}
    pagina, errores = _llevar(navegador, sitio, datos=_cotizacion("PEN"), cambiar=en_soles)
    assert pagina.evaluate(JS_LL_GRUPOS) == {"En ejecución": [], "En formulación": ["req-901"]}
    assert "pesos chilenos" in pagina.locator("#llLista .ll-grupo").first.inner_text()
    assert pagina.locator("#llResumen").inner_text().startswith("3 líneas por S/")
    assert pagina.locator("#llResumen").inner_text().endswith("sin IVA, en soles.")
    assert pagina.locator('#llLista .ll-item[data-clave="req-901"]').get_attribute("aria-pressed") == "true"
    assert pagina.locator("#llLlevar").is_enabled()
    assert not errores
    pagina.context.close()


def test_el_cotizador_abierto_suelto_manda_su_cotizacion_al_portal_que_abre(navegador, sitio):
    """Abierto fuera del Portal, el carrito abre …/portal/#/llevar-cotizacion en otra pestaña: el Portal avisa que está
    listo y el carrito le manda la cotización como mensaje (la dirección no la lleva). Sin la biblioteca conectada, el
    diálogo dice qué falta."""
    ctx = navegador.new_context(viewport={"width": 1280, "height": 860})
    cot = ctx.new_page()
    cot.goto(sitio + "/finanzas-quempin/cotizador-historico/")
    with ctx.expect_page() as nueva:
        # Lo mismo que hace el carrito (template.html del Cotizador)
        cot.evaluate("""(datos) => {
            const v = window.open('/finanzas-quempin/portal/#/llevar-cotizacion', '_blank');
            addEventListener('message', (e) => {
                if (e.source === v && e.data && e.data.tipo === 'quempin-portal-listo') v.postMessage({ tipo: 'quempin-cotizacion', datos }, location.origin);
            });
        }""", _cotizacion())
    portal = nueva.value
    errores = []
    portal.on("pageerror", lambda e: errores.append(str(e)))
    portal.locator("#dlgLlevar").wait_for()
    assert portal.locator("#llResumen").inner_text().startswith("3 líneas por $37.900 sin IVA")
    assert "llevar-cotizacion" not in portal.url
    portal.locator("#llVacio").wait_for()
    assert "Conecta" in portal.locator("#llVacio").inner_text() or "Chrome o Edge" in portal.locator("#llVacio").inner_text()
    assert portal.locator("#llLlevar").is_disabled() and portal.locator("#llLista").is_hidden()
    portal.locator("#llCancelar").click()
    assert portal.locator("#dlgLlevar").is_hidden()
    assert not errores
    ctx.close()


@pytest.mark.parametrize("ancho", [360, 390])
def test_llevar_la_cotizacion_cabe_en_el_telefono(navegador, sitio, ancho):
    pagina, errores = _llevar(navegador, sitio, ancho=ancho, alto=760, movil=True)
    pagina.locator("#llLineasSum").click()
    afuera = pagina.evaluate("""() => [...document.querySelectorAll('#dlgLlevar *')].filter((e) => e.getClientRects().length
        && e.getBoundingClientRect().right > document.documentElement.clientWidth + 0.5).map((e) => e.id || e.className || e.tagName)""")
    assert afuera == []
    assert pagina.evaluate("() => parseFloat(getComputedStyle(document.getElementById('llBuscar')).fontSize)") >= 16
    assert pagina.locator("#llLlevar").is_visible() and pagina.locator("#llCancelar").is_visible()
    assert not errores
    pagina.context.close()
