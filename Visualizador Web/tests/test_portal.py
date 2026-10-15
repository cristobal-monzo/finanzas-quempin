# -*- coding: utf-8 -*-
"""Portal QUEMPIN (Visualizador Web/portal/index.html, 2026-10-15): todas las
herramientas en una sola ventana, ordenadas por necesidad, calculadoras incluidas.

Dos partes:
- El registro de herramientas del portal contra lo que existe: los tableros que
  publica publicar.py, los enlaces que leen el Análisis Financiero y el Centro de
  Costos, y (si están en este equipo) las rutas del Formulador y las pestañas de
  la Calculadora Técnica, que son otros repositorios.
- El portal en Chromium sobre un sitio de mentira con las mismas rutas que
  cristobal-monzo.github.io: las herramientas se abren dentro, un enlace a otra
  herramienta abre su pestaña en el portal, el buscador, el proyecto elegido, el
  país, las pestañas que vuelven al recargar y el teléfono. Nada usa datos reales.
"""
import functools
import http.server
import importlib.util
import json
import re
import threading
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
VISUALIZADOR = AQUI.parent
RAIZ = VISUALIZADOR.parent
PORTAL = VISUALIZADOR / "portal" / "index.html"
BASES = ("/formulacion-proyectos-quempin/", "/finanzas-quempin/", "/calculadora-tecnica-quempin/")
TIPOS = {"marco", "excel", "programa", "archivo", "ayuda", "inicio"}
LS_PROYECTOS = "qpn.formulacion.proyectos.v1"


def _registro():
    html = PORTAL.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="portal-registro">(.*?)</script>', html, re.S)
    assert m, "falta el registro de herramientas"
    return json.loads(m.group(1))


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _hermano(nombre):
    """Otro repositorio junto a este (Proyectos Claude/<nombre>), si está en este equipo."""
    for base in [RAIZ, *RAIZ.parents][:5]:
        if (base / nombre).is_dir():
            return base / nombre
    return None


# ---- El archivo y su registro -------------------------------------------------------------------

def test_cabecera_del_portal():
    html = PORTAL.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="es">' in html
    assert '<meta charset="utf-8">' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "user-scalable" not in html and "maximum-scale" not in html


def test_no_carga_nada_de_otro_sitio_ni_lleva_datos():
    html = PORTAL.read_text(encoding="utf-8")
    assert not re.search(r"<script[^>]+\bsrc=", html), "sin scripts externos"
    assert not re.search(r"<link[^>]+stylesheet", html) and "@import" not in html, "sin hojas de estilo externas"
    assert not re.search(r"url\(\s*['\"]?https?:", html), "las fuentes van embebidas"
    # Solo lee la clave del candado y los proyectos del Formulador: nunca los escribe.
    assert not re.search(r"setItem\(\s*(LS_CLAVE_TABLEROS|LS_FORMULADOR|'quempin_viz_clave'|'qpn\.formulacion)", html)
    assert "innerHTML = ICONOS" in html and html.count("innerHTML") == 1, "los textos se escriben con textContent"


def test_registro_bien_formado():
    reg = _registro()
    grupos = {g["id"] for g in reg["grupos"]}
    herr = reg["herramientas"]
    ids = [h["id"] for h in herr]
    assert len(ids) == len(set(ids)), "ids repetidos"
    por_id = {h["id"]: h for h in herr}
    for h in herr:
        assert h["tipo"] in TIPOS, h["id"]
        assert h["grupo"] in grupos | {"arriba", "oculto"}, h["id"]
        assert h["nombre"].strip(), h["id"]
        if h["tipo"] == "marco":
            for clave in ("ruta", "peru"):
                if clave in h:
                    assert h[clave].startswith(BASES) and h[clave].endswith("/"), (h["id"], h[clave])
        if h["tipo"] == "excel":
            assert h["url"].startswith("https://quempinspa2020.sharepoint.com/"), h["id"]
        if h["tipo"] == "programa":
            assert h.get("accion"), h["id"]
        if h["tipo"] == "archivo":
            assert h.get("donde"), h["id"]
        if h.get("alias"):
            dueno = por_id[h["familia"]]
            assert not dueno.get("alias") and dueno["ruta"] == h["ruta"], h["id"]
        if h.get("familia") and not h.get("alias"):
            assert h["familia"] == h["id"], h["id"]
        assert h.get("claves", "") == h.get("claves", "").lower(), h["id"]
    for g in grupos:
        assert any(h["grupo"] == g for h in herr), f"grupo vacío: {g}"
    for a in reg["atajos"]:
        assert a["herr"] in por_id and a["texto"].strip()


