# -*- coding: utf-8 -*-
"""
oportunidades.py -- Buscador y evaluación previa de oportunidades en Mercado
Público (2026-10-13).

Por qué existe: el usuario pidió «una herramienta que, utilizando el
historial de Mercado Público, identifique buenas oportunidades de negocio»
con una evaluación previa por rubro, monto, dificultad de implementación,
visita técnica y tiempos de ejecución. Hasta hoy alguien revisaba Mercado
Público a mano, y la Planilla de Ingreso muestra el costo: de 305
requerimientos, 202 se descartaron después de mirarlos.

Qué hace, en cada vuelta:

1. **Aprende de la historia**: los requerimientos de la Planilla (qué se
   ofertó, qué se descartó, qué se ganó, a qué comprador y por cuánto), los
   resultados que ya trajo el monitor (``mercado_publico.py``: quién ganó y
   con cuántos oferentes) y un historial de mercado que este módulo va
   juntando de a poco: licitaciones del rubro ya adjudicadas, con ganador,
   monto y oferentes.
2. **Busca**: el listado de licitaciones publicadas (una consulta), un
   prefiltro por el nombre (palabras del rubro, o parecido con lo que QUEMPIN
   ya ofertó) y la ficha completa solo de las candidatas.
3. **Evalúa** cada candidata con 8 criterios de 0 a 100 (rubro, monto,
   dificultad, visita a terreno, ubicación, comprador y competencia, plazo
   para ofertar, tiempo de ejecución), un puntaje ponderado y su categoría.
   Cada criterio dice por qué: la evaluación es una ayuda para decidir rápido,
   no una caja negra. Hay motivos que descartan solos (cierra en menos de un
   día, visita obligatoria ya pasada, fuera de rubro).
4. **Publica** ``publicado/oportunidades.json`` para las demás herramientas
   (el paso del procesador, si su configuración lo activa). Lo que mira el
   equipo es el tablero de GitHub Pages, con la contraseña de los demás
   tableros: lo arma ``Visualizador Web/build_visualizador.py`` (2026-10-13,
   pedido del usuario: «con la estética del resto de herramientas QUEMPIN»).

Nunca escribe la Planilla: pasar una oportunidad a la Planilla lo decide una
persona. Los pesos, palabras del rubro, regiones y tramos están en
``oportunidades_config.json``.

SEGURIDAD: usa el mismo cliente, ticket cifrado y límites del monitor
(``mercado_publico.Cliente``). Lo que responde la API es dato no confiable:
textos limpios y acortados, enlaces solo a www.mercadopublico.cl. No se
publican nombres ni contactos de funcionarios del comprador.

Uso:
    py -3.14 oportunidades.py status [--sin-red]   # evalúa sin publicar; muestra las mejores
    py -3.14 oportunidades.py revisar              # vuelta completa y publica oportunidades.json
"""

from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import esquemas  # noqa: E402
import intercambio  # noqa: E402
import mercado_publico as mp  # noqa: E402
import requerimientos  # noqa: E402

HERRAMIENTA = "oportunidades"
PUBLICACION = "oportunidades"

RUTA_CONFIG = AQUI / "oportunidades_config.json"
RUTA_ESTADO = AQUI / "oportunidades_estado.json"        # caché de fichas e historial de mercado (gitignoreado; datos públicos)
RUTA_UF = AQUI.parent / "Cotizador Historico" / "Sistema" / "uf_cache.json"

CRITERIOS = (
    ("rubro", "Rubro", "Qué tan cerca está del trabajo de QUEMPIN: palabras del rubro y parecido con lo que ya se ofertó o se ganó."),
    ("monto", "Monto", "Si el monto cae en el rango que QUEMPIN suele ofertar y adjudicarse, ni tan chico que no pague el esfuerzo ni tan grande que exceda la capacidad."),
    ("dificultad", "Dificultad", "Facilidad de implementación: 100 es una mantención simple; bajan obras, diseño, varios recintos, muchos ítems o licitaciones grandes."),
    ("visita", "Visita a terreno", "Si exige visita técnica, cuándo es y cuánto cuesta ir. Una visita ya pasada suele dejar fuera."),
    ("ubicacion", "Ubicación", "Distancia del comprador a la base de QUEMPIN (región)."),
    ("comprador", "Comprador y competencia", "Historia con ese comprador (ganado, perdido, descartado) y cuántos compiten en licitaciones parecidas."),
    ("plazoOferta", "Plazo para ofertar", "Días que quedan para preparar la oferta."),
    ("ejecucion", "Tiempo de ejecución", "Duración del contrato: los de mantención de 6 a 36 meses dan ingresos recurrentes."),
)

# Tipo de licitación -> rango en UTM (Ley de Compras). Se usa cuando el
# comprador no publica el monto estimado.
RANGO_TIPO_UTM = {
    "L1": (1, 100), "E2": (1, 100), "LE": (100, 1000), "CO": (100, 1000),
    "LP": (1000, 2000), "B2": (1000, 2000), "LQ": (2000, 5000), "H2": (2000, 5000),
    "LR": (5000, 10000), "I2": (5000, 10000),
}
# UnidadTiempoDuracionContrato -> meses (1 horas, 2 días, 3 semanas, 4 meses, 5 años).
UNIDAD_A_MESES = {1: 1 / 720, 2: 1 / 30, 3: 7 / 30, 4: 1, 5: 12}

ESTADOS_OFERTADOS = {"adjudicado", "no adjudicado", "ofertado", "evaluacion"}
K_PARECIDAS = 7
SIMILITUD_PARECIDA = 0.25
SIN_FICHA = "sin ficha todavía (se pide en la próxima vuelta)"

# Nombre corto de cada región para la tabla y los filtros, por la misma clave
# con que oportunidades_config.json les da puntaje (nombre sin tildes).
NOMBRE_REGION = {
    "arica": "Arica y Parinacota", "tarapaca": "Tarapacá", "antofagasta": "Antofagasta",
    "atacama": "Atacama", "coquimbo": "Coquimbo", "valparaiso": "Valparaíso",
    "metropolitana": "Metropolitana", "higgins": "O'Higgins", "maule": "Maule", "nuble": "Ñuble",
    "biobio": "Biobío", "araucania": "La Araucanía", "los rios": "Los Ríos", "los lagos": "Los Lagos",
    "aysen": "Aysén", "magallanes": "Magallanes",
}


# ── TEXTO ────────────────────────────────────────────────────────────────────

