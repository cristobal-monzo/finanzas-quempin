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

Pedido del 2026-10-29: «que la planilla de proyectos sea replicada en el
portal», que desde ahora los proyectos se ingresen ahí y que el Excel quede
de respaldo, «actualizándose mutuamente». La vista «Planilla de Ingreso» del
Portal QUEMPIN lee ``publicado/requerimientos.json`` y escribe en el buzón;
este módulo es el puente con el Excel, en los dos sentidos.

Hace cuatro cosas, y ninguna borra ni mueve filas:

**Desde el 2026-11-06 el N° lo pone la fórmula del Excel** (decisión del
usuario: «el número se agrega solo en el Excel, completa el resto de
casillas»). La columna N° está protegida desde el 2026-11-03 y este módulo ya
no la escribe: el punto 1 quedó apagado (``FIJAR_N``) y una fila nueva se
escribe sin N°; el que le da la fórmula vuelve en el resultado. Si el
Formulador ya había reservado otro N° (su carpeta y su código lo llevan), la
fila se deshace y queda rechazada para que lo decida una persona.

1. **Fija los N°** (apagado, ver arriba) (``plan_fijar``): cada fila con datos cuyo N° todavía es
   la fórmula pasa a tener su N° escrito como número, igual que las filas
   en que el equipo ya lo escribía a mano. El N° es el de la
   última publicación (``publicado/requerimientos.json``) cuando la fila ya
   estaba ahí; si es una fila nueva, el que muestra la fórmula, salvo que
   choque con otro (entonces el siguiente libre, con aviso).
2. **Registra los proyectos nuevos** (mensaje ``nuevo-requerimiento`` →
   ``planilla-requerimientos``), del Formulador o del Portal: una fila al final
   de la lista con el N° que reservaron. Si ese N° ya lo tomó otro: el del
   Formulador no se escribe y queda ``rechazado`` (su carpeta y su código ya
   llevan ese N°: lo decide una persona); el del Portal (``numeroLibre``) toma
   el siguiente libre y lo dice.
3. **Aplica lo que se cambia en el Portal o se exporta desde el Formulador**
   (mensaje ``editar-requerimiento``): las casillas que alguien cambió o eligió
   exportar, en la fila de ese N°. Si la misma casilla
   cambió también en el Excel, **manda el cambio más reciente**, como en el
   resto del Portal (``ganador_editar``).
4. **Republica la Planilla** cuando el Excel cambió (``requerimientos.publicar``):
   lo que el equipo escribe en el Excel llega al Portal y a las demás
   herramientas en esta misma vuelta, sin esperar al procesador (cada 5 minutos).

Las columnas se ubican por su encabezado, nunca por su letra: el 2026-10-27
alguien insertó «Cliente» entre Título y Ubicación, y con las letras fijas de
entonces una fila nueva habría escrito la ubicación en «Cliente».

Una sola vez deja en el Excel la lista de la columna Estado con el estado nuevo
«Cerrado» (2026-11-09), para que también se pueda elegir ahí (operación
``estados`` de ``planilla_excel.ps1``; a la tercera vez que Excel no puede, deja
de intentarlo y queda en el log).

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
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import esquemas
import intercambio
import requerimientos
import ubicacion

AQUI = Path(__file__).resolve().parent
SCRIPT_EXCEL = AQUI / "planilla_excel.ps1"
TABLA = "Proyectos"
TIPO_NUEVO = "nuevo-requerimiento"
TIPO_EDITAR = "editar-requerimiento"
RESPALDOS = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "QUEMPIN" / "respaldos-planilla"
MAX_RESPALDOS = 30
ESTADO = AQUI / "planilla_escritura_estado.json"   # firma de la planilla ya revisada (gitignoreado)

# Lo que se escribe en una fila (clave de requerimientos.COLUMNAS): las fechas aparte, como fecha de Excel.
ESCRIBIBLES = ("estado", "canal", "captador", "evaluador", "titulo", "cliente", "ubicacion", "referencia", "presupuesto",
               "valorOfertado", "valorAdjudicado", "apertura", "cierre")
