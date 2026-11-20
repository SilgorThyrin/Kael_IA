@echo off
title Kael - Inicializador Completo
color 0A
echo ==========================================
echo   INICIANDO SISTEMA KAEL
echo ==========================================
echo.

:: 1. Inicia o Ollama em segundo plano (se ja estiver rodando, ignora)
echo [1/3] Verificando Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [+] Ollama ja esta em execucao.
) else (
    echo [+] Iniciando Ollama em segundo plano...
    start "" /B "C:\PortableAI\Ollama\ollama.exe" serve
    timeout /t 3 /nobreak >nul
)

:: 2. Inicia o Servidor API do Kael (em uma nova janela invisivel ou minimizada)
echo [2/3] Iniciando Servidor API do Kael...
start "Kael API Server" /MIN cmd /c "cd /d C:\PortableAI\kael && ..\python\python.exe api_server.py"
timeout /t 2 /nobreak >nul

:: 3. Abre a Interface no Navegador
echo [3/3] Abrindo Interface do Kael...
start "" "C:\PortableAI\kael\chat.html"

echo.
echo ==========================================
echo   KAEL INICIADO COM SUCESSO!
echo   (Nao feche a janela preta do "Kael API Server")
echo ==========================================
timeout /t 5