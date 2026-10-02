@echo off
setlocal

rem Wrapper para el Programador de tareas de Windows: corre el procesador del
rem intercambio (procesar.py) cada 2 horas (decision del usuario, 2026-10-02). Su propio log va a
rem logs\procesador_AAAA-MM.log (una linea por vuelta).

set "PROYECTO=C:\Users\quemp\OneDrive - QUEMPIN SPA\Escritorio\Proyectos Claude\Finanzas QUEMPIN"
set "PYTHON=C:\Users\quemp\AppData\Local\Python\pythoncore-3.14-64\python.exe"

cd /d "%PROYECTO%\Sistema Intercambio"
"%PYTHON%" procesar.py > nul 2>&1
exit /b %ERRORLEVEL%
