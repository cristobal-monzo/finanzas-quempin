# -*- coding: utf-8 -*-
"""
Test de CONTRATO entre los tres consumidores de los KPIs de Análisis
Financiero: el Excel (fórmulas), los reportes PDF (Reportes/
kpis_recalculados.py) y el dashboard web (Visualizador Web/
build_visualizador.py).

Existe por un bug real (auditoría 2026-07-28): la corrección que quitó el
ABS() del componente de desviación de la "Nota del Proyecto" se aplicó al
Excel y a los reportes, pero no al visualizador. El MISMO proyecto mostraba
nota 94 en el dashboard y 100 en el Excel/PDF, y ningún test lo detectaba
porque el del visualizador recalculaba la nota copiando la fórmula de la
implementación (con su bug incluido) en vez de afirmar el resultado esperado.

Estos tests comparan las salidas de los dos caminos Python entre sí y contra
la fórmula de Excel, sobre casos donde la diferencia se manifiesta.
"""

import importlib.util
import sys
from pathlib import Path

import analisis_financiero as af

_RAIZ_MODULO = Path(__file__).resolve().parents[2]

# datos_reportes.py hace "from kpis_recalculados import ..." por nombre plano
# y solo agrega Sistema/ a sys.path, nunca su propia carpeta -- cuenta con que
# quien lo importe ya tenga Reportes/ en el path (lo hace su conftest). Este
# test vive en otra suite, asi que lo agrega el mismo.
_RAIZ_REPORTES = _RAIZ_MODULO / "Reportes"
if str(_RAIZ_REPORTES) not in sys.path:
    sys.path.insert(0, str(_RAIZ_REPORTES))


def _cargar(nombre_unico: str, ruta: Path):
    spec = importlib.util.spec_from_file_location(nombre_unico, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre_unico] = modulo
    spec.loader.exec_module(modulo)
    return modulo


kr = _cargar("kpis_recalculados_contrato", _RAIZ_REPORTES / "kpis_recalculados.py")
bv = _cargar(
    "build_visualizador_contrato", _RAIZ_MODULO / "Visualizador Web" / "build_visualizador.py"
)
dr = _cargar("datos_reportes_contrato", _RAIZ_REPORTES / "datos_reportes.py")


def _caso(venta, mat_p, eq_p, mo_p, otros_p, mat_r, eq_r, otros_r, mo_r):
    """Mismo proyecto expresado en los dos vocabularios: claves cortas (lo que
    consume el visualizador) y encabezados de Excel (lo que consumen los
    reportes)."""
    corto = {
        "tag": "TEST", "nombre": "Proyecto Test", "cliente": "Cliente X",
        "estado": "Terminado", "fecha_inicio": None, "fecha_cierre": None,
        "categoria": "I+D+i", "monto_venta": venta,
        "materiales_proy": mat_p, "equipos_proy": eq_p,
        "mo_proy": mo_p, "otros_proy": otros_p, "mo_real": mo_r,
    }
    encabezados = {
        "Monto de Venta (sin IVA)": venta,
        "Costos Materiales Proyectados": mat_p,
        "Costos Equipos Proyectados": eq_p,
        "Mano de Obra Proyectada": mo_p,
        "Otros Costos Proyectados": otros_p,
        "Mano de Obra Real": mo_r,
    }
    reales = {"Materiales": mat_r, "Equipos": eq_r, "Otros": otros_r}
    return corto, encabezados, reales


# Proyecto 20% BAJO presupuesto -- el caso donde ABS() vs MAX(0,...) difieren.
CASO_BAJO_PRESUPUESTO = _caso(
    venta=10_000_000,
    mat_p=4_000_000, eq_p=2_000_000, mo_p=1_000_000, otros_p=1_000_000,
    mat_r=3_200_000, eq_r=1_600_000, otros_r=800_000, mo_r=800_000,
)
# Proyecto 20% SOBRE presupuesto -- acá ambas versiones siempre coincidieron.
CASO_SOBRE_PRESUPUESTO = _caso(
    venta=10_000_000,
    mat_p=4_000_000, eq_p=2_000_000, mo_p=1_000_000, otros_p=1_000_000,
    mat_r=4_800_000, eq_r=2_400_000, otros_r=1_200_000, mo_r=1_200_000,
)


def _notas_de_ambos_caminos(caso):
    corto, encabezados, reales = caso
    kpi_viz = bv.calcular_kpis_proyecto(corto, reales)
    _, indicadores = kr.recalcular_proyecto(encabezados, reales)
    return kpi_viz, indicadores


