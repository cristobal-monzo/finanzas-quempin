# -*- coding: utf-8 -*-
"""Lo que se escribe en la Planilla de Ingreso: N° fijos, proyectos nuevos del Formulador y del Portal, y lo que
se cambia en el Portal.

Siempre sobre una planilla armada en tmp_path, y sin Excel: «escribir» se reemplaza por una versión
con openpyxl que aplica las mismas operaciones (la real, planilla_excel.ps1, se probó a mano sobre una
copia de la planilla el 2026-10-26 y el 2026-10-29)."""
import json
import os
from datetime import date, datetime, timedelta

import openpyxl
import pytest

import esquemas
import intercambio as ic
import planilla_escritura as pe
import requerimientos as rq

# Las columnas de la planilla real desde el 2026-10-27, con «Cliente» entre Título y Ubicación
ENCABEZADOS = ["N°", "Estado", "Canal", "Capt.", "Eval.", "Título", "Cliente", "Ubicación", "ID o Referencia", "Apertura",
               "Cierre", "Visita", "Eº visita", "Visitador", "Presupuesto (IVA inc.)", "Valor ofertado (IVA inc)",
               "Valor adjudicado (IVA inc)", "Entrega (días)", "Plazo Oferta (días)"]
COLUMNAS = pe.columnas_de(ENCABEZADOS)


def _planilla(tmp_path, filas, vacias=3):
    """filas: (N° fijo o None = fórmula, título). La fórmula guarda su valor como lo haría Excel."""
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = rq.HOJA
    hoja.append(ENCABEZADOS)
    for i, (numero, titulo) in enumerate(filas, start=2):
        hoja.append([numero if numero is not None else f'=IF(B{i}<>"",ROW()-1, "")', "Evaluación", "Otro", "NB", "NB",
                     titulo, None, "Valdivia", "-", datetime(2026, 10, 20)])
    for j in range(vacias):
        hoja.append([f'=IF(B{len(filas) + 2 + j}<>"",ROW()-1, "")'])
    ruta = tmp_path / "Planilla.xlsx"
    libro.save(ruta)
    return ruta


def _filas(filas):
    """Lo que leer_filas devolvería (openpyxl no calcula fórmulas: el N° de una fórmula es fila-1)."""
    return [{"fila": i, "formula": n is None, "numero": n if n is not None else i - 1, "titulo": t, "referencia": "-"}
            for i, (n, t) in enumerate(filas, start=2)]


def _pub(*pares):
    return [{"numero": n, "titulo": t, "referencia": "-"} for n, t in pares]


# ── las columnas, por su encabezado ──────────────────────────────────────────

def test_las_columnas_se_ubican_por_su_encabezado_y_no_por_su_letra():
    """El 2026-10-27 alguien insertó «Cliente» en G: con las letras fijas de antes, la ubicación iba a «Cliente»."""
    assert {k: COLUMNAS[k]["letra"] for k in ("estado", "titulo", "ubicacion", "referencia", "apertura", "cierre", "presupuesto")} == {
        "estado": "B", "titulo": "F", "ubicacion": "H", "referencia": "I", "apertura": "J", "cierre": "K", "presupuesto": "O"}
    antes = pe.columnas_de([e for e in ENCABEZADOS if e != "Cliente"])
    assert antes["ubicacion"]["letra"] == "G" and antes["referencia"]["letra"] == "H"
    assert COLUMNAS["ubicacion"]["encabezado"] == "Ubicación"


def test_eval_y_cliente_se_escriben_en_su_columna():
    """Las dos columnas que el usuario dejó en el Portal (2026-10-30), con «Cliente» donde está en la Planilla real."""
    assert (COLUMNAS["evaluador"]["letra"], COLUMNAS["cliente"]["letra"]) == ("E", "G")
    valores, _, borrar, encabezados = pe._celdas({"evaluador": "CM", "cliente": "Colegio de prueba", "ubicacion": None}, COLUMNAS)
    assert valores == {"E": "CM", "G": "Colegio de prueba"} and borrar == ["H"]
    assert encabezados == {"E": "Eval.", "G": "Cliente", "H": "Ubicación"}
    assert {"evaluador", "cliente"} <= set(pe.EDITABLES) <= set(pe.ESCRIBIBLES)


