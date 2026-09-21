# -*- coding: utf-8 -*-
"""
catalogo_busqueda.py -- los DATOS del buscador del Cotizador Historico: que
palabras son equivalentes entre si, que marcas se reconocen, que pesa cada
campo del item y que equivalencias de medida son tecnicamente validas.

La logica que los aplica vive en busqueda.py, igual que catalogo_taxonomia.py
es a taxonomia.py. Este es el archivo que se edita cuando una busqueda real
no encontro lo que debia.

Todo lo de aqui viaja al dashboard dentro del snapshot (ver
busqueda.config_para_snapshot): el JavaScript del visualizador NO tiene su
propia copia de estas tablas. Es la misma leccion que dejo la taxonomia en
2026-09-08 -- cuando la tabla vive duplicada en el HTML, Chile y Peru
divergen y nadie se entera.
"""

# ---------------------------------------------------------------------------
# SINONIMOS
# ---------------------------------------------------------------------------
# Cada grupo es un conjunto de escrituras equivalentes del MISMO concepto. El
# motor las canonicaliza a la primera palabra del grupo, y lo hace en los dos
# lados (consulta y documento), asi que da igual como se haya escrito la
# compra en la factura y como lo escriba quien busca.
#
# Se escriben en lenguaje natural: busqueda.py les aplica la misma
# normalizacion + raiz que usa la taxonomia (taxonomia.singular/normalizar),
# asi que no hay que calcular raices a mano ni repetir plurales.
#
# Criterio para agregar un grupo: que sean el mismo PRODUCTO, no productos
# parecidos. "codo" y "curva" no van juntos (son familias distintas de la
# taxonomia y su precio no se promedia); "bola" y "esferica" si, porque son
# dos nombres de la misma valvula.
SINONIMOS = [
    # --- piping: tipos de pieza ---
    ["bola", "esferica", "esferico"],
    ["caneria", "cañeria", "canieria", "tuberia"],
    ["niple", "neplo"],
    ["copla", "coupling"],
    ["flange", "brida"],
    ["flexible", "manguera"],
    ["union", "racord", "machon", "pomel"],
    ["reduccion", "reductor", "reductora"],
    ["bushing", "buje"],
    ["abrazadera", "clamp"],
    ["tapon", "tapagorro"],
    # --- valvulas ---
    ["valvula", "valv"],
    ["retencion", "antirretorno", "check"],
    # --- materiales (mismos canonicos que catalogo_taxonomia.MATERIALES) ---
    ["inoxidable", "inox", "ss304", "ss316", "aisi"],
    ["galvanizado", "galvanizada", "galv", "zincado"],
    ["bronce", "dzr", "laton"],
    ["cobre"],
    ["ppr"],
    ["pex", "pexa"],
    ["pvc", "vinilit"],
    ["plastico", "polipropileno", "hdpe", "nylon"],
    # --- fijaciones y consumibles ---
    ["golilla", "arandela"],
    ["tarugo", "taco"],
    ["broca", "mecha"],
    ["tornillo", "tirafondo"],
    ["disco", "muela"],
    ["teflon", "ptfe"],
    ["empaquetadura", "gasket", "oring"],
    # --- herramientas ---
    ["esmeril", "amoladora", "pulidora"],
    ["destornillador", "atornillador"],
    ["alicate", "tenaza"],
    ["taladro", "rotomartillo"],
    # --- electricos ---
    ["ampolleta", "foco", "bombilla"],
    # --- EPP ---
    ["lente", "antiparra", "gafa"],
    # --- equipos ---
    ["bomba", "electrobomba"],
    ["estanque", "tanque"],
]


