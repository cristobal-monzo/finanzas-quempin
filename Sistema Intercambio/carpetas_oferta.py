# -*- coding: utf-8 -*-
"""
carpetas_oferta.py -- La carpeta de cada proyecto: nace con su fila en la
Planilla de Ingreso y sigue el Estado de esa fila.

Pedido del usuario (2026-11-02): que al crearse un proyecto en la Planilla se
cree su carpeta en «Formulación de proyectos», con la estructura de siempre,
para subir ahí las bases técnicas y los documentos complementarios; que esa
sea la carpeta principal del proyecto, en vez de armarla a mano. Y que al
cambiar el Estado la carpeta se mueva adonde corresponde, con un aviso antes.

Dónde queda cada una (``DESTINOS``) sale de lo que el equipo ya hacía, medido el
2026-11-02 sobre las 203 carpetas de las dos bibliotecas:

    Evaluación                  Formulación de proyectos (la raíz: lo que está en curso)
    Ofertado                    Formulación › 0 OFERTAS PRESENTADAS
    No adjudicado, Descartado   Formulación › 0 OFERTAS PRESENTADAS › 0 Ofertas Cerradas <año>
    Adjudicado                  Formulación › 0 OFERTAS ADJUDICADAS, y su copia en Gestión de Proyectos
    Post-venta                  sigue en la raíz de Gestión (se sigue atendiendo)
    Cerrado                     Gestión de Proyectos › 0 Proyectos Entregados <año>

Al adjudicarse, la carpeta de Gestión se arma como desde el 2026-10-19: una copia
en «Formulación» dentro de una carpeta nueva y el original en 0 OFERTAS
ADJUDICADAS, con el Excel de la formulación al día. Eso lo hacía QUEMPIN.exe en
el computador de quien lo pedía; desde esta versión lo hace esta vuelta, que
reintenta si algo está abierto y funciona desde cualquier navegador.

Esta vuelta (``vuelta``, cada 10 minutos, desde planilla_escritura.py) hace lo
que el navegador no puede, y nunca borra un archivo de nadie:

1. **Crea la carpeta** de cada fila nueva de la Planilla que no la tenga, con
   las subcarpetas de siempre (``ESTRUCTURA``). El Portal la crea al tiro al
   ingresar el requerimiento; aquí se crea la de lo escrito en el Excel, tras
   ``ESPERA_CREAR``, para no duplicar una que todavía no termina de sincronizar.
   Lo que ya estaba en la Planilla la primera vez queda como conocido: en el
   Portal cada fila sin carpeta tiene su botón «Crear carpeta».
2. **Mueve las carpetas** que alguien confirmó después de ver el aviso (mensaje
   ``mover-carpeta``). El destino lo decide esta tabla según el Estado de la
   Planilla, nunca el mensaje. Un cambio escrito directo en el Excel no mueve
   nada, porque no hay dónde avisar: el Portal lo muestra con su botón «Mover».
3. **Lleva el Estado al Formulador** (``formulaciones.alinear_estados``).
4. **Republica ``proyectos.json``** si cambió alguna carpeta, para que las
   herramientas sepan dónde está cada una sin esperar al procesador.

La tarea tiene un límite de 15 minutos, así que una copia grande a Gestión se
retoma: lo copiado queda en «Formulación (copiando)» y la vuelta siguiente sigue
desde ahí (``SEGUNDOS_POR_VUELTA``). Recién completa toma su nombre.

Uso:  py -3.14 carpetas_oferta.py [--simular]
"""

import hashlib
import json
import os
import re
import shutil
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import esquemas
import formulaciones
import intercambio
import requerimientos
import ubicacion