def test_leer_filas_toma_la_referencia_de_su_columna(tmp_path):
    ruta = _planilla(tmp_path, [(1, "A")])
    (f,) = pe.leer_filas(ruta)
    assert (f["titulo"], f["referencia"]) == ("A", "-")


# ── plan_fijar ───────────────────────────────────────────────────────────────

def test_fija_cada_formula_con_el_n_publicado_aunque_la_tabla_se_haya_ordenado():
    # Publicado: 1 A, 2 B, 3 C. Alguien ordenó: ahora las fórmulas dicen 1 C, 2 A, 3 B.
    ops, avisos = pe.plan_fijar(_filas([(None, "C"), (None, "A"), (None, "B")]), _pub((1, "A"), (2, "B"), (3, "C")))
    assert [(o["titulo"], o["numero"]) for o in ops] == [("C", 3), ("A", 1), ("B", 2)]
    assert avisos == []


def test_las_filas_ya_fijas_no_se_tocan_y_una_nueva_queda_con_su_n():
    filas = _filas([(1, "A"), (None, "B"), (None, "Nueva")])
    ops, avisos = pe.plan_fijar(filas, _pub((1, "A"), (2, "B")))
    assert [(o["fila"], o["numero"]) for o in ops] == [(3, 2), (4, 3)]
    assert avisos == []


def test_una_fila_nueva_cuyo_n_ya_existe_no_se_renumera_sola():
    filas = _filas([(2, "A"), (None, "Repetida")])   # la fórmula de la fila 3 dice 2: el de A
    ops, avisos = pe.plan_fijar(filas, _pub((2, "A")))
    assert ops == []
    assert "Repetida" in avisos[0] and "una persona" in avisos[0]


def test_titulos_repetidos_se_reparten_en_orden():
    ops, _ = pe.plan_fijar(_filas([(None, "Mantención"), (None, "Mantención")]), _pub((7, "Mantención"), (9, "Mantención")))
    assert [o["numero"] for o in ops] == [7, 9]


# ── fila_de_mensaje ──────────────────────────────────────────────────────────

def _mensaje(numero=4, herramienta="formulador", enviado="2026-10-26T16:00:00-03:00", **req):
    r = {"numero": numero, "titulo": "Caldera gimnasio"}
    r.update(req)
    m = {"esquema": ic.ESQUEMA, "id": f"nuevo{numero:04d}{herramienta[:3]}", "tipo": pe.TIPO_NUEVO, "destino": rq.DESTINO,
         "origen": {"herramienta": herramienta, "usuario": "NB", "enviado": enviado}, "requerimiento": r,
         "fuente": {"herramienta": herramienta}}
    if herramienta == "formulador":
        m["fuente"].update({"uid": "f1e2d3c4b5a6", "codigo": f"{numero}. Caldera gimnasio"})
    else:
        m["numeroLibre"] = True
    return m


def test_fila_nueva_con_el_formato_de_las_demas():
    op = pe.fila_de_mensaje(_mensaje(captador="CM", evaluador="NB"), None, COLUMNAS, hoy=date(2026, 10, 26))
    assert op["op"] == "nueva" and op["numero"] == 4
    assert op["valores"] == {"B": "Evaluación", "C": "Otro", "D": "CM", "E": "NB", "F": "Caldera gimnasio", "I": "-"}
    assert op["fechas"] == {"J": "2026-10-26"}
    # Excel revisa que cada letra siga teniendo ese encabezado antes de escribir
    assert op["encabezados"]["I"] == "ID o Referencia" and op["encabezados"]["J"] == "Apertura"


def test_lo_del_proyecto_al_escribir_manda_y_un_id_de_licitacion_es_mercado_publico():
    formulacion = {"datos": {"titulo": "Caldera gimnasio municipal", "ubicacion": "Ciudad Ficticia", "idLicitacion": "1234-5-LE26"}}
    op = pe.fila_de_mensaje(_mensaje(), formulacion, COLUMNAS)
    assert op["valores"]["F"] == "Caldera gimnasio municipal"
    assert op["valores"]["H"] == "Ciudad Ficticia"
    assert op["valores"]["I"] == "1234-5-LE26"
    assert op["valores"]["C"] == "Mercado Público"


