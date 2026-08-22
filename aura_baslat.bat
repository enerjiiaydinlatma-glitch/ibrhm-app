@echo off
title Aura Baslatiliyor...
echo Aura backend baslatiliyor...

if not exist "C:\AuraProject\ibrhm_app\auro-backend\venv\Scripts\activate.bat" (
    echo HATA: venv bulunamadi - C:\AuraProject\ibrhm_app\auro-backend\venv
    pause
    exit /b 1
)

start "Aura Backend" cmd /k "cd /d C:\AuraProject\ibrhm_app\auro-backend && venv\Scripts\activate && uvicorn main:app --reload"

timeout /t 5 /nobreak >nul

echo Aura arayuzu aciliyor...
cd /d C:\AuraProject\ibrhm_app
start "Aura Flutter" cmd /k "flutter run -d chrome"
