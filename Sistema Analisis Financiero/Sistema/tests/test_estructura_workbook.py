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