def test_un_titulo_que_parece_formula_va_con_apostrofo():
    assert pe.fila_de_mensaje(_mensaje(titulo="=HOLA"), None, COLUMNAS)["valores"]["F"] == "'=HOLA"


@pytest.mark.parametrize("texto, escrito", [
    ("-2+3", "'-2+3"), ("@SUMA", "'@SUMA"), ("+56", "'+56"),   # serían fórmulas
    ("10-2", "'10-2"), ("1/2", "'1/2"), ("00123", "'00123"),   # serían fecha o número
    ("-", "-"), ("12. Ciudad de prueba", "12. Ciudad de prueba"), ("1234-56-LP26", "1234-56-LP26"),   # quedan como están
])
def test_lo_que_excel_reinterpretaria_va_con_apostrofo(texto, escrito):
    assert pe._texto_celda(texto) == escrito


def test_la_fila_del_portal_lleva_su_cierre_con_hora_y_vacios_sin_escribir():
    op = pe.fila_de_mensaje(_mensaje(herramienta="portal", canal="Postventa", referencia="", cierre="2026-11-05T15:00"), None, COLUMNAS)
    assert op["fechas"]["K"] == "2026-11-05T15:00"
    assert op["valores"]["C"] == "Postventa" and op["valores"]["I"] == "-"


# ── quién manda cuando una casilla cambió en los dos lados ───────────────────

def _editar(numero, cambios, reemplaza=None, enviado="2026-10-29T12:00:00-03:00", titulo="A", id_=None):
    m = {"esquema": ic.ESQUEMA, "id": id_ or f"editar{numero:04d}{enviado[11:13]}{enviado[14:16]}{enviado[17:19]}",
         "tipo": pe.TIPO_EDITAR, "destino": rq.DESTINO,
         "origen": {"herramienta": "portal", "usuario": "LC", "enviado": enviado},
         "requerimiento": {"numero": numero, "titulo": titulo}, "cambios": cambios}
    if reemplaza is not None:
        m["reemplaza"] = reemplaza
    return m


def _hora(texto):
    return datetime.fromisoformat(texto)


def test_si_el_excel_todavia_tiene_lo_que_se_vio_se_escribe():
    m = _editar(5, {"estado": "Ofertado"}, {"estado": "Evaluación"})
    cambios, detalle = pe.ganador_editar(m, {"estado": "Evaluación"}, {}, _hora("2026-10-29T13:00:00-03:00"))
    assert cambios == {"estado": "Ofertado"} and detalle == []


def test_lo_que_ya_dice_el_excel_no_se_reescribe():
    m = _editar(5, {"estado": "Ofertado", "cierre": "2026-11-13T15:00"}, {"estado": "Evaluación"})
    cambios, _ = pe.ganador_editar(m, {"estado": "Ofertado", "cierre": "2026-11-13T15:00"}, {}, _hora("2026-10-29T13:00:00-03:00"))
    assert cambios == {}


def test_cambiada_en_los_dos_lados_manda_el_cambio_mas_reciente():
    actual = {"estado": "Descartado"}          # alguien la cambió en el Excel
    m = _editar(5, {"estado": "Ofertado"}, {"estado": "Evaluación"}, enviado="2026-10-29T12:00:00-03:00")
    # El Excel se guardó después del cambio del Portal: queda lo del Excel
    cambios, detalle = pe.ganador_editar(m, actual, {}, _hora("2026-10-29T12:30:00-03:00"))
    assert cambios == {} and "Descartado" in detalle[0] and "más reciente" in detalle[0]
    # El cambio del Portal es posterior: se escribe, y lo dice
    cambios, detalle = pe.ganador_editar(m, actual, {}, _hora("2026-10-29T11:30:00-03:00"))
    assert cambios == {"estado": "Ofertado"} and "reemplaza" in detalle[0]


