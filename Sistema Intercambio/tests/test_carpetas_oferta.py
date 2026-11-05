# -*- coding: utf-8 -*-
"""La carpeta de cada proyecto: nace con su fila en la Planilla y sigue su Estado (carpetas_oferta.py). Bibliotecas
falsas en una carpeta temporal: ninguna prueba toca las reales."""
import json
from datetime import datetime, timedelta

import pytest

import carpetas_oferta as co
import esquemas
import formulaciones
import intercambio

AHORA = datetime(2026, 11, 2, 15, 0).astimezone()
PRESENTADAS = "0 OFERTAS PRESENTADAS"
ADJUDICADAS = "0 OFERTAS ADJUDICADAS"


@pytest.fixture
def e(tmp_path):
    raiz = intercambio.asegurar_carpeta(tmp_path / "Intercambio")
    form = tmp_path / "Formulación de proyectos - Documentos"
    ges = tmp_path / "Gestión de Proyectos - Documentos"
    for c in (PRESENTADAS, ADJUDICADAS, f"{PRESENTADAS}/0 Ofertas Cerradas 2025", "1 CARPETA MODELO"):
        (form / c).mkdir(parents=True)
    for c in ("0 Proyectos Entregados 2026", "0 Carpeta modelo"):
        (ges / c).mkdir(parents=True)
    publicados = []
    return {"raiz": raiz, "form": form, "ges": ges, "estado": tmp_path / "estado.json", "publicados": publicados}


def _planilla(e, *filas):
    intercambio.publicar(e["raiz"], "requerimientos", "planilla-requerimientos",
                         {"requerimientos": [{"numero": n, "estado": est, "titulo": t} for n, est, t in filas]})


def _vuelta(e, ahora=AHORA, **kw):
    return co.vuelta(e["raiz"], e["form"], e["ges"], e["estado"], ahora=ahora, publicar_proyectos=lambda raiz: e["publicados"].append(raiz), **kw)


def _pedir(e, n, estado, minutos=60, **extra):
    enviado = (AHORA - timedelta(minutes=minutos)).isoformat(timespec="seconds")
    m = dict({"esquema": intercambio.ESQUEMA, "id": intercambio.nuevo_id(), "tipo": co.TIPO_MOVER, "destino": co.DESTINO,
              "origen": {"herramienta": "portal", "enviado": enviado, "usuario": "NB"},
              "requerimiento": {"numero": n}, "estado": estado}, **extra)
    intercambio.enviar(e["raiz"], m)
    return m


def _resultados(raiz):
    return {m["id"]: m["resultado"] for m in (json.loads(p.read_text(encoding="utf-8")) for p in (raiz / "procesado").rglob("*.json"))}


def _en_buzon(raiz):
    return [m["id"] for m in intercambio.leer_buzon(raiz, destino=co.DESTINO, tipo=co.TIPO_MOVER)[0]]


def _carpeta(e, ruta, *archivos):
    c = e["form"] / ruta
    c.mkdir(parents=True, exist_ok=True)
    for a in archivos:
        (c / a).write_text("contenido de " + a, encoding="utf-8")
    return c


# ── el nombre ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("titulo,esperado", [
    ("Calefacción gimnasio", "325. Calefacción gimnasio"),
    ("  Doble   espacio ", "325. Doble espacio"),
    ('Con / barra: y "comillas"?', "325. Con - barra- y -comillas"),
    ("Con % y # en el título", "325. Con - y - en el título"),
    ("325. Ya trae su N°", "325. Ya trae su N°"),
    ("324. Trae otro N°", "325. 324. Trae otro N°"),
    ("Termina en punto.", "325. Termina en punto"),
    ("X" * 200, "325. " + "X" * 65),
    ("", ""),
    (None, ""),
])
def test_el_nombre_de_una_carpeta_nueva(titulo, esperado):
    assert co.nombre_carpeta(325, titulo) == esperado


def test_el_nombre_largo_cabe_en_lo_que_abre_excel():
    ruta = "C:\\Users\\quemp\\OneDrive - QUEMPIN SPA\\Formulación de proyectos - Documentos\\0 OFERTAS PRESENTADAS\\0 Ofertas Cerradas 2026\\"
    assert len(ruta + co.nombre_carpeta(325, "X" * 200) + "\\Formulación 325 v1.xlsx") <= 218


