# -*- coding: utf-8 -*-
"""
dimensiones.py -- cuanto mide un producto, y QUE ES cada numero.

    Plancha policarbonato transparente 0,7 x 812 x 3660 mm
        -> espesor 0,7 mm · ancho 812 mm · largo 3660 mm

Es el MOTOR de la lectura dimensional; los datos (que esquema usa cada
familia, las equivalencias de disco y electrodo, la tabla DN) viven en
catalogo_atributos.py, y las funciones de texto que comparte con la
descripcion del producto, en atributos.py.

POR QUE HAY UN ESQUEMA POR FAMILIA

El mismo "40x2" es un perfil cuadrado de 40 mm de lado y 2 de espesor;
"2x6" es una escuadria de pino en pulgadas; "0,7 x 812 x 3660" es espesor x
ancho x largo de una plancha; "5/8-11 x 5" es un perno de 5/8" con 11 hilos
por pulgada y 5" de largo. Una sola regla generica no puede leer los cuatro:
por eso el tipo de producto se resuelve ANTES (taxonomia.clasificar) y recien
despues se eligen los roles de cada numero (ESQUEMA_POR_TIPO).

Hasta 2026-09-22 el modulo guardaba una sola medida sin rol. Con eso las tres
barras PEX del catalogo (16, 20 y 32 mm) compartian hoja -- la unica medida
que se leia era el largo de la barra, 5,8 m -- y no habia forma de filtrar
planchas por espesor.
"""
import re
from fractions import Fraction

import presentacion
import taxonomia as tx
from catalogo_atributos import (CATEGORIAS_ELECTRICAS, DISCO_PULGADA_A_MM, DN_A_PULGADA,
                                ELECTRODO_PULGADA_A_MM, ESQUEMA_POR_FAMILIA, ESQUEMA_POR_TIPO,
                                MATERIALES_SISTEMA_METRICO)


class Dim(dict):
    """Una dimension con su rol: valor en mm siempre, y ademas su escritura
    en pulgadas si el catalogo la mide en pulgadas (1.1/4")."""


def _dim(valor, unidad, confianza, texto=None):
    if unidad == "plg":
        v = Fraction(valor)
        return Dim(valor_mm=round(float(v) * 25.4, 3), unidad="plg",
                   pulgadas=tx.fraccion_a_texto(v) + '"', texto=texto or tx.fraccion_a_texto(v) + '"',
                   confianza=confianza)
    v = float(valor)
    return Dim(valor_mm=round(v, 3), unidad="mm", pulgadas=None,
               texto=texto or _mm_texto(v), confianza=confianza)


def _mm_texto(v):
    return ("%g mm" % v).replace(".", ",")


def texto_dimension(rol, d):
    """Como se muestra una dimension en pantalla (filtros, fichas).

    El rol ya no cambia la escritura -- hasta 2026-09-23 solo el largo pasaba
    a metros, y por eso un espesor de plancha se veia bien pero una extension
    electrica se ofrecia como "20000mm". La unidad la decide el tamano del
    numero, igual para todos los roles (ver presentacion.py)."""
    if d.get("pulgadas"):
        return d["pulgadas"]
    if d.get("valor_mm") is None:
        return d.get("texto")
    return presentacion.medida_texto(d["valor_mm"])


_NUM = r"(?:\d+\s*[.\-]\s*\d+\s*/\s*\d+|\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+(?:\.\d+)?)"
_UNIDAD = r'(?:"|plgs?\.?|pulgs?\.?|pulgadas?|pg\b|in\b|inch\b|mms?\b|cms?\b|mts?\b\.?|metros?\b|m\b)'
_ESCANER = re.compile(r"(?P<num>%s)(?P<u>\s*%s)?|(?P<x>[x×])|(?P<w>[a-zñ#Ø]+)|(?P<o>\S)"
                      % (_NUM, _UNIDAD), re.I)
_UNIDAD_DE = {}
for _u in ('"', "plg", "plgs", "pulg", "pulgs", "pulgada", "pulgadas", "pg", "in", "inch"):
    _UNIDAD_DE[_u] = "plg"
for _u in ("mm", "mms"):
    _UNIDAD_DE[_u] = "mm"
for _u in ("cm", "cms"):
    _UNIDAD_DE[_u] = "cm"
for _u in ("m", "mt", "mts", "metro", "metros"):
    _UNIDAD_DE[_u] = "m"

_CORTE_ADMIN = re.compile(
    r"\b(cod|codigo|codigos|c[oó]d|ref|factura|boleta|gu[ií]a|doc|documento|folio|pedido|neto|"
    r"ingreso|sku|ean|precio|descuento|lista|venta|tot|total de|impreso)\b\.?", re.I)
_LABEL = re.compile(
    r"\b(espesor|esp|largo|longitud|long|ancho|alto|altura|di[aá]metro|diam|profundidad|en)\s*[:=.]?\s*"
    r"(Ø\s*)?(%s)\s*(%s)?" % (_NUM, _UNIDAD), re.I)
_LABEL_DIAMETRO = re.compile(r"Ø\s*(%s)\s*(%s)?" % (_NUM, _UNIDAD), re.I)
_ROL_DE_LABEL = {"espesor": "espesor", "esp": "espesor", "largo": "largo", "longitud": "largo",
                 "long": "largo", "ancho": "ancho", "alto": "alto", "altura": "alto",
                 "diametro": "diametro", "diámetro": "diametro", "diam": "diametro",
                 "profundidad": "profundidad", "en": "espesor"}


_UNIDADES_PEGADAS = (r"(?:mm|cm|mts?|metros?|plgs?|pulgs?|pulgadas?|in|inch|lts?|kg|kgs|grs?|"
                     r"ml|cc|un|und|unid|pzs|psi|bar|cms|mms)")
