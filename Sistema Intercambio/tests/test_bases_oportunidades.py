# -*- coding: utf-8 -*-
"""Revisión de las bases antes del correo de alertas (2026-10-15).

Las fichas de prueba son sintéticas (datos ficticios), con los mismos id de
elemento que la ficha pública real de Mercado Público."""

import json
import urllib.error
from datetime import datetime

import pytest

import alertas_oportunidades as al
import bases_oportunidades as b
import compra_agil as ca
import mercado_publico as mp
import oportunidades as op

AHORA = datetime(2026, 10, 15, 10, 0)          # jueves
CODIGO = "1234-56-LE26"


def _span(id_, texto):
    return f'<span id="{id_}" class="texto09">{texto}</span>\n'


def _pagina(codigo=CODIGO, estado="Publicada", cierre="05-11-2026 15:00:00", fechas=(), criterios=(), garantias=(),
            clausulas=(), anexos=("ANEXO N° 1 DECLARACIÓN JURADA",), monto="20000000", duracion="24 Meses",
            plazo_pago="30 días contra la recepción conforme de la factura", subcontratacion="Se permite subcontratación",
            reclamos="3", observacion="Sin observaciones", corta=False):
    partes = [f"<html><body><span id=\"lblNumLicitacion\">{codigo}</span>\n", _span("lblFicha2Reclamo", reclamos)]
    if corta:                                   # una L1: sin «Contenido de las bases»
        return "".join(partes + [_span("lblCierre", cierre), "</body></html>"])
    partes += [_span("lblFicha1Estado", estado), _span("lblFicha1Tipo", "Pública-Licitación Pública (LE)"),
               _span("lblFicha3Cierre", cierre), _span("lblFicha3Fin", "23-10-2026 18:00:00"),
               _span("lblFicha2Comuna", "Quilpué"), _span("lblFicha2Region", "Región de Valparaíso"),
               _span("lblFicha7MontoEstimado", monto), _span("lblFicha7Estimacion", "Presupuesto Disponible"),
               _span("lblFicha7Observacion", observacion), _span("lblFicha7TiempoContrato", duracion),
               _span("lblFicha7ContratoRenovacion", "NO"), _span("lblFicha7Plazos", plazo_pago),
               _span("lblFicha7Subcontratacion", subcontratacion),
               _span("lblFicha7NombreResponsablePago", "Funcionaria Ficticia"),
               _span("lblFicha7EmailResponsablePago", "pagos@ejemplo.cl")]
    for i, (texto, fecha) in enumerate(fechas, start=2):
        partes += [_span(f"grvFechasUsuario_ctl{i:02d}_lblFicha3TituloFechaUsuario", texto),
                   _span(f"grvFechasUsuario_ctl{i:02d}_lblFicha3FechaUsuario", fecha)]
    for i, (nombre, ponderacion, detalle) in enumerate(criterios, start=2):
        partes += [_span(f"grvCriterios_ctl{i:02d}_lblNombreCriterio", nombre), _span(f"grvCriterios_ctl{i:02d}_lblPonderacion", ponderacion),
                   _span(f"grvCriterios_ctl{i:02d}_lblObservaciones", detalle)]
    for i, (tipo, monto_g, unidad, vence, descripcion) in enumerate(garantias, start=2):
        partes += [_span(f"grvGarantias_ctl{i:02d}_lblFicha8TituloTipoGarantia", tipo), _span(f"grvGarantias_ctl{i:02d}_lblFicha8Monto", monto_g),
                   _span(f"grvGarantias_ctl{i:02d}_lblFicha8TipoMoneda", unidad), _span(f"grvGarantias_ctl{i:02d}_lblFicha8FechaVencimiento", vence),
                   _span(f"grvGarantias_ctl{i:02d}_lblFicha8Descripcion", descripcion)]
    for i, (titulo, texto) in enumerate(clausulas, start=2):
        partes += [_span(f"grvRequerimientosTecnicos_ctl{i:02d}_lblTitulo", titulo),
                   _span(f"grvRequerimientosTecnicos_ctl{i:02d}_lblDescripcion", texto)]
    for i, anexo in enumerate(anexos, start=2):
        partes.append(_span(f"grvAdministrativo_ctl{i:02d}_lblDescripcion", anexo))
    return "".join(partes) + "</body></html>"


