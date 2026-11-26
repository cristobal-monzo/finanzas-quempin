# -*- coding: utf-8 -*-
"""
formulaciones.py -- El repositorio de presupuestos del Formulador de proyectos,
visto desde Python, para que Claude los resuma y los lleve a otras herramientas.

Pedido del usuario (2026-09-30): «cuando alguien genere un nuevo presupuesto
quiero que se guarde, o que al menos quede un input para que yo, usando
Claude, pueda actualizar». El Formulador (web) guarda cada presupuesto en
``publicado/formulador/<uid>.json`` de la carpeta de intercambio (ver
``js/compartida.js`` en su repo). Cada archivo es un sobre con:

- ``historia``: las versiones anteriores que pasaron por la carpeta;
- ``resumen``: los números que calculó el propio Formulador (costo, precio,
  margen y costos por categoría del Análisis Financiero);
- ``datos``: el proyecto completo.

Este módulo:

- lee el repositorio (``leer_repositorio``);
- incorpora los presupuestos que llegaron **por archivo** al buzón (mensaje
  ``formulacion``, desde navegadores sin acceso a la carpeta), con las mismas
  reglas de quién gana que usa el Formulador (``incorporar_buzon``);
- lleva la cuenta de qué presupuestos ya revisó el usuario con Claude
  (``novedades`` / ``marcar_revisadas``);
- lleva al presupuesto el Estado que cambió en la Planilla de Ingreso
  (``alinear_estados``, paso ``estados-formulador`` del procesador, 2026-11-25).

Nunca calcula precios: eso lo hace el Formulador, porque dos cálculos
terminan divergiendo. Tampoco borra archivos del repositorio.
"""

import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import intercambio

RUTA_REPOSITORIO = (intercambio.CARPETA_PUBLICADO, "formulador")
TIPO_ENTREGA = "formulacion"
DESTINO = "formulador"
# La misma del Formulador (js/compartida.js, MAX_HISTORIA): con menos, una versión escrita aquí corta la historia que la
# fusión automática del Formulador usa para saber de qué versión viene un cambio (2026-11-25; antes 50)
MAX_HISTORIA = 200
# Cómo se dice cada estado en el Formulador (js/store.js, ESTADOS) y en la Planilla de Ingreso. EN_PLANILLA es la misma
# tabla de js/flujo.js del Formulador (tests/test_formulaciones.py la compara si ese repositorio está al lado).
EN_PLANILLA = {"Borrador": "Evaluación", "En revisión": "Evaluación", "Enviada": "Ofertado", "Adjudicada": "Adjudicado",
               "Cerrada": "Cerrado", "Perdida": "No adjudicado", "Descartada": "Descartado"}
AL_FORMULADOR = {"Evaluación": "En revisión", "Ofertado": "Enviada", "Adjudicado": "Adjudicada", "Cerrado": "Cerrada",
                 "No adjudicado": "Perdida", "Descartado": "Descartada"}
FIRMA_PLANILLA = "Planilla de Ingreso"
# El orden de los estados: la Planilla que se pone al día tarde (una sugerencia del Formulador que alguien pasó después)
# no hace retroceder a un presupuesto que ya avanzó solo
ETAPA = {"Evaluación": 0, "Ofertado": 1, "Adjudicado": 2, "No adjudicado": 2, "Descartado": 2, "Cerrado": 3}
ESCRITOS = "_escritos"      # en 'vistos': lo escrito en el repositorio que falta confirmar (OneDrive puede perderlo)
ESPERA_EDICION = timedelta(minutes=10)    # un presupuesto que alguien está editando espera a la vuelta siguiente
_CON_NUMERO = re.compile(r"^\s*(\d{1,5})\s*\.")
# Qué revisó el usuario con Claude: {"revisadas": {uid: modificado}, "fecha": iso}.
# Solo lleva identificadores y fechas, pero se ignora en git igual que los
# demás estados.
RUTA_REVISADAS = Path(__file__).resolve().parent / "formulaciones_revisadas.json"