# La excepcion del principio es la rosca metrica: "M10" es el diametro de un
# perno, no un codigo de producto (a diferencia de "NB2-40" o "SS316").
_CODIGO_LETRA_NUMERO = re.compile(r"\b(?![Mm]\d{1,2}(?!\d))[A-Za-z]{1,6}-?\d{2,}(?:[-/]\d+)*[A-Za-z]*\b")
_CODIGO_NUMERO_LETRA = re.compile(r"\b\d+(?!%s(?![a-z]))[A-Za-z]{2,}\d*\b" % _UNIDADES_PEGADAS, re.I)
# "(0,06 planchas)", "(100 un)", "(5 pcs/bag)": cantidad o nota, no medida.
# Se conserva el parentesis que trae una unidad o una etiqueta dentro
# ("(espesor 3,40 mm)").
_PARENTESIS_CANTIDAD = re.compile(
    r"\(\s*\d[\d.,/ ]*\s*(?!%s|espesor|largo|ancho|alto|diametro)[a-zñ][^)]*\)" % _UNIDADES_PEGADAS,
    re.I)

# DN50 = diametro nominal 50 mm = 2" nominales. Es la unica pasarela entre
# el metrico y las pulgadas (ver catalogo_atributos.DN_A_PULGADA).
_DN = re.compile(r"\bdn\s*(\d{1,4})\b", re.I)


def _limpiar(texto, electrico=False):
    """El texto listo para leer medidas: sin la cola administrativa, sin
    precios, sin codigos alfanumericos, sin magnitudes que no son longitud."""
    t = tx.unificar_comillas(tx.preposiciones(texto))
    m = _CORTE_ADMIN.search(t)
    if m:
        t = t[:m.start()]
    t = re.sub(r"\$\s*[\d.,]+", " ", t)
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    # "50mmx50mt": se separa la unidad de la x para que la medida siguiente
    # no quede pegada al codigo de la anterior.
    t = re.sub(r"(?<=\d)(mm|cm|mts?|m)\s*[x×]\s*(?=\d)", r"\1 x ", t, flags=re.I)
    t = re.sub(r"\(\s*[\d.,/ ]+\s*(mm|cm|\")?\s*\)", " ", t)              # (25 mm), (7/16), (04)
    # Un parentesis con un numero y una palabra que no es unidad ni etiqueta
    # es una cantidad o una nota: "(0,06 planchas)", "(100 un)", "(5 pcs/bag)".
    t = _PARENTESIS_CANTIDAD.sub(" ", t)
    t = re.sub(r"\bN\s*[°º]\s*[\d.\-]+", " ", t, flags=re.I)
    t = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b", " ", t)
    t = re.sub(r"\b\d{5,}\b", " ", t)
    # "D32x1" y "D.63" son un diametro en mm (convencion PPR y de diales)
    t = re.sub(r"\bD\s*\.?\s*(\d{2,3})(?=\s*[x×]|\b)", r"Ø\1mm", t)
    t = re.sub(r"\b\d+(?:\.\d+)?\s*%", " ", t)
    # Magnitudes que no son longitud. La "a" de los amperes solo se saca en
    # los productos electricos: fuera de ahi, "Válvula retención Bugatti 2
    # A/BR" perdia su medida de 2" porque el "2 A" se leia como amperes.
    amperes = r"a|ma|ah|" if electrico else ""
    t = re.sub(r"\b\d+(?:\.\d+)?\s*(" + amperes +
               r"v|kv|w|kw|kg|kgs|gr|grs|g|ml|cc|lt|lts|l|oz|psi|bar|hz|rpm|"
               r"db|octanos|micrones|micras|mic|un|und|uds|unidades|pzs|piezas|pza|hjs|hojas|"
               r"dias|mts2|m2|m3|pcs|pack|tpi|lm)\b", " ", t, flags=re.I)
    t = re.sub(r"kg\s*/\s*m3", " ", t, flags=re.I)
    t = re.sub(r"\b\d+\s*[°º]\s*(c|k)?\b", " ", t, flags=re.I)
    t = re.sub(r"(?<![\w.])-?\d+\s*[+-/]\s*\d+\s*(?=bar|psi|°)", " ", t, flags=re.I)
    # especificaciones con numero: no son medidas
    t = re.sub(r"\b(?:sch|sched|schedule|ced|cedula)\.?\s*-?\s*\d{1,3}s?\b", " ", t, flags=re.I)
    t = re.sub(r"\bpn\s*-?\s*\d{1,3}\b", " ", t, flags=re.I)
    t = re.sub(r"\bserie\s*\d(?:[.,]\d)?\b", " ", t, flags=re.I)
    t = re.sub(r"\b(?:g|gr|grado)\s*[.\-]?\s*[258]\b", " ", t, flags=re.I)
    t = re.sub(r"\b(?:astm\s*)?a\s*-?\s*(?:36|53|105|106|179|234|312|500|572)\b", " ", t, flags=re.I)
    t = re.sub(r"\b(?:sae|aisi|ss|sus|inox|tp)\s*-?\s*\d{3,4}[lh]?\b", " ", t, flags=re.I)
    t = re.sub(r"\b(?:2|3|4)\d\d[lh]\b", " ", t, flags=re.I)                 # 304L suelto
    t = re.sub(r"\b(?:inoxidable|inox\.?)\s+(3\d\d|4\d\d|2\d\d)\b", " inoxidable ", t, flags=re.I)
    t = re.sub(r"\be\s*-?\s*(?:6010|6011|6013|7018|7024)\b", " ", t, flags=re.I)
    t = re.sub(r"\b(?:6010|6011|6013|7018|7024)\b", " ", t)
    t = re.sub(r"\brl\s*(?:45|90)\b", " ", t, flags=re.I)
    t = re.sub(r"\b[6-8]\s*x\s*(?:7|19|37)\b(?=\s*,)", " ", t)              # construccion de cable
    t = re.sub(r"(?<![\w.])(?:22|45|60|90|135|180)\s*(?:°|º|grados?)", " ", t, flags=re.I)
    # codigos alfanumericos (SS316, A234, VFB50-A, NB2-40/42, 6204-ZZ, 2UA, 2EN1)
    t = _CODIGO_LETRA_NUMERO.sub(" ", t)
    # Un numero seguido de letras tambien suele ser un codigo ("2UA", "2EN1"),
    # salvo que esas letras sean una UNIDAD: "32mm", "08cm" y "5.8mts" son
    # medidas. Sin esta excepcion se perdia la medida de media familia.
    t = _CODIGO_NUMERO_LETRA.sub(" ", t)
    t = re.sub(r"\b\d{3,4}-[A-Za-z]{1,4}\b", " ", t)
    return t


