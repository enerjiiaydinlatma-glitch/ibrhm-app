@echo off
cd /d "%~dp0.."
call ..\auro-backend\venv\Scripts\activate.bat
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8765"
python -m uvicorn danisma.server:app --host 127.0.0.1 --port 8765
