# -*- coding: utf-8 -*-
"""uso_portal.py: suma lo que cada navegador anotó. Datos ficticios en tmp_path."""
import json
from datetime import date

import uso_portal


def _escribir(raiz, nombre, dias):
    carpeta = raiz / "publicado" / "uso-portal"
    carpeta.mkdir(parents=True, exist_ok=True)
    sobre = {"esquema": "quempin.intercambio/1", "herramienta": "portal", "generado": "2026-11-09T10:00:00-03:00",
             "datos": {"dispositivo": nombre, "dias": dias}}
    (carpeta / f"{nombre}.json").write_text(json.dumps(sobre), encoding="utf-8")


def test_suma_aperturas_y_cuenta_navegadores_desde_una_fecha(tmp_path):
    _escribir(tmp_path, "aaaaaaaa", [{"fecha": "2026-11-09", "herramienta": "planilla", "aperturas": 3},
                                     {"fecha": "2026-09-01", "herramienta": "planilla", "aperturas": 50}])
    _escribir(tmp_path, "bbbbbbbb", [{"fecha": "2026-11-08", "herramienta": "planilla", "aperturas": 1},
                                     {"fecha": "2026-11-08", "herramienta": "formulador", "aperturas": 2}])
    (tmp_path / "publicado" / "uso-portal" / "roto.json").write_text("{a medio", encoding="utf-8")
    r = uso_portal.resumen(uso_portal.leer(tmp_path), date(2026, 11, 1))
    assert r["aperturas"] == {"planilla": 4, "formulador": 2}
    assert r["navegadores"] == {"planilla": 2, "formulador": 1}
    assert r["total"] == 6 and r["activos"] == 2


def test_sin_carpeta_no_hay_datos(tmp_path):
    assert uso_portal.leer(tmp_path) == []