def _componentes(texto):
    """Grupos de medidas: [[{valor, frac, unidad, texto, pos}, ...], ...].
    Un grupo son numeros unidos por 'x'; la unidad escrita al final de un
    grupo alcanza a los numeros sin unidad que la preceden."""
    grupos, actual, pendiente_x = [], [], False
    for m in _ESCANER.finditer(texto):
        if m.group("num"):
            inicio = m.start()
            previo = texto[inicio - 1] if inicio else " "
            # Un numero pegado a una letra o a otro numero es parte de un
            # codigo ("NB2-40", "A312"), no una medida. La 'x' NO cuenta: es
            # el separador de las medidas compuestas ("40x40x2").
            if (previo.isalnum() and previo not in "xX×") or previo in "/.-":
                if actual and not pendiente_x:
                    grupos.append(actual)
                    actual = []
                continue
            crudo = m.group("num")
            unidad = (m.group("u") or "").strip().lower().rstrip(".")
            valor, es_frac = tx.parsear_numero(crudo)
            if re.match(r"^0\d\s+\d+\s*/\s*\d+$", crudo.strip()):     # "04 3/4": codigo + 3/4
                valor, es_frac = tx.parsear_numero(crudo.strip().split(None, 1)[1])
            if valor is None:
                continue
            comp = {"valor": valor, "frac": es_frac, "unidad": _UNIDAD_DE.get(unidad),
                    "texto": crudo.strip(), "cero": bool(re.match(r"^0\d", crudo.strip())),
                    "pos": inicio}
            if actual and not pendiente_x:
                grupos.append(actual)
                actual = []
            actual.append(comp)
            pendiente_x = False
        elif m.group("x"):
            pendiente_x = bool(actual)
        else:
            if actual:
                grupos.append(actual)
                actual = []
            pendiente_x = False
    if actual:
        grupos.append(actual)
    # propagar la unidad hacia la izquierda dentro del grupo
    for g in grupos:
        derecha = None
        for c in reversed(g):
            if c["unidad"]:
                derecha = c["unidad"]
            elif derecha and not c["frac"]:
                if derecha == "plg" and c["valor"] > tx.MAX_PULGADAS_NOMINAL:
                    continue
                c["unidad"] = derecha
                c["heredada"] = True
        for c in g:
            if c["frac"]:
                c["unidad"] = "plg"
    return grupos


def _en_unidad(c, unidad):
    """El valor del componente leido en la unidad que decidio el esquema, no
    en la que traia. Hace falta porque la unidad se propaga dentro del grupo
    y a veces el esquema la corrige: en "20x3/4\"" (PEX) el 20 hereda la
    pulgada del 3/4 pero son milimetros."""
    return _mm({"valor": c["valor"], "unidad": unidad})


def _mm(c, defecto=None):
    """Valor en mm de un componente ya con unidad; None si no tiene."""
    u = c["unidad"] or defecto
    if u == "plg":
        return float(c["valor"]) * 25.4
    if u == "mm":
        return float(c["valor"])
    if u == "cm":
        return float(c["valor"]) * 10
    if u == "m":
        return float(c["valor"]) * 1000
    return None


def _dim_de(c, defecto=None, confianza=0.95):
    u = c["unidad"] or defecto
    if u is None:
        return None
    conf = confianza if c["unidad"] and not c.get("heredada") else confianza - 0.05
    if not c["unidad"]:
        conf = min(conf, 0.8)
    if u == "plg":
        return _dim(c["valor"], "plg", conf)
    return _dim(_mm(c, defecto), "mm", conf)


def _etiquetadas(texto):
    """Medidas que el texto nombra: 'espesor 25mm', 'Ø54mm', 'largo 500mm',
    'en 0,8mm' (el espesor de la chapa). Devuelve (dims, texto_sin_ellas)."""
    dims = {}

    def tomar(m, rol):
        valor, es_frac = tx.parsear_numero(m.group(3) if rol != "diametro_o" else m.group(1))
        if valor is None:
            return m.group(0)
        u = (m.group(4) if rol != "diametro_o" else m.group(2)) or ""
        u = _UNIDAD_DE.get(u.strip().lower().rstrip("."), None)
        if es_frac:
            u = "plg"
        if u is None:
            u = "mm"
        c = {"valor": valor, "frac": es_frac, "unidad": u}
        real = "diametro" if rol == "diametro_o" else rol
        if real == "espesor" and m.group(1).lower() == "en" and not (u == "mm" and float(valor) < 10):
            return m.group(0)
        # "Cadena eslabon largo 8mm": ahi "largo" es un adjetivo del eslabon,
        # no la etiqueta de una medida de 8 mm.
        if real == "largo" and u == "mm" and float(valor) < 20:
            return m.group(0)
        if real not in dims:
            dims[real] = _dim_de(c, confianza=1.0)
        return " "

    def por_label(m):
        rol = _ROL_DE_LABEL.get(m.group(1).lower(), None)
        if m.group(2):
            rol = "diametro"
        return tomar(m, rol) if rol else m.group(0)

    t = _LABEL.sub(por_label, texto)
    t = _LABEL_DIAMETRO.sub(lambda m: tomar(m, "diametro_o"), t)
    return dims, t


# ---------------- esquemas ----------------

def _todas(grupos):
    return [c for g in grupos for c in g]


def _largo_de(grupos, usados):
    """El largo: una medida en metros, o una en mm/cm que no puede ser una
    seccion (>= 1000 mm)."""
    candidatas = [c for c in _todas(grupos) if id(c) not in usados and c["unidad"] in ("m", "mm", "cm")
                  and (c["unidad"] == "m" or (_mm(c) or 0) >= 1000)]
    if not candidatas:
        return None
    c = max(candidatas, key=lambda x: _mm(x))
    usados.add(id(c))
    return _dim_de(c)