def _o(codigo=CODIGO, **kw):
    return dict({"codigo": codigo, "nombre": "Mantención de calderas", "puntaje": 90, "cierre": "2026-11-05T15:00",
                 "monto": {"valor": 20_000_000, "fuente": "estimado"}, "duracionMeses": 24,
                 "visita": {"fecha": None, "obligatoria": None, "mencionada": False}, "descripcion": "Mantención de calderas"}, **kw)


@pytest.fixture
def config():
    return op.cargar_config()


def _verificar(config, pagina, o=None, ahora=AHORA):
    return b.verificar_licitacion(o or _o(), b.leer_ficha(pagina), ahora, config["alertas"])


def _textos(r, nivel=None):
    return [p["texto"] for p in r["puntos"] if nivel is None or p["nivel"] == nivel]


# ── leer la ficha ────────────────────────────────────────────────────────────

def test_lee_la_ficha_por_id_y_sin_contactos():
    f = b.leer_ficha(_pagina(
        fechas=[("VISITA A TERRENO (OBLIGATORIA)", "16-10-2026 10:30:00")],
        criterios=[("Precio", "60%", "SEGUN BASES ADJUNTAS")],
        garantias=[("Garantías de Seriedad de Ofertas", "1.500.000", "Peso Chileno", "12-05-2027", "Consultas a garantias@ejemplo.cl")],
        clausulas=[("MULTAS", "1 UTM por día de atraso")]))
    assert f["estado"] == "Publicada" and f["cierre"] == "2026-11-05T15:00" and f["preguntasHasta"] == "2026-10-23T18:00"
    assert f["fechasComprador"] == [{"texto": "VISITA A TERRENO (OBLIGATORIA)", "fecha": "2026-10-16T10:30"}]
    assert f["criterios"] == [{"nombre": "Precio", "ponderacion": 60.0, "detalle": "SEGUN BASES ADJUNTAS"}]
    assert f["garantias"][0]["monto"] == 1_500_000 and "garantias@ejemplo.cl" not in json.dumps(f)
    assert f["monto"] == 20_000_000 and f["duracion"] == "24 Meses" and f["reclamosPago"] == 3
    assert f["observaciones"] is None                                   # «Sin observaciones» no es un dato
    assert "Funcionaria Ficticia" not in json.dumps(f) and "pagos@ejemplo.cl" not in json.dumps(f)
    assert f["contenidoBases"] and f["anexos"]["administrativos"] == ["ANEXO N° 1 DECLARACIÓN JURADA"]


def test_el_texto_de_la_ficha_se_limpia():
    f = b.leer_ficha(_pagina(criterios=[("Precio<script>x</script>", "50%", "a&lt;b\x07")]))
    assert f["criterios"][0]["nombre"] == "Precio x" and f["criterios"][0]["detalle"] == "a<b"


@pytest.mark.parametrize("texto,remite", [
    ("SEGUN BASES ADJUNTAS", True), ("CONFORME NUMERAL 4 DEL ANEXO NRO. 1", True), ("Según el punto 6.1 de las BAE.", True),
    ("Revisar en Bases Técnica XI.- Criterios de Evaluación", True), ("DE ACUERDO A NUMERAL 17.2 BASES ADMINISTRATIVAS.", True),
    ("CONFORME AL FORO ESTABLECIDO PARA TAL EFECTO.", False), ("1 UTM por día de atraso", False)])
def test_reconoce_lo_que_remite_a_las_bases_adjuntas(texto, remite):
    assert b.remite(texto) is remite


# ── verificar ────────────────────────────────────────────────────────────────

def test_la_visita_obligatoria_ya_pasada_descarta(config):
    r = _verificar(config, _pagina(fechas=[("VISITA A TERRENO (OBLIGATORIA)", "09-10-2026 10:00:00")]))
    assert "visita a terreno obligatoria fue el 09-10-2026 10:00" in r["descarta"]


def test_la_visita_por_venir_se_avisa_y_corrige_la_evaluacion(config):
    r = _verificar(config, _pagina(fechas=[("VISITA A TERRENO (OBLIGATORIA)", "16-10-2026 10:30:00")]))
    assert r["descarta"] is None
    assert any("Visita a terreno obligatoria el 16-10-2026 10:30 (mañana)" in t and "la evaluación previa no la tenía" in t
               for t in _textos(r, "atencion"))
    assert r["correcciones"]["visita"] == "Sí, obligatoria: 16-10-2026 10:30 · según las bases"


