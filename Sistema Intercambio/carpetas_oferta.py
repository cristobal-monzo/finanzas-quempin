# -*- coding: utf-8 -*-
"""
carpetas_oferta.py -- La carpeta de cada requerimiento: nace con su fila en la
Planilla de Ingreso y sigue el Estado de esa fila.

Pedido del usuario (2026-11-02, retomado el 2026-11-25): que cada requerimiento
nuevo tenga su carpeta en «Formulación de proyectos», con la estructura de
siempre, y que al cambiar el Estado la carpeta vaya adonde corresponde, con un
aviso antes. El 2026-11-25 eligió: las cuatro subcarpetas de siempre; al
adjudicarse, el original a «0 OFERTAS ADJUDICADAS» y una copia en Gestión de
Proyectos (lo que hacía QUEMPIN.exe); el aviso, una casilla marcada en el
Portal; y la lista «fuera de lugar» arriba de la tabla de Requerimientos.

Dónde queda cada una (``DESTINOS``), medido en las carpetas de las dos
bibliotecas (2026-11-02 y de nuevo el 2026-11-25):

    Evaluación                  Formulación de proyectos (la raíz: lo que está en curso)
    Ofertado                    Formulación › 0 OFERTAS PRESENTADAS
    No adjudicado, Descartado   Formulación › 0 OFERTAS PRESENTADAS › 0 Ofertas Cerradas <año>
    Adjudicado                  Formulación › 0 OFERTAS ADJUDICADAS, y su copia en la raíz de Gestión de Proyectos
    Cerrado                     el original igual; la de Gestión, en Gestión › 0 Proyectos Entregados <año>

Corre como paso ``carpetas-oferta`` del procesador (cada 5 minutos), antes de
``entregados``. Nunca borra ni pisa una carpeta de nadie:

1. **Crea la carpeta** «N°. Título» de cada fila nueva de la Planilla que no
   tenga una con su N° en ninguna de las dos bibliotecas, después de
   ``ESPERA_CREAR`` (si alguien la creó a mano en otro computador, OneDrive la
   trae entretanto), con las subcarpetas de ``ESTRUCTURA``, en el grupo de
   Formulación de su estado. Lo que ya estaba en la Planilla la primera vez queda
   como conocido, y lo que entra «No adjudicado» o «Descartado» no lleva carpeta.
2. **Mueve las carpetas** que alguien pidió desde el Portal (mensaje
   ``mover-carpeta``: la casilla al cambiar el Estado o «Mover» en la lista
   «fuera de lugar»). El destino lo decide ``DESTINOS`` según el Estado, nunca el
   mensaje. Solo cuando la Planilla ya dice ese estado o el cambio espera en el
   buzón. Hasta el 2026-11-25 esto lo hacía ``cierre_entregados.py``, solo para
   «Cerrado».

``fuera_de_lugar`` (lo publica ``proyectos.json``, paso ``proyectos``) dice qué
carpetas no están donde su Estado dice: el Portal lo muestra con su botón «Mover».

Uso:  py -3.14 carpetas_oferta.py      (dice qué haría, sin tocar nada)
"""

import json
import os
import re
import shutil
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import esquemas  # noqa: E402
import intercambio  # noqa: E402
import proyectos  # noqa: E402
import requerimientos  # noqa: E402
import ubicacion  # noqa: E402

