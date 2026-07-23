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


def test_se_reescribe_completa_sin_duplicar_entre_corridas(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_glosario_kpis(wb)
    af.asegurar_hoja_glosario_kpis(wb)

    ws = wb[af.HOJA_GLOSARIO_KPIS]
    assert ws.max_row == 1 + len(af.GLOSARIO_KPIS)
