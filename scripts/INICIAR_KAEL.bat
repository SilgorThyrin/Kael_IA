@echo off
chcp 65001 >nul
title Iniciando Kael v5.3 (Núcleo com Roblox)
set "TARGET_DIR=C:\PortableAI"
cd /d "%TARGET_DIR%"

:: 1. Garantir que o Ollama esteja rodando limpo
echo [1/3] Preparando motor Ollama...
taskkill /F /IM ollama.exe >nul 2>&1
start "" "%TARGET_DIR%\Ollama\ollama.exe" serve
timeout /t 4 /nobreak >nul

:: 2. INICIAR O SERVIDOR PYTHON (BLINDADO: A tela NAO vai mais fechar sozinha)
echo [2/3] Iniciando o Cerrebro do Kael...
:: O "cmd /k" força a janela a ficar aberta mesmo se der erro no Python
start "Kael Core Server" cmd /k "title Kael Core Server && %TARGET_DIR%\python\python.exe kael_core.py"
timeout /t 3 /nobreak >nul

:: 3. Abrir o Companion (Orbe) e o Chat no Navegador
echo [3/3] Ativando Companion e abrindo Chat...
start "" "%TARGET_DIR%\python\pythonw.exe" kael_companion.py
timeout /t 2 /nobreak >nul
start "" "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" "http://127.0.0.1:8000"

echo.
echo ===================================================
echo KAEL INICIADO!
echo A janela preta do "Kael Core Server" agora NAO FECHA SOZINHA.
echo ===================================================
pause