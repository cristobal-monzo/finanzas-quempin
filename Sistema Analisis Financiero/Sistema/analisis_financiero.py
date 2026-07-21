# -*- coding: utf-8 -*-
"""
analisis_financiero.py -- Consolidador de costos reales por proyecto para
QUEMPIN SpA. Lee Centro de Costos.xlsx (SOLO LECTURA, nunca lo escribe) y
mantiene Análisis de Proyectos.xlsx (3 hojas: Proyectos, Detalle Costos
Reales, Indicadores). Ver docs/superpowers/specs/2026-07-20-analisis-
financiero-design.md para el diseño completo.
"""

import shutil
from datetime import datetime
from pathlib import Path

import openpyxl

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────

RAIZ = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ.parent
# Reorganizado 2026-07-21: el código/skill vive en "Sistema Analisis
# Financiero/" (esta carpeta), separado de "Análisis Financiero/" que
# contiene solo el Excel de trabajo -- ambas son carpetas hermanas bajo la
# raíz de Finanzas QUEMPIN/. RAIZ_DATOS apunta a la carpeta con el Excel.
RAIZ_DATOS = RAIZ_MODULO.parent / "Análisis Financiero"
RUTA_EXCEL = RAIZ_DATOS / "Análisis de Proyectos.xlsx"
RAIZ_RESPALDOS = RAIZ_MODULO / "Respaldos"

RAIZ_CENTRO_COSTOS = RAIZ_MODULO.parent / "Centro de Costos"
RUTA_EXCEL_CENTRO_COSTOS = RAIZ_CENTRO_COSTOS / "Excel" / "Centro de Costos.xlsx"
RAIZ_FACTURAS_CENTRO_COSTOS = (
    RAIZ_CENTRO_COSTOS / "Sitio de comunicación - Centro de Costos 1" / "Facturas y Boletas"
)

HOJA_PROYECTOS = "Proyectos"
HOJA_DETALLE_COSTOS_REALES = "Detalle Costos Reales"
HOJA_INDICADORES = "Indicadores"

HEADERS_PROYECTOS = [
    "TAG proyecto", "Nombre del proyecto", "Estado", "Fecha de inicio",
    "Fecha de cierre", "Monto de Venta (sin IVA)",
    "Costos Materiales Proyectados", "Costos Equipos Proyectados",
    "Mano de Obra Proyectada", "Otros Costos Proyectados",
    "Costos Materiales Reales", "Costos Equipos Reales",
    "Otros Costos Reales", "Mano de Obra Real", "Total Proyectado",
    "Total Real", "Margen Proyectado", "Margen Real",
    "Desviación % (Real vs Proyectado)",
]
HEADERS_DETALLE_COSTOS_REALES = ["TAG proyecto", "Subcategoría", "Bucket", "Total sin IVA"]
HEADERS_INDICADORES = [
    "TAG proyecto", "Nombre del proyecto", "Rentabilidad sobre costo",
    "Margen neto %", "Productividad Materiales", "Productividad Equipos",
    "Productividad MO", "Productividad Otros", "Costo Materiales % de venta",
    "Costo Equipos % de venta", "Costo MO % de venta", "Costo Otros % de venta",
    "Desviación % Materiales", "Desviación % Equipos", "Desviación % MO",
    "Desviación % Otros",
]


def asegurar_estructura_workbook(ruta_excel: Path) -> openpyxl.Workbook:
    """Abre ruta_excel si existe, o crea un libro nuevo. Garantiza que las 3
    hojas existan con encabezados en la fila 1 -- si una hoja ya existe, no
    la toca (regla de oro: no reescribir datos ya presentes). Elimina hojas
    default vacías ("Hoja1"/"Sheet") si quedaron de un libro recién creado."""
    if ruta_excel.exists():
        wb = openpyxl.load_workbook(ruta_excel)
    else:
        wb = openpyxl.Workbook()

    for nombre_hoja, headers in (
        (HOJA_PROYECTOS, HEADERS_PROYECTOS),
        (HOJA_DETALLE_COSTOS_REALES, HEADERS_DETALLE_COSTOS_REALES),
        (HOJA_INDICADORES, HEADERS_INDICADORES),
    ):
        if nombre_hoja not in wb.sheetnames:
            ws = wb.create_sheet(nombre_hoja)
            for col, encabezado in enumerate(headers, start=1):
                ws.cell(row=1, column=col, value=encabezado)

    for nombre_default in ("Hoja1", "Sheet"):
        if nombre_default in wb.sheetnames:
            ws_default = wb[nombre_default]
            esta_vacia = all(
                celda.value is None
                for fila in ws_default.iter_rows()
                for celda in fila
            )
            if esta_vacia:
                del wb[nombre_default]

    return wb


