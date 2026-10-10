@echo off
rem Windows acilisinda paneli SESSIZCE (pencere acmadan) baslatir; Voice Mesh dahil her sey panel tarafindan baslatilir.
cd /d "%~dp0"
netstat -ano | findstr ":8795" | findstr "LISTENING" >nul
if %errorlevel%==0 goto END
set AURA_NO_OPEN=1
start "" /min pythonw aura_studio.py
:END
