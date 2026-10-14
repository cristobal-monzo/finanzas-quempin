@echo off
setlocal

rem Wrapper para el Programador de tareas de Windows (tarea "Oportunidades
rem Mercado Publico QUEMPIN", todos los dias, 2026-10-13): arma el tablero de
rem Oportunidades en Mercado Publico y lo publica en GitHub Pages si quedo al
rem dia (driver.py oportunidades). Deja log en logs\.

set "PROYECTO=C:\Users\quemp\OneDrive - QUEMPIN SPA\Escritorio\Proyectos Claude\Finanzas QUEMPIN"
set "PYTHON=C:\Users\quemp\AppData\Local\Python\pythoncore-3.14-64\python.exe"
set "DRIVER=%PROYECTO%\.claude\skills\Actualizar_Finanzas\driver.py"
set "LOGDIR=%PROYECTO%\logs"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "STAMP=%%i"
set "LOG=%LOGDIR%\oportunidades_%STAMP%.log"

cd /d "%PROYECTO%"

echo ============================================================>> "%LOG%"
echo Inicio: %DATE% %TIME%>> "%LOG%"
echo ============================================================>> "%LOG%"

"%PYTHON%" "%DRIVER%" oportunidades >> "%LOG%" 2>&1
set "CODIGO=%ERRORLEVEL%"

echo.>> "%LOG%"
echo Fin: %DATE% %TIME%  (codigo de salida: %CODIGO%)>> "%LOG%"

rem Conservar solo los ultimos 30 logs (un mes).
for /f "skip=30 delims=" %%f in ('dir /b /o-d "%LOGDIR%\oportunidades_*.log" 2^>nul') do del "%LOGDIR%\%%f"

exit /b %CODIGO%