# ── MAPEO DE CATEGORÍAS ──────────────────────────────────────────────────────

MAPEO_CATEGORIA_BUCKET = {
    "Materiales": "Materiales",
    "Consumibles": "Materiales",
    "Equipos-Herramientas": "Equipos",
}


def mapear_categoria_a_bucket(categoria_item: str | None) -> tuple[str, bool]:
    """Devuelve (bucket, es_mapeo_explicito). Cualquier categoria_item que no
    esté en MAPEO_CATEGORIA_BUCKET (incluyendo None) cae en "Otros" con
    es_mapeo_explicito=False, para poder avisar sin perder el monto."""
    if categoria_item in MAPEO_CATEGORIA_BUCKET:
        return MAPEO_CATEGORIA_BUCKET[categoria_item], True
    return "Otros", False


# ── LECTURA DE CENTRO DE COSTOS (SOLO LECTURA) ───────────────────────────────

def prefijo_de_n_ref(n_ref: str) -> str:
    """'UMAG-001' -> 'UMAG'. Mismo prefijo que PREFIJOS_PROYECTO en
    Centro de Costos/Sistema/auditor_centro_costos.py."""
    return n_ref.split("-")[0]


def leer_detalle_centro_costos(ruta_excel_cc: Path) -> list[dict]:
    """Lee la hoja 'Detalle' de Centro de Costos.xlsx -- SOLO LECTURA, este
    módulo nunca escribe ese archivo. Filas sin N° Ref. o sin Total sin IVA
    se ignoran (no se puede agrupar ni sumar sin esos dos datos)."""
    wb = openpyxl.load_workbook(ruta_excel_cc, data_only=True)
    ws = wb["Detalle"]
    encabezados = [celda.value for celda in ws[1]]
    col_n_ref = encabezados.index("N° Ref.") + 1
    col_categoria = encabezados.index("Categoría Ítem") + 1
    col_total_sin_iva = encabezados.index("Total sin IVA (CLP)") + 1

    items = []
    for fila in ws.iter_rows(min_row=2):
        n_ref = fila[col_n_ref - 1].value
        total = fila[col_total_sin_iva - 1].value
        if n_ref is None or total is None:
            continue
        categoria = fila[col_categoria - 1].value
        items.append({"n_ref": n_ref, "categoria_item": categoria, "total_sin_iva": float(total)})
    return items


def agrupar_por_proyecto_y_subcategoria(items_detalle: list[dict]) -> dict[tuple[str, str], float]:
    """Suma total_sin_iva agrupado por (prefijo de proyecto, categoria_item
    original -- sin colapsar a bucket todavía, eso lo hace la hoja 'Detalle
    Costos Reales' al escribir, para no perder la subcategoría real)."""
    agrupado: dict[tuple[str, str], float] = {}
    for item in items_detalle:
        prefijo = prefijo_de_n_ref(item["n_ref"])
        clave = (prefijo, item["categoria_item"])
        agrupado[clave] = agrupado.get(clave, 0.0) + item["total_sin_iva"]
    return agrupado


# ── LECTURA DE LA HOJA "PROYECTOS" ───────────────────────────────────────────

