# -*- coding: utf-8 -*-
"""
calibrar_oportunidades.py -- ¿Qué tan bien acierta la nota de oportunidades?
(2026-10-14).

Por qué existe: el usuario pidió «mejorar la precisión de las notas» y un
correo cuando una oportunidad pasa de 85. Para saber si una nota acierta hace
falta compararla con algo: la Planilla de Ingreso tiene 305 requerimientos con
la decisión que tomó QUEMPIN (ofertar o descartar), y casi todos traen el
código de Mercado Público. Este módulo evalúa cada uno con el motor de
``oportunidades.py`` como si se viera el día después de publicado, y mide:

- **AUC**: la probabilidad de que una licitación ofertada saque más nota que
  una descartada (0,5 = al azar, 1 = perfecto).
- **Tasa de oferta por tramo de nota**: de las que sacan 85 o más, cuántas se
  ofertaron. Es la precisión del correo.

Cada caso se evalúa **sin sí mismo** en la historia (si no, el parecido con
su propio título lo delata). Las fichas se bajan una vez a
``oportunidades_estado_calibracion.json`` (gitignoreado, datos públicos).

Uso:
    py -3.14 calibrar_oportunidades.py descargar   # baja las fichas que falten (unos 10 minutos la primera vez)
    py -3.14 calibrar_oportunidades.py medir       # AUC y tasa de oferta por tramo, sin consultar la API
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import compra_agil as ca  # noqa: E402
import intercambio  # noqa: E402
import mercado_publico as mp  # noqa: E402
import oportunidades as op  # noqa: E402
import requerimientos  # noqa: E402

RUTA_CACHE = AQUI / "oportunidades_estado_calibracion.json"
TRAMOS = (85, 75, 60, 45, 0)


def _reqs(raiz) -> list[dict]:
    sobre = intercambio.leer_publicacion(raiz, requerimientos.PUBLICACION) if raiz else None
    return ((sobre or {}).get("datos") or {}).get("requerimientos") or []


def etiqueta(req: dict) -> bool | None:
    """True si QUEMPIN la ofertó, False si la descartó, None si sigue abierta."""
    estado = requerimientos.normalizar_encabezado(req.get("estado") or "")
    if estado in op.ESTADOS_OFERTADOS:
        return True
    if estado == "descartado":
        return False
    return None


def descargar(raiz, ruta: Path = RUTA_CACHE, tope: int = 400) -> dict:
    cache = op._leer_estado(ruta)
    fichas = cache.setdefault("fichas", {})
    faltan = [c for c in dict.fromkeys(mp.codigo_de(r.get("referencia")) for r in _reqs(raiz)) if c and c not in fichas]
    faltan.sort(key=ca.es_codigo)        # primero las licitaciones: la API de Compra Ágil es lenta y a veces da 504
    ticket = mp.leer_ticket()
    # Un solo intento en Compra Ágil: lo que falla (504, sobre todo las de 2025) se reintenta en otra corrida.
    cli, cli_ca = mp.Cliente(ticket, tope=tope), ca.Cliente(ticket, tope=tope, reintentos=1)
    hechas = 0
    try:
        for codigo in faltan:
            try:
                if ca.es_codigo(codigo):
                    crudo = cli_ca.detalle(codigo)
                    fichas[codigo] = ca.leer_ficha(crudo, codigo) if crudo else {"codigo": codigo, "noEncontrada": True}
                elif mp._CODIGO_EXACTO.match(codigo):
                    crudo = cli.licitacion(codigo)
                    fichas[codigo] = op.leer_ficha(crudo, codigo) if crudo else {"codigo": codigo, "noEncontrada": True}
            except (mp.TopeDeLlamadas, ca.CuotaAgotada, mp.TicketInvalido):
                raise
            except mp.ErrorMercadoPublico as error:     # una sola que falla (504) no frena las demás; se reintenta después
                print(f"  [AVISO] {codigo}: {error}")
            hechas += 1
            if hechas % 20 == 0:
                intercambio._escribir_json_atomico(ruta, cache)
                print(f"  {hechas} de {len(faltan)}", flush=True)
    except (mp.TopeDeLlamadas, ca.CuotaAgotada) as error:
        print(f"[AVISO] {error}: lo que falta sigue en la próxima corrida")
    finally:
        intercambio._escribir_json_atomico(ruta, cache)
    return {"bajadas": hechas, "faltaban": len(faltan), "total": len(fichas)}


def casos(raiz, config: dict | None = None, ruta: Path = RUTA_CACHE, reqs: list[dict] | None = None,
          mercado: list[dict] | None = None) -> list[dict]:
    """Cada requerimiento con decisión y ficha, evaluado sin sí mismo en la
    historia, como si se mirara el día después de publicado."""
    config = config or op.cargar_config()
    reqs = reqs if reqs is not None else _reqs(raiz)
    fichas = op._leer_estado(ruta).get("fichas") or {}
    if mercado is None:
        estado = op._leer_estado(op.RUTA_ESTADO)
        mercado = [m for m in (estado.get("mercado") or {}).values() if isinstance(m, dict) and m.get("ganadores")]
    uf = op.valor_uf(config)
    salida = []
    for i, req in enumerate(reqs):
        lab = etiqueta(req)
        codigo = mp.codigo_de(req.get("referencia"))
        ficha = fichas.get(codigo) if codigo else None
        if lab is None or not ficha or ficha.get("noEncontrada") or not ficha.get("nombre"):
            continue
        otros = [r for j, r in enumerate(reqs) if j != i and mp.codigo_de(r.get("referencia")) != codigo]
        publicada = ficha.get("publicada") or ficha.get("cierre")
        try:
            # Una compra ágil se cotiza en horas: se mira 3 horas después de publicada; una licitación, al día siguiente.
            ahora = (datetime.fromisoformat(publicada if len(publicada) > 10 else publicada + "T09:00")
                     + (timedelta(hours=3) if ficha.get("compraAgil") else timedelta(days=1)))
        except (TypeError, ValueError):
            continue
        ev = op.Evaluador(config, op.Historia(otros), [m for m in mercado if m.get("codigo") != codigo], ahora, uf)
        r = ev.evaluar(ficha)
        salida.append({"req": req.get("numero"), "codigo": codigo, "ofertada": lab, "ganada": requerimientos.normalizar_encabezado(req.get("estado") or "") == "adjudicado",
                       "compraAgil": bool(ficha.get("compraAgil")), "puntaje": r["puntaje"], "categoria": r["categoria"],
                       "criterios": {k: c["puntaje"] for k, c in r["criterios"].items()}, "nombre": ficha.get("nombre"),
                       "evaluada": bool(req.get("evaluador")), "parecidas": r["parecidas"]})
    return salida


def auc(positivos: list[float], negativos: list[float]) -> float | None:
    if not positivos or not negativos:
        return None
    gana = sum((p > n) + 0.5 * (p == n) for p in positivos for n in negativos)
    return gana / (len(positivos) * len(negativos))


def medir(lista: list[dict]) -> dict:
    """AUC y tasa de oferta por tramo de nota (una descartada por el motor
    cuenta con nota 0: el correo nunca la manda)."""
    def nota(c):
        return 0 if c["categoria"] == "descartar" else c["puntaje"]
    tramos = []
    for desde, hasta in zip(TRAMOS, (None,) + TRAMOS[:-1]):
        dentro = [c for c in lista if nota(c) >= desde and (hasta is None or nota(c) < hasta)]
        tramos.append({"desde": desde, "hasta": hasta, "casos": len(dentro), "ofertadas": sum(c["ofertada"] for c in dentro)})
    return {
        "casos": len(lista), "ofertadas": sum(c["ofertada"] for c in lista),
        "auc": auc([nota(c) for c in lista if c["ofertada"]], [nota(c) for c in lista if not c["ofertada"]]),
        "tramos": tramos,
    }


def _imprimir(nombre: str, m: dict) -> None:
    a = m["auc"]
    print(f"{nombre}: {m['casos']} casos, {m['ofertadas']} ofertados; AUC {a:.3f}" if a is not None else f"{nombre}: sin casos")
    for t in m["tramos"]:
        if t["casos"]:
            rango = f"{t['desde']}+" if t["hasta"] is None else f"{t['desde']}–{t['hasta']}"
            print(f"   nota {rango:<7} {t['casos']:>4} casos, {t['ofertadas']:>3} ofertadas ({100 * t['ofertadas'] / t['casos']:.0f} %)")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except AttributeError:
        pass
    orden = argv[0] if argv else ""
    if orden not in ("descargar", "medir"):
        print(__doc__.split("Uso:")[1])
        return 2
    raiz = op._raiz()
    if raiz is None:
        return 1
    if orden == "descargar":
        print(descargar(raiz))
        return 0
    lista = casos(raiz)
    _imprimir("Todas", medir(lista))
    _imprimir("Licitaciones", medir([c for c in lista if not c["compraAgil"]]))
    _imprimir("Compras ágiles", medir([c for c in lista if c["compraAgil"]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