def test_la_visita_voluntaria_ya_pasada_no_descarta(config):
    r = _verificar(config, _pagina(fechas=[("VISITA A TERRENO VOLUNTARIA: Calle Ficticia 123", "14-10-2026 12:00:00")]))
    assert r["descarta"] is None and any("visita voluntaria fue el 14-10-2026" in t for t in _textos(r, "dato"))


def test_la_visita_sin_decir_si_es_obligatoria_pide_revisarlo(config):
    r = _verificar(config, _pagina(fechas=[("Visita a Terreno, Hospital Ficticio, Calle Uno 456", "20-10-2026 10:00:00")]))
    texto = next(t for t in _textos(r, "atencion") if t.startswith("Visita a terreno"))
    assert "(en 5 días): Hospital Ficticio, Calle Uno 456; revisa en las bases si es obligatoria" in texto


def test_sin_visita_queda_confirmado(config):
    assert "Sin visita a terreno en la ficha de las bases" in _textos(_verificar(config, _pagina()), "ok")


def test_el_resumen_de_la_visita_para_el_tablero():
    """Lo que guarda la evaluación previa (visitaBases): con un criterio de
    visita, una fecha por recinto cuenta como visita; la firma del contrato no."""
    f = b.leer_ficha(_pagina(fechas=[("Línea N° 2, Recinto Ficticio Dos, Calle Dos 22", "21-10-2026 12:00:00"),
                                     ("Línea N° 1, Recinto Ficticio Uno, Calle Uno 11", "20-10-2026 10:00:00"),
                                     ("Fecha estimada firma de contrato", "02-12-2026 18:00:00")],
                             criterios=[("Visita Terreno", "10%", "Asistencia a la visita")]))
    r = b.resumen_visita(f)
    assert [x["fecha"] for x in r["fechas"]] == ["2026-10-20T10:00", "2026-10-21T12:00"]   # ordenadas, sin la firma
    assert r["fechas"][0]["lugar"] == "Línea N° 1, Recinto Ficticio Uno, Calle Uno 11"
    assert r["nombrada"] and r["daPuntaje"] and r["contenidoBases"]
    sin = b.resumen_visita(b.leer_ficha(_pagina(fechas=[("Fecha estimada firma de contrato", "02-12-2026 18:00:00")])))
    assert sin["fechas"] == [] and not sin["nombrada"] and sin["contenidoBases"]
    assert not b.resumen_visita(b.leer_ficha(_pagina(corta=True)))["contenidoBases"]   # una L1: no se sabe


@pytest.mark.parametrize("pagina,motivo", [
    (_pagina(estado="Cerrada"), "ya no está publicada"),
    (_pagina(cierre="16-10-2026 12:00:00"), "quedan 26 horas y hacen falta 48"),
])
def test_lo_que_descarta_sola(config, pagina, motivo):
    assert motivo in _verificar(config, pagina)["descarta"]


def test_un_cierre_que_cambio_se_avisa_y_corrige(config):
    r = _verificar(config, _pagina(cierre="12-11-2026 15:00:00"))
    assert any("El cierre cambió: ahora es el 12-11-2026 15:00" in t for t in _textos(r, "atencion"))
    assert r["correcciones"]["cierre"] == "2026-11-12T15:00"