AQUI = Path(__file__).resolve().parent
RUTA_ESTADO = AQUI / "carpetas_oferta_estado.json"      # gitignoreado
TIPO_MOVER = "mover-carpeta"
DESTINO = "carpetas-proyecto"
SUB_FORMULACION = "Formulación"                          # la misma de carpetas_proyecto.py y de Sistema QUEMPIN
# Las subcarpetas de siempre: con este nombre exacto las tienen 68 de las 156 carpetas de oferta, hasta el N° 278
ESTRUCTURA = ("ANTECEDENTES", "DOCUMENTOS EN TRABAJO", "ENTREGABLES", "VISITA TÉCNICA")
# «*» es el año en que se mueve; una carpeta que ya está en cualquier año de ese grupo no se mueve otra vez. La
# misma tabla está en el Portal (PQ_CARPETA) y en el Formulador (js/oferta.js): test_portal.py las compara.
DESTINOS = {
    "Evaluación": {"formulacion": []},
    "Ofertado": {"formulacion": ["0 OFERTAS PRESENTADAS"]},
    "Adjudicado": {"formulacion": ["0 OFERTAS ADJUDICADAS"], "gestion": [], "crear": True},
    "Post-venta": {"formulacion": ["0 OFERTAS ADJUDICADAS"], "gestion": []},
    "Cerrado": {"formulacion": ["0 OFERTAS ADJUDICADAS"], "gestion": ["0 Proyectos Entregados *"]},
    "No adjudicado": {"formulacion": ["0 OFERTAS PRESENTADAS", "0 Ofertas Cerradas *"]},
    "Descartado": {"formulacion": ["0 OFERTAS PRESENTADAS", "0 Ofertas Cerradas *"]},
}
# Lo que entra a la Planilla ya descartado (son 205 de 323 filas, casi todas sin carpeta) no necesita una
SIN_CARPETA_NUEVA = ("No adjudicado", "Descartado")
# Una ruta entera de un archivo de la carpeta tiene que caber en los 218 caracteres que Excel abre, aun después de
# pasar a 0 Ofertas Cerradas: 122 de la ruta + 70 del nombre + 24 de «\Formulación 325 v1.xlsx». Los mismos en el Portal.
LARGO_NOMBRE = 70
ESPERA_CREAR = timedelta(minutes=15)      # lo que tarda OneDrive en traer una carpeta creada en otro computador
ESPERA_ESTADO = timedelta(minutes=30)     # un «mover» llegó antes que el cambio de estado que lo pidió (OneDrive)
PLAZO_MOVER = timedelta(days=7)           # tanto reintenta con la carpeta ocupada
PLAZO_RENOMBRE = timedelta(hours=24)
SEGUNDOS_POR_VUELTA = 8 * 60              # lo que puede tardar una vuelta copiando (la tarea tiene 15 minutos)
_CON_NUMERO = re.compile(r"^\s*(\d{1,5})\s*\.\s*(.*)$")
_PROHIBIDOS = re.compile(r'[\\/:*?"<>|#%\x00-\x1f]+')


class SigueDespues(Exception):
    """La copia no alcanzó en esta vuelta: la siguiente sigue desde donde quedó."""


# ── NOMBRES ──────────────────────────────────────────────────────────────────

def _clave(nombre: str) -> str:
    return unicodedata.normalize("NFC", str(nombre)).strip().casefold()


def nombre_carpeta(numero, titulo) -> str:
    """«N°. Título» apto para una carpeta, sin el N° repetido, o '' sin título."""
    t = unicodedata.normalize("NFC", str(titulo or ""))
    m = _CON_NUMERO.match(t)
    if m and int(m.group(1)) == int(numero):
        t = m.group(2)
    t = re.sub(r"\s+", " ", _PROHIBIDOS.sub("-", t)).strip(" .-")
    return f"{int(numero)}. {t}"[:LARGO_NOMBRE].rstrip(" .-") if t else ""


def numero_de(nombre: str) -> int | None:
    m = _CON_NUMERO.match(nombre)
    return int(m.group(1)) if m and int(m.group(1)) > 0 else None


# ── DÓNDE ESTÁ ───────────────────────────────────────────────────────────────

def _hijas(carpeta: Path) -> list[Path]:
    try:
        return sorted((h for h in carpeta.iterdir() if h.is_dir() and not h.name.startswith(".")), key=lambda h: _clave(h.name))
    except OSError:
        return []


