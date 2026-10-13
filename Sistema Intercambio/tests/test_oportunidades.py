# -*- coding: utf-8 -*-
"""Buscador de oportunidades: entiende el rubro sin confundirse con palabras
sueltas, evalúa cada criterio con su motivo, descarta solo por reglas claras y
respeta el tope de consultas. El tablero que lo muestra tiene sus propias
pruebas (test_tablero_oportunidades.py). Siempre con una API falsa (conftest
corta la red) y en tmp_path; los datos son ficticios."""
import json
import urllib.parse
from datetime import datetime

import pytest

import esquemas
import intercambio as ic
import mercado_publico as mp
import oportunidades as op
import requerimientos as rq

TICKET = "A1B2C3D4-0000-1111-2222-333344445555"
AHORA = datetime(2026, 10, 13, 10, 0)


# ── datos ficticios ──────────────────────────────────────────────────────────

def _req(numero, titulo, estado="Descartado", referencia=None, **kw):
    return dict({"numero": numero, "estado": estado, "titulo": titulo, "referencia": referencia}, **kw)


HISTORIA = [
    _req(1, "Mantención preventiva caldera hospital", "Adjudicado", "5000-1-LE26", valorOfertado=8_000_000),
    _req(2, "Mantención calderas y red de calefacción", "No adjudicado", "5001-2-LE26", valorOfertado=15_000_000),
    _req(3, "Reparación caldera agua caliente", "Adjudicado", "5002-3-LE26", valorOfertado=4_000_000),
    _req(4, "Mantención caldera escuela", "Ofertado", "5003-4-LE26", valorOfertado=20_000_000),
    _req(5, "Mantención aire acondicionado oficinas", "Descartado", "5004-5-LE26"),
    _req(6, "Convenio aire acondicionado cuarteles", "Descartado", "5005-6-LE26"),
    _req(7, "Mantención aire acondicionado edificio", "Descartado", "5006-7-LE26"),
    _req(8, "Caldera sala de calderas CESFAM", "Adjudicado", "761391-8-LE26", valorOfertado=30_000_000),
    _req(9, "Revisión y pruebas a caldera", "No adjudicado", "5008-9-COT26", valorOfertado=500_000),
    _req(10, "Calefacción piscina municipal", "No adjudicado", "5009-10-LP26", valorOfertado=60_000_000),
]


def _ficha(codigo, nombre, descripcion="", region="Región de Valparaíso", monto=10_000_000, visita=None,
           cierre="2026-10-25T15:00:00", duracion="12", unidad=4, **extra):
    return dict({
        "CodigoExterno": codigo, "Nombre": nombre, "CodigoEstado": 5, "Descripcion": descripcion,
        "Estado": "Publicada", "Tipo": codigo.rsplit("-", 1)[-1][:-2], "Moneda": "CLP",
        "Comprador": {"NombreOrganismo": "Servicio de ejemplo", "NombreUnidad": "Unidad de ejemplo",
                      "ComunaUnidad": "Quilpué", "RegionUnidad": region,
                      "NombreUsuario": "Funcionaria X", "RutUsuario": "11.111.111-1"},
        "NombreResponsableContrato": "Funcionario Y", "EmailResponsableContrato": "y@ejemplo.cl",
        "CantidadReclamos": 10, "Obras": "0", "Etapas": 1, "TomaRazon": "0",
        "Fechas": {"FechaPublicacion": "2026-10-10T10:00:00", "FechaCierre": cierre, "FechaVisitaTerreno": visita},
        "VisibilidadMonto": 1 if monto else 0, "MontoEstimado": monto,
        "TiempoDuracionContrato": duracion, "UnidadTiempoDuracionContrato": unidad, "EsRenovable": 0,
        "Items": {"Cantidad": 1, "Listado": [{"Correlativo": 1, "Categoria": "Servicios / Calefacción",
                                              "NombreProducto": "Servicio de mantención", "Descripcion": "x"}]},
    }, **extra)


