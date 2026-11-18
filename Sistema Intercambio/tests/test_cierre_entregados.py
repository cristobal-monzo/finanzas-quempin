# -*- coding: utf-8 -*-
"""Lo que está en «0 Proyectos Entregados» pasa a «Cerrado» en la Planilla, y el Portal puede pedir llevar ahí la
carpeta al cerrar un proyecto (cierre_entregados.py, 2026-11-09). Bibliotecas falsas en una carpeta temporal."""
import os
from datetime import datetime, timedelta

import pytest

import cierre_entregados as ce
import esquemas
import intercambio
import procesar
import requerimientos as rq

ANIO = datetime.now().year


def _req(n, estado, titulo=None):
    return {"numero": n, "estado": estado, "titulo": titulo or f"Proyecto {n}"}


@pytest.fixture
def e(tmp_path):
    raiz = intercambio.asegurar_carpeta(tmp_path / "Intercambio")
    gestion = tmp_path / "Gestión de Proyectos - Documentos"
    (gestion / "289. Instalación de prueba" / "Compras").mkdir(parents=True)
    (gestion / "0 Carpeta modelo").mkdir()
    (gestion / f"0 Proyectos Entregados {ANIO}" / "296. Caldera de prueba").mkdir(parents=True)
    (gestion / f"0 Proyectos Entregados {ANIO}" / "Sin número de prueba").mkdir()            # sin N°: no se puede cruzar
    (gestion / "0 Proyectos Entregados 2025" / "Otra sin número").mkdir(parents=True)
    _planilla(raiz, [_req(289, "Adjudicado", "INSTALACIÓN DE PRUEBA"), _req(296, "Adjudicado", "Sala de calderas de prueba")])
    return {"raiz": raiz, "gestion": gestion}


def _planilla(raiz, reqs):
    intercambio.publicar(raiz, "requerimientos", "procesador", {"requerimientos": reqs}, validar=False)   # parcial


def _buzon(raiz, tipo=None):
    return intercambio.leer_buzon(raiz, tipo=tipo)[0]


def _procesados(raiz):
    return [intercambio._leer_json(p) for p in (raiz / intercambio.CARPETA_PROCESADO).rglob("*.json")]


def _mover(raiz, n, minutos=-60, titulo=None):
    enviado = (datetime.now().astimezone() + timedelta(minutes=minutos)).isoformat(timespec="seconds")
    m = {"esquema": intercambio.ESQUEMA, "id": intercambio.nuevo_id(), "tipo": ce.TIPO_MOVER, "destino": ce.DESTINO,
         "origen": {"herramienta": "portal", "usuario": "NB", "enviado": enviado},
         "requerimiento": {"numero": n, **({"titulo": titulo} if titulo else {})}, "estado": "Cerrado"}
    assert esquemas.validar_mensaje(m) == []
    intercambio.enviar(raiz, m)
    return m


def _editar_cerrado(raiz, n, herramienta="portal"):
    m = {"esquema": intercambio.ESQUEMA, "id": intercambio.nuevo_id(), "tipo": "editar-requerimiento",
         "destino": rq.DESTINO, "origen": {"herramienta": herramienta, "enviado": intercambio.ahora_iso()},
         "requerimiento": {"numero": n}, "cambios": {"estado": "Cerrado"}, "reemplaza": {"estado": "Adjudicado"}}
    intercambio.enviar(raiz, m)


# ── las carpetas ────────────────────────────────────────────────────────────

def test_lee_las_carpetas_entregadas_de_todos_los_anios(e):
    vistas = {(x["grupo"], x["carpeta"], x["req"]) for x in ce.entregadas(e["gestion"])}
    assert vistas == {(f"0 Proyectos Entregados {ANIO}", "296. Caldera de prueba", 296), (f"0 Proyectos Entregados {ANIO}", "Sin número de prueba", None),
                      ("0 Proyectos Entregados 2025", "Otra sin número", None)}
    assert set(ce.en_raiz(e["gestion"])) == {289}


def test_un_n_temporal_no_es_de_la_planilla(e):
    (e["gestion"] / f"0 Proyectos Entregados {ANIO}" / "001t. Sin número").mkdir()
    assert [x["req"] for x in ce.entregadas(e["gestion"]) if x["carpeta"].startswith("001t")] == [None]


# ── cerrar lo que se movió a mano ───────────────────────────────────────────

