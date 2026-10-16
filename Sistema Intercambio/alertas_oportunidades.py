# -*- coding: utf-8 -*-
"""
alertas_oportunidades.py -- Correo automático cuando aparece una oportunidad
muy buena en Mercado Público (2026-10-14).

Pedido del usuario: «si la nota es muy alta, sobre 85, se envíe un correo
automático [...] con un resumen: monto, tiempo restante, región, si requiere
o no visita técnica, etc. El correo debe ser en casos muy buenos: no quiero
recibir 1 correo al día, máximo 3 correos a la semana, y no deben repetirse
las ofertas que ya fueron enviadas».

Reglas (``alertas`` en oportunidades_config.json):
- Solo licitaciones y compras ágiles con nota **mayor o igual a notaMinima**,
  con ficha completa, que el motor no descarta, que no están ya en la Planilla
  (alguien ya las tomó) y que todavía dan tiempo para ofertar
  (``horasMinimasParaCerrar``, distinto para una compra ágil).
- **Nunca se repite** una oportunidad: lo enviado queda en
  ``oportunidades_estado_correos.json`` (gitignoreado).
- **Como máximo maxCorreosPorSemana correos en 7 días corridos.** Si en una
  vuelta hay varias, van todas juntas en un solo correo. Si ya se llegó al
  tope, esperan: la próxima vuelta las vuelve a mirar si siguen abiertas.
- **Solo en horario laboral** (2026-10-15, pedido del usuario: «nunca debes
  mandar un correo fuera de los días u horarios laborales, siempre de lunes a
  viernes y en horarios entre las 9.00 a las 17.00»): ``alertas.horario`` y
  los feriados nacionales de ``alertas.feriados``. Fuera de horario lo
  elegible **espera**, sin marcarse como enviado: sale en la primera vuelta
  dentro del horario si sigue abierto. Se revisa al decidir y otra vez justo
  antes de entregar el correo a Outlook.
- Los destinatarios están en ``oportunidades_destinatarios.json``, fuera del
  repositorio (que es público): ``{"para": ["nombre@quempin.cl", ...]}``. Sin
  ese archivo no se envía nada.
- **Antes de enviar se revisan las bases** (2026-10-15, pedido del usuario:
  «antes de enviar los correos [...] se analicen los anexos buscando las
  bases técnicas y administrativas y verifiques los puntos más relevantes»):
  ``bases_oportunidades.py`` lee la ficha de las bases de cada candidata y
  el correo lleva lo verificado. Lo que las bases descartan (no publicada,
  cierre muy cerca, visita obligatoria ya pasada) no se envía y queda en
  ``descartadasBases`` del registro: no se vuelve a revisar. Si la ficha no
  responde, la oportunidad espera a la próxima vuelta, salvo que en la
  próxima ya no alcance a cerrar con tiempo: entonces sale con el aviso.
  Configuración: ``alertas.revisionBases``.

El correo sale por **Outlook de este equipo** (``enviar_correo_outlook.ps1``,
COM de Outlook): no se guarda ninguna contraseña nueva. Lo llama
``Actualizar_Finanzas/driver.py`` después de armar el tablero, solo si
Mercado Público respondió (con datos de la caché no se avisa nada).

Uso:
    py -3.14 alertas_oportunidades.py status          # qué se enviaría ahora (con sus bases revisadas), sin enviar ni guardar
    py -3.14 alertas_oportunidades.py vista [ruta]    # escribe el correo como .html para mirarlo (revisa las bases), sin enviar
    py -3.14 alertas_oportunidades.py enviar          # envía si corresponde (lo hace el driver)
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import bases_oportunidades as bases  # noqa: E402
import intercambio  # noqa: E402
import oportunidades as op  # noqa: E402

RUTA_DATOS = AQUI / "Visualizador Web" / "data" / "oportunidades.json"
RUTA_REGISTRO = AQUI / "oportunidades_estado_correos.json"          # lo enviado (gitignoreado)
RUTA_DESTINATARIOS = AQUI / "oportunidades_destinatarios.json"      # a quién (gitignoreado: el repo es público)
SCRIPT_OUTLOOK = AQUI / "enviar_correo_outlook.ps1"
URL_TABLERO = "https://cristobal-monzo.github.io/finanzas-quempin/oportunidades/"
_CORREO = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
NARANJO, NARANJO_TINTA = "#ff5100", "#b23a00"


class ErrorCorreo(Exception):
    """No se pudo entregar el correo a Outlook."""


# ── QUÉ ENVIAR ───────────────────────────────────────────────────────────────

def horas_para(cierre, ahora: datetime) -> float | None:
    if not cierre:
        return None
    try:
        f = datetime.fromisoformat(cierre if len(cierre) > 10 else cierre + "T23:59")
    except ValueError:
        return None
    return (f - ahora).total_seconds() / 3600


def es_compra_agil(o: dict) -> bool:
    return bool(o.get("compraAgil")) or str(o.get("codigo") or "").split("-")[-1].startswith("COT")


def elegibles(datos: dict, enviados: set[str], reglas: dict, ahora: datetime) -> list[dict]:
    """Las oportunidades que merecen correo y no se enviaron antes, de mejor a peor."""
    minimas = reglas["horasMinimasParaCerrar"]
    salida = []
    for o in datos.get("oportunidades") or []:
        horas = horas_para(o.get("cierre"), ahora)
        if (o.get("puntaje", 0) >= reglas["notaMinima"] and o.get("ficha") and o.get("categoria") != "descartar"
                and not o.get("descartar") and o.get("codigo") not in enviados
                and not (reglas.get("omitirSiEstaEnPlanilla", True) and o.get("enPlanilla"))
                and horas is not None and horas >= minimas["compraAgil" if es_compra_agil(o) else "licitacion"]):
            salida.append(o)
    return sorted(salida, key=lambda o: -o["puntaje"])


def en_horario_laboral(ahora: datetime, reglas: dict) -> tuple[bool, str]:
    """(se puede enviar ahora, por qué no). Lunes a viernes, dentro de
    horario.desde y antes de horario.hasta, y que no sea feriado."""
    h = reglas["horario"]
    if ahora.isoweekday() not in h["dias"]:
        return False, "es fin de semana"
    if ahora.date().isoformat() in set(reglas.get("feriados") or []):
        return False, "es feriado"
    if not (h["desde"] <= ahora.strftime("%H:%M") < h["hasta"]):
        return False, f"es fuera del horario de {h['desde']} a {h['hasta']}"
    return True, ""


def feriados_cubren(ahora: datetime, reglas: dict) -> bool:
    """La lista de feriados tiene fechas del año en curso (hay que extenderla cada año)."""
    return any(str(f).startswith(f"{ahora.year}-") for f in reglas.get("feriados") or [])


def correos_en_7_dias(registro: dict, ahora: datetime) -> int:
    desde = (ahora - timedelta(days=7)).isoformat(timespec="seconds")
    return sum(1 for c in registro.get("correos") or [] if c.get("fecha", "") > desde)


def decidir(datos: dict, registro: dict, reglas: dict, ahora: datetime) -> dict:
    # Lo ya enviado y lo que la revisión de las bases descartó no vuelve.
    enviados = {e.get("codigo") for e in (registro.get("enviados") or []) + (registro.get("descartadasBases") or [])}
    lista = elegibles(datos, enviados, reglas, ahora)
    usados = correos_en_7_dias(registro, ahora)
    if not lista:
        return {"enviar": [], "esperan": [], "motivo": f"ninguna oportunidad nueva con nota {reglas['notaMinima']} o más"}
    habil, por_que = en_horario_laboral(ahora, reglas)
    if not habil:
        h = reglas["horario"]
        return {"enviar": [], "esperan": lista,
                "motivo": f"no se envía porque {por_que} (solo de lunes a viernes hábiles, de {h['desde']} a {h['hasta']}): "
                          "esperan a la próxima vuelta en horario"}
    if usados >= reglas["maxCorreosPorSemana"]:
        return {"enviar": [], "esperan": lista,
                "motivo": f"ya se enviaron {usados} correos en 7 días (tope {reglas['maxCorreosPorSemana']}): esperan"}
    tope = reglas.get("maxOportunidadesPorCorreo", 5)
    return {"enviar": lista[:tope], "esperan": lista[tope:], "motivo": f"correo {usados + 1} de {reglas['maxCorreosPorSemana']} en 7 días"}


# ── REVISAR LAS BASES ANTES DE ENVIAR ────────────────────────────────────────

def revisar_bases(o: dict, ahora: datetime, config: dict) -> dict:
    """La revisión real, contra Mercado Público. Las pruebas la reemplazan."""
    return bases.revisar(o, ahora, config)


def proxima_vuelta(ahora: datetime, reglas: dict) -> datetime:
    """Cuándo podría salir el próximo correo: el siguiente día hábil, a la
    hora en que empieza el horario (la tarea corre a diario a esa hora)."""
    hh, mm = (int(x) for x in reglas["horario"]["desde"].split(":"))
    dia = ahora.date()
    for _ in range(15):
        dia += timedelta(days=1)
        momento = datetime(dia.year, dia.month, dia.day, hh, mm)
        if en_horario_laboral(momento, reglas)[0]:
            return momento
    return momento


def ultima_oportunidad(o: dict, ahora: datetime, reglas: dict) -> bool:
    """En la próxima vuelta ya no alcanzaría a avisarse a tiempo."""
    horas = horas_para(o.get("cierre"), proxima_vuelta(ahora, reglas))
    return horas is None or horas < reglas["horasMinimasParaCerrar"]["compraAgil" if es_compra_agil(o) else "licitacion"]


def revisar_candidatas(d: dict, reglas: dict, config: dict, ahora: datetime, revisor) -> dict:
    """Revisa las bases de las que van al correo, de mejor a peor nota. Una
    que las bases descartan deja su lugar a la siguiente; una cuya ficha no
    respondió espera, salvo que sea su última vuelta a tiempo."""
    rb = reglas.get("revisionBases") or {}
    tope = reglas.get("maxOportunidadesPorCorreo", 5)
    maximo = rb.get("maxRevisionesPorVuelta", 8)
    aprobadas, sin_revisar, sin_turno, descartadas = [], [], [], []
    revisadas = 0
    for o in d["enviar"] + d["esperan"]:
        if len(aprobadas) >= tope or revisadas >= maximo:
            sin_turno.append(o)
            continue
        revisadas += 1
        r = revisor(o, ahora, config)
        o = dict(o, revisionBases=r)
        if r.get("descarta"):
            descartadas.append(o)
        elif not r.get("ok") and not ultima_oportunidad(o, ahora, reglas):
            sin_revisar.append(o)
        else:
            aprobadas.append(o)
    motivo = d["motivo"]
    if not aprobadas:
        partes = ([f"la revisión de las bases descartó {len(descartadas)}"] if descartadas else []) + \
                 ([f"no se pudieron revisar las bases de {len(sin_revisar)} (esperan a la próxima vuelta)"] if sin_revisar else [])
        motivo = "; ".join(partes or ["no quedó ninguna para enviar"]) + ": no se envía correo"
    return dict(d, enviar=aprobadas, esperan=sin_revisar + sin_turno, descartadasBases=descartadas, motivo=motivo)


# ── EL CORREO ────────────────────────────────────────────────────────────────

def _fecha_hora(texto) -> str:
    try:
        f = datetime.fromisoformat(texto if len(texto) > 10 else texto + "T23:59")
    except (TypeError, ValueError):
        return str(texto or "sin fecha")
    return f.strftime("%d-%m-%Y %H:%M")


def tiempo_restante(cierre, ahora: datetime) -> str:
    h = horas_para(cierre, ahora)
    if h is None:
        return "sin fecha de cierre"
    if h < 48:
        return f"{h:.0f} horas"
    return f"{h / 24:.0f} días"


def texto_visita(o: dict) -> str:
    v = o.get("visita") or {}
    if v.get("fecha"):
        cuando = _fecha_hora(v["fecha"])
        if v.get("obligatoria"):
            return f"Sí, obligatoria: {cuando}"
        if v.get("obligatoria") is False:
            return f"Optativa: {cuando}"
        return f"Sí: {cuando} (revisar en las bases si es obligatoria)"
    if v.get("mencionada"):
        return ("Las bases la nombran, sin fecha en la ficha" if v.get("fuente") == "bases"
                else "La descripción menciona una visita (sin fecha en la ficha)")
    if v.get("sinVisita"):
        return "No requiere (sin visita en la ficha de las bases)"
    return "Sin confirmar: revisar en las bases"


def texto_monto(o: dict) -> str:
    m = o.get("monto") or {}
    if not m.get("valor"):
        return "No publicado"
    valor = "$" + f"{round(m['valor']):,}".replace(",", ".")
    fuente = m.get("fuente") or ""
    if fuente.startswith("por tipo"):
        return f"~{valor} (estimado {fuente})"
    return valor + (" (disponible)" if es_compra_agil(o) else " (estimado por el comprador)" if fuente.startswith("estimado") else "")


def texto_ejecucion(o: dict) -> str:
    meses = o.get("duracionMeses")
    if meses is None:
        return "No informado"
    if es_compra_agil(o):
        return f"Entrega en {round(meses * 30)} días"
    return f"{meses:.0f} meses" if meses >= 1 else f"{round(meses * 30)} días"


def filas(o: dict, ahora: datetime) -> list[tuple[str, str]]:
    lugar = ", ".join(x for x in (o.get("comuna"), o.get("regionCorta") or o.get("region")) if x) or "Sin dato"
    # Lo que la revisión de las bases corrigió manda sobre la evaluación previa.
    corregido = (o.get("revisionBases") or {}).get("correcciones") or {}
    cierre = corregido.get("cierre") or o.get("cierre")
    salida = [
        ("Monto", corregido.get("monto") or texto_monto(o)),
        ("Tiempo restante", f"{tiempo_restante(cierre, ahora)} (cierra el {_fecha_hora(cierre)})"),
        ("Región", lugar),
        ("Visita técnica", corregido.get("visita") or texto_visita(o)),
        ("Ejecución" if not es_compra_agil(o) else "Plazo de entrega", texto_ejecucion(o)),
        ("Comprador", " · ".join(x for x in (o.get("organismo"), o.get("unidadCompra")) if x) or "Sin dato"),
    ]
    if o.get("probabilidadGanar") is not None:
        salida.append(("Historia parecida", f"QUEMPIN ganó ~{round(100 * o['probabilidadGanar'])} % de las parecidas que ofertó"))
    return salida


def asunto(lista: list[dict]) -> str:
    if len(lista) == 1:
        o = lista[0]
        nombre = (o.get("nombre") or o["codigo"])[:70]
        return f"Oportunidad {o['puntaje']:.0f}/100 en Mercado Público: {nombre}"
    return f"{len(lista)} oportunidades muy buenas en Mercado Público (nota {lista[-1]['puntaje']:.0f} a {lista[0]['puntaje']:.0f})"


_MARCA_NIVEL = {"descarta": ("✗", "#b00020"), "atencion": ("!", NARANJO_TINTA), "ok": ("✓", "#1b7a3a"), "dato": ("·", "#777")}


def bloque_bases(o: dict) -> str:
    """Lo verificado en las bases, de lo más importante a lo informativo."""
    r = o.get("revisionBases")
    if not r:
        return ""
    e = html.escape
    titulo = '<div style="font-size:14px;font-weight:bold;color:#111;margin:14px 0 4px 0">Revisión de las bases</div>'
    if not r.get("ok"):
        return (titulo + f'<div style="font-size:14px;color:{NARANJO_TINTA}">! No se pudo leer la ficha de las bases '
                f'({e(r.get("error") or "sin respuesta")}). Sale igual porque mañana ya no habría tiempo: revísalas antes de decidir.</div>')
    filas_html = "".join(
        f'<li style="margin:3px 0"><span style="color:{_MARCA_NIVEL[p["nivel"]][1]};font-weight:bold">{_MARCA_NIVEL[p["nivel"]][0]}</span> {e(p["texto"])}</li>'
        for p in sorted(r.get("puntos") or [], key=lambda p: bases.NIVELES.index(p["nivel"])))
    remiten = (f' {r["remiten"]} punto{"s" if r["remiten"] > 1 else ""} de la ficha remite{"n" if r["remiten"] > 1 else ""} '
               'a las bases adjuntas (PDF).') if r.get("remiten") else ""
    return (titulo + f'<ul style="list-style:none;padding:0;margin:0;font-size:14px;color:#111">{filas_html}</ul>'
            f'<div style="font-size:12px;color:#777;margin-top:6px">Leído de {e(r.get("fuente") or "Mercado Público")} '
            f'el {_fecha_hora(r.get("revisado"))}.{remiten} Los PDF adjuntos no se pueden bajar automáticamente: léelos en la ficha.</div>')


def cuerpo_html(lista: list[dict], ahora: datetime, reglas: dict) -> str:
    e = html.escape
    bloques = []
    for o in lista:
        tipo = "Compra Ágil" if es_compra_agil(o) else f"Licitación {o.get('tipo') or ''}".strip()
        filas_html = "".join(
            f'<tr><td style="padding:4px 12px 4px 0;color:#555;white-space:nowrap;vertical-align:top">{e(k)}</td>'
            f'<td style="padding:4px 0;color:#111;vertical-align:top">{e(v)}</td></tr>' for k, v in filas(o, ahora))
        # Si las bases dicen otra cosa de la visita, la frase de la evaluación previa sobra (y la contradiría).
        corrige_visita = "visita" in ((o.get("revisionBases") or {}).get("correcciones") or {})
        vigentes = [x for x in (o.get("aFavor") or []) + (o.get("enContra") or [])
                    if not (corrige_visita and "visita" in op.normalizar(x))]
        favor = "".join(f'<li style="margin:2px 0">✓ {e(x)}</li>' for x in o.get("aFavor") or [] if x in vigentes)
        contra = "".join(f'<li style="margin:2px 0;color:{NARANJO_TINTA}">! {e(x)}</li>' for x in o.get("enContra") or [] if x in vigentes)
        razones = (f'<ul style="list-style:none;padding:0;margin:10px 0 0 0;font-size:14px">{favor}{contra}</ul>'
                   if favor or contra else "")
        bloques.append(f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e5e5;border-left:4px solid {NARANJO};border-radius:6px;margin:0 0 16px 0">
<tr><td style="padding:14px 16px">
  <div style="font-size:12px;color:#666;text-transform:uppercase;letter-spacing:.04em">{e(tipo)} · {e(o['codigo'])}</div>
  <div style="font-size:17px;font-weight:bold;color:#111;margin:4px 0 8px 0">{e(o.get('nombre') or '')}</div>
  <div style="display:inline-block;background:{NARANJO};color:#fff;font-weight:bold;font-size:15px;padding:3px 10px;border-radius:12px">Nota {o['puntaje']:.0f}/100</div>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:10px;font-size:14px">{filas_html}</table>
  {razones}
  {bloque_bases(o)}
  <div style="margin-top:12px"><a href="{e(o['url'], quote=True)}" style="color:{NARANJO_TINTA};font-weight:bold">Ver la ficha en Mercado Público</a></div>
</td></tr></table>""")
    return f"""<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;padding:0;background:#fff">
<div style="font-family:Lato,Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;padding:16px;color:#111">
  <div style="font-size:13px;font-weight:bold;color:{NARANJO_TINTA};letter-spacing:.06em">QUEMPIN · OPORTUNIDADES EN MERCADO PÚBLICO</div>
  <p style="font-size:15px;margin:8px 0 16px 0">{'Apareció una oportunidad' if len(lista) == 1 else f'Aparecieron {len(lista)} oportunidades'} con nota {reglas['notaMinima']} o más en la evaluación de hoy.{' Antes de enviar este correo se revisaron sus bases en Mercado Público: lo verificado va en cada una.' if any((o.get('revisionBases') or {}).get('ok') for o in lista) else ''}</p>
  {''.join(bloques)}
  <p style="font-size:14px;margin:16px 0"><a href="{URL_TABLERO}" style="color:{NARANJO_TINTA}">Abrir el tablero de Oportunidades</a> (con la contraseña de los tableros) para ver cómo se calculó cada nota.</p>
  <p style="font-size:12px;color:#777;margin:16px 0 0 0">Correo automático: solo para notas de {reglas['notaMinima']} o más, en días hábiles de {reglas['horario']['desde']} a {reglas['horario']['hasta']}, como máximo {reglas['maxCorreosPorSemana']} correos en 7 días y nunca dos veces la misma oportunidad. Las notas son una evaluación previa y la revisión lee la ficha de las bases que publica Mercado Público; las bases administrativas y técnicas en PDF hay que leerlas en la ficha antes de ofertar.</p>
</div></body></html>"""


