# -*- coding: utf-8 -*-
"""
catalogo_atributos.py -- los DATOS con que se describe un producto: de que
material esta hecho, como se abrevia cada palabra, que terminaciones existen,
como se leen las dimensiones de cada familia y que filtros tiene sentido
ofrecer para cada una. El motor que los aplica vive en atributos.py.

Mismo reparto motor/datos que taxonomia.py + catalogo_taxonomia.py: este es
el archivo que se edita para ensenarle al sistema un material, una
abreviatura o una terminacion nueva. `driver.py atributos` lista las palabras
del catalogo real que todavia no estan en ninguna de estas tablas.

EL PRINCIPIO (pedido del usuario, 2026-09-22)

    Un producto no se clasifica por su forma o sus dimensiones. Primero se
    identifica QUE es, despues DE QUE esta hecho y recien despues sus
    caracteristicas dimensionales y tecnicas.

Por eso el material es un atributo propio, con prioridad alta y con ROL:
el mismo "acero" es el material de una plancha de acero, un componente en un
"mazo de goma con mango de acero" y una aplicacion en un "disco de corte
para acero". Solo el primero es el material del producto.
"""

# ---------------------------------------------------------------------------
# MATERIALES
# ---------------------------------------------------------------------------
# (nombre canonico, familia de material, alias)
#
# - Los alias se escriben en lenguaje natural; el motor les aplica la misma
#   normalizacion que al texto (sin tildes, sin plural, abreviaturas).
# - La familia de material ("base") agrupa para buscar y filtrar: una
#   consulta "plancha plastico" encuentra policarbonato y acrilico.
# - El ORDEN importa solo como desempate entre dos alias que calzan en la
#   misma posicion: el mas especifico va primero ("acero inoxidable" antes
#   que "acero", "fierro galvanizado" antes que "fierro").
#
# Por que Acero negro y Acero carbono son dos entradas: en piping chileno
# "canieria negra" es el nombre del producto (el usuario pidio distinguirla,
# 2026-09-09); en planchas y barras se habla de acero al carbono. Los dos
# comparten familia de material y se buscan juntos.
MATERIALES = [
    # --- aceros ---
    ("Acero inoxidable", "Acero inoxidable",
     ["acero inoxidable", "inoxidable", "inox", "acero inox", "a inox", "ss", "sus", "aisi",
      "ss304", "ss316", "ss304l", "ss316l", "inox304", "inox316", "stainless"]),
    ("Acero galvanizado", "Acero",
     ["acero galvanizado", "fierro galvanizado", "galvanizado", "galvanizada", "galv",
      "zincado", "zincada", "zinc", "zn", "electrogalvanizado", "hdg", "acero zincado"]),
    ("Zincalum", "Acero", ["zincalum", "zincalume", "aluzinc", "galvalume"]),
    ("Acero negro", "Acero",
     ["acero negro", "fierro negro", "caneria negra", "canieria negra", "cañeria negra",
      "punta negra", "punta negro", "tubo negro", "cuadrado negro", "cuad negro"]),
    ("Acero rápido (HSS)", "Acero", ["hss", "hss co", "acero rapido", "hss cobalto"]),
    ("Hierro fundido", "Hierro", ["fierro fundido", "hierro fundido", "hierro ductil",
                                  "fundicion gris"]),
    ("Acero carbono", "Acero",
     ["acero carbono", "acero al carbono", "acero laminado", "acero", "fierro", "fe",
      "trefilado", "acero trefilado"]),
    # --- no ferrosos ---
    ("Cobre", "Cobre", ["cobre", "cu"]),
    ("Latón", "Aleaciones de cobre", ["laton", "dzr", "bronce dzr"]),
    ("Bronce", "Aleaciones de cobre", ["bronce", "br", "bce"]),
    ("Aluminio", "Aluminio", ["aluminio", "alum", "alu"]),
    ("Magnesio", "Otros metales", ["magnesio"]),
    # --- plasticos ---
    ("CPVC", "Plásticos", ["cpvc"]),
    ("PVC", "Plásticos", ["pvc", "pvc p", "vinilit", "cementado", "cementada", "cementar"]),
    ("PPR", "Plásticos", ["ppr", "pp r", "polipropileno random"]),
    ("PEX", "Plásticos", ["pex", "pex a", "pexa", "pe x"]),
    ("HDPE", "Plásticos", ["hdpe", "pead", "polietileno alta densidad"]),
    ("Polipropileno", "Plásticos", ["polipropileno"]),
    ("Policarbonato", "Plásticos", ["policarbonato", "policarb"]),
    ("Acrílico", "Plásticos", ["acrilico", "pmma", "plexiglas", "plexiglass"]),
    ("Nylon", "Plásticos", ["nylon", "nailon", "poliamida"]),
    ("PTFE", "Plásticos", ["ptfe", "teflon"]),
    ("Poliéster", "Textiles", ["poliester"]),
    # --- elastomeros y sellos ---
    ("EPDM", "Elastómeros", ["epdm"]),
    ("NBR", "Elastómeros", ["nbr", "nitrilo", "buna"]),
    ("Viton", "Elastómeros", ["viton", "fkm"]),
    ("Neopreno", "Elastómeros", ["neopreno"]),
    ("Silicona", "Elastómeros", ["silicona"]),
    ("Caucho", "Elastómeros", ["caucho", "goma"]),
    ("Grafito", "Minerales y fibras", ["grafito", "graphinox", "grafoil"]),
    # --- minerales y fibras ---
    ("Fibra de vidrio", "Minerales y fibras", ["fibra de vidrio", "fibra vidrio", "fibrovidrio"]),
    ("Fibra cerámica", "Minerales y fibras", ["fibra ceramica"]),
    ("Lana mineral", "Minerales y fibras", ["lana mineral", "lana de roca", "lana de vidrio"]),
    ("Vidrio", "Minerales y fibras", ["vidrio"]),
    # --- madera y derivados ---
    ("MDF", "Madera y derivados", ["mdf"]),
    ("Terciado", "Madera y derivados", ["terciado", "contrachapado", "plywood"]),
    ("OSB", "Madera y derivados", ["osb"]),
    ("Melamina", "Madera y derivados", ["melamina"]),
    ("Pino", "Madera y derivados", ["pino", "pino radiata"]),
    ("Madera", "Madera y derivados", ["madera"]),
    # --- otros ---
    ("Cuero", "Textiles", ["cuero", "cabritilla", "descarne"]),
    ("Epoxi", "Resinas", ["epoxi", "epoxico", "epoxica", "epoxy"]),
]

