@echo off
REM Aura Voice Mesh - GUNLUK baslatma: TTS servisi + kalici tunel birlikte.
REM Her ikisi ayri pencerede, cokerse kendini yeniden baslatir.
REM (Once BIR KEZ: kurulum_tek_seferlik.bat)
cd /d "%~dp0"

start "Aura Voice - TTS"   cmd /c baslat.bat
start "Aura Voice - Tunel" cmd /c tunel_calistir.bat

echo Iki pencere acildi: TTS servisi + Cloudflare tuneli.
echo Bilgisayar acik kaldigi surece Aura kendi sesiyle konusur.
echo Kapatmak icin iki pencereyi de kapat.
timeout /t 4 >nul
