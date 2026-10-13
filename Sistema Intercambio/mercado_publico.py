# -*- coding: utf-8 -*-
"""
mercado_publico.py -- Monitor de licitaciones de Mercado Público (2026-10-13).

Por qué existe: el 97 % de los requerimientos de la Planilla de Ingreso viene
de Mercado Público y su resultado (adjudicado, no adjudicado, desierta) se
pasaba a mano cuando alguien se acordaba de mirar: la Planilla tenía 22
«Adjudicado» y 10 «Ofertado» sin valor, y con eso calcula la tasa de
adjudicación que usa el Flujo de Caja (análisis del 2026-10-08, §6 punto 1).

Qué hace, en cada vuelta del procesador:

1. Barre las **órdenes de compra emitidas a QUEMPIN** (por día, con el código
   de proveedor). Una OC es la prueba definitiva de que se ganó, y es la única
   señal de las Compras Ágiles (COT), que la API no expone como licitación.
2. Consulta las **licitaciones de la Planilla** que tienen código en «ID o
   Referencia» y todavía no tienen resultado (Ofertado, Evaluación), más una
   verificación única de las ya cerradas.
3. Deja **sugerencias** ``actualizar-requerimiento`` para la Planilla
   («Adjudicado» con el monto, «No adjudicado», con el motivo), por el mismo
   camino que el Formulador: una persona las pasa y el procesador las cierra
   solas. **Nunca escribe la Planilla** (ver requerimientos.py).
4. Publica ``publicado/licitaciones.json``: estado de cada licitación, quién
   ganó y por cuánto (precio de mercado para el Formulador), las OC y lo que
   necesita una persona (bandeja de pendientes).

SEGURIDAD
- El **ticket** de la API es personal (se pide con ClaveÚnica). Se guarda
  cifrado con DPAPI de Windows en %LOCALAPPDATA%\\QUEMPIN\\ (fuera de OneDrive
  y del repositorio, que es público): solo el mismo usuario de Windows en el
  mismo equipo puede descifrarlo. Se ingresa sin eco (``configurar``), nunca
  por la línea de comandos, y se censura en todo mensaje de error.
- Solo HTTPS al dominio de ChileCompra, con verificación de certificado,
  tiempo límite y tamaño máximo de respuesta. Sin dependencias nuevas.
- Lo que responde la API se trata como dato no confiable: códigos validados
  con una expresión regular antes de ir a la URL, textos limpios de
  caracteres de control y acortados, enlaces solo a www.mercadopublico.cl.
- No se publican nombres ni datos de contacto de funcionarios del comprador:
  solo el organismo.
- La API rechaza consultas muy seguidas (error 10500): pausa mínima entre
  llamadas, reintento con espera creciente y un tope de llamadas por vuelta
  (lo que falta sigue en la próxima).

Uso:
    py -3.14 mercado_publico.py configurar    # pide el ticket sin mostrarlo, lo prueba y lo guarda cifrado
    py -3.14 mercado_publico.py status        # qué se sugeriría, sin enviar ni publicar nada
    py -3.14 mercado_publico.py revisar       # una vuelta completa (lo mismo que hace el procesador)
    py -3.14 mercado_publico.py olvidar       # borra el ticket guardado en este equipo
"""

from __future__ import annotations

import json
import math
import os
import re
import ssl
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import esquemas  # noqa: E402
import intercambio  # noqa: E402
import requerimientos  # noqa: E402

HERRAMIENTA = "mercado-publico"
PUBLICACION = "licitaciones"

# QUEMPIN SPA como proveedor del Estado: verificado contra la API el
# 2026-10-13 (Empresas/BuscarProveedor con el RUT devuelve este código).
RUT_QUEMPIN = "76.772.215-K"
CODIGO_PROVEEDOR = "1717812"

API = "https://api.mercadopublico.cl/servicios/v1/publico/"
SITIO = "www.mercadopublico.cl"
FICHA_LICITACION = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion="
FICHA_OC = "https://www.mercadopublico.cl/PurchaseOrder/Modules/PO/DetailsPurchaseOrder.aspx?codigoOC="

RUTA_ESTADO = AQUI / "mercado_publico_estado.json"     # caché de lo consultado (gitignoreado; datos públicos)
VARIABLE_TICKET = "QUEMPIN_MP_TICKET"                    # para pruebas u otro equipo; nunca en un archivo del repo
ENTROPIA_DPAPI = b"quempin.mercado-publico/1"

TIEMPO_LIMITE_SEG = 30
MAX_BYTES_RESPUESTA = 5 * 1024 * 1024
PAUSA_SEG = 2.0            # medido 2026-10-13: sin pausa, la mitad de las consultas volvía con 10500
REINTENTOS = 3
LLAMADAS_POR_VUELTA = 120  # ~4 minutos como máximo; lo que falta sigue en la próxima vuelta
DIAS_HISTORIA_OC = 60      # la primera vez se barren las OC de los últimos 60 días
DIAS_REBARRIDO_OC = 2      # hoy y ayer se vuelven a barrer siempre (una OC aparece cuando cambia de estado)
DIAS_VIGENCIA_FINAL = 30   # una licitación ya resuelta se vuelve a mirar al mes (puede revocarse)
IVA = 0.19

# Código de una adquisición: <unidad>-<correlativo>-<tipo><año>. El tipo es
# LE, LP, L1, B2, CO, COT (Compra Ágil), SE, AG… (visto en la Planilla real).
PATRON_CODIGO = re.compile(r"\b(\d{1,9}-\d{1,7}-[A-Z][A-Z0-9]{1,3}\d{2})\b")
_CODIGO_EXACTO = re.compile(r"^\d{1,9}-\d{1,7}-[A-Z][A-Z0-9]{1,3}\d{2}$")
_TICKET = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")

