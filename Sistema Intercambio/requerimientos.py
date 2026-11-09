# -*- coding: utf-8 -*-
"""
requerimientos.py -- La Planilla de Ingreso de Requerimientos, vista por las
demás herramientas.

Vive en la raíz de la biblioteca «Formulación de proyectos - Documentos». Desde
el 2026-10-29 se ingresa y se cambia en la vista «Planilla de Ingreso» del
Portal QUEMPIN, y este Excel queda de respaldo, al día en los dos sentidos. Su
N° es lo primero que se asigna a un proyecto y ya prefija las carpetas de
SharePoint («280. UMAG - …»), así que es la **clave común de proyecto** del
intercambio (plan de integración, 2026-09-30, §5.2).

Este módulo hace dos cosas, y ninguna escribe la planilla (lo único que se
escribe en ella, con Excel, está en ``planilla_escritura.py``: los N° fijos,
los proyectos nuevos del Formulador y del Portal, y lo que se cambia en el
Portal):

1. **Publica** una copia de solo lectura en ``publicado/requerimientos.json``
   (``publicar``), para que el Formulador cree proyectos desde un
   requerimiento y el registro de proyectos cruce claves.
2. **Cierra las sugerencias** que le mandan otras herramientas (mensaje
   ``actualizar-requerimiento``: estado, valor ofertado, valor adjudicado)
   cuando una persona ya las pasó a la planilla (``revisar_sugerencias``).

POR QUÉ NO SE ESCRIBE LA PLANILLA (medido el 2026-10-01 sobre una copia):
guardarla con openpyxl conserva valores, validaciones, formato condicional y
la tabla «Proyectos», pero **borra** ``xl/metadata.xml`` y ``xl/richData/*``
--lo que Excel usa para las fórmulas de matriz dinámica y las imágenes dentro
de celdas-- además de ``calcChain.xml``; el archivo baja de 147 KB a 87 KB.
Es la planilla que el equipo abre todos los días y la pérdida sería
silenciosa. Por eso una sugerencia se aplica **a mano** y se archiva sola
cuando la planilla ya muestra esos valores: la evidencia se busca donde vive
el dato, no en una confirmación aparte.
"""

import math
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

import esquemas
import intercambio

PUBLICACION = "requerimientos"
HERRAMIENTA = "planilla-requerimientos"
DESTINO = "planilla-requerimientos"
TIPO_SUGERENCIA = "actualizar-requerimiento"
HOJA = "Listado Requerimientos"
FUENTE = "Planilla de Ingreso de Requerimientos"

# Encabezado normalizado (sin tildes, minúsculas, sin puntos ni °) -> clave.
# Por nombre y no por posición: si alguien inserta una columna, nada se corre.
COLUMNAS = {
    "n": "numero",
    "estado": "estado",
    "canal": "canal",
    "capt": "captador",
    "eval": "evaluador",
    "titulo": "titulo",
    "cliente": "cliente",
    "ubicacion": "ubicacion",
    "id o referencia": "referencia",
    "apertura": "apertura",
    "cierre": "cierre",
    "visita": "visita",
    "visitador": "visitador",
    "presupuesto (iva inc)": "presupuesto",
    "valor ofertado (iva inc)": "valorOfertado",
    "valor adjudicado (iva inc)": "valorAdjudicado",
    "entrega (dias)": "entregaDias",
    "plazo oferta (dias)": "plazoOfertaDias",
}
NUMERICAS = {"presupuesto", "valorOfertado", "valorAdjudicado", "entregaDias", "plazoOfertaDias"}
# Lo que la planilla y una sugerencia comparten (clave de la sugerencia ->
# clave de la planilla publicada).
CAMPOS_SUGERIBLES = {"estado": "estado", "valorOfertado": "valorOfertado", "valorAdjudicado": "valorAdjudicado"}
TITULO_COLUMNA = {"estado": "Estado", "valorOfertado": "Valor ofertado (IVA inc)",
                  "valorAdjudicado": "Valor adjudicado (IVA inc)"}

