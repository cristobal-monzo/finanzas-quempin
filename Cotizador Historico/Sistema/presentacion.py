# -*- coding: utf-8 -*-
"""
presentacion.py -- como se ESCRIBE lo que ya se entendio.

    20000 mm          -> "20 m"
    "Radiador ANWO"   -> "Radiador Anwo"
    "Quilpue"/"Quilpue" (con y sin tilde) -> una sola forma

Separa la escritura de la interpretacion. Los otros modulos deciden QUE es un
producto (taxonomia), DE QUE esta hecho (atributos) y CUANTO mide
(dimensiones); este decide solamente como se muestra, y nunca al reves: las
cadenas canonicas que usa el buscador para calzar medidas se siguen
generando en mm (dimensiones.medidas_equivalentes, taxonomia.Medida.canonico)
y no pasan por aca.

POR QUE ESTA SEPARADO DEL MOTOR

Un numero y su escritura son cosas distintas. "20000mm" y "20 m" son la misma
extension electrica: la primera escritura es la que hace falta para comparar
medidas entre si (una sola unidad, sin ambiguedad), la segunda es la unica
que un comprador reconoce. Mientras las dos vivieron en el mismo campo, el
catalogo mostraba la escritura de la maquina -- "Extension Electrica
20000mm", "Teflon 1000x10000mm" -- y cambiarla habria roto el calce de
medidas del buscador.

La misma separacion vale para los nombres: el catalogo real trae "ANWO",
"Anwo" y "anwo" para la misma marca, y "Quilpue" con y sin tilde para el
mismo proveedor. Unificarlos en el dato de origen seria reescribir el Excel
(que es la fuente, y este modulo es de solo lectura); unificarlos al mostrar
es reversible y no pierde nada -- el texto original sigue guardado en
nombre_original.
"""
import re
import unicodedata

from catalogo_busqueda import MARCAS
from catalogo_presentacion import PALABRAS_CANONICAS, SIGLAS


# ---------------------------------------------------------------------------
# MEDIDAS
# ---------------------------------------------------------------------------
# A partir de un metro la escritura en milimetros deja de decir algo: nadie
# pide una extension de 20000 mm. El corte es 1000 y no 100 a proposito --
# pasar 115 mm (un disco de corte) a 11,5 cm seria igual de ilegible en la
# otra direccion, y el catalogo real no tiene ninguna familia que se compre
# en centimetros.
CORTE_METRO_MM = 1000.0


def numero(v):
    """El numero como se escribe en Chile: coma decimal, sin ceros de mas."""
    return ("%g" % round(float(v), 3)).replace(".", ",")


def unidad_practica(valor_mm):
    """('20', 'm') o ('115', 'mm') -- el numero ya escrito y su unidad."""
    v = float(valor_mm)
    if abs(v) >= CORTE_METRO_MM:
        return numero(v / 1000.0), "m"
    return numero(v), "mm"


def medida_texto(valor_mm):
    """Una medida suelta, con la unidad que un comprador usaria."""
    n, u = unidad_practica(valor_mm)
    return "%s %s" % (n, u)


def grupo_texto(valores_mm):
    """Un grupo de medidas que se escriben juntas ("0,7 x 812 x 3660 mm").

    La unidad es COMUN a todo el grupo: mezclar "1 m x 812 mm" obliga a leer
    dos veces. Se usa el metro solo si TODAS las componentes llegan al metro,
    para que una plancha siga escrita 0,7 x 812 x 3660 mm -- que es como la
    vende el proveedor -- y un rollo de teflon de 1 x 10 m no quede en
    1000x10000mm.
    """
    valores = [float(v) for v in valores_mm]
    if not valores:
        return None
    if all(abs(v) >= CORTE_METRO_MM for v in valores):
        return " x ".join(numero(v / 1000.0) for v in valores) + " m"
    return " x ".join(numero(v) for v in valores) + " mm"


# ---------------------------------------------------------------------------
# NOMBRES
# ---------------------------------------------------------------------------
# Las marcas ya estan curadas con su escritura correcta para el buscador
# (catalogo_busqueda.MARCAS); reusarlas evita mantener dos listas que digan
# lo mismo y se desincronicen.
_FORMA_CANONICA = {}
for _m in MARCAS:
    _FORMA_CANONICA[_m.lower()] = _m
for _s in SIGLAS:
    _FORMA_CANONICA[_s.lower()] = _s
for _c in PALABRAS_CANONICAS:
    _FORMA_CANONICA[_c.lower()] = _c

_PALABRA = re.compile(r"[0-9A-Za-zÀ-ÿ][0-9A-Za-zÀ-ÿ'’./-]*")


def _sin_acentos(s):
    """Quita tildes pero NO la enye: en NFD la 'n' de "cana" y la de "cana"
    con enye se decomponen igual, y confundirlas cambia la palabra."""
    s = s.replace("ñ", "\0n\0").replace("Ñ", "\0N\0")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("\0n\0", "ñ").replace("\0N\0", "Ñ")