TIPO_MOVER = "mover-carpeta"
TIPO_EDITAR = "editar-requerimiento"
DESTINO = "carpetas-proyecto"
SUB_FORMULACION = "Formulación"                          # la misma de carpetas_proyecto.py y de Sistema QUEMPIN
# Las subcarpetas de siempre (el usuario las eligió el 2026-11-25): con este nombre exacto las tienen 68 de las
# carpetas de oferta hasta el N° 278, y la 342.
ESTRUCTURA = ("ANTECEDENTES", "DOCUMENTOS EN TRABAJO", "ENTREGABLES", "VISITA TÉCNICA")
# «*» es el año en que se mueve; una carpeta que ya está en cualquier año de ese grupo no se mueve otra vez. 'gestion'
# es dónde va la de Gestión de Proyectos ([] = su raíz); sin 'gestion', la de Gestión no se toca. 'crear': si no tiene
# carpeta en Gestión, se arma con la copia de la oferta. La misma tabla está en el Portal (PQ_CARPETA, js/planilla.js):
# tests/portal/test_portal_planilla.py las compara.
DESTINOS = {
    "Evaluación": {"formulacion": []},
    "Ofertado": {"formulacion": ["0 OFERTAS PRESENTADAS"]},
    "Adjudicado": {"formulacion": ["0 OFERTAS ADJUDICADAS"], "gestion": [], "crear": True},
    "Cerrado": {"formulacion": ["0 OFERTAS ADJUDICADAS"], "gestion": ["0 Proyectos Entregados *"]},
    "No adjudicado": {"formulacion": ["0 OFERTAS PRESENTADAS", "0 Ofertas Cerradas *"]},
    "Descartado": {"formulacion": ["0 OFERTAS PRESENTADAS", "0 Ofertas Cerradas *"]},
}
# Lo que entra a la Planilla ya descartado (casi dos tercios de las filas, casi todas sin carpeta) no necesita una
SIN_CARPETA_NUEVA = ("No adjudicado", "Descartado")
# Una ruta entera de un archivo de la carpeta tiene que caber en los 218 caracteres que Excel abre, aun después de
# pasar a 0 Ofertas Cerradas: 122 de la ruta + 70 del nombre + 24 de «\Formulación 325 v1.xlsx». Lo mismo en el Portal.
LARGO_NOMBRE = 70
ESPERA_CREAR = timedelta(minutes=15)      # lo que tarda OneDrive en traer una carpeta creada en otro computador
ESPERA_PLANILLA = timedelta(minutes=30)   # un «mover» llegó antes que el cambio de estado que lo pidió (OneDrive)
PLAZO_MOVER = timedelta(days=7)           # tanto reintenta con algo abierto
SEGUNDOS_POR_VUELTA = 2 * 60              # lo que una vuelta del procesador (cada 5 minutos) puede pasar copiando
_PROHIBIDOS = re.compile(r'[\\/:*?"<>|#%\x00-\x1f]+')
_CON_NUMERO = re.compile(r"^\s*(\d{1,5})\s*\.\s*(.*)$")


class SigueDespues(Exception):
    """La copia no alcanzó en esta vuelta: la siguiente sigue desde donde quedó."""


class YaExiste(Exception):
    """En el destino ya hay otra carpeta con ese nombre: nunca se pisa."""


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
    """El N° de la Planilla al comienzo del nombre, con la regla de proyectos.py («036. Quilpué» → 36). Un N° temporal
    («001t») no es de la Planilla."""
    m = proyectos._CARPETA_CON_NUMERO.match(nombre)
    return int(m.group(1)) if m and m.group(1).isdigit() and int(m.group(1)) > 0 else None


# ── DÓNDE ESTÁ ───────────────────────────────────────────────────────────────

def _hijas(carpeta: Path) -> list[Path]:
    try:
        return sorted((h for h in Path(carpeta).iterdir() if h.is_dir() and not h.name.startswith((".", "~$"))),
                      key=lambda h: _clave(h.name))
    except OSError:
        return []


def indice(biblioteca: Path | None) -> dict[int, list[list[str]]]:
    """{N°: [ruta en tramos desde la biblioteca]} de las carpetas con N° de la raíz y de los grupos «0 …» (hasta
    tres niveles: «0 OFERTAS PRESENTADAS › 0 Ofertas Cerradas 2026 › 54. Nombre»). Solo lista nombres: no baja nada
    de la nube."""
    salida: dict[int, list[list[str]]] = {}

    def recorrer(carpeta: Path, ruta: list[str], nivel: int):
        for h in _hijas(carpeta):
            if h.name.startswith(proyectos.CARPETAS_AGRUPADORAS):
                if nivel < 3:
                    recorrer(h, ruta + [h.name], nivel + 1)
                continue
            n = numero_de(h.name)
            if n:
                salida.setdefault(n, []).append(ruta + [h.name])

    if biblioteca is not None and Path(biblioteca).is_dir():
        recorrer(Path(biblioteca), [], 1)
    return salida


# ── QUÉ HAY QUE HACER (solo calcula) ─────────────────────────────────────────

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


def anio_de(fila: dict | None, ahora: datetime) -> int:
    """El año del grupo de Formulación («0 Ofertas Cerradas <año>»): el del cierre de la licitación, como las ordenó
    el equipo; sin fecha de cierre, el año en curso. Los entregados de Gestión van siempre en el año en curso."""
    m = re.match(r"^(20\d\d)-", str((fila or {}).get("cierre") or ""))
    return int(m.group(1)) if m else ahora.year