# CodigoEstado de una licitación -> resultado para QUEMPIN.
ESTADO_LICITACION = {5: "abierta", 6: "en-evaluacion", 7: "desierta", 8: "adjudicada", 18: "revocada", 19: "suspendida"}
FINALES = {"ganada", "perdida", "desierta", "revocada"}
TEXTO_RESULTADO = {
    "ganada": "Adjudicada a QUEMPIN",
    "perdida": "Adjudicada a otro proveedor",
    "desierta": "Declarada desierta",
    "revocada": "Revocada",
    "suspendida": "Suspendida",
    "abierta": "Publicada, recibiendo ofertas",
    "en-evaluacion": "Cerrada, en evaluación",
    "adjudicada-sin-detalle": "Adjudicada (sin detalle por ítem)",
    "compra-agil": "Compra Ágil (sin resultado público)",
    "no-encontrada": "No encontrada en Mercado Público",
    "otro": "Otro estado",
}


# ── ERRORES ──────────────────────────────────────────────────────────────────

class ErrorMercadoPublico(Exception):
    """Falla al consultar la API (el mensaje nunca lleva el ticket)."""


class TicketInvalido(ErrorMercadoPublico):
    """La API rechazó el ticket: no tiene sentido seguir consultando."""


class SinTicket(ErrorMercadoPublico):
    """No hay ticket configurado en este equipo."""


class TopeDeLlamadas(ErrorMercadoPublico):
    """Se acabó el presupuesto de llamadas de esta vuelta."""


# ── TICKET (DPAPI de Windows) ────────────────────────────────────────────────

def ruta_ticket() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "QUEMPIN" / "mercado-publico.ticket"


def _dpapi(datos: bytes, proteger: bool) -> bytes:
    """CryptProtectData / CryptUnprotectData con la clave del usuario de
    Windows. Sin dependencias: ctypes."""
    if os.name != "nt":
        raise ErrorMercadoPublico("guardar el ticket cifrado requiere Windows; usa la variable "
                                  f"{VARIABLE_TICKET} en este equipo")
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(b: bytes) -> Blob:
        buffer = ctypes.create_string_buffer(b, len(b))
        return Blob(len(b), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    entrada, entropia, salida = blob(datos), blob(ENTROPIA_DPAPI), Blob()
    sin_interfaz = 0x1   # CRYPTPROTECT_UI_FORBIDDEN: nunca abrir un diálogo (corre en una tarea programada)
    if proteger:
        ok = crypt32.CryptProtectData(ctypes.byref(entrada), "QUEMPIN Mercado Publico", ctypes.byref(entropia),
                                      None, None, sin_interfaz, ctypes.byref(salida))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(entrada), None, ctypes.byref(entropia),
                                        None, None, sin_interfaz, ctypes.byref(salida))
    if not ok:
        raise ErrorMercadoPublico("Windows no pudo " + ("cifrar" if proteger else "descifrar")
                                  + " el ticket (¿otro usuario u otro equipo?): vuelve a configurarlo")
    try:
        return ctypes.string_at(salida.pbData, salida.cbData)
    finally:
        kernel32.LocalFree(salida.pbData)


def ticket_valido(texto: str) -> bool:
    return bool(_TICKET.match(texto or ""))


def guardar_ticket(ticket: str, ruta: Path | None = None) -> Path:
    ticket = (ticket or "").strip()
    if not ticket_valido(ticket):
        raise ValueError("el ticket no tiene el formato de Mercado Público (8-4-4-4-12 caracteres hexadecimales)")
    ruta = ruta or ruta_ticket()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    temporal.write_bytes(_dpapi(ticket.upper().encode("ascii"), proteger=True))
    os.replace(temporal, ruta)
    return ruta


def leer_ticket(ruta: Path | None = None) -> str:
    """La variable de entorno manda (pruebas, otro equipo); si no, el archivo
    cifrado. Nunca devuelve un texto con otro formato."""
    fijo = (os.environ.get(VARIABLE_TICKET) or "").strip()
    if fijo:
        if not ticket_valido(fijo):
            raise SinTicket(f"la variable {VARIABLE_TICKET} no tiene un ticket con formato válido")
        return fijo.upper()
    ruta = ruta or ruta_ticket()
    if not ruta.is_file():
        raise SinTicket("no hay ticket de Mercado Público en este equipo: configúralo con "
                        "«py -3.14 mercado_publico.py configurar»")
    ticket = _dpapi(ruta.read_bytes(), proteger=False).decode("ascii", "replace").strip()
    if not ticket_valido(ticket):
        raise SinTicket("el ticket guardado está dañado: vuelve a configurarlo")
    return ticket


def olvidar_ticket(ruta: Path | None = None) -> bool:
    ruta = ruta or ruta_ticket()
    if ruta.is_file():
        ruta.unlink()
        return True
    return False


# ── CLIENTE DE LA API ────────────────────────────────────────────────────────

def _abrir_https(url: str, tiempo: float) -> tuple[int, bytes]:
    """GET con verificación de certificado y tope de tamaño. Devuelve (código
    HTTP, cuerpo): la API responde sus errores con JSON aun con 500 o 203."""
    pedido = urllib.request.Request(url, headers={"Accept": "application/json",
                                                  "User-Agent": "QUEMPIN-monitor-licitaciones/1"})
    contexto = ssl.create_default_context()
    try:
        with urllib.request.urlopen(pedido, timeout=tiempo, context=contexto) as r:
            return r.status, r.read(MAX_BYTES_RESPUESTA + 1)
    except urllib.error.HTTPError as error:
        cuerpo = error.read(MAX_BYTES_RESPUESTA + 1) if error.fp else b""
        return error.code, cuerpo