def indice(biblioteca: Path | None) -> dict[int, list[list[str]]]:
    """{N°: [ruta en tramos desde la biblioteca]} de las carpetas «N°. Nombre» de
    la raíz y de los grupos «0 …». Solo lista nombres: no baja nada de la nube."""
    salida: dict[int, list[list[str]]] = {}

    def recorrer(carpeta: Path, ruta: list[str], nivel: int):
        for h in _hijas(carpeta):
            n = numero_de(h.name)
            if n:
                salida.setdefault(n, []).append(ruta + [h.name])
            elif h.name.startswith("0 ") and nivel < 4:
                recorrer(h, ruta + [h.name], nivel + 1)

    if biblioteca is not None:
        recorrer(Path(biblioteca), [], 1)
    return salida


# ── QUÉ HAY QUE HACER (solo calcula; el Portal y el Formulador llevan el mismo cálculo para su aviso) ──

def _mismo_grupo(actual: list[str], objetivo: list[str]) -> bool:
    if len(actual) != len(objetivo):
        return False
    for a, o in zip(actual, objetivo):
        if o.endswith("*"):
            if not _clave(a).startswith(_clave(o[:-1])):
                return False
        elif _clave(a) != _clave(o):
            return False
    return True


def _con_anio(grupo: list[str], anio: int) -> list[str]:
    return [g.replace("*", str(anio)) for g in grupo]


def plan(estado: str, ruta_f: list[str] | None, ruta_g: list[str] | None, anio: int, con_copia: bool = True) -> dict:
    """{'formulacion': {'desde', 'hasta'} | None, 'gestion': {'accion': 'crear'|'copiar'|'mover', 'desde', 'hasta'} | None,
    'nombre'}. 'desde' y 'hasta' son rutas de grupo, sin el nombre de la carpeta. con_copia: la carpeta de Gestión ya
    tiene «Formulación» (si no, una copia que se cortó o una carpeta hecha a mano: al adjudicarse se le agrega; el
    aviso del navegador no lo sabe y no lo dice)."""
    salida = {"formulacion": None, "gestion": None, "nombre": (ruta_f or ruta_g or [""])[-1]}
    destino = DESTINOS.get(estado)
    if destino is None:
        return salida
    if ruta_f and not _mismo_grupo(ruta_f[:-1], destino["formulacion"]):
        salida["formulacion"] = {"desde": ruta_f[:-1], "hasta": _con_anio(destino["formulacion"], anio)}
    objetivo = destino.get("gestion")
    if objetivo is None:
        return salida
    if ruta_g:
        if not _mismo_grupo(ruta_g[:-1], objetivo):
            salida["gestion"] = {"accion": "mover", "desde": ruta_g[:-1], "hasta": _con_anio(objetivo, anio)}
        elif ruta_f and destino.get("crear") and not con_copia:
            salida["gestion"] = {"accion": "copiar", "desde": ruta_g[:-1], "hasta": ruta_g[:-1]}
    elif ruta_f and destino.get("crear"):
        salida["gestion"] = {"accion": "crear", "desde": None, "hasta": _con_anio(objetivo, anio)}
    return salida


def _texto_ruta(biblioteca: str, grupo: list[str]) -> str:
    return " › ".join([biblioteca] + list(grupo))


def describir(p: dict) -> list[str]:
    salida = []
    g = p["gestion"]
    if g and g["accion"] == "crear":
        salida.append(f"Se creó en Gestión de Proyectos, con la copia de la oferta en «{SUB_FORMULACION}».")
    elif g and g["accion"] == "copiar":
        salida.append(f"Su carpeta de Gestión de Proyectos quedó con la copia de la oferta en «{SUB_FORMULACION}».")
    elif g:
        salida.append(f"Pasó de {_texto_ruta('Gestión de Proyectos', g['desde'])} a {_texto_ruta('Gestión de Proyectos', g['hasta'])}.")
    f = p["formulacion"]
    if f:
        salida.append(f"Pasó de {_texto_ruta('Formulación de proyectos', f['desde'])} a {_texto_ruta('Formulación de proyectos', f['hasta'])}.")
    return salida


