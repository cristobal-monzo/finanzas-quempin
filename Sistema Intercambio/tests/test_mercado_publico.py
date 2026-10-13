# -*- coding: utf-8 -*-
"""Monitor de licitaciones de Mercado Público: interpreta la API, sugiere solo
lo que Mercado Público prueba, no repite sugerencias, cuida el ticket y
respeta los límites de la API. Siempre con una API falsa (conftest corta la
red) y en tmp_path: nunca la carpeta real ni el ticket del equipo."""
import json
import os
import urllib.parse
from datetime import date

import pytest

import bandeja
import esquemas
import intercambio as ic
import mercado_publico as mp
import requerimientos as rq

TICKET = "A1B2C3D4-0000-1111-2222-333344445555"
HOY = date(2026, 10, 13)


# ── API falsa ────────────────────────────────────────────────────────────────

def _licitacion(codigo, estado=8, adjudicados=(("76.772.215-K", "QUEMPIN SPA", 1, 1000000),), **extra):
    items = [{"Correlativo": i + 1, "Adjudicacion": {"RutProveedor": rut, "NombreProveedor": nombre,
                                                   "Cantidad": cant, "MontoUnitario": unit}}
             for i, (rut, nombre, cant, unit) in enumerate(adjudicados)]
    return dict({"CodigoExterno": codigo, "Nombre": "Mantención de calderas", "CodigoEstado": estado,
                 "Estado": {8: "Adjudicada", 7: "Desierta", 6: "Cerrada", 5: "Publicada"}.get(estado, "Otro"),
                 "Moneda": "CLP", "Comprador": {"NombreOrganismo": "Hospital de ejemplo", "NombreUsuario": "Funcionaria X",
                                                "RutUsuario": "11.111.111-1"},
                 "Fechas": {"FechaCierre": "2026-09-15T11:00:00", "FechaAdjudicacion": "2026-09-30T12:26:03.083",
                            "FechaEstimadaAdjudicacion": "2026-09-30T16:46:00"},
                 "Adjudicacion": {"Fecha": "2026-09-30T00:00:00", "NumeroOferentes": 4,
                                  "UrlActa": "http://www.mercadopublico.cl/Procurement/acta.aspx?qs=abc"},
                 "Items": {"Cantidad": len(items), "Listado": items}}, **extra)


def _orden(codigo, licitacion="", nombre="OC", total_neto=1000000, rut="76.772.215-K", estado=6):
    return {"Codigo": codigo, "Nombre": nombre, "CodigoEstado": estado, "Estado": "Aceptada",
            "CodigoLicitacion": licitacion, "TipoMoneda": "CLP", "TotalNeto": total_neto,
            "Total": round(total_neto * 1.19), "Fechas": {"FechaEnvio": "2026-10-01T11:30:26.493"},
            "Comprador": {"NombreOrganismo": "Hospital de ejemplo", "NombreContacto": "Funcionaria X"},
            "Proveedor": {"Codigo": "1717812", "RutSucursal": rut}}


class ApiFalsa:
    """Responde por recurso y parámetro; anota cada URL pedida."""

    def __init__(self, licitaciones=None, ordenes_por_dia=None, ordenes=None):
        self.licitaciones = licitaciones or {}
        self.ordenes_por_dia = ordenes_por_dia or {}
        self.ordenes = ordenes or {}
        self.urls = []
        self.guion = []          # respuestas forzadas (código HTTP, dict) que se consumen primero

    def __call__(self, url, tiempo):
        self.urls.append(url)
        assert url.startswith("https://api.mercadopublico.cl/")
        if self.guion:
            codigo, cuerpo = self.guion.pop(0)
            return codigo, json.dumps(cuerpo).encode()
        partes = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(partes.query))
        if partes.path.endswith("licitaciones.json"):
            lic = self.licitaciones.get(q["codigo"])
            return 200, json.dumps({"Cantidad": int(bool(lic)), "Listado": [lic] if lic else []}).encode()
        if partes.path.endswith("ordenesdecompra.json") and "codigo" in q:
            oc = self.ordenes.get(q["codigo"])
            return 200, json.dumps({"Cantidad": int(bool(oc)), "Listado": [oc] if oc else []}).encode()
        if partes.path.endswith("ordenesdecompra.json"):
            lista = [{"Codigo": c, "CodigoEstado": self.ordenes[c]["CodigoEstado"]} for c in self.ordenes_por_dia.get(q["fecha"], [])]
            return 200, json.dumps({"Cantidad": len(lista), "Listado": lista}).encode()
        if "BuscarProveedor" in partes.path:
            return 200, json.dumps({"Cantidad": 1, "listaEmpresas": [{"CodigoEmpresa": "1717812", "NombreEmpresa": "QUEMPIN SPA"}]}).encode()
        raise AssertionError(url)