def test_solo_cuenta_como_numero_el_que_lleva_punto():
    assert co.numero_de("325. Obra") == 325
    assert co.numero_de("3474-93-LE25, PROVISIÓN") is None     # un ID de Mercado Público, no un N°
    assert co.numero_de("Sin número") is None


# ── el plan ──────────────────────────────────────────────────────────────────

def test_cada_estado_dice_adonde_va_la_carpeta():
    f = lambda est, ruta: (co.plan(est, ruta, None, 2026)["formulacion"] or {}).get("hasta")  # noqa: E731
    obra = ["325. Obra"]
    assert f("Evaluación", obra) is None
    assert f("Ofertado", obra) == [PRESENTADAS]
    assert f("No adjudicado", obra) == [PRESENTADAS, "0 Ofertas Cerradas 2026"]
    assert f("Descartado", obra) == [PRESENTADAS, "0 Ofertas Cerradas 2026"]
    assert f("Adjudicado", obra) == [ADJUDICADAS]
    assert f("Post-venta", obra) == [ADJUDICADAS]
    assert f("Cerrado", obra) == [ADJUDICADAS]
    assert f("Evaluación", [PRESENTADAS, "325. Obra"]) == []


def test_una_carpeta_en_cerradas_de_otro_anio_no_se_mueve_otra_vez():
    p = co.plan("Descartado", [PRESENTADAS, "0 Ofertas Cerradas 2025", "325. Obra"], None, 2026)
    assert p["formulacion"] is None and p["gestion"] is None
    p = co.plan("Cerrado", None, ["0 Proyectos Entregados 2025", "325. Obra"], 2026)
    assert p["gestion"] is None


def test_gestion_solo_se_crea_al_adjudicarse():
    assert co.plan("Adjudicado", ["325. Obra"], None, 2026)["gestion"] == {"accion": "crear", "desde": None, "hasta": []}
    # Un proyecto antiguo puede tener su carpeta en Gestión sin N° («USACH»): crear otra la duplicaría
    assert co.plan("Post-venta", ["325. Obra"], None, 2026)["gestion"] is None
    assert co.plan("Cerrado", ["325. Obra"], None, 2026)["gestion"] is None


def test_cerrado_y_reabierto_mueven_la_carpeta_de_gestion():
    p = co.plan("Cerrado", [ADJUDICADAS, "325. Obra"], ["325. Obra"], 2026)
    assert p["formulacion"] is None
    assert p["gestion"] == {"accion": "mover", "desde": [], "hasta": ["0 Proyectos Entregados 2026"]}
    p = co.plan("Post-venta", [ADJUDICADAS, "325. Obra"], ["0 Proyectos Entregados 2026", "325. Obra"], 2026)
    assert p["gestion"] == {"accion": "mover", "desde": ["0 Proyectos Entregados 2026"], "hasta": []}


def test_volver_atras_no_toca_la_copia_de_gestion():
    p = co.plan("Ofertado", [ADJUDICADAS, "325. Obra"], ["325. Obra"], 2026)
    assert p["formulacion"]["hasta"] == [PRESENTADAS] and p["gestion"] is None


# ── crear ────────────────────────────────────────────────────────────────────

def test_la_primera_vez_no_crea_nada_y_lo_de_antes_queda_conocido(e):
    _planilla(e, (320, "Evaluación", "Sin carpeta de antes"), (321, "Ofertado", "Otra de antes"))
    r = _vuelta(e)
    assert r["creadas"] == []
    assert not (e["form"] / "320. Sin carpeta de antes").exists()
    r = _vuelta(e, ahora=AHORA + timedelta(hours=2))
    assert r["creadas"] == [] and not (e["form"] / "320. Sin carpeta de antes").exists()