def test_lo_que_escribio_el_portal_cuenta_desde_cuando_se_cambio_en_el_portal():
    """Un cambio del Portal más nuevo que otro del Portal ya escrito gana, aunque el libro se haya guardado después
    (el guardado fue el de este mismo módulo)."""
    escritas = {"5|estado": {"valor": "Descartado", "enviado": "2026-10-29T11:00:00-03:00"}}
    m = _editar(5, {"estado": "Ofertado"}, {"estado": "Evaluación"}, enviado="2026-10-29T11:05:00-03:00")
    cambios, _ = pe.ganador_editar(m, {"estado": "Descartado"}, escritas, _hora("2026-10-29T11:10:00-03:00"))
    assert cambios == {"estado": "Ofertado"}
    # Si después una persona la cambió en el Excel, vale la hora del libro
    cambios, _ = pe.ganador_editar(m, {"estado": "Adjudicado"}, escritas, _hora("2026-10-29T11:10:00-03:00"))
    assert cambios == {}


def test_las_fechas_se_comparan_hasta_el_minuto():
    m = _editar(5, {"apertura": "2026-10-21T11:20"}, {"apertura": "2026-10-21T11:20"})
    assert pe.ganador_editar(m, {"apertura": "2026-10-21T11:20"}, {}, _hora("2026-10-29T13:00:00-03:00"))[0] == {}


def test_un_monto_exportado_se_compara_como_numero():
    m = _editar(5, {"valorOfertado": 1190000}, {"valorOfertado": None})
    assert pe.ganador_editar(m, {"valorOfertado": 1190000.0}, {}, _hora("2026-11-02T13:00:00-03:00"))[0] == {}
    m = _editar(5, {"valorOfertado": 1190000}, {"valorOfertado": 900000})
    cambios, detalle = pe.ganador_editar(m, {"valorOfertado": 900000.0}, {}, _hora("2026-11-02T13:00:00-03:00"))
    assert cambios == {"valorOfertado": 1190000} and detalle == []


def test_las_celdas_de_lo_que_exporta_el_formulador():
    valores, fechas, borrar, encabezados = pe._celdas({"valorOfertado": 1190000, "cliente": "Municipalidad"}, COLUMNAS)
    assert valores == {"P": 1190000, "G": "Municipalidad"} and not fechas and not borrar
    assert encabezados == {"P": "Valor ofertado (IVA inc)", "G": "Cliente"}


def test_el_formulador_escribe_los_montos_pero_el_portal_no_los_muestra():
    assert set(pe.SOLO_FORMULADOR) <= set(pe.ESCRIBIBLES) and not set(pe.SOLO_FORMULADOR) & set(pe.EDITABLES)


def test_las_celdas_de_un_cambio():
    valores, fechas, borrar, encabezados = pe._celdas({"ubicacion": None, "cierre": "2026-11-13T15:00", "titulo": " Liceo "}, COLUMNAS)
    assert valores == {"F": "Liceo"} and fechas == {"K": "2026-11-13T15:00"} and borrar == ["H"]
    assert set(encabezados) == {"F", "H", "K"}


# ── la vuelta ────────────────────────────────────────────────────────────────