# Frases donde la palabra de un material NO es un material: "teflon liquido"
# es un sellante anaerobico, no PTFE; "papel de aluminio" si seria aluminio.
NO_ES_MATERIAL = ["teflon liquido", "teflon anaerobico", "gas mapp"]

# "negro"/"negra" solos son un color ("Poleron termico negro"). Solo son
# acero negro en las categorias donde el catalogo los usa asi.
CATEGORIAS_NEGRO_ES_MATERIAL = {"Piping y Fittings", "Planchas y Perfiles"}

# Material que se deduce del TIPO cuando el texto no lo dice (confianza
# menor: queda marcado como inferido en la ficha).
MATERIAL_POR_TIPO = {
    "Fierro de Construcción": "Acero carbono",
    "Madera Dimensionada": "Pino",
    "Cable de Acero": "Acero carbono",
}

# Grados de perno de acero al carbono: G-2, G-5 y G-8 son grados SAE de
# acero al carbono, asi que un "perno G-5" es de acero aunque no lo diga.
GRADOS_ACERO_CARBONO = {"G-2", "G-5", "G-8", "8.8", "10.9", "12.9"}

# Series AISI de acero inoxidable (las de acero al carbono son 1xxx).
SERIES_INOXIDABLE = {"201", "301", "302", "303", "304", "309", "310", "316", "317", "321",
                     "347", "410", "416", "420", "430", "440"}


# ---------------------------------------------------------------------------
# ROLES DEL MATERIAL
# ---------------------------------------------------------------------------
# Un material que aparece despues de estas palabras es la APLICACION del
# producto ("disco para acero inoxidable", "broca p/metal"), no su material.
MARCADORES_APLICACION = {"para", "p", "uso"}

