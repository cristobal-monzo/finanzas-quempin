# -*- coding: utf-8 -*-
"""
cierre_entregados.py -- La carpeta de un proyecto en «0 Proyectos Entregados»
dice que el proyecto terminó, y la Planilla de Ingreso lo dice también.

Pedido del usuario (2026-11-09): «que al mover manualmente los proyectos a esa
carpeta, durante el siguiente registro el sistema lo identifique como
terminado», y que desde el Portal, al cambiar un proyecto a «Cerrado», haya una
opción para mover su carpeta ahí. Plan:
``Documentación/Planes y análisis/2026-11-09-carpeta-entregados-cierra-proyecto.md``.

Corre como un paso del procesador (``procesar.py``, paso ``entregados``), en el
computador que tiene sincronizada la biblioteca «Gestión de Proyectos». Hace dos
cosas, en este orden:

1. **Mueve** las carpetas que pidió el Portal (mensaje ``mover-carpeta``): de la
   raíz de Gestión a «0 Proyectos Entregados <año>». Solo si la Planilla ya dice
   «Cerrado» o ese cambio todavía espera en el buzón (si nada de eso aparece en
   30 minutos, el cambio se retiró y la carpeta no se mueve). Nunca borra ni pisa:
   si en el destino ya hay una con ese nombre, no la mueve. Si algo de la carpeta
   está abierto, reintenta en cada vuelta durante 7 días.
2. **Cierra** lo entregado a mano: cada carpeta con N° dentro de cualquier
   «0 Proyectos Entregados <año>» cuyo requerimiento la Planilla tiene
   «Adjudicado» pasa a «Cerrado». El procesador nunca escribe la Planilla: deja
   un ``editar-requerimiento`` en el buzón y ``planilla_escritura.py`` lo escribe
   en su vuelta de cada 10 minutos, con sus respaldos.

Frenos de la parte 2:

- **Una sola vez por N°.** Lo ya pedido queda anotado (``cerrados``, en el estado
  del procesador): si alguien después lo vuelve a «Adjudicado» a mano, se respeta.
- **Solo «Adjudicado» se cierra.** Una carpeta entregada de un requerimiento que
  la Planilla tiene en otro estado (Evaluación, Ofertado, No adjudicado...) o que
  no está en la Planilla queda como aviso: puede ser un N° equivocado.
- **Solo con un N° que no se repite.** Si ese N° tiene también una carpeta en la
  raíz de Gestión (se copió en vez de moverse) o dos en los entregados, queda
  como aviso. Las carpetas sin N° no se pueden cruzar con la Planilla: solo se
  cuentan.
- **Tope por vuelta** (``MAX_CIERRES``): si de una vez aparecen más, no se pide
  ninguno y queda el aviso, por si se movieron carpetas de más. Una persona lo
  confirma con ``py -3.14 cierre_entregados.py --confirmar``.

Uso:  py -3.14 cierre_entregados.py              (dice qué haría, sin tocar nada)
      py -3.14 cierre_entregados.py --confirmar  (pide los cierres aunque pasen el tope)
"""

import os
import re
import sys
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

HERRAMIENTA = "procesador"
DESTINO = "carpetas-proyecto"
TIPO_MOVER = "mover-carpeta"
TIPO_EDITAR = "editar-requerimiento"
CERRADO = "Cerrado"
SE_CIERRAN = ("Adjudicado",)                 # lo que pasa solo a «Cerrado» (requerimientos.ESTADOS_GANADOS sin él)
GRUPO = "0 Proyectos Entregados"             # + « <año>»: así se llaman en Gestión (2025 y 2026, medido el 2026-11-09)
_GRUPO = re.compile(r"^0\s+proyectos\s+entregados\b", re.IGNORECASE)
MAX_CIERRES = 5
ESPERA_PLANILLA = timedelta(minutes=30)      # OneDrive puede traer el mover-carpeta antes que el cambio de estado
REINTENTAR_HASTA = timedelta(days=7)         # una carpeta con algo abierto


