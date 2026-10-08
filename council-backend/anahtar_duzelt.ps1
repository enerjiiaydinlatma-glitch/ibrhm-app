# Ses anahtarini koddan cikarir, SADECE 3 dosyayi ekler, anahtar sizdirmadigini dogrular, commit + push yapar.
# Calistir (council-backend klasorunde):  powershell -ExecutionPolicy Bypass -File .\anahtar_duzelt.ps1
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
function Dur($m) { Write-Host "[HATA] $m" -ForegroundColor Red; Write-Host "Bu ekrani Claude'a yapistir."; exit 1 }
function Ok($m) { Write-Host "[OK] $m" -ForegroundColor Green }

$Py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
$dosyalar = @("make_topic_short.py", "daily_auto.bat", "daily_auto_evening.bat")
$beklenen = @("council-backend/make_topic_short.py", "council-backend/daily_auto.bat", "council-backend/daily_auto_evening.bat")

# 0) bekleyen anahtarli commit var mi?
$bekleyen = git log origin/claude/beautiful-archimedes-almi2e..HEAD --format=%s 2>&1
if ($bekleyen) { Dur "Henuz gonderilmemis yerel commit var: $bekleyen   -> once 'git reset --soft HEAD~1' ve 'git restore --staged make_topic_short.py' calistir." }
Ok "Bekleyen yerel commit yok"

# 1) anahtari koddan cikar
& $Py redact_voice_key.py @dosyalar
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) { Dur "redact_voice_key.py hata verdi." }
foreach ($f in $dosyalar) {
    if (Select-String -Path $f -Pattern "sc-local-" -Quiet) { Dur "$f icinde hala acik anahtar var." }
}
if (-not (Test-Path ".voice_key")) { Dur ".voice_key olusmadi." }
Ok "3 dosyada acik anahtar yok, .voice_key hazir"

# 2) sadece bu 3 dosyayi ekle
git add -- @dosyalar
$staged = @(git diff --cached --name-only)
$fark = Compare-Object ($staged | Sort-Object) ($beklenen | Sort-Object)
if ($fark) { git reset -q; Dur "Beklenmeyen dosya eklenmis: $($staged -join ', ')  (hepsi geri alindi)" }
Ok "Eklenenler tam olarak beklenen 3 dosya"

# 3) eklenen satirlarda anahtar var mi
$sizinti = git diff --cached -U0 | Select-String -Pattern '^\+[^+].*sc-local-'
if ($sizinti) { git reset -q; Dur "Eklenen satirlarda anahtar var, iptal edildi." }
Ok "Eklenen satirlarda anahtar yok"

# 4) commit + push
git commit -m "chore(council): make_topic_short ve bat dosyalari - ses anahtari .voice_key dosyasina tasindi"
if ($LASTEXITCODE -ne 0) { Dur "commit basarisiz." }
git push origin claude/beautiful-archimedes-almi2e
if ($LASTEXITCODE -ne 0) { Dur "push basarisiz (yukaridaki mesaja bak)." }
Ok "Gonderildi. Anahtar artik sadece .voice_key dosyasinda (bu bilgisayarda)."
