# -*- coding: utf-8 -*-
"""
busqueda.py -- el buscador del Cotizador Historico: encuentra un item del
catalogo historico aunque quien lo busca no escriba lo mismo que decia la
factura. Es el MOTOR; los datos (sinonimos, marcas, pesos, equivalencias de
medida) viven en catalogo_busqueda.py.

Lo consumen los dos caminos del modulo, igual que taxonomia.py:
  - cotizador_historico.buscar_items / consultar_item  (CLI y conversacion)
  - Visualizador Web/busqueda.js, alimentado por el snapshot  (dashboard)

QUE PROBLEMA RESUELVE (medido sobre el catalogo real, 2026-09-15)

El buscador anterior puntuaba con una funcion que devolvia 1.0 en cuanto el
item compartia UNA palabra de >=4 letras con la consulta. Sobre los datos
reales eso significa que "Valvula de bola de 2\"" y "valvula" daban
exactamente el mismo resultado: 41 compras, todas con puntaje 1.0, ordenadas
por el orden en que estaban en el Excel. La valvula de 1/2" salia segunda y
la de 2" que se pidio podia salir decima. No habia ranking: habia un filtro
binario disfrazado de ranking.

COMO PUNTUA ESTE

  relevancia = (cobertura ponderada de los terminos) x (peso del campo donde
               calzo cada uno) x (multiplicador de medida)

Cuatro ideas, en orden de impacto:

1. COBERTURA. Un item que calza los 3 terminos de la consulta vale mucho mas
   que uno que calza 1. Los terminos se ponderan por IDF, asi que en
   "valvula bola 2" pesa mas "bola" (25 compras) que "valvula" (41), y mas
   que las dos la medida.
2. CAMPOS CON PESO. El mismo termino vale 10 en el Nombre Item, 9 en la hoja
   de la taxonomia, 4 en la descripcion y 2 en el proyecto. Un codigo exacto
   vale 12: si calza, es EL item.
3. MEDIDA COMO DIMENSION APARTE. La medida no es un termino mas: es un
   multiplicador. 2" contra 2" multiplica por 1,6; contra 1/2" por 0,18. Una
   medida distinta es OTRO producto, no un match mas debil.
4. TOLERANCIA. Tildes, mayusculas, plurales, palabras vacias, orden de las
   palabras y errores de tipeo se resuelven ANTES de puntuar, normalizando
   los dos lados con las mismas funciones que usa la taxonomia.

LO QUE NO HACE, A PROPOSITO

- No interpreta las comillas como operador de frase exacta. En este catalogo
  la comilla es la unidad de medida mas frecuente: 2" son dos pulgadas, no
  una frase. Soportar frases exactas aqui romperia la consulta mas comun del
  modulo.
- No convierte milimetros a pulgadas dividiendo por 25,4. Ver la nota de
  DN_A_PULGADA en catalogo_busqueda.py.
- No oculta nada. Lo que no calza la medida se hunde en el ranking, pero
  sigue estando (misma regla de oro que la taxonomia).
"""

import math
import re
import unicodedata
from bisect import bisect_left


import taxonomia
from catalogo_atributos import ABREVIATURAS
from catalogo_busqueda import (CALIDAD_DIFUSA, CALIDAD_EXACTA, CALIDAD_PREFIJO,
                               DN_A_PULGADA, FACTOR_NORMA_LARGO,
                               FRACCION_DEL_MEJOR, MARCAS,
                               MAX_ERRORES_POR_LARGO, MAX_SUGERENCIAS,
                               MULT_MEDIDA_AUSENTE, MULT_MEDIDA_DISTINTA,
                               MULT_MEDIDA_EXACTA, PESOS_CAMPO,
                               PISO_COBERTURA, PREFIJOS_DIAMETRO,
                               PULGADAS_NOMINALES, SINONIMOS, SUFIJOS_PULGADA,
                               UMBRAL_ABSOLUTO, UMBRAL_SUGERENCIA)

# Se reutilizan tal cual las de la taxonomia -- no hay una segunda lista de
# palabras vacias en el proyecto.
VACIAS = taxonomia.VACIAS

CAMPOS = ("cod", "tipo", "nom", "hoja", "mat", "dim", "esp", "term", "apl", "mar", "cat",
          "desc", "prov", "proy")


# ====================== 1. NORMALIZACION ======================

def _canonico_sinonimo():
    """{raiz_escrita_como_sea: raiz_canonica} a partir de SINONIMOS y de las
    abreviaturas del catalogo de atributos.

    Las abreviaturas ("galv", "cuad", "perf", "neg") estan escritas UNA vez,
    en catalogo_atributos.ABREVIATURAS, y las usan tanto la clasificacion
    como el buscador: si se agrega una abreviatura nueva, las dos la
    entienden."""
    mapa = {}
    for grupo in SINONIMOS:
        canonico = taxonomia.singular(taxonomia.normalizar(grupo[0]))
        for palabra in grupo:
            mapa[taxonomia.singular(taxonomia.normalizar(palabra))] = canonico
    for abreviatura, completa in ABREVIATURAS.items():
        if " " in completa:
            continue
        raiz_abreviatura = taxonomia.singular(taxonomia.normalizar(abreviatura))
        raiz_completa = taxonomia.singular(taxonomia.normalizar(completa))
        mapa.setdefault(raiz_abreviatura, mapa.get(raiz_completa, raiz_completa))
    return mapa


SINONIMO_DE = _canonico_sinonimo()


def raiz(palabra):
    """La forma con la que se compara una palabra: sin tildes, sin
    mayusculas, sin plural y con los sinonimos unificados.

    Es la misma raiz que usa la taxonomia (taxonomia.singular sobre
    taxonomia.normalizar) mas el paso de sinonimos, para que 'Valvulas',
    'valvula' y 'valv' sean la misma cosa que 'VALVULA'."""
    r = taxonomia.singular(taxonomia.normalizar(palabra))
    return SINONIMO_DE.get(r, r)


def terminos(texto):
    """Las raices significativas de un texto, en orden y sin repetir.

    Descarta las palabras vacias ('de', 'para', 'con'...) para que "valvula
    de bola" y "valvula bola" produzcan exactamente la misma lista -- de ahi
    sale la independencia del orden y de las palabras omitidas."""
    vistos = []
    for palabra in taxonomia.normalizar(texto).split():
        if palabra in VACIAS:
            continue
        r = raiz(palabra)
        if r and r not in vistos:
            vistos.append(r)
    return tuple(vistos)