# ...y un material que viene justo despues de una de estas PIEZAS es el
# material de esa pieza, no el del producto: "mazo de goma con mango de
# acero" es de goma, "visor policarbonato c/marco aluminio" es de
# policarbonato, y el bronce de "conexion inferior 1/2 NPT bronce" es el de
# la conexion de un manometro de caja inoxidable.
#
# Aca NO van sustantivos que sean el producto mismo (tuerca, perno, disco,
# bola, tapa): con ellos dentro, "Tuerca inoxidable" se quedaba sin material
# porque su propia palabra anulaba al que venia detras.
SUSTANTIVOS_COMPONENTE = {"marco", "mango", "cabezal", "injerto", "inserto", "cuello", "vaina",
                          "manilla", "empunadura", "puno", "cordon", "cab", "cabeza", "palanca",
                          "conexion", "carcasa", "asa"}

# Tipos cuyo material escrito es, salvo que diga "de X", lo que CORTAN o
# PULEN: un disco de corte "acero inoxidable" no es un disco de inoxidable.
TIPOS_MATERIAL_ES_APLICACION = {"Disco de Corte", "Disco de Desbaste", "Disco Flap", "Disco",
                                "Lija", "Hoja de Sierra", "Adhesivo"}


# ---------------------------------------------------------------------------
# ABREVIATURAS
# ---------------------------------------------------------------------------
# Como escribe el catalogo real las palabras largas. Se expanden ANTES de
# clasificar y viajan al buscador como sinonimos (una sola tabla para los dos
# lados, ver busqueda.SINONIMO_DE).
#
# Solo abreviaturas sin ambiguedad dentro de este catalogo: "br" es bronce
# siempre que aparece; "s" solo seria "sin" despues de una barra, y eso lo
# resuelve el motor (s/ -> sin), no esta tabla.
ABREVIATURAS = {
    "galv": "galvanizado",
    "inox": "inoxidable",
    "policarb": "policarbonato",
    "perf": "perfil",
    "valv": "valvula",
    "cuad": "cuadrado",
    "rect": "rectangular",
    "neg": "negro",
    "lam": "laminado",
    "hex": "hexagonal",
    "amer": "americana",
    "reduc": "reduccion",
    "alum": "aluminio",
    "cte": "corriente",
    "calef": "calefaccion",
    "temp": "temperatura",
    "glic": "glicerina",
    "manovac": "manovacuometro",
    "desinf": "desinfectante",
    "aisl": "aislante",
    "esp": "espesor",
    "diam": "diametro",
}

# ---------------------------------------------------------------------------
# TERMINACIONES Y COLORES
# ---------------------------------------------------------------------------
# (frase, terminacion canonica). Una terminacion es una caracteristica del
# producto que NO cambia de que esta hecho: una plancha galvanizada lisa y
# una ondulada son las dos de acero galvanizado.
TERMINACIONES = [
    ("transparente", "Transparente"), ("cristal", "Transparente"),
    ("opal", "Opal"), ("opalino", "Opal"),
    ("alveolar", "Alveolar"), ("compacto", "Compacto"),
    ("lisa", "Lisa"), ("liso", "Lisa"),
    ("ondulada", "Ondulada"), ("ondulado", "Ondulada"), ("acanalada", "Acanalada"),
    ("laminado en frio", "Laminada en frío"), ("laminada en frio", "Laminada en frío"),
    ("laminado en caliente", "Laminada en caliente"), ("laminada en caliente", "Laminada en caliente"),
    ("galvanizado en caliente", "Galvanizado en caliente"), ("hdg", "Galvanizado en caliente"),
    ("zincado", "Zincado"), ("zincada", "Zincado"),
    ("cromado", "Cromado"), ("cromada", "Cromado"), ("niquelado", "Niquelado"),
    ("pulido", "Pulido"), ("pulida", "Pulido"), ("satinado", "Satinado"),
    ("brillante", "Brillante"), ("mate", "Mate"),
    ("prepintado", "Prepintado"), ("pintado", "Pintado"),
    ("expandido", "Expandido"), ("trefilado", "Trefilado"), ("trefilada", "Trefilado"),
    ("mandrilado", "Mandrilado"), ("mandrilada", "Mandrilado"),
    ("con costura", "Con costura"), ("sin costura", "Sin costura"),
    ("bruto", "Bruto"), ("cepillado", "Cepillado"), ("seco", "Seco"),
    ("dimensionado", "Dimensionado"), ("impregnado", "Impregnado"),
]