class Cliente:
    """Llamadas a la API pública de ChileCompra, en serie y espaciadas."""

    def __init__(self, ticket: str, abrir=None, pausa: float = PAUSA_SEG, reintentos: int = REINTENTOS,
                 tope: int = LLAMADAS_POR_VUELTA, dormir=time.sleep, reloj=time.monotonic):
        if not ticket_valido(ticket):
            raise SinTicket("ticket con formato inválido")
        self._ticket = ticket
        # Se busca al construir (no al importar): las pruebas cortan la red reemplazando _abrir_https.
        self._abrir, self._dormir, self._reloj = abrir or _abrir_https, dormir, reloj
        self.pausa, self.reintentos, self.tope = pausa, reintentos, tope
        self.llamadas = 0
        self._ultima = None

    def censurar(self, texto) -> str:
        return str(texto).replace(self._ticket, "•••").replace(self._ticket.lower(), "•••")

    def _esperar_turno(self) -> None:
        if self._ultima is not None:
            falta = self.pausa - (self._reloj() - self._ultima)
            if falta > 0:
                self._dormir(falta)
        self._ultima = self._reloj()

    def obtener(self, recurso: str, **parametros) -> dict:
        """GET a API + recurso. Reintenta el 10500 («peticiones simultáneas»)
        con espera creciente; el ticket inválido corta todo."""
        if not re.fullmatch(r"[A-Za-z/]+\.json|Empresas/BuscarProveedor", recurso):
            raise ValueError(f"recurso no permitido: {recurso}")
        consulta = urllib.parse.urlencode(dict(parametros, ticket=self._ticket))
        url = f"{API}{recurso}?{consulta}"
        ultimo = "sin respuesta"
        for intento in range(self.reintentos):
            if self.llamadas >= self.tope:
                raise TopeDeLlamadas(f"tope de {self.tope} llamadas por vuelta")
            self._esperar_turno()
            self.llamadas += 1
            try:
                codigo_http, cuerpo = self._abrir(url, TIEMPO_LIMITE_SEG)
            except (OSError, ValueError) as error:      # URLError, timeout, certificado
                ultimo = f"sin conexión con Mercado Público ({type(error).__name__}: {self.censurar(error)[:160]})"
                self._dormir(self.pausa * (2 ** intento))
                continue
            if len(cuerpo) > MAX_BYTES_RESPUESTA:
                raise ErrorMercadoPublico("respuesta de Mercado Público demasiado grande")
            try:
                datos = json.loads(cuerpo.decode("utf-8-sig"))
            except (UnicodeDecodeError, ValueError):
                ultimo = f"respuesta que no es JSON (HTTP {codigo_http})"
                self._dormir(self.pausa * (2 ** intento))
                continue
            if not isinstance(datos, dict):
                raise ErrorMercadoPublico("respuesta de Mercado Público con forma inesperada")
            if "Listado" in datos or "listaEmpresas" in datos:
                return datos
            codigo = datos.get("Codigo")
            mensaje = self.censurar(_texto(datos.get("Mensaje"), 160))
            if codigo == 203:
                raise TicketInvalido("Mercado Público rechazó el ticket («Ticket no válido»): configúralo de nuevo")
            if codigo == 10500:
                ultimo = "Mercado Público pidió esperar (peticiones simultáneas)"
                self._dormir(self.pausa * (2 ** (intento + 1)))
                continue
            raise ErrorMercadoPublico(f"Mercado Público respondió {codigo}: {mensaje}")
        raise ErrorMercadoPublico(ultimo)

    # Consultas concretas
    def licitacion(self, codigo: str) -> dict | None:
        _exigir_codigo(codigo)
        listado = self.obtener("licitaciones.json", codigo=codigo).get("Listado") or []
        return listado[0] if listado and isinstance(listado[0], dict) else None

    def ordenes_del_dia(self, dia: date, proveedor: str = CODIGO_PROVEEDOR) -> list[dict]:
        datos = self.obtener("ordenesdecompra.json", fecha=dia.strftime("%d%m%Y"), CodigoProveedor=proveedor)
        return [x for x in datos.get("Listado") or [] if isinstance(x, dict)]

    def orden(self, codigo: str) -> dict | None:
        _exigir_codigo(codigo)
        listado = self.obtener("ordenesdecompra.json", codigo=codigo).get("Listado") or []
        return listado[0] if listado and isinstance(listado[0], dict) else None

    def proveedor(self, rut: str) -> list[dict]:
        return self.obtener("Empresas/BuscarProveedor", rutempresaproveedor=rut).get("listaEmpresas") or []


def _exigir_codigo(codigo: str) -> None:
    if not _CODIGO_EXACTO.match(codigo or ""):
        raise ValueError(f"código de Mercado Público inválido: {codigo!r}")


# ── LIMPIEZA DE LO QUE RESPONDE LA API ───────────────────────────────────────

def _texto(valor, largo: int = 200) -> str | None:
    if valor is None:
        return None
    limpio = "".join(c if unicodedata.category(c)[0] != "C" else " " for c in str(valor))
    limpio = re.sub(r"\s+", " ", limpio).strip()
    if not limpio:
        return None
    return limpio if len(limpio) <= largo else limpio[: largo - 1].rstrip() + "…"