@pytest.fixture
def entorno(tmp_path, monkeypatch):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    monkeypatch.setattr(pe, "ESTADO", tmp_path / "estado.json")
    escritas = []

    def falso_escribir(ruta, operaciones, columnas=None, limite=600):
        escritas.append(operaciones)
        libro = openpyxl.load_workbook(ruta)
        hoja = libro[rq.HOJA]
        encabezados = [c.value for c in hoja[1]]
        resultados = []

        def poner(fila, o):
            for letra, esperado in (o.get("encabezados") or {}).items():
                assert hoja[f"{letra}1"].value == esperado, (letra, esperado)
            for letra, v in o["valores"].items():
                hoja[f"{letra}{fila}"] = v
            for letra, v in (o.get("fechas") or {}).items():
                hoja[f"{letra}{fila}"] = datetime.fromisoformat(v)
            for letra in o.get("borrar") or []:
                hoja[f"{letra}{fila}"] = None

        for i, o in enumerate(operaciones):
            if o["op"] == "fijar":
                hoja.cell(o["fila"], 1).value = o["numero"]
                resultados.append({"i": i, "ok": True, "fila": o["fila"]})
            elif o["op"] == "nueva":
                fila = max(r for r in range(2, hoja.max_row + 1) if hoja.cell(r, 2).value or r == 2) + 1
                # Como el Excel desde el 2026-11-06: el N° lo da la fórmula =SI(B<>"";FILA()-1;"")
                real = fila - 1
                if o.get("exigeNumero") and real != o["numero"]:
                    resultados.append({"i": i, "ok": False, "fila": fila, "detalle": f"la fórmula le daba el N° {real}"})
                    continue
                hoja.cell(fila, 1).value = real
                poner(fila, o)
                resultados.append({"i": i, "ok": True, "fila": fila, "numero": real})
            else:
                col_t = encabezados.index("Título") + 1
                filas = [r for r in range(2, hoja.max_row + 1)
                         if hoja.cell(r, 1).value == o["numero"] and hoja.cell(r, col_t).value in (o["titulo"], o.get("tituloNuevo"))]
                if len(filas) != 1:
                    resultados.append({"i": i, "ok": False, "fila": 0, "detalle": f"{len(filas)} filas"})
                    continue
                poner(filas[0], o)
                resultados.append({"i": i, "ok": True, "fila": filas[0]})
        libro.save(ruta)
        return {"estado": "ok", "detalle": "", "resultados": resultados}

    monkeypatch.setattr(pe, "escribir", falso_escribir)
    # openpyxl no calcula: el N° de una fórmula se lee como lo dejaría Excel (fila - 1)
    original = pe.leer_filas

    def leer(ruta):
        filas = original(ruta)
        for f in filas:
            if f["formula"]:
                f["numero"] = f["fila"] - 1
        return filas

    monkeypatch.setattr(pe, "leer_filas", leer)
    return raiz, escritas


def _archivados(raiz):
    return {m["id"]: m["resultado"] for m in (json.loads(p.read_text(encoding="utf-8")) for p in (raiz / "procesado").rglob("*.json"))}


def _publicados(raiz):
    return {x["numero"]: x for x in ic.leer_publicacion(raiz, "requerimientos")["datos"]["requerimientos"]}


def _hace(minutos):
    return (datetime.now().astimezone() - timedelta(minutes=minutos)).isoformat(timespec="seconds")


def test_registra_el_proyecto_nuevo_y_republica_la_planilla(tmp_path, entorno):
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A"), (2, "B"), (3, "C")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _mensaje(4))
    r = pe.vuelta(raiz, ruta)
    assert r["detalle"] == "0 N° fijados, 1 requerimiento(s) registrado(s), 0 cambiado(s)"
    assert ic.leer_buzon(raiz, destino=rq.DESTINO, tipo=pe.TIPO_NUEVO)[0] == []
    publicados = ic.leer_publicacion(raiz, "requerimientos")["datos"]["requerimientos"]
    assert [(x["numero"], x["titulo"]) for x in publicados][-1] == (4, "Caldera gimnasio")
    # La vuelta siguiente no abre Excel: nada cambió
    assert pe.vuelta(raiz, ruta)["detalle"] == "sin cambios"
    assert len(escritas) == 1


def test_un_n_que_ya_tomo_otro_no_se_escribe(tmp_path, entorno):
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A"), (2, "B")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _mensaje(2))
    r = pe.vuelta(raiz, ruta)
    assert escritas == []
    assert "ya es «B»" in r["avisos"][0]
    assert ic.leer_buzon(raiz, destino=rq.DESTINO, tipo=pe.TIPO_NUEVO)[0] == []
    assert list(_archivados(raiz).values())[0]["estado"] == "rechazado"


def test_el_del_portal_con_un_n_tomado_queda_con_el_siguiente_libre(tmp_path, entorno):
    """Dos personas agregan un requerimiento en el Portal a la vez y las dos ven el N° 3 libre."""
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A"), (2, "B")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _mensaje(3, herramienta="portal", enviado=_hace(5), titulo="Primera"))
    ic.enviar(raiz, _mensaje(3, herramienta="portal", enviado=_hace(4), titulo="Segunda", canal="Postventa"))
    r = pe.vuelta(raiz, ruta)
    assert r["detalle"].endswith("2 requerimiento(s) registrado(s), 0 cambiado(s)")
    pub = _publicados(raiz)
    assert (pub[3]["titulo"], pub[4]["titulo"], pub[4]["canal"]) == ("Primera", "Segunda", "Postventa")
    resultado = [x for x in _archivados(raiz).values() if any("N° 4" in d for d in x["detalle"])][0]
    assert resultado["estado"] == "aplicado" and any("quedó con el N° 4" in d for d in resultado["detalle"])