FECHAS = ("apertura", "cierre")
# Las columnas de la Planilla que el Portal muestra y deja cambiar (2026-10-29): las que el equipo llena de
# verdad. Las demás tenían 45 % o más de casillas vacías o ilegibles y siguen solo en el Excel. Eval. y Cliente
# también, contadas en toda la planilla, pero se llenan en casi toda fila reciente y el usuario las dejó
# (2026-10-30). El esquema editar-requerimiento y el Portal (PQ_COLUMNAS) llevan la misma lista.
EDITABLES = ("estado", "canal", "captador", "evaluador", "titulo", "cliente", "ubicacion", "referencia", "apertura", "cierre")
# Las que el Portal no muestra y sí exporta el Formulador («Exportar a la Planilla», 2026-11-02): el mismo mensaje.
SOLO_FORMULADOR = ("presupuesto", "valorOfertado", "valorAdjudicado")
# Un cambio que llega antes que la fila que lo crea (OneDrive sincroniza los archivos en cualquier orden)
# espera esto antes de rechazarse.
ESPERA_FILA = timedelta(hours=24)
# Ver el docstring: el N° es la fórmula de la Planilla y su columna está protegida (2026-11-06).
FIJAR_N = False
INTENTOS_LISTA = 3


def _es_formula(valor) -> bool:
    return isinstance(valor, str) and valor.startswith("=")


def _clave(titulo, referencia) -> tuple:
    return (requerimientos.normalizar_encabezado(titulo), requerimientos.normalizar_encabezado(referencia))