def test_garantias_criterios_pago_y_condiciones(config):
    r = _verificar(config, _pagina(
        reclamos="120", subcontratacion="No permite subcontratación SEGUN BASES ADJUNTAS",
        plazo_pago="60 días contra la recepción conforme de la factura",
        criterios=[("Precio", "35%", "SEGUN BASES ADJUNTAS"), ("Experiencia de los Oferentes", "30%", "SEGUN BASES ADJUNTAS"),
                   ("Certificación SEC (Anexo 15)", "15%", "Adjuntar certificados del personal SEC clase A"),
                   ("Plazo de entrega", "20%", "SEGUN BASES ADJUNTAS")],
        garantias=[("Garantías de Seriedad de Ofertas", "1000000", "Peso Chileno", "12-05-2027", "SEGUN BASES ADJUNTAS"),
                   ("Garantía fiel de Cumplimiento de Contrato", "5", "%", "08-04-2029", "SEGUN BASES ADJUNTAS")],
        clausulas=[("MULTAS", "1 UTM por cada día de atraso en la mantención")]))
    atencion, dato = " | ".join(_textos(r, "atencion")), " | ".join(_textos(r, "dato"))
    for esperado in ("Garantía de seriedad de la oferta: $1.000.000 (≈ 5,0 % del monto), vigente hasta el 12-05-2027",
                     "El precio pesa solo 35 %", "La experiencia pesa 30 %", "Da puntaje «Certificación SEC (Anexo 15)» (15 %)",
                     "Paga a 60 días", "120 reclamos por pagar fuera de plazo", "No permite subcontratar",
                     "Tiene multas y sanciones: 1 UTM por cada día de atraso"):
        assert esperado in atencion, esperado
    assert "Menciona certificación SEC" not in atencion          # ya salió como criterio: no se repite
    assert "Garantía de fiel cumplimiento: 5 % (≈ $1.000.000), vigente hasta el 08-04-2029" in dato
    assert "Criterios de evaluación: Precio 35 %, Experiencia de los Oferentes 30 %" in dato
    assert r["remiten"] == 5                    # 3 criterios + 2 garantías dicen «según bases adjuntas»


def test_el_monto_publicado_corrige_uno_estimado(config):
    r = _verificar(config, _pagina(monto="45000000"), o=_o(monto={"valor": 10_000_000, "fuente": "por tipo (LE)"}))
    assert r["correcciones"]["monto"] == "$45.000.000 (presupuesto disponible)"
    assert "Monto confirmado: $20.000.000 (presupuesto disponible)" in _textos(_verificar(config, _pagina()), "ok")


def test_la_duracion_distinta_se_avisa(config):
    r = _verificar(config, _pagina(duracion="36 Meses"))
    assert "El contrato dura 36 meses (la evaluación usó 24 meses)" in _textos(r, "atencion")


def test_una_l1_no_trae_el_contenido_de_las_bases(config):
    r = _verificar(config, _pagina(corta=True))
    assert any("no trae el contenido de las bases" in t for t in _textos(r, "atencion"))
    assert "No pide garantías en la ficha" not in _textos(r)


def test_documentos_repetidos_o_que_solo_remiten_no_se_listan(config):
    r = _verificar(config, _pagina(anexos=["CONFORME BASE DE LICITACION"] * 3))
    assert "Los documentos que pide la oferta están detallados en las bases adjuntas" in _textos(r, "dato")


# ── bajar la ficha ───────────────────────────────────────────────────────────

def test_bajar_la_ficha_valida_lo_que_llega():
    assert CODIGO in b.bajar_ficha(CODIGO, abrir=lambda url, t: (200, _pagina().encode()))
    with pytest.raises(b.ErrorBases, match="HTTP 503"):
        b.bajar_ficha(CODIGO, abrir=lambda url, t: (503, b""))
    with pytest.raises(b.ErrorBases, match="no es la ficha"):
        b.bajar_ficha(CODIGO, abrir=lambda url, t: (200, _pagina(codigo="9-9-LE26").encode()))
    with pytest.raises(ValueError):
        b.bajar_ficha("1234-56-LE26&x=1", abrir=lambda url, t: (200, b""))


def test_una_redireccion_no_puede_salir_de_mercado_publico():
    manejador = b._SoloMercadoPublico()
    with pytest.raises(urllib.error.HTTPError):
        manejador.redirect_request(None, None, 302, "Found", {}, "https://otro-sitio.cl/ficha")
    with pytest.raises(urllib.error.HTTPError):
        manejador.redirect_request(None, None, 302, "Found", {}, "http://www.mercadopublico.cl/ficha")


def test_si_la_ficha_no_responde_no_lanza(config):
    def caida(url, tiempo):
        raise OSError("sin conexión")
    r = b.revisar(_o(), AHORA, config, abrir=caida, dormir=lambda s: None)
    assert r["ok"] is False and "sin conexión" in r["error"] and r["descarta"] is None


def test_revisar_una_licitacion(config):
    r = b.revisar(_o(), AHORA, config, abrir=lambda url, t: (200, _pagina().encode()), dormir=lambda s: None)
    assert r["ok"] and r["fuente"] == b.FUENTE_LICITACION and r["revisado"] == "2026-10-15T10:00"