def _numero(valor) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        return None
    return float(valor)


def _fecha(valor) -> str | None:
    """'2026-09-30T12:26:03.083' -> '2026-09-30T12:26'; el año 1900 es «sin fecha» en la API."""
    texto = _texto(valor, 40)
    if not texto or not re.match(r"^\d{4}-\d{2}-\d{2}", texto) or texto.startswith("1900"):
        return None
    return texto[:16] if len(texto) >= 16 and texto[10] == "T" else texto[:10]


def _url_sitio(valor) -> str | None:
    """Solo enlaces a www.mercadopublico.cl, siempre por HTTPS."""
    texto = _texto(valor, 500)
    if not texto:
        return None
    partes = urllib.parse.urlsplit(texto)
    if partes.scheme not in ("http", "https") or partes.hostname != SITIO:
        return None
    return urllib.parse.urlunsplit(("https", SITIO, partes.path, partes.query, ""))


def normalizar_rut(rut) -> str:
    return re.sub(r"[^0-9K]", "", str(rut or "").upper())


def es_quempin(rut) -> bool:
    return normalizar_rut(rut) == normalizar_rut(RUT_QUEMPIN)


def codigo_de(referencia) -> str | None:
    """El código de Mercado Público dentro de «ID o Referencia» (puede venir
    con texto alrededor). None si no hay."""
    m = PATRON_CODIGO.search(str(referencia or "").upper())
    return m.group(1) if m else None


def es_compra_agil(codigo: str) -> bool:
    return bool(re.search(r"-COT\d{2}$", codigo or ""))


def _redondear(x: float) -> int:
    return int(math.floor(x + 0.5))


# ── INTERPRETAR ──────────────────────────────────────────────────────────────

def leer_licitacion(crudo: dict | None, codigo: str) -> dict:
    """Lo que importa de una licitación, ya limpio. 'resultado' es el
    resultado para QUEMPIN (ganada, perdida, desierta…)."""
    base = {"codigo": codigo, "url": FICHA_LICITACION + urllib.parse.quote(codigo)}
    if crudo is None:
        return dict(base, resultado="compra-agil" if es_compra_agil(codigo) else "no-encontrada")
    estado_cod = crudo.get("CodigoEstado") if isinstance(crudo.get("CodigoEstado"), int) else None
    fechas = crudo.get("Fechas") if isinstance(crudo.get("Fechas"), dict) else {}
    adj = crudo.get("Adjudicacion") if isinstance(crudo.get("Adjudicacion"), dict) else {}
    comprador = crudo.get("Comprador") if isinstance(crudo.get("Comprador"), dict) else {}
    items = ((crudo.get("Items") or {}).get("Listado") if isinstance(crudo.get("Items"), dict) else None) or []

    por_proveedor: dict[str, dict] = {}
    for item in items:
        a = item.get("Adjudicacion") if isinstance(item, dict) else None
        if not isinstance(a, dict) or not normalizar_rut(a.get("RutProveedor")):
            continue
        cantidad, unitario = _numero(a.get("Cantidad")), _numero(a.get("MontoUnitario"))
        clave = normalizar_rut(a.get("RutProveedor"))
        p = por_proveedor.setdefault(clave, {"rut": _texto(a.get("RutProveedor"), 15),
                                             "nombre": _texto(a.get("NombreProveedor"), 120), "montoNeto": 0.0})
        if cantidad is not None and unitario is not None and cantidad >= 0 and unitario >= 0:
            p["montoNeto"] += cantidad * unitario
    adjudicados = sorted(({**p, "montoNeto": _redondear(p["montoNeto"])} for p in por_proveedor.values()),
                         key=lambda p: -p["montoNeto"])
    quempin = next((p for p in adjudicados if es_quempin(p["rut"])), None)

    estado = ESTADO_LICITACION.get(estado_cod, "otro")
    if estado == "adjudicada":
        resultado = "ganada" if quempin else ("perdida" if adjudicados else "adjudicada-sin-detalle")
    else:
        resultado = estado
    return dict(
        base,
        nombre=_texto(crudo.get("Nombre"), 160),
        comprador=_texto(comprador.get("NombreOrganismo"), 120),
        estado=_texto(crudo.get("Estado"), 40),
        resultado=resultado,
        moneda=_texto(crudo.get("Moneda"), 5),
        fechaCierre=_fecha(fechas.get("FechaCierre")),
        fechaAdjudicacion=_fecha(fechas.get("FechaAdjudicacion")) or _fecha(adj.get("Fecha")),
        fechaEstimadaAdjudicacion=_fecha(fechas.get("FechaEstimadaAdjudicacion")),
        oferentes=adj.get("NumeroOferentes") if isinstance(adj.get("NumeroOferentes"), int) else None,
        urlActa=_url_sitio(adj.get("UrlActa")),
        adjudicados=adjudicados,
        montoQuempin=quempin["montoNeto"] if quempin else None,
    )


