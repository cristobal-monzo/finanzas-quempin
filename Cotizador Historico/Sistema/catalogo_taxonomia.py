# -*- coding: utf-8 -*-
"""
catalogo_taxonomia.py -- los DATOS de la taxonomia del Cotizador Historico:
que categorias existen, que materiales se reconocen y que palabras llevan a
cada familia de producto. La logica que los aplica vive en taxonomia.py.

Este archivo es el que se edita para corregir o extender la clasificacion
(el motor casi nunca cambia). Cada regla es:

    (terminos, categoria, subcategoria, familia, prioridad_extra)

- terminos: palabras o frases. El match es por PALABRA COMPLETA sobre la
  raiz de cada palabra, nunca por substring -- por eso "Steelgen" no activa
  "tee" y "dado que" no activa "dado" (dos errores reales del clasificador
  anterior, ver docs/superpowers/specs/2026-09-08-taxonomia-cotizador-design.md).
- familia: el sustantivo generico del producto. Es explicito a proposito: el
  sistema anterior usaba "la primera palabra del nombre" y producia carpetas
  como "Compras", "Redes" (por "Red Bull") o "Muffines".
- prioridad_extra: desempate. Positivo = mas especifico (gana), negativo =
  ultimo recurso. Ver taxonomia.clasificar para la formula completa del score.

Al agregar una regla, correr:
    py -3.14 ".claude/skills/Cotizador_Historico/driver.py" categorias
y revisar que no se haya movido nada que ya estaba bien clasificado.
"""

# categoria -> (icono, cotizable)
# cotizable=False son gastos de operacion: no son productos que se coticen,
# no entran a las estadisticas de precio del carrito ni a los KPIs de catalogo.
CATEGORIAS = {
    'Piping y Fittings':            ('\U0001F527', True),
    'Válvulas y Control de Flujo':  ('\U0001F6E0', True),
    'Instrumentación y Medición':   ('\U0001F321', True),
    'Bombas y Equipos Hidráulicos': ('⚙', True),
    'Calefacción y Combustión':     ('\U0001F525', True),
    'Aislación y Refractarios':     ('\U0001F9F1', True),
    'Soldadura y Gases':            ('\U0001F6E1', True),
    'Abrasivos y Corte':            ('\U0001FA9A', True),
    'Fijaciones':                   ('\U0001F529', True),
    'Sellado y Lubricantes':        ('\U0001F9F4', True),
    'Herramientas Manuales':        ('\U0001F528', True),
    'Herramientas Eléctricas':      ('\U0001F50C', True),
    'Materiales Eléctricos':        ('⚡', True),
    'Pinturas y Recubrimientos':    ('\U0001F3A8', True),
    'Perfilería y Maderas':         ('\U0001F4CF', True),
    'Seguridad Industrial (EPP)':   ('\U0001F9BA', True),
    'Aseo y Oficina':               ('\U0001F9F9', True),
    'Alimentación':                 ('\U0001F37D', False),
    'Transporte y Logística':       ('\U0001F69A', False),
    'Arriendos y Servicios':        ('\U0001F4CB', False),
    'Sin Clasificar':               ('❓', True),
}

# Materiales: (lemas, nombre canonico). El material es una FACETA, no una
# categoria: entra a la hoja y al filtro, no al arbol de carpetas.
MATERIALES = [
    # Los materiales de SISTEMA (PPR, PEX, PVC) van primero a proposito: un
    # "Terminal DZR PEX" es un fitting de bronce DZR para tuberia PEX, y
    # quien lo busca lo busca como PEX, que es la instalacion de la que
    # forma parte -- no como bronce, que es de lo que esta hecho.
    (['ppr'], 'PPR'),
    (['pex'], 'PEX'),
    (['pvc', 'vinilit', 'cementada', 'cementado', 'cementar'], 'PVC'),
    (['inoxidable', 'inox', 'ss304', 'ss316', 'aisi'], 'Inoxidable'),
    (['cobre', 'cu'], 'Cobre'),
    (['bronce', 'br', 'dzr', 'latón', 'laton'], 'Bronce'),
    (['galvanizado', 'galvanizada', 'galv', 'zincado', 'zinc'], 'Galvanizado'),
    (['hdpe', 'polipropileno', 'plastico', 'nylon'], 'Plástico'),
    (['aluminio'], 'Aluminio'),
    # 'negro'/'negra' sueltos NO van aca: en este catalogo son colores
    # ("Poleron termico negro", "Sellante alta temperatura negro"). El acero
    # negro se reconoce por la frase completa o por su norma.
    (['acero negro', 'fierro negro', 'caneria negra', 'canieria negra', 'cañeria negra',
      'punta negra', 'a53', 'astm', 'sch40', 'erw', 'a234'], 'Acero Negro'),
    (['acero'], 'Acero'),
]

