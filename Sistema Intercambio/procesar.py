# -*- coding: utf-8 -*-
"""
procesar.py -- El procesador del intercambio: mantiene la carpeta al día entre
una corrida grande y otra.

Plan de integración (2026-09-30, §5.5). Antes, el lado Python solo se movía
cuando corría ``/Actualizar_Finanzas`` (tarea programada dom/mar/jue a las
23:00, o a la mañana siguiente si el PC estaba apagado): un envío hecho un
miércoles se aplicaba el viernes. Este procesador corre cada 2 horas (su
propia tarea programada, ver ``tarea_procesador.cmd``; el usuario eligió 2 horas
en vez de 15 minutos el 2026-10-02) y hace solo lo barato,
y solo si algo cambió desde la última vez:

1. ``esquemas.json``: deja el catálogo en la carpeta (las herramientas de
   otros repositorios validan con él), y el ``LEEME.md`` para personas, que
   vive versionado en ``LEEME-carpeta.md`` (desde el 2026-10-19; antes solo
   existía en la carpeta y quedó atrás).
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
7. Mercado Público: resultado de las licitaciones de la Planilla y órdenes
   de compra a QUEMPIN -> ``licitaciones.json`` y sugerencias para la
   Planilla (``mercado_publico.py``; consulta la API en cada vuelta).
7b. Oportunidades: licitaciones publicadas del rubro con su evaluación previa
   -> ``oportunidades.json`` (``oportunidades.py``; solo si su configuración
   dice ``enProcesador``; el equipo lo ve en su tablero).
7c. UF del día: una vez al día, para que el tablero del Cotizador tenga una
   UF reciente de respaldo si mindicador.cl no responde (2026-10-19).
7c2. Proyectos entregados (``cierre_entregados.py``, 2026-11-09): mueve a
   «0 Proyectos Entregados <año>» la carpeta que pidió el Portal al cerrar un
   proyecto, y lo que ya está ahí con la Planilla en «Adjudicado» lo pide
   «Cerrado» con un mensaje (la Planilla la escribe planilla_escritura.py).
7d. Carpetas de facturas de los proyectos (``carpetas_proyecto.py``,
   2026-10-28): crea la del Centro de Costos de lo recién adjudicado y deja
   en cada proyecto de Gestión de Proyectos el acceso directo web «Facturas
   del proyecto» a esa carpeta (2026-10-29).
7e. Documentos subidos desde el Portal -> «Facturas y Boletas/<país>/<proyecto>/»
   del Centro de Costos, y la lista de esas carpetas (``documentos_cc.py``,
   2026-10-23).
8. ``proyectos.json``: el cruce de claves, con todo lo anterior.
9. ``estado.json``: el pulso que muestran las herramientas («al día hace 6
   min»): qué corrió, qué quedó pendiente por destinatario y cuán nueva es
   cada publicación.

Cada paso corre envuelto: uno que falla queda en ``estado.json`` y no frena a
los demás (mismo criterio que los pasos 12b/12c/12d de Centro de Costos). Los
módulos de Finanzas corren en su propio proceso, igual que en
``/Actualizar_Finanzas``: tienen archivos homónimos que chocan en sys.modules.

Nunca escribe la Planilla de Ingreso ni publica nada en GitHub.

A pedido (2026-11-02): el botón «Actualizar datos» del Portal deja un mensaje
``pedir-vuelta`` en el buzón, y otra tarea (``tarea_pedidos.cmd``, cada minuto)
corre ``--si-hay-pedido``, que da una vuelta normal solo si hay uno. Cada vuelta
archiva los pedidos que vio al empezar: el que llegó después pide otra.

Uso:  py -3.14 procesar.py [--forzar | --si-hay-pedido]
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

import carpetas_proyecto  # noqa: E402
import cierre_entregados  # noqa: E402
import documentos_cc  # noqa: E402
import documentos_proyecto  # noqa: E402
import esquemas  # noqa: E402
import formulaciones  # noqa: E402
import intercambio  # noqa: E402
import mercado_publico  # noqa: E402
import oportunidades  # noqa: E402
import proyectos  # noqa: E402
import requerimientos  # noqa: E402
import respaldo  # noqa: E402
import ubicacion  # noqa: E402

RUTA_ESTADO_LOCAL = AQUI / "procesador_estado.json"    # firmas de lo ya procesado (gitignoreado)
RUTA_CANDADO = AQUI / ".procesador.lock"
CANDADO_VENCE_SEG = 30 * 60
CARPETA_LOGS = RAIZ_FINANZAS / "logs"
ARCHIVO_PAQUETE = "esquemas.json"
ARCHIVO_LEEME = "LEEME.md"
LEEME_VERSIONADO = AQUI / "LEEME-carpeta.md"
PUBLICACION_ESTADO = "estado"
DESTINO_PEDIDOS = "procesador"
TIPO_PEDIDO = "pedir-vuelta"
PEDIDO_SEPARACION_SEG = 5 * 60   # un pedido espera en el buzón si la última vuelta es más reciente que esto

DRIVER_AF = RAIZ_FINANZAS / "Sistema Analisis Financiero" / ".claude" / "skills" / "Registro_Analisis_Financiero" / "driver.py"
DRIVER_COTIZADOR = RAIZ_FINANZAS / "Cotizador Historico" / ".claude" / "skills" / "Cotizador_Historico" / "driver.py"
EXCEL_AF = RAIZ_FINANZAS / "Análisis Financiero" / "Análisis de Proyectos 2026.xlsx"
EXCEL_CC = RAIZ_FINANZAS / "Centro de Costos" / "Excel" / "Centro de Costos.xlsx"
FOTO_COTIZADOR = RAIZ_FINANZAS / "Cotizador Historico" / "Visualizador Web" / "data" / "cotizador-historico.json"
# El snapshot saneado que el Centro de Costos arma en cada run (PASO 12c): sus facturas, para «Proyectos en ejecución»
FOTO_CC = RAIZ_FINANZAS / "Centro de Costos" / "Visualizador Web" / "data" / "centro-de-costos.json"
UF_ULTIMA = RAIZ_FINANZAS / "Cotizador Historico" / "Sistema" / "uf_ultima.json"
RAIZ_FACTURAS_CL = (RAIZ_FINANZAS / "Centro de Costos" / "Sitio de comunicación - Centro de Costos 1"
                    / "Facturas y Boletas" / "Chile")
# Sistema QUEMPIN es otro repositorio, con su propio Python (3.11, el que
# tiene PySide6): se lo llama como proceso aparte.
RAIZ_SISTEMA_QUEMPIN = RAIZ_FINANZAS.parent / "Sistema QUEMPIN"
PYTHON_SISTEMA_QUEMPIN = os.environ.get("QUEMPIN_PYTHON_SISTEMA", "py -3.11").split()

# Los tipos que atiende Análisis Financiero, leídos del catálogo (cada esquema
# declara su destino): antes era una lista escrita aquí, y un tipo nuevo
# (datos-proyecto, 2026-10-02) se habría quedado en el buzón sin disparar el run.
TIPOS_AF = tuple(sorted(t for t, ficha in esquemas.catalogo()["mensajes"].items()
                        if ficha.get("destino") == "analisis-financiero"))


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
    leeme = _poner_leeme(raiz)
    if firma == previo and (raiz / ARCHIVO_PAQUETE).exists() and not forzar:
        return "sin cambios" + leeme, None
    intercambio._escribir_json_atomico(raiz / ARCHIVO_PAQUETE, paquete)
    return f"{len(paquete['mensajes'])} tipos de mensaje y {len(paquete['publicaciones'])} publicaciones" + leeme, firma


def _poner_leeme(raiz: Path) -> str:
    """Deja en la carpeta el LEEME versionado, solo si cambió."""
    try:
        texto = LEEME_VERSIONADO.read_bytes()
    except OSError:
        return ""
    destino = raiz / ARCHIVO_LEEME
    try:
        if destino.read_bytes() == texto:
            return ""
    except OSError:
        pass
    temporal = destino.with_name(f".{destino.name}.tmp")
    temporal.write_bytes(texto)
    os.replace(temporal, destino)
    return "; LEEME.md al día"


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
    aplicadas = sum(1 for d in decisiones if d["accion"] in ("aplicado", "reemplazado"))
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
    no dispara un run en cada vuelta: se reintenta cuando cambia algo."""
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