# ── LAS CARPETAS ─────────────────────────────────────────────────────────────

def _numero(nombre: str) -> int | None:
    """El N° de la Planilla al comienzo del nombre («036. Quilpué» → 36). Un N° temporal («001t») no es de la Planilla."""
    coincide = proyectos._CARPETA_CON_NUMERO.match(nombre)
    return int(coincide.group(1)) if coincide and coincide.group(1).isdigit() else None


def _hijas(carpeta: Path) -> list[Path]:
    try:
        return sorted(h for h in Path(carpeta).iterdir() if h.is_dir() and not h.name.startswith((".", "~$")))
    except OSError:
        return []


def grupos_entregados(gestion: Path) -> list[Path]:
    """Las carpetas «0 Proyectos Entregados <año>» de la raíz de Gestión."""
    return [h for h in _hijas(gestion) if _GRUPO.match(h.name)]


def entregadas(gestion: Path) -> list[dict]:
    """[{'carpeta', 'grupo', 'req' (int o None), 'ruta'}] de los proyectos que ya están en algún «0 Proyectos Entregados»."""
    return [{"carpeta": h.name, "grupo": g.name, "req": _numero(h.name), "ruta": h}
            for g in grupos_entregados(gestion) for h in _hijas(g)]


def en_raiz(gestion: Path) -> dict[int, list[Path]]:
    """{N°: [carpetas]} de los proyectos con N° de la raíz de Gestión (sin las agrupadoras «0 …»)."""
    salida: dict[int, list[Path]] = {}
    for h in _hijas(gestion):
        n = None if h.name.startswith(proyectos.CARPETAS_AGRUPADORAS) else _numero(h.name)
        if n is not None:
            salida.setdefault(n, []).append(h)
    return salida


def grupo_del_anio(gestion: Path, anio: int) -> Path:
    """La carpeta de entregados de ese año: la que ya existe (sin distinguir mayúsculas) o la que hay que crear."""
    nombre = f"{GRUPO} {anio}"
    for g in grupos_entregados(gestion):
        if g.name.strip().lower() == nombre.lower():
            return g
    return Path(gestion) / nombre


# ── LA PLANILLA ──────────────────────────────────────────────────────────────

def _planilla(raiz: Path) -> dict[int, dict]:
    datos = (intercambio.leer_publicacion(raiz, requerimientos.PUBLICACION) or {}).get("datos") or {}
    salida = {}
    for r in datos.get("requerimientos") or []:
        try:
            salida[int(r.get("numero"))] = r
        except (TypeError, ValueError):
            continue
    return salida


def _cierres_en_camino(raiz: Path) -> set[int]:
    """N° con un cambio a «Cerrado» que todavía espera en el buzón (del Portal o de una vuelta anterior)."""
    mensajes, _ = intercambio.leer_buzon(raiz, destino=requerimientos.DESTINO, tipo=TIPO_EDITAR)
    salida = set()
    for m in mensajes:
        if (m.get("cambios") or {}).get("estado") == CERRADO:
            try:
                salida.add(int((m.get("requerimiento") or {}).get("numero")))
            except (TypeError, ValueError):
                continue
    return salida


def _instante(texto) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.astimezone()


# ── 1. MOVER LO QUE PIDIÓ EL PORTAL ─────────────────────────────────────────

