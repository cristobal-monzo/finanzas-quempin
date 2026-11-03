"""Un prefijo de N° Ref. es el TAG del proyecto en Análisis Financiero, el
Portal y el Formulador: dos proyectos con el mismo prefijo suman sus costos.
Caso real (2026-11-03): la carpeta «280. UMAG - Conexión y PH Lab 1» derivaba
«UMAG», el prefijo de otro proyecto (UMAG Linea de H2)."""
import pytest

import auditor_centro_costos as acc


@pytest.fixture(autouse=True)
def _limpio(monkeypatch):
    monkeypatch.setattr(acc, "PREFIJOS_PROYECTO", {"UMAG": "UMAG", "Cesfam Limache": "CFLI"})
    acc.registrar_duenos_prefijo([])
    yield
    acc.registrar_duenos_prefijo([])


def test_un_proyecto_nuevo_no_deriva_el_prefijo_de_otro():
    acc.registrar_duenos_prefijo([{"n_ref": "UMAG-045", "proyecto": "UMAG"}])
    nuevo = acc.normalizar_nombre_proyecto("280. UMAG - Conexión y PH Lab 1")
    prefijo = acc.prefijo_para_proyecto(nuevo)
    assert prefijo != "UMAG"
    assert prefijo == "UMA2"
    # Estable dentro de la corrida y distinto para un tercero
    assert acc.prefijo_para_proyecto(nuevo) == "UMA2"
    assert acc.prefijo_para_proyecto("Umag tercera etapa") == "UMA3"


def test_tampoco_el_de_un_prefijo_definido_sin_documentos_aun():
    acc.PREFIJOS_PROYECTO["Cesfam Constitución"] = "CESF"
    assert acc.prefijo_para_proyecto("Cesfam Otro") == "CES2"


def test_un_proyecto_que_ya_tiene_documentos_sigue_con_su_prefijo_derivado():
    acc.registrar_duenos_prefijo([{"n_ref": "UARE-001", "proyecto": "UA Reactor"},
                                  {"n_ref": "UMAG-001", "proyecto": "UMAG"}])
    assert acc.prefijo_para_proyecto("UA Reactor") == "UARE"
    assert acc.prefijo_para_proyecto("UMAG") == "UMAG"


def test_siguiente_n_ref_usa_el_prefijo_propio():
    acc.registrar_duenos_prefijo([{"n_ref": "UMAG-045", "proyecto": "UMAG"}])
    max_seq = {"UMAG": 45}
    assert acc.siguiente_n_ref("UMAG - Conexión y PH Lab1", max_seq) == "UMA2-001"
    assert acc.siguiente_n_ref("UMAG", max_seq) == "UMAG-046"