def test_una_fila_nueva_tiene_su_carpeta_con_la_estructura_de_siempre(e):
    _planilla(e, (320, "Evaluación", "De antes"))
    _vuelta(e)
    _planilla(e, (320, "Evaluación", "De antes"), (325, "Evaluación", "Calefacción gimnasio"))
    # La primera vuelta que la ve espera: si la creó el Portal en otro computador, OneDrive todavía la está trayendo
    assert _vuelta(e, ahora=AHORA + timedelta(minutes=10))["creadas"] == []
    assert not (e["form"] / "325. Calefacción gimnasio").exists()
    r = _vuelta(e, ahora=AHORA + timedelta(minutes=30))
    assert r["creadas"] == ["325. Calefacción gimnasio"]
    assert sorted(h.name for h in (e["form"] / "325. Calefacción gimnasio").iterdir()) == sorted(co.ESTRUCTURA)
    assert _vuelta(e, ahora=AHORA + timedelta(minutes=60))["creadas"] == []


def test_la_estructura_es_la_medida_en_las_bibliotecas():
    assert co.ESTRUCTURA == ("ANTECEDENTES", "DOCUMENTOS EN TRABAJO", "ENTREGABLES", "VISITA TÉCNICA")


def test_si_otro_ya_creo_la_carpeta_no_se_duplica(e):
    _planilla(e, (320, "Evaluación", "De antes"))
    _vuelta(e)
    _planilla(e, (320, "Evaluación", "De antes"), (325, "Evaluación", "Otro nombre"))
    _vuelta(e, ahora=AHORA + timedelta(minutes=10))
    _carpeta(e, "325. Hecha a mano")
    r = _vuelta(e, ahora=AHORA + timedelta(minutes=30))
    assert r["creadas"] == [] and not (e["form"] / "325. Otro nombre").exists()


def test_lo_que_entra_descartado_o_sin_titulo_no_tiene_carpeta(e):
    _planilla(e, (320, "Evaluación", "De antes"))
    _vuelta(e)
    _planilla(e, (320, "Evaluación", "De antes"), (325, "Descartado", "No se oferta"), (326, "Evaluación", None))
    _vuelta(e, ahora=AHORA + timedelta(minutes=10))
    r = _vuelta(e, ahora=AHORA + timedelta(minutes=30))
    assert r["creadas"] == []
    # Con su título, sí
    _planilla(e, (320, "Evaluación", "De antes"), (325, "Descartado", "No se oferta"), (326, "Evaluación", "Ya tiene título"))
    _vuelta(e, ahora=AHORA + timedelta(minutes=40))
    assert _vuelta(e, ahora=AHORA + timedelta(minutes=60))["creadas"] == ["326. Ya tiene título"]


def test_una_fila_nueva_ya_adjudicada_queda_donde_corresponde(e):
    _planilla(e, (320, "Evaluación", "De antes"))
    _vuelta(e)
    _planilla(e, (320, "Evaluación", "De antes"), (325, "Adjudicado", "Reparación postventa"))
    _vuelta(e, ahora=AHORA + timedelta(minutes=10))
    _vuelta(e, ahora=AHORA + timedelta(minutes=30))
    assert (e["form"] / ADJUDICADAS / "325. Reparación postventa" / "ANTECEDENTES").is_dir()
    assert (e["ges"] / "325. Reparación postventa" / "Formulación" / "ANTECEDENTES").is_dir()


def test_el_requerimiento_que_cambio_de_numero_se_lleva_su_carpeta(e):
    _planilla(e, (325, "Evaluación", "Ajena"), (326, "Evaluación", "Mía"))
    _vuelta(e)
    _carpeta(e, "325. Mía", "bases.pdf")
    r = _vuelta(e, ahora=AHORA + timedelta(minutes=10), renumerados=[(325, 326, "Mía")])
    assert r["renombradas"] == ["325. Mía → 326. Mía"]
    assert (e["form"] / "326. Mía" / "bases.pdf").is_file() and not (e["form"] / "325. Mía").exists()


def test_el_cambio_de_numero_espera_a_que_llegue_la_carpeta(e):
    _planilla(e, (325, "Evaluación", "Ajena"), (326, "Evaluación", "Mía"))
    _vuelta(e)
    assert _vuelta(e, ahora=AHORA + timedelta(minutes=10), renumerados=[(325, 326, "Mía")])["renombradas"] == []
    _carpeta(e, "325. Mía")
    assert _vuelta(e, ahora=AHORA + timedelta(minutes=20))["renombradas"] == ["325. Mía → 326. Mía"]


