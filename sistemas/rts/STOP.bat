@echo off
chcp 65001 > nul
cd /d "%~dp0"
title RTS - Encerrando...
echo.
echo  ================================================================
echo   RTS - Real Time Support - ENCERRANDO
echo  ================================================================
echo.
echo  Encerrando processos...

:: Encerra o servidor Node.js (Dashboard - porta 8080)
echo  [1/3] Encerrando servidor Dashboard (Node.js)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F > nul 2>&1
)

:: Encerra o servidor Flask (Auth John Deere - porta 5000)
echo  [2/3] Encerrando servidor Auth (Flask)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F > nul 2>&1
)

:: Encerra a interface PySide6 (app.py)
echo  [3/3] Encerrando interface RTS...
taskkill /IM python.exe /F > nul 2>&1
taskkill /IM pythonw.exe /F > nul 2>&1

echo.
echo  RTS encerrado com sucesso.
echo  Pressione qualquer tecla para fechar...
pause > nul