# Familias que se comparan por medida: sin medida no se promedian precios
# (pero el item SIGUE VISIBLE, marcado "sin medida").
CATEGORIAS_CON_MEDIDA = {'Piping y Fittings', 'Fijaciones', 'Válvulas y Control de Flujo'}

# Categorias donde el material DEFINE el producto y por lo tanto entra a la
# hoja: un codo de cobre y uno de bronce son productos distintos y su precio
# no se promedia. Fuera de estas, el material se sigue detectando y sirve de
# filtro, pero no parte la hoja -- si no, un "Guante de plastico" quedaba
# separado de "Guante" y un visor con marco de aluminio se volvia un producto
# de aluminio.
CATEGORIAS_CON_MATERIAL = {'Piping y Fittings', 'Válvulas y Control de Flujo', 'Fijaciones',
                           'Perfilería y Maderas'}

# Categorias cuya subcategoria es el MATERIAL en vez del tipo de pieza
# (pedido del usuario 2026-09-09: "que se pueda diferenciar facilmente entre
# PEX, Cobre, inoxidable, acero, PPR, otros"). El tipo de pieza no se pierde:
# sigue al frente del nombre de la hoja ("Codo de Bronce 1.1/4"), y las hojas
# se listan alfabeticamente para que todos los codos queden juntos.
# Se eligio material-como-subcategoria y no "tipo de Material" (Codos de
# Cobre, Codos de PPR...) porque sobre el catalogo real eso da 52 carpetas,
# la mayoria de 1 o 2 compras, contra 9 carpetas de 3 a 52 compras asi.
CATEGORIAS_SUBCATEGORIA_POR_MATERIAL = {'Piping y Fittings'}
SUBCATEGORIA_SIN_MATERIAL = 'Otros materiales'

# Categorias donde el producto se identifica por su MODELO, no por un
# generico (pedido del usuario 2026-09-09: "quiero que el titulo de las
# bombas sea tipo 'Bomba circuladora A 80/180 XM', mostrando el modelo").
# Dos calderas de marcas distintas no son el mismo producto y su precio no
# se promedia: en el catalogo real habia 3 calderas de $1,0M a $4,2M
# compartiendo una sola hoja llamada "Caldera".
CATEGORIAS_CON_MODELO = {'Bombas y Equipos Hidráulicos', 'Calefacción y Combustión',
                         'Herramientas Eléctricas', 'Instrumentación y Medición',
                         # Un electrodo 6010 y uno 7018 son productos
                         # distintos (3,7x de diferencia medida), igual que
                         # la soldadura de plata al 6% y la al 15% (2,6x), o
                         # una pasta de soldar de 50gr y una de 500gr.
                         'Soldadura y Gases'}

# Categorias de importancia menor para un cotizador: se muestran aparte, en
# una seccion secundaria debajo del listado principal (pedido del usuario
# 2026-09-09). Son los gastos de operacion mas la cola de trabajo de lo que
# todavia no se puede clasificar.
CATEGORIAS_SECUNDARIAS = {'Transporte y Logística', 'Alimentación', 'Arriendos y Servicios',
                          'Sin Clasificar'}

