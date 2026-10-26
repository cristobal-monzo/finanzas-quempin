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
            assert h["incrustar"] in {"tablero", "calculadora", "formulador", "gantt"} and h["tipo"] == "marco", h["id"]
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
    for pieza in ("id: 'seguimiento'", "id: 'ficha'", "parts[0] === 'req'", "parts[0] === 'tag'"):
        assert pieza in texto, pieza
    # La Carta Gantt, herramienta aparte desde el 2026-10-20: su página abre la carta de un proyecto con
    # #/proyecto/<uid>, y el Formulador manda ahí los enlaces antiguos #/p/<uid>/gantt
    gantt = app.parent.parent / "gantt"
    assert "parts[0] === 'proyecto'" in (gantt / "app.js").read_text(encoding="utf-8")
    assert "gantt/#/proyecto/" in texto
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

CABECERA_GANTT = """<div class="viz-root"><header class="viz-header"><div class="viz-container">
  <a class="viz-logo" href="#/"><span class="viz-wordmark">QUEMPIN</span></a>
  <div class="viz-titleblock"><h1>Carta Gantt</h1></div>
  <button class="viz-theme-toggle hb" id="themeToggle">Modo oscuro</button></div></header></div>"""

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
    pagina("/formulacion-proyectos-quempin/gantt/", "Carta Gantt", "gantt", CABECERA_GANTT)
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
    # Lo que se abre fuera del portal (Excel, Sistema QUEMPIN) lleva la flecha ↗; las vistas del portal, no
    fuera = [h["id"] for h in reg["herramientas"] if h["id"] in esperadas and h["tipo"] not in ("marco", "vista")]
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
    # La Carta Gantt es una herramienta aparte (2026-10-20): sin proyecto abre su lista, sin pedir uno
    _menu(pagina, "Carta Gantt")
    assert not pagina.locator("#popProyecto").is_visible()
    _marco(pagina, "gantt", "gantt")
    _esperar(pagina, "gantt", "hash", "#/")
    # Con un proyecto elegido, abre su carta en su propia pestaña, aparte del Formulador
    pagina.locator("#btnProyecto").click()
    assert pagina.locator("#listaProyectos .pop-item .t").all_inner_texts() == ["QMPN-2026-001 · Obra de prueba",
                                                                                "QMPN-2026-002 · Mantención de prueba"]
    pagina.locator("#listaProyectos .pop-item", has_text="QMPN-2026-001").click()
    assert "QMPN-2026-001" in pagina.locator("#proyectoActual").inner_text()
    _esperar(pagina, "gantt", "hash", "#/proyecto/u2")
    assert pagina.evaluate("document.getElementById('marco-gantt').contentDocument.documentElement.dataset.enPortal") == "gantt"
    _menu(pagina, "Formulador")
    formulador = _marco(pagina, "formulador", "formulador")
    _esperar(pagina, "formulador", "hash", "#/req/7")
    assert _pestanas(pagina) == ["Inicio", "Carta Gantt · QMPN-2026-001", "Formulador · QMPN-2026-001"]
    pagina.locator("#pestanas .x").first.click()
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
    for juntas in ("Formulador y Seguimiento", "Centro de Costos y Análisis Financiero",
                   "Emitir cotización y Orden de compra"):
        assert juntas in por_nombre, juntas
    assert filas[-1] == ["Calculadora (todas)", []]
    assert {"Biblioteca Formulación", "Carpeta de intercambio", "Contraseña"} <= set(por_nombre["Formulador y Seguimiento"])
    # La Carta Gantt, herramienta aparte (2026-10-20): la carpeta del equipo para compartir sus cartas
    assert set(por_nombre["Carta Gantt"]) == {"Biblioteca Formulación", "Carpeta de intercambio", "Contraseña"}
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
        # La Carta Gantt (2026-10-20): pierde toda su cabecera; su tema, en su página y en su interfaz
        g = raiz_f / "gantt"
        assert reg["gantt"]["incrustar"] == "gantt" and 'class="viz-header"' in (g / "index.html").read_text(encoding="utf-8")
        assert f"'{reg['gantt']['tema']}'" in (g / "index.html").read_text(encoding="utf-8")
        assert f"'{reg['gantt']['tema']}'" in (g / "app.js").read_text(encoding="utf-8")


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


# ---- Recorrido de proyectos (2026-10-20) -----------------------------------------------------------------
# Todos los proyectos del equipo en las seis etapas, armado con lo que publica la carpeta de intercambio.

def test_el_recorrido_tiene_las_etapas_del_formulador():
    """Las seis etapas del tablero son las del Seguimiento del Formulador (js/flujo.js), en el mismo orden."""
    portal = PORTAL.read_text(encoding="utf-8")
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


def _dia(dias, hora=None):
    from datetime import date, timedelta
    d = (date.today() + timedelta(days=dias)).isoformat()
    return d + "T" + hora if hora else d


def _sobre(herramienta, datos):
    return {"esquema": "quempin.intercambio/1", "herramienta": herramienta, "generado": _dia(0, "09:00:00-03:00"), "datos": datos}


