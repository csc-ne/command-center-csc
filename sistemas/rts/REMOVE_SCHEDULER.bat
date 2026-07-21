@echo off
chcp 65001 > nul
cd /d "%~dp0"
title RTS - Removendo Agendamento

echo.
echo  ================================================================
echo   RTS - Removendo Agendamento Automatico
echo  ================================================================
echo.

echo  Removendo tarefa "RTS - Iniciar"...
schtasks /delete /tn "RTS - Iniciar" /f > nul 2>&1
if %errorlevel% equ 0 (echo  OK) else (echo  Tarefa nao encontrada ou ja removida.)

echo  Removendo tarefa "RTS - Encerrar"...
schtasks /delete /tn "RTS - Encerrar" /f > nul 2>&1
if %errorlevel% equ 0 (echo  OK) else (echo  Tarefa nao encontrada ou ja removida.)

echo.
echo  Agendamento removido. O RTS nao sera mais iniciado automaticamente.
echo.
pause
