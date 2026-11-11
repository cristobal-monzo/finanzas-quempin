# -*- coding: utf-8 -*-
"""El procesador del intercambio: hace solo lo que cambió, un paso que falla
no frena a los demás, y deja un estado.json válido. Los subprocesos (drivers
de Finanzas y Sistema QUEMPIN) se reemplazan: nada real se toca."""
import json
import os

import openpyxl
import pytest

import esquemas
import intercambio as ic
import procesar as pr
import requerimientos as rq

REVISAR_REAL = pr.mercado_publico.revisar   # antes de que el fixture lo reemplace


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
    monkeypatch.setattr(pr.mercado_publico, "revisar", lambda raiz: {
        "licitaciones": 0, "ordenes": 0, "llamadas": 0, "sugeridas": [], "revisar": [], "incompleta": False})
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


def test_estado_dice_que_codigo_corre_y_si_esta_la_tarea_de_pedidos(entorno, monkeypatch):
    """Auditoría del 2026-11-06: las tareas corren lo que esté abierto en la carpeta principal de Finanzas, que estuvo
    semanas en una rama de trabajo; y «Actualizar datos» se publicó sin la tarea que lo atiende."""
    r = _vuelta(entorno)
    datos = ic.leer_publicacion(entorno["raiz"], "estado")["datos"]
    assert datos["codigo"] == {"rama": "master", "commit": "abc1234", "sucio": False} and datos["pedidos"] == {"tarea": True}
    assert not any(a.startswith("código:") for a in r["avisos"])
    monkeypatch.setattr(pr, "codigo_en_uso", lambda repo=None: {"rama": "otra-rama", "commit": "def5678", "sucio": False})
    monkeypatch.setattr(pr, "tarea_de_pedidos_instalada", lambda: False)
    r = _vuelta(entorno)
    datos = ic.leer_publicacion(entorno["raiz"], "estado")["datos"]
    assert datos["pedidos"] == {"tarea": False}
    assert [a for a in datos["avisos"] if a.startswith("código:")] == [
        "código: el procesador corre la rama «otra-rama» (def5678), no master. "
        "Las tareas programadas corren lo que esté abierto en la carpeta principal de Finanzas."]
    assert r["avisos"] == datos["avisos"]
    # Sin git ni schtasks (otro equipo): no van los campos, y el estado sigue cumpliendo su esquema
    monkeypatch.setattr(pr, "codigo_en_uso", lambda repo=None: None)
    monkeypatch.setattr(pr, "tarea_de_pedidos_instalada", lambda: None)
    _vuelta(entorno)
    datos = ic.leer_publicacion(entorno["raiz"], "estado")["datos"]
    assert "codigo" not in datos and "pedidos" not in datos


def test_avisos_de_codigo():
    assert pr.avisos_de_codigo(None) == []
    assert pr.avisos_de_codigo({"rama": "master", "commit": "a1", "sucio": False}) == []
    assert pr.avisos_de_codigo({"rama": "master", "commit": "a1", "sucio": True}) == [
        "código: la carpeta principal de Finanzas tiene código modificado sin commit (a1)."]
    assert pr.avisos_de_codigo({"rama": "x", "commit": "a1", "sucio": True})[0].startswith("código: el procesador corre la rama «x»")


@pytest.mark.con_git_real
def test_codigo_en_uso_lee_rama_commit_y_solo_el_codigo_sucio(tmp_path):
    import shutil
    import subprocess

    codigo = pr.codigo_en_uso
    if shutil.which("git") is None:
        pytest.skip("git no está instalado en esta máquina")
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    git("init", "-b", "master")
    git("config", "user.email", "prueba@example.com")
    git("config", "user.name", "Prueba")
    (repo / "paso.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "LEEME.md").write_text("hola\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "uno")
    c = codigo(repo)
    assert c["rama"] == "master" and len(c["commit"]) >= 7 and c["sucio"] is False
    (repo / "LEEME.md").write_text("cambio\n", encoding="utf-8")
    assert codigo(repo)["sucio"] is False             # un .md editado no cambia lo que corre
    (repo / "paso.py").write_text("x = 2\n", encoding="utf-8")
    assert codigo(repo)["sucio"] is True
    git("switch", "-c", "otra")
    assert codigo(repo)["rama"] == "otra"
    assert codigo(tmp_path / "no-es-repo") is None


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


