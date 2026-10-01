@echo off
setlocal

rem Wrapper para el Programador de tareas de Windows.
rem Corre /Actualizar_Finanzas run sobre los datos reales y deja log en logs\.

set "PROYECTO=C:\Users\quemp\OneDrive - QUEMPIN SPA\Escritorio\Proyectos Claude\Finanzas QUEMPIN"
set "PYTHON=C:\Users\quemp\AppData\Local\Python\pythoncore-3.14-64\python.exe"
set "DRIVER=%PROYECTO%\.claude\skills\Actualizar_Finanzas\driver.py"
set "LOGDIR=%PROYECTO%\logs"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "STAMP=%%i"
set "LOG=%LOGDIR%\actualizar_finanzas_%STAMP%.log"

cd /d "%PROYECTO%"

echo ============================================================>> "%LOG%"
echo Inicio: %DATE% %TIME%>> "%LOG%"
echo ============================================================>> "%LOG%"

"%PYTHON%" "%DRIVER%" run >> "%LOG%" 2>&1
set "CODIGO=%ERRORLEVEL%"

echo.>> "%LOG%"
echo Fin: %DATE% %TIME%  (codigo de salida: %CODIGO%)>> "%LOG%"

rem Conservar solo los ultimos 30 logs.
for /f "skip=30 delims=" %%f in ('dir /b /o-d "%LOGDIR%\actualizar_finanzas_*.log" 2^>nul') do del "%LOGDIR%\%%f"

exit /b %CODIGO%
