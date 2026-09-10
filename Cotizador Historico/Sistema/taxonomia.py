# -*- coding: utf-8 -*-
"""
taxonomia.py -- clasifica cada item comprado en categoria > subcategoria >
hoja, y extrae su medida normalizada. Es el MOTOR; los datos (categorias,
materiales, reglas) viven en catalogo_taxonomia.py.

Lo consumen los dos caminos del modulo, para que la consulta por consola y
el dashboard web clasifiquen exactamente igual:
  - cotizador_historico.consultar_item  (CLI y conversacion)
  - Visualizador Web/build_visualizador.py  (dashboard, Chile y Peru)

Cuatro etapas independientes y testeables por separado:

  1. normalizar/raiz  -- texto comparable (sin tildes, sin plural)
  2. parsear_medidas  -- gramatica de medidas: "1.1/4 plg" -> 1.1/4"
  3. clasificar       -- categoria/subcategoria/familia por catalogo de reglas
  4. clave_hoja       -- familia + material + medida = la unidad de comparacion
                         de precios ("Codo de Bronce 1.1/4\"")

Por que existe (2026-09-08): antes esta logica vivia en JavaScript dentro de
Visualizador Web/template.html, duplicada y ya divergente entre Chile y Peru,
sin tests, y sin que la consulta por consola la usara. Ademas leia mal las
fracciones mixtas del catalogo chileno ("1.1/4" se leia "1/4"), asi que
promediaba en una sola hoja productos de tamanos distintos. Ver
docs/superpowers/specs/2026-09-08-taxonomia-cotizador-design.md.

REGLA DE ORO: ningun item se oculta. Si no se le puede extraer la medida, la
hoja queda marcada "(sin medida)" y el item sigue visible y contable -- el
sistema anterior descartaba 136 de 1193 compras (11,4%) sin avisar.
"""
import re
import unicodedata
from fractions import Fraction
from functools import lru_cache

from catalogo_taxonomia import (CATEGORIAS, CATEGORIAS_CON_MATERIAL, CATEGORIAS_CON_MEDIDA,
                                CATEGORIAS_CON_MODELO, CATEGORIAS_SECUNDARIAS,
                                CATEGORIAS_SUBCATEGORIA_POR_MATERIAL, MATERIALES, REGLAS,
                                SUBCATEGORIA_SIN_MATERIAL)


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


# Devuelve TUPLA (no lista) por dos motivos: es hashable, asi que la funcion
# se puede memoizar; y permite comparar rebanadas contra el termino ya
# lematizado sin construir una lista nueva en cada comparacion. Los llamadores
# solo leen, concatenan e indexan el resultado -- ninguno lo muta.
@lru_cache(maxsize=None)
def lemas(s):
    return tuple(singular(t) for t in normalizar(s).split() if t not in VACIAS)


@lru_cache(maxsize=None)
def n_palabras(termino):
    """Cantidad de palabras del termino ANTES de descartar las vacias -- es el
    peso que usa el score de clasificar(), y no coincide con len(lemas(t))."""
    return len(normalizar(termino).split())


def _posiciones(lemas_texto, termino):
    """Posiciones donde el termino (1..n palabras) aparece como secuencia
    completa de lemas. Match por palabra: 'tee' NO matchea dentro de
    'steelgen', y 'dado' no matchea 'dado que' porque se exige ademas que no
    venga negado."""
    # lemas() es exactamente la lematizacion que esta funcion hacia inline, y
    # ahora viene cacheada: el termino sale del catalogo, asi que se lematiza
    # una vez en toda la corrida y no una vez por item.
    pal = lemas(termino)
    if not pal:
        return []
    n = len(pal)
    return [i for i in range(len(lemas_texto) - n + 1)
            if lemas_texto[i:i + n] == pal]


def _negado(lemas_texto, pos):
    return pos > 0 and lemas_texto[pos - 1] in NEGADORES


def detectar_material(nombre, descripcion):
    lt = lemas(nombre) + lemas(descripcion)
    for terminos, canonico in MATERIALES:
        for t in terminos:
            for p in _posiciones(lt, t):
                if not _negado(lt, p):
                    return canonico
    return None


def clasificar(nombre_item, descripcion):
    """-> dict con categoria, subcategoria, familia, material, medida, score."""
    nombre = nombre_item or ''
    desc = descripcion or ''
    lem_nombre = lemas(nombre)
    lem_desc = lemas(desc)

    mejor = None
    for idx, (terminos, cat, sub, familia, extra) in enumerate(REGLAS):
        for termino in terminos:
            npal = n_palabras(termino)
            for lem, bono in ((lem_nombre, 30), (lem_desc, 0)):
                for p in _posiciones(lem, termino):
                    if _negado(lem, p):
                        continue
                    score = 100 + extra + bono + 10 * npal
                    if mejor is None or score > mejor[0]:
                        mejor = (score, cat, sub, familia, termino)
                    break

    material = detectar_material(nombre, desc)
    sub_forzada = False
    if mejor is None:
        cat, sub, familia, score, termino = 'Sin Clasificar', 'Sin Clasificar', (nombre.strip() or 'Ítem'), 0, None
    else:
        score, cat, sub, familia, termino = mejor

    # La categoria se resuelve ANTES de medir: solo las familias que
    # comparan por medida aceptan el entero pelado como pulgadas.
    requiere_medida = cat in CATEGORIAS_CON_MEDIDA
    medida = medida_principal(nombre, desc, aceptar_entero=requiere_medida)

    # En piping la subcategoria es el material, para poder distinguir de un
    # vistazo cobre de PPR o de PEX; el tipo de pieza sigue al frente del
    # nombre de la hoja.
    if cat in CATEGORIAS_SUBCATEGORIA_POR_MATERIAL and not sub_forzada:
        sub = material or SUBCATEGORIA_SIN_MATERIAL

    usa_modelo = cat in CATEGORIAS_CON_MODELO
    titulo = titulo_modelo(nombre, desc, familia) if usa_modelo else None
    return {
        'categoria': cat,
        'subcategoria': sub,
        'familia': familia,
        'material': material,
        'medida': medida.canonico() if medida else None,
        'medida_mm': medida.mm if medida else None,
        'score': score,
        'termino': termino,
        'titulo': titulo,
        'usa_modelo': usa_modelo,
        'cotizable': CATEGORIAS.get(cat, ('', True))[1],
        'secundaria': es_secundaria(cat),
        'requiere_medida': requiere_medida,
        'material_define': cat in CATEGORIAS_CON_MATERIAL,
    }


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


def clave_hoja(c):
    """La unidad de comparacion de precios: familia + material + medida.
    Nunca mezcla un codo de 1/2 con uno de 2, ni cobre con bronce.

    El material entra solo donde define el producto (ver
    CATEGORIAS_CON_MATERIAL): en una herramienta o un EPP suele ser un
    detalle del texto (el marco de aluminio de un visor) y partiria la hoja
    sin motivo."""
    if c.get('usa_modelo'):
        return c['titulo']
    partes = [c['familia']]
    if c['material'] and c.get('material_define'):
        partes.append('de ' + c['material'])
    if c['medida']:
        partes.append(c['medida'])
    elif c['requiere_medida']:
        partes.append('(sin medida)')
    return ' '.join(partes)