# ── mover ────────────────────────────────────────────────────────────────────

def test_ofertar_lleva_la_carpeta_a_presentadas(e):
    _carpeta(e, "325. Obra", "bases.pdf")
    _planilla(e, (325, "Ofertado", "Obra"))
    m = _pedir(e, 325, "Ofertado")
    r = _vuelta(e)
    assert [x["nombre"] for x in r["movidas"]] == ["325. Obra"]
    assert (e["form"] / PRESENTADAS / "325. Obra" / "bases.pdf").is_file() and not (e["form"] / "325. Obra").exists()
    resultado = _resultados(e["raiz"])[m["id"]]
    assert resultado["estado"] == "aplicado" and resultado["requerimiento"] == 325
    assert "Formulación de proyectos a Formulación de proyectos › 0 OFERTAS PRESENTADAS" in resultado["detalle"][0]


def test_perder_la_lleva_a_cerradas_del_anio(e):
    _carpeta(e, f"{PRESENTADAS}/325. Obra")
    _planilla(e, (325, "No adjudicado", "Obra"))
    _pedir(e, 325, "No adjudicado")
    _vuelta(e)
    assert (e["form"] / PRESENTADAS / "0 Ofertas Cerradas 2026" / "325. Obra").is_dir()


def test_adjudicar_copia_a_gestion_y_deja_el_original_en_adjudicadas(e):
    _carpeta(e, f"{PRESENTADAS}/325. Obra/ANTECEDENTES", "bases.pdf")
    (e["form"] / PRESENTADAS / "325. Obra" / "desktop.ini").write_text("x", encoding="utf-8")
    _planilla(e, (325, "Adjudicado", "Obra"))
    m = _pedir(e, 325, "Adjudicado")
    _vuelta(e)
    assert (e["form"] / ADJUDICADAS / "325. Obra" / "ANTECEDENTES" / "bases.pdf").is_file()
    assert not (e["form"] / PRESENTADAS / "325. Obra").exists()
    assert (e["ges"] / "325. Obra" / "Formulación" / "ANTECEDENTES" / "bases.pdf").read_text(encoding="utf-8") == "contenido de bases.pdf"
    assert not (e["ges"] / "325. Obra" / "Formulación" / "desktop.ini").exists()
    assert _resultados(e["raiz"])[m["id"]]["estado"] == "aplicado"


def test_cerrado_lleva_la_carpeta_de_gestion_a_entregados_y_reabrirlo_la_devuelve(e):
    _carpeta(e, f"{ADJUDICADAS}/325. Obra")
    (e["ges"] / "325. Obra" / "Formulación").mkdir(parents=True)
    _planilla(e, (325, "Cerrado", "Obra"))
    _pedir(e, 325, "Cerrado")
    _vuelta(e)
    assert (e["ges"] / "0 Proyectos Entregados 2026" / "325. Obra" / "Formulación").is_dir()
    assert (e["form"] / ADJUDICADAS / "325. Obra").is_dir()
    _planilla(e, (325, "Post-venta", "Obra"))
    _pedir(e, 325, "Post-venta")
    _vuelta(e)
    assert (e["ges"] / "325. Obra").is_dir() and not (e["ges"] / "0 Proyectos Entregados 2026" / "325. Obra").exists()


def test_entregados_del_anio_se_crea_si_no_existe(e):
    (e["ges"] / "0 Proyectos Entregados 2026").rmdir()
    (e["ges"] / "325. Obra").mkdir()
    _planilla(e, (325, "Cerrado", "Obra"))
    _pedir(e, 325, "Cerrado")
    _vuelta(e)
    assert (e["ges"] / "0 Proyectos Entregados 2026" / "325. Obra").is_dir()


def test_mover_espera_a_que_la_planilla_diga_ese_estado(e):
    _carpeta(e, "325. Obra")
    _planilla(e, (325, "Evaluación", "Obra"))
    m = _pedir(e, 325, "Ofertado", minutos=5)
    r = _vuelta(e)
    assert "espera que la Planilla" in r["esperan"][0] and m["id"] in _en_buzon(e["raiz"])
    assert (e["form"] / "325. Obra").is_dir()


