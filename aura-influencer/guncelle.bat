@echo off
chcp 65001 >nul
echo Aura guncelleme basliyor...
cd /d C:\AuraProject\aura_yeni
git fetch origin claude/dreamy-curie-t7jckk
git checkout --detach origin/claude/dreamy-curie-t7jckk
git log --oneline -1
robocopy "C:\AuraProject\aura_yeni\aura-influencer" "C:\AuraProject\ibrhm_app\aura-influencer" /E /NFL /NDL /NJH /XF guncelle.bat drafts.json day_status.json tiktok_meta.json conversation.json ai_usage.json snapshots.json token.json token_analytics.json client_secret.json access_token.txt code_pin.txt tiktok_client.json tiktok_token.json trends_cache.json pinned_comments.json video_tags.json experiments.json actions.json /XD _backups output uploads _video_work reports
echo.
echo TAMAM. Simdi: paneli yeniden baslat (Kod sekmesi) - Gelismis - Hazir Paketleri Yukle.
pause
