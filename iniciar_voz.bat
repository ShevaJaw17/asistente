@echo off
title Asistente Robin - Modo Voz
cd /d "%~dp0"
set PYTHON="%~dp0venv\Scripts\python.exe"
if not exist %PYTHON% (
    echo ERROR: No se encontro el entorno virtual (venv).
    pause
    exit /b 1
)
echo Verificando que el servidor llama.cpp este corriendo...
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo El servidor llama.cpp NO esta corriendo. Abrelo con iniciar_servidor.bat primero.
    pause
    exit /b 1
)
echo.
echo Modo voz: habla por el microfono y Robin responde en voz alta.
echo Di "termina" para salir.
echo.
%PYTHON% "%~dp0asistente.py" --voz
pause