def _formulacion(uid, codigo, req, estado, responsable, precio=0, errores=0, eliminado=False, titulo=""):
    return {"esquema": "quempin.intercambio/1", "herramienta": "formulador", "tipo": "proyecto",
            "resumen": {"precioNeto": precio, "errores": errores, "alertas": 0},
            "datos": {"uid": uid, "codigo": codigo, "version": 1, "titulo": titulo, "estado": estado, "responsable": responsable,
                      "modificado": _dia(-1, "10:00:00Z"), "eliminado": eliminado,
                      "vinculos": {"requerimiento": {"numero": req}} if req else {}}}


def _intercambio_de_prueba():
    """Lo que publicaría la carpeta de intercambio, con un proyecto en cada situación del recorrido. Datos de mentira,
    con fechas relativas a hoy."""
    reqs = [
        {"numero": 900, "estado": "Evaluación", "evaluador": "LC", "captador": "NB", "titulo": "LICEO", "ubicacion": "Valparaíso",
         "cierre": _dia(2, "15:00"), "visita": _dia(1)},
        {"numero": 901, "estado": "Evaluación", "evaluador": "CM", "titulo": "MANTENCIÓN DE CALDERAS DEL CESFAM Y GLP", "cierre": _dia(20)},
        {"numero": 902, "estado": "Evaluación", "evaluador": "CM", "titulo": "Formulación lista", "cierre": _dia(10)},
        {"numero": 903, "estado": "Evaluación", "evaluador": "LC", "titulo": "Borrador en Sistema QUEMPIN", "cierre": _dia(5)},
        {"numero": 904, "estado": "Evaluación", "evaluador": "LC", "titulo": "Cotización emitida", "cierre": _dia(1)},
        {"numero": 905, "estado": "Ofertado", "evaluador": "NB", "titulo": "Oferta esperando", "cierre": _dia(-5)},
        {"numero": 906, "estado": "Ofertado", "evaluador": "LC", "titulo": "Oferta ganada", "cierre": _dia(-20)},
        {"numero": 907, "estado": "Adjudicado", "evaluador": "NB", "titulo": "Adjudicada sin ficha", "cierre": _dia(-10)},
        {"numero": 908, "estado": "Adjudicado", "evaluador": "LC", "titulo": "En obra", "cierre": _dia(-40)},
        {"numero": 909, "estado": "Adjudicado", "evaluador": "NB", "titulo": "Terminada", "cierre": _dia(-90)},
        {"numero": 910, "estado": "Adjudicado", "evaluador": "JB", "titulo": "Adjudicada hace mucho", "cierre": _dia(-200)},
        {"numero": 911, "estado": "Descartado", "evaluador": "LC", "titulo": "Descartada", "cierre": _dia(3)},
        {"numero": 912, "estado": "Evaluación", "evaluador": "NB", "titulo": "Cerró sin oferta", "cierre": _dia(-3)},
        {"numero": 913, "estado": "Ofertado", "evaluador": "NB", "titulo": "Perdida en el Formulador", "cierre": _dia(-15)},
    ]
    cruce = [
        {"req": "900", "tag": None, "formulaciones": [], "cotizaciones": [], "ordenes": [], "carpetas": {"oferta": ["900. Liceo de prueba"]}},
        {"req": "904", "tag": None, "formulaciones": [], "cotizaciones": [{"folio": "6020001", "fecha": _dia(-1)}], "ordenes": [], "carpetas": {}},
        {"req": "908", "tag": "DEMO", "formulaciones": [], "cotizaciones": [], "ordenes": [],
         "carpetas": {"oferta": ["0 OFERTAS ADJUDICADAS/908. En obra"], "ejecucion": ["908. En obra"]}},
    ]
    af = [
        {"tag": "DEMO", "nombre": "Obra demo", "avance": 0.4, "req": "908", "cierre": _dia(30), "venta": {"cargada": True}},
        {"tag": "FIN", "nombre": "Obra terminada", "avance": 1, "req": "909", "cierre": _dia(-10), "venta": {"cargada": True}},
        {"tag": "SOLO", "nombre": "Obra sin número", "avance": 0.5, "req": None, "cierre": _dia(60), "venta": {"cargada": True}},
    ]
    lic = [
        {"req": 905, "codigo": "1-1-LE26", "resultado": "en-evaluacion", "estado": "Cerrada",
         "url": "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=1-1-LE26"},
        {"req": 906, "codigo": "1-2-LE26", "resultado": "ganada", "estado": "Adjudicada",
         "url": "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=1-2-LE26"},
    ]
    sobre_msg = {"esquema": "quempin.intercambio/1", "id": "b903", "tipo": "borrador-cotizacion", "destino": "sistema-quempin",
                 "origen": {"herramienta": "formulador", "enviado": _dia(-1, "10:00")}, "proyecto": {"req": "903"}, "fuente": {"uid": "f903"}}
    return {
        "publicado/requerimientos.json": _sobre("procesador", {"requerimientos": reqs}),
        "publicado/proyectos.json": _sobre("procesador", {"proyectos": cruce, "sinVincular": {}}),
        "publicado/analisis-financiero.json": _sobre("analisis-financiero", {"proyectos": af}),
        "publicado/licitaciones.json": _sobre("procesador", {"licitaciones": lic}),
        "publicado/formulador/f901.json": _formulacion("f901", "QMPN-2026-901", 901, "Borrador", "CM"),
        "publicado/formulador/f902.json": _formulacion("f902", "QMPN-2026-902", 902, "En revisión", "CM", precio=1000),
        "publicado/formulador/f913.json": _formulacion("f913", "QMPN-2026-913", 913, "Perdida", "NB", precio=500),
        "publicado/formulador/fz.json": _formulacion("fz", "QMPN-2026-777", None, "Borrador", "LC"),
        "publicado/formulador/fx.json": _formulacion("fx", "QMPN-2026-778", None, "Borrador", "LC", eliminado=True),
        "buzon/b903.json": sobre_msg,
        "buzon/otro.json": {"tipo": "datos-proyecto", "destino": "analisis-financiero"},
    }


