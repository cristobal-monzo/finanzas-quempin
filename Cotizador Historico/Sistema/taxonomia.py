# -*- coding: utf-8 -*-
"""
taxonomia.py -- clasifica cada item comprado en categoria > subcategoria >
hoja, y extrae su medida normalizada. Es el MOTOR; los datos (categorias,
materiales, reglas) viven en catalogo_taxonomia.py.

Lo consumen los dos caminos del modulo, para que la consulta por consola y
el dashboard web clasifiquen exactamente igual:
  - cotizador_historico.consultar_item  (CLI y conversacion)
  - Visualizador Web/build_visualizador.py  (dashboard, Chile y Peru)

Cinco etapas independientes y testeables por separado:

  1. normalizar/raiz  -- texto comparable (sin tildes, sin plural)
  2. parsear_medidas  -- gramatica de medidas: "1.1/4 plg" -> 1.1/4"
  3. clasificar       -- QUE es el producto: categoria/subcategoria/tipo, con
                         el sustantivo principal mandando sobre el secundario
  4. atributos        -- DE QUE esta hecho y cuanto mide: material (con su
                         rol), dimensiones por esquema de familia y
                         especificaciones tecnicas (ver atributos.py)
  5. clave_hoja       -- tipo + material + medida = la unidad de comparacion
                         de precios ("Codo de Bronce 1.1/4\"")

Por que existe (2026-09-08): antes esta logica vivia en JavaScript dentro de
Visualizador Web/template.html, duplicada y ya divergente entre Chile y Peru,
sin tests, y sin que la consulta por consola la usara. Ademas leia mal las
fracciones mixtas del catalogo chileno ("1.1/4" se leia "1/4"), asi que
promediaba en una sola hoja productos de tamanos distintos. Ver
docs/specs/2026-09-08-taxonomia-cotizador-design.md.

REGLA DE ORO: ningun item se oculta. Si no se le puede extraer la medida, la
hoja queda marcada "(sin medida)" y el item sigue visible y contable -- el
sistema anterior descartaba 136 de 1193 compras (11,4%) sin avisar.
"""
import re
import unicodedata
from fractions import Fraction
from functools import lru_cache

import presentacion

from catalogo_taxonomia import (CATEGORIAS, CATEGORIAS_CON_MATERIAL, CATEGORIAS_CON_MEDIDA,
                                CATEGORIAS_CON_MODELO, CATEGORIAS_ENTERO_ES_PULGADA,
                                CATEGORIAS_SECUNDARIAS, CATEGORIAS_SUBCATEGORIA_POR_MATERIAL,
                                DESAMBIGUACION, ENVASES, ENVASES_CON_DE, FAMILIA_DE_SUBCATEGORIA,
                                MARCADORES_COMPONENTE, NO_PRODUCTO, REDIRECCION_POR_MATERIAL,
                                REGLAS, SUBCATEGORIA_SIN_MATERIAL, TIPO_POR_MATERIAL)


# ====================== 1-2. MEDIDAS ======================

DENOM_VALIDOS = {2, 3, 4, 8, 16, 32, 64}

# Angulos tipicos de un fitting ("Codo 90", "Curva 45"): nunca son el diametro.
ANGULOS_DE_FITTING = {22, 45, 60, 90, 135, 180}

# Ningun fitting del catalogo pasa de 24 pulgadas nominales.
MAX_PULGADAS_NOMINAL = 24

UNIDADES_PULGADA = {'"', "''", '”', '“', 'plg', 'plgs', 'pulg', 'pulgs', 'pulgada', 'pulgadas', 'pg', 'in', 'inch'}
UNIDADES_MM = {'mm'}
UNIDADES_CM = {'cm'}
UNIDADES_M = {'m', 'mt', 'mts', 'metro', 'metros'}
UNIDADES_LONGITUD = UNIDADES_PULGADA | UNIDADES_MM | UNIDADES_CM | UNIDADES_M

CORTES_ADMIN = re.compile(
    r'\b(cod|codigo|codigos|ref|factura|boleta|guia|doc|documento|folio|pedido|neto|ingreso|serie|sku|ean)\b\.?',
    re.I)

_ENTERO = r'\d+'
_DEC = r'\d+[.,]\d+'
_FRAC = r'\d+\s*/\s*\d+'
_MIXTA = r'\d+\s*[.\-·]\s*\d+\s*/\s*\d+|\d+\s+\d+\s*/\s*\d+'
_COMPONENTE = r'(?:' + _MIXTA + r'|' + _FRAC + r'|' + _DEC + r'|' + _ENTERO + r')'
_UNIDAD = r'(?:"|\'\'|”|plgs?\.?|pulgs?\.?|pulgadas?|pg|in|inch|mm|cm|mts?|metros?)'

# Un grupo dimensional: A [unidad] [x B [unidad]]... con la unidad opcional
# en cada componente y/o una sola al final.
PATRON_GRUPO = re.compile(
    r'(?<![\w/])' + _COMPONENTE + r'\s*' + _UNIDAD + r'?' +
    r'(?:\s*[x×]\s*' + _COMPONENTE + r'\s*' + _UNIDAD + r'?)*',
    re.I)
