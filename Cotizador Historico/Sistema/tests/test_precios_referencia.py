# -*- coding: utf-8 -*-
"""Precios de referencia para el Formulador: agrupación por hoja, nada de
proveedores ni de documentos en lo publicado, y que el buscador del
navegador funcione sobre las hojas publicadas."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import precios_referencia as pr

intercambio = pr.intercambio

RAIZ_MODULO = Path(__file__).resolve().parents[2]
RUTA_JS = RAIZ_MODULO / "Visualizador Web" / "busqueda.js"


def _compra(n_ref, fecha, precio, hoja="Guante cuero", clave="guante cuero", proveedor="Sodimac",
            cotizable=True, desc="guant cuero factura n 149187224 sodimac", **extra):
    c = {
        "n_ref": n_ref, "fecha": fecha, "precio_reajustado_hoy": precio, "precio_reajustado_hoy_con_iva": round(precio * 1.19),
        "hoja": hoja, "hoja_clave": clave, "categoria": "Seguridad Industrial (EPP)", "subcategoria": "Guantes",
        "familia": "Guante", "material": "Cuero", "medida": None, "cotizable": cotizable, "secundaria": False,
        "proveedor_tag": proveedor, "proyecto": "Junji's Valparaiso",
        "_bt": {"cod": f"{n_ref.lower().replace('-', '')} {n_ref.split('-')[0].lower()}", "tipo": "guant",
                "nom": "guant", "hoja": "guant cuero", "mat": "cuer", "desc": desc,
                "prov": proveedor.lower(), "proy": "junj valparais", "cat": "segur industrial epp guant"},
        "_bm": [],
    }
    c.update(extra)
    return c


SNAPSHOT = {
    "generado": "01-10-2026 08:42", "uf_hoy": 41065.38, "uf_fecha": "01-10-2026 08:42", "uf_fuente": "mindicador.cl",
    "busqueda": {"campos": ["tipo", "nom", "hoja", "mat", "desc", "cat"], "pesos_campo": {"tipo": 11, "nom": 10, "hoja": 9, "mat": 8, "desc": 3.5, "cat": 5}},
    "items": [
        _compra("JUNJ-014", "2026-08-21", 13504),
        _compra("JUNJ-079", "2026-07-29", 5000, proveedor="Ferretería Punta Arenas"),
        _compra("FCH2-020", "2026-05-01", 2000, hoja="Peaje", clave="peaje", cotizable=False, desc="peaje ruta 68"),
    ],
}


def test_una_hoja_por_producto_cotizable_con_su_ultimo_precio():
    d = pr.datos_desde_snapshot(SNAPSHOT)
    (hoja,) = d["hojas"]
    assert hoja["nombre"] == "Guante cuero" and hoja["n"] == 2
    assert hoja["precio"] == {"promedio": 9252, "minimo": 5000, "maximo": 13504, "ultimo": 13504}
    assert hoja["ultimaCompra"] == "2026-08-21"
    assert d["uf"] == {"valor": 41065.38, "fecha": "2026-10-01T08:42", "fuente": "mindicador.cl"}


def test_no_viajan_proveedores_proyectos_ni_documentos():
    (hoja,) = pr.datos_desde_snapshot(SNAPSHOT)["hojas"]
    assert set(hoja["_bt"]) == {"tipo", "nom", "hoja", "mat", "desc", "cat"}   # sin prov, proy ni cod
    texto = json.dumps(hoja, ensure_ascii=False)
    assert "sodimac" not in texto.lower()                     # nombre de tienda en la descripción
    assert "149187224" not in texto                           # número de factura
    assert "junj014" not in texto and "fch2020" not in texto  # N° Ref
    assert "industrial" in hoja["_bt"]["cat"]                 # palabra de proveedor que también es de producto


def test_publicar_y_saber_si_esta_al_dia(tmp_path):
    raiz = intercambio.asegurar_carpeta(tmp_path / "Intercambio")
    foto = tmp_path / "cotizador-historico.json"
    foto.write_text(json.dumps(SNAPSHOT), encoding="utf-8")
    assert not pr.publicacion_al_dia(raiz, foto)
    r = pr.publicar(raiz, foto)
    assert r["hojas"] == 1
    assert pr.publicacion_al_dia(raiz, foto)
    otra = dict(SNAPSHOT, generado="02-10-2026 08:00")
    foto.write_text(json.dumps(otra), encoding="utf-8")
    assert not pr.publicacion_al_dia(raiz, foto)


def test_sin_foto_del_tablero_lo_dice(tmp_path):
    raiz = intercambio.asegurar_carpeta(tmp_path / "Intercambio")
    with pytest.raises(FileNotFoundError):
        pr.publicar(raiz, tmp_path / "no-existe.json")


@pytest.mark.skipif(shutil.which("node") is None, reason="node no está instalado")
def test_el_buscador_del_navegador_encuentra_las_hojas_publicadas(tmp_path):
    """El Formulador busca con busqueda.js sobre las hojas (no sobre las
    compras): las hojas tienen que traer _bt/_bm con la misma forma."""
    d = pr.datos_desde_snapshot(SNAPSHOT)
    script = tmp_path / "buscar.js"
    script.write_text(
        "const fs = require('fs'); require(process.argv[2]);\n"
        "const d = JSON.parse(fs.readFileSync(0, 'utf8'));\n"
        "const b = globalThis.CHBusqueda.crear(d.hojas, Object.assign({vacias: [], sinonimos: {}, alias_medida: {},"
        " calidad: {exacta: 1, prefijo: 0.8, tipeo: 0.6}, max_errores: [[4, 1], [7, 2]], piso_cobertura: 0.5,"
        " factor_norma_largo: 0.1, fraccion_del_mejor: 0.3, umbral_absoluto: 0.1, medida: {}}, d.busqueda));\n"
        "const r = b.buscar('guante de cuero');\n"
        "process.stdout.write(JSON.stringify((r.resultados || r).map((x) => (x.item || d.hojas[x.idx] || x).nombre)));\n",
        encoding="utf-8")
    proc = subprocess.run(["node", str(script), str(RUTA_JS)], input=json.dumps(d).encode("utf-8"),
                          capture_output=True)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert "Guante cuero" in proc.stdout.decode("utf-8")


def test_copia_del_formulador_es_textual():
    copia = RAIZ_MODULO.parents[1] / "Formulación de proyectos" / "quempin-formulacion" / "js" / "busqueda.js"
    if not copia.exists():
        pytest.skip("el Formulador no está en esta máquina (o todavía no lleva la copia)")
    assert copia.read_bytes() == RUTA_JS.read_bytes(), (
        "vuelve a copiar Cotizador Historico/Visualizador Web/busqueda.js al Formulador")