class ApiFalsa:
    def __init__(self, fichas=(), dias=None, adjudicadas=None):
        self.fichas = {f["CodigoExterno"]: f for f in fichas}
        self.dias = dias or {}
        self.adjudicadas = adjudicadas or {}
        self.urls = []

    def __call__(self, url, tiempo):
        self.urls.append(url)
        assert url.startswith("https://api.mercadopublico.cl/")
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        if q.get("estado") == "activas":
            lista = [{"CodigoExterno": c, "Nombre": f["Nombre"], "CodigoEstado": 5, "FechaCierre": f["Fechas"]["FechaCierre"]}
                     for c, f in self.fichas.items()]
            return 200, json.dumps({"Cantidad": len(lista), "Listado": lista}).encode()
        if "fecha" in q:
            lista = self.dias.get(q["fecha"], [])
            return 200, json.dumps({"Cantidad": len(lista), "Listado": lista}).encode()
        if "codigo" in q:
            f = self.fichas.get(q["codigo"]) or self.adjudicadas.get(q["codigo"])
            return 200, json.dumps({"Cantidad": int(bool(f)), "Listado": [f] if f else []}).encode()
        raise AssertionError(url)


def _cliente(api, tope=80):
    return mp.Cliente(TICKET, abrir=api, dormir=lambda s: None, tope=tope)


@pytest.fixture
def config():
    return op.cargar_config()


@pytest.fixture
def evaluador(config):
    return op.Evaluador(config, op.Historia(HISTORIA), [], AHORA, 40000)


def _evaluar(evaluador, crudo):
    return evaluador.evaluar(op.leer_ficha(crudo, crudo["CodigoExterno"]))


# ── texto y rubro ────────────────────────────────────────────────────────────

def test_raices_entiende_abreviaturas_y_plurales_sin_confundir_palabras():
    assert op.raices("MANTTO. CALDERAS y Sist. Calef.") == ["mantencion", "caldera", "sistema", "calefaccion"]
    assert op.raices("Paneles solares, radiadores, gases") == ["panel", "solar", "radiador", "gas"]
    assert op.raices("Estudio hidrogeológico") != op.raices("Estudio hidrógeno")
    assert op.contiene(op.raices("Mantención de la SALA DE CALDERAS"), "sala de calderas")
    assert not op.contiene(op.raices("sala de reuniones y calderas"), "sala de calderas")


def test_una_palabra_generica_o_un_lugar_no_hacen_parecida_una_licitacion(evaluador):
    # «Revisión» está en un título ofertado (N° 9), pero no dice nada del rubro.
    assert evaluador.h.parecidas("Revisión de prótesis de hombro") == []
    assert evaluador.prefiltro("Revisión de prótesis de hombro") == 0
    parecidas = evaluador.h.parecidas("Mantención de calderas del hospital")
    assert parecidas and all("aldera" in it["titulo"] for _, it in parecidas)


def test_rubro_nucleo_afin_y_fuera_de_rubro(evaluador):
    caldera = _evaluar(evaluador, _ficha("1-1-LE26", "Mantención preventiva de calderas"))
    clima = _evaluar(evaluador, _ficha("1-2-LE26", "Mantención aire acondicionado y climatización"))
    petroleo = _evaluar(evaluador, _ficha("1-3-LE26", "Suministro de petróleo para calefacción"))
    ajena = _evaluar(evaluador, _ficha("1-4-LE26", "Servicio de radiotaxis"))
    assert caldera["criterios"]["rubro"]["puntaje"] >= 70 and not caldera["descartar"]
    assert "núcleo: caldera" in caldera["criterios"]["rubro"]["motivo"]
    assert clima["criterios"]["rubro"]["puntaje"] < 50
    assert clima["categoria"] in ("baja", "evaluar")           # tope por rubro, aunque lo demás sea perfecto
    assert petroleo["descartar"] and "Fuera de rubro" in petroleo["descartar"][0]
    assert ajena["descartar"] and "Sin relación" in ajena["descartar"][0]