def test_si_la_planilla_quedo_con_otro_estado_la_carpeta_no_se_mueve(e):
    _carpeta(e, "325. Obra")
    _planilla(e, (325, "Evaluación", "Obra"))
    m = _pedir(e, 325, "Ofertado", minutos=45)
    _vuelta(e)
    assert (e["form"] / "325. Obra").is_dir()
    resultado = _resultados(e["raiz"])[m["id"]]
    assert resultado["estado"] == "reemplazado" and "«Evaluación»" in resultado["detalle"][0]


def test_mientras_el_cambio_de_estado_espera_en_el_buzon_el_mover_tambien(e):
    _carpeta(e, "325. Obra")
    _planilla(e, (325, "Evaluación", "Obra"))
    intercambio.enviar(e["raiz"], {"esquema": intercambio.ESQUEMA, "id": intercambio.nuevo_id(), "tipo": "editar-requerimiento",
                                   "destino": "planilla-requerimientos", "origen": {"herramienta": "portal", "enviado": AHORA.isoformat()},
                                   "requerimiento": {"numero": 325}, "cambios": {"estado": "Ofertado"}})
    m = _pedir(e, 325, "Ofertado", minutos=120)
    _vuelta(e)
    assert m["id"] in _en_buzon(e["raiz"])


def test_de_dos_pedidos_para_el_mismo_numero_vale_el_ultimo(e):
    _carpeta(e, "325. Obra")
    _planilla(e, (325, "Ofertado", "Obra"))
    primero = _pedir(e, 325, "Adjudicado", minutos=30)
    segundo = _pedir(e, 325, "Ofertado", minutos=10)
    _vuelta(e)
    resultados = _resultados(e["raiz"])
    assert resultados[primero["id"]]["estado"] == "reemplazado" and resultados[segundo["id"]]["estado"] == "aplicado"
    assert (e["form"] / PRESENTADAS / "325. Obra").is_dir() and not (e["ges"] / "325. Obra").exists()


def test_con_dos_carpetas_del_mismo_numero_decide_una_persona(e):
    _carpeta(e, "325. Obra")
    _carpeta(e, f"{PRESENTADAS}/325. Otra")
    _planilla(e, (325, "Ofertado", "Obra"))
    m = _pedir(e, 325, "Ofertado")
    _vuelta(e)
    assert (e["form"] / "325. Obra").is_dir() and (e["form"] / PRESENTADAS / "325. Otra").is_dir()
    assert _resultados(e["raiz"])[m["id"]]["estado"] == "rechazado"


def test_sin_carpeta_no_hay_nada_que_mover(e):
    _planilla(e, (325, "Ofertado", "Obra"))
    m = _pedir(e, 325, "Ofertado")
    _vuelta(e)
    assert _resultados(e["raiz"])[m["id"]]["estado"] == "sin-cambios"


def test_ya_en_su_lugar_no_hace_nada(e):
    _carpeta(e, f"{PRESENTADAS}/325. Obra")
    _planilla(e, (325, "Ofertado", "Obra"))
    m = _pedir(e, 325, "Ofertado")
    r = _vuelta(e)
    assert r["movidas"] == [] and _resultados(e["raiz"])[m["id"]]["estado"] == "sin-cambios"


def test_crear_desde_el_boton_del_portal(e):
    _planilla(e, (325, "Evaluación", "Obra sin carpeta"))
    m = _pedir(e, 325, "Evaluación", crear=True)
    r = _vuelta(e)
    assert r["creadas"] == ["325. Obra sin carpeta"]
    assert (e["form"] / "325. Obra sin carpeta" / "VISITA TÉCNICA").is_dir()
    assert _resultados(e["raiz"])[m["id"]]["estado"] == "sin-cambios"


