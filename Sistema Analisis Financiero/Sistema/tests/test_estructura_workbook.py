import openpyxl

import analisis_financiero as af


def test_crea_las_3_hojas_con_encabezados_si_no_existe_el_archivo(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)

    assert af.HOJA_PROYECTOS in wb.sheetnames
    assert af.HOJA_DETALLE_COSTOS_REALES in wb.sheetnames
    assert af.HOJA_INDICADORES in wb.sheetnames

    ws = wb[af.HOJA_PROYECTOS]
    assert ws.cell(row=1, column=1).value == "TAG proyecto"
    assert ws.cell(row=1, column=2).value == "Nombre del proyecto"
    assert ws.cell(row=1, column=19).value == "Desviación % (Real vs Proyectado)"


def test_elimina_hoja1_vacia_al_migrar_un_archivo_existente(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb_previo = openpyxl.Workbook()
    wb_previo.active.title = "Hoja1"
    wb_previo.save(ruta)

    wb = af.asegurar_estructura_workbook(ruta)

    assert "Hoja1" not in wb.sheetnames
    assert af.HOJA_PROYECTOS in wb.sheetnames


def test_no_toca_una_hoja_proyectos_que_ya_existe(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb_previo = openpyxl.Workbook()
    ws_previo = wb_previo.active
    ws_previo.title = af.HOJA_PROYECTOS
    ws_previo.cell(row=2, column=1, value="UMAG")
    ws_previo.cell(row=2, column=2, value="UMAG")
    wb_previo.save(ruta)

    wb = af.asegurar_estructura_workbook(ruta)

    ws = wb[af.HOJA_PROYECTOS]
    assert ws.cell(row=2, column=1).value == "UMAG"


def test_agrega_encabezados_nuevos_a_una_hoja_existente_sin_tocar_los_viejos(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb_previo = openpyxl.Workbook()
    ws_previo = wb_previo.active
    ws_previo.title = af.HOJA_PROYECTOS
    # Simula un archivo real creado ANTES de que existiera la columna
    # "Cliente" -- solo tiene los 19 headers originales, no el 20.
    for col, encabezado in enumerate(af.HEADERS_PROYECTOS[:19], start=1):
        ws_previo.cell(row=1, column=col, value=encabezado)
    ws_previo.cell(row=2, column=1, value="UMAG")
    ws_previo.cell(row=2, column=2, value="UMAG")
    wb_previo.save(ruta)

    wb = af.asegurar_estructura_workbook(ruta)

    ws = wb[af.HOJA_PROYECTOS]
    assert ws.cell(row=1, column=1).value == "TAG proyecto"
    assert ws.cell(row=1, column=20).value == "Cliente"
    assert ws.cell(row=2, column=1).value == "UMAG"


def test_hoja_proyectos_incluye_columna_cliente_al_final(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)

    ws = wb[af.HOJA_PROYECTOS]
    assert ws.cell(row=1, column=20).value == "Cliente"


def test_hoja_indicadores_incluye_nota_y_evaluacion(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)

    ws = wb[af.HOJA_INDICADORES]
    assert ws.cell(row=1, column=17).value == "Nota del Proyecto"
    assert ws.cell(row=1, column=18).value == "Evaluación"


def test_crea_hoja_clientes_con_encabezados(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)

    assert af.HOJA_CLIENTES in wb.sheetnames
    ws = wb[af.HOJA_CLIENTES]
    assert ws.cell(row=1, column=1).value == "Cliente"
    assert ws.cell(row=1, column=7).value == "CLTV"
    assert ws.cell(row=1, column=8).value == "Clasificación"


def test_crea_hoja_glosario_kpis_con_encabezados(tmp_path):
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)

    assert af.HOJA_GLOSARIO_KPIS in wb.sheetnames
    ws = wb[af.HOJA_GLOSARIO_KPIS]
    assert ws.cell(row=1, column=1).value == "KPI"
    assert ws.cell(row=1, column=4).value == "Qué significa el resultado"