def leer_orden(crudo: dict) -> dict | None:
    """Una OC emitida a QUEMPIN, ya limpia; None si no es de QUEMPIN (la API
    se filtra por proveedor, pero no se le cree a ciegas)."""
    codigo = _texto(crudo.get("Codigo"), 40)
    if not codigo or not _CODIGO_EXACTO.match(codigo):
        return None
    proveedor = crudo.get("Proveedor") if isinstance(crudo.get("Proveedor"), dict) else {}
    if proveedor and not (es_quempin(proveedor.get("RutSucursal")) or str(proveedor.get("Codigo")) == CODIGO_PROVEEDOR):
        return None
    fechas = crudo.get("Fechas") if isinstance(crudo.get("Fechas"), dict) else {}
    comprador = crudo.get("Comprador") if isinstance(crudo.get("Comprador"), dict) else {}
    nombre = _texto(crudo.get("Nombre"), 200)
    # De qué adquisición viene: el campo, o el código que el comprador escribe
    # en el nombre («… a compra ágil: 4321-7-COT26», «OC DESDE 5555-39-LE26»).
    origen = codigo_de(crudo.get("CodigoLicitacion"))
    if not origen:
        for texto in (crudo.get("Nombre"), crudo.get("Descripcion")):
            encontrados = [c for c in PATRON_CODIGO.findall(str(texto or "").upper()) if c != codigo]
            if encontrados:
                origen = encontrados[0]
                break
    return {
        "codigo": codigo,
        "nombre": nombre,
        "estado": _texto(crudo.get("Estado"), 40),
        "codigoEstado": crudo.get("CodigoEstado") if isinstance(crudo.get("CodigoEstado"), int) else None,
        "comprador": _texto(comprador.get("NombreOrganismo"), 120),
        "fecha": _fecha(fechas.get("FechaEnvio")) or _fecha(fechas.get("FechaCreacion")),
        "moneda": _texto(crudo.get("TipoMoneda"), 5),
        "totalNeto": _redondear(_numero(crudo.get("TotalNeto")) or 0) or None,
        "total": _redondear(_numero(crudo.get("Total")) or 0) or None,
        "adquisicion": origen,
        "url": FICHA_OC + urllib.parse.quote(codigo),
    }


# ── DECIDIR QUÉ SUGERIR ──────────────────────────────────────────────────────

def _fecha_corta(texto) -> str:
    try:
        return datetime.fromisoformat(str(texto)[:10]).strftime("%d-%m-%Y")
    except ValueError:
        return str(texto or "")


def _pesos(valor) -> str:
    return "$" + f"{_redondear(valor):,}".replace(",", ".")


def _estado_planilla(req: dict) -> str:
    return requerimientos.normalizar_encabezado(req.get("estado") or "")


def valor_con_iva(lic: dict | None, ordenes: list[dict]) -> tuple[int | None, str]:
    """El valor adjudicado con IVA y de dónde sale. Si las OC de esa
    adquisición suman exactamente el neto adjudicado, se usa su total real
    (trae el IVA que aplicó el comprador); si no, neto del acta + 19 %: en
    los contratos de mantención el acta es el total del contrato y cada OC
    es una entrega mensual (medido el 2026-10-13 sobre la Planilla real).
    Sin acta (Compra Ágil) se usan las OC."""
    ocs_clp = [o for o in ordenes if (o.get("moneda") or "CLP") == "CLP" and o.get("total")]
    neto_lic = (lic or {}).get("montoQuempin")
    if ocs_clp:
        neto_ocs = sum(o.get("totalNeto") or 0 for o in ocs_clp)
        total_ocs = sum(o["total"] for o in ocs_clp)
        if neto_lic is None or abs(neto_ocs - neto_lic) <= 1:
            n = len(ocs_clp)
            return total_ocs, f"total de {'la orden de compra' if n == 1 else f'las {n} órdenes de compra'}, IVA incluido"
    if neto_lic and (lic.get("moneda") or "CLP") == "CLP":
        return _redondear(neto_lic * (1 + IVA)), f"neto adjudicado {_pesos(neto_lic)} + 19 % IVA"
    return None, ""


def decidir(req: dict, lic: dict | None, ordenes: list[dict]) -> dict:
    """Qué hacer con un requerimiento según Mercado Público.
    {'cambios': {...} | None, 'motivo': str, 'revisar': str | None}.
    Regla: se sugiere solo lo que Mercado Público prueba; lo dudoso va a
    'revisar' (una persona decide) y nunca pisa lo que la Planilla ya dice."""
    estado = _estado_planilla(req)
    ganada = (lic or {}).get("resultado") == "ganada" or bool(ordenes)
    codigo = (lic or {}).get("codigo") or (ordenes[0]["adquisicion"] if ordenes else "")
    if ganada:
        valor, como = valor_con_iva(lic, ordenes)
        partes = []
        if lic and lic.get("resultado") == "ganada":
            partes.append(f"{codigo} adjudicada a QUEMPIN el {_fecha_corta(lic.get('fechaAdjudicacion'))}"
                          + (f" ({lic['oferentes']} oferentes)" if lic.get("oferentes") else ""))
        if ordenes:
            partes.append("orden de compra " + ", ".join(o["codigo"] for o in ordenes[:3])
                          + (f" de {ordenes[0]['comprador']}" if ordenes[0].get("comprador") else ""))
        motivo = "Mercado Público: " + "; ".join(partes) + (f". Valor: {_pesos(valor)} ({como})." if valor else ".")
        cambios = {}
        if estado != "adjudicado":
            cambios["estado"] = "Adjudicado"
        if valor and not req.get("valorAdjudicado"):
            cambios["valorAdjudicado"] = valor
        return {"cambios": cambios or None, "motivo": motivo, "revisar": None}

    resultado = (lic or {}).get("resultado")
    if resultado in ("perdida", "desierta", "revocada"):
        if resultado == "perdida":
            ganadores = ", ".join(f"{p['nombre'] or p['rut']} ({_pesos(p['montoNeto'])} neto)" for p in lic["adjudicados"][:2])
            motivo = f"Mercado Público: {codigo} adjudicada el {_fecha_corta(lic.get('fechaAdjudicacion'))} a {ganadores}."
        else:
            motivo = f"Mercado Público: {codigo} {TEXTO_RESULTADO[resultado].lower()}."
        if estado == "ofertado":
            return {"cambios": {"estado": "No adjudicado"}, "motivo": motivo, "revisar": None}
        if estado == "adjudicado":
            return {"cambios": None, "motivo": motivo,
                    "revisar": f"La planilla dice «Adjudicado», pero {motivo[len('Mercado Público: '):]} ¿Es el código correcto?"}
        if estado in ("evaluacion", ""):
            return {"cambios": None, "motivo": motivo,
                    "revisar": f"Sigue en «{req.get('estado') or 'sin estado'}» y la licitación ya se resolvió "
                               f"({TEXTO_RESULTADO[resultado].lower()}): si se ofertó, «No adjudicado»; si no, «Descartado»."}
    return {"cambios": None, "motivo": "", "revisar": None}


