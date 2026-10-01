# -*- coding: utf-8 -*-
"""
driver.py -- Comandos del skill Reportes_Analisis_Financiero.

  status   solo lectura: que reportes quedaron pendientes/desactualizados.
  contexto <clave>   los numeros de una entidad, ya formateados y comparados
           contra la cartera, para redactar el analisis de la pagina 2.
  generar  arma el PDF completo (pagina 1 deterministica + el analisis que
           escribio el agente), lo renderiza y actualiza el manifiesto.
  run      igual que status, mas el recordatorio del flujo.

La pagina 1 la arma Reportes/panel.py, no el agente: no tiene decisiones
editoriales (el estandar pide todos los KPIs de la entidad) y escribirla a
mano una vez por reporte era el grueso del costo de este skill.
"""

import json
import sys
from datetime import date
from pathlib import Path

RAIZ_SKILL = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ_SKILL.parent.parent.parent
RAIZ_REPORTES = RAIZ_MODULO / "Reportes"
RAIZ_SISTEMA = RAIZ_MODULO / "Sistema"
for raiz in (RAIZ_REPORTES, RAIZ_SISTEMA):
    if str(raiz) not in sys.path:
        sys.path.insert(0, str(raiz))

import datos_reportes as dr  # noqa: E402
import estado_reportes as er  # noqa: E402
import motor_reportes  # noqa: E402
import panel  # noqa: E402
from analisis_financiero import (  # noqa: E402
    CATEGORIAS_KPI, HOJA_PROYECTOS, NOMBRE_LEGIBLE_CATEGORIA, RAIZ_DATOS, RUTA_EXCEL,
)
from brand import formatear_kpi, formatear_moneda, formatear_porcentaje  # noqa: E402
from graficos import formatear_valor  # noqa: E402

import openpyxl  # noqa: E402

RUTA_ESTADO_REPORTES = RAIZ_REPORTES / "estado_reportes.json"
RAIZ_SALIDA = RAIZ_DATOS / "Reportes"
CARPETA_POR_TIPO = {
    "proyecto": "Proyectos", "cliente": "Clientes", "categoria": "Categorías",
}


def listar_entidades(ruta_excel: Path = RUTA_EXCEL, wb=None) -> dict[str, tuple[str, str]]:
    """Recorre 'Proyectos' y arma la clave->tipo/identificador de cada
    proyecto, cliente unico, y categoria unica presentes hoy. Excluye por
    completo los proyectos sin datos manuales completos (spec §6) -- ni
    generan su propia entrada 'proyecto:TAG', ni aportan a 'cliente:'/
    'categoria:' salvo que OTRO proyecto completo ya la haya registrado."""
    wb = wb if wb is not None else openpyxl.load_workbook(ruta_excel, data_only=True)
    ws = wb[HOJA_PROYECTOS]
    mapa = {celda.value: idx + 1 for idx, celda in enumerate(ws[1]) if celda.value}
    col_tag = mapa.get("TAG proyecto")

    entidades: dict[str, tuple[str, str]] = {}
    clientes_vistos = set()
    categorias_vistas = set()
    for fila_idx in range(2, ws.max_row + 1):
        tag = ws.cell(row=fila_idx, column=col_tag).value if col_tag else None
        if not tag:
            continue
        fila = {h: ws.cell(row=fila_idx, column=c).value for h, c in mapa.items()}
        if not dr.proyecto_tiene_datos_completos(fila):
            continue

        entidades[f"proyecto:{tag}"] = ("proyecto", tag)

        cliente = fila.get("Cliente")
        if cliente and cliente not in clientes_vistos:
            clientes_vistos.add(cliente)
            entidades[f"cliente:{cliente}"] = ("cliente", cliente)

        categoria = fila.get("Categoría")
        if categoria and categoria not in categorias_vistas:
            categorias_vistas.add(categoria)
            entidades[f"categoria:{categoria}"] = ("categoria", categoria)

    return entidades


_FUNCIONES_POR_TIPO = {
    "proyecto": dr.paquete_datos_proyecto,
    "cliente": dr.paquete_datos_cliente,
    "categoria": dr.paquete_datos_categoria,
}


