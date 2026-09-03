@echo off
title Aura Brain - Tunel
cd /d "%~dp0"
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python
:loop
"%PY%" tunel_sync.py
echo [%date% %time%] tunel_sync durdu. 5 sn sonra tekrar...
timeout /t 5 >nul
goto loop