def _clave_sugerencia(numero: int, cambios: dict) -> str:
    return f"{numero}|" + json.dumps(cambios, sort_keys=True, ensure_ascii=False)


def mensaje_sugerencia(req: dict, codigo: str, cambios: dict, motivo: str) -> dict:
    return {
        "esquema": intercambio.ESQUEMA,
        "id": intercambio.nuevo_id(),
        "tipo": requerimientos.TIPO_SUGERENCIA,
        "destino": requerimientos.DESTINO,
        "origen": {"herramienta": HERRAMIENTA, "enviado": intercambio.ahora_iso()},
        "requerimiento": {"numero": req["numero"]},
        "cambios": cambios,
        # Lo que la planilla decía al sugerir: si alguien la cambia antes de
        # pasarla, requerimientos.decidir_sugerencia lo marca como conflicto.
        "reemplaza": {k: req.get(requerimientos.CAMPOS_SUGERIBLES[k]) for k in cambios},
        "fuente": {"herramienta": HERRAMIENTA, "codigo": codigo, "motivo": motivo},
    }


def _ya_pedido(pendientes: list[dict], numero: int, cambios: dict) -> bool:
    """Ya hay en el buzón una sugerencia (de cualquier herramienta) que pide
    lo mismo para ese N°."""
    for m in pendientes:
        if (m.get("requerimiento") or {}).get("numero") != numero:
            continue
        otros = m.get("cambios") or {}
        if all(k in otros and requerimientos._igual(otros[k], v) for k, v in cambios.items()):
            return True
    return False


# ── LA VUELTA ────────────────────────────────────────────────────────────────

def _leer_estado(ruta: Path) -> dict:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _hoy() -> date:
    return date.today()


def _barrer_ordenes(cliente: Cliente, estado: dict, hoy: date) -> None:
    """OC emitidas a QUEMPIN, día por día, de hoy hacia atrás. Un día ya
    barrido no se repite, salvo hoy y ayer. El avance se guarda día a día: si
    se acaba el tope de llamadas, la próxima vuelta sigue donde quedó."""
    ordenes = estado.setdefault("ordenes", {})
    limite = (hoy - timedelta(days=DIAS_HISTORIA_OC + 30)).isoformat()
    barridos = {d for d in estado.get("diasBarridos", []) if d >= limite}
    for i in range(DIAS_HISTORIA_OC):
        dia = hoy - timedelta(days=i)
        if i >= DIAS_REBARRIDO_OC and dia.isoformat() in barridos:
            continue
        for item in cliente.ordenes_del_dia(dia):
            codigo = _texto(item.get("Codigo"), 40)
            if not codigo or not _CODIGO_EXACTO.match(codigo):
                continue
            previa = ordenes.get(codigo)
            # Una OC reaparece en el día en que cambia de estado: solo entonces se vuelve a pedir su detalle.
            if previa is None or previa.get("codigoEstado") != item.get("CodigoEstado"):
                crudo = cliente.orden(codigo)
                leida = leer_orden(crudo) if crudo else None
                if leida:
                    ordenes[codigo] = leida
        if i >= DIAS_REBARRIDO_OC:
            barridos.add(dia.isoformat())
        estado["diasBarridos"] = sorted(barridos)
    viejas = (hoy - timedelta(days=400)).isoformat()
    for codigo in [c for c, o in ordenes.items() if (o.get("fecha") or "9999") < viejas]:
        del ordenes[codigo]


def _a_consultar(reqs: list[dict], cache: dict, ahora: datetime) -> tuple[list, list]:
    """(urgentes, verificar): pares (req, código) por consultar. Urgentes, los
    que esperan resultado; verificar, una pasada única por los ya cerrados
    (y de nuevo al mes)."""
    urgentes, verificar = [], []
    for r in reqs:
        codigo = codigo_de(r.get("referencia"))
        if not codigo or es_compra_agil(codigo):
            continue
        estado = _estado_planilla(r)
        if estado == "descartado":
            continue
        previa = cache.get(codigo)
        if previa and previa.get("resultado") in FINALES:
            try:
                edad = ahora - datetime.fromisoformat(previa["_consultado"])
            except (KeyError, ValueError):
                edad = timedelta(days=DIAS_VIGENCIA_FINAL + 1)
            if edad < timedelta(days=DIAS_VIGENCIA_FINAL):
                continue
        (urgentes if estado in ("ofertado", "evaluacion", "") else verificar).append((r, codigo))
    return urgentes, verificar