_ABREVIATURAS = {
    "mant": "mantencion", "mantto": "mantencion", "mtto": "mantencion", "mto": "mantencion",
    "manten": "mantencion", "mantenimiento": "mantencion", "mantenimineto": "mantencion",
    "mantencione": "mantencion", "mantenciones": "mantencion",
    "calef": "calefaccion", "sist": "sistema", "serv": "servicio", "adq": "adquisicion",
    "eq": "equipo", "inst": "instalacion", "rep": "reparacion", "prev": "preventivo",
    "preventiva": "preventivo", "corr": "correctivo", "correctiva": "correctivo", "h2": "hidrogeno",
    "acs": "agua caliente", "calderas": "caldera", "boilers": "boiler",
}
_VACIAS = set("""a al ante con contra de del desde el en entre hacia hasta la las le lo los para por
según segun sin sobre tras un una unos unas y o u e que se su sus otro otros otras n nro num del""".split())
# Raíces que aparecen en licitaciones de cualquier rubro: no sirven para decir
# que dos licitaciones se parecen («Revisión de prótesis» no se parece a
# «Revisión de caldera»). Las frases del rubro se siguen buscando completas.
_GENERICAS = """manten preven correc repara revisi prueba sistem equipo instal provis mejora adquis
hospit cesfam edific centro escuel liceo region munici comuna anual contra ejecuc trabaj genera
varios otros requie nuevo normal establ salud servic sumini public direcc nacion conven obras obra
cambio reempl compra materi insumo integr diseno proyec habili accesi recint inmueb oficin
agua potabl sanita limpie aseo red licita mes ano dia semana trimest periodo plazo hora
tribunal juzgado fiscal carabin armada ejercit fach polic gendarm univers minist gobiern junji jardin
colegio consult cuartel comisar regimie naval aerea valparaiso santiago metropol vina quilpue quillota
concepcion temuco valdivia arica iquique antofag serena rancagua talca chillan osorno montt punta arenas""".split()
_GENERICA = re.compile(r"^(?:" + "|".join(sorted(_GENERICAS, key=len, reverse=True)) + ")")
SIMILITUD_SIN_PALABRAS = 0.6
# Para decir que dos títulos se parecen solo cuentan palabras que aparecen en
# al menos 3 títulos de la Planilla: un lugar («Llay Llay») o una sigla del
# comprador («DGC») no hacen parecida una licitación de otro rubro.
MIN_TITULOS_PALABRA = 3
# Sin palabras del rubro, una licitación solo pasa si comparte al menos 2
# palabras útiles con algo que QUEMPIN ofertó: una sola («piscina»,
# «carabineros», «estanque») no basta (medido el 2026-10-13: con una sola
# pasaban 376 de las 5.000 publicadas, casi todas ajenas).
MIN_PALABRAS_COMUNES = 2


def normalizar(texto) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes.lower()).strip()


def raices(texto) -> list[str]:
    """Palabras útiles, sin tildes, con las abreviaturas de Mercado Público
    expandidas y en singular («calderas» y «caldera» son la misma). No se
    corta a una raíz fija: «hidrogeológico» no es «hidrógeno»."""
    salida = []
    for palabra in normalizar(texto).split():
        palabra = _ABREVIATURAS.get(palabra, palabra)
        for p in palabra.split():
            if p in _VACIAS or p.isdigit() or (len(p) < 3 and p != "h2"):
                continue
            salida.append(singular(p))
    return salida


def singular(p: str) -> str:
    if len(p) > 4 and p.endswith("es") and p[-3] in "lrndzjs":
        return p[:-2]                    # paneles, radiadores, calefacciones, gases
    if len(p) > 3 and p.endswith("s") and p[-2] in "aeiou":
        return p[:-1]                    # calderas, equipos, válvulas
    return p


def contiene(raices_texto: list[str], frase: str) -> bool:
    """La frase (por raíces, en orden y seguidas) está en el texto."""
    f = raices(frase)
    if not f:
        return False
    n = len(f)
    return any(raices_texto[i:i + n] == f for i in range(len(raices_texto) - n + 1))


def coincidencias(raices_texto: list[str], frases: list[str]) -> list[str]:
    return [f for f in frases if contiene(raices_texto, f)]


# ── HISTORIA ─────────────────────────────────────────────────────────────────

def unidad_de(codigo) -> str | None:
    """La unidad de compra es el primer número del código («761391-52-LE26»)."""
    m = re.match(r"^(\d{1,9})-", str(codigo or ""))
    return m.group(1) if m else None


def region_corta(region) -> str | None:
    """«Región del Libertador General Bernardo O'Higgins» -> «O'Higgins»."""
    if not region:
        return None
    texto = normalizar(region)
    return next((nombre for clave, nombre in NOMBRE_REGION.items() if clave in texto), region)


class Historia:
    """Los requerimientos de la Planilla, listos para comparar: raíces con
    TF-IDF para buscar los más parecidos, montos y la relación con cada
    unidad de compra."""

    def __init__(self, reqs: list[dict]):
        self.items = []
        for r in reqs:
            if not isinstance(r, dict) or not r.get("titulo"):
                continue
            estado = requerimientos.normalizar_encabezado(r.get("estado") or "")
            codigo = mp.codigo_de(r.get("referencia"))
            self.items.append({
                "req": r.get("numero"), "titulo": mp._texto(r.get("titulo"), 120), "estado": r.get("estado") or "",
                "ofertado": estado in ESTADOS_OFERTADOS, "ganado": estado == "adjudicado",
                "perdido": estado == "no adjudicado", "codigo": codigo, "unidad": unidad_de(codigo),
                "raices": raices(r.get("titulo")),
                "monto": next((v for v in (r.get("valorOfertado"), r.get("presupuesto"), r.get("valorAdjudicado"))
                               if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0), None),
            })
        documentos = len(self.items) or 1
        frecuencia: dict[str, int] = {}
        for it in self.items:
            for t in set(it["raices"]):
                frecuencia[t] = frecuencia.get(t, 0) + 1
        self.idf = {t: math.log((1 + documentos) / (1 + f)) + 1 for t, f in frecuencia.items()}
        self.idf_desconocida = math.log(1 + documentos) + 1
        # Solo estas palabras hacen parecidos dos títulos; las demás cuentan en la
        # norma (una palabra desconocida diluye el parecido, como debe ser).
        self.vocabulario = {t for t, f in frecuencia.items() if f >= min(MIN_TITULOS_PALABRA, documentos)}
        for it in self.items:
            it["vector"] = self.vector(it["raices"])
        self.por_codigo = {it["codigo"]: it for it in self.items if it["codigo"]}

    def vector(self, rs: list[str]) -> dict:
        v: dict[str, float] = {}
        for t in rs:
            if _GENERICA.match(t):
                continue
            v[t] = v.get(t, 0) + self.idf.get(t, self.idf_desconocida)
        norma = math.sqrt(sum(x * x for x in v.values())) or 1
        return {t: x / norma for t, x in v.items()}

    def similitud(self, v: dict, w: dict) -> tuple[float, int]:
        """(coseno, palabras en común), contando solo palabras del vocabulario."""
        comunes = [t for t in v if t in w and t in self.vocabulario]
        return sum(v[t] * w[t] for t in comunes), len(comunes)

    def parecidas(self, texto: str, k: int = K_PARECIDAS, minimo: float = SIMILITUD_PARECIDA,
                  min_comunes: int = 1) -> list[tuple[float, dict]]:
        v = self.vector(raices(texto))
        if not v:
            return []
        pares = []
        for it in self.items:
            s, n = self.similitud(v, it["vector"])
            if s >= minimo and n >= min_comunes:
                pares.append((round(s, 3), it))
        # A igual parecido, primero las más recientes (N° más alto): muchos títulos
        # empatan («Mantención de calderas») y la experiencia reciente dice más.
        pares.sort(key=lambda p: (-p[0], -(p[1]["req"] or 0)))
        return pares[:k]

    def muy_parecida_ofertada(self, nombre: str) -> float:
        """El mayor parecido con un título ofertado que alcanza para entrar sin
        palabras del rubro (≥ 0,6 y al menos 2 palabras en común); 0 si no hay."""
        fuertes = self.parecidas(nombre, k=len(self.items), minimo=SIMILITUD_SIN_PALABRAS, min_comunes=MIN_PALABRAS_COMUNES)
        return max((s for s, it in fuertes if it["ofertado"]), default=0)

    def montos_ofertados(self) -> list[float]:
        return sorted(it["monto"] for it in self.items if it["ofertado"] and it["monto"])

    def con_unidad(self, unidad: str | None) -> list[dict]:
        return [it for it in self.items if unidad and it["unidad"] == unidad]

    def resumen(self) -> dict:
        return {"requerimientos": len(self.items), "ofertados": sum(it["ofertado"] for it in self.items),
                "ganados": sum(it["ganado"] for it in self.items), "perdidos": sum(it["perdido"] for it in self.items)}