def test_el_n_lo_da_la_formula_y_el_del_portal_lo_acepta(tmp_path, entorno):
    """2026-11-06: la vuelta no escribe el N°, lo da la fórmula. El del Portal
    pidió el 5 (vio una lista vieja) y queda con el que da la fórmula, el 3."""
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A"), (2, "B")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _mensaje(5, herramienta="portal", enviado=_hace(5), titulo="Postventa de A", canal="Postventa",
                             referencia="1. A"))
    pe.vuelta(raiz, ruta)
    [op] = escritas[0]
    assert op["op"] == "nueva" and "A" not in op["valores"] and op["exigeNumero"] is False
    pub = _publicados(raiz)
    assert (pub[3]["titulo"], pub[3]["canal"], pub[3]["referencia"]) == ("Postventa de A", "Postventa", "1. A")
    resultado = list(_archivados(raiz).values())[0]
    assert resultado["estado"] == "aplicado" and any("le dio el N° 3" in d for d in resultado["detalle"])


def test_el_del_formulador_con_otro_n_de_la_formula_queda_rechazado(tmp_path, entorno):
    """Su carpeta y su código ya llevan el N° pedido: si la fórmula da otro, no se escribe."""
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A"), (2, "B"), (3, "C")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _mensaje(7))
    r = pe.vuelta(raiz, ruta)
    assert any("le daba el N° 4" in a for a in r["avisos"])
    assert ic.leer_buzon(raiz, destino=rq.DESTINO, tipo=pe.TIPO_NUEVO)[0] == []
    assert list(_archivados(raiz).values())[0]["estado"] == "rechazado"


def test_un_cambio_del_portal_se_escribe_en_la_fila_de_su_n(tmp_path, entorno):
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A"), (2, "B")])
    rq.publicar(raiz, ruta)
    m = _editar(2, {"estado": "Ofertado", "ubicacion": None, "cierre": "2026-11-13T15:00"},
                {"estado": "Evaluación", "ubicacion": "Valdivia", "cierre": None}, enviado=_hace(1), titulo="B")
    ic.enviar(raiz, m)
    r = pe.vuelta(raiz, ruta)
    assert r["detalle"].endswith("1 cambiado(s)")
    (op,) = escritas[0]
    assert op["op"] == "editar" and op["titulo"] == "B" and op["borrar"] == ["H"]
    pub = _publicados(raiz)
    assert (pub[2]["estado"], pub[2]["ubicacion"], pub[2]["cierre"]) == ("Ofertado", None, "2026-11-13T15:00")
    assert pub[1]["estado"] == "Evaluación"
    assert _archivados(raiz)[m["id"]]["estado"] == "aplicado"
    # Lo escrito queda anotado: decide quién manda si esa casilla vuelve a cambiar en los dos lados
    assert json.loads(pe.ESTADO.read_text(encoding="utf-8"))["escritas"]["2|estado"]["valor"] == "Ofertado"


def test_un_cambio_del_titulo_y_otro_despues_a_la_misma_fila(tmp_path, entorno):
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _editar(1, {"titulo": "A corregido"}, {"titulo": "A"}, enviado=_hace(3), titulo="A"))
    ic.enviar(raiz, _editar(1, {"canal": "Mercado Público"}, {"canal": "Otro"}, enviado=_hace(2), titulo="A corregido"))
    pe.vuelta(raiz, ruta)
    assert [o["titulo"] for o in escritas[0]] == ["A", "A corregido"]
    pub = _publicados(raiz)
    assert (pub[1]["titulo"], pub[1]["canal"]) == ("A corregido", "Mercado Público")


