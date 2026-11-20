@echo off
chcp 65001 >nul
title INICIANDO KAEL (Modo Diagnóstico)
set "TARGET_DIR=C:\PortableAI"
cd /d "%TARGET_DIR%"

echo [1/4] Limpando processos antigos para evitar conflitos...
taskkill /F /IM ollama.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/4] Subindo o motor Ollama...
start "Ollama Server" "%TARGET_DIR%\Ollama\ollama.exe" serve
timeout /t 4 /nobreak >nul

echo [3/4] Iniciando o Cerebro do Kael (Python)...
:: Usamos python.exe (sem o 'w') propositalmente para ver QUALQUER erro na tela
start "Kael Core (NAO FECHE ESTA JANELA)" "%TARGET_DIR%\python\python.exe" kael_core.py
timeout /t 5 /nobreak >nul

echo [4/4] Abrindo o Chat no Navegador...
:: Forçamos a abertura na URL do servidor local, NAO no arquivo HTML solto
start "" "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" "http://127.0.0.1:8000"

echo.
echo ===================================================
echo KAEL INICIADO!
echo Verifique se estas 2 janelas pretas estão abertas:
echo 1. "Ollama Server"
echo 2. "Kael Core (NAO FECHE ESTA JANELA)"
echo ===================================================
pause