def _pedir_vuelta(raiz, id_="pedido0001"):
    ic.enviar(raiz, {"esquema": ic.ESQUEMA, "id": id_, "tipo": pr.TIPO_PEDIDO, "destino": pr.DESTINO_PEDIDOS,
                     "origen": {"herramienta": "portal", "usuario": "LC", "enviado": ic.ahora_iso()}})


def _estado_con_vuelta_de_hace(raiz, minutos):
    from datetime import datetime, timedelta
    corrida = (datetime.now().astimezone() - timedelta(minutes=minutos)).isoformat(timespec="seconds")
    ic.publicar(raiz, "estado", "procesador", {"procesador": {"ultimaCorrida": corrida}}, validar=False)  # parcial


def test_la_vuelta_atiende_los_pedidos_del_portal(entorno):
    raiz = entorno["raiz"]
    _pedir_vuelta(raiz)
    r = _vuelta(entorno)
    assert r["pedidos"] == 1 and pr._pedidos(raiz) == []
    assert ic.resultados_recientes(raiz, destino=pr.DESTINO_PEDIDOS)["pedido0001"]["estado"] == "aplicado"
    # El pulso que publica ya no lo cuenta como pendiente
    assert "procesador" not in ic.leer_publicacion(raiz, "estado")["datos"]["buzon"]


def test_el_pedido_que_llega_durante_la_vuelta_pide_otra(entorno):
    raiz = entorno["raiz"]

    def _llega_uno(raiz_, previo, forzar):
        _pedir_vuelta(raiz_, "pedido0002")
        return "ok", None

    _pedir_vuelta(raiz)
    r = _vuelta(entorno, pasos=pr.PASOS + (("llega", _llega_uno),))
    assert r["pedidos"] == 1
    assert [m["id"] for m in pr._pedidos(raiz)] == ["pedido0002"]
    assert ic.leer_publicacion(raiz, "estado")["datos"]["buzon"]["procesador"]["pendientes"] == 1


def test_hay_pedido_respeta_la_separacion_entre_vueltas(entorno):
    raiz = entorno["raiz"]
    assert pr.hay_pedido(raiz) is False
    _pedir_vuelta(raiz)
    assert pr.hay_pedido(raiz) is True      # sin pulso todavía
    _estado_con_vuelta_de_hace(raiz, 0.5)
    assert pr.hay_pedido(raiz) is False     # queda esperando en el buzón
    assert len(pr._pedidos(raiz)) == 1
    # Un minuto basta (2026-11-11): la vuelta a pedido ya no consulta Mercado Público, que tiene su turno
    _estado_con_vuelta_de_hace(raiz, 2)
    assert pr.hay_pedido(raiz) is True


def test_si_hay_pedido_sin_pedido_no_corre_ni_anota_nada(entorno, monkeypatch):
    monkeypatch.setattr(pr, "CARPETA_LOGS", entorno["tmp"] / "logs")
    monkeypatch.setattr(pr.ubicacion, "ubicar_intercambio", lambda _: entorno["raiz"])
    monkeypatch.setattr(pr, "procesar", lambda **kw: pytest.fail("corrió sin que nadie lo pidiera"))
    assert pr.main(["--si-hay-pedido"]) == 0
    assert not (entorno["tmp"] / "logs").exists()


