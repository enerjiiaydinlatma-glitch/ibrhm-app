@echo off
title Aura Voice Mesh - Cloudflare Tunnel
REM Hizli tunel: hesap/domain gerekmez, rastgele bir *.trycloudflare.com verir.
REM Cikan "https://....trycloudflare.com" adresini Railway'de AURA_VOICE_URL yap.
REM
REM Ilk kez: cloudflared'i kur ->  winget install --id Cloudflare.cloudflared
REM
REM Kalici adres istersen (production): once "cloudflared tunnel login" +
REM named tunnel + kendi domainin (bkz. SETUP.md).

where cloudflared >nul 2>nul
if errorlevel 1 (
  echo cloudflared bulunamadi. Once kur:
  echo     winget install --id Cloudflare.cloudflared
  pause
  exit /b 1
)

echo Tunel aciliyor (voice service :8123 -^> internet)...
cloudflared tunnel --url http://localhost:8123
pause