JS_ESCRIBIR_INTERCAMBIO = """async (archivos) => {
    const raiz = await navigator.storage.getDirectory();
    const bib = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos', { create: true });
    const inter = await (await bib.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN', { create: true })).getDirectoryHandle('Intercambio', { create: true });
    for (const [ruta, contenido] of Object.entries(archivos)) {
        const partes = ruta.split('/');
        let d = inter;
        for (const p of partes.slice(0, -1)) d = await d.getDirectoryHandle(p, { create: true });
        const w = await (await d.getFileHandle(partes[partes.length - 1], { create: true })).createWritable();
        await w.write(JSON.stringify(contenido));
        await w.close();
    }
}"""

JS_COLUMNAS = """() => Object.fromEntries([...document.querySelectorAll('#rcTablero .rc-col')].map((c) => [c.dataset.etapa,
    [...c.querySelectorAll(':scope > .rc-lista .rc-tarjeta')].map((t) => t.dataset.clave)]))"""


def _portal_con_datos(navegador, sitio, usuario=None, **kw):
    """El portal con la biblioteca conectada (como la deja el Formulador) y la carpeta de prueba, en el Inicio."""
    pagina, errores = _abrir_portal(navegador, sitio, **kw)
    if not pagina.evaluate("typeof showDirectoryPicker === 'function'"):
        pagina.context.close()
        pytest.skip("este Chromium no conecta carpetas")
    pagina.evaluate(JS_CONECTAR, 30)
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, _intercambio_de_prueba())
    if usuario:
        pagina.evaluate("u => localStorage.setItem('quempin_usuario', u)", usuario)
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    return pagina, errores


def _recorrido_con_datos(navegador, sitio, usuario=None, **kw):
    """Lo mismo, ya en el Recorrido."""
    pagina, errores = _portal_con_datos(navegador, sitio, usuario, **kw)
    _menu(pagina, "Recorrido de proyectos")
    pagina.locator("#rcTablero .rc-tarjeta").first.wait_for()
    return pagina, errores


def _cifras(pagina):
    return dict(zip(pagina.locator("#rcResumen .rc-kpi").evaluate_all("bs => bs.map((b) => b.dataset.foco)"),
                    [int(x) for x in pagina.locator("#rcResumen .rc-kpi-n").all_inner_texts()]))


