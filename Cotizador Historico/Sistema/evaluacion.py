# -*- coding: utf-8 -*-
"""
evaluacion.py -- mide la clasificacion y el buscador con criterios que NO
dependen del sistema que se esta midiendo.

    py -3.14 ".claude/skills/Cotizador_Historico/driver.py" evaluacion [--detalle]

Complementa a benchmark_busqueda.py, que juzga cada resultado con la
clasificacion que el propio sistema le puso al item (familia + material +
medida). Eso sirve para comparar dos buscadores sobre la MISMA taxonomia,
pero no puede ver un error de la taxonomia: si tres barras PEX de 16, 20 y
32 mm comparten hoja, el benchmark las cuenta como "el mismo producto" y da
el acierto por bueno. Aca:

- la relevancia de cada consulta es un predicado sobre el TEXTO CRUDO del
  producto (nombre + descripcion), escrito mirando el catalogo;
- los atributos se comparan contra referencia_atributos.REFERENCIA,
  etiquetada a mano;
- los resultados se agrupan por el texto del producto (dos compras del mismo
  producto cuentan una vez), no por la hoja de ninguna version.

Asi el mismo archivo se puede correr contra el motor anterior (importando
sus modulos desde otra carpeta) y contra el actual, y los numeros son
comparables. Ver el pie de este archivo.

METRICAS
  P@1        el primer resultado es correcto
  P@5        fraccion de correctos entre los 5 primeros productos
  P@5 norm   P@5 / el maximo alcanzable (hay consultas con 1 solo correcto)
  Success@5  hay al menos un correcto entre los 5 primeros
  MRR        1 / posicion del primer correcto
"""

import re
import unicodedata
from fractions import Fraction

K = 5


# ---------------------------------------------------------------------------
# NORMALIZACION DEL TEXTO CRUDO (solo para los predicados de relevancia)
# ---------------------------------------------------------------------------

def texto_normalizado(item):
    t = (str(item.get("nombre_item") or "") + " " + str(item.get("descripcion") or "")).lower()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)            # 0,7 -> 0.7
    return re.sub(r"\s+", " ", t)


_ADMIN = re.compile(r"\b(factura|boleta|doc\.? ingreso|guia|precio|neto)\b.*$")


def clave_producto(item):
    """Dos compras del mismo producto cuentan una vez en las metricas."""
    nombre = texto_normalizado({"nombre_item": item.get("nombre_item")})
    desc = _ADMIN.sub("", texto_normalizado({"descripcion": item.get("descripcion")}))
    return (nombre.strip() + "|" + desc.strip()[:70])


def P(*patrones):
    """Predicado: TODOS los patrones (regex) aparecen en el texto normalizado."""
    compilados = [re.compile(p) for p in patrones]
    return lambda t: all(c.search(t) for c in compilados)


# ---------------------------------------------------------------------------
# CONSULTAS: (consulta, predicado de relevancia, familia de producto, nota)
# ---------------------------------------------------------------------------
# Escritas contra el catalogo real: cada una tiene al menos un producto
# relevante (se verifica al correr). Las que el usuario dio como ejemplo en
# el pedido del 2026-09-22 estan marcadas "(pedido)".

