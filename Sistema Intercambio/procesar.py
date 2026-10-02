# -*- coding: utf-8 -*-
"""
procesar.py -- El procesador del intercambio: mantiene la carpeta al día entre
una corrida grande y otra.

Plan de integración (2026-09-30, §5.5). Antes, el lado Python solo se movía
cuando corría ``/Actualizar_Finanzas`` (tarea programada dom/mar/jue a las
23:00, o a la mañana siguiente si el PC estaba apagado): un envío hecho un
miércoles se aplicaba el viernes. Este procesador corre cada 15 minutos (su
propia tarea programada, ver ``tarea_procesador.cmd``) y hace solo lo barato,
y solo si algo cambió desde la última vez:

1. ``esquemas.json``: deja el catálogo en la carpeta (las herramientas de
   otros repositorios validan con él).
2. Formulaciones entregadas por archivo -> repositorio del Formulador.
3. Planilla de Ingreso -> ``requerimientos.json``, y cierra las sugerencias
   que ya están pasadas a la planilla.
4. Análisis Financiero: si llegaron envíos nuevos, ``run`` (con respaldo); si
   no, pero cambió el Centro de Costos o su libro, solo republica (sin
   escribir el Excel).
5. Cotizador: republica los precios de referencia si cambió la foto del
   tablero (no pide la UF de nuevo).
6. Sistema QUEMPIN: registros de documentos de otras herramientas,
   borradores inválidos y sus publicaciones (con su propio Python).
7. ``proyectos.json``: el cruce de claves, con todo lo anterior.
8. ``estado.json``: el pulso que muestran las herramientas («al día hace 6
   min»): qué corrió, qué quedó pendiente por destinatario y cuán nueva es
   cada publicación.

Cada paso corre envuelto: uno que falla queda en ``estado.json`` y no frena a
los demás (mismo criterio que los pasos 12b/12c/12d de Centro de Costos). Los
módulos de Finanzas corren en su propio proceso, igual que en
``/Actualizar_Finanzas``: tienen archivos homónimos que chocan en sys.modules.

Nunca escribe la Planilla de Ingreso ni publica nada en GitHub.

Uso:  py -3.14 procesar.py [--forzar]
"""

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent                     # Sistema Intercambio
RAIZ_FINANZAS = AQUI.parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import esquemas  # noqa: E402
import formulaciones  # noqa: E402
import intercambio  # noqa: E402
import proyectos  # noqa: E402
import requerimientos  # noqa: E402
import ubicacion  # noqa: E402

RUTA_ESTADO_LOCAL = AQUI / "procesador_estado.json"    # firmas de lo ya procesado (gitignoreado)
RUTA_CANDADO = AQUI / ".procesador.lock"
CANDADO_VENCE_SEG = 30 * 60
CARPETA_LOGS = RAIZ_FINANZAS / "logs"
ARCHIVO_PAQUETE = "esquemas.json"
PUBLICACION_ESTADO = "estado"

DRIVER_AF = RAIZ_FINANZAS / "Sistema Analisis Financiero" / ".claude" / "skills" / "Registro_Analisis_Financiero" / "driver.py"
DRIVER_COTIZADOR = RAIZ_FINANZAS / "Cotizador Historico" / ".claude" / "skills" / "Cotizador_Historico" / "driver.py"
EXCEL_AF = RAIZ_FINANZAS / "Análisis Financiero" / "Análisis de Proyectos 2026.xlsx"
EXCEL_CC = RAIZ_FINANZAS / "Centro de Costos" / "Excel" / "Centro de Costos.xlsx"
FOTO_COTIZADOR = RAIZ_FINANZAS / "Cotizador Historico" / "Visualizador Web" / "data" / "cotizador-historico.json"
RAIZ_FACTURAS_CL = (RAIZ_FINANZAS / "Centro de Costos" / "Sitio de comunicación - Centro de Costos 1"
                    / "Facturas y Boletas" / "Chile")
# Sistema QUEMPIN es otro repositorio, con su propio Python (3.11, el que
# tiene PySide6): se lo llama como proceso aparte.
RAIZ_SISTEMA_QUEMPIN = RAIZ_FINANZAS.parent / "Sistema QUEMPIN"
PYTHON_SISTEMA_QUEMPIN = os.environ.get("QUEMPIN_PYTHON_SISTEMA", "py -3.11").split()

TIPOS_AF = ("presupuesto-proyecto", "venta-proyecto")


# ── UTILIDADES ───────────────────────────────────────────────────────────────

