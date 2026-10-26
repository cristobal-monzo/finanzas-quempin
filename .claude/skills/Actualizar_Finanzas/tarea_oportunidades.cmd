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

rem Con el PC apagado a las 9:00 la tarea corre al encenderlo, cuando la red todavia no llega: el 22 y
rem el 23-10-2026 Mercado Publico no respondio ("getaddrinfo failed") y el tablero quedo con los datos
rem del 20-10 hasta el 25-10. Se espera hasta 10 minutos a que el nombre de la API se resuelva (la
rem tarea se corta a los 45; una vuelta normal toma menos de 20).
powershell -NoProfile -Command "for ($i = 0; $i -lt 20; $i++) { try { [Net.Dns]::GetHostAddresses('api.mercadopublico.cl') | Out-Null; if ($i) { Write-Output ('Red lista despues de ' + ($i * 30) + ' s.') }; exit 0 } catch { Start-Sleep -Seconds 30 } }; exit 1" >> "%LOG%" 2>&1
if errorlevel 1 echo [AVISO] Sin red despues de 10 minutos: se intenta igual.>> "%LOG%"

"%PYTHON%" "%DRIVER%" oportunidades >> "%LOG%" 2>&1
set "CODIGO=%ERRORLEVEL%"

echo.>> "%LOG%"
echo Fin: %DATE% %TIME%  (codigo de salida: %CODIGO%)>> "%LOG%"

rem Conservar solo los ultimos 30 logs (un mes).
for /f "skip=30 delims=" %%f in ('dir /b /o-d "%LOGDIR%\oportunidades_*.log" 2^>nul') do del "%LOGDIR%\%%f"

exit /b %CODIGO%