def test_el_recorrido_sin_biblioteca_dice_que_conectar(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.locator("#iniRecorrido").click()
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
    assert accion("req-912") == "Actualizar la Planilla"
    assert accion("req-901") == "Seguir formulando"
    assert accion("req-902") == "Preparar la cotización"
    assert accion("req-903") == "Emitir en Sistema QUEMPIN"
    assert accion("req-904") == "Marcar como Enviada"
    assert accion("req-905") == "Esperando respuesta"
    assert accion("req-906") == "Marcar como Adjudicada"
    assert accion("req-913") == "Avisar a la Planilla"
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
    # La herramienta de cada etapa, desde su columna
    pagina.locator('.rc-col[data-etapa="ejecucion"] .rc-donde').click()
    _marco(pagina, "analisis", "af")
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
    # El Inicio dice lo que te espera, y lleva al recorrido
    pagina.locator("#pestanas .ir").first.click()
    assert pagina.locator("#iniRcTit span").inner_text() == "Te esperan 5 proyectos"
    pagina.locator("#iniRcVer").click()
    assert pagina.locator("#vistaRecorrido").is_visible()
    assert not errores
    pagina.context.close()


def _inicio_tarjetas(pagina):
    return pagina.locator("#iniRcLista .rc-tarjeta").evaluate_all("ts => ts.map((t) => t.dataset.clave)")


def test_el_inicio_muestra_lo_que_te_espera(navegador, sitio):
    """Pedido del 2026-10-20: debajo de las herramientas, una vista previa del recorrido enfocada en el usuario
    elegido; si no tiene pendientes, un acceso directo al recorrido."""
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC")
    previa = pagina.locator("#iniRc")
    previa.locator(".rc-tarjeta").first.wait_for()
    assert pagina.locator("#iniRecorrido").is_hidden()
    # Debajo de las herramientas, antes de la línea de ayuda
    assert pagina.evaluate("[...document.querySelector('.inicio').children].map((e) => e.id || e.className)") == [
        "tituloInicio", "iniGrupos", "iniRc", "iniRecorrido", "ini-pie"]
    assert pagina.locator("#iniRcTit span").inner_text() == "Te esperan 5 proyectos" and pagina.locator("#iniRcTit b").inner_text() == "LC"
    assert pagina.locator("#iniRcSub").inner_text() == "De tus proyectos, 2 cierran esta semana · 1 en ejecución"
    # Lo urgente primero (rojo, después ámbar) y, entre iguales, en el orden del recorrido; con más de cuatro, «+N más»
    assert _inicio_tarjetas(pagina) == ["req-900", "req-904", "f-fz"]
    etapa = lambda c: pagina.locator(f'#iniRc .rc-tarjeta[data-clave="{c}"] .rc-etapa').inner_text()
    assert [etapa(c) for c in ("req-900", "req-904", "f-fz")] == ["Requerimiento", "Oferta", "Requerimiento"]
    assert pagina.locator('#iniRc .rc-tarjeta[data-clave="req-904"] .rc-segs .aqui').count() == 1
    assert pagina.locator('#iniRc .rc-tarjeta[data-clave="req-904"] .rc-segs .hecha').count() == 3
    mas = pagina.locator("#iniRcLista .ini-rc-mas")
    assert mas.inner_text().split("\n") == ["+2", "Ver los 5 que te esperan"]
    # Cada tarjeta abre su detalle y su botón la herramienta donde se hace
    pagina.locator('#iniRc .rc-tarjeta[data-clave="req-904"] .rc-abrir').click()
    assert pagina.locator("#dlgRcTit").inner_text() == "N° 904 · Cotización emitida"
    pagina.keyboard.press("Escape")
    pagina.locator('#iniRc .rc-tarjeta[data-clave="req-900"] .rc-accion').click()
    _esperar(pagina, "formulador", "hash", "#/req/900")
    # «+2 más» abre el recorrido con solo lo que te espera; «Ver el recorrido», el tablero completo
    pagina.locator("#pestanas .ir").first.click()
    mas.click()
    assert pagina.locator("#vistaRecorrido").is_visible() and pagina.locator("#rcFoco").inner_text().strip() == "Mostrando: Te esperan"
    assert sorted(sum(pagina.evaluate(JS_COLUMNAS).values(), [])) == ["f-fz", "req-900", "req-903", "req-904", "req-906"]
    pagina.locator("#pestanas .ir").first.click()
    pagina.locator("#iniRcVer").click()
    assert pagina.locator("#rcFoco").is_hidden() and len(sum(pagina.evaluate(JS_COLUMNAS).values(), [])) == 14
    pagina.locator("#pestanas .ir").first.click()
    # Otro usuario, elegido arriba: la vista previa cambia sin recargar
    elegir = lambda u: (pagina.locator("#btnUsuario").click(), pagina.locator(f'#listaUsuarios .usr-op[data-usuario="{u}"]').click())
    elegir("CM")
    assert _inicio_tarjetas(pagina) == ["req-901", "req-902"] and pagina.locator("#iniRcLista .ini-rc-mas").count() == 0
    assert pagina.locator("#iniRcTit span").inner_text() == "Te esperan 2 proyectos"
    assert pagina.locator("#iniRcSub").inner_text() == "Lo más urgente primero, con el botón para hacerlo"
    # Nada pendiente: queda el acceso directo, que dice cómo va el equipo
    elegir("ES")
    assert previa.is_hidden() and pagina.locator("#iniRecorrido").is_visible()
    assert pagina.locator("#iniRecorridoSub").inner_text() == (
        "Nada te espera por ahora. En el equipo, 2 cierran esta semana · 1 espera respuesta · 3 en ejecución")
    pagina.locator("#btnUsuario").click()
    pagina.locator("#sinUsuario").click()
    assert previa.is_hidden() and pagina.locator("#iniRecorridoSub").inner_text() == (
        "Elige tu usuario para ver aquí lo que te espera. En el equipo, 10 requieren acción · 2 cierran esta semana"
        " · 1 espera respuesta · 3 en ejecución")
    pagina.locator("#iniRecorrido").click()
    assert pagina.locator("#vistaRecorrido").is_visible()
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho, alto", [(1366, 657), (1536, 730), (1024, 768), (390, 844)])
def test_lo_que_te_espera_cabe_en_el_inicio(navegador, sitio, ancho, alto):
    """Con la vista previa el Inicio sigue sin barras en el escritorio, y en el teléfono no se sale por el lado."""
    movil = ancho < 760
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC", ancho=ancho, alto=alto, movil=movil)
    pagina.locator("#iniRc .rc-tarjeta").first.wait_for()
    if not movil:
        assert pagina.evaluate(JS_BARRAS) == []
    d = pagina.evaluate(JS_DESBORDES)
    assert d["doc"] <= ancho and not d["fuera"], d
    derecha = pagina.evaluate("""() => Math.max(...[...document.querySelectorAll('#iniRc *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))""")
    assert derecha <= ancho + 0.5, derecha
    chicos = pagina.evaluate("""() => [...document.querySelectorAll('#iniRc *')]
        .filter((e) => e.getClientRects().length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
        .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12).map((e) => e.className || e.tagName)""")
    assert not chicos, chicos
    columnas = "getComputedStyle(document.getElementById('iniRcLista')).gridTemplateColumns.split(' ').length"
    assert pagina.evaluate(columnas) == (1 if movil else 4)
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


# ---- Planificación semanal (2026-10-20) -------------------------------------------------------------

DISPOSITIVO = "pruebaportal01"          # el nombre del archivo que escribe el navegador de las pruebas
# Los proyectos activos de _intercambio_de_prueba (la etapa Ejecución del Recorrido, sin los de hace más de 60
# días), por nombre: 907 adjudicado sin ficha, 908 con ficha DEMO al 40 % y SOLO, una ficha sin N°.
ACTIVOS = {"req:907": "Adjudicada sin ficha", "req:908": "En obra", "tag:SOLO": "Obra sin número"}

JS_LEER_INTERCAMBIO = """async (ruta) => {
    const raiz = await navigator.storage.getDirectory();
    let d = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos');
    d = await (await d.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN')).getDirectoryHandle('Intercambio');
    const partes = ruta.split('/');
    try {
        for (const p of partes.slice(0, -1)) d = await d.getDirectoryHandle(p);
        return JSON.parse(await (await (await d.getFileHandle(partes[partes.length - 1])).getFile()).text());
    } catch (e) { return null; }
}"""

JS_ESCRIBIR_TEXTO = """async ([ruta, texto]) => {
    const raiz = await navigator.storage.getDirectory();
    let d = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos');
    d = await (await d.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN')).getDirectoryHandle('Intercambio');
    const partes = ruta.split('/');
    for (const p of partes.slice(0, -1)) d = await d.getDirectoryHandle(p, { create: true });
    const w = await (await d.getFileHandle(partes[partes.length - 1], { create: true })).createWritable();
    await w.write(texto);
    await w.close();
}"""

# Lo que muestra «Por personal»: por persona, cada día con sus proyectos (o su ausencia)
JS_PERSONAL = """() => Object.fromEntries([...document.querySelectorAll('#plPersonal tr[data-persona]')].map((tr) => [tr.dataset.persona,
    [...tr.querySelectorAll('td[data-dia]')].map((td) => [...td.querySelectorAll('.pl-chip .t, .pl-aus')].map((e) => e.textContent))]))"""


def _semana_de(d):
    from datetime import timedelta
    lunes = d - timedelta(days=d.weekday())
    anio, numero, _ = lunes.isocalendar()
    return f"{anio}-W{numero:02d}", lunes


def _instante(segundos):
    from datetime import datetime, timedelta, timezone
    t = datetime.now(timezone.utc) + timedelta(seconds=segundos)
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _sobre_plan(semana, lunes, dispositivo, asignaciones=(), ausencias=(), pausas=(), proyectos=None):
    return {"esquema": "quempin.intercambio/1", "herramienta": "planificacion", "tipo": "planificacion-semana",
            "generado": _instante(0), "autor": "NB",
            "datos": {"semana": semana, "desde": lunes.isoformat(), "dispositivo": dispositivo, "asignaciones": list(asignaciones),
                      "ausencias": list(ausencias), "pausas": list(pausas), "proyectos": proyectos or {}}}


def _plan_con_datos(navegador, sitio, usuario=None, vista=None, **kw):
    """El portal con la carpeta de prueba, en la Planificación semanal. Este navegador escribe «pruebaportal01.json»."""
    pagina, errores = _portal_con_datos(navegador, sitio, usuario, **kw)
    pagina.evaluate("""([d, v]) => {
        localStorage.setItem('quempin_portal_dispositivo', d);
        if (v) localStorage.setItem('quempin_portal_plan', JSON.stringify({ vista: v }));
    }""", [DISPOSITIVO, vista])
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Planificación semanal")
    pagina.locator("#plResumen .rc-kpi").first.wait_for()
    return pagina, errores


def _esperar_archivo(pagina, ruta, hasta=lambda sobre: True):
    """El archivo de la carpeta de prueba, cuando ya cumple lo esperado (se guarda medio segundo después del cambio)."""
    import time
    fin = time.time() + 10
    while True:
        sobre = pagina.evaluate(JS_LEER_INTERCAMBIO, ruta)
        if sobre and hasta(sobre):
            return sobre
        assert time.time() < fin, f"{ruta}: {sobre}"
        pagina.wait_for_timeout(150)


def _celda_personal(pagina, persona, dia):
    return pagina.locator(f'#plPersonal tr[data-persona="{persona}"] td[data-dia="{dia}"] .pl-celda')


def _celda_proyecto(pagina, clave, dia):
    return pagina.locator(f'#plProyecto tr[data-clave="{clave}"] td[data-dia="{dia}"] .pl-celda')


def test_la_planificacion_semanal_en_el_registro():
    """Pedido del 2026-10-20: planificar la semana con el personal NB, ES, LC, CM, MP, SV y EV, como máximo 3 proyectos
    por persona en un día. Lee y guarda en la carpeta del equipo, y Configuración y conexiones lo dice."""
    reg = _registro()
    h = {x["id"]: x for x in reg["herramientas"]}["planificacion"]
    assert h["tipo"] == "vista" and h["vista"] == "vistaPlan" and h["grupo"] == "finanzas"
    assert reg["personal"] == ["NB", "ES", "LC", "CM", "MP", "SV", "EV"]
    assert set(reg["usuarios"]) <= set(reg["personal"]), "quien usa las herramientas también se planifica"
    usan = {e["id"]: e["usan"] for e in _conexiones()["elementos"]}
    assert "planificacion" in usan["biblioteca"] and "planificacion" in usan["intercambio"]
    portal = PORTAL.read_text(encoding="utf-8")
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
    """Pedido del 2026-10-20: si un proyecto activo no se asigna en la semana actual, una alarma. Se ve en la cabecera
    (desde cualquier herramienta), en el menú y en el Inicio, y la vista dice cuáles son."""
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC")
    alerta = pagina.locator("#plAlertaCab")
    alerta.wait_for()
    assert " ".join(alerta.inner_text().split()) == "3 sin asignar"
    assert all(t in alerta.get_attribute("title") for t in ACTIVOS.values())
    item = pagina.locator('.ini-item[data-herr="planificacion"]')
    assert item.locator(".pl-alerta-n").inner_text() == "3"
    assert item.locator(".ini-sub").inner_text() == "3 proyectos sin asignar esta semana"
    assert item.locator(".ini-fuera").count() == 0, "se abre dentro del portal"
    pagina.locator("#btnMenu").click()
    pagina.locator("#grupo-finanzas").click()
    assert pagina.locator('#menu .menu-item[data-herr="planificacion"] .pl-alerta-n').inner_text() == "3"
    pagina.keyboard.press("Escape")
    alerta.click()
    pagina.locator("#plAlarma").wait_for()
    assert _pestanas(pagina) == ["Inicio", "Planificación"]
    assert pagina.locator("#plAlarma").get_attribute("data-nivel") == "bad"
    assert pagina.locator("#plAlarma .pl-alarma-tit").inner_text() == "3 proyectos activos sin nadie asignado esta semana"
    assert pagina.locator("#plAlarma .pl-alarma-p").all_inner_texts() == list(ACTIVOS.values())
    assert [int(x) for x in pagina.locator("#plResumen .rc-kpi-n").all_inner_texts()][:2] == [3, 3]
    assert pagina.locator("#plSemanaRango").inner_text().startswith("Esta semana · ") and pagina.locator("#plHoy").is_disabled()
    # Cada proyecto de la alarma lleva a su fila en «Por proyecto», donde los sin asignar van primero
    pagina.locator("#plAlarma .pl-alarma-p", has_text="En obra").click()
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
    assert list(pagina.evaluate(JS_PERSONAL)) == ["NB", "ES", "LC", "CM", "MP", "SV", "EV"]
    assert pagina.locator("#plPersonal tr.tuya").get_attribute("data-persona") == "LC"
    _celda_personal(pagina, "LC", 0).click()
    pop = pagina.locator("#plPop")
    assert pop.is_visible() and pagina.locator("#plPopTit").inner_text().startswith("LC · Lunes ")
    assert pagina.locator("#plPopSub").inner_text() == "0 de 3 proyectos este día"
    pop.locator('input[data-op="c|req:908"]').check()
    assert pagina.evaluate(JS_PERSONAL)["LC"][0] == ["En obra"]
    assert "LC va a En obra el lunes" in pagina.locator("#aviso").inner_text()
    assert pagina.locator("#plAlertaN").inner_text() == "2"
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
    pagina.wait_for_function("document.getElementById('plFrescura').textContent === 'Guardado en la carpeta del equipo'")
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
    pagina.locator("#plAlarma .pl-alarma-p").first.click()
    titulos = [pagina.locator("#plPopTit").inner_text()]
    for _ in range(2):
        pagina.locator("#plPopSiguiente").click()
        titulos.append(pagina.locator("#plPopTit").inner_text())
    assert len(set(titulos)) == 3, titulos
    pagina.keyboard.press("Escape")
    pagina.locator('.pl-vista[data-vista="personal"]').click()
    # El sábado: al quitarle lo último su columna se esconde, pero la ventanita sigue en el sábado (no salta al lunes)
    pagina.locator("#plSabado").check()
    _celda_personal(pagina, "ES", 5).click()
    pop.locator('input[data-op="c|req:908"]').check()
    pagina.keyboard.press("Escape")
    pagina.locator("#plSabado").click()          # ya no se pide, pero queda a la vista porque tiene algo
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
    pagina.locator("#plImprimir").click()
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
    pagina.locator("#plAlarma .pl-alarma-p", has_text=nombres[0]).click()
    assert pagina.locator('.pl-vista[data-vista="proyecto"]').get_attribute("aria-pressed") == "true"
    assert pop.is_visible() and pagina.locator("#plPopTit").inner_text() == nombres[0]
    assert sig.inner_text() == f"Siguiente sin nadie: {nombres[1]} ›"
    pop.locator('input[data-op="c|LC"]').check()
    assert pagina.locator("#plAlertaN").inner_text() == "2"
    sig.click()
    assert pagina.locator("#plPopTit").inner_text() == nombres[1]
    # Si esa semana no se trabaja en él, se marca desde la misma ventanita
    pop.locator('[data-op="pausa"]').click()
    assert pagina.locator("#plAlertaN").inner_text() == "1"
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


def test_sin_trabajo_esta_semana_no_cuenta_como_alarma(navegador, sitio):
    pagina, errores = _plan_con_datos(navegador, sitio, vista="proyecto")
    fila = pagina.locator('#plProyecto tr[data-clave="tag:SOLO"]')
    fila.locator(".pl-pausar").click()
    assert pagina.locator("#plAlertaN").inner_text() == "2"
    assert "pausa" in fila.get_attribute("class") and fila.locator(".rc-chip").inner_text() == "Sin trabajo esta semana"
    assert "Obra sin número" not in pagina.locator("#plAlarma").inner_text()
    assert pagina.locator("#plResumen .rc-kpi").nth(1).locator(".rc-kpi-sub").inner_text() == "Y 1 sin trabajo esta semana"
    # Los que no se trabajan van al final
    assert pagina.locator("#plProyecto tr[data-clave]").evaluate_all("ts => ts.map((t) => t.dataset.clave)")[-1] == "tag:SOLO"
    fila.locator(".pl-pausar", has_text="Volver a planificar").click()
    assert pagina.locator("#plAlertaN").inner_text() == "3"
    # Asignarle a alguien también lo saca de la pausa
    fila.locator(".pl-pausar").click()
    _celda_proyecto(pagina, "tag:SOLO", 3).click()
    pagina.locator('#plPop input[data-op="c|MP"]').check()
    assert "Ya no está «sin trabajo esta semana»" in pagina.locator("#aviso").inner_text()
    assert "pausa" not in (fila.get_attribute("class") or "") and pagina.locator("#plAlertaN").inner_text() == "2"
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
    pagina.locator("#plCopiar").click()
    pagina.wait_for_function("document.getElementById('aviso').textContent.startsWith('Se copió')")
    assert pagina.locator("#aviso").inner_text().startswith(f"Se copió 1 asignación de la semana {anterior}.")
    assert pagina.evaluate(JS_PERSONAL)["LC"][3] == ["En obra"]
    # Compartir (2026-10-23): por persona, lo de cada uno día por día; también por día, como antes
    jueves = (lunes + timedelta(days=3)).day
    pagina.locator("#plCompartir").click()
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
    pagina.locator("#plCompartir").click()
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
    pagina.locator("#plImprimir").click()
    dlg = pagina.locator("#dlgPlExportar")
    assert dlg.is_visible()
    assert dlg.locator("#plExpPers input:checked").evaluate_all("xs => xs.map((x) => x.value)") == ["LC"]
    assert dlg.locator("#plExpCuenta").inner_text() == "Sale la tabla de la semana y 1 hoja de persona."
    dlg.locator("#plExpImprimir").click()
    assert pagina.evaluate("window.__impreso") is True and dlg.is_hidden()
    assert pagina.evaluate("window.__titulo").startswith(f"Planificación semana {numero} (")
    assert pagina.evaluate("window.__hojas") == ["pl-doc-tabla:Quién va a qué proyecto", "pl-doc-hoja:LC"]
    tabla = pagina.evaluate("window.__tabla")
    assert [f[0] for f in tabla] == ["NB", "ES", "LC", "CM", "MP", "SV", "EV"]
    assert tabla[2][4].startswith("En obra") and tabla[2][1] == "Sin proyecto"
    hoja = pagina.evaluate("window.__hoja")
    assert "En obra" in hoja and "Nadie más" in hoja and "Sin proyecto asignado" in hoja and "tú" not in hoja
    # Al terminar, el documento se vacía y la página vuelve a su título
    assert pagina.evaluate("document.body.classList.contains('pl-imprimiendo')") is False
    assert pagina.evaluate("document.getElementById('plDoc').childElementCount") == 0
    assert not pagina.evaluate("document.title").startswith("Planificación semana")
    # Sin nada elegido no se imprime
    pagina.locator("#plImprimir").click()
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
        pagina.locator("#plGeneral .pl-nuevo" if vista == "general" else f"#pl{vista.capitalize()} .pl-celda >> visible=true").first.click()
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


# ---- Subir documentos al Centro de Costos (2026-10-23) ----------------------------------------------------------

JS_LEER_BUZON = """async () => {
    const raiz = await navigator.storage.getDirectory();
    const bib = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos');
    const buzon = await (await (await bib.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN')).getDirectoryHandle('Intercambio')).getDirectoryHandle('buzon');
    const salida = { mensajes: {}, adjuntos: {} };
    for await (const [n, h] of buzon.entries()) {
        if (h.kind === 'file' && n.includes('_documento-cc_')) salida.mensajes[n] = await (await h.getFile()).text();
    }
    const adj = await buzon.getDirectoryHandle('adjuntos');
    for await (const [id, d] of adj.entries()) {
        for await (const [n, h] of d.entries()) salida.adjuntos[id + '/' + n] = Array.from(new Uint8Array(await (await h.getFile()).arrayBuffer()));
    }
    return salida;
}"""


def _subir_con_datos(navegador, sitio, **kw):
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC", **kw)
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {"publicado/centro-costos-carpetas.json": _sobre("procesador", {"paises": {
        "CL": [{"nombre": "280. Obra de ejemplo", "req": "280", "documentos": 12}, {"nombre": "Gastos Generales", "req": None, "documentos": 3}],
        "PE": [{"nombre": "Obra Lima", "req": None, "documentos": 0}]}})})
    _menu(pagina, "Subir documentos")
    pagina.locator("#scLista .sc-op").first.wait_for()
    return pagina, errores


