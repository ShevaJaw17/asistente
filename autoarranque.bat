@echo off
rem ============================================================
rem  Autoarranque de Robin (llama.cpp + servidor web + programador)
rem  Lanzado por la tarea de Windows al iniciar sesión.
rem ============================================================
cd /d "%~dp0"
set PYBIN="%~dp0venv\Scripts\python.exe"

rem --- 1) Servidor llama.cpp (puerto 8080), si no está ya corriendo ---
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    set SRV=%~dp0llama_cpp\bin\srv.exe
    if not exist %SRV% (
        powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0recuperar_srv.ps1" >nul 2>&1
    )
    if exist %SRV% (
        start "LambdaServer-llama" /min %SRV% --model %~dp0llama_cpp\models\qwen2.5-7b-Q4_K_M.gguf --host 127.0.0.1 --port 8080 -ngl 99 -c 8192
    )
)

rem --- 2) Servidor web de chat/panel + programador (puerto 8000), si no corre ya ---
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    start "RobinWeb" /min %PYBIN% "%~dp0servidor_web.py"
)

exit /b 0
