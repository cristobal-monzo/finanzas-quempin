# -*- coding: utf-8 -*-
"""El procesador del intercambio: hace solo lo que cambió, un paso que falla
no frena a los demás, y deja un estado.json válido. Los subprocesos (drivers
de Finanzas y Sistema QUEMPIN) se reemplazan: nada real se toca."""
import json

import openpyxl
import pytest

import esquemas
import intercambio as ic
import procesar as pr
import requerimientos as rq


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    planilla = tmp_path / "Planilla.xlsx"
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = rq.HOJA
    hoja.append(["N°", "Estado", "Título", "Valor ofertado (IVA inc)"])
    hoja.append([280, "Ofertado", "UMAG", 3510500])
    libro.save(planilla)
    monkeypatch.setenv("QUEMPIN_PLANILLA_REQUERIMIENTOS", str(planilla))
    monkeypatch.setattr(pr, "RUTA_CANDADO", tmp_path / ".lock")
    monkeypatch.setattr(pr, "EXCEL_AF", tmp_path / "af.xlsx")
    monkeypatch.setattr(pr, "EXCEL_CC", tmp_path / "cc.xlsx")
    monkeypatch.setattr(pr, "FOTO_COTIZADOR", tmp_path / "foto.json")
    monkeypatch.setattr(pr, "RAIZ_SISTEMA_QUEMPIN", tmp_path / "sin-sistema")
    monkeypatch.setattr(pr, "RAIZ_FACTURAS_CL", tmp_path / "sin-facturas")
    llamadas = []

    def _correr(comando, cwd=None, limite=600):
        llamadas.append([str(c) for c in comando])
        return True, "listo"

    monkeypatch.setattr(pr, "correr", _correr)
    return {"raiz": raiz, "planilla": planilla, "estado": tmp_path / "estado_local.json", "llamadas": llamadas,
            "tmp": tmp_path}


def _vuelta(e, **kw):
    return pr.procesar(e["raiz"], ruta_estado=e["estado"], **kw)


def test_primera_vuelta_publica_todo_y_un_estado_valido(entorno):
    r = _vuelta(entorno)
    assert r["activo"] and all(p["ok"] for p in r["pasos"].values()), r
    raiz = entorno["raiz"]
    assert (raiz / "esquemas.json").exists()
    assert ic.leer_publicacion(raiz, "requerimientos")["datos"]["requerimientos"][0]["numero"] == 280
    assert ic.leer_publicacion(raiz, "proyectos") is not None
    estado = ic.leer_publicacion(raiz, "estado")
    assert esquemas.validar_publicacion("estado", estado) == []
    assert set(estado["datos"]["procesador"]["pasos"]) == {n for n, _ in pr.PASOS}
    assert "requerimientos" in estado["datos"]["publicaciones"]


def test_segunda_vuelta_sin_cambios_no_hace_nada_caro(entorno):
    _vuelta(entorno)
    entorno["llamadas"].clear()
    r = _vuelta(entorno)
    assert r["pasos"]["requerimientos"]["detalle"] == "sin cambios"
    assert r["pasos"]["esquemas"]["detalle"] == "sin cambios"
    assert r["pasos"]["analisis-financiero"]["detalle"] == "sin cambios"
    assert entorno["llamadas"] == []


def test_envio_nuevo_para_af_dispara_un_run_una_sola_vez(entorno):
    _vuelta(entorno)
    entorno["llamadas"].clear()
    ic.enviar(entorno["raiz"], {"esquema": ic.ESQUEMA, "id": "venta0001", "tipo": "venta-proyecto",
                                "destino": "analisis-financiero",
                                "origen": {"herramienta": "formulador", "enviado": "2026-10-01T10:00:00-03:00"}})
    _vuelta(entorno)
    assert [c[-1] for c in entorno["llamadas"]] == ["run"]
    entorno["llamadas"].clear()
    _vuelta(entorno)          # el envío sigue (el falso run no lo atendió): no se reintenta en cada vuelta
    assert entorno["llamadas"] == []