# ── LO QUE SE HACE EN EL DISCO ───────────────────────────────────────────────

def _bajo(base: Path, tramos: list[str]) -> Path:
    """La carpeta de esos tramos, usando la que ya exista con otra forma de escribirlos. No la crea."""
    actual = Path(base)
    for t in tramos:
        actual = ubicacion.hija(actual, t)
    return actual


def crear_carpeta(biblioteca: Path, nombre: str) -> Path:
    """La carpeta nueva en la raíz, con las subcarpetas de siempre. Nunca usa una que ya exista."""
    destino = Path(biblioteca) / nombre
    destino.mkdir()
    for sub in ESTRUCTURA:
        (destino / sub).mkdir()
    return destino


def _mover(origen: Path, grupo: Path) -> None:
    """Un solo cambio de nombre: se mueve completa o no se mueve."""
    grupo.mkdir(parents=True, exist_ok=True)
    destino = grupo / origen.name
    if destino.exists():
        raise FileExistsError(f"ya hay otra «{origen.name}» en «{grupo.name}»")
    os.rename(origen, destino)


def _archivos(carpeta: Path) -> tuple[list[Path], int]:
    """(archivos relativos, bytes), sin desktop.ini (lo pone Windows u OneDrive en cada carpeta)."""
    salida, total = [], 0
    for base, dirs, nombres in os.walk(carpeta):
        dirs.sort()
        for n in sorted(nombres):
            if n.lower() == "desktop.ini":
                continue
            ruta = Path(base) / n
            salida.append(ruta.relative_to(carpeta))
            total += ruta.stat().st_size
    return salida, total


def copiar_oferta(origen: Path, carpeta_gestion: Path, segundos: float = SEGUNDOS_POR_VUELTA) -> None:
    """La copia de la oferta en «Formulación». Se arma en «Formulación (copiando)» y toma su nombre recién
    completa. Si no alcanza el tiempo, levanta SigueDespues y la vuelta siguiente sigue desde ahí."""
    final = ubicacion.hija(carpeta_gestion, SUB_FORMULACION)
    if final.exists():
        return                # una carpeta de Gestión que ya tenía su copia no se toca
    temporal = carpeta_gestion / f"{SUB_FORMULACION} (copiando)"
    temporal.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + segundos
    archivos, total = _archivos(origen)
    for base, dirs, _ in os.walk(origen):
        for d in dirs:
            (temporal / Path(base).relative_to(origen) / d).mkdir(parents=True, exist_ok=True)
    for rel in archivos:
        destino = temporal / rel
        if destino.exists() and destino.stat().st_size == (origen / rel).stat().st_size:
            continue
        if time.monotonic() > limite:
            raise SigueDespues(f"copiando «{origen.name}» a Gestión de Proyectos: sigue en la próxima vuelta")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen / rel, destino)
    copia, bytes_copia = _archivos(temporal)
    if len(copia) != len(archivos) or bytes_copia != total:
        raise OSError("la copia no quedó igual al original")
    os.rename(temporal, carpeta_gestion / SUB_FORMULACION)


def ejecutar(p: dict, form: Path, ges: Path | None, ruta_f: list[str] | None, ruta_g: list[str] | None,
             segundos: float = SEGUNDOS_POR_VUELTA) -> None:
    """Primero Gestión y después el original, como lo hacía QUEMPIN.exe: si la copia falla, nada se movió."""
    g = p["gestion"]
    if ges is not None and g and g["accion"] == "crear" and ruta_f:
        carpeta = Path(ges) / ruta_f[-1]
        carpeta.mkdir(exist_ok=True)
        copiar_oferta(_bajo(form, ruta_f), carpeta, segundos)
    elif ges is not None and g and g["accion"] == "copiar" and ruta_f and ruta_g:
        copiar_oferta(_bajo(form, ruta_f), _bajo(ges, ruta_g), segundos)
    elif ges is not None and g and ruta_g:
        _mover(_bajo(ges, ruta_g), _bajo(ges, g["hasta"]))
    if ruta_f and p["formulacion"]:
        _mover(_bajo(form, ruta_f), _bajo(form, p["formulacion"]["hasta"]))


