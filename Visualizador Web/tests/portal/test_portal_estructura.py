# -*- coding: utf-8 -*-
"""Portal QUEMPIN: el archivo, su registro y lo que leen las demás herramientas (casi todo sin navegador).

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- El archivo y su registro -------------------------------------------------------------------


def test_cabecera_del_portal():
    html = texto_portal()
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="es">' in html
    assert '<meta charset="utf-8">' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "user-scalable" not in html and "maximum-scale" not in html


def test_no_carga_nada_de_otro_sitio_ni_lleva_datos():
    html = texto_portal()
    # Los scripts enlazados son el de las cajas de números (2026-11-10) y los del Portal en js/ (2026-11-18), del mismo
    # sitio: publicar.py los copia con él.
    scripts = re.findall(r"<script[^>]+\bsrc=[^>]*>", html)
    assert scripts == ['<script src="../numeros.js">'] + [f'<script src="js/{a}">' for a in archivos_js()], "sin scripts externos"
    # Las hojas que enlaza son la de las fuentes (2026-10-30) y portal.css (2026-11-18), del mismo sitio.
    assert re.findall(r"<link[^>]+stylesheet[^>]*>", html) == ['<link rel="stylesheet" href="../marca/fuentes.css">',
                                                              '<link rel="stylesheet" href="portal.css">']
    assert "@import" not in html, "sin hojas de estilo de otro sitio"
    assert not re.search(r"url\(\s*['\"]?https?:", html), "ninguna fuente de otro sitio"
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
            assert f'id="{h["vista"]}"' in texto_portal(), h["id"]
        assert h.get("claves", "") == h.get("claves", "").lower(), h["id"]
    for g in grupos:
        assert any(h["grupo"] == g for h in herr), f"grupo vacío: {g}"
    # Lo que muestra el Inicio: cada herramienta con su línea breve, que cabe en una línea
    for h in herr:
        if h["grupo"] in grupos - {"ayuda"}:
            assert 0 < len(h.get("breve", "")) <= 38, h["id"]
        if h["tipo"] == "marco":   # el nombre de su pestaña
            assert len(h.get("corto", h["nombre"])) <= 18, h["id"]


def test_los_grupos_por_etapa_del_trabajo():
    """Pedido del 2026-11-10 (el Inicio como centro de trabajo): las herramientas por etapa del trabajo, en el Inicio y en
    el menú; lo de Sistema QUEMPIN va en la etapa donde se usa. La calculadora al final, antes de la ayuda."""
    reg = _registro()
    assert [g["nombre"] for g in reg["grupos"]] == [
        "Captar y ofertar", "Ejecutar proyectos", "Control financiero", "Calculadora", "Ayuda"]
    de = lambda g: [h["id"] for h in reg["herramientas"] if h["grupo"] == g]
    assert de("ofertar") == ["oportunidades", "planilla", "formulador", "proyectos", "cotizador", "cotizacion"]
    assert de("ejecutar") == ["ejecucion", "planificacion", "gantt", "orden-compra", "subir-cc"]
    # «Ingresar avance» vive dentro del Análisis Financiero (pedido del 2026-11-18): sin acceso propio en el Inicio ni en el menú
    assert sorted(de("oculto")) == ["calculadora", "ingresar"]
    assert de("controlar") == ["centro-costos", "analisis", "rendiciones", "flujo-caja"]


def test_la_ayuda_sin_indice_anterior_y_con_configuracion():
    """Pedido del 2026-10-16: fuera el «Índice anterior»; en su lugar, Configuración y conexiones."""
    ayuda = [h for h in _registro()["herramientas"] if h["grupo"] == "ayuda"]
    assert [h["nombre"] for h in ayuda] == ["Cómo usar el portal", "Configuración y conexiones", "Errores y observaciones"]
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
        if h["grupo"] in {"ofertar", "ejecutar", "controlar"}:
            assert h["id"] in usadas or (h.get("alias") and h["familia"] in usadas), h["id"]
    tareas = [t["nombre"] for t in cx["procesador"]["tareas"]]
    assert tareas == ["Procesar intercambio QUEMPIN", "Registrar en la Planilla QUEMPIN", "Actualizar Finanzas QUEMPIN",
                      "Oportunidades Mercado Publico QUEMPIN"]
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