def leer_filas_proyectos(ws_proyectos) -> tuple[list[dict], list[str]]:
    """Recorre la hoja 'Proyectos' desde la fila 2. Filas sin TAG o sin
    Nombre se saltan con aviso. TAG duplicado: se queda con la primera
    fila, avisa de las siguientes."""
    filas_validas = []
    avisos = []
    tags_vistos = set()

    for fila_idx in range(2, ws_proyectos.max_row + 1):
        tag = ws_proyectos.cell(row=fila_idx, column=1).value
        nombre = ws_proyectos.cell(row=fila_idx, column=2).value

        if not tag or not nombre:
            if tag or nombre:
                avisos.append(f"Fila {fila_idx}: falta TAG o Nombre, se salta.")
            continue

        if tag in tags_vistos:
            avisos.append(f"Fila {fila_idx}: TAG '{tag}' duplicado, se usa la primera fila.")
            continue

        tags_vistos.add(tag)
        filas_validas.append({"fila": fila_idx, "tag": tag, "nombre": nombre})

    return filas_validas, avisos


# ── CARPETAS DE PROYECTO ─────────────────────────────────────────────────────

def asegurar_carpeta_proyecto(nombre_proyecto: str, raiz_facturas: Path) -> bool:
    """Crea raiz_facturas/<nombre_proyecto>/ si no existe. Devuelve True si
    la creó, False si ya existía. raiz_facturas debe ser la fuente REAL que
    lee Centro de Costos hoy (Sitio de comunicación - Centro de Costos 1/
    Facturas y Boletas/), nunca la carpeta legado."""
    carpeta = raiz_facturas / nombre_proyecto
    ya_existia = carpeta.exists()
    carpeta.mkdir(parents=True, exist_ok=True)
    return not ya_existia


def asegurar_carpetas_proyectos(filas_validas: list[dict], raiz_facturas: Path) -> list[str]:
    """Aplica asegurar_carpeta_proyecto a cada fila válida. Devuelve los
    nombres de las carpetas que se crearon (para el informe de consola)."""
    creadas = []
    for fila_info in filas_validas:
        if asegurar_carpeta_proyecto(fila_info["nombre"], raiz_facturas):
            creadas.append(fila_info["nombre"])
    return creadas


# ── BACKUP ────────────────────────────────────────────────────────────────

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre",
    12: "Diciembre",
}


def hacer_backup(ruta_excel: Path, raiz_respaldos: Path) -> Path | None:
    """Copia ruta_excel a raiz_respaldos/<Mes Año>/Análisis de Proyectos -
    backup <fecha> <hora>.xlsx antes de escribir -- mismo patrón que
    Centro de Costos. Devuelve None si ruta_excel todavía no existe (nada
    que respaldar)."""
    if not ruta_excel.exists():
        return None
    ahora = datetime.now()
    carpeta_mes = raiz_respaldos / f"{MESES_ES[ahora.month]} {ahora.year}"
    carpeta_mes.mkdir(parents=True, exist_ok=True)
    marca_tiempo = ahora.strftime("%Y-%m-%d %H%M%S")
    destino = carpeta_mes / f"Análisis de Proyectos - backup {marca_tiempo}.xlsx"
    shutil.copy2(ruta_excel, destino)
    return destino


# ── HOJA "DETALLE COSTOS REALES" (100% regenerada cada corrida) ─────────────

def regenerar_hoja_detalle_costos_reales(wb, agrupado: dict[tuple[str, str], float]) -> list[str]:
    """Borra todas las filas de datos (fila 2 en adelante) y las reescribe
    completas desde 'agrupado' -- mismo patrón que las hojas de proyecto de
    Centro de Costos: se recalcula entera, nunca se acumula a mano. Devuelve
    avisos de subcategorías sin mapeo explícito (caen en 'Otros')."""
    ws = wb[HOJA_DETALLE_COSTOS_REALES]
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)

    avisos = []
    fila = 2
    for (tag, subcategoria), total in sorted(agrupado.items()):
        bucket, es_explicito = mapear_categoria_a_bucket(subcategoria)
        if not es_explicito:
            avisos.append(
                f"Categoría '{subcategoria}' (proyecto {tag}) sin mapeo explícito, va a 'Otros'."
            )
        ws.cell(row=fila, column=1, value=tag)
        ws.cell(row=fila, column=2, value=subcategoria)
        ws.cell(row=fila, column=3, value=bucket)
        ws.cell(row=fila, column=4, value=total)
        fila += 1

    return avisos


