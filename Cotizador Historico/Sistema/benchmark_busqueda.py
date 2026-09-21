# -*- coding: utf-8 -*-
"""
benchmark_busqueda.py -- mide si el buscador encuentra lo que se le pide.

Se corre con:
    py -3.14 ".claude/skills/Cotizador_Historico/driver.py" benchmark
    py -3.14 ".claude/skills/Cotizador_Historico/driver.py" benchmark --detalle

Por que existe: el buscador anterior "funcionaba" en el sentido de que
devolvia resultados para casi cualquier cosa. Lo que no hacia era ponerlos en
orden, y eso no se nota mirando una consulta suelta -- solo aparece cuando se
mide sobre un set fijo de consultas con una respuesta esperada. Este archivo
es ese set.

COMO SE DEFINE LA RESPUESTA ESPERADA

No con una lista de nombres escrita a mano (que envejece cada vez que se
registra una compra nueva), sino con un predicado sobre la clasificacion que
la taxonomia ya le puso a cada item: familia + material + medida. Buscar
'valvula de bola de 2"' espera items con familia "Valvula de Bola" y medida
2", sean cuales sean las compras que haya hoy en el Excel. Asi el benchmark
sigue siendo valido cuando el catalogo crece.

METRICAS (las tres que pidio el usuario)

  Success@5 -- en cuantas consultas hay al menos un resultado correcto entre
               los 5 primeros. Es la que responde "¿lo encontre o no?".
  P@5       -- que fraccion de los 5 primeros son correctos. Castiga llenar
               la pantalla con parientes lejanos.
  MRR       -- 1/posicion del primer correcto. Distingue salir 1o de salir 5o.

Las tres se calculan sobre RESULTADOS AGRUPADOS POR HOJA, no sobre compras
sueltas: el catalogo real tiene la misma valvula comprada tres veces, y
contar tres veces el mismo acierto (o el mismo error) infla la metrica sin
que el buscador haya mejorado.
"""

import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import busqueda  # noqa: E402
import taxonomia  # noqa: E402

K = 5


