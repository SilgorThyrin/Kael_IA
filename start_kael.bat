@echo off
title Kael - Inicializador Principal
color 0A
echo ==========================================
echo   INICIANDO KAEL (Ambiente Portatil)
echo ==========================================
echo.

:: 1. Iniciar Ollama em segundo plano
echo [1/3] Verificando Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [+] Ollama ja esta rodando.
) else (
    echo [+] Iniciando servico Ollama...
    start "" /B "C:\PortableAI\Ollama\ollama.exe" serve
    timeout /t 3 /nobreak >nul
)

:: 2. Iniciar o Servidor API do Kael (em uma janela separada minimizada)
echo [2/3] Iniciando Servidor API do Kael...
:: O /MIN deixa a janela minimizada. O /k mantém a janela aberta para mostrar logs se precisar.
start "Kael API Server" /MIN cmd /k "cd /d C:\PortableAI\kael && ..\python\python.exe api_server.py"
timeout /t 4 /nobreak >nul

:: 3. Abrir a Interface no Navegador
echo [3/3] Abrindo interface do Kael no navegador...
start "" "C:\PortableAI\kael\ui\chat.html"

echo.
echo ==========================================
echo   KAEL INICIADO COM SUCESSO!
echo   (A janela "Kael API Server" fica rodando em segundo plano)
echo ==========================================
timeout /t 5
exit