PATRON_COMP_UNIDAD = re.compile(r'(' + _COMPONENTE + r')\s*(' + _UNIDAD + r')?', re.I)


class Medida(object):
    """Una medida dimensional: uno o mas componentes que comparten unidad.

    componentes: lista de Fraction (pulgadas) o float (mm)
    unidad: 'plg' | 'mm'
    """

    __slots__ = ('componentes', 'unidad')

    def __init__(self, componentes, unidad):
        self.componentes = list(componentes)
        self.unidad = unidad

    @property
    def principal(self):
        return max(self.componentes)

    @property
    def mm(self):
        v = float(self.principal)
        return v * 25.4 if self.unidad == 'plg' else v

    def canonico(self):
        vistos = []
        for c in self.componentes:
            t = fraccion_a_texto(c) if self.unidad == 'plg' else ('%g' % float(c))
            vistos.append(t)
        # componentes todos iguales -> se muestra uno solo ("1/2x1/2" -> 1/2")
        if len(set(vistos)) == 1:
            vistos = vistos[:1]
        suf = '"' if self.unidad == 'plg' else 'mm'
        return 'x'.join(vistos) + suf

    def presentable(self):
        """La misma medida escrita para leerla: "20 m" donde canonico() dice
        "20000mm". canonico() no puede cambiar -- es la cadena con que el
        buscador calza medidas entre si."""
        if self.unidad == 'plg':
            return self.canonico()
        valores = [float(c) for c in self.componentes]
        if len(set(valores)) == 1:
            valores = valores[:1]
        return presentacion.grupo_texto(valores)

    def __eq__(self, otro):
        return (isinstance(otro, Medida) and self.unidad == otro.unidad
                and self.componentes == otro.componentes)

    def __hash__(self):
        return hash((self.unidad, tuple(self.componentes)))

    def __repr__(self):
        return 'Medida(%s)' % self.canonico()


def fraccion_a_texto(f):
    """Fraction -> convencion chilena del catalogo: 1.1/4, 3/4, 2."""
    f = Fraction(f)
    entero = f.numerator // f.denominator
    resto = f - entero
    if resto == 0:
        return str(entero)
    frac = '%d/%d' % (resto.numerator, resto.denominator)
    return frac if entero == 0 else '%d.%s' % (entero, frac)


def parsear_numero(txt):
    """'1.1/4' y '1 1/4' -> Fraction(5,4). '3/4' -> Fraction(3,4). '25' -> 25.

    Devuelve (valor, es_fraccionario) o (None, False) si no es un numero
    dimensional valido (denominador de codigo de modelo, fraccion impropia)."""
    t = txt.strip()
    pegada = re.match(r'^(\d+)\s*[.\-·]\s*(\d+)\s*/\s*(\d+)$', t)
    m = pegada or re.match(r'^(\d+)\s+(\d+)\s*/\s*(\d+)$', t)
    if m:
        ent, num, den = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if den not in DENOM_VALIDOS or num >= den:
            return None, False
        # "Codo BR 90 3/4" es un codo de 90 grados y 3/4 de pulgada, no uno de
        # noventa y tres cuartos: si la parte entera separada por espacio es un
        # angulo tipico de fitting, no forma parte de la medida. Y ningun
        # fitting del catalogo pasa de 24", asi que una parte entera mayor es
        # otro numero pegado (un codigo, una cantidad).
        # Se descarta solo la parte entera, no la medida completa: "Codo BR
        # 90 3/4" sigue siendo un codo de 3/4 de pulgada.
        if ent > MAX_PULGADAS_NOMINAL or (not pegada and ent in ANGULOS_DE_FITTING):
            return Fraction(num, den), True
        return Fraction(ent) + Fraction(num, den), True
    t = t.replace(' ', '')
    m = re.match(r'^(\d+)/(\d+)$', t)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if den not in DENOM_VALIDOS or num >= den * 8:
            return None, False
        return Fraction(num, den), True
    m = re.match(r'^(\d+)[.,](\d+)$', t)
    if m:
        return Fraction(m.group(1) + '.' + m.group(2)), False
    if re.match(r'^\d+$', t):
        return Fraction(int(t)), False
    return None, False


def _unidad_canonica(txt):
    u = (txt or '').strip().lower().rstrip('.')
    if u in UNIDADES_PULGADA:
        return 'plg'
    if u in UNIDADES_MM:
        return 'mm'
    if u in UNIDADES_CM:
        return 'cm'
    if u in UNIDADES_M:
        return 'm'
    return None