# ---------------------------------------------------------------------------
# EQUIVALENCIAS DN <-> PULGADA
# ---------------------------------------------------------------------------
# Diametro nominal ISO -> pulgada nominal. Es la unica conversion entre el
# mundo metrico y el de pulgadas que el buscador acepta, y es a proposito:
# es una tabla normalizada y cerrada, no una regla aritmetica.
#
# NO se convierte mm <-> pulgada dividiendo por 25,4. Un tubo PPR de 50mm es
# un diametro EXTERIOR real y equivale a DN40 (1.1/2"), no a los 1,97" que
# daria la division. Confundirlos mezclaria en una misma hoja productos de
# calibre distinto, que es justo lo que la taxonomia evita.
# Por eso "50mm" solo encuentra items de 50mm, y solo "DN50" escrito asi
# trae ademas los de 2".
DN_A_PULGADA = {
    6: "1/4",
    8: "5/16",
    10: "3/8",
    15: "1/2",
    20: "3/4",
    25: "1",
    32: "1.1/4",
    40: "1.1/2",
    50: "2",
    65: "2.1/2",
    80: "3",
    90: "3.1/2",
    100: "4",
    125: "5",
    150: "6",
    200: "8",
    250: "10",
    300: "12",
}


# Medidas nominales en pulgadas que el buscador siempre sabe escribir, este o
# no ese calibre comprado hoy. Sin esto, buscar 7/16" cuando todavia nadie
# compro uno no reconoceria siquiera que el texto trae una medida, y los
# resultados saldrian ordenados como si la consulta no la tuviera.
#
# Se generan en vez de escribirse a mano: son ~90 y una lista escrita a dedo
# se equivoca callada (falta un calibre y esa consulta deja de entender su
# propia medida). Los denominadores son los mismos que acepta la taxonomia.
def _pulgadas_nominales():
    fracciones = []
    for denominador in (2, 4, 8, 16):
        for numerador in range(1, denominador):
            if numerador * 2 % 2 == 0 and denominador > 2 and numerador % 2 == 0:
                continue                       # 2/4 ya esta como 1/2
            fracciones.append("%d/%d" % (numerador, denominador))
    enteros = [str(n) for n in range(1, 25)]
    mixtas = ["%d.%s" % (entero, frac)
              for entero in range(1, 13)
              for frac in ("1/8", "1/4", "3/8", "1/2", "5/8", "3/4", "7/8")]
    return list(dict.fromkeys(fracciones + enteros + mixtas))


PULGADAS_NOMINALES = _pulgadas_nominales()

# Sufijos con que el catalogo chileno escribe una pulgada. El primero es el
# canonico; el resto son las escrituras que hay que reconocer al leer una
# consulta. Se validan una por una contra taxonomia.parsear_medidas en
# tests/test_busqueda_medidas.py -- si alguien agrega aqui un sufijo que el
# parser no entiende, ese test falla.
SUFIJOS_PULGADA = ['"', "''", "”", "“", " plg", " plgs", " pulg",
                   " pulgs", " pulgada", " pulgadas", " pg", " in", " inch"]

# Prefijos de diametro que pueden venir pegados al numero.
PREFIJOS_DIAMETRO = ["Ø", "⌀", "∅", "d.", "diam ", "diametro "]


# ---------------------------------------------------------------------------
# MARCAS
# ---------------------------------------------------------------------------
# Lista CERRADA y curada, leida del catalogo real. Es deliberadamente una
# lista y no una heuristica: la version anterior ("la primera palabra
# capitalizada que no sea preposicion", extraerMarcaModelo en template.html)
# etiquetaba como marca cualquier palabra que abriera una frase, y producia
# chips como "Precio" o "Cod". Una marca mal detectada no es solo un chip
# feo: es un filtro que promete agrupar y agrupa cualquier cosa.
#
# El match es por palabra completa sobre el texto normalizado, asi que
# agregar una marca aqui no puede "pescar" substrings de otras palabras.
MARCAS = [
    # sanitario / calefaccion
    "Anwo", "Bugatti", "Enolgas", "Bossini", "DAB", "Tupy", "Beta", "Ivar",
    "Nibco", "Aqualine", "Nexxo", "Eurokono", "Aiscom", "Tempres", "Honeywell",
    "Vinilit", "Alimat",
    # herramientas
    "Bauker", "Uyustools", "Truper", "Tolsen", "Stanley", "Dewalt", "Bosch",
    "Makita", "Karcher", "Einhell", "Irwin", "Bahco", "Gedore", "Rothenberger",
    "Virax", "Redline",
    # quimicos / consumibles
    "Sika", "Fischer", "Loctite", "Krafft", "Temflex", "Activex", "Indura",
    "Soldexa", "Lincoln", "Sherwin", "Solutech",
]


