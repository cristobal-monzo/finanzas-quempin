# -*- coding: utf-8 -*-
"""
estado_reportes.py -- Manifiesto de que reportes PDF quedaron desactualizados
(cambiaron sus datos de entrada desde la ultima generacion). Solo detecta y
marca -- nunca dispara redaccion ni renderizado.
"""

import hashlib
import json
from pathlib import Path


def calcular_hash_entidad(datos: dict) -> str:
    """Hash sha256 estable (claves ordenadas) de un paquete de datos."""
    payload = json.dumps(datos, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cargar_estado(ruta_estado: Path) -> dict:
    ruta_estado = Path(ruta_estado)
    if not ruta_estado.exists():
        return {}
    return json.loads(ruta_estado.read_text(encoding="utf-8"))


def guardar_estado(ruta_estado: Path, estado: dict) -> None:
    ruta_estado = Path(ruta_estado)
    ruta_estado.parent.mkdir(parents=True, exist_ok=True)
    ruta_estado.write_text(
        json.dumps(estado, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )


def detectar_desactualizados(paquetes_actuales: dict[str, dict], estado: dict) -> list[str]:
    """paquetes_actuales: clave (ej. 'proyecto:UMAG') -> paquete de datos
    actual. Devuelve las claves sin reporte previo o cuyo hash cambio."""
    desactualizados = []
    for clave, datos in paquetes_actuales.items():
        hash_actual = calcular_hash_entidad(datos)
        entrada_previa = estado.get(clave)
        if entrada_previa is None or entrada_previa.get("hash") != hash_actual:
            desactualizados.append(clave)
    return sorted(desactualizados)


def marcar_generado(estado: dict, clave: str, datos: dict, generado_el: str) -> dict:
    """Devuelve un estado NUEVO (no muta el original) con clave actualizada."""
    nuevo_estado = dict(estado)
    nuevo_estado[clave] = {"hash": calcular_hash_entidad(datos), "generado_el": generado_el}
    return nuevo_estado