def texto_util(texto):
    """Quita el texto administrativo (codigos, folios, facturas) donde los
    numeros no son medidas."""
    t = ' ' + str(texto or '') + ' '
    m = CORTES_ADMIN.search(t)
    if m:
        t = t[:m.start()]
    t = re.sub(r'\(\s*\d{1,3}\s*\)', ' ', t)                       # (04): codigo de catalogo
    t = re.sub(r'\bN\s*[°º]\s*[\d.\-]+', ' ', t, flags=re.I)        # N°148985129
    t = re.sub(r'\b[A-Za-z]{1,6}[\-]?\d{2,}[A-Za-z0-9\-/]*\b', ' ', t)  # SS316, A234, VFB50-A, NB2-40/42
    t = re.sub(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b', ' ', t)          # fechas (ano completo, para no comerse '2,5-3/32')
    t = re.sub(r'\b\d{5,}\b', ' ', t)
    # magnitudes que no son dimensiones
    t = re.sub(r'\b\d+(?:[.,]\d+)?\s*(v|kv|w|kw|a|ma|kg|kgs|gr|grs|g|ml|cc|lt|lts|l|oz|psi|bar|hz|rpm|db|ah|'
               r'octanos|micrones|micras|un|uds|unidades|pzs|piezas|hjs|hojas|dias|mts2|m2|m3|pcs|pack)\b',
               ' ', t, flags=re.I)
    t = re.sub(r'\b\d+\s*[°º]\s*(c|k)?\b', ' ', t, flags=re.I)      # 90°, 105C
    return t


def parsear_medidas(texto):
    """Lista de Medida encontradas en el texto, en orden de aparicion."""
    t = texto_util(texto)
    salida = []
    for g in PATRON_GRUPO.finditer(t):
        crudo = g.group(0)
        pares = [(c, u) for c, u in PATRON_COMP_UNIDAD.findall(crudo) if c.strip()]
        if not pares:
            continue
        unidad_final = None
        for _, u in pares:
            cu = _unidad_canonica(u)
            if cu:
                unidad_final = cu
        # cada componente: unidad propia > unidad del grupo > pulgada si es fraccion
        por_unidad = {}
        orden = []
        for comp, u in pares:
            valor, es_frac = parsear_numero(comp)
            if valor is None:
                continue
            # Una fraccion es SIEMPRE pulgada en este catalogo, aunque el grupo
            # traiga una unidad metrica al final ('2.1/2x10cm' = 2.1/2" de diametro
            # por 10 cm de largo, no 2,5 cm).
            cu = 'plg' if es_frac else (_unidad_canonica(u) or unidad_final)
            if cu is None:
                continue                      # entero pelado sin unidad: no es medida
            if cu == 'cm':
                valor, cu = valor * 10, 'mm'
            elif cu == 'm':
                valor, cu = valor * 1000, 'mm'
            if cu not in por_unidad:
                por_unidad[cu] = []
                orden.append(cu)
            por_unidad[cu].append(valor)
        for cu in orden:
            salida.append(Medida(por_unidad[cu], cu))
    return salida


# Palabras que convierten al numero que sigue en una cantidad, no en una
# medida: "Pack 2 curva PVC" son dos curvas, no una curva de 2 pulgadas.
CUANTIFICADORES = {'pack', 'set', 'juego', 'kit', 'caja', 'bolsa', 'par', 'pares',
                   'unidad', 'unidades', 'cantidad', 'bulto', 'rollo', 'tira', 'barra'}

_PATRON_ENTERO_SOLO = re.compile(
    r'(?<![\w./-])(\d{1,2})(?![\w/."\u00b0\u00ba]|\s*[-/]\s*\d)')


# "032" (con cero a la izquierda) es como el catalogo escribe las medidas
# PPR/PVC en milimetros: 020, 025, 032, 040, 050, 063, 090. El cero inicial
# es la firma que lo distingue de una cantidad.
_PATRON_MM_CERO_IZQ = re.compile(r'(?<![\w.])0(\d{2})(?![\w/."])')

# DN50 = diametro nominal 50 mm (norma ISO). PN16 es presion nominal, no
# diametro: por eso el patron pide "dn" explicito y no "[a-z]{2}".
_PATRON_DN = re.compile(r'\bDN\s*(\d{1,4})\b', re.I)


def medida_metrica_por_convencion(textos):
    """Las dos convenciones metricas del catalogo que no llevan unidad
    escrita: 'DN50' y el '032' del PPR."""
    for texto in textos:
        t = str(texto or '')
        m = _PATRON_DN.search(t)
        if m:
            return Medida([Fraction(int(m.group(1)))], 'mm')
    for texto in textos:
        m = _PATRON_MM_CERO_IZQ.search(texto_util(texto))
        if m:
            return Medida([Fraction(int(m.group(1)))], 'mm')
    return None


def entero_pelado_como_pulgada(textos):
    """Un entero suelto leido como diametro nominal en pulgadas.

    El catalogo escribe a veces el diametro sin unidad ("Copla cobre 2 SO",
    "Tee galv. 1 NPT"). Fuera del piping un entero suelto NO es una medida
    (una gasolina de 93 octanos no mide 93 pulgadas), por eso esto solo se
    usa cuando la categoria del item la requiere -- ver clasificar().

    Tres guardas, cada una por un error real encontrado al medirlo sobre el
    catalogo (2026-09-08): no toma angulos de fitting ("Codo 90"), no toma
    la cantidad de un envase ("Pack 2 curva"), y no toma el extremo de un
    rango metrico ("abrazadera 8-12mm")."""
    for texto in textos:
        t = texto_util(texto)
        palabras = t.split()
        for i, palabra in enumerate(palabras):
            m = _PATRON_ENTERO_SOLO.fullmatch(palabra)
            if not m:
                continue
            valor = int(m.group(1))
            if valor < 1 or valor > 24 or valor in ANGULOS_DE_FITTING:
                continue
            anterior = palabras[i - 1].lower().strip('.,') if i else ''
            if anterior in CUANTIFICADORES:
                continue
            return Medida([Fraction(valor)], 'plg')
    return None


def medida_principal(*textos, aceptar_entero=False):
    """La medida que identifica al producto entre todas las del nombre y la
    descripcion. La pulgada manda sobre el metrico porque en este catalogo el
    diametro nominal va en pulgadas y el largo en cm/mm.

    aceptar_entero habilita el ultimo recurso de leer un entero suelto como
    pulgadas (ver entero_pelado_como_pulgada); solo se usa en las familias
    donde la medida es obligatoria."""
    candidatas = []
    for t in textos:
        candidatas.extend(parsear_medidas(t))
    if not candidatas:
        if not aceptar_entero:
            return None
        return medida_metrica_por_convencion(textos) or entero_pelado_como_pulgada(textos)
    pulg = [c for c in candidatas if c.unidad == 'plg']
    if pulg:
        return max(pulg, key=lambda c: (len(c.componentes), c.principal))
    return candidatas[0]


def medida_canonica(*textos, aceptar_entero=False):
    m = medida_principal(*textos, aceptar_entero=aceptar_entero)
    return m.canonico() if m else None


# ============ 1b. NORMALIZACION Y 3-4. CLASIFICACION ============

# Tres ayudantes de texto que usan los dos motores de atributos (atributos.py
# y dimensiones.py). Viven aca, en la capa de normalizacion, para que ninguno
# de los dos dependa del otro.

# "p/", "c/" y "s/" son "para", "con" y "sin" (el catalogo los usa todo el
# tiempo). Se expanden antes que nada: son los marcadores que deciden el ROL
# de un material ("disco p/metal" -> aplicacion).
_BARRA_PREPOSICION = re.compile(r'\b([pcs])\s*/\s*(?=[a-z0-9])', re.I)
_PREPOSICION = {'p': 'para ', 'c': 'con ', 's': 'sin '}
_COMILLAS_TIPOGRAFICAS = {'“': '"', '”': '"', '″': '"', '´´': '"',
                          '′′': '"', "''": '"'}


def preposiciones(texto):
    return _BARRA_PREPOSICION.sub(lambda m: _PREPOSICION[m.group(1).lower()], str(texto or ''))


def unificar_comillas(texto):
    """Todas las formas de escribir la pulgada llevan a la misma comilla. El
    apostrofe despues de una fraccion tambien es pulgada en este catalogo
    ("1/4' HI NPT"), nunca un pie."""
    t = str(texto or '')
    for origen, destino in _COMILLAS_TIPOGRAFICAS.items():
        t = t.replace(origen, destino)
    return re.sub(r"(\d/\d{1,2})'(?!')", r'\1"', t)


def texto_plano(texto):
    """Minusculas, sin tildes, con las preposiciones abreviadas expandidas y
    el decimal con punto: la forma en que las expresiones regulares de
    atributos y dimensiones leen una descripcion."""
    t = sin_tildes(unificar_comillas(preposiciones(texto))).lower()
    return re.sub(r'(?<=\d),(?=\d)', '.', t)


NEGADORES = {'sin', 's', 'no', 'excepto', 'salvo'}


# Las 4 funciones de normalizacion son puras (str -> str) y se llaman sobre
# un universo chico y repetido: los terminos del catalogo (constantes) y los
# nombres/descripciones de los items (se repiten mucho, es el mismo producto
# comprado varias veces). Sin cache, clasificar el catalogo completo llamaba
# a normalizar() 2.116.803 veces para 1.374 items -- ~1.540 veces por item,
# re-normalizando una y otra vez las MISMAS constantes del catalogo desde
# _posiciones(). Memoizarlas es lo que baja reajustar_todos de ~6,7s a
# decimas. maxsize=None es seguro: el universo de claves esta acotado por el
# catalogo mas los items de una corrida.
@lru_cache(maxsize=None)
def sin_tildes(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s or '')) if unicodedata.category(c) != 'Mn')