def paso_documentos_proyecto(raiz: Path, previo, forzar):
    """Las facturas del Centro de Costos de cada proyecto (2026-11-06), para que
    el Portal las muestre y se asocien a sus gastos proyectados y cotizados."""
    firma = firma_archivo(FOTO_CC)
    if firma is None:
        return "el tablero del Centro de Costos no se ha generado", None
    if firma == previo and intercambio.leer_publicacion(raiz, documentos_proyecto.NOMBRE) and not forzar:
        return "sin cambios", None
    r = documentos_proyecto.publicar(raiz, FOTO_CC)
    return f"{r['documentos']} documento(s) de {r['proyectos']} proyecto(s)", firma


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


def paso_mercado_publico(raiz: Path, previo, forzar):
    """Siempre consulta: lo que cambia está en Mercado Público, no en la
    carpeta. Sin ticket o con el ticket rechazado, el paso falla y la bandeja
    de pendientes lo muestra con qué hacer."""
    r = mercado_publico.revisar(raiz)
    partes = [f"{r['licitaciones']} licitación(es), {r['ordenes']} OC, {r['llamadas']} consulta(s)"]
    if r["sugeridas"]:
        partes.append(f"{len(r['sugeridas'])} sugerencia(s) nueva(s) para la Planilla")
    if r["revisar"]:
        partes.append(f"{len(r['revisar'])} por revisar")
    if r["incompleta"]:
        partes.append("sigue en la próxima vuelta")
    return "; ".join(partes), "ok"


