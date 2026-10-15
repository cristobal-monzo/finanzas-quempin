# -*- coding: utf-8 -*-
"""Compras ágiles en la evaluación de oportunidades y el correo de alertas
(2026-10-14). Siempre con APIs falsas (conftest corta la red y el envío por
Outlook) y en tmp_path; los datos son ficticios."""
import json
import urllib.parse
from datetime import datetime, timedelta

import pytest

import alertas_oportunidades as al
import compra_agil as ca
import esquemas
import intercambio as ic
import mercado_publico as mp
import oportunidades as op

TICKET = "A1B2C3D4-0000-1111-2222-333344445555"
AHORA = datetime(2026, 10, 13, 10, 0)


def _req(numero, titulo, estado, referencia, **kw):
    return dict({"numero": numero, "estado": estado, "titulo": titulo, "referencia": referencia}, **kw)


HISTORIA = [
    _req(1, "Mantención preventiva caldera hospital", "Adjudicado", "5000-1-LE26", valorOfertado=8_000_000),
    _req(2, "Mantención calderas y red de calefacción", "No adjudicado", "5001-2-LE26", valorOfertado=15_000_000),
    _req(3, "Reparación caldera agua caliente", "Adjudicado", "5002-3-LE26", valorOfertado=4_000_000),
    _req(4, "Mantención caldera escuela", "Ofertado", "5003-4-LE26", valorOfertado=20_000_000),
    _req(5, "Mantención aire acondicionado oficinas", "Descartado", "5004-5-LE26"),
    _req(9, "Revisión y pruebas a caldera", "No adjudicado", "5008-9-COT26", valorOfertado=500_000),
]


def _ficha(codigo, nombre, cierre="2026-10-25T15:00:00"):
    """Una licitación (API v1) mínima."""
    return {"CodigoExterno": codigo, "Nombre": nombre, "CodigoEstado": 5, "Descripcion": "", "Tipo": "LE", "Moneda": "CLP",
            "Comprador": {"NombreOrganismo": "Servicio de ejemplo", "ComunaUnidad": "Quilpué", "RegionUnidad": "Región de Valparaíso"},
            "Fechas": {"FechaPublicacion": "2026-10-10T10:00:00", "FechaCierre": cierre}, "VisibilidadMonto": 1,
            "MontoEstimado": 10_000_000, "TiempoDuracionContrato": "12", "UnidadTiempoDuracionContrato": 4,
            "Items": {"Listado": [{"NombreProducto": "Servicio de mantención"}]}}


class ApiFalsa:
    """La API de licitaciones (v1): el listado de activas y cada ficha."""
    def __init__(self, fichas=()):
        self.fichas = {f["CodigoExterno"]: f for f in fichas}

    def __call__(self, url, tiempo):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        if q.get("estado") == "activas":
            lista = [{"CodigoExterno": c, "Nombre": f["Nombre"], "CodigoEstado": 5, "FechaCierre": f["Fechas"]["FechaCierre"]}
                     for c, f in self.fichas.items()]
            return 200, json.dumps({"Cantidad": len(lista), "Listado": lista}).encode()
        if "codigo" in q:
            f = self.fichas.get(q["codigo"])
            return 200, json.dumps({"Cantidad": int(bool(f)), "Listado": [f] if f else []}).encode()
        return 200, json.dumps({"Cantidad": 0, "Listado": []}).encode()     # historial de mercado: vacío


def _cliente(api, tope=80):
    return mp.Cliente(TICKET, abrir=api, dormir=lambda s: None, tope=tope)


# ── API de Compra Ágil falsa ─────────────────────────────────────────────────

def _ca(codigo, nombre, monto=2_000_000, cierre="2026-10-15 18:00", region="Región de Valparaíso ",
        descripcion="", plazo=10, cambio="2026-10-13T09:00:00.000Z", estado="publicada"):
    return {
        "codigo": codigo, "nombre": nombre, "descripcion": descripcion,
        "estado": {"id_estado": 2, "codigo": estado, "glosa": "Publicada"},
        "convocatoria": {"estado_convocatoria": 1, "descripcion": "Primer llamado"},
        "fechas": {"fecha_publicacion": "2026-10-13 09:00", "fecha_cierre": cierre, "fecha_ultimo_cambio": cambio},
        "entrega": {"direccion_entrega": "Calle 1", "plazo_entrega_dias": plazo},
        "presupuesto": {"tipo_presupuesto": "Disponible", "moneda": "CLP", "monto_disponible_clp": monto},
        "montos": {"moneda": "CLP", "monto_disponible_clp": monto},
        "institucion": {"organismo_comprador": "Servicio de ejemplo", "rut": "61.000.000-0",
                        "unidad_compra": "Abastecimiento", "region": 5, "nombre_region": region},
        "productos_solicitados": [{"codigo_producto": 1, "nombre": "Mantenimiento de calderas", "descripcion": "según bases", "cantidad": 1}],
        "proveedores_cotizando": [], "resumen": {"total_ofertas_recibidas": 0},
    }


