# -*- coding: utf-8 -*-
"""
catalogo_taxonomia.py -- los DATOS de la taxonomia del Cotizador Historico:
que categorias existen y que palabras identifican a cada TIPO de producto.
La logica que los aplica vive en taxonomia.py; los materiales, terminaciones
y esquemas de medida, en catalogo_atributos.py.

Este archivo es el que se edita para corregir o extender la clasificacion
(el motor casi nunca cambia). Cada regla es:

    (terminos, categoria, subcategoria, tipo, prioridad_extra)

- terminos: palabras o frases. El match es por PALABRA COMPLETA sobre la
  raiz de cada palabra, nunca por substring -- por eso "Steelgen" no activa
  "tee" y "dado que" no activa "dado" (dos errores reales del clasificador
  anterior, ver docs/specs/2026-09-08-taxonomia-cotizador-design.md).
- tipo: QUE es el producto ("Codo", "Plancha", "Perno Hexagonal"). Es
  explicito a proposito: el sistema de 2026-07 usaba "la primera palabra del
  nombre" y producia carpetas como "Compras" o "Redes" (por "Red Bull").
- prioridad_extra: desempate. Positivo = mas especifico (gana), negativo =
  ultimo recurso. Ver taxonomia.clasificar para la formula completa.

NUNCA una palabra de MATERIAL como termino de una regla (2026-09-22): el
material es un atributo aparte (catalogo_atributos.MATERIALES). Cuando
"policarbonato" era un termino de la regla de Plancha, una plancha de
policarbonato quedaba SIN material y dentro de "Perfileria y Maderas".

Al agregar una regla, correr:
    py -3.14 ".claude/skills/Cotizador_Historico/driver.py" categorias
    py -3.14 ".claude/skills/Cotizador_Historico/driver.py" evaluacion
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
    # Hasta 2026-09-21 existia "Perfileria y Maderas": una misma carpeta con
    # planchas de policarbonato, acero y zincalum, perfiles, platinas y pino.
    # La forma (plancha, perfil) y la materialidad (madera) son ejes
    # distintos: ahora la plancha es un TIPO y el material, un atributo.
    'Planchas y Perfiles':          ('\U0001F4CF', True),
    'Maderas':                      ('\U0001FAB5', True),
    'Materiales de Construcción':   ('\U0001F3D7', True),
    'Seguridad Industrial (EPP)':   ('\U0001F9BA', True),
    'Aseo y Oficina':               ('\U0001F9F9', True),
    'Alimentación':                 ('\U0001F37D', False),
    'Transporte y Logística':       ('\U0001F69A', False),
    'Arriendos y Servicios':        ('\U0001F4CB', False),
    'Sin Clasificar':               ('❓', True),
}

# Familias que se comparan por medida: sin medida no se promedian precios
# (pero el item SIGUE VISIBLE, marcado "sin medida").
CATEGORIAS_CON_MEDIDA = {'Piping y Fittings', 'Fijaciones', 'Válvulas y Control de Flujo',
                         'Planchas y Perfiles', 'Maderas'}

# Categorias donde un entero sin unidad puede leerse como pulgada nominal
# ("Copla cobre 2 SO"). En planchas o perfiles el mismo entero son mm.
CATEGORIAS_ENTERO_ES_PULGADA = {'Piping y Fittings', 'Fijaciones', 'Válvulas y Control de Flujo'}

# Categorias donde el material DEFINE el producto y por lo tanto entra a la
# hoja: un codo de cobre y uno de bronce son productos distintos y su precio
# no se promedia; una plancha de policarbonato y una de acero, tampoco.
# Fuera de estas, el material se sigue detectando y sirve de filtro, pero no
# parte la hoja -- si no, un "Guante de plastico" quedaba separado de
# "Guante" y un visor con marco de aluminio se volvia un producto de aluminio.
CATEGORIAS_CON_MATERIAL = {'Piping y Fittings', 'Válvulas y Control de Flujo', 'Fijaciones',
                           'Planchas y Perfiles', 'Maderas'}

# Categorias cuya subcategoria es el MATERIAL en vez del tipo de pieza
# (pedido del usuario 2026-09-09: "que se pueda diferenciar facilmente entre
# PEX, Cobre, inoxidable, acero, PPR, otros"). El tipo de pieza no se pierde:
# sigue al frente del nombre de la hoja ("Codo de Bronce 1.1/4"), y las hojas
# se listan alfabeticamente para que todos los codos queden juntos.
# Se eligio material-como-subcategoria y no "tipo de Material" (Codos de
# Cobre, Codos de PPR...) porque sobre el catalogo real eso da 52 carpetas,
# la mayoria de 1 o 2 compras, contra 9 carpetas de 3 a 52 compras asi.
# Desde 2026-09-22 la carpeta es el SISTEMA de tuberia si lo hay: un terminal
# de laton DZR para PEX va en PEX, que es la instalacion de la que forma
# parte, aunque su material (el atributo) sea laton.
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

# ---------------------------------------------------------------------------
# FAMILIA DE PRODUCTO
# ---------------------------------------------------------------------------
# El nivel entre la categoria (la carpeta del dashboard) y el tipo:
# "Fittings" agrupa codos, tees y coplas; "Valvulas" las de bola, retencion y
# alivio. Por defecto la familia es la subcategoria de la regla; esta tabla
# solo lista las que se agrupan distinto.
FAMILIA_DE_SUBCATEGORIA = {
    'Codos y Curvas': 'Fittings', 'Tees y Cruces': 'Fittings', 'Coplas y Uniones': 'Fittings',
    'Reducciones': 'Fittings', 'Niples y Puntas': 'Fittings', 'Terminales y Adaptadores': 'Fittings',
    'Tapones': 'Fittings', 'Flexibles': 'Mangueras y Flexibles',
    'Válvulas de Bola': 'Válvulas', 'Válvulas Especiales': 'Válvulas', 'Otras Válvulas': 'Válvulas',
    'Manómetros': 'Instrumentación', 'Termómetros y Sondas': 'Instrumentación',
    'Instrumentos Eléctricos': 'Instrumentación', 'Caudalímetros': 'Instrumentación',
    'Nivel': 'Instrumentación', 'Refrigeración': 'Instrumentación',
    'Aislación Térmica': 'Aislación', 'Mantas y Fibras': 'Aislación', 'Refractarios': 'Aislación',
    'Cintas Térmicas': 'Aislación',
    'Madera Dimensionada': 'Maderas',
    'Enchufes': 'Accesorios Eléctricos', 'Protección': 'Accesorios Eléctricos',
    'Tableros': 'Accesorios Eléctricos', 'Iluminación': 'Accesorios Eléctricos',
    'Pilas': 'Accesorios Eléctricos',
}

# ---------------------------------------------------------------------------
# REGLAS
# ---------------------------------------------------------------------------
# (terminos, categoria, subcategoria, tipo, prioridad_extra)
REGLAS = [
    # ---------------- Piping y Fittings ----------------
    (['cañeria', 'caneria', 'canieria', 'tuberia'], 'Piping y Fittings', 'Cañerías y Tubos', 'Cañería', 0),
    (['tubo', 'tira'], 'Piping y Fittings', 'Cañerías y Tubos', 'Tubo', -5),
    (['codo'], 'Piping y Fittings', 'Codos y Curvas', 'Codo', 0),
    (['curva'], 'Piping y Fittings', 'Codos y Curvas', 'Curva', 0),
    (['tee'], 'Piping y Fittings', 'Tees y Cruces', 'Tee', 0),
    (['cruz'], 'Piping y Fittings', 'Tees y Cruces', 'Cruz', 0),
    (['copla', 'coupling'], 'Piping y Fittings', 'Coplas y Uniones', 'Copla', 0),
    (['union americana', 'u amer', 'u americana'], 'Piping y Fittings', 'Coplas y Uniones',
     'Unión Americana', 5),
    (['union', 'racord', 'union rapida', 'acople'], 'Piping y Fittings', 'Coplas y Uniones', 'Unión', 0),
    (['machon'], 'Piping y Fittings', 'Niples y Puntas', 'Machón', 0),
    (['bushing', 'buje'], 'Piping y Fittings', 'Reducciones', 'Bushing', 0),
    (['reduccion', 'reductor', 'reductora'], 'Piping y Fittings', 'Reducciones', 'Reducción', 0),
    (['niple', 'neplo'], 'Piping y Fittings', 'Niples y Puntas', 'Niple', 0),
    (['punta negra', 'punta negro', 'punta trefilada'], 'Piping y Fittings', 'Niples y Puntas',
     'Punta Negra', 5),
    (['hilo tuerca'], 'Piping y Fittings', 'Niples y Puntas', 'Hilo Tuerca', 5),
    (['canastillo'], 'Válvulas y Control de Flujo', 'Filtros', 'Canastillo', 5),
    (['terminal', 'termo', 'term'], 'Piping y Fittings', 'Terminales y Adaptadores', 'Terminal', 0),
    (['conector'], 'Piping y Fittings', 'Terminales y Adaptadores', 'Conector', 0),
    (['adaptador'], 'Piping y Fittings', 'Terminales y Adaptadores', 'Adaptador', -5),
    (['cono'], 'Piping y Fittings', 'Terminales y Adaptadores', 'Cono', -5),
    (['tapon', 'tapagorro', 'tapa gorro', 'sol placa'], 'Piping y Fittings', 'Tapones', 'Tapón', 0),
    (['flange', 'brida'], 'Piping y Fittings', 'Flanges', 'Flange', 0),
    (['abrazadera'], 'Piping y Fittings', 'Soportes y Abrazaderas', 'Abrazadera', 0),
    (['flexible', 'manguera'], 'Piping y Fittings', 'Flexibles', 'Flexible', 0),

    # ---------------- Válvulas y Control ----------------
    (['valvula bola', 'valvula de bola', 'llave de paso', 'llave paso'],
     'Válvulas y Control de Flujo', 'Válvulas de Bola', 'Válvula de Bola', 10),
    (['valvula retencion', 'valvula de retencion', 'valvula check', 'valvula antirretorno'],
     'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula de Retención', 10),
    (['valvula alivio', 'valvula de alivio', 'valvula de seguridad'],
     'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula de Alivio', 10),
    (['valvula bloqueo purga', 'valvula de bloqueo y purga'], 'Válvulas y Control de Flujo',
     'Válvulas Especiales', 'Válvula de Bloqueo y Purga', 15),
    (['valvula corte', 'valvula de corte', 'valvula bloqueo'], 'Válvulas y Control de Flujo',
     'Válvulas Especiales', 'Válvula de Corte', 10),
    (['valvula aguja', 'valvula de aguja'], 'Válvulas y Control de Flujo', 'Válvulas Especiales',
     'Válvula de Aguja', 10),
    (['valvula globo', 'valvula de globo'], 'Válvulas y Control de Flujo', 'Válvulas Especiales',
     'Válvula de Globo', 10),
    (['valvula compuerta', 'valvula de compuerta'], 'Válvulas y Control de Flujo',
     'Válvulas Especiales', 'Válvula de Compuerta', 10),
    (['valvula mariposa'], 'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula Mariposa', 10),
    (['valvula solenoide'], 'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula Solenoide', 10),
    (['valvula termostatica'], 'Válvulas y Control de Flujo', 'Válvulas Especiales',
     'Válvula Termostática', 12),
    (['valvula angular'], 'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula Angular', 10),
    (['valvula fancoil'], 'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula Fancoil', 10),
    (['valvula'], 'Válvulas y Control de Flujo', 'Otras Válvulas', 'Válvula', 0),
    (['alimat', 'flow control'], 'Válvulas y Control de Flujo', 'Válvulas Especiales', 'Válvula de Llenado', 5),
    (['purga', 'venteo', 'eliminador de aire'], 'Válvulas y Control de Flujo', 'Purgas y Venteos', 'Purga', 0),
    (['filtro y', 'filtro tipo y'], 'Válvulas y Control de Flujo', 'Filtros', 'Filtro Y', 5),
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
    (['manifold manometro', 'manifold refrigeracion'], 'Instrumentación y Medición', 'Refrigeración',
     'Manifold de Refrigeración', 10),

    # ---------------- Bombas y equipos hidráulicos ----------------
    (['bomba', 'electrobomba'], 'Bombas y Equipos Hidráulicos', 'Bombas', 'Bomba', 0),
    (['estanque'], 'Bombas y Equipos Hidráulicos', 'Estanques', 'Estanque', 0),
    (['impulsor', 'rodete'], 'Bombas y Equipos Hidráulicos', 'Repuestos', 'Impulsor', 0),
    (['arrestallama'], 'Bombas y Equipos Hidráulicos', 'Repuestos', 'Arrestallama', 0),
    (['rodamiento'], 'Bombas y Equipos Hidráulicos', 'Repuestos', 'Rodamiento', 0),

    # ---------------- Calefacción y combustión ----------------
    (['caldera'], 'Calefacción y Combustión', 'Calderas', 'Caldera', 0),
    (['radiador'], 'Calefacción y Combustión', 'Radiadores', 'Radiador', 0),
    (['quemador'], 'Calefacción y Combustión', 'Quemadores', 'Quemador', 5),
    # Boquilla de un quemador a petroleo ("Inyector 300-60B"): estaba en
    # "Sin Clasificar".
    (['inyector', 'boquilla quemador'], 'Calefacción y Combustión', 'Quemadores', 'Inyector', 0),
    (['termostato', 'presostato'], 'Calefacción y Combustión', 'Termostatos y Presostatos', 'Termostato', 0),
    (['contactor', 'rele'], 'Calefacción y Combustión', 'Control', 'Contactor', 0),
    (['kit escape', 'chimenea', 'cometa', 'cometi', 'gorro'], 'Calefacción y Combustión', 'Chimeneas y Escapes', 'Escape', 0),
    (['ventilador', 'extractor'], 'Calefacción y Combustión', 'Ventilación', 'Ventilador', 0),

    # ---------------- Aislación y refractarios ----------------
    (['coquilla'], 'Aislación y Refractarios', 'Aislación Térmica', 'Coquilla', 5),
    (['aislante', 'aislacion', 'espuma aislante'], 'Aislación y Refractarios', 'Aislación Térmica', 'Aislante', 0),
    (['aerotape', 'cinta aislante termica'], 'Aislación y Refractarios', 'Cintas Térmicas',
     'Cinta Aislante Térmica', 10),
    (['manta fibra', 'fibra ceramica', 'lana mineral'], 'Aislación y Refractarios', 'Mantas y Fibras', 'Manta', 5),
    (['refractario'], 'Aislación y Refractarios', 'Refractarios', 'Refractario', 10),

    # ---------------- Soldadura y gases ----------------
    (['electrodo'], 'Soldadura y Gases', 'Electrodos', 'Electrodo', 0),
    # La pinza porta electrodo es un accesorio: no se promedia con los
    # electrodos (su precio no tiene nada que ver).
    (['porta electrodo', 'portaelectrodo', 'pinza porta electrodo'], 'Soldadura y Gases',
     'Accesorios de Soldadura', 'Pinza Portaelectrodo', 15),
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
    # El porta sierra (arbol) no es una sierra: es el accesorio que la monta.
    (['porta sierra', 'porta sierra copa', 'portasierra'], 'Abrasivos y Corte', 'Accesorios de Corte',
     'Porta Sierra Copa', 15),
    (['broca'], 'Abrasivos y Corte', 'Brocas', 'Broca', 0),

    # ---------------- Fijaciones ----------------
    (['perno hexagonal', 'perno hex'], 'Fijaciones', 'Pernos', 'Perno Hexagonal', 5),
    (['perno anclaje', 'perno de anclaje', 'anclaje'], 'Fijaciones', 'Pernos', 'Perno de Anclaje', 5),
    (['perno ojo', 'perno de ojo', 'perno argolla'], 'Fijaciones', 'Pernos', 'Perno Ojo', 5),
    (['perno coche', 'perno carruaje'], 'Fijaciones', 'Pernos', 'Perno Coche', 5),
    (['perno'], 'Fijaciones', 'Pernos', 'Perno', 0),
    (['tornillo madera', 'tornillo para madera', 'tornillo drywall', 'tornillo volcanita'],
     'Fijaciones', 'Tornillos', 'Tornillo para Madera', 5),
    (['autoperforante', 'tornillo autoperforante'], 'Fijaciones', 'Tornillos', 'Tornillo Autoperforante', 5),
    (['tornillo'], 'Fijaciones', 'Tornillos', 'Tornillo', 0),
    (['tuerca'], 'Fijaciones', 'Tuercas', 'Tuerca', 0),
    (['golilla plana', 'arandela plana'], 'Fijaciones', 'Golillas', 'Golilla Plana', 5),
    (['golilla presion', 'golilla de presion', 'arandela presion', 'golilla grower'],
     'Fijaciones', 'Golillas', 'Golilla de Presión', 5),
    (['golilla', 'arandela'], 'Fijaciones', 'Golillas', 'Golilla', 0),
    (['remache'], 'Fijaciones', 'Remaches', 'Remache', 0),
    (['clavo'], 'Fijaciones', 'Clavos', 'Clavo', 0),
    (['tarugo'], 'Fijaciones', 'Tarugos', 'Tarugo', 0),
    (['amarra', 'amarra plastica'], 'Fijaciones', 'Amarras', 'Amarra', 0),
    (['varilla', 'varilla roscada', 'hilo acero', 'barra roscada'], 'Fijaciones', 'Varillas y Hilos', 'Varilla Roscada', 0),
    (['hilo'], 'Fijaciones', 'Varillas y Hilos', 'Varilla Roscada', -8),
    (['cuerda', 'soga', 'polysteel', 'driza', 'huincha trenzada'], 'Fijaciones', 'Izaje y Amarre', 'Cuerda', 0),
    (['grillete'], 'Fijaciones', 'Izaje y Amarre', 'Grillete', 0),
    (['guardacabo'], 'Fijaciones', 'Izaje y Amarre', 'Guardacabo', 0),
    (['prensa cable'], 'Fijaciones', 'Izaje y Amarre', 'Prensa Cable', 5),
    (['cable de acero'], 'Fijaciones', 'Izaje y Amarre', 'Cable de Acero', 5),
    (['eslinga'], 'Fijaciones', 'Izaje y Amarre', 'Eslinga', 0),
    (['cadena'], 'Fijaciones', 'Izaje y Amarre', 'Cadena', 0),
    (['argolla'], 'Fijaciones', 'Izaje y Amarre', 'Argolla', 0),
    (['tapatornillo'], 'Fijaciones', 'Tornillos', 'Tapatornillo', 5),
    # Herrajes: el pomel es la bisagra de soldar de un porton, no un fitting
    # (el sistema anterior lo mandaba a "Union" de piping).
    (['pomel', 'bisagra'], 'Fijaciones', 'Herrajes', 'Pomel', 0),
    (['picaporte', 'cerradura', 'candado'], 'Fijaciones', 'Herrajes', 'Herraje', -5),

    # ---------------- Sellado y lubricantes ----------------
    (['teflon liquido', 'teflon anaerobico'], 'Sellado y Lubricantes', 'Siliconas y Sellantes', 'Teflón Líquido', 12),
    (['teflon'], 'Sellado y Lubricantes', 'Teflón y Sellos de Hilo', 'Teflón', 0),
    (['cinta sella hilo', 'sella hilo'], 'Sellado y Lubricantes', 'Teflón y Sellos de Hilo', 'Cinta Sella Hilo', 10),
    (['silicona', 'sellante', 'sellador', 'tapagotera'], 'Sellado y Lubricantes', 'Siliconas y Sellantes', 'Sellante', 0),
    (['adhesivo', 'pegamento'], 'Sellado y Lubricantes', 'Adhesivos', 'Adhesivo', 0),
    # 'epdm' ya no es un termino: es un MATERIAL. Una plancha de EPDM, de
    # teflon o de grafito es una plancha de empaquetadura por su material
    # (ver taxonomia: REDIRECCION_POR_MATERIAL).
    (['empaquetadura', 'sello conico', 'sello', 'oring', 'o-ring', 'graphinox',
      'plancha teflon', 'plancha de teflon'], 'Sellado y Lubricantes', 'Empaquetaduras', 'Empaquetadura', 5),
    (['lubricante', 'grasa', 'aflojador', 'wd-40', 'wd40', 'desoxidante'], 'Sellado y Lubricantes', 'Lubricantes', 'Lubricante', 0),
    (['solutech', 'aditivo', 'anticongelante'], 'Sellado y Lubricantes', 'Aditivos Químicos', 'Aditivo', 0),
    (['cinta amarre', 'cinta de amarre'], 'Fijaciones', 'Izaje y Amarre', 'Cinta de Amarre', 10),
    (['cinta electrica', 'cinta aisladora', 'cinta aislante'], 'Materiales Eléctricos', 'Cintas', 'Cinta Eléctrica', 10),
    (['cinta aluminio', 'cinta de aluminio', 'huincha ductos', 'huincha ducto'],
     'Aislación y Refractarios', 'Cintas Térmicas', 'Cinta de Aluminio', 10),
    (['cinta'], 'Sellado y Lubricantes', 'Cintas', 'Cinta', -10),

    # ---------------- Herramientas manuales ----------------
    (['llave'], 'Herramientas Manuales', 'Llaves', 'Llave', 0),
    (['llave cadena', 'llave de cadena'], 'Herramientas Manuales', 'Llaves', 'Llave de Cadena', 10),
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
    # "Barrote fuerza articulado" es una llave de fuerza, no un herraje.
    (['barrote', 'barrote fuerza', 'barra de fuerza'], 'Herramientas Manuales', 'Dados y Puntas',
     'Barrote de Fuerza', 0),
    (['terraja', 'cabezal de terraja', 'cabezal terraja'], 'Herramientas Manuales', 'Terrajas', 'Terraja', 5),
    (['calafatera', 'pistola calafateo', 'pistola calafatera'], 'Herramientas Manuales', 'Aplicación', 'Calafatera', 5),
    (['remachadora'], 'Herramientas Manuales', 'Aplicación', 'Remachadora', 5),
    (['curvadora'], 'Herramientas Manuales', 'Aplicación', 'Curvadora', 10),
    (['sacabocado'], 'Herramientas Manuales', 'Otras Herramientas', 'Sacabocado', -5),
    (['cincel'], 'Herramientas Manuales', 'Otras Herramientas', 'Cincel', -5),
    (['espatula', 'plana botadora'], 'Herramientas Manuales', 'Otras Herramientas', 'Espátula', -5),
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
    # "Martillo soldador 500W" es un cautin electrico, no un martillo.
    (['martillo soldador', 'cautin'], 'Herramientas Eléctricas', 'Soldadores y Cautines', 'Cautín', 15),
    (['llave de impacto', 'llave impacto', 'pistola de impacto'], 'Herramientas Eléctricas',
     'Llaves de Impacto', 'Llave de Impacto', 15),
    (['compresor', 'soplador'], 'Herramientas Eléctricas', 'Compresores', 'Compresor', 0),
    (['fusora', 'termofusora'], 'Herramientas Eléctricas', 'Máquinas Especiales', 'Máquina Fusora', 5),
    (['generador'], 'Herramientas Eléctricas', 'Generadores', 'Generador', 0),
    (['tecle', 'huinche', 'polipasto'], 'Herramientas Eléctricas', 'Elevación', 'Tecle', 5),

    # ---------------- Materiales eléctricos ----------------
    (['enchufe', 'toma corriente', 'tomacorriente', 'schuko'], 'Materiales Eléctricos', 'Enchufes', 'Enchufe', 0),
    (['adaptador electrico', 'adaptador schuko'], 'Materiales Eléctricos', 'Enchufes',
     'Adaptador Eléctrico', 10),
    (['cable', 'alargador'], 'Materiales Eléctricos', 'Cables y Extensiones', 'Cable', -5),
    (['extension electrica', 'extension'], 'Materiales Eléctricos', 'Cables y Extensiones',
     'Extensión Eléctrica', -3),
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

    # ---------------- Planchas y perfiles ----------------
    # La forma: la plancha es el tipo; policarbonato, acero, MDF o zincalum
    # son su material (atributo), nunca un termino de esta regla.
    (['plancha', 'placa', 'lamina'], 'Planchas y Perfiles', 'Planchas', 'Plancha', 0),
    (['perfil cuadrado', 'tubo cuadrado', 'perfil tubular cuadrado'], 'Planchas y Perfiles', 'Perfiles',
     'Perfil Cuadrado', 8),
    (['perfil rectangular', 'tubo rectangular', 'perfil tubular rectangular'], 'Planchas y Perfiles',
     'Perfiles', 'Perfil Rectangular', 8),
    (['angulo', 'perfil angulo', 'perfil l'], 'Planchas y Perfiles', 'Perfiles', 'Perfil Ángulo', 0),
    (['perfil canal', 'perfil c', 'costanera'], 'Planchas y Perfiles', 'Perfiles', 'Perfil Canal', 5),
    (['perfil omega', 'omega'], 'Planchas y Perfiles', 'Perfiles', 'Perfil Omega', 5),
    (['perfil', 'tubo estructural'], 'Planchas y Perfiles', 'Perfiles', 'Perfil', 5),
    (['riel', 'riel ruc', 'riel strut'], 'Planchas y Perfiles', 'Perfiles', 'Riel', 0),
    (['moldura', 'guardacanto'], 'Planchas y Perfiles', 'Perfiles', 'Moldura', 0),
    (['platina', 'pletina', 'barra plana'], 'Planchas y Perfiles', 'Barras y Platinas', 'Platina', 0),
    (['fierro construccion', 'fierro de construccion', 'fierro estriado', 'barra estriada'],
     'Planchas y Perfiles', 'Barras y Platinas', 'Fierro de Construcción', 5),
    (['barra redonda', 'barra lisa', 'barra cuadrada', 'fierro'], 'Planchas y Perfiles',
     'Barras y Platinas', 'Barra', -5),
    (['malla', 'cerco', 'panel de malla', 'rejilla'], 'Planchas y Perfiles', 'Mallas', 'Malla', 0),

    # ---------------- Maderas ----------------
    (['pino', 'madera', 'viga', 'tabla', 'liston', 'cuarton', 'polin'], 'Maderas', 'Madera Dimensionada',
     'Madera Dimensionada', 0),

    # ---------------- Materiales de construcción ----------------
    # Estaban en "Aseo y Oficina > Sacos" porque la factura decia "saco de
    # arena": el saco es el envase, la arena es el producto.
    (['cemento'], 'Materiales de Construcción', 'Cementos y Morteros', 'Cemento', 5),
    (['mortero', 'hormigon', 'concreto'], 'Materiales de Construcción', 'Cementos y Morteros', 'Mortero', 0),
    (['arena', 'gravilla', 'ripio', 'grava', 'arido'], 'Materiales de Construcción', 'Áridos', 'Árido', 5),

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
    # "Manifold" a secas es el talonario autocopiativo; el manifold de
    # refrigeracion (manometros) se resuelve por contexto (DESAMBIGUACION).
    (['manifold', 'libro manifold', 'boleta talonario'], 'Aseo y Oficina', 'Papelería', 'Manifold', 0),
    (['lapiz', 'marcador', 'destacador'], 'Aseo y Oficina', 'Papelería', 'Lápiz', 0),
    (['libro', 'papel', 'archivador', 'cuaderno'], 'Aseo y Oficina', 'Papelería', 'Papelería', -5),
    (['bandeja'], 'Aseo y Oficina', 'Menaje', 'Bandeja', -5),

    # ---------------- Alimentación (gasto) ----------------
    (['almuerzo', 'colacion', 'cena', 'desayuno', 'comida', 'menu', 'plato preparado', 'wok'],
     'Alimentación', 'Comidas', 'Almuerzo', 0),
    (['sandwich', 'miga', 'hamburguesa', 'completo', 'empanada', 'pizza', 'snack', 'wantan',
      'arrollado'], 'Alimentación', 'Sándwiches y Snacks', 'Sándwich', 0),
    (['bebida', 'coca cola', 'pepsi', 'sprite', 'fanta', 'bilz', 'gatorade', 'powerade', 'monster',
      'red bull', 'jugo', 'nectar', 'agua mineral', 'agua', 'cafe', 'te', 'leche'],
     'Alimentación', 'Bebidas', 'Bebida', 0),
    (['galleta', 'muffin', 'medialuna', 'helado', 'chocolate', 'barra de cereal', 'protein', 'dulce',
      'combo', 'consumo', 'nuggets', 'papas'],
     'Alimentación', 'Sándwiches y Snacks', 'Snack', 0),
    (['supermercado', 'ingrediente', 'abarrote', 'feria libre'], 'Alimentación', 'Supermercado', 'Supermercado', 0),
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
    # Compras que el documento no detalla (voucher de tarjeta, boleta sin
    # items): no son un producto, son una compra sin desglose.
    (['compra sin desglose', 'materiales varios', 'compra de materiales', 'materiales de ferreteria',
      'ferreteria', 'producto ferretero', 'sin detalle', 'voucher'],
     'Arriendos y Servicios', 'Compras sin Desglose', 'Compra sin Desglose', 5),
    # "Compra en ..." a secas: ultimo recurso, porque "en" es palabra vacia y
    # el termino se reduce a "compra". Con prioridad normal se llevaba una
    # "Compra en comercio de huevos, confites y abarrotes" que es
    # Alimentacion.
    (['compra'], 'Arriendos y Servicios', 'Compras sin Desglose', 'Compra sin Desglose', -15),
]

# ---------------------------------------------------------------------------
# PALABRAS DE ENVASE
# ---------------------------------------------------------------------------
# "Kit bomba", "Pack 2 curva", "Bolsa de clavos": el envase no es el
# producto. Al medir en que posicion del nombre esta el sustantivo principal,
# estas palabras no cuentan -- asi "bomba" es la primera palabra de "Kit bomba
# DAB ... union 1.1/4"" y le gana a "union". Las de la segunda lista solo son
# envase cuando las sigue "de" ("Bolsa de clavos"; "Bolsa basura" SI es una
# bolsa).
ENVASES = {"kit", "set", "juego", "pack", "par", "display", "repuesto"}
ENVASES_CON_DE = {"bolsa", "caja", "saco", "rollo", "tira", "paquete", "pote", "tarro"}

# Frases que parecen un producto pero describen otra cosa: "hilo interior" es
# un tipo de conexion, no una varilla roscada.
# Ojo: cada frase se compara por sus lemas de CONTENIDO, asi que "con hilo"
# se reduciria a "hilo" y vetaria la palabra entera -- y con ella el tipo
# "Hilo Tuerca". Cada frase de esta lista tiene que dejar dos lemas reales.
NO_PRODUCTO = ["hilo interior", "hilo exterior", "hilo amarillo", "hilo hi", "hilo he",
               "tipo l", "tipo m", "tipo k", "punta fina", "punta broca", "punta huevo"]

# Marcadores despues de los cuales un sustantivo es un COMPONENTE o un
# accesorio incluido, no el producto: "Soplete con manguera", "Kit valvula
# angular ... con codo de regulacion (incluye terminal ...)".
MARCADORES_COMPONENTE = {"con", "incluye", "incluido", "incl", "porta", "mas"}

# ---------------------------------------------------------------------------
# DESAMBIGUACION POR CONTEXTO
# ---------------------------------------------------------------------------
# Sustantivos genericos cuyo tipo depende de con que otras palabras aparecen.
# Un "adaptador" con "schuko" es un adaptador electrico; con "broca" o
# "sierra", el porta sierra de un taladro; si no, un adaptador de piping.
# (tipo detectado) -> [(marcadores, (categoria, subcategoria, tipo nuevo))]
DESAMBIGUACION = {
    'Adaptador': [
        ({'schuko', 'enchufe', 'duplex', 'triple', '16a', '10a', '2p', 'volt', 'electrico'},
         ('Materiales Eléctricos', 'Enchufes', 'Adaptador Eléctrico')),
        ({'broca', 'sierra', 'copa', 'mandril'},
         ('Abrasivos y Corte', 'Accesorios de Corte', 'Porta Sierra Copa')),
    ],
    'Conector': [
        ({'cable', 'electrico', 'electrica', 'borne'},
         ('Materiales Eléctricos', 'Cables y Extensiones', 'Conector Eléctrico')),
    ],
    'Terminal': [
        ({'cable', 'electrico', 'electrica', 'ojo', 'horquilla'},
         ('Materiales Eléctricos', 'Cables y Extensiones', 'Terminal Eléctrico')),
    ],
    'Manifold': [
        ({'manometro', 'refrigeracion', 'refrigerante', 'r410', 'r22', 'tripleauto'},
         ('Instrumentación y Medición', 'Refrigeración', 'Manifold de Refrigeración')),
    ],
    'Pomel': [
        ({'caneria', 'acople'}, ('Piping y Fittings', 'Coplas y Uniones', 'Unión')),
    ],
    'Tubo': [
        ({'cuadrado', 'rectangular', 'estructural'},
         ('Planchas y Perfiles', 'Perfiles', 'Perfil')),
    ],
}

# Materiales que convierten una plancha en una plancha de EMPAQUETADURA: una
# plancha de teflon, grafito o EPDM se corta para hacer juntas, no es una
# plancha de construccion.
MATERIALES_DE_SELLO = {'PTFE', 'Grafito', 'EPDM', 'NBR', 'Viton', 'Neopreno', 'Caucho'}
REDIRECCION_POR_MATERIAL = {
    'Plancha': (MATERIALES_DE_SELLO,
                ('Sellado y Lubricantes', 'Empaquetaduras', 'Plancha de Empaquetadura')),
    'Empaquetadura': (MATERIALES_DE_SELLO,
                      ('Sellado y Lubricantes', 'Empaquetaduras', 'Plancha de Empaquetadura')),
}

# Cuando ninguna regla calza pero el texto trae un material que casi siempre
# se compra en una forma ("EPDM 3/16 x 1,5 MT"), se sugiere ese tipo con
# confianza baja -- nunca se inventa una categoria sin avisar.
TIPO_POR_MATERIAL = {
    'Policarbonato': ('Planchas y Perfiles', 'Planchas', 'Plancha'),
    'Acrílico': ('Planchas y Perfiles', 'Planchas', 'Plancha'),
    'MDF': ('Planchas y Perfiles', 'Planchas', 'Plancha'),
    'Terciado': ('Planchas y Perfiles', 'Planchas', 'Plancha'),
    'OSB': ('Planchas y Perfiles', 'Planchas', 'Plancha'),
    'Melamina': ('Planchas y Perfiles', 'Planchas', 'Plancha'),
    'Zincalum': ('Planchas y Perfiles', 'Planchas', 'Plancha'),
    'EPDM': ('Sellado y Lubricantes', 'Empaquetaduras', 'Plancha de Empaquetadura'),
    'NBR': ('Sellado y Lubricantes', 'Empaquetaduras', 'Plancha de Empaquetadura'),
    'Viton': ('Sellado y Lubricantes', 'Empaquetaduras', 'Plancha de Empaquetadura'),
    'Neopreno': ('Sellado y Lubricantes', 'Empaquetaduras', 'Plancha de Empaquetadura'),
    'Pino': ('Maderas', 'Madera Dimensionada', 'Madera Dimensionada'),
}

# ---------------------------------------------------------------------------
# DESCRIPTORES
# ---------------------------------------------------------------------------
# Palabras frecuentes del catalogo que NO son producto, material ni marca,
# pero tampoco son "desconocidas": adjetivos de uso, calidad o forma. Sirven
# para que el informe de terminos sin interpretar (driver.py atributos)
# muestre solo lo que de verdad falta ensenarle al sistema.
DESCRIPTORES = [
    "tipo", "agua", "gas", "alta", "baja", "temperatura", "presion", "industrial", "estandar",
    "standard", "std", "profesional", "recto", "recta", "simple", "doble", "triple", "corriente",
    "calibrada", "calibrado", "largo", "larga", "corto", "grande", "chico", "mediano", "universal",
    "manual", "electrico", "electrica", "automatico", "automatica", "portatil", "inalambrico",
    "inalambrica", "nacional", "italiana", "italiano", "economico", "economica", "premium",
    "reforzado", "multiuso", "desechable", "reusable", "talla", "paso", "total", "interior",
    "exterior", "punta", "cabeza", "fina", "grueso", "gruesa", "liviano", "liviana", "pesado",
    "trabajo", "seguridad", "proteccion", "unidad", "metro", "pieza", "accesorio", "modelo",
    "marca", "radiador", "regulacion", "resorte", "retorno", "vertical", "horizontal", "red",
    "hembra", "macho", "centro", "central", "lenteja", "hexagonal", "plana", "plano", "redondo",
    "redonda", "cuadrado", "cuadrada", "rectangular", "angular", "reduccion", "reducido",
    "americana", "rapida", "rapido", "ajustable", "articulado", "magnetico", "termico",
    "termica", "aislado", "aislada", "certificado", "reflectante", "cinta", "estopa", "manilla",
    "disco", "cuerpo", "solo", "incluye", "mango", "marco", "cabezal", "vias", "via", "linea",
    "circulacion", "circuladora", "rotor", "humedo", "expansion", "sanitario", "radial",
    "bimetalico", "glicerina", "inferior", "posterior", "superior", "conexion", "caja", "bolsa",
    "pack", "set", "kit", "par", "rollo", "tira", "barra", "display", "carrete", "pote",
    "metrica", "metrico", "laminado", "laminada", "mandrilado", "trefilado",
]
