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
TIPOS = {"marco", "excel", "programa", "archivo", "ayuda", "inicio", "vista"}
LS_PROYECTOS = "qpn.formulacion.proyectos.v1"


def _bloque(id_):
    html = PORTAL.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="%s">(.*?)</script>' % id_, html, re.S)
    assert m, f"falta el bloque {id_}"
    return json.loads(m.group(1))


def _registro():
    return _bloque("portal-registro")


def _conexiones():
    return _bloque("portal-conexiones")


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
            assert re.fullmatch(r"quempin://[a-z-]+", h.get("enlace", "")), h["id"]
        if h["tipo"] == "archivo":
            assert h.get("donde"), h["id"]
        if h.get("alias"):
            dueno = por_id[h["familia"]]
            assert not dueno.get("alias") and dueno["ruta"] == h["ruta"], h["id"]
        if h.get("familia") and not h.get("alias"):
            # La dueña de la familia, o una página hermana con su propia ruta (las calculadoras)
            dueno = por_id[h["familia"]]
            assert h["familia"] == h["id"] or (dueno["familia"] == dueno["id"] and h["ruta"] != dueno["ruta"]), h["id"]
        if h.get("incrustar"):
            assert h["incrustar"] in {"tablero", "calculadora", "formulador"} and h["tipo"] == "marco", h["id"]
        if h["tipo"] == "vista":   # una vista propia del portal, con su sección en la página
            assert f'id="{h["vista"]}"' in PORTAL.read_text(encoding="utf-8"), h["id"]
        assert h.get("claves", "") == h.get("claves", "").lower(), h["id"]
    for g in grupos:
        assert any(h["grupo"] == g for h in herr), f"grupo vacío: {g}"
    # Lo que muestra el Inicio: cada herramienta con su línea breve, que cabe en una línea
    for h in herr:
        if h["grupo"] in grupos - {"ayuda"}:
            assert 0 < len(h.get("breve", "")) <= 38, h["id"]
        if h["tipo"] == "marco":   # el nombre de su pestaña
            assert len(h.get("corto", h["nombre"])) <= 18, h["id"]


def test_los_grupos_del_pedido_del_2026_10_16():
    """Cuatro grupos y la ayuda; la calculadora al final, antes de la ayuda."""
    assert [g["nombre"] for g in _registro()["grupos"]] == [
        "Formulación de proyectos", "Control y finanzas", "Cotizar y comprar", "Calculadora", "Ayuda"]


def test_la_ayuda_sin_indice_anterior_y_con_configuracion():
    """Pedido del 2026-10-16: fuera el «Índice anterior»; en su lugar, Configuración y conexiones."""
    ayuda = [h for h in _registro()["herramientas"] if h["grupo"] == "ayuda"]
    assert [h["nombre"] for h in ayuda] == ["Cómo usar el portal", "Configuración y conexiones"]
    assert not any(h.get("ruta") == "/finanzas-quempin/" for h in _registro()["herramientas"])


def test_conexiones_bien_referenciadas():
    """Cada carpeta, programa o acceso dice para qué es, quién lo usa, dónde está y qué pasa si falta;
    cada herramienta del portal (salvo las calculadoras) necesita algo de la lista."""
    cx = _conexiones()
    reg = _registro()
    ids_herr = {h["id"] for h in reg["herramientas"]}
    elementos = cx["elementos"]
    ids = [e["id"] for e in elementos] + [cx["procesador"]["id"]]
    assert len(ids) == len(set(ids)), "ids repetidos"
    for e in elementos:
        for campo in ("tipo", "nombre", "corto", "para", "falta"):
            assert e.get(campo, "").strip(), (e["id"], campo)
        assert e["usan"] and set(e["usan"]) <= ids_herr | {"procesador"}, e["id"]
        assert e.get("ruta") or e["tipo"] in {"Cuenta", "En el navegador"}, f"{e['id']}: ¿dónde está?"
        if "web" in e:
            assert e["web"].startswith("https://quempinspa2020.sharepoint.com/"), e["id"]
        if "abrir" in e:
            assert e["abrir"] in ids_herr, e["id"]
        assert e.get("estado") in {None, "navegador", "biblioteca", "procesador", "contrasena"}, e["id"]
    por_id = {h["id"]: h for h in reg["herramientas"]}
    usadas = {u for e in elementos for u in e["usan"]}
    for h in reg["herramientas"]:
        if h["grupo"] in {"formular", "finanzas", "cotizar"}:
            assert h["id"] in usadas or (h.get("alias") and h["familia"] in usadas), h["id"]
    tareas = [t["nombre"] for t in cx["procesador"]["tareas"]]
    assert tareas == ["Procesar intercambio QUEMPIN", "Actualizar Finanzas QUEMPIN", "Oportunidades Mercado Publico QUEMPIN"]
    assert por_id["planilla"]["url"].startswith("https://quempinspa2020.sharepoint.com/sites/Licitaciones-Enproceso/")