def test_un_cambio_a_una_fila_que_se_crea_en_la_misma_vuelta_va_junto(tmp_path, entorno):
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _mensaje(2, herramienta="portal", enviado=_hace(3), titulo="Nueva"))
    m = _editar(2, {"ubicacion": "Talca"}, {"ubicacion": None}, enviado=_hace(2), titulo="Nueva")
    ic.enviar(raiz, m)
    pe.vuelta(raiz, ruta)
    (op,) = escritas[0]
    assert op["op"] == "nueva" and op["valores"]["H"] == "Talca"
    assert _publicados(raiz)[2]["ubicacion"] == "Talca"
    assert _archivados(raiz)[m["id"]]["estado"] == "aplicado"


def test_un_cambio_a_una_fila_que_quedo_con_otro_n_la_sigue(tmp_path, entorno):
    """Dos personas tomaron el N° 2 a la vez: el cambio que veía la segunda fila no cae en la de la primera."""
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _mensaje(2, herramienta="portal", enviado=_hace(5), titulo="Primera"))
    segunda = _mensaje(2, herramienta="portal", enviado=_hace(4), titulo="Segunda")
    segunda["id"] = "nuevosegunda1"
    ic.enviar(raiz, segunda)
    ic.enviar(raiz, _editar(2, {"ubicacion": "Talca"}, {"ubicacion": None}, enviado=_hace(3), titulo="Segunda"))
    pe.vuelta(raiz, ruta)
    pub = _publicados(raiz)
    assert (pub[2]["titulo"], pub[2]["ubicacion"]) == ("Primera", None)
    assert (pub[3]["titulo"], pub[3]["ubicacion"]) == ("Segunda", "Talca")


def test_un_cambio_a_un_n_que_ahora_es_de_otro_no_se_escribe(tmp_path, entorno):
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A"), (2, "B")])
    rq.publicar(raiz, ruta)
    m = _editar(2, {"estado": "Adjudicado"}, {"estado": "Evaluación"}, enviado=_hace(2), titulo="Otra cosa")
    ic.enviar(raiz, m)
    pe.vuelta(raiz, ruta)
    assert escritas == [] and _publicados(raiz)[2]["estado"] == "Evaluación"
    resultado = _archivados(raiz)[m["id"]]
    assert resultado["estado"] == "rechazado" and "ahora es «B»" in resultado["detalle"][0]


def test_un_cambio_cuya_fila_no_llega_todavia_espera(tmp_path, entorno):
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _editar(9, {"estado": "Ofertado"}, enviado=_hace(5), titulo="Otra"))
    pe.vuelta(raiz, ruta)
    assert escritas == [] and len(ic.leer_buzon(raiz, destino=rq.DESTINO, tipo=pe.TIPO_EDITAR)[0]) == 1
    # Un día después se rechaza
    viejo = _editar(8, {"estado": "Ofertado"}, enviado=_hace(60 * 25), titulo="Otra")
    ic.enviar(raiz, viejo)
    pe.vuelta(raiz, ruta)
    assert _archivados(raiz)[viejo["id"]]["estado"] == "rechazado"


def _exportar(numero, cambios, reemplaza, titulo, enviado):
    """Lo que deja «Exportar a la Planilla» del Formulador (js/herramientas.js, mensajeEditarRequerimiento)."""
    m = _editar(numero, cambios, reemplaza, enviado=enviado, titulo=titulo, id_=f"exportar{numero:04d}")
    m["origen"]["herramienta"] = "formulador"
    m["fuente"] = {"herramienta": "formulador", "uid": "f1e2d3c4b5a6", "codigo": f"{numero}. {titulo}"}
    return m