# ---------------------------------------------------------------------------
# EL SET DE CONSULTAS
# ---------------------------------------------------------------------------
# Cada caso: (consulta, criterio, nota). El criterio es un dict con las claves
# que tienen que calzar sobre el item (familia / material / medida /
# categoria / nombre_contiene). Las que no aparecen, no se exigen.
#
# Los primeros 13 son los "casos minimos de prueba" pedidos por el usuario --
# el mismo producto escrito de todas las formas en que un comprador lo
# escribiria. Los que siguen recorren el resto del catalogo para que la
# medicion no quede sesgada a una sola familia.
CASOS = [
    # --- el caso central: una valvula de bola de 2", escrita de 7 formas ---
    ('Válvula de bola de 2"', {"familia": "Válvula de Bola", "medida": '2"'}, "forma canonica"),
    ("valvula bola 2", {"familia": "Válvula de Bola", "medida": '2"'}, "sin tildes, sin unidad"),
    ("válvula 2 pulgadas", {"familia": "Válvula de Bola", "medida": '2"'}, "unidad escrita en palabras"),
    ('bola 2"', {"familia": "Válvula de Bola", "medida": '2"'}, "sin el sustantivo principal"),
    ("válvula esférica 2 in", {"familia": "Válvula de Bola", "medida": '2"'}, "sinonimo tecnico + unidad inglesa"),
    ('válbula de vola 2"', {"familia": "Válvula de Bola", "medida": '2"'}, "dos errores de tipeo"),
    ("valvula de bola dn50", {"familia": "Válvula de Bola", "medida": '2"'}, "medida en DN"),
    ('Valvula 2" bola', {"familia": "Válvula de Bola", "medida": '2"'}, "orden de palabras alterado"),
    ('válvula acero inoxidable 2"', {"medida": '2"', "categoria": "Válvulas y Control de Flujo"}, "material que no existe en esa medida"),

    # --- medidas parecidas: no deben confundirse entre si ---
    ('valvula bola 1/2"', {"familia": "Válvula de Bola", "medida": '1/2"'}, "media pulgada"),
    ("codo bronce 1.1/4", {"familia": "Codo", "material": "Bronce", "medida": '1.1/4"'}, "fraccion mixta chilena"),
    ("codo de bronce 1 1/4", {"familia": "Codo", "material": "Bronce", "medida": '1.1/4"'}, "fraccion mixta con espacio"),
    ("codo bronce 1-1/4 pulg", {"familia": "Codo", "material": "Bronce", "medida": '1.1/4"'}, "fraccion mixta con guion"),
    ('codo bronce 1.1/2"', {"familia": "Codo", "material": "Bronce", "medida": '1.1/2"'}, "vecina de la anterior"),

    # --- codigo exacto ---
    ("DCD7781", {"nombre_contiene": "DCD7781"}, "modelo exacto"),
    ("HER3709", {"nombre_contiene": "glicerina"}, "codigo de proveedor"),

    # --- piping por material ---
    ('cañeria cobre 1/2"', {"familia": "Cañería", "material": "Cobre", "medida": '1/2"'}, "con tilde y ñ"),
    ('tuberia de cobre 1/2"', {"familia": "Cañería", "material": "Cobre", "medida": '1/2"'}, "sinonimo tuberia/caneria"),
    ("caneria cobre 1.1/2", {"familia": "Cañería", "material": "Cobre", "medida": '1.1/2"'}, "sin tildes"),
    ("copla ppr 32", {"familia": "Copla", "material": "PPR"}, "PPR en milimetros"),
    ("terminal ppr 25", {"familia": "Terminal", "material": "PPR"}, "terminal de fusion"),
    ("niple galvanizado", {"familia": "Niple", "material": "Galvanizado"}, "niple"),
    ("union americana", {"familia": "Unión"}, "nombre compuesto"),
    ("flexible", {"familia": "Flexible"}, "flexible/manguera"),
    ("manguera", {"familia": "Flexible"}, "sinonimo de flexible"),

    # --- resto del catalogo ---
    ("taladro", {"categoria": "Herramientas Eléctricas", "nombre_contiene": "aladro"}, "herramienta electrica"),
    ("guantes cabritilla", {"familia": "Guante"}, "plural + modelo"),
    ("guante", {"familia": "Guante"}, "singular"),
    ("manometro con glicerina", {"familia": "Manómetro"}, "instrumento + palabra vacia"),
    ("manómetro", {"familia": "Manómetro"}, "con tilde"),
    ("tapones para los oidos", {"familia": "Tapón Auditivo"}, "EPP que colisiona con 'tapon' de piping"),
    ("disco de corte", {"familia": "Disco de Corte"}, "consumible"),
    ("lentes de seguridad", {"familia": "Lente de Seguridad"}, "EPP"),
    ("antiparras", {"familia": "Lente de Seguridad"}, "sinonimo de lente"),
    ("soldadura de plata", {"categoria": "Soldadura y Gases", "nombre_contiene": "plata"}, "subcategoria propia"),
    ("electrodo", {"familia": "Electrodo"}, "aporte de soldadura"),
    ("teflon", {"familia": "Teflón"}, "sellado"),
    ("coquilla aislante", {"familia": "Aislante"}, "aislacion"),
    ("bomba", {"categoria": "Bombas y Equipos Hidráulicos"}, "equipo"),
    ("estanque", {"familia": "Estanque"}, "equipo"),
    ("peaje", {"familia": "Peaje"}, "gasto de operacion"),
    ("perno", {"familia": "Perno"}, "fijacion"),
    ("golilla", {"familia": "Golilla"}, "fijacion"),
    ("arandela", {"familia": "Golilla"}, "sinonimo de golilla"),
    ("abrazadera", {"familia": "Abrazadera"}, "soporte"),
    ("silicona", {"familia": "Sellante"}, "sellado"),
    ("brocha", {"familia": "Brocha"}, "pintura"),
    ("overol", {"familia": "Overol"}, "ropa de trabajo"),
]

