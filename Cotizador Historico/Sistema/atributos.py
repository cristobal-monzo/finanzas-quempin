# -*- coding: utf-8 -*-
"""
atributos.py -- describe un producto como un conjunto de ATRIBUTOS
independientes: de que material esta hecho, que dimensiones tiene (y que es
cada una), que especificaciones tecnicas trae y cuanta confianza hay en cada
dato. Es el MOTOR; los datos viven en catalogo_atributos.py.

    Plancha policarbonato transparente 0,7 x 812 x 3660 mm
        -> material Policarbonato, terminacion Transparente,
           espesor 0,7 mm, ancho 812 mm, largo 3660 mm

Lo usa taxonomia.clasificar despues de decidir QUE es el producto (su tipo):
el significado de "0,7 x 812 x 3660" depende de que sea una plancha, igual
que "2x6" es una escuadria de madera en pulgadas y "40x2" un perfil de 40 mm
de lado. Por eso aca no hay una lectura generica de medidas: hay esquemas por
familia (ver ESQUEMA_POR_TIPO).

Por que existe (2026-09-22): la clasificacion anterior guardaba una sola
"medida" sin rol y un material elegido por la primera palabra que calzara.
Con eso una plancha de policarbonato no tenia material (el policarbonato era
una palabra que llevaba a "Plancha", dentro de "Perfileria y Maderas"), un
disco "para acero inoxidable" quedaba hecho de inoxidable, y las barras PEX
de 16, 20 y 32 mm compartian hoja porque la unica medida leida era el largo
de la barra.

Todo es determinista y explicable: cada atributo trae su confianza y, si es
baja o hubo que elegir entre dos lecturas, el motivo queda en
"motivos_revision".
"""
import re
from functools import lru_cache

import taxonomia as tx
from catalogo_atributos import (ABREVIATURAS, CATEGORIAS_CON_CONEXION, CATEGORIAS_ELECTRICAS,
                                CATEGORIAS_NEGRO_ES_MATERIAL, COLORES, EXTREMOS,
                                GRADOS_ACERO_CARBONO, MARCADORES_APLICACION, MATERIAL_POR_TIPO,
                                MATERIALES, MATERIALES_SISTEMA_METRICO, NO_ES_MATERIAL,
                                SERIES_INOXIDABLE, SUSTANTIVOS_COMPONENTE, TERMINACIONES,
                                TERMINACIONES_POR_CATEGORIA, TIPOS_MATERIAL_ES_APLICACION)

# ====================== 1. TEXTO ======================

@lru_cache(maxsize=None)
def palabras(texto):
    """Tokens normalizados (sin tildes, minusculas) con las abreviaturas
    expandidas. A diferencia de taxonomia.lemas, CONSERVA las palabras vacias:
    "para", "con" y "de" son las que dicen si un material es el del producto,
    un componente o la aplicacion."""
    salida = []
    for token in tx.normalizar(tx.preposiciones(texto)).split():
        salida.extend(ABREVIATURAS.get(token, token).split())
    return tuple(salida)


@lru_cache(maxsize=None)
def secuencia(texto):
    """(lemas de contenido, indice de cada uno en palabras(texto)).

    Los lemas son los de taxonomia (singular, sin palabras vacias), asi que
    una frase del catalogo se compara igual que siempre; el indice permite
    volver a mirar las palabras vacias que habia antes de cada lema."""
    lemas, indices = [], []
    for i, p in enumerate(palabras(texto)):
        if p in tx.VACIAS:
            continue
        lemas.append(tx.singular(p))
        indices.append(i)
    return tuple(lemas), tuple(indices)


@lru_cache(maxsize=None)
def lemas_de_frase(frase):
    return secuencia(frase)[0]


def posiciones(lemas_texto, frase):
    pal = lemas_de_frase(frase)
    if not pal:
        return []
    n = len(pal)
    return [i for i in range(len(lemas_texto) - n + 1) if lemas_texto[i:i + n] == pal]


def nombre_normalizado(nombre, descripcion=""):
    """La version del nombre que se usa para buscar: sin tildes, minusculas,
    decimales con punto (0,7 -> 0.7), abreviaturas expandidas y las 'x' de las
    medidas convertidas en espacios. El nombre original se conserva aparte,
    tal cual se escribio, para mostrarlo."""
    t = tx.sin_tildes(tx.preposiciones(" ".join(x for x in (nombre, descripcion) if x))).lower()
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    t = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", " ", t)
    t = re.sub(r"(?<=\d)(mm|cm|mts?|m)\b", r" \1", t)
    t = re.sub(r"[^a-z0-9./\"ñ ]+", " ", t)
    fuera = []
    for token in t.split():
        limpio = token.strip(".")
        fuera.extend(ABREVIATURAS.get(limpio, limpio).split())
    # El Nombre Item suele repetir palabras de la descripcion ("Plancha
    # policarbonato" + "Plancha policarbonato transparente 0,7..."): se deja
    # una sola de cada una, en el orden en que aparecen.
    return " ".join(dict.fromkeys(p for p in fuera if p))