# ── criterios ────────────────────────────────────────────────────────────────

def test_monto_en_el_rango_habitual_y_estimado_por_tipo(evaluador):
    habitual = _evaluar(evaluador, _ficha("1-1-LE26", "Mantención calderas", monto=12_000_000))
    enorme = _evaluar(evaluador, _ficha("1-2-LR26", "Mantención calderas", monto=900_000_000))
    oculto = _evaluar(evaluador, _ficha("1-3-L126", "Mantención calderas", monto=None))
    assert habitual["criterios"]["monto"]["puntaje"] >= 85
    assert enorme["criterios"]["monto"]["puntaje"] == 10 and not enorme["descartar"]   # el tope de la historia orienta, no descarta
    assert oculto["monto"]["fuente"] == "por tipo L1, 1–100 UTM" and "por tipo L1" in oculto["criterios"]["monto"]["motivo"]
    grande = _evaluar(evaluador, _ficha("1-4-LE26", "Mantención calderas", monto=None))
    assert grande["monto"]["fuente"] == "por tipo LE, 100–1.000 UTM"


def test_un_tope_de_monto_puesto_a_mano_si_descarta(config):
    config["monto"]["maximo"] = 50_000_000
    ev = op.Evaluador(config, op.Historia(HISTORIA), [], AHORA, 40000)
    r = _evaluar(ev, _ficha("1-2-LP26", "Mantención calderas", monto=80_000_000))
    assert r["categoria"] == "descartar" and "máximo" in r["descartar"][0]


def test_visita_a_terreno_pasada_obligatoria_descarta_y_futura_resta_por_distancia(evaluador):
    sin = _evaluar(evaluador, _ficha("1-1-LE26", "Mantención calderas"))
    pasada = _evaluar(evaluador, _ficha("1-2-LE26", "Mantención calderas", "La visita a terreno será obligatoria.",
                                        visita="2026-10-10T10:00:00"))
    cerca = _evaluar(evaluador, _ficha("1-3-LE26", "Mantención calderas", visita="2026-10-20T10:00:00"))
    lejos = _evaluar(evaluador, _ficha("1-4-LE26", "Mantención calderas", visita="2026-10-20T10:00:00",
                                       region="Región de Magallanes y de la Antártica Chilena"))
    assert sin["criterios"]["visita"]["puntaje"] == 100
    assert pasada["categoria"] == "descartar" and "visita obligatoria" in pasada["descartar"][0]
    assert pasada["visita"]["obligatoria"] is True
    assert cerca["criterios"]["visita"]["puntaje"] > lejos["criterios"]["visita"]["puntaje"]
    assert lejos["criterios"]["ubicacion"]["puntaje"] < cerca["criterios"]["ubicacion"]["puntaje"]


def test_plazo_para_ofertar_y_duracion(evaluador):
    manana = _evaluar(evaluador, _ficha("1-1-LE26", "Mantención calderas", cierre="2026-10-13T20:00:00"))
    holgado = _evaluar(evaluador, _ficha("1-2-LE26", "Mantención calderas", cierre="2026-10-30T15:00:00"))
    assert manana["categoria"] == "descartar" and "menos de un día" in manana["descartar"][0]
    assert holgado["criterios"]["plazoOferta"]["puntaje"] == 100
    assert holgado["duracionMeses"] == 12 and holgado["criterios"]["ejecucion"]["puntaje"] == 100
    texto = _evaluar(evaluador, _ficha("1-3-LE26", "Mantención calderas por 36 meses", duracion="0"))
    assert texto["duracionMeses"] == 36


def test_dificultad_sube_con_obras_diseno_y_tamano(evaluador):
    simple = _evaluar(evaluador, _ficha("1-1-LE26", "Mantención preventiva calderas"))
    obra = _evaluar(evaluador, _ficha("1-2-LR26", "Diseño y reubicación de sala de calderas en varios establecimientos",
                                      Obras="1", Etapas=2))
    assert simple["criterios"]["dificultad"]["puntaje"] == 100
    assert obra["criterios"]["dificultad"]["puntaje"] <= 40
    assert "declarada como obra" in obra["criterios"]["dificultad"]["motivo"]


