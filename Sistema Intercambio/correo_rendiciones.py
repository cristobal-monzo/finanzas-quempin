"""
correo_rendiciones.py -- Correo automático de cada rendición enviada desde el Portal.

Pedido del usuario (2026-11-18): «Enviar rendición» la guarda en el registro de
rendiciones y envía un correo automático, muy ejecutivo, a los destinatarios
de ``rendiciones_destinatarios.json``. El correo dice que es automático, el
monto total, el período (del documento más antiguo al más reciente) y la
persona, con nombre y apellido.

- El registro es ``publicado/rendiciones.json`` (lo escribe documentos_cc.py).
  Este paso le agrega a cada rendición ``correo`` (fecha, para y estado): el
  Portal lo muestra en «Registro de rendiciones».
- Un correo por rendición, una sola vez (``rendiciones_estado_correos.json``,
  gitignoreado). Una rendición con documentos en varias carpetas llega en
  varios mensajes: se espera hasta que lleguen todos o pasen ESPERA_INCOMPLETA
  desde que se envió; entonces sale con lo que llegó y lo dice.
- Una rendición enviada hace más de DIAS_MAX días no genera correo (un equipo
  nuevo, sin el registro de lo enviado, no reenvía lo antiguo).
- Sale por Outlook de este equipo (``enviar_correo_outlook.ps1``), a cualquier
  hora: la persona espera su correo al enviar.

Uso:
    py -3.14 correo_rendiciones.py status          # qué se enviaría ahora, sin enviar
    py -3.14 correo_rendiciones.py vista [ruta]    # escribe el próximo correo como .html, sin enviar
    py -3.14 correo_rendiciones.py enviar          # envía lo pendiente (lo hace el procesador)
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import intercambio  # noqa: E402

PUBLICACION = "rendiciones"
RUTA_REGISTRO = AQUI / "rendiciones_estado_correos.json"          # lo enviado (gitignoreado)
RUTA_DESTINATARIOS = AQUI / "rendiciones_destinatarios.json"      # a quién (gitignoreado)
DIAS_MAX = 14
ESPERA_INCOMPLETA = timedelta(hours=2)
URL_PORTAL = "https://cristobal-monzo.github.io/finanzas-quempin/portal/#/rendiciones"
TIPOS = {"vale": "Vale a rendir", "recuperacion": "Recuperación de gastos", "caja": "Caja chica"}
NARANJO, GRIS = "#ff5100", "#555555"
_CORREO = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class ErrorCorreo(Exception):
    """No se pudo entregar el correo."""


def _leer(ruta: Path) -> dict:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def destinatarios(ruta: Path | None = None) -> list[str]:
    para = [str(x).strip() for x in _leer(ruta or RUTA_DESTINATARIOS).get("para") or [] if isinstance(x, str)]
    return [x for x in para if _CORREO.match(x)]


def _fecha(texto: str):
    try:
        return datetime.strptime(texto, "%d-%m-%Y")
    except (TypeError, ValueError):
        return None


def _momento(texto: str | None):
    """Un instante con zona horaria (sin zona = la de este equipo): se compara igual en cualquier equipo."""
    try:
        return _con_zona(datetime.fromisoformat(str(texto).replace("Z", "+00:00")))
    except (TypeError, ValueError):
        return None


def _con_zona(m: datetime) -> datetime:
    return m if m.tzinfo else m.astimezone()


def pesos(n) -> str:
    return "$ " + f"{int(round(n or 0)):,}".replace(",", ".")


def periodo(ren: dict) -> tuple[str, str] | None:
    """Del documento más antiguo al más reciente: (desde, hasta) en dd-mm-aaaa."""
    fechas = sorted(f for f in (_fecha(d.get("fecha")) for d in ren.get("documentos") or []) if f)
    if not fechas:
        return None
    return fechas[0].strftime("%d-%m-%Y"), fechas[-1].strftime("%d-%m-%Y")


def texto_periodo(ren: dict) -> str:
    p = periodo(ren)
    if not p:
        return ren.get("periodo") or "sin fecha"
    return f"el {p[0]}" if p[0] == p[1] else f"del {p[0]} al {p[1]}"


def persona(ren: dict) -> str:
    return " ".join(str(ren.get("deudor") or "").split()) or "(sin nombre)"


def por_proyecto(ren: dict) -> list[tuple[str, int, int]]:
    """(carpeta, documentos, monto) de lo que llegó, de mayor a menor monto."""
    suma: dict[str, list[int]] = {}
    for d in ren.get("documentos") or []:
        s = suma.setdefault(d.get("carpeta") or "(sin carpeta)", [0, 0])
        s[0] += 1
        s[1] += int(d.get("valor") or 0)
    return sorted(((c, n, v) for c, (n, v) in suma.items()), key=lambda x: -x[2])


def armar(ren: dict) -> tuple[str, str]:
    """El asunto y el cuerpo HTML del correo de una rendición."""
    e = html.escape
    nombre, total = persona(ren), pesos(ren.get("total"))
    asunto = f"Rendición de gastos {ren.get('numero', '')} · {nombre} · {total}"
    llegaron, cantidad = len(ren.get("documentos") or []), int(ren.get("cantidad") or 0)
    filas = [
        ("Persona", e(nombre)),
        ("Monto total", f"<b>{e(total)}</b>"),
        ("Período", e(texto_periodo(ren)[0].upper() + texto_periodo(ren)[1:])),
        ("Tipo", e(TIPOS.get(ren.get("tipo"), "Rendición"))),
        ("N° de rendición", e(str(ren.get("numero") or ""))),
        ("Documentos", e(str(cantidad or llegaron))),
    ]
    if ren.get("unidad"):
        filas.append(("Unidad presupuestaria", e(ren["unidad"])))
    proyectos = "<br>".join(f"{e(c)}: {e(pesos(v))} ({n} doc.)" for c, n, v in por_proyecto(ren))
    if proyectos:
        filas.append(("Por proyecto", proyectos))
    tabla = "".join(
        f'<tr><td style="padding:6px 16px 6px 0;color:{GRIS};vertical-align:top;white-space:nowrap">{k}</td>'
        f'<td style="padding:6px 0;vertical-align:top">{v}</td></tr>' for k, v in filas)
    falta = ""
    if cantidad and llegaron < cantidad:
        falta = (f'<p style="margin:12px 0 0 0;color:{NARANJO}">Llegaron {llegaron} de {cantidad} documentos al Centro '
                 f'de Costos; el resto aún no se sincroniza.</p>')
    cuerpo = f"""<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222;max-width:600px">
  <div style="border-bottom:3px solid {NARANJO};padding-bottom:8px;margin-bottom:16px">
    <span style="font-size:18px;font-weight:bold">Rendición de gastos</span>
    <span style="color:{GRIS};font-size:12px;margin-left:8px">Correo automático · QUEMPIN</span>
  </div>
  <p style="margin:0 0 12px 0">Correo automático generado para la rendición de gastos de <b>{e(nombre)}</b>
    por un monto total de <b>{e(total)}</b>. Los gastos corresponden al período {e(texto_periodo(ren))}
    (documento más antiguo y más reciente de la rendición).</p>
  <table style="border-collapse:collapse;font-size:14px">{tabla}</table>{falta}
  <p style="margin:16px 0 0 0;font-size:12px;color:{GRIS}">Los documentos quedaron en la carpeta de cada proyecto del
    Centro de Costos. Registro de rendiciones: <a href="{URL_PORTAL}" style="color:{NARANJO}">Portal QUEMPIN</a>.</p>