def plan(estado: str, ruta_f: list[str] | None, ruta_g: list[str] | None, anio: int, con_copia: bool = True,
         anio_g: int | None = None) -> dict:
    """{'formulacion': {'desde', 'hasta'} | None, 'gestion': {'accion': 'crear'|'copiar'|'mover', 'desde', 'hasta'} |
    None, 'nombre'}. 'desde' y 'hasta' son rutas de grupo, sin el nombre de la carpeta. con_copia: la carpeta de
    Gestión ya tiene «Formulación» (si no, una copia que se cortó: al adjudicarse se le completa). anio: el de los
    grupos de Formulación (anio_de); anio_g, el de Gestión (el año en curso)."""
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
            salida["gestion"] = {"accion": "mover", "desde": ruta_g[:-1], "hasta": _con_anio(objetivo, anio_g or anio)}
        elif ruta_f and destino.get("crear") and not con_copia:
            salida["gestion"] = {"accion": "copiar", "desde": ruta_g[:-1], "hasta": ruta_g[:-1]}
    elif ruta_f and destino.get("crear"):
        salida["gestion"] = {"accion": "crear", "desde": None, "hasta": _con_anio(objetivo, anio_g or anio)}
    return salida


def _texto_ruta(biblioteca: str, grupo: list[str]) -> str:
    return " › ".join([biblioteca] + list(grupo))


def describir(p: dict) -> list[str]:
    salida = []
    g = p["gestion"]
    if g and g["accion"] == "crear":
        salida.append(f"Se crea en Gestión de Proyectos, con la copia de la oferta en «{SUB_FORMULACION}».")
    elif g and g["accion"] == "copiar":
        salida.append(f"Su carpeta de Gestión de Proyectos recibe la copia de la oferta en «{SUB_FORMULACION}».")
    elif g:
        salida.append(f"De {_texto_ruta('Gestión de Proyectos', g['desde'])} a {_texto_ruta('Gestión de Proyectos', g['hasta'])}.")
    f = p["formulacion"]
    if f:
        salida.append(f"De {_texto_ruta('Formulación de proyectos', f['desde'])} a {_texto_ruta('Formulación de proyectos', f['hasta'])}.")
    return salida


def _con_copia(ges: Path | None, ruta_g: list[str] | None) -> bool:
    return ruta_g is None or ges is None or ubicacion.hija(_bajo(ges, ruta_g), SUB_FORMULACION).exists()


def fuera_de_lugar(reqs: dict, en_f: dict, en_g: dict, ges: Path | None, ahora: datetime, omitir=()) -> list[dict]:
    """[{'req', 'carpeta', 'estado', 'detalle'}]: las carpetas con N° que no están donde dice el Estado de su fila.
    Sin las de un N° con dos carpetas (lo decide una persona), las de 'omitir' (un «mover» que ya espera) ni la carpeta
    de Gestión que falta o le falta la copia de la oferta, si eso es lo único (no está fuera de lugar)."""
    salida = []
    for n in sorted(set(en_f) | set(en_g)):
        fila = reqs.get(n)
        if fila is None or n in omitir or fila.get("estado") not in DESTINOS:
            continue
        rutas_f, rutas_g = en_f.get(n) or [], en_g.get(n) or []
        if len(rutas_f) > 1 or len(rutas_g) > 1:
            continue
        ruta_f = rutas_f[0] if rutas_f else None
        ruta_g = rutas_g[0] if rutas_g else None
        p = plan(fila["estado"], ruta_f, ruta_g, anio_de(fila, ahora), _con_copia(ges, ruta_g), ahora.year)
        # Lo único que falta es la carpeta de Gestión o su copia: no está fuera de lugar. Un proyecto antiguo puede tener su
        # carpeta de Gestión sin N° adelante («Hospital San Jose»), y crear otra la duplicaría
        if p["gestion"] and p["gestion"]["accion"] in ("copiar", "crear") and not p["formulacion"]:
            continue
        if p["gestion"] and p["gestion"]["accion"] == "copiar":
            p["gestion"] = None
        if p["formulacion"] or p["gestion"]:
            salida.append({"req": str(n), "carpeta": p["nombre"], "estado": fila["estado"], "detalle": describir(p)})
    return salida


# ── LO QUE SE HACE EN EL DISCO ───────────────────────────────────────────────

def _bajo(base: Path, tramos: list[str]) -> Path:
    """La carpeta de esos tramos, usando la que ya exista con otra forma de escribirlos. No la crea."""
    actual = Path(base)
    for t in tramos:
        actual = ubicacion.hija(actual, t)
    return actual