def test_comprador_que_ya_adjudico_a_quempin_suma(evaluador):
    conocido = _evaluar(evaluador, _ficha("761391-99-LE26", "Mantención calderas"))
    nuevo = _evaluar(evaluador, _ficha("999-99-LE26", "Mantención calderas"))
    assert conocido["criterios"]["comprador"]["puntaje"] > nuevo["criterios"]["comprador"]["puntaje"]
    assert "N° 8" in conocido["criterios"]["comprador"]["motivo"]


def test_sin_ficha_lo_desconocido_queda_neutro(evaluador):
    r = evaluador.evaluar_sin_ficha("1-1-LE26", "Mantención calderas", "2026-10-25T15:00", None)
    assert r["ficha"] is False
    assert {r["criterios"][k]["puntaje"] for k in ("dificultad", "visita", "ejecucion")} == {50}


def test_la_categoria_repite_la_regla_de_la_pagina(evaluador):
    assert evaluador.categoria(90, 90) == "prioritaria"
    assert evaluador.categoria(90, 60) == "buena"
    assert evaluador.categoria(90, 45) == "evaluar"
    assert evaluador.categoria(90, 30) == "baja"
    assert evaluador.categoria(10, 90) == "baja"


def test_no_publica_funcionarios_ni_contactos(evaluador):
    crudo = _ficha("1-1-LE26", "Mantención calderas",
                   "Consultas a juan.perez@hospital.cl o fono: 32 2345678. Monto referencial 25456000.")
    r = _evaluar(evaluador, crudo)
    texto = json.dumps(r, ensure_ascii=False)
    assert "Funcionari" not in texto and "@" not in texto and "2345678" not in texto
    assert "25456000" in texto                                  # los montos no se confunden con teléfonos


# ── la vuelta ────────────────────────────────────────────────────────────────