# ── EL ESTADO DE ESTA VUELTA ─────────────────────────────────────────────────

def leer_estado(ruta: Path = RUTA_ESTADO) -> dict:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar_estado(estado: dict, ruta: Path = RUTA_ESTADO) -> None:
    temporal = Path(ruta).with_suffix(".tmp")
    temporal.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(temporal, ruta)


def _instante(texto) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.astimezone()


# ── 1. LAS CARPETAS NUEVAS ───────────────────────────────────────────────────

def crear_nuevas(reqs: dict, form: Path, ges: Path | None, estado: dict, ahora: datetime, r: dict, simular: bool = False) -> None:
    """La carpeta de cada fila nueva que siga sin una después de ESPERA_CREAR. La primera vez todo queda conocido."""
    primera = "conocidos" not in estado
    conocidos = set(estado.get("conocidos") or [])
    esperan = estado.setdefault("esperanCarpeta", {})
    en_f, en_g = indice(form), indice(ges)
    for n in sorted(reqs):
        if n in conocidos:
            continue
        fila = reqs[n]
        if primera or n in en_f or n in en_g or fila.get("estado") in SIN_CARPETA_NUEVA:
            conocidos.add(n)
            esperan.pop(str(n), None)
            continue
        nombre = nombre_carpeta(n, fila.get("titulo"))
        if not nombre:
            continue          # una fila que todavía no tiene título: espera a tenerlo
        desde = _instante(esperan.get(str(n)))
        if desde is None:
            esperan[str(n)] = ahora.isoformat(timespec="seconds")
            continue
        if ahora - desde < ESPERA_CREAR:
            continue
        if simular:
            r["creadas"].append(nombre)
            continue
        try:
            crear_carpeta(form, nombre)
            ejecutar(plan(fila.get("estado"), [nombre], None, ahora.year), form, ges, [nombre], None)
        except SigueDespues as aviso:
            r["avisos"].append(str(aviso))
        except OSError as error:
            r["avisos"].append(f"No se pudo crear la carpeta del N° {n} «{nombre}»: {error}")
            continue
        r["creadas"].append(nombre)
        conocidos.add(n)
        esperan.pop(str(n), None)
    estado["conocidos"] = sorted(conocidos)


def renombrar_pendientes(form: Path, estado: dict, renumerados: list, ahora: datetime, r: dict, simular: bool = False) -> None:
    """El N° que tomó un requerimiento del Portal que chocó con otro: su carpeta, creada al tiro con el N° que
    pedía, pasa al que le tocó. Puede demorar en llegar por OneDrive: se reintenta hasta PLAZO_RENOMBRE."""
    lista = list(estado.get("renombres") or [])
    lista += [{"pedido": a, "numero": b, "titulo": t, "desde": ahora.isoformat(timespec="seconds")} for a, b, t in renumerados]
    quedan = []
    for x in lista:
        viejo = nombre_carpeta(x["pedido"], x["titulo"])
        nuevo = nombre_carpeta(x["numero"], x["titulo"])
        origen = ubicacion.hija(form, viejo) if viejo else None
        if origen is None or not origen.is_dir():
            if ahora - (_instante(x["desde"]) or ahora) < PLAZO_RENOMBRE:
                quedan.append(x)
            continue
        if simular:
            r["renombradas"].append(f"{viejo} → {nuevo}")
            continue
        try:
            os.rename(origen, Path(form) / nuevo)
            r["renombradas"].append(f"{viejo} → {nuevo}")
        except OSError as error:
            r["avisos"].append(f"No se pudo renombrar «{viejo}»: {error}")
            quedan.append(x)
    estado["renombres"] = quedan


# ── 2. MOVER (mensaje mover-carpeta) ─────────────────────────────────────────