def paquetes_de(claves, ruta_excel: Path = RUTA_EXCEL, wb=None) -> dict[str, dict]:
    """Paquete de datos de cada clave, abriendo el libro UNA sola vez para
    todas (antes se abria uno por entidad: 20 aperturas por corrida)."""
    wb = wb if wb is not None else dr.abrir_libro(ruta_excel)
    entidades = listar_entidades(ruta_excel, wb)
    paquetes = {}
    for clave in claves:
        if clave not in entidades:
            raise ValueError(
                f"Entidad desconocida: '{clave}'. Las claves validas salen de "
                f"`status` (formato 'proyecto:TAG' / 'cliente:Nombre' / "
                f"'categoria:Nombre')."
            )
        tipo, identificador = entidades[clave]
        paquetes[clave] = _FUNCIONES_POR_TIPO[tipo](ruta_excel, identificador, wb)
    return paquetes


def calcular_reportes_pendientes(
    ruta_excel: Path = RUTA_EXCEL, ruta_estado: Path = RUTA_ESTADO_REPORTES,
) -> list[str]:
    """Claves de entidades cuyo reporte PDF no existe o quedo desactualizado."""
    wb = dr.abrir_libro(ruta_excel)
    entidades = listar_entidades(ruta_excel, wb)
    paquetes_actuales = paquetes_de(entidades, ruta_excel, wb)
    estado = er.cargar_estado(ruta_estado)
    return er.detectar_desactualizados(paquetes_actuales, estado)


def ruta_pdf(clave: str, paquete: dict) -> Path:
    """Donde vive el PDF de una entidad. El nombre de archivo es el
    identificador (lo que ya usan los reportes existentes: Proyectos/UMAG.pdf,
    Clientes/Universidad de Magallanes.pdf)."""
    identificador = clave.split(":", 1)[1]
    seguro = identificador.replace("/", "-").replace("\\", "-").strip()
    return RAIZ_SALIDA / CARPETA_POR_TIPO[paquete["tipo"]] / f"{seguro}.pdf"


# ── CONTEXTO PARA REDACTAR LA PAGINA 2 ──────────────────────────────────────
# Todo lo que hace falta para escribir el analisis, ya calculado y formateado.
# Antes el agente volcaba los dicts crudos del paquete (~60 lineas de floats)
# y escribia Python suelto para compararlos contra la cartera; esto es la
# misma informacion en ~25 lineas legibles.

def _linea_categorias(fuente: dict, sesgo: list[dict]) -> list[str]:
    sesgo_por_nombre = {s["categoria"]: s["sesgo"] for s in sesgo}
    lineas = ["Por categoria de gasto (proyectado -> real, desviacion, sesgo de la cartera):"]
    for sufijo, col_p, col_r in CATEGORIAS_KPI:
        nombre = NOMBRE_LEGIBLE_CATEGORIA[sufijo]
        proyectado, real = fuente.get(col_p) or 0.0, fuente.get(col_r) or 0.0
        desviacion = (real / proyectado - 1) if proyectado else None
        referencia = sesgo_por_nombre.get(nombre)
        pct = lambda v: "—" if v is None else formatear_porcentaje(v, signo=True)  # noqa: E731
        lineas.append(
            f"  {nombre:<12} {formatear_moneda(proyectado):>14} -> {formatear_moneda(real):>14}"
            f"  {pct(desviacion):>8}   cartera {pct(referencia)}"
        )
    return lineas


def _lineas_cartera(contexto: dict) -> list[str]:
    concentracion = contexto.get("concentracion") or {}
    return [
        f"Cartera: {contexto.get('n_proyectos_completos')} proyectos completos, "
        f"venta total {formatear_moneda(contexto.get('venta_total') or 0)}; "
        f"mediana de margen al cierre "
        f"{formatear_porcentaje(contexto['margen_mediano']) if contexto.get('margen_mediano') is not None else '—'}, "
        f"mediana de Nota "
        f"{formatear_valor(contexto['nota_mediana'], 1) if contexto.get('nota_mediana') is not None else '—'}",
        f"Concentracion: mayor cliente "
        f"{formatear_porcentaje(concentracion['top_1']) if concentracion.get('top_1') is not None else '—'}, "
        f"top 3 {formatear_porcentaje(concentracion['top_3']) if concentracion.get('top_3') is not None else '—'}, "
        f"{concentracion.get('n_clientes')} clientes "
        f"({formatear_valor(concentracion['clientes_equivalentes'], 1)} equivalentes)"
        if concentracion.get("clientes_equivalentes") is not None else "Concentracion: sin venta cargada",
    ]