def _cliente(api, **kw):
    return mp.Cliente(TICKET, abrir=api, dormir=lambda s: None, **kw)


def _req(numero, estado="Ofertado", referencia="1234-56-LE26", **kw):
    return dict({"numero": numero, "estado": estado, "titulo": f"Req {numero}", "referencia": referencia,
                 "valorOfertado": 1100000, "valorAdjudicado": None}, **kw)


@pytest.fixture
def carpeta(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")

    def con_planilla(reqs):
        ic.publicar(raiz, rq.PUBLICACION, rq.HERRAMIENTA, {"requerimientos": reqs})
        return raiz
    return con_planilla


def _sugerencias(raiz):
    mensajes, invalidos = ic.leer_buzon(raiz, destino=rq.DESTINO, tipo=rq.TIPO_SUGERENCIA)
    assert invalidos == []
    return mensajes


# ── Interpretar ──────────────────────────────────────────────────────────────

def test_licitacion_ganada_suma_los_items_de_quempin_y_limpia_enlaces():
    crudo = _licitacion("1234-56-LE26", adjudicados=[("76.772.215-K", "QUEMPIN SPA", 2, 300000),
                                                    ("76772215-k", "QUEMPIN", 1, 400000),
                                                    ("99.999.999-9", "Otra SpA", 1, 50000)])
    lic = mp.leer_licitacion(crudo, "1234-56-LE26")
    assert lic["resultado"] == "ganada" and lic["montoQuempin"] == 1000000
    assert lic["urlActa"].startswith("https://www.mercadopublico.cl/")          # http -> https
    assert lic["url"].endswith("idlicitacion=1234-56-LE26")
    assert lic["oferentes"] == 4 and lic["fechaAdjudicacion"] == "2026-09-30T12:26"
    assert "Funcionaria" not in json.dumps(lic)                                  # sin datos de funcionarios


def test_licitacion_perdida_desierta_y_ausente():
    perdida = mp.leer_licitacion(_licitacion("1-2-LE26", adjudicados=[("99.999.999-9", "Otra SpA", 1, 900000)]), "1-2-LE26")
    assert perdida["resultado"] == "perdida" and perdida["adjudicados"][0]["montoNeto"] == 900000
    assert mp.leer_licitacion(_licitacion("1-2-LE26", estado=7, adjudicados=[]), "1-2-LE26")["resultado"] == "desierta"
    assert mp.leer_licitacion(None, "1-2-LE26")["resultado"] == "no-encontrada"
    assert mp.leer_licitacion(None, "4321-7-COT26")["resultado"] == "compra-agil"


def test_lo_que_responde_la_api_no_se_cree_a_ciegas():
    crudo = _licitacion("1-2-LE26", Nombre="Caldera\x00\x1b[31m  roja\n" + "x" * 500)
    crudo["Adjudicacion"]["UrlActa"] = "https://sitio-malo.example/acta"
    lic = mp.leer_licitacion(crudo, "1-2-LE26")
    assert lic["urlActa"] is None
    assert "\x00" not in lic["nombre"] and "\x1b" not in lic["nombre"] and len(lic["nombre"]) <= 160
    otra = _orden("1-9-SE26", rut="99.999.999-9")
    otra["Proveedor"]["Codigo"] = "555"
    assert mp.leer_orden(otra) is None                                           # OC de otro proveedor


def test_codigos_dentro_de_la_referencia_y_de_la_orden():
    assert mp.codigo_de("ID: 5555-39-le26 (ver bases)") == "5555-39-LE26"
    assert mp.codigo_de("trato directo") is None
    oc = mp.leer_orden(_orden("4321-11-AG26", nombre="Servicio de mantención a compra ágil: 4321-7-COT26"))
    assert oc["adquisicion"] == "4321-7-COT26" and oc["url"].endswith("codigoOC=4321-11-AG26")


# ── Decidir ──────────────────────────────────────────────────────────────────

def test_ganada_sugiere_adjudicado_con_iva():
    lic = mp.leer_licitacion(_licitacion("1234-56-LE26"), "1234-56-LE26")
    d = mp.decidir(_req(280), lic, [])
    assert d["cambios"] == {"estado": "Adjudicado", "valorAdjudicado": 1190000}
    assert "adjudicada a QUEMPIN" in d["motivo"] and "+ 19 % IVA" in d["motivo"]


def test_con_la_orden_de_compra_usa_su_total_real():
    lic = mp.leer_licitacion(_licitacion("1234-56-LE26"), "1234-56-LE26")
    oc = mp.leer_orden(_orden("1234-90-SE26", licitacion="1234-56-LE26"))
    oc["total"] = 1190001
    assert mp.decidir(_req(280), lic, [oc])["cambios"]["valorAdjudicado"] == 1190001


def test_planilla_adjudicada_sin_valor_solo_completa_el_valor():
    lic = mp.leer_licitacion(_licitacion("1234-56-LE26"), "1234-56-LE26")
    assert mp.decidir(_req(280, estado="Adjudicado"), lic, [])["cambios"] == {"valorAdjudicado": 1190000}
    assert mp.decidir(_req(280, estado="Adjudicado", valorAdjudicado=5), lic, [])["cambios"] is None   # no pisa


def test_perdida_sugiere_no_adjudicado_solo_si_estaba_ofertado():
    lic = mp.leer_licitacion(_licitacion("1-2-LE26", adjudicados=[("99.999.999-9", "Otra SpA", 1, 900000)]), "1-2-LE26")
    assert mp.decidir(_req(1), lic, [])["cambios"] == {"estado": "No adjudicado"}
    contradice = mp.decidir(_req(1, estado="Adjudicado"), lic, [])
    assert contradice["cambios"] is None and "Otra SpA" in contradice["revisar"]
    en_eval = mp.decidir(_req(1, estado="Evaluación"), lic, [])
    assert en_eval["cambios"] is None and "Descartado" in en_eval["revisar"]
    assert mp.decidir(_req(1, estado="Descartado"), lic, []) == {"cambios": None, "motivo": "", "revisar": None}


def test_en_evaluacion_no_sugiere_nada():
    lic = mp.leer_licitacion(_licitacion("1-2-LE26", estado=6, adjudicados=[]), "1-2-LE26")
    assert mp.decidir(_req(1), lic, [])["cambios"] is None


# ── Cliente ──────────────────────────────────────────────────────────────────

def test_reintenta_peticiones_simultaneas_con_espera_creciente():
    api = ApiFalsa(licitaciones={"1-2-LE26": _licitacion("1-2-LE26")})
    api.guion = [(500, {"Codigo": 10500, "Mensaje": "Lo sentimos. Hemos detectado que existen peticiones simultáneas."})]
    esperas = []
    c = mp.Cliente(TICKET, abrir=api, dormir=esperas.append, reloj=lambda: 0.0)
    assert c.licitacion("1-2-LE26")["CodigoExterno"] == "1-2-LE26"
    assert c.llamadas == 2 and esperas[0] == 2 * mp.PAUSA_SEG


def test_espacia_las_llamadas():
    api = ApiFalsa()
    esperas, t = [], [100.0]
    c = mp.Cliente(TICKET, abrir=api, dormir=esperas.append, reloj=lambda: t[0])
    c.licitacion("1-2-LE26")
    t[0] += 0.5
    c.licitacion("1-3-LE26")
    assert esperas == [pytest.approx(mp.PAUSA_SEG - 0.5)]


def test_ticket_rechazado_corta_y_nunca_aparece_en_mensajes():
    api = ApiFalsa()
    api.guion = [(203, {"Codigo": 203, "Mensaje": f"Ticket no válido {TICKET}"})]
    with pytest.raises(mp.TicketInvalido) as error:
        _cliente(api).licitacion("1-2-LE26")
    assert TICKET not in str(error.value)
    api.guion = [(500, {"Codigo": 999, "Mensaje": f"falla con {TICKET.lower()}"})]
    with pytest.raises(mp.ErrorMercadoPublico) as error:
        _cliente(api).licitacion("1-2-LE26")
    assert TICKET.lower() not in str(error.value) and "•••" in str(error.value)


def test_sin_conexion_no_filtra_el_ticket():
    def _cae(url, tiempo):
        raise OSError(f"no se pudo abrir {url}")
    with pytest.raises(mp.ErrorMercadoPublico) as error:
        mp.Cliente(TICKET, abrir=_cae, dormir=lambda s: None).licitacion("1-2-LE26")
    assert TICKET not in str(error.value)


def test_codigo_invalido_no_llega_a_la_url():
    api = ApiFalsa()
    for malo in ("1-2-LE26&ticket=otro", "../../x", "", "1-2-LE26 OR 1=1"):
        with pytest.raises(ValueError):
            _cliente(api).licitacion(malo)
    assert api.urls == []


def test_tope_de_llamadas_y_respuesta_gigante():
    api = ApiFalsa()
    c = _cliente(api, tope=1)
    c.licitacion("1-2-LE26")
    with pytest.raises(mp.TopeDeLlamadas):
        c.licitacion("1-3-LE26")
    grande = mp.Cliente(TICKET, abrir=lambda u, t: (200, b" " * (mp.MAX_BYTES_RESPUESTA + 1)), dormir=lambda s: None)
    with pytest.raises(mp.ErrorMercadoPublico):
        grande.licitacion("1-2-LE26")


# ── La vuelta completa ───────────────────────────────────────────────────────

def _api_tipica():
    return ApiFalsa(
        licitaciones={
            "1234-56-LE26": _licitacion("1234-56-LE26"),
            "1-2-LE26": _licitacion("1-2-LE26", adjudicados=[("99.999.999-9", "Otra SpA", 1, 900000)]),
            "7-7-LE26": _licitacion("7-7-LE26", estado=6, adjudicados=[]),
        },
        ordenes_por_dia={"01102026": ["1234-90-SE26", "4321-11-AG26"]},
        ordenes={"1234-90-SE26": _orden("1234-90-SE26", licitacion="1234-56-LE26"),
                 "4321-11-AG26": _orden("4321-11-AG26", nombre="a compra ágil: 4321-7-COT26", total_neto=400000)})


def test_vuelta_sugiere_publica_y_no_repite(carpeta, tmp_path):
    raiz = carpeta([_req(280), _req(281, referencia="1-2-LE26"), _req(282, referencia="7-7-LE26"),
                    _req(283, estado="Descartado", referencia="9-9-LE26"), _req(284, referencia="sin código")])
    api = _api_tipica()
    estado = tmp_path / "estado.json"
    r = mp.revisar(raiz, _cliente(api), ruta_estado=estado, hoy=HOY)

    assert {s["req"]: s["cambios"] for s in r["sugeridas"]} == {
        280: {"estado": "Adjudicado", "valorAdjudicado": 1190000}, 281: {"estado": "No adjudicado"}}
    assert not any("9-9-LE26" in u for u in api.urls)                      # Descartado no se consulta
    mensajes = _sugerencias(raiz)
    assert all(esquemas.validar_mensaje(m) == [] for m in mensajes)
    m280 = next(m for m in mensajes if m["requerimiento"]["numero"] == 280)
    assert m280["origen"]["herramienta"] == "mercado-publico" and m280["fuente"]["codigo"] == "1234-56-LE26"
    assert m280["reemplaza"] == {"estado": "Ofertado", "valorAdjudicado": None}
    assert "Mercado Público" in m280["fuente"]["motivo"]

    pub = ic.leer_publicacion(raiz, mp.PUBLICACION)
    assert esquemas.validar_publicacion(mp.PUBLICACION, pub) == []
    datos = pub["datos"]
    assert datos["resumen"]["ganadas"] == 1 and datos["resumen"]["perdidas"] == 1 and datos["resumen"]["tasaAdjudicacion"] == 0.5
    assert datos["ordenesSinRequerimiento"] == ["4321-11-AG26"]          # Compra Ágil sin fila en la planilla
    assert TICKET not in json.dumps(pub) and TICKET not in estado.read_text(encoding="utf-8")

    # Segunda vuelta: nada nuevo en el buzón, y lo ya resuelto no se vuelve a consultar.
    api.urls.clear()
    r2 = mp.revisar(raiz, _cliente(api), ruta_estado=estado, hoy=HOY)
    assert r2["sugeridas"] == [] and len(_sugerencias(raiz)) == 2
    assert not any("1234-56-LE26" in u or "1-2-LE26" in u for u in api.urls)
    assert any("7-7-LE26" in u for u in api.urls)                           # la que sigue en evaluación, sí


def test_sugerencia_descartada_no_vuelve(carpeta, tmp_path):
    raiz = carpeta([_req(281, referencia="1-2-LE26")])
    api, estado = _api_tipica(), tmp_path / "estado.json"
    mp.revisar(raiz, _cliente(api), ruta_estado=estado, hoy=HOY)
    (m,) = _sugerencias(raiz)
    assert rq.descartar_sugerencia(raiz, m["id"])
    mp.revisar(raiz, _cliente(api), ruta_estado=estado, hoy=HOY)
    assert _sugerencias(raiz) == []


def test_no_duplica_lo_que_ya_sugirio_el_formulador(carpeta, tmp_path):
    raiz = carpeta([_req(281, referencia="1-2-LE26")])
    ic.enviar(raiz, {"esquema": ic.ESQUEMA, "id": "formulador01", "tipo": rq.TIPO_SUGERENCIA, "destino": rq.DESTINO,
                     "origen": {"herramienta": "formulador", "enviado": "2026-10-10T10:00:00-03:00"},
                     "requerimiento": {"numero": 281}, "cambios": {"estado": "No adjudicado"},
                     "fuente": {"herramienta": "formulador"}})
    r = mp.revisar(raiz, _cliente(_api_tipica()), ruta_estado=tmp_path / "e.json", hoy=HOY)
    assert r["sugeridas"] == [] and [m["id"] for m in _sugerencias(raiz)] == ["formulador01"]


def test_status_no_escribe_en_la_carpeta(carpeta, tmp_path):
    raiz = carpeta([_req(280)])
    r = mp.revisar(raiz, _cliente(_api_tipica()), enviar=False, ruta_estado=tmp_path / "e.json", hoy=HOY)
    assert r["sugeridas"] and _sugerencias(raiz) == []
    assert ic.leer_publicacion(raiz, mp.PUBLICACION) is None


def test_orden_de_compra_de_compra_agil_prueba_la_adjudicacion(carpeta, tmp_path):
    raiz = carpeta([_req(290, referencia="4321-7-COT26")])
    r = mp.revisar(raiz, _cliente(_api_tipica()), ruta_estado=tmp_path / "e.json", hoy=HOY)
    assert r["sugeridas"] == [{"req": 290, "codigo": "4321-7-COT26",
                               "cambios": {"estado": "Adjudicado", "valorAdjudicado": round(400000 * 1.19)}}]
    fila = ic.leer_publicacion(raiz, mp.PUBLICACION)["datos"]["licitaciones"][0]
    assert fila["resultado"] == "ganada" and fila["ordenes"] == ["4321-11-AG26"]


def test_tope_deja_la_vuelta_incompleta_y_sigue_despues(carpeta, tmp_path):
    raiz = carpeta([_req(280)])
    api, estado = _api_tipica(), tmp_path / "e.json"
    r = mp.revisar(raiz, _cliente(api, tope=5), ruta_estado=estado, hoy=HOY)
    assert r["incompleta"] and ic.leer_publicacion(raiz, mp.PUBLICACION)["datos"]["completo"] is False
    hechos = len(json.loads(estado.read_text(encoding="utf-8"))["diasBarridos"])
    mp.revisar(raiz, _cliente(api, tope=500), ruta_estado=estado, hoy=HOY)
    assert len(json.loads(estado.read_text(encoding="utf-8"))["diasBarridos"]) > hechos


def test_la_sugerencia_la_entiende_la_planilla(carpeta, tmp_path):
    raiz = carpeta([_req(280)])
    mp.revisar(raiz, _cliente(_api_tipica()), ruta_estado=tmp_path / "e.json", hoy=HOY)
    (d,) = rq.revisar_sugerencias(raiz, [_req(280)], archivar=False)
    assert d["accion"] == "pendiente" and any("Adjudicado" in linea for linea in d["detalle"])
    (d,) = rq.revisar_sugerencias(raiz, [_req(280, estado="Adjudicado", valorAdjudicado=1190000)])
    assert d["accion"] == "aplicado"                                          # pasada a mano: se cierra sola


def test_bandeja_muestra_lo_que_necesita_una_persona():
    datos = {"revisar": [{"req": 281, "codigo": "1-2-LE26", "texto": "La planilla dice «Adjudicado», pero…"}],
             "ordenes": [{"codigo": "4321-11-AG26", "comprador": "Organismo de ejemplo", "url": "https://www.mercadopublico.cl/x"}],
             "ordenesSinRequerimiento": ["4321-11-AG26"]}
    textos = [p.texto for p in bandeja.desde_licitaciones(datos)]
    assert any("N° 281" in t for t in textos) and any("4321-11-AG26 (Organismo de ejemplo)" in t for t in textos)
    assert bandeja.desde_licitaciones(None) == []


# ── Ticket ───────────────────────────────────────────────────────────────────

def test_sin_ticket_dice_como_configurarlo():
    with pytest.raises(mp.SinTicket, match="configurar"):
        mp.leer_ticket()


def test_ticket_por_variable_de_entorno_se_valida(monkeypatch):
    monkeypatch.setenv(mp.VARIABLE_TICKET, TICKET.lower())
    assert mp.leer_ticket() == TICKET
    monkeypatch.setenv(mp.VARIABLE_TICKET, "no-es-un-ticket")
    with pytest.raises(mp.SinTicket):
        mp.leer_ticket()


@pytest.mark.skipif(os.name != "nt", reason="DPAPI es de Windows")
def test_ticket_guardado_cifrado(tmp_path):
    ruta = tmp_path / "mp.ticket"
    mp.guardar_ticket(TICKET.lower(), ruta)
    assert TICKET.encode() not in ruta.read_bytes() and TICKET.lower().encode() not in ruta.read_bytes()
    assert mp.leer_ticket(ruta) == TICKET
    ruta.write_bytes(b"basura")
    with pytest.raises(mp.ErrorMercadoPublico):
        mp.leer_ticket(ruta)
    assert mp.olvidar_ticket(ruta) and not ruta.exists()
    with pytest.raises(ValueError):
        mp.guardar_ticket("123", ruta)


def test_sin_la_licitacion_no_sugiere_montos_de_ordenes_parciales(carpeta, tmp_path):
    """Contrato de mantención: el acta es el total y cada OC una entrega mensual."""
    api = _api_tipica()
    api.licitaciones["1234-56-LE26"] = _licitacion("1234-56-LE26", adjudicados=[("76.772.215-K", "QUEMPIN SPA", 12, 500000)])
    raiz = carpeta([_req(280, estado="Adjudicado")])       # ya cerrada: su licitación va al final de la vuelta
    estado = tmp_path / "e.json"
    # El tope alcanza para barrer las OC (60 días + 2 detalles) pero no para la licitación.
    r = mp.revisar(raiz, _cliente(api, tope=mp.DIAS_HISTORIA_OC + 2), ruta_estado=estado, hoy=HOY)
    assert r["incompleta"] and _sugerencias(raiz) == []
    assert "1234-90-SE26" in json.loads(estado.read_text(encoding="utf-8"))["ordenes"]
    mp.revisar(raiz, _cliente(api), ruta_estado=estado, hoy=HOY)
    (m,) = _sugerencias(raiz)
    assert m["cambios"]["valorAdjudicado"] == round(6000000 * 1.19)                # el acta, no la OC de 1.000.000


def test_dato_nuevo_reemplaza_la_sugerencia_anterior_del_monitor(carpeta, tmp_path):
    api, estado = _api_tipica(), tmp_path / "e.json"
    raiz = carpeta([_req(280)])
    mp.revisar(raiz, _cliente(api), ruta_estado=estado, hoy=HOY)
    (viejo,) = _sugerencias(raiz)
    datos = json.loads(estado.read_text(encoding="utf-8"))
    datos["licitaciones"]["1234-56-LE26"]["_consultado"] = "2000-01-01T00:00:00"      # vencida: se vuelve a consultar
    estado.write_text(json.dumps(datos), encoding="utf-8")
    api.licitaciones["1234-56-LE26"] = _licitacion("1234-56-LE26", adjudicados=[("76.772.215-K", "QUEMPIN SPA", 1, 2000000)])
    mp.revisar(raiz, _cliente(api), ruta_estado=estado, hoy=HOY)
    (nuevo,) = _sugerencias(raiz)
    assert nuevo["id"] != viejo["id"] and nuevo["cambios"]["valorAdjudicado"] == 2380000
    assert ic.resultados_recientes(raiz)[viejo["id"]]["estado"] == "reemplazado"