# ── compras ágiles ───────────────────────────────────────────────────────────

def _crudo_ca(**kw):
    return dict({"codigo": "100-1-COT26", "estado": {"codigo": "publicada", "glosa": "Publicada"},
                 "fechas": {"fecha_cierre": "2026-10-17 18:00"}, "presupuesto": {"monto_disponible_clp": 2_000_000},
                 "entrega": {"plazo_entrega_dias": 10, "direccion_entrega": "Calle Ficticia 123, Quilpué, fono +56 9 1234 5678"},
                 "documentos": [{"id": 1, "nombre": "Términos de referencia.pdf"}],
                 "descripcion": "Mantención de caldera. Se exige visita técnica previa el día lunes y técnico con certificación SEC.",
                 "productos_solicitados": [{"nombre": "Mantención de caldera", "descripcion": "Caldera a gas"}],
                 "resumen": {"total_ofertas_recibidas": 2}, "convocatoria": {"estado_convocatoria": 1}}, **kw)


class _ClienteCaFalso:
    def __init__(self, crudo):
        self.crudo = crudo

    def detalle(self, codigo):
        return self.crudo

    def censurar(self, texto):
        return str(texto)


def test_revisar_una_compra_agil(config):
    o = _o("100-1-COT26", compraAgil=True, cierre="2026-10-17T18:00", monto={"valor": 2_000_000, "fuente": "estimado"})
    r = b.revisar(o, AHORA, config, cliente_ca=_ClienteCaFalso(_crudo_ca()), dormir=lambda s: None)
    atencion, todo = " | ".join(_textos(r, "atencion")), " | ".join(_textos(r))
    assert r["ok"] and r["fuente"] == b.FUENTE_COMPRA_AGIL and r["descarta"] is None
    assert "Trae 1 adjunto: «Términos de referencia.pdf». Léelos en la ficha" in atencion
    assert "Pide o menciona una visita: «Mantención de caldera. Se exige visita técnica previa" in atencion
    assert "Menciona certificación SEC (descripción)" in atencion
    assert "Monto confirmado: $2.000.000 (disponible)" in todo and "Plazo de entrega: 10 días" in todo
    assert "+56 9 1234 5678" not in todo and "Ya recibió 2 cotizaciones" in todo


def test_un_adjunto_sobre_la_visita_se_avisa(config):
    o = _o("100-1-COT26", compraAgil=True, cierre="2026-10-17T18:00")
    crudo = _crudo_ca(descripcion="Servicio de mantención de caldera.", documentos=[{"id": 2, "nombre": "i) ACTA VISITA A TERRENO.doc"}])
    r = b.revisar(o, AHORA, config, cliente_ca=_ClienteCaFalso(crudo), dormir=lambda s: None)
    assert "Un adjunto trata de la visita a terreno: «i) ACTA VISITA A TERRENO.doc»" in " | ".join(_textos(r, "atencion"))
    assert r["correcciones"]["visita"].startswith("Hay un adjunto sobre la visita")


def test_una_compra_agil_cerrada_o_que_ya_no_existe_descarta(config):
    o = _o("100-1-COT26", compraAgil=True, cierre="2026-10-17T18:00")
    cerrada = _crudo_ca(estado={"codigo": "cerrada", "glosa": "Cerrada"})
    assert "ya no está publicada (Cerrada)" in b.revisar(o, AHORA, config, cliente_ca=_ClienteCaFalso(cerrada), dormir=lambda s: None)["descarta"]
    assert "ya no la muestra" in b.revisar(o, AHORA, config, cliente_ca=_ClienteCaFalso(None), dormir=lambda s: None)["descarta"]


# ── el correo espera la revisión ─────────────────────────────────────────────

def _op(codigo, puntaje, cierre="2026-10-30T15:00", **kw):
    return dict({"codigo": codigo, "nombre": f"Mantención caldera {codigo}", "puntaje": puntaje, "categoria": "prioritaria",
                 "descartar": [], "ficha": True, "cierre": cierre, "url": mp.FICHA_LICITACION + codigo, "tipo": "LE",
                 "monto": {"valor": 12_000_000, "fuente": "estimado"}, "regionCorta": "Valparaíso", "comuna": "Quilpué",
                 "visita": {"fecha": None, "obligatoria": None, "mencionada": False}, "duracionMeses": 12,
                 "aFavor": [], "enContra": [], "enPlanilla": None}, **kw)