_ERROR_EXCEL = re.compile(r"^#(VALUE|REF|N/A|NAME|DIV/0|NUM|NULL|SPILL|CALC)[!?]?$", re.IGNORECASE)


def normalizar_encabezado(texto) -> str:
    plano = "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if unicodedata.category(c) != "Mn")
    plano = plano.lower().replace("°", "").replace("º", "").replace(".", "")
    return re.sub(r"\s+", " ", plano).strip()


def _valor(valor, clave: str):
    if valor is None:
        return None
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto or _ERROR_EXCEL.match(texto):
            return None
        if clave in NUMERICAS:
            try:
                return float(texto.replace(".", "").replace(",", "."))
            except ValueError:
                return None
        return texto
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, datetime):
        return valor.date().isoformat() if valor.time() == datetime.min.time() else valor.isoformat(timespec="minutes")
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, (int, float)):
        if not math.isfinite(valor):
            return None
        if clave in NUMERICAS:
            return int(valor) if float(valor).is_integer() else float(valor)
        return str(int(valor)) if float(valor).is_integer() else str(valor)
    return str(valor)


def _numero(valor) -> int | None:
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)) and math.isfinite(valor) and float(valor).is_integer() and valor >= 1:
        return int(valor)
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    return None


# ── LECTURA ──────────────────────────────────────────────────────────────────

_NS_HOJA = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_RICO = "{http://schemas.microsoft.com/office/spreadsheetml/2017/richdata}"
_NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _columna_n(ref: str) -> int:
    n = 0
    for c in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(c) - 64
    return n


def entidades_vinculadas(ruta: Path, hoja: str = HOJA) -> dict[tuple, str]:
    """{(fila, columna): nombre} de las celdas con un tipo de dato vinculado de Excel.

    «Ubicación» se escribe casi siempre como dato geográfico (Datos › Geografía): Excel la muestra
    como «Valparaíso», pero en el archivo la celda guarda el error #VALUE! y apunta (atributo vm)
    a xl/richData, donde está el nombre. openpyxl no sigue ese puntero, así que hasta el 2026-10-29
    se publicaban vacías 256 de 323 ubicaciones. Camino: vm → metadata.xml (valueMetadata → futureMetadata
    XLRICHVALUE) → rdrichvalue.xml → su estructura en rdrichvaluestructure.xml → la clave _DisplayString."""
    import zipfile
    from xml.etree import ElementTree as ET

    try:
        z = zipfile.ZipFile(ruta)
    except (OSError, zipfile.BadZipFile):
        return {}
    with z:
        nombres = set(z.namelist())
        if not {"xl/metadata.xml", "xl/richData/rdrichvalue.xml", "xl/richData/rdrichvaluestructure.xml"} <= nombres:
            return {}
        libro = ET.fromstring(z.read("xl/workbook.xml"))
        rid = next((s.get(_NS_REL + "id") for s in libro.iter(_NS_HOJA + "sheet") if s.get("name") == hoja), None)
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        destino = next((r.get("Target") for r in rels if r.get("Id") == rid), None)
        if not destino:
            return {}
        parte = destino.lstrip("/") if destino.startswith("/") else "xl/" + destino
        estructuras = [[k.get("n") for k in s] for s in ET.fromstring(z.read("xl/richData/rdrichvaluestructure.xml"))]
        nombres_rv = []
        for rv in ET.fromstring(z.read("xl/richData/rdrichvalue.xml")):
            claves = estructuras[int(rv.get("s"))] if int(rv.get("s", -1)) < len(estructuras) else []
            valores = dict(zip(claves, (x.text for x in rv)))
            nombres_rv.append((valores.get("_DisplayString") or "").strip() or None)
        meta = ET.fromstring(z.read("xl/metadata.xml"))
        tipos = [t.get("name") for t in meta.iter(_NS_HOJA + "metadataType")]
        futuro = []
        for fm in meta.iter(_NS_HOJA + "futureMetadata"):
            if fm.get("name") == "XLRICHVALUE":
                futuro = [next((int(x.get("i")) for x in bk.iter(_NS_RICO + "rvb")), None) for bk in fm.iter(_NS_HOJA + "bk")]
        valor_meta = []
        for vm in meta.iter(_NS_HOJA + "valueMetadata"):
            for bk in vm.iter(_NS_HOJA + "bk"):
                rc = bk.find(_NS_HOJA + "rc")
                ok = rc is not None and 0 < int(rc.get("t")) <= len(tipos) and tipos[int(rc.get("t")) - 1] == "XLRICHVALUE"
                valor_meta.append(int(rc.get("v")) if ok else None)
        salida = {}
        with z.open(parte) as f:
            for _, c in ET.iterparse(f):
                if c.tag != _NS_HOJA + "c":
                    continue
                vm = c.get("vm")
                if vm and vm.isdigit() and 0 < int(vm) <= len(valor_meta):
                    k = valor_meta[int(vm) - 1]
                    i = futuro[k] if k is not None and k < len(futuro) else None
                    nombre = nombres_rv[i] if i is not None and i < len(nombres_rv) else None
                    if nombre:
                        ref = c.get("r")
                        salida[(int(re.search(r"\d+", ref).group()), _columna_n(ref))] = nombre
                c.clear()
        return salida