def _letra(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def columnas_de(encabezados) -> dict[str, dict]:
    """{clave: {"letra", "i" (desde 0), "encabezado"}} de cada columna conocida, por su encabezado."""
    salida = {}
    for i, texto in enumerate(encabezados):
        clave = requerimientos.COLUMNAS.get(requerimientos.normalizar_encabezado(texto))
        if clave and clave not in salida:
            salida[clave] = {"letra": _letra(i + 1), "i": i, "encabezado": str(texto).strip()}
    return salida


def leer_columnas(ruta: Path) -> dict[str, dict]:
    import openpyxl

    libro = openpyxl.load_workbook(ruta, read_only=True)
    try:
        return columnas_de(next(libro[requerimientos.HOJA].iter_rows(max_row=1, values_only=True), ()))
    finally:
        libro.close()


def leer_filas(ruta: Path) -> list[dict]:
    """Cada fila de la hoja con Estado o Título: su fila, si su N° es fórmula,
    el N° que muestra (el valor guardado por Excel), título y referencia."""
    import openpyxl

    formulas = openpyxl.load_workbook(ruta, read_only=True, data_only=False)
    valores = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        hf = formulas[requerimientos.HOJA]
        hv = valores[requerimientos.HOJA]
        col = columnas_de(next(hv.iter_rows(max_row=1, values_only=True), ()))
        ie, it, ir = (col[c]["i"] if c in col else None for c in ("estado", "titulo", "referencia"))
        ancho = max(i for i in (0, ie, it, ir) if i is not None) + 1
        celda = lambda fila, i: fila[i].value if i is not None and i < len(fila) else None
        salida = []
        for n, (ff, fv) in enumerate(zip(hf.iter_rows(min_row=2, max_col=ancho), hv.iter_rows(min_row=2, max_col=ancho)), start=2):
            estado, titulo = celda(fv, ie), celda(fv, it)
            if (estado in (None, "")) and (titulo in (None, "")):
                continue
            salida.append({"fila": n, "formula": _es_formula(ff[0].value), "numero": requerimientos._numero(fv[0].value),
                           "titulo": titulo if isinstance(titulo, str) else ("" if titulo is None else str(titulo)),
                           "referencia": celda(fv, ir)})
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


# Excel interpreta lo que se le escribe como si se tecleara: un texto que empieza con = + - @ sería una fórmula, y
# uno de solo cifras y separadores, un número o una fecha («10-2» pasaría a ser 10 de febrero). Va con apóstrofo, como
# al escribirlo a mano. El «-» solo es la referencia de las filas sin ID, y Excel lo deja como texto.
_PARECE_NUMERO = re.compile(r"[\d\s.,/:\-]+")


def _texto_celda(v):
    if not isinstance(v, str) or v == "-":
        return v
    return "'" + v if v[:1] in ("=", "+", "-", "@") or _PARECE_NUMERO.fullmatch(v) else v


def _celdas(valores: dict, columnas: dict) -> tuple[dict, dict, list, dict]:
    """(valores, fechas, borrar, encabezados) por letra de columna. Un valor None o vacío borra la casilla.
    Una clave sin columna en la planilla no se escribe."""
    por_letra, fechas, borrar, encabezados = {}, {}, [], {}
    for clave, v in valores.items():
        c = columnas.get(clave)
        if clave not in ESCRIBIBLES or not c:
            continue
        encabezados[c["letra"]] = c["encabezado"]
        if v is None or (isinstance(v, str) and not v.strip()):
            borrar.append(c["letra"])
        elif clave in FECHAS:
            # AAAA-MM-DD, o con la hora (el cierre de una licitación): AAAA-MM-DDTHH:MM
            fechas[c["letra"]] = str(v)[:16]
        else:
            por_letra[c["letra"]] = _texto_celda(v.strip() if isinstance(v, str) else v)
    return por_letra, fechas, borrar, encabezados


def fila_de_mensaje(m: dict, formulacion: dict | None, columnas: dict, hoy: date | None = None) -> dict:
    """La operación 'nueva' de un mensaje nuevo-requerimiento. Lo que el
    proyecto tenga al momento de escribir (título, ubicación, ID de
    licitación) manda sobre lo que traía el mensaje: pudo cambiar en esos
    minutos."""
    r = {k: v for k, v in m["requerimiento"].items() if v not in (None, "")}
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
    valores, fechas, _, encabezados = _celdas({k: r[k] for k in ESCRIBIBLES if k in r}, columnas)
    return {"op": "nueva", "numero": int(r["numero"]), "valores": valores, "fechas": fechas, "encabezados": encabezados}


# ── LO QUE SE CAMBIA EN EL PORTAL (editar-requerimiento) ─────────────────────

def _comparable(clave: str, v) -> str:
    if v is None:
        return ""
    # Un monto puede venir como 1190000 (el mensaje) o 1190000.0 (la celda): es el mismo valor
    if clave in SOLO_FORMULADOR and isinstance(v, (int, float)):
        return str(round(v))
    s = str(v).strip()
    return s[:16] if clave in FECHAS else s


def _instante(texto) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.astimezone()


def ganador_editar(m: dict, actual: dict, escritas: dict, modificada: datetime) -> tuple[dict, list[str]]:
    """({campo: valor} que se escribe, detalle) de un editar-requerimiento contra la fila actual.

    Cada casilla que el Portal cambia trae en ``reemplaza`` lo que esa persona veía. Si la Planilla todavía
    lo tiene, se escribe. Si no, alguien la cambió también en el Excel y **manda el cambio más reciente**:
    el del Portal es de ``origen.enviado``; el del Excel, de cuando este módulo escribió esa casilla (si
    la casilla sigue con lo que escribió: ``escritas``) o, si la cambió una persona, de la última vez que
    se guardó el libro (``modificada``)."""
    enviado = _instante(m["origen"]["enviado"])
    numero = m["requerimiento"]["numero"]
    reemplaza = m.get("reemplaza") or {}
    cambios, detalle = {}, []
    for campo, nuevo in m["cambios"].items():
        hoy = actual.get(campo)
        if _comparable(campo, hoy) == _comparable(campo, nuevo):
            continue
        if campo in reemplaza and _comparable(campo, hoy) != _comparable(campo, reemplaza[campo]):
            previa = escritas.get(f"{numero}|{campo}") or {}
            mia = previa and _comparable(campo, previa.get("valor")) == _comparable(campo, hoy)
            cuando_excel = _instante(previa.get("enviado")) if mia else modificada
            if enviado and cuando_excel and cuando_excel > enviado:
                detalle.append(f"{campo}: en la Planilla quedó «{hoy or ''}», escrito después que «{nuevo or ''}» (manda el más reciente).")
                continue
            detalle.append(f"{campo}: «{nuevo or ''}» reemplaza a «{hoy or ''}», escrito antes en la Planilla.")
        cambios[campo] = nuevo
    return cambios, detalle


# ── EXCEL ────────────────────────────────────────────────────────────────────

def respaldar(ruta: Path) -> Path:
    RESPALDOS.mkdir(parents=True, exist_ok=True)
    destino = RESPALDOS / f"{datetime.now():%Y%m%d-%H%M%S} {ruta.name}"
    shutil.copy2(ruta, destino)
    for viejo in sorted(RESPALDOS.glob("*.xlsx"))[:-MAX_RESPALDOS]:
        viejo.unlink(missing_ok=True)
    return destino


def escribir(ruta: Path, operaciones: list[dict], columnas: dict | None = None, limite: int = 600) -> dict:
    """Aplica las operaciones con Excel. {estado, detalle, resultados}."""
    if not operaciones:
        return {"estado": "ok", "detalle": "nada que escribir", "resultados": []}
    respaldar(ruta)
    titulo = (columnas or {}).get("titulo") or {"letra": "F"}
    with tempfile.TemporaryDirectory() as tmp:
        entrada, salida = Path(tmp) / "entrada.json", Path(tmp) / "salida.json"
        entrada.write_text(json.dumps({"ruta": str(ruta), "hoja": requerimientos.HOJA, "tabla": TABLA,
                                       "columnaTitulo": titulo["letra"], "operaciones": operaciones},
                                      ensure_ascii=False), encoding="utf-8")
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


def _guardar_estado(firma: str, escritas: dict, lista: dict | None = None) -> None:
    # Lo escrito desde el Portal: solo lo de los últimos 60 días sirve para decidir quién manda
    limite = (datetime.now().astimezone() - timedelta(days=60)).isoformat()
    escritas = {k: v for k, v in escritas.items() if str(v.get("enviado") or "") >= limite[:10]}
    ESTADO.write_text(json.dumps(dict(lista or {}, firma=firma, escritas=escritas), ensure_ascii=False), encoding="utf-8")


def _publicar(raiz: Path, planilla: Path, avisos: list) -> bool:
    try:
        requerimientos.publicar(raiz, planilla)
        return True
    except Exception as error:  # noqa: BLE001 -- el procesador lo reintenta; queda el aviso
        avisos.append(f"No se republicó la planilla: {error}")
        return False


def vuelta(raiz: Path | None = None, planilla: Path | None = None, simular: bool = False) -> dict:
    raiz = raiz or ubicacion.ubicar_intercambio(AQUI)
    planilla = planilla or ubicacion.ubicar_planilla(AQUI)
    if raiz is None or planilla is None or not Path(planilla).exists():
        return {"activo": False, "detalle": "sin la biblioteca de Formulación en este equipo"}
    planilla = Path(planilla)
    nuevos_m, _ = intercambio.leer_buzon(raiz, destino=requerimientos.DESTINO, tipo=TIPO_NUEVO)
    editar_m, _ = intercambio.leer_buzon(raiz, destino=requerimientos.DESTINO, tipo=TIPO_EDITAR)
    previo = _leer_estado()
    escritas = dict(previo.get("escritas") or {})
    firma = _firma(planilla)
    # La lista de la columna Estado del Excel: una vez, y a la tercera se deja de intentar (queda en el log)
    lista = {k: previo[k] for k in ("listaEstados", "intentosEstados") if k in previo}
    falta_lista = previo.get("listaEstados") != list(requerimientos.ESTADOS) and int(previo.get("intentosEstados") or 0) < INTENTOS_LISTA
    if not nuevos_m and not editar_m and not falta_lista and previo.get("firma") == firma:
        return {"activo": True, "detalle": "sin cambios"}
    modificada = datetime.fromtimestamp(planilla.stat().st_mtime).astimezone()
    cambio_excel = previo.get("firma") != firma

    columnas = leer_columnas(planilla)
    filas = leer_filas(planilla)
    publicados = ((intercambio.leer_publicacion(raiz, requerimientos.PUBLICACION) or {}).get("datos") or {}).get("requerimientos") or []
    ops, avisos = plan_fijar(filas, publicados) if FIJAR_N else ([], [])
    op_lista = None
    if falta_lista and "estado" in columnas:
        c = columnas["estado"]
        op_lista = {"op": "estados", "lista": list(requerimientos.ESTADOS), "letra": c["letra"], "encabezados": {c["letra"]: c["encabezado"]}}
    tomados = numeros_tomados(filas) | {o["numero"] for o in ops}
    # Lo que ya lleva un N° fuera de la planilla: los demás pedidos y las carpetas de proyecto
    reservados = {int(x["requerimiento"]["numero"]) for x in nuevos_m if isinstance((x.get("requerimiento") or {}).get("numero"), int)}
    for p in ((intercambio.leer_publicacion(raiz, "proyectos") or {}).get("datos") or {}).get("proyectos") or []:
        if str(p.get("req") or "").isdigit():
            reservados.add(int(p["req"]))
    archivar = []          # (mensaje, estado, detalle, extra) que no esperan a Excel
    escribir_m = []        # (mensaje, operación, detalle, cambios) que se archivan según lo que diga Excel
    # (N° pedido, título) → operación 'nueva' de esta vuelta: un cambio a esa fila se suma a ella, aunque le haya tocado otro N°
    nuevas: dict = {}
    norma = requerimientos.normalizar_encabezado

    for m in sorted(nuevos_m, key=lambda m: m["origen"]["enviado"]):
        errores = esquemas.validar_mensaje(m)
        if errores:
            archivar.append((m, "rechazado", errores, {}))
            continue
        numero = pedido = int(m["requerimiento"]["numero"])
        detalle = []
        if numero in tomados:
            dueno = next((f["titulo"] for f in filas if f["numero"] == numero), "")
            # ¿Es el mismo proyecto, ya escrito (una vuelta que se cortó después de guardar)?
            if requerimientos.normalizar_encabezado(dueno) == requerimientos.normalizar_encabezado(m["requerimiento"].get("titulo")):
                archivar.append((m, "sin-cambios", [f"El N° {numero} ya está en la planilla con ese título."], {"requerimiento": numero}))
                continue
            if not m.get("numeroLibre"):
                archivar.append((m, "rechazado",
                                 [f"El N° {numero} ya es «{dueno or 'otro requerimiento'}» en la planilla: el proyecto necesita otro N° (lo decide una persona)."],
                                 {"requerimiento": numero}))
                avisos.append(f"N° {numero} pedido por el Formulador ya es «{dueno}».")
                continue
            # Del Portal: nadie usó todavía ese N° fuera de la planilla, así que toma el siguiente libre
            libre = max(tomados | reservados) + 1
            detalle.append(f"El N° {numero} ya lo tenía «{dueno or 'otro requerimiento'}»: quedó con el N° {libre}.")
            numero = libre
        formulacion = None
        uid = (m.get("fuente") or {}).get("uid")
        if uid:
            try:
                formulacion = json.loads((Path(raiz) / "publicado" / "formulador" / f"{uid}.json").read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                formulacion = None
        op = fila_de_mensaje(m, formulacion, columnas)
        op["numero"] = numero
        # El N° lo da la fórmula: uno que ya está en una carpeta y un código tiene que coincidir
        op["exigeNumero"] = not m.get("numeroLibre")
        tomados.add(numero)
        nuevas[(pedido, norma(m["requerimiento"].get("titulo")))] = op
        escribir_m.append((m, op, detalle, {}))
        ops.append(op)

    actuales = None
    ahora = datetime.now().astimezone()
    for m in sorted(editar_m, key=lambda m: m["origen"]["enviado"]):
        errores = esquemas.validar_mensaje(m)
        if errores:
            archivar.append((m, "rechazado", errores, {}))
            continue
        numero = int(m["requerimiento"]["numero"])
        visto = norma(m["requerimiento"].get("titulo"))
        # El cambio a un N° que se crea en esta misma vuelta va en su fila nueva (y se archiva con ella)
        if (numero, visto) in nuevas:
            op_nueva = nuevas[(numero, visto)]
            if "titulo" in m["cambios"]:
                nuevas[(numero, norma(m["cambios"]["titulo"]))] = op_nueva
            valores, fechas, borrar, encabezados = _celdas(m["cambios"], columnas)
            op_nueva["valores"].update(valores)
            op_nueva["fechas"].update(fechas)
            for letra in borrar:
                op_nueva["valores"].pop(letra, None)
                op_nueva["fechas"].pop(letra, None)
            op_nueva["encabezados"].update(encabezados)
            escribir_m.append((m, op_nueva, [f"Escrito junto con la fila nueva del N° {op_nueva['numero']}."], {}))
            continue
        if actuales is None:
            actuales = requerimientos.por_numero(requerimientos.leer_planilla(planilla))
        actual = actuales.get(numero)
        if actual is None:
            enviado = _instante(m["origen"]["enviado"])
            if enviado and ahora - enviado < ESPERA_FILA:
                continue      # su fila puede venir en camino: espera en el buzón
            archivar.append((m, "rechazado", [f"El N° {numero} no está en la planilla."], {"requerimiento": numero}))
            continue
        # La fila que esa persona veía: si dos tomaron el mismo N°, este puede ser ahora el de otro requerimiento
        if visto and visto != norma(actual.get("titulo")):
            archivar.append((m, "rechazado",
                             [f"El N° {numero} ahora es «{actual.get('titulo') or ''}», no «{m['requerimiento']['titulo']}»: "
                              "no se cambió nada. Búscalo en la Planilla y vuelve a hacerlo."], {"requerimiento": numero}))
            continue
        cambios, detalle = ganador_editar(m, actual, escritas, modificada)
        if not cambios:
            estado = "reemplazado" if detalle else "sin-cambios"
            archivar.append((m, estado, detalle or ["La planilla ya muestra lo cambiado."], {"requerimiento": numero}))
            continue
        valores, fechas, borrar, encabezados = _celdas(cambios, columnas)
        op = {"op": "editar", "numero": numero, "titulo": actual.get("titulo") or "", "valores": valores,
              "fechas": fechas, "borrar": borrar, "encabezados": encabezados}
        # Lo que sigue en esta vuelta se decide contra la fila ya cambiada
        actual.update(cambios)
        if "titulo" in cambios:
            op["tituloNuevo"] = cambios["titulo"]
        escribir_m.append((m, op, detalle, cambios))
        ops.append(op)

    if op_lista is not None:
        ops.append(op_lista)
    if simular:
        return {"activo": True, "simulado": True, "operaciones": ops, "avisos": avisos,
                "archivar": [(x[0]["id"], x[1], x[2]) for x in archivar]}
    for m, estado, detalle, extra in archivar:
        intercambio.archivar(raiz, m, estado, detalle, extra=extra or None)

    if not ops:
        _guardar_estado(firma, escritas, lista)
        publicada = _publicar(raiz, planilla, avisos) if cambio_excel else False
        return {"activo": True, "detalle": "N° ya fijos; nada que escribir" + ("; planilla republicada" if publicada else ""),
                "avisos": avisos}
    resultado = escribir(planilla, ops, columnas)
    if resultado.get("estado") != "ok":
        # Lo que ya está en el Excel sí llega al Portal; lo pedido se reintenta en la vuelta siguiente
        if cambio_excel:
            _publicar(raiz, planilla, avisos)
        return {"activo": True, "detalle": f"planilla {resultado.get('estado')}: {resultado.get('detalle')}", "avisos": avisos}
    por_i = {r["i"]: r for r in resultado.get("resultados") or []}
    fijados = sum(1 for i, o in enumerate(ops) if o["op"] == "fijar" and (por_i.get(i) or {}).get("ok"))
    if op_lista is not None:
        if (por_i.get(ops.index(op_lista)) or {}).get("ok"):
            lista = {"listaEstados": op_lista["lista"]}
        else:
            lista = {"intentosEstados": int(previo.get("intentosEstados") or 0) + 1}
    registrados = editados = 0
    for m, op, detalle, cambios in escribir_m:
        r = por_i.get(ops.index(op)) or {}
        if not r.get("ok") and m["tipo"] == TIPO_NUEVO and "le daba el N°" in str(r.get("detalle") or ""):
            # El N° reservado (carpeta y código) no es el que da la fórmula: reintentar no lo arregla
            intercambio.archivar(raiz, m, "rechazado", [f"No se registró: {r['detalle']}. El proyecto ya lleva el N° "
                                                        f"{op['numero']} en su carpeta y su código; lo decide una persona."],
                                 extra={"requerimiento": op["numero"]})
            avisos.append(f"N° {op['numero']}: {r['detalle']}.")
            continue
        if not r.get("ok"):
            avisos.append(f"N° {op['numero']}: {r.get('detalle') or 'no se escribió'} (se reintenta).")
            continue
        real = r.get("numero")
        if op["op"] == "nueva" and isinstance(real, (int, float)) and int(real) != op["numero"]:
            # La fórmula le dio otro N° (solo pasa con numeroLibre: si no, el Excel deshace la fila)
            detalle = detalle + [f"La fórmula de la Planilla le dio el N° {int(real)} (se pidió el {op['numero']})."]
            op["numero"] = int(real)
        if m["tipo"] == TIPO_NUEVO:
            registrados += 1
            texto = [f"Registrado en la planilla: N° {op['numero']}, fila {r.get('fila')}."] + detalle
        elif op["op"] == "nueva":
            texto = detalle
        else:
            editados += 1
            texto = [f"Cambiado en la planilla: N° {op['numero']}, fila {r.get('fila')}."] + detalle
            for campo, valor in cambios.items():
                escritas[f"{op['numero']}|{campo}"] = {"valor": valor, "enviado": m["origen"]["enviado"]}
        intercambio.archivar(raiz, m, "aplicado", texto, extra={"requerimiento": op["numero"], "fila": r.get("fila")})
    fallidos = [r for r in resultado.get("resultados") or [] if not r.get("ok")]
    _guardar_estado(_firma(planilla) if not fallidos else previo.get("firma") or "", escritas, lista)
    # Las demás herramientas lo ven ya, sin esperar la vuelta del procesador (cada 5 minutos)
    _publicar(raiz, planilla, avisos)
    return {"activo": True, "detalle": f"{fijados} N° fijados, {registrados} requerimiento(s) registrado(s), {editados} cambiado(s)",
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