# (terminos, categoria, subcategoria, familia, prioridad_extra)
REGLAS = [
    # ---------------- Piping y Fittings ----------------
    (['cañeria', 'caneria', 'canieria', 'tuberia'], 'Piping y Fittings', 'Cañerías y Tubos', 'Cañería', 0),
    (['tubo', 'tira'], 'Piping y Fittings', 'Cañerías y Tubos', 'Tubo', -5),
    (['codo'], 'Piping y Fittings', 'Codos y Curvas', 'Codo', 0),
    (['curva'], 'Piping y Fittings', 'Codos y Curvas', 'Curva', 0),
    (['tee'], 'Piping y Fittings', 'Tees y Cruces', 'Tee', 0),
    (['cruz'], 'Piping y Fittings', 'Tees y Cruces', 'Cruz', 0),
    (['copla', 'coupling'], 'Piping y Fittings', 'Coplas y Uniones', 'Copla', 0),
    (['union', 'union americana', 'u amer', 'machon', 'pomel', 'racord', 'union rapida'],
     'Piping y Fittings', 'Coplas y Uniones', 'Unión', 0),
    (['bushing', 'buje'], 'Piping y Fittings', 'Reducciones', 'Bushing', 0),
    (['reduccion', 'reductor', 'reductora', 'reduc'], 'Piping y Fittings', 'Reducciones', 'Reducción', 0),
    (['niple', 'neplo'], 'Piping y Fittings', 'Niples y Puntas', 'Niple', 0),
    (['punta negra', 'punta trefilada'], 'Piping y Fittings', 'Niples y Puntas', 'Punta Negra', 5),
    (['hilo tuerca'], 'Piping y Fittings', 'Niples y Puntas', 'Hilo Tuerca', 5),
    (['canastillo'], 'Válvulas y Control de Flujo', 'Filtros', 'Canastillo', 5),
    (['terminal', 'termo', 'term'], 'Piping y Fittings', 'Terminales y Adaptadores', 'Terminal', 0),
    (['conector'], 'Piping y Fittings', 'Terminales y Adaptadores', 'Conector', 0),
    (['adaptador'], 'Piping y Fittings', 'Terminales y Adaptadores', 'Adaptador', -5),
    (['cono'], 'Piping y Fittings', 'Terminales y Adaptadores', 'Cono', -5),
    (['tapon', 'tapagorro', 'sol placa'], 'Piping y Fittings', 'Tapones', 'Tapón', 0),
    (['flange', 'brida'], 'Piping y Fittings', 'Flanges', 'Flange', 0),
    (['abrazadera'], 'Piping y Fittings', 'Soportes y Abrazaderas', 'Abrazadera', 0),
    (['flexible', 'manguera'], 'Piping y Fittings', 'Flexibles', 'Flexible', 0),

    # ---------------- Válvulas y Control ----------------
    (['valvula bola', 'valvula de bola'], 'Válvulas y Control de Flujo', 'Válvulas de Bola', 'Válvula de Bola', 10),
    (['valvula retencion', 'valvula de retencion'], 'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula de Retención', 10),
    (['valvula alivio', 'valvula de alivio'], 'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula de Alivio', 10),
    (['valvula corte', 'valvula de corte', 'valvula bloqueo'], 'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula de Corte', 10),
    (['valvula fancoil', 'valvula angular', 'valvula termostatica'], 'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula Especial', 10),
    (['valvula'], 'Válvulas y Control de Flujo', 'Válvulas de Bola', 'Válvula', 0),
    (['alimat', 'flow control'], 'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula de Llenado', 5),
    (['purga', 'venteo', 'eliminador de aire'], 'Válvulas y Control de Flujo', 'Purgas y Venteos', 'Purga', 0),
    (['filtro'], 'Válvulas y Control de Flujo', 'Filtros', 'Filtro', 0),
    (['anodo'], 'Válvulas y Control de Flujo', 'Ánodos', 'Ánodo', 0),

    # ---------------- Instrumentación ----------------
    (['manometro', 'manovacuometro'], 'Instrumentación y Medición', 'Manómetros', 'Manómetro', 0),
    (['vacuometro'], 'Instrumentación y Medición', 'Manómetros', 'Vacuómetro', 0),
    (['termometro', 'termocupla', 'termopar', 'sonda'], 'Instrumentación y Medición', 'Termómetros y Sondas', 'Termómetro', 0),
    (['termopozo'], 'Instrumentación y Medición', 'Termómetros y Sondas', 'Termopozo', 0),
    (['multimetro', 'amperimetro', 'voltimetro', 'pinza amperimetrica'], 'Instrumentación y Medición', 'Instrumentos Eléctricos', 'Multímetro', 0),
    (['caudalimetro', 'flujometro'], 'Instrumentación y Medición', 'Caudalímetros', 'Caudalímetro', 0),
    (['interruptor de nivel', 'interruptor nivel'], 'Instrumentación y Medición', 'Nivel', 'Interruptor de Nivel', 10),

    # ---------------- Bombas y equipos hidráulicos ----------------
    (['bomba'], 'Bombas y Equipos Hidráulicos', 'Bombas', 'Bomba', 0),
    (['estanque'], 'Bombas y Equipos Hidráulicos', 'Estanques', 'Estanque', 0),
    (['impulsor', 'rodete'], 'Bombas y Equipos Hidráulicos', 'Repuestos', 'Impulsor', 0),
    (['arrestallama'], 'Bombas y Equipos Hidráulicos', 'Repuestos', 'Arrestallama', 0),
    (['rodamiento'], 'Bombas y Equipos Hidráulicos', 'Repuestos', 'Rodamiento', 0),

    # ---------------- Calefacción y combustión ----------------
    (['caldera'], 'Calefacción y Combustión', 'Calderas', 'Caldera', 0),
    (['radiador'], 'Calefacción y Combustión', 'Radiadores', 'Radiador', 0),
    (['quemador'], 'Calefacción y Combustión', 'Quemadores', 'Quemador', 5),
    (['termostato', 'presostato'], 'Calefacción y Combustión', 'Termostatos y Presostatos', 'Termostato', 0),
    (['contactor', 'rele'], 'Calefacción y Combustión', 'Control', 'Contactor', 0),
    (['kit escape', 'chimenea', 'cometa', 'cometi', 'gorro'], 'Calefacción y Combustión', 'Chimeneas y Escapes', 'Escape', 0),

    # ---------------- Aislación y refractarios ----------------
    (['coquilla', 'aislante', 'aislacion', 'aerotape'], 'Aislación y Refractarios', 'Aislación Térmica', 'Aislante', 0),
    (['manta fibra', 'fibra ceramica', 'lana mineral'], 'Aislación y Refractarios', 'Mantas y Fibras', 'Manta', 5),
    (['refractario'], 'Aislación y Refractarios', 'Refractarios', 'Refractario', 5),

    # ---------------- Soldadura y gases ----------------
    (['electrodo'], 'Soldadura y Gases', 'Electrodos', 'Electrodo', 0),
    # La soldadura de plata es su propia subcategoria (pedido del usuario
    # 2026-09-09): cuesta un orden de magnitud mas que la de estano y
    # mezclarlas en "Aportes" no dice nada util sobre ninguna de las dos.
    (['soldadura plata', 'soldadura de plata', 'soldadura al plata', 'barra plata'],
     'Soldadura y Gases', 'Soldadura de Plata', 'Soldadura de Plata', 12),
    (['soldadura', 'carrete soldadura', 'carrete de soldadura'], 'Soldadura y Gases', 'Aportes', 'Soldadura', 0),
    # Prioridad sobre la regla de plata: un "Fundente para plata" es un
    # fundente, no un aporte de plata.
    (['fundente'], 'Soldadura y Gases', 'Fundentes', 'Fundente', 15),
    (['gas mapp', 'tubo gas', 'tubo de gas', 'oxigeno', 'argon', 'acetileno'], 'Soldadura y Gases', 'Gases', 'Gas', 5),
    (['soplete'], 'Soldadura y Gases', 'Sopletes', 'Soplete', 0),
    (['pasta soldar', 'pasta de soldar', 'pasta para soldar'], 'Soldadura y Gases', 'Fundentes', 'Pasta de Soldar', 10),

    # ---------------- Abrasivos y corte ----------------
    (['disco corte', 'disco de corte'], 'Abrasivos y Corte', 'Discos', 'Disco de Corte', 10),
    (['disco desbaste', 'disco de desbaste'], 'Abrasivos y Corte', 'Discos', 'Disco de Desbaste', 10),
    (['disco flap', 'disco laminado'], 'Abrasivos y Corte', 'Discos', 'Disco Flap', 10),
    (['disco'], 'Abrasivos y Corte', 'Discos', 'Disco', 0),
    (['lija'], 'Abrasivos y Corte', 'Lijas', 'Lija', 0),
    (['grata', 'escobilla de acero', 'escobilla acero'], 'Abrasivos y Corte', 'Gratas y Escobillas', 'Grata', 0),
    (['hoja de sierra', 'hoja sierra', 'sierra copa', 'sierra de corte'], 'Abrasivos y Corte', 'Hojas de Sierra', 'Hoja de Sierra', 10),
    (['broca'], 'Abrasivos y Corte', 'Brocas', 'Broca', 0),

    # ---------------- Fijaciones ----------------
    (['perno'], 'Fijaciones', 'Pernos', 'Perno', 0),
    (['tornillo'], 'Fijaciones', 'Tornillos', 'Tornillo', 0),
    (['autoperforante'], 'Fijaciones', 'Tornillos', 'Autoperforante', 0),
    (['tuerca'], 'Fijaciones', 'Tuercas', 'Tuerca', 0),
    (['golilla', 'arandela'], 'Fijaciones', 'Golillas', 'Golilla', 0),
    (['remache'], 'Fijaciones', 'Remaches', 'Remache', 0),
    (['clavo'], 'Fijaciones', 'Clavos', 'Clavo', 0),
    (['tarugo'], 'Fijaciones', 'Tarugos', 'Tarugo', 0),
    (['amarra', 'amarra plastica'], 'Fijaciones', 'Amarras', 'Amarra', 0),
    (['varilla', 'varilla roscada', 'hilo acero', 'barra roscada'], 'Fijaciones', 'Varillas y Hilos', 'Varilla', 0),
    (['hilo'], 'Fijaciones', 'Varillas y Hilos', 'Hilo', -8),
    (['cuerda', 'soga', 'polysteel', 'driza'], 'Fijaciones', 'Izaje y Amarre', 'Cuerda', 0),
    (['grillete'], 'Fijaciones', 'Izaje y Amarre', 'Grillete', 0),
    (['guardacabo'], 'Fijaciones', 'Izaje y Amarre', 'Guardacabo', 0),
    (['prensa cable'], 'Fijaciones', 'Izaje y Amarre', 'Prensa Cable', 5),
    (['cable de acero'], 'Fijaciones', 'Izaje y Amarre', 'Cable de Acero', 5),
    (['eslinga'], 'Fijaciones', 'Izaje y Amarre', 'Eslinga', 0),
    (['cadena'], 'Fijaciones', 'Izaje y Amarre', 'Cadena', 0),
    (['tapatornillo'], 'Fijaciones', 'Tornillos', 'Tapatornillo', 5),

    # ---------------- Sellado y lubricantes ----------------
    (['teflon liquido', 'teflon anaerobico'], 'Sellado y Lubricantes', 'Siliconas y Sellantes', 'Teflón Líquido', 12),
    (['teflon'], 'Sellado y Lubricantes', 'Teflón y Sellos de Hilo', 'Teflón', 0),
    (['cinta sella hilo', 'sella hilo'], 'Sellado y Lubricantes', 'Teflón y Sellos de Hilo', 'Cinta Sella Hilo', 10),
    (['silicona', 'sellante', 'sellador', 'tapagotera'], 'Sellado y Lubricantes', 'Siliconas y Sellantes', 'Sellante', 0),
    (['adhesivo', 'pegamento'], 'Sellado y Lubricantes', 'Adhesivos', 'Adhesivo', 0),
    (['empaquetadura', 'sello conico', 'sello', 'oring', 'o-ring', 'epdm', 'graphinox',
      'plancha teflon', 'plancha de teflon'], 'Sellado y Lubricantes', 'Empaquetaduras', 'Empaquetadura', 5),
    (['lubricante', 'grasa', 'aflojador', 'wd-40', 'wd40', 'desoxidante'], 'Sellado y Lubricantes', 'Lubricantes', 'Lubricante', 0),
    (['solutech', 'aditivo', 'anticongelante'], 'Sellado y Lubricantes', 'Aditivos Químicos', 'Aditivo', 0),
    (['cinta amarre', 'cinta de amarre'], 'Fijaciones', 'Izaje y Amarre', 'Cinta de Amarre', 10),
    (['cinta electrica', 'cinta aisladora', 'cinta aislante'], 'Materiales Eléctricos', 'Cintas', 'Cinta Eléctrica', 10),
    (['cinta aluminio', 'cinta de aluminio', 'huincha ductos'], 'Aislación y Refractarios', 'Cintas Térmicas', 'Cinta de Aluminio', 10),
    (['cinta'], 'Sellado y Lubricantes', 'Cintas', 'Cinta', -10),

    # ---------------- Herramientas manuales ----------------
    (['llave'], 'Herramientas Manuales', 'Llaves', 'Llave', 0),
    (['destornillador', 'atornillador'], 'Herramientas Manuales', 'Destornilladores', 'Destornillador', 0),
    (['martillo', 'mazo'], 'Herramientas Manuales', 'Martillos y Mazos', 'Martillo', 0),
    (['alicate', 'prensa', 'tenaza'], 'Herramientas Manuales', 'Alicates y Prensas', 'Alicate', 0),
    (['cuchillo', 'cuchilla', 'cortante', 'cartonero', 'hoja cuchillo', 'hojas cuchillo'],
     'Herramientas Manuales', 'Corte Manual', 'Cuchillo', 0),
    (['cortatubo', 'corta tubo', 'cortatubos'], 'Herramientas Manuales', 'Corte Manual', 'Cortatubos', 5),
    (['serrucho', 'marco sierra', 'sierra'], 'Herramientas Manuales', 'Corte Manual', 'Sierra', -5),
    (['huincha'], 'Herramientas Manuales', 'Medición', 'Huincha', 0),
    (['nivel'], 'Herramientas Manuales', 'Medición', 'Nivel', 0),
    (['escuadra'], 'Herramientas Manuales', 'Medición', 'Escuadra', 0),
    (['pie de metro', 'calibrador'], 'Herramientas Manuales', 'Medición', 'Pie de Metro', 0),
    (['dado', 'punta atornillar', 'punta impacto', 'puntas', 'punta', 'aumentador', 'reductor impacto'],
     'Herramientas Manuales', 'Dados y Puntas', 'Dado', -5),
    (['calafatera', 'pistola calafateo', 'pistola calafatera'], 'Herramientas Manuales', 'Aplicación', 'Calafatera', 5),
    (['remachadora'], 'Herramientas Manuales', 'Aplicación', 'Remachadora', 5),
    (['curvadora'], 'Herramientas Manuales', 'Aplicación', 'Curvadora', 10),
    (['sacabocado'], 'Herramientas Manuales', 'Otras Herramientas', 'Sacabocado', -5),
    (['cincel'], 'Herramientas Manuales', 'Otras Herramientas', 'Cincel', -5),
    (['espatula', 'plana botadora'], 'Herramientas Manuales', 'Otras Herramientas', 'Espátula', -5),
    (['picaporte', 'barrote'], 'Herramientas Manuales', 'Otras Herramientas', 'Herraje', -5),
    (['escobillon'], 'Aseo y Oficina', 'Limpieza', 'Escobillón', -5),
    (['pala'], 'Aseo y Oficina', 'Limpieza', 'Pala', -5),
    (['bolso', 'caja de herramienta', 'set herramienta', 'juego de herramienta', 'kit herramienta'],
     'Herramientas Manuales', 'Sets y Contenedores', 'Set de Herramientas', 5),
    # 'set'/'juego'/'kit' solos: ultimo recurso. Cualquier regla especifica
    # ('kit bomba' -> Bomba) gana por el bono de nombre y por longitud.
    (['set', 'juego', 'kit'], 'Herramientas Manuales', 'Sets y Contenedores', 'Set', -18),

    # ---------------- Herramientas eléctricas ----------------
    (['taladro', 'atornillador inalambrico', 'rotomartillo'], 'Herramientas Eléctricas', 'Taladros', 'Taladro', 5),
    (['esmeril', 'amoladora', 'pulidora'], 'Herramientas Eléctricas', 'Esmeriles', 'Esmeril', 0),
    (['hidrolavadora'], 'Herramientas Eléctricas', 'Hidrolavadoras', 'Hidrolavadora', 0),
    (['soldadora'], 'Herramientas Eléctricas', 'Soldadoras', 'Soldadora', 5),
    (['compresor', 'soplador'], 'Herramientas Eléctricas', 'Compresores', 'Compresor', 0),
    (['fusora', 'termofusora'], 'Herramientas Eléctricas', 'Máquinas Especiales', 'Máquina Fusora', 5),
    (['generador'], 'Herramientas Eléctricas', 'Generadores', 'Generador', 0),
    (['tecle', 'huinche', 'polipasto'], 'Herramientas Eléctricas', 'Elevación', 'Tecle', 5),

    # ---------------- Materiales eléctricos ----------------
    (['enchufe', 'toma corriente', 'tomacorriente', 'schuko'], 'Materiales Eléctricos', 'Enchufes', 'Enchufe', 0),
    (['cable', 'extension electrica', 'extension', 'alargador'], 'Materiales Eléctricos', 'Cables y Extensiones', 'Cable', -5),
    (['conduit', 'canalizacion', 'bandeja portacable'], 'Materiales Eléctricos', 'Conduit', 'Conduit', 5),
    (['panel electrico', 'tablero', 'armario metalico', 'caja ti'], 'Materiales Eléctricos', 'Tableros', 'Tablero', 5),
    (['luz de trabajo', 'luminaria'], 'Materiales Eléctricos', 'Iluminación', 'Luz de Trabajo', 5),
    (['foco', 'ampolleta', 'led', 'tubo led'], 'Materiales Eléctricos', 'Iluminación', 'Ampolleta', 0),
    (['pila', 'bateria'], 'Materiales Eléctricos', 'Pilas', 'Pila', 0),
    (['interruptor', 'automatico', 'diferencial'], 'Materiales Eléctricos', 'Protección', 'Interruptor', -5),

    # ---------------- Pinturas ----------------
    (['pintura', 'esmalte', 'anticorrosivo', 'barniz', 'latex'], 'Pinturas y Recubrimientos', 'Pinturas', 'Pintura', 0),
    (['brocha', 'rodillo'], 'Pinturas y Recubrimientos', 'Brochas y Rodillos', 'Brocha', 0),
    (['aguarras', 'diluyente', 'thinner'], 'Pinturas y Recubrimientos', 'Diluyentes', 'Diluyente', 0),
    (['spray'], 'Pinturas y Recubrimientos', 'Sprays', 'Spray', -5),

    # ---------------- Perfilería y maderas ----------------
    (['perfil', 'tubo cuadrado', 'tubo rectangular', 'tubo estructural'], 'Perfilería y Maderas', 'Perfiles', 'Perfil', 5),
    (['platina', 'pletina', 'angulo'], 'Perfilería y Maderas', 'Platinas y Ángulos', 'Platina', 0),
    (['plancha', 'placa', 'policarbonato', 'moldura'], 'Perfilería y Maderas', 'Planchas', 'Plancha', 0),
    (['fierro construccion', 'fierro'], 'Perfilería y Maderas', 'Fierro', 'Fierro', 0),
    (['pino', 'madera', 'viga', 'terciado'], 'Perfilería y Maderas', 'Maderas', 'Madera', 0),

    # ---------------- EPP ----------------
    (['guante'], 'Seguridad Industrial (EPP)', 'Guantes', 'Guante', 0),
    (['lente', 'antiparra', 'visor', 'careta'], 'Seguridad Industrial (EPP)', 'Protección Visual', 'Lente de Seguridad', 0),
    # 'oido'/'auditivo' solos y con prioridad alta: cualquier item que los
    # mencione es proteccion auditiva. Sin esto, "Tapones para oidos" caia en
    # Piping por la palabra "tapon".
    (['oido', 'auditivo', 'tapon reusable', 'protector auricular'],
     'Seguridad Industrial (EPP)', 'Protección Auditiva', 'Tapón Auditivo', 20),
    (['casco'], 'Seguridad Industrial (EPP)', 'Cascos', 'Casco', 0),
    (['overol'], 'Seguridad Industrial (EPP)', 'Ropa de Trabajo', 'Overol', 0),
    (['buzo'], 'Seguridad Industrial (EPP)', 'Ropa de Trabajo', 'Buzo', 0),
    (['chaleco'], 'Seguridad Industrial (EPP)', 'Ropa de Trabajo', 'Chaleco', 0),
    (['poleron', 'polar'], 'Seguridad Industrial (EPP)', 'Ropa de Trabajo', 'Polerón', 0),
    (['pantalon'], 'Seguridad Industrial (EPP)', 'Ropa de Trabajo', 'Pantalón', 0),
    (['coleto', 'delantal'], 'Seguridad Industrial (EPP)', 'Ropa de Trabajo', 'Coleto', 0),
    (['cofia', 'gorro de seguridad'], 'Seguridad Industrial (EPP)', 'Ropa de Trabajo', 'Cofia', 0),
    (['zapato', 'bota', 'calzado', 'cubre calzado', 'plantilla'], 'Seguridad Industrial (EPP)', 'Calzado', 'Calzado', 0),
    (['arnes', 'linea de vida', 'cabo de vida'], 'Seguridad Industrial (EPP)', 'Anticaídas', 'Arnés', 0),
    (['cono de señalizacion', 'cono naranja', 'cono vial', 'barra conectora', 'cinta peligro',
      'cinta de peligro', 'señaletica', 'letrero'],
     'Seguridad Industrial (EPP)', 'Señalización', 'Señalización', 5),

    # ---------------- Aseo y oficina ----------------
    (['pano', 'paño', 'microfibra'], 'Aseo y Oficina', 'Paños y Esponjas', 'Paño', 0),
    (['esponja'], 'Aseo y Oficina', 'Paños y Esponjas', 'Esponja', 0),
    (['toalla'], 'Aseo y Oficina', 'Paños y Esponjas', 'Toalla', 0),
    (['bolsa'], 'Aseo y Oficina', 'Bolsas y Sacos', 'Bolsa', 0),
    (['saco', 'saco escombro', 'saco de escombro'], 'Aseo y Oficina', 'Bolsas y Sacos', 'Saco', 0),
    (['desinfectante', 'toalla desinfectante'], 'Aseo y Oficina', 'Limpieza', 'Desinfectante', 0),
    (['detergente', 'limpiador', 'cloro', 'jabon'], 'Aseo y Oficina', 'Limpieza', 'Limpiador', 0),
    (['manifold', 'libro manifold', 'boleta talonario'], 'Aseo y Oficina', 'Papelería', 'Manifold', 0),
    (['lapiz', 'marcador', 'destacador'], 'Aseo y Oficina', 'Papelería', 'Lápiz', 0),
    (['libro', 'papel', 'archivador', 'cuaderno'], 'Aseo y Oficina', 'Papelería', 'Papelería', -5),

    # ---------------- Alimentación (gasto) ----------------
    (['almuerzo', 'colacion', 'cena', 'desayuno', 'comida', 'menu'], 'Alimentación', 'Comidas', 'Almuerzo', 0),
    (['sandwich', 'miga', 'hamburguesa', 'completo', 'empanada', 'pizza', 'snack'], 'Alimentación', 'Sándwiches y Snacks', 'Sándwich', 0),
    (['bebida', 'coca cola', 'pepsi', 'sprite', 'fanta', 'bilz', 'gatorade', 'powerade', 'monster',
      'red bull', 'jugo', 'nectar', 'agua mineral', 'agua', 'cafe', 'te', 'leche'],
     'Alimentación', 'Bebidas', 'Bebida', 0),
    (['galleta', 'muffin', 'medialuna', 'helado', 'chocolate', 'barra de cereal', 'protein', 'dulce',
      'combo', 'consumo', 'nuggets', 'papas'],
     'Alimentación', 'Sándwiches y Snacks', 'Snack', 0),
    (['supermercado', 'ingrediente', 'abarrote'], 'Alimentación', 'Supermercado', 'Supermercado', 0),
    (['alimentacion'], 'Alimentación', 'Comidas', 'Alimentación', 0),

    # ---------------- Transporte y logística (gasto) ----------------
    (['peaje'], 'Transporte y Logística', 'Peajes', 'Peaje', 10),
    (['combustible', 'gasolina', 'bencina', 'petroleo', 'diesel', 'parafina', 'octanos'],
     'Transporte y Logística', 'Combustible', 'Combustible', 10),
    (['estacionamiento', 'parquimetro'], 'Transporte y Logística', 'Estacionamiento', 'Estacionamiento', 10),
    (['flete', 'despacho', 'envio', 'encomienda', 'courier', 'starken', 'chilexpress', 'embarque',
      'transporte', 'transporte de carga'],
     'Transporte y Logística', 'Fletes y Despachos', 'Flete', 10),
    (['pasaje', 'vuelo', 'equipaje', 'ticket aereo', 'tur bus'], 'Transporte y Logística', 'Pasajes', 'Pasaje', 10),
    (['arriendo vehiculo', 'arriendo auto', 'arriendo camioneta', 'arriendo camion', 'arriendo furgon',
      'arriendo de vehiculo', 'arriendo de auto', 'arriendo de camioneta', 'arriendo de camion'],
     'Transporte y Logística', 'Arriendo de Vehículos', 'Arriendo de Vehículo', 20),
    (['tasa', 'impuesto'], 'Transporte y Logística', 'Cargos y Tasas', 'Cargo', -5),

    # ---------------- Arriendos y servicios (gasto) ----------------
    (['andamio', 'arriendo andamio', 'bandeja euro', 'baranda', 'rodapie', 'estabilizador', 'nivelador multi'],
     'Arriendos y Servicios', 'Arriendo de Andamios', 'Andamio', 15),
    (['arriendo'], 'Arriendos y Servicios', 'Arriendo de Equipos', 'Arriendo', -5),
    (['mano de obra', 'servicio', 'instalacion', 'confeccion', 'reparacion', 'mantencion'],
     'Arriendos y Servicios', 'Servicios', 'Servicio', -5),
    (['alojamiento', 'hostel', 'hotel', 'viatico'], 'Arriendos y Servicios', 'Alojamiento y Viáticos', 'Alojamiento', 10),
    (['seguro', 'propina', 'garantia extendida', 'otros cargos'], 'Arriendos y Servicios', 'Otros Gastos', 'Otro Gasto', -10),
    (['compra sin desglose', 'materiales varios', 'compra de materiales', 'materiales de ferreteria', 'ferreteria'],
     'Arriendos y Servicios', 'Compras sin Desglose', 'Compra sin Desglose', 5),
]
