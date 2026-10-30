# -*- coding: utf-8 -*-
"""Lector de la Planilla de Ingreso y sugerencias que se cierran solas.

Siempre sobre una planilla armada en tmp_path: nunca la real."""
import json
from datetime import datetime

import openpyxl
import pytest

import esquemas
import intercambio as ic
import requerimientos as rq

ENCABEZADOS = ["N°", "Estado", "Canal", "Capt.", "Eval.", "Título", "Ubicación", "ID o Referencia", "Apertura",
               "Cierre", "Visita", "Visitador", "Presupuesto (IVA inc.)", "Valor ofertado (IVA inc)",
               "Valor adjudicado (IVA inc)", "Entrega (días)", "Plazo Oferta (días)"]


def _planilla(tmp_path, filas, encabezados=ENCABEZADOS):
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = rq.HOJA
    hoja.append(encabezados)
    for fila in filas:
        hoja.append(fila)
    ruta = tmp_path / "Planilla.xlsx"
    libro.save(ruta)
    return ruta


def _fila(numero, estado="Ofertado", titulo="Caldera", ofertado=None, adjudicado=None, ubicacion="Valdivia"):
    return [numero, estado, "Mercado Público", "JB", "CM", titulo, ubicacion, "123-45-LE26",
            datetime(2026, 9, 1), datetime(2026, 9, 15, 15, 30), None, None, 1000000, ofertado, adjudicado, 30, 0]


def test_lee_por_nombre_de_columna_y_limpia_valores(tmp_path):
    ruta = _planilla(tmp_path, [_fila(280, ofertado=3510500, ubicacion="#VALUE!"), [None, "Descartado"], _fila("281")])
    reqs = rq.leer_planilla(ruta)
    assert [r["numero"] for r in reqs] == [280, 281]
    r = reqs[0]
    assert r["ubicacion"] is None                    # error de fórmula = vacío
    assert r["apertura"] == "2026-09-01"             # fecha sin hora
    assert r["cierre"] == "2026-09-15T15:30"         # con hora
    assert r["valorOfertado"] == 3510500 and r["valorAdjudicado"] is None
    assert r["referencia"] == "123-45-LE26"


def test_cliente_se_publica_si_la_planilla_tiene_la_columna(tmp_path):
    con_cliente = ENCABEZADOS[:6] + ["Cliente"] + ENCABEZADOS[6:]
    fila = _fila(7)
    ruta = _planilla(tmp_path, [fila[:6] + ["Colegio de prueba"] + fila[6:]], encabezados=con_cliente)
    (r,) = rq.leer_planilla(ruta)
    assert r["cliente"] == "Colegio de prueba" and r["ubicacion"] == "Valdivia"


def test_columnas_en_otro_orden_no_corren_nada(tmp_path):
    orden = list(reversed(ENCABEZADOS))
    ruta = _planilla(tmp_path, [list(reversed(_fila(7, titulo="Horno")))], encabezados=orden)
    (r,) = rq.leer_planilla(ruta)
    assert r["numero"] == 7 and r["titulo"] == "Horno" and r["estado"] == "Ofertado"


def test_numero_repetido_se_avisa(tmp_path):
    ruta = _planilla(tmp_path, [_fila(5, titulo="Primera"), _fila(5, titulo="Segunda")])
    avisos = []
    (r,) = rq.leer_planilla(ruta, avisos)
    assert r["titulo"] == "Primera" and "N° 5" in avisos[0]
    assert "fila 3 «Segunda»" in avisos[0]          # el Portal lo muestra: esa fila solo se ve en el Excel


def test_una_fila_con_datos_y_sin_numero_se_avisa(tmp_path):
    """El 2026-10-29 había dos así al fondo de la tabla: no llegaban a ninguna herramienta y nadie lo veía."""
    ruta = _planilla(tmp_path, [_fila(5), [None, "Descartado", None, None, None, "Sin número"], [None, None]])
    avisos = []
    assert [r["numero"] for r in rq.leer_planilla(ruta, avisos)] == [5]
    assert len(avisos) == 1 and "fila 3 «Sin número»" in avisos[0]