def test_subir_documentos_llega_a_la_carpeta_del_centro_de_costos(navegador, sitio, tmp_path):
    import hashlib
    import subprocess
    import sys

    pagina, errores = _subir_con_datos(navegador, sitio)
    opciones = pagina.locator("#scLista .sc-op").all_inner_texts()
    assert any("280. Obra de ejemplo" in o and "12 documentos" in o for o in opciones)
    # Un proyecto en ejecución sin carpeta se ofrece como carpeta nueva
    assert any(o.startswith("908. En obra") and "carpeta nueva" in o for o in opciones), opciones
    assert pagina.locator("#scEnviar").is_disabled()
    pagina.locator("#scBuscar").fill("obra ejemplo")
    pagina.keyboard.press("Enter")
    assert pagina.locator("#scElegidoNom").inner_text() == "280. Obra de ejemplo"
    pdf, foto = b"%PDF-1.4 factura de prueba", b"\xff\xd8\xff foto boleta"
    pagina.locator("#scArchivo").set_input_files([
        {"name": "Factura 12:34.pdf", "mimeType": "application/pdf", "buffer": pdf},
        {"name": "boleta.JPG", "mimeType": "image/jpeg", "buffer": foto},
        {"name": "planilla.xlsx", "mimeType": "application/vnd.ms-excel", "buffer": b"no"},
    ])
    assert pagina.locator("#scArchivos li").count() == 2          # el Excel no se agrega
    assert "planilla.xlsx" in pagina.locator("#aviso").inner_text()
    pagina.locator("#scNota").fill("Compras de la semana")
    assert pagina.locator("#scEnviar").inner_text() == "Subir 2 documentos"
    pagina.locator("#scEnviar").click()
    pagina.locator("#scEnvios .sc-pill", has_text="En camino").wait_for()
    assert pagina.locator("#scArchivos li").count() == 0

    # Lo que quedó en la carpeta de intercambio, tal cual, lo atiende el procesador real
    leido = pagina.evaluate(JS_LEER_BUZON)
    [(nombre, texto)] = leido["mensajes"].items()
    raiz = tmp_path / "Intercambio"
    (raiz / "buzon").mkdir(parents=True)
    (raiz / "buzon" / nombre).write_text(texto, encoding="utf-8")
    for ruta, datos in leido["adjuntos"].items():
        destino = raiz / "buzon" / "adjuntos" / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(bytes(datos))
    msg = json.loads(texto)
    assert msg["origen"]["usuario"] == "LC" and msg["nota"] == "Compras de la semana" and msg["proyecto"] == {"req": "280"}
    assert [a["nombre"] for a in msg["archivos"]] == ["Factura 12-34.pdf", "boleta.JPG"]
    assert msg["archivos"][0]["sha256"] == hashlib.sha256(pdf).hexdigest()
    chile = tmp_path / "Facturas y Boletas" / "Chile"
    (chile / "280. Obra de ejemplo").mkdir(parents=True)
    # En su propio proceso: los módulos del intercambio tienen nombres que chocan con los de otros módulos de Finanzas
    salida = subprocess.run([sys.executable, "-c", "import json, sys, documentos_cc, intercambio; from pathlib import Path; "
                             "intercambio.asegurar_carpeta(Path(sys.argv[1])); "
                             "print(json.dumps(documentos_cc.atender(Path(sys.argv[1]), {'CL': Path(sys.argv[2])})))", str(raiz), str(chile)],
                            cwd=RAIZ / "Sistema Intercambio", capture_output=True, text=True, check=True).stdout
    assert json.loads(salida) == {"aplicados": 1, "archivos": 2, "esperan": 0, "rechazados": 0}
    assert (chile / "280. Obra de ejemplo" / "Factura 12-34.pdf").read_bytes() == pdf
    assert (chile / "280. Obra de ejemplo" / "boleta.JPG").read_bytes() == foto
    assert not errores
    pagina.context.close()