CONSULTAS = [
    # --- planchas ---
    ("plancha policarbonato 0.7", P("policarbonato", r"\b0\.7\b"), "Planchas", "(pedido)"),
    ("plancha policarbonato", P("plancha|placa", "policarbonato"), "Planchas", "(pedido)"),
    ("policarbonato transparente", P("policarbonato", "transparente"), "Planchas", "(pedido)"),
    ("plancha 0.7", P("plancha", r"\b0\.7\b"), "Planchas", "(pedido)"),
    ("policarbonato 812", P("policarbonato", r"\b812\b"), "Planchas", "(pedido)"),
    ("plancha policarbonato 0.7 812", P("policarbonato", r"\b0\.7\b", r"\b812\b"), "Planchas",
     "(pedido)"),
    ("plancha galvanizada 0,8", P("plancha", "galvaniz", r"\b0\.8\b"), "Planchas", "decimal con coma"),
    ("plancha acero 2,5mm", P("plancha", "acero", r"\b2\.5\b"), "Planchas", "material + espesor"),
    ("plancha inox 1mm", P("plac|planch", "inox", r"\b1(\.0)? ?mm"), "Planchas", "abreviatura"),
    ("plancha zincalum", P("zincalum"), "Planchas", "material nuevo"),
    ("policarbonsto", P("policarbonato"), "Planchas", "(pedido) error de tipeo"),
    ("plancha laminada en frio", P("plancha", "laminada en frio"), "Planchas", "terminacion"),
    ("placa acero inoxidable", P("plac|planch", "inox"), "Planchas", "sinonimo placa/plancha"),
    ("plancha policarbonato 4mm", P("policarbonato", r"\b4 ?mm"), "Planchas", "espesor"),
    ("plancha acero carbono", P("plancha", r"a-36|1010|plancha de acero"), "Planchas",
     "material por su grado"),

    # --- perfiles ---
    ("perfil cuadrado 40x40x2", P("cuad", r"\b40 ?x ?(40 ?x ?)?2(\.0)?\b"), "Perfiles",
     "(pedido) seccion completa"),
    ("perfil rectangular 80x40", P("rectangular", r"80 ?x ?40"), "Perfiles", "seccion"),
    ("tubo cuadrado 50x3", P("cuad", r"50 ?x ?3"), "Perfiles", "tubo = perfil"),
    ("angulo 40x40x3", P("angulo", r"40 ?x ?40 ?x ?3"), "Perfiles", "perfil angulo"),
    ("platina 25x3", P("platina", r"25 ?x ?3"), "Perfiles", "platina"),
    ("pletina 50x5", P("pletina|platina", r"50 ?x ?5"), "Perfiles", "sinonimo"),
    # Un ángulo de 40x40 también es un perfil de 40x40: la consulta no dice
    # la geometría, así que cualquiera de los dos es una respuesta correcta.
    ("perfil 40x40", P(r"perfil cuadrado|tubo cuad|angulo", r"\b40 ?x"), "Perfiles",
     "seccion parcial"),
    ("riel galvanizado", P("riel"), "Perfiles", "estaba sin clasificar"),
    ("perfil inox 40x40", P(r"perfil cuadrado|tubo cuad|angulo", r"\b40 ?x"), "Perfiles",
     "(pedido) material que no existe en esa medida"),
    ("fierro construccion 8mm", P("fierro construccion", r"\b8 ?mm"), "Perfiles", "barra"),
    ("perf cuadrado 40", P(r"perfil cuadrado|tubo cuad", r"\b40"), "Perfiles", "abreviatura perf"),

    # --- cañerias y tubos ---
    ("cañeria cobre tipo L 1/2", P("cobre", r"\bl\b|tipo l", r"\b1/2\b"), "Cañerías",
     "tipo de pared"),
    ("tubo inox 316 1/4", P(r"\b316\b", r"\b1/4\b"), "Cañerías", "grado AISI"),
    ("cañeria inox 6 sch10", P("a312", "sch10"), "Cañerías", "schedule"),
    ("cañeria acero carbono 8", P("a53", r"\b8 pulgadas"), "Cañerías", "material por norma"),
    ("tuberia ppr 32", P(r"tuberia ppr|caneria ppr|ppr serie", r"\b0?32(mm|x| )"), "Cañerías",
     "PPR en mm"),
    ("pex 20", P("pex-a", r"\b20 barra"), "Cañerías", "PEX: el numero es el diametro"),
    ("tubo pvc 25mm", P("tubo pvc", r"\b25 ?mm"), "Cañerías", "diametro x largo"),
    ("cañeria negra 3/4", P("negra", "caneria", r"3/4"), "Cañerías", "acero negro"),
    ("cañeria pex 16", P("pex-a", r"\b16\b"), "Cañerías", "PEX de 16 no es el de 32"),
    ("cañeria cobre 1 1/4", P("cobre", "caneria", r"1[ .]1/4"), "Cañerías", "fraccion mixta"),

    # --- valvulas ---
    ("válvula bola 2 pulgadas inox", P("bola", r'(\b2 ?(plg|")|inox)'), "Válvulas", "(pedido)"),
    ("valvula vola 2 inox", P("bola", r'(\b2 ?(plg|")|inox)'), "Válvulas", "(pedido) tipeo"),
    ("valvula retencion inox", P("retencion", "inox"), "Válvulas", "tipo + material"),
    ("valvula bola ppr 50", P("bola", "ppr", r"\b50"), "Válvulas", "PPR"),
    ("valvula aguja 1/4", P("aguja"), "Válvulas", "tipo poco frecuente"),
    ("valvula bola dzr 3/4", P("bola", "dzr", "3/4"), "Válvulas", "laton DZR"),
    ("valvula alivio 3 bar", P("alivio", r"3 bar"), "Válvulas", "presion"),
    ("valv bola 3/4", P("bola", r"3/4"), "Válvulas", "abreviatura valv"),
    ("valvula bola laton", P("bola", "dzr"), "Válvulas", "DZR es laton"),
    ("llave de paso 3/4", P("bola", r"3/4"), "Válvulas", "nombre coloquial"),

    # --- fittings ---
    ("codo 1/2 NPT 316", P("codo", r"\b1/2\b"), "Fittings", "(pedido) no existe exacto"),
    ("tee inox 1/2", P("tee", "inox", r"\b1/2\b"), "Fittings", "tipo+material+medida"),
    ("bushing galvanizado 1 1/4 x 1", P("bushing", "galv", r"1[ .]1/4 ?\"? ?x ?1\b"), "Fittings",
     "reduccion"),
    ("copla ppr 40", P("copla", "ppr", r"\b0?40"), "Fittings", "PPR"),
    ("terminal pex 20x1/2", P("terminal", "pex", r"20x1/2"), "Fittings", "PEX + hilo"),
    ("union americana ppr 32", P("union americana", "ppr", r"\b0?32"), "Fittings", "compuesto"),
    ("flange dn50", P("flange", "dn50"), "Fittings", "DN"),
    ("brida 8 pulgadas", P("flange", r"8 pulgadas"), "Fittings", "sinonimo brida"),
    ("conector macho inox 1/4 x 1/2", P("conector macho", "inox", r"1/4 ?\"? ?x ?1/2"), "Fittings",
     "compuesta"),
    ("reduccion cobre 3/4 x 1/2", P("reduccion", "cobre"), "Fittings", "reduccion"),
    ("codo ppr 90mm", P("codo ppr", r"90 ?mm"), "Fittings", "90 es medida, no angulo"),
    ("niple bronce 1/2", P("niple", r"bronce|\bbr\b", r"\b1/2\b"), "Fittings", "abreviatura BR"),
    ("curva sch 40 3/4", P("curva", "sch40"), "Fittings", "schedule"),
    ("tee sch40 3/4", P("tee", "sch40"), "Fittings", "schedule"),
    ("hilo tuerca galvanizado 3/4", P("hilo tuerca", "galv", r"3/4"), "Fittings",
     "no es 4.3/4"),
    ("punta negra 1", P("punta", "neg", r"\b1 ?x ?10"), "Fittings", "abreviatura neg"),
    ("galv 1/2", P("galv", r"\b1/2\b"), "Fittings", "solo material + medida"),
    ("tapon inox 1/4", P("tapon", "inox"), "Fittings", "tipo+material"),
    ("cobre 3/4 x 1/2", P("cobre", r"3/4 ?x ?1/2"), "Fittings", "sin tipo"),

    # --- pernos y fijaciones ---
    ("perno hexagonal 5/8 x 5", P("perno hex", r"5x5/8|5/8-11 x 5"), "Pernos",
     "largo y diametro en cualquier orden"),
    ("perno anclaje 1/2", P("anclaje", r"\b1/2"), "Pernos", "tipo"),
    ("tuerca inoxidable 1/2", P("tuerca", "inox", r"\b1/2"), "Pernos", "material"),
    ("golilla presion 5/8", P("golilla presion", "5/8"), "Pernos", "tipo de golilla"),
    ("tuerca m8", P("tuerca", r"\bm8\b"), "Pernos", "rosca metrica"),
    ("remache pop 4.8 x 15", P("remache", r"4\.8 ?x ?15"), "Pernos", "decimales"),
    ("tornillo madera 3 pulgadas", P("tornillo madera", r"x 3\""), "Pernos", "largo"),
    ("perno g5 1/2", P("perno", "g-5", r"1/2"), "Pernos", "grado"),
    ("varilla roscada 1/2", P(r"\bhilo\b", r"1/2-13"), "Pernos", "hilo = varilla"),
    ("perno m12 x 50", P("perno", r"12x50"), "Pernos", "metrico"),
    ("golilla plana zincada 1/2", P("golilla", "plana", r"\b1/2", "zinc"), "Pernos", "acabado"),

    # --- electricos ---
    ("enchufe hembra 10a", P("enchufe hembra"), "Eléctricos", "amperaje"),
    ("adaptador schuko", P("schuko"), "Eléctricos", "no es un fitting"),
    ("cinta aisladora", P(r"cinta (aisladora|aislante|electrica)"), "Eléctricos", "sinonimos"),
    ("extension electrica 20 metros", P("extension", r"20 metros"), "Eléctricos", "largo"),
    ("conduit 16mm", P("conduit", r"16 ?mm"), "Eléctricos", "conduit"),

    # --- aislacion ---
    ("coquilla 25mm", P("coquilla", r"25 ?mm"), "Aislación", "espesor"),
    ("manta fibra ceramica 25mm", P("manta fibra"), "Aislación", "manta"),
    ("cinta aluminio 50mm", P("cinta aluminio", r"50 ?mm"), "Aislación", "ancho"),
    ("aislante 1 1/2", P("aislante", r"1 1/2"), "Aislación", "diametro"),
    ("coquilla 54", P("coquilla", r"54 ?mm"), "Aislación", "diametro interior"),

    # --- resto ---
    ("disco corte 4 1/2 inox", P("disco", "corte", r"4[ .]1/2|4\.5", "inox"), "Otros",
     "inox es para que material corta"),
    ("disco corte 115mm", P("disco", "corte", r"115|4[ .]1/2|4\.5"), "Otros",
     "115 mm = 4 1/2 en discos"),
    ("electrodo 7018 1/8", P("electrodo", "7018", r"1/8"), "Otros", "clase AWS"),
    ("electrodo 6011 3.2", P("electrodo", "6011", r"3\.2"), "Otros", "mm"),
    ("broca concreto 5mm", P("broca", "concreto", r"\b5 ?mm"), "Otros", "aplicacion"),
    ("llave cadena", P("llave cadena"), "Otros", "herramienta, no cadena"),
    ("lija fierro 120", P("lija", "120"), "Otros", "grano"),
    ("brocha 3 pulgadas", P("brocha", r"\b3 ?(\"|pulg|plg)"), "Otros", "ancho"),
    ("manometro glicerina 1/4", P("manometro", "glic", r"1/4"), "Otros", "conexion"),
    ("termometro bimetalico 1/2", P("termometro bimetalico"), "Otros", "tipo"),
    ("rodamiento 6204", P("rodamiento", "6204"), "Otros", "modelo"),
    ("pino 2x6", P("pino", r"2 ?x ?6"), "Otros", "escuadria"),
    ("pino 2x3", P("pino", r'2"? ?x ?3'), "Otros", "escuadria"),
    ("empaquetadura epdm", P("epdm"), "Otros", "material de sello"),
    ("plancha teflon", P("plancha teflon"), "Otros", "plancha de empaquetadura"),
    ("cable de acero 3/16", P("cable de acero", "3/16"), "Otros", "izaje"),
    ("ss316", P(r"ss316|\b316\b"), "Otros", "(pedido) grado"),
    ("aisi 304", P(r"\b304"), "Otros", "(pedido) grado"),
    ("codo cobre 1", P("codo", "cobre", r'\b1"'), "Otros", "entero suelto"),
    ("pvc 32", P("pvc", r"\b32"), "Otros", "material + mm"),
    ("llave stillson", P("stillson"), "Otros", "marca/modelo"),
    ("adhesivo pvc", P("adhesivo", r"pvc|vinilit"), "Otros", "aplicacion"),
    ("tubo gas mapp", P("mapp"), "Otros", "gas"),
    ("soldadura plata 15%", P("plata", "15%"), "Otros", "ley de plata"),
]