def esquema_lamina(grupos, dims, ctx, rol_espesor="espesor"):
    comps = [c for c in _todas(grupos) if c["unidad"] or not c["frac"]]
    comps = [c for c in comps if (_mm(c, "mm") or 0) > 0]
    if not comps:
        return dims
    if "espesor" in dims and rol_espesor == "espesor":
        resto = comps
    else:
        finas = [c for c in comps if (_mm(c, "mm") or 999) <= 60]
        if not finas:
            resto = comps
        else:
            e = finas[0] if (_mm(finas[0], "mm") == min(_mm(c, "mm") for c in comps)) else \
                min(finas, key=lambda c: _mm(c, "mm"))
            dims.setdefault(rol_espesor, _dim_de(e, "mm", 0.95 if len(comps) >= 3 else 0.85))
            resto = [c for c in comps if c is not e]
    resto = sorted(resto, key=lambda c: _mm(c, "mm"))
    if len(resto) >= 2:
        dims.setdefault("ancho", _dim_de(resto[0], "mm", 0.9))
        dims.setdefault("largo", _dim_de(resto[-1], "mm", 0.9))
    elif len(resto) == 1:
        d = _dim_de(resto[0], "mm", 0.6)
        dims.setdefault("ancho", d)
        ctx["motivos"].append("plancha con dos medidas: no se sabe si la segunda es ancho o largo")
    return dims


def esquema_perfil(grupos, dims, ctx):
    usados = set()
    largo = _largo_de(grupos, usados)
    if largo:
        dims.setdefault("largo", largo)
    seccion = [c for c in _todas(grupos) if id(c) not in usados and not c["frac"]]
    if not seccion:
        return dims
    grupo = max(([c for c in g if id(c) not in usados] for g in grupos), key=len)
    if not grupo:
        grupo = seccion[:1]
    tipo = ctx["tipo"]
    vals = [c for c in grupo]
    if tipo in ("Fierro de Construcción", "Barra"):
        dims.setdefault("diametro", _dim_de(vals[0], "mm"))
        return dims
    if tipo == "Platina" and len(vals) >= 2:
        a, b = sorted(vals[:2], key=lambda c: -_mm(c, "mm"))
        dims.setdefault("ancho", _dim_de(a, "mm"))
        dims.setdefault("espesor", _dim_de(b, "mm"))
        return dims
    if len(vals) >= 3:
        e = vals[2] if _mm(vals[2], "mm") <= min(_mm(vals[0], "mm"), _mm(vals[1], "mm")) \
            else min(vals, key=lambda c: _mm(c, "mm"))
        lados = [c for c in vals[:3] if c is not e]
        dims.setdefault("ancho", _dim_de(lados[0], "mm"))
        dims.setdefault("alto", _dim_de(lados[1], "mm"))
        dims.setdefault("espesor", _dim_de(e, "mm"))
    elif len(vals) == 2:
        a, b = vals
        if tipo == "Perfil Cuadrado" and _mm(b, "mm") <= 10:
            dims.setdefault("ancho", _dim_de(a, "mm"))
            alto = _dim_de(a, "mm", 0.8)
            dims.setdefault("alto", alto)
            dims.setdefault("espesor", _dim_de(b, "mm"))
        elif _mm(b, "mm") <= 6 and tipo not in ("Moldura",):
            dims.setdefault("ancho", _dim_de(a, "mm"))
            dims.setdefault("espesor", _dim_de(b, "mm"))
        else:
            dims.setdefault("ancho", _dim_de(a, "mm"))
            dims.setdefault("alto", _dim_de(b, "mm"))
    else:
        dims.setdefault("ancho", _dim_de(vals[0], "mm", 0.7))
    return dims


def esquema_madera(grupos, dims, ctx):
    usados = set()
    largo = _largo_de(grupos, usados)
    if largo:
        dims.setdefault("largo", largo)
    for g in grupos:
        seccion = [c for c in g if id(c) not in usados]
        if len(seccion) >= 2 and all(float(c["valor"]) <= 16 for c in seccion[:2]):
            for rol, c in zip(("ancho", "alto"), seccion[:2]):
                u = c["unidad"] if c["unidad"] == "plg" else None
                dims.setdefault(rol, _dim(c["valor"], "plg", 0.95 if u else 0.85))
            break
    return dims


def _plastico(ctx):
    return (ctx.get("material") in MATERIALES_SISTEMA_METRICO or
            ctx.get("sistema") in MATERIALES_SISTEMA_METRICO or ctx["tipo"] == "Conduit")


_TIPOS_CON_ANGULO = ("Codo", "Curva", "Tee", "Cruz")


def _es_angulo(c, ctx):
    """El 90 de "Codo PPR 90 032" son grados, no milimetros. Solo cuenta
    como angulo si el numero viene SIN unidad: "Codo PPR 90mm" si es un codo
    de 90 mm, y en "Tee PPR 90x40x90mm" el 90 hereda los mm del grupo."""
    return (ctx["tipo"] in _TIPOS_CON_ANGULO and not c["unidad"] and not c["frac"]
            and float(c["valor"]) == int(c["valor"])
            and int(c["valor"]) in tx.ANGULOS_DE_FITTING)


