# -*- coding: utf-8 -*-
"""
bases_oportunidades.py -- Revisión de las bases de una oportunidad justo antes
del correo de alertas (2026-10-15).

Pedido del usuario: «antes de enviar los correos de alerta de buenas ofertas,
se analicen los anexos buscando las bases técnicas y administrativas y
verifiques los puntos más relevantes, luego de eso envías el correo».

Qué se puede leer y qué no (verificado el 2026-10-15):
- Los **PDF adjuntos** de una licitación (bases administrativas y técnicas)
  solo se bajan desde «Ver adjuntos», que exige reCAPTCHA Enterprise; los de
  una compra ágil, desde buscador.mercadopublico.cl, que rechaza a todo lo
  que no sea un navegador (CloudFront). Ninguna API los entrega: la de
  licitaciones no los nombra, la de Compra Ágil da solo nombre e id, y la
  OCDS no trae documentos (ni las licitaciones recién publicadas). **No se
  intenta saltar esas protecciones**: el correo pide leer esos PDF.
- La **ficha pública** de la licitación sí se lee (sin captcha) y trae el
  «Contenido de las bases» que el comprador llenó en el portal: etapas y
  plazos (con la visita a terreno, que la API no informa: llega como
  1900-01-02), antecedentes que pide la oferta, criterios de evaluación con
  su ponderación, montos y duración, garantías y otras cláusulas (multas,
  sanciones). Una licitación menor a 100 UTM (L1) no trae ese contenido.
- De una compra ágil se vuelve a pedir la ficha a su API: estado, cierre,
  presupuesto, plazo y lugar de entrega, descripción y nombres de adjuntos.

Con eso, cada oportunidad se verifica justo antes del correo (``revisar``):
- **descarta** (no se envía y no se vuelve a revisar): ya no está publicada,
  el cierre cambió y queda menos que ``horasMinimasParaCerrar``, o la visita
  a terreno obligatoria ya pasó.
- **atencion**: visita por agendar, garantías, criterios que pesan
  (experiencia, certificaciones, marca), no permite subcontratar, pago a más
  de 30 días, muchos reclamos por pago, multas, señales del texto (SEC,
  representación de marca, registros...) y lo que la evaluación previa tenía
  distinto (cierre, monto, duración, visita).
- **ok** (confirmado) y **dato** (útil para preparar la oferta).
- Lo que la ficha deja «según bases adjuntas» se cuenta (``remiten``).

SEGURIDAD: solo HTTPS a www.mercadopublico.cl (las redirecciones no pueden
salir del sitio), código validado, tiempo límite y tope de tamaño; una
consulta cada ``pausaSeg``. El HTML es dato no confiable: se lee por id de
elemento, se limpia (``mp._texto``) y se borran correos y teléfonos
(``op._sin_contactos``). No se leen nombres ni contactos de funcionarios
(responsable de pago, de la licitación). El correo escapa todo.

Uso:
    py -3.14 bases_oportunidades.py <código> [<código> ...]   # revisa y muestra, sin enviar ni guardar nada
"""

from __future__ import annotations

import html
import http.client
import json
import re
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import compra_agil as ca  # noqa: E402
import mercado_publico as mp  # noqa: E402
import oportunidades as op  # noqa: E402

TIEMPO_LIMITE_SEG = 40
NIVELES = ("descarta", "atencion", "ok", "dato")      # también es el orden en que se muestran
FUENTE_LICITACION = "la ficha de las bases en Mercado Público"
FUENTE_COMPRA_AGIL = "la ficha de la compra ágil (API de Compra Ágil)"
_ERRORES_RED = (OSError, ValueError, http.client.HTTPException, mp.ErrorMercadoPublico)


class ErrorBases(Exception):
    """La página que llegó no es la ficha que se pidió."""


# ── BAJAR LA FICHA ───────────────────────────────────────────────────────────