# ---------------------------------------------------------------------------
# METRICAS DE BUSQUEDA
# ---------------------------------------------------------------------------

def _productos_en_orden(items):
    vistos, salida = set(), []
    for it in items:
        clave = clave_producto(it)
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(it)
    return salida


def evaluar_busqueda(items, indice, consultas=CONSULTAS, k=K):
    """-> lista de filas {consulta, p1, p5, techo, success, rr, n}."""
    relevantes_por_consulta = {}
    for consulta, pred, _fam, _nota in consultas:
        claves = {clave_producto(it) for it in items if pred(texto_normalizado(it))}
        relevantes_por_consulta[consulta] = claves

    filas = []
    for consulta, pred, familia, nota in consultas:
        resultados, _sug = indice.buscar(consulta)
        top = _productos_en_orden([r["item"] for r in resultados])[:k]
        aciertos = [pred(texto_normalizado(it)) for it in top]
        rr = 0.0
        for pos, ok in enumerate(aciertos, start=1):
            if ok:
                rr = 1.0 / pos
                break
        n_rel = len(relevantes_por_consulta[consulta])
        filas.append({
            "consulta": consulta, "familia": familia, "nota": nota,
            "p1": 1.0 if aciertos and aciertos[0] else 0.0,
            "p5": sum(aciertos) / float(k),
            "techo": min(n_rel, k) / float(k),
            "success": 1.0 if any(aciertos) else 0.0,
            "rr": rr, "n_relevantes": n_rel, "n": len(resultados),
            "top": [it.get("nombre_item") for it in top],
        })
    return filas


