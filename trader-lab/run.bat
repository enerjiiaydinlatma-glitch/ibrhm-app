@echo off
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
if not exist .venv\Scripts\python.exe (
  %PY% -m venv .venv || (echo Python 3.11+ kurulu degil: https://www.python.org/downloads/ & exit /b 1)
)
.venv\Scripts\python.exe -m pip install -q -r requirements.txt || exit /b 1
echo.
echo Panel: http://127.0.0.1:8000   (kapatmak icin Ctrl+C)
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn trader.api:get_app --factory --host 127.0.0.1 --port 8000