def atender_mover(raiz: Path, reqs: dict, form: Path, ges: Path | None, ahora: datetime, r: dict, simular: bool = False,
                  segundos: float = SEGUNDOS_POR_VUELTA) -> None:
    mensajes, _ = intercambio.leer_buzon(raiz, destino=DESTINO, tipo=TIPO_MOVER)
    if not mensajes:
        return

    def archivar(m, estado_final, detalle, n=None):
        if not simular:
            intercambio.archivar(raiz, m, estado_final, detalle, extra={"requerimiento": n} if n else None)

    esperan_planilla = set()
    for tipo in ("editar-requerimiento", "nuevo-requerimiento"):
        for m in intercambio.leer_buzon(raiz, destino=requerimientos.DESTINO, tipo=tipo)[0]:
            esperan_planilla.add((m.get("requerimiento") or {}).get("numero"))
    # De cada N°, lo último que se pidió: si cambió de opinión, la carpeta no da la vuelta larga
    ultimo: dict = {}
    for m in sorted(mensajes, key=lambda x: x["origen"]["enviado"]):
        errores = esquemas.validar_mensaje(m)
        if errores:
            archivar(m, "rechazado", errores)
            continue
        n = m["requerimiento"]["numero"]
        if n in ultimo:
            archivar(ultimo[n], "reemplazado", ["Después se pidió otro cambio para esta carpeta."], n)
        ultimo[n] = m
    en_f, en_g = indice(form), indice(ges)
    for n, m in ultimo.items():
        enviado = _instante(m["origen"]["enviado"]) or ahora
        fila = reqs.get(n)
        pedido = m["estado"]
        if fila is None or fila.get("estado") != pedido:
            if n in esperan_planilla or ahora - enviado < ESPERA_ESTADO:
                r["esperan"].append(f"N° {n}: espera que la Planilla diga «{pedido}»")
            else:
                archivar(m, "reemplazado", [f"La Planilla dice «{(fila or {}).get('estado') or 'otra cosa'}», no «{pedido}»: la carpeta no se movió."], n)
            continue
        rutas_f, rutas_g = en_f.get(n) or [], en_g.get(n) or []
        if len(rutas_f) > 1 or len(rutas_g) > 1:
            nombres = ", ".join("/".join(x) for x in rutas_f + rutas_g)
            archivar(m, "rechazado", [f"Hay más de una carpeta con el N° {n}: {nombres}. Una persona decide cuál es; no se movió nada."], n)
            continue
        ruta_f = rutas_f[0] if rutas_f else None
        ruta_g = rutas_g[0] if rutas_g else None
        if ruta_f is None and ruta_g is None:
            nombre = nombre_carpeta(n, fila.get("titulo"))
            if not m.get("crear") or not nombre:
                archivar(m, "sin-cambios", [f"El N° {n} no tiene carpeta con su N° adelante: no hay nada que mover."], n)
                continue
            if simular:
                r["creadas"].append(nombre)
                continue
            try:
                crear_carpeta(form, nombre)
            except OSError as error:
                r["esperan"].append(f"N° {n}: no se pudo crear «{nombre}» ({error})")
                continue
            ruta_f = [nombre]
            r["creadas"].append(nombre)
        con_copia = ruta_g is None or ges is None or ubicacion.hija(_bajo(ges, ruta_g), SUB_FORMULACION).exists()
        p = plan(pedido, ruta_f, ruta_g, ahora.year, con_copia)
        if not p["formulacion"] and not p["gestion"]:
            archivar(m, "sin-cambios", ["La carpeta ya está donde corresponde a su estado."], n)
            continue
        if simular:
            r["movidas"].append({"numero": n, "nombre": p["nombre"], "detalle": describir(p)})
            continue
        try:
            ejecutar(p, form, ges, ruta_f, ruta_g, segundos)
        except SigueDespues as aviso:
            r["esperan"].append(str(aviso))
            continue
        except OSError as error:
            motivo = "hay un archivo abierto o OneDrive la está sincronizando" if isinstance(error, PermissionError) else str(error)
            if ahora - enviado > PLAZO_MOVER:
                archivar(m, "rechazado", [f"«{p['nombre']}» no se pudo mover en {PLAZO_MOVER.days} días: {motivo}. Pídelo de nuevo."], n)
            else:
                r["esperan"].append(f"N° {n}: {motivo}; se reintenta")
            continue
        detalle = describir(p)
        archivar(m, "aplicado", [f"«{p['nombre']}»: " + " ".join(detalle)], n)
        r["movidas"].append({"numero": n, "nombre": p["nombre"], "detalle": detalle})