def percentil(valores: list[float], p: float) -> float | None:
    if not valores:
        return None
    v = sorted(valores)
    i = (len(v) - 1) * p
    a, b = math.floor(i), math.ceil(i)
    return v[a] + (v[b] - v[a]) * (i - a)


# ── LEER UNA FICHA ───────────────────────────────────────────────────────────

def _entero(valor) -> int | None:
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    return n


_CONTACTO = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"                                   # correos
                       r"|\+56[\d\s()-]{7,13}\d"                                          # +56 ...
                       r"|(?i:\b(fono|tel[eé]fono|tel\.|cel(ular)?|whatsapp)\b)[:\s.]*[\d\s+()-]{6,}\d")  # «fono: ...»


def _sin_contactos(texto: str | None) -> str | None:
    """La descripción la escribe el comprador y a veces trae correos o
    teléfonos de funcionarios: no se publican."""
    return _CONTACTO.sub("[contacto omitido]", texto) if texto else texto


def leer_ficha(crudo: dict, codigo: str) -> dict:
    """Lo que la evaluación necesita de una licitación, ya limpio. Sin
    nombres ni contactos de funcionarios."""
    fechas = crudo.get("Fechas") if isinstance(crudo.get("Fechas"), dict) else {}
    comprador = crudo.get("Comprador") if isinstance(crudo.get("Comprador"), dict) else {}
    items = ((crudo.get("Items") or {}).get("Listado") if isinstance(crudo.get("Items"), dict) else None) or []
    items = [i for i in items if isinstance(i, dict)]
    visible = crudo.get("VisibilidadMonto") in (1, "1")
    monto = mp._numero(crudo.get("MontoEstimado"))
    return {
        "codigo": codigo,
        "nombre": mp._texto(crudo.get("Nombre"), 200),
        "descripcion": _sin_contactos(mp._texto(crudo.get("Descripcion"), 1200)),
        "estadoCodigo": crudo.get("CodigoEstado") if isinstance(crudo.get("CodigoEstado"), int) else None,
        "tipo": mp._texto(crudo.get("Tipo"), 4) or codigo.rsplit("-", 1)[-1][:-2],
        "moneda": mp._texto(crudo.get("Moneda"), 5),
        "organismo": mp._texto(comprador.get("NombreOrganismo"), 120),
        "unidadCompra": mp._texto(comprador.get("NombreUnidad"), 120),
        "comuna": mp._texto(comprador.get("ComunaUnidad"), 60),
        "region": mp._texto(comprador.get("RegionUnidad"), 80),
        "reclamos": crudo.get("CantidadReclamos") if isinstance(crudo.get("CantidadReclamos"), int) else None,
        "publicada": mp._fecha(fechas.get("FechaPublicacion")),
        "cierre": mp._fecha(fechas.get("FechaCierre")) or mp._fecha(crudo.get("FechaCierre")),
        "visita": mp._fecha(fechas.get("FechaVisitaTerreno")),
        "direccionVisita": _sin_contactos(mp._texto(crudo.get("DireccionVisita"), 160)),
        "montoEstimado": monto if (visible and monto and monto > 0) else None,
        "duracion": _entero(crudo.get("TiempoDuracionContrato")),
        "unidadDuracion": _entero(crudo.get("UnidadTiempoDuracionContrato")),
        "renovable": crudo.get("EsRenovable") in (1, "1"),
        "obras": str(crudo.get("Obras")).strip() == "1",
        "etapas": _entero(crudo.get("Etapas")),
        "tomaRazon": str(crudo.get("TomaRazon")).strip() == "1",
        "items": len(items),
        "categorias": sorted({c for c in (mp._texto(i.get("Categoria"), 160) for i in items) if c})[:6],
        "productos": [p for p in (mp._texto(i.get("NombreProducto"), 80) for i in items[:8]) if p],
    }


def leer_adjudicada(crudo: dict, codigo: str) -> dict | None:
    """Una licitación ya adjudicada del rubro, para el historial de mercado:
    quién ganó, por cuánto y con cuántos oferentes."""
    lic = mp.leer_licitacion(crudo, codigo)
    if not lic.get("adjudicados"):
        return None
    comprador = crudo.get("Comprador") if isinstance(crudo.get("Comprador"), dict) else {}
    return {
        "codigo": codigo, "nombre": lic.get("nombre"), "organismo": lic.get("comprador"),
        "unidad": unidad_de(codigo), "region": mp._texto(comprador.get("RegionUnidad"), 80),
        "fecha": (lic.get("fechaAdjudicacion") or "")[:10] or None, "oferentes": lic.get("oferentes"),
        "moneda": lic.get("moneda"), "monto": sum(p["montoNeto"] for p in lic["adjudicados"]),
        "ganadores": [p["nombre"] or p["rut"] for p in lic["adjudicados"][:3]],
        "quempin": lic.get("montoQuempin") is not None,
    }


# ── EVALUAR ──────────────────────────────────────────────────────────────────

def cargar_config(ruta: Path | None = None) -> dict:
    return json.loads((ruta or RUTA_CONFIG).read_text(encoding="utf-8"))


def valor_uf(config: dict) -> float:
    try:
        datos = json.loads(RUTA_UF.read_text(encoding="utf-8"))
        return float(datos[max(datos)])
    except (OSError, ValueError, KeyError, TypeError):
        return float(config["monto"]["valorUFRespaldo"])


def _pesos(valor) -> str:
    if valor is None:
        return "sin dato"
    if valor >= 1_000_000:
        return f"${valor / 1_000_000:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")
    return "$" + f"{round(valor):,}".replace(",", ".")


def _acotar(x: float) -> int:
    return int(max(0, min(100, round(x))))


