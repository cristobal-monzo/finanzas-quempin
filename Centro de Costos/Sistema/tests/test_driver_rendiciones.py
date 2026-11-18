"""Los documentos que llegan en una rendición del Portal (2026-11-18) traen lo que una persona revisó: `status` lo
muestra junto a cada pendiente, buscado por país, carpeta y nombre del archivo (rendiciones.json del intercambio)."""
import importlib.util
import json
import sys
from pathlib import Path

_DRIVER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / ".claude" / "skills" / "Registro_Centro_de_Costos" / "driver.py"
)
_spec = importlib.util.spec_from_file_location("driver_bajo_prueba_rendiciones", _DRIVER_PATH)
driver = importlib.util.module_from_spec(_spec)
sys.modules["driver_bajo_prueba_rendiciones"] = driver
_spec.loader.exec_module(driver)

RENDICIONES = [{
    "id": "ren1", "numero": "R-20261118-1000-NB", "tipo": "recuperacion", "deudor": "Persona de Ejemplo", "total": 46000, "cantidad": 2,
    "documentos": [
        {"pais": "CL", "carpeta": "280. Obra de ejemplo", "archivo": "R - 1 Factura 4512.jpg", "mensaje": "m1", "n": 1, "tipo": "Factura",
         "numero": "4512", "fecha": "14-10-2026", "proveedor": "Estación Ejemplo Ltda.", "rut": "76.111.111-6", "detalle": "Combustible", "valor": 40000},
        {"pais": "CL", "carpeta": "Gastos Generales", "archivo": "R - 2 Boleta 778.pdf", "mensaje": "m2", "n": 2, "tipo": "Boleta",
         "numero": "778", "fecha": "02-11-2026", "detalle": "Colación", "valor": 6000},
    ],
}]


def test_dato_de_rendicion_por_carpeta_y_archivo_sin_distinguir_mayusculas():
    d = driver.dato_de_rendicion(RENDICIONES, "CL", "280. OBRA de ejemplo", "r - 1 factura 4512.JPG")
    assert d["numero"] == "4512" and d["valor"] == 40000
    assert d["rendicion"] == {"numero": "R-20261118-1000-NB", "deudor": "Persona de Ejemplo", "tipo": "recuperacion"}
    assert driver.dato_de_rendicion(RENDICIONES, "CL", "Gastos Generales", "R - 1 Factura 4512.jpg") is None   # otra carpeta
    assert driver.dato_de_rendicion(RENDICIONES, "PE", "280. Obra de ejemplo", "R - 1 Factura 4512.jpg") is None
    assert driver.dato_de_rendicion([], "CL", "x", "y") is None


def test_describir_dato_rendicion():
    d = driver.dato_de_rendicion(RENDICIONES, "CL", "280. Obra de ejemplo", "R - 1 Factura 4512.jpg")
    txt = driver.describir_dato_rendicion(d)
    assert txt == ("Factura N° 4512 · 14-10-2026 · Combustible · $40.000 · Estación Ejemplo Ltda. (RUT 76.111.111-6) · "
                   "rendición R-20261118-1000-NB de Persona de Ejemplo")


def test_status_muestra_los_datos_de_la_rendicion_de_un_pendiente(monkeypatch, capsys):
    monkeypatch.setattr(driver, "rendiciones_publicadas", lambda: RENDICIONES)
    sin_datos = [{"proyecto": "Gastos Generales", "archivo": "R - 2 Boleta 778.pdf"}, {"proyecto": "Gastos Generales", "archivo": "otra.jpg"}]
    con = driver.mostrar_datos_de_rendiciones(sin_datos, "CL")
    assert [i["archivo"] for i, _ in con] == ["R - 2 Boleta 778.pdf"]
    salida = capsys.readouterr().out
    assert "llegaron en una rendición del Portal" in salida and "Boleta N° 778 · 02-11-2026 · Colación · $6.000" in salida


def test_rendiciones_publicadas_lee_el_intercambio(tmp_path, monkeypatch):
    (tmp_path / "publicado").mkdir()
    (tmp_path / "publicado" / "rendiciones.json").write_text(
        json.dumps({"esquema": "quempin.intercambio/1", "herramienta": "procesador", "datos": {"rendiciones": RENDICIONES}}), encoding="utf-8")

    class _Ubicacion:
        @staticmethod
        def ubicar_intercambio(_):
            return tmp_path

    class _Ctx:
        def __enter__(self):
            return _Ubicacion

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(driver.acc, "_modulo_hermano_fresco", lambda *a, **k: _Ctx())
    assert driver.rendiciones_publicadas() == RENDICIONES
    monkeypatch.setattr(driver.acc, "_modulo_hermano_fresco", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sin intercambio")))
    assert driver.rendiciones_publicadas() == []