def test_las_calculadoras_estan_en_el_portal():
    reg = _registro()
    calcs = [h for h in reg["herramientas"] if h["grupo"] == "calcular"]
    assert [h["id"] for h in calcs] == ["diametro", "hidrogeno", "gas", "otros-gases"]
    assert all(h["ruta"].startswith("/calculadora-tecnica-quempin/") for h in calcs)


def test_estan_todos_los_tableros_publicados():
    """Cada tablero que publica publicar.py está en el portal (Chile en «ruta», Perú en «peru»), y el
    portal no apunta a uno que no se publica."""
    publicar = _cargar("publicar_para_test_portal", VISUALIZADOR / "publicar.py")
    publicados = {"/finanzas-quempin/" + subruta + "/" for subruta, _ in publicar.TABLEROS.values()}
    rutas = set()
    for h in _registro()["herramientas"]:
        for clave in ("ruta", "peru"):
            if h.get(clave, "").startswith("/finanzas-quempin/") and h[clave] != "/finanzas-quempin/":
                rutas.add(h[clave])
    assert rutas == publicados


def test_los_tableros_leen_los_enlaces_que_arma_el_portal():
    af = (RAIZ / "Sistema Analisis Financiero" / "Visualizador Web" / "template.html").read_text(encoding="utf-8")
    assert "#proyecto=" in af and "addEventListener('hashchange', abrirDesdeEnlace)" in af
    for pestana in ("tabResumen", "tabProyectos", "tabIngreso"):
        assert f'data-tab="{pestana}"' in af, pestana
    cc = (RAIZ / "Centro de Costos" / "Visualizador Web" / "template.html").read_text(encoding="utf-8")
    assert "p.get('tag')" in cc and "addEventListener('hashchange'" in cc
    candado = (VISUALIZADOR / "candado.js").read_text(encoding="utf-8")
    assert "pwGate" in candado and "quempin_viz_clave" in candado


def test_las_rutas_del_formulador_que_usa_el_portal():
    formulador = _hermano("Formulación de proyectos")
    app = formulador / "quempin-formulacion" / "js" / "app.js" if formulador else None
    if not app or not app.exists():
        pytest.skip("el Formulador no está en este equipo")
    texto = app.read_text(encoding="utf-8")
    for pieza in ("id: 'gantt'", "id: 'seguimiento'", "id: 'ficha'", "parts[0] === 'req'", "parts[0] === 'tag'"):
        assert pieza in texto, pieza
    store = (app.parent / "store.js").read_text(encoding="utf-8")
    assert f"'{LS_PROYECTOS}'" in store
    assert "id=\"pwGate\"" in (app.parent.parent / "index.html").read_text(encoding="utf-8")