def paso_oportunidades(raiz: Path, previo, forzar):
    """Busca y evalúa licitaciones publicadas. Apagado hasta que la
    configuración diga «enProcesador»: consulta la API con el mismo ticket
    que el monitor y publica para todo el equipo."""
    config = oportunidades.cargar_config()
    if not config.get("enProcesador"):
        return "apagado (oportunidades_config.json, enProcesador)", None
    r = oportunidades.revisar(raiz, config=config)
    d = r["datos"]
    cuenta = {c: sum(1 for o in d["oportunidades"] if o["categoria"] == c) for c in ("prioritaria", "buena")}
    partes = [f"{len(d['oportunidades'])} evaluada(s): {cuenta['prioritaria']} prioritaria(s), {cuenta['buena']} buena(s)",
              f"{r['llamadas']} consulta(s)"]
    if r["incompleta"]:
        partes.append("sigue en la próxima vuelta")
    return "; ".join(partes), "ok"


def paso_uf(raiz: Path, previo, forzar):
    """Una consulta a mindicador.cl al día (driver.py uf del Cotizador), para
    que la UF de respaldo nunca tenga más de un día hábil."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    # La misma variable que usa el Cotizador (las pruebas la apuntan a tmp_path)
    guardada = _leer_json(Path(os.environ.get("QUEMPIN_UF_ULTIMA") or UF_ULTIMA), {}).get("fecha")
    if (guardada == hoy or previo == hoy) and not forzar:
        return "UF del día ya guardada", None
    ok, salida = correr([sys.executable, str(DRIVER_COTIZADOR), "uf"], cwd=DRIVER_COTIZADOR.parent, limite=120)
    if not ok:
        # Es solo el respaldo del Cotizador: mindicador.cl caído no es una falla del procesador
        # (no debe encender el aviso de las herramientas). Se reintenta en la próxima vuelta.
        return "mindicador.cl no respondió; se reintenta en la próxima vuelta", None
    return salida.splitlines()[-1] if salida else "UF guardada", hoy


def paso_respaldo(raiz: Path, previo, forzar):
    """Un zip al día de publicado/, buzon/, procesado/ y la Planilla, fuera de
    OneDrive (respaldo.py). Una falla no detiene al resto del procesador."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    if previo == hoy and not forzar:
        return "respaldo del día ya hecho", None
    try:
        zip_, n = respaldo.respaldar(raiz, ubicacion.ubicar_planilla(AQUI))
    except OSError as e:
        return f"respaldo no se pudo escribir ({e}); se reintenta en la próxima vuelta", None
    return f"{n} archivos en {zip_}", hoy


def _raices_facturas() -> dict:
    return {"CL": RAIZ_FACTURAS_CL, "PE": RAIZ_FACTURAS_CL.parent / "Perú"}