class Evaluador:
    def __init__(self, config: dict, historia: Historia, mercado: list[dict], ahora: datetime, uf: float):
        self.c, self.h, self.ahora, self.uf = config, historia, ahora, uf
        self.mercado = mercado
        self.mercado_vec = [(m, historia.vector(raices(m.get("nombre")))) for m in mercado]
        montos = historia.montos_ofertados()
        cm = config["monto"]
        self.rango = {
            "p10": cm.get("idealDesde") or percentil(montos, 0.10),
            "p25": cm.get("idealDesde") or percentil(montos, 0.25),
            "p75": cm.get("idealHasta") or percentil(montos, 0.75),
            "p90": cm.get("idealHasta") or percentil(montos, 0.90),
        }
        self.rango["maximo"] = cm.get("maximo") or ((self.rango["p90"] or 0) * 3 or None)

    # Prefiltro: solo con el nombre (antes de gastar una consulta en la ficha).
    def prefiltro(self, nombre: str) -> float:
        rs = raices(nombre)
        r = self.c["rubro"]
        nucleo, afines = coincidencias(rs, r["nucleo"]), coincidencias(rs, r["afines"])
        if coincidencias(rs, r["excluir"]):
            return 0                 # con «combustible» o «producto químico» en el nombre se descartaría igual: no gastar la ficha
        if not nucleo and not afines:
            return 60 * self.h.muy_parecida_ofertada(nombre)
        parecidas = self.h.parecidas(nombre, k=3)
        sim_ofertada = max((s for s, it in parecidas if it["ofertado"]), default=0)
        return (60 if nucleo else 0) + (30 if afines else 0) + 60 * sim_ofertada

    def evaluar(self, ficha: dict, en_planilla: dict | None = None) -> dict:
        texto = " ".join(x for x in [ficha.get("nombre"), ficha.get("descripcion"), *ficha.get("productos", [])] if x)
        rs = raices(texto)
        # La categoría de los ítems no entra: la de climatización junta calefacción con aire acondicionado.
        # Lo parecido se busca por el nombre: la Planilla guarda títulos, no descripciones.
        parecidas = self.h.parecidas(ficha.get("nombre") or "")
        # Los motivos para descartar que dependen de la fecha (plazo, visita ya
        # pasada) van aparte: la página los recalcula con la fecha del día, así
        # una licitación vista días después del build no queda como si nada.
        criterios, descartar_fijo, descartar_tiempo = {}, [], []

        criterios["rubro"] = self._rubro(rs, ficha, parecidas, descartar_fijo)
        monto, fuente_monto = self._monto_clp(ficha)
        criterios["monto"] = self._monto(monto, fuente_monto, descartar_fijo)
        meses = self._duracion_meses(ficha, texto)
        criterios["dificultad"] = self._dificultad(rs, ficha)
        criterios["ubicacion"] = self._ubicacion(ficha)
        criterios["visita"] = self._visita(ficha, texto, criterios["ubicacion"]["puntaje"], descartar_tiempo)
        parecidas_mercado = self._mercado_parecido(ficha)
        criterios["comprador"] = self._comprador(ficha, parecidas_mercado)
        criterios["plazoOferta"] = self._plazo(ficha, descartar_tiempo)
        criterios["ejecucion"] = self._ejecucion(meses, ficha)
        if not ficha.get("_completa", True):
            # Sin ficha no se sabe de visita, dificultad ni duración: neutro, nunca «perfecto».
            for k in ("dificultad", "visita", "ejecucion"):
                criterios[k] = {"puntaje": 50, "motivo": SIN_FICHA, "corto": SIN_FICHA}

        pesos = self.c["pesos"]
        total = sum(pesos[k] for k in pesos) or 1
        puntaje = round(sum(criterios[k]["puntaje"] * pesos[k] for k in pesos) / total, 1)
        descartar = descartar_fijo + descartar_tiempo
        categoria = "descartar" if descartar else self.categoria(puntaje, criterios["rubro"]["puntaje"])
        a_favor, en_contra = self.a_favor_y_en_contra(criterios)

        ofertadas = [(s, it) for s, it in parecidas if it["ofertado"]]
        resueltas = [(s, it) for s, it in ofertadas if it["ganado"] or it["perdido"]]
        prob = (round(sum(s for s, it in resueltas if it["ganado"]) / sum(s for s, _ in resueltas), 2)
                if len(resueltas) >= 2 else None)
        dias = self._dias_para(ficha.get("cierre"))
        return {
            "codigo": ficha["codigo"],
            "url": mp.FICHA_LICITACION + ficha["codigo"],
            "nombre": ficha.get("nombre"),
            "descripcion": (ficha.get("descripcion") or "")[:600] or None,
            "organismo": ficha.get("organismo"),
            "unidadCompra": ficha.get("unidadCompra"),
            "region": ficha.get("region"),
            "regionCorta": region_corta(ficha.get("region")),
            "comuna": ficha.get("comuna"),
            "tipo": ficha.get("tipo"),
            "publicada": ficha.get("publicada"),
            "cierre": ficha.get("cierre"),
            "diasParaCierre": None if dias is None else round(dias, 1),
            "monto": {"valor": round(monto) if monto else None, "fuente": fuente_monto},
            "duracionMeses": None if meses is None else round(meses, 1),
            "visita": {"fecha": ficha.get("visita"), "obligatoria": self._visita_obligatoria(texto) if ficha.get("visita") else None},
            "categorias": ficha.get("categorias") or [],
            "puntaje": puntaje,
            "categoria": categoria,
            "descartar": descartar,
            "descartarFijo": descartar_fijo,
            "aFavor": a_favor,
            "enContra": en_contra,
            "criterios": criterios,
            "probabilidadGanar": prob,
            "valorEsperado": round(monto * prob) if (monto and prob is not None) else None,
            "parecidas": [{"req": it["req"], "titulo": it["titulo"], "estado": it["estado"], "similitud": s}
                          for s, it in parecidas[:5]],
            "mercado": [{k: m.get(k) for k in ("codigo", "nombre", "organismo", "fecha", "monto", "moneda", "oferentes", "ganadores")}
                        for _, m in parecidas_mercado[:5]],
            "enPlanilla": en_planilla,
            "ficha": True,
        }

    def a_favor_y_en_contra(self, criterios: dict) -> tuple[list[str], list[str]]:
        """Lo que más empuja la licitación hacia arriba y hacia abajo, en
        frases cortas: así se entiende de un vistazo por qué está donde está.
        El plazo no entra: la página lo muestra aparte, contado al día."""
        pesos = self.c["pesos"]
        validos = [(k, c) for k, c in criterios.items() if k != "plazoOferta" and c.get("corto") and c["corto"] != SIN_FICHA]
        favor = sorted((x for x in validos if x[1]["puntaje"] >= 80), key=lambda x: -pesos[x[0]] * x[1]["puntaje"])
        contra = sorted((x for x in validos if x[1]["puntaje"] <= 50), key=lambda x: -pesos[x[0]] * (100 - x[1]["puntaje"]))
        return [c["corto"] for _, c in favor[:3]], [c["corto"] for _, c in contra[:2]]

    def categoria(self, puntaje: float, rubro: int) -> str:
        """La categoría por puntaje, con tope si el rubro no es claro (la
        misma regla repite la página al mover los pesos)."""
        orden = [c["id"] for c in sorted(self.c["categorias"], key=lambda c: -c["desde"])]
        cat = next((c["id"] for c in sorted(self.c["categorias"], key=lambda c: -c["desde"]) if puntaje >= c["desde"]), orden[-1])
        for tope in self.c.get("topesPorRubro", []):
            if rubro < tope["rubroMenorA"] and orden.index(cat) < orden.index(tope["categoriaMaxima"]):
                cat = tope["categoriaMaxima"]
        return cat

    def evaluar_sin_ficha(self, codigo: str, nombre: str, cierre: str | None, en_planilla) -> dict:
        """Candidata cuya ficha todavía no se pidió (tope de consultas): se
        evalúa solo con el nombre y queda marcada."""
        ficha = {"codigo": codigo, "nombre": nombre, "cierre": cierre, "tipo": codigo.rsplit("-", 1)[-1][:-2], "_completa": False}
        r = self.evaluar(ficha, en_planilla)
        r["ficha"] = False
        return r

    # ── criterios ──
    def _rubro(self, rs, ficha, parecidas, descartar) -> dict:
        r = self.c["rubro"]
        rs_nombre = raices(ficha.get("nombre"))
        nucleo, afines, fuera = coincidencias(rs, r["nucleo"]), coincidencias(rs, r["afines"]), coincidencias(rs, r["excluir"])
        resta = coincidencias(rs, r.get("restar", []))
        # El nombre es la señal fuerte; lo que solo aparece en la descripción pesa
        # menos («guardavidas para la piscina temperada» no es climatizar una piscina).
        nucleo_nombre, afines_nombre = coincidencias(rs_nombre, r["nucleo"]), coincidencias(rs_nombre, r["afines"])
        if nucleo:
            base = 85 if nucleo_nombre else 60
        elif afines:
            base = 55 if afines_nombre else 35
        else:
            base = 15
        donde = "" if (nucleo_nombre or (not nucleo and afines_nombre)) else " (solo en la descripción)"
        motivo = [(f"núcleo: {', '.join(nucleo[:3])}" if nucleo else f"afín: {', '.join(afines[:3])}") + donde
                  if (nucleo or afines) else "sin palabras del rubro"]
        if fuera:
            base -= 35
            motivo.append(f"fuera de rubro: {', '.join(fuera[:3])}")
        if resta:
            base -= 10 if nucleo else 25      # «calderas y aire acondicionado» sigue siendo del rubro
            motivo.append(f"resta: {', '.join(resta[:3])}")
        ofertadas = sum(s for s, it in parecidas if it["ofertado"])
        todas = sum(s for s, _ in parecidas)
        if todas:
            p = ofertadas / todas
            # La historia pesa poco: muchos descartes de la Planilla fueron por distancia o plazo, que ya miden otros criterios.
            base = 0.75 * base + 0.25 * (100 * p) + (10 if any(it["ganado"] for s, it in parecidas[:3]) else 0)
            ganadas = [it for _, it in parecidas if it["ganado"]]
            motivo.append(f"{sum(1 for _, it in parecidas if it['ofertado'])} de {len(parecidas)} parecidas se ofertaron"
                          + (f", {len(ganadas)} ganada(s) (N° {', '.join(str(it['req']) for it in ganadas[:3])})" if ganadas else ""))
        en_nombre = coincidencias(rs_nombre, r["excluir"])
        if en_nombre:
            descartar.append("Fuera de rubro: " + ", ".join(en_nombre[:3]))
        if not nucleo and not afines:
            if fuera and not en_nombre:
                descartar.append("Fuera de rubro: " + ", ".join(fuera[:3]))
            elif not fuera and not self.h.muy_parecida_ofertada(ficha.get("nombre") or ""):
                descartar.append("Sin relación clara con el rubro (ni palabras del rubro ni muy parecida a algo ofertado)")
            base = min(base, 45)
        if fuera:
            corto = f"Fuera de rubro: {fuera[0]}"
        elif nucleo:
            corto = f"Del rubro: {nucleo[0]}" + ("" if nucleo_nombre else " (en la descripción)")
        elif afines:
            corto = f"Rubro afín: {afines[0]}" + ("" if afines_nombre else " (en la descripción)")
        else:
            corto = "Parecida a lo ya ofertado" if parecidas else "Sin palabras del rubro"
        return {"puntaje": _acotar(base), "motivo": "; ".join(motivo), "corto": corto}

    def _monto_clp(self, ficha) -> tuple[float | None, str]:
        m, moneda = ficha.get("montoEstimado"), (ficha.get("moneda") or "CLP").upper()
        if m:
            if moneda in ("CLF", "UF"):
                return m * self.uf, "estimado (UF)"
            if moneda == "UTM":
                return m * self.c["monto"]["valorUTM"], "estimado (UTM)"
            if moneda == "CLP":
                return m, "estimado"
        rango = RANGO_TIPO_UTM.get(ficha.get("tipo") or "")
        if rango:
            utm = self.c["monto"]["valorUTM"]
            desde, hasta = (f"{x:,}".replace(",", ".") for x in rango)
            return math.sqrt(rango[0] * rango[1]) * utm, f"por tipo {ficha.get('tipo')}, {desde}–{hasta} UTM"
        return None, "sin dato"

    def _monto(self, monto, fuente, descartar) -> dict:
        r = self.rango
        if monto is None or not r["p10"]:
            return {"puntaje": 50, "motivo": "sin monto publicado ni tipo de licitación conocido",
                    "corto": "Monto no publicado"}
        if r["p25"] <= monto <= r["p75"]:
            p, txt, corto = 100, "en el rango que QUEMPIN más oferta", "en el rango habitual"
        elif r["p10"] <= monto <= r["p90"]:
            p, txt, corto = 85, "dentro del rango habitual", "dentro de lo habitual"
        elif monto < r["p10"]:
            p, txt, corto = max(25, 85 * math.sqrt(monto / r["p10"])), "más chico que lo habitual", "más chico que lo habitual"
        else:
            p, txt, corto = max(20, 85 * (r["p90"] / monto) ** 0.6), "más grande que lo habitual", "más grande que lo habitual"
        if r["maximo"] and monto > r["maximo"]:
            p, txt, corto = 10, f"sobre el máximo de {_pesos(r['maximo'])}: revisar garantías y caja", "sobre el máximo: garantías y caja"
            if self.c["monto"].get("maximo"):       # solo un tope puesto a mano descarta; el de la historia es orientativo
                descartar.append(f"Monto {_pesos(monto)} sobre el máximo de {_pesos(r['maximo'])}")
        estimado = fuente.startswith("por tipo")
        if estimado:
            p = 0.7 * p + 0.3 * 60      # el monto es una suposición: pesa menos
        return {"puntaje": _acotar(p), "motivo": f"{_pesos(monto)} ({fuente}): {txt}",
                "corto": f"{'~' if estimado else ''}{_pesos(monto)}, {corto}"}

    def _duracion_meses(self, ficha, texto) -> float | None:
        d, u = ficha.get("duracion"), ficha.get("unidadDuracion")
        if d and d > 0 and u in UNIDAD_A_MESES:
            return d * UNIDAD_A_MESES[u]
        m = re.search(r"\b(\d{1,3})\s*(mes|meses|ano|anos|dia|dias|semana|semanas)\b", normalizar(texto))
        if m:
            n, unidad = int(m.group(1)), m.group(2)
            return n * {"mes": 1, "meses": 1, "ano": 12, "anos": 12, "dia": 1 / 30, "dias": 1 / 30,
                        "semana": 7 / 30, "semanas": 7 / 30}[unidad]
        return None

    def _dificultad(self, rs, ficha) -> dict:
        c = self.c["dificultad"]
        p, motivos = 100, []
        altas, medias = coincidencias(rs, c["palabrasAltas"]), coincidencias(rs, c["palabrasMedias"])
        if altas:
            p -= c["restaAlta"]
            motivos.append(f"requiere {', '.join(altas[:2])}")
        elif medias:
            p -= c["restaMedia"]
            motivos.append(f"incluye {', '.join(medias[:2])}")
        if self._varios_recintos(ficha):
            p -= c["restaVariosRecintos"]
            motivos.append("varios recintos")
        if ficha.get("obras"):
            p -= c["restaObras"]
            motivos.append("declarada como obra")
        resta_tipo = c["restaPorTipo"].get(ficha.get("tipo") or "", 0)
        if resta_tipo:
            p -= resta_tipo
            motivos.append(f"licitación {ficha.get('tipo')} (más requisitos y garantías)")
        if (ficha.get("items") or 0) > c["muchosItems"]:
            p -= c["restaMuchosItems"]
            motivos.append(f"{ficha['items']} ítems")
        if (ficha.get("etapas") or 1) >= 2:
            p -= c["restaDosEtapas"]
            motivos.append("apertura en dos etapas")
        if ficha.get("tomaRazon"):
            p -= c["restaTomaRazon"]
            motivos.append("toma de razón de Contraloría")
        mantencion = contiene(rs, "mantencion")
        if not motivos:
            simple = "Mantención simple" if mantencion else "Sin señales de complejidad"
            return {"puntaje": _acotar(p), "motivo": simple.lower(), "corto": simple}
        # La frase corta dice hacia dónde empuja: a favor, que es simple; en contra, lo que la complica.
        if p >= 80:
            corto = "Mantención sin mayor complejidad" if mantencion else "Ejecución sin mayor complejidad"
        else:
            corto = motivos[0][:1].upper() + motivos[0][1:]
        return {"puntaje": _acotar(p), "motivo": "; ".join(motivos), "corto": corto}

    def _varios_recintos(self, ficha) -> bool:
        """Se busca el plural tal cual (sin pasar a singular): «al
        establecimiento» es uno solo, «los establecimientos» son varios."""
        texto = " " + normalizar(" ".join(x for x in (ficha.get("nombre"), ficha.get("descripcion")) if x)) + " "
        return any(f" {normalizar(p)} " in texto for p in self.c["dificultad"]["palabrasVariosRecintos"])

    def _ubicacion(self, ficha) -> dict:
        reg = normalizar(ficha.get("region"))
        tabla = {k: v for k, v in self.c["regiones"].items() if not k.startswith("_")}
        pts = next((v for clave, v in tabla.items() if clave in reg), None)
        if pts is None:
            return {"puntaje": self.c["regiones"].get("_sinRegion", 50),
                    "motivo": ficha.get("region") or "región desconocida", "corto": "Región desconocida"}
        lugar = ", ".join(x for x in (ficha.get("comuna"), ficha.get("region")) if x)
        nombre = ficha.get("comuna") or region_corta(ficha.get("region"))
        corto = f"Cerca: {nombre}" if pts >= 80 else (f"Lejos: {region_corta(ficha.get('region'))}" if pts <= 50 else nombre)
        return {"puntaje": pts, "motivo": lugar, "corto": corto}

    @staticmethod
    def _visita_obligatoria(texto) -> bool | None:
        t = normalizar(texto)
        if re.search(r"visita\w*( \w+){0,5} obligatori", t) or re.search(r"obligatori\w*( \w+){0,3} visita", t):
            return True
        if re.search(r"visita\w*( \w+){0,5} (optativ|opcional|voluntari|no obligatori)", t):
            return False
        return None

    def _visita(self, ficha, texto, region_pts, descartar) -> dict:
        fecha = ficha.get("visita")
        if not fecha:
            return {"puntaje": 100, "motivo": "sin visita a terreno en la ficha", "corto": "Sin visita a terreno"}
        obligatoria = self._visita_obligatoria(texto)
        dias = self._dias_para(fecha)
        cuando = mp._fecha_corta(fecha) + (f" {fecha[11:16]}" if len(fecha) > 11 else "")
        tipo = "obligatoria" if obligatoria else ("optativa" if obligatoria is False else "¿obligatoria? (ver bases)")
        if dias is not None and dias < 0:
            if obligatoria:
                descartar.append(f"La visita obligatoria fue el {cuando}")
            reglas = self.c["visitaPasada"]
            return {"puntaje": reglas["optativa"] if obligatoria is False else reglas["obligatoriaODuda"],
                    "motivo": f"visita {tipo} el {cuando}: ya pasó", "corto": "La visita a terreno ya pasó"}
        p = 40 + 0.5 * region_pts           # ir cuesta más mientras más lejos
        if dias is not None and dias < 2:
            p -= 20
        if obligatoria is False:
            p = (p + 100) / 2
        corto = ("Visita optativa" if obligatoria is False else "Visita a terreno") + f" el {mp._fecha_corta(fecha)[:5]}"
        return {"puntaje": _acotar(p), "motivo": f"visita {tipo} el {cuando}"
                + (f" (en {dias:.0f} día(s))" if dias is not None else ""), "corto": corto}

    def _mercado_parecido(self, ficha) -> list[tuple[float, dict]]:
        v = self.h.vector(raices(ficha.get("nombre")))
        unidad = unidad_de(ficha["codigo"])
        pares = []
        for m, mv in self.mercado_vec:
            if m.get("codigo") == ficha["codigo"]:
                continue
            s, _ = self.h.similitud(v, mv)
            if m.get("unidad") == unidad:
                s += 0.3           # el mismo comprador pesa más: suele volver a licitar lo mismo
            if s >= 0.35:
                pares.append((round(s, 3), m))
        pares.sort(key=lambda p: (-p[0], p[1].get("fecha") or ""))
        return pares

    def _comprador(self, ficha, parecidas_mercado) -> dict:
        unidad = unidad_de(ficha["codigo"])
        propias = [it for it in self.h.con_unidad(unidad) if it["codigo"] != ficha["codigo"]]
        p, motivos = 55, []
        ganadas = [it for it in propias if it["ganado"]]
        perdidas = [it for it in propias if it["perdido"]]
        if ganadas:
            p += 35
            motivos.append(f"ya nos adjudicó N° {', '.join(str(it['req']) for it in ganadas[:3])}")
            corto = "Ya nos adjudicó antes"
        elif perdidas:
            p += 10
            motivos.append(f"se le ofertó antes sin ganar (N° {', '.join(str(it['req']) for it in perdidas[:3])})")
            corto = "Le ofertamos antes"
        elif propias:
            motivos.append(f"comprador conocido, solo descartes (N° {', '.join(str(it['req']) for it in propias[:3])})")
            corto = "Comprador conocido"
        else:
            motivos.append("comprador nuevo para QUEMPIN")
            corto = "Comprador nuevo"
        oferentes = [m["oferentes"] for _, m in parecidas_mercado if isinstance(m.get("oferentes"), int)]
        if oferentes:
            prom = sum(oferentes) / len(oferentes)
            if prom <= 2:
                p += 10
                if not ganadas:
                    corto = f"Poca competencia (~{prom:.0f} oferentes)"
            elif prom >= 5:
                p -= 10
                if not ganadas:
                    corto = f"Mucha competencia (~{prom:.0f} oferentes)"
            motivos.append(f"{prom:.1f} oferentes en promedio en {len(oferentes)} licitación(es) parecida(s)")
        mismo = [m for _, m in parecidas_mercado if m.get("unidad") == unidad]
        if mismo:
            m = mismo[0]
            motivos.append(f"ya licitó algo parecido ({(m.get('fecha') or '')[:7]}): ganó {', '.join(m.get('ganadores') or ['?'])}"
                           f" por {_pesos(m.get('monto'))} neto")
        if (ficha.get("reclamos") or 0) > 500:
            p -= 10
            motivos.append(f"{ficha['reclamos']} reclamos de proveedores contra el organismo")
            if not ganadas:
                corto = "Muchos reclamos de proveedores"
        return {"puntaje": _acotar(p), "motivo": "; ".join(motivos), "corto": corto}

    def _dias_para(self, fecha) -> float | None:
        if not fecha:
            return None
        try:
            f = datetime.fromisoformat(fecha if len(fecha) > 10 else fecha + "T23:59")
        except ValueError:
            return None
        return (f - self.ahora).total_seconds() / 86400

    def _plazo(self, ficha, descartar) -> dict:
        """Puntaje por días hasta el cierre, con los tramos de la configuración.
        La página repite esta regla con la fecha del día (plazoOferta en reglas)."""
        dias = self._dias_para(ficha.get("cierre"))
        if dias is None:
            return {"puntaje": 50, "motivo": "sin fecha de cierre", "corto": "Sin fecha de cierre"}
        cuando = mp._fecha_corta(ficha["cierre"])
        tramo = next(t for t in self.c["plazoOferta"]["tramos"] if t["menosDeDias"] is None or dias < t["menosDeDias"])
        if tramo.get("descarta"):
            descartar.append("Cierra en menos de un día" if dias >= 0 else "Ya cerró")
            return {"puntaje": tramo["puntaje"], "motivo": f"cierra el {cuando}: no alcanza", "corto": "Cierra hoy"}
        return {"puntaje": tramo["puntaje"], "motivo": f"cierra el {cuando} ({dias:.0f} días)",
                "corto": f"Cierra en {dias:.0f} días"}

    def _ejecucion(self, meses, ficha) -> dict:
        c = self.c["ejecucion"]
        if meses is None:
            return {"puntaje": c["sinDato"], "motivo": "duración no informada", "corto": "Duración no informada"}
        tramo = next(t for t in c["tramos"] if t["hastaMeses"] is None or meses <= t["hastaMeses"])
        texto = f"{meses:.0f} mes(es)" if meses >= 1 else f"{meses * 30:.0f} día(s)"
        corto = (f"Contrato de {meses:.0f} meses" if meses >= 2 else
                 f"Trabajo de {meses:.0f} mes" if meses >= 1 else f"Trabajo de {meses * 30:.0f} días")
        return {"puntaje": tramo["puntaje"], "motivo": f"{texto}: {tramo['texto']}" + (", renovable" if ficha.get("renovable") else ""),
                "corto": corto + (", renovable" if ficha.get("renovable") else "")}


