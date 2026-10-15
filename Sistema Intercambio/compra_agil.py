# -*- coding: utf-8 -*-
"""
compra_agil.py -- Cliente de la API de Compra Ágil de Mercado Público
(2026-10-14).

Por qué existe: el usuario pidió que la evaluación de oportunidades cubra
«licitaciones y compras ágiles». La API de licitaciones (v1, la de
``mercado_publico.py``) no expone las Compras Ágiles (COT): ChileCompra abrió
en mayo de 2026 una API aparte, «API Compra Ágil v2» (guía de uso v3.0,
https://www.chilecompra.cl/api/). Usa el mismo ticket, pero va en un header
HTTP (no en la URL), tiene cuota diaria (error 429) y responde
``{"success", "payload", "errors"}``.

Medido el 2026-10-14 con el ticket de QUEMPIN:
- Las fechas vienen como «2026-10-15 12:00» en hora de Chile, aunque algunos
  campos lleven una «Z» que no corresponde (el cierre del listado y el
  «fecha_cierre_primer_llamado» con Z tienen la misma hora).
- ``q`` busca en el nombre y la descripción: «caldera» trae también
  «Adquisición de mobiliario». El prefiltro de oportunidades.py decide.
- Es lenta y a veces no responde (504): el cliente tiene un presupuesto de
  tiempo por vuelta (``limite_seg``) además del tope de llamadas.

SEGURIDAD: el mismo ticket cifrado con DPAPI que el monitor
(``mercado_publico.leer_ticket``), solo HTTPS a api2.mercadopublico.cl con
verificación de certificado, tiempo límite y tamaño máximo; el ticket se
censura en todo mensaje. Lo que responde la API es dato no confiable: códigos
validados antes de ir a la URL, textos limpios y acortados, sin correos ni
teléfonos de funcionarios.
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import mercado_publico as mp

API = "https://api2.mercadopublico.cl/v2/compra-agil"
FICHA = "https://buscador.mercadopublico.cl/ficha?code="   # ficha pública (verificada en un navegador el 2026-10-14)
PAUSA_SEG = 1.0
REINTENTOS = 2
LLAMADAS_POR_VUELTA = 80
TIEMPO_LIMITE_SEG = 35       # el 504 de la API llega a los ~30 s
# Medido el 2026-10-15: con la API lenta, cada búsqueda tardaba 15 a 20 s y
# «caldera» daba 504 a los 30 s aunque se acotara por fecha o por página. Sin
# un tope de tiempo, 26 búsquedas con reintentos podían pasar los 45 minutos
# de la tarea diaria y no se publicaba nada.
TAMANO_PAGINA = 50
_CODIGO = re.compile(r"^\d{1,9}-\d{1,7}-COT\d{2}$")


class CuotaAgotada(mp.ErrorMercadoPublico):
    """La API de Compra Ágil respondió 429: la cuota del día se acabó."""


def _abrir_https(url: str, tiempo: float, encabezados: dict) -> tuple[int, bytes]:
    pedido = urllib.request.Request(url, headers=dict(encabezados, **{
        "Accept": "application/json", "User-Agent": "QUEMPIN-oportunidades/1"}))
    try:
        with urllib.request.urlopen(pedido, timeout=tiempo, context=ssl.create_default_context()) as r:
            return r.status, r.read(mp.MAX_BYTES_RESPUESTA + 1)
    except urllib.error.HTTPError as error:
        return error.code, (error.read(mp.MAX_BYTES_RESPUESTA + 1) if error.fp else b"")


def es_codigo(codigo) -> bool:
    return bool(_CODIGO.match(str(codigo or "")))


class Cliente:
    """Llamadas a la API de Compra Ágil, en serie, espaciadas y con tope."""

    def __init__(self, ticket: str, abrir=None, pausa: float = PAUSA_SEG, reintentos: int = REINTENTOS,
                 tope: int = LLAMADAS_POR_VUELTA, dormir=time.sleep, reloj=time.monotonic,
                 limite_seg: float | None = None):
        if not mp.ticket_valido(ticket):
            raise mp.SinTicket("ticket con formato inválido")
        self._ticket = ticket
        self._abrir, self._dormir, self._reloj = abrir or _abrir_https, dormir, reloj
        self.pausa, self.reintentos, self.tope, self.limite_seg = pausa, reintentos, tope, limite_seg
        self.llamadas = 0
        self._ultima = None
        self._inicio = reloj()

    def censurar(self, texto) -> str:
        return str(texto).replace(self._ticket, "•••").replace(self._ticket.lower(), "•••")

    def fraccion_usada(self) -> float:
        """Qué parte del tiempo de la vuelta ya se usó (0 si no hay límite)."""
        return 0.0 if not self.limite_seg else (self._reloj() - self._inicio) / self.limite_seg

    def _esperar_turno(self) -> None:
        if self._ultima is not None:
            falta = self.pausa - (self._reloj() - self._ultima)
            if falta > 0:
                self._dormir(falta)
        self._ultima = self._reloj()

    def _obtener(self, ruta: str, parametros: dict) -> dict | None:
        """GET; devuelve el payload, o None si la API dice 404 (no existe)."""
        url = API + ruta + ("?" + urllib.parse.urlencode(parametros) if parametros else "")
        ultimo = "sin respuesta"
        for intento in range(self.reintentos):
            if self.llamadas >= self.tope:
                raise mp.TopeDeLlamadas(f"tope de {self.tope} llamadas de Compra Ágil por vuelta")
            if self.limite_seg is not None and self._reloj() - self._inicio >= self.limite_seg:
                raise mp.TopeDeLlamadas(f"se acabaron los {self.limite_seg / 60:.0f} minutos para Compra Ágil de esta vuelta")
            self._esperar_turno()
            self.llamadas += 1
            try:
                codigo_http, cuerpo = self._abrir(url, TIEMPO_LIMITE_SEG, {"ticket": self._ticket})
            except (OSError, ValueError) as error:
                ultimo = f"sin conexión con Compra Ágil ({type(error).__name__}: {self.censurar(error)[:160]})"
                self._dormir(self.pausa * (2 ** (intento + 1)))
                continue
            if codigo_http in (401, 403):
                raise mp.TicketInvalido("la API de Compra Ágil rechazó el ticket")
            if codigo_http == 429:
                raise CuotaAgotada("se acabó la cuota diaria de la API de Compra Ágil (vuelve mañana)")
            if codigo_http == 404:
                return None
            if len(cuerpo) > mp.MAX_BYTES_RESPUESTA:
                raise mp.ErrorMercadoPublico("respuesta de Compra Ágil demasiado grande")
            try:
                datos = json.loads(cuerpo.decode("utf-8-sig"))
            except (UnicodeDecodeError, ValueError):
                ultimo = f"respuesta de Compra Ágil que no es JSON (HTTP {codigo_http})"
                self._dormir(self.pausa * (2 ** (intento + 1)))
                continue
            if codigo_http >= 500:
                ultimo = f"Compra Ágil respondió HTTP {codigo_http}"
                self._dormir(self.pausa * (2 ** (intento + 1)))
                continue
            if not isinstance(datos, dict) or datos.get("success") != "OK" or not isinstance(datos.get("payload"), dict):
                errores = datos.get("errors") if isinstance(datos, dict) else None
                primero = errores[0] if isinstance(errores, list) and errores and isinstance(errores[0], dict) else {}
                raise mp.ErrorMercadoPublico(f"Compra Ágil respondió HTTP {codigo_http}: "
                                             + self.censurar(mp._texto(primero.get("mensaje"), 160) or "error"))
            return datos["payload"]
        raise mp.ErrorMercadoPublico(ultimo)

    def buscar(self, q: str, estado: str = "publicada", max_paginas: int = 4) -> list[dict]:
        """Las compras ágiles que nombran «q» (en el nombre o la descripción)."""
        items, pagina = [], 1
        while pagina <= max_paginas:
            payload = self._obtener("", {"q": q, "estado": estado, "tamano_pagina": TAMANO_PAGINA,
                                         "numero_pagina": pagina}) or {}
            items += [x for x in payload.get("items") or [] if isinstance(x, dict)]
            paginas = (payload.get("paginacion") or {}).get("total_paginas")
            if not isinstance(paginas, int) or pagina >= paginas:
                break
            pagina += 1
        return items

    def detalle(self, codigo: str) -> dict | None:
        if not es_codigo(codigo):
            raise ValueError(f"código de Compra Ágil inválido: {codigo!r}")
        return self._obtener("/" + urllib.parse.quote(codigo), {})


# ── LEER ─────────────────────────────────────────────────────────────────────

def fecha(valor) -> str | None:
    """«2026-10-15 12:00» o «2026-10-15T12:00:00Z» -> «2026-10-15T12:00» (hora de Chile)."""
    texto = mp._texto(valor, 40)
    if not texto or not re.match(r"^\d{4}-\d{2}-\d{2}", texto):
        return None
    return mp._fecha(texto.replace(" ", "T", 1).rstrip("Z"))


def leer_listado(item: dict) -> dict | None:
    """Lo mínimo de una fila del listado: para el prefiltro y para saber si
    la ficha guardada sigue al día."""
    codigo = mp._texto(item.get("codigo"), 40)
    if not es_codigo(codigo):
        return None
    fechas = item.get("fechas") if isinstance(item.get("fechas"), dict) else {}
    estado = item.get("estado") if isinstance(item.get("estado"), dict) else {}
    montos = item.get("montos") if isinstance(item.get("montos"), dict) else {}
    inst = item.get("institucion") if isinstance(item.get("institucion"), dict) else {}
    monto = mp._numero(montos.get("monto_disponible_clp"))
    # Región, monto y organismo también vienen en el listado: si la ficha no
    # alcanza a pedirse (API lenta), la evaluación por el nombre los usa igual.
    return {"codigo": codigo, "nombre": mp._texto(item.get("nombre"), 200), "cierre": fecha(fechas.get("fecha_cierre")),
            "cambio": mp._texto(fechas.get("fecha_ultimo_cambio"), 40), "estado": mp._texto(estado.get("codigo"), 30),
            "region": mp._texto(inst.get("nombre_region"), 80), "organismo": mp._texto(inst.get("organismo_comprador"), 120),
            "monto": monto if monto and monto > 0 else None}


def leer_ficha(crudo: dict, codigo: str) -> dict:
    """La ficha de una compra ágil con las mismas claves que
    ``oportunidades.leer_ficha`` de una licitación, para evaluarla igual.
    Sin nombres ni contactos de funcionarios."""
    from oportunidades import _sin_contactos      # import tardío: oportunidades importa este módulo

    def dic(x):
        return x if isinstance(x, dict) else {}
    inst, fechas, conv = dic(crudo.get("institucion")), dic(crudo.get("fechas")), dic(crudo.get("convocatoria"))
    pres, entrega, resumen, estado = dic(crudo.get("presupuesto")), dic(crudo.get("entrega")), dic(crudo.get("resumen")), dic(crudo.get("estado"))
    productos = [p for p in crudo.get("productos_solicitados") or [] if isinstance(p, dict)]
    monto = mp._numero(pres.get("monto_disponible_clp")) or mp._numero(pres.get("presupuesto_estimado"))
    plazo = entrega.get("plazo_entrega_dias")
    plazo = plazo if isinstance(plazo, int) and not isinstance(plazo, bool) and plazo > 0 else None
    textos_prod = [t for p in productos[:8] for t in (mp._texto(p.get("nombre"), 80), mp._texto(p.get("descripcion"), 160)) if t]
    return {
        "codigo": codigo,
        "compraAgil": True,
        "nombre": mp._texto(crudo.get("nombre"), 200),
        "descripcion": _sin_contactos(mp._texto(crudo.get("descripcion"), 1200)),
        "estado": mp._texto(estado.get("codigo"), 30),
        "estadoCodigo": None,
        "tipo": "COT",
        "moneda": "CLP",
        "organismo": mp._texto(inst.get("organismo_comprador"), 120),
        "unidadCompra": mp._texto(inst.get("unidad_compra"), 120),
        "comuna": None,
        "region": mp._texto(inst.get("nombre_region"), 80),
        "reclamos": None,
        "publicada": fecha(fechas.get("fecha_publicacion")),
        "cierre": fecha(fechas.get("fecha_cierre")),
        "cambio": mp._texto(fechas.get("fecha_ultimo_cambio"), 40),
        "llamado": conv.get("estado_convocatoria") if conv.get("estado_convocatoria") in (1, 2) else None,
        "visita": None,
        "direccionVisita": None,
        "montoEstimado": monto if monto and monto > 0 else None,
        "duracion": plazo,
        "unidadDuracion": 2 if plazo else None,      # días
        "renovable": False,
        "obras": False,
        "etapas": None,
        "tomaRazon": False,
        "items": len(productos),
        "categorias": [],
        "productos": textos_prod,
        "ofertasRecibidas": resumen.get("total_ofertas_recibidas") if isinstance(resumen.get("total_ofertas_recibidas"), int) else None,
    }
