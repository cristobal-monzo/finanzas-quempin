# -*- coding: utf-8 -*-
"""Portal QUEMPIN en el teléfono: el resumen cifrado, solo para leer (2026-11-18, fase C del plan del Portal, maqueta M3).

Un teléfono no tiene showDirectoryPicker: el Portal baja datos/indice.json y datos/<parte>.json (los arma
Sistema Intercambio/resumen_movil.py, que tiene sus propias pruebas), los abre con la clave de los tableros y las
vistas leen igual que con la carpeta. Aquí se emula un teléfono sin esa función, con el resumen armado desde la
carpeta de prueba de «Proyectos en ejecución»."""
import base64
import functools
import http.server
import json
import threading

import pytest

from portal_comun import *  # noqa: F401,F403
from portal_comun import _Silencioso, _cargar, _ejecucion_de_prueba, _sitio, _menu, _esperar_aviso, RAIZ

CONTRASENA = "clave de mentira del telefono"
candado = _cargar("candado_para_test_movil", RAIZ / "Visualizador Web" / "candado.py")
resumen_movil = _cargar("resumen_movil_para_test", RAIZ / "Sistema Intercambio" / "resumen_movil.py")


@pytest.fixture(scope="module")
def sitio_movil(tmp_path_factory):
    """El sitio de mentira con portal/datos/ armado por resumen_movil.py desde la carpeta de prueba."""
    raiz = tmp_path_factory.mktemp("sitio_movil")
    _sitio(raiz)
    inter = tmp_path_factory.mktemp("intercambio")
    for ruta, contenido in _ejecucion_de_prueba().items():
        (inter / ruta).parent.mkdir(parents=True, exist_ok=True)
        (inter / ruta).write_text(json.dumps(contenido), encoding="utf-8")
    # Lo que nunca va al teléfono
    (inter / "publicado" / "precios-referencia.json").write_text('{"datos": {"secreto": 1}}', encoding="utf-8")
    resumen_movil.armar(inter, raiz / "finanzas-quempin" / "portal" / "datos", contrasena=CONTRASENA)
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Silencioso, directory=str(raiz)))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()


def _clave_b64():
    return base64.b64encode(candado.derivar_clave(CONTRASENA)).decode("ascii")


def _telefono(navegador, sitio, clave=True, usuario="LC", indice=None):
    """Un teléfono (390 × 844, táctil) sin showDirectoryPicker. indice(dict) cambia datos/indice.json al servirlo."""
    ctx = navegador.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    semilla = {"quempin_usuario": usuario}
    if clave:
        semilla["quempin_viz_clave"] = _clave_b64()
    ctx.add_init_script("""(semilla => {
        Object.defineProperty(window, 'showDirectoryPicker', { value: undefined, configurable: true });
        if (window !== window.top) return;
        for (const [k, v] of Object.entries(semilla)) if (localStorage.getItem(k) === null) localStorage.setItem(k, v);
    })(%s)""" % json.dumps(semilla))
    if indice:
        def cambiar(ruta):
            r = ruta.fetch()
            ruta.fulfill(response=r, body=json.dumps(indice(r.json())))
        ctx.route("**/portal/datos/indice.json*", cambiar)
    pagina = ctx.new_page()
    errores = []
    pagina.on("pageerror", lambda e: errores.append(str(e)))
    pagina.goto(sitio + "/finanzas-quempin/portal/")
    pagina.locator("#vistaInicio").wait_for()
    return pagina, errores


def _con_datos(pagina):
    pagina.wait_for_function("() => soloLectura() && rc.leido > 0")


def test_en_el_telefono_se_ve_la_semana_con_la_hora_del_resumen(navegador, sitio_movil):
    pagina, errores = _telefono(navegador, sitio_movil)
    _con_datos(pagina)
    franja = pagina.locator("#mvFranja")
    assert franja.is_visible() and franja.inner_text().startswith("Solo lectura · datos de las ")
    assert "viejo" not in (franja.get_attribute("class") or "")
    assert pagina.evaluate("document.documentElement.classList.contains('solo-lectura')")
    # La semana del Inicio (maqueta V4) también sale del resumen
    pagina.locator("#iniSemana .ini-sem-dia").first.wait_for()
    _menu(pagina, "Planificación semanal")
    pagina.locator("#plResumen .rc-kpi").first.wait_for()
    assert pagina.locator("#plVacio").is_hidden()
    assert pagina.locator("#plAgregar").is_hidden()
    pagina.wait_for_function("() => [...document.querySelectorAll('#vistaPlan .pl-chip')].length > 0 || /En obra/.test(document.getElementById('vistaPlan').textContent)")
    assert pagina.locator("#vistaPlan .pl-arr").count() == 0 or pagina.locator("#vistaPlan .pl-arr").first.is_hidden()
    assert errores == []