# ── ENVIAR ───────────────────────────────────────────────────────────────────

def destinatarios(ruta: Path | None = None) -> list[str]:
    datos = op._leer_estado(ruta or RUTA_DESTINATARIOS)
    para = [str(x).strip() for x in datos.get("para") or [] if isinstance(x, str)]
    return [x for x in para if _CORREO.match(x)]


def exigir_horario_laboral(ahora: datetime | None = None) -> None:
    """Segundo control del horario, con la hora de este instante y la
    configuración recién leída: nunca sale un correo fuera del horario
    laboral, aunque quien llame se haya equivocado."""
    habil, por_que = en_horario_laboral(ahora or datetime.now(), op.cargar_config()["alertas"])
    if not habil:
        raise ErrorCorreo(f"no se envía porque {por_que}")


def enviar_outlook(para: list[str], titulo: str, cuerpo: str) -> str:
    """Entrega el correo a Outlook de este equipo (COM). Devuelve 'enviado' o
    'bandeja-de-salida' (Outlook lo envía al sincronizar)."""
    exigir_horario_laboral()
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "correo.json"
        ruta.write_text(json.dumps({"para": para, "asunto": titulo, "html": cuerpo}, ensure_ascii=True), encoding="ascii")
        try:
            r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                "-File", str(SCRIPT_OUTLOOK), str(ruta)],
                               capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ErrorCorreo(f"no se pudo abrir Outlook ({type(error).__name__})") from error
    salida = (r.stdout or "").strip().splitlines()
    if r.returncode != 0 or not salida or salida[-1] not in ("enviado", "bandeja-de-salida"):
        raise ErrorCorreo("Outlook no aceptó el correo: " + ((r.stderr or r.stdout or "").strip()[-300:] or f"código {r.returncode}"))
    return salida[-1]


