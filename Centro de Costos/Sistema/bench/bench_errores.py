# -*- coding: utf-8 -*-
"""
bench_errores.py -- mide la eficacia del proceso de deteccion y resolucion de
errores del Centro de Costos sobre un corpus sintetico con ground truth.

    py -3.14 "Centro de Costos/Sistema/bench/bench_errores.py"
    py -3.14 "Centro de Costos/Sistema/bench/bench_errores.py" --repeticiones 3
    py -3.14 "Centro de Costos/Sistema/bench/bench_errores.py" --json salida.json

Que mide, y por que cada metrica
--------------------------------
* deteccion_recall / precision   -- cuantos de los defectos inyectados ve el
  sistema, y cuantas de sus senales caen sobre documentos SANOS (los primeros
  20 del corpus, que nunca se ensucian).
* tasa_no_resuelta               -- METRICA PRINCIPAL. Fraccion de defectos
  inyectados que, tras una corrida completa MAS un recorrido de resolucion
  hecho por un operador perfecto (el arnes conoce el valor correcto), siguen
  sin quedar corregidos ni cerrados. Un defecto que el sistema solo imprime en
  consola cuenta como NO resuelto: no hay forma de cerrarlo ni de evitar que
  reaparezca identico en la corrida siguiente.
* tasa_auto_resolucion           -- defectos que el sistema corrige solo, con
  registro de auditoria, sin intervencion humana.
* segundos_por_resolucion        -- tiempo de pared del recorrido de
  resolucion dividido por los defectos efectivamente cerrados.
* defectos_publicados_sin_detectar -- defectos que llegaron a los consumidores
  aguas abajo (Excel guardado, copia del sitio, visualizador, Analisis
  Financiero) ANTES de que alguien los reportara. Mide validacion tardia.
* hallazgos_reemitidos           -- de los hallazgos de la corrida 1 que
  quedaron sin resolver, cuantos vuelven a emitirse identicos en la corrida 2
  sin ninguna marca de "ya lo vi". Mide falta de deduplicacion.

El arnes NO conoce la implementacion: imputa "detectado" leyendo la salida que
el sistema le da a un humano (el INFORME DE AUDITORIA y las celdas rojas del
libro), que es la unica interfaz que existe hoy.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import corpus_errores as ce  # noqa: E402
import sandbox  # noqa: E402
from sandbox import acc  # noqa: E402

# Documentos sanos de control: los primeros 20 del corpus nunca reciben
# defecto (ver corpus_errores.generar_corpus).
RE_OK = re.compile(r"\[OK\] (?P<proy>[^\\]+)\\(?P<archivo>\S+) -> (?P<nref>[A-Z]+-\d+)")
RE_SECCION = re.compile(r"^\s*(\d)\. [A-ZÁÉÍÓÚÑ]")

# Secciones del INFORME DE AUDITORIA que son HALLAZGOS (7 = notas del JSON, no
# es un hallazgo: solo repite lo que el extractor escribio).
SECCIONES_HALLAZGO = {"1", "2", "3", "4", "5", "6"}


def _mapa_archivo_a_nref(cfg):
    """archivo original -> N Ref, leido de los logs que el propio run deja."""
    mapa = {}
    for log in sorted(Path(cfg["ruta_logs"]).glob("run_*.log")):
        for m in RE_OK.finditer(log.read_text(encoding="utf-8", errors="ignore")):
            mapa[m.group("archivo")] = m.group("nref")
    return mapa


def _texto_hallazgos(salida):
    """Solo el texto de las secciones 1..6 del INFORME DE AUDITORIA."""
    lineas = salida.splitlines()
    try:
        inicio = next(i for i, l in enumerate(lineas) if "INFORME DE AUDITORIA" in l)
    except StopIteration:
        return ""
    seccion = None
    trozos = []
    for linea in lineas[inicio:]:
        m = RE_SECCION.match(linea)
        if m:
            seccion = m.group(1)
            continue
        if "RESUMEN FINAL" in linea:
            seccion = None
        if seccion in SECCIONES_HALLAZGO:
            trozos.append(linea)
    return "\n".join(trozos)


def _celdas_rojas(cfg):
    import openpyxl
    ruta = Path(cfg["ruta_excel"])
    if not ruta.exists():
        return []
    wb = openpyxl.load_workbook(str(ruta), data_only=False)
    if "Master" not in wb.sheetnames:
        return []
    try:
        return acc.listar_celdas_rojas(wb["Master"])
    finally:
        wb.close()


def _items_agrupados(cfg):
    import openpyxl
    ruta = Path(cfg["ruta_excel"])
    if not ruta.exists():
        return []
    wb = openpyxl.load_workbook(str(ruta), data_only=False)
    if "Detalle" not in wb.sheetnames:
        return []
    try:
        return acc.listar_items_agrupados(wb["Detalle"])
    finally:
        wb.close()


def _valor_master(cfg, n_ref, columna):
    import openpyxl
    wb = openpyxl.load_workbook(str(cfg["ruta_excel"]), data_only=False)
    try:
        ws = wb["Master"]
        fila = acc._mapa_filas_por_n_ref(ws).get(n_ref)
        return None if fila is None else ws.cell(row=fila, column=columna).value
    finally:
        wb.close()


def _correcciones_aplicadas(cfg):
    ruta = Path(cfg["ruta_correcciones"])
    if not ruta.exists():
        return {}
    entradas = json.loads(ruta.read_text(encoding="utf-8"))
    return {(c["n_ref"], c.get("columna")): c for c in entradas if c.get("estado") == "Aplicado"}


def _registro_errores(cfg):
    """Todas las entradas del registro persistente de errores, si existe. En
    la linea base no existe ninguno (los hallazgos solo viven en consola):
    devuelve []."""
    ruta = Path(cfg["ruta_correcciones"]).parent / "errores_detectados.json"
    if not ruta.exists():
        return []
    registro = json.loads(ruta.read_text(encoding="utf-8"))
    return registro.get("errores", []) if isinstance(registro, dict) else registro


def _auto_resoluciones(cfg):
    return {e["id"]: e for e in _registro_errores(cfg) if e.get("estado") == "auto_resuelto"}


def _resolver(cfg, defectos, mapa_nref):
    """Operador perfecto: intenta cerrar cada defecto por los canales AUDITADOS
    que el sistema efectivamente ofrece, usando el valor correcto del ground
    truth. Devuelve (cerrados_verificados, segundos).

    "Auditado" es parte de la definicion de resuelto, no un adorno: este es un
    sistema financiero y el modulo entero esta construido sobre la idea de que
    toda correccion a mano queda registrada (fuente azul marino +
    correcciones_manuales.json + ERRORES.md). Editar el JSON de origen a
    escondidas haria desaparecer el sintoma sin dejar constancia de quien
    cambio un monto, asi que no cuenta como resolucion.

    Canales que se prueban, en orden:
      1. registro de hallazgos -> corregir_hallazgos() por LOTE (si existe);
      2. celda roja de Master  -> corregir_valor_manual() de a una;
      3. fila agrupada         -> desglosar_item_agrupado().
    """
    cerrados = []
    t0 = time.perf_counter()

    # -- Canal 1: registro de hallazgos (no existe en la linea base) ---------
    registro = _registro_errores(cfg)
    por_archivo = {}
    for e in registro:
        if e.get("estado") == "abierto" and e.get("n_ref"):
            por_archivo.setdefault(e.get("archivo"), []).append(e)

    lote, esperados = [], []
    for d in defectos:
        if d["valor_correcto"] is None or d["clase"] == "ITEM_AGRUPADO":
            continue
        for e in por_archivo.get(d["archivo"], []):
            if e.get("columna") is None:
                continue
            if not _campo_calza(d, e):
                continue
            lote.append((e["id"], _valor_para(d, e)))
            esperados.append((d, e))
            break

    if lote:
        with contextlib.redirect_stdout(io.StringIO()):
            aplicadas, _ = acc.corregir_hallazgos(
                lote, ruta_excel=cfg["ruta_excel"],
                ruta_correcciones=cfg["ruta_correcciones"],
                ruta_errores=cfg["ruta_errores_md"], ruta_backups=cfg["ruta_backups"])
        ids_ok = {a["id"] for a in aplicadas}
        cerrados = [d for d, e in esperados if e["id"] in ids_ok]

    # -- Canales 2 y 3: los que ya existian ---------------------------------
    ya = {d["archivo"] for d in cerrados}
    rojas = {(c["n_ref"], c["columna"]): c for c in _celdas_rojas(cfg)}
    agrupados = {a["n_ref"]: a for a in _items_agrupados(cfg)}
    for d in defectos:
        if d["archivo"] in ya:
            continue
        n_ref = mapa_nref.get(d["archivo"])
        if n_ref is None:
            continue
        aplicado = False
        with contextlib.redirect_stdout(io.StringIO()):
            if (n_ref, 5) in rojas and d["campo"] == "n_documento" and d["valor_correcto"]:
                aplicado = acc.corregir_valor_manual(
                    n_ref, 5, str(d["valor_correcto"]),
                    ruta_excel=cfg["ruta_excel"], ruta_correcciones=cfg["ruta_correcciones"],
                    ruta_errores=cfg["ruta_errores_md"], ruta_backups=cfg["ruta_backups"],
                ) is not None
            elif (n_ref, 12) in rojas and d["campo"] == "iva" and d["valor_correcto"] is not None:
                aplicado = acc.corregir_valor_manual(
                    n_ref, 12, int(d["valor_correcto"]),
                    ruta_excel=cfg["ruta_excel"], ruta_correcciones=cfg["ruta_correcciones"],
                    ruta_errores=cfg["ruta_errores_md"], ruta_backups=cfg["ruta_backups"],
                ) is not None
            elif n_ref in agrupados and d["clase"] == "ITEM_AGRUPADO":
                aplicado = acc.desglosar_item_agrupado(
                    n_ref, d["valor_correcto"],
                    ruta_excel=cfg["ruta_excel"], ruta_correcciones=cfg["ruta_correcciones"],
                    ruta_errores=cfg["ruta_errores_md"], ruta_backups=cfg["ruta_backups"],
                ) is not None
        if aplicado:
            cerrados.append(d)
    segundos = time.perf_counter() - t0

    # -- Verificacion: el cierre solo cuenta si el valor que quedo en el libro
    #    es el correcto Y quedo asentado en el registro de correcciones -------
    aplicadas_reg = _correcciones_aplicadas(cfg)
    agrupados_ahora = {a["n_ref"] for a in _items_agrupados(cfg)}
    verificados = []
    for d in cerrados:
        n_ref = mapa_nref[d["archivo"]]
        if d["clase"] == "ITEM_AGRUPADO":
            ok = n_ref not in agrupados_ahora
        else:
            columna = _COLUMNA_POR_CLASE.get(d["clase"])
            if columna is None:
                ok = False
            else:
                actual = _valor_master(cfg, n_ref, columna)
                ok = (_comparable(actual) == _comparable(_valor_esperado_en_master(d))
                      and (n_ref, columna) in aplicadas_reg)
        if ok:
            verificados.append(d)
    return verificados, segundos


# Clase de defecto -> columna de Master donde tiene que quedar el valor bueno.
_COLUMNA_POR_CLASE = {
    "N_DOC_ILEGIBLE": 5,
    "TIPO_DOC_DESCONOCIDO": 6,
    "PROVEEDOR_VACIO": 8,
    "CATEGORIA_VACIA": 9,
    "FECHA_INVALIDA": 4,
    "FECHA_FUTURA": 4,
    "IMPUESTO_MENOR": 12,
    "IMPUESTO_EXCESO": 12,
    "IMPUESTO_ESTIMADO": 12,
    "NC_IMPUESTO_DESCUADRADO": 12,
}


def _campo_calza(defecto, entrada):
    return _COLUMNA_POR_CLASE.get(defecto["clase"]) == entrada.get("columna")


def _valor_para(defecto, entrada):
    return _valor_esperado_en_master(defecto)


def _valor_esperado_en_master(defecto):
    """El valor correcto tal como debe quedar escrito en Master."""
    v = defecto["valor_correcto"]
    if _COLUMNA_POR_CLASE.get(defecto["clase"]) == 12:
        return int(v)
    if defecto["clase"] == "N_DOC_ILEGIBLE":
        return str(v)
    return v


def _comparable(valor):
    from datetime import datetime as _dt
    if isinstance(valor, _dt):
        return valor.strftime("%d-%m-%Y")
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return valor


class _Buffer(io.StringIO):
    """main() hace sys.stdout.reconfigure(...) como primera linea; StringIO no
    tiene ese metodo. No-op: el buffer ya es texto Unicode."""

    def reconfigure(self, **kwargs):
        return None


def _correr(cfg, pais=sandbox.PAIS_BENCH):
    buf = _Buffer()
    err = _Buffer()
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        acc.main(pais=pais)
    return buf.getvalue(), time.perf_counter() - t0


def medir(semilla, n_documentos=240, conservar=None):
    documentos, defectos, sin_entrada = ce.generar_corpus(
        n_documentos=n_documentos, semilla=semilla
    )
    archivos_limpios = {d["archivo"] for d in documentos} - {d["archivo"] for d in defectos}

    tmp = Path(tempfile.mkdtemp(prefix="bench_cc_"))
    try:
        cfg = sandbox.montar(tmp, documentos, sin_entrada)

        salida1, seg_run1 = _correr(cfg)
        texto1 = _texto_hallazgos(salida1)
        mapa_nref = _mapa_archivo_a_nref(cfg)
        rojas = _celdas_rojas(cfg)
        agrupados = _items_agrupados(cfg)
        nrefs_marcados = {c["n_ref"] for c in rojas} | {a["n_ref"] for a in agrupados}
        registro1 = _registro_errores(cfg)
        archivos_en_registro = {e.get("archivo") for e in registro1}

        def _senalado(archivo):
            n_ref = mapa_nref.get(archivo)
            if archivo in texto1:
                return True
            if n_ref and re.search(r"\b%s\b" % re.escape(n_ref), texto1):
                return True
            if n_ref and n_ref in nrefs_marcados:
                return True
            return archivo in archivos_en_registro

        # Un duplicado se considera detectado si el sistema nombra a CUALQUIERA
        # de los dos miembros del par. Hoy marca al que se inventaria segundo,
        # que no tiene por que ser la copia sobrante (el inventario recorre las
        # carpetas de proyecto en orden alfabetico): darlo por no detectado
        # seria castigar al sistema por un detalle de atribucion, no por no
        # haber visto el problema.
        def _detectado(d):
            if d["clase"].startswith("DUPLICADO") and d["valor_correcto"]:
                return _senalado(d["archivo"]) or _senalado(d["valor_correcto"])
            return _senalado(d["archivo"])

        detectados = [d for d in defectos if _detectado(d)]
        # Los originales de un par duplicado son documentos sanos que el
        # sistema puede nombrar legitimamente: no cuentan como falso positivo.
        originales_de_par = {d["valor_correcto"] for d in defectos
                             if d["clase"].startswith("DUPLICADO") and d["valor_correcto"]}
        falsos_positivos = [a for a in archivos_limpios
                            if a not in originales_de_par and _senalado(a)]

        cerrados, seg_resolucion = _resolver(cfg, defectos, mapa_nref)
        auto_final = _auto_resoluciones(cfg)
        archivos_auto = {e.get("archivo") for e in auto_final.values()}
        auto_resueltos = [d for d in defectos
                          if d["archivo"] in archivos_auto
                          and d not in cerrados]
        cerrados_total = {d["archivo"] for d in cerrados} | {d["archivo"] for d in auto_resueltos}

        # Corrida 2: mismos datos, nada nuevo. Todo hallazgo que reaparezca
        # identico sin marca de "ya visto" es ruido re-emitido.
        salida2, seg_run2 = _correr(cfg)
        texto2 = _texto_hallazgos(salida2)
        abiertos = [d for d in defectos if d["archivo"] not in cerrados_total]
        # Solo cuenta como ruido re-emitido el hallazgo que vuelve SIN identidad
        # ni antiguedad, o sea indistinguible de uno nuevo. Un hallazgo abierto
        # que reaparece con su id y su "visto Nx desde <fecha>" es seguimiento,
        # no ruido.
        seguidos = {e.get("archivo") for e in _registro_errores(cfg)
                    if e.get("corridas_vistas", 1) > 1}
        reemitidos = [d for d in abiertos
                      if _senalado_en(d, texto2, mapa_nref) and d["archivo"] not in seguidos]

        # Validacion tardia: un defecto se considera "publicado sin detectar" si
        # su hallazgo se imprime DESPUES de que el libro ya se guardo y se
        # copio/propago aguas abajo.
        publicado_antes = _detecta_despues_de_publicar(salida1)
        publicados_sin_detectar = len(detectados) if publicado_antes else 0

        metricas = {
            "semilla": semilla,
            "documentos": len(documentos),
            "defectos_inyectados": len(defectos),
            "documentos_control_sanos": len(archivos_limpios),
            "detectados": len(detectados),
            "deteccion_recall": len(detectados) / len(defectos),
            "falsos_positivos": len(falsos_positivos),
            "tasa_falsos_positivos": len(falsos_positivos) / max(1, len(archivos_limpios)),
            "resueltos_por_operador": len(cerrados),
            "auto_resueltos": len(auto_resueltos),
            "resueltos_total": len(cerrados_total),
            "tasa_no_resuelta": 1 - len(cerrados_total) / len(defectos),
            "tasa_auto_resolucion": len(auto_resueltos) / len(defectos),
            "segundos_resolucion": seg_resolucion,
            "segundos_por_resolucion": (seg_resolucion / len(cerrados)) if cerrados else None,
            "defectos_publicados_sin_detectar": publicados_sin_detectar,
            "hallazgos_reemitidos": len(reemitidos),
            "segundos_run1": seg_run1,
            "segundos_run2": seg_run2,
            "no_detectados_por_clase": _por_clase(
                [d for d in defectos if d not in detectados]),
            "no_resueltos_por_clase": _por_clase(
                [d for d in defectos if d["archivo"] not in cerrados_total]),
        }
        if conservar:
            shutil.copytree(tmp, conservar, dirs_exist_ok=True)
        return metricas
    finally:
        sandbox.desmontar()
        shutil.rmtree(tmp, ignore_errors=True)


def _senalado_en(defecto, texto, mapa_nref):
    n_ref = mapa_nref.get(defecto["archivo"])
    if defecto["archivo"] in texto:
        return True
    return bool(n_ref) and bool(re.search(r"\b%s\b" % re.escape(n_ref), texto))


def _detecta_despues_de_publicar(salida):
    """True si el sistema recien reporta hallazgos DESPUES de guardar el libro
    y propagarlo aguas abajo (PASO 12/12b/12c/12d): en ese caso todo defecto
    detectado ya se publico en los tres consumidores antes de que nadie lo
    viera. Se toma la PRIMERA senal de deteccion que aparece en la salida."""
    i_guardar = salida.find("PASO 12")
    if i_guardar == -1:
        return False
    candidatos = [salida.find(m) for m in ("PASO 5B", "Hallazgos vigentes",
                                           "HALLAZGOS ABIERTOS", "INFORME DE AUDITORIA")]
    candidatos = [i for i in candidatos if i != -1]
    return (min(candidatos) > i_guardar) if candidatos else True


def _por_clase(defectos):
    conteo = {}
    for d in defectos:
        conteo[d["clase"]] = conteo.get(d["clase"], 0) + 1
    return dict(sorted(conteo.items(), key=lambda kv: (-kv[1], kv[0])))


SEMILLAS = (20260910, 411, 90210)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repeticiones", type=int, default=3,
                   help="cuantas semillas distintas medir (max %d)" % len(SEMILLAS))
    p.add_argument("--documentos", type=int, default=240)
    p.add_argument("--json", type=str, default=None, help="guardar el detalle en un archivo")
    args = p.parse_args(argv)

    corridas = [medir(s, args.documentos) for s in SEMILLAS[:args.repeticiones]]

    def prom(clave):
        vals = [c[clave] for c in corridas if c[clave] is not None]
        return statistics.mean(vals) if vals else None

    print("=" * 74)
    print("  BENCHMARK: deteccion y resolucion de errores -- Centro de Costos")
    print("=" * 74)
    print("  Corpus sintetico anonimizado | %d documentos | %d defectos inyectados"
          % (corridas[0]["documentos"], corridas[0]["defectos_inyectados"]))
    print("  Semillas: %s" % ", ".join(str(c["semilla"]) for c in corridas))
    print("-" * 74)
    filas = [
        ("Recall de deteccion", "deteccion_recall", "{:.1%}"),
        ("Tasa de falsos positivos (docs sanos)", "tasa_falsos_positivos", "{:.1%}"),
        ("TASA DE ERRORES NO RESUELTOS", "tasa_no_resuelta", "{:.1%}"),
        ("Tasa de resolucion automatica", "tasa_auto_resolucion", "{:.1%}"),
        ("Defectos cerrados (de %d)" % corridas[0]["defectos_inyectados"],
         "resueltos_total", "{:.1f}"),
        ("Segundos por resolucion aplicada", "segundos_por_resolucion", "{:.2f}"),
        ("Defectos publicados antes de detectarse", "defectos_publicados_sin_detectar", "{:.1f}"),
        ("Hallazgos re-emitidos en la corrida 2", "hallazgos_reemitidos", "{:.1f}"),
        ("Segundos corrida 1", "segundos_run1", "{:.2f}"),
    ]
    for etiqueta, clave, fmt in filas:
        v = prom(clave)
        print("  %-42s %s" % (etiqueta, fmt.format(v) if v is not None else "n/a"))

    print("-" * 74)
    print("  Defectos NO DETECTADOS por clase (promedio de las corridas):")
    agregado = {}
    for c in corridas:
        for k, v in c["no_detectados_por_clase"].items():
            agregado[k] = agregado.get(k, 0) + v
    for k, v in sorted(agregado.items(), key=lambda kv: (-kv[1], kv[0])):
        print("    %-26s %.1f" % (k, v / len(corridas)))

    print("-" * 74)
    print("  Defectos NO RESUELTOS por clase (promedio de las corridas):")
    agregado = {}
    for c in corridas:
        for k, v in c["no_resueltos_por_clase"].items():
            agregado[k] = agregado.get(k, 0) + v
    for k, v in sorted(agregado.items(), key=lambda kv: (-kv[1], kv[0])):
        print("    %-26s %.1f" % (k, v / len(corridas)))
    print("=" * 74)

    if args.json:
        Path(args.json).write_text(json.dumps(corridas, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print("  Detalle guardado en %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
