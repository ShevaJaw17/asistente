@echo off
title Asistente Virtual Local
echo Verificando el servidor llama.cpp...
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo El servidor no esta corriendo. Abriendo una ventana para iniciarlo...
    start "" "%~dp0iniciar_servidor.bat"
    echo Esperando a que el servidor este listo...
    powershell -NoProfile -Command "$d=(Get-Date).AddSeconds(90); do { if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) { exit 0 }; Start-Sleep -Seconds 2 } while ((Get-Date) -lt $d); exit 1"
    if errorlevel 1 (
        echo ERROR: No se pudo iniciar el servidor a tiempo.
        pause
        exit /b 1
    )
)
echo Servidor listo. Iniciando el asistente...
cd /d "%~dp0"
set PYTHON="%~dp0venv\Scripts\python.exe"
if not exist %PYTHON% (
    echo ERROR: No se encontro el entorno virtual.
    pause
    exit /b 1
)
start "" %PYTHON% "%~dp0interfaz.py"
