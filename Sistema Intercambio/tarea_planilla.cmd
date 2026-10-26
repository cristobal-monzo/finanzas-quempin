@echo off
setlocal

rem Wrapper para el Programador de tareas de Windows: cada 10 minutos (decision del usuario,
rem 2026-10-26) registra en la Planilla de Ingreso los proyectos nuevos del Formulador y deja fijo
rem el N de cada fila (planilla_escritura.py). Solo abre Excel si hay algo que escribir. Su log va a
rem logs\planilla_AAAA-MM.log (una linea por vuelta que hizo algo).

set "PROYECTO=C:\Users\quemp\OneDrive - QUEMPIN SPA\Escritorio\Proyectos Claude\Finanzas QUEMPIN"
set "PYTHON=C:\Users\quemp\AppData\Local\Python\pythoncore-3.14-64\python.exe"

cd /d "%PROYECTO%\Sistema Intercambio"
"%PYTHON%" planilla_escritura.py > nul 2>&1
exit /b %ERRORLEVEL%
