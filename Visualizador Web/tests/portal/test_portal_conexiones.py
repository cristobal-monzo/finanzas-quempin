# -*- coding: utf-8 -*-
"""Portal QUEMPIN: Configuración y conexiones.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- Configuración y conexiones (2026-10-16) -------------------------------------------------------


def test_configuracion_y_conexiones_en_su_pestana(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Configuración y conexiones")
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
    for juntas in ("Centro de Costos y Análisis Financiero",):
        assert juntas in por_nombre, juntas
    # Emitir cotización y Orden de compra necesitan lo mismo, pero desde el 2026-11-10 van en etapas distintas
    assert por_nombre["Emitir cotización"] == por_nombre["Orden de compra"]
    assert filas[-1] == ["Calculadora (todas)", []]
    assert {"Biblioteca Formulación", "Carpeta de intercambio", "Contraseña"} <= set(por_nombre["Formulador"])
    # La Carta Gantt, herramienta aparte (2026-10-20): la carpeta del equipo para compartir sus cartas
    assert set(por_nombre["Carta Gantt"]) == {"Biblioteca Formulación", "Carpeta de intercambio", "Contraseña"}
    assert "QUEMPIN.exe" in por_nombre["Emitir cotización"]
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