@pytest.fixture
def carpeta(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Herramientas" / "Intercambio")
    ic.publicar(raiz, rq.PUBLICACION, rq.HERRAMIENTA, {"requerimientos": HISTORIA})
    return raiz


def test_vuelta_completa_publica_la_evaluacion(carpeta, config):
    adjudicada = _ficha("5000-50-LE26", "Mantención calderas hospital", CodigoEstado=8,
                        Adjudicacion={"NumeroOferentes": 3, "Fecha": "2026-09-01T00:00:00"})
    adjudicada["Items"]["Listado"][0]["Adjudicacion"] = {"RutProveedor": "99.999.999-9", "NombreProveedor": "Competidor SpA",
                                                         "Cantidad": 1, "MontoUnitario": 9_000_000}
    api = ApiFalsa(
        fichas=[_ficha("5000-60-LE26", "Mantención preventiva calderas hospital"),
                _ficha("7777-1-LE26", "Servicio de radiotaxis"),
                _ficha("5004-61-LE26", "Mantención de aire acondicionado oficinas")],
        dias={"12102026": [{"CodigoExterno": "5000-50-LE26", "Nombre": "Mantención calderas hospital", "CodigoEstado": 8}]},
        adjudicadas={"5000-50-LE26": adjudicada})
    r = op.revisar(carpeta, cliente=_cliente(api), config=config, ahora=AHORA)
    sobre = ic.leer_publicacion(carpeta, op.PUBLICACION)
    assert sobre and esquemas.validar_publicacion(op.PUBLICACION, sobre) == []
    codigos = [o["codigo"] for o in sobre["datos"]["oportunidades"]]
    assert codigos[0] == "5000-60-LE26"
    assert "7777-1-LE26" not in codigos                              # «radiotaxis» ni siquiera se pidió
    assert not any("7777-1-LE26" in u for u in api.urls if "codigo=" in u)
    mejor = sobre["datos"]["oportunidades"][0]
    assert mejor["mercado"] and mejor["mercado"][0]["ganadores"] == ["Competidor SpA"]   # precedente del mismo comprador
    assert sobre["datos"]["perfil"]["competidores"][0]["nombre"] == "Competidor SpA"
    assert sobre["datos"]["reglas"]["plazoOferta"] == config["plazoOferta"]["tramos"]   # lo que la página recalcula al día
    assert list((carpeta.parent).glob("*.html")) == []               # la página vive en GitHub Pages, no junto a la Planilla
    assert r["llamadas"] <= config["consultas"]["tope"]


def test_respeta_el_tope_de_consultas_y_sigue_en_la_proxima(carpeta, config):
    fichas = [_ficha(f"5000-{i}-LE26", f"Mantención calderas recinto {i}") for i in range(100, 110)]
    api = ApiFalsa(fichas=fichas)
    r = op.revisar(carpeta, cliente=_cliente(api, tope=4), config=config, ahora=AHORA)
    assert r["incompleta"] and len(api.urls) == 4
    sin_ficha = [o for o in r["datos"]["oportunidades"] if not o["ficha"]]
    assert len(sin_ficha) == 7                                       # 1 listado + 3 fichas; las demás, solo por nombre
    api2 = ApiFalsa(fichas=fichas)
    r2 = op.revisar(carpeta, cliente=_cliente(api2), config=config, ahora=AHORA)
    assert all(o["ficha"] for o in r2["datos"]["oportunidades"])
    assert sum("codigo=" in u for u in api2.urls) == 7               # las 3 ya leídas no se piden de nuevo


def test_status_no_publica(carpeta, config):
    api = ApiFalsa(fichas=[_ficha("5000-60-LE26", "Mantención calderas")])
    op.revisar(carpeta, cliente=_cliente(api), enviar=False, config=config, ahora=AHORA)
    assert ic.leer_publicacion(carpeta, op.PUBLICACION) is None


def test_a_favor_y_en_contra_dicen_hacia_donde_empuja_cada_criterio(evaluador):
    buena = _evaluar(evaluador, _ficha("761391-99-LE26", "Mantención de calderas", monto=12_000_000))
    lejana = _evaluar(evaluador, _ficha("1-2-LE26", "Mantención de calderas", "Para los establecimientos de la comuna.",
                                        region="Región de Magallanes y de la Antártica Chilena", monto=900_000_000))
    assert buena["aFavor"] and buena["enContra"] == []
    assert any(f.startswith("Del rubro: caldera") for f in buena["aFavor"])
    assert "Ya nos adjudicó antes" in buena["aFavor"] or len(buena["aFavor"]) == 3
    assert "Lejos: Magallanes" in lejana["enContra"] and any("más grande" in c or "máximo" in c for c in lejana["enContra"])
    # Una penalización nunca aparece como algo a favor
    assert not any("recintos" in f.lower() for f in lejana["aFavor"])
    assert len(lejana["enContra"]) <= 2 and len(buena["aFavor"]) <= 3


def test_los_motivos_que_dependen_de_la_fecha_van_aparte(evaluador):
    """La página recalcula el plazo y la visita con la fecha del día: necesita
    saber qué motivos para descartar no dependen de la fecha."""
    r = _evaluar(evaluador, _ficha("1-1-LE26", "Suministro de petróleo para calefacción", cierre="2026-10-13T20:00:00"))
    assert any("Fuera de rubro" in d for d in r["descartarFijo"])
    assert not any("menos de un día" in d for d in r["descartarFijo"])
    assert any("menos de un día" in d for d in r["descartar"])


def test_el_plazo_usa_los_tramos_de_la_configuracion(config):
    config["plazoOferta"]["tramos"] = [{"menosDeDias": 1, "puntaje": 0, "descarta": True}, {"menosDeDias": None, "puntaje": 77}]
    ev = op.Evaluador(config, op.Historia(HISTORIA), [], AHORA, 40000)
    assert _evaluar(ev, _ficha("1-1-LE26", "Mantención calderas", cierre="2026-10-15T12:00:00"))["criterios"]["plazoOferta"]["puntaje"] == 77


def test_el_procesador_no_lo_corre_hasta_activarlo(carpeta, config, monkeypatch):
    import procesar
    llamadas = []
    monkeypatch.setattr(op, "revisar", lambda raiz, config: llamadas.append(raiz) or {
        "datos": {"oportunidades": [{"categoria": "prioritaria"}]}, "llamadas": 3, "incompleta": False})
    config["enProcesador"] = False
    monkeypatch.setattr(op, "cargar_config", lambda: config)
    detalle, firma = procesar.paso_oportunidades(carpeta, None, False)
    assert "apagado" in detalle and firma is None and llamadas == []
    config["enProcesador"] = True
    detalle, firma = procesar.paso_oportunidades(carpeta, None, False)
    assert llamadas == [carpeta] and "1 prioritaria" in detalle and firma == "ok"


def test_sin_palabras_del_rubro_hace_falta_parecerse_en_dos_palabras():
    """Medido con las 5.000 publicadas del 2026-10-13: con una sola palabra en
    común («piscina», «carabineros», «meses») pasaban 376 licitaciones ajenas."""
    h = op.Historia([
        _req(1, "Estanque vertical acero inoxidable", "Adjudicado"),
        _req(2, "Estanque vertical acero 600 litros", "No adjudicado"),
        _req(3, "Estanque vertical acero galvanizado", "Ofertado"),
        _req(4, "Servicio de aseo por 12 meses"),
        _req(5, "Servicio de guardias por 24 meses"),
        _req(6, "Mensajería por 36 meses"),
    ])
    assert h.muy_parecida_ofertada("Estanque vertical de acero") >= op.SIMILITUD_SIN_PALABRAS
    assert h.muy_parecida_ofertada("Estanques autosoportantes para combate de incendios") == 0
    assert h.parecidas("Servicio de aseo por 12 meses para la DOP") == []
    assert h.parecidas("Adquisición de medicamentos por 12 meses") == []   # la duración no hace parecidos


def test_palabras_del_rubro_solo_en_la_descripcion_pesan_menos(evaluador):
    nombre = _evaluar(evaluador, _ficha("1-1-LE26", "Mantención de calderas"))
    descripcion = _evaluar(evaluador, _ficha("1-2-LE26", "Servicio externo de guardavidas",
                                             "Guardavidas para la piscina temperada por 12 meses."))
    assert "solo en la descripción" in descripcion["criterios"]["rubro"]["motivo"]
    assert descripcion["criterios"]["rubro"]["puntaje"] < 40 and descripcion["categoria"] in ("baja", "descartar")
    assert nombre["criterios"]["rubro"]["puntaje"] > descripcion["criterios"]["rubro"]["puntaje"] + 30


def test_varios_recintos_se_busca_en_plural_y_las_frases_con_tilde_igual_calzan(evaluador):
    uno = _evaluar(evaluador, _ficha("1-1-LE26", "Mantención de caldera", "Agua caliente sanitaria al establecimiento."))
    varios = _evaluar(evaluador, _ficha("1-2-LE26", "Mantención de calderas", "Para los establecimientos de la comuna."))
    assert "varios recintos" not in uno["criterios"]["dificultad"]["motivo"]
    assert "varios recintos" in varios["criterios"]["dificultad"]["motivo"]
    assert "calefacción" in _evaluar(evaluador, _ficha("1-3-LE26", "MANTENCION CALEFACCION"))["criterios"]["rubro"]["motivo"]


def test_parecidas_empatadas_muestran_primero_las_recientes(evaluador):
    reqs = [r["req"] for _, r in evaluador.h.parecidas("Mantención de calderas", k=10) if _ == 1.0]
    assert reqs == sorted(reqs, reverse=True)