def revisar(raiz: Path, cliente: Cliente | None = None, enviar: bool = True,
            ruta_estado: Path | None = None, hoy: date | None = None) -> dict:
    """Una vuelta completa. Devuelve el resumen. Con 'enviar' deja las
    sugerencias en el buzón y publica licitaciones.json; sin él solo
    consulta (actualiza la caché local) y dice qué haría."""
    hoy = hoy or _hoy()
    ahora = datetime.now()
    ruta_estado = ruta_estado or RUTA_ESTADO
    cliente = cliente or Cliente(leer_ticket())
    estado = _leer_estado(ruta_estado)
    cache = estado.setdefault("licitaciones", {})
    avisos: list[str] = []
    incompleta = False

    sobre = intercambio.leer_publicacion(raiz, requerimientos.PUBLICACION)
    reqs = ((sobre or {}).get("datos") or {}).get("requerimientos") or []
    if not reqs:
        avisos.append("No hay Planilla de Ingreso publicada: solo se revisaron las órdenes de compra.")

    def consultar(pares):
        for _, codigo in pares:
            lic = leer_licitacion(cliente.licitacion(codigo), codigo)
            lic["_consultado"] = ahora.isoformat(timespec="seconds")
            cache[codigo] = lic

    urgentes, verificar = _a_consultar(reqs, cache, ahora)
    try:
        consultar(urgentes)            # lo que espera resultado va primero
        _barrer_ordenes(cliente, estado, hoy)
        consultar(verificar)
    except TopeDeLlamadas:
        incompleta = True
        avisos.append("Se alcanzó el tope de consultas de esta vuelta: lo que falta se revisa en la próxima.")
    finally:
        estado["actualizado"] = ahora.isoformat(timespec="seconds")
        intercambio._escribir_json_atomico(ruta_estado, estado)

    ordenes = list(estado.get("ordenes", {}).values())
    por_adquisicion: dict[str, list[dict]] = {}
    for o in ordenes:
        if o.get("adquisicion"):
            por_adquisicion.setdefault(o["adquisicion"], []).append(o)

    pendientes_buzon, _ = intercambio.leer_buzon(raiz, destino=requerimientos.DESTINO, tipo=requerimientos.TIPO_SUGERENCIA)
    enviadas = estado.setdefault("sugerenciasEnviadas", {})
    filas, revisar_lista, sugeridas = [], [], []
    codigos_de_reqs = set()
    for r in reqs:
        codigo = codigo_de(r.get("referencia"))
        if not codigo:
            continue
        codigos_de_reqs.add(codigo)
        lic = cache.get(codigo)
        ocs = sorted(por_adquisicion.get(codigo, []), key=lambda o: o.get("fecha") or "")
        if lic is None and not es_compra_agil(codigo):
            # Todavía no se consulta la licitación (tope de llamadas): sus OC solas pueden ser
            # entregas parciales de un contrato, y el monto saldría mal. Se decide en la próxima vuelta.
            continue
        if lic is None and not ocs:
            if _estado_planilla(r) != "ofertado":
                continue
            lic = leer_licitacion(None, codigo)
        d = decidir(r, lic, ocs)
        fila = {k: v for k, v in (lic or leer_licitacion(None, codigo)).items() if not k.startswith("_")}
        if ocs and fila["resultado"] in ("compra-agil", "no-encontrada", "en-evaluacion", "adjudicada-sin-detalle"):
            fila["resultado"] = "ganada"
        fila.update(req=r["numero"], titulo=_texto(r.get("titulo"), 160), planilla=r.get("estado"),
                    ordenes=[o["codigo"] for o in ocs], motivo=d["motivo"] or None)
        filas.append(fila)
        if d["revisar"]:
            revisar_lista.append({"req": r["numero"], "codigo": codigo, "texto": d["revisar"]})
        if d["cambios"]:
            clave = _clave_sugerencia(r["numero"], d["cambios"])
            if clave in enviadas or _ya_pedido(pendientes_buzon, r["numero"], d["cambios"]):
                continue
            if enviar:
                # Una sugerencia anterior del monitor para el mismo N°, con otro dato, queda reemplazada:
                # en el buzón nunca hay dos versiones de lo mismo esperando a una persona.
                for viejo in pendientes_buzon:
                    if ((viejo.get("origen") or {}).get("herramienta") == HERRAMIENTA
                            and (viejo.get("requerimiento") or {}).get("numero") == r["numero"]):
                        intercambio.archivar(raiz, viejo, "reemplazado",
                                             ["Mercado Público tiene un dato más reciente: ver la sugerencia nueva."],
                                             extra={"requerimiento": r["numero"]})
                intercambio.enviar(raiz, mensaje_sugerencia(r, codigo, d["cambios"], d["motivo"]))
                enviadas[clave] = intercambio.ahora_iso()
            sugeridas.append({"req": r["numero"], "codigo": codigo, "cambios": d["cambios"]})
    if enviar:
        intercambio._escribir_json_atomico(ruta_estado, estado)

    limite_oc = (hoy - timedelta(days=DIAS_HISTORIA_OC)).isoformat()
    sin_req = [o for o in ordenes if (o.get("fecha") or "") >= limite_oc
               and (o.get("adquisicion") not in codigos_de_reqs)]
    datos = publicacion(filas, ordenes, sin_req, revisar_lista, avisos, incompleta, ahora)
    sobre_pub = {"esquema": intercambio.ESQUEMA, "herramienta": HERRAMIENTA, "generado": intercambio.ahora_iso(), "datos": datos}
    errores = esquemas.validar_publicacion(PUBLICACION, sobre_pub)
    if errores:
        raise ValueError("licitaciones.json no cumple su esquema: " + "; ".join(errores[:5]))
    if enviar:
        intercambio.publicar(raiz, PUBLICACION, HERRAMIENTA, datos)
    return {"llamadas": cliente.llamadas, "licitaciones": len(filas), "ordenes": len(ordenes),
            "sugeridas": sugeridas, "revisar": revisar_lista, "sinRequerimiento": sin_req,
            "incompleta": incompleta, "avisos": avisos}


