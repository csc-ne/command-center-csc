@echo off
chcp 65001 > nul
cd /d "%~dp0"
title RTS - Real Time Support

echo.
echo  ========================================================
echo   RTS - Real Time Support ^| Veneza Equipamentos
echo  ========================================================
echo.

REM ── Garante que a pasta de logs existe ────────────────────
if not exist "logs\output" mkdir logs\output

REM ── Verifica se o ambiente virtual existe ──────────────────
if not exist "venv\Scripts\activate.bat" (
    echo  [ERRO] Ambiente virtual nao encontrado.
    echo  Execute: python -m venv venv  e instale as dependencias.
    echo.
    pause
    exit /b 1
)

REM ── Verifica se node_modules existe ────────────────────────
if not exist "node_modules" (
    echo  [AVISO] node_modules nao encontrado. Instalando dependencias Node...
    call npm install
    echo.
)

echo  [1/3] Ativando ambiente virtual Python...
call venv\Scripts\activate

echo  [2/3] Iniciando servidor de autenticacao John Deere (porta 5000)...
start "RTS Auth - John Deere" /min cmd /c "call venv\Scripts\activate && python interface\johndeere\JohnDeereAPI.py > logs\output\auth_server.log 2>&1"

echo  [3/3] Aguardando servidor de autenticacao inicializar...
timeout /t 3 /nobreak > nul

echo.
echo  Iniciando servidor do Dashboard (porta 8080)...
echo  ^(log em logs\output\dashboard.log^)
start "RTS Dashboard" /min cmd /c "node connection\server.js > logs\output\dashboard.log 2>&1"

echo  Aguardando servidor do Dashboard inicializar...
timeout /t 6 /nobreak > nul

echo.
echo  ========================================================
echo   Iniciando interface RTS...
echo  ========================================================
echo.

python interface\app.py

echo.
echo  RTS encerrado.
pause