def test_si_hay_pedido_con_pedido_da_la_vuelta_y_lo_anota(entorno, monkeypatch):
    raiz = entorno["raiz"]
    monkeypatch.setattr(pr, "CARPETA_LOGS", entorno["tmp"] / "logs")
    monkeypatch.setattr(pr, "RUTA_ESTADO_LOCAL", entorno["estado"])
    monkeypatch.setattr(pr.ubicacion, "ubicar_intercambio", lambda _: raiz)
    _pedir_vuelta(raiz)
    assert pr.main(["--si-hay-pedido"]) == 0
    assert pr._pedidos(raiz) == []
    assert " pedidos=1 " in next((entorno["tmp"] / "logs").glob("procesador_*.log")).read_text(encoding="utf-8")


def test_avisos_de_sistema_quempin_quedan_en_el_detalle(tmp_path, monkeypatch):
    (tmp_path / "app" / "integraciones").mkdir(parents=True)
    (tmp_path / "app" / "integraciones" / "ecosistema.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(pr, "RAIZ_SISTEMA_QUEMPIN", tmp_path)
    salida = json.dumps({"activo": True, "borradores": 0, "avisos": ["folios: no se pudo publicar (sin Control)."]})
    monkeypatch.setattr(pr, "correr", lambda comando, cwd=None, limite=600: (True, salida))
    detalle, firma = pr.paso_sistema_quempin(tmp_path, None, False)
    assert firma == "ok" and detalle.endswith("avisos: folios: no se pudo publicar (sin Control).")


def test_mercado_publico_sin_ticket_falla_con_instrucciones(entorno, monkeypatch):
    monkeypatch.setattr(pr.mercado_publico, "revisar", REVISAR_REAL)   # el real, con la red cortada (conftest)
    r = _vuelta(entorno)
    paso = r["pasos"]["mercado-publico"]
    assert paso["ok"] is False and "configurar" in paso["detalle"]
    assert r["pasos"]["proyectos"]["ok"] is True                     # no frena a los demás


def test_uf_del_dia_se_pide_una_sola_vez_al_dia(entorno, tmp_path, monkeypatch):
    uf = tmp_path / "uf_ultima.json"
    monkeypatch.setenv("QUEMPIN_UF_ULTIMA", str(uf))
    _vuelta(entorno)
    pedidas = [c for c in entorno["llamadas"] if c[-1] == "uf"]
    assert len(pedidas) == 1
    entorno["llamadas"].clear()
    _vuelta(entorno)
    assert not [c for c in entorno["llamadas"] if c[-1] == "uf"]


def test_el_leeme_versionado_queda_en_la_carpeta_y_no_se_reescribe(entorno):
    _vuelta(entorno)
    leeme = entorno["raiz"] / "LEEME.md"
    assert leeme.read_bytes() == pr.LEEME_VERSIONADO.read_bytes()
    os.utime(leeme, (1_000_000, 1_000_000))
    _vuelta(entorno)
    assert leeme.stat().st_mtime == 1_000_000


def test_el_estado_dice_su_propia_vuelta(entorno):
    _vuelta(entorno)
    _vuelta(entorno)
    estado = ic.leer_publicacion(entorno["raiz"], "estado")["datos"]
    assert estado["publicaciones"]["estado"]["generado"] >= estado["procesador"]["ultimaCorrida"][:16]


def test_el_log_dice_cuanto_tardo_cada_paso_lento(tmp_path, monkeypatch):
    """2026-10-25: el log solo decía «ok» o «FALLA», y una vuelta de 300 s no se veía hasta que fallaba."""
    monkeypatch.setattr(pr, "CARPETA_LOGS", tmp_path)
    pr._registrar({"activo": True, "avisos": [], "pasos": {
        "esquemas": {"ok": True, "detalle": "", "seg": 1.5},
        "sistema-quempin": {"ok": True, "detalle": "", "seg": 89.6},
        "uf": {"ok": False, "detalle": "", "seg": 12.0}}})
    linea = next(tmp_path.glob("procesador_*.log")).read_text(encoding="utf-8").strip()
    assert linea.endswith(" activo 103s esquemas=ok sistema-quempin=ok(90s) uf=FALLA(12s)")
    pr._registrar({"activo": False, "avisos": ["sin carpeta"], "pasos": {}})
    assert next(tmp_path.glob("procesador_*.log")).read_text(encoding="utf-8").splitlines()[-2].endswith(" inactivo ")


def test_mindicador_caido_no_es_una_falla_del_procesador(entorno, tmp_path, monkeypatch):
    monkeypatch.setenv("QUEMPIN_UF_ULTIMA", str(tmp_path / "uf_ultima.json"))
    monkeypatch.setattr(pr, "correr", lambda comando, cwd=None, limite=600: (comando[-1] != "uf", "[ERROR] HTTP 500"))
    r = _vuelta(entorno)
    assert r["pasos"]["uf"]["ok"] and "se reintenta" in r["pasos"]["uf"]["detalle"]
    assert not r["avisos"]


# ── Cada 5 minutos (2026-11-11): turnos, OneDrive y vueltas que no se pisan ──

def _contar_mercado_publico(monkeypatch, incompleta=False, falla=False):
    llamadas = []

    def _revisar(raiz):
        llamadas.append(1)
        if falla:
            raise pr.mercado_publico.ErrorMercadoPublico("la API no respondió")
        return {"licitaciones": 3, "ordenes": 1, "llamadas": 4, "sugeridas": [], "revisar": [], "incompleta": incompleta}
    monkeypatch.setattr(pr.mercado_publico, "revisar", _revisar)
    return llamadas


def _turno_de_hace(e, paso, minutos):
    from datetime import datetime, timedelta
    firmas = json.loads(e["estado"].read_text(encoding="utf-8"))
    cuando = datetime.now().astimezone() - timedelta(minutes=minutos)
    firmas[pr.CLAVE_TURNOS][paso]["cuando"] = cuando.isoformat(timespec="seconds")
    e["estado"].write_text(json.dumps(firmas), encoding="utf-8")


def _estado_hace(raiz, minutos):
    """Corre hacia atrás la hora del estado publicado, sin tocar nada más."""
    from datetime import datetime, timedelta
    sobre = ic.leer_publicacion(raiz, "estado")
    corrida = datetime.now().astimezone() - timedelta(minutes=minutos)
    sobre["datos"]["procesador"]["ultimaCorrida"] = corrida.isoformat(timespec="seconds")
    ic._escribir_json_atomico(raiz / "publicado" / "estado.json", sobre)


def test_mercado_publico_corre_cada_3_horas_y_entre_medio_queda_su_ultimo_resultado(entorno, monkeypatch):
    llamadas = _contar_mercado_publico(monkeypatch)
    r = _vuelta(entorno)
    assert len(llamadas) == 1 and r["conTurno"] == ["mercado-publico", "oportunidades"]
    r = _vuelta(entorno)
    assert len(llamadas) == 1 and r["conTurno"] == []
    paso = r["pasos"]["mercado-publico"]
    assert paso["ok"] and paso["detalle"].startswith("3 licitación(es)") and paso["seg"] == 0 and paso["ultimaVez"]
    _turno_de_hace(entorno, "mercado-publico", 2 * 60 + 50)
    _vuelta(entorno)
    assert len(llamadas) == 1
    _turno_de_hace(entorno, "mercado-publico", 3 * 60 + 1)
    _vuelta(entorno)
    assert len(llamadas) == 2


def test_mercado_publico_que_fallo_se_reintenta_en_media_hora_y_la_falla_se_sigue_viendo(entorno, monkeypatch):
    llamadas = _contar_mercado_publico(monkeypatch, falla=True)
    _vuelta(entorno)
    _vuelta(entorno)                                         # los demás pasos pasan a «sin cambios»
    r = _vuelta(entorno)
    assert len(llamadas) == 1
    assert r["pasos"]["mercado-publico"]["ok"] is False      # la bandeja y el pulso la siguen mostrando
    assert r["avisos"] == ["mercado-publico: la API no respondió"]
    assert r["estado"] == ""                                 # y el estado no cambia por eso
    _turno_de_hace(entorno, "mercado-publico", 31)
    _vuelta(entorno)
    assert len(llamadas) == 2


def test_mercado_publico_a_medias_sigue_en_la_vuelta_siguiente(entorno, monkeypatch):
    llamadas = _contar_mercado_publico(monkeypatch, incompleta=True)
    _vuelta(entorno)
    _vuelta(entorno)
    assert len(llamadas) == 2


def test_forzar_no_adelanta_el_turno_de_mercado_publico(entorno, monkeypatch):
    """--forzar lo usan el run de Actualizar_Finanzas y cada registro del Centro de Costos: la API sigue cada 3 h."""
    llamadas = _contar_mercado_publico(monkeypatch)
    _vuelta(entorno)
    r = _vuelta(entorno, forzar=True)
    assert len(llamadas) == 1
    assert r["pasos"]["requerimientos"]["detalle"] != "sin cambios"   # lo local sí se rehace


def test_con_el_tablero_de_oportunidades_consultando_la_api_espera_a_la_vuelta_siguiente(entorno, monkeypatch):
    llamadas = _contar_mercado_publico(monkeypatch)
    with pr.mercado_publico.usando_api():
        r = _vuelta(entorno, forzar=True)
    assert llamadas == [] and r["conTurno"] == []
    assert r["pasos"]["proyectos"]["ok"]                           # lo demás corre igual
    _vuelta(entorno)
    assert len(llamadas) == 1                                      # sin anotar el intento: le toca en la siguiente


def test_la_marca_de_la_api_en_uso_se_quita_y_vence():
    import time
    ruta = pr.mercado_publico.ruta_api_en_uso()
    with pr.mercado_publico.usando_api():
        assert pr.mercado_publico.api_en_uso()
    assert not ruta.exists() and not pr.mercado_publico.api_en_uso()
    ruta.write_text("123", encoding="utf-8")
    viejo = time.time() - pr.mercado_publico.API_EN_USO_VENCE_SEG - 60
    os.utime(ruta, (viejo, viejo))
    assert not pr.mercado_publico.api_en_uso()                     # un proceso que murió no la bloquea para siempre


def test_una_vuelta_sin_novedad_no_escribe_nada_en_onedrive(entorno):
    _vuelta(entorno)
    _vuelta(entorno)                                               # los detalles pasan a «sin cambios»
    estado = entorno["raiz"] / "publicado" / "estado.json"
    for ruta in (estado, entorno["estado"]):
        os.utime(ruta, (1_000_000, 1_000_000))
    r = _vuelta(entorno)
    assert r["estado"] == "" and pr.sin_novedad(r)
    assert estado.stat().st_mtime == 1_000_000 and entorno["estado"].stat().st_mtime == 1_000_000


def test_sin_novedad_el_pulso_se_reescribe_cada_15_minutos(entorno):
    _vuelta(entorno)
    _vuelta(entorno)
    _estado_hace(entorno["raiz"], minutos=16)
    r = _vuelta(entorno)
    assert r["estado"] == "latido" and pr.sin_novedad(r)           # el pulso sigue vivo, pero no va al log
    assert ic.leer_publicacion(entorno["raiz"], "estado")["datos"]["procesador"]["ultimaCorrida"] >= ic.ahora_iso()[:16]


def test_la_vuelta_que_atiende_un_pedido_siempre_reescribe_el_pulso(entorno):
    """El Portal da el pedido por hecho cuando cambia ultimaCorrida: aunque nada más cambie, tiene que escribirse."""
    _vuelta(entorno)
    _vuelta(entorno)
    _estado_hace(entorno["raiz"], minutos=2)
    antes = ic.leer_publicacion(entorno["raiz"], "estado")["datos"]["procesador"]["ultimaCorrida"]
    _pedir_vuelta(entorno["raiz"])
    r = _vuelta(entorno)
    assert r["estado"] in ("cambios", "latido") and not pr.sin_novedad(r)
    assert ic.leer_publicacion(entorno["raiz"], "estado")["datos"]["procesador"]["ultimaCorrida"] != antes


def test_un_paso_que_cambia_vuelve_a_escribir_el_estado(entorno):
    _vuelta(entorno)
    _vuelta(entorno)
    libro = openpyxl.load_workbook(entorno["planilla"])
    libro[rq.HOJA].append([281, "Ofertado", "H2 Green", 1000])
    libro.save(entorno["planilla"])
    r = _vuelta(entorno)
    assert r["estado"] == "cambios" and not pr.sin_novedad(r)


def test_el_log_no_anota_las_vueltas_sin_novedad(tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "CARPETA_LOGS", tmp_path)
    tranquila = {"activo": True, "avisos": [], "pedidos": 0, "estado": "latido", "conTurno": [], "forzada": False,
                 "pasos": {"esquemas": {"ok": True, "detalle": "", "seg": 0.4}}}
    pr._registrar(tranquila)
    assert not list(tmp_path.glob("procesador_*.log"))
    for cambio in ({"estado": "cambios"}, {"pedidos": 1}, {"conTurno": ["mercado-publico"]}, {"forzada": True},
                   {"pasos": {"sistema-quempin": {"ok": True, "detalle": "", "seg": 24.0}}}):
        assert not pr.sin_novedad({**tranquila, **cambio}), cambio


def test_forzar_espera_a_que_termine_la_vuelta_en_curso():
    pr.RUTA_CANDADO.write_text("123")
    esperas = []

    def _dormir(seg):
        esperas.append(seg)
        pr.RUTA_CANDADO.unlink()          # la vuelta en curso termina
    pr._tomar_candado(esperar_seg=60, dormir=_dormir)
    assert esperas == [5] and pr.RUTA_CANDADO.exists()


def test_el_candado_vencido_se_reemplaza():
    pr.RUTA_CANDADO.write_text("123")
    viejo = os.path.getmtime(pr.RUTA_CANDADO) - pr.CANDADO_VENCE_SEG - 60
    os.utime(pr.RUTA_CANDADO, (viejo, viejo))
    pr._tomar_candado()
    assert pr.RUTA_CANDADO.read_text() == str(os.getpid())


def test_el_driver_espera_el_mismo_candado():
    """Oportunidades (Actualizar_Finanzas/driver.py) espera a que el procesador suelte su candado: si cada uno lo
    buscara en otra ruta, consultarían la API a la vez."""
    import importlib.util
    from pathlib import Path
    ruta = Path(pr.__file__).resolve().parents[1] / ".claude" / "skills" / "Actualizar_Finanzas" / "driver.py"
    spec = importlib.util.spec_from_file_location("driver_actualizar_finanzas_candado", ruta)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    assert driver.CANDADO_PROCESADOR == pr.carpeta_local() / "procesador.lock"
    assert "OneDrive" not in str(driver.CANDADO_PROCESADOR)


def test_mindicador_caido_se_reintenta_en_media_hora(entorno, monkeypatch):
    from datetime import datetime, timedelta
    pedidas = []

    def _correr(comando, cwd=None, limite=600):
        if comando[-1] == "uf":
            pedidas.append(1)
            return False, "[ERROR] HTTP 500"
        return True, "listo"
    monkeypatch.setattr(pr, "correr", _correr)
    r = _vuelta(entorno)
    assert len(pedidas) == 1 and "se reintenta a las" in r["pasos"]["uf"]["detalle"]
    r = _vuelta(entorno)
    assert len(pedidas) == 1 and "se reintenta a las" in r["pasos"]["uf"]["detalle"]
    firmas = json.loads(entorno["estado"].read_text(encoding="utf-8"))
    hace = datetime.now().astimezone() - timedelta(minutes=31)
    firmas["uf"] = pr.INTENTO + hace.isoformat(timespec="seconds")
    entorno["estado"].write_text(json.dumps(firmas), encoding="utf-8")
    _vuelta(entorno)
    assert len(pedidas) == 2