def paso_entregados(raiz: Path, previo, forzar):
    """Las carpetas que el Portal pidió llevar a «0 Proyectos Entregados», y lo que ya está ahí con la Planilla en
    «Adjudicado» pasa a «Cerrado» (cierre_entregados.py, 2026-11-09). Corre en cada vuelta: lo que cambia son las
    carpetas, no un archivo con firma. Su «firma» es lo que ya se pidió cerrar una vez."""
    detalle, estado, _ = cierre_entregados.vuelta(raiz, ubicacion.biblioteca(ubicacion.BIBLIOTECA_GESTION, AQUI),
                                                  previo if isinstance(previo, dict) else {})
    return detalle, estado


def paso_carpetas_proyecto(raiz: Path, previo, forzar):
    if not RAIZ_FACTURAS_CL.is_dir():
        return "el sitio del Centro de Costos no está sincronizado en este equipo", None
    r = carpetas_proyecto.atender(raiz, _raices_facturas(),
                                  ubicacion.biblioteca(ubicacion.BIBLIOTECA_GESTION, AQUI),
                                  carpetas_proyecto.RUTA_ESTADO)
    partes = []
    if r["creadasCC"]:
        partes.append("carpeta nueva en el Centro de Costos: " + ", ".join(r["creadasCC"]))
    if r["accesos"]:
        partes.append(f"«{carpetas_proyecto.ACCESO_FACTURAS}» en: " + ", ".join(r["accesos"]))
    if r["conArchivos"]:
        partes.append(f"una carpeta «{carpetas_proyecto.SUB_FACTURAS}» con archivos (pasarlos al Centro de Costos): "
                      + ", ".join(r["conArchivos"]))
    if r["sinQuitar"]:
        partes.append(f"no se pudo quitar la carpeta vacía «{carpetas_proyecto.SUB_FACTURAS}» de: " + ", ".join(r["sinQuitar"]))
    return "; ".join(partes) or "sin cambios", "ok"


def paso_documentos_cc(raiz: Path, previo, forzar):
    raices = _raices_facturas()
    r = documentos_cc.atender(raiz, raices)
    carpetas = documentos_cc.publicar_carpetas(raiz, {p: b for p, b in raices.items() if b.is_dir()})
    detalle = (f"{r['archivos']} archivo(s) de {r['aplicados']} envío(s) a Facturas y Boletas; "
               f"{r['esperan']} esperan; {r['rechazados']} rechazado(s); "
               + ", ".join(f"{n} carpetas {p}" for p, n in carpetas.items()))
    return detalle, None


def paso_proyectos(raiz: Path, previo, forzar):
    carpetas = proyectos.carpetas_de_proyectos(AQUI, RAIZ_FACTURAS_CL if RAIZ_FACTURAS_CL.is_dir() else None)
    # La dirección web de la carpeta del Centro de Costos (2026-10-29), para «Facturas del proyecto» del Portal
    carpetas["facturasWeb"] = carpetas_proyecto.enlaces_web(_raices_facturas(), carpetas_proyecto.RUTA_ESTADO)
    # Las carpetas de proyecto de la raíz de Gestión, con o sin N° (2026-11-03): todas van a «Proyectos en ejecución»
    raiz_gestion = ubicacion.biblioteca(ubicacion.BIBLIOTECA_GESTION, AQUI)
    gestion = proyectos.proyectos_en_gestion(raiz_gestion, proyectos.leer_temporales(raiz))
    # ... y las de «0 Proyectos Entregados <año>» (2026-11-09): la pestaña «Entregados» de esa vista
    entregados = proyectos.proyectos_entregados(raiz_gestion)
    r = proyectos.publicar(raiz, carpetas, gestion=gestion, entregados=entregados)
    return (f"{r['proyectos']} proyectos; {r['sin_tag_req']} TAG sin N° de requerimiento; "
            f"{r['conflictos']} conflicto(s); {r['gestion']} en Gestión de Proyectos, "
            f"{r['entregados']} entregados"), "ok"


