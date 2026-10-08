# Sign Council - GUNLUK ADIM ADIM CALISTIRICI (PowerShell)
# Kullanim (herhangi bir klasorden):
#   powershell -ExecutionPolicy Bypass -File C:\AuraProject\ibrhm_app\council-backend\gunluk.ps1
# Her adim kontrol eder, hata varsa DURUR ve ne yapilacagini soyler. Kopyala-yapistir yok.
# Video varsayilan olarak PRIVATE yuklenir; yayin sadece senin onayinla (YAYINLA yazarak).

param(
    [string]$Url = "",       # kaynak sayfa adresi (verilirse sorulmaz)
    [string]$Facts = "",     # grafikte gordugun sayilar (opsiyonel; ; ile ayir)
    [string]$Sec = "",       # kanit numaralari (ornek "1,3,6,8,17"); bos = onerilen ilk 6
    [switch]$Evet            # Enter bekleyen "devam?" sorularini otomatik gec
)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$Branch = "claude/beautiful-archimedes-almi2e"

function Adim($no, $baslik) { Write-Host ""; Write-Host "=== ADIM $no : $baslik ===" -ForegroundColor Cyan }
function Tamam($m) { Write-Host "  [OK] $m" -ForegroundColor Green }
function Uyari($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }
function Dur($m) { Write-Host "  [HATA] $m" -ForegroundColor Red; Write-Host "  Bu ekrani (veya son satirlari) Claude'a yapistir." ; exit 1 }
function Devam($m) { if ($Evet) { Write-Host "  (otomatik devam)"; return }; $x = Read-Host "  $m (Enter = devam, q = cik)"; if ($x -eq "q") { Write-Host "Cikildi."; exit 0 } }

# --- python yolu (bat dosyalariyla ayni) ---
$Py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

# ---------------------------------------------------------------- ADIM 1
Adim 1 "Klasor ve Python"
Tamam "Klasor: $PSScriptRoot"
try { $v = & $Py --version 2>&1; Tamam "Python: $v" } catch { Dur "Python calismiyor ($Py)." }
foreach ($f in @("aura_engine.py","daily_limit.py","claim_lint.py","manual_topic.py","explain_run.py","daily_check.py","publish_youtube.py","kaynak_cek.py","source_check.py")) {
    if (-not (Test-Path $f)) { Dur "Eksik dosya: $f  (git pull gerekebilir - Adim 2)" }
}
Tamam "Gerekli dosyalar var"

# ---------------------------------------------------------------- ADIM 2
Adim 2 "Guncel kod (git pull)"
$dal = (git rev-parse --abbrev-ref HEAD).Trim()
if ($dal -ne $Branch) { Uyari "Dal: $dal (beklenen: $Branch)"; Devam "Yine de devam edilsin mi" } else { Tamam "Dal: $dal" }
$ErrorActionPreference = "Continue"
git pull --ff-only origin $Branch 2>&1 | ForEach-Object { Write-Host "    $_" }
if ($LASTEXITCODE -ne 0) { Dur "git pull basarisiz. Cikti yukarida." }
$ErrorActionPreference = "Stop"
Tamam "git pull tamam"

# ---------------------------------------------------------------- ADIM 3
Adim 3 "Inceleme modu (REVIEW_MODE) ve testler"
if (-not (Test-Path "REVIEW_MODE")) { New-Item REVIEW_MODE -ItemType File | Out-Null; Tamam "REVIEW_MODE olusturuldu (zamanli video private cikar)" } else { Tamam "REVIEW_MODE var" }
$ErrorActionPreference = "Continue"
& $Py -m unittest test_daily_limit test_manual_topic test_kaynak 2>&1 | ForEach-Object { Write-Host "    $_" }
$testSonuc = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($testSonuc -ne 0) { Dur "Birim testleri basarisiz." }
Tamam "Birim testleri gecti"

# ---------------------------------------------------------------- ADIM 4
Adim 4 "Bugun kac video var? (gunluk sinir 2)"
$ErrorActionPreference = "Continue"
& $Py daily_check.py 2>&1 | Select-Object -First 12 | ForEach-Object { Write-Host "    $_" }
$ErrorActionPreference = "Stop"
Devam "Devam edilsin mi"

# ---------------------------------------------------------------- ADIM 5
Adim 5 "Ses sunucusu"
$env:AURA_VOICE_URL = "http://127.0.0.1:8124"
if (Test-Path ".voice_key") { $env:AURA_VOICE_KEY = (Get-Content ".voice_key" -Raw).Trim() }
elseif (-not $env:AURA_VOICE_KEY) {
    $m = Select-String -Path "daily_auto.bat" -Pattern "set AURA_VOICE_KEY=(.+)" | Select-Object -First 1
    if ($m) { $env:AURA_VOICE_KEY = $m.Matches[0].Groups[1].Value.Trim() }
}
if ($env:AURA_VOICE_KEY) { Tamam "Ses anahtari ortama alindi (degeri gosterilmez)" } else { Uyari "Ses anahtari bulunamadi" }
function SesAcik { try { $r = Invoke-WebRequest -Uri "http://127.0.0.1:8124/health" -UseBasicParsing -TimeoutSec 4; return ($r.Content -match '"model_loaded"\s*:\s*true') } catch { return $false } }
if (SesAcik) { Tamam "Ses sunucusu acik" }
else {
    Uyari "Ses sunucusu KAPALI."
    Write-Host "  Mission Control > Durum sekmesi > 'Ses sunucusunu baslat' butonuna bas, 40-90 sn bekle."
    for ($i = 1; $i -le 12; $i++) { Read-Host "  Basinca Enter (kontrol $i/12)" | Out-Null; if (SesAcik) { break } else { Uyari "Henuz hazir degil" } }
    if (-not (SesAcik)) { Dur "Ses sunucusu acilmadi. Video uretilemez." }
    Tamam "Ses sunucusu acik"
}

