import json

import pytest

import intercambio as ic


def _mensaje(id_="abc12345", enviado="2026-09-30T10:00:00-03:00", destino="analisis-financiero",
             tipo="presupuesto-proyecto", **extra):
    m = {
        "esquema": ic.ESQUEMA, "id": id_, "tipo": tipo, "destino": destino,
        "origen": {"herramienta": "formulador", "enviado": enviado},
    }
    m.update(extra)
    return m


def _dejar(raiz, nombre, contenido):
    ruta = raiz / ic.CARPETA_BUZON / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido if isinstance(contenido, str) else json.dumps(contenido), encoding="utf-8")
    return ruta


def test_asegurar_carpeta_crea_estructura_y_manifiesto_sin_pisarlo(tmp_path):
    raiz = tmp_path / "Intercambio"
    ic.asegurar_carpeta(raiz)
    for sub in ("buzon", "procesado", "publicado"):
        assert (raiz / sub).is_dir()
    assert ic.es_carpeta_de_intercambio(raiz)
    manifiesto = raiz / ic.MANIFIESTO
    manifiesto.write_text(json.dumps({"esquema": ic.ESQUEMA, "marca": 1}), encoding="utf-8")
    ic.asegurar_carpeta(raiz)
    assert json.loads(manifiesto.read_text(encoding="utf-8"))["marca"] == 1


def test_una_carpeta_cualquiera_no_es_de_intercambio(tmp_path):
    assert not ic.es_carpeta_de_intercambio(tmp_path)
    (tmp_path / ic.MANIFIESTO).write_text("{no es json", encoding="utf-8")
    assert not ic.es_carpeta_de_intercambio(tmp_path)


@pytest.mark.parametrize("cambio, error", [
    ({"esquema": "otra-cosa"}, "esquema"),
    ({"esquema": "quempin.intercambio/9"}, "versión"),
    ({"id": "x"}, "id"),
    ({"id": "con espacio 123"}, "id"),
    ({"tipo": ""}, "tipo"),
    ({"destino": None}, "destino"),
    ({"origen": "formulador"}, "origen.herramienta"),
    ({"origen": {"herramienta": "formulador"}}, "origen.enviado"),
])
def test_validar_mensaje_detecta_cada_falla_del_sobre(cambio, error):
    m = _mensaje()
    m.update(cambio)
    errores = ic.validar_mensaje(m)
    assert errores and any(error in e for e in errores)


def test_validar_mensaje_acepta_un_sobre_completo():
    assert ic.validar_mensaje(_mensaje()) == []
    assert ic.validar_mensaje(["no", "dict"]) == ["no es un objeto JSON"]


def test_leer_buzon_ordena_filtra_y_separa_invalidos(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    _dejar(raiz, "b.json", _mensaje("mensaje-b", enviado="2026-09-30T12:00:00-03:00"))
    _dejar(raiz, "a.json", _mensaje("mensaje-a", enviado="2026-09-30T09:00:00-03:00"))
    _dejar(raiz, "otro.json", _mensaje("mensaje-c", destino="centro-de-costos"))
    _dejar(raiz, "roto.json", "{esto no es json")
    _dejar(raiz, "sin-id.json", {"esquema": ic.ESQUEMA})
    _dejar(raiz, ".temporal.json", _mensaje("mensaje-d"))
    _dejar(raiz, "a.json.crswap", "{}")
    _dejar(raiz, "nota.txt", "hola")

    validos, invalidos = ic.leer_buzon(raiz, destino="analisis-financiero")

    assert [m["id"] for m in validos] == ["mensaje-a", "mensaje-b"]
    assert validos[0]["_archivo"].name == "a.json"
    assert sorted(i["_archivo"].name for i in invalidos) == ["roto.json", "sin-id.json"]


def test_leer_buzon_sin_carpeta_devuelve_vacio(tmp_path):
    assert ic.leer_buzon(tmp_path / "no-existe") == ([], [])


def test_archivar_mueve_con_resultado_y_no_pisa_homonimos(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    _dejar(raiz, "m.json", _mensaje("mensaje-1"))
    (m,), _ = ic.leer_buzon(raiz)
    destino = ic.archivar(raiz, m, "aplicado", ["Materiales: $0 → $10"], extra={"tag": "DEMO"})

    assert not (raiz / "buzon" / "m.json").exists()
    registro = json.loads(destino.read_text(encoding="utf-8"))
    assert "_archivo" not in registro
    assert registro["resultado"]["estado"] == "aplicado"
    assert registro["resultado"]["tag"] == "DEMO"
    assert registro["resultado"]["detalle"] == ["Materiales: $0 → $10"]

    _dejar(raiz, "m.json", _mensaje("mensaje-2"))
    (m2,), _ = ic.leer_buzon(raiz)
    destino2 = ic.archivar(raiz, m2, "descartado")
    assert destino2 != destino and destino.exists() and destino2.exists()


def test_archivar_rechaza_estados_que_no_son_finales(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    _dejar(raiz, "m.json", _mensaje())
    (m,), _ = ic.leer_buzon(raiz)
    with pytest.raises(ValueError):
        ic.archivar(raiz, m, "pendiente")
    assert (raiz / "buzon" / "m.json").exists()


def test_resultados_recientes_por_id(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    _dejar(raiz, "m.json", _mensaje("mensaje-1"))
    (m,), _ = ic.leer_buzon(raiz)
    ic.archivar(raiz, m, "aplicado", ["ok"], extra={"tag": "DEMO"})
    resultados = ic.resultados_recientes(raiz)
    assert resultados["mensaje-1"]["estado"] == "aplicado"
    assert resultados["mensaje-1"]["tag"] == "DEMO"


def test_publicar_y_leer_publicacion(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    ruta = ic.publicar(raiz, "demo", "prueba", {"proyectos": [1, 2]})
    assert ruta.name == "demo.json"
    assert not list((raiz / "publicado").glob(".*.tmp"))
    sobre = ic.leer_publicacion(raiz, "demo")
    assert sobre["herramienta"] == "prueba" and sobre["datos"] == {"proyectos": [1, 2]}
    assert ic.leer_publicacion(raiz, "no-existe") is None


def test_resultados_recientes_filtra_por_destino(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    for id_, destino in (("paraaf01", "analisis-financiero"), ("parasq01", "sistema-quempin")):
        ic.enviar(raiz, _mensaje(id_=id_, destino=destino))
    for m in ic.leer_buzon(raiz)[0]:
        ic.archivar(raiz, m, "aplicado")
    assert set(ic.resultados_recientes(raiz)) == {"paraaf01", "parasq01"}
    assert set(ic.resultados_recientes(raiz, destino="sistema-quempin")) == {"parasq01"}