PASOS = (
    ("esquemas", paso_esquemas),
    ("formulaciones", paso_formulaciones),
    ("requerimientos", paso_requerimientos),
    ("analisis-financiero", paso_analisis_financiero),
    ("precios-referencia", paso_precios),
    ("documentos-proyecto", paso_documentos_proyecto),
    ("sistema-quempin", paso_sistema_quempin),
    ("mercado-publico", paso_mercado_publico),
    ("oportunidades", paso_oportunidades),
    ("uf", paso_uf),
    ("entregados", paso_entregados),
    ("carpetas-proyecto", paso_carpetas_proyecto),
    ("documentos-cc", paso_documentos_cc),
    ("proyectos", paso_proyectos),
    ("respaldo", paso_respaldo),
)


# ── ESTADO PUBLICADO ─────────────────────────────────────────────────────────

def resumen_publicaciones(raiz: Path) -> dict:
    salida = {}
    for ruta in sorted((raiz / intercambio.CARPETA_PUBLICADO).glob("*.json")):
        sobre = intercambio.leer_publicacion(raiz, ruta.stem)
        if sobre:
            salida[ruta.stem] = {"herramienta": sobre.get("herramienta"), "generado": sobre.get("generado")}
    if PUBLICACION_ESTADO in salida:   # el que se está escribiendo: su fecha es la de esta vuelta, no la anterior
        salida[PUBLICACION_ESTADO]["generado"] = intercambio.ahora_iso()
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


# Lo que corre el procesador (2026-11-06, auditoría del flujo de entrega): las tareas programadas ejecutan los .py
# tal como estén en la carpeta principal de Finanzas. Esa carpeta estuvo semanas en una rama de trabajo
# («auditoria-proceso-errores», 63 commits adelante de master): un cambio de rama ahí cambiaba en el acto el código
# del procesador y de la Planilla. Cada vuelta dice qué rama y commit corrió, y avisa si no es la de producción o si
# hay código modificado sin commit.
RAMA_PRODUCCION = "master"
EXTENSIONES_CODIGO = (".py", ".ps1", ".cmd", ".bat", ".js", ".json", ".html", ".css", ".yml")
# La tarea que atiende «Actualizar datos» del Portal (procesar.py --si-hay-pedido, cada minuto). Si no está instalada,
# el pedido espera la vuelta de cada 2 horas, y el Portal lo dice en vez de prometer unos minutos.
TAREA_PEDIDOS = "Pedidos al procesador QUEMPIN"


