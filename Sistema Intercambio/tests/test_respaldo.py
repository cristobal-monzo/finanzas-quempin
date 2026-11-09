"""Respaldo diario de la carpeta de Intercambio (respaldo.py, 2026-11-09)."""
import zipfile
from datetime import datetime

import procesar
import respaldo


def _carpeta(tmp_path):
    raiz = tmp_path / "intercambio"
    (raiz / "publicado" / "planificacion").mkdir(parents=True)
    (raiz / "publicado" / "planificacion" / "semana.json").write_text("{}", encoding="utf-8")
    (raiz / "buzon").mkdir()
    (raiz / "buzon" / "m.json").write_text("{}", encoding="utf-8")
    return raiz


def test_zip_con_carpetas_y_planilla(tmp_path):
    raiz = _carpeta(tmp_path)
    planilla = tmp_path / "Planilla.xlsx"
    planilla.write_bytes(b"x")
    zip_, n = respaldo.respaldar(raiz, planilla, tmp_path / "r", datetime(2026, 11, 9))
    assert zip_.name == "intercambio-2026-11-09.zip" and n == 3
    nombres = set(zipfile.ZipFile(zip_).namelist())
    assert {"publicado/planificacion/semana.json", "buzon/m.json", "planilla/Planilla.xlsx"} <= nombres


def test_guarda_solo_los_ultimos(tmp_path):
    raiz = _carpeta(tmp_path)
    destino = tmp_path / "r"
    for d in range(1, 36):
        respaldo.respaldar(raiz, None, destino, datetime(2026, 10, 1).replace(day=1) if d == 1 else datetime(2026, 10 + (d > 31), (d - 1) % 31 + 1))
    zips = sorted(destino.glob("intercambio-*.zip"))
    assert len(zips) == respaldo.DIAS_A_GUARDAR
    assert not list(destino.glob("*.tmp"))


def test_paso_una_vez_al_dia(tmp_path, monkeypatch):
    raiz = _carpeta(tmp_path)
    monkeypatch.setattr(procesar.ubicacion, "ubicar_planilla", lambda aqui: None)
    texto, firma = procesar.paso_respaldo(raiz, None, False)
    hoy = datetime.now().strftime("%Y-%m-%d")
    assert firma == hoy and "2 archivos" in texto
    assert (tmp_path / "respaldos" / respaldo.nombre_del_dia()).is_file()
    assert procesar.paso_respaldo(raiz, hoy, False) == ("respaldo del día ya hecho", None)
