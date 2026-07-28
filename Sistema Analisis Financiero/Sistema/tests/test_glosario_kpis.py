import analisis_financiero as af


def test_una_fila_por_kpi_del_glosario(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")

    af.asegurar_hoja_glosario_kpis(wb)

    ws = wb[af.HOJA_GLOSARIO_KPIS]
    assert ws.max_row == 1 + len(af.GLOSARIO_KPIS)
    assert ws.cell(row=2, column=1).value == af.GLOSARIO_KPIS[0][0]
    assert ws.cell(row=2, column=2).value == af.GLOSARIO_KPIS[0][1]


def test_incluye_los_kpis_nuevos_de_este_spec(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_glosario_kpis(wb)

    nombres = [fila[0] for fila in af.GLOSARIO_KPIS]
    for esperado in ("Nota del Proyecto", "Evaluación", "CLTV", "Clasificación (Clientes)"):
        assert esperado in nombres


def test_no_incluye_los_5_kpis_redundantes_eliminados_2026_07_28(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_glosario_kpis(wb)

    nombres = [fila[0] for fila in af.GLOSARIO_KPIS]
    for eliminado in (
        "Rentabilidad sobre costo", "Productividad (Materiales/Equipos/MO/Otros)",
    ):
        assert eliminado not in nombres


def test_incluye_los_4_kpis_nuevos_2026_07_28(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_glosario_kpis(wb)

    nombres = [fila[0] for fila in af.GLOSARIO_KPIS]
    for esperado in (
        "Desviación % Total",
        "Ahorro/Sobrecosto neto en $ (por categoría y total)",
        "Estructura % del costo real (mix, por categoría)",
        "% del Total Real del proyecto (Detalle Costos Reales)",
    ):
        assert esperado in nombres


def test_incluye_los_2_kpis_nuevos_2026_07_28_segunda_tanda(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_glosario_kpis(wb)

    nombres = [fila[0] for fila in af.GLOSARIO_KPIS]
    for esperado in (
        "Peso del proyecto en la cartera de ventas (%)",
        "Margen por día de ejecución",
    ):
        assert esperado in nombres


def test_se_reescribe_completa_sin_duplicar_entre_corridas(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_glosario_kpis(wb)
    af.asegurar_hoja_glosario_kpis(wb)

    ws = wb[af.HOJA_GLOSARIO_KPIS]
    assert ws.max_row == 1 + len(af.GLOSARIO_KPIS)