def test_lo_movido_a_mano_pide_cerrado_a_la_planilla(e):
    detalle, estado, _ = ce.vuelta(e["raiz"], e["gestion"], {})
    (m,) = _buzon(e["raiz"], "editar-requerimiento")
    assert esquemas.validar_mensaje(m) == []
    assert m["destino"] == "planilla-requerimientos" and m["origen"]["herramienta"] == "procesador"
    assert m["requerimiento"] == {"numero": 296, "titulo": "Sala de calderas de prueba"}      # confirma la fila
    assert m["cambios"] == {"estado": "Cerrado"} and m["reemplaza"] == {"estado": "Adjudicado"}
    assert set(estado["cerrados"]) == {"296"}
    assert "N° 296" in detalle and "1 carpeta(s) sin N°" not in detalle and "2 carpeta(s) sin N°" in detalle


def test_no_se_pide_dos_veces(e):
    _, estado, _ = ce.vuelta(e["raiz"], e["gestion"], {})
    # Mientras espera en el buzón, y después de escrito en la Planilla
    ce.vuelta(e["raiz"], e["gestion"], estado)
    assert len(_buzon(e["raiz"], "editar-requerimiento")) == 1
    for m in _buzon(e["raiz"], "editar-requerimiento"):
        intercambio.archivar(e["raiz"], m, "aplicado")
    _planilla(e["raiz"], [_req(289, "Adjudicado"), _req(296, "Cerrado")])
    detalle, _, _ = ce.vuelta(e["raiz"], e["gestion"], estado)
    assert _buzon(e["raiz"], "editar-requerimiento") == [] and "1 ya cerrados" in detalle


def test_si_alguien_lo_reabre_se_respeta(e):
    _, estado, _ = ce.vuelta(e["raiz"], e["gestion"], {})
    for m in _buzon(e["raiz"], "editar-requerimiento"):
        intercambio.archivar(e["raiz"], m, "aplicado")
    # Alguien lo dejó de nuevo en «Adjudicado» en el Excel, con la carpeta todavía en los entregados
    ce.vuelta(e["raiz"], e["gestion"], estado)
    assert _buzon(e["raiz"], "editar-requerimiento") == []


def test_si_el_portal_ya_lo_pidio_no_se_repite(e):
    _editar_cerrado(e["raiz"], 296)
    _, estado, _ = ce.vuelta(e["raiz"], e["gestion"], {})
    assert len(_buzon(e["raiz"], "editar-requerimiento")) == 1 and estado["cerrados"] == {}


@pytest.mark.parametrize("estado", ["Evaluación", "Ofertado", "No adjudicado", "Descartado", None])
def test_solo_se_cierra_lo_adjudicado(e, estado):
    _planilla(e["raiz"], [_req(296, estado)])
    detalle, _, avisos = ce.vuelta(e["raiz"], e["gestion"], {})
    assert _buzon(e["raiz"], "editar-requerimiento") == []
    assert any("N° 296" in a and "no se cerró" in a for a in avisos) and "revisar" in detalle


def test_un_n_que_no_esta_en_la_planilla_queda_como_aviso(e):
    _planilla(e["raiz"], [_req(289, "Adjudicado")])
    _, _, avisos = ce.vuelta(e["raiz"], e["gestion"], {})
    assert _buzon(e["raiz"], "editar-requerimiento") == [] and any("no está en la Planilla" in a for a in avisos)


def test_un_n_copiado_y_no_movido_no_se_cierra(e):
    (e["gestion"] / "296. Caldera de prueba").mkdir()
    _, _, avisos = ce.vuelta(e["raiz"], e["gestion"], {})
    assert _buzon(e["raiz"], "editar-requerimiento") == [] and any("también en la raíz" in a for a in avisos)


def test_dos_carpetas_con_el_mismo_n_en_los_entregados_no_se_cierran(e):
    (e["gestion"] / "0 Proyectos Entregados 2025" / "296. Otra de prueba").mkdir()
    _, _, avisos = ce.vuelta(e["raiz"], e["gestion"], {})
    assert _buzon(e["raiz"], "editar-requerimiento") == [] and any("2 carpetas" in a for a in avisos)


