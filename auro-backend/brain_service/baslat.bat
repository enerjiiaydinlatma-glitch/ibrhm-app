@echo off
title Aura Brain Mesh
cd /d "%~dp0"

REM Ayarlar sync_secrets.txt'ten okunur (GIT'E GIRMEZ). En az AURA_BRAIN_KEY
REM gerekli - Railway'deki AURA_BRAIN_KEY ile AYNI olmali.
if exist "sync_secrets.txt" (
  for /f "usebackq tokens=1,* delims==" %%A in ("sync_secrets.txt") do (
    if /i "%%A"=="AURA_BRAIN_KEY" if "%AURA_BRAIN_KEY%"=="" set AURA_BRAIN_KEY=%%B
    if /i "%%A"=="BRAIN_BACKEND_MODEL" if "%BRAIN_BACKEND_MODEL%"=="" set BRAIN_BACKEND_MODEL=%%B
    if /i "%%A"=="BRAIN_BACKEND_URL" if "%BRAIN_BACKEND_URL%"=="" set BRAIN_BACKEND_URL=%%B
  )
)
if "%AURA_BRAIN_KEY%"=="" (
  echo HATA: AURA_BRAIN_KEY yok. sync_secrets.example.txt -^> sync_secrets.txt kopyalayip doldur.
  pause
  exit /b 1
)
if "%BRAIN_BACKEND_MODEL%"=="" set BRAIN_BACKEND_MODEL=qwen2.5:7b-instruct
if "%BRAIN_BACKEND_URL%"=="" set BRAIN_BACKEND_URL=http://localhost:11434

REM Ollama calisyor mu? (ayri process - "ollama serve" ile baslatilir)
curl -s -o nul -m 3 %BRAIN_BACKEND_URL%/api/tags
if errorlevel 1 (
  echo UYARI: %BRAIN_BACKEND_URL% yanit vermiyor. Once "ollama serve" calistir
  echo ve "ollama pull %BRAIN_BACKEND_MODEL%" ile modeli cek.
  echo Yine de baslatiliyor - backend gelince otomatik calisir.
)

set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python

:loop
echo [%date% %time%] Aura Brain Mesh baslatiliyor (:8130, backend %BRAIN_BACKEND_MODEL%)...
"%PY%" server.py
echo [%date% %time%] Servis durdu. 5 sn sonra tekrar... (kapatmak icin pencereyi kapat)
timeout /t 5 >nul
goto loop
