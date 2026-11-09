"""Respaldo diario de los registros del Portal (2026-11-09).

Lo que el Portal guarda vive solo en la carpeta de Intercambio (OneDrive):
``publicado/`` (Planificación, vehículos, ejecución, cierres, Gantt…),
``buzon/`` y ``procesado/``. OneDrive guarda versiones archivo por archivo, pero
no permite volver *todo* a como estaba un día. Este módulo deja un ``.zip``
por día con esas carpetas y la Planilla de Ingreso.

Destino: FUERA de OneDrive, para que un error de sincronización no se lleve
también el respaldo. Por defecto ``%LOCALAPPDATA%\\QUEMPIN\\respaldos-intercambio``;
``QUEMPIN_RESPALDO_DESTINO`` lo cambia (p. ej. a un disco externo). Se guardan
los últimos ``DIAS_A_GUARDAR`` zips.

Restaurar: abrir el zip del día y copiar los archivos de vuelta a la carpeta de
Intercambio (cerrar antes el Portal y pausar el procesador).
"""
from __future__ import annotations

import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

CARPETAS = ("publicado", "buzon", "procesado")
DIAS_A_GUARDAR = 30
PREFIJO = "intercambio-"


def destino() -> Path:
    propio = os.environ.get("QUEMPIN_RESPALDO_DESTINO")
    if propio:
        return Path(propio)
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(base) / "QUEMPIN" / "respaldos-intercambio"


def nombre_del_dia(fecha: datetime | None = None) -> str:
    return f"{PREFIJO}{(fecha or datetime.now()):%Y-%m-%d}.zip"


def respaldar(raiz: Path, planilla: Path | None = None, carpeta: Path | None = None,
              fecha: datetime | None = None) -> tuple[Path, int]:
    """Escribe el zip del día (lo reemplaza si ya existe) y poda los viejos.
    Devuelve (ruta del zip, cantidad de archivos)."""
    carpeta = carpeta or destino()
    carpeta.mkdir(parents=True, exist_ok=True)
    final = carpeta / nombre_del_dia(fecha)
    temporal = final.with_suffix(".zip.tmp")
    n = 0
    with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in CARPETAS:
            base = Path(raiz) / sub
            if not base.is_dir():
                continue
            for archivo in sorted(base.rglob("*")):
                if archivo.is_file():
                    try:
                        z.write(archivo, Path(sub) / archivo.relative_to(base))
                        n += 1
                    except OSError:
                        pass   # archivo solo en la nube o bloqueado: se toma mañana
        if planilla and Path(planilla).is_file():
            try:
                z.write(planilla, Path("planilla") / Path(planilla).name)
                n += 1
            except OSError:
                pass
    os.replace(temporal, final)
    for viejo in sorted(carpeta.glob(f"{PREFIJO}*.zip"))[:-DIAS_A_GUARDAR]:
        viejo.unlink(missing_ok=True)
    return final, n
