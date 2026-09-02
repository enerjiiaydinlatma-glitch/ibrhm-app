@echo off
title Aura Voice Mesh - Tunel (kalici)
cd /d "%~dp0"
set CF="C:\Program Files (x86)\cloudflared\cloudflared.exe"
if not exist %CF% ( echo cloudflared yok. & pause & exit /b 1 )

:loop
echo [%date% %time%] Tunel baglaniyor (aura-ses)...
%CF% tunnel --config config.yml run aura-ses
echo [%date% %time%] Tunel koptu. 5 sn sonra tekrar...
timeout /t 5 >nul
goto loop
