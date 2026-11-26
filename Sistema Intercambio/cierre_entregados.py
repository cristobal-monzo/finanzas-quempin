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
computador que tiene sincronizada la biblioteca «Gestión de Proyectos».

**Cierra** lo entregado a mano: cada carpeta con N° dentro de cualquier
«0 Proyectos Entregados <año>» cuyo requerimiento la Planilla tiene
«Adjudicado» pasa a «Cerrado». El procesador nunca escribe la Planilla: deja
un ``editar-requerimiento`` en el buzón y ``planilla_escritura.py`` lo escribe
en su vuelta, con sus respaldos.

Mover la carpeta que pidió el Portal al cerrar (mensaje ``mover-carpeta``) lo
hacía también este módulo hasta el 2026-11-25; desde entonces lo hace
``carpetas_oferta.py`` (paso ``carpetas-oferta``, justo antes), para todos los
estados.

Frenos:

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

import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import intercambio  # noqa: E402
import proyectos  # noqa: E402
import requerimientos  # noqa: E402
import ubicacion  # noqa: E402

HERRAMIENTA = "procesador"
TIPO_EDITAR = "editar-requerimiento"
CERRADO = "Cerrado"
SE_CIERRAN = ("Adjudicado",)                 # lo que pasa solo a «Cerrado» (requerimientos.ESTADOS_GANADOS sin él)
GRUPO = "0 Proyectos Entregados"             # + « <año>»: así se llaman en Gestión (2025 y 2026, medido el 2026-11-09)
MAX_CIERRES = 5


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
    """Las carpetas «0 Proyectos Entregados <año>» de la raíz de Gestión (la misma regla de proyectos.py)."""
    return [h for h in _hijas(gestion) if proyectos._es_de_entregados(h.name)]


def entregadas(gestion: Path) -> list[dict]:
    """[{'carpeta', 'grupo', 'req' (int o None), 'ruta'}] de los proyectos que ya están en algún «0 Proyectos Entregados».
    Sale de proyectos.proyectos_entregados, lo mismo que publica proyectos.json para la pestaña «Entregados» del Portal;
    aquí solo vale un N° de la Planilla (no uno temporal «001t»)."""
    return [{"carpeta": e["carpeta"], "grupo": e["grupo"], "ruta": Path(gestion) / e["grupo"] / e["carpeta"],
             "req": int(e["req"]) if str(e.get("req") or "").isdigit() else None}
            for e in proyectos.proyectos_entregados(gestion)]


def en_raiz(gestion: Path) -> dict[int, list[Path]]:
    """{N°: [carpetas]} de los proyectos con N° de la raíz de Gestión (sin las agrupadoras «0 …»)."""
    salida: dict[int, list[Path]] = {}
    for h in _hijas(gestion):
        n = None if h.name.startswith(proyectos.CARPETAS_AGRUPADORAS) else _numero(h.name)
        if n is not None:
            salida.setdefault(n, []).append(h)
    return salida


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


# ── CERRAR LO ENTREGADO A MANO ────────────────────────────────────────────

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
    resumen, estado = pedir_cierres(raiz, Path(gestion), previo, confirmar)
    partes = []
    if resumen["pedidos"]:
        partes.append("pasan a «Cerrado» en la Planilla: N° " + ", ".join(str(n) for n in resumen["pedidos"]))
    if resumen["avisos"]:
        partes.append("revisar: " + "; ".join(resumen["avisos"]))
    partes.append(f"{resumen['yaCerrados']} ya cerrados; {resumen['sinNumero']} carpeta(s) sin N° en los entregados")
    avisos = [f"entregados: {a}" for a in resumen["avisos"]]
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
