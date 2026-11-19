# -*- coding: utf-8 -*-
"""Portal QUEMPIN: clic derecho, errores y observaciones, y errores sin aviso.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- Clic derecho y observaciones (2026-10-30) ---------------------------------------------------------------------


def test_el_clic_derecho_abre_el_menu_del_portal_y_no_el_del_navegador(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.evaluate("window.addEventListener('contextmenu', (e) => { window.__nativo = !e.defaultPrevented; })")
    pagina.locator("#tituloInicio").click(button="right", position={"x": 5, "y": 5})
    opciones = _opciones_ctx(pagina)
    assert "Reportar un error u observación…" in opciones
    assert "Buscar" in opciones and "Ver las observaciones" in opciones
    assert "Actualizar esta herramienta" not in opciones        # en el Inicio no hay herramienta que actualizar
    assert pagina.evaluate("window.__nativo") is False
    pagina.keyboard.press("Escape")
    assert pagina.locator("#menuCtx").evaluate("(m) => m.open") is False
    assert not errores
    pagina.context.close()


def test_shift_clic_derecho_deja_el_menu_del_navegador(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.evaluate("window.addEventListener('contextmenu', (e) => { window.__nativo = !e.defaultPrevented; })")
    objetivo = pagina.locator("#tituloInicio")
    pagina.keyboard.down("Shift")
    objetivo.click(button="right")
    pagina.keyboard.up("Shift")
    assert pagina.evaluate("window.__nativo") is True
    assert pagina.locator("#menuCtx").evaluate("(m) => m.open") is False
    assert not errores
    pagina.context.close()


def test_el_menu_se_abre_donde_se_hizo_clic_y_siempre_cabe(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio, ancho=1000, alto=700)
    pagina.mouse.click(300, 200, button="right")
    pagina.locator("#menuCtx[open]").wait_for()
    caja = pagina.locator("#menuCtx").bounding_box()
    assert (caja["x"], caja["y"]) == (300, 200)
    # Otro clic derecho, fuera del menú: se va a ese punto. En una esquina no se sale de la pantalla.
    pagina.mouse.click(995, 695, button="right")
    pagina.wait_for_function("() => document.getElementById('menuCtx').open && parseFloat(document.getElementById('menuCtx').style.left) > 300")
    caja = pagina.locator("#menuCtx").bounding_box()
    assert caja["x"] + caja["width"] <= 1000 and caja["y"] + caja["height"] <= 700
    # Un clic fuera lo cierra
    pagina.mouse.click(50, 300)
    assert pagina.locator("#menuCtx").evaluate("(m) => m.open") is False
    assert not errores
    pagina.context.close()


def test_escape_cierra_el_menu_y_no_lo_que_quedo_detras(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio, proyectos=True)
    pagina.locator("#btnUsuario").click()
    pagina.locator("#popUsuario").wait_for()
    pagina.locator("#popUsuario").click(button="right", position={"x": 5, "y": 5})
    pagina.locator("#menuCtx[open]").wait_for()
    pagina.keyboard.press("Escape")
    assert pagina.locator("#menuCtx").evaluate("(m) => m.open") is False
    assert pagina.locator("#popUsuario").is_visible()
    pagina.keyboard.press("Escape")
    assert pagina.locator("#popUsuario").is_hidden()
    assert not errores
    pagina.context.close()


def test_el_menu_se_recorre_con_las_flechas(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.locator("#tituloInicio").click(button="right", position={"x": 5, "y": 5})
    pagina.locator("#menuCtx[open]").wait_for()
    enfocado = "() => document.activeElement.textContent"
    pagina.keyboard.press("ArrowDown")
    assert "Reportar" in pagina.evaluate(enfocado)
    pagina.keyboard.press("End")
    assert "Ver las observaciones" in pagina.evaluate(enfocado)
    pagina.keyboard.press("ArrowDown")
    assert "Reportar" in pagina.evaluate(enfocado)
    pagina.keyboard.press("Enter")
    pagina.locator("#dlgObs[open]").wait_for()
    assert not errores
    pagina.context.close()


def test_el_menu_tambien_funciona_dentro_de_una_herramienta(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    marco = _marco(pagina, "centro-costos", "cc")
    marco.evaluate("window.addEventListener('contextmenu', (e) => { window.__nativo = !e.defaultPrevented; })")
    enlace = marco.locator("#aOtra")
    enlace.click(button="right")
    opciones = _opciones_ctx(pagina)
    assert "Abrir el enlace en otra pestaña" in opciones and "Copiar el enlace" in opciones
    assert "Actualizar esta herramienta" in opciones and "Abrir aparte" in opciones
    assert marco.evaluate("window.__nativo") is False
    # El menú queda junto al enlace, aunque esté dentro del marco
    caja, punto = pagina.locator("#menuCtx").bounding_box(), enlace.bounding_box()
    assert abs(caja["x"] - (punto["x"] + punto["width"] / 2)) < 2
    pagina.locator("#menuCtx .ctx-item", has_text="Abrir el enlace en otra pestaña").click()
    assert pagina.evaluate("window.__abiertas")[-1].endswith("/otra-cosa/")
    assert not errores
    pagina.context.close()


def test_las_opciones_de_una_pestana_y_de_un_boton_del_inicio(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    _marco(pagina, "centro-costos", "cc")
    _menu(pagina, "Configuración y conexiones")
    _menu(pagina, "Flujo de Caja")
    _marco(pagina, "flujo-caja", "fc")
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos", "Conexiones", "Flujo de Caja"]

    pagina.locator('.pestana[data-familia="centro-costos"]').click(button="right")
    opciones = _opciones_ctx(pagina)
    assert {"Actualizar", "Abrir aparte", "Cerrar esta pestaña", "Cerrar las demás", "Reportar un error u observación…"} <= set(opciones)
    pagina.locator("#menuCtx .ctx-item", has_text="Abrir aparte").click()
    assert pagina.evaluate("window.__abiertas")[-1].endswith("/centro-de-costos/")

    # Una vista del portal no se actualiza ni se abre aparte
    pagina.locator('.pestana[data-familia="conexiones"]').click(button="right")
    opciones = _opciones_ctx(pagina)
    assert "Actualizar" not in opciones and "Abrir aparte" not in opciones and "Cerrar esta pestaña" in opciones
    pagina.keyboard.press("Escape")

    pagina.locator('.pestana[data-familia="centro-costos"]').click(button="right")
    pagina.locator("#menuCtx .ctx-item", has_text="Cerrar las demás").click()
    assert _pestanas(pagina) == ["Inicio", "Centro de Costos"]
    _marco(pagina, "centro-costos", "cc")

    pagina.locator('.pestana[data-familia="inicio"]').click()
    pagina.locator('.ini-item[data-herr="oportunidades"]').click(button="right")
    opciones = _opciones_ctx(pagina)
    assert opciones[0] == "Abrir Oportunidades MP" or opciones[0].startswith("Abrir Oportunidades")
    pagina.locator("#menuCtx .ctx-item", has_text="Abrir aparte").first.click()
    assert pagina.evaluate("window.__abiertas")[-1].endswith("/finanzas-quempin/oportunidades/")
    assert not errores
    pagina.context.close()


def test_copiar_cortar_y_pegar_dentro_de_una_herramienta(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=sitio)
    _menu(pagina, "Centro de Costos")
    marco = _marco(pagina, "centro-costos", "cc")
    marco.evaluate("""() => {
        const i = document.createElement('input');
        i.id = 'campoPrueba';
        i.value = 'hola mundo';
        i.addEventListener('input', () => { document.body.dataset.tecleado = i.value; });
        document.body.prepend(i);
    }""")
    campo = marco.locator("#campoPrueba")
    campo.click()
    marco.evaluate("document.getElementById('campoPrueba').setSelectionRange(0, 4)")
    campo.click(button="right", position={"x": 5, "y": 5})
    # El clic derecho no le quita la selección al campo en todos los sistemas: se vuelve a marcar y se reabre
    pagina.locator("#menuCtx[open]").wait_for()
    pagina.keyboard.press("Escape")
    marco.evaluate("document.getElementById('campoPrueba').setSelectionRange(0, 4)")
    marco.evaluate("""() => {
        const c = document.getElementById('campoPrueba');
        const r = c.getBoundingClientRect();
        c.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, button: 2, clientX: r.left + 5, clientY: r.top + 5 }));
    }""")
    opciones = _opciones_ctx(pagina)
    assert {"Cortar", "Copiar", "Pegar", "Seleccionar todo"} <= set(opciones)
    pagina.locator("#menuCtx .ctx-item", has_text="Cortar").click()
    pagina.wait_for_function("() => navigator.clipboard.readText().then((t) => t === 'hola')")
    marco.wait_for_function("document.getElementById('campoPrueba').value === ' mundo'")
    assert marco.evaluate("document.body.dataset.tecleado") == " mundo"      # el campo avisa su cambio, como al teclear
    marco.evaluate("document.getElementById('campoPrueba').setSelectionRange(6, 6)")
    marco.evaluate("""() => {
        const c = document.getElementById('campoPrueba');
        const r = c.getBoundingClientRect();
        c.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, button: 2, clientX: r.left + 5, clientY: r.top + 5 }));
    }""")
    pagina.locator("#menuCtx .ctx-item", has_text="Pegar").click()
    marco.wait_for_function("document.getElementById('campoPrueba').value === ' mundohola'")
    assert not errores
    pagina.context.close()


def test_un_campo_de_clave_no_se_copia_ni_viaja_en_el_reporte(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    marco = _marco(pagina, "centro-costos", "cc")
    marco.evaluate("""() => {
        const i = document.createElement('input');
        i.type = 'password'; i.id = 'clavePrueba'; i.value = 'secreta-de-prueba';
        document.body.prepend(i);
        i.select();
    }""")
    marco.locator("#clavePrueba").click(button="right")
    opciones = _opciones_ctx(pagina)
    assert "Copiar" not in opciones and "Cortar" not in opciones and "Pegar" in opciones
    pagina.locator("#menuCtx .ctx-reportar").click()
    pagina.locator("#dlgObs[open]").wait_for()
    _esperar_acceso(pagina)
    pagina.locator("#obsNota").fill("La contraseña no entra")
    pagina.locator("#obsEnviar").click()
    _esperar_envio(pagina)
    nombre, msg, _ = _observacion_unica(pagina)
    assert "secreta-de-prueba" not in json.dumps(msg)
    assert msg["donde"]["elemento"]["atributos"]["type"] == "password"
    assert not errores
    pagina.context.close()


def test_reportar_llega_al_buzon_y_se_revisa_con_la_linea_de_comandos(navegador, sitio, tmp_path):
    """De punta a punta: clic derecho en una herramienta, enviar, lo que queda en la carpeta lo acepta el esquema y lo
    atiende observaciones.py, y quien reportó ve la respuesta en el portal."""
    import hashlib
    import subprocess
    import sys

    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC", proyectos=True)
    _menu(pagina, "Análisis Financiero")
    marco = _marco(pagina, "analisis", "af")
    marco.locator('.viz-tab-btn[data-tab="tabProyectos"]').click()
    marco.evaluate("""() => {
        document.querySelector('.viz-tab-btn[data-tab="tabProyectos"]').classList.add('is-active');
        const s = document.createElement('section');
        s.innerHTML = '<h2>Resumen del proyecto</h2><p><button id="botonRaro" data-fila="7" title="Calcula el margen">Calcular</button></p>';
        document.body.append(s);
    }""")
    _abrir_reporte(pagina, marco.locator("#botonRaro"))
    assert "Calcular" in pagina.locator("#obsDonde").inner_text()
    assert "Análisis Financiero" in pagina.locator("#obsDonde").inner_text()
    assert pagina.locator("#obsQuien").input_value() == "LC"
    pagina.locator("#obsFotos img").wait_for()
    _esperar_acceso(pagina)
    pagina.locator('input[name="obsClase"][value="dato"]').check(force=True)
    pagina.locator("#obsNota").fill("El margen de este proyecto sale negativo")
    pagina.locator("#obsBloquea").check()
    pagina.locator("#obsArchivo").set_input_files([
        {"name": "de mi teléfono.png", "mimeType": "image/png", "buffer": PNG_ROJO},
        {"name": "planilla.xlsx", "mimeType": "application/vnd.ms-excel", "buffer": b"no"},
    ])
    assert pagina.locator("#obsFotos figure").count() == 2
    assert "planilla.xlsx" in pagina.locator("#obsAcceso").inner_text()    # lo que no sirve se dice, y no se agrega
    pagina.locator("#obsNota").press("Control+Enter")
    _esperar_envio(pagina)
    assert "quedó registrada" in pagina.locator("#aviso").inner_text()

    leido = pagina.evaluate(JS_LEER_OBSERVACIONES)
    [(nombre, txt)] = leido["mensajes"].items()
    msg = json.loads(txt)
    assert nombre.endswith("_portal_observacion_" + msg["id"] + ".json")
    assert msg["clase"] == "dato" and msg["bloquea"] is True and msg["origen"]["usuario"] == "LC"
    d = msg["donde"]
    assert d["herramienta"] == "analisis" and d["nombre"] == "Análisis Financiero"
    assert d["ruta"] == ["Análisis Financiero", "Proyectos"]
    assert d["seccion"] == "Resumen del proyecto"
    assert d["direccion"].endswith("/analisis-financiero/") or "/analisis-financiero/" in d["direccion"]
    assert d["elemento"]["selector"] == "#botonRaro"
    assert d["elemento"]["texto"] == "Calcular" and d["elemento"]["titulo"] == "Calcula el margen"
    assert d["elemento"]["atributos"]["data-fila"] == "7"
    assert "proyecto" not in d          # sin selector de proyecto (2026-11-06)
    assert msg["entorno"]["tema"] in ("claro", "oscuro") and msg["entorno"]["navegador"].startswith("Chrome/")
    assert {a["nombre"]: a["origen"] for a in msg["adjuntos"]} == {"captura.png": "captura", "imagen-1.png": "pegada"}

    # Las imágenes: un PNG de verdad, del tamaño de la herramienta, y con la marca naranja donde se hizo clic
    captura = bytes(leido["adjuntos"][msg["id"] + "/captura.png"])
    assert captura.startswith(b"\x89PNG\r\n\x1a\n")
    [declarada] = [a for a in msg["adjuntos"] if a["nombre"] == "captura.png"]
    assert declarada["bytes"] == len(captura) and declarada["sha256"] == hashlib.sha256(captura).hexdigest()
    assert bytes(leido["adjuntos"][msg["id"] + "/imagen-1.png"]) == PNG_ROJO

    # Lo que quedó en la carpeta, tal cual, para el esquema y la línea de comandos reales
    raiz = tmp_path / "Intercambio"
    (raiz / "buzon").mkdir(parents=True)
    (raiz / "buzon" / nombre).write_text(txt, encoding="utf-8")
    for ruta, datos in leido["adjuntos"].items():
        destino = raiz / "buzon" / "adjuntos" / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(bytes(datos))
    def cli(*args):
        r = subprocess.run([sys.executable, "observaciones.py", "--raiz", str(raiz), *args],
                           cwd=RAIZ / "Sistema Intercambio", capture_output=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        return r.stdout
    (raiz / "intercambio.json").write_text(json.dumps({"esquema": "quempin.intercambio/1"}), encoding="utf-8")
    subprocess.run([sys.executable, "-c", "import json, sys, esquemas; e = esquemas.validar_mensaje(json.load(open(sys.argv[1], encoding='utf-8'))); "
                    "sys.exit('; '.join(e) if e else 0)", str(raiz / "buzon" / nombre)], cwd=RAIZ / "Sistema Intercambio", check=True)
    estado = cli("status")
    assert msg["id"][:8] in estado and "[!]" in estado and "El margen de este proyecto" in estado and "no cumple" not in estado
    assert "captura.png" in cli("ver", msg["id"][:8])
    cli("cerrar", msg["id"][:8], "aplicado", "Ya se corrigió el cálculo del margen")
    [hecho] = list((raiz / "procesado").rglob("*.json"))
    assert (hecho.parent / "adjuntos" / msg["id"] / "captura.png").read_bytes() == captura

    # Quien reportó lo ve en el portal: primero por revisar; con el archivo en «procesado», resuelta y con la respuesta
    pagina.locator('.pestana[data-familia="inicio"]').click()
    _menu(pagina, "Errores y observaciones")
    pagina.locator("#obsLista .sc-pill", has_text="Por revisar").wait_for()
    assert "1 por revisar" in pagina.locator("#obsCuenta").inner_text()
    assert pagina.locator("#obsLista .obs-fila-bloquea").inner_text() == "Impide trabajar"
    assert "Análisis Financiero › Proyectos" in pagina.locator("#obsLista .obs-fila").inner_text()
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {f"procesado/{hecho.parent.name}/{hecho.name}": json.loads(hecho.read_text(encoding="utf-8"))})
    pagina.locator("#obsActualizar").click()
    pagina.locator("#obsLista .sc-pill", has_text="Resuelta").wait_for()
    assert "Ya se corrigió el cálculo del margen" in pagina.locator("#obsLista .obs-fila-res").inner_text()
    assert pagina.locator("#obsLista .obs-retirar").count() == 0
    assert not errores
    pagina.context.close()


def test_la_imagen_se_parece_a_la_pantalla(navegador, sitio):
    """Una imagen SVG no carga nada de afuera: la hoja de estilo y la imagen del marco tienen que ir incrustadas, y lo
    desplazado se ve desplazado."""
    pagina, errores = _portal_con_datos(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    marco = _marco(pagina, "centro-costos", "cc")
    marco.evaluate("""() => new Promise((listo) => {
        const hoja = document.createElement('link');
        hoja.rel = 'stylesheet';
        hoja.href = 'prueba.css';
        hoja.onload = () => {
            const im = new Image();
            im.onload = () => listo();
            im.src = 'prueba.png';
            im.style.cssText = 'position:fixed;left:200px;top:0;width:50px;height:50px';
            document.body.append(im);
        };
        document.head.append(hoja);
        const caja = document.createElement('div');
        caja.className = 'caja-prueba';
        document.body.append(caja);
        const lejos = document.createElement('button');
        lejos.id = 'lejos';
        lejos.textContent = 'Abajo';
        lejos.style.cssText = 'position:absolute;left:400px;top:1500px;width:120px;height:60px;background:rgb(0,160,60);border:0';
        document.body.append(lejos);
        document.body.style.height = '4000px';
        document.body.append(document.createComment('un comentario -- como los del Formulador'));
    })""")
    marco.evaluate("window.scrollTo(0, 1400)")
    _abrir_reporte(pagina, marco.locator("#lejos"))
    pagina.locator("#obsFotos img").wait_for()
    tam = marco.evaluate("[innerWidth, innerHeight]")
    p = pagina.evaluate(JS_PIXELES, [[50, 50], [225, 25], [500, 150]])
    assert [p["ancho"], p["alto"]] == tam
    assert _cerca(p["colores"][0], (12, 34, 56)), p        # la hoja de estilo de otro archivo
    assert _cerca(p["colores"][1], (255, 0, 0)), p         # la imagen de otro archivo
    assert _cerca(p["colores"][2], (0, 160, 60)), p        # lo que está a 1500 px, con la página desplazada a 1400
    assert not errores
    pagina.context.close()


def test_la_imagen_marca_donde_se_hizo_clic(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    marco = _marco(pagina, "centro-costos", "cc")
    marco.evaluate("""() => {
        const b = document.createElement('div');
        b.id = 'plano';
        b.style.cssText = 'position:fixed;left:100px;top:100px;width:300px;height:300px;background:rgb(255,255,255)';
        document.body.append(b);
    }""")
    marco.locator("#plano").click(button="right", position={"x": 150, "y": 150})
    pagina.locator("#menuCtx .ctx-reportar").click()
    pagina.locator("#obsFotos img").wait_for()
    p = pagina.evaluate(JS_PIXELES, [[250 + 16, 250], [250, 250]])
    assert _cerca(p["colores"][0], (255, 81, 0), 40), p    # el círculo naranja
    assert _cerca(p["colores"][1], (255, 255, 255)), p     # y adentro se sigue viendo lo que había
    # Se puede quitar antes de enviar
    pagina.locator("#obsFotos .obs-foto-x").click()
    assert pagina.locator("#obsFotos figure").count() == 0
    assert not errores
    pagina.context.close()


def test_un_clic_en_el_portal_muestra_tambien_la_herramienta_abierta(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    marco = _marco(pagina, "centro-costos", "cc")
    marco.evaluate("""() => {
        const b = document.createElement('div');
        b.style.cssText = 'position:fixed;inset:0;background:rgb(10,120,200)';
        document.body.append(b);
    }""")
    _abrir_reporte(pagina, pagina.locator('.pestana[data-familia="centro-costos"]'))
    pagina.locator("#obsFotos img").wait_for()
    caja = pagina.locator("#marco-centro-costos").bounding_box()
    p = pagina.evaluate(JS_PIXELES, [[caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2]])
    assert [p["ancho"], p["alto"]] == [1280, 860]
    assert _cerca(p["colores"][0], (10, 120, 200)), p
    assert not errores
    pagina.context.close()


def test_flujo_de_caja_no_guarda_imagen_ni_lo_que_muestra_la_pantalla(navegador, sitio):
    """Decisión del 2026-10-02: el resultado de Flujo de Caja no queda en la carpeta que ve toda la biblioteca."""
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC")
    _menu(pagina, "Flujo de Caja")
    marco = _marco(pagina, "flujo-caja", "fc")
    marco.evaluate("""() => {
        const c = document.createElement('button');
        c.id = 'cifra';
        c.dataset.monto = '123456789';
        c.title = 'Caja $123.456.789';
        c.textContent = '$123.456.789';
        document.body.append(c);
        getSelection().selectAllChildren(c);
    }""")
    _abrir_reporte(pagina, marco.locator("#cifra"))
    assert pagina.locator("#obsZonaImagen").is_hidden()
    assert pagina.locator("#obsSinCaptura").is_visible()
    assert "123.456.789" not in pagina.locator("#obsDonde").inner_text()
    _esperar_acceso(pagina)
    pagina.locator("#obsNota").fill("La caja no cuadra")
    # Una imagen pegada tampoco entra
    pagina.evaluate("""() => {
        const d = new DataTransfer();
        d.items.add(new File([new Uint8Array([137, 80, 78, 71])], 'pegada.png', { type: 'image/png' }));
        document.getElementById('obsNota').dispatchEvent(new ClipboardEvent('paste', { bubbles: true, cancelable: true, clipboardData: d }));
    }""")
    assert pagina.locator("#obsFotos figure").count() == 0
    pagina.locator("#obsEnviar").click()
    _esperar_envio(pagina)
    _, msg, adjuntos = _observacion_unica(pagina)
    assert "adjuntos" not in msg and not adjuntos
    assert "123" not in json.dumps(msg["donde"], ensure_ascii=False).replace(msg["donde"].get("direccion", ""), "")
    assert msg["donde"]["herramienta"] == "flujo-caja" and msg["donde"]["elemento"]["atributos"]["id"] == "cifra"
    assert "seleccion" not in msg["donde"]

    # Desde el portal, con Flujo de Caja a la vista, tampoco
    _abrir_reporte(pagina, pagina.locator("#btnMenu"))
    assert pagina.locator("#obsZonaImagen").is_hidden()
    assert pagina.locator("#obsFotos figure").count() == 0
    assert not errores
    pagina.context.close()


def test_pegar_una_imagen_en_la_ventana_la_agrega(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _reportar_sin_clic_derecho(pagina)
    pagina.locator("#dlgObs[open]").wait_for()
    pagina.evaluate("""(bytes) => {
        const d = new DataTransfer();
        d.items.add(new File([new Uint8Array(bytes)], 'pegada.png', { type: 'image/png' }));
        document.getElementById('obsNota').dispatchEvent(new ClipboardEvent('paste', { bubbles: true, cancelable: true, clipboardData: d }));
    }""", list(PNG_ROJO))
    pagina.locator("#obsFotos figure").wait_for()
    # Hasta tres: la zona de agregar desaparece
    pagina.locator("#obsArchivo").set_input_files([{"name": f"i{n}.png", "mimeType": "image/png", "buffer": PNG_ROJO} for n in range(2)])
    assert pagina.locator("#obsFotos figure").count() == 3
    assert pagina.locator("#obsAgregar").is_hidden()
    # Agrandar y quitar
    pagina.locator("#obsFotos .obs-foto-ver").first.click()
    assert pagina.locator("#obsFotos figure.grande").count() == 1
    pagina.locator("#obsFotos .obs-foto-x").first.click()
    assert pagina.locator("#obsFotos figure").count() == 2
    assert pagina.locator("#obsAgregar").is_visible()
    assert not errores
    pagina.context.close()


def test_sin_clic_derecho_se_elige_la_herramienta(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="NB")
    _reportar_sin_clic_derecho(pagina)
    pagina.locator("#dlgObs[open]").wait_for()
    assert pagina.locator("#obsHerrCampo").is_visible()
    assert pagina.locator("#obsDonde").is_hidden()
    assert pagina.locator("#obsHerr").input_value() == "portal"
    assert pagina.locator("#obsFotos figure").count() == 0     # sin clic derecho no hay de qué sacar imagen
    # Elegir Flujo de Caja esconde las imágenes
    pagina.locator("#obsHerr").select_option("flujo-caja")
    assert pagina.locator("#obsZonaImagen").is_hidden()
    pagina.locator("#obsHerr").select_option("cotizador")
    assert pagina.locator("#obsZonaImagen").is_visible()
    _esperar_acceso(pagina)
    pagina.locator("#obsNota").fill("Sería útil ordenar por fecha")
    pagina.locator('input[name="obsClase"][value="mejora"]').check(force=True)
    pagina.locator("#obsEnviar").click()
    _esperar_envio(pagina)
    _, msg, _ = _observacion_unica(pagina)
    assert msg["clase"] == "mejora" and msg["donde"]["herramienta"] == "cotizador"
    assert msg["donde"]["ruta"] == [msg["donde"]["nombre"]] and "elemento" not in msg["donde"]
    assert not errores
    pagina.context.close()


def test_dentro_de_una_ventana_del_portal_dice_cual(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio)
    _menu(pagina, "Emitir cotización")
    pagina.locator("#aviso button", has_text="¿No se abrió?").click()
    pagina.locator("#dlgInfo[open]").wait_for()
    titulo = pagina.locator("#dlgInfoTit").inner_text()
    _abrir_reporte(pagina, pagina.locator("#dlgInfoTxt"))
    assert titulo in pagina.locator("#obsDonde").inner_text()
    _esperar_acceso(pagina)
    pagina.locator("#obsNota").fill("Falta explicar esto")
    pagina.locator("#obsEnviar").click()
    _esperar_envio(pagina)
    _, msg, _ = _observacion_unica(pagina)
    assert msg["donde"]["dialogo"] == titulo
    assert pagina.locator("#dlgInfo").evaluate("(d) => d.open") is True      # la ventana de atrás sigue abierta
    assert not errores
    pagina.context.close()


def test_lo_escrito_sigue_al_cerrar_y_cancelar_lo_borra(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio)
    _reportar_sin_clic_derecho(pagina)
    pagina.locator("#dlgObs[open]").wait_for()
    pagina.locator("#obsNota").fill("Un borrador")
    pagina.locator("#obsBloquea").check()
    pagina.keyboard.press("Escape")
    pagina.wait_for_function("() => !document.getElementById('dlgObs').open")
    _reportar_sin_clic_derecho(pagina)
    assert pagina.locator("#obsNota").input_value() == "Un borrador"
    assert pagina.locator("#obsBloquea").is_checked()
    pagina.locator("#obsCancelar").click()
    _reportar_sin_clic_derecho(pagina)
    assert pagina.locator("#obsNota").input_value() == ""
    assert not pagina.locator("#obsBloquea").is_checked()
    assert not errores
    pagina.context.close()


def test_una_nota_vacia_no_se_envia(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio)
    _reportar_sin_clic_derecho(pagina)
    pagina.locator("#dlgObs[open]").wait_for()
    _esperar_acceso(pagina)
    pagina.locator("#obsNota").fill("ok")
    pagina.locator("#obsEnviar").click()
    assert "pocas palabras" in pagina.locator("#obsAcceso").inner_text()
    assert pagina.locator("#dlgObs").evaluate("(d) => d.open") is True
    assert not pagina.evaluate(JS_LEER_OBSERVACIONES)["mensajes"]
    # Al seguir escribiendo el aviso se va
    pagina.locator("#obsNota").fill("ok, ahora sí")
    assert "pocas palabras" not in pagina.locator("#obsAcceso").inner_text()
    assert not errores
    pagina.context.close()


def test_sin_biblioteca_pide_conectarla(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    if not pagina.evaluate("typeof showDirectoryPicker === 'function'"):
        pagina.context.close()
        pytest.skip("este Chromium no conecta carpetas")
    _reportar_sin_clic_derecho(pagina)
    pagina.locator("#dlgObs[open]").wait_for()
    pagina.locator("#obsConectar").wait_for()
    assert "conecta una vez la biblioteca" in pagina.locator("#obsAcceso").inner_text()
    assert pagina.locator("#obsEnviar").is_disabled()
    assert not errores
    pagina.context.close()


def test_sin_permiso_lo_pide_al_enviar(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio)
    pagina.evaluate("""() => {
        window.__permiso = 'prompt';
        window.__pidio = 0;
        FileSystemDirectoryHandle.prototype.queryPermission = async () => window.__permiso;
        FileSystemDirectoryHandle.prototype.requestPermission = async () => { window.__pidio++; window.__permiso = 'granted'; return 'granted'; };
    }""")
    _reportar_sin_clic_derecho(pagina)
    pagina.locator("#dlgObs[open]").wait_for()
    pagina.wait_for_function("() => document.getElementById('obsAcceso').textContent.includes('pedirá permiso')")
    pagina.locator("#obsNota").fill("Una nota con permiso")
    pagina.locator("#obsEnviar").click()
    _esperar_envio(pagina)
    assert pagina.evaluate("window.__pidio") == 1
    assert _observacion_unica(pagina)[1]["nota"] == "Una nota con permiso"
    assert not errores
    pagina.context.close()


def test_si_niegan_el_permiso_lo_escrito_sigue_ahi(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio)
    pagina.evaluate("""() => {
        FileSystemDirectoryHandle.prototype.queryPermission = async () => 'prompt';
        FileSystemDirectoryHandle.prototype.requestPermission = async () => 'denied';
    }""")
    _reportar_sin_clic_derecho(pagina)
    pagina.locator("#dlgObs[open]").wait_for()
    pagina.wait_for_function("() => document.getElementById('obsAcceso').textContent.includes('pedirá permiso')")
    pagina.locator("#obsNota").fill("Una nota sin permiso")
    pagina.locator("#obsEnviar").click()
    pagina.wait_for_function("() => document.getElementById('obsAcceso').textContent.includes('falta el permiso')")
    assert pagina.locator("#obsNota").input_value() == "Una nota sin permiso"
    assert pagina.locator("#obsEnviar").is_enabled()
    assert not errores
    pagina.context.close()


def test_un_navegador_sin_carpetas_copia_el_reporte(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    pagina.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=sitio)
    pagina.context.add_init_script("delete window.showDirectoryPicker; Object.defineProperty(window, 'showDirectoryPicker', { value: undefined });")
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Centro de Costos")
    marco = _marco(pagina, "centro-costos", "cc")
    _abrir_reporte(pagina, marco.locator("#aOtra"))
    pagina.wait_for_function("() => document.getElementById('obsEnviar').textContent === 'Copiar el reporte'")
    assert "no puede escribir en la carpeta" in pagina.locator("#obsAcceso").inner_text()
    assert pagina.locator("#obsZonaImagen").is_hidden()         # el reporte es solo texto
    pagina.locator("#obsNota").fill("El enlace no abre")
    pagina.locator("#obsEnviar").click()
    _esperar_envio(pagina)
    copiado = pagina.evaluate("navigator.clipboard.readText()")
    assert "El enlace no abre" in copiado and "Centro de Costos" in copiado and "/centro-de-costos/" in copiado
    assert not errores
    pagina.context.close()


def test_la_vista_filtra_lo_propio_y_deja_retirar_solo_lo_propio(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC")
    mia, ajena = "aaaaaaaaaaaa", "bbbbbbbbbbbb"
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {
        f"buzon/20261030-112000_portal_observacion_{mia}.json": _observacion_en_buzon(mia, "LC", "Una nota mía"),
        f"buzon/adjuntos/{mia}/captura.png": "imagen",
        f"buzon/20261030-112000_portal_observacion_{ajena}.json": _observacion_en_buzon(ajena, "NB"),
    })
    _menu(pagina, "Errores y observaciones")
    pagina.locator("#obsLista .obs-fila", has_text="Una nota mía").wait_for()
    assert pagina.locator("#obsLista .obs-fila:not(.obs-fila-vacia)").count() == 2
    assert pagina.locator("#obsLista .obs-retirar").count() == 1
    assert "2 por revisar" in pagina.locator("#obsCuenta").inner_text()
    pagina.locator("#obsMias").check()
    assert pagina.locator("#obsLista .obs-fila").count() == 1
    # Retirar pide confirmación y se lleva también las imágenes
    boton = pagina.locator("#obsLista .obs-retirar")
    boton.click()
    assert "Toca otra vez" in boton.inner_text()
    assert pagina.evaluate(JS_LEER_OBSERVACIONES)["adjuntos"]
    boton.click()
    pagina.locator("#obsLista .obs-fila-vacia").wait_for()
    leido = pagina.evaluate(JS_LEER_OBSERVACIONES)
    assert [n for n in leido["mensajes"]] == [f"20261030-112000_portal_observacion_{ajena}.json"]
    assert not leido["adjuntos"]
    assert not errores
    pagina.context.close()


def test_la_vista_aguanta_un_archivo_raro(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC")
    raro = _observacion_en_buzon("cccccccccccc", "LC", "Una nota rara")
    raro.update(clase="constructor", resultado={"estado": "constructor", "detalle": "no es una lista"})
    mes = pagina.evaluate("new Date().toISOString().slice(0, 7)")
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {
        f"procesado/{mes}/20261030-112000_portal_observacion_cccccccccccc.json": raro,
        "buzon/20261030-112000_portal_observacion_dddddddddddd.json": "esto no es un mensaje",
    })
    _menu(pagina, "Errores y observaciones")
    pagina.locator("#obsLista .obs-fila", has_text="Una nota rara").wait_for()
    assert pagina.locator("#obsLista .obs-fila").count() == 1
    assert not errores
    pagina.context.close()


def test_la_vista_sin_biblioteca_dice_que_conectar_y_igual_deja_reportar(navegador, sitio):
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Errores y observaciones")
    pagina.locator("#obsVacio").wait_for()
    assert pagina.locator("#obsContenido").is_hidden()
    pagina.locator("#obsNueva").click()
    pagina.locator("#dlgObs[open]").wait_for()
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [360, 390])
def test_reportar_en_el_telefono_cabe_y_no_hace_zoom(navegador, sitio, ancho):
    pagina, errores = _portal_con_datos(navegador, sitio, ancho=ancho, alto=740, movil=True)
    # Un teléfono: mantener apretado dispara contextmenu sobre lo tocado
    pagina.evaluate("""() => document.querySelector('#tituloInicio').dispatchEvent(
        new MouseEvent('contextmenu', { bubbles: true, cancelable: true, button: 0, clientX: 300, clientY: 400 }))""")
    pagina.locator("#menuCtx[open]").wait_for()
    caja = pagina.locator("#menuCtx").bounding_box()
    assert caja["x"] >= 0 and caja["x"] + caja["width"] <= ancho and caja["y"] + caja["height"] <= 740
    altos = pagina.evaluate("[...document.querySelectorAll('#menuCtx .ctx-item')].map((b) => b.getBoundingClientRect().height)")
    assert min(altos) >= 44, altos
    pagina.locator("#menuCtx .ctx-reportar").tap()
    pagina.locator("#dlgObs[open]").wait_for()
    pagina.locator("#obsFotos img").wait_for()
    caja = pagina.locator("#dlgObs").bounding_box()
    assert caja["x"] >= 0 and caja["x"] + caja["width"] <= ancho and caja["y"] >= 0 and caja["y"] + caja["height"] <= 740
    derecha = pagina.evaluate("""() => Math.max(...[...document.querySelectorAll('#dlgObs *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))""")
    assert derecha <= ancho + 0.5, derecha
    fuentes = pagina.evaluate("[...document.querySelectorAll('#dlgObs select, #dlgObs textarea')].filter((e) => e.getClientRects().length).map((e) => parseFloat(getComputedStyle(e).fontSize))")
    assert fuentes and min(fuentes) >= 16, fuentes
    # El botón para enviar se alcanza
    assert pagina.locator("#obsEnviar").is_visible()
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [390, 1280])
def test_la_vista_de_observaciones_sin_desbordes(navegador, sitio, ancho):
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC", ancho=ancho, alto=844, movil=ancho < 760)
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {
        "buzon/20261030-112000_portal_observacion_aaaaaaaaaaaa.json": _observacion_en_buzon("aaaaaaaaaaaa", "LC", "Una-nota-" * 40),
    })
    _menu(pagina, "Errores y observaciones")
    pagina.locator("#obsLista .obs-retirar").wait_for()
    d = pagina.evaluate(JS_DESBORDES)
    assert d["doc"] <= ancho and not d["fuera"], d
    derecha = pagina.evaluate("""() => Math.max(...[...document.querySelectorAll('#vistaObservaciones *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))""")
    assert derecha <= ancho + 0.5, derecha
    assert not errores
    pagina.context.close()

# ---- Errores sin aviso (2026-11-18) ------------------------------------------------------------------------------------
# Plan docs/plans/2026-11-18-mejoras-portal.md, fase A: un error de JavaScript llega solo a «Errores y observaciones».


def test_un_error_del_portal_llega_solo_a_observaciones(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="NB")
    _lanzar(pagina, "Falla de prueba del Portal")
    escritas = list(_observaciones_escritas(pagina, 1).values())
    # Otro error que el Portal envió solo sería uno de verdad (una vez llegó uno en la suite completa): que se vea cuál
    otros = [(o.get("tecnico") or {}).get("mensaje") for o in escritas if "Falla de prueba" not in (o.get("tecnico") or {}).get("mensaje", "")]
    assert not otros, f"el Portal envió además estos errores: {otros}"
    [m] = escritas
    assert m["tipo"] == "observacion" and m["destino"] == "mejora-continua" and m["clase"] == "error"
    assert m["automatico"] is True and "adjuntos" not in m
    assert m["origen"]["usuario"] == "NB"
    assert m["nota"].startswith("Error automático:") and "Falla de prueba del Portal" in m["nota"]
    t = m["tecnico"]
    assert t["tipo"] == "error" and "Falla de prueba del Portal" in t["mensaje"]
    assert t["firma"].startswith("inicio|") and "pila" in t and isinstance(t["linea"], int)
    assert m["donde"]["herramienta"] == "inicio"
    # Ya enviado: no queda nada esperando
    assert pagina.evaluate("JSON.parse(localStorage.getItem('quempin_portal_errores_pendiente') || '[]')") == []
    assert [e for e in errores if "Falla de prueba" not in e] == []
    pagina.context.close()


def test_el_mismo_error_se_envia_una_vez_y_hay_un_tope_por_visita(navegador, sitio):
    pagina, _ = _portal_con_datos(navegador, sitio)
    pagina.evaluate("() => { for (let i = 0; i < 3; i++) setTimeout(() => { throw new Error('Siempre el mismo'); }); }")
    _observaciones_escritas(pagina, 1)
    pagina.wait_for_timeout(500)
    assert len(_observaciones_escritas(pagina, 1)) == 1
    # Una promesa rechazada también llega, como «promesa»
    _lanzar(pagina, "Promesa de prueba", promesa=True)
    tipos = sorted(m["tecnico"]["tipo"] for m in _observaciones_escritas(pagina, 2).values())
    assert tipos == ["error", "promesa"]
    # A lo más 5 por visita: van 2, se lanzan 6 distintos más
    for i in range(6):
        _lanzar(pagina, f"Distinto {i}")
    pagina.wait_for_timeout(1500)
    assert len(_observaciones_escritas(pagina, 5)) == 5
    pagina.context.close()


def test_el_ruido_conocido_no_se_envia(navegador, sitio):
    pagina, _ = _portal_con_datos(navegador, sitio)
    _lanzar(pagina, "ResizeObserver loop completed with undelivered notifications.")
    pagina.wait_for_timeout(800)
    assert _observaciones_escritas(pagina, 1, espera_ms=200) == {}
    pagina.context.close()


def test_sin_permiso_el_error_espera_y_sale_despues(navegador, sitio):
    pagina, _ = _portal_con_datos(navegador, sitio)
    pagina.evaluate("""() => {
        window.__permiso = 'prompt';
        FileSystemDirectoryHandle.prototype.queryPermission = async () => window.__permiso;
        FileSystemDirectoryHandle.prototype.requestPermission = async () => { throw new Error('no se pide sin un clic'); };
    }""")
    _lanzar(pagina, "Falla sin permiso")
    pagina.wait_for_function("() => JSON.parse(localStorage.getItem('quempin_portal_errores_pendiente') || '[]').length === 1")
    pagina.wait_for_timeout(500)
    assert _observaciones_escritas(pagina, 1, espera_ms=200) == {}
    # Con permiso, al volver a la pestaña sale
    pagina.evaluate("() => { window.__permiso = 'granted'; document.dispatchEvent(new Event('visibilitychange')); }")
    [m] = _observaciones_escritas(pagina, 1).values()
    assert "Falla sin permiso" in m["tecnico"]["mensaje"]
    pagina.wait_for_function("() => JSON.parse(localStorage.getItem('quempin_portal_errores_pendiente') || '[]').length === 0")
    pagina.context.close()


def test_un_error_del_arranque_sale_en_la_visita_siguiente(navegador, sitio):
    pagina, _ = _portal_con_datos(navegador, sitio)
    pagina.evaluate("""() => localStorage.setItem('quempin_portal_errores_arranque', JSON.stringify([
        { tipo: 'error', mensaje: 'Uncaught TypeError: falla del arranque', archivo: location.href, linea: 4600, columna: 3, pila: '' }]))""")
    pagina.reload()
    [m] = _observaciones_escritas(pagina, 1).values()
    assert m["donde"]["herramienta"] == "portal" and m["tecnico"]["linea"] == 4600
    assert "falla del arranque" in m["tecnico"]["mensaje"]
    assert pagina.evaluate("localStorage.getItem('quempin_portal_errores_arranque')") is None
    pagina.context.close()


def test_un_error_en_una_herramienta_llega_con_su_nombre_y_flujo_de_caja_sin_pila(navegador, sitio):
    pagina, _ = _portal_con_datos(navegador, sitio)
    _menu(pagina, "Centro de Costos")
    _lanzar(_marco(pagina, "centro-costos"), "Falla en el Centro de Costos")
    [cc] = _observaciones_escritas(pagina, 1).values()
    assert cc["donde"]["herramienta"] == "centro-costos" and "pila" in cc["tecnico"]
    assert cc["tecnico"]["firma"].startswith("centro-costos|")
    _menu(pagina, "Flujo de Caja")
    _lanzar(_marco(pagina, "flujo-caja", "fc"), "Falla en Flujo de Caja")
    [fc] = [m for m in _observaciones_escritas(pagina, 2).values() if m["donde"]["herramienta"] == "flujo-caja"]
    assert "pila" not in fc["tecnico"] and "#" not in fc["donde"].get("direccion", "")
    pagina.context.close()


def test_la_vista_muestra_los_automaticos_aparte_y_agrupados(navegador, sitio):
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="NB")
    pagina.evaluate(JS_ESCRIBIR_BUZON, [
        _obs_de_prueba("obsauto000001", "NB", "Error automático: x", "2026-11-18T09:00:00-03:00", automatico=True),
        _obs_de_prueba("obsauto000002", "ES", "Error automático: x", "2026-11-18T10:00:00-03:00", automatico=True),
        _obs_de_prueba("obsescrita003", "NB", "Una nota escrita por una persona", "2026-11-18T11:00:00-03:00"),
    ])
    _menu(pagina, "Errores y observaciones")
    pagina.locator("#obsLista .obs-fila:not(.obs-fila-vacia)").first.wait_for()
    assert pagina.locator("#obsLista .obs-fila").count() == 1
    assert "1 por revisar de 1 observación" in pagina.locator("#obsCuenta").inner_text()
    assert pagina.locator("#obsAuto").is_visible()
    assert pagina.locator("#obsAuto").evaluate("(d) => d.open") is False
    assert "1 error, 1 por revisar" in pagina.locator("#obsAutoResumen").inner_text()
    pagina.locator("#obsAutoResumen").click()
    fila = pagina.locator("#obsAutoLista .obs-fila")
    assert fila.count() == 1
    assert "visto 2 veces por 2 personas" in fila.inner_text()
    assert "/finanzas-quempin/portal/:812" in fila.locator(".obs-fila-tec").inner_text()
    assert fila.locator(".obs-retirar").count() == 0          # un automático no se retira
    assert not errores
    pagina.context.close()