def test_nota_coincide_entre_visualizador_y_reportes_bajo_presupuesto():
    """El caso que estaba roto: el visualizador usaba abs(desviación) y
    castigaba haber gastado de menos."""
    kpi_viz, indicadores = _notas_de_ambos_caminos(CASO_BAJO_PRESUPUESTO)
    assert kpi_viz["desviacion_pct"] < 0, "el caso debe estar bajo presupuesto"
    assert kpi_viz["nota"] == indicadores["Nota del Proyecto"]
    assert kpi_viz["evaluacion"] == indicadores["Evaluación"]


def test_nota_coincide_entre_visualizador_y_reportes_sobre_presupuesto():
    kpi_viz, indicadores = _notas_de_ambos_caminos(CASO_SOBRE_PRESUPUESTO)
    assert kpi_viz["desviacion_pct"] > 0, "el caso debe estar sobre presupuesto"
    assert kpi_viz["nota"] == indicadores["Nota del Proyecto"]
    assert kpi_viz["evaluacion"] == indicadores["Evaluación"]


def test_gastar_de_menos_no_baja_la_nota():
    """Regla de negocio explícita (2026-07-28): estar bajo presupuesto da el
    puntaje máximo del componente de control, igual que estar justo en
    presupuesto. Sin esto, ahorrar penalizaba."""
    margen_neto = 0.30
    assert af.calcular_nota(margen_neto, -0.20) == af.calcular_nota(margen_neto, 0.0)
    assert af.calcular_nota(margen_neto, -0.99) == af.calcular_nota(margen_neto, 0.0)


def test_gastar_de_mas_si_baja_la_nota():
    margen_neto = 0.30
    assert af.calcular_nota(margen_neto, 0.20) < af.calcular_nota(margen_neto, 0.0)


def test_formula_excel_de_la_nota_usa_max_no_abs():
    """La fórmula que se escribe en el .xlsx debe expresar la misma regla que
    calcular_nota(). Si alguien reintroduce ABS() acá, el Excel volvería a
    discrepar de los dos caminos Python."""
    formula = af._formula_nota(5)
    assert "ABS(" not in formula.upper()
    assert "MAX(0," in formula.replace(" ", "")


def test_umbrales_de_evaluacion_son_los_mismos_en_formula_y_en_python():
    formula = af._formula_evaluacion(2)
    for umbral in (af.UMBRAL_EXCELENTE, af.UMBRAL_BUENO, af.UMBRAL_APROBADO):
        assert f">={umbral}" in formula.replace(" ", "")
    assert af.clasificar_evaluacion(af.UMBRAL_EXCELENTE) == "Excelente"
    assert af.clasificar_evaluacion(af.UMBRAL_BUENO) == "Bueno"
    assert af.clasificar_evaluacion(af.UMBRAL_APROBADO) == "Aprobado"
    assert af.clasificar_evaluacion(af.UMBRAL_APROBADO - 1) == "Requiere atención"


def test_completitud_es_la_misma_regla_en_dashboard_y_en_reportes():
    """Un proyecto sin 'Estado' no puede salir con KPIs en el dashboard y a la
    vez ser rechazado por los reportes -- eran dos definiciones distintas."""
    corto, encabezados, _ = CASO_BAJO_PRESUPUESTO

    assert bv.es_proyecto_completo(dict(corto, estado="Terminado", fecha_inicio="2026-01-01"))
    assert dr.proyecto_tiene_datos_completos(
        dict(encabezados, **{"Estado": "Terminado", "Fecha de inicio": "2026-01-01"})
    )

    sin_estado_corto = dict(corto, estado=None, fecha_inicio="2026-01-01")
    sin_estado_encabezados = dict(
        encabezados, **{"Estado": None, "Fecha de inicio": "2026-01-01"}
    )
    assert not bv.es_proyecto_completo(sin_estado_corto)
    assert not dr.proyecto_tiene_datos_completos(sin_estado_encabezados)


def test_cadena_vacia_cuenta_como_faltante_en_ambos_caminos():
    corto, encabezados, _ = CASO_BAJO_PRESUPUESTO
    assert not bv.es_proyecto_completo(dict(corto, estado="", fecha_inicio="2026-01-01"))
    assert not dr.proyecto_tiene_datos_completos(
        dict(encabezados, **{"Estado": "", "Fecha de inicio": "2026-01-01"})
    )


def test_cero_si_cuenta_como_dato_cargado():
    """Un costo real en 0 es un dato, no un vacío -- no debe marcar el
    proyecto como incompleto en ninguno de los dos caminos."""
    corto, encabezados, _ = CASO_BAJO_PRESUPUESTO
    assert bv.es_proyecto_completo(
        dict(corto, estado="Terminado", fecha_inicio="2026-01-01", mo_real=0)
    )
    assert dr.proyecto_tiene_datos_completos(
        dict(
            encabezados,
            **{"Estado": "Terminado", "Fecha de inicio": "2026-01-01", "Mano de Obra Real": 0},
        )
    )