def leer_planilla(ruta: Path, avisos: list | None = None) -> list[dict]:
    """Una fila por requerimiento con N°. Solo lectura (read_only + valores).
    Un N° repetido se queda con la primera fila. Lo que por eso no llega a las
    herramientas (la fila repetida, una fila con datos y sin N°) lo dice en
    'avisos': el Portal lo muestra, porque esas filas solo se ven en el Excel."""
    import openpyxl

    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        hoja = libro[HOJA] if HOJA in libro.sheetnames else libro.worksheets[0]
        filas = hoja.iter_rows(values_only=True)
        encabezados = next(filas, ())
        indices = {}
        for i, texto in enumerate(encabezados):
            clave = COLUMNAS.get(normalizar_encabezado(texto))
            if clave and clave not in indices:
                indices[clave] = i
        if "numero" not in indices:
            raise ValueError(f"la hoja «{hoja.title}» no tiene la columna N°")
        vinculadas = entidades_vinculadas(ruta, hoja.title)
        salida, vistos = [], set()
        for n_fila, fila in enumerate(filas, start=2):
            numero = _numero(fila[indices["numero"]] if indices["numero"] < len(fila) else None)
            titulo = _valor(fila[indices["titulo"]], "titulo") if "titulo" in indices and indices["titulo"] < len(fila) else None
            if numero is None:
                estado = _valor(fila[indices["estado"]], "estado") if "estado" in indices and indices["estado"] < len(fila) else None
                if (titulo or estado) and avisos is not None:
                    avisos.append(f"La fila {n_fila} «{titulo or estado}» no tiene N° en la planilla: no se ve en las herramientas.")
                continue
            if numero in vistos:
                if avisos is not None:
                    avisos.append(f"El N° {numero} aparece más de una vez en la planilla: se usa la primera fila; "
                                  f"la fila {n_fila} «{titulo or ''}» no se ve en las herramientas.")
                continue
            vistos.add(numero)
            registro = {"numero": numero}
            for clave, i in indices.items():
                if clave != "numero":
                    valor = _valor(fila[i] if i < len(fila) else None, clave)
                    if valor is None and (n_fila, i + 1) in vinculadas and clave not in NUMERICAS:
                        valor = vinculadas[(n_fila, i + 1)]
                    registro[clave] = valor
            for clave in ("estado", "titulo"):
                registro.setdefault(clave, None)
            salida.append(registro)
        return salida
    finally:
        libro.close()