def _unidad_diametro(c, ctx, posicion=0):
    """Unidad de un diametro escrito sin unidad. En tuberia plastica un
    entero es el diametro exterior en mm (PEX 32, PPR 032); en metal, una
    pulgada nominal (Copla cobre 2). Un 0 a la izquierda es siempre mm."""
    # Una unidad HEREDADA del grupo se descarta en dos casos conocidos del
    # piping, donde el primer numero es el diametro y el segundo otra cosa:
    #   "20x3/4\"" (PEX): el 20 son milimetros, la pulgada es del 3/4.
    #   "1x10cms": el 1 es una pulgada, los 10 cm son el largo del niple.
    heredada_de_largo = (c.get("heredada") and c["unidad"] in ("cm", "m")
                         and float(c["valor"]) <= tx.MAX_PULGADAS_NOMINAL)
    heredada_de_rosca = (c.get("heredada") and c["unidad"] == "plg" and _plastico(ctx)
                         and posicion == 0 and float(c["valor"]) >= 12)
    if c["unidad"] and not (heredada_de_rosca or heredada_de_largo):
        # "Codo DZR PEX HE 20x3/4\"": la pulgada del 3/4 se propaga hacia el
        # 20, pero en un sistema PEX ese 20 son milimetros (el diametro del
        # tubo) y el 3/4 es la rosca. 20 pulgadas no existen en un codo.
        return c["unidad"]
    if c["frac"]:
        return "plg"
    if _es_angulo(c, ctx):
        return None
    v = float(c["valor"])
    if c.get("cero"):
        return "mm"
    if _plastico(ctx):
        if posicion > 0 and v <= 4 and v == int(v):
            return "plg"                      # la rosca de un terminal PPR 32x1
        return "mm" if v >= 12 else None
    if v == int(v) and 1 <= v <= tx.MAX_PULGADAS_NOMINAL and int(v) not in tx.ANGULOS_DE_FITTING:
        return "plg"
    return None


def esquema_tuberia(grupos, dims, ctx):
    usados = set()
    largo = _largo_de(grupos, usados)
    if largo:
        dims.setdefault("largo", largo)
    for g in grupos:
        resto = [c for c in g if id(c) not in usados]
        if not resto:
            continue
        c = resto[0]
        u = _unidad_diametro(c, ctx)
        if u is None or (u in ("mm", "cm") and (_mm(c, u) or 0) >= 1000):
            continue
        if u == "m":
            continue
        dims.setdefault("diametro", _dim(c["valor"], "plg", 0.95) if u == "plg"
                        else _dim(_mm(c, u), "mm", 0.95 if c["unidad"] else 0.85))
        usados.add(id(c))
        if len(resto) >= 2 and "espesor" not in dims:
            e = resto[1]
            if not e["frac"] and (e["unidad"] in (None, "mm")) and float(e["valor"]) < 20:
                dims["espesor"] = _dim(float(e["valor"]), "mm", 0.85)
                usados.add(id(e))
        break
    return dims


def esquema_fitting(grupos, dims, ctx):
    usados = set()
    # Los dos diametros de una reduccion no siempre vienen juntos: el
    # catalogo escribe "1 1/4x1" pero tambien "1/2 HE x 3/8 HI" y
    # "1/4' HI NPT - 1/8' HE NPT", donde las palabras del medio separan los
    # grupos. Se recorren todos los grupos en orden y se toman los primeros
    # diametros validos.
    # Los centimetros y metros ESCRITOS son el largo de la pieza, nunca su
    # diametro; los heredados del grupo ("1x10cms") pueden ser la pulgada
    # del diametro, y los resuelve _unidad_diametro.
    resto = [c for g in grupos for c in g
             if not (c["unidad"] in ("cm", "m") and not c.get("heredada"))]
    diametros = []
    for i, c in enumerate(resto):
        u = _unidad_diametro(c, ctx, posicion=i)
        if u is None or (u == "mm" and not (_plastico(ctx) or c["unidad"] == "mm")):
            continue
        if u == "mm" and float(c["valor"]) > 400:
            continue
        # "Abrazadera ... 3/4\" - 1,5 mm": junto a un diametro en pulgadas,
        # un milimetro chico es el espesor de la pieza, no otro diametro.
        if u == "mm" and float(c["valor"]) < 10 and any(x[1] == "plg" for x in diametros):
            continue
        diametros.append((c, u))
        if len(diametros) >= 3:
            break
    if diametros:
        if "diametro" in dims:
            # el diametro ya vino etiquetado ("Ø32mm", "DN50"): lo que se
            # encuentre distinto de el es la salida
            principal = dims["diametro"]["valor_mm"]
            distintos = [(c, u) for c, u in diametros
                         if abs(_en_unidad(c, u) - principal) > 0.01]
        else:
            c0, u0 = diametros[0]
            conf0 = 0.95 if c0["unidad"] or c0["frac"] else 0.85
            dims["diametro"] = _dim(c0["valor"] if u0 == "plg" else _en_unidad(c0, u0), u0, conf0)
            distintos = [(c, u) for c, u in diametros[1:]
                         if not (c["valor"] == c0["valor"] and u == u0)]
        if distintos:
            c1, u1 = distintos[0]
            rol = "diametro_derivacion" if ctx["tipo"] in ("Tee", "Cruz") else "diametro_salida"
            dims.setdefault(rol, _dim(c1["valor"] if u1 == "plg" else _en_unidad(c1, u1), u1, 0.9))
        for c, _u in diametros:
            usados.add(id(c))
    for c in _todas(grupos):
        if id(c) in usados:
            continue
        if c["unidad"] in ("cm", "m") or (c["unidad"] == "mm" and "diametro" in dims
                                         and dims["diametro"]["unidad"] == "plg"):
            v = _mm(c)
            if c["unidad"] == "mm" and v is not None and v < 10 and ctx["tipo"] == "Abrazadera":
                dims.setdefault("espesor", _dim(v, "mm", 0.8))
            elif v is not None and v >= 20:
                dims.setdefault("largo", _dim(v, "mm", 0.9))
    return dims


_ROSCA_HILOS = re.compile(r"(%s)\s*-\s*(\d{1,2})(?![\d/])" % _NUM)
_METRICA_LARGO = re.compile(r"(?<![a-z0-9])m\s?(\d{1,2}(?:\.\d{1,2})?)(?:\s*[x×]\s*(\d{1,3}(?:\.\d+)?)\s*(mm)?)?",
                            re.I)


