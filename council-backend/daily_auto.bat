@echo off
REM ============================================================
REM  AURA MOTORU - TAM OTONOM GUNLUK CALISTIRICI
REM  Windows Gorev Zamanlayicisi bunu tetikler - kimse tiklamaz.
REM  1) Ses sunucusunu (varsa eskilerini kapatip) baslatir, saglikli
REM     olana kadar bekler (~30sn)
REM  2) aura_engine.py --short-upload --public calistirir
REM  3) Cikti gunluk log dosyasina yazilir (kimse izlemiyor olabilir)
REM ============================================================
setlocal
cd /d "%~dp0"
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python
set LOG=%~dp0_daily_auto_%date:~-4,4%%date:~-7,2%%date:~-10,2%.log

echo [%date% %time%] daily_auto basladi >> "%LOG%"

REM BUG (13 Eyl 2026 kesfedildi + ilk duzeltme YANLIS yerdeydi - bkz.
REM daily_auto_evening.bat): AURA_VOICE_URL'i "sunucuyu baslat" blogunun
REM ICINE koymustum, ama o blok SADECE sunucu SAGLIKSIZSA calisiyor -
REM sunucu zaten ayaktaysa (aksam slotundan kalma, cogu gun budur) o blok
REM TAMAMEN atlaniyor, URL hic set edilmiyor, istemci eski 8123 varsayilanina
REM baglanip 401/refused aliyordu. Simdi KOSULSUZ, health-check'ten ONCE.
set AURA_VOICE_URL=http://127.0.0.1:8124
set AURA_VOICE_KEY=sc-local-8x2Kq9mF4vRw6-council-voice

REM --- 1) zaten saglikliysa DOKUNMA (gunde 2 Short - 2. slot 1.'nin sicak
REM     sunucusunu kesip yeniden 30-60sn beklemesin); degilse eskisini kapat+baslat ---
curl -s -m 3 http://127.0.0.1:8124/health | find "model_loaded"":true" >nul 2>&1
if %errorlevel%==0 (
  echo [%date% %time%] ses sunucusu zaten saglikli - atlaniyor >> "%LOG%"
  goto ready
)
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { $_.CommandLine -like '*voice_service*server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >> "%LOG%" 2>&1
timeout /t 2 >nul

set AURA_VOICE_PORT=8124
set AURA_VOICE_VOICES_DIR=%~dp0reference_voices
set AURA_VOICE_DEFAULT_SPEAKER=aura
start "Sign Council Ses (auto)" /min "%PY%" "%~dp0..\auro-backend\voice_service\server.py"

REM --- 2) saglikli olana kadar bekle (maks ~60sn) ---
set /a tries=0
:waitloop
curl -s -m 3 http://127.0.0.1:8124/health | find "model_loaded"":true" >nul 2>&1
if %errorlevel%==0 goto ready
set /a tries+=1
if %tries% GEQ 20 goto ready
timeout /t 3 >nul
goto waitloop
:ready
echo [%date% %time%] ses sunucusu hazir (deneme %tries%) >> "%LOG%"

REM --- 3) Aura motorunu calistir ---
REM Format rotasyonu (Aura 5 Eylul kanal analizi + wetubemevlana slayt 4 +
REM 11 Eylul Consumer Exposed analizi):
REM   Pazar     -> --leaderboard  (siralama gorseli + "tahmin et, kaydet")
REM   Sali      -> --verdict      (N flagged, M clean dengeli liste)
REM   Carsamba  -> --hottake      (son bolumun en keskin 45sn'si)
REM   Cumartesi -> --evergreen    (habere bagli olmayan zamansiz mekanizma)
REM   diger 3 gun-> kazanan tekil-konu kalibi
set FMTFLAG=
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).DayOfWeek"') do set DOW=%%d
if /I "%DOW%"=="Sunday" set FMTFLAG=--leaderboard
if /I "%DOW%"=="Tuesday" set FMTFLAG=--verdict
if /I "%DOW%"=="Wednesday" set FMTFLAG=--hottake
if /I "%DOW%"=="Saturday" set FMTFLAG=--evergreen
echo [%date% %time%] format: %DOW% -> "%FMTFLAG%" >> "%LOG%"
"%PY%" -u daily_guard.py --short-upload --public %FMTFLAG% >> "%LOG%" 2>&1

echo [%date% %time%] daily_auto bitti >> "%LOG%"
endlocal