def firma_archivo(ruta) -> str | None:
    """Fecha de modificación + tamaño: alcanza para saber si cambió sin leerlo."""
    try:
        st = Path(ruta).stat()
    except OSError:
        return None
    return f"{int(st.st_mtime)}-{st.st_size}"


def _leer_json(ruta: Path, por_defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return por_defecto


def _guardar_json(ruta: Path, datos) -> None:
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(temporal, ruta)


def correr(comando: list, cwd: Path | None = None, limite: int = 600) -> tuple[bool, str]:
    """Corre un proceso aparte y devuelve (ok, últimas líneas de su salida)."""
    try:
        proceso = subprocess.run(comando, cwd=cwd, capture_output=True, timeout=limite,
                                 env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)
    salida = (proceso.stdout + proceso.stderr).decode("utf-8", "replace")
    ok = proceso.returncode == 0 and "[ERROR]" not in salida and "Traceback" not in salida
    return ok, "\n".join(salida.strip().splitlines()[-6:])


# ── PASOS ────────────────────────────────────────────────────────────────────
# Cada paso recibe (raiz, previo, forzar) y devuelve (detalle, firma nueva o
# None si no hizo nada). 'previo' es la firma con que corrió la última vez.

def paso_esquemas(raiz: Path, previo, forzar):
    paquete = esquemas.paquete()
    texto = json.dumps(paquete, ensure_ascii=False, sort_keys=True)
    firma = hashlib.sha1(texto.encode("utf-8")).hexdigest()
    if firma == previo and (raiz / ARCHIVO_PAQUETE).exists() and not forzar:
        return "sin cambios", None
    intercambio._escribir_json_atomico(raiz / ARCHIVO_PAQUETE, paquete)
    return f"{len(paquete['mensajes'])} tipos de mensaje y {len(paquete['publicaciones'])} publicaciones", firma


def paso_formulaciones(raiz: Path, previo, forzar):
    mensajes, _ = intercambio.leer_buzon(raiz, destino=formulaciones.DESTINO, tipo=formulaciones.TIPO_ENTREGA)
    if not mensajes:
        return "sin entregas por archivo", None
    resultados = formulaciones.incorporar_buzon(raiz)
    return f"{len(resultados)} entrega(s) incorporada(s)", "ok"


def paso_requerimientos(raiz: Path, previo, forzar):
    planilla = ubicacion.ubicar_planilla(AQUI)
    if planilla is None:
        return "Planilla de Ingreso no encontrada (biblioteca sin sincronizar)", None
    firma = firma_archivo(planilla)
    pendientes, _ = intercambio.leer_buzon(raiz, destino=requerimientos.DESTINO, tipo=requerimientos.TIPO_SUGERENCIA)
    if firma == previo and not pendientes and not forzar:
        return "sin cambios", None
    if firma != previo or forzar or intercambio.leer_publicacion(raiz, requerimientos.PUBLICACION) is None:
        requerimientos.publicar(raiz, planilla)
    reqs = (intercambio.leer_publicacion(raiz, requerimientos.PUBLICACION) or {}).get("datos", {}).get("requerimientos", [])
    decisiones = requerimientos.revisar_sugerencias(raiz, reqs)
    aplicadas = sum(1 for d in decisiones if d["accion"] == "aplicado")
    esperan = sum(1 for d in decisiones if d["accion"] in ("pendiente", "conflicto"))
    return f"{len(reqs)} requerimientos; sugerencias: {aplicadas} cerradas, {esperan} esperan", firma


def _envios_af(raiz: Path) -> list:
    mensajes, _ = intercambio.leer_buzon(raiz, destino="analisis-financiero")
    return sorted(m["id"] for m in mensajes if m["tipo"] in TIPOS_AF)


def _firma_af(envios: list) -> str:
    return json.dumps({"envios": envios, "af": firma_archivo(EXCEL_AF), "cc": firma_archivo(EXCEL_CC)})


def paso_analisis_financiero(raiz: Path, previo, forzar):
    """'run' (con respaldo) solo si hay envíos que todavía no se intentaron;
    si no, y cambió el Centro de Costos o el libro, solo republica sin
    escribir el Excel. Un envío que queda pendiente (valor escrito a mano)
    no dispara un run cada 15 minutos: se reintenta cuando cambia algo."""
    envios = _envios_af(raiz)
    firma = _firma_af(envios)
    if firma == previo and not forzar:
        return "sin cambios", None
    anteriores = json.loads(previo).get("envios") if previo else None
    if envios and (forzar or envios != anteriores):
        ok, salida = correr([sys.executable, str(DRIVER_AF), "run"], cwd=DRIVER_AF.parent)
        if not ok:
            raise RuntimeError(f"run de Análisis Financiero: {salida}")
        quedan = _envios_af(raiz)
        # La firma se toma DESPUÉS del run, que cambia el Excel: si no, la
        # próxima vuelta lo volvería a correr por su propio guardado.
        return f"{len(envios) - len(quedan)} envío(s) aplicado(s), {len(quedan)} en espera", _firma_af(quedan)
    ok, salida = correr([sys.executable, str(DRIVER_AF), "intercambio", "publicar"], cwd=DRIVER_AF.parent)
    if not ok:
        raise RuntimeError(f"publicar de Análisis Financiero: {salida}")
    return "lista de proyectos republicada (sin tocar el Excel)", firma


def paso_precios(raiz: Path, previo, forzar):
    firma = firma_archivo(FOTO_COTIZADOR)
    if firma is None:
        return "el tablero del Cotizador no se ha generado", None
    if firma == previo and intercambio.leer_publicacion(raiz, "precios-referencia") and not forzar:
        return "sin cambios", None
    ok, salida = correr([sys.executable, str(DRIVER_COTIZADOR), "precios"], cwd=DRIVER_COTIZADOR.parent)
    if not ok:
        raise RuntimeError(f"precios del Cotizador: {salida}")
    return salida.splitlines()[-1] if salida else "publicados", firma


def paso_sistema_quempin(raiz: Path, previo, forzar):
    if not (RAIZ_SISTEMA_QUEMPIN / "app" / "integraciones" / "ecosistema.py").exists():
        return "Sistema QUEMPIN no está en este equipo", None
    ok, salida = correr(PYTHON_SISTEMA_QUEMPIN + ["-m", "app.integraciones.ecosistema", "procesar"],
                        cwd=RAIZ_SISTEMA_QUEMPIN, limite=300)
    if not ok:
        raise RuntimeError(f"Sistema QUEMPIN: {salida}")
    try:
        resultado = json.loads(salida.splitlines()[-1])
    except (ValueError, IndexError):
        return salida[-200:], "ok"
    if not resultado.get("activo"):
        return "; ".join(resultado.get("avisos") or ["inactivo"]), None
    detalle = f"publicado; {resultado.get('borradores', 0)} borrador(es) esperan en Sistema QUEMPIN"
    if resultado.get("avisos"):   # ej. «folios: no se pudo publicar (...)»: que se vea, no solo en su log
        detalle += " · avisos: " + "; ".join(resultado["avisos"])
    return detalle, "ok"


def paso_proyectos(raiz: Path, previo, forzar):
    carpetas = proyectos.carpetas_de_proyectos(AQUI, RAIZ_FACTURAS_CL if RAIZ_FACTURAS_CL.is_dir() else None)
    r = proyectos.publicar(raiz, carpetas)
    return (f"{r['proyectos']} proyectos; {r['sin_tag_req']} TAG sin N° de requerimiento; "
            f"{r['conflictos']} conflicto(s)"), "ok"


PASOS = (
    ("esquemas", paso_esquemas),
    ("formulaciones", paso_formulaciones),
    ("requerimientos", paso_requerimientos),
    ("analisis-financiero", paso_analisis_financiero),
    ("precios-referencia", paso_precios),
    ("sistema-quempin", paso_sistema_quempin),
    ("proyectos", paso_proyectos),
)


# ── ESTADO PUBLICADO ─────────────────────────────────────────────────────────

def resumen_publicaciones(raiz: Path) -> dict:
    salida = {}
    for ruta in sorted((raiz / intercambio.CARPETA_PUBLICADO).glob("*.json")):
        sobre = intercambio.leer_publicacion(raiz, ruta.stem)
        if sobre:
            salida[ruta.stem] = {"herramienta": sobre.get("herramienta"), "generado": sobre.get("generado")}
    repositorio = raiz / intercambio.CARPETA_PUBLICADO / "formulador"
    if repositorio.is_dir():
        salida["formulador/"] = {"herramienta": "formulador",
                                 "proyectos": sum(1 for _ in repositorio.glob("*.json"))}
    return salida


def resumen_buzon(raiz: Path) -> dict:
    mensajes, invalidos = intercambio.leer_buzon(raiz)
    por_destino: dict[str, dict] = {}
    for m in mensajes:
        d = por_destino.setdefault(m["destino"], {"pendientes": 0, "masAntiguo": None, "tipos": {}})
        d["pendientes"] += 1
        d["tipos"][m["tipo"]] = d["tipos"].get(m["tipo"], 0) + 1
        if d["masAntiguo"] is None or m["origen"]["enviado"] < d["masAntiguo"]:
            d["masAntiguo"] = m["origen"]["enviado"]
    if invalidos:
        por_destino["(ilegibles)"] = {"pendientes": len(invalidos), "masAntiguo": None, "tipos": {}}
    return por_destino


def publicar_estado(raiz: Path, pasos: dict, duracion: float, avisos: list) -> None:
    datos = {
        "procesador": {"ultimaCorrida": intercambio.ahora_iso(), "duracionSeg": round(duracion, 1),
                       "equipo": socket.gethostname(), "pasos": pasos},
        "publicaciones": resumen_publicaciones(raiz),
        "buzon": resumen_buzon(raiz),
        "avisos": avisos,
    }
    sobre = {"esquema": intercambio.ESQUEMA, "herramienta": "procesador", "generado": intercambio.ahora_iso(), "datos": datos}
    errores = esquemas.validar_publicacion(PUBLICACION_ESTADO, sobre)
    if errores:
        raise ValueError("estado.json no cumple su esquema: " + "; ".join(errores[:3]))
    intercambio.publicar(raiz, PUBLICACION_ESTADO, "procesador", datos)


# ── ORQUESTACIÓN ─────────────────────────────────────────────────────────────

class Ocupado(Exception):
    """Otra corrida del procesador sigue en curso."""


def _tomar_candado() -> None:
    try:
        descriptor = os.open(RUTA_CANDADO, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            edad = time.time() - RUTA_CANDADO.stat().st_mtime
        except OSError:
            edad = 0
        if edad < CANDADO_VENCE_SEG:
            raise Ocupado("otra corrida del procesador sigue en curso")
        RUTA_CANDADO.unlink(missing_ok=True)
        descriptor = os.open(RUTA_CANDADO, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(descriptor, str(os.getpid()).encode())
    os.close(descriptor)


def procesar(raiz: Path | None = None, forzar: bool = False, pasos=PASOS,
             ruta_estado: Path = RUTA_ESTADO_LOCAL) -> dict:
    """Una vuelta completa. Devuelve {'activo', 'pasos', 'avisos'}."""
    raiz = raiz or ubicacion.ubicar_intercambio(AQUI)
    if raiz is None or not intercambio.es_carpeta_de_intercambio(raiz):
        return {"activo": False, "pasos": {}, "avisos": [
            "No se encontró la carpeta de intercambio (biblioteca «Formulación de proyectos» sin sincronizar)."]}
    _tomar_candado()
    try:
        inicio = time.perf_counter()
        firmas = _leer_json(ruta_estado, {})
        resultado, avisos = {}, []
        for nombre, paso in pasos:
            t0 = time.perf_counter()
            try:
                detalle, firma = paso(raiz, firmas.get(nombre), forzar)
                resultado[nombre] = {"ok": True, "detalle": detalle, "seg": round(time.perf_counter() - t0, 1)}
                if firma is not None:
                    firmas[nombre] = firma
            except Exception as error:  # noqa: BLE001 -- un paso nunca frena a los demás
                resultado[nombre] = {"ok": False, "detalle": str(error)[:500], "seg": round(time.perf_counter() - t0, 1)}
                avisos.append(f"{nombre}: {str(error)[:200]}")
        _guardar_json(ruta_estado, firmas)
        publicar_estado(raiz, resultado, time.perf_counter() - inicio, avisos)
        return {"activo": True, "pasos": resultado, "avisos": avisos}
    finally:
        RUTA_CANDADO.unlink(missing_ok=True)


def _registrar(resultado: dict) -> None:
    try:
        CARPETA_LOGS.mkdir(exist_ok=True)
        ruta = CARPETA_LOGS / f"procesador_{datetime.now():%Y-%m}.log"
        partes = [f"{n}={'ok' if p['ok'] else 'FALLA'}" for n, p in resultado.get("pasos", {}).items()]
        linea = f"{datetime.now():%Y-%m-%d %H:%M:%S} {'activo' if resultado.get('activo') else 'inactivo'} " + " ".join(partes)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(linea + "".join(f"\n    {a}" for a in resultado.get("avisos", [])) + "\n")
    except OSError:
        pass


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except AttributeError:
        pass
    try:
        resultado = procesar(forzar="--forzar" in argv)
    except Ocupado as error:
        print(f"[INFO] {error}.")
        return 0
    _registrar(resultado)
    if not resultado["activo"]:
        print(f"[AVISO] {resultado['avisos'][0]}")
        return 0
    for nombre, paso in resultado["pasos"].items():
        print(f"  {'OK   ' if paso['ok'] else 'FALLA'} {nombre:<20} {paso['detalle']}  ({paso['seg']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