def _brief_proyecto(paquete: dict) -> list[str]:
    p, ind = paquete["proyecto"], paquete["indicadores"]
    contexto = paquete["_contexto"]
    peso = (contexto.get("peso_cartera") or {}).get(paquete["tag"])
    lineas = [
        f"{p.get('Nombre del proyecto')} (TAG {paquete['tag']}) | Cliente: {p.get('Cliente')} "
        f"| Categoria: {p.get('Categoría')}",
        f"Estado: {'EN DESARROLLO' if paquete['en_desarrollo'] else 'CERRADO'} "
        f"| Avance {formatear_kpi('% Avance', p.get('% Avance'))} "
        f"| Inicio {panel.fecha_legible(p.get('Fecha de inicio')) or '—'} "
        f"| Cierre {panel.fecha_legible(p.get('Fecha de cierre')) or 'sin fecha'}",
        f"Venta {formatear_moneda(p.get('Monto de Venta (sin IVA)') or 0)}"
        + (f" ({formatear_porcentaje(peso)} de la venta de la cartera)" if peso is not None else ""),
        f"Presupuesto {formatear_moneda(p.get('Total Proyectado') or 0)} -> "
        f"real a la fecha {formatear_moneda(p.get('Total Real') or 0)} -> "
        f"estimado al cierre {formatear_kpi('Costo estimado al cierre', ind.get('Costo estimado al cierre'))}",
        f"Margen al cierre {formatear_kpi('Margen estimado al cierre', ind.get('Margen estimado al cierre'))} "
        f"({formatear_kpi('Margen estimado al cierre %', ind.get('Margen estimado al cierre %'))}) "
        f"| a la fecha {formatear_kpi('Margen neto %', ind.get('Margen neto %'))} "
        f"| escenario indice {formatear_kpi('Margen al cierre % (escenario índice de costo)', ind.get('Margen al cierre % (escenario índice de costo)'))}",
        f"Nota {formatear_kpi('Nota del Proyecto', ind.get('Nota del Proyecto'))} "
        f"({ind.get('Evaluación')}) | Desviacion estimada al cierre "
        f"{formatear_kpi('Desviación estimada al cierre %', ind.get('Desviación estimada al cierre %'))} "
        f"| Error del presupuesto {formatear_kpi('Error del presupuesto %', ind.get('Error del presupuesto %'))}",
    ]
    lineas += _linea_categorias(p, contexto.get("sesgo_por_categoria") or [])
    alertas = paquete.get("alertas") or []
    lineas.append(f"Alertas ({len(alertas)}):" if alertas else "Alertas: ninguna")
    lineas += [f"  - {a}" for a in alertas]
    lineas += _lineas_cartera(contexto)
    return lineas


def _brief_agregado(paquete: dict, titulo: str) -> list[str]:
    proyectos = paquete["proyectos"]
    contexto = paquete["_contexto"]
    venta = sum(p.get("Monto de Venta (sin IVA)") or 0.0 for p in proyectos)
    margen = sum(p.get("Margen estimado al cierre") or 0.0 for p in proyectos)
    lineas = [titulo]
    if paquete["tipo"] == "cliente":
        kpis = paquete["kpis_cliente"]
        lineas.append(
            f"Recurrente: {kpis.get('Cliente recurrente')} | Clasificacion: "
            f"{kpis.get('Clasificación')} | Proyectos completos: {kpis.get('N° de proyectos')}"
        )
    lineas.append(
        f"Venta acumulada {formatear_moneda(venta)} | Margen al cierre "
        f"{formatear_moneda(margen)} ({formatear_porcentaje(margen / venta) if venta else '—'} ponderado)"
    )
    lineas.append("Proyectos (venta / margen al cierre / margen % / Nota / avance):")
    for p in sorted(proyectos, key=lambda x: -(x.get("Monto de Venta (sin IVA)") or 0)):
        lineas.append(
            f"  {p.get('TAG proyecto'):<6} {str(p.get('Nombre del proyecto'))[:28]:<28} "
            f"{formatear_moneda(p.get('Monto de Venta (sin IVA)') or 0):>13} "
            f"{formatear_kpi('Margen estimado al cierre', p.get('Margen estimado al cierre')):>13} "
            f"{formatear_kpi('Margen estimado al cierre %', p.get('Margen estimado al cierre %')):>8} "
            f"{formatear_kpi('Nota del Proyecto', p.get('Nota del Proyecto')):>7} "
            f"{formatear_kpi('% Avance', p.get('% Avance')):>7}"
        )
    lineas += _linea_categorias(
        panel.agregar_costos(proyectos), contexto.get("sesgo_por_categoria") or [],
    )
    lineas += _lineas_cartera(contexto)
    return lineas


