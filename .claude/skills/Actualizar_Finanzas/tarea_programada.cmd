@echo off
setlocal

rem Wrapper para el Programador de tareas de Windows (tarea "Actualizar Finanzas QUEMPIN",
rem lunes a viernes a las 10:00 desde el 2026-11-19; antes solo los lunes).
rem
rem 1. Claude Code sin pantalla lee las facturas nuevas del Centro de Costos y anota las que
rem    cumplen las reglas de corrida_programada.md en datos_extraidos.json. Solo puede leer,
rem    correr py -3.14 y escribir ese archivo; nunca corre run, publicar, separar ni eliminar.
rem 2. Despues, siempre: /Actualizar_Finanzas run --con-pendientes (registra lo anotado, deja
rem    las otras en la bandeja, actualiza todo y publica). Si Claude Code falta, no tiene
rem    sesion o falla, el paso 2 corre igual, como antes del 2026-11-19.
rem
rem   tarea_programada.cmd          corrida normal
rem   tarea_programada.cmd prueba   solo el paso 1, sin escribir nada (log *_prueba_*)
rem
rem Token de larga duracion para Claude Code (el inicio de sesion normal vence):
rem   claude setup-token   y despues   py -3.14 token_claude.py guardar

set "PROYECTO=C:\Users\quemp\OneDrive - QUEMPIN SPA\Escritorio\Proyectos Claude\Finanzas QUEMPIN"
set "PYTHON=C:\Users\quemp\AppData\Local\Python\pythoncore-3.14-64\python.exe"
set "DRIVER=%PROYECTO%\.claude\skills\Actualizar_Finanzas\driver.py"
set "SKILL=%~dp0"
set "CLAUDE=%APPDATA%\npm\claude.cmd"
set "LOGDIR=%PROYECTO%\logs"
set "MODO=%~1"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "STAMP=%%i"
if /i "%MODO%"=="prueba" (
    set "LOG=%LOGDIR%\actualizar_finanzas_prueba_%STAMP%.log"
    set "PEDIDO=MODO PRUEBA. Corre /Actualizar_Finanzas como corrida programada: solo lee e informa."
    set "PUEDE_ESCRIBIR="
) else (
    set "LOG=%LOGDIR%\actualizar_finanzas_%STAMP%.log"
    set "PEDIDO=Corre /Actualizar_Finanzas como corrida programada."
    set "PUEDE_ESCRIBIR=Edit(./Centro de Costos/Sistema/datos_extraidos.json)"
)

cd /d "%PROYECTO%"

echo ============================================================>> "%LOG%"
echo Inicio: %DATE% %TIME%>> "%LOG%"
echo ============================================================>> "%LOG%"

rem --- Paso 1: Claude Code lee las facturas nuevas -------------------------------------
for /f "delims=" %%t in ('""%PYTHON%" "%SKILL%token_claude.py" leer 2^>nul"') do set "CLAUDE_CODE_OAUTH_TOKEN=%%t"

set "CODIGO_CLAUDE=sin Claude Code"
if exist "%CLAUDE%" (
    echo.>> "%LOG%"
    echo --- Facturas nuevas: Claude Code ---------------------------->> "%LOG%"
    if defined PUEDE_ESCRIBIR (
        call "%CLAUDE%" -p "%PEDIDO%" --append-system-prompt-file "%SKILL%corrida_programada.md" --model sonnet --permission-mode dontAsk --allowedTools Read Glob Grep "Bash(py -3.14 *)" "Bash(cd *)" "%PUEDE_ESCRIBIR%" --disallowedTools "Bash(* run*)" "Bash(*publicar*)" "Bash(*separar*)" "Bash(*eliminar*)" >> "%LOG%" 2>&1
    ) else (
        call "%CLAUDE%" -p "%PEDIDO%" --append-system-prompt-file "%SKILL%corrida_programada.md" --model sonnet --permission-mode dontAsk --allowedTools Read Glob Grep "Bash(py -3.14 *)" "Bash(cd *)" --disallowedTools Edit Write "Bash(* run*)" "Bash(*publicar*)" "Bash(*separar*)" "Bash(*eliminar*)" >> "%LOG%" 2>&1
    )
    call set "CODIGO_CLAUDE=%%ERRORLEVEL%%"
)
set "CLAUDE_CODE_OAUTH_TOKEN="
echo.>> "%LOG%"
echo [Claude Code: %CODIGO_CLAUDE%]>> "%LOG%"

if /i "%MODO%"=="prueba" (
    echo Fin de la prueba: %DATE% %TIME%>> "%LOG%"
    exit /b 0
)

rem --- Paso 2: la actualizacion completa, siempre ---------------------------------------
echo.>> "%LOG%"
echo --- /Actualizar_Finanzas run --con-pendientes -------------->> "%LOG%"
"%PYTHON%" "%DRIVER%" run --con-pendientes >> "%LOG%" 2>&1
set "CODIGO=%ERRORLEVEL%"

echo.>> "%LOG%"
echo Fin: %DATE% %TIME%  (codigo de salida: %CODIGO%)>> "%LOG%"

rem Conservar solo los ultimos 30 logs.
for /f "skip=30 delims=" %%f in ('dir /b /o-d "%LOGDIR%\actualizar_finanzas_*.log" 2^>nul') do del "%LOGDIR%\%%f"

exit /b %CODIGO%
