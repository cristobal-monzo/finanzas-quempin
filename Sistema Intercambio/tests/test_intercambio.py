import json
import os

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


def _ejemplo_publicacion(nombre, archivo):
    ruta = ic._catalogo().CARPETA / "ejemplos" / "publicaciones" / nombre / archivo
    return json.loads(ruta.read_text(encoding="utf-8"))["datos"]


def test_publicar_valida_su_esquema_y_si_no_cumple_deja_la_anterior(tmp_path):
    """Desde el 2026-11-06 publicar valida contra el catálogo: lo que no cumple no se escribe (8 de 17
    publicaciones se validaban antes, cada una por su cuenta). Queda la anterior y quien publica falla a la vista."""
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    valido = _ejemplo_publicacion("contrapartes", "valido-1.json")
    ruta = ic.publicar(raiz, "contrapartes", "sistema-quempin", valido)
    antes = ruta.read_bytes()
    invalido = _ejemplo_publicacion("contrapartes", "invalido-sin-proveedores.json")
    with pytest.raises(ic.PublicacionInvalida, match="contrapartes no cumple su esquema"):
        ic.publicar(raiz, "contrapartes", "sistema-quempin", invalido)
    assert ruta.read_bytes() == antes
    assert not list((raiz / "publicado").glob(".*.tmp"))
    assert ic.errores_de_publicacion("contrapartes", "sistema-quempin", invalido)
    assert ic.errores_de_publicacion("contrapartes", "sistema-quempin", valido) == []


def test_publicar_sin_esquema_o_sin_validar_escribe_igual(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    ic.publicar(raiz, "demo", "prueba", {"cualquier": "cosa"})        # sin esquema en el catálogo
    assert ic.leer_publicacion(raiz, "demo")["datos"] == {"cualquier": "cosa"}
    # Solo para pruebas que simulan una publicación parcial de otra herramienta
    ic.publicar(raiz, "contrapartes", "sistema-quempin", {"clientes": []}, validar=False)
    assert ic.leer_publicacion(raiz, "contrapartes")["datos"] == {"clientes": []}


def test_publicar_valida_lo_que_queda_en_el_archivo_y_con_el_paquete_de_la_carpeta(tmp_path):
    """Valida la forma ya pasada por JSON (una tupla queda lista) y, con 'paquete' (el esquemas.json de la
    carpeta, que usa la copia de Sistema QUEMPIN), los esquemas de ese paquete y no los de esquemas/."""
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    valido = _ejemplo_publicacion("contrapartes", "valido-1.json")
    con_tuplas = {k: tuple(v) if isinstance(v, list) else v for k, v in valido.items()}
    assert ic.errores_de_publicacion("contrapartes", "sistema-quempin", con_tuplas) == []
    paquete = ic._catalogo().paquete()
    paquete = dict(paquete, publicaciones={"solo-esta": {"type": "object", "required": ["n"]}})
    assert ic.errores_de_publicacion("contrapartes", "x", {"nada": 1}, paquete) == []   # el paquete no la conoce
    with pytest.raises(ic.PublicacionInvalida):
        ic.publicar(raiz, "solo-esta", "x", {"otra": 1}, paquete=paquete)
    ic.publicar(raiz, "solo-esta", "x", {"n": 1}, paquete=paquete)
    assert ic.leer_publicacion(raiz, "solo-esta")["datos"] == {"n": 1}


def test_publicar_lo_mismo_no_reescribe_el_archivo(tmp_path):
    """Una publicación igual a la anterior no se reescribe: OneDrive no la vuelve a subir y
    «generado» queda en el último cambio real (2026-10-19)."""
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    ruta = ic.publicar(raiz, "demo", "prueba", {"a": [1, 2], "b": 1.5})
    antes = ruta.read_bytes()
    os.utime(ruta, (1_000_000, 1_000_000))
    ic.publicar(raiz, "demo", "prueba", {"b": 1.5, "a": (1, 2)})   # mismos datos, otro orden y tipo
    assert ruta.read_bytes() == antes and ruta.stat().st_mtime == 1_000_000
    ic.publicar(raiz, "demo", "prueba", {"a": [1, 2, 3], "b": 1.5})
    assert ic.leer_publicacion(raiz, "demo")["datos"]["a"] == [1, 2, 3]
    ic.publicar(raiz, "demo", "otra-herramienta", {"a": [1, 2, 3], "b": 1.5})
    assert ic.leer_publicacion(raiz, "demo")["herramienta"] == "otra-herramienta"