def crear_carpeta(base: Path, nombre: str) -> Path:
    """La carpeta nueva, con las subcarpetas de siempre. Nunca usa una que ya exista."""
    destino = Path(base) / nombre
    destino.mkdir(parents=False)
    for sub in ESTRUCTURA:
        (destino / sub).mkdir()
    return destino


def _mover(origen: Path, grupo: Path) -> None:
    """Un solo cambio de nombre en el mismo disco (OneDrive lo sube como movimiento): se mueve completa o no se mueve."""
    destino = grupo / origen.name
    if destino.exists():
        raise YaExiste(f"en «{grupo.name}» ya hay otra «{origen.name}»; no se pisa. Revisa cuál sirve y mueve la otra a mano")
    grupo.mkdir(parents=True, exist_ok=True)
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
    """La copia de la oferta en «Formulación» de la carpeta de Gestión. Se arma en «Formulación (copiando)» y toma su
    nombre recién completa; si no alcanza el tiempo, levanta SigueDespues y la vuelta siguiente sigue desde ahí."""
    if ubicacion.hija(carpeta_gestion, SUB_FORMULACION).exists():
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
    if ges is not None and g and ruta_f and g["accion"] == "crear":
        carpeta = _bajo(ges, g["hasta"]) / ruta_f[-1]
        if carpeta.exists() and ubicacion.hija(carpeta, SUB_FORMULACION).exists():
            raise YaExiste(f"en Gestión de Proyectos ya hay otra «{ruta_f[-1]}»; no se pisa")
        carpeta.mkdir(parents=True, exist_ok=True)
        copiar_oferta(_bajo(form, ruta_f), carpeta, segundos)
    elif ges is not None and g and ruta_f and ruta_g and g["accion"] == "copiar":
        copiar_oferta(_bajo(form, ruta_f), _bajo(ges, ruta_g), segundos)
    elif ges is not None and g and ruta_g and g["accion"] == "mover":
        _mover(_bajo(ges, ruta_g), _bajo(ges, g["hasta"]))
    if ruta_f and p["formulacion"]:
        _mover(_bajo(form, ruta_f), _bajo(form, p["formulacion"]["hasta"]))


# ── LO QUE SE LEE DEL INTERCAMBIO ───────────────────────────────────────────────────

def _instante(texto) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.astimezone()


def leer_planilla(raiz: Path) -> dict[int, dict]:
    datos = (intercambio.leer_publicacion(raiz, requerimientos.PUBLICACION) or {}).get("datos") or {}
    salida = {}
    for r in datos.get("requerimientos") or []:
        try:
            salida[int(r.get("numero"))] = r
        except (TypeError, ValueError):
            continue
    return salida


def moviendo(raiz: Path) -> set[int]:
    """N° con un «mover» que espera en el buzón (la lista «fuera de lugar» no los repite)."""
    salida = set()
    for m in intercambio.leer_buzon(raiz, destino=DESTINO, tipo=TIPO_MOVER)[0]:
        try:
            salida.add(int((m.get("requerimiento") or {}).get("numero")))
        except (TypeError, ValueError):
            continue
    return salida


# ── 1. LAS CARPETAS NUEVAS ───────────────────────────────────────────────────

def crear_nuevas(reqs: dict, form: Path, en_f: dict, en_g: dict, estado: dict, ahora: datetime, r: dict,
                 simular: bool = False) -> None:
    """La carpeta de cada fila nueva que siga sin una después de ESPERA_CREAR, en el grupo de Formulación de su estado
    (Gestión no: eso lo pide una persona). La primera vez todo queda conocido."""
    primera = "conocidos" not in estado
    conocidos = set(estado.get("conocidos") or [])
    esperan = estado.setdefault("esperanCarpeta", {})
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
        grupo = _con_anio((DESTINOS.get(fila.get("estado")) or DESTINOS["Evaluación"])["formulacion"], anio_de(fila, ahora))
        if not simular:
            try:
                base = _bajo(form, grupo)
                base.mkdir(parents=True, exist_ok=True)
                crear_carpeta(base, nombre)
            except OSError as error:
                r["avisos"].append(f"No se pudo crear la carpeta del N° {n} «{nombre}»: {error}")
                continue
        r["creadas"].append(_texto_ruta("Formulación de proyectos", grupo + [nombre]))
        en_f[n] = [grupo + [nombre]]
        conocidos.add(n)
        esperan.pop(str(n), None)
    estado["conocidos"] = sorted(conocidos)


# ── 2. MOVER (mensaje mover-carpeta) ─────────────────────────────────────────