def test_sin_columna_numero_es_error_claro(tmp_path):
    ruta = _planilla(tmp_path, [["x"]], encabezados=["Estado"])
    with pytest.raises(ValueError, match="N°"):
        rq.leer_planilla(ruta)


def test_resumen_y_tasa_de_adjudicacion(tmp_path):
    reqs = [{"numero": i, "estado": e} for i, e in enumerate(["Adjudicado", "No adjudicado", "No adjudicado", "Descartado", "Adjudicado"], 1)]
    res = rq.resumen(reqs)
    assert res["porEstado"]["Adjudicado"] == 2 and res["tasaAdjudicacion"] == 0.5
    assert rq.resumen([{"numero": 1, "estado": "Ofertado"}])["tasaAdjudicacion"] is None


def test_publicar_cumple_su_esquema(tmp_path):
    ruta = _planilla(tmp_path, [_fila(280)])
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    rq.publicar(raiz, ruta)
    sobre = ic.leer_publicacion(raiz, "requerimientos")
    assert esquemas.validar_publicacion("requerimientos", sobre) == []
    assert sobre["datos"]["requerimientos"][0]["numero"] == 280


# ── sugerencias ──────────────────────────────────────────────────────────────

def _sugerencia(numero=280, cambios=None, reemplaza=None, id_="sug00001"):
    m = {"esquema": ic.ESQUEMA, "id": id_, "tipo": rq.TIPO_SUGERENCIA, "destino": rq.DESTINO,
         "origen": {"herramienta": "formulador", "enviado": "2026-10-01T10:00:00-03:00"},
         "requerimiento": {"numero": numero}, "cambios": cambios or {"estado": "Adjudicado", "valorAdjudicado": 3000000},
         "fuente": {"herramienta": "formulador", "codigo": "QPN-2026-001"}}
    if reemplaza is not None:
        m["reemplaza"] = reemplaza
    return m


def test_sugerencia_pendiente_dice_que_escribir():
    d = rq.decidir_sugerencia(_sugerencia(), {"numero": 280, "estado": "Ofertado", "valorAdjudicado": None})
    assert d["accion"] == "pendiente"
    assert d["falta"] == {"estado": "Adjudicado", "valorAdjudicado": 3000000}
    assert any("Valor adjudicado" in x and "$3.000.000" in x for x in d["detalle"])


def test_sugerencia_ya_en_la_planilla_queda_aplicada():
    d = rq.decidir_sugerencia(_sugerencia(), {"numero": 280, "estado": "adjudicado ", "valorAdjudicado": 3000000.0})
    assert d["accion"] == "aplicado"


def test_sugerencia_en_conflicto_si_la_planilla_cambio_despues():
    m = _sugerencia(cambios={"valorOfertado": 3500000}, reemplaza={"valorOfertado": None})
    d = rq.decidir_sugerencia(m, {"numero": 280, "estado": "Ofertado", "valorOfertado": 3400000})
    assert d["accion"] == "conflicto"


def test_sugerencia_invalida_se_rechaza():
    m = _sugerencia(cambios={"estado": "Ganado"})
    assert rq.decidir_sugerencia(m, None)["accion"] == "rechazado"