def test_una_carpeta_ocupada_se_reintenta_y_no_se_pierde_el_pedido(e, monkeypatch):
    _carpeta(e, "325. Obra")
    _planilla(e, (325, "Ofertado", "Obra"))
    m = _pedir(e, 325, "Ofertado")
    real = co.os.rename

    def ocupada(a, b):
        raise PermissionError("en uso")

    monkeypatch.setattr(co.os, "rename", ocupada)
    r = _vuelta(e)
    assert "archivo abierto" in r["esperan"][0] and m["id"] in _en_buzon(e["raiz"])
    monkeypatch.setattr(co.os, "rename", real)
    _vuelta(e)
    assert (e["form"] / PRESENTADAS / "325. Obra").is_dir()
    assert _resultados(e["raiz"])[m["id"]]["estado"] == "aplicado"


def test_ocupada_por_mas_de_una_semana_se_rechaza_con_el_motivo(e, monkeypatch):
    _carpeta(e, "325. Obra")
    _planilla(e, (325, "Ofertado", "Obra"))
    m = _pedir(e, 325, "Ofertado", minutos=8 * 24 * 60)

    def ocupada(a, b):
        raise PermissionError("en uso")

    monkeypatch.setattr(co.os, "rename", ocupada)
    _vuelta(e)
    resultado = _resultados(e["raiz"])[m["id"]]
    assert resultado["estado"] == "rechazado" and "Pídelo de nuevo" in resultado["detalle"][0]


def test_si_ya_hay_otra_con_ese_nombre_en_el_destino_no_se_pisa(e):
    _carpeta(e, "325. Obra", "mio.pdf")
    _carpeta(e, f"{PRESENTADAS}/325. Obra", "suyo.pdf")
    _planilla(e, (325, "Ofertado", "Obra"))
    m = _pedir(e, 325, "Ofertado", minutos=60)
    _vuelta(e)
    # Dos con el mismo N°: lo decide una persona, y las dos quedan como estaban
    assert (e["form"] / "325. Obra" / "mio.pdf").is_file() and (e["form"] / PRESENTADAS / "325. Obra" / "suyo.pdf").is_file()
    assert _resultados(e["raiz"])[m["id"]]["estado"] == "rechazado"


def test_una_copia_grande_sigue_en_la_vuelta_siguiente(e):
    c = _carpeta(e, f"{PRESENTADAS}/325. Obra", "a.pdf", "b.pdf")
    _planilla(e, (325, "Adjudicado", "Obra"))
    m = _pedir(e, 325, "Adjudicado")
    r = _vuelta(e, segundos=-1)
    assert "sigue en la próxima vuelta" in r["esperan"][0]
    assert (e["ges"] / "325. Obra" / "Formulación (copiando)").is_dir() and not (e["ges"] / "325. Obra" / "Formulación").exists()
    assert m["id"] in _en_buzon(e["raiz"]) and c.is_dir()
    _vuelta(e)
    assert (e["ges"] / "325. Obra" / "Formulación" / "b.pdf").is_file() and not (e["ges"] / "325. Obra" / "Formulación (copiando)").exists()
    assert (e["form"] / ADJUDICADAS / "325. Obra" / "a.pdf").is_file()


def test_una_carpeta_de_gestion_que_ya_tiene_su_copia_no_se_toca(e):
    (e["ges"] / "325. Obra" / "Formulación").mkdir(parents=True)
    (e["ges"] / "325. Obra" / "Formulación" / "de-antes.pdf").write_text("x", encoding="utf-8")
    _carpeta(e, f"{PRESENTADAS}/325. Obra", "nuevo.pdf")
    _planilla(e, (325, "Adjudicado", "Obra"))
    _pedir(e, 325, "Adjudicado")
    _vuelta(e)
    assert not (e["ges"] / "325. Obra" / "Formulación" / "nuevo.pdf").exists()
    assert (e["ges"] / "325. Obra" / "Formulación" / "de-antes.pdf").is_file()
    assert (e["form"] / ADJUDICADAS / "325. Obra").is_dir()


def test_a_una_carpeta_de_gestion_hecha_a_mano_se_le_agrega_la_copia(e):
    (e["ges"] / "325. Obra" / "Compras").mkdir(parents=True)
    _carpeta(e, f"{PRESENTADAS}/325. Obra", "bases.pdf")
    _planilla(e, (325, "Adjudicado", "Obra"))
    m = _pedir(e, 325, "Adjudicado")
    _vuelta(e)
    assert (e["ges"] / "325. Obra" / "Formulación" / "bases.pdf").is_file() and (e["ges"] / "325. Obra" / "Compras").is_dir()
    assert "quedó con la copia" in _resultados(e["raiz"])[m["id"]]["detalle"][0]


