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

Ampliado (auditoría de todo el repo) para cubrir el resto de los KPIs que
también se recalculan por separado en cada camino y que hasta entonces no
tenían este contrato: costo%/estructura%/desviación%/ahorro-sobrecosto por
categoría, y CLTV/Clasificación de clientes.
"""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

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


# ── Cobertura ampliada: el resto de los KPIs por categoria tambien se ──────
# recalculan por separado en cada camino (bv._kpis_por_categoria vs
# kr.recalcular_proyecto) y, hasta acá, nada los comparaba entre sí -- solo
# Nota/Evaluación tenían este contrato. El mismo tipo de divergencia que ya
# ocurrió una vez con la Nota podría colarse en cualquiera de estos sin que
# la suite lo note.
_CATEGORIA_CORTA_A_LARGA = {"materiales": "Materiales", "equipos": "Equipos", "mo": "MO", "otros": "Otros"}


def test_kpis_por_categoria_y_totales_coinciden_entre_visualizador_y_reportes():
    for caso in (CASO_BAJO_PRESUPUESTO, CASO_SOBRE_PRESUPUESTO):
        kpi_viz, indicadores = _notas_de_ambos_caminos(caso)
        assert kpi_viz["desviacion_pct"] == pytest.approx(indicadores["Desviación % Total"])
        assert kpi_viz["ahorro_sobrecosto_total"] == pytest.approx(indicadores["Ahorro/Sobrecosto Total"])
        for corta, larga in _CATEGORIA_CORTA_A_LARGA.items():
            assert kpi_viz["costo_pct_venta"][corta] == pytest.approx(
                indicadores[f"Costo {larga} % de venta"]
            )
            assert kpi_viz["estructura_pct"][corta] == pytest.approx(
                indicadores[f"Estructura % {larga}"]
            )
            assert kpi_viz["desviacion_pct_categoria"][corta] == pytest.approx(
                indicadores[f"Desviación % {larga}"]
            )
            assert kpi_viz["ahorro_sobrecosto"][corta] == pytest.approx(
                indicadores[f"Ahorro/Sobrecosto {larga}"]
            )


# ── Contrato de CLTV/Clientes: mismo problema, otro par de implementaciones ─
# kr.calcular_cltv_clientes (reportes) y bv.calcular_clientes (dashboard)
# recalculan AOV/Vida/Meses activo/Frecuencia/Margen%/CLTV/Clasificación cada
# uno por su cuenta a partir de la hoja "Proyectos" -- tampoco tenían un test
# que los comparara entre sí. 3 clientes (2 con 2 proyectos, 1 con uno solo)
# para ejercitar tanto el promedio de fechas como el caso de un solo proyecto,
# y que haya 3 valores de CLTV distintos para que la clasificación por
# percentil (67/33) tenga los tres tramos posibles.
def _proyecto_cliente(tag, cliente, fecha_inicio, venta, proy, real):
    corto = {
        "tag": tag, "nombre": tag, "cliente": cliente,
        "estado": "Terminado", "fecha_inicio": fecha_inicio, "fecha_cierre": None,
        "categoria": "I+D+i", "monto_venta": venta,
        "materiales_proy": proy[0], "equipos_proy": proy[1],
        "mo_proy": proy[2], "otros_proy": proy[3], "mo_real": real[3],
    }
    encabezados = {
        "Cliente": cliente, "Fecha de inicio": fecha_inicio,
        "Monto de Venta (sin IVA)": venta,
        "Costos Materiales Proyectados": proy[0], "Costos Equipos Proyectados": proy[1],
        "Mano de Obra Proyectada": proy[2], "Otros Costos Proyectados": proy[3],
        "Mano de Obra Real": real[3],
    }
    reales = {"Materiales": real[0], "Equipos": real[1], "Otros": real[2]}
    return corto, encabezados, reales


_PROYECTOS_CLIENTES = [
    _proyecto_cliente("A1", "Cliente A", datetime(2026, 1, 1), 5_000_000,
                       (1_000_000, 500_000, 500_000, 200_000), (900_000, 450_000, 150_000, 480_000)),
    _proyecto_cliente("A2", "Cliente A", datetime(2026, 4, 1), 6_000_000,
                       (1_200_000, 600_000, 600_000, 300_000), (1_100_000, 550_000, 250_000, 580_000)),
    _proyecto_cliente("B1", "Cliente B", datetime(2026, 2, 1), 10_000_000,
                       (2_000_000, 1_000_000, 1_000_000, 500_000), (1_500_000, 800_000, 400_000, 900_000)),
    _proyecto_cliente("B2", "Cliente B", datetime(2026, 8, 1), 12_000_000,
                       (2_400_000, 1_200_000, 1_200_000, 600_000), (1_800_000, 900_000, 500_000, 1_000_000)),
    _proyecto_cliente("C1", "Cliente C", datetime(2026, 5, 1), 2_000_000,
                       (500_000, 300_000, 300_000, 100_000), (600_000, 350_000, 150_000, 350_000)),
]


def test_cltv_y_clasificacion_de_clientes_coinciden_entre_visualizador_y_reportes():
    kpis_bv = [bv.calcular_kpis_proyecto(corto, reales) for corto, _, reales in _PROYECTOS_CLIENTES]
    proyectos_por_tag = {corto["tag"]: corto for corto, _, _ in _PROYECTOS_CLIENTES}
    clientes_bv = {c["cliente"]: c for c in bv.calcular_clientes(kpis_bv, proyectos_por_tag)}

    proyectos_actualizados_kr = [
        kr.recalcular_proyecto(encabezados, reales)[0] for _, encabezados, reales in _PROYECTOS_CLIENTES
    ]
    clientes_kr = kr.calcular_cltv_clientes(proyectos_actualizados_kr)

    assert set(clientes_bv) == {"Cliente A", "Cliente B", "Cliente C"}
    assert set(clientes_kr) == set(clientes_bv)

    for nombre, c_bv in clientes_bv.items():
        c_kr = clientes_kr[nombre]
        assert c_bv["aov"] == pytest.approx(c_kr["AOV (Valor promedio de venta)"])
        assert c_bv["vida"] == c_kr["Vida del cliente (n° de proyectos)"]
        assert c_bv["meses_activo"] == pytest.approx(c_kr["Meses activo"])
        assert c_bv["frecuencia"] == pytest.approx(c_kr["Frecuencia de compra (proyectos/año)"])
        assert c_bv["margen_pct"] == pytest.approx(c_kr["Margen de utilidad %"])
        assert c_bv["cltv"] == pytest.approx(c_kr["CLTV"])
        assert c_bv["clasificacion"] == c_kr["Clasificación"]
