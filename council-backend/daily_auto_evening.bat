@echo off
REM ============================================================
REM  AURA MOTORU - AKSAM SLOTU (GUNDE 2. SHORT)
REM  11 Eylul 2026: kullanici karari - gunde 2 Short. Bu, sabah
REM  daily_auto.bat'in AYNI GUNDE ikinci calistirilmasidir - farkli
REM  saatte ikinci bir Windows Gorev Zamanlayicisi tetikleyicisi
REM  bunu cagirir (kurulum: asagidaki NOT'a bak).
REM
REM  Sabah slotundan farki:
REM   - Format rotasyonu YOK - hep kazanan tekil-konu kalibi (leaderboard/
REM     hottake/evergreen GUNDE 1 kez yeter, sabah slotunda kaliyor)
REM   - aura_engine.py'daki gunde-bir-kez kilidi optimize/reference/arc'i
REM     bu ikinci calistirmada otomatik atlar (ayni gun icin flag dosyasi)
REM   - Tekrar-konusu guvenlik agi zaten var: _recent_decisions() BUGUNKU
REM     plan.json'i da okur, Aura ayni hikayeyi 2. kez secmez
REM
REM  NOT (kurulum, bir kerelik - Claude Windows Gorev Zamanlayicisini
REM  degistiremiyor, bunu SEN ya da mevcut SignCouncilDaily'yi kuran kim
REM  yaptiysa ekler):
REM    schtasks /create /tn "SignCouncilEvening" /tr "\"%~dp0daily_auto_evening.bat\"" /sc daily /st 21:00
REM  (saat: sabah 18:00 ise aksam 21:00 gibi ~3 saat sonra iyi bir aralik)
REM ============================================================
setlocal
cd /d "%~dp0"
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python
set LOG=%~dp0_daily_auto_%date:~-4,4%%date:~-7,2%%date:~-10,2%.log

echo [%date% %time%] daily_auto_evening basladi >> "%LOG%"

REM BUG (13 Eyl 2026 kesfedildi + YANLIS duzeltilmis, bkz. daily_auto.bat):
REM AURA_VOICE_URL'i asagidaki "sunucuyu baslat" bloguna koymustum, ama o
REM blok SADECE sunucu SAGLIKSIZSA calisiyor - sunucu zaten ayaktaysa
REM (sabah slotundan kalma, cogu gun budur) "goto ready" ile o blok TAMAMEN
REM atlaniyor ve URL/KEY hic set edilmiyordu - istemci hala eski 8123
REM varsayilanina baglanip 401 aliyordu. Simdi KOSULSUZ, health-check'ten
REM ONCE set ediliyor - sunucuyu biz mi baslattik, zaten mi ayaktaydi fark etmez.
set AURA_VOICE_URL=http://127.0.0.1:8124
set AURA_VOICE_KEY=sc-local-8x2Kq9mF4vRw6-council-voice

REM --- ses sunucusu zaten saglikliysa dokunma ---
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

REM 13 Eyl 2026: kullanici karari - haber nisi tek basina yeterli cekim
REM saglamiyordu (24 abone, haftalarca gunluk yayindan sonra). 3 BAGIMSIZ
REM AI danismanina (Anthropic/OpenAI/Groq, ayri ayri) ayni soru soruldu,
REM ucu de "izleyici ikilemini konseye karar verdirt" onerdi. Aksam slotu
REM artik bu format - sabah slotu (daily_auto.bat) mevcut haber/rotasyon
REM formatinda degismeden kaliyor, boylece hicbir sey silinmiyor.
echo [%date% %time%] aksam slotu: Konsey Karar Veriyor (izleyici ikilemi) >> "%LOG%"
"%PY%" -u daily_guard.py --short-upload --public --council-decides >> "%LOG%" 2>&1

echo [%date% %time%] daily_auto_evening bitti >> "%LOG%"
endlocal