# "verde" es la madera humeda en el aserradero, no un color.
TERMINACIONES_POR_CATEGORIA = {"Maderas": [("verde", "Verde")]}

COLORES = {"blanco": "Blanco", "blanca": "Blanco", "negro": "Negro", "negra": "Negro",
           "rojo": "Rojo", "roja": "Rojo", "azul": "Azul", "amarillo": "Amarillo",
           "amarilla": "Amarillo", "verde": "Verde", "gris": "Gris", "naranja": "Naranja",
           "claro": "Claro", "dorado": "Dorado", "plateado": "Plateado", "caoba": "Caoba",
           "turquesa": "Turquesa"}


# ---------------------------------------------------------------------------
# ESPECIFICACIONES: conexiones
# ---------------------------------------------------------------------------
# Extremos de un fitting o valvula, en la forma en que el catalogo los
# escribe. Solo se leen en las categorias de piping (fuera de ahi "macho" y
# "hembra" describen un enchufe, no una conexion roscada).
EXTREMOS = {"hi": "HI", "hembra": "HI", "he": "HE", "macho": "HE", "so": "SO",
            "soldar": "SO", "soldable": "SO", "fusion": "Fusión", "termofusion": "Fusión",
            "cementar": "Cementar", "cementada": "Cementar", "cementado": "Cementar",
            "bw": "BW", "sw": "SW", "od": "OD", "bridado": "Brida", "brida": "Brida",
            "ni": "HE"}
CATEGORIAS_CON_CONEXION = {"Piping y Fittings", "Válvulas y Control de Flujo",
                           "Instrumentación y Medición"}
CATEGORIAS_ELECTRICAS = {"Materiales Eléctricos", "Herramientas Eléctricas",
                         "Calefacción y Combustión", "Instrumentación y Medición",
                         "Soldadura y Gases", "Bombas y Equipos Hidráulicos"}


# ---------------------------------------------------------------------------
# ESQUEMAS DIMENSIONALES
# ---------------------------------------------------------------------------
# El mismo "40x2" es un perfil cuadrado de 40 mm de lado y 2 de espesor, y
# "2x6" es una escuadria de pino de 2x6 pulgadas. El significado de cada
# numero depende de QUE producto es, asi que el esquema se elige por tipo
# primero y por familia despues.
ESQUEMA_POR_TIPO = {
    "Plancha": "lamina", "Plancha de Empaquetadura": "lamina", "Manta": "lamina",
    "Malla": "malla",
    "Perfil": "perfil", "Perfil Cuadrado": "perfil", "Perfil Rectangular": "perfil",
    "Perfil Ángulo": "perfil", "Perfil Canal": "perfil", "Perfil Omega": "perfil",
    "Riel": "perfil", "Moldura": "perfil", "Platina": "perfil",
    "Fierro de Construcción": "barra", "Barra": "barra",
    "Madera Dimensionada": "madera",
    "Cañería": "tuberia", "Tubo": "tuberia", "Conduit": "tuberia",
    "Perno": "perno", "Perno Hexagonal": "perno", "Perno de Anclaje": "perno",
    "Perno Ojo": "perno", "Perno Coche": "perno", "Varilla Roscada": "perno",
    "Tuerca": "tuerca", "Golilla": "tuerca", "Golilla Plana": "tuerca",
    "Golilla de Presión": "tuerca", "Grillete": "tuerca", "Guardacabo": "tuerca",
    "Prensa Cable": "tuerca",
    "Tornillo": "tornillo", "Tornillo Autoperforante": "tornillo",
    "Tornillo para Madera": "tornillo",
    "Remache": "remache", "Argolla": "remache", "Tarugo": "perno", "Clavo": "remache",
    "Disco de Corte": "disco", "Disco de Desbaste": "disco", "Disco Flap": "disco",
    "Disco": "disco",
    "Electrodo": "electrodo",
    "Cinta Eléctrica": "cinta", "Cinta de Aluminio": "cinta", "Cinta": "cinta",
    "Teflón": "cinta", "Cinta Sella Hilo": "cinta", "Cinta de Amarre": "cinta",
    "Cinta Aislante Térmica": "cinta",
    "Coquilla": "aislacion", "Aislante": "aislacion",
    "Termopozo": "instrumento", "Manómetro": "instrumento", "Termómetro": "instrumento",
    "Ánodo": "instrumento",
    # Se comparan por diametro (y largo, cuando lo traen)
    "Cable de Acero": "tuberia", "Cadena": "tuberia", "Cuerda": "tuberia",
    "Eslinga": "cinta", "Cinta de Amarre": "cinta",
    "Broca": "tuerca", "Terraja": "tuerca", "Brocha": "cinta",
    "Flexible": "fitting", "Abrazadera": "fitting",
}
ESQUEMA_POR_FAMILIA = {
    "Fittings": "fitting", "Válvulas": "fitting", "Flanges": "fitting", "Filtros": "fitting",
    "Purgas y Venteos": "fitting", "Mangueras y Flexibles": "fitting",
    "Soportes y Abrazaderas": "fitting", "Cañerías y Tubos": "tuberia",
}

