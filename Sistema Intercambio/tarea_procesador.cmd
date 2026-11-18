@echo off
setlocal

rem Wrapper para el Programador de tareas de Windows: corre el procesador del
rem intercambio (procesar.py) cada 5 minutos (decision del usuario, 2026-11-11; antes cada 2 horas). Mercado
rem Publico va cada 3 horas y la UF una vez al dia (TURNO_SEG de procesar.py). Su propio log va a
rem logs\procesador_AAAA-MM.log (una linea por vuelta con novedades).

set "PROYECTO=C:\Users\quemp\OneDrive - QUEMPIN SPA\Escritorio\Proyectos Claude\Finanzas QUEMPIN"
set "PYTHON=C:\Users\quemp\AppData\Local\Python\pythoncore-3.14-64\python.exe"

cd /d "%PROYECTO%\Sistema Intercambio"
"%PYTHON%" procesar.py > nul 2>&1
exit /b %ERRORLEVEL%