# ── LA VUELTA ────────────────────────────────────────────────────────────────

def _leer_estado(ruta: Path) -> dict:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _mercado_del_monitor() -> list[dict]:
    """Los resultados que ya trajo el monitor para las licitaciones de la
    Planilla: también son historia de mercado (quién le ganó a QUEMPIN)."""
    salida = []
    for codigo, lic in (_leer_estado(mp.RUTA_ESTADO).get("licitaciones") or {}).items():
        if isinstance(lic, dict) and lic.get("adjudicados"):
            salida.append({"codigo": codigo, "nombre": lic.get("nombre"), "organismo": lic.get("comprador"),
                           "unidad": unidad_de(codigo), "region": None, "fecha": (lic.get("fechaAdjudicacion") or "")[:10] or None,
                           "oferentes": lic.get("oferentes"), "moneda": lic.get("moneda"),
                           "monto": sum(p.get("montoNeto") or 0 for p in lic["adjudicados"]),
                           "ganadores": [p.get("nombre") or p.get("rut") for p in lic["adjudicados"][:3]],
                           "quempin": lic.get("montoQuempin") is not None})
    return salida


def competidores(mercado: list[dict]) -> list[dict]:
    cuenta: dict[str, dict] = {}
    for m in mercado:
        for g in m.get("ganadores") or []:
            if not g or mp.normalizar_rut(g) == mp.normalizar_rut(mp.RUT_QUEMPIN) or "QUEMPIN" in g.upper():
                continue
            c = cuenta.setdefault(g, {"nombre": g, "ganadas": 0, "monto": 0})
            c["ganadas"] += 1
            if (m.get("moneda") or "CLP") == "CLP":
                c["monto"] += m.get("monto") or 0
    return sorted(cuenta.values(), key=lambda c: (-c["ganadas"], -c["monto"]))[:12]