def esquema_perno(grupos, dims, ctx):
    """Diametro y largo de un perno. El catalogo los escribe en cualquier
    orden ("5x5/8" y "5/8 x 5"): el diametro es siempre el menor."""
    m = _METRICA_LARGO.search(ctx["texto_limpio"])
    if m:
        dims.setdefault("diametro", _dim(float(m.group(1)), "mm", 1.0, "M%s" % m.group(1)))
        if m.group(2):
            dims.setdefault("largo", _dim(float(m.group(2)), "mm", 0.95))
        return dims
    comps = [c for g in grupos for c in g]
    if not comps:
        return dims
    grupo = max(grupos, key=len)
    hay_pulgada = any(c["frac"] or c["unidad"] == "plg" for c in _todas(grupos)) or \
        "diametro" in dims and dims["diametro"]["unidad"] == "plg"
    valores = []
    for c in grupo:
        if c["unidad"] in ("cm", "m"):
            continue
        u = c["unidad"] or ("plg" if hay_pulgada else "mm")
        valores.append((c, u))
    if not valores:
        return dims
    if "diametro" in dims:
        otros = [(c, u) for c, u in valores if abs(_mm(c, u) - dims["diametro"]["valor_mm"]) > 0.01]
        if otros and ctx["tipo"] != "Varilla Roscada":
            c, u = max(otros, key=lambda p: _mm(p[0], p[1]))
            dims.setdefault("largo", _dim(c["valor"], "plg", 0.9) if u == "plg" else _dim(_mm(c, u), "mm", 0.9))
        return dims
    if len(valores) >= 2 and ctx["tipo"] != "Varilla Roscada":
        (a, ua), (b, ub) = sorted(valores[:2], key=lambda p: _mm(p[0], p[1]))
        conf = 0.9 if (a["unidad"] or a["frac"]) and (b["unidad"] or b["frac"]) else 0.8
        dims.setdefault("diametro", _dim(a["valor"], "plg", conf) if ua == "plg" else _dim(_mm(a, ua), "mm", conf))
        dims.setdefault("largo", _dim(b["valor"], "plg", conf) if ub == "plg" else _dim(_mm(b, ub), "mm", conf))
    else:
        c, u = valores[0]
        dims.setdefault("diametro", _dim(c["valor"], "plg", 0.9) if u == "plg" else _dim(_mm(c, u), "mm", 0.85))
    return dims


def esquema_tuerca(grupos, dims, ctx):
    m = _METRICA_LARGO.search(ctx["texto_limpio"])
    if m:
        dims.setdefault("diametro", _dim(float(m.group(1)), "mm", 1.0, "M%s" % m.group(1)))
        return dims
    for c in _todas(grupos):
        u = c["unidad"] or ("plg" if c["frac"] else None)
        if u is None and float(c["valor"]) == int(c["valor"]) and 1 <= c["valor"] <= 4:
            u = "plg"
        if u in ("plg", "mm"):
            dims.setdefault("diametro", _dim(c["valor"], "plg", 0.95) if u == "plg" else _dim(_mm(c, u), "mm", 0.9))
            break
    return dims


_TORNILLO = re.compile(r"(?:#|\bsr)?\s*(\d{1,2})(?:\s*-\s*\d{1,2})?\s*[x×]\s*(%s)\s*(%s)?" % (_NUM, _UNIDAD), re.I)


def esquema_tornillo(grupos, dims, ctx):
    m = _TORNILLO.search(ctx["texto_crudo"])
    if m:
        calibre = int(m.group(1))
        valor, es_frac = tx.parsear_numero(m.group(2))
        if valor is not None and calibre <= 16:
            u = _UNIDAD_DE.get((m.group(3) or "").strip().lower().rstrip("."), None)
            if es_frac or (u is None and float(valor) <= 6):
                u = "plg"
            dims.setdefault("calibre", Dim(valor_mm=None, unidad=None, pulgadas=None,
                                           texto="#%d" % calibre, confianza=0.85))
            if u == "plg":
                dims.setdefault("largo", _dim(valor, "plg", 0.9))
            elif u:
                dims.setdefault("largo", _dim(_mm({"valor": valor, "unidad": u}), "mm", 0.9))
    return dims


def esquema_remache(grupos, dims, ctx):
    for g in grupos:
        if len(g) >= 2:
            a, b = g[0], g[1]
            ua = "plg" if a["frac"] or a["unidad"] == "plg" else "mm"
            ub = "plg" if b["frac"] or b["unidad"] == "plg" else "mm"
            dims.setdefault("diametro", _dim(a["valor"], ua, 0.9) if ua == "plg" else _dim(float(a["valor"]), "mm", 0.9))
            dims.setdefault("largo", _dim(b["valor"], ub, 0.9) if ub == "plg" else _dim(float(b["valor"]), "mm", 0.9))
            break
    return dims


def esquema_disco(grupos, dims, ctx):
    for g in grupos:
        c = g[0]
        v = float(c["valor"])
        if c["unidad"] == "plg" or c["frac"] or (c["unidad"] is None and v <= 14):
            d = _dim(c["valor"], "plg", 0.95 if c["unidad"] or c["frac"] else 0.8)
        elif (c["unidad"] in ("mm", None)) and 100 <= v <= 400:
            d = _dim(v, "mm", 0.95)
        else:
            continue
        clave = d["pulgadas"][:-1] if d["pulgadas"] else None
        if clave in DISCO_PULGADA_A_MM:
            d["equivalente"] = "%dmm" % DISCO_PULGADA_A_MM[clave]
        elif d["unidad"] == "mm":
            for pulg, mm in DISCO_PULGADA_A_MM.items():
                if abs(mm - v) < 1.5:
                    d["equivalente"] = pulg + '"'
        dims.setdefault("diametro", d)
        for resto in g[1:]:
            rv = _mm(resto, "mm")
            if rv is None:
                continue
            if rv <= 10 and "espesor" not in dims:
                dims["espesor"] = _dim(rv, "mm", 0.9)
            elif 15 <= rv <= 30 and "agujero" not in dims:
                dims["agujero"] = _dim(rv, "mm", 0.9)
        break
    for c in _todas(grupos):
        if c["unidad"] == "mm" and float(c["valor"]) <= 10 and "espesor" not in dims:
            dims["espesor"] = _dim(float(c["valor"]), "mm", 0.85)
    return dims


