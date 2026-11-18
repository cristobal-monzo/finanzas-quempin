"""El correo automático de cada rendición (2026-11-18): una vez, completa, con persona, monto y período."""
import json
from datetime import datetime, timedelta, timezone

CHILE = timezone(timedelta(hours=-3))      # la hora de los envíos de ejemplo: la prueba vale en cualquier equipo (el CI va en UTC)

import correo_rendiciones as cr
import intercambio


def _ren(**cambios):
    r = {"id": "a1b2c3d4e5f6", "numero": "R-20261118-1000-NB", "tipo": "recuperacion", "deudor": "  Nicolás   Becker ",
         "total": 73280, "cantidad": 2, "usuario": "NB", "enviado": "2026-11-18T10:00:00-03:00",
         "pdf": "rendiciones/R-20261118-1000-NB.pdf",
         "documentos": [
             {"pais": "CL", "carpeta": "280. Obra de ejemplo", "archivo": "a.jpg", "mensaje": "m1", "n": 1, "tipo": "Factura",
              "numero": "296581", "fecha": "14-10-2026", "valor": 70780},
             {"pais": "CL", "carpeta": "Gastos Generales", "archivo": "b.jpg", "mensaje": "m2", "n": 2, "tipo": "Comprobante",
              "numero": "119", "fecha": "11-09-2026", "valor": 2500}]}
    r.update(cambios)
    return r


def _raiz(tmp_path, lista, con_pdf=True):
    raiz = tmp_path / "Intercambio"
    intercambio.asegurar_carpeta(raiz)
    intercambio.publicar(raiz, "rendiciones", "procesador", {"rendiciones": lista})
    if con_pdf:
        (raiz / "publicado" / "rendiciones").mkdir(parents=True, exist_ok=True)
        (raiz / "publicado" / "rendiciones" / "R-20261118-1000-NB.pdf").write_bytes(b"%PDF-1.4 de prueba")
    return raiz


def test_el_correo_dice_persona_monto_y_periodo():
    asunto, cuerpo = cr.armar(_ren())
    assert asunto == "Rendición de gastos R-20261118-1000-NB · Nicolás Becker · $ 73.280"
    assert "Correo automático generado para la rendición de gastos de <b>Nicolás Becker</b>" in cuerpo
    assert "monto total de <b>$ 73.280</b>" in cuerpo
    assert "período del 11-09-2026 al 14-10-2026" in cuerpo          # del más antiguo al más reciente
    assert "280. Obra de ejemplo: $ 70.780 (1 doc.)" in cuerpo and "Llegaron" not in cuerpo
    # Lo escrito a mano va escapado
    _, cuerpo = cr.armar(_ren(deudor="Ana <b>Pérez</b>"))
    assert "&lt;b&gt;" in cuerpo


def test_se_envia_una_sola_vez_y_queda_en_el_registro(tmp_path):
    raiz = _raiz(tmp_path, [_ren()])
    (tmp_path / "dest.json").write_text(json.dumps({"para": ["a@ejemplo.cl", "no-es-correo", "b@ejemplo.cl"]}), encoding="utf-8")
    enviados = []
    remitente = lambda para, asunto, cuerpo, adjuntos: enviados.append((para, asunto, adjuntos)) or "enviado"
    kw = dict(remitente=remitente, ahora=datetime(2026, 11, 18, 10, 30, tzinfo=CHILE), ruta_registro=tmp_path / "reg.json",
              ruta_destinatarios=tmp_path / "dest.json")
    r = cr.ejecutar(raiz, **kw)
    assert r["enviados"] == ["R-20261118-1000-NB"] and enviados[0][0] == ["a@ejemplo.cl", "b@ejemplo.cl"]
    # Siempre con el PDF de la rendición adjunto (pedido del usuario: para la revisión de quien lo recibe)
    [adjunto] = enviados[0][2]
    assert adjunto.name == "R-20261118-1000-NB.pdf" and adjunto.read_bytes().startswith(b"%PDF")
    [ren] = intercambio.leer_publicacion(raiz, "rendiciones")["datos"]["rendiciones"]
    assert ren["correo"]["estado"] == "enviado" and ren["correo"]["para"] == ["a@ejemplo.cl", "b@ejemplo.cl"]
    assert ren["correo"]["adjunto"] == "R-20261118-1000-NB.pdf"
    assert cr.ejecutar(raiz, **kw)["enviados"] == [] and len(enviados) == 1