def _barrer_mercado(cliente, estado: dict, evaluador: Evaluador, config: dict, hoy: date) -> None:
    """Historial de mercado, de a poco: cada vuelta lee el listado de unos
    días hacia atrás (una consulta por día) y pide la ficha de las
    adjudicadas del rubro. Lo hecho queda en la caché y la próxima vuelta
    sigue donde quedó, hasta cubrir diasHistoriaMercado. Usa solo las
    consultas que sobran: completar la historia de a poco es lo normal, no una
    vuelta incompleta."""
    def queda_presupuesto() -> bool:
        return cliente.llamadas < cliente.tope

    cc = config["consultas"]
    mercado = estado.setdefault("mercado", {})
    cola = estado.setdefault("colaMercado", [])
    barridos = set(estado.get("diasMercado", []))
    limite = hoy - timedelta(days=cc["diasHistoriaMercado"])
    leidos = 0
    dia = hoy - timedelta(days=1)
    while dia >= limite and leidos < cc["diasMercadoPorVuelta"] and queda_presupuesto():
        if dia.isoformat() not in barridos:
            listado = cliente.obtener("licitaciones.json", fecha=dia.strftime("%d%m%Y")).get("Listado") or []
            for x in listado:
                codigo = mp._texto((x or {}).get("CodigoExterno"), 40) if isinstance(x, dict) else None
                if (codigo and mp._CODIGO_EXACTO.match(codigo) and x.get("CodigoEstado") == 8
                        and codigo not in mercado and codigo not in cola
                        and evaluador.prefiltro(x.get("Nombre") or "") >= 60):
                    cola.append(codigo)
            barridos.add(dia.isoformat())
            estado["diasMercado"] = sorted(d for d in barridos if d >= limite.isoformat())
            leidos += 1
        dia -= timedelta(days=1)
    while cola and queda_presupuesto():
        codigo = cola[0]
        crudo = cliente.licitacion(codigo)
        leida = leer_adjudicada(crudo, codigo) if crudo else None
        mercado[codigo] = leida or {"codigo": codigo, "sinAdjudicados": True}
        cola.pop(0)