def test_revisar_archiva_solo_aplicadas_y_rechazadas(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    ic.enviar(raiz, _sugerencia(id_="aplicada1"))
    ic.enviar(raiz, _sugerencia(numero=281, id_="pendiente1"))
    malo = _sugerencia(id_="rechazada1")
    malo["cambios"] = {"estado": "Ganado"}
    (raiz / "buzon" / "x_rechazada1.json").write_text(json.dumps(malo), encoding="utf-8")
    reqs = [{"numero": 280, "estado": "Adjudicado", "valorAdjudicado": 3000000},
            {"numero": 281, "estado": "Ofertado", "valorAdjudicado": None}]
    decisiones = {d["mensaje"]["id"]: d["accion"] for d in rq.revisar_sugerencias(raiz, reqs)}
    assert decisiones == {"aplicada1": "aplicado", "pendiente1": "pendiente", "rechazada1": "rechazado"}
    quedan = [m["id"] for m in ic.leer_buzon(raiz)[0]]
    assert quedan == ["pendiente1"]
    assert set(ic.resultados_recientes(raiz)) == {"aplicada1", "rechazada1"}


def test_descartar_sugerencia(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    ic.enviar(raiz, _sugerencia(id_="descartar1"))
    assert rq.descartar_sugerencia(raiz, "descartar1")
    assert not rq.descartar_sugerencia(raiz, "descartar1")
    assert ic.resultados_recientes(raiz)["descartar1"]["estado"] == "descartado"


def test_una_sugerencia_superada_por_otra_mas_nueva_se_archiva_reemplazada(tmp_path):
    """Misma regla que «Pasar a la Planilla» del Formulador: la más nueva por columna (2026-10-19)."""
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    vieja = _sugerencia(cambios={"estado": "Adjudicado", "valorAdjudicado": 1000}, id_="vieja0001")
    nueva = _sugerencia(cambios={"estado": "Adjudicado", "valorAdjudicado": 2000}, id_="nueva0001")
    nueva["origen"]["enviado"] = "2026-10-02T10:00:00-03:00"
    parcial = _sugerencia(cambios={"estado": "Ofertado", "valorOfertado": 900}, id_="parcial01")
    parcial["origen"]["enviado"] = "2026-09-30T10:00:00-03:00"   # su valorOfertado no lo pide nadie después
    otro_n = _sugerencia(numero=281, id_="otro00001")
    for m in (vieja, nueva, parcial, otro_n):
        ic.enviar(raiz, m)
    reqs = [{"numero": 280, "estado": "Evaluación"}, {"numero": 281, "estado": "Ofertado"}]
    decisiones = {d["mensaje"]["id"]: d["accion"] for d in rq.revisar_sugerencias(raiz, reqs)}
    assert decisiones["vieja0001"] == "reemplazado"
    assert decisiones["nueva0001"] == "pendiente" and decisiones["parcial01"] == "pendiente"
    assert decisiones["otro00001"] == "pendiente"
    assert ic.resultados_recientes(raiz)["vieja0001"]["estado"] == "reemplazado"
    assert "vieja0001" not in [m["id"] for m in ic.leer_buzon(raiz)[0]]


# ── la planilla ordenada (N° = FILA()-1) ─────────────────────────────────────

def test_planilla_ordenada_no_se_publica_y_queda_la_anterior(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    filas = [_fila(n, titulo=f"Proyecto {n}") for n in range(280, 290)]
    rq.publicar(raiz, _planilla(tmp_path, filas))
    # Se ordena la tabla: los títulos quedan bajo otros N°.
    corridas = [[f[0]] + f[1:5] + [filas[(i + 3) % 10][5]] + f[6:] for i, f in enumerate(filas)]
    with pytest.raises(rq.PlanillaRenumerada) as error:
        rq.publicar(raiz, _planilla(tmp_path, corridas))
    assert len(error.value.movidos) == 10
    assert "cambió el N°" in str(error.value)
    publicada = ic.leer_publicacion(raiz, "requerimientos")["datos"]["requerimientos"]
    assert publicada[0]["titulo"] == "Proyecto 280"
    rq.publicar(raiz, _planilla(tmp_path, corridas), aceptar_renumeracion=True)
    assert ic.leer_publicacion(raiz, "requerimientos")["datos"]["requerimientos"][0]["titulo"] == "Proyecto 283"


def test_filas_nuevas_y_un_titulo_corregido_si_se_publican(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    filas = [_fila(n, titulo=f"Proyecto {n}") for n in range(280, 285)]
    rq.publicar(raiz, _planilla(tmp_path, filas))
    filas[1][5] = "Proyecto 281 (corregido)"
    filas += [_fila(285, titulo="Nuevo"), _fila(286, titulo="Otro nuevo")]
    rq.publicar(raiz, _planilla(tmp_path, filas))
    assert len(ic.leer_publicacion(raiz, "requerimientos")["datos"]["requerimientos"]) == 7
    assert rq.renumerados([{"numero": 1, "titulo": "A"}, {"numero": 2, "titulo": "B"}],
                          [{"numero": 2, "titulo": "A"}, {"numero": 1, "titulo": "B"}]) == [(1, 2, "A"), (2, 1, "B")]


# ── «Ubicación» como dato geográfico de Excel (2026-10-29) ───────────────────

_RICO = "http://schemas.microsoft.com/office/spreadsheetml/2017/richdata"


def _con_dato_geografico(ruta, celdas):
    """Convierte cada celda {«G2»: «Valparaíso»} en un tipo de dato vinculado, como lo guarda Excel: la celda
    queda con el error #VALUE! y vm=«n», y el nombre va en xl/richData (por metadata.xml)."""
    import re
    import zipfile

    with zipfile.ZipFile(ruta) as z:
        partes = {n: z.read(n) for n in z.namelist()}
    hoja = partes["xl/worksheets/sheet1.xml"].decode("utf-8")
    rvs, bks, vms = [], [], []
    for i, (ref, nombre) in enumerate(celdas.items()):
        # Una entidad «núcleo» antes de la de la celda, como en la planilla real: el índice no es el de la celda
        rvs.append(f'<rv s="0"><v>536870912</v><v>{nombre} Province</v><v>id{i}</v><v>en-US</v><v>Map</v></rv>')
        rvs.append(f'<rv s="1"><v>#VALUE!</v><v>en-US</v><v>id{i}</v><v>536870912</v><v>{nombre}</v></rv>')
        bks.append(f'<bk><extLst><ext uri="{{3e2802c4-a4d2-4d8b-9148-e3be6c30e623}}"><xlrd:rvb i="{2 * i + 1}"/></ext></extLst></bk>')
        vms.append(f'<bk><rc t="1" v="{i}"/></bk>')
        hoja, n = re.subn(rf'<c r="{ref}"[^>]*?(/>|>.*?</c>)', f'<c r="{ref}" t="e" vm="{i + 1}"><v>#VALUE!</v></c>', hoja)
        assert n == 1, ref
    partes["xl/worksheets/sheet1.xml"] = hoja.encode("utf-8")
    partes["xl/richData/rdrichvaluestructure.xml"] = (
        f'<rvStructures xmlns="{_RICO}" count="2"><s t="_linkedentity2"><k n="%EntityServiceId"/><k n="_DisplayString"/>'
        '<k n="%EntityId"/><k n="%EntityCulture"/><k n="_Icon"/></s><s t="_linkedentity2core"><k n="_CRID"/>'
        '<k n="%EntityCulture"/><k n="%EntityId"/><k n="%EntityServiceId"/><k n="_DisplayString"/></s></rvStructures>').encode()
    partes["xl/richData/rdrichvalue.xml"] = f'<rvData xmlns="{_RICO}" count="{len(rvs)}">{"".join(rvs)}</rvData>'.encode()
    partes["xl/metadata.xml"] = (
        f'<metadata xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:xlrd="{_RICO}">'
        '<metadataTypes count="1"><metadataType name="XLRICHVALUE"/></metadataTypes>'
        f'<futureMetadata name="XLRICHVALUE" count="{len(bks)}">{"".join(bks)}</futureMetadata>'
        f'<valueMetadata count="{len(vms)}">{"".join(vms)}</valueMetadata></metadata>').encode()
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        for n, datos in partes.items():
            z.writestr(n, datos)


def test_la_ubicacion_como_dato_geografico_se_lee_por_su_nombre(tmp_path):
    """En la planilla real 256 de 323 ubicaciones son datos geográficos: openpyxl solo ve #VALUE!."""
    ruta = _planilla(tmp_path, [_fila(1, ubicacion="x"), _fila(2, ubicacion="Talca"), _fila(3, ubicacion="x")])
    _con_dato_geografico(ruta, {"G2": "Valparaíso", "G4": "Viña del Mar"})
    assert rq.entidades_vinculadas(ruta) == {(2, 7): "Valparaíso", (4, 7): "Viña del Mar"}
    assert [r["ubicacion"] for r in rq.leer_planilla(ruta)] == ["Valparaíso", "Talca", "Viña del Mar"]


def test_sin_datos_vinculados_no_cambia_nada(tmp_path):
    ruta = _planilla(tmp_path, [_fila(1, ubicacion="#VALUE!")])
    assert rq.entidades_vinculadas(ruta) == {}
    assert rq.leer_planilla(ruta)[0]["ubicacion"] is None
