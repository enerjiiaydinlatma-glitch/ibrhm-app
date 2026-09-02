@echo off
title Aura Voice Mesh - Tunel + Railway otomatik senkron
cd /d "%~dp0"
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python

REM quick tunnel'i baslatir, adresi Railway'de AURA_VOICE_URL'e otomatik yazar,
REM tunnel koparsa yeniden baslatip tekrar senkronlar. Kapatmak icin pencereyi kapat.
"%PY%" tunel_sync.py

echo.
echo tunel_sync durdu. Pencereyi kapatabilirsin.
pause