class ApiCaFalsa:
    def __init__(self, compras=(), fallan=(), status=None):
        self.compras = {c["codigo"]: c for c in compras}
        self.fallan, self.status = set(fallan), status
        self.urls, self.encabezados = [], []

    def __call__(self, url, tiempo, encabezados):
        self.urls.append(url)
        self.encabezados.append(encabezados)
        assert url.startswith(ca.API)
        if self.status:
            return self.status, json.dumps({"success": "NOK", "payload": None, "errors": [{"codigo": str(self.status), "mensaje": "x"}]}).encode()
        partes = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(partes.query))
        if partes.path.endswith("/compra-agil"):
            if q["q"] in self.fallan:
                return 504, b"<html>timeout</html>"
            # Como la API real: busca en el nombre y en la descripción.
            items = [c for c in self.compras.values() if q["q"].lower() in (c["nombre"] + " " + c["descripcion"]).lower()]
            return 200, json.dumps({"success": "OK", "payload": {"items": items, "paginacion": {
                "total_paginas": 1, "numero_pagina": 1, "tamano_pagina": len(items), "total_resultados": len(items)}}}).encode()
        codigo = urllib.parse.unquote(partes.path.rsplit("/", 1)[-1])
        if codigo not in self.compras:
            return 404, json.dumps({"success": "NOK", "payload": None, "errors": [{"codigo": "404"}]}).encode()
        return 200, json.dumps({"success": "OK", "payload": self.compras[codigo]}).encode()


def _cliente_ca(api, tope=50):
    return ca.Cliente(TICKET, abrir=api, dormir=lambda s: None, tope=tope)


@pytest.fixture
def config():
    c = op.cargar_config()
    c["compraAgil"]["busquedas"] = ["caldera", "calefacción"]
    return c


# ── cliente y ficha ──────────────────────────────────────────────────────────

def test_el_ticket_va_en_el_header_y_nunca_en_la_url():
    api = ApiCaFalsa([_ca("100-1-COT26", "Mantención caldera")])
    cli = _cliente_ca(api)
    assert [x["codigo"] for x in cli.buscar("caldera")] == ["100-1-COT26"]
    assert cli.detalle("100-1-COT26")["codigo"] == "100-1-COT26"
    assert cli.detalle("100-9-COT26") is None                      # 404: no existe
    assert all(TICKET not in u for u in api.urls) and all(e == {"ticket": TICKET} for e in api.encabezados)
    with pytest.raises(ValueError):
        cli.detalle("100-1-COT26/../x")


@pytest.mark.parametrize("status,error", [(429, ca.CuotaAgotada), (401, mp.TicketInvalido), (403, mp.TicketInvalido)])
def test_cuota_agotada_y_ticket_rechazado_cortan(status, error):
    with pytest.raises(error):
        _cliente_ca(ApiCaFalsa(status=status)).buscar("caldera")


def test_la_ficha_de_una_compra_agil_queda_como_la_de_una_licitacion():
    crudo = _ca("100-1-COT26", "Mantención caldera", cierre="2026-10-15 18:00", plazo=25,
                descripcion="Consultas a juan.perez@ejemplo.cl o fono: +56 9 1234 5678")
    f = ca.leer_ficha(crudo, "100-1-COT26")
    assert f["compraAgil"] and f["tipo"] == "COT" and f["cierre"] == "2026-10-15T18:00"
    assert f["montoEstimado"] == 2_000_000 and f["duracion"] == 25 and f["unidadDuracion"] == 2
    assert "ejemplo.cl" not in f["descripcion"] and "1234" not in f["descripcion"]
    assert ca.fecha("2026-10-19T08:00:00Z") == "2026-10-19T08:00"      # la «Z» de la API es hora de Chile


# ── en la evaluación ─────────────────────────────────────────────────────────

def _revisar(tmp_path, config, compras, licitaciones=(), ahora=AHORA, **kw):
    return op.revisar(None, cliente=_cliente(ApiFalsa(licitaciones)), enviar=False, ruta_estado=tmp_path / "estado.json",
                      config=config, ahora=ahora, reqs=HISTORIA, cliente_ca=_cliente_ca(ApiCaFalsa(compras, **kw)))