# Consultas que NO deben encontrar nada: miden el otro lado de la moneda, que
# el buscador sepa decir "no hay". Un buscador que devuelve algo para todo es
# tan inutil como uno que no devuelve nada.
CASOS_SIN_RESULTADO = [
    "xyzzy",
    "helicoptero",
    "zzzzzzz qqqq",
    # La empresa todavia no compra ninguno. Estuvo un rato como caso "debe
    # encontrar un esmeril" hasta que medir mostro que el catalogo real no
    # tiene ni uno: una consulta cuya respuesta no existe en los datos no
    # mide al buscador, mide al que escribio el test. El sinonimo
    # amoladora/esmeril sigue en el catalogo para cuando compren el primero.
    "amoladora",
]


def relevante(item, criterio):
    """True si este item es lo que la consulta pedia."""
    if "familia" in criterio and item.get("familia") != criterio["familia"]:
        return False
    if "material" in criterio and item.get("material") != criterio["material"]:
        return False
    if "medida" in criterio and item.get("medida") != criterio["medida"]:
        return False
    if "categoria" in criterio and item.get("categoria") != criterio["categoria"]:
        return False
    if "nombre_contiene" in criterio:
        texto = ((item.get("nombre_item") or "") + " " + (item.get("descripcion") or "")).lower()
        if criterio["nombre_contiene"].lower() not in texto:
            return False
    return True


def _agrupar_por_hoja(items_ordenados):
    """Un resultado por producto, en el orden en que aparecio el primero.

    El buscador devuelve compras; lo que el usuario evalua son productos. Sin
    esto, tres compras identicas de la misma valvula ocupan tres de los cinco
    primeros lugares y la metrica dice que todo anda bien."""
    vistos = []
    claves = set()
    for item in items_ordenados:
        clave = item.get("hoja_clave") or item.get("hoja") or item.get("nombre_item")
        if clave in claves:
            continue
        claves.add(clave)
        vistos.append(item)
    return vistos


def evaluar(items_ordenados, criterio, k=K):
    """(acierto_en_k, precision_en_k, rr) para una consulta ya resuelta."""
    top = _agrupar_por_hoja(items_ordenados)[:k]
    aciertos = [relevante(it, criterio) for it in top]
    rr = 0.0
    for pos, ok in enumerate(aciertos, start=1):
        if ok:
            rr = 1.0 / pos
            break
    return (any(aciertos), sum(aciertos) / float(k), rr)


def techo_p_at_k(items, criterio, k=K):
    """El P@k maximo alcanzable para esta consulta.

    La mayoria de las consultas de este catalogo tienen UNA sola hoja
    correcta -- hay un solo producto "Valvula de Bola 2\"". Contra eso el P@5
    no puede pasar de 0,2 por mucho que el buscador acierte, asi que el
    numero crudo subestima. Se informa junto al normalizado (P@5 / techo),
    que es el que se puede leer como 'que fraccion de lo alcanzable logro'."""
    hojas = set()
    for item in items:
        if relevante(item, criterio):
            hojas.add(item.get("hoja_clave") or item.get("hoja") or item.get("nombre_item"))
    return min(len(hojas), k) / float(k)


# ---------------------------------------------------------------------------
# EL BUSCADOR ANTERIOR, PARA PODER COMPARAR
# ---------------------------------------------------------------------------

LONGITUD_MINIMA_PALABRA_SIGNIFICATIVA = 4
UMBRAL_SIMILITUD_LEGADO = 0.6


def _similitud_legado(a, b):
    """La funcion de similitud que uso este modulo hasta 2026-09-15.

    Se conserva SOLO para medir contra ella. Devuelve 1.0 en cuanto los dos
    textos comparten una palabra de 4+ caracteres, que es exactamente el
    motivo por el que no habia ranking: sobre el catalogo real, 41 compras
    empataban en 1.0 para 'valvula de bola de 2"' y el desempate lo hacia el
    orden de las filas del Excel."""
    from difflib import SequenceMatcher
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    for palabra in b.split():
        if len(palabra) >= LONGITUD_MINIMA_PALABRA_SIGNIFICATIVA and (palabra in a or a in palabra):
            return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _normalizar_legado(texto):
    import unicodedata
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def buscar_legado(items, texto):
    consulta = _normalizar_legado(texto)
    puntuadas = []
    for item in items:
        s = max(_similitud_legado(consulta, _normalizar_legado(item.get("nombre_item"))),
                _similitud_legado(consulta, _normalizar_legado(item.get("descripcion"))))
        puntuadas.append((s, item))
    puntuadas.sort(key=lambda par: -par[0])
    return [item for s, item in puntuadas if s >= UMBRAL_SIMILITUD_LEGADO]