def resumir_busqueda(filas):
    n = len(filas) or 1
    techo = sum(f["techo"] for f in filas) or 1.0
    return {
        "consultas": len(filas),
        "p1": sum(f["p1"] for f in filas) / n,
        "p5": sum(f["p5"] for f in filas) / n,
        "p5_norm": sum(f["p5"] for f in filas) / techo,
        "success5": sum(f["success"] for f in filas) / n,
        "mrr": sum(f["rr"] for f in filas) / n,
    }


# ---------------------------------------------------------------------------
# METRICAS DE ATRIBUTOS (contra la referencia etiquetada a mano)
# ---------------------------------------------------------------------------

# Equivalencias con las que se juzga el material, iguales para cualquier
# version del motor: el motor anterior no distinguia laton de bronce ni acero
# negro de acero al carbono, y no se le cobra esa distincion.
_EQUIVALENTES = [{"Acero carbono", "Acero negro"}, {"Bronce", "Latón"}]
_PLASTICOS = {"Nylon", "HDPE", "Polipropileno", "Plástico"}

# Nombres del motor anterior (hasta 2026-09-21) -> los actuales.
_MATERIAL_ANTERIOR = {"Inoxidable": "Acero inoxidable", "Galvanizado": "Acero galvanizado",
                      "Acero Negro": "Acero negro", "Acero": "Acero carbono"}

