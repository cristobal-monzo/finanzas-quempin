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

Desde el 2026-11-18 las pruebas están en tests/portal/test_portal_<vista>.py y aquí queda lo común: rutas, el sitio de mentira, las fixtures, constantes y ayudantes."""
import base64
import functools
import http.server
import importlib.util
import json
import re
import shutil
import threading
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parents[1]          # tests/ (este archivo está en tests/portal/)
VISUALIZADOR = AQUI.parent
RAIZ = VISUALIZADOR.parent
PORTAL = VISUALIZADOR / "portal" / "index.html"
BASES = ("/formulacion-proyectos-quempin/", "/finanzas-quempin/", "/calculadora-tecnica-quempin/")
TIPOS = {"marco", "excel", "programa", "archivo", "ayuda", "inicio", "vista"}
LS_PROYECTOS = "qpn.formulacion.proyectos.v1"
# Lo que el portal carga del Formulador (mismo sitio), con el nombre global de cada uno
FORMULADOR_JS = {"pulso.js": "QPulso", "calc.js": "QCalc", "pegar.js": "QPegar", "busqueda.js": "CHBusqueda"}


def _bloque(id_):
    html = texto_portal()
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


# Un pixel rojo
PNG_ROJO = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC")


def _sitio(raiz: Path):
    def pagina(ruta, titulo, herr, cuerpo="", script=""):
        destino = raiz / ruta.strip("/") / "index.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(PAGINA.format(titulo=titulo, herr=herr, cuerpo=cuerpo, script=script), encoding="utf-8")

    # El Portal con sus partes (portal.css, js/), como lo deja publicar.py
    shutil.copytree(PORTAL.parent, raiz / "finanzas-quempin" / "portal",
                    ignore=shutil.ignore_patterns("docs", "*.py", "*.md", "__pycache__"))
    shutil.copytree(PORTAL.parents[1] / "marca", raiz / "finanzas-quempin" / "marca")
    shutil.copy2(PORTAL.parents[1] / "numeros.js", raiz / "finanzas-quempin" / "numeros.js")   # como lo deja publicar.py
    shutil.copy2(PORTAL.parents[1] / "candado.js", raiz / "finanzas-quempin" / "candado.js")   # abre el resumen del teléfono
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
    # El pulso del procesador que lee «Configuración y conexiones» y, desde el 2026-10-28, lo que «Proyectos en ejecución»
    # usa del Formulador: sus reglas de cálculo, su lector de filas pegadas y el buscador del Cotizador (si está en este equipo)
    formulador = _hermano("Formulación de proyectos")
    for nombre in FORMULADOR_JS:
        js = formulador / "quempin-formulacion" / "js" / nombre if formulador else None
        if js and js.exists():
            (raiz / "formulacion-proyectos-quempin" / "js").mkdir(parents=True, exist_ok=True)
            (raiz / "formulacion-proyectos-quempin" / "js" / nombre).write_bytes(js.read_bytes())
    # El validador que el Portal carga del Formulador antes de escribir sus archivos (2026-11-06). Su fuente es
    # Sistema Intercambio/esquemas.js (el Formulador lleva una copia textual): así se prueba también sin el Formulador.
    (raiz / "formulacion-proyectos-quempin" / "js").mkdir(parents=True, exist_ok=True)
    (raiz / "formulacion-proyectos-quempin" / "js" / "esquemas.js").write_bytes((RAIZ / "Sistema Intercambio" / "esquemas.js").read_bytes())
    pagina("/calculadora-tecnica-quempin/", "Calculadora Técnica", "calc")
    for ruta, herr in (("DiametroTuberia", "diametro"), ("Hidrogeno", "hidrogeno"),
                       ("GasNatural-GLP", "gas"), ("OtrosGases", "otros")):
        pagina(f"/calculadora-tecnica-quempin/{ruta}/", herr, herr,
               CABECERA_CALC + '<select id="selector-gas" onchange="location.href = this.value"><option value="">—</option>'
               '<option value="../OtrosGases/">Otros gases</option></select>', PESTANAS_CALC.format())
    pagina("/otra-cosa/", "Otra cosa", "otra")
    # Lo que la imagen de la pantalla tiene que incrustar: una hoja de estilo y una imagen de otro archivo
    (raiz / "finanzas-quempin" / "centro-de-costos" / "prueba.css").write_text(
        ".caja-prueba { position: fixed; left: 0; top: 0; width: 100px; height: 100px; background: rgb(12, 34, 56); }", encoding="utf-8")
    (raiz / "finanzas-quempin" / "centro-de-costos" / "prueba.png").write_bytes(PNG_ROJO)


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
        nav.qpn_playwright = p      # para abrir otro motor en el mismo hilo (WebKit: test_portal_movil.py)
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


JS_DESBORDES = _cargar("auditoria_movil_para_test_portal", VISUALIZADOR / "auditoria_movil.py").JS_DESBORDES


# ---- Dentro del portal las herramientas no repiten su cabecera (2026-10-16) ----------------------

def _estilo(marco, selector, prop="display"):
    return marco.evaluate("([s, p]) => { const e = document.querySelector(s); return e ? getComputedStyle(e)[p] : null; }",
                          [selector, prop])


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


def _plantilla_tablero(subruta, compilado):
    """El template de un tablero publicado (el AF de Perú se arma con el de Chile)."""
    t = RAIZ / Path(compilado).parent.parent / "template.html"
    if t.exists():
        return t
    # AF y el Cotizador de Perú usan la plantilla de Chile
    modulo = "Cotizador Historico" if subruta.startswith("cotizador") else "Sistema Analisis Financiero"
    return RAIZ / modulo / "Visualizador Web" / "template.html"


# ---- Usuario (2026-10-16): las iniciales del equipo, elegidas una vez por navegador -------------------

USUARIOS = ["NB", "ES", "LC", "CM", "MP"]


def _proyectos_con_responsable():
    datos = json.loads(json.dumps(PROYECTOS))
    datos["proyectos"][1]["responsable"] = "LC"     # QMPN-2026-001 v2, la versión que manda
    datos["proyectos"][2]["responsable"] = "CM"     # QMPN-2026-002
    return datos


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
        # El catálogo que deja el procesador: con él, todo lo que el Portal escribe en estas pruebas se valida (2026-11-06)
        "esquemas.json": _cargar("esquemas_para_test_portal", RAIZ / "Sistema Intercambio" / "esquemas.py").paquete(),
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


JS_BUZON_VUELTA = """async () => {
    const raiz = await navigator.storage.getDirectory();
    const bib = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos');
    const inter = await (await bib.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN')).getDirectoryHandle('Intercambio');
    const buzon = await inter.getDirectoryHandle('buzon');
    const salida = [];
    for await (const [n, h] of buzon.entries()) {
        if (n.includes('_pedir-vuelta_')) salida.push({ nombre: n, mensaje: JSON.parse(await (await h.getFile()).text()) });
    }
    return salida;
}"""

JS_PROCESADOR_ATIENDE = """async ({ borrar, pulso }) => {
    // Lo que deja una vuelta en la carpeta, por partes: OneDrive trae el buzón y el pulso por separado.
    const raiz = await navigator.storage.getDirectory();
    const bib = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos');
    const inter = await (await bib.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN')).getDirectoryHandle('Intercambio');
    if (borrar) {
        const buzon = await inter.getDirectoryHandle('buzon');
        for await (const n of buzon.keys()) if (n.includes('_pedir-vuelta_')) await buzon.removeEntry(n);
    }
    if (pulso) {
        const pub = await inter.getDirectoryHandle('publicado');
        const w = await (await pub.getFileHandle('estado.json', { create: true })).createWritable();
        await w.write(JSON.stringify({ esquema: 'quempin.intercambio/1', datos: { procesador: {
            ultimaCorrida: new Date(Date.now() + 1000).toISOString(), pasos: {} } } }));
        await w.close();
    }
}"""


def _inicio_con_semana(navegador, sitio, **kw):
    """El Inicio con la carpeta de prueba y esta semana planificada (lunes: cuatro proyectos; miércoles: uno)."""
    from datetime import date, timedelta
    semana, lunes = _semana_de(date.today())
    d = lambda i: (lunes + timedelta(days=i)).isoformat()
    asig = lambda i, per, p: {"dia": d(i), "persona": per, "proyecto": p, "activa": True, "t": _instante(-60), "por": "NB"}
    usos = [(0, "NB", "req:908"), (0, "ES", "req:908"), (0, "LC", "req:908"), (0, "CM", "req:907"), (0, "MP", "tag:SOLO"),
            (0, "EV", "otra:bodega"), (2, "NB", "req:907"), (2, "ES", "req:907")]
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC", **kw)
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {f"publicado/planificacion/{semana}/otro0001.json": _sobre_plan(
        semana, lunes, "otro0001", [asig(*u) for u in usos], proyectos={"otra:bodega": {"titulo": "Bodega"}})})
    pagina.reload()
    pagina.locator("#iniSemana .ini-sem-dia").first.wait_for()
    return pagina, errores


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
        if (v) localStorage.setItem('quempin_portal_plan', JSON.stringify({ v: 2, vista: v }));
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


def _mas(pagina, id_):
    """Un botón del menú «Más» de la Planificación (2026-10-28), con el menú abierto."""
    if pagina.locator("#plMasLista").is_hidden():
        pagina.locator("#plMas").click()
    return pagina.locator(id_)


def _alarma(pagina):
    """La lista de los proyectos sin asignar, desplegada desde su cifra del resumen (2026-10-28)."""
    if pagina.locator("#plAlarma").is_hidden():
        pagina.locator("#plResumen .pl-kpi-alarma").click()
    return pagina.locator("#plAlarma")


# La cuenta de la alarma, junto a la Planificación en el Inicio (ya no en la cabecera, 2026-10-28)
ALERTA_N = '#menu .menu-item[data-herr="planificacion"] .pl-alerta-n'


def _celda_proyecto(pagina, clave, dia):
    return pagina.locator(f'#plProyecto tr[data-clave="{clave}"] td[data-dia="{dia}"] .pl-celda')


# ---- La vista simple y el arrastre (2026-10-28) ------------------------------------------------------------------

def _dia_general(pagina, i):
    """General muestra un día en grande (2026-11-16): se elige en «La semana», al lado. Abre en hoy."""
    pagina.locator(f'#plGeneral .pl-sem-dia[data-dia="{i}"]').click()
    assert pagina.locator("#plGeneral .pl-dia-grande").get_attribute("data-dia") == str(i)


def _dias_de(lunes):
    from datetime import timedelta
    return [lunes + timedelta(days=i) for i in range(5)]


# ---- Vehículos de la Planificación (2026-10-25) -------------------------------------------------------------------

# Las etiquetas de vehículo dentro de un elemento: [nombre, iniciales de quienes lo llevan si no son todos]
JS_VEHS = """(el) => [...el.querySelectorAll('.pl-veh')].map((v) => [v.querySelector('.n').textContent,
    v.querySelector('.q') ? v.querySelector('.q').textContent : ''])"""

# «Vehículos en la semana» (vista General): cada día, por vehículo, sus usos («En obra ES LC», con « / » entre uno y
# otro) o «Libre»
JS_PANEL_VEHICULOS = """() => [...document.querySelectorAll('#plVehiculos tbody tr')].map((tr) => [tr.dataset.iso,
    Object.fromEntries([...tr.querySelectorAll('td[data-veh]')].map((td) => [td.dataset.veh,
        [...td.querySelectorAll('.pl-veh-uso')].map((b) => b.querySelector('.t').textContent + ' ' + b.querySelector('.quien').textContent).join(' / ')
        || td.textContent.trim()]))])"""


def _vehs(locator):
    return locator.evaluate(JS_VEHS)


def _semana_con_vehiculos(pagina):
    """Lo que planificó otro computador: ES y LC van en la RAM a En obra el lunes; MP en la Quempineta a Obra sin número
    de lunes a miércoles; el martes, la RAM va con ES a En obra y con NB a Adjudicada sin ficha (dos lugares a la vez)."""
    from datetime import date, timedelta
    semana, lunes = _semana_de(date.today())
    d = lambda i: (lunes + timedelta(days=i)).isoformat()
    asig = lambda dia, per, p: {"dia": dia, "persona": per, "proyecto": p, "activa": True, "t": _instante(-60), "por": "NB"}
    veh = lambda dia, per, p, v: {"dia": dia, "persona": per, "proyecto": p, "vehiculo": v, "t": _instante(-50), "por": "NB"}
    usos = [(0, "ES", "req:908", "ram"), (0, "LC", "req:908", "ram"), (1, "ES", "req:908", "ram"), (1, "NB", "req:907", "ram")] + [
        (i, "MP", "tag:SOLO", "quempineta") for i in range(3)]
    sobre = _sobre_plan(semana, lunes, "otro0002", asignaciones=[asig(d(i), per, p) for i, per, p, _ in usos])
    sobre["datos"]["vehiculos"] = [veh(d(i), per, p, v) for i, per, p, v in usos]
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {f"publicado/planificacion/{semana}/otro0002.json": sobre})
    pagina.locator("#plActualizar").click()
    pagina.wait_for_function("(document.querySelector('#plResumen .pl-kpi-veh .rc-kpi-n') || {}).textContent === '2'")
    return semana, lunes


def _cambio_de_otro(semana, lunes, dia, persona="MP", por="NB", dispositivo="otro0001"):
    from datetime import timedelta
    d = (lunes + timedelta(days=dia)).isoformat()
    return {f"publicado/planificacion/{semana}/{dispositivo}.json": _sobre_plan(semana, lunes, dispositivo, [
        {"dia": d, "persona": persona, "proyecto": "req:908", "activa": True, "t": _instante(1), "por": por}])}


def _presencia(dispositivo, por, vista, donde, segundos=0):
    return {"esquema": "quempin.intercambio/1", "herramienta": "portal", "generado": _instante(segundos),
            "datos": {"dispositivo": dispositivo, "por": por, "vista": vista, "donde": donde, "t": _instante(segundos)}}


# ---- Personas y proyectos escritos a mano en la Planificación (2026-10-26) ---------------------------------------

LISTA = f"publicado/planificacion/lista/{DISPOSITIVO}.json"


def _esquemas():
    return _cargar("esquemas_para_test_portal", RAIZ / "Sistema Intercambio" / "esquemas.py")


CIERRES = f"publicado/planificacion/cierres/{DISPOSITIVO}.json"

JS_BUZON = """async () => {
    const raiz = await navigator.storage.getDirectory();
    let d = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos');
    d = await (await (await d.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN')).getDirectoryHandle('Intercambio')).getDirectoryHandle('buzon');
    const salida = {};
    for await (const [n, h] of d.entries()) if (h.kind === 'file') salida[n] = JSON.parse(await (await h.getFile()).text());
    return salida;
}"""


def _proyectos_del_dialogo(pagina, titulo):
    """Las claves de una lista de «Estado de los proyectos» («En ejecución · 3», «Cerrados en la planificación»)."""
    return pagina.evaluate("""(t) => {
        const h = [...document.querySelectorAll('#plProyLista h3')].find((x) => x.textContent.startsWith(t));
        return h ? [...h.nextElementSibling.querySelectorAll(':scope > li[data-tarjeta], :scope > li[data-clave]')].map((li) => li.dataset.clave || li.dataset.tarjeta) : null;
    }""", titulo)


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
    # La lista se pinta dos veces: al abrir la vista y cuando termina de leer las carpetas del Centro de Costos
    # (scCargar, asíncrono). Esperar solo la primera opción dejaba leerla a medio armar: en el runner de GitHub, más
    # lento, faltaba «12 documentos» y el CI estuvo rojo del 29-10 al 05-11 (pasaba en el equipo de la oficina).
    pagina.wait_for_function("""() => {
        const t = [...document.querySelectorAll('#scLista .sc-op')].map((o) => o.innerText);
        return t.some((x) => x.includes('280. Obra de ejemplo') && x.includes('12 documentos'))
            && t.some((x) => x.startsWith('908. En obra'));
    }""")
    return pagina, errores


# ── Rendiciones (2026-11-18): lectura de cada boleta o factura, tabla, PDF y Centro de Costos ──────────────────────
RD_BOLETA = """R.U.T.: 76.111.111-6
Boleta electrónica
N9 1234567
RESTAURANTE EJEMPLO
COMIDAS EJEMPLO LIMITADA
Fecha: 2026 10-14
ID UNICO TX:
76111111_39_1234567
1 x $ 6.190
TOTAL: $6.190
Neto: $ 5.202
IVA (19%): $ 988"""
RD_VOUCHER = """GETNET
COMPRA EXENTA
VALIDO COMO BOLETA
Rut: 77.222.222-K
TRANSPORTES EJEMPLO LTDA
11/09/2026 15:55:44 AID:
Monto: $ 2.400
Total: $ 2.400
Aprobación: 259032 Comprabante: 000119"""
RD_FACTURA = """COMBUSTIBLES DEL SUR SPA
R.U.T.: 76.111.111-6
FACTURA ELECTRONICA
Nro: 296581
Fecha emisión: 14/10/2076
Razón social: QUEMPIN SPA
RUT: 76772215-K
Petróleo Diesel 47,28 x 1.410
TOTAL NETO 58.109
TOTAL EXENTO 0
I.V.A. (19%) 12.671
TOTAL 70.780"""
# Las librerías del CDN, imitadas: Tesseract devuelve en orden los textos de window.__ocr y jsPDF anota lo que dibuja.
RD_TESSERACT = """window.Tesseract = { createWorker: async () => ({ recognize: async () => {
    const t = (window.__ocr || []).shift() || '';
    return { data: { text: t, confidence: 92, words: [] } };
} }) };"""
RD_JSPDF = """(() => {
  class jsPDF {
    constructor() { window.__pdf = { paginas: 1, textos: [], fotos: 0, logos: 0, guardado: null }; }
    text(t) { window.__pdf.textos.push(String(t)); }
    addImage(d, formato) { if (formato === 'PNG') window.__pdf.logos++; else window.__pdf.fotos++; }
    addPage() { window.__pdf.paginas++; }
    getNumberOfPages() { return window.__pdf.paginas; }
    getTextWidth(s) { return String(s).length * 1.6; }
    save(n) { window.__pdf.guardado = n; }
    output(t) { window.__pdf.salidas = (window.__pdf.salidas || 0) + 1; return new TextEncoder().encode('%PDF-1.4 rendicion de prueba').buffer; }
  }
  ['setPage', 'setFont', 'setFontSize', 'setTextColor', 'setDrawColor', 'setFillColor', 'setLineWidth', 'line', 'rect', 'roundedRect']
    .forEach((m) => { jsPDF.prototype[m] = function () {}; });
  window.jspdf = { jsPDF };
})();"""
RD_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=")
JS_RD_FILAS = """() => [...document.querySelectorAll('#rdFilas > tr')].map((tr) => Object.assign(
    Object.fromEntries([...tr.querySelectorAll('[data-campo]')].map((e) => [e.dataset.campo, e.value])),
    { dudas: [...tr.querySelectorAll('.duda')].map((e) => e.dataset.campo), lectura: tr.querySelector('.rd-lect').innerText }))"""


def _rd_librerias(pagina):
    def servir(ruta):
        url = ruta.request.url
        cuerpo = RD_TESSERACT if "tesseract" in url else RD_JSPDF if "jspdf" in url else None
        if cuerpo is None:
            ruta.fulfill(status=404, body="")
        else:
            ruta.fulfill(status=200, content_type="application/javascript", body=cuerpo,
                         headers={"access-control-allow-origin": "*"})
    pagina.context.route("https://cdn.jsdelivr.net/**", servir)
    pagina.context.route("https://cdnjs.cloudflare.com/**", servir)


def _rd_subir(pagina, textos, nombres):
    pagina.evaluate("t => { window.__ocr = (window.__ocr || []).concat(t); }", textos)
    pagina.locator("#rdArchivo").set_input_files([{"name": n, "mimeType": "image/png", "buffer": RD_PNG + bytes(i)} for i, n in enumerate(nombres)])
    pagina.wait_for_function("""n => {
        const filas = [...document.querySelectorAll('#rdFilas > tr')];
        return filas.length === n && filas.every((tr) => tr.querySelector('.rd-lect').dataset.nivel !== 'leyendo');
    }""", arg=len(nombres))


# ---- Proyectos en ejecución (2026-10-28) ------------------------------------------------------------------------------
EJ = f"publicado/ejecucion/{DISPOSITIVO}.json"
JS_EJ_KPIS = """() => Object.fromEntries([...document.querySelectorAll('#ejProyecto .ej-kpi')].map((k) =>
    [k.querySelector('.ej-kpi-et').textContent, k.querySelector('.ej-kpi-v').textContent]))"""
JS_EJ_IND = """() => Object.fromEntries([...document.querySelectorAll('#ejProyecto .ej-ind tbody tr')].map((tr) =>
    [tr.dataset.ind, [...tr.querySelectorAll('td')].map((td) => td.textContent.trim())]))"""
# «Cómo va el proyecto» es una tabla desde el 2026-11-06: lo gastado de la mano de obra
JS_EJ_MO = """() => document.querySelector('#ejProyecto tr.ej-cat[data-cat="Mano de Obra"] td[data-et="Gastado"]').textContent"""
JS_EJ_COMO = """(cat) => Object.fromEntries([...document.querySelectorAll('#ejProyecto tr.ej-cat[data-cat="' + cat + '"] td')].map((td) => [td.dataset.et, td.textContent]))"""


def _con_formulador_js(*nombres):
    """¿Sirve el sitio de prueba estos scripts del Formulador? (solo si su repositorio está en este equipo)"""
    f = _hermano("Formulación de proyectos")
    return bool(f) and all((f / "quempin-formulacion" / "js" / n).exists() for n in nombres)


def _formulacion_908():
    """Una formulación adjudicada de mentira para el N° 908: $1.000.000 en materiales (un estanque de $800.000 y 50 m de
    cañería), $500.000 en equipos, $600.000 en mano de obra (10 días-hombre de nivel 2) y $400.000 en otros; utilidad
    50 %: precio neto $3.750.000."""
    datos = {"uid": "f908", "codigo": "QMPN-2026-908", "version": 1, "titulo": "En obra", "estado": "Adjudicada", "responsable": "LC",
             "modificado": _dia(-30, "10:00:00Z"), "vinculos": {"requerimiento": {"numero": 908}},
             "parametros": {"moneda": "CLP", "iva": 19, "gastosGenerales": 0, "imprevistos": 0, "tarifaN1": 45000, "tarifaN2": 60000,
                            "tarifaN3": 75000, "margenObjetivo": 30, "margenMinimo": 20, "metaUtilidadDH": 0},
             "partidas": [{"uid": "p1", "descripcion": "Sala de calderas", "unidad": "gl", "cantidad": 1, "utilidadTipo": "pct", "utilidadValor": 50}],
             "materiales": [{"uid": "m1", "descripcion": "Estanque inoxidable 100 L", "partida": "p1", "unidad": "Un.", "cantidad": 1, "costoUnitario": 800000},
                            {"uid": "m2", "descripcion": "Cañería de cobre 1/2", "partida": "p1", "unidad": "m", "cantidad": 50, "costoUnitario": 4000}],
             "equipos": [{"uid": "e1", "descripcion": "Arriendo de andamio", "partida": "p1", "unidad": "día", "cantidad": 10, "costoUnitario": 50000}],
             "manoObra": [{"uid": "h1", "descripcion": "Instalación", "partida": "p1", "n1p": 0, "n1d": 0, "n2p": 2, "n2d": 5, "n3p": 0, "n3d": 0}],
             "otros": [{"uid": "o1", "descripcion": "Viáticos", "partida": "p1", "unidad": "día", "cantidad": 40, "costoUnitario": 10000}]}
    return {"esquema": "quempin.intercambio/1", "herramienta": "formulador", "tipo": "proyecto",
            "resumen": {"precioNeto": 3750000, "errores": 0, "alertas": 0,
                        "costosAF": {"Materiales": 1000000, "Equipos": 500000, "Mano de Obra": 600000, "Otros": 400000}},
            "datos": datos}


def _ejecucion_de_prueba():
    """La carpeta del Recorrido, con el N° 908 en obra: su formulación, su presupuesto y su gasto en el Análisis Financiero
    ($300.000 en materiales y $50.000 en otros), tres OC (una que el Centro de Costos todavía no trae, una que ya está ahí y
    una que el procesador no sabe) y ES y LC asignados el lunes de esta semana en la Planificación."""
    import copy
    from datetime import date
    archivos = copy.deepcopy(_intercambio_de_prueba())
    demo = next(p for p in archivos["publicado/analisis-financiero.json"]["datos"]["proyectos"] if p["tag"] == "DEMO")
    demo.update({"proyectados": {"Materiales": 1000000, "Equipos": 500000, "Mano de Obra": 600000, "Otros": 400000},
                 "reales": {"Materiales": 300000, "Equipos": 0, "Mano de Obra": None, "Otros": 50000}})
    c908 = next(c for c in archivos["publicado/proyectos.json"]["datos"]["proyectos"] if c["req"] == "908")
    c908["ordenes"] = [
        {"folio": "612900", "fecha": _dia(-2), "contraparte": "Ferretería Demo", "referencia": "Codos y tees", "moneda": "CLP", "neto": 120000, "enCentroCostos": False},
        {"folio": "612901", "fecha": _dia(-20), "contraparte": "Andamios Demo", "referencia": "Arriendo", "moneda": "CLP", "neto": 50000, "enCentroCostos": True},
        {"folio": "612902", "fecha": _dia(-1), "contraparte": "Otro Demo", "referencia": "Sin confirmar", "moneda": "CLP", "neto": 70000}]
    archivos["publicado/formulador/f908.json"] = _formulacion_908()
    semana, lunes = _semana_de(date.today())
    archivos[f"publicado/planificacion/{semana}/pruebaplan001.json"] = _sobre_plan(semana, lunes, "pruebaplan001", asignaciones=[
        {"dia": lunes.isoformat(), "persona": p, "proyecto": "req:908", "activa": True, "t": _instante(-3600), "por": "NB"} for p in ("ES", "LC")],
        proyectos={"req:908": {"titulo": "En obra"}})
    return archivos


def _ejecucion_con_datos(navegador, sitio, usuario="LC", proyecto=None, cambiar=None, **kw):
    """El portal con la carpeta de prueba, en «Proyectos en ejecución» (y, con proyecto, en su resumen).
    cambiar(archivos): para ajustar la carpeta de prueba antes de escribirla."""
    pagina, errores = _abrir_portal(navegador, sitio, **kw)
    if not pagina.evaluate("typeof showDirectoryPicker === 'function'"):
        pagina.context.close()
        pytest.skip("este Chromium no conecta carpetas")
    pagina.evaluate(JS_CONECTAR, 30)
    archivos = _ejecucion_de_prueba()
    if cambiar:
        cambiar(archivos)
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, archivos)
    pagina.evaluate("""([u, d, p]) => {
        localStorage.setItem('quempin_usuario', u);
        localStorage.setItem('quempin_portal_dispositivo', d);
        if (p) localStorage.setItem('quempin_portal_ejecucion', JSON.stringify({ proyecto: p }));
    }""", [usuario, DISPOSITIVO, proyecto])
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Proyectos en ejecución")
    pagina.locator("#ejProyecto .ej-kpis" if proyecto else "#ejTarjetas .ej-tarjeta").first.wait_for()
    return pagina, errores


def _esperar_kpi(pagina, etiqueta, valor):
    pagina.wait_for_function("""([e, v]) => [...document.querySelectorAll('#ejProyecto .ej-kpi')].some((k) =>
        k.querySelector('.ej-kpi-et').textContent === e && k.querySelector('.ej-kpi-v').textContent === v)""", arg=[etiqueta, valor])


def _prov(pagina, n=0):
    """La tarjeta del proveedor n en el diálogo de un ítem."""
    return pagina.locator("#ejCProvs .ej-prov-fila").nth(n)


def _escribir_prov(pagina, n, proveedor, precio):
    _prov(pagina, n).locator(".ej-p-prov input").fill(proveedor)
    _prov(pagina, n).locator(".ej-p-precio input").fill(precio)


def _esperar_aviso(pagina, comienzo):
    pagina.wait_for_function("(c) => document.getElementById('aviso').textContent.startsWith(c)", arg=comienzo)


def _pr_kpi(pagina, k):
    return pagina.locator(f'#dlgEjPres .ej-pr-kpi[data-k="{k}"] > b').inner_text()


def _pr_filas(pagina):
    return pagina.locator("#ejPrTabla tbody tr:not(.ej-pr-vacio)")


def _item_de_prueba(i, proveedor, precio, t=-60, **kw):
    return dict({"id": i, "proyecto": "req:908", "tipo": "costo", "t": _instante(t), "por": "NB", "descripcion": "Estanque inoxidable de 100 litros con serpentín de cobre",
                 "categoria": "Materiales", "cantidad": 1, "precio": precio, "proveedor": proveedor, "estado": "evaluar", "simular": False, "grupo": "cgrupoprueba1"}, **kw)


def _sobre_de_otro(*items):
    return ["publicado/ejecucion/otronavegador1.json", json.dumps({"esquema": "quempin.intercambio/1", "herramienta": "ejecucion", "tipo": "ejecucion-proyectos",
            "generado": _instante(0), "datos": {"dispositivo": "otronavegador1", "items": list(items)}})]


def _documentos_908(archivos):
    """Las facturas del Centro de Costos del 908 (TAG DEMO), como las publica el procesador (2026-11-06)."""
    archivos["publicado/documentos-proyecto.json"] = {"esquema": "quempin.intercambio/1", "herramienta": "procesador", "generado": _instante(-600),
        "datos": {"actualizado": "2026-11-06 10:00", "documentos": [
            {"ref": "DEMO-002", "tag": "DEMO", "proyecto": "908. En obra", "fecha": _dia(-3), "tipo": "Factura", "numero": "5521",
             "proveedor": "Aceros Demo SpA", "resumen": "Estanque inoxidable", "categoria": "Materiales", "neto": 200000, "estado": "Pagado",
             "pendiente": False, "enlace": "https://quempinspa2020.sharepoint.com/x/DEMO-002.pdf",
             "items": [{"nombre": "Estanque inoxidable 100 L", "cantidad": 1, "unitario": 200000, "neto": 200000, "categoria": "Materiales"}]},
            {"ref": "DEMO-001", "tag": "DEMO", "proyecto": "908. En obra", "fecha": _dia(-10), "tipo": "Boleta", "numero": "88",
             "proveedor": "Combustibles Demo", "resumen": "Petróleo", "categoria": "Otros", "neto": 30000, "estado": "Pagado",
             "pendiente": True, "enlace": None, "items": []},
            {"ref": "OTRO-001", "tag": "OTRO", "fecha": _dia(-1), "tipo": "Factura", "categoria": "Otros", "neto": 999, "items": []}]}}
    assert _esquemas().validar_publicacion("documentos-proyecto", archivos["publicado/documentos-proyecto.json"]) == []


def _carpetas_908(**carpetas):
    def cambiar(archivos):
        c908 = next(c for c in archivos["publicado/proyectos.json"]["datos"]["proyectos"] if c["req"] == "908")
        c908["carpetas"] = carpetas
    return cambiar


WEB_908 = "https://quempinspa2020.sharepoint.com/Documentos%20compartidos/Centro%20de%20Costos/Facturas%20y%20Boletas/Chile/908.%20En%20obra"


# ---- La cotización del Cotizador Histórico, a un proyecto (2026-10-29) --------------------------------------------------

def _cotizacion(moneda="CLP"):
    """Lo que manda el carrito del Cotizador (datosParaProyecto de su template): dos compras de materiales y una
    herramienta, de mentira. $37.900 netos."""
    pesos = moneda == "CLP"
    return {"v": 1, "origen": "cotizador-historico", "moneda": moneda, "uf": 41221.08 if pesos else None,
            "ufFecha": "26-10-2026 10:00" if pesos else "",
            "filas": [
                {"descripcion": 'Codo de Cobre 1/2"', "unidad": "Un.", "cantidad": 10, "costoUnitario": 1190, "proveedor": "Ferretería Demo",
                 "ref": "codo cobre 1 2", "categoria": "Ferreteria", "compra": "2026-09-04", "nRef": "DEMO-101"},
                {"descripcion": 'Válvula de Bola Bronce 3/4"', "unidad": "Un.", "cantidad": 2, "costoUnitario": 8500, "proveedor": "Otra Demo",
                 "ref": "valvula bola bronce 3 4", "categoria": "Materiales", "compra": "2026-08-20", "nRef": "DEMO-102"},
                {"descripcion": "Taladro percutor (ficticio)", "unidad": "Un.", "cantidad": 1, "costoUnitario": 9000, "proveedor": "",
                 "ref": "", "categoria": "Equipos-Herramientas", "compra": "", "nRef": ""}]}


JS_LL_GRUPOS = """() => Object.fromEntries([...document.querySelectorAll('#llLista .ll-grupo')].map((s) =>
    [s.querySelector('h3').textContent, [...s.querySelectorAll('.ll-item')].map((b) => b.dataset.clave)]))"""


def _llevar(navegador, sitio, datos=None, cambiar=None, **kw):
    """El portal con la carpeta de prueba de «Proyectos en ejecución», el Cotizador abierto aquí dentro y su carrito
    recién mandado con «Llevar a un proyecto…»: el diálogo ya muestra los proyectos."""
    pagina, errores = _abrir_portal(navegador, sitio, **kw)
    if not pagina.evaluate("typeof showDirectoryPicker === 'function'"):
        pagina.context.close()
        pytest.skip("este Chromium no conecta carpetas")
    pagina.evaluate(JS_CONECTAR, 30)
    archivos = _ejecucion_de_prueba()
    if cambiar:
        cambiar(archivos)
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, archivos)
    pagina.evaluate("""([u, d]) => { localStorage.setItem('quempin_usuario', u); localStorage.setItem('quempin_portal_dispositivo', d); }""",
                    ["LC", DISPOSITIVO])
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Cotizador Histórico")
    marco = _marco(pagina, "cotizador")
    # Un mensaje de la página misma (no de una herramienta abierta aquí ni de quien abrió el Portal) no se atiende
    pagina.evaluate("d => postMessage({ tipo: 'quempin-cotizacion', datos: d }, location.origin)", datos or _cotizacion())
    pagina.wait_for_timeout(300)
    assert pagina.locator("#dlgLlevar").is_hidden()
    marco.evaluate("d => parent.postMessage({ tipo: 'quempin-cotizacion', datos: d }, location.origin)", datos or _cotizacion())
    pagina.locator("#dlgLlevar").wait_for()
    pagina.locator("#llLista .ll-grupo").first.wait_for()
    return pagina, errores


# ---- Planilla de Ingreso en el portal (2026-10-29) --------------------------------------------------------------------

def _planilla_con_datos(navegador, sitio, usuario=None, extra=None, **kw):
    """El portal con la carpeta de prueba (y lo que agregue extra), en la Planilla de Ingreso."""
    pagina, errores = _portal_con_datos(navegador, sitio, usuario, **kw)
    if extra:
        pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, extra)
        pagina.reload()
        pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Requerimientos")
    pagina.locator("#pqFilas tr").first.wait_for()
    return pagina, errores


def _ns(pagina):
    return pagina.locator("#pqFilas tr").evaluate_all("trs => trs.map((t) => +t.dataset.n)")


def _pedidos_planilla(pagina, tipo):
    return [m for m in pagina.evaluate(JS_BUZON).values() if m.get("tipo") == tipo and m.get("destino") == "planilla-requerimientos"]


def _pedido(numero, tipo, herramienta="portal", minutos=-5, **cuerpo):
    from datetime import datetime, timedelta
    enviado = (datetime.now().astimezone() + timedelta(minutes=minutos)).isoformat(timespec="seconds")
    m = {"esquema": "quempin.intercambio/1", "id": f"{tipo[:5]}{numero}{herramienta[:3]}x", "tipo": tipo, "destino": "planilla-requerimientos",
         "origen": {"herramienta": herramienta, "usuario": "CM", "enviado": enviado}}
    m.update(cuerpo)
    m.setdefault("requerimiento", {"numero": numero})
    nombre = enviado[:19].replace("-", "").replace(":", "").replace("T", "-") + f"_{herramienta}_{tipo}_{m['id']}.json"
    return nombre, m


# ── «Cerrado» y la carpeta a «0 Proyectos Entregados» (2026-11-09) ──────────

def _con_gestion(*carpetas, estados=None):
    """La carpeta de prueba con estas carpetas en la raíz de Gestión de Proyectos (proyectos.json, «gestion») y, si se
    dan, otros estados en la Planilla."""
    base = _intercambio_de_prueba()
    sobre = base["publicado/proyectos.json"]
    sobre["datos"]["gestion"] = [{"carpeta": c, "req": c.split(".")[0]} for c in carpetas]
    extra = {"publicado/proyectos.json": sobre}
    if estados:
        reqs = base["publicado/requerimientos.json"]
        for r in reqs["datos"]["requerimientos"]:
            r["estado"] = estados.get(r["numero"], r["estado"])
        extra["publicado/requerimientos.json"] = reqs
    return extra


def _mover_pedidos(pagina):
    return [m for m in pagina.evaluate(JS_BUZON).values() if m.get("tipo") == "mover-carpeta"]


def _gestion_908(archivos, estado=None):
    archivos["publicado/proyectos.json"]["datos"]["gestion"] = [{"carpeta": "908. En obra", "req": "908"}]
    if estado:
        for r in archivos["publicado/requerimientos.json"]["datos"]["requerimientos"]:
            if r["numero"] == 908:
                r["estado"] = estado


# ---- Clic derecho y observaciones (2026-10-30) ---------------------------------------------------------------------

JS_LEER_OBSERVACIONES = """async () => {
    const raiz = await navigator.storage.getDirectory();
    const bib = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos');
    const buzon = await (await (await bib.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN')).getDirectoryHandle('Intercambio')).getDirectoryHandle('buzon', { create: true });
    const salida = { mensajes: {}, adjuntos: {} };
    for await (const [n, h] of buzon.entries()) {
        if (h.kind === 'file' && n.includes('_observacion_')) salida.mensajes[n] = await (await h.getFile()).text();
    }
    const adj = await buzon.getDirectoryHandle('adjuntos', { create: true });
    for await (const [id, d] of adj.entries()) {
        for await (const [n, h] of d.entries()) salida.adjuntos[id + '/' + n] = Array.from(new Uint8Array(await (await h.getFile()).arrayBuffer()));
    }
    return salida;
}"""

# Los colores de unos puntos de la imagen de la pantalla que muestra la ventana de reportar, y su tamaño.
JS_PIXELES = """(puntos) => {
    const im = document.querySelector('#obsFotos img');
    const k = document.createElement('canvas');
    k.width = im.naturalWidth;
    k.height = im.naturalHeight;
    const g = k.getContext('2d');
    g.drawImage(im, 0, 0);
    return { ancho: k.width, alto: k.height, colores: puntos.map(([x, y]) => Array.from(g.getImageData(x, y, 1, 1).data).slice(0, 3)) };
}"""


def _opciones_ctx(pagina):
    pagina.locator("#menuCtx[open]").wait_for()
    return pagina.locator("#menuCtx .ctx-txt").all_inner_texts()


def _abrir_reporte(pagina, objetivo):
    objetivo.click(button="right")
    pagina.locator("#menuCtx .ctx-reportar").click()
    pagina.locator("#dlgObs[open]").wait_for()


def _reportar_sin_clic_derecho(pagina):
    """«Reportar» en Errores y observaciones (el Inicio ya no lleva el enlace, 2026-11-10): sin lugar, se elige la herramienta."""
    if pagina.locator("#vistaObservaciones").is_hidden():
        _menu(pagina, "Errores y observaciones")
    pagina.locator("#obsNueva").click()


def _esperar_envio(pagina):
    pagina.wait_for_function("() => !document.getElementById('dlgObs').open")


def _esperar_acceso(pagina):
    pagina.wait_for_function("() => !document.getElementById('obsEnviar').disabled || !document.getElementById('obsConectar').hidden")


def _cerca(color, esperado, margen=6):
    return all(abs(a - b) <= margen for a, b in zip(color, esperado))


def _observacion_unica(pagina):
    leido = pagina.evaluate(JS_LEER_OBSERVACIONES)
    [(nombre, txt)] = leido["mensajes"].items()
    return nombre, json.loads(txt), leido["adjuntos"]


def _observacion_en_buzon(id_, usuario, nota="Una nota de otra persona"):
    return {"esquema": "quempin.intercambio/1", "id": id_, "tipo": "observacion", "destino": "mejora-continua",
            "origen": {"herramienta": "portal", "enviado": "2026-10-30T11:20:00-03:00", "usuario": usuario},
            "clase": "mejora", "nota": nota, "donde": {"herramienta": "cotizador", "nombre": "Cotizador Histórico"}}


# ---- Errores sin aviso (2026-11-18) ------------------------------------------------------------------------------------

def _observaciones_escritas(pagina, n, espera_ms=8000):
    """Espera a que el buzón tenga n observaciones y las devuelve (dict nombre → mensaje)."""
    leido = {}
    for _ in range(espera_ms // 100):
        try:
            leido = {k: json.loads(v) for k, v in pagina.evaluate(JS_LEER_OBSERVACIONES)["mensajes"].items()}
        except Exception:            # leído justo mientras el Portal lo escribe (NotFoundError, JSON a medias)
            leido = {}
        if len(leido) >= n:
            break
        pagina.wait_for_timeout(100)
    return leido


def _lanzar(objetivo, mensaje, promesa=False):
    """Un error sin atrapar (o una promesa rechazada sin catch) en esa página o marco."""
    if promesa:
        objetivo.evaluate("(m) => { Promise.reject(new Error(m)); }", mensaje)
    else:
        objetivo.evaluate("(m) => { setTimeout(() => { throw new Error(m); }); }", mensaje)


JS_ESCRIBIR_BUZON = """async (archivos) => {
    const raiz = await navigator.storage.getDirectory();
    const bib = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos');
    const buzon = await (await (await bib.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN')).getDirectoryHandle('Intercambio')).getDirectoryHandle('buzon', { create: true });
    for (const [nombre, m] of archivos) {
        const w = await (await buzon.getFileHandle(nombre, { create: true })).createWritable();
        await w.write(JSON.stringify(m));
        await w.close();
    }
}"""


def _obs_de_prueba(id_, usuario, nota, enviado, automatico=False):
    m = {"esquema": "quempin.intercambio/1", "id": id_, "tipo": "observacion", "destino": "mejora-continua",
         "origen": {"herramienta": "portal", "enviado": enviado, "usuario": usuario}, "clase": "error", "nota": nota,
         "donde": {"herramienta": "planificacion", "nombre": "Planificación semanal", "ruta": ["Planificación semanal"]}}
    if automatico:
        m["automatico"] = True
        m["tecnico"] = {"mensaje": nota, "archivo": "https://x/finanzas-quempin/portal/", "linea": 812,
                        "firma": "planificacion|" + nota + "|/finanzas-quempin/portal/|812"}
    return [f"20261118-0900{id_[-2:]}_portal_observacion_{id_}.json", m]


# ── «Qué buscamos» del tablero de Oportunidades (2026-11-16) ─────────────────

JS_GUARDAR_DESDE_EL_TABLERO = """(ajustes) => new Promise((listo) => {
    window.addEventListener('message', (e) => {
        if (e.data && e.data.tipo === 'quempin-ajustes-oportunidades-resultado' && e.data.pedido === 'p-prueba') listo(e.data);
    });
    window.parent.postMessage({ tipo: 'quempin-ajustes-oportunidades', pedido: 'p-prueba', ajustes }, location.origin);
})"""

JS_AJUSTES_EN_EL_BUZON = """async () => {
    const raiz = await navigator.storage.getDirectory();
    let d = await raiz.getDirectoryHandle('Formulación de proyectos - Documentos');
    d = await (await (await d.getDirectoryHandle('.HERRAMIENTAS FORMULACIÓN')).getDirectoryHandle('Intercambio')).getDirectoryHandle('buzon');
    const salida = [];
    for await (const [n, h] of d.entries()) if (h.kind === 'file' && n.includes('_ajustes-oportunidades_')) salida.push(JSON.parse(await (await h.getFile()).text()));
    return salida;
}"""


# ---- El Portal partido en archivos (2026-11-18) ---------------------------------------------------------------------

def archivos_js():
    """Los js/ del Portal en el orden en que index.html los carga."""
    return re.findall(r'<script src="js/([^"]+)"></script>', PORTAL.read_text(encoding="utf-8"))


def texto_portal():
    """index.html, portal.css y cada js/ en su orden, juntos: lo que hasta el 2026-11-18 era un solo archivo. Para las
    pruebas que buscan un texto en el código; las que miran el HTML mismo leen PORTAL."""
    partes = [PORTAL, PORTAL.parent / "portal.css", *(PORTAL.parent / "js" / a for a in archivos_js())]
    return "\n".join(p.read_text(encoding="utf-8") for p in partes)


# Lo que importa «from portal_comun import *»: todo menos las fixtures (las engancha conftest.py)
__all__ = [n for n in dir() if not n.startswith("__") and n not in ('sitio', 'navegador')]
