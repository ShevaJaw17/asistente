@echo off
title Nico Robin - Asistente
setlocal
set "DIR=%~dp0"

echo === Nico Robin - Asistente Virtual ===
echo.

rem --- 1) Verificar/cargar el servidor llama.cpp (puerto 8080) ---
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo [Servidor] No esta corriendo. Iniciandolo en background...
    start "" /min "%DIR%iniciar_servidor.bat"
    echo [Servidor] Esperando a que este listo...
    powershell -NoProfile -Command "$d=(Get-Date).AddSeconds(120); do { if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) { exit 0 }; Start-Sleep -Seconds 2 } while ((Get-Date) -lt $d); exit 1"
    if errorlevel 1 (
        echo [ERROR] No se pudo iniciar el servidor a tiempo.
        echo Asegurate de que tu GPU soporta Vulkan y vuelve a intentarlo.
        echo.
        pause
        exit /b 1
    )
)
echo [Servidor] Listo en http://127.0.0.1:8080
echo.

rem --- 2) Lanzar la interfaz grafica sin consola ---
set "PYW=%DIR%venv\Scripts\pythonw.exe"
if exist "%PYW%" goto :ok
echo [ERROR] No se encontro el entorno virtual en %PYW%
pause
exit /b 1

:ok
echo Abriendo interfaz grafica...
start "" "%PYW%" "%DIR%lanzar_gui.py"
echo.
echo Hecho. Si la ventana no aparece en unos segundos, revisa gui_run.log
timeout /t 3 >nul
endlocal