_DN_A_PULGADA_MM = {15: 12.7, 20: 19.05, 25: 25.4, 32: 31.75, 40: 38.1, 50: 50.8,
                    65: 63.5, 80: 76.2, 100: 101.6, 150: 152.4, 200: 203.2}


def _material_ok(esperado, obtenido):
    obtenido = _MATERIAL_ANTERIOR.get(obtenido, obtenido)
    if esperado is None:
        return obtenido is None
    if obtenido == "Plástico":
        return esperado in _PLASTICOS
    if esperado == obtenido:
        return True
    return any(esperado in g and obtenido in g for g in _EQUIVALENTES)


def valor_mm(texto):
    """'0.7mm' -> 0.7 ; '1.1/4"' -> 31.75"""
    t = str(texto).strip()
    if t.endswith("mm"):
        return float(t[:-2])
    if t.endswith('"'):
        t = t[:-1]
        m = re.match(r"^(\d+)\.(\d+)/(\d+)$", t)
        if m:
            return (int(m.group(1)) + Fraction(int(m.group(2)), int(m.group(3)))) * 25.4
        if "/" in t:
            num, den = t.split("/")
            return float(Fraction(int(num), int(den))) * 25.4
        return float(t) * 25.4
    return float(t)


def _iguales(a, b):
    if a is None or b is None:
        return False
    a, b = float(a), float(b)
    if abs(a - b) <= max(0.05, 0.01 * max(a, b)):
        return True
    # DN50 escrito en mm equivale a 2" nominal (misma regla que el buscador)
    for dn, mm in _DN_A_PULGADA_MM.items():
        if (abs(a - dn) < 0.01 and abs(b - mm) < 0.05) or (abs(b - dn) < 0.01 and abs(a - mm) < 0.05):
            return True
    return False