def test_las_rutas_de_conexiones_son_las_del_intercambio():
    """Los nombres de bibliotecas y carpetas, contra los que buscan las herramientas (Sistema Intercambio/ubicacion.py,
    que Sistema QUEMPIN y el Análisis Financiero copian textual)."""
    ubicacion = _cargar("ubicacion_para_test_portal", RAIZ / "Sistema Intercambio" / "ubicacion.py")
    e = {x["id"]: x for x in _conexiones()["elementos"]}
    clave = ubicacion._clave
    assert e["biblioteca"]["ruta"][-1] == ubicacion.BIBLIOTECA_FORMULACION
    assert e["gestion"]["ruta"][-1] == ubicacion.BIBLIOTECA_GESTION
    assert e["planilla"]["ruta"][-2:] == [ubicacion.BIBLIOTECA_FORMULACION, ubicacion.PLANILLA_REQUERIMIENTOS]
    assert [clave(x) for x in e["intercambio"]["ruta"][-3:]] == [
        clave(ubicacion.BIBLIOTECA_FORMULACION), clave(ubicacion.CARPETA_HERRAMIENTAS), clave(ubicacion.CARPETA_INTERCAMBIO)]
    # Sistema QUEMPIN encuentra el intercambio subiendo desde su carpeta compartida: las dos bibliotecas van juntas
    assert e["compartida"]["ruta"][0] == e["biblioteca"]["ruta"][0] == e["cotizaciones"]["ruta"][0]
    assert "web" in e["intercambio"] and e["intercambio"]["web"].endswith("/.HERRAMIENTAS FORMULACIÓN/Intercambio")


def test_sistema_quempin_conoce_los_enlaces_del_portal():
    """Cada quempin:// del portal es una sección que QUEMPIN.exe abre (Sistema QUEMPIN app/protocolo.py)."""
    sistema = _hermano("Sistema QUEMPIN")
    protocolo = sistema / "app" / "protocolo.py" if sistema else None
    if not protocolo or not protocolo.exists():
        pytest.skip("Sistema QUEMPIN no está en este equipo")
    secciones = set(re.findall(r'^\s+"([a-z-]+)": \d+,$', protocolo.read_text(encoding="utf-8"), re.M))
    assert {"cotizacion", "orden-compra"} <= secciones
    for h in _registro()["herramientas"]:
        if h["tipo"] == "programa":
            assert h["enlace"].removeprefix("quempin://") in secciones, h["id"]


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

# Cabeceras como las reales: lo que el portal esconde dentro de él (logo, título, modo oscuro).
CABECERA_TABLERO = """<div class="viz-root"><header class="viz-header"><div class="viz-container">
  <div class="viz-logo"><div class="viz-wordmark">QUEMPIN</div></div>
  <div class="viz-titleblock"><h1>Tablero — Visualizador</h1><p id="vizGenerated">Datos al 15-10-2026</p></div>
  <button class="viz-theme-toggle" id="themeToggle">Modo oscuro</button></div>
  <nav class="viz-modnav"><a class="viz-modnav-tab" href="/finanzas-quempin/flujo-de-caja/">Flujo</a></nav></header></div>"""
CABECERA_CALC = """<header class="viz-header"><div class="viz-container"><span class="viz-wordmark">QUEMPIN</span>
  <div class="viz-titleblock"><h1>Calculadora</h1></div><button id="themeToggle">Modo oscuro</button></div></header>"""