class _SoloMercadoPublico(urllib.request.HTTPRedirectHandler):
    """Una redirección solo puede seguir dentro de https://www.mercadopublico.cl."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        partes = urllib.parse.urlsplit(newurl)
        if partes.scheme != "https" or partes.hostname != mp.SITIO:
            raise urllib.error.HTTPError(newurl, code, "redirección fuera de Mercado Público", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _abrir_ficha(url: str, tiempo: float) -> tuple[int, bytes]:
    abridor = urllib.request.build_opener(_SoloMercadoPublico(),
                                          urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    pedido = urllib.request.Request(url, headers={"User-Agent": "QUEMPIN-oportunidades/1", "Accept": "text/html"})
    try:
        with abridor.open(pedido, timeout=tiempo) as r:
            return r.status, r.read(mp.MAX_BYTES_RESPUESTA + 1)
    except urllib.error.HTTPError as error:
        return error.code, b""


def bajar_ficha(codigo: str, abrir=None) -> str:
    """El HTML de la ficha pública de una licitación."""
    mp._exigir_codigo(codigo)
    if ca.es_codigo(codigo):
        raise ValueError(f"{codigo} es una compra ágil: no tiene ficha de licitación")
    estado, cuerpo = (abrir or _abrir_ficha)(mp.FICHA_LICITACION + urllib.parse.quote(codigo), TIEMPO_LIMITE_SEG)
    if estado != 200:
        raise ErrorBases(f"Mercado Público respondió HTTP {estado}")
    if len(cuerpo) > mp.MAX_BYTES_RESPUESTA:
        raise ErrorBases("la ficha es demasiado grande")
    pagina = cuerpo.decode("utf-8", errors="replace")
    if codigo not in pagina:
        raise ErrorBases("la página que llegó no es la ficha de esta licitación")
    return pagina


# ── LEER LA FICHA ────────────────────────────────────────────────────────────

_ELEMENTO = re.compile(r'<(span|a)\b[^>]*\bid="([A-Za-z0-9_]+)"[^>]*>(.*?)</\1>', re.S | re.I)
_VACIOS = {"", "no hay informacion", "sin observaciones", "sin informacion"}


def _limpio(fragmento, largo: int = 300) -> str | None:
    """Texto de un pedazo de HTML: sin etiquetas, sin caracteres de control,
    sin correos ni teléfonos, acortado."""
    texto = re.sub(r"(?i)<br\s*/?>", " ", str(fragmento or ""))
    texto = op._sin_contactos(mp._texto(html.unescape(re.sub(r"<[^>]+>", " ", texto)), 5000))
    texto = mp._texto(texto, largo)
    return None if texto is None or op.normalizar(texto) in _VACIOS else texto


def _elementos(pagina: str) -> dict[str, str]:
    """El HTML interno de cada span/enlace con id: la ficha se lee por id
    (ASP.NET les pone nombres estables), no por posición."""
    salida: dict[str, str] = {}
    for m in _ELEMENTO.finditer(pagina):
        salida.setdefault(m.group(2), m.group(3))
    return salida


def _grilla(ids: dict, grilla: str, campos: dict[str, str]) -> list[dict]:
    """Las filas de una grilla (grvX_ctl02_campo, grvX_ctl03_campo...), en orden."""
    filas: dict[int, dict] = {}
    for clave, valor in ids.items():
        m = re.match(rf"^{grilla}_ctl(\d+)_(\w+)$", clave)
        if m and m.group(2) in campos:
            filas.setdefault(int(m.group(1)), {})[campos[m.group(2)]] = valor
    return [filas[k] for k in sorted(filas)]


_FECHA = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")


def _fecha(texto) -> str | None:
    """«19-10-2026 9:00:00» -> «2026-10-19T09:00» (sin hora, a las 23:59)."""
    m = _FECHA.search(texto or "")
    if not m:
        return None
    d, mes, a, h, mi = m.groups()
    try:
        return datetime(int(a), int(mes), int(d), int(h or 23), int(mi or 59)).isoformat(timespec="minutes")
    except ValueError:
        return None


def _numero(texto) -> float | None:
    """«17421600», «1.800.000», «12,5%» -> número."""
    t = re.sub(r"[^\d,.]", "", texto or "")
    if not re.search(r"\d", t):
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or re.search(r"\.\d{3}$", t):
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def leer_ficha(pagina: str) -> dict:
    """Lo que importa de la ficha de una licitación, ya limpio."""
    ids = _elementos(pagina)

    def t(clave, largo=300):
        return _limpio(ids.get(clave), largo)

    anexos = {}
    for tipo, grilla in (("administrativos", "grvAdministrativo"), ("tecnicos", "grvTecnico"), ("economicos", "grvEconomico")):
        filas = _grilla(ids, grilla, {"lblDescripcion": "descripcion"})
        anexos[tipo] = [x for x in (_limpio(f.get("descripcion"), 90) for f in filas) if x]
    criterios = []
    for f in _grilla(ids, "grvCriterios", {"lblNombreCriterio": "nombre", "lblPonderacion": "ponderacion",
                                            "lblObservaciones": "detalle"}):
        nombre = _limpio(f.get("nombre"), 90)
        if nombre:
            criterios.append({"nombre": nombre, "ponderacion": _numero(_limpio(f.get("ponderacion"), 20)),
                              "detalle": _limpio(f.get("detalle"), 400)})
    garantias = []
    for f in _grilla(ids, "grvGarantias", {"lblFicha8TituloTipoGarantia": "tipo", "lblFicha8Monto": "monto",
                                            "lblFicha8TipoMoneda": "unidad", "lblFicha8FechaVencimiento": "vencimiento",
                                            "lblFicha8Descripcion": "descripcion"}):
        garantias.append({"tipo": _limpio(f.get("tipo"), 80), "monto": _numero(_limpio(f.get("monto"), 30)),
                          "unidad": _limpio(f.get("unidad"), 30), "vencimiento": _limpio(f.get("vencimiento"), 20),
                          "descripcion": _limpio(f.get("descripcion"), 400)})
    clausulas = [{"titulo": _limpio(f.get("titulo"), 120), "texto": _limpio(f.get("texto"), 600)}
                 for f in _grilla(ids, "grvRequerimientosTecnicos", {"lblTitulo": "titulo", "lblDescripcion": "texto"})]
    fechas = [{"texto": _limpio(f.get("texto"), 160), "fecha": _fecha(_limpio(f.get("fecha"), 40))}
              for f in _grilla(ids, "grvFechasUsuario", {"lblFicha3TituloFechaUsuario": "texto",
                                                         "lblFicha3FechaUsuario": "fecha"})]
    return {
        "estado": t("lblFicha1Estado", 60),
        "tipo": t("lblFicha1Tipo", 160),
        "cierre": _fecha(t("lblFicha3Cierre", 40) or t("lblCierre", 40)),
        "preguntasHasta": _fecha(t("lblFicha3Fin", 40)),
        "fechasComprador": [f for f in fechas if f["texto"] or f["fecha"]],
        "comuna": t("lblFicha2Comuna", 80),
        "region": t("lblFicha2Region", 80),
        "reclamosPago": op._entero(t("lblFicha2Reclamo", 12)),
        "monto": _numero(t("lblFicha7MontoEstimado", 40)),
        "estimacion": t("lblFicha7Estimacion", 80),
        "observaciones": t("lblFicha7Observacion", 400),
        "justificacionMonto": t("lblFicha7JustificacionMontoEstimado", 300),
        "duracion": t("lblFicha7TiempoContrato", 40),
        "renovacion": t("lblFicha7ContratoRenovacion", 20),
        "plazoPago": t("lblFicha7Plazos", 160),
        "subcontratacion": t("lblFicha7Subcontratacion", 300),
        "anexos": anexos,
        "criterios": criterios,
        "garantias": garantias,
        "clausulas": [c for c in clausulas if c["titulo"]],
        # Una L1 (menos de 100 UTM) tiene una ficha corta, sin «Contenido de las bases».
        "contenidoBases": "lblFicha1Estado" in ids or bool(criterios) or bool(garantias),
    }


# ── VERIFICAR ────────────────────────────────────────────────────────────────

_REMITE = re.compile(r"\b(segun|conforme|acuerdo|revisar|ver|establecido|indicado)\b.*"
                     r"\b(bases?|bae|bag|anexos?|resolucion|numeral|punto|adjunt[oa]s?)\b")
_VISITA = re.compile(r"\b(visita|visitas|terreno|recorrido|inspeccion)\b")
_PRECIO = re.compile(r"\b(precio|economic[oa]|oferta economica|valor|costo)\b")
_EXPERIENCIA = re.compile(r"\bexperiencia\b")
_CERTIFICA = re.compile(r"\b(certificacion\w*|certificad\w*|sec|marca|iso|acreditacion\w*|autorizad\w*)\b")
_MULTA = re.compile(r"\b(multas?|sancion\w*)\b")
_SIN_TITULO_VISITA = re.compile(r"^\s*visitas?\s+(?:a\s+|en\s+|de\s+)?(?:terreno|t[eé]cnica)\s*[:,.\-]*\s*", re.I)


def remite(texto) -> bool:
    """El texto solo manda a las bases adjuntas («SEGÚN BASES ADJUNTAS»,
    «Conforme numeral 4 del Anexo N°1»): el contenido está en el PDF."""
    n = op.normalizar(texto)
    return bool(n) and len(n) <= 160 and bool(_REMITE.search(n))


def _obligatoria(texto) -> bool | None:
    n = op.normalizar(texto)
    if re.search(r"\bno (es )?obligatori|voluntari|optativ|opcional|no excluyente", n):
        return False
    if re.search(r"obligatori|excluyente", n):
        return True
    return None


# Fechas del comprador que no son una visita aunque una cláusula hable de ella.
_OTRA_FECHA = re.compile(r"\b(firma|contrato|evaluacion|adjudicacion|apertura|consultas?|preguntas?|respuestas?"
                         r"|aclaracion\w*|garantias?|inicio|entrega)\b")


def visitas_de_la_ficha(f: dict) -> dict:
    """La visita a terreno según la ficha de las bases (la API no la informa:
    llega como 1900-01-02). Es visita una fecha del comprador que la nombra
    («VISITA TÉCNICA», «Visita a terreno opcional en ...»), o cualquiera que
    no sea otro hito (firma, adjudicación...) si un criterio o una cláusula
    trata de la visita: hay bases que ponen una fecha por recinto («Línea N° 1,
    ...»). Cada visita lleva si es obligatoria (su texto o, si no lo dice,
    el de la cláusula)."""
    criterios = [c for c in f["criterios"] if _VISITA.search(op.normalizar(c["nombre"]))]
    clausulas = [c for c in f["clausulas"] if _VISITA.search(op.normalizar(c["titulo"]))]
    nombrada = bool(criterios or clausulas)
    visitas, otras = [], []
    for x in f["fechasComprador"]:
        n = op.normalizar(x.get("texto"))
        es_visita = bool(x.get("fecha")) and (bool(_VISITA.search(n)) or (nombrada and not _OTRA_FECHA.search(n)))
        (visitas if es_visita else otras).append(x)
    general = next((v for v in (_obligatoria(c["texto"]) for c in clausulas) if v is not None), None)
    for v in visitas:
        v["obligatoria"] = _obligatoria(v["texto"])
        if v["obligatoria"] is None:
            v["obligatoria"] = general
    return {"visitas": visitas, "otras": otras, "criterios": criterios, "nombrada": nombrada}


def _lugar_visita(texto) -> str | None:
    """«VISITA A TERRENO VOLUNTARIA: Santa Isabel 1240» -> lo que sigue al
    título, si dice algo más que «obligatoria»."""
    resto = _SIN_TITULO_VISITA.sub("", texto or "")
    return mp._texto(resto, 120) if len(op.normalizar(resto).split()) > 2 else None


def resumen_visita(f: dict) -> dict:
    """Lo que la evaluación previa guarda de la visita (``visitaBases`` de la
    ficha en la caché de oportunidades.py)."""
    v = visitas_de_la_ficha(f)
    return {"fechas": sorted(({"fecha": x["fecha"], "obligatoria": x["obligatoria"], "lugar": _lugar_visita(x["texto"])}
                              for x in v["visitas"]), key=lambda x: x["fecha"]),
            "nombrada": v["nombrada"], "daPuntaje": bool(v["criterios"]), "contenidoBases": bool(f.get("contenidoBases"))}


def _horas(cierre, ahora: datetime) -> float | None:
    try:
        f = datetime.fromisoformat(cierre if len(cierre) > 10 else cierre + "T23:59")
    except (TypeError, ValueError):
        return None
    return (f - ahora).total_seconds() / 3600


def _dmy(iso) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d-%m-%Y %H:%M")
    except (TypeError, ValueError):
        return str(iso or "sin fecha")


def _cuando(iso, ahora: datetime) -> str:
    dias = (datetime.fromisoformat(iso).date() - ahora.date()).days
    return "hoy" if dias == 0 else "mañana" if dias == 1 else f"en {dias} días"


def _pesos(valor) -> str:
    return "$" + f"{round(valor):,}".replace(",", ".")


def _monto_garantia(g: dict) -> str:
    if g.get("monto") is None:
        return "monto en las bases"
    unidad = op.normalizar(g.get("unidad"))
    n = f"{g['monto']:g}".replace(".", ",")
    if unidad in ("", "%") or "porcentaje" in unidad:
        return f"{n} %"
    if "peso" in unidad:
        return _pesos(g["monto"])
    if "fomento" in unidad or unidad == "uf":
        return f"{n} UF"
    return f"{n} {g.get('unidad')}"


def _meses(texto) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mes|d[ií]a|a[nñ]o|semana|hora)", texto or "", re.I)
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    unidad = op.normalizar(m.group(2))
    return n * {"mes": 1, "dia": 1 / 30, "ano": 12, "semana": 7 / 30, "hora": 1 / 720}.get(unidad, 1)


def _texto_meses(meses: float) -> str:
    return f"{meses:.0f} meses" if meses >= 1 else f"{round(meses * 30)} días"


def _plano(texto: str) -> str:
    """El texto en minúsculas y sin tildes, del mismo largo que el original
    (para citar el pedazo del texto donde se encontró algo)."""
    salida = []
    for c in texto:
        d = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode().lower()
        salida.append(d[0] if d and d[0].isalnum() else " ")
    return "".join(salida)


def _buscar(texto: str, frase: str) -> tuple[int, int] | None:
    palabras = op.normalizar(frase).split()
    if not texto or not palabras:
        return None
    m = re.search(r"\b" + r"\s+".join(map(re.escape, palabras)) + r"\b", _plano(texto))
    return (m.start(), m.end()) if m else None


def _cita(texto: str, inicio: int, fin: int, margen: int = 70) -> str:
    a, b = max(0, inicio - margen), min(len(texto), fin + margen)
    return ("…" if a else "") + texto[a:b].strip() + ("…" if b < len(texto) else "")


def _senales(textos: list[tuple[str, str]], reglas_bases: dict, omitir: set[str]) -> list[dict]:
    """Requisitos que suelen pesar (SEC, marca, experiencia mínima,
    registros, seguros, ISO...), buscados en los textos que se leyeron."""
    puntos = []
    for senal in reglas_bases.get("senales") or []:
        if senal.get("clave") in omitir:
            continue
        for donde, texto in textos:
            lugar = next((p for p in (_buscar(texto, f) for f in senal.get("frases") or []) if p), None)
            if lugar:
                puntos.append({"nivel": "atencion",
                               "texto": f"Menciona {senal['tema']} ({donde}): «{_cita(texto, *lugar)}»"})
                break
    return puntos


def _verificar_cierre(cierre, o: dict, ahora: datetime, minimas: float, puntos: list, correcciones: dict) -> str | None:
    if not cierre:
        return None
    h = _horas(cierre, ahora)
    if h is not None and h < minimas:
        return f"cierra el {_dmy(cierre)}: quedan {max(h, 0):.0f} horas y hacen falta {minimas:g} para ofertar"
    if o.get("cierre") and cierre[:16] != str(o["cierre"])[:16]:
        puntos.append({"nivel": "atencion", "texto": f"El cierre cambió: ahora es el {_dmy(cierre)} (la evaluación tenía el {_dmy(o['cierre'])})"})
        correcciones["cierre"] = cierre
    else:
        puntos.append({"nivel": "ok", "texto": f"Cierre confirmado: {_dmy(cierre)}"})
    return None


def _verificar_monto(monto, base: str, o: dict, puntos: list, correcciones: dict) -> None:
    if not monto:
        return
    evaluado = o.get("monto") or {}
    valor, fuente = evaluado.get("valor"), str(evaluado.get("fuente") or "")
    if not valor or fuente.startswith("por tipo"):
        puntos.append({"nivel": "atencion", "texto": f"Monto publicado: {_pesos(monto)} ({base}); la evaluación lo había estimado"})
        correcciones["monto"] = f"{_pesos(monto)} ({base})"
    elif abs(monto - valor) / valor > 0.05:
        puntos.append({"nivel": "atencion", "texto": f"Monto publicado: {_pesos(monto)} ({base}); la evaluación usó {_pesos(valor)}"})
        correcciones["monto"] = f"{_pesos(monto)} ({base})"
    else:
        puntos.append({"nivel": "ok", "texto": f"Monto confirmado: {_pesos(monto)} ({base})"})


def verificar_licitacion(o: dict, f: dict, ahora: datetime, reglas: dict) -> dict:
    """Los puntos más relevantes de la ficha de las bases, comparados con la
    evaluación previa ``o``."""
    rb = reglas.get("revisionBases") or {}
    puntos: list[dict] = []
    correcciones: dict = {}
    descarta = None

    if f.get("estado") and op.normalizar(f["estado"]) != "publicada":
        descarta = f"ya no está publicada (estado: {f['estado']})"
    descarta = _verificar_cierre(f.get("cierre"), o, ahora, reglas["horasMinimasParaCerrar"]["licitacion"],
                                 puntos, correcciones) or descarta
    if not f.get("contenidoBases"):
        puntos.append({"nivel": "atencion", "texto": "La ficha no trae el contenido de las bases (licitación menor a 100 UTM): "
                                                     "plazos, requisitos y garantías están solo en los adjuntos"})

    # Visita a terreno: la API no la informa; está en las fechas que define el comprador.
    vis = visitas_de_la_ficha(f)
    visitas, otras, criterios_visita, hay_visita = vis["visitas"], vis["otras"], vis["criterios"], vis["nombrada"]
    ahora_iso = ahora.isoformat(timespec="minutes")
    futuras = sorted((v for v in visitas if v["fecha"] > ahora_iso), key=lambda v: v["fecha"])
    pasadas = [v for v in visitas if v["fecha"] <= ahora_iso]
    sin_registro = not (o.get("visita") or {}).get("fecha")
    if visitas and not futuras and any(v["obligatoria"] for v in pasadas):
        descarta = descarta or f"la visita a terreno obligatoria fue el {_dmy(max(v['fecha'] for v in pasadas))}: ya pasó"
    for v in futuras[:3]:
        tipo = " obligatoria" if v["obligatoria"] else " voluntaria" if v["obligatoria"] is False else ""
        lugar = f": {_lugar_visita(v['texto'])}" if _lugar_visita(v["texto"]) else ""
        duda = "; revisa en las bases si es obligatoria" if v["obligatoria"] is None else ""
        puntos.append({"nivel": "atencion", "texto": f"Visita a terreno{tipo} el {_dmy(v['fecha'])} ({_cuando(v['fecha'], ahora)}){lugar}{duda}"
                                                     + (" — la evaluación previa no la tenía" if sin_registro else "")})
    if len(futuras) > 3:
        puntos.append({"nivel": "dato", "texto": f"Hay {len(futuras) - 3} visitas más en la ficha"})
    for v in ([] if descarta else pasadas[-2:]):
        if v["obligatoria"] is False:
            puntos.append({"nivel": "dato", "texto": f"La visita voluntaria fue el {_dmy(v['fecha'])} (ya pasó)"})
        else:
            puntos.append({"nivel": "atencion", "texto": f"Hubo visita a terreno el {_dmy(v['fecha'])} (ya pasó): "
                                                         + ("era obligatoria; confirma que no te deja fuera" if v["obligatoria"]
                                                            else "confirma en las bases que no era obligatoria")})
    for c in criterios_visita:
        puntos.append({"nivel": "atencion", "texto": f"La visita da puntaje: «{c['nombre']}» pesa {c['ponderacion'] or 0:g} %"})
    if not visitas and hay_visita:
        puntos.append({"nivel": "atencion", "texto": "Las bases nombran una visita a terreno sin fecha en la ficha: búscala en el PDF"})
    elif not visitas and f.get("contenidoBases"):
        puntos.append({"nivel": "ok", "texto": "Sin visita a terreno en la ficha de las bases"})
    if visitas:
        v = futuras[0] if futuras else max(pasadas, key=lambda x: x["fecha"])
        tipo = "Sí, obligatoria" if v["obligatoria"] else "Voluntaria" if v["obligatoria"] is False else "Sí"
        correcciones["visita"] = f"{tipo}: {_dmy(v['fecha'])}" + ("" if futuras else " (ya pasó)") + " · según las bases"
    for x in otras[:2]:
        puntos.append({"nivel": "dato", "texto": f"Fecha del comprador: {x['texto'] or 'sin nombre'}" + (f" — {_dmy(x['fecha'])}" if x["fecha"] else "")})

    _verificar_monto(f.get("monto"), (f.get("estimacion") or "monto estimado").lower(), o, puntos, correcciones)
    if f.get("observaciones") and not remite(f["observaciones"]):
        puntos.append({"nivel": "dato", "texto": f"Observación del monto: {f['observaciones']}"})

    meses = _meses(f.get("duracion"))
    if meses:
        evaluado = o.get("duracionMeses")
        renovable = ", con renovación" if op.normalizar(f.get("renovacion")).startswith("si") else ""
        if evaluado and abs(meses - evaluado) / max(evaluado, 0.1) > 0.1:
            puntos.append({"nivel": "atencion", "texto": f"El contrato dura {_texto_meses(meses)}{renovable} (la evaluación usó {_texto_meses(evaluado)})"})
        else:
            puntos.append({"nivel": "dato", "texto": f"Contrato de {_texto_meses(meses)}{renovable}"})

    # Garantías: hay que tomarlas (y pagarlas) antes de ofertar o de firmar.
    for g in f["garantias"]:
        tipo = op.normalizar(g.get("tipo"))
        vence = f", vigente hasta el {g['vencimiento']}" if g.get("vencimiento") else ""
        monto = _monto_garantia(g)
        if "seriedad" in tipo:
            proporcion = ""
            if g.get("monto") and "peso" in op.normalizar(g.get("unidad")) and f.get("monto"):
                proporcion = f" (≈ {100 * g['monto'] / f['monto']:.1f} % del monto)".replace(".", ",")
            puntos.append({"nivel": "atencion", "texto": f"Garantía de seriedad de la oferta: {monto}{proporcion}{vence}. Hay que tomarla antes del cierre"})
        elif "fiel" in tipo or "cumplimiento" in tipo:
            alto = g.get("monto") and monto.endswith("%") and g["monto"] > rb.get("fielCumplimientoAlto", 10)
            equivale = f" (≈ {_pesos(g['monto'] / 100 * f['monto'])})" if g.get("monto") and monto.endswith("%") and f.get("monto") else ""
            puntos.append({"nivel": "atencion" if alto else "dato", "texto": f"Garantía de fiel cumplimiento: {monto}{equivale}{vence}"})
        else:
            detalle = f": {mp._texto(g['descripcion'], 160)}" if g.get("descripcion") and not remite(g["descripcion"]) else ""
            puntos.append({"nivel": "atencion", "texto": f"{g.get('tipo') or 'Otra garantía'}: {monto}{vence}{detalle}"})
    if not f["garantias"] and f.get("contenidoBases"):
        puntos.append({"nivel": "ok", "texto": "No pide garantías en la ficha"})

    # Criterios de evaluación: cuánto pesa el precio y qué más da puntaje.
    cubiertas: set[str] = set()
    criterios = sorted((c for c in f["criterios"] if c.get("ponderacion") is not None), key=lambda c: -c["ponderacion"])
    if criterios:
        puntos.append({"nivel": "dato", "texto": "Criterios de evaluación: " + ", ".join(f"{c['nombre']} {c['ponderacion']:g} %" for c in criterios[:7])
                                                 + (f" y {len(criterios) - 7} más" if len(criterios) > 7 else "")})
        precio = sum(c["ponderacion"] for c in criterios if _PRECIO.search(op.normalizar(c["nombre"])))
        if precio and precio < rb.get("precioPesaPoco", 40):
            puntos.append({"nivel": "atencion", "texto": f"El precio pesa solo {precio:g} %: lo técnico define la adjudicación"})
        for c in criterios:
            nombre = op.normalizar(c["nombre"])
            if _EXPERIENCIA.search(nombre) and c["ponderacion"] >= rb.get("experienciaPesaMucho", 25):
                puntos.append({"nivel": "atencion", "texto": f"La experiencia pesa {c['ponderacion']:g} %: prepara certificados de contratos parecidos"})
            elif _CERTIFICA.search(nombre) and not _VISITA.search(nombre):
                puntos.append({"nivel": "atencion", "texto": f"Da puntaje «{c['nombre']}» ({c['ponderacion']:g} %)"})
                # Lo que ya salió como criterio no se repite como señal del texto.
                cubiertas.update(clave for clave, patron in (("sec", r"\bsec\b"), ("marca", r"\bmarca\b"), ("iso", r"\biso\b"))
                                 if re.search(patron, nombre))

    dias_pago = re.search(r"(\d+)\s*d[ií]as", f.get("plazoPago") or "")
    if dias_pago and int(dias_pago.group(1)) > rb.get("plazoPagoMaxDias", 30):
        puntos.append({"nivel": "atencion", "texto": f"Paga a {dias_pago.group(1)} días: {f['plazoPago']}"})
    if f.get("reclamosPago") is not None and f["reclamosPago"] >= rb.get("reclamosPagoAltos", 50):
        puntos.append({"nivel": "atencion", "texto": f"El comprador acumula {f['reclamosPago']} reclamos por pagar fuera de plazo en 12 meses"})
    if op.normalizar(f.get("subcontratacion")).startswith("no permite"):
        puntos.append({"nivel": "atencion", "texto": "No permite subcontratar: todo el servicio con personal propio"})

    multa = next((c for c in f["clausulas"] if _MULTA.search(op.normalizar(c["titulo"]))), None)
    if multa:
        detalle = f": {mp._texto(multa['texto'], 180)}" if multa.get("texto") and not remite(multa["texto"]) else " (el detalle está en las bases adjuntas)"
        puntos.append({"nivel": "atencion", "texto": f"Tiene multas y sanciones{detalle}"})

    # Sin repetidos ni los que solo dicen «conforme a las bases».
    documentos = list(dict.fromkeys(x for tipo in ("administrativos", "tecnicos", "economicos") for x in f["anexos"][tipo]))
    nombrados = [x for x in documentos if not remite(x)]
    if nombrados:
        puntos.append({"nivel": "dato", "texto": f"Pide {len(nombrados)} documento{'s' if len(nombrados) > 1 else ''} para ofertar: "
                                                 + "; ".join(nombrados[:4]) + (f" y {len(nombrados) - 4} más" if len(nombrados) > 4 else "")})
    elif documentos:
        puntos.append({"nivel": "dato", "texto": "Los documentos que pide la oferta están detallados en las bases adjuntas"})
    if f.get("preguntasHasta") and f["preguntasHasta"] > ahora_iso:
        puntos.append({"nivel": "dato", "texto": f"Preguntas al comprador hasta el {_dmy(f['preguntasHasta'])}"})

    textos = ([("criterios", f"{c['nombre']}: {c.get('detalle') or ''}") for c in f["criterios"]]
              + [("cláusulas", f"{c['titulo']}: {c.get('texto') or ''}") for c in f["clausulas"]]
              + [("garantías", g["descripcion"]) for g in f["garantias"] if g.get("descripcion")]
              + [("documentos que pide", x) for x in documentos]
              + [("descripción", o.get("descripcion") or ""), ("observaciones", f.get("observaciones") or "")])
    omitir = {"visita"} | cubiertas | ({"garantia"} if f["garantias"] else set()) | ({"multas"} if multa else set())
    puntos += _senales(textos, rb, omitir)

    remiten = sum(1 for x in ([c.get("detalle") for c in f["criterios"]] + [g.get("descripcion") for g in f["garantias"]]
                              + [c.get("texto") for c in f["clausulas"]] + [f.get("observaciones"), f.get("justificacionMonto")])
                  if x and remite(x))
    return {"puntos": puntos, "descarta": descarta, "correcciones": correcciones, "remiten": remiten}


def verificar_compra_agil(o: dict, crudo: dict, ahora: datetime, reglas: dict) -> dict:
    """Lo mismo para una compra ágil, con la ficha recién pedida a su API."""
    def dic(x):
        return x if isinstance(x, dict) else {}
    rb = reglas.get("revisionBases") or {}
    puntos: list[dict] = []
    correcciones: dict = {}
    descarta = None
    estado = dic(crudo.get("estado"))
    if mp._texto(estado.get("codigo"), 30) not in (None, "publicada"):
        descarta = f"ya no está publicada ({mp._texto(estado.get('glosa'), 60) or estado.get('codigo')})"
    descarta = _verificar_cierre(ca.fecha(dic(crudo.get("fechas")).get("fecha_cierre")), o, ahora,
                                 reglas["horasMinimasParaCerrar"]["compraAgil"], puntos, correcciones) or descarta
    if dic(crudo.get("convocatoria")).get("estado_convocatoria") == 2:
        puntos.append({"nivel": "dato", "texto": "Está en segundo llamado"})
    presupuesto = dic(crudo.get("presupuesto"))
    monto = mp._numero(presupuesto.get("monto_disponible_clp")) or mp._numero(presupuesto.get("presupuesto_estimado"))
    _verificar_monto(monto if monto and monto > 0 else None, "disponible", o, puntos, correcciones)

    entrega = dic(crudo.get("entrega"))
    plazo = entrega.get("plazo_entrega_dias")
    if isinstance(plazo, int) and not isinstance(plazo, bool) and plazo > 0:
        puntos.append({"nivel": "dato", "texto": f"Plazo de entrega: {plazo} días"})
    lugar = op._sin_contactos(mp._texto(entrega.get("direccion_entrega"), 160))
    if lugar:
        puntos.append({"nivel": "dato", "texto": f"Lugar de entrega: {lugar}"})

    documentos = [x for x in (mp._texto(d.get("nombre"), 80) for d in crudo.get("documentos") or [] if isinstance(d, dict)) if x]
    if documentos:
        puntos.append({"nivel": "atencion", "texto": f"Trae {len(documentos)} adjunto{'s' if len(documentos) > 1 else ''}: "
                                                     + ", ".join(f"«{x}»" for x in documentos[:4])
                                                     + (f" y {len(documentos) - 4} más" if len(documentos) > 4 else "")
                                                     + ". Léelos en la ficha antes de cotizar"})
    else:
        puntos.append({"nivel": "ok", "texto": "Sin adjuntos: lo que pide está en la descripción"})
    ofertas = dic(crudo.get("resumen")).get("total_ofertas_recibidas")
    if isinstance(ofertas, int) and not isinstance(ofertas, bool) and ofertas > 0:
        puntos.append({"nivel": "dato", "texto": f"Ya recibió {ofertas} {'cotizaciones' if ofertas > 1 else 'cotización'}"})

    descripcion = op._sin_contactos(mp._texto(crudo.get("descripcion"), 3000)) or ""
    productos = "; ".join(t for p in crudo.get("productos_solicitados") or [] if isinstance(p, dict)
                          for t in (mp._texto(p.get("nombre"), 100), mp._texto(p.get("descripcion"), 300)) if t)
    textos = [("descripción", descripcion), ("productos", op._sin_contactos(productos) or "")]
    visita = next(((d, p) for d, t in textos for p in [_buscar(t, "visita")] if p), None)
    if visita:
        texto = dict(textos)[visita[0]]
        puntos.append({"nivel": "atencion", "texto": f"Pide o menciona una visita: «{_cita(texto, *visita[1])}»"})
        correcciones["visita"] = "La descripción menciona una visita · revisa la ficha"
    acta = next((x for x in documentos if _VISITA.search(op.normalizar(x))), None)
    if acta:
        puntos.append({"nivel": "atencion", "texto": f"Un adjunto trata de la visita a terreno: «{acta}». Revisa si fue obligatoria y si ya pasó"})
        correcciones.setdefault("visita", "Hay un adjunto sobre la visita a terreno · revisa la ficha")
    textos.append(("nombres de los adjuntos", "; ".join(documentos)))
    puntos += _senales(textos, rb, {"visita"})
    return {"puntos": puntos, "descarta": descarta, "correcciones": correcciones, "remiten": 0}


# ── REVISAR (lo que llama el correo) ─────────────────────────────────────────

_ultima_consulta = {"t": None}


def _esperar_turno(pausa: float, dormir, reloj=time.monotonic) -> None:
    if _ultima_consulta["t"] is not None:
        falta = pausa - (reloj() - _ultima_consulta["t"])
        if falta > 0:
            dormir(falta)
    _ultima_consulta["t"] = reloj()


def revisar(o: dict, ahora: datetime, config: dict, abrir=None, cliente_ca=None, dormir=time.sleep) -> dict:
    """Revisa las bases de una oportunidad. Nunca lanza por un problema de
    red: devuelve ``ok`` False con el motivo, y quien llama decide si espera."""
    reglas = config["alertas"]
    codigo = str(o.get("codigo") or "")
    base = {"codigo": codigo, "revisado": ahora.isoformat(timespec="minutes"), "puntos": [], "descarta": None,
            "correcciones": {}, "remiten": 0}
    _esperar_turno(float((reglas.get("revisionBases") or {}).get("pausaSeg", 3)), dormir)
    cliente = None
    try:
        if ca.es_codigo(codigo):
            cliente = cliente_ca or ca.Cliente(mp.leer_ticket(), limite_seg=120)
            crudo = cliente.detalle(codigo)
            if crudo is None:
                return dict(base, ok=True, fuente=FUENTE_COMPRA_AGIL, descarta="Mercado Público ya no la muestra (no existe o dejó de ser pública)")
            return dict(base, ok=True, fuente=FUENTE_COMPRA_AGIL, **verificar_compra_agil(o, crudo, ahora, reglas))
        ficha = leer_ficha(bajar_ficha(codigo, abrir))
        return dict(base, ok=True, fuente=FUENTE_LICITACION, **verificar_licitacion(o, ficha, ahora, reglas))
    except (ErrorBases, *_ERRORES_RED) as error:
        texto = cliente.censurar(error) if cliente else str(error)
        return dict(base, ok=False, error=mp._texto(f"{type(error).__name__}: {texto}", 200))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except AttributeError:
        pass
    if not argv:
        print(__doc__.split("Uso:")[1])
        return 2
    try:
        datos = json.loads((AQUI / "Visualizador Web" / "data" / "oportunidades.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    evaluadas = {o.get("codigo"): o for o in datos.get("oportunidades") or []}
    config, ahora = op.cargar_config(), datetime.now()
    for codigo in argv:
        o = evaluadas.get(codigo) or {"codigo": codigo}
        r = revisar(o, ahora, config)
        print(f"\n{codigo}  {(o.get('nombre') or '')[:70]}")
        if not r["ok"]:
            print(f"  [ERROR] no se pudo revisar: {r['error']}")
            continue
        if r["descarta"]:
            print(f"  [DESCARTA] {r['descarta']}")
        for p in sorted(r["puntos"], key=lambda p: NIVELES.index(p["nivel"])):
            print(f"  [{p['nivel'].upper():<8}] {p['texto']}")
        if r["remiten"]:
            print(f"  {r['remiten']} puntos de la ficha remiten a las bases adjuntas (PDF).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