def test_subir_documentos_carpeta_nueva_y_peru(navegador, sitio):
    pagina, errores = _subir_con_datos(navegador, sitio)
    pagina.locator("#scLista .sc-op", has_text="908. En obra").click()
    assert "carpeta nueva" in pagina.locator("#scElegidoMeta").inner_text()
    pagina.locator("#scCambiar").click()
    pagina.locator('.sc-pais button[data-pais="PE"]').click()
    assert pagina.locator("#scLista .sc-op").all_inner_texts()[0].startswith("Obra Lima")
    assert not pagina.locator("#scLista .sc-op", has_text="908. En obra").count()
    pagina.locator("#scBuscar").fill("Obra Cusco")
    pagina.locator("#scLista .sc-op", has_text="+ crear carpeta").click()
    assert pagina.locator("#scElegidoMeta").inner_text().startswith("Perú · carpeta nueva")
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [390, 1280])
def test_subir_documentos_sin_desbordes(navegador, sitio, ancho):
    pagina, errores = _subir_con_datos(navegador, sitio, ancho=ancho, alto=844, movil=ancho < 760)
    d = pagina.evaluate(JS_DESBORDES)
    assert d["doc"] <= ancho and not d["fuera"], d
    derecha = pagina.evaluate("""() => Math.max(...[...document.querySelectorAll('#vistaSubir *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))""")
    assert derecha <= ancho + 0.5, derecha
    assert not errores
    pagina.context.close()


def test_subir_documentos_sin_biblioteca_dice_que_conectar(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Subir documentos")
    pagina.locator("#scVacio").wait_for()
    assert "Conecta" in pagina.locator("#scVacio").inner_text() or "Chrome o Edge" in pagina.locator("#scVacio").inner_text()
    assert pagina.locator("#scContenido").is_hidden()
    assert not errores
    pagina.context.close()