@lru_cache(maxsize=None)
def normalizar(s):
    s = sin_tildes(s).lower()
    s = re.sub(r'[^a-z0-9ñ]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


@lru_cache(maxsize=None)
def singular(p):
    """Raiz para comparar: quita el plural y la 'e' final.

    El espanol no permite deducir el singular desde el plural sin lexico
    ('guantes'->guante pero 'tapones'->tapon, ambos con consonante antes de
    '-es'), asi que no se intenta: se lleva ambas formas a la misma raiz
    ('guante'/'guantes' -> 'guant', 'tapon'/'tapones' -> 'tapon').
    """
    if len(p) <= 3:
        return p
    if p.endswith('ces'):
        p = p[:-3] + 'z'
    elif p.endswith('s'):
        p = p[:-1]
    if len(p) > 3 and p.endswith('e'):
        p = p[:-1]
    return p


# Palabras vacias: se descartan antes de comparar, para que "tapon para
# oido" y "tapon oido" sean la misma secuencia, y una regla escrita como
# "valvula de bola" matchee tambien "valvula bola". Los negadores (sin, s/,
# no) NO son palabras vacias: se necesitan para descartar un match ("soplete
# s/abrazadera" no es un fitting).
VACIAS = {'de', 'del', 'la', 'el', 'los', 'las', 'lo', 'y', 'o', 'con', 'para',
          'por', 'a', 'al', 'en', 'un', 'una', 'unos', 'unas', 'su'}


@lru_cache(maxsize=None)
def n_palabras(termino):
    """Cantidad de palabras del termino ANTES de descartar las vacias -- es el
    peso que usa el score de clasificar(), y no coincide con len(lemas(t))."""
    return len(normalizar(termino).split())


def _negado(lemas_texto, pos):
    return pos > 0 and lemas_texto[pos - 1] in NEGADORES


# ---------------------------------------------------------------------------
# 3. QUE ES EL PRODUCTO
# ---------------------------------------------------------------------------
# El puntaje de una regla, en orden de importancia:
#
#   100 + prioridad de la regla
#       + 30 si calzo en el Nombre Item (no en la descripcion)
#       + 10 por palabra del termino     (mas especifico, mas puntaje)
#       + hasta 12 por estar al PRINCIPIO del nombre
#       - 25 si viene despues de "con", "incluye" o "porta"
#
# Las dos ultimas son de 2026-09-22 y son las que hacen que mande el
# sustantivo principal: en espanol el nucleo del sintagma va primero
# ("Válvula de bola de bronce"), y lo que sigue a "con" es un componente.
# Sin ellas, "Kit bomba DAB ... union 1.1/4\"" se clasificaba como Union y
# "Bolsas basura c/amarra" como Amarra.
BONO_NOMBRE = 30
BONO_POSICION = (12, 8, 4)
CASTIGO_COMPLEMENTO = 25
MARGEN_AMBIGUA = 10


@lru_cache(maxsize=None)
def _terminos_compilados():
    """{primer lema: [(lemas del termino, n palabras, indice de regla, termino)]}."""
    indice = {}
    for i, (terminos, _cat, _sub, _tipo, _extra) in enumerate(REGLAS):
        for termino in terminos:
            lem = atributos.lemas_de_frase(termino)
            if not lem:
                continue
            indice.setdefault(lem[0], []).append((lem, n_palabras(termino), i, termino))
    return indice


@lru_cache(maxsize=None)
def _frases_no_producto():
    return tuple(atributos.lemas_de_frase(f) for f in NO_PRODUCTO)


def _candidatos(texto, campo):
    """Todas las reglas que calzan en un texto, con su puntaje.

    Devuelve dicts con el puntaje ya calculado y el porque: en que campo
    calzo, en que posicion del nombre y si venia detras de un complemento.
    """
    if not texto:
        return []
    lem, idx = atributos.secuencia(texto)
    if not lem:
        return []
    pal = atributos.palabras(texto)
    indice = _terminos_compilados()

    # posicion "de sintagma": las palabras de envase (kit, set, pack) y los
    # numeros no cuentan, asi que en "Kit bomba DAB" la bomba esta primera.
    posicion, n = {}, 0
    for i, lema in enumerate(lem):
        crudo = pal[idx[i]]
        siguiente = pal[idx[i] + 1] if idx[i] + 1 < len(pal) else ''
        envase = crudo in ENVASES or (crudo in ENVASES_CON_DE and siguiente in ('de', 'del'))
        posicion[i] = n
        if not envase and crudo.isalpha():
            n += 1

    vetados = set()
    for frase in _frases_no_producto():
        k = len(frase)
        for p in range(len(lem) - k + 1):
            if lem[p:p + k] == frase:
                vetados.update(range(p, p + k))

    # desde donde empieza un complemento ("con", "incluye", "porta")
    complemento_desde = None
    for i, crudo in enumerate(pal):
        if crudo in MARCADORES_COMPONENTE:
            complemento_desde = i
            break

    salida = []
    for p, lema in enumerate(lem):
        if p in vetados:
            continue
        for term_lem, npal, regla, termino in indice.get(lema, ()):
            k = len(term_lem)
            if lem[p:p + k] != term_lem or _negado(lem, p):
                continue
            complemento = complemento_desde is not None and idx[p] > complemento_desde
            _t, cat, sub, tipo, extra = REGLAS[regla]
            score = (100 + extra + (BONO_NOMBRE if campo == 'nom' else 0) + 10 * npal
                     + (BONO_POSICION[posicion[p]] if posicion[p] < len(BONO_POSICION) else 0)
                     - (CASTIGO_COMPLEMENTO if complemento else 0))
            salida.append({'score': score, 'regla': regla, 'termino': termino,
                           'lemas': frozenset(term_lem), 'campo': campo, 'pos': posicion[p],
                           'complemento': complemento, 'categoria': cat, 'subcategoria': sub,
                           'tipo': tipo})
    return salida


def _refinar(mejor, candidatos):
    """Un termino que CONTIENE al ganador lo reemplaza: si el nombre dice
    "Válvula" y la descripcion "Válvula bola Bugatti", el producto es una
    valvula de bola. Asi la palabra mas especifica manda aunque este en el
    campo de menos peso."""
    especificos = [c for c in candidatos
                   if not c['complemento'] and c['lemas'] > mejor['lemas']]
    if not especificos:
        return mejor, False
    elegido = max(especificos, key=lambda c: (len(c['lemas']), c['score']))
    return elegido, True


def _desambiguar(mejor, lemas_todo):
    """Los sustantivos genericos (adaptador, conector, manifold) cambian de
    familia segun el contexto: un adaptador "schuko" es electrico; uno con
    "broca", el porta sierra de un taladro."""
    reglas = DESAMBIGUACION.get(mejor['tipo'])
    if not reglas:
        return mejor, None
    presentes = set(lemas_todo)
    for marcadores, destino in reglas:
        if {singular(m) for m in marcadores} & presentes:
            cat, sub, tipo = destino
            nuevo = dict(mejor, categoria=cat, subcategoria=sub, tipo=tipo)
            return nuevo, 'contexto: ' + ', '.join(sorted({singular(m) for m in marcadores} & presentes))
    return mejor, None


def clasificar(nombre_item, descripcion):
    """La ficha completa de un producto.

    Primero QUE es (tipo y familia), despues DE QUE esta hecho (material),
    despues sus dimensiones -- cada una con su rol -- y sus especificaciones
    tecnicas. Devuelve ademas la confianza de cada paso y, cuando algo quedo
    en duda, el motivo para revisarlo.

    Las claves 'categoria', 'subcategoria', 'familia', 'material', 'medida',
    'score' y 'cotizable' se mantienen con el mismo significado que antes de
    2026-09-22 (la hoja, el dashboard y la consulta por consola las usan);
    'familia' es el TIPO de producto y 'familia_producto' el nivel de arriba.
    """
    nombre = nombre_item or ''
    desc = descripcion or ''
    motivos = []

    candidatos = _candidatos(nombre, 'nom') + _candidatos(desc, 'desc')
    lemas_todo = atributos.secuencia(nombre)[0] + atributos.secuencia(desc)[0]

    ambigua = False
    alternativa = None
    if candidatos:
        mejor = max(candidatos, key=lambda c: (c['score'], -c['regla']))
        confianza_tipo = _confianza_tipo(mejor)
        mejor, refinado = _refinar(mejor, candidatos)
        if refinado:
            confianza_tipo = max(confianza_tipo, 0.9 if mejor['campo'] == 'desc' else 0.95)
        mejor, motivo_contexto = _desambiguar(mejor, lemas_todo)
        if motivo_contexto:
            motivos.append(motivo_contexto)
            confianza_tipo = min(confianza_tipo, 0.9)
        # Ambiguedad: otra categoria a menos de MARGEN_AMBIGUA puntos.
        otras = [c for c in candidatos
                 if c['categoria'] != mejor['categoria'] and not c['lemas'] < mejor['lemas']]
        if otras:
            rival = max(otras, key=lambda c: c['score'])
            if mejor['score'] - rival['score'] < MARGEN_AMBIGUA:
                ambigua = True
                alternativa = {'categoria': rival['categoria'], 'tipo': rival['tipo'],
                               'termino': rival['termino']}
                confianza_tipo *= 0.85
                motivos.append('podría ser %s (%s)' % (rival['tipo'], rival['categoria']))
        cat, sub, tipo = mejor['categoria'], mejor['subcategoria'], mejor['tipo']
        score, termino = mejor['score'], mejor['termino']
    else:
        cat, sub, tipo = 'Sin Clasificar', 'Sin Clasificar', (nombre.strip() or 'Ítem')
        score, termino, confianza_tipo = 0, None, 0.0

    # Especificaciones primero: el "tipo L" de una caneria o el grado de un
    # perno ayudan a deducir el material.
    specs = atributos.especificaciones(nombre, desc, cat, tipo)
    mats = atributos.detectar_materiales(nombre, desc, cat, tipo, specs)
    material, sistema = mats['material'], mats['sistema']
    motivos.extend(mats['motivos'])

    # Una plancha de teflon, grafito o EPDM es una empaquetadura: ahi el
    # material define la familia, no la forma.
    redireccion = REDIRECCION_POR_MATERIAL.get(tipo)
    if redireccion and material in redireccion[0]:
        cat, sub, tipo = redireccion[1]
        motivos.append('familia por material: %s' % material)

    # Sin regla que calce pero con un material que casi siempre se compra en
    # una forma ("EPDM 3/16 x 1,5 MT"): se sugiere, con confianza baja.
    if cat == 'Sin Clasificar' and material in TIPO_POR_MATERIAL:
        cat, sub, tipo = TIPO_POR_MATERIAL[material]
        confianza_tipo = 0.6
        motivos.append('tipo deducido del material %s' % material)

    familia = FAMILIA_DE_SUBCATEGORIA.get(sub, sub)
    requiere_medida = cat in CATEGORIAS_CON_MEDIDA
    material_define = cat in CATEGORIAS_CON_MATERIAL

    dims, esquema = dimensiones.dimensiones(nombre, desc, tipo, familia, material, sistema,
                                          motivos, cat)
    legado = medida_principal(nombre, desc, aceptar_entero=cat in CATEGORIAS_ENTERO_ES_PULGADA)
    medida = dimensiones.medida_hoja(dims, esquema, legado.canonico() if legado else None)
    # La misma medida, escrita para leerla. Son dos campos y no uno porque
    # 'medida' es lo que el buscador compara ("20000mm" calza con "20 mt" del
    # texto de otra compra) y 'medida_texto' es lo que se muestra ("20 m").
    medida_texto = dimensiones.medida_hoja(
        dims, esquema, legado.presentable() if legado else None, presentable=True)
    terminacion, color = atributos.terminaciones(nombre, desc, cat)

    if cat in CATEGORIAS_SUBCATEGORIA_POR_MATERIAL:
        sub = sistema or material or SUBCATEGORIA_SIN_MATERIAL

    principal = _dim_principal(dims, esquema)
    confianza_dims = min([d['confianza'] for d in dims.values()] or [0.0])
    partes = [confianza_tipo]
    if material:
        partes.append(mats['confianza'])
    if dims:
        partes.append(confianza_dims)
    confianza = round(min(partes), 2) if partes else 0.0

    faltantes = []
    if material_define and not material:
        faltantes.append('material')
    if requiere_medida and not medida:
        faltantes.append('medida')
    if cat == 'Sin Clasificar':
        faltantes.append('tipo')

    usa_modelo = cat in CATEGORIAS_CON_MODELO
    titulo = titulo_modelo(nombre, desc, tipo) if usa_modelo else None
    return {
        'categoria': cat,
        'subcategoria': sub,
        # 'familia' es el TIPO del producto: se conserva el nombre de la clave
        # porque la hoja, el dashboard, el benchmark y la consulta por consola
        # la usan desde 2026-09-08.
        'familia': tipo,
        'tipo': tipo,
        'familia_producto': familia,
        'material': material,
        'material_base': mats['material_base'],
        'material_grado': mats['material_grado'],
        'sistema': sistema,
        'aplicacion': mats['aplicacion'],
        'materiales_secundarios': mats['secundarios'],
        'terminacion': terminacion,
        'color': color,
        'dimensiones': dims,
        'esquema': esquema,
        'especificaciones': specs,
        'medida': medida,
        'medida_texto': medida_texto,
        'medida_mm': principal['valor_mm'] if principal else None,
        'medidas_equivalentes': dimensiones.medidas_equivalentes(dims),
        'numeros': dimensiones.numeros_de_dimensiones(dims),
        'nombre_original': (nombre + (' — ' + desc if desc else '')).strip(),
        'nombre_normalizado': atributos.nombre_normalizado(nombre, desc),
        'score': score,
        'termino': termino,
        'titulo': titulo,
        'usa_modelo': usa_modelo,
        'cotizable': CATEGORIAS.get(cat, ('', True))[1],
        'secundaria': es_secundaria(cat),
        'requiere_medida': requiere_medida,
        'material_define': material_define,
        'confianza': confianza,
        'confianzas': {'tipo': round(confianza_tipo, 2),
                       'material': round(mats['confianza'], 2),
                       'dimensiones': round(confianza_dims, 2)},
        'ambigua': ambigua,
        'alternativa': alternativa,
        'faltantes': faltantes,
        'motivos_revision': motivos,
        'revisar': bool(confianza < 0.7 or ambigua or cat == 'Sin Clasificar'),
    }


def _confianza_tipo(mejor):
    if mejor['campo'] == 'nom':
        return 1.0 if mejor['pos'] == 0 else 0.9
    return 0.85 if mejor['pos'] == 0 else 0.75


_ROL_PRINCIPAL = {'lamina': 'espesor', 'malla': 'diametro', 'perfil': 'ancho', 'barra': 'diametro',
                  'madera': 'ancho', 'tuberia': 'diametro', 'fitting': 'diametro',
                  'perno': 'diametro', 'tuerca': 'diametro', 'tornillo': 'largo',
                  'remache': 'diametro', 'disco': 'diametro', 'electrodo': 'diametro',
                  'cinta': 'ancho', 'aislacion': 'espesor', 'instrumento': 'conexion',
                  'generico': 'medida'}


def _dim_principal(dims, esquema):
    rol = _ROL_PRINCIPAL.get(esquema, 'medida')
    if rol in dims:
        return dims[rol]
    for d in dims.values():
        return d
    return None


# ---------------------------------------------------------------------------
# 4. LA HOJA: LA UNIDAD DE COMPARACION DE PRECIOS
# ---------------------------------------------------------------------------

# Texto administrativo que no forma parte del nombre de un equipo: todo lo
# que sigue a estos marcadores se corta del titulo.
_CORTE_TITULO = re.compile(
    r'\s*[,.;(\-]?\s*\b(cod|cods|codigo|c[oó]d|c[oó]digo|factura|boleta|guia|gu[ií]a|doc|documento|'
    r'folio|pedido|neto|precio de lista|venta mayorista|venta exenta|ingreso|serie|sku|ean|'
    r'con descuento|c/descuento|marca)\b.*$', re.I)
_PARENTESIS_FINAL = re.compile(r'\s*\([^)]*\)\s*$')
# "R 24" y "R24" son el mismo modelo: se pegan para que no abran dos hojas.
_MODELO_SEPARADO = re.compile(r'\b([A-Z]{1,3})\s+(\d)')


def _limpiar_titulo(texto):
    t = ' '.join(str(texto or '').split())
    t = _CORTE_TITULO.sub('', t)
    for _ in range(2):
        t = _PARENTESIS_FINAL.sub('', t)
    return t.strip(' ,.;:-')


def titulo_modelo(nombre, descripcion, familia, limite=62):
    """El titulo de un equipo tiene que mostrar su modelo.

    Dos calderas de marcas distintas no son el mismo producto: en el catalogo
    real habia tres, de $1,0M a $4,2M, compartiendo una hoja llamada
    "Caldera". Elige entre el nombre del item y su descripcion el texto mas
    informativo que mencione la familia, y le saca la cola administrativa
    (codigos, folios, descuentos)."""
    candidatos = [_limpiar_titulo(nombre), _limpiar_titulo(descripcion)]
    raiz_familia = sin_tildes(str(familia or '').lower())[:6]
    con_familia = [t for t in candidatos if t and raiz_familia in sin_tildes(t.lower())]
    elegidos = con_familia or [t for t in candidatos if t]
    if not elegidos:
        return familia
    titulo = max(elegidos, key=len)
    titulo = _MODELO_SEPARADO.sub(r'\1\2', titulo)
    # El catalogo real trae la misma marca escrita de varias formas ("ANWO" y
    # "Anwo" en dos radiadores seguidos). El titulo es lo que se lee en el
    # listado, asi que va con la escritura del catalogo de marcas.
    titulo = presentacion.nombre_presentable(titulo)
    if len(titulo) > limite:
        titulo = titulo[:limite].rsplit(' ', 1)[0] + '…'
    return titulo[0].upper() + titulo[1:]


def es_secundaria(categoria):
    """Las categorias de importancia menor para cotizar (gastos de operacion
    y la cola de "Sin Clasificar") se muestran aparte, bajo el listado
    principal -- pedido del usuario 2026-09-09."""
    return categoria in CATEGORIAS_SECUNDARIAS


def clave_agrupacion(c):
    """La clave con la que se agrupan las compras: la hoja normalizada.

    Se separa del texto que se muestra porque el mismo producto puede venir
    escrito distinto ("Estanque R24 lts rojo 8 bar" y "Estanque R 24 LTS
    rojo 8 BAR" son el mismo estanque). La hoja se muestra tal cual se leyo;
    agrupar usa esta version sin tildes, sin mayusculas y sin espacios de
    mas."""
    clave = normalizar(clave_hoja(c))
    # "c/hilo amarillo" y "con hilo amarillo" son lo mismo: el catalogo
    # abrevia "con"/"sin" con "c/" y "s/" de forma inconsistente. Se
    # normaliza solo en la clave; el texto se muestra tal cual se escribio.
    return ' '.join('con' if t == 'c' else 'sin' if t == 's' else t for t in clave.split())


# Especificaciones que parten la hoja porque cambian el precio del mismo
# producto: una caneria de cobre tipo L y una tipo K valen distinto, igual
# que un fitting SCH 40 y uno SCH 80.
SPECS_EN_LA_HOJA = ('tipo_pared', 'schedule')


def clave_hoja(c, presentable=False):
    """La unidad de comparacion de precios: tipo + material + medida.
    Nunca mezcla un codo de 1/2 con uno de 2, ni cobre con bronce.

    Con presentable=True devuelve la MISMA hoja con la medida escrita para
    leerla ("Extension Electrica 20 m"). Son dos cadenas y no una porque la
    hoja tambien se indexa: escrita "3/4" x 1/2"" deja de calzar con la
    consulta "reduccion cobre 3/4 x 1/2", que el buscador junta en un solo
    termino "3/4x1/2" -- exactamente como esta escrita la hoja canonica.

    El material entra solo donde define el producto (ver
    CATEGORIAS_CON_MATERIAL): en una herramienta o un EPP suele ser un
    detalle del texto (el marco de aluminio de un visor) y partiria la hoja
    sin motivo."""
    if c.get('usa_modelo'):
        return c['titulo']
    partes = [c.get('tipo') or c['familia']]
    if c.get('sistema') and c.get('material_define'):
        partes.append(c['sistema'])
    if c['material'] and c.get('material_define'):
        partes.append('de ' + c['material'])
        if c.get('material_grado'):
            partes.append(c['material_grado'])
    for clave in SPECS_EN_LA_HOJA:
        valor = (c.get('especificaciones') or {}).get(clave)
        if valor and c.get('material_define'):
            partes.append(valor)
    medida = (c.get('medida_texto') or c['medida']) if presentable else c['medida']
    if medida:
        partes.append(medida)
    elif c['requiere_medida']:
        partes.append('(sin medida)')
    return ' '.join(partes)


# Los dos motores de atributos importan ESTE modulo (usan la gramatica de
# medidas y la normalizacion), asi que sus imports van al final: cuando
# Python llega aca taxonomia ya esta completo y no hay ciclo posible.
# Ninguno llama al otro durante la importacion.
#   atributos.py    -- de que esta hecho y como se describe el producto
#   dimensiones.py  -- cuanto mide, y que es cada numero
import atributos  # noqa: E402
import dimensiones  # noqa: E402
