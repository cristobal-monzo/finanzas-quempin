# -*- coding: utf-8 -*-
"""El Portal en el teléfono (2026-11-18, fase C del plan del Portal): un resumen cifrado de la carpeta de Intercambio.

    py -3.14 resumen_movil.py            # arma el resumen y dice qué cambió y cuánto pesa, sin publicar
    py -3.14 resumen_movil.py publicar   # lo arma y, si toca, lo sube a gh-pages (lo corre la tarea del procesador)

En el teléfono (y en Safari o Firefox) el Portal no puede abrir la carpeta del equipo: el navegador no tiene
showDirectoryPicker. Este resumen lleva lo que el Portal lee de ella, cifrado con el candado de los tableros, y el
Portal lo abre como una carpeta de solo lectura (js/resumen.js): las vistas leen igual que en el computador.

Qué lleva (PARTES): las publicaciones que leen el Recorrido, la Planificación semanal, Proyectos en ejecución y
Requerimientos, y los mensajes chicos del buzón (lo pedido que todavía espera). No lleva precios-referencia
(1 MB, solo sugiere precios al anotar una compra, y en el teléfono no se anota nada), ni lo que solo sirve para
escribir (uso-portal, presencia, carpetas del Centro de Costos) ni procesado/. El Flujo de Caja nunca pasa por la
carpeta de Intercambio.

Cada parte va en su propio archivo cifrado (portal/datos/<parte>.json). Una parte que no cambió conserva su sobre
anterior byte a byte: gh-pages guarda una copia de cada versión, y así solo crece con lo que de verdad cambió.
portal/datos/indice.json (sin cifrar: solo horas y huellas) dice cuándo se revisó por última vez y la huella de cada
parte; el Portal muestra esa hora («Solo lectura · datos de las 14:35»).

Cuándo se sube: si cambió alguna parte (estado.json no cuenta: cambia en cada latido del procesador), como máximo
cada 30 minutos; y si nada cambió, una vez por hora, para que la hora del teléfono no envejezca. Solo de lunes a
sábado de 7:00 a 20:00. procesar.py nunca publica en GitHub: esto lo corre aparte tarea_procesador.cmd.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ_REPO = AQUI.parent
sys.path.insert(0, str(RAIZ_REPO / "Visualizador Web"))
import candado  # noqa: E402

VERSION = 1
# Carpeta local (gitignored) con lo último que se armó: indice.json y <parte>.json, tal como van a gh-pages/portal/datos.
SALIDA = AQUI / "resumen_movil"
RUTA_ESTADO = AQUI / "resumen_movil_estado.json"
DESTINO = "portal/datos"          # en gh-pages, junto al Portal

MAX_BUZON = 64 * 1024             # un mensaje más grande (un borrador de cotización entero) no hace falta en el teléfono
SEMANAS_ATRAS, SEMANAS_ADELANTE = 8, 12
CADA_CAMBIO_SEG = 30 * 60
LATIDO_SEG = 60 * 60
HORARIO = (7, 20)                 # de 7:00 a 20:00
DIAS = range(0, 6)                # lunes a sábado


def _semana_vale(nombre: str, hoy: date) -> bool:
    """Una carpeta AAAA-Www de la Planificación entra si está entre 8 semanas atrás y 12 adelante."""
    m = re.fullmatch(r"(\d{4})-W(\d{2})", nombre)
    if not m:
        return True               # lista/, cierres/: siempre
    try:
        lunes = date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    except ValueError:
        return False
    return hoy - timedelta(weeks=SEMANAS_ATRAS) <= lunes <= hoy + timedelta(weeks=SEMANAS_ADELANTE)


def _base(raiz: Path, hoy: date):
    pub = raiz / "publicado"
    for n in ("requerimientos", "proyectos", "analisis-financiero", "licitaciones"):
        yield pub / f"{n}.json"
    buzon = raiz / "buzon"
    if buzon.is_dir():
        yield from (p for p in sorted(buzon.glob("*.json")) if p.stat().st_size <= MAX_BUZON)


def _planificacion(raiz: Path, hoy: date):
    carpeta = raiz / "publicado" / "planificacion"
    if carpeta.is_dir():
        for sub in sorted(p for p in carpeta.iterdir() if p.is_dir() and _semana_vale(p.name, hoy)):
            yield from sorted(sub.glob("*.json"))


def _ejecucion(raiz: Path, hoy: date):
    pub = raiz / "publicado"
    for sub in ("ejecucion", "gantt"):
        if (pub / sub).is_dir():
            yield from sorted((pub / sub).glob("*.json"))
    yield pub / "documentos-proyecto.json"


def _formulador(raiz: Path, hoy: date):
    carpeta = raiz / "publicado" / "formulador"
    if carpeta.is_dir():
        yield from sorted(carpeta.glob("*.json"))


def _estado(raiz: Path, hoy: date):
    yield raiz / "publicado" / "estado.json"


# parte -> qué archivos de la carpeta lleva. «estado» no cuenta como cambio (ver CAMBIAN).
PARTES = {
    "base": _base,
    "planificacion": _planificacion,
    "ejecucion": _ejecucion,
    "formulador": _formulador,
    "estado": _estado,
}
CAMBIAN = ("base", "planificacion", "ejecucion", "formulador")
# Nunca van, aunque alguien cambie PARTES: lo prueba test_resumen_movil.py
NUNCA = ("precios-referencia", "uso-portal", "presencia", "flujo-de-caja", "procesado")


def armar_parte(raiz: Path, parte: str, hoy: date | None = None) -> dict:
    """{"archivos": {"publicado/x.json": {"m": mtime en ms, "d": su contenido}}}. Un archivo que no se lee como JSON
    (OneDrive a medio sincronizar) se salta, como hace el Portal."""
    hoy = hoy or date.today()
    archivos = {}
    for p in PARTES[parte](raiz, hoy):
        if not p.is_file():
            continue
        ruta = p.relative_to(raiz).as_posix()
        if any(n in ruta for n in NUNCA):
            continue
        try:
            datos = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        archivos[ruta] = {"m": int(p.stat().st_mtime * 1000), "d": datos}
    return {"archivos": archivos}


def _plano(parte: dict) -> bytes:
    return json.dumps(parte, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _huella(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()[:16]


def armar(raiz: Path, salida: Path = SALIDA, ahora: datetime | None = None, contrasena: str | None = None) -> dict:
    """Arma cada parte en salida/<parte>.json (cifrada) y salida/indice.json. Una parte igual a la anterior
    conserva su sobre. Devuelve {"cambiadas": [...], "indice": {...}, "pesos": {parte: bytes del sobre}}."""
    ahora = ahora or datetime.now().astimezone()
    anterior = {}
    try:
        anterior = json.loads((salida / "indice.json").read_text(encoding="utf-8")).get("partes", {})
    except (OSError, ValueError):
        pass
    salida.mkdir(parents=True, exist_ok=True)
    partes, cambiadas, pesos = {}, [], {}
    for nombre in PARTES:
        plano = _plano(armar_parte(raiz, nombre, ahora.date()))
        huella = _huella(plano)
        ruta = salida / f"{nombre}.json"
        if anterior.get(nombre) != huella or not ruta.is_file():
            sobre = candado.cifrar_bytes(plano, contrasena, comprimir=True)
            tmp = ruta.with_suffix(".tmp")
            tmp.write_text(sobre, encoding="ascii")
            os.replace(tmp, ruta)
            cambiadas.append(nombre)
        partes[nombre] = huella
        pesos[nombre] = ruta.stat().st_size
    indice = {"version": VERSION, "revisado": ahora.isoformat(timespec="seconds"), "partes": partes}
    tmp = salida / "indice.tmp"
    tmp.write_text(json.dumps(indice, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, salida / "indice.json")
    return {"cambiadas": cambiadas, "indice": indice, "pesos": pesos}


def abre_con(salida: Path, contrasena: str) -> list[str]:
    """Las partes de salida/ que NO abren con esa contraseña ([] = todas abren). Nunca se sube una que no abra."""
    malas = []
    indice = json.loads((salida / "indice.json").read_text(encoding="utf-8"))
    for nombre, huella in indice["partes"].items():
        try:
            plano = candado.descifrar_bytes((salida / f"{nombre}.json").read_text(encoding="ascii"), contrasena)
            if _huella(plano) != huella:
                malas.append(nombre)
        except Exception:
            malas.append(nombre)
    return malas


def toca_subir(estado: dict, cambiadas: list[str], ahora: datetime) -> str | None:
    """Por qué se sube ahora («cambió base», «latido») o None. Solo en horario; un cambio, como máximo cada 30 min."""
    if ahora.weekday() not in DIAS or not HORARIO[0] <= ahora.hour < HORARIO[1]:
        return None
    pendientes = sorted(set(estado.get("pendientes", [])) | {c for c in cambiadas if c in CAMBIAN})
    ultima = estado.get("subido")
    hace = (ahora - datetime.fromisoformat(ultima)).total_seconds() if ultima else None
    if pendientes and (hace is None or hace >= CADA_CAMBIO_SEG):
        return "cambió " + ", ".join(pendientes)
    if hace is None or hace >= LATIDO_SEG:
        return "latido"
    return None


def _leer_estado() -> dict:
    try:
        return json.loads(RUTA_ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar_estado(estado: dict) -> None:
    tmp = RUTA_ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, RUTA_ESTADO)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("accion", nargs="?", choices=["ver", "publicar"], default="ver")
    ap.add_argument("--ya", action="store_true", help="sube aunque no toque (fuera de horario o antes de 30 min)")
    args = ap.parse_args(argv)

    import ubicacion
    raiz = ubicacion.ubicar_intercambio()
    if not raiz:
        print("[AVISO] no se encontró la carpeta de Intercambio: no hay resumen.")
        return 0
    ahora = datetime.now().astimezone()
    r = armar(Path(raiz), SALIDA, ahora)
    total = sum(r["pesos"].values())
    print(f"[OK] resumen armado en {SALIDA} ({total / 1024:.0f} KB): "
          + ", ".join(f"{p} {b / 1024:.0f} KB" for p, b in r["pesos"].items()))
    print("     cambió: " + (", ".join(r["cambiadas"]) or "nada"))
    if args.accion != "publicar":
        return 0

    estado = _leer_estado()
    estado["pendientes"] = sorted(set(estado.get("pendientes", [])) | {c for c in r["cambiadas"] if c in CAMBIAN})
    motivo = "a pedido" if args.ya else toca_subir(estado, r["cambiadas"], ahora)
    if not motivo:
        _guardar_estado(estado)
        print("[OK] no toca subir todavía.")
        return 0
    malas = abre_con(SALIDA, candado.leer_contrasena())
    if malas:
        _guardar_estado(estado)
        _anotar(ahora, f"[ERROR] no abren con la contraseña del equipo: {', '.join(malas)}. No se sube nada.")
        return 1
    import publicar
    try:
        commit = publicar.subir_carpeta_aparte(SALIDA, DESTINO, f"resumen del teléfono: {motivo} ({ahora:%Y-%m-%d %H:%M})")
    except Exception as error:          # sin red, GitHub caído: se reintenta en la vuelta siguiente
        _guardar_estado(estado)
        _anotar(ahora, f"[ERROR] no se pudo subir ({motivo}): {error}")
        return 1
    estado.update({"subido": ahora.isoformat(timespec="seconds"), "pendientes": [], "commit": commit,
                   "pesos": r["pesos"]})
    _guardar_estado(estado)
    _anotar(ahora, f"[OK] subido a gh-pages ({motivo}): {commit or 'ya estaba igual'}, {total / 1024:.0f} KB")
    return 0


def _anotar(ahora: datetime, texto: str) -> None:
    """A la pantalla y a logs/resumen_movil_AAAA-MM.log: una línea por subida o falla (la tarea corre cada 5 minutos y
    casi siempre no hace nada; eso no se anota)."""
    print(texto)
    try:
        carpeta = RAIZ_REPO / "logs"
        carpeta.mkdir(exist_ok=True)
        with open(carpeta / f"resumen_movil_{ahora:%Y-%m}.log", "a", encoding="utf-8") as f:
            f.write(f"{ahora:%Y-%m-%d %H:%M:%S} {texto}\n")
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())