def test_las_pestanas_de_las_calculadoras_son_las_de_la_calculadora_tecnica():
    calculadora = _hermano("Calculadora Técnica")
    gases = calculadora / "assets" / "gases.js" if calculadora else None
    if not gases or not gases.exists():
        pytest.skip("la Calculadora Técnica no está en este equipo")
    texto = gases.read_text(encoding="utf-8")
    reales = {}
    for bloque in re.split(r"\n  \{", texto)[1:]:
        ruta = re.search(r"ruta: '([^']+)'", bloque)
        herramientas = re.search(r"herramientas: \[(.*?)\]", bloque, re.S)
        if ruta and herramientas:
            reales["/calculadora-tecnica-quempin/" + ruta.group(1)] = re.findall(r"id: '([^']+)'", herramientas.group(1))
    portal = {h["ruta"]: [s["id"] for s in h.get("pestanas", [])]
              for h in _registro()["herramientas"] if h["grupo"] == "calcular"}
    assert portal == reales
    # El portal cambia de pestaña cambiando el #: cada calculadora con pestañas lo escucha.
    for ruta, pestanas in reales.items():
        if pestanas:
            ui = calculadora / ruta.split("/")[2] / "js" / "ui.js"
            assert "addEventListener('hashchange'" in ui.read_text(encoding="utf-8"), ui


# ---- El portal en el navegador, sobre un sitio de mentira ---------------------------------------

PAGINA = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>{titulo}</title></head>
<body data-herr="{herr}"><h1>{titulo}</h1>{cuerpo}
<script>
  function anotar() {{ document.body.dataset.hash = location.hash; }}
  anotar(); addEventListener('hashchange', anotar);
  var n = (+sessionStorage.getItem('cargas-{herr}') || 0) + 1;
  sessionStorage.setItem('cargas-{herr}', String(n));
  document.body.dataset.cargas = String(n);
</script>{script}</body></html>"""

CANDADO = """<div id="pwGate">Contraseña del equipo</div>
<script>if (localStorage.getItem('quempin_viz_clave')) document.getElementById('pwGate').hidden = true;</script>"""

PESTANAS_CALC = """<script>
  function activar(n) {{ document.body.dataset.tab = n; }}
  activar(decodeURIComponent(location.hash.slice(1)));
  addEventListener('hashchange', function () {{ activar(decodeURIComponent(location.hash.slice(1))); }});