def test_muchos_de_una_vez_esperan_que_una_persona_confirme(e):
    reqs = [_req(289, "Adjudicado")]
    for n in range(500, 500 + ce.MAX_CIERRES + 1):
        (e["gestion"] / "0 Proyectos Entregados 2025" / f"{n}. Viejo {n}").mkdir()
        reqs.append(_req(n, "Adjudicado"))
    _planilla(e["raiz"], reqs + [_req(296, "Cerrado")])
    _, estado, avisos = ce.vuelta(e["raiz"], e["gestion"], {})
    assert _buzon(e["raiz"], "editar-requerimiento") == [] and estado["cerrados"] == {}
    assert any("--confirmar" in a for a in avisos)
    resumen, estado = ce.pedir_cierres(e["raiz"], e["gestion"], estado, confirmar=True)
    assert len(resumen["pedidos"]) == ce.MAX_CIERRES + 1 == len(_buzon(e["raiz"], "editar-requerimiento"))


# ── mover lo que pidió el Portal ────────────────────────────────────────────

def test_mueve_la_carpeta_cuando_el_cerrado_espera_en_el_buzon(e):
    _editar_cerrado(e["raiz"], 289)
    _mover(e["raiz"], 289)
    detalle, estado, _ = ce.vuelta(e["raiz"], e["gestion"], {})
    destino = e["gestion"] / f"0 Proyectos Entregados {ANIO}" / "289. Instalación de prueba"
    assert destino.is_dir() and (destino / "Compras").is_dir() and not (e["gestion"] / "289. Instalación de prueba").exists()
    (p,) = [x for x in _procesados(e["raiz"]) if x["tipo"] == ce.TIPO_MOVER]
    assert p["resultado"]["estado"] == "aplicado" and p["resultado"]["carpeta"] == f"0 Proyectos Entregados {ANIO}/289. Instalación de prueba"
    # Ya en los entregados y con el cambio en camino: no se pide otra vez «Cerrado»
    del_289 = [m for m in _buzon(e["raiz"], "editar-requerimiento") if m["requerimiento"]["numero"] == 289]
    assert len(del_289) == 1 and "289" not in estado["cerrados"]
    assert "pasó a" in detalle


def test_mueve_la_carpeta_cuando_la_planilla_ya_dice_cerrado(e):
    _planilla(e["raiz"], [_req(289, "Cerrado"), _req(296, "Cerrado")])
    _mover(e["raiz"], 289)
    ce.vuelta(e["raiz"], e["gestion"], {})
    assert (e["gestion"] / f"0 Proyectos Entregados {ANIO}" / "289. Instalación de prueba").is_dir()


def test_crea_la_carpeta_del_anio_si_no_existe(e, tmp_path):
    import shutil
    shutil.rmtree(e["gestion"] / f"0 Proyectos Entregados {ANIO}")
    _planilla(e["raiz"], [_req(289, "Cerrado")])
    _mover(e["raiz"], 289)
    ce.vuelta(e["raiz"], e["gestion"], {})
    assert (e["gestion"] / f"0 Proyectos Entregados {ANIO}" / "289. Instalación de prueba").is_dir()


def test_si_el_cambio_se_retiro_no_mueve_nada(e):
    m = _mover(e["raiz"], 289, minutos=-5)
    ce.vuelta(e["raiz"], e["gestion"], {})
    # Recién llegado: espera, por si OneDrive todavía no trae el cambio de estado
    assert [x["id"] for x in _buzon(e["raiz"], ce.TIPO_MOVER)] == [m["id"]]
    for x in _buzon(e["raiz"], ce.TIPO_MOVER):
        os.remove(x["_archivo"])
    _mover(e["raiz"], 289, minutos=-45)
    ce.vuelta(e["raiz"], e["gestion"], {})
    assert (e["gestion"] / "289. Instalación de prueba").is_dir() and _buzon(e["raiz"], ce.TIPO_MOVER) == []
    (p,) = [x for x in _procesados(e["raiz"]) if x["tipo"] == ce.TIPO_MOVER]
    assert p["resultado"]["estado"] == "descartado" and "Adjudicado" in p["resultado"]["detalle"][0]


def test_nunca_pisa_una_carpeta_que_ya_esta_en_el_destino(e):
    (e["gestion"] / f"0 Proyectos Entregados {ANIO}" / "289. Instalación de prueba").mkdir()
    (e["gestion"] / f"0 Proyectos Entregados {ANIO}" / "289. Instalación de prueba" / "de antes.txt").write_text("x", encoding="utf-8")
    _planilla(e["raiz"], [_req(289, "Cerrado")])
    _mover(e["raiz"], 289)
    ce.vuelta(e["raiz"], e["gestion"], {})
    assert (e["gestion"] / "289. Instalación de prueba" / "Compras").is_dir()
    assert (e["gestion"] / f"0 Proyectos Entregados {ANIO}" / "289. Instalación de prueba" / "de antes.txt").exists()
    (p,) = [x for x in _procesados(e["raiz"]) if x["tipo"] == ce.TIPO_MOVER]
    assert p["resultado"]["estado"] == "rechazado" and "no se pisa" in p["resultado"]["detalle"][0]