def revisar(raiz: Path | None, cliente=None, enviar: bool = True, ruta_estado: Path | None = None,
            config: dict | None = None, ahora: datetime | None = None, sin_red: bool = False,
            reqs: list[dict] | None = None) -> dict:
    """Una vuelta completa. Devuelve {'datos': publicación, 'llamadas', 'avisos'}.
    Con 'enviar' publica oportunidades.json en la carpeta de intercambio; sin
    él solo consulta (actualiza la caché local). Con 'sin_red' evalúa con lo
    que ya está en la caché. El tablero publicado (con contraseña) lo arma
    Visualizador Web/build_visualizador.py con estos mismos datos."""
    config = config or cargar_config()
    ahora = ahora or datetime.now()
    ruta_estado = ruta_estado or RUTA_ESTADO
    estado = _leer_estado(ruta_estado)
    fichas = estado.setdefault("fichas", {})
    avisos: list[str] = []
    incompleta = False

    if reqs is None:
        sobre = intercambio.leer_publicacion(raiz, requerimientos.PUBLICACION) if raiz else None
        reqs = ((sobre or {}).get("datos") or {}).get("requerimientos") or []
    if not reqs:
        avisos.append("No hay Planilla de Ingreso publicada: se evalúa sin la historia de QUEMPIN.")
    historia = Historia(reqs)

    def mercado_actual():
        return [m for m in (estado.get("mercado") or {}).values() if isinstance(m, dict) and m.get("ganadores")] + _mercado_del_monitor()

    evaluador = Evaluador(config, historia, mercado_actual(), ahora, valor_uf(config))

    if not sin_red:
        cliente = cliente or mp.Cliente(mp.leer_ticket(), tope=config["consultas"]["tope"])
        try:
            listado = cliente.obtener("licitaciones.json", estado="activas").get("Listado") or []
            activas = {}
            for x in listado:
                codigo = mp._texto(x.get("CodigoExterno"), 40) if isinstance(x, dict) else None
                if codigo and mp._CODIGO_EXACTO.match(codigo):
                    activas[codigo] = {"nombre": mp._texto(x.get("Nombre"), 200), "cierre": mp._fecha(x.get("FechaCierre"))}
            estado["activas"] = activas
            estado["activasConsultado"] = ahora.isoformat(timespec="seconds")
            candidatas = sorted(((evaluador.prefiltro(v["nombre"] or ""), c) for c, v in activas.items()), reverse=True)
            candidatas = [c for p, c in candidatas if p > 0][: config["prefiltro"]["maxCandidatas"]]
            estado["candidatas"] = candidatas
            refresco = timedelta(days=config["consultas"]["diasRefrescoFicha"])
            for codigo in candidatas:
                previa = fichas.get(codigo)
                if previa and ahora - datetime.fromisoformat(previa["_consultado"]) < refresco:
                    continue
                crudo = cliente.licitacion(codigo)
                if crudo:
                    fichas[codigo] = dict(leer_ficha(crudo, codigo), _consultado=ahora.isoformat(timespec="seconds"))
            try:
                _barrer_mercado(cliente, estado, evaluador, config, ahora.date())
            except mp.TopeDeLlamadas:
                pass        # un reintento de la API gastó lo último: la historia sigue en la próxima vuelta
        except mp.TopeDeLlamadas:
            incompleta = True
            avisos.append("Se alcanzó el tope de consultas de esta vuelta: las fichas y el historial que faltan siguen en la próxima.")
        finally:
            # Las fichas de licitaciones que ya no están publicadas se olvidan al mes.
            viejas = (ahora - timedelta(days=30)).isoformat()
            for codigo in [c for c, f in fichas.items() if c not in (estado.get("activas") or {}) and f.get("_consultado", "") < viejas]:
                del fichas[codigo]
            estado["actualizado"] = ahora.isoformat(timespec="seconds")
            intercambio._escribir_json_atomico(ruta_estado, estado)
        evaluador = Evaluador(config, historia, mercado_actual(), ahora, valor_uf(config))
    elif not estado.get("activas"):
        avisos.append("La caché está vacía: corre una vez con red.")

    activas = estado.get("activas") or {}
    oportunidades = []
    for codigo in estado.get("candidatas") or []:
        if codigo not in activas:
            continue
        it = historia.por_codigo.get(codigo)
        en_planilla = {"req": it["req"], "estado": it["estado"]} if it else None
        ficha = fichas.get(codigo)
        if ficha and ficha.get("estadoCodigo") not in (None, 5):
            continue
        if ficha:
            oportunidades.append(evaluador.evaluar(ficha, en_planilla))
        else:
            oportunidades.append(evaluador.evaluar_sin_ficha(codigo, activas[codigo]["nombre"], activas[codigo]["cierre"], en_planilla))
    # Primero la categoría (una «Buena» por tope de rubro no pasa delante de una «Prioritaria»), después el puntaje.
    rango_categoria = {c["id"]: i for i, c in enumerate(sorted(config["categorias"], key=lambda c: -c["desde"]))}
    oportunidades.sort(key=lambda o: (rango_categoria.get(o["categoria"], len(rango_categoria)), -o["puntaje"]))

    datos = publicacion(oportunidades, evaluador, historia, config, estado, avisos, incompleta, ahora)
    sobre_pub = {"esquema": intercambio.ESQUEMA, "herramienta": HERRAMIENTA, "generado": intercambio.ahora_iso(), "datos": datos}
    errores = esquemas.validar_publicacion(PUBLICACION, sobre_pub)
    if errores:
        raise ValueError("oportunidades.json no cumple su esquema: " + "; ".join(errores[:5]))
    if enviar and raiz:
        intercambio.publicar(raiz, PUBLICACION, HERRAMIENTA, datos)
    return {"datos": datos, "llamadas": getattr(cliente, "llamadas", 0), "avisos": avisos, "incompleta": incompleta}