_CARACTER_INVALIDO = re.compile(r"[^A-Za-z0-9_-]")


def nombre_archivo(uid) -> str:
    """El mismo que usa el Formulador (js/compartida.js)."""
    return _CARACTER_INVALIDO.sub("_", str(uid)) + ".json"


def carpeta_repositorio(raiz: Path) -> Path:
    return Path(raiz).joinpath(*RUTA_REPOSITORIO)


# ── LECTURA ──────────────────────────────────────────────────────────────────

def _item(sobre, ruta: Path) -> dict | None:
    datos = sobre.get("datos") if isinstance(sobre, dict) else None
    if not (isinstance(sobre, dict) and sobre.get("esquema") == intercambio.ESQUEMA
            and sobre.get("tipo") == "proyecto" and isinstance(datos, dict) and datos.get("uid")
            and nombre_archivo(datos["uid"]) == ruta.name):
        return None
    return {
        "uid": str(datos["uid"]),
        "mod": str(datos.get("modificado") or ""),
        "historia": [h for h in (sobre.get("historia") or []) if isinstance(h, str)],
        "resumen": sobre.get("resumen") if isinstance(sobre.get("resumen"), dict) else {},
        "autor": str(sobre.get("autor") or ""),
        "datos": datos,
        "archivo": ruta,
    }


def leer_repositorio(raiz: Path) -> list[dict]:
    """Presupuestos del repositorio. Solo cuenta el archivo con el nombre de
    su uid: las copias que deja OneDrive en un conflicto se ignoran, igual que
    en el Formulador."""
    carpeta = carpeta_repositorio(raiz)
    if not carpeta.is_dir():
        return []
    items = []
    for ruta in sorted(carpeta.glob("*.json")):
        try:
            sobre = intercambio._leer_json(ruta)
        except (OSError, ValueError):
            continue
        item = _item(sobre, ruta)
        if item:
            items.append(item)
    return items


# ── ENTREGAS POR ARCHIVO (mensaje «formulacion» en el buzón) ──────────────────

def validar_entrega(mensaje: dict) -> list[str]:
    datos = mensaje.get("datos")
    if not isinstance(datos, dict):
        return ["falta el presupuesto ('datos')"]
    errores = []
    if not isinstance(datos.get("uid"), str) or not datos["uid"].strip():
        errores.append("el presupuesto no tiene uid")
    if not isinstance(datos.get("modificado"), str):
        errores.append("el presupuesto no tiene fecha de modificación")
    if not isinstance(mensaje.get("historia", []), list):
        errores.append("'historia' debe ser una lista")
    return errores


def decidir_entrega(mensaje: dict, actual: dict | None) -> str:
    """'nuevo' | 'aplicar' | 'sin-cambios' | 'reemplazado' | 'conflicto'.
    Mismas reglas que el Formulador: la entrega reemplaza lo que hay solo si
    viene de esa versión. Si la carpeta ya tiene algo más nuevo que viene de
    la entrega, no se toca. Si cambiaron por separado, la entrega queda como
    copia."""
    mod = str(mensaje["datos"].get("modificado") or "")
    if actual is None:
        return "nuevo"
    if actual["mod"] == mod:
        return "sin-cambios"
    if actual["mod"] in set(mensaje.get("historia") or []):
        return "aplicar"
    if mod in set(actual["historia"]):
        return "reemplazado"
    return "conflicto"


def _escribir(raiz: Path, datos: dict, historia: list, resumen, autor: str) -> Path:
    ruta = carpeta_repositorio(raiz) / nombre_archivo(datos["uid"])
    intercambio._escribir_json_atomico(ruta, {
        "esquema": intercambio.ESQUEMA, "herramienta": "formulador", "tipo": "proyecto",
        "generado": intercambio.ahora_iso(), "autor": autor,
        "historia": [h for h in historia if isinstance(h, str)][-MAX_HISTORIA:],
        "resumen": resumen if isinstance(resumen, dict) else {}, "datos": datos,
    })
    return ruta