def valores_de_medida_legado(medida):
    """Los numeros de la medida canonica del motor anterior ('0.7x812x3660mm',
    '1.1/2x1.1/4"'), en mm. Ese motor no asignaba roles: solo una cadena."""
    if not medida:
        return []
    t = str(medida)
    if t.endswith("mm"):
        return [float(v) for v in t[:-2].split("x") if v]
    if t.endswith('"'):
        return [valor_mm(v + '"') for v in t[:-1].split("x") if v]
    return []


def evaluar_atributos(tx, referencia):
    """Material, familia, tipo y dimensiones de cada producto de referencia."""
    filas = []
    for ref in referencia:
        c = tx.clasificar(ref["nombre"], ref["descripcion"])
        dims = c.get("dimensiones")
        if dims is None:                       # motor anterior: una sola cadena
            valores = valores_de_medida_legado(c.get("medida"))
            por_rol = None
        else:
            valores = [d["valor_mm"] for d in dims.values()]
            por_rol = {rol: d["valor_mm"] for rol, d in dims.items()}

        esperados = {rol: valor_mm(v) for rol, v in ref["dims"].items()}
        valores_ok = all(any(_iguales(e, v) for v in valores) for e in esperados.values())
        roles_ok = (por_rol is not None and
                    all(_iguales(e, por_rol.get(rol)) for rol, e in esperados.items()))

        fila = {
            "nombre": ref["nombre"], "descripcion": ref["descripcion"],
            "familia_esp": ref["familia"], "familia": c.get("familia_producto"),
            "tipo_esp": ref["tipo"], "tipo": c.get("tipo"),
            "material_esp": ref["material"], "material": c.get("material"),
            "evalua_material": ref["material"] is not _SALTAR(),
            "dims_esp": ref["dims"], "dims": dims,
            "tiene_dims": bool(esperados),
            "valores_ok": valores_ok, "roles_ok": roles_ok,
            "categoria_esp": ref.get("categoria"), "categoria": c.get("categoria"),
        }
        fila["material_ok"] = (fila["evalua_material"] and
                               _material_ok(ref["material"], c.get("material")))
        filas.append(fila)
    return filas


