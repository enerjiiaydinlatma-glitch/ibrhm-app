@echo off
title Aura Voice Mesh - TEK SEFERLIK kurulum
setlocal
set CF="C:\Program Files (x86)\cloudflared\cloudflared.exe"
if not exist %CF% (
  echo cloudflared bulunamadi. Kur:  winget install --id Cloudflare.cloudflared
  pause & exit /b 1
)

echo ============================================================
echo  Aura Voice Mesh - kalici tunel kurulumu (bir kez yapilir)
echo ============================================================
echo.
echo 1) Simdi tarayici acilacak - Cloudflare hesabinla giris yap ve
echo    kullanmak istedigin domaini SEC ("Authorize").
echo.
pause
%CF% tunnel login
if errorlevel 1 ( echo Giris basarisiz. & pause & exit /b 1 )

echo.
echo 2) "aura-ses" adli tunel olusturuluyor...
%CF% tunnel create aura-ses

echo.
echo 3) Simdi bir ALT ALAN adi sec (orn: ses.senindomainin.com) ve asagi yaz.
set /p SUB=Alt alan adi (tam, ornek ses.enerjiiaydinlatma.com):
%CF% tunnel route dns aura-ses %SUB%

echo.
echo ============================================================
echo  BITTI. Simdi:
echo   - config.yml icindeki "TUNNEL-ADI" yerine: aura-ses
echo   - Railway ^> auro-backend ^> Variables:
echo       AURA_VOICE_URL = https://%SUB%
echo       AURA_VOICE_KEY = (baslat.bat icindeki AURA_VOICE_KEY ile ayni)
echo   - Gunluk kullanim:  baslat_hepsi.bat
echo ============================================================
pause