def _cambios_en_camino(raiz: Path) -> tuple[dict[int, set], set[int]]:
    """({N°: estados pedidos}, N° con algún cambio) de lo que espera en el buzón para la Planilla."""
    estados, todos = {}, set()
    for tipo in (TIPO_EDITAR, "nuevo-requerimiento"):
        for m in intercambio.leer_buzon(raiz, destino=requerimientos.DESTINO, tipo=tipo)[0]:
            try:
                n = int((m.get("requerimiento") or {}).get("numero"))
            except (TypeError, ValueError):
                continue
            todos.add(n)
            e = (m.get("cambios") or {}).get("estado") or (m.get("requerimiento") or {}).get("estado")
            if e:
                estados.setdefault(n, set()).add(e)
    return estados, todos


def atender_mover(raiz: Path, reqs: dict, form: Path, ges: Path | None, en_f: dict, en_g: dict, ahora: datetime,
                  r: dict, simular: bool = False, segundos: float = SEGUNDOS_POR_VUELTA) -> None:
    mensajes, _ = intercambio.leer_buzon(raiz, destino=DESTINO, tipo=TIPO_MOVER)
    if not mensajes:
        return

    def archivar(m, estado_final, texto, **extra):
        if not simular:
            intercambio.archivar(raiz, m, estado_final, [texto],
                                 extra=dict(extra, requerimiento=(m.get("requerimiento") or {}).get("numero")))
        (r["movidas"] if estado_final == "aplicado" else r["sinMover"]).append(texto)

    en_camino, con_cambios = _cambios_en_camino(raiz)
    # De cada N°, lo último que se pidió: si cambió de opinión, la carpeta no da la vuelta larga
    ultimo: dict = {}
    for m in sorted(mensajes, key=lambda x: str((x.get("origen") or {}).get("enviado") or "")):
        errores = esquemas.validar_mensaje(m)
        if errores:
            if not simular:
                intercambio.archivar(raiz, m, "rechazado", errores)
            r["sinMover"].append("; ".join(errores))
            continue
        n = int(m["requerimiento"]["numero"])
        if n in ultimo:
            archivar(ultimo[n], "reemplazado", f"N° {n}: después se pidió otro cambio para esta carpeta.")
        ultimo[n] = m
    for n, m in ultimo.items():
        enviado = _instante(m["origen"]["enviado"])
        reciente = enviado is not None and ahora - enviado < ESPERA_PLANILLA
        pedido = m["estado"]
        fila = reqs.get(n)
        actual = str((fila or {}).get("estado") or "")
        if actual != pedido and pedido not in en_camino.get(n, set()):
            if reciente or n in con_cambios:
                r["esperan"].append(f"N° {n}: espera que la Planilla diga «{pedido}»")
            else:
                archivar(m, "descartado", f"N° {n}: la Planilla dice «{actual or 'sin estado'}», no «{pedido}» (el cambio "
                                          "se retiró o se reemplazó): la carpeta quedó donde estaba.")
            continue
        rutas_f, rutas_g = en_f.get(n) or [], en_g.get(n) or []
        if len(rutas_f) > 1 or len(rutas_g) > 1:
            nombres = ", ".join(" › ".join(x) for x in rutas_f + rutas_g)
            archivar(m, "rechazado", f"N° {n}: hay más de una carpeta con ese N° ({nombres}); lo decide una persona, "
                                     "no se movió nada.")
            continue
        ruta_f = rutas_f[0] if rutas_f else None
        ruta_g = rutas_g[0] if rutas_g else None
        if ruta_f is None and ruta_g is None:
            nombre = nombre_carpeta(n, (fila or {}).get("titulo") or m["requerimiento"].get("titulo"))
            if m.get("crear") and nombre:
                if not simular:
                    try:
                        crear_carpeta(form, nombre)
                    except OSError as error:
                        r["esperan"].append(f"N° {n}: no se pudo crear «{nombre}» ({error})")
                        continue
                r["creadas"].append(_texto_ruta("Formulación de proyectos", [nombre]))
                ruta_f = [nombre]
                en_f[n] = [ruta_f]
            elif reciente:
                r["esperan"].append(f"N° {n}: no hay carpeta con su N° (OneDrive puede estar trayéndola)")
                continue
            else:
                archivar(m, "rechazado", f"N° {n}: no hay una carpeta con ese N° en Formulación ni en Gestión de "
                                         "Proyectos; no se movió nada.")
                continue
        p = plan(pedido, ruta_f, ruta_g, anio_de(fila, ahora), _con_copia(ges, ruta_g), ahora.year)
        if not p["formulacion"] and not p["gestion"]:
            donde = " › ".join(ruta_g or ruta_f)
            archivar(m, "sin-cambios", f"N° {n}: su carpeta ya está donde corresponde a «{pedido}» ({donde}).")
            continue
        if simular:
            r["movidas"].append(f"N° {n} «{p['nombre']}»: " + " ".join(describir(p)))
            continue
        try:
            ejecutar(p, form, ges, ruta_f, ruta_g, segundos)
        except SigueDespues as aviso:
            r["esperan"].append(str(aviso))
            continue
        except YaExiste as error:
            archivar(m, "rechazado", f"N° {n}: {error}.")
            continue
        except OSError as error:
            if enviado is not None and ahora - enviado > PLAZO_MOVER:
                archivar(m, "rechazado", f"N° {n}: «{p['nombre']}» no se pudo mover en {PLAZO_MOVER.days} días ({error}). "
                                         "Muévela a mano o pídelo de nuevo.")
            else:
                r["esperan"].append(f"N° {n}: no se pudo mover «{p['nombre']}» (¿un archivo abierto?); se reintenta")
                r["avisos"].append(f"carpeta del N° {n} sin mover: {str(error)[:150]}")
            continue
        archivar(m, "aplicado", f"N° {n} «{p['nombre']}»: " + " ".join(describir(p)))
        # Lo que viene después en esta vuelta (la lista «fuera de lugar») ve dónde quedó
        en_f.update(indice(form))
        en_g.update(indice(ges))