def _SALTAR():
    import referencia_atributos
    return referencia_atributos.SALTAR


def resumir_atributos(filas):
    con_material = [f for f in filas if f["evalua_material"]]
    con_dims = [f for f in filas if f["tiene_dims"]]
    con_familia = [f for f in filas if f["familia"] is not None]
    con_categoria = [f for f in filas if f["categoria_esp"]]
    return {
        "productos": len(filas),
        "material": sum(f["material_ok"] for f in con_material) / (len(con_material) or 1),
        "dims_valores": sum(f["valores_ok"] for f in con_dims) / (len(con_dims) or 1),
        "dims_roles": sum(f["roles_ok"] for f in con_dims) / (len(con_dims) or 1),
        "familia": (sum(f["familia"] == f["familia_esp"] for f in con_familia) / len(con_familia)
                    if con_familia else None),
        "tipo": (sum(f["tipo"] == f["tipo_esp"] for f in con_familia) / len(con_familia)
                 if con_familia else None),
        "categoria": (sum(f["categoria"] == f["categoria_esp"] for f in con_categoria)
                      / (len(con_categoria) or 1)),
        "n_material": len(con_material), "n_dims": len(con_dims),
    }


# ---------------------------------------------------------------------------
# METRICAS SOBRE EL CATALOGO COMPLETO
# ---------------------------------------------------------------------------

def evaluar_catalogo(tx, items):
    """Conteos sobre todas las compras reales: lo que el sistema no sabe
    clasificar y lo que decidio por un margen minimo."""
    sin_clasificar = otros_materiales = sin_material = ambiguas = baja_confianza = 0
    cotizables = 0
    requiere_material = getattr(tx, "CATEGORIAS_CON_MATERIAL", set())
    for it in items:
        c = tx.clasificar(it.get("nombre_item"), it.get("descripcion"))
        if c["categoria"] == "Sin Clasificar":
            sin_clasificar += 1
        if c.get("subcategoria") == "Otros materiales":
            otros_materiales += 1
        if c.get("cotizable") and c["categoria"] != "Sin Clasificar":
            cotizables += 1
            if c["categoria"] in requiere_material and not c.get("material"):
                sin_material += 1
        if c.get("ambigua") if "ambigua" in c else _ambigua_legado(tx, it):
            ambiguas += 1
        conf = c.get("confianza")
        if conf is not None and conf < 0.7:
            baja_confianza += 1
    return {"compras": len(items), "sin_clasificar": sin_clasificar,
            "otros_materiales": otros_materiales, "sin_material": sin_material,
            "ambiguas": ambiguas, "baja_confianza": baja_confianza,
            "cotizables": cotizables}


def _ambigua_legado(tx, item):
    """Para el motor anterior, que no informa su margen: la misma definicion
    que usa el actual -- dos reglas de categorias distintas a menos de 10
    puntos, con la formula de puntaje de ese motor."""
    nombre = item.get("nombre_item") or ""
    desc = item.get("descripcion") or ""
    ln, ld = tx.lemas(nombre), tx.lemas(desc)
    mejores = {}
    for terminos, cat, _sub, _fam, extra in tx.REGLAS:
        for termino in terminos:
            npal = tx.n_palabras(termino)
            for lem, bono in ((ln, 30), (ld, 0)):
                for p in tx._posiciones(lem, termino):
                    if tx._negado(lem, p):
                        continue
                    s = 100 + extra + bono + 10 * npal
                    mejores[cat] = max(mejores.get(cat, 0), s)
                    break
    orden = sorted(mejores.values(), reverse=True)
    return len(orden) >= 2 and orden[0] - orden[1] < 10