# ---------------------------------------------------------------- ADIM 6
Adim 6 "KAYNAK (kodla cekilir; alinti elle kopyalanmaz)"
if ($Url) { $url = $Url.Trim() } else { $url = (Read-Host "  Kaynak sayfa adresi (https:// ile baslayan)").Trim() }
if ($url -notmatch '^https?://') { Dur "Adres http:// veya https:// ile baslamali." }
$ErrorActionPreference = "Continue"
if ($Evet) { & $Py kaynak_cek.py $url --auto "--select=$Sec" "--facts=$Facts" } else { & $Py kaynak_cek.py $url }
$kcSonuc = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($kcSonuc -ne 0) { Dur "Kaynak cekilemedi (yukaridaki mesaja bak)." }
$paketYol = (Get-Content "_engine\kaynak_son.txt" -Raw).Trim()
if (-not (Test-Path $paketYol)) { Dur "Kaynak paketi bulunamadi: $paketYol" }
$paket = Get-Content $paketYol -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $paket.claim) { Uyari "Sayfada iddia cumlesi bulunamadi. Video 'sayfa ne diyor' tarzinda olur." }
if ($paket.evidence.Count -lt 1) { Dur "Hic kanit cumlesi secilmedi." }
Write-Host ""
Write-Host "  Konu : $($paket.topic)"
Write-Host "  Kanit: $($paket.evidence.Count) cumle | Paket: $paketYol"
$ErrorActionPreference = "Continue"
& $Py claim_lint.py $paket.topic 2>&1 | ForEach-Object { Write-Host "    $_" }
$ErrorActionPreference = "Stop"
Devam "Plan dogru mu? Devam edilsin mi"

# ---------------------------------------------------------------- ADIM 7
Adim 7 "Plan onizleme (hicbir sey yuklenmez)"
$ErrorActionPreference = "Continue"
& $Py aura_engine.py --plan-only --source $paketYol 2>&1 | ForEach-Object { Write-Host "    $_" }
if ($LASTEXITCODE -ne 0) { Dur "Plan adimi hata verdi." }
$ErrorActionPreference = "Stop"
Devam "Uretime (private yukleme) gecilsin mi"

# ---------------------------------------------------------------- ADIM 8
Adim 8 "Uretim (2-4 dk). Pencereyi kapatma, bilgisayari kilitleme/uyutma."
$log = "_gunluk_$(Get-Date -Format 'yyyyMMdd_HHmm').log"
$ErrorActionPreference = "Continue"
& $Py -u aura_engine.py --short-upload --source $paketYol 2>&1 | Tee-Object -FilePath $log | ForEach-Object { Write-Host "    $_" }
$ErrorActionPreference = "Stop"
Tamam "Cikti kaydedildi: $log"

# ---------------------------------------------------------------- ADIM 9
Adim 9 "Inceleme raporu"
$ErrorActionPreference = "Continue"
& $Py explain_run.py 2>&1 | ForEach-Object { Write-Host "    $_" }
$ErrorActionPreference = "Stop"

$gun = Get-Date -Format "yyyy-MM-dd"
$kayit = Join-Path $PSScriptRoot "_engine\$gun\.uploaded_today.json"
if (-not (Test-Path $kayit)) {
    Uyari "Bugun icin yukleme kaydi yok - video uretilmedi/yuklenmedi. Yukaridaki cikti ve $log dosyasina bak."
    exit 0
}
$bilgi = Get-Content $kayit -Raw | ConvertFrom-Json
$vid = $bilgi.video_id
Tamam "Yuklenen video: https://youtu.be/$vid  (PRIVATE ise Studio'da Ozel gorunur)"

# ---------------------------------------------------------------- ADIM 10
Adim 10 "Yayin karari (sadece SEN)"
Write-Host "  Kontrol listesi:"
Write-Host "   0) Motorun [source_check] satiri TEMIZ mi? (degilse video zaten private; nedenini oku)"
Write-Host "   1) Metindeki HER alinti kaynak sayfadaki cumlelerle birebir ayni mi?"
Write-Host "   2) Niyet atfi (gizlice / orttu / tuzak / kasten) yok mu?"
Write-Host "   3) Kaynaksiz rakam veya ucuncu sirket adi yok mu?"
Write-Host "   4) Baslik soru-ima degil, nesnel mi?"
$k = Read-Host "  Hepsi dogruysa YAYINLA yaz; degilse bos birak (video private kalir, Studio'dan silebilirsin)"
if ($k -ceq "YAYINLA") {
    $ErrorActionPreference = "Continue"
    & $Py publish_youtube.py $vid 2>&1 | ForEach-Object { Write-Host "    $_" }
    Tamam "Yayin komutu calisti. Studio'da kontrol et."
} else {
    Uyari "Yayinlanmadi. Video private. Silmek veya sonra yayinlamak sende."
}
Write-Host ""
Write-Host "Bitti. Aksam: python daily_check.py" -ForegroundColor Cyan