# ====================== 2. MEDIDAS ======================

# Comillas tipograficas y el simbolo de diametro se llevan a su forma simple
# ANTES de cualquier otra cosa: son la diferencia entre 2" y 2 a secas.
_COMILLAS = {"“": '"', "”": '"', "″": '"', "´´": '"',
             "′′": '"', "''": '"'}
_DIAMETRO = re.compile(r"[Ø⌀∅]\s*")
_PATRON_DN_CONSULTA = re.compile(r"\bdn\s*(\d{1,4})\b", re.I)


def _unificar_comillas(texto):
    t = str(texto or "")
    for origen, destino in _COMILLAS.items():
        t = t.replace(origen, destino)
    return t


def _limpiar_para_medidas(texto):
    """Deja el texto en la forma que taxonomia.parsear_medidas entiende
    mejor: comillas unificadas y el simbolo de diametro fuera del camino
    (Ø2" -> 2", que el parser no reconocia porque Ø cuenta como caracter de
    palabra y bloqueaba su lookbehind)."""
    return _DIAMETRO.sub(" ", _unificar_comillas(texto))


def _pulgada_canonica(texto_fraccion):
    """'1.1/4' -> la forma canonica que usa la taxonomia para esa medida."""
    valor, _ = taxonomia.parsear_numero(texto_fraccion)
    if valor is None:
        return None
    return taxonomia.Medida([valor], "plg").canonico()


def _alias_de_pulgada(texto_fraccion):
    """Todas las escrituras validas de una medida en pulgadas."""
    formas = {texto_fraccion}
    if "." in texto_fraccion:                      # 1.1/4 -> 1-1/4, 1 1/4
        entero, frac = texto_fraccion.split(".", 1)
        formas.add("%s-%s" % (entero, frac))
        formas.add("%s %s" % (entero, frac))
    alias = set()
    for forma in formas:
        # Una FRACCION sin unidad ya es una medida sin ambiguedad posible:
        # "codo bronce 1.1/4" y "valvula 1/2" son la escritura normal del
        # catalogo chileno. Un ENTERO sin unidad no entra aca -- "pack 2
        # curva" son dos curvas, no una de 2 pulgadas -- y se resuelve
        # aparte, con guardas (ver _entero_suelto_como_pulgada).
        if "/" in forma:
            alias.add(forma)
        for sufijo in SUFIJOS_PULGADA:
            alias.add(forma + sufijo)
            for prefijo in PREFIJOS_DIAMETRO:
                alias.add(prefijo + forma + sufijo)
    return alias