def mover(raiz: Path, gestion: Path, ahora: datetime | None = None) -> dict:
    """Atiende los mover-carpeta del buzón. {'movidas', 'esperan', 'rechazadas', 'avisos'} (listas de textos)."""
    ahora = ahora or datetime.now().astimezone()
    r = {"movidas": [], "esperan": [], "rechazadas": [], "avisos": []}
    mensajes, _ = intercambio.leer_buzon(raiz, destino=DESTINO, tipo=TIPO_MOVER)
    if not mensajes:
        return r
    planilla = _planilla(raiz)
    en_camino = _cierres_en_camino(raiz)
    raiz_gestion = en_raiz(gestion)
    ya_entregadas = {}
    for e in entregadas(gestion):
        if e["req"] is not None:
            ya_entregadas.setdefault(e["req"], []).append(e)

    def archivar(m, estado, texto, **extra):
        intercambio.archivar(raiz, m, estado, [texto], extra=dict(extra, requerimiento=m["requerimiento"]["numero"]))
        (r["movidas"] if estado == "aplicado" else r["rechazadas"]).append(texto)

    for m in mensajes:
        errores = esquemas.validar_mensaje(m)
        if errores:
            intercambio.archivar(raiz, m, "rechazado", errores)
            r["rechazadas"].append("; ".join(errores))
            continue
        n = int(m["requerimiento"]["numero"])
        enviado = _instante(m["origen"]["enviado"])
        reciente = enviado is not None and ahora - enviado < ESPERA_PLANILLA
        carpetas = raiz_gestion.get(n) or []
        if not carpetas:
            if n in ya_entregadas:
                e = ya_entregadas[n][0]
                archivar(m, "sin-cambios", f"N° {n}: su carpeta ya está en «{e['grupo']}/{e['carpeta']}».")
            elif reciente:
                r["esperan"].append(f"N° {n}: su carpeta no está en Gestión de Proyectos (OneDrive puede estar trayéndola).")
            else:
                archivar(m, "rechazado", f"N° {n}: no hay una carpeta con ese N° en la raíz de Gestión de Proyectos; no se movió nada.")
            continue
        if len(carpetas) > 1:
            archivar(m, "rechazado", f"N° {n}: hay {len(carpetas)} carpetas con ese N° en Gestión de Proyectos "
                                     f"({', '.join(c.name for c in carpetas)}); lo decide una persona.")
            continue
        estado = str((planilla.get(n) or {}).get("estado") or "")
        if estado != CERRADO and n not in en_camino:
            if reciente:
                r["esperan"].append(f"N° {n}: espera que la Planilla diga «{CERRADO}».")
            else:
                archivar(m, "descartado", f"N° {n}: la Planilla dice «{estado or 'sin estado'}», no «{CERRADO}» "
                                          "(el cambio se retiró o se reemplazó): la carpeta quedó donde estaba.")
            continue
        origen = carpetas[0]
        grupo = grupo_del_anio(gestion, ahora.year)
        destino = grupo / origen.name
        if destino.exists():
            archivar(m, "rechazado", f"N° {n}: en «{grupo.name}» ya hay una carpeta «{origen.name}»; no se pisa. "
                                     "Revisa cuál sirve y mueve la otra a mano.")
            continue
        try:
            grupo.mkdir(exist_ok=True)
            # Mismo disco y misma biblioteca: un cambio de nombre, que OneDrive sube como movimiento (no copia y borra)
            os.rename(origen, destino)
        except OSError as error:
            if enviado is not None and ahora - enviado > REINTENTAR_HASTA:
                archivar(m, "rechazado", f"N° {n}: no se pudo mover «{origen.name}» en 7 días ({error}). Muévela a mano.")
            else:
                r["esperan"].append(f"N° {n}: no se pudo mover «{origen.name}» (¿un archivo abierto?); se reintenta.")
                r["avisos"].append(f"carpeta del N° {n} sin mover: {str(error)[:150]}")
            continue
        archivar(m, "aplicado", f"N° {n}: «{origen.name}» pasó a «{grupo.name}».", carpeta=f"{grupo.name}/{origen.name}")
        raiz_gestion.pop(n, None)
    return r


# ── 2. CERRAR LO ENTREGADO A MANO ────────────────────────────────────────────