def resumen(requerimientos: list[dict]) -> dict:
    por_estado: dict[str, int] = {}
    for r in requerimientos:
        estado = r.get("estado") or "(sin estado)"
        por_estado[estado] = por_estado.get(estado, 0) + 1
    adjudicados = por_estado.get("Adjudicado", 0)
    perdidos = por_estado.get("No adjudicado", 0)
    return {
        "total": len(requerimientos),
        "porEstado": por_estado,
        # De lo que se ofertó y ya se resolvió, cuánto se ganó. Lo usa Flujo
        # de Caja para ponderar lo que sigue "Ofertado".
        "tasaAdjudicacion": round(adjudicados / (adjudicados + perdidos), 4) if adjudicados + perdidos else None,
    }


def datos_publicacion(ruta_planilla: Path) -> dict:
    avisos: list[str] = []
    reqs = leer_planilla(ruta_planilla, avisos)
    modificado = datetime.fromtimestamp(Path(ruta_planilla).stat().st_mtime).astimezone()
    return {
        "fuente": FUENTE,
        "actualizado": modificado.isoformat(timespec="seconds"),
        "requerimientos": reqs,
        "resumen": resumen(reqs),
        "avisos": avisos,
    }


def _clave_fila(r: dict) -> tuple:
    return (normalizar_encabezado(r.get("titulo")), normalizar_encabezado(r.get("referencia")))


def renumerados(anteriores: list[dict], nuevos: list[dict]) -> list[tuple]:
    """(N° publicado, N° de ahora, título) de los requerimientos que siguen en
    la planilla con el mismo título y referencia, pero bajo otro N°.

    Hasta el 2026-10-26 el N° de casi todas las filas era la fórmula
    =SI(B<>"";FILA()-1;""): ese día alguien ordenó la tabla y 55
    requerimientos cambiaron de N°. Desde entonces planilla_escritura.py deja
    cada N° fijo, pero una fila nueva escrita a mano tiene la fórmula hasta
    su vuelta siguiente. El N° es la clave de las carpetas, del Formulador y
    del Análisis Financiero, así que publicarlo corrido cruzaría proyectos
    en todas las herramientas."""
    nuevo_por_n = por_numero(nuevos)
    donde: dict = {}
    for r in nuevos:
        donde.setdefault(_clave_fila(r), []).append(r["numero"])
    salida = []
    for r in anteriores:
        clave = _clave_fila(r)
        if not clave[0]:
            continue
        actual = nuevo_por_n.get(r["numero"])
        if actual is not None and _clave_fila(actual) == clave:
            continue
        otros = donde.get(clave) or []
        if len(otros) == 1:
            salida.append((r["numero"], otros[0], r.get("titulo")))
    return salida


# Desde cuántos N° movidos se frena la publicación. Uno o dos pueden ser una
# corrección a mano (un N° repetido que alguien arregla); más es un orden.
UMBRAL_RENUMERADOS = 3


class PlanillaRenumerada(RuntimeError):
    def __init__(self, movidos: list[tuple]):
        self.movidos = movidos
        ejemplos = "; ".join(f"{a} → {b} «{(t or '').strip()[:40]}»" for a, b, t in movidos[:4])
        super().__init__(
            f"La Planilla le cambió el N° a {len(movidos)} requerimientos ({ejemplos}…): ¿se ordenó la tabla? "
            "El N° es la fórmula FILA()-1. Se mantiene la publicación anterior hasta que la Planilla vuelva "
            "a sus N° (o se acepte con aceptar_renumeracion=True).")


def desaparecidos(previos: dict, nuevos: list[dict], hoy: str) -> list[dict]:
    """[{numero, titulo, desde}] de los N° que estaban publicados y ya no están
    en la Planilla, ni con otro N° (eso es `renumerados`).

    El freno de renumeración no ve una fila borrada: el N° desaparecía en
    silencio y con él el cruce con carpetas, Formulador y AF (2026-11-09). Se
    arrastran de una publicación a la siguiente, con la fecha en que faltaron,
    hasta que el N° vuelva: si no, el aviso duraría una sola vuelta."""
    numeros = {r["numero"] for r in nuevos}
    claves = {_clave_fila(r) for r in nuevos}
    salida = {}
    for d in previos.get("desaparecidos") or []:
        if isinstance(d, dict) and isinstance(d.get("numero"), int) and d["numero"] not in numeros:
            salida[d["numero"]] = d
    for r in previos.get("requerimientos") or []:
        n = r.get("numero")
        if n in numeros or n in salida or (_clave_fila(r)[0] and _clave_fila(r) in claves):
            continue
        salida[n] = {"numero": n, "titulo": r.get("titulo"), "desde": hoy}
    return [salida[n] for n in sorted(salida)]