def publicacion(oportunidades, evaluador: Evaluador, historia: Historia, config, estado, avisos, incompleta, ahora) -> dict:
    mercado = evaluador.mercado
    fechas = sorted(m["fecha"] for m in mercado if m.get("fecha"))
    pesos = config["pesos"]
    return {
        "consultado": ahora.astimezone().isoformat(timespec="seconds"),
        "completo": not incompleta,
        "criterios": [{"id": i, "nombre": n, "peso": pesos[i], "descripcion": d} for i, n, d in CRITERIOS],
        "categorias": config["categorias"],
        "topesPorRubro": config.get("topesPorRubro", []),
        # Lo que la página recalcula con la fecha del día (una licitación se
        # mira días después de evaluada): misma tabla que usa Evaluador.
        "reglas": {"plazoOferta": config["plazoOferta"]["tramos"], "visitaPasada": config["visitaPasada"]},
        "perfil": {
            "historia": historia.resumen(),
            "montoHabitual": dict({k: (round(v) if v else None) for k, v in evaluador.rango.items()},
                                  maximoFijo=bool(config["monto"].get("maximo"))),
            "mercado": {"licitaciones": len(mercado), "desde": fechas[0] if fechas else None,
                        "diasBarridos": len(estado.get("diasMercado") or []),
                        "diasObjetivo": config["consultas"]["diasHistoriaMercado"]},
            "competidores": competidores(mercado),
            "publicadas": len(estado.get("activas") or {}),
            "candidatas": len(estado.get("candidatas") or []),
        },
        "oportunidades": oportunidades,
        "avisos": avisos,
    }


# ── LÍNEA DE COMANDOS ────────────────────────────────────────────────────────

def _raiz():
    import ubicacion
    raiz = ubicacion.ubicar_intercambio(AQUI)
    if raiz is None or not intercambio.es_carpeta_de_intercambio(raiz):
        print("[AVISO] No se encontró la carpeta de intercambio: se evalúa sin la historia de la Planilla.")
        return None
    return raiz


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except AttributeError:
        pass
    orden = argv[0] if argv else ""
    if orden not in ("status", "revisar"):
        print(__doc__.split("Uso:")[1])
        return 2
    raiz = _raiz()
    try:
        r = revisar(raiz, enviar=orden == "revisar", sin_red="--sin-red" in argv)
    except mp.ErrorMercadoPublico as error:
        print(f"[ERROR] {error}")
        return 1
    d = r["datos"]
    p = d["perfil"]
    print(f"Mercado Público: {p['publicadas']} licitaciones publicadas, {p['candidatas']} candidatas del rubro, "
          f"{len(d['oportunidades'])} evaluadas; historial de mercado con {p['mercado']['licitaciones']} adjudicadas "
          f"({p['mercado']['diasBarridos']} de {p['mercado']['diasObjetivo']} días); {r['llamadas']} consulta(s).")
    for o in d["oportunidades"][:15]:
        marca = "DESCARTAR" if o["categoria"] == "descartar" else o["categoria"].upper()
        print(f"  {o['puntaje']:5.1f}  {marca:<11} {o['codigo']:<18} {(o['nombre'] or '')[:60]}"
              + (f"  [Planilla N° {o['enPlanilla']['req']}]" if o.get("enPlanilla") else ""))
    for a in r["avisos"]:
        print(f"  [AVISO] {a}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