def titulo_legible(datos: dict) -> str:
    return f"{datos.get('codigo') or '—'} v{datos.get('version') or 1} «{datos.get('titulo') or 'Sin título'}»"


def incorporar_buzon(raiz: Path) -> list[dict]:
    """Lleva al repositorio los presupuestos entregados por archivo y archiva
    cada mensaje con su resultado. Devuelve [{uid, decision, estado, detalle}]."""
    mensajes, _ = intercambio.leer_buzon(raiz, destino=DESTINO, tipo=TIPO_ENTREGA)
    if not mensajes:
        return []
    actuales = {i["uid"]: i for i in leer_repositorio(raiz)}
    resultados = []
    for m in mensajes:
        errores = validar_entrega(m)
        if errores:
            intercambio.archivar(raiz, m, "rechazado", errores)
            resultados.append({"uid": None, "decision": "rechazado", "estado": "rechazado", "detalle": errores})
            continue
        datos, autor = m["datos"], str(m["origen"].get("usuario") or "")
        uid = datos["uid"]
        decision = decidir_entrega(m, actuales.get(uid))
        if decision in ("nuevo", "aplicar"):
            _escribir(raiz, datos, m.get("historia") or [], m.get("resumen"), autor)
            estado, detalle = "aplicado", [f"{titulo_legible(datos)} quedó en el repositorio de formulaciones."]
        elif decision == "conflicto":
            copia = dict(datos, uid=secrets.token_hex(6),
                         titulo=f"{datos.get('titulo') or 'Presupuesto'} (entregado por archivo)")
            copia.pop("vinculos", None)
            _escribir(raiz, copia, [], m.get("resumen"), autor)
            estado = "aplicado"
            detalle = [f"{titulo_legible(datos)} también cambió en la carpeta: la entrega quedó como copia "
                       f"«{copia['titulo']}» para no perder ningún cambio."]
        elif decision == "sin-cambios":
            estado, detalle = "sin-cambios", [f"{titulo_legible(datos)} ya estaba igual en el repositorio."]
        else:
            estado, detalle = "reemplazado", [f"El repositorio ya tiene una versión más nueva de {titulo_legible(datos)}."]
        intercambio.archivar(raiz, m, estado, detalle, extra={"uid": uid, "decision": decision})
        resultados.append({"uid": uid, "decision": decision, "estado": estado, "detalle": detalle})
        actuales = {i["uid"]: i for i in leer_repositorio(raiz)}
    return resultados


def entregas_en_buzon(raiz: Path) -> list[dict]:
    mensajes, _ = intercambio.leer_buzon(raiz, destino=DESTINO, tipo=TIPO_ENTREGA)
    return mensajes


# ── EL ESTADO QUE VIENE DE LA PLANILLA ───────────────────────────────────────
# Pedido del usuario (2026-11-02, hecho el 2026-11-25): si el Estado cambia en la Planilla o en el Portal, el proyecto
# del Formulador muestra el mismo. Lo que cambia en la Planilla llega al presupuesto con la regla de siempre del
# repositorio: una versión nueva, con la anterior en su historia, que cada navegador se trae.

def _instante(texto) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.astimezone()


def _numero_req(datos: dict) -> int | None:
    v = (datos.get("vinculos") or {}).get("requerimiento")
    texto = str((v.get("numero") if isinstance(v, dict) else v) or "").strip()
    return int(texto) if texto.isdigit() and int(texto) > 0 else None


def _numero_propio(datos: dict) -> int | None:
    """El N° que dicen el nombre de su carpeta de oferta o su código «N°. Nombre»."""
    for nombre in (((datos.get("vinculos") or {}).get("carpetaOferta") or {}).get("nombre"), datos.get("codigo")):
        m = _CON_NUMERO.match(str(nombre or ""))
        if m:
            return int(m.group(1))
    return None


