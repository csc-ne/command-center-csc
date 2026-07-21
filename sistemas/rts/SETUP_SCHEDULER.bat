@echo off
chcp 65001 > nul
cd /d "%~dp0"
title RTS - Configurando Agendamento

echo.
echo  ================================================================
echo   RTS - Configurando Agendamento Automatico
echo   Segunda a Sexta: 07:00 (iniciar) / 17:50 (encerrar)
echo  ================================================================
echo.

:: Obtém o diretório onde este bat está localizado
set "RTS_DIR=%~dp0"
:: Remove a barra final
if "%RTS_DIR:~-1%"=="\" set "RTS_DIR=%RTS_DIR:~0,-1%"

echo  Diretorio do RTS: %RTS_DIR%
echo.

:: ----------------------------------------------------------------
:: TAREFA 1 — Iniciar RTS de segunda a sexta às 07:00
:: ----------------------------------------------------------------
echo  [1/2] Criando tarefa de INICIO (Seg-Sex 07:00)...

schtasks /create ^
    /tn "RTS - Iniciar" ^
    /tr "\"%RTS_DIR%\START.bat\"" ^
    /sc weekly ^
    /d MON,TUE,WED,THU,FRI ^
    /st 07:00 ^
    /sd 01/01/2025 ^
    /ru "%USERNAME%" ^
    /rl HIGHEST ^
    /f > nul 2>&1

if %errorlevel% equ 0 (
    echo  OK - Tarefa "RTS - Iniciar" criada com sucesso.
) else (
    echo  ERRO ao criar tarefa de inicio. Tente executar como Administrador.
)

:: ----------------------------------------------------------------
:: TAREFA 2 — Encerrar RTS de segunda a sexta às 17:50
:: ----------------------------------------------------------------
echo  [2/2] Criando tarefa de ENCERRAMENTO (Seg-Sex 17:50)...

schtasks /create ^
    /tn "RTS - Encerrar" ^
    /tr "\"%RTS_DIR%\STOP.bat\"" ^
    /sc weekly ^
    /d MON,TUE,WED,THU,FRI ^
    /st 17:50 ^
    /sd 01/01/2025 ^
    /ru "%USERNAME%" ^
    /rl HIGHEST ^
    /f > nul 2>&1

if %errorlevel% equ 0 (
    echo  OK - Tarefa "RTS - Encerrar" criada com sucesso.
) else (
    echo  ERRO ao criar tarefa de encerramento. Tente executar como Administrador.
)

echo.
echo  ================================================================
echo   Agendamento configurado!
echo.
echo   Para verificar: abra o Agendador de Tarefas do Windows
echo   e procure por "RTS - Iniciar" e "RTS - Encerrar".
echo.
echo   Para remover o agendamento, execute REMOVE_SCHEDULER.bat
echo  ================================================================
echo.
pause