def _guardar_registro(ruta: Path, registro: dict, ahora: datetime) -> None:
    # Se recuerda un año (una licitación no vuelve a publicarse con el mismo código).
    hace_un_ano = (ahora - timedelta(days=365)).isoformat()
    for clave in ("enviados", "correos", "descartadasBases"):
        if clave in registro:
            registro[clave] = [x for x in registro[clave] if x.get("fecha", "") > hace_un_ano]
    intercambio._escribir_json_atomico(ruta, registro)


def ejecutar(datos: dict, enviar: bool = True, ahora: datetime | None = None, config: dict | None = None,
             remitente=None, ruta_registro: Path | None = None, ruta_destinatarios: Path | None = None,
             revisor=None) -> dict:
    # Se resuelven al llamar (no al definir): así las pruebas pueden cambiarlos y nunca envían ni consultan de verdad.
    remitente = remitente or enviar_outlook
    revisor = revisor or revisar_bases
    ruta_registro = ruta_registro or RUTA_REGISTRO
    ruta_destinatarios = ruta_destinatarios or RUTA_DESTINATARIOS
    config = config or op.cargar_config()
    reglas = config["alertas"]
    ahora = ahora or datetime.now()
    registro = op._leer_estado(ruta_registro)
    d = dict(decidir(datos, registro, reglas, ahora), descartadasBases=[])
    if d["enviar"] and (reglas.get("revisionBases") or {}).get("activa", True):
        d = revisar_candidatas(d, reglas, config, ahora, revisor)
    resultado = dict(d, enviado=None)
    momento = ahora.isoformat(timespec="seconds")
    if enviar and d["descartadasBases"]:
        registro.setdefault("descartadasBases", []).extend(
            {"codigo": o["codigo"], "fecha": momento, "puntaje": o["puntaje"], "nombre": (o.get("nombre") or "")[:120],
             "motivo": o["revisionBases"]["descarta"]} for o in d["descartadasBases"])
    if not d["enviar"] or not enviar:
        if enviar and d["descartadasBases"]:
            _guardar_registro(ruta_registro, registro, ahora)
        return resultado
    para = destinatarios(ruta_destinatarios)
    if not para:
        resultado["motivo"] = f"no hay destinatario en {ruta_destinatarios.name}: no se envió"
        if d["descartadasBases"]:
            _guardar_registro(ruta_registro, registro, ahora)
        return resultado
    estado = remitente(para, asunto(d["enviar"]), cuerpo_html(d["enviar"], ahora, reglas))
    registro.setdefault("correos", []).append({"fecha": momento, "codigos": [o["codigo"] for o in d["enviar"]], "estado": estado})
    registro.setdefault("enviados", []).extend(
        {"codigo": o["codigo"], "fecha": momento, "puntaje": o["puntaje"], "nombre": (o.get("nombre") or "")[:120],
         "bases": _resumen_revision(o.get("revisionBases"))} for o in d["enviar"])
    _guardar_registro(ruta_registro, registro, ahora)
    resultado["enviado"] = estado
    return resultado