def test_dos_carpetas_con_el_mismo_n_no_se_mueven(e):
    (e["gestion"] / "289. Otra cosa").mkdir()
    _planilla(e["raiz"], [_req(289, "Cerrado")])
    _mover(e["raiz"], 289)
    ce.vuelta(e["raiz"], e["gestion"], {})
    assert (e["gestion"] / "289. Instalación de prueba").is_dir() and (e["gestion"] / "289. Otra cosa").is_dir()
    (p,) = [x for x in _procesados(e["raiz"]) if x["tipo"] == ce.TIPO_MOVER]
    assert p["resultado"]["estado"] == "rechazado" and "lo decide una persona" in p["resultado"]["detalle"][0]


def test_si_ya_estaba_en_los_entregados_no_hace_nada(e):
    _planilla(e["raiz"], [_req(296, "Cerrado")])
    _mover(e["raiz"], 296)
    ce.vuelta(e["raiz"], e["gestion"], {})
    (p,) = [x for x in _procesados(e["raiz"]) if x["tipo"] == ce.TIPO_MOVER]
    assert p["resultado"]["estado"] == "sin-cambios"


def test_con_algo_abierto_reintenta_y_a_los_7_dias_se_rinde(e, monkeypatch):
    def ocupado(a, b):
        raise PermissionError(32, "El proceso no tiene acceso al archivo porque está siendo utilizado por otro proceso")
    monkeypatch.setattr(ce.os, "rename", ocupado)
    _planilla(e["raiz"], [_req(289, "Cerrado")])
    _mover(e["raiz"], 289)
    detalle, _, avisos = ce.vuelta(e["raiz"], e["gestion"], {})
    assert len(_buzon(e["raiz"], ce.TIPO_MOVER)) == 1 and "se reintenta" in detalle and avisos
    for x in _buzon(e["raiz"], ce.TIPO_MOVER):
        os.remove(x["_archivo"])
    _mover(e["raiz"], 289, minutos=-8 * 24 * 60)
    ce.vuelta(e["raiz"], e["gestion"], {})
    assert _buzon(e["raiz"], ce.TIPO_MOVER) == []
    (p,) = [x for x in _procesados(e["raiz"]) if x["tipo"] == ce.TIPO_MOVER]
    assert p["resultado"]["estado"] == "rechazado" and "a mano" in p["resultado"]["detalle"][0]


def test_sin_la_biblioteca_de_gestion_no_hace_nada(e):
    detalle, estado, avisos = ce.vuelta(e["raiz"], None, {"cerrados": {"1": "x"}})
    assert "no está sincronizada" in detalle and estado == {"cerrados": {"1": "x"}} and avisos == []


# ── en el procesador ────────────────────────────────────────────────────────

def test_el_procesador_lo_corre_antes_de_las_carpetas_y_del_cruce(e, monkeypatch):
    nombres = [n for n, _ in procesar.PASOS]
    assert nombres.index("requerimientos") < nombres.index("entregados") < nombres.index("carpetas-proyecto") < nombres.index("proyectos")
    monkeypatch.setattr(procesar.ubicacion, "biblioteca", lambda nombre, desde=None: e["gestion"])
    detalle, firma = procesar.paso_entregados(e["raiz"], None, False)
    assert firma["cerrados"].keys() == {"296"} and "N° 296" in detalle
    # La firma es lo ya pedido: la vuelta siguiente no lo repite
    procesar.paso_entregados(e["raiz"], firma, False)
    assert len(_buzon(e["raiz"], "editar-requerimiento")) == 1


def test_la_planilla_escribe_el_cerrado_que_pide_el_procesador(e):
    """El mensaje del procesador pasa por las mismas reglas que uno del Portal (ganador_editar)."""
    import planilla_escritura as pe
    ce.vuelta(e["raiz"], e["gestion"], {})
    (m,) = _buzon(e["raiz"], "editar-requerimiento")
    cambios, detalle = pe.ganador_editar(m, {"estado": "Adjudicado", "titulo": "Sala de calderas de prueba"}, {}, datetime.now().astimezone())
    assert cambios == {"estado": "Cerrado"} and detalle == []