def publicacion(filas, ordenes, sin_req, revisar_lista, avisos, incompleta, ahora) -> dict:
    cuenta = {r: sum(1 for f in filas if f["resultado"] == r) for r in ("ganada", "perdida", "desierta", "revocada")}
    resueltas = cuenta["ganada"] + cuenta["perdida"]
    hace_un_anio = (ahora - timedelta(days=365)).date().isoformat()
    return {
        "proveedor": {"rut": RUT_QUEMPIN, "codigo": CODIGO_PROVEEDOR, "nombre": "QUEMPIN SPA"},
        "consultado": ahora.astimezone().isoformat(timespec="seconds"),
        "completo": not incompleta,
        "licitaciones": sorted(filas, key=lambda f: -f["req"]),
        "ordenes": sorted((o for o in ordenes if (o.get("fecha") or "") >= hace_un_anio),
                          key=lambda o: o.get("fecha") or "", reverse=True),
        "ordenesSinRequerimiento": [o["codigo"] for o in sorted(sin_req, key=lambda o: o.get("fecha") or "", reverse=True)],
        "revisar": revisar_lista,
        "resumen": {
            "ganadas": cuenta["ganada"], "perdidas": cuenta["perdida"],
            "desiertas": cuenta["desierta"] + cuenta["revocada"],
            "enEspera": sum(1 for f in filas if f["resultado"] in ("abierta", "en-evaluacion", "suspendida", "compra-agil")),
            # Solo lo que Mercado Público ya resolvió con un ganador.
            "tasaAdjudicacion": round(cuenta["ganada"] / resueltas, 4) if resueltas else None,
        },
        "avisos": avisos,
    }


# ── LÍNEA DE COMANDOS ────────────────────────────────────────────────────────

def _raiz() -> Path | None:
    import ubicacion
    raiz = ubicacion.ubicar_intercambio(AQUI)
    if raiz is None or not intercambio.es_carpeta_de_intercambio(raiz):
        print("[AVISO] No se encontró la carpeta de intercambio (biblioteca «Formulación de proyectos» sin sincronizar).")
        return None
    return raiz


def cmd_configurar() -> int:
    if sys.stdin.isatty():
        import getpass
        ticket = getpass.getpass("Ticket de la API de Mercado Público (no se muestra al escribir): ")
    else:
        ticket = sys.stdin.readline()
    ticket = ticket.strip()
    if not ticket_valido(ticket):
        print("[ERROR] Eso no tiene el formato de un ticket de Mercado Público (8-4-4-4-12 caracteres).")
        return 1
    try:
        empresas = Cliente(ticket.upper()).proveedor(RUT_QUEMPIN)
    except ErrorMercadoPublico as error:
        print(f"[ERROR] No se pudo comprobar el ticket: {error}")
        return 1
    if not any(str(e.get("CodigoEmpresa")) == CODIGO_PROVEEDOR for e in empresas if isinstance(e, dict)):
        print(f"[ERROR] El ticket funciona, pero QUEMPIN SPA ({RUT_QUEMPIN}) no aparece con el código {CODIGO_PROVEEDOR}.")
        return 1
    ruta = guardar_ticket(ticket)
    print(f"[OK] Ticket comprobado (QUEMPIN SPA, proveedor {CODIGO_PROVEEDOR}) y guardado cifrado para este usuario de Windows:")
    print(f"     {ruta}")
    return 0


def cmd_revisar(enviar: bool) -> int:
    raiz = _raiz()
    if raiz is None:
        return 1
    try:
        r = revisar(raiz, enviar=enviar)
    except ErrorMercadoPublico as error:
        print(f"[ERROR] {error}")
        return 1
    print(f"Mercado Público: {r['licitaciones']} licitación(es) de la planilla, {r['ordenes']} orden(es) de compra "
          f"a QUEMPIN, {r['llamadas']} consulta(s) a la API.")
    for s in r["sugeridas"]:
        cambios = ", ".join(f"{k} = {v}" for k, v in s["cambios"].items())
        print(f"  {'Sugerido' if enviar else 'Se sugeriría'} a la planilla · N° {s['req']} ({s['codigo']}): {cambios}")
    for x in r["revisar"]:
        print(f"  Revisar · N° {x['req']} ({x['codigo']}): {x['texto']}")
    if r["sinRequerimiento"]:
        print(f"  {len(r['sinRequerimiento'])} orden(es) de compra a QUEMPIN sin requerimiento en la planilla: "
              + ", ".join(o["codigo"] for o in r["sinRequerimiento"][:8]))
    for a in r["avisos"]:
        print(f"  [AVISO] {a}")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except AttributeError:
        pass
    orden = argv[0] if argv else ""
    if orden == "configurar":
        return cmd_configurar()
    if orden == "olvidar":
        print("[OK] Ticket borrado de este equipo." if olvidar_ticket() else "[INFO] No había ticket guardado.")
        return 0
    if orden in ("revisar", "status"):
        return cmd_revisar(enviar=orden == "revisar")
    print(__doc__.split("Uso:")[1])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