def nombre_presentable(texto):
    """El texto del catalogo con las palabras que tienen una escritura
    conocida puestas en esa escritura.

    Solo toca palabras que estan en el catalogo (marcas, siglas tecnicas,
    unidades): todo lo demas queda exactamente como lo escribio el
    proveedor. Es deliberado -- una regla general de "capitalizar" convertiria
    "PVC" en "Pvc" y "1/2 NPT" en "1/2 Npt".
    """
    if not texto:
        return texto

    def reemplazo(m):
        palabra = m.group(0)
        canonica = _FORMA_CANONICA.get(_sin_acentos(palabra).lower())
        if canonica is None or canonica == palabra:
            return palabra
        return canonica

    return _PALABRA.sub(reemplazo, texto)


# ---------------------------------------------------------------------------
# NOMBRES QUE SOLO EXISTEN EN LOS DATOS (proveedores, proyectos)
# ---------------------------------------------------------------------------
def clave_nombre(s):
    """Dos escrituras del mismo nombre comparten clave: 'Quilpue',
    'Quilpue' con tilde y 'QUILPUE' son el mismo proveedor."""
    return " ".join(_sin_acentos(s or "").lower().split())


def _prolijidad(nombre):
    """Cuanto se parece a un nombre bien escrito: ni todo en mayusculas ni
    todo en minusculas. Desempata cuando dos escrituras aparecen lo mismo."""
    letras = [c for c in nombre if c.isalpha()]
    if not letras:
        return 0
    if all(c.isupper() for c in letras) or all(c.islower() for c in letras):
        return 0
    return 1


# Las tildes no son opcionales en castellano: si el catalogo escribe la misma
# palabra con y sin tilde, la forma con tilde es la correcta. Se aplica solo
# desde 5 letras porque los pares cortos SI son palabras distintas -- "mas" y
# "mas" con tilde, "solo"/"solo", "esta"/"esta", "el"/"el" -- y ahi la regla
# elegiria mal la mitad de las veces.
LARGO_MINIMO_TILDE = 5


def _tildes(palabra):
    return sum(1 for a, b in zip(palabra, _sin_acentos(palabra)) if a != b)


def unificar_ortografia(textos):
    """{palabra -> palabra con su escritura canonica} leido del propio
    catalogo: si "portatil" aparece tambien como "portatil" con tilde, gana
    la que la lleva.

    Es data-driven a proposito: el catalogo crece con proveedores nuevos que
    escriben como quieren, y una lista a mano quedaria vieja al mes.
    """
    formas = {}
    for texto in textos:
        for palabra in _PALABRA.findall(texto or ""):
            if len(palabra) < LARGO_MINIMO_TILDE or not palabra.isalpha():
                continue
            clave = _sin_acentos(palabra).lower()
            formas.setdefault(clave, {}).setdefault(palabra, 0)
            formas[clave][palabra] += 1

    salida = {}
    for variantes in formas.values():
        con_tilde = [v for v in variantes if _tildes(v)]
        if not con_tilde or len(con_tilde) == len(variantes):
            continue  # ninguna o todas: no hay una diferencia de tildes que resolver
        # Entre las que llevan tilde manda la mas frecuente. Las diferencias
        # de mayusculas las resuelve el catalogo de siglas, no esto: aca solo
        # se copia la caja de la palabra original.
        mejor = sorted(con_tilde, key=lambda v: (-variantes[v], v))[0]
        for variante in variantes:
            if not _tildes(variante):
                salida[variante] = _misma_caja(variante, mejor.lower())
    return salida


def _misma_caja(original, canonica):
    """Le pone a la forma canonica la caja que traia el original, para no
    convertir "Portatil" al principio de un nombre en "portatil"."""
    if original[:1].isupper() and canonica[:1].islower():
        return canonica[:1].upper() + canonica[1:]
    if original[:1].islower() and canonica[:1].isupper():
        return canonica[:1].lower() + canonica[1:]
    return canonica


def aplicar_ortografia(texto, mapa):
    """Reescribe un texto con el mapa que devolvio unificar_ortografia."""
    if not texto or not mapa:
        return texto
    return _PALABRA.sub(lambda m: mapa.get(m.group(0), m.group(0)), texto)


def unificar_nombres(nombres):
    """{escritura -> escritura canonica} para una lista de nombres repetidos.

    Gana la forma con tildes (son nombres propios: "Quilpue" sin tilde es una
    falta, no una variante); entre las que empatan en tildes, la mas
    frecuente; despues la mejor escrita, y al final la primera
    alfabeticamente. Es determinista y se explica sola -- no hay una lista que
    mantener a mano, y si manana el catalogo escribe un proveedor de otra
    forma, la regla sigue valiendo.
    """
    conteo = {}
    for n in nombres:
        if not n:
            continue
        conteo.setdefault(clave_nombre(n), {}).setdefault(n, 0)
        conteo[clave_nombre(n)][n] += 1

    salida = {}
    for formas in conteo.values():
        mejor = sorted(formas.items(),
                       key=lambda kv: (-_tildes(kv[0]), -kv[1],
                                       -_prolijidad(kv[0]), kv[0]))[0][0]
        for forma in formas:
            salida[forma] = mejor
    return salida