# Materiales de SISTEMA de tuberia plastica: un entero sin unidad junto a
# ellos es el diametro exterior en milimetros ("PEX 32", "PPR 032"), nunca
# pulgadas. En cobre, bronce o acero el mismo entero es una pulgada nominal.
MATERIALES_SISTEMA_METRICO = {"PPR", "PEX", "PVC", "CPVC", "HDPE", "Polipropileno"}

# ---------------------------------------------------------------------------
# DN <-> PULGADA
# ---------------------------------------------------------------------------
# Diametro nominal ISO -> pulgada nominal. Es la UNICA conversion entre el
# mundo metrico y el de pulgadas que este modulo acepta, y es a proposito:
# es una tabla normalizada y cerrada, no una regla aritmetica.
#
# NO se convierte mm <-> pulgada dividiendo por 25,4. Un tubo PPR de 50mm es
# un diametro EXTERIOR real y equivale a DN40 (1.1/2"), no a los 1,97" que
# daria la division. Confundirlos mezclaria en una misma hoja productos de
# calibre distinto. La usan la clasificacion (atributos._limpiar) y el
# buscador (catalogo_busqueda la importa de aqui: una sola tabla).
DN_A_PULGADA = {
    6: "1/4", 8: "5/16", 10: "3/8", 15: "1/2", 20: "3/4", 25: "1", 32: "1.1/4",
    40: "1.1/2", 50: "2", 65: "2.1/2", 80: "3", 90: "3.1/2", 100: "4", 125: "5",
    150: "6", 200: "8", 250: "10", 300: "12",
}

# Equivalencias comerciales de discos abrasivos: un disco de 115 mm es el
# "4 1/2 pulgadas" de ferreteria. Solo aplican a discos (el resto del
# catalogo NO convierte mm <-> pulgada, ver catalogo_busqueda.DN_A_PULGADA).
DISCO_PULGADA_A_MM = {"4.1/2": 115, "5": 125, "7": 180, "9": 230, "14": 355}

# Equivalencias de electrodos: 3/32" = 2,5 mm, 1/8" = 3,2 mm, 5/32" = 4 mm.
ELECTRODO_PULGADA_A_MM = {"3/32": 2.5, "1/8": 3.2, "5/32": 4.0, "3/16": 4.8}