# ---------------------------------------------------------------------------
# CORRIDA
# ---------------------------------------------------------------------------

def correr(tx, bq, items, referencia, detalle=False, salida=print):
    import copy
    filas_attr = evaluar_atributos(tx, referencia)
    attr = resumir_atributos(filas_attr)
    cat = evaluar_catalogo(tx, items)
    indice = bq.Indice([copy.deepcopy(it) for it in items])
    filas_bus = evaluar_busqueda(items, indice)
    bus = resumir_busqueda(filas_bus)

    salida("=" * 78)
    salida(f"  EVALUACION - {len(referencia)} productos de referencia, "
           f"{len(CONSULTAS)} consultas, {len(items)} compras")
    salida("=" * 78)
    salida(f"  Material correcto ........ {attr['material']:.3f}  (sobre {attr['n_material']})")
    salida(f"  Dimensiones (valores) .... {attr['dims_valores']:.3f}  (sobre {attr['n_dims']})")
    salida(f"  Dimensiones (con su rol) . {attr['dims_roles']:.3f}")
    if attr["familia"] is not None:
        salida(f"  Familia correcta ......... {attr['familia']:.3f}")
        salida(f"  Tipo correcto ............ {attr['tipo']:.3f}")
    salida(f"  Categoria correcta ....... {attr['categoria']:.3f}")
    salida(f"  Busqueda P@1 ............. {bus['p1']:.3f}")
    salida(f"  Busqueda P@5 ............. {bus['p5']:.3f}   (normalizada {bus['p5_norm']:.3f})")
    salida(f"  Busqueda Success@5 ....... {bus['success5']:.3f}")
    salida(f"  Busqueda MRR ............. {bus['mrr']:.3f}")
    salida(f"  Catalogo: sin clasificar {cat['sin_clasificar']}, 'Otros materiales' "
           f"{cat['otros_materiales']}, sin material donde define {cat['sin_material']}, "
           f"ambiguas {cat['ambiguas']}, baja confianza {cat['baja_confianza']}")
    if detalle:
        salida("\n-- consultas que fallan el primer lugar --")
        for f in filas_bus:
            if f["p1"] < 1:
                salida(f"  [{f['success']:.0f}] {f['consulta']!r:38} rel={f['n_relevantes']:2d} "
                       f"top={f['top'][:3]}")
        salida("\n-- referencia con errores --")
        for f in filas_attr:
            errores = []
            if f["evalua_material"] and not f["material_ok"]:
                errores.append(f"material {f['material']!r} (esp {f['material_esp']!r})")
            if f["tiene_dims"] and not f["valores_ok"]:
                errores.append(f"dims {f['dims']} (esp {f['dims_esp']})")
            elif f["tiene_dims"] and f["dims"] is not None and not f["roles_ok"]:
                errores.append(f"roles {({r: d['valor_mm'] for r, d in f['dims'].items()})} "
                               f"(esp {f['dims_esp']})")
            if f["familia"] is not None and f["familia"] != f["familia_esp"]:
                errores.append(f"familia {f['familia']!r} (esp {f['familia_esp']!r})")
            if f["tipo"] is not None and f["tipo"] != f["tipo_esp"]:
                errores.append(f"tipo {f['tipo']!r} (esp {f['tipo_esp']!r})")
            if f["categoria_esp"] and f["categoria"] != f["categoria_esp"]:
                errores.append(f"categoria {f['categoria']!r} (esp {f['categoria_esp']!r})")
            if errores:
                salida(f"  {f['nombre'][:30]:30} | {f['descripcion'][:40]:40} | " + "; ".join(errores))
    return {"atributos": attr, "busqueda": bus, "catalogo": cat,
            "filas_busqueda": filas_bus, "filas_atributos": filas_attr}
