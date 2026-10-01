"""Repositorio de presupuestos del Formulador visto desde Python: lectura,
entregas por archivo (mensaje «formulacion») y revisión con Claude. Todo en
carpetas temporales: nunca la carpeta real."""

import json

import pytest

import formulaciones as fz
import intercambio as ic

ESQ = ic.ESQUEMA


def _datos(uid="a1b2c3d4e5f6", mod="2026-09-30T15:00:00.000Z", **extra):
    d = {"schema": "quempin-formulacion/v1", "uid": uid, "codigo": "QPN-2026-001", "version": 1,
         "titulo": "Oferta de prueba", "cliente": "Cliente de prueba", "estado": "Borrador",
         "responsable": "Persona", "modificado": mod, "partidas": [], "materiales": []}
    d.update(extra)
    return d


def _resumen(**extra):
    r = {"moneda": "CLP", "costoDirecto": 1113820, "costoTotal": 1113820, "utilidad": 742584,
         "precioNeto": 1856404, "margen": 0.4, "errores": 0, "alertas": 1,
         "costosAF": {"Materiales": 178820, "Equipos": 560000, "Mano de Obra": 225000, "Otros": 150000}}
    r.update(extra)
    return r


def _sobre(datos, historia=None, resumen=None):
    return {"esquema": ESQ, "herramienta": "formulador", "tipo": "proyecto", "generado": "x",
            "autor": "Persona", "historia": historia or [], "resumen": resumen or _resumen(), "datos": datos}


def _guardar(raiz, datos, historia=None, nombre=None):
    carpeta = fz.carpeta_repositorio(raiz)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / (nombre or fz.nombre_archivo(datos["uid"]))
    ruta.write_text(json.dumps(_sobre(datos, historia)), encoding="utf-8")
    return ruta


def _entrega(datos, historia=None, id_="entrega001", enviado="2026-09-30T16:00:00-03:00"):
    return {"esquema": ESQ, "id": id_, "tipo": fz.TIPO_ENTREGA, "destino": fz.DESTINO,
            "origen": {"herramienta": "formulador", "usuario": "Colega", "enviado": enviado},
            "historia": historia or [], "resumen": _resumen(), "datos": datos}


@pytest.fixture
def raiz(tmp_path):
    return ic.asegurar_carpeta(tmp_path / "Intercambio")


# ── LECTURA ──────────────────────────────────────────────────────────────────

def test_lee_el_repositorio_e_ignora_lo_que_no_es_un_presupuesto(raiz):
    _guardar(raiz, _datos())
    _guardar(raiz, _datos(), nombre="a1b2c3d4e5f6-ESCRITORIO.json")      # copia de conflicto de OneDrive
    (fz.carpeta_repositorio(raiz) / "roto.json").write_text("{no", encoding="utf-8")
    (fz.carpeta_repositorio(raiz) / "otro.json").write_text(json.dumps({"esquema": ESQ, "tipo": "x"}), encoding="utf-8")
    (item,) = fz.leer_repositorio(raiz)
    assert item["uid"] == "a1b2c3d4e5f6" and item["resumen"]["precioNeto"] == 1856404


def test_repositorio_vacio(tmp_path):
    assert fz.leer_repositorio(tmp_path / "no-existe") == []


# ── ENTREGAS POR ARCHIVO ─────────────────────────────────────────────────────

@pytest.mark.parametrize("actual,historia_entrega,esperado", [
    (None, [], "nuevo"),
    ({"mod": "m1", "historia": []}, [], "conflicto"),
    ({"mod": "m1", "historia": []}, ["m1"], "aplicar"),              # la entrega viene de lo que hay
    ({"mod": "m3", "historia": ["m1", "m2"]}, ["m1"], "reemplazado"),  # la carpeta ya es más nueva
    ({"mod": "m2", "historia": []}, [], "sin-cambios"),
])
def test_decidir_entrega(actual, historia_entrega, esperado):
    m = _entrega(_datos(mod="m2"), historia_entrega)
    if esperado == "reemplazado":
        actual["historia"].append("m2")
    assert fz.decidir_entrega(m, actual) == esperado


def test_entrega_nueva_queda_en_el_repositorio_y_se_archiva(raiz):
    ic.enviar(raiz, _entrega(_datos()))
    (r,) = fz.incorporar_buzon(raiz)
    assert r["estado"] == "aplicado" and r["decision"] == "nuevo"
    (item,) = fz.leer_repositorio(raiz)
    assert item["autor"] == "Colega" and item["resumen"]["costoDirecto"] == 1113820
    assert not list((raiz / ic.CARPETA_BUZON).glob("*.json"))
    (archivado,) = (raiz / ic.CARPETA_PROCESADO).rglob("*.json")
    assert json.loads(archivado.read_text(encoding="utf-8"))["resultado"]["estado"] == "aplicado"