# ── FÓRMULAS DE LA HOJA "PROYECTOS" ──────────────────────────────────────────

def asegurar_formulas_proyectos(ws_proyectos, filas_validas: list[dict]) -> None:
    """Escribe las columnas derivadas (K/L/M = SUMIFS hacia 'Detalle Costos
    Reales'; O/P/Q/R/S = totales/márgenes/desviación) para cada fila válida.
    Nunca toca las columnas manuales (A-J, N)."""
    for fila_info in filas_validas:
        r = fila_info["fila"]
        tag_ref = f"$A{r}"

        for columna, bucket in ((11, "Materiales"), (12, "Equipos"), (13, "Otros")):
            ws_proyectos.cell(row=r, column=columna, value=(
                f"=SUMIFS('{HOJA_DETALLE_COSTOS_REALES}'!$D:$D,"
                f"'{HOJA_DETALLE_COSTOS_REALES}'!$A:$A,{tag_ref},"
                f"'{HOJA_DETALLE_COSTOS_REALES}'!$C:$C,\"{bucket}\")"
            ))

        ws_proyectos.cell(row=r, column=15, value=f"=G{r}+H{r}+I{r}+J{r}")
        ws_proyectos.cell(row=r, column=16, value=f"=K{r}+L{r}+M{r}+N{r}")
        ws_proyectos.cell(row=r, column=17, value=f"=F{r}-O{r}")
        ws_proyectos.cell(row=r, column=18, value=f"=F{r}-P{r}")
        ws_proyectos.cell(row=r, column=19, value=f"=P{r}/O{r}-1")


# ── FÓRMULAS DE LA HOJA "INDICADORES" (100% regenerada cada corrida) ────────

def asegurar_hoja_indicadores(wb, filas_validas: list[dict]) -> None:
    """Regenera 'Indicadores' completa: una fila compacta por proyecto
    válido (sin huecos), pero cada fórmula referencia la fila REAL del
    proyecto en 'Proyectos' (que sí puede tener huecos)."""
    ws = wb[HOJA_INDICADORES]
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)

    fila_destino = 2
    for fila_info in filas_validas:
        r = fila_info["fila"]
        ws.cell(row=fila_destino, column=1, value=f"=Proyectos!A{r}")
        ws.cell(row=fila_destino, column=2, value=f"=Proyectos!B{r}")
        ws.cell(row=fila_destino, column=3, value=f"=Proyectos!R{r}/Proyectos!P{r}")
        ws.cell(row=fila_destino, column=4, value=f"=Proyectos!R{r}/Proyectos!F{r}")
        ws.cell(row=fila_destino, column=5, value=f"=Proyectos!F{r}/Proyectos!K{r}")
        ws.cell(row=fila_destino, column=6, value=f"=Proyectos!F{r}/Proyectos!L{r}")
        ws.cell(row=fila_destino, column=7, value=f"=Proyectos!F{r}/Proyectos!N{r}")
        ws.cell(row=fila_destino, column=8, value=f"=Proyectos!F{r}/Proyectos!M{r}")
        ws.cell(row=fila_destino, column=9, value=f"=Proyectos!K{r}/Proyectos!F{r}")
        ws.cell(row=fila_destino, column=10, value=f"=Proyectos!L{r}/Proyectos!F{r}")
        ws.cell(row=fila_destino, column=11, value=f"=Proyectos!N{r}/Proyectos!F{r}")
        ws.cell(row=fila_destino, column=12, value=f"=Proyectos!M{r}/Proyectos!F{r}")
        ws.cell(row=fila_destino, column=13, value=f"=Proyectos!K{r}/Proyectos!G{r}-1")
        ws.cell(row=fila_destino, column=14, value=f"=Proyectos!L{r}/Proyectos!H{r}-1")
        ws.cell(row=fila_destino, column=15, value=f"=Proyectos!N{r}/Proyectos!I{r}-1")
        ws.cell(row=fila_destino, column=16, value=f"=Proyectos!M{r}/Proyectos!J{r}-1")
        fila_destino += 1