def codigo_en_uso(repo: Path | None = None) -> dict | None:
    """{rama, commit, sucio} del repositorio desde el que corre el procesador; None si git no responde. 'sucio'
    cuenta solo archivos de código (un .md editado a mano no cambia lo que corre)."""
    repo = repo or AQUI.parent

    def git(*args):
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        return r.stdout if r.returncode == 0 else None
    try:
        rama, commit = git("rev-parse", "--abbrev-ref", "HEAD"), git("rev-parse", "--short", "HEAD")
        cambios = git("status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.SubprocessError):
        return None
    if rama is None or commit is None or cambios is None:
        return None
    rutas = [linea[3:].strip().strip('"') for linea in cambios.splitlines() if len(linea) > 3]
    sucio = any(r.lower().endswith(EXTENSIONES_CODIGO) for r in rutas)
    return {"rama": rama.strip(), "commit": commit.strip(), "sucio": sucio}


def avisos_de_codigo(codigo: dict | None) -> list[str]:
    if not codigo:
        return []
    if codigo["rama"] != RAMA_PRODUCCION:
        return [f"código: el procesador corre la rama «{codigo['rama']}» ({codigo['commit']}), no {RAMA_PRODUCCION}. "
                f"Las tareas programadas corren lo que esté abierto en la carpeta principal de Finanzas."]
    if codigo["sucio"]:
        return [f"código: la carpeta principal de Finanzas tiene código modificado sin commit ({codigo['commit']})."]
    return []


def tarea_de_pedidos_instalada() -> bool | None:
    """Si la tarea programada que atiende «Actualizar datos» existe en este equipo; None si no se pudo saber."""
    try:
        r = subprocess.run(["schtasks", "/query", "/tn", TAREA_PEDIDOS], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.returncode == 0


def publicar_estado(raiz: Path, pasos: dict, duracion: float, avisos: list) -> None:
    datos = {
        "procesador": {"ultimaCorrida": intercambio.ahora_iso(), "duracionSeg": round(duracion, 1),
                       "equipo": socket.gethostname(), "pasos": pasos},
        "publicaciones": resumen_publicaciones(raiz),
        "buzon": resumen_buzon(raiz),
        "avisos": avisos,
    }
    codigo = codigo_en_uso()
    if codigo:
        datos["codigo"] = codigo
        avisos.extend(avisos_de_codigo(codigo))
    tarea = tarea_de_pedidos_instalada()
    if tarea is not None:
        datos["pedidos"] = {"tarea": tarea}
    sobre = {"esquema": intercambio.ESQUEMA, "herramienta": "procesador", "generado": intercambio.ahora_iso(), "datos": datos}
    errores = esquemas.validar_publicacion(PUBLICACION_ESTADO, sobre)
    if errores:
        raise ValueError("estado.json no cumple su esquema: " + "; ".join(errores[:3]))
    intercambio.publicar(raiz, PUBLICACION_ESTADO, "procesador", datos)


# ── ORQUESTACIÓN ─────────────────────────────────────────────────────────────

class Ocupado(Exception):
    """Otra corrida del procesador sigue en curso."""


def _pedidos(raiz: Path) -> list:
    return intercambio.leer_buzon(raiz, destino=DESTINO_PEDIDOS, tipo=TIPO_PEDIDO)[0]


def _archivar_pedidos(raiz: Path, pedidos: list, avisos: list) -> None:
    for pedido in pedidos:
        try:
            intercambio.archivar(raiz, pedido, "aplicado", ["Atendido por la vuelta del procesador."])
        except OSError as error:   # sigue en el buzón: pedirá otra vuelta
            avisos.append(f"pedidos: {str(error)[:200]}")


def hay_pedido(raiz: Path) -> bool:
    """Hay un pedido en el buzón y la última vuelta no es tan reciente: el botón se puede apretar muchas veces, y
    cada vuelta consulta a Mercado Público (hasta 120 llamadas)."""
    if not _pedidos(raiz):
        return False
    estado = intercambio.leer_publicacion(raiz, PUBLICACION_ESTADO) or {}
    try:
        ultima = datetime.fromisoformat(estado["datos"]["procesador"]["ultimaCorrida"])
        return (datetime.now().astimezone() - ultima).total_seconds() >= PEDIDO_SEPARACION_SEG
    except (KeyError, TypeError, ValueError):
        return True


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
        pedidos = _pedidos(raiz)   # antes de los pasos: lo que se pida mientras corre puede no alcanzar a verse en esta vuelta
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
        _archivar_pedidos(raiz, pedidos, avisos)
        publicar_estado(raiz, resultado, time.perf_counter() - inicio, avisos)
        return {"activo": True, "pasos": resultado, "avisos": avisos, "pedidos": len(pedidos)}
    finally:
        RUTA_CANDADO.unlink(missing_ok=True)


PASO_LENTO_SEG = 10   # desde aquí el log anota los segundos del paso


def _registrar(resultado: dict) -> None:
    """Una línea por vuelta, con lo que tardó y los segundos de cada paso lento (2026-10-25): sistema-quempin
    llegó dos veces al límite de 300 s y la UF tardó 91 s, y el log solo decía «ok» o «FALLA»."""
    try:
        CARPETA_LOGS.mkdir(exist_ok=True)
        ruta = CARPETA_LOGS / f"procesador_{datetime.now():%Y-%m}.log"
        pasos = resultado.get("pasos", {})
        partes = [f"{n}={'ok' if p['ok'] else 'FALLA'}" + (f"({p['seg']:.0f}s)" if p.get("seg", 0) >= PASO_LENTO_SEG else "")
                  for n, p in pasos.items()]
        total = f" {sum(p.get('seg', 0) for p in pasos.values()):.0f}s" if pasos else ""
        pedidos = f" pedidos={resultado['pedidos']}" if resultado.get("pedidos") else ""
        linea = f"{datetime.now():%Y-%m-%d %H:%M:%S} {'activo' if resultado.get('activo') else 'inactivo'}{total}{pedidos} " + " ".join(partes)
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
    if "--si-hay-pedido" in argv:
        raiz = ubicacion.ubicar_intercambio(AQUI)
        if raiz is None or not intercambio.es_carpeta_de_intercambio(raiz) or not hay_pedido(raiz):
            return 0
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