def test_entrega_que_viene_de_la_version_del_repositorio_la_reemplaza(raiz):
    _guardar(raiz, _datos(mod="m1", titulo="Antes"))
    ic.enviar(raiz, _entrega(_datos(mod="m2", titulo="Después"), historia=["m1"]))
    (r,) = fz.incorporar_buzon(raiz)
    assert r["decision"] == "aplicar"
    (item,) = fz.leer_repositorio(raiz)
    assert item["datos"]["titulo"] == "Después" and item["historia"] == ["m1"]


def test_entrega_en_conflicto_queda_como_copia_sin_perder_nada(raiz):
    _guardar(raiz, _datos(mod="m1", titulo="En la carpeta"))
    ic.enviar(raiz, _entrega(_datos(mod="m9", titulo="Por archivo")))
    (r,) = fz.incorporar_buzon(raiz)
    assert r["decision"] == "conflicto"
    titulos = sorted(i["datos"]["titulo"] for i in fz.leer_repositorio(raiz))
    assert titulos == ["En la carpeta", "Por archivo (entregado por archivo)"]


def test_entrega_mas_vieja_que_el_repositorio_no_lo_toca(raiz):
    _guardar(raiz, _datos(mod="m3", titulo="Nuevo"), historia=["m1", "m2"])
    ic.enviar(raiz, _entrega(_datos(mod="m2", titulo="Viejo"), historia=["m1"]))
    (r,) = fz.incorporar_buzon(raiz)
    assert r["estado"] == "reemplazado"
    assert fz.leer_repositorio(raiz)[0]["datos"]["titulo"] == "Nuevo"


def test_entrega_invalida_se_rechaza(raiz):
    m = _entrega(_datos())
    del m["datos"]["modificado"]
    ic.enviar(raiz, m)
    (r,) = fz.incorporar_buzon(raiz)
    assert r["estado"] == "rechazado" and fz.leer_repositorio(raiz) == []


def test_mensajes_para_otras_herramientas_no_se_tocan(raiz):
    otro = {"esquema": ESQ, "id": "envio001", "tipo": "presupuesto-proyecto", "destino": "analisis-financiero",
            "origen": {"herramienta": "formulador", "enviado": "2026-09-30T10:00:00-03:00"}}
    ic.enviar(raiz, otro)
    assert fz.incorporar_buzon(raiz) == []
    assert len(list((raiz / ic.CARPETA_BUZON).glob("*.json"))) == 1


# ── REVISIÓN CON CLAUDE ──────────────────────────────────────────────────────

def test_novedades_y_revisadas(raiz, tmp_path):
    estado = tmp_path / "revisadas.json"
    _guardar(raiz, _datos(uid="uno000000001", mod="m1"))
    nov = fz.novedades(fz.leer_repositorio(raiz), fz.leer_revisadas(estado))
    assert [i["uid"] for i in nov["nuevos"]] == ["uno000000001"] and nov["cambiados"] == []
    fz.marcar_revisadas(fz.leer_repositorio(raiz), estado)
    assert fz.novedades(fz.leer_repositorio(raiz), fz.leer_revisadas(estado)) == {"nuevos": [], "cambiados": []}
    _guardar(raiz, _datos(uid="uno000000001", mod="m2"), historia=["m1"])
    _guardar(raiz, _datos(uid="dos000000002", mod="m1"))
    nov = fz.novedades(fz.leer_repositorio(raiz), fz.leer_revisadas(estado))
    assert [i["uid"] for i in nov["nuevos"]] == ["dos000000002"]
    assert [i["uid"] for i in nov["cambiados"]] == ["uno000000001"]


def test_linea_legible(raiz):
    _guardar(raiz, _datos(estado="Adjudicada"))
    texto = fz.linea(fz.leer_repositorio(raiz)[0])
    assert "QPN-2026-001 v1 «Oferta de prueba»" in texto and "Adjudicada" in texto
    assert "costo $1.113.820" in texto and "precio neto $1.856.404" in texto and "margen 40,0 %" in texto


# ── ENVIAR (librería común) ──────────────────────────────────────────────────

def test_enviar_valida_y_usa_el_nombre_del_formulador(raiz):
    ruta = ic.enviar(raiz, _entrega(_datos(), id_="abcdef123456"))
    assert ruta.name == "20260930-160000_formulador_formulacion_abcdef123456.json"
    with pytest.raises(ValueError):
        ic.enviar(raiz, {"esquema": ESQ})