def test_el_mensaje_invalido_se_rechaza(e):
    _planilla(e, (325, "Ofertado", "Obra"))
    m = _pedir(e, 325, "Inventado")
    _vuelta(e)
    assert _resultados(e["raiz"])[m["id"]]["estado"] == "rechazado"


def test_la_ruta_no_viene_del_mensaje():
    assert "ruta" not in json.dumps(esquemas.cargar("mensajes/mover-carpeta")["properties"])


def test_simular_no_toca_nada(e):
    _carpeta(e, "325. Obra")
    _planilla(e, (325, "Ofertado", "Obra"))
    m = _pedir(e, 325, "Ofertado")
    r = co.vuelta(e["raiz"], e["form"], e["ges"], e["estado"], simular=True, ahora=AHORA)
    assert [x["nombre"] for x in r["movidas"]] == ["325. Obra"]
    assert (e["form"] / "325. Obra").is_dir() and m["id"] in _en_buzon(e["raiz"]) and not e["estado"].exists()


# ── proyectos.json ───────────────────────────────────────────────────────────

def test_proyectos_se_republica_solo_si_cambio_alguna_carpeta(e):
    _carpeta(e, "325. Obra")
    _planilla(e, (325, "Evaluación", "Obra"))
    _vuelta(e)
    assert len(e["publicados"]) == 1
    _vuelta(e)
    assert len(e["publicados"]) == 1
    _carpeta(e, "326. Otra hecha a mano")
    _vuelta(e)
    assert len(e["publicados"]) == 2


# ── el estado que llega al Formulador ────────────────────────────────────────

def _formulacion(raiz, uid, estado, req, codigo=None, version=1, mod="2026-10-01T10:00:00.000Z", carpeta=None, eliminado=False):
    datos = {"uid": uid, "estado": estado, "codigo": codigo or f"QMPN-2026-{uid}", "version": version, "modificado": mod, "titulo": "Obra",
             "vinculos": {"requerimiento": {"numero": str(req)}}}
    if carpeta:
        datos["vinculos"]["carpetaOferta"] = {"nombre": carpeta, "ruta": [carpeta]}
    if eliminado:
        datos["eliminado"] = True
    formulaciones._escribir(raiz, datos, ["2026-09-01T10:00:00.000Z"], {"precioNeto": 100}, "NB")


def _datos(raiz, uid):
    return json.loads((raiz / "publicado" / "formulador" / f"{uid}.json").read_text(encoding="utf-8"))


def test_un_cambio_en_la_planilla_llega_al_formulador(e):
    _formulacion(e["raiz"], "aaa", "Enviada", 325)
    _planilla(e, (325, "Ofertado", "Obra"))
    _vuelta(e)
    assert _datos(e["raiz"], "aaa")["datos"]["estado"] == "Enviada"
    _planilla(e, (325, "Cerrado", "Obra"))
    r = _vuelta(e)
    assert r["alineadas"] == ["QMPN-2026-aaa v1 «Obra» → Cerrada"]
    sobre = _datos(e["raiz"], "aaa")
    assert sobre["datos"]["estado"] == "Cerrada" and sobre["datos"]["modificadoPor"] == "Planilla de Ingreso"
    # Una versión nueva que viene de la anterior: así cada navegador la trae sin conflicto (js/compartida.js)
    assert sobre["historia"][-1] == "2026-10-01T10:00:00.000Z" and sobre["datos"]["modificado"] > "2026-10-01"
    assert sobre["resumen"] == {"precioNeto": 100}


def test_lo_que_ya_estaba_distinto_no_se_toca_la_primera_vez(e):
    _formulacion(e["raiz"], "aaa", "Borrador", 325)
    _planilla(e, (325, "Ofertado", "Obra"))
    assert _vuelta(e)["alineadas"] == []
    assert _vuelta(e)["alineadas"] == []
    assert _datos(e["raiz"], "aaa")["datos"]["estado"] == "Borrador"


