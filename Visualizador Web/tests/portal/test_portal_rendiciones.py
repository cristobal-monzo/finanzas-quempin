# -*- coding: utf-8 -*-
"""Portal QUEMPIN: Rendiciones.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ── Rendiciones (2026-11-18): lectura de cada boleta o factura, tabla, PDF y Centro de Costos ──────────────────────
# Textos inventados con la forma de lo que el OCR devolvió de boletas reales (con sus errores típicos: «N9» por «N°»,
# «Comprabante», «2026 10-14», el año «2076»). RUT de mentira con su dígito verificador correcto.


def test_rendiciones_lector_de_texto(navegador, sitio):
    """El lector de texto (solo calcula): tipo, N°, fecha, RUT del emisor (nunca el de QUEMPIN), proveedor, detalle y
    total, y marca como duda lo que no se lee seguro (el año imposible, lo que falta)."""
    pagina, errores = _abrir_portal(navegador, sitio)
    leer = lambda t: pagina.evaluate("t => window.QRendiciones.interpretar(t, { fuente: 'ocr', hoy: '2026-11-18' })", t)
    b = leer(RD_BOLETA)
    assert {k: b[k] for k in ("tipo", "numero", "fecha", "rut", "detalle", "valor")} == {
        "tipo": "Boleta", "numero": "1234567", "fecha": "2026-10-14", "rut": "76.111.111-6", "detalle": "Colación", "valor": 6190}
    assert b["proveedor"] == "Comidas Ejemplo Limitada" and "valor" not in b["dudas"]           # neto + IVA = total
    v = leer(RD_VOUCHER)
    assert {k: v[k] for k in ("tipo", "numero", "fecha", "rut", "proveedor", "detalle", "valor")} == {
        "tipo": "Boleta", "numero": "119", "fecha": "2026-09-11", "rut": "77.222.222-K", "proveedor": "Transportes Ejemplo Ltda.",
        "detalle": "Transporte", "valor": 2400}
    f = leer(RD_FACTURA)
    assert {k: f[k] for k in ("tipo", "numero", "fecha", "rut", "detalle", "valor")} == {
        "tipo": "Factura", "numero": "296581", "fecha": "2026-10-14", "rut": "76.111.111-6", "detalle": "Combustible", "valor": 70780}
    assert "fecha" in f["dudas"] and "valor" not in f["dudas"]      # «2076»: día y mes sirven, el año se revisa
    nada = leer("foto movida\nilegible")
    assert {"numero", "fecha", "valor"} <= set(nada["dudas"]) and nada["valor"] is None
    # Los PDF electrónicos traen el texto exacto: sin dudas por confianza del OCR
    assert pagina.evaluate("t => window.QRendiciones.interpretar(t, { fuente: 'pdf', hoy: '2026-11-18' }).dudas", RD_BOLETA) == []
    assert pagina.evaluate("['70.780', '$ 6.190', '104.832,00', '70780', 'abc'].map(window.QRendiciones.monto)") == [70780, 6190, 104832, 70780, None]
    # Lo que devuelve el lector con IA se normaliza igual y lo vacío queda en duda
    ia = pagina.evaluate("j => window.QRendiciones.deIA(j)", {"tipo": "Factura", "numero": "00045", "fecha": "2026-11-02", "valor": 1500.4, "dudas": ["rut", "x"]})
    assert ia["numero"] == "45" and ia["valor"] == 1500 and ia["dudas"] == ["rut"]
    assert not errores
    pagina.context.close()


def test_rendiciones_de_la_foto_al_pdf_y_al_centro_de_costos(navegador, sitio, tmp_path):
    import subprocess
    import sys

    pagina, errores = _portal_con_datos(navegador, sitio, usuario="LC")
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {"publicado/centro-costos-carpetas.json": _sobre("procesador", {"paises": {
        "CL": [{"nombre": "280. Obra de ejemplo", "req": "280", "documentos": 12}, {"nombre": "Gastos Generales", "req": None, "documentos": 3}],
        "PE": []}})})
    _rd_librerias(pagina)
    _menu(pagina, "Rendiciones")
    pagina.wait_for_function("() => document.querySelectorAll('#rdProyectos option').length >= 2")
    assert pagina.locator("#rdPdf").is_disabled() and pagina.locator("#rdEnviar").is_disabled()
    # La persona: por defecto, el nombre y apellido de quien usa el portal (el registro lleva «nombres»)
    assert pagina.locator("#rdDeudor").input_value() == "Lucas Contreras"
    assert pagina.locator("#rdPersonas option").count() == 7
    _rd_subir(pagina, [RD_FACTURA, RD_VOUCHER], ["factura bencina.png", "voucher.png"])
    filas = pagina.evaluate(JS_RD_FILAS)
    assert [f["numero"] for f in filas] == ["296581", "119"] and [f["valor"] for f in filas] == ["70.780", "2.400"]
    assert filas[0]["fecha"] == "2026-10-14" and "fecha" in filas[0]["dudas"] and filas[0]["lectura"] == "1 dato por revisar"
    assert pagina.locator("#rdTotal").inner_text() == "$ 73.180"
    assert pagina.locator("#rdPeriodo").input_value() == "Septiembre - Octubre 2026"
    # El proyecto, uno por documento: por su N° o su nombre, de la lista de carpetas
    fila = lambda i: pagina.locator("#rdFilas > tr").nth(i)
    assert "proyecto" in pagina.locator("#rdNotaEnviar").inner_text()
    fila(0).locator('[data-campo="proyecto"]').fill("280")
    fila(0).locator('[data-campo="proyecto"]').press("Tab")
    assert fila(0).locator('[data-campo="proyecto"]').input_value() == "280. Obra de ejemplo"
    fila(1).locator('[data-campo="proyecto"]').fill("gastos generales")
    fila(1).locator('[data-campo="proyecto"]').press("Tab")
    fila(1).locator('[data-campo="valor"]').fill("2.500")
    pagina.locator("#rdDeudor").fill("Persona de Ejemplo")
    assert pagina.locator("#rdTotal").inner_text() == "$ 73.280"

    # El PDF: resumen y una página con la foto de cada documento
    pagina.locator("#rdPdf").click()
    pagina.wait_for_function("() => window.__pdf && window.__pdf.guardado")
    pdf = pagina.evaluate("window.__pdf")
    assert pdf["paginas"] == 3 and pdf["fotos"] == 2, pdf
    assert pdf["guardado"].startswith("Recuperación de Gastos Persona de Ejemplo") and pdf["guardado"].endswith(".pdf")
    for t in ("Recuperación de Gastos", "Distribución por proyecto", "$ 73.280", "Firma Deudor", "Firma Director Proyecto", "Documento 2 de 2", "Página 3 de 3"):
        assert t in pdf["textos"], t

    # Enviar: con un dato en naranjo pide confirmar; después un documento-cc por proyecto, con «rendicion»
    pagina.locator("#rdEnviar").click()
    assert pagina.locator("#rdEnviar").inner_text().startswith("Enviar igual")
    pagina.locator("#rdEnviar").click()
    # Antes de enviar, el correo tal como saldrá (pedido del usuario, 2026-11-25); «Volver» no envía nada
    dlg = pagina.locator("#dlgRdCorreo")
    dlg.wait_for(state="visible")
    assert pagina.locator("#rdCorreoAsunto").inner_text().endswith("· Persona de Ejemplo · $ 73.280")
    assert pagina.locator("#rdCorreoPdf").inner_text().endswith(".pdf")
    cuerpo = pagina.frame_locator("#rdCorreoCuerpo").locator("body").inner_text()
    assert "período del 11-09-2026 al 14-10-2026" in cuerpo and "280. Obra de ejemplo: $ 70.780 (1 doc.)" in cuerpo, cuerpo
    dlg.get_by_role("button", name="Volver").click()
    dlg.wait_for(state="hidden")
    assert not pagina.locator("#rdEnviar").is_disabled() and pagina.locator("#rdCorreoCuerpo").count() == 0
    pagina.locator("#rdEnviar").click()
    dlg.wait_for(state="visible")
    dlg.get_by_role("button", name="Enviar", exact=True).click()
    pagina.locator("#rdEnvios .sc-pill", has_text="En camino").wait_for()
    assert pagina.locator("#rdEnviar").inner_text() == "Rendición enviada" and pagina.locator("#rdEnviar").is_disabled()
    leido = pagina.evaluate(JS_LEER_BUZON)
    assert len(leido["mensajes"]) == 2, list(leido["mensajes"])          # uno por proyecto: «Volver» no dejó nada
    mensajes = {json.loads(t)["carpeta"]: (n, json.loads(t)) for n, t in leido["mensajes"].items()}
    assert set(mensajes) == {"280. Obra de ejemplo", "Gastos Generales"}
    m280 = mensajes["280. Obra de ejemplo"][1]
    ren = m280["rendicion"]
    # El PDF de la rendición viaja con uno solo de los mensajes (va adjunto en el correo), aparte de los documentos
    con_pdf = [m for _, m in mensajes.values() if m["rendicion"].get("pdf")]
    assert len(con_pdf) == 1 and con_pdf[0]["rendicion"]["pdf"]["nombre"].endswith(".pdf")
    assert all(a["nombre"] != con_pdf[0]["rendicion"]["pdf"]["nombre"] for a in con_pdf[0]["archivos"])
    assert ren["tipo"] == "recuperacion" and ren["deudor"] == "Persona de Ejemplo" and ren["total"] == 73280 and ren["cantidad"] == 2
    assert ren["id"] == mensajes["Gastos Generales"][1]["rendicion"]["id"]
    [doc] = ren["documentos"]
    assert {k: doc[k] for k in ("n", "tipo", "numero", "fecha", "detalle", "valor", "rut")} == {
        "n": 1, "tipo": "Factura", "numero": "296581", "fecha": "14-10-2026", "detalle": "Combustible", "valor": 70780, "rut": "76.111.111-6"}
    assert m280["archivos"][0]["nombre"] == doc["archivo"] and doc["archivo"].endswith(" - 1 Factura 296581.png")
    assert m280["proyecto"] == {"req": "280"} and m280["origen"]["usuario"] == "LC"

    # Lo atiende el procesador real: copia cada documento a su carpeta y publica rendiciones.json
    raiz = tmp_path / "Intercambio"
    (raiz / "buzon").mkdir(parents=True)
    for nombre, msg in mensajes.values():
        (raiz / "buzon" / nombre).write_text(json.dumps(msg), encoding="utf-8")
    for ruta, datos in leido["adjuntos"].items():
        destino = raiz / "buzon" / "adjuntos" / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(bytes(datos))
    chile = tmp_path / "Facturas y Boletas" / "Chile"
    (chile / "280. Obra de ejemplo").mkdir(parents=True)
    (chile / "Gastos Generales").mkdir()
    salida = subprocess.run([sys.executable, "-c", "import json, sys, documentos_cc, intercambio; from pathlib import Path; "
                             "intercambio.asegurar_carpeta(Path(sys.argv[1])); "
                             "print(json.dumps(documentos_cc.atender(Path(sys.argv[1]), {'CL': Path(sys.argv[2])})))", str(raiz), str(chile)],
                            cwd=RAIZ / "Sistema Intercambio", capture_output=True, text=True, check=True).stdout
    assert json.loads(salida) == {"aplicados": 2, "archivos": 2, "esperan": 0, "rechazados": 0}
    pub = json.loads((raiz / "publicado" / "rendiciones.json").read_text(encoding="utf-8"))
    [r] = pub["datos"]["rendiciones"]
    assert [(d["carpeta"], d["numero"], d["valor"]) for d in r["documentos"]] == [("280. Obra de ejemplo", "296581", 70780), ("Gastos Generales", "119", 2500)]
    # El correo automático (con un remitente de prueba): persona, monto total y período del más antiguo al más reciente
    (tmp_path / "dest.json").write_text(json.dumps({"para": ["a@ejemplo.cl", "b@ejemplo.cl"]}), encoding="utf-8")
    correo = subprocess.run([sys.executable, "-c", "import json, sys, correo_rendiciones as cr; from pathlib import Path; "
                             "salida = []; "
                             "r = cr.ejecutar(Path(sys.argv[1]), remitente=lambda p, a, c, adj: salida.append([p, a, c, [x.read_bytes().decode() for x in adj]]) or 'enviado', "
                             "ruta_registro=Path(sys.argv[2]) / 'reg.json', ruta_destinatarios=Path(sys.argv[2]) / 'dest.json'); "
                             "print(json.dumps([r, salida]))", str(raiz), str(tmp_path)],
                            cwd=RAIZ / "Sistema Intercambio", capture_output=True, text=True, check=True).stdout
    resultado, [[para, asunto, cuerpo, adjuntos]] = json.loads(correo)
    assert adjuntos == ["%PDF-1.4 rendicion de prueba"]          # siempre con el PDF adjunto
    assert resultado["enviados"] == [r["numero"]] and para == ["a@ejemplo.cl", "b@ejemplo.cl"]
    assert asunto.endswith("· Persona de Ejemplo · $ 73.280") and "Correo automático generado" in cuerpo
    assert "período del 11-09-2026 al 14-10-2026" in cuerpo
    # La vista previa del Portal arma el mismo correo que el procesador: con esta rendición y con casos de borde
    otros = [dict(r, unidad="Obras <norte> & \"sur\"", deudor="  Ana   O'Brien "),
             dict(r, documentos=r["documentos"][:1], cantidad=2),                              # llegó uno de dos
             dict(r, documentos=[dict(d, fecha="") for d in r["documentos"]], periodo="Octubre 2026"),
             dict(r, tipo="vale", numero="", documentos=[dict(d, carpeta="A") for d in r["documentos"]])]
    _rd_correo_igual(pagina, [r] + otros)
    # El registro de rendiciones del Portal la muestra con su correo
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {"publicado/rendiciones.json": json.loads((raiz / "publicado" / "rendiciones.json").read_text(encoding="utf-8"))})
    _menu(pagina, "Rendiciones")                          # volver a mostrarla relee la carpeta
    pill = pagina.locator("#rdEnvios li").first.locator(".sc-pill")
    pill.filter(has_text="Correo enviado").wait_for()
    linea = pagina.locator("#rdEnvios li").first.inner_text()
    assert "Persona de Ejemplo" in linea and "$ 73.280" in linea and "gastos del 11-09-2026 al 14-10-2026" in linea, linea
    assert (chile / "Gastos Generales" / r["documentos"][1]["archivo"]).exists()
    assert not errores
    pagina.context.close()


def _rd_correo_igual(pagina, rendiciones):
    """QRendiciones.correo (la vista previa) y armar() de correo_rendiciones.py: mismo asunto y mismo HTML."""
    import re
    import subprocess
    import sys
    py = json.loads(subprocess.run([sys.executable, "-c", "import json, sys, correo_rendiciones as cr; "
                                    "print(json.dumps([cr.armar(r) for r in json.loads(sys.stdin.read())]))"],
                                   input=json.dumps(rendiciones), cwd=RAIZ / "Sistema Intercambio", capture_output=True,
                                   text=True, encoding="utf-8", check=True).stdout)
    js = pagina.evaluate("rs => rs.map((r) => { const c = window.QRendiciones.correo(r); return [c.asunto, c.cuerpo]; })", rendiciones)
    junta = lambda h: re.sub(r"\s+", " ", h).replace("> <", "><").strip()
    for (a_py, c_py), (a_js, c_js) in zip(py, js):
        assert a_js == a_py
        assert junta(c_js) == junta(c_py)


def test_rendiciones_sin_biblioteca_hace_el_pdf_y_se_guarda_en_el_navegador(navegador, sitio):
    """En el celular (sin la carpeta del equipo) se arma y descarga el PDF; enviar al Centro de Costos espera un
    computador. Lo que se lleva sigue ahí al volver a abrir el portal."""
    pagina, errores = _abrir_portal(navegador, sitio)
    _rd_librerias(pagina)
    _menu(pagina, "Rendiciones")
    _rd_subir(pagina, [RD_BOLETA], ["boleta.png"])
    assert not pagina.locator("#rdPdf").is_disabled() and pagina.locator("#rdEnviar").is_disabled()
    nota = pagina.locator("#rdNotaEnviar").inner_text()
    assert "Chrome o Edge" in nota or "conecta" in nota
    fila = pagina.locator("#rdFilas > tr").first
    fila.locator('[data-campo="proveedor"]').fill("Proveedor corregido")
    pagina.wait_for_timeout(700)          # se guarda en IndexedDB a los 400 ms
    pagina.reload()                       # la dirección (#/rendiciones) vuelve a abrir la vista
    pagina.locator("#vistaRendir").wait_for()
    pagina.wait_for_function("() => document.querySelectorAll('#rdFilas > tr').length === 1")
    [f] = pagina.evaluate(JS_RD_FILAS)
    assert f["numero"] == "1234567" and f["proveedor"] == "Proveedor corregido" and f["valor"] == "6.190"
    # Nueva rendición: pide confirmar (no se envió ni se descargó) y vacía la tabla
    pagina.locator("#rdNueva").click()
    assert pagina.locator("#rdFilas > tr").count() == 1
    pagina.locator("#rdNueva").click()
    assert pagina.locator("#rdFilas > tr").count() == 0 and pagina.locator("#rdTotal").inner_text() == "$ 0"
    assert not errores
    pagina.context.close()


def test_rendiciones_datos_en_naranjo_estan_bien_y_otra_boleta_de_la_misma_foto(navegador, sitio):
    """Observaciones de LC (2026-11-23): un dato en naranjo se da por bueno con «Están bien», sin cambiarlo y volver a
    ponerlo; y una foto con varias boletas suma filas a mano («+»), debajo de la suya, con la misma imagen y lo que se
    repite, sin volver a leerla."""
    pagina, errores = _abrir_portal(navegador, sitio)
    _rd_librerias(pagina)
    _menu(pagina, "Rendiciones")
    _rd_subir(pagina, [RD_FACTURA, RD_VOUCHER], ["factura.png", "voucher.png"])
    fila = lambda i: pagina.locator("#rdFilas > tr").nth(i)
    [f, _] = pagina.evaluate(JS_RD_FILAS)
    assert f["dudas"] == ["fecha"] and f["lectura"] == "1 dato por revisar"
    fila(0).locator(".rd-bien").click()
    [f, _] = pagina.evaluate(JS_RD_FILAS)
    assert f["dudas"] == [] and f["lectura"] == "Leído" and f["fecha"] == "2026-10-14"
    assert not fila(0).locator(".rd-bien").is_visible()
    # Otra boleta de la misma foto: queda justo debajo, con N° y valor por llenar (en naranjo, sin «Están bien»)
    fila(0).locator(".rd-otra").click()
    pagina.wait_for_function("() => document.querySelectorAll('#rdFilas > tr').length === 3")
    filas = pagina.evaluate(JS_RD_FILAS)
    assert [x["numero"] for x in filas] == ["296581", "", "119"]
    otra = filas[1]
    assert (otra["tipo"], otra["fecha"], otra["detalle"], otra["valor"]) == ("Factura", "2026-10-14", "Combustible", "")
    assert sorted(otra["dudas"]) == ["numero", "valor"] and not fila(1).locator(".rd-bien").is_visible()
    assert pagina.evaluate("document.activeElement.dataset.campo") == "numero"
    assert fila(1).locator(".rd-mini img").get_attribute("src") == fila(0).locator(".rd-mini img").get_attribute("src")
    fila(1).locator('[data-campo="numero"]').fill("296582")
    fila(1).locator('[data-campo="valor"]').fill("10.000")
    fila(1).locator('[data-campo="valor"]').press("Tab")
    assert pagina.locator("#rdTotal").inner_text() == "$ 83.180"
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [390, 1280])
def test_rendiciones_sin_desbordes(navegador, sitio, ancho):
    pagina, errores = _abrir_portal(navegador, sitio, ancho=ancho, alto=844, movil=ancho < 760)
    _rd_librerias(pagina)
    _menu(pagina, "Rendiciones")
    _rd_subir(pagina, [RD_FACTURA, RD_VOUCHER], ["factura.png", "voucher.png"])
    d = pagina.evaluate(JS_DESBORDES)
    assert d["doc"] <= ancho and not d["fuera"], d
    derecha = pagina.evaluate("""() => Math.max(...[...document.querySelectorAll('#vistaRendir *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))""")
    assert derecha <= ancho + 0.5, derecha
    if ancho < 760:   # en el teléfono, los campos a 16 px (el iPhone no hace zoom)
        assert pagina.evaluate("""() => Math.min(...[...document.querySelectorAll('#vistaRendir input, #vistaRendir select')]
            .filter((e) => e.getClientRects().length).map((e) => parseFloat(getComputedStyle(e).fontSize)))""") >= 16
    assert not errores
    pagina.context.close()