def _resumen_revision(r: dict | None) -> str:
    if not r:
        return "sin revisar (revisión apagada)"
    if not r.get("ok"):
        return f"no se pudo revisar: {r.get('error')}"
    atencion = sum(1 for p in r.get("puntos") or [] if p["nivel"] == "atencion")
    return f"revisadas: {atencion} punto{'s' if atencion != 1 else ''} de atención"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except AttributeError:
        pass
    orden = argv[0] if argv else ""
    if orden not in ("status", "vista", "enviar"):
        print(__doc__.split("Uso:")[1])
        return 2
    try:
        datos = json.loads(RUTA_DATOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"[ERROR] No hay evaluación guardada en {RUTA_DATOS}: arma primero el tablero.")
        return 1
    config = op.cargar_config()
    if not feriados_cubren(datetime.now(), config["alertas"]):
        print(f"[AVISO] La lista de feriados (alertas.feriados en oportunidades_config.json) no tiene fechas de "
              f"{datetime.now().year}: agrégalas. Mientras tanto solo se evitan los fines de semana.")
    if orden == "vista":
        ahora = datetime.now()
        lista = sorted((o for o in datos.get("oportunidades") or [] if o.get("ficha") and o.get("categoria") != "descartar"),
                       key=lambda o: -o["puntaje"])[:2]
        lista = [dict(o, revisionBases=revisar_bases(o, ahora, config)) for o in lista]
        ruta = Path(argv[1]) if len(argv) > 1 else Path(tempfile.gettempdir()) / "vista_correo_oportunidades.html"
        ruta.write_text(cuerpo_html(lista, ahora, config["alertas"]), encoding="utf-8")
        print(f"Vista del correo (con las 2 mejores de hoy, tengan o no {config['alertas']['notaMinima']}, y sus bases revisadas): {ruta}")
        return 0
    try:
        r = ejecutar(datos, enviar=orden == "enviar", config=config)
    except ErrorCorreo as error:
        print(f"[ERROR] {error}. No se marcó como enviada: se reintenta en la próxima vuelta.")
        return 1
    for o in r["enviar"]:
        print(f"  {'[ENVIADA]' if r['enviado'] else '[SE ENVIARÍA]'} {o['puntaje']:5.1f}  {o['codigo']:<18} {(o.get('nombre') or '')[:60]}")
        print(f"      bases: {_resumen_revision(o.get('revisionBases'))}")
    for o in r["descartadasBases"]:
        print(f"  [DESCARTADA POR LAS BASES] {o['puntaje']:5.1f}  {o['codigo']:<18} {o['revisionBases']['descarta']}")
    for o in r["esperan"]:
        espera = f" (bases: {_resumen_revision(o['revisionBases'])})" if o.get("revisionBases") else ""
        print(f"  [ESPERA]  {o['puntaje']:5.1f}  {o['codigo']:<18} {(o.get('nombre') or '')[:60]}{espera}")
    estado = {"enviado": "correo enviado", "bandeja-de-salida": "correo en la bandeja de salida de Outlook (sale al sincronizar)"}
    print(f"Alertas por correo: {estado.get(r['enviado'], r['motivo'])}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