# ====================== 2. MATERIALES ======================

class _Material(object):
    __slots__ = ("nombre", "base", "alias", "campo", "pos", "rol", "confianza", "orden",
                 "largo")

    def __init__(self, nombre, base, alias, campo, pos, rol, confianza, orden, largo):
        self.nombre, self.base, self.alias = nombre, base, alias
        self.campo, self.pos, self.rol = campo, pos, rol
        self.confianza, self.orden, self.largo = confianza, orden, largo


_BASE_DE = {nombre: base for nombre, base, _alias in MATERIALES}
_ORDEN_DE = {nombre: i for i, (nombre, _b, _a) in enumerate(MATERIALES)}

# Abreviaturas de material: calzan igual, pero con algo menos de confianza.
_ALIAS_ABREVIADOS = {"br", "bce", "galv", "zn", "fe", "cu", "alu", "alum", "ss", "sus", "inox",
                     "hss", "policarb"}

# Un acero especifico gana a "acero" a secas: "acero galvanizado", "fierro
# negro" y "acero inoxidable" son todos acero, pero lo que define al producto
# es el adjetivo.
_ACEROS_ESPECIFICOS = {"Acero inoxidable", "Acero galvanizado", "Zincalum", "Acero negro",
                       "Acero rápido (HSS)", "Hierro fundido"}

# Materiales que el catalogo usa como SISTEMA de tuberia: un terminal de
# laton DZR "PEX" es de laton para tuberia PEX. Ver detectar_materiales.
_METALES = {"Acero inoxidable", "Acero galvanizado", "Acero negro", "Acero carbono", "Cobre",
            "Latón", "Bronce", "Aluminio", "Hierro fundido"}

# Bases de material que, en una herramienta de corte o un adhesivo, son lo
# que el producto trabaja (aplicacion). Resinas y elastomeros no: un
# "adhesivo epoxico" es epoxico.
_BASES_SUSTRATO = {"Acero", "Acero inoxidable", "Aluminio", "Madera y derivados", "Plásticos",
                   "Hierro", "Cobre", "Aleaciones de cobre"}

# Materiales de los que esta hecha la herramienta, nunca lo que corta:
# una "Broca p/metal HSS" es de acero rapido y corta metal.
_MATERIALES_DE_HERRAMIENTA = {"Acero rápido (HSS)", "Epoxi"}

_FRONTERAS = re.compile(r"[,;()\[\]]")


def _segmentos(texto):
    """El texto partido en clausulas (por comas y parentesis). Un marcador
    "para"/"con" solo afecta a lo que viene despues DENTRO de su clausula:
    en "Cañeria de cobre tipo M para agua, 1\"" el "para" no alcanza a
    ningun material."""
    return [s for s in _FRONTERAS.split(tx.preposiciones(texto)) if s.strip()]


def _alias_por_categoria(categoria):
    alias = [(nombre, base, list(lista)) for nombre, base, lista in MATERIALES]
    if categoria in CATEGORIAS_NEGRO_ES_MATERIAL:
        for entrada in alias:
            if entrada[0] == "Acero negro":
                entrada[2].extend(["negro", "negra"])
    return alias


@lru_cache(maxsize=None)
def _alias_compilados(categoria):
    salida = []
    for nombre, base, lista in _alias_por_categoria(categoria):
        for a in lista:
            lem = lemas_de_frase(a)
            if lem:
                salida.append((nombre, base, a, lem))
    # frases largas primero: "acero inoxidable" antes que "acero"
    salida.sort(key=lambda t: -len(t[3]))
    return tuple(salida)


def _vocabulario_material():
    return {lem for _n, _b, _a, lemas in _alias_compilados("") for lem in lemas}