def aviso_desaparecido(d: dict) -> str:
    return (f"N° {d['numero']} «{(d.get('titulo') or '').strip()[:50]}» ya no está en la Planilla "
            f"(falta desde el {d['desde']}): si se borró la fila, ese N° deja de cruzar con sus carpetas, "
            "el Formulador y el AF. Restáurala o confirma que se eliminó a propósito.")


def publicar(raiz_intercambio: Path, ruta_planilla: Path, aceptar_renumeracion: bool = False) -> Path:
    datos = datos_publicacion(ruta_planilla)
    previa = intercambio.leer_publicacion(raiz_intercambio, PUBLICACION)
    previos = (previa or {}).get("datos") or {}
    if previa and not aceptar_renumeracion:
        movidos = renumerados(previos.get("requerimientos") or [], datos["requerimientos"])
        if len(movidos) >= UMBRAL_RENUMERADOS:
            raise PlanillaRenumerada(movidos)
    faltan = desaparecidos(previos, datos["requerimientos"], datetime.now().date().isoformat())
    if faltan:
        datos["desaparecidos"] = faltan
        datos["avisos"] = datos["avisos"] + [aviso_desaparecido(d) for d in faltan]
    sobre = {"esquema": intercambio.ESQUEMA, "herramienta": HERRAMIENTA, "generado": intercambio.ahora_iso(), "datos": datos}
    errores = esquemas.validar_publicacion(PUBLICACION, sobre)
    if errores:
        raise ValueError("la publicación de requerimientos no cumple su esquema: " + "; ".join(errores[:5]))
    return intercambio.publicar(raiz_intercambio, PUBLICACION, HERRAMIENTA, datos)


def por_numero(requerimientos: list[dict]) -> dict[int, dict]:
    return {r["numero"]: r for r in requerimientos}


# ── SUGERENCIAS (mensaje actualizar-requerimiento) ───────────────────────────

def _igual(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) < 0.5
    if isinstance(a, str) and isinstance(b, str):
        return normalizar_encabezado(a) == normalizar_encabezado(b)
    return a is None and b is None


def decidir_sugerencia(mensaje: dict, requerimiento: dict | None) -> dict:
    """{'accion': 'aplicado'|'pendiente'|'conflicto'|'rechazado', 'detalle': [...], 'falta': {...}}.
    'aplicado' = la planilla ya muestra lo sugerido (se archiva).
    'pendiente' = falta pasarlo a mano. 'conflicto' = la planilla cambió
    después de que quien sugirió la miró (reemplaza no calza)."""
    errores = esquemas.validar_mensaje(mensaje)
    if errores:
        return {"accion": "rechazado", "detalle": errores, "falta": {}}
    numero = mensaje["requerimiento"]["numero"]
    if requerimiento is None:
        return {"accion": "pendiente", "falta": dict(mensaje["cambios"]),
                "detalle": [f"El requerimiento N° {numero} no está en la planilla (¿N° mal escrito?)."]}
    reemplaza = mensaje.get("reemplaza") or {}
    falta, conflictos = {}, []
    for clave, nuevo in mensaje["cambios"].items():
        actual = requerimiento.get(CAMPOS_SUGERIBLES[clave])
        if _igual(actual, nuevo):
            continue
        falta[clave] = nuevo
        if clave in reemplaza and not _igual(actual, reemplaza[clave]):
            conflictos.append(f"{TITULO_COLUMNA[clave]}: la planilla dice {_texto(actual)}; "
                              f"quien sugirió vio {_texto(reemplaza[clave])}.")
    if not falta:
        return {"accion": "aplicado", "falta": {}, "detalle": ["La planilla ya muestra lo sugerido."]}
    detalle = [f"N° {numero} · {TITULO_COLUMNA[c]}: escribir {_texto(v)} (hoy {_texto(requerimiento.get(CAMPOS_SUGERIBLES[c]))})"
               for c, v in falta.items()]
    if conflictos:
        return {"accion": "conflicto", "falta": falta, "detalle": conflictos + detalle}
    return {"accion": "pendiente", "falta": falta, "detalle": detalle}