# ---------------------------------------------------------------------------
# FACETAS POR FAMILIA (filtros del dashboard)
# ---------------------------------------------------------------------------
# Que filtros tiene sentido ofrecer para cada familia de producto. "Schedule"
# no existe para una plancha ni "Ancho" para una valvula. Cada entrada es
# (clave del atributo en la ficha, etiqueta). Las claves "dim:<rol>" son
# dimensiones; "spec:<clave>" especificaciones.
FACETAS_POR_FAMILIA = {
    "Planchas": [("material", "Material"), ("dim:espesor", "Espesor"), ("dim:ancho", "Ancho"),
                 ("dim:largo", "Largo"), ("terminacion", "Terminación"),
                 ("material_grado", "Grado")],
    "Empaquetaduras": [("tipo", "Tipo"), ("material", "Material"), ("dim:espesor", "Espesor")],
    "Perfiles": [("tipo", "Tipo"), ("material", "Material"), ("dim:ancho", "Ancho"),
                 ("dim:alto", "Alto"), ("dim:espesor", "Espesor"), ("dim:largo", "Largo")],
    "Barras y Platinas": [("tipo", "Tipo"), ("material", "Material"), ("dim:ancho", "Ancho"),
                          ("dim:espesor", "Espesor"), ("dim:diametro", "Diámetro"),
                          ("dim:largo", "Largo")],
    "Mallas": [("material", "Material"), ("dim:diametro", "Alambre"), ("dim:ancho", "Ancho"),
               ("dim:largo", "Largo")],
    "Maderas": [("material", "Madera"), ("dim:ancho", "Ancho"), ("dim:alto", "Alto"),
                ("dim:largo", "Largo"), ("terminacion", "Terminación")],
    "Cañerías y Tubos": [("tipo", "Tipo"), ("material", "Material"),
                         ("dim:diametro", "Diámetro"), ("spec:schedule", "Schedule"),
                         ("spec:tipo_pared", "Tipo de pared"), ("spec:presion", "Presión"),
                         ("spec:norma", "Norma"), ("dim:largo", "Largo")],
    "Fittings": [("tipo", "Tipo"), ("material", "Material"), ("dim:diametro", "Diámetro"),
                 ("dim:diametro_salida", "Diámetro salida"), ("spec:conexion", "Conexión"),
                 ("spec:rosca", "Rosca"), ("spec:schedule", "Schedule"),
                 ("spec:presion", "Presión")],
    "Flanges": [("material", "Material"), ("dim:diametro", "Diámetro"),
                ("spec:presion", "Presión"), ("spec:norma", "Norma"), ("spec:rosca", "Rosca")],
    "Válvulas": [("tipo", "Tipo"), ("dim:diametro", "Diámetro"), ("material", "Material"),
                 ("spec:conexion", "Conexión"), ("spec:presion", "Presión"),
                 ("spec:accionamiento", "Accionamiento"), ("marca", "Marca")],
    "Pernos": [("tipo", "Tipo"), ("dim:diametro", "Diámetro"), ("dim:largo", "Largo"),
               ("material", "Material"), ("spec:grado", "Grado"), ("spec:rosca", "Rosca")],
    "Tuercas": [("dim:diametro", "Diámetro"), ("material", "Material"), ("spec:grado", "Grado"),
                ("spec:rosca", "Rosca")],
    "Golillas": [("tipo", "Tipo"), ("dim:diametro", "Diámetro"), ("material", "Material")],
    "Tornillos": [("tipo", "Tipo"), ("dim:calibre", "Calibre"), ("dim:largo", "Largo"),
                  ("material", "Material")],
    "Remaches": [("dim:diametro", "Diámetro"), ("dim:largo", "Largo"), ("material", "Material")],
    "Varillas y Hilos": [("dim:diametro", "Diámetro"), ("material", "Material"),
                         ("spec:grado", "Grado")],
    "Aislación": [("tipo", "Tipo"), ("material", "Material"), ("dim:espesor", "Espesor"),
                  ("dim:diametro", "Diámetro"), ("dim:ancho", "Ancho"), ("dim:largo", "Largo")],
    "Discos": [("tipo", "Tipo"), ("dim:diametro", "Diámetro"), ("dim:espesor", "Espesor"),
               ("aplicacion", "Para cortar"), ("marca", "Marca")],
    "Electrodos": [("dim:diametro", "Diámetro"), ("spec:norma", "Clase AWS"), ("marca", "Marca")],
    "Instrumentación": [("tipo", "Tipo"), ("dim:conexion", "Conexión"), ("material", "Material"),
                        ("marca", "Marca")],
    "Accesorios Eléctricos": [("tipo", "Tipo"), ("spec:corriente", "Corriente")],
}
# Para las familias que no estan arriba: lo minimo que casi siempre sirve.
FACETAS_POR_DEFECTO = [("tipo", "Tipo"), ("material", "Material"), ("medida", "Medida"),
                       ("marca", "Marca")]