def test_las_compras_agiles_se_evaluan_junto_a_las_licitaciones(tmp_path, config):
    r = _revisar(tmp_path, config, [_ca("100-1-COT26", "Mantención preventiva caldera escuela"),
                                    _ca("100-2-COT26", "Compra de resmas de papel", descripcion="para la oficina junto a la caldera")],
                 licitaciones=[_ficha("5100-1-LE26", "Mantención de calderas")])
    ops = {o["codigo"]: o for o in r["datos"]["oportunidades"]}
    assert set(ops) == {"5100-1-LE26", "100-1-COT26"}                # el prefiltro saca la de resmas
    o = ops["100-1-COT26"]
    assert o["compraAgil"] and o["url"] == ca.FICHA + "100-1-COT26" and o["ficha"]
    assert r["datos"]["reglas"]["plazoOfertaCompraAgil"] == config["compraAgil"]["plazoOferta"]["tramos"]
    sobre = {"esquema": ic.ESQUEMA, "herramienta": op.HERRAMIENTA, "generado": ic.ahora_iso(), "datos": r["datos"]}
    assert esquemas.validar_publicacion(op.PUBLICACION, sobre) == []


def test_sin_cliente_de_compra_agil_no_se_consulta(tmp_path, config):
    r = op.revisar(None, cliente=_cliente(ApiFalsa([_ficha("5100-1-LE26", "Mantención de calderas")])), enviar=False,
                   ruta_estado=tmp_path / "e.json", config=config, ahora=AHORA, reqs=HISTORIA)
    assert [o["codigo"] for o in r["datos"]["oportunidades"]] == ["5100-1-LE26"]


def test_una_compra_agil_se_cotiza_en_horas(tmp_path, config):
    # Cierra en 8 horas: una licitación se descartaría (menos de un día); una compra ágil no.
    r = _revisar(tmp_path, config, [_ca("100-1-COT26", "Mantención caldera", cierre="2026-10-13 18:00"),
                                    _ca("100-2-COT26", "Reparación caldera", cierre="2026-10-13 14:00")])
    ops = {o["codigo"]: o for o in r["datos"]["oportunidades"]}
    assert ops["100-1-COT26"]["categoria"] != "descartar"
    assert ops["100-1-COT26"]["criterios"]["plazoOferta"]["corto"] == "Cierra en 8 horas"
    assert ops["100-2-COT26"]["descartar"] == ["Cierra en menos de 6 horas"]


def test_el_monto_de_una_compra_agil_se_compara_con_las_compras_agiles(config):
    historia = HISTORIA + [{"numero": 20 + i, "estado": "No adjudicado", "titulo": f"Mantención caldera {i}",
                            "referencia": f"77{i}-1-COT26", "valorOfertado": 1_500_000 + 100_000 * i} for i in range(10)]
    ev = op.Evaluador(config, op.Historia(historia), [], AHORA, 40000)
    assert ev.rango_ca["p90"] < 3_000_000 < ev.rango["p10"] * 10
    r = ev.evaluar(ca.leer_ficha(_ca("100-1-COT26", "Mantención caldera", monto=2_000_000), "100-1-COT26"))
    assert r["criterios"]["monto"]["puntaje"] >= 85                 # al lado de las licitaciones sería «más chico que lo habitual»


def test_la_visita_se_lee_en_la_descripcion_de_una_compra_agil(config):
    ev = op.Evaluador(config, op.Historia(HISTORIA), [], AHORA, 40000)
    con = ev.evaluar(ca.leer_ficha(_ca("100-1-COT26", "Mantención caldera", descripcion="Se exige visita técnica previa"), "100-1-COT26"))
    sin = ev.evaluar(ca.leer_ficha(_ca("100-2-COT26", "Mantención caldera", descripcion="Ver visitas guiadas del museo"), "100-2-COT26"))
    assert con["visita"]["mencionada"] and con["criterios"]["visita"]["puntaje"] < 100
    assert not sin["visita"]["mencionada"] and sin["criterios"]["visita"]["puntaje"] == 100


def test_una_busqueda_caida_no_borra_lo_que_seguia_abierto(tmp_path, config):
    compra = _ca("100-1-COT26", "Mantención calefacción central")
    _revisar(tmp_path, config, [compra])
    r = _revisar(tmp_path, config, [compra], fallan={"calefacción"})
    assert [o["codigo"] for o in r["datos"]["oportunidades"]] == ["100-1-COT26"]
    assert any("no respondió a 1 búsqueda" in a for a in r["avisos"])


