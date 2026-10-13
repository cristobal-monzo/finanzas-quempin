# -*- coding: utf-8 -*-
"""
bandeja.py -- todo lo que espera a una persona, en un solo lugar (2026-10-13).

Por que existe: lo pendiente estaba repartido en ocho lugares -- sugerencias
para la Planilla, envios que esperan en el buzon de cada herramienta,
borradores para Sistema QUEMPIN, el procesador detenido, avisos del
procesador, proyectos y cotizaciones sin N° de requerimiento, reportes PDF
desactualizados, presupuestos del Formulador sin revisar y hallazgos del
Centro de Costos. Cada uno se veia solo si alguien iba a buscarlo. La bandeja
los junta en 'status' y 'run' de /Actualizar_Finanzas (decision del
2026-10-13: dentro del orquestador, no como un skill mas).

Solo lee. Las fuentes son lo que el procesador ya publica en la carpeta de
intercambio (estado.json, analisis-financiero.json,
documentos-comerciales.json) mas las salidas de los otros pasos del
orquestador, que llegan ya contadas en `extras`.

Uso desde codigo:  pendientes(raiz_intercambio, extras) -> [Pendiente]
                   imprimir(pendientes)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

# Mismo horario y umbral que pulso.js (el aviso del Formulador y del AF): un
# procesador detenido es el que pasa mas de 4 horas habiles sin correr.
HORARIO = {"dias": (0, 1, 2, 3, 4), "desde": 8.5, "hasta": 19}   # lunes=0 en Python
DETENIDO_HORAS_HABILES = 4

# Que hacer con lo que espera en el buzon de cada herramienta.
ACCION_BUZON = {
    "planilla-requerimientos": ("sugerencia(s) para la Planilla de Ingreso",
                                "revisarlas con /Sugerencias_Requerimientos"),
    "sistema-quempin": ("envio(s) para Sistema QUEMPIN (borradores de cotizacion o registros)",
                        "abrir Sistema QUEMPIN: los toma al iniciar"),
    "analisis-financiero": ("envio(s) al Analisis Financiero",
                            "se aplican en el run del AF; los que piden decision: "
                            "'Registro_Analisis_Financiero/driver.py intercambio'"),
}


@dataclass
class Pendiente:
    nivel: str      # 'alto' (algo detenido o fallando) | 'medio' (espera a una persona)
    texto: str
    accion: str = ""


def minutos_habiles(desde: datetime, hasta: datetime, horario=HORARIO) -> int:
    """Minutos de horario habil entre dos fechas locales (como pulso.js)."""
    if hasta <= desde:
        return 0
    total = 0.0
    dia = datetime(desde.year, desde.month, desde.day)
    while dia <= hasta:
        if dia.weekday() in horario["dias"]:
            ini = dia + timedelta(minutes=round(horario["desde"] * 60))
            fin = dia + timedelta(minutes=round(horario["hasta"] * 60))
            a, b = max(ini, desde), min(fin, hasta)
            if b > a:
                total += (b - a).total_seconds() / 60
        dia += timedelta(days=1)
    return round(total)


def _leer_datos(raiz: Path, nombre: str):
    try:
        sobre = json.loads((Path(raiz) / "publicado" / f"{nombre}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return sobre.get("datos") if isinstance(sobre, dict) else None


def _fecha_local(texto) -> datetime | None:
    try:
        f = datetime.fromisoformat(str(texto))
    except ValueError:
        return None
    return f.astimezone().replace(tzinfo=None) if f.tzinfo else f


def desde_estado(estado: dict | None, ahora: datetime) -> list[Pendiente]:
    """Procesador (detenido o con pasos fallando), sus avisos y el buzon."""
    if not estado:
        return [Pendiente("alto", "No se pudo leer estado.json de la carpeta de intercambio.",
                          "revisar que la biblioteca «Formulación de proyectos» este sincronizada")]
    salida = []
    proc = estado.get("procesador") or {}
    ultima = _fecha_local(proc.get("ultimaCorrida"))
    if ultima is None:
        salida.append(Pendiente("alto", "El procesador del intercambio nunca registro una corrida.",
                                "revisar la tarea «Procesar intercambio QUEMPIN»"))
    else:
        habiles = minutos_habiles(ultima, ahora)
        if habiles > DETENIDO_HORAS_HABILES * 60:
            salida.append(Pendiente(
                "alto", f"El procesador del intercambio no corre desde el {ultima:%d-%m %H:%M} "
                        f"({habiles // 60} h habiles).",
                "revisar la tarea programada «Procesar intercambio QUEMPIN» (que este habilitada)"))
    fallas = [n for n, p in (proc.get("pasos") or {}).items() if isinstance(p, dict) and p.get("ok") is False]
    if fallas:
        salida.append(Pendiente("alto", f"Pasos del procesador con error en su ultima corrida: {', '.join(fallas)}.",
                                "ver logs/procesador_<mes>.log"))
    for aviso in estado.get("avisos") or []:
        salida.append(Pendiente("alto", f"Aviso del procesador: {aviso}"))
    for destino, info in sorted((estado.get("buzon") or {}).items()):
        n = int((info or {}).get("pendientes") or 0)
        if not n:
            continue
        que, accion = ACCION_BUZON.get(destino, (f"mensaje(s) para {destino}", ""))
        antiguo = _fecha_local((info or {}).get("masAntiguo"))
        desde = f", el mas antiguo del {antiguo:%d-%m}" if antiguo else ""
        salida.append(Pendiente("medio", f"{n} {que} esperan{desde}.", accion))
    return salida


def sin_requerimiento(af: dict | None, documentos: dict | None) -> list[Pendiente]:
    """Proyectos del AF y cotizaciones sin N° de requerimiento: sin el, el
    Flujo de Caja no asocia sus cuotas ni sus OC al proyecto."""
    salida = []
    proyectos = (af or {}).get("proyectos") or []
    sin_req = [p.get("tag") for p in proyectos if isinstance(p, dict) and not p.get("req")]
    if sin_req:
        salida.append(Pendiente(
            "medio", f"{len(sin_req)} proyecto(s) del AF sin N° de requerimiento: {', '.join(map(str, sin_req[:12]))}"
                     f"{' ...' if len(sin_req) > 12 else ''}.",
            "completarlo en «Ingresar datos» del tablero del AF si el proyecto tiene requerimiento"))
    docs = [d for d in ((documentos or {}).get("documentos") or []) if isinstance(d, dict)]
    cot = [d for d in docs if str(d.get("tipo")) == "60" and str(d.get("pais") or "Chile") == "Chile"]
    sin = [d for d in cot if not ((d.get("proyecto") or {}).get("req"))]
    if cot and sin:
        salida.append(Pendiente(
            "medio", f"{len(sin)} de {len(cot)} cotizacion(es) de Chile sin N° de requerimiento.",
            "Sistema QUEMPIN propone el N° al editarlas («Usar este N°»); las ventas directas no lo llevan"))
    return salida


def pendientes(raiz_intercambio: Path | None, extras: list[Pendiente] = (), ahora: datetime | None = None) -> list[Pendiente]:
    ahora = ahora or datetime.now()
    if raiz_intercambio is None:
        base = [Pendiente("alto", "No se encontro la carpeta de intercambio.",
                          "sincronizar la biblioteca «Formulación de proyectos»")]
    else:
        base = desde_estado(_leer_datos(raiz_intercambio, "estado"), ahora)
        base += sin_requerimiento(_leer_datos(raiz_intercambio, "analisis-financiero"),
                                  _leer_datos(raiz_intercambio, "documentos-comerciales"))
    todos = base + list(extras)
    return sorted(todos, key=lambda p: 0 if p.nivel == "alto" else 1)


def imprimir(lista: list[Pendiente]) -> None:
    print("\n" + "=" * 72)
    print("  BANDEJA DE PENDIENTES -- lo que espera a una persona")
    print("=" * 72)
    if not lista:
        print("  Nada pendiente.")
        return
    for p in lista:
        marca = "[!]" if p.nivel == "alto" else "[ ]"
        print(f"  {marca} {p.texto}")
        if p.accion:
            print(f"      -> {p.accion}")