def test_en_el_telefono_no_se_cambia_nada(navegador, sitio_movil):
    """Lo que cambia algo se frena con un aviso, y la carpeta de mentira no deja escribir aunque algo se cuele."""
    pagina, errores = _telefono(navegador, sitio_movil)
    _con_datos(pagina)
    _menu(pagina, "Planificación semanal")
    pagina.locator("#plResumen .rc-kpi").first.wait_for()
    assert pagina.evaluate("plCambiar(plSemanaVista(), [], 'x')") is None
    _esperar_aviso(pagina, "Solo lectura")
    assert pagina.evaluate("planif.porGuardar.size") == 0
    assert pagina.locator("#plPop").is_hidden()
    assert pagina.evaluate("""async () => {
        const buzon = await rc.dir.getDirectoryHandle('buzon', { create: true });      // ya está: se entrega
        try { await buzon.getFileHandle('nuevo.json', { create: true }); return 'escribió'; } catch (e) { return e.name; }
    }""") == "NotAllowedError"
    assert pagina.evaluate("""async () => {
        const pub = await rc.dir.getDirectoryHandle('publicado');
        try { await (await pub.getFileHandle('requerimientos.json')).createWritable(); return 'escribió'; } catch (e) { return e.name; }
    }""") == "NotAllowedError"
    # No va lo que no sirve para leer
    assert pagina.evaluate("""async () => {
        const pub = await rc.dir.getDirectoryHandle('publicado');
        try { await pub.getFileHandle('precios-referencia.json'); return 'está'; } catch (e) { return e.name; }
    }""") == "NotFoundError"
    assert errores == []


def test_en_el_telefono_requerimientos_y_ejecucion_muestran_datos(navegador, sitio_movil):
    pagina, errores = _telefono(navegador, sitio_movil)
    _con_datos(pagina)
    _menu(pagina, "Requerimientos")
    pagina.locator("#vistaPlanilla").get_by_text("En obra").first.wait_for()
    assert pagina.locator("#pqNuevo").is_hidden()
    _menu(pagina, "Proyectos en ejecución")
    pagina.locator("#ejTarjetas .ej-tarjeta").first.wait_for()
    assert pagina.locator("#ejVacio").is_hidden()
    assert errores == []


def test_sin_la_clave_el_telefono_la_pide_en_la_franja(navegador, sitio_movil):
    pagina, errores = _telefono(navegador, sitio_movil, clave=False)
    entrar = pagina.locator("#mvEntrar")
    entrar.wait_for()
    assert pagina.locator("#mvTexto").inner_text() == "Escribe la contraseña del equipo para ver los datos"
    pagina.locator("#mvContrasena").fill("otra cosa")
    entrar.locator("button").click()
    _esperar_aviso(pagina, "Contraseña incorrecta")
    pagina.locator("#mvContrasena").fill(CONTRASENA.upper())       # como en los tableros: sin mayúsculas
    entrar.locator("button").click()
    _con_datos(pagina)
    assert entrar.is_hidden()
    assert pagina.evaluate("localStorage.getItem('quempin_viz_clave')") == _clave_b64()
    assert errores == []


def test_con_mas_de_2_horas_la_franja_se_pone_ambar(navegador, sitio_movil):
    from datetime import datetime, timedelta
    hace = (datetime.now().astimezone() - timedelta(hours=3)).isoformat(timespec="seconds")
    pagina, errores = _telefono(navegador, sitio_movil, indice=lambda i: dict(i, revisado=hace))
    _con_datos(pagina)
    franja = pagina.locator("#mvFranja")
    assert "viejo" in franja.get_attribute("class")
    assert franja.inner_text().endswith("(hace 3 h)")
    assert errores == []


def test_en_el_telefono_el_inicio_apaga_lo_que_no_funciona_y_deja_las_calculadoras(navegador, sitio_movil):
    """Maqueta M3 (2026-11-18): el mismo Inicio. Subir, Rendiciones y lo de Sistema QUEMPIN, apagados; el usuario pidió
    expresamente que las calculadoras queden."""
    pagina, errores = _telefono(navegador, sitio_movil)
    apagadas = pagina.locator("#iniAreas .ini-item.apagado").evaluate_all("bs => bs.map((b) => b.dataset.herr)")
    assert sorted(apagadas) == ["cotizacion", "orden-compra", "rendiciones", "subir-cc"]
    calcular = pagina.locator('#iniAreas .ini-area[data-grupo="calcular"] .ini-item')
    assert calcular.count() == 4 and calcular.evaluate_all("bs => bs.every((b) => !b.classList.contains('apagado'))")
    pagina.locator('#iniAreas .ini-item[data-herr="rendiciones"]').dispatch_event("click")      # aria-disabled
    _esperar_aviso(pagina, "Rendiciones: necesita un computador")
    assert pagina.locator("#vistaRendir").is_hidden()
    pagina.locator('#iniAreas .ini-item[data-herr="hidrogeno"]').click()
    pagina.wait_for_function("() => estado.pestanas.some((p) => p.herr === 'hidrogeno')")
    assert errores == []


def test_en_el_computador_con_la_carpeta_no_se_usa_el_resumen(navegador, sitio_movil):
    """Con showDirectoryPicker y sin la clave recordada no se baja nada: se ve lo de siempre («conecta la carpeta»)."""
    ctx = navegador.new_context(viewport={"width": 1280, "height": 860})
    pedidos = []
    ctx.on("request", lambda r: pedidos.append(r.url))
    pagina = ctx.new_page()
    pagina.goto(sitio_movil + "/finanzas-quempin/portal/")
    pagina.wait_for_function("() => rc.sinDatos === 'conectar'")
    assert not any("/portal/datos/" in u for u in pedidos)
    assert pagina.locator("#mvFranja").is_hidden() and not pagina.evaluate("soloLectura()")
    ctx.close()