</div>"""
    return asunto, cuerpo


def decidir(lista: list[dict], registro: dict, ahora: datetime) -> dict:
    """Qué rendiciones llevan correo ahora: completas (o que ya esperaron ESPERA_INCOMPLETA), no enviadas antes y
    de los últimos DIAS_MAX días."""
    ahora = _con_zona(ahora)
    ya = {x.get("id") for x in registro.get("enviados") or []}
    enviar, esperan = [], []
    for ren in lista:
        if ren.get("id") in ya or ren.get("correo"):
            continue
        cuando = _momento(ren.get("enviado"))
        if cuando and ahora - cuando > timedelta(days=DIAS_MAX):
            continue
        completa = len(ren.get("documentos") or []) >= int(ren.get("cantidad") or 0)
        if not completa and cuando and ahora - cuando < ESPERA_INCOMPLETA:
            esperan.append(ren)
            continue
        enviar.append(ren)
    return {"enviar": enviar, "esperan": esperan}


def remitente_outlook(para: list[str], asunto: str, cuerpo: str) -> str:
    import alertas_oportunidades  # solo al enviar de verdad: abre Outlook
    try:
        return alertas_oportunidades.entregar_outlook(para, asunto, cuerpo)
    except alertas_oportunidades.ErrorCorreo as error:
        raise ErrorCorreo(str(error)) from error


def ejecutar(raiz: Path, enviar: bool = True, remitente=None, ahora: datetime | None = None,
             ruta_registro: Path | None = None, ruta_destinatarios: Path | None = None) -> dict:
    """Envía el correo de cada rendición que lo necesita y lo anota en rendiciones.json y en el registro local.
    Devuelve {enviados: [N°], esperan: [N°], errores: [texto]}."""
    remitente = remitente or remitente_outlook
    ruta_registro = ruta_registro or RUTA_REGISTRO
    ahora = _con_zona(ahora or datetime.now())
    pub = intercambio.leer_publicacion(raiz, PUBLICACION)
    lista = list(((pub or {}).get("datos") or {}).get("rendiciones") or [])
    registro = _leer(ruta_registro)
    d = decidir(lista, registro, ahora)
    salida = {"enviados": [], "esperan": [r.get("numero") for r in d["esperan"]], "errores": []}
    if not enviar or not d["enviar"]:
        salida["pendientes"] = [r.get("numero") for r in d["enviar"]]
        return salida
    para = destinatarios(ruta_destinatarios)
    if not para:
        salida["errores"].append(f"sin destinatarios en {(ruta_destinatarios or RUTA_DESTINATARIOS).name}")
        return salida
    cambio = False
    for ren in d["enviar"]:
        asunto, cuerpo = armar(ren)
        try:
            estado = remitente(para, asunto, cuerpo)
        except Exception as error:  # noqa: BLE001 — un correo que no sale no frena al procesador; se reintenta
            salida["errores"].append(f"{ren.get('numero')}: {error}")
            continue
        momento = ahora.isoformat(timespec="seconds")
        registro.setdefault("enviados", []).append({"id": ren.get("id"), "numero": ren.get("numero"), "fecha": momento,
                                                    "estado": estado})
        intercambio._escribir_json_atomico(ruta_registro, registro)
        ren["correo"] = {"fecha": momento, "para": para, "estado": estado}
        salida["enviados"].append(ren.get("numero"))
        cambio = True
    if cambio:
        # Se relee justo antes: documentos_cc pudo agregar documentos; solo se le pone «correo» a lo enviado
        actual = intercambio.leer_publicacion(raiz, PUBLICACION)
        nueva = list(((actual or {}).get("datos") or {}).get("rendiciones") or [])
        correos = {r["id"]: r["correo"] for r in lista if r.get("correo")}
        for r in nueva:
            if r.get("id") in correos and not r.get("correo"):
                r["correo"] = correos[r["id"]]
        intercambio.publicar(raiz, PUBLICACION, "procesador", {"rendiciones": nueva})
    return salida


def main(argv: list[str]) -> int:
    orden = argv[0] if argv else "status"
    import ubicacion
    raiz = ubicacion.ubicar_intercambio(AQUI)
    if raiz is None:
        print("No encuentro la carpeta de Intercambio en este equipo.")
        return 1
    if orden == "status":
        print(json.dumps(ejecutar(raiz, enviar=False), ensure_ascii=False, indent=2))
        return 0
    if orden == "vista":
        pub = intercambio.leer_publicacion(raiz, PUBLICACION)
        lista = ((pub or {}).get("datos") or {}).get("rendiciones") or []
        if not lista:
            print("No hay rendiciones publicadas.")
            return 0
        asunto, cuerpo = armar(lista[0])
        ruta = Path(argv[1]) if len(argv) > 1 else Path("correo_rendicion.html")
        ruta.write_text(f"<h3>{html.escape(asunto)}</h3>{cuerpo}", encoding="utf-8")
        print(f"Escrito {ruta}")
        return 0
    if orden == "enviar":
        print(json.dumps(ejecutar(raiz), ensure_ascii=False, indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