def test_espera_los_documentos_que_faltan_y_despues_sale_con_lo_que_llego(tmp_path):
    incompleta = _ren(cantidad=3)
    (tmp_path / "dest.json").write_text(json.dumps({"para": ["a@ejemplo.cl"]}), encoding="utf-8")
    cuerpos = []
    kw = dict(remitente=lambda p, a, c, adj: cuerpos.append(c) or "bandeja-de-salida", ruta_registro=tmp_path / "reg.json",
              ruta_destinatarios=tmp_path / "dest.json")
    raiz = _raiz(tmp_path, [incompleta])
    r = cr.ejecutar(raiz, ahora=datetime(2026, 11, 18, 10, 30, tzinfo=CHILE), **kw)
    assert r["enviados"] == [] and r["esperan"] == ["R-20261118-1000-NB"]
    r = cr.ejecutar(raiz, ahora=datetime(2026, 11, 18, 12, 30, tzinfo=CHILE), **kw)
    assert r["enviados"] == ["R-20261118-1000-NB"] and "Llegaron 2 de 3 documentos" in cuerpos[0]


def test_lo_antiguo_no_genera_correo_y_un_error_se_reintenta(tmp_path):
    (tmp_path / "dest.json").write_text(json.dumps({"para": ["a@ejemplo.cl"]}), encoding="utf-8")
    raiz = _raiz(tmp_path, [_ren(enviado="2026-10-01T10:00:00-03:00")])
    kw = dict(ahora=datetime(2026, 11, 18, 10, 30, tzinfo=CHILE), ruta_registro=tmp_path / "reg.json", ruta_destinatarios=tmp_path / "dest.json")
    assert cr.ejecutar(raiz, remitente=lambda *a: "enviado", **kw)["enviados"] == []

    raiz = _raiz(tmp_path / "b", [_ren()])
    def falla(*a):
        raise cr.ErrorCorreo("Outlook cerrado")
    r = cr.ejecutar(raiz, remitente=falla, **kw)
    assert r["errores"] == ["R-20261118-1000-NB: Outlook cerrado"]
    assert "correo" not in intercambio.leer_publicacion(raiz, "rendiciones")["datos"]["rendiciones"][0]
    assert cr.ejecutar(raiz, remitente=lambda *a: "enviado", **kw)["enviados"] == ["R-20261118-1000-NB"]


def test_sin_destinatarios_no_envia_y_lo_dice(tmp_path):
    raiz = _raiz(tmp_path, [_ren()])
    r = cr.ejecutar(raiz, remitente=lambda *a: "enviado", ahora=datetime(2026, 11, 18, 10, 30, tzinfo=CHILE),
                    ruta_registro=tmp_path / "reg.json", ruta_destinatarios=tmp_path / "no-existe.json")
    assert r["enviados"] == [] and "sin destinatarios" in r["errores"][0]


def test_sin_pdf_el_correo_nunca_sale(tmp_path):
    """El correo siempre lleva el PDF: sin él espera, y a las 2 horas el paso falla y lo dice."""
    (tmp_path / "dest.json").write_text(json.dumps({"para": ["a@ejemplo.cl"]}), encoding="utf-8")
    raiz = _raiz(tmp_path, [_ren()], con_pdf=False)
    enviados = []
    kw = dict(remitente=lambda *a: enviados.append(a) or "enviado", ruta_registro=tmp_path / "reg.json",
              ruta_destinatarios=tmp_path / "dest.json")
    r = cr.ejecutar(raiz, ahora=datetime(2026, 11, 18, 10, 30, tzinfo=CHILE), **kw)
    assert r["esperan"] == ["R-20261118-1000-NB"] and not r["errores"]
    r = cr.ejecutar(raiz, ahora=datetime(2026, 11, 18, 12, 30, tzinfo=CHILE), **kw)
    assert r["enviados"] == [] and "no llegó su PDF" in r["errores"][0] and not enviados
    # Una rendición antigua, sin «pdf» en el registro, tampoco sale sin él
    raiz = _raiz(tmp_path / "b", [{k: v for k, v in _ren().items() if k != "pdf"}])
    assert cr.ejecutar(raiz, ahora=datetime(2026, 11, 18, 12, 30, tzinfo=CHILE), **kw)["enviados"] == [] and not enviados


def test_el_correo_dice_que_lleva_el_pdf():
    _, cuerpo = cr.armar(_ren())
    assert "Se adjunta el PDF de la rendición para su revisión" in cuerpo


def test_outlook_no_recibe_un_correo_sin_su_adjunto(tmp_path, monkeypatch):
    import alertas_oportunidades as ao
    monkeypatch.undo()                      # la de verdad, pero sin llegar a Outlook: falta el archivo
    try:
        ao.entregar_outlook(["a@ejemplo.cl"], "x", "y", [tmp_path / "no-existe.pdf"])
    except ao.ErrorCorreo as error:
        assert "no está el adjunto" in str(error)
    else:
        raise AssertionError("debía negarse")
