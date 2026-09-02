@echo off
title Servidor llama.cpp (Vulkan/GPU)
setlocal
set BIN="%~dp0llama_cpp\bin"
set MODELS="%~dp0llama_cpp\models"
set SRV=%BIN%\srv.exe

rem Asegurar que el ejecutable del servidor exista (el antivirus puede borrarlo)
if not exist %SRV% (
    echo Recuperando el ejecutable del servidor...
    powershell -NoProfile -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; $z=[System.IO.Compression.ZipFile]::OpenRead('%~dp0llama_cpp\llama.zip'); $e=$z.Entries | Where-Object { $_.Name -eq 'llama-server.exe' }; [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e, '%~dp0llama_cpp\bin\srv.exe', $true); $z.Dispose()"
)

echo Iniciando servidor llama.cpp con GPU (Vulkan)...
echo Puerta: http://127.0.0.1:8080
echo.
%SRV% --model %MODELS%\qwen2.5-3b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 8080 -ngl 99 -c 8192
echo.
echo El servidor se detuvo.
pause