def _texto(valor) -> str:
    if valor is None:
        return "(vacío)"
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return "$" + f"{round(valor):,}".replace(",", ".")
    return f"«{valor}»"


def reemplazadas(mensajes: list[dict]) -> dict[str, str]:
    """{id: fecha de la más nueva} de las sugerencias cuyas columnas pide
    todas otra posterior para el mismo N° (de cualquier herramienta). Es la
    regla con que el Formulador muestra «Pasar a la Planilla» (la más nueva
    por columna, js/pendientes.js): las anteriores quedaban en el buzón para
    siempre, porque la Planilla nunca iba a mostrar un valor ya superado."""
    salida = {}
    por_n: dict = {}
    for m in mensajes:
        por_n.setdefault((m.get("requerimiento") or {}).get("numero"), []).append(m)
    for grupo in por_n.values():
        grupo.sort(key=lambda m: (m["origen"]["enviado"], m["id"]))
        for i, m in enumerate(grupo):
            posteriores = grupo[i + 1:]
            columnas = set(m.get("cambios") or {})
            if columnas and posteriores and columnas <= {c for x in posteriores for c in (x.get("cambios") or {})}:
                salida[m["id"]] = posteriores[-1]["origen"]["enviado"][:10]
    return salida


def revisar_sugerencias(raiz_intercambio: Path, requerimientos: list[dict], archivar: bool = True) -> list[dict]:
    """Decide cada sugerencia del buzón contra la planilla actual. Con
    'archivar', mueve a procesado/ las que ya están aplicadas ('aplicado')
    y las inválidas ('rechazado'); las demás siguen en el buzón."""
    mensajes, invalidos = intercambio.leer_buzon(raiz_intercambio, destino=DESTINO, tipo=TIPO_SUGERENCIA)
    indice = por_numero(requerimientos)
    nuevas = reemplazadas(mensajes)
    salida = []
    for m in mensajes:
        if m["id"] in nuevas:
            n = (m.get("requerimiento") or {}).get("numero")
            decision = {"accion": "reemplazado", "falta": {}, "mensaje": m,
                        "detalle": [f"N° {n}: hay una sugerencia más nueva para lo mismo ({nuevas[m['id']]})."]}
            if archivar:
                intercambio.archivar(raiz_intercambio, m, "reemplazado", decision["detalle"], extra={"requerimiento": n})
            salida.append(decision)
            continue
        decision = decidir_sugerencia(m, indice.get((m.get("requerimiento") or {}).get("numero")))
        decision["mensaje"] = m
        if archivar and decision["accion"] in ("aplicado", "rechazado"):
            intercambio.archivar(raiz_intercambio, m, decision["accion"], decision["detalle"],
                                 extra={"requerimiento": (m.get("requerimiento") or {}).get("numero")})
        salida.append(decision)
    return salida


def descartar_sugerencia(raiz_intercambio: Path, id_mensaje: str, motivo: str = "") -> bool:
    mensajes, _ = intercambio.leer_buzon(raiz_intercambio, destino=DESTINO, tipo=TIPO_SUGERENCIA)
    for m in mensajes:
        if m["id"] == id_mensaje:
            intercambio.archivar(raiz_intercambio, m, "descartado",
                                 [motivo or "Descartada por el usuario: la planilla queda como está."])
            return True
    return False