CABECERA_FORMULADOR = """<div class="viz-root"><header class="viz-header"><div class="viz-container">
  <a class="viz-logo" href="#/"><span class="viz-wordmark">QUEMPIN</span></a>
  <div class="viz-titleblock"><h1>Formulación de Proyectos</h1></div>
  <button class="viz-theme-toggle hb usuario-btn" id="usuarioBtn">LC</button>
  <button class="viz-theme-toggle hb" id="herrBtn">Herramientas</button>
  <button class="viz-theme-toggle hb" data-act="config" id="config">Configuración</button>
  <button class="viz-theme-toggle hb" id="themeToggle">Modo oscuro</button></div>
  <nav class="viz-modnav"><div class="viz-container viz-modnav-inner" id="modnav"><a class="viz-modnav-tab is-active" href="#/">Proyectos</a></div></nav>
</header></div>"""

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
    pagina("/finanzas-quempin/centro-de-costos/", "Centro de Costos", "cc", CABECERA_TABLERO + CANDADO + """
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
    pagina("/formulacion-proyectos-quempin/", "Formulador", "formulador", CABECERA_FORMULADOR)
    # El pulso del procesador que lee «Configuración y conexiones» (el del Formulador, si está en este equipo)
    formulador = _hermano("Formulación de proyectos")
    pulso = formulador / "quempin-formulacion" / "js" / "pulso.js" if formulador else None
    if pulso and pulso.exists():
        (raiz / "formulacion-proyectos-quempin" / "js").mkdir(parents=True, exist_ok=True)
        (raiz / "formulacion-proyectos-quempin" / "js" / "pulso.js").write_bytes(pulso.read_bytes())
    pagina("/calculadora-tecnica-quempin/", "Calculadora Técnica", "calc")
    for ruta, herr in (("DiametroTuberia", "diametro"), ("Hidrogeno", "hidrogeno"),
                       ("GasNatural-GLP", "gas"), ("OtrosGases", "otros")):
        pagina(f"/calculadora-tecnica-quempin/{ruta}/", herr, herr,
               CABECERA_CALC + '<select id="selector-gas" onchange="location.href = this.value"><option value="">—</option>'
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
        // Los quempin:// (QUEMPIN.exe) se anotan en vez de pedirle a Windows que abra el programa.
        window.__lanzados = [];
        document.addEventListener('click', (e) => {
            const a = e.target && e.target.closest ? e.target.closest('a[href^="quempin:"]') : null;
            if (a) { window.__lanzados.push(a.getAttribute('href')); e.preventDefault(); }
        }, true);
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
    """Elige una herramienta por su nombre en el menú: lo abre con ☰, despliega su grupo (hay uno solo
    abierto a la vez) y la elige; al elegirla el menú se cierra."""
    herr = _registro()["herramientas"]
    h = next((x for x in herr if x["nombre"] == nombre), None) or next(x for x in herr if x["nombre"].startswith(nombre))
    if pagina.locator("#menu").is_hidden():
        pagina.locator("#btnMenu").click()
    item = pagina.locator(f'#menu .menu-item[data-herr="{h["id"]}"]')
    if not item.is_visible():
        item.locator("xpath=ancestor::section[1]/button[contains(@class, 'grupo-cab')]").click()
    item.click()


def _pestanas(pagina):
    return pagina.locator("#pestanas .ir").all_inner_texts()


JS_BARRAS = """() => ['.vista-inicio', '.menu-lista', '.pestanas-lista'].map((s) => {
    const e = document.querySelector(s);
    return e && e.getClientRects().length ? [s, e.scrollHeight - e.clientHeight, e.scrollWidth - e.clientWidth] : [s, 0, 0];
}).filter(([s, alto, ancho]) => alto > 1 || ancho > 1)"""


def test_inicio_muestra_todas_las_herramientas_por_grupo(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    grupos = pagina.locator("#menu .grupo-cab").all_inner_texts()
    assert [g.strip() for g in grupos] == ["Formulación de proyectos", "Control y finanzas", "Cotizar y comprar",
                                           "Calculadora", "Ayuda"]
    assert pagina.locator("#iniGrupos .ini-grupo h2").all_inner_texts() == [
        "Formulación de proyectos", "Control y finanzas", "Cotizar y comprar", "Calculadora"]
    reg = _registro()
    esperadas = [h["id"] for h in reg["herramientas"] if h["grupo"] in {"formular", "finanzas", "cotizar", "calcular"}]
    assert pagina.evaluate("[...document.querySelectorAll('#iniGrupos .ini-item')].map(b => b.dataset.herr)") == esperadas
    # Lo que se abre fuera del portal (Excel, Sistema QUEMPIN) lleva la flecha ↗
    fuera = [h["id"] for h in reg["herramientas"] if h["id"] in esperadas and h["tipo"] != "marco"]
    assert fuera == ["planilla", "cotizacion", "orden-compra"]
    assert pagina.locator("#iniGrupos .ini-item:has(.ini-fuera)").count() == len(fuera)
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
    # Sin menú fijo al lado, las cuatro columnas caben desde 1024 px
    columnas = "getComputedStyle(document.getElementById('iniGrupos')).gridTemplateColumns.split(' ').length"
    assert pagina.evaluate(columnas) == 4
    assert pagina.evaluate("getComputedStyle(document.querySelector('.menu-lista')).scrollbarWidth") == "none"
    # El menú (☰), con su grupo más largo desplegado, tampoco desborda; va encima y no achica el Inicio
    _menu(pagina, "Seguimiento")
    pagina.locator("#pestanas .ir", has_text="Inicio").click()
    pagina.locator("#btnMenu").click()
    assert pagina.locator('#menu .grupo-cab[aria-expanded="true"]').inner_text().strip() == "Formulación de proyectos"
    assert pagina.evaluate(JS_BARRAS) == []
    assert pagina.evaluate(columnas) == 4
    assert not errores
    pagina.context.close()


def test_el_menu_despliega_un_grupo_a_la_vez(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.locator("#btnMenu").click()          # el menú con nombres
    abiertos = lambda: pagina.locator('#menu .grupo-cab[aria-expanded="true"]').all_inner_texts()
    assert [g.strip() for g in abiertos()] == ["Formulación de proyectos"]
    pagina.locator("#grupo-finanzas").click()
    assert [g.strip() for g in abiertos()] == ["Control y finanzas"]
    assert pagina.locator("#items-formular").is_hidden()
    pagina.locator("#grupo-finanzas").click()
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


def test_el_proyecto_elegido_abre_cada_herramienta_en_el(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio, proyectos=True)
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
    _menu(pagina, "Formulador")
    _esperar(pagina, "formulador", "hash", "#/req/7")
    assert _pestanas(pagina) == ["Inicio", "Formulador · QMPN-2026-001"]
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
    _menu(pagina, "Ingresar avance")
    af = _marco(pagina, "analisis", "af")
    _esperar(pagina, "analisis", "tab", "tabIngreso")
    _menu(pagina, "Análisis Financiero")
    _esperar(pagina, "analisis", "tab", "tabResumen")
    assert _pestanas(pagina) == ["Inicio", "Análisis"]
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
    _menu(pagina, "Ingresar avance")
    _marco(pagina, "analisis", "af")                                                  # solo existe en Chile
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


def test_una_pestana_por_herramienta_y_no_mas_de_ocho_cargadas(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    nombres = ["Centro de Costos", "Análisis Financiero", "Ingresar avance", "Flujo de Caja", "Cotizador Histórico",
               "Oportunidades", "Formulador", "Carta Gantt", "Seguimiento", "Diámetro de tubería", "Hidrógeno",
               "Gas natural / GLP", "Configuración y conexiones"]
    for nombre in nombres:
        _menu(pagina, nombre)
        if pagina.locator("#popProyecto").is_visible():            # la Carta Gantt pide proyecto: se sigue sin
            pagina.keyboard.press("Escape")
    assert len(_pestanas(pagina)) == 9                               # Inicio + 8 pestañas, ni una más
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
        _marco(pagina, "calculadora", "diametro")
        assert pagina.locator("#buscar").is_hidden()
        d = pagina.evaluate(JS_DESBORDES)
        assert d["doc"] <= ancho and not d["fuera"], d
    assert not errores
    pagina.context.close()


# ---- Dentro del portal las herramientas no repiten su cabecera (2026-10-16) ----------------------

def _estilo(marco, selector, prop="display"):
    return marco.evaluate("([s, p]) => { const e = document.querySelector(s); return e ? getComputedStyle(e)[p] : null; }",
                          [selector, prop])


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
    assert pagina.evaluate("[...document.querySelectorAll('#iniGrupos .ini-item.abierta')].map(b => b.dataset.herr)") == ["flujo-caja"]
    assert not errores
    pagina.context.close()


# ---- Configuración y conexiones (2026-10-16) -------------------------------------------------------

JS_CONECTAR = """async (minutos) => {
    // Lo que deja el Formulador al conectar la biblioteca (js/intercambio.js), con carpetas del almacenamiento
    // privado del navegador en vez de las de OneDrive: así el permiso ya está dado.
    const raiz = await navigator.storage.getDirectory();
    const bib = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos', { create: true });
    const herr = await bib.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN', { create: true });
    const inter = await herr.getDirectoryHandle('Intercambio', { create: true });
    const pub = await inter.getDirectoryHandle('publicado', { create: true });
    const w = await (await pub.getFileHandle('estado.json', { create: true })).createWritable();
    await w.write(JSON.stringify({ esquema: 'quempin.intercambio/1', datos: { procesador: {
        ultimaCorrida: new Date(Date.now() - minutos * 60000).toISOString(), pasos: {} } } }));
    await w.close();
    await new Promise((ok, mal) => {
        const r = indexedDB.open('qpn-intercambio', 1);
        r.onupgradeneeded = () => r.result.createObjectStore('carpetas');
        r.onerror = () => mal(r.error);
        r.onsuccess = () => {
            const tx = r.result.transaction('carpetas', 'readwrite');
            tx.objectStore('carpetas').put(inter, 'intercambio');
            tx.objectStore('carpetas').put(bib, 'biblioteca');
            tx.oncomplete = () => { r.result.close(); ok(); };
            tx.onerror = () => mal(tx.error);
        };
    });
}"""

JS_ESTADO_CX = """() => Object.fromEntries([...document.querySelectorAll('#cxEstado li')].map(li =>
    [li.dataset.estado, [li.dataset.nivel, li.querySelector('.cx-est-det').textContent]]))"""


def _estado_cx(pagina, esperar=None):
    """El estado de cada fila de «En este navegador», cuando ya se revisó (o cuando llega a lo esperado)."""
    pagina.wait_for_function("""(esperado) => {
        const filas = [...document.querySelectorAll('#cxEstado li')];
        if (!filas.length || !filas.every((li) => li.dataset.nivel)) return false;
        return !esperado || Object.entries(esperado).every(([s, n]) =>
            document.querySelector('#cxEstado li[data-estado="' + s + '"]').dataset.nivel === n);
    }""", arg=esperar)
    return pagina.evaluate(JS_ESTADO_CX)


def test_configuracion_y_conexiones_en_su_pestana(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.locator("#iniConexiones").click()
    assert _pestanas(pagina) == ["Inicio", "Conexiones"]
    assert pagina.locator("#vistaConexiones").is_visible() and pagina.locator("#vistaInicio").is_hidden()
    assert pagina.url.endswith("#/conexiones")
    assert pagina.locator("iframe").count() == 0
    assert pagina.locator("#btnRecargar").is_hidden() and pagina.locator("#btnAparte").is_hidden()
    # Una tarjeta por cada carpeta, programa o acceso, más el computador del procesador
    cx = _conexiones()
    tarjetas = pagina.evaluate("[...document.querySelectorAll('.cx-tarjeta')].map(t => t.id)")
    assert tarjetas == ["cx-" + e["id"] for e in cx["elementos"]] + ["cx-procesador"]
    # Sus enlaces van a SharePoint, codificados
    enlaces = pagina.evaluate("[...document.querySelectorAll('.cx-tarjeta a[href]')].map(a => a.getAttribute('href'))")
    assert len(enlaces) == sum(1 for e in cx["elementos"] if "web" in e)
    assert all(h.startswith("https://quempinspa2020.sharepoint.com/") and " " not in h for h in enlaces)
    assert any(h.endswith("/.HERRAMIENTAS%20FORMULACI%C3%93N/Intercambio") for h in enlaces)
    # Qué necesita cada herramienta: las que necesitan lo mismo van juntas; las calculadoras, nada
    filas = pagina.evaluate("""() => [...document.querySelectorAll('#cxNecesita tbody tr')].map(tr =>
        [tr.querySelector('th').textContent, [...tr.querySelectorAll('.cx-chip')].map(c => c.textContent)])""")
    por_nombre = dict(filas)
    for juntas in ("Formulador, Carta Gantt y Seguimiento", "Centro de Costos y Análisis Financiero",
                   "Emitir cotización y Orden de compra"):
        assert juntas in por_nombre, juntas
    assert filas[-1] == ["Calculadora (todas)", []]
    assert {"Biblioteca Formulación", "Carpeta de intercambio", "Contraseña"} <= set(por_nombre["Formulador, Carta Gantt y Seguimiento"])
    assert "QUEMPIN.exe" in por_nombre["Emitir cotización y Orden de compra"]
    # Un dato de la tabla lleva a su tarjeta; «Lo usan» abre la herramienta
    pagina.locator("#cxNecesita .cx-chip", has_text="QUEMPIN.exe").first.click()
    pagina.wait_for_function("() => document.getElementById('cx-sistema').classList.contains('resaltada')")
    pagina.locator("#cx-biblioteca .cx-usan .cx-chip", has_text="Formulador").click()
    _marco(pagina, "formulador", "formulador")
    assert _pestanas(pagina) == ["Inicio", "Conexiones", "Formulador"]
    # La pestaña vuelve al recargar, y se cierra como cualquier otra
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for(state="attached")
    assert _pestanas(pagina) == ["Inicio", "Conexiones", "Formulador"]
    pagina.locator("#pestanas .ir", has_text="Conexiones").click()
    assert pagina.locator("#vistaConexiones").is_visible()
    pagina.locator("#pestanas .pestana", has_text="Conexiones").locator(".x").click()
    assert _pestanas(pagina) == ["Inicio", "Formulador"]
    assert pagina.locator("#vistaConexiones").is_hidden()
    # También desde el buscador y desde la Ayuda del menú
    pagina.locator("#buscar").fill("carpeta de intercambio")
    assert pagina.locator("#resultados .res-tit").first.inner_text() == "Configuración y conexiones"
    pagina.keyboard.press("Escape")
    _menu(pagina, "Configuración y conexiones")
    assert pagina.locator("#vistaConexiones").is_visible()
    assert not errores
    pagina.context.close()


def test_conexiones_revisa_este_navegador(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio, clave=False)
    _menu(pagina, "Configuración y conexiones")
    e = _estado_cx(pagina)
    assert e["contrasena"][0] == "warn"
    puede = pagina.evaluate("typeof showDirectoryPicker === 'function'")
    assert e["navegador"][0] == ("ok" if puede else "bad")
    if not puede:
        pytest.skip("este Chromium no conecta carpetas")
    assert e["biblioteca"][0] == "bad" and "Sin conectar" in e["biblioteca"][1]
    assert e["procesador"][0] == "nada"
    # Solo mira: no crea la base del Formulador cuando no existe
    assert "qpn-intercambio" not in pagina.evaluate("indexedDB.databases().then((d) => d.map((x) => x.name))")
    # Con la biblioteca conectada (como la deja el Formulador) y el procesador al día
    pagina.evaluate(JS_CONECTAR, 30)
    pagina.locator("#pestanas .ir", has_text="Inicio").click()
    pagina.locator("#pestanas .ir", has_text="Conexiones").click()
    e = _estado_cx(pagina, {"biblioteca": "ok", "procesador": "ok"})
    assert "Formulación de proyectos - Documentos" in e["biblioteca"][1]
    if (pagina.evaluate("!!window.QPulso")):          # el pulso del Formulador, con sus mismos textos
        assert "hace 30 min" in e["procesador"][1], e["procesador"]
    assert pagina.locator("#cx-biblioteca .cx-pildora").inner_text().strip() == "Conectada"
    assert pagina.locator("#cx-intercambio .cx-pildora").inner_text().strip() == "Al día"
    assert not errores
    pagina.context.close()


def test_preparar_este_computador(navegador, sitio):
    """Pedido del 2026-10-19: arriba, cada cosa que se conecta, en orden, con su botón; la biblioteca se conecta aquí."""
    pagina, errores = _abrir_portal(navegador, sitio, clave=False)
    _menu(pagina, "Configuración y conexiones")
    e = _estado_cx(pagina)
    assert list(e) == ["navegador", "onedrive", "biblioteca", "contrasena", "usuario", "sistema", "procesador"]
    if not pagina.evaluate("typeof showDirectoryPicker === 'function'"):
        pytest.skip("este Chromium no conecta carpetas")
    botones = lambda s: pagina.locator('#cxEstado li[data-estado="' + s + '"] .cx-est-acc').inner_text()
    assert "Conectar biblioteca" in botones("biblioteca")
    assert "Elegir mi usuario" in botones("usuario") and "Probar QUEMPIN.exe" in botones("sistema")
    assert pagina.locator('#cxEstado li[data-estado="onedrive"] a[href^="https://quempinspa2020.sharepoint.com/"]').count() == 2
    assert pagina.locator("#cxAvanceTxt").inner_text() == "1 de 6 pasos listos"
    # El botón destacado es solo el del paso que toca ahora
    assert pagina.evaluate("[...document.querySelectorAll('#cxEstado .cx-boton')].map(b => b.closest('li').dataset.estado)") == ["onedrive"]
    # Una carpeta que no es la biblioteca: se dice qué elegir y no se guarda nada
    pagina.evaluate("""async () => {
        const raiz = await navigator.storage.getDirectory();
        const otra = await raiz.getDirectoryHandle('Descargas', { create: true });
        window.showDirectoryPicker = async () => otra;
    }""")
    pagina.locator('#cxEstado li[data-estado="biblioteca"] button', has_text="Conectar biblioteca").click()
    pagina.wait_for_function("() => /no es la biblioteca/.test(document.getElementById('aviso').textContent)")
    assert _estado_cx(pagina)["biblioteca"][0] == "bad"
    # La biblioteca completa (con su intercambio y la Planilla): queda donde la guarda el Formulador
    pagina.evaluate(JS_CONECTAR, 30)
    pagina.evaluate("""async () => {
        const raiz = await navigator.storage.getDirectory();
        const bib = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos');
        const inter = await (await bib.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN')).getDirectoryHandle('Intercambio');
        const w = await (await inter.getFileHandle('intercambio.json', { create: true })).createWritable();
        await w.write(JSON.stringify({ esquema: 'quempin.intercambio/1' }));
        await w.close();
        await bib.getFileHandle('Planilla de Ingreso de Requerimientos.xlsx', { create: true });
        await new Promise((ok) => { const r = indexedDB.deleteDatabase('qpn-intercambio'); r.onsuccess = r.onerror = ok; });
        window.showDirectoryPicker = async () => bib;
    }""")
    pagina.locator("#pestanas .ir", has_text="Inicio").click()
    pagina.locator("#pestanas .ir", has_text="Conexiones").click()
    _estado_cx(pagina, {"biblioteca": "bad"})
    pagina.locator('#cxEstado li[data-estado="biblioteca"] button', has_text="Conectar biblioteca").click()
    e = _estado_cx(pagina, {"biblioteca": "ok", "procesador": "ok"})
    assert "Formulación de proyectos - Documentos" in e["biblioteca"][1]
    dentro = pagina.evaluate("""() => [...document.querySelectorAll('#cxEstado li[data-estado="biblioteca"] .cx-est-dentro span')]
        .map((s) => [s.className, s.textContent])""")
    assert dentro == [["si", "Carpeta de intercambio"], ["si", "Planilla de Ingreso"]]
    guardado = pagina.evaluate("""() => new Promise((ok) => { const r = indexedDB.open('qpn-intercambio');
        r.onsuccess = () => { const t = r.result.transaction('carpetas').objectStore('carpetas');
          const a = t.get('intercambio'), b = t.get('biblioteca');
          t.transaction.oncomplete = () => { r.result.close(); ok([a.result.name, b.result.name]); }; }; })""")
    assert guardado == ["Intercambio", "Formulación de proyectos - Documentos"]
    # Con la biblioteca conectada, OneDrive queda a medio camino hasta marcarlo; las marcas se pueden quitar
    assert e["onedrive"][0] == "warn"
    pagina.locator('#cxEstado li[data-estado="onedrive"] button', has_text="Ya están las dos").click()
    _estado_cx(pagina, {"onedrive": "ok"})
    pagina.locator('#cxEstado li[data-estado="usuario"] button', has_text="Elegir mi usuario").click()
    pagina.locator("#listaUsuarios .usr-op").first.click()
    _estado_cx(pagina, {"usuario": "ok"})
    assert pagina.locator("#cxAvanceTxt").inner_text() == "4 de 6 pasos listos"
    pagina.locator('#cxEstado li[data-estado="onedrive"] .cx-desmarcar').click()
    _estado_cx(pagina, {"onedrive": "warn"})
    assert not errores
    pagina.context.close()


def test_conexiones_en_el_telefono(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio, ancho=390, alto=844, movil=True)
    _menu(pagina, "Configuración y conexiones")
    _estado_cx(pagina)
    derecha = pagina.evaluate("""() => Math.max(...[...document.querySelectorAll('#vistaConexiones *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))""")
    assert derecha <= 390.5, derecha
    # Ningún texto bajo 12 px
    chicos = pagina.evaluate("""() => [...document.querySelectorAll('#vistaConexiones *')]
        .filter((e) => e.getClientRects().length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
        .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12).map((e) => e.className || e.tagName)""")
    assert not chicos, chicos
    assert not errores
    pagina.context.close()


def _plantilla_tablero(subruta, compilado):
    """El template de un tablero publicado (el AF de Perú se arma con el de Chile)."""
    t = RAIZ / Path(compilado).parent.parent / "template.html"
    return t if t.exists() else RAIZ / "Sistema Analisis Financiero" / "Visualizador Web" / "template.html"


def test_lo_que_esconde_el_portal_existe_en_cada_herramienta():
    """Los selectores de ESTILO_INCRUSTADO y las claves de tema del registro, contra el código de cada
    herramienta: si una cambia su cabecera, esto avisa en vez de que el portal la muestre repetida."""
    reg = {h["id"]: h for h in _registro()["herramientas"]}
    publicar = _cargar("publicar_para_test_incrustar", VISUALIZADOR / "publicar.py")
    por_ruta = {}
    for h in reg.values():
        for clave in ("ruta", "peru"):
            if h.get(clave):
                por_ruta[h[clave]] = h
    for subruta, compilado in publicar.TABLEROS.values():
        h = por_ruta["/finanzas-quempin/" + subruta + "/"]
        texto = _plantilla_tablero(subruta, compilado).read_text(encoding="utf-8")
        assert h["incrustar"] == "tablero", subruta
        assert '<header class="viz-header">' in texto and 'id="vizGenerated"' in texto, subruta
        assert f"localStorage.getItem('{h['tema']}')" in texto, subruta
    calculadora = _hermano("Calculadora Técnica")
    if calculadora:
        for h in reg.values():
            if h.get("incrustar") == "calculadora":
                carpeta = h["ruta"].removeprefix("/calculadora-tecnica-quempin/").strip("/")
                texto = (calculadora / carpeta / "index.html").read_text(encoding="utf-8")
                assert 'class="viz-header"' in texto and f"'{h['tema']}'" in texto, h["id"]
    formulador = _hermano("Formulación de proyectos")
    raiz_f = formulador / "quempin-formulacion" if formulador else None
    if raiz_f and raiz_f.exists():
        indice = (raiz_f / "index.html").read_text(encoding="utf-8")
        for pieza in ('class="viz-header"', 'class="viz-logo"', 'class="viz-titleblock"', 'id="herrBtn"',
                      'id="themeToggle"', 'class="viz-modnav"', 'data-act="config"', 'id="usuarioBtn"'):
            assert pieza in indice, pieza
        assert f"'{reg['formulador']['tema']}'" in (raiz_f / "js" / "app.js").read_text(encoding="utf-8")


# ---- Usuario (2026-10-16): las iniciales del equipo, elegidas una vez por navegador -------------------

USUARIOS = ["NB", "ES", "LC", "CM", "MP", "SV"]


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


def _proyectos_con_responsable():
    datos = json.loads(json.dumps(PROYECTOS))
    datos["proyectos"][1]["responsable"] = "LC"     # QMPN-2026-001 v2, la versión que manda
    datos["proyectos"][2]["responsable"] = "CM"     # QMPN-2026-002
    return datos


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
    # El selector de proyectos muestra primero los suyos
    pagina.locator("#btnProyecto").click()
    assert pagina.locator("#listaProyectos .pop-grupo").all_text_contents() == ["Tus proyectos (LC)", "Del equipo"]
    titulos = pagina.locator("#listaProyectos li").all_inner_texts()
    assert titulos[1].startswith("QMPN-2026-001") and titulos[3].startswith("QMPN-2026-002"), titulos
    assert "a cargo de CM" in titulos[3]
    pagina.keyboard.press("Escape")
    # El buscador dice cuál es suyo y encuentra por iniciales
    pagina.locator("#buscar").fill("cm")
    assert "a cargo de CM" in pagina.locator("#resultados").inner_text()
    pagina.locator("#buscar").fill("")
    # Sin usuario: se guarda vacío y los proyectos van sin grupos
    boton.click()
    pagina.locator("#sinUsuario").click()
    assert pagina.evaluate("localStorage.getItem('quempin_usuario')") == ""
    assert pagina.locator("#usuarioActual").inner_text() == "¿Quién eres?"
    pagina.locator("#btnProyecto").click()
    assert pagina.locator("#listaProyectos .pop-grupo").count() == 0
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


# ---- La carpeta del proyecto en el Explorador (2026-10-19, QUEMPIN.exe 1.3.10) -------------------------
def _proyectos_con_carpeta():
    datos = json.loads(json.dumps(PROYECTOS))
    datos["proyectos"][1]["vinculos"]["carpetaOferta"] = {
        "nombre": "312. Gimnasio de prueba", "ruta": ["0 OFERTAS PRESENTADAS", "312. Gimnasio de prueba"], "numero": "312"}
    # Adjudicada y copiada a Gestión de Proyectos: el original quedó en Adjudicadas y se abre la copia
    datos["proyectos"][2]["vinculos"] = {"carpetaOferta": {
        "nombre": "250. Obra de prueba", "ruta": ["0 OFERTAS ADJUDICADAS", "250. Obra de prueba"], "numero": "250",
        "gestion": {"copiada": "2026-10-19T12:00:00.000Z"}}}
    datos["proyectos"].append({"uid": "u5", "codigo": "QMPN-2026-009", "version": 1, "titulo": "Ruta mala", "estado": "Borrador",
                               "modificado": "2026-10-01T09:00:00Z", "vinculos": {"carpetaOferta": {"nombre": "x", "ruta": ["..", "x"]}}})
    return datos


def test_la_carpeta_del_proyecto_se_abre_en_el_explorador(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.evaluate("d => localStorage.setItem('qpn.formulacion.proyectos.v1', JSON.stringify(d))", _proyectos_con_carpeta())
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    boton = pagina.locator("#btnCarpeta")
    assert boton.is_hidden()          # sin proyecto elegido
    pagina.locator("#btnProyecto").click()
    pagina.locator("#listaProyectos .pop-item", has_text="Obra de prueba").click()
    assert boton.is_visible()
    assert "312. Gimnasio de prueba" in boton.get_attribute("title")
    boton.click()
    assert pagina.evaluate("window.__lanzados") == ["quempin://carpeta/formulacion/0%20OFERTAS%20PRESENTADAS/312.%20Gimnasio%20de%20prueba"]
    assert "Abriendo «312. Gimnasio de prueba» en el Explorador" in pagina.locator("#aviso").inner_text()
    pagina.locator("#aviso button", has_text="¿No se abrió?").click()
    texto = pagina.locator("#dlgInfo").inner_text()
    assert "1.3.10" in texto and "Formulación de proyectos › 0 OFERTAS PRESENTADAS › 312. Gimnasio de prueba" in texto
    pagina.locator("#dlgInfo button", has_text="Entendido").click()
    # Uno ya copiado a Gestión de Proyectos abre esa copia
    pagina.locator("#btnProyecto").click()
    pagina.locator("#listaProyectos .pop-item", has_text="Mantención de prueba").click()
    boton.click()
    assert pagina.evaluate("window.__lanzados")[-1] == "quempin://carpeta/gestion/250.%20Obra%20de%20prueba"
    # Sin carpeta, o con una ruta que no es de la biblioteca, no hay botón
    pagina.locator("#btnProyecto").click()
    pagina.locator("#listaProyectos .pop-item", has_text="Ruta mala").click()
    assert boton.is_hidden()
    assert not errores
    pagina.context.close()


def test_en_el_telefono_no_hay_boton_de_carpeta(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio, ancho=390, alto=844, movil=True)
    pagina.evaluate("d => { localStorage.setItem('qpn.formulacion.proyectos.v1', JSON.stringify(d)); localStorage.setItem('quempin_portal_proyecto', JSON.stringify('QMPN-2026-001')); }", _proyectos_con_carpeta())
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    assert pagina.locator("#btnCarpeta").is_hidden()
    d = pagina.evaluate(JS_DESBORDES)
    assert d["doc"] <= 390 and not d["fuera"], d
    assert not errores
    pagina.context.close()


def test_sistema_quempin_atiende_las_carpetas_que_pide_el_portal():
    """quempin://carpeta/<formulacion|gestion>/… es lo que lee app/carpetas.py de Sistema QUEMPIN."""
    sistema = _hermano("Sistema QUEMPIN")
    carpetas = sistema / "app" / "carpetas.py" if sistema else None
    if not carpetas or not carpetas.exists():
        pytest.skip("Sistema QUEMPIN no está en este equipo")
    fuente = carpetas.read_text(encoding="utf-8")
    assert 'ACCIONES = ("carpeta", "trasladar")' in fuente
    assert '"formulacion": ubicacion.BIBLIOTECA_FORMULACION' in fuente and '"gestion": ubicacion.BIBLIOTECA_GESTION' in fuente
    portal = PORTAL.read_text(encoding="utf-8")
    assert "'quempin://carpeta/' + c.biblioteca + '/'" in portal
