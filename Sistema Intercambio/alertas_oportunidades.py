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
- El destinatario está en ``oportunidades_destinatarios.json``, fuera del
  repositorio (que es público): ``{"para": ["nombre@quempin.cl"]}``. Sin ese
  archivo no se envía nada.

El correo sale por **Outlook de este equipo** (``enviar_correo_outlook.ps1``,
COM de Outlook): no se guarda ninguna contraseña nueva. Lo llama
``Actualizar_Finanzas/driver.py`` después de armar el tablero, solo si
Mercado Público respondió (con datos de la caché no se avisa nada).

Uso:
    py -3.14 alertas_oportunidades.py status          # qué se enviaría ahora, sin enviar
    py -3.14 alertas_oportunidades.py vista [ruta]    # escribe el correo como .html para mirarlo, sin enviar
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


def correos_en_7_dias(registro: dict, ahora: datetime) -> int:
    desde = (ahora - timedelta(days=7)).isoformat(timespec="seconds")
    return sum(1 for c in registro.get("correos") or [] if c.get("fecha", "") > desde)


def decidir(datos: dict, registro: dict, reglas: dict, ahora: datetime) -> dict:
    enviados = {e.get("codigo") for e in registro.get("enviados") or []}
    lista = elegibles(datos, enviados, reglas, ahora)
    usados = correos_en_7_dias(registro, ahora)
    if not lista:
        return {"enviar": [], "esperan": [], "motivo": f"ninguna oportunidad nueva con nota {reglas['notaMinima']} o más"}
    if usados >= reglas["maxCorreosPorSemana"]:
        return {"enviar": [], "esperan": lista,
                "motivo": f"ya se enviaron {usados} correos en 7 días (tope {reglas['maxCorreosPorSemana']}): esperan"}
    tope = reglas.get("maxOportunidadesPorCorreo", 5)
    return {"enviar": lista[:tope], "esperan": lista[tope:], "motivo": f"correo {usados + 1} de {reglas['maxCorreosPorSemana']} en 7 días"}


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
        return "La descripción menciona una visita (sin fecha en la ficha)"
    return "No requiere (sin visita en la ficha)"


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
    salida = [
        ("Monto", texto_monto(o)),
        ("Tiempo restante", f"{tiempo_restante(o.get('cierre'), ahora)} (cierra el {_fecha_hora(o.get('cierre'))})"),
        ("Región", lugar),
        ("Visita técnica", texto_visita(o)),
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


def cuerpo_html(lista: list[dict], ahora: datetime, reglas: dict) -> str:
    e = html.escape
    bloques = []
    for o in lista:
        tipo = "Compra Ágil" if es_compra_agil(o) else f"Licitación {o.get('tipo') or ''}".strip()
        filas_html = "".join(
            f'<tr><td style="padding:4px 12px 4px 0;color:#555;white-space:nowrap;vertical-align:top">{e(k)}</td>'
            f'<td style="padding:4px 0;color:#111;vertical-align:top">{e(v)}</td></tr>' for k, v in filas(o, ahora))
        favor = "".join(f'<li style="margin:2px 0">✓ {e(x)}</li>' for x in o.get("aFavor") or [])
        contra = "".join(f'<li style="margin:2px 0;color:{NARANJO_TINTA}">! {e(x)}</li>' for x in o.get("enContra") or [])
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
  <div style="margin-top:12px"><a href="{e(o['url'], quote=True)}" style="color:{NARANJO_TINTA};font-weight:bold">Ver la ficha en Mercado Público</a></div>
</td></tr></table>""")
    return f"""<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;padding:0;background:#fff">
<div style="font-family:Lato,Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;padding:16px;color:#111">
  <div style="font-size:13px;font-weight:bold;color:{NARANJO_TINTA};letter-spacing:.06em">QUEMPIN · OPORTUNIDADES EN MERCADO PÚBLICO</div>
  <p style="font-size:15px;margin:8px 0 16px 0">{'Apareció una oportunidad' if len(lista) == 1 else f'Aparecieron {len(lista)} oportunidades'} con nota {reglas['notaMinima']} o más en la evaluación de hoy.</p>
  {''.join(bloques)}
  <p style="font-size:14px;margin:16px 0"><a href="{URL_TABLERO}" style="color:{NARANJO_TINTA}">Abrir el tablero de Oportunidades</a> (con la contraseña de los tableros) para ver cómo se calculó cada nota.</p>
  <p style="font-size:12px;color:#777;margin:16px 0 0 0">Correo automático: solo para notas de {reglas['notaMinima']} o más, como máximo {reglas['maxCorreosPorSemana']} correos en 7 días y nunca dos veces la misma oportunidad. Las notas son una evaluación previa: confirma plazos, visita y requisitos en las bases.</p>
</div></body></html>"""


# ── ENVIAR ───────────────────────────────────────────────────────────────────

def destinatarios(ruta: Path | None = None) -> list[str]:
    datos = op._leer_estado(ruta or RUTA_DESTINATARIOS)
    para = [str(x).strip() for x in datos.get("para") or [] if isinstance(x, str)]
    return [x for x in para if _CORREO.match(x)]


def enviar_outlook(para: list[str], titulo: str, cuerpo: str) -> str:
    """Entrega el correo a Outlook de este equipo (COM). Devuelve 'enviado' o
    'bandeja-de-salida' (Outlook lo envía al sincronizar)."""
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


def ejecutar(datos: dict, enviar: bool = True, ahora: datetime | None = None, config: dict | None = None,
             remitente=None, ruta_registro: Path | None = None, ruta_destinatarios: Path | None = None) -> dict:
    # Se resuelven al llamar (no al definir): así las pruebas pueden cambiarlos y nunca envían de verdad.
    remitente = remitente or enviar_outlook
    ruta_registro = ruta_registro or RUTA_REGISTRO
    ruta_destinatarios = ruta_destinatarios or RUTA_DESTINATARIOS
    config = config or op.cargar_config()
    reglas = config["alertas"]
    ahora = ahora or datetime.now()
    registro = op._leer_estado(ruta_registro)
    d = decidir(datos, registro, reglas, ahora)
    resultado = dict(d, enviado=None)
    if not d["enviar"] or not enviar:
        return resultado
    para = destinatarios(ruta_destinatarios)
    if not para:
        resultado["motivo"] = f"no hay destinatario en {ruta_destinatarios.name}: no se envió"
        return resultado
    estado = remitente(para, asunto(d["enviar"]), cuerpo_html(d["enviar"], ahora, reglas))
    momento = ahora.isoformat(timespec="seconds")
    registro.setdefault("correos", []).append({"fecha": momento, "codigos": [o["codigo"] for o in d["enviar"]], "estado": estado})
    registro.setdefault("enviados", []).extend({"codigo": o["codigo"], "fecha": momento, "puntaje": o["puntaje"],
                                                "nombre": (o.get("nombre") or "")[:120]} for o in d["enviar"])
    # Lo enviado se recuerda un año (una licitación no vuelve a publicarse con el mismo código).
    hace_un_ano = (ahora - timedelta(days=365)).isoformat()
    registro["enviados"] = [x for x in registro["enviados"] if x.get("fecha", "") > hace_un_ano]
    registro["correos"] = [x for x in registro["correos"] if x.get("fecha", "") > hace_un_ano]
    intercambio._escribir_json_atomico(ruta_registro, registro)
    resultado["enviado"] = estado
    return resultado


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
    if orden == "vista":
        ahora = datetime.now()
        lista = sorted((o for o in datos.get("oportunidades") or [] if o.get("ficha") and o.get("categoria") != "descartar"),
                       key=lambda o: -o["puntaje"])[:2]
        ruta = Path(argv[1]) if len(argv) > 1 else Path(tempfile.gettempdir()) / "vista_correo_oportunidades.html"
        ruta.write_text(cuerpo_html(lista, ahora, config["alertas"]), encoding="utf-8")
        print(f"Vista del correo (con las 2 mejores de hoy, tengan o no {config['alertas']['notaMinima']}): {ruta}")
        return 0
    try:
        r = ejecutar(datos, enviar=orden == "enviar", config=config)
    except ErrorCorreo as error:
        print(f"[ERROR] {error}. No se marcó como enviada: se reintenta en la próxima vuelta.")
        return 1
    for o in r["enviar"]:
        print(f"  {'[ENVIADA]' if r['enviado'] else '[SE ENVIARÍA]'} {o['puntaje']:5.1f}  {o['codigo']:<18} {(o.get('nombre') or '')[:60]}")
    for o in r["esperan"]:
        print(f"  [ESPERA]  {o['puntaje']:5.1f}  {o['codigo']:<18} {(o.get('nombre') or '')[:60]}")
    estado = {"enviado": "correo enviado", "bandeja-de-salida": "correo en la bandeja de salida de Outlook (sale al sincronizar)"}
    print(f"Alertas por correo: {estado.get(r['enviado'], r['motivo'])}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
