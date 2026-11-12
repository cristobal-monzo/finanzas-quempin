@echo off
setlocal

rem Wrapper para el Programador de tareas de Windows: cada minuto (2026-11-12; antes cada 10, decision del usuario
rem del 2026-10-26) pasa a la Planilla de Ingreso lo nuevo del Formulador y del Portal, y lo cambiado en
rem el Portal; publica lo cambiado en el Excel y deja fijo el N de cada fila (planilla_escritura.py).
rem Solo abre Excel si hay algo que escribir. Su log va a logs\planilla_AAAA-MM.log (una linea por
rem vuelta que hizo algo).

set "PROYECTO=C:\Users\quemp\OneDrive - QUEMPIN SPA\Escritorio\Proyectos Claude\Finanzas QUEMPIN"
set "PYTHON=C:\Users\quemp\AppData\Local\Python\pythoncore-3.14-64\python.exe"

cd /d "%PROYECTO%\Sistema Intercambio"
"%PYTHON%" planilla_escritura.py > nul 2>&1
exit /b %ERRORLEVEL%