def vigentes_por_req(repositorio: list[dict]) -> dict[int, dict]:
    """El presupuesto que manda en cada N°, con la regla del Portal (rcArmar): la última versión de cada código y,
    entre códigos del mismo N° (un borrador duplicado, por ejemplo), el modificado más recientemente."""
    por_codigo: dict = {}
    for item in repositorio:
        d = item["datos"]
        if d.get("eliminado"):
            continue
        codigo = str(d.get("codigo") or item["uid"])
        version = int(d["version"]) if str(d.get("version") or "").isdigit() else 1
        previo = por_codigo.get(codigo)
        if previo is None or (version, item["mod"]) > previo[0]:
            por_codigo[codigo] = ((version, item["mod"]), item)
    salida: dict[int, dict] = {}
    for _, item in por_codigo.values():
        n = _numero_req(item["datos"])
        if n and (n not in salida or salida[n]["mod"] < item["mod"]):
            salida[n] = item
    return salida


def alinear_estados(raiz: Path, requerimientos: list[dict], vistos: dict | None, omitir=(), ahora: datetime | None = None,
                    simular: bool = False) -> tuple[dict, list[str]]:
    """Lleva al Formulador lo que cambió en la Planilla desde la vuelta anterior. Devuelve (vistos, cambiados).

    Solo lo que cambió: la primera vez (vistos None) y en una fila nueva se anota lo que hay, porque lo que ya estaba
    distinto no se sabe quién lo tiene bien (medido el 2026-11-02: 9 presupuestos, 2 unidos a un N° equivocado).
    'omitir': los N° con un cambio de estado del Formulador que todavía espera en el buzón (una sugerencia que alguien
    no ha decidido): se vuelven a mirar cuando ya no espera. Un presupuesto editado hace menos de ESPERA_EDICION espera
    a la vuelta siguiente, para no cruzarse con quien lo tiene abierto, y uno cuya carpeta o código dicen otro N° no se
    toca: ese vínculo está en duda.

    No retrocede (ETAPA): si el presupuesto ya está más adelante que el estado nuevo de la Planilla y la Planilla no
    estaba con él (se está poniendo al día, por ejemplo con una sugerencia antigua), no se toca. Si estaban iguales y la
    Planilla vuelve atrás (alguien reabrió el proyecto), sí. Lo escrito queda en vistos['_escritos'] hasta verlo en el
    repositorio: si OneDrive lo perdió en un conflicto con una versión anterior, se vuelve a escribir."""
    ahora = ahora or datetime.now().astimezone()
    actuales = {str(r["numero"]): r["estado"] for r in requerimientos
                if isinstance(r.get("numero"), int) and isinstance(r.get("estado"), str) and r.get("estado")}
    if vistos is None:
        return actuales, []
    nuevos, cambiados = dict(vistos), []
    escritos = dict(nuevos.pop(ESCRITOS, None) or {})
    vigentes = None
    if escritos:
        vigentes = vigentes_por_req(leer_repositorio(raiz))
        for n, x in list(escritos.items()):
            item = vigentes.get(int(n))
            mod, sello = (_instante(item["mod"]) if item else None), _instante(x.get("sello"))
            if item is None or sello is None or mod is None or mod >= sello:   # instantes: el Formulador escribe en UTC
                escritos.pop(n)               # quedó, o alguien lo cambió después: manda esa persona
            else:
                nuevos[n] = x.get("antes", "")  # se perdió: esta vuelta lo vuelve a mirar, desde lo que había
                escritos.pop(n)
    cambiaron = {n: e for n, e in actuales.items() if nuevos.get(n) != e and int(n) not in omitir}
    if cambiaron:
        vigentes = vigentes if vigentes is not None else vigentes_por_req(leer_repositorio(raiz))
    for n, estado in cambiaron.items():
        item = vigentes.get(int(n))
        d = item["datos"] if item else {}
        propio = EN_PLANILLA.get(d.get("estado") or "Borrador")
        atrasada = (estado in ETAPA and propio in ETAPA and ETAPA[estado] < ETAPA[propio] and nuevos.get(n) != propio)
        if (n not in vistos or item is None or estado not in AL_FORMULADOR or propio == estado or atrasada
                or _numero_propio(d) not in (None, int(n))):
            nuevos[n] = estado
            continue
        modificado = _instante(item["mod"])
        if modificado and ahora - modificado < ESPERA_EDICION:
            continue
        if not simular:
            sello = ahora.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            _escribir(raiz, dict(d, estado=AL_FORMULADOR[estado], modificado=sello, modificadoPor=FIRMA_PLANILLA),
                      item["historia"] + [item["mod"]], item["resumen"], FIRMA_PLANILLA)
            escritos[n] = {"sello": sello, "estado": estado, "antes": nuevos.get(n, "")}
        nuevos[n] = estado
        cambiados.append(f"{titulo_legible(d)} → {AL_FORMULADOR[estado]}")
    if escritos:
        nuevos[ESCRITOS] = escritos
    return nuevos, cambiados