def _rol(palabras_seg, indice, tipo, nombre_material, base):
    """principal | componente | aplicacion, mirando lo que hay ANTES del
    material dentro de su clausula."""
    previas = palabras_seg[:indice]
    if nombre_material in _MATERIALES_DE_HERRAMIENTA:
        return "principal"
    if any(p in MARCADORES_APLICACION for p in previas):
        return "aplicacion"
    # "cabezal KNE de aluminio", "c/marco aluminio": manda la PIEZA que el
    # material califica, no el "con" suelto. Con la regla escrita al reves
    # ("cualquier cosa despues de con es componente"), una "válvula
    # retención c/resorte inoxidable" se quedaba sin material.
    # Los numeros no cuentan en la ventana: en "conexion inferior 1/2 NPT
    # bronce" la pieza que el bronce califica es la conexion, aunque entre
    # medio venga la medida.
    cercanas = [p for p in previas if p not in tx.VACIAS and not p.isdigit()][-4:]
    if any(p in SUSTANTIVOS_COMPONENTE for p in cercanas):
        return "componente"
    if tipo in TIPOS_MATERIAL_ES_APLICACION or tipo in ("Broca", "Tornillo para Madera"):
        if base in _BASES_SUSTRATO and nombre_material not in _MATERIALES_DE_HERRAMIENTA:
            return "aplicacion"
    return "principal"



def _materiales_en(texto, campo, categoria, tipo):
    encontrados = []
    for n_seg, segmento in enumerate(_segmentos(texto)):
        pal = palabras(segmento)
        lem, idx = secuencia(segmento)
        vetados = set()
        for frase in NO_ES_MATERIAL:
            for p in posiciones(lem, frase):
                vetados.update(range(p, p + len(lemas_de_frase(frase))))
        ocupados = set()
        for nombre, base, alias, alem in _alias_compilados(categoria):
            n = len(alem)
            for p in range(len(lem) - n + 1):
                if lem[p:p + n] != alem:
                    continue
                span = set(range(p, p + n))
                if span & ocupados or span & vetados:
                    continue
                if p > 0 and lem[p - 1] in tx.NEGADORES:
                    continue
                ocupados |= span
                rol = _rol(pal, idx[p], tipo, nombre, base)
                confianza = 0.9 if alias in _ALIAS_ABREVIADOS else 1.0
                if campo == "desc":
                    confianza -= 0.05
                encontrados.append(_Material(nombre, base, alias, campo, (n_seg, p), rol,
                                             confianza, _ORDEN_DE[nombre], n))
    return encontrados


_GRADO_INOX = re.compile(r"\b(?:aisi|ss|sus|inox|tp)?\s*-?\s*(2\d\d|3\d\d|4\d\d)(l|h)?\b")
_GRADO_INOX_PEGADO = re.compile(r"\b(?:aisi|ss|sus|inox)\s*-?\s*(\d{3})(l|h)?\b")
_ASTM = re.compile(r"\b(?:astm\s*)?a\s*-?\s*(36|53|105|106|179|234|312|500|572)\b(\s*(?:gr\.?|grado)\s*[ab]\b)?"
                   r"(\s*wpb)?")
_SAE = re.compile(r"\b(?:sae|aisi)?\s*(10[1-9]\d)\b")
_GRADO_PERNO = re.compile(r"\b(?:g|gr|grado)\s*[.\-]?\s*([258])\b|\b(8\.8|10\.9|12\.9)\b")


def grados(texto, categoria=""):
    """-> dict con los grados/normas de material que trae el texto:
    {'inox': 'AISI 316L', 'astm': ['ASTM A53'], 'sae': 'SAE 1010', 'perno': 'G-5'}"""
    t = tx.texto_plano(texto)
    salida = {}
    menciona_inox = bool(re.search(r"\binox|\binoxidable|\bss\s*\d|\baisi\s*[234]|\bsus\b|\ba\s*-?\s*312\b", t))
    m = _GRADO_INOX_PEGADO.search(t)
    if m and m.group(1) in SERIES_INOXIDABLE:
        salida["inox"] = "AISI %s%s" % (m.group(1), (m.group(2) or "").upper())
    elif menciona_inox:
        for m in _GRADO_INOX.finditer(t):
            if m.group(1) in SERIES_INOXIDABLE:
                salida["inox"] = "AISI %s%s" % (m.group(1), (m.group(2) or "").upper())
                break
    normas = []
    for m in _ASTM.finditer(t):
        n = "ASTM A%s" % m.group(1)
        if m.group(3):
            n += " WPB"
        if n not in normas:
            normas.append(n)
    if normas:
        salida["astm"] = normas
    m = _SAE.search(t)
    if m and not menciona_inox and categoria in ("Planchas y Perfiles", ""):
        salida["sae"] = "SAE %s" % m.group(1)
    m = _GRADO_PERNO.search(t)
    if m and categoria in ("Fijaciones", ""):
        salida["perno"] = ("G-%s" % m.group(1)) if m.group(1) else m.group(2)
    return salida