# ---------------------------------------------------------------------------
# PESOS POR CAMPO
# ---------------------------------------------------------------------------
# Cuanto vale que un termino de la consulta aparezca en cada campo del item.
# Pedido explicito del usuario: "mayor peso para nombre, medida, categoria y
# codigo del item". La medida no esta aca porque no se puntua como termino
# sino como multiplicador (ver MULT_MEDIDA_*): una medida distinta no es un
# match mas debil, es otro producto.
#
# "hoja" es el nombre canonico que la taxonomia le puso al producto
# (familia + material + medida, ej. "Valvula de Bola de Bronce 1.1/2\"").
# Pesa casi como el nombre porque es justamente el nombre bien escrito: por
# eso una compra cuyo Nombre Item es solo "Valvula" aparece igual al buscar
# "valvula de bola".
PESOS_CAMPO = {
    "cod": 12.0,    # N Ref. y codigos de proveedor: si calza, es EL item
    "nom": 10.0,    # Nombre Item
    "hoja": 9.0,    # nombre canonico de la taxonomia (familia+material+medida)
    "mat": 6.0,     # material
    "mar": 6.0,     # marca
    "cat": 5.0,     # categoria + subcategoria
    "desc": 4.0,    # descripcion (texto libre de la factura)
    "prov": 2.0,    # proveedor
    "proy": 2.0,    # proyecto
}

# Calidad del match de un termino, segun como haya calzado.
CALIDAD_EXACTA = 1.0
CALIDAD_PREFIJO = 0.85   # "valv" encuentra "valvula"
CALIDAD_DIFUSA = 0.6     # "valbula" encuentra "valvula" (1 error de tipeo)

# Tolerancia a errores de tipeo, por largo del termino. Mismo criterio que
# usan los motores de busqueda serios (fuzziness AUTO): en una palabra corta
# un error la convierte en otra palabra distinta, en una larga casi nunca.
# Medido sobre los casos reales del usuario: "vola"(4) -> "bola" necesita 1,
# "valbula"(7) -> "valvula" necesita 1, y 2 errores solo se perdonan desde 7
# caracteres para que "cono"/"codo"/"copa" no se confundan entre si.
MAX_ERRORES_POR_LARGO = ((0, 3, 0), (4, 6, 1), (7, 99, 2))

# Cuanto se descuenta por calzar dentro de un campo largo (ver
# busqueda._norma_largo). 0,12 deja un nombre de 8 palabras en la mitad del
# peso de uno de una sola -- suficiente para desempatar, suave para no
# esconder los Nombre Item sin simplificar que tiene este catalogo.
FACTOR_NORMA_LARGO = 0.12

# Multiplicadores de medida. Una medida distinta NO se oculta (regla de oro
# del modulo: ningun item se oculta), se hunde: el usuario que busca 2"
# igual puede ver que existe la de 1/2" si baja, pero nunca antes que la que
# pidio.
MULT_MEDIDA_EXACTA = 1.6
MULT_MEDIDA_DISTINTA = 0.18
MULT_MEDIDA_AUSENTE = 0.55   # el item no declara medida: ni premio ni castigo fuerte

# Cuanto pesa cubrir TODOS los terminos de la consulta frente a cubrir uno
# solo. Con esto, "valvula bola 2" pone primero las que son de bola Y de 2",
# no las 41 que solo dicen "valvula".
PISO_COBERTURA = 0.35

# Corte dinamico: se descarta lo que puntue menos que esta fraccion del mejor
# resultado. Un umbral absoluto solo no sirve -- una consulta especifica y
# una generica puntuan en rangos distintos.
FRACCION_DEL_MEJOR = 0.32
UMBRAL_ABSOLUTO = 0.05
UMBRAL_SUGERENCIA = 0.02
MAX_SUGERENCIAS = 6
