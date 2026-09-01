@echo off
rem ============================================================
rem  Instala / desinstala el autoarranque de Robin al iniciar sesión.
rem  Usa una tarea programada de Windows (schtasks).
rem  Uso:  doble clic para instalar, o "instalar_autoarranque.bat quitar"
rem ============================================================
cd /d "%~dp0"

if /I "%~1"=="quitar" (
    schtasks /Delete /TN "RobinAutoarranque" /F >nul 2>&1
    echo Autoarranque desinstalado (tarea RobinAutoarranque eliminada).
    pause
    exit /b 0
)

echo Instalando autoarranque de Robin al iniciar sesion...
schtasks /Create /TN "RobinAutoarranque" /TR "\"%~dp0autoarranque.bat\"" /SC ONLOGON /RL LIMITED /F
if errorlevel 1 (
    echo ERROR: no se pudo crear la tarea. Probablemente falte iniciar la terminal como administrador.
    pause
    exit /b 1
)

echo.
echo Listo. La tarea 'RobinAutoarranque' se ejecutara cada vez que inicies sesion.
echo Levanta: servidor llama.cpp (8080) + servidor web/chat+programador (8000).
echo.
echo Para desinstalarlo: ejecuta  instalar_autoarranque.bat quitar
pause
