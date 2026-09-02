@echo off
title Aura Voice Mesh - TTS
cd /d "%~dp0"

REM Bu anahtar Railway'deki AURA_VOICE_KEY ile AYNI olmali (SETUP.md).
if "%AURA_VOICE_KEY%"=="" set AURA_VOICE_KEY=bhpkaVp9HGIYl7ufF5mTCT4m-huFLYWsE7C3ex4dl4Q

set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python

:loop
echo [%date% %time%] Aura Voice Mesh baslatiliyor (model ~20sn yuklenir)...
"%PY%" server.py
echo [%date% %time%] Servis durdu. 5 sn sonra tekrar... (kapatmak icin pencereyi kapat)
timeout /t 5 >nul
goto loop