def plan_cierres(raiz: Path, gestion: Path, cerrados: dict) -> dict:
    """Qué pedir, sin tocar nada. {'pedir': [(N°, fila, carpeta)], 'avisos': [...], 'sinNumero': n, 'yaCerrados': n,
    'respetados': [N°]}."""
    planilla = _planilla(raiz)
    en_camino = _cierres_en_camino(raiz)
    raiz_gestion = en_raiz(gestion)
    por_n: dict[int, list[dict]] = {}
    sin_numero = 0
    for e in entregadas(gestion):
        if e["req"] is None:
            sin_numero += 1
        else:
            por_n.setdefault(e["req"], []).append(e)
    plan = {"pedir": [], "avisos": [], "sinNumero": sin_numero, "yaCerrados": 0, "respetados": []}
    for n, lista in sorted(por_n.items()):
        nombre = f"«{lista[0]['grupo']}/{lista[0]['carpeta']}»"
        fila = planilla.get(n)
        estado = str((fila or {}).get("estado") or "")
        if estado == CERRADO or n in en_camino:
            plan["yaCerrados"] += 1
            continue
        if str(n) in cerrados:
            plan["respetados"].append(n)      # ya se pidió una vez y alguien lo cambió después: manda esa persona
            continue
        if len(lista) > 1:
            plan["avisos"].append(f"N° {n}: {len(lista)} carpetas en los entregados ({', '.join(e['carpeta'] for e in lista)}); no se cerró.")
            continue
        if n in raiz_gestion:
            plan["avisos"].append(f"N° {n}: tiene carpeta en los entregados y también en la raíz de Gestión "
                                  f"(«{raiz_gestion[n][0].name}»); no se cerró. Deja una sola.")
            continue
        if fila is None:
            plan["avisos"].append(f"N° {n}: {nombre} está en los entregados, pero ese N° no está en la Planilla; revisa el N° de la carpeta.")
            continue
        if estado not in SE_CIERRAN:
            plan["avisos"].append(f"N° {n}: {nombre} está en los entregados, pero la Planilla dice «{estado or 'sin estado'}»; "
                                  "no se cerró. Si se adjudicó y entregó, cámbialo a «Cerrado»; si no, revisa el N° de la carpeta.")
            continue
        plan["pedir"].append((n, fila, lista[0]))
    return plan


def _mensaje_cierre(fila: dict, entregada: dict) -> dict:
    n = int(fila["numero"])
    requerimiento = {"numero": n}
    if str(fila.get("titulo") or "").strip():
        requerimiento["titulo"] = str(fila["titulo"]).strip()       # confirma la fila al escribir
    return {
        "esquema": intercambio.ESQUEMA, "id": intercambio.nuevo_id(), "tipo": TIPO_EDITAR,
        "destino": requerimientos.DESTINO,
        "origen": {"herramienta": HERRAMIENTA, "enviado": intercambio.ahora_iso()},
        "requerimiento": requerimiento,
        "cambios": {"estado": CERRADO},
        # Lo que se veía: si en el Excel alguien ya le puso otra cosa, manda el cambio más reciente
        "reemplaza": {"estado": fila.get("estado")},
        "fuente": {"herramienta": HERRAMIENTA, "codigo": f"{entregada['grupo']}/{entregada['carpeta']}"[:200]},
    }


def pedir_cierres(raiz: Path, gestion: Path, previo: dict | None, confirmar: bool = False) -> tuple[dict, dict]:
    """(resumen, estado nuevo). El estado es {'cerrados': {N°: fecha}}: lo que ya se pidió una vez."""
    cerrados = dict((previo or {}).get("cerrados") or {})
    plan = plan_cierres(raiz, gestion, cerrados)
    resumen = {"pedidos": [], "avisos": list(plan["avisos"]), "sinNumero": plan["sinNumero"],
               "yaCerrados": plan["yaCerrados"], "respetados": plan["respetados"]}
    if len(plan["pedir"]) > MAX_CIERRES and not confirmar:
        resumen["avisos"].append(
            f"{len(plan['pedir'])} proyectos aparecieron de una vez en «{GRUPO}» con la Planilla en «Adjudicado» (N° "
            + ", ".join(str(n) for n, _, _ in plan["pedir"]) + f"); pasan del tope de {MAX_CIERRES} y no se cerró ninguno. "
            "Si están bien, ciérralos con: py -3.14 cierre_entregados.py --confirmar")
        return resumen, {"cerrados": cerrados}
    for n, fila, entregada in plan["pedir"]:
        intercambio.enviar(raiz, _mensaje_cierre(fila, entregada))
        cerrados[str(n)] = intercambio.ahora_iso()
        resumen["pedidos"].append(n)
    return resumen, {"cerrados": cerrados}