def test_la_ficha_se_vuelve_a_pedir_solo_si_la_compra_cambio(tmp_path, config):
    _revisar(tmp_path, config, [_ca("100-1-COT26", "Mantención caldera")])
    api = ApiCaFalsa([_ca("100-1-COT26", "Mantención caldera")])
    op.revisar(None, cliente=_cliente(ApiFalsa()), enviar=False, ruta_estado=tmp_path / "estado.json", config=config,
               ahora=AHORA, reqs=HISTORIA, cliente_ca=_cliente_ca(api))
    assert not any(u.endswith("/100-1-COT26") for u in api.urls)


# ── el correo ────────────────────────────────────────────────────────────────

def _op(codigo, puntaje, cierre="2026-10-20T15:00", **kw):
    return dict({"codigo": codigo, "nombre": f"Mantención caldera {codigo}", "puntaje": puntaje, "categoria": "prioritaria",
                 "descartar": [], "ficha": True, "cierre": cierre, "url": mp.FICHA_LICITACION + codigo, "tipo": "LE",
                 "monto": {"valor": 12_000_000, "fuente": "estimado"}, "regionCorta": "Valparaíso", "comuna": "Quilpué",
                 "visita": {"fecha": "2026-10-16T10:00", "obligatoria": True}, "duracionMeses": 12,
                 "aFavor": ["Del rubro: caldera"], "enContra": [], "enPlanilla": None}, **kw)


@pytest.fixture
def reglas():
    return op.cargar_config()["alertas"]


def test_solo_notas_altas_abiertas_nuevas_y_fuera_de_la_planilla(reglas):
    datos = {"oportunidades": [
        _op("1-1-LE26", 91), _op("1-2-LE26", 84.9), _op("1-3-LE26", 95, categoria="descartar", descartar=["x"]),
        _op("1-4-LE26", 90, enPlanilla={"req": 300}), _op("1-5-LE26", 92, cierre="2026-10-14T09:00"),
        _op("1-6-LE26", 88, ficha=False), _op("1-7-COT26", 86, cierre="2026-10-13T23:00"), _op("1-8-LE26", 89)]}
    d = al.decidir(datos, {"enviados": [{"codigo": "1-8-LE26", "fecha": "2026-01-01"}]}, reglas, AHORA)
    # 1-5 cierra en 23 horas (una licitación pide 48); 1-7 es compra ágil y le bastan 12.
    assert [o["codigo"] for o in d["enviar"]] == ["1-1-LE26", "1-7-COT26"]


def test_como_maximo_3_correos_en_7_dias(reglas):
    registro = {"correos": [{"fecha": (AHORA - timedelta(days=d)).isoformat()} for d in (1, 3, 6)]}
    d = al.decidir({"oportunidades": [_op("1-1-LE26", 95)]}, registro, reglas, AHORA)
    assert d["enviar"] == [] and [o["codigo"] for o in d["esperan"]] == ["1-1-LE26"]
    registro["correos"][-1]["fecha"] = (AHORA - timedelta(days=8)).isoformat()
    assert [o["codigo"] for o in al.decidir({"oportunidades": [_op("1-1-LE26", 95)]}, registro, reglas, AHORA)["enviar"]] == ["1-1-LE26"]


def test_varias_van_en_un_solo_correo_y_nunca_se_repiten(tmp_path, reglas):
    enviados = []
    destinatarios = tmp_path / "dest.json"
    destinatarios.write_text(json.dumps({"para": ["persona@ejemplo.cl", "no es un correo"]}), encoding="utf-8")
    registro = tmp_path / "registro.json"

    def remitente(para, asunto, cuerpo):
        enviados.append((para, asunto, cuerpo))
        return "enviado"
    datos = {"oportunidades": [_op("1-1-LE26", 90), _op("1-2-LE26", 96)]}
    kw = dict(ahora=AHORA, remitente=remitente, ruta_registro=registro, ruta_destinatarios=destinatarios)
    r = al.ejecutar(datos, **kw)
    assert r["enviado"] == "enviado" and len(enviados) == 1
    assert enviados[0][0] == ["persona@ejemplo.cl"] and enviados[0][1].startswith("2 oportunidades")
    assert al.ejecutar(datos, **kw)["enviar"] == [] and len(enviados) == 1            # ya enviadas: no se repiten
    assert {e["codigo"] for e in json.loads(registro.read_text(encoding="utf-8"))["enviados"]} == {"1-1-LE26", "1-2-LE26"}