# ── LA VUELTA ────────────────────────────────────────────────────────────────

def vuelta(raiz: Path, form: Path | None, ges: Path | None, previo: dict | None, simular: bool = False,
           ahora: datetime | None = None, segundos: float = SEGUNDOS_POR_VUELTA) -> tuple[str, dict, list]:
    """(detalle, estado nuevo, avisos) del paso del procesador. El estado es {'conocidos', 'esperanCarpeta'}."""
    estado = json.loads(json.dumps(previo or {}))
    if form is None or not Path(form).is_dir():
        return "la biblioteca «Formulación de proyectos» no está sincronizada en este equipo", estado, []
    ahora = ahora or datetime.now().astimezone()
    reqs = leer_planilla(raiz)
    if not reqs:
        return "la Planilla todavía no está publicada", estado, []
    r = {"creadas": [], "movidas": [], "esperan": [], "sinMover": [], "avisos": []}
    en_f, en_g = indice(form), indice(ges)
    crear_nuevas(reqs, Path(form), en_f, en_g, estado, ahora, r, simular)
    atender_mover(raiz, reqs, Path(form), ges, en_f, en_g, ahora, r, simular, segundos)
    partes = []
    if r["creadas"]:
        partes.append("carpetas nuevas: " + "; ".join(r["creadas"]))
    if r["movidas"]:
        partes.append("movidas: " + "; ".join(r["movidas"]))
    if r["esperan"]:
        partes.append("por mover: " + "; ".join(r["esperan"]))
    if r["sinMover"]:
        partes.append("sin mover: " + "; ".join(r["sinMover"]))
    return "; ".join(partes) or "sin cambios", estado, r["avisos"]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except AttributeError:
        pass
    raiz = ubicacion.ubicar_intercambio(AQUI)
    form = ubicacion.biblioteca(ubicacion.BIBLIOTECA_FORMULACION, AQUI)
    ges = ubicacion.biblioteca(ubicacion.BIBLIOTECA_GESTION, AQUI)
    if raiz is None or form is None:
        print("Falta la carpeta de Intercambio o la biblioteca «Formulación de proyectos» en este equipo.")
        return 1
    try:
        firmas = json.loads((AQUI / "procesador_estado.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        firmas = {}
    previo = firmas.get("carpetas-oferta") if isinstance(firmas.get("carpetas-oferta"), dict) else {}
    detalle, _, avisos = vuelta(raiz, form, ges, previo, simular=True)
    print("Haría:", detalle)
    for a in avisos:
        print("  aviso:", a)
    lista = fuera_de_lugar(leer_planilla(raiz), indice(form), indice(ges), ges, datetime.now().astimezone(), moviendo(raiz))
    print(f"\nFuera de lugar ({len(lista)}):")
    for x in lista:
        print(f"  N° {x['req']} «{x['carpeta']}» ({x['estado']}): " + " ".join(x["detalle"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
