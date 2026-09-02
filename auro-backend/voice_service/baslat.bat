@echo off
title Aura Voice Mesh - TTS
cd /d "%~dp0"

REM --- Gizli anahtar: auro-backend'deki AURA_VOICE_KEY ile AYNI olmali ---
if "%AURA_VOICE_KEY%"=="" set AURA_VOICE_KEY=DEGISTIR-uzun-gizli-bir-anahtar

REM Global Python 3.12 (chatterbox + torch cu118 burada kurulu)
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python

echo Aura Voice Mesh baslatiliyor (model ilk seferde ~20sn yuklenir)...
"%PY%" server.py

pause