def esquema_electrodo(grupos, dims, ctx):
    for c in _todas(grupos):
        if c["frac"] or c["unidad"] == "plg":
            d = _dim(c["valor"], "plg", 0.95)
            mm = ELECTRODO_PULGADA_A_MM.get(d["pulgadas"][:-1])
            if mm:
                d["equivalente"] = ("%gmm" % mm)
            dims.setdefault("diametro", d)
            return dims
    for c in _todas(grupos):
        v = float(c["valor"])
        if (c["unidad"] in ("mm", None)) and 1.5 <= v <= 6:
            d = _dim(v, "mm", 0.9 if c["unidad"] else 0.75)
            for pulg, mm in ELECTRODO_PULGADA_A_MM.items():
                if abs(mm - v) < 0.05:
                    d["equivalente"] = pulg + '"'
            dims.setdefault("diametro", d)
            return dims
    return dims


def esquema_cinta(grupos, dims, ctx):
    usados = set()
    largo = _largo_de(grupos, usados)
    if largo:
        dims.setdefault("largo", largo)
    resto = [c for c in _todas(grupos) if id(c) not in usados]
    anchos = []
    for c in resto:
        if c["frac"] or c["unidad"] == "plg":
            anchos.append(_dim(c["valor"], "plg", 0.9))
        elif c["unidad"] == "mm":
            anchos.append(_dim(float(c["valor"]), "mm", 0.9))
        elif c["unidad"] is None and float(c["valor"]) <= 2 and float(c["valor"]) == int(c["valor"]):
            anchos.append(_dim(c["valor"], "plg", 0.75))
    if len(anchos) >= 2:
        anchos.sort(key=lambda d: d["valor_mm"])
        dims.setdefault("espesor", anchos[0])
        dims.setdefault("ancho", anchos[-1])
    elif anchos:
        dims.setdefault("ancho", anchos[0])
    return dims


def esquema_aislacion(grupos, dims, ctx):
    usados = set()
    largo = _largo_de(grupos, usados)
    if largo:
        dims.setdefault("largo", largo)
    for c in _todas(grupos):
        if id(c) in usados:
            continue
        if c["frac"] or c["unidad"] == "plg":
            dims.setdefault("diametro", _dim(c["valor"], "plg", 0.85))
        elif c["unidad"] == "mm" and "espesor" not in dims:
            dims.setdefault("espesor", _dim(float(c["valor"]), "mm", 0.75))
    return dims


def esquema_instrumento(grupos, dims, ctx):
    for c in _todas(grupos):
        if c["frac"] or c["unidad"] == "plg":
            if float(c["valor"]) <= 2:
                dims.setdefault("conexion", _dim(c["valor"], "plg", 0.9))
                break
    for c in _todas(grupos):
        if c["unidad"] in ("mm",) and "largo" not in dims and float(c["valor"]) >= 100 and \
                ctx["tipo"] in ("Termopozo", "Termómetro"):
            dims.setdefault("largo", _dim(float(c["valor"]), "mm", 0.75))
    return dims


def esquema_generico(grupos, dims, ctx):
    medida = tx.medida_principal(ctx["nombre"], ctx["descripcion"])
    if medida is not None and "medida" not in dims and not dims:
        if medida.unidad == "plg" and len(medida.componentes) == 1:
            dims["medida"] = _dim(medida.componentes[0], "plg", 0.8)
        elif medida.unidad == "mm" and len(medida.componentes) == 1:
            dims["medida"] = _dim(float(medida.componentes[0]), "mm", 0.8)
    usados = set()
    if "largo" not in dims:
        largo = _largo_de(grupos, usados)
        if largo and largo["valor_mm"] >= 1000:
            dims["largo"] = largo
    return dims


ESQUEMAS = {
    "lamina": esquema_lamina,
    "malla": lambda g, d, c: esquema_lamina(g, d, c, rol_espesor="diametro"),
    "perfil": esquema_perfil, "barra": esquema_perfil, "madera": esquema_madera,
    "tuberia": esquema_tuberia, "fitting": esquema_fitting, "perno": esquema_perno,
    "tuerca": esquema_tuerca, "tornillo": esquema_tornillo, "remache": esquema_remache,
    "disco": esquema_disco, "electrodo": esquema_electrodo, "cinta": esquema_cinta,
    "aislacion": esquema_aislacion, "instrumento": esquema_instrumento,
    "generico": esquema_generico,
}


def esquema_de(tipo, familia):
    return ESQUEMA_POR_TIPO.get(tipo) or ESQUEMA_POR_FAMILIA.get(familia) or "generico"


def dimensiones(nombre, descripcion, tipo, familia, material=None, sistema=None,
                motivos=None, categoria=""):
    """-> (dims {rol: Dim}, esquema). Lee el nombre y, si ahi no hay medidas,
    la descripcion. El esquema de la familia decide que es cada numero."""
    esquema = esquema_de(tipo, familia)
    ctx = {"tipo": tipo, "familia": familia, "material": material, "sistema": sistema,
           "motivos": motivos if motivos is not None else [], "nombre": nombre,
           "descripcion": descripcion}
    electrico = categoria in CATEGORIAS_ELECTRICAS
    for texto in _textos_con_medidas(nombre, descripcion, electrico):
        limpio = _limpiar(texto, electrico)
        dn = _DN.search(tx.texto_plano(texto))
        if dn and DN_A_PULGADA.get(int(dn.group(1))) and esquema in ("fitting", "tuberia"):
            pulgada = DN_A_PULGADA[int(dn.group(1))]
            valor, _frac = tx.parsear_numero(pulgada)
            ctx["dn"] = _dim(valor, "plg", 0.95, "DN%s" % dn.group(1))
        if esquema in ("perno", "tuerca"):
            limpio, rosca = _separar_rosca(limpio)
        else:
            rosca = None
        dims, sin_etiquetas = _etiquetadas(limpio)
        if rosca is not None:
            dims.setdefault("diametro", rosca)
        if ctx.get("dn"):
            dims.setdefault("diametro", ctx["dn"])
        grupos = _componentes(sin_etiquetas)
        ctx["texto_limpio"] = limpio
        ctx["texto_crudo"] = tx.unificar_comillas(texto)
        dims = ESQUEMAS[esquema](grupos, dims, ctx)
        if dims:
            return dims, esquema
    return {}, esquema