def test_si_outlook_falla_no_se_marca_como_enviada(tmp_path, reglas):
    destinatarios = tmp_path / "dest.json"
    destinatarios.write_text(json.dumps({"para": ["persona@ejemplo.cl"]}), encoding="utf-8")

    def falla(*a):
        raise al.ErrorCorreo("Outlook no aceptó el correo")
    with pytest.raises(al.ErrorCorreo):
        al.ejecutar({"oportunidades": [_op("1-1-LE26", 90)]}, ahora=AHORA, remitente=falla,
                    ruta_registro=tmp_path / "r.json", ruta_destinatarios=destinatarios)
    assert not (tmp_path / "r.json").exists()


def test_sin_destinatario_no_se_envia_nada(tmp_path):
    r = al.ejecutar({"oportunidades": [_op("1-1-LE26", 90)]}, ahora=AHORA, ruta_registro=tmp_path / "r.json")
    assert r["enviado"] is None and "no hay destinatario" in r["motivo"]


def test_el_correo_resume_lo_pedido_y_escapa_el_texto_de_la_api(reglas):
    o = _op("1-1-LE26", 91, nombre="Caldera <script>alert(1)</script>")
    ca_op = _op("100-1-COT26", 87, cierre="2026-10-14T06:00", compraAgil=True, url=ca.FICHA + "100-1-COT26", visita={"fecha": None, "mencionada": True},
                duracionMeses=10 / 30, monto={"valor": 2_000_000, "fuente": "estimado"})
    cuerpo = al.cuerpo_html([o, ca_op], AHORA, reglas)
    assert "<script>" not in cuerpo and "&lt;script&gt;" in cuerpo
    for esperado in ("$12.000.000", "7 días", "Quilpué, Valparaíso", "Sí, obligatoria: 16-10-2026 10:00", "12 meses",
                     "Compra Ágil", "20 horas", "La descripción menciona una visita", "Entrega en 10 días", al.URL_TABLERO):
        assert esperado in cuerpo, esperado
    assert al.asunto([o]).startswith("Oportunidad 91/100 en Mercado Público")


def test_con_la_api_lenta_se_usa_lo_que_alcanzo_en_el_tiempo_de_la_vuelta(tmp_path, config):
    # Cada consulta «tarda» 20 s y la vuelta tiene 50 s: alcanza la primera búsqueda y una ficha.
    config["compraAgil"]["busquedas"] = ["caldera", "calefacción", "radiador"]
    reloj = {"t": 0.0}

    def tic():
        reloj["t"] += 20
        return reloj["t"]
    api = ApiCaFalsa([_ca("100-1-COT26", "Mantención caldera"), _ca("100-2-COT26", "Reparación calefacción")])
    cli = ca.Cliente(TICKET, abrir=api, dormir=lambda s: None, reloj=tic, limite_seg=50)
    r = op.revisar(None, cliente=_cliente(ApiFalsa()), enviar=False, ruta_estado=tmp_path / "e.json", config=config,
                   ahora=AHORA, reqs=HISTORIA, cliente_ca=cli)
    assert [o["codigo"] for o in r["datos"]["oportunidades"]] == ["100-1-COT26"]
    assert any("estuvo lenta" in a for a in r["avisos"])


def test_sin_ficha_se_usa_la_region_y_el_monto_del_listado(tmp_path, config):
    # Sin tiempo para la ficha: la evaluación por el nombre usa lo que trae el listado.
    config["compraAgil"]["fraccionTiempoBusquedas"] = 1.0
    compra = _ca("100-1-COT26", "Mantención caldera", region="Región de Magallanes y de la Antártica ", monto=1_800_000)
    api = ApiCaFalsa([compra])
    original = api.__call__

    class SinDetalle(ApiCaFalsa):
        def __call__(self, url, tiempo, encabezados):
            if urllib.parse.urlsplit(url).path.endswith("/100-1-COT26"):
                return 504, b"timeout"
            return original(url, tiempo, encabezados)
    r = op.revisar(None, cliente=_cliente(ApiFalsa()), enviar=False, ruta_estado=tmp_path / "e.json", config=config,
                   ahora=AHORA, reqs=HISTORIA, cliente_ca=_cliente_ca(SinDetalle([compra])))
    o = r["datos"]["oportunidades"][0]
    assert not o["ficha"] and o["compraAgil"] and o["regionCorta"] == "Magallanes"
    assert o["criterios"]["ubicacion"]["puntaje"] == 15 and o["monto"]["valor"] == 1_800_000
