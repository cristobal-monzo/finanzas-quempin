"""Token de Claude Code para la corrida programada (2026-11-19).

La tarea de lunes a viernes abre Claude Code sin pantalla para que lea las facturas nuevas. El inicio de sesión
normal vence cada pocas semanas; para una tarea sin nadie al frente, Claude Code da un token de larga duración con
`claude setup-token`. Aquí se guarda cifrado con DPAPI (solo este usuario de Windows en este computador lo abre),
fuera de OneDrive, igual que el ticket de Mercado Público.

  py -3.14 token_claude.py guardar   # pega el token de `claude setup-token` (no se ve al escribirlo)
  py -3.14 token_claude.py estado    # dice si hay uno guardado, sin mostrarlo
  py -3.14 token_claude.py leer      # lo escribe en la salida: solo para tarea_programada.cmd
  py -3.14 token_claude.py borrar
"""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

ENTROPIA = b"QUEMPIN Claude Code token"


def ruta_token() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "QUEMPIN" / "claude.token"


def _dpapi(datos: bytes, proteger: bool) -> bytes:
    """CryptProtectData / CryptUnprotectData con la clave del usuario de Windows, sin abrir diálogos."""
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(b: bytes) -> Blob:
        buffer = ctypes.create_string_buffer(b, len(b))
        return Blob(len(b), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    entrada, entropia, salida = blob(datos), blob(ENTROPIA), Blob()
    sin_interfaz = 0x1
    if proteger:
        ok = crypt32.CryptProtectData(ctypes.byref(entrada), "QUEMPIN Claude Code", ctypes.byref(entropia),
                                      None, None, sin_interfaz, ctypes.byref(salida))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(entrada), None, ctypes.byref(entropia),
                                        None, None, sin_interfaz, ctypes.byref(salida))
    if not ok:
        raise OSError("Windows no pudo " + ("cifrar" if proteger else "descifrar") + " el token")
    try:
        return ctypes.string_at(salida.pbData, salida.cbData)
    finally:
        kernel32.LocalFree(salida.pbData)


def guardar(token: str, ruta: Path | None = None) -> Path:
    token = (token or "").strip()
    if len(token) < 20 or any(c.isspace() for c in token):
        raise ValueError("eso no parece un token de `claude setup-token`")
    ruta = ruta or ruta_token()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    temporal.write_bytes(_dpapi(token.encode("utf-8"), proteger=True))
    os.replace(temporal, ruta)
    return ruta


def leer(ruta: Path | None = None) -> str | None:
    """El token guardado, o None si no hay o no se puede abrir (la tarea sigue con el inicio de sesión normal)."""
    ruta = ruta or ruta_token()
    try:
        return _dpapi(ruta.read_bytes(), proteger=False).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def main(args: list[str]) -> int:
    orden = args[0] if args else "estado"
    if orden == "guardar":
        ruta = guardar(getpass.getpass("Token de `claude setup-token` (no se ve al escribir): "))
        print(f"Guardado cifrado en {ruta}")
    elif orden == "leer":
        token = leer()
        if not token:
            return 1
        sys.stdout.write(token)
    elif orden == "borrar":
        ruta_token().unlink(missing_ok=True)
        print("Borrado.")
    elif orden == "estado":
        print("Hay un token guardado." if leer() else
              "No hay token: la tarea usa el inicio de sesión normal de Claude Code, que vence cada pocas semanas.")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