def _separar_rosca(texto):
    """'5/8-11' es un perno de 5/8" con 11 hilos por pulgada: el 11 no es
    otra medida."""
    m = _ROSCA_HILOS.search(texto)
    if not m:
        return texto, None
    valor, es_frac = tx.parsear_numero(m.group(1))
    if valor is None or not es_frac:
        return texto, None
    return texto[:m.start()] + " " + texto[m.end():], _dim(valor, "plg", 0.95)


def _textos_con_medidas(nombre, descripcion, electrico=False):
    """Primero el texto que tiene mas informacion dimensional: si el nombre
    trae la medida completa se usa ese; si no, la descripcion; y al final
    los dos juntos (hay items con el diametro en el nombre y el largo en la
    descripcion)."""
    salida = []
    for t in (descripcion, nombre):
        if t and t not in salida:
            salida.append(t)
    if len(salida) == 2:
        salida.append(nombre + " " + descripcion)
    # el texto con mas numeros primero
    salida.sort(key=lambda t: -len(re.findall(r"\d", _limpiar(t, electrico))))
    return salida


def _unir_presentable(partes):
    """Varias dimensiones escritas juntas. Las que estan en milimetros
    comparten unidad (ver presentacion.grupo_texto); las que el catalogo mide
    en pulgadas se quedan en pulgadas -- convertirlas seria inventar una
    precision que el proveedor no dio."""
    if all(p.get("valor_mm") is not None and not p.get("pulgadas") for p in partes):
        return presentacion.grupo_texto([p["valor_mm"] for p in partes])
    piezas = []
    for p in partes:
        if p.get("pulgadas"):
            piezas.append(p["pulgadas"])
        elif p.get("valor_mm") is not None:
            piezas.append(presentacion.medida_texto(p["valor_mm"]))
        elif p.get("texto"):
            piezas.append(p["texto"])
    return " x ".join(piezas) or None


def medida_hoja(dims, esquema, legado, presentable=False):
    """La medida con que se arma la HOJA (la unidad de comparacion de
    precios). Depende del esquema: una plancha se compara por su formato
    completo; un fitting, por su diametro (en la escritura que ya usaba la
    taxonomia, para no mover las hojas que estaban bien).

    Con presentable=True devuelve la MISMA medida escrita para leerla (ver
    presentacion.py): "20 m" en vez de "20000mm". La eleccion de roles es la
    misma en los dos casos a proposito -- una sola funcion decide que numero
    identifica al producto, y solo cambia como se escribe."""
    def txt(d):
        if d.get("pulgadas"):
            return d["pulgadas"][:-1], '"'
        if d.get("valor_mm") is None:
            return d.get("texto"), ""
        if presentable:
            return presentacion.unidad_practica(d["valor_mm"])
        return "%g" % d["valor_mm"], "mm"

    def unir(roles):
        partes = [dims[r] for r in roles if r in dims]
        if not partes:
            return None
        if presentable:
            return _unir_presentable(partes)
        unidades = {txt(d)[1] for d in partes}
        if len(unidades) == 1:
            return "x".join(txt(d)[0] for d in partes) + unidades.pop()
        return " x ".join("".join(txt(d)) for d in partes)

    def con_largo(seccion):
        if not seccion or "largo" not in dims:
            return seccion
        largo = dims["largo"]["valor_mm"]
        if presentable:
            return "%s x %s" % (seccion, presentacion.medida_texto(largo))
        return "%s x %gm" % (seccion, largo / 1000.0)

    if esquema in ("lamina", "malla"):
        roles = ("espesor", "ancho", "largo") if esquema == "lamina" else ("diametro", "ancho", "largo")
        return unir(roles)
    if esquema in ("perfil", "barra"):
        return con_largo(unir(("ancho", "alto", "espesor")) or unir(("diametro",)))
    if esquema == "madera":
        return con_largo(unir(("ancho", "alto")))
    if esquema == "tuberia":
        return unir(("diametro",)) or legado
    if esquema == "fitting":
        return unir(("diametro", "diametro_salida", "diametro_derivacion")) or legado
    if esquema in ("perno", "remache"):
        return unir(("diametro", "largo")) or legado
    if esquema == "tornillo":
        return unir(("calibre", "largo")) or legado
    if esquema == "cinta":
        return unir(("ancho",)) or legado
    if esquema == "aislacion":
        return unir(("espesor", "diametro")) or legado
    if esquema == "barra":
        return unir(("diametro",)) or unir(("ancho", "espesor")) or legado
    if esquema in ("tuerca", "electrodo", "instrumento"):
        return unir(("diametro",)) or unir(("conexion",)) or legado
    if esquema == "disco":
        return unir(("diametro",)) or legado
    return legado


def medidas_equivalentes(dims):
    """Todas las escrituras canonicas de las dimensiones del producto, para
    el buscador: '1/2"', '32mm', y las equivalencias propias de la familia
    (un disco de 4.1/2" tambien es de 115mm)."""
    salida = []
    for d in dims.values():
        if d.get("pulgadas"):
            salida.append(d["pulgadas"])
        elif d.get("valor_mm") is not None:
            salida.append("%gmm" % d["valor_mm"])
        if d.get("equivalente"):
            salida.append(d["equivalente"])
    return salida


def numeros_de_dimensiones(dims):
    """Los numeros de las dimensiones tal como alguien los escribiria en una
    consulta: '0.7', '812', '3660' (en mm) y ademas en la unidad en que el
    catalogo los escribio ('5.8' de un largo de 5,8 m, '1/2' de media
    pulgada)."""
    salida = []
    for rol, d in dims.items():
        if d.get("valor_mm") is None:
            if d.get("texto"):
                salida.append(re.sub(r"[^0-9.]", "", d["texto"]))
            continue
        if d.get("pulgadas"):
            salida.append(d["pulgadas"][:-1])
            continue
        mm = d["valor_mm"]
        salida.append("%g" % mm)
        if rol == "largo" and mm >= 1000:
            salida.append("%g" % (mm / 1000.0))
        if d.get("equivalente"):
            salida.append(re.sub(r"[^0-9./]", "", d["equivalente"]))
    return [s for s in dict.fromkeys(salida) if s]
