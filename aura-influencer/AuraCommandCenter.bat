@echo off
title Aura Command Center
cd /d "%~dp0"
echo Aura Command Center baslatiliyor...
netstat -ano | findstr ":8795" | findstr "LISTENING" >nul
if %errorlevel%==0 goto ALREADY_RUNNING
echo Sunucu baslatiliyor (bu pencereyi ACIK birak; uygulama penceresi kendiliginden acilir)...
python aura_studio.py
goto END
:ALREADY_RUNNING
echo Sunucu zaten calisiyor, uygulama penceresi aciliyor...
python -c "import aura_studio;aura_studio._open_app_window('http://127.0.0.1:8795/')"
:END
