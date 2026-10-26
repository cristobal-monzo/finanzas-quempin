# -*- coding: utf-8 -*-
"""
planilla_escritura.py -- Lo único que se escribe en la Planilla de Ingreso de
Requerimientos, y siempre con Excel (``planilla_excel.ps1``, por COM).

Pedido del usuario (2026-10-26): «si se hace un proyecto sin número de
requerimiento desde el formulador, se registre dicha información en la
planilla, siguiendo el formato exacto que ya existe», y que el N° de cada
proyecto se mantenga aunque alguien vuelva a ordenar la tabla (ese día se
ordenó y 55 requerimientos cambiaron de N°, porque el N° era la fórmula
=SI(B<>"";FILA()-1;"")).

Hace dos cosas, y ninguna borra ni mueve filas:

1. **Fija los N°** (``plan_fijar``): cada fila con datos cuyo N° todavía es
   la fórmula pasa a tener su N° escrito como número, igual que las filas
   en que el equipo ya lo escribía a mano. El N° es el de la
   última publicación (``publicado/requerimientos.json``) cuando la fila ya
   estaba ahí; si es una fila nueva, el que muestra la fórmula, salvo que
   choque con otro (entonces el siguiente libre, con aviso).
2. **Registra los proyectos nuevos** que manda el Formulador (mensaje
   ``nuevo-requerimiento`` → ``planilla-requerimientos``): una fila al final
   de la lista con el N° que el Formulador reservó. Si ese N° ya lo tomó
   otro, no se escribe y el mensaje queda ``rechazado`` con el motivo: la
   carpeta y el código del proyecto ya llevan ese N°, así que lo decide una
   persona.

Por qué Excel y no openpyxl: ver ``requerimientos.py`` (openpyxl borra
xl/metadata.xml y xl/richData). Excel abre el archivo de OneDrive con
coautoría, así que un colega que la tenga abierta en el navegador no
choca; si alguien la tiene tomada en un Excel de escritorio, se abre solo
para lectura, no se escribe nada y se reintenta en la vuelta siguiente.

Antes de cada escritura queda un respaldo en
``%LOCALAPPDATA%\\QUEMPIN\\respaldos-planilla`` (los últimos 30).

Uso:  py -3.14 planilla_escritura.py [--simular]     (la tarea cada 10 minutos)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

import esquemas
import intercambio
import requerimientos
import ubicacion

AQUI = Path(__file__).resolve().parent
SCRIPT_EXCEL = AQUI / "planilla_excel.ps1"
TABLA = "Proyectos"
TIPO_NUEVO = "nuevo-requerimiento"
RESPALDOS = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "QUEMPIN" / "respaldos-planilla"
MAX_RESPALDOS = 30
ESTADO = AQUI / "planilla_escritura_estado.json"   # firma de la planilla ya revisada (gitignoreado)

# Columnas de la planilla (letra) para cada dato de una fila nueva.
COLUMNA = {"estado": "B", "canal": "C", "captador": "D", "evaluador": "E", "titulo": "F", "ubicacion": "G",
           "referencia": "H", "presupuesto": "N", "valorOfertado": "O", "valorAdjudicado": "P"}
FECHAS = {"apertura": "I", "cierre": "J"}


def _es_formula(valor) -> bool:
    return isinstance(valor, str) and valor.startswith("=")


def _clave(titulo, referencia) -> tuple:
    return (requerimientos.normalizar_encabezado(titulo), requerimientos.normalizar_encabezado(referencia))


def leer_filas(ruta: Path) -> list[dict]:
    """Cada fila de la hoja con Estado o Título: su fila, si su N° es fórmula,
    el N° que muestra (el valor guardado por Excel), título y referencia."""
    import openpyxl

    formulas = openpyxl.load_workbook(ruta, read_only=True, data_only=False)
    valores = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        hf = formulas[requerimientos.HOJA]
        hv = valores[requerimientos.HOJA]
        salida = []
        for n, (ff, fv) in enumerate(zip(hf.iter_rows(min_row=2, max_col=8), hv.iter_rows(min_row=2, max_col=8)), start=2):
            estado, titulo = fv[1].value, fv[5].value
            if (estado in (None, "")) and (titulo in (None, "")):
                continue
            salida.append({"fila": n, "formula": _es_formula(ff[0].value), "numero": requerimientos._numero(fv[0].value),
                           "titulo": titulo if isinstance(titulo, str) else ("" if titulo is None else str(titulo)),
                           "referencia": fv[7].value})
        return salida
    finally:
        formulas.close()
        valores.close()


def plan_fijar(filas: list[dict], publicados: list[dict]) -> tuple[list[dict], list[str]]:
    """Las operaciones 'fijar' para las filas con N° en fórmula, y los avisos."""
    fijos = {f["numero"] for f in filas if not f["formula"] and f["numero"] is not None}
    por_clave: dict = {}
    for r in sorted(publicados, key=lambda r: r["numero"]):
        por_clave.setdefault(_clave(r.get("titulo"), r.get("referencia")), []).append(r["numero"])
    usados = set(fijos)
    ops, avisos, sin_publicar = [], [], []
    for f in filas:
        if not f["formula"]:
            continue
        candidatos = [n for n in por_clave.get(_clave(f["titulo"], f["referencia"]), []) if n not in usados]
        if candidatos:
            numero = candidatos[0]
        else:
            sin_publicar.append(f)
            continue
        usados.add(numero)
        ops.append({"op": "fijar", "fila": f["fila"], "titulo": f["titulo"], "numero": numero})
    # Filas nuevas (todavía no publicadas): el N° que muestra la fórmula, si nadie más lo tiene. Si choca,
    # no se inventa otro (quizá ya está en una carpeta): queda en fórmula y lo decide una persona.
    for f in sin_publicar:
        numero = f["numero"]
        if numero is None or numero in usados:
            avisos.append(f"Fila {f['fila']} «{f['titulo'][:50]}»: su N° {numero} ya lo tiene otro requerimiento; "
                          "queda como está para que una persona le dé su N°.")
            continue
        usados.add(numero)
        ops.append({"op": "fijar", "fila": f["fila"], "titulo": f["titulo"], "numero": numero})
    return ops, avisos


def numeros_tomados(filas: list[dict]) -> set:
    return {f["numero"] for f in filas if f["numero"] is not None}


def fila_de_mensaje(m: dict, formulacion: dict | None, hoy: date | None = None) -> dict:
    """La operación 'nueva' de un mensaje nuevo-requerimiento. Lo que el
    proyecto tenga al momento de escribir (título, ubicación, ID de
    licitación) manda sobre lo que traía el mensaje: pudo cambiar en esos
    minutos."""
    r = dict(m["requerimiento"])
    f = (formulacion or {}).get("datos") or {}
    if str(f.get("titulo") or "").strip():
        r["titulo"] = str(f["titulo"]).strip()
    if str(f.get("ubicacion") or "").strip():
        r["ubicacion"] = str(f["ubicacion"]).strip()
    if str(f.get("idLicitacion") or "").strip():
        r["referencia"] = str(f["idLicitacion"]).strip()
        r.setdefault("canal", "Mercado Público")
    r.setdefault("estado", "Evaluación")
    r.setdefault("canal", "Otro")
    # Como las demás filas que no son de Mercado Público: «-» cuando no hay referencia
    r.setdefault("referencia", "-")
    r.setdefault("apertura", (hoy or date.today()).isoformat())
    # Un texto que empieza con = + @ sería una fórmula en Excel: va con apóstrofo, como al escribirlo a mano
    texto = lambda v: "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "@") else v
    valores = {COLUMNA[k]: texto(r[k]) for k in COLUMNA if r.get(k) not in (None, "")}
    # AAAA-MM-DD, o con la hora (el cierre de una licitación): AAAA-MM-DDTHH:MM
    fechas = {FECHAS[k]: str(r[k])[:16] for k in FECHAS if r.get(k)}
    return {"op": "nueva", "numero": int(r["numero"]), "valores": valores, "fechas": fechas}


# ── EXCEL ────────────────────────────────────────────────────────────────────

def respaldar(ruta: Path) -> Path:
    RESPALDOS.mkdir(parents=True, exist_ok=True)
    destino = RESPALDOS / f"{datetime.now():%Y%m%d-%H%M%S} {ruta.name}"
    shutil.copy2(ruta, destino)
    for viejo in sorted(RESPALDOS.glob("*.xlsx"))[:-MAX_RESPALDOS]:
        viejo.unlink(missing_ok=True)
    return destino


def escribir(ruta: Path, operaciones: list[dict], limite: int = 600) -> dict:
    """Aplica las operaciones con Excel. {estado, detalle, resultados}."""
    if not operaciones:
        return {"estado": "ok", "detalle": "nada que escribir", "resultados": []}
    respaldar(ruta)
    with tempfile.TemporaryDirectory() as tmp:
        entrada, salida = Path(tmp) / "entrada.json", Path(tmp) / "salida.json"
        entrada.write_text(json.dumps({"ruta": str(ruta), "hoja": requerimientos.HOJA, "tabla": TABLA,
                                       "operaciones": operaciones}, ensure_ascii=False), encoding="utf-8")
        # Sin cambiar la política de ejecución: la del usuario (RemoteSigned) ya deja correr un script local
        proceso = subprocess.run(["powershell", "-NoProfile", "-File", str(SCRIPT_EXCEL),
                                  "-Entrada", str(entrada), "-Salida", str(salida)],
                                 capture_output=True, text=True, timeout=limite)
        if not salida.exists():
            return {"estado": "error", "detalle": (proceso.stderr or proceso.stdout or "Excel no respondió")[-500:], "resultados": []}
        return json.loads(salida.read_text(encoding="utf-8-sig"))


# ── LA VUELTA (cada 10 minutos) ──────────────────────────────────────────────

def _firma(ruta: Path) -> str:
    st = ruta.stat()
    return f"{st.st_size}:{int(st.st_mtime)}"


def _leer_estado() -> dict:
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def vuelta(raiz: Path | None = None, planilla: Path | None = None, simular: bool = False) -> dict:
    raiz = raiz or ubicacion.ubicar_intercambio(AQUI)
    planilla = planilla or ubicacion.ubicar_planilla(AQUI)
    if raiz is None or planilla is None or not Path(planilla).exists():
        return {"activo": False, "detalle": "sin la biblioteca de Formulación en este equipo"}
    mensajes, _ = intercambio.leer_buzon(raiz, destino=requerimientos.DESTINO, tipo=TIPO_NUEVO)
    previo = _leer_estado()
    firma = _firma(planilla)
    if not mensajes and previo.get("firma") == firma:
        return {"activo": True, "detalle": "sin cambios"}

    filas = leer_filas(planilla)
    publicados = ((intercambio.leer_publicacion(raiz, requerimientos.PUBLICACION) or {}).get("datos") or {}).get("requerimientos") or []
    ops, avisos = plan_fijar(filas, publicados)
    tomados = numeros_tomados(filas) | {o["numero"] for o in ops}
    nuevos = []      # (mensaje, operación)
    for m in sorted(mensajes, key=lambda m: m["origen"]["enviado"]):
        errores = esquemas.validar_mensaje(m)
        if errores:
            if not simular:
                intercambio.archivar(raiz, m, "rechazado", errores)
            continue
        numero = int(m["requerimiento"]["numero"])
        if numero in tomados:
            dueno = next((f["titulo"] for f in filas if f["numero"] == numero), "")
            # ¿Es el mismo proyecto, ya escrito (una vuelta que se cortó después de guardar)?
            if requerimientos.normalizar_encabezado(dueno) == requerimientos.normalizar_encabezado(m["requerimiento"].get("titulo")):
                if not simular:
                    intercambio.archivar(raiz, m, "sin-cambios", [f"El N° {numero} ya está en la planilla con ese título."],
                                         extra={"requerimiento": numero})
                continue
            if not simular:
                intercambio.archivar(raiz, m, "rechazado",
                                     [f"El N° {numero} ya es «{dueno}» en la planilla: el proyecto necesita otro N° (lo decide una persona)."],
                                     extra={"requerimiento": numero})
            avisos.append(f"N° {numero} pedido por el Formulador ya es «{dueno}».")
            continue
        formulacion = None
        uid = (m.get("fuente") or {}).get("uid")
        if uid:
            try:
                formulacion = json.loads((Path(raiz) / "publicado" / "formulador" / f"{uid}.json").read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                formulacion = None
        op = fila_de_mensaje(m, formulacion)
        tomados.add(numero)
        nuevos.append((m, op))
        ops.append(op)

    if simular:
        return {"activo": True, "simulado": True, "operaciones": ops, "avisos": avisos}
    if not ops:
        ESTADO.write_text(json.dumps({"firma": firma}), encoding="utf-8")
        return {"activo": True, "detalle": "N° ya fijos; nada que registrar", "avisos": avisos}
    resultado = escribir(Path(planilla), ops)
    if resultado.get("estado") != "ok":
        return {"activo": True, "detalle": f"planilla {resultado.get('estado')}: {resultado.get('detalle')}", "avisos": avisos}
    por_i = {r["i"]: r for r in resultado.get("resultados") or []}
    fijados = sum(1 for i, o in enumerate(ops) if o["op"] == "fijar" and (por_i.get(i) or {}).get("ok"))
    registrados = 0
    for m, op in nuevos:
        r = por_i.get(ops.index(op)) or {}
        if r.get("ok"):
            registrados += 1
            intercambio.archivar(raiz, m, "aplicado", [f"Registrado en la planilla: N° {op['numero']}, fila {r.get('fila')}."],
                                 extra={"requerimiento": op["numero"], "fila": r.get("fila")})
        else:
            avisos.append(f"N° {op['numero']}: {r.get('detalle') or 'no se escribió'} (se reintenta).")
    fallidos = [r for r in resultado.get("resultados") or [] if not r.get("ok")]
    if not fallidos:
        ESTADO.write_text(json.dumps({"firma": _firma(Path(planilla))}), encoding="utf-8")
    if registrados:
        # Las demás herramientas ven el N° ya, sin esperar la vuelta del procesador (cada 2 horas)
        try:
            requerimientos.publicar(raiz, Path(planilla))
        except Exception as error:  # noqa: BLE001 -- el registro ya quedó; publicar lo reintenta el procesador
            avisos.append(f"No se republicó la planilla: {error}")
    return {"activo": True, "detalle": f"{fijados} N° fijados, {registrados} requerimiento(s) registrado(s)",
            "avisos": avisos + [r.get("detalle") for r in fallidos if r.get("detalle")]}


LOGS = AQUI.parent / "logs"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        resultado = vuelta(simular="--simular" in argv)
    except Exception as error:  # noqa: BLE001 -- queda en el log; la vuelta siguiente reintenta
        resultado = {"activo": True, "detalle": f"error: {error}"}
    linea = json.dumps(resultado, ensure_ascii=False, default=str)
    print(json.dumps(resultado, ensure_ascii=False, indent=1, default=str) if "--simular" in argv else linea)
    # Una línea por vuelta que hizo algo (las «sin cambios» de cada 10 minutos no se anotan)
    if "--simular" not in argv and resultado.get("detalle") != "sin cambios":
        LOGS.mkdir(exist_ok=True)
        with open(LOGS / f"planilla_{datetime.now():%Y-%m}.log", "a", encoding="utf-8") as log:
            log.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {linea}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
