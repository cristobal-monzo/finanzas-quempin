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
    for esperado in ("Nota del Proyecto", "Evaluación", "Clasificación (Clientes)"):
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


def test_nota_parcial_y_cltv_salieron_con_la_fase_1(tmp_path):
    """2026-09-21: la Nota Parcial se reemplazó por la estimación al cierre y
    el CLTV (con AOV/Vida/Meses activo/Frecuencia) por margen acumulado y
    recompra -- el glosario no debe explicar KPIs que el libro ya no tiene."""
    nombres = [fila[0] for fila in af.GLOSARIO_KPIS]
    for eliminado in ("Nota Parcial", "CLTV", "AOV (Clientes)", "Vida del cliente",
                      "Meses activo", "Frecuencia de compra (Clientes)"):
        assert eliminado not in nombres
    for nuevo in ("Costo estimado al cierre", "Margen estimado al cierre (y %)",
                  "Desviación estimada al cierre %", "Datos completos",
                  "Venta acumulada y Margen acumulado (Clientes)",
                  "Cliente recurrente / Tasa de recompra"):
        assert nuevo in nombres


def test_se_reescribe_completa_sin_duplicar_entre_corridas(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_glosario_kpis(wb)
    af.asegurar_hoja_glosario_kpis(wb)

    ws = wb[af.HOJA_GLOSARIO_KPIS]
    assert ws.max_row == 1 + len(af.GLOSARIO_KPIS)


# ── Cobertura: toda columna de KPI real tiene un concepto en el glosario ──
# GLOSARIO_KPIS no es una copia 1:1 de HEADERS_INDICADORES/HEADERS_CLIENTES:
# varias columnas comparten a propósito un mismo concepto (ej. las 4 "Costo
# % de venta" por categoría son una sola fila de glosario) y algunos nombres
# difieren del header real (ej. columna "AOV (Valor promedio de venta)" ->
# glosario "AOV (Clientes)"). Antes nada garantizaba que una columna NUEVA
# quedara sin su concepto de glosario -- este mapa lo hace explícito y hace
# fallar el test si se agrega una columna sin decidir su fila de glosario.
# "Cliente"/"Monto de Venta" en Indicadores son columnas de apoyo para la hoja
# "Clientes" (2026-09-21), no KPIs.
COLUMNAS_IDENTIFICADORAS_INDICADORES = {
    "TAG proyecto", "Nombre del proyecto", "Cliente", "Monto de Venta (sin IVA)",
}
COLUMNAS_IDENTIFICADORAS_CLIENTES = {"Cliente"}

COLUMNA_A_KPI_GLOSARIO = {
    "Margen neto %": "Margen neto %",
    "Costo Materiales % de venta": "Costo % de venta (por categoría)",
    "Costo Equipos % de venta": "Costo % de venta (por categoría)",
    "Costo MO % de venta": "Costo % de venta (por categoría)",
    "Costo Otros % de venta": "Costo % de venta (por categoría)",
    "Estructura % Materiales": "Estructura % del costo real (mix, por categoría)",
    "Estructura % Equipos": "Estructura % del costo real (mix, por categoría)",
    "Estructura % MO": "Estructura % del costo real (mix, por categoría)",
    "Estructura % Otros": "Estructura % del costo real (mix, por categoría)",
    "Desviación % Materiales": "Desviación % (por categoría, Real vs Proyectado)",
    "Desviación % Equipos": "Desviación % (por categoría, Real vs Proyectado)",
    "Desviación % MO": "Desviación % (por categoría, Real vs Proyectado)",
    "Desviación % Otros": "Desviación % (por categoría, Real vs Proyectado)",
    "Desviación % Total": "Desviación % Total",
    "Ahorro/Sobrecosto Materiales": "Ahorro/Sobrecosto neto en $ (por categoría y total)",
    "Ahorro/Sobrecosto Equipos": "Ahorro/Sobrecosto neto en $ (por categoría y total)",
    "Ahorro/Sobrecosto MO": "Ahorro/Sobrecosto neto en $ (por categoría y total)",
    "Ahorro/Sobrecosto Otros": "Ahorro/Sobrecosto neto en $ (por categoría y total)",
    "Ahorro/Sobrecosto Total": "Ahorro/Sobrecosto neto en $ (por categoría y total)",
    "Nota del Proyecto": "Nota del Proyecto",
    "Evaluación": "Evaluación",
    "Peso del proyecto en la cartera de ventas (%)": "Peso del proyecto en la cartera de ventas (%)",
    "Margen por día de ejecución": "Margen por día de ejecución",
    "Costo estimado al cierre": "Costo estimado al cierre",
    "Margen estimado al cierre": "Margen estimado al cierre (y %)",
    "Margen estimado al cierre %": "Margen estimado al cierre (y %)",
    "Desviación estimada al cierre %": "Desviación estimada al cierre %",
    "Margen al cierre % (escenario índice de costo)": "Margen al cierre % (escenario índice de costo)",
    "Error del presupuesto %": "Error del presupuesto %",
    "Datos completos": "Datos completos",
    "N° de proyectos": "N° de proyectos (Clientes)",
    "Venta acumulada (sin IVA)": "Venta acumulada y Margen acumulado (Clientes)",
    "Margen acumulado": "Venta acumulada y Margen acumulado (Clientes)",
    "Margen %": "Margen % (Clientes)",
    "Cliente recurrente": "Cliente recurrente / Tasa de recompra",
    "Clasificación": "Clasificación (Clientes)",
}


def test_todas_las_columnas_de_kpi_reales_estan_en_el_mapa_de_cobertura():
    """Si se agrega una columna nueva a HEADERS_INDICADORES/HEADERS_CLIENTES
    sin decidir a qué fila de GLOSARIO_KPIS corresponde, este test debe
    fallar -- no quedar en silencio."""
    columnas_indicadores = set(af.HEADERS_INDICADORES) - COLUMNAS_IDENTIFICADORAS_INDICADORES
    columnas_clientes = set(af.HEADERS_CLIENTES) - COLUMNAS_IDENTIFICADORAS_CLIENTES
    todas = columnas_indicadores | columnas_clientes

    faltantes = todas - set(COLUMNA_A_KPI_GLOSARIO)
    assert faltantes == set(), f"columnas de KPI sin mapeo a glosario: {faltantes}"


def test_cada_concepto_del_mapa_de_cobertura_existe_de_verdad_en_el_glosario():
    nombres_glosario = {fila[0] for fila in af.GLOSARIO_KPIS}
    for columna, concepto in COLUMNA_A_KPI_GLOSARIO.items():
        assert concepto in nombres_glosario, (
            f"'{columna}' apunta a un concepto de glosario ('{concepto}') que no existe"
        )


def test_glosario_documenta_avance_y_estimacion_al_cierre():
    """El Excel se explica solo: todo KPI del libro tiene su fila en
    'Glosario KPIs' (pedido explícito del usuario, spec 2026-07-21)."""
    kpis = [fila[0] for fila in af.GLOSARIO_KPIS]
    assert "% Avance" in kpis
    assert "Costo estimado al cierre" in kpis
    assert all(len(fila) == 4 for fila in af.GLOSARIO_KPIS)
    assert all(texto.strip() for fila in af.GLOSARIO_KPIS for texto in fila)
