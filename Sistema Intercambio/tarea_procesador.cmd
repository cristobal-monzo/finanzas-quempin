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
set "CODIGO=%ERRORLEVEL%"

rem El resumen cifrado del Portal en el telefono (resumen_movil.py, 2026-11-18): lo arma y, si toca (cambio algo,
rem como maximo cada 30 min, o una vez por hora; lunes a sabado de 7 a 20), lo sube a gh-pages. procesar.py nunca
rem publica en GitHub: va aparte y su falla no cambia el codigo de salida del procesador. Sin preguntas de git.
rem Anota cada subida y cada falla en logs\resumen_movil_AAAA-MM.log.
set "GIT_TERMINAL_PROMPT=0"
"%PYTHON%" resumen_movil.py publicar > nul 2>&1
exit /b %CODIGO%
