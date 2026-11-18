# -*- coding: utf-8 -*-
"""Portal QUEMPIN: Subir documentos al Centro de Costos.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- Subir documentos al Centro de Costos (2026-10-23) ----------------------------------------------------------


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