def _revision(codigo, ok=True, descarta=None, puntos=(), correcciones=None, error=None):
    return {"codigo": codigo, "ok": ok, "error": error, "revisado": "2026-10-15T10:00", "puntos": list(puntos),
            "descarta": descarta, "correcciones": correcciones or {}, "remiten": 2, "fuente": b.FUENTE_LICITACION}


@pytest.fixture
def envio(tmp_path):
    destinatarios = tmp_path / "dest.json"
    destinatarios.write_text(json.dumps({"para": ["persona@ejemplo.cl"]}), encoding="utf-8")
    enviados = []

    def remitente(para, asunto, cuerpo):
        enviados.append((asunto, cuerpo))
        return "enviado"
    return {"enviados": enviados, "kw": dict(remitente=remitente, ruta_registro=tmp_path / "r.json", ruta_destinatarios=destinatarios)}


def test_lo_que_las_bases_descartan_no_se_envia_ni_se_vuelve_a_revisar(envio):
    revisadas = []

    def revisor(o, ahora, config):
        revisadas.append(o["codigo"])
        return _revision(o["codigo"], descarta="la visita a terreno obligatoria fue el 09-10-2026 10:00: ya pasó") \
            if o["codigo"] == "1-1-LE26" else _revision(o["codigo"])
    datos = {"oportunidades": [_op("1-1-LE26", 95), _op("1-2-LE26", 90)]}
    r = al.ejecutar(datos, ahora=AHORA, revisor=revisor, **envio["kw"])
    assert [o["codigo"] for o in r["enviar"]] == ["1-2-LE26"] and len(envio["enviados"]) == 1
    registro = json.loads(envio["kw"]["ruta_registro"].read_text(encoding="utf-8"))
    assert registro["descartadasBases"][0]["codigo"] == "1-1-LE26" and "ya pasó" in registro["descartadasBases"][0]["motivo"]
    assert registro["enviados"][0]["bases"].startswith("revisadas")
    datos["oportunidades"].append(_op("1-3-LE26", 88))
    al.ejecutar(datos, ahora=AHORA, revisor=revisor, **envio["kw"])
    assert revisadas == ["1-1-LE26", "1-2-LE26", "1-3-LE26"]        # 1-1 no se revisó de nuevo


def test_una_descartada_deja_su_lugar_a_la_siguiente(envio):
    config = op.cargar_config()
    config["alertas"]["maxOportunidadesPorCorreo"] = 1
    datos = {"oportunidades": [_op("1-1-LE26", 95), _op("1-2-LE26", 90), _op("1-3-LE26", 88)]}
    r = al.ejecutar(datos, ahora=AHORA, config=config, **envio["kw"],
                    revisor=lambda o, ahora, c: _revision(o["codigo"], descarta="ya no está publicada" if o["codigo"] == "1-1-LE26" else None))
    assert [o["codigo"] for o in r["enviar"]] == ["1-2-LE26"] and [o["codigo"] for o in r["esperan"]] == ["1-3-LE26"]


def test_si_la_ficha_no_responde_espera_salvo_que_sea_la_ultima_vuelta(envio):
    caida = lambda o, ahora, config: _revision(o["codigo"], ok=False, error="OSError: sin conexión")  # noqa: E731
    # Cierra en 15 días: hay tiempo, espera sin marcarse.
    r = al.ejecutar({"oportunidades": [_op("1-1-LE26", 95)]}, ahora=AHORA, revisor=caida, **envio["kw"])
    assert r["enviar"] == [] and envio["enviados"] == [] and "no se pudieron revisar las bases de 1" in r["motivo"]
    assert not envio["kw"]["ruta_registro"].exists()
    # Jueves 10:00 y cierra el lunes 12:00: el viernes 9:00 quedarían 75 horas (alcanza), el lunes ya no.
    r = al.ejecutar({"oportunidades": [_op("1-1-LE26", 95, cierre="2026-10-19T12:00")]}, ahora=AHORA, revisor=caida, **envio["kw"])
    assert r["enviar"] == []
    viernes = datetime(2026, 10, 16, 10, 0)
    r = al.ejecutar({"oportunidades": [_op("1-1-LE26", 95, cierre="2026-10-19T12:00")]}, ahora=viernes, revisor=caida, **envio["kw"])
    assert r["enviado"] == "enviado" and "No se pudo leer la ficha de las bases (OSError: sin conexión)" in envio["enviados"][0][1]


