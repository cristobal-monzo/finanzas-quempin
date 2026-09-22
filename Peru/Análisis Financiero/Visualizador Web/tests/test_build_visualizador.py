import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import openpyxl

_RUTA_BV = Path(__file__).resolve().parent.parent / "build_visualizador.py"
_spec = importlib.util.spec_from_file_location("build_visualizador_af_pe", _RUTA_BV)
bv = importlib.util.module_from_spec(_spec)
sys.modules["build_visualizador_af_pe"] = bv
_spec.loader.exec_module(bv)


def test_extraer_datos_saneados_sin_proyectos_no_falla(tmp_path):
    wb = openpyxl.Workbook()
    ws_p = wb.active
    ws_p.title = "Proyectos"
    for c, h in enumerate(bv.af.HEADERS_PROYECTOS, 1):
        ws_p.cell(row=1, column=c, value=h)
    ws_d = wb.create_sheet("Detalle Costos Reales")
    for c, h in enumerate(bv.af.HEADERS_DETALLE_COSTOS_REALES, 1):
        ws_d.cell(row=1, column=c, value=h)
    ruta = tmp_path / "Análisis de Proyectos Perú.xlsx"
    wb.save(str(ruta))

    data = bv.extraer_datos_saneados(ruta)
    assert data["proyectos"] == []
    assert data["clientes"] == []
    assert data["pendientes"] == []
    assert data["kpis_proyectos"]["n_completos"] == 0
    # Sin proyectos no hay promedio que inventar: vacío, el tablero muestra "—".
    assert data["kpis_proyectos"]["nota_promedio"] is None
    # Mismo build que Chile (2026-09-21), con la moneda de Perú.
    assert data["pais"] == "PE"
    assert data["moneda"] == {"simbolo": "S/", "locale": "es-PE"}


def test_extraer_datos_saneados_con_un_proyecto_completo_no_falla(tmp_path):
    """Regresion del bug real de la ola de correcciones 2026-08-31: este
    modulo tenia su propia CLAVE_POR_ENCABEZADO/leer_proyectos con la clave
    vieja 'Estado' cuando el modulo compartido analisis_financiero.py ya
    habia renombrado esa columna a '% Avance' -- KeyError en
    es_proyecto_completo y ValueError en leer_proyectos. Quedo latente
    porque el unico test de este archivo usaba un Excel sin ninguna fila de
    proyecto, así que 'Estado' vs. '% Avance' nunca se ejercitaba de
    verdad."""
    wb = openpyxl.Workbook()
    ws_p = wb.active
    ws_p.title = "Proyectos"
    for c, h in enumerate(bv.af.HEADERS_PROYECTOS, 1):
        ws_p.cell(row=1, column=c, value=h)
    valores = {
        "TAG proyecto": "LIMA", "Nombre del proyecto": "LIMA", "Cliente": "ACME",
        "% Avance": 0.5, "Fecha de inicio": datetime(2026, 1, 15),
        "Monto de Venta (sin IVA)": 1_000_000,
        "Costos Materiales Proyectados": 300_000, "Costos Equipos Proyectados": 200_000,
        "Mano de Obra Proyectada": 200_000, "Otros Costos Proyectados": 100_000,
        "Mano de Obra Real": 350_000,
    }
    for nombre_col, valor in valores.items():
        col = bv.af.HEADERS_PROYECTOS.index(nombre_col) + 1
        ws_p.cell(row=2, column=col, value=valor)
    ws_d = wb.create_sheet("Detalle Costos Reales")
    for c, h in enumerate(bv.af.HEADERS_DETALLE_COSTOS_REALES, 1):
        ws_d.cell(row=1, column=c, value=h)
    ruta = tmp_path / "Análisis de Proyectos Perú.xlsx"
    wb.save(str(ruta))

    data = bv.extraer_datos_saneados(ruta)

    assert data["kpis_proyectos"]["n_completos"] == 1
    proyecto = data["proyectos"][0]
    assert proyecto["avance"] == 0.5
    assert "estado" not in proyecto
    # La Nota Parcial se reemplazó por la estimación al cierre (2026-09-21):
    # 350.000 gastados de 800.000 al 50% -> 350.000 + 400.000 al cierre.
    assert "nota_parcial" not in proyecto
    assert proyecto["costo_estimado_cierre"] == 750_000
    assert proyecto["nota"] == bv.af.calcular_nota(0.25, 750_000 / 800_000 - 1)


def test_peru_no_tiene_template_propio():
    """Unificado con Chile el 2026-09-21: la copia completa del template ya
    se había quedado atrás dos veces."""
    carpeta = Path(__file__).resolve().parent.parent
    assert not (carpeta / "template.html").exists()
    assert bv._comun.RUTA_TEMPLATE.exists()
