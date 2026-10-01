# -*- coding: utf-8 -*-
"""
catalogo_presentacion.py -- los DATOS de como se escribe cada cosa.

El motor esta en presentacion.py; aca solo viven las listas, para que
agregar una sigla nueva no obligue a leer codigo. Mismo patron que
taxonomia/catalogo_taxonomia y atributos/catalogo_atributos.

Estas listas NO deciden nada sobre la clasificacion: una palabra que este
aca no se vuelve marca, material ni tipo de producto. Solo cambian como se
escribe algo que el catalogo ya escribio de varias formas.
"""

# ---------------------------------------------------------------------------
# SIGLAS
# ---------------------------------------------------------------------------
# Siglas tecnicas leidas del catalogo real, con su escritura correcta. Van
# aca y no en una regla general de "mayusculas" porque no existe tal regla:
# "PVC" va en mayusculas, "bar" en minusculas, "Ø" es un simbolo. Cualquier
# heuristica generica convierte "PVC" en "Pvc".
SIGLAS = [
    # normas y grados
    "ASTM", "AISI", "SAE", "AWS", "ASME", "ANSI", "DIN", "ISO", "NCh",
    # roscas y conexiones
    "NPT", "NPTF", "BSP", "BSPT", "BSPP", "HI-HI", "HI-HE", "HE-HE",
    # medidas normalizadas de canerias
    "DN", "NPS", "SCH", "PN",
    # unidades
    # (nunca de una sola letra: "A" y "V" convertirian la preposicion "a" y
    #  cualquier "v" suelta en una unidad)
    "PSI", "bar", "mm", "cm", "kg", "gr", "ml", "cc", "lts", "mts",
    "HP", "RPM", "VAC", "VDC", "kW",
    # materiales y plasticos
    "PVC", "CPVC", "PPR", "PEX", "HDPE", "PTFE", "EPDM", "NBR", "MDF",
    "OSB", "HSS", "DZR", "ABS", "PET",
    # varios del rubro
    "LPG", "GLP", "MAPP", "LED", "IP", "EPP", "UV", "IVA", "STD", "XL",
]


# ---------------------------------------------------------------------------
# PALABRAS CANONICAS
# ---------------------------------------------------------------------------
# Escape hatch para las palabras que la regla automatica de tildes no puede
# resolver sola (ver presentacion.unificar_ortografia): empates donde las dos
# escrituras son palabras distintas del castellano, o terminos del rubro con
# una forma preferida por el equipo.
#
# Esta vacia a proposito. Si se llena, cada entrada deberia poder explicarse
# en una linea; si hay que agregar muchas, probablemente la regla automatica
# esta mal y hay que arreglarla a ella, no la lista.
PALABRAS_CANONICAS = [
]
