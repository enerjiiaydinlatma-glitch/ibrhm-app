@echo off
REM Aura Voice Mesh - GUNLUK baslatma. Iki pencere acar:
REM  1) baslat.bat        -> Chatterbox TTS servisi (:8123), cokerse yeniden basla
REM  2) tunel_kalici.bat  -> quick tunnel + Railway AURA_VOICE_URL otomatik senkron
REM Bilgisayar acik kaldigi surece Aura kendi sesiyle konusur. Adres degisse bile
REM Railway kendini gunceller - elle mudahale yok.
REM (Ilk kez: sync_secrets.example.txt -> sync_secrets.txt kopyalayip doldur.)
cd /d "%~dp0"

start "Aura Voice - TTS"   cmd /c baslat.bat
start "Aura Voice - Tunel" cmd /c tunel_kalici.bat

echo Iki pencere acildi. Kapatmak icin ikisini de kapat.
timeout /t 4 >nul