</script>"""


def _sitio(raiz: Path):
    def pagina(ruta, titulo, herr, cuerpo="", script=""):
        destino = raiz / ruta.strip("/") / "index.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(PAGINA.format(titulo=titulo, herr=herr, cuerpo=cuerpo, script=script), encoding="utf-8")

    (raiz / "finanzas-quempin" / "portal").mkdir(parents=True)
    (raiz / "finanzas-quempin" / "portal" / "index.html").write_bytes(PORTAL.read_bytes())
    pagina("/finanzas-quempin/", "Herramientas QUEMPIN", "indice")
    pagina("/finanzas-quempin/centro-de-costos/", "Centro de Costos", "cc", CANDADO + """
      <a id="aAF" href="../analisis-financiero/#proyecto=DEMO">Ficha en Análisis Financiero</a>
      <a id="aForm" href="/formulacion-proyectos-quempin/" target="_blank">Formulador ↗</a>
      <a id="aMismo" href="#tag=OTRO">mismo tablero</a>
      <a id="aOtra" href="/otra-cosa/">otra página</a>
      <a id="aPortal" href="/finanzas-quempin/portal/">portal</a>""")
    pagina("/finanzas-quempin/centro-de-costos-peru/", "Centro de Costos Perú", "ccpe")
    pagina("/finanzas-quempin/analisis-financiero/", "Análisis Financiero", "af", CANDADO + """
      <button class="viz-tab-btn" data-tab="tabResumen">Resumen</button>
      <button class="viz-tab-btn" data-tab="tabProyectos">Proyectos</button>
      <button class="viz-tab-btn" data-tab="tabIngreso" id="tabBtnIngreso" hidden>Ingresar datos</button>
      <button id="entrar">Entrar</button>
      <button id="bOpen" onclick="window.open('/formulacion-proyectos-quempin/#/req/7', '_blank', 'noopener')">Pasar a ejecución</button>
      <button id="bReporte" onclick="var v = window.open('', '_blank'); document.body.dataset.reporte = v ? 'abierta' : 'nula'; if (v) v.close();">Reporte</button>""",
          """<script>
      function arrancar() {
        document.querySelectorAll('.viz-tab-btn').forEach(function (b) {
          b.addEventListener('click', function () { document.body.dataset.tab = b.dataset.tab; });
        });
        setTimeout(function () { document.getElementById('tabBtnIngreso').hidden = false; }, 300);
      }
      if (localStorage.getItem('quempin_viz_clave')) arrancar();
      document.getElementById('entrar').addEventListener('click', function () {
        localStorage.setItem('quempin_viz_clave', 'clave-de-mentira');
        document.getElementById('pwGate').hidden = true;
        arrancar();
      });
    </script>""")
    pagina("/finanzas-quempin/analisis-financiero-peru/", "Análisis Financiero Perú", "afpe")
    pagina("/finanzas-quempin/cotizador-historico/", "Cotizador Histórico", "cot")
    pagina("/finanzas-quempin/cotizador-historico-peru/", "Cotizador Histórico Perú", "cotpe")
    pagina("/finanzas-quempin/flujo-de-caja/", "Flujo de Caja", "fc")
    pagina("/finanzas-quempin/oportunidades/", "Oportunidades", "op")
    pagina("/formulacion-proyectos-quempin/", "Formulador", "formulador")
    pagina("/calculadora-tecnica-quempin/", "Calculadora Técnica", "calc")
    for ruta, herr in (("DiametroTuberia", "diametro"), ("Hidrogeno", "hidrogeno"),
                       ("GasNatural-GLP", "gas"), ("OtrosGases", "otros")):
        pagina(f"/calculadora-tecnica-quempin/{ruta}/", herr, herr,
               '<select id="selector-gas" onchange="location.href = this.value"><option value="">—</option>'
               '<option value="../OtrosGases/">Otros gases</option></select>', PESTANAS_CALC.format())
    pagina("/otra-cosa/", "Otra cosa", "otra")


class _Silencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def sitio(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("sitio")
    _sitio(raiz)
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Silencioso, directory=str(raiz)))
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()


@pytest.fixture(scope="module")
def navegador():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as error:   # sin Chromium instalado (py -3.14 -m playwright install chromium)
            pytest.skip(f"no se pudo abrir Chromium: {error}")
        yield nav
        nav.close()


PROYECTOS = {"schema": "quempin-formulacion/v1", "proyectos": [
    {"uid": "u1", "codigo": "QMPN-2026-001", "version": 1, "titulo": "Obra de prueba", "cliente": "Cliente Demo",
     "estado": "Borrador", "modificado": "2026-10-01T10:00:00Z",
     "vinculos": {"requerimiento": {"numero": 7}, "analisisFinanciero": {"tag": "demo"}}},
    {"uid": "u2", "codigo": "QMPN-2026-001", "version": 2, "titulo": "Obra de prueba", "cliente": "Cliente Demo",
     "estado": "Borrador", "modificado": "2026-10-03T10:00:00Z",
     "vinculos": {"requerimiento": {"numero": 7}, "analisisFinanciero": {"tag": "demo"}}},
    {"uid": "u3", "codigo": "QMPN-2026-002", "version": 1, "titulo": "Mantención de prueba", "cliente": "Otro Cliente",
     "estado": "Enviada", "modificado": "2026-10-02T10:00:00Z"},
    {"uid": "u4", "codigo": "QMPN-2026-003", "version": 1, "titulo": "Borrada", "estado": "Borrador",
     "eliminado": True, "modificado": "2026-10-04T10:00:00Z"},
]}


def _abrir_portal(navegador, sitio, ancho=1280, alto=860, clave=True, proyectos=False, movil=False):
    ctx = navegador.new_context(viewport={"width": ancho, "height": alto}, is_mobile=movil, has_touch=movil)
    semilla = {}
    if clave:
        semilla["quempin_viz_clave"] = "clave-de-mentira"
    if proyectos:
        semilla[LS_PROYECTOS] = json.dumps(PROYECTOS)
    ctx.add_init_script("""(semilla => {
        if (window !== window.top) return;
        for (const [k, v] of Object.entries(semilla)) if (localStorage.getItem(k) === null) localStorage.setItem(k, v);
        window.__abiertas = [];
        window.open = function (u) { window.__abiertas.push(String(u)); return null; };
    })(%s)""" % json.dumps(semilla))
    pagina = ctx.new_page()
    errores = []
    pagina.on("pageerror", lambda e: errores.append(str(e)))
    pagina.goto(sitio + "/finanzas-quempin/portal/")
    pagina.locator("#vistaInicio").wait_for()
    return pagina, errores


def _marco(pagina, familia, herr=None):
    """El documento de la herramienta abierta en la pestaña de esa familia, ya cargado."""
    pagina.wait_for_function("""([f, h]) => {
        const m = document.getElementById('marco-' + f);
        const b = m && m.contentDocument && m.contentDocument.body;
        return !!(b && b.dataset.herr && b.dataset.cargas && (!h || b.dataset.herr === h));
    }""", arg=[familia, herr])
    return pagina.locator("#marco-" + familia).element_handle().content_frame()


def _esperar(pagina, familia, campo, valor):
    """Espera a que la herramienta de esa pestaña muestre ese dato (también si se está recargando)."""
    pagina.wait_for_function("""([f, c, v]) => {
        const m = document.getElementById('marco-' + f);
        const b = m && m.contentDocument && m.contentDocument.body;
        return !!b && b.dataset[c] === v;
    }""", arg=[familia, campo, valor])


def _menu(pagina, nombre):
    pagina.locator("#menu .menu-item", has_text=nombre).first.click()


def _pestanas(pagina):
    return pagina.locator("#pestanas .ir").all_inner_texts()


def test_inicio_muestra_los_grupos_y_las_calculadoras(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    grupos = pagina.locator("#menu .grupo-cab").all_inner_texts()
    assert [g.strip() for g in grupos] == ["Conseguir trabajo", "Formular la oferta", "Calcular", "Cotizar y comprar",
                                           "Ejecutar y controlar", "Caja de la empresa", "Ayuda"]
    calcs = pagina.locator("#calcs .calc")
    assert calcs.count() == 4
    assert [calcs.nth(i).locator(".calc-pest button").count() for i in range(4)] == [0, 3, 5, 4]
    assert _pestanas(pagina) == ["Inicio"]
    assert pagina.locator("iframe").count() == 0
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
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos", "Análisis Financiero"]
    # Un enlace con target=_blank y un window.open también quedan en el portal, sin ventanas nuevas.
    pagina.locator("#pestanas .ir", has_text="Centro de Costos").click()
    cc.click("#aForm")
    _marco(pagina, "formulador", "formulador")
    pagina.locator("#pestanas .ir", has_text="Análisis Financiero").click()
    af.click("#bOpen")
    _esperar(pagina, "formulador", "hash", "#/req/7")
    assert len(pagina.context.pages) == 1
    assert _pestanas(pagina).count("Formulador de proyectos") == 1
    # El window.open('') de los reportes PDF no se toca: abre su ventana como siempre.
    pagina.locator("#pestanas .ir", has_text="Análisis Financiero").click()
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
    gas = _marco(pagina, "gas", "gas")
    _esperar(pagina, "gas", "tab", "quemador")
    # Otra pestaña de la misma calculadora: se cambia ahí mismo, sin recargar ni abrir otra.
    pagina.locator("#buscar").fill("combustion")
    pagina.keyboard.press("Enter")
    _esperar(pagina, "gas", "tab", "combustion")
    assert gas.evaluate("document.body.dataset.cargas") == "1"
    assert _pestanas(pagina) == ["Inicio", "Gas natural / GLP"]
    # Volver a elegirla en el menú no la mueve de donde quedó.
    _menu(pagina, "Gas natural / GLP")
    pagina.wait_for_timeout(200)
    assert gas.evaluate("document.body.dataset.tab") == "combustion"
    # Las fichas de Inicio también entran directo a una pestaña.
    pagina.locator("#pestanas .ir", has_text="Inicio").click()
    tarjeta = pagina.locator("#calcs .calc").filter(has=pagina.locator("h3", has_text=re.compile("^Hidrógeno$")))
    tarjeta.locator("button", has_text="Memoria de cálculo").click()
    h2 = _marco(pagina, "hidrogeno", "hidrogeno")
    _esperar(pagina, "hidrogeno", "tab", "memoria")
    # Búsquedas por necesidad
    for consulta, esperado in (("factura", "Centro de Costos"), ("orden de compra", "Orden de compra"),
                               ("caneria", "Diámetro de tubería"), ("licitaciones", "Oportunidades en Mercado Público")):
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
    h2 = _marco(pagina, "hidrogeno", "hidrogeno")
    h2.select_option("#selector-gas", "../OtrosGases/")
    _marco(pagina, "otros-gases", "otros")
    assert _pestanas(pagina) == ["Inicio", "Otros gases"]
    assert pagina.locator('#menu .menu-item[aria-current="page"]').inner_text().strip() == "Otros gases"
    assert not errores
    pagina.context.close()


def test_el_proyecto_elegido_abre_cada_herramienta_en_el(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio, proyectos=True)
    # Inicio: lo que hay en este navegador, sin la versión vieja ni el eliminado
    assert pagina.locator("#miDia .num").all_inner_texts() == ["1", "1"]
    assert pagina.locator("#recientes .reciente .t").all_inner_texts() == ["QMPN-2026-001 · Obra de prueba",
                                                                           "QMPN-2026-002 · Mantención de prueba"]
    # La Carta Gantt necesita un proyecto: lo pide y después la abre
    _menu(pagina, "Carta Gantt")
    assert pagina.locator("#popProyecto").is_visible()
    assert "Carta Gantt" in pagina.locator("#popNota").inner_text()
    assert pagina.locator("#listaProyectos .pop-item .t").all_inner_texts() == ["QMPN-2026-001 · Obra de prueba",
                                                                                "QMPN-2026-002 · Mantención de prueba"]
    pagina.locator("#listaProyectos .pop-item", has_text="QMPN-2026-001").click()
    formulador = _marco(pagina, "formulador", "formulador")
    _esperar(pagina, "formulador", "hash", "#/p/u2/gantt")
    assert "QMPN-2026-001" in pagina.locator("#proyectoActual").inner_text()
    # El mismo Formulador, en la misma pestaña
    _menu(pagina, "Formulador de proyectos")
    _esperar(pagina, "formulador", "hash", "#/req/7")
    assert _pestanas(pagina) == ["Inicio", "Formulador de proyectos · QMPN-2026-001"]
    _menu(pagina, "Centro de Costos")
    cc = _marco(pagina, "centro-costos", "cc")
    _esperar(pagina, "centro-costos", "hash", "#tag=DEMO")
    # Sin proyecto: las abiertas vuelven a su vista general
    pagina.locator("#btnProyecto").click()
    pagina.locator("#listaProyectos .pop-item", has_text="Sin proyecto").click()
    _esperar(pagina, "centro-costos", "hash", "")
    _esperar(pagina, "formulador", "hash", "#/")
    # Buscar por N° de requerimiento abre el seguimiento de ese proyecto
    pagina.locator("#buscar").fill("7")
    assert pagina.locator("#resultados .res-tit").first.inner_text() == "QMPN-2026-001 · Obra de prueba"
    pagina.keyboard.press("Enter")
    _esperar(pagina, "formulador", "hash", "#/p/u2/seguimiento")
    # Un proyecto nuevo guardado por el Formulador aparece sin recargar el portal
    formulador.evaluate("""k => {
        const d = JSON.parse(localStorage.getItem(k));
        d.proyectos.push({uid: 'u5', codigo: 'QMPN-2026-004', version: 1, titulo: 'Nuevo', estado: 'Borrador', modificado: '2026-10-05T10:00:00Z'});
        localStorage.setItem(k, JSON.stringify(d));
    }""", LS_PROYECTOS)
    pagina.locator("#btnProyecto").click()
    pagina.wait_for_function("() => document.querySelectorAll('#listaProyectos .pop-item').length === 4")   # + «Sin proyecto»
    assert not errores
    pagina.context.close()


def test_ingresar_datos_y_analisis_son_una_sola_pestana(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Ingresar avance y datos")
    af = _marco(pagina, "analisis", "af")
    _esperar(pagina, "analisis", "tab", "tabIngreso")
    _menu(pagina, "Análisis Financiero")
    _esperar(pagina, "analisis", "tab", "tabResumen")
    assert _pestanas(pagina) == ["Inicio", "Análisis Financiero"]
    assert af.evaluate("document.body.dataset.cargas") == "1"
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
    _menu(pagina, "Planilla de Ingreso")
    abiertas = pagina.evaluate("window.__abiertas")
    assert len(abiertas) == 1 and abiertas[0].startswith("https://quempinspa2020.sharepoint.com/")
    assert pagina.locator("iframe").count() == 0
    _menu(pagina, "Emitir cotización")
    assert pagina.locator("#dlgInfo").is_visible()
    assert "QUEMPIN.exe" in pagina.locator("#dlgInfo").inner_text()
    pagina.locator("#dlgInfo button", has_text="Entendido").click()
    _menu(pagina, "Control de Documentos")
    assert "QUEMPIN_Control de Documentos" in pagina.locator("#dlgInfoDonde").inner_text()
    pagina.keyboard.press("Escape")
    _menu(pagina, "Cómo usar el portal")
    assert pagina.locator("#dlgAyuda").is_visible()
    assert _pestanas(pagina) == ["Inicio"]
    assert not errores
    pagina.context.close()


def test_el_pais_elige_el_tablero_de_peru(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.select_option("#pais", "pe")
    _menu(pagina, "Cotizador Histórico")
    assert _marco(pagina, "cotizador", "cotpe").url.endswith("/cotizador-historico-peru/")
    _menu(pagina, "Flujo de Caja")
    assert _marco(pagina, "flujo-caja", "fc").url.endswith("/flujo-de-caja/")        # solo existe en Chile
    _menu(pagina, "Ingresar avance y datos")
    _marco(pagina, "analisis", "af")                                                  # solo existe en Chile
    assert pagina.locator("#pais").input_value() == "pe"
    # De vuelta a Chile, el Cotizador abierto se cambia solo
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
    _marco(pagina, "hidrogeno", "hidrogeno")
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for(state="attached")
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos", "Hidrógeno"]
    h2 = _marco(pagina, "hidrogeno", "hidrogeno")
    _esperar(pagina, "hidrogeno", "tab", "memoria")
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


def test_no_quedan_mas_de_ocho_herramientas_cargadas(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    nombres = ["Centro de Costos", "Análisis Financiero", "Flujo de Caja", "Cotizador Histórico", "Oportunidades",
               "Formulador de proyectos", "Diámetro de tubería", "Hidrógeno", "Gas natural / GLP"]
    for nombre in nombres:
        _menu(pagina, nombre)
    _marco(pagina, "gas", "gas")
    assert len(_pestanas(pagina)) == 10
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


JS_DESBORDES = _cargar("auditoria_movil_para_test_portal", VISUALIZADOR / "auditoria_movil.py").JS_DESBORDES


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
        _marco(pagina, "diametro", "diametro")
        assert pagina.locator("#buscar").is_hidden()
        d = pagina.evaluate(JS_DESBORDES)
        assert d["doc"] <= ancho and not d["fuera"], d
    assert not errores
    pagina.context.close()
