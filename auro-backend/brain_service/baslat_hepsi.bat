@echo off
REM Aura Brain Mesh - hepsini baslat (2 pencere).
REM ONCE ayri bir pencerede: ollama serve   +   ollama pull qwen2.5:7b-instruct
cd /d "%~dp0"
start "Aura Brain - LLM" cmd /c baslat.bat
start "Aura Brain - Tunel" cmd /c tunel_kalici.bat