# ── REVISIÓN CON CLAUDE ──────────────────────────────────────────────────────

def leer_revisadas(ruta: Path | None = None) -> dict:
    """ruta None = RUTA_REVISADAS (leída al llamar: las pruebas la reemplazan)."""
    try:
        datos = intercambio._leer_json(ruta or RUTA_REVISADAS)
    except (OSError, ValueError):
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    if not isinstance(datos.get("revisadas"), dict):
        datos["revisadas"] = {}
    return datos


def novedades(repositorio: list[dict], revisadas: dict) -> dict:
    """{"nuevos": [...], "cambiados": [...]} desde la última revisión."""
    vistas = revisadas.get("revisadas", {})
    nuevos, cambiados = [], []
    for item in repositorio:
        previo = vistas.get(item["uid"])
        if previo is None:
            nuevos.append(item)
        elif previo != item["mod"]:
            cambiados.append(item)
    orden = lambda i: i["mod"]  # noqa: E731
    return {"nuevos": sorted(nuevos, key=orden, reverse=True), "cambiados": sorted(cambiados, key=orden, reverse=True)}


def marcar_revisadas(repositorio: list[dict], ruta: Path | None = None) -> int:
    datos = leer_revisadas(ruta)
    for item in repositorio:
        datos["revisadas"][item["uid"]] = item["mod"]
    datos["fecha"] = intercambio.ahora_iso()
    intercambio._escribir_json_atomico(ruta or RUTA_REVISADAS, datos)
    return len(repositorio)


# ── TEXTO ────────────────────────────────────────────────────────────────────

# Moneda del presupuesto (resumen.moneda del Formulador): pesos enteros; soles, dólares y euros con centavos
_MONEDAS = {"CLP": ("$", 0), "PEN": ("S/ ", 2), "USD": ("US$ ", 2), "EUR": ("€ ", 2)}


def _monto(valor, moneda: str = "CLP") -> str:
    if not isinstance(valor, (int, float)):
        return "—"
    simbolo, dec = _MONEDAS.get(moneda or "CLP", _MONEDAS["CLP"])
    texto = f"{abs(valor):,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return ("-" if round(valor, dec) < 0 else "") + simbolo + texto


def _fecha(iso: str) -> str:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone().strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return str(iso)


def linea(item: dict) -> str:
    """Una línea por presupuesto, para el resumen que lee el usuario."""
    d, r = item["datos"], item["resumen"]
    margen = r.get("margen")
    partes = [
        titulo_legible(d),
        d.get("cliente") or "sin cliente",
        d.get("estado") or "Borrador",
        f"costo {_monto(r.get('costoDirecto'), r.get('moneda'))}",
        f"precio neto {_monto(r.get('precioNeto'), r.get('moneda'))}",
        f"margen {margen * 100:.1f} %".replace(".", ",") if isinstance(margen, (int, float)) else "margen —",
    ]
    if r.get("errores"):
        partes.append(f"{r['errores']} error(es)")
    quien = item["autor"] or d.get("responsable") or ""
    if quien:
        partes.append(f"por {quien}")
    partes.append(f"modificado {_fecha(item['mod'])}")
    if d.get("eliminado"):
        partes.append("EN LA PAPELERA")
    return " · ".join(partes)