# ── LA VUELTA ────────────────────────────────────────────────────────────────

def vuelta(raiz: Path, gestion: Path | None, previo: dict | None, confirmar: bool = False) -> tuple[str, dict, list]:
    """(detalle, estado nuevo, avisos) del paso del procesador."""
    if gestion is None or not Path(gestion).is_dir():
        return "la biblioteca «Gestión de Proyectos» no está sincronizada en este equipo", dict(previo or {}), []
    movidas = mover(raiz, Path(gestion))
    resumen, estado = pedir_cierres(raiz, Path(gestion), previo, confirmar)
    partes = []
    if movidas["movidas"]:
        partes.append("movidas a los entregados: " + "; ".join(movidas["movidas"]))
    if movidas["esperan"]:
        partes.append("por mover: " + "; ".join(movidas["esperan"]))
    if movidas["rechazadas"]:
        partes.append("sin mover: " + "; ".join(movidas["rechazadas"]))
    if resumen["pedidos"]:
        partes.append("pasan a «Cerrado» en la Planilla: N° " + ", ".join(str(n) for n in resumen["pedidos"]))
    if resumen["avisos"]:
        partes.append("revisar: " + "; ".join(resumen["avisos"]))
    partes.append(f"{resumen['yaCerrados']} ya cerrados; {resumen['sinNumero']} carpeta(s) sin N° en los entregados")
    avisos = movidas["avisos"] + [f"entregados: {a}" for a in resumen["avisos"]]
    return "; ".join(partes), estado, avisos


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except AttributeError:
        pass
    raiz = ubicacion.ubicar_intercambio(AQUI)
    gestion = ubicacion.biblioteca(ubicacion.BIBLIOTECA_GESTION, AQUI)
    if raiz is None or gestion is None:
        print("Falta la carpeta de Intercambio o la biblioteca «Gestión de Proyectos» en este equipo.")
        return 1
    # El mismo estado que guarda el procesador (sus firmas, paso «entregados»)
    import json
    ruta_estado = AQUI / "procesador_estado.json"
    try:
        firmas = json.loads(ruta_estado.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        firmas = {}
    previo = firmas.get("entregados") if isinstance(firmas.get("entregados"), dict) else {}
    if "--confirmar" not in argv:
        plan = plan_cierres(raiz, gestion, dict(previo.get("cerrados") or {}))
        print(f"Pasarían a «Cerrado» ({len(plan['pedir'])}): " + (", ".join(f"N° {n} ({e['carpeta']})" for n, _, e in plan["pedir"]) or "ninguno"))
        for a in plan["avisos"]:
            print("  revisar:", a)
        print(f"{plan['yaCerrados']} ya cerrados; {plan['sinNumero']} carpeta(s) sin N°; respetados: {plan['respetados'] or 'ninguno'}")
        return 0
    # Con el candado del procesador: su vuelta guarda el mismo archivo de estado
    import procesar
    try:
        procesar._tomar_candado()
    except procesar.Ocupado as error:
        print(f"[INFO] {error}: vuelve a intentarlo en unos minutos.")
        return 1
    try:
        try:
            firmas = json.loads(ruta_estado.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            firmas = {}
        previo = firmas.get("entregados") if isinstance(firmas.get("entregados"), dict) else {}
        resumen, estado = pedir_cierres(raiz, gestion, previo, confirmar=True)
        firmas["entregados"] = estado
        ruta_estado.write_text(json.dumps(firmas, ensure_ascii=False, indent=1), encoding="utf-8")
    finally:
        procesar.RUTA_CANDADO.unlink(missing_ok=True)
    print("Pedido «Cerrado» para: " + (", ".join(f"N° {n}" for n in resumen["pedidos"]) or "ninguno"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