def test_lo_que_exporta_el_formulador_queda_escrito_en_su_fila(tmp_path, entorno):
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A"), (2, "Caldera gimnasio")])
    rq.publicar(raiz, ruta)
    m = _exportar(2, {"estado": "Ofertado", "valorOfertado": 11900000, "cliente": "Municipalidad"},
                  {"estado": "Evaluación", "valorOfertado": None, "cliente": None}, "Caldera gimnasio", _hace(2))
    assert esquemas.validar_mensaje(m) == []
    ic.enviar(raiz, m)
    pe.vuelta(raiz, ruta)
    (op,) = escritas[0]
    assert op["op"] == "editar" and op["valores"] == {"B": "Ofertado", "P": 11900000, "G": "Municipalidad"}
    fila = _publicados(raiz)[2]
    assert (fila["estado"], fila["valorOfertado"], fila["cliente"]) == ("Ofertado", 11900000, "Municipalidad")
    assert _archivados(raiz)[m["id"]]["estado"] == "aplicado"
    # Exportar lo mismo otra vez no reescribe nada
    otra = _exportar(2, {"valorOfertado": 11900000}, {"valorOfertado": None}, "Caldera gimnasio", _hace(1))
    otra["id"] = "exportar0002b"
    ic.enviar(raiz, otra)
    pe.vuelta(raiz, ruta)
    assert len(escritas) == 1 and _archivados(raiz)[otra["id"]]["estado"] == "sin-cambios"


def test_lo_que_exporta_el_formulador_a_una_fila_nueva_va_con_ella(tmp_path, entorno):
    """Un proyecto sin fila: el registro (nuevo-requerimiento) y los valores que el registro no lleva, juntos."""
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _mensaje(2, enviado=_hace(3), estado="Ofertado"))
    m = _exportar(2, {"valorOfertado": 5950000}, {"valorOfertado": None}, "Caldera gimnasio", _hace(2))
    ic.enviar(raiz, m)
    pe.vuelta(raiz, ruta)
    (op,) = escritas[0]
    assert op["op"] == "nueva" and op["valores"]["B"] == "Ofertado" and op["valores"]["P"] == 5950000
    assert _archivados(raiz)[m["id"]]["estado"] == "aplicado"


def test_lo_que_exporta_el_formulador_a_un_n_que_es_de_otro_no_se_escribe(tmp_path, entorno):
    """El 2026-11-02 la planilla volvió a numerar con fórmula y se corrieron 104 N°: el título que se vio manda."""
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A"), (2, "B")])
    rq.publicar(raiz, ruta)
    m = _exportar(2, {"valorOfertado": 5950000}, {"valorOfertado": None}, "Caldera gimnasio", _hace(2))
    ic.enviar(raiz, m)
    pe.vuelta(raiz, ruta)
    assert escritas == [] and _archivados(raiz)[m["id"]]["estado"] == "rechazado"


def test_lo_que_se_cambia_en_el_excel_llega_al_portal_en_la_vuelta(tmp_path, entorno):
    """Sin nada en el buzón: si el Excel cambió, se republica sin esperar al procesador (cada 2 horas)."""
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A")])
    rq.publicar(raiz, ruta)
    assert pe.vuelta(raiz, ruta)["detalle"].startswith("N° ya fijos")
    libro = openpyxl.load_workbook(ruta)
    libro[rq.HOJA]["B2"] = "Ofertado"
    libro.save(ruta)
    st = os.stat(ruta)
    os.utime(ruta, (st.st_atime, st.st_mtime + 5))
    r = pe.vuelta(raiz, ruta)
    assert "republicada" in r["detalle"] and escritas == []
    assert _publicados(raiz)[1]["estado"] == "Ofertado"


def test_ya_no_fija_los_n_en_formula(tmp_path, entorno):
    """Decisión del usuario (2026-11-06): el N° es la fórmula del Excel y su
    columna está protegida; la vuelta no la escribe."""
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A"), (None, "B")])
    rq.publicar(raiz, ruta)
    pe.vuelta(raiz, ruta)
    assert not any(o["op"] == "fijar" for ops in escritas for o in ops)


def test_simular_no_escribe_ni_archiva(tmp_path, entorno):
    raiz, escritas = entorno
    ruta = _planilla(tmp_path, [(1, "A")])
    rq.publicar(raiz, ruta)
    ic.enviar(raiz, _editar(1, {"estado": "Ofertado"}, {"estado": "Evaluación"}, enviado=_hace(1)))
    r = pe.vuelta(raiz, ruta, simular=True)
    assert [o["op"] for o in r["operaciones"]] == ["editar"]
    assert escritas == [] and _archivados(raiz) == {}
