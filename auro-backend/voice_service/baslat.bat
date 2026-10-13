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
REM IKINCI KOPYA KORUMASI (8 Eki 2026): :8123 zaten bir Aura Voice sunucusu tarafindan sunuluyorsa
REM (ornegin uygulama pythonw ile acmis) bir kopya DAHA baslatma. Eskiden bu dongu her ~35 sn'de modeli
REM (5-6 GB RAM) yukleyip port dolu oldugu icin cokuyor ve PC'yi kastiriyordu. Simdi nobetci gibi bekler:
REM sunucu dusunce otomatik yeniden baslatir, calisirken dokunmaz.
curl -s -o nul -m 3 http://127.0.0.1:8123/health
if not errorlevel 1 (
  echo [%date% %time%] :8123 zaten calisiyor - ikinci kopya baslatilmiyor. 60 sn sonra tekrar kontrol...
  timeout /t 60 >nul
  goto loop
)
echo [%date% %time%] Aura Voice Mesh baslatiliyor (model ~20sn yuklenir)...
"%PY%" server.py
echo [%date% %time%] Servis durdu. 5 sn sonra tekrar... (kapatmak icin pencereyi kapat)
timeout /t 5 >nul
goto loop