def test_la_proxima_vuelta_salta_fines_de_semana_y_feriados():
    reglas = op.cargar_config()["alertas"]
    assert al.proxima_vuelta(datetime(2026, 10, 16, 10, 0), reglas) == datetime(2026, 10, 19, 9, 0)     # viernes -> lunes
    assert al.proxima_vuelta(datetime(2026, 10, 9, 10, 0), reglas) == datetime(2026, 10, 13, 9, 0)      # el lunes 12 es feriado


def test_el_correo_lleva_lo_verificado_y_lo_corregido(envio):
    puntos = [{"nivel": "dato", "texto": "Contrato de 24 meses"},
              {"nivel": "atencion", "texto": "Visita a terreno obligatoria el 16-10-2026 10:30 (mañana) <b>"},
              {"nivel": "ok", "texto": "Cierre confirmado: 30-10-2026 15:00"}]
    revisor = lambda o, ahora, config: _revision(o["codigo"], puntos=puntos,  # noqa: E731
                                                  correcciones={"visita": "Sí, obligatoria: 16-10-2026 10:30 · según las bases"})
    al.ejecutar({"oportunidades": [_op("1-1-LE26", 95, aFavor=["Del rubro: caldera", "Sin visita a terreno"])]},
                ahora=AHORA, revisor=revisor, **envio["kw"])
    cuerpo = envio["enviados"][0][1]
    assert "Revisión de las bases" in cuerpo and "se revisaron sus bases en Mercado Público" in cuerpo
    assert "Sí, obligatoria: 16-10-2026 10:30 · según las bases" in cuerpo and "No requiere (sin visita en la ficha)" not in cuerpo
    assert "(mañana) &lt;b&gt;" in cuerpo and "<b>" not in cuerpo
    assert "Sin visita a terreno" not in cuerpo and "Del rubro: caldera" in cuerpo   # la evaluación previa no contradice a las bases
    assert cuerpo.index("Visita a terreno obligatoria") < cuerpo.index("Cierre confirmado") < cuerpo.index("Contrato de 24 meses")
    assert "2 puntos de la ficha remiten a las bases adjuntas (PDF)" in cuerpo


def test_con_la_revision_apagada_se_envia_como_antes(envio):
    config = op.cargar_config()
    config["alertas"]["revisionBases"]["activa"] = False

    def revisor(*a):
        raise AssertionError("no debía revisar")
    r = al.ejecutar({"oportunidades": [_op("1-1-LE26", 95)]}, ahora=AHORA, config=config, revisor=revisor, **envio["kw"])
    assert r["enviado"] == "enviado" and "Revisión de las bases" not in envio["enviados"][0][1]


def test_fuera_de_horario_no_se_revisa_nada(envio):
    def revisor(*a):
        raise AssertionError("fuera de horario no se baja ninguna ficha")
    r = al.ejecutar({"oportunidades": [_op("1-1-LE26", 95)]}, ahora=datetime(2026, 10, 17, 11, 0), revisor=revisor, **envio["kw"])
    assert r["enviar"] == [] and [o["codigo"] for o in r["esperan"]] == ["1-1-LE26"]


def test_status_no_guarda_lo_descartado(tmp_path):
    registro = tmp_path / "r.json"
    r = al.ejecutar({"oportunidades": [_op("1-1-LE26", 95)]}, enviar=False, ahora=AHORA, ruta_registro=registro,
                    revisor=lambda o, ahora, c: _revision(o["codigo"], descarta="ya no está publicada"))
    assert [o["codigo"] for o in r["descartadasBases"]] == ["1-1-LE26"] and not registro.exists()


def test_compra_agil_usa_su_cliente_sin_ticket_no_sale_a_la_red(config):
    # Sin ticket configurado (el conftest lo esconde) no se puede pedir la ficha: queda sin revisar, sin lanzar.
    o = _o("100-1-COT26", compraAgil=True, cierre="2026-10-17T18:00")
    r = b.revisar(o, AHORA, config, dormir=lambda s: None)
    assert r["ok"] is False and r["error"]
    assert ca.es_codigo("100-1-COT26")