# ── LA VUELTA ────────────────────────────────────────────────────────────────

def _publicar_proyectos(raiz: Path) -> None:
    import procesar          # aquí, no arriba: trae todos los módulos del procesador
    procesar.paso_proyectos(raiz, None, False)


def vuelta(raiz: Path | None = None, form: Path | None = None, ges: Path | None = None, ruta_estado: Path | None = None,
           renumerados: list | None = None, del_formulador=(), simular: bool = False, publicar_proyectos=None,
           ahora: datetime | None = None, segundos: float = SEGUNDOS_POR_VUELTA) -> dict:
    raiz = raiz or ubicacion.ubicar_intercambio(AQUI)
    form = form or ubicacion.biblioteca(ubicacion.BIBLIOTECA_FORMULACION, AQUI)
    ges = ges or ubicacion.biblioteca(ubicacion.BIBLIOTECA_GESTION, AQUI)
    if raiz is None or form is None:
        return {"activo": False, "detalle": "sin la biblioteca de Formulación en este equipo"}
    ahora = ahora or datetime.now().astimezone()
    ruta_estado = ruta_estado or RUTA_ESTADO
    estado = leer_estado(ruta_estado)
    r = {"activo": True, "creadas": [], "renombradas": [], "movidas": [], "esperan": [], "alineadas": [], "avisos": []}
    filas = ((intercambio.leer_publicacion(raiz, requerimientos.PUBLICACION) or {}).get("datos") or {}).get("requerimientos") or []
    reqs = {f["numero"]: f for f in filas if isinstance(f.get("numero"), int)}
    if not reqs:
        return dict(r, detalle="la Planilla todavía no está publicada")
    renombrar_pendientes(form, estado, renumerados or [], ahora, r, simular)
    crear_nuevas(reqs, form, ges, estado, ahora, r, simular)
    atender_mover(raiz, reqs, form, ges, ahora, r, simular, segundos)
    vistos, alineadas = formulaciones.alinear_estados(raiz, filas, estado.get("estadosVistos"), set(del_formulador), ahora, simular)
    estado["estadosVistos"] = vistos
    r["alineadas"] = alineadas
    # Dónde está cada carpeta: se republica si cambió algo, aunque lo haya hecho una persona en el Explorador
    firma = hashlib.sha1(json.dumps([indice(form), indice(ges)], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    if firma != estado.get("firmaCarpetas") and not simular:
        try:
            (publicar_proyectos or _publicar_proyectos)(raiz)
            estado["firmaCarpetas"] = firma
        except Exception as error:  # noqa: BLE001 -- el procesador lo publica igual en su vuelta
            r["avisos"].append(f"No se republicó proyectos.json: {error}")
    if not simular:
        guardar_estado(estado, ruta_estado)
    return r


def resumen(r: dict) -> str:
    """Una línea para el log de la Planilla; vacía si esta vuelta no hizo nada."""
    partes = []
    if r.get("creadas"):
        partes.append("carpetas nuevas: " + ", ".join(r["creadas"]))
    if r.get("renombradas"):
        partes.append("renombradas: " + ", ".join(r["renombradas"]))
    if r.get("movidas"):
        partes.append("movidas: " + ", ".join(x["nombre"] for x in r["movidas"]))
    if r.get("esperan"):
        partes.append("esperan: " + "; ".join(r["esperan"]))
    if r.get("alineadas"):
        partes.append("estado llevado al Formulador: " + ", ".join(r["alineadas"]))
    if r.get("avisos"):
        partes.append("avisos: " + "; ".join(r["avisos"]))
    return " · ".join(partes)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    print(json.dumps(vuelta(simular="--simular" in argv), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
