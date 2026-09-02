@echo off
title Aura Voice Mesh - TTS
cd /d "%~dp0"

REM AURA_VOICE_KEY sync_secrets.txt'ten okunur (GIT'E GIRMEZ) - Railway'deki
REM AURA_VOICE_KEY ile AYNI olmali (bkz. sync_secrets.example.txt / SETUP.md).
if "%AURA_VOICE_KEY%"=="" (
  for /f "usebackq tokens=1,* delims==" %%A in ("sync_secrets.txt") do (
    if /i "%%A"=="AURA_VOICE_KEY" set AURA_VOICE_KEY=%%B
  )
)
if "%AURA_VOICE_KEY%"=="" (
  echo HATA: AURA_VOICE_KEY yok. sync_secrets.example.txt -^> sync_secrets.txt kopyalayip doldur.
  pause
  exit /b 1
)

set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python

:loop
echo [%date% %time%] Aura Voice Mesh baslatiliyor (model ~20sn yuklenir)...
"%PY%" server.py
echo [%date% %time%] Servis durdu. 5 sn sonra tekrar... (kapatmak icin pencereyi kapat)
timeout /t 5 >nul
goto loop
