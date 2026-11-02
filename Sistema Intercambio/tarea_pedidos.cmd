@echo off
setlocal

rem Wrapper para el Programador de tareas de Windows: cada minuto mira si alguien apreto "Actualizar
rem datos" en el Portal (mensaje pedir-vuelta en el buzon) y, solo entonces, da una vuelta del procesador
rem (2026-11-02). Sin pedido termina al tiro y no escribe nada. Su log es el del procesador.

set "PROYECTO=C:\Users\quemp\OneDrive - QUEMPIN SPA\Escritorio\Proyectos Claude\Finanzas QUEMPIN"
set "PYTHON=C:\Users\quemp\AppData\Local\Python\pythoncore-3.14-64\python.exe"

cd /d "%PROYECTO%\Sistema Intercambio"
"%PYTHON%" procesar.py --si-hay-pedido > nul 2>&1
exit /b %ERRORLEVEL%