# ---------------------------------------------------------------------------
# CORRIDA
# ---------------------------------------------------------------------------

def _resumen(filas):
    n = len(filas) or 1
    techo = sum(f["techo"] for f in filas) or 1.0
    return {
        "success": sum(f["success"] for f in filas) / n,
        "p_at_k": sum(f["p_at_k"] for f in filas) / n,
        "p_at_k_norm": sum(f["p_at_k"] for f in filas) / techo,
        "mrr": sum(f["mrr"] for f in filas) / n,
    }


def correr(items, detalle=False, salida=print):
    """Corre el set completo contra el motor nuevo y contra el anterior."""
    for item in items:
        if "hoja" not in item or not item.get("hoja"):
            clasif = taxonomia.clasificar(item.get("nombre_item"), item.get("descripcion"))
            item.update({
                "categoria": clasif["categoria"], "subcategoria": clasif["subcategoria"],
                "familia": clasif["familia"], "material": clasif["material"],
                "medida": clasif["medida"], "hoja": taxonomia.clave_hoja(clasif),
                "hoja_clave": taxonomia.clave_agrupacion(clasif),
            })

    indice = busqueda.Indice(items)

    filas_nuevo, filas_viejo = [], []
    for consulta, criterio, nota in CASOS:
        techo = techo_p_at_k(items, criterio)
        resultados, _sug = indice.buscar(consulta)
        legado = buscar_legado(items, consulta)
        ok_n, p_n, rr_n = evaluar([r["item"] for r in resultados], criterio)
        ok_v, p_v, rr_v = evaluar(legado, criterio)
        filas_nuevo.append({"q": consulta, "success": ok_n, "p_at_k": p_n, "mrr": rr_n,
                            "techo": techo, "n": len(resultados), "nota": nota})
        filas_viejo.append({"q": consulta, "success": ok_v, "p_at_k": p_v, "mrr": rr_v,
                            "techo": techo, "n": len(legado), "nota": nota})

    vacias_nuevo = sum(1 for q in CASOS_SIN_RESULTADO if not indice.buscar(q)[0])
    vacias_viejo = sum(1 for q in CASOS_SIN_RESULTADO if not buscar_legado(items, q))

    antes, despues = _resumen(filas_viejo), _resumen(filas_nuevo)

    salida("=" * 86)
    salida(f"  BENCHMARK DEL BUSCADOR - {len(CASOS)} consultas sobre {len(items)} compras reales")
    salida("=" * 86)
    salida("")
    salida("| Metrica           | Antes (difflib) | Ahora (ranking) | Mejora |")
    salida("|---|---|---|---|")
    for clave, etiqueta in (("success", f"Success@{K}"), ("p_at_k", f"P@{K}"),
                            ("p_at_k_norm", f"P@{K} normalizada"), ("mrr", "MRR")):
        a, d = antes[clave], despues[clave]
        mejora = ((d - a) / a * 100.0) if a else float("inf")
        salida(f"| {etiqueta:17} | {a:15.3f} | {d:15.3f} | {mejora:+.1f}% |")
    salida("")
    salida(f"Consultas sin resultado esperado ({len(CASOS_SIN_RESULTADO)}): "
           f"antes acerto {vacias_viejo}, ahora {vacias_nuevo}")

    if detalle:
        salida("")
        salida("| Consulta | Antes | Ahora | Resultados | Caso |")
        salida("|---|---|---|---|---|")
        for fv, fn in zip(filas_viejo, filas_nuevo):
            marca_v = "OK" if fv["success"] else "--"
            marca_n = "OK" if fn["success"] else "--"
            salida(f"| {fn['q']} | {marca_v} (rr={fv['mrr']:.2f}) | {marca_n} (rr={fn['mrr']:.2f}) "
                   f"| {fn['n']} | {fn['nota']} |")

    return {"antes": antes, "despues": despues,
            "filas_nuevo": filas_nuevo, "filas_viejo": filas_viejo,
            "vacias_nuevo": vacias_nuevo, "vacias_viejo": vacias_viejo}