def test_cambio_en_centro_de_costos_solo_republica(entorno):
    _vuelta(entorno)
    entorno["llamadas"].clear()
    (entorno["tmp"] / "cc.xlsx").write_bytes(b"cambio")
    _vuelta(entorno)
    assert [c[-2:] for c in entorno["llamadas"]] == [["intercambio", "publicar"]]


def test_planilla_cambiada_se_republica_y_cierra_sugerencias(entorno):
    _vuelta(entorno)
    ic.enviar(entorno["raiz"], {"esquema": ic.ESQUEMA, "id": "sugiere01", "tipo": rq.TIPO_SUGERENCIA,
                                "destino": rq.DESTINO,
                                "origen": {"herramienta": "formulador", "enviado": "2026-10-01T10:00:00-03:00"},
                                "requerimiento": {"numero": 280}, "cambios": {"estado": "Adjudicado"},
                                "fuente": {"herramienta": "formulador"}})
    r = _vuelta(entorno)
    assert "1 esperan" in r["pasos"]["requerimientos"]["detalle"]
    libro = openpyxl.load_workbook(entorno["planilla"])
    libro.active["B2"] = "Adjudicado"
    libro.save(entorno["planilla"])
    r = _vuelta(entorno)
    assert "1 cerradas" in r["pasos"]["requerimientos"]["detalle"]
    assert ic.resultados_recientes(entorno["raiz"])["sugiere01"]["estado"] == "aplicado"


def test_un_paso_que_falla_no_frena_a_los_demas(entorno, monkeypatch):
    def _revienta(raiz, previo, forzar):
        raise RuntimeError("se cayó")
    pasos = (("roto", _revienta),) + pr.PASOS
    r = pr.procesar(entorno["raiz"], ruta_estado=entorno["estado"], pasos=pasos)
    assert r["pasos"]["roto"]["ok"] is False and r["pasos"]["proyectos"]["ok"] is True
    assert r["avisos"] == ["roto: se cayó"]
    assert ic.leer_publicacion(entorno["raiz"], "estado")["datos"]["avisos"] == ["roto: se cayó"]


def test_sin_carpeta_queda_inactivo(tmp_path):
    assert pr.procesar(tmp_path / "no-existe")["activo"] is False


def test_dos_corridas_a_la_vez_no(entorno):
    pr.RUTA_CANDADO.write_text("123")
    with pytest.raises(pr.Ocupado):
        _vuelta(entorno)


def test_buzon_resumido_por_destino(entorno):
    for i, destino in enumerate(("sistema-quempin", "sistema-quempin", "analisis-financiero")):
        ic.enviar(entorno["raiz"], {"esquema": ic.ESQUEMA, "id": f"msg0000{i}", "tipo": "x", "destino": destino,
                                    "origen": {"herramienta": "y", "enviado": f"2026-10-0{i + 1}T10:00:00-03:00"}})
    b = pr.resumen_buzon(entorno["raiz"])
    assert b["sistema-quempin"]["pendientes"] == 2 and b["sistema-quempin"]["masAntiguo"].startswith("2026-10-01")
    assert b["analisis-financiero"]["pendientes"] == 1


def test_avisos_de_sistema_quempin_quedan_en_el_detalle(tmp_path, monkeypatch):
    (tmp_path / "app" / "integraciones").mkdir(parents=True)
    (tmp_path / "app" / "integraciones" / "ecosistema.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(pr, "RAIZ_SISTEMA_QUEMPIN", tmp_path)
    salida = json.dumps({"activo": True, "borradores": 0, "avisos": ["folios: no se pudo publicar (sin Control)."]})
    monkeypatch.setattr(pr, "correr", lambda comando, cwd=None, limite=600: (True, salida))
    detalle, firma = pr.paso_sistema_quempin(tmp_path, None, False)
    assert firma == "ok" and detalle.endswith("avisos: folios: no se pudo publicar (sin Control).")
