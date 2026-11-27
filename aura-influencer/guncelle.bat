@echo off
chcp 65001 >nul
rem Kendini TEMP'e kopyalayip oradan calisir: boylece robocopy bu dosyanin KENDISINI de guncelleyebilir.
if /i not "%~dp0"=="%TEMP%\" (
  copy /Y "%~f0" "%TEMP%\aura_guncelle_run.bat" >nul
  call "%TEMP%\aura_guncelle_run.bat"
  exit /b
)
echo Aura guncelleme basliyor...
cd /d C:\AuraProject\aura_yeni
git fetch origin claude/dreamy-curie-t7jckk
git checkout --detach origin/claude/dreamy-curie-t7jckk
git log --oneline -1
robocopy "C:\AuraProject\aura_yeni\aura-influencer" "C:\AuraProject\ibrhm_app\aura-influencer" /E /NFL /NDL /NJH /XF drafts.json day_status.json tiktok_meta.json conversation.json ai_usage.json snapshots.json token.json token_analytics.json client_secret.json access_token.txt code_pin.txt tiktok_client.json tiktok_token.json trends_cache.json pinned_comments.json video_tags.json experiments.json actions.json /XD _backups output uploads _video_work reports
echo.
echo Panel yeniden baslatiliyor...
where python >nul 2>nul
if errorlevel 1 (
  echo Python bulunamadi - paneli elle yeniden baslat.
) else (
  python "C:\AuraProject\ibrhm_app\aura-influencer\_studio\safe_restart.py" 8795
)
echo.
echo Panel penceresi aciliyor...
start "" "C:\AuraProject\ibrhm_app\aura-influencer\AuraCommandCenter.bat"
echo TAMAM.
pause