def brief(clave: str, paquete: dict) -> str:
    if paquete["tipo"] == "proyecto":
        lineas = _brief_proyecto(paquete)
    elif paquete["tipo"] == "cliente":
        lineas = _brief_agregado(paquete, f"Cliente {paquete['cliente']}")
    else:
        lineas = _brief_agregado(paquete, f"Categoria {paquete['categoria']}")
    return "\n".join([f"=== {clave} -- contexto para la pagina 2 ==="] + lineas)


# ── COMANDOS ────────────────────────────────────────────────────────────────

def status() -> None:
    pendientes = calcular_reportes_pendientes()
    print("=== Reportes Analisis Financiero -- status ===")
    if not pendientes:
        print("Todos los reportes estan al dia.")
        return
    print(f"{len(pendientes)} reporte(s) pendiente(s)/desactualizado(s):")
    for clave in pendientes:
        print(f"  - {clave}")


def run() -> None:
    pendientes = calcular_reportes_pendientes()
    print("=== Reportes Analisis Financiero -- run ===")
    if not pendientes:
        print("Todos los reportes estan al dia. Nada que generar.")
        return
    print(
        f"{len(pendientes)} reporte(s) pendiente(s). Este comando NO los genera solo:\n"
        f"  1. driver.py contexto <clave>          -> los numeros de la entidad\n"
        f"  2. el agente escribe SOLO el analisis (pagina 2) en un .html suelto\n"
        f"  3. driver.py generar <clave> --narrativa <ese .html>\n"
        f"     (o driver.py generar --lote lote.json para varios de una)\n"
        f"La pagina 1 la arma panel.py: no se escribe a mano."
    )
    for clave in pendientes:
        print(f"  - {clave}")


def contexto(claves: list[str]) -> None:
    paquetes = paquetes_de(claves)
    print("\n\n".join(brief(clave, paquetes[clave]) for clave in claves))


def generar(pares: list[tuple[str, Path]], ruta_estado: Path = RUTA_ESTADO_REPORTES) -> list[Path]:
    """pares: (clave de entidad, ruta del .html con el analisis de pagina 2).
    Arma el documento completo, renderiza todos los PDFs con un solo Chromium
    y actualiza el manifiesto. Devuelve las rutas escritas."""
    from pypdf import PdfReader

    generado_el = date.today().strftime("%d-%m-%Y")
    paquetes = paquetes_de([clave for clave, _ in pares])

    documentos, destinos = [], []
    for clave, ruta_narrativa in pares:
        narrativa = Path(ruta_narrativa).read_text(encoding="utf-8")
        paquete = paquetes[clave]
        destino = ruta_pdf(clave, paquete)
        documentos.append((panel.documento(paquete, narrativa, generado_el), destino))
        destinos.append(destino)

    motor_reportes.renderizar_pdfs(documentos)

    estado = er.cargar_estado(ruta_estado)
    for (clave, _), destino in zip(pares, destinos):
        paginas = len(PdfReader(str(destino)).pages)
        aviso = "" if paginas == 2 else f"  <-- OJO: {paginas} paginas (el estandar son 2)"
        print(f"  {clave} -> {destino}{aviso}")
        estado = er.marcar_generado(estado, clave, paquetes[clave], generado_el)
    er.guardar_estado(ruta_estado, estado)
    print(f"{len(destinos)} reporte(s) generado(s) y marcado(s) al dia en el manifiesto.")
    return destinos


def _parsear_generar(argumentos: list[str]) -> list[tuple[str, Path]]:
    if argumentos[:1] == ["--lote"]:
        lote = json.loads(Path(argumentos[1]).read_text(encoding="utf-8"))
        return [(clave, Path(ruta)) for clave, ruta in lote.items()]
    if len(argumentos) != 3 or argumentos[1] != "--narrativa":
        raise SystemExit(
            'Uso: generar "<clave>" --narrativa <archivo.html>\n'
            "     generar --lote <archivo.json>   ({\"clave\": \"archivo.html\", ...})"
        )
    return [(argumentos[0], Path(argumentos[2]))]


if __name__ == "__main__":
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    comando = _sys.argv[1] if len(_sys.argv) > 1 else "status"
    argumentos = _sys.argv[2:]
    if comando == "contexto":
        if not argumentos:
            raise SystemExit('Uso: contexto "proyecto:UMAG" ["cliente:Nombre" ...]')
        contexto(argumentos)
    elif comando == "generar":
        generar(_parsear_generar(argumentos))
    else:
        {"status": status, "run": run}.get(comando, status)()