# ── ORQUESTADOR ───────────────────────────────────────────────────────────

def ejecutar(
    ruta_excel_af: Path = RUTA_EXCEL,
    ruta_excel_cc: Path = RUTA_EXCEL_CENTRO_COSTOS,
    raiz_facturas_cc: Path = RAIZ_FACTURAS_CENTRO_COSTOS,
    raiz_respaldos: Path = RAIZ_RESPALDOS,
    dry_run: bool = False,
) -> dict:
    """Orquesta todo el flujo. Con dry_run=True no escribe nada -- ni backup,
    ni carpetas, ni el Excel -- solo reporta qué pasaría (usado por el
    comando 'status' del skill). Captura PermissionError/OSError de operaciones
    de archivo (backup, carpetas, save); excepciones de lectura de datos
    propagarán hacia afuera."""
    resumen = {"avisos": [], "carpetas_creadas": [], "categorias_no_mapeadas": [], "error": None}

    wb = asegurar_estructura_workbook(ruta_excel_af)
    ws_proyectos = wb[HOJA_PROYECTOS]
    filas_validas, avisos_lectura = leer_filas_proyectos(ws_proyectos)
    resumen["avisos"].extend(avisos_lectura)

    if not ruta_excel_cc.exists():
        resumen["avisos"].append(
            f"No se encontró {ruta_excel_cc}, no se actualizan costos reales."
        )
        return resumen

    items_detalle = leer_detalle_centro_costos(ruta_excel_cc)
    agrupado = agrupar_por_proyecto_y_subcategoria(items_detalle)

    if dry_run:
        for fila_info in filas_validas:
            if not (raiz_facturas_cc / fila_info["nombre"]).exists():
                resumen["carpetas_creadas"].append(fila_info["nombre"])
        categorias_no_mapeadas = set()
        for _, subcategoria in agrupado:
            _, es_explicito = mapear_categoria_a_bucket(subcategoria)
            if not es_explicito:
                categorias_no_mapeadas.add(subcategoria)
        resumen["categorias_no_mapeadas"] = sorted(categorias_no_mapeadas)
        return resumen

    try:
        hacer_backup(ruta_excel_af, raiz_respaldos)
    except PermissionError as exc:
        resumen["avisos"].append(f"No se pudo respaldar (¿archivo abierto?): {exc}")

    try:
        resumen["carpetas_creadas"] = asegurar_carpetas_proyectos(filas_validas, raiz_facturas_cc)
    except OSError as exc:
        resumen["avisos"].append(f"No se pudieron crear una o más carpetas de proyecto: {exc}")

    avisos_detalle = regenerar_hoja_detalle_costos_reales(wb, agrupado)
    resumen["avisos"].extend(avisos_detalle)
    categorias_no_mapeadas = set()
    for _, subcategoria in agrupado:
        _, es_explicito = mapear_categoria_a_bucket(subcategoria)
        if not es_explicito:
            categorias_no_mapeadas.add(subcategoria)
    resumen["categorias_no_mapeadas"] = sorted(categorias_no_mapeadas)

    asegurar_formulas_proyectos(ws_proyectos, filas_validas)
    asegurar_hoja_indicadores(wb, filas_validas)

    try:
        wb.save(ruta_excel_af)
    except PermissionError as exc:
        resumen["error"] = f"No se pudo guardar {ruta_excel_af} (¿archivo abierto?): {exc}"

    return resumen


def main() -> None:
    resumen = ejecutar()
    print("=== Análisis Financiero ===")
    if resumen["carpetas_creadas"]:
        print(f"Carpetas de proyecto creadas: {', '.join(resumen['carpetas_creadas'])}")
    if resumen["categorias_no_mapeadas"]:
        print(
            "Categorías sin mapeo explícito (van a 'Otros'): "
            + ", ".join(resumen["categorias_no_mapeadas"])
        )
    for aviso in resumen["avisos"]:
        print(f"[AVISO] {aviso}")
    if resumen["error"]:
        print(f"[ERROR] {resumen['error']}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