def test_lo_cambiado_en_el_formulador_no_se_le_devuelve(e):
    _formulacion(e["raiz"], "aaa", "Enviada", 325)
    _planilla(e, (325, "Ofertado", "Obra"))
    _vuelta(e)
    _planilla(e, (325, "Adjudicado", "Obra"))
    assert _vuelta(e, del_formulador=[325])["alineadas"] == []
    assert _datos(e["raiz"], "aaa")["datos"]["estado"] == "Enviada"


def test_borrador_y_en_revision_son_evaluacion_y_volver_atras_llega(e):
    _formulacion(e["raiz"], "aaa", "Borrador", 325)
    _formulacion(e["raiz"], "bbb", "Enviada", 326)
    _planilla(e, (325, "Ofertado", "A"), (326, "Ofertado", "B"))
    _vuelta(e)
    _planilla(e, (325, "Evaluación", "A"), (326, "Evaluación", "B"))
    r = _vuelta(e)
    assert r["alineadas"] == ["QMPN-2026-bbb v1 «Obra» → En revisión"]
    assert _datos(e["raiz"], "aaa")["datos"]["estado"] == "Borrador"


def test_un_presupuesto_en_edicion_espera_la_vuelta_siguiente(e):
    reciente = (AHORA - timedelta(minutes=3)).isoformat(timespec="seconds")
    _formulacion(e["raiz"], "aaa", "Enviada", 325, mod=reciente)
    _planilla(e, (325, "Ofertado", "Obra"))
    _vuelta(e)
    _planilla(e, (325, "Adjudicado", "Obra"))
    assert _vuelta(e)["alineadas"] == []
    assert _datos(e["raiz"], "aaa")["datos"]["estado"] == "Enviada"
    assert len(_vuelta(e, ahora=AHORA + timedelta(minutes=20))["alineadas"]) == 1
    assert _datos(e["raiz"], "aaa")["datos"]["estado"] == "Adjudicada"


def test_un_vinculo_en_duda_no_se_toca(e):
    # 2026-11-02, real: «314. UA Reactor» está unido al N° 313, que es otro requerimiento
    _formulacion(e["raiz"], "aaa", "Borrador", 313, codigo="314. UA Reactor", carpeta="314. UA Reactor")
    _planilla(e, (313, "Evaluación", "Otra cosa"))
    _vuelta(e)
    _planilla(e, (313, "Descartado", "Otra cosa"))
    assert _vuelta(e)["alineadas"] == []
    assert _datos(e["raiz"], "aaa")["datos"]["estado"] == "Borrador"


def test_llega_al_presupuesto_que_manda_de_ese_numero(e):
    _formulacion(e["raiz"], "v1", "Enviada", 325, codigo="325. Obra", version=1, mod="2026-10-05T10:00:00.000Z")
    _formulacion(e["raiz"], "v2", "Enviada", 325, codigo="325. Obra", version=2, mod="2026-10-03T10:00:00.000Z")
    _formulacion(e["raiz"], "borrador", "Enviada", 325, codigo="QMPN-2026-9", mod="2026-09-01T10:00:00.000Z")
    _formulacion(e["raiz"], "papelera", "Enviada", 325, codigo="QMPN-2026-8", mod="2026-10-20T10:00:00.000Z", eliminado=True)
    _planilla(e, (325, "Ofertado", "Obra"))
    _vuelta(e)
    _planilla(e, (325, "Adjudicado", "Obra"))
    _vuelta(e)
    estados = {u: _datos(e["raiz"], u)["datos"]["estado"] for u in ("v1", "v2", "borrador", "papelera")}
    assert estados == {"v1": "Enviada", "v2": "Adjudicada", "borrador": "Enviada", "papelera": "Enviada"}


def test_una_fila_nueva_no_le_cambia_el_estado_a_su_proyecto(e):
    _formulacion(e["raiz"], "aaa", "Enviada", 325)
    _planilla(e, (320, "Evaluación", "Otra"))
    _vuelta(e)
    _planilla(e, (320, "Evaluación", "Otra"), (325, "Evaluación", "Obra"))
    assert _vuelta(e)["alineadas"] == []
    assert _datos(e["raiz"], "aaa")["datos"]["estado"] == "Enviada"