def normalizar_alias(texto):
    """La clave con la que se busca un alias de medida: comillas unificadas,
    sin tildes, minusculas y sin espacios de mas. Deja pasar " / . - porque
    son parte de la medida.

    La coma decimal se convierte en punto ANTES de limpiar: si no, "0,8" se
    partia en "0" y "8" y una plancha de 0,8 mm se buscaba con dos numeros
    que no significan nada (uno de ellos encontraba el fierro de 8 mm)."""
    t = _unificar_comillas(texto).lower()
    t = "".join(c for c in unicodedata.normalize("NFD", t)
                if unicodedata.category(c) != "Mn")
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    t = _DIAMETRO.sub("", t)
    t = re.sub(r'[^a-z0-9"/.\- ]+', " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # "3/4 x 1/2" y "3/4x1/2" son la misma medida compuesta: el catalogo la
    # escribe pegada y la gente la escribe con espacios.
    return re.sub(r'(\d["]?)\s+x\s+(?=\d)', r"\1x", t)


def _construir_alias_medida(medidas_extra=()):
    """{alias_normalizado: medida_canonica} para las pulgadas nominales, los
    DN de la tabla y las medidas que efectivamente existan en el catalogo.

    Es LA tabla que el dashboard recibe en el snapshot: gracias a ella el
    JavaScript no necesita reimplementar la gramatica de medidas de
    taxonomia.py, solo mirar la tabla. Cada entrada se valida contra el
    parser real en tests/test_busqueda_medidas.py."""
    alias = {}

    def agregar(texto, canonico):
        clave = normalizar_alias(texto)
        if clave and clave not in alias:
            alias[clave] = canonico

    pulgadas = list(PULGADAS_NOMINALES)
    for medida in medidas_extra:
        m = re.fullmatch(r"(\d+(?:[.]\d+/\d+)?|\d+/\d+)\"", str(medida or ""))
        if m:
            pulgadas.append(m.group(1))

    for texto_frac in dict.fromkeys(pulgadas):
        canonico = _pulgada_canonica(texto_frac)
        if not canonico:
            continue
        for a in _alias_de_pulgada(texto_frac):
            agregar(a, canonico)

    # DN: la unica pasarela entre metrico y pulgadas, y solo escrita "DN".
    for dn, pulgada in DN_A_PULGADA.items():
        canonico = _pulgada_canonica(pulgada)
        if canonico:
            agregar("dn%d" % dn, canonico)
            agregar("dn %d" % dn, canonico)

    # Las medidas tal cual las escribio el catalogo, incluidas las compuestas
    # ("3/4x1/2\""), que no calzan con ningun patron simple. Se registran como
    # alias de si mismas para que la consulta las reconozca igual.
    for medida in medidas_extra:
        agregar(str(medida), str(medida))

    # Medidas metricas tal como las escribe el catalogo (PPR/PVC en mm).
    for medida in medidas_extra:
        m = re.fullmatch(r"(\d+(?:\.\d+)?)mm", str(medida or ""))
        if m:
            agregar("%smm" % m.group(1), str(medida))
            agregar("%s mm" % m.group(1), str(medida))
    for mm in (16, 20, 25, 32, 40, 50, 63, 75, 90, 110, 125, 160):
        agregar("%dmm" % mm, "%dmm" % mm)
        agregar("%d mm" % mm, "%dmm" % mm)
    return alias


ALIAS_MEDIDA = _construir_alias_medida()

# "2" -> '2"'. Tabla aparte de ALIAS_MEDIDA a proposito: un numero PELADO solo
# es una medida dentro de una consulta y con guardas (ver
# _entero_suelto_como_pulgada). Si estuviera en la tabla general, cualquier
# numero de cualquier texto se leeria como calibre.
# Es una tabla y no un calculo para que Python y el navegador lleguen
# exactamente al mismo texto canonico sin que el JavaScript tenga que saber
# convertir fracciones.
ALIAS_ENTERO = {str(n): _pulgada_canonica(str(n))
                for n in range(1, taxonomia.MAX_PULGADAS_NOMINAL + 1)}
_MAX_PALABRAS_ALIAS = 3


def _pulgada_de_dn(texto):
    """Las pulgadas nominales que nombra un texto escrito en DN.

    DN es la UNICA pasarela entre el mundo metrico y el de pulgadas que este
    buscador acepta, y va en un solo sentido: DN50 significa 2". No se hace
    el camino inverso (2" -> 50mm) ni se traduce un milimetro suelto,
    porque los milimetros de este catalogo son diametros EXTERIORES de PPR
    y PVC: un tubo PPR de 50mm es DN40 (1.1/2"), no DN50. Ligar 2" con
    "50mm" mezclaria calibres distintos, justo lo que la taxonomia evita al
    separar las hojas por medida."""
    salida = set()
    for m in _PATRON_DN_CONSULTA.finditer(_unificar_comillas(str(texto or ""))):
        pulgada = DN_A_PULGADA.get(int(m.group(1)))
        if pulgada:
            canonico = _pulgada_canonica(pulgada)
            if canonico:
                salida.add(canonico)
    return salida


def _entero_suelto_como_pulgada(palabras, porcentajes=()):
    """Un numero suelto en una CONSULTA es casi siempre el calibre.

    "valvula bola 2" es una valvula de dos pulgadas, no dos valvulas. Las
    tres guardas son las mismas que usa taxonomia.entero_pelado_como_pulgada
    y salen de sus mismas constantes: no pasa de 24 pulgadas nominales, no es
    un angulo de fitting ("codo 90"), y no viene despues de un cuantificador
    ("pack 2 curva" son dos curvas).

    La regla se escribe aqui, y no se reusa la de taxonomia, porque esta
    tiene que correr identica en el navegador: opera sobre la lista de
    palabras ya normalizada, sin la tuberia de limpieza de texto
    administrativo que taxonomia.texto_util necesita para leer una factura.
    Las CONSTANTES si se comparten -- si manana cambia el tope de pulgadas,
    cambia en un solo lugar."""
    for i, palabra in enumerate(palabras):
        if not re.fullmatch(r"\d{1,2}", palabra):
            continue
        valor = int(palabra)
        if valor < 1 or valor > taxonomia.MAX_PULGADAS_NOMINAL:
            continue
        if valor in taxonomia.ANGULOS_DE_FITTING:
            continue
        if i and palabras[i - 1] in taxonomia.CUANTIFICADORES:
            continue
        if palabra in porcentajes:
            continue
        canonico = ALIAS_ENTERO.get(palabra)
        return ({canonico} if canonico else set()), i
    return set(), None


def parsear_consulta(texto):
    """(terminos, medidas) de una consulta -- ver parsear_consulta_detalle."""
    d = parsear_consulta_detalle(texto)
    return d["terminos"], d["medidas"]


def parsear_consulta_detalle(texto):
    """Todo lo que se puede leer de lo que alguien escribio:

        {terminos, medidas, blandas}

    Las medidas se leen PRIMERO y las palabras que las escribian se sacan
    del texto antes de sacar los terminos: sin eso, "valvula 2 pulgadas"
    dejaba 'pulgada' como un termino mas, que ningun item cumple (los items
    dicen 2", no "2 pulgadas") y que por lo tanto hundia la cobertura de la
    consulta correcta.

    Lo que queda despues de las medidas tambien se mira: los NUMEROS pasan a
    ser terminos del campo de dimensiones ("plancha policarbonato 0.7"), los
    grados de material se parten en material + numero ("SS316" -> inoxidable
    + 316) y las especificaciones se pegan ("sch 40" -> sch40). Antes todo
    numero que no fuera una pulgada se descartaba, asi que "plancha 0.7",
    "policarbonato 812" y "electrodo 6011" buscaban solo por la palabra."""
    medidas = set()
    palabras = normalizar_alias(texto).split()
    palabras = _unir_especificaciones(palabras)
    usadas = set()
    i = 0
    while i < len(palabras):
        for largo in range(min(_MAX_PALABRAS_ALIAS, len(palabras) - i), 0, -1):
            canonico = ALIAS_MEDIDA.get(" ".join(palabras[i:i + largo]))
            if canonico:
                medidas.add(canonico)
                usadas.update(range(i, i + largo))
                i += largo
                break
        else:
            i += 1

    medidas |= _pulgada_de_dn(texto)

    # Un numero con signo de porcentaje no es una medida: "soldadura plata
    # 15%" es la ley de la plata, no quince pulgadas. El % se pierde al
    # normalizar, asi que se lee del texto tal cual lo escribieron.
    porcentajes = set(re.findall(r"(\d{1,3})\s*%", str(texto or "")))
    blandas = set()
    if not medidas:
        sueltas, indice = _entero_suelto_como_pulgada(palabras, porcentajes)
        medidas |= sueltas
        if indice is not None:
            # La palabra que escribia la medida se saca del texto igual que
            # cuando viene con unidad: si no, "valvula bola 2" sumaba ademas
            # el termino numerico #2 y devolvia un conjunto distinto al de
            # 'valvula bola 2"', que es la misma consulta.
            usadas.add(indice)
        # Un entero suelto es una lectura POSIBLE de la medida, no una
        # certeza: "plancha 4" son 4 mm de espesor y "valvula 4" son 4
        # pulgadas. Se marca blanda para que un item cuyo 4 es una dimension
        # en milimetros no quede hundido como si fuera de otro calibre.
        for canonico in sueltas:
            blandas.add(canonico.rstrip('"'))

    resto = " ".join(p for i, p in enumerate(palabras) if i not in usadas)
    terms = [t for t in terminos(resto) if not t.isdigit()]
    terms.extend(t for t in _terminos_numericos(resto) if t not in terms)

    # Un codigo se escribe con separadores ("JUNJ-101", "Cod. HER3709") pero
    # se indexa pegado. Sin este termino extra, "JUNJ-101" se partia en
    # 'junj' + '101', el '101' se descartaba por numerico y 'junj' calzaba
    # por prefijo con los 386 items de todos los documentos JUNJ-*.
    #
    # Se pega PALABRA POR PALABRA, no la consulta entera: pegarla entera
    # convertia "valvula 2 pulgadas" en el codigo 'valvula2pulgadas', un
    # termino que ningun item cumple y que, por ser unico, entraba al
    # denominador de la cobertura con el peso mas alto posible y hundia el
    # puntaje de los resultados correctos.
    # Una palabra que YA se leyo como medida no vuelve a entrar como codigo:
    # "dn50" es dos pulgadas, no un modelo. Si entrara como termino ademas,
    # sumaria al denominador de la cobertura un termino que ningun item
    # cumple y "valvula de bola dn50" devolveria algo distinto a
    # 'valvula de bola 2"'.
    for i, palabra in enumerate(palabras):
        if i in usadas:
            continue
        pegado = re.sub(r"[^a-z0-9]", "", palabra)
        if _TOKEN_CODIGO.match(pegado) and pegado not in terms:
            terms.append(pegado)
    return {"terminos": tuple(terms), "medidas": medidas, "blandas": blandas}


# ---- numeros, grados y especificaciones de la consulta ----

# "sch 40" -> sch40, "pn 16" -> pn16, "clase 150" -> clase150: el catalogo
# los escribe pegados y asi se indexan.
_PREFIJOS_SPEC = ("sch", "sched", "schedule", "cedula", "ced", "pn", "clase", "serie", "grado",
                  "gr", "g")
_CANONICO_SPEC = {"sched": "sch", "schedule": "sch", "cedula": "sch", "ced": "sch",
                  "grado": "g", "gr": "g"}
# Prefijos con que se escribe un grado de acero inoxidable pegado al numero.
_PREFIJOS_GRADO = ("ss", "aisi", "inox", "sus", "tp")
_NUMERO_CONSULTA = re.compile(r"^(\d+(?:[.,]\d+)?)(mm|cm|mts|mt|m|plg|pulg|pulgadas?|in)?$")


def _unir_especificaciones(palabras):
    salida = []
    i = 0
    while i < len(palabras):
        p = palabras[i]
        siguiente = palabras[i + 1] if i + 1 < len(palabras) else ""
        if p in _PREFIJOS_SPEC and re.fullmatch(r"\d{1,4}s?", siguiente):
            salida.append(_CANONICO_SPEC.get(p, p) + siguiente)
            i += 2
            continue
        salida.append(p)
        i += 1
    return salida


def _terminos_numericos(texto):
    """Los numeros de una consulta, en la forma en que estan indexados:

        "0,7"     -> #0.7       (el espesor de una plancha)
        "812 mm"  -> #812
        "5.8m"    -> #5800 y #5.8   (el catalogo escribe las dos)
        "40x20x2" -> #40 #20 #2
        "ss316"   -> inoxidable y #316
        "m12"     -> #12
    """
    salida = []

    def agregar(valor):
        for v in ("#" + _texto_numero(valor),):
            if v not in salida:
                salida.append(v)

    for palabra in texto.split():
        m = re.fullmatch(r"(%s)[\s-]*(\d{3})(l|h)?" % "|".join(_PREFIJOS_GRADO), palabra)
        if m:
            for t in (raiz(m.group(1)), "#" + m.group(2)):
                if t not in salida:
                    salida.append(t)
            if m.group(3):
                salida.append(m.group(2) + m.group(3))
            continue
        m = re.fullmatch(r"m(\d{1,2})", palabra)          # rosca metrica M12
        if m:
            agregar(m.group(1))
            continue
        for trozo in re.split(r"[x×]", palabra):
            m = _NUMERO_CONSULTA.match(trozo)
            if not m:
                continue
            valor = float(m.group(1).replace(",", "."))
            unidad = m.group(2)
            if unidad in ("m", "mt", "mts"):
                agregar(valor * 1000)
                agregar(valor)
            elif unidad == "cm":
                agregar(valor * 10)
            else:
                agregar(valor)
    return salida


def _texto_numero(valor):
    """Un numero en la forma canonica con que se indexa: sin ceros de mas
    ("0.70" y "0,7" son el mismo espesor; "032" y "32", el mismo tubo)."""
    return ("%g" % float(valor))


def medidas_de_consulta(texto):
    """Solo las medidas de una consulta (ver parsear_consulta)."""
    return parsear_consulta(texto)[1]


def medidas_de_item(nombre, descripcion, medida_taxonomia=None, equivalentes=()):
    """TODAS las medidas que menciona un item, no solo la que la taxonomia
    eligio como principal.

    La taxonomia se queda con una sola medida porque necesita una clave de
    hoja estable; el buscador se queda con todas porque quien busca
    "termopozo 1/2 NPT" o "coquilla 54mm" esta nombrando una medida que
    igual esta escrita ahi."""
    encontradas = set()
    for texto in (nombre, descripcion):
        if not texto:
            continue
        for m in taxonomia.parsear_medidas(_limpiar_para_medidas(texto)):
            encontradas.add(m.canonico())
        encontradas |= _pulgada_de_dn(texto)
    if medida_taxonomia:
        encontradas.add(medida_taxonomia)
    # Las medidas que la ficha ya resolvio con su rol (diametro, espesor,
    # largo) y sus equivalencias de familia: un disco de 4.1/2" tambien se
    # busca como "115mm", y un electrodo de 1/8" como "3.2mm".
    encontradas.update(m for m in equivalentes if m)
    return sorted(encontradas)


# ====================== 3. TERMINOS DEL DOCUMENTO ======================

_MARCA_POR_RAIZ = {raiz(m): m for m in MARCAS}
_TOKEN_CODIGO = re.compile(r"^(?=.*\d)[a-z0-9]{4,}$")


def detectar_marca(nombre, descripcion):
    """La marca del item, si es una de las de la lista curada. None si no.

    Nunca adivina: la heuristica anterior ("primera palabra capitalizada")
    devolvia cosas como 'Precio' o 'Cod'."""
    for palabra in taxonomia.normalizar((nombre or "") + " " + (descripcion or "")).split():
        marca = _MARCA_POR_RAIZ.get(raiz(palabra))
        if marca:
            return marca
    return None


def _codigos(item):
    """Codigos con los que alguien podria buscar este item exacto: el N Ref.
    del documento y los codigos/modelos alfanumericos del texto."""
    salida = []
    n_ref = str(item.get("n_ref") or "")
    if n_ref:
        salida.append(taxonomia.normalizar(n_ref).replace(" ", ""))
        salida.extend(taxonomia.normalizar(n_ref).split())
    texto = (item.get("nombre_item") or "") + " " + (item.get("descripcion") or "")
    for palabra in taxonomia.normalizar(texto).split():
        if _TOKEN_CODIGO.match(palabra) and normalizar_alias(palabra) not in ALIAS_MEDIDA:
            salida.append(palabra)
    return salida


# Los campos de la ficha que el buscador indexa. Un item que viene del
# dashboard ya los trae (agregar_taxonomia los copia a la compra); uno que
# viene directo del Excel se clasifica aqui.
_CAMPOS_FICHA = ("familia", "tipo", "familia_producto", "material", "material_base",
                 "material_grado", "sistema", "aplicacion", "terminacion", "color",
                 "especificaciones", "numeros", "medidas_equivalentes", "medida",
                 "medida_texto", "categoria", "subcategoria")


def con_ficha(item):
    """El item con su ficha de atributos. Si ya la trae (camino del
    dashboard), se devuelve tal cual; si no (camino del CLI, que lee el Excel
    directo), se clasifica.

    Sin esto, buscar "valvula de bola" desde la consola no podria usar el
    nombre canonico del producto, que es el campo que hace que una compra
    registrada como "Valvula" a secas igual aparezca."""
    if item.get("hoja"):
        return item
    clasif = taxonomia.clasificar(item.get("nombre_item"), item.get("descripcion"))
    return dict(item, hoja=taxonomia.clave_hoja(clasif),
                **{c: clasif[c] for c in _CAMPOS_FICHA})


def terminos_documento(item):
    """{campo: "raices separadas por espacio"} -- lo que se indexa de un item.

    Un campo por ATRIBUTO, no un saco de palabras: el tipo de producto, el
    material (con su familia de material y su grado), las dimensiones, las
    especificaciones tecnicas, la terminacion y para que sirve. Asi el peso
    de cada campo puede seguir la prioridad que pidio el usuario -- tipo,
    material, medida, otras dimensiones, especificaciones, terminacion,
    marca y recien despues el texto libre.

    Este dict es exactamente lo que build_visualizador.py embebe en el
    snapshot, para que el JavaScript del dashboard NO tenga que derivar los
    terminos por su cuenta. El lado del documento se calcula una sola vez,
    en Python; el navegador solo procesa la consulta."""
    item = con_ficha(item)
    nombre = item.get("nombre_item") or ""
    desc = item.get("descripcion") or ""
    hoja = item.get("hoja") or ""
    tipo = item.get("tipo") or item.get("familia") or ""
    marca = item.get("marca") or detectar_marca(nombre, desc)
    specs = item.get("especificaciones") or {}
    terminacion = item.get("terminacion") or []
    if isinstance(terminacion, str):
        terminacion = [terminacion]

    campos = {
        "cod": " ".join(dict.fromkeys(_codigos(item))),
        "tipo": " ".join(terminos(tipo + " " + (item.get("familia_producto") or ""))),
        "nom": " ".join(terminos(nombre)),
        "hoja": " ".join(terminos(hoja)),
        "mat": " ".join(dict.fromkeys(
            list(terminos(" ".join(x for x in (item.get("material"), item.get("material_base"),
                                               item.get("sistema")) if x)))
            + _terminos_grado(item.get("material_grado")))),
        "dim": " ".join("#" + n for n in (item.get("numeros") or [])),
        "esp": " ".join(dict.fromkeys(_terminos_especificaciones(specs))),
        "term": " ".join(terminos(" ".join(terminacion + ([item.get("color")] if item.get("color") else [])))),
        "apl": " ".join(terminos(item.get("aplicacion") or "")),
        "mar": " ".join(terminos(marca or "")),
        "cat": " ".join(terminos((item.get("categoria") or "") + " " +
                                 (item.get("subcategoria") or ""))),
        "desc": " ".join(terminos(desc)),
        "prov": " ".join(terminos(item.get("proveedor_tag") or "")),
        "proy": " ".join(terminos(item.get("proyecto") or "")),
    }
    return {c: v for c, v in campos.items() if v}


def _terminos_grado(grado):
    """'AISI 316L' -> ['aisi', '316l', '#316'] : quien busca escribe
    cualquiera de las tres (y "SS316" se parte igual del lado de la
    consulta)."""
    if not grado:
        return []
    salida = list(terminos(grado))
    for m in re.finditer(r"(\d{2,4})([a-z])?", grado.lower()):
        salida.append("#" + m.group(1))
        if m.group(2):
            salida.append(m.group(1) + m.group(2))
    return salida


def _terminos_especificaciones(specs):
    """Las especificaciones como se escriben: 'SCH 40' -> sch40 y #40;
    'HI-HI' -> hi; 'PN16' -> pn16 y #16."""
    salida = []
    for valor in specs.values():
        texto = str(valor).lower()
        for parte in re.split(r"[\s\-/]+", texto):
            pegado = re.sub(r"[^a-z0-9]", "", parte)
            if pegado and pegado not in salida:
                salida.append(pegado)
        pegado_total = re.sub(r"[^a-z0-9]", "", texto)
        if pegado_total and pegado_total not in salida:
            salida.append(pegado_total)
        for numero in re.findall(r"\d+(?:\.\d+)?", texto):
            t = "#" + ("%g" % float(numero))
            if t not in salida:
                salida.append(t)
    return salida


# ====================== 4. DISTANCIA DE EDICION ======================

def max_errores(largo):
    for minimo, maximo, errores in MAX_ERRORES_POR_LARGO:
        if minimo <= largo <= maximo:
            return errores
    return 0


def distancia_acotada(a, b, maximo):
    """Levenshtein que abandona apenas supera 'maximo'. Acotarla no es solo
    velocidad: es lo que evita que 'codo' se confunda con 'cono' cuando el
    presupuesto de errores es 0."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > maximo:
        return maximo + 1
    anterior = list(range(lb + 1))
    for i in range(1, la + 1):
        actual = [i] + [0] * lb
        mejor_fila = actual[0]
        ca = a[i - 1]
        for j in range(1, lb + 1):
            costo = 0 if ca == b[j - 1] else 1
            actual[j] = min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + costo)
            if actual[j] < mejor_fila:
                mejor_fila = actual[j]
        if mejor_fila > maximo:
            return maximo + 1
        anterior = actual
    return anterior[lb]


# ====================== 5. INDICE Y BUSQUEDA ======================

def _norma_largo(n_palabras):
    """Cuanto se descuenta por calzar dentro de un campo largo.

    Que "teflon" aparezca en un nombre que dice solo "Teflon" es mas
    informativo que verlo dentro de "Soplete gas c/certif. fric. c/2
    boquillas s/manguera". Sin este descuento, los dos empatan y el desempate
    queda al azar: sobre el catalogo real eso hacia que 'manometro' abriera
    con "Alimat 1/2\" con manometro intermedio" -- una valvula -- en vez de
    con los manometros.

    El descuento es suave a proposito (un nombre de 8 palabras conserva la
    mitad del peso): los Nombre Item de este catalogo vienen sin simplificar
    y castigarlos fuerte esconderia productos reales."""
    return 1.0 / (1.0 + FACTOR_NORMA_LARGO * max(0, n_palabras - 1))

class Indice(object):
    """Indice invertido en memoria sobre una lista de items ya clasificados.

    Se construye una vez (por corrida del CLI, o por carga del dashboard) y
    responde muchas consultas. No guarda los items: guarda sus posiciones,
    asi que el llamador sigue siendo el dueno de la lista."""

    __slots__ = ("items", "post", "df", "vocab", "vocab_ordenado", "vocab_por_largo",
                 "medidas", "numeros", "n", "largo", "_cache_expansion")

    def __init__(self, items, terminos_por_item=None, medidas_por_item=None):
        self.items = items
        self.n = len(items)
        self.post = {c: {} for c in CAMPOS}
        self.df = {}
        self.medidas = []
        self.numeros = []
        self.largo = {c: {} for c in CAMPOS}

        for idx, item_crudo in enumerate(items):
            # La ficha se resuelve UNA vez por item: la usan los terminos y
            # las medidas. self.items conserva los dicts originales (el
            # llamador sigue siendo su dueno).
            item = item_crudo if terminos_por_item is not None else con_ficha(item_crudo)
            campos = (terminos_por_item[idx] if terminos_por_item is not None
                      else terminos_documento(item))
            self.numeros.append(set(campos.get("dim", "").split()))
            del_item = set()
            for campo, texto in campos.items():
                if campo not in self.post:
                    continue
                palabras = texto.split()
                self.largo[campo][idx] = len(palabras)
                for termino in palabras:
                    self.post[campo].setdefault(termino, set()).add(idx)
                    del_item.add(termino)
            for termino in del_item:
                self.df[termino] = self.df.get(termino, 0) + 1

            if medidas_por_item is not None:
                self.medidas.append(set(medidas_por_item[idx]))
            else:
                self.medidas.append(set(medidas_de_item(
                    item.get("nombre_item"), item.get("descripcion"), item.get("medida"),
                    item.get("medidas_equivalentes") or ())))

        self.vocab = self.df
        self.vocab_ordenado = sorted(self.df)
        # Buckets por largo: la busqueda difusa solo puede calzar terminos
        # cuyo largo este dentro del presupuesto de errores, asi que recorrer
        # el vocabulario entero por cada termino es trabajo tirado.
        self.vocab_por_largo = {}
        for termino in self.vocab_ordenado:
            self.vocab_por_largo.setdefault(len(termino), []).append(termino)
        self._cache_expansion = {}

    def _numeros(self, idx):
        """Los numeros de las dimensiones de un item, como estan indexados
        ('#0.7', '#812'). Salen del mismo campo que se puntua, asi que no hay
        una segunda estructura que mantener."""
        return self.numeros[idx]

    # ---- expansion de un termino de consulta ----

    def _por_prefijo(self, termino):
        if len(termino) < 3:
            return []
        i = bisect_left(self.vocab_ordenado, termino)
        salida = []
        while i < len(self.vocab_ordenado) and self.vocab_ordenado[i].startswith(termino):
            salida.append(self.vocab_ordenado[i])
            i += 1
        return salida

    def _por_distancia(self, termino):
        tope = max_errores(len(termino))
        if not tope:
            return []
        salida = []
        for largo in range(len(termino) - tope, len(termino) + tope + 1):
            for candidato in self.vocab_por_largo.get(largo, ()):
                if distancia_acotada(termino, candidato, tope) <= tope:
                    salida.append(candidato)
        return salida

    def expandir(self, termino):
        """{termino_del_indice: calidad} -- las formas del indice que este
        termino de consulta acepta, de la mejor a la peor. Exacto gana a
        prefijo, y prefijo gana a tipeo mal escrito.

        La expansion difusa solo corre cuando el termino NO existe tal cual
        en el indice. Si existe, ya esta bien escrito: buscarle vecinos a un
        error de tipeo que no ocurrio cuesta casi toda la latencia de la
        consulta y solo agrega ruido ('codo' traeria 'cono', 'copa', 'coda')."""
        cacheada = self._cache_expansion.get(termino)
        if cacheada is not None:
            return cacheada
        expansion = {}
        exacto = termino in self.vocab
        if exacto:
            expansion[termino] = CALIDAD_EXACTA
        for candidato in self._por_prefijo(termino):
            expansion.setdefault(candidato, CALIDAD_PREFIJO)
        if not exacto:
            for candidato in self._por_distancia(termino):
                expansion.setdefault(candidato, CALIDAD_DIFUSA)
        self._cache_expansion[termino] = expansion
        return expansion

    def terminos_sin_resultado(self, texto):
        """Los terminos de la consulta que el catalogo no conoce en absoluto.

        Una consulta se puede cumplir a medias: 'valvula de compuerta' en un
        catalogo sin valvulas de compuerta igual devuelve las de bola, y eso
        es preferible a una pantalla vacia. Pero hay que DECIRLO -- si no, el
        usuario cree que la de bola es lo que pidio. El dashboard lo muestra
        como 'no encontramos "compuerta"' sobre los resultados."""
        terms, _medidas = parsear_consulta(texto)
        return tuple(t for t in terms if not self.expandir(t))

    def idf(self, termino, expansion=None):
        """Cuanto discrimina un termino. Un termino que esta en media base de
        datos no dice nada; uno que esta en 3 items dice casi todo."""
        if expansion:
            df = max((self.df.get(t, 0) for t in expansion), default=0)
        else:
            df = self.df.get(termino, 0)
        return math.log(1.0 + self.n / (1.0 + df))

    # ---- busqueda ----

    def buscar(self, texto, filtro=None, aplicar_medida=True):
        """(resultados, sugerencias).

        resultados: lista de dicts {idx, item, score, motivos, medida_ok},
        ordenada de mas a menos relevante. motivos dice POR QUE aparecio cada
        uno (que termino calzo en que campo), que es lo que el dashboard
        muestra como chips debajo de cada tarjeta.

        filtro: callable(item) -> bool, aplicado antes de puntuar.

        aplicar_medida=False apaga el ranking por medida y devuelve las
        coincidencias de texto puras. Lo usa consultar_item, que necesita
        TODAS las compras de la familia para poder decir "descarte 3 de otra
        medida" antes de promediar; si la medida ya hubiera hundido esas 3
        bajo el corte, el aviso diria 0 y el usuario no se enteraria de que
        existen. El dashboard, en cambio, si quiere el ranking por medida:
        ahi la pregunta es "muestrame lo que pedi primero", no "cuanto
        cuesta esto exactamente"."""
        consulta = parsear_consulta_detalle(texto)
        terms, medidas_pedidas = consulta["terminos"], consulta["medidas"]
        blandas = {"#" + n for n in consulta["blandas"]}
        if not aplicar_medida:
            medidas_pedidas = set()
        if not terms and not medidas_pedidas:
            return [], []

        expansiones = {t: self.expandir(t) for t in terms}
        pesos = {t: self.idf(t, expansiones[t]) for t in terms}
        peso_total = sum(pesos.values()) or 1.0
        peso_campo_max = max(PESOS_CAMPO.values())

        mejor_por_item = {}
        for t in terms:
            for termino_idx, calidad in expansiones[t].items():
                for campo, postings in self.post.items():
                    ids = postings.get(termino_idx)
                    if not ids:
                        continue
                    peso = PESOS_CAMPO[campo] * calidad
                    largos = self.largo[campo]
                    for idx in ids:
                        valor = peso * _norma_largo(largos.get(idx, 1))
                        actual = mejor_por_item.setdefault(idx, {})
                        previo = actual.get(t)
                        if previo is None or valor > previo[0]:
                            actual[t] = (valor, campo, termino_idx, calidad)

        candidatos = set(mejor_por_item)
        if medidas_pedidas and not terms:
            for idx, medidas in enumerate(self.medidas):
                if medidas & medidas_pedidas:
                    candidatos.add(idx)

        puntuados = []
        for idx in candidatos:
            item = self.items[idx]
            if filtro is not None and not filtro(item):
                continue
            calzados = mejor_por_item.get(idx, {})

            bruto = sum(v[0] * pesos[t] for t, v in calzados.items())
            cobertura = sum(pesos[t] for t in calzados) / peso_total
            relevancia = (bruto / (peso_total * peso_campo_max)) if peso_total else 0.0
            relevancia *= PISO_COBERTURA + (1.0 - PISO_COBERTURA) * cobertura * cobertura

            medidas_item = self.medidas[idx]
            if medidas_pedidas:
                if medidas_item & medidas_pedidas:
                    relevancia *= MULT_MEDIDA_EXACTA
                    medida_ok = True
                elif blandas & self._numeros(idx):
                    # "plancha 4": el 4 se leyo como 4 pulgadas, pero este
                    # item lo tiene como dimension en milimetros. Es la misma
                    # medida escrita de otra forma, no otro calibre.
                    relevancia *= MULT_MEDIDA_EXACTA
                    medida_ok = True
                elif medidas_item:
                    relevancia *= MULT_MEDIDA_DISTINTA
                    medida_ok = False
                else:
                    relevancia *= MULT_MEDIDA_AUSENTE
                    medida_ok = None
            else:
                medida_ok = None

            if relevancia <= 0:
                continue
            puntuados.append({
                "idx": idx,
                "item": item,
                "score": relevancia,
                "cobertura": cobertura,
                "medida_ok": medida_ok,
                "motivos": _motivos(calzados, medidas_pedidas, medidas_item),
            })

        puntuados.sort(key=lambda r: (-r["score"], str(self.items[r["idx"]].get("nombre_item") or "")))
        if not puntuados:
            return [], []

        corte = max(UMBRAL_ABSOLUTO, puntuados[0]["score"] * FRACCION_DEL_MEJOR)
        resultados = [r for r in puntuados if r["score"] >= corte]
        sugerencias = _sugerencias([r for r in puntuados if r["score"] < corte])
        return resultados, sugerencias


def _motivos(calzados, medidas_pedidas, medidas_item):
    """Por que aparecio este item, en el idioma del usuario."""
    ETIQUETA = {"cod": "código", "nom": "nombre", "hoja": "producto",
                "mat": "material", "mar": "marca", "cat": "categoría",
                "desc": "descripción", "prov": "proveedor", "proy": "proyecto"}
    motivos = []
    for t, (_valor, campo, termino_idx, calidad) in sorted(
            calzados.items(), key=lambda par: -par[1][0]):
        motivos.append({
            "campo": campo,
            "etiqueta": ETIQUETA.get(campo, campo),
            "termino": t,
            "coincidencia": termino_idx,
            "calidad": calidad,
        })
    if medidas_pedidas and (medidas_item & medidas_pedidas):
        medida = sorted(medidas_item & medidas_pedidas)[0]
        motivos.insert(0, {"campo": "medida", "etiqueta": "medida",
                           "termino": medida, "coincidencia": medida,
                           "calidad": CALIDAD_EXACTA})
    return motivos


MIN_COBERTURA_SUGERENCIA = 0.4


def _sugerencias(descartados):
    """Que escribir en vez de lo que se escribio: los nombres canonicos
    (hoja de la taxonomia) de lo que estuvo cerca pero no paso el corte.

    Se exige que el casi-resultado haya cubierto buena parte de la consulta.
    Sin ese piso, una consulta sin nada que ver ("xyzzy") sugeria los seis
    items que por casualidad tenian una palabra a un error de distancia --
    'Combustible', 'Alimentacion' -- que no ayudan a nadie y hacen parecer
    roto al buscador."""
    salida = []
    for r in descartados:
        if r["score"] < UMBRAL_SUGERENCIA or r["cobertura"] < MIN_COBERTURA_SUGERENCIA:
            continue
        etiqueta = r["item"].get("hoja") or r["item"].get("nombre_item")
        if etiqueta and etiqueta not in salida:
            salida.append(etiqueta)
        if len(salida) >= MAX_SUGERENCIAS:
            break
    return salida


# ====================== 6. PUENTE AL DASHBOARD ======================

def catalogo_sugerencias(items, minimo=1):
    """Lo que el buscador ofrece como autocompletado: los nombres reales del
    catalogo, no una lista escrita a mano.

    Se calcula aqui y viaja en el snapshot, para que la consola y el
    dashboard sugieran lo mismo. Cada entrada trae su tipo (producto,
    categoria, marca, material, medida) para que la UI pueda mostrarlo."""
    conteos = {}

    def sumar(texto, tipo, extra=None):
        if not texto:
            return
        clave = (tipo, str(texto))
        entrada = conteos.setdefault(clave, {"texto": str(texto), "tipo": tipo,
                                             "n": 0, "extra": extra})
        entrada["n"] += 1

    for item in items:
        sumar(item.get("hoja"), "producto")
        sumar(item.get("tipo") or item.get("familia"), "familia")
        sumar(item.get("familia_producto"), "familia")
        sumar(item.get("categoria"), "categoria")
        sumar(item.get("subcategoria"), "subcategoria")
        sumar(item.get("material"), "material")
        sumar(item.get("material_grado"), "material")
        for t in (item.get("terminacion") or []):
            sumar(t, "terminacion")
        sumar(item.get("medida"), "medida")
        sumar(item.get("marca") or detectar_marca(item.get("nombre_item"),
                                                  item.get("descripcion")), "marca")

    salida = [e for e in conteos.values() if e["n"] >= minimo]
    for entrada in salida:
        entrada["clave"] = " ".join(terminos(entrada["texto"])) or normalizar_alias(entrada["texto"])
    salida.sort(key=lambda e: (-e["n"], e["texto"]))
    return salida


def config_para_snapshot(medidas_presentes=()):
    """Todas las tablas que el buscador del dashboard necesita para procesar
    una consulta, listas para embeber en el snapshot.

    El JavaScript (Visualizador Web/busqueda.js) implementa SOLO el lado de
    la consulta y el puntaje; los datos -- sinonimos, palabras vacias, pesos,
    alias de medida -- salen de aqui. Es la misma separacion motor/datos que
    taxonomia.py + catalogo_taxonomia.py, extendida a traves del build para
    que no exista una segunda copia de estas tablas dentro del HTML."""
    return {
        "vacias": sorted(VACIAS),
        "sinonimos": dict(sorted(SINONIMO_DE.items())),
        "alias_medida": dict(sorted(_construir_alias_medida(medidas_presentes).items())),
        "pesos_campo": dict(PESOS_CAMPO),
        "campos": list(CAMPOS),
        "calidad": {"exacta": CALIDAD_EXACTA, "prefijo": CALIDAD_PREFIJO,
                    "difusa": CALIDAD_DIFUSA},
        "max_errores": [list(t) for t in MAX_ERRORES_POR_LARGO],
        "medida": {"exacta": MULT_MEDIDA_EXACTA, "distinta": MULT_MEDIDA_DISTINTA,
                   "ausente": MULT_MEDIDA_AUSENTE},
        # Tablas del lado de la consulta que el navegador necesita para leer
        # numeros, grados y especificaciones igual que Python.
        "especificaciones": {
            "prefijos": list(_PREFIJOS_SPEC),
            "canonico": dict(_CANONICO_SPEC),
            "grados": list(_PREFIJOS_GRADO),
        },
        "piso_cobertura": PISO_COBERTURA,
        "factor_norma_largo": FACTOR_NORMA_LARGO,
        "fraccion_del_mejor": FRACCION_DEL_MEJOR,
        "umbral_absoluto": UMBRAL_ABSOLUTO,
        "umbral_sugerencia": UMBRAL_SUGERENCIA,
        "min_cobertura_sugerencia": MIN_COBERTURA_SUGERENCIA,
        "max_sugerencias": MAX_SUGERENCIAS,
        "max_palabras_alias": _MAX_PALABRAS_ALIAS,
        # Constantes del respaldo "un entero suelto es el calibre". Viajan en
        # el snapshot en vez de estar escritas en el JavaScript para que el
        # tope de pulgadas y la lista de cuantificadores existan una sola vez
        # en el proyecto (son de taxonomia.py).
        "entero_suelto": {
            "alias": dict(ALIAS_ENTERO),
            "max_pulgadas": taxonomia.MAX_PULGADAS_NOMINAL,
            "angulos": sorted(taxonomia.ANGULOS_DE_FITTING),
            "cuantificadores": sorted(taxonomia.CUANTIFICADORES),
        },
    }


def indexar_para_snapshot(compras):
    """Deja cada compra con sus terminos (_bt) y sus medidas (_bm) listos.

    Es el trabajo pesado del buscador -- tokenizar, lematizar, aplicar
    sinonimos y leer las medidas de cada texto -- y se hace UNA vez, en el
    build, sobre las ~1.400 compras. El navegador recibe el resultado y solo
    procesa lo que el usuario escribe.

    Ademas de rapido, es lo que mantiene una sola fuente de verdad: si el
    lado del documento tambien se tokenizara en JavaScript, habria dos
    implementaciones del mismo paso y volveriamos al problema que dejo la
    taxonomia duplicada en los templates."""
    for compra in compras:
        # con_ficha: una compra del dashboard ya trae sus atributos; una que
        # viene del Excel se clasifica aqui. Tiene que ser la MISMA ficha que
        # usa Indice() en Python, o el navegador y la consola indexarian
        # medidas distintas (lo que el test de paridad detecta como ordenes
        # distintos).
        ficha = con_ficha(compra)
        compra["marca"] = compra.get("marca") or detectar_marca(
            compra.get("nombre_item"), compra.get("descripcion"))
        compra["_bt"] = terminos_documento(ficha)
        compra["_bm"] = medidas_de_item(compra.get("nombre_item"),
                                        compra.get("descripcion"),
                                        ficha.get("medida"),
                                        ficha.get("medidas_equivalentes") or ())
    return compras