def _a_un_error(a, b):
    """True si 'a' y 'b' difieren en una sola letra (cambiada, agregada o
    borrada). Es la distancia de edicion acotada a 1, escrita aca y no
    reusada de busqueda.py porque ese modulo importa a este."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    corto, largo = (a, b) if la < lb else (b, a)
    i = 0
    while i < len(corto) and corto[i] == largo[i]:
        i += 1
    return corto[i:] == largo[i + 1:]


@lru_cache(maxsize=4096)
def _palabra_material_difusa(token):
    """Un error de tipeo en el nombre de un material ("fiero" por "fierro"):
    distancia 1 contra un alias de 5+ letras, y solo si la palabra no es otra
    cosa conocida. Queda con confianza baja y marcado para revision."""
    if len(token) < 5 or token in vocabulario_conocido():
        # Una palabra que el sistema YA entiende no es el error de tipeo de
        # otra: sin esta guarda, el "cuerpo" de "valvula solo cuerpo" se leia
        # como un producto de cuero.
        return None
    candidatos = set()
    for nombre, _b, alias, alem in _alias_compilados(""):
        if len(alem) != 1 or len(alem[0]) < 5:
            continue
        if tx.singular(token) == alem[0]:
            return None
        if _a_un_error(tx.singular(token), alem[0]):
            candidatos.add(nombre)
    return candidatos.pop() if len(candidatos) == 1 else None


def detectar_materiales(nombre, descripcion, categoria="", tipo=None, especificaciones=None):
    """-> dict con material, material_base, material_grado, sistema,
    secundarios (componentes y aplicaciones), confianza y motivos.

    El material del producto es el PRINCIPAL mas relevante: el del nombre
    antes que el de la descripcion, el primero en aparecer, y el acero
    especifico (inoxidable, galvanizado, negro) antes que "acero" a secas.
    """
    candidatos = (_materiales_en(nombre, "nom", categoria, tipo) +
                  _materiales_en(descripcion, "desc", categoria, tipo))
    principales = [c for c in candidatos if c.rol == "principal"]
    secundarios = [{"material": c.nombre, "rol": c.rol} for c in candidatos if c.rol != "principal"]
    motivos = []
    texto = " ".join(x for x in (nombre, descripcion) if x)
    g = grados(texto, categoria)
    especificaciones = especificaciones or {}

    def orden(c):
        return (0 if c.campo == "nom" else 1, c.pos, -c.largo, c.orden)

    principales.sort(key=orden)
    elegido = principales[0] if principales else None
    confianza = elegido.confianza if elegido else 0.0

    # Un acero especifico le gana a "acero"/"fierro" a secas (dentro del
    # mismo producto no puede ser las dos cosas).
    if elegido is not None and elegido.nombre == "Acero carbono":
        especificos = [c for c in principales if c.nombre in _ACEROS_ESPECIFICOS]
        if especificos:
            elegido = especificos[0]
            confianza = elegido.confianza

    # Sistema de tuberia: metal + plastico de sistema en el mismo fitting.
    sistema = None
    nombres = [c.nombre for c in principales]
    plasticos = [n for n in nombres if n in MATERIALES_SISTEMA_METRICO]
    metales = [n for n in nombres if n in _METALES]
    if plasticos and categoria in CATEGORIAS_CON_CONEXION:
        sistema = plasticos[0]
        if metales and elegido is not None and elegido.nombre in MATERIALES_SISTEMA_METRICO:
            elegido = next(c for c in principales if c.nombre == metales[0])
            confianza = elegido.confianza

    # Dos materiales principales incompatibles en el nombre: se elige el
    # primero pero se avisa.
    if elegido is not None:
        otros = {c.nombre for c in principales
                 if c.campo == elegido.campo and c.nombre != elegido.nombre
                 and not (c.nombre in MATERIALES_SISTEMA_METRICO and sistema)
                 and not (c.nombre == "Acero carbono" and elegido.nombre in _ACEROS_ESPECIFICOS)}
        if otros:
            motivos.append("dos materiales en el texto: %s y %s" % (elegido.nombre,
                                                                    ", ".join(sorted(otros))))
            confianza = min(confianza, 0.6)

    material = elegido.nombre if elegido else None
    grado = None
    inferido = None

    # Grados: el de inoxidable confirma (o aporta) el material.
    if "inox" in g:
        grado = g["inox"]
        if material is None:
            material, confianza, inferido = "Acero inoxidable", 0.95, "grado " + grado
    normas = g.get("astm", [])
    if material is None and normas:
        n = normas[0]
        if n in ("ASTM A53", "ASTM A106"):
            material, confianza, inferido = "Acero negro", 0.85, "norma " + n
        elif n in ("ASTM A36", "ASTM A105", "ASTM A234", "ASTM A234 WPB", "ASTM A500", "ASTM A572"):
            material, confianza, inferido = "Acero carbono", 0.9, "norma " + n
    if grado is None and material in ("Acero carbono", "Acero negro", None):
        if "ASTM A36" in normas:
            grado = "ASTM A36"
        elif "sae" in g:
            grado = g["sae"]
            if material is None:
                material, confianza, inferido = "Acero carbono", 0.9, "grado " + grado
    if material is None and g.get("perno") in GRADOS_ACERO_CARBONO:
        material, confianza, inferido = "Acero carbono", 0.85, "grado de perno " + g["perno"]
    if material is None and especificaciones.get("tipo_pared") and tipo in ("Cañería", "Tubo"):
        material, confianza, inferido = "Cobre", 0.8, "cañería " + especificaciones["tipo_pared"]
    if material is None and tipo in MATERIAL_POR_TIPO:
        material, confianza, inferido = MATERIAL_POR_TIPO[tipo], 0.8, "tipo " + tipo
    if material is None:
        for token in palabras(nombre or "") + palabras(descripcion or ""):
            difuso = _palabra_material_difusa(token)
            if difuso:
                material, confianza = difuso, 0.65
                inferido = "posible error de tipeo: %r" % token
                motivos.append("material leido de %r (¿%s?)" % (token, difuso))
                break
    if inferido and not any(m.startswith("material leido") for m in motivos):
        motivos.append("material inferido por " + inferido)

    aplicacion = next((s["material"] for s in secundarios if s["rol"] == "aplicacion"), None)
    return {
        "material": material,
        "material_base": _BASE_DE.get(material),
        "material_grado": grado,
        "sistema": sistema if sistema != material else None,
        "aplicacion": aplicacion,
        "secundarios": secundarios,
        "confianza": round(confianza, 2) if material else 0.0,
        "inferido": inferido,
        "motivos": motivos,
    }


# ====================== 3. ESPECIFICACIONES ======================

_SCH = re.compile(r"\b(?:sch|sched|schedule|ced|cedula)\.?\s*-?\s*(\d{1,3}s?|std|xs|xxs)\b")
_SCH_SUELTO = re.compile(r"\b(std|xs|xxs)\b")
_PN = re.compile(r"\bpn\s*-?\s*(\d{1,3})\b")
_PSI = re.compile(r"(?<![\d.\-/])(\d{2,5})\s*psi\b")
_BAR = re.compile(r"(?<![\d.\-+/])(\d{1,2}(?:\.\d)?)\s*bar\b")
_CLASE = re.compile(r"\b(?:clase|class)\s*(\d{3,4})\b|\b(150|300|600|900|1500)\s*(?:#|lbs?)\b")
_ROSCA = re.compile(r"\b(npt|nptf|bsp|bspt|bspp|unc|unf|nc|nf|npsm)\b")
_METRICA = re.compile(r"(?<![a-z0-9])m\s?(\d{1,2}(?:\.\d{1,2})?)(?![a-z0-9.])")
_TIPO_PARED = [re.compile(r"\btipo\s*([klm])\b"), re.compile(r"\b([klm])\s+cobre\b"),
               re.compile(r"\bcobre\s+(?:tipo\s+)?([klm])\b"),
               re.compile(r"\bcan(?:i|ñ)?eria\s+([klm])\b")]
_SERIE = re.compile(r"\bserie\s*(\d(?:\.\d)?)\b")
_AWS = re.compile(r"(?<![\d.])e?\s*-?\s*(6010|6011|6013|7018|7024|308l?|309l?|316l?)\b")
_ANGULO = re.compile(r"(?<![\d.])(22|45|60|90|135|180)\s*(?:°|º|grados?)")
_ANGULO_RL = re.compile(r"\brl\s*(45|90)\b")
_CORRIENTE = re.compile(r"(?<![\w.])(\d{1,3})\s*a\b(?!\s*/)")
_VOLTAJE = re.compile(r"(?<![\w.])(\d{2,4})\s*v(?:ca|cc|ac|dc)?\b")
_POTENCIA = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(k?w)\b")
_CAPACIDAD = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(lts?|litros?|l)\b")
_VOLUMEN = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(ml|cc)\b")
_PESO = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(kg|kgs|grs?|g)\b(?!\s*/)")
_DENSIDAD = re.compile(r"(\d+)\s*kg\s*/\s*m3")
_PRESENTACION = re.compile(
    r"\b(?:pack|caja|bolsa|set|paquete|display|juego)\s*(?:de\s*)?(\d{1,4})\b"
    r"|(?<![\w.])(\d{1,4})\s*(?:un|und|unid|unidades|uds|pzs|piezas|pares|pcs)\b")
_GRANO = re.compile(r"\bgrano\s*(\d{2,4})\b|\bn[o°º]?\.?\s*(\d{2,3})\b")
_PORCENTAJE = re.compile(r"(?<![\d.])(\d{1,2})\s*%")
_ERW = re.compile(r"\berw\b|\bcon costura\b")
_SIN_COSTURA = re.compile(r"\bsin costura\b|\bseamless\b")
_PASO = re.compile(r"\bpaso total\b|\bp\s*/\s*t\b|\bpara t\b|\bpaso reducido\b")
_ACCIONAMIENTO = [("manilla", "Manilla"), ("palanca", "Palanca"), ("mariposa", "Mariposa"),
                  ("volante", "Volante"), ("actuador", "Actuador"), ("solenoide", "Solenoide"),
                  ("resorte", "Resorte")]


def _fmt_num(texto):
    v = float(texto)
    return ("%g" % v).replace(".", ",")


def especificaciones(nombre, descripcion, categoria="", tipo=None):
    """Especificaciones tecnicas: schedule, presion, rosca, conexion, norma,
    tipo de pared, angulo, datos electricos, presentacion. Cada una con su
    forma canonica ("SCH 40", "PN16", "NPT", "HI-HI")."""
    t = tx.texto_plano(" ".join(x for x in (nombre, descripcion) if x))
    s = {}
    m = _SCH.search(t)
    if m:
        v = m.group(1).upper()
        s["schedule"] = v if v in ("STD", "XS", "XXS") else "SCH " + v
    elif categoria in ("Piping y Fittings",):
        m = _SCH_SUELTO.search(t)
        if m:
            s["schedule"] = m.group(1).upper()
    m = _PN.search(t)
    if m:
        s["presion"] = "PN%s" % m.group(1)
    else:
        m = _PSI.search(t)
        if m:
            s["presion"] = "%s psi" % m.group(1)
        else:
            m = _BAR.search(t)
            if m:
                s["presion"] = "%s bar" % _fmt_num(m.group(1))
            else:
                m = _CLASE.search(t)
                if m:
                    s["presion"] = "Clase %s" % (m.group(1) or m.group(2))
    roscas = []
    for m in _ROSCA.finditer(t):
        r = {"nc": "UNC", "nf": "UNF", "nptf": "NPT"}.get(m.group(1), m.group(1).upper())
        if r not in roscas:
            roscas.append(r)
    if categoria in ("Fijaciones",) or tipo in ("Tuerca", "Perno", "Tarugo"):
        m = _METRICA.search(t)
        if m:
            roscas.append("M%s" % m.group(1))
    if roscas:
        s["rosca"] = " ".join(roscas)
    m = re.search(r"(\d+\s*/\s*\d+|\d+[ .]\d+\s*/\s*\d+)\s*-\s*(\d{1,2})\b(?!\s*/)", t)
    if m and (categoria == "Fijaciones" or tipo in ("Tuerca", "Varilla Roscada")):
        s["hilos_por_pulgada"] = m.group(2)
    for patron in _TIPO_PARED:
        m = patron.search(t)
        if m and categoria in ("Piping y Fittings", ""):
            s["tipo_pared"] = "Tipo %s" % m.group(1).upper()
            break
    m = _SERIE.search(t)
    if m and "ppr" in t:
        s["serie"] = "Serie %s" % _fmt_num(m.group(1))
    if categoria in CATEGORIAS_CON_CONEXION:
        extremos = _extremos(t)
        if extremos:
            s["conexion"] = extremos
        m = _ANGULO.search(t) or _ANGULO_RL.search(t)
        if m:
            s["angulo"] = "%s°" % m.group(1)
        elif tipo in ("Codo", "Curva"):
            m = re.search(r"\b(45|90)\b(?!\s*(?:mm|cm|x|\"|°))", t)
            if m:
                s["angulo"] = "%s°" % m.group(1)
        m = _PASO.search(t)
        if m:
            s["paso"] = "Paso reducido" if "reducido" in m.group(0) else "Paso total"
    if tipo and tipo.startswith("Válvula"):
        for palabra, canonico in _ACCIONAMIENTO:
            if re.search(r"\b%s\b" % palabra, t):
                s["accionamiento"] = canonico
                break
    normas = [n for n in grados(t).get("astm", [])
              if n not in ("ASTM A36",)]
    if normas:
        s["norma"] = normas[0]
    if categoria == "Soldadura y Gases" or tipo == "Electrodo":
        m = _AWS.search(t)
        if m:
            s["norma"] = "AWS E%s" % m.group(1).upper()
    if _ERW.search(t) and categoria == "Piping y Fittings":
        s["costura"] = "Con costura"
    elif _SIN_COSTURA.search(t):
        s["costura"] = "Sin costura"
    g = grados(t, categoria)
    if g.get("perno"):
        s["grado"] = g["perno"]
    if categoria in CATEGORIAS_ELECTRICAS:
        m = _CORRIENTE.search(t)
        if m:
            s["corriente"] = "%s A" % m.group(1)
        m = _VOLTAJE.search(t)
        if m:
            s["voltaje"] = "%s V" % m.group(1)
        m = _POTENCIA.search(t)
        if m:
            s["potencia"] = "%s %s" % (_fmt_num(m.group(1)), m.group(2).upper().replace("KW", "kW"))
    m = _CAPACIDAD.search(t)
    if m:
        s["capacidad"] = "%s L" % _fmt_num(m.group(1))
    else:
        m = _VOLUMEN.search(t)
        if m:
            s["capacidad"] = "%s %s" % (_fmt_num(m.group(1)), m.group(2))
    m = _DENSIDAD.search(t)
    if m:
        s["densidad"] = "%s kg/m³" % m.group(1)
    else:
        m = _PESO.search(t)
        if m:
            unidad = "kg" if m.group(2).startswith("k") else "g"
            s["peso"] = "%s %s" % (_fmt_num(m.group(1)), unidad)
    m = _PRESENTACION.search(t)
    if m:
        s["presentacion"] = "%s un" % (m.group(1) or m.group(2))
    if categoria == "Abrasivos y Corte":
        m = _GRANO.search(t)
        if m:
            s["grano"] = "Grano %s" % (m.group(1) or m.group(2))
    if categoria == "Soldadura y Gases":
        m = _PORCENTAJE.search(t)
        if m:
            # La ley de una soldadura de plata (6%, 15%) o el estano de un
            # carrete (50%): es lo que decide su precio.
            s["ley"] = "%s%%" % m.group(1)
    return s


def _extremos(t):
    """'HI-HI', 'SO-HE', 'Fusión'... en el orden en que se escribieron."""
    t = re.sub(r"hilo\s+interior", " hi ", t)
    t = re.sub(r"hilo\s+exterior", " he ", t)
    salida = []
    for token in re.findall(r"[a-z]+", t):
        e = EXTREMOS.get(token)
        if e:
            salida.append(e)
    if not salida:
        return None
    unicos = []
    for e in salida:
        if e in ("Fusión", "Cementar", "Brida"):
            if e not in unicos:
                unicos.append(e)
        else:
            unicos.append(e)
    return "-".join(unicos[:3])


# ====================== 4. TERMINACIONES ======================

def terminaciones(nombre, descripcion, categoria=""):
    texto = " ".join(x for x in (nombre, descripcion) if x)
    lem = secuencia(texto)[0]
    salida = []
    frases = list(TERMINACIONES) + TERMINACIONES_POR_CATEGORIA.get(categoria, [])
    for frase, canonico in sorted(frases, key=lambda f: -len(lemas_de_frase(f[0]))):
        if posiciones(lem, frase) and canonico not in salida:
            if canonico == "Zincado" and "Galvanizado en caliente" in salida:
                continue
            salida.append(canonico)
    if "Laminada en frío" in salida or "Laminada en caliente" in salida:
        salida = [s for s in salida if s != "Laminado"]
    color = None
    for p in palabras(texto):
        if p in COLORES and not (p in ("verde",) and categoria == "Maderas"):
            if p in ("negro", "negra") and categoria in CATEGORIAS_NEGRO_ES_MATERIAL:
                continue
            color = COLORES[p]
            break
    return salida, color


# ====================== 6. TERMINOS NO INTERPRETADOS ======================

@lru_cache(maxsize=1)
def vocabulario_conocido():
    """Todas las palabras que el sistema sabe interpretar: reglas de tipo,
    materiales, terminaciones, colores, abreviaturas, conexiones y palabras
    vacias. Lo que un producto tenga fuera de esto es 'sin interpretar'."""
    from catalogo_taxonomia import DESCRIPTORES, REGLAS
    conocido = set(tx.VACIAS) | set(tx.NEGADORES) | set(tx.CUANTIFICADORES)
    for terminos, *_resto in REGLAS:
        for t in terminos:
            conocido.update(lemas_de_frase(t))
    conocido |= _vocabulario_material()
    for frase, _c in TERMINACIONES:
        conocido.update(lemas_de_frase(frase))
    conocido.update(tx.singular(c) for c in COLORES)
    conocido.update(tx.singular(a) for a in ABREVIATURAS)
    conocido.update(tx.singular(e) for e in EXTREMOS)
    conocido.update(tx.singular(d) for d in DESCRIPTORES)
    conocido.update({"npt", "bsp", "bspt", "unc", "unf", "sch", "pn", "psi", "bar", "mm", "cm",
                     "mt", "mts", "metro", "plg", "pulgada", "pulg", "x", "dn", "tipo", "astm",
                     "aisi", "sae", "din", "iso", "ansi"})
    return conocido


def auditoria(items, clasificar, top=25):
    """El diccionario visto desde los DATOS: que palabras del catalogo real
    el sistema todavia no sabe interpretar, que productos quedaron con poca
    confianza y cuales se decidieron por un margen minimo.

    Es la contracara de "no inventar": cuando aparece un termino que ninguna
    tabla explica, el sistema no lo mete a la fuerza en una categoria -- lo
    deja como atributo sin interpretar y lo reporta aca, con una sugerencia
    de que podria ser (abreviatura de una palabra conocida, error de tipeo o
    marca nueva) para que una persona decida.

        py -3.14 driver.py atributos
    """
    import collections
    conocido = vocabulario_conocido()
    desconocidos = collections.Counter()
    ejemplos = {}
    mayusculas = collections.Counter()
    baja_confianza, ambiguas, sin_material, sin_medida = [], [], [], []

    for it in items:
        nombre = it.get("nombre_item") or ""
        desc = it.get("descripcion") or ""
        ficha = clasificar(nombre, desc)
        for palabra in sin_interpretar(nombre, conocido):
            desconocidos[palabra] += 1
            ejemplos.setdefault(palabra, nombre)
            if _escrita_en_mayuscula(palabra, nombre + " " + desc):
                mayusculas[palabra] += 1
        if ficha.get("revisar") and ficha["confianza"] < 0.7:
            baja_confianza.append((nombre, desc, ficha))
        if ficha.get("ambigua"):
            ambiguas.append((nombre, desc, ficha))
        if "material" in ficha.get("faltantes", []):
            sin_material.append((nombre, desc, ficha))
        if "medida" in ficha.get("faltantes", []):
            sin_medida.append((nombre, desc, ficha))

    sugerencias = {p: _sugerencia_para(p, conocido, mayusculas.get(p, 0))
                   for p, _n in desconocidos.most_common(top)}
    return {
        "desconocidos": desconocidos.most_common(top),
        "ejemplos": ejemplos,
        "sugerencias": sugerencias,
        "baja_confianza": baja_confianza,
        "ambiguas": ambiguas,
        "sin_material": sin_material,
        "sin_medida": sin_medida,
        "n_desconocidos": len(desconocidos),
    }


def _escrita_en_mayuscula(palabra, texto):
    """Si la palabra aparece con inicial mayuscula (o toda en mayusculas) en
    el texto original, probablemente sea una marca o un modelo: "Suvinil",
    "KWB", "DAB". No se decide solo, se propone en la auditoria."""
    for m in re.finditer(r"\b\w+", tx.sin_tildes(texto)):
        if m.group(0).lower() == palabra and m.group(0)[0].isupper():
            return True
    return False


def _sugerencia_para(palabra, conocido, veces_en_mayuscula):
    """Que puede ser una palabra que ninguna tabla explica. Nunca se aplica
    sola: se propone para que alguien la agregue al catalogo."""
    raiz_palabra = tx.singular(palabra)
    prefijos = sorted({c for c in conocido if len(c) > len(raiz_palabra) + 1
                       and c.startswith(raiz_palabra) and len(raiz_palabra) >= 3})
    if len(prefijos) == 1:
        return "¿abreviatura de %r?" % prefijos[0]
    if len(palabra) >= 5:
        cercanas = sorted({c for c in conocido if len(c) >= 5 and _a_un_error(raiz_palabra, c)})
        if len(cercanas) == 1:
            return "¿error de tipeo de %r?" % cercanas[0]
    if veces_en_mayuscula:
        return "¿marca o modelo?"
    return "término nuevo: ¿producto, material o descriptor?"


def sin_interpretar(nombre, conocido):
    """Palabras del NOMBRE que ninguna tabla explica. No se adivina que son:
    se informan, para que un humano decida si son una marca, un material o
    un tipo nuevo (driver.py atributos las lista por frecuencia)."""
    salida = []
    for p in palabras(nombre or ""):
        if len(p) < 3 or not p.isalpha():
            continue
        if tx.singular(p) in conocido or p in conocido:
            continue
        if p not in salida:
            salida.append(p)
    return salida
